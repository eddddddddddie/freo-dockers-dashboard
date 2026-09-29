"""The Coach View: the whole season on one 1440x900 screen.

Row 1: headline tiles (season value, change vs baseline, per game sparkline).
Row 2: margin by round | where we win | quarter pattern.
Row 3: role leaders | player form | top goalkickers.
Every chart has hover detail in place of axis clutter.
"""

import streamlit as st

import data as D
import charts as CH
from theme import card_title, tiles_row, leaders_list

MID_H = 238   # chart height in the middle row (px)
BOT_H = 262   # chart height in the bottom row (px)

# Player stats offered on the form card: label -> column.
FORM_STATS = {
    "Disposals": "disposals",
    "Contested": "contested_poss",
    "Clearances": "clearances",
    "Tackles": "tackles",
    "Marks": "marks",
    "Goals+assists": "forward_threat",
}

PLOT_CONFIG = {"displayModeBar": False}


def _plot(fig):
    st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)


def render(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)

    tiles_row(D.tiles(team_df, season, baseline), baseline)

    # ---- middle row
    c1, c2, c3 = st.columns([2.2, 1.35, 1.15])
    with c1, st.container(border=True):
        card_title("Margin by game", f"green win, red loss · avg {tdf['margin'].mean():+.1f}" if len(tdf) else "")
        _plot(CH.margin_bars(tdf, MID_H))
    with c2, st.container(border=True):
        card_title("Where we win", "win rate when each side wins the count")
        _plot(CH.win_conditions_bars(D.win_conditions(tdf), MID_H))
    with c3, st.container(border=True):
        card_title("Quarter pattern", "avg points, Freo margin on top")
        _plot(CH.quarter_bars(D.quarter_pattern(tdf), MID_H))

    # ---- bottom row
    b1, b2, b3 = st.columns([1.05, 2.45, 1.2])
    with b1, st.container(border=True):
        card_title("Role leaders", "most games led")
        leaders_list(D.role_leaders(pdf))
    with b2, st.container(border=True):
        t, s = st.columns([1, 2.2], vertical_alignment="center")
        with t:
            card_title("Player form", "last 6 games vs own avg")
        with s:
            stat = st.segmented_control("Form stat", list(FORM_STATS), default="Disposals",
                                        key="form_stat", label_visibility="collapsed")
        stat = stat or "Disposals"
        vals, avgs, _ = D.form_matrix(pdf, FORM_STATS[stat])
        if len(vals):
            _plot(CH.form_heatmap(vals, avgs, stat, BOT_H - 38))
        else:
            st.caption("Not enough games yet.")
    with b3, st.container(border=True):
        card_title("Goalkickers", "season total")
        _plot(CH.goalkickers_bar(D.top_goalkickers(pdf, n=8), BOT_H))
