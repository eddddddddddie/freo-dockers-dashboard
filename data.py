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

import pandas as pd
import streamlit as st

PLAYER_CSV = "freo_player_games.csv"
TEAM_CSV = "freo_team_games.csv"
PLAYER_EXT_CSV = "freo_player_games_ext.csv"
TEAM_EXT_CSV = "freo_team_games_ext.csv"
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
    cols = _new_cols(ext, df)
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


def record(tdf):
    wins = int((tdf["result"] == "W").sum())
    losses = int((tdf["result"] == "L").sum())
    games = len(tdf)
    win_pct = wins / games * 100 if games else 0.0
    return {
        "games": games, "wins": wins, "losses": losses, "win_pct": win_pct,
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
    ("Disposals", "avg", "freo_disposals", None, True),
    ("Goal accuracy", "acc", None, None, True),
    ("Tackles", "avg", "freo_tackles", None, True),
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


def tiles(team_df, season, baseline):
    """Values for the headline tiles, with change vs the baseline season.
    Differentials and accuracy change in absolute units (a % change of a
    number that can cross zero is meaningless); plain averages change in %."""
    cur = team_season(team_df, season)
    base = team_season(team_df, baseline) if baseline is not None else None
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
            "series": _tile_series(cur, kind, fcol, ocol).round(1).tolist(),
            "games": game_labels(cur),
        })
    return out


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


def game_strip(tdf):
    """Matrix for the game strip: one column per game, a margin row then one row
    per stat. Returns (rows, z scaled to -1..1 per row, hover text, x labels).
    Each row is scaled to its 90th percentile gap (and clipped), so one blowout
    does not wash out the rest of the row."""
    rows_spec = [("Margin", "freo_score", "opp_score")] + (
        STRIP_ROWS_EXT if has_ext(tdf) else STRIP_ROWS)
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


def running_margin(tdf):
    """Average margin at each quarter break, in wins and in losses."""
    f = pd.DataFrame(tdf["freo_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    o = pd.DataFrame(tdf["opp_qtrs"].map(_qtr_points).tolist(), columns=["Q1", "Q2", "Q3", "Q4"])
    cum = (f - o).cumsum(axis=1)
    cum["result"] = tdf["result"].values
    out = cum.groupby("result").mean()
    out["games"] = cum.groupby("result").size()
    return out
