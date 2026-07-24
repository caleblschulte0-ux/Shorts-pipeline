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
- effects: a GLOBAL budget — at most 1 replay, at most 2 subtle_punch;
  spend emphasis on the payoff, not the first beat. Usually [].

Return STRICT JSON:
{"is_story": true,
 "premise": str, "central_question": str, "ending_emotion": str,
 "structure": "<one of the six>", "structure_reason": str,
 "title": str, "hook_overlay": str,          // 3-7 words, over opening
 "target_duration": int,                      // seconds, 25-90
 "beats": [{"source_id": str, "start": s, "end": s,
            "role": "setup|escalation|climax|payoff|context|reaction",
            "purpose": str, "transition": "hard_cut",
            "context_overlay": str,
            "effects": [{"type": "subtle_punch", "at": s}, ...]}, ...],
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
            f"  transcript:\n{r.get('transcript_lines', '')[:1500]}")
    return "\n\n".join(out)


def validate_edl(edl: dict, durations: dict[str, float]) -> dict | None:
    """Hard-validate a director EDL against the playbook's laws. Returns
    the cleaned EDL or None. `durations` maps source_id -> clip length."""
    try:
        if not edl or not edl.get("is_story"):
            return None
        structure = str(edl.get("structure", ""))
        if structure not in STRUCTURES:
            return None
        premise = str(edl.get("premise", "")).strip()
        payoffish = [b for b in (edl.get("beats") or [])
                     if str(b.get("role")) in ("payoff", "climax")]
        if not premise or not payoffish:
            return None          # §8: no stated premise/payoff = no story
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
                    effects.append({"type": ft})
            beats.append({"source_id": sid, "start": round(s, 2),
                          "end": round(e, 2), "role": role,
                          "purpose": purpose[:120],
                          "transition": "hard_cut",
                          "context_overlay": overlay,
                          "effects": effects})
        if len(beats) < 2:
            return None
        if n_overlay > max(0, len(beats) - 1):
            return None          # an overlay on every beat = decoration
        hook = scrub_text(str(edl.get("hook_overlay", "")).strip())[:60]
        end = edl.get("ending") or {}
        hold = min(2.0, max(0.0, float(end.get("duration", 1.0) or 1.0)))
        return {
            "is_story": True,
            "premise": premise[:200],
            "central_question": str(edl.get("central_question", ""))[:150],
            "ending_emotion": str(edl.get("ending_emotion", ""))[:40],
            "structure": structure,
            "structure_reason": str(edl.get("structure_reason", ""))[:200],
            "title": str(edl.get("title", "")).strip()[:95],
            "hook_overlay": hook.upper(),
            "target_duration": int(edl.get("target_duration", 45) or 45),
            "beats": beats,
            "ending": {"type": "reaction_hold", "duration": hold},
        }
    except (TypeError, ValueError, KeyError):
        return None


def _brain(user: str, system: str) -> dict | None:
    out = None
    try:
        out = _call_claude(user, system=system)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[director] claude failed ({e}) — groq",
              flush=True)
    if out is None:
        try:
            out = _call_groq(user, system=system)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[director] groq failed ({e})", flush=True)
    return out


def plan_story(reports: list[dict], event: dict | None = None) -> dict | None:
    """Eligibility gate + structure choice + full story EDL, validated.
    None = not a story / director unreachable / plan invalid."""
    if len(reports) < 2:
        return None
    user = ""
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
    return validate_edl(out, durations)


def review_rough_cut(edl: dict, transcript_lines: str, sheet: str | None,
                     duration_s: float) -> dict:
    """§18 narrative review of the assembled rough cut. Fails OPEN on
    brain unreachability (publish=True, score -1) — the mechanical QA
    still stands behind it; the critic exists to catch incoherence, not to
    become a new way to lose stories."""
    user = (f"PREMISE: {edl.get('premise')}\n"
            f"CENTRAL QUESTION: {edl.get('central_question')}\n"
            f"STRUCTURE: {edl.get('structure')}\n"
            f"DURATION: {duration_s:.1f}s\n"
            f"EDL: " + str([{k: b[k] for k in
                             ('source_id', 'start', 'end', 'role',
                              'purpose', 'context_overlay')}
                            for b in edl.get('beats', [])]) + "\n"
            + (f"Contact sheet: {sheet}\n" if sheet else "")
            + f"FINAL TRANSCRIPT:\n{transcript_lines[:3000]}")
    out = _brain(user, _REVIEW_SYSTEM)
    if not out:
        return {"publish": True, "story_score": -1, "problems": []}
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
    return validate_edl(out or {}, durations)
