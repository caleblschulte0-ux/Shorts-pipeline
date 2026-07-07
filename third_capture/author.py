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

Return STRICT JSON: {"title": str, "hook": str, "hashtags": [str, ...]}

Rules:
- title: <= 85 chars, sells the MOMENT not the streamer ("He opened the one
  box he shouldn't have" beats "xQc funny moment"). Present tense, punchy,
  no emoji spam (max 1 emoji), no ALL CAPS words except a single emphasis.
  NEVER invent something that isn't supported by the transcript/original
  title — curiosity is fine, lying is not.
- hook: 4-8 words, ALL CAPS, shown on screen for the first 3 seconds. It
  frames the tension ("HE DID NOT SEE THIS COMING") without spoiling the
  payoff. Must be honest to the clip.
- hashtags: 10-14 lowercase tags, no '#'. Mix: the streamer, what's
  happening in the clip, and broad reach tags (clips, streamer, gaming,
  funny...). No spaces in tags.
"""


def author_package(streamer: str, clip_title: str, transcript: str,
                   views: int) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests
        user = (f"Streamer: {streamer}\n"
                f"Original clip title: {clip_title!r}\n"
                f"Twitch views in <24h: {views}\n"
                f"Transcript (whisper, may have small errors):\n"
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
        tags = [t for t in tags if 2 <= len(t) <= 30][:14]
        if not title or len(title) > 100:
            return None
        return {"title": title[:95], "hook": hook[:60], "hashtags": tags}
    except Exception as e:  # noqa: BLE001 — authoring never blocks a post
        print(f"[author] groq authoring skipped: {e}", flush=True)
        return None
