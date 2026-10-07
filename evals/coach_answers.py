"""The expected answers for the coach session tasks (docs/coach_sessions.md),
worked out with plain pandas from the current data, so the session sheet never
goes stale after a data refresh. Run before each round of sessions:

    python evals/coach_answers.py          # 2026
    python evals/coach_answers.py 2027     # another season (its grand final, if played)
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import charts as CH  # noqa: E402
import data as D  # noqa: E402
import takeaways as T  # noqa: E402


def _qtrs(s):
    return [6 * int(g) + int(b) for g, b in (x.split(".") for x in s.split())]


def main(season):
    t, p, lg = D.load_team(), D.load_players(), D.load_league()
    ts, ps = D.team_season(t, season), D.players_season(p, season)
    rec = D.record(ts)
    out = []

    # 1. The season in one sentence
    line = f"{rec['wins']}-{rec['losses']}" + (f"-{rec['draws']}" if rec["draws"] else "")
    if lg is not None:
        f = D.ladder(lg, season).loc["Fremantle"]
        line += (f"; home and away {int(f['wins'])}-{int(f['losses'])}, "
                 f"{T._ordinal(int(f['position']))} on the ladder ({f['pct']:.1f}%)")
    last = ts.iloc[-1]
    line += (f"; last game {last['round']} v {last['opponent']}, "
             f"{'won' if last['margin'] > 0 else 'lost' if last['margin'] < 0 else 'drew'} "
             f"{int(last['freo_score'])}-{int(last['opp_score'])}")
    out.append(("1. The season in one sentence", line))

    # 2. Why did we lose (or win) the last game
    g = last
    fa = g["freo_goals"] / (g["freo_goals"] + g["freo_behinds"]) * 100
    oa = g["opp_goals"] / (g["opp_goals"] + g["opp_behinds"]) * 100
    run = [a - b for a, b in zip(_qtrs(g["freo_qtrs"]), _qtrs(g["opp_qtrs"]))]
    out.append((f"2. Why the {g['round']} result", (
        f"Freo {int(g['freo_goals'])}.{int(g['freo_behinds'])} ({fa:.1f}%) to "
        f"{int(g['opp_goals'])}.{int(g['opp_behinds'])} ({oa:.1f}%), from "
        f"{int(g['freo_goals'] + g['freo_behinds'])} scoring shots to "
        f"{int(g['opp_goals'] + g['opp_behinds'])}; inside 50s {int(g['freo_inside_50s'])}-"
        f"{int(g['opp_inside_50s'])}, clearances {int(g['freo_clearances'])}-"
        f"{int(g['opp_clearances'])}, contested poss {int(g['freo_contested_poss'])}-"
        f"{int(g['opp_contested_poss'])}; margin at each break {run}")))

    # 3. Who played above themselves in that game (the players table's tinted cells)
    cols = ["disposals", "contested_poss", "clearances", "inside_50s", "metres_gained",
            "score_involvements", "tackles", "pressure_acts", "goals"]
    cols = [c for c in cols if c in ps.columns]
    vals, pct, avgs = D.match_players(ps, g, cols)
    picks = [(pl, c, vals.at[pl, c], pct.at[pl, c] - 100) for c in cols
             for pl in pct.index[avgs[c] >= CH.VS_SELF_MIN_AVG.get(c, 0)] if pct.at[pl, c] >= 130]
    most = Counter(pl for pl, *_ in picks).most_common(4)
    top = sorted(picks, key=lambda r: -r[3])[:5]
    out.append((f"3. Who played above themselves in {g['round']}", (
        "most tinted cells: " + ", ".join(f"{pl} ({n})" for pl, n in most) + "; biggest: "
        + ", ".join(f"{pl} {c.replace('_', ' ')} {v:.0f} ({d:+.0f}%)" for pl, c, v, d in top))))

    # 4. Against the top 8
    if lg is not None:
        tv, _ = D.slice_games(t, p, "vs top 8", lg)
        tt = D.team_season(tv, season)
        r8 = D.record(tt)
        out.append(("4. Against the top 8 (Games: vs top 8)", (
            f"{r8['wins']}-{r8['losses']}, average margin {r8['margin']:+.1f} (all games "
            f"{rec['margin']:+.1f}); {T.where_we_win(D.win_conditions(tt))}; "
            f"{T.drivers(D.margin_drivers(tt))}")))

    # 5. The last opponent, scouted
    opp = g["opponent"]
    if lg is not None and opp in D.ladder(lg, season).index:
        o = D.ladder(lg, season).loc[opp]
        _, ranks = D.team_ranks(lg, season)
        h = D.record(t[t["opponent"] == opp])
        extra = ""
        if os.path.exists(D.OPP_PLAYER_CSV):
            raw = pd.read_csv(D.OPP_PLAYER_CSV)
            og = raw[(raw["season"] == season) & (raw["opponent"] == opp)
                     & (raw["date_local"] == g["game_dt"].strftime("%Y-%m-%d"))]
            if len(og):
                b = og.loc[og["disposals"].idxmax()]
                extra = f"; their most disposals in {g['round']}: {b['player']} {b['disposals']:.0f}"
        out.append((f"5. {opp}, scouted", (
            f"{T._ordinal(int(o['position']))} on the ladder, {int(o['wins'])}-{int(o['losses'])} ({o['pct']:.1f}%); "
            f"{T.style(ranks, opp)}; {T.where_we_win(D.scout_win_conditions(lg, opp, season))}; "
            f"Freo v {opp}, all seasons: {h['wins']}-{h['losses']}" + extra)))

    # 6. One thing that decides our games
    dr = D.margin_drivers(ts)
    _, fit = D.driver_points(ts, dr.iloc[0]["stat"])
    out.append(("6. One thing that decides our games", (
        f"{dr.iloc[0]['stat']} differential (r {dr.iloc[0]['r']:+.2f}), then "
        f"{dr.iloc[1]['stat'].lower()} (r {dr.iloc[1]['r']:+.2f}); won {fit['ahead_won']} of "
        f"{fit['ahead']} when ahead on {dr.iloc[0]['stat'].lower()}. Association, not cause.")))

    # 7. (if time) Is Caleb Serong in form?
    me = ps[ps["player"] == "Caleb Serong"].sort_values("game_dt")
    before = p[(p["season"] == season - 1) & (p["player"] == "Caleb Serong")]
    if len(me):
        pr = D.player_squad_ranks(ps, "Caleb Serong")
        firsts = ", ".join(pr[pr["rank"] == 1]["stat"].str.lower()) or "none"
        change = (f", {(me['disposals'].mean() / before['disposals'].mean() - 1) * 100:+.0f}% on "
                  f"{season - 1}" if len(before) else "")
        out.append(("7. Is Caleb Serong in form? (if time)", (
            f"{me['disposals'].mean():.1f} disposals a game{change}; last 5 "
            f"{me['disposals'].tail(5).mean():.1f}; 1st in the squad for {firsts}")))

    print(f"Expected answers, {season} (data as loaded now)\n")
    for task, answer in out:
        print(f"{task}\n   {answer}\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
