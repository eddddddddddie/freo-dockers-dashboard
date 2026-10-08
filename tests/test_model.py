"""The match model (model.py): no leakage from results into form, simulated
games that add up, sensible forecasts, and saved test results that beat the
simple baselines."""

import numpy as np
import pytest

import data as D
import model as M


@pytest.fixture(scope="module")
def fitted():
    if D.load_league() is None:
        pytest.skip("league file not scraped")
    return M.app_model()


def test_form_uses_only_earlier_games():
    lg = M._league_with_extras(D.load_league())
    fm = M.form(lg)
    g = lg[lg["team"] == "Sydney"].sort_values("game_dt")
    row = g.iloc[10]
    want = g["inside50s"].iloc[:10].astype(float).ewm(halflife=M.HALF_LIFE).mean().iloc[-1]
    assert fm.loc[(row["match_id"], "Sydney"), "f_inside50s"] == pytest.approx(want)
    assert fm.loc[(g.iloc[0]["match_id"], "Sydney"), "n_prior"] == 0


def test_simulated_scores_add_up():
    pts, goals, shots, _ = M.simulate([25, 22], [0.53, 0.5], 50, None, np.full(4, 30.0), n=2000, kq=15)
    assert (pts == goals * 6 + (shots - goals)).all() and (goals <= shots).all()
    assert abs(shots[:, 0].mean() - 25) < 1.5 and abs(shots[:, 1].mean() - 22) < 1.5
    e, quarters = M.one_game([25, 22], [0.53, 0.5], 50, [[.25] * 4] * 2, np.full(4, 30.0), seed=3,
                             kq=15, stick=0.1)
    step = e["freo_score"].diff().fillna(e["freo_score"]) + e["opp_score"].diff().fillna(e["opp_score"])
    assert set(step.astype(int)) <= {1, 6}
    assert (e.groupby("quarter")["secs"].diff().fillna(0) >= 0).all()
    again, _ = M.one_game([25, 22], [0.53, 0.5], 50, [[.25] * 4] * 2, np.full(4, 30.0), seed=3,
                          kq=15, stick=0.1)
    assert again.equals(e)


def test_home_ground_helps_and_chances_add_to_one(fitted):
    m, lg, X = fitted
    home = M.forecast(m, lg, X, "Fremantle", "Sydney", 1, runs_sims=50)
    away = M.forecast(m, lg, X, "Fremantle", "Sydney", -1, runs_sims=50)
    assert home["win"] > away["win"]
    for f in (home, away):
        assert 0 <= f["win"] <= 1 and 0 <= f["draw"] <= 1 and f["p10"] <= f["p50"] <= f["p90"]
        assert ((0 <= f["run_chance"]) & (f["run_chance"] <= 1)).all()


def test_saved_evaluation_beats_the_simple_baselines():
    ev = M.load_eval()
    if ev is None:
        pytest.skip("run python model.py")
    assert ev["games"] > 150
    assert ev["model"]["brier"] < ev["home"]["brier"] and ev["model"]["mae"] < ev["home"]["mae"]
    assert ev["model"]["brier"] <= ev["form"]["brier"] + 0.01
