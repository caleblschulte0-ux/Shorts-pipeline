#!/usr/bin/env python3
"""THE CONTINUITY DIRECTOR (PRO_DOCTRINE — preserve continuity / recognize reuse).

The editorial judge caught the reveal number riding the SAME Earth footage the
film opens and closes on — ACCIDENTAL_REUSE that diluted the deliberate
open->close callback. That was found by a human-in-the-loop judge reading the
render. "Preserve continuity" is a north-star capability of the director, so the
system must catch its own accidental reuse instead of relying on a reviewer.

This module does it with a perceptual hash (dHash): render each beat to a
representative frame, hash it, and flag any two NON-ADJACENT beats whose frames
are near-identical — UNLESS a beat is a DECLARED callback (the payoff returning
to the opening image on purpose). A dissolve between adjacent beats naturally
shares pixels, so adjacent pairs are never flagged.

Pure-PIL, no extra deps. A frame's dHash is 64 bits: downscale to 9x8 grayscale,
then one bit per adjacent-pixel brightness comparison. Near-duplicate frames have
a small Hamming distance; unrelated frames are far apart.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

# Hamming distance at/below which two beat frames are "the same shot reused".
# Calibrated on the real speed-story render: the SAME clip at different
# timestamps (the intentional open->close callback, 15 s apart) lands at 14,
# while every genuinely DISTINCT pair sits at >= 19. 16 catches same-clip reuse
# (the ACCIDENTAL_REUSE the editorial judge flagged) with a margin below the
# distinct floor. The callback allowance permits the deliberate return.
REUSE_THRESHOLD = 16


def dhash(frame, size: int = 8) -> int:
    """64-bit difference hash of a PIL image (grayscale, row-wise gradient)."""
    from PIL import Image
    im = frame.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = im.load()
    bits = 0
    for y in range(size):
        for x in range(size):
            bits = (bits << 1) | (1 if px[x, y] < px[x + 1, y] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _mid_frame(clip: Path):
    """The frame at the clip's midpoint, as a PIL image."""
    from PIL import Image
    from io import BytesIO
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)], capture_output=True,
        text=True).stdout.strip() or 1.0)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{dur / 2:.2f}", "-i", str(clip),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    return Image.open(BytesIO(r.stdout)).convert("RGB")


def detect_reuse(beats: list[dict], threshold: int = REUSE_THRESHOLD
                 ) -> list[dict]:
    """`beats`: [{"idx","job","callback","hash"}...]. Return ACCIDENTAL_REUSE
    findings for non-adjacent, non-callback beat pairs whose frames match.

    A beat marked ``callback: true`` is a DELIBERATE return to an earlier image
    (the payoff), so any match involving it is expected and never flagged."""
    out = []
    for i in range(len(beats)):
        for j in range(i + 1, len(beats)):
            a, b = beats[i], beats[j]
            if j - i <= 1:                       # adjacent -> dissolve overlap
                continue
            if a.get("callback") or b.get("callback"):
                continue                         # declared callback: expected
            d = hamming(a["hash"], b["hash"])
            if d <= threshold:
                out.append({
                    "label": "ACCIDENTAL_REUSE",
                    "beats": [a["job"], b["job"]],
                    "beat_idx": [a["idx"], b["idx"]],
                    "distance": d,
                    "reason": f"beats {a['job']} and {b['job']} render a "
                              f"near-identical frame (dHash distance {d} "
                              f"<= {threshold}) with no declared callback — "
                              "the same shot is reused. Re-source one of them "
                              "or mark the intended one as a callback.",
                })
    return out


def analyze(clips_by_beat: list[dict], out_pkg: Path,
            threshold: int = REUSE_THRESHOLD) -> dict:
    """clips_by_beat: [{"idx","job","callback","clip":Path}...] (one
    representative clip per BEAT). Hash each, detect reuse, write
    pkg/continuity.json, return the report."""
    beats = []
    for c in clips_by_beat:
        beats.append({"idx": c["idx"], "job": c["job"],
                      "callback": bool(c.get("callback")),
                      "hash": dhash(_mid_frame(Path(c["clip"])))})
    findings = detect_reuse(beats, threshold)
    report = {"threshold": threshold,
              "beats": [{"idx": b["idx"], "job": b["job"],
                         "callback": b["callback"]} for b in beats],
              "findings": findings, "ok": not findings}
    out_pkg.mkdir(parents=True, exist_ok=True)
    (out_pkg / "continuity.json").write_text(json.dumps(report, indent=2))
    return report
