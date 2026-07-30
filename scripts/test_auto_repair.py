#!/usr/bin/env python3
"""The loop must actually FIX itself: a ranked plan has to become real edits,
respecting the escalation ladder, with nothing story-specific."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import auto_repair, media_suitability as suit  # noqa: E402

STORY = {"slug": "x", "beats": [
    {"kind": "flat_hook", "say": "open"},
    {"kind": "scene_work", "subject": "person at a desk"},
    {"kind": "flat_number", "hold": 3.0},
    {"kind": "flat_statement"},
    {"kind": "scene_free", "subject": "person walking"},
    {"kind": "flat_compare"},
]}


def task(code, target="film", tid="t1"):
    return {"id": tid, "defect_code": code, "target": target}


def main():
    n = len(STORY["beats"])

    # 1. a media complaint reseeds that beat — no story knowledge required
    s, j = auto_repair.apply({"tasks": [task("MEDIA_UNSUITABLE", "beat 1")],
                              "repair_class": "local"}, STORY)
    assert s["beats"][1]["_media_reseed"] == 1 and j[0]["applied"]
    assert STORY["beats"][1].get("_media_reseed") is None, "story was mutated"
    print("ok  1. media findings reseed the targeted beat (input unmutated)")

    # 2. a stale span halves the hold
    s, _ = auto_repair.apply({"tasks": [task("STALE_SPAN", "beat 2")],
                              "repair_class": "local"}, STORY)
    assert s["beats"][2]["hold"] == 1.5
    print("ok  2. a stale span halves that beat's hold")

    # 3. THE LADDER: a card-budget fix is refused at `local`, applied at `scene`
    p = {"tasks": [task("CARDS_OVER_BUDGET")], "repair_class": "local"}
    s, j = auto_repair.apply(p, STORY, escalation="local")
    assert not j[0]["applied"] and "scene repair class" in j[0]["why"]
    s, j = auto_repair.apply(p, STORY, escalation="scene")
    converted = [b for b in s["beats"] if b.get("_prefer_scene")]
    assert j[0]["applied"] and converted, j
    print(f"ok  3. card conversion deferred at local, applied at scene "
          f"({len(converted)} beat(s))")

    # 4. re-opening the film is STRUCTURAL only
    p = {"tasks": [task("HOOK_WEAK", "beat 0")]}
    assert not auto_repair.apply(p, STORY, escalation="scene")[1][0]["applied"]
    s, j = auto_repair.apply(p, STORY, escalation="structural")
    assert j[0]["applied"] and s["beats"][0]["_force_motion"]
    print("ok  4. the opening is only re-cut at the structural class")

    # 5. a dull beat with a subject gets motion; without one, a scene
    s, _ = auto_repair.apply({"tasks": [task("DULL_BEAT", "beat 1"),
                                        task("DULL_BEAT", "beat 3", "t2")],
                              "repair_class": "local"}, STORY)
    assert s["beats"][1]["_force_motion"] and s["beats"][3]["_prefer_scene"]
    print("ok  5. dull beats get motion, or a scene when they have no subject")

    # 6. an unknown code is recorded as unrepaired, never silently dropped
    _, j = auto_repair.apply({"tasks": [task("SOMETHING_NEW")],
                              "repair_class": "structural"}, STORY)
    assert not j[0]["applied"] and "no automated repair" in j[0]["action"]
    print("ok  6. an unhandled defect is journaled, not swallowed")

    # --- the suitability gate (system-level, every channel) ----------------
    branded = {"title": "File:Bodycam Video From Attack on LAPD Officer.webm"}
    news = {"title": "大批民众自发前往香港火灾现场周边献花悼念.webm"}
    reel = {"title": "Czechoslovak arms factories 1938 newsreel.webm"}
    clean = {"title": "person, alone, lonely, walk, sunset, outdoors"}
    for bad in (branded, news, reel):
        assert not suit.is_suitable(bad), bad["title"]
    assert suit.is_suitable(clean)
    kept, rejected = suit.filter_candidates([branded, news, reel, clean])
    assert kept == [clean] and len(rejected) == 3
    assert all(r[1] for r in rejected), "a rejection with no reason"
    print("ok  7. every clip the judges named is filtered out; clean stock "
          "survives, each rejection with a reason")

    # 8. a film ABOUT conflict may legitimately show it — register-aware
    assert suit.is_suitable({"title": "protest march crowd"}, register="news")
    assert not suit.is_suitable({"title": "protest march crowd"})
    print("ok  8. the off-register rule respects the film's declared register")

    # 9. branded is hard regardless of register — a burn-in survives any grade
    assert not suit.is_suitable(branded, register="news")
    print("ok  9. third-party branding is rejected even for a news register")

    print("auto repair + suitability: 9/9 checks pass")


if __name__ == "__main__":
    main()
