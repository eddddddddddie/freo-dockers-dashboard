"""
Every club's matches from the AFL match centre API, for the opponent scout
report and league averages.

One row per team per match (so two rows a match): score, result, quarter by
quarter scores, and team totals summed from that team's player stats (the
team stats endpoint leaves the extended stats empty). Rates and percentages
are never summed; score involvements are not summed either (one score
involves several players). Uses the same unpublished API, token flow and
1.5 s delay as afl_api_scraper.py; see that file's notes.

Usage:
    python league_scraper.py            # 2025 and 2026
    python league_scraper.py 2026

Writes league_team_games.csv. Checks at the end: Fremantle's scores and
quarter scores against the AFL Tables CSV, and kicks + handballs =
disposals on every team total.
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import afl_api_scraper as A

ITEM_URL = "https://api.afl.com.au/cfs/afl/matchItem/{}"
# Per player counts summed into team totals.
COUNTS = [
    "kicks", "handballs", "disposals", "marks", "tackles", "goals", "behinds", "hitouts",
    "inside50s", "rebound50s", "clangers", "frees_for", "frees_against", "one_percenters",
    "bounces", "goal_assists", "contested_possessions", "uncontested_possessions",
    "contested_marks", "marks_inside50", "centre_clearances", "stoppage_clearances",
    "total_clearances", "metres_gained", "intercepts", "turnovers", "tackles_inside50",
    "shots_at_goal", "pressure_acts", "def_half_pressure_acts", "spoils", "ground_ball_gets",
    "f50_ground_ball_gets", "score_launches", "hitouts_to_advantage", "effective_disposals",
    "effective_kicks", "intercept_marks", "marks_on_lead",
]


def season_matches(year):
    matches = A.get(A.MATCHES_URL.format(A.comp_season_id(year)))["matches"]
    return [m for m in matches if m.get("status") == "CONCLUDED"]


def quarter_scores(item, side):
    """Cumulative score at the end of each quarter for one side. The API gives
    each quarter's own points (checked against AFL Tables), so add them up."""
    periods = item["score"][f"{side}TeamScore"].get("periodScore") or []
    pts = [p["score"]["totalScore"] for p in sorted(periods, key=lambda p: p["periodNumber"])][:4]
    cum = [sum(pts[:i + 1]) for i in range(len(pts))]
    return cum + [None] * (4 - len(cum))


def scrape_match(m, year, warnings):
    mid = m["providerId"]
    pdata = A.get(A.PLAYER_URL.format(mid))
    item = A.get(ITEM_URL.format(mid))
    start = m["utcStartTime"][:10]
    tz = ZoneInfo(m["venue"].get("timezone") or "Australia/Perth")
    date_local = (datetime.strptime(m["utcStartTime"], "%Y-%m-%dT%H:%M:%S.%f%z")
                  .astimezone(tz).strftime("%Y-%m-%d"))
    rnd = m["round"]
    rows = []
    for side, other in (("home", "away"), ("away", "home")):
        players = [A.player_row({}, p) for p in pdata.get(f"{side}TeamPlayerStats", [])]
        if not players:
            warnings.append(f"{mid}: no {side} player stats")
        tot = {c: sum(p.get(c) or 0 for p in players) for c in COUNTS}
        if tot["kicks"] + tot["handballs"] != tot["disposals"]:
            warnings.append(f"{mid} {side}: kicks + handballs != disposals")
        s, o = m[side]["score"], m[other]["score"]
        margin = s["totalScore"] - o["totalScore"]
        q_for, q_against = quarter_scores(item, side), quarter_scores(item, other)
        rows.append({
            "season": year, "api_round": rnd["name"], "round_number": rnd["roundNumber"],
            "is_final": "Final" in rnd["name"], "date_local": date_local, "utc_date": start,
            "match_id": mid, "venue": m["venue"].get("name"),
            "team": A.team_name(m[side]["team"]["name"]),
            "opponent": A.team_name(m[other]["team"]["name"]),
            "is_home": side == "home",
            "score_for": s["totalScore"], "score_against": o["totalScore"],
            "goals_for": s["goals"], "behinds_for": s["behinds"],
            "goals_against": o["goals"], "behinds_against": o["behinds"],
            "margin": margin, "result": "W" if margin > 0 else ("L" if margin < 0 else "D"),
            **{f"q{i + 1}_for": q_for[i] for i in range(4)},
            **{f"q{i + 1}_against": q_against[i] for i in range(4)},
            **tot,
        })
    return rows


def check_against_afl_tables(rows):
    """Fremantle rows must match the AFL Tables scores and quarter scores."""
    try:
        import pandas as pd
        t = pd.read_csv("freo_team_games.csv")
    except (ImportError, FileNotFoundError):
        return ["freo_team_games.csv not available: skipped the Fremantle check"]
    t["d"] = pd.to_datetime(t["date"], format="%a %d-%b-%Y %I:%M %p").dt.date.astype(str)
    out, checked = [], 0
    for r in (r for r in rows if r["team"] == "Fremantle"):
        g = t[(t["season"] == r["season"]) & (t["opponent"] == r["opponent"])
              & (t["d"] == r["date_local"])]
        if len(g) != 1:
            out.append(f"{r['match_id']}: no single AFL Tables game for {r['opponent']} {r['date_local']}")
            continue
        g = g.iloc[0]
        checked += 1
        if (g["freo_score"], g["opp_score"]) != (r["score_for"], r["score_against"]):
            out.append(f"{r['match_id']}: score {r['score_for']}-{r['score_against']} vs "
                       f"AFL Tables {g['freo_score']}-{g['opp_score']}")
        cum = [6 * int(x.split(".")[0]) + int(x.split(".")[1]) for x in g["freo_qtrs"].split()]
        if cum != [r[f"q{i}_for"] for i in range(1, 5)]:
            out.append(f"{r['match_id']}: quarters {[r[f'q{i}_for'] for i in range(1, 5)]} "
                       f"vs AFL Tables {cum}")
    out.append(f"Fremantle games checked against AFL Tables: {checked}")
    return out


def main(years):
    A.session.headers["x-media-mis-token"] = A.session.post(
        A.TOKEN_URL, data=b"", timeout=30).json()["token"]
    rows, warnings = [], []
    for year in years:
        matches = season_matches(year)
        print(f"{year}: {len(matches)} matches")
        for i, m in enumerate(matches, 1):
            try:
                rows += scrape_match(m, year, warnings)
            except (requests.RequestException, KeyError, ValueError) as exc:
                warnings.append(f"{m.get('providerId')}: failed ({exc})")
            if i % 25 == 0:
                print(f"  {i}/{len(matches)}")
    lead = ["season", "api_round", "round_number", "is_final", "date_local", "utc_date",
            "match_id", "venue", "team", "opponent", "is_home"]
    A.write_csv("league_team_games.csv", rows, lead)
    print(f"\nWrote {len(rows)} team rows ({len(rows) // 2} matches).")
    for w in warnings + check_against_afl_tables(rows):
        print("  " + w)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2025, 2026])
