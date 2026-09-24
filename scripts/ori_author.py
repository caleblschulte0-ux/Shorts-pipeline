#!/usr/bin/env python3
"""Write the next OpenRangeInteractive SLEEP FILM script.

Keeps `data_learning/ori_episodes/` stocked so the weekly film never stops
for want of a script. A two-hour script (~14,000 words) is not one answer, so
it is written the way a person would write it: an OUTLINE first (title,
thumbnail, era, 12-15 chapters with what each covers), then EACH CHAPTER in
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
14-16 chapters. The first opens gently (welcome, settle in, where and when we are).
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
    if not (14 <= n <= 16):
        bad.append(f"{n} chapters (14-16)")
    return bad


SAME_LOOK_SHARE = 0.5      # at most half a chapter's beats may share one setting+shot
IDLE_SHARE = 0.3           # at most three in ten peopled beats may show everyone idle
FILM_LOOK_SHARE = 0.2      # ... and at most one in five of the whole film's
FILM_PLACE_SHARE = 0.25
CROWD_SHRINK = 0.8         # a scene the layout must draw smaller than this fraction of natural size is too crowded    # ... and no one SETTING, whatever the shot, past a quarter of the film


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


def _with_retry(prompt_fn, check, ask, label):
    problems = ""
    for attempt in (1, 2):
        try:
            out = _parse(ask(SYSTEM, prompt_fn(problems)))
        except NoBrain:
            raise
        except Exception as e:                           # noqa: BLE001
            print(f"[ori_author] {label} attempt {attempt}: {e}", flush=True)
            problems = f"\nYOUR LAST ANSWER COULD NOT BE READ AS JSON ({str(e)[:80]}). Return only JSON."
            continue
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
    o = _with_retry(lambda pr: OUTLINE.format(topic=topic, era=era, suffix=SUFFIX, vocab=vocab) + pr,
                    lambda o: _outline_problems(o, era), ask, f"{topic!r} outline")
    if o is None:
        return None
    chs = o["chapters"]
    words_lo, words_hi = 1000, 1400
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
                                                            words_lo - 100, words_hi + 200, before=before,
                                                            opening=(i == 0)),
            ask, f"{topic!r} chapter {i + 1}")
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
        OS.EPISODES.mkdir(parents=True, exist_ok=True)
        path = OS.EPISODES / f"{ep['slug']}.json"
        path.write_text(json.dumps(ep, indent=1, ensure_ascii=False) + "\n")
        print(f"[ori_author] wrote {path.relative_to(REPO)}", flush=True)
        wrote += 1
    print(f"[ori_author] {wrote} written; queue now {len(queue())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
