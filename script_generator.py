#!/usr/bin/env python3
"""Turn a trending topic into a render-ready script package.

Given a topic (query + news headlines) we ask Claude to write a
60-80-word YouTube Short script, plus the shot list and punch overlays
keyed off trigger phrases in that script. Output schema matches what
make_explainer_stacked.py consumes.

Hard constraints baked into the prompt (we learned these from prior
renders):
  * Whisper rewrites numbers as digits, so trigger phrases must use
    "12" not "twelve" and "25" not "twenty five".
  * "Wayfair" transcribes as "wafer", "Once" at sentence start
    transcribes as "wants" — skip both.
  * Every shot.phrase and punch.phrase must appear verbatim in the
    script (the runtime looks them up word-for-word in the whisper
    transcript).

Env: ANTHROPIC_API_KEY (required).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"


SYSTEM_PROMPT = """You write short, viral-style YouTube Shorts scripts about whatever's trending. \
Output strict JSON only — no prose, no markdown fences.

The video format is a 1080x1920 vertical Short, ~25 seconds:
- Top half: 5-7 stock B-roll clips that cycle every ~2 seconds
- Bottom half: Minecraft parkour gameplay (visual background only)
- Burned captions auto-generated from the narration audio
- 4-7 big "punch" text overlays that emphasize key stats or beats

Your job is to produce a JSON package the renderer will consume verbatim. \
Tone is doomscroll-explainer: a strong factual hook, dense delivery, no filler. \
Think "X is happening and here's why" — not editorial opinion."""


USER_PROMPT_TEMPLATE = """Topic: {topic_query}

Context (news headlines and snippets driving the trend):
{context_block}

Write a JSON package with this exact schema:

{{
  "title": "<short, punchy YouTube title, 6-10 words>",
  "script": "<60-80 words, conversational tone, opens with a hook, ends decisively>",
  "shots": [
    {{"phrase": "<2-3 word phrase that appears VERBATIM in the script>",
      "query": "<1-3 word stock-footage search query, visually concrete>"}}
  ],
  "punches": [
    {{"phrase": "<word/phrase that appears VERBATIM in the script>",
      "text": "<1-3 word ALL CAPS overlay>",
      "color": "<#hex>"}}
  ],
  "music_vibe": "<one of: dark, cinematic, hiphop>"
}}

Hard rules:
- The script must mention {topic_query} clearly enough that someone who has never heard of it understands what it is.
- Open with a HOOK. Punchy, declarative, attention-grabbing. Examples: "X is dying.", "Your Y is a lie.", "Here's what nobody told you about Z."
- Numbers in the SCRIPT TEXT can be either spelled or digits, but every trigger PHRASE (shot.phrase, punch.phrase) MUST match how Whisper transcribes the audio:
    - Spoken "twelve million" → Whisper writes "12 million" → trigger phrase uses "12 million"
    - Spoken "twenty five" → Whisper writes "25" → trigger phrase uses "25"
- Avoid the word "Wayfair" (transcribes as "wafer") and avoid "Once" as a sentence opener (transcribes as "wants"). Use "First" / "Once you" / etc instead.
- 5-7 shots. Each shot.query is what we pass to Pexels/Pixabay — must be a visually concrete subject (a noun, a scene). Bad: "economic anxiety". Good: "stock market screen", "empty store".
- Each shot.phrase must be a unique distinctive substring of the script (lowercase or proper case, but verbatim). The renderer aligns the shot to that phrase's TTS timing.
- 4-7 punches. Punch text is 1-3 ALL-CAPS words. Use colors thoughtfully: #ff3030 for shock/bad, #50ff80 for positive, #ffaa30 for warning, #ffffff for neutral.
- music_vibe: "dark" for serious/exposé, "cinematic" for big-picture, "hiphop" for upbeat/cultural.

Output ONLY the JSON object. No code fence, no commentary."""


def _build_context(headlines: list[str], snippets: list[str]) -> str:
    lines: list[str] = []
    for h in headlines[:8]:
        lines.append(f"- {h}")
    for s in snippets[:4]:
        if s:
            lines.append(f"  ({s})")
    return "\n".join(lines) if lines else "(no additional context)"


def _call_anthropic(system: str, user: str, model: str = DEFAULT_MODEL) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var not set")
    body = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_API,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    # Single text content block
    return resp["content"][0]["text"]


def _strip_fence(text: str) -> str:
    """Claude usually obeys 'no fence' but be defensive — strip ```json
    fences if they slip through."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _validate_package(pkg: dict, script: str) -> None:
    """Light sanity checks — confirm trigger phrases actually occur in
    the script. If they don't, the renderer would silently fall back to
    default timings and the alignment is shot."""
    issues: list[str] = []
    script_lower = script.lower()
    for s in pkg.get("shots", []):
        if (s.get("phrase") or "").lower() not in script_lower:
            issues.append(f"shot trigger {s.get('phrase')!r} not in script")
    for p in pkg.get("punches", []):
        if (p.get("phrase") or "").lower() not in script_lower:
            issues.append(f"punch trigger {p.get('phrase')!r} not in script")
    if issues:
        print("[script_generator] WARNING: " + "; ".join(issues), file=sys.stderr)


def generate(topic_query: str, headlines: list[str], snippets: list[str] | None = None,
             *, model: str = DEFAULT_MODEL) -> dict:
    """Hit Claude, return the parsed JSON package."""
    user = USER_PROMPT_TEMPLATE.format(
        topic_query=topic_query,
        context_block=_build_context(headlines, snippets or []),
    )
    raw = _call_anthropic(SYSTEM_PROMPT, user, model=model)
    pkg = json.loads(_strip_fence(raw))
    _validate_package(pkg, pkg.get("script", ""))
    pkg["topic"] = topic_query
    return pkg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="topic query (otherwise read JSON from stdin)")
    ap.add_argument("--headlines", action="append", default=[],
                    help="news headline context; repeat for multiple")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, help="write package JSON to this file (default stdout)")
    args = ap.parse_args()

    if args.topic:
        headlines = args.headlines
        snippets: list[str] = []
        topic = args.topic
    else:
        # Read a discover_topic.py output entry from stdin.
        data = json.load(sys.stdin)
        if isinstance(data, list):
            data = data[0]
        topic = data["query"]
        headlines = data.get("headlines", [])
        snippets = data.get("snippets", [])

    pkg = generate(topic, headlines, snippets, model=args.model)
    out_json = json.dumps(pkg, indent=2)
    if args.out:
        args.out.write_text(out_json)
        print(f"-> {args.out}")
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
