#!/usr/bin/env python3
"""A designed beat is judged on whether it MOVES, not on whether it photographs.

This locks in behaviour that already existed and was twice mistaken for a bug.

Measuring `interest_judge._appeal` on the character scenes gives 0.29-0.51
against a 0.55 dull floor, which looks damning: the taste judge demands
character scenes (NO_CHARACTER) while the dullness floor appears to reject them
for being flat vector art. It was reported to the owner as a contradiction
needing a deliberate gate change.

It is not one. `dull_beats` never applies the appeal floor to a designed beat —
it flags one only when it is genuinely STATIC, and then asks for it to be
ANIMATED rather than replaced by footage. The floor governs photographic beats,
where low appeal really does mean grey wallpaper.

The test exists so nobody "fixes" this by lowering the footage bar to match a
number that was never applied to scenes.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import no_dull_beats as ndb  # noqa: E402

SCENE = {"job": "DEVELOP", "flat": {"kind": "scene_hold"}}
CARD = {"job": "DEVELOP", "flat": {"kind": "flat_number"}}
FOOT = {"job": "DEVELOP", "image": {"query": "crowd people walking street"}}
NO_BORING = {"boring_stretches": []}
LOW = 0.29          # measured on the real scene_hold frame


def dull(cool, beats):
    return ndb.dull_beats(NO_BORING, cool, beats)


def row(beat, appeal, suspect=(), t="10-15"):
    return {"beat": beat, "job": "DEVELOP", "appeal": appeal,
            "suspect": list(suspect), "t": t}


def main():
    # 1. a MOVING character scene is not dull, however unphotographic
    assert dull([row(0, LOW)], [SCENE]) == []
    assert dull([row(0, LOW)], [CARD]) == []
    print(f"ok  1. a moving designed beat at appeal {LOW} is NOT dull — the "
          "photographic floor does not apply to it")

    # 2. a STATIC one is dull, and its fix is to animate, never to replace
    d = dull([row(0, LOW, ["LOW_MOTION"])], [SCENE])
    assert len(d) == 1 and d[0]["kind"] == "animate", d
    print(f"ok  2. a static designed beat IS dull, fix={d[0]['kind']!r} — the "
          "explainer is kept, not swapped for stock")

    # 3. the same low appeal on a PHOTOGRAPHIC beat is dull, fix=motion
    d = dull([row(0, LOW)], [FOOT])
    assert len(d) == 1 and d[0]["kind"] == "motion", d
    print("ok  3. the floor still governs footage — same score, dull, "
          f"fix={d[0]['kind']!r}")

    # 4. both treatments are recognised as designed (a scene is not footage)
    assert ndb._is_designed(SCENE) and ndb._is_designed(CARD)
    assert not ndb._is_designed(FOOT)
    print("ok  4. character scenes and cards both count as designed")

    # 5. a bright hook is allowed to hold — the opening frame earns its stillness
    assert dull([{"beat": 0, "job": "HOOK", "appeal": 0.95, "suspect": [],
                  "t": "0-5"}], [FOOT]) == []
    print("ok  5. a strong hook is not condemned for holding")

    print("treatment-aware dullness: 5/5 checks pass")


if __name__ == "__main__":
    main()
