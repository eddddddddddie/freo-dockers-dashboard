"""The login gate, the usage cap, the insights and a headless start of the
whole app (Streamlit's AppTest; no browser, no API calls)."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import auth
import data as D
import insights as I
import usage as U

BAND = '<div class="cv-band'  # the dashboard's header band element (not the CSS rule)


def login(at, user, pw):
    at.text_input[0].input(user)
    at.text_input[1].input(pw)
    at.button[0].click()
    return at.run()


@pytest.fixture
def app():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, "app.py"), default_timeout=90)
    at.secrets["APP_USERNAME"] = os.environ["APP_USERNAME"]
    at.secrets["APP_PASSWORD"] = os.environ["APP_PASSWORD"]
    at.secrets["ANTHROPIC_API_KEY"] = ""
    return at.run()


def test_login_page_shows_no_data(app):
    assert not app.exception
    assert not any(BAND in m.value for m in app.markdown)


def test_wrong_password_is_rejected(app):
    at = login(app, os.environ["APP_USERNAME"], "wrong")
    assert any("Incorrect" in e.value for e in at.error)
    assert not any(BAND in m.value for m in at.markdown)


def test_right_password_opens_the_dashboard(app):
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    assert not at.exception, at.exception
    assert any(BAND in m.value for m in at.markdown)


def test_match_and_scout_views_render(app):
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    views = at.button_group(key="view")
    for view in views.options:
        at = views.set_value(view).run()
        assert not at.exception, (view, at.exception)
        views = at.button_group(key="view")


def test_phone_layout(app):
    """Below layout.PHONE_W the app draws one column: a view dropdown, Wharf-ai
    above the dashboard, and a list of recent games that open in Match."""
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    at.session_state["window_size"] = (390, 844)
    at = at.run()
    assert not at.exception, at.exception
    games = [b for b in at.button if (b.key or "").startswith("rg_2026_")]
    assert len(games) == 8 and games[0].label.startswith("**")   # newest first, 8 shown
    for view in ["Match", "Player", "Scout", "Season"]:
        at = at.selectbox(key="view").set_value(view).run()
        assert not at.exception, (view, at.exception)
    at = at.button(key=games[0].key).click().run()
    assert at.session_state["view"] == "Match"


def test_constant_time_compare():
    assert auth._matches("abc", "abc") and not auth._matches("abc", "abd")


def test_usage_cap_and_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB", str(tmp_path / "u.sqlite"))
    monkeypatch.setenv("WHARF_DAILY_CAP", "2")

    class Usage:
        input_tokens, output_tokens = 1_000_000, 100_000
        cache_read_input_tokens, cache_creation_input_tokens = 0, 0

    t = U.Tally()
    t.add_usage(Usage())
    assert t.cost() == pytest.approx(2.00 + 1.00)  # $2/M in, $10/M out
    assert U.can_ask()
    U.record("q1", t)
    U.record("q2", t)
    assert U.questions_today() == 2 and not U.can_ask()


def test_login_cap_counts_per_sign_in(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB", str(tmp_path / "u.sqlite"))
    monkeypatch.setenv("WHARF_DAILY_CAP", "50")
    monkeypatch.setenv("WHARF_LOGIN_CAP", "2")
    t = U.Tally()
    U.record("q1", t, sid="login-a")
    U.record("q2", t, ok=False, sid="login-a")   # failed questions count too
    U.record("q3", t, sid="login-b")
    assert U.questions_this_login("login-a") == 2 and not U.can_ask("login-a")
    assert U.questions_this_login("login-b") == 1 and U.can_ask("login-b")


def test_insights_are_computed_sentences():
    team, players = D.load_team(), D.load_players()
    for season, base in [(2026, 2025), (2025, None)]:
        pool = I.candidates(team, players, season, base)
        assert pool and all(any(ch.isdigit() for ch in c) for c in pool)


def test_unlimited_users_skip_the_caps_and_the_shared_count(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB", str(tmp_path / "u.sqlite"))
    monkeypatch.setenv("WHARF_UNLIMITED", "Owner@Example.com, second@example.com")
    t = U.Tally()
    U.record("q1", t, sid="g:owner", user_email="owner@example.com")
    U.record("q2", t, sid="g:coach", user_email="coach@example.com")
    U.record("q3", t, sid="pw-login")                       # password sign-in, no email
    assert U.is_unlimited("OWNER@example.com ") and not U.is_unlimited("coach@example.com")
    assert not U.is_unlimited(None) and not U.is_unlimited("")
    assert U.questions_today() == 2   # the owner's question isn't counted
