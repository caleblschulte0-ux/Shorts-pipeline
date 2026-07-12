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
 "series": str,
 "edit": {"slam": str, "emoji": str, "replay_worthy": bool,
          "cut": {"start": number, "end": number}, "complete": bool}}

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
- edit: you also DIRECT the edit (a human editor's judgement):
  - slam: the punchline word(s) that slam on screen at the peak — 1-2
    words, <= 12 chars, taken VERBATIM from the transcript (the funniest/
    most explosive thing actually said), or "" when nothing said fits.
    Never write a word nobody said.
  - emoji: exactly one of "skull" | "fire" | "sob" | "joy" | "eyes" |
    "mindblown" | "scream" | "flushed" | "pleading" | "rage" — the
    reaction a viewer would actually comment on this moment.
  - replay_worthy: true ONLY if the peak moment genuinely rewards seeing
    twice (a visible event, a wild line). Talking with nothing visual
    happening = false.
  - cut: {"start","end"} in SECONDS into this clip — the span to KEEP so a
    first-time viewer instantly understands the moment. Use the [t.t-t.t]
    timestamps in the transcript. start early enough to include the SETUP
    (what's happening / the question / the stakes) — never open in the
    middle of a sentence or reaction with no context. end AFTER the full
    payoff AND its reaction lands (the laugh, the stunned pause, the
    "bro"). It is better to keep a little extra than to clip the payoff.
    If the whole clip is needed, use start 0 and end = the clip length.
  - complete: true if this clip CONTAINS both an understandable beginning
    and the payoff. false if it starts mid-action with no way to tell
    what's going on, OR the payoff is clearly cut off (the clip ends right
    as the key thing is happening, before you see the result/reaction). A
    false clip confuses the viewer, so we skip it — only mark false when
    you are genuinely sure the clip is broken this way; when unsure, true.

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


def _timestamped(words: list[dict]) -> str:
    """Compact [start-end] transcript so the director can reason about WHEN
    the setup and payoff happen (for the cut boundaries)."""
    lines, cur, cs, ce = [], [], None, None
    for w in words:
        if cs is None:
            cs = w["s"]
        cur.append(w["w"])
        ce = w["e"]
        if len(cur) >= 8:
            lines.append(f"[{cs:.1f}-{ce:.1f}] {' '.join(cur)}")
            cur, cs = [], None
    if cur:
        lines.append(f"[{cs:.1f}-{ce:.1f}] {' '.join(cur)}")
    return "\n".join(lines)


def _build_user_prompt(streamer: str, clip_title: str, transcript: str,
                       views: int, words: list[dict] | None = None,
                       clip_dur: float = 0.0) -> str:
    sparse = len(transcript.split()) < 8
    body = (_timestamped(words) if words else transcript)[:1800]
    dur_note = (f"Clip length: {clip_dur:.1f}s. The transcript below is "
                f"time-stamped [start-end] in seconds — use it to choose "
                f"edit.cut.\n" if words and clip_dur else "")
    return (f"Streamer: {streamer}\n"
            f"Original clip title: {clip_title!r}\n"
            f"Twitch views in <24h: {views}\n"
            + dur_note
            + ("NOTE: the clip has almost no dialogue (screaming/"
               "crowd moment) — build the title from the original "
               "clip title and the streamer, do NOT guess events.\n"
               if sparse else "")
            + f"Transcript (whisper, may have small errors):\n{body}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _postprocess(out: dict, streamer: str, context: str,
                 clip_dur: float = 0.0) -> dict | None:
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

    # Edit direction (validated hard — the renderer must never trust raw
    # model output): slam must be words actually present in the source
    # material, emoji from the asset whitelist, replay a strict bool.
    _EMOJI_OK = {"skull", "fire", "sob", "joy", "eyes", "mindblown",
                 "scream", "flushed", "pleading", "rage"}
    edit_raw = out.get("edit") or {}
    slam = re.sub(r"[^A-Za-z0-9 !?']", "",
                  str(edit_raw.get("slam", ""))).strip().upper()[:14]
    if slam and _norm(slam) not in _norm(context):
        slam = ""                     # said by nobody → not a slam
    emoji = str(edit_raw.get("emoji", "")).strip().lower()
    if emoji not in _EMOJI_OK:
        emoji = ""
    edit = {"slam": slam, "emoji": emoji,
            "replay_worthy": bool(edit_raw.get("replay_worthy", True)),
            "complete": bool(edit_raw.get("complete", True))}

    # Narrative cut window (§9): trusted only when it's sane against the
    # known clip length — a >=3s span inside [0, clip_dur]. Anything off
    # falls back to the heuristic tight-cut (no cut key).
    cut_raw = edit_raw.get("cut") or {}
    try:
        cs, ce = float(cut_raw.get("start")), float(cut_raw.get("end"))
        lo, hi = max(0.0, cs), (min(ce, clip_dur) if clip_dur else ce)
        if hi - lo >= 3.0 and lo >= 0.0 and (not clip_dur or hi <= clip_dur
                                             + 0.5):
            edit["cut"] = {"start": round(lo, 2), "end": round(hi, 2)}
    except (TypeError, ValueError):
        pass

    return {"title": title[:95], "hook": hook[:60], "caption": caption,
            "hashtags": tags, "series": series or "chaos", "edit": edit}


def _call_claude(user: str, system: str = SYSTEM) -> dict | None:
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
    prompt = (system + "\n\n" + user
              + "\n\nReturn ONLY the JSON object, nothing else.")
    r = subprocess.run(["claude", "-p", prompt], capture_output=True,
                       text=True, timeout=240)
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        raise RuntimeError(f"no JSON in claude output "
                           f"(rc={r.returncode})")
    return json.loads(m.group(0))


def _call_groq(user: str, system: str = SYSTEM) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    import requests
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              "temperature": 0.5,
              "response_format": {"type": "json_object"}},
        timeout=45)
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


# ---------------------------------------------- clip selection ("banger") brain

_RANK_SYSTEM = """You are a viral-Shorts curator for a Twitch/Kick clip
channel with a mass general audience (a 16-year-old scrolling Shorts). You are
given candidate clips (streamer, title, Twitch views, velocity). Score each
for how likely a GENERAL audience would WATCH TO THE END and SHARE it as a
vertical Short.

Score 0.0-1.0:
- HIGH (0.8-1.0): a clear funny / shocking / heated / wholesome / dramatic
  MOMENT that reads instantly — a fail, a rage, a clutch, a betrayal, a
  jumpscare, a wild reaction.
- MEDIUM (0.4-0.6): probably fine but generic, or the title is vague/garbage
  so you can't tell (unknown = 0.5, NEVER 0 — a bad title often hides a great
  clip; don't punish it, just don't boost it).
- LOW (0.0-0.3): actively bad for a Short — giveaway/drops/subathon/"gifted"
  spam, sponsor/ad reads, pure technical/setup talk, "just chatting" with
  nothing happening, or clearly boring/insider content a stranger won't get.

Return ONLY JSON: {"scores": [{"i": <index int>, "banger": <0-1>,
"why": "<=6 words"}]}. One entry per candidate, same indices given."""


def rank_clips(clips: list[dict]) -> dict:
    """Banger score per clip -> {clip_key_or_url: (banger, why)}. One brain
    call (Claude, Groq fallback). Empty dict when no brain/parse fails — the
    caller then keeps pure-velocity ranking. Never raises."""
    if not clips:
        return {}
    lines = []
    for i, c in enumerate(clips):
        lines.append(f"{i}. streamer={c.get('channel','?')} "
                     f"views={c.get('views',0)} vph={c.get('vph',0):.0f} "
                     f"title={str(c.get('title',''))[:90]!r}")
    user = "Candidates:\n" + "\n".join(lines)
    out = None
    try:
        out = _call_claude(user, system=_RANK_SYSTEM)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[rank] claude failed ({e}) — groq", flush=True)
    if out is None:
        try:
            out = _call_groq(user, system=_RANK_SYSTEM)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[rank] groq failed ({e})", flush=True)
    if not out:
        return {}
    result = {}
    for s in (out.get("scores") or []):
        try:
            i = int(s["i"])
            b = max(0.0, min(1.0, float(s.get("banger", 0.5))))
            if 0 <= i < len(clips):
                key = clips[i].get("url", "")
                result[key] = (b, str(s.get("why", ""))[:40])
        except (TypeError, ValueError, KeyError):
            continue
    return result


def author_package(streamer: str, clip_title: str, transcript: str,
                   views: int, words: list[dict] | None = None,
                   clip_dur: float = 0.0) -> dict | None:
    """Claude-first (the brain), Groq fallback (LOUD, per repo doctrine),
    None (raw clip title) last. Authoring never blocks a post. `words`
    (timestamped) + `clip_dur` let the director choose the narrative cut."""
    user = _build_user_prompt(streamer, clip_title, transcript, views,
                              words=words, clip_dur=clip_dur)
    context = f"{clip_title} {transcript}"
    try:
        out = _call_claude(user)
        if out is not None:
            meta = _postprocess(out, streamer, context, clip_dur=clip_dur)
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
            meta = _postprocess(out, streamer, context, clip_dur=clip_dur)
            if meta:
                print(f"::warning::[author] GROQ FALLBACK authored: "
                      f"{meta['title']!r}", flush=True)
                return meta
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[author] groq authoring failed: {e}", flush=True)
    return None
