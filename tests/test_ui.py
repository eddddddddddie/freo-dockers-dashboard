"""Browser checks: the one-screen layout fits with no page scroll at the four
tested window sizes, in every view, with no exceptions and white cards.
Run with:  pytest -m ui   (needs Playwright; uses installed Chrome if present)."""

import os
import socket
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.ui
SIZES = [(1440, 790), (1920, 960), (1280, 680), (1680, 950)]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The app on a free port, with its own secrets file: just the test login. Not
    .streamlit/secrets.toml, which may hold Google sign-in, API keys or the live
    usage database."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    secrets = tmp_path_factory.mktemp("secrets") / "secrets.toml"
    secrets.write_text(f'APP_USERNAME = "{os.environ["APP_USERNAME"]}"\n'
                       f'APP_PASSWORD = "{os.environ["APP_PASSWORD"]}"\n')
    env = {**os.environ, "ANTHROPIC_API_KEY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                             "--server.port", str(port), "--server.headless", "true",
                             "--secrets.files", str(secrets)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:  # never leave a server running after the tests
        proc.kill()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:  # never leave a server running after the tests
        proc.kill()


@pytest.fixture(scope="module")
def browser():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            b = p.chromium.launch()
        yield b
        b.close()


def open_app(browser, server, w, h):
    pg = browser.new_page(viewport={"width": w, "height": h})
    pg.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")  # skip the tour
    pg.goto(server)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()
    pg.wait_for_selector(".js-plotly-plot", timeout=60000)
    pg.wait_for_timeout(3000)
    return pg


def fit(pg):
    return pg.evaluate("""() => {
        const m = document.querySelector('[data-testid=stMain]');
        const cards = [...document.querySelectorAll('[class*=st-key-card_]')];
        return {scroll: m.scrollHeight, client: m.clientHeight,
                exceptions: document.querySelectorAll('[data-testid=stException]').length,
                cards: cards.length,
                white: cards.filter(c => getComputedStyle(c).backgroundColor === 'rgb(255, 255, 255)').length};
    }""")


@pytest.mark.parametrize("w,h", SIZES)
def test_every_view_fits_one_screen(browser, server, w, h):
    pg = open_app(browser, server, w, h)
    views = [v for v in ["Season", "Match", "Scout"]
             if pg.get_by_role("radio", name=v, exact=True).count()]
    for view in views:
        pg.get_by_role("radio", name=view, exact=True).click()
        pg.wait_for_timeout(3000)
        f = fit(pg)
        assert f["exceptions"] == 0, (view, f)
        assert f["scroll"] <= f["client"] + 1, (view, w, h, f)
        assert f["cards"] and f["white"] == f["cards"], (view, f)
    # Player vs player and the pickers' whole-list pages (links; the sign-in
    # cookie carries over): whole squad, all clubs, quarter-time check.
    for name, query in [("compare", "view=Player&player=Caleb%20Serong&vs=Andrew%20Brayshaw"),
                        ("squad", "view=Player&player=Whole%20squad"),
                        ("clubs", "view=Scout&opp=All%20clubs"), ("qt", "view=Match&game=QT"),
                        ("momentum", "view=Match&game=MOM")]:
        pg.goto(f"{server}/?season=2026&{query}")
        pg.wait_for_selector(".cv-band", timeout=60000)
        pg.wait_for_timeout(3000)
        f = fit(pg)
        assert f["exceptions"] == 0 and f["scroll"] <= f["client"] + 1, (name, w, h, f)
        assert f["cards"] and f["white"] == f["cards"], (name, f)
    pg.close()


PHONES = [(375, 667), (390, 844), (412, 915)]   # iPhone SE, iPhone 15, Pixel


@pytest.mark.parametrize("w,h", PHONES)
def test_phone_layout_scrolls_one_column(browser, server, w, h):
    """On a phone: nothing wider than the screen, Wharf-ai above the dashboard,
    tiles two to a row."""
    ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True)
    ctx.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")
    pg = ctx.new_page()
    pg.goto(server)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()   # stays signed in for the links below
    for view in ["Season", "Match", "Player", "Scout"]:
        if view != "Season":
            pg.goto(f"{server}/?season=2026&view={view}")
        pg.wait_for_selector(".js-plotly-plot", timeout=60000)
        pg.wait_for_timeout(3000)
        f = pg.evaluate("""() => {
            const m = document.querySelector('[data-testid=stMain]');
            const top = s => document.querySelector(s).getBoundingClientRect().top;
            const lefts = [...document.querySelectorAll('.cv-tile')].map(t => Math.round(t.getBoundingClientRect().left));
            return {docW: document.documentElement.scrollWidth, mainW: m.scrollWidth,
                    exceptions: document.querySelectorAll('[data-testid=stException]').length,
                    chatAbove: top('.st-key-card_wharfai') < top('.cv-tiles'),
                    columns: new Set(lefts).size};
        }""")
        assert f["exceptions"] == 0, (view, f)
        assert f["docW"] <= w and f["mainW"] <= w, (view, w, f)
        assert f["chatAbove"] and f["columns"] == 2, (view, f)
    ctx.close()


TABLETS = [(820, 1100, "stack"), (844, 390, "stack"), (1180, 760, "split")]


@pytest.mark.parametrize("w,h,mode", TABLETS)
def test_tablet_layouts(browser, server, w, h, mode):
    """Tablets and landscape phones: the page scrolls with nothing wider than the
    screen, cards two to a row, tiles three to a row. stack: Wharf-ai above the
    dashboard; split: beside it, and still in view after scrolling down."""
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=True)
    ctx.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")
    pg = ctx.new_page()
    pg.goto(server)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()
    for view in ["Season", "Match", "Player", "Scout"]:
        if view != "Season":
            pg.goto(f"{server}/?season=2026&view={view}")
        pg.wait_for_selector(".js-plotly-plot", timeout=60000)
        pg.wait_for_timeout(3000)
        f = pg.evaluate("""() => {
            const m = document.querySelector('[data-testid=stMain]');
            const r = s => document.querySelector(s).getBoundingClientRect();
            const tiles = [...document.querySelectorAll('.cv-tile')].map(t => Math.round(t.getBoundingClientRect().left));
            const cards = [...document.querySelectorAll('[class*=st-key-card_]')]
                .filter(c => !c.className.includes('card_wharfai')).map(c => Math.round(c.getBoundingClientRect().left));
            const out = {docW: document.documentElement.scrollWidth, mainW: m.scrollWidth,
                exceptions: document.querySelectorAll('[data-testid=stException]').length,
                tileCols: new Set(tiles).size, cardCols: new Set(cards).size,
                chatAbove: r('.st-key-card_wharfai').bottom <= r('.cv-tiles').top + 1,
                chatBeside: r('.st-key-card_wharfai').left >= r('.cv-tiles').right};
            m.scrollTo(0, m.scrollHeight);
            return out; }""")
        pg.wait_for_timeout(500)
        chat_top = pg.evaluate("document.querySelector('.st-key-card_wharfai').getBoundingClientRect().top")
        assert f["exceptions"] == 0, (view, f)
        assert f["docW"] <= w and f["mainW"] <= w, (view, w, f)
        assert f["tileCols"] == 3 and f["cardCols"] == 2, (view, f)
        if mode == "stack":
            assert f["chatAbove"], (view, f)
        else:
            assert f["chatBeside"] and 0 <= chat_top <= 20, (view, f, chat_top)  # pinned in view
    ctx.close()


def _click_cell(pg, card, n):
    """Press on the n-th clickable cell of a card's chart (the invisible layer)."""
    box = pg.locator(f".st-key-card_{card} .js-plotly-plot g.points path").nth(n).bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down()
    pg.wait_for_timeout(60)
    pg.mouse.up()
    pg.wait_for_timeout(4000)


def test_clicks_links_and_back_button(browser, server):
    pg = open_app(browser, server, 1440, 790)
    band = lambda: pg.locator(".cv-band .ttl").inner_text().split("\n")[0]  # noqa: E731
    _click_cell(pg, "strip", 5)                       # first row, 6th game
    assert "view=Match" in pg.evaluate("location.search") and " v " in band()
    game = band()
    pg.get_by_role("radio", name="Player", exact=True).click()
    pg.wait_for_timeout(3500)
    assert "view=Player" in pg.evaluate("location.search")
    pg.go_back()
    pg.wait_for_timeout(4000)
    assert band() == game, "browser Back should return to the match"
    pg.close()
    pg2 = browser.new_page(viewport={"width": 1440, "height": 790})
    pg2.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")
    pg2.goto(server + "/?season=2025&view=Match&game=EF")
    pg2.wait_for_selector("input[type=password]", timeout=60000)
    pg2.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg2.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg2.get_by_role("button", name="Sign in").click()
    pg2.wait_for_selector(".js-plotly-plot", timeout=60000)
    pg2.wait_for_timeout(3000)
    assert pg2.locator(".cv-band .ttl").inner_text().startswith("EF v"), "deep link opens the game"
    pg2.close()


def test_driver_drill_down_opens_and_goes_back(browser, server):
    """Clicking a stat in "What drives our margin" swaps the bars for that stat's
    scatter (one point per game); the back arrow returns to the bars."""
    pg = open_app(browser, server, 1440, 790)
    _click_cell(pg, "drivers", 0)                     # the top driver's row
    assert pg.locator(".st-key-driver_back").count() == 1
    n = pg.locator(".st-key-card_drivers .js-plotly-plot g.scatterlayer g.trace").nth(1) \
        .locator("path.point").count()
    assert n >= 20, n                                 # a point for every game
    pg.locator(".st-key-driver_back button").first.click()   # Streamlit may briefly keep a stale copy
    pg.wait_for_timeout(3500)
    assert pg.locator(".st-key-driver_back").count() == 0
    pg.close()


def test_stay_signed_in_and_sign_out(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 790})
    ctx.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")
    pg = ctx.new_page()
    pg.goto(server)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()   # "keep me signed in" is ticked by default
    pg.wait_for_selector(".js-plotly-plot", timeout=60000)
    pg.wait_for_timeout(2000)
    pg.reload()
    pg.wait_for_selector(".js-plotly-plot", timeout=60000)
    assert pg.locator("input[type=password]").count() == 0, "a reload should not ask again"
    pg.locator(".st-key-signout_btn button").first.click()
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.reload()
    pg.wait_for_selector("input[type=password]", timeout=60000)
    assert not [c for c in ctx.cookies() if c["name"] == "freo_coach_session"]
    ctx.close()


V2_PAGES = ["place=last-game&game=GF", "place=next-opponent", "place=next-opponent&club=Sydney",
            "place=our-season", "place=players", "place=players&player=Caleb%20Serong",
            "place=players&player=Caleb%20Serong&vs=Andrew%20Brayshaw", "place=game-day"]


@pytest.mark.parametrize("w,h", SIZES)
def test_v2_places_scroll_cleanly_with_wharf_ai_in_view(browser, server, w, h):
    """v2 pages scroll (no one-screen rule) but never sideways, raise nothing, and
    keep Wharf-ai in view beside them, also after scrolling to the bottom."""
    pg = open_app(browser, server, w, h)
    for query in V2_PAGES:
        pg.goto(f"{server}/?v2=1&season=2026&{query}")
        pg.wait_for_selector(".cv-band.v2", timeout=60000)
        pg.wait_for_timeout(2500)
        f = pg.evaluate("""() => {
            const m = document.querySelector('[data-testid=stMain]');
            m.scrollTop = m.scrollHeight;
            return {wide: document.documentElement.scrollWidth - window.innerWidth,
                    exceptions: document.querySelectorAll('[data-testid=stException]').length}}""")
        pg.wait_for_timeout(400)
        box = pg.locator(".st-key-card_wharfai").first.bounding_box()
        assert f["exceptions"] == 0, (query, f)
        assert f["wide"] <= 1, (query, w, f)
        assert box and box["y"] < h and box["y"] + box["height"] > 0, (query, "Wharf-ai out of view")
    pg.close()


def test_v2_phone_docks_wharf_ai(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.add_init_script("localStorage.setItem('freoCoachTourDone_v1', '1')")
    pg = ctx.new_page()
    pg.goto(server + "/?v2=1&season=2026&place=our-season")
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(2500)
    dock = pg.locator(".st-key-wa_dock").bounding_box()
    assert dock and dock["y"] + dock["height"] <= 844 + 1 and dock["y"] > 600   # along the bottom
    assert pg.evaluate("document.documentElement.scrollWidth") <= 391
    pg.get_by_role("button", name="Ask Wharf-ai about this page").click()
    pg.wait_for_selector(".st-key-wa_dock_open", timeout=30000)
    ctx.close()
