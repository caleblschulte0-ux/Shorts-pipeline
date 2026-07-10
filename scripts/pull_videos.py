#!/usr/bin/env python3
"""Pull (delete) scheduled YouTube videos by id — used to yank a batch that
shouldn't publish. Tries delete; if the token lacks delete scope, falls back to
un-scheduling (private, no publishAt); if that also fails, prints the Studio
link so a human can remove it. Never raises on a single failure.

  python scripts/pull_videos.py --channel explainer VIDEOID1 VIDEOID2 ...
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="explainer")
    ap.add_argument("ids", nargs="+")
    a = ap.parse_args()
    from uploaders import YouTubeUploader
    svc = YouTubeUploader(channel=a.channel)._service()
    bad = 0
    for vid in a.ids:
        try:
            svc.videos().delete(id=vid).execute()
            print(f"DELETED {vid}")
            continue
        except Exception as e:
            print(f"[pull] delete failed for {vid}: {str(e)[:160]}", file=sys.stderr)
        # Fallback: un-schedule — set private and clear publishAt so it never
        # auto-publishes even if delete scope is missing.
        try:
            svc.videos().update(
                part="status",
                body={"id": vid, "status": {"privacyStatus": "private", "publishAt": None}},
            ).execute()
            print(f"UNSCHEDULED {vid} (set private, cleared publishAt)")
            continue
        except Exception as e2:
            print(f"[pull] unschedule failed for {vid}: {str(e2)[:160]}", file=sys.stderr)
            print(f"MANUAL-REMOVE https://studio.youtube.com/video/{vid}/edit")
            bad += 1
    print(f"[pull] done — {bad} still need manual removal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
