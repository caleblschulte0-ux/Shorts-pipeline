#!/usr/bin/env python3
"""Pick the FINISHED story cuts out of a story-backtest artifact, small
enough to watch on a phone.

Operator, 2026-10-09, after being handed a 570MB artifact zip to download:
*"i need to see the finished producs and i need to seem them here"*. The
backtest's artifact holds every repair of every story plus its working
files; what a person reviews is the BEST cut of each story — the one the
pipeline would have shipped had it cleared the bar. This picks that cut per
story, re-encodes it to a phone-sized 540x960, and writes an index with its
score and the critic's retelling. `backtest-preview.yml` publishes the
result to the `preview-renders` branch, where a session can fetch it with
plain git and post it in the thread.

    python scripts/backtest_preview.py <artifact dir> <dest dir> [proven.json]

A story that PASSES (operator, 2026-10-12: *"keep trying to make stories
until we get a good one"*; 2026-10-16, on posting what passes: *"Go"*)
used to die with the backtest: it uploads nothing and writes no repo
state, so search 31's 88 had no way onto the channel. With a third
argument each passing story's plan and sources are added to that file
(`state/third_proven_stories.json`), and the channel's next real run
tries it first: re-rendered, judged again at the same bar, posted only
if it clears it (`run_third._proven_clusters`).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024        # git is the wrong home for anything large


def best_cuts(report: dict) -> list[dict]:
    """The highest-scoring rendered cut of each story, best story first.
    A cut that passes outranks one that does not; ties go to the later
    repair (it is what the pipeline would have kept)."""
    best: dict[str, dict] = {}
    for c in report.get("cuts") or []:
        if not (c.get("files") or {}).get("mp4"):
            continue
        rv = c.get("review") or {}
        key = (bool(c.get("passes")), int(rv.get("story_score") or 0),
               int(c.get("revision") or 0))
        cur = best.get(c.get("label", ""))
        if cur is None or key >= cur["_key"]:
            best[c.get("label", "")] = dict(c, _key=key)
    return sorted(best.values(), key=lambda c: c["_key"], reverse=True)


def promote(report: dict, path: Path, run_id: str = "") -> int:
    """Add each PASSING story's plan to the proven file; returns how many
    were new. Keyed on the story's sources, so a story found twice is
    kept once."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {"stories": []}
    # a story the operator turned down is never promoted again, however
    # the critic scores it next time (Pikaboo vs Payo, 88: "That video
    # sucked", 2026-10-17)
    have = {tuple(x.get("source_urls") or [])
            for x in (data.get("stories") or []) + (data.get("rejected")
                                                    or [])
            + (data.get("pending") or [])}
    added = 0
    for c in best_cuts(report):
        if not c.get("passes"):
            continue
        urls = sorted({str(b.get("source_id")) for b in
                       (c.get("edl") or {}).get("beats") or []
                       if b.get("source_id")})
        if len(urls) < 2 or tuple(urls) in have:
            continue
        have.add(tuple(urls))
        # a pass waits in `pending` until the operator has watched it: the
        # channel posts only `stories`, and the critic's 88 for Pikaboo vs
        # Payo was a video the operator called bad (2026-10-17)
        data.setdefault("pending", []).append({
            "label": c.get("label"), "run": str(run_id),
            "score": int((c.get("review") or {}).get("story_score") or 0),
            "edl": c.get("edl"), "sources": c.get("sources") or [],
            "source_urls": urls})
        added += 1
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, default=str) + "\n")
    return added


def _safe(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:60]


def main(src: str, dest: str, proven: str = "") -> int:
    src_p, dest_p = Path(src), Path(dest)
    reports = list(src_p.rglob("report.json"))
    if not reports:
        print(f"no report.json under {src_p}", flush=True)
        return 1
    root = reports[0].parent
    report = json.loads(reports[0].read_text())
    dest_p.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, c in enumerate(best_cuts(report), 1):
        rv = c.get("review") or {}
        e = c.get("edl") or {}
        score = int(rv.get("story_score") or 0)
        name = f"{i:02d}_{score}_{_safe(c.get('label', 'story'))}.mp4"
        out = dest_p / name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(root / c["files"]["mp4"]),
             "-vf", "scale=540:960", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "30", "-c:a", "aac", "-b:a", "96k",
             "-movflags", "+faststart", str(out)], check=True)
        if out.stat().st_size > MAX_BYTES:
            out.unlink()
            name = f"(over {MAX_BYTES // 2**20}MB, not published)"
        rows.append({"file": name, "score": score,
                     "passes": bool(c.get("passes")),
                     "label": c.get("label"),
                     "repair": c.get("revision"),
                     "title": e.get("title"),
                     "hook": e.get("hook_overlay"),
                     "retelling": rv.get("stranger_summary"),
                     **({"audience": rv["audience"],
                         "structure_ok": rv.get("structure_ok"),
                         "structure": [p.get("fix") for p in
                                       rv.get("problems") or []]}
                        if rv.get("gate") == "structure" else {})})
    (dest_p / "index.json").write_text(json.dumps(
        {"floor": report.get("floor"), "cuts": rows}, indent=1))
    print(json.dumps(rows, indent=1), flush=True)
    if proven:
        import os
        n = promote(report, Path(proven), os.environ.get("RUN_ID", ""))
        print(f"{n} passing story(ies) added to {proven}", flush=True)
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
