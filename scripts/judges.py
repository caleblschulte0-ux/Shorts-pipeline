#!/usr/bin/env python3
"""What the judges thought — a readable digest of the brains' verdicts.

Several brains judge every slot: the banger ranker, the transcript-aware
content gate, the story director, the vision critic, and the render_qa
engine. Their reasoning used to exist only in the CI log — which expires,
and takes ~1200 lines to read. Answering "why was this clip rejected?" a
day later meant log archaeology.

run_third records each verdict into state/third_qa_stats.json; this renders
it. Reads committed state only, so it works locally, offline, days later.

    python scripts/judges.py                # the latest run
    python scripts/judges.py --runs 3       # the last 3 runs
    python scripts/judges.py --date 20260730
    python scripts/judges.py --rejects      # only what got turned down
    python scripts/judges.py --json         # machine-readable

Exit 0 always (a reporting tool must never fail a pipeline).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "state" / "third_qa_stats.json"
LOG = ROOT / "state" / "third_posted_log.json"

# One glyph per outcome, so a slate reads at a glance.
MARK = {"pass": "PASS", "reject": "REJECT", "unavailable": "-- DOWN",
        "fail": "REJECT", "not_a_story": "no arc", "starved": "STARVED"}


def _fmt_judge(name: str, v: dict) -> list[str]:
    """One judge's verdict as display lines."""
    out = []
    if name == "banger":
        blind = v.get("blind")
        score = v.get("score")
        tag = "  <- BLIND (can't-score default)" if blind else ""
        why = f" — {v['why']}" if v.get("why") else ""
        out.append(f"    ranker      {score}{why}{tag}")
    elif name == "content":
        verdict = MARK.get(v.get("verdict"), v.get("verdict", "?"))
        score, floor = v.get("score"), v.get("floor")
        why = f" — {v['why']}" if v.get("why") else ""
        bar = f" ({score} vs floor {floor})" if score is not None else ""
        # provenance: a text-only verdict carries the known bias against
        # visually-driven clips, so it must not read as authoritative
        eyes = "" if v.get("saw_frames") else "  [TEXT-ONLY — did not see]"
        out.append(f"    content     {verdict}{bar}{why}{eyes}")
    elif name == "vision":
        verdict = MARK.get(v.get("verdict"), v.get("verdict", "?"))
        conf = f" conf={v['confidence']}" if v.get("confidence") else ""
        out.append(f"    vision      {verdict}{conf}")
        for p in v.get("problems") or []:
            out.append(f"                  · {p}")
    elif name == "render_qa":
        probs = v.get("problems") or []
        verdict = "PASS" if not probs else "REJECT"
        out.append(f"    render_qa   {verdict}")
        for p in probs:
            out.append(f"                  · {p}")
    elif name == "title":
        src = v.get("source", "?")
        note = "authored by the brain" if src == "authored" else (
            "kept the clipper's title" if v.get("kept_raw")
            else "FLOOR — authoring produced nothing")
        out.append(f"    title       {note}")
        if v.get("title"):
            out.append(f"                  \"{v['title']}\"")
    elif name == "selection":
        # a RESCUE means the title floor failed and the clip was escalated
        # to the transcript judge rather than the slot being abandoned —
        # the operator should be able to see that happened
        v_ = v.get("verdict")
        label = {"rescue": "RESCUED (escalated to the transcript judge)",
                 "skip": "SKIPPED (below the hard floor)"}.get(v_, v_ or "?")
        out.append(f"    selection   {label}")
        if v.get("why"):
            out.append(f"                  · {v['why']}")
    elif name == "story_director":
        for c in v.get("clusters") or []:
            mark = MARK.get(c.get("outcome"), c.get("outcome", "?"))
            out.append(f"    story       {mark}  {c.get('cluster')}")
            out.append(f"                  · {c.get('why')}")
    return out


def _render_run(run: dict, rejects_only: bool) -> None:
    brain = run.get("brain") or {}
    ok, fail = brain.get("ok", 0), brain.get("fail", 0)
    if ok or fail:
        total = ok + fail
        health = ("DOWN — every brain task failed" if ok == 0 else
                  "healthy" if fail == 0 else
                  f"DEGRADED — {fail}/{total} brain tasks failed")
        brain_line = f"   brain: {health}  ({ok} ok / {fail} failed)"
    else:
        brain_line = "   brain: not recorded (run predates brain tracking)"

    print(f"\n=== {run.get('date')}  {run.get('ts', '')}"
          f"{'  [dry-run]' if run.get('dry_run') else ''}")
    print(brain_line)

    dead = run.get("dead_sources") or {}
    if dead:
        # a source that returned nothing is lost supply — surface it so the
        # allowlist can be pruned on evidence instead of guesswork
        broke = {k: v for k, v in dead.items() if v.get("fail")}
        empty = [k for k, v in dead.items() if not v.get("fail")]
        if broke:
            print(f"   dead sources: {len(broke)} ERRORED — "
                  + ", ".join(f"{k} ({v.get('err', '?')})"
                              for k, v in list(broke.items())[:6])
                  + (" ..." if len(broke) > 6 else ""))
        if empty:
            print(f"   quiet sources: {len(empty)} returned 0 clips — "
                  + ", ".join(empty[:8])
                  + (" ..." if len(empty) > 8 else ""))

    clips = run.get("clips") or []
    shown = 0
    for c in clips:
        posted = bool(c.get("ok"))
        if rejects_only and posted:
            continue
        shown += 1
        status = "POSTED " if posted else "not posted"
        why = c.get("error") or c.get("skipped") or ""
        print(f"\n  {c.get('slug')}  [{status}]"
              + (f"  {why[:110]}" if why and not posted else ""))
        judges = c.get("judges") or {}
        if not judges:
            print("    (no judge verdicts recorded)")
            continue
        for name in ("selection", "banger", "content",
                     "story_director", "title",
                     "render_qa", "vision"):
            if name in judges:
                for line in _fmt_judge(name, judges[name]):
                    print(line)
    if not shown:
        print("\n  (nothing matched)")


def _rejects_from_log(date: str) -> list[dict]:
    """Blocklisted clips carry their own rejection reason in the posted log
    — the durable record that outlives the run's stats window."""
    try:
        log = json.loads(LOG.read_text())["posted"]
    except Exception:  # noqa: BLE001
        return []
    out = []
    for k, v in log.items():
        if not v.get("qa_rejected"):
            continue
        ts = str(v.get("ts", ""))
        if date and not ts.replace("-", "").startswith(date):
            continue
        out.append({"key": k, "title": v.get("title", ""),
                    "streamer": v.get("streamer", ""),
                    "by": v.get("rejected_by", ""),
                    "why": v.get("rejected_why", ""), "ts": ts})
    return sorted(out, key=lambda r: r["ts"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1,
                    help="how many recent runs to show (default 1)")
    ap.add_argument("--date", default="",
                    help="only runs for this date folder (e.g. 20260730)")
    ap.add_argument("--rejects", action="store_true",
                    help="only slots that did NOT post")
    ap.add_argument("--json", action="store_true",
                    help="dump the raw records instead of rendering")
    a = ap.parse_args()

    if not STATS.exists():
        print(f"no stats yet at {STATS.relative_to(ROOT)}")
        return 0
    try:
        runs = json.loads(STATS.read_text()).get("runs", [])
    except Exception as e:  # noqa: BLE001
        print(f"could not read stats: {e}")
        return 0
    if a.date:
        runs = [r for r in runs if str(r.get("date", "")).startswith(a.date)]
    runs = runs[-max(1, a.runs):]
    if not runs:
        print("no runs matched")
        return 0

    if a.json:
        print(json.dumps(runs, indent=2))
        return 0

    print("JUDGES — what the brains thought "
          f"({len(runs)} run{'s' if len(runs) != 1 else ''})")
    for r in runs:
        _render_run(r, a.rejects)

    blocked = _rejects_from_log(a.date or str(runs[-1].get("date", "")))
    if blocked:
        print(f"\n=== blocklisted sources ({len(blocked)}) — "
              "clips turned down before they could take a slot")
        for b in blocked:
            head = f"  {b['streamer']:>14}  {b['title'][:46]!r}"
            print(head)
            if b["by"] or b["why"]:
                print(f"                  {b['by']}: {b['why']}")
            else:
                print("                  (reason not recorded — pre-dates "
                      "verdict capture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
