"""Wharf-ai accuracy test set.

Asks Wharf-ai 27 questions whose answers are known, and checks each answer
for the right number, record, name or refusal. Expected values are computed
here with plain pandas from the CSVs (not through Wharf-ai's own tools), so
the checks stay correct when the data is refreshed and a tool bug can't hide
behind itself. Grading is deterministic string/number matching, no model.

Run (needs ANTHROPIC_API_KEY, spends real money, about US$0.30-0.60 a run):
    python evals/wharf_eval.py            # all cases (25 Freo + 2 league)
    python evals/wharf_eval.py 3 7 12     # just these case numbers

Writes evals/results/<timestamp>.json. Exit code 1 if any case fails.
"""

import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import chatbot as C  # noqa: E402
import data as D  # noqa: E402
import usage as U  # noqa: E402

S = 2026  # the season the questions are about unless they say otherwise


def _qtr(qtrs):
    cum = [6 * int(g) + int(b) for g, b in (q.split(".") for q in qtrs.split())]
    return cum


def build_cases():
    """(question, check type, expected). Checks: num (value, tolerance),
    nums (all values), record ("W-L"), text (any of these phrases)."""
    t = D.load_team()
    p = D.load_players()
    t26, p26 = t[t["season"] == S], p[p["season"] == S]
    w26, l26 = t26[t26["result"] == "W"], t26[t26["result"] == "L"]

    def rec(df):
        w = int((df["result"] == "W").sum())
        return f"{w}-{len(df) - w}"

    def pooled(df):
        return df["freo_goals"].sum() / (df["freo_goals"] + df["freo_behinds"]).sum() * 100

    i50 = t26[t26["freo_inside_50s"] > t26["opp_inside_50s"]]
    run = pd.DataFrame([[f - o for f, o in zip(_qtr(a), _qtr(b))]
                        for a, b in zip(l26["freo_qtrs"], l26["opp_qtrs"])])
    q3 = pd.DataFrame([[f - o for f, o in zip(_qtr(a), _qtr(b))]
                       for a, b in zip(t26["freo_qtrs"], t26["opp_qtrs"])])
    q3_margin = (q3[2] - q3[1]).mean()
    mg = p26.groupby("player").agg(n=("metres_gained", "size"), m=("metres_gained", "mean"))
    top_mg = mg[mg["n"] >= 10]["m"].idxmax()
    lead = D.role_leaders(D.players_season(p, S))[0]["player"]
    bolton_r3 = p26[(p26["player"] == "Shai Bolton") & (p26["round"] == "R3")]["disposals"].iloc[0]
    gf = t26[t26["round"] == "GF"].iloc[0]
    top_game = t26.loc[t26["freo_score"].idxmax()]
    best_goals = sorted(p26[p26["goals"] == p26["goals"].max()]["player"].unique())  # ties count
    geel = t[t["opponent"] == "Geelong"]
    diff = lambda s: (t26[f"freo_{s}"] - t26[f"opp_{s}"]).mean()  # noqa: E731

    return [
        ("What was our home record in 2026 (home games only, not finals)?", "record",
         rec(t26[t26["type"] == "Home"])),
        ("What was our average winning or losing margin in away games in 2026?", "num",
         (t26[t26["type"] == "Away"]["margin"].mean(), 0.15)),
        ("How many goals did Jye Amiss kick in 2026?", "num",
         (p26[p26["player"] == "Jye Amiss"]["goals"].sum(), 0)),
        ("What did Caleb Serong average in disposals per game in 2026?", "num",
         (p26[p26["player"] == "Caleb Serong"]["disposals"].mean(), 0.1)),
        ("What was our goal kicking accuracy for the whole 2026 season?", "num",
         (pooled(t26), 0.15)),
        ("What was the final score in the 2026 grand final?", "nums",
         [gf["freo_score"], gf["opp_score"]]),
        ("In 2026, what was our win rate in games where we won the inside 50 count?", "num",
         ((i50["result"] == "W").mean() * 100, 1.0)),
        ("How strongly does our metres gained differential correlate with the final margin "
         "in 2026? Give the correlation coefficient.", "num",
         ((t26["freo_metres_gained"] - t26["opp_metres_gained"]).corr(t26["margin"]), 0.01)),
        ("What was our win-loss record in 2025?", "record", rec(t[t["season"] == 2025])),
        ("Who led our team in contested possessions in the most games in 2026?", "text", [lead]),
        ("In our 2026 losses, what was our average margin at three quarter time?", "num",
         (run[2].mean(), 0.15)),
        ("What is our win-loss record against Geelong across 2025 and 2026?", "record", rec(geel)),
        ("How many disposals did Shai Bolton have in round 3 of 2026?", "num", (bolton_r3, 0)),
        ("Where on the ground did we take our shots at goal in the grand final?", "text",
         ["don't have", "do not have", "not available", "isn't in", "is not in", "not in the data",
          "no shot location", "doesn't include", "does not include", "can't tell", "cannot tell"]),
        ("What was our goal kicking accuracy in games we won in 2026?", "num", (pooled(w26), 0.15)),
        ("Which player averaged the most metres gained per game in 2026, with at least 10 games?",
         "text", [top_mg]),
        ("What was our average clearance differential per game in 2026?", "num",
         (diff("clearances"), 0.1)),
        ("How many games did we play in 2026, including finals?", "num", (len(t26), 0)),
        ("What was our average centre clearance differential per game in 2026?", "num",
         (diff("centre_clearances"), 0.1)),
        ("How many pressure acts did we average per game in 2026?", "num",
         (t26["freo_pressure_acts"].mean(), 0.15)),
        ("What was our average score in the games we lost in 2026?", "num",
         (l26["freo_score"].mean(), 0.15)),
        ("What was our average margin in third quarters in 2026 (points in Q3 only)?", "num",
         (q3_margin, 0.15)),
        ("Which Fremantle player kicked the most goals in a single game in 2026?", "text",
         best_goals),
        ("What was our record in 2026 finals?", "record", rec(t26[t26["type"] == "Final"])),
        ("What was our highest score in a game in 2026?", "num", (top_game["freo_score"], 0)),
    ] + league_cases()


def league_cases():
    """Opponent questions, answered from every club's games (skipped if not scraped)."""
    lg = D.load_league()
    if lg is None:
        return []
    lad = D.ladder(lg, S)
    pos = int(lad.loc["Brisbane Lions", "position"])
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
             7: "seventh", 8: "eighth"}
    syd = lad.loc["Sydney"]
    return [
        ("Where did the Brisbane Lions finish on the 2026 ladder?", "text",
         [f"{pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd' if pos == 3 else 'th'}",
          words.get(pos, "")]),
        ("What was Sydney's home and away win-loss record in 2026?", "record",
         f"{int(syd['wins'])}-{int(syd['losses'])}"),
    ]


NUM = re.compile(r"[-+−]?\d[\d,]*(?:\.\d+)?")


def numbers(text):
    return [float(n.replace(",", "").replace("−", "-")) for n in NUM.findall(text)]


def grade(kind, expected, answer):
    a = answer.replace("–", "-").replace("—", "-")
    if kind == "num":
        val, tol = expected
        # A negative value may be written without its sign ("down by 8.2"), so accept
        # the magnitude for negative expectations.
        return any(abs(n - val) <= tol + 1e-9
                   or (val < 0 and abs(abs(n) - abs(val)) <= tol + 1e-9)
                   for n in numbers(a))
    if kind == "nums":
        found = numbers(a)
        return all(any(abs(n - v) < 1e-9 for n in found) for v in expected)
    if kind == "record":
        w, l = expected.split("-")
        return bool(re.search(rf"\b{w}\s*-\s*{l}\b", a)) or bool(
            re.search(rf"\b{w} wins?\b.*\b{l} loss", a, re.I | re.S))
    if kind == "text":
        return any(e.lower() in a.lower() for e in expected)
    raise ValueError(kind)


def show(expected):
    if isinstance(expected, tuple):
        return f"{expected[0]:.2f}" if isinstance(expected[0], float) else str(expected[0])
    return str(expected)


def main(only):
    client = C.get_client()
    if client is None:
        sys.exit("ANTHROPIC_API_KEY is not set (environment or .streamlit/secrets.toml).")
    cases = build_cases()
    results, total = [], U.Tally()
    for i, (q, kind, exp) in enumerate(cases, 1):
        if only and i not in only:
            continue
        tally, start = U.Tally(), time.time()
        try:
            answer = "".join(C.stream_answer(client, S, [{"role": "user", "content": q}],
                                             on_tool=lambda n, a: tally.tools.append(n),
                                             on_usage=tally.add_usage))
            error = None
        except Exception as exc:  # record API failures as failed cases
            answer, error = "", str(exc)
        ok = error is None and grade(kind, exp, answer)
        for k in ("input", "output", "cache_read", "cache_write", "steps"):
            setattr(total, k, getattr(total, k) + getattr(tally, k))
        results.append({"case": i, "question": q, "check": kind, "expected": show(exp),
                        "pass": ok, "answer": answer, "error": error, "tools": tally.tools,
                        "seconds": round(time.time() - start, 1), "cost_usd": round(tally.cost(), 4)})
        print(f"{'PASS' if ok else 'FAIL'}  {i:>2}. {q[:70]:<70} expected {show(exp)}")
        if not ok:
            print("        answer:", (error or answer).replace("\n", " ")[:300])
    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} passed · cost US${total.cost():.2f} · "
          f"{total.steps} model requests")
    os.makedirs("evals/results", exist_ok=True)
    out = f"evals/results/{datetime.now():%Y%m%d-%H%M%S}.json"
    with open(out, "w") as f:
        json.dump({"model": C.MODEL, "passed": passed, "total": len(results),
                   "cost_usd": round(total.cost(), 4), "results": results}, f, indent=2)
    print("Saved", out)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main({int(a) for a in sys.argv[1:]}))
