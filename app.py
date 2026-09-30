"""Fremantle Dockers Coach View: the whole season on one screen.

Run with:  streamlit run app.py
One screen with no page scroll, sized to the browser window (layout.py): the
dashboard on the left, the Wharf-ai chat panel down the right. Sign-in needs
APP_USERNAME / APP_PASSWORD in the environment or Streamlit secrets. Wharf-ai opens with an insight
computed from the data (no API needed); answering questions needs
ANTHROPIC_API_KEY (environment or Streamlit secrets), plus
ANTHROPIC_WORKSPACE_ID (wrkspc_...) for multi-workspace keys.
"""

import html
import os
import random

import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fremantle Dockers Coach View",
                   page_icon="🟣", layout="wide",
                   initial_sidebar_state="collapsed")

from theme import (inject_css, header_band, match_band, scout_band, player_band, chat_header,
                   insight_card)
import auth
import layout
import data as D
import views as V
import chatbot as C
import insights as I
import deepdives as DD
import usage as U
import tour
import nav

inject_css()
auth.require_login()          # stops here until signed in (a valid cookie signs in too)
auth.cookie_sync()            # stores the "keep me signed in" cookie after sign-in
win_w, win_h = layout.window_size()
tour.show()                   # first-visit walkthrough (once per browser)
if st.session_state.pop("restored", False) and "messages" not in st.session_state:
    # Signed back in from the cookie: carry on this session's Wharf-ai chat.
    st.session_state["messages"] = U.load_chat(st.session_state.get("sid"))
SZ = layout.sizes(win_h, win_w)

team_df = D.load_team()
player_df = D.load_players()
all_seasons = D.seasons(team_df)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
AVATARS = {"user": os.path.join(ASSETS, "supporter.svg"),        # supporter in a bobble beanie
           "assistant": os.path.join(ASSETS, "anchor.svg")}      # Wharf-ai's anchor
PANEL_H = SZ["panel"]       # Wharf-ai panel height (px), level with the dashboard bottom
HISTORY_H = SZ["history"]   # scrolling area inside the panel
TOOL_LABELS = {
    "team_games": "listing games", "team_aggregate": "averaging team stats",
    "correlate": "checking a correlation", "quarter_breakdown": "breaking down quarters",
    "player_aggregate": "comparing players", "player_games": "pulling player games",
    "show_chart": "drawing a chart",
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
        "Who were our best players in this game?",
        "How did this game compare with our season average?",
        "Where did the game turn, quarter by quarter?",
    ] if focus else []
    season_q = [
        "How do our losses differ from our wins?",
        f"What has changed most since {baseline}?" if baseline else None,
        "Which quarter do we fade in, and against whom?",
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


SIDE_SHARE = 1 / 4.55          # the chat panel's share of the window width (columns 3.55 : 1)
CHAR_W = 6.4                   # average width of one character in panel text (px)


def _lines(text, width):
    return max(1, -(-int(len(text) * CHAR_W) // max(int(width), 1)))


def fitting_prompts(prompts, insight, win_w, history_h):
    """As many prompts as fit between the insight card and the chat box.
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
    return out or prompts[:3]


# ------------------------------------------------------------ Wharf-ai
DEEP_DIVES = ["Player map", "Year on year", "Opponents", "Quarter-time check",
              "Wharf-ai usage"]


def _pick_deep_dive():
    """Open the chosen deep dive on this run and reset the dropdown."""
    st.session_state["open_deep_dive"] = st.session_state.get("deep_dive")
    st.session_state["deep_dive"] = None


def wait_line(phrase, doing=None):
    """The waiting message: an AFL phrase with animated dots, and what Wharf-ai
    is calculating, if anything."""
    extra = f' <span class="wa-doing">· {html.escape(doing)}</span>' if doing else ""
    return (f'<div class="wa-wait">🏉 {html.escape(phrase)}<span class="wa-dots">...</span>'
            f'{extra}</div>')


def scroll_to_bottom(selector):
    """Scroll a scrolling container on the page to its end (Streamlit keeps the
    old scroll position when content is added)."""
    components.html(
        "<script>setTimeout(function(){var e=window.parent.document.querySelector("
        f"'{selector}');if(e){{e.scrollTop=e.scrollHeight;}}}},350);</script>", height=0)


def _show_chart(fig_json):
    st.plotly_chart(pio.from_json(fig_json), use_container_width=True,
                    config={"displayModeBar": False})


@st.fragment
def chat_panel(season, baseline, focus=None):
    """Runs as a fragment: asking a question reruns only this panel.
    focus: the match on screen in match mode, passed to Wharf-ai."""
    key = f"insight_{season}"
    if key not in st.session_state:
        st.session_state[key] = I.pick(team_df, player_df, season, baseline)
    msgs = st.session_state.setdefault("messages", [])
    client = C.get_client()
    # Which page the chat is about: the view and what is on it. Each message
    # records the page it was asked on, so moving to another page can offer
    # that page's questions above the earlier chat.
    page = focus or f"the {season} season"
    asked_before = {m["content"] for m in msgs if m["role"] == "user"}
    moved = bool(msgs) and msgs[-1].get("page") != page

    sid = st.session_state.get("sid")
    asked, limit = U.questions_today(), U.cap()
    mine, mine_limit = U.questions_this_login(sid), U.login_cap()
    chat_header(f"Answers from the match data only · {mine}/{mine_limit} of your questions today")
    day_capped, login_capped = asked >= limit, mine >= mine_limit
    capped = day_capped or login_capped
    history = st.container(height=HISTORY_H, border=False, key="wa_history")
    with history:
        insight = st.session_state[key]
        if insight:
            insight_card(insight)
            if st.button("↻ Another insight", key="more_insight", type="tertiary"):
                st.session_state[key] = I.pick(team_df, player_df, season, baseline,
                                               avoid=insight)
                st.rerun(scope="fragment")
        clicked = None
        if not msgs:
            # Fill the panel to the bottom: as many suggestions as fit under the insight.
            st.markdown('<div class="wa-sub">Try asking</div>', unsafe_allow_html=True)
            shown = fitting_prompts(example_prompts(season, baseline, focus), insight,
                                    win_w, HISTORY_H)
            for i, q in enumerate(shown):
                if st.button(q, key=f"ex_{i}", use_container_width=True,
                             disabled=client is None or capped):
                    clicked = q
        for n, msg in enumerate(msgs):
            with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
                if msg.get("steps"):
                    st.caption("Worked out with: " + ", ".join(msg["steps"]))
                st.markdown(msg["content"])
                for fig_json in msg.get("charts", []):
                    _show_chart(fig_json)
            # Follow-ups under the latest answer only, and only on the page they
            # were asked on (after a move, this page's questions sit above instead).
            if (msg["role"] == "assistant" and n == len(msgs) - 1 and msg.get("followups")
                    and not moved):
                st.markdown('<div class="wa-sub">Ask next</div>', unsafe_allow_html=True)
                for j, q in enumerate(msg["followups"]):
                    if st.button(q, key=f"fu_{n}_{j}", use_container_width=True,
                                 disabled=client is None or capped):
                        clicked = q
        if moved:
            # A chat has started on another page: the earlier chat stays, and this
            # page's questions follow it at the bottom, filling about half the chat
            # window. The chat is scrolled to the bottom so they are in view.
            st.markdown('<div class="wa-sub wa-earlier">Questions for this page</div>',
                        unsafe_allow_html=True)
            fresh = [q for q in example_prompts(season, baseline, focus) if q not in asked_before]
            for i, q in enumerate(fitting_prompts(fresh, None, win_w, HISTORY_H // 2 + 70)):
                if st.button(q, key=f"pq_{i}", use_container_width=True,
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
            steps, charts, followups = [], [], []
            phrases = random.sample(WAIT_PHRASES, len(WAIT_PHRASES))
            status.markdown(wait_line(phrases[0]), unsafe_allow_html=True)

            def on_tool(name, args):
                tally.tools.append(name)
                steps.append(TOOL_LABELS.get(name, name))
                status.markdown(wait_line(phrases[len(steps) % len(phrases)], steps[-1]),
                                unsafe_allow_html=True)

            try:
                reply = st.write_stream(C.stream_answer(
                    client, season, msgs, opening=st.session_state[key], on_tool=on_tool,
                    on_chart=lambda fig: charts.append(fig.to_json()), focus=focus,
                    on_followups=followups.extend, on_usage=tally.add_usage))
                for fig_json in charts:  # drawn under the answer text
                    _show_chart(fig_json)
                if steps:
                    status.caption("Worked out with: " + ", ".join(dict.fromkeys(steps)))
                else:
                    status.empty()
            except Exception as exc:  # show API errors instead of crashing the app
                U.record(prompt, tally, ok=False, sid=sid,
                         user_email=(auth.current_user() or {}).get("email"))
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(f"Sorry, Wharf-ai hit an error: {exc}")
                return
    U.record(prompt, tally, sid=sid, user_email=(auth.current_user() or {}).get("email"))
    if not followups:  # the model left them out: offer unasked suggestions instead
        asked_now = {m["content"] for m in msgs if m["role"] == "user"}
        followups = [q for q in example_prompts(season, baseline, focus) if q not in asked_now][:3]
    msgs.append({"role": "assistant", "content": reply, "charts": charts,
                 "followups": followups, "page": page, "steps": list(dict.fromkeys(steps))})
    U.save_chat(st.session_state.get("sid"), msgs)
    # Redraw without the example prompts. A question handed over from a deep
    # dive arrives on a full-app run, where a fragment-only rerun is not allowed.
    st.rerun() if pending and not (typed or clicked) else st.rerun(scope="fragment")


# ------------------------------------------------------------- layout
main, side = st.columns([3.55, 1])
focus = None
league = D.load_league()
CLUBS = sorted(t for t in league["team"].unique() if t != "Fremantle") if league is not None else []


def _game_label(season, rnd):
    """The game picker's label for a round in a season (for links like ?game=GF)."""
    tdf_ = D.team_season(team_df, season)
    for label, i in D.game_choices(tdf_):
        if tdf_["round"].iloc[i] == rnd:
            return label
    return None


# A queued move from a click, or the web address on a visit's first run.
nav.apply_pending(all_seasons, _game_label,
                  lambda s: D.player_list(D.players_season(player_df, s)), lambda: CLUBS)

with main:
    h1, h2, h3, h4, h5, h6 = st.columns([4.4, 0.84, 1.66, 0.98, 0.24, 0.24],
                                         vertical_alignment="center")
    with h2:
        season = st.segmented_control("Season", all_seasons, default=all_seasons[-1],
                                      key="season", label_visibility="collapsed")
    with h3:
        views = [v for v in nav.VIEWS if v != "Scout" or league is not None]
        view = st.segmented_control("View", views, default="Season",
                                    key="view", label_visibility="collapsed") or "Season"
    season = season or all_seasons[-1]
    baseline = D.baseline_season(season, all_seasons)
    tdf = D.team_season(team_df, season)
    pdf_season = D.players_season(player_df, season)
    pos = scout = player = game_round = None
    with h1:
        if view == "Scout" and league is not None:
            pick, band = st.columns([1.12, 3.3], vertical_alignment="center")
            if st.session_state.get("scout_team") not in CLUBS:
                last_opp = tdf["opponent"].iloc[-1] if len(tdf) else CLUBS[0]
                st.session_state["scout_team"] = last_opp if last_opp in CLUBS else CLUBS[0]
            with pick:
                scout = st.selectbox("Opponent", CLUBS, key="scout_team",
                                     label_visibility="collapsed")
            with band:
                lad = D.ladder(league, season)
                games = league[(league["season"] == season) & (league["team"] == scout)].tail(5)
                last5 = [(r.result, f"{r.api_round} v {r.opponent}: {r.score_for} to {r.score_against}")
                         for r in games.itertuples()]
                scout_band(scout, season, lad.loc[scout], last5)
            focus = f"the opponent scout report for {scout}, {season} season"
        elif view == "Player":
            names = D.player_list(pdf_season)
            if st.session_state.get("player_pick") not in names:
                st.session_state["player_pick"] = names[0]
            pick, band = st.columns([1.12, 3.3], vertical_alignment="center")
            with pick:
                player = st.selectbox("Player", names, key="player_pick",
                                      label_visibility="collapsed")
            with band:
                player_band(player, season, pdf_season[pdf_season["player"] == player])
            focus = f"the player profile for {player}, {season} season"
        elif view == "Match" and len(tdf):
            pick, band = st.columns([1.12, 3.3], vertical_alignment="center")
            choices = D.game_choices(tdf)
            with pick:
                label = st.selectbox("Game", [c[0] for c in choices], key=f"game_{season}",
                                     label_visibility="collapsed")
            pos = dict(choices)[label]
            game = tdf.iloc[pos]
            game_round = game["round"]
            with band:
                match_band(game, f"{game['venue']} · {game['game_dt']:%a %d %b %Y}")
            focus = (f"{game['round']} v {game['opponent']} at {game['venue']}, "
                     f"{'won' if game['result'] == 'W' else 'lost'} by {abs(int(game['margin']))}")
        else:
            last = tdf.tail(5)
            form = [(r.result, f"{r.round} vs {r.opponent}: {r.freo_score} to {r.opp_score}")
                    for r in last.itertuples()]
            note = (f"{len(tdf)} games to {tdf['round'].iloc[-1]}, "
                    f"{tdf['game_dt'].iloc[-1]:%d %b}") if len(tdf) else "No games"
            if baseline is not None:
                note += f" · vs {baseline}"
            header_band(season, D.record(tdf), form, note)
    with h4:
        # A dropdown rather than a popover: it closes itself on a pick, so it
        # never sits on top of the dialog it opens.
        st.selectbox("Deep dives", list(DEEP_DIVES), index=None, placeholder="Deep dives",
                     key="deep_dive", label_visibility="collapsed", on_change=_pick_deep_dive)
    with h5:
        # The walkthrough has its own button (it also runs once, on first sign-in).
        if st.button("?", key="tour_btn", help="Take the app tour"):
            tour.replay()
            st.rerun()
    with h6:
        who = (auth.current_user() or {}).get("email")
        if st.button("", icon=":material/logout:", key="signout_btn",
                     help=f"Sign out ({who})" if who else "Sign out"):
            auth.sign_out()
    nav.write_url(season, view, game=game_round, player=player, opp=scout)
    dive = st.session_state.pop("open_deep_dive", None)
    if dive == "Player map":
        DD.player_map(player_df, season)
    elif dive == "Year on year":
        DD.year_on_year(player_df, all_seasons)
    elif dive == "Opponents":
        DD.opponents(team_df, all_seasons)
    elif dive == "Quarter-time check":
        DD.quarter_time(team_df, all_seasons)
    elif dive == "Wharf-ai usage":
        DD.usage_log()
    if scout is not None:
        V.render_scout(team_df, league, season, scout, SZ)
    elif player is not None:
        V.render_player(player_df, season, baseline, player, SZ)
    elif pos is not None:
        V.render_match(team_df, player_df, season, pos, SZ)
    else:
        V.render(team_df, player_df, season, baseline, SZ)

with side, st.container(border=True, height=PANEL_H, key="card_wharfai"):
    chat_panel(season, baseline, focus)
