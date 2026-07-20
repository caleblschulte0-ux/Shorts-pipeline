#!/usr/bin/env python3
"""THE CONTRAST director — change the MEDIUM so it doesn't feel like one long
animation.

The variety gate (no_dull_beats) catches beats that LOOK alike. This catches a
subtler, worse thing: beats that are the same KIND of thing. Four animated space
diagrams back to back — a spinning globe, an orbit, a number, a galaxy — each
looks different, yet the video is still "another animation, another animation,
another animation." The owner's words: *"we just showed the Earth spin four
different ways — do something DIFFERENT here."*

So this director enforces MEDIUM variety. After a run of animations it cuts in a
real-world breather — a VIDEO (preferred) or a PHOTO — for texture and contrast.
Footage returns here as a deliberate, occasional cut, NOT the default: the video
breathes, the animation stretch doesn't overstay, and the real shot lands with
impact BECAUSE the eye has been watching drawings.

Rule of thumb: no more than MAX_ANIM_RUN animations in a row without a real cut.

    from data_learning import contrast_director
    contrast_director.contrast_pass(beats)   # mutates beats in place
"""
from __future__ import annotations

MAX_ANIM_RUN = 3          # animations in a row before a real-world cut is forced

# derive a filmable subject for the breather from the beat's own words, so the
# real cut is ABOUT the beat, not a random stock clip.
_SUBJECT_HINTS = (
    ("sun", "the sun in ultra hd from space"),
    ("solar", "the sun in ultra hd from space"),
    ("galaxy", "the milky way galaxy night sky timelapse"),
    ("moon", "the moon in ultra hd"),
    ("ocean", "ocean waves from above"),
    ("storm", "a hurricane from space"),
    ("planet", "planet earth from the international space station"),
    ("earth", "planet earth from the international space station"),
    ("ground", "planet earth from the international space station"),
    ("orbit", "planet earth from the international space station"),
)
_DEFAULT_SUBJECT = "planet earth from the international space station"


def _is_anim(beat: dict) -> bool:
    return beat.get("mode") == "designed_2d" or bool(beat.get("flat"))


def _subject_for(beat: dict) -> str:
    text = f"{beat.get('narration','')} {(beat.get('flat') or {}).get('label','')}"
    low = text.lower()
    for key, subj in _SUBJECT_HINTS:
        if key in low:
            return subj
    return _DEFAULT_SUBJECT


def _to_footage(beat: dict) -> None:
    """Turn an animation beat into a real-world cut. Keep its number as an
    annotation ON the footage (footage+annotation) so the fact still lands; a beat
    with no number becomes a pure establishing breather."""
    num = (beat.get("flat") or {}).get("text")
    numlabel = (beat.get("flat") or {}).get("label", "")
    numsub = (beat.get("flat") or {}).get("sub", "")
    subj = _subject_for(beat)
    beat.pop("flat", None)
    beat["mode"] = "footage"
    beat["_contrast_cut"] = True
    # route through motion-first so the clip is RELEVANCE-GATED and lands on a
    # DYNAMIC window — a plain footage fetch grabbed an off-topic clip (a rocket on
    # a truck) because it doesn't rank by relevance; motion-first does.
    beat["_force_motion"] = True
    beat["subject"] = subj
    beat["footage"] = {"intent": subj, "subject": subj, "push": 1.08,
                       "direction": "in"}
    if num:
        beat["number"] = {"text": num, "sub": numsub or "MPH",
                          "label": numlabel or ""}


def contrast_pass(beats: list[dict], max_run: int = MAX_ANIM_RUN) -> list[dict]:
    """Break every run of > max_run consecutive animations with a real cut. Prefers
    to convert a TRANSITIONAL beat (one carrying no number — an establishing /
    'pull back and watch' beat) so a key number-explainer is never lost; falls back
    to the beat that lands right at the run limit. HOOK and PAYOFF bookends are
    never converted (the opening and its callback are deliberate). Returns the
    (mutated) beats."""
    n = len(beats)
    i = 0
    while i < n:
        if not _is_anim(beats[i]):
            i += 1
            continue
        j = i
        while j < n and _is_anim(beats[j]):
            j += 1
        run = list(range(i, j))                      # [i, j) is one animation run
        if len(run) > max_run:
            # candidates inside the run, excluding the bookend jobs
            inner = [k for k in run
                     if str(beats[k].get("job", "")).upper()
                     not in {"HOOK", "PAYOFF", "ENDING", "COLD_OPEN"}]
            # prefer a transitional beat (no number) near the run limit
            transitional = [k for k in inner
                            if not (beats[k].get("flat") or {}).get("text")]
            pick = None
            if transitional:
                pick = min(transitional, key=lambda k: abs(k - (i + max_run)))
            elif inner:
                pick = inner[min(max_run, len(inner) - 1)]
            if pick is not None:
                _to_footage(beats[pick])
        i = j
    return beats
