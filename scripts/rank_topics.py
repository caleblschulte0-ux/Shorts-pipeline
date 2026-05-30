#!/usr/bin/env python3
"""Fetch and rank today's trending topics for short-form video.

Pulls headlines from RSS feeds, then uses Groq (fast Llama inference) to
score each headline by short-video viability and return the top-k.

Usage:
    python3 scripts/rank_topics.py --top-k 10
    GROQ_API_KEY=gsk_... python3 scripts/rank_topics.py --top-k 10
    python3 scripts/rank_topics.py --top-k 10 --output topics.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://abcnews.go.com/abcnews/topstories",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://techcrunch.com/feed/",
]

SCORING_PROMPT = """You are a YouTube Shorts producer ranking news headlines by video-ability.

Score each headline 1-10:
  8-10: Clear visual story, surprising stat or moment, self-contained, explainable in 60 words
  5-7:  Interesting but needs context or lacks strong visual hook
  1-4:  Live sports scores, obituaries, election/war diplomacy, too abstract or complex

Hard EXCLUDE (score 0): live sports, obits, election results, war/ceasefire negotiations,
diplomatic meetings, anything requiring >60 words to make sense.

Return ONLY valid JSON array, no markdown, no explanation:
[{{"rank":1,"headline":"...","score":9.5,"reason":"one sentence why"}}]

Rank by score descending. Headlines to score:
{headlines}"""


def fetch_rss(url: str, timeout: int = 10) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendingShorts/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            root = ET.fromstring(resp.read())
        titles: list[str] = []
        for item in root.iter("item"):
            title = item.find("title")
            if title is not None and title.text:
                titles.append(title.text.strip())
        return titles[:15]
    except Exception as e:
        print(f"  WARN {url}: {e}", file=sys.stderr)
        return []


def rank_with_groq(headlines: list[str], api_key: str, top_k: int) -> list[dict]:
    numbered = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(headlines))
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "user", "content": SCORING_PROMPT.format(headlines=numbered)}],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    content = data["choices"][0]["message"]["content"]
    start = content.find("[")
    end = content.rfind("]") + 1
    ranked = json.loads(content[start:end])
    return [r for r in ranked if r.get("score", 0) >= 5][:top_k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--output", help="write JSON to file instead of stdout")
    ap.add_argument("--feeds", nargs="*", default=RSS_FEEDS)
    args = ap.parse_args()

    print("Fetching RSS feeds...", file=sys.stderr)
    all_headlines: list[str] = []
    for url in args.feeds:
        titles = fetch_rss(url)
        print(f"  {url}: {len(titles)} items", file=sys.stderr)
        all_headlines.extend(titles)

    seen: set[str] = set()
    unique: list[str] = []
    for h in all_headlines:
        key = h.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(h)
    print(f"Total unique headlines: {len(unique)}", file=sys.stderr)

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("WARN: GROQ_API_KEY not set — returning unranked top headlines", file=sys.stderr)
        result = [
            {"rank": i + 1, "headline": h, "score": None, "reason": "no API key"}
            for i, h in enumerate(unique[: args.top_k])
        ]
    else:
        print(f"Ranking {len(unique)} headlines with Groq...", file=sys.stderr)
        try:
            result = rank_with_groq(unique, api_key, args.top_k)
        except Exception as e:
            print(f"ERROR: Groq ranking failed: {e}", file=sys.stderr)
            result = [
                {"rank": i + 1, "headline": h, "score": None, "reason": "ranking error"}
                for i, h in enumerate(unique[: args.top_k])
            ]

    output_str = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(output_str + "\n")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(output_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
