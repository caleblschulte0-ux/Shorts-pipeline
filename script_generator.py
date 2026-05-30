#!/usr/bin/env python3
"""Turn a trending topic into a render-ready script package.

Given a topic (query + news headlines) we ask an LLM to write a
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

Backend preference: Groq → Gemini → Anthropic. Groq's free tier is
the friendliest signup (just an email, no card, no age-gate, no
regional restriction) and serves Llama 3.3 70B fast enough for daily
generation. Gemini works too but requires age-verifying your Google
account. Anthropic is paid and stays as an opt-in.

Env (set whichever one you have):
  GROQ_API_KEY      — free at https://console.groq.com/keys (recommended)
  GEMINI_API_KEY    — free at https://aistudio.google.com/apikey
                       (needs age-verified Google account)
  ANTHROPIC_API_KEY — paid
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
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

# Default model per backend.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


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


def _call_groq(system: str, user: str, model: str = DEFAULT_GROQ_MODEL) -> str:
    """Hit Groq's OpenAI-compatible chat completions endpoint. Free
    tier on Llama 3.3 70B: 30 RPM / 14400 requests per day, no card."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY env var not set")
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        # Forces a valid JSON object back — no fence stripping needed.
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        GROQ_API,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    return resp["choices"][0]["message"]["content"]


def _call_gemini(system: str, user: str, model: str = DEFAULT_GEMINI_MODEL) -> str:
    """Hit Google's Generative Language API. Free tier on
    gemini-2.5-flash: 15 RPM / 1500 requests per day, no card required."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var not set")
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
            # Force JSON output so we don't have to strip code fences.
            "responseMimeType": "application/json",
        },
    }).encode()
    url = GEMINI_API.format(model=model) + f"?key={api_key}"
    req = urllib.request.Request(
        url, data=body, headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    return resp["candidates"][0]["content"]["parts"][0]["text"]


def _call_anthropic(system: str, user: str, model: str = DEFAULT_ANTHROPIC_MODEL) -> str:
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
    return resp["content"][0]["text"]


def _call_llm(system: str, user: str, *, backend: str | None = None, model: str | None = None) -> str:
    """Dispatch to whichever backend the caller asked for, or fall back
    to whichever has a configured key. Free backends win over paid."""
    if backend == "groq" or (backend is None and os.environ.get("GROQ_API_KEY")):
        return _call_groq(system, user, model=model or DEFAULT_GROQ_MODEL)
    if backend == "gemini" or (backend is None and os.environ.get("GEMINI_API_KEY")):
        return _call_gemini(system, user, model=model or DEFAULT_GEMINI_MODEL)
    if backend == "anthropic" or (backend is None and os.environ.get("ANTHROPIC_API_KEY")):
        return _call_anthropic(system, user, model=model or DEFAULT_ANTHROPIC_MODEL)
    raise RuntimeError(
        "no LLM backend configured. Set one of:\n"
        "  GROQ_API_KEY    (free, recommended — https://console.groq.com/keys)\n"
        "  GEMINI_API_KEY  (free — https://aistudio.google.com/apikey)\n"
        "  ANTHROPIC_API_KEY (paid)"
    )


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
             *, backend: str | None = None, model: str | None = None) -> dict:
    """Hit the configured LLM, return the parsed JSON package."""
    user = USER_PROMPT_TEMPLATE.format(
        topic_query=topic_query,
        context_block=_build_context(headlines, snippets or []),
    )
    raw = _call_llm(SYSTEM_PROMPT, user, backend=backend, model=model)
    pkg = json.loads(_strip_fence(raw))
    _validate_package(pkg, pkg.get("script", ""))
    pkg["topic"] = topic_query
    return pkg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="topic query (otherwise read JSON from stdin)")
    ap.add_argument("--headlines", action="append", default=[],
                    help="news headline context; repeat for multiple")
    ap.add_argument("--backend", choices=("groq", "gemini", "anthropic"),
                    help="force a specific LLM backend (default: auto)")
    ap.add_argument("--model", help="override the model name for the chosen backend")
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

    pkg = generate(topic, headlines, snippets, backend=args.backend, model=args.model)
    out_json = json.dumps(pkg, indent=2)
    if args.out:
        args.out.write_text(out_json)
        print(f"-> {args.out}")
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
