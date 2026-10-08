# Design notes

Feature reference and history for the Coach View: what each view and card shows, how it looks,
measurements and past experiments. Moved from CLAUDE.md on 2026-10-08 so that file can stay
short. CLAUDE.md holds the rules and gotchas and wins where the two differ; update this file
when a feature changes, but don't rely on it being exhaustive.

## Data
- Source: afltables.com (free, public). Be polite: keep the 1.5 s delay between requests.
- `freo_scraper.py` builds three CSVs. Run: `python freo_scraper.py 2025 2026`
  - `freo_player_games.csv`: one row per player per game. Game columns: season, round, date,
    type (Home/Away/Final), opponent, venue, result, margin, jumper, player, sub (on/off).
    Stats: kicks, marks, handballs, disposals, goals, behinds, hitouts, tackles, rebound_50s,
    inside_50s, clearances, clangers, frees_for, frees_against, brownlow_votes,
    contested_poss, uncontested_poss, contested_marks, marks_inside_50, one_percenters,
    bounces, goal_assists, pct_played.
  - `freo_team_games.csv`: one row per game, Freo totals (`freo_*`) vs opposition totals (`opp_*`),
    plus scores, quarter-by-quarter scoring strings, crowd.
  - `freo_score_events.csv`: every score in every game, in order, from each page's scoring
    progression (`freo_scraper.parse_scoring`, parsed from the raw HTML because its quarter rows
    are left unclosed): quarter, quarter length and seconds into it, team (Freo / Opp), goal or
    behind, player (blank and `rushed` = 1 for rushed behinds), running score. Scraped 2026-10-08:
    3390 scores in 74 games; every score adds 6 or 1 to its side and every break matches the
    quarter strings (`tests/test_data.py`). Game clock = earlier quarters' full lengths + seconds.
- Scraped 2026-09-29 with no warnings: 51 games (2025: 24, 2026: 27); 2024 added 2026-10-01 with
  `refresh.py 2024`: 74 games (2024: 23, no finals), 23 players per game, 1702 player rows. The
  same refresh brought in Champion Data's later revisions to 2026 metres gained (a few metres in
  some games).
  Player sums match team totals, score = 6 x goals + behinds, and margin = freo_score - opp_score.
- Draws exist (2024 R12 v Collingwood, 75-75, result "D"). A draw is neither a win nor a loss:
  `data.record` and the other record counts carry `draws`, `theme.record_text` shows "12-10-1",
  and `theme.result_colour` gives draws the neutral grey (with the D letter). Never count
  "not a win" as a loss.
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
- Still not available anywhere we use: shot locations, xG, player positions or zones, GPS
  running. Do not invent these. The one exception is the ground cards below: simulated, and
  say so on everything they show.
- Ground cards (`sim.py`, `views._ground_card`): Match, Player and Scout each carry one card
  that shows its subject on the ground, with no switch to find it (the app is a showcase). Each
  card has its own Heat / Events / Running control: Heat, where they spent the time (pale yellow
  to deep red, `theme.HEAT`, scaled to the 99th percentile); Events,
  their real goals, marks, contested and uncontested possessions at simulated spots; Running,
  simulated GPS. Match (`match_ground_card`, beside the players table): the team in that game,
  running load table. Player (`player_ground_card`, beside the range card): his season, running
  game by game. Scout (`scout_ground_card`, third in the bottom row; Events only, no heat
  map and so no control): the club's players in their games against Freo, attacking right (their roles come from their
  stats, as their positions aren't listed). Counts are the real box score; only the places and
  the GPS running are simulated (listed position, time on ground, work rate), seeded from
  season, round and player so they never change. Every figure carries an amber SIMULATED tag;
  Wharf-ai's tools never see it and its page note says the ground card is a demo. The match
  players table has pixel column widths so it fits beside the card at 1440 (at 1280 the last
  column scrolls inside the table).
  `tests/test_sim.py` checks counts, repeatability and that the real data and Wharf-ai are
  untouched.

## Dashboard layout
The sign-in screen (`auth._splash`, `theme.login_hero`) follows the club site's home page: the
whole page in the club purple (a maroon glow top right, a large faint anchor bottom right), a thin
"Coach View" strip, the headline "The numbers behind *Freo*" in the serif (our own line, not the
club's slogan; the words rise in), one line on what's inside, then the
sign-in straight on the purple: white fields, a white button, white labels. Nothing on it looks
clickable unless it is. A ticker along the bottom (`theme.login_ticker`) lists what's inside,
with no numbers. No club or sponsor marks, no photos and no data before sign-in. Sign-in has two modes (`auth.py`). Google (used when the secrets have a complete `[auth]` section:
redirect_uri, cookie_secret, client_id, client_secret, server_metadata_url): anyone with a
verified Google account signs in through Streamlit's `st.login`; the app never sees a password;
Streamlit keeps the sign-in in its own HttpOnly identity cookie; each person is `person_id(email)`
(a hash), so Wharf-ai limits (`WHARF_USER_CAP`, default 10 a day) and saved chats are per person,
and the usage log records their email. Google OAuth client: web application, redirect URIs
`https://<app>.streamlit.app/oauth2callback` and `http://localhost:8501/oauth2callback`, consent
screen External and In production. `[auth]` must be the last section in secrets.toml.
The fallback (no `[auth]`: local dev, CI) is a login (`auth.require_login`, username/password from secrets,
compared in constant time, 30 s pause after 5 failed tries). "Keep me signed in for 7 days"
(ticked by default) stores a signed token (HMAC-SHA256 over a random session id, the username and
an expiry) in the `freo_coach_session` cookie, set from JavaScript by `components/cookie` because
Streamlit can't set cookies (so not HttpOnly; SameSite=Lax, Secure on https). A new visit, refresh
or opened link with a valid token skips the form (`st.context.cookies`), and the session's
Wharf-ai chat is reloaded (`usage.save_chat` / `load_chat`, same disk caveat as the usage log).
Changing APP_PASSWORD (or APP_COOKIE_SECRET) signs everyone out. The sign-out button (header, next
to ?) clears the cookie. Not yet checked on Streamlit Cloud, where the app runs inside a frame.
One screen with no page scroll, sized to the browser window: the dashboard (`views.render`) on
the left, the Wharf-ai chat panel down the right (`app.chat_panel`, a fragment, so chatting does
not re-render the charts). `components/viewport` is a tiny custom component that reports the
window size (and again on resize); `layout.sizes(height, width)` turns it into the chart heights,
panel height and player-form row count, tuned at 1440x790 and scaled from there (`BAR_H` is the
top bar; titles and tile values ellipsise rather than wrap, so width doesn't change heights; the
cards and the Wharf-ai panel end level, 9px above the window bottom; Match and Player rows take
`views.ROW_GAIN` extra to end level with Season's). The first run uses the 1440x790 design size.
Streamlit chrome and the sidebar are hidden by CSS in `theme.inject_css`. After any layout
change, check the fit with screenshots at 1440x790, 1920x960 and 1280x680.
- Phone layout (window narrower than `layout.PHONE_W` = 700px; `app.PHONE`, `views.set_phone`,
  `theme.inject_phone_css`): one scrolling column instead of one screen. Order: band, a controls
  row (season, view dropdown, ?, sign out; kept on one line by CSS because Streamlit stacks
  columns below 640px), the picker for Match/Player/Scout, Wharf-ai (insight, 3 suggestions,
  chat box; once a chat starts it scrolls inside about half the screen, with a "Dashboard ↓"
  button that scrolls by script, since a #anchor link lands in the wrong place in Streamlit's
  scrolling container), then the cards one per row, and (admins only) Wharf-ai usage at the bottom. Season on a
  phone: tiles 2 to a row, recent games as tappable buttons (8, then "Show all") instead of the
  game strip, then where we win, drivers, quarters, role leaders, player form (the 6-game
  heatmap reads fine at 390px). Player grids keep 6 columns (`views.PHONE_GRID`). Cards grow
  with their content (`views._h`), chart dragging is off so a swipe scrolls the page, tap
  targets are at least 40 to 44px, and the tour has a shorter phone version (`PHONE_STEPS`).
  First run: the app asks for the window size before sign-in, and if someone is signed in
  straight away (cookie, Google) it shows "Loading the Coach View..." until the size arrives
  (the viewport component is told `need` so it resends even if the tab sent it before), so a
  phone never flashes the desktop layout. `tests/test_ui.py::test_phone_layout_scrolls_one_column`
  checks 375x667, 390x844 and 412x915.
- Layout modes (`layout.mode(width, height)`): phone (under 700px wide), desktop (1280x600 or
  more: the one-screen layout), split (landscape tablets, 1000px or wider and 600px or taller)
  and stack (everything else: portrait tablets, landscape phones, small windows). The one-screen
  layout breaks below about 1280px (clipped controls, overlapping heatmap rows), hence the cut-off.
  Stack and split both scroll (`theme.inject_tablet_css`, `layout.scroll_sizes`): band on its own
  line, then a controls row (season, view buttons, usage for admins, ?, sign out) and the picker; tiles
  three to a row; cards two to a row with wide ones (game strip, player grids, player form, game
  flow) across the row; card heights follow content. Stack puts Wharf-ai above the dashboard (4
  suggestions, 3 when the window is under 500px tall) with the "Dashboard ↓" button; split keeps
  it in a column on the right, pinned with `position:sticky` while the dashboard scrolls, as tall
  as the window less 44px (any taller and it slides off the top at the end of the page). Each
  view lists its cards once and hands `views.arrange` three arrangements: desktop rows with
  column ratios, the tablet grid, and the phone order. `test_tablet_layouts` checks 820x1100,
  844x390 and 1180x760.
- Four views: Season, Match, Player, Scout (`views.render*`). Each band leads with one big number
  (record, margin, the player's main average, ladder spot); secondary figures hide below 1760px.
  Tiles are 6 per view (grid sized from the count). Text is 12px minimum. Every card has a
  computed one-line takeaway under its title (`takeaways.py`, `card_title(takeaway=...)`).
  Each chart also shows its takeaway: the focus functions in `takeaways.py` (`swing_stat`,
  `best_worst_quarter`, `top_driver`, `hot_player`, `rank_focus`, `style_marks`) pick the mark
  the text names and the chart gets it as `focus=`: those marks stay full strength (and their
  labels bold), the rest drop to `charts.FADE` opacity in the same hue with muted labels. Trend
  and form charts shade the last 5 games with their average (`charts._last_n_band`, label above
  the plot), and the player trend labels the best and lowest games.
- Where we win (and Scout's How they win) is a dumbbell (`charts.win_dumbbell`): each stat from
  the win rate when the other side won the count to the rate when Freo (the club) did, sorted by
  the gap, the swing labelled in a column at the right. Quarters has a third view, Games
  (`D.quarter_strip`, drawn with `charts.game_strip(show_x=False)`): Q1-Q4 by game, purple Freo
  won the quarter, cyan the opposition, click a cell to open the game. What drives our margin is
  small multiples (`charts.driver_multiples`: a tiny scatter per stat, each game's differential
  across and the margin up on a shared scale, titled with r, strongest first, two to a row and as
  many rows as fit, the takeaway's stat in purple) and a drill-down: click a panel (invisible point markers carry the click, as Streamlit doesn't
  report clicks on bars) for `charts.driver_scatter` (every game's differential against the
  margin, win/loss colours, a least-squares line; click a point to open that game); the back
  arrow returns, and the chart key changes on the way back so the old click isn't reported again.
- Navigation (`nav.py`): the web address holds season / view / game / player / opp
  (`?season=2026&view=Match&game=GF`), so views can be bookmarked and sent. Clicking a game in the
  game strip opens it in Match; clicking a player in Player form, the match player grid, the player
  map or year on year opens their Player view; Opponents can open a club's Scout view. Clicks go
  through `nav.go()`, which queues the move and reruns, because a control can't change after it is
  drawn. Heatmap cells aren't clickable in Streamlit, so `charts._click_layer` adds invisible
  point markers (and pins the axes so they don't pad). Browser Back/Forward: Streamlit doesn't
  rerun on popstate and `st.query_params` keeps the old address on that rerun, so the viewport
  component sends the new address and `nav._back_forward` applies it.
- Player view: band (photo or initials, #, position, age, height from `freo_squad.csv`, and the
  player's best squad ranking as the lead number, e.g. "1st · Metres gained in squad"), tiles with squad rank and change
  on last season, game-by-game trend (pick a stat), squad rank on 12 stats, the range on each stat
  (`charts.player_ranges`: every game a dot as a % of his own season average, the latest ringed
  with its number, each stat's lowest-highest at the right, click a dot to open that game;
  "Show all numbers" gives the per-game table).
- Player vs player: in the Player view, "Compare with..." (next to the player picker; `vs=` in
  the address) swaps the profile for `views.render_compare`: a band with both photos (or
  initials), each ringed in that player's chart colour, both surnames and their
  games together and record in them (`data.games_together`), tiles with each player's average and
  squad rank per stat and a share bar, game by game for both (gaps where one didn't play, dashed
  season averages), squad rank on each stat as a dumbbell (as many stats as fit the height), and a
  stat by stat table (season and last 5; phones show season and gap). Colours: player A Freo
  purple, player B cyan (`charts.PAIR`, validated, CVD dE 17). `data.compare_players` builds the
  rows. Wharf-ai gets comparison questions on that page.
- Coach research: `docs/coach_sessions.md` is a 30-minute task script (six timed tasks plus one
  if time, with the expected answers, what to watch for, note sheet, debrief).
  `python evals/coach_answers.py [season]` works out every expected answer from the current data
  (print it before each round). Re-run the sessions after each design round.
- Top bar (`st-key-topbar`, every layout, after the club site's nav bar): flat purple, edge to
  edge (its wrapper takes negative margins; the CSS-only markdown blocks above it are taken out
  of the flow so there's no gap), the title "*Freo* Coach View" in Source Serif 4 (Google Fonts;
  the club's own font is not used) with "Freo" in italic like the site's headline, the season
  toggle (one button per season in the data; its column scales with the count) and the view
  switch as white nav links with an underline on the selected one (`aria-checked`), then the
  outlined icon buttons: Wharf-ai usage (admins only), ?, sign out. Phones drop the title. No
  ticker in the bar (removed 2026-10-07; insights live in the Wharf-ai panel). Under the bar: the picker and the band, with record, win rate, avg for/against/margin, last 5, data
  freshness and (1600px and wider) the last match score.
- Scout mode (`views.render_scout`, needs league_team_games.csv): pick any club (defaults to the
  last opponent); band with home and away record, ladder spot (computed: 4 points a win, 2 a draw,
  percentage) and form; tiles with the club's value, league rank and Freo's value; style vs league
  (rank of 18 on each stat, club vs Freo); how they win; their quarters; their last 14 games;
  every Freo game against them. Wharf-ai gets `league_aggregate` and `ladder` tools.
  Each club is shown in its own colours (`theme.CLUB_COLOURS`, colours only, no logos): the band
  uses the club's dark colour with an accent stripe, rank chips its dark colour, and the charts a
  chart colour on the club's hue, chosen as the closest to the real club colour that still passes
  the validator against Freo purple and the opponent grey (navy clubs therefore chart as a strong
  blue). Collingwood charts in charcoal with a lighter grey for their opponents.
- First-visit tour (`tour.py`, `components/tour`): driver.js 1.8.0 from jsDelivr, loaded into the
  app page; 12 steps spotlighting each part; runs once per browser (localStorage
  `freoCoachTourDone_v1`): on a first visit a "New here?" prompt points at the pulsing ? button
(Take the tour / close); the tour runs from there or from the ? button any time. driver.js is
  fetched as soon as the component loads, and the ? click is caught by a capture listener on the
  page (so no app rerun) and starts the tour at once (about 0.2 s); steps for cards the current
  view doesn't have are skipped. It never starts over a running tour. The CSS that hides Streamlit's footer must
  not match `footer` generally: driver.js draws its buttons in a `<footer>`.
- Match mode (`views.render_match`): pick one game (most recent first); the band shows the score
  line, Freo purple fading into the opposition's dark club colour with their accent stripe; tiles
  show this game against the season average (sparkline accents that game); tale of the tape (Freo
  vs opposition share per stat, the opposition in their club chart colour, tick at Freo's season
  average share); Momentum (`charts.momentum_chart`, two panels on one game clock: the margin
  after every score as a step line with goals as dots and behinds as ticks in each side's colour,
  the game's biggest run of 3+ goals unanswered shaded and labelled; under it, momentum bars,
  `data.momentum`: the quarter's scores so far, each weighted down by half every 4 minutes
  (`MOMENTUM_HALF_LIFE`), Freo up, the opposition down, back to 0 at each quarter; takeaway like
  "Up 17 in Q4, lost by 7: BRL 4.0 unanswered"; without score events the old game flow card,
  margin at each break, is drawn instead); game leaders for both sides
  (`theme.leaders_pair`, surnames, from `opp_player_games_ext.csv`; Freo only without it) + goals; every Freo
  player in the game (scrolls inside its card). The players card is a stats table (`views._match_players`, `st.dataframe`): every
  player, rating points then 9 stats, each cell the number and a bar against the team's best
  that game (`ProgressColumn`); cells 30%+ above the player's own season average tinted light
  purple and bold, 30%+ below tinted grey (`views.STANDOUT`, on season averages of at least
  `charts.VS_SELF_MIN_AVG`). Sort by clicking a header; selecting a row opens the player (the
  table key changes after, so the old pick isn't reported again). 26px rows, scrolls inside the
  card; on a phone four stats and no RP. The takeaway names the biggest games on own average. Wharf-ai is
  told which match is on screen.
- 6 tiles (`data.TILES`, `data.PLAYER_TILES`): season value, change vs baseline season, per-game sparkline. Differentials and goal
  accuracy change in absolute units (a % change of a value that can cross zero is meaningless);
  plain averages change in %. Accuracy is pooled (total goals / total scoring shots).
- Middle row: game strip (one column per game: result, then margin and key differentials shaded
  orange to purple by who won the count, each row scaled to its 90th percentile gap), "where we win"
  (win rate when each side wins the count), quarters (points per quarter, or average running margin
  at each break in wins vs losses; from the cumulative quarter score strings).
- Bottom row: role leaders (most games led + per game avg, plus top goalkicker), who's up, who's
  down (`charts.form_dumbbell`: each top player's season average, a ring, to his last-3 average,
  purple up, grey down, sorted by the change, which is labelled at the right; as many rows as fit,
  the biggest risers and drops; stat picker), what drives our margin (Pearson r of each differential with margin;
  label it association, not cause).
- Games slice (`D.slice_games`, `D.GAME_SLICES`, `app.slice_picker`): on Season (its picker
  slot) and Player (a third picker), All games / Home / Away / Finals / Wins / Losses / vs top 8
  (each season's own ladder) / Last 10. The data is cut in every season, so tiles compare with the
  same slice of the season before; player rows follow their games. The band says "<slice> only",
  the address keeps `games=`, a click elsewhere keeps the slice and an address sets it (none =
  all games), and Wharf-ai's focus carries ", <slice> only". An empty slice (no 2024 finals) shows
  a plain message instead of the cards.
- Each view's picker has a first option for a page across all its options (no tiles row; the
  cards fill the height, level with the Wharf-ai panel, `views._full_h`; `nav.SQUAD`,
  `nav.ALL_CLUBS`, `nav.QT`, kept in the address as `player=Whole squad`, `opp=All clubs`,
  `game=QT`). The band is the season band. Defaults stay a real player, the last opponent and the
  latest game.
  - Player -> Whole squad (`views.render_squad`): player map (per game averages on two chosen
    stats, median quadrants, dot size = time on ground) | year on year (slope chart, the season
    before -> this one, top 15 with 8+ games in both). Clicking a player opens their profile.
  - Scout -> All clubs (`views.render_clubs`): every game vs each club, all seasons, toughest
    first, and "Ask Wharf-ai about <club>", which hands the question over via
    `st.session_state["pending_prompt"]`; that arrives on a full-app run, so the chat panel must
    not call `st.rerun(scope="fragment")` then (Streamlit raises).
  - Match -> Quarter-time check (`views.render_quarter_time`): enter the margin at a break:
    record, average final margin and net scoring after the break in games within a +/- window, a
    scatter of margin at the break vs final margin, and the matching games. Matched on score
    only, since there are no quarter-by-quarter stats.
- Wharf-ai usage (`admin.usage_log`, a dialog from the chart icon by the ? button) shows only to
  the emails in `WHARF_ADMINS` (comma separated, in secrets; Google sign-in only, so it never
  shows with the password login).
- Cards are `views.card(name)` / keyed containers (`key="card_<name>"`); the card CSS targets the
  `st-key-card_*` class, because Streamlit 1.64 removed the old bordered-container wrapper element.
  In 1.64 segmented controls render as radio buttons (tests: `get_by_role("radio", ...)`).
- The viewport component keeps the last size it sent on the parent window: every send reruns the
  app, and an extra rerun mid-answer cuts off a streaming Wharf-ai reply.
- Streamlit gives HTML markdown blocks a -1rem bottom margin; `inject_css` cancels it for the
  band, tiles, panel, card-title, leader and tape blocks. Narrow charts use legend keys in the card title
  (`card_title(keys=...)`) because Plotly legends stack vertically at that width.

## Chatbot (Wharf-ai)
- The insight card rotates through all of the season's insights every 30 s, in the browser with
  CSS (no reruns, so it can't interrupt a streaming answer; pauses on hover); "Another insight"
  moves on straight away. Wharf-ai is told the whole rotation.
- Named Wharf-ai; right-hand panel. Beside the dashboard (desktop, split) the panel is a fixed
  height and `theme.inject_side_panel_css` makes it a flex column: the purple header and the
  question box stay put and only the chat (`wa_history`) scrolls, taking whatever height the
  header leaves. With no messages it shows as many suggested prompts as fit
  under the insight (`app.fitting_prompts` estimates each button's height from its length and the
  panel width, calibrated at 1440 and 1920 wide); match mode leads with match questions. Every
  answer ends with a hidden `FOLLOWUPS: q | q | q` line that `chatbot._hold_back_marker` strips
  from the streamed text; the three show as "Ask next" buttons under the latest answer (unasked
  suggestions are used if the model leaves the line out).
- Each chat message records the page it was asked on (`focus`, or "the <season> season"). If a chat
  has started and the user moves to another page (view, game, player or club), the earlier chat
  stays and that page's questions follow it at the bottom ("Questions for this page", ones already
  asked are skipped), enough to fill about half the chat window; the chat is scrolled to the bottom
  so they are in view, and the old answer's follow-ups are hidden. Asking one continues the same
  conversation on the new page. It opens with an insight from
  `insights.py`: a pool of facts computed with pandas (win-rate swing by stat, best quarter, close
  games, home vs away, accuracy in wins vs losses, biggest change vs baseline, player in form,
  centre vs stoppage clearances), one picked at random per page open and per season. No LLM
  writes the insight, so it works without an API key. The shown insight is passed to the model.
- Daily cap and usage log (`usage.py`): every question is logged to SQLite (question, tools,
  steps, tokens, estimated cost at Sonnet 5.5 prices, sign-in session id); `WHARF_LOGIN_CAP`
  (default 10) questions per sign-in, answered or failed, shown in the panel header ("3/10 questions
  this sign-in"; a refresh or new tab keeps the same sign-in, signing in again starts a fresh 10);
  `WHARF_UNLIMITED` (comma separated emails, Google sign-in only) skips both limits and isn't
  counted in the shared total; keep it in secrets (the repo is public).
  `WHARF_DAILY_CAP` (default 100) per day, shared by everyone, resets at midnight Perth time, is the
  overall ceiling; log on the Wharf-ai usage page (admins only, `WHARF_ADMINS`). Storage
  (`usage._run`): with `USAGE_DATABASE_URL` (a Postgres URL; Supabase's Session pooler, see
  `docs/supabase_setup.md`) the log and saved chats go to `wharf_questions` / `wharf_chats`,
  created on first use with row-level security on, through a small psycopg pool with prepared
  statements off; they survive redeploys. If the database is down, Wharf-ai keeps working
  (counts 0, writes skipped, retried after 60 s) and the usage page warns. Without it: a SQLite
  file on the app's disk (`USAGE_DB`), wiped on Streamlit Cloud at every restart or redeploy.
  `tests/test_usage_pg.py` (empties the tables) runs only with `USAGE_TEST_DATABASE_URL`, which
  CI points at a throwaway Postgres service. Every test run sets `FREO_TESTS` (conftest), so
  `usage._pg_url` ignores `USAGE_DATABASE_URL` and only uses a test database a test switches
  on (`USAGE_TEST_DB_ACTIVE`); the UI tests' app gets its own secrets file (`--secrets.files`,
  just the test login), never `.streamlit/secrets.toml`. Counts are cached for 30 s with
  Postgres (each read is a network round trip; logging a question clears them).
- While Wharf-ai works, the status line shows a spinning red AFL ball (`theme.BALL_SVG`, inline SVG, fixed size so the
  line doesn't shift; still under reduced motion) and an AFL phrase (`app.WAIT_PHRASES`,
  20 of them, shuffled; a new one each time a tool runs, with what it is calculating alongside,
  and "writing the answer" when the next model request starts), plus a seconds counter the browser
  runs in CSS (`.wa-secs`; a negative animation-delay keeps the count going when the line is redrawn).
- Speed (measured 2026-09-30): the time is almost all the model; app reruns take 0.1 to 0.25 s and
  tools under 60 ms. On Sonnet 5.5, answer text written after tool results is not streamed: the
  API sends it in one burst once written (text between tool calls may become a hidden progress
  update, so it is held back), whatever the thinking, fallback, strict or eager settings. Only an
  answer with no tool call streams word by word. Effort `low` (the documented setting for chat)
  gave a median 4.7 s to an answer against 7.6 s at `medium`, with the eval still 27/27.
  `FREO_CHAT_EFFORT` overrides it. The client has a 60 s read timeout (the longest gap between
  streamed events), a 10 s connect timeout and 2 retries, so a stalled request fails in about a
  minute with a plain message (`chatbot.friendly_error`) instead of hanging for the SDK's 10 minutes.
  Each answer then keeps a "Worked out with: ..." note (stored as `steps` on the message).
- Avatars are generic SVGs in `assets/` (no club marks): `supporter.svg` (user, purple on white,
  bobble beanie) and `anchor.svg` (Wharf-ai, white on purple anchor with a robot head: antenna, visor eyes, grille mouth).
- Answers must be grounded in the loaded CSVs: compute numbers with code, then explain. Never
  state a stat that wasn't calculated. This is enforced with tools: `chatbot.stream_answer` runs a
  manual streaming tool-use loop on `claude-sonnet-5-5` (adaptive thinking, effort `low`,
  server-side refusal fallback `fallbacks: "default"`), and the model gets every number from
  `wharf_tools.py` (team_games, team_aggregate, correlate, quarter_breakdown, player_aggregate,
  player_games, show_chart, league_aggregate, ladder, opp_players: the opposition's players in
  their games against Freo, from `opp_player_games_ext.csv`, with the usual game filters). They are fixed pandas queries, no model-written code.
  Game filters include `behind_at` / `ahead_at` (Q1, Q2 = half time, Q3), and team metrics
  include `loss`, `draw` and `margin_q1`-`margin_q3`; the prompt says every win-loss record
  comes from team_aggregate sums of win/loss/draw, never from counting listed games (the
  baseline eval caught a "2-1" from four listed games that were 2-2). The API sometimes
  stops for "tool_use" with no tool call or no content at all: `_stream_answer` asks again
  (twice at most) instead of sending an empty tool-result turn (a 400). Wording in a tool
  description can trigger it: "Use for who hurt us" did, 4 in 10; reworded, 0 in 10. show_chart draws a small
  team_trend / player_trend / player_bar chart under the answer from the data itself (the model
  never supplies the numbers); charts are stored with the message as figure JSON and only role +
  content go back to the API. Tool inputs stream eagerly, so
  `wharf_tools.run` validates them and returns errors the model can fix. That includes filters: an
  unknown filter key (e.g. `venue`) or a non-object `filters` is an error listing the valid ones
  (`_check_filters`), never skipped, since skipping it would answer over every game. Goal accuracy from
  `team_aggregate` is pooled, matching the dashboard.
- Within one question the message list is append-only and assistant turns are passed back whole
  (thinking + tool_use blocks), as preserved thinking requires; only the final text is kept in the
  chat history between questions. Tools + the stable system prompt are cached; the per-view note
  (season, opening insight) sits after the cache breakpoint.
- Under each answer (`app.answer_extras`): "Show the numbers" opens every calculation the answer
  used, each tool's own table (`wharf_tools.Result` carries the DataFrame; `evidence.item` keeps
  it with the message as CSV, so saved chats keep it too); a thumbs up or down (`st.feedback`,
  `usage.rate`, logged with the answer text); and, if any, "Not matched to a calculation: ..."
  for numbers `evidence.unbacked` can't trace to a table, the question, the insights or an
  earlier answer's tables, directly, rounded, as a percentage, or by one simple step (a
  difference, total, per game rate, percentage change, wins and losses from a win rate, or a
  share of two numbers the answer itself states). It skips years, counts up to 3, ordinals and
  names like "inside 50". On the eval (all answers correct) it flagged 1 of 230 numbers, a real
  two-step sum the prompt doesn't allow. The prompt allows one simple step from two numbers if
  both are stated, and never to mention tools to the reader.
- Box-score data shows what happened, not structures or zones. The bot should say so
  when a question needs data we don't have.
- Needs ANTHROPIC_API_KEY from the environment (never hard-code it). Multi-workspace
  keys also need ANTHROPIC_WORKSPACE_ID (`wrkspc_...` from the console).

## Style
- Styled after fremantlefc.com.au's look: flat deep purple #331C54 top bar / Wharf-ai head,
  #F7F7F7 page, white cards (4px radius, no border or shadow: white on the light page is boundary
  enough), Inter (Google Fonts) with bold
  sentence-case titles, small uppercase labels on tiles and bands, thin white dividers on purple,
  and a faint mark at the right of each band (`marks.py`, our own line drawings, never a club's
logo or crest): the anchor for Freo, and in a club's Scout band and at their end of the Match band
a drawing of the mascot behind their nickname (cat for Geelong, crow for Adelaide, lion, magpie,
claw marks for Richmond, Captain Carlton's mask, and so on), passed to the band as `--mark`. The Match
  band is laid out like the site's match card: the score big in the middle with goals.behinds
  under each side, then a "Won by 12" / "Lost by 7" pill. Palette in CSS variables at the top of
  `theme.inject_css`.
- Chart colours come from the site too, all in `theme.COLORS` / `RAMP` / `DIVERGE` / `SERIES`
  (nothing hard-coded elsewhere) and checked with the dataviz validator: Freo #61359C (the site
  purple's hue lifted to OKLCH L 0.44; #331C54 itself is L 0.29, below the 0.43 floor for marks),
  opposition #008CA2 (site cyan; CVD dE 17 vs Freo), extra series #CC4C77 (site maroon) and
  #2E5FB7 (site navy), win #288B2C / loss #D42325 (site green and FULL TIME red), player-form ramp
  #BEACE4 -> #331C54, game strip cyan <- #EDEDEF -> purple. Maroon cannot be the opposition colour:
  it is too close to the loss red for anyone (dE 9.8). Green vs red fails red-green colour
  vision (dE 2.9), so every win/loss mark also carries a W/L letter or a bar direction. Do NOT use the Fremantle club logo, crest,
  photos, fonts files or other trademarks.
- Chart ink, after Tufte (`theme.style_fig`, `charts.py`): no gridlines and no axis lines; only
  lines that mean something are drawn (a zero margin, an average, a median). x labels are
  horizontal and thinned (`charts._round_ticks`: the round only, opponent on hover, the last game
  always shown), never rotated. Lines are named at their ends (`charts._end_labels`), dumbbells
  name the top row's two dots (`charts._tag_pair`), the highlighted quarter's bars carry the team
  names, and the tale of the tape names its columns, all in place of colour keys. Only the game
  strip and the two player tables (colour fills the cells) keep a key in the card title.
