# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Fremantle Dockers Performance Dashboard

## Commands
- Setup: `pip install requests beautifulsoup4` (the dashboard will also need streamlit, pandas, plotly, anthropic)
- Scrape: `python freo_scraper.py 2025 2026` (no args defaults to 2025 and 2026). Takes about
  1.5 s per match, so plan for a minute or so per season. Writes both CSVs into the current directory.
- There are no tests, linter config, or git repo yet.

## Goal
Build a player-by-player, game-by-game stats dashboard for the Fremantle Dockers (AFL),
with a built-in chatbot that answers tactical questions grounded in the data.
Inspiration: an Aston Villa performance dashboard (side nav, season picker,
"current vs baseline" tables, match-by-match trend lines, role leaders).

## Data
- Source: afltables.com (free, public). Be polite: keep the 1.5 s delay between requests.
- `freo_scraper.py` (already written) builds two CSVs. Run: `python freo_scraper.py 2025 2026`
  - `freo_player_games.csv`: one row per player per game. Game columns: season, round, date,
    type (Home/Away/Final), opponent, venue, result, margin, jumper, player, sub (on/off).
    Stats: kicks, marks, handballs, disposals, goals, behinds, hitouts, tackles, rebound_50s,
    inside_50s, clearances, clangers, frees_for, frees_against, brownlow_votes,
    contested_poss, uncontested_poss, contested_marks, marks_inside_50, one_percenters,
    bounces, goal_assists, pct_played.
  - `freo_team_games.csv`: one row per game, Freo totals (`freo_*`) vs opposition totals (`opp_*`),
    plus scores, quarter-by-quarter scoring strings, crowd.
- Scraped 2026-09-29 with no warnings: 51 games (2025: 24, 2026: 27), 23 players per game, 1173 player rows.
  Player sums match team totals, score = 6 x goals + behinds, and margin = freo_score - opp_score.
- Data quirks to handle in the dashboard:
  - Team `freo_behinds`/`opp_behinds` include rushed behinds; summed player behinds don't. Use team totals for goal accuracy.
  - AFL Tables doesn't mark substitutes on 2026 pages, so `sub` is blank for all of 2026. Don't infer subs
    from low `pct_played` (ruckmen routinely play around 45%).
  - Round labels are AFL Tables' own, and neither season has an R1.
- Not available from AFL Tables: metres gained, pressure acts, score involvements, shot
  locations, xG. Footywire could add some advanced stats later. Do not invent these.

## Scraper internals (freo_scraper.py)
- Two-stage flow: `get_match_list` reads Freo's `teams/fremantle/allgames.html` and takes game
  metadata (round, H/A/F, scores, quarter strings, venue, crowd, date) from fixed column positions
  (index 0-12; index 9, W-D-L, is skipped). After that, `scrape_match` fetches each
  `stats/games/<year>/<id>.html` page and parses every table whose first 200 chars contain "Match Statistics".
- `parse_stats_table` maps columns through the AFL Tables header abbreviations in `STAT_NAMES`
  (KI, MK, HB, ... %P). If the site layout changes, this dict and the allgames column indexes are what break.
- Team identity comes from the table title (`"<Team> Match Statistics"`) compared against `TEAM_NAME = "Fremantle"`.
  Opposition data is kept as totals only; opposition player rows are thrown away.
- Parsing conventions: blank cells become 0 (AFL Tables leaves zeros blank). `to_num` falls back to returning
  the raw string, so an unexpected value can end up as text in a numeric column. Names get flipped from
  "Last, First" to "First Last". The ↑/↓ markers on the jumper cell become `sub` = on/off.
- `pct_played` is dropped from team totals. The team CSV columns are sorted: game columns first, then alphabetical.
- Built-in check: kicks + handballs == disposals on every player row. Failures, plus matches with no
  Freo table, are collected and printed as warnings at the end instead of stopping the run.

## Dashboard pages
1. Home: season record, results strip, key numbers vs previous season
2. Midfield & Contest: clearances, contested possessions, inside 50s, Freo vs opposition by round
3. Ball Movement & Scoring: disposals, marks, goal accuracy (goals vs behinds), goal assists
4. Defence: rebound 50s, one percenters, opposition inside 50s and scores
5. Players: pick any player, game-by-game form, last-5 average, season comparison
6. Role leaders (per game): Ball Winner (contested poss), Tackler, Clearances, Rebounder
   (rebound 50s), Spoiler (one percenters), Forward Threat (goals + goal assists)
- Global season selector (2025 / 2026) and a "current vs baseline" table with correct % change.
- Differential insights, e.g. "win rate when Freo wins the clearance count".

## Chatbot
- Chat panel available on every page. Answers must be grounded in the loaded CSVs:
  compute numbers with code, then explain. Never state a stat that wasn't calculated.
- Box-score data shows what happened, not structures or zones. The bot should say so
  when a question needs data we don't have.
- Needs an Anthropic API key read from an environment variable (ANTHROPIC_API_KEY). Never hard-code it.

## Suggested stack
Python + Streamlit + pandas + Plotly (simple to run locally), unless a better option is agreed.

## Style and constraints
- Freo-style purple and white theme. Do NOT use the Fremantle club logo or other trademarks.
- Sanity-check every displayed number (e.g. kicks + handballs = disposals; % change maths).
- In written text and UI copy, don't use em dashes.

## Later
- In-game use: start with manual quarter-time input compared against season patterns.
  Live data feeds are licensed (Champion Data) and out of scope for v1.
