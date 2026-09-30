"""Wharf-ai usage: a daily question cap and a log of every question.

Each answered (or failed) question is one row in a small SQLite file: when,
what was asked, which tools ran, tokens and an estimated cost. The cap is
shared by everyone using the app (there is one login) and resets at midnight
Perth time.

The file lives next to the app (gitignored). On Streamlit Cloud the disk is
not kept across restarts or redeploys, so the log and today's count start
again after one; for permanent history, point USAGE_DB at persistent storage.

Settings (environment or Streamlit secrets): WHARF_DAILY_CAP (default 100, shared
by everyone), WHARF_USER_CAP (default 10 questions per person per day; with the
username/password fallback a "person" is one sign-in), USAGE_DB (default
wharf_usage.sqlite), WHARF_UNLIMITED (comma separated emails with no limits,
e.g. the app owner; their questions don't count towards the shared daily cap;
needs Google sign-in, which is how the app knows who someone is). Keep emails in
secrets, not the code: the repo is public. WHARF_LOGIN_CAP is read as a fallback
for WHARF_USER_CAP.
"""

import json
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import settings

TZ = ZoneInfo("Australia/Perth")
DEFAULT_CAP = 100
DEFAULT_LOGIN_CAP = 10
# claude-sonnet-5-5, US$ per million tokens: input, output, cache read, cache write (5 min).
PRICES = {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50}


def _db():
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
    return con


def cap():
    try:
        return max(0, int(settings.get("WHARF_DAILY_CAP") or DEFAULT_CAP))
    except ValueError:
        return DEFAULT_CAP


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def unlimited_emails():
    raw = settings.get("WHARF_UNLIMITED") or ""
    return {e.strip().lower() for e in raw.replace(";", ",").split(",") if e.strip()}


def is_unlimited(email):
    return bool(email) and email.strip().lower() in unlimited_emails()


def questions_today():
    """Questions asked today by everyone except unlimited users (the shared cap)."""
    exempt = sorted(unlimited_emails())
    marks = ",".join("?" * len(exempt))
    sql = "SELECT COUNT(*) FROM questions WHERE day = ?"
    if exempt:
        sql += f" AND (user_email IS NULL OR lower(user_email) NOT IN ({marks}))"
    with _db() as con:
        return con.execute(sql, (today(), *exempt)).fetchone()[0]


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
    with _db() as con:
        return con.execute("SELECT COUNT(*) FROM questions WHERE sid = ? AND day = ?",
                           (sid, today())).fetchone()[0]


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


def record(question, tally, ok=True, sid=None, user_email=None):
    """Log one question (answered or failed: both count towards the caps)."""
    with _db() as con:
        con.execute("INSERT INTO questions (ts, day, question, tools, steps, input_tokens, "
                    "output_tokens, cache_read, cache_write, cost_usd, ok, sid, user_email) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        datetime.now(TZ).isoformat(timespec="seconds"), today(), question,
                        json.dumps(tally.tools), tally.steps, tally.input, tally.output,
                        tally.cache_read, tally.cache_write, round(tally.cost(), 5), int(ok), sid,
                        user_email))


def recent(limit=200):
    """Recent questions, newest first, as a list of dicts."""
    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM questions ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def summary():
    """Questions and cost today and over the last 7 days."""
    with _db() as con:
        t = con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM questions WHERE day = ?",
                        (today(),)).fetchone()
        w = con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM questions "
                        "WHERE day >= date(?, '-6 days')", (today(),)).fetchone()
    return {"today": t[0], "today_cost": t[1], "week": w[0], "week_cost": w[1], "cap": cap()}


# ---- Saved chats ------------------------------------------------------------
# A signed-in session's Wharf-ai conversation, so it survives a refresh or a
# new tab while the sign-in cookie is valid. Same disk caveat as the log.
def _chats():
    con = _db()
    con.execute("CREATE TABLE IF NOT EXISTS chats (sid TEXT PRIMARY KEY, updated TEXT, data TEXT)")
    return con


def save_chat(sid, messages):
    if not sid:
        return
    with _chats() as con:
        con.execute("INSERT OR REPLACE INTO chats VALUES (?,?,?)",
                    (sid, datetime.now(TZ).isoformat(timespec="seconds"), json.dumps(messages)))


def load_chat(sid):
    if not sid:
        return []
    with _chats() as con:
        row = con.execute("SELECT data FROM chats WHERE sid = ?", (sid,)).fetchone()
    try:
        return json.loads(row[0]) if row else []
    except ValueError:
        return []
