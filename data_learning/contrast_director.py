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

# CURATED breather clips. Footage search ranks by TITLE keywords, which can't tell
# "Earth seen from the ISS" from "astronauts inside the ISS" — so a contrast cut
# PINS a known-good NASA clip by id instead of searching. A small, reliable
# library beats an unreliable search for the one real shot per video.
KNOWN_GOOD = {
    "earth": {"nasa_id": "NHQ_2020_1221_Earth Views", "ss": 40.0},
    "sun":   {"nasa_id": "GSFC_20170623_Sun_m12240_ChromosphereFlare", "ss": 2.0},
    "moon":  {"nasa_id": "GSFC_20200622_moon_m13098", "ss": 1.0},
}
_FAMILY_KEYS = (
    ("sun", "sun"), ("solar", "sun"), ("moon", "moon"),
    ("galaxy", "earth"), ("planet", "earth"), ("earth", "earth"),
    ("ground", "earth"), ("orbit", "earth"),
)

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


def _family_key(beat: dict) -> str:
    """The curated footage family for a beat, or '' if none fits. Returning '' is
    important: on a topic with no good real footage (time, the body, an abstract
    idea) we must NOT force an off-topic Earth clip — the run just stays all
    animation, which is the honest answer for a footage-poor subject."""
    low = f"{beat.get('narration', '')} " \
          f"{(beat.get('flat') or {}).get('label', '')}".lower()
    for key, fam in _FAMILY_KEYS:
        if key in low:
            return fam
    return ""


def _to_footage(beat: dict) -> None:
    """Turn an animation beat into a real-world cut, PINNING a curated known-good
    clip by id. Title-keyword search kept grabbing off-topic clips (a rocket on a
    truck, ISS interiors) because it can't tell 'Earth from the ISS' from 'people
    inside the ISS'. A small reliable library beats an unreliable search for the
    one real shot per video. Keeps the beat's number as an annotation on the
    footage; a number-less beat becomes a pure establishing breather. Falls back to
    a relevance-gated search only when no curated clip exists for the theme."""
    num = (beat.get("flat") or {}).get("text")
    numlabel = (beat.get("flat") or {}).get("label", "")
    numsub = (beat.get("flat") or {}).get("sub", "")
    fam = _family_key(beat)
    pin = KNOWN_GOOD.get(fam)
    beat.pop("flat", None)
    beat.pop("_force_motion", None)
    beat.pop("subject", None)
    beat["mode"] = "footage"
    beat["_contrast_cut"] = True
    if pin:
        beat["footage"] = {"nasa_id": pin["nasa_id"], "ss": pin["ss"],
                           "push": 1.08, "direction": "in",
                           "intent": f"a real filmed {fam} shot — the breather"}
    else:
        subj = _DEFAULT_SUBJECT
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
            # only cut real footage in if this topic HAS a good real shot; on a
            # footage-poor subject (time, the body, an idea) leave it all-animation.
            if pick is not None and _family_key(beats[pick]) in KNOWN_GOOD:
                _to_footage(beats[pick])
        i = j
    return beats
