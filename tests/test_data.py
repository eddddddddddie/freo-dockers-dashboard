"""Data rules from CLAUDE.md, checked on the committed CSVs."""

import pandas as pd
import pytest

import data as D


@pytest.fixture(scope="module")
def team():
    return D.load_team()


@pytest.fixture(scope="module")
def players():
    return D.load_players()


def qtr_points(q):
    return [6 * int(g) + int(b) for g, b in (x.split(".") for x in q.split())]


def test_kicks_plus_handballs_is_disposals(players):
    assert (players["kicks"] + players["handballs"] == players["disposals"]).all()


def test_score_is_six_goals_plus_behinds(team):
    assert (team["freo_score"] == 6 * team["freo_goals"] + team["freo_behinds"]).all()
    assert (team["opp_score"] == 6 * team["opp_goals"] + team["opp_behinds"]).all()


def test_margin_is_score_difference(team):
    assert (team["margin"] == team["freo_score"] - team["opp_score"]).all()


def test_quarter_strings_end_at_final_score(team):
    assert (team["freo_qtrs"].map(lambda q: qtr_points(q)[-1]) == team["freo_score"]).all()
    assert (team["opp_qtrs"].map(lambda q: qtr_points(q)[-1]) == team["opp_score"]).all()


def test_player_totals_match_team_totals(team, players):
    summed = players.groupby(["season", "round"])["disposals"].sum()
    t = team.set_index(["season", "round"])["freo_disposals"]
    assert (summed.reindex(t.index) == t).all()


def test_api_stats_merged_for_every_row(team, players):
    assert team["freo_pressure_acts"].notna().all()
    assert players["pressure_acts"].notna().all()


def test_goal_accuracy_is_pooled_from_team_totals(team):
    t26 = D.team_season(team, 2026)
    tile = next(x for x in D.tiles(team, 2026, 2025) if x["label"] == "Goal accuracy")
    pooled = t26["freo_goals"].sum() / (t26["freo_goals"] + t26["freo_behinds"]).sum() * 100
    assert tile["value"] == pytest.approx(pooled)


def test_differential_change_is_absolute_not_percent(team):
    tile = next(x for x in D.tiles(team, 2026, 2025) if x["label"] == "Contested poss diff")
    assert tile["unit"] == "" and tile["change"] == pytest.approx(tile["value"] - tile["base"])


def test_running_margin_at_q4_is_final_margin(team):
    for season in D.seasons(team):
        tdf = D.team_season(team, season)
        rm = D.running_margin(tdf)
        for res in rm.index:
            assert rm.loc[res, "Q4"] == pytest.approx(tdf[tdf["result"] == res]["margin"].mean())


def test_match_tiles_compare_one_game_with_season(team):
    tdf = D.team_season(team, 2026)
    pos = len(tdf) - 1
    t = D.match_tiles(team, 2026, pos)[0]  # clearance diff
    g = tdf.iloc[pos]
    assert t["value"] == pytest.approx(g["freo_clearances"] - g["opp_clearances"])


def test_similar_positions_counts(team):
    games, sm = D.similar_positions(team, "Half time", 0, 6)
    assert sm["games"] == len(games) == sm["wins"] + sm["losses"]
    assert (games["Q2"].abs() <= 6).all()


def test_league_file_if_present():
    lg = D.load_league()
    if lg is None:
        pytest.skip("league_team_games.csv not scraped")
    assert (lg["kicks"] + lg["handballs"] == lg["disposals"]).all()
    assert (lg["score_for"] == 6 * lg["goals_for"] + lg["behinds_for"]).all()
    assert (lg.groupby("match_id").size() == 2).all()
    freo = lg[lg["team"] == "Fremantle"]
    assert len(freo) == len(D.load_team())


def test_compare_players_matches_plain_pandas(players):
    p = D.players_season(players, 2026)
    a, b = "Caleb Serong", "Andrew Brayshaw"
    cmp = D.compare_players(p, a, b).set_index("stat")
    for who, key in ((a, "a"), (b, "b")):
        me = p[p["player"] == who].sort_values("game_dt")
        assert cmp.loc["Disposals", f"avg_{key}"] == pytest.approx(me["disposals"].mean())
        assert cmp.loc["Disposals", f"last_{key}"] == pytest.approx(me["disposals"].tail(5).mean())
    together = D.games_together(p, a, b)
    both = set(p[p["player"] == a]["round"]) & set(p[p["player"] == b]["round"])
    assert together["games"] == len(both) == together["wins"] + together["losses"]


def test_draws_are_neither_wins_nor_losses(team):
    from theme import record_text
    for season in D.seasons(team):
        rec = D.record(D.team_season(team, season))
        assert rec["wins"] + rec["losses"] + rec["draws"] == rec["games"]
        res = D.team_season(team, season)["result"]
        assert rec["draws"] == int((res == "D").sum())
    assert record_text(12, 10, 1) == "12-10-1" and record_text(21, 6) == "21-6"


def test_opposition_players_if_present(team):
    """The opposition's players: every Freo game has them, kicks + handballs =
    disposals, and their goals add up to the opposition's score in AFL Tables."""
    o = D.load_opp_players()
    if o is None:
        pytest.skip("opp_player_games_ext.csv not scraped")
    assert (o["kicks"] + o["handballs"] == o["disposals"]).all()
    for _, g in team.iterrows():
        assert D.opp_match_leaders(g) is not None, (g["season"], g["round"], g["opponent"])
    goals = o.groupby(["season", "opponent", "date_local"])["goals"].sum().rename("goals_players")
    t = team[["season", "opponent", "opp_goals"]].assign(date_local=team["game_dt"].dt.strftime("%Y-%m-%d"))
    joined = t.join(goals, on=["season", "opponent", "date_local"])
    matched = joined.dropna(subset=["goals_players"])
    assert len(matched) >= len(team) * 0.9           # most dates agree exactly (some are a day apart)
    assert (matched["goals_players"] == matched["opp_goals"]).all()


def test_quarter_strip_and_driver_points(team):
    """The Games view of Quarters and the drivers drill-down, against plain pandas."""
    t = D.team_season(team, 2026)
    rows, z, hover, labels = D.quarter_strip(t)
    assert rows == ["Q1", "Q2", "Q3", "Q4"] and len(labels) == len(t) and len(z[0]) == len(t)
    q3 = [qtr_points(f)[2] - qtr_points(f)[1] - (qtr_points(o)[2] - qtr_points(o)[1])
          for f, o in zip(t["freo_qtrs"], t["opp_qtrs"])]
    assert all((v > 0) == (s > 0) and (v < 0) == (s < 0) for v, s in zip(z[2], q3))
    pts, fit = D.driver_points(t, "Metres gained")
    diff = t["freo_metres_gained"] - t["opp_metres_gained"]
    assert fit["r"] == pytest.approx(diff.corr(t["margin"]), abs=1e-9)
    assert fit["ahead"] == int((diff > 0).sum())
    assert fit["ahead_won"] == int(((diff > 0) & (t["result"] == "W")).sum())
