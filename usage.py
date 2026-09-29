"""Wharf-ai usage: a daily question cap and a log of every question.

Each answered (or failed) question is one row in a small SQLite file: when,
what was asked, which tools ran, tokens and an estimated cost. The cap is
shared by everyone using the app (there is one login) and resets at midnight
Perth time.

The file lives next to the app (gitignored). On Streamlit Cloud the disk is
not kept across restarts or redeploys, so the log and today's count start
again after one; for permanent history, point USAGE_DB at persistent storage.

Settings (environment or Streamlit secrets): WHARF_DAILY_CAP (default 50),
USAGE_DB (default wharf_usage.sqlite).
"""

import json
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import settings

TZ = ZoneInfo("Australia/Perth")
DEFAULT_CAP = 50
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
    return con


def cap():
    try:
        return max(0, int(settings.get("WHARF_DAILY_CAP") or DEFAULT_CAP))
    except ValueError:
        return DEFAULT_CAP


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def questions_today():
    with _db() as con:
        return con.execute("SELECT COUNT(*) FROM questions WHERE day = ?", (today(),)).fetchone()[0]


def can_ask():
    return questions_today() < cap()


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


def record(question, tally, ok=True):
    with _db() as con:
        con.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            datetime.now(TZ).isoformat(timespec="seconds"), today(), question,
            json.dumps(tally.tools), tally.steps, tally.input, tally.output,
            tally.cache_read, tally.cache_write, round(tally.cost(), 5), int(ok)))


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
