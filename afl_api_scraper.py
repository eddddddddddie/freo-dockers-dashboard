"""
Fremantle Dockers advanced stats from the AFL match centre API.

Adds the Champion Data stats AFL Tables does not publish (pressure acts,
metres gained, score involvements, centre vs stoppage clearances, intercepts,
disposal efficiency, contest one-on-ones and more). The dashboard merges these
onto the AFL Tables CSVs from freo_scraper.py.

This is the unpublished API behind afl.com.au's match centre, not a documented
one: URLs and fields can change without notice. Data is Champion Data's; check
the AFL's terms before displaying it publicly.

Usage:
    python afl_api_scraper.py              # 2025 and 2026
    python afl_api_scraper.py 2026         # one season

Writes into the current directory:
    freo_player_games_ext.csv  one row per Freo player per game
    freo_team_games_ext.csv    one row per game, freo_* vs opp_* totals
    opp_player_games_ext.csv   one row per opposition player per Freo game
    freo_squad.csv             listed squad per season: id, date of birth, height, position

Join keys: season, opponent (AFL Tables naming), local match date (date_local)
and, for players, jumper. Round numbers are NOT a join key: the API's
"Round 1" is AFL Tables' "R2".
"""

import csv
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TEAM_NAME = "Fremantle"
DELAY = 1.5  # seconds between requests, same as freo_scraper.py
HEADERS = {"User-Agent": "Mozilla/5.0 (FreoDockers dashboard)",
           "Origin": "https://www.afl.com.au"}
TOKEN_URL = "https://api.afl.com.au/cfs/afl/WMCTok"
SEASONS_URL = "https://aflapi.afl.com.au/afl/v2/compseasons?competitionId=1&pageSize=100"
MATCHES_URL = "https://aflapi.afl.com.au/afl/v2/matches?compSeasonId={}&pageSize=300"
PLAYER_URL = "https://api.afl.com.au/cfs/afl/playerStats/match/{}"
TEAM_URL = "https://api.afl.com.au/cfs/afl/teamStats/match/{}"

# API team names -> AFL Tables names (as used in freo_team_games.csv).
TEAM_MAP = {
    "Adelaide Crows": "Adelaide", "Geelong Cats": "Geelong",
    "Gold Coast SUNS": "Gold Coast", "GWS GIANTS": "Greater Western Sydney",
    "Sydney Swans": "Sydney", "West Coast Eagles": "West Coast",
}

# Fields that are metadata, fantasy scoring or duplicated elsewhere.
SKIP = {"lastUpdated", "ranking", "dreamTeamPoints", "superGoals", "interchangeCounts"}

# The team stats endpoint returns no extendedStats and leaves metres gained
# empty, so these per player counts are summed into team totals for both
# sides. Rates and percentages are never summed, and neither are score
# involvements (one score involves several players).
SUMMED = ["pressure_acts", "def_half_pressure_acts", "spoils", "ground_ball_gets",
          "f50_ground_ball_gets", "score_launches", "hitouts_to_advantage", "ruck_contests",
          "contest_def_one_on_ones", "contest_def_losses", "contest_off_one_on_ones",
          "contest_off_wins", "intercept_marks", "marks_on_lead", "effective_disposals",
          "effective_kicks", "kickins", "kickins_playon", "metres_gained"]

session = requests.Session()
session.headers.update(HEADERS)
_last = [0.0]


def get(url, **kw):
    wait = DELAY - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    r = session.get(url, timeout=30, **kw)
    _last[0] = time.time()
    r.raise_for_status()
    return r.json()


def snake(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def flatten(stats):
    """Top-level stats plus the nested clearances and extendedStats groups."""
    out = {}
    for k, v in stats.items():
        if k in SKIP:
            continue
        if k == "clearances" and isinstance(v, dict):
            out.update({snake(ck): cv for ck, cv in v.items()})
        elif k == "extendedStats" and isinstance(v, dict):
            out.update({snake(ek): ev for ek, ev in v.items()})
        elif v is not None and not isinstance(v, dict):
            out[snake(k)] = v
    return out


def team_name(api_name):
    return TEAM_MAP.get(api_name, api_name)


def comp_season_id(year):
    for c in get(SEASONS_URL)["compSeasons"]:
        if c.get("name") == f"{year} Toyota AFL Premiership":
            return c["id"]
    raise SystemExit(f"No AFL Premiership season found for {year}")


def freo_matches(year):
    matches = get(MATCHES_URL.format(comp_season_id(year)))["matches"]
    out = []
    for m in matches:
        home, away = m["home"]["team"]["name"], m["away"]["team"]["name"]
        if TEAM_NAME not in (home, away) or m.get("status") != "CONCLUDED":
            continue
        tz = ZoneInfo(m["venue"].get("timezone") or "Australia/Perth")
        start = datetime.strptime(m["utcStartTime"], "%Y-%m-%dT%H:%M:%S.%f%z")
        out.append({
            "season": year,
            "api_round": m["round"]["name"],
            "date_local": start.astimezone(tz).strftime("%Y-%m-%d"),
            "opponent": team_name(away if home == TEAM_NAME else home),
            "freo_side": "home" if home == TEAM_NAME else "away",
            "match_id": m["providerId"],
        })
    return sorted(out, key=lambda g: g["date_local"])


def player_row(game, p):
    ps = p["playerStats"]
    info = ps["player"]
    name = info["playerName"]
    return {**game,
            "jumper": info.get("playerJumperNumber"),
            "player": f"{name.get('givenName', '')} {name.get('surname', '')}".strip(),
            "player_id": info.get("playerId"),
            "time_on_ground_pct": ps.get("timeOnGroundPercentage"),
            **flatten(ps["stats"])}


def scrape_match(game, warnings):
    pdata = get(PLAYER_URL.format(game["match_id"]))
    tdata = get(TEAM_URL.format(game["match_id"]))["teamStats"]
    mid = game["match_id"]
    sides = {"freo_": game["freo_side"], "opp_": "away" if game["freo_side"] == "home" else "home"}
    rows = {prefix: [player_row(game, p) for p in pdata.get(f"{side}TeamPlayerStats", [])]
            for prefix, side in sides.items()}
    for r in rows["freo_"]:
        if r.get("kicks", 0) + r.get("handballs", 0) != r.get("disposals", 0):
            warnings.append(f"{mid} {r['player']}: kicks + handballs != disposals")
    if not rows["freo_"] or not rows["opp_"]:
        warnings.append(f"{mid}: missing player stats for one side")

    team = {**game}
    found = 0
    for t in tdata:
        name = t.get("teamName")
        name = name.get("teamName") if isinstance(name, dict) else name
        prefix = "freo_" if name == TEAM_NAME else "opp_"
        found += prefix == "freo_"
        team.update({prefix + k: v for k, v in flatten(t["stats"]).items()})
    if found != 1 or len(tdata) != 2:
        warnings.append(f"{mid}: expected one Freo and one opposition team row")

    for prefix, players in rows.items():
        # Check the summing against totals the team endpoint does report.
        for col in ("kicks", "handballs", "tackles"):
            summed = sum(r.get(col) or 0 for r in players)
            if team.get(prefix + col) is not None and summed != team[prefix + col]:
                warnings.append(f"{mid}: {prefix}{col} players {summed} vs team {team[prefix + col]}")
        for col in SUMMED:
            team[prefix + col] = sum(r.get(col) or 0 for r in players)
    return rows["freo_"], team, rows["opp_"]


def write_csv(path, rows, lead):
    cols = lead + sorted({k for r in rows for k in r} - set(lead))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main(years):
    session.headers["x-media-mis-token"] = session.post(TOKEN_URL, data=b"", timeout=30).json()["token"]
    players, teams, opp_players, warnings = [], [], [], []
    for year in years:
        games = freo_matches(year)
        print(f"{year}: {len(games)} Freo matches")
        for g in games:
            print(f"  {g['api_round']:<34} {g['opponent']:<24} {g['date_local']}")
            try:
                p, t, o = scrape_match(g, warnings)
            except requests.RequestException as exc:
                warnings.append(f"{g['match_id']}: request failed ({exc})")
                continue
            players += p
            teams.append(t)
            opp_players += o

    game_cols = ["season", "api_round", "date_local", "opponent", "freo_side", "match_id"]
    write_csv("freo_player_games_ext.csv", players, game_cols + ["jumper", "player", "player_id"])
    write_csv("freo_team_games_ext.csv", teams, game_cols)
    # The opposition's players in Freo games (for the match view's leaders).
    write_csv("opp_player_games_ext.csv", opp_players, game_cols + ["jumper", "player", "player_id"])
    print(f"\nWrote {len(players)} player rows, {len(teams)} team rows and "
          f"{len(opp_players)} opposition player rows.")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  " + w)




# ---- Squad details (age, height, position) -----------------------------------------
SQUADS_URL = "https://aflapi.afl.com.au/afl/v2/squads?teamId={}&compSeasonId={}"
TEAMS_URL = "https://aflapi.afl.com.au/afl/v2/teams?competitionId=1&pageSize=50"


def scrape_squads(years, path="freo_squad.csv"):
    """Fremantle's listed squad each season: Champion Data id, date of birth,
    height and position. Writes freo_squad.csv (no token needed)."""
    team_id = next(t["id"] for t in get(TEAMS_URL)["teams"] if t["name"] == TEAM_NAME)
    rows = []
    for year in years:
        squad = get(SQUADS_URL.format(team_id, comp_season_id(year)))["squad"]["players"]
        for entry in squad:
            p = entry["player"]
            rows.append({"season": year, "player_id": p["providerId"],
                         "player": f"{p['firstName']} {p['surname']}",
                         "jumper": entry.get("jumperNumber"), "position": entry.get("position"),
                         "date_of_birth": p.get("dateOfBirth"),
                         "height_cm": p.get("heightInCm") or None})
        print(f"{year}: {sum(r['season'] == year for r in rows)} listed players")
    write_csv(path, rows, ["season", "player_id", "player", "jumper", "position",
                           "date_of_birth", "height_cm"])
    return rows


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or [2025, 2026]
    main(years)
    scrape_squads(years)
