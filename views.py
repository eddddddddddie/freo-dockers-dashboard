"""The Coach View's four views, each one screen with no page scroll.

Season: headline tiles | game strip, where we win, quarters | role leaders,
        player form, what drives our margin.
Match:  one game against the season average.
Player: one player's season.
Scout:  any club's season against the league and Freo.

Every card has a computed one-line takeaway under its title (takeaways.py).
Clicking a game in the game strip opens it in Match; clicking a player in a
player grid opens their profile (nav.go).
"""

import streamlit as st

import data as D
import charts as CH
import nav
import takeaways as T
from theme import (COLORS, RAMP, club_colours, card_title, tiles_row, leaders_list, tape, scout_tiles_row,
                   h2h_table)

TK = 18  # height of a card's takeaway line (px); charts give it up

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


def _plot(fig, key=None):
    """Draw a chart. With a key, clicks on its points come back as an event."""
    if key is None:
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        return None
    return st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG,
                           on_select="rerun", selection_mode="points", key=key)


def _open_game(event, labels, season):
    point = nav.clicked(event)
    if point and point.get("x") in labels:
        game_round = labels[labels.index(point["x"])].split(" ")[0]
        nav.go(view="Match", season=season, game=game_round)


def _open_player(event, season, strip_avg=False):
    point = nav.clicked(event)
    if point and point.get("y"):
        name = str(point["y"]).split("  (")[0] if strip_avg else str(point["y"])
        nav.go(view="Player", season=season, player=name)


def render(team_df, player_df, season, baseline, sz):
    """sz: pixel sizes from layout.sizes(); "mid"/"bot" are the chart heights of
    the middle and bottom rows, "form_rows" the players shown in player form."""
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    form_stats = FORM_STATS_EXT if "pressure_acts" in pdf.columns else FORM_STATS

    tiles_row(D.tiles(team_df, season, baseline), baseline)

    # ---- middle row
    c1, c2, c3 = st.columns([2.2, 1.35, 1.15])
    with c1, card("strip"):
        card_title("Game strip", "click a game to open it",
                   keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"])],
                   takeaway=T.strip(tdf))
        rows, z, hover, labels = D.game_strip(tdf)
        ev = _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(), MID_H),
                   key=f"strip_{season}")
        _open_game(ev, labels, season)
    with c2, card("wherewin"):
        wc = D.win_conditions(tdf)
        card_title("Where we win", keys=[("Freo won it", COLORS["freo"]),
                                         ("Opp won it", COLORS["opp"])],
                   takeaway=T.where_we_win(wc))
        _plot(CH.win_conditions_bars(wc, MID_H))
    with c3, card("quarters"):
        t, s = st.columns([0.8, 1.2], vertical_alignment="center")
        with s:
            qview = st.segmented_control("Quarter view", ["Points", "W v L"],
                                         default="Points", key="qview",
                                         label_visibility="collapsed") or "Points"
        qp, rm = D.quarter_pattern(tdf), D.running_margin(tdf)
        with t:
            card_title("Quarters")  # colour key sits inside the chart
        st.markdown(f'<div class="card-take">{T.quarters(qp) if qview == "Points" else T.running(rm)}'
                    '</div>', unsafe_allow_html=True)
        if qview == "Points":
            _plot(CH.quarter_bars(qp, MID_H - 12))
        else:
            _plot(CH.running_margin_lines(rm, MID_H - 12))

    # ---- bottom row
    b1, b2, b3 = st.columns([1.05, 2.45, 1.2])
    # Same height as its neighbours; on very small windows the list scrolls
    # inside the card instead of pushing the page past the screen.
    with b1, card("leaders", height=max(BOT_H + 40 + TK, 200)):
        leaders = D.role_leaders(pdf)
        card_title("Role leaders", "most games led", takeaway=T.leaders(leaders))
        gk = D.top_goalkickers(pdf, n=1)
        if len(gk):
            leaders.append({"role": "Top goalkicker", "player": gk.index[0],
                            "value": f"{int(gk['goals'].iloc[0])}",
                            "sub": f"goals in {int(gk['games'].iloc[0])} games"})
        leaders_list(leaders)
    with b2, card("form"):
        stat = st.session_state.get("form_stat") or "Disposals"
        vals, avgs, _ = D.form_matrix(pdf, form_stats.get(stat, "disposals"),
                                      n_players=sz["form_rows"])
        t, s = st.columns([2.6, 1], vertical_alignment="center")
        with t:
            card_title("Player form", "last 6 games vs own season avg · click a player",
                       keys=[("below", RAMP[0]), ("above", RAMP[-1])],
                       takeaway=T.form(vals, avgs) if len(vals) else "")
        with s:
            st.selectbox("Form stat", list(form_stats), key="form_stat",
                         label_visibility="collapsed")
        if len(vals):
            ev = _plot(CH.form_heatmap(vals, avgs, stat, BOT_H - 38), key=f"form_{season}_{stat}")
            _open_player(ev, season, strip_avg=True)
        else:
            st.caption("Not enough games yet.")
    with b3, card("drivers"):
        dr = D.margin_drivers(tdf)
        card_title("What drives our margin", "r, not cause", takeaway=T.drivers(dr))
        _plot(CH.drivers_bar(dr, BOT_H))


# ---- Match mode ------------------------------------------------------------
# Player grid columns in match mode: header label -> player column.
MATCH_STATS = [
    ("D", "disposals"), ("K", "kicks"), ("H", "handballs"), ("M", "marks"),
    ("CP", "contested_poss"), ("CLR", "clearances"), ("I50", "inside_50s"),
    ("T", "tackles"), ("MG", "metres_gained"), ("SI", "score_involvements"),
    ("PA", "pressure_acts"), ("R50", "rebound_50s"), ("G", "goals"), ("B", "behinds"),
    ("RP", "rating_points"),
]
BREAK_NAMES = {"Q1": "quarter time", "Q2": "half time", "Q3": "three quarter time",
               "Q4": "the siren"}


def render_match(team_df, player_df, season, pos, sz):
    """One game on one screen, every number against the season average.

    Row 1: tiles for this game (change vs season average).
    Row 2: tale of the tape | game flow (running margin) | who led each role.
    Row 3: every Freo player, shaded against their own season average.
    """
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    game = tdf.iloc[pos]

    tiles_row(D.match_tiles(team_df, season, pos), "Season avg")

    c1, c2, c3 = st.columns([1.5, 1.25, 1])
    with c1, card("tape", height=MID_H + 40 + TK):
        rows = D.tale_of_the_tape(tdf, pos)
        card_title("Tale of the tape", keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"]),
                                             ("season avg share", COLORS["ink"])],
                   takeaway=T.tape(rows))
        tape(rows)
    with c2, card("flow"):
        flow, avg = D.game_flow(tdf, pos)
        take = T.flow(flow.rename(index=BREAK_NAMES), game["result"], int(game["margin"]))
        card_title("Game flow", keys=[("This game", COLORS["freo"]), ("Avg win", COLORS["win"]),
                                      ("Avg loss", COLORS["loss"])], takeaway=take)
        _plot(CH.game_flow_lines(flow, avg, MID_H))
    with c3, card("gameleaders", height=MID_H + 40 + TK):
        leaders, goals = D.match_leaders(pdf, game)
        card_title("Game leaders", takeaway=T.match_leaders(goals))
        leaders_list(leaders)

    with card("players", height=BOT_H + 40 + TK):
        stats = [(lbl, col) for lbl, col in MATCH_STATS if col in pdf.columns]
        vals, pct, _ = D.match_players(pdf, game, [c for _, c in stats])
        card_title("Players this game", "shaded against each player's own season average · "
                   "click a player", keys=[("below", RAMP[0]), ("above", RAMP[-1])],
                   takeaway=T.match_players(vals))
        grid_h = max(BOT_H - 10, 18 * len(vals) + 40)  # scrolls inside the card if needed
        ev = _plot(CH.match_player_grid(vals, pct, [lbl for lbl, _ in stats], grid_h),
                   key=f"mplayers_{season}_{pos}")
        _open_player(ev, season)


# ---- Player profile ---------------------------------------------------------
PLAYER_TREND_STATS = {
    "Disposals": "disposals", "Contested poss": "contested_poss", "Clearances": "clearances",
    "Metres gained": "metres_gained", "Score involvements": "score_involvements",
    "Pressure acts": "pressure_acts", "Tackles": "tackles", "Marks": "marks",
    "Goals": "goals", "Rating points": "rating_points",
}
LOG_STATS = [("D", "disposals"), ("CP", "contested_poss"), ("CLR", "clearances"),
             ("I50", "inside_50s"), ("MG", "metres_gained"), ("SI", "score_involvements"),
             ("T", "tackles"), ("PA", "pressure_acts"), ("G", "goals"), ("RP", "rating_points"),
             ("TOG", "time_on_ground_pct")]


def render_player(player_df, season, baseline, player, sz):
    """One player's season on one screen.

    Row 1: per game averages with squad rank and change on last season.
    Row 2: game by game trend (pick a stat) | squad rank on each stat.
    Row 3: every game this season, shaded against the player's own average.
    """
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    pdf = D.players_season(player_df, season)
    me = pdf[pdf["player"] == player].sort_values("game_dt")
    trend_stats = {k: v for k, v in PLAYER_TREND_STATS.items() if v in pdf.columns}

    tiles_row(D.player_tiles(player_df, player, season, baseline), baseline,
              rank_label="squad rank")

    c1, c2 = st.columns([1.9, 1.1])
    with c1, card("ptrend"):
        label = st.session_state.get("ptrend_stat") or "Disposals"
        col = trend_stats.get(label, "disposals")
        t, s = st.columns([2.4, 1], vertical_alignment="center")
        with t:
            card_title("Game by game", "dots green win, red loss",
                       takeaway=T.player_trend(me, col, label))
        with s:
            st.selectbox("Trend stat", list(trend_stats), key="ptrend_stat",
                         label_visibility="collapsed")
        _plot(CH.player_trend(me, col, label, MID_H - 10))
    with c2, card("pranks"):
        pr = D.player_squad_ranks(pdf, player)
        card_title("Squad rank", f"per game, of players with {D.MIN_GAMES}+ games",
                   takeaway=T.player_ranks(pr))
        if len(pr):
            _plot(CH.squad_rank_bars(pr, MID_H))
        else:
            st.caption(f"Needs {D.MIN_GAMES} games for a squad rank.")

    with card("plog", height=BOT_H + 40 + TK):
        log = D.player_log(pdf, player)
        stats = [(l, c) for l, c in LOG_STATS if c in log.columns]
        card_title("Every game", "shaded against the player's own season average",
                   keys=[("below", RAMP[0]), ("above", RAMP[-1])],
                   takeaway=T.player_best(log, "disposals", "Disposals"))
        if len(log):
            vals = log.set_index(log["round"] + " v " + log["opponent"].map(D.abbr))[
                [c for _, c in stats]]
            avgs = log[[c for _, c in stats]].mean()
            pct = vals / avgs.clip(lower=0.1) * 100
            grid_h = max(BOT_H - 10, 18 * len(vals) + 40)
            _plot(CH.match_player_grid(vals, pct, [l for l, _ in stats], grid_h))


# ---- Opponent scout report ----------------------------------------------------
def render_scout(team_df, lg, season, opp, sz):
    """One club's season on one screen, set against the league and Freo.

    Row 1: their key numbers with league rank and Freo's figure.
    Row 2: style vs league (rank on each stat) | how they win | their quarters.
    Row 3: their recent form | every Freo game against them.
    """
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    club = club_colours(opp)                 # the club's own colours
    tint, grey = club["chart"], club["vs"]
    scout_tiles_row(D.scout_tiles(lg, opp, season), chip=club["band"])

    c1, c2, c3 = st.columns([1.45, 1.35, 1.2])
    with c1, card("style"):
        avg, ranks = D.team_ranks(lg, season)
        card_title("Style vs league", "rank of 18 on each stat", takeaway=T.style(ranks, opp))
        _plot(CH.rank_dumbbell(avg, ranks, opp, D.SCOUT_STATS, MID_H, team_color=tint))
    with c2, card("howtheywin"):
        short = D.abbr(opp)
        wc = D.scout_win_conditions(lg, opp, season)
        card_title("How they win", keys=[(f"{short} won it", tint),
                                         ("Their opponent did", grey)],
                   takeaway=T.where_we_win(wc))
        _plot(CH.win_conditions_bars(wc, MID_H, names=(f"{short} won it", "Their opponent won it"),
                                     colors=(tint, grey)))
    with c3, card("theirquarters"):
        qp = D.scout_quarters(lg, opp, season)
        card_title("Their quarters", "avg points", takeaway=T.quarters(qp))
        _plot(CH.quarter_bars(qp, MID_H - 12, names=(opp, "Opponents"), colors=(tint, grey)))

    b1, b2 = st.columns([1.55, 1.45])
    games = lg[(lg["season"] == season) & (lg["team"] == opp)].tail(14)
    with b1, card("theirform"):
        card_title("Their form", f"last {len(games)} games, green win, red loss",
                   takeaway=T.scout_form(games))
        _plot(CH.form_bars(games, BOT_H))
    with b2, card("h2h", height=BOT_H + 40 + TK):
        rows = D.head_to_head(team_df, opp)
        card_title("Against Fremantle", "every game, both seasons", takeaway=T.h2h(rows))
        if len(rows):
            h2h_table(rows)
        else:
            st.caption("No games against Fremantle in the data.")
