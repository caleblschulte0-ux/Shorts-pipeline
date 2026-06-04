"""Free, mostly-legal topic-specific *video* clip search.

Sibling of `topic_media.py`. Where that returns image URLs for the
top-half of the frame, this returns short video clips of the actual
event / entity being discussed. Real footage of a cave rescue beats a
stock laptop shot every time.

Sources, tried in order:

  1. Wikimedia Commons video files (`mime: video/*`). Same API call
     `topic_media._commons_files` already uses for images.
  2. Internet Archive `archive.org/advancedsearch.php` filtered to
     `mediatype:movies` + an opensource/CC collection. Strong for any
     event ≥30 days old, since archive mirrors news clips heavily.
  3. News article `og:video` / `twitter:player:stream` scrape. Same
     GDELT article list `topic_media._gdelt_news_image` walks, but
     pulling the embedded video tag instead of the image tag.
  4. YouTube `search.list?videoLicense=creativeCommon`. Requires
     `YOUTUBE_API_KEY`. CC-BY allows commercial reuse with attribution.
     Uses ~100 quota units per call.
  5. *Opt-in only* via `TOPIC_VIDEO_ALLOW_STRIKES=1` — searches YouTube
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
import urllib.parse
import urllib.request
from pathlib import Path

from topic_media import _get  # shared UA/Accept HTTP helper

CACHE_DIR = Path("/tmp/topic_videos")
TIMEOUT = 20
# 80 MB hard cap. We ship a 3-5 second sub-cut from the head of the
# file anyway, so for very long source clips we use a Range request to
# pull only the first MAX_BYTES — ffmpeg decodes the moov-atom + the
# leading frames just fine. Wikimedia's per-IP policy is generous but
# the UA below must identify us per their compliance docs.
MAX_BYTES = 80 * 1024 * 1024
UA = ("shorts-pipeline/1.0 (https://github.com/caleblschulte0-ux/shorts-pipeline; "
      "caleblschulte0@gmail.com) urllib/python3")


def _cache_path(url: str, ext: str = ".mp4") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
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


# ---------- Source 1: Wikimedia Commons video ----------

def _commons_videos(topic: str, limit: int = 3) -> list[str]:
    """Same Commons search topic_media uses for images, filtered to
    video MIMEs. Commons serves WebM/OGG/MP4 at their raw URL."""
    try:
        from topic_media import _commons_files
        return _commons_files(topic, mime_prefix="video/", limit=limit)
    except Exception:  # noqa: BLE001
        return []


# ---------- Source 2: Internet Archive ----------

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


# ---------- Source 3: og:video on news articles ----------

_OG_VIDEO_RE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\']'
    r'(?:og:video(?::url|:secure_url)?|twitter:player:stream)'
    r'["\'][^>]*content\s*=\s*["\']([^"\']+)',
    re.I,
)


def _og_videos(topic: str, max_hours: int = 24 * 7) -> list[str]:
    """Walk GDELT's recent article list for `topic`, scrape og:video /
    twitter:player:stream out of each article HTML. About 30-40% of
    major news outlets include broadcast clip URLs this way for embed
    purposes — same URLs their own embeds use."""
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
        for m in _OG_VIDEO_RE.finditer(html):
            cand = m.group(1)
            if cand.startswith("//"):
                cand = "https:" + cand
            if cand.startswith("http") and cand.split("?")[0].lower().endswith(
                    (".mp4", ".m4v", ".webm", ".mov")):
                out.append(cand)
                break
    return out


# ---------- Source 4: YouTube Creative Commons ----------

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

def search(topic: str, context: str = "", *, max_clips: int = 6) -> list[Path]:
    """Return cached local Paths of topic-specific videos, best first.

    Pulls up to `max_clips` distinct clips across all sources, so the
    renderer can build a per-render pool and round-robin different
    angles across shots instead of showing the same launch clip six
    times. Sources are tried in priority order and we stop as soon as
    `max_clips` is reached.
    """
    combined = f"{topic} {context}".strip()
    seen: set[str] = set()
    results: list[Path] = []

    def _try(url: str, ext: str = ".mp4") -> bool:
        """Returns True if `results` is now full."""
        if not url or url in seen:
            return len(results) >= max_clips
        seen.add(url)
        dest = _cache_path(url, ext=ext)
        p = _download(url, dest)
        if p:
            results.append(p)
        return len(results) >= max_clips

    # 1. Wikimedia Commons video. Take the title's hits first (best
    #    quality on named entities) then broaden to the combined query.
    if context:
        for u in _commons_videos(context, limit=4):
            if _try(u, ext=Path(u).suffix.lower() or ".webm"):
                return results
    for u in _commons_videos(combined, limit=4):
        if _try(u, ext=Path(u).suffix.lower() or ".webm"):
            return results

    # 2. Internet Archive — strong on historical / 30-day-old material.
    for u in _archive_videos(combined, limit=3):
        if _try(u, ext=".mp4"):
            return results

    # 3. og:video on today's news coverage of the same event.
    for u in _og_videos(combined):
        if _try(u, ext=Path(u.split("?")[0]).suffix.lower() or ".mp4"):
            return results

    # 4. YouTube CC-licensed clips. Quota cost ~100 units/call; bail
    #    silently if no API key configured. Now downloads up to 3 so the
    #    pool has variety instead of stopping at the first hit.
    if len(results) < max_clips:
        for vid in _youtube_search(combined, license_filter="creativeCommon",
                                    limit=4):
            dest = _cache_path(f"yt:cc:{vid}", ext=".mp4")
            p = _ytdlp_download(vid, dest)
            if p:
                results.append(p)
                if len(results) >= max_clips:
                    return results

    # 5. Opt-in fair-use path. Off by default.
    if not results and os.environ.get("TOPIC_VIDEO_ALLOW_STRIKES") == "1":
        for vid in _youtube_search(combined, license_filter=None, limit=4):
            dest = _cache_path(f"yt:any:{vid}", ext=".mp4")
            p = _ytdlp_download(vid, dest)
            if p:
                results.append(p)
                if len(results) >= max_clips:
                    return results

    return results


if __name__ == "__main__":  # smoke test entry point
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "Tesla Cybertruck"
    context = sys.argv[2] if len(sys.argv) > 2 else ""
    paths = search(topic, context)
    for p in paths:
        print(p)
    if not paths:
        print(f"(no topic videos found for {topic!r})")
