"""Fremantle Dockers Coach View: the whole season on one screen.

Run with:  streamlit run app.py
Laid out for a 1440x900 display with no page scroll: the dashboard on the
left, the Wharf-ai chat panel down the right. Wharf-ai opens with an insight
computed from the data (no API needed); answering questions needs
ANTHROPIC_API_KEY (environment or Streamlit secrets), plus
ANTHROPIC_WORKSPACE_ID (wrkspc_...) for multi-workspace keys.
"""

import os

import streamlit as st

st.set_page_config(page_title="Fremantle Dockers Coach View",
                   page_icon="🟣", layout="wide",
                   initial_sidebar_state="collapsed")

from theme import inject_css, header_band, chat_header, insight_card
import data as D
import views as V
import chatbot as C
import insights as I
import deepdives as DD

inject_css()

team_df = D.load_team()
player_df = D.load_players()
all_seasons = D.seasons(team_df)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
AVATARS = {"user": os.path.join(ASSETS, "supporter.svg"),        # supporter in a bobble beanie
           "assistant": os.path.join(ASSETS, "anchor.svg")}      # Wharf-ai's anchor
PANEL_H = 722       # Wharf-ai panel height (px), level with the dashboard bottom
HISTORY_H = 570     # scrolling area inside the panel


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
@st.fragment
def chat_panel(season, baseline):
    """Runs as a fragment: asking a question reruns only this panel."""
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
            try:
                reply = st.write_stream(C.stream_answer(
                    client, C.build_context("team", "player"), season, msgs,
                    opening=st.session_state[key]))
            except Exception as exc:  # show API errors instead of crashing the app
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(f"Sorry, Wharf-ai hit an error: {exc}")
                return
    msgs.append({"role": "assistant", "content": reply})
    # Redraw without the example prompts. A question handed over from a deep
    # dive arrives on a full-app run, where a fragment-only rerun is not allowed.
    st.rerun() if pending and not (typed or clicked) else st.rerun(scope="fragment")


# ------------------------------------------------------------- layout
main, side = st.columns([3.55, 1])

with main:
    h1, h2, h3 = st.columns([5.6, 1, 0.95], vertical_alignment="center")
    with h2:
        season = st.segmented_control("Season", all_seasons, default=all_seasons[-1],
                                      key="season", label_visibility="collapsed")
    season = season or all_seasons[-1]
    baseline = D.baseline_season(season, all_seasons)
    tdf = D.team_season(team_df, season)
    with h1:
        last = tdf.tail(5)
        form = [(r.result, f"{r.round} vs {r.opponent}: {r.freo_score} to {r.opp_score}")
                for r in last.itertuples()]
        note = (f"{len(tdf)} games to {tdf['round'].iloc[-1]} "
                f"({tdf['game_dt'].iloc[-1]:%d %b %Y})") if len(tdf) else "No games"
        if baseline is not None:
            note += f" · changes vs {baseline}"
        header_band(season, D.record(tdf), form, note)
    with h3, st.popover("Deep dives", use_container_width=True):
        if st.button("Player map", use_container_width=True):
            DD.player_map(player_df, season)
        if st.button("Year on year", use_container_width=True):
            DD.year_on_year(player_df, all_seasons)
        if st.button("Opponents", use_container_width=True):
            DD.opponents(team_df, all_seasons)
    V.render(team_df, player_df, season, baseline)

with side, st.container(border=True, height=PANEL_H):
    chat_panel(season, baseline)
