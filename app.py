"""Fremantle Dockers Coach View: the whole season on one screen.

Run with:  streamlit run app.py
One screen with no page scroll, sized to the browser window (layout.py): the
dashboard on the left, the Wharf-ai chat panel down the right. Sign-in needs
APP_USERNAME / APP_PASSWORD in the environment or Streamlit secrets. Wharf-ai opens with an insight
computed from the data (no API needed); answering questions needs
ANTHROPIC_API_KEY (environment or Streamlit secrets), plus
ANTHROPIC_WORKSPACE_ID (wrkspc_...) for multi-workspace keys.
"""

import os

import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="Fremantle Dockers Coach View",
                   page_icon="🟣", layout="wide",
                   initial_sidebar_state="collapsed")

from theme import (inject_css, header_band, match_band, scout_band, chat_header,
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

inject_css()
auth.require_login()          # stops here until signed in
win_w, win_h = layout.window_size()
tour.show()                   # first-visit walkthrough (once per browser)
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


def example_prompts(season, baseline, focus=None):
    """Suggested questions, most useful first. The panel shows as many as fit."""
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
              "Wharf-ai usage", "App tour"]


def _pick_deep_dive():
    """Open the chosen deep dive on this run and reset the dropdown."""
    st.session_state["open_deep_dive"] = st.session_state.get("deep_dive")
    st.session_state["deep_dive"] = None


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

    asked, limit = U.questions_today(), U.cap()
    chat_header(f"Answers from the match data only · {asked}/{limit} questions today")
    capped = asked >= limit
    history = st.container(height=HISTORY_H, border=False)
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
                             disabled=client is None):
                    clicked = q
        for n, msg in enumerate(msgs):
            with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
                st.markdown(msg["content"])
                for fig_json in msg.get("charts", []):
                    _show_chart(fig_json)
            # Follow-ups under the latest answer only.
            if msg["role"] == "assistant" and n == len(msgs) - 1 and msg.get("followups"):
                st.markdown('<div class="wa-sub">Ask next</div>', unsafe_allow_html=True)
                for j, q in enumerate(msg["followups"]):
                    if st.button(q, key=f"fu_{n}_{j}", use_container_width=True,
                                 disabled=client is None):
                        clicked = q
        if client is None:
            st.caption("Questions need ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID "
                       "for multi-workspace keys) in the environment or app secrets.")

    typed = st.chat_input("Daily question limit reached; resets at midnight Perth time"
                          if capped else "Ask Wharf-ai about the data",
                          disabled=client is None or capped)
    pending = st.session_state.pop("pending_prompt", None)  # sent from a deep dive
    prompt = typed or clicked or (pending if client is not None else None)
    if not prompt:
        return
    if capped:
        with history:
            st.info(f"Wharf-ai has answered {limit} questions today, the daily limit. "
                    "It resets at midnight Perth time.")
        return
    tally = U.Tally()
    msgs.append({"role": "user", "content": prompt})
    with history:
        with st.chat_message("user", avatar=AVATARS["user"]):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            status = st.empty()
            steps, charts, followups = [], [], []

            def on_tool(name, args):
                tally.tools.append(name)
                steps.append(TOOL_LABELS.get(name, name))
                status.caption("Calculating: " + ", ".join(steps))

            try:
                reply = st.write_stream(C.stream_answer(
                    client, season, msgs, opening=st.session_state[key], on_tool=on_tool,
                    on_chart=lambda fig: charts.append(fig.to_json()), focus=focus,
                    on_followups=followups.extend, on_usage=tally.add_usage))
                for fig_json in charts:  # drawn under the answer text
                    _show_chart(fig_json)
            except Exception as exc:  # show API errors instead of crashing the app
                U.record(prompt, tally, ok=False)
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(f"Sorry, Wharf-ai hit an error: {exc}")
                return
    U.record(prompt, tally)
    if not followups:  # the model left them out: offer unasked suggestions instead
        asked = {m["content"] for m in msgs if m["role"] == "user"}
        followups = [q for q in example_prompts(season, baseline, focus) if q not in asked][:3]
    msgs.append({"role": "assistant", "content": reply, "charts": charts,
                 "followups": followups})
    # Redraw without the example prompts. A question handed over from a deep
    # dive arrives on a full-app run, where a fragment-only rerun is not allowed.
    st.rerun() if pending and not (typed or clicked) else st.rerun(scope="fragment")


# ------------------------------------------------------------- layout
main, side = st.columns([3.55, 1])
focus = None

with main:
    h1, h2, h3, h4 = st.columns([5.05, 0.86, 1.34, 1.07], vertical_alignment="center")
    with h2:
        season = st.segmented_control("Season", all_seasons, default=all_seasons[-1],
                                      key="season", label_visibility="collapsed")
    league = D.load_league()
    with h3:
        views = ["Season", "Match"] + (["Scout"] if league is not None else [])
        view = st.segmented_control("View", views, default="Season",
                                    key="view", label_visibility="collapsed") or "Season"
    season = season or all_seasons[-1]
    baseline = D.baseline_season(season, all_seasons)
    tdf = D.team_season(team_df, season)
    pos = scout = None
    with h1:
        if view == "Scout":
            pick, band = st.columns([1.12, 3.3], vertical_alignment="center")
            clubs = sorted(t for t in league["team"].unique() if t != "Fremantle")
            last_opp = tdf["opponent"].iloc[-1] if len(tdf) else clubs[0]
            with pick:
                scout = st.selectbox("Opponent", clubs, index=clubs.index(last_opp),
                                     key="scout_team", label_visibility="collapsed")
            with band:
                lad = D.ladder(league, season)
                games = league[(league["season"] == season) & (league["team"] == scout)].tail(5)
                last5 = [(r.result, f"{r.api_round} v {r.opponent}: {r.score_for} to {r.score_against}")
                         for r in games.itertuples()]
                scout_band(scout, season, lad.loc[scout], last5)
            focus = f"the opponent scout report for {scout}, {season} season"
        elif view == "Match" and len(tdf):
            pick, band = st.columns([1.12, 3.3], vertical_alignment="center")
            choices = D.game_choices(tdf)
            with pick:
                label = st.selectbox("Game", [c[0] for c in choices], key=f"game_{season}",
                                     label_visibility="collapsed")
            pos = dict(choices)[label]
            game = tdf.iloc[pos]
            with band:
                match_band(game, f"{game['venue']} · {game['game_dt']:%a %d %b %Y}")
            focus = (f"{game['round']} v {game['opponent']} at {game['venue']}, "
                     f"{'won' if game['result'] == 'W' else 'lost'} by {abs(int(game['margin']))}")
        else:
            last = tdf.tail(5)
            form = [(r.result, f"{r.round} vs {r.opponent}: {r.freo_score} to {r.opp_score}")
                    for r in last.itertuples()]
            note = (f"{len(tdf)} games to {tdf['round'].iloc[-1]} "
                    f"({tdf['game_dt'].iloc[-1]:%d %b %Y})") if len(tdf) else "No games"
            if baseline is not None:
                note += f" · changes vs {baseline}"
            header_band(season, D.record(tdf), form, note)
    with h4:
        # A dropdown rather than a popover: it closes itself on a pick, so it
        # never sits on top of the dialog it opens.
        st.selectbox("Deep dives", list(DEEP_DIVES), index=None, placeholder="Deep dives",
                     key="deep_dive", label_visibility="collapsed", on_change=_pick_deep_dive)
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
    elif dive == "App tour":
        tour.replay()
        st.rerun()
    if scout is not None:
        V.render_scout(team_df, league, season, scout, SZ)
    elif pos is not None:
        V.render_match(team_df, player_df, season, pos, SZ)
    else:
        V.render(team_df, player_df, season, baseline, SZ)

with side, st.container(border=True, height=PANEL_H, key="card_wharfai"):
    chat_panel(season, baseline, focus)
