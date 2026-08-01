#!/usr/bin/env python3
"""THE BEAT INTENT PLANNER (PRO_DOCTRINE — the story-to-visual director).

The renderer is the execution layer. THIS is the intelligence: it turns declared
BEAT INTENTS into a sequence of phased SHOTS, so an idea DEVELOPS across several
visuals instead of one card held until the narration ends. It enforces the laws
the editorial judge measures:

  - a beat longer than its max_unchanged develops (setup -> development phases),
    never one static card (kills SHOT_TOO_LONG / STATIC_NUMBER_CARD);
  - numbers and text render OVER footage when footage fits the beat
    (kills TEXT_AS_FALLBACK, FOOTAGE_GRAPHICS_DISCONNECTED, and puts the payoff
    line ON the strongest image — kills PAYOFF_SPLIT_FROM_IMAGE);
  - the hook and every footage beat carry a shot INTENT (the narrative job), so
    footage is chosen for purpose, not keyword (kills TOPICAL_BUT_NOT_EDITORIAL —
    the authoring/selection layer honors `footage.intent`);
  - the payoff beat lands the line on the strongest image and nothing weaker
    follows it (kills POST_CLIMAX_DOWNGRADE).

A BEAT (pro_stories/<slug>.beats.json):
  {"job":"HOOK", "narration":"...", "understand":"...", "subject":"...",
   "function":"experience", "mode":"footage",
   "footage":{"nasa_id":"...","ss":..,"intent":"calm ordinary Earth, apparent stillness"},
   "number":{"text":"1,670","sub":"km/h","label":"the earth's spin"},   # number beats
   "text":"You have never been still.",                                 # text beats
   "text_role":"thesis|annotation|none", "max_unchanged":7.0,
   "flat":{"kind":"flat_orbit",...}}                                    # pure-2D beats

plan_story() returns a flat list of SHOTS (the pro_render shot dicts) with an
explicit `seconds` and a `line` only on the phase that carries the narration.
"""
from __future__ import annotations

from data_learning import textmatch

LEAD, TAIL, MIN_SHOT = 0.45, 0.9, 2.8
MAX_UNCHANGED = 4.5        # default: a visual may not hold longer than this
DEV_PHASE = 2.6           # silent development tail when a beat splits

# The card-to-character repair (`_prefer_scene`, from a judge finding of
# CARDS_OVER_BUDGET / NO_CHARACTER / INFOGRAPHIC_REEL) needs somewhere to put the
# beat. These are a figure doing an ordinary human thing. The money-world scenes
# (paycheck, tax, rent, grocery, subs, savings) are excluded: they are correct
# only for a film about money, and an automated repair must not import a topic
# the story never had.
NEUTRAL_SCENES = ("scene_free", "scene_hold", "scene_walkout", "scene_queue",
                  "scene_work", "scene_screen", "scene_sleep")

# This list used to be called TOPIC-AGNOSTIC, "carrying no subject
# presupposition". That was never true, and believing it cost a whole render.
# Read their own defaults: free="YEARS ARE YOURS", hold="DAYS ON HOLD",
# queue="MONTHS IN LINE", work="YEARS AT WORK", screen="YEARS ON A SCREEN",
# sleep="YEARS ASLEEP", walkout="STOP WAITING" — this is ONE film's scene
# library (the where-your-life-goes piece), and `NEUTRAL_SCENES[(bi + k) % 7]`
# rotated it onto whatever beat happened to land on each index.
#
# On the 2026-08-01 shared-air render that put walkout_scene — a payoff about
# leaving a waiting room, staged as a dim room with a bright doorway — under the
# line "the air arriving in your lungs did not come from your room, it came from
# everywhere". The blind judge read the doorway as "a dashboard plate, a
# template with the content not filled in" and labelled the film
# EMPTY_COMPOSITION + UI_WIDGET. It was neither: it was a specific scene about
# a subject this film never had.
#
# So a scene is chosen for what it DEPICTS: each entry lists the words whose
# presence in the beat's own narration makes that staging honest, and a domain
# word must SPECIFICALLY license its staging. Weak ones ("people",
# "hours", "each") match almost any narration and put us back where we started,
# and the 5-char stem makes near-misses collide — "everyone" in the queue domain
# matched "everywhere" in the air line and nearly re-staged the same waiting
# room this whole change exists to stop. When in doubt, leave the word out: a
# miss falls back to the staging-neutral pool, which is the safe direction.
SCENE_DOMAIN = {
    "scene_hold": "wait waiting waited hold holding held delay delayed "
                  "stuck stalled paused",
    # NOT bare "line" or "turn": "a line of text", "a coastline", "it turns
    # out" would all stage a queue. A domain word has to mean the thing.
    "scene_queue": "queue queues queuing crowd crowds crowded lineup "
                   "waiting",
    "scene_walkout": "leave leaving escape exit exits door doorway "
                     "outside walked release",
    "scene_work": "work working worked job jobs labour labor office "
                  "desk shift career",
    "scene_screen": "screen screens phone scroll scrolling digital "
                    "online feed device",
    "scene_sleep": "sleep sleeping asleep bed bedroom dream dreaming "
                   "awake night",
    "scene_free": "open free air sky world everywhere anywhere breathe "
                  "move moving alone stand",
}

# What a beat gets when its words license nothing. NOT a single scene: six
# unmatched beats all staged identically is SAMENESS, which is its own reject
# label — the fix for one defect must not manufacture another.
#
# These three are the staging-neutral ones: a figure in open space, a figure in
# a room that dims, a row of figures. They read as "a person, somewhere" and
# carry no claim. The four left out do: walkout is a bright doorway PAYOFF,
# work is a desk, screen is a glowing monitor, sleep is a starry bedroom. Those
# only appear when the beat actually asks for them.
#
# Even these three are compromises — scene_free still carries a sunrise mood.
# A genuinely generic staging library does not exist yet; building one is the
# real fix. Until then this picks among the least wrong, instead of dealing a
# specific scene off the top of the deck.
GENERIC_STAGINGS = ("scene_free", "scene_hold", "scene_queue")


def _scene_for(bi: int, k: int, line: str) -> str:
    """The designed scene whose subject the beat's own words support.

    Rotation is kept — but only among scenes the line licenses, or among the
    staging-neutral ones when it licenses none. Either way a long beat still
    changes staging between phases, without importing a subject the story never
    had.
    """
    fit = [s for s in NEUTRAL_SCENES
           if textmatch.shares(line, SCENE_DOMAIN.get(s, ""))] \
        if str(line).strip() else []
    pool = fit or GENERIC_STAGINGS
    return pool[(bi + k) % len(pool)]


def _phase_lengths(secs: float, maxu: float) -> list[float]:
    """Split a beat into phases none longer than max_unchanged.

    A footage beat already develops across phases; a DESIGNED beat did not — it
    emitted one shot for its whole duration, so a 9.5s scene was 9.5s of one
    picture. That is measured directly as dead time (the novelty gate reported a
    STALE 114.5-124.0s span on exactly such a beat) and it is the largest single
    contributor to a film's dead fraction.

    Phases are equal so the cut lands on a rhythm rather than leaving a runt
    tail, and the count is reduced rather than emitting anything under MIN_SHOT:
    two long-ish shots read better than three stutters."""
    if secs <= maxu:
        return [secs]
    n = max(2, int(-(-secs // maxu)))          # ceil
    while n > 2 and secs / n < MIN_SHOT:
        n -= 1
    return [secs / n] * n


def _scene_phases(bi: int, secs: float, maxu: float, *, line: str = "",
                  number: str = "", label: str = "", mood=None) -> list[dict]:
    """A designed/character beat as a SEQUENCE. Each phase moves the same figure
    to a different situation — rotating only among the scenes the beat's own
    words license (`_scene_for`) — so a long beat keeps introducing something new
    without importing a subject the story never had. The narration rides only the
    first phase; the rest are silent visual development."""
    out = []
    for k, dur in enumerate(_phase_lengths(secs, maxu)):
        sh = {"kind": _scene_for(bi, k, line),
              "seconds": dur, "number": number, "label": label, "mood": mood}
        if k == 0 and line:
            sh["line"] = line
        out.append(sh)
    return out


def _beat_seconds(dur: float) -> float:
    return max(MIN_SHOT, LEAD + dur + TAIL) if dur else 4.0


def plan_story(beats: list[dict], durs: list[float]) -> list[dict]:
    """beats + their narration durations -> a phased shot list. Each shot is a
    pro_render shot dict with `seconds`; the narration `line` rides only the
    first phase of a beat (later phases are silent visual development)."""
    shots: list[dict] = []
    n = len(beats)

    def emit(sh: dict) -> None:
        """append a shot, tagged with the BEAT it came from so the assembler
        can emit a real beat->time map (the editorial package measures the
        render's true boundaries, not a hand-estimated guess)."""
        sh = dict(sh)
        sh["_beat"] = bi
        shots.append(sh)

    for bi, (b, dur) in enumerate(zip(beats, durs)):
        secs = _beat_seconds(dur)
        maxu = float(b.get("max_unchanged", MAX_UNCHANGED))
        line = b.get("narration", "")
        is_last = bi == n - 1
        foot = b.get("footage")

        # NO DULL BEATS — auto-repair escalation. When the dullness director has
        # marked a beat `_force_motion` (its designed/still treatment scored dull),
        # override it: land the beat's text/number ON motion of the subject
        # (motion-first at render, still fallback). A dull flat card becomes a
        # moving shot. See scripts/no_dull_beats.py.
        subj = _motion_subject(b, b.get("image") or {})
        if b.get("_force_motion") and subj:
            txt = b.get("text") or (b.get("number") or {}).get("label", "")
            role = b.get("text_role", "annotation")
            img = b.get("image") or {"query": subj, "perspective":
                                     b.get("perspective", "")}
            emit(_depict(b, img, secs, subj, text=txt, text_role=role,
                         line=line))
            continue

        # CARD -> CHARACTER. The judges measured the stat-plate look dominating
        # the film; the repair converts an offending card into a scene of a
        # person, which is the only treatment that adds a human to the frame.
        # Applies ONLY where nothing filmable would be destroyed: a card beat, or
        # a beat with no image/footage of its own. A footage beat keeps its
        # footage — swapping real material for a drawing is never the fix.
        if b.get("_prefer_scene") and (b.get("flat") or
                                       not (b.get("image") or b.get("footage"))):
            # rotate by beat index so converting several cards does not just
            # trade a repeated card for a repeated scene
            num = b.get("number") or {}
            for sh in _scene_phases(bi, secs, maxu, line=line,
                                    number=num.get("text", ""),
                                    label=num.get("label", "") or b.get("text", ""),
                                    mood=(b.get("flat") or {}).get("mood")):
                emit(sh)
            continue

        # ---- pure designed-2D beat (orbit, galaxy, comparison, title) —
        # only when NO number/text rides it (those route to composite below).
        if b.get("flat") and not b.get("number") and not b.get("text"):
            sh = dict(b["flat"])
            # a long comparison must not carry the whole beat: cap it, then let
            # a footage development phase (if provided) finish the idea.
            if sh["kind"] == "flat_compare" and secs > maxu and foot:
                emit({**sh, "seconds": maxu - 0.4, "line": line})
                emit(_footage(foot, secs - (maxu - 0.4), b,
                                      phase="development"))
            elif secs > maxu:
                # A DESIGNED BEAT MAY NOT HOLD ONE PICTURE PAST max_unchanged.
                # Play the authored card for its allowance, then DEVELOP: real
                # footage when the beat offered any, otherwise character scenes,
                # which both break the hold and put a person on screen — the
                # direction the taste judge asks for anyway.
                emit({**sh, "seconds": maxu - 0.4, "line": line})
                rest = secs - (maxu - 0.4)
                if foot:
                    emit(_footage(foot, rest, b, phase="development"))
                else:
                    for ph in _scene_phases(bi + 1, rest, maxu):
                        emit(ph)
            else:
                emit({**sh, "seconds": secs, "line": line})
            continue

        # ---- number beat: the value rides MOVING footage (not a static card).
        # The number arrives as it is spoken; if the beat runs long, the number
        # lands and then the FOOTAGE keeps developing (enforces max_unchanged).
        if b.get("number"):
            num = b["number"]
            if b.get("_prefer_designed") and not b.get("flat"):
                # VARIETY: the director flagged this footage-number beat a visual
                # look-alike of an earlier clip. Land the number on a DESIGNED card
                # (an animated count-up) instead of yet another near-identical shot
                # — breaks the monotony AND adds an animation we want more of.
                emit({"kind": "flat_number", **num, "seconds": secs, "line": line})
                continue
            if b.get("flat"):
                # the subject can't be filmed (tier C: the galaxy) -> the
                # number rides the DESIGNED base, a distinct image that escapes
                # the footage ladder.
                emit({"kind": "composite", "base": b["flat"], **num,
                              "seconds": secs, "line": line})
            elif foot:
                if secs > maxu and not is_last:
                    emit({"kind": "footage_number", **_foot(foot),
                                  **num, "seconds": maxu, "line": line,
                                  "intent": foot.get("intent")})
                    emit(_dev(foot, secs - maxu))
                else:
                    emit({"kind": "footage_number", **_foot(foot),
                                  **num, "seconds": secs, "line": line,
                                  "intent": foot.get("intent")})
            else:
                emit({"kind": "flat_number", **num, "seconds": secs,
                              "line": line})
            continue

        img = b.get("image")

        # VARIETY — the dullness director flagged this beat a visual look-alike of
        # an earlier one (the '5 clouds' monotony). Re-render it as a DESIGNED
        # number/statement card instead of yet another near-identical clip: it
        # breaks the repetition AND adds one of the animated number graphics we
        # want more of. Only fires when the beat carries a number/text to build on.
        if b.get("_prefer_designed"):
            num = b.get("number") or {}
            if num.get("text"):
                emit({"kind": "flat_number", "text": num["text"],
                      "sub": num.get("sub", ""),
                      "label": num.get("label", "") or line, "seconds": secs})
                continue
            if b.get("text"):
                emit({"kind": "flat_statement", "statement": b["text"],
                      "seconds": secs})
                continue

        # ---- text beat: thesis / annotation OVER footage or a real PHOTO,
        # never on black ----
        if b.get("text"):
            role = b.get("text_role", "thesis")
            if b.get("flat"):
                emit({"kind": "composite", "base": b["flat"],
                              "text": b["text"], "text_role": role,
                              "seconds": secs, "line": line})
            elif img:
                # MOTION-FIRST: a DEPICTION beat that declared a still is probed
                # for a moving clip of the same subject at render (motion beats a
                # still of the same thing). The still rides along as the fallback.
                subject = _motion_eligible(b, img)
                if subject:
                    if secs > maxu and not is_last:
                        emit(_depict(b, img, maxu, subject, text=b["text"],
                                     text_role=role, line=line))
                        emit(_img_dev(img, secs - maxu))
                    else:
                        emit(_depict(b, img, secs, subject, text=b["text"],
                                     text_role=role, line=line))
                # a ground-truth / human-scale PHOTO carries the point footage
                # can't (the perspective director's consequence shot). The line
                # lands ON the photo; a long beat keeps the Ken Burns move alive.
                elif secs > maxu and not is_last:
                    emit({"kind": "image_text", **_img(img),
                                  "text": b["text"], "text_role": role,
                                  "seconds": maxu, "line": line})
                    emit(_img_dev(img, secs - maxu))
                else:
                    emit({"kind": "image_text", **_img(img),
                                  "text": b["text"], "text_role": role,
                                  "seconds": secs, "line": line})
            elif foot:
                if secs > maxu and not is_last:
                    emit({"kind": "footage_text", **_foot(foot),
                                  "text": b["text"], "text_role": role,
                                  "seconds": maxu, "line": line,
                                  "intent": foot.get("intent")})
                    emit(_dev(foot, secs - maxu))
                else:
                    emit({"kind": "footage_text", **_foot(foot),
                                  "text": b["text"], "text_role": role,
                                  "seconds": secs, "line": line,
                                  "intent": foot.get("intent")})
            else:
                # no footage available -> a designed statement card is the
                # honest fallback (declared, not a media-search miss)
                emit({"kind": "flat_statement", "statement": b["text"],
                              "seconds": secs, "line": line})
            continue

        # ---- plain image beat: a real PHOTO as the beat, Ken-Burns'd. A long
        # image beat splits into several moves (each a different pan/push) so a
        # still never freezes into a slideshow.
        if img:
            # MOTION-FIRST: probe a moving version of the subject; a single
            # depict shot resolves to a clip (or the still fallback) at render.
            subject = _motion_eligible(b, img)
            if subject:
                # A DEPICTION BEAT IS STILL A BEAT. This emitted ONE shot for the
                # beat's whole length — so a 9s beat was a single held picture,
                # and when motion-first missed, 9s of one frozen still. The
                # text+image path above already splits at max_unchanged; a beat
                # carrying narration alone got no such treatment, which is why
                # 15 of 20 beats rendered over the limit and half the film
                # measured dead. Same law for both: play the depiction for its
                # allowance, then keep developing.
                if secs > maxu and not is_last:
                    emit(_depict(b, img, maxu, subject, line=line))
                    for sh in _chunk_image(img, secs - maxu, maxu):
                        emit(sh)
                else:
                    emit(_depict(b, img, secs, subject, line=line))
                continue
            for k, sh in enumerate(_chunk_image(img, secs, maxu)):
                if k == 0 and line:
                    sh["line"] = line
                emit(sh)
            continue

        # ---- plain footage beat: CHUNK a long beat into several short shots,
        # each capped at max_unchanged and each jumping to a DIFFERENT window /
        # framing of the clip, so the picture keeps changing instead of one slow
        # 10-second drift (the interest judge's dead stretch). The narration
        # line rides the first chunk; the rest are silent visual development.
        if foot:
            for k, sh in enumerate(_chunk_footage(foot, secs, maxu, b)):
                if k == 0 and line:
                    sh["line"] = line
                emit(sh)
            continue

        # nothing declared -> a titled statement so the render never stalls
        emit({"kind": "flat_statement",
                      "statement": b.get("understand", line),
                      "seconds": secs, "line": line})
    return shots


def _chunk_footage(foot: dict, secs: float, maxu: float,
                   beat: dict) -> list[dict]:
    """Split `secs` of a footage beat into ceil(secs/maxu) short shots. Each
    chunk steps its window (`ss` forward, `at` across) and alternates push
    direction, so consecutive chunks look DIFFERENT — the picture keeps changing
    instead of one long slow drift. A short beat stays a single shot."""
    import math
    n = max(1, math.ceil(secs / maxu)) if secs > maxu + 0.4 else 1
    if n == 1:
        return [_footage(foot, secs, beat)]
    each = secs / n
    base_ss = foot.get("ss")
    base_at = float(foot.get("at", 0.5))
    base_dir = foot.get("direction", "in")
    shots = []
    for k in range(n):
        f = dict(foot)
        # walk deeper into the clip so each chunk shows a new part of the shot
        if base_ss is not None:
            f["ss"] = float(base_ss) + k * (each + 0.6)
        f["at"] = min(0.92, base_at + k * 0.12)
        f["direction"] = base_dir if k % 2 == 0 else \
            ("out" if base_dir != "out" else "in")
        sh = {"kind": "footage", **_foot(f), "seconds": each,
              "intent": foot.get("intent")}
        if k:
            sh["phase"] = "development"
        shots.append(sh)
    return shots


def _motion_subject(beat: dict, image: dict) -> str:
    """What to search MOVING footage of, for a depiction beat that declared a
    still. Prefer an explicit motion query, then the image's own search query,
    then the beat's SUBJECT (the schema's 'what this beat is about') — never the
    narration prose, which is a sentence, not a search."""
    for q in (image.get("motion_query"), beat.get("motion_query"),
              image.get("query"), beat.get("subject")):
        if q:
            return str(q)
    return ""


def _motion_eligible(beat: dict, image: dict) -> str | None:
    """MOTION-FIRST LAW gate (authoring side): should this still be PROBED for a
    moving version? Returns the subject query to probe with, or None to keep the
    still as authored. A still is kept as-is only when:
      - the beat EXPLAINS rather than DEPICTS (a chart/diagram/map — function
        other than 'experience'), or
      - the author pinned `still: true` (a specific document/photo a clip can't
        replace), or
      - there is no subject to search motion with.
    Every other still-declared DEPICTION is motion-first: we look for a clip and
    only fall back to the still if none clears the bar (resolved at render)."""
    if image.get("still") or beat.get("still"):
        return None
    if str(beat.get("function", "experience")).lower() != "experience":
        return None
    return _motion_subject(beat, image) or None


def _depict(beat: dict, image: dict, secs: float, subject: str,
            *, text: str = "", text_role: str = "", line: str = "",
            phase: str = "") -> dict:
    """A DEPICTION shot: 'show this subject, motion-first'. The renderer resolves
    it — a moving clip of the subject if one clears the bar, else the declared
    still (carried here as the fallback). Text rides whichever wins."""
    sh: dict = {"kind": "depict_text" if text else "depict",
                "motion_query": subject, "seconds": secs, **_img(image)}
    if image.get("perspective"):
        sh["perspective"] = image["perspective"]
    # A media repair on this beat travels to the selection gate as a reseed, so
    # the re-render steps past the clip the judges rejected instead of re-picking
    # it (the candidate order is otherwise deterministic).
    if beat.get("_media_reseed"):
        sh["reseed"] = int(beat["_media_reseed"])
    if text:
        sh["text"], sh["text_role"] = text, text_role or "thesis"
    if line:
        sh["line"] = line
    if phase:
        sh["phase"] = phase
    return sh


def _img(image: dict) -> dict:
    """The image-source fields a shot needs, from a beat's image block. Either a
    pinned ``url`` (+ optional credit) or a ``query`` the gateway resolves to the
    highest-appeal commercial photo, plus Ken-Burns controls."""
    out: dict = {}
    if image.get("url"):
        out["image_url"] = image["url"]
        for k in ("source", "license", "attribution", "title"):
            if image.get(k) is not None:
                out["image_" + k] = image[k]
    if image.get("query"):
        out["image_query"] = image["query"]
    if image.get("asset"):                    # pinned generated asset
        out["exchange_asset"] = image["asset"]  # (exchange_media id)
    for k in ("perspective", "push", "direction", "pan", "min_appeal",
              "must_match"):
        if image.get(k) is not None:
            out[k] = image[k]
    return out


def _img_dev(image: dict, seconds: float) -> dict:
    """A silent image DEVELOPMENT phase: same photo, pan/push flipped so the
    second half of a long image beat reframes instead of holding."""
    d = _img(image)
    d["direction"] = "out" if image.get("direction") != "out" else "in"
    d["pan"] = "left" if image.get("pan") != "left" else "right"
    return {"kind": "image", **d, "seconds": max(1.6, seconds),
            "phase": "development"}


IMG_HOLD = 3.6        # a photo is a BRIEF noun cutaway, not a held slideshow


def _chunk_image(image: dict, secs: float, maxu: float) -> list[dict]:
    """A photo illustrates a NOUN, briefly — never a single still zoomed in and
    out for the whole beat. A long image beat CUTS between the beat's distinct
    noun images (`image.queries`: extra subjects named in the narration), a new
    one every ~IMG_HOLD seconds, with a gentle drift (not a weird aggressive
    zoom). If only one subject is given, the beat is capped short and holds once
    rather than re-zooming to pad the runtime."""
    import math
    hold = min(maxu, IMG_HOLD)
    # the subjects to cut between: the main query + any extra nouns the beat lists
    variants = [image.get("query")] + list(image.get("queries") or [])
    variants = [v for v in variants if v] or [image.get("query")]
    if secs <= hold + 0.4 or len(variants) == 1:
        # one subject: a single GENTLE hold covering the beat — no re-zoom padding.
        # (A long beat should carry multiple nouns to cut between; see `queries`.)
        im = dict(image)
        im.setdefault("push", 1.10)
        return [{"kind": "image", **_img(im), "seconds": secs}]
    n = min(len(variants), max(2, math.ceil(secs / hold)))
    each = secs / n
    pans = ["auto", "right", "left", "up", "down"]
    shots = []
    for k in range(n):
        im = dict(image)
        im["query"] = variants[k % len(variants)]   # CUT to a DIFFERENT noun
        im.pop("url", None)                          # extra nouns resolve by query
        im["pan"] = pans[k % len(pans)]
        im["push"] = 1.10                            # gentle drift, not a zoom
        sh = {"kind": "image", **_img(im), "seconds": each}
        if k:
            sh["phase"] = "development"
        shots.append(sh)
    return shots


def _foot(foot: dict) -> dict:
    """the footage-source fields a shot needs, from a beat's footage block."""
    out = {}
    if foot.get("nasa_id"):
        out["footage_nasa_id"] = foot["nasa_id"]
    if foot.get("query"):
        out["footage_query"] = foot["query"]
    for k in ("ss", "at", "push", "direction"):
        if foot.get(k) is not None:
            out[k] = foot[k]
    return out


def _dev(foot: dict, seconds: float) -> dict:
    """A silent footage DEVELOPMENT phase: same source, pushed the other way,
    so after a number/text lands the world keeps evolving instead of holding
    (enforces max_unchanged for composited beats)."""
    d = _foot(foot)
    d["direction"] = "out" if foot.get("direction") != "out" else "in"
    d["at"] = min(1.0, float(foot.get("at", 0.5)) + 0.2)
    return {"kind": "footage", **d, "seconds": max(1.6, seconds),
            "intent": foot.get("intent"), "phase": "development"}


def _footage(foot: dict, seconds: float, beat: dict, phase: str = "",
             line: str = "") -> dict:
    sh = {"kind": "footage", **_foot(foot), "seconds": seconds,
          "intent": foot.get("intent")}
    if line:
        sh["line"] = line
    if phase:
        sh["phase"] = phase
    return sh
