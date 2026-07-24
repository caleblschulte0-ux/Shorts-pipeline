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
{"title": str, "hook": str, "caption": str, "cta": str, "hashtags": [str, ...],
 "series": str,
 "edit": {"slam": str, "emoji": str, "replay_worthy": bool,
          "cut": {"start": number, "end": number}, "complete": bool}}

This niche is REALITY TV: viewers follow PEOPLE and DRAMA — fights, beef,
crying, betrayal, breakups, getting caught / kicked / exposed / humbled,
shocking reactions — not game mechanics. The clips that reach millions are
framed as a STORY a stranger will tap to see, and they lead with the
person's NAME (a name earns the swipe from fans AND captures the search).
Package every clip that way.

Rules:
- title: sell the MOMENT as a story someone must tap. Shape:
  [WHO — streamer/person by name] + [the dramatic/emotional thing that
  happens] + [a curiosity gap or consequence that makes you need to watch].
  The winning shape (real top performers): "Kai Cenat Starts Crying And Ends
  The Stream After This", "Crystal Was So Done After This Girl Kept
  Disrespecting Her", "Stableronaldo Can't Believe What Kai Just Did". Lead
  with the name; present tense; real emotional stakes; exactly one curiosity
  gap. <= 90 chars, max 1 emoji, at most one ALL-CAPS emphasis word. NEVER
  invent an event the transcript/original title doesn't support — tease
  honestly, do not lie or clickbait a payoff that isn't there.
- hook: 4-8 words, ALL CAPS, on screen the first 3 seconds. The dramatic
  stakes in one breath — a curiosity gap that stops the swipe ("SHE KEPT
  DISRESPECTING HER", "THEN IT ALL WENT WRONG") without spoiling the payoff.
  Honest only.
- caption: ONE natural sentence for the video description (max ~140
  chars) — how a fan would describe the moment to a friend. Plain human
  wording, no jargon, no "clip from the allowlist" robot-speak, one
  emoji max.
- cta: ONE short comment-baiting question (<= 70 chars) that makes a viewer
  want to reply with a TAKE — the single biggest lever for the Shorts feed,
  which promotes videos that spark comments. Provoke a SIDE or an opinion on
  the drama: "Was Jason overreacting or was that fair? 👇", "Who's actually
  in the wrong here?", "Team Lacy or team coach?". Tie it to THIS clip's
  conflict, never generic ("comment below!"). End with the question. If the
  clip has no opinion-worthy conflict (pure wholesome/hype), use a lighter
  prompt ("Rate that reaction 1-10 👇"). Honest — never invent a conflict
  that isn't in the clip.
- hashtags: 5-7 lowercase tags, no '#', no spaces. LEAD with the specific
  pull — the streamer/person's name AND the live event or storyline if there
  is one (e.g. streameruniversity) — then the game/activity and the emotional
  beat, then ONE broad tag (streamerclips / clips). Names + the event are
  what people search and what the feed clusters; put them FIRST, generic tags
  last.
- series: one of "drama" | "beef" | "rage" | "chat-betrayal" | "jumpscare" |
  "clutch" | "fail" | "win" | "wholesome" | "argument" | "chaos" — the
  recurring shelf this moment belongs to (favor the human-drama labels when
  they fit; that is what travels).
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
    LENGTH: aim for a 12-30s keep window — long enough for the setup +
    payoff + reaction, short enough that a scroller actually finishes it.
    Only exceed ~35s when the payoff genuinely needs the buildup; never pad
    with rambling/dead time (a 38s "he explains his reasoning" clip loses
    the audience). And do not cut so tight (<8s) that the moment has no
    room to breathe.
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

# HARD title/hook safety gate: slurs and demeaning "calls him/her X" insult
# framings must NEVER go in our public title, even if the word is said in the
# clip (unlike _SENSITIVE, which only blocks INVENTED themes). A match rejects
# the authored packaging and we fall back to the streamer's own clip title.
# (Live incident: a Groq-fallback title "Silky Calls Him Gay".)
_TITLE_UNSAFE = re.compile(
    r"\b(f[a@4]gg?[o0]t?s?|n[i1]gg[ae]?r?s?|r[e3]t[a@4]rds?|tr[a@4]nn(y|ies)"
    r"|dyke|kike|spic|chink|coon"
    r"|calls?\s+(him|her|them|\w+)\s+(gay|a\s+\w+)"
    r"|is\s+(gay|a\s+(fag|retard))"
    r"|gay\s+for)\b",
    re.I)

# The removal counterpart of _TITLE_UNSAFE: the exact fragments to excise
# when we must SANITISE rather than reject. Used for the raw-clip-title
# fallback path — that text is the streamer's own Twitch title, which we do
# not control, so rejecting it isn't an option (it would lose the slot). We
# strip the offending phrase instead and, if nothing usable is left, build a
# clean streamer-based drama title. (Live incident: raw title "Silky Calls
# Him Gay" published because the authored-title reject fell back to the raw
# title verbatim — this closes that path.)
_UNSAFE_FRAG = re.compile(
    r"\bcalls?\s+(?:him|her|them|\w+)\s+(?:gay|a\s+\w+)\b"
    r"|\bis\s+(?:gay|a\s+(?:fag\w*|retard\w*))\b"
    r"|\bgay\s+for\b"
    r"|\b(?:f[a@4]gg?[o0]t?s?|n[i1]gg[ae]?r?s?|r[e3]t[a@4]rds?"
    r"|tr[a@4]nn(?:y|ies)|dyke|kike|spic|chink|coon)\b",
    re.I)


def title_is_unsafe(s: str) -> bool:
    """True if a slur or demeaning insult-framing is present. The single
    source of truth for the safety gate (used by both the authored-title
    reject and the raw-title sanitiser)."""
    return bool(_TITLE_UNSAFE.search(s or ""))


def scrub_text(s: str) -> str:
    """Excise unsafe fragments from free text (captions, descriptions)
    without any title-shaped fallback — returns whatever clean text remains,
    which may be shorter. Safe to call on any public-facing string."""
    if not title_is_unsafe(s):
        return s
    out = _UNSAFE_FRAG.sub("", s)
    out = re.sub(r"\s{2,}", " ", out).strip(" -:—,")
    return out


def safe_title(raw: str, streamer: str = "") -> str:
    """Guarantee a publishable title. Authored titles already pass the gate
    in _postprocess; THIS protects the raw-clip-title fallback path, whose
    text we don't control. It never rejects (that would lose the slot) — it
    strips the unsafe fragment and, if too little remains, returns a clean
    streamer-based drama title so a slot always ships a safe title."""
    t = (raw or "").strip()
    if not title_is_unsafe(t):
        return t
    cleaned = scrub_text(t)
    # a residual match (nested phrasing) or too little left → neutral title
    if title_is_unsafe(cleaned) or len(cleaned.split()) < 2:
        pretty = (streamer or "").strip("_").title()
        cleaned = (f"{pretty} Has The Whole Stream Reacting" if pretty
                   else "The Clip Everyone's Talking About")
    print(f"::warning::[author] sanitised unsafe raw title "
          f"{raw!r} -> {cleaned!r}", flush=True)
    return cleaned


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
                       clip_dur: float = 0.0, guidance: str = "") -> str:
    sparse = len(transcript.split()) < 8
    body = (_timestamped(words) if words else transcript)[:1800]
    dur_note = (f"Clip length: {clip_dur:.1f}s. The transcript below is "
                f"time-stamped [start-end] in seconds — use it to choose "
                f"edit.cut.\n" if words and clip_dur else "")
    # Channel-learned steer (retention feedback): only present when our own
    # analytics say openings are bleeding viewers. Shapes edit.cut + hook.
    guide_note = (f"CHANNEL FEEDBACK (obey for edit.cut and hook): {guidance}\n"
                  if guidance else "")
    return (f"Streamer: {streamer}\n"
            f"Original clip title: {clip_title!r}\n"
            f"Twitch views in <24h: {views}\n"
            + dur_note
            + guide_note
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
    tags = [t for t in tags if 2 <= len(t) <= 30][:7]
    series = re.sub(r"[^a-z-]", "", str(out.get("series", "")).lower())
    if not title or len(title) > 100:
        return None
    # hard safety gate: a slur or demeaning insult-framing in the title/hook
    # is off-brand + gets demonetized/suppressed — reject regardless of what
    # was said, fall back to the streamer's own clip title.
    if title_is_unsafe(title) or title_is_unsafe(hook):
        print("::warning::[author] rejected — unsafe title/hook phrasing "
              f"({title!r}) — falling back to raw clip title", flush=True)
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
    caption = scrub_text(str(out.get("caption", "")).strip()[:180])
    # Comment-bait CTA (feed-engagement lever): a take-provoking question,
    # scrubbed and length-capped. Empty when the model omits it — the
    # description simply carries no prompt then.
    cta = scrub_text(str(out.get("cta", "")).strip())[:90]

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
            "cta": cta, "hashtags": tags, "series": series or "chaos",
            "edit": edit}


def _call_claude(user: str, system: str = SYSTEM,
                 read_files: bool = False) -> dict | None:
    """Headless Claude via the claude-code CLI (CLAUDE_CODE_OAUTH_TOKEN —
    the same brain the daily channel uses). Returns parsed JSON or None.

    `read_files=True` grants the Read tool (`--allowedTools Read`) so the
    prompt can inspect a local image (the contact sheet) — without it the
    CLI's default permissions may refuse the read and the model answers
    BLIND. Vision callers MUST pass read_files=True (a text-only model like
    the Groq fallback can never see frames — that's why scene analysis
    records vision provenance and refuses to trust visual_beats from a
    model that didn't actually look)."""
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
    cmd = ["claude", "-p", prompt]
    if read_files:
        cmd += ["--allowedTools", "Read"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
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

_RANK_SYSTEM = """You are the greenlight curator for a Twitch/Kick clip
channel with a mass general audience (a 16-year-old scrolling Shorts). You are
given candidate clips (streamer, title, Twitch views, velocity). Score each on
how likely a STRANGER — who does not know the streamer, the game, or the inside
joke — would WATCH TO THE END and SHARE it as a vertical Short.

THE ONE-SENTENCE TEST. A clip earns a high score only if you can state it as
"[Person] tries/does [clear action], but [surprising consequence]." If the best
you can say is "streamer reacts / talks to chat / funny moment / he loses it /
you had to be there", it does NOT promise a payoff — score it LOW.

This niche is REALITY TV: the clips that reach MILLIONS are human DRAMA —
someone caught / exposed / embarrassed / humbled / proven wrong; two people
disagreeing, roasting, betraying, or choosing sides; visible fear / shock /
anger / crying / laughter; a challenge or bet with a visible win or failure; a
wholesome moment that feels real; or a live event people are searching NOW.
Gameplay mechanics and inside-baseball rarely travel.

Score 0.0-1.0, anchored to a greenlight rubric (clarity, universal stakes,
real emotion, a clear payoff, freshness, search/fan pull, commentability):
- HIGH (0.8-1.0): passes the one-sentence test with strong universal stakes a
  stranger gets in one second — conflict/beef, a betrayal, someone crying or
  losing it, getting caught/kicked/exposed, a shocking reveal or reversal, a
  visible win/fail. Bonus for a live storyline/event people already follow, or
  a name people search.
- MEDIUM (0.4-0.6): watchable but generic, OR the title is vague/garbage so you
  genuinely can't tell (unknown = 0.5, NEVER 0 — a bad title often hides a
  great clip; don't punish it, just don't boost it).
- LOW (0.0-0.3): fails the one-sentence test or hits an AUTOMATIC-REJECT — a
  ROUTINE giveaway/drops/subathon/gifted-sub ALERT with no real reaction,
  sponsor/ad read, menu/setup/technical talk, routine gameplay, ordinary
  conversation with no change, or insider content a stranger can't follow.
  Also LOW if the title has to exaggerate or invent an event to sound
  interesting. (A gifted-sub moment is NOT auto-low when the person's genuine
  reaction, the amount, or the surrounding event makes it an emotionally
  complete, searchable moment — our own data shows those retain.)

Some candidates carry a transcript snippet (snip=...) — actual words said in
the clip. When present, judge from the SNIP over the title: titles lie, the
transcript doesn't. A snip revealing routine/no-change talk overrides an
exciting title; a snip revealing real conflict/emotion rescues a vague title.

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
        line = (f"{i}. streamer={c.get('channel','?')} "
                f"views={c.get('views',0)} vph={c.get('vph',0):.0f} "
                f"title={str(c.get('title',''))[:90]!r}")
        if c.get("snip"):
            line += f" snip={str(c['snip'])[:160]!r}"
        lines.append(line)
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


# ---------------------------------------------- story "showrunner" brain
# Turns a CLUSTER of clips about the same people/event into an ordered
# narrative arc (beginning -> middle -> end). This is what powers the
# multi-clip "story" compilation — the reality-TV recap format that travels
# far better than a single decontextualized moment.

_STORY_SYSTEM = """You are the SHOWRUNNER for a Twitch/Kick clip channel. You
are given a set of candidate clips that MAY be about the same people or the
same unfolding event (a beef, a challenge, a friendship arc, an event
storyline like Streamer University). Your job: decide whether they form a real
STORY a stranger would watch beginning-to-end, and if so, order them into a
narrative arc.

A real story has a CHANGE across it — it starts one way and ends another:
- a beef that starts, escalates, and resolves (or explodes),
- a challenge/bet that is set up, attempted, and won or lost,
- a friendship/rivalry that shifts,
- an event storyline that builds to a payoff.

A pile of unrelated clips of the same streamer is NOT a story. Neither is the
same moment clipped twice. If there is no genuine beginning-to-end arc across
DISTINCT moments, say so honestly.

You will get numbered candidates, each with: streamer, date, title, and a
short transcript snippet. Return ONLY JSON:
{"is_story": true|false,
 "title": "<the story as one tappable line, name-first, present tense, honest>",
 "hook": "<4-8 word ALL-CAPS hook for the first card>",
 "why": "<=8 words: the arc in a phrase>",
 "beats": [{"i": <candidate index int>, "role": "setup|escalation|climax|resolution",
            "card": "<=4 word chapter card shown before this beat>"}]}

Rules:
- Order beats to TELL THE STORY (chronological / causal), not by views.
- Use 2-5 beats. Each beat = a DISTINCT moment (never the same clip twice).
- card: a tiny chapter title a viewer reads in half a second — "IT STARTS",
  "IT GETS WORSE", "TWO DAYS LATER", "THEY MAKE UP". No period.
- title: name the people; tease the arc; ONE honest curiosity gap. Never
  invent an event the clips don't support.
- is_story=false (and beats=[]) when the candidates don't form a real arc —
  an empty slot beats a fake story. Be strict: most piles are NOT stories."""


def order_story(clips: list[dict]) -> dict | None:
    """Showrunner over a candidate cluster -> ordered narrative arc, or None.

    `clips`: list of dicts with keys streamer/channel, date, title, and
    optional transcript snippet ('snip'). Returns
    {is_story, title, hook, why, beats:[{clip, role, card}]} where each beat's
    `clip` is the ORIGINAL clip dict (in narrative order), or None when no
    brain is reachable / parse fails / it's judged not-a-story. Never raises.
    """
    if len(clips) < 2:
        return None
    lines = []
    for i, c in enumerate(clips):
        lines.append(
            f"{i}. streamer={c.get('channel') or c.get('streamer','?')} "
            f"date={c.get('date') or c.get('ts','?')} "
            f"title={str(c.get('title',''))[:90]!r} "
            f"snip={str(c.get('snip',''))[:140]!r}")
    user = "Candidate clips:\n" + "\n".join(lines)
    out = None
    try:
        out = _call_claude(user, system=_STORY_SYSTEM)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[story] claude failed ({e}) — groq", flush=True)
    if out is None:
        try:
            out = _call_groq(user, system=_STORY_SYSTEM)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[story] groq failed ({e})", flush=True)
    if not out or not out.get("is_story"):
        return None
    beats = []
    seen = set()
    for b in (out.get("beats") or []):
        try:
            i = int(b["i"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (0 <= i < len(clips)) or i in seen:
            continue          # in-range, and never the same clip twice
        seen.add(i)
        beats.append({"clip": clips[i],
                      "role": str(b.get("role", ""))[:20],
                      "card": scrub_text(str(b.get("card", ""))[:32]).upper()})
    if len(beats) < 2:
        return None           # a story needs at least two distinct beats
    # YouTube titles cap at 100 chars; a run-on showrunner title (live: 114
    # chars from the canary) gets clamped at a word boundary, not mid-word
    title = str(out.get("title", "")).strip()
    if len(title) > 95:
        title = title[:95].rsplit(" ", 1)[0]
    return {"is_story": True,
            "title": safe_title(title,
                                beats[0]["clip"].get("channel", "")),
            "hook": scrub_text(str(out.get("hook", ""))[:60]).upper(),
            "why": str(out.get("why", ""))[:60],
            "beats": beats[:5]}


def author_package(streamer: str, clip_title: str, transcript: str,
                   views: int, words: list[dict] | None = None,
                   clip_dur: float = 0.0, guidance: str = "") -> dict | None:
    """Claude-first (the brain), Groq fallback (LOUD, per repo doctrine),
    None (raw clip title) last. Authoring never blocks a post. `words`
    (timestamped) + `clip_dur` let the director choose the narrative cut;
    `guidance` is the channel's own retention feedback (empty until data)."""
    user = _build_user_prompt(streamer, clip_title, transcript, views,
                              words=words, clip_dur=clip_dur, guidance=guidance)
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
