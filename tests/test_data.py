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


def test_game_slices_cut_games_and_their_player_rows(team, players):
    """Each slice keeps the right games in every season, and only those games'
    player rows; "vs top 8" uses each season's own ladder."""
    lg = D.load_league()
    for which in D.GAME_SLICES:
        t, p = D.slice_games(team, players, which, lg)
        if which == "Home games":
            assert (t["type"] == "Home").all() and len(t) == (team["type"] == "Home").sum()
        if which in ("Wins", "Losses"):
            assert (t["result"] == which[0]).all()
        if which == "Last 10 games":
            assert (t.groupby("season").size() <= 10).all()
        if which == "vs top 8" and lg is not None:
            for s, g in t.groupby("season"):
                assert set(g["opponent"]) <= set(D.ladder(lg, s).index[:8])
        keys = set(zip(t["season"], t["round"]))
        assert set(zip(p["season"], p["round"])) == keys        # player rows follow their games


def test_vs_self_takeaway_names_the_biggest_game_on_own_average(players):
    """Match view: the "above themselves" takeaway names the biggest game as a %
    of the player's own season average (on averages big enough to count)."""
    import charts as CH
    import takeaways as T
    pdf = D.players_season(players, 2026)
    game = D.team_season(D.load_team(), 2026).iloc[-1]
    stats = [("Disposals", "disposals"), ("Tackles", "tackles"), ("Metres gained", "metres_gained")]
    vals, pct, avgs = D.match_players(pdf, game, [c for _, c in stats])
    best = max(((pct.at[p, c], p, l) for l, c in stats for p in pct.index
                if avgs.at[p, c] >= CH.VS_SELF_MIN_AVG[c]), key=lambda r: r[0])
    text = T.vs_self(vals, pct, avgs, stats)
    assert f"{best[1].split()[-1]} {best[2].lower()}" in text and f"{best[0] - 100:+.0f}%" in text


def test_last_game_takeaway_counts_stats_above_average(players):
    import takeaways as T
    log = D.player_log(D.players_season(players, 2026), "Caleb Serong").sort_values("game_dt")
    stats = [("Disposals", "disposals"), ("Tackles", "tackles"), ("Goals", "goals")]
    above = sum(log.iloc[-1][c] > log[c].mean() for _, c in stats)
    assert f"above his average on {above} of 3 stats" in T.last_game_vs_avg(log, stats)


def test_score_events_add_up_to_every_quarter(team):
    """freo_score_events.csv: every game has its scores, each adds 6 (goal) or 1
    (behind) to the side that kicked it, times run forward within a quarter, and
    the running score at each break is the quarter score string."""
    ev = D.load_score_events()
    assert ev is not None
    for _, g in team.iterrows():
        e = ev[(ev["season"] == g["season"]) & (ev["round"] == g["round"])
               & (ev["opponent"] == g["opponent"])].sort_values("event")
        assert len(e), (g["season"], g["round"])
        step_f = e["freo_score"].diff().fillna(e["freo_score"].iloc[0])
        step_o = e["opp_score"].diff().fillna(e["opp_score"].iloc[0])
        want = e["kind"].map({"goal": 6, "behind": 1})
        assert ((e["team"] == "Freo") & (step_f == want) & (step_o == 0)
                | (e["team"] == "Opp") & (step_o == want) & (step_f == 0)).all(), g["round"]
        assert (e.groupby("quarter")["secs"].diff().fillna(0) >= 0).all()
        assert (e["secs"] <= e["quarter_secs"]).all()
        for q, (f, o) in enumerate(zip(qtr_points(g["freo_qtrs"]), qtr_points(g["opp_qtrs"])), 1):
            upto = e[e["quarter"] <= q]
            assert (int(upto["freo_score"].iloc[-1]) if len(upto) else 0,
                    int(upto["opp_score"].iloc[-1]) if len(upto) else 0) == (f, o), (g["round"], q)


def test_momentum_and_runs_on_the_2026_grand_final(team):
    """Brisbane's last four goals: the biggest run (4.0, 24 points, all in Q4),
    momentum at its lowest after them, and 0 at every quarter's first bounce."""
    import takeaways as T
    g = team[(team["season"] == 2026) & (team["round"] == "GF")].iloc[0]
    events, quarters = D.game_events(g)
    assert int(events["margin"].iloc[-1]) == int(g["margin"])
    run = D.scoring_runs(events).iloc[0]
    assert (run["team"], run["goals"], run["behinds"], run["points"]) == ("Opp", 4, 0, 24)
    assert run["q_start"] == run["q_end"] == 4
    mom = D.momentum(events, quarters)
    starts = mom.groupby("quarter")["momentum"].first()
    assert (starts == 0).all()
    assert mom["momentum"].idxmin() == len(mom) - 1 or mom.loc[mom["momentum"].idxmin(), "quarter"] == 4
    assert T.momentum(events, run, "L", -7, "BRL") == "Up 17 in Q4, lost by 7: BRL 4.0 unanswered"


def test_momentum_halves_every_half_life():
    """One Freo goal 2 minutes into a 30 minute quarter: momentum is 6 when it's
    kicked, 3 one half-life later, and back to 0 at the next quarter."""
    q = pd.DataFrame({"start": [0.0, 30.0], "length": [30.0, 30.0]}, index=[1, 2])
    ev = pd.DataFrame({"quarter": [1], "t": [2.0], "pts": [6]})
    mom = D.momentum(ev, q)
    q1 = mom[mom["quarter"] == 1].set_index("t")["momentum"]
    assert q1[1.5] == 0 and q1[2.0] == 6
    assert abs(q1[2.0 + D.MOMENTUM_HALF_LIFE] - 3) < 1e-9
    assert (mom[mom["quarter"] == 2]["momentum"] == 0).all()
