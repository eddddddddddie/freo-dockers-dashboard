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
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "ANTHROPIC_API_KEY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                             "--server.port", str(port), "--server.headless", "true"],
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
    pg.close()


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
