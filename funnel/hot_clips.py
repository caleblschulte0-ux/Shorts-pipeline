"""The clips the INTERNET already found entertaining.

Operator, 2026-10-10, after backtest 18 (fourteen stories that hung
together, best 74): *"None of them are entertaining is the issue."* The
story arm was building from each streamer's own most-viewed clips, and a
streamer's top clip of the week is often just their least boring minute.
What strangers actually found funny, shocking or dramatic is already
voted on in public: r/LivestreamFail's top posts are Twitch clips the
whole streamer-watching internet upvoted, each with a title that says in
plain words what happens ("xQc loses it all on a meme coin").

    livestreamfail(period="week") -> [{slug, url, post_title, upvotes,
                                       comments, permalink, created}]

Twitch clip posts only (clips.twitch.tv/<slug>, twitch.tv/<ch>/clip/<slug>),
best first. Reddit's app-only OAuth (REDDIT_CLIENT_ID/SECRET, the media
funnel's token) when set, the public JSON otherwise; nothing on failure.
A shared capability: any channel looking for what is entertaining on
stream right now can call it.
"""
from __future__ import annotations

import json
import re
import urllib.request

SUB = "LivestreamFail"
TIMEOUT = 15

_SLUG = re.compile(
    r"(?:clips\.twitch\.tv/(?:embed\?clip=)?|twitch\.tv/[^/\s]+/clip/)"
    r"([A-Za-z0-9_-]{6,120})")


def clip_slug(url: str) -> str | None:
    """The Twitch clip id in a clip URL, else None."""
    m = _SLUG.search(str(url or ""))
    return m.group(1) if m else None


def _listing(period: str, limit: int) -> dict | None:
    from funnel import media_funnel
    token = media_funnel._reddit_token()
    host = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    url = f"{host}/r/{SUB}/top.json?t={period}&limit={limit}&raw_json=1"
    headers = {"User-Agent": media_funnel._UA_REDDIT}
    if token:
        headers["Authorization"] = f"bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[hot_clips] r/{SUB} {period} failed "
              f"({type(e).__name__})", flush=True)
        return None


def livestreamfail(period: str = "week", limit: int = 100) -> list[dict]:
    """r/LivestreamFail's top Twitch clips for `period`, most upvoted
    first. [] when Reddit cannot be reached."""
    data = _listing(period, limit) or {}
    out, seen = [], set()
    for ch in ((data.get("data") or {}).get("children") or []):
        p = ch.get("data") or {}
        if p.get("over_18") or p.get("removed_by_category"):
            continue
        slug = clip_slug(p.get("url") or p.get("url_overridden_by_dest"))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append({"slug": slug,
                    "url": f"https://clips.twitch.tv/{slug}",
                    "post_title": str(p.get("title") or "")[:200],
                    "upvotes": int(p.get("ups") or p.get("score") or 0),
                    "comments": int(p.get("num_comments") or 0),
                    "permalink": "https://www.reddit.com"
                                 + str(p.get("permalink") or ""),
                    "created": float(p.get("created_utc") or 0)})
    out.sort(key=lambda c: -c["upvotes"])
    return out
