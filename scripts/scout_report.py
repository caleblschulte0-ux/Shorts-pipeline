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

print(f"Scouted **{d.get('total', 0)}** total candidates.")
print()
print(f"- Reddit (across {len(sources.get('reddit_subs', []))} subs): **{sources.get('reddit_count', 0)}** video posts")
print(f"- Wikipedia On This Day: **{sources.get('wikipedia_on_this_day_count', 0)}** historical events")
print(f"- Wikimedia Commons recent videos: **{sources.get('wikimedia_commons_count', 0)}** files")
print()

if reddit:
    print("### Top Reddit by score")
    for p in reddit[:10]:
        title = (p.get("title") or "").replace("[", "(").replace("]", ")")[:80]
        print(f"- **{p.get('score', 0):,}** r/{p.get('subreddit', '?')} — [{title}]({p.get('permalink', '')})")
    print()

if wikipedia:
    print("### Sample of Wikipedia On This Day")
    for e in wikipedia[:10]:
        year = e.get("year")
        text = (e.get("text") or "")[:120]
        page = e.get("page_url") or ""
        print(f"- **{year}** — {text} ([{e.get('page_title', '')}]({page}))")
    print()

if wikimedia:
    print("### Sample of Wikimedia recent videos")
    for v in wikimedia[:10]:
        print(f"- *{v.get('query')}* — [{v.get('title')}]({v.get('page_url')})")
    print()

print("Full list committed to `state/scouted_sources.json`.")
