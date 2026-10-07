"""
Fremantle Dockers game-by-game stats scraper (source: afltables.com)

Setup:   pip install requests beautifulsoup4
Run:     python freo_scraper.py              (defaults to 2025 and 2026)
         python freo_scraper.py 2024 2025 2026

Outputs (in the same folder):
  freo_player_games.csv  one row per player per game
  freo_team_games.csv    one row per game: Freo totals vs opposition totals
  freo_score_events.csv  one row per score (goal or behind) in each game, in order,
                         from the page's scoring progression: quarter, time, side,
                         player and the running score
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


def _secs(text):
    """'12m 5s' -> 725."""
    m = re.search(r"(\d+)m\s*(\d+)s", text)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _cell_text(html):
    return clean(re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " "))


def parse_scoring(html):
    """The page's scoring progression: a list of events in order, each
    {quarter, quarter_secs, secs, side ('left'/'right'), kind, player, left, right}
    with the running scores in points, plus the two team names (left, right).

    The table is parsed from the raw HTML because its quarter rows leave a <b>
    and the row unclosed, which nests the rest of the table under them in
    html.parser. Each score row has five cells: the left team's scorer, time,
    running score, time, the right team's scorer."""
    start = html.find('<a name="prog"></a>')
    if start < 0:
        return [], (None, None)
    table = html[start:html.find("</table>", start)]
    teams = [_cell_text(t) for t in re.findall(r"<th width=25%>(.*?)</th>", table)]
    left, right = (teams + [None, None])[:2]
    events, quarter, q_len = [], 0, None
    for row in table.split("<tr>")[1:]:
        q = re.search(r"(1st|2nd|3rd|Final) quarter \((\d+m \d+s)\)", row)
        if q:
            quarter += 1
            q_len = _secs(q.group(2))
            continue
        cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)(?=<td|</tr>|$)", row, re.S)]
        if len(cells) != 5 or not quarter:
            continue
        score = re.findall(r"(\d+)\.(\d+)\.\s*(\d+)", cells[2])
        if len(score) != 2:
            continue                       # the totals row (biggest lead, game time)
        side = "left" if cells[0] else "right"
        what = cells[0] or cells[4]
        kind = "goal" if what.endswith(" goal") else "behind"
        player = re.sub(r"\s+(goal|behind)$", "", what)
        events.append({"quarter": quarter, "quarter_secs": q_len,
                       "secs": _secs(cells[1] if side == "left" else cells[3]),
                       "side": side, "kind": kind,
                       "player": "" if player.lower() == "rushed" else player,
                       "left": int(score[0][2]), "right": int(score[1][2])})
    return events, (left, right)


def score_events(html, match):
    """The scoring progression as rows with Freo's side named: team is "Freo" or
    "Opp", and the running scores are freo_score / opp_score."""
    events, (left, right) = parse_scoring(html)
    freo_left = left == TEAM_NAME
    if not events or TEAM_NAME not in (left, right):
        return []
    rows = []
    for i, e in enumerate(events, 1):
        mine = (e["side"] == "left") == freo_left
        rows.append({
            "event": i, "quarter": e["quarter"], "quarter_secs": e["quarter_secs"],
            "secs": e["secs"], "team": "Freo" if mine else "Opp", "kind": e["kind"],
            "player": e["player"], "rushed": int(e["player"] == ""),
            "freo_score": e["left"] if freo_left else e["right"],
            "opp_score": e["right"] if freo_left else e["left"]})
    return rows


def scrape_match(match):
    html = fetch(match["url"])
    soup = BeautifulSoup(html, "html.parser")
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
    return freo_players, freo_totals, opp_totals, score_events(html, match)


def main():
    years = [int(y) for y in sys.argv[1:]] or [2025, 2026]
    print(f"Fetching Fremantle match list for {years}...")
    matches = get_match_list(years)
    print(f"Found {len(matches)} matches. Scraping (about {len(matches) * DELAY_SECONDS / 60:.0f} min)...")

    game_cols = ["season", "round", "date", "type", "opponent", "venue", "result", "margin"]
    player_rows, team_rows, event_rows, problems = [], [], [], []

    for i, m in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] {m['season']} {m['round']} vs {m['opponent']}")
        try:
            players, freo_tot, opp_tot, events = scrape_match(m)
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
        if not events:
            problems.append(f"{m['season']} {m['round']}: no scoring progression")
        elif (events[-1]["freo_score"], events[-1]["opp_score"]) != (m["freo_score"], m["opp_score"]):
            problems.append(f"{m['season']} {m['round']}: scoring progression ends "
                            f"{events[-1]['freo_score']}-{events[-1]['opp_score']}, "
                            f"final score {m['freo_score']}-{m['opp_score']}")
        event_rows += [{**{k: m[k] for k in ["season", "round", "date", "opponent"]}, **e}
                       for e in events]

    with open("freo_player_games.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=game_cols + ["jumper", "player", "sub"] + STAT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(player_rows)

    team_fields = sorted({k for r in team_rows for k in r}, key=lambda k: (k not in game_cols, k))
    with open("freo_team_games.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=team_fields)
        w.writeheader()
        w.writerows(team_rows)

    event_fields = ["season", "round", "date", "opponent", "event", "quarter", "quarter_secs", "secs",
                    "team", "kind", "player", "rushed", "freo_score", "opp_score"]
    with open("freo_score_events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=event_fields)
        w.writeheader()
        w.writerows(event_rows)

    print(f"\nDone: {len(player_rows)} player-game rows, {len(team_rows)} games, "
          f"{len(event_rows)} scores.")
    print("Saved freo_player_games.csv, freo_team_games.csv and freo_score_events.csv")
    if problems:
        print(f"\n{len(problems)} warnings (first 10 shown; paste these to Claude if any):")
        for p in problems[:10]:
            print("  -", p)
    else:
        print("All data checks passed.")


if __name__ == "__main__":
    main()
