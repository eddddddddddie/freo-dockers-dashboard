"""Cards that v2.py reuses: the match players table, the player's game log
and the SIMULATED ground cards (positions, events and GPS running). Pages scroll, so cards grow with their content.

Every card has a computed one-line takeaway under its title (takeaways.py).
Clicking a player in a table opens their profile (nav.go; v2.apply turns the
old view names into places).
"""

import numpy as np
import pandas as pd
import streamlit as st

import data as D
import charts as CH
import nav
import takeaways as T
from theme import COLORS, RAMP, card_title, fit_mode, is_dark


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
PHONE = False    # set by v2.run: phones get fewer columns and one card a row


def set_layout(mode):
    global PHONE
    PHONE = mode == "phone"


def arrange(grid, phone):
    """Draw cards (functions that each draw one card): grid, rows of one or two
    (a single card spans the row); phone, the cards in order, one a row."""
    if PHONE:
        for part in phone:
            part()
        return
    for parts in grid:
        if len(parts) == 1:
            parts[0]()
            continue
        for col, part in zip(st.columns(len(parts)), parts):
            with col:
                part()


def _plot(fig, key=None):
    """Draw a chart. With a key, clicks on its points come back as an event.
    On a touch screen, dragging a chart would zoom it instead of scrolling."""
    fig.update_layout(dragmode=False)
    fig = fit_mode(fig)
    if key is None:
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        return None
    return st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG,
                           on_select="rerun", selection_mode="points", key=key)




# ---- Match mode ------------------------------------------------------------
# The columns kept in player grids on a phone (about 50px each fits 390px wide).
PHONE_GRID = {"D", "CP", "CLR", "T", "MG", "G"}


# The match players table: (header, column, full name). With AFL match centre
# stats, or without; a phone keeps the four marked True.
TABLE_STATS = [("Disp", "disposals", "Disposals", True), ("CP", "contested_poss", "Contested possessions", True),
               ("CLR", "clearances", "Clearances", False), ("I50", "inside_50s", "Inside 50s", False),
               ("MG", "metres_gained", "Metres gained", True), ("SI", "score_involvements", "Score involvements", False),
               ("T", "tackles", "Tackles", True), ("PA", "pressure_acts", "Pressure acts", False),
               ("M", "marks", "Marks", False), ("G", "goals", "Goals", False)]
STANDOUT = 30   # % above or below a player's own season average that gets a cell tinted
TINT_UP, TINT_DOWN = "#EDE5F7", "#F0F0F0"   # the standout cell tints (and their keys)
TINTS = ((TINT_UP, COLORS["brand"]), (TINT_DOWN, "#6B6B6B"))        # (background, text)
TINTS_DARK = (("#3B2A5C", "#E4DAF7"), ("#2A2732", "#8C8796"))


def _match_players(pdf, game, season, pos):
    """Every Freo player in this game as a stats table: the number and a bar
    (against the best in the team that game) in each cell, cells 30%+ above the
    player's own season average tinted purple and 30%+ below tinted grey (on
    averages big enough for a % to mean much). Sort by clicking a header; select
    a row for the player's profile."""
    with card("players"):
        stats = [(h, c, n) for h, c, n, phone in TABLE_STATS
                 if c in pdf.columns and (phone or not PHONE)]
        if "pressure_acts" in pdf.columns:
            stats = [s for s in stats if s[1] != "marks"]     # room for the match centre stats
        cols = [c for _, c, _ in stats]
        rp = "rating_points" if "rating_points" in pdf.columns and not PHONE else None
        vals, pct, avgs = D.match_players(pdf, game, cols + ([rp] if rp else []))
        (up_bg, up_ink), (down_bg, down_ink) = TINTS_DARK if is_dark() else TINTS
        card_title("Players this game", "the number and a bar against the team's best · sort by a "
                   "header, " + ("tap" if PHONE else "click") + " a row for the player",
                   keys=[(f"{STANDOUT}%+ above own avg", up_bg), (f"{STANDOUT}%+ below", down_bg)],
                   takeaway=T.vs_self(vals, pct, avgs, [(n, c) for _, c, n in stats]))
        df = vals[cols + ([rp] if rp else [])].reset_index().rename(columns={"index": "Player"})
        df.columns = ["Player"] + cols + (["RP"] if rp else [])
        df = df[["Player"] + (["RP"] if rp else []) + cols]

        def tint(frame):
            out = pd.DataFrame("", index=frame.index, columns=frame.columns)
            for c in cols:
                ok = (avgs[c] >= CH.VS_SELF_MIN_AVG.get(c, 0)).values
                up = (pct[c].values >= 100 + STANDOUT) & ok
                down = (pct[c].values <= 100 - STANDOUT) & ok
                out.loc[up, c] = f"background-color:{up_bg}; color:{up_ink}; font-weight:700"
                out.loc[down, c] = f"background-color:{down_bg}; color:{down_ink}"
            return out

        # Narrow columns: on a desktop the table shares its row with the ground card.
        cfg = {"Player": st.column_config.TextColumn("Player", width="small" if PHONE else 112,
                                                     pinned=True)}
        if rp:
            cfg["RP"] = st.column_config.NumberColumn("RP", help="Rating points", format="%d",
                                                      width=42)
        for h, c, n in stats:
            cfg[c] = st.column_config.ProgressColumn(h, help=n, min_value=0,
                                                     max_value=float(max(df[c].max(), 1)),
                                                     format="%d", width="small" if PHONE else 64)
        n_sel = st.session_state.get("mtable_n", 0)
        ev = st.dataframe(df.style.apply(tint, axis=None), column_config=cfg, hide_index=True,
                          row_height=26,   # about 9 players in view on a laptop; the rest scroll
                          height=min(30 + 26 * len(df), 520),
                          on_select="rerun", selection_mode="single-row",
                          key=f"mtable_{season}_{pos}_{n_sel}")
        rows = (ev.selection.get("rows") if ev and hasattr(ev, "selection") else None) or []
        if rows:
            st.session_state["mtable_n"] = n_sel + 1     # a fresh table next time, no stale pick
            nav.go(view="Player", season=season, player=df["Player"].iloc[rows[0]])


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


# The range card's rows (full names), from the log stats.
RANGE_NAMES = {"D": "Disposals", "CP": "Contested poss", "CLR": "Clearances", "I50": "Inside 50s",
               "MG": "Metres gained", "SI": "Score involvements", "T": "Tackles",
               "PA": "Pressure acts", "G": "Goals", "RP": "Rating points"}


def _player_log(pdf, player, height):
    """The player's season stat by stat: every game as a dot against his own
    average (the range), the latest game ringed; "Show all numbers" gives the
    per-game table."""
    with card("plog"):
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
                card_title("Range on each stat", "every game against his own season average, the "
                           "latest ringed · " + ("tap" if PHONE else "click") + " a game",
                           takeaway=T.last_game_vs_avg(in_order, stats))
            if len(log) >= 2:
                h = max(height - 10, 22 * len(stats) + 40)
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
            grid_h = max(height - 10, 18 * len(vals) + 40)
            _plot(CH.match_player_grid(vals, pct, [l for l, _ in stats], grid_h))


# ---- Quarter-time check ---------------------------------------------------------
# chart rows. On the scrolling layouts they get a fixed, readable height.
SQUAD_STATS = {
    "Disposals": "disposals", "Contested poss": "contested_poss",
    "Uncontested poss": "uncontested_poss", "Metres gained": "metres_gained",
    "Score involvements": "score_involvements", "Pressure acts": "pressure_acts",
    "Tackles": "tackles", "Clearances": "clearances", "Inside 50s": "inside_50s",
    "Rebound 50s": "rebound_50s", "Intercepts": "intercepts", "Marks": "marks",
    "One percenters": "one_percenters", "Goals": "goals",
}


# ---- On the ground (SIMULATED): positions and GPS running --------------------------
def _ground_card(name, rows, role, who, attack="Freo", running=None, heat=True, chart_h=300):
    """A SIMULATED ground card for some player-game rows, with its own switch:
    Heat (where they spent the time), Events (their real goals, marks and
    possessions at simulated spots) and, given running = (takeaway, draw(height)),
    Running (GPS). heat=False leaves out the heat map; with one mode, no switch."""
    import sim
    with card(name):
        modes = (["Heat"] if heat else []) + ["Events"] + (["Running"] if running else [])
        mode = st.session_state.get(f"{name}_mode") or modes[0]
        t = st.container()           # the title, drawn once the mode's figures are known
        if len(modes) > 1:
            st.segmented_control("Ground", modes, default=modes[0], key=f"{name}_mode",
                                 label_visibility="collapsed")
        if mode == "Running":
            with t:
                card_title("Running", "SIMULATED GPS", takeaway=running[0])
            running[1](chart_h)
            return
        if mode == "Heat":
            per = 140 if len(rows) <= 30 else max(20, int(4000 / max(len(rows), 1)))
            xy = np.vstack([sim.positions(r.player, r.season, r.round, role.get(r.player, "mid"), per)
                            for r in rows.itertuples()]) if len(rows) else np.zeros((0, 2))
            with t:
                card_title("On the ground", "SIMULATED positions",
                           takeaway=f"Where {who} spent the time")
            if len(xy):
                _plot(CH.ground_heat(xy, chart_h, attack))
            return
        found = {k: ([], []) for k in sim.LAYERS}
        for _, r in rows.iterrows():
            ev = sim.events(r, role.get(r["player"], "mid"))
            for k, xy in ev.items():
                found[k][0].extend(xy.tolist())
                found[k][1].extend([f"{r['player']} · {r['round']}"] * len(xy))
        shown = {k: (np.array(found[k][0]).reshape(-1, 2), found[k][1]) for k in sim.LAYERS}
        with t:
            card_title("On the ground", "real counts · SIMULATED spots",
                       takeaway=" · ".join(f"{k} {len(found[k][0])}" for k in sim.LAYERS))
        _plot(CH.ground_events(shown, chart_h, attack))


def match_ground_card(player_df, season, game):
    """The team in one game on the ground (SIMULATED), with its running load."""
    import sim
    pdf = D.players_season(player_df, season)
    rows = pdf[(pdf["round"] == game["round"]) & (pdf["opponent"] == game["opponent"])]
    run = sim.running(pdf).merge(rows[["season", "round", "player"]],
                                 on=["season", "round", "player"])
    tab = (run.set_index("player")[["distance_km", "hsr_m", "sprints", "top_speed"]]
           .sort_values("distance_km", ascending=False).reset_index())

    def running(height):
        # Plain numbers in narrow columns: the card is about 300px wide.
        cfg = {"player": st.column_config.TextColumn("Player", pinned=True, width=96),
               "distance_km": st.column_config.NumberColumn("km", help="Distance", format="%.1f",
                                                            width=44),
               "hsr_m": st.column_config.NumberColumn(
                   "HSR", help="High-speed running (over 20 km/h), metres", format="%d", width=48),
               "sprints": st.column_config.NumberColumn("Spr", help="Sprints", format="%d", width=38),
               "top_speed": st.column_config.NumberColumn("Top", help="Top speed, km/h", format="%.1f",
                                                          width=44)}
        st.dataframe(tab, column_config=cfg, hide_index=True, row_height=26, height=height)

    take = f"Most: {tab['player'].iloc[0]} {tab['distance_km'].iloc[0]:.1f} km" if len(tab) else ""
    _ground_card("gmatch", rows, sim.roles(player_df), "the team", running=(take, running))


def player_ground_card(player_df, season, player):
    """One player's season on the ground (SIMULATED), with his running game by game."""
    import sim
    pdf = D.players_season(player_df, season)
    rows = pdf[pdf["player"] == player]
    run = sim.running(pdf).merge(rows[["season", "round", "player"]],
                                 on=["season", "round", "player"]).sort_values("game_dt")

    def running(height):
        if len(run):
            _plot(CH.running_trend(run, height))

    take = (f"Average {run['distance_km'].mean():.1f} km, {run['hsr_m'].mean():,.0f} m at high speed"
            if len(run) else "")
    _ground_card("gplayer", rows, sim.roles(player_df), player.split()[-1],
                 running=(take, running))

