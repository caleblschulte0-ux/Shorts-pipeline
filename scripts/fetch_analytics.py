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

Deep retention metrics
----------------------
When the OAuth token carries the `yt-analytics.readonly` scope, this
script ALSO pulls the metrics the algorithm actually rewards — average
view percentage, average view duration, and estimated minutes watched —
via the YouTube *Analytics* API, and ranks videos by retention as well as
by views-per-hour. Tokens minted before that scope was added degrade
gracefully: the analytics calls are skipped and you still get the
view-count snapshot. Re-auth via setup_youtube.py to enable them.

Auth: reuses YOUTUBE_TOKEN_JSON / YOUTUBE_CLIENT_SECRETS_JSON via the
same loader pattern as uploaders.py.

CLI:
  python3 scripts/fetch_analytics.py            # writes today's snapshot
  python3 scripts/fetch_analytics.py --max-age-days 30
"""
from __future__ import annotations

import argparse
import json
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


def _youtube_service(channel: str = ""):
    """Build a YouTube Data API client. Reuses the uploader's channel-routed
    auth so `channel="explainer"` reads YOUTUBE_TOKEN_JSON_EXPLAINER (the
    second channel) and "" reads the original YOUTUBE_TOKEN_JSON — no auth
    logic duplicated."""
    from uploaders import YouTubeUploader
    return YouTubeUploader(channel=channel)._service()


def _analytics_service(channel: str = ""):
    """youtubeAnalytics client on the same token, or None if the token lacks
    the analytics scope (older tokens) or anything goes wrong building it.
    Never raises — retention is an enhancement, view counts are the baseline."""
    try:
        from uploaders import YouTubeUploader
        return YouTubeUploader(channel=channel).analytics_service()
    except Exception as e:  # noqa: BLE001
        print(f"[analytics] retention service unavailable ({e})",
              file=sys.stderr)
        return None


def _retention_metrics(analytics, video_ids: list[str],
                       start_date: str) -> dict[str, dict]:
    """Pull average view %, average view duration, and minutes watched for
    each video via youtubeAnalytics. Returns {video_id: {...}}; empty on any
    failure (missing scope, quota) so the caller degrades to view counts."""
    if analytics is None or not video_ids:
        return {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = ("views,estimatedMinutesWatched,"
            "averageViewDuration,averageViewPercentage")
    # engagedViews = the Shorts 'chose to watch (vs swiped away)' signal;
    # shares + subscribersGained show which videos actually build the channel.
    extended = base + ",engagedViews,shares,subscribersGained"
    out: dict[str, dict] = {}
    for batch in _chunked(video_ids, 200):       # filter caps at 500 ids
        resp = None
        for metrics in (extended, base):         # extras may 400 → retry basic
            try:
                resp = analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=today,
                    dimensions="video",
                    metrics=metrics,
                    filters="video==" + ",".join(batch),
                    maxResults=len(batch),
                ).execute()
                break
            except Exception as e:  # noqa: BLE001
                err = e
                continue
        if resp is None:
            print(f"[analytics] retention skipped ({err}); "
                  f"view counts only", file=sys.stderr)
            return out                          # both variants failed → clean
        headers = [h["name"] for h in resp.get("columnHeaders", [])]
        for row in resp.get("rows", []):
            r = dict(zip(headers, row))
            vid = r.get("video")
            if not vid:
                continue
            out[vid] = {
                "average_view_percentage": round(
                    float(r.get("averageViewPercentage", 0)), 1),
                "average_view_duration_s": round(
                    float(r.get("averageViewDuration", 0)), 1),
                "estimated_minutes_watched": round(
                    float(r.get("estimatedMinutesWatched", 0)), 1),
            }
            for k, name in (("engaged_views", "engagedViews"),
                            ("shares", "shares"),
                            ("subscribers_gained", "subscribersGained")):
                if name in r:
                    out[vid][k] = int(float(r.get(name, 0) or 0))
    return out


def _retention_curves(analytics, video_ids: list[str],
                      start_date: str, limit: int = 12) -> dict[str, list]:
    """Per-moment retention CURVE for the newest videos: audienceWatchRatio at
    each elapsedVideoTimeRatio step. This shows WHERE viewers drop — mappable
    onto the 3 segments (each ≈ a third of runtime), so the brain can blame the
    exact beat that lost the audience. One query per video; best-effort."""
    if analytics is None or not video_ids:
        return {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: dict[str, list] = {}
    got = 0
    for vid in video_ids[:limit]:
        rows = None
        # audienceWatchRatio + relativeRetentionPerformance is the documented
        # audience-retention report; if the pair 400s, retry the bare ratio.
        for metrics in ("audienceWatchRatio,relativeRetentionPerformance",
                        "audienceWatchRatio"):
            try:
                resp = analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=today,
                    dimensions="elapsedVideoTimeRatio",
                    metrics=metrics,
                    filters=f"video=={vid}",
                    maxResults=100,
                ).execute()
                rows = resp.get("rows") or []
                break
            except Exception as e:  # noqa: BLE001
                err = e
                continue
        if rows is None:
            print(f"[analytics] curve skipped for {vid} ({err})", file=sys.stderr)
            continue
        if rows:
            # [elapsed_ratio, audience_watch_ratio, (relative_perf if present)]
            out[vid] = [[round(float(r[0]), 3), round(float(r[1]), 3)]
                        + ([round(float(r[2]), 3)] if len(r) > 2 else [])
                        for r in rows]
            got += 1
    print(f"[analytics] retention curves: {got}/{min(limit, len(video_ids))} "
          f"videos had enough watch data", file=sys.stderr)
    return out


def _search_and_traffic(analytics, start_date: str) -> dict:
    """Channel-level: which traffic sources drive views, and the ACTUAL search
    terms viewers typed to find us — direct fuel for the search-legibility
    strategy (title/hook phrasing) and topic choice. Best-effort."""
    if analytics is None:
        return {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: dict = {}
    try:
        resp = analytics.reports().query(
            ids="channel==MINE", startDate=start_date, endDate=today,
            dimensions="insightTrafficSourceType", metrics="views",
            sort="-views", maxResults=15).execute()
        out["traffic_sources"] = {row[0]: int(row[1])
                                  for row in resp.get("rows") or []}
    except Exception as e:  # noqa: BLE001
        print(f"[analytics] traffic sources skipped ({e})", file=sys.stderr)
    try:
        resp = analytics.reports().query(
            ids="channel==MINE", startDate=start_date, endDate=today,
            dimensions="insightTrafficSourceDetail", metrics="views",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views", maxResults=25).execute()
        out["search_terms"] = [{"term": row[0], "views": int(row[1])}
                               for row in resp.get("rows") or []]
    except Exception as e:  # noqa: BLE001
        print(f"[analytics] search terms skipped ({e})", file=sys.stderr)
    return out


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

    # Deep retention metrics (best-effort; skipped if the token lacks scope).
    pub_dates = [s["published_at"][:10] for s in stats.values()
                 if s.get("published_at")]
    start_date = min(pub_dates) if pub_dates else \
        datetime.now(timezone.utc).strftime("%Y-%m-%d")
    an = _analytics_service(channel)
    retention = _retention_metrics(an, list(stats.keys()), start_date)
    # Retention CURVES: query the HIGHEST-VIEW videos, not the newest — YouTube
    # only returns a per-moment curve once a video has enough watch data, and a
    # brand-new 6-view video never will. These are also the ones worth learning
    # from. Plus channel-level traffic sources + real viewer search terms.
    top_ids = [vid for vid, s in sorted(
        stats.items(), key=lambda kv: kv[1].get("views", 0), reverse=True)]
    curves = _retention_curves(an, top_ids, start_date, limit=15)
    discovery = _search_and_traffic(an, start_date)

    videos: list[dict] = []
    for vid, entry in candidates:
        s = stats.get(vid)
        if not s:
            # Video was uploaded but YouTube's API doesn't have it yet
            # (rare; usually means scheduled and not live). Skip rather
            # than emit zeros that would skew the summary.
            continue
        age = _hours_since(s.get("published_at")) or _hours_since(entry.get("posted_at")) or 0.01
        v = {
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
        }
        v.update(retention.get(vid, {}))   # retention keys when available
        if vid in curves:
            v["retention_curve"] = curves[vid]   # [[elapsed_ratio, watch_ratio]]
        videos.append(v)

    videos.sort(key=lambda v: v["views_per_hour"], reverse=True)
    by_vph = sorted(videos, key=lambda v: v["views_per_hour"], reverse=True)
    # Retention leaderboard — only over videos that actually have the metric.
    retained = [v for v in videos if "average_view_percentage" in v]
    by_ret = sorted(retained, key=lambda v: v["average_view_percentage"],
                    reverse=True)

    def _ret_card(v):
        return {"title": v["title"],
                "average_view_percentage": v["average_view_percentage"],
                "average_view_duration_s": v.get("average_view_duration_s"),
                "views": v["views"], "url": v["url"]}

    summary = {
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
    }
    if by_ret:
        summary["videos_with_retention"] = len(by_ret)
        summary["avg_view_percentage"] = round(
            sum(v["average_view_percentage"] for v in by_ret) / len(by_ret), 1)
        summary["top_5_by_retention"] = [_ret_card(v) for v in by_ret[:5]]
        summary["bottom_5_by_retention"] = [_ret_card(v) for v in by_ret[-5:][::-1]]

    snap = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "videos": videos,
        "summary": summary,
    }
    if discovery.get("traffic_sources"):
        snap["traffic_sources"] = discovery["traffic_sources"]
    if discovery.get("search_terms"):
        snap["search_terms"] = discovery["search_terms"]
    return snap


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
    if summary.get("top_5_by_retention"):
        best = summary["top_5_by_retention"][0]
        print(f"[analytics] avg retention {summary['avg_view_percentage']}% "
              f"across {summary['videos_with_retention']} videos; best: "
              f"{best['title']!r} @ {best['average_view_percentage']}%",
              file=sys.stderr)
    else:
        print("[analytics] retention metrics unavailable "
              "(token lacks yt-analytics scope — re-auth to enable)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
