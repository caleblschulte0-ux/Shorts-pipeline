"""Which free route still hands a GitHub runner sports FOOTAGE? Prints one
line per route. Publishes nothing, writes nothing.

2026-11-11: the cut-ins and montages came back empty because YouTube
refuses the runner and the converters timed out on 27 of 33 videos; the
Reddit fallback (`hot_clips.reddit_videos`) read r/all's search feed, which
now refuses it too.

    python scripts/footage_probe.py "Jalen Brunson"
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from funnel import hot_clips  # noqa: E402


def _n(got) -> str:
    kids = ((got or {}).get("data") or {}).get("children") or []
    vids = [k["data"].get("url", "") for k in kids
            if any(h in str(k["data"].get("url", ""))
                   for h in ("v.redd.it", "streamable.com"))]
    return f"{len(kids)} posts, {len(vids)} videos {vids[:2]}"


def main() -> int:
    q = sys.argv[1] if len(sys.argv) > 1 else "Jalen Brunson"
    e = urllib.parse.quote(q)
    routes = {
        "rss r/all site:streamable": lambda: hot_clips._rss(
            f"/search.json?q={urllib.parse.quote(q + ' site:streamable.com')}"
            "&sort=top&t=all&type=link", "all"),
        "rss r/nba search": lambda: hot_clips._rss(
            f"/r/nba/search.json?q={e}&restrict_sr=1&sort=top&t=all", "nba"),
        "rss r/nba search site:streamable": lambda: hot_clips._rss(
            f"/r/nba/search.json?q={urllib.parse.quote(q + ' site:streamable.com')}"
            "&restrict_sr=1&sort=top&t=all", "nba"),
        "rss r/nba top year": lambda: hot_clips._rss(
            "/r/nba/top.json?t=year&limit=100", "nba"),
        "pullpush nba q": lambda: hot_clips._pullpush(q, "year", 100, "nba"),
        "api r/nba search": lambda: hot_clips._get(
            f"/r/nba/search.json?q={e}&restrict_sr=1&sort=top&t=all"),
    }
    for name, fn in routes.items():
        t = time.time()
        try:
            out = _n(fn())
        except Exception as ex:  # noqa: BLE001
            out = f"error {type(ex).__name__}: {ex}"
        print(f"PROBE {name:36s} {time.time() - t:5.1f}s  {out}", flush=True)
        time.sleep(3)
    print("PROBE reddit_videos():", json.dumps(
        [v["url"] for v in hot_clips.reddit_videos(q)][:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
