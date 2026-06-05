#!/usr/bin/env python3
"""Post the curated data-explainer STORY shorts to a single channel.

This is a separate, self-contained path from the trending daily pipeline
(scripts/run_trending_daily.py) so the existing channel is never touched.
It renders each story slug with studio_render and uploads it with the
YouTubeUploader — which enforces YOUTUBE_EXPECTED_CHANNEL, so a wrong token
can never post to the wrong account.

Auth (env, set in the workflow from repo secrets):
    YOUTUBE_CLIENT_SECRETS_JSON   shared OAuth client (same app is fine)
    YOUTUBE_TOKEN_JSON            the TARGET channel's token
    YOUTUBE_EXPECTED_CHANNEL      e.g. "short_explainer67" (hard guard)

Usage:
    python scripts/post_stories.py --dry-run            # render only, no upload
    python scripts/post_stories.py                      # render + upload (public)
    python scripts/post_stories.py --slugs debt-trap grocery-squeeze
    python scripts/post_stories.py --every-hours 6      # schedule, spaced out
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import studio_render            # noqa: E402

CONFIG = REPO / "data_learning" / "niche.config.json"
OUTPUT_DIR = REPO / "output"
STATE_DIR = REPO / "state"
# Deliberately a DIFFERENT log file from the trending pipeline's
# state/posted_log.json so the two channels never collide.
LOG_PATH = STATE_DIR / "explainer_posted_log.json"


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"posted": {}}


def _save_log(log: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2) + "\n")


def _description(cfg: dict) -> str:
    parts = [cfg.get("hook", "").strip()]
    if cfg.get("closing"):
        parts += ["", cfg["closing"].strip()]
    tags = cfg.get("hashtags", [])
    if tags:
        parts += ["", " ".join(f"#{t}" for t in tags)]
    return "\n".join(p for p in parts if p is not None)[:5000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*",
                    help="story slugs to post (default: every story in config)")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but do not upload")
    ap.add_argument("--force", action="store_true",
                    help="re-post even if the slug is in the posted log")
    ap.add_argument("--every-hours", type=float, default=0.0,
                    help="schedule uploads this many hours apart (private until "
                         "publishAt); 0 = publish immediately")
    ap.add_argument("--start-in-hours", type=float, default=1.0,
                    help="when scheduling, how long from now the first one posts")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    slugs = args.slugs or list(stories)
    unknown = [s for s in slugs if s not in stories]
    if unknown:
        print(f"unknown slugs: {unknown}\navailable: {list(stories)}",
              file=sys.stderr)
        return 2

    log = _load_log()
    results = []
    uploader = None
    when = datetime.now(timezone.utc) + timedelta(hours=args.start_in_hours)

    for slug in slugs:
        sc = stories[slug]
        if not args.force and slug in log["posted"]:
            print(f"[{slug}] already posted -> {log['posted'][slug].get('url')}, "
                  f"skipping (use --force to repost)")
            continue
        out = OUTPUT_DIR / f"story_{slug}.mp4"
        print(f"[{slug}] rendering -> {out}", flush=True)
        studio_render.render(slug, out)

        if args.dry_run:
            print(f"[{slug}] dry-run: rendered, not uploading")
            results.append({"slug": slug, "ok": True, "url": "(dry-run)"})
            continue

        publish_at = None
        if args.every_hours > 0:
            publish_at = when.replace(microsecond=0).isoformat().replace(
                "+00:00", "Z")
            when += timedelta(hours=args.every_hours)

        if uploader is None:                 # lazy import → clear error if deps
            from uploaders import YouTubeUploader
            uploader = YouTubeUploader()
        print(f"[{slug}] uploading"
              + (f" (scheduled {publish_at})" if publish_at else " (public now)"),
              flush=True)
        res = uploader.upload(
            file_path=out,
            title=sc.get("title", slug)[:100],
            description=_description(sc),
            tags=list(sc.get("hashtags", []))[:30],
            publish_at=publish_at,
        )
        url = getattr(res, "url", None) or str(res)
        print(f"[{slug}] uploaded -> {url}", flush=True)
        log["posted"][slug] = {
            "url": url, "title": sc.get("title"),
            "at": datetime.now(timezone.utc).isoformat(),
            "publish_at": publish_at,
        }
        _save_log(log)
        results.append({"slug": slug, "ok": True, "url": url})

    ok = sum(1 for r in results if r["ok"])
    print(f"\ndone: {ok}/{len(results)} ok")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
