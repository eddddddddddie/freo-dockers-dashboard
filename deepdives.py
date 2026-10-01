"""Deep dives: full-size pop-ups opened from the header, so the Coach View
itself stays on one screen.

- Player map: every player's per game averages on two chosen stats.
- Year on year: per game averages, the last two seasons, for the top players.
- Opponents: every game against every club, both seasons, with a button that
  hands a question about that club to Wharf-ai.
"""

import html

import streamlit as st

import data as D
import charts as CH
import nav
from theme import COLORS, record_text, result_colour

CHART_H = 520

# Stats offered in the deep dives: label -> player column (skipped if missing).
STATS = {
    "Disposals": "disposals", "Contested poss": "contested_poss",
    "Uncontested poss": "uncontested_poss", "Metres gained": "metres_gained",
    "Score involvements": "score_involvements", "Pressure acts": "pressure_acts",
    "Tackles": "tackles", "Clearances": "clearances", "Inside 50s": "inside_50s",
    "Rebound 50s": "rebound_50s", "Intercepts": "intercepts", "Marks": "marks",
    "One percenters": "one_percenters", "Goals": "goals",
}
PLOT_CONFIG = {"displayModeBar": False}


def _stats(df):
    return {k: v for k, v in STATS.items() if v in df.columns}


@st.dialog("Player map", width="large")
def player_map(player_df, season):
    pdf = D.players_season(player_df, season)
    stats = _stats(pdf)
    labels = list(stats)
    c1, c2, c3 = st.columns([1, 1, 1.6], vertical_alignment="bottom")
    x = c1.selectbox("Across", labels, index=labels.index("Contested poss"))
    y_default = "Metres gained" if "Metres gained" in stats else "Uncontested poss"
    y = c2.selectbox("Up", labels, index=labels.index(y_default))
    c3.caption(f"{season}, players with 5+ games. Dot size is time on ground. "
               "Dotted lines are the team median. Click a dot for the player's profile.")
    size_col = "time_on_ground_pct" if "time_on_ground_pct" in pdf.columns else "pct_played"
    pa = D.player_averages(pdf, [stats[x], stats[y], size_col])
    ev = st.plotly_chart(CH.player_map(pa, stats[x], stats[y], x, y, size_col, CHART_H),
                         width="stretch", config=PLOT_CONFIG, on_select="rerun",
                         selection_mode="points", key="pmap_click")
    point = nav.clicked(ev)
    if point is not None and point.get("point_index") is not None:
        nav.go(view="Player", season=season, player=pa.index[point["point_index"]])


@st.dialog("Year on year", width="large")
def year_on_year(player_df, all_seasons):
    if len(all_seasons) < 2:
        st.info("Needs two seasons of data.")
        return
    s0, s1 = all_seasons[-2], all_seasons[-1]
    stats = _stats(D.players_season(player_df, s0))  # stat must exist in both seasons
    labels = list(stats)
    c1, c2 = st.columns([1, 2.6], vertical_alignment="bottom")
    stat = c1.selectbox("Stat", labels, index=0)
    c2.caption(f"Per game average, {s0} to {s1}, for the 15 players highest in {s1} "
               "with 8+ games in both seasons. Purple went up, grey went down. "
               "Click a line for the player's profile.")
    yoy = D.year_on_year(player_df, s0, s1, stats[stat])
    if not len(yoy):
        st.info("No players with enough games in both seasons.")
        return
    ev = st.plotly_chart(CH.slope_chart(yoy, s0, s1, stat, CHART_H),
                         width="stretch", config=PLOT_CONFIG, on_select="rerun",
                         selection_mode="points", key="yoy_click")
    point = nav.clicked(ev)
    if point is not None and point.get("curve_number") is not None:
        nav.go(view="Player", season=s1, player=yoy.index[point["curve_number"]])


def _chip(g):
    color = result_colour(g["result"])
    tip = (f"{g['season']} {g['round']} ({g['type']}) at {g['venue']}: "
           f"Freo {g['freo_score']} to {g['opp_score']}")
    return (f'<span class="op-chip" style="background:{color}" title="{html.escape(tip)}">'
            f'{g["round"]} {g["margin"]:+d}</span>')


@st.dialog("Opponents", width="large")
def opponents(team_df, all_seasons):
    grid = D.opponent_grid(team_df)
    head = "".join(f"<th>{s}</th>" for s in all_seasons)
    rows = ""
    for r in grid:
        cells = "".join(
            "<td>" + "".join(_chip(g) for g in r["games"].get(s, [])) + "</td>"
            for s in all_seasons)
        rows += (f'<tr><td class="op-name">{html.escape(r["opponent"])}</td>{cells}'
                 f'<td class="op-num">{record_text(r["wins"], r["losses"], r["draws"])}</td>'
                 f'<td class="op-num">{r["avg_margin"]:+.1f}</td></tr>')
    st.caption("Every game against each club, toughest first (lowest average margin). "
               "Chips show round and margin; hover for the score and venue.")
    st.markdown(
        f'<div class="op-wrap"><table class="op-grid"><thead><tr><th>Opponent</th>{head}'
        f'<th>Record</th><th>Avg margin</th></tr></thead><tbody>{rows}</tbody></table></div>',
        unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1.3], vertical_alignment="bottom")
    opp = c1.selectbox("Club", [r["opponent"] for r in grid])
    if D.load_league() is not None and c2.button(f"Open the scout report", type="primary"):
        nav.go(view="Scout", season=all_seasons[-1], opp=opp)
    if c3.button(f"Ask Wharf-ai about {opp}"):
        st.session_state["pending_prompt"] = (
            f"How have we gone against {opp} across {all_seasons[0]} and "
            f"{all_seasons[-1]}, and what decided those games?")
        st.rerun()


@st.dialog("Quarter-time check", width="large")
def quarter_time(team_df, all_seasons):
    """Enter the margin at a break; see how Freo have gone from similar positions.

    Only quarter scores are in the data (AFL Tables has no quarter-by-quarter
    stats), so positions are matched on the margin alone."""
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.2], vertical_alignment="bottom")
    brk = c1.selectbox("Break", list(D.BREAKS), index=1)
    margin = c2.number_input("Freo margin", value=0, step=1,
                             help="Freo score minus opposition score at the break")
    window = c3.number_input("Within ± points", value=6, min_value=0, max_value=60, step=1)
    scope = c4.selectbox("Games", ["Both seasons"] + [str(s) for s in reversed(all_seasons)])
    game_type = st.radio("Venue", ["Any", "Home", "Away", "Final"], horizontal=True,
                         label_visibility="collapsed")
    seasons = None if scope == "Both seasons" else [int(scope)]
    gt = None if game_type == "Any" else game_type
    games, sm = D.similar_positions(team_df, brk, int(margin), int(window), seasons, gt)
    col = sm["col"]

    left, right = st.columns([1, 1.6])
    with left:
        if sm["games"]:
            st.markdown(
                f'<div class="qt-big">{record_text(sm["wins"], sm["losses"], sm["draws"])}</div>'
                f'<div class="qt-sub">from {sm["games"]} games within ±{int(window)} of '
                f'{int(margin):+d} at {brk.lower()} ({sm["win_pct"]:.0f}% won, of '
                f'{sm["pool"]} games checked)</div>'
                f'<div class="qt-line">Average final margin <b>{sm["avg_final"]:+.1f}</b></div>'
                f'<div class="qt-line">Net scoring from the break to the siren '
                f'<b>{sm["avg_after"]:+.1f}</b></div>',
                unsafe_allow_html=True)
        else:
            st.info("No games from a position like that. Widen the ± window.")
        st.caption("Matched on the score only: quarter-by-quarter stats (inside 50s, "
                   "clearances) are not in the data. A small sample says little; check the count.")
    with right:
        bm = D.break_margins(team_df)
        if seasons:
            bm = bm[bm["season"].isin(seasons)]
        if gt:
            bm = bm[bm["type"] == gt]
        st.plotly_chart(CH.break_scatter(bm, col, int(margin), int(window), brk, 300),
                        width="stretch", config=PLOT_CONFIG)
    if sm["games"]:
        show = games[["season", "round", "type", "opponent", col, "margin", "result"]].rename(
            columns={col: f"At {brk.lower()}", "margin": "Final", "result": "Result",
                     "season": "Season", "round": "Round", "type": "Type",
                     "opponent": "Opponent"})
        st.dataframe(show, hide_index=True, width="stretch", height=180)


@st.dialog("Wharf-ai usage", width="large")
def usage_log():
    """Questions asked, tools used, tokens and estimated cost."""
    import pandas as pd
    import usage as U
    s = U.summary()
    c = st.columns(4)
    c[0].metric("Questions today", f"{s['today']} / {s['cap']}")
    c[1].metric("Cost today (US$)", f"{s['today_cost']:.2f}")
    c[2].metric("Questions, last 7 days", s["week"])
    c[3].metric("Cost, last 7 days (US$)", f"{s['week_cost']:.2f}")
    rows = U.recent()
    if not rows:
        st.info("No questions logged yet.")
        return
    df = pd.DataFrame(rows)
    for col in ("user_email", "answer", "unbacked"):
        df[col] = df.get(col, pd.Series([None] * len(df))).fillna("")
    df["rating"] = df.get("rating", pd.Series([None] * len(df))).map({1: "👍", 0: "👎"}).fillna("")
    df["unbacked"] = df["unbacked"].str.replace(r'[\[\]"]', "", regex=True)
    df["tools"] = df["tools"].str.replace(r'[\[\]"]', "", regex=True)
    df["ok"] = df["ok"].map({1: "yes", 0: "failed"})
    rated = (df["rating"] != "").sum()
    down = (df["rating"] == "👎").sum()
    flagged = (df["unbacked"] != "").sum()
    st.caption(f"Rated answers: {rated} ({down} thumbs down) · answers with a number not matched "
               f"to a calculation: {flagged}")
    view = df[["ts", "user_email", "rating", "question", "unbacked", "tools", "steps",
               "input_tokens", "output_tokens", "cache_read", "cost_usd", "ok"]]
    st.dataframe(view.rename(columns={
        "ts": "When", "user_email": "Who", "rating": "Rated", "question": "Question",
        "unbacked": "Not matched", "tools": "Tools", "steps": "Steps", "input_tokens": "Input",
        "output_tokens": "Output", "cache_read": "Cache read", "cost_usd": "US$", "ok": "OK"}),
        hide_index=True, width="stretch", height=340)
    # With the answers, for review (evals/review_feedback.py turns thumbs down
    # into candidate test cases). Download before a redeploy wipes the log.
    st.download_button("Download the log with answers (CSV)",
                       df.drop(columns=["sid"], errors="ignore").to_csv(index=False),
                       file_name=f"wharf_usage_{U.today()}.csv", mime="text/csv")
    st.caption("Costs are estimates at claude-sonnet-5-5 list prices. The log is stored on the "
               "app's own disk: on Streamlit Cloud it starts again after a restart or redeploy, "
               "so download it first if you want to keep the ratings.")
