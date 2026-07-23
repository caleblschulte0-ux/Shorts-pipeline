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
- FAIL-OPEN on infrastructure problems (CLI missing, timeout, ffmpeg error) on a
  preview run; the caller (post_stories) fails CLOSED on a real publish run.
- Model: the CLI 'opus' alias (override with SHOWRUNNER_MODEL).

CLI:
    python scripts/showrunner_review.py output/story_x.mp4 [--context ctx.json]
    # exit 0 = ship, 2 = block, 1 = skipped/errored (treated as ship by callers)
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
    "hook": (20, 4), "data_demo": (25, 5), "mascot": (20, 4),
    "craft": (15, 3), "pace": (10, 2), "payoff": (10, 2),
}
# Hard auto-fail checks. The model must answer EVERY one (present + evidence);
# code BLOCKS if any is present, regardless of the numeric score. These are the
# rubric's hard rules — they are not suggestions.
AUTOFAIL_CHECKS = ["junk_imagery", "decorative_mascot", "bare_number_card",
                   "dead_air", "empty_void"]


def compute_score(dims: dict) -> int:
    """Turn anchored dimension grades into the weighted 100-pt score. In CODE,
    not by asking the model for the total."""
    total = 0.0
    for k, (w, ceil) in WEIGHTS.items():
        g = max(0, min(ceil, int(dims.get(k, 0))))
        total += w * g / ceil
    return round(total)


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
    if wins:
        for i, (s0, s1) in enumerate(wins):
            for f, tag in ((0.08, "start"), (0.5, "mid"), (0.92, "end")):
                plan.append((s0 + f * (s1 - s0), f"seg{i}:{tag}"))
    else:
        for k in range(6):
            t = 2.5 + (dur - 4.5) * k / 5
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


def _motion_evidence(mp4: Path, td: Path) -> dict:
    """Objective, code-measured motion facts (NOT a judgement). Samples the whole
    clip at ~3fps and reports the longest near-frozen run (seconds) and the
    fraction of near-black frames. Vision judges whether motion is *meaningful*;
    this decides whether motion *exists* — so 'dead air' can't be averaged away."""
    ev = {"longest_static_s": 0.0, "dark_fraction": 0.0, "sampled": 0}
    try:
        from PIL import Image
        fps = 3
        seq = td / "mv"
        seq.mkdir(exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
             "-vf", f"fps={fps},scale=96:-1,format=gray", str(seq / "m%04d.png")],
            check=True)
        imgs = sorted(seq.glob("m*.png"))
        ev["sampled"] = len(imgs)
        if len(imgs) < 2:
            return ev
        px = [list(Image.open(p).getdata()) for p in imgs]
        n = len(px)
        # dark fraction
        dark = sum(1 for p in px if (sum(p) / len(p)) < 22)
        ev["dark_fraction"] = round(dark / n, 3)
        # DEAD AIR = a stretch where nothing meaningfully changes over ~1s. Use a
        # 1s LOOKBACK (not consecutive frames) so a SMOOTH build (a waffle filling
        # a few cells per frame, a total ticking) is correctly read as motion —
        # only a genuinely static hold registers as frozen.
        lb = fps                              # ~1.0s lookback
        run = best = 0
        for i in range(lb, n):
            a, b = px[i], px[i - lb]
            diff = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
            if diff < 3.0:            # no meaningful change across a full second
                run += 1
                best = max(best, run)
            else:
                run = 0
        ev["longest_static_s"] = round(best / fps, 2)
    except Exception as e:  # noqa: BLE001
        ev["error"] = str(e)[:120]
    return ev


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
    m = re.search(r"\{.*\}", (proc.stdout or "").strip(), re.S)
    if not m:
        raise RuntimeError(f"no JSON in claude output: {(proc.stdout or '')[:200]}")
    return json.loads(m.group(0))


def _gemini_judge(prompt: str, labeled) -> dict:
    parts: list = []
    for p, lab, ts in labeled:
        parts.append({"text": f"Frame {lab} (t={ts:.2f}s):"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _b64(p)}})
    parts.append({"text": prompt + "\n\nReturn ONLY the JSON object, no prose."})
    url = GEMINI_API.format(model=GEMINI_MODEL, key=os.environ["GEMINI_API_KEY"])
    resp = _post_json(url, {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": 0.2, "maxOutputTokens": 2000}},
        {"content-type": "application/json"})
    return json.loads(resp["candidates"][0]["content"]["parts"][0]["text"])


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

MOTION FACTS (measured in code, not opinion) — use them, especially for dead_air \
and empty_void:
{motion}

Return ONLY this JSON:
{{"dimensions":{{"hook":int,"data_demo":int,"mascot":int,"craft":int,"pace":int,"payoff":int}},
 "checks":{{"junk_imagery":{{"present":bool,"evidence":str}},"decorative_mascot":{{"present":bool,"evidence":str}},
 "bare_number_card":{{"present":bool,"evidence":str}},"dead_air":{{"present":bool,"evidence":str}},
 "empty_void":{{"present":bool,"evidence":str}}}},
 "one_line":str,"problems":[str],"fixes":[str]}}

RUBRIC:
{rubric}

SCRIPT / SCENE CONTEXT:
{ctx}"""


def review_video(mp4: Path, context: dict | None = None) -> dict:
    """Grade the finished video and COMPUTE the verdict in code. The model
    supplies anchored dimension grades + hard-check answers; this function turns
    them into the 100-pt score, folds in objective motion evidence, and decides
    ship/block. Raises only on genuine infra failure (caller fails open on that)."""
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
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        labeled = _extract_frames(mp4, tdp, manifest)
        if not labeled:
            raise RuntimeError("no frames extracted (ffmpeg?)")
        motion = _motion_evidence(mp4, tdp)
        prompt = _GRADE_PROMPT.format(
            motion=json.dumps(motion),
            rubric=_rubric()[:6000],
            ctx=json.dumps(ctx, indent=0)[:3000])
        grades, backend = _judge(prompt, labeled)

    dims = grades.get("dimensions", {}) or {}
    score = compute_score(dims)
    checks = grades.get("checks", {}) or {}
    # Objective override: code measures whether motion EXISTS; the model can't
    # average a real dead hold away.
    if motion.get("longest_static_s", 0) >= 4.0:
        checks.setdefault("dead_air", {})
        checks["dead_air"] = {"present": True,
                              "evidence": f"code: {motion['longest_static_s']}s frozen"}
    failed = [k for k in AUTOFAIL_CHECKS
              if isinstance(checks.get(k), dict) and checks[k].get("present")]
    verdict = "block" if (failed or score < MIN_SCORE) else "ship"
    return {
        "score": score, "verdict": verdict,
        "dimensions": {k: int(dims.get(k, 0)) for k in WEIGHTS},
        "auto_fails": [f"{k}: {checks[k].get('evidence', '')}" for k in failed],
        "checks": checks, "motion": motion, "judge": backend,
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
