"""Data loading and derived metrics for the Fremantle Dockers dashboard.

Reads the two CSVs produced by freo_scraper.py and adds only derived values
(scoring shots, accuracy, chronological ordering, per game averages). Team
totals are used for goal accuracy because team behinds include rushed behinds
that summed player behinds do not.
"""

import pandas as pd
import streamlit as st

PLAYER_CSV = "freo_player_games.csv"
TEAM_CSV = "freo_team_games.csv"
DATE_FMT = "%a %d-%b-%Y %I:%M %p"


@st.cache_data
def load_team():
    df = pd.read_csv(TEAM_CSV)
    df["game_dt"] = pd.to_datetime(df["date"], format=DATE_FMT, errors="coerce")
    df["freo_scoring_shots"] = df["freo_goals"] + df["freo_behinds"]
    df["opp_scoring_shots"] = df["opp_goals"] + df["opp_behinds"]
    # Accuracy from team totals (includes rushed behinds). Guard divide by zero.
    df["freo_accuracy"] = df["freo_goals"] / df["freo_scoring_shots"].replace(0, pd.NA) * 100
    df["opp_accuracy"] = df["opp_goals"] / df["opp_scoring_shots"].replace(0, pd.NA) * 100
    df = df.sort_values("game_dt").reset_index(drop=True)
    return df


@st.cache_data
def load_players():
    df = pd.read_csv(PLAYER_CSV)
    df["game_dt"] = pd.to_datetime(df["date"], format=DATE_FMT, errors="coerce")
    df["forward_threat"] = df["goals"] + df["goal_assists"]
    df = df.sort_values("game_dt").reset_index(drop=True)
    return df


def seasons(df):
    return sorted(int(s) for s in df["season"].unique())


def baseline_season(season, all_seasons):
    """The previous season available, or None if the selected season is earliest."""
    earlier = [s for s in all_seasons if s < season]
    return max(earlier) if earlier else None


def team_season(team_df, season):
    """Games for one season, in chronological order."""
    return team_df[team_df["season"] == season].sort_values("game_dt").reset_index(drop=True)


def players_season(player_df, season):
    return player_df[player_df["season"] == season].sort_values("game_dt").reset_index(drop=True)


def record(tdf):
    wins = int((tdf["result"] == "W").sum())
    losses = int((tdf["result"] == "L").sum())
    games = len(tdf)
    win_pct = wins / games * 100 if games else 0.0
    return {
        "games": games, "wins": wins, "losses": losses, "win_pct": win_pct,
        "score_for": tdf["freo_score"].mean() if games else 0.0,
        "score_against": tdf["opp_score"].mean() if games else 0.0,
        "margin": tdf["margin"].mean() if games else 0.0,
    }


# Metrics shown in the current vs baseline comparison table. Each is a per game
# average of a Freo column (accuracy is already a percentage).
COMPARISON_METRICS = [
    ("Score for", "freo_score"),
    ("Score against", "opp_score"),
    ("Margin", "margin"),
    ("Goal accuracy %", "freo_accuracy"),
    ("Disposals", "freo_disposals"),
    ("Clearances", "freo_clearances"),
    ("Contested poss", "freo_contested_poss"),
    ("Inside 50s", "freo_inside_50s"),
    ("Marks", "freo_marks"),
    ("Tackles", "freo_tackles"),
    ("Rebound 50s", "freo_rebound_50s"),
    ("One percenters", "freo_one_percenters"),
]


def comparison_frame(team_df, season, baseline):
    """Per game averages for the selected season, the baseline season, and the
    percentage change. Returns a display DataFrame."""
    cur = team_season(team_df, season)
    rows = []
    base = team_season(team_df, baseline) if baseline is not None else None
    # Win % is a rate, not an average, so handle it first.
    cur_rec = record(cur)
    if base is not None:
        base_rec = record(base)
        rows.append(_row("Win %", cur_rec["win_pct"], base_rec["win_pct"], pct=True))
    else:
        rows.append(_row("Win %", cur_rec["win_pct"], None, pct=True))
    for label, col in COMPARISON_METRICS:
        cur_val = cur[col].mean()
        base_val = base[col].mean() if base is not None else None
        rows.append(_row(label, cur_val, base_val))
    cur_label = f"{season}"
    base_label = f"{baseline}" if baseline is not None else "no baseline"
    df = pd.DataFrame(rows)
    df.columns = ["Metric", cur_label, base_label, "Change"]
    return df


def _row(label, cur, base, pct=False):
    cur_s = "-" if cur is None or pd.isna(cur) else f"{cur:.1f}"
    if base is None or pd.isna(base):
        return [label, cur_s, "-", "-"]
    base_s = f"{base:.1f}"
    if base == 0:
        change = "-"
    else:
        delta = (cur - base) / abs(base) * 100
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        change = f"{arrow} {delta:+.1f}%"
    return [label, cur_s, base_s, change]


def differential(tdf, freo_col, opp_col):
    """Win rate in games where Freo won vs lost the count on a stat."""
    ahead = tdf[tdf[freo_col] > tdf[opp_col]]
    behind = tdf[tdf[freo_col] < tdf[opp_col]]
    def rate(g):
        return (g["result"] == "W").mean() * 100 if len(g) else None
    return {
        "ahead_games": len(ahead), "ahead_winrate": rate(ahead),
        "behind_games": len(behind), "behind_winrate": rate(behind),
    }


# Roles for the role-leaders page: label -> (column, whether higher is the leader).
ROLES = [
    ("Ball Winner", "contested_poss"),
    ("Tackler", "tackles"),
    ("Clearances", "clearances"),
    ("Rebounder", "rebound_50s"),
    ("Spoiler", "one_percenters"),
    ("Forward Threat", "forward_threat"),
]


def role_leaders_table(pdf_season):
    """One row per game with the leading player and value for each role."""
    rows = []
    for (rnd, opp), grp in pdf_season.groupby(["round", "opponent"], sort=False):
        row = {"Round": rnd, "Opponent": opp}
        for label, col in ROLES:
            idx = grp[col].idxmax()
            top = grp.loc[idx]
            val = int(top[col])
            row[label] = f"{top['player']} ({val})" if val > 0 else "-"
        rows.append(row)
    # Keep chronological order using the season frame's existing order.
    order = pdf_season.drop_duplicates(["round", "opponent"])[["round", "opponent"]]
    order = list(zip(order["round"], order["opponent"]))
    rows.sort(key=lambda r: order.index((r["Round"], r["Opponent"])))
    return pd.DataFrame(rows)


def role_leader_counts(pdf_season, role_col):
    """How many games each player led a given role in the season."""
    counts = {}
    for _, grp in pdf_season.groupby(["round", "opponent"], sort=False):
        idx = grp[role_col].idxmax()
        top = grp.loc[idx]
        if top[role_col] > 0:
            counts[top["player"]] = counts.get(top["player"], 0) + 1
    s = pd.Series(counts).sort_values(ascending=False)
    return s


def season_role_leaders(pdf_season):
    """The player who led each role in the most games this season."""
    out = []
    for label, col in ROLES:
        counts = role_leader_counts(pdf_season, col)
        if len(counts):
            out.append((label, counts.index[0], int(counts.iloc[0])))
        else:
            out.append((label, "-", 0))
    return out


# ---- Season Overview helpers ----------------------------------------------
def top_goalkickers(player_df, season, n=6):
    """Leading goalkickers for the season (total goals), highest first."""
    pdf = players_season(player_df, season)
    g = pdf.groupby("player")["goals"].sum()
    g = g[g > 0].sort_values(ascending=False).head(n)
    return g


def possession_mix(team_df, season):
    """Contested vs uncontested possession totals and the contested share, plus
    how often Freo won the contested-possession count."""
    tdf = team_season(team_df, season)
    contested = int(tdf["freo_contested_poss"].sum())
    uncontested = int(tdf["freo_uncontested_poss"].sum())
    total = contested + uncontested
    pct = contested / total * 100 if total else 0.0
    d = differential(tdf, "freo_contested_poss", "opp_contested_poss")
    return {
        "contested": contested, "uncontested": uncontested, "total": total,
        "contested_pct": pct, "won_games": d["ahead_games"], "games": len(tdf),
    }


# Metrics offered on the Season Trends card: label -> (freo col, opp col).
TREND_METRICS = [
    ("Inside 50s", "freo_inside_50s", "opp_inside_50s"),
    ("Score", "freo_score", "opp_score"),
    ("Disposals", "freo_disposals", "opp_disposals"),
    ("Clearances", "freo_clearances", "opp_clearances"),
    ("Contested poss", "freo_contested_poss", "opp_contested_poss"),
    ("Marks", "freo_marks", "opp_marks"),
]
