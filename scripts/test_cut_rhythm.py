#!/usr/bin/env python3
"""The cut must have a rhythm, and the rhythm must not break the beat.

THE DEFECT. `planner.MAX_UNCHANGED` is a ceiling — a law about how long a
visual may hold. It was ALSO used as the literal length of every lead shot
(`emit(..., seconds=maxu)` at eight sites), which turned it into a constant.
The shared-air plan: 39 shots, FOUR distinct lengths, `4.50 / 1.85` repeating
end to end. Four consecutive blind taste verdicts said SAMENESS and BORING;
four consecutive responses changed what was ON screen and never looked at the
cut. The score went 4.0 -> 4.0 -> 3.5 -> 3.0.

THE TRAP, WHICH I FELL INTO. The first version of the fix enforced MIN_SHOT
(2.8s) on both halves of a split. Distinct lengths went 4 -> 8 and the range
collapsed from 1.85-4.5s to 2.80-3.55s: eight values all a third of a second
apart. That is a WORSE edit that scores better on "count the distinct
lengths", which is why `length_span_s` is measured alongside and why the test
below asserts both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import cut_rhythm as cr  # noqa: E402
from shared import film_metrics as fm  # noqa: E402
from data_learning import planner  # noqa: E402


def test_the_lead_shot_stops_being_a_constant():
    """The whole defect in one assertion."""
    holds = {cr.hold_for(i, 6.35, 4.5) for i in range(6)}
    assert len(holds) >= 4, holds
    assert max(holds) <= 4.5, holds
    print(f"ok  six consecutive beats cut at {len(holds)} different points")


def test_the_ceiling_is_still_a_law():
    """A rhythm may not buy variety by holding a picture longer than allowed.

    Stated as "never worse than the constant it replaces", which is the
    guarantee that is actually true. A very long beat (13.2s against a 4.5s
    ceiling) ALREADY produced an over-ceiling tail before this change — the
    lead took 4.5 and one development shot took the remaining 8.7. That is a
    real defect and it is not this module's; the correct invariant here is
    that varying the cut never lengthens either half beyond what the constant
    ceiling would have produced.
    """
    for i in range(12):
        for secs in (5.0, 6.35, 7.0, 9.0, 13.2):
            h = cr.hold_for(i, secs, 4.5)
            assert h <= 4.5 + 1e-9, (i, secs, h)
            assert secs - h <= max(4.5, secs - 4.5) + 1e-9, (
                f"tail {secs - h:.2f}s is LONGER than the {secs - 4.5:.2f}s "
                "the constant ceiling would have left", i, secs)
    print("ok  no half is ever longer than the constant would have made it")


def test_a_beat_that_cannot_vary_is_left_alone():
    """Adopting this must not be able to make a film worse than it was."""
    assert cr.hold_for(3, 4.0, 4.5) == 4.5      # no split happens at all
    assert cr.hold_for(3, 4.0, 3.0) == 3.0      # window empty: old behaviour
    assert cr.hold_for(3, "x", 4.5) == 4.5      # junk in, ceiling out
    print("ok  no legal room -> the old value, unchanged")


def test_it_also_kills_the_one_frame_RUNT():
    """A found bug, not a designed feature — recorded because it is a win.

    A 4.6s beat against a 4.5s ceiling used to emit a 4.5s lead and a 0.10s
    tail: a single-frame flash of a second image, charged to the render as a
    shot. The tail floor removes the whole class — the beat cuts 2.9 + 1.7
    instead. Nothing was looking for this; it fell out of giving the tail a
    minimum length at all.
    """
    h = cr.hold_for(3, 4.6, 4.5)
    assert 4.6 - h >= cr.FAST_CUT - 1e-9, (h, 4.6 - h)
    assert h < 4.5, h
    print(f"ok  a 4.6s beat cuts {h} + {round(4.6 - h, 2)}, not 4.5 + 0.10")


def test_the_beat_total_never_moves():
    """Narration rides these shots. A prettier cut is not worth a desync."""
    for i in range(8):
        for secs in (6.35, 9.0, 11.4, 13.2):
            ph = cr.phase_lengths(secs, 4.5, index=i)
            assert abs(sum(ph) - secs) < 0.01, (i, secs, ph, sum(ph))
            assert all(p >= cr.FAST_CUT - 1e-9 for p in ph), (i, secs, ph)
            assert all(p <= 4.5 + 1e-9 for p in ph), (i, secs, ph)
    print("ok  phases sum to the beat, and every phase is a usable shot")


def test_the_phase_COUNT_is_unchanged():
    """The skew moves where cuts land. It must not add or remove a cut.

    The phase count is what governs render cost and how much media a beat
    needs; changing it as a side effect of a rhythm change would make every
    before/after comparison in the ledger meaningless.
    """
    for secs in (6.35, 9.0, 11.4, 13.2, 4.0, 4.5):
        old = 1 if secs <= 4.5 else max(2, int(-(-secs // 4.5)))
        while old > 2 and secs / old < 2.8:
            old -= 1
        for i in range(6):
            assert len(cr.phase_lengths(secs, 4.5, index=i)) == old, (secs, i)
    print("ok  same number of shots as the equal split it replaces")


def test_phases_are_not_all_the_same_length():
    ph = cr.phase_lengths(8.0, 4.5, index=0)
    assert len(set(round(p, 2) for p in ph)) > 1, ph
    # ...but a beat sitting exactly at 2x the ceiling has nowhere to go: the
    # equal split IS the only legal split, and it stays equal rather than
    # borrowing room it does not have.
    assert cr.phase_lengths(9.0, 4.5, index=0) == [4.5, 4.5]
    print(f"ok  a split beat is no longer two identical halves: {ph}")


def test_variety_WITHOUT_range_is_not_an_improvement():
    """The trap, pinned. This is the version of the fix I shipped and undid.

    A cut with more distinct lengths, all clustered in the middle, must read as
    a REGRESSION — otherwise the metric rewards the squeeze.
    """
    was = fm.score_plan([{"kind": "depict", "seconds": s}
                         for s in (4.5, 1.85) * 8])
    squeezed = fm.score_plan([{"kind": "depict", "seconds": s} for s in
                              (2.8, 3.55, 2.88, 3.48, 3.15, 3.2, 2.8, 3.55,
                               2.88, 3.48, 3.15, 3.2, 2.8, 3.55, 2.88, 3.48)])
    assert squeezed["shot_lengths"] > was["shot_lengths"], (was, squeezed)
    assert squeezed["length_span_s"] < was["length_span_s"], (was, squeezed)
    cmp = fm.compare(was, squeezed)
    assert cmp["verdict"] == "REGRESSION", cmp
    assert any("length_span_s" in x for x in cmp["regressed"]), cmp
    print("ok  more lengths + less contrast reads as REGRESSION, not progress")


def test_the_real_story_actually_gets_a_rhythm():
    """Wiring, on the film four judges called BORING — not a fixture."""
    beats = json.loads(
        (REPO / "data_learning" / "pro_stories" / "shared-air.beats.json")
        .read_text())["beats"]
    shots = planner.plan_story(beats, [5.0] * len(beats))
    m = fm.score_plan(shots, beats)
    assert m["shot_lengths"] >= 12, (
        f"shared-air planned {m['shot_lengths']} distinct shot lengths across "
        f"{m['shots']} shots — it had 4, and four judges said SAMENESS")
    assert m["length_span_s"] >= 4.0, (
        f"span {m['length_span_s']}s — the fix must not buy variety by "
        "squeezing every shot toward the mean")
    assert 126.0 <= m["runtime_s"] <= 128.0, (
        f"runtime moved to {m['runtime_s']}s — the cut may not change the "
        "film's length; the narration is underneath it")
    print(f"ok  shared-air: {m['shot_lengths']} lengths over "
          f"{m['length_span_s']}s, runtime {m['runtime_s']}s")


def test_it_is_deterministic():
    """Same story, same cut — or no two renders are ever comparable."""
    a = [cr.hold_for(i, 6.35, 4.5) for i in range(20)]
    b = [cr.hold_for(i, 6.35, 4.5) for i in range(20)]
    assert a == b, "the rhythm must not be random"
    print("ok  the rhythm is a cycle, not a dice roll")


if __name__ == "__main__":
    test_the_lead_shot_stops_being_a_constant()
    test_the_ceiling_is_still_a_law()
    test_a_beat_that_cannot_vary_is_left_alone()
    test_it_also_kills_the_one_frame_RUNT()
    test_the_beat_total_never_moves()
    test_the_phase_COUNT_is_unchanged()
    test_phases_are_not_all_the_same_length()
    test_variety_WITHOUT_range_is_not_an_improvement()
    test_the_real_story_actually_gets_a_rhythm()
    test_it_is_deterministic()
    print("all cut-rhythm checks pass")
