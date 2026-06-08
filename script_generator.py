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
import urllib.error
import urllib.request
from pathlib import Path


ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

# Default model per backend.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


SYSTEM_PROMPT = """You write viral-style YouTube Shorts scripts as strict JSON. \
1080x1920 vertical, ~45 seconds, doomscroll-explainer tone: factual hook, dense \
delivery, no filler, no editorial opinion. Each shot can carry a `mascot_pose` \
hint for the on-screen anchor character. Output JSON only — no prose, no fences."""


USER_PROMPT_TEMPLATE = """Topic: {topic_query}

Context (headlines and snippets driving the trend):
{context_block}

Schema:
{{
  "title": "<6-10 word punchy YouTube title>",
  "script": "<110-140 words, opens with a SHORT hook (<=5 words ending in ? or !), ends with a one-word-answer question>",
  "shots": [
    {{"phrase": "<2-4 word VERBATIM substring of the script>",
      "query": "<1-3 word stock-footage search, visually concrete>",
      "mascot_pose": "<idle|shock|point|laugh|think|dismiss>"}}
  ],
  "punches": [
    {{"phrase": "<VERBATIM substring of the script>",
      "text": "<1-3 word ALL CAPS overlay>",
      "color": "<#hex>"}}
  ],
  "music_vibe": "<dark|cinematic|hiphop>"
}}

Hard rules (validated):

1. SCRIPT LENGTH: 110-140 words, must end with a period or question mark. Shorter is rejected.

2. HOOK: The first sentence MUST be a punchy question or 1-word exclamation, \
5 words or fewer. Good: "A kangaroo did WHAT?", "Why fire 30,000 people?", \
"This shouldn't be legal.". Bad: "Apple just unveiled a new...", "X is dying." \
(too long, declarative). The hook is what stops the swipe.

3. KICKER: The final sentence MUST be a question the viewer can answer in ONE \
WORD or comma-pick (yes/no, A/B, single noun). Specific to the story, not \
generic. Good: "Would you have eaten that kangaroo?", "Was the captain right?", \
"Could YOU survive a 9.0 quake?". Bad: "What do you think?", "Let us know!" \
(generic = no comments).

4. BANNED phrases — algorithm-suppressed engagement-bait: "comment YES", \
"subscribe for part 2", "tag a friend", "let me know in the comments", \
"like if you agree", "drop a like".

5. SCRIPT SHAPE: Question hook (5 words max) → 6-9 dense factual sentences → \
one-word-answer question kicker. Mention {topic_query} clearly enough that a \
stranger understands.

6. TRIGGER PHRASES MUST BE VERBATIM SUBSTRINGS. Each shot.phrase and punch.phrase \
must appear in the script word-for-word, exact order. Mismatches break the renderer.

7. NUMBERS in the script use digits ("12 million", "25%", "1980") so audio transcription \
matches. Trigger phrases that contain numbers must also use digits.

8. AVOID: "Wayfair" (transcribes as "wafer"); "Once" as a sentence opener \
(transcribes as "wants" — use "First" / "Back in" / "Once you").

9. SHOTS: exactly 10-14. shot.query is a concrete visible noun ("empty store shelves", \
"stock chart"), not an abstraction ("economic anxiety", "frustration").

10. MASCOT POSE per shot — one of: idle (default, neutral at desk), shock \
(twist / surprising fact), point (first mention of the central entity), laugh \
(absurd/quirky beat), think (setup / mystery framing), dismiss (skeptical \
kicker). Default to "idle" for most shots. **At most 3 non-idle poses per \
script** — over-reacting defeats the watermark feel.

11. PUNCHES: exactly 6-10. 1-3 ALL CAPS words. Colors: #ff3030 (shock/bad), \
#50ff80 (positive), #ffaa30 (warning), #ffffff (neutral). The FIRST punch \
fires at video start (frame 0) so the shock-number is on screen before the \
TTS even speaks.

12. music_vibe: dark (serious/exposé), cinematic (big-picture), hiphop (cultural/upbeat).

Output ONLY the JSON object."""


# Sent to the model when validation fails on the first try. We list
# the specific problems and ask for a corrected JSON object back.
RETRY_PROMPT_TEMPLATE = """Your previous JSON output failed validation. Issues:

{issues}

Here was your previous output:
{previous}

Fix every issue and output the corrected JSON object. Same schema, same rules. \
Output ONLY the JSON object."""


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
    tier on Llama 3.3 70B: 30 RPM, 14,400 RPD, AND 6,000 TPM. The TPM
    limit is what bites — a single ranker call + 6 script gens is
    ~25K tokens spread over 30s of looping, well over the cap. We
    retry on 429 with exponential backoff so the orchestrator doesn't
    cascade-fail when we get throttled."""
    import time as _time
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

    last_err: Exception | None = None
    # Backoff schedule: respect Retry-After when present, otherwise
    # exponential with jitter. 5 attempts ~= up to ~60s of waiting,
    # enough for TPM windows to roll over.
    for attempt in range(5):
        req = urllib.request.Request(
            GROQ_API,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                # Groq sits behind Cloudflare, which 1010-blocks the
                # default "Python-urllib/X" user agent.
                "User-Agent": "shorts-pipeline/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            return resp["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code != 429:
                raise
            retry_after = e.headers.get("Retry-After") if e.headers else None
            try:
                wait = float(retry_after) if retry_after else (2 ** attempt) * 4
            except ValueError:
                wait = (2 ** attempt) * 4
            wait = min(wait, 30)
            print(f"[groq] 429 rate-limited, sleeping {wait:.1f}s (attempt {attempt+1}/5)",
                  file=sys.stderr)
            _time.sleep(wait)
    raise last_err if last_err else RuntimeError("groq retry exhausted")


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


# Allowed mascot poses. Unknown / missing pose falls back to "idle" in
# the renderer; we DO surface a soft warning so the model learns to fill
# the field on retry.
_VALID_POSES = frozenset({"idle", "shock", "point", "laugh", "think", "dismiss"})

# Suppression-bait phrases the algorithm flags. We reject scripts that
# contain any of these — see 1kReach 2026 research.
_BANNED_PHRASES = (
    "comment yes",
    "subscribe for part",
    "tag a friend",
    "let me know in the comments",
    "like if you agree",
    "drop a like",
)


def _hook_word_count(script: str) -> int:
    """Word count of the first sentence (the hook). Splits on the first
    ., ?, or ! — whichever comes first. Used by the validator to enforce
    the ≤5-word hook rule that drives 3-second hold."""
    first = re.split(r"[.!?]", script.strip(), maxsplit=1)[0]
    return len([w for w in first.split() if w])


def _validate_package(pkg: dict) -> list[str]:
    """Return a list of validation issues. Empty list = clean."""
    issues: list[str] = []
    script = pkg.get("script", "") or ""
    script_lower = script.lower()

    word_count = len(script.split())
    if word_count < 100:
        issues.append(
            f"script is only {word_count} words — must be 110-140 words. "
            "Add more factual content."
        )
    elif word_count > 150:
        issues.append(
            f"script is {word_count} words — must be 110-140 words. Tighten it."
        )
    if not script.rstrip().endswith((".", "!", "?")):
        issues.append("script must end with a period, exclamation, or question mark.")

    # Hook: first sentence must be ≤5 words AND end with ? or !.
    hook_wc = _hook_word_count(script)
    if hook_wc > 5:
        issues.append(
            f"hook (first sentence) is {hook_wc} words — must be 5 or fewer. "
            "Rewrite as a short question or exclamation that stops the swipe."
        )
    first_punct = next((c for c in script if c in ".!?"), "")
    if first_punct == ".":
        issues.append(
            "hook ends with a period — must end with ? or ! to drive 3-second "
            "hold. Make it a question or exclamation."
        )

    # Kicker: last non-empty sentence must be a question.
    last = re.split(r"[.!?]", script.rstrip(".!?").strip())
    last_sentence = next((s for s in reversed(last) if s.strip()), "")
    # The final character of the whole script tells us if it ended with ?.
    if not script.rstrip().endswith("?"):
        issues.append(
            "kicker (final sentence) must end with a question mark — a story-"
            "specific question answerable in one word ('yes/no' or 'A/B'). "
            "Generic 'what do you think?' is also rejected; the question must "
            "name a thing from the story."
        )

    # Suppression-bait phrases.
    for bad in _BANNED_PHRASES:
        if bad in script_lower:
            issues.append(
                f"banned phrase {bad!r} appears in script — algorithm-suppressed "
                "engagement-bait. Remove it; the kicker question already drives "
                "comments."
            )

    for s in pkg.get("shots", []):
        phrase = (s.get("phrase") or "").lower().strip()
        if not phrase:
            issues.append("shot has empty phrase")
        elif phrase not in script_lower:
            issues.append(
                f"shot trigger phrase {s['phrase']!r} is not a verbatim substring "
                f"of the script. Either change the script to include it, or pick "
                f"a different trigger phrase that IS in the script."
            )
        pose = (s.get("mascot_pose") or "").strip().lower()
        if pose and pose not in _VALID_POSES:
            issues.append(
                f"shot has unknown mascot_pose {pose!r} — must be one of: "
                f"{sorted(_VALID_POSES)}. Omit the field for 'idle'."
            )

    # Cap non-idle poses at 3 per script so the mascot stays watermark-feel.
    non_idle = sum(
        1 for s in pkg.get("shots", [])
        if (s.get("mascot_pose") or "idle").strip().lower() not in ("", "idle")
    )
    if non_idle > 3:
        issues.append(
            f"{non_idle} shots have non-idle mascot_pose — max 3 per script. "
            "Reactive poses are for the 2-3 emotional beats only; the rest "
            "stay idle."
        )

    for p in pkg.get("punches", []):
        phrase = (p.get("phrase") or "").lower().strip()
        if not phrase:
            issues.append("punch has empty phrase")
        elif phrase not in script_lower:
            issues.append(
                f"punch trigger phrase {p['phrase']!r} is not a verbatim substring "
                f"of the script. Either change the script to include it, or pick "
                f"a different trigger phrase that IS in the script."
            )

    n_shots = len(pkg.get("shots", []))
    if not (10 <= n_shots <= 14):
        issues.append(f"have {n_shots} shots — must be 10-14.")
    n_punches = len(pkg.get("punches", []))
    if not (6 <= n_punches <= 10):
        issues.append(f"have {n_punches} punches — must be 6-10.")

    return issues


def generate(topic_query: str, headlines: list[str], snippets: list[str] | None = None,
             *, backend: str | None = None, model: str | None = None,
             max_retries: int = 2) -> dict:
    """Hit the configured LLM, return the parsed JSON package. If the
    first response fails validation (script length, trigger-phrase
    mismatch, etc.) we send the issues back to the model and ask for a
    fix — up to `max_retries` times before giving up and returning the
    last attempt with a warning."""
    user = USER_PROMPT_TEMPLATE.format(
        topic_query=topic_query,
        context_block=_build_context(headlines, snippets or []),
    )

    raw = _call_llm(SYSTEM_PROMPT, user, backend=backend, model=model)
    pkg = json.loads(_strip_fence(raw))
    issues = _validate_package(pkg)

    attempt = 0
    while issues and attempt < max_retries:
        attempt += 1
        print(f"[script_generator] attempt {attempt}: {len(issues)} issue(s), retrying",
              file=sys.stderr)
        for i in issues:
            print(f"   - {i}", file=sys.stderr)
        retry_user = RETRY_PROMPT_TEMPLATE.format(
            issues="\n".join(f"- {i}" for i in issues),
            previous=json.dumps(pkg, indent=2),
        )
        raw = _call_llm(SYSTEM_PROMPT, retry_user, backend=backend, model=model)
        try:
            pkg = json.loads(_strip_fence(raw))
        except json.JSONDecodeError:
            # Retry returned non-JSON; bail to the previous attempt.
            print("[script_generator] retry returned non-JSON, keeping prior attempt",
                  file=sys.stderr)
            break
        issues = _validate_package(pkg)

    if issues:
        print(f"[script_generator] WARNING: {len(issues)} unresolved issue(s):",
              file=sys.stderr)
        for i in issues:
            print(f"   - {i}", file=sys.stderr)

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
