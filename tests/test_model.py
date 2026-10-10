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


def test_saved_forecasts_cover_every_club_and_match_a_live_run(fitted):
    saved = M.load_forecasts()
    if saved is None:
        pytest.skip("run python model.py forecasts")
    clubs = sorted(t for t in D.load_league()["team"].unique() if t != "Fremantle")
    assert set(saved["forecasts"]) == {f"{c}|{v}" for c in clubs for v in (1, -1, 0)}
    m, lg, X = fitted
    live = M.forecast(m, lg, X, "Fremantle", "Sydney", 1, runs_sims=10)
    f = saved["forecasts"]["Sydney|1"]
    assert f["win"] == pytest.approx(live["win"]) and f["p50"] == pytest.approx(live["p50"])
    assert sum(f["counts"]) == f["n"]


def test_margin_paths_end_on_the_final_margin_and_bands_hold_their_share():
    out = M.simulate([25, 22], [0.53, 0.5], 50, [[.2, .25, .25, .3]] * 2, None, n=4000, kq=15, unc=0.1,
                     paths=True)
    pts, goals, shots, _, path = out
    assert (pts == goals * 6 + (shots - goals)).all()
    assert (path[:, -1] == pts[:, 0] - pts[:, 1]).all()
    assert path.shape == (4000, 4 * M.PATH_BINS)
    s = M.path_summary(path, path[:, -1])
    bands = np.array(s["bands"])
    assert (bands[0] == 0).all() and (np.diff(bands, axis=1) >= 0).all()     # 10th <= 25th <= ... <= 90th
    inside = ((path[:, -1] >= bands[-1, 0]) & (path[:, -1] <= bands[-1, 4])).mean()
    assert 0.78 <= inside <= 0.85
    assert 0.5 < s["q3_leader_wins"] < 1


def test_uncertainty_is_chosen_on_the_tuning_season():
    ev = M.load_eval()
    if ev is None or "unc" not in ev:
        pytest.skip("model_eval.json not made")
    briers = {float(u): b for u, b in ev["unc_brier"].items()}
    assert set(briers) == set(M.UNC_GRID)
    assert ev["unc"] == min(briers, key=lambda u: (round(briers[u], 4), u))


def test_what_if_with_no_change_is_the_forecast_and_levers_match_a_live_run(fitted):
    saved = M.load_forecasts()
    if saved is None or "levers" not in saved:
        pytest.skip("model_forecasts.json not made")
    f = saved["forecasts"]["Adelaide|1"]
    same = M.what_if(f, saved, {})
    assert same["counts"] == f["counts"] and same["win"] == f["win"]
    m, lg, X = fitted
    shares = M.quarter_shares()
    base = M.matchup(m, lg, X, "Fremantle", "Adelaide", 1, shares, n=200)
    moved = M.matchup(m, lg, X, "Fremantle", "Adelaide", 1, shares, n=200, shifts={"centre_clearances": 3})
    e = saved["levers"]["centre_clearances"]
    assert moved["lam"] - base["lam"] == pytest.approx(3 * np.array(e["dlam"]), abs=1e-6)
    assert moved["acc"] - base["acc"] == pytest.approx(3 * np.array(e["dacc"]), abs=1e-6)
    up = M.what_if(f, saved, {"centre_clearances": 3})
    assert up["win"] > f["win"]
