#!/usr/bin/env python3
"""judge_report — make the judging evidence readable without the runner.

    A judge response that cannot be viewed after the runner disappears is
    treated as MISSING judge evidence.

Three surfaces, from the same durable JSON under ``<out>_pkg/judging/``:

  A. the machine-readable package itself (written by judging_store)
  B. ``judging/report.md`` — the human report: scores by judge and attempt,
     every complaint, worst beats with timestamps, the repair asked for, what
     changed, before/after movement, defects fixed / remaining / introduced,
     judge disagreement, and the final reason
  C. ``$GITHUB_STEP_SUMMARY`` — a concise scoreboard with the artifact name to
     download for the full evidence

Usage:
    python scripts/judge_report.py <out.mp4> [--step-summary] [--html]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO, REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from data_learning.judging_store import JudgingStore  # noqa: E402

ARTIFACT_NAME = "curiosity-judging"


def _fmt(x, nd=1):
    return "—" if x is None else (f"{float(x):.{nd}f}"
                                  if isinstance(x, (int, float)) else str(x))


def _delta(d):
    if d is None:
        return "—"
    return f"{'+' if d > 0 else ''}{d:.2f}"


def build_markdown(store: JudgingStore) -> str:
    hist = store.history()
    summary = store.read_final_summary() if hasattr(store, "read_final_summary") else None
    summary = summary or _read(store.root / "final_summary.json")
    L: list[str] = []
    slug = (summary or {}).get("slug") or Path(store.out).stem
    L.append(f"# Judging report — {slug}")
    L.append("")
    if summary:
        L.append(f"**Result: `{summary.get('status', '?').upper()}`** — "
                 f"{summary.get('reason', '')}")
        L.append("")
        L.append(f"- attempts: **{summary.get('attempts')}** "
                 f"of max {summary.get('max_attempts')}")
        L.append(f"- final professional-quality score: "
                 f"**{_fmt(summary.get('final_overall_10'))}/10** "
                 f"(band `{summary.get('final_band')}`)")
        L.append(f"- final personality: {_fmt(summary.get('final_personality'))}/5")
        prog = [p for p in (summary.get("score_progression") or [])]
        if prog:
            L.append("- score progression: "
                     + " → ".join(_fmt(p) for p in prog))
        L.append("- escalation: "
                 + " → ".join(summary.get("escalation_progression") or ["—"]))
        L.append(f"- eligible for owner review: "
                 f"**{'yes' if summary.get('eligible_for_owner_review') else 'no'}**")
        L.append("- autonomous publishing: **disabled** "
                 "(the launch policy owns this, not the score)")
        if summary.get("unresolved_blockers"):
            L.append("")
            L.append("### Unresolved blockers")
            for b in summary["unresolved_blockers"]:
                L.append(f"- {b}")
        L.append("")

    for h in hist:
        n = h["attempt"]
        comb = h.get("combined") or {}
        dec = comb.get("decision") or {}
        man = h.get("manifest") or {}
        cmp_ = h.get("comparison") or {}
        plan = h.get("repair_plan") or {}
        L.append(f"## Attempt {n:02d} — repair class `{man.get('escalation', '?')}`")
        L.append("")
        L.append(f"- judged artifact: `{str(man.get('mp4_sha256'))[:16]}…`")
        L.append(f"- overall **{_fmt(comb.get('overall_10'))}/10**, "
                 f"personality {_fmt(comb.get('personality'))}/5, "
                 f"band `{dec.get('band')}`, "
                 f"advance: **{dec.get('advance')}**")
        L.append("")

        L.append("### Scores by judge")
        L.append("")
        L.append("| judge | status | pass | overall | findings | confidence |")
        L.append("|---|---|---|---|---|---|")
        for name, v in sorted((comb.get("verdicts") or {}).items()):
            L.append(f"| {name} | {v.get('status', '?')} | "
                     f"{'—' if v.get('pass') is None else v.get('pass')} | "
                     f"{_fmt(v.get('overall_10'))} | "
                     f"{len(v.get('findings') or [])} | "
                     f"{_fmt(v.get('confidence'), 2)} |")
        L.append("")

        findings = comb.get("findings") or []
        if findings:
            L.append("### Every complaint")
            L.append("")
            L.append("| severity | code | where | judge | complaint | fix asked for |")
            L.append("|---|---|---|---|---|---|")
            for f in findings:
                where = (f.get("time_range") or f.get("beat")
                         or f.get("target") or "film")
                L.append(f"| {f.get('severity', '?')} | `{f.get('defect_code', '?')}` "
                         f"| {str(where)[:40]} | {f.get('judge', '?')} "
                         f"| {str(f.get('complaint', ''))[:160].replace('|', '/')} "
                         f"| {str(f.get('recommended_fix', ''))[:160].replace('|', '/')} |")
            L.append("")

        if dec.get("dissent"):
            L.append("### Judge disagreement (preserved, not averaged)")
            L.append("")
            for d in dec["dissent"]:
                L.append(f"- **{d['judge']}**: "
                         f"{'pass' if d['pass'] else 'reject'}")
            L.append("")

        if plan.get("tasks"):
            L.append(f"### Repair plan ({plan.get('repair_class')}, "
                     f"{plan.get('n_tasks')} task(s), "
                     f"sig `{plan.get('signature', '?')}`)")
            L.append("")
            L.append("| # | tier | target | required change | success criterion |")
            L.append("|---|---|---|---|---|")
            for t in plan["tasks"]:
                L.append(f"| {t['id']} | {t['tier']} | {str(t['target'])[:36]} "
                         f"| {str(t['required_change'])[:120].replace('|', '/')} "
                         f"| {str(t['success_criterion'])[:90].replace('|', '/')} |")
            L.append("")
            if plan.get("deferred"):
                L.append(f"_{len(plan['deferred'])} task(s) deferred to a broader "
                         "repair class._")
                L.append("")
            if plan.get("suppressed"):
                L.append("**Contradictions resolved:**")
                for s in plan["suppressed"]:
                    L.append(f"- `{s.get('defect_code')}` on {s.get('target')}"
                             f" — {s.get('suppressed_because')}")
                L.append("")

        if not cmp_.get("first_attempt", True):
            L.append("### Movement vs the previous attempt")
            L.append("")
            L.append(f"- overall {_fmt(cmp_.get('overall_prev'))} → "
                     f"{_fmt(cmp_.get('overall_now'))} "
                     f"(**{_delta(cmp_.get('overall_delta'))}**)")
            L.append(f"- personality {_fmt(cmp_.get('personality_prev'))} → "
                     f"{_fmt(cmp_.get('personality_now'))} "
                     f"({_delta(cmp_.get('personality_delta'))})")
            L.append(f"- materially different render: "
                     f"**{cmp_.get('materially_different')}**")
            L.append(f"- defects fixed: {cmp_.get('fixed') or 'none'}")
            L.append(f"- defects introduced: {cmp_.get('introduced') or 'none'}")
            L.append(f"- targeted defects fixed: "
                     f"{cmp_.get('targeted_defects_fixed') or 'none'}")
            L.append(f"- targeted defects still present: "
                     f"{cmp_.get('targeted_defects_remaining') or 'none'}")
            L.append(f"- stalled: **{cmp_.get('stalled')}**, "
                     f"regressed: **{cmp_.get('regressed')}**")
            L.append("")

    L.append("---")
    L.append("")
    L.append(f"Full machine-readable evidence: `{store.root}` "
             f"(workflow artifact **{ARTIFACT_NAME}**). Every judge response, "
             "raw and normalized, for every attempt.")
    return "\n".join(L) + "\n"


def _read(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def build_step_summary(store: JudgingStore) -> str:
    s = _read(store.root / "final_summary.json") or {}
    hist = store.history()
    L = [f"## Judging — {s.get('slug') or Path(store.out).stem}", ""]
    L.append(f"**{s.get('status', 'unknown').upper()}** — {s.get('reason', '')}  ")
    L.append(f"attempts **{s.get('attempts', len(hist))}**/"
             f"{s.get('max_attempts', '?')} · "
             f"final **{_fmt(s.get('final_overall_10'))}/10** "
             f"(`{s.get('final_band')}`) · "
             f"personality {_fmt(s.get('final_personality'))}/5")
    L.append("")
    L.append("| attempt | class | overall | personality | advance | findings | repairs |")
    L.append("|---|---|---|---|---|---|---|")
    for h in hist:
        c = h.get("combined") or {}
        d = c.get("decision") or {}
        p = h.get("repair_plan") or {}
        L.append(f"| {h['attempt']:02d} "
                 f"| {(h.get('manifest') or {}).get('escalation', '?')} "
                 f"| {_fmt(c.get('overall_10'))} "
                 f"| {_fmt(c.get('personality'))} "
                 f"| {d.get('advance')} "
                 f"| {c.get('n_findings', 0)} "
                 f"| {p.get('n_tasks', 0)} |")
    L.append("")
    if s.get("unresolved_blockers"):
        L.append("**Unresolved blockers**")
        for b in s["unresolved_blockers"][:10]:
            L.append(f"- {b}")
        L.append("")
    # every complaint, compactly — the owner should not need the runner
    last = hist[-1] if hist else None
    if last:
        fs = ((last.get("combined") or {}).get("findings") or [])[:12]
        if fs:
            L.append("**Complaints on the final attempt**")
            for f in fs:
                where = f.get("time_range") or f.get("beat") or f.get("target") or "film"
                L.append(f"- `{f.get('defect_code')}` ({f.get('severity')}) "
                         f"@ {where} — {str(f.get('complaint', ''))[:140]}")
            L.append("")
    L.append(f"Full evidence: download the **{ARTIFACT_NAME}** artifact "
             f"(`{store.root.name}/` — raw + normalized responses per attempt).")
    return "\n".join(L) + "\n"


def write_all(out: Path, step_summary: bool = True) -> dict:
    store = JudgingStore(Path(out))
    if not store.root.exists():
        return {"written": [], "note": "no judging evidence to report"}
    written = []
    md = build_markdown(store)
    p = store.root / "report.md"
    p.write_text(md)
    written.append(str(p))
    html = ("<!-- generated by scripts/judge_report.py -->\n"
            "<pre style=\"font:14px/1.5 ui-monospace,monospace;"
            "white-space:pre-wrap\">" + md.replace("&", "&amp;")
            .replace("<", "&lt;") + "</pre>\n")
    ph = store.root / "report.html"
    ph.write_text(html)
    written.append(str(ph))
    if step_summary:
        dest = os.environ.get("GITHUB_STEP_SUMMARY")
        if dest:
            with open(dest, "a", encoding="utf-8") as fh:
                fh.write(build_step_summary(store))
            written.append(dest)
        else:
            print(build_step_summary(store))
    return {"written": written}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--no-step-summary", action="store_true")
    a = ap.parse_args(argv)
    res = write_all(a.out, step_summary=not a.no_step_summary)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
