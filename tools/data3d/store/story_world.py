"""STORY AND WORLD FIRST (caaleb, 2026-11-19, of the 3D shorts: "You're so used to making these 2D videos. We're going
beat by beat ... you just realize you're much more writing a story now. Building a world that the viewer has to believe
in. And you're just being very, very lazy about it.")

A 2D explainer can cut from one picture to the next because each beat is a picture of a number. A 3D short is a world
the viewer has to buy, and every 3D short so far was planned the 2D way: a list of beats, a set per beat, Data dropped
into each one with no reason to be there, nothing carried from one beat to the next. So a 3D story now starts with its
WORLD, in script.json, before any beat:

  world.logline     the story in one sentence: who wants what, and what stands in the way
  world.hero        who Data IS in this story (a role, and what he wears or carries that says so)
  world.goal        what he is trying to do across the whole short
  world.place       ONE world the sets belong to (a park, a town, a ship), described as a place, not a list
  world.time        when (and how it moves on through the short)
  world.weather     the light and weather, and how it changes
  world.path        the sets in story order: his route through the world (== script.json sets)
  world.continuity  {thing: why}: what persists from beat to beat because the STORY carries it (his costume, his goal
                    seen early and reached late, the storm). Each must appear in at least two beats' storyboard lines.
                    A continuity thing is not a lazy reuse: store/variety.py lets it recur without spending the callback.

The beats are then moments of that one story: each storyboard line names the hero by his role. The judge is told the
logline and the hero, and fails a shot whose place does not look like a real part of that world (store/judge3d.py).
Binds every short not in fresh.BEFORE.
"""
import re

import fresh

NEED = ("logline", "hero", "goal", "place", "time", "weather", "path", "continuity")
CONTINUITY_MAX = 5
MIN_WORDS = 6            # a field this short is a label, not a world


def held(story):
    return fresh.held(story)


def role(world):
    """the hero's role word: 'Data as the park's ranger: ...' -> 'ranger'"""
    h = str(world.get("hero", "")).lower()
    m = re.search(r"\bas (?:the |a |an |his |her )?(?:[\w']+'s )?([a-z][\w\s-]*?)\s*(?:[:,;(]|$)", h)
    return m.group(1).split()[-1] if m and m.group(1).split() else ""


def _named(thing, text):
    """a continuity thing appears in a beat when its last word (or its whole name) does: 'ranger hat' -> 'hat'"""
    words = thing.lower().replace("_", " ").split()
    return bool(words) and (thing.lower().replace("_", " ") in text or re.search(rf"\b{re.escape(words[-1])}s?\b", text))


def continuity(script):
    return {str(k).lower().replace("_", " "): v for k, v in ((script.get("world") or {}).get("continuity") or {}).items()}


def problems(story, script):
    if not held(story): return []
    w = script.get("world")
    if not isinstance(w, dict):
        return [("world", "plan the WORLD before the beats: script.json needs a `world` block (" + ", ".join(NEED) + ")")]
    out = []
    for k in NEED:
        if not w.get(k):
            out.append(("world", f"world.{k} is missing"))
    for k in ("logline", "hero", "goal", "place"):
        if w.get(k) and len(str(w[k]).split()) < MIN_WORDS:
            out.append(("world", f"world.{k} is a label ({w[k]!r}); write it as a sentence"))
    if w.get("path") and list(w["path"]) != list(script.get("sets") or []):
        out.append(("world", f"world.path {w['path']} is not the beats' sets {script.get('sets')}: the sets are his route"))
    cont = continuity(script)
    if len(cont) > CONTINUITY_MAX:
        out.append(("world", f"{len(cont)} continuity things; at most {CONTINUITY_MAX}: the rest is built for its beat"))
    texts = [str(b).lower() for b in script.get("storyboard") or []]
    for thing, why in cont.items():
        if not str(why).strip():
            out.append(("world", f"continuity {thing!r}: say why the story carries it"))
        n = sum(1 for t in texts if _named(thing, t))
        if n < 2:
            out.append(("world", f"continuity {thing!r} is in {n} beat(s): a thing the story carries is seen in at least two"))
    r = role(w)
    if not r:
        out.append(("world", "world.hero must say who Data is: 'Data as the <role>: ...'"))
    else:
        for i, t in enumerate(texts, 1):
            if not re.search(rf"\b{re.escape(r)}s?\b", t) and not re.search(r"\b(he|his|him)\b", t):
                out.append((f"storyboard beat {i}", f"the beat never involves the {r}: every beat is a moment of his story"))
    return out
