#!/usr/bin/env python3
"""Format the scouted_sources.json into a markdown comment for the
tracking issue. Reads state/scouted_sources.json; prints markdown to
stdout."""
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "state" / "scouted_sources.json"

if not PATH.exists():
    print("no scouted_sources.json on disk")
    sys.exit(0)

d = json.loads(PATH.read_text())
sources = d.get("sources", {})
reddit = d.get("reddit_posts", [])
wikipedia = d.get("wikipedia_events", [])
wikimedia = d.get("wikimedia_videos", [])
youtube = d.get("youtube_trending", [])
lemmy = d.get("lemmy_posts", [])
hn = d.get("hackernews_posts", [])

print(f"Scouted **{d.get('total', 0)}** total candidates across 6 sources.")
print()
print(f"- Reddit: **{sources.get('reddit_count', 0)}**")
print(f"- Wikipedia On This Day: **{sources.get('wikipedia_on_this_day_count', 0)}**")
print(f"- Wikimedia Commons: **{sources.get('wikimedia_commons_count', 0)}**")
print(f"- YouTube Trending: **{sources.get('youtube_trending_count', 0)}**")
print(f"- Lemmy: **{sources.get('lemmy_count', 0)}**")
print(f"- Hacker News: **{sources.get('hackernews_count', 0)}**")
print()

if youtube:
    print("### YouTube Trending — top 10 by views")
    for v in sorted(youtube, key=lambda x: x.get("views", 0), reverse=True)[:10]:
        title = (v.get("title") or "").replace("[", "(").replace("]", ")")[:80]
        print(f"- **{v.get('views', 0):,}** views — [{title}]({v.get('url', '')}) ({v.get('channel', '?')})")
    print()

if lemmy:
    print("### Lemmy — top 10 by score")
    for p in lemmy[:10]:
        title = (p.get("title") or "").replace("[", "(").replace("]", ")")[:80]
        print(f"- **{p.get('score', 0):,}** c/{p.get('community', '?')} ({p.get('instance', '?')}) — [{title}]({p.get('url', '')})")
    print()

if hn:
    print("### Hacker News — top 10 video links")
    for p in hn[:10]:
        title = (p.get("title") or "").replace("[", "(").replace("]", ")")[:80]
        print(f"- **{p.get('score', 0):,}** — [{title}]({p.get('url', '')}) (HN: {p.get('permalink', '')})")
    print()

if reddit:
    print("### Top Reddit by score")
    for p in reddit[:10]:
        title = (p.get("title") or "").replace("[", "(").replace("]", ")")[:80]
        print(f"- **{p.get('score', 0):,}** r/{p.get('subreddit', '?')} — [{title}]({p.get('permalink', '')})")
    print()

if wikipedia:
    print("### Wikipedia On This Day — recent (this century)")
    recent = [e for e in wikipedia if (e.get("year") or 0) >= 2000]
    for e in sorted(recent, key=lambda x: x.get("year") or 0, reverse=True)[:10]:
        text = (e.get("text") or "")[:120]
        print(f"- **{e.get('year')}** — {text}")
    print()

if wikimedia:
    print("### Wikimedia recent videos")
    for v in wikimedia[:10]:
        print(f"- *{v.get('query')}* — [{v.get('title')}]({v.get('page_url')})")
    print()

print("Full list committed to `state/scouted_sources.json`.")
