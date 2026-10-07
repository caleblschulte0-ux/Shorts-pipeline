#!/usr/bin/env python3
"""Story BACKTEST: run the real story arm, upload nothing, keep everything.

Operator, 2026-10-05: "This needs to be even better and to test it you need
to be back testing and showing me what it's coming up with." The story arm
gets two attempts a day, so learning what it makes took a day per data
point, and the only cut anyone ever saw was the one that shipped.

This drives `run_third._story_attempt` — the same scout, VOD arcs, scene
analysis, director, renderer, critic and repair loop as production — in a
loop over today's real discovery pool and the channel's real month of
posts, and keeps every cut the critic is shown (first render and every
repair, passed or failed) with its plan and verdict
(`run_third._backtest_keep`, enabled by STORY_BACKTEST_DIR). A story that
passes is marked shipped IN MEMORY so the next attempt goes looking for a
different one; a refused candidate is remembered in a scratch copy of the
clip memory so it is not tried twice.

It never uploads and writes no repo state: the posted log is read, the
clip memory and the story-event file are scratch copies.

    python scripts/story_backtest.py --attempts 4 --out backtest/

Output: <out>/report.md (and report.json) plus, per rendered cut,
<label>__rN.mp4, .json (plan + verdict) and .jpg (contact sheet).
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _load_run_third():
    spec = importlib.util.spec_from_file_location(
        "run_third_backtest", REPO / "scripts" / "run_third.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    return rt


def _sheet(mp4: Path) -> Path | None:
    out = mp4.with_suffix(".jpg")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4),
                        "-vf", "fps=1/2.5,scale=240:-1,tile=6x3",
                        "-frames:v", "1", str(out)], check=True, timeout=120)
        return out
    except Exception:  # noqa: BLE001
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--out", default="backtest")
    ap.add_argument("--max-clusters", type=int, default=6,
                    help="candidates examined per attempt")
    args = ap.parse_args(argv)

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ["STORY_BACKTEST_DIR"] = str(out)
    scratch = Path(tempfile.mkdtemp(prefix="story_backtest_"))

    from third_capture import clip_memory
    mem_copy = scratch / "clip_memory.json"
    if clip_memory.PATH.exists():
        shutil.copy2(clip_memory.PATH, mem_copy)
    clip_memory.PATH = mem_copy                 # scratch: never the repo's

    rt = _load_run_third()
    rt.EVENTS_FILE = scratch / "third_events.json"
    if (REPO / "state" / "third_events.json").exists():
        shutil.copy2(REPO / "state" / "third_events.json", rt.EVENTS_FILE)
    rt._CLIP_MEMORY = None

    base = json.loads((REPO / "state" / "third_packages" /
                       "default_clip.json").read_text())
    base.pop("count", None)
    base.pop("story_count", None)
    base["capture"]["story_max_clusters"] = args.max_clusters
    # production caps the story arm at story_budget_min so the day's clips
    # keep their time; a backtest has nothing else to spend it on
    base["capture"].pop("story_budget_min", None)
    floor = int(base["capture"].get("story_min_score", 80))
    log = copy.deepcopy(json.loads(
        (REPO / "state" / "third_posted_log.json").read_text()))

    attempts = []
    for i in range(1, args.attempts + 1):
        if rt._deadline_passed():
            print(f"[backtest] out of budget before attempt {i}", flush=True)
            break
        rt._JUDGES.clear()
        pkg = copy.deepcopy(base)
        pkg["slug"] = f"backtest-{i}"
        work = scratch / f"work_{i}"
        work.mkdir(parents=True, exist_ok=True)
        print(f"\n===== backtest attempt {i} =====", flush=True)
        led = rt._story_attempt(pkg, log, work, work / "story.mp4",
                                pkg["slug"])
        rec = {"attempt": i,
               "story_director": copy.deepcopy(
                   rt._JUDGES.get("story_director") or {}),
               "shipped": None}
        if led:
            rec["shipped"] = {k: led.get(k) for k in
                              ("authored_title", "narrative_score",
                               "narrative_summary", "revision_count",
                               "duration_s", "member_keys")}
            # shipped IN MEMORY only, so the next attempt looks elsewhere
            log["posted"][pkg["slug"]] = {
                "story_key": led.get("story_key"),
                "member_keys": led.get("member_keys") or [],
                "title": led.get("authored_title"),
                "ts": datetime.now(timezone.utc).isoformat()}
        attempts.append(rec)

    cuts = []
    for j in sorted(out.glob("*.json")):
        if j.name.startswith("report"):
            continue
        r = json.loads(j.read_text())
        mp4 = j.with_suffix(".mp4")
        sheet = _sheet(mp4) if mp4.exists() else None
        rv = r.get("review") or {}
        r["files"] = {"mp4": mp4.name if mp4.exists() else None,
                      "sheet": sheet.name if sheet else None}
        r["passes"] = bool(rv.get("publish")) and \
            int(rv.get("story_score") or 0) >= floor
        cuts.append(r)

    (out / "report.json").write_text(json.dumps(
        {"floor": floor, "attempts": attempts, "cuts": cuts},
        indent=1, default=str))
    (out / "report.md").write_text(_report_md(floor, attempts, cuts))
    print((out / "report.md").read_text(), flush=True)
    return 0


def _report_md(floor: int, attempts: list, cuts: list) -> str:
    L = ["# Story backtest",
         "",
         f"{len(attempts)} attempt(s), {len(cuts)} rendered cut(s), "
         f"{sum(1 for c in cuts if c['passes'])} at or above the {floor} "
         f"floor with a named payoff. Nothing was uploaded.", ""]
    for a in attempts:
        sd = a["story_director"]
        sup = sd.get("supply") or {}
        L.append(f"## Attempt {a['attempt']}")
        for s in sup.get("scouted") or []:
            L.append(f"- scout proposed ({s.get('shape')}, {s.get('n')} "
                     f"clips): {s.get('premise')}")
        for c in sd.get("clusters") or []:
            L.append(f"- **{c['outcome']}** — {c['cluster']}: {c['why']}")
        if a["shipped"]:
            sh = a["shipped"]
            L.append(f"- **WOULD SHIP:** \"{sh.get('authored_title')}\" "
                     f"(score {sh.get('narrative_score')}, "
                     f"{sh.get('revision_count')} repair(s)) — "
                     f"{sh.get('narrative_summary')}")
        L.append("")
    L.append("## Every rendered cut")
    for c in cuts:
        rv = c.get("review") or {}
        e = c.get("edl") or {}
        L += ["",
              f"### {c['label']} — repair {c['revision']}: "
              f"{'PASSES' if c['passes'] else 'fails'} "
              f"(score {rv.get('story_score')}, publish "
              f"{rv.get('publish')})",
              f"- title: {e.get('title')} | hook: {e.get('hook_overlay')}",
              f"- premise: {e.get('premise')}",
              f"- critic's retelling: {rv.get('stranger_summary') or '—'}"
              f" | payoff at: {rv.get('payoff_at')}"]
        for p in rv.get("problems") or []:
            L.append(f"- problem @{p.get('at')}s {p.get('type')}: "
                     f"{p.get('fix')}")
        for n in e.get("narration_lines") or (
                [e["narration"]] if e.get("narration") else []):
            L.append(f"- narration over beat {n.get('over_beat')}: "
                     f"{n.get('text')}")
        L.append(f"- files: {c['files']['mp4']} / {c['files']['sheet']}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
