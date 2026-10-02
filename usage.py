"""Wharf-ai usage: a daily question cap and a log of every question.

Each answered (or failed) question is one row: when, what was asked, which
tools ran, tokens, an estimated cost, the answer and its rating. The shared cap
resets at midnight Perth time.

Where it's kept:
  - USAGE_DATABASE_URL set (a Postgres connection string, e.g. Supabase's
    Session pooler URL): tables wharf_questions and wharf_chats in that
    database, created on first use with row-level security on (so Supabase's
    public Data API can't read them; this app connects as the owner). The log
    and saved chats survive restarts and redeploys. If the database can't be
    reached, Wharf-ai keeps working (counts read as 0, writes are skipped) and
    the usage page says so.
  - Otherwise: a SQLite file next to the app (USAGE_DB, default
    wharf_usage.sqlite, gitignored). On Streamlit Cloud that file starts again
    after every restart or redeploy.

Settings (environment or Streamlit secrets): WHARF_DAILY_CAP (default 100, shared
by everyone), WHARF_USER_CAP (default 10 questions per person per day; with the
username/password fallback a "person" is one sign-in), USAGE_DB (default
wharf_usage.sqlite), WHARF_ADMINS (comma separated emails that see the usage log),
WHARF_UNLIMITED (comma separated emails with no limits,
e.g. the app owner; their questions don't count towards the shared daily cap;
needs Google sign-in, which is how the app knows who someone is). Keep emails in
secrets, not the code: the repo is public. WHARF_LOGIN_CAP is read as a fallback
for WHARF_USER_CAP.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import settings

TZ = ZoneInfo("Australia/Perth")
DEFAULT_CAP = 100
DEFAULT_LOGIN_CAP = 10
# claude-sonnet-5-5, US$ per million tokens: input, output, cache read, cache write (5 min).
PRICES = {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50}


# ---- Storage -------------------------------------------------------------------
_PG_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS wharf_questions (
        id BIGSERIAL PRIMARY KEY, ts TEXT, day TEXT, question TEXT, tools TEXT, steps INTEGER,
        input_tokens INTEGER, output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER,
        cost_usd DOUBLE PRECISION, ok INTEGER, sid TEXT, user_email TEXT, answer TEXT,
        rating INTEGER, unbacked TEXT)""",
    "CREATE INDEX IF NOT EXISTS wharf_questions_day ON wharf_questions (day)",
    "CREATE INDEX IF NOT EXISTS wharf_questions_sid ON wharf_questions (sid, day)",
    "CREATE TABLE IF NOT EXISTS wharf_chats (sid TEXT PRIMARY KEY, updated TEXT, data TEXT)",
    # No policies: Supabase's public Data API sees nothing; the table owner (this app) is not
    # bound by row-level security.
    "ALTER TABLE wharf_questions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE wharf_chats ENABLE ROW LEVEL SECURITY",
]
_POOLS = {}
_DOWN_UNTIL = {}       # URL -> time before which a failed database isn't tried again
RETRY_SECONDS = 60
last_error = None      # the last database error, shown on the usage page


def _pg_url():
    # Under the tests (FREO_TESTS, set by tests/conftest.py, also for the app the UI
    # tests start) the live database is never used, even though .streamlit/secrets.toml
    # holds its URL: only a test database a test switches on (USAGE_TEST_DB_ACTIVE).
    if os.environ.get("FREO_TESTS"):
        return os.environ.get("USAGE_TEST_DB_ACTIVE") or None
    return settings.get("USAGE_DATABASE_URL")


def store_name():
    return "Postgres (USAGE_DATABASE_URL)" if _pg_url() else "SQLite file on the app's disk"


def _pool(url):
    """One small connection pool per URL, made on first use (and the tables with it).
    Prepared statements are off, so Supabase's transaction pooler works too. If the
    database can't be reached, the pool is closed and not tried again for a minute,
    so a down database costs one short wait a minute, not one per rerun."""
    if url in _POOLS:
        return _POOLS[url]
    import time
    if _DOWN_UNTIL.get(url, 0) > time.time():
        raise ConnectionError(f"database unreachable; retrying after {RETRY_SECONDS} s")
    from psycopg_pool import ConnectionPool
    pool = ConnectionPool(url, min_size=1, max_size=4, timeout=5, open=False,
                          kwargs={"autocommit": True, "prepare_threshold": None,
                                  "connect_timeout": 5},
                          max_idle=240)   # no check on every use: a broken connection is replaced
    try:
        pool.open(wait=True, timeout=6)
        with pool.connection() as con:
            for sql in _PG_SCHEMA:
                con.execute(sql)
    except Exception:
        pool.close()
        _DOWN_UNTIL[url] = time.time() + RETRY_SECONDS
        raise
    _POOLS[url] = pool
    return pool


def _sqlite():
    path = settings.get("USAGE_DB") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "wharf_usage.sqlite")
    con = sqlite3.connect(path, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS questions (
        ts TEXT, day TEXT, question TEXT, tools TEXT, steps INTEGER,
        input_tokens INTEGER, output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER,
        cost_usd REAL, ok INTEGER)""")
    cols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    if "sid" not in cols:  # logs from before the per sign-in cap
        con.execute("ALTER TABLE questions ADD COLUMN sid TEXT")
    if "user_email" not in cols:  # logs from before Google sign-in
        con.execute("ALTER TABLE questions ADD COLUMN user_email TEXT")
    for col, kind in (("answer", "TEXT"), ("rating", "INTEGER"), ("unbacked", "TEXT")):
        if col not in cols:  # logs from before answer ratings
            con.execute(f"ALTER TABLE questions ADD COLUMN {col} {kind}")
    con.execute("CREATE TABLE IF NOT EXISTS chats (sid TEXT PRIMARY KEY, updated TEXT, data TEXT)")
    return con


def _run(sql, params=(), fetch=None, default=None):
    """Run one statement on whichever store is set up. SQL is written for SQLite
    (? placeholders, tables {Q} and {C}); for Postgres the placeholders and
    table names are swapped. fetch: None, "one" (a tuple) or "all" (dicts)."""
    global last_error
    url = _pg_url()
    if not url:
        sql = sql.replace("{Q}", "questions").replace("{C}", "chats")
        with _sqlite() as con:
            if fetch == "all":
                con.row_factory = sqlite3.Row
            cur = con.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            return cur
    sql = sql.replace("?", "%s").replace("{Q}", "wharf_questions").replace("{C}", "wharf_chats")
    try:
        from psycopg.rows import dict_row
        with _pool(url).connection() as con:
            cur = con.cursor(row_factory=dict_row if fetch == "all" else None)
            cur.execute(sql, params)
            out = cur.fetchone() if fetch == "one" else cur.fetchall() if fetch == "all" else True
        last_error = None
        return out
    except Exception as exc:          # never let the log take Wharf-ai down
        last_error = f"{type(exc).__name__}: {exc}"
        print(f"usage store: {last_error}", file=sys.stderr)
        return default


def cap():
    try:
        return max(0, int(settings.get("WHARF_DAILY_CAP") or DEFAULT_CAP))
    except ValueError:
        return DEFAULT_CAP


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _emails(key):
    raw = settings.get(key) or ""
    return {e.strip().lower() for e in raw.replace(";", ",").split(",") if e.strip()}


def unlimited_emails():
    return _emails("WHARF_UNLIMITED")


def is_unlimited(email):
    return bool(email) and email.strip().lower() in unlimited_emails()


def is_admin(email):
    """WHARF_ADMINS: who sees the Wharf-ai usage log (Google sign-in only)."""
    return bool(email) and email.strip().lower() in _emails("WHARF_ADMINS")


# The Wharf-ai panel reads the counts on every redraw; with a database across the
# network each read is a round trip, so they're kept for a short while. Logging a
# question clears them, so a person's own count is always current.
_COUNT_TTL = 30
_counts = {}


def _cached(key, fn):
    import time
    hit = _counts.get(key)
    if hit and time.time() - hit[0] < _COUNT_TTL and _pg_url():
        return hit[1]
    value = fn()
    _counts[key] = (time.time(), value)
    return value


def questions_today():
    """Questions asked today by everyone except unlimited users (the shared cap)."""
    exempt = sorted(unlimited_emails())
    marks = ",".join("?" * len(exempt))
    sql = "SELECT COUNT(*) FROM questions WHERE day = ?"
    if exempt:
        sql += f" AND (user_email IS NULL OR lower(user_email) NOT IN ({marks}))"
    def count():
        row = _run(sql.replace("FROM questions", "FROM {Q}"), (today(), *exempt), "one")
        return row[0] if row else 0
    return _cached(("today", today(), tuple(exempt)), count)


def login_cap():
    """Questions per person per day."""
    raw = settings.get("WHARF_USER_CAP") or settings.get("WHARF_LOGIN_CAP")
    try:
        return max(0, int(raw or DEFAULT_LOGIN_CAP))
    except ValueError:
        return DEFAULT_LOGIN_CAP


def questions_this_login(sid):
    """Questions this person (or sign-in) has asked today."""
    if not sid:
        return 0
    def count():
        row = _run("SELECT COUNT(*) FROM {Q} WHERE sid = ? AND day = ?", (sid, today()), "one")
        return row[0] if row else 0
    return _cached(("login", today(), sid), count)


def can_ask(sid=None):
    return questions_today() < cap() and questions_this_login(sid) < login_cap()


class Tally:
    """Adds up token usage across the model requests of one question."""

    def __init__(self):
        self.input = self.output = self.cache_read = self.cache_write = self.steps = 0
        self.tools = []

    def add_usage(self, u):
        self.steps += 1
        self.input += getattr(u, "input_tokens", 0) or 0
        self.output += getattr(u, "output_tokens", 0) or 0
        self.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0

    def cost(self):
        return (self.input * PRICES["input"] + self.output * PRICES["output"]
                + self.cache_read * PRICES["cache_read"]
                + self.cache_write * PRICES["cache_write"]) / 1e6


def record(question, tally, ok=True, sid=None, user_email=None, answer=None, unbacked=None):
    """Log one question (answered or failed: both count towards the caps).
    Returns its id, for rate()."""
    _counts.clear()
    sql = ("INSERT INTO {Q} (ts, day, question, tools, steps, input_tokens, "
           "output_tokens, cache_read, cache_write, cost_usd, ok, sid, user_email, answer, "
           "unbacked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    params = (datetime.now(TZ).isoformat(timespec="seconds"), today(), question,
              json.dumps(tally.tools), tally.steps, tally.input, tally.output,
              tally.cache_read, tally.cache_write, round(tally.cost(), 5), int(ok), sid,
              user_email, answer, json.dumps(unbacked) if unbacked else None)
    if not _pg_url():
        return _run(sql, params).lastrowid
    row = _run(sql + " RETURNING id", params, "one")
    return row[0] if row else None


def rate(qid, rating):
    """A reader's thumbs up (1) or down (0) on an answer; None clears it."""
    if qid is None:
        return
    _run("UPDATE {Q} SET rating = ? WHERE " + ("id" if _pg_url() else "rowid") + " = ?",
         (rating, qid))


def recent(limit=200):
    """Recent questions, newest first, as a list of dicts."""
    cols = "*" if _pg_url() else "rowid AS id, *"
    return _run(f"SELECT {cols} FROM {{Q}} ORDER BY ts DESC LIMIT ?", (limit,), "all", default=[])


def summary():
    """Questions and cost today and over the last 7 days."""
    week_start = (datetime.now(TZ) - timedelta(days=6)).strftime("%Y-%m-%d")  # days sort as text
    t = _run("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM {Q} WHERE day = ?",
             (today(),), "one") or (0, 0)
    w = _run("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM {Q} WHERE day >= ?",
             (week_start,), "one") or (0, 0)
    return {"today": t[0], "today_cost": float(t[1]), "week": w[0], "week_cost": float(w[1]),
            "cap": cap(), "store": store_name(), "error": last_error}


# ---- Saved chats ------------------------------------------------------------
# A signed-in session's Wharf-ai conversation, so it survives a refresh or a
# new tab while the sign-in is valid (and a redeploy, with Postgres).
def save_chat(sid, messages):
    if not sid:
        return
    now, data = datetime.now(TZ).isoformat(timespec="seconds"), json.dumps(messages)
    if _pg_url():
        _run("INSERT INTO {C} (sid, updated, data) VALUES (?,?,?) ON CONFLICT (sid) "
             "DO UPDATE SET updated = EXCLUDED.updated, data = EXCLUDED.data", (sid, now, data))
    else:
        _run("INSERT OR REPLACE INTO {C} VALUES (?,?,?)", (sid, now, data))


def load_chat(sid):
    if not sid:
        return []
    row = _run("SELECT data FROM {C} WHERE sid = ?", (sid,), "one")
    try:
        return json.loads(row[0]) if row else []
    except ValueError:
        return []
