"""The Coach View: the whole season on one 1440x900 screen.

Row 1: headline tiles (season value, change vs baseline, per game sparkline).
Row 2: game strip | where we win | quarters (points, or wins v losses).
Row 3: role leaders (incl. top goalkicker) | player form | what drives our margin.
Every chart has hover detail in place of axis clutter.
"""

import streamlit as st

import data as D
import charts as CH
from theme import COLORS, card_title, tiles_row, leaders_list, tape

# Chart heights come from layout.sizes() (sized to the browser window).

# Player stats offered on the form card: label -> column.
FORM_STATS = {
    "Disposals": "disposals",
    "Contested": "contested_poss",
    "Clearances": "clearances",
    "Tackles": "tackles",
    "Marks": "marks",
    "Goals+assists": "forward_threat",
}
# With AFL match centre stats loaded (marks makes way).
FORM_STATS_EXT = {
    "Disposals": "disposals",
    "Metres": "metres_gained",
    "Score inv.": "score_involvements",
    "Contested": "contested_poss",
    "Clearances": "clearances",
    "Pressure": "pressure_acts",
    "Tackles": "tackles",
    "Goals+assists": "forward_threat",
}

PLOT_CONFIG = {"displayModeBar": False}


def card(name, height="content"):
    """A white card. The key gives it a stable `st-key-card_<name>` class for the
    card CSS, which does not depend on Streamlit's internal element names."""
    return st.container(border=True, height=height, key=f"card_{name}")


def _plot(fig):
    st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)


def render(team_df, player_df, season, baseline, sz):
    """sz: pixel sizes from layout.sizes(); "mid"/"bot" are the chart heights of
    the middle and bottom rows, "form_rows" the players shown in player form."""
    MID_H, BOT_H = sz["mid"], sz["bot"]
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    form_stats = FORM_STATS_EXT if "pressure_acts" in pdf.columns else FORM_STATS

    tiles_row(D.tiles(team_df, season, baseline), baseline)

    # ---- middle row
    c1, c2, c3 = st.columns([2.2, 1.35, 1.15])
    with c1, card("strip"):
        card_title("Game strip", "who won each count",
                   keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"])])
        rows, z, hover, labels = D.game_strip(tdf)
        _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(), MID_H))
    with c2, card("wherewin"):
        # Win rate in games where each side won the count on that stat.
        card_title("Where we win", keys=[("Freo won it", COLORS["freo"]),
                                         ("Opp won it", COLORS["opp"])])
        _plot(CH.win_conditions_bars(D.win_conditions(tdf), MID_H))
    with c3, card("quarters"):
        t, s = st.columns([0.8, 1.2], vertical_alignment="center")
        with s:
            qview = st.segmented_control("Quarter view", ["Points", "W v L"],
                                         default="Points", key="qview",
                                         label_visibility="collapsed") or "Points"
        with t:
            card_title("Quarters")  # colour key sits inside the chart
        if qview == "Points":
            _plot(CH.quarter_bars(D.quarter_pattern(tdf), MID_H - 12))
        else:
            _plot(CH.running_margin_lines(D.running_margin(tdf), MID_H - 12))

    # ---- bottom row
    b1, b2, b3 = st.columns([1.05, 2.45, 1.2])
    # Same height as its neighbours; on very small windows the list scrolls
    # inside the card instead of pushing the page past the screen.
    with b1, card("leaders", height=max(BOT_H + 40, 200)):
        card_title("Role leaders", "most games led")
        leaders = D.role_leaders(pdf)
        gk = D.top_goalkickers(pdf, n=1)
        if len(gk):
            leaders.append({"role": "Top goalkicker", "player": gk.index[0],
                            "value": f"{int(gk['goals'].iloc[0])}",
                            "sub": f"goals in {int(gk['games'].iloc[0])} games"})
        leaders_list(leaders)
    with b2, card("form"):
        t, s = st.columns([2.6, 1], vertical_alignment="center")
        with t:
            card_title("Player form", "last 6 games vs own season avg",
                       keys=[("below", "#DDD0F7"), ("above", "#5B21B6")])
        with s:
            stat = st.selectbox("Form stat", list(form_stats), key="form_stat",
                                label_visibility="collapsed")
        stat = stat or "Disposals"
        vals, avgs, _ = D.form_matrix(pdf, form_stats.get(stat, "disposals"),
                                      n_players=sz["form_rows"])
        if len(vals):
            _plot(CH.form_heatmap(vals, avgs, stat, BOT_H - 38))
        else:
            st.caption("Not enough games yet.")
    with b3, card("drivers"):
        card_title("What drives our margin", "r, not cause")
        _plot(CH.drivers_bar(D.margin_drivers(tdf), BOT_H))


# ---- Match mode ------------------------------------------------------------
# Player grid columns in match mode: header label -> player column.
MATCH_STATS = [
    ("D", "disposals"), ("K", "kicks"), ("H", "handballs"), ("M", "marks"),
    ("CP", "contested_poss"), ("CLR", "clearances"), ("I50", "inside_50s"),
    ("T", "tackles"), ("MG", "metres_gained"), ("SI", "score_involvements"),
    ("PA", "pressure_acts"), ("R50", "rebound_50s"), ("G", "goals"), ("B", "behinds"),
    ("RP", "rating_points"),
]


def render_match(team_df, player_df, season, pos, sz):
    """One game on one screen, every number against the season average.

    Row 1: tiles for this game (change vs season average).
    Row 2: tale of the tape | game flow (running margin) | who led each role.
    Row 3: every Freo player, shaded against their own season average.
    """
    MID_H, BOT_H = sz["mid"], sz["bot"]
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    game = tdf.iloc[pos]

    tiles_row(D.match_tiles(team_df, season, pos), "Season avg")

    c1, c2, c3 = st.columns([1.5, 1.25, 1])
    with c1, card("tape", height=MID_H + 40):
        card_title("Tale of the tape", keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"]),
                                             ("season avg share", "#1F2937")])
        tape(D.tale_of_the_tape(tdf, pos))
    with c2, card("flow"):
        card_title("Game flow", keys=[("This game", COLORS["freo"]), ("Avg win", COLORS["win"]),
                                      ("Avg loss", COLORS["loss"])])
        flow, avg = D.game_flow(tdf, pos)
        _plot(CH.game_flow_lines(flow, avg, MID_H))
    with c3, card("gameleaders", height=MID_H + 40):
        card_title("Game leaders")
        leaders, goals = D.match_leaders(pdf, game)
        leaders_list(leaders)
        st.markdown(f'<div class="cv-lead"><div><div class="role">Goals</div>'
                    f'<div class="name" style="font-weight:500;font-size:.78rem">{goals}</div>'
                    f'</div></div>', unsafe_allow_html=True)

    with card("players", height=BOT_H + 40):
        card_title("Players this game", "shaded against each player's own season average",
                   keys=[("below", "#DDD0F7"), ("above", "#5B21B6")])
        stats = [(lbl, col) for lbl, col in MATCH_STATS if col in pdf.columns]
        vals, pct, _ = D.match_players(pdf, game, [c for _, c in stats])
        grid_h = max(BOT_H - 10, 18 * len(vals) + 40)  # scrolls inside the card if needed
        _plot(CH.match_player_grid(vals, pct, [lbl for lbl, _ in stats], grid_h))
