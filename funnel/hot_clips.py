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


# Reddit refuses an anonymous JSON request from a cloud runner (backtest
# 19, 2026-10-10: both listings HTTPError, 0 clips — the internet seeds
# never reached the director). So every read tries, in order: the API
# (app-only OAuth when REDDIT_CLIENT_ID/SECRET are set, else public), the
# PullPush (a public archive of Reddit posts), then the subreddit's public
# RSS feed of the same listing. Each returns Reddit's own listing shape, and
# the run says which one answered.
_PERIOD_S = {"hour": 3600, "day": 86400, "week": 7 * 86400,
             "month": 30 * 86400, "year": 365 * 86400}


def _fetch(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _get(path: str) -> dict | None:
    from funnel import media_funnel
    token = media_funnel._reddit_token()
    host = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    headers = {"User-Agent": media_funnel._UA_REDDIT}
    if token:
        headers["Authorization"] = f"bearer {token}"
    try:
        return json.loads(_fetch(f"{host}{path}", headers)
                          .decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[hot_clips] r/{SUB} {path.split('?')[0]} "
              f"API failed ({type(e).__name__})", flush=True)
        return None


_ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)


def _from_atom(xml: str) -> dict:
    """Reddit's Atom feed as its JSON listing shape: title, permalink,
    the post's own link (the "[link]" in the entry body), time. No vote
    counts — a feed keeps the listing's ORDER, which is the ranking."""
    import html
    from datetime import datetime
    kids = []
    for body in _ENTRY.findall(xml or ""):
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        link = re.search(r'<link href="([^"]+)"', body)
        content = html.unescape((re.search(
            r"<content[^>]*>(.*?)</content>", body, re.S) or [None, ""])[1])
        out = re.search(r'<a href="([^"]+)">\[link\]</a>', content)
        when = re.search(r"<(?:published|updated)>([^<]+)<", body)
        try:
            ts = datetime.fromisoformat(when.group(1)).timestamp() \
                if when else 0.0
        except ValueError:
            ts = 0.0
        perm = html.unescape(link.group(1)) if link else ""
        kids.append({"data": {
            "title": html.unescape(title.group(1)) if title else "",
            "url": html.unescape(out.group(1)) if out else perm,
            "permalink": re.sub(r"^https?://[^/]+", "", perm),
            "created_utc": ts}})
    return {"data": {"children": kids}}


def _rss(path: str) -> dict | None:
    from funnel import media_funnel
    url = "https://www.reddit.com" + path.replace(".json?", ".rss?", 1)
    try:
        got = _from_atom(_fetch(url, {"User-Agent": media_funnel._UA_REDDIT})
                         .decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[hot_clips] r/{SUB} RSS failed "
              f"({type(e).__name__})", flush=True)
        return None
    return got if got["data"]["children"] else None


def _pullpush(query: str | None, period: str, limit: int) -> dict | None:
    import time as _t
    q = {"subreddit": SUB, "size": min(int(limit), 100),
         "after": int(_t.time() - _PERIOD_S.get(period, _PERIOD_S["week"])),
         "sort_type": "score", "sort": "desc"}
    if query:
        q["q"] = query
    url = ("https://api.pullpush.io/reddit/search/submission/?"
           + urllib.parse.urlencode(q))
    try:
        data = json.loads(_fetch(url, {"User-Agent": "shorts-pipeline/1.0"})
                          .decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[hot_clips] PullPush failed "
              f"({type(e).__name__})", flush=True)
        return None
    posts = data.get("data") if isinstance(data, dict) else None
    if not posts:
        return None
    return {"data": {"children": [{"data": p} for p in posts]}}


def _first(path: str, query: str | None, period: str,
           limit: int) -> dict | None:
    # PullPush before RSS: it carries scores and the over_18 flag; a feed
    # carries neither.
    for name, fn in (("api", lambda: _get(path)),
                     ("pullpush", lambda: _pullpush(query, period, limit)),
                     ("rss", lambda: _rss(path))):
        got = fn()
        if got and (got.get("data") or {}).get("children"):
            if name != "api":
                print(f"[hot_clips] r/{SUB} answered by {name}", flush=True)
            return got
    return None


def _listing(period: str, limit: int) -> dict | None:
    return _first(f"/r/{SUB}/top.json?t={period}&limit={limit}&raw_json=1",
                  None, period, limit)


def _search(query: str, period: str, limit: int) -> dict | None:
    q = urllib.parse.quote(query)
    return _first(f"/r/{SUB}/search.json?q={q}&restrict_sr=1"
                  f"&sort=relevance&t={period}&limit={limit}&raw_json=1",
                  query, period, limit)


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
