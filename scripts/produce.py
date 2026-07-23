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


def _provenance_gap(story: dict) -> str | None:
    """Flagship factual-provenance gate (audit #11). A story that OPTS IN with
    top-level ``"require_provenance": true`` must carry `facts[]` provenance for
    its numeric claims; a spoken number with no source must not publish. Scoped
    to opt-in stories so non-financial stories (speeds, scales) are unaffected —
    provenance is authored per story, not guessed from narration."""
    if not story or not story.get("require_provenance"):
        return None
    sourced = sum(1 for b in story.get("beats", []) if b.get("facts"))
    if sourced == 0:
        return ("require_provenance is set but no beat carries facts[] — refusing "
                "to publish financial claims with no source (audit #11)")
    return None


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

    prov = _provenance_gap(story or {})
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
    # A verdict is only valid for the render it judged. A re-render rebuilds the
    # blind package but does not delete an old verdict, so a verdict that predates
    # the current mp4 is STALE — treat it as absent and fail closed, or we would
    # promote a new cut on last cut's judgment.
    vpath = pkg / "verdict.json"
    if verdict is not None and out.exists() and \
            vpath.stat().st_mtime < out.stat().st_mtime:
        reasons.append("stale vision verdict (pkg/verdict.json predates this "
                       "render) — FAILS CLOSED; re-judge the current blind package")
        verdict = None
    elif verdict is None:
        reasons.append("no vision taste verdict (pkg/verdict.json) — FAILS CLOSED; "
                       "judge the blind package before publishing")
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


def produce(slug: str, out: Path, rounds: int = 3) -> dict:
    """Render + gate + repair the story, then evaluate it. Returns the evaluate()
    result with the slug attached."""
    import no_dull_beats
    story_path = resolve_story(slug)
    story = json.loads(story_path.read_text())
    print(f"[produce] {slug}: render + director loop ({story_path.name})")
    try:
        director_rc = no_dull_beats.run(story_path, out, rounds=rounds)
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
        return result
    result = evaluate(out, director_rc, story=story)
    result["slug"] = slug
    if result["status"] == "pass":
        print(f"[produce] {slug}: PASS — publishing package ready")
    else:
        print(f"[produce] {slug}: QUARANTINE — " + "; ".join(result["reasons"]))
    return result


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("out", type=Path)
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args(argv)
    res = produce(a.slug, a.out, rounds=a.rounds)
    return 0 if res["status"] == "pass" else 5


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
