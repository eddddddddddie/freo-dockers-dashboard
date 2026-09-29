"""The six dashboard pages. Each renders its charts plus a table view."""

import pandas as pd
import streamlit as st

import data as D
import charts as CH
from theme import COLORS, card_title, hero, leader_list, insight_box

# Player stats offered on the Players page: label -> column.
PLAYER_STATS = [
    ("Disposals", "disposals"), ("Kicks", "kicks"), ("Handballs", "handballs"),
    ("Marks", "marks"), ("Contested possessions", "contested_poss"),
    ("Clearances", "clearances"), ("Tackles", "tackles"),
    ("Inside 50s", "inside_50s"), ("Rebound 50s", "rebound_50s"),
    ("One percenters", "one_percenters"), ("Goals", "goals"),
    ("Goal assists", "goal_assists"), ("Hitouts", "hitouts"),
]


def _table(tdf, cols, rename):
    view = tdf[cols].rename(columns=rename)
    st.dataframe(view, hide_index=True, width="stretch")


def _chart_with_table(fig, tdf, cols, rename, label="Show the numbers"):
    st.plotly_chart(fig, use_container_width=True)
    with st.expander(label):
        _table(tdf, cols, rename)


# ------------------------------------------------------ Season Overview
def render_overview(team_df, player_df, season, baseline):
    """Card-grid overview inspired by a performance-analysis dashboard."""
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)

    # Row 1: Top Scorers | Possession Mix + insight
    r1 = st.columns([1, 2])
    with r1[0]:
        with st.container(border=True):
            card_title("Top Scorers")
            gk = D.top_goalkickers(player_df, season, n=6)
            if len(gk):
                hero(f"{int(gk.iloc[0])}", f"goals · {gk.index[0]}")
                st.plotly_chart(CH.top_scorers_bar(gk), use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.caption("No goals recorded.")
    with r1[1]:
        with st.container(border=True):
            card_title("Possession Mix")
            mix = D.possession_mix(team_df, season)
            inner = st.columns([2, 1])
            with inner[0]:
                st.plotly_chart(
                    CH.possession_donut(mix["contested"], mix["uncontested"]),
                    use_container_width=True, config={"displayModeBar": False})
            with inner[1]:
                insight_box(
                    f"{mix['contested_pct']:.0f}%",
                    f"of Freo's possessions are contested. They won the contested "
                    f"count in {mix['won_games']} of {mix['games']} games this season.")

    # Row 2: Output vs Baseline | Season Trends
    r2 = st.columns([1, 2])
    with r2[0]:
        with st.container(border=True):
            title = "Output vs Baseline" if baseline is None else f"Output vs {baseline}"
            card_title(title)
            frame = D.comparison_frame(team_df, season, baseline).head(9)
            st.dataframe(frame, hide_index=True, width="stretch")
    with r2[1]:
        with st.container(border=True):
            card_title("Season Trends")
            labels = [m[0] for m in D.TREND_METRICS]
            pick = st.selectbox("Metric", labels, index=0, key="trend_metric",
                                label_visibility="collapsed")
            _, fcol, ocol = next(m for m in D.TREND_METRICS if m[0] == pick)
            st.plotly_chart(CH.trend_area(tdf, fcol, ocol, pick),
                            use_container_width=True, config={"displayModeBar": False})

    # Row 3: Volume vs Efficiency | Role Leaders
    r3 = st.columns([2, 1])
    with r3[0]:
        with st.container(border=True):
            card_title("Volume vs Efficiency")
            st.caption("Inside 50s against score, per game. Wins in green, losses in red. "
                       "We do not have shot locations, so this is the box-score view.")
            st.plotly_chart(
                CH.volume_efficiency_scatter(tdf, "freo_inside_50s", "freo_score",
                                             "Inside 50s", "Score"),
                use_container_width=True, config={"displayModeBar": False})
    with r3[1]:
        with st.container(border=True):
            card_title("Role Leaders")
            items = [(role, name, f"{games}<small> games</small>")
                     for role, name, games in D.season_role_leaders(pdf)]
            leader_list(items)


# ---------------------------------------------------------------- Home
def render_home(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    rec = D.record(tdf)
    st.subheader(f"{season} season record")

    c = st.columns(5)
    base_rec = D.record(D.team_season(team_df, baseline)) if baseline is not None else None
    c[0].metric("Record", f"{rec['wins']} - {rec['losses']}")
    c[1].metric("Win rate", f"{rec['win_pct']:.0f}%",
                _delta(rec["win_pct"], base_rec, "win_pct", "pp"))
    c[2].metric("Score for (avg)", f"{rec['score_for']:.1f}",
                _delta(rec["score_for"], base_rec, "score_for"))
    c[3].metric("Score against (avg)", f"{rec['score_against']:.1f}",
                _delta(rec["score_against"], base_rec, "score_against"), delta_color="inverse")
    c[4].metric("Margin (avg)", f"{rec['margin']:+.1f}",
                _delta(rec["margin"], base_rec, "margin"))

    st.markdown("##### Results")
    _results_strip(tdf)

    st.markdown("##### Current season vs baseline")
    if baseline is None:
        st.info("No earlier season is loaded, so there is nothing to compare "
                f"{season} against yet.")
    else:
        st.caption(f"Per-game averages, {season} compared with {baseline}. "
                   "Change is the percentage change on each metric.")
    frame = D.comparison_frame(team_df, season, baseline)
    st.dataframe(frame, hide_index=True, width="stretch")


def _delta(cur, base_rec, key, suffix=""):
    if base_rec is None:
        return None
    base = base_rec[key]
    if base is None:
        return None
    diff = cur - base
    if suffix == "pp":
        return f"{diff:+.0f} pp"
    return f"{diff:+.1f}"


def _results_strip(tdf):
    chips = []
    for _, g in tdf.iterrows():
        bg = COLORS["win"] if g["result"] == "W" else COLORS["loss"]
        chips.append(
            f'<div class="chip" style="background:{bg}">'
            f'<span class="rnd">{g["round"]} {g["result"]}</span>'
            f'<span class="opp">{g["opponent"]}</span>'
            f'<span class="mgn">{int(g["margin"]):+d}</span></div>'
        )
    st.markdown('<div class="results-strip">' + "".join(chips) + "</div>",
                unsafe_allow_html=True)


# --------------------------------------------------- Midfield & Contest
def render_midfield(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    st.subheader("Midfield and contest")
    st.caption("Fremantle vs opposition by round. Winning the contest usually "
               "sets up everything downstream.")

    _differential_insight(tdf, "clearances", "freo_clearances", "opp_clearances")

    st.markdown("##### Clearances")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_clearances", "opp_clearances", "Clearances"),
        tdf, ["round", "opponent", "freo_clearances", "opp_clearances"],
        {"round": "Round", "opponent": "Opponent",
         "freo_clearances": "Freo", "opp_clearances": "Opp"})

    st.markdown("##### Contested possessions")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_contested_poss", "opp_contested_poss",
                            "Contested possessions"),
        tdf, ["round", "opponent", "freo_contested_poss", "opp_contested_poss"],
        {"round": "Round", "opponent": "Opponent",
         "freo_contested_poss": "Freo", "opp_contested_poss": "Opp"})

    st.markdown("##### Inside 50s")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_inside_50s", "opp_inside_50s", "Inside 50s"),
        tdf, ["round", "opponent", "freo_inside_50s", "opp_inside_50s"],
        {"round": "Round", "opponent": "Opponent",
         "freo_inside_50s": "Freo", "opp_inside_50s": "Opp"})


def _differential_insight(tdf, name, fcol, ocol):
    d = D.differential(tdf, fcol, ocol)
    if d["ahead_winrate"] is None:
        return
    bw = f"{d['behind_winrate']:.0f}%" if d["behind_winrate"] is not None else "n/a"
    st.markdown(
        f'<div class="insight">When Freo win the <b>{name}</b> count they win '
        f'<b>{d["ahead_winrate"]:.0f}%</b> of the time ({d["ahead_games"]} games). '
        f'When they lose it, their win rate is {bw} ({d["behind_games"]} games).</div>',
        unsafe_allow_html=True)


# ------------------------------------------------ Ball Movement & Scoring
def render_ball_movement(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    st.subheader("Ball movement and scoring")

    acc = tdf["freo_accuracy"].mean()
    goals = int(tdf["freo_goals"].sum())
    behinds = int(tdf["freo_behinds"].sum())
    c = st.columns(3)
    c[0].metric("Goal accuracy (season)", f"{acc:.1f}%")
    c[1].metric("Goals", f"{goals}")
    c[2].metric("Behinds", f"{behinds}")
    st.caption("Accuracy uses team totals, which include rushed behinds.")

    st.markdown("##### Disposals")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_disposals", "opp_disposals", "Disposals"),
        tdf, ["round", "opponent", "freo_disposals", "opp_disposals"],
        {"round": "Round", "opponent": "Opponent",
         "freo_disposals": "Freo", "opp_disposals": "Opp"})

    st.markdown("##### Marks")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_marks", "opp_marks", "Marks"),
        tdf, ["round", "opponent", "freo_marks", "opp_marks"],
        {"round": "Round", "opponent": "Opponent",
         "freo_marks": "Freo", "opp_marks": "Opp"})

    st.markdown("##### Goal accuracy (goals and behinds per game)")
    _chart_with_table(
        CH.goals_behinds_bar(tdf),
        tdf, ["round", "opponent", "freo_goals", "freo_behinds", "freo_accuracy"],
        {"round": "Round", "opponent": "Opponent", "freo_goals": "Goals",
         "freo_behinds": "Behinds", "freo_accuracy": "Accuracy %"})

    st.markdown("##### Goal assists")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_goal_assists", "opp_goal_assists", "Goal assists"),
        tdf, ["round", "opponent", "freo_goal_assists", "opp_goal_assists"],
        {"round": "Round", "opponent": "Opponent",
         "freo_goal_assists": "Freo", "opp_goal_assists": "Opp"})


# ----------------------------------------------------------- Defence
def render_defence(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    st.subheader("Defence")
    st.caption("Rebounding, spoiling, and keeping the opposition out of their "
               "forward half. For the opposition inside 50s line, lower is better.")

    st.markdown("##### Rebound 50s")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_rebound_50s", "opp_rebound_50s", "Rebound 50s"),
        tdf, ["round", "opponent", "freo_rebound_50s", "opp_rebound_50s"],
        {"round": "Round", "opponent": "Opponent",
         "freo_rebound_50s": "Freo", "opp_rebound_50s": "Opp"})

    st.markdown("##### One percenters")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_one_percenters", "opp_one_percenters",
                            "One percenters"),
        tdf, ["round", "opponent", "freo_one_percenters", "opp_one_percenters"],
        {"round": "Round", "opponent": "Opponent",
         "freo_one_percenters": "Freo", "opp_one_percenters": "Opp"})

    st.markdown("##### Inside 50s conceded vs generated")
    _chart_with_table(
        CH.freo_vs_opp_line(tdf, "freo_inside_50s", "opp_inside_50s", "Inside 50s"),
        tdf, ["round", "opponent", "freo_inside_50s", "opp_inside_50s"],
        {"round": "Round", "opponent": "Opponent",
         "freo_inside_50s": "Freo", "opp_inside_50s": "Opp (conceded)"})

    st.markdown("##### Opposition score by round")
    _chart_with_table(
        CH.result_score_bar(tdf),
        tdf, ["round", "opponent", "result", "freo_score", "opp_score"],
        {"round": "Round", "opponent": "Opponent", "result": "Result",
         "freo_score": "Freo", "opp_score": "Opp"})


# ----------------------------------------------------------- Players
def render_players(team_df, player_df, season, baseline):
    st.subheader("Players")
    pdf = D.players_season(player_df, season)
    names = sorted(pdf["player"].unique())
    if not names:
        st.info("No player data for this season.")
        return

    col1, col2 = st.columns([2, 2])
    default = names.index("Caleb Serong") if "Caleb Serong" in names else 0
    player = col1.selectbox("Player", names, index=default)
    stat_label = col2.selectbox("Stat", [s[0] for s in PLAYER_STATS], index=0)
    stat_col = dict(PLAYER_STATS)[stat_label]

    p = pdf[pdf["player"] == player].sort_values("game_dt").reset_index(drop=True)
    season_avg = p[stat_col].mean()
    last5 = p.tail(5)
    last5_avg = last5[stat_col].mean()

    m = st.columns(3)
    m[0].metric("Games", f"{len(p)}")
    m[1].metric(f"{stat_label} (season avg)", f"{season_avg:.1f}")
    m[2].metric(f"{stat_label} (last 5)", f"{last5_avg:.1f}",
                f"{last5_avg - season_avg:+.1f} vs season")

    _chart_with_table(
        CH.player_form(p, stat_col, stat_label, season_avg, last5_avg),
        p, ["round", "opponent", "result", stat_col],
        {"round": "Round", "opponent": "Opponent", "result": "Result",
         stat_col: stat_label})

    # Season comparison if the player appears in more than one season.
    all_seasons = D.seasons(player_df)
    player_all = player_df[player_df["player"] == player]
    played = [s for s in all_seasons if s in player_all["season"].values]
    if len(played) > 1:
        st.markdown(f"##### {player}: season comparison (per-game averages)")
        rows = []
        for label, col in PLAYER_STATS:
            row = {"Stat": label}
            for s in played:
                sub = player_all[player_all["season"] == s]
                row[str(s)] = round(sub[col].mean(), 1)
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# -------------------------------------------------------- Role leaders
def render_roles(team_df, player_df, season, baseline):
    st.subheader("Role leaders (per game)")
    st.caption("Who led each role in each game, and who leads most often across "
               "the season. Ball Winner is contested possessions, Forward Threat "
               "is goals plus goal assists.")
    pdf = D.players_season(player_df, season)
    if pdf.empty:
        st.info("No player data for this season.")
        return

    role_labels = [r[0] for r in D.ROLES]
    role = st.selectbox("Role leaderboard", role_labels, index=0)
    role_col = dict(D.ROLES)[role]
    counts = D.role_leader_counts(pdf, role_col)
    if len(counts):
        st.plotly_chart(CH.leader_counts_bar(counts), use_container_width=True)
    else:
        st.info("No leaders recorded for this role.")

    st.markdown("##### Game-by-game role leaders")
    table = D.role_leaders_table(pdf)
    st.dataframe(table, hide_index=True, width="stretch")
