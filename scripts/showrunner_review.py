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


GEMINI_API = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
GEMINI_MODEL = os.environ.get("SHOWRUNNER_GEMINI_MODEL", "gemini-2.5-flash")


def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def _anthropic_headers() -> dict | None:
    """Auth for the Claude Messages API. Prefer a plain API key; otherwise use
    the Claude headless-brain OAuth token (CLAUDE_CODE_OAUTH_TOKEN / _API_KEY)
    the way the pipeline's brain is already authenticated — Bearer + the oauth
    beta header. Returns None if no Claude credential is available."""
    base = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return {**base, "x-api-key": key}
    oauth = (os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
             or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if oauth:
        return {**base, "authorization": f"Bearer {oauth}",
                "anthropic-beta": "oauth-2025-04-20"}
    return None


def _anthropic_judge(system: str, frames: list[str], ask: str) -> dict:
    headers = _anthropic_headers()
    if headers is None:
        raise RuntimeError("no Claude credential (ANTHROPIC_API_KEY or "
                           "CLAUDE_CODE_OAUTH_TOKEN)")
    content: list = []
    for i, b in enumerate(frames):
        content.append({"type": "text",
                        "text": f"Frame {i + 1}/{len(frames)} (in order):"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": b}})
    content.append({"type": "text", "text": ask})
    # Structured output the CORRECT Anthropic-Messages way: define a tool whose
    # input_schema IS the verdict schema and force it. (The old body used
    # output_config/json_schema/effort — none of which are Messages API fields —
    # so every call 400'd and the gate silently fell open. That is why nothing
    # was ever actually reviewed.)
    resp = _post_json(ANTHROPIC_API, {
        "model": MODEL, "max_tokens": 2000, "system": system,
        "messages": [{"role": "user", "content": content}],
        "tools": [{"name": "submit_verdict",
                   "description": "Submit the showrunner's scored verdict.",
                   "input_schema": VERDICT_SCHEMA}],
        "tool_choice": {"type": "tool", "name": "submit_verdict"}},
        headers)
    for block in resp.get("content", []):
        if block.get("type") == "tool_use":
            return block["input"]
    # Fallback: some gateways return the JSON as text.
    for block in resp.get("content", []):
        if block.get("type") == "text":
            import re
            m = re.search(r"\{.*\}", block["text"], re.S)
            if m:
                return json.loads(m.group(0))
    raise RuntimeError(f"no verdict in Anthropic response: {str(resp)[:300]}")


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


def _judge(system: str, frames: list[str], ask: str) -> dict:
    """Prefer the Claude headless brain (API key OR the CLAUDE_CODE_OAUTH_TOKEN
    the pipeline already uses) — it's the strongest judge. Fall back to free
    Gemini vision only if Claude isn't available or errors."""
    errs = []
    if _anthropic_headers() is not None:
        try:
            return _anthropic_judge(system, frames, ask)
        except Exception as e:  # noqa: BLE001
            errs.append(f"claude: {e}")
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return _gemini_judge(system, frames, ask)
        except Exception as e:  # noqa: BLE001
            errs.append(f"gemini: {e}")
    raise RuntimeError("no vision LLM backend available (set "
                       "CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY, or "
                       f"GEMINI_API_KEY). {errs}")


def review_video(mp4: Path, context: dict | None = None) -> dict:
    """Return a verdict dict (see docs/DIRECTOR.md). Raises only on a genuine
    infra failure (caller should fail-open on that)."""
    mp4 = Path(mp4)
    ctx = context or {}
    with tempfile.TemporaryDirectory() as td:
        frame_files = _extract_frames(mp4, Path(td), N_FRAMES)
        if not frame_files:
            raise RuntimeError("no frames extracted (ffmpeg?)")
        frames = [_b64(f) for f in frame_files]
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
        verdict = _judge(_rubric(), frames, ask)
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
