#!/usr/bin/env python3
"""A quarantine in hand beats a timeout.

`_repair_attempts` bounds the repair loop by a COUNT, and its docstring already
names the failure that count exists to prevent: "a CI job that exceeds its wall
clock delivers nothing at all". But a count cannot honour a clock it was never
given. Two attempts of an unknown-length film is a guess, and on 2026-08-01 the
guess was wrong in the dangerous direction — shared-air's first round took 145
minutes of a 335-minute job, so the loop opened a second full render with the
round-1 mp4, package and verdict all sitting on a disk that dies with the
runner. A third would have started with ~40 minutes left.

Being killed mid-encode is strictly worse than stopping: a quarantine still
ships an inspectable package and a judgeable video, a timeout ships nothing.

So the budget is measured in SECONDS, against the last round's real duration —
the next render is the same film with a few beats changed, so it costs about the
same. These tests pin the decision, including that an unset budget stays
unbounded (local runs have no job cap and must not inherit a CI one).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import produce  # noqa: E402


def _with_budget(v):
    if v is None:
        os.environ.pop("CURIOSITY_WALLCLOCK_S", None)
    else:
        os.environ["CURIOSITY_WALLCLOCK_S"] = str(v)


def test_no_budget_means_unbounded():
    """A local run has no job cap and must not inherit CI's."""
    _with_budget(None)
    assert produce._wallclock_budget_s() is None
    assert produce._time_for_another_round(time.monotonic() - 10_000, 9_000, "x")
    # garbage or nonsense never silently caps a render
    for bad in ("", "   ", "abc", "0", "-5"):
        _with_budget(bad)
        assert produce._wallclock_budget_s() is None, bad
    print("ok  an unset or invalid budget leaves the loop unbounded")


def test_a_round_that_fits_is_allowed():
    _with_budget(18000)                      # 5h
    started = time.monotonic() - 3600        # 1h spent
    assert produce._time_for_another_round(started, 3600, "x")   # 1h more: fits
    print("ok  a round that fits the remaining clock still runs")


def test_a_round_that_cannot_finish_is_refused():
    """The real shared-air numbers: 145 min spent of a 300 min budget."""
    _with_budget(18000)
    started = time.monotonic() - 145 * 60
    # a second 145-min round leaves ~10 min — the 1.15x allowance refuses it
    assert not produce._time_for_another_round(started, 145 * 60, "shared-air")
    print("ok  a render the clock cannot finish is refused, package kept")


def test_the_allowance_is_not_a_coin_flip():
    """1.15x, not 1.0x — a repair adds work, and the artifact is already won."""
    _with_budget(1000)
    started = time.monotonic() - 500        # 500s left
    assert produce._time_for_another_round(started, 400, "x")     # 460 <= 500
    assert not produce._time_for_another_round(started, 450, "x")  # 517 > 500
    print("ok  the next round is budgeted at 1.15x the last, not exactly 1x")


if __name__ == "__main__":
    try:
        test_no_budget_means_unbounded()
        test_a_round_that_fits_is_allowed()
        test_a_round_that_cannot_finish_is_refused()
        test_the_allowance_is_not_a_coin_flip()
        print("all wall-clock budget checks pass")
    finally:
        _with_budget(None)
