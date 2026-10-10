"""Coach View v2 (?v2=1): every place and its pages draw without an error, moves
follow the one click rule, and Wharf-ai is on every page (headless, AppTest)."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import v2

BAND = '<div class="cv-band v2'


def _app(query, size=(1440, 790), extra={"v2": "1"}):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, "app.py"), default_timeout=120)
    at.secrets["APP_USERNAME"] = os.environ["APP_USERNAME"]
    at.secrets["APP_PASSWORD"] = os.environ["APP_PASSWORD"]
    at.secrets["ANTHROPIC_API_KEY"] = ""
    at.session_state["window_size"] = size
    for k, v in {**(extra or {}), **query}.items():
        at.query_params[k] = v
    at = at.run()
    at.text_input[0].input(os.environ["APP_USERNAME"])
    at.text_input[1].input(os.environ["APP_PASSWORD"])
    at.button[0].click()
    return at.run()


def _wharf_ai_shown(at):
    return any("Wharf-ai" in m.value for m in at.markdown) or any(
        b.key == "wa_open_btn" for b in at.button)


@pytest.mark.parametrize("query", [
    {"place": "last-game", "game": "GF"},
    {"place": "next-opponent"},
    {"place": "next-opponent", "club": "Sydney"},
    {"place": "our-season"},
    {"place": "our-season", "games": "Losses"},
    {"place": "players"},
    {"place": "players", "player": "Caleb Serong"},
    {"place": "players", "player": "Caleb Serong", "vs": "Andrew Brayshaw"},
    {"place": "game-day"},
])
def test_every_place_draws_with_wharf_ai(query):
    at = _app({"season": "2026", **query})
    assert not at.exception, (query, at.exception)
    assert any(BAND in m.value for m in at.markdown), query
    assert _wharf_ai_shown(at), query


def test_v2_is_the_default_and_v2_0_keeps_the_old_layout():
    at = _app({"season": "2026"}, extra=None)
    assert not at.exception
    assert any(BAND in m.value for m in at.markdown)              # v2 with no flag
    assert "v2" not in at.query_params


def test_v2_0_shows_the_old_layout():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, "app.py"), default_timeout=120)
    at.secrets["APP_USERNAME"] = os.environ["APP_USERNAME"]
    at.secrets["APP_PASSWORD"] = os.environ["APP_PASSWORD"]
    at.secrets["ANTHROPIC_API_KEY"] = ""
    at.query_params["v2"] = "0"
    at = at.run()
    at.text_input[0].input(os.environ["APP_USERNAME"])
    at.text_input[1].input(os.environ["APP_PASSWORD"])
    at.button[0].click()
    at = at.run()
    assert not at.exception
    assert not any(BAND in m.value for m in at.markdown)
    assert at.query_params["v2"] == ["0"]                          # kept in the address
    assert [b for b in at.button_group if b.key == "view"]          # the old view switch


def test_places_switch_and_the_address_follows():
    at = _app({"season": "2026", "place": "last-game"})
    places = at.button_group(key="v2_place")
    for place in v2.PLACES:
        at = places.set_value(place).run()
        assert not at.exception, (place, at.exception)
        assert at.query_params["place"] == [v2.SLUGS[place]]
        places = at.button_group(key="v2_place")


def test_next_opponent_opens_on_the_first_club_and_its_what_if_moves():
    at = _app({"season": "2026", "place": "next-opponent"})
    assert not at.exception
    assert at.selectbox(key="v2_club").value == "Adelaide"
    assert any("Adelaide" in m.value for m in at.markdown if BAND in m.value)
    assert at.query_params["club"] == ["Adelaide"]
    takes = lambda a: [m.value for m in a.markdown if "win chance" in m.value and "to" in m.value]  # noqa: E731
    at = at.slider(key="v2_wi_centre_clearances").set_value(3).run()
    assert not at.exception
    assert any("+3 centre clearances a game" in t for t in takes(at))


def test_ask_wharf_ai_queues_the_cards_question():
    at = _app({"season": "2026", "place": "last-game", "game": "GF"})
    ask = next(b for b in at.button if b.key == "ask_v2_tape")
    at = ask.click().run()
    assert not at.exception
    # No API key in tests, so the question waits for the panel instead of being answered.
    assert at.session_state["wa_open"]


def test_phone_docks_wharf_ai_and_opens_it():
    at = _app({"season": "2026", "place": "our-season"}, size=(390, 844))
    assert not at.exception
    at = at.button(key="wa_open_btn").click().run()
    assert not at.exception
    assert any(b.key == "wa_close" for b in at.button)
    assert any("Wharf-ai" in m.value for m in at.markdown)
