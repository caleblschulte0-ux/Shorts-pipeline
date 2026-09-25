#!/usr/bin/env python3
"""The SHOWRUNNER — a headless Claude that WATCHES each rendered video and
enforces the channel's taste bar (docs/DIRECTOR.md) before it is allowed to
post. This is the editor with a veto the pipeline never had: "it rendered" is
not a passing grade.

It samples frames across the finished mp4, sends them (vision) to Claude along
with the rubric and the per-scene plan, and gets back a scored verdict. If the
video is boring or sloppy (score below the bar, or any hard auto-fail like a
junk image or a floating do-nothing mascot), the verdict is BLOCK and the
uploader skips it.

Design notes:
- Judges via the Claude HEADLESS BRAIN — the `claude` CLI in print mode on the
  CLAUDE_CODE_OAUTH_TOKEN subscription, the SAME mechanism the pipeline's brain
  step already uses. NOT the paid Anthropic API. The CLI Reads the sampled
  frame images itself (vision). Free Gemini vision is the only fallback.
- Infrastructure problems (CLI missing, timeout, ffmpeg error) RAISE. What
  that means for the video is not this module's call: every publishing
  channel routes the outcome through `shared/showrunner_gate.decide()`,
  which fails OPEN on a preview run and CLOSED on a real publish run — an
  infra failure is not evidence of quality, and it is not approval either.
- Model: the CLI 'opus' alias (override with SHOWRUNNER_MODEL).

CLI:
    python scripts/showrunner_review.py output/story_x.mp4 [--context ctx.json]
    # exit 0 = ship, 2 = block, 1 = skipped/errored — on a PUBLISH run the
    # shared gate treats 1 as a hold (fail-closed); only previews proceed
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUBRIC_PATH = REPO / "docs" / "DIRECTOR.md"
MODEL = os.environ.get("SHOWRUNNER_MODEL", "opus")
MIN_SCORE = int(os.environ.get("SHOWRUNNER_MIN_SCORE", "70"))
N_FRAMES = int(os.environ.get("SHOWRUNNER_FRAMES", "14"))

# Rubric weights (docs/DIRECTOR.md) as (weight_out_of_100, grade_ceiling). The
# MODEL grades observable quality on the small anchored ceiling; the CODE turns
# those grades into the 100-pt score and decides pass/fail. The model is NEVER
# told the passing threshold — that is what stops the score compressing to a
# safe ~72 every time.
WEIGHTS = {
    "hook": (18, 4), "data_demo": (22, 5), "mascot": (18, 4),
    "craft": (12, 3), "pace": (8, 2), "payoff": (8, 2),
    # temporal_craft is graded IN CODE from measured cadence (effective fps /
    # duplicate-frame ratio), NOT by the model — so choppy motion materially
    # costs points and a laggy video can't score 90 on pretty stills.
    "temporal_craft": (14, 3),
}
# Hard auto-fail checks. The model must answer EVERY one (present + evidence);
# code BLOCKS if any is present, regardless of the numeric score. These are the
# rubric's hard rules — they are not suggestions.
AUTOFAIL_CHECKS = ["junk_imagery", "decorative_mascot", "bare_number_card",
                   "dead_air", "empty_void", "unreadable"]
# `unreadable` was added on 2026-09-09, and the reason is the whole point of
# having a gate. The operator watched a video this gate had PASSED and read
# back what was on screen:
#
#     8s   "90 (pre-vaccine)"       the leading "19" outside the frame
#     28s  "Not yet vaccinated  9"  the percent sign outside the frame
#     20s  two labels printed on top of one another, unreadable
#     36s  the mascot standing on the title, covering "vaccinated"
#
# The judge was RIGHT to pass it. Every hard check it had — junk_imagery,
# decorative_mascot, bare_number_card, dead_air, empty_void — is about
# CONTENT and MOTION. Not one is about whether the frame can be READ, so
# there was no box to tick for a label cut off at the edge.
#
# That is a gap in the AUTHORITY, not in the five machines that happened to
# be caught fixing it the same evening. A quality bar that cannot see
# illegibility will ship illegible videos for as long as it exists, and the
# next renderer reintroduces it the day after the last one is patched.
#
# It is deliberately NOT in FATAL_CHECKS. Under the `rebuild` policy only
# junk_imagery hard-blocks, and a channel that has just started posting
# again should not be stopped by a check on its first day — but it is asked,
# answered, recorded in the verdict and the ledger, and it blocks under
# `standard`, which is what the explainer runs.

# DECISION POLICY — which auto-fails hard-block, and at what floor.
#
# "standard" is the rule as it has always been: ANY auto-fail blocks, floor
# MIN_SCORE. "rebuild" is an INTERIM OPERATOR RULING (2026-08-13, twice
# reaffirmed: "I don't care if the quality dips ... we should never not be
# posting"): only the FATAL classes hard-block, and the numeric floor —
# lowered by env in the one workflow that opts in — decides the rest.
#
# The ruling was made against measured data, not vibes. Of 23 blocks in the
# ledger since 08-11, ZERO were held by the score floor alone — every hold
# was the any-auto-fail rule, and the craft classes (empty_void,
# decorative_mascot, bare_number_card, dead_air) held videos the judge
# itself scored 55-78. Fourteen days of zero posts on the explainer channel
# is the outcome the operator overruled.
#
# What "rebuild" does NOT change, ever:
#   * the brain still watches every video and grades exactly as before —
#     nothing here touches the judge, the rubric, or its sovereignty;
#   * junk_imagery still blocks at ANY score: mismatched or misleading
#     imagery is a trust defect, not a craft one, and "quality can dip"
#     does not cover publishing visuals that misrepresent the data;
#   * the measured temporal gate (frozen/choppy video) still blocks in code;
#   * a publish run still fails CLOSED on no-verdict/infra-error/timeout;
#   * every craft check is still recorded in the verdict, the ledger and
#     the fix notes — the repair loop and the retro keep working the
#     backlog while the channel posts.
#
# To END the rebuild: delete the SHOWRUNNER_POLICY / SHOWRUNNER_MIN_SCORE
# env lines from the workflow that set them. Defaults restore "standard"/70.
POLICY = os.environ.get("SHOWRUNNER_POLICY", "standard").strip() or "standard"
FATAL_CHECKS = ("junk_imagery",)


def _format_directive(ctx: dict) -> str:
    """Translate the shared quality bar for the format actually rendered.

    ChatGPT added this on 2026-08-02 after the generic data-story wording
    blocked two correctly rendered Reddit narratives for not demonstrating a
    statistic. The gate remains sovereign; only an inapplicable criterion is
    translated into the format's equivalent visual-demonstration standard.
    """
    fmt = str((ctx or {}).get("format") or "").strip().lower()
    if fmt == "reddit_story":
        return (
            "FORMAT = REDDIT STORY. This is a narrative, not a statistics "
            "explainer. Grade data_demo by whether the cause/effect story "
            "beats are visibly demonstrated with changing, relevant shot "
            "illustrations plus gameplay/captions; do not demand numbers, a "
            "chart, or a data claim. bare_number_card is relevant only if an "
            "actual number card appears. Data is the separate Explainer "
            "channel mascot: if any mascot appears here, mark "
            "decorative_mascot present. If none appears, grade mascot=4 for "
            "correct channel-brand separation.")
    if fmt == "graph_race":
        return (
            "FORMAT = GRAPH RACE. The growing lines, moving tips, changing "
            "leaderboard, and year counter are the data demonstration. Data "
            "is the separate Explainer channel mascot: if any mascot appears "
            "here, mark decorative_mascot present. If none appears, grade "
            "mascot=4 for correct channel-brand separation. A one-series "
            "growth chart has a scale payoff, not a competitive winner.")
    if fmt == "sleep":
        return (
            "FORMAT = SLEEP FILM (OpenRangeInteractive long-form: about two "
            "hours, 16:9, a calm narrated history story people fall asleep "
            "to, often with the screen face down). Every picture is a "
            "hand-drawn cartoon scene (round-headed people, ink outlines) "
            "made by code, one per narrated passage, each dissolving into "
            "the next; there are no numbers on screen. The rubric applies "
            "in full; translate its terms to what this audience needs, never "
            "lower a bar. There is no mascot: if none appears, grade "
            "mascot=4 for correct channel separation; if one appears, mark "
            "decorative_mascot present. hook: the opening frames must set "
            "the place and time and invite the listener in (a title over an "
            "inviting scene) — a jolt or a blank opening fails it. "
            "data_demo: grade whether each scene SHOWS what the narration "
            "says at that moment (narration_at_frame in the context gives the line "
            "spoken at each sampled frame, by its label): the right "
            "era and place, the people doing the activity described. "
            "junk_imagery is present if a scene contradicts or is unrelated "
            "to its line (wrong era, a modern object, the wrong activity) "
            "or the same picture repeats back to back. pace: steady is "
            "correct here — grade whether scenes change at a regular rhythm "
            "with no abrupt cuts and no long stretch where the picture "
            "stops living; slowness itself is the format, not a flaw. "
            "payoff: the ending should wind down (night, rest, a quiet last "
            "scene), not stop mid-thought. craft: a consistent drawn style, "
            "readable characters, and nothing broken (detached limbs, props "
            "drawn through people, clipped figures). bare_number_card "
            "applies only if a number card appears. dead_air, empty_void "
            "and unreadable apply exactly as written — night scenes are "
            "deep blue and firelit, never black.")
    return "Apply the general director rubric exactly as written."


def compute_score(dims: dict) -> int:
    """Turn anchored dimension grades into the weighted 100-pt score. In CODE,
    not by asking the model for the total."""
    total = 0.0
    for k, (w, ceil) in WEIGHTS.items():
        g = max(0, min(ceil, int(dims.get(k, 0))))
        total += w * g / ceil
    return round(total)


def apply_motion_override(checks: dict, motion: dict) -> dict:
    """Objective override: code measures whether motion EXISTS; the model can't
    average a real dead hold away. Returns a NEW checks dict (never mutates)."""
    checks = dict(checks or {})
    if (motion or {}).get("longest_static_s", 0) >= 4.0:
        checks["dead_air"] = {
            "present": True,
            "evidence": f"code: {motion['longest_static_s']}s frozen"}
    return checks


def failed_autofails(checks: dict) -> list:
    """Which hard auto-fail checks are PRESENT — code BLOCKS on any of these
    regardless of the numeric score. The rubric's hard rules, not suggestions."""
    return [k for k in AUTOFAIL_CHECKS
            if isinstance((checks or {}).get(k), dict) and checks[k].get("present")]


def validate_judge_response(grades: dict) -> list:
    """Sanity-check the judge's JSON against the schema `_GRADE_PROMPT` asked
    for. Non-empty return means the response cannot be trusted to score or
    grade: every WEIGHTS dimension and every AUTOFAIL_CHECKS key must be
    present with the right shape, or `review_video` blocks outright rather
    than letting a missing/malformed answer read as a silent pass (an empty
    or partial `checks` object previously computed zero auto-fails)."""
    problems = []
    dims = (grades or {}).get("dimensions")
    if not isinstance(dims, dict):
        problems.append("dimensions missing or not an object")
    else:
        for k, (_, ceil) in WEIGHTS.items():
            if k == "temporal_craft":
                continue  # code-graded, not part of the judge's answer
            v = dims.get(k)
            if isinstance(v, bool) or not isinstance(v, int) or not (0 <= v <= ceil):
                problems.append(f"dimensions.{k} missing or out of range 0-{ceil}")
    checks = (grades or {}).get("checks")
    if not isinstance(checks, dict):
        problems.append("checks missing or not an object")
    else:
        for k in AUTOFAIL_CHECKS:
            c = checks.get(k)
            if not isinstance(c, dict):
                problems.append(f"checks.{k} missing or not an object")
                continue
            if not isinstance(c.get("present"), bool):
                problems.append(f"checks.{k}.present missing or not boolean")
            if not str(c.get("evidence") or "").strip():
                problems.append(f"checks.{k}.evidence missing or empty")
    return problems


def decide_verdict(score: int, checks: dict, *, policy: str | None = None,
                   min_score: int | None = None) -> str:
    """The single ship/block rule, pure so the calibration fixtures can pin
    it in CI. "standard": ANY auto-fail blocks, floor MIN_SCORE — unchanged
    from the day it was written. "rebuild" (interim operator ruling, see
    POLICY above): only FATAL_CHECKS hard-block; craft auto-fails are
    recorded and repair-targeted but the numeric floor decides."""
    policy = policy if policy is not None else POLICY
    floor = min_score if min_score is not None else MIN_SCORE
    fails = failed_autofails(checks)
    if policy == "rebuild":
        fatal = [f for f in fails if f in FATAL_CHECKS]
        return "block" if (fatal or score < floor) else "ship"
    return "block" if (fails or score < floor) else "ship"


def _duration(mp4: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp4)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 40.0


def _frame_plan(dur: float, manifest: dict | None):
    """(timestamp, label) samples that actually cover the beats — a burst in the
    first 2s (hook motion), the start/mid/end of every segment, and the payoff
    tail — instead of 6 blind evenly-spaced stills. Uses the render manifest's
    segment windows when present; falls back to a dense even sweep otherwise."""
    plan = [(0.3, "hook@0.3"), (0.8, "hook@0.8"), (1.5, "hook@1.5"),
            (2.2, "hook@2.2")]
    wins = (manifest or {}).get("segment_windows")
    if not wins and (manifest or {}).get("chapters"):
        # LONG-FORM: `longform_render` writes chapters (start second + label),
        # not segment windows — the same information in the shape that video
        # actually has. Turn consecutive chapter starts into windows so the
        # judge samples each chapter settled rather than sweeping blind.
        chs = sorted((float(c.get("t", 0.0)) for c in manifest["chapters"]
                      if isinstance(c, dict)))
        wins = [[chs[i], (chs[i + 1] if i + 1 < len(chs) else dur)]
                for i in range(len(chs))]
        wins = [w for w in wins if w[1] - w[0] > 1.0]
    if wins:
        for i, (s0, s1) in enumerate(wins):
            # Sample SETTLED moments, not the transition-in (mascot still gliding,
            # elements still fading) — judging a beat by its 8%-in frame is unfair
            # and was misreading composed beats as empty.
            for f, tag in ((0.25, "start"), (0.55, "mid"), (0.85, "end")):
                plan.append((s0 + f * (s1 - s0), f"seg{i}:{tag}"))
    else:
        # SIX STILLS IS A SHORTS NUMBER. It covers a 40s vertical fine; on a
        # 5-8 minute 16:9 long-form it is one glance per ~60 seconds, and a
        # judge that never sees minute 4 cannot honestly say the video holds
        # up — it would rubber-stamp exactly the dead middle a watch-page
        # video dies of. Scale the sweep with duration (~one sample per 12s,
        # bounded) so a long-form is actually watched, and keep the classic
        # six for anything short so no existing verdict shifts.
        n = 6 if dur <= 90 else max(6, min(28, int(dur // 12)))
        for k in range(n):
            t = 2.5 + (dur - 4.5) * k / max(1, n - 1)
            plan.append((t, f"mid{k}"))
    plan.append((max(0.0, dur - 1.8), "payoff@-1.8"))
    plan.append((max(0.0, dur - 0.4), "payoff@-0.4"))
    # de-dup / clamp / sort
    seen, out = set(), []
    for t, lab in sorted(plan):
        ts = round(min(max(t, 0.0), max(0.0, dur - 0.05)), 2)
        if ts in seen:
            continue
        seen.add(ts)
        out.append((ts, lab))
    return out


def _extract_frames(mp4: Path, td: Path, manifest: dict | None = None):
    """Extract the planned frames. Returns [(path, label, ts), ...]."""
    dur = _duration(mp4)
    frames = []
    for i, (t, lab) in enumerate(_frame_plan(dur, manifest)):
        out = td / f"f{i:02d}.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                 "-i", str(mp4), "-frames:v", "1", "-vf", "scale=430:-1",
                 str(out)], check=True)
            if out.exists():
                frames.append((out, lab, t))
        except Exception:  # noqa: BLE001
            continue
    return frames


def _max_block_diff(a, b, w: int, grid: int = 12) -> float:
    """Max, over a GRID of blocks, of the mean absolute gray difference in that
    block. This is the honest 'did anything move?' signal: a held/duplicated
    frame reads ~0 in EVERY block, while a smoothly-but-locally animating region
    (a chart filling, the mascot gliding) spikes the one block it lives in — even
    when it's a small slice of the frame. A whole-frame MEAN can't tell those
    apart (it dilutes localized motion below any sane threshold and then calls a
    smooth build 'frozen'), which is exactly what pinned temporal_craft at 0."""
    h = len(a) // w if w else 0
    if h < grid:
        # too small to block — fall back to whole-frame mean
        return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))
    bw = max(1, w // grid)
    bh = max(1, h // grid)
    best = 0.0
    for by in range(0, h - bh + 1, bh):
        for bx in range(0, w - bw + 1, bw):
            s = 0
            for yy in range(bh):
                base = (by + yy) * w + bx
                for xx in range(bw):
                    s += abs(a[base + xx] - b[base + xx])
            m = s / (bw * bh)
            if m > best:
                best = m
    return best


# A block whose mean gray shifts by more than this HAS motion; below it the
# frame is a genuine hold (encoder noise on a static frame stays ~0-2). Chosen
# above the noise floor and far below real motion (measured 10-60 on live
# builds) — see data_learning/tests/test_showrunner_scoring.py.
BLOCK_MOTION_THRESH = 6.0


def _gray_stream(mp4: Path, fps: int, width: int):
    """Yield every sampled frame of `mp4` as a flat numpy uint8 gray array,
    decoded through the SAME filter chain the probes always used
    (`fps=N,scale=W:-1,format=gray`) but piped as raw bytes instead of
    written to PNGs and held in Python lists. Holding them was fine for a
    40-second short; a two-hour long-form is 172,800 frames at 24fps and
    ran out of memory, which the gate would have read as an unmeasured
    probe and held forever. Pixel values are identical: the PNGs were
    lossless copies of these same bytes (`tests/test_showrunner_probe_stream.py`
    holds the old implementation as the oracle). Returns (w, h) first."""
    import numpy as np
    vf = f"fps={fps},scale={width}:-1,format=gray"
    head = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", vf, "-frames:v", "1",
         "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True)
    data = getattr(head, "stdout", b"") or b""
    if not data:
        # ffmpeg decoded nothing: no frames at all, which the callers report
        # as "only 0 sampled frames" — an unmeasured probe, never a pass
        yield (0, 0)
        return
    from PIL import Image
    import io
    with Image.open(io.BytesIO(data)) as im:
        w, h = im.size
    yield (w, h)
    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", vf, "-f", "rawvideo",
         "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    try:
        n = w * h
        while True:
            buf = proc.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, dtype=np.uint8)
    finally:
        proc.stdout.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited {rc} decoding {Path(mp4).name}")


def _max_block_diff_np(a, b, w: int, grid: int = 12) -> float:
    """`_max_block_diff` in numpy, exactly: the same blocks (bw = w//grid,
    bh = h//grid, as many whole blocks as fit), each block's integer sum of
    absolute differences divided by its pixel count, the max of those."""
    import numpy as np
    h = len(a) // w if w else 0
    ai = a.astype(np.int32)
    bi = b.astype(np.int32)
    if h < grid:
        return float(np.abs(ai - bi).sum()) / max(1, len(a))
    bw = max(1, w // grid)
    bh = max(1, h // grid)
    rows, cols = h // bh, w // bw
    d = np.abs(ai[: h * w].reshape(h, w) - bi[: h * w].reshape(h, w))
    d = d[: rows * bh, : cols * bw].reshape(rows, bh, cols, bw).sum(axis=(1, 3), dtype=np.int64)
    return float(d.max()) / (bw * bh)


def _motion_evidence(mp4: Path, td: Path) -> dict:
    """Objective, code-measured motion facts (NOT a judgement). Samples the whole
    clip at ~3fps and reports the longest near-frozen run (seconds) and the
    fraction of near-black frames. Vision judges whether motion is *meaningful*;
    this decides whether motion *exists* — so 'dead air' can't be averaged away."""
    ev = {"longest_static_s": 0.0, "static_at_s": None, "dark_fraction": 0.0,
          "sampled": 0}
    try:
        from collections import deque
        fps = 3
        # 160px (was 96) so a moving mascot registers as motion the way a human
        # sees it — 96px was too coarse and false-flagged a moving closing.
        stream = _gray_stream(mp4, fps, 160)
        w, _h = next(stream)
        lb = fps
        window: deque = deque(maxlen=lb + 1)
        n = dark = 0
        run = best = best_end = 0
        for i, px in enumerate(stream):
            n += 1
            if float(px.sum(dtype="int64")) / len(px) < 22:
                dark += 1
            window.append(px)
            # DEAD AIR = a stretch where NO block changes over ~1s (1s LOOKBACK, not
            # consecutive frames) so a SMOOTH build reads as motion; only a genuine
            # static hold registers. Block-max (not a whole-frame mean) so a small
            # animating region still counts as motion. Also report WHERE it starts.
            if i >= lb:
                diff = _max_block_diff_np(window[-1], window[0], w)
                if diff < BLOCK_MOTION_THRESH:
                    run += 1
                    if run > best:
                        best, best_end = run, i
                else:
                    run = 0
        ev["sampled"] = n
        if n < 2:
            return ev
        ev["dark_fraction"] = round(dark / n, 3)
        ev["longest_static_s"] = round(best / fps, 2)
        if best:
            ev["static_at_s"] = round((best_end - best) / fps, 2)   # run start
    except Exception as e:  # noqa: BLE001
        ev["error"] = str(e)[:120]
    return ev


def _temporal_evidence(mp4: Path, td: Path) -> dict:
    """CADENCE facts: does the video actually move at its export rate, or is a
    low-fps source animation duplicated into a 30fps timeline (visible judder)?
    Samples at 24fps and reports the duplicate-frame ratio, the EFFECTIVE unique
    frame rate, and the longest duplicate run. Objective — this is what a 90 on
    pretty stills was hiding."""
    ev = {"sample_fps": 24, "duplicate_ratio": None, "effective_fps": None,
          "max_dup_run": None, "measured": False}
    try:
        sf = 24
        stream = _gray_stream(mp4, sf, 192)
        w, _h = next(stream)
        prev = None
        n = 0
        dup = run = maxrun = 0
        run_start = maxrun_start = 0
        for px in stream:
            if prev is not None:
                _i = n - 1
                # Block-max, not a whole-frame mean: a frame is a DUPLICATE only if
                # NO block moved. A whole-frame mean diluted a chart that fills part
                # of the frame down below 0.8 and mislabelled smooth builds as held
                # (effective_fps ~10 on a genuinely-30fps render). Choppy low-fps
                # source dup still shows identical blocks -> still caught.
                if _max_block_diff_np(prev, px, w) < BLOCK_MOTION_THRESH:
                    dup += 1
                    if run == 0:
                        run_start = _i
                    run += 1
                    if run > maxrun:
                        maxrun, maxrun_start = run, run_start
                else:
                    run = 0
            prev = px
            n += 1
        if n < 3:
            ev["error"] = f"only {n} sampled frames — nothing to measure"
            return ev
        pairs = n - 1
        ev["duplicate_ratio"] = round(dup / pairs, 3)
        ev["effective_fps"] = round(sf * (1 - dup / pairs), 1)
        ev["max_dup_run"] = maxrun + 1        # frames
        # WHERE it froze, not just that it did. Every frozen-stretch block so
        # far has cost a full render to localise by guesswork; the timestamp
        # turns the next one into a single look at the video.
        ev["max_dup_at_s"] = round(maxrun_start / float(sf), 2)
        ev["duration_s"] = round(n / float(sf), 2)
        ev["measured"] = True
    except Exception as e:  # noqa: BLE001
        ev["error"] = str(e)[:120]
    return ev


def temporal_unmeasured(ev: dict) -> str | None:
    """Why the cadence probe produced no measurement, or None if it did.

    Doctor finding 3de32f29a8e4: every failure in here — ffmpeg missing, a
    PIL decode error, too few sampled frames, the milestone import — was
    swallowed into `ev["error"]` and left the numbers as None. Downstream,
    `temporal_hard_fail` returned "no failure" for unknown and
    `temporal_grade` awarded a neutral 2, so a probe that measured NOTHING
    reached the vision judge as ordinary evidence and could ship with a
    bounded score. Nothing raised, so the fail-closed outer gate saw a
    complete verdict and had no reason to hold.

    "Never block blind" is right for the code FLOOR — it may only add blocks
    on measured badness. It is not a licence to publish blind. So the
    unknown state is surfaced as an infra failure and `review_video` raises,
    which is the one place this repo decides publish-vs-preview:
    `shared/showrunner_gate.decide()` turns a raise into a HOLD on a publish
    run and a skip on a preview."""
    if ev.get("measured"):
        return None
    why = ev.get("error") or "no measurement and no reason recorded"
    return f"cadence probe produced no measurement: {why}"


def temporal_grade(ev: dict) -> int:
    """0-3 temporal-craft grade from measured effective fps (30 = buttery)."""
    fps = ev.get("effective_fps")
    if fps is None:
        return 2                              # unknown -> neutral, don't punish blind
    if fps >= 24:
        return 3
    if fps >= 17:
        return 2
    if fps >= 11:
        return 1
    return 0


def temporal_hard_fail(ev: dict) -> str | None:
    """CODE hard-fail on measured cadence, evaluated BEFORE the vision review
    (ChatGPT: 'add a hard build failure ... do this before the expensive vision
    review'). Thresholds come from the active quality phase (milestones), so the
    floor RISES phase by phase instead of jumping straight to a bar that blocks
    everything. Returns the failure reason, or None when the render passes.
    This gate only ADDS blocks on measured badness — it never blocks blind.
    Unknown evidence still returns None here, but it no longer reaches this
    function on a real review: `review_video` raises on an unmeasured probe
    so the outer gate decides publish-vs-preview (3de32f29a8e4)."""
    fps = ev.get("effective_fps")
    dup = ev.get("duplicate_ratio")
    run = ev.get("max_dup_run")
    if fps is None or dup is None:
        return None
    try:
        try:
            from data_learning.quality_milestones import active_phase
        except ImportError:
            sys.path.insert(0, str(REPO))
            from data_learning.quality_milestones import active_phase
        ph = active_phase()
    except Exception as e:  # noqa: BLE001
        # Measured cadence with no floor to measure it against is not a
        # pass, it is an unapplied gate. Raising lets showrunner_gate decide
        # publish-vs-preview instead of quietly grading everything neutral.
        raise RuntimeError(
            f"quality milestones unavailable ({e}) — the temporal floor "
            "cannot be applied, so this render is unjudged") from e
    if fps < ph.min_effective_fps:
        return (f"effective_fps {fps} < {ph.min_effective_fps} "
                f"({ph.name} floor) — low-fps source in a 30fps master")
    if dup > ph.max_duplicate_ratio:
        return (f"duplicate_ratio {dup} > {ph.max_duplicate_ratio} "
                f"({ph.name} ceiling) — too many held frames")
    if run is not None and run > ph.max_dup_run_frames:
        at = ev.get("max_dup_at_s")
        dur = ev.get("duration_s")
        where = ""
        if at is not None:
            where = (f" starting at t={at}s"
                     + (f" of {dur}s" if dur else "")
                     + f" (~{round(run / 24.0, 1)}s frozen)")
        return (f"max_dup_run {run} frames > {ph.max_dup_run_frames} "
                f"({ph.name} ceiling) — a frozen stretch outside any "
                f"intentional hold{where}")
    return None


def _b64(p: Path) -> str:
    return base64.standard_b64encode(p.read_bytes()).decode()


def _rubric() -> str:
    try:
        return RUBRIC_PATH.read_text()
    except Exception:  # noqa: BLE001
        return "Be an exacting creative director. Block boring or sloppy videos."


def _rubric_sha() -> str:
    import hashlib
    try:
        return hashlib.sha1(RUBRIC_PATH.read_bytes()).hexdigest()[:10]
    except Exception:  # noqa: BLE001
        return "?"


GEMINI_API = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
GEMINI_MODEL = os.environ.get("SHOWRUNNER_GEMINI_MODEL", "gemini-2.5-flash")


def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def _headless_claude_judge(prompt: str, labeled) -> dict:
    """Deliver the grade prompt + labelled frames to the Claude HEADLESS BRAIN
    (the `claude` CLI on the CLAUDE_CODE_OAUTH_TOKEN subscription — NOT the API).
    The CLI Reads each frame image itself. Raises on any failure."""
    if not shutil.which("claude"):
        raise RuntimeError("claude CLI not installed (npm i -g @anthropic-ai/claude-code)")
    listing = "\n".join(f"- {lab} (t={ts:.2f}s): {p}" for p, lab, ts in labeled)
    full = (prompt + "\n\nThe frames are these image files — READ each one with "
            "the Read tool before grading; the label says WHERE in the video it "
            "is:\n" + listing + "\n\nReturn ONLY the JSON object, no prose.")
    model = os.environ.get("SHOWRUNNER_MODEL", "opus")
    timeout = int(os.environ.get("SHOWRUNNER_TIMEOUT", "480"))
    proc = subprocess.run(
        ["claude", "-p", full, "--model", model,
         "--allowedTools", "Read", "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI rc={proc.returncode}: {(proc.stderr or proc.stdout)[:200]}")
    return parse_judge_json(proc.stdout or "", repair=_repair_json_via_cli)


def _balanced_objects(text: str):
    """Every top-level {...} span in `text`, by brace depth (quotes
    respected), outermost first. Prose before/after and a SECOND object
    ("here is the JSON: {...} — and a note {...}") no longer confuse it."""
    out, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
    return out


def parse_judge_json(text: str, repair=None) -> dict:
    """The judge's JSON out of whatever the judge actually printed.

    THREE TIMES ON 2026-09-21 the headless brain graded a video and the
    grade was thrown away: `Expecting ',' delimiter: line 7 column 1395`,
    three attempts in a row on `amazon-still-shrinking`, and the same at
    17:33 on `global-ewaste-crisis`. Each time the verdict text was there —
    a stray unescaped quote inside a string, or prose around the object —
    and `re.search(r"\\{.*\\}")` + `json.loads` had no second idea. Three
    identical retries cost ~15 minutes of judge time and then the gate
    failed CLOSED on a video the brain had watched and graded.

    Recovery, in order, each one strictly a parse of what the judge wrote:
      1. the whole text;  2. the text with ``` fences stripped;
      3. each balanced top-level object, largest first;
      4. `repair(text)` — a model asked ONLY to make the same JSON parse
         (no frames, no grading), then steps 1-3 on its answer.
    Nothing here changes a grade. If none of it parses, raise, and the gate
    still holds.
    """
    raw = (text or "").strip()
    if not raw:
        raise RuntimeError("no JSON in judge output: (empty)")
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S | re.M).strip()
    tries = [raw, fenced]
    tries += sorted(_balanced_objects(raw), key=len, reverse=True)
    last = None
    for cand in tries:
        try:
            got = json.loads(cand)
            if isinstance(got, dict):
                return got
        except json.JSONDecodeError as e:
            last = e
    if repair is not None:
        try:
            fixed = repair(raw)
        except Exception as e:  # noqa: BLE001 — the repair is best-effort
            fixed = None
            last = last or e
        if fixed:
            return parse_judge_json(fixed, repair=None)
    raise RuntimeError(f"no JSON in judge output ({last}): {raw[:200]}")


def _repair_json_via_cli(broken: str) -> str | None:
    """Ask the headless brain to make its OWN output parse — no frames, no
    rubric, no grading — and return what it prints. The fix is checked by
    `parse_judge_json`, never trusted."""
    if not shutil.which("claude"):
        return None
    ask = ("The text below is meant to be ONE JSON object but does not parse "
           "(a stray quote, a missing comma, or prose around it). Return the "
           "SAME object as valid JSON — same keys, same values, same numbers, "
           "escape quotes inside strings. Output ONLY the JSON.\n\n" + broken[:20000])
    try:
        proc = subprocess.run(
            ["claude", "-p", ask, "--model",
             os.environ.get("SHOWRUNNER_REPAIR_MODEL", "sonnet"),
             "--output-format", "text"],
            capture_output=True, text=True,
            timeout=int(os.environ.get("SHOWRUNNER_REPAIR_TIMEOUT", "120")))
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout or None


def _gemini_judge(prompt: str, labeled) -> dict:
    parts: list = []
    for p, lab, ts in labeled:
        parts.append({"text": f"Frame {lab} (t={ts:.2f}s):"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _b64(p)}})
    parts.append({"text": prompt + "\n\nReturn ONLY the JSON object, no prose."})
    url = GEMINI_API.format(model=GEMINI_MODEL, key=os.environ["GEMINI_API_KEY"])
    resp = _post_json(url, {
        "contents": [{"role": "user", "parts": parts}],
        # 2000 truncated the verdict mid-string ("Unterminated string starting
        # at line 11"), so the ONLY fallback judge died of a parse error at the
        # exact moment the headless brain was rate-limited and the channel had
        # nothing left to grade with. Give the verdict room to finish.
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": 0.2, "maxOutputTokens": 8000}},
        {"content-type": "application/json"})
    txt = resp["candidates"][0]["content"]["parts"][0]["text"]
    # A verdict cut off mid-object or wrapped in prose is still evidence:
    # the same recovery ladder as the headless brain, still failing CLOSED
    # when nothing parses.
    return parse_judge_json(txt)


def _judge(prompt: str, labeled):
    """Returns (grades_dict, backend_used). Headless brain is the judge of
    record (retried); free Gemini is the only fallback. The backend that
    actually produced the grades is reported (no more mislabelling)."""
    import time
    errs = []
    for attempt in range(int(os.environ.get("SHOWRUNNER_RETRIES", "3"))):
        try:
            return _headless_claude_judge(prompt, labeled), "headless-claude"
        except Exception as e:  # noqa: BLE001
            errs.append(f"headless-claude[{attempt}]: {e}")
            time.sleep(3 * (attempt + 1))
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return _gemini_judge(prompt, labeled), "gemini-fallback"
        except Exception as e:  # noqa: BLE001
            errs.append(f"gemini: {e}")
    raise RuntimeError(f"no vision judge available. {errs}")


_GRADE_PROMPT = """You are the SHOWRUNNER — the channel's editor with a veto. \
GRADE what you actually SEE in the frames (labels say where in the timeline each \
sits), against the rubric below. Do NOT output an overall score or a pass/fail — \
you only grade the anchors and answer the hard checks; the code decides.

Grade each dimension on its anchor (0 = absent/broken, top = exemplary):
  hook 0-4, data_demo 0-5, mascot 0-4, craft 0-3, pace 0-2, payoff 0-2

Answer EVERY hard check with present (true/false) + one-line evidence citing a \
frame label. Be strict — these are hard rules, not vibes:
  junk_imagery        an AI/stock image or garbled cutout that doesn't belong
  decorative_mascot   the mascot merely stands/slides/perches, no real bit tied
                      to the stat (a setup->action->payoff)
  bare_number_card    a beat that is just a big number on a background, not a
                      demonstration
  dead_air            >= ~4s where nothing meaningful moves / two beats identical
  empty_void          large dead/black areas; the frame's space is wasted
  unreadable          ANY text a viewer cannot read on a phone: cut off by
                      the frame edge (a label reading "90 (" that should say
                      "1990 ("), printed on top of other text, covered by
                      the mascot or a mark, or so low-contrast against its
                      background that it disappears. Judge it as a phone
                      held at arm's length, not as a still you can zoom: if
                      you have to work out what a label says, it is present.

MOTION FACTS (measured in code, not opinion) — use them, especially for dead_air \
and empty_void:
{motion}

FORMAT CONTRACT (authoritative for how this format demonstrates its content):
{format_directive}

DEPICTION GRADES (required, one per segment you can see, hook excluded). This \
is a LEARNING signal for the brain that invents the visuals — it never decides \
ship or block. Grade each segment's picture on two anchors, 0-3:
  bespoke      3 = the picture is MADE OF the subject and the subject's own
                   physics carries the number (a grid of laser bolts, each one
                   0.2 MJ, filling to the value; a lake whose shoreline recedes
                   to the lost area). Nothing generic remains.
               2 = a real invented form for THIS story, but a generic element
                   still carries the number (a subject-shaped vessel filling).
               1 = a stock machine with a subject icon dropped in —
                   a track with a dog on it, a seesaw with a cat, two tubes,
                   a timeline cross. The icon could be swapped for any subject.
               0 = a chart (bars, a line, a donut, a waffle).
  proves_claim 3 = a viewer sees the number's meaning without reading it;
               0 = the picture asserts nothing the label does not.
Name the kind you saw: "bespoke" | "machine" | "chart". One short note.
Your whole reply must PARSE as JSON: escape any double quote inside a string \
(write \\"), no trailing commas, nothing before the opening brace or after the \
closing one.

STRUCTURED DIAGNOSIS (required): identify the WEAKEST SCENE by its frame-label \
segment id (segN as printed on the frame labels; the hook is "hook"). If you \
would block this video you MUST name the scene that most needs repair, the \
failure class, the visible evidence, the root cause, and a concrete repair \
goal — the repair system targets that scene directly, it does not parse prose.

Return ONLY this JSON:
{{"dimensions":{{"hook":int,"data_demo":int,"mascot":int,"craft":int,"pace":int,"payoff":int}},
 "checks":{{"junk_imagery":{{"present":bool,"evidence":str}},"decorative_mascot":{{"present":bool,"evidence":str}},
 "bare_number_card":{{"present":bool,"evidence":str}},"dead_air":{{"present":bool,"evidence":str}},
 "empty_void":{{"present":bool,"evidence":str}},
 "unreadable":{{"present":bool,"evidence":str}}}},
 "weakest_scene":{{"id":str,"index":int,"failure_class":str,
 "visible_evidence":str,"root_cause":str,"repair_goal":str}},
 "depictions":[{{"id":str,"kind":str,"bespoke":int,"proves_claim":int,"note":str}}],
 "one_line":str,"problems":[str],"fixes":[str]}}

RUBRIC:
{rubric}

SCRIPT / SCENE CONTEXT:
{ctx}"""


def clean_depictions(raw) -> list | None:
    """The judge's per-depiction grades, made safe to store — or None.

    OPTIONAL BY DESIGN. This field is a learning signal for the brain that
    invents the visuals; it never touches ship/block, so its absence or
    malformation must never become a block reason (`validate_judge_response`
    does not know about it). Older judges and older verdicts simply lack it.
    Anything that is not a list of {id, bespoke, proves_claim} with the ints
    in 0-3 is dropped, entry by entry, rather than trusted.
    """
    if not isinstance(raw, list):
        return None
    out = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        sid = str(d.get("id") or "").strip()
        if not sid:
            continue
        try:
            b = max(0, min(3, int(d.get("bespoke"))))
            pc = max(0, min(3, int(d.get("proves_claim"))))
        except (TypeError, ValueError):
            continue
        kind = str(d.get("kind") or "").strip().lower()
        if kind not in ("bespoke", "machine", "chart"):
            kind = "bespoke" if b >= 2 else ("chart" if b == 0 else "machine")
        out.append({"id": sid, "kind": kind, "bespoke": b, "proves_claim": pc,
                    "note": str(d.get("note") or "")[:240]})
    return out or None


def review_video(mp4: Path, context: dict | None = None) -> dict:
    """Grade the finished video and COMPUTE the verdict in code. The model
    supplies anchored dimension grades + hard-check answers; this function turns
    them into the 100-pt score, folds in objective motion evidence, and decides
    ship/block. Raises only on genuine infra failure — which
    `shared/showrunner_gate.decide()` turns into a HOLD on a publish run
    and a skip on a preview. This function never decides that itself."""
    mp4 = Path(mp4)
    ctx = dict(context or {})
    manifest = ctx.get("manifest")
    if manifest is None:
        mpath = mp4.with_suffix(".manifest.json")
        if mpath.exists():
            try:
                manifest = json.loads(mpath.read_text())
            except Exception:  # noqa: BLE001
                manifest = None
    if manifest is None:
        # LONG-FORM sidecar: `longform_render` writes `<out>.meta.json`
        # (chapters + duration + sources) instead of a shorts manifest.
        # Without this the judge falls to a blind sweep of a 5-minute video.
        mpath = mp4.with_suffix(".meta.json")
        if mpath.exists():
            try:
                manifest = json.loads(mpath.read_text())
            except Exception:  # noqa: BLE001
                manifest = None
    if manifest is None and ctx.get("chapters"):
        manifest = {"chapters": ctx["chapters"]}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        labeled = _extract_frames(mp4, tdp, manifest)
        if not labeled:
            raise RuntimeError("no frames extracted (ffmpeg?)")
        motion = _motion_evidence(mp4, tdp)
        temporal = _temporal_evidence(mp4, tdp)
        unmeasured = temporal_unmeasured(temporal)
        if unmeasured:
            # Before the vision call: an unjudgeable render should not cost a
            # judge invocation, and it must not reach one as neutral evidence.
            raise RuntimeError(unmeasured)
        # BUILD-TIME TEMPORAL GATE (code, BEFORE the expensive vision review):
        # a render whose measured cadence is below the active quality phase's
        # hard floor is invalid — block it outright without spending a vision
        # call. This only ever ADDS a block (never overrides a brain BLOCK).
        gate = temporal_hard_fail(temporal)
        if gate:
            dims = {k: 0 for k in WEIGHTS}
            dims["temporal_craft"] = temporal_grade(temporal)
            return {
                "score": compute_score(dims), "verdict": "block",
                "dimensions": dims,
                "auto_fails": [f"temporal_gate: {gate}"],
                "checks": {"temporal_gate": {"fail": True, "evidence": gate}},
                "motion": motion, "temporal": temporal,
                "judge": "code-temporal-pregate",
                "one_line": f"blocked before vision review: {gate}",
                "problems": [gate], "fixes": ["raise real motion per output "
                                              "frame (see temporal thresholds)"],
            }
        prompt = _GRADE_PROMPT.format(
            motion=json.dumps({**motion, "temporal": temporal}),
            format_directive=_format_directive(ctx),
            rubric=_rubric()[:6000],
            # a sleep film's context carries the line spoken at each of its
            # ~18 sampled frames, which does not fit the shorts budget
            ctx=json.dumps(ctx, indent=0)[:(6000 if str(ctx.get("format") or "").lower() == "sleep" else 3000)])
        try:
            grades, backend = _judge(prompt, labeled)
        except Exception as judge_err:  # noqa: BLE001
            # NOBODY COULD WATCH. The gate will hold (fail-closed) — that is
            # right. What was wrong on 2026-09-21 is that the render then
            # died with the runner and the fleet's third brain was never
            # asked. If the caller opened the mailbox (`ctx["mailbox"]`,
            # publish runs only), keep the render and file a review request
            # carrying exactly what the judge would have been given; the
            # claim step ships it later on an explicit code-decided ship.
            # See `shared/review_mailbox.py`.
            mb = ctx.get("mailbox")
            rid = None
            if isinstance(mb, dict):
                from shared import review_mailbox as _rm
                rid = _rm.file_request(
                    mp4=mp4, slug=str(ctx.get("slug") or mp4.stem),
                    labeled=labeled, prompt=prompt, motion=motion,
                    temporal=temporal, ctx=ctx, mailbox=mb)
            raise RuntimeError(
                f"{judge_err}"
                + (f" — review request filed: {rid}" if rid else "")) from judge_err

    return assemble_verdict(grades, motion=motion, temporal=temporal,
                            backend=backend)


def assemble_verdict(grades: dict, *, motion: dict, temporal: dict,
                     backend: str) -> dict:
    """Turn a judge's graded anchors into the verdict — ONE function for
    every judge. The headless brain, the Gemini fallback and a ChatGPT
    mailbox answer all pass through here, so the schema check, the
    code-computed score, the motion override and `decide_verdict` are
    byte-identical whoever graded. A judge grades; this decides."""
    schema_problems = validate_judge_response(grades)
    if schema_problems:
        dims = {k: 0 for k in WEIGHTS}
        dims["temporal_craft"] = temporal_grade(temporal)
        evidence = "; ".join(schema_problems)[:500]
        return {
            "score": compute_score(dims), "verdict": "block",
            "dimensions": dims,
            "auto_fails": [f"malformed_judge_response: {p}" for p in schema_problems],
            "checks": {"malformed_judge_response": {"present": True, "evidence": evidence}},
            "motion": motion, "temporal": temporal,
            "judge": backend,
            "one_line": "blocked: judge response failed schema validation",
            "problems": schema_problems,
            "fixes": ["judge must answer every WEIGHTS dimension and every "
                      "AUTOFAIL_CHECKS key with present(bool) + nonempty "
                      "evidence, per _GRADE_PROMPT"],
        }

    dims = grades.get("dimensions", {}) or {}
    # temporal_craft is CODE-graded from measured cadence — the model doesn't
    # get to call a choppy video smooth.
    dims["temporal_craft"] = temporal_grade(temporal)
    checks = apply_motion_override(grades.get("checks", {}) or {}, motion)
    score = compute_score(dims)
    failed = failed_autofails(checks)
    verdict = decide_verdict(score, checks)
    # STRUCTURED weakest-scene diagnosis: pass the judge's own scene target
    # through so repair addresses the scene the judge saw failing — never
    # re-derived by parsing prose. A block verdict without one is an emergency
    # (logged); the repair layer then falls back explicitly.
    ws = grades.get("weakest_scene")
    if verdict == "block" and not isinstance(ws, dict):
        print("[showrunner] EMERGENCY: block verdict without a structured "
              "weakest_scene — repair will use its logged fallback", flush=True)
        ws = None
    return {
        "score": score, "verdict": verdict,
        "dimensions": {k: int(dims.get(k, 0)) for k in WEIGHTS},
        "auto_fails": [f"{k}: {checks[k].get('evidence', '')}" for k in failed],
        "checks": checks, "motion": motion, "temporal": temporal,
        "judge": backend, "weakest_scene": ws,
        # Per-depiction grades ride along to the ledger and to post_stories,
        # which hands them to `viz_director.grade_mechanics`. This return
        # is built field by field, so a key the judge sends is dropped unless
        # it is named here — which is how "the showrunner already sees which
        # beat was a bolt grid" stayed prose for months.
        "depictions": clean_depictions(grades.get("depictions")),
        "one_line": grades.get("one_line", ""),
        "problems": grades.get("problems", []),
        "fixes": grades.get("fixes", []),
    }


def should_block(verdict: dict) -> bool:
    return verdict.get("verdict") == "block"


LEDGER = REPO / "state" / "showrunner_verdicts.jsonl"


def append_ledger(slug: str, verdict: dict) -> None:
    """Append a compact, durable record of the gate's verdict. This is the
    showrunner's memory — a permanent trail of what it judged and why, so its
    authority is concrete and auditable, not a one-off print in a CI log."""
    from datetime import datetime, timezone
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "slug": slug,
               "score": verdict.get("score"),
               "verdict": verdict.get("verdict"),
               "dimensions": verdict.get("dimensions"),
               "one_line": verdict.get("one_line"),
               "auto_fails": verdict.get("auto_fails", []),
               # The judge's specific diagnosis and prescriptions. These were
               # dropped from the durable record until 2026-08-24, so the only
               # cross-run trace of WHY a video failed was one_line — a
               # re-planner (or a human reading the ledger) had nothing to act
               # on. Bounded so a chatty verdict can't bloat the ledger.
               "problems": [str(p)[:300] for p in
                            (verdict.get("problems") or [])[:6]],
               "fixes": [str(f)[:300] for f in
                         (verdict.get("fixes") or [])[:6]],
               "motion": verdict.get("motion"),
               "judge": verdict.get("judge", "unknown"),   # ACTUAL backend used
               "model": os.environ.get("SHOWRUNNER_MODEL", "opus"),
               "rubric_sha": _rubric_sha()}
        with LEDGER.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:  # noqa: BLE001 — the ledger must never break a run
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--context", type=Path, default=None,
                    help="JSON file with the story/scene plan for context")
    ap.add_argument("--out", type=Path, default=None,
                    help="where to write the verdict sidecar (default: "
                         "<mp4>.showrunner.json)")
    args = ap.parse_args()

    if os.environ.get("SHOWRUNNER", "on").lower() in ("off", "0", "false"):
        print("[showrunner] disabled (SHOWRUNNER=off) — skipping")
        return 1
    ctx = {}
    if args.context and args.context.exists():
        try:
            ctx = json.loads(args.context.read_text())
        except Exception:  # noqa: BLE001
            pass
    try:
        verdict = review_video(Path(args.mp4), ctx)
    except Exception as e:  # noqa: BLE001 — FAIL-OPEN on infra problems
        print(f"[showrunner] review skipped ({e}) — not blocking", flush=True)
        return 1
    out = args.out or Path(str(args.mp4) + ".showrunner.json")
    try:
        out.write_text(json.dumps(verdict, indent=2))
    except Exception:  # noqa: BLE001
        pass
    append_ledger(Path(args.mp4).stem, verdict)
    tag = "BLOCK ⛔" if should_block(verdict) else "SHIP ✅"
    print(f"[showrunner] {tag}  score={verdict.get('score')}  "
          f"— {verdict.get('one_line')}", flush=True)
    for p in verdict.get("problems", [])[:6]:
        print(f"    · problem: {p}", flush=True)
    for f in verdict.get("fixes", [])[:6]:
        print(f"    → fix: {f}", flush=True)
    return 2 if should_block(verdict) else 0


if __name__ == "__main__":
    sys.exit(main())
