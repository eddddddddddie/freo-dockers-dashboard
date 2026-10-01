"""Turn Wharf-ai feedback into candidate test cases.

Reads the usage log (the CSV from Deep dives -> Wharf-ai usage -> Download, or
the local wharf_usage.sqlite), and lists every answer rated thumbs down or with
a number not matched to a calculation: question, answer, tools and flags.
Writes evals/results/feedback_<date>.md. For each one worth keeping, work out
the right answer with plain pandas and add it to build_cases() in
wharf_eval.py, so the test set grows from real questions.

    python evals/review_feedback.py                       # local log
    python evals/review_feedback.py wharf_usage_2026-10-01.csv
"""

import os
import sqlite3
import sys
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path=None):
    if path:
        return pd.read_csv(path)
    db = os.environ.get("USAGE_DB") or os.path.join(ROOT, "wharf_usage.sqlite")
    if not os.path.exists(db):
        sys.exit(f"No usage log at {db}. Download the CSV from the app and pass its path.")
    with sqlite3.connect(db) as con:
        return pd.read_sql("SELECT * FROM questions ORDER BY ts", con)


def main(path=None):
    df = load(path)
    for col in ("rating", "unbacked", "answer"):
        if col not in df.columns:
            df[col] = None
    rating = df["rating"].astype(str).str.strip()
    down = rating.isin(["0", "0.0", "👎"])
    flagged = ~df["unbacked"].fillna("").astype(str).str.strip().isin(["", "[]"])
    pick = df[down | flagged]
    lines = [f"# Wharf-ai feedback review, {datetime.now():%d %b %Y}", "",
             f"{len(df)} questions in the log; {int(down.sum())} rated thumbs down; "
             f"{int(flagged.sum())} with a number not matched to a calculation.", ""]
    for _, r in pick.iterrows():
        why = ", ".join(w for w, on in (("thumbs down", down[_]), ("unmatched numbers", flagged[_])) if on)
        lines += [f"## {r['question']}", "", f"- When: {r.get('ts', '')}  ·  Why listed: {why}",
                  f"- Tools: {r.get('tools', '')}",
                  f"- Not matched: {r['unbacked'] if flagged[_] else 'none'}", "",
                  "Answer:", "", "> " + str(r["answer"] or "(not logged)").replace("\n", "\n> "), "",
                  "Candidate test case (fill in the expected value from plain pandas):", "",
                  f'    ({r["question"]!r}, "num", (EXPECTED, 0.1)),', ""]
    os.makedirs(os.path.join(ROOT, "evals", "results"), exist_ok=True)
    out = os.path.join(ROOT, "evals", "results", f"feedback_{datetime.now():%Y%m%d}.md")
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"{len(pick)} answers to review. Saved {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
