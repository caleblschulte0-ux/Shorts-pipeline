"""Control-flow tests for the bounded self-repair loop.

The loop drives real renders, but its DECISION logic — pick the weakest thing,
choose a whitelisted remedy, keep the better cut, stop when it should — must be
trustworthy without spending render minutes. A fake render_fn stands in for the
pipeline so the whole loop runs in milliseconds.

Runs with pytest OR standalone: `python3 data_learning/tests/test_repair_loop.py`.
"""
from __future__ import annotations

import importlib.util
import json
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
    assert r["env"] == {"scene_repair": True}    # structural, not an env nudge


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

    repairs = []
    out = rl.repair("x", max_iters=2, render_fn=fake,
                    scene_repair_fn=lambda s, v: repairs.append(s))
    assert len(out["attempts"]) == 3             # baseline + 2 repairs, bounded
    assert len(repairs) == 2                     # each repair was scene-addressed
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

    repairs = []
    out = rl.repair("x", max_iters=2, render_fn=fake,
                    scene_repair_fn=lambda s, v: repairs.append(s))
    assert out["shipped"] is True
    assert out["best"]["score"] == 74
    assert len(out["attempts"]) == 2             # stopped as soon as it shipped
    # the repair pass was a SCENE repair (structural), not an env nudge
    assert len(repairs) == 1
    assert out["attempts"][1]["env"] == {}


def test_hierarchy_no_hard_failures_beats_score():
    # a lower-scoring cut with NO hard failures beats a higher-scoring one WITH
    a = _v("block", 60)
    a["auto_fails"] = []
    b = _v("block", 70)
    b["auto_fails"] = ["decorative_mascot: x"]
    assert rl.better(a, b) is a


def test_hierarchy_temporal_tiebreakers():
    a = _v("block", 60); b = _v("block", 60)
    a["auto_fails"] = b["auto_fails"] = []
    a["dimensions"] = {"hook": 2, "craft": 1}
    b["dimensions"] = {"hook": 2, "craft": 2}      # higher lowest dimension
    assert rl.better(a, b) is b
    b["dimensions"] = dict(a["dimensions"])
    a["temporal"] = {"effective_fps": 20.0, "duplicate_ratio": 0.2}
    b["temporal"] = {"effective_fps": 24.0, "duplicate_ratio": 0.2}
    assert rl.better(a, b) is b                    # higher fps wins the tie
    b["temporal"] = {"effective_fps": 20.0, "duplicate_ratio": 0.1}
    assert rl.better(a, b) is b                    # lower dup ratio wins


def _fake_repo(tmp, slug):
    import os as _o
    for d in ("state/scene_plans", "output/scenes"):
        _o.makedirs(tmp / d, exist_ok=True)
    return tmp


def _render_writing(tmp, slug, tag, score, plan):
    """A fake render: writes canonical video/verdict + the active scene plan,
    like the real pipeline would, then returns the verdict."""
    def fn(s, env):
        (tmp / "output").mkdir(parents=True, exist_ok=True)
        (tmp / "output" / f"story_{slug}.mp4").write_text(tag)
        # weak mascot dim so pick_remedy has a whitelisted target each iter
        v = _v("block", score, dims={"hook": 4, "data_demo": 5, "mascot": 1,
                                     "craft": 3, "pace": 2, "payoff": 2,
                                     "temporal_craft": 3})
        v["auto_fails"] = []
        (tmp / "output" / f"story_{slug}.showrunner.json").write_text(
            json.dumps(v))
        if plan is not None:
            pp = tmp / "state" / "scene_plans" / f"{slug}.json"
            pp.parent.mkdir(parents=True, exist_ok=True)
            pp.write_text(json.dumps(plan))
        return v
    return fn


def test_rollback_worse_attempt_restores_incumbent():
    """Attempt 0 scores 68, attempt 1 (after a plan change) scores 54: the
    canonical plan, video and verdict must all be attempt 0's afterwards."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = _fake_repo(Path(td), "s")
        seq = iter([("base", 68, None), ("worse", 54, {"1": {"viz": "stack"}})])

        def render(slug, env):
            tag, score, plan = next(seq)
            return _render_writing(tmp, "s", tag, score, plan)(slug, env)

        out = rl.repair("s", max_iters=1, render_fn=render,
                        scene_repair_fn=lambda s, v: None,
                        run_root=tmp / "runs", repo=tmp)
        assert out["best"]["score"] == 68
        assert out["promoted"].endswith("attempt_0")
        # canonical video/verdict restored to attempt 0
        assert (tmp / "output" / "story_s.mp4").read_text() == "base"
        vj = json.loads((tmp / "output" / "story_s.showrunner.json").read_text())
        assert vj["score"] == 68
        # the losing plan is NOT active (attempt 0 had none)
        assert not (tmp / "state" / "scene_plans" / "s.json").exists()
        # the failed candidate remains available for diagnosis
        assert (tmp / "runs" / "attempt_1" / "video.mp4").read_text() == "worse"


def test_promotion_better_attempt_becomes_canonical():
    """Attempt 0 scores 68, attempt 1 scores 76: attempt 1 (and its plan) must
    become the canonical state."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = _fake_repo(Path(td), "s")
        seq = iter([("base", 68, None), ("fixed", 76, {"1": {"viz": "stack"}})])

        def render(slug, env):
            tag, score, plan = next(seq)
            return _render_writing(tmp, "s", tag, score, plan)(slug, env)

        out = rl.repair("s", max_iters=1, render_fn=render,
                        scene_repair_fn=lambda s, v: None,
                        run_root=tmp / "runs", repo=tmp)
        assert out["best"]["score"] == 76
        assert out["promoted"].endswith("attempt_1")
        assert (tmp / "output" / "story_s.mp4").read_text() == "fixed"
        plan = json.loads((tmp / "state" / "scene_plans" / "s.json").read_text())
        assert plan == {"1": {"viz": "stack"}}    # winner's plan is ACTIVE


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
