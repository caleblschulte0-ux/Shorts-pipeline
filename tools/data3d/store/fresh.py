"""EVERY VIDEO IS NEW, AND EVERY BEAT IS WORTH WATCHING (caaleb, 2026-11-19, of the rebuilt card rewards short:
"These are just dog shit, top to bottom ... what happened? We used to be making good videos. Half that was the Dr. Katz
effect. Half of them were reusing backgrounds and shit ... data pumping up a price tag. Like, that works for maybe 1
second. Like, it's not something that, like, people want to sit there and watch ... Pouring coins into a fucking jar.
That's in every single one of our videos.")

store/variety.py looks ACROSS THE BEATS of one short. Every short passed it and the channel still repeated itself,
because nothing looked ACROSS THE SHORTS: the store set opened all five of them, and coins went into a jar, a sack, a
bucket or a vault in four. This module holds three things, before a frame renders:

  history   a set, or a GAG (a family of visual idea: coins into a container, a pile growing, a balloon swelling ...),
            that any earlier short used is refused. A repeat across shorts is a callback in `callbacks` with why
            (`set:<name>` / `gag:<family>`), and caaleb's "wow, crazy one-time and forever event" is FOREVER, which is
            empty until he names one. BANNED gags are refused even as a callback: he named them.
  watch     each beat's staging carries its `arc`: at least ARC_MIN moments ({"at": fraction of the beat, "what": ...}),
            the first by ARC_FIRST, the last after ARC_LAST, none more than ARC_GAP apart, no two the same. A price tag
            swelling over three pump strokes is ONE moment said three times; a beat needs something NEW every ~2 s,
            building to its end, or the viewer has swiped by second two.
  dr_katz   the Dr. Katz look is Data parked facing the lens, waist-up or closer, while the camera sits on him: a
            picture of a character talking, not a scene. It is where the 2026-11-12/13 rules ("medium shots and
            close-ups only", "shoot the prop close and in front of Data") had driven every beat. At most TALK_MAX beats
            may be a close or medium camera, at least WORLD_MIN must show Data whole in his world, and on the
            storyboard stills (staging.framing) at most TALK_MAX shots may measure as a talking head.

Binds every short not in BEFORE (the shorts that existed when it was written; their beats are the history it reads).
"""
import json
import re
from pathlib import Path

STORIES = Path(__file__).resolve().parents[1] / "stories"
BEFORE = {"checkout", "banana", "saffron", "helium", "cardrewards"}
FOREVER = {}          # {"set:<name>" | "gag:<family>": "caaleb's words blessing it"}; nothing is, yet

# families of visual idea, matched on a beat's words (storyboard line, ideas line, Data's act, props)
GAGS = {
    "coins_into_container": r"\b(coins?|cash|notes|bills|money)\b[^.;]{0,80}\b(jar|sack|bucket|vault|bag|pot|tin|bank|slot)s?\b"
                            r"|\b(jar|sack|bucket|vault|tin)s?\b[^.;]{0,80}\b(coins?|cash|money)\b",
    "pile_grows":           r"\b(piles?|heaps?|mound|stacks? (grows?|rises?|climbs?)|towers? (grows?|rises?))\b",
    "inflate":              r"\b(balloons?|inflat\w*|pumps?|pumping|swells?|swelling)\b",
    "conveyor":             r"\b(conveyor|belt)s?\b",
    "balance":              r"\b(balances?|seesaw|scale pans?|weighing scale|tips? the scale)\b",
    "clock_spins":          r"\b(clock|calendar)s?\b",
    "coin_flip":            r"\bflips?\b[^.;]{0,40}\bcoin|\bcoin\b[^.;]{0,40}\bflips?\b",
    "shovel":               r"\bshovel\w*\b",
    "wall_of_copies":       r"\b(copies|clones?|wall of)\b",
    "dominoes":             r"\bdomino\w*\b",
    "wilts":                r"\b(wilts?|withers?|shrivels?|dies in seconds)\b",
    "lever_switch":         r"\b(levers?|track switch|switch(es)? (the|a) track)\b",
    "drains":               r"\bdrain\w*\b",
    "swallowed":            r"\bswallow\w*\b",
    "flies_away":           r"\b(rises? out of (the )?frame|floats? (up and )?away|slips? through his fingers)\b",
}
BANNED = {
    "coins_into_container": "caaleb 2026-11-19: \"Pouring coins into a fucking jar. That's in every single one of our videos.\"",
    "inflate":              "caaleb 2026-11-19: \"data pumping up a price tag. Like, that works for maybe 1 second.\"",
    "pile_grows":           "caaleb 2026-10-11: \"we kind of overuse piles ... we need to relax on the piles\"",
}

ARC_MIN, ARC_FIRST, ARC_LAST, ARC_GAP = 3, 0.3, 0.7, 0.4
TALKING = {"close", "medium"}
TALK_MAX = 1          # beats framed on Data's face and chest
WORLD_MIN = 3         # beats that show him whole in his world (any other camera kind)
TALK_H = 0.75         # measured: head-to-feet taller than this of the frame (feet cut, waist-up) ...
TALK_YAW = 40         # ... with his face within this of the lens is a talking head


def held(story):
    return bool(story) and story not in BEFORE


def _script(story):
    p = STORIES / story / "script.json"
    return json.loads(p.read_text()) if p.exists() else {}


def beat_words(script):
    """one lower-case string per beat: what the beat SHOWS, in every place a script says it"""
    n = len(script.get("lines") or [])
    sb, ideas, st = script.get("storyboard") or [], script.get("ideas") or [], script.get("staging") or []
    out = []
    for i in range(n):
        parts = [sb[i] if i < len(sb) else "", ideas[i] if i < len(ideas) else ""]
        if i < len(st) and isinstance(st[i], dict):
            parts += [st[i].get("data", ""), " ".join(map(str, st[i].get("props") or []))]
            parts += [str(m.get("what", "")) for m in st[i].get("arc") or [] if isinstance(m, dict)]
        out.append(" ".join(map(str, parts)).lower())
    return out


def gags(text):
    return {g for g, rx in GAGS.items() if re.search(rx, text.lower())}


def history(exclude):
    """{"sets": {set: [story]}, "gags": {gag: [story]}} over every other short in stories/"""
    sets, gs = {}, {}
    for d in sorted(STORIES.iterdir()):
        if not d.is_dir() or d.name == exclude or not (d / "script.json").exists(): continue
        s = _script(d.name)
        for x in set(s.get("sets") or ["store"]):   # a short with no sets was shot in the store
            sets.setdefault(x, []).append(d.name)
        for g in set().union(*(gags(w) for w in beat_words(s))) if beat_words(s) else set():
            gs.setdefault(g, []).append(d.name)
    return {"sets": sets, "gags": gs}


def history_problems(story, script):
    out = []
    cb = {str(k).lower(): v for k, v in (script.get("callbacks") or {}).items()}
    past = history(story)
    for x in sorted(set(script.get("sets") or [])):
        k = f"set:{x}"
        if x in past["sets"] and k not in cb and k not in FOREVER:
            out.append(("sets", f"the {x} set was already in {', '.join(past['sets'][x])}: build a new place"))
    for i, w in enumerate(beat_words(script), 1):
        for g in sorted(gags(w)):
            k = f"gag:{g}"
            if g in BANNED:
                out.append((f"beat {i}", f"{g.replace('_', ' ')} is banned ({BANNED[g]})"))
            elif g in past["gags"] and k not in cb and k not in FOREVER:
                out.append((f"beat {i}", f"{g.replace('_', ' ')} was already done in {', '.join(past['gags'][g])}: "
                                         f"a new idea, not the channel's old one"))
    return out


def watch_problems(script):
    out = []
    for i, b in enumerate(script.get("staging") or [], 1):
        arc = b.get("arc") if isinstance(b, dict) else None
        if not isinstance(arc, list) or len(arc) < ARC_MIN:
            out.append((f"beat {i}", f"give the beat its arc: at least {ARC_MIN} moments that each show something new "
                                     f"({{'at': 0.1, 'what': ...}}); one action said once reads in a second"))
            continue
        try:
            at = [float(m["at"]) for m in arc]
        except (KeyError, TypeError, ValueError):
            out.append((f"beat {i}", "every arc moment needs 'at' (a fraction of the beat) and 'what'")); continue
        whats = [str(m.get("what", "")).strip().lower() for m in arc]
        if at != sorted(at) or len(set(at)) < len(at):
            out.append((f"beat {i}", f"the arc's moments must come in order: {at}"))
        if at[0] > ARC_FIRST:
            out.append((f"beat {i}", f"the first thing happens at {at[0]:.2f} of the beat; start by {ARC_FIRST}"))
        if at[-1] < ARC_LAST:
            out.append((f"beat {i}", f"the last new thing happens at {at[-1]:.2f}; the beat must still be building after {ARC_LAST}"))
        gap = max((b2 - a2 for a2, b2 in zip(at, at[1:])), default=0)
        if gap > ARC_GAP:
            out.append((f"beat {i}", f"{gap:.2f} of the beat with nothing new; at most {ARC_GAP}"))
        if not all(whats) or len(set(_stem(w) for w in whats)) < len(whats):
            out.append((f"beat {i}", "each arc moment is a DIFFERENT thing happening, not the same stroke again"))
    return out


def _stem(what):
    """'third stroke: the tag swells more' and 'first stroke: the tag swells' are one moment: compare without counts"""
    w = re.sub(r"\b(first|second|third|fourth|again|more|bigger|another|one|two|three|four|1st|2nd|3rd|\d+)\b", " ", what)
    return " ".join(w.split())


def dr_katz_problems(script):
    st = [b for b in script.get("staging") or [] if isinstance(b, dict)]
    cams = [b.get("camera") for b in st]
    talk = [i for i, c in enumerate(cams, 1) if c in TALKING]
    out = []
    if len(talk) > TALK_MAX:
        out.append(("staging", f"beats {talk} frame Data's face and chest ({'/'.join(sorted(TALKING))}): at most "
                               f"{TALK_MAX}; the rest show him whole, doing it, in his world (the Dr. Katz look)"))
    world = len(cams) - len(talk)
    need = min(WORLD_MIN, max(0, len(cams) - TALK_MAX))
    if world < need:
        out.append(("staging", f"{world} beats show Data whole in his world; a short needs {need}"))
    return out


def talking_heads(fr):
    """fr: {shot: framing} from staging.framing. [(shot, problem)] past the first TALK_MAX talking-head shots"""
    heads = [n for n in sorted(fr) if fr[n].get("h") and fr[n]["h"] > TALK_H and abs(fr[n].get("yaw", 180)) < TALK_YAW]
    return [(n, f"a talking head (Data {fr[n]['h']:.2f} of the frame tall, face {fr[n]['yaw']:.0f} deg off the lens), "
                f"and shots {heads[:TALK_MAX]} already are: pull back so he is whole and doing it, or turn him to the work")
            for n in heads[TALK_MAX:]]


def problems(story, script):
    if not held(story): return []
    return history_problems(story, script) + watch_problems(script) + dr_katz_problems(script)
