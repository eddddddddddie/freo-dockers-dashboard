"""The numbers behind a Wharf-ai answer.

Every tool result is kept with the answer it fed (`item`), so the chat can show
the exact tables under "Show the numbers". `unbacked` then checks the answer:
each number in its text should come from those tables, the question, the
panel's insights or an earlier answer's tables, either directly, rounded, as a
percentage, or by a simple step the prompt allows (a difference of two figures,
a percentage change, or wins and losses from a win rate and a game count). A
number that can't be matched is listed under the answer for the reader to
check. It is a prompt to look, not proof of a mistake: the model may have done
a sum the check doesn't try.
"""

import io
import json
import re
from itertools import combinations

import pandas as pd

# A number not glued to letters (so not R12, Q3, I50, 50s, 1st), with an
# optional sign, thousands commas, decimals and percent sign.
_NUM = re.compile(r"(?<![\w.,])([-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(%?)(?![\dA-Za-z]|[.,]\d)")
YEARS = range(1990, 2101)


def item(name, args, result):
    """A JSON-ready record of one tool call: its table if it returned one."""
    df = getattr(result, "df", None)
    rec = {"tool": name, "args": args, "note": getattr(result, "note", "")}
    if df is not None:
        rec["csv"] = df.to_csv(index=False)
    else:
        rec["text"] = str(result)
    return rec


def table(rec):
    """The record's table as a DataFrame (None for a text-only result)."""
    if not rec.get("csv"):
        return None
    try:
        return pd.read_csv(io.StringIO(rec["csv"]))
    except (ValueError, pd.errors.ParserError):
        return None


def describe(rec, labels=None):
    """'Averaging team stats: season 2026, grouped by type'."""
    label = (labels or {}).get(rec["tool"], rec["tool"].replace("_", " "))
    a = rec.get("args") or {}
    bits = []
    for k in ("metrics", "stats", "x", "y", "players", "teams", "kind", "agg", "group_by"):
        v = a.get(k)
        if v not in (None, [], ""):
            v = ", ".join(map(str, v)) if isinstance(v, list) else v
            bits.append(f"{k.replace('_', ' ')} {v}")
    f = a.get("filters") or {}
    if isinstance(f, dict) and f:
        bits.append("where " + ", ".join(f"{k} {', '.join(map(str, v)) if isinstance(v, list) else v}"
                                         for k, v in f.items()))
    return label[:1].upper() + label[1:] + (": " + "; ".join(bits) if bits else "")


def numbers(text):
    """[(value, decimals, is_percent, as written)] for each number in the text."""
    out = []
    for m in _NUM.finditer(text or ""):
        raw = m.group(1)
        v = float(raw.replace(",", "").replace("−", "-"))
        dec = len(raw.split(".")[1]) if "." in raw else 0
        out.append((v, dec, bool(m.group(2)), raw + m.group(2)))
    return out


def _cells(rec):
    """(column, value) for every number a record holds: table cells, plus any in
    its text, note and arguments."""
    out = []
    df = table(rec)
    if df is not None:
        for col in df.columns:
            for v in pd.to_numeric(df[col], errors="coerce").dropna():
                out.append((col, float(v)))
    for txt in (rec.get("text"), rec.get("note"), json.dumps(rec.get("args") or {})):
        out += [(None, v) for v, *_ in numbers(txt)]
    return out


def _derived(records):
    """Figures a careful analyst could state from the tables in one step."""
    vals = set()
    by_col = {}
    for rec in records:
        df = table(rec)
        for col, v in _cells(rec):
            vals.add(v)
            if col is not None:
                by_col.setdefault(col, []).append(v)
        if df is None:
            continue
        num = df.apply(pd.to_numeric, errors="coerce")
        for _, row in num.iterrows():
            cells = [float(x) for x in row.dropna()]
            for a, b in combinations(cells, 2):
                vals.update({a - b, b - a, a + b, a * b})
                if b:
                    vals.add(a / b)                       # per game: goals / games
                if a:
                    vals.add(b / a)
            games = row.get("games")
            if games == games and games is not None:     # wins and losses from a win rate
                for x in cells:
                    if 0 <= x <= 1:
                        vals.update({games * x, games * (1 - x)})
    for col, vs in by_col.items():                        # the same stat in two rows or calls
        vs = vs[:80]
        for a, b in combinations(vs, 2):
            vals.update({a - b, b - a, a + b})
            if b:
                vals.add((a - b) / abs(b) * 100)
            if a:
                vals.add((b - a) / abs(a) * 100)
    return vals


def _matches(v, dec, pct, sources):
    tol = 0.5 * 10 ** -dec + 1e-9      # anything that rounds to what was written
    for s in sources:
        for c in (s, s * 100) if pct or dec <= 1 else (s,):
            if abs(c - v) <= tol or abs(abs(c) - abs(v)) <= tol:
                return True
    return False


_FIFTY = re.compile(r"\b(inside|rebound)\s+$", re.I)   # "inside 50", "rebound 50" are names


def unbacked(answer, records, context=""):
    """The numbers in the answer that no record (or the context text: the
    question, the insights) accounts for, as written, in order, no repeats.
    A number worked out from two others the answer itself states and backs
    ("17 of 19 games (89.5%)") counts as backed: the reader can check it."""
    sources = _derived(records) | {v for v, *_ in numbers(context)}
    found = []
    for m, (v, dec, pct, raw) in zip(_NUM.finditer(answer or ""), numbers(answer)):
        if dec == 0 and not pct and (int(v) in YEARS or abs(v) <= 3):
            continue        # years, and "two goals", "top 3" style small counts
        if v == 50 and _FIFTY.search(answer[max(0, m.start() - 12):m.start()]):
            continue
        found.append((v, dec, pct, raw, _matches(v, dec, pct, sources)))
    backed = [v for v, *_, ok in found if ok]
    steps = set()
    for a, b in combinations(backed, 2):
        steps.update({a - b, b - a, a + b})
        for x, y in ((a, b), (b, a)):
            if y:
                steps.update({x / y, x / y * 100})
    out = []
    for v, dec, pct, raw, ok in found:
        if not ok and raw not in out and not _matches(v, dec, pct, steps):
            out.append(raw)
    return out
