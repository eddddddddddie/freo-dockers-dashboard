"""Card takeaways, player profile data and navigation state."""

import pandas as pd
import pytest

import data as D
import nav
import takeaways as T


@pytest.fixture(scope="module")
def season():
    team, players = D.load_team(), D.load_players()
    return D.team_season(team, 2026), D.players_season(players, 2026), players


def test_takeaways_are_computed_from_the_card_data(season):
    tdf, pdf, _ = season
    strip = T.strip(tdf)
    top = D.margin_drivers(tdf).iloc[0]
    assert strip.startswith(top["stat"])
    qp = D.quarter_pattern(tdf)
    best = qp.loc[qp["margin"].idxmax()]
    assert f"Best {best['quarter']} ({best['margin']:+.1f})" in T.quarters(qp)
    for text in (T.where_we_win(D.win_conditions(tdf)), T.drivers(D.margin_drivers(tdf)),
                 T.leaders(D.role_leaders(pdf))):
        assert text and len(text) < 90


def test_match_flow_takeaway_for_the_grand_final(season):
    tdf, _, _ = season
    pos = len(tdf) - 1
    flow, _ = D.game_flow(tdf, pos)
    g = tdf.iloc[pos]
    text = T.flow(flow, g["result"], int(g["margin"]))
    assert str(abs(int(g["margin"]))) in text


def test_player_tiles_ranks_and_change(season):
    _, pdf, players = season
    tiles = D.player_tiles(players, "Caleb Serong", 2026, 2025)
    disp = next(t for t in tiles if t["label"] == "Disposals")
    me = pdf[pdf["player"] == "Caleb Serong"]
    assert disp["value"] == pytest.approx(me["disposals"].mean())
    assert 1 <= disp["rank"] <= disp["squad"]
    prev = D.players_season(players, 2025)
    base = prev[prev["player"] == "Caleb Serong"]["disposals"].mean()
    assert disp["change"] == pytest.approx((disp["value"] - base) / base * 100)


def test_squad_ranks_cover_every_profile_stat(season):
    _, pdf, _ = season
    pr = D.player_squad_ranks(pdf, "Andrew Brayshaw")
    assert len(pr) >= 10 and (pr["rank"] >= 1).all() and (pr["rank"] <= pr["squad"]).all()


def test_clicked_reads_the_first_point():
    class Event:
        selection = {"points": [{"x": "R7 WCE", "y": "Margin"}]}
    assert nav.clicked(Event())["x"] == "R7 WCE"
    assert nav.clicked(None) is None


def test_player_details_age_height_and_best_ranking(season):
    _, _, players = season
    d = D.player_details(players, "Jordan Clark", 2026, today="2026-09-30")
    squad = D.load_squad()
    row = squad[(squad["player_id"] == d["player_id"]) & (squad["season"] == 2026)].iloc[0]
    dob = pd.Timestamp(row["date_of_birth"])
    assert d["age"] == 2026 - dob.year - ((9, 30) < (dob.month, dob.day))
    assert d["height_cm"] == row["height_cm"]
    ranks = D.player_squad_ranks(D.players_season(players, 2026), "Jordan Clark")
    assert d["top"]["rank"] == ranks["rank"].min()
