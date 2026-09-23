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
  people doing what the words describe. Change the picture every beat; vary
  settings, shots and people across the chapter.
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


def _chapter_problems(beats, era: str, lo: int, hi: int) -> list[str]:
    if not isinstance(beats, list) or not beats:
        return ["no beats"]
    bad, total = [], 0
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
                else "This is the opening chapter: welcome the listener gently and set the scene.")
        final = ("- This is the LAST chapter: let the night grow deep and quiet, and end "
                 "with the people asleep and the listener invited to sleep too."
                 if i == len(chs) - 1 else "")
        res = _with_retry(
            lambda pr, i=i, ch=ch, prev=prev, final=final: CHAPTER.format(
                title=o["title"], era=era, n=i + 1, total=len(chs), chapter=ch.get("title", ""),
                covers=ch.get("covers", ""), prev=prev, words_lo=words_lo, words_hi=words_hi,
                final=final, vocab=vocab, problems=pr),
            lambda r: _chapter_problems(r.get("beats") if isinstance(r, dict) else None, era,
                                        words_lo - 100, words_hi + 200),
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
        topics = [{"topic": args.topic, "era": args.era or "stone_age"}]
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
