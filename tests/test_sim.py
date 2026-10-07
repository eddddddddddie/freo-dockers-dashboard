"""The simulated demo data (sim.py): real counts, simulated places; the same
every time; never touching the real data or Wharf-ai."""

import numpy as np

import data as D
import sim


def test_events_use_the_real_counts_and_stay_on_the_ground():
    p = D.players_season(D.load_players(), 2026)
    role = sim.roles(p)
    for _, r in p.sample(40, random_state=1).iterrows():
        ev = sim.events(r, role[r["player"]])
        assert len(ev["Goals"]) == int(r["goals"])
        assert len(ev["Marks"]) == int(r["marks"])
        assert len(ev["Contested"]) == int(r["contested_poss"])
        assert len(ev["Uncontested"]) == int(r["uncontested_poss"])
        for xy in ev.values():
            if len(xy):
                assert ((xy[:, 0] / 82) ** 2 + (xy[:, 1] / 66) ** 2 <= 1.01).all()
        if len(ev["Goals"]):
            assert (ev["Goals"][:, 0] > 20).all()           # goals come from the forward half


def test_running_is_repeatable_plausible_and_leaves_the_real_data_alone():
    p = D.players_season(D.load_players(), 2026)
    before = p.copy()
    a, b = sim.running(p), sim.running(p)
    assert a.equals(b) and p.equals(before)
    assert len(a) == len(p)
    assert a["distance_km"].between(0.5, 18).all() and (a["hsr_m"] > 0).all()   # an early injury runs little
    q = a[["q1_km", "q2_km", "q3_km", "q4_km"]].sum(axis=1)
    assert np.allclose(q, a["distance_km"], atol=0.05)
    by_role = a.groupby("role")["distance_km"].mean()
    assert by_role["mid"] > by_role["ruck"]                  # mids run further than rucks


def test_wharf_ai_never_sees_the_simulation():
    import inspect
    import chatbot
    import wharf_tools
    for mod in (wharf_tools, chatbot):
        assert "sim" not in {n for n, _ in inspect.getmembers(mod, inspect.ismodule)}
