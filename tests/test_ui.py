"""Browser checks of the five places: every page draws with no exception and
never scrolls sideways, Wharf-ai stays in view (beside the page, or docked to
the bottom of a phone or portrait tablet), clicks, links and Back work.
Run with:  pytest -m ui   (needs Playwright; uses installed Chrome if present)."""

import os
import socket
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.ui
SIZES = [(1440, 790), (1920, 960), (1280, 680), (1680, 950)]
TOUR_SEEN = "localStorage.setItem('freoCoachTourDone_v2', '1')"   # skip the tour
PAGES = ["place=last-game&game=GF", "place=next-opponent", "place=next-opponent&club=Sydney",
         "place=our-season", "place=players", "place=players&player=Caleb%20Serong",
         "place=players&player=Caleb%20Serong&vs=Andrew%20Brayshaw", "place=game-day"]


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


def sign_in(pg, url):
    pg.goto(url)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()   # stays signed in for the links that follow
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(2500)
    return pg


def open_app(browser, server, w, h, query="", **ctx):
    c = browser.new_context(viewport={"width": w, "height": h}, **ctx)
    c.add_init_script(TOUR_SEEN)
    return sign_in(c.new_page(), f"{server}/?{query}")


def check_page(pg, server, query, w, h):
    """Open a page, scroll to its bottom: no exception, nothing wider than the
    window, and Wharf-ai (its panel or the dock) still in view."""
    pg.goto(f"{server}/?season=2026&{query}")
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(2500)
    f = pg.evaluate("""() => {
        const m = document.querySelector('[data-testid=stMain]');
        m.scrollTop = m.scrollHeight;
        const lefts = [...document.querySelectorAll('.cv-tile')].map(t => Math.round(t.getBoundingClientRect().left));
        return {wide: document.documentElement.scrollWidth - window.innerWidth,
                exceptions: document.querySelectorAll('[data-testid=stException]').length,
                tileCols: new Set(lefts).size}}""")
    pg.wait_for_timeout(400)
    wa = pg.locator(".st-key-card_wharfai, .st-key-wa_dock").first.bounding_box()
    assert f["exceptions"] == 0, (query, f)
    assert f["wide"] <= 1, (query, w, f)
    assert wa and wa["y"] < h and wa["y"] + wa["height"] > 0, (query, "Wharf-ai out of view")
    return f


@pytest.mark.parametrize("w,h", SIZES)
def test_places_scroll_cleanly_with_wharf_ai_in_view(browser, server, w, h):
    """Desktops: pages scroll (no one-screen rule) but never sideways, and the
    Wharf-ai panel stays beside them, also at the bottom of the page."""
    pg = open_app(browser, server, w, h)
    for query in PAGES:
        check_page(pg, server, query, w, h)
    assert pg.locator(".st-key-wa_dock").count() == 0
    pg.context.close()


PHONES = [(375, 667), (390, 844), (412, 915)]   # iPhone SE, iPhone 15, Pixel
TABLETS = [(820, 1100), (844, 390), (1180, 760)]


@pytest.mark.parametrize("w,h", PHONES + TABLETS)
def test_phones_and_tablets(browser, server, w, h):
    """Phones and tablets: nothing wider than the screen and Wharf-ai in view.
    Under 1000px wide (or 600 tall) it docks to the bottom; tiles run two to a
    row on a phone, three on a tablet."""
    phone = w < 700
    pg = open_app(browser, server, w, h, is_mobile=phone, has_touch=True)
    for query in PAGES[:1] + PAGES[3:5] + PAGES[6:7]:
        f = check_page(pg, server, query, w, h)
        if query.startswith("place=last-game"):
            assert f["tileCols"] == (2 if phone else 3 if w < 1250 else 6), (w, f)
    docked = pg.locator(".st-key-wa_dock").count() == 1
    assert docked == (w < 1000 or h < 600), (w, h)
    if docked:
        dock = pg.locator(".st-key-wa_dock").bounding_box()
        assert dock["y"] + dock["height"] <= h + 1 and dock["y"] > h / 2   # along the bottom
        pg.get_by_role("button", name="Ask Wharf-ai about this page").click()
        pg.wait_for_selector(".st-key-wa_dock_open", timeout=30000)
    pg.context.close()


def _click_cell(pg, card, n):
    """Press on the n-th clickable cell of a card's chart (the invisible layer)."""
    box = pg.locator(f".st-key-card_{card} .js-plotly-plot g.points path").nth(n).bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down()
    pg.wait_for_timeout(60)
    pg.mouse.up()
    pg.wait_for_timeout(4000)


def test_clicks_links_and_back_button(browser, server):
    """A game in Our season's overlay opens Last game for it; Back returns; a
    link to a game opens it (and an old ?view= link still works)."""
    pg = open_app(browser, server, 1440, 790, "season=2026&place=our-season")
    band = lambda: pg.locator(".cv-band.v2 .ttl").first.inner_text().split("\n")[0]  # noqa: E731
    _click_cell(pg, "v2_strip", 5)
    assert "place=last-game" in pg.evaluate("location.search") and " v " in band()
    pg.go_back()
    pg.wait_for_timeout(4000)
    assert "place=our-season" in pg.evaluate("location.search")
    pg.goto(server + "/?season=2025&place=last-game&game=EF")
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(3000)
    assert band().startswith("EF v"), band()
    pg.goto(server + "/?season=2025&view=Match&game=R25")
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(3000)
    assert band().startswith("R25 v"), band()
    pg.context.close()


def test_stay_signed_in_and_sign_out(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 790})
    ctx.add_init_script(TOUR_SEEN)
    pg = ctx.new_page()
    pg.goto(server)
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.get_by_label("Username").fill(os.environ["APP_USERNAME"])
    pg.get_by_role("textbox", name="Password").fill(os.environ["APP_PASSWORD"])
    pg.get_by_role("button", name="Sign in").click()   # "keep me signed in" is ticked by default
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    pg.wait_for_timeout(2000)
    pg.reload()
    pg.wait_for_selector(".cv-band.v2", timeout=60000)
    assert pg.locator("input[type=password]").count() == 0, "a reload should not ask again"
    pg.locator(".st-key-signout_btn button").first.click()
    pg.wait_for_selector("input[type=password]", timeout=60000)
    pg.reload()
    pg.wait_for_selector("input[type=password]", timeout=60000)
    assert not [c for c in ctx.cookies() if c["name"] == "freo_coach_session"]
    ctx.close()
