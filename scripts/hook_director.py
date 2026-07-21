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


def grade_visual(render: Path, hook_seconds: float = 6.0) -> dict:
    """0-5 visual score + gates from the render's opening. Grades TWO things a
    hook lives or dies by: the first ~1.6s (does it SLAM in) AND whether it keeps
    moving across its whole length (a gorgeous frame HELD static for 10s is the
    single most common retention killer — 'ten seconds of clouds'). Sampling only
    the first frames is how a held shot sneaks through; we sample the whole hook."""
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
    # MOTION via LOCAL (peak-block) per-pixel change — a whole-frame mean misses a
    # counting number or a slam in a clean frame (big local change, tiny average),
    # so it wrongly called clean animation static. Peak block credits real motion;
    # a truly frozen frame still scores ~0. (Same fix as the cool judge.)
    def _local(prev, cur, gx=12, gy=7):
        d = np.abs(cur - prev)
        h, w = d.shape
        bh, bw = max(1, h // gy), max(1, w // gx)
        best = 0.0
        for y in range(0, h, bh):
            for x in range(0, w, bw):
                blk = d[y:y + bh, x:x + bw]
                if blk.size:
                    best = max(best, float(blk.mean()))
        return best
    small = [np.asarray(frame(t).resize((96, 54)).convert("L"), dtype="float32")
             for t in (0.1, 0.4, 0.7, 1.0, 1.3, 1.6)]
    opening_motion = round(max(_local(small[i - 1], small[i])
                               for i in range(1, len(small))), 1)
    span = max(2.0, min(hook_seconds, 8.0))
    ts = [round(0.3 + 0.7 * k, 2) for k in range(int((span - 0.3) / 0.7) + 1)]
    wide = [np.asarray(frame(t).resize((96, 54)).convert("L"), dtype="float32")
            for t in ts]
    wdiffs = [_local(wide[i - 1], wide[i]) for i in range(1, len(wide))] or [0.0]
    sustained_motion = round(sum(wdiffs) / len(wdiffs), 1)   # mean local, over hook
    # local scale is bigger than a whole-frame mean, so retune the floors.
    OPEN_FLOOR, HELD_FLOOR = 6.0, 4.0
    gates, score = [], 0
    # CALM is low appeal AND low motion — a bold moving graphic is not 'calm' even
    # if it isn't photographic; only a bland, still opener trips this.
    if hook_appeal < 0.42 and opening_motion < 12.0:
        gates.append("CALM_OPENER")
    if opening_motion < OPEN_FLOOR:     # first ~1.6s genuinely barely moves
        gates.append("STATIC_FIRST_FRAME")
    if sustained_motion < HELD_FLOOR:   # a HELD shot — it just sits there
        gates.append("HELD_STATIC")
    score += 1 if opening_motion >= OPEN_FLOOR else 0
    score += 1 if hook_appeal >= 0.42 else 0
    score += 1 if (hook_appeal >= 0.60 or opening_motion >= 40) else 0
    score += 1 if opening_motion >= 18 else 0        # a strong slam / cut
    score += 1 if sustained_motion >= HELD_FLOOR else 0
    if sustained_motion < HELD_FLOOR:   # a held shot cannot score above a floor
        score = min(score, 2)
    return {"score": min(5, score), "gates": gates, "hook_appeal": hook_appeal,
            "opening_motion": opening_motion, "sustained_motion": sustained_motion}


def grade(line: str, render: Path | None = None,
          hook_seconds: float = 6.0) -> dict:
    ln = grade_line(line)
    vis = grade_visual(render, hook_seconds) if render else {
        "score": 0, "gates": [], "note": "no render supplied"}
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
