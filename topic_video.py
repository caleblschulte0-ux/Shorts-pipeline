"""Free, mostly-legal topic-specific *video* clip search.

Sibling of `topic_media.py`. Where that returns image URLs for the
top-half of the frame, this returns short video clips of the actual
event / entity being discussed. Real footage of a cave rescue beats a
stock laptop shot every time.

Sources, tried in order:

  0. **NASA Image and Video Library** (`images-api.nasa.gov`). Free,
     public domain, no key. Strongest source for any space, climate,
     geology, weather or aviation topic — has the actual mission
     footage that Commons usually only paraphrases. Goes first.
  1. **DVIDS** (`api.dvidshub.net`). Defense Visual Information
     Distribution Service — the Pentagon's media library. All assets
     are US federal government works (17 U.S.C. § 105 → public domain,
     zero copyright risk). Strong on Coast Guard rescues, hurricane
     response, NATO exercises, military deployments, White House press
     pool video. Requires free `DVIDS_API_KEY` env var; skips silently
     if unset. Sibling-tier to NASA — both federal PD media libraries
     with current-events footage.
  2. Wikimedia Commons video files (`mime: video/*`). Same API call
     `topic_media._commons_files` already uses for images.
  3. Internet Archive `archive.org/advancedsearch.php` filtered to
     `mediatype:movies` + an opensource/CC collection. Strong for any
     event ≥30 days old, since archive mirrors news clips heavily.
  4. News article video scrape: `og:video`, `twitter:player:stream`,
     `<video src>`, `<source src>`, and JSON-LD VideoObject embeds.
     The HTML5/JSON-LD extensions catch outlets that lazy-load video
     and never set an og:video meta tag.
  5. **Reddit `v.redd.it`** — where viral bystander footage actually
     lives. Doorbell-cam meteor flashes, dashcam pileups, witness
     phone clips, town-vs-tax local-news shorts. None of these land
     in CC libraries; they get uploaded to Reddit first. Free, no
     auth needed for the public JSON API. The "we can't show the
     actual footage we're talking about" gap closes here.
  6. **Vimeo Creative Commons** (`api.vimeo.com/videos?filter=CC`).
     Requires `VIMEO_TOKEN` env var (free dev account). Lower volume
     than Commons but better SNR for human-story topics where NASA
     and Commons are both thin.
  7. YouTube `search.list?videoLicense=creativeCommon`. Requires
     `YOUTUBE_API_KEY`. CC-BY allows commercial reuse with attribution.
     Uses ~100 quota units per call.
  8. *Opt-in only* via `TOPIC_VIDEO_ALLOW_STRIKES=1` — searches YouTube
     without the CC filter. Relies on fair-use commentary doctrine for
     short clips. **YouTube's Content ID is automated and matches
     single-second clips regardless of fair use; three strikes
     terminate the channel.** Off by default. Document the risk before
     flipping the flag.

All sources return cached *local file paths* (not URLs) so the renderer
just plays them as ordinary video clips through ffmpeg.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from topic_media import _get  # shared UA/Accept HTTP helper

# Stock-footage download cache (audit Ticket 4). Lives in the repo's
# cache/ dir (gitignored) instead of /tmp so actions/cache can persist it
# between CI runs — /tmp is wiped with every runner, which re-downloaded
# the same footage daily. Env-overridable for local setups.
CACHE_DIR = Path(os.environ.get("TOPIC_VIDEO_CACHE",
                                Path(__file__).resolve().parent / "cache" / "stock_video"))
# Prune oldest files beyond this cap so the cache stays inside
# actions/cache's useful size (the whole repo shares a 10 GB pool).
CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024


def _prune_cache() -> None:
    try:
        files = sorted(CACHE_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        while files and total > CACHE_MAX_BYTES:
            victim = files.pop(0)
            total -= victim.stat().st_size
            victim.unlink(missing_ok=True)
    except OSError:
        pass
TIMEOUT = 20
# 80 MB hard cap. We ship a 3-5 second sub-cut from the head of the
# file anyway, so for very long source clips we use a Range request to
# pull only the first MAX_BYTES — ffmpeg decodes the moov-atom + the
# leading frames just fine. Wikimedia's per-IP policy is generous but
# the UA below must identify us per their compliance docs.
MAX_BYTES = 128 * 1024 * 1024
UA = ("shorts-pipeline/1.0 (https://github.com/caleblschulte0-ux/shorts-pipeline; "
      "caleblschulte0@gmail.com) urllib/python3")

# Substrings that, when they appear in a source filename / identifier,
# strongly suggest the file isn't B-roll: podcasts, interviews, tribute
# videos, credits rolls, mission patches, etc. These survive the topic
# keyword search because the source video MENTIONS the topic, but they
# play as a talking head or a static frame rather than as event footage.
# Match is case-insensitive substring on the URL filename + path.
JUNK_PATTERNS = (
    "podcast", "interview", "lex_fridman", "lex fridman",
    "joe_rogan", "joe rogan", "episode", "ep_", "ep ",
    "tribute", "memorial", "thanks", "credits", "credit_roll",
    "commentary", "discussion", "debate", "panel",
    "patch", "logo", "wordmark", "screenshot", "infographic",
    "slideshow", "diagram", "schematic", "powerpoint",
    "presentation", "lecture", "webinar", "qa_", "_qa.",
    "narration", "voiceover", "voice_over",
    "thumbnail", "promo", "trailer", "teaser",
)


def _looks_like_junk(url_or_name: str) -> bool:
    """Cheap filter against non-B-roll content. Returns True if the
    URL / filename matches any known junk pattern — the caller skips
    the file before paying download cost."""
    lower = url_or_name.lower()
    return any(pat in lower for pat in JUNK_PATTERNS)


def _cache_path(url: str, ext: str = ".mp4") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _prune_cache()
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + ext
    return CACHE_DIR / name


def _download(url: str, dest: Path) -> Path | None:
    """Stream a direct video URL to disk. Returns dest on success, None
    on any failure (404, network error). Caller falls through to the
    next source on None.

    Uses a `Range: bytes=0-MAX_BYTES` request so we get only the head
    of long files instead of getting cut off mid-stream — the resulting
    file is still a valid MP4/WebM container that ffmpeg can decode at
    least the first chunk of.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Referer": "https://en.wikipedia.org/",
            "Range": f"bytes=0-{MAX_BYTES - 1}",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            written = 0
            with dest.open("wb") as fh:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_BYTES:
                        break   # server ignored Range header — take what we got
                    fh.write(chunk)
        if dest.stat().st_size < 10_000:
            # < 10 KB is almost certainly an error page or stub, not a clip.
            dest.unlink()
            return None
        return dest
    except Exception as e:  # noqa: BLE001
        # Don't leave a half-written file in the cache or the next
        # render thinks it succeeded.
        if dest.exists():
            dest.unlink()
        print(f"      [topic_video download fail] {url[:60]}: {e}")
        return None


# ---------- Source 0: NASA Image and Video Library ----------

def _nasa_videos(topic: str, limit: int = 4) -> list[str]:
    """Search NASA's public library for video assets matching `topic`.
    Returns direct .mp4 / .mov URLs from `images-assets.nasa.gov`.

    The search endpoint returns *collections* (one per "asset" — a
    page with metadata, an image, captions, and one or more video
    derivatives). Each collection's asset manifest at
    `/asset/{nasa_id}` lists every file in that asset; we pick the
    smallest mp4 derivative (typically `~orig.mp4` or `~mobile.mp4`)
    so the download stays small and ffmpeg handles it.

    Public domain — NASA explicitly disclaims copyright on its own
    productions. No API key required, no rate limit advertised.
    """
    if not topic.strip():
        return []
    qs = urllib.parse.urlencode({
        "q": topic,
        "media_type": "video",
        "page_size": limit,
    })
    try:
        data = json.loads(_get(
            f"https://images-api.nasa.gov/search?{qs}", timeout=TIMEOUT))
    except Exception as e:  # noqa: BLE001
        print(f"      [nasa search fail] {e}")
        return []
    items = ((data.get("collection") or {}).get("items") or [])
    out: list[str] = []
    for it in items[:limit]:
        # Each item links to an asset manifest by `nasa_id`.
        d = (it.get("data") or [{}])[0]
        nasa_id = d.get("nasa_id")
        if not nasa_id:
            continue
        try:
            asset = json.loads(_get(
                f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}",
                timeout=TIMEOUT))
        except Exception:  # noqa: BLE001
            continue
        files = [(i.get("href") or "")
                 for i in ((asset.get("collection") or {}).get("items") or [])]
        # Prefer the smaller "mobile"/"medium" derivative; fall back to
        # orig. NASA asset URLs contain spaces and unicode characters
        # in filenames that urllib refuses to fetch without encoding,
        # so we re-encode the path component on the way out.
        mp4s = [f for f in files if f.lower().endswith(".mp4")]
        if not mp4s:
            continue
        mobile = [f for f in mp4s if "mobile" in f.lower()
                  or "small" in f.lower() or "medium" in f.lower()]
        url = mobile[0] if mobile else mp4s[0]
        try:
            parsed = urllib.parse.urlsplit(url)
            # Force HTTPS — NASA's images-assets CDN occasionally
            # 503s on HTTP requests while serving the same path
            # fine over HTTPS.
            url = urllib.parse.urlunsplit((
                "https", parsed.netloc,
                urllib.parse.quote(parsed.path), parsed.query, parsed.fragment))
        except Exception:  # noqa: BLE001
            continue
        out.append(url)
    return out


# ---------- Source 1: DVIDS (Defense Visual Information Distribution Service) ----------

def _dvids_videos(topic: str, limit: int = 4) -> list[str]:
    """Search DVIDS for video assets matching `topic`. Returns direct
    MP4 URLs from the Pentagon's public media library.

    All DVIDS content is US federal government work — automatically
    public domain per 17 U.S.C. § 105. No copyright risk, no fair-use
    defense needed, no DMCA exposure. Free attribution as a courtesy
    only.

    Strong content categories: Coast Guard helicopter rescues,
    hurricane response / FEMA evacuation footage, NATO exercises,
    military deployments, White House press pool video, NTSB / FBI
    raid footage (when released), wildfire response (DoD assisting
    CalFire), disaster recovery during federal declarations.

    Requires free `DVIDS_API_KEY` env var. Registration:
    https://www.dvidshub.net/api/. Skips silently when unset.

    Two-step protocol because the search endpoint returns asset
    summaries; direct download URLs live on the per-asset detail
    endpoint. We over-fetch search results and bail out of the detail
    loop early once we have `limit` valid MP4 URLs.
    """
    api_key = os.environ.get("DVIDS_API_KEY", "").strip()
    if not api_key or not topic.strip():
        return []
    qs = urllib.parse.urlencode({
        "q": topic,
        "type": "video",
        "max_results": limit * 3,
        "sort": "publishdate",
        "api_key": api_key,
    })
    try:
        data = json.loads(_get(
            f"https://api.dvidshub.net/search?{qs}", timeout=TIMEOUT))
    except Exception as e:  # noqa: BLE001
        print(f"      [dvids search skip] {e}")
        return []

    out: list[str] = []
    for r in (data.get("results") or [])[:limit * 3]:
        # Some search-result payloads carry a direct video URL. Try
        # the common field names before falling back to the per-asset
        # detail endpoint.
        url = (
            r.get("video_url_mp4") or
            r.get("download_video_url") or
            r.get("video_url") or
            ""
        )
        if not (url and url.startswith("http") and ".mp4" in url.lower()):
            asset_id = r.get("id") or r.get("asset_id")
            if not asset_id:
                continue
            try:
                detail = json.loads(_get(
                    f"https://api.dvidshub.net/asset/{urllib.parse.quote(str(asset_id))}"
                    f"?api_key={urllib.parse.quote(api_key)}",
                    timeout=TIMEOUT,
                ))
            except Exception:  # noqa: BLE001
                continue
            asset = (detail.get("results") or detail) or {}
            url = (
                asset.get("download_video_url") or
                asset.get("video_url_mp4") or
                asset.get("video_url") or
                ""
            )
        if url and url.startswith("http") and ".mp4" in url.lower():
            out.append(url)
        if len(out) >= limit:
            break
    return out


# ---------- Source 2: Wikimedia Commons video ----------

def _commons_videos(topic: str, limit: int = 3) -> list[str]:
    """Same Commons search topic_media uses for images, filtered to
    video MIMEs. Commons serves WebM/OGG/MP4 at their raw URL."""
    try:
        from topic_media import _commons_files
        return _commons_files(topic, mime_prefix="video/", limit=limit)
    except Exception:  # noqa: BLE001
        return []


# ---------- Source 3: Internet Archive ----------

def _archive_videos(topic: str, limit: int = 3) -> list[str]:
    """Search Internet Archive for opensource movies matching the topic.
    Returns direct MP4 download URLs (Archive serves an `__ia_thumb.mp4`
    plus the original; we prefer mid-quality .mp4 derivatives).
    """
    if not topic.strip():
        return []
    q = f'({topic}) AND mediatype:(movies) AND collection:(opensource_movies OR opensource_audio_video)'
    qs = urllib.parse.urlencode({
        "q": q,
        "fl[]": "identifier",
        "rows": limit,
        "page": 1,
        "output": "json",
        "sort[]": "downloads desc",
    })
    try:
        data = json.loads(_get(
            f"https://archive.org/advancedsearch.php?{qs}", timeout=TIMEOUT))
    except Exception:  # noqa: BLE001
        return []
    docs = ((data.get("response") or {}).get("docs") or [])
    out: list[str] = []
    for d in docs:
        ident = d.get("identifier")
        if not ident:
            continue
        try:
            meta = json.loads(_get(
                f"https://archive.org/metadata/{ident}", timeout=TIMEOUT))
        except Exception:  # noqa: BLE001
            continue
        files = meta.get("files") or []
        # Pick the smallest .mp4 derivative — they're already trimmed
        # to typical web sizes (~10-30 MB) and decode quickly.
        mp4s = [f for f in files if f.get("name", "").lower().endswith(".mp4")]
        mp4s.sort(key=lambda f: int(f.get("size") or 1 << 30))
        for f in mp4s[:1]:
            # Archive filenames often contain spaces and unicode; the
            # download endpoint needs them URL-encoded or urllib raises
            # "URL can't contain control characters".
            fname = urllib.parse.quote(f["name"])
            out.append(f"https://archive.org/download/{ident}/{fname}")
    return out


# ---------- Source 4: og:video on news articles ----------

_OG_VIDEO_RE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\']'
    r'(?:og:video(?::url|:secure_url)?|twitter:player:stream)'
    r'["\'][^>]*content\s*=\s*["\']([^"\']+)',
    re.I,
)

# Plain <video src> and <source src> tags. Most modern news outlets
# lazy-load video via JS and never emit an og:video meta tag — but
# when their initial HTML *does* embed the player, it's almost always
# one of these. The pattern is permissive on the attribute order
# because outlets render them in every combination imaginable.
_HTML5_VIDEO_RE = re.compile(
    r'<(?:video|source)[^>]*\bsrc\s*=\s*["\']([^"\']+\.(?:mp4|m4v|webm|mov)[^"\']*)',
    re.I,
)

# JSON-LD VideoObject is what Schema.org-aware outlets emit for SEO.
# The contentUrl field is the actual video URL. Matching the JSON
# inside <script type="application/ld+json"> is brittle so we just
# regex for the field — false positives are filtered by extension.
_JSONLD_VIDEO_RE = re.compile(
    r'"contentUrl"\s*:\s*"([^"]+\.(?:mp4|m4v|webm|mov)[^"]*)',
    re.I,
)

# Direct MP4 URLs hidden in JavaScript player config blobs. Covers:
#   - JWPlayer (`"file":"...mp4"`) — used by local TV affiliates
#   - Video.js / `"src":"...mp4"` inside a sources array
#   - Generic "mp4_url":"...", "download_video_url":"...", "videoUrl":"..."
# These catch the player config that gets server-rendered as a JS
# variable / JSON blob inline in the article HTML. We don't need to
# parse the JS structure — just regex the field. Extension filter on
# the URL keeps false positives down. Strips JSON-escaped slashes.
_PLAYER_CONFIG_RE = re.compile(
    r'(?:"file"|"src"|"mp4_url"|"download_video_url"|"videoUrl"|"hlsUrl"|"playbackUrl")'
    r'\s*:\s*"([^"]+\.(?:mp4|m4v|webm|mov)[^"]*)"',
    re.I,
)


def _extract_video_urls(html: str) -> list[str]:
    """Pull every plausible video URL out of an article HTML body —
    og:video meta + Twitter player stream + raw <video>/<source> tags
    + JSON-LD VideoObject.contentUrl + direct MP4 URLs hidden in
    JavaScript player config blobs (JWPlayer/Video.js/Brightcove
    payloads inlined as JSON). Returns unique results in the order
    they appeared."""
    seen: set[str] = set()
    out: list[str] = []
    for pat in (_OG_VIDEO_RE, _HTML5_VIDEO_RE, _JSONLD_VIDEO_RE,
                _PLAYER_CONFIG_RE):
        for m in pat.finditer(html):
            cand = m.group(1)
            # JSON-encoded slashes survive into the regex match.
            cand = cand.replace("\\/", "/")
            if cand.startswith("//"):
                cand = "https:" + cand
            if not cand.startswith("http"):
                continue
            if not cand.split("?")[0].lower().endswith(
                    (".mp4", ".m4v", ".webm", ".mov")):
                continue
            if cand in seen:
                continue
            seen.add(cand)
            out.append(cand)
    return out


def _og_videos(topic: str, max_hours: int = 24 * 7) -> list[str]:
    """Walk GDELT's recent article list for `topic`, then scrape every
    embedded video URL we can find from each article (og:video,
    twitter:player:stream, <video>/<source> tags, JSON-LD VideoObject).
    Modern news outlets often emit one of these even when others are
    missing, so we try all four for ~30% better recall than og:video
    alone."""
    if not topic.strip():
        return []
    qs = urllib.parse.urlencode({
        "query": f"{topic} sourcelang:eng",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 8,
        "timespan": f"{max_hours}h",
    })
    try:
        data = json.loads(_get(
            f"https://api.gdeltproject.org/api/v2/doc/doc?{qs}",
            timeout=TIMEOUT))
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for art in (data.get("articles") or [])[:5]:
        page = art.get("url")
        if not page:
            continue
        try:
            html = _get(page, timeout=10).decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        # Take just the first hit per article — too many videos from
        # one outlet biases the pool toward whoever has the most
        # embeds, not whose story is best.
        for cand in _extract_video_urls(html):
            out.append(cand)
            break
    return out


# ---------- Source 5: Reddit v.redd.it ----------

# Reddit's `created_utc` is in seconds since epoch. We skip posts newer
# than this window as a soft DMCA-risk mitigation: stolen-content
# takedowns are heavily front-loaded in the first day after a viral
# repost, so age >= 24h means most fakes have already been pulled.
REDDIT_MIN_AGE_HOURS = 24
# Lower bound: skip posts older than 30 days — for our "this just
# happened" channel the footage stops being topical even if it would
# still be legally fine.
REDDIT_MAX_AGE_HOURS = 24 * 30


def _reddit_videos(topic: str, limit: int = 4) -> list[str]:
    """Search Reddit for posts matching `topic`, return v.redd.it MP4
    URLs from video posts. This is where viral bystander footage
    actually lives — homeowner doorbell cams, dashcam pileups, witness
    phone clips — that never make it into CC libraries because the OP
    posted them to Reddit first and never re-licensed.

    Returns video-only MP4 URLs (Reddit stores audio in a separate
    DASH stream that we drop — fine since the renderer strips B-roll
    audio anyway).

    Skips posts < 24h old as a soft DMCA-risk mitigation: most
    stolen-content takedowns happen within the first 24 hours after
    a viral repost. Skips posts > 30 days old as a topicality filter.

    Reddit's JSON API 403s from some CI / corporate egress; we catch
    and return [] so the rest of the source chain continues to run.
    """
    if not topic.strip():
        return []
    qs = urllib.parse.urlencode({
        "q": topic,
        "type": "link",
        "sort": "relevance",
        "limit": 25,
        # Filter to last month server-side too so we don't waste a 25-row
        # page on stuff that's about to be aged out by the loop below.
        "t": "month",
    })
    try:
        raw = _get(
            f"https://www.reddit.com/search.json?{qs}", timeout=TIMEOUT)
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        # Sandboxed CI / corporate proxies commonly 403 reddit.com;
        # production runners usually don't. Either way fall through
        # silently so the rest of the source chain still runs.
        print(f"      [reddit search skip] {e}")
        return []

    now = time.time()
    out: list[str] = []
    for child in (data.get("data") or {}).get("children") or []:
        p = (child.get("data") or {})
        if not p.get("is_video"):
            continue
        created = float(p.get("created_utc") or 0)
        if created <= 0:
            continue
        age_h = (now - created) / 3600.0
        if age_h < REDDIT_MIN_AGE_HOURS or age_h > REDDIT_MAX_AGE_HOURS:
            continue
        media = (p.get("secure_media") or p.get("media") or {})
        rv = (media.get("reddit_video") or {})
        url = rv.get("fallback_url") or ""
        if not url:
            continue
        # Strip cache-bust query params; Reddit appends a `source=fallback`
        # which still works but trimming keeps the cache key cleaner.
        url = url.split("?")[0]
        if not (url.startswith("https://v.redd.it/") and ".mp4" in url):
            continue
        out.append(url)
        if len(out) >= limit:
            break
    return out


# ---------- Source 6: Vimeo Creative Commons ----------

def _vimeo_videos(topic: str, limit: int = 4) -> list[str]:
    """Search Vimeo's CC-licensed pool. Requires `VIMEO_TOKEN` env var
    from a free Vimeo developer account. Skips silently if no token
    is set so the rest of the chain still works.

    Vimeo's CC pool skews toward personal projects and short docs,
    which is the right shape for human-story topics (rescues,
    courtroom moments, named individuals) that NASA has nothing for
    and Commons covers only thinly.

    Returns direct download URLs (Vimeo's `/files` field — one per
    rendition; we take the smallest-but-usable one).
    """
    token = os.environ.get("VIMEO_TOKEN", "").strip()
    if not token or not topic.strip():
        return []
    params = {
        "query": topic,
        "filter": "CC",
        "per_page": limit,
        "sort": "relevant",
        "fields": "uri,name,download,files",
    }
    url = ("https://api.vimeo.com/videos?"
           + urllib.parse.urlencode(params))
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"      [vimeo search fail] {e}")
        return []
    out: list[str] = []
    for v in (data.get("data") or []):
        # Prefer `download` (direct files); fall back to `files`
        # (HLS/progressive renditions). Vimeo serves the smallest
        # mp4 progressive at ~360p which is plenty for shorts.
        progressives = []
        for f in (v.get("download") or []):
            if f.get("link") and f.get("type", "").lower().startswith("video/mp4"):
                progressives.append((int(f.get("size") or 1 << 30), f["link"]))
        for f in (v.get("files") or []):
            if f.get("link") and f.get("quality") == "sd":
                progressives.append((int(f.get("size") or 1 << 30), f["link"]))
        if not progressives:
            continue
        progressives.sort()
        out.append(progressives[0][1])
    return out


# ---------- Source 7: YouTube Creative Commons ----------

def _youtube_search(topic: str, *, license_filter: str | None,
                    limit: int = 5) -> list[str]:
    """Call YouTube Data API `search.list` for `topic`. `license_filter`
    is "creativeCommon" for Source 4 or None for Source 5 (opt-in).
    Returns video IDs ordered by YouTube's relevance score."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key or not topic.strip():
        return []
    params = {
        "key": api_key,
        "part": "id",
        "q": topic,
        "type": "video",
        "videoEmbeddable": "true",
        "videoDuration": "short",   # < 4 min — keeps download size sane
        "maxResults": limit,
        "order": "relevance",
        "safeSearch": "moderate",
    }
    if license_filter:
        params["videoLicense"] = license_filter
    try:
        data = json.loads(_get(
            "https://www.googleapis.com/youtube/v3/search?"
            + urllib.parse.urlencode(params),
            timeout=TIMEOUT))
    except Exception as e:  # noqa: BLE001
        print(f"      [youtube search fail] {e}")
        return []
    return [item["id"]["videoId"] for item in (data.get("items") or [])
            if (item.get("id") or {}).get("videoId")]


def _ytdlp_download(video_id: str, dest: Path) -> Path | None:
    """Pull the MP4 for a YouTube video ID via yt-dlp. Bails out with
    None if yt-dlp isn't installed or the download fails — caller falls
    through to the next source."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        # Prefer ≤720p mp4 so the file stays small enough to fit
        # MAX_BYTES with margin and downloads quickly. yt-dlp picks the
        # best matching format automatically.
        subprocess.run([
            "yt-dlp", "-q", "--no-warnings", "--no-playlist",
            "-f", "best[ext=mp4][height<=720]/best[height<=720]/best",
            "--max-filesize", str(MAX_BYTES),
            "-o", str(dest),
            url,
        ], check=True, timeout=90, capture_output=True)
        return dest if dest.exists() and dest.stat().st_size > 0 else None
    except FileNotFoundError:
        print("      [yt-dlp not installed; skipping YouTube source]")
        return None
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode(errors="ignore")[:200]
        print(f"      [yt-dlp fail {video_id}] {msg}")
        return None
    except subprocess.TimeoutExpired:
        print(f"      [yt-dlp timeout {video_id}]")
        return None


# ---------- Public entry point ----------

def _title_from_url(url: str) -> str:
    """Pull a readable title from a source URL. Used for shot-matching
    scoring downstream — the renderer compares each shot's phrase
    against this string to pick a relevant clip."""
    name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    name = urllib.parse.unquote(name)
    # Strip the file extension and turn underscores into spaces so
    # individual tokens can match shot text cleanly.
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name.replace("_", " ").replace("-", " ").strip()


def search(topic: str, context: str = "", *, max_clips: int = 6) -> list[dict]:
    """Return cached topic-specific videos, best first.

    Each result is a dict `{path, title, source}`. The renderer uses
    `title` to score clips against each shot's phrase/query so the
    "moon" shot gets the moon clip rather than whichever clip the
    round-robin counter landed on. Junk content (podcasts, interviews,
    tribute / credits rolls) is filtered out before download.

    Pulls up to `max_clips` distinct clips across all sources, so the
    renderer can build a per-render pool and distribute angles across
    shots instead of showing the same launch clip six times.
    """
    combined = f"{topic} {context}".strip()
    seen: set[str] = set()
    results: list[dict] = []

    def _try(url: str, *, source: str, ext: str = ".mp4") -> bool:
        """Returns True if `results` is now full."""
        if not url or url in seen:
            return len(results) >= max_clips
        seen.add(url)
        title = _title_from_url(url)
        if _looks_like_junk(url) or _looks_like_junk(title):
            print(f"      [topic_video skip junk] {title[:60]}")
            return len(results) >= max_clips
        dest = _cache_path(url, ext=ext)
        p = _download(url, dest)
        if p:
            results.append({"path": p, "title": title, "source": source})
        return len(results) >= max_clips

    # 0. NASA library — public-domain mission footage. Goes first
    #    because when it hits, it almost certainly has the actual
    #    event the script is about (a launch, an EVA, a Mars rover
    #    drive) and the license is unambiguous.
    for u in _nasa_videos(combined, limit=4):
        if _try(u, source="nasa", ext=".mp4"):
            return results

    # 1. DVIDS — Pentagon's public media library. All US federal
    #    government works → automatically PD per 17 U.S.C. § 105.
    #    Strong on Coast Guard rescues, hurricane response, NATO
    #    exercises, military deployments, White House press pool.
    #    Skips silently when DVIDS_API_KEY isn't set.
    for u in _dvids_videos(combined, limit=4):
        if _try(u, source="dvids", ext=".mp4"):
            return results

    # 2. Wikimedia Commons video. Take the title's hits first (best
    #    quality on named entities) then broaden to the combined query.
    if context:
        for u in _commons_videos(context, limit=5):
            if _try(u, source="commons",
                     ext=Path(u).suffix.lower() or ".webm"):
                return results
    for u in _commons_videos(combined, limit=5):
        if _try(u, source="commons",
                 ext=Path(u).suffix.lower() or ".webm"):
            return results

    # 3. Internet Archive — strong on historical / 30-day-old material.
    for u in _archive_videos(combined, limit=4):
        if _try(u, source="archive", ext=".mp4"):
            return results

    # 4. News article video embeds (og:video, twitter:player:stream,
    #    HTML5 <video>/<source>, JSON-LD VideoObject).
    for u in _og_videos(combined):
        if _try(u, source="og",
                 ext=Path(u.split("?")[0]).suffix.lower() or ".mp4"):
            return results

    # 5. Reddit v.redd.it — viral bystander footage (doorbell cams,
    #    dashcams, witness phone clips). This is the source that
    #    actually has the clips we narrate ("dozens of doorbell cams
    #    caught the flash"). Skips silently if Reddit's blocked at
    #    the network layer (some CI runners 403).
    for u in _reddit_videos(combined, limit=4):
        if _try(u, source="reddit", ext=".mp4"):
            return results

    # 6. Vimeo CC video path REMOVED. The CC pool was essentially
    # empty for current-event topics and the API's `download` field
    # requires a paid token scope, so this branch returned ~0 results
    # in practice. VIMEO_TOKEN now feeds the news-image funnel
    # (`media_funnel.p_vimeo`) as a THUMBNAIL source — the news event
    # hero photos that ride on Vimeo's video previews. Keep the
    # `_vimeo_videos` helper around for callers that still want the
    # video path; the renderer no longer hits it from this cascade.

    # 7. YouTube CC-licensed clips. Quota cost ~100 units/call; bail
    #    silently if no API key configured. Downloads up to 4 so the
    #    pool has variety instead of stopping at the first hit.
    if len(results) < max_clips:
        for vid in _youtube_search(combined, license_filter="creativeCommon",
                                    limit=4):
            dest = _cache_path(f"yt:cc:{vid}", ext=".mp4")
            p = _ytdlp_download(vid, dest)
            if p:
                results.append({"path": p, "title": f"youtube cc {vid}",
                                 "source": "youtube_cc"})
                if len(results) >= max_clips:
                    return results

    # 8. Opt-in fair-use path. Off by default.
    if not results and os.environ.get("TOPIC_VIDEO_ALLOW_STRIKES") == "1":
        for vid in _youtube_search(combined, license_filter=None, limit=4):
            dest = _cache_path(f"yt:any:{vid}", ext=".mp4")
            p = _ytdlp_download(vid, dest)
            if p:
                results.append({"path": p, "title": f"youtube {vid}",
                                 "source": "youtube_any"})
                if len(results) >= max_clips:
                    return results

    return results


if __name__ == "__main__":  # smoke test entry point
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "Tesla Cybertruck"
    context = sys.argv[2] if len(sys.argv) > 2 else ""
    items = search(topic, context)
    for it in items:
        print(f"{it['source']:10s}  {it['title'][:60]:60s}  {it['path']}")
    if not items:
        print(f"(no topic videos found for {topic!r})")
