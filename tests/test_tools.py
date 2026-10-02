"""Wharf-ai's tools give the same answers as plain pandas, and bad input
comes back as an error the model can fix (not an exception)."""

import pytest

import data as D
import wharf_tools as W


def run_ok(name, args):
    text, is_error, _ = W.run(name, args)
    assert not is_error, text
    return text


def test_home_record_2026():
    t = D.team_season(D.load_team(), 2026)
    home = t[t["type"] == "Home"]
    text = run_ok("team_aggregate", {"metrics": ["win", "margin"], "group_by": "type",
                                     "filters": {"season": 2026}})
    line = next(l for l in text.splitlines() if l.startswith("Home,"))
    games, win, margin = line.split(",")[1:4]
    assert int(games) == len(home)
    assert float(win) == pytest.approx((home["result"] == "W").mean(), abs=0.01)
    assert float(margin) == pytest.approx(home["margin"].mean(), abs=0.01)


def test_accuracy_is_pooled():
    t = D.team_season(D.load_team(), 2026)
    text = run_ok("team_aggregate", {"metrics": ["freo_accuracy"], "filters": {"season": 2026}})
    value = float(text.splitlines()[2].split(",")[1])
    pooled = t["freo_goals"].sum() / t["freo_scoring_shots"].sum() * 100
    assert value == pytest.approx(pooled, abs=0.01)


def test_correlation():
    t = D.team_season(D.load_team(), 2026)
    r = (t["freo_metres_gained"] - t["opp_metres_gained"]).corr(t["margin"])
    assert f"{r:+.3f}" in run_ok("correlate", {"x": "diff_metres_gained", "y": "margin",
                                               "filters": {"season": 2026}})


def test_player_average():
    p = D.players_season(D.load_players(), 2026)
    avg = p[p["player"] == "Caleb Serong"]["disposals"].mean()
    text = run_ok("player_aggregate", {"stats": ["disposals"], "players": ["Serong"],
                                       "filters": {"season": 2026}})
    row = next(l for l in text.splitlines() if l.startswith("Caleb Serong,"))
    assert float(row.split(",")[2]) == pytest.approx(avg, abs=0.01)


def test_show_chart_returns_a_figure():
    text, is_error, fig = W.run("show_chart", {"kind": "player_trend", "title": "t",
                                               "players": ["Serong"], "stat": "disposals"})
    assert not is_error and fig is not None and "Chart shown" in text


@pytest.mark.parametrize("name,args", [
    ("team_aggregate", {"metrics": ["freo_bogus"]}),
    ("team_games", {"metrics": ["margin"], "unknown_arg": 1}),
    ("player_aggregate", {"stats": ["disposals"], "players": ["Luke"]}),  # ambiguous
    ("show_chart", {"kind": "pie", "title": "x"}),
    ("no_such_tool", {}),
])
def test_bad_input_is_an_error_result(name, args):
    text, is_error, fig = W.run(name, args)
    assert is_error and text and fig is None


def test_league_tools_if_present():
    if D.load_league() is None:
        pytest.skip("league_team_games.csv not scraped")
    text = run_ok("ladder", {"season": 2026})
    assert "Fremantle" in text
    run_ok("league_aggregate", {"metrics": ["margin"], "filters": {"season": 2026}})


@pytest.mark.parametrize("name,args", [
    ("team_aggregate", {"metrics": ["margin"], "filters": {"venue": "Perth Stadium"}}),
    ("player_aggregate", {"stats": ["disposals"], "filters": {"quarter": 3}}),
    ("team_games", {"metrics": ["margin"], "filters": "2026"}),
])
def test_unknown_or_malformed_filters_are_errors(name, args):
    """A filter the tools don't know must fail loudly: skipping it would answer
    over every game instead."""
    text, is_error, _ = W.run(name, args)
    assert is_error, text
    assert "filter" in text.lower()


def test_unknown_league_filter_is_an_error():
    if D.load_league() is None:
        pytest.skip("no league data")
    text, is_error, _ = W.run("league_aggregate", {"metrics": ["margin"],
                                                   "filters": {"venue": "Gabba"}})
    assert is_error and "Unknown filter: venue" in text


def test_opp_players_match_plain_pandas():
    """opp_players: the opposition's players in Freo games, checked against the raw
    file (no join through the tool): one game (the 2026 GF) and a club over seasons."""
    import pandas as pd
    o = D.load_opp_players()
    if o is None:
        pytest.skip("opp_player_games_ext.csv not scraped")
    t = D.load_team()
    gf = t[(t["season"] == 2026) & (t["round"] == "GF")].iloc[0]
    raw = pd.read_csv(D.OPP_PLAYER_CSV)
    gf_rows = raw[(raw["season"] == 2026) & (raw["opponent"] == gf["opponent"])
                  & (raw["date_local"] == gf["game_dt"].strftime("%Y-%m-%d"))]
    top = gf_rows.sort_values("disposals", ascending=False).iloc[0]
    text = run_ok("opp_players", {"stats": ["disposals"], "limit": 1,
                                  "filters": {"season": 2026, "rounds": ["GF"]}})
    assert f"{top['player']},{gf['opponent']},1,{float(top['disposals'])}" in text
    # Geelong's clearances against us, all seasons, players with 3+ games
    geel = raw[raw["opponent"] == "Geelong"].groupby("player")["total_clearances"].agg(["size", "mean"])
    best = geel[geel["size"] >= 3]["mean"].idxmax()
    text = run_ok("opp_players", {"stats": ["clearances"], "min_games": 3, "limit": 1,
                                  "filters": {"opponent": "Geelong"}})
    assert text.splitlines()[2].startswith(f"{best},Geelong,{int(geel.loc[best, 'size'])},")
    # Freo's result filters work on these rows too, and bad stats are errors
    assert "games matched" in run_ok("opp_players", {"stats": ["tackles"], "filters": {"result": "L"}})
    assert W.run("opp_players", {"stats": ["tackels"]})[1]


def test_behind_and_ahead_at_a_break_match_plain_pandas():
    t = D.team_season(D.load_team(), 2026)
    q = lambda s: [6 * int(g) + int(b) for g, b in (x.split(".") for x in s.split())]  # noqa: E731
    ht = [q(a)[1] - q(b)[1] for a, b in zip(t["freo_qtrs"], t["opp_qtrs"])]
    behind = t[[m < 0 for m in ht]]
    text = run_ok("team_aggregate", {"metrics": ["win", "loss", "draw"], "agg": "sum",
                                     "filters": {"season": 2026, "behind_at": "Q2"}})
    games, w, l, d = text.splitlines()[2].split(",")
    assert (int(games), int(w), int(l)) == (len(behind), (behind["result"] == "W").sum(),
                                            (behind["result"] == "L").sum())
    ahead = sum(m > 0 for m in ht)
    assert f"Games matched: {ahead}." in run_ok("team_aggregate", {
        "metrics": ["margin"], "filters": {"season": 2026, "ahead_at": "Q2"}})
    assert W.run("team_games", {"metrics": ["margin"], "filters": {"behind_at": "Q9"}})[1]
