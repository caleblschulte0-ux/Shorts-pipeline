#!/usr/bin/env python3
"""THE EDITORIAL REVIEW PANEL (PRO_DOCTRINE — editorial direction system).

The blind PIXEL-QUALITY panel (scripts/visual_judge.py) answers "does this look
professional?" — and it will happily PASS a topical slideshow. This panel
answers the question the pixel judge cannot: **does each visual actually DO the
narrative job the script needs at that moment, and does the timeline cohere and
pay off?**

Validated on the 89.9s regression fixture: given only the beat intents + the
render (never the code), the editorial judge independently reproduced the
operator's entire hand-diagnosis with repairable labels (rocket hook is
TOPICAL_BUT_NOT_EDITORIAL, the number cards are STATIC_NUMBER_CARD, the sentence
slates are TEXT_AS_FALLBACK, the payoff is PAYOFF_SPLIT_FROM_IMAGE, the ending is
ACCIDENTAL_REUSE + POST_CLIMAX_DOWNGRADE, the timeline is
FOOTAGE_GRAPHICS_DISCONNECTED). That is the measurement layer the planner and
the repair loop optimize against.

This script does the deterministic half: turn a render + a BEAT MAP into the
review package a judge reads. The judges themselves are fresh subagents run by
the orchestrator (they must not see code or intent-beyond-the-beat-map), one per
role: EDITORIAL-ALIGNMENT, CONTINUITY, VISUAL-EXHAUSTION, PAYOFF.

    python3 scripts/editorial_review.py <render.mp4> <beatmap.json> --out <pkg>

BEAT MAP schema (authored by the Beat Intent Planner, or hand-written for a
fixture): {"topic": "...", "beats": [{"t":"0-10","job":"HOOK",
"narration":"...","intended_understanding":"...","visual":"..."}, ...]}.

REPAIRABLE FAILURE LABELS — the judges return these (with beat time + reason),
not scores; each maps to a repair strategy in the automated repair loop.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

# The label vocabulary (PRO_DOCTRINE §"Judge panel expansion"). Each maps to a
# repair strategy in the repair loop (task: automated repair).
REPAIRABLE_LABELS = {
    "TOPICAL_BUT_NOT_EDITORIAL": "regenerate the media query from the narrative "
    "job, not topic keywords; pick the clip that does the beat's job",
    "STATIC_NUMBER_CARD": "attach the value to footage / split the beat into "
    "phases / build an explanatory visual / add a consequence / shorten",
    "TEXT_AS_FALLBACK": "source evidence or construct a designed visual; reserve "
    "full-sentence text for a deliberate quote/thesis only",
    "CHART_CARRYING_BEAT": "transform the chart into a mechanism / scale / "
    "environment / physical consequence after the comparison lands",
    "FOOTAGE_GRAPHICS_DISCONNECTED": "composite graphics onto footage "
    "(annotation/transform) instead of alternating full-screen modes",
    "ACCIDENTAL_REUSE": "replace with a different shot, or give the reuse a "
    "declared callback purpose with altered context",
    "PAYOFF_SPLIT_FROM_IMAGE": "rebuild the ending so the strongest line and the "
    "strongest image land together as one unit",
    "POST_CLIMAX_DOWNGRADE": "do not follow the climax with a weaker visual; end "
    "on the payoff image",
    "SHOT_TOO_LONG": "develop / transform / cut when the shot has communicated "
    "everything (visual exhaustion)",
    "TEMPLATE_REPETITION": "vary the visual grammar; do not repeat a card format "
    "without development",
}

# The four editorial roles. The orchestrator runs each as a fresh subagent that
# sees the contact sheet + beat map (never the code). Kept here so the protocol
# is one durable, versioned artifact.
ROLES = ("editorial_alignment", "continuity", "visual_exhaustion", "payoff")


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0.0)


STRIP = 4   # frames sampled across each beat window (begin -> end)


def build_package(render: Path, beatmap: Path, out: Path) -> Path:
    """Build the editorial review package: a beat-aligned contact sheet where
    each beat is a horizontal TEMPORAL STRIP — STRIP frames sampled evenly
    across the beat's time window (left = beat start, right = beat end) — plus
    the beat map, for the judges to read.

    One frame per beat cannot show whether a shot keeps developing or freezes,
    so the visual-exhaustion judge is blind to SHOT_TOO_LONG. The strip makes
    the sheet MOTION-AWARE: a beat whose last frames are identical to each other
    is a static hold; a beat whose frames keep changing left-to-right is
    developing. Every beat row is one strip; the sheet stacks the beats."""
    out.mkdir(parents=True, exist_ok=True)
    bm = json.loads(beatmap.read_text())
    beats = bm["beats"]
    dur = _dur(render)
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except Exception:  # noqa: BLE001
        font = small = ImageFont.load_default()
    fw = 360                      # per-frame width in a strip
    label_w = 150                 # left label column
    tmp = out / "_t.png"
    rows = []                     # one composited strip (PIL image) per beat
    for b in beats:
        a, z = (float(x) for x in str(b["t"]).split("-"))
        span = max(0.0, z - a)
        # sample begin..end; pull the endpoints just inside the window so we
        # capture the true first/last state of the shot (a freeze shows up as
        # the final 2 frames being identical).
        ts = [min(dur - 0.05, a + 0.12 + span * k / (STRIP - 1))
              for k in range(STRIP)]
        frames = []
        for t in ts:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                 "-i", str(render), "-frames:v", "1", "-vf", f"scale={fw}:-1",
                 str(tmp)], check=True)
            frames.append(Image.open(tmp).convert("RGB"))
        fh = frames[0].height
        strip = Image.new("RGB", (label_w + STRIP * fw, fh), (10, 10, 16))
        d = ImageDraw.Draw(strip)
        # left label column: the beat time range + job
        d.text((8, 10), f"{b['t']}s", font=font, fill=(255, 235, 120))
        d.text((8, 36), str(b.get("job", "")), font=small, fill=(210, 210, 225))
        d.text((8, fh - 26), "start → end", font=small, fill=(120, 120, 140))
        for k, fr in enumerate(frames):
            x = label_w + k * fw
            strip.paste(fr, (x, 0))
            # per-frame within-beat timestamp so a judge can name the hold
            d.rectangle([x, 0, x + 74, 22], fill=(8, 8, 14))
            d.text((x + 5, 3), f"{ts[k]:.1f}s", font=small, fill=(255, 235, 120))
        rows.append(strip)
    tmp.unlink(missing_ok=True)
    W = rows[0].width
    H = sum(r.height for r in rows) + 4 * (len(rows) - 1)
    sheet = Image.new("RGB", (W, H), (4, 4, 8))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 4
    sheet.save(out / "beat_sheet.png")
    shutil.copy(beatmap, out / "beat_map.json")
    (out / "labels.json").write_text(json.dumps(REPAIRABLE_LABELS, indent=1))
    print(f"editorial review package -> {out}")
    print(f"beats={len(beats)} duration={dur:.1f}s strip={STRIP} "
          f"roles={list(ROLES)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render", type=Path)
    ap.add_argument("beatmap", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    build_package(a.render, a.beatmap, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
