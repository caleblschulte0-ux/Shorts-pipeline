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

LEAD, TAIL, MIN_SHOT = 0.45, 0.9, 2.8
MAX_UNCHANGED = 7.0        # default: a visual may not hold longer than this
DEV_PHASE = 2.6           # silent development tail when a beat splits


def _beat_seconds(dur: float) -> float:
    return max(MIN_SHOT, LEAD + dur + TAIL) if dur else 4.0


def plan_story(beats: list[dict], durs: list[float]) -> list[dict]:
    """beats + their narration durations -> a phased shot list. Each shot is a
    pro_render shot dict with `seconds`; the narration `line` rides only the
    first phase of a beat (later phases are silent visual development)."""
    shots: list[dict] = []
    n = len(beats)
    for bi, (b, dur) in enumerate(zip(beats, durs)):
        secs = _beat_seconds(dur)
        maxu = float(b.get("max_unchanged", MAX_UNCHANGED))
        line = b.get("narration", "")
        is_last = bi == n - 1
        foot = b.get("footage")

        # ---- pure designed-2D beat (orbit, galaxy, comparison, title) -------
        if b.get("flat"):
            sh = dict(b["flat"])
            # a long comparison must not carry the whole beat: cap it, then let
            # a footage development phase (if provided) finish the idea.
            if sh["kind"] == "flat_compare" and secs > maxu and foot:
                shots.append({**sh, "seconds": maxu - 0.4, "line": line})
                shots.append(_footage(foot, secs - (maxu - 0.4), b,
                                      phase="development"))
            else:
                shots.append({**sh, "seconds": secs, "line": line})
            continue

        # ---- number beat: the value rides MOVING footage (not a static card).
        # The number arrives as it is spoken; if the beat runs long, the number
        # lands and then the FOOTAGE keeps developing (enforces max_unchanged).
        if b.get("number"):
            num = b["number"]
            if foot:
                if secs > maxu and not is_last:
                    shots.append({"kind": "footage_number", **_foot(foot),
                                  **num, "seconds": maxu, "line": line,
                                  "intent": foot.get("intent")})
                    shots.append(_dev(foot, secs - maxu))
                else:
                    shots.append({"kind": "footage_number", **_foot(foot),
                                  **num, "seconds": secs, "line": line,
                                  "intent": foot.get("intent")})
            else:
                shots.append({"kind": "flat_number", **num, "seconds": secs,
                              "line": line})
            continue

        # ---- text beat: thesis / annotation OVER footage, never on black ----
        if b.get("text"):
            role = b.get("text_role", "thesis")
            if foot:
                if secs > maxu and not is_last:
                    shots.append({"kind": "footage_text", **_foot(foot),
                                  "text": b["text"], "text_role": role,
                                  "seconds": maxu, "line": line,
                                  "intent": foot.get("intent")})
                    shots.append(_dev(foot, secs - maxu))
                else:
                    shots.append({"kind": "footage_text", **_foot(foot),
                                  "text": b["text"], "text_role": role,
                                  "seconds": secs, "line": line,
                                  "intent": foot.get("intent")})
            else:
                # no footage available -> a designed statement card is the
                # honest fallback (declared, not a media-search miss)
                shots.append({"kind": "flat_statement", "statement": b["text"],
                              "seconds": secs, "line": line})
            continue

        # ---- plain footage beat: one shot, or setup+development if long -----
        if foot:
            if secs > maxu and not is_last:
                shots.append(_footage(foot, secs - DEV_PHASE, b,
                                      phase="setup", line=line))
                # development phase: a push/pull the other direction so the
                # frame keeps evolving instead of holding (real development,
                # not the same static plate).
                dev = _foot(foot)
                dev["direction"] = "out" if foot.get("direction") != "out" \
                    else "in"
                dev["at"] = min(1.0, float(foot.get("at", 0.5)) + 0.18)
                shots.append({"kind": "footage", **dev, "seconds": DEV_PHASE,
                              "intent": foot.get("intent")})
            else:
                shots.append(_footage(foot, secs, b, line=line))
            continue

        # nothing declared -> a titled statement so the render never stalls
        shots.append({"kind": "flat_statement",
                      "statement": b.get("understand", line),
                      "seconds": secs, "line": line})
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
