#!/usr/bin/env python3
"""Groq clip author — writes the packaging a raw Twitch clip can't.

Given the streamer, the clip's original title, and the whisper transcript
of what was actually said, produces:
  - a YouTube Shorts title that sells the MOMENT (raw clip titles are
    often garbage — "v", "W", "LOL")
  - a hook card line for the first 3 seconds
  - hashtags tuned to the clip + evergreen streamer tags

Best-effort: returns None whenever GROQ_API_KEY is missing or anything
fails, and the caller falls back to the raw clip title. The author only
packages what's in the transcript — instructed hard against inventing
events that don't happen in the clip (playbook: never clickbait the clip
doesn't pay off).
"""
from __future__ import annotations

import json
import os
import re

MODEL = "llama-3.3-70b-versatile"

SYSTEM = """You package Twitch/Kick clips as YouTube Shorts for a clip channel.
You are given the streamer name, the clip's original title, its view count on
Twitch, and the transcript of what is said in the clip.

Return STRICT JSON:
{"title": str, "hook": str, "caption": str, "hashtags": [str, ...],
 "series": str}

Rules:
- title: the formula is [Streamer name] + [emotional event] + [specific
  object/context]. Examples: "Kai Cenat Realizes Chat Set Him Up",
  "CaseOh Gets Jump-Scared So Hard He Leaves", "xQc Thinks He Won — Then
  This Happens". <= 85 chars, present tense, clarity first, emotion second.
  Max 1 emoji, no ALL-CAPS words except a single emphasis. NEVER invent
  something unsupported by the transcript/original title — curiosity is
  fine, lying is not.
- hook: 4-8 words, ALL CAPS, on screen for the first 3 seconds. Compressed
  conflict — one emotional label, one subject, one implied consequence
  ("CHAT SET HIM UP SO BADLY") without spoiling the payoff. Honest only.
- caption: ONE natural sentence for the video description (max ~140
  chars) — how a fan would describe the moment to a friend. Plain human
  wording, no jargon, no "clip from the allowlist" robot-speak, one
  emoji max.
- hashtags: EXACTLY 3-4 lowercase tags, no '#', no spaces. The streamer,
  the game/activity if clear, one broad tag (clips / streamer / gaming).
  Few and relevant beats many — over-tagging reduces relevance.
- series: one of "rage" | "chat-betrayal" | "jumpscare" | "clutch" |
  "fail" | "win" | "wholesome" | "argument" | "chaos" — the recurring
  shelf this moment belongs to.

HONESTY (hard rules):
- If the transcript is noisy, thin, or ambiguous, DO NOT infer what the
  clip is "about" — describe only what is certain (who + the energy of
  the moment) or lean on the original clip title.
- NEVER introduce sensitive themes (gender, sexuality, race, religion,
  politics) unless they are unmistakably the explicit subject of the
  transcript. A misheard word is not a subject.
- Spell the streamer's handle EXACTLY as given.
"""

# themes the author may not invent: if one of these appears in the
# authored title/hook but nowhere in the source material, the output is
# rejected and we fall back to the raw clip title
_SENSITIVE = ("gender", "feminin", "masculin", "trans", "race", "racis",
              "politic", "religio", "sexual", "sexist", "gay", "lesbian",
              "abortion", "immigra")


def _build_user_prompt(streamer: str, clip_title: str, transcript: str,
                       views: int) -> str:
    sparse = len(transcript.split()) < 8
    return (f"Streamer: {streamer}\n"
            f"Original clip title: {clip_title!r}\n"
            f"Twitch views in <24h: {views}\n"
            + ("NOTE: the clip has almost no dialogue (screaming/"
               "crowd moment) — build the title from the original "
               "clip title and the streamer, do NOT guess events.\n"
               if sparse else "")
            + f"Transcript (whisper, may have small errors):\n"
              f"{transcript[:1800]}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _postprocess(out: dict, streamer: str, context: str) -> dict | None:
    import difflib
    title = str(out.get("title", "")).strip()
    hook = str(out.get("hook", "")).strip().upper()
    tags = [re.sub(r"[^a-z0-9]", "", str(t).lower())
            for t in out.get("hashtags", [])]
    tags = [t for t in tags if 2 <= len(t) <= 30][:4]
    series = re.sub(r"[^a-z-]", "", str(out.get("series", "")).lower())
    if not title or len(title) > 100:
        return None
    # honesty gate: a sensitive theme in the title/hook that never
    # appears in the source material means the author guessed — reject
    ctx = context.lower()
    for w in _SENSITIVE:
        if (w in title.lower() or w in hook.lower()) and w not in ctx:
            print(f"::warning::[author] rejected — invented sensitive "
                  f"theme {w!r} not present in the clip", flush=True)
            return None
    # anchor the right streamer WITHOUT double-naming: a near-miss
    # spelling ('stablernaldo') is corrected in place, not prefixed
    pretty = streamer.strip("_").title()
    fixed_words = []
    matched = False
    for word in title.split():
        if _norm(word) == _norm(streamer) or \
                difflib.SequenceMatcher(
                    None, _norm(word), _norm(streamer)).ratio() > 0.8:
            fixed_words.append(pretty)
            matched = True
        else:
            fixed_words.append(word)
    title = " ".join(fixed_words)
    if not matched:
        title = f"{pretty}: {title}"
    caption = str(out.get("caption", "")).strip()[:180]
    return {"title": title[:95], "hook": hook[:60], "caption": caption,
            "hashtags": tags, "series": series or "chaos"}


def _call_claude(user: str) -> dict | None:
    """Headless Claude via the claude-code CLI (CLAUDE_CODE_OAUTH_TOKEN —
    the same brain the daily channel uses). Returns parsed JSON or None."""
    import shutil
    import subprocess
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        return None
    if not shutil.which("claude"):
        print("::warning::[author] claude CLI not installed — "
              "falling to Groq", flush=True)
        return None
    prompt = (SYSTEM + "\n\n" + user
              + "\n\nReturn ONLY the JSON object, nothing else.")
    r = subprocess.run(["claude", "-p", prompt], capture_output=True,
                       text=True, timeout=240)
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        raise RuntimeError(f"no JSON in claude output "
                           f"(rc={r.returncode})")
    return json.loads(m.group(0))


def _call_groq(user: str) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    import requests
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user}],
              "temperature": 0.7,
              "response_format": {"type": "json_object"}},
        timeout=45)
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def author_package(streamer: str, clip_title: str, transcript: str,
                   views: int) -> dict | None:
    """Claude-first (the brain), Groq fallback (LOUD, per repo doctrine),
    None (raw clip title) last. Authoring never blocks a post."""
    user = _build_user_prompt(streamer, clip_title, transcript, views)
    context = f"{clip_title} {transcript}"
    try:
        out = _call_claude(user)
        if out is not None:
            meta = _postprocess(out, streamer, context)
            if meta:
                print(f"[author] Claude authored: {meta['title']!r}",
                      flush=True)
                return meta
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[author] Claude failed ({e}) — falling to Groq",
              flush=True)
    try:
        out = _call_groq(user)
        if out is not None:
            meta = _postprocess(out, streamer, context)
            if meta:
                print(f"::warning::[author] GROQ FALLBACK authored: "
                      f"{meta['title']!r}", flush=True)
                return meta
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[author] groq authoring failed: {e}", flush=True)
    return None
