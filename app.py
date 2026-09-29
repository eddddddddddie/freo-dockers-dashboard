"""Fremantle Dockers performance dashboard.

Run with:  streamlit run app.py
The chatbot needs ANTHROPIC_API_KEY. Multi-workspace keys also need
ANTHROPIC_WORKSPACE_ID (wrkspc_...). The dashboard works without either.
"""

import streamlit as st

st.set_page_config(page_title="Fremantle Dockers Performance",
                   page_icon="🟣", layout="wide")

from theme import inject_css, band
import data as D
import views as V
import chatbot as C

inject_css()

team_df = D.load_team()
player_df = D.load_players()
all_seasons = D.seasons(team_df)

# ------------------------------------------------------------ sidebar
st.sidebar.markdown("## Fremantle Dockers")
st.sidebar.caption("Performance dashboard")

season = st.sidebar.radio("Season", all_seasons, index=len(all_seasons) - 1)
baseline = D.baseline_season(season, all_seasons)

PAGES = {
    "Season Overview": V.render_overview,
    "Home": V.render_home,
    "Midfield & Contest": V.render_midfield,
    "Ball Movement & Scoring": V.render_ball_movement,
    "Defence": V.render_defence,
    "Players": V.render_players,
    "Role Leaders": V.render_roles,
}
page = st.sidebar.radio("Page", list(PAGES.keys()))

st.sidebar.markdown("---")
if baseline is not None:
    st.sidebar.caption(f"Baseline for comparisons: {baseline} season.")
else:
    st.sidebar.caption("No earlier season loaded for comparison.")

# ------------------------------------------------------------- header
subtitle = f"{len(D.team_season(team_df, season))} games loaded"
band(f"{page}", subtitle, season=season)

# --------------------------------------------------------- page body
PAGES[page](team_df, player_df, season, baseline)

# ----------------------------------------------------------- chatbot
st.markdown("---")
st.subheader("Ask the data")
st.caption("Questions are answered from the loaded box-score data only. The "
           "assistant will say when something is not in the data.")

client = C.get_client()
if client is None:
    st.info("Set ANTHROPIC_API_KEY and restart to enable the chat assistant. "
            "If your key is not scoped to a single workspace, also set "
            "ANTHROPIC_WORKSPACE_ID (from console Settings or the API keys page).")
else:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("e.g. How does our clearance work compare to last season?")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            context = C.build_context("team", "player")
            try:
                reply = st.write_stream(
                    C.stream_answer(client, context, season, st.session_state.messages)
                )
            except Exception as exc:  # surface API errors instead of crashing the app
                err = str(exc)
                if "anthropic-workspace-id" in err:
                    reply = (
                        "This API key is not tied to one workspace. Set "
                        "ANTHROPIC_WORKSPACE_ID to your workspace ID (starts with "
                        "wrkspc_) in the app secrets or environment, reboot the "
                        "app, and try again."
                    )
                else:
                    reply = f"Sorry, the assistant hit an error: {exc}"
                st.error(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
