"""SIMULATED data for the Ground switch (Match, Player, Scout): GPS running and
positions on the ground. None of it is real. It exists to show what the Coach View could do with
a club's tracking data, and is kept apart from the real data: it never writes
to the CSVs, Wharf-ai's tools never see it, and every card that shows it says
"simulated".

What is real and what is made up:
  - Counts come from the real box score: a player's goals, marks (and marks
    inside 50), contested and uncontested possessions in a game are his real
    numbers. Only WHERE they happened is simulated, from his listed position
    (freo_squad.csv): midfielders around the centre and corridor, forwards
    inside 50, defenders in the back half, rucks at the stoppages.
  - Running (distance, high-speed metres, sprints, top speed, quarter splits) is
    simulated from his real time on ground and work rate that game (pressure
    acts, metres gained), so a big-effort game shows big running.
  - Everything is seeded from season, round and player, so the same game always
    looks the same.

The ground: x along the length (-82 m at Freo's defensive goal, +82 m at the
goal they attack; Freo always kick to the right), y across (-66 m to +66 m).
"""

import math
import zlib

import numpy as np
import pandas as pd

import data as D

HALF_L, HALF_W = 82.0, 66.0          # half the oval's length and width (metres)
GOAL_X = HALF_L

# Where each role spends time: (x, y, sd_x, sd_y, weight) mixture components.
ZONES = {
    "mid": [(0, 0, 24, 22, .5), (22, 0, 28, 28, .3), (-22, 0, 28, 28, .2)],
    "mid_fwd": [(26, 0, 26, 25, .6), (0, 0, 24, 24, .4)],
    "fwd": [(52, 0, 20, 28, .65), (24, 0, 24, 30, .35)],
    "key_fwd": [(60, 0, 14, 16, .8), (34, 0, 18, 20, .2)],
    "def": [(-46, 0, 22, 30, .65), (-16, 0, 24, 30, .35)],
    "key_def": [(-60, 0, 14, 16, .8), (-34, 0, 18, 20, .2)],
    "ruck": [(0, 0, 16, 14, .55), (30, 0, 20, 24, .25), (-30, 0, 20, 24, .2)],
}
ROLE_OF = {"MIDFIELDER": "mid", "MIDFIELDER_FORWARD": "mid_fwd", "MEDIUM_FORWARD": "fwd",
           "KEY_FORWARD": "key_fwd", "MEDIUM_DEFENDER": "def", "KEY_DEFENDER": "key_def",
           "RUCK": "ruck"}
# Full-game distance (km) and the share of it at high speed (>20 km/h), by role.
RUN = {"mid": (14.0, .12), "mid_fwd": (13.2, .12), "fwd": (12.2, .11), "key_fwd": (11.0, .09),
       "def": (12.6, .10), "key_def": (11.2, .08), "ruck": (11.6, .07)}
TOP_SPEED = {"mid": 31.5, "mid_fwd": 32.0, "fwd": 32.5, "key_fwd": 31.0, "def": 32.0,
             "key_def": 30.5, "ruck": 29.5}
LAYERS = ["Goals", "Marks", "Contested", "Uncontested"]


def _rng(*parts):
    return np.random.default_rng(zlib.crc32("|".join(map(str, parts)).encode()))


def roles(player_df):
    """{player: role}, from the latest listed position, or from his stats."""
    squad = D.load_squad()
    out = {}
    if squad is not None and "hitouts" in player_df.columns:   # Freo's listed positions
        latest = squad.sort_values("season").drop_duplicates("player", keep="last")
        out = {r.player: ROLE_OF.get(str(r.position), "mid") for r in latest.itertuples()
               if r.player in set(player_df["player"])}
    cols = [c for c in ("goals", "hitouts", "rebound_50s") if c in player_df.columns]
    avgs = player_df.groupby("player")[cols].mean().reindex(columns=["goals", "hitouts", "rebound_50s"],
                                                              fill_value=0)
    for p, a in avgs.iterrows():
        if p not in out:
            out[p] = ("ruck" if a["hitouts"] >= 8 else "fwd" if a["goals"] >= 1
                      else "def" if a["rebound_50s"] >= 2 else "mid")
    return out


def _inside_oval(x, y):
    return (x / HALF_L) ** 2 + (y / HALF_W) ** 2 <= 1


def _mixture(rng, zones, n, lateral=0.0, spread=1.0):
    comps = rng.choice(len(zones), size=n, p=[z[4] for z in zones])
    pts = []
    for c in comps:
        x0, y0, sx, sy, _ = zones[c]
        for _ in range(20):                       # resample until inside the oval
            x, y = rng.normal(x0, sx * spread), rng.normal(y0 + lateral, sy * spread)
            if _inside_oval(x, y):
                break
        pts.append((x, y))
    return np.array(pts).reshape(-1, 2)


def _lateral(player):
    """A player's favourite side of the ground (some wings, some corridor)."""
    return float(_rng("lateral", player).normal(0, 12))


def positions(player, season, rnd, role, n=140):
    """Simulated places a player was on the ground in one game (samples)."""
    return _mixture(_rng("pos", season, rnd, player), ZONES[role], n, _lateral(player))


def _goal_spots(rng, n):
    pts = []
    for _ in range(int(n)):
        d = float(np.clip(rng.gamma(4.0, 6.5), 4, 52))           # most inside 40 m
        ang = math.radians(float(rng.normal(0, 26 if d < 25 else 18)))
        pts.append((GOAL_X - d * math.cos(ang), d * math.sin(ang)))
    return np.array(pts).reshape(-1, 2)


def events(row, role):
    """Real counts from one player-game row, at simulated spots on the ground:
    {layer: array of (x, y)}."""
    rng = _rng("ev", row["season"], row["round"], row["player"])
    zones = ZONES[role]
    lat = _lateral(row["player"])
    n = lambda c: int(row.get(c, 0) or 0)   # noqa: E731
    mi50 = min(n("marks_inside_50"), n("marks"))
    f50 = [(GOAL_X - 28, 0, 10, 16, 1.0)]
    stoppage = [(z[0] * .6, z[1], z[2] * .55, z[3] * .55, z[4]) for z in zones]
    return {
        "Goals": _goal_spots(rng, n("goals")),
        "Marks": np.vstack([_mixture(rng, f50, mi50),
                            _mixture(rng, zones, n("marks") - mi50, lat)]),
        "Contested": _mixture(rng, stoppage, n("contested_poss"), lat * .5),
        "Uncontested": _mixture(rng, zones, n("uncontested_poss"), lat * 1.3, spread=1.15),
    }


def running(pdf):
    """Simulated GPS running for every player-game in pdf: distance (km), high-speed
    metres (>20 km/h), sprints (>25 km/h), top speed (km/h) and distance in each
    quarter, from time on ground and work rate that game."""
    role = roles(pdf)
    tog = "time_on_ground_pct" if "time_on_ground_pct" in pdf.columns else "pct_played"
    work_cols = [c for c in ("pressure_acts", "metres_gained", "disposals") if c in pdf.columns]
    z = pdf[work_cols].sub(pdf.groupby("player")[work_cols].transform("mean"))
    z = z.div(pdf.groupby("player")[work_cols].transform("std").replace(0, 1)).fillna(0)
    work = z.mean(axis=1)
    rows = []
    for (i, r), w in zip(pdf.iterrows(), work):
        ro = role.get(r["player"], "mid")
        rng = _rng("run", r["season"], r["round"], r["player"])
        me = _rng("player", r["player"])
        base, hsr_share = RUN[ro]
        share = float(np.clip((r.get(tog) or 80) / 85, .25, 1.2))
        dist = base * float(me.normal(1, .05)) * share * float(rng.normal(1, .04)) * (1 + .03 * w)
        hsr = dist * 1000 * hsr_share * float(np.clip(1 + .18 * w + rng.normal(0, .07), .5, 1.6))
        fade = .012 + (.008 if r.get("result") == "L" else 0)
        q = np.array([.25 + 1.5 * fade, .25 + .5 * fade, .25 - .5 * fade, .25 - 1.5 * fade])
        q = q * rng.normal(1, .03, 4)
        q = q / q.sum() * dist
        rows.append({"season": r["season"], "round": r["round"], "opponent": r["opponent"],
                     "result": r.get("result"), "game_dt": r.get("game_dt"), "player": r["player"],
                     "role": ro, "distance_km": round(dist, 2), "hsr_m": int(hsr),
                     "sprints": int(max(0, hsr / 48 + rng.normal(0, 3))),
                     "top_speed": round(TOP_SPEED[ro] + float(me.normal(0, .9))
                                        + float(rng.normal(0, .5)), 1),
                     **{f"q{k + 1}_km": round(v, 2) for k, v in enumerate(q)}})
    return pd.DataFrame(rows)


def opp_rows(opp):
    """The opposition's players in their games against Freo (opp_player_games_ext.csv),
    with the columns events() and roles() read (their counts are real, Champion
    Data's). Their positions aren't listed anywhere, so roles() works them out
    from their stats."""
    o = D.load_opp_players()
    if o is None:
        return pd.DataFrame()
    o = o[o["opponent"] == opp].rename(columns={
        "uncontested_possessions": "uncontested_poss", "marks_inside50": "marks_inside_50",
        "api_round": "round"})
    return o.assign(round=o["round"].astype(str) + " " + o["date_local"].astype(str))
