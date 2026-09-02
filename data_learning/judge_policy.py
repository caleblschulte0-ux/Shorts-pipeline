"""judge_policy — the BINDING quality law, shared by every channel.

Before this module a film advanced on a weak two-part test: no reject labels
AND ``personality >= 3``. A mediocre video with a 3.0/10 professional-quality
score satisfied that test, so the one number that actually answers "would I
believe a professional editor shipped this?" was recorded and ignored.

This module makes that number binding, and makes the whole decision explicit:

  - the professional-quality score (``overall_10``) is REQUIRED. A verdict
    without one is missing evidence, not a pass.
  - bands are configurable and drive different outcomes (structural failure /
    repair required / internal review / owner review).
  - a hard blocker from ANY judge blocks advancement. Nothing is averaged
    away: `decide()` never mixes a blocker into a mean.
  - EVERY required judge must individually pass. A unanimous reject
    (pass=False from all required judges) is not "disagreement" — dissent()
    only fires on a split — so a required judge's own pass field is checked
    directly and blocks on its own.
  - judge DISAGREEMENT is surfaced as its own blocker rather than resolved by
    silently taking the kinder verdict.
  - autonomous publishing stays off here regardless of score; only the
    separately approved launch policy may permit it.

Nothing in this module knows about any story, slug, title or topic — the
policy is the same law for every film.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Bands, as ranges on the 0-10 professional-quality score. Bands are
# half-open upward: structural_failure < repair_floor <= repair_required <
# internal_floor <= internal_review < owner_floor <= owner_review.
DEFAULT_POLICY: dict = {
    # --- the score bands -------------------------------------------------
    "repair_floor": 7.5,          # below this the CREATIVE APPROACH is failing
    "internal_floor": 8.5,        # 7.5-8.49: repairable
    "owner_floor": 9.0,           # 8.5-8.99: internal review only
    # --- what it takes to ADVANCE out of the development loop ------------
    "development_min_overall": 8.0,
    "owner_review_min_overall": 9.0,
    "min_personality": 3.0,
    "max_unresolved_major": 0,
    # --- hard vocabulary -------------------------------------------------
    "auto_reject_labels": [
        "INFOGRAPHIC_REEL", "NO_CHARACTER", "NO_SOUL", "SAMENESS",
        "EMPTY_COMPOSITION", "BORING", "LOW_ENERGY", "CARDS_OVER_BUDGET",
        "CHEAP_TYPOGRAPHY", "UI_WIDGET",
    ],
    # --- loop bounds -----------------------------------------------------
    "max_attempts": 3,
    # --- publishing ------------------------------------------------------
    "autonomous_publish": False,   # the launch policy owns this, not the score
    # --- which judges MUST have produced a verdict ------------------------
    "required_judges": ["taste", "technical", "factual"],
    "rubric_version": "2026-07-30",
}

_ENV_PREFIX = "CURIOSITY_JUDGE_"
_NUMERIC = {"repair_floor", "internal_floor", "owner_floor",
            "development_min_overall", "owner_review_min_overall",
            "min_personality", "max_unresolved_major", "max_attempts"}

# The 0-10 professional-quality scale every score-shaped field lives on.
_SCORE_FIELDS = ("repair_floor", "internal_floor", "owner_floor",
                 "development_min_overall", "owner_review_min_overall",
                 "min_personality")
_INT_FIELDS = ("max_unresolved_major", "max_attempts")

#: SAFETY FLOORS — the minimums this module's own docstring makes binding
#: ("the professional-quality score is REQUIRED", "personality still has a
#: floor"). An override may RAISE a floor (stricter is always allowed, the
#: same rule the retro triage applies) but may never push one below the
#: default: a config that sets development_min_overall to 0 is the exact
#: "advance a 3.0/10 film" failure this module exists to prevent, arriving
#: through a side door.
_SAFETY_FLOORS = ("development_min_overall", "owner_review_min_overall",
                  "min_personality")

# Severities, most serious first. `blocker` can never be averaged away.
SEVERITY_ORDER = ("blocker", "major", "minor", "info")


def _is_num(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(float(v)))


def _problems(pol: dict) -> list[str]:
    """Every reason a candidate policy is NOT a lawful judge policy.

    Applied to the WHOLE candidate after each override is overlaid, never to
    fields one at a time — a policy is a system of related thresholds, and a
    field can be individually plausible while breaking the system (an
    internal_floor below the repair_floor inverts the bands; a lowered
    development_min_overall removes the law's whole point). Empty list =
    lawful."""
    probs: list[str] = []
    for k in _SCORE_FIELDS:
        v = pol.get(k)
        if not _is_num(v) or not (0.0 <= float(v) <= 10.0):
            probs.append(f"{k} must be a finite number in [0, 10], "
                         f"got {v!r}")
    for k in _INT_FIELDS:
        v = pol.get(k)
        if not _is_num(v) or float(v) != int(float(v)):
            probs.append(f"{k} must be an integer, got {v!r}")
    if not probs:
        # Cross-field checks only make sense once every field is a number.
        if not (pol["repair_floor"] <= pol["internal_floor"]
                <= pol["owner_floor"]):
            probs.append("score bands must be monotonic: repair_floor <= "
                         "internal_floor <= owner_floor "
                         f"(got {pol['repair_floor']!r} / "
                         f"{pol['internal_floor']!r} / "
                         f"{pol['owner_floor']!r})")
        if pol["development_min_overall"] > pol["owner_review_min_overall"]:
            probs.append("development_min_overall may not exceed "
                         "owner_review_min_overall")
        if int(pol["max_attempts"]) < 1:
            probs.append(f"max_attempts must be >= 1, "
                         f"got {pol['max_attempts']!r}")
        if int(pol["max_unresolved_major"]) < 0:
            probs.append(f"max_unresolved_major must be >= 0, "
                         f"got {pol['max_unresolved_major']!r}")
        # SAFETY INVARIANTS — not tunables. Raising a floor is a stricter
        # law and always lawful; lowering one below the default is
        # bar-removal and is refused regardless of how it arrived.
        for k in _SAFETY_FLOORS:
            if float(pol[k]) < float(DEFAULT_POLICY[k]):
                probs.append(f"{k}={pol[k]!r} lowers the safety floor "
                             f"below the default {DEFAULT_POLICY[k]!r} — "
                             "floors may only be raised")
        # "Autonomous publishing stays off here regardless of score; only
        # the separately approved launch policy may permit it" (module
        # docstring). That launch policy hands `decide()` its own policy
        # dict — it does not flow through load(), so nothing load() reads
        # may ever flip this on.
        if bool(pol.get("autonomous_publish")):
            probs.append("autonomous_publish cannot be enabled by config or "
                         "environment — only the separately approved launch "
                         "policy may permit it")
    rj = pol.get("required_judges")
    if (not isinstance(rj, list) or not rj
            or not all(isinstance(x, str) and x.strip() for x in rj)):
        probs.append(f"required_judges must be a nonempty list of judge "
                     f"names, got {rj!r}")
    arl = pol.get("auto_reject_labels")
    if not isinstance(arl, list) or not all(isinstance(x, str) for x in arl):
        probs.append(f"auto_reject_labels must be a list of strings, "
                     f"got {arl!r}")
    return probs


def _refuse(source: str, probs: list[str]) -> None:
    """A refused override must be LOUD. Silently keeping defaults is correct
    for the law but wrong for the operator, who thinks their override took —
    the exact green-but-not-doing-what-you-think shape this repo keeps
    re-finding. Printed to stderr so it survives into CI logs."""
    for p in probs:
        print(f"[judge_policy] REFUSED {source}: {p} — keeping the default "
              f"policy for this override", file=sys.stderr)


def load(config_path: Path | None = None) -> dict:
    """The active policy: defaults, overlaid by a ``judge_policy`` block in the
    channel config, overlaid by ``CURIOSITY_JUDGE_*`` env vars.

    Overrides are VALIDATED BEFORE USE (doctor finding 9fe73cb62e3f — a
    nonnumeric max_attempts used to survive this function and crash the
    caller mid-run, and a config could zero the development floor). The
    config block is accepted or refused ATOMICALLY: one invalid field
    refuses the whole block, loudly, and the defaults stand — combining
    "the fields that happened to parse" would ship a policy nobody wrote.
    Each env var is its own override and is validated the same way against
    the policy it would produce. The safety invariants (`_SAFETY_FLOORS`
    may only be raised; ``autonomous_publish`` stays off) hold against
    config and environment alike."""
    pol = dict(DEFAULT_POLICY)
    pol["auto_reject_labels"] = list(DEFAULT_POLICY["auto_reject_labels"])
    pol["required_judges"] = list(DEFAULT_POLICY["required_judges"])
    if config_path is not None:
        try:
            block = (json.loads(Path(config_path).read_text())
                     .get("judge_policy") or {})
        except Exception:  # noqa: BLE001 — an unreadable config never loosens policy
            block = {}
        if block:
            candidate = dict(pol)
            for k, v in block.items():
                if k in candidate:
                    candidate[k] = v
            probs = _problems(candidate)
            if probs:
                _refuse(f"judge_policy block in {config_path}", probs)
            else:
                pol = candidate
    for k in list(pol):
        raw = os.environ.get(_ENV_PREFIX + k.upper())
        if raw is None or raw == "":
            continue
        candidate = dict(pol)
        try:
            if k in _NUMERIC:
                candidate[k] = float(raw)
            elif isinstance(pol[k], bool):
                candidate[k] = raw.strip().lower() in ("1", "true", "yes",
                                                       "on")
            elif isinstance(pol[k], list):
                candidate[k] = [x.strip() for x in raw.split(",")
                                if x.strip()]
            else:
                candidate[k] = raw
        except (TypeError, ValueError):
            _refuse(f"env {_ENV_PREFIX + k.upper()}",
                    [f"{k}={raw!r} is not parseable"])
            continue
        probs = _problems(candidate)
        if probs:
            _refuse(f"env {_ENV_PREFIX + k.upper()}", probs)
            continue
        pol = candidate
    for k in _INT_FIELDS:
        pol[k] = int(pol[k])
    return pol


def band(overall: float | None, policy: dict | None = None) -> str:
    """Which band a professional-quality score falls in. `None` is NOT a band —
    a missing score is missing evidence and is reported as such."""
    pol = policy or load()
    if overall is None:
        return "unscored"
    o = float(overall)
    if o < pol["repair_floor"]:
        return "structural_failure"
    if o < pol["internal_floor"]:
        return "repair_required"
    if o < pol["owner_floor"]:
        return "internal_review"
    return "owner_review"


def _sev_rank(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(str(s).lower())
    except ValueError:
        return len(SEVERITY_ORDER)


def hard_blockers(findings: list[dict], policy: dict | None = None) -> list[dict]:
    """Every finding that blocks advancement on its own. Returned as a list, not
    folded into a score — one unresolved hard objection is not outvoted."""
    pol = policy or load()
    auto = {str(x).upper() for x in pol["auto_reject_labels"]}
    out = []
    for f in findings or []:
        if f.get("resolved"):
            continue
        sev = str(f.get("severity", "")).lower()
        code = str(f.get("defect_code", "")).upper()
        if sev == "blocker" or code in auto:
            out.append(f)
    return sorted(out, key=lambda f: _sev_rank(f.get("severity", "info")))


def unresolved_major(findings: list[dict]) -> list[dict]:
    return [f for f in (findings or [])
            if not f.get("resolved")
            and str(f.get("severity", "")).lower() == "major"]


def dissent(verdicts: dict) -> list[dict]:
    """Judges that disagree about whether the film is acceptable. Preserved as
    an explicit list — a synthesis step may weigh it, but it may never delete
    it, and it is never smoothed into an average."""
    stances = []
    for name, v in (verdicts or {}).items():
        if not isinstance(v, dict) or v.get("status") in ("failed", "abstained"):
            continue
        p = v.get("pass")
        if p is None:
            continue
        stances.append((name, bool(p)))
    if len({p for _, p in stances}) <= 1:
        return []
    return [{"judge": n, "pass": p} for n, p in sorted(stances)]


def decide(combined: dict, policy: dict | None = None) -> dict:
    """The binding decision for one render attempt.

    `combined` is the merged judge view: ``{"overall_10", "personality",
    "findings": [...], "verdicts": {name: {...}}}``.

    Returns ``{"advance", "band", "eligible_for_owner_review",
    "autonomous_publish_allowed", "blockers", "reasons", ...}``. `advance` is
    True only when every condition holds — there is no partial credit and no
    averaging path around a blocker.
    """
    pol = policy or load()
    findings = combined.get("findings") or []
    verdicts = combined.get("verdicts") or {}
    overall = combined.get("overall_10")
    personality = combined.get("personality")

    blockers: list[str] = []

    # 1. required judges must have spoken, AND must have passed. A judge that
    #    failed or abstained is recorded as such and FAILS CLOSED — missing
    #    evidence is not consent. Doctor finding 69a0ad32a52f: this used to
    #    stop at "did the judge speak", so every required judge could return
    #    status "ok" with pass=False (an explicit REJECT) and still advance
    #    as long as overall_10 cleared the score floor and no OTHER judge
    #    disagreed — a unanimous reject is not a disagreement, so dissent()
    #    never caught it either. A required judge's pass is now itself a
    #    blocker: only pass is True (not falsy, not missing, not a string)
    #    counts as a pass.
    for name in pol["required_judges"]:
        v = verdicts.get(name)
        if v is None:
            blockers.append(f"required judge {name!r} produced no verdict — "
                            "FAILS CLOSED")
        elif str(v.get("status", "ok")) in ("failed", "abstained"):
            blockers.append(f"required judge {name!r} {v.get('status')}"
                            f" ({str(v.get('error', ''))[:80]}) — FAILS CLOSED")
        elif v.get("pass") is not True:
            blockers.append(f"required judge {name!r} did not pass "
                            f"(pass={v.get('pass')!r}) — FAILS CLOSED")

    # 2. the professional-quality score is REQUIRED and BINDING.
    if overall is None:
        blockers.append("no professional-quality score (overall_10) — a film "
                        "cannot advance on personality alone")
    else:
        if float(overall) < pol["development_min_overall"]:
            blockers.append(
                f"overall {float(overall):.1f} below the development floor "
                f"{pol['development_min_overall']:.1f} "
                f"({band(overall, pol)})")

    # 3. personality floor (kept, but no longer sufficient on its own).
    if personality is not None and float(personality) < pol["min_personality"]:
        blockers.append(f"personality {float(personality):.1f} below "
                        f"{pol['min_personality']:.1f}")

    # 4. hard objections from ANY judge — never averaged away.
    hb = hard_blockers(findings, pol)
    for f in hb:
        blockers.append(f"hard objection [{f.get('defect_code', '?')}] from "
                        f"{f.get('judge', '?')}: "
                        f"{str(f.get('complaint', ''))[:100]}")

    # 5. too many unresolved major findings.
    maj = unresolved_major(findings)
    if len(maj) > pol["max_unresolved_major"]:
        blockers.append(f"{len(maj)} unresolved major finding(s) > allowed "
                        f"{pol['max_unresolved_major']}")

    # 6. judge disagreement is its own blocker, surfaced not smoothed.
    dis = dissent(verdicts)
    if dis:
        blockers.append("judges disagree and the split is unresolved: "
                        + ", ".join(f"{d['judge']}={'pass' if d['pass'] else 'reject'}"
                                    for d in dis))

    b = band(overall, pol)
    eligible = (not blockers and overall is not None
                and float(overall) >= pol["owner_review_min_overall"])
    return {
        "advance": not blockers,
        "band": b,
        "overall_10": overall,
        "personality": personality,
        "eligible_for_owner_review": eligible,
        # The score NEVER unlocks publishing. Only the separately approved
        # launch policy does, and it is off by default.
        "autonomous_publish_allowed": bool(pol["autonomous_publish"]) and eligible,
        "blockers": blockers,
        "dissent": dis,
        "unresolved_major": len(maj),
        "hard_objections": [f.get("defect_code") for f in hb],
        "policy": {k: pol[k] for k in
                   ("repair_floor", "internal_floor", "owner_floor",
                    "development_min_overall", "owner_review_min_overall",
                    "min_personality", "max_unresolved_major", "max_attempts",
                    "autonomous_publish", "rubric_version")},
    }


if __name__ == "__main__":
    import sys
    pol = load(REPO / "data_learning" / "curiosity.config.json")
    if len(sys.argv) > 1:
        print(json.dumps(decide(json.loads(Path(sys.argv[1]).read_text()), pol),
                         indent=2))
    else:
        print(json.dumps(pol, indent=2))
