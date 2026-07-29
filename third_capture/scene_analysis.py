#!/usr/bin/env python3
"""Multimodal scene analysis — what is actually IN a source clip.

STORY_DIRECTOR_PLAYBOOK §7: transcripts alone are insufficient, and a
40-word snip is worse. Before the story director may plan anything, every
candidate source gets a structured scene report built from:

- the COMPLETE timestamped transcript (whisper words, content-cached),
- sampled frames (the same labeled contact sheet the QA gate uses),
- and source metadata.

The report carries people, a one-line summary, dialogue beats (who speaks,
to what purpose), visual beats, emotional states, MISSING context (the VOD
expansion trigger), and candidate keep-windows. The full transcript stays
attached — the director reads it all, never a summary of a summary.

Contract: `analyze_source()` returns a report dict or None, never raises.
Vision is best-effort (Claude CLI when available); without it the report
degrades to transcript-only via the Groq brain, and `visual_beats` stays
empty rather than invented.
"""
from __future__ import annotations


import subprocess
from pathlib import Path

from third_capture import clip_edit, clip_qa
from third_capture.author import _call_claude, _call_groq

REPO = Path(__file__).resolve().parent.parent

_SCENE_SYSTEM = """You are a scene analyst for a streamer-clip story
system. You are given a clip's metadata, its COMPLETE timestamped
transcript, and (when present) a contact sheet image path of sampled
frames — read that image file if a path is given.

Report ONLY what is observably in the source. Never invent people, causes,
or events. If something is unknown, list it under missing_context.

Return STRICT JSON:
{"people": [str, ...],            // who appears/speaks (names or roles)
 "location": str,                  // "" if unclear
 "summary": str,                   // one sentence, observable facts only
 "dialogue_beats": [{"start": s, "end": s, "speaker": str,
                     "purpose": str}, ...],
 "visual_beats": [{"start": s, "end": s, "event": str}, ...],
 "emotional_state": [str, ...],
 "opens_mid_sentence": bool,       // clip starts inside a thought/action
 "payoff_shown": bool,             // the consequence/reaction is visible
 "missing_context": [str, ...],    // what a stranger cannot know from this
 "candidate_windows": [{"start": s, "end": s, "purpose": str}, ...]}

Times are seconds into THIS clip. visual_beats only from frames you were
actually shown; with no frames return visual_beats: []."""


def _dialogue_lines(words: list[dict]) -> str:
    """The full transcript as timestamped lines, split on >=1.2s pauses —
    the director reads every word, not a snip."""
    if not words:
        return "(no speech)"
    lines, cur = [], [words[0]]
    for w in words[1:]:
        if w["s"] - cur[-1]["e"] >= 1.2:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    lines.append(cur)
    return "\n".join(
        f"[{seg[0]['s']:.1f}-{seg[-1]['e']:.1f}] "
        + " ".join(w["w"] for w in seg) for seg in lines)


def analyze_source(video: Path, meta: dict, work: Path, *,
                   whisper_model: str = "small") -> dict | None:
    """Full scene report for one source clip. `meta` carries at least
    title/channel/source_url. Returns the report (with `transcript_lines`
    and `words` attached for the director) or None."""
    try:
        video = Path(video)
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        try:
            dur = float(subprocess.check_output(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", str(video)],
                text=True, timeout=30).strip() or 0)
        except Exception:  # noqa: BLE001
            dur = 0.0
        words = clip_edit.transcribe_words(video, whisper_model)
        tlines = _dialogue_lines(words)
        sheet = work / f"{video.stem}.scene.jpg"
        have_sheet = clip_qa.contact_sheet(video, sheet) is not None

        user = (f"Clip: title={str(meta.get('title', ''))[:90]!r} "
                f"streamer={meta.get('channel') or meta.get('streamer', '?')} "
                f"duration={dur:.1f}s\n"
                + (f"Contact sheet image (12 frames, timestamped labels): "
                   f"{sheet}\n" if have_sheet else "No frames available.\n")
                + f"FULL TRANSCRIPT (timestamped):\n{tlines}")
        # VISION PROVENANCE (reviewer #1): a text-only model can never see
        # the frames, so visual_beats are trustworthy ONLY when a
        # vision-capable model (Claude WITH the Read grant) actually
        # inspected the contact sheet. Track which model answered; the Groq
        # fallback is text-only and its visual_beats are DISCARDED, so the
        # module's "visual events are never invented" promise holds.
        out = None
        vision_ok = False
        if have_sheet:
            try:
                out = _call_claude(user, system=_SCENE_SYSTEM,
                                   read_files=True)
                if out is not None:
                    vision_ok = True     # Claude saw the frames
            except Exception as e:  # noqa: BLE001
                print(f"::warning::[scene] claude vision failed ({e}) — "
                      "groq (text-only, no visual_beats)", flush=True)
        if out is None:
            try:
                out = _call_groq(user, system=_SCENE_SYSTEM)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::[scene] groq failed ({e})", flush=True)
        if not out:
            return None

        def _beats(key, fields):
            res = []
            for b in (out.get(key) or [])[:12]:
                try:
                    item = {"start": max(0.0, float(b["start"])),
                            "end": min(dur or 1e9, float(b["end"]))}
                    for f in fields:
                        item[f] = str(b.get(f, ""))[:80]
                    if item["end"] > item["start"]:
                        res.append(item)
                except (TypeError, ValueError, KeyError):
                    continue
            return res

        return {
            "source_id": meta.get("source_url") or meta.get("url", ""),
            "title": str(meta.get("title", ""))[:120],
            "channel": str(meta.get("channel")
                           or meta.get("streamer", "")),
            "duration_s": round(dur, 1),
            "people": [str(p)[:40] for p in (out.get("people") or [])][:8],
            "location": str(out.get("location", ""))[:60],
            "summary": str(out.get("summary", ""))[:200],
            "dialogue_beats": _beats("dialogue_beats",
                                     ("speaker", "purpose")),
            # only a model that ACTUALLY SAW the frames may contribute
            # visual beats — a text-only fallback's "visual" claims are
            # invented and discarded
            "visual_beats": (_beats("visual_beats", ("event",))
                             if vision_ok else []),
            "vision_ok": vision_ok,
            "emotional_state": [str(e)[:30] for e in
                                (out.get("emotional_state") or [])][:5],
            "opens_mid_sentence": bool(out.get("opens_mid_sentence")),
            "payoff_shown": bool(out.get("payoff_shown", True)),
            "missing_context": [str(m)[:100] for m in
                                (out.get("missing_context") or [])][:6],
            "candidate_windows": _beats("candidate_windows", ("purpose",)),
            # keep the WHOLE transcript (reviewer #3): a VOD-expanded window
            # can be 2-3 min, and the later reaction/resolution the system
            # expanded to FIND must not be truncated away. 16k chars covers
            # a ~3-min clip's timestamped lines with headroom.
            "transcript_lines": tlines[:16000],
            "words": words,
            "path": str(video),
        }
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[scene] analysis failed "
              f"({type(e).__name__}: {e})", flush=True)
        return None
