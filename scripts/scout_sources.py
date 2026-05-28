#!/usr/bin/env python3
"""Scout trending video posts from places the Claude container's egress
proxy blocks. Runs from a GitHub Actions runner (which has open egress).

Output: state/scouted_sources.json — a list of candidate Reddit posts
with video URLs, sorted by score. The chat-side workflow reads that file
to populate scripts/catalog.py with fresh entries.

Run weekly (or on demand via workflow_dispatch).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "state" / "scouted_sources.json"

# Brain-rot Shorts vibe — strong reaction footage, fast hooks, viral
# potential. Tune the mix here.
SUBREDDITS = [
    "PublicFreakout",
    "SweatyPalms",
    "NatureIsFuckingLit",
    "BeAmazed",
    "Damnthatsinteresting",
    "interestingasfuck",
    "IdiotsInCars",
    "Unexpected",
    "instant_regret",
    "instantkarma",
    "MadeMeSmile",
    "nextfuckinglevel",
    "HumansBeingBros",
    "facepalm",
    "WTF",
]

HEADERS = {
    "User-Agent": "shorts-pipeline-scout/1.0 (by github-actions; +https://github.com/caleblschulte0-ux/shorts-pipeline)",
    "Accept": "application/json",
}


def fetch_subreddit_top(sub: str, t: str = "week", limit: int = 25) -> list[dict]:
    url = f"https://www.reddit.com/r/{sub}/top.json?t={t}&limit={limit}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"[{sub}] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:  # noqa: BLE001
        print(f"[{sub}] {type(e).__name__}: {e}", file=sys.stderr)
        return []

    out: list[dict] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        media = (d.get("secure_media") or d.get("media") or {}) or {}
        reddit_video = (media.get("reddit_video") or {}) if isinstance(media, dict) else {}
        fallback_url = reddit_video.get("fallback_url") if isinstance(reddit_video, dict) else None
        post_url = d.get("url") or ""
        is_reddit_video = bool(fallback_url) or "v.redd.it" in post_url
        is_external_video = any(
            host in post_url
            for host in ("youtube.com", "youtu.be", "vimeo.com", "streamable.com")
        )
        if not (is_reddit_video or is_external_video):
            continue
        if d.get("over_18"):
            continue

        out.append({
            "subreddit": sub,
            "id": d.get("id"),
            "title": (d.get("title") or "").strip(),
            "permalink": "https://www.reddit.com" + (d.get("permalink") or ""),
            "url": post_url,
            "video_url": fallback_url,
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
            "duration_sec": int(reddit_video.get("duration") or 0) if isinstance(reddit_video, dict) else 0,
            "created_utc": int(d.get("created_utc") or 0),
        })
    return out


def main() -> int:
    all_posts: list[dict] = []
    for sub in SUBREDDITS:
        print(f"scouting r/{sub}...")
        posts = fetch_subreddit_top(sub, t="week", limit=25)
        print(f"  +{len(posts)} video posts")
        all_posts.extend(posts)
        time.sleep(2)  # polite rate-limit

    # Sort by upvotes; keep the top 200 to bound file size.
    all_posts.sort(key=lambda p: p.get("score", 0), reverse=True)
    all_posts = all_posts[:200]

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "scouted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subreddits": SUBREDDITS,
        "total": len(all_posts),
        "posts": all_posts,
    }, indent=2) + "\n")
    print(f"\nwrote {len(all_posts)} posts -> {OUT_PATH}")
    if all_posts:
        print("\ntop 10 by score:")
        for p in all_posts[:10]:
            print(f"  {p['score']:>7,} r/{p['subreddit']:24s} | {p['title'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
