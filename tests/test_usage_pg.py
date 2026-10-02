"""The usage log on Postgres (the Supabase path). Runs only when
USAGE_TEST_DATABASE_URL points at a database that may be wiped: it empties the
wharf_ tables. CI runs it against a throwaway Postgres container. Never point
it at the live database."""

import os

import pytest

import usage as U

URL = os.environ.get("USAGE_TEST_DATABASE_URL")
needs_pg = pytest.mark.skipif(not URL, reason="USAGE_TEST_DATABASE_URL not set")


@pytest.fixture
def pg(monkeypatch):
    monkeypatch.setenv("USAGE_DATABASE_URL", URL)
    monkeypatch.setenv("WHARF_UNLIMITED", "owner@example.com")
    U._run("SELECT 1")                                       # makes the tables
    U._run("TRUNCATE wharf_questions, wharf_chats")
    assert U.last_error is None, U.last_error
    return U


@needs_pg
def test_log_caps_rating_and_summary(pg):
    t = pg.Tally()
    t.input, t.output, t.steps = 1000, 200, 2
    a = pg.record("q1", t, sid="g:coach", user_email="coach@example.com", answer="a1",
                  unbacked=["12"])
    b = pg.record("q2", t, ok=False, sid="g:coach", user_email="coach@example.com")
    pg.record("q3", t, sid="g:owner", user_email="owner@example.com")
    assert isinstance(a, int) and b == a + 1
    assert pg.questions_this_login("g:coach") == 2 and pg.questions_today() == 2  # owner exempt
    pg.rate(a, 0)
    rows = {r["question"]: r for r in pg.recent()}
    assert rows["q1"]["rating"] == 0 and rows["q1"]["answer"] == "a1"
    assert rows["q1"]["unbacked"] == '["12"]' and rows["q2"]["ok"] == 0
    s = pg.summary()
    assert s["today"] == 3 and s["week"] == 3 and s["store"].startswith("Postgres")
    assert abs(s["today_cost"] - 3 * t.cost()) < 1e-4


@needs_pg
def test_saved_chat_round_trip_and_overwrite(pg):
    pg.save_chat("g:coach", [{"role": "user", "content": "hi"}])
    pg.save_chat("g:coach", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}])
    assert [m["content"] for m in pg.load_chat("g:coach")] == ["hi", "yo"]
    assert pg.load_chat("g:nobody") == []


@needs_pg
def test_row_level_security_is_on(pg):
    rows = pg._run("SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
                   "('wharf_questions', 'wharf_chats')", fetch="all")
    assert {r["relname"]: r["relrowsecurity"] for r in rows} == {
        "wharf_questions": True, "wharf_chats": True}


def test_unreachable_database_never_breaks_wharf_ai(monkeypatch):
    """A down database: counts read 0, writes are skipped, the error is kept for the
    usage page, and after the first failure it isn't retried on every call."""
    import time
    url = "postgresql://nobody:x@127.0.0.1:1/none"
    monkeypatch.setenv("USAGE_DATABASE_URL", url)
    U._POOLS.pop(url, None)
    U._DOWN_UNTIL.pop(url, None)
    assert U.questions_today() == 0 and U.last_error
    start = time.time()
    assert U.record("q", U.Tally()) is None and U.recent() == [] and U.load_chat("s") == []
    assert time.time() - start < 1          # backed off: no new connection attempts
    assert "unreachable" in U.last_error
