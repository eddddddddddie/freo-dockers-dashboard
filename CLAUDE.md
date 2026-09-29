# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Fremantle Dockers Performance Dashboard

## Commands
- Setup: `pip install requests beautifulsoup4` (the dashboard will also need streamlit, pandas, plotly, anthropic)
- Scrape: `python freo_scraper.py 2025 2026` (no args defaults to 2025 and 2026). Takes about
  1.5 s per match, so plan for a minute or so per season. Writes both CSVs into the current directory.
- Advanced stats: `python afl_api_scraper.py 2025 2026` (same defaults, about 3 minutes for both
  seasons). Writes `freo_player_games_ext.csv` and `freo_team_games_ext.csv`. Optional: the
  dashboard runs on the AFL Tables CSVs alone and hides the extra stats.
- Check the merge: `python -c "import data; data.ext_check()"` (coverage, surname mismatches,
  and where the two sources disagree on shared stats).
- Run: `streamlit run app.py`. There are no tests or linter config.

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
  - Round labels are AFL Tables' own, and neither season has an R1. They run one ahead of the
    AFL's numbering (AFL Tables R2 = AFL "Round 1"), so never join sources on round.
- Advanced stats come from the AFL match centre API (`afl_api_scraper.py`), which is unpublished and
  undocumented: a token from a POST to `api.afl.com.au/cfs/afl/WMCTok`, the fixture from
  `aflapi.afl.com.au/afl/v2/matches`, then `cfs/afl/playerStats/match/{id}` and `teamStats/match/{id}`.
  URLs and fields can change without notice. The data is Champion Data's.
  - Adds pressure acts, metres gained, score involvements, centre vs stoppage clearances,
    intercepts, disposal efficiency, turnovers, contest one-on-ones, ground ball gets and more.
  - The team endpoint returns no extended stats and leaves metres gained empty, so those team
    totals are summed from player rows (both sides). Rates and score involvements are never summed.
    The scraper checks summed kicks, handballs and tackles against the team endpoint.
  - `data.py` merges by season + opponent + local date (within a day), players by jumper, and only
    when surnames agree. AFL Tables stays the source for every stat both have; the API only adds
    columns. As of 2026-09-29 all 51 games and 1173 player rows match; shared stats differ in a
    handful of rows (e.g. one Erasmus handball in 2026 R5, rebound 50s in 4 games).
  - Pressure acts track with not having the ball: Freo win more often when the opposition wins the
    pressure count, so the pressure tile has no good/bad colour.
- Still not available anywhere we use: shot locations, xG, player positions or zones. Do not invent these.

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

## Dashboard layout (single Coach View, no other pages)
One screen, laid out for a 1440x900 display with no page scroll (`app.py` -> `views.render`).
Streamlit chrome and the sidebar are hidden by CSS in `theme.inject_css`; chart heights are
fixed pixels (`MID_H`, `BOT_H` in `views.py`), so check the fit with a 1440x790 screenshot
after any layout change.
- Header: season toggle (2025 / 2026), record, win rate, avg for/against/margin, last 5, data freshness.
- 8 tiles: season value, change vs baseline season, per-game sparkline. Differentials and goal
  accuracy change in absolute units (a % change of a value that can cross zero is meaningless);
  plain averages change in %. Accuracy is pooled (total goals / total scoring shots).
- Middle row: margin by game, "where we win" (win rate when each side wins the count), quarter
  pattern (from the cumulative quarter score strings).
- Bottom row: role leaders (most games led + per game avg), player form heatmap (last 6 games vs
  the player's own season average, stat picker), top goalkickers.
- Chatbot opens in a dialog from the header button.

## Chatbot
- Chat panel available on every page. Answers must be grounded in the loaded CSVs:
  compute numbers with code, then explain. Never state a stat that wasn't calculated.
- Box-score data shows what happened, not structures or zones. The bot should say so
  when a question needs data we don't have.
- Needs ANTHROPIC_API_KEY from the environment (never hard-code it). Multi-workspace
  keys also need ANTHROPIC_WORKSPACE_ID (`wrkspc_...` from the console).

## Suggested stack
Python + Streamlit + pandas + Plotly (simple to run locally), unless a better option is agreed.

## Style and constraints
- Freo-style purple and white theme. Do NOT use the Fremantle club logo or other trademarks.
- Sanity-check every displayed number (e.g. kicks + handballs = disposals; % change maths).
- In written text and UI copy, don't use em dashes.

## Later
- In-game use: start with manual quarter-time input compared against season patterns.
  Live data feeds are licensed (Champion Data) and out of scope for v1.
