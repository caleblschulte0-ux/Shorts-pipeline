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

from third_capture.author import _call_claude, _call_groq, scrub_text

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

Be stricter about coherence than cosmetics. Return STRICT JSON:
{"publish": true|false, "story_score": 0-100,
 "problems": [{"type": "missing_context|repetition|weak_payoff|confusing|
               misleading|pacing|other",
               "at": <seconds>, "fix": "<specific instruction>"}, ...]}"""

_REVISE_SYSTEM = """You are the story director revising your own edit ONCE
based on the critic's timestamped problems. You may only: adjust cut
boundaries, remove a repetitive segment, extend a reaction, add/remove a
context overlay, change a transition, or remove an effect. You may NOT add
new sources or invent context. Return the COMPLETE corrected EDL in the
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
        out.append(
            f"SOURCE {r['source_id']}\n"
            f"  streamer={r['channel']} dur={r['duration_s']}s "
            f"date={r.get('date', '?')}\n"
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


def validate_edl(edl: dict, durations: dict[str, float],
                 windows: dict[str, list] | None = None) -> dict | None:
    """Hard-validate a director EDL against the playbook's NARRATIVE laws,
    not just syntax (reviewer #8). Returns the cleaned EDL or None.
    `durations` maps source_id -> clip length; `windows` maps source_id ->
    [(start,end)] evidence windows (dialogue/visual/candidate beats) so a
    cut can be required to land on something that actually happens."""
    windows = windows or {}
    try:
        if not edl or not edl.get("is_story"):
            return None
        structure = str(edl.get("structure", ""))
        if structure not in STRUCTURES:
            return None
        premise = str(edl.get("premise", "")).strip()
        central_q = str(edl.get("central_question", "")).strip()
        payoffish = [b for b in (edl.get("beats") or [])
                     if str(b.get("role")) in ("payoff", "climax")]
        if not premise or not central_q or not payoffish:
            return None          # §8: premise + question + payoff required
        # hook must be a real 3-7 word curiosity line
        hook_raw = scrub_text(str(edl.get("hook_overlay", "")).strip())
        if not (3 <= len(hook_raw.split()) <= 7):
            return None
        beats = []
        n_punch = n_replay = n_overlay = 0
        for b in (edl.get("beats") or [])[:MAX_BEATS]:
            sid = str(b.get("source_id", ""))
            dur = durations.get(sid)
            if dur is None:
                return None      # director referenced an unknown source
            s = max(0.0, float(b.get("start", 0)))
            e = min(float(dur), float(b.get("end", 0)))
            if e - s < 1.5:
                return None      # sub-1.5s segments are noise, not beats
            # the cut must land on something that actually happens — a
            # dialogue/visual/candidate window in that source (skipped only
            # when analysis produced no windows for it, to avoid over-reject)
            w = windows.get(sid)
            if w and not _overlaps(s, e, w):
                return None
            role = str(b.get("role", ""))
            if role not in ROLES:
                return None
            purpose = str(b.get("purpose", "")).strip()
            if not purpose:
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
        if len(beats) < 2:
            return None
        if n_overlay > max(0, len(beats) - 1):
            return None          # an overlay on every beat = decoration
        # §8/§20: the story must END on its payoff — not trail off on a
        # context/setup beat (reviewer #8: "could validate while ending on
        # an irrelevant context beat")
        if beats[-1]["role"] not in ("payoff", "climax", "reaction"):
            return None
        # first beat must fit the chosen structure: a cold_open / mystery
        # opens on the strong moment; the timeline structures open on setup
        first_role = beats[0]["role"]
        if structure in ("cold_open", "mystery_reveal"):
            if first_role not in ("climax", "payoff", "reaction"):
                return None
        elif structure in ("chronological", "escalation", "before_after"):
            if first_role not in ("setup", "context", "escalation"):
                return None
        # §14 narration: optional, justified, verified-voice only. Key is
        # `over_beat` (reviewer #10) — narration is DUCKED OVER that beat,
        # which is what the renderer does; `after_beat` still read for compat
        narration = None
        n_in = edl.get("narration")
        if isinstance(n_in, dict):
            text = scrub_text(str(n_in.get("text", "")).strip())[:90]
            why = str(n_in.get("essential_because", "")).strip()
            over = int(n_in.get("over_beat",
                                n_in.get("after_beat", -1)) or -1)
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
           read_files: bool = False, require_vision: bool = False) -> dict | None:
    """The director's model call. `read_files=True` grants Claude the Read
    tool so it can actually OPEN a contact-sheet image referenced in `user`
    — without it the critic is blind to the rendered frames and can only
    reason about text. The Groq fallback is always text-only.

    `require_vision=True` means the answer is only trustworthy if a
    vision-capable model produced it: Claude (with the Read grant) is the
    ONLY vision backend, so if it doesn't answer we return None instead of
    falling through to text-only Groq. Without this, a rough-cut critic that
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
    if require_vision:
        print("::warning::[director] a VISION verdict was required but claude "
              "(the only vision backend) was unavailable — refusing the "
              "text-only groq fallback (fail closed)", flush=True)
        return None
    try:
        out = _call_groq(user, system=system)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[director] groq failed ({e})", flush=True)
    return out


def plan_story(reports: list[dict], event: dict | None = None,
               guidance: str = "") -> dict | None:
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
    user += "SCENE REPORTS:\n" + _fmt_reports(reports)
    out = _brain(user, _PLAN_SYSTEM)
    if not out or not out.get("is_story"):
        return None
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    return validate_edl(out, durations, _windows(reports))


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
                 require_vision=have_sheet)
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
    return {"publish": bool(out.get("publish", False)),
            "story_score": int(out.get("story_score", 0) or 0),
            "problems": problems}


def revise_edl(edl: dict, problems: list[dict],
               reports: list[dict]) -> dict | None:
    """§19: exactly ONE constrained revision. Returns a re-validated EDL
    or None (caller then abandons the story to the clip fallback)."""
    if not problems:
        return None
    user = ("YOUR PREVIOUS EDL:\n" + str(edl) + "\n\n"
            "CRITIC PROBLEMS (timestamped):\n"
            + "\n".join(f"- at {p['at']:.1f}s [{p['type']}]: {p['fix']}"
                        for p in problems)
            + "\n\nSCENE REPORTS (for reference):\n"
            + _fmt_reports(reports)[:4000])
    out = _brain(user, _REVISE_SYSTEM)
    durations = {r["source_id"]: float(r.get("duration_s") or 0)
                 for r in reports}
    return validate_edl(out or {}, durations, _windows(reports))
