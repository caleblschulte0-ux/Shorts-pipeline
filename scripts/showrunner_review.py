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
N_FRAMES = int(os.environ.get("SHOWRUNNER_FRAMES", "6"))

VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["ship", "block"]},
        "one_line": {"type": "string"},
        "auto_fails": {"type": "array", "items": {"type": "string"}},
        "dimensions": {
            "type": "object", "additionalProperties": False,
            "properties": {k: {"type": "integer"} for k in
                           ("hook", "data_demo", "mascot", "craft", "pace",
                            "payoff")},
            "required": ["hook", "data_demo", "mascot", "craft", "pace",
                         "payoff"],
        },
        "problems": {"type": "array", "items": {"type": "string"}},
        "fixes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "verdict", "one_line", "auto_fails", "dimensions",
                 "problems", "fixes"],
}


def _duration(mp4: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp4)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 40.0


def _extract_frames(mp4: Path, td: Path, n: int) -> list[Path]:
    """Evenly-spaced frames across the video, scaled down to keep tokens sane."""
    dur = _duration(mp4)
    frames = []
    for i in range(n):
        # sample from ~4% to ~96% so we catch the hook and the payoff
        t = dur * (0.04 + 0.92 * (i / max(1, n - 1)))
        out = td / f"f{i:02d}.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                 "-i", str(mp4), "-frames:v", "1", "-vf", "scale=430:-1",
                 str(out)], check=True)
            if out.exists():
                frames.append(out)
        except Exception:  # noqa: BLE001
            continue
    return frames


def _b64(p: Path) -> str:
    return base64.standard_b64encode(p.read_bytes()).decode()


def _rubric() -> str:
    try:
        return RUBRIC_PATH.read_text()
    except Exception:  # noqa: BLE001
        return "Be an exacting creative director. Block boring or sloppy videos."


GEMINI_API = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
GEMINI_MODEL = os.environ.get("SHOWRUNNER_GEMINI_MODEL", "gemini-2.5-flash")


def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def _headless_claude_judge(system: str, frame_files: list[Path], ask: str) -> dict:
    """Judge via the Claude HEADLESS BRAIN — the `claude` CLI in print mode,
    authenticated by the CLAUDE_CODE_OAUTH_TOKEN subscription (same mechanism the
    pipeline's brain step uses). NOT the paid Anthropic API. The CLI Reads the
    frame image files itself (vision) and returns the verdict JSON.

    Raises on any failure so the caller can fall back / fail-open on infra."""
    if not shutil.which("claude"):
        raise RuntimeError("claude CLI not installed (npm i -g @anthropic-ai/claude-code)")
    listing = "\n".join(f"- {p}" for p in frame_files)
    prompt = (
        system + "\n\n" + ask +
        "\n\nThe video frames are these image files, IN ORDER. Use the Read "
        "tool to actually VIEW each one before scoring — do not guess:\n"
        + listing +
        "\n\nReturn ONLY the JSON verdict object with exactly these fields: "
        "score (0-100 int), verdict ('ship'|'block'), one_line, auto_fails "
        "(list), dimensions {hook,data_demo,mascot,craft,pace,payoff ints}, "
        "problems (list), fixes (list). No prose, no code fence.")
    model = os.environ.get("SHOWRUNNER_MODEL", "opus")
    timeout = int(os.environ.get("SHOWRUNNER_TIMEOUT", "480"))
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model,
         "--allowedTools", "Read", "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI rc={proc.returncode}: {(proc.stderr or proc.stdout)[:200]}")
    out = (proc.stdout or "").strip()
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise RuntimeError(f"no JSON verdict in claude output: {out[:200]}")
    return json.loads(m.group(0))


def _gemini_judge(system: str, frames: list[str], ask: str) -> dict:
    parts: list = []
    for i, b in enumerate(frames):
        parts.append({"text": f"Frame {i + 1}/{len(frames)} (in order):"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b}})
    parts.append({"text": ask + "\n\nReturn ONLY the JSON object, no prose."})
    url = GEMINI_API.format(model=GEMINI_MODEL,
                            key=os.environ["GEMINI_API_KEY"])
    resp = _post_json(url, {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": 0.35, "maxOutputTokens": 2000}},
        {"content-type": "application/json"})
    txt = resp["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(txt)


def _judge(system: str, frame_files: list[Path], ask: str) -> dict:
    """Judge of record: the Claude HEADLESS BRAIN (the `claude` CLI on the
    subscription OAuth token) — not the paid API. Falls back to free Gemini
    vision only if the headless brain is unavailable or errors."""
    errs = []
    # The headless brain is the judge of record; retry a couple times so a
    # transient CLI timeout / 429 doesn't fail-open and lose the verdict (the
    # intermittent no-verdict renders were exactly this).
    import time
    for attempt in range(int(os.environ.get("SHOWRUNNER_RETRIES", "3"))):
        try:
            return _headless_claude_judge(system, frame_files, ask)
        except Exception as e:  # noqa: BLE001
            errs.append(f"headless-claude[{attempt}]: {e}")
            time.sleep(3 * (attempt + 1))
    if os.environ.get("GEMINI_API_KEY"):
        try:
            frames_b64 = [_b64(f) for f in frame_files]
            return _gemini_judge(system, frames_b64, ask)
        except Exception as e:  # noqa: BLE001
            errs.append(f"gemini: {e}")
    raise RuntimeError("no vision judge available (headless `claude` CLI, or "
                       f"GEMINI_API_KEY fallback). {errs}")


def review_video(mp4: Path, context: dict | None = None) -> dict:
    """Return a verdict dict (see docs/DIRECTOR.md). Raises only on a genuine
    infra failure (caller should fail-open on that)."""
    mp4 = Path(mp4)
    ctx = context or {}
    with tempfile.TemporaryDirectory() as td:
        frame_files = _extract_frames(mp4, Path(td), N_FRAMES)
        if not frame_files:
            raise RuntimeError("no frames extracted (ffmpeg?)")
        ask = (
            "You are the SHOWRUNNER for this channel. Score the video (the "
            "frames above, in order) against the rubric using the exact JSON "
            "schema fields. Be exacting — you are the editor with a veto, and a "
            "boring or sloppy video must be BLOCKED (better to block a mediocre "
            "video than let it ship). Judge what you SEE, not what was "
            "intended.\n\nJSON fields: score (0-100 int), verdict "
            "('ship'|'block'), one_line, auto_fails (list), dimensions "
            "{hook,data_demo,mascot,craft,pace,payoff ints}, problems (list), "
            "fixes (list).\n\nScene plan / script for context:\n"
            f"{json.dumps(ctx, indent=2)[:4000]}"
        )
        verdict = _judge(_rubric(), frame_files, ask)
    # Enforce the bar in code too (belt and suspenders): block on low score or
    # any auto-fail even if the model hedged the verdict field.
    score = int(verdict.get("score", 0))
    if score < MIN_SCORE or verdict.get("auto_fails"):
        verdict["verdict"] = "block"
    return verdict


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
               "one_line": verdict.get("one_line"),
               "auto_fails": verdict.get("auto_fails", []),
               "judge": "headless-claude"}
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
