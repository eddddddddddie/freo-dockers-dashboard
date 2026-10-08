"""Data tools Wharf-ai calls to compute every number it quotes.

Each tool is a small, fixed pandas query over the loaded CSVs: no model-written
code runs. Inputs are validated here (tool inputs stream eagerly, so the API
does not validate them), bad input comes back as an error the model can fix,
and results are compact CSV capped at MAX_ROWS rows.
"""

import pandas as pd

import charts as CH
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
    t["loss"] = (t["result"] == "L").astype(int)
    t["draw"] = (t["result"] == "D").astype(int)
    brk = _break_margins()
    for q in ("Q1", "Q2", "Q3"):           # running margin at quarter, half and three quarter time
        t[f"margin_{q.lower()}"] = brk[q].values
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
GAME_FILTERS = ("season", "result", "type", "opponent", "rounds", "min_margin", "max_margin",
                "behind_at", "ahead_at")
BREAK_KEYS = {"Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "QT": "Q1", "HT": "Q2", "3QT": "Q3"}
LEAGUE_FILTERS = ("season", "result", "finals", "opponent")


def _check_filters(f, allowed):
    """The filters as a dict. An unknown key is an error, never skipped: skipping
    it would quietly answer over every game (e.g. a "venue" filter)."""
    if f is None:
        return {}
    if not isinstance(f, dict):
        raise ToolError("filters must be an object, e.g. {\"season\": 2026}.")
    bad = [k for k in f if k not in allowed]
    if bad:
        raise ToolError(f"Unknown filter: {', '.join(bad)}. Valid filters are "
                        f"{', '.join(allowed)}. To split by something else, use group_by.")
    return f


def _filter(df, f):
    f = _check_filters(f, GAME_FILTERS)
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
    for key, behind in (("behind_at", True), ("ahead_at", False)):
        if f.get(key):
            q = BREAK_KEYS.get(str(f[key]).upper())
            if q is None:
                raise ToolError(f"{key} must be Q1 (quarter time), Q2 (half time) or Q3 "
                                "(three quarter time).")
            at = _break_margins()[q].rename("_at")
            m = df.join(at, on=["season", "round"])["_at"]
            df = df[m < 0] if behind else df[m > 0]
    return df


def _break_margins():
    """Freo's running margin at each break (Q1-Q3), by season and round."""
    t = D.load_team()
    f = pd.DataFrame(t["freo_qtrs"].map(D._qtr_points).tolist(), index=t.index)
    o = pd.DataFrame(t["opp_qtrs"].map(D._qtr_points).tolist(), index=t.index)
    run = (f - o).cumsum(axis=1).iloc[:, :3]
    run.columns = ["Q1", "Q2", "Q3"]
    return run.set_index(pd.MultiIndex.from_frame(t[["season", "round"]]))


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


class Result(str):
    """A tool's output: the text the model reads, carrying the table it was made
    from (`df`, the rows shown) and its note, so the app can show the numbers."""

    def __new__(cls, text, df=None, note=""):
        obj = super().__new__(cls, text)
        obj.df, obj.note = df, note
        return obj


def _csv(df, note=""):
    total = len(df)
    df = df.head(MAX_ROWS).round(2)
    out = df.to_csv(index=False).strip()
    extra = f"\n({total} rows, first {MAX_ROWS} shown)" if total > MAX_ROWS else f"\n({total} rows)"
    return Result((note + "\n" if note else "") + out + extra, df, note)


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


# ---- the opposition's players (in Freo games only) -------------------------------
OPP_GROUPS = ["season", "result", "type", "round"]
_OPP_META = {"season", "jumper", "margin"}


def _opp_players():
    """The opposition's players in Freo games (AFL match centre), each row with
    that game's Freo-side details (round, type, Freo's result and margin), so the
    usual game filters apply; "opponent" is the player's club."""
    o = D.load_opp_players()
    if o is None:
        raise ToolError("Opposition player stats are not loaded (run afl_api_scraper.py).")
    t = D.load_team()[["season", "round", "type", "opponent", "result", "margin", "game_dt"]]
    m = o.drop(columns=["round"], errors="ignore").merge(t, on=["season", "opponent"])
    return m[(m["game_dt"].dt.normalize() - m["_d"]).abs() <= pd.Timedelta(days=1)]


def opp_player_stats():
    o = D.load_opp_players()
    if o is None:
        return []
    return sorted(c for c in o.columns
                  if pd.api.types.is_numeric_dtype(o[c]) and c not in _OPP_META)


def opp_players(stats, agg="mean", filters=None, players=None, min_games=1, group_by=None,
                sort_by=None, limit=20):
    """Opposition players' stats in their games against Fremantle, per player."""
    p = _filter(_opp_players(), filters)
    _check_cols(stats, set(opp_player_stats()), "opposition player stat")
    if agg not in AGGS:
        raise ToolError(f"agg must be one of {AGGS}.")
    if players:
        names = [_match_one(n, p["player"].unique(), "opposition player") for n in players]
        p = p[p["player"].isin(names)]
    if not len(p):
        raise ToolError("No opposition players match those filters.")
    keys = ["player", "opponent"] + ([group_by] if group_by else [])
    if group_by:
        _check_cols([group_by], OPP_GROUPS, "group_by")
    g = p.groupby(keys)
    out = g[stats].agg(agg)
    out.insert(0, "games", g.size())
    out = out[out["games"] >= int(min_games)].reset_index().rename(columns={"opponent": "club"})
    sort_by = sort_by or stats[0]
    _check_cols([sort_by], set(out.columns), "sort column")
    out = out.sort_values(sort_by, ascending=False)
    note = (f"{agg} of each stat per opposition player, in their games against Fremantle only "
            f"({p.groupby(['season', 'round', 'opponent']).ngroups} games matched).")
    return _csv(out.head(max(1, min(int(limit), MAX_ROWS))), note)


LEAGUE_GROUPS = ["team", "result", "is_home", "opponent", "season", "is_final"]


def _league():
    lg = D.load_league()
    if lg is None:
        raise ToolError("League data is not loaded (run league_scraper.py).")
    return lg


def league_aggregate(metrics, agg="mean", group_by="team", filters=None, teams=None,
                     sort_by=None, limit=18):
    """Any club's games: aggregate league metrics, by team by default."""
    lg = _league()
    f = _check_filters(filters, LEAGUE_FILTERS)
    if f.get("season") not in (None, "all"):
        lg = lg[lg["season"] == int(f["season"])]
    if f.get("result"):
        lg = lg[lg["result"] == str(f["result"]).upper()[:1]]
    if f.get("finals") is not None:
        lg = lg[lg["is_final"] == bool(f["finals"])]
    if f.get("opponent"):
        lg = lg[lg["opponent"] == _match_one(str(f["opponent"]), lg["opponent"].unique(), "club")]
    if teams:
        lg = lg[lg["team"].isin([_match_one(n, lg["team"].unique(), "club") for n in teams])]
    numeric = set(lg.select_dtypes("number").columns)
    _check_cols(metrics, numeric, "league metric")
    if agg not in AGGS:
        raise ToolError(f"agg must be one of {AGGS}.")
    _check_cols([group_by], LEAGUE_GROUPS, "group_by")
    g = lg.groupby(group_by)
    out = g[metrics].agg(agg)
    out.insert(0, "games", g.size())
    if agg == "mean" and "accuracy" in metrics:  # pooled, as elsewhere
        out["accuracy"] = g["goals_for"].sum() / g["scoring_shots"].sum() * 100
    out = out.reset_index()
    sort_by = sort_by or metrics[0]
    _check_cols([sort_by], set(out.columns), "sort column")
    out = out.sort_values(sort_by, ascending=False).head(max(1, min(int(limit), MAX_ROWS)))
    return _csv(out, f"{agg} per game unless agg is sum/count, one row per {group_by}.")


def ladder(season):
    """Ladder from home and away results."""
    lad = D.ladder(_league(), int(season)).reset_index()
    return _csv(lad[["position", "team", "played", "wins", "losses", "draws", "points", "pct"]],
                "Home and away only; 4 points a win, 2 a draw; pct = points for / against x 100.")


def show_chart(kind, title, metrics=None, players=None, stat=None, filters=None,
               min_games=5, top_n=10):
    """Draw a chart under the answer from the data itself (the model never
    supplies the numbers). Returns (summary text, plotly figure)."""
    if kind == "team_trend":
        _check_cols(metrics or [], _team_metrics(), "team metric")
        if len(metrics) > 2:
            raise ToolError("team_trend takes 1 or 2 metrics.")
        t = _filter(_team(), filters).sort_values("game_dt")
        if not len(t):
            raise ToolError("No games match those filters.")
        x = D.game_labels(t)
        series = [(m, x, t[m].round(1).tolist()) for m in metrics]
        fig = CH.answer_chart(series, title, "")
        return f"Chart shown: {title} ({len(t)} games).", fig
    if kind == "player_trend":
        if not stat or not players or len(players) > 3:
            raise ToolError("player_trend needs a stat and 1 to 3 players.")
        _check_cols([stat], set(player_stats()), "player stat")
        p = _filter(_players(), filters)
        names = [_match_one(n, p["player"].unique(), "player") for n in players]
        series = []
        for n in names:
            g = p[p["player"] == n].sort_values("game_dt")
            x = (g["round"] + " " + g["opponent"].map(D.abbr)).tolist()
            series.append((n, x, g[stat].round(1).tolist()))
        fig = CH.answer_chart(series, title, stat.replace("_", " "))
        return f"Chart shown: {title} ({', '.join(names)}).", fig
    if kind == "player_bar":
        if not stat:
            raise ToolError("player_bar needs a stat.")
        _check_cols([stat], set(player_stats()), "player stat")
        p = _filter(_players(), filters)
        if players:
            p = p[p["player"].isin([_match_one(n, p["player"].unique(), "player")
                                    for n in players])]
        g = p.groupby("player")[stat].agg(["mean", "count"])
        g = g[g["count"] >= int(min_games)].sort_values("mean", ascending=False)
        g = g.head(max(1, min(int(top_n), 15)))
        if not len(g):
            raise ToolError("No players match (check min_games and filters).")
        series = [(f"{stat.replace('_', ' ')} per game", g.index.tolist(),
                   g["mean"].round(1).tolist())]
        fig = CH.answer_chart(series, title, "", kind="bar", height=max(180, 26 * len(g) + 50))
        return f"Chart shown: {title} ({len(g)} players, per game averages).", fig
    raise ToolError("kind must be team_trend, player_trend or player_bar.")


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
        "behind_at": {"type": "string", "enum": ["Q1", "Q2", "Q3"],
                      "description": "Only games where Freo trailed at this break (Q2 = half time)"},
        "ahead_at": {"type": "string", "enum": ["Q1", "Q2", "Q3"],
                     "description": "Only games where Freo led at this break"},
    },
    "additionalProperties": False,
}


# ---- momentum: every score in order (freo_score_events.csv) -------------------
MOMENTUM_KINDS = ["games", "runs", "windows", "carry", "scores"]


def momentum(kind, filters=None, side="both", min_goals=3, minutes=10):
    if D.load_score_events() is None:
        raise ToolError("Scores in order are not in the data.")
    if kind not in MOMENTUM_KINDS:
        raise ToolError(f"kind must be one of {MOMENTUM_KINDS}.")
    t = _filter(_team(), filters)
    if not len(t):
        raise ToolError("No games match those filters.")
    note = _games_note(t)
    if kind == "games":
        out = D.game_run_summary(t)
        return _csv(out, "One row per game. freo_best / opp_best: each side's biggest run of "
                         "unanswered scores (goals.behinds; _pts its points); freo_runs / opp_runs: "
                         f"runs of {D.RUN_GOALS}+ goals; max_lead / max_deficit: Freo's biggest lead "
                         "and deficit at any point; q4_max_lead: biggest lead during the last "
                         "quarter; lead_changes: times the lead changed hands. " + note)
    if kind == "runs":
        if side not in ("both", "for", "against"):
            raise ToolError("side must be both, for (Freo's runs) or against.")
        if not 2 <= int(min_goals) <= 10:
            raise ToolError("min_goals must be 2 to 10.")
        out = D.run_table(t, int(min_goals))
        if len(out) and side != "both":
            out = out[out["team"] == ("Freo" if side == "for" else "Opp")]
        out = out.drop(columns=["t_start"], errors="ignore")
        return _csv(out, f"Every run of {int(min_goals)}+ goals with no score by the other side. "
                         "team: who kicked it; starts: quarter and clock; minutes: its length; "
                         "margin_before/after: Freo's margin; answered_in: minutes of play until the "
                         "other side scored (blank: the game ended first). " + note)
    if kind == "windows":
        if not 3 <= int(minutes) <= 15:
            raise ToolError("minutes must be 3 to 15.")
        out, n = D.window_scoring(t, int(minutes))
        return _csv(out, f"Average points a game in the first and last {int(minutes)} minutes of "
                         f"each quarter and the middle, over {n} games; net = Freo minus opposition.")
    if kind == "carry":
        r = D.momentum_test(t)
        if not r:
            raise ToolError("Not enough goals in those games.")
        out = pd.DataFrame([{**r, **{k: r[k] * 100 for k in ("observed", "chance", "lo", "hi")}}])
        out = out.rename(columns={"observed": "observed_pct", "chance": "chance_pct",
                                  "lo": "lo_pct", "hi": "hi_pct"})
        return _csv(out, "After a goal, how often the next goal in the same quarter was by the "
                         "same side (observed, %), against chance: each quarter's goals shuffled "
                         "2,000 times keeping the score (chance = mean, lo-hi = 5th to 95th "
                         "percentile, p = share of shuffles at or above observed). Observed above "
                         "hi would be evidence of momentum; inside the range is none. " + note)
    if len(t) != 1:
        raise ToolError(f"kind 'scores' needs filters matching one game; {len(t)} match. "
                        "Add season and rounds, e.g. {\"season\": 2026, \"rounds\": [\"GF\"]}.")
    events, quarters = D.game_events(t.iloc[0])
    out = events.assign(clock=[D._clock(x, quarters) for x in events["t"]])[
        ["event", "clock", "team", "kind", "player", "freo_score", "opp_score", "margin"]]
    return _csv(out, "Every score in the game in order (player blank: rushed behind).")


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

TOOLS.append(_tool(
    "show_chart",
    "Draw a small chart under your answer, built from the data by the app (you never supply "
    "the numbers). Use it when a trend or ranking is easier to see than read, at most 2 per "
    "answer. kind: team_trend (1-2 team metrics per game), player_trend (one player stat per "
    "game for 1-3 players), player_bar (per game average of one stat, top players or the "
    "players you name). Still quote the key numbers from the other tools in your text.",
    {"kind": {"type": "string", "enum": ["team_trend", "player_trend", "player_bar"]},
     "title": {"type": "string", "description": "Short chart title"},
     "metrics": {"type": "array", "items": {"type": "string"}},
     "players": {"type": "array", "items": {"type": "string"}},
     "stat": {"type": "string"}, "filters": _FILTERS,
     "min_games": {"type": "integer"}, "top_n": {"type": "integer"}},
    ["kind", "title"]))

TOOLS.append(_tool(
    "league_aggregate",
    "Any club's games, for opponent questions and league comparisons: aggregate league "
    "metrics (mean per game by default) grouped by team (default), result, is_home, opponent, "
    "season or is_final. Filter by season, result, finals (true/false), opponent, or teams.",
    {"metrics": {"type": "array", "items": {"type": "string"}},
     "agg": {"type": "string", "enum": AGGS},
     "group_by": {"type": "string", "enum": LEAGUE_GROUPS},
     "filters": {"type": "object", "additionalProperties": False, "properties": {
         "season": {"type": ["integer", "string"]}, "result": {"type": "string", "enum": ["W", "L", "D"]},
         "finals": {"type": "boolean"}, "opponent": {"type": "string"}}},
     "teams": {"type": "array", "items": {"type": "string"}},
     "sort_by": {"type": "string"}, "limit": {"type": "integer"}}, ["metrics"]))
TOOLS.append(_tool("ladder", "The ladder for a season, from home and away results.",
                   {"season": {"type": "integer"}}, ["season"]))
TOOLS.append(_tool(
    "opp_players",
    "The opposition's players, only in their games against Fremantle: aggregate their stats "
    "per player (mean per game by default; for one game, filter to it), optionally grouped "
    "by season, result (Freo's), type or round. filters.opponent picks the club; rounds "
    "picks games, e.g. ['GF']. Use for the opposition's best players against Fremantle and "
    "matchups.",
    {"stats": {"type": "array", "items": {"type": "string"}},
     "agg": {"type": "string", "enum": AGGS}, "filters": _FILTERS,
     "players": {"type": "array", "items": {"type": "string"}},
     "min_games": {"type": "integer"},
     "group_by": {"type": "string", "enum": OPP_GROUPS},
     "sort_by": {"type": "string"}, "limit": {"type": "integer"}}, ["stats"]))

TOOLS.append(_tool(
    "momentum",
    "Every score of every Freo game in order, with its time. kind: games (per game: each "
    "side's biggest unanswered run, runs of 3+ goals, Freo's biggest lead and deficit, biggest "
    "lead in the last quarter, lead changes), runs (every run of min_goals+ goals unanswered; "
    "side for/against/both; how fast the other side answered), windows (points in the first "
    "and last N minutes of each quarter), carry (does the side that kicked the last goal kick "
    "the next one more often than chance), scores (one game's scores in order; filters must "
    "match one game). Use for momentum, runs, when a game turned, and leads lost or overturned.",
    {"kind": {"type": "string", "enum": MOMENTUM_KINDS}, "filters": _FILTERS,
     "side": {"type": "string", "enum": ["both", "for", "against"]},
     "min_goals": {"type": "integer"}, "minutes": {"type": "integer"}}, ["kind"]))

_IMPL = {
    "team_games": team_games, "team_aggregate": team_aggregate, "correlate": correlate,
    "quarter_breakdown": quarter_breakdown, "player_aggregate": player_aggregate,
    "player_games": player_games, "show_chart": show_chart,
    "league_aggregate": league_aggregate, "ladder": ladder, "opp_players": opp_players,
    "momentum": momentum,
}


def run(name, args):
    """Run one tool call. Returns (text, is_error, figure or None)."""
    fn = _IMPL.get(name)
    if fn is None:
        return f"Unknown tool '{name}'.", True, None
    if not isinstance(args, dict):
        return "Tool input must be a JSON object.", True, None
    try:
        out = fn(**args)
    except ToolError as e:
        return str(e), True, None
    except TypeError as e:  # unexpected or missing argument names
        return f"Bad arguments: {e}", True, None
    except (KeyError, ValueError) as e:
        return f"Could not run that query: {e}", True, None
    if isinstance(out, tuple):  # show_chart: (summary, figure)
        return out[0], False, out[1]
    return out, False, None


def describe():
    """Schema text for the system prompt: what metrics and stats exist."""
    stems = team_stems()
    t = D.load_team()
    return (
        "TEAM METRICS (for team_games, team_aggregate, correlate): margin, win, loss, draw "
        "(1 or 0; with agg sum they give the record), margin_q1, margin_q2, margin_q3 (Freo's "
        "running margin at quarter, half and three quarter time), "
        "freo_score, opp_score, freo_accuracy, opp_accuracy (goal accuracy %; team_aggregate "
        "returns it pooled over the games), and for each stat below "
        "freo_<stat>, opp_<stat> and diff_<stat> (Freo minus opposition).\n"
        f"Stats: {', '.join(stems)}.\n"
        f"PLAYER STATS (for player_aggregate, player_games): {', '.join(player_stats())}.\n"
        f"Seasons: {', '.join(str(s) for s in D.seasons(t))}. Opponents: "
        f"{', '.join(sorted(t['opponent'].unique()))}."
        + _opp_describe() + _league_describe()
    )


def _league_describe():
    lg = D.load_league()
    if lg is None:
        return ""
    skip = {"season", "round_number"}
    cols = sorted(c for c in lg.select_dtypes("number").columns
                  if c not in skip and not c.startswith("opp_") and not c.startswith("diff_"))
    return ("\nLEAGUE METRICS (league_aggregate; every club's games, one row per team per match; "
            "team names as above plus Fremantle): " + ", ".join(cols) + ", plus opp_<stat> (the "
            "opposition's) and diff_<stat> (team minus opposition) for each count stat. There "
            "are no player stats for other clubs except in their games against Fremantle "
            "(opp_players).")


def _opp_describe():
    stats = opp_player_stats()
    if not stats:
        return ""
    return ("\nOPPOSITION PLAYER STATS (opp_players; other clubs' players in their games "
            "against Fremantle only, Champion Data names): " + ", ".join(stats) + ".")
