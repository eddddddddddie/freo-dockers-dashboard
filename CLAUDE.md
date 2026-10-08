# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Fremantle Dockers Performance Dashboard

A one-screen "Coach View" Streamlit dashboard of Fremantle Dockers (AFL) stats, player by player
and game by game, with a chatbot (Wharf-ai) that answers questions grounded in the data.
Feature-by-feature descriptions, measurements and history live in `docs/design_notes.md`.

## Commands
- Setup: Python 3.12 (`.python-version`). `python3.12 -m venv .venv && .venv/bin/pip install -r
  requirements.txt` (pins Streamlit 1.64+, pandas 3, plotly 7, anthropic 1.9+).
- Run: `streamlit run app.py`. There is no linter config.
- Tests: `pip install -r requirements-dev.txt`, then `pytest -m "not ui"` (data rules, Wharf-ai
  tools vs plain pandas, login, usage cap, insights, headless app via AppTest) and `pytest -m ui`
  (Playwright: one-screen fit in every view at 1440x790, 1920x960, 1280x680, 1680x950, plus phone
  and tablet layouts). Single test: `pytest tests/test_data.py::test_name` or `-k <pattern>`.
  `.github/workflows/checks.yml` runs both on every push with a test-only login. Locally the
  tests sign in with the login in `.streamlit/secrets.toml` (Streamlit copies secrets into the
  environment at startup, overriding anything set before).
- Data refresh: `python refresh.py` (this season; `python refresh.py 2024` for any season;
  `--dry-run` writes nothing). Runs the three scrapers for one season in a temp folder, swaps that
  season's rows in, and keeps them only if no source lost games, every source has the same Freo
  games, and tests/test_data.py + test_tools.py pass. Writes `data_refresh.json` ("data <date>" in
  the band). `.github/workflows/refresh.yml` runs it Tue and Wed 06:00 Perth, March to September,
  and commits any change, which redeploys the app.
- Individual scrapers (normally run through refresh.py; all default to 2025 2026):
  - `python freo_scraper.py 2025 2026`: AFL Tables, 1.5 s per request (keep the delay; volunteer
    site). Writes `freo_player_games.csv`, `freo_team_games.csv`, `freo_score_events.csv`.
  - `python afl_api_scraper.py 2025 2026` (about 3 min): Champion Data stats from the AFL API.
    Writes `freo_player_games_ext.csv`, `freo_team_games_ext.csv`, `opp_player_games_ext.csv`,
    `freo_squad.csv`. Optional: the app runs on the AFL Tables CSVs alone and hides extra stats.
  - `python league_scraper.py 2025 2026` (about 22 min): `league_team_games.csv`, every team's
    totals per match, for Scout and the ladder. Checks Freo rows against AFL Tables.
  - `python league_events_scraper.py 2025 2026` (about 5.5 min a season, AFL Tables, same
    delay): `league_score_events.csv`, every score of every AFL game in order (home and away as
    AFL Tables lists them), for other clubs' momentum charts. Checks each game's last score.
- Check the merge of the two sources: `python -c "import data; data.ext_check()"`.
- Wharf-ai accuracy eval: `python evals/wharf_eval.py` (34 questions, answers computed with plain
  pandas, deterministic grading; spends about US$0.20; results in `evals/results/`, gitignored).
  Run it after any change to the prompt, tools or model.
- Wharf-ai feedback review: `python evals/review_feedback.py [usage.csv]` turns thumbs-down and
  unmatched-number answers into candidate test cases.
- Coach sessions: `docs/coach_sessions.md` is the usability script; `python
  evals/coach_answers.py [season]` prints its expected answers from the current data.
- Usage database keep-alive: `.github/workflows/keep_db_awake.yml` (Mon and Thu) stops the free
  Supabase project pausing; a failed run means it paused, so restore it in Supabase.

## Secrets
Read through `settings.get()` from `.streamlit/secrets.toml` locally (gitignored) or Streamlit
Cloud Secrets. The repo is public: no credentials, admin emails or unlimited-user lists in code.
- `APP_USERNAME` / `APP_PASSWORD`: password login (required unless Google sign-in is set up; the
  app stays locked without a login). Optional `APP_COOKIE_SECRET`; changing it or the password
  signs everyone out.
- `[auth]` section (redirect_uri, cookie_secret, client_id, client_secret, server_metadata_url):
  switches to Google sign-in via `st.login`. Must be the last section in secrets.toml.
- `ANTHROPIC_API_KEY` (plus `ANTHROPIC_WORKSPACE_ID` for multi-workspace keys), optional
  `ANTHROPIC_BASE_URL`, `FREO_CHAT_MODEL`, `FREO_CHAT_EFFORT`.
- `USAGE_DATABASE_URL` (Postgres, Supabase Session pooler, `docs/supabase_setup.md`). Without it
  the usage log and saved chats are SQLite on local disk, wiped on every Streamlit Cloud redeploy.
- `WHARF_ADMINS`, `WHARF_UNLIMITED` (comma-separated emails, Google sign-in only),
  `WHARF_USER_CAP` (10 questions per person per day; with password login a person is one
  sign-in; `WHARF_LOGIN_CAP` is the old name), `WHARF_DAILY_CAP` (100, shared, midnight Perth), `PLAYER_PHOTOS = "afl"` (loads AFL headshots by URL; never store them in the repo).

## Code map
- Entry and wiring: `app.py` (sign-in gate, top bar, season band, pickers, Wharf-ai panel as a
  fragment) calls `views.render`, which picks a view and lays out cards through `views.arrange`.
- Data: `data.py` loads and merges every CSV (cached) and computes all derived tables, tiles and
  records. Views, takeaways, insights and Wharf-ai's tools all read from it, so stat logic belongs
  here, not in views or charts.
- v2 (`?v2=1`): `v2.py` draws the six places, reusing cards from `views.py` where they fit.
- Presentation: `charts.py` (Plotly figures), `theme.py` (CSS, colours, HTML blocks), `layout.py`
  (window size to card heights and layout mode), `nav.py` (address bar state, `nav.go`),
  `takeaways.py` (card one-liners and chart focus), `marks.py` (band drawings), `sim.py`
  (simulated ground cards), `tour.py` + `components/` (custom JS components: viewport, cookie, tour).
- Wharf-ai: `chatbot.py` (prompt, streaming tool loop) -> `wharf_tools.py` (pandas tools) ->
  `evidence.py` (traces numbers in answers to tool tables); `insights.py` (no-LLM insights);
  `usage.py` (caps, log, saved chats), `admin.py` (usage dialog).
- Infra: `auth.py` (Google or password login, cookie), `settings.py` (secrets/env lookup).
- Data pipeline: the three scrapers, orchestrated by `refresh.py`. The CSVs are committed and are
  the app's only data source.

## Data rules
- Never invent stats we don't have: shot locations, xG, player positions or zones, GPS running.
  The only exception is the ground cards (`sim.py`): places and running are simulated from real
  counts, seeded so they never change, tagged SIMULATED on every figure, and never seen by
  Wharf-ai's tools. The app is a showcase, so in v2 they sit on the pages they belong to (Last
  game, Next opponent, Our season, Players), and the page note tells Wharf-ai they are a demo.
  Other clubs' heat maps share their real team totals across a standard 22 (`sim.team_rows`),
  since their players' stats exist only for games against Freo. `tests/test_sim.py` guards this.
- Draws exist (2024 R12, result "D"). A draw is neither a win nor a loss: records carry `draws`
  (`data.record`, `theme.record_text` gives "12-10-1"). Never count "not a win" as a loss.
- Team `freo_behinds`/`opp_behinds` include rushed behinds; summed player behinds don't. Use team
  totals for goal accuracy, which is pooled (total goals / total scoring shots) everywhere.
- AFL Tables round labels run one ahead of the AFL's (AFL Tables R2 = AFL "Round 1"; no season has
  an R1). Never join sources on round: match on season + opponent + local date within a day.
- AFL Tables has no sub markers on 2026 pages (`sub` blank). Don't infer subs from `pct_played`.
- Merging (`data.py`): players by jumper and only when surnames agree. AFL Tables stays the source
  for every stat both have; the API only adds columns. The API's team endpoint lacks extended
  stats and metres gained, so those team totals are summed from player rows; rates and score
  involvements are never summed.
- The AFL API (`api.afl.com.au/cfs/afl/WMCTok` token, `aflapi.afl.com.au/afl/v2/matches`,
  `cfs/afl/playerStats|teamStats/match/{id}`) is unpublished: URLs and fields can change.
- `freo_score_events.csv` is parsed from raw HTML (`freo_scraper.parse_scoring`) because AFL
  Tables leaves its quarter rows unclosed. Game clock = earlier quarters' full lengths + seconds.
- Momentum (`data.momentum`, `momentum_test`, the Season momentum page, Wharf-ai's `momentum`
  tool) comes from scores only: no other stat is timed. Any club's game: `data.club_game_events`
  (league_score_events.csv) gives the same shape as `game_events`, from that club's side
  (team "Freo" means the side the page is about); matched on season, clubs and date, never round. The shuffle test finds no momentum in
  Freo's games so far; say so rather than implying runs predict the next goal.
- Pressure acts rise when Freo don't have the ball (Freo win more often when the opposition wins
  the pressure count), so the pressure tile has no good/bad colour.
- Tile changes: differentials and accuracy change in absolute units (a % change of a value that
  can cross zero is meaningless); plain averages change in %.
- Correlations ("what drives our margin") are labelled association, not cause.
- Game slices (`D.slice_games`): the data is cut in every season, so tiles compare with the same
  slice of the baseline season; an empty slice shows a message instead of cards.
- The quarter-time check matches games on score only; there are no quarter-by-quarter stats.

## AFL Tables scraper (freo_scraper.py)
- `get_match_list` reads `teams/fremantle/allgames.html` by fixed column position (0-12, 9 skipped);
  `scrape_match` parses each game page's "Match Statistics" tables, mapping headers through
  `STAT_NAMES`. Those indexes and that dict are what break if the site layout changes.
- Blank cells become 0. `to_num` falls back to the raw string, so a surprise value can land as text.
  Names flip from "Last, First". Opposition player rows are discarded (totals only).
- It warns (doesn't stop) when kicks + handballs != disposals or a game has no Freo table.

## Coach View v2 (`?v2=1`, being built; the old views stay the default until switch-over)
- `v2.py`: five places around a coach's week: Last game, Next opponent, Our season, Players,
  Game day. The momentum charts and the simulated ground cards are folded into them (Lab is gone):
  Next opponent shows the club's last 5 games as momentum small multiples
  (`charts.momentum_multiples`, from `data.club_game_events`) beside their heat map. `app.py` hands over to `v2.run` right after sign-in
  and sizing, before the old navigation reads queued moves, then stops.
- Wharf-ai is always visible: a sticky panel beside the page (1000px+ wide and 600px+ tall),
  otherwise docked to the bottom of the screen (`wa_dock`, opens over the page as
  `wa_dock_open`). Never hide it behind a page or a drawer that leaves nothing on screen.
- Pages scroll; there is no one-screen rule in v2, so card text wraps and charts use the fixed
  `CHART_H` / `TALL_H`. One band (`v2.band`), one tile row (`v2.tiles`), one card header
  (`v2.finding`, whose "Ask" button queues its question in `pending_prompt`).
- One click rule: any game opens Last game for it, any player their profile in Players. Move
  with `v2.go(place=...)`. Cards reused from `views.py` call `nav.go(view=...)`; `v2.apply`
  translates those (Match -> Last game, Player -> Players, Scout -> Next opponent).
- Picker first options are real strings (`EVERY_CLUB`, `SQUAD`, `NOBODY`), not None: a None
  value shows Streamlit's "Choose an option" placeholder.
- Phones get a two-line top bar (seasons and icons, then the place picker): the old phone CSS
  sizes the first top-bar column to its content.
- Tests: `tests/test_v2.py` (AppTest, every place) and the `v2` tests in `tests/test_ui.py`.

## Layout and Streamlit gotchas
- Layout modes (`layout.mode`): desktop (1280x600 or more) is one screen with no page scroll;
  split (1000px+ wide, 600px+ tall) and stack scroll, with Wharf-ai beside or above; phone (under
  700px wide) is one scrolling column. Each view hands `views.arrange` three arrangements (desktop
  rows, tablet grid, phone order). Below about 1280px the one-screen layout breaks.
- `components/viewport` reports the window size; `layout.sizes` turns it into chart and panel
  heights, tuned at 1440x790. Cards and the Wharf-ai panel must end level, 9px above the window
  bottom. Titles and tile values ellipsise rather than wrap. Text is 12px minimum. After any
  layout change, check screenshots at 1440x790, 1920x960 and 1280x680, then run `pytest -m ui`.
- On first run the app waits for the window size before drawing (so a phone never flashes the
  desktop layout). The viewport component remembers the last size it sent: every send reruns
  the app, and an extra rerun mid-answer cuts off a streaming Wharf-ai reply.
- Cards are keyed containers (`views.card(name)`, `key="card_<name>"`); CSS targets
  `st-key-card_*` because Streamlit 1.64 dropped the bordered-container wrapper. In 1.64
  segmented controls render as radios (tests use `get_by_role("radio", ...)`).
- Streamlit gives HTML markdown blocks a -1rem bottom margin; `theme.inject_css` cancels it for
  specific blocks. Streamlit chrome and the sidebar are hidden by CSS. That CSS must not match
  `footer` generally: driver.js (the tour) draws its buttons in a `<footer>`.
- Navigation state lives in the URL (`?season=&view=&game=&player=&opp=&vs=&games=`). Clicks go
  through `nav.go()`, which queues the move and reruns, because a control can't change after it
  is drawn. Streamlit doesn't rerun on browser Back/Forward, so the viewport component sends the
  new address and `nav._back_forward` applies it.
- Streamlit doesn't report clicks on heatmap cells or bars: `charts._click_layer` adds invisible
  point markers. After a click is handled, change the chart or table key so the old selection
  isn't reported again on the next rerun.
- The chat panel is an `st.fragment`. A question handed over through
  `st.session_state["pending_prompt"]` arrives on a full-app run, so don't call
  `st.rerun(scope="fragment")` then (Streamlit raises).
- Every card has a one-line takeaway computed in `takeaways.py`; the focus functions there pick the
  mark the takeaway names, and charts get it as `focus=` (full strength, the rest faded).

## Sign-in
- Google mode (when `[auth]` is complete): `st.login`; each person is `auth.person_id(email)` (a
  hash), so Wharf-ai limits and saved chats are per person. Admin and unlimited lists only work here.
- Password mode (local dev, CI): constant-time compare, 30 s pause after 5 failures. "Keep me
  signed in" stores an HMAC-signed token in the `freo_coach_session` cookie, set from JavaScript
  (`components/cookie`) because Streamlit can't set cookies, so it is not HttpOnly.
- Nothing before sign-in shows data, photos or club or sponsor marks.

## Wharf-ai (chatbot)
- Grounding: every number comes from `wharf_tools.py` (fixed pandas queries, no model-written code);
  never state a stat that wasn't calculated. Win-loss records come from team_aggregate sums of
  win/loss/draw, never from counting listed games. When a question needs data we don't have
  (structures, zones, positions), the bot says so.
- `chatbot.stream_answer`: manual streaming tool-use loop on `claude-sonnet-5-5`, adaptive
  thinking, effort `low`, `fallbacks: "default"`. 60 s read timeout, 10 s connect, 2 retries,
  then `chatbot.friendly_error`.
- Within one question the message list is append-only and assistant turns go back whole (thinking
  + tool_use blocks, for preserved thinking); only final text is kept between questions. Tools and
  the stable system prompt are cached; the per-view note sits after the cache breakpoint.
- The API sometimes stops for "tool_use" with no tool call: `_stream_answer` asks again (twice at
  most) rather than send an empty tool-result turn (a 400). Tool-description wording can trigger
  it, so rerun the eval after editing descriptions.
- Tool inputs stream eagerly, so `wharf_tools.run` validates them and returns fixable errors.
  Unknown filter keys are errors (`_check_filters`), never skipped: skipping would answer over
  every game.
- Answer text after tool results isn't streamed by the API (it arrives in one burst); only answers
  with no tool call stream word by word. Don't try to fix this in the app.
- Each answer ends with a hidden `FOLLOWUPS: q | q | q` line, stripped from the stream by
  `chatbot._hold_back_marker` and shown as "Ask next" buttons.
- `show_chart` draws charts from the data itself (the model never supplies numbers). Charts and
  "Show the numbers" tables are stored with the message; only role + content go back to the API.
- `evidence.unbacked` flags numbers in an answer it can't trace to a tool table, the question, the
  insights or earlier tables (directly or by one simple step). The prompt allows one simple step
  from two stated numbers, and never mentioning tools to the reader.
- `insights.py` facts are computed with pandas, no LLM, so they work without an API key.
- Usage (`usage.py`): per-person and shared daily caps; Postgres when `USAGE_DATABASE_URL`
  is set (tables `wharf_questions`, `wharf_chats`, row-level security on, prepared statements off),
  else SQLite. If Postgres is down, Wharf-ai keeps working with writes skipped.
- Tests set `FREO_TESTS` (conftest), so `usage._pg_url` ignores `USAGE_DATABASE_URL`;
  `tests/test_usage_pg.py` empties its tables and runs only with `USAGE_TEST_DATABASE_URL`. The UI
  tests' app gets its own secrets file, never `.streamlit/secrets.toml`.

## Style and constraints
- Look follows fremantlefc.com.au: flat purple #331C54 top bar, #F7F7F7 page, white cards (4px
  radius, no border or shadow), Inter, Source Serif 4 for the title. Never use the Fremantle (or
  any club's) logo, crest, photos, font files or other trademarks; band drawings in `marks.py` are
  our own. Other clubs appear in their colours only (`theme.CLUB_COLOURS`).
- All colours live in `theme.COLORS` / `RAMP` / `DIVERGE` / `SERIES` / `HEAT` (nothing hard-coded
  elsewhere) and pass the dataviz validator: Freo #61359C, opposition #008CA2, win #288B2C, loss
  #D42325. Green vs red fails red-green colour vision, so every win/loss mark also carries a W/L
  letter or a direction. Maroon can't be the opposition colour (too close to loss red).
- Chart ink (`theme.style_fig`): no gridlines or axis lines, only meaningful lines (zero, average,
  median); horizontal, thinned x labels (`charts._round_ticks`), never rotated; label lines and
  marks directly instead of legends.
- Sanity-check every displayed number (kicks + handballs = disposals; % change maths).
- In written text and UI copy, don't use em dashes.

## Later
- Live in-game data is licensed (Champion Data) and out of scope; in-game use is the manual
  quarter-time check.
