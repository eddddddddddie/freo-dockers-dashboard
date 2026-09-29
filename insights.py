"""Opening insights for the Wharf-ai panel.

Each candidate is computed with pandas from the loaded CSVs, so every number
shown is calculated, never generated. One is picked at random when the page
opens (or the season changes), so a coach sees a different angle each visit.
Candidates that don't apply (too few games, no baseline, no API stats) are
skipped.
"""

import random

import data as D


def _pct(n, d):
    return n / d * 100 if d else 0.0


def _win_swing(tdf):
    """The stat whose count most changes Freo's win rate."""
    wc = D.win_conditions(tdf).dropna(subset=["ahead_winrate", "behind_winrate"])
    wc = wc[(wc["ahead_games"] >= 4) & (wc["behind_games"] >= 4)]
    if not len(wc):
        return None
    wc = wc.assign(swing=wc["ahead_winrate"] - wc["behind_winrate"])
    r = wc.loc[wc["swing"].idxmax()]
    return (f"**{r['stat']} is the count that matters most.** When Freo win it they win "
            f"{r['ahead_winrate']:.0f}% of {r['ahead_games']} games; when they lose it, "
            f"{r['behind_winrate']:.0f}% of {r['behind_games']}. That is a "
            f"{r['swing']:.0f} point swing, the biggest of any stat on the board.")


def _best_quarter(tdf):
    qp = D.quarter_pattern(tdf)
    best, worst = qp.loc[qp["margin"].idxmax()], qp.loc[qp["margin"].idxmin()]
    return (f"**{best['quarter']} is Freo's quarter.** They outscore opponents by "
            f"{best['margin']:+.1f} points on average and win it {best['won']} times in "
            f"{best['games']} games. The weakest is {worst['quarter']} at "
            f"{worst['margin']:+.1f} ({worst['won']} of {worst['games']} won).")


def _close_games(tdf):
    close = tdf[tdf["margin"].abs() <= 12]
    if len(close) < 3:
        return None
    w = int((close["result"] == "W").sum())
    l = int((close["result"] == "L").sum())
    return (f"**Close games: {w}-{l}.** Of {len(tdf)} games, {len(close)} were decided by "
            f"two goals or less. Freo's win rate in those is {_pct(w, len(close)):.0f}%, "
            f"against {D.record(tdf)['win_pct']:.0f}% overall.")


def _home_away(tdf):
    home, away = tdf[tdf["type"] == "Home"], tdf[tdf["type"] == "Away"]
    if len(home) < 4 or len(away) < 4:
        return None
    hw, aw = (home["result"] == "W").sum(), (away["result"] == "W").sum()
    return (f"**Home {hw}-{len(home) - hw}, away {aw}-{len(away) - aw}.** Average margin "
            f"is {home['margin'].mean():+.1f} at home and {away['margin'].mean():+.1f} away "
            f"(finals excluded).")


def _accuracy_split(tdf):
    wins, losses = tdf[tdf["result"] == "W"], tdf[tdf["result"] == "L"]
    if len(wins) < 3 or len(losses) < 3:
        return None
    def acc(g):
        return _pct(g["freo_goals"].sum(), g["freo_scoring_shots"].sum())
    return (f"**Goal kicking in wins vs losses.** Freo kick {acc(wins):.1f}% of scoring "
            f"shots as goals in wins and {acc(losses):.1f}% in losses, from "
            f"{wins['freo_scoring_shots'].mean():.1f} and "
            f"{losses['freo_scoring_shots'].mean():.1f} shots a game.")


def _biggest_change(team_df, season, baseline):
    if baseline is None:
        return None
    tiles = [t for t in D.tiles(team_df, season, baseline) if t["change"] is not None]
    # Compare changes on a common scale: size of the change relative to last season.
    def scale(t):
        return abs(t["change"]) if t["unit"] == "%" else abs(t["change"]) / max(abs(t["base"]), 1) * 100
    if not tiles:
        return None
    t = max(tiles, key=scale)
    fmt = "{:+.1f}" if t["kind"] == "diff" else "{:.1f}"
    return (f"**Biggest shift since {baseline}: {t['label'].lower()}.** It has moved from "
            f"{fmt.format(t['base'])} to {fmt.format(t['value'])} per game "
            f"({t['change']:+.1f}{t['unit'] or ''}).")


def _hot_form(pdf):
    """The player furthest above their own season average over the last 5 games."""
    stat, label = ("metres_gained", "metres gained") if "metres_gained" in pdf.columns \
        else ("disposals", "disposals")
    order = pdf.drop_duplicates(["round", "opponent"]).sort_values("game_dt")
    last5 = order.tail(5)["round"]
    season = pdf.groupby("player")[stat].agg(["mean", "count"])
    recent = pdf[pdf["round"].isin(last5)].groupby("player")[stat].agg(["mean", "count"])
    j = season.join(recent, rsuffix="_5").dropna()
    j = j[(j["count"] >= 8) & (j["count_5"] >= 4)]
    if not len(j):
        return None
    j = j.assign(lift=(j["mean_5"] - j["mean"]) / j["mean"].clip(lower=1) * 100)
    name = j["lift"].idxmax()
    r = j.loc[name]
    return (f"**{name} is in form.** {r['mean_5']:.1f} {label} a game across the last "
            f"{int(r['count_5'])} games played, up {r['lift']:.0f}% on a season average of "
            f"{r['mean']:.1f}.")


def _centre_vs_stoppage(tdf):
    if not D.has_ext(tdf):
        return None
    c = (tdf["freo_centre_clearances"] - tdf["opp_centre_clearances"]).mean()
    s = (tdf["freo_stoppage_clearances"] - tdf["opp_stoppage_clearances"]).mean()
    def verdict(x):
        return "roughly even" if abs(x) < 0.5 else ("ahead" if x > 0 else "behind")
    return (f"**Clearances split: centre {c:+.1f}, stoppage {s:+.1f} a game.** "
            f"Freo are {verdict(c)} at centre bounces and {verdict(s)} at stoppages "
            f"around the ground.")


def candidates(team_df, player_df, season, baseline):
    tdf = D.team_season(team_df, season)
    pdf = D.players_season(player_df, season)
    if len(tdf) < 5:
        return []
    out = [_win_swing(tdf), _best_quarter(tdf), _close_games(tdf), _home_away(tdf),
           _accuracy_split(tdf), _biggest_change(team_df, season, baseline),
           _hot_form(pdf), _centre_vs_stoppage(tdf)]
    return [c for c in out if c]


def pick(team_df, player_df, season, baseline, avoid=None):
    """A random insight for the season, avoiding the last one shown if possible."""
    pool = candidates(team_df, player_df, season, baseline)
    if avoid in pool and len(pool) > 1:
        pool.remove(avoid)
    return random.choice(pool) if pool else None
