"""Wharf-ai accuracy test set.

Asks Wharf-ai 38 questions whose answers are known, and checks each answer
for the right number, record, name or refusal. Expected values are computed
here with plain pandas from the CSVs (not through Wharf-ai's own tools), so
the checks stay correct when the data is refreshed and a tool bug can't hide
behind itself. Grading is deterministic string/number matching, no model.

Run (needs ANTHROPIC_API_KEY, spends real money, about US$0.30-0.60 a run):
    python evals/wharf_eval.py            # all cases (26 Freo + 2 league + 6 newer + 4 momentum)
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
import evidence as E  # noqa: E402
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
    geel = t[(t["opponent"] == "Geelong") & t["season"].isin([2025, 2026])]   # as the question says
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
        # Player vs player: both averages must be right, not just the winner's.
        ("Who averaged more contested possessions in 2026, Caleb Serong or Andrew Brayshaw, "
         "and by how much?", "nums",
         [round(p26[p26["player"] == n]["contested_poss"].mean(), 1)
          for n in ("Caleb Serong", "Andrew Brayshaw")]),
    ] + league_cases() + newer_cases(t, p) + momentum_cases(t)


def newer_cases(t, p):
    """The pickers' whole-list pages (squad, clubs, quarter-time), draws, and the
    opposition's players (opp_players)."""
    t24, t26 = t[t["season"] == 2024], t[t["season"] == S]
    w24, l24 = int((t24["result"] == "W").sum()), int((t24["result"] == "L").sum())
    ht = pd.Series([_qtr(a)[1] - _qtr(b)[1] for a, b in zip(t26["freo_qtrs"], t26["opp_qtrs"])],
                   index=t26.index)
    behind = t26[ht < 0]
    by = lambda s: p[p["season"] == s].groupby("player")["disposals"].agg(["size", "mean"])  # noqa: E731
    yy = by(2025)[lambda d: d["size"] >= 8].join(by(2026)[lambda d: d["size"] >= 8],
                                                 lsuffix="_a", rsuffix="_b", how="inner")
    riser = (yy["mean_b"] - yy["mean_a"]).idxmax()
    toughest = t.groupby("opponent")["margin"].mean().idxmin()
    cases = [
        ("Which player's disposals per game rose the most from 2025 to 2026, among players "
         "with at least 8 games in both seasons?", "text", [riser]),
        ("Against which club have we had the lowest average margin across 2024 to 2026?",
         "text", [toughest]),
        ("In 2026, what was our win-loss record in games where we were behind at half time?",
         "record", f"{int((behind['result'] == 'W').sum())}-{int((behind['result'] == 'L').sum())}"),
        ("What was our win-loss-draw record in 2024?", "all",
         [("record", f"{w24}-{l24}"), ("text", ["draw", "drew", f"{w24}-{l24}-"])]),
    ]
    if not os.path.exists(D.OPP_PLAYER_CSV):
        return cases
    raw = pd.read_csv(D.OPP_PLAYER_CSV)
    gf = t26[t26["round"] == "GF"].iloc[0]
    gfp = raw[(raw["season"] == S) & (raw["opponent"] == gf["opponent"])
              & (raw["date_local"] == gf["game_dt"].strftime("%Y-%m-%d"))]
    top = gfp.loc[gfp["disposals"].idxmax()]
    r26 = raw[raw["season"] == S]
    tacklers = sorted(r26[r26["tackles"] == r26["tackles"].max()]["player"].unique())
    return cases + [
        (f"Who had the most disposals for {gf['opponent']} in the 2026 grand final, and how "
         "many?", "all", [("text", [top["player"]]), ("num", (float(top["disposals"]), 0))]),
        ("Which opposition player laid the most tackles in a single game against us in 2026?",
         "text", tacklers),
    ]


def momentum_cases(t):
    """Scores in order (the momentum tool), expected values from the raw events CSV."""
    if not os.path.exists(D.EVENTS_CSV):
        return []
    ev = pd.read_csv(D.EVENTS_CSV)
    e26 = ev[ev["season"] == S]
    gf = e26[e26["round"] == "GF"].sort_values("event")
    tail = 0
    for team, kind in zip(gf["team"][::-1], gf["kind"][::-1]):
        if team != "Opp":
            break
        tail += kind == "goal"
    opp_runs, lost_after_q4_lead = 0, 0
    res = t[t["season"] == S].set_index("round")["result"]
    for rnd, g in e26.groupby("round"):
        g = g.sort_values("event")
        block = (g["team"] != g["team"].shift()).cumsum()
        goals = g.assign(goal=g["kind"] == "goal").groupby(block).agg(team=("team", "first"),
                                                                       goals=("goal", "sum"))
        opp_runs += int(((goals["team"] == "Opp") & (goals["goals"] >= 3)).sum())
        m = g["freo_score"] - g["opp_score"]
        q4 = pd.concat([m[g["quarter"] < 4].tail(1), m[g["quarter"] == 4]])
        lost_after_q4_lead += bool(res[rnd] == "L" and (q4 > 0).any())
    same = pairs = 0
    for _, g in ev[ev["kind"] == "goal"].sort_values("event").groupby(["season", "round", "quarter"]):
        teams = g["team"].tolist()
        pairs += len(teams) - 1
        same += sum(a == b for a, b in zip(teams, teams[1:]))
    gf_opp = t[(t["season"] == S) & (t["round"] == "GF")]["opponent"].iloc[0]
    return [
        (f"How many goals in a row did {gf_opp} kick to finish the 2026 grand final?",
         "num", (float(tail), 0)),
        ("In 2026, how many runs of three or more unanswered goals did the opposition kick "
         "against us?", "num", (float(opp_runs), 0)),
        ("In 2026, how many games did we lose after leading at some point in the last quarter?",
         "num", (float(lost_after_q4_lead), 0)),
        ("Across 2024 to 2026, after a goal, what percentage of the time was the next goal in "
         "the same quarter kicked by the same team?", "num", (round(same / pairs * 100, 1), 0.1)),
    ]


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
        # Whole numbers exactly; decimals to the one place given (11.38 or 11.4 for 11.4).
        return all(any(abs(n - v) <= (1e-9 if float(v).is_integer() else 0.05 + 1e-9)
                       for n in found) for v in expected)
    if kind == "record":
        w, l = expected.split("-")
        losses = rf"(?:{l}|no)" if l == "0" else l       # "11 wins ... no losses" is 11-0
        phrased = l == "0" and bool(re.search(rf"\ball {w}\b", a, re.I))   # "won all 11"
        n = int(w) + int(l)                        # "11 wins from 11 games" (no draws in the cases)
        phrased = phrased or bool(re.search(rf"\b{w} wins? (?:from|in|out of|of) {n} games", a, re.I))
        return phrased or bool(re.search(rf"\b{w}\s*-\s*{l}\b", a)) or bool(
            re.search(rf"\b{w} wins?\b.*\b{losses} loss", a, re.I | re.S))
    if kind == "text":
        return any(e.lower() in a.lower() for e in expected)
    if kind == "all":       # every one of several checks, e.g. a name and its number
        return all(grade(k, e, answer) for k, e in expected)
    raise ValueError(kind)


def show(expected):
    if isinstance(expected, list) and expected and isinstance(expected[0], tuple) \
            and isinstance(expected[0][0], str) and expected[0][0] in ("text", "num", "nums", "record"):
        return " + ".join(show(e) for _, e in expected)
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
        tally, start, found = U.Tally(), time.time(), []
        try:
            answer = "".join(C.stream_answer(
                client, S, [{"role": "user", "content": q}],
                on_tool=lambda n, a: tally.tools.append(n), on_usage=tally.add_usage,
                on_result=lambda n, a, out, err: None if err else found.append(E.item(n, a, out))))
            error = None
        except Exception as exc:  # record API failures as failed cases
            answer, error = "", str(exc)
        ok = error is None and grade(kind, exp, answer)
        flagged = E.unbacked(answer, found, context=q)
        for k in ("input", "output", "cache_read", "cache_write", "steps"):
            setattr(total, k, getattr(total, k) + getattr(tally, k))
        results.append({"case": i, "question": q, "check": kind, "expected": show(exp),
                        "pass": ok, "answer": answer, "error": error, "tools": tally.tools,
                        "seconds": round(time.time() - start, 1), "cost_usd": round(tally.cost(), 4),
                        "unbacked": flagged, "evidence": found})
        print(f"{'PASS' if ok else 'FAIL'}  {i:>2}. {q[:70]:<70} expected {show(exp)}")
        if not ok:
            print("        answer:", (error or answer).replace("\n", " ")[:300])
        if flagged:
            print("        not matched to a calculation:", ", ".join(flagged))
    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} passed · cost US${total.cost():.2f} · "
          f"{total.steps} model requests")
    nums = sum(len(E.numbers(r["answer"])) for r in results)
    flags = sum(len(r["unbacked"]) for r in results)
    print(f"Unmatched numbers: {flags} of {nums} in {sum(bool(r['unbacked']) for r in results)} "
          "answers (the answers are checked correct, so these are mostly the check's false alarms)")
    os.makedirs("evals/results", exist_ok=True)
    out = f"evals/results/{datetime.now():%Y%m%d-%H%M%S}.json"
    with open(out, "w") as f:
        json.dump({"model": C.MODEL, "passed": passed, "total": len(results),
                   "cost_usd": round(total.cost(), 4), "results": results}, f, indent=2)
    print("Saved", out)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main({int(a) for a in sys.argv[1:]}))
