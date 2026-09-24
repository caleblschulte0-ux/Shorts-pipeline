#!/usr/bin/env python3
"""Write the next OpenRangeInteractive SLEEP FILM script.

Keeps `data_learning/ori_episodes/` stocked so the weekly film never stops
for want of a script. A two-hour script (~14,500 words) is not one answer, so
it is written the way a person would write it: an OUTLINE first (title,
thumbnail, era, 10-13 chapters with what each covers), then EACH CHAPTER in
its own call, told what came before so the story flows. Every chapter is run
through the same scene and length checks the renderer uses
(`ori_sleep.validate`, `doodle.scene.validate`) and sent back ONCE with the
exact problems; a chapter that still fails sinks the episode, which is
dropped, never written.

The brain is the channel's usual chain (`shared.script_generator._call_llm`:
the Claude subscription CLI first) with the mailbox excluded — a script that
no model wrote this run is not one to render.

    python scripts/ori_author.py              # top up to queue_minimum
    python scripts/ori_author.py --count 1
    python scripts/ori_author.py --topic "What did medieval peasants do after dark?" --era medieval
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import ori_sleep as OS      # noqa: E402
from data_learning.doodle import scene as S    # noqa: E402

CONFIG = REPO / "data_learning" / "ori.config.json"
POSTED = REPO / "state" / "curiosity_posted_log.json"
#: topics tried beyond the number wanted before the author gives up for the run
MAX_EXTRA_TOPICS = 1
#: a 1,200-word chapter is not a one-line judgement; the shared CLI default
#: (90s) is sized for the latter and timed every attempt out in CI
os.environ.setdefault("CLAUDE_CLI_TIMEOUT", "600")
SUFFIX = "Cozy History for Sleep"

SYSTEM = """You write narration for OpenRangeInteractive, a YouTube channel of \
two-hour history stories people fall asleep to. The voice is warm, slow and \
gentle; the listener is lying in the dark, often not watching. Every passage \
you write is shown as a simple hand-drawn cartoon scene that YOU describe in a \
fixed vocabulary. Return ONLY one JSON object, no prose, no code fences."""

OUTLINE = """Plan one episode on: {topic}
Era: {era} (every scene must exist in this era).

Return:
{{
  "slug": "kebab-case-from-the-title",
  "title": "a curious question or promise, then ' | {suffix}' — 40-100 chars total",
  "thumbnail_text": "2-4 WORDS, a hook a sleepy scroller clicks (e.g. NO FIRE? / BITTEN ALL NIGHT?)",
  "thumbnail_scene": SCENE,
  "description": "3-4 calm sentences for YouTube: what the listener will drift through",
  "tags": ["10-14 lowercase tags, include history for sleep, sleep story, relaxing history"],
  "chapters": [{{"title": "short chapter title", "covers": "2-3 sentences: exactly what this chapter tells"}}]
}}
{chapters_lo}-{chapters_hi} chapters. The first opens gently (welcome, settle in, where and when we are).
The arc is ONE evening-to-night or one day-to-night, so light moves from dusk to
deep night as the film goes on, and the last chapter winds down to sleep.
Only well-established history; where scholars are unsure, say so gently.

SCENE vocabulary (exact names only):
{vocab}"""

CHAPTER = """Episode: {title}
Era: {era}
Chapter {n} of {total}: "{chapter}" — {covers}
{prev}
Write this chapter as 10-14 beats. Each beat is one passage of narration and the
single scene shown while it is spoken. Return:
{{"beats": [{{"say": "80-140 words of narration", "scene": SCENE}}]}}

NARRATION RULES — a chapter that breaks one is thrown away:
- {words_lo}-{words_hi} words in the chapter. Slow, second-person, present tense
  where it suits ("You pull the fur closer..."), soft sensory detail, no drama,
  no cliffhangers, no jokes that jolt. Short, flowing sentences.
- Only well-established history. Hedge honestly ("people probably", "we think").
  No invented names of real people, no exact dates you are not sure of.
- Never mention the video, the channel, subscribing, AI, or "this chapter".
- Each scene must SHOW what its passage says: same place, same time of day,
  people doing what the words describe — pick the ACTION from the vocabulary
  that matches the words (sewing, knapping, feeding the fire, playing,
  telling, carrying, eating, looking up); "idle" only where the words say
  rest. Change the picture every beat; vary settings, shots and people
  across the chapter.
{final}
SCENE vocabulary (exact names only):
{vocab}
{problems}"""


def _parse(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])


class NoBrain(RuntimeError):
    """Nobody could answer at all — not a bad answer to retry, a dark run."""


def _ask(system: str, user: str) -> str:
    """The brain chain without the mailbox (see module docstring)."""
    from shared import script_generator as sg
    errs = []
    # the strongest writer first: a two-hour story is not a caption
    order = {"claude_cli": 0, "anthropic": 1, "gemini": 2, "groq": 3}
    chain = sorted((c for c in sg._LLM_CHAIN if c[0] in order), key=lambda c: order[c[0]])
    for name, env, call in chain:
        if env and not os.environ.get(env):
            continue
        try:
            return call(system, user, None)
        except Exception as e:                           # noqa: BLE001
            errs.append(f"{name}: {str(e)[:100]}")
    raise NoBrain("no brain answered: " + " | ".join(errs or ["none configured"]))


def used_topics() -> set[str]:
    out = set()
    for p in OS.EPISODES.glob("*.json"):
        try:
            out.add((json.loads(p.read_text()).get("topic") or "").lower())
        except (OSError, ValueError):
            continue
    return out


def queue() -> list[str]:
    """Unposted, valid episode slugs, oldest first."""
    posted = {}
    if POSTED.exists():
        posted = (json.loads(POSTED.read_text()).get("posted") or {})
    items = []
    for p in OS.EPISODES.glob("*.json"):
        try:
            ep = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if ep.get("slug") in posted or OS.validate(ep):
            continue
        items.append((ep.get("added", ""), ep["slug"]))
    return [s for _, s in sorted(items)]


def _outline_problems(o: dict, era: str) -> list[str]:
    bad = []
    for k in ("slug", "title", "thumbnail_text", "thumbnail_scene", "description", "chapters"):
        if not o.get(k):
            bad.append(f"missing {k}")
    if bad:
        return bad
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(o["slug"])):
        bad.append("slug must be kebab-case")
    if (OS.EPISODES / f"{o['slug']}.json").exists():
        bad.append(f"slug {o['slug']!r} already exists — choose another")
    if not (40 <= len(o["title"]) <= OS.TITLE_MAX) or SUFFIX not in o["title"]:
        bad.append(f"title must be 40-{OS.TITLE_MAX} chars and end with ' | {SUFFIX}'")
    if not (2 <= len(str(o["thumbnail_text"]).split()) <= 4):
        bad.append("thumbnail_text must be 2-4 words")
    bad += ["thumbnail_scene: " + x for x in S.validate(o["thumbnail_scene"], era)]
    n = len(o["chapters"])
    if not (CHAPTERS[0] <= n <= CHAPTERS[1]):
        bad.append(f"{n} chapters ({CHAPTERS[0]}-{CHAPTERS[1]})")
    return bad


# The film is sized to the render slot BEFORE a chapter is written. Run #15
# (2026-09-24) was told "14-16 chapters of 1,000-1,400 words" — up to 2h50 —
# wrote 19,611 words, and its 149-minute film could not be drawn and judged
# in the 230-minute step. So: a word target for the whole film, chapter
# bounds derived from the chapter count, and a hard cap per chapter that
# keeps the total under OS.MAX_WORDS whatever the brain does.
TARGET_WORDS = 14500       # ~110 minutes at the measured 131 words a minute
CHAPTERS = (10, 13)


def chapter_words(n: int) -> tuple[int, int, int, int]:
    """(ask_lo, ask_hi, check_lo, check_hi) for a film of n chapters: what
    the brain is asked for, and the bounds a chapter is held to."""
    target = TARGET_WORDS // max(1, n)
    cap = OS.MAX_WORDS // max(1, n)
    ask_lo = max(700, target - 150)
    ask_hi = min(1400, target + 150, cap - 50)
    return ask_lo, ask_hi, max(600, ask_lo - 100), min(cap, ask_hi + 150)


SAME_LOOK_SHARE = 0.5      # at most half a chapter's beats may share one setting+shot
IDLE_SHARE = 0.3           # at most three in ten peopled beats may show everyone idle
FILM_LOOK_SHARE = 0.2      # ... and at most one in five of the whole film's
FILM_PLACE_SHARE = 0.25
CROWD_SHRINK = 0.8
MARK_SHARE = 0.3
MAX_FILM_REPAIRS = 40      # repair_film steps per script; each is the smallest change that lowers the count           # no one setting at more than three in ten of the film's judged moments         # a scene the layout must draw smaller than this fraction of natural size is too crowded    # ... and no one SETTING, whatever the shot, past a quarter of the film


def _mark_beats(beats) -> list[int]:
    """The beat playing at a quarter, at 55% and at 85% of the chapter's
    words — the three moments the finished film is judged at."""
    words = [len((b.get("say") or "").split()) if isinstance(b, dict) else 0 for b in beats]
    total = sum(words)
    if not total:
        return []
    out = []
    for f in (0.25, 0.55, 0.85):
        acc = 0
        for j, w in enumerate(words):
            acc += w
            if acc >= f * total:
                out.append(j)
                break
    return out


def _picture_tally(chapters) -> dict:
    """How often each (setting, shot) picture has been used so far."""
    tally = {}
    for ch in chapters:
        for b in ch.get("beats", []):
            sc = b.get("scene") if isinstance(b, dict) else None
            if isinstance(sc, dict):
                k = (sc.get("setting"), S.shot_of(sc))
                tally[k] = tally.get(k, 0) + 1
    return tally


def _tally_note(tally: dict, so_far: int) -> str:
    """A line for the chapter prompt: the pictures the film has leaned on
    and how many more of each this chapter may add."""
    if not tally:
        return ""
    top = sorted(tally.items(), key=lambda kv: -kv[1])[:3]
    parts = []
    for (setting, shot), n in top:
        room = max(0, int(FILM_LOOK_SHARE * (so_far + 12)) - n)
        parts.append(f"{setting} ({shot} shot) x{n}, at most {room} more")
    return ("- The film so far leans on: " + "; ".join(parts) + ". Prefer other settings and shots "
            "for this chapter.")


def _chapter_problems(beats, era: str, lo: int, hi: int, before=None, opening: bool = False) -> list[str]:
    if not isinstance(beats, list) or not beats:
        return ["no beats"]
    bad, total = [], 0
    if opening:
        # the hook: the film opens on a wide establishing picture of the place
        first = beats[0].get("scene") if isinstance(beats[0], dict) else None
        if not isinstance(first, dict) or S.shot_of(first) != "wide":
            bad.append("beat 1 (the film's first picture) must be a wide establishing shot: shot \"wide\"")
    for j, b in enumerate(beats):
        if not isinstance(b, dict):
            bad.append(f"beat {j + 1} is not an object")
            continue
        w = OS._words(b.get("say", ""))
        total += w
        if not (OS.BEAT_WORDS[0] <= w <= OS.BEAT_WORDS[1]):
            bad.append(f"beat {j + 1}: {w} words ({OS.BEAT_WORDS[0]}-{OS.BEAT_WORDS[1]})")
        bad += [f"beat {j + 1} scene: {x}" for x in S.validate(b.get("scene"), era)]
    if not (lo <= total <= hi):
        bad.append(f"{total} words in the chapter ({lo}-{hi})")
    # the first film's judge: "the cave mouth + fire + one or two seated
    # figures template covers most of the film, so the story's activities
    # are never shown". A chapter is a sequence of DIFFERENT pictures.
    looks = {}
    for b in beats:
        sc = b.get("scene") if isinstance(b, dict) else None
        if isinstance(sc, dict):
            k = (sc.get("setting"), S.shot_of(sc))
            looks[k] = looks.get(k, 0) + 1
    # the judge grades whether each picture SHOWS the activity its words
    # describe; a cast that only sits is a picture of nothing in particular
    peopled = [b for b in beats if isinstance(b, dict) and isinstance(b.get("scene"), dict)
               and b["scene"].get("cast")]
    idle = [b for b in peopled if all(isinstance(c, dict) and c.get("action", "idle") in ("idle", "hold")
                                      for c in b["scene"]["cast"])]
    if peopled and len(idle) > max(1, int(len(peopled) * IDLE_SHARE)):
        bad.append(f"{len(idle)} of {len(peopled)} peopled beats show everyone idle: give the people the "
                   f"action the words describe (sew, knap, feed_fire, play, talk, carry, eat, look_up...)")
    # a scene the layout can only fit by drawing everyone small is a scene
    # with too much in it: the eighth film's judge saw "a sleeper's head
    # right next to the fire's base at the tiny render size". Ask the
    # layout (fast, deterministic) and send the crowd back to the author
    for j, b in enumerate(beats):
        sc = b.get("scene") if isinstance(b, dict) else None
        if not isinstance(sc, dict) or S.validate(sc, era):
            continue
        lay = S.layout(sc, 1000 + j)
        natural = 2.05 if S.shot_of(sc) == "close" else 1.25
        if lay["scale"] < natural * CROWD_SHRINK - 1e-6:
            bad.append(f"beat {j + 1} is too crowded for its {S.shot_of(sc)} shot (drawn at "
                       f"{int(100 * lay['scale'] / natural)}% size to fit): drop a prop or a person, or widen the shot")
    # a chapter MOVES: at a quarter, half and near its end (by words, which
    # is screen time) it is in at least two different places. The judge
    # looks at exactly those three moments of every chapter, and chapters
    # whose three looked the same "blur together" (the sixth, seventh and
    # eighth films)
    marks = _mark_beats(beats)
    if marks:
        places = [beats[j]["scene"].get("setting") for j in marks
                  if isinstance(beats[j], dict) and isinstance(beats[j].get("scene"), dict)]
        if len(places) == 3 and len(set(places)) < 2:
            bad.append(f"the chapter stands in {places[0]} at its quarter, half and end (beats "
                       f"{', '.join(str(j + 1) for j in marks)}): a chapter moves — take one of those beats "
                       f"somewhere else")
    prev = None
    for j, b in enumerate(beats):
        sc = b.get("scene") if isinstance(b, dict) else None
        k = (sc.get("setting"), S.shot_of(sc)) if isinstance(sc, dict) else None
        if k is not None and k == prev:
            bad.append(f"beats {j} and {j + 1} are the same picture ({k[0]}, {k[1]} shot) back to back: "
                       f"change the setting or the shot between them")
        prev = k
    if looks:
        (setting, shot), n = max(looks.items(), key=lambda kv: kv[1])
        if n > max(2, int(len(beats) * SAME_LOOK_SHARE)):
            bad.append(f"{n} of {len(beats)} beats are the same picture ({setting}, {shot} shot): "
                       f"vary the setting and the shot, and show what each passage describes")
    if before:
        # a new chapter is a new picture: it opens somewhere other than where
        # the last one closed (the sixth film's judge, sampling each chapter's
        # first, middle and last frame, saw the cave-fire picture "in over
        # half the sampled frames, so chapters blur together")
        prev = before[-1] if isinstance(before[-1], dict) else {}
        prev_beats = prev.get("beats") or []
        last = prev_beats[-1].get("scene") if prev_beats and isinstance(prev_beats[-1], dict) else None
        first = beats[0].get("scene") if isinstance(beats[0], dict) else None
        if isinstance(last, dict) and isinstance(first, dict) and last.get("setting") == first.get("setting"):
            bad.append(f"beat 1 opens in {first.get('setting')}, where the previous chapter closed: a new chapter "
                       f"opens on a new place")
        # the whole film, not just this chapter: the second film's judge
        # counted one cave-front picture in 15 of 42 sampled frames, and the
        # fourth still saw "the cave mouth on the left, a campfire in the
        # centre" in six chapters of fourteen
        prior = _picture_tally(before)
        so_far = sum(prior.values())
        n_all = so_far + len(beats)
        for k, n in looks.items():
            total = prior.get(k, 0) + n
            if total > int(FILM_LOOK_SHARE * n_all) + 1:
                bad.append(f"{k[0]} ({k[1]} shot) would be {total} of the film's {n_all} "
                           f"pictures so far: use it for at most "
                           f"{max(0, int(FILM_LOOK_SHARE * n_all) + 1 - prior.get(k, 0))} "
                           f"beats in this chapter")
        # ...and at the three judged moments of every chapter so far, no one
        # place holds more than MARK_SHARE: the cave mouth stood at the
        # half-mark of nine chapters in fourteen, which is what "the same
        # setup in 16 of 42 samples" was
        mark_places = []
        for ch in before:
            bb = ch.get("beats") if isinstance(ch, dict) else None
            if isinstance(bb, list):
                mark_places += [bb[j]["scene"].get("setting") for j in _mark_beats(bb)
                                if isinstance(bb[j], dict) and isinstance(bb[j].get("scene"), dict)]
        here = [beats[j]["scene"].get("setting") for j in _mark_beats(beats)
                if isinstance(beats[j], dict) and isinstance(beats[j].get("scene"), dict)]
        allm = mark_places + here
        for setting in set(here):
            n = allm.count(setting)
            if n > int(MARK_SHARE * len(allm)) + 1:
                bad.append(f"{setting} would be the picture at {n} of the film's {len(allm)} judged moments so far "
                           f"(each chapter's quarter, half and end): use it at fewer of this chapter's "
                           f"(beats {', '.join(str(j + 1) for j in _mark_beats(beats))})")
        places_prior = {}
        for (setting, _shot), n in prior.items():
            places_prior[setting] = places_prior.get(setting, 0) + n
        places_here = {}
        for (setting, _shot), n in looks.items():
            places_here[setting] = places_here.get(setting, 0) + n
        for setting, n in places_here.items():
            total = places_prior.get(setting, 0) + n
            if total > int(FILM_PLACE_SHARE * n_all) + 1:
                bad.append(f"{setting} would be {total} of the film's {n_all} pictures so far, whatever the "
                           f"shot: use it for at most "
                           f"{max(0, int(FILM_PLACE_SHARE * n_all) + 1 - places_prior.get(setting, 0))} "
                           f"beats in this chapter and take the rest elsewhere")
    return bad


def mend_scene(scene: dict, era: str) -> str | None:
    """The smallest deterministic change that makes a scene the brain wrote
    valid: a scene where nothing moves gets the era's plainest light (a
    fire outdoors, a hearth or a candle indoors, a torch), a prop the kit
    does not know is dropped, a pose the action cannot take becomes one it
    can. The first fresh-topic run failed here — chapter 1 rejected twice
    for "nothing in this scene moves enough" and the author gave up — and a
    system that hands a motion rule back to a brain twice and stops is not
    a system. Returns what was done, or None when the scene was fine or
    nothing here can mend it."""
    if not isinstance(scene, dict):
        return None
    did = []
    # the cast: a held thing the kit does not draw is put down, a mood or a
    # pose it does not know becomes the plain one, a pose the action cannot
    # take becomes one it can (the second fresh-topic run: item 'candle')
    from data_learning.doodle import people as P
    for c in scene.get("cast") or []:
        if not isinstance(c, dict):
            continue
        if c.get("item") is not None and c.get("item") not in P.ITEMS:
            did.append(f"put down {c['item']}")
            c.pop("item", None)
        if c.get("mood") is not None and c.get("mood") not in P.MOODS:
            did.append(f"mood {c['mood']} -> calm")
            c["mood"] = "calm"
        action = c.get("action", "idle")
        if action not in P.ACTIONS:
            did.append(f"action {action} -> idle")
            c["action"] = action = "idle"
        pose = c.get("pose", "stand")
        if pose not in P.POSES or pose not in P.ACTIONS[action]["poses"]:
            c["pose"] = P.ACTIONS[action]["poses"][0]
            did.append(f"pose {pose} -> {c['pose']} for {action}")
    bad = S.validate(scene, era)
    if not bad:
        return ", ".join(did) if did else None
    # a prop the kit does not have, or not in this era/setting: drop it
    props = [q for q in scene.get("props", []) if isinstance(q, (str, dict))]
    keep = []
    for q in props:
        name = q if isinstance(q, str) else q.get("name")
        pr = S.PROPS.get(name)
        if pr is None or era not in pr.eras or (pr.settings and scene.get("setting") not in pr.settings):
            did.append(f"dropped {name}")
        else:
            keep.append(q)
    if len(keep) != len(props):
        scene["props"] = keep
    # nothing moves: add the plainest light this setting and era allow
    if any("moves enough" in x for x in S.validate(scene, era)):
        st = S.SETTINGS.get(scene.get("setting"))
        interior = bool(st and st.interior)
        # one light first, then two (a wide night needs a fire AND a torch);
        # a hearth is a fireplace, so it is never lit outdoors
        order = ([["hearth"], ["candle"], ["oil_lamp"], ["stove"], ["campfire"], ["brazier"], ["torch"]]
                 if interior else
                 [["campfire"], ["torch"], ["brazier"], ["cauldron"], ["campfire", "torch"],
                  ["campfire", "cauldron"], ["brazier", "torch"]])
        names = [(q if isinstance(q, str) else q.get("name")) for q in scene.get("props", [])]
        lit = None
        for group in order:
            adds = []
            for name in group:
                pr = S.PROPS.get(name)
                if pr is None or era not in pr.eras or (pr.settings and scene.get("setting") not in pr.settings):
                    adds = None
                    break
                if name not in names:
                    adds.append(name)
            if not adds:
                continue
            saved = scene.get("props", [])
            scene["props"] = list(saved) + adds
            if not any("moves enough" in x for x in S.validate(scene, era)):
                lit = adds
                break
            scene["props"] = saved
        if lit:
            did.append("lit " + " and ".join(f"a {n}" for n in lit))
        elif scene.get("time") in ("day", "dawn"):
            # a film about the night: daylight where no fire counts goes
            # to dusk, then night, and the lights are tried again (the
            # fourth fresh-topic run: "nothing in this scene moves" on a
            # beat the mend had left alone)
            was = scene.get("time")
            for t in ("dusk", "night"):
                scene["time"] = t
                inner = mend_scene(scene, era)
                if not any("moves enough" in x for x in S.validate(scene, era)):
                    did.append(f"{was} -> {t}" + (f", {inner}" if inner else ""))
                    break
            else:
                scene["time"] = was
        if not lit and any("moves enough" in x for x in S.validate(scene, era)):
            # still: bring the shot in close, where a fire counts for more
            if S.shot_of(scene) != "close":
                scene["shot"] = "close"
                if any("moves enough" in x for x in S.validate(scene, era)):
                    scene.pop("shot", None)
                else:
                    did.append("brought the shot close")
    return ", ".join(did) if did and not S.validate(scene, era) else (", ".join(did) if did else None)


def uncrowd_scene(scene: dict, era: str, seeds=(1000,)) -> str | None:
    """Make a crowded scene fit at CROWD_SHRINK of natural size: drop
    inessential props from the last while each drop fits better, then a
    person from the back of the cast, then widen the shot (lighting a torch
    if a wide night needs one). Judged by the worse of the given seeds.
    Returns what was done, or None.

    "Fits better" is measured on a GRADIENT, not the shrink step alone: the
    layout draws in steps (100, 92, 84, 76...%), so two drops that each
    leave a wide at 76% and together bring it to 92% look like no progress
    one at a time — the fourth fresh-topic run left a beat-1 wide at 76%
    three chapters running for exactly that. The ground the scene occupies
    is the second measure, so a drop that frees room counts even when the
    step has not moved yet."""
    def fit():
        if S.validate(scene, era):
            return (-1.0, 0.0)
        natural = 2.05 if S.shot_of(scene) == "close" else 1.25
        worst = (9.0, 0.0)
        for seed in seeds:
            lay = S.layout(scene, seed)
            # a scene that still collides scores below any that fits, and
            # FEWER collisions is progress — a close shot holding two houses
            # and a cow needs three drops, and the first two fix nothing on
            # their own
            room = -sum(max(0.0, sp["hi"] - sp["lo"]) for sp in S.spans(lay) if not sp.get("ground"))
            worst = min(worst, ((-float(len(lay["collisions"])) if lay["collisions"] else lay["scale"] / natural),
                                room))
        return worst

    def crowded():
        return fit()[0] < CROWD_SHRINK

    def better(now, was):
        return now[0] > was[0] + 1e-6 or (now[0] >= was[0] - 1e-6 and now[1] > was[1] + 1e-6)

    if not crowded():
        return None
    old = json.loads(json.dumps(scene))
    dropped = []
    # a place the brain pinned (`at`) is a place the layout cannot move: let
    # it choose, and see whether that alone makes room
    pinned = [c for c in scene.get("cast") or [] if isinstance(c, dict) and c.get("at")]
    pinned += [q for q in scene.get("props") or [] if isinstance(q, dict) and q.get("at")]
    if pinned:
        was = fit()
        for c in pinned:
            c.pop("at", None)
        if better(fit(), was):
            dropped.append("the fixed places")
        else:
            scene.clear(); scene.update(json.loads(json.dumps(old)))
    while crowded():
        props = list(scene.get("props", []))
        best = None
        for k in range(len(props) - 1, -1, -1):
            name = props[k] if isinstance(props[k], str) else props[k]["name"]
            pr = S.PROPS.get(name)
            if pr is None or pr.living or pr.light:
                continue
            was = fit()
            scene["props"] = props[:k] + props[k + 1:]
            if better(fit(), was):
                best = name
                break
            scene["props"] = props
        if best is None:
            break
        dropped.append(best)
    # then a person: the rule itself says "drop a prop or a person", and a
    # crowd of four drawn at 60% reads worse than three at full size. From
    # the back of the cast, never the first (the words are about somebody)
    while crowded() and len(scene.get("cast") or []) > 1:
        cast = list(scene["cast"])
        was = fit()
        scene["cast"] = cast[:-1]
        if better(fit(), was):
            gone = cast[-1]
            dropped.append(f"the {gone.get('who', 'person')} at the back")
        else:
            scene["cast"] = cast
            break
    if crowded() and S.shot_of(scene) == "close":
        scene["shot"] = "wide"
        if S.validate(scene, era) and "torch" not in scene.get("props", []):
            scene["props"] = list(scene.get("props", [])) + ["torch"]
        if crowded() or S.validate(scene, era):
            scene["shot"] = old.get("shot", "close")
            scene["props"] = [q for q in scene.get("props", []) if q != "torch" or "torch" in old.get("props", [])]
        else:
            dropped.append("the close shot (widened" + (", a torch lit" if "torch" not in old.get("props", []) else "") + ")")
    if not crowded() and dropped:
        return "dropped " + ", ".join(dropped)
    scene.clear(); scene.update(old)
    return None


# what a beat's words say its people are DOING, for a cast the brain left
# idle: the first action whose words appear wins; a fire in the scene and
# nothing in the words is warm_hands; two people and nothing else is talk
ACTION_WORDS = (
    ("sew", ("sew", "mend", "stitch", "spin", "weav", "knit", "needle", "darn")),
    ("eat", ("eat", "supper", "meal", "bread", "pottage", "stew", "feast", "dine", "porridge", "bowl")),
    ("drink", ("drink", "ale", "cup", "sip", "wine", "beer", "mead")),
    ("feed_fire", ("fire", "hearth", "ember", "log", "kindl", "flame", "bank")),
    ("stir", ("stir", "cook", "pot", "cauldron", "broth", "simmer")),
    ("carry", ("carry", "carri", "haul", "fetch", "bring", "bundle", "water", "wood", "load")),
    ("chop", ("chop", "split", "axe", "hew")),
    ("play", ("play", "game", "dice", "toss", "children", "child", "chase", "laugh")),
    ("sleep", ("sleep", "asleep", "slumber", "doze", "bed", "lie down", "lay down")),
    ("look_up", ("star", "sky", "moon", "heaven", "look up", "gaze")),
    ("talk", ("talk", "stor", "tale", "tell", "speak", "gossip", "sing", "song", "pray", "chant", "whisper",
              "voice", "word", "conversation", "murmur")),
    ("gather", ("gather", "pick", "collect", "forage", "herb")),
    ("hug_self", ("cold", "shiver", "chill", "frost", "huddle")),
    ("yawn", ("yawn", "tired", "weary", "drows")),
    ("warm_hands", ("warm", "glow", "heat")),
)


def action_for_words(say: str, scene: dict) -> str | None:
    """The action a beat's words describe, or the plain one its picture
    allows: warm_hands at a fire, talk between two people. None when the
    scene has no people."""
    cast = [c for c in (scene.get("cast") or []) if isinstance(c, dict)]
    if not cast:
        return None
    low = (say or "").lower()
    for action, words in ACTION_WORDS:
        if any(w in low for w in words):
            return action
    names = [(q if isinstance(q, str) else q.get("name")) for q in scene.get("props") or []]
    if any(n in ("campfire", "hearth", "brazier", "stove") for n in names):
        return "warm_hands"
    return "talk" if len(cast) > 1 else "look_up"


def mend_idle(beats, era: str, log=print) -> int:
    """A chapter whose people mostly stand about is given the actions its
    words describe, idle beat by idle beat, until the idle share holds —
    the fourth fresh-topic run lost two brain calls to "4 of 12 peopled
    beats show everyone idle". The first person in the cast takes the
    action and the pose the kit allows for it; the others keep theirs.
    Returns how many beats changed."""
    from data_learning.doodle import people as P
    peopled = [b for b in beats if isinstance(b, dict) and isinstance(b.get("scene"), dict)
               and b["scene"].get("cast")]
    def idle():
        return [b for b in peopled if all(isinstance(c, dict) and c.get("action", "idle") in ("idle", "hold")
                                          for c in b["scene"]["cast"])]
    n = 0
    for b in list(idle()):
        if len(idle()) <= max(1, int(len(peopled) * IDLE_SHARE)):
            break
        action = action_for_words(b.get("say", ""), b["scene"])
        if action is None or action not in P.ACTIONS:
            continue
        c = next(c for c in b["scene"]["cast"] if isinstance(c, dict))
        before = json.loads(json.dumps(c))
        c["action"] = action
        if c.get("pose", "stand") not in P.ACTIONS[action]["poses"]:
            c["pose"] = P.ACTIONS[action]["poses"][0]
        if action == "sleep":
            c["pose"] = "lie"
        if S.validate(b["scene"], era):
            c.clear(); c.update(before)
            continue
        n += 1
        log(f"[ori_author] mended beat {beats.index(b) + 1}: the {c.get('who', 'person')} now {action}s")
    return n


def mend_beats(beats, era: str, log=print) -> int:
    """mend_scene over a chapter's beats, then the crowd, then the idle;
    returns how many scenes changed."""
    n = 0
    if not isinstance(beats, list):
        return 0
    for j, b in enumerate(beats):
        if isinstance(b, dict) and isinstance(b.get("scene"), dict):
            did = mend_scene(b["scene"], era)
            crowd = uncrowd_scene(b["scene"], era, seeds=(1000 + j,))
            did = ", ".join(x for x in (did, crowd) if x)
            if did:
                n += 1
                log(f"[ori_author] mended beat {j + 1}: {did}")
    n += mend_idle(beats, era, log=log)
    return n


def _with_retry(prompt_fn, check, ask, label, mend=None):
    problems = ""
    for attempt in (1, 2, 3):
        try:
            out = _parse(ask(SYSTEM, prompt_fn(problems)))
        except NoBrain:
            raise
        except Exception as e:                           # noqa: BLE001
            print(f"[ori_author] {label} attempt {attempt}: {e}", flush=True)
            problems = f"\nYOUR LAST ANSWER COULD NOT BE READ AS JSON ({str(e)[:80]}). Return only JSON."
            continue
        if mend is not None and isinstance(out, dict):
            mend(out)                      # the deterministic fixes first; the brain sees only what is left
        bad = check(out)
        if not bad:
            return out
        print(f"[ori_author] {label} attempt {attempt} invalid: {bad[:6]}", flush=True)
        problems = ("\nYOUR LAST ATTEMPT WAS REJECTED FOR: " + "; ".join(bad[:25])
                    + "\nFix every one.")
    return None


# what a topic's words say about WHEN it is — the deterministic first pass
# of era_for(); the brain is asked only when none of these words appear
ERA_WORDS = {
    "stone_age": ("stone age", "ice age", "early human", "early humans", "cave", "hunter-gatherer",
                  "hunter gatherer", "mammoth", "neanderthal", "first farmers", "prehistoric", "paleolithic",
                  "neolithic", "flint"),
    "medieval": ("medieval", "middle ages", "peasant", "castle", "knight", "monk", "monastery", "viking",
                 "feudal", "manor", "plague", "crusade", "abbey", "serf"),
    "ancient": ("roman", "rome", "greek", "greece", "athens", "sparta", "pompeii",
                "mediterranean", "legion", "caesar", "villa", "forum", "byzant", "olive"),
    "egypt": ("egypt", "egyptian", "nile", "pharaoh", "pyramid", "pyramids", "thebes", "giza", "memphis", "luxor",
              "papyrus", "scribe"),
    "early_modern": ("tudor", "elizabethan", "pirate", "pirates", "1500s", "1600s", "16th century", "17th century",
                     "sixteenth century", "seventeenth century", "age of sail", "galleon", "plymouth", "puritan",
                     "shakespeare", "musketeer", "renaissance", "reformation", "mayflower"),
    "victorian": ("victorian", "1800s", "19th century", "nineteenth century", "industrial", "dickens", "steam",
                  "railway", "gaslight", "gas lamp", "mill town", "workhouse", "regency", "georgian", "edwardian",
                  "1700s", "18th century", "eighteenth century", "colonial", "frontier", "1770s", "revolutionary war"),
}

ERA_PROMPT = """Which of these drawn worlds fits the topic below? Answer with ONE word from this list, or "none" if the topic belongs to a time none of them can show: {eras}.
{eras_doc}
Topic: {topic}"""


def era_for(topic: str, ask=_ask) -> str | None:
    """The era a topic is drawn in, or None when the kit has no era for it.
    Words first (deterministic, no model); the brain only for a topic that
    names none of them; None is an honest refusal, never a default."""
    t = topic.lower()
    hits = {era: sum(1 for w in words if w in t) for era, words in ERA_WORDS.items()}
    named = [era for era, n in hits.items() if n]
    if len(named) == 1:
        return named[0]          # two eras named at once is a question for the brain, not a count
    if ask is None:
        return None
    eras_doc = "\n".join(f"- {e}: {S.vocabulary(e).splitlines()[0][:140]}" for e in S.ERAS)
    try:
        ans = ask("You choose which drawn world a story is set in. One word only.",
                  ERA_PROMPT.format(eras=", ".join(S.ERAS), eras_doc=eras_doc, topic=topic))
    except NoBrain:
        return None
    word = re.sub(r"[^a-z_]", "", (ans or "").strip().lower().split()[0] if (ans or "").strip() else "")
    return word if word in S.ERAS else None


def author(topic: str, era: str, ask=_ask) -> dict | None:
    vocab = S.vocabulary(era)
    o = _with_retry(lambda pr: OUTLINE.format(topic=topic, era=era, suffix=SUFFIX, vocab=vocab,
                                              chapters_lo=CHAPTERS[0], chapters_hi=CHAPTERS[1]) + pr,
                    lambda o: _outline_problems(o, era), ask, f"{topic!r} outline")
    if o is None:
        return None
    chs = o["chapters"]
    words_lo, words_hi, check_lo, check_hi = chapter_words(len(chs))
    out_chapters = []
    prev_text = ""
    for i, ch in enumerate(chs):
        prev = (f"The previous chapter ended: \"{prev_text[-600:]}\"" if prev_text
                else "This is the opening chapter: welcome the listener gently and set the scene. "
                     "Its FIRST beat is a wide establishing shot of the place (shot \"wide\"), "
                     "with the title drawn over it — the picture the film opens on.")
        final = ("- This is the LAST chapter: let the night grow deep and quiet, and end "
                 "with the people asleep and the listener invited to sleep too. Its last "
                 "outdoor scenes use time \"dawn\" — the sky pales as the film ends."
                 if i == len(chs) - 1 else "")
        tally = _picture_tally(out_chapters)
        final = "\n".join(x for x in (final, _tally_note(tally, sum(tally.values()))) if x)
        before = list(out_chapters)
        res = _with_retry(
            lambda pr, i=i, ch=ch, prev=prev, final=final: CHAPTER.format(
                title=o["title"], era=era, n=i + 1, total=len(chs), chapter=ch.get("title", ""),
                covers=ch.get("covers", ""), prev=prev, words_lo=words_lo, words_hi=words_hi,
                final=final, vocab=vocab, problems=pr),
            lambda r, before=before, i=i: _chapter_problems(r.get("beats") if isinstance(r, dict) else None, era,
                                                            check_lo, check_hi, before=before,
                                                            opening=(i == 0)),
            ask, f"{topic!r} chapter {i + 1}",
            mend=lambda r, before=before, i=i: (
                mend_beats(r.get("beats") if isinstance(r, dict) else None, era),
                # the film-level rules too (a place owning the judged moments,
                # the film's caps): repaired in code here, before the brain
                # is asked again, exactly as repair_film does on a whole film
                isinstance(r, dict) and isinstance(r.get("beats"), list) and repair_film(
                    {"slug": o["slug"], "era": era,
                     "chapters": list(before) + [{"title": ch.get("title", ""), "beats": r["beats"]}]},
                    only_chapter=len(before))))
        if res is None:
            return None
        out_chapters.append({"title": ch.get("title", f"Chapter {i + 1}"), "beats": res["beats"]})
        prev_text = res["beats"][-1]["say"]
    ep = {"slug": o["slug"], "title": o["title"], "thumbnail_text": o["thumbnail_text"],
          "thumbnail_scene": o["thumbnail_scene"], "description": o["description"],
          "tags": o.get("tags") or [], "era": era, "chapters": out_chapters,
          "sources": o.get("sources") or []}
    bad = OS.validate(ep)
    if bad:
        print(f"[ori_author] {topic!r} assembled episode invalid: {bad[:6]}", flush=True)
        return None
    ep["topic"] = topic
    ep["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    ep["authored_by"] = "ori_author"
    return ep


# words in a passage that pin it to its place: a beat whose words say the
# cave is not moved out of the cave to satisfy a picture rule
SETTING_WORDS = {
    "cave_mouth": ("cave",), "cave_inside": ("cave",), "riverbank": ("river", "stream", "bank"),
    "lakeshore": ("lake",), "seashore": ("sea", "shore", "beach", "tide"), "forest": ("forest", "wood", "trees"),
    "snowfield": ("snow",), "mountains": ("mountain", "peak", "hills"), "grassland": ("grass", "steppe", "plain"),
    "field": ("field",), "village": ("village",), "castle": ("castle",), "harbour": ("harbour", "harbor", "quay"),
    "desert": ("desert", "dune"), "nile_bank": ("nile", "river"), "forum": ("forum", "market"),
    "olive_grove": ("olive", "grove"), "street": ("street",), "market_square": ("market", "square"),
    "farmyard": ("farm", "yard", "barn"),
}
NEAR_SETTINGS = ("grassland", "forest", "riverbank", "mountains")   # a night's walk from anywhere outdoors


def _words_pin(say: str, setting: str) -> bool:
    low = (say or "").lower()
    return any(w in low for w in SETTING_WORDS.get(setting, ()))


def repair_film(ep: dict, log=print, only_chapter: int | None = None) -> list[str]:
    """Hold a whole script to the picture rules, deterministically, and fix
    what the brain left: a chapter standing in one place at its three judged
    moments, one place owning too many of those moments, a scene too crowded
    for its shot, two neighbouring beats that are the same picture. Each fix
    is the smallest change that lowers the problem count — drop the last
    inessential prop, or move one beat to the least-used nearby place — and a
    beat whose words name its place is never moved. This is what the operator
    meant by "a system that makes good videos, not one good video": a rule the
    author cannot hold on its own output is a rule that lives as a hand edit
    to one script, and that is not a rule. Returns the notes of what changed."""
    import collections
    from data_learning import ori_sleep as OS
    era = ep["era"]
    keep = ("picture", "of the film", "new place", "crowded", "moves", "judged moments")

    def problems():
        out = []
        for i, c in enumerate(ep["chapters"]):
            if only_chapter is not None and i != only_chapter:
                continue
            for x in _chapter_problems(c["beats"], era, 0, 10 ** 6, before=ep["chapters"][:i]):
                if any(k in x for k in keep):
                    out.append((i, x))
        return out

    def flat_index(i, j):
        return sum(len(c["beats"]) for c in ep["chapters"][:i]) + j

    def severity():
        """Problems, weighted: a cap that is over by N counts N, so a move
        that brings a place from 7 of 18 to 6 of 18 is progress even while
        the message stands."""
        total = 0
        for _i, x in problems():
            m = re.search(r"would be (?:the picture at )?(\d+) of", x)
            total += 1 + (int(m.group(1)) if m else 0)
        return total

    def fit(i, j):
        """How well the scene fits, the worse of the render's own seed and
        the rule's fixed seed — so a repair satisfies the rule that raised
        the problem AND the picture that will be drawn."""
        sc = ep["chapters"][i]["beats"][j]["scene"]
        if S.validate(sc, era):
            return -1.0
        natural = 2.05 if S.shot_of(sc) == "close" else 1.25
        worst = 9.0
        for seed in (OS._scene_seed(ep["slug"], flat_index(i, j), sc), 1000 + j):
            lay = S.layout(sc, seed)
            worst = min(worst, -float(len(lay["collisions"])) if lay["collisions"] else lay["scale"] / natural)
        return worst

    def scene_ok(i, j):
        return fit(i, j) >= CROWD_SHRINK

    def candidates():
        used = collections.Counter(b["scene"].get("setting") for c in ep["chapters"] for b in c["beats"])
        near = [n for n in NEAR_SETTINGS if n in S.SETTINGS and era in S.SETTINGS[n].eras]
        return sorted(near, key=lambda n: used[n])

    def own_problems(k):
        return len(_chapter_problems(ep["chapters"][k]["beats"], era, 0, 10 ** 6, before=ep["chapters"][:k]))

    def try_move(i, j, guard=None):
        """Move beat j of chapter i to the least-used nearby place. `guard`
        names a chapter outside the repaired one whose own problem count
        may not rise for it."""
        b = ep["chapters"][i]["beats"][j]
        sc = b["scene"]
        if _words_pin(b.get("say", ""), sc.get("setting")):
            return None
        old = json.loads(json.dumps(sc))
        before = severity()
        guarded = own_problems(guard) if guard is not None else None
        for alt in candidates():
            if alt == old.get("setting"):
                continue
            sc["setting"] = alt
            sc["props"] = [q for q in sc.get("props", []) if (q if isinstance(q, str) else q["name"]) != "cave_painting"]
            if (scene_ok(i, j) and severity() < before
                    and (guard is None or own_problems(guard) <= guarded)):
                return f"{ep['chapters'][i]['title']} beat {j + 1}: {old.get('setting')} -> {alt}"
            sc.clear(); sc.update(old)
        return None

    def try_shot(i, j):
        """The other shot, for a beat whose words pin its place: the
        same-picture rule itself says "change the setting OR the shot"."""
        if j < 0:
            return None
        sc = ep["chapters"][i]["beats"][j]["scene"]
        old = json.loads(json.dumps(sc))
        before = severity()
        sc["shot"] = "close" if S.shot_of(sc) == "wide" else "wide"
        if S.validate(sc, era):
            mend_scene(sc, era)                    # a wide night wants its second light
        if not S.validate(sc, era) and scene_ok(i, j) and severity() < before:
            return f"{ep['chapters'][i]['title']} beat {j + 1}: {old.get('setting')} {S.shot_of(old)} -> {S.shot_of(sc)} shot"
        sc.clear(); sc.update(old)
        return None

    def try_drop(i, j):
        before = severity()
        sc = ep["chapters"][i]["beats"][j]["scene"]
        old = json.loads(json.dumps(sc))
        did = uncrowd_scene(sc, era, seeds=(OS._scene_seed(ep["slug"], flat_index(i, j), sc), 1000 + j))
        if did and severity() < before:
            return f"{ep['chapters'][i]['title']} beat {j + 1}: {did}"
        sc.clear(); sc.update(old)
        return None

    notes = []
    skipped = set()          # a problem nothing here can fix: say so once, honestly, and move on
    for _ in range(MAX_FILM_REPAIRS):
        ap = [(i, p) for i, p in problems() if (i, p) not in skipped]
        if not ap:
            break
        i, p = ap[0]
        beats = ep["chapters"][i]["beats"]
        marks = _mark_beats(beats)
        done = None
        m = re.search(r"beat (\d+)", p)
        if "crowded" in p and m:
            j = int(m.group(1)) - 1
            done = try_drop(i, j) or try_move(i, j) or try_shot(i, j)
        elif "moves" in p or "judged moments" in p:
            for j in (marks[1], marks[0], marks[2]) if len(marks) == 3 else marks:
                done = try_move(i, j)
                if done:
                    break
        elif "back to back" in p:
            m2 = re.search(r"beats (\d+) and", p)
            j = int(m2.group(1)) if m2 else 0
            done = try_move(i, j) or try_move(i, j - 1) or try_shot(i, j) or try_shot(i, j - 1)
        elif "new place" in p:
            # beat 1 first; when its words pin it, the previous chapter's
            # LAST beat moves instead (the fourth fresh-topic run: a chapter
            # opening in the village its words name, after a village close)
            done = try_move(i, 0)
            if not done and i > 0 and ep["chapters"][i - 1]["beats"]:
                done = try_move(i - 1, len(ep["chapters"][i - 1]["beats"]) - 1, guard=i - 1)
        else:
            # "<setting> would be N of the film's ..." or "N of M beats are the
            # same picture (<setting>, <shot> shot)": move a beat of that place,
            # a non-judged one first so the chapter's marks are not disturbed
            m3 = re.search(r"same picture \((\w+),", p)
            setting = m3.group(1) if m3 else p.split(" ")[0]
            order = [j for j in range(len(beats)) if j not in marks] + list(marks)
            for j in order:
                if beats[j]["scene"].get("setting") == setting:
                    done = try_move(i, j)
                    if done:
                        break
        if not done:
            log(f"[ori_author] repair_film could not fix (no move, drop or shot change here lowers it — "
                f"the words may pin those beats): {p[:120]}")
            skipped.add((i, p))
            continue
        notes.append(done)
        log(f"[ori_author] repair_film: {done}")
    if notes:
        ep.pop("storyboard", None)          # the board must look again
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--topic", default=None)
    ap.add_argument("--era", default=None, choices=S.ERAS)
    ap.add_argument("--if-empty", action="store_true",
                    help="write one script only if none is queued (the render needs one now)")
    args = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    want = args.count if args.count is not None else \
        max(0, int(cfg.get("queue_minimum", 1)) - len(queue()))
    if args.if_empty:
        want = 0 if queue() else 1
    if args.topic:
        era = args.era or era_for(args.topic)
        if era is None:
            print(f"[ori_author] the kit has no era for {args.topic!r} — it draws {', '.join(S.ERAS)}; "
                  f"add the era's settings and props to data_learning/doodle first, or pass --era", flush=True)
            return 2
        topics = [{"topic": args.topic, "era": era}]
        want = max(want, 1)
    else:
        done = used_topics()
        topics = [t for t in cfg["topics"] if t["topic"].lower() not in done]
    wrote = tried = 0
    for t in topics:
        # a bounded budget: a dark brain must cost minutes, not the run
        if wrote >= want or tried >= want + MAX_EXTRA_TOPICS:
            break
        tried += 1
        try:
            ep = author(t["topic"], t["era"])
        except NoBrain as e:
            # a dark brain costs one line, not a walk through the topic bank
            print(f"[ori_author] {e}", flush=True)
            break
        if ep is None:
            continue
        repair_film(ep)
        OS.EPISODES.mkdir(parents=True, exist_ok=True)
        path = OS.EPISODES / f"{ep['slug']}.json"
        path.write_text(json.dumps(ep, indent=1, ensure_ascii=False) + "\n")
        print(f"[ori_author] wrote {path.relative_to(REPO)}", flush=True)
        wrote += 1
    print(f"[ori_author] {wrote} written; queue now {len(queue())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
