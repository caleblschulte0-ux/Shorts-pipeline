"""Calibration fixtures for the showrunner SCORING harness (Pass 5).

The scoring instrument is only trustworthy if it SEPARATES quality: a weak
render must score materially below a mediocre one, which must score below a
strong one, and the ship/block line must fall in the gap. These are pinned as
CI band checks so a future re-weighting that quietly collapses the separation
(everything drifting to a safe ~72) fails loudly instead of shipping slop.

Runs with pytest OR standalone: `python3 data_learning/tests/test_showrunner_scoring.py`
(pytest is not installed in every environment; the __main__ block mirrors the
asserts so the check still runs in a bare CI step).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "showrunner_review", _REPO / "scripts" / "showrunner_review.py")
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


# ---- Calibration fixtures: three renders at distinct quality tiers ----------
# Grades are on each dimension's anchored ceiling (see WEIGHTS). These stand in
# for what the model would return on a genuinely weak / mediocre / strong video.
WEAK = {"hook": 1, "data_demo": 1, "mascot": 1, "craft": 1,
        "pace": 0, "payoff": 0, "temporal_craft": 0}
BASELINE = {"hook": 3, "data_demo": 3, "mascot": 3, "craft": 2,
            "pace": 1, "payoff": 1, "temporal_craft": 2}
STRONG = {"hook": 4, "data_demo": 5, "mascot": 4, "craft": 3,
          "pace": 2, "payoff": 2, "temporal_craft": 3}

# Expected score BANDS (inclusive). Wide enough to survive small rubric tweaks,
# tight enough that a collapse of separation trips them.
BANDS = {"weak": (0, 35), "baseline": (55, 75), "strong": (90, 100)}


def test_weights_sum_to_100():
    assert sum(w for w, _ceil in sr.WEIGHTS.values()) == 100


def test_score_bands():
    assert BANDS["weak"][0] <= sr.compute_score(WEAK) <= BANDS["weak"][1]
    assert BANDS["baseline"][0] <= sr.compute_score(BASELINE) <= BANDS["baseline"][1]
    assert BANDS["strong"][0] <= sr.compute_score(STRONG) <= BANDS["strong"][1]


def test_meaningful_separation():
    """Each tier clears the next by a real margin — no compression to ~72."""
    weak, base, strong = (sr.compute_score(WEAK), sr.compute_score(BASELINE),
                          sr.compute_score(STRONG))
    assert weak < base < strong
    assert base - weak >= 20
    assert strong - base >= 20


def test_ship_block_line_falls_in_the_gap():
    """The bar sits ABOVE a mediocre render and BELOW a strong one — so the
    threshold actually discriminates instead of passing everything."""
    assert sr.compute_score(BASELINE) < sr.MIN_SCORE <= sr.compute_score(STRONG)


def test_monotonic_in_every_dimension():
    """Raising any single dimension's grade never lowers the score."""
    for k, (_w, ceil) in sr.WEIGHTS.items():
        prev = -1
        for g in range(0, ceil + 1):
            dims = dict(BASELINE)
            dims[k] = g
            s = sr.compute_score(dims)
            assert s >= prev, f"{k}@{g} regressed the score"
            prev = s


def test_temporal_grade_thresholds():
    assert sr.temporal_grade({"effective_fps": 30}) == 3
    assert sr.temporal_grade({"effective_fps": 24}) == 3
    assert sr.temporal_grade({"effective_fps": 17}) == 2
    assert sr.temporal_grade({"effective_fps": 11}) == 1
    assert sr.temporal_grade({"effective_fps": 9.6}) == 0
    assert sr.temporal_grade({"effective_fps": None}) == 2   # unknown -> neutral


def test_temporal_craft_costs_real_points():
    """A choppy render (temporal 0) must score materially below the same render
    if it were buttery (temporal 3) — the whole point of the dimension."""
    choppy = dict(STRONG, temporal_craft=0)
    smooth = dict(STRONG, temporal_craft=3)
    assert sr.compute_score(smooth) - sr.compute_score(choppy) >= 12


def test_autofail_blocks_regardless_of_score():
    """A perfect score with ANY hard auto-fail present still BLOCKS."""
    perfect = sr.compute_score(STRONG)
    assert perfect >= sr.MIN_SCORE
    for check in sr.AUTOFAIL_CHECKS:
        checks = {check: {"present": True, "evidence": "fixture"}}
        assert sr.failed_autofails(checks) == [check]
        assert sr.decide_verdict(perfect, checks) == "block"


def test_clean_strong_render_ships():
    assert sr.decide_verdict(sr.compute_score(STRONG), {}) == "ship"


def test_dead_air_override_forces_block():
    """A >=4s frozen run injected by the motion measurement forces dead_air even
    if the model didn't report it."""
    checks = sr.apply_motion_override({}, {"longest_static_s": 4.67})
    assert checks["dead_air"]["present"] is True
    assert sr.decide_verdict(sr.compute_score(STRONG), checks) == "block"


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
    print(f"\nscores: weak={sr.compute_score(WEAK)} "
          f"baseline={sr.compute_score(BASELINE)} "
          f"strong={sr.compute_score(STRONG)}  bar={sr.MIN_SCORE}")
    print("PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
