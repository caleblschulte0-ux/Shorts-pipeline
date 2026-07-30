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
  - judge DISAGREEMENT is surfaced as its own blocker rather than resolved by
    silently taking the kinder verdict.
  - autonomous publishing stays off here regardless of score; only the
    separately approved launch policy may permit it.

Nothing in this module knows about any story, slug, title or topic — the
policy is the same law for every film.
"""
from __future__ import annotations

import json
import os
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

# Severities, most serious first. `blocker` can never be averaged away.
SEVERITY_ORDER = ("blocker", "major", "minor", "info")


def load(config_path: Path | None = None) -> dict:
    """The active policy: defaults, overlaid by a ``judge_policy`` block in the
    channel config, overlaid by ``CURIOSITY_JUDGE_*`` env vars. A malformed
    override is ignored rather than allowed to silently loosen the law."""
    pol = dict(DEFAULT_POLICY)
    pol["auto_reject_labels"] = list(DEFAULT_POLICY["auto_reject_labels"])
    pol["required_judges"] = list(DEFAULT_POLICY["required_judges"])
    if config_path is not None:
        try:
            block = (json.loads(Path(config_path).read_text())
                     .get("judge_policy") or {})
            for k, v in block.items():
                if k in pol:
                    pol[k] = v
        except Exception:  # noqa: BLE001 — an unreadable config never loosens policy
            pass
    for k in list(pol):
        raw = os.environ.get(_ENV_PREFIX + k.upper())
        if raw is None or raw == "":
            continue
        try:
            if k in _NUMERIC:
                pol[k] = float(raw)
            elif isinstance(pol[k], bool):
                pol[k] = raw.strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(pol[k], list):
                pol[k] = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                pol[k] = raw
        except (TypeError, ValueError):
            continue
    for k in ("max_unresolved_major", "max_attempts"):
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

    # 1. required judges must have spoken. A judge that failed or abstained is
    #    recorded as such and FAILS CLOSED — missing evidence is not consent.
    for name in pol["required_judges"]:
        v = verdicts.get(name)
        if v is None:
            blockers.append(f"required judge {name!r} produced no verdict — "
                            "FAILS CLOSED")
        elif str(v.get("status", "ok")) in ("failed", "abstained"):
            blockers.append(f"required judge {name!r} {v.get('status')}"
                            f" ({str(v.get('error', ''))[:80]}) — FAILS CLOSED")

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
