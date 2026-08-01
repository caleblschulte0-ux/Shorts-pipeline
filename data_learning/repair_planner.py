"""repair_planner — turn judge FINDINGS into a ranked, executable repair plan.

The gap this closes: the judges were already producing `worst_beat`, `fix`,
reject labels, pacing complaints and hook complaints, and the repair engine was
consuming almost none of it — it repaired mechanical defects it detected itself
and treated the creative judge as a bouncer at the exit. Here every judge
finding becomes a repair task with a target, a required change and a success
criterion, ordered by a fixed priority law:

    1  integrity   hard factual, safety, licence or artifact blockers
    2  premise     hook, promise and payoff failures
    3  structure   pacing, ordering, stale spans, story shape
    4  depiction   visual sameness, weak or wrong depiction, media suitability
    5  polish      captions, framing, local shot repair

Ordering is deterministic: (tier, severity, target) — the same findings always
produce the same plan, so a stalled loop is detectable rather than random.

CONTRADICTION GUARD: two tasks that would change the same target in opposite
directions are not both emitted. The higher-severity task wins and the loser is
recorded in ``suppressed`` with the reason, so the conflict is visible instead
of silently applied last-write-wins.

Nothing here selects behavior by story identity — findings in, plan out.
"""
from __future__ import annotations

import json
from pathlib import Path

TIERS = {
    "integrity": 1, "premise": 2, "structure": 3, "depiction": 4, "polish": 5,
}
_SEV = {"blocker": 0, "major": 1, "minor": 2, "info": 3}

# defect code -> (tier, subsystem, required change, success criterion)
# The catalogue is generic: every entry describes a class of defect any film
# can have. Unknown codes fall back to a depiction-tier task so a new judge
# label is never silently dropped.
CATALOG: dict[str, tuple[str, str, str, str]] = {
    # --- 1 integrity ---------------------------------------------------
    "FACTUAL_UNSOURCED": ("integrity", "facts_gate",
                          "supply a claim source for the spoken number or cut the claim",
                          "facts gate reports full numeric coverage"),
    "MEDIA_LICENCE": ("integrity", "media_gateway",
                      "replace the asset with one whose licence permits this use",
                      "every credit carries a usable licence"),
    "MEDIA_UNSUITABLE": ("integrity", "media_gateway",
                         "replace the asset: third-party branding, chyrons, timecode "
                         "or subject matter unfit for the film's register",
                         "no clip carries foreign branding or an off-register subject"),
    "ARTIFACT_INTEGRITY": ("integrity", "pro_render",
                           "re-render: the package is incomplete or inconsistent",
                           "package manifest verifies"),
    "TECHNICAL": ("integrity", "render_gates",
                  "fix the technical defect (duration, audio, encode)",
                  "render_gates technical check passes"),
    # --- 2 premise -----------------------------------------------------
    "HOOK_WEAK": ("premise", "hook_director",
                  "re-open the film: the first seconds must state a promise and move",
                  "hook gate passes on both line and visual"),
    "PAYOFF_MISSING": ("premise", "story_author",
                       "deliver the promise the opening made, explicitly, near the end",
                       "payoff judge finds the promise answered"),
    "PREMISE_UNCLEAR": ("premise", "story_author",
                        "state the film's question in the opening beat",
                        "hook judge reports a legible promise"),
    # --- 3 structure ---------------------------------------------------
    "STALE_SPAN": ("structure", "no_dull_beats",
                   "cut or introduce a genuinely new element inside the span",
                   "novelty check reports no span over the hold limit"),
    "PACING": ("structure", "no_dull_beats",
               "match the picture to the words under it; shorten the hold",
               "pacing check reports no desynced beat"),
    "DULL_BEAT": ("structure", "no_dull_beats",
                  "raise the beat's appeal: motion, a new element, or a scene",
                  "beat appeal clears the dull floor"),
    "TENSION_FLAT": ("structure", "story_author",
                     "escalate: each act must raise the stake the previous one set",
                     "tension judge reports rising progression"),
    # --- 4 depiction ---------------------------------------------------
    "SAMENESS": ("depiction", "planner",
                 "break the repeated visual family; vary composition and engine",
                 "variety check reports no look-alike cluster"),
    "CARDS_OVER_BUDGET": ("depiction", "planner",
                          "carry beats with scenes or footage; cards must be a minority",
                          "card family fraction under the budget"),
    "INFOGRAPHIC_REEL": ("depiction", "planner",
                         "replace chart-carried beats with character or scene beats",
                         "taste judge no longer reports an infographic reel"),
    "NO_CHARACTER": ("depiction", "scenes",
                     "put a character in the frame carrying the idea",
                     "taste judge reports a present character"),
    "NO_SOUL": ("depiction", "scenes",
                "give the film a point of view: character, stakes, a human beat",
                "taste judge withdraws the label"),
    "EMPTY_COMPOSITION": ("depiction", "scenes",
                          "fill the frame: the shot reads as an unfinished template",
                          "taste judge withdraws the label"),
    "BORING": ("depiction", "planner", "raise energy across the flagged span",
               "taste judge withdraws the label"),
    "LOW_ENERGY": ("depiction", "planner", "raise motion and cut rate",
                   "taste judge withdraws the label"),
    "WEAK_DEPICTION": ("depiction", "media_gateway",
                       "show the noun the narration says, not an adjacent idea",
                       "editorial alignment reports the subject visible"),
    # --- 5 polish ------------------------------------------------------
    "CHEAP_TYPOGRAPHY": ("polish", "flat2d",
                         "restyle the type: weight, spacing and hierarchy",
                         "taste judge withdraws the label"),
    "UI_WIDGET": ("polish", "flat2d",
                  "remove the interface-looking element",
                  "taste judge withdraws the label"),
    "CAPTIONS": ("polish", "packager", "fix caption timing or readability",
                 "caption check passes"),
    "FRAMING": ("polish", "pro_render", "recompose the shot",
                "visual judge withdraws the complaint"),
}

# Repair CLASS by attempt — the escalation ladder. Each level is deliberately
# broader than the last so a stalled loop stops re-trying the same move.
LADDER = {
    1: "local",        # replace media, shorten spans, fix captions/framing
    2: "scene",        # visual grammar, composition, pacing pattern, transitions
    3: "structural",   # hook, narration, beat order, storyboard, creative approach
}
# which subsystems a repair class is allowed to touch
CLASS_SCOPE = {
    "local": {"media_gateway", "pro_render", "packager", "flat2d", "render_gates",
              "facts_gate", "no_dull_beats"},
    "scene": {"media_gateway", "pro_render", "packager", "flat2d", "render_gates",
              "facts_gate", "no_dull_beats", "planner", "scenes"},
    "structural": set(CATALOG and {v[1] for v in CATALOG.values()}) | {"story_author"},
}
EFFORT = {"integrity": "medium", "premise": "high", "structure": "high",
          "depiction": "medium", "polish": "low"}
# Catch-all targets: findings here are about the whole film, so two of them are
# not automatically in conflict the way two findings on one shot would be.
GENERIC_TARGETS = {"film", "media", ""}


def repair_class(attempt: int) -> str:
    """The repair class for an attempt number. Beyond the ladder everything is
    structural — but the loop is bounded elsewhere and should abandon instead."""
    return LADDER.get(int(attempt), "structural")


def _entry(code: str) -> tuple[str, str, str, str]:
    return CATALOG.get(str(code).upper(),
                       ("depiction", "planner",
                        f"address the judge finding {code}",
                        "the judge withdraws the finding"))


def _target(f: dict) -> str:
    for k in ("beat", "target", "time_range", "worst_beat"):
        v = f.get(k)
        if v not in (None, ""):
            return str(v)
    return "film"


def plan(findings: list[dict], attempt: int = 1,
         escalation: str | None = None) -> dict:
    """Build the ranked repair plan for one attempt.

    Every task carries: target, defect code, severity, subsystem, required
    change, success criterion, supporting judge evidence, dependencies and an
    effort estimate. Tasks outside the current repair class are retained as
    ``deferred`` (with the class that would unlock them) rather than dropped —
    the escalation ladder is then visible instead of implicit.
    """
    cls = escalation or repair_class(attempt)
    scope = CLASS_SCOPE.get(cls, CLASS_SCOPE["structural"])
    tasks, deferred, suppressed = [], [], []
    seen_targets: dict[str, dict] = {}

    ordered = sorted(
        (f for f in (findings or []) if not f.get("resolved")),
        key=lambda f: (TIERS.get(_entry(f.get("defect_code", "")) [0], 9),
                       _SEV.get(str(f.get("severity", "info")).lower(), 9),
                       str(_target(f))))

    for f in ordered:
        code = str(f.get("defect_code", "UNKNOWN")).upper()
        tier, subsystem, change, criterion = _entry(code)
        tgt = _target(f)
        task = {
            "id": f"t{len(tasks) + len(deferred) + len(suppressed) + 1:03d}",
            "target": tgt,
            "defect_code": code,
            "severity": str(f.get("severity", "major")).lower(),
            "tier": tier,
            "tier_rank": TIERS.get(tier, 9),
            "subsystem": subsystem,
            "repair_class": cls,
            "required_change": f.get("recommended_fix") or change,
            "success_criterion": criterion,
            "evidence": {
                "judge": f.get("judge"),
                "complaint": f.get("complaint"),
                "time_range": f.get("time_range"),
                "frame": f.get("frame"),
                "confidence": f.get("confidence"),
            },
            "dependencies": [],
            "effort": EFFORT.get(tier, "medium"),
        }
        # CONTRADICTION GUARD — one SPECIFIC target, one instruction per plan.
        # Two tasks asking DIFFERENT subsystems to change the same shot would
        # fight, so the higher-severity one wins and the loser is recorded
        # (never dropped). Whole-film findings are exempt: "film" is a catch-all
        # bucket, and a caption defect does not contradict a pacing defect just
        # because neither names a beat.
        prior = seen_targets.get(tgt)
        if tgt not in GENERIC_TARGETS and prior is not None \
                and prior["subsystem"] != subsystem:
            new_wins = _SEV.get(task["severity"], 9) < _SEV.get(prior["severity"], 9)
            winner, loser = (task, prior) if new_wins else (prior, task)
            if new_wins:
                for bucket in (tasks, deferred):
                    if prior in bucket:
                        bucket.remove(prior)
                seen_targets[tgt] = task
                (tasks if subsystem in scope else deferred).append(task)
            suppressed.append({**loser, "suppressed_because":
                               f"conflicts with {winner['defect_code']} on the same "
                               f"target ({winner['subsystem']} wins on severity)"})
            continue
        seen_targets[tgt] = task
        if subsystem in scope:
            tasks.append(task)
        else:
            task["unlocks_at_class"] = next(
                (c for c, s in CLASS_SCOPE.items() if subsystem in s), "structural")
            deferred.append(task)

    # integrity tasks gate everything else in the same plan
    integ = [t["id"] for t in tasks if t["tier"] == "integrity"]
    for t in tasks:
        if t["tier"] != "integrity":
            t["dependencies"] = list(integ)

    return {
        "attempt": int(attempt),
        "repair_class": cls,
        "n_tasks": len(tasks),
        "tasks": tasks,
        "deferred": deferred,
        "suppressed": suppressed,
        "ordering": "tier -> severity -> target (deterministic)",
    }


def signature(p: dict) -> str:
    """A stable fingerprint of WHAT a plan intends to do. Two consecutive
    attempts with the same signature are the same repair being retried — the
    loop uses this to escalate instead of spinning."""
    import hashlib
    key = "|".join(f"{t['defect_code']}@{t['target']}->{t['subsystem']}"
                   for t in sorted(p.get("tasks", []),
                                   key=lambda t: (t["defect_code"], t["target"])))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


if __name__ == "__main__":
    import sys
    findings = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(plan(findings, int(sys.argv[2]) if len(sys.argv) > 2 else 1),
                     indent=2))
