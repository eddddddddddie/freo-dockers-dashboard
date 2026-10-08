"""Data loading and derived metrics for the Fremantle Dockers dashboard.

Reads the two CSVs produced by freo_scraper.py (AFL Tables) and, when present,
merges the advanced stats from afl_api_scraper.py (AFL match centre) onto
them. AFL Tables stays the source for every stat both sources have; the API
only adds new columns. Derived values: scoring shots, accuracy, chronological
ordering, per game averages. Team totals are used for goal accuracy because
team behinds include rushed behinds that summed player behinds do not.
"""

import os
import re

import numpy as np
import pandas as pd
import streamlit as st

PLAYER_CSV = "freo_player_games.csv"
TEAM_CSV = "freo_team_games.csv"
PLAYER_EXT_CSV = "freo_player_games_ext.csv"
TEAM_EXT_CSV = "freo_team_games_ext.csv"
OPP_PLAYER_CSV = "opp_player_games_ext.csv"   # the opposition's players in Freo games
EVENTS_CSV = "freo_score_events.csv"          # every score in every Freo game, in order
DATE_FMT = "%a %d-%b-%Y %I:%M %p"
EXT_META = ["api_round", "date_local", "freo_side", "match_id", "player_id"]
# API names for stats AFL Tables already has (AFL Tables name on the right).
# These are used for the cross-check only, never merged in.
API_DUPES = {
    "kicks": "kicks", "handballs": "handballs", "disposals": "disposals", "marks": "marks",
    "goals": "goals", "behinds": "behinds", "tackles": "tackles", "hitouts": "hitouts",
    "inside50s": "inside_50s", "rebound50s": "rebound_50s", "clangers": "clangers",
    "contested_possessions": "contested_poss", "uncontested_possessions": "uncontested_poss",
    "contested_marks": "contested_marks", "marks_inside50": "marks_inside_50",
    "one_percenters": "one_percenters", "bounces": "bounces", "goal_assists": "goal_assists",
    "frees_for": "frees_for", "frees_against": "frees_against",
    "total_clearances": "clearances", "total_possessions": None, "goal_accuracy": None,
}


def _match_games(base, ext):
    """Map each ext game to an AFL Tables game: same season and opponent, local
    dates within a day. Returns ext with a `game_key` column (the base index)."""
    b = base[["season", "opponent", "game_dt"]].copy()
    b["game_key"] = b.index
    e = ext.copy()
    e["_d"] = pd.to_datetime(e["date_local"])
    m = e.reset_index().merge(b, on=["season", "opponent"], how="left")
    m = m[(m["game_dt"].dt.normalize() - m["_d"]).abs() <= pd.Timedelta(days=1)]
    return ext.join(m.set_index("index")["game_key"])


def _new_cols(ext, base):
    """API columns worth adding: not metadata, not already in AFL Tables."""
    def stem(c):
        return c.split("_", 1)[1] if c.startswith(("freo_", "opp_")) else c
    return [c for c in ext.columns
            if c not in base.columns and c not in EXT_META and c != "game_key"
            and stem(c) not in API_DUPES and c not in ("season", "opponent", "jumper", "player")]


def _surname(name):
    return re.sub(r"[^a-z]", "", str(name).split()[-1].lower()) if str(name).strip() else ""


@st.cache_data
def load_team():
    df = pd.read_csv(TEAM_CSV)
    df["game_dt"] = pd.to_datetime(df["date"], format=DATE_FMT, errors="coerce")
    df["freo_scoring_shots"] = df["freo_goals"] + df["freo_behinds"]
    df["opp_scoring_shots"] = df["opp_goals"] + df["opp_behinds"]
    # Accuracy from team totals (includes rushed behinds). Guard divide by zero.
    df["freo_accuracy"] = df["freo_goals"] / df["freo_scoring_shots"].replace(0, pd.NA) * 100
    df["opp_accuracy"] = df["opp_goals"] / df["opp_scoring_shots"].replace(0, pd.NA) * 100
    df = df.sort_values("game_dt").reset_index(drop=True)
    if os.path.exists(TEAM_EXT_CSV):
        ext = _match_games(df, pd.read_csv(TEAM_EXT_CSV)).dropna(subset=["game_key"])
        ext = ext.drop_duplicates("game_key").set_index("game_key")
        df = df.join(ext[_new_cols(ext, df)])
    return df


@st.cache_data
def load_players():
    df = pd.read_csv(PLAYER_CSV)
    df["game_dt"] = pd.to_datetime(df["date"], format=DATE_FMT, errors="coerce")
    df["forward_threat"] = df["goals"] + df["goal_assists"]
    df = df.sort_values("game_dt").reset_index(drop=True)
    if os.path.exists(PLAYER_EXT_CSV):
        df = _merge_player_ext(df, pd.read_csv(PLAYER_EXT_CSV))
    return df


def _player_game_keys(df):
    """Give every player row the index of its game (one row per game)."""
    games = df.drop_duplicates(["season", "opponent", "game_dt"])[["season", "opponent", "game_dt"]]
    keyed = df.merge(games.assign(game_key=games.index),
                     on=["season", "opponent", "game_dt"], how="left")
    return keyed, games


def _player_join(df, ext):
    """AFL Tables player rows joined to API rows by game and jumper."""
    keyed, games = _player_game_keys(df)
    ext = _match_games(games, ext).dropna(subset=["game_key"])
    return keyed.merge(ext.rename(columns={"player": "_api_player"}),
                       on=["game_key", "jumper"], how="left", suffixes=("", "_api"))


def _merge_player_ext(df, ext):
    """Attach API player stats by game and jumper. A row only merges when the
    surnames also agree, so a jumper mix-up cannot swap two players' stats."""
    cols = _new_cols(ext, df) + ["player_id"]  # the id links to freo_squad.csv
    m = _player_join(df, ext[["season", "opponent", "date_local", "jumper", "player"] + cols])
    bad = m["_api_player"].notna() & (m["player"].map(_surname) != m["_api_player"].map(_surname))
    m.loc[bad, cols] = pd.NA
    return m.drop(columns=["_api_player", "game_key"])


def ext_check():
    """Sanity check the API merge: coverage, surname disagreements, and any
    difference on stats both sources carry. Run: python -c "import data; data.ext_check()" """
    team = load_team()
    base = pd.read_csv(PLAYER_CSV)
    base["game_dt"] = pd.to_datetime(base["date"], format=DATE_FMT, errors="coerce")
    ext = pd.read_csv(PLAYER_EXT_CSV)
    m = _player_join(base, ext)
    print(f"Team games with API stats: {team['freo_pressure_acts'].notna().sum()} of {len(team)}")
    print(f"Player rows matched by jumper: {m['_api_player'].notna().sum()} of {len(base)}")
    names = m[m["_api_player"].notna() & (m["player"].map(_surname) != m["_api_player"].map(_surname))]
    for _, r in names.iterrows():
        print(f"  surname differs, not merged: {r.season} {r['round']} #{r.jumper} {r.player} vs {r._api_player}")
    both = m[m["_api_player"].notna()]
    for api_col, col in API_DUPES.items():
        if col is None or api_col not in both.columns:
            continue
        other = api_col + "_api" if api_col == col else api_col
        diff = both[both[col] != both[other]]
        if len(diff):
            print(f"  {col}: {len(diff)} rows differ, e.g. "
                  + "; ".join(f"{r.season} {r['round']} {r.player} {r[col]} vs {r[other]}"
                              for _, r in diff.head(3).iterrows()))
    tb = team.join(_match_games(team, pd.read_csv(TEAM_EXT_CSV)).dropna(subset=["game_key"])
                   .set_index("game_key"), rsuffix="_api")
    for side in ("freo_", "opp_"):
        for api_col, col in API_DUPES.items():
            a, b = side + col if col else None, side + api_col
            if a is None or a not in tb.columns:
                continue
            b = b + "_api" if b in team.columns else b
            if b in tb.columns:
                n = int((tb[a] != tb[b]).sum())
                if n:
                    print(f"  team {a}: {n} games differ")


def data_updated():
    """When refresh.py last added data (datetime, Perth time), or None."""
    import json
    from datetime import datetime
    try:
        with open("data_refresh.json") as f:
            return datetime.fromisoformat(json.load(f)["updated"])
    except (OSError, ValueError, KeyError):
        return None


def seasons(df):
    return sorted(int(s) for s in df["season"].unique())


def baseline_season(season, all_seasons):
    """The previous season available, or None if the selected season is earliest."""
    earlier = [s for s in all_seasons if s < season]
    return max(earlier) if earlier else None


def team_season(team_df, season):
    """Games for one season, in chronological order."""
    return team_df[team_df["season"] == season].sort_values("game_dt").reset_index(drop=True)


def players_season(player_df, season):
    return player_df[player_df["season"] == season].sort_values("game_dt").reset_index(drop=True)


# ---- Game slices: the filter on the Season and Player views -----------------------
GAME_SLICES = ["All games", "Home games", "Away games", "Finals", "Wins", "Losses",
               "vs top 8", "Last 10 games"]


def slice_games(team_df, player_df, which, league=None):
    """Only the games in one slice, in every season (so a season is compared with
    the same slice of the season before). "vs top 8" uses each season's own
    home-and-away ladder (from the league file; without it, nothing is cut);
    "Last 10 games" is the last 10 of each season. Player rows follow their games."""
    if which in (None, "All games"):
        return team_df, player_df
    t = team_df
    if which in ("Home games", "Away games", "Finals"):
        keep = t["type"] == {"Home games": "Home", "Away games": "Away", "Finals": "Final"}[which]
    elif which in ("Wins", "Losses"):
        keep = t["result"] == which[0]
    elif which == "vs top 8":
        if league is None:
            return team_df, player_df
        top8 = {s: set(ladder(league, s).index[:8]) for s in t["season"].unique()
                if (league["season"] == s).any()}
        keep = pd.Series([o in top8.get(s, ()) for s, o in zip(t["season"], t["opponent"])],
                         index=t.index)
    elif which == "Last 10 games":
        keep = t.groupby("season")["game_dt"].rank(ascending=False) <= 10
    else:
        raise ValueError(which)
    games = t[keep]
    keys = games[["season", "round"]].drop_duplicates()
    players = player_df.merge(keys, on=["season", "round"])
    return games, players


def record(tdf):
    wins = int((tdf["result"] == "W").sum())
    losses = int((tdf["result"] == "L").sum())
    games = len(tdf)
    win_pct = wins / games * 100 if games else 0.0
    return {
        "games": games, "wins": wins, "losses": losses, "draws": games - wins - losses,
        "win_pct": win_pct,
        "score_for": tdf["freo_score"].mean() if games else 0.0,
        "score_against": tdf["opp_score"].mean() if games else 0.0,
        "margin": tdf["margin"].mean() if games else 0.0,
    }


def differential(tdf, freo_col, opp_col):
    """Win rate in games where Freo won vs lost the count on a stat."""
    ahead = tdf[tdf[freo_col] > tdf[opp_col]]
    behind = tdf[tdf[freo_col] < tdf[opp_col]]
    def rate(g):
        return (g["result"] == "W").mean() * 100 if len(g) else None
    return {
        "ahead_games": len(ahead), "ahead_winrate": rate(ahead),
        "behind_games": len(behind), "behind_winrate": rate(behind),
    }


# Roles for the role-leaders page: label -> (column, whether higher is the leader).
ROLES = [
    ("Ball Winner", "contested_poss"),
    ("Tackler", "tackles"),
    ("Clearances", "clearances"),
    ("Rebounder", "rebound_50s"),
    ("Spoiler", "one_percenters"),
    ("Forward Threat", "forward_threat"),
]


def role_leader_counts(pdf_season, role_col):
    """How many games each player led a given role in the season."""
    counts = {}
    for _, grp in pdf_season.groupby(["round", "opponent"], sort=False):
        idx = grp[role_col].idxmax()
        top = grp.loc[idx]
        if top[role_col] > 0:
            counts[top["player"]] = counts.get(top["player"], 0) + 1
    s = pd.Series(counts).sort_values(ascending=False)
    return s


def season_role_leaders(pdf_season):
    """The player who led each role in the most games this season."""
    out = []
    for label, col in ROLES:
        counts = role_leader_counts(pdf_season, col)
        if len(counts):
            out.append((label, counts.index[0], int(counts.iloc[0])))
        else:
            out.append((label, "-", 0))
    return out




# ---- Coach View helpers ----------------------------------------------------
TEAM_ABBR = {
    "Adelaide": "ADE", "Brisbane Lions": "BRL", "Carlton": "CAR",
    "Collingwood": "COL", "Essendon": "ESS", "Geelong": "GEE",
    "Gold Coast": "GCS", "Greater Western Sydney": "GWS", "Hawthorn": "HAW",
    "Melbourne": "MEL", "North Melbourne": "NTH", "Port Adelaide": "PTA",
    "Richmond": "RIC", "St Kilda": "STK", "Sydney": "SYD",
    "West Coast": "WCE", "Western Bulldogs": "WBD",
}


def abbr(team):
    return TEAM_ABBR.get(team, team[:3].upper())


def game_labels(tdf):
    """Short x-axis labels, e.g. 'R2 GEE'."""
    return (tdf["round"] + " " + tdf["opponent"].map(abbr)).tolist()


# Headline tiles: (label, kind, freo col, opp col, higher is better).
# kind "diff" = Freo minus opposition per game; "avg" = Freo per game average;
# "opp" = opposition per game average; "acc" = season goal accuracy.
TILES = [
    ("Clearance diff", "diff", "freo_clearances", "opp_clearances", True),
    ("Contested poss diff", "diff", "freo_contested_poss", "opp_contested_poss", True),
    ("Inside 50 diff", "diff", "freo_inside_50s", "opp_inside_50s", True),
    ("Goal accuracy", "acc", None, None, True),
    ("Rebound 50s", "avg", "freo_rebound_50s", None, None),
    ("Opp score", "opp", "opp_score", None, False),
]
# With AFL match centre stats loaded, pressure replaces rebound 50s.
# Direction is neutral: pressure acts pile up for the side without the ball, so
# out-pressuring the opposition does not track with winning in this data.
PRESSURE_TILE = ("Pressure acts diff", "diff", "freo_pressure_acts", "opp_pressure_acts", None)


def has_ext(team_df):
    return "freo_pressure_acts" in team_df.columns and team_df["freo_pressure_acts"].notna().any()


def _tile_series(tdf, kind, fcol, ocol):
    """Per game values for a tile's sparkline."""
    if kind == "diff":
        return tdf[fcol] - tdf[ocol]
    if kind == "acc":
        return tdf["freo_accuracy"]
    return tdf[fcol]


def _tile_value(tdf, kind, fcol, ocol):
    """Season value. Accuracy is pooled (total goals / total scoring shots),
    not an average of per game percentages."""
    if not len(tdf):
        return None
    if kind == "acc":
        shots = tdf["freo_scoring_shots"].sum()
        return tdf["freo_goals"].sum() / shots * 100 if shots else None
    return float(_tile_series(tdf, kind, fcol, ocol).mean())


def _compare_tiles(team_df, cur, base, series_df, highlight):
    """Tile values for `cur` compared with `base`, with a per game sparkline
    drawn from `series_df` and the point at index `highlight` accented.
    Differentials and accuracy change in absolute units (a % change of a
    number that can cross zero is meaningless); plain averages change in %."""
    out = []
    specs = [PRESSURE_TILE if has_ext(team_df) and t[0] == "Rebound 50s" else t for t in TILES]
    for label, kind, fcol, ocol, better in specs:
        val = _tile_value(cur, kind, fcol, ocol)
        bval = _tile_value(base, kind, fcol, ocol) if base is not None else None
        change, unit = None, ""
        if val is not None and bval is not None:
            if kind == "diff":
                change = val - bval
            elif kind == "acc":
                change, unit = val - bval, " pts"
            elif bval:
                change, unit = (val - bval) / abs(bval) * 100, "%"
        out.append({
            "label": label, "kind": kind, "value": val, "base": bval,
            "change": change, "unit": unit, "better": better,
            "series": _tile_series(series_df, kind, fcol, ocol).round(1).tolist(),
            "games": game_labels(series_df), "highlight": highlight,
        })
    return out


def tiles(team_df, season, baseline):
    """Headline tiles for a season, with change vs the baseline season."""
    cur = team_season(team_df, season)
    base = team_season(team_df, baseline) if baseline is not None else None
    return _compare_tiles(team_df, cur, base, cur, len(cur) - 1)


# ---- Match mode --------------------------------------------------------------
def game_choices(tdf):
    """(label, row position) for each game in a season, most recent first."""
    return [(f"{tdf['round'].iloc[i]} v {tdf['opponent'].iloc[i]} "
             f"({tdf['result'].iloc[i]} {int(tdf['margin'].iloc[i]):+d})", i)
            for i in range(len(tdf) - 1, -1, -1)]


def match_tiles(team_df, season, pos):
    """Tiles for one game (row `pos` of the season) against the season average."""
    tdf = team_season(team_df, season)
    return _compare_tiles(team_df, tdf.iloc[[pos]], tdf, tdf, pos)


# Head-to-head rows for one game: label -> column stem (freo_/opp_ prefix).
TAPE = [
    ("Disposals", "disposals"), ("Contested poss", "contested_poss"),
    ("Clearances", "clearances"), ("Inside 50s", "inside_50s"),
    ("Marks", "marks"), ("Tackles", "tackles"), ("Rebound 50s", "rebound_50s"),
    ("Scoring shots", "scoring_shots"),
]
TAPE_EXT = [
    ("Metres gained", "metres_gained"), ("Inside 50s", "inside_50s"),
    ("Contested poss", "contested_poss"), ("Centre clearances", "centre_clearances"),
    ("Stoppage clearances", "stoppage_clearances"), ("Pressure acts", "pressure_acts"),
    ("Intercepts", "intercepts"), ("Turnovers", "turnovers"),
    ("Scoring shots", "scoring_shots"),
]


def tale_of_the_tape(tdf, pos):
    """Freo vs opposition on key stats in one game, with Freo's season average
    share of each stat for comparison."""
    g = tdf.iloc[pos]
    rows = []
    for label, stem in (TAPE_EXT if has_ext(tdf) else TAPE):
        f, o = float(g[f"freo_{stem}"]), float(g[f"opp_{stem}"])
        season_share = (tdf[f"freo_{stem}"].sum()
                        / (tdf[f"freo_{stem}"] + tdf[f"opp_{stem}"]).sum() * 100)
        rows.append({"stat": label, "freo": f, "opp": o,
                     "share": f / (f + o) * 100 if f + o else 50.0,
                     "season_share": season_share,
                     "season_diff": float((tdf[f"freo_{stem}"] - tdf[f"opp_{stem}"]).mean())})
    return rows


def season_flows(tdf):
    """Running margin at each break (Q1 to Q4) in every game of the season."""
    f = tdf["freo_qtrs"].map(_qtr_points)
    o = tdf["opp_qtrs"].map(_qtr_points)
    run = pd.DataFrame([pd.Series(a) - pd.Series(b) for a, b in zip(f, o)]).cumsum(axis=1)
    run.columns = ["Q1", "Q2", "Q3", "Q4"]
    return run.astype(float)


def game_flow(tdf, pos):
    """Running margin at each break for one game, plus the season's average
    running margin in wins and in losses, for comparison."""
    run = season_flows(tdf)
    run["result"] = tdf["result"].values
    avg = run.groupby("result")[["Q1", "Q2", "Q3", "Q4"]].mean()
    return run.iloc[pos][["Q1", "Q2", "Q3", "Q4"]].astype(float), avg


def match_players(pdf_season, game_row, stats):
    """Every Freo player in one game with the chosen stats, and each value as a
    % of that player's own season average."""
    g = pdf_season[(pdf_season["round"] == game_row["round"])
                   & (pdf_season["opponent"] == game_row["opponent"])]
    have = [s for s in stats if s in pdf_season.columns]
    avgs = pdf_season.groupby("player")[have].mean()
    vals = g.set_index("player")[have]
    sort_col = "rating_points" if "rating_points" in g.columns else "disposals"
    vals = vals.loc[g.sort_values(sort_col, ascending=False)["player"]]
    pct = vals / avgs.loc[vals.index].clip(lower=0.1) * 100
    return vals, pct, avgs.loc[vals.index]


def match_leaders(pdf_season, game_row):
    """Who led each role in one game."""
    g = pdf_season[(pdf_season["round"] == game_row["round"])
                   & (pdf_season["opponent"] == game_row["opponent"])]
    return _leaders(g)


def _leaders(g):
    """One side's players in one game -> (leader of each role, goalkickers)."""
    out = []
    for label, col in ROLES:
        top = g.loc[g[col].idxmax()]
        out.append({"role": label, "player": top["player"] if top[col] > 0 else "-",
                    "value": f"{int(top[col])}", "sub": col.replace("_", " ")})
    kickers = g[g["goals"] > 0].sort_values("goals", ascending=False)
    goals = ", ".join(f"{r.player.split()[-1]} {int(r.goals)}" for r in kickers.itertuples())
    return out, goals or "none"


# The match leader roles in the AFL match centre's names (opposition players).
OPP_ROLE_COLS = {"contested_poss": "contested_possessions", "tackles": "tackles",
                 "clearances": "total_clearances", "rebound_50s": "rebound50s",
                 "one_percenters": "one_percenters"}


@st.cache_data
def load_opp_players():
    """The opposition's players in every Freo game (AFL match centre), or None."""
    if not os.path.exists(OPP_PLAYER_CSV):
        return None
    o = pd.read_csv(OPP_PLAYER_CSV)
    o["forward_threat"] = o["goals"] + o["goal_assists"]
    o["_d"] = pd.to_datetime(o["date_local"])
    return o.rename(columns={v: k for k, v in OPP_ROLE_COLS.items()})


def opp_match_leaders(game_row):
    """Who led each role for the opposition in one game (same roles as
    match_leaders), or None without the opposition's player stats."""
    o = load_opp_players()
    if o is None:
        return None
    g = o[(o["season"] == game_row["season"]) & (o["opponent"] == game_row["opponent"])
          & ((o["_d"] - game_row["game_dt"].normalize()).abs() <= pd.Timedelta(days=1))]
    return _leaders(g) if len(g) else None


# ---- Momentum: every score in a game, in order (AFL Tables' scoring progression) ----
MOMENTUM_HALF_LIFE = 4.0   # minutes: a score counts half as much 4 minutes later
RUN_GOALS = 3              # a scoring run worth naming: 3+ goals unanswered


@st.cache_data
def load_score_events():
    """freo_score_events.csv, or None if it hasn't been scraped."""
    if not os.path.exists(EVENTS_CSV):
        return None
    ev = pd.read_csv(EVENTS_CSV)
    ev["player"] = ev["player"].fillna("")
    return ev


def game_events(game_row):
    """One game's scores in order, with the game clock: (events, quarters) or None.
    events adds t (minutes from the first bounce, counting each earlier quarter's
    full length), pts (+ Freo, - opposition) and margin; quarters gives each
    quarter's start and length in minutes."""
    ev = load_score_events()
    if ev is None:
        return None
    e = ev[(ev["season"] == game_row["season"]) & (ev["round"] == game_row["round"])
           & (ev["opponent"] == game_row["opponent"])].sort_values("event").copy()
    if not len(e):
        return None
    return _with_clock(e)


def _with_clock(e):
    """Add the game clock (t, minutes from the first bounce), pts (+ the side the
    page is about, - the other) and margin to one game's scores in order, which
    have team "Freo" / "Opp" (the side the page is about / the other) and
    freo_score / opp_score. Returns (events, quarters)."""
    lens = e.groupby("quarter")["quarter_secs"].first().reindex(range(1, 5)).fillna(30 * 60) / 60
    quarters = pd.DataFrame({"start": lens.cumsum().shift(fill_value=0), "length": lens})
    e["t"] = e["quarter"].map(quarters["start"]) + e["secs"] / 60
    e["pts"] = e["kind"].map({"goal": 6, "behind": 1}) * e["team"].map({"Freo": 1, "Opp": -1})
    e["margin"] = e["freo_score"] - e["opp_score"]
    return e.reset_index(drop=True), quarters


LEAGUE_EVENTS_CSV = "league_score_events.csv"   # every score in every AFL game


@st.cache_data
def load_league_events():
    """league_score_events.csv (league_events_scraper.py), or None."""
    if not os.path.exists(LEAGUE_EVENTS_CSV):
        return None
    ev = pd.read_csv(LEAGUE_EVENTS_CSV)
    ev["player"] = ev["player"].fillna("")
    ev["_d"] = pd.to_datetime(ev["date"])
    return ev


def club_game_events(game):
    """Any club's game, from that club's side: a league_team_games row (team,
    opponent, season, date_local) -> (events, quarters) with team "Freo" meaning
    the club (the side the page is about) and "Opp" its opponent, or None.
    Matched on season, the two clubs and the date (within a day), never round."""
    ev = load_league_events()
    if ev is None:
        return None
    club, opp = game["team"], game["opponent"]
    day = pd.Timestamp(game["date_local"])
    m = ev[(ev["season"] == game["season"]) & ((ev["_d"] - day).abs() <= pd.Timedelta(days=1))
           & (((ev["home"] == club) & (ev["away"] == opp)) | ((ev["home"] == opp) & (ev["away"] == club)))]
    if not len(m):
        return None
    e = m.sort_values("event").copy()
    home = e["home"].iloc[0] == club
    e["team"] = (e["team"] == club).map({True: "Freo", False: "Opp"})
    e["freo_score"] = e["home_score"] if home else e["away_score"]
    e["opp_score"] = e["away_score"] if home else e["home_score"]
    return _with_clock(e)


def momentum(events, quarters, step=0.5):
    """Who has been scoring lately, every `step` minutes: the sum of the scores so
    far in the quarter, each weighted down by half every MOMENTUM_HALF_LIFE
    minutes. Positive is Freo. It starts at 0 each quarter: the break stops play."""
    rows = []
    for q, (start, length) in quarters.iterrows():
        in_q = events[events["quarter"] == q]
        for t in np.arange(start, start + length + 1e-9, step):
            past = in_q[in_q["t"] <= t]
            m = float((past["pts"] * 0.5 ** ((t - past["t"]) / MOMENTUM_HALF_LIFE)).sum())
            rows.append({"t": round(float(t), 3), "quarter": q, "momentum": m})
    return pd.DataFrame(rows)


def scoring_runs(events):
    """Unanswered scoring: each stretch of scores by one side with none by the
    other, biggest first (points, then goals). Columns: team, goals, behinds,
    points, start/end (minutes), q_start/q_end, first (event number it starts at)."""
    if not len(events):
        return pd.DataFrame()
    block = (events["team"] != events["team"].shift()).cumsum()
    e = events.assign(_g=(events["kind"] == "goal").astype(int),
                      _b=(events["kind"] == "behind").astype(int))
    runs = e.groupby(block).agg(
        team=("team", "first"), goals=("_g", "sum"), behinds=("_b", "sum"),
        start=("t", "first"), end=("t", "last"), q_start=("quarter", "first"),
        q_end=("quarter", "last"), first=("event", "first"))
    runs["points"] = 6 * runs["goals"] + runs["behinds"]
    return runs.sort_values(["points", "goals"], ascending=False).reset_index(drop=True)


def _clock(t, quarters):
    """Minutes from the first bounce -> 'Q3 12:05'."""
    q = int(quarters.index[quarters["start"] <= t + 1e-9].max())
    m = (t - quarters.loc[q, "start"]) * 60
    return f"Q{q} {int(m // 60)}:{int(m % 60):02d}"


def season_events(tdf):
    """Every game in tdf with its scores in order: a list of (game row, events,
    quarters) for the games that have score events."""
    out = []
    for _, g in tdf.iterrows():
        ev = game_events(g)
        if ev is not None:
            out.append((g, *ev))
    return out


QUARTER_UNITS = 30     # each quarter drawn as 30 units, so games of different lengths line up


def _norm_time(t, quarter, quarters):
    """Game minutes -> a common clock where every quarter is QUARTER_UNITS long."""
    start = quarter.map(quarters["start"]).values
    length = quarter.map(quarters["length"]).values
    return (quarter.values - 1) * QUARTER_UNITS + (t.values - start) / length * QUARTER_UNITS


@st.cache_data
def season_momentum(tdf, step=0.5):
    """Every game of a season on one clock (each quarter stretched to the same
    length): each game's margin after every score, and the season's average
    momentum at each point (data.momentum, averaged across the games).
    Returns (worms, avg) where worms is a list of dicts (round, opponent,
    result, margin, x, y) and avg a DataFrame (x, momentum, quarter)."""
    worms, curves = [], []
    grid = np.arange(0, 4 * QUARTER_UNITS + 1e-9, step)
    for g, e, q in season_events(tdf):
        x = _norm_time(e["t"], e["quarter"], q)
        worms.append({"round": g["round"], "opponent": g["opponent"], "result": g["result"],
                      "margin": int(g["margin"]), "x": [0.0] + list(x) + [4.0 * QUARTER_UNITS],
                      "y": [0] + e["margin"].astype(int).tolist() + [int(g["margin"])]})
        mom = momentum(e, q)
        mx = _norm_time(mom["t"], mom["quarter"], q)
        curve = np.full(len(grid), np.nan)
        for qq in range(1, 5):      # interpolate within each quarter (momentum restarts at each)
            sel = mom["quarter"].values == qq
            gsel = (grid >= (qq - 1) * QUARTER_UNITS) & (grid <= qq * QUARTER_UNITS)
            if sel.sum() >= 2:
                curve[gsel] = np.interp(grid[gsel], mx[sel], mom["momentum"].values[sel])
        curves.append(curve)
    if not worms:
        return [], pd.DataFrame(columns=["x", "momentum", "quarter"])
    avg = pd.DataFrame({"x": grid, "momentum": np.nanmean(np.vstack(curves), axis=0)})
    avg["quarter"] = np.minimum(avg["x"] // QUARTER_UNITS + 1, 4).astype(int)
    return worms, avg


@st.cache_data
def run_table(tdf, min_goals=RUN_GOALS):
    """Every run of min_goals+ goals unanswered in these games, in game order:
    who kicked it, its score (goals, behinds, points), when (clock, minutes long),
    the margin before and after it, and how long the other side took to score
    again (minutes of play; blank if they never did)."""
    rows = []
    for g, e, quarters in season_events(tdf):
        runs = scoring_runs(e)
        for _, r in runs[runs["goals"] >= min_goals].iterrows():
            first = int(r["first"])
            before = 0 if first == 1 else int(e.loc[e["event"] == first - 1, "margin"].iloc[0])
            last = e[(e["t"] <= r["end"]) & (e["team"] == r["team"])]["event"].max()
            after = int(e.loc[e["event"] == last, "margin"].iloc[0])
            reply = e[(e["event"] > last) & (e["team"] != r["team"])]
            rows.append({
                "season": g["season"], "round": g["round"], "opponent": g["opponent"],
                "result": g["result"], "margin_final": int(g["margin"]), "team": r["team"],
                "goals": int(r["goals"]), "behinds": int(r["behinds"]), "points": int(r["points"]),
                "starts": _clock(r["start"], quarters), "q_start": int(r["q_start"]),
                "minutes": round(float(r["end"] - r["start"]), 1),
                "margin_before": before, "margin_after": after,
                "answered_in": round(float(reply["t"].iloc[0] - r["end"]), 1) if len(reply) else None,
                "t_start": float(r["start"])})
    return pd.DataFrame(rows)


@st.cache_data
def game_run_summary(tdf):
    """One row per game: each side's biggest run (points, as goals.behinds), how
    many runs of RUN_GOALS+ goals each side kicked, Freo's biggest lead and
    deficit at any point, Freo's biggest lead in the last quarter, and how many
    times the lead changed hands."""
    rows = []
    for g, e, _ in season_events(tdf):
        runs = scoring_runs(e)
        sign = np.sign(e["margin"])
        sign = sign[sign != 0]
        before_q4 = e[e["quarter"] < 4]["margin"]       # the margin at three quarter time too
        q4 = pd.concat([before_q4.tail(1), e[e["quarter"] == 4]["margin"]])
        row = {"season": g["season"], "round": g["round"], "opponent": g["opponent"],
               "result": g["result"], "margin": int(g["margin"]),
               "max_lead": max(int(e["margin"].max()), 0),
               "max_deficit": max(-int(e["margin"].min()), 0),
               "q4_max_lead": max(int(q4.max()) if len(q4) else 0, 0),
               "lead_changes": int((sign != sign.shift()).sum() - 1) if len(sign) else 0}
        for team, key in (("Freo", "freo"), ("Opp", "opp")):
            mine = runs[runs["team"] == team]
            top = mine.iloc[0] if len(mine) else None
            row[f"{key}_best_pts"] = int(top["points"]) if top is not None else 0
            row[f"{key}_best"] = f"{int(top['goals'])}.{int(top['behinds'])}" if top is not None else "0.0"
            row[f"{key}_runs"] = int((mine["goals"] >= RUN_GOALS).sum())
        rows.append(row)
    return pd.DataFrame(rows)


@st.cache_data
def window_scoring(tdf, minutes=10):
    """Average points a game for and against in the first and last `minutes` of
    each quarter, and the rest of it (quarters run about 30 minutes)."""
    acc = {}
    games = season_events(tdf)
    for _, e, quarters in games:
        for q, (start, length) in quarters.iterrows():
            in_q = e[e["quarter"] == q]
            into = in_q["t"] - start
            part = pd.Series("Middle", index=in_q.index)
            part[into <= minutes] = f"First {minutes}"
            part[into > length - minutes] = f"Last {minutes}"
            for p, grp in in_q.groupby(part):
                f = float(grp.loc[grp["pts"] > 0, "pts"].sum())
                o = float(-grp.loc[grp["pts"] < 0, "pts"].sum())
                a = acc.setdefault((q, p), [0.0, 0.0])
                a[0] += f
                a[1] += o
    n = max(len(games), 1)
    rows = [{"quarter": f"Q{q}", "part": p, "freo_pts": f / n, "opp_pts": o / n, "net": (f - o) / n}
            for (q, p), (f, o) in acc.items()]
    order = {f"First {minutes}": 0, "Middle": 1, f"Last {minutes}": 2}
    out = pd.DataFrame(rows, columns=["quarter", "part", "freo_pts", "opp_pts", "net"])
    return out.sort_values(["quarter", "part"], key=lambda c: c.map(order) if c.name == "part" else c
                           ).reset_index(drop=True), len(games)


@st.cache_data
def momentum_test(tdf, shuffles=2000, seed=7):
    """Is momentum real? After a goal, how often is the next goal (in the same
    quarter) kicked by the same side, against chance: each game's goals shuffled
    within each quarter `shuffles` times, which keeps the score and how many goals
    each side kicked in each quarter. Returns pairs, observed share, the chance
    share (mean of the shuffles) and its 5th to 95th percentile, and a one-sided
    p-value (share of shuffles at or above the observed)."""
    rng = np.random.default_rng(seed)
    seqs = []
    for _, e, _ in season_events(tdf):
        goals = e[e["kind"] == "goal"]
        for _, grp in goals.groupby("quarter"):
            if len(grp) >= 2:
                seqs.append((grp["team"] == "Freo").to_numpy())
    pairs = sum(len(x) - 1 for x in seqs)
    if not pairs:
        return None
    same = sum(int((x[1:] == x[:-1]).sum()) for x in seqs)
    sims = np.zeros(shuffles)
    for x in seqs:
        m = np.tile(x, (shuffles, 1))
        m = rng.permuted(m, axis=1)
        sims += (m[:, 1:] == m[:, :-1]).sum(axis=1)
    obs = same / pairs
    sims = sims / pairs
    return {"pairs": pairs, "same": same, "observed": obs, "chance": float(sims.mean()),
            "lo": float(np.percentile(sims, 5)), "hi": float(np.percentile(sims, 95)),
            "p": float((sims >= obs - 1e-12).mean())}


# ---- Quarter-time check ---------------------------------------------------------
BREAKS = {"Quarter time": "Q1", "Half time": "Q2", "Three quarter time": "Q3"}


def break_margins(team_df):
    """Every game with Freo's running margin at each break and the result."""
    f = team_df["freo_qtrs"].map(_qtr_points)
    o = team_df["opp_qtrs"].map(_qtr_points)
    run = pd.DataFrame([pd.Series(a) - pd.Series(b) for a, b in zip(f, o)],
                       index=team_df.index).cumsum(axis=1)
    run.columns = ["Q1", "Q2", "Q3", "Q4"]
    cols = ["season", "round", "type", "opponent", "venue", "result", "margin"]
    return team_df[cols].join(run)


def similar_positions(team_df, brk, margin, window, seasons=None, game_type=None):
    """Games where Freo's margin at a break was within `window` points of
    `margin`. Returns (matching games, summary dict)."""
    q = BREAKS[brk]
    bm = break_margins(team_df)
    if seasons:
        bm = bm[bm["season"].isin(seasons)]
    if game_type:
        bm = bm[bm["type"] == game_type]
    m = bm[(bm[q] - margin).abs() <= window].copy()
    m["after_break"] = m["Q4"] - m[q]   # net scoring from the break to the siren
    w, lo = int((m["result"] == "W").sum()), int((m["result"] == "L").sum())
    return m.sort_values(q), {
        "games": len(m), "wins": w, "losses": lo, "draws": len(m) - w - lo,
        "win_pct": w / len(m) * 100 if len(m) else None,
        "avg_final": m["margin"].mean() if len(m) else None,
        "avg_after": m["after_break"].mean() if len(m) else None,
        "pool": len(bm), "col": q,
    }


def _qtr_points(qtrs):
    """'3.1 8.4 13.8 16.14' (cumulative goals.behinds) -> points in each quarter."""
    cum = [6 * int(g) + int(b) for g, b in (q.split(".") for q in qtrs.split())]
    return [c - p for c, p in zip(cum, [0] + cum[:-1])]


def quarter_pattern(tdf):
    """Average points for and against in each quarter, and quarters won."""
    f = pd.DataFrame(tdf["freo_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    o = pd.DataFrame(tdf["opp_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    return pd.DataFrame({
        "quarter": f.columns,
        "freo": f.mean().values, "opp": o.mean().values,
        "margin": (f - o).mean().values,
        "won": (f > o).sum().values, "games": len(f),
    })


# Stats for the "where we win" card: label -> (freo col, opp col).
WIN_STATS = [
    ("Clearances", "freo_clearances", "opp_clearances"),
    ("Contested poss", "freo_contested_poss", "opp_contested_poss"),
    ("Inside 50s", "freo_inside_50s", "opp_inside_50s"),
    ("Tackles", "freo_tackles", "opp_tackles"),
    ("Marks", "freo_marks", "opp_marks"),
    ("Disposals", "freo_disposals", "opp_disposals"),
]


# With AFL match centre stats: clearances split centre vs stoppage, plus
# pressure acts and metres gained.
WIN_STATS_EXT = [
    ("Centre clearances", "freo_centre_clearances", "opp_centre_clearances"),
    ("Stoppage clearances", "freo_stoppage_clearances", "opp_stoppage_clearances"),
    ("Contested poss", "freo_contested_poss", "opp_contested_poss"),
    ("Inside 50s", "freo_inside_50s", "opp_inside_50s"),
    ("Pressure acts", "freo_pressure_acts", "opp_pressure_acts"),
    ("Metres gained", "freo_metres_gained", "opp_metres_gained"),
    ("Disposals", "freo_disposals", "opp_disposals"),
]


def win_conditions(tdf):
    rows = []
    for label, fcol, ocol in (WIN_STATS_EXT if has_ext(tdf) else WIN_STATS):
        d = differential(tdf, fcol, ocol)
        rows.append({"stat": label, **d})
    return pd.DataFrame(rows)


def what_wins(tdf):
    """What wins us games, one row per stat: the win rate when Freo won the count
    and when the opposition did (and the swing between them), plus how the
    count's differential tracks the final margin (Pearson r, association only).
    Sorted by the swing."""
    wc = win_conditions(tdf).dropna(subset=["ahead_winrate", "behind_winrate"]).copy()
    wc["swing"] = wc["ahead_winrate"] - wc["behind_winrate"]
    r = margin_drivers(tdf).set_index("stat")["r"]
    wc["r"] = wc["stat"].map(r)
    return wc.sort_values("swing", ascending=False).reset_index(drop=True)


def role_leaders(pdf_season):
    """Per role: the player who led it in the most games, how many games,
    and their per game average for that stat."""
    games = pdf_season.groupby(["round", "opponent"]).ngroups
    out = []
    for label, col in ROLES:
        counts = role_leader_counts(pdf_season, col)
        if not len(counts):
            out.append({"role": label, "player": "-", "led": 0, "games": games, "avg": None})
            continue
        name = counts.index[0]
        avg = pdf_season.loc[pdf_season["player"] == name, col].mean()
        out.append({"role": label, "player": name, "led": int(counts.iloc[0]),
                    "games": games, "avg": avg})
    return out


def top_goalkickers(pdf_season, n=6):
    g = pdf_season.groupby("player")["goals"].agg(["sum", "count"])
    g = g[g["sum"] > 0].sort_values(["sum", "count"], ascending=[False, True]).head(n)
    return g.rename(columns={"sum": "goals", "count": "games"})


def form_matrix(pdf_season, col, n_games=6, n_players=12, min_games=5):
    """Last n games of the season for the top players on one stat.

    Rows are the n_players with the best season per game average (min_games
    played) who played at least one of the last n games. Returns (values,
    season averages, game labels); values are NaN where the player did not play.
    """
    order = pdf_season.drop_duplicates(["round", "opponent"]).sort_values("game_dt")
    recent = order.tail(n_games)
    labels = (recent["round"] + " " + recent["opponent"].map(abbr)).tolist()
    stats = pdf_season.groupby("player")[col].agg(["mean", "count"])
    stats = stats[stats["count"] >= min_games]
    rec = pdf_season[pdf_season["round"].isin(recent["round"])]
    stats = stats[stats.index.isin(rec["player"])]
    top = stats.sort_values("mean", ascending=False).head(n_players)
    vals = (rec[rec["player"].isin(top.index)]
            .pivot_table(index="player", columns="round", values=col, aggfunc="sum")
            .reindex(index=top.index, columns=recent["round"]))
    vals.columns = labels
    return vals, top["mean"], labels


# ---- Game strip, margin drivers, running margin ------------------------------
# Rows of the game strip: label -> (freo col, opp col). A row is shaded by the
# differential, scaled to that row's biggest gap in the season.
STRIP_ROWS = [
    ("Inside 50s", "freo_inside_50s", "opp_inside_50s"),
    ("Contested poss", "freo_contested_poss", "opp_contested_poss"),
    ("Clearances", "freo_clearances", "opp_clearances"),
    ("Disposals", "freo_disposals", "opp_disposals"),
    ("Tackles", "freo_tackles", "opp_tackles"),
]
STRIP_ROWS_EXT = [
    ("Metres gained", "freo_metres_gained", "opp_metres_gained"),
    ("Inside 50s", "freo_inside_50s", "opp_inside_50s"),
    ("Contested poss", "freo_contested_poss", "opp_contested_poss"),
    ("Centre clearances", "freo_centre_clearances", "opp_centre_clearances"),
    ("Stoppage clearances", "freo_stoppage_clearances", "opp_stoppage_clearances"),
    ("Pressure acts", "freo_pressure_acts", "opp_pressure_acts"),
]


def game_strip(tdf, runs=False):
    """Matrix for the game strip: one column per game, a margin row then one row
    per stat. Returns (rows, z scaled to -1..1 per row, hover text, x labels).
    Each row is scaled to its 90th percentile gap (and clipped), so one blowout
    does not wash out the rest of the row. runs: add a "Biggest run" row (each
    side's biggest unanswered run in points, from the scores in order)."""
    rows_spec = [("Margin", "freo_score", "opp_score")] + (
        STRIP_ROWS_EXT if has_ext(tdf) else STRIP_ROWS)
    if runs and load_score_events() is not None:
        summary = game_run_summary(tdf).set_index(["season", "round"])
        key = pd.MultiIndex.from_arrays([tdf["season"], tdf["round"]])
        tdf = tdf.copy().assign(freo_best_run=summary["freo_best_pts"].reindex(key).fillna(0).values,
                         opp_best_run=summary["opp_best_pts"].reindex(key).fillna(0).values)
        rows_spec = rows_spec + [("Biggest run", "freo_best_run", "opp_best_run")]
    labels = game_labels(tdf)
    rows, z, hover = [], [], []
    for label, fcol, ocol in rows_spec:
        diff = tdf[fcol] - tdf[ocol]
        top = diff.abs().quantile(0.9) or diff.abs().max() or 1
        rows.append(label)
        z.append((diff / top).clip(-1, 1).round(3).tolist())
        hover.append([
            f"<b>{lbl}</b> vs {opp} ({res})<br>{label}: Freo {f:,.0f}, opp {o:,.0f} ({d:+,.0f})"
            for lbl, opp, res, f, o, d in zip(labels, tdf["opponent"], tdf["result"],
                                               tdf[fcol], tdf[ocol], diff)])
    return rows, z, hover, labels


# Differentials tested against margin: label -> column stem (freo_/opp_ prefix).
DRIVERS = [
    ("Inside 50s", "inside_50s"), ("Disposals", "disposals"),
    ("Contested poss", "contested_poss"), ("Marks", "marks"),
    ("Clearances", "clearances"), ("Tackles", "tackles"),
    ("Rebound 50s", "rebound_50s"), ("Clangers", "clangers"),
    ("Frees for", "frees_for"),
]
DRIVERS_EXT = [
    ("Metres gained", "metres_gained"), ("Inside 50s", "inside_50s"),
    ("Disposals", "disposals"), ("Turnovers", "turnovers"),
    ("Intercepts", "intercepts"), ("Contested poss", "contested_poss"),
    ("Pressure acts", "pressure_acts"), ("Marks", "marks"),
    ("Centre clearances", "centre_clearances"), ("Tackles", "tackles"),
    ("Stoppage clearances", "stoppage_clearances"),
]


def margin_drivers(tdf):
    """Pearson correlation of each Freo-minus-opposition differential with the
    final margin, strongest first. Association only, not cause."""
    rows = []
    for label, stem in (DRIVERS_EXT if has_ext(tdf) else DRIVERS):
        diff = tdf[f"freo_{stem}"] - tdf[f"opp_{stem}"]
        rows.append({"stat": label, "r": diff.corr(tdf["margin"]), "games": len(tdf)})
    out = pd.DataFrame(rows).dropna()
    return out.reindex(out["r"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def quarter_strip(tdf):
    """The quarters game by game, for the game-strip style heat strip: rows Q1-Q4,
    one column per game, each cell Freo's margin in that quarter (that quarter
    only, not running), scaled to the 90th percentile gap. Returns (rows, z,
    hover, labels), as game_strip does."""
    qs = ["Q1", "Q2", "Q3", "Q4"]
    f = pd.DataFrame(tdf["freo_qtrs"].map(_qtr_points).tolist(), columns=qs, index=tdf.index)
    o = pd.DataFrame(tdf["opp_qtrs"].map(_qtr_points).tolist(), columns=qs, index=tdf.index)
    d = f - o
    top = d.abs().stack().quantile(0.9) or 1
    labels = game_labels(tdf)
    hover = [[f"<b>{lbl}</b> v {opp} ({res})<br>{q}: Freo {fp} to {op} ({dd:+d})"
              for lbl, opp, res, fp, op, dd in zip(labels, tdf["opponent"], tdf["result"],
                                                   f[q], o[q], d[q])] for q in qs]
    return qs, [(d[q] / top).clip(-1, 1).round(3).tolist() for q in qs], hover, labels


def driver_points(tdf, stat):
    """One differential (a margin_drivers stat label) against the final margin,
    game by game, with the correlation and a least-squares line."""
    stem = dict(DRIVERS_EXT if has_ext(tdf) else DRIVERS)[stat]
    diff = tdf[f"freo_{stem}"] - tdf[f"opp_{stem}"]
    pts = pd.DataFrame({"label": game_labels(tdf), "round": tdf["round"].values,
                        "opponent": tdf["opponent"].values, "result": tdf["result"].values,
                        "diff": diff.values, "margin": tdf["margin"].values})
    ok = pts.dropna(subset=["diff", "margin"])
    slope, icept = (np.polyfit(ok["diff"], ok["margin"], 1) if len(ok) >= 3 else (0.0, 0.0))
    ahead = ok[ok["diff"] > 0]
    return pts, {"r": ok["diff"].corr(ok["margin"]), "slope": slope, "intercept": icept,
                 "games": len(ok), "ahead": len(ahead),
                 "ahead_won": int((ahead["result"] == "W").sum())}


def running_margin(tdf):
    """Average margin at each quarter break, in wins and in losses."""
    f = pd.DataFrame(tdf["freo_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    o = pd.DataFrame(tdf["opp_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    cum = (f - o).cumsum(axis=1)
    cum["result"] = tdf["result"].values
    out = cum.groupby("result").mean()
    out["games"] = cum.groupby("result").size()
    return out


# ---- Deep dives ------------------------------------------------------------
def player_averages(pdf_season, cols, min_games=5):
    """Per game averages for each player with at least min_games this season."""
    have = [c for c in cols if c in pdf_season.columns]
    g = pdf_season.groupby("player")
    out = g[have].mean()
    out["games"] = g.size()
    return out[out["games"] >= min_games]


def year_on_year(player_df, s0, s1, col, n=15, min_games=8):
    """Per game average of one stat in two seasons, for players with min_games
    in both. The n with the highest s1 value, sorted by change."""
    a = player_averages(players_season(player_df, s0), [col], min_games)[col]
    b = player_averages(players_season(player_df, s1), [col], min_games)[col]
    both = pd.DataFrame({"before": a, "after": b}).dropna()
    both = both.sort_values("after", ascending=False).head(n)
    both["change"] = both["after"] - both["before"]
    return both.sort_values("change", ascending=False)


def opponent_grid(team_df):
    """Every game against each opponent, both seasons, toughest first (lowest
    average margin). Returns [(opponent, record, avg margin, {season: [games]})]."""
    out = []
    for opp, g in team_df.sort_values("game_dt").groupby("opponent"):
        w, lo = int((g["result"] == "W").sum()), int((g["result"] == "L").sum())
        games = {int(s): gs.to_dict("records") for s, gs in g.groupby("season")}
        out.append({"opponent": opp, "wins": w, "losses": lo, "draws": len(g) - w - lo,
                    "avg_margin": g["margin"].mean(), "games": games})
    return sorted(out, key=lambda r: r["avg_margin"])


# ---- League data and the opponent scout report ---------------------------------
LEAGUE_CSV = "league_team_games.csv"
# Stats compared across the league: label -> (column, higher is better).
SCOUT_STATS = [
    ("Inside 50s", "inside50s", True), ("Contested poss", "contested_possessions", True),
    ("Centre clearances", "centre_clearances", True),
    ("Stoppage clearances", "stoppage_clearances", True),
    ("Metres gained", "metres_gained", True), ("Tackles", "tackles", True),
    ("Pressure acts", "pressure_acts", True), ("Intercepts", "intercepts", True),
    ("Turnovers", "turnovers", False), ("Scoring shots", "scoring_shots", True),
    ("Points against", "score_against", False),
]


@st.cache_data
def load_league():
    """Every club's games, one row per team per match, with the opposition's
    totals alongside (opp_*) and differentials (diff_*). None if not scraped."""
    if not os.path.exists(LEAGUE_CSV):
        return None
    lg = pd.read_csv(LEAGUE_CSV)
    lg["scoring_shots"] = lg["goals_for"] + lg["behinds_for"]
    stats = [c for c in lg.columns if c not in (
        "season", "api_round", "round_number", "is_final", "date_local", "utc_date", "match_id",
        "venue", "team", "opponent", "is_home", "result", "margin") and not c.startswith("q")
        and not c.endswith("_against") and not c.endswith("_for")] + [
        "goals_for", "behinds_for"]
    stats = list(dict.fromkeys(stats))  # scoring_shots is already in the list
    opp = lg[["match_id", "team"] + stats].rename(
        columns={"team": "opponent", **{c: f"opp_{c}" for c in stats}})
    lg = lg.merge(opp, on=["match_id", "opponent"], how="left")
    diffs = pd.DataFrame({f"diff_{c}": lg[c] - lg[f"opp_{c}"] for c in stats})
    extra = pd.DataFrame({
        "win": (lg["result"] == "W").astype(int),
        "accuracy": lg["goals_for"] / lg["scoring_shots"].replace(0, pd.NA) * 100,
        "game_dt": pd.to_datetime(lg["date_local"])})
    lg = pd.concat([lg, diffs, extra], axis=1)  # one concat, not a column at a time
    return lg.sort_values("game_dt").reset_index(drop=True)


def ladder(lg, season):
    """Ladder from the home and away results: 4 points a win, 2 a draw,
    percentage = points for / points against x 100."""
    g = lg[(lg["season"] == season) & (~lg["is_final"])]
    t = g.groupby("team").agg(played=("result", "size"), wins=("win", "sum"),
                              draws=("result", lambda r: int((r == "D").sum())),
                              pf=("score_for", "sum"), pa=("score_against", "sum"))
    t["losses"] = t["played"] - t["wins"] - t["draws"]
    t["points"] = 4 * t["wins"] + 2 * t["draws"]
    t["pct"] = t["pf"] / t["pa"] * 100
    t = t.sort_values(["points", "pct"], ascending=False)
    t["position"] = range(1, len(t) + 1)
    return t


def team_ranks(lg, season):
    """Per game average of each scout stat for every club, and its league rank
    (1 = best, taking 'higher is better' into account)."""
    g = lg[lg["season"] == season]
    avg = g.groupby("team")[[c for _, c, _ in SCOUT_STATS]].mean()
    ranks = pd.DataFrame({c: avg[c].rank(ascending=not better, method="min")
                          for _, c, better in SCOUT_STATS})
    return avg, ranks


def scout_tiles(lg, team, season, freo="Fremantle"):
    """Headline numbers for a club: value, league rank, and Freo's value."""
    g = lg[lg["season"] == season]
    per = g.groupby("team")
    specs = [
        ("Avg margin", per["margin"].mean(), True, "{:+.1f}"),
        ("Inside 50 diff", per["diff_inside50s"].mean(), True, "{:+.1f}"),
        ("Contested poss diff", per["diff_contested_possessions"].mean(), True, "{:+.1f}"),
        ("Clearance diff", per["diff_total_clearances"].mean(), True, "{:+.1f}"),
        ("Metres gained diff", per["diff_metres_gained"].mean(), True, "{:+.0f}"),
        ("Points against", per["score_against"].mean(), False, "{:.1f}"),
    ]
    out = []
    for label, series, better, fmt in specs:
        rank = series.rank(ascending=better is False, method="min") if better is not None else None
        out.append({"label": label, "value": fmt.format(series[team]),
                    "freo": fmt.format(series[freo]) if freo in series else "-",
                    "rank": int(rank[team]) if rank is not None else None,
                    "series": g[g["team"] == team]["margin"].tolist()})
    return out


def scout_win_conditions(lg, team, season):
    """Win rate for a club when it wins vs loses the count on each stat."""
    g = lg[(lg["season"] == season) & (lg["team"] == team)]
    rows = []
    for label, col in [("Centre clearances", "centre_clearances"),
                       ("Stoppage clearances", "stoppage_clearances"),
                       ("Contested poss", "contested_possessions"), ("Inside 50s", "inside50s"),
                       ("Pressure acts", "pressure_acts"), ("Metres gained", "metres_gained"),
                       ("Disposals", "disposals")]:
        ahead, behind = g[g[f"diff_{col}"] > 0], g[g[f"diff_{col}"] < 0]
        rows.append({"stat": label, "ahead_games": len(ahead), "behind_games": len(behind),
                     "ahead_winrate": ahead["win"].mean() * 100 if len(ahead) else None,
                     "behind_winrate": behind["win"].mean() * 100 if len(behind) else None})
    return pd.DataFrame(rows)


def scout_quarters(lg, team, season):
    """A club's average points for and against in each quarter."""
    g = lg[(lg["season"] == season) & (lg["team"] == team)].dropna(subset=["q4_for"])
    cum_f = g[[f"q{i}_for" for i in range(1, 5)]].to_numpy()
    cum_a = g[[f"q{i}_against" for i in range(1, 5)]].to_numpy()
    f = pd.DataFrame(cum_f - pd.DataFrame(cum_f).shift(axis=1, fill_value=0).to_numpy(),
                     columns=["Q1", "Q2", "Q3", "Q4"])
    a = pd.DataFrame(cum_a - pd.DataFrame(cum_a).shift(axis=1, fill_value=0).to_numpy(),
                     columns=["Q1", "Q2", "Q3", "Q4"])
    return pd.DataFrame({"quarter": f.columns, "freo": f.mean().values, "opp": a.mean().values,
                         "margin": (f - a).mean().values, "won": (f > a).sum().values,
                         "games": len(f)})


def head_to_head(team_df, team):
    """Every Freo game against a club, both seasons, newest first."""
    g = team_df[team_df["opponent"] == team].sort_values("game_dt", ascending=False)
    cols = ["season", "round", "type", "venue", "result", "freo_score", "opp_score", "margin",
            "freo_inside_50s", "opp_inside_50s", "freo_contested_poss", "opp_contested_poss"]
    return g[[c for c in cols if c in g.columns]]


# ---- Player profile -----------------------------------------------------------
PLAYER_TILES = [
    ("Disposals", "disposals"), ("Contested poss", "contested_poss"),
    ("Clearances", "clearances"), ("Metres gained", "metres_gained"),
    ("Tackles", "tackles"), ("Goals + assists", "forward_threat"),
]
# Stats on the squad-rank card: label -> column (higher is better for all).
PROFILE_STATS = [
    ("Disposals", "disposals"), ("Contested poss", "contested_poss"),
    ("Uncontested poss", "uncontested_poss"), ("Clearances", "clearances"),
    ("Inside 50s", "inside_50s"), ("Metres gained", "metres_gained"),
    ("Score involvements", "score_involvements"), ("Tackles", "tackles"),
    ("Pressure acts", "pressure_acts"), ("Intercepts", "intercepts"),
    ("Rebound 50s", "rebound_50s"), ("Goals", "goals"),
    ("Hitouts", "hitouts"), ("Marks", "marks"),
]
MIN_GAMES = 5


def player_list(pdf_season):
    """Players in a season, most games first (then by name)."""
    g = pdf_season.groupby("player").size()
    return sorted(g.index, key=lambda p: (-g[p], p))


def player_tiles(player_df, player, season, baseline):
    """Per game average of each tile stat for one player, with squad rank
    (players with MIN_GAMES+ games), change vs the baseline season, and a per
    game series for the sparkline."""
    cur = players_season(player_df, season)
    me = cur[cur["player"] == player].sort_values("game_dt")
    base = players_season(player_df, baseline) if baseline is not None else None
    squad = cur.groupby("player").filter(lambda g: len(g) >= MIN_GAMES)
    out = []
    for label, col in PLAYER_TILES:
        if col not in cur.columns:
            continue
        val = me[col].mean()
        avgs = squad.groupby("player")[col].mean()
        rank = int(avgs.rank(ascending=False, method="min")[player]) if player in avgs else None
        bval = None
        if base is not None:
            b = base[base["player"] == player]
            bval = b[col].mean() if len(b) >= MIN_GAMES else None
        change = (val - bval) / abs(bval) * 100 if bval else None
        out.append({"label": label, "kind": "avg", "value": val, "base": bval, "change": change,
                    "unit": "%" if change is not None else "", "better": True,
                    "series": me[col].round(1).tolist(),
                    "games": (me["round"] + " " + me["opponent"].map(abbr)).tolist(),
                    "highlight": len(me) - 1, "rank": rank, "squad": len(avgs)})
    return out


def player_squad_ranks(pdf_season, player):
    """The player's per game average and squad rank on each profile stat."""
    squad = pdf_season.groupby("player").filter(lambda g: len(g) >= MIN_GAMES)
    rows = []
    for label, col in PROFILE_STATS:
        if col not in squad.columns:
            continue
        avgs = squad.groupby("player")[col].mean()
        if player not in avgs:
            continue
        rows.append({"stat": label, "value": avgs[player],
                     "rank": int(avgs.rank(ascending=False, method="min")[player]),
                     "squad": len(avgs)})
    return pd.DataFrame(rows)


def compare_players(pdf_season, a, b, last_n=5):
    """Two players side by side on every profile stat: per game average, the
    last `last_n` games, and squad rank (players with MIN_GAMES+ games; None if
    the player has fewer). One row per stat."""
    squad = pdf_season.groupby("player").filter(lambda g: len(g) >= MIN_GAMES)
    rows = []
    for label, col in [("Goals + assists", "forward_threat")] + PROFILE_STATS:
        if col not in pdf_season.columns:
            continue
        avgs = squad.groupby("player")[col].mean()
        ranks = avgs.rank(ascending=False, method="min")
        row = {"stat": label, "col": col, "squad": len(avgs)}
        for key, who in (("a", a), ("b", b)):
            me = pdf_season[pdf_season["player"] == who].sort_values("game_dt")
            row[f"avg_{key}"] = me[col].mean() if len(me) else None
            row[f"last_{key}"] = me[col].tail(last_n).mean() if len(me) else None
            row[f"rank_{key}"] = int(ranks[who]) if who in ranks else None
        rows.append(row)
    return pd.DataFrame(rows)


def games_together(pdf_season, a, b):
    """The games both players played: count and Freo's record in them."""
    ga = pdf_season[pdf_season["player"] == a][["season", "round", "result"]]
    gb = pdf_season[pdf_season["player"] == b][["season", "round"]]
    both = ga.merge(gb, on=["season", "round"])
    wins, losses = int((both["result"] == "W").sum()), int((both["result"] == "L").sum())
    return {"games": len(both), "wins": wins, "losses": losses, "draws": len(both) - wins - losses,
            "games_a": len(ga), "games_b": len(gb)}


def player_log(pdf_season, player):
    """Every game one player played in a season, most recent first."""
    return pdf_season[pdf_season["player"] == player].sort_values("game_dt", ascending=False)


# ---- Player details (freo_squad.csv) ---------------------------------------------
SQUAD_CSV = "freo_squad.csv"
POSITIONS = {"MIDFIELDER": "Midfielder", "MIDFIELDER_FORWARD": "Midfielder / forward",
             "MEDIUM_DEFENDER": "Defender", "KEY_DEFENDER": "Key defender",
             "MEDIUM_FORWARD": "Forward", "KEY_FORWARD": "Key forward", "RUCK": "Ruck"}


@st.cache_data
def load_squad():
    if not os.path.exists(SQUAD_CSV):
        return None
    return pd.read_csv(SQUAD_CSV)


def player_details(player_df, player, season, today=None):
    """Age, height, position, Champion Data id and the player's best squad
    ranking this season (e.g. 1st for metres gained). Missing parts are None."""
    me = player_df[(player_df["player"] == player)]
    pid = me["player_id"].dropna().mode().iloc[0] if "player_id" in me and me["player_id"].notna().any() else None
    out = {"player_id": pid, "age": None, "height_cm": None, "position": None, "top": None}
    squad = load_squad()
    if squad is not None and pid is not None:
        rows = squad[squad["player_id"] == pid].sort_values("season")
        row = rows[rows["season"] == season]
        row = (row if len(row) else rows).iloc[-1] if len(rows) else None
        if row is not None:
            dob = pd.to_datetime(row["date_of_birth"], errors="coerce")
            now = pd.Timestamp(today) if today else pd.Timestamp.now()
            if pd.notna(dob):
                out["age"] = int(now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day)))
            out["height_cm"] = int(row["height_cm"]) if pd.notna(row["height_cm"]) else None
            out["position"] = POSITIONS.get(row["position"], str(row["position"]).title())
    ranks = player_squad_ranks(players_season(player_df, season), player)
    if len(ranks):
        best = ranks.loc[ranks["rank"].idxmin()]      # ties go to the earlier stat in the list
        out["top"] = {"stat": best["stat"], "rank": int(best["rank"]), "squad": int(best["squad"]),
                      "value": float(best["value"])}
    return out
