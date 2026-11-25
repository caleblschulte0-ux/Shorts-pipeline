"""Which free route still lists the week's top sports posts from a GitHub
runner (2026-11-18 onward: the API 403'd, the RSS feed 404/429'd and
PullPush 429'd on every sub, and Baller Bro posted nothing for six days).
Prints each route's HTTP status and how many posts it returned. Publishes
nothing."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

UAS = {"bot": "shorts-pipeline/1.0 (sports discovery)",
       "browser": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/130.0 Safari/537.36")}
SUB = sys.argv[1] if len(sys.argv) > 1 else "nfl"
WEEK = int(time.time()) - 7 * 86400
ROUTES = [
    ("json www", f"https://www.reddit.com/r/{SUB}/top.json?t=week&limit=50"),
    ("json old", f"https://old.reddit.com/r/{SUB}/top.json?t=week&limit=50"),
    ("json api", f"https://api.reddit.com/r/{SUB}/top?t=week&limit=50"),
    ("rss www", f"https://www.reddit.com/r/{SUB}/top.rss?t=week"),
    ("rss www/", f"https://www.reddit.com/r/{SUB}/top/.rss?t=week"),
    ("rss old", f"https://old.reddit.com/r/{SUB}/top/.rss?t=week"),
    ("pullpush", "https://api.pullpush.io/reddit/search/submission/"
                 f"?subreddit={SUB}&size=50&after={WEEK}"
                 "&sort_type=score&sort=desc"),
    ("arctic", "https://arctic-shift.photon-reddit.com/api/posts/search"
               f"?subreddit={SUB}&after={WEEK}&limit=100"),
    ("arctic asc", "https://arctic-shift.photon-reddit.com/api/posts/search"
                   f"?subreddit={SUB}&after={WEEK}&limit=100&sort=asc"),
    ("arctic 1d", "https://arctic-shift.photon-reddit.com/api/posts/search"
                  f"?subreddit={SUB}&after={WEEK}&before={WEEK + 86400}"
                  "&limit=100"),
    ("arctic top", "https://arctic-shift.photon-reddit.com/api/posts/search"
                   f"?subreddit={SUB}&after={WEEK}&limit=100&sort=desc"
                   "&sort_type=score"),
]


def hit(url: str, ua: str) -> tuple[str, int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            code = str(r.status)
    except Exception as e:  # noqa: BLE001
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:120]  # type: ignore
        except Exception:  # noqa: BLE001
            pass
        return (f"{type(e).__name__} {getattr(e, 'code', '')}".strip(),
                0, body.replace("\n", " "))
    n = body.count("<entry>")
    try:
        d = json.loads(body)
        kids = ((d.get("data") or {}).get("children")
                if isinstance(d.get("data"), dict) else d.get("data"))
        n = len(kids or [])
        first = (kids or [{}])[0]
        first = first.get("data", first)
        sample = f"{first.get('score')} {str(first.get('title'))[:60]}"
    except Exception:  # noqa: BLE001
        sample = body[:80].replace("\n", " ")
    return code, n, sample


for name, url in ROUTES:
    for uak, ua in UAS.items():
        code, n, sample = hit(url, ua)
        print(f"{name:11} {uak:8} {code:16} posts={n:3}  {sample}",
              flush=True)
        time.sleep(3)
