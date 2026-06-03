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
that publishes 25-second doomscroll-style explainers. The audience wants tight, \
punchy "X is happening and here's why it matters" content with real stakes and \
real numbers. Output strict JSON only."""


RANKER_USER_TEMPLATE = """Here are {n} topics surfaced TODAY from Google Trends, BBC, NPR, \
Hacker News, and Reddit. Each line shows an age marker like [2h ago] when the \
source dated it. Many are duplicates (same story across feeds) and many are not \
video-able. Pick the top {top_k} that would make the best 25-second explainer shorts.

FRESHNESS IS THE #1 CRITERION. The channel publishes daily-news shorts — viewers \
expect "this just happened today." Strongly prefer items dated within the last 24 \
hours. Anything older than 48 hours should only be picked if it has a breaking \
update angle ("X is escalating today" / "new development in Y"). Reject anything \
that reads as evergreen, retrospective, or "X has been quietly happening for years" — \
those feel old even when the publish date is fresh.

CATEGORY DIVERSITY IS THE #2 CRITERION. This is a WIDE news channel, not a \
tech/AI channel. Hard rule: AT MOST 2 picks from any single category. The \
candidate list will be heavily skewed toward tech/AI because Hacker News \
dominates it — resist that. Aim for a balanced {top_k} across categories such as:

  - Tech / AI (max 2)
  - Business / Finance / Markets (earnings, M&A, stock moves)
  - World affairs / Geopolitics (conflicts, deals, foreign policy)
  - US news / Domestic policy (laws, regulations, federal actions — NOT election horserace)
  - Crime / Justice (arrests, verdicts, major investigations)
  - Science / Health / Medicine (breakthroughs, recalls, studies)
  - Climate / Environment / Disasters (weather events, climate moves)
  - Culture / Sports / Entertainment (one-off newsworthy moments, NOT live games or gossip)

If the input list doesn't have enough diversity to fill all categories, that's \
fine — just don't double up on whichever category is over-represented.

Reject (do not pick):
- Live sports games or sports player news (time-locked, narrow audience)
- Celebrity deaths, obituaries, "tribute" stories
- Stories about a specific person who isn't a household name in the US
- Political horserace stories (who's leading the primary, etc.)
- Stories with no concrete visual angle or stakes
- Pure entertainment gossip ("X is dating Y")
- Evergreen "explainer" topics that don't have a news hook today

Prefer within each category:
- TODAY'S breaking news with a clear "just happened" angle
- Stories with real numbers (death toll, dollar amount, percentage, vote count)
- "Why is X happening RIGHT NOW" stories where a 60-word script can explain a current event
- Cultural / viral phenomena currently trending (something that broke this week)

If two indices clearly cover the same news event, pick only the one with the \
best context, and mention the dupe in the angle ("BBC + Reddit both flagged").

For each pick output:
  - index: the 1-based index from the list below
  - topic: copy the topic text VERBATIM from the list (for alignment — must match)
  - score: 1-10 for how video-able this topic is (10 = guaranteed banger)
  - angle: ONE sentence describing the hook for the explainer that EXPLAINS THIS \
SPECIFIC TOPIC (not a different one). Example: for "VIX at 16" the angle would be \
"history shows calm markets always crash within months" — not commentary on unrelated stories.

Output JSON of the exact form:
{{"picks": [{{"index": N, "topic": "...", "score": N, "angle": "..."}}, ...]}}

Topics:
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

    user = RANKER_USER_TEMPLATE.format(
        n=len(topics), top_k=top_k, topics_block=_format_topics(topics),
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
