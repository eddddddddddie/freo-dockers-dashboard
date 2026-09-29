"""
Fremantle Dockers game-by-game stats scraper (source: afltables.com)

Setup:   pip install requests beautifulsoup4
Run:     python freo_scraper.py              (defaults to 2025 and 2026)
         python freo_scraper.py 2024 2025 2026

Outputs (in the same folder):
  freo_player_games.csv  one row per player per game
  freo_team_games.csv    one row per game: Freo totals vs opposition totals
"""

import csv
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://afltables.com/afl/"
ALLGAMES_URL = BASE + "teams/fremantle/allgames.html"
TEAM_NAME = "Fremantle"
DELAY_SECONDS = 1.5  # be polite: AFL Tables is a volunteer-run site
HEADERS = {"User-Agent": "Mozilla/5.0 (personal Fremantle stats project)"}

STAT_NAMES = {
    "KI": "kicks", "MK": "marks", "HB": "handballs", "DI": "disposals",
    "GL": "goals", "BH": "behinds", "HO": "hitouts", "TK": "tackles",
    "RB": "rebound_50s", "IF": "inside_50s", "CL": "clearances",
    "CG": "clangers", "FF": "frees_for", "FA": "frees_against",
    "BR": "brownlow_votes", "CP": "contested_poss", "UP": "uncontested_poss",
    "CM": "contested_marks", "MI": "marks_inside_50", "1%": "one_percenters",
    "BO": "bounces", "GA": "goal_assists", "%P": "pct_played",
}
STAT_COLS = list(STAT_NAMES.values())


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return r.text


def clean(text):
    return text.replace("\xa0", " ").strip()


def to_num(text):
    text = clean(text)
    if text == "":
        return 0  # AFL Tables leaves zeros blank
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def get_match_list(years):
    """Read Freo's all-games page and return match info for the chosen years."""
    soup = BeautifulSoup(fetch(ALLGAMES_URL), "html.parser")
    matches = []
    for a in soup.find_all("a", href=re.compile(r"stats/games/(\d{4})/\d+\.html")):
        year = int(re.search(r"stats/games/(\d{4})/", a["href"]).group(1))
        if year not in years:
            continue
        cells = [clean(td.get_text(" ")) for td in a.find_parent("tr").find_all("td")]
        # Columns: Rnd, T, Opponent, Scoring, F, Scoring, A, R, M, W-D-L, Venue, Crowd, Date
        if len(cells) < 13:
            print(f"  ! Unexpected row layout, skipping: {cells}")
            continue
        href = a["href"]
        url = href if href.startswith("http") else BASE + href.split("afl/")[-1].lstrip("./")
        matches.append({
            "season": year,
            "round": cells[0],
            "type": {"H": "Home", "A": "Away", "F": "Final"}.get(cells[1], cells[1]),
            "opponent": cells[2],
            "freo_qtrs": cells[3],
            "freo_score": to_num(cells[4]),
            "opp_qtrs": cells[5],
            "opp_score": to_num(cells[6]),
            "result": cells[7],
            "margin": to_num(cells[8]),
            "venue": cells[10],
            "crowd": to_num(cells[11]),
            "date": cells[12],
            "url": url,
        })
    return matches


def parse_stats_table(table):
    """Return (team_name, player_rows, totals_dict) for one 'Match Statistics' table."""
    rows = table.find_all("tr")
    title = clean(rows[0].get_text(" "))
    team = title.split(" Match Statistics")[0].strip()

    header_row = next(r for r in rows if "Player" in [clean(c.get_text()) for c in r.find_all(["th", "td"])])
    headers = [clean(c.get_text()) for c in header_row.find_all(["th", "td"])]

    players, totals = [], {}
    for r in rows[rows.index(header_row) + 1:]:
        cells = r.find_all(["td", "th"])
        if not cells:
            continue
        first = clean(cells[0].get_text(" "))
        if first in ("Totals", "Opposition"):
            if first == "Totals":
                values = [to_num(c.get_text()) for c in cells[1:]]
                for h, v in zip(headers[2:], values):
                    if h in STAT_NAMES:
                        totals[STAT_NAMES[h]] = v
            continue
        if len(cells) != len(headers):
            continue  # skip non-player rows
        record = {}
        jumper_text = first
        record["jumper"] = to_num(re.sub(r"[^\d]", "", jumper_text) or "")
        record["sub"] = "on" if "↑" in jumper_text else ("off" if "↓" in jumper_text else "")
        name = clean(cells[1].get_text(" "))
        if "," in name:
            last, first_name = [p.strip() for p in name.split(",", 1)]
            name = f"{first_name} {last}"
        record["player"] = name
        for h, c in zip(headers[2:], cells[2:]):
            if h in STAT_NAMES:
                record[STAT_NAMES[h]] = to_num(c.get_text())
        players.append(record)
    return team, players, totals


def scrape_match(match):
    soup = BeautifulSoup(fetch(match["url"]), "html.parser")
    tables = [t for t in soup.find_all("table") if "Match Statistics" in t.get_text()[:200]]
    freo_players, freo_totals, opp_totals = [], {}, {}
    for t in tables:
        try:
            team, players, totals = parse_stats_table(t)
        except StopIteration:
            continue
        if team == TEAM_NAME:
            freo_players, freo_totals = players, totals
        elif team:
            opp_totals = totals
    return freo_players, freo_totals, opp_totals


def main():
    years = [int(y) for y in sys.argv[1:]] or [2025, 2026]
    print(f"Fetching Fremantle match list for {years}...")
    matches = get_match_list(years)
    print(f"Found {len(matches)} matches. Scraping (about {len(matches) * DELAY_SECONDS / 60:.0f} min)...")

    game_cols = ["season", "round", "date", "type", "opponent", "venue", "result", "margin"]
    player_rows, team_rows, problems = [], [], []

    for i, m in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] {m['season']} {m['round']} vs {m['opponent']}")
        try:
            players, freo_tot, opp_tot = scrape_match(m)
        except Exception as e:
            problems.append(f"{m['season']} {m['round']}: {e}")
            continue
        if not players:
            problems.append(f"{m['season']} {m['round']}: no Freo player table found")
        for p in players:
            player_rows.append({**{k: m[k] for k in game_cols}, **p})
            if p.get("disposals") != p.get("kicks", 0) + p.get("handballs", 0):
                problems.append(f"{m['season']} {m['round']} {p['player']}: kicks+handballs != disposals (column misalignment?)")
        team_row = {k: m[k] for k in game_cols + ["freo_score", "opp_score", "freo_qtrs", "opp_qtrs", "crowd"]}
        team_row.update({f"freo_{k}": v for k, v in freo_tot.items() if k != "pct_played"})
        team_row.update({f"opp_{k}": v for k, v in opp_tot.items() if k != "pct_played"})
        team_rows.append(team_row)

    with open("freo_player_games.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=game_cols + ["jumper", "player", "sub"] + STAT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(player_rows)

    team_fields = sorted({k for r in team_rows for k in r}, key=lambda k: (k not in game_cols, k))
    with open("freo_team_games.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=team_fields)
        w.writeheader()
        w.writerows(team_rows)

    print(f"\nDone: {len(player_rows)} player-game rows, {len(team_rows)} games.")
    print("Saved freo_player_games.csv and freo_team_games.csv")
    if problems:
        print(f"\n{len(problems)} warnings (first 10 shown; paste these to Claude if any):")
        for p in problems[:10]:
            print("  -", p)
    else:
        print("All data checks passed.")


if __name__ == "__main__":
    main()
