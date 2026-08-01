"""judge_loop — the closed creative-improvement loop, shared by every channel.

    render -> judge (all of them) -> persist every response -> rank a repair
    plan -> materially revise -> re-render -> re-judge -> compare -> pass,
    escalate, or abandon.

Before this, the loop repaired mechanical defects it detected itself, asked the
creative judge afterwards, and recorded the answer. The judge was a bouncer at
the exit, not part of the edit. Here the judges' own findings are what drive
the next attempt, and an attempt that does not demonstrably improve escalates
the repair CLASS rather than repeating the same move.

Injected dependencies, so the loop is testable without a 90-minute render:

    render_fn(attempt, plan) -> {"ok": bool, "director_rc": int, "detail": str}
    judges: [JudgeSpec(name, required, fn)]  fn(out, ctx) -> normalized dict

A judge's normalized dict may carry: ``pass``, ``overall_10``, ``personality``,
``findings`` (see repair_planner for the schema), ``confidence``, ``model``,
``provider``. A judge that raises is recorded as ``status="failed"``; one that
returns None is ``status="abstained"``. Either way the response is PERSISTED —
a required judge that could not speak fails the attempt closed.

MATERIAL CHANGE: a re-render only counts as a repair when the artifact hash
actually moves. Re-running a render that produces a byte-identical film is not
a repair, and the comparison says so.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO, REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from data_learning import judge_policy, repair_planner  # noqa: E402
from data_learning.judging_store import JudgingStore  # noqa: E402


@dataclass
class JudgeSpec:
    name: str
    fn: Callable
    required: bool = False
    model: str = ""
    provider: str = ""
    rubric_version: str = ""
    blind: bool = False          # must not see intent / prior scores
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------- judging
def run_judges(out: Path, judges: list[JudgeSpec], store: JudgingStore,
               attempt: int, ctx: dict | None = None) -> dict:
    """Run every judge, persist raw + normalized for each, return
    {name: normalized}. A judge never crashes the loop; its failure becomes
    evidence, and `decide()` fails closed if it was required.

    BLIND judges receive only the context marked shareable — never the
    implementation intent, the expected verdict, or any previous score.
    """
    ctx = dict(ctx or {})
    blind_ctx = {k: v for k, v in ctx.items() if k in ("out", "pkg")}
    results: dict[str, dict] = {}
    for spec in judges:
        payload = blind_ctx if spec.blind else ctx
        try:
            raw = spec.fn(out, payload)
            status = "abstained" if raw is None else "ok"
            norm = dict(raw) if isinstance(raw, dict) else {}
        except Exception as e:  # noqa: BLE001 — a judge failure is evidence
            raw, status, norm = {"error": str(e)[:500]}, "failed", {}
        for f in norm.get("findings", []) or []:
            f.setdefault("judge", spec.name)
        results[spec.name] = store.record(
            attempt, spec.name, raw=raw, normalized=norm, status=status,
            error=(norm.get("error") or (raw or {}).get("error", "")
                   if isinstance(raw, dict) else ""),
            model=spec.model, provider=spec.provider,
            rubric_version=spec.rubric_version,
            confidence=norm.get("confidence"))
        results[spec.name]["required"] = spec.required
    return results


def combine(verdicts: dict) -> dict:
    """Merge independent judges into one view WITHOUT destroying disagreement.

    The professional-quality score is taken from the judge that produces one
    (the taste judge owns `overall_10`); it is never averaged with unrelated
    judges' pass booleans. Every finding from every judge is kept, tagged with
    its author. Dissent is computed, not resolved.
    """
    findings: list[dict] = []
    overall = personality = None
    for name, v in (verdicts or {}).items():
        if not isinstance(v, dict) or v.get("status") in ("failed", "abstained"):
            continue
        for f in v.get("findings", []) or []:
            g = dict(f)
            g.setdefault("judge", name)
            findings.append(g)
        if v.get("overall_10") is not None:
            o = float(v["overall_10"])
            overall = o if overall is None else min(overall, o)   # never round UP
        if v.get("personality") is not None:
            p = float(v["personality"])
            personality = p if personality is None else min(personality, p)
    return {
        "overall_10": overall,
        "personality": personality,
        "findings": findings,
        "verdicts": verdicts,
        "dissent": judge_policy.dissent(verdicts),
        "n_findings": len(findings),
    }


# ------------------------------------------------------------------ comparison
def _finding_key(f: dict) -> str:
    return (f"{str(f.get('defect_code', '?')).upper()}"
            f"@{f.get('beat', f.get('target', f.get('time_range', 'film')))}")


def compare(prev: dict | None, cur: dict, *, prev_hash: str | None = None,
            cur_hash: str | None = None, targeted: list[str] | None = None) -> dict:
    """Movement between two attempts. This is what makes "it got better" a
    measurement rather than an opinion."""
    if not prev:
        return {"first_attempt": True, "materially_different": True,
                "overall_delta": None, "personality_delta": None,
                "fixed": [], "introduced": [],
                "targeted_defects_fixed": [], "targeted_defects_remaining": [],
                "stalled": False, "regressed": False}
    pk = {_finding_key(f) for f in prev.get("findings", [])}
    ck = {_finding_key(f) for f in cur.get("findings", [])}
    po, co = prev.get("overall_10"), cur.get("overall_10")
    pp, cp = prev.get("personality"), cur.get("personality")
    d_overall = (None if po is None or co is None else round(float(co) - float(po), 2))
    d_personality = (None if pp is None or cp is None
                     else round(float(cp) - float(pp), 2))
    targeted = [t.upper() for t in (targeted or [])]
    tgt_fixed = [k for k in pk - ck if k.split("@")[0] in targeted]
    tgt_left = [k for k in pk & ck if k.split("@")[0] in targeted]
    material = bool(prev_hash and cur_hash and prev_hash != cur_hash)
    # A stall is: the film did not materially change, OR it changed but the
    # score did not improve and the targeted defects are all still there.
    stalled = (not material) or (
        (d_overall is None or d_overall <= 0) and not tgt_fixed)
    return {
        "first_attempt": False,
        "materially_different": material,
        "prev_mp4_sha256": prev_hash, "mp4_sha256": cur_hash,
        "overall_prev": po, "overall_now": co, "overall_delta": d_overall,
        "personality_prev": pp, "personality_now": cp,
        "personality_delta": d_personality,
        "fixed": sorted(pk - ck),
        "introduced": sorted(ck - pk),
        "persisting": sorted(pk & ck),
        "targeted_defects_fixed": sorted(tgt_fixed),
        "targeted_defects_remaining": sorted(tgt_left),
        "stalled": stalled,
        "regressed": bool(d_overall is not None and d_overall < 0)
                     or bool(ck - pk and (d_overall or 0) <= 0),
    }


ORDER = ["local", "scene", "structural"]


def next_escalation(current: str, comparison: dict, plan_repeated: bool) -> str:
    """Broaden the repair class when the current one is not working. A stalled
    score, a regression, or the same plan twice all mean 'stop doing this kind
    of repair', not 'do it again'."""
    if comparison.get("first_attempt"):
        return current
    if comparison.get("stalled") or comparison.get("regressed") or plan_repeated:
        i = ORDER.index(current) if current in ORDER else 0
        return ORDER[min(i + 1, len(ORDER) - 1)]
    return current


def escalation_for(attempt_index: int, carried: str) -> str:
    """The repair class an attempt runs at.

    The ladder is indexed by ATTEMPT — 1 local, 2 scene, 3 structural — so each
    attempt is meaningfully broader than the last even when the previous one
    made some progress. A stall pushes it further still (`carried`), never
    back: the class only ever widens.
    """
    base = repair_planner.repair_class(attempt_index)
    return ORDER[max(ORDER.index(base),
                     ORDER.index(carried) if carried in ORDER else 0)]


# ------------------------------------------------------------------- the loop
def run(out: Path, *, render_fn: Callable, judges: list[JudgeSpec],
        policy: dict | None = None, story_path: Path | None = None,
        slug: str = "", ctx: dict | None = None,
        max_attempts: int | None = None,
        apply_plan_fn: Callable | None = None) -> dict:
    """Drive render -> judge -> plan -> revise -> re-render until the policy is
    satisfied, the ladder is exhausted, or the attempt bound is reached.

    Returns the final summary (also written to
    ``<out>_pkg/judging/final_summary.json``). Statuses:
      ``pass``       policy satisfied — advance to the publish gate
      ``quarantine`` bounded attempts spent, still below the bar
      ``abandoned``  structural repair also failed: the creative approach is
                     rejected, not endlessly polished
    """
    pol = policy or judge_policy.load(
        REPO / "data_learning" / "curiosity.config.json")
    cap = int(max_attempts if max_attempts is not None else pol["max_attempts"])
    store = JudgingStore(out)
    escalation = "local"
    prev_combined: dict | None = None
    prev_hash: str | None = None
    prev_sig: str | None = None
    attempts_log: list[dict] = []
    status = "quarantine"
    plan_doc: dict = {"tasks": []}

    for i in range(1, cap + 1):
        # The class WIDENS by attempt (1 local, 2 scene, 3 structural) and a
        # stall carried from the previous round can widen it further — never
        # narrow it. Each attempt is therefore meaningfully broader than the
        # last instead of retrying the same class until the bound runs out.
        escalation = escalation_for(i, escalation)
        attempt = store.open_attempt(policy=pol, escalation=escalation,
                                     story_path=story_path)
        # ---- render (attempt 1 renders the first cut; later attempts revise)
        if i > 1 and apply_plan_fn is not None:
            try:
                apply_plan_fn(plan_doc, escalation)
            except Exception as e:  # noqa: BLE001 — a failed revision is evidence
                store.write(attempt, "revision_error", {"error": str(e)[:500]})
        r = render_fn(attempt, plan_doc if i > 1 else None) or {}
        store.write(attempt, "render", r)
        if not r.get("ok", True):
            store.record(attempt, "render", raw=r, status="failed",
                         error=str(r.get("detail", ""))[:400])

        # ---- judge everything, persist everything
        verdicts = run_judges(out, judges, store, attempt, ctx=ctx)
        combined = combine(verdicts)
        decision = judge_policy.decide(combined, pol)
        combined["decision"] = decision
        combined["attempt"] = attempt
        combined["escalation"] = escalation
        store.write(attempt, "combined_verdict", combined)

        cur_hash = (store.read(attempt, "manifest") or {}).get("mp4_sha256")
        targeted = [t["defect_code"] for t in plan_doc.get("tasks", [])]
        cmp_doc = compare(prev_combined, combined, prev_hash=prev_hash,
                          cur_hash=cur_hash, targeted=targeted)
        store.write(attempt, "comparison", cmp_doc)

        # ---- plan the next repair from the judges' ACTUAL findings
        plan_doc = repair_planner.plan(combined["findings"], attempt=i,
                                       escalation=escalation)
        sig = repair_planner.signature(plan_doc)
        plan_doc["signature"] = sig
        plan_doc["repeats_previous_plan"] = bool(prev_sig and sig == prev_sig)
        store.write(attempt, "repair_plan", plan_doc)

        attempts_log.append({
            "attempt": attempt, "escalation": escalation,
            "director_rc": r.get("director_rc"),
            "overall_10": combined["overall_10"],
            "personality": combined["personality"],
            "band": decision["band"],
            "advance": decision["advance"],
            "blockers": decision["blockers"],
            "n_findings": combined["n_findings"],
            "plan_signature": sig, "n_tasks": plan_doc["n_tasks"],
            "comparison": cmp_doc,
        })

        if decision["advance"]:
            status = "pass"
            break

        # A STRUCTURAL attempt that still fails ends the approach. The creative
        # premise is rejected rather than polished forever — "do not endlessly
        # move labels around on a fundamentally mediocre video".
        if escalation == "structural":
            status = "abandoned"
            break
        escalation = next_escalation(escalation, cmp_doc,
                                     plan_doc["repeats_previous_plan"])
        prev_combined, prev_hash, prev_sig = combined, cur_hash, sig

    last = attempts_log[-1] if attempts_log else {}
    summary = {
        "slug": slug,
        "out": str(out),
        "status": status,
        "attempts": len(attempts_log),
        "max_attempts": cap,
        "final_overall_10": last.get("overall_10"),
        "final_personality": last.get("personality"),
        "final_band": last.get("band"),
        "unresolved_blockers": last.get("blockers", []),
        "score_progression": [a.get("overall_10") for a in attempts_log],
        "escalation_progression": [a.get("escalation") for a in attempts_log],
        "attempts_detail": attempts_log,
        "eligible_for_owner_review": bool(
            status == "pass" and last.get("overall_10") is not None
            and float(last["overall_10"]) >= pol["owner_review_min_overall"]),
        "autonomous_publish_allowed": False if not pol["autonomous_publish"] else None,
        "policy": pol,
        "reason": {
            "pass": "policy satisfied",
            "quarantine": "attempt bound reached below the quality bar",
            "abandoned": "structural repair failed — creative approach rejected",
        }[status],
    }
    store.write_final_summary(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(judge_policy.load(
        REPO / "data_learning" / "curiosity.config.json"), indent=2))
