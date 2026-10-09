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

# Same pin as `shared.script_generator.DEFAULT_GROQ_MODEL` (held equal by
# `tests/test_the_groq_model_is_alive.py`): Groq retired llama-3.3-70b on
# 2026-08-16 and this file 404'd on every clip title for five weeks.
MODEL = "openai/gpt-oss-120b"

# The exact enum the SYSTEM prompt hands the model (see "series:" rule
# below). Anything the model returns outside this set — empty, cut off by
# the [^a-z-] strip, or a value it invented — is an author that DIDN'T
# classify the clip, not a confirmed "chaos" one. Collapsing both into
# "chaos" silently inflated that bucket and made it look like the
# channel's weakest-performing series was also its most-produced one
# (doctor finding 2127c6395c2c) when part of that bucket was really
# "unlabeled". Content-mix decisions must read "unknown" as its own
# bucket, never folded into "chaos".
_VALID_SERIES = {
    "drama", "beef", "rage", "chat-betrayal", "jumpscare", "clutch",
    "fail", "win", "wholesome", "argument", "chaos",
}

SYSTEM = """You package Twitch/Kick clips as YouTube Shorts for a clip channel.
You are given the streamer name, the clip's original title, its view count on
Twitch, and the transcript of what is said in the clip.

Return STRICT JSON:
{"title": str, "hook": str, "caption": str, "cta": str, "hashtags": [str, ...],
 "series": str,
 "edit": {"mood": str, "mood_at": number,
          "moves": [{"move": str, "at": number}, ...],
          "line2": {"text": str, "at": number},
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
- hook: the ONE line of text on screen for the whole video, written the
  way the big Twitch repost channels write it: sentence case (never ALL
  CAPS), plain words, 3-9 words, saying the SITUATION a stranger needs to
  get the clip ("Los thought he ended stream", "Kai's mom walks in on
  stream", "Jynxzi finally hits champ"), never the punchline. It may end
  with ONE or TWO emoji when the moment earns them, the way those channels
  use them: 😭 funny or painful, 🥀 sad or a loss, 💀 a fail, 😂 a joke
  landing, 😳 awkward. Most lines take one or none. Honest only.
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
  - mood: the music and colour from one moment to the END, at most
    one, the way repost channels edit it:
    "sad" ONLY on a genuinely sad turn (a loss, someone crying, a goodbye,
    bad news, a friend falling out): the picture goes grey and a sad
    piano comes in. Never for a joke or a rage moment.
    "hype" on a W: a win, a clutch, a big reveal going right, a crowd or
    chat going off: the colour pops and a hard 808 beat comes in.
    Otherwise "" (most clips).
  - mood_at: the second (clip time, from the transcript timestamps) that
    turn lands; 0 if it holds from the start.
  - moves: the HITS a repost editor puts on single moments, 0-3 of them,
    at least 2s apart, each on the exact second from the transcript:
    "zoom": a hard punch-in with a bass boom on THE reaction or the
    punchline (the stunned face, the "BRO", the line that lands);
    "shake": the frame shakes, with the boom, on a scream, a jump scare,
    a slam, someone losing it;
    "awkward": a slow push-in with crickets on a cringe silence or a
    dead joke. Use one only where an editor obviously would; a clip with
    no such moment gets []. Never on the first second.
  - line2: when the clip TURNS (the reveal, the moment it goes wrong),
    the line of text may change to a second line at that second, same
    rules as hook ("Then chat noticed 💀", "He was not ready 😭"). Most
    clips keep one line: {"text": "", "at": 0}.
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


# Streamer clip titles are written by clippers for an audience that already
# has the context, so they collapse to pure hype ("WWWW", "w max", "wowza")
# or a bare noun ("SUBURB", "Yak"). safe_title lets those through — they are
# SAFE, just worthless — and on 2026-07-29 four of them shipped as the public
# YouTube titles. These two sets are the vocabulary of that noise.
_HYPE = {
    "w", "ww", "www", "wwww", "wwwww", "l", "ll", "lll", "lol", "lmao",
    "lmfao", "omg", "omfg", "wow", "wowza", "yo", "yoo", "yooo", "bruh",
    "bro", "ahh", "ah", "aha", "ayo", "ayoo", "ez", "gg", "ggs", "pog",
    "poggers", "sheesh", "damn", "wtf", "wth", "huh", "clip",
    "clips", "stream", "streaming", "live", "vod", "moment", "moments",
    "funny", "insane", "crazy", "nah", "fr", "ong", "sus", "goat", "peak",
    "v", "vv", "real", "actually", "literally", "bruv", "man", "dude",
}
_FILLER = {
    "the", "a", "an", "and", "but", "so", "then", "like", "just", "okay",
    "ok", "uh", "um", "er", "yeah", "yea", "nah", "i", "im", "its", "it",
    "is", "was", "you", "your", "he", "she", "they", "we", "me", "my",
    "of", "to", "in", "on", "at", "for", "with", "that", "this", "know",
}


def _words_of(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z']*", text or "")


def title_is_low_signal(raw: str) -> bool:
    """True when a title carries no information a cold viewer could act on.

    Deliberately conservative — it only fires when almost nothing survives
    stripping hype. "jasons camera ,an gets pass code to his room" is ugly
    but INFORMATIVE and passes; "w max" and "ron shaking ahh" do not."""
    words = _words_of(raw)
    meaty = [w for w in words if w.lower() not in _HYPE]
    if len(meaty) < 3:
        return True
    # 3+ words but still tiny ("Is he back?") reads as a tease with no subject
    return len(" ".join(meaty)) < 14


_SMALL = {"a", "an", "the", "and", "but", "or", "of", "to", "in", "on",
          "at", "for", "with", "is", "it", "that", "this", "his", "her"}


def _titlecase(text: str) -> str:
    """Channel voice: Title Case with small words lowered, first word always
    capitalised — matches the authored titles ('Kai Cenat Gives Out The
    First Streamer University Diploma') so the fallback isn't visibly a
    downgrade in the feed."""
    out = []
    for i, w in enumerate(text.split()):
        lw = w.lower()
        out.append(lw if i and lw in _SMALL else lw.capitalize())
    return " ".join(out)


# Tried and rejected: quoting the first N words of the transcript. It reads
# well on invented examples and falls apart on real ones — the opening of a
# clip is throat-clearing, not the payoff. On the three 07-29 clips it gave
# "How Did They Know Isn't that Crazy Like They", "Oh My God Aloki Aloki Got
# Some Dude Damn" and "Right Ladies and Gentlemen Hey Ej Swerver Thanks":
# 3/3 incoherent, and worse than the hype they replaced. Picking the
# INTERESTING span out of a transcript is the author brain's job, not a
# heuristic's. So the floor makes no specific claim at all — it varies the
# wording only so a multi-clip day doesn't ship the same line repeatedly.
_NEUTRAL = (
    "{s} Has The Whole Stream Reacting",
    "The {s} Clip Everyone's Talking About",
    "{s} Did Not See That Coming",
    "Chat Could Not Handle This {s} Moment",
    "{s} Caught It All On Stream",
)


def _neutral_title(pretty: str, seed: str) -> str:
    """A safe channel-voice line, varied deterministically by `seed` so the
    same clip always gets the same title but a day's batch doesn't repeat."""
    if not pretty:
        return "The Clip Everyone's Talking About"
    import hashlib
    # hashlib, not hash() — the builtin is salted per process, so the same
    # clip would drift between a dry run and the apply run.
    i = int(hashlib.sha1(seed.encode("utf-8", "replace")).hexdigest()[:8], 16)
    return _NEUTRAL[i % len(_NEUTRAL)].format(s=pretty)


def fallback_title(streamer: str, raw: str, transcript: str = "") -> str:
    """The public title when authoring produced nothing: a safe and
    INFORMATIVE raw clip title if there is one, else a neutral channel-voice
    line. Never returns raw hype noise, and never invents a specific claim.

    `transcript` is accepted but only seeds the neutral variant — see the
    note above _NEUTRAL for why quoting it directly was removed. Authoring
    is best-effort by design (it must never block a post), so this is the
    floor that makes that tradeoff survivable."""
    safe = safe_title(raw, streamer)
    if not title_is_low_signal(safe):
        return safe[:100]
    pretty = (streamer or "").strip("_").title()
    neutral = _neutral_title(pretty, f"{streamer}|{raw}")
    print(f"::warning::[author] low-signal raw title {raw!r} -> neutral "
          f"title {neutral!r} (authoring produced nothing)", flush=True)
    return neutral[:100]


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
                       clip_dur: float = 0.0, guidance: str = "",
                       search: str = "") -> str:
    sparse = len(transcript.split()) < 8
    body = (_timestamped(words) if words else transcript)[:1800]
    dur_note = (f"Clip length: {clip_dur:.1f}s. The transcript below is "
                f"time-stamped [start-end] in seconds — use it to choose "
                f"edit.cut.\n" if words and clip_dur else "")
    # Channel-learned steer (retention feedback): only present when our own
    # analytics say openings are bleeding viewers. Shapes edit.cut + hook.
    guide_note = (f"CHANNEL FEEDBACK (obey for edit.cut and hook): {guidance}\n"
                  if guidance else "")
    # How viewers actually FIND this channel, from its own analytics. Its own
    # section because it governs different fields (title + hashtags) than
    # the retention steer above, and carries its own honesty rule.
    search_note = (f"SEARCH DEMAND (use for title + hashtags): {search}\n"
                   if search else "")
    return (f"Streamer: {streamer}\n"
            f"Original clip title: {clip_title!r}\n"
            f"Twitch views in <24h: {views}\n"
            + dur_note
            + guide_note
            + search_note
            + ("NOTE: the clip has almost no dialogue (screaming/"
               "crowd moment) — build the title from the original "
               "clip title and the streamer, do NOT guess events.\n"
               if sparse else "")
            + f"Transcript (whisper, may have small errors):\n{body}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def anchor_streamer(title: str, streamer: str) -> str:
    """Make sure the title NAMES the streamer — the channel is ~89% YouTube
    search, and a title without the name people type is invisible to it.

    Anchors the right streamer WITHOUT double-naming: a near-miss spelling
    ('stablernaldo') is corrected in place, not prefixed; a title that never
    says the name gets "Name: " in front. Lifted verbatim out of
    `_postprocess` so the story arm can use the same rule instead of
    shipping nameless titles (all four stories through 2026-10-01 did)."""
    import difflib
    if not streamer:
        return title
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
    return title


def _postprocess(out: dict, streamer: str, context: str,
                 clip_dur: float = 0.0) -> dict | None:
    title = str(out.get("title", "")).strip()
    hook = " ".join(str(out.get("hook", "")).split())
    if hook.isupper():
        # the line is sentence case (operator, 2026-10-08/09); a model
        # that still shouts gets lowered, first letter kept up
        hook = hook[:1] + hook[1:].lower()
    tags = [re.sub(r"[^a-z0-9]", "", str(t).lower())
            for t in out.get("hashtags", [])]
    tags = [t for t in tags if 2 <= len(t) <= 30][:7]
    series = re.sub(r"[^a-z-]", "", str(out.get("series", "")).lower())
    if series not in _VALID_SERIES:
        series = "unknown"
    if not title or len(title) > 100:
        print(f"::warning::[author] rejected — title missing or >100 chars "
              f"({title[:60]!r})", flush=True)
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
    title = anchor_streamer(title, streamer)
    caption = scrub_text(str(out.get("caption", "")).strip()[:180])
    # Comment-bait CTA (feed-engagement lever): a take-provoking question,
    # scrubbed and length-capped. Empty when the model omits it — the
    # description simply carries no prompt then.
    cta = scrub_text(str(out.get("cta", "")).strip())[:90]

    # Edit direction (validated hard — the renderer must never trust raw
    # model output). The slam word, sticker emoji and replay were retired
    # 2026-10-09; what the author directs now is the cut and the mood.
    edit_raw = out.get("edit") or {}
    mood = str(edit_raw.get("mood", "")).strip().lower()
    try:
        mood_at = max(0.0, float(edit_raw.get("mood_at") or 0.0))
    except (TypeError, ValueError):
        mood_at = 0.0
    if clip_dur:
        mood_at = min(mood_at, clip_dur)
    edit = {"mood": mood if mood in ("sad", "hype") else "",
            "mood_at": round(mood_at, 2),
            "complete": bool(edit_raw.get("complete", True))}
    # the hits and the second line (third_capture/moves.py validates the
    # vocabulary, spacing and seconds again against the cut)
    _moves = []
    for m in (edit_raw.get("moves") or [])[:6]:
        if not isinstance(m, dict):
            continue
        name = str(m.get("move", "")).strip().lower()
        try:
            at = max(0.0, float(m.get("at") or 0.0))
        except (TypeError, ValueError):
            continue
        if name in ("zoom", "shake", "awkward"):
            _moves.append({"move": name,
                           "at": round(min(at, clip_dur) if clip_dur
                                       else at, 2)})
    if _moves:
        edit["moves"] = _moves
    l2 = edit_raw.get("line2") if isinstance(edit_raw.get("line2"),
                                             dict) else {}
    l2_text = scrub_text(str(l2.get("text", "")).strip())[:80]
    if l2_text:
        if l2_text.isupper() and any(c.isalpha() for c in l2_text):
            l2_text = l2_text[0] + l2_text[1:].lower()
        try:
            l2_at = max(0.0, float(l2.get("at") or 0.0))
        except (TypeError, ValueError):
            l2_at = 0.0
        if l2_at > 0:
            edit["line2"] = {"text": l2_text, "at": round(l2_at, 2)}

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

    return {"title": title[:95], "hook": hook[:80], "caption": caption,
            "cta": cta, "hashtags": tags, "series": series,
            "edit": edit}


# ------------------------------------------------------- brain health
# 2026-07-29: every rank/author/scene call failed for ~90 minutes (Claude
# CLI rc=1, Groq 429) and the run STILL published — four clips picked by
# raw view count (every banger pinned at the 0.5 default, empty reasons),
# no scene analysis, fallback titles. The per-call fallbacks each degraded
# "gracefully", so nothing stopped the slate. This tracker gives the run a
# way to notice the pattern: record each brain-task outcome, and let the
# caller refuse to keep publishing once the brain is provably down.
_BRAIN = {"ok": 0, "fail": 0}


def _brain_note(ok: bool) -> None:
    _BRAIN["ok" if ok else "fail"] += 1


def brain_down(min_calls: int = 3) -> bool:
    """True once we have real evidence the brain is DOWN, not flaky: at
    least `min_calls` brain tasks attempted and every single one failed.
    One success anywhere resets nothing but proves the path works, so the
    all-failed condition can never trip after it."""
    total = _BRAIN["ok"] + _BRAIN["fail"]
    return total >= min_calls and _BRAIN["ok"] == 0


def brain_health() -> dict:
    h = dict(_BRAIN)
    # "0 ok / 25 failed" and "0 ok / 25 failed because the subscription
    # window was already spent" call for completely different responses.
    # The judges digest reads this, so the distinction has to be IN it.
    if _LIMIT_HIT["at"]:
        h["limited_at"] = _LIMIT_HIT["at"]
        h["limit_detail"] = _LIMIT_HIT["detail"]
    return h


# ------------------------------------------------ usage-limit breaker
# 2026-07-29 read as a 90-minute outage; it was not. The cron fires at
# 11:10 UTC and the "outage" ran 11:10-12:41 — that WAS the run, first
# call to last, inside one exhausted subscription window. A run makes
# ~40 `claude -p` calls, immediately after daily.yml has already spent
# that window on a full agentic session.
#
# Once the account is out of budget, every remaining call is guaranteed
# to fail. Making them anyway costs real time and stampedes ~40 requests
# onto free-tier Groq in a few minutes — which is why "Groq 429s at the
# same time" always looked like a coincidence and never was. Groq was
# being killed BY the Claude failure, not alongside it.
_LIMIT_HIT: dict = {"at": "", "detail": ""}
_LIMIT_PAT = re.compile(
    r"usage limit|rate.?limit|quota|too many requests|resets? (at|in)|"
    # 2026-09-27/29: the CLI said "You've hit your weekly limit · resets
    # Sep 30, 12am (UTC)" and NONE of the above matched it, so the breaker
    # never armed and every call in the run re-hit the wall.
    r"(weekly|session|daily|monthly|hourly) limit|hit your \w* ?limit|"
    r"429|overloaded", re.I)


def brain_limited() -> dict:
    """Non-empty once the CLI has reported a usage/rate limit this run."""
    return dict(_LIMIT_HIT)


def _note_limit(detail: str) -> None:
    if not _LIMIT_HIT["at"]:
        from datetime import datetime, timezone
        _LIMIT_HIT.update(at=datetime.now(timezone.utc).isoformat(
            timespec="seconds"), detail=detail[:200])
        print(f"::warning::[brain] USAGE LIMIT reached — {detail[:160]}. "
              f"Skipping further Claude calls this run instead of retrying "
              f"into the wall (and stampeding Groq).", flush=True)


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
    if _LIMIT_HIT["at"]:
        # already out of budget this run — a further call cannot succeed,
        # and each one costs wall-clock and pushes another request onto
        # the Groq fallback that is about to 429 because of us
        return None
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        print("::warning::[author] CLAUDE_CODE_OAUTH_TOKEN unset — the brain "
              "is unavailable, falling to Groq", flush=True)
        return None
    if not shutil.which("claude"):
        print("::warning::[author] claude CLI not installed — "
              "falling to Groq", flush=True)
        return None
    prompt = (system + "\n\n" + user
              + "\n\nReturn ONLY the JSON object, nothing else.")
    # PIN THE MODEL. Every other brain path in the repo pins one
    # (story_forge, mascot_director and daily.yml all pin sonnet;
    # showrunner pins opus) — this call site pinned NOTHING and inherited
    # the account default. ~40 unpinned calls per run is how a window gets
    # spent without anyone choosing to spend it.
    cmd = ["claude", "-p", prompt,
           "--model", os.environ.get("THIRD_BRAIN_MODEL", "sonnet")]
    if read_files:
        cmd += ["--allowedTools", "Read"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if r.returncode != 0 and _LIMIT_PAT.search((r.stderr or "")
                                               + (r.stdout or "")):
        _note_limit((r.stderr or r.stdout or "").strip().replace("\n", " "))
        return None
    if r.returncode != 0:
        # A FAILED PROCESS IS NOT AN ANSWER. This used to fall through to
        # the JSON parse below, so a CLI that died mid-reply — after
        # emitting a complete or embedded JSON object — handed back partial
        # or stale output as a successful brain verdict, and the callers'
        # health accounting recorded an `ok` for a call that failed. Require
        # rc=0 before trusting a byte of stdout; everything nonzero that is
        # not the usage-limit breaker above raises with the CLI's own
        # message (bounded), which the callers already catch, count via
        # _brain_note(False), and fall back on.
        err = (r.stderr or "").strip().replace("\n", " ")[:300]
        head = (r.stdout or "").strip().replace("\n", " ")[:120]
        raise RuntimeError(
            f"claude exited rc={r.returncode}"
            + (f" stderr={err!r}" if err else "")
            + (f" stdout={head!r}" if head else " stdout=<empty>"))
    # Prefer a clean parse of the whole reply; the greedy r"\{.*\}" spans
    # from the FIRST brace to the LAST, so any prose containing braces (or
    # a fenced block plus trailing commentary) mis-spans and raises a
    # JSONDecodeError that the callers' bare excepts swallow as "brain
    # down". Try the honest parse first, keep the regex as the fallback.
    _txt = (r.stdout or "").strip()
    if _txt.startswith("{") and _txt.endswith("}"):
        try:
            return json.loads(_txt)
        except ValueError:
            pass
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        # SURFACE THE CLI'S OWN MESSAGE. capture_output=True collects
        # stderr and this raised on rc alone, so "rc=1" was the entire
        # diagnosis available while the brain was down for ~90 minutes on
        # 2026-07-29 and again mid-run on 07-30 — every rank, author and
        # scene call failing with no way to tell WHY (auth? usage limit?
        # prompt too long? a permission prompt?). Exactly the bug class
        # that hid the rumble 403 for days: the answer was captured, then
        # thrown away. This is the single highest-value line in the file.
        err = (r.stderr or "").strip().replace("\n", " ")[:300]
        head = (r.stdout or "").strip().replace("\n", " ")[:120]
        # A limit can also arrive as rc=0 with a prose apology and no JSON,
        # so the breaker has to be armed here too — not only on rc!=0.
        if _LIMIT_PAT.search(err + " " + head):
            _note_limit(err or head)
            return None
        raise RuntimeError(
            f"no JSON in claude output (rc={r.returncode})"
            + (f" stderr={err!r}" if err else "")
            + (f" stdout={head!r}" if head else " stdout=<empty>"))
    return json.loads(m.group(0))


# ------------------------------------------------ the fallback judges
# 2026-09-27 and 09-29 posted ZERO: Claude was at its weekly limit, the
# Groq fallback answered 413 (Payload Too Large — the director's scene
# reports ran past Groq's per-request token ceiling) and then 429, and the
# third channel had no third rung at all while GEMINI_API_KEY sat unused.
# The chain is now Claude -> Groq -> Gemini, and Gemini is the one fallback
# that can SEE: it takes the contact sheet as inline image data, so a
# vision verdict survives the CLI being out.

# Groq's free tier counts prompt + max_tokens against a per-minute token
# ceiling (8k on gpt-oss-120b) and refuses an over-size request outright
# with 413 — it does not truncate for you. ~12k characters of system+user
# is ~3.4k tokens, which leaves room for the 4k reply budget.
GROQ_PROMPT_CHARS = int(os.environ.get("THIRD_GROQ_PROMPT_CHARS", "12000"))
_GROQ_TAIL_CHARS = 300
_GROQ_TRUNC_NOTE = "\n[... truncated to fit the model's size limit ...]\n"
# a Groq 429 is a per-MINUTE limit: stop asking for a minute instead of
# spending every remaining clip's call on the same refusal
_GROQ_COOLDOWN_S = 60.0
_GROQ_REST: dict = {"until": 0.0}


def _groq_bounded(user: str, system: str = SYSTEM) -> str:
    """`user`, cut down so system+user fits GROQ_PROMPT_CHARS. Keeps the
    head (the task and the first candidates / reports) and the last
    _GROQ_TAIL_CHARS (where prompts put their closing instruction), and
    says in the prompt that it was cut."""
    budget = max(1500, GROQ_PROMPT_CHARS - len(system or ""))
    if len(user) <= budget:
        return user
    head = budget - _GROQ_TAIL_CHARS - len(_GROQ_TRUNC_NOTE)
    return user[:head] + _GROQ_TRUNC_NOTE + user[-_GROQ_TAIL_CHARS:]


def _groq_would_truncate(user: str, system: str = SYSTEM) -> bool:
    return _groq_bounded(user, system) != user


def _call_groq(user: str, system: str = SYSTEM) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    import time
    if time.time() < _GROQ_REST["until"]:
        return None
    import requests
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": system},
                           {"role": "user",
                            "content": _groq_bounded(user, system)}],
              "temperature": 0.5,
              "max_tokens": 4000,
              "reasoning_effort": "low",
              "response_format": {"type": "json_object"}},
        timeout=45)
    if resp.status_code == 429:
        _GROQ_REST["until"] = time.time() + _GROQ_COOLDOWN_S
        print(f"::warning::[groq] 429 — resting Groq for "
              f"{_GROQ_COOLDOWN_S:.0f}s (Gemini answers meanwhile)",
              flush=True)
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


GEMINI_MODEL = os.environ.get("THIRD_GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent")
# Same breaker shape as Claude's _LIMIT_HIT: once Gemini says 429 (free
# tier RPM / RPD), every further call this run is a guaranteed refusal —
# stop asking rather than stampede it.
_GEMINI_LIMIT: dict = {"at": "", "detail": ""}


def gemini_limited() -> dict:
    return dict(_GEMINI_LIMIT)


def _json_from_text(txt: str) -> dict:
    txt = (txt or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", txt)
    try:
        out = json.loads(txt)
    except ValueError:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if not m:
            raise
        out = json.loads(m.group(0))
    if not isinstance(out, dict):
        raise ValueError("model reply is JSON but not an object")
    return out


def _call_gemini(user: str, system: str = SYSTEM,
                 image_path: str | None = None) -> dict | None:
    """Gemini (GEMINI_API_KEY, gemini-2.5-flash) with a JSON response.
    `image_path` attaches a local JPEG as inline base64 image data, so the
    model actually SEES the contact sheet — the only non-Claude judge here
    that can. None when there is no key, the image cannot be read, or the
    breaker is armed; raises on any other failure (callers count it)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or _GEMINI_LIMIT["at"]:
        return None
    parts: list = []
    if image_path:
        import base64
        try:
            with open(image_path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode("ascii")
        except OSError as e:
            print(f"::warning::[gemini] cannot read image {image_path} "
                  f"({e}) — no vision call", flush=True)
            return None
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": data}})
    parts.append({"text": user + "\n\nReturn ONLY the JSON object."})
    import requests
    resp = requests.post(
        GEMINI_API.format(model=GEMINI_MODEL),
        params={"key": key},
        headers={"content-type": "application/json"},
        json={"system_instruction": {"parts": [{"text": system}]},
              "contents": [{"role": "user", "parts": parts}],
              "generationConfig": {"temperature": 0.5,
                                   "maxOutputTokens": 8192,
                                   "responseMimeType": "application/json"}},
        timeout=120)
    if resp.status_code == 429:
        from datetime import datetime, timezone
        _GEMINI_LIMIT.update(
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            detail=str(getattr(resp, "text", ""))[:200])
        print("::warning::[gemini] 429 — no more Gemini calls this run",
              flush=True)
        return None
    resp.raise_for_status()
    body = resp.json()
    cands = body.get("candidates") or []
    if not cands:
        raise RuntimeError(f"gemini returned no candidates: "
                           f"{str(body.get('promptFeedback', ''))[:160]}")
    txt = "".join(p.get("text", "") for p in
                  ((cands[0].get("content") or {}).get("parts") or [])
                  if isinstance(p, dict))
    if not txt.strip():
        raise RuntimeError(f"gemini returned no text (finishReason="
                           f"{cands[0].get('finishReason')})")
    return _json_from_text(txt)


# Which text fallback answered the last _call_text_fallback() — logs name
# the provider, so a Gemini-authored title never reads as Groq's.
_LAST_FALLBACK: dict = {"provider": ""}


def _call_text_fallback(user: str, system: str = SYSTEM,
                        tag: str = "brain") -> dict | None:
    """The text-only fallback chain after Claude: Groq, then Gemini.
    Never raises. One exception to the order: when the prompt is too big
    for Groq (it would have to be truncated) and Gemini is available,
    Gemini goes first, so the long prompt is read WHOLE and Groq's cut-down
    copy is the last resort rather than the default."""
    _LAST_FALLBACK["provider"] = ""
    order = [("groq", _call_groq), ("gemini", _call_gemini)]
    if (_groq_would_truncate(user, system)
            and os.environ.get("GEMINI_API_KEY", "").strip()
            and not _GEMINI_LIMIT["at"]):
        order.reverse()
    for name, fn in order:
        try:
            out = fn(user, system=system)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[{tag}] {name} failed ({e})", flush=True)
            continue
        if out:
            _LAST_FALLBACK["provider"] = name
            return out
    return None


def _call_gemini_vision(user: str, system: str, image_path: str,
                        tag: str = "brain") -> dict | None:
    """Gemini WITH the image, never raising. None = no vision verdict."""
    if not image_path or not os.path.isfile(str(image_path)):
        return None
    try:
        return _call_gemini(user, system=system, image_path=str(image_path))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[{tag}] gemini vision failed ({e})", flush=True)
        return None


# ---------------------------------------------- clip selection ("banger") brain

_RANK_SYSTEM = """You are the greenlight curator for a Twitch/Kick clip
channel with a mass general audience (a 16-year-old scrolling Shorts). You are
given candidate clips (streamer, title, Twitch views, velocity). Score each on
how likely a STRANGER — who does not know the streamer, the game, or the inside
joke — would WATCH TO THE END and SHARE it as a vertical Short.

THE ONE-SENTENCE TEST — this is the bar for the TOP band, not for passing.
A clip reaches HIGH only if you can state it as "[Person] tries/does [clear
action], but [surprising consequence]."

Failing that test does NOT make a clip LOW. It only means the clip is not a
HIGH. Ask the second question before you score:

  DOES SOMETHING OBSERVABLE HAPPEN?

If yes — a real laugh or flinch, a hit or a miss, someone walking in, an object
breaking, a stunt landing or failing, a crowd reacting to something you
can SEE — that is a GOOD clip (0.6-0.8) even though you cannot phrase it as
action-plus-consequence. Score it there.

Only score LOW when nothing observable happens at all: talking with no
event, a monologue, menu/setup/sponsor talk, routine gameplay narration.
"Streamer reacts" is LOW only when you cannot tell WHAT they are reacting
to; a visible reaction to a visible thing is a GOOD clip, and it is most of
what this channel posts.

This niche is REALITY TV: the clips that reach MILLIONS are human DRAMA —
someone caught / exposed / embarrassed / humbled / proven wrong; two people
disagreeing, roasting, betraying, or choosing sides; visible fear / shock /
anger / crying / laughter; a challenge or bet with a visible win or failure; a
wholesome moment that feels real; or a live event people are searching NOW.
Gameplay mechanics and inside-baseball rarely travel.

Score 0.0-1.0, anchored to a greenlight rubric (clarity, universal stakes,
real emotion, a clear payoff, freshness, search/fan pull, commentability).
THE BANDS BELOW ARE CONTIGUOUS AND COVER 0.0-1.0 WITH NO GAPS — keep them
that way. A gap is not cosmetic: the gate's threshold sat in one (0.6-0.8
was unanchored, the bar was 0.70) and the channel published almost nothing
for days while every check stayed green.
- HIGH (0.8-1.0): passes the one-sentence test with strong universal stakes a
  stranger gets in one second — conflict/beef, a betrayal, someone crying or
  losing it, getting caught/kicked/exposed, a shocking reveal or reversal, a
  visible win/fail. Bonus for a live storyline/event people already follow, or
  a name people search.
- GOOD (0.6-0.8): a REAL, COMPLETE MOMENT that a stranger can enjoy without
  knowing anyone — a genuine unscripted reaction (a real laugh, a flinch, a
  jump scare landing), a visible fail or win, physical comedy, a stunt or
  attempt that visibly succeeds or fails, an unexpected interruption, a
  spontaneous crowd/chat reaction to something you can SEE. It does NOT need
  beef, betrayal or tears to sit here. Most of what a clips channel should
  post lives in this band — USE IT. Do not force a clip down to MEDIUM just
  because it isn't a saga: this scale previously had nothing between 0.6 and
  0.8, every real clip got squashed into MEDIUM, and the channel published
  almost nothing. If something genuinely happens on screen and you can see
  it happen, it belongs here or above.
- MEDIUM (0.35-0.6): watchable but generic, OR the title is vague/garbage so you
  genuinely can't tell (unknown = 0.5, NEVER 0 — a bad title often hides a
  great clip; don't punish it, just don't boost it).
- LOW (0.0-0.35): fails the one-sentence test or hits an AUTOMATIC-REJECT — a
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


# The SAME greenlight rubric, but for a judge that can SEE the clip.
# 2026-07-31: the content gate rejected every candidate all day with
# reasons that were exclusively about talk — "rambling chat talk",
# "confused chat talk", "vague ramble", "routine gameplay narration".
# Not one mentioned anything visual, because the gate only ever received
# `words[:40]`. On a CLIPS channel that is a systematic bias against
# precisely the content that travels: a fail, a reaction face, physical
# comedy and a gameplay moment all read as "rambling chat" when you only
# read the words. This variant gets the frames.
_CONTENT_SYSTEM = _RANK_SYSTEM.replace(
    "Some candidates carry a transcript snippet",
    """You are given BOTH a contact sheet image (frames across the clip,
timestamp-labeled) and the transcript. READ THE IMAGE FIRST.

The words are only half the clip, and on this channel usually the lesser
half. A moment can be a complete story with mundane dialogue: someone's
face at the instant they realize, a physical fail, a reaction from the
people around them, something visibly going wrong on screen. Judge WHAT
HAPPENS, from the frames, and use the transcript to confirm or deny it.

- If the frames show a real visible event or a genuine emotional reaction,
  score it on THAT, even when the transcript is unremarkable chatter.
  Do NOT write it off as "rambling talk" — that is describing the audio of
  a visual moment.
- If the frames show a person sitting and talking with nothing changing,
  the low score is correct and the transcript will agree.
- If the frames contradict an exciting title, believe the frames.

Some candidates carry a transcript snippet""")


def judge_content(streamer: str, title: str, transcript: str,
                  sheet: str = "", views: int = 0) -> tuple:
    """Content greenlight for ONE clip, judged on what it SHOWS as well as
    what it says. Returns (score|None, why, saw_frames).

    `saw_frames` is provenance, not decoration: a text-only verdict here
    carries the exact bias this function exists to remove, so callers must
    be able to tell the two apart and say so in the record. score=None
    means no judge was reachable at all."""
    user = (f"Candidate clip:\n"
            f"0. streamer={streamer} views={views} title={str(title)[:90]!r}\n"
            + (f"Contact sheet image (12 timestamped frames): {sheet}\n"
               if sheet else "No frames available — transcript only.\n")
            + (f"TRANSCRIPT: {str(transcript)[:1200]!r}" if
               str(transcript).strip() else
               "TRANSCRIPT: (none — no intelligible speech in this clip). "
               "Judge it on the FRAMES. Silence is not a defect: a fail, a "
               "reaction, physical comedy and a clean gameplay moment all "
               "read as no-transcript. Do NOT penalise the missing words."))
    tried_claude = False

    def _first_score(out):
        for s in ((out or {}).get("scores") or []):
            # A MISSING `banger` KEY IS "NO SCORE", NOT 0.5.
            # The default used to be 0.5, which is under the 0.70
            # content floor — so a malformed reply REJECTED the
            # clip and wrote it to the PERMANENT blocklist with
            # `rejected_why: "0.50 < 0.7"`. A parse quirk became an
            # irreversible verdict on a clip nothing had evaluated.
            if not isinstance(s, dict) or s.get("banger") is None:
                continue
            try:
                return (max(0.0, min(1.0, float(s["banger"]))),
                        str(s.get("why", ""))[:40])
            except (TypeError, ValueError):
                continue
        return None

    if sheet:
        try:
            tried_claude = True
            try:
                got = _first_score(_call_claude(
                    user, system=_CONTENT_SYSTEM, read_files=True))
            except Exception as e:  # noqa: BLE001
                print(f"::warning::[content] claude vision failed ({e}) — "
                      f"gemini vision", flush=True)
                got = None
            if got is None:
                # Claude could not see it (limit, empty, or a reply in the
                # wrong shape). GEMINI SEES TOO: it gets the same contact
                # sheet as inline image data, so the verdict keeps its eyes
                # instead of dropping to the text-only rubric. One brain
                # task, one note: ok if either vision judge answered.
                got = _first_score(_call_gemini_vision(
                    user, _CONTENT_SYSTEM, sheet, tag="content"))
                if got is not None:
                    print(f"::warning::[content] GEMINI VISION judged "
                          f"(claude unavailable): {got[0]:.2f}", flush=True)
            if got is not None:
                _brain_note(True)
                return got[0], got[1], True
            # reached only if no vision judge produced a usable score — a
            # model answering in the wrong shape is a failed brain task,
            # not a silent no-op
            _brain_note(False)
        except Exception as e:  # noqa: BLE001
            # COUNT IT. A vision failure used to record nothing at all, so
            # a CLI failing 100% of eyes-on calls while Groq answered the
            # text fallback registered as a HEALTHY brain (brain_down()
            # needs ok == 0) and the blind-slate gate never fired. The
            # 2026-07-29 incident this tracker exists for would have been
            # partly invisible again: ok climbing while every visual
            # judgment silently degraded to the text-only rubric this
            # function was written to replace.
            _brain_note(False)
            print(f"::warning::[content] vision judge failed ({e}) — "
                  f"falling back to text-only", flush=True)
    # Text-only fallback: same rubric, no frames. Deliberately NOT a
    # failure — losing every clip when vision blinks would be worse than
    # the bias — but it is recorded as blind so a day judged entirely
    # without eyes is visible instead of looking authoritative.
    #
    # AMPLIFICATION: this used to call rank_clips(), which calls
    # _call_claude() again — so a vision call that failed because the
    # account was out of budget immediately fired a SECOND CLI call for
    # the same clip. Across a slate that doubles the request rate exactly
    # when the brain is already failing, and doubles the Groq stampede
    # behind it. When Claude has already been tried and refused for this
    # clip, go straight to the text fallback provider.
    b, why = None, ""
    if not str(transcript).strip():
        # NO TRANSCRIPT AND NO EYES. A text judge handed a silent clip
        # scores the title, which is the bias this function exists to
        # remove — and a manufactured mid-band score would blocklist the
        # clip permanently. score=None means "no judge was reachable",
        # the gate fails open, and the record says why.
        return None, "no transcript and no frames — nothing to judge", False
    text_user = ("Candidates:\n0. streamer=" + str(streamer)
                 + f" views={views} vph=0 title={str(title)[:90]!r}"
                 + f" snip={str(transcript)[:400]!r}")
    out = None
    if not tried_claude:
        try:
            out = _call_claude(text_user, system=_RANK_SYSTEM)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[content] claude text judge failed ({e})",
                  flush=True)
    if out is None:
        out = _call_text_fallback(text_user, system=_RANK_SYSTEM,
                                  tag="content")
    # same rule as the vision path: a reply with no `banger` is NO score,
    # never a manufactured 0.5 that blocklists a clip nothing evaluated
    got = _first_score(out)
    _brain_note(got is not None)
    if got is not None:
        b, why = got
    return b, why, False


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
        out = _call_text_fallback(user, system=_RANK_SYSTEM, tag="rank")
    _brain_note(bool(out))
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
        out = _call_text_fallback(user, system=_STORY_SYSTEM, tag="story")
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
                   clip_dur: float = 0.0, guidance: str = "",
                   search: str = "") -> dict | None:
    """Claude-first (the brain), Groq fallback (LOUD, per repo doctrine),
    None (raw clip title) last. Authoring never blocks a post. `words`
    (timestamped) + `clip_dur` let the director choose the narrative cut;
    `guidance` is the channel's own retention feedback (empty until data)."""
    user = _build_user_prompt(streamer, clip_title, transcript, views,
                              words=words, clip_dur=clip_dur, guidance=guidance,
                              search=search)
    context = f"{clip_title} {transcript}"
    try:
        out = _call_claude(user)
        if out is not None:
            meta = _postprocess(out, streamer, context, clip_dur=clip_dur)
            if meta:
                print(f"[author] Claude authored: {meta['title']!r}",
                      flush=True)
                _brain_note(True)
                return meta
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[author] Claude failed ({e}) — falling to Groq",
              flush=True)
    out = _call_text_fallback(user, tag="author")
    if out is not None:
        try:
            meta = _postprocess(out, streamer, context, clip_dur=clip_dur)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[author] fallback reply unusable: {e}",
                  flush=True)
            meta = None
        if meta:
            print(f"::warning::[author] "
                  f"{(_LAST_FALLBACK['provider'] or 'fallback').upper()} "
                  f"FALLBACK authored: {meta['title']!r}", flush=True)
            _brain_note(True)
            return meta
    # Both brains are down. This used to return silently and the raw clip
    # title shipped with nothing in the log to explain why — say it loudly,
    # because the public title is now a fallback, not an authored one.
    print("::warning::[author] AUTHORING FAILED (claude + groq + gemini) — the clip "
          "ships on a fallback title, not an authored one", flush=True)
    _brain_note(False)
    return None
