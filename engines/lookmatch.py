"""lookmatch — pull mixed-source media toward ONE house look (gated).

THE PROBLEM (verbatim from the blind taste judge, 2026-07-29, money-goes):
"three flat real-estate-style house exteriors ... sit next to genuinely
cinematic material with no single color grade tying them together, so the
film reads as a keyword search rather than a shoot." The final film grade
runs over every frame, but a grade applied ON TOP of wildly different
exposure/saturation cannot make a washed-out listing photo and a moody
night clip read as one shoot. Harmonization has to happen PER ASSET,
BEFORE assembly.

WHAT IT DOES: measures each asset's luma mean and saturation (ffmpeg
signalstats over sampled frames), then applies a GENTLE eq nudge toward the
house target band — never a creative regrade, only a normalization, and the
correction is clamped so a deliberately dark or bright shot keeps its
character. Assets already inside the band pass through UNTOUCHED (the
returned path is the input), so the cost is one probe, not a re-encode.

Contract (the package rules): ``available()`` is offline/deterministic;
``maybe_harmonize(src, out)`` returns the harmonized path (or the input
path when in-band) and None on ANY failure; scratch stays under cache/.

GATED: per the registry rules this ships OFF — no renderer calls it yet.
First adoption in any channel requires a side-by-side preview render before
flipping a default. Demo:

    python -m engines demo lookmatch --image photo.jpg --out /tmp/lm.jpg
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

# The house target band, MEASURED (not guessed) from the graded, taste-
# passing money-goes master on 2026-07-29: whole-film YAVG 65.9, SATAVG
# 12.3 — the house look is genuinely low-key and restrained. Harmonizing
# toward anything brighter would be a creative regrade wearing a
# normalization costume. In-band assets are untouched. Re-measure these if
# the film grade in pro_render ever changes.
TARGET_LUMA = 66.0           # 0-255 signalstats YAVG
TARGET_SAT = 13.0            # 0-255 signalstats SATAVG
LUMA_BAND = 24.0             # |YAVG - target| inside this band -> no touch
SAT_BAND = 12.0
MAX_GAIN = 0.22              # clamp: never brighten/darken past ~22%
MAX_SAT_SHIFT = 0.25


def available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which(
        "ffprobe") is not None


def _stats(src: Path) -> tuple[float, float] | None:
    """(mean luma, mean saturation) over sampled frames, or None."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(src), "-vf",
             "select='not(mod(n\\,12))',signalstats,"
             "metadata=print:key=lavfi.signalstats.YAVG,"
             "metadata=print:key=lavfi.signalstats.SATAVG",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120)
        y = [float(m) for m in re.findall(r"YAVG=([0-9.]+)", r.stderr)]
        s = [float(m) for m in re.findall(r"SATAVG=([0-9.]+)", r.stderr)]
        if not y:
            return None
        return (sum(y) / len(y), (sum(s) / len(s)) if s else TARGET_SAT)
    except Exception:  # noqa: BLE001
        return None


def plan(src: Path) -> dict | None:
    """The correction lookmatch WOULD apply: {'luma','sat','gamma',
    'saturation','in_band'}. None when the asset can't be probed."""
    st = _stats(Path(src))
    if st is None:
        return None
    luma, sat = st
    # near-greyscale (archival b/w, line art) is a legitimate LOOK, not a
    # saturation defect — pumping color into it would be a creative change,
    # so it always counts as saturation-in-band.
    sat_ok = abs(sat - TARGET_SAT) <= SAT_BAND or sat < 4.0
    in_band = abs(luma - TARGET_LUMA) <= LUMA_BAND and sat_ok
    # gamma nudges midtones toward target without crushing ends; clamp hard.
    gamma = 1.0
    if abs(luma - TARGET_LUMA) > LUMA_BAND and luma > 1:
        gamma = min(1.0 + MAX_GAIN,
                    max(1.0 - MAX_GAIN, (TARGET_LUMA / luma) ** 0.6))
    saturation = 1.0
    if not sat_ok and sat > 4.0:
        saturation = min(1.0 + MAX_SAT_SHIFT,
                         max(1.0 - MAX_SAT_SHIFT, TARGET_SAT / sat))
    return {"luma": round(luma, 1), "sat": round(sat, 1),
            "gamma": round(gamma, 3), "saturation": round(saturation, 3),
            "in_band": in_band}


def maybe_harmonize(src, out) -> Path | None:
    """Harmonized copy of src at out — or src itself when already in-band —
    or None on any failure. Works for stills and clips alike."""
    try:
        src, out = Path(src), Path(out)
        if not (available() and src.exists() and src.stat().st_size > 256):
            return None
        p = plan(src)
        if p is None:
            return None
        if p["in_band"]:
            return src                       # untouched: cost was one probe
        out.parent.mkdir(parents=True, exist_ok=True)
        vf = f"eq=gamma={p['gamma']}:saturation={p['saturation']}"
        is_video = src.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf]
        cmd += (["-c:v", "libx264", "-crf", "18", "-preset", "fast",
                 "-c:a", "copy"] if is_video else ["-frames:v", "1", "-q:v", "2"])
        cmd.append(str(out))
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        if out.exists() and out.stat().st_size > 256:
            return out
        return None
    except Exception:  # noqa: BLE001 — best-effort, never raises
        return None
