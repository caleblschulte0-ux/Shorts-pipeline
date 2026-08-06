#!/usr/bin/env python3
"""The camera must be decided, not defaulted.

THE DEFECT. `footage_hybrid.image_beat` has accepted `direction` (in/out) and
`pan` (left/right/up/down) since it was written. The planner set NEITHER. So
every shot of every film pushed in, and all 14 image shots of the shared-air
plan carried the identical `push: 1.1` — a camera doing one thing for two
minutes. The blind taste judge said LOW_ENERGY twice and BORING four times.

Worse, two of those constants were assigned with `im["push"] = 1.10` and
`im["pan"] = pans[k % 5]`, which OVERWROTE an authored camera. A story that
specified its own move was silently ignored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import camera_grammar as cg  # noqa: E402
from shared import film_metrics as fm  # noqa: E402

def _score(shots, beats=None):
    """Fixture plans are written in one unit; `compare` requires saying which.
    See film_metrics.score_plan's duration_source note — an untagged pair is
    'incomparable', which is the correct answer for a real mismatch and a
    useless one for a test that controls both sides."""
    return fm.score_plan(shots, beats, duration_source="estimated")

from data_learning import planner  # noqa: E402


def test_the_move_carries_the_role():
    """Not an alternation — a reveal pulls out because that is what it means."""
    assert cg.move_for(0, "REVEAL")["direction"] == "out"
    assert cg.move_for(1, "REVEAL")["direction"] == "out"      # index cannot flip it
    assert cg.move_for(0, "CLOSE")["direction"] == "out"
    assert cg.move_for(1, "HOOK")["direction"] == "in"
    assert cg.move_for(0, "PAYOFF")["direction"] == "in"
    # a role with no inherent direction varies instead of sitting on one
    free = {cg.move_for(i, "DEVELOP")["direction"] for i in range(4)}
    assert free == {"in", "out"}, free
    print("ok  REVEAL/CLOSE pull out, HOOK/PAYOFF push in, DEVELOP varies")


def test_no_two_ADJACENT_shots_share_a_move():
    """The one real rule: two cuts drifting the same way read as one camera."""
    shots = [{"kind": "depict"} for _ in range(40)]
    moved = cg.plan_moves(shots, ["DEVELOP"] * 40)
    assert cg.repeated_moves(moved) == 0, cg.repeated_moves(moved)
    # ...and it holds even when the roles pin the direction for a long stretch
    moved = cg.plan_moves(shots, ["REVEAL"] * 40)
    assert cg.repeated_moves(moved) == 0, [
        (s["direction"], s["pan"]) for s in moved[:6]]
    print("ok  no adjacent pair shares a move, even under a fixed direction")


def test_an_AUTHORED_camera_wins():
    """The overwrite bug, pinned. An author outranks a cycle."""
    shots = [{"kind": "image", "direction": "out", "pan": "left", "push": 1.5},
             {"kind": "image"}]
    moved = cg.plan_moves(shots, ["DEVELOP", "DEVELOP"])
    assert moved[0]["direction"] == "out", moved[0]
    assert moved[0]["pan"] == "left", moved[0]
    assert moved[0]["push"] == 1.5, moved[0]
    print("ok  an authored direction/pan/push survives the grammar")


def test_a_still_still_moves_more_than_footage():
    """A preserved distinction, not an invented one.

    `image_beat` documents it: a frozen photo is the canonical slideshow tell,
    so a Ken Burns shot gets more movement than footage does. That was the
    1.14-vs-1.06 pair of defaults. The cycle must not quietly undo it.
    """
    for i in range(6):
        assert cg.move_for(i, "DEVELOP", still=True)["push"] >= 1.14, i
    print("ok  a still never gets less push than the 1.14 floor it had")


def test_the_input_is_not_mutated():
    shots = [{"kind": "depict"}]
    out = cg.plan_moves(shots)
    assert "direction" not in shots[0], shots[0]
    assert out[0]["direction"], out[0]
    print("ok  plan_moves returns a new list and leaves the input alone")


def test_an_empty_plan_does_not_explode():
    assert cg.plan_moves([]) == []
    assert cg.plan_moves(None) == []
    assert cg.repeated_moves([]) == 0
    print("ok  an empty plan is handled, not raised on")


def test_the_metric_reports_it_and_None_when_absent():
    """Unmeasured is None — the rule the whole module runs on."""
    blind = _score([{"kind": "depict", "seconds": 4.0}])
    assert blind["camera_moves"] is None and blind["repeated_moves"] is None, blind
    bad = _score([{"kind": "depict", "seconds": 4.0, "direction": "in",
                          "pan": "left"} for _ in range(5)])
    assert bad["camera_moves"] == 1 and bad["repeated_moves"] == 4, bad
    good = _score(cg.plan_moves(
        [{"kind": "depict", "seconds": 4.0} for _ in range(5)]))
    assert good["repeated_moves"] == 0, good
    assert fm.compare(bad, good)["verdict"] == "improvement", fm.compare(bad, good)
    print("ok  repeated_moves is measured, and absent means None not zero")


def test_the_real_story_gets_a_camera():
    """Wiring, on the film the judges called LOW_ENERGY."""
    beats = json.loads(
        (REPO / "data_learning" / "pro_stories" / "shared-air.beats.json")
        .read_text())["beats"]
    shots = planner.plan_story(beats, [5.0] * len(beats))
    m = _score(shots, beats)
    assert m["repeated_moves"] == 0, m
    assert m["camera_moves"] >= 4, m
    pushes = {round(float(s.get("push") or 0), 2) for s in shots}
    assert len(pushes) >= 4, (
        f"every shot still pushes the same amount: {sorted(pushes)}")
    print(f"ok  shared-air: {m['camera_moves']} moves, 0 repeats, "
          f"{len(pushes)} push values")


if __name__ == "__main__":
    test_the_move_carries_the_role()
    test_no_two_ADJACENT_shots_share_a_move()
    test_an_AUTHORED_camera_wins()
    test_a_still_still_moves_more_than_footage()
    test_the_input_is_not_mutated()
    test_an_empty_plan_does_not_explode()
    test_the_metric_reports_it_and_None_when_absent()
    test_the_real_story_gets_a_camera()
    print("all camera-grammar checks pass")
