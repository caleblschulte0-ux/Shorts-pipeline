"""Control-flow tests for the bounded self-repair loop.

The loop drives real renders, but its DECISION logic — pick the weakest thing,
choose a whitelisted remedy, keep the better cut, stop when it should — must be
trustworthy without spending render minutes. A fake render_fn stands in for the
pipeline so the whole loop runs in milliseconds.

Runs with pytest OR standalone: `python3 data_learning/tests/test_repair_loop.py`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "repair_loop", _REPO / "scripts" / "repair_loop.py")
rl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rl)


def _v(verdict, score, dims=None, auto_fails=None):
    return {"verdict": verdict, "score": score,
            "dimensions": dims or {}, "auto_fails": auto_fails or []}


def test_weakest_dimension_picks_biggest_headroom():
    dims = {"hook": 4, "data_demo": 5, "mascot": 1, "craft": 3,
            "pace": 2, "payoff": 2, "temporal_craft": 3}
    assert rl.weakest_dimension(dims) == "mascot"   # 1/4 is the lowest fraction


def test_weakest_dimension_breaks_ties_by_weight():
    # temporal_craft(14) and pace(8) both at 0; the heavier one wins the fix.
    dims = {"hook": 4, "data_demo": 5, "mascot": 4, "craft": 3,
            "pace": 0, "payoff": 2, "temporal_craft": 0}
    assert rl.weakest_dimension(dims) == "temporal_craft"


def test_pick_remedy_prioritises_autofail():
    v = _v("block", 80, dims={"mascot": 1}, auto_fails=["dead_air: 4.6s frozen"])
    r = rl.pick_remedy(v, set())
    assert r["target"] == "dead_air"
    assert r["env"] == {"MASCOT_BRAIN": "1"}


def test_pick_remedy_falls_back_to_weakest_dim():
    v = _v("block", 60, dims={"hook": 4, "data_demo": 5, "mascot": 1,
                              "craft": 3, "pace": 2, "payoff": 2,
                              "temporal_craft": 3})
    r = rl.pick_remedy(v, set())
    assert r["target"] == "mascot"


def test_pick_remedy_exhausts():
    # weakest is a dimension with no whitelisted remedy -> None (loop stops).
    v = _v("block", 60, dims={"hook": 0, "data_demo": 5, "mascot": 4,
                              "craft": 3, "pace": 2, "payoff": 2,
                              "temporal_craft": 3})
    assert rl.pick_remedy(v, set()) is None


def test_better_prefers_ship_then_score():
    assert rl.better(_v("block", 99), _v("ship", 71))["verdict"] == "ship"
    assert rl.better(_v("block", 60), _v("block", 80))["score"] == 80
    assert rl.better(None, _v("block", 10))["score"] == 10


def test_loop_stops_immediately_on_ship():
    calls = []

    def fake(slug, env):
        calls.append(env)
        return _v("ship", 82)

    out = rl.repair("x", max_iters=2, render_fn=fake)
    assert out["shipped"] is True
    assert out["stopped"] == "shipped"
    assert len(calls) == 1                       # no wasted re-renders


def test_loop_keeps_best_and_is_bounded():
    strong = {"hook": 4, "data_demo": 5, "craft": 3, "pace": 2, "payoff": 2}
    # Two distinct remedy targets across the run (a dead-air auto-fail, then the
    # weakest dimension) so the loop can spend its full 2-repair budget.
    steps = iter([
        _v("block", 55, dims={**strong, "mascot": 3, "temporal_craft": 0},
           auto_fails=["dead_air: 4.6s frozen"]),
        _v("block", 68, dims={**strong, "mascot": 1, "temporal_craft": 3}),
        _v("block", 66, dims={**strong, "mascot": 1, "temporal_craft": 3}),
    ])

    def fake(slug, env):
        return next(steps)

    out = rl.repair("x", max_iters=2, render_fn=fake)
    assert len(out["attempts"]) == 3             # baseline + 2 repairs, bounded
    assert out["best"]["score"] == 68            # kept the best, not the last
    assert out["shipped"] is False
    assert out["stopped"] == "budget_exhausted"


def test_loop_recovers_to_ship_and_keeps_it():
    seq = iter([("block", 60), ("ship", 74)])

    def fake(slug, env):
        v, s = next(seq)
        return _v(v, s, dims={"mascot": 1, "hook": 4, "data_demo": 5,
                              "craft": 3, "pace": 2, "payoff": 2,
                              "temporal_craft": 3})

    out = rl.repair("x", max_iters=2, render_fn=fake)
    assert out["shipped"] is True
    assert out["best"]["score"] == 74
    assert len(out["attempts"]) == 2             # stopped as soon as it shipped
    # the repair render got the whitelisted mascot-brain nudge
    assert out["attempts"][1]["env"].get("MASCOT_BRAIN") == "1"


def _main() -> int:
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print("PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
