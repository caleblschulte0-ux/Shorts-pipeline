#!/usr/bin/env python3
"""A designed scene must depict what the beat SAYS.

THE DEFECT (2026-08-01, shared-air run 30708150996). `_scene_phases` picked a
scene with `NEUTRAL_SCENES[(bi + k) % 7]` — pure index rotation — and the list
was documented as "TOPIC-AGNOSTIC ... carrying no subject presupposition".

It never was. Read the scenes' own default labels: free="YEARS ARE YOURS",
hold="DAYS ON HOLD", queue="MONTHS IN LINE", work="YEARS AT WORK",
screen="YEARS ON A SCREEN", sleep="YEARS ASLEEP", walkout="STOP WAITING". That
is ONE film's scene library — the where-your-life-goes piece — being dealt out
to whatever beat happened to land on each index.

So a film about the atmosphere got walkout_scene (a payoff about leaving a
waiting room: a dim room, a bright doorway, a figure striding out) under the
line "the air arriving in your lungs did not come from your room, it came from
everywhere". The blind taste judge, seeing only frames, called the doorway "a
dashboard plate ... a template with the content not filled in" and labelled the
film EMPTY_COMPOSITION and UI_WIDGET. It was neither. It was a specific scene
about a subject the film never had, staged at full size in the middle of frame.

Same root cause as the media-anchoring defect fixed the same day: something that
depicts a subject was chosen without asking what the beat is about.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import planner  # noqa: E402

AIR = ("So the air arriving in your lungs right now did not come from your "
       "room. It came from everywhere.")


def test_the_shared_air_beat_no_longer_gets_a_waiting_room():
    """The exact line and beat index that shipped the doorway."""
    for k in range(4):
        got = planner._scene_for(6, k, AIR)
        assert got != "scene_walkout", (k, got)
        assert got not in ("scene_work", "scene_screen", "scene_sleep",
                           "scene_queue", "scene_hold"), (k, got)
    print("ok  a line about air no longer stages a waiting room or an office")


def test_a_line_that_licenses_a_scene_still_gets_it():
    """The fix must not blanket-disable the library — that would be SAMENESS."""
    assert planner._scene_for(0, 0, "You spend thirteen years at work.") \
        == "scene_work"
    assert planner._scene_for(0, 0, "Twenty-six years asleep in a bed.") \
        == "scene_sleep"
    assert planner._scene_for(0, 0, "Eleven years staring at a screen.") \
        == "scene_screen"
    print("ok  a line that really is about work/sleep/screens still stages it")


def test_no_match_reaches_no_scene_at_all():
    """There is NO staging-neutral scene in this library — so use none of it.

    An earlier pass today picked (free, hold, queue) as a "staging-neutral"
    pool. That was wrong, and the next render proved it in one frame:
    queue_scene draws a literal "N O W  S E R V I N G" ticket and hold_scene a
    hold-time counter, both hardcoded. The judge saw "ON HOLD / NOW SERVING
    dashboard readouts" and labelled the film UI_WIDGET — the same waiting room
    re-imported through the pool meant to keep it out.
    """
    for line in ("Nothing here resembles any staging.",
                 "Volcanic basalt cools into hexagonal columns.",
                 "", "   "):
        for bi in range(7):
            assert planner._scene_for(bi, 0, line) is None, (line, bi)
    print("ok  an unlicensed beat reaches no scene at all, not a 'neutral' one")


def test_an_unlicensed_beat_gets_real_media():
    """Refusing a scene is only half a fix — the beat still needs a picture."""
    shots = planner._scene_phases(
        3, 9.0, 4.5, line="Volcanic basalt cools into hexagonal columns.",
        subject="a wall of dark hexagonal stone columns")
    assert shots and all(s["kind"] == "depict" for s in shots), shots
    q = shots[0]["motion_query"]
    assert "hexagonal" in q or "columns" in q or "stone" in q, q
    # phases must not fetch the SAME clip twice — that is sameness in one beat
    assert len({s["reseed"] for s in shots}) == len(shots), shots
    print(f"ok  an unlicensed beat falls back to real media ({q!r})")


def test_an_authored_scene_is_checked_too():
    """The doorway was AUTHORED in the beats file, not rotated onto it.

    shared-air names scene_walkout/queue/hold/sleep/free — the whole life-time
    library — for a film about the atmosphere. Trusting authored kinds
    absolutely is what put a waiting-room doorway under a line about lungs.
    """
    beats = [{"job": "DEVELOP", "mode": "designed_2d",
              "narration": "The air arriving in your lungs came from everywhere.",
              "understand": "a figure breathing in open air",
              "flat": {"kind": "scene_walkout"}}]
    kinds = {s.get("kind") for s in planner.plan_story(beats, [6.0])}
    assert "scene_walkout" not in kinds, kinds
    assert "depict" in kinds, kinds
    # ...but an author whose words DO license the staging still gets it
    beats[0]["narration"] = "You finally leave, walking out through the door."
    kinds = {s.get("kind") for s in planner.plan_story(beats, [6.0])}
    assert "scene_walkout" in kinds, kinds
    print("ok  an authored scene is licensed by the beat's words, or refused")


def test_variety_survives_within_a_matching_beat():
    """A long beat still changes staging between phases when it can."""
    line = "You wait on hold for hours, then you leave and walk outside."
    seen = {planner._scene_for(0, k, line) for k in range(4)}
    assert len(seen) > 1, seen
    assert seen <= set(planner.NEUTRAL_SCENES), seen
    print(f"ok  a beat whose words license several scenes still rotates ({len(seen)})")


def test_the_planner_actually_uses_it():
    """Wiring, not just the helper: a real designed beat gets a fitting scene."""
    shots = planner._scene_phases(6, 9.0, 4.5, line=AIR)
    assert len(shots) >= 2, shots
    kinds = {s["kind"] for s in shots}
    assert "scene_walkout" not in kinds, kinds
    assert shots[0].get("line") == AIR, shots[0]
    assert all("line" not in s for s in shots[1:]), shots
    print("ok  _scene_phases routes through _scene_for, narration on phase 1 only")


if __name__ == "__main__":
    test_the_shared_air_beat_no_longer_gets_a_waiting_room()
    test_a_line_that_licenses_a_scene_still_gets_it()
    test_no_match_reaches_no_scene_at_all()
    test_an_unlicensed_beat_gets_real_media()
    test_an_authored_scene_is_checked_too()
    test_variety_survives_within_a_matching_beat()
    test_the_planner_actually_uses_it()
    print("all scene-fit checks pass")
