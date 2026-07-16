#!/usr/bin/env python3
"""THE AUTOMATED REPAIR LOOP (PRO_DOCTRINE — label -> strategy, closed).

The gates (continuity director, exact-window analyzer, judge panel) FIND
problems. Until now a human applied the fix — re-sourcing the reused clip by
hand. This closes the loop for the mechanical case: when the continuity
director flags ACCIDENTAL_REUSE, the repair loop RE-SOURCES the offending beat
to a clean window that is perceptually DISTINCT from the beat it collided with,
and re-renders — the same move a human made, automated.

Two strategies, cheapest first:
  1. within-clip re-pick — a distinct clean window in the beat's OWN clip
     (free: the clip is already downloaded);
  2. cross-clip search — search NASA for the beat's intent, download a small
     rendition of each candidate, and take the first clean window that is
     distinct from the collision (mirrors the manual fix for self-similar
     footage, e.g. one daylight Earth clip that looks like every other).

Labels that need genuine re-authoring (a chart carrying a beat, a topical hook)
are NOT auto-repaired — they are surfaced in repair_report.json for the author.
"""
from __future__ import annotations

import json
import subprocess
from io import BytesIO
from pathlib import Path

from data_learning import continuity, footage_hybrid as fh

# a repaired window must be at least this far (dHash bits) from the collision.
DISTINCT_MIN = continuity.REUSE_THRESHOLD + 4     # 20 — clear of the ~19 floor


def _frame_at(clip: Path, t: float):
    from PIL import Image
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    return Image.open(BytesIO(r.stdout)).convert("RGB")


def pick_distinct_window(clip: Path, seconds: float, avoid_hash: int,
                         step: float = 20.0,
                         min_dist: int = DISTINCT_MIN) -> tuple:
    """Sweep the clip's clean windows and return (ss, dist) for the window
    whose mid-frame is FARTHEST (in dHash bits) from `avoid_hash` while still
    passing the exact-window analyzer. Returns (None, best_dist) if no window
    clears `min_dist` — the clip is too self-similar to repair in place."""
    spans = fh.clean_windows(clip, min_len=seconds + 1.0)
    best = (None, -1)
    for a, z in spans:
        t = a
        while t + seconds <= z:
            rep = fh.analyze_window(clip, t, seconds)
            if rep.get("ok"):
                d = continuity.hamming(
                    avoid_hash, continuity.dhash(_frame_at(clip, t + seconds / 2)))
                if d > best[1]:
                    best = (t, d)
            t += step
    return best if best[1] >= min_dist else (None, best[1])


def _beat_footage(beat: dict) -> dict | None:
    return beat.get("footage")


def repair_reuse(story: dict, work: Path, findings: list[dict],
                 beat_hashes: dict) -> list[dict]:
    """For each ACCIDENTAL_REUSE finding, re-source the LATER beat to a window
    distinct from the earlier one. Mutates `story` in place; returns a per-fix
    log. `beat_hashes` maps beat idx -> the rendered frame's dHash."""
    beats = story["beats"]
    log = []
    for f in findings:
        if f.get("label") != "ACCIDENTAL_REUSE":
            continue
        i, j = f["beat_idx"]
        anchor, target = min(i, j), max(i, j)   # keep the earlier, move later
        tb = beats[target]
        foot = _beat_footage(tb)
        if not foot or not foot.get("nasa_id"):
            log.append({"beat": tb.get("job"), "action": "skipped",
                        "why": "not a footage beat with a source"})
            continue
        avoid = beat_hashes.get(anchor)
        seconds = 8.0
        safe = "".join(c if c.isalnum() else "_"
                       for c in str(foot["nasa_id"]))[:60]
        src = work / f"srccache_{safe}.mp4"
        # strategy 1: distinct window in the beat's own clip
        if src.exists() and avoid is not None:
            ss, dist = pick_distinct_window(src, seconds, avoid)
            if ss is not None:
                foot["ss"] = round(ss, 1)
                log.append({"beat": tb.get("job"), "action": "rewindow",
                            "nasa_id": foot["nasa_id"], "ss": foot["ss"],
                            "distance": dist})
                continue
        # strategy 2: a different clip entirely (self-similar source)
        got = _resource_distinct(tb, foot, seconds, avoid, work)
        log.append(got if got else
                   {"beat": tb.get("job"), "action": "unrepaired",
                    "why": "no distinct clean window found in-clip or via search"})
    return log


def _resource_distinct(beat, foot, seconds, avoid, work) -> dict | None:
    """Search NASA for the beat's intent and adopt the first candidate clip
    with a clean window distinct from the collision."""
    query = foot.get("query") or beat.get("understand") or beat.get("job", "")
    for hit in fh.search_footage(str(query), limit=6):
        nid = hit.get("nasa_id")
        if not nid or nid == foot.get("nasa_id"):
            continue
        try:
            safe = "".join(c if c.isalnum() else "_" for c in str(nid))[:60]
            dest = work / f"srccache_{safe}.mp4"
            if not dest.exists():
                fh.download_video(str(nid), dest)
            ss, dist = pick_distinct_window(dest, seconds, avoid) \
                if avoid is not None else (None, -1)
            if ss is not None:
                foot["nasa_id"] = nid
                foot["ss"] = round(ss, 1)
                foot.pop("query", None)
                return {"beat": beat.get("job"), "action": "reclip",
                        "nasa_id": nid, "ss": foot["ss"], "distance": dist}
        except Exception:  # noqa: BLE001 — try the next candidate
            continue
    return None


def _hashes_from_pkg(story, out) -> dict:
    """dHash per beat's representative frame from the rendered video, keyed by
    beat idx — the same frames the continuity director judged."""
    pkg = out.with_name(out.stem + "_pkg")
    bm = json.loads((pkg / "beatmap.json").read_text())
    v720 = out.with_name(out.stem + "_720p.mp4")
    v = v720 if v720.exists() else out
    hashes = {}
    for idx, b in enumerate(bm["beats"]):
        a, z = (float(x) for x in str(b["t"]).split("-"))
        hashes[idx] = continuity.dhash(_frame_at(v, (a + z) / 2))
    return hashes


def repair(story_path: Path, out: Path, work: Path,
           max_rounds: int = 2) -> dict:
    """Render -> read continuity gate -> auto-repair reuse -> re-render, up to
    `max_rounds`. Writes repair_report.json next to the render."""
    from data_learning import pro_render
    story = json.loads(story_path.read_text())
    report = {"rounds": [], "final_ok": False}
    for rnd in range(max_rounds):
        pro_render.build(story, out, work, voice=story.get("voice",
                                                           pro_render.VOICE))
        pkg = out.with_name(out.stem + "_pkg")
        cont = json.loads((pkg / "continuity.json").read_text())
        if cont.get("ok"):
            report["rounds"].append({"round": rnd, "findings": 0,
                                     "fixes": []})
            report["final_ok"] = True
            break
        hashes = _hashes_from_pkg(story, out)
        fixes = repair_reuse(story, work, cont["findings"], hashes)
        report["rounds"].append({"round": rnd,
                                 "findings": len(cont["findings"]),
                                 "fixes": fixes})
        if not any(f.get("action") in ("rewindow", "reclip") for f in fixes):
            break                                # nothing mechanical left to do
    (out.with_name(out.stem + "_pkg") / "repair_report.json").write_text(
        json.dumps(report, indent=2))
    return report
