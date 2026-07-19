#!/usr/bin/env python3
"""THE COOL JUDGE (data_learning/COOL_JUDGE.md — is this the SICKEST way to show it?).

For every beat, one question: is this the coolest, most view-worthy way to show
the subject — or are we cropping to a boring fragment of something spectacular?
The canonical fail is FRAGMENT_OF_THE_SPECTACLE: a zoomed-in hurricane eye (a
white cloud) when the WHOLE spinning storm from space is available and way cooler.

"Cool" is taste on pixels, so the final verdict is a vision subagent using the
doctrine. This script does the deterministic half: it cuts the render into per-
BEAT cards (a representative frame + a short clip + motion/appeal numbers) and
runs an objective PRE-SCREEN that flags cool-suspect beats (near-frozen, dull, or
a long hold) for the judge to scrutinise. The pre-screen never certifies cool — a
high-motion beat can still be a boring fragment — it only focuses the eyes.

    python3 scripts/cool_judge.py <render.mp4> --beatmap <beatmap.json> \
        --out <pkgdir>

Emits <pkg>/beat_<i>.png (+ _clip.mp4) per beat and cool_prescreen.json:
  [{beat, job, t, motion, appeal, hold_s, suspect:[LOW_MOTION|DULL|LONG_HOLD]}]
The judge prompt lives in the orchestrator/doctrine, not here (no intent leak
beyond the beat's own job, which the judge needs to reason about the subject).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# a beat that barely moves is a frozen plate; a dull beat is low-appeal; a long
# hold on one image is a scroll risk. Tunable, deliberately generous — the eyes
# make the real call, these just raise a hand.
LOW_MOTION = 4.0
DULL = 0.42
LONG_HOLD = 6.0


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0.0)


def _frame(clip: Path, t: float):
    from io import BytesIO
    from PIL import Image
    t = max(0.0, t)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    if not r.stdout:                       # t past the end / bad seek -> back off
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-sseof", "-0.5", "-i", str(clip),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True)
    return Image.open(BytesIO(r.stdout)).convert("RGB")


def _motion(clip: Path, a: float, b: float) -> float:
    """Peak frame-to-frame change across the beat — its dynamism (a spinning
    storm scores high, a frozen plate near zero)."""
    import numpy as np
    n = 6
    ts = [a + (b - a) * i / (n - 1) for i in range(n)]
    small = [np.asarray(_frame(clip, t).resize((96, 54)).convert("L"),
                        dtype="float32") for t in ts]
    diffs = [float(np.abs(small[i] - small[i - 1]).mean())
             for i in range(1, len(small))]
    return round(max(diffs), 1) if diffs else 0.0


def build_package(render: Path, beatmap: dict, out: Path) -> list[dict]:
    from interest_judge import _appeal
    out.mkdir(parents=True, exist_ok=True)
    beats = beatmap.get("beats", [])
    total = _dur(render)
    rows = []
    for i, b in enumerate(beats):
        rng = str(b.get("t", "")).split("-")
        try:
            a, z = float(rng[0]), float(rng[1])
        except (ValueError, IndexError):
            continue
        z = min(z, total - 0.1)            # last beat may overrun the render
        if z <= a:
            a, z = max(0.0, total - 1.5), total - 0.1
        mid = (a + z) / 2
        card = out / f"beat_{i:02d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{mid:.2f}",
             "-i", str(render), "-frames:v", "1", "-vf", "scale=960:-1",
             str(card)], check=True)
        clip = out / f"beat_{i:02d}_clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.2f}",
             "-i", str(render), "-t", f"{max(1.0, z - a):.2f}",
             "-vf", "scale=640:-1", "-an", str(clip)], check=True)
        motion = _motion(render, a + 0.2, z - 0.2)
        appeal = round(_appeal(_frame(render, mid)), 3)
        hold = round(z - a, 1)
        suspect = []
        if motion < LOW_MOTION:
            suspect.append("LOW_MOTION")
        if appeal < DULL:
            suspect.append("DULL")
        if hold >= LONG_HOLD:
            suspect.append("LONG_HOLD")
        rows.append({"beat": i, "job": b.get("job", ""), "t": b.get("t", ""),
                     "motion": motion, "appeal": appeal, "hold_s": hold,
                     "suspect": suspect, "card": card.name,
                     "clip": clip.name})
    (out / "cool_prescreen.json").write_text(json.dumps(rows, indent=2))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render", type=Path)
    ap.add_argument("--beatmap", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    beatmap = json.loads(a.beatmap.read_text())
    rows = build_package(a.render, beatmap, a.out)
    flagged = [r for r in rows if r["suspect"]]
    print(f"[cool] {len(rows)} beats -> {a.out}  "
          f"({len(flagged)} cool-suspect)")
    for r in rows:
        tag = ",".join(r["suspect"]) or "ok"
        print(f"  beat {r['beat']} {r['job']:16s} motion={r['motion']:5.1f} "
              f"appeal={r['appeal']:.2f} hold={r['hold_s']:.1f}s  {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
