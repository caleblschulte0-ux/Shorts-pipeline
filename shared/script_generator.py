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
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

# Default model per backend.
# THE PRIMARY TEXT BRAIN WAS DEAD FOR FIVE WEEKS AND NOBODY SAW IT.
#
# Groq retired `llama-3.3-70b-versatile` on 2026-08-16 (announced by email
# on 06-17; console.groq.com/docs/deprecations). From that day every
# `_call_llm` got `HTTP Error 404` from Groq and fell through to Gemini's
# free tier — which the same run then exhausted, so by the time a rendered
# video needed the Gemini JUDGE fallback it was 429 too. Read off the
# 2026-09-22 09:36 explainer run: 18 Groq 404s, 9 Gemini 429s, every video
# held. Groq's named replacement is `openai/gpt-oss-120b` (JSON object mode,
# 131K context, free tier). `RETIRED_GROQ_MODELS` keeps a stale `GROQ_MODEL`
# env pin from resurrecting the 404; `tests/test_the_groq_model_is_alive.py`
# holds the pin against Groq's published shutdown list.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
RETIRED_GROQ_MODELS = frozenset({
    "llama-3.3-70b-versatile", "llama-3.1-8b-instant",          # 2026-08-16
    "qwen/qwen3.6-27b",                                          # 2026-09-14
    "groq/compound", "groq/compound-mini",                       # 2026-09-21
    "qwen/qwen3-32b", "meta-llama/llama-4-scout-17b-16e-instruct",  # 2026-07-17
})
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


class UnfitTopic(ValueError):
    """The topic cannot seed a story. Raised BEFORE any render is spent."""


# A reddit_story is FICTION ON A UNIVERSAL PREMISE (the registry's own words,
# `authoring_brief.FORMAT_SPECS["reddit_story"]`). It is never a retelling
# of the news, and it is never set next to a tragedy.
#
# 2026-09-22, the showrunner on four backfills in one afternoon: "a
# fabricated first-person 'cousin sold missiles' story laid over a real
# geopolitical headline", "a fabricated first-person 'cover-up' story about
# a real terror attack ... misinformation risk", and two ticker topics told
# as drama over brand photos. Every one was blocked at 18-22, and every one
# was authored by THIS module from a news topic the ranker had picked for
# a news channel, under a prompt that said "use the topic as loose
# inspiration". A real headline is not inspiration for fiction; it is the
# thing fiction must not be mistaken for. So a topic about death, violence,
# war, crime or politics is REFUSED before a word is written, the trend
# may only choose the story's SETTING (a coffee shop, a car dealership, an
# office), and no real person, company, product, place or event from the
# headline may appear in the story — held by `_validate_package`.
_UNFIT = re.compile(
    r"\b(?:terror\w*|attack\w*|bomb\w*|shoot\w*|shot|gunman|gunmen|kill\w*|"
    r"dead|death\w*|die[sd]?|dying|murder\w*|stab\w*|assault\w*|rape\w*|"
    r"abuse\w*|war|wars|warfare|missile\w*|airstrike\w*|arming|weapon\w*|"
    r"troops|military|hostage\w*|kidnap\w*|crash\w*|collision|disaster\w*|"
    r"earthquake\w*|hurricane\w*|tornado\w*|flood\w*|wildfire\w*|missing|"
    r"victim\w*|cancer|overdose\w*|suicide\w*|genocide|massacre\w*|famine|"
    r"epidemic|pandemic|outbreak|verdict|sentenced|indict\w*|arrest\w*|"
    r"trial|lawsuit|election\w*|senat\w*|congress|parliament|president\w*|"
    r"minister\w*|sanction\w*|houthi\w*|hamas|taliban|nato|kremlin|pentagon)\b",
    re.I)


def unfit_for_fiction(text: str) -> str | None:
    """The first word that makes `text` unusable as a story seed, or None.
    A refusal list, so it can only ever SKIP a topic — never admit one."""
    m = _UNFIT.search(text or "")
    return m.group(0) if m else None


def reddit_spec() -> dict:
    """The registry's own definition of a reddit_story — rules and the
    subreddit list — read at call time so this module never keeps a copy."""
    from shared import authoring_brief
    return authoring_brief.FORMAT_SPECS["reddit_story"]


def system_prompt() -> str:
    spec = reddit_spec()
    rules = "\n".join(f"- {r}" for r in spec["rules"])
    return (
        "You write ORIGINAL first-person Reddit-style storytime scripts for "
        "YouTube Shorts as strict JSON (1080x1920 vertical, ~45-60 seconds). "
        "The story is FICTION on a UNIVERSAL premise. It is never about the "
        "news, never a real event, and it names no real person, company, "
        "brand, product, place or organisation. Open on the shock, build "
        "tension, end on a twist or payoff.\n\nThe channel's rules for this "
        f"format:\n{rules}\n\nSubreddit: exactly one of "
        f"{', '.join(spec['subreddit_options'])}.\n"
        "Output JSON only - no prose, no fences.")


USER_PROMPT_TEMPLATE = """Setting seed: {topic_query}

What is trending right now (for SETTING and OCCUPATION only - a story set \
in a cafe, a hardware store, an airport, a rental office):
{context_block}

Schema:
{{
  "subreddit": "<one of the listed subreddits>",
  "title": "<6-10 word punchy YouTube title, first-person, no real names>",
  "script": "<130-170 words, first-person, sentence 1 drops into the shock/premise, builds tension, ends on the twist or payoff - NOT a question>",
  "hashtags": ["<3-5 lowercase tags, first one the subreddit>"],
  "shots": [
    {{"phrase": "<2-4 word VERBATIM substring of the script>",
      "query": "<1-3 word stock-footage search, visually concrete>"}}
  ],
  "punches": [
    {{"phrase": "<VERBATIM substring of the script>",
      "text": "<1-3 word ALL CAPS overlay>",
      "color": "<#hex>"}}
  ],
  "music_vibe": "<dark|cinematic|hiphop>"
}}

Hard rules (validated):

1. THE TREND IS A SETTING, NOT A STORY. Do not retell, reference or \
dramatise the news above. No real person, company, brand, product, place, \
event or organisation from it may appear anywhere in the title or script - \
the narrator is an ordinary person at work, and every name is invented. \
If the trend is about death, injury, violence, war, crime victims, disaster, \
illness or politics, it cannot seed a story: output ONLY \
{{"unusable": "<one line why>"}} and nothing else.

2. SCRIPT LENGTH: 130-170 words (renders ~45-60s, must fit a 60s Short). \
First-person, ONE paragraph. Must end on a statement.

3. OPEN-LOOP HOOK: Sentence 1 drops the viewer into the most shocking \
moment or the jaw-dropping premise so they NEED to know what happens. \
Name the drama, WITHHOLD the resolution. Good: "My landlord invented $4,000 \
of damage and then the neighbour handed me a key.", "The customer who \
mistook me for staff got exactly the help she asked for." Bad (vague / no \
stakes): "Something crazy happened at work." It is burned huge on the \
cover frame - make it a specific gut-punch.

4. ENDING: Land on the TWIST or payoff. Do NOT append a question ("What \
would you do?", "AITA?", "Part 2?") or any call-to-action.

5. BANNED phrases - algorithm-suppressed engagement-bait: "comment YES", \
"subscribe for part 2", "tag a friend", "let me know in the comments", \
"like if you agree", "drop a like".

6. TRIGGER PHRASES MUST BE VERBATIM SUBSTRINGS. Each shot.phrase and \
punch.phrase must appear in the script word-for-word, exact order.

7. NUMBERS in the script use digits ("12 dollars", "25%", "3 weeks") so \
audio transcription matches. Trigger phrases with numbers use digits too.

8. AVOID: "Wayfair" (transcribes as "wafer"); "Once" as a sentence opener \
(transcribes as "wants" - use "First" / "Back in" / "Once you").

9. SHOTS: exactly 6-8. shot.query is concrete b-roll matching the beat \
("angry customer", "phone text messages", "empty apartment", "cash \
register", "person walking away"), not an abstraction and never a brand.

10. PUNCHES: exactly 3-5. 1-3 ALL CAPS words on the most shocking phrases. \
Colors: #ff3030 (shock/bad), #50ff80 (positive), #ffaa30 (warning), \
#ffffff (neutral). The FIRST punch fires at video start (frame 0).

11. music_vibe: dark (serious), cinematic (big-picture), hiphop (upbeat).

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
    if model in RETIRED_GROQ_MODELS:
        print(f"[groq] '{model}' is retired on Groq — using {DEFAULT_GROQ_MODEL}",
              file=sys.stderr)
        model = DEFAULT_GROQ_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        # gpt-oss spends part of this budget on reasoning tokens before the
        # JSON; 2000 was enough for Llama's answer alone, not for both.
        "max_tokens": 4000,
        # Forces a valid JSON object back — no fence stripping needed.
        "response_format": {"type": "json_object"},
    }
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"     # a ranker, not a proof
    body = json.dumps(payload).encode()

    last_err: Exception | None = None
    # Backoff schedule: respect Retry-After when present, otherwise short
    # exponential. Kept SHORT by default (2 tries) so callers that HAVE a
    # fallback — entity_media drops to its regex visual extractor — bail to
    # it in seconds during a 429 storm instead of stalling ~90s per call
    # (which blew daily renders past the job timeout). Tune via
    # GROQ_MAX_RETRIES; raise it for the Groq script-gen fallback path.
    _retries = max(1, int(os.environ.get("GROQ_MAX_RETRIES", "2")))
    for attempt in range(_retries):
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
            wait = min(wait, 12)
            print(f"[groq] 429 rate-limited, sleeping {wait:.1f}s "
                  f"(attempt {attempt+1}/{_retries})", file=sys.stderr)
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


#: The headless brain's model and how long one judgment may take. A gate
#: asks this once per story, so a generous per-call timeout becomes a very
#: long run over a full catalogue; 90s is comfortably above a normal answer
#: and far below "the run is hung".
DEFAULT_CLAUDE_CLI_MODEL = "sonnet"
CLAUDE_CLI_TIMEOUT = int(os.environ.get("CLAUDE_CLI_TIMEOUT", "90"))

#: THE SHOWRUNNER SHARES THIS SUBSCRIPTION AND FAILS CLOSED.
#:
#: `scripts/showrunner_review.py` judges every rendered video on the same
#: CLAUDE_CODE_OAUTH_TOKEN, and CLAUDE.md is explicit that it holds
#: everything when it has no verdict: "a fail-closed gate with no judge holds
#: everything". A PRE-render gate asks this brain once per story and there
#: are 85 un-posted stories, so an unbounded judge would cheerfully spend the
#: whole subscription before the first render — and then the showrunner,
#: which is the load-bearing one, would get nothing and block the day. That
#: is a WORSE outage than the one this backend exists to fix, arrived at by
#: fixing it.
#:
#: So the gate gets a bounded allowance. When it runs out the backend raises
#: like any other unavailable one, the chain falls through, and the
#: deterministic floor stands — exactly the behaviour of the day before this
#: change, for the stories past the bound only. The showrunner never calls
#: `_call_llm`; it shells the CLI itself, so this counter cannot touch it.
CLAUDE_CLI_MAX_CALLS = int(os.environ.get("CLAUDE_CLI_MAX_CALLS", "40"))
_CLAUDE_CLI_CALLS = 0


def _call_claude_cli(system: str, user: str,
                     model: str | None = None) -> str:
    """The Claude HEADLESS BRAIN — the `claude` CLI on the
    CLAUDE_CODE_OAUTH_TOKEN subscription, NOT the paid API.

    WHY THIS EXISTS. On 2026-09-13 the explainer published nothing: its own
    log said `0 posted, 85 held by the gate, 0 faults`, every un-posted story
    held PRE-RENDER. The cause was not the gate being wrong — it was the gate
    being RIGHT and having nobody to ask. Both configured backends were down
    at once:

        [llm] groq unavailable (HTTP Error 404)
        [llm] gemini unavailable (HTTP Error 429: Too Many Requests)

    The `thesis` check is a crude keyword-overlap test with a SEMANTIC JUDGE
    as its designed escape hatch, so with no judge it fails closed on stories
    that are plainly on-topic — the headline "Americans Stopped Moving.
    Here's Why." against a segment called "mortgage lock-in", which IS the
    why. A fail-closed gate whose adjudicator is unreachable holds
    everything, and that is what an empty day looks like.

    And the whole time, a working Claude was sitting in the same job. Every
    publishing workflow already carries `CLAUDE_CODE_OAUTH_TOKEN` because the
    SHOWRUNNER refuses to run without it (CLAUDE.md: "any workflow that
    publishes MUST carry CLAUDE_CODE_OAUTH_TOKEN"). The judge simply never
    asked it.

    THIS ADDS A JUDGE, IT DOES NOT REMOVE ONE. No threshold moves, no rule
    relaxes, nothing gains a bypass. A story that this brain says has no
    bridge to its headline is still held — `_thesis_supports_headline` only
    accepts an exact `true`, and everything else is still UNAVAILABLE rather
    than a pass. The change is that "unavailable" stops being the answer on a
    day when two third-party APIs happen to be down together.

    LAST in the chain on purpose: it is the slowest of the four and spawns a
    process, so the two free HTTP backends and the paid API all get their
    turn first. It only ever runs when they have all failed — which is
    exactly the situation it was added for.
    """
    global _CLAUDE_CLI_CALLS
    # THE BUDGET IS CHECKED FIRST, before we even look for the binary: a
    # spent allowance is a decision, not a consequence of the environment,
    # and it should read the same on a runner with the CLI and one without.
    # (It also stopped the bound being untestable in CI, where the `tests`
    # job has no `claude` on PATH and the "not installed" error fired first.)
    if _CLAUDE_CLI_CALLS >= CLAUDE_CLI_MAX_CALLS:
        raise RuntimeError(
            f"headless-brain budget spent ({CLAUDE_CLI_MAX_CALLS} calls) — "
            f"the rest of this run's subscription belongs to the showrunner")
    if not shutil.which("claude"):
        raise RuntimeError(
            "claude CLI not installed (npm i -g @anthropic-ai/claude-code)")
    _CLAUDE_CLI_CALLS += 1
    prompt = f"{system}\n\n{user}"
    proc = subprocess.run(
        ["claude", "-p", prompt,
         "--model", model or DEFAULT_CLAUDE_CLI_MODEL,
         "--output-format", "text"],
        capture_output=True, text=True, timeout=CLAUDE_CLI_TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[:200]}")
    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("claude CLI returned nothing")
    return out


_LLM_CHAIN = (
    ("groq", "GROQ_API_KEY", lambda s, u, m: _call_groq(
        s, u, model=m or DEFAULT_GROQ_MODEL)),
    ("gemini", "GEMINI_API_KEY", lambda s, u, m: _call_gemini(
        s, u, model=m or DEFAULT_GEMINI_MODEL)),
    ("anthropic", "ANTHROPIC_API_KEY", lambda s, u, m: _call_anthropic(
        s, u, model=m or DEFAULT_ANTHROPIC_MODEL)),
    # The subscription brain, last: free, already present in every publishing
    # workflow, and the difference between "the judge is unavailable" and a
    # judgment. See `_call_claude_cli` for the day this cost.
    ("claude_cli", "CLAUDE_CODE_OAUTH_TOKEN", lambda s, u, m: _call_claude_cli(
        s, u, model=m)),
    # THE MAILBOX, dead last and needing no key: a question the run cannot
    # get answered is filed for ChatGPT and answered on the next run
    # (`shared/llm_mailbox.py`). On 2026-09-21 all four backends above were
    # gone at once and the editorial gate held 83 stories with nobody to
    # ask; this is the difference between "held until the brains return"
    # and "held one run". It returns exactly what a model would have said,
    # or raises — it never invents an answer.
    ("mailbox", None, lambda s, u, m: _call_mailbox(s, u)),
)


def _call_mailbox(system: str, user: str) -> str:
    from shared import llm_mailbox
    return llm_mailbox.call(system, user, caller="_call_llm")


def _call_llm(system: str, user: str, *, backend: str | None = None,
              model: str | None = None) -> str:
    """Dispatch to the backend the caller asked for, or walk the configured
    ones in order (free before paid) until one ANSWERS.

    This used to CHOOSE a backend and then raise whatever that one raised —
    the docstring said "fall back" but the code only ever selected. So a
    Groq rate limit was a total authoring outage even with Gemini configured:
    on 2026-08-11 all four trending backfill attempts and the entity-media
    pass died on `HTTP Error 429` in a run where the showrunner's own Gemini
    fallback key was present and idle. Falling through on a FAILURE is the
    thing the name always promised.

    An explicit `backend=` is still exact — the caller asked for that one, so
    it gets that one's error rather than a silent substitution.
    """
    if backend is not None:
        for name, _env, call in _LLM_CHAIN:
            if name == backend:
                return call(system, user, model)
        raise RuntimeError(f"unknown LLM backend {backend!r}")
    errs: list[str] = []
    for name, env, call in _LLM_CHAIN:
        if env and not os.environ.get(env):
            continue                       # env=None: always configured
        try:
            return call(system, user, model)
        except Exception as e:  # noqa: BLE001 — try the next backend
            errs.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
            print(f"[llm] {name} unavailable ({type(e).__name__}: "
                  f"{str(e)[:90]}) — trying the next backend",
                  file=sys.stderr, flush=True)
    if errs:
        raise RuntimeError("every configured LLM backend failed — "
                           + " | ".join(errs))
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


def _title_case(line: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", line) if len(w) > 3]
    return len(words) >= 3 and sum(w[:1].isupper() for w in words) >= 0.6 * len(words)


def _sentences(text: str) -> list[list[str]]:
    return [s.split() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "")
            if s.strip()]


def real_entities(topic_query: str, headlines: list[str],
                  snippets: list[str] | None = None) -> set[str]:
    """The named things in the trend a story must not contain.

    A name is a word the trend capitalises MID-SENTENCE in prose and never
    writes in lowercase anywhere. That one test separates "Tesla" from the
    "Price" of a Title-Case headline: a Title-Case line says nothing about
    which of its words are names, so its middle contributes none; the
    article text (`snippets`, from `_research`) says "price" in lowercase
    somewhere and "Tesla" never. A sentence's first word is sentence case,
    not a name, unless it opens a second sentence, is capitalised
    mid-sentence elsewhere, or is a word of the search query ("tesla
    recall" / "Tesla said on Monday..."). An all-lowercase line IS a search
    query, so its words are the subject, never evidence that "tesla" is an
    ordinary word."""
    from collections import Counter
    from shared.punchup_guard import _COMMON_CAPS, proper_nouns
    lines = [ln.strip() for ln in [topic_query or "", *(headlines or [])]
             if ln and ln.strip()]
    queries = {ln for ln in lines if ln == ln.lower()}
    query_words = set(re.findall(r"[a-z0-9'\-]+", " ".join(queries)))
    prose = [ln for ln in lines if ln not in queries and not _title_case(ln)]
    lower_seen = set(re.findall(r"\b[a-z][a-z0-9'\-]*\b",
                                " ".join(prose + list(snippets or []))))
    mid: set[str] = set()
    openers: Counter = Counter()
    for words in _sentences("\n".join(prose + list(snippets or []))):
        first = re.sub(r"[^A-Za-z0-9'\-]", "", words[0])
        if first[:1].isupper() and first.lower() not in _COMMON_CAPS:
            openers[first.lower()] += 1
        if len(words) > 1 and not _title_case(" ".join(words)):
            mid |= proper_nouns(" ".join(words[1:]))
    caps = mid | {w for w, n in openers.items()
                  if n >= 2 or w in mid or w in query_words}
    return {w for w in caps if w not in lower_seen and len(w) > 2}


def _validate_package(pkg: dict, real_entities: set[str] | None = None) -> list[str]:
    """Return a list of validation issues. Empty list = clean."""
    issues: list[str] = []
    try:
        subs = list(reddit_spec()["subreddit_options"])
    except Exception:                                       # noqa: BLE001
        subs = []
    if subs and pkg.get("subreddit") not in subs:
        issues.append(
            f"subreddit {pkg.get('subreddit')!r} is not one of {subs} - a "
            "package without one is not a reddit_story and cannot render.")
    if real_entities:
        from shared.punchup_guard import _all_words
        named = sorted(real_entities & _all_words(
            f"{pkg.get('title') or ''} {pkg.get('script') or ''}"))
        if named:
            issues.append(
                f"the story names the real news ({', '.join(named)}) - a "
                "reddit story is fiction on a universal premise. Remove every "
                "real person, company, product, place and event; invent names.")
    script = pkg.get("script", "") or ""
    script_lower = script.lower()

    # RESET v2 2026-07: Reddit drama storytime (~45-60s), open-loop hook, twist
    # ending (no question).
    word_count = len(script.split())
    if word_count < 100:
        issues.append(
            f"script is only {word_count} words — must be 130-170 words. "
            "Build the drama with more concrete beats."
        )
    elif word_count > 200:
        issues.append(
            f"script is {word_count} words — must be 130-170 words (renders "
            "~45-60s, must fit a 60s Short). Tighten it."
        )
    if not script.rstrip().endswith((".", "!")):
        issues.append(
            "script must end on a statement (period or exclamation) — end on the "
            "surprising payoff, NOT a question."
        )

    # Hook: first sentence must be a specific, dramatic open-loop that drops
    # the viewer into the shock — a real sentence (>=6 words), not a vague tease.
    hook_wc = _hook_word_count(script)
    if hook_wc < 6:
        issues.append(
            f"hook (first sentence) is only {hook_wc} words — drop the viewer "
            "into the specific shocking moment in sentence 1 (e.g. \"My fiance's "
            "mom read my private diary out loud at our rehearsal dinner.\")."
        )

    # No forced end question — the reset kills the one-word-answer kicker.
    if script.rstrip().endswith("?"):
        issues.append(
            "script ends with a question — the reset forbids the forced "
            "kicker question. End on the surprising payoff or consequence."
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
    if not (6 <= n_shots <= 8):
        issues.append(f"have {n_shots} shots — must be 6-8 (mood b-roll per beat).")
    n_punches = len(pkg.get("punches", []))
    if not (3 <= n_punches <= 5):
        issues.append(f"have {n_punches} punches — must be 3-5.")

    return issues


def generate(topic_query: str, headlines: list[str], snippets: list[str] | None = None,
             *, backend: str | None = None, model: str | None = None,
             max_retries: int = 2) -> dict:
    """Hit the configured LLM, return the parsed JSON package. If the
    first response fails validation (script length, trigger-phrase
    mismatch, etc.) we send the issues back to the model and ask for a
    fix — up to `max_retries` times before giving up and returning the
    last attempt with a warning."""
    seed = " ".join([topic_query or "", *(headlines or [])])
    hit = unfit_for_fiction(seed)
    if hit:
        raise UnfitTopic(f"{topic_query!r} cannot seed a story ({hit!r}): "
                         "a real tragedy, war, crime or politics is not "
                         "inspiration for fiction")
    names = real_entities(topic_query, headlines or [], snippets or [])
    user = USER_PROMPT_TEMPLATE.format(
        topic_query=topic_query,
        context_block=_build_context(headlines, snippets or []),
    )
    system = system_prompt()

    raw = _call_llm(system, user, backend=backend, model=model)
    pkg = json.loads(_strip_fence(raw))
    if isinstance(pkg, dict) and pkg.get("unusable"):
        raise UnfitTopic(f"{topic_query!r} refused by the writer: "
                         f"{str(pkg['unusable'])[:160]}")
    issues = _validate_package(pkg, names)

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
        raw = _call_llm(system, retry_user, backend=backend, model=model)
        try:
            pkg = json.loads(_strip_fence(raw))
        except json.JSONDecodeError:
            # Retry returned non-JSON; bail to the previous attempt.
            print("[script_generator] retry returned non-JSON, keeping prior attempt",
                  file=sys.stderr)
            break
        issues = _validate_package(pkg, names)

    if issues:
        print(f"[script_generator] WARNING: {len(issues)} unresolved issue(s):",
              file=sys.stderr)
        for i in issues:
            print(f"   - {i}", file=sys.stderr)

    # A story that STILL names the news after every retry does not exist:
    # it is the misinformation shape, and no render should be spent on it.
    from shared.punchup_guard import _all_words
    named = sorted(names & _all_words(
        f"{pkg.get('title') or ''} {pkg.get('script') or ''}"))
    if named:
        raise UnfitTopic(f"the story still names the real news "
                         f"({', '.join(named)}) after {max_retries} retries")

    # The subreddit is the card's label, nothing more; a package without one
    # would route to the retired stacked renderer, so it is filled here -
    # deterministically from the title, and SAID, never silently.
    subs = list(reddit_spec()["subreddit_options"])
    if pkg.get("subreddit") not in subs:
        pick = subs[sum(map(ord, pkg.get("title") or topic_query)) % len(subs)]
        print(f"[script_generator] WARNING: subreddit {pkg.get('subreddit')!r} "
              f"not in the registry's list - card labelled r/{pick}",
              file=sys.stderr)
        pkg["subreddit"] = pick
    if not pkg.get("slug"):
        pkg["slug"] = re.sub(r"[^a-z0-9]+", "-",
                             (pkg.get("title") or topic_query).lower()).strip("-")[:60]
    if not isinstance(pkg.get("hashtags"), list) or not pkg["hashtags"]:
        pkg["hashtags"] = [pkg["subreddit"].lower(), "storytime", "reddit"]
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
