"""Freo In Numbers: four places around a coach's week (v2.py).

Run with:  streamlit run app.py
The page on the left, the Wharf-ai chat panel in a sticky column on the right
(docked to the bottom of a narrow or short screen). Sign-in needs
APP_USERNAME / APP_PASSWORD in the environment or Streamlit secrets. Wharf-ai opens with an insight
computed from the data (no API needed); answering questions needs
ANTHROPIC_API_KEY (environment or Streamlit secrets), plus
ANTHROPIC_WORKSPACE_ID (wrkspc_...) for multi-workspace keys.
"""

import html
import os
import random
import time

import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Freo In Numbers",
                   page_icon="🟣", layout="wide",
                   initial_sidebar_state="collapsed")

from theme import (inject_css, inject_phone_css, inject_side_panel_css, brand_title, BALL_SVG, inject_tablet_css,
                   chat_header, insight_rotator)
import auth
import settings
import layout
import data as D
import chatbot as C
import evidence as E
import insights as I
import admin
import usage as U
import tour
import v2

inject_css()
# The window size is asked for first, so it is usually known by the time the
# dashboard draws (the sign-in page gives it time to arrive).
win_w, win_h = layout.window_size()
first_run = not st.session_state.get("_ran")
st.session_state["_ran"] = True
auth.require_login()          # stops here until signed in (a valid cookie signs in too)
auth.cookie_sync()            # stores the "keep me signed in" cookie after sign-in
if first_run and not layout.size_known():
    # Signed in straight away (cookie or Google) before the browser has said how
    # wide it is: wait for it rather than draw the desktop layout on a phone and
    # then jump. The size arrives in a moment and reruns the app.
    st.markdown('<div class="cv-wait">Loading Freo In Numbers...</div>', unsafe_allow_html=True)
    st.stop()
LAYOUT = layout.mode(win_w, win_h)      # phone, stack, split or desktop (see layout.mode)
PHONE = LAYOUT == "phone"
SCROLL = LAYOUT != "desktop"
# Wharf-ai docked to the bottom of the screen (narrow or short windows; v2.run
# decides the same), else a sticky panel beside the page.
DOCK = win_w < 1000 or win_h < 600
if PHONE:
    inject_phone_css()
elif SCROLL:
    inject_tablet_css()
if not DOCK:
    inject_side_panel_css()
tour.show(phone=PHONE)        # first-visit walkthrough (once per browser)
if st.session_state.pop("restored", False) and "messages" not in st.session_state:
    # Signed back in from the cookie: carry on this session's Wharf-ai chat.
    st.session_state["messages"] = U.load_chat(st.session_state.get("sid"))

team_df = D.load_team()
player_df = D.load_players()
all_seasons = D.seasons(team_df)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
AVATARS = {"user": os.path.join(ASSETS, "supporter.svg"),        # supporter in a bobble beanie
           "assistant": os.path.join(ASSETS, "anchor.svg")}      # Wharf-ai's anchor
PANEL_H = win_h - 60        # the side panel: the window less the top bar and a gap
HISTORY_H = max(300, int(win_h * 0.55)) if DOCK else PANEL_H - 150   # the chat's scrolling area
TOP_PROMPTS = 3 if PHONE or win_h < 500 else 4   # suggestions in the docked panel
TOOL_LABELS = {
    "team_games": "listing games", "team_aggregate": "averaging team stats",
    "correlate": "checking a correlation", "quarter_breakdown": "breaking down quarters",
    "player_aggregate": "comparing players", "player_games": "pulling player games",
    "show_chart": "drawing a chart", "league_aggregate": "comparing clubs",
    "ladder": "checking the ladder",
}
# Shown while Wharf-ai works, one per step, in the spirit of Claude Code's
# "Combobulating". A new one each time it starts a calculation.
WAIT_PHRASES = [
    "Inside 50ing", "Marking", "Drawing a free", "Taking a speccy", "Shepherding",
    "Handballing over the top", "Kicking truly", "Snapping around the corner",
    "Winning the hard ball", "Laying a tackle", "Going back to the mark", "Soccering it off the deck",
    "Running through the banner", "Checking the score review", "Threading a torpedo",
    "Reading the ruck tap", "Breaking the tag", "Arguing with the umpire (politely)",
    "Kicking it long to the square", "Rushing a behind",
]


def example_prompts(season, baseline, focus=None):
    """Suggested questions, most useful first. The panel shows as many as fit."""
    if focus and focus.startswith(f"the {season} season"):   # the season, cut to a slice
        focus = None
    if focus and focus.startswith("a comparison of "):
        pair = focus[len("a comparison of "):].split(",")[0]
        a, b = pair.split(" and ", 1)
        sa, sb = a.split()[-1], b.split()[-1]
        return [f"Who has had the better season, {a} or {b}?",
                f"Where is {sa} ahead of {sb}, and where is {sb} ahead?",
                f"Who is in better form over the last five games, {sa} or {sb}?",
                f"How do {sa} and {sb} compare in wins and in losses?",
                f"How do {sa} and {sb} compare with last season?",
                f"What is our record when both {sa} and {sb} play?",
                f"Who wins more of the contested ball, {sa} or {sb}?",
                f"Which games were {sa}'s and {sb}'s best this season?"]
    if focus and focus.startswith("the player profile for "):
        who = focus.split(" for ", 1)[1].split(",")[0]
        first = who.split()[0]
        return [f"How is {who} going this season?",
                f"Is {first} in form over the last five games?",
                f"How does {first} compare with last season?",
                f"Where does {first} rank in the squad?",
                f"What does {first} do in wins versus losses?",
                f"Which games were {first}'s best?"] + [
            q for q in example_prompts(season, baseline) if "players" in q.lower()]
    if focus and focus.startswith("the whole squad"):
        since = f" since {baseline}" if baseline else ""
        return [f"Who are our most improved players{since}?",
                f"Whose numbers have dropped most{since}?",
                "Which players gain the most metres per game?",
                "Who wins the most contested ball in the squad?",
                "Who leads our pressure acts, and does it matter?",
                "Which players have the most score involvements?"]
    if focus and focus.startswith("the opponent scout report for "):
        club = focus.split(" for ", 1)[1].split(",")[0]
        scout = [f"What wins {club} games?",
                 f"Where are {club} weakest compared with the league?",
                 f"How have we gone against {club}?",
                 f"How do {club} compare with us on contested ball?",
                 f"Which quarters do {club} win?",
                 f"How do {club} go when they lose the inside 50 count?"]
        focus = None
    else:
        scout = []
    match = [
        "Why did we win or lose this game?",
        "When did this game turn?",
        "Who were our best players in this game?",
        "How did this game compare with our season average?",
        "Where did the game turn, quarter by quarter?",
    ] if focus else []
    season_q = [
        "How do our losses differ from our wins?",
        f"What has changed most since {baseline}?" if baseline else None,
        "Which quarter do we fade in, and against whom?",
        "How often do we concede a run of three goals or more?",
        "Where are we losing the clearance battle?",
        "Which players are in the best form right now?",
        "Which players lift in finals?",
        "What do our close games have in common?",
        "How do we perform at home versus away?",
        "Which opponents have we struggled against?",
        f"Who are our most improved players since {baseline}?" if baseline else None,
        "Does winning the contested ball win us games?",
        "How has our goal kicking accuracy trended?",
        "Who leads our pressure acts, and does it matter?",
        "Which players gain the most metres per game?",
        "How did we finish the season compared with the start?",
        "Who are our most reliable goalkickers?",
        "Which players win the most clearances?",
        "What happens when we lose the inside 50 count?",
        "Who spends the most time on ground?",
    ]
    return scout + match + [q for q in season_q if q]


# The chat panel's share of the window width: columns 3.2 : 1 (v2.run).
SIDE_SHARE = 1 / 4.2
CHAR_W = 6.4                   # average width of one character in panel text (px)


def _lines(text, width):
    return max(1, -(-int(len(text) * CHAR_W) // max(int(width), 1)))


SIDE_PROMPTS = 4               # at most this many suggestions beside the page: a short list reads calmer


def fitting_prompts(prompts, insight, win_w, history_h):
    """Up to SIDE_PROMPTS prompts, as many as fit between the insight card and the chat box.
    Button and insight heights are estimated from text length and the panel
    width, since long prompts wrap onto two lines in a narrow panel."""
    # Measured at 1440 and 1920 wide: a prompt button is 30px (50px on two
    # lines) plus a 6px gap; the insight card is about 36px + 18px a line.
    panel_w = (win_w - 36) * SIDE_SHARE - 34
    used = 6 + 30 + 6 + 34 + 6                       # gaps, "Another insight", "Try asking"
    if insight:
        used += 36 + 18 * _lines(insight, panel_w - 26)
    out = []
    for q in prompts:
        h = 30 + 20 * (_lines(q, panel_w - 22) - 1) + 6
        if used + h > history_h:
            continue            # too tall for what is left: a shorter one may still fit
        used += h
        out.append(q)
        if len(out) == SIDE_PROMPTS:
            break
    return out or prompts[:3]


# ------------------------------------------------------------ Wharf-ai
AFL_PHOTO = ("https://s.afl.com.au/staticfile/AFL%20Tenant/AFL/Players/ChampIDImages/AFL/"
             "{season}014/{number}.png")


@st.cache_data(ttl=86400, show_spinner=False)
def _photo_exists(url):
    try:
        import requests
        return requests.head(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"}).ok
    except Exception:
        return False


def player_photo(player_id, season):
    """The AFL's headshot URL for a player, only when PLAYER_PHOTOS = "afl" is set
    in secrets (the photos are the AFL's; they're loaded from afl.com.au, never
    stored in the repo) and the photo exists. Otherwise None (initials)."""
    if (settings.get("PLAYER_PHOTOS") or "").lower() != "afl" or not player_id:
        return None
    number = str(player_id).replace("CD_I", "")
    for yr in (season, season - 1):
        url = AFL_PHOTO.format(season=yr, number=number)
        if _photo_exists(url):
            return url
    return None


def wait_line(phrase, doing=None, started=None):
    """The waiting message: a spinning red footy, an AFL phrase, what Wharf-ai is
    calculating, if anything, and a seconds counter from `started` (time.time())."""
    extra = f' <span class="wa-doing">· {html.escape(doing)}</span>' if doing else ""
    if started is not None:
        extra += (f' <span class="wa-secs" style="animation-delay:-{time.time() - started:.1f}s">'
                  '</span>')
    return f'<div class="wa-wait">{BALL_SVG} {html.escape(phrase)}{extra}</div>'


def scroll_to_bottom(selector):
    """Scroll a scrolling container on the page to its end (Streamlit keeps the
    old scroll position when content is added)."""
    components.html(
        "<script>setTimeout(function(){var e=window.parent.document.querySelector("
        f"'{selector}');if(e){{e.scrollTop=e.scrollHeight;}}}},350);</script>", height=0)


def _show_chart(fig_json):
    st.plotly_chart(pio.from_json(fig_json), width="stretch",
                    config={"displayModeBar": False})


def answer_extras(msg, n, msgs):
    """Under an answer: any number that couldn't be matched to a calculation,
    the tables it was worked out from, and a thumbs up or down."""
    if msg.get("unbacked"):
        st.markdown(f'<div class="wa-flag">Not matched to a calculation: '
                    f'{html.escape(", ".join(msg["unbacked"]))}. Check under Show the numbers.</div>',
                    unsafe_allow_html=True)
    found = msg.get("evidence") or []
    if found:
        with st.expander(f"Show the numbers ({len(found)} calculation{'s' if len(found) != 1 else ''})"):
            for rec in found:
                st.caption(E.describe(rec, TOOL_LABELS))
                df = E.table(rec)
                if df is not None:
                    st.dataframe(df, hide_index=True, width="stretch",
                                 height=min(36 + 35 * len(df), 260))
                else:
                    st.text(rec.get("text", ""))
    if msg.get("qid"):
        key = f"fb_{msg['qid']}"
        if key not in st.session_state and msg.get("rating") is not None:
            st.session_state[key] = msg["rating"]
        st.feedback("thumbs", key=key, on_change=_rate, args=(msg["qid"], n, msgs))


def _rate(qid, n, msgs):
    rating = st.session_state.get(f"fb_{qid}")
    U.rate(qid, rating)
    msgs[n]["rating"] = rating
    U.save_chat(st.session_state.get("sid"), msgs)


@st.cache_data(show_spinner=False)
def season_insights(season, baseline):
    """The season's insights, worked out once (the CSVs don't change while the
    app runs), not on every rerun of the chat panel."""
    return I.candidates(team_df, player_df, season, baseline)


@st.fragment
def chat_panel(season, baseline, focus=None):
    """Runs as a fragment: asking a question reruns only this panel.
    focus: the match on screen in match mode, passed to Wharf-ai."""
    key = f"insight_{season}"
    pool = season_insights(season, baseline)
    if key not in st.session_state or st.session_state[key] not in pool:
        st.session_state[key] = random.choice(pool) if pool else None
    msgs = st.session_state.setdefault("messages", [])
    client = C.get_client()
    # Which page the chat is about: the view and what is on it. Each message
    # records the page it was asked on, so moving to another page can offer
    # that page's questions above the earlier chat.
    page = focus or f"the {season} season"
    asked_before = {m["content"] for m in msgs if m["role"] == "user"}
    moved = bool(msgs) and msgs[-1].get("page") != page

    sid = st.session_state.get("sid")
    email = (auth.current_user() or {}).get("email")
    asked, limit = U.questions_today(), U.cap()
    mine, mine_limit = U.questions_this_login(sid), U.login_cap()
    if U.is_unlimited(email):   # WHARF_UNLIMITED: no per-person or daily limit
        chat_header(f"Answers from the data · {mine} questions today, no limit")
        day_capped = login_capped = False
    else:
        chat_header(f"Answers from the data · {mine}/{mine_limit} questions today")
        day_capped, login_capped = asked >= limit, mine >= mine_limit
    capped = day_capped or login_capped
    # On a phone the panel is as tall as its content until a chat starts, then
    # the chat scrolls inside about half the screen so the dashboard stays close.
    history_h = (HISTORY_H if msgs else "content") if DOCK else HISTORY_H
    history = st.container(height=history_h, border=False, key="wa_history")
    with history:
        insight = st.session_state[key]
        if insight:
            # Every insight for the season, rotating every 30 s in the browser,
            # starting with the chosen one; the button moves on straight away.
            start = pool.index(insight) if insight in pool else 0
            insight_rotator(pool, start=start, seconds=30)
            if st.button("↻ Another insight", key="more_insight", type="tertiary"):
                st.session_state[key] = pool[(start + 1) % len(pool)]
                st.rerun(scope="fragment")
        clicked = None
        if not msgs:
            # A few suggestions under the insight (as many as fit, at most SIDE_PROMPTS).
            st.markdown('<div class="wa-sub">Try asking</div>', unsafe_allow_html=True)
            longest = max(pool, key=len) if pool else insight  # the card is as tall as this
            shown = (example_prompts(season, baseline, focus)[:TOP_PROMPTS] if DOCK else
                     fitting_prompts(example_prompts(season, baseline, focus), longest,
                                     win_w, HISTORY_H))
            for i, q in enumerate(shown):
                if st.button(q, key=f"ex_{i}", width="stretch",
                             disabled=client is None or capped):
                    clicked = q
        for n, msg in enumerate(msgs):
            with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
                if msg.get("steps"):
                    st.caption("Worked out with: " + ", ".join(msg["steps"]))
                st.markdown(msg["content"])
                for fig_json in msg.get("charts", []):
                    _show_chart(fig_json)
                if msg["role"] == "assistant":
                    answer_extras(msg, n, msgs)
            # Follow-ups under the latest answer only, and only on the page they
            # were asked on (after a move, this page's questions sit above instead).
            if (msg["role"] == "assistant" and n == len(msgs) - 1 and msg.get("followups")
                    and not moved):
                st.markdown('<div class="wa-sub">Ask next</div>', unsafe_allow_html=True)
                for j, q in enumerate(msg["followups"]):
                    if st.button(q, key=f"fu_{n}_{j}", width="stretch",
                                 disabled=client is None or capped):
                        clicked = q
        if moved:
            # A chat has started on another page: the earlier chat stays, and this
            # page's questions follow it at the bottom, filling about half the chat
            # window. The chat is scrolled to the bottom so they are in view.
            st.markdown('<div class="wa-sub wa-earlier">Questions for this page</div>',
                        unsafe_allow_html=True)
            fresh = [q for q in example_prompts(season, baseline, focus) if q not in asked_before]
            page_qs = (fresh[:TOP_PROMPTS] if DOCK else
                       fitting_prompts(fresh, None, win_w, HISTORY_H // 2 + 70))
            for i, q in enumerate(page_qs):
                if st.button(q, key=f"pq_{i}", width="stretch",
                             disabled=client is None or capped):
                    clicked = q
            scroll_to_bottom(".st-key-wa_history")
        if client is None:
            st.caption("Questions need ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID "
                       "for multi-workspace keys) in the environment or app secrets.")

    placeholder = ("Daily question limit reached; resets at midnight Perth time" if day_capped
                   else f"You've used your {mine_limit} questions for today" if login_capped
                   else "Ask Wharf-ai about the data")
    typed = st.chat_input(placeholder, disabled=client is None or capped)
    pending = st.session_state.pop("pending_prompt", None)  # sent from a deep dive
    prompt = typed or clicked or (pending if client is not None else None)
    if not prompt:
        return
    if capped:
        with history:
            if day_capped:
                st.info(f"Wharf-ai has answered {limit} questions today, the daily limit. "
                        "It resets at midnight Perth time.")
            else:
                st.info(f"You've used your {mine_limit} Wharf-ai questions for today; more "
                        "tomorrow (midnight Perth time). The dashboard still works as normal.")
        return
    tally = U.Tally()
    msgs.append({"role": "user", "content": prompt, "page": page})
    with history:
        with st.chat_message("user", avatar=AVATARS["user"]):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            status = st.empty()
            steps, charts, followups, found = [], [], [], []
            phrases = random.sample(WAIT_PHRASES, len(WAIT_PHRASES))
            started = time.time()
            status.markdown(wait_line(phrases[0], started=started), unsafe_allow_html=True)

            def on_step(n):
                # A new model request after the tools ran. The API sends the
                # answer text in one go once it is written (text after tool calls
                # isn't streamed on this model), so say what is happening meanwhile.
                if n:
                    status.markdown(wait_line(phrases[(len(steps) + n) % len(phrases)],
                                              "writing the answer", started),
                                    unsafe_allow_html=True)

            def on_tool(name, args):
                tally.tools.append(name)
                steps.append(TOOL_LABELS.get(name, name))
                status.markdown(wait_line(phrases[len(steps) % len(phrases)], steps[-1], started),
                                unsafe_allow_html=True)

            try:
                reply = st.write_stream(C.stream_answer(
                    client, season, msgs, opening="\n".join(pool) or st.session_state[key],
                    on_tool=on_tool,
                    on_chart=lambda fig: charts.append(fig.to_json()), focus=focus,
                    on_followups=followups.extend, on_usage=tally.add_usage,
                    on_step=on_step,
                    on_result=lambda name, args, out, err: None if err else found.append(
                        E.item(name, args, out))))
                for fig_json in charts:  # drawn under the answer text
                    _show_chart(fig_json)
                if steps:
                    status.caption("Worked out with: " + ", ".join(dict.fromkeys(steps)))
                else:
                    status.empty()
            except Exception as exc:  # show API errors instead of crashing the app
                status.empty()
                U.record(prompt, tally, ok=False, sid=sid,
                         user_email=(auth.current_user() or {}).get("email"))
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(C.friendly_error(exc) or f"Sorry, Wharf-ai hit an error: {exc}")
                return
    # Numbers in the answer that none of this chat's calculations (or the
    # question, or the panel's insights) account for, listed under it to check.
    earlier = [r for m in msgs if m["role"] == "assistant" for r in m.get("evidence", [])]
    flagged = E.unbacked(reply, found + earlier, context="\n".join([prompt, focus or ""] + pool))
    qid = U.record(prompt, tally, sid=sid, user_email=(auth.current_user() or {}).get("email"),
                   answer=reply, unbacked=flagged)
    if not followups:  # the model left them out: offer unasked suggestions instead
        asked_now = {m["content"] for m in msgs if m["role"] == "user"}
        followups = [q for q in example_prompts(season, baseline, focus) if q not in asked_now][:3]
    msgs.append({"role": "assistant", "content": reply, "charts": charts,
                 "followups": followups, "page": page, "steps": list(dict.fromkeys(steps)),
                 "evidence": found, "unbacked": flagged, "qid": qid})
    U.save_chat(st.session_state.get("sid"), msgs)
    # Redraw without the example prompts. A question handed over from a deep
    # dive arrives on a full-app run, where a fragment-only rerun is not allowed.
    st.rerun() if pending and not (typed or clicked) else st.rerun(scope="fragment")


# ------------------------------------------------------------- the pages
# Five places around a coach's week (v2.py): the page on the left, Wharf-ai in a
# sticky panel on the right, or docked to the bottom of a narrow or short screen.
league = D.load_league()
CLUBS = sorted(t for t in league["team"].unique() if t != "Fremantle") if league is not None else []


def _game_label(season, rnd):
    """The game picker's label for a round in a season (for links like ?game=GF)."""
    tdf_ = D.team_season(team_df, season)
    for label, i in D.game_choices(tdf_):
        if tdf_["round"].iloc[i] == rnd:
            return label
    return None


def _signout():
    who = (auth.current_user() or {}).get("email")
    if st.button("", icon=":material/logout:", key="signout_btn",
                 help=f"Sign out ({who})" if who else "Sign out"):
        auth.sign_out()


def _usage():
    """Wharf-ai usage, for the people listed in WHARF_ADMINS only."""
    if U.is_admin((auth.current_user() or {}).get("email")):
        if st.button("", icon=":material/monitoring:", key="usage_btn", help="Wharf-ai usage"):
            admin.usage_log()


def _tour():
    tour.replay()
    st.rerun()


v2.run({
    "win": (win_w, win_h), "team": team_df, "player_df": player_df,
    "team_view": team_df, "player_view": player_df, "seasons": all_seasons,
    "league": league, "clubs": CLUBS, "game_label": _game_label,
    "players": lambda s: D.player_list(D.players_season(player_df, s)),
    "photo": player_photo, "chat_panel": chat_panel, "brand_title": brand_title,
    "usage_button": _usage, "signout_button": _signout, "tour_replay": _tour,
})
