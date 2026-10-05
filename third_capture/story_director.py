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

import re

from third_capture.author import (_call_claude, _call_gemini_vision,
                                  _call_text_fallback, scrub_text)

STRUCTURES = {"chronological", "cold_open", "mystery_reveal",
              "two_perspectives", "escalation", "before_after"}
ROLES = {"setup", "escalation", "climax", "payoff", "context", "reaction"}
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


def _ground(edl: dict | None, reports: list[dict], rs: list) -> dict | None:
    """Drop a narration line the footage does not support — the cut stays,
    the invented sentence goes."""
    if edl and edl.get("narration") and \
            not narration_grounded(edl["narration"].get("text", ""), reports):
        rs.append("narration dropped — not grounded in the sources: "
                  f"{edl['narration'].get('text', '')!r}")
        edl = dict(edl)
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

Then emit the COMPLETE timeline. Segment rules:
- exact start/end seconds INTO THE NAMED SOURCE, chosen from its dialogue/
  visual beats: enter just before the new information, leave after the
  line lands and the reaction completes (never clip the last half-second
  of a laugh/stunned silence)
- every segment states its narrative purpose; a segment adding no
  information, emotion, escalation, or payoff must not exist
- remove repetition across sources (same explanation twice = cut one)
- context_overlay: 2-6 words over the FOOTAGE only when the viewer would
  otherwise be confused (time jump, new speaker, new place) — e.g.
  "EARLIER THAT DAY", "THEN HIS FRIEND RESPONDED". NEVER meta-labels like
  "IT GETS WORSE" or "PART TWO". "" when the cut is already obvious.
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
- narration: OPTIONAL top-level {"text": <=15 words, "over_beat": idx,
  "essential_because": str} — spoken OVER that beat (ducked). ONLY when
  essential context cannot be
  shown by footage + a short overlay. Verified facts only, never
  motives, never drama ("Two days later, he finally responded." — good;
  "He was furious and planning revenge." — forbidden). Usually omit.

Return STRICT JSON:
{"is_story": true,
 "premise": str, "central_question": str, "ending_emotion": str,
 "structure": "<one of the six>", "structure_reason": str,
 "title": str, "hook_overlay": str,          // 3-7 words, over opening
 "target_duration": int,                      // seconds, 25-90
 "beats": [{"source_id": str, "start": s, "end": s,
            "role": "setup|escalation|climax|payoff|context|reaction",
            "purpose": str,
            "transition": "hard_cut|j_cut|l_cut",
            "framing": "wide|tight",
            "context_overlay": str,
            "effects": [{"type": "subtle_punch", "at": s}, ...]}, ...],
 "narration": {"text": str, "over_beat": int,
               "essential_because": str} | omitted,
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

Return STRICT JSON, best story first, at most 3:
{"stories": [{"members": ["C3", "C9", "C14"],
              "premise": "<one sentence: who, what changed>",
              "why_connected": "<why these clips are one story>",
              "shape": "one_stream|multi_stream|multi_streamer"}]}
Return {"stories": []} when the catalogue holds no real story."""


def scout_stories(lines: list[str], ids: set[str],
                  max_stories: int = 3,
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
context overlay, change a transition, remove an effect — and, ONLY when the
critic names missing_context, add or rewrite the ONE narration line.

Narration ({"text", "over_beat", "essential_because"}): at most 15 words,
spoken over the beat that needs it (usually beat 0, to set up the story).
It may state ONLY what a source's transcript or scene report states —
who someone is, what they said happened, what was claimed — in the
footage's own words where possible. Never motive, never feelings, never
drama, never anything the sources do not say. `essential_because` names
the source line it comes from. A line not supported by the sources is
removed automatically, so do not guess. If the missing context is not in
the sources at all, fix what you can with cuts instead.

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
        out.append(
            f"SOURCE {r['source_id']}\n"
            f"  streamer={r['channel']} dur={r['duration_s']}s "
            f"date={r.get('date', '?')}{at}\n"
            f"  summary: {r['summary']}\n"
            f"  people: {', '.join(r.get('people', []))}\n"
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


def validate_edl(edl: dict, durations: dict[str, float],
                 windows: dict[str, list] | None = None,
                 reasons: list | None = None,
                 positions: dict | None = None) -> dict | None:
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
            hook_raw = " ".join(_hw[:7])
            rs.append(f"hook trimmed {len(_hw)}->7 words (repaired)")
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
            role = str(b.get("role", ""))
            if role not in ROLES:
                rs.append(f"unknown beat role {role!r}")
                return None
            purpose = str(b.get("purpose", "")).strip()
            if not purpose:
                rs.append(f"beat {sid} states no purpose")
                return None      # §10: every segment states its purpose
            overlay = scrub_text(
                str(b.get("context_overlay", "")).strip())[:40].upper()
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
        narration = None
        n_in = edl.get("narration")
        if isinstance(n_in, dict):
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
                    and len(text.split()) <= 15
                    and not _BAD_NARRATION.search(text)):
                narration = {"text": text, "over_beat": over,
                             "essential_because": why[:120]}
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
            "hook_overlay": hook_raw[:60].upper(),
            "target_duration": target,
            "beats": beats,
            "narration": narration,
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


def plan_story(reports: list[dict], event: dict | None = None,
               guidance: str = "", hypothesis: str = "") -> dict | None:
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
    out = _brain(user, _PLAN_SYSTEM)
    rs: list = []
    if out is None:
        rs.append("director unreachable")
        _LAST_REJECTION.clear()
        _LAST_REJECTION.update(why="; ".join(rs), editorial=False)
        return None
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    edl = validate_edl(out, durations, _windows(reports), reasons=rs,
                       positions=_positions(reports))
    # the director's own narration meets the same floor as the reviser's
    edl = _ground(edl, reports, rs)
    # `editorial` separates "a human editor would also say no" from "the
    # plan was malformed" — the second is OUR bug and needs a code fix, and
    # for a month both were logged as "no genuine arc".
    _LAST_REJECTION.clear()
    _LAST_REJECTION.update(
        why="; ".join(rs) or ("accepted" if edl else "rejected, no reason"),
        editorial=any("not a story" in r for r in rs))
    return edl


def review_rough_cut(edl: dict, transcript_lines: str, sheet: str | None,
                     duration_s: float) -> dict:
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


def revise_edl(edl: dict, problems: list[dict],
               reports: list[dict]) -> dict | None:
    """§19: one constrained revision (the caller loops up to
    `story_revisions`). May add ONE narration line when the critic names
    missing context; a line the sources do not support is dropped
    (`narration_grounded`). Returns a re-validated EDL or None (caller then
    abandons the story to the clip fallback)."""
    if not problems:
        return None
    user = ("YOUR PREVIOUS EDL:\n" + str(edl) + "\n\n"
            "CRITIC PROBLEMS (timestamped):\n"
            + "\n".join(f"- at {p['at']:.1f}s [{p['type']}]: {p['fix']}"
                        for p in problems)
            # THE WHOLE REPORTS, as the director planned from. `[:4000]` cut
            # every source's transcript but the first: on 2026-10-03 the
            # critic asked for "Kai stating the accusation" at the opening
            # and the reviser could not see the line it was asked to use —
            # the cut scored 58, 46, 58 and was dropped.
            + "\n\nSCENE REPORTS (the same ones you planned from):\n"
            + _fmt_reports(reports))
    out = _brain(user, _REVISE_SYSTEM)
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    rs: list = []
    edl2 = validate_edl(out or {}, durations, _windows(reports), reasons=rs,
                        positions=_positions(reports))
    edl2 = _ground(edl2, reports, rs)
    for r in rs:
        if r.startswith("narration dropped"):
            print(f"[story] revision: {r}", flush=True)
    return edl2
