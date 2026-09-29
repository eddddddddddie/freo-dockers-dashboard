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

from theme import inject_css, header_band, match_band, chat_header, insight_card
import auth
import layout
import data as D
import views as V
import chatbot as C
import insights as I
import deepdives as DD

inject_css()
auth.require_login()          # stops here until signed in
win_w, win_h = layout.window_size()
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


def example_prompts(season, baseline):
    prompts = [
        "How do our losses differ from our wins?",
        "Which players lift in finals?",
        "Where are we losing the clearance battle?",
    ]
    prompts.insert(1, f"What has changed most since {baseline}?" if baseline
                   else "Which quarter do we fade in, and against whom?")
    return prompts


# ------------------------------------------------------------ Wharf-ai
DEEP_DIVES = ["Player map", "Year on year", "Opponents", "Quarter-time check"]


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

    chat_header()
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
            st.caption("Try asking")
            for i, q in enumerate(example_prompts(season, baseline)):
                if st.button(q, key=f"ex_{i}", use_container_width=True,
                             disabled=client is None):
                    clicked = q
        for msg in msgs:
            with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
                st.markdown(msg["content"])
                for fig_json in msg.get("charts", []):
                    _show_chart(fig_json)
        if client is None:
            st.caption("Questions need ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID "
                       "for multi-workspace keys) in the environment or app secrets.")

    typed = st.chat_input("Ask Wharf-ai about the data", disabled=client is None)
    pending = st.session_state.pop("pending_prompt", None)  # sent from a deep dive
    prompt = typed or clicked or (pending if client is not None else None)
    if not prompt:
        return
    msgs.append({"role": "user", "content": prompt})
    with history:
        with st.chat_message("user", avatar=AVATARS["user"]):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            status = st.empty()
            steps, charts = [], []

            def on_tool(name, args):
                steps.append(TOOL_LABELS.get(name, name))
                status.caption("Calculating: " + ", ".join(steps))

            try:
                reply = st.write_stream(C.stream_answer(
                    client, season, msgs, opening=st.session_state[key], on_tool=on_tool,
                    on_chart=lambda fig: charts.append(fig.to_json()), focus=focus))
                for fig_json in charts:  # drawn under the answer text
                    _show_chart(fig_json)
            except Exception as exc:  # show API errors instead of crashing the app
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(f"Sorry, Wharf-ai hit an error: {exc}")
                return
    msgs.append({"role": "assistant", "content": reply, "charts": charts})
    # Redraw without the example prompts. A question handed over from a deep
    # dive arrives on a full-app run, where a fragment-only rerun is not allowed.
    st.rerun() if pending and not (typed or clicked) else st.rerun(scope="fragment")


# ------------------------------------------------------------- layout
main, side = st.columns([3.55, 1])
focus = None

with main:
    h1, h2, h3, h4 = st.columns([5.4, 0.88, 1.02, 1.0], vertical_alignment="center")
    with h2:
        season = st.segmented_control("Season", all_seasons, default=all_seasons[-1],
                                      key="season", label_visibility="collapsed")
    with h3:
        view = st.segmented_control("View", ["Season", "Match"], default="Season",
                                    key="view", label_visibility="collapsed") or "Season"
    season = season or all_seasons[-1]
    baseline = D.baseline_season(season, all_seasons)
    tdf = D.team_season(team_df, season)
    pos = None
    with h1:
        if view == "Match" and len(tdf):
            pick, band = st.columns([1.4, 3.0], vertical_alignment="center")
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
    if pos is not None:
        V.render_match(team_df, player_df, season, pos, SZ)
    else:
        V.render(team_df, player_df, season, baseline, SZ)

with side, st.container(border=True, height=PANEL_H, key="card_wharfai"):
    chat_panel(season, baseline, focus)
