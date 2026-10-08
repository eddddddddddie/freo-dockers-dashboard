"""
Every score in every AFL game, in order (source: afltables.com scoring progression)

Run:     python league_events_scraper.py              (defaults to 2025 and 2026)
         python league_events_scraper.py 2024 2025 2026
About 1.5 s a game (the polite delay), so about 5.5 minutes a season.

Output (in the current folder):
  league_score_events.csv  one row per score: season, round, date, home and away
                           clubs (as AFL Tables lists them, home on the left), the
                           event number, quarter, quarter length and seconds into it,
                           the club that scored, goal or behind, player (blank for a
                           rushed behind) and the running home and away scores.

Checks: every game's last score must equal its final score on the page; games
with no scoring progression are reported as warnings at the end.
"""

import csv
import re
import sys

from bs4 import BeautifulSoup

from freo_scraper import BASE, clean, fetch, parse_scoring

FIELDS = ["season", "round", "date", "home", "away", "event", "quarter", "quarter_secs", "secs",
          "team", "kind", "player", "home_score", "away_score"]


def game_urls(year):
    """Every game page linked from the season page, in order."""
    soup = BeautifulSoup(fetch(f"{BASE}seas/{year}.html"), "html.parser")
    seen, urls = set(), []
    for a in soup.find_all("a", href=re.compile(rf"stats/games/{year}/\d+\.html")):
        href = a["href"]
        url = href if href.startswith("http") else BASE + href.split("afl/")[-1].lstrip("./")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def game_header(html):
    """(round, ISO date, [home final, away final]) from the page's top table."""
    text = clean(re.sub(r"<[^>]+>", " ", html[:6000]))
    rnd = re.search(r"Round:\s*(.+?)\s+Venue:", text)
    date = re.search(r"Date:\s*\w+,\s*(\d{1,2})-(\w{3})-(\d{4})", text)
    iso = None
    if date:
        from datetime import datetime
        iso = datetime.strptime(" ".join(date.groups()), "%d %b %Y").strftime("%Y-%m-%d")
    finals = [int(x) for x in re.findall(r"\d+\.\d+\.<b>(\d+)</b></td></tr>", html[:6000])]
    return (rnd.group(1).strip() if rnd else ""), iso, finals


def scrape_game(url, year):
    html = fetch(url)
    events, (home, away) = parse_scoring(html)
    rnd, date, finals = game_header(html)
    rows = [{"season": year, "round": rnd, "date": date, "home": home, "away": away,
             "event": i, "quarter": e["quarter"], "quarter_secs": e["quarter_secs"], "secs": e["secs"],
             "team": home if e["side"] == "left" else away, "kind": e["kind"], "player": e["player"],
             "home_score": e["left"], "away_score": e["right"]}
            for i, e in enumerate(events, 1)]
    return rows, finals


def main():
    years = [int(y) for y in sys.argv[1:]] or [2025, 2026]
    rows, problems = [], []
    for year in years:
        urls = game_urls(year)
        print(f"{year}: {len(urls)} games (about {len(urls) * 1.5 / 60:.0f} min)", flush=True)
        for i, url in enumerate(urls, 1):
            try:
                game, finals = scrape_game(url, year)
            except Exception as e:      # one bad page shouldn't stop the season
                problems.append(f"{url}: {e}")
                continue
            if not game:
                problems.append(f"{url}: no scoring progression")
                continue
            last = (game[-1]["home_score"], game[-1]["away_score"])
            if len(finals) >= 2 and last != (finals[0], finals[-1]):
                problems.append(f"{url}: progression ends {last}, final score {finals[0]}-{finals[-1]}")
            rows += game
            if i % 25 == 0:
                print(f"  {i}/{len(urls)}", flush=True)
    with open("league_score_events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    games = len({(r["season"], r["date"], r["home"]) for r in rows})
    print(f"\nDone: {len(rows)} scores in {games} games. Saved league_score_events.csv")
    if problems:
        print(f"{len(problems)} warnings (first 10):")
        for p in problems[:10]:
            print("  -", p)
    else:
        print("All data checks passed.")


if __name__ == "__main__":
    main()
