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
posts = d.get("posts", [])
subs = d.get("subreddits", [])

print(f"Found **{d.get('total', len(posts))}** trending video posts across **{len(subs)}** subreddits.")
print()
print("Top 15 by score:")
print()
for p in posts[:15]:
    title = (p.get("title") or "").replace("[", "(").replace("]", ")")[:80]
    print(f"- **{p.get('score', 0):,}** r/{p.get('subreddit', '?')} — [{title}]({p.get('permalink', '')})")
print()
print(f"Full list committed to `state/scouted_sources.json`.")
