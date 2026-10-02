"""The Coach View's four views, each one screen with no page scroll.

Season: headline tiles | game strip, where we win, quarters | role leaders,
        player form, what drives our margin.
Match:  one game against the season average.
Player: one player's season.
Scout:  any club's season against the league and Freo.
Each picker also has a page across all of its options: Player -> Whole squad
(player map, year on year), Scout -> All clubs (every game against every
club), Match -> Quarter-time check (how Freo have gone from a margin at a break).

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
                   h2h_table, compare_tiles_row, compare_table, opponents_table, record_text,
                   leaders_pair)

TK = 18  # height of a card's takeaway line (px); charts give it up
ROW_GAIN = 15  # Match and Player rows run 15px shorter than Season's; their bottom row takes it

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


# Set by the app from layout.mode: "desktop" (one screen), "split" and "stack"
# (tablets: the page scrolls, cards two to a row) or "phone" (one column).
LAYOUT = "desktop"
PHONE = False
GRID = False     # the tablet layouts' two-to-a-row grid


def set_layout(mode):
    global LAYOUT, PHONE, GRID
    LAYOUT, PHONE, GRID = mode, mode == "phone", mode in ("stack", "split")


def _h(height):
    """A card's fixed height on the one-screen desktop; when the page scrolls,
    cards grow with their content."""
    return height if LAYOUT == "desktop" else "content"


def arrange(desktop, grid, phone):
    """Draw a view's cards (functions that each draw one card).
    desktop: [(column ratios, [cards])] rows; grid: [[cards]] rows of one or
    two for tablets (a single card spans the row); phone: [cards] in order."""
    if PHONE:
        for part in phone:
            part()
        return
    rows = [([1] * len(r), r) for r in grid] if GRID else desktop
    for ratios, parts in rows:
        if len(parts) == 1:
            parts[0]()
            continue
        for col, part in zip(st.columns(ratios), parts):
            with col:
                part()


def _plot(fig, key=None):
    """Draw a chart. With a key, clicks on its points come back as an event.
    On a touch screen, dragging a chart would zoom it instead of scrolling."""
    if LAYOUT != "desktop":
        fig.update_layout(dragmode=False)
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
    the middle and bottom rows, "form_rows" the players shown in player form.
    On a phone the cards run one under another, the game strip replaced by a
    list of recent games."""
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    form_stats = FORM_STATS_EXT if "pressure_acts" in pdf.columns else FORM_STATS

    tiles_row(D.tiles(team_df, season, baseline), baseline)

    def strip():
        with card("strip"):
            card_title("Game strip", "click a game to open it",
                       keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"])],
                       takeaway=T.strip(tdf))
            rows, z, hover, labels = D.game_strip(tdf)
            ev = _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(), MID_H,
                                     focus=T.top_driver(D.margin_drivers(tdf))),
                       key=f"strip_{season}")
            _open_game(ev, labels, season)

    def recent():
        with card("recent"):
            recent_games(tdf, season)

    def wherewin():
        with card("wherewin"):
            wc = D.win_conditions(tdf)
            card_title("Where we win", keys=[("Freo won it", COLORS["freo"]),
                                             ("Opp won it", COLORS["opp"])],
                       takeaway=T.where_we_win(wc))
            _plot(CH.win_dumbbell(wc, MID_H, focus=T.swing_stat(wc)))

    def quarters():
        with card("quarters"):
            t, s = st.columns([0.6, 1.4], vertical_alignment="center")
            with s:
                qview = st.segmented_control("Quarter view", ["Points", "W v L", "Games"],
                                             default="Points", key="qview",
                                             label_visibility="collapsed") or "Points"
            qp, rm = D.quarter_pattern(tdf), D.running_margin(tdf)
            with t:
                card_title("Quarters")  # colour key sits inside the chart
            take = {"Points": T.quarters(qp), "W v L": T.running(rm),
                    "Games": T.quarter_games(qp)}[qview]
            st.markdown(f'<div class="card-take">{take}</div>', unsafe_allow_html=True)
            if qview == "Points":
                _plot(CH.quarter_bars(qp, MID_H - 12, focus=T.best_worst_quarter(qp)))
            elif qview == "W v L":
                _plot(CH.running_margin_lines(rm, MID_H - 12))
            else:   # every game's quarters: purple Freo won it, cyan the opposition did
                rows, z, hover, labels = D.quarter_strip(tdf)
                ev = _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(),
                                         MID_H - 12, focus=T.best_worst_quarter(qp)[0],
                                         show_x=False), key=f"qstrip_{season}")
                _open_game(ev, labels, season)

    def role_leaders():
        # Same height as its neighbours; on very small windows the list scrolls
        # inside the card instead of pushing the page past the screen.
        with card("leaders", height=_h(max(BOT_H + 40 + TK, 200))):
            leaders = D.role_leaders(pdf)
            card_title("Role leaders", "most games led", takeaway=T.leaders(leaders))
            gk = D.top_goalkickers(pdf, n=1)
            if len(gk):
                leaders.append({"role": "Top goalkicker", "player": gk.index[0],
                                "value": f"{int(gk['goals'].iloc[0])}",
                                "sub": f"goals in {int(gk['games'].iloc[0])} games"})
            leaders_list(leaders)

    def form():
        with card("form"):
            stat = st.session_state.get("form_stat") or "Disposals"
            vals, avgs, _ = D.form_matrix(pdf, form_stats.get(stat, "disposals"),
                                          n_players=sz["form_rows"])
            t, s = st.columns([2.6, 1], vertical_alignment="center")
            with t:
                card_title("Who's up, who's down", "last 3 games against own season avg · "
                           + ("tap a player" if PHONE else "click a player"),
                           keys=[("up", COLORS["freo"]), ("down", COLORS["neutral"])],
                           takeaway=T.form(vals, avgs) if len(vals) else "")
            with s:
                st.selectbox("Form stat", list(form_stats), key="form_stat",
                             label_visibility="collapsed")
            last3, pct = T.form_change(vals, avgs) if len(vals) else ([], [])
            if len(pct):
                ev = _plot(CH.form_dumbbell(last3, avgs, pct, stat, BOT_H - 38,
                                            focus=T.hot_player(vals, avgs)),
                           key=f"form_{season}_{stat}")
                _open_player(ev, season)
            else:
                st.caption("Not enough games yet.")

    def drivers():
        # Click a stat for its scatter (every game, that differential v the margin);
        # "All stats" goes back. The chart key changes on the way back, so the old
        # click isn't reported again.
        with card("drivers"):
            dr = D.margin_drivers(tdf)
            pick = st.session_state.get("driver_pick")
            n = st.session_state.get("driver_n", 0)
            if pick in set(dr["stat"]):
                pts, fit = D.driver_points(tdf, pick)
                t, b = st.columns([5, 1], vertical_alignment="center")
                with t:
                    card_title(pick, "every game", takeaway=T.driver_detail(pick, fit))
                with b:
                    if st.button("", key="driver_back", icon=":material/arrow_back:",
                                 help="Back to all stats"):
                        st.session_state["driver_pick"] = None
                        st.session_state["driver_n"] = n + 1
                        st.rerun()
                ev = _plot(CH.driver_scatter(pts, fit, pick, BOT_H - 10), key=f"drvpts_{season}_{n}")
                point = nav.clicked(ev)
                if point is not None and point.get("point_index") is not None \
                        and point.get("curve_number") == 1:
                    nav.go(view="Match", season=season, game=pts["round"].iloc[point["point_index"]])
                return
            card_title("What drives our margin", "r, not cause · " + ("tap" if PHONE else "click")
                       + " a stat", takeaway=T.drivers(dr))
            ev = _plot(CH.drivers_bar(dr, BOT_H, focus=T.top_driver(dr)), key=f"drv_{season}_{n}")
            point = nav.clicked(ev)
            if point is not None and point.get("y") in set(dr["stat"]):
                st.session_state["driver_pick"] = point["y"]
                st.rerun()

    arrange(desktop=[([2.2, 1.35, 1.15], [strip, wherewin, quarters]),
                     ([1.05, 2.45, 1.2], [role_leaders, form, drivers])],
            grid=[[strip], [wherewin, quarters], [role_leaders, drivers], [form]],
            phone=[recent, wherewin, drivers, quarters, role_leaders, form])


RECENT_N = 8  # games in the phone's recent games list before "Show all"


def recent_games(tdf, season):
    """Phone: the season's games as a list, newest first, each a button that
    opens the game in Match view (the game strip is too narrow to read or tap)."""
    show_all = st.session_state.get(f"recent_all_{season}", False)
    games = tdf.iloc[::-1] if show_all else tdf.iloc[::-1].head(RECENT_N)
    card_title("Recent games" if not show_all else "Every game", "tap a game to open it",
               takeaway=T.strip(tdf))
    for r in games.itertuples():
        label = (f"**{r.result}** · {r.round} v {r.opponent} · "
                 f"{int(r.freo_score)}-{int(r.opp_score)} ({int(r.margin):+d})")
        if st.button(label, key=f"rg_{season}_{r.round}", width="stretch"):
            nav.go(view="Match", season=season, game=r.round)
    if len(tdf) > RECENT_N:
        more = "Show fewer" if show_all else f"Show all {len(tdf)} games"
        if st.button(more, key=f"rg_more_{season}", type="tertiary"):
            st.session_state[f"recent_all_{season}"] = not show_all
            st.rerun()


# ---- Match mode ------------------------------------------------------------
# Player grid columns in match mode: header label -> player column.
MATCH_STATS = [
    ("D", "disposals"), ("K", "kicks"), ("H", "handballs"), ("M", "marks"),
    ("CP", "contested_poss"), ("CLR", "clearances"), ("I50", "inside_50s"),
    ("T", "tackles"), ("MG", "metres_gained"), ("SI", "score_involvements"),
    ("PA", "pressure_acts"), ("R50", "rebound_50s"), ("G", "goals"), ("B", "behinds"),
    ("RP", "rating_points"),
]
# The columns kept in player grids on a phone (about 50px each fits 390px wide).
PHONE_GRID = {"D", "CP", "CLR", "T", "MG", "G"}
BREAK_NAMES = {"Q1": "quarter time", "Q2": "half time", "Q3": "three quarter time",
               "Q4": "the siren"}


def render_match(team_df, player_df, season, pos, sz):
    """One game on one screen, every number against the season average.

    Row 1: tiles for this game (change vs season average).
    Row 2: tale of the tape | game flow (running margin) | who led each role.
    Row 3: every Freo player, shaded against their own season average.
    """
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK + ROW_GAIN
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    game = tdf.iloc[pos]
    opp_c = club_colours(game["opponent"])["chart"]   # the opposition in their own colour

    tiles_row(D.match_tiles(team_df, season, pos), "Season avg")

    def tape_card():
        with card("tape", height=_h(MID_H + 40 + TK)):
            rows = D.tale_of_the_tape(tdf, pos)
            card_title("Tale of the tape", keys=[("Freo", COLORS["freo"]),
                                                 (D.abbr(game["opponent"]), opp_c),
                                                 ("season avg share", COLORS["ink"])],
                       takeaway=T.tape(rows))
            tape(rows, opp_color=opp_c)

    def flow_card():
        with card("flow"):
            flow, avg = D.game_flow(tdf, pos)
            take = T.flow(flow.rename(index=BREAK_NAMES), game["result"], int(game["margin"]))
            card_title("Game flow", keys=[("This game", COLORS["freo"]), ("Avg W", COLORS["win"]),
                                          ("Avg L", COLORS["loss"]),
                                          ("Others", COLORS["neutral"])], takeaway=take)
            others = D.season_flows(tdf).drop(index=pos)
            _plot(CH.game_flow_lines(flow, avg, MID_H, others=others))

    def leaders_card():
        with card("gameleaders", height=_h(MID_H + 40 + TK)):
            leaders, goals = D.match_leaders(pdf, game)
            theirs = D.opp_match_leaders(game)
            if theirs is None:       # no opposition player stats for this game
                card_title("Game leaders", takeaway=T.match_leaders(goals))
                leaders_list(leaders)
            else:
                card_title("Game leaders", takeaway=T.match_leaders(goals, theirs[1], D.abbr(game["opponent"])))
                leaders_pair(leaders, theirs[0], D.abbr(game["opponent"]), opp_c)

    def players_card():
        _match_players(pdf, game, season, pos, BOT_H)

    arrange(desktop=[([1.5, 1.25, 1], [tape_card, flow_card, leaders_card]), ([1], [players_card])],
            grid=[[tape_card, leaders_card], [flow_card], [players_card]],
            phone=[tape_card, flow_card, leaders_card, players_card])


# The match view's "above themselves" columns (with AFL match centre stats, or without).
VS_SELF_STATS = [("Disposals", "disposals"), ("Contested", "contested_poss"),
                 ("Metres gained", "metres_gained"), ("Score inv.", "score_involvements"),
                 ("Tackles", "tackles"), ("Pressure acts", "pressure_acts")]
VS_SELF_STATS_BASIC = [("Disposals", "disposals"), ("Contested", "contested_poss"),
                       ("Marks", "marks"), ("Clearances", "clearances"),
                       ("Inside 50s", "inside_50s"), ("Tackles", "tackles")]
PHONE_VS_SELF = {"Disposals", "Contested", "Metres gained", "Marks"}
PHONE_SHORT = {"Disposals": "Disp", "Contested": "CP", "Metres gained": "MG", "Marks": "Marks"}


def _match_players(pdf, game, season, pos, BOT_H):
    """Every Freo player in this game. By default, who played above or below
    themselves (each game number as a % of the player's own season average, on a
    few key stats); "Show all numbers" gives the full grid."""
    with card("players", height=_h(BOT_H + 40 + TK)):
        full = st.session_state.get("mplayers_all", False)
        t, s = st.columns([4, 1], vertical_alignment="center")
        with s:
            st.toggle("Show all numbers", key="mplayers_all")
        if full:
            stats = [(lbl, col) for lbl, col in MATCH_STATS if col in pdf.columns
                     and (not PHONE or lbl in PHONE_GRID)]
            vals, pct, _ = D.match_players(pdf, game, [c for _, c in stats])
            with t:
                card_title("Players this game", "shaded against each player's own season average · "
                           + ("tap a player" if PHONE else "click a player"),
                           keys=[("below", RAMP[0]), ("above", RAMP[-1])],
                           takeaway=T.match_players(vals))
            grid_h = max(BOT_H - 10, 18 * len(vals) + 40)  # scrolls inside the card if needed
            ev = _plot(CH.match_player_grid(vals, pct, [lbl for lbl, _ in stats], grid_h),
                       key=f"mplayers_{season}_{pos}")
            _open_player(ev, season)
            return
        spec = VS_SELF_STATS if "pressure_acts" in pdf.columns else VS_SELF_STATS_BASIC
        spec = [(lbl, col) for lbl, col in spec if col in pdf.columns]
        # A phone shows three columns; the takeaway is still worked out from all of them.
        stats = [(PHONE_SHORT.get(lbl, lbl), col) for lbl, col in spec if lbl in PHONE_VS_SELF] \
            if PHONE else spec
        cols = [c for _, c in spec] + (["rating_points"] if "rating_points" in pdf.columns else [])
        vals, pct, avgs = D.match_players(pdf, game, cols)
        with t:
            card_title("Who played above themselves",
                       "each dot: this game against the player's own season average · "
                       + ("tap" if PHONE else "click") + " a player",
                       keys=[("15%+ above", COLORS["freo"]), ("15%+ below", COLORS["neutral"])],
                       takeaway=T.vs_self(vals, pct, avgs, spec))
        h = max(BOT_H - 10, 18 * len(vals) + 44)  # scrolls inside the card if needed
        ev = _plot(CH.vs_self_dots(vals, pct, avgs, stats, h, rp=vals.get("rating_points"),
                                   ticks=not PHONE), key=f"mvself_{season}_{pos}")
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
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK + ROW_GAIN
    pdf = D.players_season(player_df, season)
    me = pdf[pdf["player"] == player].sort_values("game_dt")
    trend_stats = {k: v for k, v in PLAYER_TREND_STATS.items() if v in pdf.columns}

    tiles_row(D.player_tiles(player_df, player, season, baseline), baseline,
              rank_label="squad rank")

    def trend_card():
        with card("ptrend"):
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

    def ranks_card():
        with card("pranks"):
            pr = D.player_squad_ranks(pdf, player)
            card_title("Squad rank", f"per game, of players with {D.MIN_GAMES}+ games",
                       takeaway=T.player_ranks(pr))
            if len(pr):
                _plot(CH.squad_rank_bars(pr, MID_H, focus=T.rank_focus(pr)))
            else:
                st.caption(f"Needs {D.MIN_GAMES} games for a squad rank.")

    def log_card():
        _player_log(pdf, player, BOT_H)

    arrange(desktop=[([1.9, 1.1], [trend_card, ranks_card]), ([1], [log_card])],
            grid=[[trend_card, ranks_card], [log_card]],
            phone=[trend_card, ranks_card, log_card])


# The range card's rows (full names), from the log stats.
RANGE_NAMES = {"D": "Disposals", "CP": "Contested poss", "CLR": "Clearances", "I50": "Inside 50s",
               "MG": "Metres gained", "SI": "Score involvements", "T": "Tackles",
               "PA": "Pressure acts", "G": "Goals", "RP": "Rating points"}


def _player_log(pdf, player, BOT_H):
    """The player's season stat by stat: every game as a dot against his own
    average (the range), the latest game ringed; "Show all numbers" gives the
    per-game table."""
    with card("plog", height=_h(BOT_H + 40 + TK)):
        log = D.player_log(pdf, player)
        full = st.session_state.get("plog_all", False)
        t, s = st.columns([4, 1], vertical_alignment="center")
        with s:
            st.toggle("Show all numbers", key="plog_all")
        if not full:
            stats = [(RANGE_NAMES[l], c) for l, c in LOG_STATS if l in RANGE_NAMES
                     and c in log.columns]
            in_order = log.sort_values("game_dt").reset_index(drop=True) if len(log) else log
            with t:
                card_title("Range on each stat", "every game against his own season average · "
                           + ("tap" if PHONE else "click") + " a game",
                           keys=[("latest game", COLORS["freo"]), ("other games", RAMP[1])],
                           takeaway=T.last_game_vs_avg(in_order, stats))
            if len(log) >= 2:
                h = max(BOT_H - 10, 22 * len(stats) + 40)
                ev = _plot(CH.player_ranges(in_order, stats, h), key=f"prange_{player}")
                point = nav.clicked(ev)
                # The dots run stat by stat, every game in date order within each stat.
                if point is not None and point.get("curve_number") == 0 \
                        and point.get("point_index") is not None:
                    row = in_order.iloc[point["point_index"] % len(in_order)]
                    nav.go(view="Match", season=int(row["season"]), game=row["round"])
            else:
                st.caption("Needs two games or more.")
            return
        stats = [(l, c) for l, c in LOG_STATS if c in log.columns
                 and (not PHONE or l in PHONE_GRID)]
        with t:
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


# ---- Player vs player -----------------------------------------------------------
def render_compare(player_df, season, a, b, sz):
    """Two players' seasons side by side.

    Row 1: each tile stat, both players' averages and squad ranks.
    Row 2: game by game for both (pick a stat) | squad rank on every stat.
    Row 3: every stat, season and last 5 averages, and the gap.
    """
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK + ROW_GAIN - 3
    pdf = D.players_season(player_df, season)
    names = (a, b)
    logs = [pdf[pdf["player"] == n].sort_values("game_dt") for n in names]
    cmp = D.compare_players(pdf, a, b)
    trend_stats = {k: v for k, v in PLAYER_TREND_STATS.items() if v in pdf.columns}
    compare_tiles_row(cmp, names, [lbl for lbl, _ in D.PLAYER_TILES])
    keys = [(n, c) for n, c in zip(names, CH.PAIR)]

    def trend_card():
        with card("ctrend"):
            label = st.session_state.get("ctrend_stat") or "Disposals"
            col = trend_stats.get(label, "disposals")
            t, s = st.columns([2.4, 1], vertical_alignment="center")
            with t:
                card_title("Game by game", "dashed: season average", keys=keys,
                           takeaway=T.compare_last(logs, names, col, label))
            with s:
                st.selectbox("Compare stat", list(trend_stats), key="ctrend_stat",
                             label_visibility="collapsed")
            season_games = pdf.drop_duplicates(["round"])[["round", "opponent", "game_dt"]]
            _plot(CH.compare_trend(season_games, logs, names, col, label, MID_H - 10))

    def ranks_card():
        with card("cranks"):
            card_title("Squad rank", f"per game, of players with {D.MIN_GAMES}+ games",
                       keys=keys, takeaway=T.compare_ahead(cmp, names))
            if cmp[["rank_a", "rank_b"]].notna().all(axis=1).any():
                _plot(CH.compare_ranks(cmp, names, MID_H))
            else:
                st.caption(f"Both need {D.MIN_GAMES} games for a squad rank.")

    def table_card():
        with card("ctable", height=_h(BOT_H + 40 + TK)):
            card_title("Stat by stat", "per game, season and last 5", takeaway=T.compare_gap(cmp, names))
            compare_table(cmp, names)

    arrange(desktop=[([1.9, 1.1], [trend_card, ranks_card]), ([1], [table_card])],
            grid=[[trend_card, ranks_card], [table_card]],
            phone=[trend_card, ranks_card, table_card])


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

    games = lg[(lg["season"] == season) & (lg["team"] == opp)].tail(14)

    def style_card():
        with card("style"):
            avg, ranks = D.team_ranks(lg, season)
            card_title("Style vs league", "rank of 18 on each stat", takeaway=T.style(ranks, opp))
            _plot(CH.rank_dumbbell(avg, ranks, opp, D.SCOUT_STATS, MID_H, team_color=tint,
                                   focus=T.style_marks(ranks, opp)))

    def win_card():
        with card("howtheywin"):
            short = D.abbr(opp)
            wc = D.scout_win_conditions(lg, opp, season)
            card_title("How they win", keys=[(f"{short} won it", tint),
                                             ("Their opponent did", grey)],
                       takeaway=T.where_we_win(wc))
            _plot(CH.win_dumbbell(wc, MID_H, names=(f"{short} won it", "Their opponent won it"),
                                  colors=(tint, grey), focus=T.swing_stat(wc)))

    def quarters_card():
        with card("theirquarters"):
            qp = D.scout_quarters(lg, opp, season)
            card_title("Their quarters", "avg points", takeaway=T.quarters(qp))
            _plot(CH.quarter_bars(qp, MID_H - 12, names=(opp, "Opponents"), colors=(tint, grey),
                                  focus=T.best_worst_quarter(qp)))

    def form_card():
        with card("theirform"):
            card_title("Their form", f"last {len(games)} games, green win, red loss",
                       takeaway=T.scout_form(games))
            _plot(CH.form_bars(games, BOT_H))

    def h2h_card():
        with card("h2h", height=_h(BOT_H + 40 + TK)):
            rows = D.head_to_head(team_df, opp)
            card_title("Against Fremantle", "every game, all seasons", takeaway=T.h2h(rows))
            if len(rows):
                h2h_table(rows)
            else:
                st.caption("No games against Fremantle in the data.")

    arrange(desktop=[([1.45, 1.35, 1.2], [style_card, win_card, quarters_card]),
                     ([1.55, 1.45], [form_card, h2h_card])],
            grid=[[style_card, win_card], [quarters_card, form_card], [h2h_card]],
            phone=[style_card, win_card, quarters_card, form_card, h2h_card])


# ---- Whole squad, all clubs, quarter-time check ---------------------------------
# Pages with no tiles row: their cards take the height of the tiles and both
# chart rows. On the scrolling layouts they get a fixed, readable height.
SQUAD_STATS = {
    "Disposals": "disposals", "Contested poss": "contested_poss",
    "Uncontested poss": "uncontested_poss", "Metres gained": "metres_gained",
    "Score involvements": "score_involvements", "Pressure acts": "pressure_acts",
    "Tackles": "tackles", "Clearances": "clearances", "Inside 50s": "inside_50s",
    "Rebound 50s": "rebound_50s", "Intercepts": "intercepts", "Marks": "marks",
    "One percenters": "one_percenters", "Goals": "goals",
}
def _full_h(sz):
    """Outer height of a card filling the page below the band: level with the
    bottom of the Wharf-ai panel, which starts 58px higher (the header row)."""
    return sz["panel"] - 58 if LAYOUT == "desktop" else 520


def render_squad(player_df, season, baseline, sz):
    """Every player at once: two chosen stats per game | year on year."""
    H = _full_h(sz)
    chart_h = H - 84            # the card's title, takeaway and padding
    pdf = D.players_season(player_df, season)
    stats = {k: v for k, v in SQUAD_STATS.items() if v in pdf.columns}
    labels = list(stats)

    def map_card():
        with card("pmap", height=_h(H)):
            t, cx, cy = st.columns([1.3, 1, 1], vertical_alignment="center")
            with cx:
                x = st.selectbox("Across", labels, index=labels.index("Contested poss"),
                                 key="pmap_x", format_func=lambda v: f"Across: {v}",
                                 label_visibility="collapsed")
            with cy:
                y_default = "Metres gained" if "Metres gained" in stats else "Uncontested poss"
                y = st.selectbox("Up", labels, index=labels.index(y_default), key="pmap_y",
                                 format_func=lambda v: f"Up: {v}", label_visibility="collapsed")
            size_col = "time_on_ground_pct" if "time_on_ground_pct" in pdf.columns else "pct_played"
            pa = D.player_averages(pdf, [stats[x], stats[y], size_col])
            with t:
                card_title("Player map", "per game, 5+ games, dot size: time on ground",
                           takeaway=T.squad_map(pa, stats[x], stats[y], x, y))
            if not len(pa):
                st.caption("No players with 5 games yet.")
                return
            ev = _plot(CH.player_map(pa, stats[x], stats[y], x, y, size_col, chart_h),
                       key=f"pmap_{season}_{x}_{y}")
            point = nav.clicked(ev)
            if point is not None and point.get("point_index") is not None:
                nav.go(view="Player", season=season, player=pa.index[point["point_index"]])

    def yoy_card():
        with card("yoy", height=_h(H)):
            if baseline is None:
                card_title("Year on year")
                st.caption(f"Needs the season before {season} in the data.")
                return
            base_stats = [k for k in labels if stats[k] in D.players_season(player_df, baseline)]
            t, c = st.columns([1.6, 1], vertical_alignment="center")
            with c:
                stat = st.selectbox("Year on year stat", base_stats, key="yoy_stat",
                                    label_visibility="collapsed")
            yoy = D.year_on_year(player_df, baseline, season, stats[stat])
            with t:
                card_title("Year on year", "top 15, 8+ games in both",
                           keys=[("up", COLORS["freo"]), ("down", COLORS["neutral"])],
                           takeaway=T.year_on_year(yoy))
            if not len(yoy):
                st.caption("No players with enough games in both seasons.")
                return
            ev = _plot(CH.slope_chart(yoy, baseline, season, stat, chart_h),
                       key=f"yoy_{season}_{stat}")
            point = nav.clicked(ev)
            if point is not None and point.get("curve_number") is not None:
                nav.go(view="Player", season=season, player=yoy.index[point["curve_number"]])

    arrange(desktop=[([1.25, 1], [map_card, yoy_card])],
            grid=[[map_card], [yoy_card]], phone=[map_card, yoy_card])


def render_clubs(team_df, all_seasons, sz):
    """Every game against every club, all seasons, toughest first."""
    grid = D.opponent_grid(team_df)
    H = _full_h(sz)

    def grid_card():
        with card("clubs", height=_h(H)):
            card_title("Every club", "every game, all seasons, toughest first · "
                       "chips show round and margin, hover for the score",
                       takeaway=T.clubs(grid))
            opponents_table(grid, all_seasons, max_h=H - 128 if LAYOUT == "desktop" else None)
            c1, c2, _ = st.columns([1.2, 1.4, 2], vertical_alignment="center")
            opp = c1.selectbox("Ask about", [r["opponent"] for r in grid], key="clubs_ask",
                               label_visibility="collapsed")
            if c2.button(f"Ask Wharf-ai about {opp}", key="clubs_ask_btn"):
                st.session_state["pending_prompt"] = (
                    f"How have we gone against {opp} across {all_seasons[0]} to "
                    f"{all_seasons[-1]}, and what decided those games?")
                st.rerun()

    arrange(desktop=[([1], [grid_card])], grid=[[grid_card]], phone=[grid_card])


def render_quarter_time(team_df, all_seasons, sz):
    """Enter the margin at a break; see how Freo have gone from similar positions.

    Only quarter scores are in the data (AFL Tables has no quarter-by-quarter
    stats), so positions are matched on the margin alone."""
    H = _full_h(sz)
    INPUT_H = 108                      # the inputs card, and the gap under it
    rest = H - INPUT_H - 16            # for the two rows below
    top_h = int(rest * 0.58) if LAYOUT == "desktop" else 340
    low_h = rest - top_h + 4

    with card("qtinput", height=_h(INPUT_H)):
        card_title("Quarter-time check", "enter the margin at a break")
        c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1.1, 1.6], vertical_alignment="bottom")
        brk = c1.selectbox("Break", list(D.BREAKS), index=1, key="qt_brk")
        margin = c2.number_input("Freo margin", value=0, step=1, key="qt_margin",
                                 help="Freo score minus opposition score at the break")
        window = c3.number_input("Within ± points", value=6, min_value=0, max_value=60, step=1,
                                 key="qt_window")
        scope = c4.selectbox("Seasons", ["All seasons"] + [str(s) for s in reversed(all_seasons)],
                             key="qt_scope")
        game_type = c5.segmented_control("Venue", ["Any", "Home", "Away", "Final"], default="Any",
                                         key="qt_venue") or "Any"
    seasons = None if scope == "All seasons" else [int(scope)]
    gt = None if game_type == "Any" else game_type
    games, sm = D.similar_positions(team_df, brk, int(margin), int(window), seasons, gt)
    col = sm["col"]

    def result_card():
        with card("qtresult", height=_h(top_h)):
            card_title("From there")
            if sm["games"]:
                st.markdown(
                    f'<div class="qt-box"><div class="qt-big">{record_text(sm["wins"], sm["losses"], sm["draws"])}</div>'
                    f'<div class="qt-sub">from {sm["games"]} games within ±{int(window)} of '
                    f'{int(margin):+d} at {brk.lower()} ({sm["win_pct"]:.0f}% won, of '
                    f'{sm["pool"]} games checked)</div>'
                    f'<div class="qt-line">Average final margin <b>{sm["avg_final"]:+.1f}</b></div>'
                    f'<div class="qt-line">Net scoring from the break to the siren '
                    f'<b>{sm["avg_after"]:+.1f}</b></div></div>',
                    unsafe_allow_html=True)
            else:
                st.info("No games from a position like that. Widen the ± window.")
            st.caption("Matched on the score only: quarter-by-quarter stats (inside 50s, "
                       "clearances) are not in the data. A small sample says little; check the count.")

    def scatter_card():
        with card("qtscatter", height=_h(top_h)):
            card_title(f"Margin at {brk.lower()} and at the siren", "every game, shaded: your window")
            bm = D.break_margins(team_df)
            if seasons:
                bm = bm[bm["season"].isin(seasons)]
            if gt:
                bm = bm[bm["type"] == gt]
            _plot(CH.break_scatter(bm, col, int(margin), int(window), brk, top_h - 56))

    def games_card():
        with card("qtgames", height=_h(low_h)):
            card_title("The matching games", f"{sm['games']} games" if sm["games"] else "")
            if sm["games"]:
                show = games[["season", "round", "type", "opponent", col, "margin", "result"]].rename(
                    columns={col: f"At {brk.lower()}", "margin": "Final", "result": "Result",
                             "season": "Season", "round": "Round", "type": "Type",
                             "opponent": "Opponent"})
                st.dataframe(show, hide_index=True, width="stretch",
                             height=max(low_h - 56, 80) if LAYOUT == "desktop" else 260)
            else:
                st.caption("None yet.")

    arrange(desktop=[([1, 1.6], [result_card, scatter_card]), ([1], [games_card])],
            grid=[[result_card, scatter_card], [games_card]],
            phone=[result_card, scatter_card, games_card])
