"""One-line takeaways under each card title: the card's main point in words,
computed from the same data the card draws, so a coach gets the answer
before reading the chart. Every function returns plain text or "" when there
is nothing sound to say (too few games, missing data).
"""

import pandas as pd

import data as D
from theme import record_text


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---- Season view ------------------------------------------------------------------
def strip(tdf):
    dr = D.margin_drivers(tdf)
    if not len(dr):
        return ""
    top = dr.iloc[0]
    stem = dict(D.DRIVERS_EXT if D.has_ext(tdf) else D.DRIVERS)[top["stat"]]
    won = tdf[tdf[f"freo_{stem}"] > tdf[f"opp_{stem}"]]
    w = int((won["result"] == "W").sum())
    return (f"{top['stat']} tracks the result most: won {w} of {len(won)} games "
            f"when ahead on it")


# The focus functions say which mark a card's chart should pick out: the same
# thing its takeaway names, so the words and the highlight always agree.
def swing_stat(wc):
    """The stat with the biggest win-rate swing (both sides 4+ games), or None."""
    wc = wc.dropna(subset=["ahead_winrate", "behind_winrate"])
    wc = wc[(wc["ahead_games"] >= 4) & (wc["behind_games"] >= 4)]
    if not len(wc):
        return None
    return wc.loc[(wc["ahead_winrate"] - wc["behind_winrate"]).idxmax(), "stat"]


def where_we_win(wc):
    stat = swing_stat(wc)
    if stat is None:
        return ""
    r = wc[wc["stat"] == stat].iloc[0]
    return (f"Biggest swing: {r['stat'].lower()} "
            f"({r['ahead_winrate']:.0f}% v {r['behind_winrate']:.0f}%)")


def best_worst_quarter(qp):
    return qp.loc[qp["margin"].idxmax(), "quarter"], qp.loc[qp["margin"].idxmin(), "quarter"]


def quarters(qp):
    best, worst = qp.loc[qp["margin"].idxmax()], qp.loc[qp["margin"].idxmin()]
    return f"Best {best['quarter']} ({best['margin']:+.1f}), worst {worst['quarter']} ({worst['margin']:+.1f})"


def running(rm):
    if "L" not in rm.index:
        return "No losses to compare"
    lo = rm.loc["L", ["Q1", "Q2", "Q3", "Q4"]]
    return f"Losses: {lo['Q1']:+.1f} at QT, {lo['Q4']:+.1f} at the end"


def leaders(rows):
    names = pd.Series([r["player"] for r in rows if r.get("led")])
    if not len(names):
        return ""
    top, n = names.value_counts().index[0], names.value_counts().iloc[0]
    return f"{top} leads {n} roles" if n > 1 else f"{rows[0]['player']} wins the ball most"


def _form_pct(vals, avgs):
    last3 = vals.iloc[:, -3:]
    pct = (last3.mean(axis=1) / avgs.clip(lower=0.1) * 100).dropna()
    return pct[last3.notna().sum(axis=1) >= 2]


def form_change(vals, avgs):
    """(last-3 average, % of season average) for the players the takeaway ranks:
    2 or more of the last 3 games."""
    last3 = vals.iloc[:, -3:].mean(axis=1)
    pct = _form_pct(vals, avgs)
    return last3[pct.index], pct


def hot_player(vals, avgs):
    pct = _form_pct(vals, avgs)
    return pct.idxmax() if len(pct) else None


def form(vals, avgs):
    pct = _form_pct(vals, avgs)
    if not len(pct):
        return ""
    hot = pct.idxmax()
    return f"Hottest: {hot}, {pct[hot] - 100:+.0f}% on own average over the last 3"


def quarter_games(qp):
    best = qp.loc[qp["margin"].idxmax()]
    return f"{best['quarter']}: Freo won it in {int(best['won'])} of {int(best['games'])} games"


def driver_detail(stat, fit):
    if not fit["ahead"]:
        return f"r {fit['r']:+.2f} over {fit['games']} games"
    return f"Won {fit['ahead_won']} of {fit['ahead']} when ahead on it (r {fit['r']:+.2f})"


def top_driver(dr):
    return dr.iloc[0]["stat"] if len(dr) else None


def drivers(dr):
    if len(dr) < 2:
        return ""
    return f"{dr.iloc[0]['stat']} matters most (r {dr.iloc[0]['r']:+.2f})"


# ---- Match view -----------------------------------------------------------------
def tape(rows):
    counted = [r for r in rows if r["stat"] != "Turnovers"]
    won = sum(r["freo"] > r["opp"] for r in counted)
    return f"Freo won {won} of {len(counted)} counts"


def flow(game, result, margin):
    lead = game.max()
    at = game.idxmax()
    if result == "D":
        return (f"Led by {lead:.0f} at {at}, drew" if lead > 0 else
                f"Trailed by {abs(game.min()):.0f} at {game.idxmin()}, drew" if game.min() < 0
                else "Drew; level at every break")
    word = {"W": "won", "L": "lost"}.get(result, "drew")
    if lead > 0 and result == "L":
        return f"Led by {lead:.0f} at {at}, {word} by {abs(margin)}"
    if game.min() < 0 and result == "W":
        return f"Trailed by {abs(game.min()):.0f} at {game.idxmin()}, {word} by {abs(margin)}"
    return f"{word.capitalize()} by {abs(margin)}; {'never behind' if game.min() >= 0 else 'never ahead'} at a break"


def momentum(events, run, result, margin, opp_label):
    """'Up 17 in Q4, lost by 7: BRL 4.0 unanswered' (short: the card is narrow).
    run: the game's biggest scoring run (data.scoring_runs), or None."""
    lead, trail = int(events["margin"].max()), int(events["margin"].min())
    q_lead = int(events.loc[events["margin"].idxmax(), "quarter"])
    q_trail = int(events.loc[events["margin"].idxmin(), "quarter"])
    word = {"W": f"won by {abs(margin)}", "L": f"lost by {abs(margin)}", "D": "drew"}[result]
    who = "Freo" if run is not None and run["team"] == "Freo" else opp_label
    run_txt = "" if run is None else f"{who} {run['goals']}.{run['behinds']} unanswered"
    if result == "L" and lead > 0:
        head = f"Up {lead} in Q{q_lead}, {word}"
    elif result == "W" and trail < 0:
        head = f"Down {-trail} in Q{q_trail}, {word}"
    else:
        head = word.capitalize()
    return f"{head}: {run_txt}" if run_txt else head


def runs_season(summary):
    """'Conceded a 3+ goal run in 15 of 27 games, won 9 of them'."""
    if not len(summary):
        return ""
    hit = summary[summary["opp_runs"] > 0]
    w = int((hit["result"] == "W").sum())
    return (f"Conceded a {D.RUN_GOALS}+ goal run in {len(hit)} of {len(summary)} games, "
            f"won {w} of them")


def carry(test, label):
    """Does the side that kicked the last goal kick the next one more often?"""
    if not test:
        return ""
    obs, ch = test["observed"] * 100, test["chance"] * 100
    if test["observed"] > test["hi"]:
        return f"Yes in {label}: {obs:.0f}% against {ch:.0f}% by chance"
    return f"No sign of it in {label}: {obs:.0f}% against {ch:.0f}% by chance"


def window_focus(w):
    """The best and the worst window: [(quarter, part), (quarter, part)]."""
    if not len(w):
        return None
    hi, lo = w.loc[w["net"].idxmax()], w.loc[w["net"].idxmin()]
    return [(hi["quarter"], hi["part"]), (lo["quarter"], lo["part"])]


def windows(w):
    if not len(w):
        return ""
    hi, lo = w.loc[w["net"].idxmax()], w.loc[w["net"].idxmin()]
    name = lambda r: f"{r['quarter']} {r['part'].lower()}"
    return f"Best: {name(hi)} ({hi['net']:+.1f} a game); worst: {name(lo)} ({lo['net']:+.1f})"


def run_list(runs, against=True):
    """'19 runs conceded; Freo scored again within 3.2 min on average'."""
    if not len(runs):
        return ""
    who = "Freo" if against else "the opposition"
    ans = runs["answered_in"].dropna()
    tail = f"; {who} replied in {ans.median():.1f} min (median)" if len(ans) else ""
    return f"{len(runs)} runs {'conceded' if against else 'kicked'}{tail}"


def club_last5(games, runs, club_label):
    """'4-1 in their last 5; biggest run 7.2 v ADE (R24)'. games: league rows;
    runs: [(label, biggest run row or None)] in the same order."""
    if not len(games):
        return ""
    w, lo = int((games["result"] == "W").sum()), int((games["result"] == "L").sum())
    head = f"{w}-{lo}" + (f"-{len(games) - w - lo}" if len(games) - w - lo else "") + " in their last 5"
    mine = [(lbl, r) for lbl, r in runs if r is not None and r["team"] == "Freo"]
    if not mine:
        return head
    lbl, r = max(mine, key=lambda x: (x[1]["points"], x[1]["goals"]))
    return f"{head}; their biggest run {r['goals']}.{r['behinds']} ({lbl})"


def season_momentum(avg):
    """'Strongest: the middle of Q3 (+2.0 momentum on average); weakest: early Q2 (-0.4)'.
    avg: data.season_momentum's average momentum on the common clock."""
    if not len(avg):
        return ""
    third = (avg["x"] % D.QUARTER_UNITS // (D.QUARTER_UNITS / 3)).clip(upper=2).astype(int)
    m = avg.groupby([avg["quarter"], third])["momentum"].mean()
    name = lambda k: f"{['early', 'the middle of', 'late'][k[1]]} Q{k[0]}"   # noqa: E731
    hi, lo = m.idxmax(), m.idxmin()
    return f"Strongest: {name(hi)} ({m[hi]:+.1f} momentum on average); weakest: {name(lo)} ({m[lo]:+.1f})"


def match_leaders(goals, opp_goals=None, opp_label=None):
    """'Goals: Voss 3, Dudley 2 · BRL: Neale 3' (the opposition's when known)."""
    text = f"Goals: {goals}" if goals != "none" else "No Freo goals recorded"
    if opp_goals and opp_goals != "none":
        text += f" · {opp_label}: {opp_goals}"
    return text


def vs_self(vals, pct, avgs, stats, n=2):
    """'Biggest games on their own average: Bolton metres gained 686 (+101%), ...'
    (only stats whose season average is big enough for a % to mean much)."""
    from charts import VS_SELF_MIN_AVG
    rows = []
    for lbl, col in stats:
        ok = avgs[col] >= VS_SELF_MIN_AVG.get(col, 0)
        for pl in pct.index[ok]:
            rows.append((pct.at[pl, col], pl, lbl, vals.at[pl, col]))
    rows = sorted((r for r in rows if r[0] == r[0]), reverse=True)[:n]
    if not rows:
        return ""
    return "Biggest on own average: " + ", ".join(
        f"{_short(pl)} {lbl.lower()} {v:.0f} ({p - 100:+.0f}%)" for p, pl, lbl, v in rows)


def match_players(vals):
    if "rating_points" in vals.columns and len(vals):
        top = vals["rating_points"].idxmax()
        return f"Top rated: {top} ({vals.loc[top, 'rating_points']:.0f} rating points)"
    top = vals["disposals"].idxmax()
    return f"Most disposals: {top} ({vals.loc[top, 'disposals']:.0f})"


# ---- Scout view -----------------------------------------------------------------
def style_marks(ranks, team):
    """The club's top 3 and bottom 3 stats (labels), as the style takeaway names them."""
    r = ranks.loc[team]
    labels = {c: l for l, c, _ in D.SCOUT_STATS}
    return ([labels[c] for c in r.index if r[c] <= 3], [labels[c] for c in r.index if r[c] >= 16])


def style(ranks, team):
    top, low = (list(map(str.lower, x)) for x in style_marks(ranks, team))
    parts = []
    if top:
        parts.append("top 3 for " + ", ".join(top[:3]))
    if low:
        parts.append("bottom 3 for " + ", ".join(low[:3]))
    return ("; ".join(parts) or "No top 3 or bottom 3 rankings").capitalize()


def scout_form(games):
    last = games.tail(5)
    w = int((last["result"] == "W").sum())
    return f"Last 5: {w}-{len(last) - w}"


def h2h(rows):
    if not len(rows):
        return ""
    w = int((rows["result"] == "W").sum())
    return f"Fremantle {w}-{len(rows) - w} against them in the data"


# ---- Player view ----------------------------------------------------------------
def player_trend(me, col, label):
    if len(me) < 5:
        return ""
    last5, season = me.tail(5)[col].mean(), me[col].mean()
    change = (last5 - season) / season * 100 if season else 0
    return f"Last 5: {last5:.1f} {label.lower()} a game, {change:+.0f}% on the season average"


def rank_focus(pr):
    """The stats the squad-rank takeaway names: 1sts, else top 3s, else the best."""
    if not len(pr):
        return set()
    first = set(pr[pr["rank"] == 1]["stat"])
    top3 = set(pr[pr["rank"] <= 3]["stat"])
    return first or top3 or {pr.loc[pr["rank"].idxmin(), "stat"]}


def player_ranks(pr):
    if not len(pr):
        return ""
    first = pr[pr["rank"] == 1]["stat"].str.lower().tolist()
    top3 = pr[(pr["rank"] > 1) & (pr["rank"] <= 3)]["stat"].str.lower().tolist()
    if first:
        return "1st in the squad for " + ", ".join(first[:3])
    if top3:
        return "Top 3 in the squad for " + ", ".join(top3[:3])
    best = pr.loc[pr["rank"].idxmin()]
    return f"Best squad rank: {_ordinal(int(best['rank']))} for {best['stat'].lower()}"


def last_game_vs_avg(log, stats):
    """'Last game (GF v BRL): above his average on 6 of 10 stats'."""
    if len(log) < 2:
        return ""
    last = log.iloc[-1]
    cols = [c for _, c in stats]
    above = sum(last[c] > log[c].mean() for c in cols)
    return (f"Last game ({last['round']} v {D.abbr(last['opponent'])}): above his average on "
            f"{above} of {len(cols)} stats")


def player_best(log, col, label):
    if not len(log):
        return ""
    b = log.loc[log[col].idxmax()]
    return f"Best: {b['season']} {b['round']} v {b['opponent']} ({b[col]:.0f} {label.lower()})"


# ---- Player vs player ----------------------------------------------------------
def _short(name):
    return name.split()[-1]


def compare_ahead(cmp, names):
    """'Serong ahead on 8 of 15 stats, Brayshaw on 6'."""
    a = int((cmp["avg_a"] > cmp["avg_b"]).sum())
    b = int((cmp["avg_b"] > cmp["avg_a"]).sum())
    if not a and not b:
        return ""
    first, second = ((names[0], a), (names[1], b)) if a >= b else ((names[1], b), (names[0], a))
    return (f"{_short(first[0])} ahead on {first[1]} of {len(cmp)} stats, "
            f"{_short(second[0])} on {second[1]}")


def compare_gap(cmp, names):
    """The biggest gap relative to the two averages."""
    c = cmp.dropna(subset=["avg_a", "avg_b"])
    c = c[(c["avg_a"] + c["avg_b"]) > 0.5]
    if not len(c):
        return ""
    rel = (c["avg_a"] - c["avg_b"]).abs() / ((c["avg_a"] + c["avg_b"]) / 2)
    r = c.loc[rel.idxmax()]
    who = names[0] if r["avg_a"] > r["avg_b"] else names[1]
    return (f"Biggest gap: {r['stat'].lower()}, {_short(who)} by "
            f"{abs(r['avg_a'] - r['avg_b']):.1f} a game")


def compare_last(logs, names, col, label, n=5):
    """'Last 5: Serong 23.6, Brayshaw 24.0 disposals a game'."""
    parts = [f"{_short(nm)} {log.sort_values('game_dt')[col].tail(n).mean():.1f}"
             for log, nm in zip(logs, names) if len(log)]
    return f"Last {n}: " + ", ".join(parts) + f" {label.lower()} a game" if parts else ""


# ---- Whole squad, all clubs, quarter-time check -------------------------------
def squad_map(pa, xcol, ycol, xlab, ylab):
    """'Most contested poss: Serong 13.2 · most metres gained: Young 498.1'."""
    if not len(pa):
        return ""
    a, b = pa[xcol].idxmax(), pa[ycol].idxmax()
    return (f"Most {xlab.lower()}: {_short(a)} {pa.loc[a, xcol]:.1f} · "
            f"most {ylab.lower()}: {_short(b)} {pa.loc[b, ycol]:.1f}")


def year_on_year(yoy):
    """'Biggest rise: Serong +3.1 · biggest drop: Fyfe -4.0'."""
    if not len(yoy):
        return ""
    up, down = yoy["change"].idxmax(), yoy["change"].idxmin()
    parts = []
    if yoy.loc[up, "change"] > 0:
        parts.append(f"Biggest rise: {_short(up)} {yoy.loc[up, 'change']:+.1f}")
    if yoy.loc[down, "change"] < 0:
        parts.append(f"biggest drop: {_short(down)} {yoy.loc[down, 'change']:+.1f}")
    text = " · ".join(parts)
    return text[:1].upper() + text[1:]


def clubs(grid):
    """'Toughest: Collingwood (0-3, -28.3) · best: West Coast (5-0, +61.2)'."""
    grid = [r for r in grid if r["wins"] + r["losses"] + r["draws"] >= 2]
    if len(grid) < 2:
        return ""
    lo, hi = grid[0], grid[-1]
    rec = lambda r: record_text(r["wins"], r["losses"], r["draws"])  # noqa: E731
    return (f"Toughest: {lo['opponent']} ({rec(lo)}, {lo['avg_margin']:+.1f}) · "
            f"best: {hi['opponent']} ({rec(hi)}, {hi['avg_margin']:+.1f})")


def sim_paths(f, them):
    """'Freo lead at three-quarter time in 59% of games; whoever leads then wins
    85%' (a forecast's path_summary)."""
    lead = f.get("lead")
    if not lead:
        return ""
    text = f"Freo lead at three-quarter time in {lead[2]:.0%} of games"
    if f.get("q3_leader_wins") is not None:
        text += f"; whoever leads then wins {f['q3_leader_wins']:.0%}"
    if f.get("q3_behind_wins") is not None:
        text += f", Freo from behind {f['q3_behind_wins']:.0%}"
    return text


def calibration(ev):
    """How the model's strongest calls came out in its test season: 'When it
    made the home side a 70%+ favourite, they won 96% of those 51 games (it
    said 81%). '"""
    top = next((c for c in ev.get("calibration", []) if c["forecast"].startswith("70%")), None)
    if not top or top["games"] < 10:
        return ""
    return (f"When it made the home side a 70%+ favourite, they won {top['won']:.0%} of those "
            f"{top['games']} games (it said {top['said']:.0%}). ")


def what_if(base, f, moved, levers, them, best=None):
    """'+3 centre clearances a game: Freo's win chance 60% to 66%, margin +8 to
    +12'; with nothing moved, the stat that moves it most (best: (metric,
    change, forecast))."""
    if not moved:
        if not best:
            return f"Freo win {base['win']:.0%} as things stand: move a stat to play the games again"
        m, c, b = best
        return (f"Freo win {base['win']:.0%} as things stand; of these stats, {levers[m]['label'].lower()} "
                f"moves it most ({c:+d} a game: {b['win']:.0%})")
    what = ", ".join(f"{c:+d} {levers[m]['label'].lower()}" for m, c in moved)
    return (f"{what} a game: Freo's win chance {base['win']:.0%} to {f['win']:.0%}, "
            f"typical margin {base['p50']:+.0f} to {f['p50']:+.0f}")
