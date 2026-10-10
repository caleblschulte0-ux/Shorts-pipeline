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

    about(query, period="month") -> [{url, platform, post_title, upvotes,
                                      comments, permalink, created}]

THE OTHER SIDE (operator, 2026-10-10, of the Kai Cenat / Reggie saga:
*"take whoever made those allegations originally, that stream, take a
clip from there, and then go to Kai's stream of him saying, oh, this is
bullshit ... here's part two ... Kai saying part two came and there was
no evidence. Like, that's a story"*). The channel only ever discovered
the Twitch clips of the streamers it follows, so it held Kai's half of
that feud for weeks and never once the other half: Reggie's videos are
not on Twitch. `about()` searches r/LivestreamFail for everything posted
about a person, on ANY platform yt-dlp can download (Twitch, Kick,
YouTube, X, Streamable, TikTok, Reddit's own video), oldest first, so a
back-and-forth across two people's channels arrives as its turns.
"""
from __future__ import annotations

import json
import re
import urllib.parse
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


# Where a post's video lives, by host. Everything here downloads with
# yt-dlp; a link to an article or an image is not footage.
_VIDEO_HOSTS = (("clips.twitch.tv", "twitch"), ("twitch.tv", "twitch"),
                ("kick.com", "kick"), ("youtube.com", "youtube"),
                ("youtu.be", "youtube"), ("streamable.com", "streamable"),
                ("twitter.com", "x"), ("x.com", "x"),
                ("tiktok.com", "tiktok"), ("v.redd.it", "reddit"))


def video_link(post: dict) -> tuple[str, str] | None:
    """(url, platform) of the footage a post links to, else None. A
    Reddit-hosted video is downloaded from the post itself."""
    url = str(post.get("url_overridden_by_dest") or post.get("url") or "")
    low = url.lower()
    for host, platform in _VIDEO_HOSTS:
        if host in low:
            if platform == "reddit":
                return ("https://www.reddit.com"
                        + str(post.get("permalink") or ""), "reddit")
            if platform == "youtube" and "/channel/" in low:
                return None
            return url, platform
    return None


def _get(path: str) -> dict | None:
    from funnel import media_funnel
    token = media_funnel._reddit_token()
    host = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    url = f"{host}{path}"
    headers = {"User-Agent": media_funnel._UA_REDDIT}
    if token:
        headers["Authorization"] = f"bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[hot_clips] r/{SUB} {path.split('?')[0]} "
              f"failed ({type(e).__name__})", flush=True)
        return None


def _listing(period: str, limit: int) -> dict | None:
    return _get(f"/r/{SUB}/top.json?t={period}&limit={limit}&raw_json=1")


def _search(query: str, period: str, limit: int) -> dict | None:
    q = urllib.parse.quote(query)
    return _get(f"/r/{SUB}/search.json?q={q}&restrict_sr=1&sort=relevance"
                f"&t={period}&limit={limit}&raw_json=1")


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


def about(query: str, period: str = "month", limit: int = 50) -> list[dict]:
    """Every r/LivestreamFail post about `query` (a person, usually) that
    links to footage on any platform, OLDEST FIRST — a feud reads in the
    order it was said. [] when Reddit cannot be reached."""
    data = _search(query, period, limit) or {}
    out, seen = [], set()
    for ch in ((data.get("data") or {}).get("children") or []):
        p = ch.get("data") or {}
        if p.get("over_18") or p.get("removed_by_category"):
            continue
        link = video_link(p)
        if not link or link[0] in seen:
            continue
        seen.add(link[0])
        out.append({"url": link[0], "platform": link[1],
                    "slug": clip_slug(link[0]),
                    "post_title": str(p.get("title") or "")[:200],
                    "upvotes": int(p.get("ups") or p.get("score") or 0),
                    "comments": int(p.get("num_comments") or 0),
                    "permalink": "https://www.reddit.com"
                                 + str(p.get("permalink") or ""),
                    "created": float(p.get("created_utc") or 0)})
    out.sort(key=lambda c: c["created"])
    return out
