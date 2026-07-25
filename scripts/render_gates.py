#!/usr/bin/env python3
"""Phase-8 automated render gates — judge a finished pro_render output.

Reads the render's package (fallbacks.json, performance.json, meta/srt/jpg
sidecars) plus the mp4 itself and prints a PASS/HOLD verdict per gate:

  technical    exit artifacts exist, duration sane, audio present
  fallbacks    no unacceptable fallback; degraded ones listed for review
  performance  no rising per-shot trend; media vs render cost split reported
  package      publishing sidecars complete (meta.json, .srt, .jpg, beatmap)

Usage:  python scripts/render_gates.py <out.mp4> [--min-dur S] [--max-dur S]
Exit 0 only when every gate passes — callers can quarantine on non-zero.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True)
    try:
        d = json.loads(out.stdout)
        dur = float(d.get("format", {}).get("duration", 0))
        kinds = [s.get("codec_type") for s in d.get("streams", [])]
        return {"duration": dur, "has_video": "video" in kinds,
                "has_audio": "audio" in kinds}
    except Exception:  # noqa: BLE001
        return {"duration": 0, "has_video": False, "has_audio": False}


def gate_technical(mp4: Path, min_dur: float, max_dur: float) -> tuple[bool, list[str]]:
    notes = []
    if not mp4.exists() or mp4.stat().st_size < 1_000_000:
        return False, [f"missing or tiny mp4: {mp4}"]
    p = probe(mp4)
    notes.append(f"duration {p['duration']:.1f}s, video={p['has_video']}, "
                 f"audio={p['has_audio']}")
    ok = (p["has_video"] and p["has_audio"]
          and min_dur <= p["duration"] <= max_dur)
    if not ok:
        notes.append(f"FAIL: need audio+video and {min_dur:.0f}s <= dur <= {max_dur:.0f}s")
    return ok, notes


def gate_fallbacks(pkg: Path) -> tuple[bool, list[str]]:
    f = pkg / "fallbacks.json"
    if not f.exists():
        return False, ["fallbacks.json missing — render did not report honestly"]
    data = json.loads(f.read_text())
    verdict = data.get("verdict", "unknown")
    fb = data.get("fallbacks", [])
    notes = [f"verdict={verdict}, {len(fb)} fallbacks recorded"]
    for x in fb:
        notes.append(f"  [{x.get('severity')}] {x.get('kind')}: "
                     f"{str(x.get('detail'))[:70]}")
    return verdict in ("ok", "degraded"), notes


def gate_performance(pkg: Path) -> tuple[bool, list[str]]:
    f = pkg / "performance.json"
    if not f.exists():
        return False, ["performance.json missing"]
    m = json.loads(f.read_text())
    shots = m.get("shots", [])
    notes = [f"total {m.get('total_elapsed_s', 0):.0f}s for "
             f"{m.get('actual_duration_s', 0):.0f}s of video, "
             f"{len(shots)} shots"]
    if len(shots) >= 6:
        # trend on LOCAL render time (frame_render) — media waits excluded
        loc = [s.get("frame_render_s", 0) - s.get("asset_resolution_s", 0)
               for s in shots]
        per = [t / max(s.get("planned_duration_s", 1), 0.1)
               for t, s in zip(loc, shots)]
        first = sum(per[:3]) / 3
        last = sum(per[-3:]) / 3
        ratio = last / first if first > 0 else 1.0
        notes.append(f"local render cost first->last: {ratio:.2f}x "
                     f"({'RISING' if ratio > 1.5 else 'flat'})")
        media = sum(s.get("asset_resolution_s", 0) for s in shots)
        render = sum(loc)
        notes.append(f"media resolution {media:.0f}s vs local render "
                     f"{render:.0f}s")
        if ratio > 1.5:
            return False, notes
    # memory across shots
    if shots:
        r0 = shots[0].get("mem_start", {}).get("rss_mb", 0)
        r1 = max(s.get("mem_end", {}).get("rss_mb", 0) for s in shots)
        notes.append(f"rss {r0:.0f} -> peak {r1:.0f}MB")
        if r0 > 0 and r1 > max(4 * r0, r0 + 1500):
            notes.append("FAIL: memory ballooned across shots")
            return False, notes
    return True, notes


def gate_package(mp4: Path, pkg: Path) -> tuple[bool, list[str]]:
    required = {
        "meta.json": mp4.with_suffix(".meta.json"),
        "captions": mp4.with_suffix(".srt"),
        "thumbnail": mp4.with_suffix(".jpg"),
        "beatmap": pkg / "beatmap.json",
    }
    notes, ok = [], True
    for name, p in required.items():
        exists = p.exists() and p.stat().st_size > 0
        notes.append(f"{'✓' if exists else '✗'} {name}: {p.name}")
        ok = ok and exists
    return ok, notes


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", type=Path)
    ap.add_argument("--min-dur", type=float, default=30.0)
    ap.add_argument("--max-dur", type=float, default=420.0)
    a = ap.parse_args(argv)
    pkg = a.mp4.with_name(a.mp4.stem + "_pkg")

    gates = [
        ("technical", *gate_technical(a.mp4, a.min_dur, a.max_dur)),
        ("fallbacks", *gate_fallbacks(pkg)),
        ("performance", *gate_performance(pkg)),
        ("package", *gate_package(a.mp4, pkg)),
    ]

    all_ok = True
    print(f"RENDER GATES — {a.mp4}")
    for name, ok, notes in gates:
        print(f"\n[{'PASS' if ok else 'HOLD'}] {name}")
        for n in notes:
            print(f"    {n}")
        all_ok = all_ok and ok
    print(f"\n=> {'ALL GATES PASS' if all_ok else 'HOLD — do not publish'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
