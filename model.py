"""Match model and simulator, from public data (a forecast, not a record).

What it does
  1. Form: for every club before every game, a rolling average (exponentially
     weighted, half-life HALF_LIFE games, carried across seasons) of each metric
     for and against, from league_team_games.csv. Only games before the one
     being predicted are used, so nothing leaks from the result.
  2. Model: ridge regressions (numpy, standardised inputs) from both clubs'
     form and who is at home to each side's scoring shots and goal accuracy.
  3. Simulator: a game played score by score. Each side's scoring shots in each
     quarter are drawn around the model's expectation (with the extra spread
     real games show, fitted from the training residuals), split across the
     quarters by the club's own quarter pattern (from league_score_events.csv),
     timed within each quarter, and each shot is a goal with the side's
     predicted accuracy. Run it thousands of times for win chances, margins and
     how often each side kicks a run of 3+ goals unanswered.

What it can't know: anything timed except scores (whole-game stats only, see
CLAUDE.md), injuries, selection, weather or tactics. Scores in the simulator
don't make the next score more likely (momentum carry): the test in
data.momentum_test finds no sign of it in Freo's games, and `evaluate` checks
whether real games run in streaks more than simulated ones.
"""

import numpy as np
import pandas as pd

import data as D

HALF_LIFE = 8          # games: a game 8 games ago counts half as much as the last one
MIN_PRIOR = 5          # games of history a club needs before its form is trusted
METRICS = ["scoring_shots", "accuracy", "score_for", "inside50s", "contested_possessions",
           "uncontested_possessions", "centre_clearances", "stoppage_clearances", "metres_gained",
           "pressure_acts", "tackles", "intercepts", "turnovers", "marks_inside50", "rebound50s",
           "hitouts", "score_launches", "clangers"]
LAMBDAS = [1, 3, 10, 30, 100, 300, 1000, 3000]


# ---- form and design ------------------------------------------------------------
def form(lg):
    """Each club's form going into each game: one row per (match_id, team) with
    f_<metric> (its own average) and a_<metric> (what its opponents averaged
    against it), plus n_prior (games of history)."""
    lg = lg.sort_values("game_dt")
    out = []
    for team, g in lg.groupby("team", sort=False):
        g = g.sort_values("game_dt")
        cols = {}
        for m in METRICS:
            own = g[m].astype(float)
            opp = g[f"opp_{m}"].astype(float) if f"opp_{m}" in g else None
            cols[f"f_{m}"] = own.shift(1).ewm(halflife=HALF_LIFE).mean()
            if opp is not None:
                cols[f"a_{m}"] = opp.shift(1).ewm(halflife=HALF_LIFE).mean()
        df = pd.DataFrame(cols, index=g.index)
        df["n_prior"] = np.arange(len(g))
        df["match_id"], df["team"] = g["match_id"].values, g["team"].values
        out.append(df)
    return pd.concat(out).set_index(["match_id", "team"])


def _league_with_extras(lg):
    lg = lg.copy()
    if "opp_accuracy" not in lg:
        opp = lg[["match_id", "team", "accuracy", "score_for"]].rename(
            columns={"team": "opponent", "accuracy": "opp_accuracy", "score_for": "opp_score_for"})
        lg = lg.merge(opp, on=["match_id", "opponent"], how="left")
    return lg


def design(lg, fm):
    """The model's inputs for every team-game: the club's form, its opponent's
    form and whether the club is at home. Rows where either club has fewer than
    MIN_PRIOR games of history are dropped."""
    mine = fm.loc[list(zip(lg["match_id"], lg["team"]))].reset_index(drop=True)
    theirs = fm.loc[list(zip(lg["match_id"], lg["opponent"]))].reset_index(drop=True)
    X = pd.concat([mine.drop(columns=["n_prior"]).add_prefix("us_"),
                   theirs.drop(columns=["n_prior"]).add_prefix("them_")], axis=1)
    X["home"] = lg["is_home"].astype(float).values
    ok = (mine["n_prior"].values >= MIN_PRIOR) & (theirs["n_prior"].values >= MIN_PRIOR)
    ok &= X.notna().all(axis=1).values
    return X, ok


# ---- ridge ------------------------------------------------------------------
class Ridge:
    """Ridge regression on standardised inputs (closed form)."""

    def __init__(self, lam):
        self.lam = lam

    def fit(self, X, y):
        X = np.asarray(X, float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1
        Z = (X - self.mu) / self.sd
        self.b0 = float(np.mean(y))
        A = Z.T @ Z + self.lam * np.eye(Z.shape[1])
        self.b = np.linalg.solve(A, Z.T @ (np.asarray(y, float) - self.b0))
        return self

    def predict(self, X):
        return self.b0 + ((np.asarray(X, float) - self.mu) / self.sd) @ self.b


class MatchModel:
    """Scoring shots and accuracy for one side, from both clubs' form."""

    def fit(self, X, shots, acc, tune_X=None, tune_shots=None, tune_acc=None):
        self.cols = list(X.columns)
        self.lam_shots = self.lam_acc = LAMBDAS[2]
        if tune_X is not None:      # pick the penalty on a later season (never the test season)
            self.lam_shots = min(LAMBDAS, key=lambda l: np.mean(
                (Ridge(l).fit(X, shots).predict(tune_X) - tune_shots) ** 2))
            self.lam_acc = min(LAMBDAS, key=lambda l: np.mean(
                (Ridge(l).fit(X, acc).predict(tune_X) - tune_acc) ** 2))
            X = pd.concat([X, tune_X])
            shots = np.concatenate([shots, tune_shots])
            acc = np.concatenate([acc, tune_acc])
        self.shots = Ridge(self.lam_shots).fit(X, shots)
        self.acc = Ridge(self.lam_acc).fit(X, acc)
        resid = shots - self.shots.predict(X)
        lam = np.clip(self.shots.predict(X), 5, None)
        # Spread beyond Poisson: shots ~ Poisson(lambda * G), G ~ Gamma(k, 1/k).
        extra = max(np.var(resid) - np.mean(lam), 1e-6)
        self.k = float(np.mean(lam) ** 2 / extra)
        # Accuracy varies game to game beyond the goal-or-behind luck of each shot
        # (which the simulator already draws): keep only that extra, as a fraction.
        p = np.clip(self.acc.predict(X) / 100, 0.3, 0.75)
        luck = np.mean(p * (1 - p) / np.asarray(shots, float))
        self.acc_sd = float(np.sqrt(max(np.var((acc / 100) - p) - luck, 0.0)))
        return self

    spread = 1.0       # predictions are stretched by this about the mean (fitted on a later season)

    def predict(self, X):
        X = X[self.cols]
        lam = self.shots.b0 + self.spread * (self.shots.predict(X) - self.shots.b0)
        acc = self.acc.b0 + self.spread * (self.acc.predict(X) - self.acc.b0)
        return np.clip(lam, 8, None), np.clip(acc / 100, 0.3, 0.75)

    def top_inputs(self, n=8):
        """The inputs that move expected scoring shots most (standardised
        coefficients), for explaining the model."""
        s = pd.Series(self.shots.b, index=self.cols)
        return s.reindex(s.abs().sort_values(ascending=False).index).head(n)


# ---- quarter pattern and the simulator --------------------------------------------
def quarter_shares(events=None):
    """Each club's share of its scoring shots in each quarter, all seasons,
    shrunk halfway to the league's: {club: [q1..q4]}, plus "league"."""
    ev = D.load_league_events() if events is None else events
    if ev is None:
        return {"league": np.array([.25, .25, .25, .25])}
    counts = ev.groupby(["team", "quarter"]).size().unstack(fill_value=0).reindex(columns=range(1, 5),
                                                                                    fill_value=0)
    league = counts.sum() / counts.values.sum()
    out = {"league": league.values}
    for team, row in counts.iterrows():
        own = row / row.sum()
        out[team] = (0.5 * own + 0.5 * league).values
    return out


def quarter_lengths(events=None):
    ev = D.load_league_events() if events is None else events
    if ev is None:
        return np.full(4, 30.5)
    return ev.drop_duplicates(["season", "date", "home", "quarter"]).groupby("quarter")[
        "quarter_secs"].mean().reindex(range(1, 5)).values / 60


def simulate(lam, acc, k, shares, qlen, n=10000, seed=0, acc_sd=0.0, kq=None):
    """n games between side 0 and side 1 (totals only: the order of scores
    doesn't change who wins). lam, acc: (2,) expected scoring shots and accuracy;
    shares: (2, 4) each side's quarter split (None: even); kq: quarter swings
    (each side's rate in each quarter varies by a Gamma(kq) factor; None: none).
    Returns points, goals and shots (n, 2) and the accuracy used (n, 2)."""
    rng = np.random.default_rng(seed)
    lam, acc = np.asarray(lam, float), np.asarray(acc, float)
    sh = np.full((2, 4), 0.25) if shares is None else np.asarray(shares, float)
    g = rng.gamma(k, 1 / k, size=(n, 2, 1))
    gq = rng.gamma(kq, 1 / kq, size=(n, 2, 4)) if kq else 1.0
    p = np.clip(acc + rng.normal(0, acc_sd, size=(n, 2)), 0.25, 0.8)
    shots = rng.poisson(lam[None, :, None] * sh[None] * g * gq).sum(axis=2)
    goals = rng.binomial(shots, p)
    points = goals * 6 + (shots - goals)
    return points, goals, shots, p


def one_game(lam, acc, k, shares, qlen, seed, kq=None, stick=0.0):
    """One simulated game, score by score, as an events table with the same
    columns as data.game_events (team "Freo" = side 0, "Opp" = side 1). Each
    quarter's scoring shots are drawn per side (with quarter swings, kq), then
    put in order with `stick`: the next score is that much more likely (as a
    weight) to go to whoever scored last, the measured momentum carry."""
    rng = np.random.default_rng(seed)
    shares = np.asarray(shares, float)
    rows = []
    g = rng.gamma(k, 1 / k, size=2)
    for q in range(4):
        gq = rng.gamma(kq, 1 / kq, size=2) if kq else np.ones(2)
        left = [int(rng.poisson(lam[s] * g[s] * gq[s] * shares[s][q])) for s in (0, 1)]
        times = np.sort(rng.uniform(0, qlen[q], sum(left)))
        last = None
        for t in times:
            w = [left[s] * (1 + stick if s == last else 1) for s in (0, 1)]
            side = int(rng.random() * (w[0] + w[1]) >= w[0])
            left[side] -= 1
            last = side
            rows.append((q + 1, t, side, rng.random() < acc[side]))
    f = o = 0
    out = []
    for i, (q, t, side, goal) in enumerate(rows, 1):
        pts = 6 if goal else 1
        f, o = (f + pts, o) if side == 0 else (f, o + pts)
        out.append({"event": i, "quarter": q, "quarter_secs": int(qlen[q - 1] * 60), "secs": int(t * 60),
                    "team": "Freo" if side == 0 else "Opp", "kind": "goal" if goal else "behind",
                    "player": "", "freo_score": f, "opp_score": o})
    e = pd.DataFrame(out)
    if not len(e):
        return None
    return D._with_clock(e)


# ---- fitting and evaluation ---------------------------------------------------------
def training_frame(lg=None):
    lg = _league_with_extras(D.load_league() if lg is None else lg)
    fm = form(lg)
    X, ok = design(lg, fm)
    return lg, X, ok


KQ_GRID = [None, 30, 15, 8, 5]
STICK_GRID = [0.0, 0.1, 0.2, 0.35]


def fit(seasons_train, season_tune=None, lg=None, shape=True):
    """Fit on seasons_train; on season_tune (never the test season) choose the
    penalties, the spread and the game-shape settings, then refit on both."""
    lg, X, ok = training_frame(lg)
    tr = ok & lg["season"].isin(seasons_train).values
    m = MatchModel().fit(X[tr], lg.loc[tr, "scoring_shots"].values, lg.loc[tr, "accuracy"].values)
    m.kq, m.stick = None, 0.0
    if season_tune is None:
        return m, lg, X, ok
    tu = ok & (lg["season"] == season_tune).values
    home = tu & lg["is_home"].astype(bool).values
    pred = _pred_margin(m, lg, X, home)
    actual = lg.loc[home, "margin"].values.astype(float)
    spread = float(np.sum(actual * pred) / np.sum(pred * pred))   # least squares through 0
    full = MatchModel().fit(X[tr], lg.loc[tr, "scoring_shots"].values, lg.loc[tr, "accuracy"].values,
                            tune_X=X[tu], tune_shots=lg.loc[tu, "scoring_shots"].values,
                            tune_acc=lg.loc[tu, "accuracy"].values)
    full.spread = max(1.0, spread)
    full.kq, full.stick = (_fit_shape(m, lg, X, home) if shape else (None, 0.0))
    return full, lg, X, ok


def _pred_margin(m, lg, X, home_rows):
    """Predicted margin (home minus away) for the home rows."""
    away = _away_rows(lg, home_rows)
    lh, ah = m.predict(X[home_rows])
    la, aa = m.predict(X.iloc[away])
    return lh * (1 + 5 * ah) - la * (1 + 5 * aa)


def _away_rows(lg, home_rows):
    games = lg[home_rows]
    key = dict(zip(zip(lg["match_id"], lg["team"]), range(len(lg))))
    return [key[(mid, opp)] for mid, opp in zip(games["match_id"], games["opponent"])]


def _fit_shape(m, lg, X, home_rows, sims=8):
    """Quarter swings and stickiness that make simulated games as streaky as the
    real ones in the tuning season (runs of 3+ goals, longest run, lead changes)."""
    games = lg[home_rows]
    away = _away_rows(lg, home_rows)
    lh, ah = m.predict(X[home_rows])
    la, aa = m.predict(X.iloc[away])
    ev = D.load_league_events()
    season = int(games["season"].iloc[0])
    shares = quarter_shares(ev[ev["season"] < season] if (ev["season"] < season).any() else ev)
    qlen = quarter_lengths()
    real = []
    for g in games.itertuples():
        e = D.club_game_events(g._asdict())
        if e is not None:
            real.append(_runs(e[0]))
    target = np.array(real, float).mean(0)
    best, best_err = (None, 0.0), np.inf
    for kq in KQ_GRID:
        for stick in STICK_GRID:
            out = []
            for i, g in enumerate(games.itertuples()):
                qs = [shares.get(g.team, shares["league"]), shares.get(g.opponent, shares["league"])]
                for s in range(sims):
                    e = one_game([lh[i], la[i]], [ah[i], aa[i]], m.k, qs, qlen, seed=7919 * i + s,
                                 kq=kq, stick=stick)
                    if e is not None:
                        out.append(_runs(e[0]))
            err = float(np.sum(((np.array(out, float).mean(0) - target) / target) ** 2))
            if err < best_err:
                best, best_err = (kq, stick), err
    return best


def matchup(model, lg, X, club, opp, home, shares, n=10000, seed=0):
    """Forecast club v opp today (from each club's latest form): expected shots
    and accuracy for both, and the simulated outcomes."""
    # Form after their latest game: roll the average forward one more game.
    after = {}
    for t in (club, opp):
        g = lg[lg["team"] == t].sort_values("game_dt")
        row = {}
        for m in METRICS:
            row[f"f_{m}"] = g[m].astype(float).ewm(halflife=HALF_LIFE).mean().iloc[-1]
            if f"opp_{m}" in g:
                row[f"a_{m}"] = g[f"opp_{m}"].astype(float).ewm(halflife=HALF_LIFE).mean().iloc[-1]
        after[t] = pd.Series(row)
    rows = []
    for a, b, h in ((club, opp, home), (opp, club, -home if home else 0)):
        x = pd.concat([after[a].add_prefix("us_"), after[b].add_prefix("them_")])
        x["home"] = 1.0 if h == 1 else 0.0
        rows.append(x)
    Xm = pd.DataFrame(rows)[model.cols]
    lam, acc = model.predict(Xm)
    qs = [shares.get(club, shares["league"]), shares.get(opp, shares["league"])]
    points, goals, shots, p = simulate(lam, acc, model.k, qs, quarter_lengths(), n=n, seed=seed,
                                       acc_sd=model.acc_sd, kq=model.kq)
    margin = points[:, 0] - points[:, 1]
    return {"lam": lam, "acc": acc, "shares": qs, "margin": margin, "points": points,
            "win": float((margin > 0).mean()), "draw": float((margin == 0).mean()),
            "p10": float(np.percentile(margin, 10)), "p50": float(np.median(margin)),
            "p90": float(np.percentile(margin, 90))}


def evaluate(train=(2024,), tune=2025, test=2026, n=4000):
    """Fit on `train` (+ `tune` for the penalty, then refit with it), predict every
    `test` game from the home side, before it happened. Returns a dict of results
    against two baselines, and the momentum-shape check."""
    model, lg, X, ok = fit(list(train), tune)
    te = ok & (lg["season"] == test).values & lg["is_home"].astype(bool).values
    games = lg[te]
    Xh = X[te]
    away_rows = []
    for mid, team in zip(games["match_id"], games["opponent"]):
        away_rows.append(np.where((lg["match_id"] == mid).values & (lg["team"] == team).values)[0][0])
    Xa = X.iloc[away_rows]
    lam_h, acc_h = model.predict(Xh)
    lam_a, acc_a = model.predict(Xa)
    exp_h = lam_h * (1 + 5 * acc_h)
    exp_a = lam_a * (1 + 5 * acc_a)
    pred = exp_h - exp_a
    actual = games["margin"].values.astype(float)
    shares = quarter_shares(D.load_league_events().query("season < @test"))
    qlen = quarter_lengths()
    wins = []
    for i in range(len(games)):
        pts, *_ = simulate([lam_h[i], lam_a[i]], [acc_h[i], acc_a[i]], model.k, None, qlen, n=n,
                           seed=i, acc_sd=model.acc_sd, kq=model.kq)
        m = pts[:, 0] - pts[:, 1]
        wins.append((m > 0).mean() + 0.5 * (m == 0).mean())
    wins = np.array(wins)
    won = np.where(actual > 0, 1.0, np.where(actual < 0, 0.0, 0.5))
    trn = lg[ok & lg["season"].isin(list(train) + [tune]).values & lg["is_home"].astype(bool).values]
    home_adv = float(trn["margin"].mean())
    home_rate = float((trn["margin"] > 0).mean() + 0.5 * (trn["margin"] == 0).mean())
    fh = X.loc[te]
    fa = Xa
    form_pred = ((fh["us_f_score_for"].values - fh["us_a_score_for"].values)
                 - (fa["us_f_score_for"].values - fa["us_a_score_for"].values)) / 2 + home_adv
    sd = float(np.std(trn["margin"]))
    from math import erf, sqrt
    form_win = np.array([0.5 * (1 + erf(v / (sd * sqrt(2)))) for v in form_pred])

    def brier(p):
        return float(np.mean((p - won) ** 2))

    def tips(p):
        return float(np.mean(((p > 0.5) & (won == 1)) | ((p < 0.5) & (won == 0)) | (won == 0.5)))

    res = {
        "games": int(len(games)), "lam_shots": model.lam_shots, "lam_acc": model.lam_acc, "k": model.k,
        "spread": model.spread, "kq": model.kq, "stick": model.stick,
        "model": {"mae": float(np.mean(np.abs(pred - actual))), "tips": tips(wins), "brier": brier(wins)},
        "form": {"mae": float(np.mean(np.abs(form_pred - actual))), "tips": tips(form_win),
                 "brier": brier(form_win)},
        "home": {"mae": float(np.mean(np.abs(home_adv - actual))), "tips": tips(np.full(len(won), home_rate)),
                 "brier": brier(np.full(len(won), home_rate))},
        "top_inputs": model.top_inputs(),
        "calibration": _calibration(wins, won),
    }
    res["shape"] = _shape_check(games, lam_h, lam_a, acc_h, acc_a, model, shares, qlen)
    return res


def _calibration(p, won, bins=(0, .3, .45, .55, .7, 1.01)):
    out = []
    for lo, hi in zip(bins, bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.any():
            out.append({"forecast": f"{lo:.0%}-{min(hi, 1):.0%}", "games": int(m.sum()),
                        "said": float(p[m].mean()), "won": float(won[m].mean())})
    return out


def _runs(e):
    block = (e["team"] != e["team"].shift()).cumsum()
    r = e.assign(g=(e["kind"] == "goal").astype(int)).groupby(block).agg(team=("team", "first"),
                                                                          goals=("g", "sum"))
    sign = np.sign(e["margin"])
    sign = sign[sign != 0]
    return (int((r["goals"] >= 3).sum()), int(r["goals"].max()),
            int((sign != sign.shift()).sum() - 1) if len(sign) else 0)


def _shape_check(games, lam_h, lam_a, acc_h, acc_a, model, shares, qlen, sims=40):
    """Real 2026 games against simulated ones for the same matchups: runs of 3+
    goals a game, the longest goal run, lead changes."""
    real, sim = [], []
    for i, g in enumerate(games.itertuples()):
        ev = D.club_game_events(g._asdict())
        if ev is None:
            continue
        real.append(_runs(ev[0]))
        qs = [shares.get(g.team, shares["league"]), shares.get(g.opponent, shares["league"])]
        for s in range(sims):
            e = one_game([lam_h[i], lam_a[i]], [acc_h[i], acc_a[i]], model.k, qs, qlen, seed=1000 * i + s,
                         kq=model.kq, stick=model.stick)
            if e is not None:
                sim.append(_runs(e[0]))
    real, sim = np.array(real), np.array(sim)
    names = ["runs of 3+ goals a game", "longest goal run", "lead changes"]
    return {n: {"real": float(real[:, j].mean()), "simulated": float(sim[:, j].mean())}
            for j, n in enumerate(names)}


# ---- saved settings and the app's forecast -----------------------------------------
EVAL_JSON = "model_eval.json"


def save_eval(path=EVAL_JSON):
    """Run `evaluate` and save its results and the tuned settings (python model.py)."""
    import json
    from datetime import date
    r = evaluate()
    out = {k: v for k, v in r.items() if k != "top_inputs"}
    out["top_inputs"] = {k: round(float(v), 3) for k, v in r["top_inputs"].items()}
    out["evaluated"] = date.today().isoformat()
    out["train"], out["tune"], out["test"] = [2024], 2025, 2026
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=float)
    return out


def load_eval(path=EVAL_JSON):
    import json
    import os
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def app_model():
    """The model the app forecasts with: fitted on every season, with the
    penalties, spread and game-shape settings tuned in model_eval.json."""
    ev = load_eval()
    lg, X, ok = training_frame()
    m = MatchModel()
    m.cols = list(X.columns)
    lam_s = ev["lam_shots"] if ev else LAMBDAS[4]
    lam_a = ev["lam_acc"] if ev else LAMBDAS[4]
    shots, acc = lg.loc[ok, "scoring_shots"].values, lg.loc[ok, "accuracy"].values
    m.lam_shots, m.lam_acc = lam_s, lam_a
    m.shots, m.acc = Ridge(lam_s).fit(X[ok], shots), Ridge(lam_a).fit(X[ok], acc)
    pred = np.clip(m.shots.predict(X[ok]), 5, None)
    m.k = float(np.mean(pred) ** 2 / max(np.var(shots - pred) - np.mean(pred), 1e-6))
    p = np.clip(m.acc.predict(X[ok]) / 100, 0.3, 0.75)
    m.acc_sd = float(np.sqrt(max(np.var(acc / 100 - p) - np.mean(p * (1 - p) / shots), 0.0)))
    m.spread = ev["spread"] if ev else 1.0
    m.kq = ev["kq"] if ev else None
    m.stick = ev["stick"] if ev else 0.0
    return m, lg, X


def forecast(m, lg, X, club, opp, venue, runs_sims=400):
    """club v opp: venue 1 = club at home, -1 = away, 0 = neutral. Adds each
    side's chance of kicking at least one run of 3+ goals unanswered."""
    shares = quarter_shares()
    out = matchup(m, lg, X, club, opp, venue, shares)
    qlen = quarter_lengths()
    runs = np.zeros(2)
    for s in range(runs_sims):
        e = one_game(out["lam"], out["acc"], m.k, out["shares"], qlen, seed=s, kq=m.kq, stick=m.stick)
        if e is None:
            continue
        blocks = (e[0]["team"] != e[0]["team"].shift()).cumsum()
        r = e[0].assign(g=(e[0]["kind"] == "goal").astype(int)).groupby(blocks).agg(
            team=("team", "first"), goals=("g", "sum"))
        for i, side in enumerate(("Freo", "Opp")):
            runs[i] += bool(((r["team"] == side) & (r["goals"] >= 3)).any())
    out["run_chance"] = runs / runs_sims
    out["qlen"] = qlen
    return out


FORECASTS_JSON = "model_forecasts.json"
HIST_EDGES = np.arange(-120, 126, 6)     # the margin distribution's bins (points, Freo minus them)


def save_forecasts(path=FORECASTS_JSON, club="Fremantle"):
    """Every club v Freo at home, away and at a neutral ground, worked out ahead
    so the app opens them instantly: the summary, the margin distribution as
    binned counts, and what's needed to draw an example game."""
    import json
    from datetime import date
    m, lg, X = app_model()
    out = {"made": date.today().isoformat(), "club": club, "k": m.k, "kq": m.kq, "stick": m.stick,
           "edges": HIST_EDGES.tolist(), "forecasts": {}}
    for opp in sorted(t for t in lg["team"].unique() if t != club):
        for venue in (1, -1, 0):
            f = forecast(m, lg, X, club, opp, venue)
            counts, _ = np.histogram(np.clip(f["margin"], HIST_EDGES[0], HIST_EDGES[-1] - 0.01),
                                     bins=HIST_EDGES)
            out["forecasts"][f"{opp}|{venue}"] = {
                "lam": f["lam"].tolist(), "acc": f["acc"].tolist(),
                "shares": [list(map(float, q)) for q in f["shares"]], "qlen": list(map(float, f["qlen"])),
                "win": f["win"], "draw": f["draw"], "p10": f["p10"], "p50": f["p50"], "p90": f["p90"],
                "run_chance": f["run_chance"].tolist(), "counts": counts.tolist(), "n": int(len(f["margin"]))}
    with open(path, "w") as fh:
        json.dump(out, fh)
    return out


def load_forecasts(path=FORECASTS_JSON):
    import json
    import os
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


if __name__ == "__main__":
    import sys
    if "forecasts" not in sys.argv[1:]:       # python model.py forecasts: skip the 3 min test
        r = save_eval()
        print(f"Saved {EVAL_JSON}: model tips {r['model']['tips']:.1%}, margin error "
              f"{r['model']['mae']:.1f}, Brier {r['model']['brier']:.3f} on {r['games']} {r['test']} games")
    f = save_forecasts()
    print(f"Saved {FORECASTS_JSON}: {len(f['forecasts'])} forecasts")
