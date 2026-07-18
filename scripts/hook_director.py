#!/usr/bin/env python3
"""THE HOOK DIRECTOR (data_learning/HOOK_DIRECTOR.md — grade & gate the opening).

Grades a proposed hook (opening VISUAL + opening LINE) against the researched
rubric: 8 hard-fail gates, a 0-5 visual score, a 0-5 line score. Pass = no gate
tripped AND visual >= 3 AND line >= 3 AND total >= 7.

The VISUAL is graded objectively from the render's opening ~2.5s (subject appeal
+ motion — a calm cloud open scores ~0.08 appeal and trips CALM_OPENER; a
designed graphic / vivid / high-contrast open scores rich). The LINE is graded
by pattern heuristics (throat-clearing / context-setting gates; points for a
curiosity void, stakes, a specific number, self-relevance, stacking).

    python3 scripts/hook_director.py --line "..." [--render out.mp4]
    from hook_director import grade

Nuanced visual judgments a metric can't make (is the subject an ANOMALY, is it
legible in <1s, is there on-screen text) are left to the hook judge subagent,
which uses the same doctrine to DESIGN a replacement when this gate fails.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STAKES = re.compile(r"\b(kill|kills|killed|deadl|danger|destroy|destroys|erase|"
                    r"erases|wipe|worst|deadliest|strongest|most powerful|never|"
                    r"terrif|impossible|nothing (?:can|on earth)|catastroph|"
                    r"lethal|violent|unstoppable|collaps|nuclear|bomb|explos|"
                    r"unleash|level a|flatten|obliterat)", re.I)
NUMBER = re.compile(r"\b\d[\d,\.]*\b|\bthousand\b|\bmillion\b|\bbillion\b")
YOU = re.compile(r"\byou\b|\byour\b|\byou're\b", re.I)
INMEDIA = re.compile(r"^(by the time|already|right now|in the middle of|seconds "
                     r"from|it's about to|watch)", re.I)
OPEN_LOOP = re.compile(r"(here's why|but (?:it|that|there)|and (?:no one|nothing|"
                       r"it builds|it's about)|what happens|until you|the reason|"
                       r"—|and it)", re.I)
THROAT = re.compile(r"\b(hey|hi|hello|welcome|what'?s up|guys|folks|subscribe|"
                    r"like and|smash that|in today'?s video)\b", re.I)
CONTEXT = re.compile(r"^(to understand|first,? we|before we|let'?s start|imagine|"
                     r"today (?:we|i)|in this video|we need to|have you ever)",
                     re.I)


def grade_line(line: str) -> dict:
    """0-5 line score + tripped gates (THROAT_CLEARING / CONTEXT_SETTING /
    NO_GAP_NO_STAKES)."""
    s = line.strip()
    gates, hits, score = [], [], 0
    if THROAT.search(s):
        gates.append("THROAT_CLEARING")
    if CONTEXT.match(s):
        gates.append("CONTEXT_SETTING")
    has_num = bool(NUMBER.search(s))
    has_stakes = bool(STAKES.search(s))
    has_you = bool(YOU.search(s))
    has_q = "?" in s
    has_loop = bool(OPEN_LOOP.search(s)) or bool(INMEDIA.match(s))
    for ok, tag in ((has_loop, "curiosity/open-loop"), (has_stakes, "stakes"),
                    (has_num, "specific-number"),
                    (has_you or bool(INMEDIA.match(s)), "you/in-media-res")):
        if ok:
            score += 1
            hits.append(tag)
    triggers = sum([has_loop, has_stakes, has_num, has_you, has_q])
    if triggers >= 2:
        score += 1
        hits.append("stacks-2+")
    if not (has_num or has_stakes or has_q or has_loop):
        gates.append("NO_GAP_NO_STAKES")
    return {"score": min(5, score), "gates": gates, "hits": hits}


def grade_visual(render: Path) -> dict:
    """0-5 visual score + gates from the render's opening ~2.5s (appeal+motion)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from interest_judge import _appeal
    import subprocess
    import numpy as np
    from io import BytesIO
    from PIL import Image

    def frame(t):
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(render),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True)
        return Image.open(BytesIO(r.stdout)).convert("RGB")
    # appeal over the opening ~2.5s
    aps = [_appeal(frame(t)) for t in (0.2, 0.9, 1.6, 2.3)]
    hook_appeal = round(sum(aps) / len(aps), 3)
    # MOTION via real per-pixel change (dense, first ~1.6s) — catches a slam, a
    # pulsing glow, streaks, a push or a cut that a coarse hash misses.
    small = [np.asarray(frame(t).resize((96, 54)).convert("L"), dtype="float32")
             for t in (0.1, 0.4, 0.7, 1.0, 1.3, 1.6)]
    diffs = [float(np.abs(small[i] - small[i - 1]).mean())
             for i in range(1, len(small))]
    opening_motion = round(max(diffs), 1)          # peak frame-to-frame change
    gates, score = [], 0
    if hook_appeal < 0.42:              # calm/bland/ambiguous open
        gates.append("CALM_OPENER")
    if opening_motion < 4.0:            # first ~1.6s barely moves
        gates.append("STATIC_FIRST_FRAME")
    score += 1 if opening_motion >= 4.0 else 0      # motion in the open
    score += 1 if hook_appeal >= 0.42 else 0        # a legible, rich subject
    score += 1 if hook_appeal >= 0.60 else 0        # genuinely striking image
    score += 1 if opening_motion >= 9.0 else 0      # strong move / slam / cut
    score += 1 if (hook_appeal >= 0.50 and opening_motion >= 6.0) else 0
    return {"score": min(5, score), "gates": gates,
            "hook_appeal": hook_appeal, "opening_motion": opening_motion}


def grade(line: str, render: Path | None = None) -> dict:
    ln = grade_line(line)
    vis = grade_visual(render) if render else {"score": 0, "gates": [],
                                               "note": "no render supplied"}
    gates = ln["gates"] + vis.get("gates", [])
    total = ln["score"] + vis["score"]
    ok = (not gates and ln["score"] >= 3 and vis["score"] >= 3 and total >= 7)
    return {"pass": ok, "total": total, "gates": gates,
            "line": ln, "visual": vis}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", required=True)
    ap.add_argument("--render", type=Path, default=None)
    a = ap.parse_args()
    print(json.dumps(grade(a.line, a.render), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
