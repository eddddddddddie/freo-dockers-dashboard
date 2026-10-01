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
                   h2h_table, compare_tiles_row, compare_table)

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
            ev = _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(), MID_H),
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
            _plot(CH.win_conditions_bars(wc, MID_H))

    def quarters():
        with card("quarters"):
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
                card_title("Player form", "last 6 games vs own season avg · "
                           + ("tap a player" if PHONE else "click a player"),
                           keys=[("below", RAMP[0]), ("above", RAMP[-1])],
                           takeaway=T.form(vals, avgs) if len(vals) else "")
            with s:
                st.selectbox("Form stat", list(form_stats), key="form_stat",
                             label_visibility="collapsed")
            if len(vals):
                ev = _plot(CH.form_heatmap(vals, avgs, stat, BOT_H - 38),
                           key=f"form_{season}_{stat}")
                _open_player(ev, season, strip_avg=True)
            else:
                st.caption("Not enough games yet.")

    def drivers():
        with card("drivers"):
            dr = D.margin_drivers(tdf)
            card_title("What drives our margin", "r, not cause", takeaway=T.drivers(dr))
            _plot(CH.drivers_bar(dr, BOT_H))

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
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    game = tdf.iloc[pos]

    tiles_row(D.match_tiles(team_df, season, pos), "Season avg")

    def tape_card():
        with card("tape", height=_h(MID_H + 40 + TK)):
            rows = D.tale_of_the_tape(tdf, pos)
            card_title("Tale of the tape", keys=[("Freo", COLORS["freo"]), ("Opp", COLORS["opp"]),
                                                 ("season avg share", COLORS["ink"])],
                       takeaway=T.tape(rows))
            tape(rows)

    def flow_card():
        with card("flow"):
            flow, avg = D.game_flow(tdf, pos)
            take = T.flow(flow.rename(index=BREAK_NAMES), game["result"], int(game["margin"]))
            card_title("Game flow", keys=[("This game", COLORS["freo"]), ("Avg win", COLORS["win"]),
                                          ("Avg loss", COLORS["loss"])], takeaway=take)
            _plot(CH.game_flow_lines(flow, avg, MID_H))

    def leaders_card():
        with card("gameleaders", height=_h(MID_H + 40 + TK)):
            leaders, goals = D.match_leaders(pdf, game)
            card_title("Game leaders", takeaway=T.match_leaders(goals))
            leaders_list(leaders)

    def players_card():
        _match_players(pdf, game, season, pos, BOT_H)

    arrange(desktop=[([1.5, 1.25, 1], [tape_card, flow_card, leaders_card]), ([1], [players_card])],
            grid=[[tape_card, leaders_card], [flow_card], [players_card]],
            phone=[tape_card, flow_card, leaders_card, players_card])


def _match_players(pdf, game, season, pos, BOT_H):
    with card("players", height=_h(BOT_H + 40 + TK)):
        stats = [(lbl, col) for lbl, col in MATCH_STATS if col in pdf.columns
                 and (not PHONE or lbl in PHONE_GRID)]
        vals, pct, _ = D.match_players(pdf, game, [c for _, c in stats])
        card_title("Players this game", "shaded against each player's own season average · "
                   + ("tap a player" if PHONE else "click a player"),
                   keys=[("below", RAMP[0]), ("above", RAMP[-1])], takeaway=T.match_players(vals))
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
                _plot(CH.squad_rank_bars(pr, MID_H))
            else:
                st.caption(f"Needs {D.MIN_GAMES} games for a squad rank.")

    def log_card():
        _player_log(pdf, player, BOT_H)

    arrange(desktop=[([1.9, 1.1], [trend_card, ranks_card]), ([1], [log_card])],
            grid=[[trend_card, ranks_card], [log_card]],
            phone=[trend_card, ranks_card, log_card])


def _player_log(pdf, player, BOT_H):
    with card("plog", height=_h(BOT_H + 40 + TK)):
        log = D.player_log(pdf, player)
        stats = [(l, c) for l, c in LOG_STATS if c in log.columns
                 and (not PHONE or l in PHONE_GRID)]
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
    MID_H, BOT_H = sz["mid"] - TK, sz["bot"] - TK
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
            _plot(CH.rank_dumbbell(avg, ranks, opp, D.SCOUT_STATS, MID_H, team_color=tint))

    def win_card():
        with card("howtheywin"):
            short = D.abbr(opp)
            wc = D.scout_win_conditions(lg, opp, season)
            card_title("How they win", keys=[(f"{short} won it", tint),
                                             ("Their opponent did", grey)],
                       takeaway=T.where_we_win(wc))
            _plot(CH.win_conditions_bars(wc, MID_H,
                                         names=(f"{short} won it", "Their opponent won it"),
                                         colors=(tint, grey)))

    def quarters_card():
        with card("theirquarters"):
            qp = D.scout_quarters(lg, opp, season)
            card_title("Their quarters", "avg points", takeaway=T.quarters(qp))
            _plot(CH.quarter_bars(qp, MID_H - 12, names=(opp, "Opponents"), colors=(tint, grey)))

    def form_card():
        with card("theirform"):
            card_title("Their form", f"last {len(games)} games, green win, red loss",
                       takeaway=T.scout_form(games))
            _plot(CH.form_bars(games, BOT_H))

    def h2h_card():
        with card("h2h", height=_h(BOT_H + 40 + TK)):
            rows = D.head_to_head(team_df, opp)
            card_title("Against Fremantle", "every game, both seasons", takeaway=T.h2h(rows))
            if len(rows):
                h2h_table(rows)
            else:
                st.caption("No games against Fremantle in the data.")

    arrange(desktop=[([1.45, 1.35, 1.2], [style_card, win_card, quarters_card]),
                     ([1.55, 1.45], [form_card, h2h_card])],
            grid=[[style_card, win_card], [quarters_card, form_card], [h2h_card]],
            phone=[style_card, win_card, quarters_card, form_card, h2h_card])
