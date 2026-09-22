#!/usr/bin/env python3
"""Write the next OpenRangeInteractive documentary EPISODE script.

Keeps `data_learning/ori_episodes/` stocked so the channel never stops for
want of a script. Picks the first topic from `data_learning/ori.config.json`
no episode covers yet, asks a brain for a script in the episode contract,
and runs it through `ori_documentary.validate` — the same structural gate a
hand-written script passes. A reply that fails is sent back ONCE with the
exact problems; one that still fails is dropped, never written.

The brain is the channel's usual chain (`shared.script_generator._call_llm`:
the Claude subscription CLI and the free keys) with the mailbox excluded —
a documentary script that no model wrote this run is not one to render.

    python scripts/ori_author.py              # top up to queue_minimum
    python scripts/ori_author.py --count 2    # write exactly two
    python scripts/ori_author.py --topic "How lightning actually works"
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

from data_learning import ori_documentary as OD      # noqa: E402

CONFIG = REPO / "data_learning" / "ori.config.json"
#: topics tried beyond the number wanted before the author gives up for the run
MAX_EXTRA_TOPICS = 1
#: a 1,500-word script is not a one-line judgement; the shared CLI default
#: (90s) is sized for the latter and timed every attempt out in CI
os.environ.setdefault("CLAUDE_CLI_TIMEOUT", "600")
POSTED = REPO / "state" / "curiosity_posted_log.json"

SYSTEM = """You write narration scripts for OpenRangeInteractive, a faceless \
documentary YouTube channel: calm narration over real stock footage, 8-10 \
minutes, evergreen curiosity topics. Your script is rendered automatically, \
so you return ONLY one JSON object, no prose, no code fences."""

BRIEF = """Write one episode on: {topic}

THE JSON CONTRACT (every key required unless marked optional):
{{
  "slug": "kebab-case-from-the-title",
  "title": "20-70 chars, a promise the video keeps, front-loaded, no clickbait lies",
  "thumbnail_text": "2-4 WORDS that make someone click (not the title repeated)",
  "thumbnail_shots": ["2-4 word stock footage search", "..."],
  "description": "2-3 sentences for the YouTube description",
  "tags": ["8-12 lowercase tags"],
  "chapters": [
    {{"title": "Intro", "beats": [ BEAT, ... ]}},
    {{"title": "Short chapter title", "beats": [ BEAT, ... ]}}
  ],
  "sources": [{{"name": "publisher - page title", "url": "https://..."}}]
}}
BEAT = {{"say": "1-3 sentences of narration",
         "shots": ["2-4 word stock video search", "another"],
         "stat": {{"value": "12,262 m", "label": "what the number is"}}  (optional)}}

RULES — a script that breaks one is thrown away:
- 6-9 chapters. The first is the cold open titled "Intro": 3 beats, open on
  the single most surprising fact, then promise the journey. No "welcome
  back", no "in this video", no channel name.
- 1250-1650 narrated words in total. Plain spoken English, second person,
  short sentences. Each chapter escalates; the reveal comes late.
- ONLY well-established facts you are certain of, rounded honestly ("about",
  "nearly"). No invented numbers, no contested claims, no dates you are not
  sure of. Every number you say appears in digits in "say".
- A "stat" appears on screen while its beat is spoken: its "value" MUST be
  written in digits inside that same beat's "say". Use 6-12 stats, only on
  the numbers that matter.
- "shots": 2-3 per beat, concrete things a stock library films: "ocean waves
  aerial", "scientist microscope", "lightning storm night". Never abstract
  ("the concept of time"), never a named person, logo or brand, never text.
- The last beat asks the viewer one specific question to answer in the
  comments.
- 4-8 sources with real, stable https URLs (NASA, NOAA, USGS, national
  academies, encyclopedias, university pages). Never invent a URL.
{problems}"""


def used_topics() -> set[str]:
    out = set()
    for p in OD.EPISODES.glob("*.json"):
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
    for p in OD.EPISODES.glob("*.json"):
        try:
            ep = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if ep.get("slug") in posted or OD.validate(ep):
            continue
        items.append((ep.get("added", ""), ep["slug"]))
    return [s for _, s in sorted(items)]


def _parse(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])


def _ask(system: str, user: str) -> str:
    """The brain chain without the mailbox (see module docstring)."""
    from shared import script_generator as sg
    errs = []
    # the strongest writer first: a ten-minute script is not a caption
    order = {"claude_cli": 0, "anthropic": 1, "gemini": 2, "groq": 3}
    chain = sorted((c for c in sg._LLM_CHAIN if c[0] in order),
                   key=lambda c: order[c[0]])
    for name, env, call in chain:
        if env and not os.environ.get(env):
            continue
        try:
            return call(system, user, None)
        except Exception as e:                           # noqa: BLE001
            errs.append(f"{name}: {str(e)[:100]}")
    raise RuntimeError("no brain answered: " + " | ".join(errs or ["none configured"]))


def author(topic: str, ask=_ask) -> dict | None:
    problems = ""
    for attempt in (1, 2):
        try:
            ep = _parse(ask(SYSTEM, BRIEF.format(topic=topic, problems=problems)))
        except Exception as e:                           # noqa: BLE001
            print(f"[ori_author] {topic!r} attempt {attempt}: {e}", flush=True)
            continue
        bad = OD.validate(ep)
        if (OD.EPISODES / f"{ep.get('slug')}.json").exists():
            bad.append(f"slug {ep.get('slug')!r} already exists — choose another")
        if not bad:
            ep["topic"] = topic
            ep["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            ep["authored_by"] = "ori_author"
            return ep
        print(f"[ori_author] {topic!r} attempt {attempt} invalid: {bad[:6]}",
              flush=True)
        problems = ("\nYOUR LAST ATTEMPT WAS REJECTED FOR: " + "; ".join(bad)
                    + "\nFix every one.")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--topic", default=None)
    args = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    want = args.count if args.count is not None else \
        max(0, int(cfg.get("queue_minimum", 3)) - len(queue()))
    if args.topic:
        topics = [args.topic]
        want = max(want, 1)
    else:
        done = used_topics()
        topics = [t for t in cfg["topics"] if t.lower() not in done]
    wrote = tried = 0
    for t in topics:
        # a bounded budget: a dark brain must cost minutes, not the run
        if wrote >= want or tried >= want + MAX_EXTRA_TOPICS:
            break
        tried += 1
        ep = author(t)
        if ep is None:
            continue
        OD.EPISODES.mkdir(parents=True, exist_ok=True)
        path = OD.EPISODES / f"{ep['slug']}.json"
        path.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n")
        print(f"[ori_author] wrote {path.relative_to(REPO)}", flush=True)
        wrote += 1
    print(f"[ori_author] {wrote} written; queue now {len(queue())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
