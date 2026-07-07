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
{"title": str, "hook": str, "hashtags": [str, ...], "series": str}

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
- hashtags: EXACTLY 3-4 lowercase tags, no '#', no spaces. The streamer,
  the game/activity if clear, one broad tag (clips / streamer / gaming).
  Few and relevant beats many — over-tagging reduces relevance.
- series: one of "rage" | "chat-betrayal" | "jumpscare" | "clutch" |
  "fail" | "win" | "wholesome" | "argument" | "chaos" — the recurring
  shelf this moment belongs to.
"""


def author_package(streamer: str, clip_title: str, transcript: str,
                   views: int) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests
        sparse = len(transcript.split()) < 8
        user = (f"Streamer: {streamer}\n"
                f"Original clip title: {clip_title!r}\n"
                f"Twitch views in <24h: {views}\n"
                + ("NOTE: the clip has almost no dialogue (screaming/"
                   "crowd moment) — build the title from the original "
                   "clip title and the streamer, do NOT guess events.\n"
                   if sparse else "")
                + f"Transcript (whisper, may have small errors):\n"
                  f"{transcript[:1800]}")
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
        out = json.loads(resp.json()["choices"][0]["message"]["content"])
        title = str(out.get("title", "")).strip()
        hook = str(out.get("hook", "")).strip().upper()
        tags = [re.sub(r"[^a-z0-9]", "", str(t).lower())
                for t in out.get("hashtags", [])]
        tags = [t for t in tags if 2 <= len(t) <= 30][:4]
        series = re.sub(r"[^a-z-]", "", str(out.get("series", "")).lower())
        if not title or len(title) > 100:
            return None
        # the title formula REQUIRES the right streamer: if the author
        # named someone else (or nobody), anchor it to the real handle
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
        if norm(streamer) not in norm(title):
            title = f"{streamer.strip('_').title()}: {title}"
        return {"title": title[:95], "hook": hook[:60], "hashtags": tags,
                "series": series or "chaos"}
    except Exception as e:  # noqa: BLE001 — authoring never blocks a post
        print(f"[author] groq authoring skipped: {e}", flush=True)
        return None
