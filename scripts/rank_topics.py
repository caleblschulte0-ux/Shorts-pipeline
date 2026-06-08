#!/usr/bin/env python3
"""Rank raw discovered topics using an LLM so the operator (or the
script author) only sees the cream.

The discovery layer collects ~100 raw candidates per day across 5-10
sources. Most aren't worth a Short — live sports, obits, niche
celebrities, etc. Keyword heuristics catch the obvious ones but miss
nuance ("Hungary unlocks EU billions" is a great topic, but doesn't
match any positive-keyword list).

This module bundles the full candidate list into one Groq call and
asks the model to:
  * de-dupe stories that appear in multiple feeds (same news event)
  * skip topics that don't make good faceless explainers
  * score each surviving topic 1-10 for video-ability
  * suggest a one-line angle for the explainer

Returns the top N picks as enriched Topic objects (with .angle set).

Backend: re-uses script_generator._call_llm so the same Groq/Gemini/
Anthropic dispatch + UA handling applies. Defaults to Groq since it's
free and fast.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.discover_topic import Topic, discover_all, as_dict  # noqa: E402


RANKER_SYSTEM = """You curate trending news topics for a faceless YouTube Shorts channel \
that publishes 45-second doomscroll-style explainers. The audience wants tight, \
punchy "X is happening and here's why it matters" content with real stakes and \
real numbers. Output strict JSON only."""


RANKER_USER_TEMPLATE = """{n} topics surfaced TODAY from Google Trends, BBC, NPR, HN, Reddit, \
Google News quirky feeds. Each line has an age marker like [2h ago]. Many are \
duplicates across feeds and many aren't video-able. Pick the top {top_k} for \
45-second explainer shorts.

RULE 1 — FRESHNESS. Strongly prefer items <24h old. Items >48h old need a \
breaking-update angle to qualify. Reject anything evergreen / retrospective \
("X has been quietly happening for years").

RULE 2 — QUIRKY-HEAVY MIX. **At least {half_k} of {top_k} picks must be from \
the Quirky / Animal / Disaster bucket.** Channel analytics show these crush \
serious news — shark attack got 21 views vs. 0 for Nvidia earnings. The \
{half_k} quirky slots must cover at least TWO of these three sub-buckets:
  - **Animals / Wildlife** (escaped kangaroo named Hunter, shark attack, \
raccoon shuts down airport, world's biggest pumpkin)
  - **Weather / Natural disaster / Freak event** (meteor over Rome, F4 \
tornado, dust devil flips truck, sinkhole swallows house)
  - **Weird local / Quirky news** (NYC sewer mystery, town renames itself, \
Hell Michigan listed at $666K, blanket fort, 1M bees escape semi)

**Named-entity preference**: a story with a specific NAMED subject \
("Hunter the kangaroo", "Quantinuum IPO", "Twistex dashcam") strongly beats \
the generic version ("kangaroo escapes", "quantum stock IPOs", "tornado \
chaser video"). Named entities drive search demand that compounds for weeks.

Quirky = the SITUATION is weird, not the PERSON. Good shape: "1 million \
bees escape from semi on Tennessee highway", "United Airlines flight turned \
back over Bluetooth network name", "town renames itself to protest tax law", \
"world record pumpkin grown by amateur", "raccoon shuts down airport".

**Hard cap: at most 1 "Florida Man" / "local-arrest" / personality-based \
crime story per slate.** Three "Florida man does X" picks reads as fluff. \
If multiple surface, pick the single weirdest situation (radioactive device \
on Facebook > stolen garden gnomes > generic assault) and skip the rest.

MUST be real — if no wire/news outlet confirms, skip it (r/nottheonion gets \
satire reposts). NOT politics-with-quirky-frame, NOT heartwarming fluff, \
NOT celebrity gossip.

The other {other_k} picks fill these slots in order:
  - **1 hard-news slot** (one of: World affairs, US policy, Crime/Justice, \
Science/Health, Climate, Culture — rotate so the same category doesn't \
appear two days in a row)
  - **1 Tech/Markets slot — OPTIONAL, max 1.** Only include when the story \
has a NICHE named-entity angle that drives search demand (e.g. "Quantinuum \
IPO at $14B", "SpaceX Starship 11 launch"). SKIP generic earnings/AI hype \
("Apple revenue beat", "Nvidia ships new chip", "OpenAI raises funding") — \
those got 0 views on this channel. If nothing niche surfaces today, leave \
this slot empty and add another quirky pick instead.

If quirky is thin, top up serious. Never go below {top_k} just for purity.

REJECT:
- Live sports games / sports-player news
- Celebrity obituaries / tribute stories
- Stories about people who aren't household names in the US
- Political horserace ("X leads primary by 3 points")
- Stories with no concrete visual angle or stakes
- Pure gossip ("X is dating Y")
- Evergreen explainers without today's news hook
- Generic tech earnings / chip launches / funding rounds (zero views on \
this channel; only include tech when it has a named-entity search hook)
- **Ongoing war/conflict updates that are incremental** ("day 47 of...", \
"fighting continues", "casualties rise"). Only include conflict if today \
brought a major escalation, ceasefire, named-leader statement, or named-victim \
event — something new in the arc, not the next day.

DEDUP: If two indices cover the same event, pick the one with the best context \
and list every source that flagged it in the angle (e.g. "BBC + Reuters + \
Politico"). Multi-sourced stories are strongly preferred — load-bearing news, \
not one outlet's pet take.

For each pick output:
  - index: 1-based index from the list below
  - topic: copy the topic text VERBATIM from the list (must match exactly)
  - score: 1-10 (10 = guaranteed banger)
  - angle: ONE sentence describing the hook for THIS specific topic (not a \
different one). Example: for "Quantinuum IPO" → "history's first $14B \
quantum-computing IPO drops in a market that just lost $1T".

Output JSON only: {{"picks": [{{"index": N, "topic": "...", "score": N, "angle": "..."}}, ...]}}

{topics_block}
"""


def _age_hint(published_at: str | None) -> str:
    """Return a short '[2h ago]' / '[1d ago]' marker for the prompt so
    the ranker can see freshness at a glance."""
    if not published_at:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        hours = delta.total_seconds() / 3600.0
        if hours < 1:
            return f"[{int(delta.total_seconds() / 60)}m ago]"
        if hours < 24:
            return f"[{int(hours)}h ago]"
        return f"[{int(hours / 24)}d ago]"
    except (ValueError, TypeError):
        return ""


def _format_topics(topics: list[Topic], *, max_headline_chars: int = 140) -> str:
    """Render the candidate list as a numbered block for the prompt.
    We include source labels because the LLM uses them to dedupe and
    to weight (an HN-only story is different from a BBC-only story).
    Age markers like [2h ago] flag freshness for the ranker."""
    lines: list[str] = []
    for i, t in enumerate(topics, 1):
        srcs = ",".join(t.sources) if t.sources else "?"
        age = _age_hint(t.published_at)
        age_part = f" {age}" if age else ""
        headline = (t.headlines[0] if t.headlines else t.query)[:max_headline_chars]
        lines.append(f"{i}. [{srcs}]{age_part} {t.query[:80]}")
        if headline and headline != t.query:
            lines.append(f"     → {headline}")
        # Include second headline if it adds context (often it does for
        # Google Trends, which packs multiple news sources per item).
        if len(t.headlines) > 1:
            extra = t.headlines[1][:max_headline_chars]
            if extra and extra.lower() != headline.lower():
                lines.append(f"     → {extra}")
    return "\n".join(lines)


def rank(topics: list[Topic], *, top_k: int = 5, backend: str | None = None,
         model: str | None = None) -> list[Topic]:
    """Send candidates to the LLM, return the top_k picks as enriched
    Topic objects (with .score from the LLM and .angle populated)."""
    if not topics:
        return []
    # Lazy import — keeps discovery usable without the LLM dep installed.
    from script_generator import _call_llm

    # half_k = required minimum quirky/animal/disaster picks (the channel's
    # high-engagement bucket); other_k = max serious picks. Ratio shifted to
    # 2/3 quirky after channel analytics showed animal/quirky beats serious
    # news on every metric — see the rebrand doc.
    half_k = max(2, (top_k * 2) // 3)
    other_k = top_k - half_k
    user = RANKER_USER_TEMPLATE.format(
        n=len(topics), top_k=top_k,
        half_k=half_k, other_k=other_k,
        topics_block=_format_topics(topics),
    )
    raw = _call_llm(RANKER_SYSTEM, user, backend=backend, model=model)
    # _call_llm returns the raw string content. Strip fences just in
    # case (some backends ignore JSON-mode).
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)

    picks: list[Topic] = []
    for p in data.get("picks", [])[:top_k]:
        try:
            i = int(p["index"]) - 1
        except (KeyError, ValueError, TypeError):
            continue
        if not (0 <= i < len(topics)):
            continue
        t = topics[i]

        # Sanity-check the model's index vs the topic text it echoed
        # back. If they don't match (Llama sometimes shifts indices vs
        # the angle it's emitting), try to recover by matching on the
        # echoed topic text instead.
        echo = (p.get("topic") or "").strip().lower()
        if echo:
            actual = t.query.strip().lower()
            if echo[:30] not in actual and actual[:30] not in echo:
                # Find the topic whose query best matches the echoed text.
                best_i, best_score = i, 0
                for j, cand in enumerate(topics):
                    cq = cand.query.lower()
                    if cq[:30] in echo or echo[:30] in cq:
                        best_i = j
                        best_score = len(set(cq.split()) & set(echo.split()))
                        if best_score >= 3:
                            break
                if best_i != i:
                    print(f"[rank] index drift: model said {i+1} but topic '{echo[:40]}' "
                          f"matches {best_i+1} — using {best_i+1}", file=sys.stderr)
                    i = best_i
                    t = topics[i]

        try:
            t.score = float(p.get("score", 0))
        except (TypeError, ValueError):
            t.score = 0.0
        t.angle = (p.get("angle") or "").strip() or None
        picks.append(t)
    picks.sort(key=lambda x: -x.score)
    return picks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=5,
                    help="how many picks to return (default 5)")
    ap.add_argument("--backend", choices=("groq", "gemini", "anthropic"),
                    help="force a specific LLM backend (default: auto)")
    ap.add_argument("--model", help="override model name")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of human-readable text")
    args = ap.parse_args()

    print("[rank] running multi-source discovery...", file=sys.stderr)
    raw = discover_all()
    print(f"[rank] {len(raw)} raw candidates; asking LLM to pick top {args.top_k}...",
          file=sys.stderr)

    picks = rank(raw, top_k=args.top_k, backend=args.backend, model=args.model)

    if args.json:
        print(json.dumps([as_dict(t) | {"angle": t.angle} for t in picks], indent=2))
    else:
        for i, t in enumerate(picks, 1):
            print(f"{i}. [{t.score:>4.1f}/10] {t.query}")
            if t.angle:
                print(f"     angle: {t.angle}")
            srcs = ",".join(t.sources[:4])
            print(f"     sources: {srcs}")
            if t.urls:
                print(f"     url: {t.urls[0]}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
