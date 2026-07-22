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
- Mirrors the pipeline's existing raw-HTTP Anthropic pattern (script_generator),
  adding vision — no new dependency. Uses ANTHROPIC_API_KEY.
- FAIL-OPEN on infrastructure problems (no key, API/ffmpeg error): a hiccup must
  not halt the whole channel. FAIL-CLOSED only on a real reviewed BLOCK verdict.
- Model: claude-opus-4-8 (the judgment quality IS the point). Override with
  SHOWRUNNER_MODEL.

CLI:
    python scripts/showrunner_review.py output/story_x.mp4 [--context ctx.json]
    # exit 0 = ship, 2 = block, 1 = skipped/errored (treated as ship by callers)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUBRIC_PATH = REPO / "docs" / "DIRECTOR.md"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("SHOWRUNNER_MODEL", "claude-opus-4-8")
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


def _call(system: str, content: list) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": {
            "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
            "effort": "high",
        },
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_API, data=body, method="POST",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode())
    for block in resp.get("content", []):
        if block.get("type") == "text":
            return json.loads(block["text"])
    raise RuntimeError("no text block in showrunner response")


def review_video(mp4: Path, context: dict | None = None) -> dict:
    """Return a verdict dict (see docs/DIRECTOR.md). Raises only on a genuine
    infra failure (caller should fail-open on that)."""
    mp4 = Path(mp4)
    ctx = context or {}
    with tempfile.TemporaryDirectory() as td:
        frames = _extract_frames(mp4, Path(td), N_FRAMES)
        if not frames:
            raise RuntimeError("no frames extracted (ffmpeg?)")
        content: list = []
        for i, f in enumerate(frames):
            content.append({"type": "text",
                            "text": f"Frame {i + 1}/{len(frames)} "
                                    f"(in order across the video):"})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": _b64(f)}})
        ask = (
            "You are the SHOWRUNNER for this channel. Score the video above "
            "against the rubric using the exact JSON schema. Be exacting — you "
            "are the editor with a veto, and a boring or sloppy video must be "
            "BLOCKED (it is better to block a mediocre video than to let it "
            "ship). Judge what you SEE in the frames, not what was intended.\n\n"
            f"Scene plan / script for context:\n{json.dumps(ctx, indent=2)[:4000]}"
        )
        content.append({"type": "text", "text": ask})
        verdict = _call(_rubric(), content)
    # Enforce the bar in code too (belt and suspenders): block on low score or
    # any auto-fail even if the model hedged the verdict field.
    score = int(verdict.get("score", 0))
    if score < MIN_SCORE or verdict.get("auto_fails"):
        verdict["verdict"] = "block"
    return verdict


def should_block(verdict: dict) -> bool:
    return verdict.get("verdict") == "block"


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
