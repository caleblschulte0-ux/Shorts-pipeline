"""auto_repair — APPLY a ranked repair plan to a story, so the loop fixes itself.

judge_loop already produces a ranked plan from the judges' real findings. Until
now nothing consumed it: the plan was written to the package and a human read
it. This closes that gap — `apply(plan, story)` edits the beats so the NEXT
render is materially different in the direction the judges asked for.

Strictly generic. Repairs are chosen by DEFECT CODE and applied to whatever
beat the finding targets. Nothing here reads a slug, title or topic, and no
rule is written for one film — the same transformations serve every channel.

Escalation is respected: a `local` pass only swaps media and trims holds, a
`scene` pass may change a beat's treatment, and only a `structural` pass may
touch the opening or the beat order. That is what makes each attempt broader
than the last instead of the same move retried.

Every edit is recorded in the returned journal so the comparison step can say
what actually changed — and so a repair that did nothing is visible as such.
"""
from __future__ import annotations

import copy
import re

# beats that render as a card/stat-plate look; converting one to a scene is the
# standard answer to "this reads as an infographic reel"
_CARD_PREFIX = ("flat_", "chapter")
# treatments a card can become, cheapest-first. `_prefer_scene` asks the planner
# for a character/scene rendering of the same content.
_SCENE_HINT = "_prefer_scene"


def _beat_index(target, n: int, beatmap: dict | None = None) -> int | None:
    """Resolve a finding's target to a beat index.

    Accepts 'beat 7', 7, '7', or a TIME RANGE ('112.0-119.5s') resolved through
    the beatmap. The time-range case is not decorative: the director reports
    every span defect that way — STALE_SPAN, PACING — because it watches the
    rendered film and has no beat numbers, only a clock. This function's own
    docstring used to promise the caller mapped those "via the beatmap", and no
    caller ever did, so on the 2026-08-01 shared-air render the one genuinely
    repairable finding of six died on "target is a time range, not a beat" and
    the loop applied zero repairs. A span belongs to the beat that covers its
    midpoint, which is the beat you would actually re-cut.
    """
    if isinstance(target, int):
        return target if 0 <= target < n else None
    s = str(target)
    m = re.search(r"beat\s*(\d+)", s, re.I) or re.fullmatch(r"\s*(\d+)\s*", s)
    if m:
        i = int(m.group(1))
        return i if 0 <= i < n else None
    span = re.fullmatch(r"\s*([\d.]+)\s*-\s*([\d.]+)\s*s?\s*", s)
    if span and beatmap:
        try:
            mid = (float(span.group(1)) + float(span.group(2))) / 2.0
        except ValueError:
            return None
        for i, b in enumerate(beatmap.get("beats") or []):
            if i >= n:
                break
            try:
                a, z = str(b.get("t", "")).split("-")
                if float(a) <= mid < float(z):
                    return i
            except (ValueError, AttributeError):
                continue
    return None


from data_learning.textmatch import words as _words


def _anchored(beat: dict) -> bool:
    """Does this beat's media query depict what the beat actually SAYS?

    A query sharing no content word with its own narration would serve any beat
    in the film equally well — that is the definition of an interchangeable
    shot. Beats with no media query at all (designed scenes) are not judged
    here; they are anchored by construction.
    """
    img = beat.get("image") or {}
    q = " ".join(str(img.get(k, "")) for k in ("query", "subject")) + " " + \
        str(beat.get("motion_query", "") or beat.get("subject", "") or "")
    qw = _words(q)
    if not qw:
        return True
    return bool(qw & _words(beat.get("narration", "")))


def _least_anchored(beats: list) -> list[int]:
    """Indices of media beats whose query is not anchored to their narration."""
    return [i for i, b in enumerate(beats) if not _is_card(b) and not _anchored(b)]


def _kind(beat: dict) -> str:
    return str((beat.get("flat") or {}).get("kind") or beat.get("kind") or "")


def _is_card(beat: dict) -> bool:
    return _kind(beat).startswith(_CARD_PREFIX)


def apply(plan: dict, story: dict, escalation: str | None = None,
          beatmap: dict | None = None) -> dict:
    """Return (new_story, journal). `story` is not mutated.

    journal: [{task, defect_code, target, action, applied: bool, why}]
    """
    story = copy.deepcopy(story)
    beats = story.get("beats") or []
    n = len(beats)
    cls = escalation or plan.get("repair_class") or "local"
    journal: list[dict] = []

    def note(t, action, applied, why=""):
        journal.append({"task": t.get("id"), "defect_code": t.get("defect_code"),
                        "target": t.get("target"), "action": action,
                        "applied": bool(applied), "why": why})

    for t in plan.get("tasks", []):
        code = str(t.get("defect_code", "")).upper()
        i = _beat_index(t.get("target"), n, beatmap)

        # --- media: the asset was unsuitable or off-subject. Re-query with a
        # different subject phrasing; the suitability gate keeps the branded
        # ones out of the pool entirely, so a re-render simply picks another.
        if code in ("MEDIA_UNSUITABLE", "MEDIA_LICENCE", "WEAK_DEPICTION"):
            if i is None:
                note(t, "reseed_media_globally", True,
                     "no beat named; the suitability filter re-picks on render")
                story["_media_reseed"] = int(story.get("_media_reseed", 0)) + 1
                continue
            beats[i].pop("_force_motion", None)
            beats[i]["_media_reseed"] = int(beats[i].get("_media_reseed", 0)) + 1
            note(t, f"reseed beat {i} media", True)
            continue

        # --- pacing: a span held too long. Trim the beat rather than re-shoot.
        if code in ("STALE_SPAN", "PACING"):
            if i is None:
                note(t, "trim", False, "target is a time range, not a beat")
                continue
            hold = float(beats[i].get("hold", 0) or 0)
            if hold > 0:
                beats[i]["hold"] = round(max(0.0, hold * 0.5), 2)
                note(t, f"halve hold on beat {i}", True)
            else:
                beats[i]["_prefer_designed"] = True
                note(t, f"beat {i} -> designed explainer", True)
            continue

        # --- a dull beat wants motion. Only meaningful when the beat has a
        # subject a video search can serve.
        if code == "DULL_BEAT":
            if i is None:
                note(t, "force_motion", False, "no beat named")
                continue
            if beats[i].get("subject") or beats[i].get("image"):
                beats[i]["_force_motion"] = True
                note(t, f"force motion on beat {i}", True)
            else:
                beats[i][_SCENE_HINT] = True
                note(t, f"beat {i} -> scene (no media subject)", True)
            continue

        # --- the card look dominates. SCENE-class and up: convert cards to
        # scenes, worst offenders first, until the budget is plausibly met.
        # BORING and LOW_ENERGY belong here too. They were in the taste judge's
        # vocabulary and in NO strategy at all, so a film the judge called
        # boring produced a task whose journal entry read "no automated repair
        # for this code" — a label that can be raised but never answered.
        if code in ("CARDS_OVER_BUDGET", "INFOGRAPHIC_REEL", "NO_CHARACTER",
                    "NO_SOUL", "EMPTY_COMPOSITION", "SAMENESS",
                    "BORING", "LOW_ENERGY"):
            if cls == "local":
                note(t, "convert cards to scenes", False,
                     "needs the scene repair class — deferred by the ladder")
                continue
            cards = [k for k, b in enumerate(beats) if _is_card(b)]
            if cards:
                convert = cards[:max(1, len(cards) // 3)]
                for k in convert:
                    beats[k][_SCENE_HINT] = True
                note(t, f"convert {len(convert)} card beat(s) to scenes",
                     True, f"card beats: {len(cards)}")
                continue
            # A FILM CAN BE SOULLESS WITHOUT A SINGLE CARD. This branch used to
            # end here, so on a film with no cards the repair for "no soul /
            # sameness / empty composition" was a no-op BY CONSTRUCTION — the
            # finding was consumed and nothing changed. That is how shared-air
            # (2026-08-01) judged 4/10 as "a montage of anonymous mood stock,
            # ~9 of 24 beats shuffleable with zero consequence" and got zero
            # repairs for it: the healer only knew how to fix card-reels.
            #
            # The other way to be soulless is footage that depicts nothing in
            # particular. The generic, film-agnostic test is ANCHORING: does a
            # beat's media query share any content word with the words that beat
            # SPEAKS? A query that does not is interchangeable with every other
            # beat's — exactly the "could be shuffled" complaint. Convert the
            # least-anchored third to scenes and reseed the rest, so the next
            # render is materially different where the judge said it was flat.
            ranked = _least_anchored(beats)
            convert = ranked[:max(1, len(ranked) // 3)]
            for k in convert:
                beats[k][_SCENE_HINT] = True
            for k in ranked[len(convert):]:
                beats[k]["_media_reseed"] = int(beats[k].get("_media_reseed", 0)) + 1
            if not ranked:
                story["_media_reseed"] = int(story.get("_media_reseed", 0)) + 1
            note(t, f"no cards: {len(convert)} unanchored beat(s) -> scenes, "
                 f"{len(ranked) - len(convert)} reseeded", True,
                 f"unanchored beats: {len(ranked)}")
            continue

        # --- the opening. STRUCTURAL only: re-opening a film is not a polish.
        if code in ("HOOK_WEAK", "PREMISE_UNCLEAR"):
            if cls != "structural":
                note(t, "re-open the film", False,
                     "needs the structural repair class")
                continue
            if beats:
                beats[0]["_force_motion"] = True
                beats[0]["_prefer_scene"] = True
                note(t, "re-open on motion + scene", True)
            continue

        # --- typography / widget complaints are style flags the renderer reads
        if code in ("CHEAP_TYPOGRAPHY", "UI_WIDGET"):
            story["_restyle_type"] = True
            note(t, "flag type restyle", True)
            continue

        note(t, "no automated repair for this code", False,
             "left for the next escalation or the owner")

    story["beats"] = beats
    return story, journal


def summarize(journal: list[dict]) -> str:
    done = [j for j in journal if j["applied"]]
    skipped = [j for j in journal if not j["applied"]]
    return (f"{len(done)} repair(s) applied, {len(skipped)} deferred: "
            + "; ".join(f"{j['defect_code']}->{j['action']}" for j in done[:5]))
