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

# Reddit blocks both shared-IP and bot-style User-Agents pretty aggressively
# on www.reddit.com. old.reddit.com is more lenient. We also rotate UAs so
# a single block doesn't kill the whole scout.
UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

REDDIT_HOSTS = ["https://old.reddit.com", "https://www.reddit.com"]


def _headers(ua_idx: int = 0) -> dict:
    return {
        "User-Agent": UAS[ua_idx % len(UAS)],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }


def fetch_subreddit_top(sub: str, t: str = "week", limit: int = 25) -> list[dict]:
    last_err = None
    for host_idx, host in enumerate(REDDIT_HOSTS):
        url = f"{host}/r/{sub}/top.json?t={t}&limit={limit}"
        req = urllib.request.Request(url, headers=_headers(host_idx))
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                break
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} from {host}"
            continue
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue
    else:
        print(f"[{sub}] all hosts failed: {last_err}", file=sys.stderr)
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


def fetch_wikipedia_on_this_day() -> list[dict]:
    """Wikipedia's "On This Day" feed — events that happened on this date
    in history, each with a linked article and (often) a thumbnail. Open
    API, no auth, never IP-blocks."""
    now = datetime.now(timezone.utc)
    url = (
        "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/"
        f"{now.month:02d}/{now.day:02d}"
    )
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"[wikipedia/onthisday] {type(e).__name__}: {e}", file=sys.stderr)
        return []

    out: list[dict] = []
    for kind in ("selected", "events", "births", "deaths"):
        for item in data.get(kind, [])[:30]:
            year = item.get("year")
            text = (item.get("text") or "").strip()
            pages = item.get("pages") or []
            if not text or not pages:
                continue
            page = pages[0]
            thumb = (page.get("thumbnail") or {}).get("source")
            out.append({
                "source_type": "wikipedia_on_this_day",
                "kind": kind,
                "year": year,
                "text": text,
                "page_title": page.get("titles", {}).get("normalized") or page.get("title"),
                "page_url": page.get("content_urls", {}).get("desktop", {}).get("page"),
                "thumbnail": thumb,
                "extract": (page.get("extract") or "").strip()[:500],
            })
    return out


def fetch_wikimedia_recent_videos(limit: int = 50) -> list[dict]:
    """Hit the Wikimedia Commons search API for recently uploaded videos
    in interesting categories. Doesn't give us viral, but gives us *real*
    fresh footage we can hook a story to."""
    out: list[dict] = []
    queries = [
        "tornado", "lightning", "volcano", "eruption", "avalanche",
        "earthquake", "tsunami", "hurricane", "wildfire",
        "wildlife", "predator", "hunt",
        "explosion", "rocket launch",
    ]
    for q in queries:
        url = (
            "https://commons.wikimedia.org/w/api.php"
            f"?action=query&list=search&srsearch={q}+filetype:video"
            f"&srsort=create_timestamp_desc&srlimit=5&format=json"
        )
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"[wikimedia/{q}] {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for item in (data.get("query", {}).get("search") or [])[:limit]:
            title = item.get("title") or ""
            if not title.lower().startswith("file:"):
                continue
            out.append({
                "source_type": "wikimedia_commons_video",
                "query": q,
                "title": title,
                "page_url": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
                "timestamp": item.get("timestamp"),
            })
        time.sleep(0.5)
    return out


def main() -> int:
    all_reddit: list[dict] = []
    for sub in SUBREDDITS:
        print(f"scouting r/{sub}...")
        posts = fetch_subreddit_top(sub, t="week", limit=25)
        print(f"  +{len(posts)} video posts")
        all_reddit.extend(posts)
        time.sleep(2)
    all_reddit.sort(key=lambda p: p.get("score", 0), reverse=True)
    all_reddit = all_reddit[:200]

    print("\nscouting Wikipedia On This Day...")
    wikipedia = fetch_wikipedia_on_this_day()
    print(f"  +{len(wikipedia)} historical events")

    print("\nscouting Wikimedia Commons newest videos...")
    wikimedia = fetch_wikimedia_recent_videos()
    print(f"  +{len(wikimedia)} recent video files")

    total = len(all_reddit) + len(wikipedia) + len(wikimedia)
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "scouted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "reddit_subs": SUBREDDITS,
            "reddit_count": len(all_reddit),
            "wikipedia_on_this_day_count": len(wikipedia),
            "wikimedia_commons_count": len(wikimedia),
        },
        "total": total,
        "reddit_posts": all_reddit,
        "wikipedia_events": wikipedia,
        "wikimedia_videos": wikimedia,
    }, indent=2) + "\n")
    print(f"\nwrote {total} candidates -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
