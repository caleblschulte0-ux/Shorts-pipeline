#!/usr/bin/env python3
"""THE PRODUCER — the single canonical path from a beat story to a publishable
(or quarantined) film. This replaces the split the audit found — "the pro engine
makes previews, the legacy engine publishes" — with ONE enforced pipeline that
every mode (canary / schedule / all / auto / dry-run) goes through:

    data_learning/pro_stories/<slug>.beats.json
      -> no_dull_beats.run   (render via pro_render + deterministic director gates
                              + auto-repair + re-render; renderer already emits the
                              publishing sidecars + a fallback verdict)
      -> fallback verdict     (pro_render _pkg/fallbacks.json: 'unacceptable' quarantines)
      -> publishing package    (meta.json / .srt / .jpg present, or fail closed)
      -> VISION taste verdict  (VISUAL_STANDARD / TASTE_JUDGE, blind panel)
      -> PASS (package ready) or QUARANTINE (reasons)

The vision verdict is a blind-panel call the orchestrator writes to
``<out>_pkg/verdict.json`` as ``{"pass": bool, "reject_labels": [...], ...}``.
When it is ABSENT the producer FAILS CLOSED — a film is never published unjudged
(audit: "a missing judge or failed package must fail closed"). In the interactive
session the orchestrator (this agent) renders the verdict; in headless CI nothing
publishes until a verdict exists, which is exactly the intended safety.

    python3 scripts/produce.py <slug> <out.mp4> [--rounds N]
    exit 0 = PASS (ready to publish), 5 = QUARANTINE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PRO_STORIES = REPO / "data_learning" / "pro_stories"
_RC = {3: "stale span — the video holds one idea too long (novelty)",
       4: "data-cards over budget — reads as an infographic reel"}


def resolve_story(slug: str) -> Path:
    for cand in (PRO_STORIES / f"{slug}.beats.json", PRO_STORIES / f"{slug}.json"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"no pro story for slug {slug!r} under {PRO_STORIES}")


def _read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _provenance_gap(story: dict, out: Path | None = None) -> str | None:
    """Flagship factual-provenance gate (Phase 9 / audit #11). A story that
    OPTS IN with top-level ``"require_provenance": true`` runs the full FACTS
    GATE (scripts/facts_gate.py): claim-registry schema validation + numeric-
    narration coverage. Any failure blocks publish; the machine-readable
    verdict is written to ``<out>.facts-report.json``. Scoped to opt-in
    stories so non-financial stories (speeds, scales) are unaffected."""
    if not story or not story.get("require_provenance"):
        return None
    slug = story.get("slug")
    if not slug:
        return "require_provenance set but story has no slug for the facts gate"
    try:
        import facts_gate
        report = facts_gate.evaluate(slug)
        if out is not None:
            dest = out.with_suffix(".facts-report.json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(report, indent=2) + "\n")
        if not report.get("pass"):
            heads = "; ".join(report.get("errors", [])[:3])
            more = len(report.get("errors", [])) - 3
            return ("FACTS GATE blocked: " + heads
                    + (f" (+{more} more)" if more > 0 else ""))
        return None
    except Exception as e:  # noqa: BLE001 — a gate that cannot run FAILS CLOSED
        return f"facts gate could not run ({str(e)[:80]}) — refusing to publish unverified claims"


def evaluate(out: Path, director_rc: int, story: dict | None = None) -> dict:
    """Given a finished render at `out` and the director's return code, decide
    PASS vs QUARANTINE from the packaged evidence (no rendering here — pure,
    unit-testable). `story` (the loaded beats) enables the opt-in provenance
    gate; omitted in unit tests that only exercise the package decision."""
    pkg = out.with_name(out.stem + "_pkg")
    reasons: list[str] = []

    if director_rc != 0:
        reasons.append("director gates failed "
                       f"(rc={director_rc}: {_RC.get(director_rc, 'reject')})")

    prov = _provenance_gap(story or {}, out=out)
    if prov:
        reasons.append(prov)

    fb = _read_json(pkg / "fallbacks.json") or {}
    if fb.get("verdict") == "unacceptable":
        bad = [f.get("kind") for f in fb.get("fallbacks", [])
               if f.get("severity") == "unacceptable"]
        reasons.append(f"unacceptable render fallback: {bad}")

    for side, why in ((out.with_suffix(".meta.json"), "meta.json"),
                      (out.with_suffix(".srt"), "captions .srt"),
                      (out.with_suffix(".jpg"), "thumbnail .jpg")):
        if not side.exists():
            reasons.append(f"missing publishing sidecar: {why}")

    verdict = _read_json(pkg / "verdict.json")
    # A verdict is only valid for the render it judged. PRIMARY check
    # (PR#173 adoption A): the verdict carries the sha256 of the exact mp4 it
    # judged (judge_verdict.write stamps it); a mismatch — replaced video,
    # copied verdict, hand-edited binding — FAILS CLOSED. SECONDARY
    # (belt-and-braces): the old mtime rule still applies, so even a
    # hypothetical hash collision cannot promote an older judgment.
    vpath = pkg / "verdict.json"
    if verdict is not None and out.exists():
        bound = verdict.get("mp4_sha256")
        if bound:
            import artifact_identity
            actual = artifact_identity.sha256_file(out)
            if bound != actual:
                reasons.append("vision verdict is bound to a DIFFERENT render "
                               f"(verdict mp4_sha256 {bound[:12]}… != current "
                               f"{actual[:12]}…) — FAILS CLOSED; re-judge")
                verdict = None
        else:
            reasons.append("vision verdict carries no mp4_sha256 binding — "
                           "FAILS CLOSED; re-judge with the current "
                           "judge_verdict.py so the verdict binds to the film")
            verdict = None
    if verdict is not None and out.exists() and \
            vpath.stat().st_mtime < out.stat().st_mtime:
        reasons.append("stale vision verdict (pkg/verdict.json predates this "
                       "render) — FAILS CLOSED; re-judge the current blind package")
        verdict = None
    elif verdict is None:
        if not any("verdict" in r for r in reasons):
            reasons.append("no vision taste verdict (pkg/verdict.json) — FAILS "
                           "CLOSED; judge the blind package before publishing")
    # THE BINDING QUALITY LAW (data_learning/judge_policy.py). A film no longer
    # advances because it dodged the reject vocabulary and scraped personality
    # 3 — the professional-quality score (overall_10) is REQUIRED and BINDING,
    # a hard objection from any judge is never averaged away, and unresolved
    # judge disagreement blocks on its own.
    policy_decision = None
    if verdict is not None:
        from data_learning import judge_policy, judges as judge_adapters
        pol = judge_policy.load(REPO / "data_learning" / "curiosity.config.json")
        taste_norm = judge_adapters.taste(out) or {}
        combined = {
            "overall_10": taste_norm.get("overall_10"),
            "personality": taste_norm.get("personality"),
            "findings": taste_norm.get("findings", []),
            # produce.evaluate is the single-shot gate: the taste judge is the
            # verdict on record here, and the technical/factual conditions it
            # would otherwise duplicate are already enforced above as reasons.
            "verdicts": {"taste": {**taste_norm, "status": "ok"},
                         "technical": {"status": "ok", "pass": True},
                         "factual": {"status": "ok", "pass": True}},
        }
        policy_decision = judge_policy.decide(combined, pol)
        if not policy_decision["advance"]:
            reasons.extend(policy_decision["blockers"])

    status = "pass" if not reasons else "quarantine"
    result = {"out": str(out), "status": status, "reasons": reasons,
              "director_rc": director_rc, "pkg": str(pkg),
              "fallback_verdict": fb.get("verdict", "unknown")}
    if policy_decision is not None:
        result["judge_policy"] = policy_decision
    if pkg.exists():
        (pkg / "produce_report.json").write_text(json.dumps(result, indent=2))
    return result


def record_judging(slug: str, out: Path, story: dict | None = None,
                   director_rc: int | None = None, deep: bool = False) -> dict:
    """Run the full judge set over a finished render and PERSIST every response
    under ``<out>_pkg/judging/attempt_NN/`` — raw and normalized, including
    failures and abstentions — then write the combined verdict, the ranked
    repair plan, the comparison against the previous attempt, and the human
    report. Returns the attempt's headline numbers.

    This is what makes a green workflow inspectable: the owner can read every
    judge's complete output, the repair it asked for, and the movement, without
    any access to the runner."""
    from data_learning import judge_loop, judge_policy, judges as judge_adapters
    from data_learning import repair_planner
    from data_learning.judging_store import JudgingStore

    pol = judge_policy.load(REPO / "data_learning" / "curiosity.config.json")
    store = JudgingStore(out)
    prev_n = store.existing_attempts()
    prev = store.read(prev_n[-1], "combined_verdict") if prev_n else None
    prev_hash = ((store.read(prev_n[-1], "manifest") or {}).get("mp4_sha256")
                 if prev_n else None)
    prev_plan = store.read(prev_n[-1], "repair_plan") if prev_n else None

    attempt = store.open_attempt(policy=pol,
                                 escalation=repair_planner.repair_class(
                                     len(prev_n) + 1))
    ctx = {"story": story or {}, "out": str(out), "pkg": str(out.with_name(out.stem + "_pkg"))}
    verdicts = judge_loop.run_judges(out, judge_adapters.default_specs(deep=deep),
                                     store, attempt, ctx=ctx)
    combined = judge_loop.combine(verdicts)
    # THE DIRECTOR IS A JUDGE TOO. Its gates produce the most specific diagnosis
    # in the pipeline — timecoded stale spans, per-beat dullness with the right
    # repair kind, the hook verdict — and none of it used to reach the planner,
    # which is why the auto-repairer idled through five production runs on an
    # empty task list while the director had seven complaints on screen.
    try:
        dj = json.loads((out.with_name(out.stem + "_pkg") /
                         "director_findings.json").read_text())
        df = dj.get("findings") or []
        if df:
            combined["findings"] = list(combined.get("findings") or []) + df
            combined["n_findings"] = len(combined["findings"])
            print(f"[produce] {slug}: +{len(df)} director finding(s) into the "
                  "repair plan")
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001 — a bad sidecar must not lose the judging
        print(f"[produce] {slug}: director findings unreadable ({str(e)[:80]})",
              file=sys.stderr)
    combined["decision"] = judge_policy.decide(combined, pol)
    combined["attempt"] = attempt
    combined["director_rc"] = director_rc
    store.write(attempt, "combined_verdict", combined)

    cur_hash = (store.read(attempt, "manifest") or {}).get("mp4_sha256")
    targeted = [t["defect_code"] for t in (prev_plan or {}).get("tasks", [])]
    cmp_doc = judge_loop.compare(prev, combined, prev_hash=prev_hash,
                                 cur_hash=cur_hash, targeted=targeted)
    store.write(attempt, "comparison", cmp_doc)

    plan = repair_planner.plan(combined["findings"], attempt=attempt)
    plan["signature"] = repair_planner.signature(plan)
    plan["repeats_previous_plan"] = bool(
        prev_plan and prev_plan.get("signature") == plan["signature"])
    store.write(attempt, "repair_plan", plan)

    escalation = judge_loop.next_escalation(
        repair_planner.repair_class(attempt), cmp_doc,
        plan["repeats_previous_plan"])
    decision = combined["decision"]
    status = ("pass" if decision["advance"]
              else ("abandoned" if attempt >= pol["max_attempts"] else "quarantine"))
    store.write_final_summary({
        "slug": slug, "out": str(out), "status": status,
        "attempts": attempt, "max_attempts": pol["max_attempts"],
        "final_overall_10": combined["overall_10"],
        "final_personality": combined["personality"],
        "final_band": decision["band"],
        "unresolved_blockers": decision["blockers"],
        "score_progression": [
            (store.read(n, "combined_verdict") or {}).get("overall_10")
            for n in store.existing_attempts()],
        "escalation_progression": [
            (store.read(n, "manifest") or {}).get("escalation")
            for n in store.existing_attempts()],
        "next_escalation": escalation,
        "eligible_for_owner_review": decision["eligible_for_owner_review"],
        "autonomous_publish_allowed": decision["autonomous_publish_allowed"],
        "policy": decision["policy"],
        "reason": ("policy satisfied" if status == "pass" else
                   "attempt bound reached below the quality bar"
                   if status == "abandoned" else
                   "below the quality bar — repair plan written"),
    })
    try:
        import judge_report
        judge_report.write_all(out, step_summary=True)
    except Exception as e:  # noqa: BLE001 — reporting never blocks a render
        print(f"[produce] judge report skipped ({str(e)[:100]})", file=sys.stderr)
    return {"attempt": attempt, "overall_10": combined["overall_10"],
            "personality": combined["personality"],
            "band": decision["band"], "advance": decision["advance"],
            "n_findings": combined["n_findings"],
            "n_repair_tasks": plan["n_tasks"],
            "next_escalation": escalation,
            "blockers": decision["blockers"],
            "judging_dir": str(store.root)}


def _try_resume(slug: str, out: Path, story_path: Path) -> int | None:
    """RESUME (PR#173 adoption D): if the on-disk package was rendered from
    EXACTLY this story content and nothing in it has changed since — proven by
    recomputing every hash in pkg/manifest.json, never by mtimes — reuse the
    recorded director verdict instead of re-rendering for an hour. Any doubt
    (no manifest, missing rc, any changed artifact) returns None and the full
    render runs. This is what makes a container death mid-evaluate cheap."""
    import artifact_identity
    import run_ledger
    m = artifact_identity.load_manifest(out)
    if not m or m.get("director_rc") is None:
        return None
    ok, reasons = artifact_identity.verify_manifest(out, story_path=story_path)
    if not ok:
        run_ledger.append("resume_miss", slug, {"reasons": reasons[:4]})
        print(f"[produce] {slug}: resume refused ({'; '.join(reasons[:2])}) — "
              "full render")
        return None
    rc = int(m["director_rc"])
    run_ledger.append("resume_hit", slug, {"director_rc": rc,
                      "manifest_sha256": m.get("manifest_sha256")})
    print(f"[produce] {slug}: RESUME — package identity verified against the "
          f"manifest (director rc={rc}); skipping re-render")
    return rc


def _mp4_hash(out: Path) -> str | None:
    """The rendered film's identity, for the circuit breaker. None when it can
    not be computed — an unknown hash must never look like an unchanged one."""
    try:
        import artifact_identity
        return artifact_identity.sha256_file(out) if out.exists() else None
    except Exception:  # noqa: BLE001 — identity is diagnostic here, never fatal
        return None


def _reconcile_verdict(slug: str, result: dict) -> None:
    """ONE verdict system. Mutates `result` in place.

    evaluate() is the legacy gate; the judge policy is the binding quality
    verdict. Attaching the policy decision as data while RETURNING the legacy
    status is split-brain — the repairer acted on the new decision while the
    stopping condition and the batch layer read the old one, so a film the
    policy would advance could still be reported quarantined, and vice versa.

    The two are ANDed, never swapped. The policy may VETO a pass but never grant
    one: evaluate() holds the fail-closed conditions the policy does not model —
    a render that died, a missing narration track, an unresolved licence — and a
    quality score must not publish a film that is broken."""
    j = result.get("judging") or {}
    adv = j.get("advance")
    if adv is None:
        return                      # no judging record: never invent a verdict
    blockers = list(j.get("blockers") or [])
    result["legacy_status"] = result.get("status")
    if not adv and result.get("status") == "pass":
        result["status"] = "quarantine"
        result["reasons"] = list(result.get("reasons") or []) + [
            "judge policy withholds advance"
            + (f": {'; '.join(blockers[:3])}" if blockers else "")]
        print(f"[produce] {slug}: legacy gate passed but the judge policy "
              "withholds advance — quarantined on the binding verdict")
    elif adv and result.get("status") != "pass":
        print(f"[produce] {slug}: judge policy would advance, but evaluate() "
              f"still blocks: {'; '.join(result.get('reasons', [])[:2])}")


def _beatmap(out: Path) -> dict | None:
    """The rendered film's beat -> time map, for resolving span targets."""
    f = Path(out).with_name(Path(out).stem + "_pkg") / "beatmap.json"
    try:
        return json.loads(f.read_text())
    except Exception:  # noqa: BLE001 — no beatmap just means span targets miss
        return None


def _round_signature(result: dict) -> tuple:
    """What this round COMPLAINED and what it SCORED — the pair the circuit
    breaker compares across renders."""
    fs = findings_of(result)
    return (tuple(sorted(f"{f.get('defect_code','')}@{f.get('target','')}"
                         for f in fs)),
            str((result.get("judging") or {}).get("overall_10")))


def _judge_suspect(prev_sig, cur_sig, prev_hash, cur_hash) -> bool:
    """True when the FILM changed but the verdict did not move at all.

    That combination indicts the judge's INPUT, not the film. It is exactly what
    four consecutive renders looked like while the hook gate was grading only
    the text before the first period. Requires two known, DIFFERENT hashes — an
    unknown hash must never be mistaken for a changed one, and an unchanged
    render repeating itself is the film's fault, not the judge's."""
    return bool(prev_sig is not None and cur_sig == prev_sig
                and prev_hash and cur_hash and prev_hash != cur_hash)


def findings_of(result: dict) -> list[dict]:
    """The complaints behind a round's verdict, from the judging record if it
    ran and the produce reasons otherwise, so the breaker can compare rounds
    even when the judges abstained."""
    j = result.get("judging") or {}
    if isinstance(j.get("findings"), list):
        return j["findings"]
    return [{"defect_code": r[:60], "target": "film"}
            for r in (result.get("reasons") or [])]


def _repair_attempts() -> int:
    """How many render->judge->repair rounds one produce() call may spend.

    Bounded because each round is a FULL re-render: a feature-length story can
    run over an hour, and a CI job that exceeds its wall clock delivers nothing
    at all — an unbounded loop would turn a quarantine (which still ships an
    inspectable package) into a timeout (which ships nothing)."""
    try:
        return max(1, int(os.environ.get("CURIOSITY_REPAIR_ATTEMPTS", "2")))
    except ValueError:
        return 2


def produce(slug: str, out: Path, rounds: int = 2, fresh: bool = False,
            attempts: int | None = None) -> dict:
    """Render -> judge -> REPAIR -> re-render until the policy is satisfied or the
    attempt budget is spent. Returns the final evaluate() result with the slug
    attached. `fresh=True` forces a re-render even when the on-disk package
    proves identical (resume path).

    THE CLOSED LOOP. Every attempt already produced a ranked repair plan from the
    judges' real findings; until now nothing applied it, so a second render
    re-rendered the identical story and the plan was a document rather than a
    fix. Here the plan is applied to the beats (auto_repair), the revised story is
    written into the package as evidence, and THAT is what re-renders.

    The escalation class widens per attempt (local -> scene -> structural), so
    each round is broader than the last rather than the same move retried. A
    round that applies NOTHING stops the loop immediately: re-rendering unchanged
    input to get an unchanged verdict is the one thing this loop must never do.
    """
    import no_dull_beats
    import run_ledger
    from data_learning import auto_repair, repair_planner
    from data_learning.judging_store import JudgingStore
    story_path = resolve_story(slug)
    story = json.loads(story_path.read_text())
    budget = _repair_attempts() if attempts is None else max(1, int(attempts))
    run_ledger.append("run_started", slug,
                      {"out": str(out), "rounds": rounds, "fresh": fresh,
                       "repair_attempts": budget})
    if not fresh:
        rc = _try_resume(slug, out, story_path)
        if rc is not None:
            result = evaluate(out, rc, story=story)
            result["slug"] = slug
            result["resumed"] = True
            run_ledger.append("evaluated", slug,
                              {"status": result["status"], "resumed": True,
                               "n_reasons": len(result["reasons"])})
            tag = "PASS" if result["status"] == "pass" else "QUARANTINE"
            print(f"[produce] {slug}: {tag} (resumed)"
                  + ("" if result["status"] == "pass"
                     else " — " + "; ".join(result["reasons"])))
            return result

    pkg = out.with_name(out.stem + "_pkg")
    repair_log: list[dict] = []
    result: dict = {}
    prev_sig: tuple | None = None
    prev_hash: str | None = None
    for attempt_i in range(1, budget + 1):
        if attempt_i > 1:
            print(f"[produce] {slug}: === repair attempt {attempt_i}/{budget} "
                  f"— re-rendering the REVISED story ({story_path.name}) ===")
        result = _render_and_judge(slug, out, story_path, story, rounds)
        if result.get("status") == "pass" or attempt_i == budget:
            break

        # JUDGE-MALFUNCTION CIRCUIT BREAKER. If the FILM materially changed but
        # the complaint and the score came back byte-identical, the suspect is
        # the judge's input, not the film. That is not hypothetical: the hook
        # gate graded `narration.split(".")[0]` and so returned the same verdict
        # and the same score for four consecutive ~2-hour renders, including one
        # whose opening had been rewritten specifically to clear it. This check
        # would have caught it on the second attempt instead of the fourth.
        sig = _round_signature(result)
        cur_hash = _mp4_hash(out)
        if _judge_suspect(prev_sig, sig, prev_hash, cur_hash):
            msg = ("judge malfunction suspected: the render CHANGED "
                   f"({prev_hash[:12]}… -> {cur_hash[:12]}…) but every complaint "
                   "and the score are identical — inspect what the judge is "
                   "being given before spending another render")
            print(f"[produce] {slug}: {msg}", file=sys.stderr)
            result.setdefault("reasons", []).append(msg)
            result["judge_malfunction_suspected"] = True
            break
        prev_sig, prev_hash = sig, cur_hash

        # ---- apply the judges' ranked plan to the beats, then re-render THAT.
        # The FINDINGS are the source of truth, not the stored plan: a plan is
        # only ever built for one repair class, and the class decides which
        # findings become tasks at all (the rest are held in `deferred`).
        findings: list[dict] = []
        try:
            store = JudgingStore(out)
            seen = store.existing_attempts()
            if seen:
                findings = ((store.read(seen[-1], "combined_verdict") or {})
                            .get("findings") or [])
        except Exception as e:  # noqa: BLE001 — no findings means no repair, not a crash
            print(f"[produce] {slug}: could not read the judges' findings ({e})",
                  file=sys.stderr)

        # THE LADDER MUST NOT BECOME A DEAD END. The class starts narrow so the
        # cheap repairs are tried first, but attempt 1 opens at `local` while the
        # commonest creative defect (CARDS_OVER_BUDGET) is not even planned as a
        # task until `scene`. Stopping there would mean the defect the judges
        # raise most often is the one repair that never runs. The ladder exists
        # to ORDER repairs, not to refuse one the judges demonstrably need — so
        # when a class yields nothing and findings are still held back, re-plan
        # one step wider. This costs no render: only the final revision renders.
        ladder = ["local", "scene", "structural"]
        first = repair_planner.repair_class(attempt_i)
        start = ladder.index(first) if first in ladder else 0
        escalation, plan, revised, journal, applied = first, {}, story, [], []
        for step in range(start, len(ladder)):
            escalation = ladder[step]
            plan = repair_planner.plan(findings, attempt=attempt_i,
                                       escalation=escalation)
            # The beatmap is how a span defect ("112.0-119.5s") becomes a beat
            # the healer can edit. Without it every director finding — which is
            # ALWAYS a time range, because the director watches a clock, not a
            # beat list — is dropped as unaddressable.
            revised, journal = auto_repair.apply(plan, story,
                                                 escalation=escalation,
                                                 beatmap=_beatmap(out))
            applied = [j for j in journal if j.get("applied")]
            if applied:
                break
            held = len(plan.get("deferred", [])) + len(
                [j for j in journal if "repair class" in str(j.get("why", ""))])
            if not held or step + 1 >= len(ladder):
                break          # nothing left to widen INTO — the findings are spent
            print(f"[produce] {slug}: the {escalation} class repaired nothing "
                  f"and {held} finding(s) are held for a wider class — "
                  f"re-planning at {ladder[step + 1]}")
        repair_log.append({"attempt": attempt_i, "escalation": escalation,
                           "n_findings": len(findings),
                           "n_tasks": len(plan.get("tasks", [])),
                           "n_applied": len(applied), "journal": journal})
        if not applied:
            print(f"[produce] {slug}: repair applied NOTHING at the "
                  f"{escalation} class — stopping rather than re-rendering an "
                  "identical film for an identical verdict")
            result.setdefault("reasons", []).append(
                f"repair loop stopped after attempt {attempt_i}: no automated "
                f"repair applied at the {escalation} class")
            break
        print(f"[produce] {slug}: {auto_repair.summarize(journal)}")
        # the revised beats ARE the next render's input, and they ship in the
        # package so a reviewer can read exactly what the loop changed and why
        rev_dir = pkg / "revised"
        rev_dir.mkdir(parents=True, exist_ok=True)
        story_path = rev_dir / f"attempt_{attempt_i + 1:02d}.beats.json"
        story_path.write_text(json.dumps(revised, indent=2) + "\n")
        story = revised
        run_ledger.append("repair_applied", slug,
                          {"attempt": attempt_i, "escalation": escalation,
                           "n_applied": len(applied),
                           "story": str(story_path)})

    if repair_log:
        result["repairs"] = repair_log
        try:
            pkg.mkdir(parents=True, exist_ok=True)
            (pkg / "repair_log.json").write_text(
                json.dumps(repair_log, indent=2) + "\n")
        except Exception as e:  # noqa: BLE001 — evidence only, never fatal
            print(f"[produce] {slug}: repair log not written ({e})",
                  file=sys.stderr)
    run_ledger.append("evaluated", slug,
                      {"status": result.get("status"),
                       "n_reasons": len(result.get("reasons", [])),
                       "repair_rounds": len(repair_log)})
    if result.get("status") == "pass":
        print(f"[produce] {slug}: PASS — publishing package ready")
    else:
        print(f"[produce] {slug}: QUARANTINE — "
              + "; ".join(result.get("reasons", [])))
    return result


def _render_and_judge(slug: str, out: Path, story_path: Path, story: dict,
                      rounds: int) -> dict:
    """ONE round: render the given story, evaluate it, and persist the judging
    evidence (which also writes the ranked repair plan the caller applies)."""
    import no_dull_beats
    import run_ledger
    print(f"[produce] {slug}: render + director loop ({story_path.name})")
    try:
        director_rc = no_dull_beats.run(story_path, out, rounds=rounds)
        run_ledger.append("render_completed", slug, {"director_rc": director_rc})
    except Exception as e:  # noqa: BLE001 — a render that DIES must FAIL CLOSED,
        # never crash the producer (a malformed beat, a TTS death, a builder bug).
        # No render => no publishable film: quarantine with the failure recorded.
        detail = str(e)
        if hasattr(e, "stderr") and e.stderr:
            tail = e.stderr if isinstance(e.stderr, str) else e.stderr.decode(errors="replace")
            detail = tail.strip().splitlines()[-1] if tail.strip() else detail
        print(f"[produce] {slug}: render FAILED — {detail[:200]}", file=sys.stderr)
        result = {"out": str(out), "status": "quarantine",
                  "reasons": [f"render failed (fail-closed): {detail[:200]}"],
                  "director_rc": None, "pkg": str(out.with_name(out.stem + "_pkg")),
                  "fallback_verdict": "render_error", "slug": slug}
        print(f"[produce] {slug}: QUARANTINE — render failed (fail-closed)")
        run_ledger.append("render_failed", slug, {"detail": detail[:160]})
        return result
    # PACKAGE IDENTITY (PR#173 adoption A): hash every artifact that defines
    # this film into pkg/manifest.json. Verdicts and approvals bind to these
    # hashes; the resume path proves identity against them.
    try:
        import artifact_identity
        artifact_identity.build_manifest(out, story_path=story_path,
                                         director_rc=director_rc)
    except Exception as e:  # noqa: BLE001 — identity failure must not lose the
        print(f"[produce] {slug}: manifest build failed ({e})",  # render itself;
              file=sys.stderr)                     # evaluate() fails closed anyway
    # ADVISORY CRAFT REPORT (nextgen cognitive-load + retention-risk cluster):
    # every render carries its authoring-time analysis in the package so a
    # quarantine can be read next to WHY the story was fragile. Strictly
    # advisory — it never gates (the director + blind judge gate on pixels,
    # which outranks metadata) and never breaks a render.
    try:
        import story_advisor
        rep = story_advisor.advise(slug, story_path=story_path)
        pkg = out.with_name(out.stem + "_pkg")
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "advisor.json").write_text(json.dumps(rep, indent=2) + "\n")
    except Exception as e:  # noqa: BLE001 — advisory only, never fatal
        print(f"[produce] {slug}: advisor skipped ({str(e)[:80]})")
    result = evaluate(out, director_rc, story=story)
    result["slug"] = slug
    # DURABLE JUDGING EVIDENCE. Every judge runs and every response — raw,
    # normalized, failed, abstained — is persisted under the package so it
    # survives the runner. A judge response that cannot be read after the
    # runner disappears is treated as missing evidence, so nothing important
    # is allowed to live only in the console log.
    try:
        result["judging"] = record_judging(slug, out, story,
                                           director_rc=director_rc)
    except Exception as e:  # noqa: BLE001 — evidence capture never kills a render
        print(f"[produce] {slug}: judging evidence capture failed ({str(e)[:120]})",
              file=sys.stderr)
    _reconcile_verdict(slug, result)
    # the round's own verdict; produce() prints the FINAL one after the loop
    print(f"[produce] {slug}: round verdict — {result['status'].upper()}"
          + ("" if result["status"] == "pass"
             else " — " + "; ".join(result["reasons"][:3])))
    return result


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("out", type=Path)
    ap.add_argument("--rounds", type=int, default=2)  # Phase 10: max 2 automated repair passes, then quarantine
    ap.add_argument("--fresh", action="store_true",
                    help="force a full re-render even when the on-disk package "
                         "verifies identical (skips the resume path)")
    a = ap.parse_args(argv)
    res = produce(a.slug, a.out, rounds=a.rounds, fresh=a.fresh)
    return 0 if res["status"] == "pass" else 5


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
