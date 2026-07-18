#!/usr/bin/env python3
"""THE INTEREST JUDGE (PRO_DOCTRINE — "is this actually worth watching?").

Every other gate asks: is it clean, professional, coherent, MOVING? None asks
the only question a scrolling viewer asks: **is this INTERESTING?** A slow push
through a grey cloud mass passes every motion/quality gate and is still a snooze.

The operator's standard (the "gold watcher"): a good video has *constantly
something interesting on the screen* — not just movement, something new to look
at, an escalation, a reveal, a "wait, what is that?" Movement != interest.

This judge encodes that distinction with an OBJECTIVE grounding so it can't be
fooled by a moving camera:

  NOVELTY curve — how much the actual PICTURE changes over ~2s (perceptual-hash
  distance), NOT optical flow. A camera drifting into the same clouds has high
  motion but near-zero novelty: same content, bigger. A long run of low novelty
  is a BORING STRETCH — nothing new is happening, however much the camera moves.

  VARIETY — how many visually distinct "scenes" the whole film contains. A 60s
  film that is three near-identical grey-cloud looks is monotonous by
  construction, no matter how each shot moves.

The judge subagent reads the dense filmstrip + this novelty curve + the flagged
boring stretches and returns an INTERESTING / BORING verdict with the dead
stretches named, WHY they are dead, and what would make them interesting — so
the director can fix them (cut the dead footage, cut faster, bring a genuinely
different image, escalate, reveal).

    python3 scripts/interest_judge.py <render.mp4> --out <pkg>

Labels the judge returns (each with a time span + reason):
  BORING_STRETCH        — N seconds where nothing newly interesting appears
  MONOTONOUS_PALETTE    — the whole film sits on one look/subject/colour
  NO_ESCALATION         — visual interest never builds; it starts and stays flat
  MOVEMENT_NOT_INTEREST — a shot mistakes camera motion for something happening
  NO_HOOK               — the opening seconds give no reason to keep watching
  WEAK_PEAK             — the most interesting moment isn't interesting enough
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

SAMPLE = 1.0          # seconds between sampled frames
NOVELTY_LAG = 2       # compare each frame to the one ~NOVELTY_LAG*SAMPLE ago
DEAD = 12             # dHash distance below which two frames are "the same look"
BORING_RUN = 5.0      # seconds of sustained low novelty = a boring stretch


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0.0)


def _dhash(img, size: int = 8) -> int:
    from PIL import Image
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = g.load()
    bits = 0
    for y in range(size):
        for x in range(size):
            bits = (bits << 1) | (1 if px[x, y] < px[x + 1, y] else 0)
    return bits


def _ham(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def build_package(render: Path, out: Path) -> dict:
    """Dense filmstrip + novelty curve + boring-stretch detection."""
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO
    out.mkdir(parents=True, exist_ok=True)
    dur = _dur(render)
    times = [t for t in _frange(0.4, dur - 0.2, SAMPLE)]
    frames, hashes = [], []
    for t in times:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(render),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True)
        im = Image.open(BytesIO(r.stdout)).convert("RGB")
        frames.append(im)
        hashes.append(_dhash(im))

    # NOVELTY: how much the picture changed vs ~2s ago (content change, not motion)
    novelty = []
    for i in range(len(hashes)):
        j = max(0, i - NOVELTY_LAG)
        novelty.append(_ham(hashes[i], hashes[j]) if i else 0)

    # BORING STRETCHES: sustained runs where novelty stays under DEAD
    boring, run_start = [], None
    for i, nv in enumerate(novelty):
        low = nv < DEAD
        if low and run_start is None:
            run_start = times[i]
        if (not low or i == len(novelty) - 1) and run_start is not None:
            end = times[i]
            if end - run_start >= BORING_RUN:
                boring.append([round(run_start, 1), round(end, 1)])
            run_start = None

    # VARIETY: how many visually distinct looks (greedy clustering of hashes)
    reps: list[int] = []
    for h in hashes:
        if all(_ham(h, r) >= DEAD + 6 for r in reps):
            reps.append(h)
    variety = len(reps)

    # render the dense filmstrip (frames left->right, top->bottom) with the
    # per-frame novelty printed, so the judge sees where the picture goes flat.
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    fw, cols = 300, 6
    thumbs = []
    for t, im, nv in zip(times, frames, novelty):
        th = im.resize((fw, int(fw * im.height / im.width)))
        d = ImageDraw.Draw(th)
        d.rectangle([0, 0, fw, 22], fill=(8, 8, 14))
        # novelty flagged red when the picture is barely changing
        col = (255, 90, 90) if nv < DEAD else (150, 235, 150)
        d.text((4, 3), f"{t:4.1f}s  new:{nv}", font=font, fill=col)
        thumbs.append(th)
    rowh = thumbs[0].height
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * fw, rows * rowh), (4, 4, 8))
    for i, th in enumerate(thumbs):
        sheet.paste(th, ((i % cols) * fw, (i // cols) * rowh))
    sheet.save(out / "interest_strip.png")

    dead_secs = sum(b[1] - b[0] for b in boring)
    report = {
        "duration": round(dur, 1),
        "variety_scenes": variety,
        "mean_novelty": round(sum(novelty) / max(1, len(novelty)), 1),
        "boring_stretches": boring,
        "dead_seconds": round(dead_secs, 1),
        "dead_fraction": round(dead_secs / max(1.0, dur), 2),
    }
    (out / "interest.json").write_text(json.dumps(report, indent=2))
    print(f"interest package -> {out}")
    print(json.dumps(report, indent=2))
    return report


def _frange(a: float, b: float, step: float):
    t = a
    while t <= b:
        yield t
        t += step


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    build_package(a.render, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
