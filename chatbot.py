"""Grounded chat assistant.

Numbers are computed with pandas here and passed to Claude as context. The
model explains and compares those numbers but must not invent any that are not
present. Box-score data shows what happened, not zones or structures, so the
assistant is told to say when a question needs data we do not have.

Reads ANTHROPIC_API_KEY from the environment (never hard-coded).
"""

import os
import pandas as pd
import streamlit as st

import data as D

MODEL = os.environ.get("FREO_CHAT_MODEL", "claude-opus-4-8")

UNAVAILABLE = (
    "metres gained, pressure acts, score involvements, shot locations, "
    "expected score (xG), player positions or zones, and anything about team "
    "structure or set-ups"
)

SYSTEM_INTRO = f"""You are the analyst for a Fremantle Dockers (AFL) performance dashboard.
You answer tactical and statistical questions using ONLY the data provided below,
which was computed from the dashboard's two CSV files (afltables.com box scores for
the 2025 and 2026 seasons).

Rules:
- Every number you state must come from, or be directly computed from, the data below.
  Never estimate or invent a figure. If you compute something (a difference, a rate,
  an average), show the arithmetic briefly.
- If a question needs data we do not have, say so plainly. We do NOT have: {UNAVAILABLE}.
  Box-score data shows what happened, not why or where on the ground.
- Goal accuracy uses team totals (team behinds include rushed behinds; summed player
  behinds do not).
- Substitute markers are blank for all 2026 games (the source did not record them), so
  do not infer subs from low game time; ruckmen routinely play around 45 percent.
- Neither season has a Round 1, and round labels are the source's own (finals are
  EF, QF, SF, PF, GF).
- Be concise and concrete. Lead with the answer. Do not use em dashes.
"""


@st.cache_data
def build_context(_team_df_token, _player_df_token):
    """Build the grounded data context string once (cached). The token args
    keep the cache tied to the loaded data without hashing the frames here."""
    team = D.load_team()
    players = D.load_players()
    parts = ["=== DATA CONTEXT (all figures are computed from the CSVs) ==="]

    for season in D.seasons(team):
        tdf = D.team_season(team, season)
        rec = D.record(tdf)
        parts.append(f"\n## Season {season}")
        parts.append(
            f"Record: {rec['wins']}-{rec['losses']} "
            f"({rec['win_pct']:.0f}% win rate over {rec['games']} games). "
            f"Avg score for {rec['score_for']:.1f}, against {rec['score_against']:.1f}, "
            f"avg margin {rec['margin']:+.1f}."
        )
        # Differentials.
        for name, fcol, ocol in [
            ("clearances", "freo_clearances", "opp_clearances"),
            ("contested possessions", "freo_contested_poss", "opp_contested_poss"),
            ("inside 50s", "freo_inside_50s", "opp_inside_50s"),
        ]:
            d = D.differential(tdf, fcol, ocol)
            aw = f"{d['ahead_winrate']:.0f}%" if d["ahead_winrate"] is not None else "n/a"
            bw = f"{d['behind_winrate']:.0f}%" if d["behind_winrate"] is not None else "n/a"
            parts.append(
                f"When Freo win the {name} count: {aw} win rate "
                f"({d['ahead_games']} games). When they lose it: {bw} "
                f"({d['behind_games']} games)."
            )
        # Per-game team table.
        cols = ["round", "opponent", "result", "margin", "freo_score", "opp_score",
                "freo_goals", "freo_behinds", "freo_disposals", "opp_disposals",
                "freo_clearances", "opp_clearances", "freo_contested_poss",
                "opp_contested_poss", "freo_inside_50s", "opp_inside_50s",
                "freo_marks", "freo_tackles", "freo_rebound_50s", "opp_rebound_50s",
                "freo_one_percenters", "freo_goal_assists"]
        parts.append("Per-game team totals (CSV):")
        parts.append(tdf[cols].to_csv(index=False).strip())
        # Player season averages.
        pdf = D.players_season(players, season)
        stat_cols = ["kicks", "marks", "handballs", "disposals", "goals", "behinds",
                     "tackles", "clearances", "contested_poss", "inside_50s",
                     "rebound_50s", "one_percenters", "goal_assists", "hitouts"]
        agg = pdf.groupby("player").agg(
            games=("round", "count"),
            **{c: (c, "mean") for c in stat_cols}
        ).round(1).sort_values("disposals", ascending=False)
        parts.append("Player per-game averages this season (CSV):")
        parts.append(agg.reset_index().to_csv(index=False).strip())

    return "\n".join(parts)


def get_client():
    """Return an Anthropic client, or None if the key or SDK is unavailable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic()


def stream_answer(client, data_context, current_season, history):
    """Yield text chunks. The big data block is cached; the small viewing-season
    note sits after it so the cached prefix stays stable across seasons."""
    system = [
        {"type": "text", "text": SYSTEM_INTRO + "\n" + data_context,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text",
         "text": f"The user is currently viewing the {current_season} season."},
    ]
    with client.messages.stream(
        model=MODEL,
        max_tokens=6000,
        thinking={"type": "adaptive"},
        system=system,
        messages=history,
    ) as stream:
        for text in stream.text_stream:
            yield text
