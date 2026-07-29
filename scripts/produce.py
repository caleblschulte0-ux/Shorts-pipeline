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
    elif not verdict.get("pass"):
        reasons.append(f"vision taste REJECT: labels={verdict.get('reject_labels')} "
                       f"personality={verdict.get('personality')}")

    status = "pass" if not reasons else "quarantine"
    result = {"out": str(out), "status": status, "reasons": reasons,
              "director_rc": director_rc, "pkg": str(pkg),
              "fallback_verdict": fb.get("verdict", "unknown")}
    if pkg.exists():
        (pkg / "produce_report.json").write_text(json.dumps(result, indent=2))
    return result


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


def produce(slug: str, out: Path, rounds: int = 2, fresh: bool = False) -> dict:
    """Render + gate + repair the story, then evaluate it. Returns the evaluate()
    result with the slug attached. `fresh=True` forces a re-render even when
    the on-disk package proves identical (resume path)."""
    import no_dull_beats
    import run_ledger
    story_path = resolve_story(slug)
    story = json.loads(story_path.read_text())
    run_ledger.append("run_started", slug,
                      {"out": str(out), "rounds": rounds, "fresh": fresh})
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
    result = evaluate(out, director_rc, story=story)
    result["slug"] = slug
    run_ledger.append("evaluated", slug,
                      {"status": result["status"],
                       "n_reasons": len(result["reasons"])})
    if result["status"] == "pass":
        print(f"[produce] {slug}: PASS — publishing package ready")
    else:
        print(f"[produce] {slug}: QUARANTINE — " + "; ".join(result["reasons"]))
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
