#!/usr/bin/env python3
"""Discover today's trending topics that are actually video-able.

Pulls Google's "Daily Search Trends" RSS feed, which gives us raw search
trends with the news headlines that drove each spike. We filter out
topics that don't make good faceless-explainer fodder (live sports
games, celebrity obits, niche political flare-ups) and rank the rest by
search volume plus a topic-friendliness score.

Output: a ranked list of topic dicts, each with the raw query, the news
context, and a confidence score. Downstream the script generator picks
the top one and asks Claude to turn it into a 25-second script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


TRENDS_RSS = "https://trends.google.com/trending/rss?geo=US&hours=24"

# Namespace used by the Google Trends RSS extension.
NS = {"ht": "https://trends.google.com/trending/rss"}


# Keyword scoring. Positive keywords mean the topic probably has a story
# we can explain in 60-80 words with stock footage; negative keywords
# flag topics that fall apart on a faceless channel (live games,
# specific dead people, individual political horserace stuff).
POSITIVE_KEYWORDS = {
    # Tech / business
    "stock": 8, "ipo": 8, "earnings": 6, "layoffs": 10, "lawsuit": 6,
    "lawsuit": 6, "acquisition": 6, "merger": 6, "bankruptcy": 9,
    "recall": 8, "shortage": 7, "ban": 6, "boycott": 6,
    "ceo": 4, "founder": 4, "billionaire": 5,
    # Products / launches
    "launches": 6, "released": 4, "release": 4, "leak": 5, "leaked": 5,
    "price": 5, "raises": 4, "raise": 4, "discontinued": 7,
    # Economy
    "inflation": 8, "interest": 4, "rates": 4, "housing": 6, "rent": 6,
    "wages": 6, "tax": 4, "tariff": 7, "recession": 8,
    # Phenomena
    "viral": 6, "tiktok": 4, "trend": 3, "ai": 5,
    "scandal": 7, "controversy": 5, "exposed": 6,
}

# Hard skips. Any of these in the trend or news text → score below floor.
NEGATIVE_KEYWORDS = {
    # Live sports / time-locked
    "vs": -20, "vs.": -20, "match": -15, "game": -8, "score": -10,
    "playoffs": -20, "championship": -15, "tournament": -10,
    "nfl": -15, "nba": -15, "mlb": -15, "nhl": -15, "ncaa": -15,
    "premier league": -20, "champions league": -20, "world cup": -20,
    "french open": -20, "wimbledon": -20, "us open": -20,
    "live updates": -20, "live blog": -20, "today's game": -20,
    # Death / obit
    "dies": -50, "died": -50, "death": -30, "passes away": -50,
    "obituary": -50, "tribute": -30, "in memoriam": -50,
    "killed": -30, "murdered": -30, "shot dead": -50,
    # Adult / sensitive
    "porn": -100, "onlyfans": -50, "nude": -50,
    # Politics horserace (channel-risk)
    "primary election": -20, "midterms": -20, "campaign rally": -20,
    "endorses": -10,
}

# Domain hints: news source URLs that suggest a topic is/isn't usable.
SOURCE_PENALTY = {
    "espn.com": -25, "foxsports.com": -25, "skysports.com": -25,
    "rolandgarros.com": -30, "wimbledon.com": -30,
}


@dataclass
class Topic:
    query: str
    traffic: int = 0
    score: float = 0.0
    headlines: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


def _parse_traffic(s: str | None) -> int:
    """'2000+' / '50,000+' / '100K+' -> integer estimate."""
    if not s:
        return 0
    s = s.strip().rstrip("+").replace(",", "").lower()
    mult = 1
    if s.endswith("k"):
        mult = 1_000
        s = s[:-1]
    elif s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def _fetch_trends() -> bytes:
    req = urllib.request.Request(
        TRENDS_RSS,
        headers={"User-Agent": "shorts-pipeline/1.0", "Accept": "application/rss+xml"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _score(topic: Topic) -> float:
    """Heuristic score: higher is more video-able. Combines keyword
    sentiment with search traffic. The negative keywords act as hard
    skips since they easily reach -100 and dominate any positive."""
    text = " ".join([
        topic.query,
        *topic.headlines,
        *topic.snippets,
    ]).lower()

    kw_score = 0.0
    for kw, w in POSITIVE_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text):
            kw_score += w
    for kw, w in NEGATIVE_KEYWORDS.items():
        if kw in text:  # substring match — these are usually multi-word
            kw_score += w
    for src in topic.sources:
        for needle, w in SOURCE_PENALTY.items():
            if needle in src:
                kw_score += w

    # Traffic contributes log-scaled. 1k -> +3, 10k -> +4, 100k -> +5.
    import math
    traffic_score = math.log10(max(1, topic.traffic)) if topic.traffic else 0

    return kw_score + traffic_score


def discover(rss_bytes: bytes | None = None, min_score: float = 4.0) -> list[Topic]:
    raw = rss_bytes if rss_bytes is not None else _fetch_trends()
    root = ET.fromstring(raw)
    items = root.findall("./channel/item")

    topics: list[Topic] = []
    for it in items:
        t = Topic(query=(it.findtext("title") or "").strip())
        t.traffic = _parse_traffic(it.findtext("ht:approx_traffic", namespaces=NS))
        for ni in it.findall("ht:news_item", NS):
            hl = (ni.findtext("ht:news_item_title", namespaces=NS) or "").strip()
            sn = (ni.findtext("ht:news_item_snippet", namespaces=NS) or "").strip()
            src = (ni.findtext("ht:news_item_source", namespaces=NS) or "").strip()
            url = (ni.findtext("ht:news_item_url", namespaces=NS) or "").strip()
            if hl: t.headlines.append(hl)
            if sn: t.snippets.append(sn)
            if src: t.sources.append(src)
            if url: t.urls.append(url)
        t.score = _score(t)
        topics.append(t)

    topics.sort(key=lambda x: -x.score)
    return [t for t in topics if t.score >= min_score]


def as_dict(t: Topic) -> dict:
    return {
        "query": t.query, "traffic": t.traffic, "score": round(t.score, 2),
        "headlines": t.headlines, "snippets": t.snippets,
        "sources": t.sources, "urls": t.urls,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="max topics to print")
    ap.add_argument("--min-score", type=float, default=4.0, help="floor on heuristic score")
    ap.add_argument("--json", action="store_true", help="emit JSON for machine use")
    args = ap.parse_args()

    topics = discover(min_score=args.min_score)[:args.limit]
    if args.json:
        print(json.dumps([as_dict(t) for t in topics], indent=2))
    else:
        for i, t in enumerate(topics, 1):
            print(f"{i:2d}. [{t.score:>5.1f}] {t.query!r:35} traffic={t.traffic}")
            for hl in t.headlines[:2]:
                print(f"      - {hl[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
