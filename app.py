"""Fremantle Dockers Coach View: the whole season on one screen.

Run with:  streamlit run app.py
Laid out for a 1440x900 display with no page scroll. The chatbot opens in a
dialog and needs ANTHROPIC_API_KEY (environment or Streamlit secrets).
Multi-workspace keys also need ANTHROPIC_WORKSPACE_ID (wrkspc_...). The
dashboard works without either.
"""

import streamlit as st

st.set_page_config(page_title="Fremantle Dockers Coach View",
                   page_icon="🟣", layout="wide",
                   initial_sidebar_state="collapsed")

from theme import inject_css, header_band
import data as D
import views as V
import chatbot as C

inject_css()

team_df = D.load_team()
player_df = D.load_players()
all_seasons = D.seasons(team_df)


# ------------------------------------------------------------ chatbot
@st.dialog("Ask the data", width="large")
def chat_dialog(season):
    st.caption("Answers come from the loaded box-score data only. The assistant "
               "will say when something is not in the data.")
    client = C.get_client()
    if client is None:
        st.info("Set ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID for "
                "multi-workspace keys) in the environment or app secrets, then "
                "reboot the app.")
        return
    msgs = st.session_state.setdefault("messages", [])
    history = st.container(height=420, border=False)
    with history:
        for msg in msgs:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    prompt = st.chat_input("e.g. How does our clearance work compare to last season?")
    if not prompt:
        return
    msgs.append({"role": "user", "content": prompt})
    with history:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                reply = st.write_stream(C.stream_answer(
                    client, C.build_context("team", "player"), season, msgs))
            except Exception as exc:  # show API errors instead of crashing the app
                msgs.pop()  # keep failed turns out of the history sent next time
                if "anthropic-workspace-id" in str(exc):
                    st.error("This API key is not tied to one workspace. Set "
                             "ANTHROPIC_WORKSPACE_ID (starts with wrkspc_) in the "
                             "app secrets or environment, reboot the app, and try again.")
                else:
                    st.error(f"Sorry, the assistant hit an error: {exc}")
                return
    msgs.append({"role": "assistant", "content": reply})


# ------------------------------------------------------------- header
h1, h2, h3 = st.columns([7, 1.3, 1.1], vertical_alignment="center")
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
with h3:
    if st.button("💬 Ask the data", use_container_width=True, type="primary"):
        chat_dialog(season)

# --------------------------------------------------------------- body
V.render(team_df, player_df, season, baseline)
