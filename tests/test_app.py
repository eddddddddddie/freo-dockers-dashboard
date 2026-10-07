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


def test_player_comparison_view(app):
    """Picking "compare with" swaps the Player view for the comparison, and a
    move to another player without one clears it."""
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    at = at.button_group(key="view").set_value("Player").run()
    a = at.selectbox(key="player_pick").value
    b = [n for n in at.selectbox(key="player_pick").options[1:] if n != a][0]   # [0] is the whole squad
    at = at.selectbox(key="player_vs").set_value(b).run()
    assert not at.exception, at.exception
    assert any('class="cv-band player cmp"' in m.value for m in at.markdown)
    assert at.query_params.get("vs") == [b] or at.query_params.get("vs") == b
    at.session_state["pending_nav"] = {"view": "Player", "player": b}
    at = at.run()
    assert at.session_state["player_vs"] is None and at.session_state["player_pick"] == b


def test_whole_squad_all_clubs_and_quarter_time_pages(app):
    """Each picker's page across all its options draws, keeps its place in the
    address, and the deep dives menu and usage log are gone for everyone else."""
    import nav
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    assert not [s for s in at.selectbox if s.key == "deep_dive"]
    assert not [b for b in at.button if b.key == "usage_btn"]   # password sign-in: not an admin
    for view, key, value, param in [("Player", "player_pick", nav.SQUAD, ("player", nav.SQUAD)),
                                    ("Scout", "scout_team", nav.ALL_CLUBS, ("opp", nav.ALL_CLUBS)),
                                    ("Match", "game_2026", nav.QT, ("game", nav.QT_ROUND))]:
        at = at.button_group(key="view").set_value(view).run()
        at = at.selectbox(key=key).set_value(value).run()
        assert not at.exception, (view, at.exception)
        assert any(BAND in m.value for m in at.markdown), view
        got = at.query_params.get(param[0])
        assert got in (param[1], [param[1]]), (view, got)
    at = at.number_input(key="qt_margin").set_value(-12).run()   # behind by 2 goals at half time
    assert not at.exception, at.exception


def test_games_slice_cuts_season_and_player_views(app):
    """The games picker on Season (and Player) recuts every card, names the slice
    in the band, and keeps it in the address."""
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    at = at.selectbox(key="games_slice").set_value("Away games").run()
    assert not at.exception, at.exception
    band = next(m.value for m in at.markdown if BAND in m.value)
    assert "Away games only" in band
    assert at.query_params.get("games") in ("Away games", ["Away games"])
    at = at.button_group(key="view").set_value("Player").run()
    assert not at.exception and at.selectbox(key="games_slice").value == "Away games"
    at = at.selectbox(key="games_slice").set_value("Finals").run()
    assert not at.exception, at.exception


def test_ground_cards_on_match_player_and_scout(app):
    """Match, Player and Scout each carry a ground card (SIMULATED, and labelled
    so) with no switch to find it; every mode draws without an error."""
    at = login(app, os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])
    assert not [t for t in at.toggle if t.key == "ground_mode"]
    for view, key in (("Match", "gmatch_mode"), ("Player", "gplayer_mode"), ("Scout", "gscout_mode")):
        at = at.button_group(key="view").set_value(view).run()
        assert not at.exception, (view, at.exception)
        assert any("SIMULATED" in m.value for m in at.markdown), view
        modes = ["Events", "Running"] if key != "gscout_mode" else ["Events"]
        for mode in modes:
            at = at.button_group(key=key).set_value(mode).run()
            assert not at.exception, (view, mode, at.exception)


def test_layout_modes():
    import layout as L
    assert L.mode(390, 844) == L.mode(667, 340) == "phone"
    assert L.mode(820, 1100) == L.mode(844, 390) == L.mode(1024, 1366) == "stack"
    assert L.mode(1180, 820) == L.mode(1024, 700) == "split"
    assert L.mode(1280, 680) == L.mode(1440, 790) == L.mode(1366, 1024) == "desktop"


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


def test_usage_log_only_for_admins(monkeypatch):
    monkeypatch.setenv("WHARF_ADMINS", "Owner@Example.com")
    assert U.is_admin(" owner@example.com") and not U.is_admin("coach@example.com")
    assert not U.is_admin(None) and not U.is_admin("")
