#!/usr/bin/env python3
"""Scout trending video posts from places the Claude container's egress
proxy blocks. Runs from a GitHub Actions runner (which has open egress).

Output: state/scouted_sources.json — candidate video posts and history
events, the chat-side workflow reads it to populate scripts/catalog.py.

Source mix (any failed source returns []; the rest still write a result):
  - Reddit         — usually 0 from Azure runners, kept for if it ever works
  - Wikipedia OTD  — 100+ historical events per day, never IP-blocks
  - Wikimedia      — recent video uploads in extreme-weather / wildlife etc.
  - YouTube Trending — real most-viewed today, via Data API + existing creds
  - Lemmy          — federated Reddit alternative, open API
  - Hacker News    — top stories that link to video sites
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "state" / "scouted_sources.json"
ERR_PATH = REPO / "state" / "scout_errors.log"

_ERROR_BUFFER: list[str] = []


def _err(line: str) -> None:
    """Capture error lines so they get committed back with the JSON."""
    print(line, file=sys.stderr)
    _ERROR_BUFFER.append(line)

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
        _err(f"[{sub}] all hosts failed: {last_err}")
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
        _err(f"[wikipedia/onthisday] {type(e).__name__}: {e}")
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


def _refresh_youtube_access_token() -> str | None:
    """OAuth access tokens last ~1h, the saved one in the secret is stale.
    The token.json itself already contains client_id, client_secret, and
    refresh_token, so we don't need a second env var."""
    import os
    token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "")
    if not token_json:
        _err("[youtube/refresh] YOUTUBE_TOKEN_JSON env not set")
        return None
    try:
        tok = json.loads(token_json)
    except Exception as e:  # noqa: BLE001
        _err(f"[youtube/refresh] cannot parse token json: {e}")
        return None
    client_id = tok.get("client_id")
    client_secret = tok.get("client_secret")
    refresh_token = tok.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        _err(
            "[youtube/refresh] token missing field(s): "
            f"client_id={bool(client_id)} client_secret={bool(client_secret)} "
            f"refresh_token={bool(refresh_token)}"
        )
        return None
    try:
        body = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return data.get("access_token")
    except urllib.error.HTTPError as e:
        body_text = (e.read() or b"")[:400].decode("utf-8", "replace")
        _err(f"[youtube/refresh] HTTP {e.code}: {body_text}")
        return None
    except Exception as e:  # noqa: BLE001
        _err(f"[youtube/refresh] {type(e).__name__}: {e}")
        return None


def fetch_youtube_trending() -> list[dict]:
    """YouTube trending via Data API. Reuses YOUTUBE_TOKEN_JSON for auth."""
    access_token = _refresh_youtube_access_token()
    if not access_token:
        _err("[youtube/trending] no access token (refresh failed)")
        return []

    params = (
        "chart=mostPopular&maxResults=50&regionCode=US"
        "&part=snippet,statistics,contentDetails"
    )
    url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = (e.read() or b"")[:300].decode("utf-8", "replace")
        _err(f"[youtube/trending] HTTP {e.code}: {body}")
        return []
    except Exception as e:  # noqa: BLE001
        _err(f"[youtube/trending] {type(e).__name__}: {e}")
        return []

    out: list[dict] = []
    for item in data.get("items", []):
        s = item.get("snippet", {}) or {}
        st = item.get("statistics", {}) or {}
        cd = item.get("contentDetails", {}) or {}
        vid = item.get("id") or ""
        out.append({
            "source_type": "youtube_trending",
            "video_id": vid,
            "title": s.get("title"),
            "channel": s.get("channelTitle"),
            "published_at": s.get("publishedAt"),
            "iso_duration": cd.get("duration"),
            "views": int(st.get("viewCount", 0) or 0),
            "likes": int(st.get("likeCount", 0) or 0),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "thumbnail": ((s.get("thumbnails") or {}).get("high") or {}).get("url"),
        })
    return out


VIDEO_HOSTS = (
    "youtube.com", "youtu.be", "vimeo.com", "v.redd.it",
    "streamable.com", "twitch.tv", "dailymotion.com",
)


def fetch_lemmy_top() -> list[dict]:
    """Top posts of the week from popular Lemmy instances that link to
    videos. Lemmy's API is open and doesn't IP-block."""
    instances = ["lemmy.world", "sh.itjust.works", "lemmy.ml"]
    out: list[dict] = []
    for inst in instances:
        api = f"https://{inst}/api/v3/post/list?sort=TopWeek&type_=All&limit=50"
        try:
            req = urllib.request.Request(api, headers=_headers())
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            _err(f"[lemmy/{inst}] {type(e).__name__}: {e}")
            continue
        for entry in (data.get("posts") or []):
            post = entry.get("post") or {}
            url = post.get("url") or ""
            if not any(h in url for h in VIDEO_HOSTS):
                continue
            counts = entry.get("counts") or {}
            community = entry.get("community") or {}
            out.append({
                "source_type": "lemmy_top",
                "instance": inst,
                "community": community.get("name"),
                "title": post.get("name"),
                "url": url,
                "score": int(counts.get("score", 0) or 0),
                "comments": int(counts.get("comments", 0) or 0),
            })
        time.sleep(1)
    out.sort(key=lambda p: p.get("score", 0), reverse=True)
    return out[:100]


def fetch_hackernews_video_links() -> list[dict]:
    """HN top stories that link to a video site."""
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                headers=_headers(),
            ),
            timeout=20,
        ) as r:
            ids = json.loads(r.read())[:80]
    except Exception as e:  # noqa: BLE001
        _err(f"[hn/top] {type(e).__name__}: {e}")
        return []

    out: list[dict] = []
    for hid in ids:
        try:
            with urllib.request.urlopen(
                f"https://hacker-news.firebaseio.com/v0/item/{hid}.json",
                timeout=10,
            ) as r:
                item = json.loads(r.read())
        except Exception:
            continue
        url = item.get("url") or ""
        if not any(h in url for h in VIDEO_HOSTS):
            continue
        out.append({
            "source_type": "hackernews_video",
            "title": item.get("title"),
            "url": url,
            "score": int(item.get("score", 0) or 0),
            "permalink": f"https://news.ycombinator.com/item?id={hid}",
        })
    out.sort(key=lambda p: p.get("score", 0), reverse=True)
    return out


VIDEO_EXTS_W = (".webm", ".ogv", ".mp4", ".mov", ".mkv")


def fetch_wikimedia_recent_videos(limit: int = 100) -> list[dict]:
    """Pull recent file uploads on Wikimedia Commons via logevents and
    filter to video file extensions. Gives a stream of real fresh
    footage uploaded in the last day or two."""
    out: list[dict] = []
    cont = None
    for _ in range(4):  # up to 4 pages × 100 = 400 recent uploads
        url = (
            "https://commons.wikimedia.org/w/api.php"
            "?action=query&list=logevents&letype=upload"
            "&lelimit=100&leprop=title|timestamp|user&format=json"
        )
        if cont:
            url += f"&lecontinue={urllib.parse.quote(cont)}"
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            _err(f"[wikimedia/logevents] {type(e).__name__}: {e}")
            break
        for ev in data.get("query", {}).get("logevents", []):
            title = ev.get("title") or ""
            tlow = title.lower()
            if not any(tlow.endswith(ext) for ext in VIDEO_EXTS_W):
                continue
            out.append({
                "source_type": "wikimedia_commons_recent",
                "title": title,
                "page_url": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
                "uploaded_at": ev.get("timestamp"),
                "uploader": ev.get("user"),
            })
            if len(out) >= limit:
                return out
        cont = (data.get("continue") or {}).get("lecontinue")
        if not cont:
            break
        time.sleep(0.5)
    return out


def main() -> int:
    print("scouting Reddit (likely blocked from Azure)...")
    all_reddit: list[dict] = []
    for sub in SUBREDDITS:
        posts = fetch_subreddit_top(sub, t="week", limit=25)
        all_reddit.extend(posts)
        time.sleep(2)
    all_reddit.sort(key=lambda p: p.get("score", 0), reverse=True)
    all_reddit = all_reddit[:200]
    print(f"  reddit: {len(all_reddit)}")

    print("\nscouting Wikipedia On This Day...")
    wikipedia = fetch_wikipedia_on_this_day()
    print(f"  wikipedia: {len(wikipedia)}")

    print("\nscouting Wikimedia Commons recent videos...")
    wikimedia = fetch_wikimedia_recent_videos()
    print(f"  wikimedia: {len(wikimedia)}")

    print("\nscouting YouTube trending...")
    youtube = fetch_youtube_trending()
    print(f"  youtube: {len(youtube)}")

    print("\nscouting Lemmy top week...")
    lemmy = fetch_lemmy_top()
    print(f"  lemmy: {len(lemmy)}")

    print("\nscouting Hacker News video links...")
    hn = fetch_hackernews_video_links()
    print(f"  hn: {len(hn)}")

    total = len(all_reddit) + len(wikipedia) + len(wikimedia) + len(youtube) + len(lemmy) + len(hn)
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "scouted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "reddit_subs": SUBREDDITS,
            "reddit_count": len(all_reddit),
            "wikipedia_on_this_day_count": len(wikipedia),
            "wikimedia_commons_count": len(wikimedia),
            "youtube_trending_count": len(youtube),
            "lemmy_count": len(lemmy),
            "hackernews_count": len(hn),
        },
        "total": total,
        "reddit_posts": all_reddit,
        "wikipedia_events": wikipedia,
        "wikimedia_videos": wikimedia,
        "youtube_trending": youtube,
        "lemmy_posts": lemmy,
        "hackernews_posts": hn,
    }, indent=2) + "\n")
    print(f"\nwrote {total} candidates -> {OUT_PATH}")

    # Always write the error log (empty if no errors) so we can read it
    # from the chat side via git pull after the bot commits.
    ERR_PATH.write_text("\n".join(_ERROR_BUFFER) + ("\n" if _ERROR_BUFFER else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
