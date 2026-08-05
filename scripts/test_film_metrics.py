#!/usr/bin/env python3
"""The shot-plan scorer must catch the regression that cost twelve hours.

On 2026-08-01/02 five full renders of one story were judged, 2.5-4.5 hours
each. Two of the five changes made the film measurably worse and there was no
way to know until the video existed and a blind judge had looked at it:

    attempt  figure shots  overall  personality
    1        14            4.0      2
    3        14            3.5      2
    4         0            3.5      2     <- the library ban removed every human
    5         0            3.0      1     <- judge adds NO_CHARACTER

Column two is a property of the SHOT PLAN. It needs no media, no ffmpeg, no
judge and no network. These tests prove the scorer would have refused that
change in milliseconds, which is the entire justification for the module.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import film_metrics as fm  # noqa: E402

# The real attempt-1 shape: figures present, some real media, some cards.
A1 = ([{"kind": "scene_free", "seconds": 4.0}] * 14
      + [{"kind": "depict", "seconds": 5.0, "motion_query": "child running",
          "line": "a child running in the sun"}] * 15
      + [{"kind": "image", "seconds": 4.0}] * 12)
# The attempt-4 shape: every figure replaced by stock.
A4 = ([{"kind": "depict", "seconds": 5.0, "motion_query": f"thing {i}",
        "line": f"a line about thing {i}"} for i in range(29)]
      + [{"kind": "image", "seconds": 4.0}] * 8)


def test_the_regression_is_visible_without_a_render():
    before, after = fm.score_plan(A1), fm.score_plan(A4)
    assert before["figure_shots"] == 14, before
    assert after["figure_shots"] == 0, after
    cmp = fm.compare(before, after)
    assert cmp["verdict"] == "REGRESSION", cmp
    assert any("figure_shots" in x for x in cmp["regressed"]), cmp
    print(f"ok  the character loss shows up as {cmp['verdict']}: {cmp['regressed']}")


def test_the_guard_refuses_it_outright():
    """Some changes are never worth making whatever else improves."""
    bad = fm.guard(fm.score_plan(A1), fm.score_plan(A4))
    assert bad and "ZERO" in bad[0], bad
    # and it does not fire on a change that keeps people on screen
    ok = fm.guard(fm.score_plan(A1), fm.score_plan(A1[:20]))
    assert ok == [], ok
    print(f"ok  guard refuses the figure-wipe: {bad[0]}")


def test_compare_reports_regressions_not_only_wins():
    """Reporting only the wins is how the figure-wipe shipped as a fix."""
    before = fm.score_plan(A1)
    # a change that removes duplicates AND every figure: one win, one loss
    after = fm.score_plan(A4)
    cmp = fm.compare(before, after)
    assert cmp["regressed"], cmp
    assert cmp["verdict"] == "REGRESSION", (
        "any regression must dominate, or a mixed change reads as progress")
    print("ok  a mixed change reads as REGRESSION, not 'improvement'")


def test_duplicate_media_is_counted():
    """36 slots / 32 clips was real, and a judge named the pairs by timestamp."""
    dupes = [{"kind": "depict", "seconds": 4.0, "motion_query": "reeds in wind"},
             {"kind": "depict", "seconds": 4.0, "motion_query": "reeds in wind"},
             {"kind": "depict", "seconds": 4.0, "motion_query": "ocean waves"}]
    m = fm.score_plan(dupes)
    assert m["duplicate_media"] == 1, m
    assert m["distinct_media"] == 2, m
    print("ok  a repeated media query is counted before it is ever fetched")


def test_unanchored_media_is_counted():
    """A query sharing no word with its line would serve any other beat."""
    m = fm.score_plan([
        {"kind": "depict", "seconds": 4, "motion_query": "glacier ice melting",
         "line": "The glacier is melting fast."},
        {"kind": "depict", "seconds": 4, "motion_query": "two people talking",
         "line": "The glacier is melting fast."},
    ])
    assert m["anchorable_media"] == 2 and m["unanchored_media"] == 1, m
    print("ok  an unanchored query is counted against the plan")


def test_not_measured_is_None_never_zero():
    """A false zero on an unmeasured axis manufactures fake regressions.

    This module did exactly that on its own first real comparison: a plan
    rebuilt from performance.json carries no media queries, scored
    unanchored_media=0, and comparing a real plan against it reported
    "REGRESSION: unanchored 0 -> 8" for a change that improved the film.
    """
    blind = fm.score_plan([{"kind": "scene_free", "seconds": 4.0}])
    assert blind["duplicate_media"] is None, blind
    assert blind["unanchored_media"] is None, blind
    assert blind["unanchored_fraction"] is None, blind
    assert "n/a" in blind["summary"], blind["summary"]
    # ...and compare() then declines to judge that axis at all
    real = fm.score_plan([{"kind": "depict", "seconds": 4.0,
                           "motion_query": "x y", "line": "nothing alike"}])
    cmp = fm.compare(blind, real)
    assert not any("unanchored" in x for x in cmp["regressed"]), cmp
    print("ok  an unmeasured axis is None, and compare() skips it")


def test_an_empty_plan_does_not_explode():
    """Metrics must never be the thing that breaks a render."""
    m = fm.score_plan([])
    assert m["shots"] == 0 and m["figure_shots"] == 0, m
    assert isinstance(m["summary"], str), m
    assert fm.compare(m, m)["verdict"] == "no change"
    print("ok  an empty plan scores cleanly instead of raising")


def test_the_ledger_round_trips_and_trends():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "led.jsonl"
        # five weak renders, then five better ones
        for i in range(5):
            fm.record("s", fm.score_plan(A4), path=f,
                      verdict={"overall_10": 3.0, "personality": 1})
        for i in range(5):
            fm.record("s", fm.score_plan(A1), path=f,
                      verdict={"overall_10": 6.0, "personality": 3})
        rows = fm.history(f)
        assert len(rows) == 10, len(rows)
        t = fm.trend(rows, n=5)
        assert t["enough_data"] and t["direction"] == "better", t
        assert t["delta_overall"] == 3.0, t
        # ...and it says "worse" when it is worse, not just when it is better
        t2 = fm.trend(list(reversed(rows)), n=5)
        assert t2["direction"] == "worse", t2
    print("ok  the ledger records, reads back, and reports BOTH directions")


def test_trend_refuses_to_judge_too_little_data():
    """A retro that launders noise into a mandate is worse than none."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "led.jsonl"
        fm.record("s", fm.score_plan(A1), path=f,
                  verdict={"overall_10": 4.0, "personality": 2})
        assert fm.trend(fm.history(f), n=5)["enough_data"] is False
    print("ok  trend refuses to call a direction without two full windows")


if __name__ == "__main__":
    test_the_regression_is_visible_without_a_render()
    test_the_guard_refuses_it_outright()
    test_compare_reports_regressions_not_only_wins()
    test_duplicate_media_is_counted()
    test_unanchored_media_is_counted()
    test_not_measured_is_None_never_zero()
    test_an_empty_plan_does_not_explode()
    test_the_ledger_round_trips_and_trends()
    test_trend_refuses_to_judge_too_little_data()
    print("all film-metrics checks pass")
