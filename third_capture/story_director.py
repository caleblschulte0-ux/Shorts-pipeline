#!/usr/bin/env python3
"""The story director — one brain controlling one timeline.

STORY_DIRECTOR_PLAYBOOK §8-10, §18-19. The old architecture asked a model
to order clips and then let each clip edit itself; that produced stitched
compilations. Here the director owns the WHOLE timeline: it judges
eligibility (a story needs a meaningful CHANGE, not a pile of moments),
picks an explicit structure, and emits a story-level EDL with exact in/out
points, per-segment narrative purpose, context overlays (over footage,
never cards), and a global effect budget. After the rough cut renders, a
critic reviews it as a STORY (12 questions) and exactly one revision pass
is allowed before the slot falls back to a normal clip.

Contract: every function returns a validated dict or None, never raises.
"""
from __future__ import annotations

import json
import re

from third_capture.author import (_call_claude, _call_gemini_vision,
                                  _call_text_fallback, scrub_text)

STRUCTURES = {"chronological", "cold_open", "mystery_reveal",
              "two_perspectives", "escalation", "before_after"}
ROLES = {"setup", "escalation", "climax", "payoff", "context", "reaction"}
# What the brain calls a role it means. Backtests 2026-10-07/08 threw away
# three repairs over "unknown beat role 'turn'", "'evidence'", "'proof'" —
# a word, not a defect in the edit. Anything not here is still refused.
ROLE_ALIASES = {"turn": "climax", "twist": "climax", "reveal": "climax",
                "evidence": "context", "proof": "context",
                "background": "context", "resolution": "payoff",
                "punchline": "payoff", "aftermath": "payoff",
                "hook": "setup", "intro": "setup", "build": "escalation",
                "conflict": "escalation", "complication": "escalation",
                "response": "reaction"}
TRANSITIONS = {"hard_cut", "j_cut", "l_cut"}
FRAMINGS = {"wide", "tight"}
# §14: narration never speculates — motive/drama words reject the line
_BAD_NARRATION = re.compile(
    r"\b(furious|revenge|secretly|plotting|planning to|must have|probably"
    r"|devastated|terrified|humiliated)\b", re.I)
MAX_BEATS = 5

_GROUND_STOP = set(
    "the a an and or but to of in on at is was are were be been his her him "
    "them they he she it its for with that this then than from into about "
    "after before over just only also says said tells told asks asked".split())


def narration_grounded(text: str, reports: list[dict]) -> bool:
    """True when a narration line says only what the footage says.

    The story repair may now add ONE spoken line of setup (§14) — the critic
    refused the same Kai Cenat story on three runs because "the opening never
    says what Reggie is accused of", and the reviser was not allowed to say
    it. A line it may SAY is a line it could also invent, so this is the
    check: at least two-thirds of the line's content words (4+ letters, not
    stop words, names included) must appear in the sources' transcripts,
    summaries or people. Not a fact-checker — a floor that a sentence made
    up from nothing cannot clear. Code may only ADD blocks."""
    words = [w for w in re.findall(r"[a-z0-9']+", str(text).lower())
             if len(w) >= 4 and w not in _GROUND_STOP]
    if not words:
        return False
    corpus = " ".join(
        " ".join([str(r.get("transcript_lines", "")),
                  str(r.get("summary", "")),
                  # Twitch metadata, not the footage — but facts: whose
                  # stream it is and what they were playing
                  str(r.get("channel", "")), str(r.get("game", "")),
                  # the streamer's own title for the broadcast
                  str(r.get("stream_title", "")),
                  # who someone is, from general knowledge, checked by a
                  # second model (`known_people`)
                  " ".join(f"{k} {v}" for k, v in
                           (r.get("known_people") or {}).items()),
                  " ".join(str(x) for x in r.get("people") or []),
                  " ".join(str(b.get("purpose", ""))
                           for b in r.get("dialogue_beats") or [])])
        for r in reports).lower()
    have = set(re.findall(r"[a-z0-9']+", corpus))

    def seen(w):
        # "accuses" / "accused" / "accusing" are one word to a viewer
        return w in have or any(h.startswith(w[:5]) for h in have
                                if len(w) >= 6 and len(h) >= 5)
    return sum(1 for w in words if seen(w)) * 3 >= len(words) * 2


_WHO_SYSTEM = """You identify people for captions on a streamer-clip
channel. For each NAME, say who they are TO THE STREAMER in at most 10
words, as a stranger would need it: "Kai Cenat's cousin", "a streamer in
Kai's AMP group", "Lacy's duo partner". Only what is widely known and
stable — a relationship or a role. Never an event, a claim, an
accusation, a motive or anything you are unsure of: then null.
Return STRICT JSON: {"who": {"<name>": "<line>" | null, ...}}"""

_WHO_VERIFY_SYSTEM = """You fact-check captions on a streamer-clip
channel. For each NAME and LINE about who they are to the streamer,
answer true only if you are confident the line is accurate and widely
known; false if it is wrong, unsure, or says anything beyond who the
person is. Return STRICT JSON: {"ok": {"<name>": true|false, ...}}"""

# a who-line names a relationship or a role, never an event
_BAD_WHO = re.compile(
    r"\b(accus|alleg|banned|arrest|lied|lying|scam|cheat|fight|beef|feud"
    r"|drama|stole|steal|charged|lawsuit|sued|controvers|ex-)", re.I)

_WHO_CACHE: dict = {}


def known_people(streamer: str, names: list[str]) -> dict:
    """{name: who they are to the streamer} for the people a story's
    sources name but never introduce — proposed by one model, kept only
    where a SECOND, different model agrees it is accurate.

    The critic's most frequent refusal across story backtests 6-11 was a
    stranger not knowing who someone is (Reggie, Ron, Bruce), and the
    grounding rule forbade any line the sources do not say. The operator
    allowed a line of text on screen (2026-10-08); this is where its
    "who" may come from when the footage never says it. Best-effort:
    any failure or doubt returns nothing, and the cut is as before."""
    names = [str(n).strip() for n in names or []
             if str(n).strip() and str(n).strip().lower()
             != str(streamer).strip().lower()][:8]
    if not names:
        return {}
    key = (str(streamer).lower(), tuple(sorted(n.lower() for n in names)))
    if key in _WHO_CACHE:
        return dict(_WHO_CACHE[key])
    out: dict = {}
    try:
        ask = f"STREAMER: {streamer}\nNAMES: " + json.dumps(names)
        got = (_call_claude(ask, system=_WHO_SYSTEM) or {}).get("who") or {}
        lines = {n: " ".join(str(v).split()) for n, v in got.items()
                 if n in names and v and len(str(v).split()) <= 12
                 and not _BAD_WHO.search(str(v))
                 and not _BAD_NARRATION.search(str(v))}
        if lines:
            ok = (_call_text_fallback(
                f"STREAMER: {streamer}\n" + json.dumps(lines),
                system=_WHO_VERIFY_SYSTEM, tag="who") or {}).get("ok") or {}
            out = {n: v for n, v in lines.items() if ok.get(n) is True}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[director] known_people failed ({e})", flush=True)
        out = {}
    _WHO_CACHE[key] = dict(out)
    return out


def narration_lines(edl: dict | None) -> list[dict]:
    """Every narrator line of an EDL, in beat order. `narration` is the
    first of them (kept for everything that read the one-line format);
    `narration_lines` holds all of them."""
    if not edl:
        return []
    lines = edl.get("narration_lines")
    if lines is None:
        lines = [edl["narration"]] if edl.get("narration") else []
    return [ln for ln in lines if isinstance(ln, dict)]


def _ground(edl: dict | None, reports: list[dict], rs: list) -> dict | None:
    """Drop every narration line the footage does not support — the cut
    stays, the invented sentences go, the grounded ones stay."""
    lines = narration_lines(edl)
    if not lines:
        return edl
    kept = []
    for ln in lines:
        if narration_grounded(ln.get("text", ""), reports):
            kept.append(ln)
        else:
            rs.append("narration dropped — not grounded in the sources: "
                      f"{ln.get('text', '')!r}")
    if len(kept) == len(lines):
        return edl
    edl = dict(edl)
    edl["narration_lines"] = kept
    if kept:
        edl["narration"] = kept[0]
    else:
        edl.pop("narration", None)
    return edl
# banned overlay phrases (§17): overlays prevent confusion, never narrate
# the edit. Meta-labels are prohibited.
_BAD_OVERLAY = re.compile(
    r"\b(the story|part (one|two|three|\d)|climax|it gets|what happens"
    r"|the beginning|the end\b|chapter)", re.I)

_PLAN_SYSTEM = """You are the STORY DIRECTOR for a streamer-clip channel.
You receive structured scene reports for several source clips about the
same developing event: people, summaries, timestamped dialogue/visual
beats, emotional states, missing context, and full transcripts.

FIRST decide eligibility. A valid story contains a MEANINGFUL CHANGE
(allies fall out, an accusation gets answered, a challenge resolves, an
argument escalates or ends, a prediction proves right/wrong...). A pile of
funny moments about the same person is NOT a story. When the premise or
payoff cannot be stated plainly from the sources, return
{"is_story": false, "why_not": "<reason>"}.

If it IS a story, DIRECT it. Choose ONE structure and justify it:
- chronological: setup -> escalation -> payoff (natural timeline compels)
- cold_open: strongest reaction first -> back to the beginning -> payoff
  (only when the real setup is slower than the reaction)
- mystery_reveal: confusing outcome first -> reveal the cause
- two_perspectives: A's action -> B's response -> consequence
- escalation: small incident -> worse -> biggest moment
- before_after: original position -> event -> changed position

THE FIRST THREE SECONDS TELL A STRANGER WHO AND WHAT. The viewer has
never heard of this streamer, this friend, this game or this pet. Before
the story moves, they must know who it is about and what is at stake —
said by the first line, or stated by the hook, or by a narration
line. "Pokimane's cat Mimi" not "my baby"; "CaseOh's sausage challenge"
not "it's done"; "Reggie says Kai ignored his call" not "the proof". In
story backtests the critic's first complaint on most cuts was exactly
this, and no repair can fix a cut that never says it.

Then emit the COMPLETE timeline. Segment rules:
- exact start/end seconds INTO THE NAMED SOURCE, chosen from its dialogue/
  visual beats: enter just before the new information, leave after the
  line lands and the reaction completes (never clip the last half-second
  of a laugh/stunned silence)
- every segment states its narrative purpose; a segment adding no
  information, emotion, escalation, or payoff must not exist
- remove repetition across sources (same explanation twice = cut one)
- context_overlay: 2-6 words, sentence case, briefly replacing the
  caption only when the viewer would otherwise be confused (time jump,
  new speaker, new place) — e.g. "Earlier that day", "Then his friend
  responded". NEVER meta-labels like
  "IT GETS WORSE" or "PART TWO". "" when the cut is already obvious.
- A STRANGER DOES NOT KNOW THE STREAMER OR THE GAME. Each SOURCE's
  `streamer=` and `game=` are Twitch's own metadata — verified facts. When
  nobody on stream says who or what this is, the opening (hook_overlay,
  beat 0's context_overlay, or narration) names them: "FORSEN PLAYING
  TERRARIA" (game=Terraria), "BUDDHA IN GTA" (game=Grand Theft Auto V).
  Never a fact that is in neither the metadata nor the sources.
  `known (general knowledge, verified by a second model)` says who a
  person is to the streamer when the footage never does ("Reggie = Kai
  Cenat's cousin"); a line of text may say exactly that.
  `stream_title=` is the STREAMER'S OWN title for that broadcast — what
  they said the stream was ("FNCS QUALIFIERS DAY 2"). Use it to say what
  was at stake ("LACY'S FNCS QUALIFIER"), attributed to the stream, never
  as a result it does not state.
- transition per beat: "hard_cut" (default) | "j_cut" (next beat's audio
  blends in over the cut — use when the next line naturally answers or
  interrupts) | "l_cut" (previous audio tails briefly over the next
  visual — use when showing the person/evidence being discussed)
- framing per beat: "wide" (default — full scene, use for the incident)
  | "tight" (closer punch-in — use for a response/reaction beat)
- effects: a GLOBAL budget — at most 1 replay ({"type":"replay","at":s}
  re-shows ~2s around `at` slowed, ONLY when the action was genuinely
  hard to see), at most 2 subtle_punch; spend emphasis on the payoff,
  not the first beat. Usually [].
- narration: OPTIONAL top-level LIST, at most ONE line per beat, each
  {"text": <=12 words, "over_beat": idx, "essential_because": str} —
  a line of TEXT shown on screen over that beat (there is NO voice-over;
  this channel never narrates — a line or two of text is all the edit
  says). Use it when the footage
  never says WHO or WHAT the story is about and the scene reports do
  (usually over beat 0), and to bridge how one clip leads to the next
  ("Later that stream, Rakai's bag ended up in a sewer.") when the cut
  jumps. Use as few as the story needs; omit when the footage says it. Verified facts from the reports only, never
  motives, never drama ("Pokimane's cat Mimi got out onto the balcony."
  — good; "He was furious and planning revenge." — forbidden). A line the
  sources do not support is removed automatically.

Return STRICT JSON:
{"is_story": true,
 "premise": str, "central_question": str, "ending_emotion": str,
 "structure": "<one of the six>", "structure_reason": str,
 "title": str,
 "hook_overlay": str,   // 3-7 words, SENTENCE CASE: the ONE caption
                        // that stays on screen the whole video, like a
                        // repost's: "Los thought he ended stream",
                        // "Kai says Reggie is lying", or the clip's own
                        // best quote in quotes ("Opening an umbrella
                        // indoors is bad luck"). It states the
                        // SITUATION in plain words (who + what) — never
                        // a teaser like "He never saw it coming", never
                        // ALL CAPS
 "target_duration": int,                      // seconds, 25-90
 "beats": [{"source_id": str, "start": s, "end": s,
            "role": "setup|escalation|climax|payoff|context|reaction",
            "purpose": str,
            "transition": "hard_cut|j_cut|l_cut",
            "framing": "wide|tight",
            "context_overlay": str,
            "effects": [{"type": "subtle_punch", "at": s}, ...]}, ...],
 "narration": [{"text": str, "over_beat": int,
                "essential_because": str}, ...] | omitted,
 "ending": {"type": "reaction_hold", "duration": 0.8-2.0}}

The FIRST beat is the opening — moving footage from second zero, hook
overlaid on it. 2-5 beats total. Honesty is law: never imply an event the
sources don't show."""

_SCOUT_SYSTEM = """You are the STORY SCOUT for a streamer-clip channel.
You get a CATALOGUE of recent clips across many streamers, one per line:
id | date | streamer | views | title | broadcast position when known |
and, for clips this channel has already WATCHED, what the footage showed
(`saw:`) and what was said (`said:`).

Find the STORIES hiding in it: 2-6 clips that, watched in order, tell ONE
story with a meaningful CHANGE. Stories come in every shape — look for all
of them:
- one stream: setup -> blowup -> reaction, minutes apart (same `vod=`)
- several streams over days or weeks: a ban -> the return; a feud -> the
  confrontation -> the makeup; a challenge started -> attempts -> result;
  a promise or prediction -> proven right or wrong; a running bit that
  keeps escalating
- several streamers: A does something on stream, B reacts or answers on
  B's own stream; a group event seen from two sides
Use what you know about these streamers, their relationships and ongoing
sagas to spot connections a keyword match would miss — but every proposal
must be grounded in lines that are actually in the catalogue.

NOT a story: a streamer's greatest hits; clips that merely share a person;
the same moment clipped twice; a pile of funny moments with no change.

EVIDENCE BEFORE TITLES. A title is a guess typed by a stranger; `saw:`
and `said:` are what is actually in the clip. Where they disagree, the
footage wins. Every proposal is VERIFIED against the real transcripts and
frames and refused when the footage does not show it — and that costs
minutes per clip, so:
- Build on watched clips wherever the story allows. A turning point that
  rests only on a title must be one the title states outright.
- Never infer a cause, a chain of events or a motive the lines do not
  each state. "Gets sniped by a boar" in a title is not a boar in the
  footage; five titles from one stream are not five chapters of one plot.
- Clips hours apart in one broadcast are separate moments unless the
  lines themselves link them.
- Fewer clips beats more: the 2-4 that carry the change, never padding.
  Every member must be a beat a viewer needs.
- ALREADY REFUSED (when listed below) are stories the director watched
  and turned down, with the reason. Do not propose them again unless a
  clip that was not in them changes what happened.

Return STRICT JSON, best story first, at most 6:
{"stories": [{"members": ["C3", "C9", "C14"],
              "premise": "<one sentence: who, what changed>",
              "why_connected": "<why these clips are one story>",
              "shape": "one_stream|multi_stream|multi_streamer"}]}
Return {"stories": []} when the catalogue holds no real story."""


def scout_stories(lines: list[str], ids: set[str],
                  max_stories: int = 6,
                  tried: list[str] | None = None) -> list[dict]:
    """Ask the brain which clips in the catalogue form stories.

    The scout PROPOSES; it never decides. A proposal only buys the expensive
    part — scene analysis on its members — and then `plan_story` judges it
    against what the footage actually says and shows, with the §8 gate
    unchanged. This replaces the job the token-overlap heuristics were doing
    badly: across 2026-09-16..22 they grouped 21 piles, 11 of which had no
    two clips about the same thing, and never once handed the director a
    story. An editor finds a story by knowing what happened, not by
    matching words in titles.

    Validation is structural and strict: members must be catalogue ids,
    distinct, 2-6 of them. Returns [] on no brain, bad JSON or no stories —
    the slot then falls back to the mechanical candidates. Never raises."""
    if len(lines) < 2:
        return []
    try:
        out = _brain("CATALOGUE:\n" + "\n".join(lines)
                     + ("\n\nALREADY REFUSED (the director watched these):\n"
                        + "\n".join(tried) if tried else ""),
                     _SCOUT_SYSTEM)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[scout] failed ({e})", flush=True)
        return []
    stories = (out or {}).get("stories") if isinstance(out, dict) else None
    if not isinstance(stories, list):
        return []
    kept: list[dict] = []
    for st in stories:
        if not isinstance(st, dict):
            continue
        mem = [str(m).strip() for m in (st.get("members") or [])]
        mem = list(dict.fromkeys(m for m in mem if m in ids))
        if not 2 <= len(mem) <= 6:
            continue
        kept.append({
            "members": mem,
            "premise": scrub_text(str(st.get("premise", "")).strip())[:200],
            "why_connected": scrub_text(
                str(st.get("why_connected", "")).strip())[:240],
            "shape": str(st.get("shape", ""))[:20],
        })
        if len(kept) >= max_stories:
            break
    return kept


_REVIEW_SYSTEM = """You are the NARRATIVE CRITIC for a streamer-story
channel. You receive a story's premise, its edit plan (EDL), the final
rendered transcript, a contact-sheet image path (read it if given), and
the duration. Judge it as a STORY a stranger encounters cold:

1. Can a stranger explain what happened?  2. Is the central question
clear?  3. Is anyone shown before being introduced?  4. Is necessary
information missing?  5. Is information repeated?  6. Does every beat
advance the story?  7. Is the chronology clear?  8. Does the opening
create curiosity?  9. Does the ending answer it?  10. Is anything
misleading?  11. Is emphasis on the right moment?  12. Does it feel like
ONE story rather than several clips?

Be stricter about coherence than cosmetics. Before you score, write the
story the way a stranger would retell it to a friend, in ONE sentence — if
you cannot, it is not a story yet. Then name the PAYOFF: the second at
which the question the opening raised is answered (a reveal, a reaction
to the consequence, a reversal). A cut that simply runs out, or ends on
an unrelated line, has NO payoff — say so with payoff_at: null and
publish: false. A score of 80+ means a stranger would watch to the end
and could retell it; 60-79 means it hangs together but would not hold
them; below 60 is a pile of clips.

Return STRICT JSON:
{"publish": true|false, "story_score": 0-100,
 "stranger_summary": "<the one-sentence retelling>",
 "payoff_at": <seconds> | null,
 "problems": [{"type": "missing_context|repetition|weak_payoff|confusing|
               misleading|pacing|other",
               "at": <seconds>, "fix": "<specific instruction>"}, ...]}"""

_REVISE_SYSTEM = """You are the story director revising your own edit
based on the critic's timestamped problems. You may only: adjust cut
boundaries, remove a repetitive segment, extend a reaction, add/remove a
context overlay, change a transition, remove an effect — and, when the
critic names missing_context or confusing, add or rewrite narration
lines: a LIST, at most ONE per beat.

Narration ([{"text", "over_beat", "essential_because"}, ...]): each line
at most 12 words of on-screen TEXT (never a voice) over the beat that
needs it — beat 0 to set up
who and what, a later beat to bridge a jump the critic could not follow.
It may state ONLY what a source's transcript or scene report states —
who someone is, what they said happened, what was claimed — in the
footage's own words where possible — plus a source's `known` line (who
a person is to the streamer, verified by a second model) and its `streamer=`,
`game=` and `stream_title=` (the streamer's own title for the broadcast:
what the stream was, e.g. a qualifier, a subathon, a trial), which are
Twitch's own metadata. When the critic says a stranger
does not know who this is or what they are playing, name them: in the
hook, beat 0's context overlay, or the narration line. Never motive,
never feelings, never drama, never anything the sources do not say. `essential_because` names
the source line it comes from. A line not supported by the sources is
removed automatically, so do not guess. If the missing context is not in
the sources at all, fix what you can with cuts instead.

The critic's times are on the OUTPUT clock (the rendered video); your
EDL is in each SOURCE's own seconds. Each problem is mapped for you to the
beat and source second it lands on, and THE CUT THE CRITIC WATCHED shows
every line each beat kept, in source seconds: move a boundary to the line
you mean — past a garbled or repeated line, onto a clean one.

You may NOT add new sources. Return the COMPLETE corrected EDL in the
exact same JSON schema you used before (is_story true, same fields)."""


def _fmt_reports(reports: list[dict]) -> str:
    out = []
    for r in reports:
        beats = "; ".join(
            f"[{b['start']:.1f}-{b['end']:.1f}] {b.get('speaker', '')}: "
            f"{b.get('purpose', '')}" for b in r.get("dialogue_beats", []))
        vis = "; ".join(
            f"[{b['start']:.1f}-{b['end']:.1f}] {b.get('event', '')}"
            for b in r.get("visual_beats", []))
        # Broadcast position, when the sources are one stream (a VOD arc).
        # Without it the director sees three same-day clips with no order
        # and has to guess which is the setup and which the reaction —
        # Twitch already told us, to the second.
        at = ""
        if r.get("vod_offset") is not None:
            try:
                o = int(float(r["vod_offset"]))
                vid = r.get("video_id")
                at = ((f" broadcast={vid}" if vid else "")
                      + f" at={o // 3600}h{(o % 3600) // 60:02d}m"
                        f"{o % 60:02d}s")
            except (TypeError, ValueError):
                at = ""
        game = f" game={r['game']}" if r.get("game") else ""
        if r.get("stream_title"):
            game += f" stream_title={r['stream_title']!r}"
        who = "; ".join(f"{k} = {v}" for k, v in
                        (r.get("known_people") or {}).items())
        who = (f"  known (general knowledge, verified by a second model): "
               f"{who}\n" if who else "")
        out.append(
            f"SOURCE {r['source_id']}\n"
            f"  streamer={r['channel']} dur={r['duration_s']}s "
            f"date={r.get('date', '?')}{at}{game}\n"
            f"  summary: {r['summary']}\n"
            f"  people: {', '.join(r.get('people', []))}\n"
            f"{who}"
            f"  dialogue: {beats or '(none)'}\n"
            f"  visual: {vis or '(none)'}\n"
            f"  emotions: {', '.join(r.get('emotional_state', []))}\n"
            f"  missing_context: {'; '.join(r.get('missing_context', []))}\n"
            f"  opens_mid_sentence={r.get('opens_mid_sentence')} "
            f"payoff_shown={r.get('payoff_shown')}\n"
            # full transcript (reviewer #3): the identified dialogue/visual
            # beats above already survive intact; give the director the
            # complete words too so a late reaction isn't cut off
            f"  transcript:\n{r.get('transcript_lines', '')[:8000]}")
    return "\n\n".join(out)


def _windows(reports: list[dict]) -> dict[str, list]:
    """source_id -> [(start,end)] evidence windows a cut may land on:
    every dialogue beat, visual beat, and candidate window from analysis."""
    out: dict[str, list] = {}
    for r in reports:
        w = []
        for key in ("dialogue_beats", "visual_beats", "candidate_windows"):
            for b in r.get(key, []):
                try:
                    w.append((float(b["start"]), float(b["end"])))
                except (TypeError, ValueError, KeyError):
                    continue
        if w:
            out[r["source_id"]] = w
    return out


def _overlaps(s: float, e: float, windows: list) -> bool:
    """True if [s,e] intersects any (ws,we) evidence window (>=0.5s)."""
    for ws, we in windows:
        if min(e, we) - max(s, ws) >= 0.5:
            return True
    return False


def _positions(reports: list[dict]) -> dict[str, tuple]:
    """source_id -> (timeline, t0): which recording a source is cut from and
    where its second 0 sits on it. Sources from one broadcast share the
    broadcast's video_id and are placed by `broadcast_t0` (the clip's VOD
    offset, or the start of the VOD window it was expanded to); any other
    source is its own timeline starting at 0, which still catches two beats
    cut over the same seconds of one clip."""
    out = {}
    for r in reports:
        sid = r.get("source_id")
        vid, t0 = r.get("video_id"), r.get("broadcast_t0")
        try:
            out[sid] = ((str(vid), float(t0)) if vid and t0 is not None
                        else (f"src:{sid}", 0.0))
        except (TypeError, ValueError):
            out[sid] = (f"src:{sid}", 0.0)
    return out


def _no_replayed_seconds(beats: list[dict], positions: dict,
                         rs: list) -> list[dict]:
    """Trim or drop a beat that replays seconds an EARLIER beat already
    showed. Two clips of one broadcast overlap whenever two clippers caught
    the same moment, and the director, reading them as separate sources,
    cut the shared stretch twice: the story backtest of 2026-10-05 opened
    with "You kept talking about proof, right?" twice back to back, and the
    critic named it on 10-04, 10-05 and in the backtest. Every beat after
    the first is moved off any stretch already shown; one left under 1.5s
    is dropped. Recorded as a repair."""
    shown: list[tuple] = []
    out = []
    for b in beats:
        tl, t0 = positions.get(b["source_id"], (f"src:{b['source_id']}", 0.0))
        s, e = b["start"], b["end"]
        for (otl, a, z) in shown:
            if otl != tl:
                continue
            bs, be = t0 + s, t0 + e
            if min(be, z) - max(bs, a) <= 0.5:
                continue
            if bs >= a:                      # starts inside: begin after it
                s = z - t0
            elif be <= z:                    # ends inside: end before it
                e = a - t0
            else:                            # straddles: keep the later part
                s = z - t0
        if e - s < 1.5:
            rs.append(f"beat {b['source_id']} {b['start']:.1f}-{b['end']:.1f}s"
                      " only replays seconds already shown — dropped "
                      "(repaired)")
            continue
        if (s, e) != (b["start"], b["end"]):
            rs.append(f"beat {b['source_id']} trimmed {b['start']:.1f}-"
                      f"{b['end']:.1f}s -> {s:.1f}-{e:.1f}s so no second of "
                      "the broadcast plays twice (repaired)")
            b = dict(b, start=round(s, 2), end=round(e, 2))
        shown.append((tl, t0 + s, t0 + e))
        out.append(b)
    return out


def _norm_w(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", str(w).lower())


def _no_repeated_lines(beats: list[dict], words: dict, rs: list,
                       min_run: int = 4) -> list[dict]:
    """Trim a beat that OPENS on the words the previous beat just ended on.

    `_no_replayed_seconds` needs broadcast positions, and clips taken from
    the channel's month of posts carry none — so the scout's Kai Cenat cut
    in the second story backtest (2026-10-05) still said "You kept talking
    about proof, right?" twice across the seam. The transcript catches what
    the timestamps cannot: when the last `min_run`+ words of one beat are
    the first words of the next, the next beat starts after them. One left
    under 1.5s is dropped. Recorded as a repair."""
    out: list[dict] = []
    for b in beats:
        if out:
            prev = out[-1]
            pw = [w for w in words.get(prev["source_id"]) or []
                  if w["e"] > prev["start"] and w["s"] < prev["end"]]
            cw = [w for w in words.get(b["source_id"]) or []
                  if w["e"] > b["start"] and w["s"] < b["end"]]
            tail = [_norm_w(w["w"]) for w in pw[-14:]]
            head = [_norm_w(w["w"]) for w in cw[:14]]
            k = 0
            for n in range(min(len(tail), len(head)), min_run - 1, -1):
                if tail[-n:] == head[:n] and all(tail[-n:]):
                    k = n
                    break
            if k:
                new_start = round(cw[k - 1]["e"] + 0.05, 2)
                if b["end"] - new_start < 1.5:
                    rs.append(f"beat {b['source_id']} only repeats the "
                              f"{k} words the last beat ended on — dropped "
                              "(repaired)")
                    continue
                rs.append(f"beat {b['source_id']} opened on the {k} words "
                          f"the last beat ended on — starts at "
                          f"{new_start:.1f}s (repaired)")
                b = dict(b, start=new_start)
        out.append(b)
    return out


_DANGLING = frozenset(
    "a an the of out to in on at for with and or but from by into about "
    "his her their its my your our than as that who".split())


def _finish_the_sentence(beats: list[dict], words: dict,
                         durations: dict, rs: list,
                         max_extend: float = 3.0,
                         min_beat: float = 1.5) -> list[dict]:
    """The story ends where a sentence ends, not mid-word.

    Third story backtest (2026-10-06): the one cut that cleared the bar
    ended on "I have them" — the critic: "the final line is cut
    mid-phrase". A word ENDS A THOUGHT when it carries sentence punctuation,
    or a pause of 0.35s+ follows it in the source (a clip that stops
    mid-sentence is not a pause). If the
    last beat's end is not just after such a word, it runs on to the next
    one, at most `max_extend` seconds and never past the source.

    Fourth backtest: the same Emiru clip ENDS mid-sentence ("than my bed.
    I have them") so there was nothing to run on to, and the critic asked
    for the other fix — "trim to end right after 'this is better than my
    bed'". When no ending is reachable forward, the beat is cut BACK to the
    last one inside it, keeping at least `min_beat` seconds. Both are
    recorded as repairs."""
    if not beats:
        return beats
    last = beats[-1]
    ws = sorted(words.get(last["source_id"]) or [], key=lambda w: w["s"])
    if not ws:
        return beats
    start, end = float(last["start"]), float(last["end"])
    src_end = float(durations.get(last["source_id"]) or end)
    limit = min(end + max_extend, src_end)

    def ends_thought(i):
        if str(ws[i]["w"]).rstrip("\"'”’)").endswith((".", "!", "?")):
            return True
        if i < len(ws) - 1:
            return ws[i + 1]["s"] - ws[i]["e"] >= 0.35
        # the source's last word ends a thought only if the source goes
        # on in silence after it. Backtest #6: Emiru's payoff clip stops
        # on "I have them" and that counted as an ending, so the first
        # cut ended there again.
        return src_end - ws[i]["e"] >= 0.35

    if any(w["s"] < end - 0.05 and w["e"] > end + 0.05 for w in ws):
        clean = False                                   # a word straddles it
    else:
        before = [i for i, w in enumerate(ws) if w["e"] <= end + 0.05]
        clean = not before or ends_thought(before[-1])
    if clean:
        return beats
    fwd = [w["e"] for i, w in enumerate(ws)
           if w["e"] > end - 0.05 and w["e"] <= limit and ends_thought(i)]
    if fwd:
        new_end, how = fwd[0], "ran on to the end of the sentence"
    else:
        back = [w["e"] for i, w in enumerate(ws)
                if start + min_beat <= w["e"] <= end and ends_thought(i)]
        if not back:
            return beats
        new_end, how = back[-1], "cut back to the last finished sentence"
    new_end = round(min(new_end + 0.1, src_end), 2)
    if abs(new_end - end) <= 0.05:
        return beats
    rs.append(f"last beat ended mid-sentence: {how}, end {end:.1f}s -> "
              f"{new_end:.1f}s (repaired)")
    return beats[:-1] + [dict(last, end=new_end)]


def _words(reports: list[dict]) -> dict:
    return {r.get("source_id"): r.get("words") or [] for r in reports}


def validate_edl(edl: dict, durations: dict[str, float],
                 windows: dict[str, list] | None = None,
                 reasons: list | None = None,
                 positions: dict | None = None,
                 words: dict | None = None) -> dict | None:
    """Hard-validate a director EDL against the playbook's NARRATIVE laws,
    not just syntax (reviewer #8). Returns the cleaned EDL or None.
    `durations` maps source_id -> clip length; `windows` maps source_id ->
    [(start,end)] evidence windows (dialogue/visual/candidate beats) so a
    cut can be required to land on something that actually happens.

    `reasons` (optional list) collects WHY a plan was thrown out. Every
    rejection here used to be indistinguishable from the director saying
    "this is not a story": the caller logged both as "no genuine arc". Over
    2026-08-10..09-08 that verdict was recorded 22 times with a healthy
    brain and not one story shipped, and nothing in the record could say
    whether the director declined or produced a plan that tripped one of
    these ten gates. Name the gate."""
    windows = windows or {}
    rs = reasons if reasons is not None else []
    try:
        if not edl:
            rs.append("no plan returned")
            return None
        if not edl.get("is_story"):
            # the ONLY editorial "no" in this function; everything below is
            # a malformed plan, which is a different problem with a
            # different fix
            # KEEP THE REASON. The director is asked for
            # {"is_story": false, "why_not": ...} and this recorded only the
            # verdict. On 2026-09-23 it turned down all three of the scout's
            # stories and the record could not say whether the footage
            # didn't show them, the director was too strict, or the clips
            # never loaded — three different fixes. "not a story" stays in
            # the string: `plan_story` keys the editorial flag on it.
            why_not = scrub_text(str(edl.get("why_not", "")).strip())[:200]
            rs.append("director judged: not a story"
                      + (f" — {why_not}" if why_not else ""))
            return None
        structure = str(edl.get("structure", ""))
        if structure not in STRUCTURES:
            rs.append(f"unknown structure {structure!r}")
            return None
        premise = str(edl.get("premise", "")).strip()
        central_q = str(edl.get("central_question", "")).strip()
        payoffish = [b for b in (edl.get("beats") or [])
                     if str(b.get("role")) in ("payoff", "climax")]
        if not premise or not central_q or not payoffish:
            rs.append("missing premise/central_question/payoff beat")
            return None          # §8: premise + question + payoff required
        # The hook is a 3-7 word curiosity line. AN OVER-LONG HOOK IS A
        # FORMATTING NIT, NOT AN INCOHERENT STORY — and this function
        # already says so everywhere else: a malformed context_overlay is
        # dropped, a bad transition and a bad framing are coerced to
        # defaults. Only `hook_overlay` threw away an entire validated arc
        # over a word count. Trim it, the same way the overlay is trimmed.
        # A hook under 3 words is not a curiosity line and still rejects.
        hook_raw = scrub_text(str(edl.get("hook_overlay", "")).strip())
        _hw = hook_raw.split()
        if len(_hw) > 7:
            # never end on a dangling word: backtest #5 shipped "EMIRU
            # FIGHTS A MATTRESS OUT OF A" to the critic, who called the
            # title cut off
            kept = _hw[:7]
            while len(kept) > 3 and kept[-1].lower().strip(",.:;!?") in \
                    _DANGLING:
                kept.pop()
            hook_raw = " ".join(kept)
            rs.append(f"hook trimmed {len(_hw)}->{len(kept)} words "
                      "(repaired)")
        elif len(_hw) < 3:
            rs.append(f"hook too short ({len(_hw)} words)")
            return None
        # KEEP THE PAYOFF WHEN THE CAP BITES.
        #
        # The payoff check above runs over the FULL, unbounded input, and the
        # cap ran after it: a six-beat plan whose only payoff was beat six
        # satisfied the check, lost that beat to `[:MAX_BEATS]`, and could
        # still pass because a terminal `reaction` is accepted as an ending
        # (doctor finding 02da0ae2137f). The result is a "story" that stops
        # before the thing it was about.
        #
        # Dropping the plan over that is the wrong repair — the arc is fine,
        # it is one beat too long. So the cap keeps the first MAX_BEATS-1
        # beats and the LAST payoff/climax, which loses a middle escalation
        # step rather than the ending. Same spirit as the hook trim above,
        # and recorded as a repair so the record says what happened.
        raw_beats = list(edl.get("beats") or [])
        if len(raw_beats) > MAX_BEATS:
            tail = [i for i, b in enumerate(raw_beats)
                    if str(b.get("role")) in ("payoff", "climax")
                    and i >= MAX_BEATS]
            if tail:
                keep = raw_beats[:MAX_BEATS - 1] + [raw_beats[tail[-1]]]
                rs.append(f"beats trimmed {len(raw_beats)}->{MAX_BEATS}, "
                          f"keeping the payoff at beat {tail[-1] + 1} "
                          "(repaired)")
            else:
                keep = raw_beats[:MAX_BEATS]
        else:
            keep = raw_beats

        beats = []
        n_punch = n_replay = n_overlay = 0
        for b in keep:
            sid = str(b.get("source_id", ""))
            dur = durations.get(sid)
            if dur is None:
                rs.append(f"beat references unknown source {sid!r}")
                return None      # director referenced an unknown source
            s = max(0.0, float(b.get("start", 0)))
            e = min(float(dur), float(b.get("end", 0)))
            if e - s < 1.5:
                rs.append(f"beat {sid} is {e - s:.2f}s (<1.5s)")
                return None      # sub-1.5s segments are noise, not beats
            # the cut must land on something that actually happens — a
            # dialogue/visual/candidate window in that source (skipped only
            # when analysis produced no windows for it, to avoid over-reject)
            w = windows.get(sid)
            if w and not _overlaps(s, e, w):
                rs.append(f"beat {sid} {s:.1f}-{e:.1f}s lands on no "
                          f"analysed window")
                return None
            role = str(b.get("role", "")).strip().lower()
            if role in ROLE_ALIASES:
                rs.append(f"beat role {role!r} read as "
                          f"{ROLE_ALIASES[role]!r} (repaired)")
                role = ROLE_ALIASES[role]
            if role not in ROLES:
                rs.append(f"unknown beat role {role!r}")
                return None
            purpose = str(b.get("purpose", "")).strip()
            if not purpose:
                rs.append(f"beat {sid} states no purpose")
                return None      # §10: every segment states its purpose
            overlay = scrub_text(
                str(b.get("context_overlay", "")).strip())[:40]
            if overlay:
                if _BAD_OVERLAY.search(overlay) or \
                        not (2 <= len(overlay.split()) <= 6):
                    overlay = ""             # banned/oversized -> drop it
                else:
                    n_overlay += 1
            effects = []
            for fx in (b.get("effects") or []):
                ft = str(fx.get("type", ""))
                if ft == "subtle_punch" and n_punch < 2:
                    n_punch += 1
                    effects.append({"type": ft,
                                    "at": max(0.0, float(fx.get("at", 0)))})
                elif ft == "replay" and n_replay < 1:
                    n_replay += 1
                    effects.append({"type": ft,
                                    "at": max(0.0, float(fx.get("at", 0)))})
            trans = str(b.get("transition", "hard_cut"))
            if trans not in TRANSITIONS:
                trans = "hard_cut"
            framing = str(b.get("framing", "wide"))
            if framing not in FRAMINGS:
                framing = "wide"
            beats.append({"source_id": sid, "start": round(s, 2),
                          "end": round(e, 2), "role": role,
                          "purpose": purpose[:120],
                          "transition": trans,
                          "framing": framing,
                          "context_overlay": overlay,
                          "effects": effects})
        beats = _no_replayed_seconds(beats, positions or {}, rs)
        beats = _no_repeated_lines(beats, words or {}, rs)
        beats = _finish_the_sentence(beats, words or {}, durations, rs)
        if len(beats) < 2:
            rs.append(f"only {len(beats)} valid beat(s)")
            return None
        # A STORY IS MORE THAN ONE CLIP. Four beats cut from one source is
        # a re-edit of a clip the clip arm already handles — and now that
        # the director may tell the story a scout's pile really holds from
        # a subset of it, "a subset of one" is the case to refuse.
        if len({b["source_id"] for b in beats}) < 2:
            rs.append("every beat is from one source — a clip, not a story")
            return None
        if n_overlay > max(0, len(beats) - 1):
            rs.append("a context overlay on every beat = decoration")
            return None          # an overlay on every beat = decoration
        # §8/§20: the story must END on its payoff — not trail off on a
        # context/setup beat (reviewer #8: "could validate while ending on
        # an irrelevant context beat")
        if beats[-1]["role"] not in ("payoff", "climax", "reaction"):
            rs.append(f"ends on a {beats[-1]['role']!r} beat, not the payoff")
            return None
        # The payoff must have SURVIVED, not merely been present in the
        # input. A beat can also be dropped inside the loop above (unknown
        # source, unusable window), so this is checked on what was built —
        # the only list that describes the video that would actually be cut.
        if not any(b["role"] in ("payoff", "climax") for b in beats):
            rs.append("no payoff/climax beat survived validation — the plan "
                      "had one, the cut would not")
            return None
        # first beat must fit the chosen structure: a cold_open / mystery
        # opens on the strong moment; the timeline structures open on setup
        first_role = beats[0]["role"]
        if structure in ("cold_open", "mystery_reveal"):
            if first_role not in ("climax", "payoff", "reaction"):
                rs.append(f"{structure} must open strong, opens on "
                          f"{first_role!r}")
                return None
        elif structure in ("chronological", "escalation", "before_after"):
            if first_role not in ("setup", "context", "escalation"):
                rs.append(f"{structure} must open on setup, opens on "
                          f"{first_role!r}")
                return None
        # §14 narration: optional, justified, verified-voice only. Key is
        # `over_beat` (reviewer #10) — narration is DUCKED OVER that beat,
        # which is what the renderer does; `after_beat` still read for compat
        # THE NARRATOR: up to ONE line per beat (story backtests
        # 2026-10-07: ten cuts, every near-miss refused for context the
        # footage never says — who someone is, how the bag got into the
        # sewer, that the ban came minutes later — and the cut was allowed
        # one line for all of it). A dict is the old one-line form.
        n_raw = edl.get("narration")
        cands = (n_raw if isinstance(n_raw, list)
                 else [n_raw] if isinstance(n_raw, dict) else [])
        lines, taken = [], set()
        for n_in in cands:
            if not isinstance(n_in, dict):
                continue
            text = scrub_text(str(n_in.get("text", "")).strip())[:90]
            why = str(n_in.get("essential_because", "")).strip()
            # NOT `int(...) or -1`: beat 0 is falsy, so that turned "over
            # the opening" into -1 and dropped every narration line meant to
            # SET UP the story — the one place the critic kept asking for it
            # ("the opening never says what Reggie is accused of").
            try:
                over = int(n_in.get("over_beat", n_in.get("after_beat", -1)))
            except (TypeError, ValueError):
                over = -1
            if (text and why and 0 <= over < len(beats)
                    and over not in taken
                    and len(text.split()) <= 15
                    and not _BAD_NARRATION.search(text)):
                taken.add(over)
                lines.append({"text": text, "over_beat": over,
                              "essential_because": why[:120]})
        lines.sort(key=lambda ln: ln["over_beat"])
        narration = lines[0] if lines else None
        # target_duration is advisory; clamp into the 25-90s band (§6)
        target = int(edl.get("target_duration", 45) or 45)
        target = min(90, max(25, target))
        end = edl.get("ending") or {}
        # reaction hold is a real hold — at least 0.8s (§12)
        hold = min(2.0, max(0.8, float(end.get("duration", 1.0) or 1.0)))
        return {
            "is_story": True,
            "premise": premise[:200],
            "central_question": central_q[:150],
            "ending_emotion": str(edl.get("ending_emotion", ""))[:40],
            "structure": structure,
            "structure_reason": str(edl.get("structure_reason", ""))[:200],
            "title": str(edl.get("title", "")).strip()[:95],
            # sentence case, as the line is shown (the reposts it looks
            # like: "Los thought he ended stream")
            "hook_overlay": hook_raw[:60],
            "target_duration": target,
            "beats": beats,
            "narration": narration,
            "narration_lines": lines,
            "ending": {"type": "reaction_hold", "duration": hold},
        }
    except (TypeError, ValueError, KeyError):
        return None


def _brain(user: str, system: str,
           read_files: bool = False, require_vision: bool = False,
           image_path: str | None = None) -> dict | None:
    """The director's model call. `read_files=True` grants Claude the Read
    tool so it can actually OPEN a contact-sheet image referenced in `user`
    — without it the critic is blind to the rendered frames and can only
    reason about text. `image_path` is that same image, handed to Gemini
    as inline data when Claude does not answer. The text fallback (Groq,
    then Gemini without the image) is text-only.

    `require_vision=True` means the answer is only trustworthy if a
    vision-capable model produced it: Claude (with the Read grant) or
    Gemini (with the image attached). If neither answers we return None
    instead of falling through to the text-only fallback. Without this, a rough-cut critic that
    is supposed to LOOK at the frames could be silently rubber-stamped by a
    Groq verdict that never saw them (reviewer #11) — mirrors the scene
    analyzer's `vision_ok` provenance."""
    out = None
    try:
        out = _call_claude(user, system=system, read_files=read_files)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[director] claude failed ({e}) — groq",
              flush=True)
    if out is not None:
        return out
    if read_files and image_path:
        # Gemini is the second vision backend: it receives the image
        # itself (inline data), so its verdict satisfies require_vision
        # honestly — it LOOKED. Added 2026-09-30 after two zero-post days
        # with Claude at its weekly limit.
        out = _call_gemini_vision(user, system, image_path, tag="director")
        if out is not None:
            return out
    if require_vision:
        print("::warning::[director] a VISION verdict was required but no "
              "vision backend (claude, gemini) answered — refusing the "
              "text-only fallback (fail closed)", flush=True)
        return None
    return _call_text_fallback(user, system=system, tag="director")


# Why the last plan_story() call ended the way it did. Read by run_third
# so the recorded verdict names the actual gate instead of a catch-all.
_LAST_REJECTION: dict = {}


def last_rejection() -> dict:
    """{'why': str, 'editorial': bool} for the most recent plan_story()."""
    return dict(_LAST_REJECTION)


_LAST_TAKES: list = []


def last_takes() -> list[dict]:
    """Every valid take the most recent plan_story() produced, best-first
    as the director ordered them (the first is what plan_story returned)."""
    return list(_LAST_TAKES)


_TAKES_ASK = (
    "\n\nWRITE {n} DIFFERENT TAKES on this story — an editor's alternate "
    "cuts, not copies: a different opening line, different beats kept or "
    "dropped, a different place to end, a different structure where one "
    "fits. Each take is a COMPLETE plan in the schema above. Return "
    '{{"is_story": true, "takes": [<plan>, <plan>, ...]}}, your best '
    "first — or the usual is_story false and why when there is no story.")


def plan_story(reports: list[dict], event: dict | None = None,
               guidance: str = "", hypothesis: str = "",
               moment: str = "", takes: int = 1) -> dict | None:
    """Eligibility gate + structure choice + full story EDL, validated.
    `guidance` is the channel's own evidence about which structures/
    lengths retain (empty until >=25 mature stories exist — creative
    decisions are never optimized before coherence is proven, spec §23).
    None = not a story / director unreachable / plan invalid."""
    if len(reports) < 2:
        return None
    user = ""
    if guidance:
        user += f"CHANNEL EVIDENCE (from our own analytics): {guidance}\n\n"
    if event:
        user += (f"EVENT: {event.get('event_id', '?')} "
                 f"people={event.get('people')} "
                 f"type={event.get('event_type', '?')}\n\n")
    if moment:
        # storyline.find_moments: one clip and the stream either side of it
        user += f"WHAT THESE SOURCES ARE: {moment}\n\n"
    if hypothesis:
        # The scout's reading, mostly from titles. The director is the one
        # with the transcripts and frames — it confirms or kills it. But a
        # scout that padded a real two-clip story with three clips the
        # footage does not support has still found a story: the director
        # may tell the one the footage DOES show, from the sources that
        # show it (the beats name their sources; validate_edl and §8 hold
        # it exactly as they hold any plan). Killing the whole pile threw
        # away what the downloads and the analysis had just paid for.
        user += ("A SCOUT PROPOSED THIS STORY, mostly from clip titles: "
                 f"{hypothesis}\nTreat it as a HYPOTHESIS. Verify it against "
                 "the scene reports below. If the footage does not show "
                 "it, ask what the footage DOES show: when some of these "
                 "sources tell a real story on their own, direct THAT story "
                 "from those sources only (two or more) and leave the rest "
                 "out. If none "
                 "do, reject it and say what the footage showed instead — "
                 "the scout never saw the clips.\n\n")
    # ONE broadcast means one shared video_id — not merely "every source has
    # a position". A scouted multi-stream story has positions too, in
    # DIFFERENT broadcasts, and telling the director they are one stream
    # would be a false premise handed to the one judge that must not get one.
    _vids = {str(r.get("video_id") or "") for r in reports}
    if (reports and len(_vids) == 1 and "" not in _vids
            and all(r.get("vod_offset") is not None for r in reports)):
        # Say it plainly: these are not clips that might be related. They
        # were cut from the same broadcast, in this order.
        user += ("THESE SOURCES ARE ONE BROADCAST: consecutive moments from "
                 "the same stream, listed in broadcast order "
                 "(`at=`). Judge whether they form setup -> "
                 "escalation -> payoff; do not assume they do.\n\n")
    user += "SCENE REPORTS:\n" + _fmt_reports(reports)
    _LAST_TAKES.clear()
    out = _brain(user + (_TAKES_ASK.format(n=takes) if takes > 1 else ""),
                 _PLAN_SYSTEM)
    rs: list = []
    if out is None:
        rs.append("director unreachable")
        _LAST_REJECTION.clear()
        _LAST_REJECTION.update(why="; ".join(rs), editorial=False)
        return None
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    # SEVERAL TAKES (story backtests 7-9: a plan that opened at 58 never
    # climbed past ~66 by repair, while a different cut of the same
    # footage scored 78). Each take meets every law on its own; the table
    # read in run_third picks which one is rendered.
    raw = out.get("takes") if isinstance(out, dict) else None
    if isinstance(raw, list) and raw:
        cands = [dict(t, is_story=True) for t in raw[:max(1, takes)]
                 if isinstance(t, dict)]
    else:
        cands = [out]
    edl = None
    for i, cand in enumerate(cands):
        trs: list = []
        e = validate_edl(cand, durations, _windows(reports), reasons=trs,
                         positions=_positions(reports),
                         words=_words(reports))
        # the director's own narration meets the same floor as the reviser's
        e = _ground(e, reports, trs)
        if e:
            _LAST_TAKES.append(e)
            edl = edl or e
        rs.extend(trs if len(cands) == 1 else [f"take {i}: {r}"
                                               for r in trs])
    # `editorial` separates "a human editor would also say no" from "the
    # plan was malformed" — the second is OUR bug and needs a code fix, and
    # for a month both were logged as "no genuine arc".
    _LAST_REJECTION.clear()
    _LAST_REJECTION.update(
        why="; ".join(rs) or ("accepted" if edl else "rejected, no reason"),
        editorial=any("not a story" in r for r in rs))
    return edl


def _fmt_on_screen(items: list[dict] | None) -> str:
    """What the cut shows and says beyond the streamer's own words.

    Backtest #5: every cut was marked down for missing context, including
    the ones whose added text SAID it — the critic samples frames (a 1-2s
    overlay falls between them) and reads the source transcript (the
    edit's own words are not in it). It is told what is really there, on the
    output clock, and still judges whether that is enough."""
    if not items:
        return ""
    # The title is ONE caption that stays up the whole video, stepping
    # aside for a context line — the channel's format, like the reposts
    # it copies (operator, 2026-10-08). Listed per piece, it read to the
    # critic as the same card "repeated across the entire video" and 12 of
    # backtest 12's 27 cuts were marked down for it. It is shown once, as
    # what it is; the critic still judges whether its WORDS are right.
    titles = [o for o in items if o["kind"] == "title"]
    rows = []
    if titles:
        rows.append(f"- CAPTION, on screen the whole video by design (this "
                    f"channel's format: one line of text, like a repost's "
                    f"caption; it steps aside while a line below shows): "
                    f"\"{titles[0]['text']}\"")
    for o in items:
        if o["kind"] == "title":
            continue
        rows.append(f"- {o['at']:.1f}s for {o['secs']:.1f}s ON-SCREEN "
                    f"{o['kind'].upper()}: \"{o['text']}\"")
    return ("ADDED BY THE EDIT (exactly what the cut shows/says beyond the "
            "transcript; frames may miss a short overlay). Judge whether "
            "these words are right, not that the caption stays up — that "
            "is the format:\n"
            + "\n".join(rows) + "\n")


def review_rough_cut(edl: dict, transcript_lines: str, sheet: str | None,
                     duration_s: float,
                     on_screen: list[dict] | None = None) -> dict:
    """§18 narrative review of the assembled rough cut. Fails CLOSED on
    brain unreachability (publish=False, score -1): the story format's
    primary risk is incoherence, so an UNREVIEWED story must not ship.

    When a contact sheet of the rough cut exists, the critic is given the
    Read grant (reviewer #8) so it actually SEES the assembled frames —
    a text-only critic cannot judge whether the picture matches the beat,
    which is exactly what a rough-cut review is for. And when a sheet exists
    the verdict is required to come from the vision model (reviewer #11):
    the text-only Groq fallback must not be able to publish a rough cut it
    never looked at, so a sheet + no vision model = fail closed."""
    have_sheet = bool(sheet)
    user = (f"PREMISE: {edl.get('premise')}\n"
            f"CENTRAL QUESTION: {edl.get('central_question')}\n"
            f"STRUCTURE: {edl.get('structure')}\n"
            f"DURATION: {duration_s:.1f}s\n"
            f"EDL: " + str([{k: b[k] for k in
                             ('source_id', 'start', 'end', 'role',
                              'purpose', 'context_overlay')}
                            for b in edl.get('beats', [])]) + "\n"
            + (f"Contact sheet image (sampled frames of the ASSEMBLED rough "
               f"cut, timestamped labels) — read this image file: {sheet}\n"
               if have_sheet else "")
            + _fmt_on_screen(on_screen)
            + f"FINAL TRANSCRIPT:\n{transcript_lines[:3000]}")
    out = _brain(user, _REVIEW_SYSTEM, read_files=have_sheet,
                 require_vision=have_sheet,
                 image_path=str(sheet) if have_sheet else None)
    if not out:
        # FAIL CLOSED for stories (reviewer #9): the story format's primary
        # risk is incoherence, so an UNREVIEWED story must not publish — the
        # caller abandons it and the slot falls back to a normal clip. (This
        # is the opposite of the single-clip vision QA, which fails open.)
        return {"publish": False, "story_score": -1, "problems": []}
    problems = []
    for p in (out.get("problems") or [])[:8]:
        try:
            problems.append({"type": str(p.get("type", "other"))[:24],
                             "at": float(p.get("at", 0)),
                             "fix": str(p.get("fix", ""))[:200]})
        except (TypeError, ValueError):
            continue
    summary = scrub_text(str(out.get("stranger_summary") or "").strip())[:240]
    try:
        payoff_at = (None if out.get("payoff_at") is None
                     else float(out.get("payoff_at")))
    except (TypeError, ValueError):
        payoff_at = None
    publish = bool(out.get("publish", False))
    # NO PAYOFF, NO STORY. Code may only ADD blocks: a critic that says
    # publish but cannot name the second the story pays off — or retell it
    # in a sentence — has described a cut that runs out, which is what the
    # 2026-10-05 Cinna story did ("your comfy" / "not I'm not") at 74.
    if publish and (payoff_at is None or not summary):
        publish = False
        problems.append({"type": "weak_payoff",
                         "at": max(0.0, float(duration_s) - 1.0),
                         "fix": "No moment answers the question the opening "
                                "raised. End on the reveal or the reaction "
                                "to the consequence, not where the clip "
                                "runs out."})
    return {"publish": publish,
            "story_score": int(out.get("story_score", 0) or 0),
            "stranger_summary": summary, "payoff_at": payoff_at,
            "problems": problems}


def revalidate(edl: dict, reports: list[dict]) -> dict | None:
    """A stored EDL (clip_memory.kept_edit) put back through the same laws
    against today's reports — the sources may have changed, the laws may
    have grown. None when it no longer holds."""
    if not isinstance(edl, dict):
        return None
    prev = {k: v for k, v in edl.items() if k != "narration_lines"}
    if narration_lines(edl):
        prev["narration"] = narration_lines(edl)
    prev["is_story"] = True
    rs: list = []
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    out = validate_edl(prev, durations, _windows(reports), reasons=rs,
                       positions=_positions(reports), words=_words(reports))
    out = _ground(out, reports, rs)
    if not out:
        print(f"[story] kept edit no longer holds: {'; '.join(rs)[:200]}",
              flush=True)
    return out


def locate(at: float, cut_beats: list[dict]) -> dict | None:
    """Map an OUTPUT second (the critic's clock) to the beat that plays it
    and the SOURCE second the EDL uses. `cut_beats` is `render_story`'s
    `beats` (each with `beat`, `source_id`, `start`, `out_start`,
    `out_end`). A second inside a replay or past the end maps to the
    nearest beat before it. None when nothing is known."""
    best = None
    for b in cut_beats or []:
        try:
            o0, o1 = float(b["out_start"]), float(b["out_end"])
        except (KeyError, TypeError, ValueError):
            continue
        if o0 <= at:
            best = (b, min(at, o1))
    if not best:
        return None
    b, t = best
    return {"beat": b.get("beat"), "source_id": b.get("source_id"),
            "source_s": round(float(b["start"]) + t - float(b["out_start"]),
                              1)}


def _cut_map(cut: dict) -> str:
    """What the rendered cut actually holds, beat by beat, in the SOURCE
    seconds the EDL is written in — the reviser edits what it can see."""
    words = cut.get("final_words") or []
    out = []
    for b in cut.get("beats") or []:
        try:
            o0, o1 = float(b["out_start"]), float(b["out_end"])
            s0 = float(b["start"])
        except (KeyError, TypeError, ValueError):
            continue
        mine = [{"w": w["w"], "s": w["s"] - o0 + s0, "e": w["e"] - o0 + s0}
                for w in words if o0 <= w["s"] < o1]
        lines = []
        if mine:
            cur = [mine[0]]
            for w in mine[1:]:
                if w["s"] - cur[-1]["e"] >= 1.2:
                    lines.append(cur)
                    cur = [w]
                else:
                    cur.append(w)
            lines.append(cur)
        said = "\n".join(
            f"    [{ln[0]['s']:.1f}-{ln[-1]['e']:.1f}] "
            + " ".join(w["w"] for w in ln) for ln in lines) or "    (no speech)"
        out.append(f"  beat {b.get('beat')} ({b.get('role', '')}) "
                   f"source {b.get('source_id')} "
                   f"{s0:.1f}-{float(b['end']):.1f}s = output "
                   f"{o0:.1f}-{o1:.1f}s:\n{said}")
    return "\n".join(out)


def _where(p: dict, cut: dict | None) -> str:
    loc = locate(float(p["at"]), (cut or {}).get("beats") or [])
    if not loc:
        return ""
    return (f" (= beat {loc['beat']}, source {loc['source_id']} at "
            f"{loc['source_s']:.1f}s)")


def revise_edl(edl: dict, problems: list[dict],
               reports: list[dict], cut: dict | None = None) -> dict | None:
    """§19: one constrained revision (the caller loops up to
    `story_revisions`). May add narration lines (one per beat at most)
    when the critic names missing context; a line the sources do not support is dropped
    (`narration_grounded`). Returns a re-validated EDL or None (caller then
    abandons the story to the clip fallback)."""
    if not problems:
        return None
    # shown in the format the brain writes: `narration` is the LIST
    prev = {k: v for k, v in edl.items() if k != "narration_lines"}
    if narration_lines(edl):
        prev["narration"] = narration_lines(edl)
    user = ("YOUR PREVIOUS EDL:\n" + str(prev) + "\n\n"
            "CRITIC PROBLEMS (timestamped on the OUTPUT clock"
            + (", each mapped to YOUR beat and source second" if cut else "")
            + "):\n"
            + "\n".join(f"- at {p['at']:.1f}s{_where(p, cut)} "
                        f"[{p['type']}]: {p['fix']}"
                        for p in problems)
            # THE CUT THE CRITIC WATCHED, in source seconds. The critic says
            # "@63.0s repetition"; the EDL is written in each source's own
            # seconds; with three beats and a hook between them the reviser
            # was guessing which line the critic meant. Backtest 6 repaired
            # the same "are you hacked" repetition three times without
            # removing it (62 -> 68 -> 71).
            + ("\n\nTHE CUT THE CRITIC WATCHED (what each beat holds, in "
               "source seconds):\n" + _cut_map(cut) if cut else "")
            # THE WHOLE REPORTS, as the director planned from. `[:4000]` cut
            # every source's transcript but the first: on 2026-10-03 the
            # critic asked for "Kai stating the accusation" at the opening
            # and the reviser could not see the line it was asked to use —
            # the cut scored 58, 46, 58 and was dropped.
            + "\n\nSCENE REPORTS (the same ones you planned from):\n"
            + _fmt_reports(reports))
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    # A REVISION THE LAWS REFUSE GETS TOLD WHY, ONCE. It used to come back
    # None and end the story with "after 0 revision(s)" and nothing logged:
    # the 2026-10-07 backtest dropped a 66 (Ludwig's archery-lane intruder)
    # and a 70 (Sodapoppin's machine) that way, both with problems a trim
    # and an overlay fix. Same validation, same laws — the reviser just
    # hears what it broke.
    for attempt in range(2):
        out = _brain(user, _REVISE_SYSTEM)
        rs: list = []
        edl2 = validate_edl(out or {}, durations, _windows(reports),
                            reasons=rs, positions=_positions(reports),
                            words=_words(reports))
        edl2 = _ground(edl2, reports, rs)
        for r in rs:
            if r.startswith("narration dropped") or not edl2:
                print(f"[story] revision: {r}", flush=True)
        if edl2 or not out:
            return edl2
        user += ("\n\nYOUR REVISION WAS REJECTED by the edit laws: "
                 + "; ".join(rs)[:1200]
                 + "\nReturn the complete EDL again, fixing that and still "
                   "fixing the critic's problems.")
    return None
