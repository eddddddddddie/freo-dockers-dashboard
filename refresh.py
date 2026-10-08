"""Refresh one season of data, safely.

    python refresh.py            # this season (Perth date)
    python refresh.py 2024       # add or refresh any season
    python refresh.py --dry-run  # scrape and report, write nothing

The scrapers each write their files from scratch with only the seasons they
are given, so this runs them for one season in a temporary folder, then puts
that season's rows into the existing files in place of the old ones (other
seasons are kept as they are). The new files are written only if:
  - the season didn't lose games (a failed page must never shrink the data),
  - every game has all its sources (AFL Tables, the AFL match centre and the
    league file), so the merge in data.py lines up,
  - the data tests pass (tests/test_data.py and tests/test_tools.py: kicks +
    handballs = disposals, score = 6 x goals + behinds, player sums = team
    totals, quarter strings, the API merge, the league file).
If anything fails the old files are put back and it exits with an error.
Nothing new to add leaves the files untouched (exit 0, "No new data").
On success it writes data_refresh.json (when, which season, games per season),
which the app shows as the data date.

Run by .github/workflows/refresh.yml twice a week in the season, which commits
any change, so the app redeploys with the new games.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("Australia/Perth")
META = "data_refresh.json"
# Scraper, then the files it writes (each has a season column). In this order:
# league_scraper checks its Fremantle rows against the fresh AFL Tables file.
STEPS = [
    ("freo_scraper.py", ["freo_player_games.csv", "freo_team_games.csv", "freo_score_events.csv"]),
    ("afl_api_scraper.py", ["freo_player_games_ext.csv", "freo_team_games_ext.csv",
                            "opp_player_games_ext.csv", "freo_squad.csv"]),
    ("league_scraper.py", ["league_team_games.csv"]),
    ("league_events_scraper.py", ["league_score_events.csv"]),   # every score of every game
]
GAMES = {"freo_team_games.csv": "Fremantle games (AFL Tables)",
         "freo_team_games_ext.csv": "Fremantle games (AFL match centre)"}


def _read(path):
    try:
        return pd.read_csv(path, low_memory=False)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None


def scrape(season, work):
    """Run every scraper for one season in `work`. Returns their output."""
    log = []
    for script, _ in STEPS:
        print(f"Running {script} {season} ...", flush=True)
        run = subprocess.run([sys.executable, os.path.join(ROOT, script), str(season)],
                             cwd=work, capture_output=True, text=True)
        log.append(f"--- {script}\n{run.stdout[-3000:]}{run.stderr[-2000:]}")
        if run.returncode:
            raise SystemExit(f"{script} failed:\n{run.stderr[-2000:]}")
    return "\n".join(log)


def merge(season, work):
    """{file: merged DataFrame} for the files whose rows for `season` changed."""
    out, problems = {}, []
    for _, files in STEPS:
        for name in files:
            old, new = _read(os.path.join(ROOT, name)), _read(os.path.join(work, name))
            if new is None or not len(new) or "season" not in new.columns:
                continue                       # nothing for this season (yet)
            new = new[new["season"] == season]
            if old is None:
                merged = new
            else:
                before = old[old["season"] == season]
                if name in GAMES and len(new) < len(before):
                    problems.append(f"{GAMES[name]}: {season} would drop from {len(before)} "
                                    f"to {len(new)} games")
                    continue
                cols = list(old.columns) + [c for c in new.columns if c not in old.columns]
                merged = pd.concat([old[old["season"] != season], new], ignore_index=True)[cols]
                merged = merged.sort_values("season", kind="stable").reset_index(drop=True)
                same = (len(before) == len(new) and
                        before.reset_index(drop=True).astype(str).equals(
                            new[before.columns].reset_index(drop=True).astype(str)))
                if same and list(new.columns) == list(before.columns):
                    continue
            out[name] = merged
    return out, problems


def check_counts(files):
    """Every source must have the same Fremantle games, season by season."""
    def per_season(name, freo_only=False):
        df = files.get(name)
        if df is None:
            df = _read(os.path.join(ROOT, name))
        if df is None:
            return {}
        if freo_only:
            df = df[df["team"] == "Fremantle"]
        return df.groupby("season").size().to_dict()

    tables = per_season("freo_team_games.csv")
    sources = {"AFL match centre": per_season("freo_team_games_ext.csv"),
               "league file": per_season("league_team_games.csv", freo_only=True)}
    return [f"{label} has {got.get(s, 0)} Fremantle games in {s}, AFL Tables has {n}"
            for label, got in sources.items() for s, n in tables.items() if got.get(s, 0) != n], tables


def run_tests():
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "not ui",
           "tests/test_data.py", "tests/test_tools.py"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-3000:]


def main(argv):
    dry = "--dry-run" in argv
    seasons = [int(a) for a in argv if a.isdigit()]
    season = seasons[0] if seasons else datetime.now(TZ).year
    with tempfile.TemporaryDirectory() as work:
        log = scrape(season, work)
        files, problems = merge(season, work)
    if problems:
        print(log)
        raise SystemExit("Refused:\n  " + "\n  ".join(problems))
    if not files:
        print(f"No new data for {season}.")
        return 0
    mismatch, games = check_counts(files)
    for name, df in files.items():
        n = int((df["season"] == season).sum())
        print(f"{name}: {n} rows for {season}")
    if mismatch:
        print(log)
        raise SystemExit("Refused, sources out of step (try again later, one may lag):\n  "
                         + "\n  ".join(mismatch))
    if dry:
        print("Dry run: nothing written.")
        return 0
    backup = tempfile.mkdtemp()
    for name in files:
        if os.path.exists(os.path.join(ROOT, name)):
            shutil.copy2(os.path.join(ROOT, name), backup)
    for name, df in files.items():
        df.to_csv(os.path.join(ROOT, name), index=False)
    ok, out = run_tests()
    if not ok:
        for name in files:                       # put the old files back
            src = os.path.join(backup, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ROOT, name))
            else:
                os.remove(os.path.join(ROOT, name))
        print(out)
        raise SystemExit("Data tests failed: the old files are back in place.")
    shutil.rmtree(backup, ignore_errors=True)
    meta = {"updated": datetime.now(TZ).isoformat(timespec="minutes"), "season": season,
            "games": {str(s): int(n) for s, n in sorted(games.items())}}
    with open(os.path.join(ROOT, META), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Updated {', '.join(files)}. Games per season: {meta['games']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
