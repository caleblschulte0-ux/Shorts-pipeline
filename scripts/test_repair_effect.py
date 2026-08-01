#!/usr/bin/env python3
"""A repair must change the RENDER, not just the story JSON.

The gap this closes: `auto_repair` wrote `_prefer_scene`, `_media_reseed` and
`_restyle_type` onto beats, `test_auto_repair.py` asserted the flags were
written, and every one of those assertions passed — while the planner read NONE
of them. The loop looked like it was repairing and re-rendered a byte-identical
film, because a flag nothing consumes is not a fix.

So these checks never assert on a flag. They run the repaired story through
`planner.plan_story` and assert the emitted SHOT LIST is materially different in
the direction the judges asked for. Any future repair lever has to survive the
same bar: show me the shot that changed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import auto_repair, planner  # noqa: E402

# a card-heavy story with one real footage beat — the shape the judges keep
# rejecting (stat plates carrying the film, one piece of real material)
STORY = {"slug": "x", "beats": [
    {"job": "HOOK", "narration": "open", "text": "the opening claim",
     "flat": {"kind": "flat_statement"}},
    {"job": "DEVELOP", "narration": "a number",
     "number": {"text": "42", "sub": "%", "label": "the share"},
     "flat": {"kind": "flat_number"}},
    {"job": "DEVELOP", "narration": "real material",
     "image": {"query": "wind blowing grass field", "perspective": "ground"}},
    {"job": "DEVELOP", "narration": "another card", "text": "a second claim",
     "flat": {"kind": "flat_statement"}},
]}
DURS = [3.0, 3.0, 3.0, 3.0]


def shots(story):
    return planner.plan_story(story["beats"], DURS)


def kinds(sh):
    return [s.get("kind") for s in sh]


def main():
    base = shots(STORY)
    # the baseline is the shape the judges reject: card treatments carrying the
    # film (a card + its text renders as `composite`), and no person anywhere
    assert not [k for k in kinds(base) if str(k).startswith("scene_")], kinds(base)
    assert kinds(base).count("composite") >= 2, kinds(base)

    # 1. CARDS_OVER_BUDGET at the scene class must get the CARDS OFF SCREEN.
    #    It used to assert specifically that a scene_* shot appeared. That is
    #    no longer the only right answer: as of 2026-08-01 the planner refuses
    #    a scene the beat's own words do not license, because the scene library
    #    belongs to one film (walkout = "STOP WAITING", queue draws a literal
    #    NOW SERVING ticket) and staging it on an unrelated beat is what got a
    #    render labelled UI_WIDGET. An unlicensed beat falls back to real media
    #    of its own subject instead — which removes the card AND puts real
    #    material on screen, so the repair is at least as strong.
    #
    #    What must still hold, and is what this check is really for: the flag
    #    materially changes the rendered plan away from cards.
    plan = {"tasks": [{"id": "t1", "defect_code": "CARDS_OVER_BUDGET",
                       "target": "film"}]}
    revised, journal = auto_repair.apply(plan, STORY, escalation="scene")
    after = shots(revised)
    assert journal[0]["applied"], journal
    replaced = [k for k in kinds(after)
                if str(k).startswith("scene_") or k in ("depict", "depict_text")]
    assert replaced, (
        "the card-budget repair applied cleanly and the planner emitted NO "
        f"scene and NO real media — the flag is dead: {kinds(after)}")
    assert kinds(after).count("composite") < kinds(base).count("composite"), (
        f"cards did not go down: {kinds(base)} -> {kinds(after)}")
    print(f"ok  1. a card-budget repair reaches the render: cards "
          f"{kinds(base).count('composite')} -> {kinds(after).count('composite')} "
          f"({replaced})")

    # 2. it converts CARDS — the real footage beat keeps its footage
    assert any(k in ("depict", "depict_text") for k in kinds(after)), (
        f"the repair destroyed the film's only real material: {kinds(after)}")
    print("ok  2. the footage beat is untouched — only cards became scenes")

    # 3. the converted scenes are TOPIC-AGNOSTIC (a repair must not import a
    #    subject the story never had, e.g. a money scene into a physics film)
    money = {"scene_money", "scene_paycheck", "scene_tax", "scene_rent",
             "scene_gas", "scene_grocery", "scene_subs", "scene_savings"}
    scene_shots = [k for k in kinds(after) if str(k).startswith("scene_")]
    assert not (set(scene_shots) & money), scene_shots
    print("ok  3. conversions use only topic-agnostic scenes, never money-world")

    # 4. converting several cards must not just trade one repetition for another
    many = {"slug": "x", "beats": [
        {"narration": f"card {i}", "text": f"claim {i}",
         "flat": {"kind": "flat_statement"}} for i in range(6)]}
    rev2, _ = auto_repair.apply(
        {"tasks": [{"id": "t", "defect_code": "CARDS_OVER_BUDGET",
                    "target": "film"}]}, many, escalation="scene")
    conv = [s.get("kind") for s in planner.plan_story(rev2["beats"], [3.0] * 6)
            if str(s.get("kind")).startswith("scene_")]
    assert len(set(conv)) == len(conv), f"repeated scene kind: {conv}"
    print(f"ok  4. multiple conversions rotate rather than repeat ({conv})")

    # 5. MEDIA_UNSUITABLE must reach the SELECTION GATE as a reseed, or the
    #    re-render re-picks the very clip the judges rejected
    plan = {"tasks": [{"id": "t2", "defect_code": "MEDIA_UNSUITABLE",
                       "target": "beat 2"}]}
    revised, journal = auto_repair.apply(plan, STORY, escalation="local")
    assert journal[0]["applied"], journal
    dep = [s for s in shots(revised) if s.get("kind") in ("depict", "depict_text")]
    assert dep, "the footage beat vanished"
    assert int(dep[0].get("reseed", 0)) >= 1, (
        "a media repair produced a shot with no reseed — the deterministic "
        f"candidate order will hand back the SAME clip: {dep[0]}")
    print(f"ok  5. a media repair reaches selection as reseed="
          f"{dep[0]['reseed']} (the rejected clip is skipped)")

    # 6. reseed ACCUMULATES — a beat rejected twice must not retry the second
    #    clip it already shipped
    again, _ = auto_repair.apply(plan, revised, escalation="local")
    dep2 = [s for s in shots(again) if s.get("kind") in ("depict", "depict_text")]
    assert int(dep2[0]["reseed"]) > int(dep[0]["reseed"]), (dep[0], dep2[0])
    print(f"ok  6. a second rejection deepens the reseed "
          f"({dep[0]['reseed']} -> {dep2[0]['reseed']}), never repeats it")

    # 7. an unrepaired story must render IDENTICALLY — reproducibility is what
    #    makes "the render changed" evidence that the repair did it
    assert kinds(shots(STORY)) == kinds(base)
    assert all(int(s.get("reseed", 0)) == 0 for s in shots(STORY))
    print("ok  7. an unrepaired story still plans identically (no drift)")

    # 8. the OTHER half: the selection gate must honour the reseed. Checks 5-6
    #    prove the shot carries it; this proves it changes which clip is taken.
    from data_learning import media
    pool = [{"title": f"wind blowing grass field {i}", "source": "stock",
             "url": f"http://example.invalid/{i}.mp4", "license": "CC0"}
            for i in range(4)]
    orig = (media.find, media.acquire, media._best_dynamic_window)
    try:
        media.find = lambda *a, **k: [dict(c) for c in pool]
        media.acquire = lambda c, dest: dest.write_bytes(b"x" * 2048)
        media._best_dynamic_window = lambda dest, secs: (1.0, 99.0)
        picks = [media.motion_first("wind blowing grass field", 3.0,
                                    Path("/tmp"), reseed=r,
                                    log=lambda m: None)
                 for r in (0, 1, 2)]
        assert all(p for p in picks), picks
        urls = [p["url"] for p in picks]
        assert len(set(urls)) == 3, f"reseed did not change the pick: {urls}"
        print(f"ok  8. the selection gate honours the reseed — three different "
              f"clips for reseed 0/1/2 ({[u[-6:] for u in urls]})")
    finally:
        media.find, media.acquire, media._best_dynamic_window = orig

    # 9. THE LADDER MUST NOT DEAD-END. Attempt 1 opens at the `local` class, and
    #    CARDS_OVER_BUDGET — the defect the judges raise most — is not even
    #    PLANNED as a task there; repair_planner holds it in `deferred`. So
    #    auto_repair never sees it, emits no journal line about it, and a loop
    #    that stopped on "nothing applied" would never once repair the commonest
    #    complaint. This asserts the shape produce() relies on to widen: held at
    #    local (visible in `deferred`), planned and applied at scene.
    from data_learning import repair_planner
    findings = [{"defect_code": "CARDS_OVER_BUDGET", "severity": "blocker",
                 "target": "film"}]
    p_local = repair_planner.plan(findings, attempt=1, escalation="local")
    assert not p_local.get("tasks"), p_local
    assert p_local.get("deferred"), (
        "a card-budget finding at the local class is neither a task nor "
        f"deferred — produce() would see no reason to widen: {p_local}")
    _, j_local = auto_repair.apply(p_local, STORY, escalation="local")
    assert not [j for j in j_local if j["applied"]], j_local

    p_scene = repair_planner.plan(findings, attempt=1, escalation="scene")
    assert p_scene.get("tasks"), p_scene
    rev, j_scene = auto_repair.apply(p_scene, STORY, escalation="scene")
    assert [j for j in j_scene if j["applied"]], j_scene
    # same as check 1: a licensed scene OR real media both count as "the plan
    # changed". What must not happen is the repair applying and the render
    # coming out identical.
    assert kinds(shots(rev)) != kinds(shots(STORY)), (
        "widening produced an applied repair that still changed no shot")
    print("ok  9. a card-budget finding is HELD at local (deferred, not a task) "
          "and both plans and renders one step wider — the loop widens rather "
          "than stalling on the commonest defect")

    print("repair effect: 9/9 checks pass — repairs reach the render")


if __name__ == "__main__":
    main()
