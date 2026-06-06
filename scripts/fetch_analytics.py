#!/usr/bin/env python3
"""Pull view / like / comment counts for every uploaded short and write
a daily snapshot the routine can read back the next morning.

Why this exists
---------------
Until now the pipeline uploaded videos and forgot them. There was no
feedback loop telling the topic ranker which angles actually worked.
This script closes that loop using the YouTube Data API's `videos.list`
endpoint (1 quota unit per call, free).

What it does
------------
1. Reads `state/posted_log.json` for every uploaded video URL.
2. Extracts the watch ID from URLs like `https://youtube.com/shorts/ABC123`.
3. Calls `videos.list?part=statistics,snippet` in batches of 50 IDs
   (the API's max per call) so the whole channel costs <5 quota units.
4. Computes views-per-hour-since-publish — the only fair comparison
   when uploads are minutes-vs-days old.
5. Writes two artefacts under `state/analytics/`:
   * `<YYYYMMDD>.json` — frozen snapshot for that day.
   * `latest.json` — rolling pointer the routine reads tomorrow.

What it does NOT do
-------------------
Deep metrics (CTR, average view duration, retention curves) require
the YouTube *Analytics* API with the `yt-analytics.readonly` scope.
The current OAuth token only has the Data API scope. If/when we want
those, a one-time re-auth via setup_youtube.py adds the scope and we
extend this script — for now, views-per-hour is the signal that
matters most.

Auth: reuses YOUTUBE_TOKEN_JSON / YOUTUBE_CLIENT_SECRETS_JSON via the
same loader pattern as uploaders.py.

CLI:
  python3 scripts/fetch_analytics.py            # writes today's snapshot
  python3 scripts/fetch_analytics.py --max-age-days 30
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

POSTED_LOG = ROOT / "state" / "posted_log.json"
ANALYTICS_DIR = ROOT / "state" / "analytics"

# YouTube watch IDs are always exactly 11 chars from this alphabet.
_ID_PATTERNS = [
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})"),
]


def _extract_id(url: str | None) -> str | None:
    if not url:
        return None
    for p in _ID_PATTERNS:
        m = p.search(url)
        if m:
            return m.group(1)
    return None


def _resolve_secret(env_path_var: str, env_inline_var: str, fallback: str) -> Path:
    """Same pattern uploaders.py uses: prefer an inline JSON blob in env
    (for CI), fall back to a path on disk, then a local filename."""
    inline = os.environ.get(env_inline_var)
    if inline:
        tmp = ROOT / f".{fallback}.runtime.json"
        tmp.write_text(inline)
        return tmp
    p = os.environ.get(env_path_var)
    return Path(p) if p else (ROOT / fallback)


def _youtube_service(channel: str = ""):
    """Build a YouTube Data API client. Reuses the uploader's channel-routed
    auth so `channel="explainer"` reads YOUTUBE_TOKEN_JSON_EXPLAINER (the
    second channel) and "" reads the original YOUTUBE_TOKEN_JSON — no auth
    logic duplicated."""
    from uploaders import YouTubeUploader
    return YouTubeUploader(channel=channel)._service()


def _entries(log: dict) -> list[dict]:
    """Normalize either posted-log shape to {url, posted_at, ident, title}.
    The trending log is a list of {video_url, posted_at, catalog_id}; the
    explainer log is a dict {slug: {url, at, publish_at, title}}."""
    posted = log.get("posted", [])
    out: list[dict] = []
    if isinstance(posted, dict):                 # explainer channel
        for slug, e in posted.items():
            if not e or e.get("skipped"):
                continue
            out.append({"url": e.get("url"), "ident": slug,
                        "posted_at": e.get("publish_at") or e.get("at"),
                        "title": e.get("title")})
    else:                                         # trending channel
        for e in posted:
            out.append({"url": e.get("video_url"),
                        "ident": e.get("catalog_id"),
                        "posted_at": e.get("posted_at"),
                        "title": e.get("title")})
    return out


def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _fetch_stats(service, video_ids: list[str]) -> dict[str, dict]:
    """videos.list takes up to 50 IDs per call. Returns a map of
    video_id -> {viewCount, likeCount, commentCount, title, publishedAt}."""
    out: dict[str, dict] = {}
    for batch in _chunked(video_ids, 50):
        resp = service.videos().list(
            part="statistics,snippet",
            id=",".join(batch),
            maxResults=50,
        ).execute()
        for item in resp.get("items", []):
            stats = item.get("statistics") or {}
            snip = item.get("snippet") or {}
            out[item["id"]] = {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "title": snip.get("title"),
                "published_at": snip.get("publishedAt"),
            }
    return out


def _hours_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.01, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)


def build_snapshot(posted_log: Path, channel: str = "",
                   max_age_days: int = 30) -> dict:
    """Pull stats for every uploaded video the posted_log knows about
    that's within max_age_days, and return a snapshot dict. New videos
    (no views yet) are included so the routine sees they exist; their
    views_per_hour is 0 not undefined."""
    if not posted_log.exists():
        sys.exit(f"missing {posted_log} — nothing to analyse")
    entries = _entries(json.loads(posted_log.read_text()))

    # Pair each log entry with its video ID + age. Drop entries older
    # than max_age_days so we don't waste quota on dead history.
    cutoff_hours = max_age_days * 24
    candidates: list[tuple[str, dict]] = []
    for entry in entries:
        vid = _extract_id(entry.get("url"))
        if not vid:
            continue
        age = _hours_since(entry.get("posted_at"))
        if age is not None and age > cutoff_hours:
            continue
        candidates.append((vid, entry))

    ids = [vid for vid, _ in candidates]
    if not ids:
        return {"fetched_at": datetime.now(timezone.utc).isoformat(),
                "videos": [], "summary": {"total_videos": 0}}

    service = _youtube_service(channel)
    stats = _fetch_stats(service, ids)

    videos: list[dict] = []
    for vid, entry in candidates:
        s = stats.get(vid)
        if not s:
            # Video was uploaded but YouTube's API doesn't have it yet
            # (rare; usually means scheduled and not live). Skip rather
            # than emit zeros that would skew the summary.
            continue
        age = _hours_since(s.get("published_at")) or _hours_since(entry.get("posted_at")) or 0.01
        videos.append({
            "video_id": vid,
            "url": entry.get("url"),
            "catalog_id": entry.get("ident"),
            "title": s["title"],
            "published_at": s["published_at"],
            "age_hours": round(age, 1),
            "views": s["views"],
            "likes": s["likes"],
            "comments": s["comments"],
            # Views-per-hour is the only fair comparison when ages differ
            # by orders of magnitude. A 2-day-old video at 500 views and a
            # 1-hour-old video at 50 views are the SAME quality signal.
            "views_per_hour": round(s["views"] / age, 2),
        })

    videos.sort(key=lambda v: v["views_per_hour"], reverse=True)
    by_vph = sorted(videos, key=lambda v: v["views_per_hour"], reverse=True)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "videos": videos,
        "summary": {
            "total_videos": len(videos),
            "total_views": sum(v["views"] for v in videos),
            "avg_views_per_video": round(
                sum(v["views"] for v in videos) / max(1, len(videos)), 1),
            "median_views_per_hour": round(sorted(
                [v["views_per_hour"] for v in videos])[len(videos) // 2], 2)
                if videos else 0,
            "top_5_by_vph": [
                {"title": v["title"], "views_per_hour": v["views_per_hour"],
                 "views": v["views"], "age_hours": v["age_hours"],
                 "url": v["url"]}
                for v in by_vph[:5]
            ],
            "bottom_5_by_vph": [
                {"title": v["title"], "views_per_hour": v["views_per_hour"],
                 "views": v["views"], "age_hours": v["age_hours"],
                 "url": v["url"]}
                for v in by_vph[-5:][::-1]
            ],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=30,
                    help="Skip uploads older than this (default 30)")
    ap.add_argument("--channel", default="",
                    help="'' = trending channel (default); 'explainer' reads "
                         "the explainer posted-log + token")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print to stdout, don't write to disk")
    args = ap.parse_args()

    if args.channel:
        posted_log = ROOT / "state" / f"{args.channel}_posted_log.json"
        out_dir = ROOT / "state" / f"analytics_{args.channel}"
    else:
        posted_log, out_dir = POSTED_LOG, ANALYTICS_DIR

    snap = build_snapshot(posted_log, channel=args.channel,
                          max_age_days=args.max_age_days)

    if args.dry_run:
        print(json.dumps(snap, indent=2))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    snap_path = out_dir / f"{today}.json"
    latest_path = out_dir / "latest.json"
    snap_path.write_text(json.dumps(snap, indent=2))
    latest_path.write_text(json.dumps(snap, indent=2))

    summary = snap["summary"]
    print(f"[analytics] {summary['total_videos']} videos, "
          f"{summary['total_views']} total views, "
          f"avg {summary['avg_views_per_video']}/video, "
          f"median {summary['median_views_per_hour']} vph",
          file=sys.stderr)
    if summary.get("top_5_by_vph"):
        print(f"[analytics] top: {summary['top_5_by_vph'][0]['title']!r} "
              f"@ {summary['top_5_by_vph'][0]['views_per_hour']} vph",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
