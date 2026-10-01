"""The numbers behind an answer: tool tables are kept, and the check flags a
number no calculation accounts for (no API calls)."""

import json

import evidence as E
import usage as U
import wharf_tools as W


def _rec(name, args):
    text, is_error, _ = W.run(name, args)
    assert not is_error, text
    return E.item(name, args, text)


def test_numbers_skip_labels_and_names():
    got = [raw for *_, raw in E.numbers("R12 v GEE, 1st, inside 50s, Q3: 6,452 metres, +9.8, 52.4%")]
    assert got == ["6,452", "+9.8", "52.4%"]


def test_records_round_trip_as_json():
    rec = _rec("team_aggregate", {"metrics": ["win", "margin"], "group_by": "type",
                                  "filters": {"season": 2026}})
    rec = json.loads(json.dumps(rec))                     # saved chats are JSON
    df = E.table(rec)
    assert list(df["type"]) == ["Away", "Final", "Home"] and df["games"].sum() == 27
    assert E.describe(rec, {"team_aggregate": "averaging team stats"}).startswith(
        "Averaging team stats: metrics win, margin")


def test_backed_answer_passes_and_invented_number_is_flagged():
    rec = _rec("team_aggregate", {"metrics": ["win", "margin"], "group_by": "type",
                                  "filters": {"season": 2026}})
    good = ("We went 11-0 at home and 8-4 away (66.7%), averaging +36.0 at home and +18.7 "
            "away, a gap of 17.3 points.")
    assert E.unbacked(good, [rec]) == []
    assert E.unbacked(good + " Our average margin in 2025 was +6.8.", [rec]) == ["+6.8"]


def test_rates_and_shares_of_stated_numbers_are_backed():
    rec = _rec("player_aggregate", {"stats": ["goals"], "players": ["Jye Amiss"],
                                    "filters": {"season": 2026}, "agg": "sum"})
    games, goals = E.table(rec)[["games", "goals"]].iloc[0]
    rate = f"{goals / games:.1f}"
    assert E.unbacked(f"Amiss kicked {goals} goals in {games} games, {rate} a game.", [rec]) == []
    assert E.unbacked("We won 17 of the 19 games (89.5%).", [],
                      context="17 games of 19 won") == []


def test_ratings_are_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB", str(tmp_path / "u.sqlite"))
    qid = U.record("q", U.Tally(), answer="a", unbacked=["+6.8"])
    U.rate(qid, 0)
    row = U.recent()[0]
    assert row["id"] == qid and row["rating"] == 0 and row["answer"] == "a"
    assert json.loads(row["unbacked"]) == ["+6.8"]
