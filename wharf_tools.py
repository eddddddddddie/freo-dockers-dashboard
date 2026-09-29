"""Data tools Wharf-ai calls to compute every number it quotes.

Each tool is a small, fixed pandas query over the loaded CSVs: no model-written
code runs. Inputs are validated here (tool inputs stream eagerly, so the API
does not validate them), bad input comes back as an error the model can fix,
and results are compact CSV capped at MAX_ROWS rows.
"""

import pandas as pd

import data as D

MAX_ROWS = 60
AGGS = ["mean", "sum", "median", "min", "max", "std", "count"]
TEAM_GROUPS = ["result", "type", "opponent", "season", "venue"]
PLAYER_GROUPS = ["season", "result", "type", "opponent"]


class ToolError(ValueError):
    """Bad tool input: returned to the model as an is_error result."""


# ---- data -------------------------------------------------------------------
def _team():
    t = D.load_team().copy()
    t["win"] = (t["result"] == "W").astype(int)
    for stem in team_stems(t):
        t[f"diff_{stem}"] = t[f"freo_{stem}"] - t[f"opp_{stem}"]
    return t


def _players():
    return D.load_players()


def team_stems(t=None):
    """Stats with both a freo_ and an opp_ column (differentials exist for these)."""
    t = D.load_team() if t is None else t
    cols = set(t.columns)
    return sorted(c[5:] for c in cols
                  if c.startswith("freo_") and f"opp_{c[5:]}" in cols
                  and pd.api.types.is_numeric_dtype(t[c]))


def player_stats():
    p = _players()
    skip = {"season", "jumper", "pct_played_api"}
    return sorted(c for c in p.columns
                  if pd.api.types.is_numeric_dtype(p[c]) and c not in skip)


# ---- helpers ----------------------------------------------------------------
def _filter(df, f):
    f = f or {}
    if f.get("season") not in (None, "all"):
        df = df[df["season"] == int(f["season"])]
    if f.get("result"):
        df = df[df["result"] == str(f["result"]).upper()[:1]]
    if f.get("type"):
        df = df[df["type"].str.lower() == str(f["type"]).lower()]
    if f.get("opponent"):
        opp = _match_one(str(f["opponent"]), df["opponent"].unique(), "opponent")
        df = df[df["opponent"] == opp]
    if f.get("rounds"):
        df = df[df["round"].isin([str(r).upper() for r in f["rounds"]])]
    if f.get("min_margin") is not None:
        df = df[df["margin"] >= float(f["min_margin"])]
    if f.get("max_margin") is not None:
        df = df[df["margin"] <= float(f["max_margin"])]
    return df


def _match_one(name, options, what):
    options = [str(o) for o in options]
    exact = [o for o in options if o.lower() == name.lower()]
    if exact:
        return exact[0]
    part = [o for o in options if name.lower() in o.lower()]
    if len(part) == 1:
        return part[0]
    if not part:
        raise ToolError(f"No {what} matches '{name}'.")
    raise ToolError(f"'{name}' matches several {what}s: {', '.join(part[:10])}. Be more specific.")


def _check_cols(cols, allowed, what):
    if not cols:
        raise ToolError(f"Give at least one {what}.")
    bad = [c for c in cols if c not in allowed]
    if bad:
        raise ToolError(f"Unknown {what}: {', '.join(bad)}. Valid {what}s are listed in the "
                        "system prompt.")


def _team_metrics():
    t = _team()
    return set(t.select_dtypes("number").columns)


def _csv(df, note=""):
    total = len(df)
    df = df.head(MAX_ROWS)
    out = df.round(2).to_csv(index=False).strip()
    extra = f"\n({total} rows, first {MAX_ROWS} shown)" if total > MAX_ROWS else f"\n({total} rows)"
    return (note + "\n" if note else "") + out + extra


def _games_note(df):
    return f"Games matched: {len(df)}."


# ---- tools ------------------------------------------------------------------
def team_games(filters=None, metrics=None, sort_by=None, descending=True, limit=30):
    t = _filter(_team(), filters)
    metrics = metrics or ["margin"]
    _check_cols(metrics, _team_metrics(), "team metric")
    cols = ["season", "round", "type", "opponent", "venue", "result"] + [m for m in metrics]
    out = t[cols]
    if sort_by:
        _check_cols([sort_by], set(out.columns), "sort column")
        out = out.sort_values(sort_by, ascending=not descending)
    return _csv(out.head(max(1, min(int(limit), MAX_ROWS))), _games_note(t))


def team_aggregate(metrics, agg="mean", group_by=None, filters=None):
    t = _filter(_team(), filters)
    _check_cols(metrics, _team_metrics(), "team metric")
    if agg not in AGGS:
        raise ToolError(f"agg must be one of {AGGS}.")
    if group_by:
        _check_cols([group_by], TEAM_GROUPS, "group_by")
        g = t.groupby(group_by)
        out = g[metrics].agg(agg)
        out.insert(0, "games", g.size())
    else:
        g = None
        out = t[metrics].agg(agg).to_frame().T
        out.insert(0, "games", len(t))
    note = f"{agg} per game unless agg is sum/count. "
    # Goal accuracy is pooled (total goals / total scoring shots), matching the
    # dashboard, never an average of per-game percentages.
    if agg == "mean":
        for side in ("freo", "opp"):
            col = f"{side}_accuracy"
            if col in metrics:
                src = g if g is not None else t.assign(_all=0).groupby("_all")
                pooled = src[f"{side}_goals"].sum() / src[f"{side}_scoring_shots"].sum() * 100
                out[col] = pooled.values
                note += f"{col} is pooled: total goals / total scoring shots. "
    if g is not None:
        out = out.reset_index()
    return _csv(out, note + _games_note(t))


def correlate(x, y, filters=None):
    t = _filter(_team(), filters)
    _check_cols([x, y], _team_metrics(), "team metric")
    pair = t[[x, y]].dropna()
    if len(pair) < 5:
        raise ToolError(f"Only {len(pair)} games match; need at least 5 for a correlation.")
    r = pair[x].corr(pair[y])
    return (f"Pearson r between {x} and {y}: {r:+.3f} over {len(pair)} games. "
            "Association only, not cause.")


def quarter_breakdown(filters=None, group_by=None):
    t = _filter(_team(), filters)
    if not len(t):
        raise ToolError("No games match those filters.")
    qs = ["Q1", "Q2", "Q3", "Q4"]
    f = pd.DataFrame(t["freo_qtrs"].map(D._qtr_points).tolist(), columns=qs, index=t.index)
    o = pd.DataFrame(t["opp_qtrs"].map(D._qtr_points).tolist(), columns=qs, index=t.index)
    run = (f - o).cumsum(axis=1)
    if group_by:
        _check_cols([group_by], TEAM_GROUPS, "group_by")
    keys = t[group_by] if group_by else pd.Series("all games", index=t.index)
    rows = []
    for key, idx in keys.groupby(keys).groups.items():
        for q in qs:
            rows.append({
                "group": key, "quarter": q, "games": len(idx),
                "freo_pts_avg": f.loc[idx, q].mean(), "opp_pts_avg": o.loc[idx, q].mean(),
                "quarter_margin_avg": (f.loc[idx, q] - o.loc[idx, q]).mean(),
                "quarters_won": int((f.loc[idx, q] > o.loc[idx, q]).sum()),
                "running_margin_avg_at_break": run.loc[idx, q].mean(),
            })
    return _csv(pd.DataFrame(rows), "Points per quarter from the quarter score strings.")


def player_aggregate(stats, agg="mean", filters=None, players=None, min_games=1,
                     last_n_games=None, group_by=None, sort_by=None, limit=20):
    p = _filter(_players(), filters)
    _check_cols(stats, set(player_stats()), "player stat")
    if agg not in AGGS:
        raise ToolError(f"agg must be one of {AGGS}.")
    if players:
        names = [_match_one(n, p["player"].unique(), "player") for n in players]
        p = p[p["player"].isin(names)]
    if last_n_games:
        n = int(last_n_games)
        p = (p.sort_values("game_dt").groupby("player", group_keys=False).tail(n))
    keys = ["player"] + ([group_by] if group_by else [])
    if group_by:
        _check_cols([group_by], PLAYER_GROUPS, "group_by")
    g = p.groupby(keys)
    out = g[stats].agg(agg)
    out.insert(0, "games", g.size())
    out = out[out["games"] >= int(min_games)].reset_index()
    sort_by = sort_by or stats[0]
    _check_cols([sort_by], set(out.columns), "sort column")
    out = out.sort_values(sort_by, ascending=False)
    note = f"{agg} of each stat per player" + (f", last {last_n_games} games each" if last_n_games else "")
    return _csv(out.head(max(1, min(int(limit), MAX_ROWS))), note + ".")


def player_games(players, stats, filters=None, limit=30):
    p = _filter(_players(), filters)
    _check_cols(stats, set(player_stats()), "player stat")
    if not players or len(players) > 4:
        raise ToolError("Give 1 to 4 players.")
    names = [_match_one(n, p["player"].unique(), "player") for n in players]
    p = p[p["player"].isin(names)].sort_values("game_dt", ascending=False)
    cols = ["player", "season", "round", "opponent", "result", "margin"] + stats
    return _csv(p[cols].head(max(1, min(int(limit), MAX_ROWS))), "Most recent first.")


# ---- definitions --------------------------------------------------------------
_FILTERS = {
    "type": "object",
    "description": "Optional game filters; omit any you don't need.",
    "properties": {
        "season": {"type": ["integer", "string"], "description": "e.g. 2026, or 'all'"},
        "result": {"type": "string", "enum": ["W", "L"]},
        "type": {"type": "string", "enum": ["Home", "Away", "Final"]},
        "opponent": {"type": "string", "description": "Club name, e.g. 'Geelong'"},
        "rounds": {"type": "array", "items": {"type": "string"},
                   "description": "AFL Tables round labels, e.g. ['R2', 'QF', 'GF']"},
        "min_margin": {"type": "number"},
        "max_margin": {"type": "number"},
    },
    "additionalProperties": False,
}


def _tool(name, description, props, required):
    return {
        "name": name, "description": description,
        "input_schema": {"type": "object", "properties": props, "required": required,
                         "additionalProperties": False},
        "eager_input_streaming": True,
    }


TOOLS = [
    _tool("team_games",
          "List games with chosen team metrics (one row per game). Use to find specific "
          "games, extremes, or to show per-game numbers.",
          {"filters": _FILTERS, "metrics": {"type": "array", "items": {"type": "string"}},
           "sort_by": {"type": "string"}, "descending": {"type": "boolean"},
           "limit": {"type": "integer"}}, ["metrics"]),
    _tool("team_aggregate",
          "Aggregate team metrics over games (mean per game by default), optionally grouped "
          "by result, type, opponent, season or venue. Use for averages, totals, win rates "
          "(mean of 'win') and splits such as wins vs losses.",
          {"metrics": {"type": "array", "items": {"type": "string"}},
           "agg": {"type": "string", "enum": AGGS},
           "group_by": {"type": "string", "enum": TEAM_GROUPS}, "filters": _FILTERS},
          ["metrics"]),
    _tool("correlate",
          "Pearson correlation between two team metrics across games, e.g. diff_metres_gained "
          "vs margin.",
          {"x": {"type": "string"}, "y": {"type": "string"}, "filters": _FILTERS}, ["x", "y"]),
    _tool("quarter_breakdown",
          "Quarter by quarter scoring: average points for and against, quarter margin, quarters "
          "won and running margin at each break, optionally grouped.",
          {"filters": _FILTERS, "group_by": {"type": "string", "enum": TEAM_GROUPS}}, []),
    _tool("player_aggregate",
          "Aggregate player stats per player (mean per game by default), with filters, a "
          "minimum games, the last N games each, or grouped by season/result/type/opponent. "
          "Use for leaders, form and season comparisons.",
          {"stats": {"type": "array", "items": {"type": "string"}},
           "agg": {"type": "string", "enum": AGGS}, "filters": _FILTERS,
           "players": {"type": "array", "items": {"type": "string"}},
           "min_games": {"type": "integer"}, "last_n_games": {"type": "integer"},
           "group_by": {"type": "string", "enum": PLAYER_GROUPS},
           "sort_by": {"type": "string"}, "limit": {"type": "integer"}}, ["stats"]),
    _tool("player_games",
          "Game by game rows for 1 to 4 players, most recent first.",
          {"players": {"type": "array", "items": {"type": "string"}},
           "stats": {"type": "array", "items": {"type": "string"}},
           "filters": _FILTERS, "limit": {"type": "integer"}}, ["players", "stats"]),
]

_IMPL = {
    "team_games": team_games, "team_aggregate": team_aggregate, "correlate": correlate,
    "quarter_breakdown": quarter_breakdown, "player_aggregate": player_aggregate,
    "player_games": player_games,
}


def run(name, args):
    """Run one tool call. Returns (text, is_error)."""
    fn = _IMPL.get(name)
    if fn is None:
        return f"Unknown tool '{name}'.", True
    if not isinstance(args, dict):
        return "Tool input must be a JSON object.", True
    try:
        return fn(**args), False
    except ToolError as e:
        return str(e), True
    except TypeError as e:  # unexpected or missing argument names
        return f"Bad arguments: {e}", True
    except (KeyError, ValueError) as e:
        return f"Could not run that query: {e}", True


def describe():
    """Schema text for the system prompt: what metrics and stats exist."""
    stems = team_stems()
    t = D.load_team()
    return (
        "TEAM METRICS (for team_games, team_aggregate, correlate): margin, win (1 if won), "
        "freo_score, opp_score, freo_accuracy, opp_accuracy (goal accuracy %; team_aggregate "
        "returns it pooled over the games), and for each stat below "
        "freo_<stat>, opp_<stat> and diff_<stat> (Freo minus opposition).\n"
        f"Stats: {', '.join(stems)}.\n"
        f"PLAYER STATS (for player_aggregate, player_games): {', '.join(player_stats())}.\n"
        f"Seasons: {', '.join(str(s) for s in D.seasons(t))}. Opponents: "
        f"{', '.join(sorted(t['opponent'].unique()))}."
    )
