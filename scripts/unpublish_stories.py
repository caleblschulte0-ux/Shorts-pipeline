#!/usr/bin/env python3
"""Take published / scheduled explainer videos back down.

Deletes the YouTube videos for the given story slugs (works whether they're
already public or still private-scheduled) and prunes them from the explainer
posted-log so the slugs are free to reuse or remove from the config.

Reuses the channel-routed auth from uploaders.YouTubeUploader, so it hits the
same token (YOUTUBE_TOKEN_JSON_EXPLAINER) and the same channel guard
(YOUTUBE_EXPECTED_CHANNEL) as the uploader — it can never touch another account.

Usage:
  python scripts/unpublish_stories.py --slugs young-and-alone everything-costs-more
  python scripts/unpublish_stories.py --slugs ocean-vs-space --dry-run   # show, don't delete
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "state" / "explainer_posted_log.json"
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="+", required=True,
                    help="story slugs to take down")
    ap.add_argument("--channel", default="explainer",
                    help="channel slug for token routing (default: explainer)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be deleted, delete nothing")
    args = ap.parse_args()

    log = json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {"posted": {}}
    posted = log.get("posted", {})

    targets = []
    for slug in args.slugs:
        entry = posted.get(slug)
        if not entry:
            print(f"[skip] {slug}: not in posted log")
            continue
        vid = _extract_id(entry.get("url"))
        if not vid:
            print(f"[skip] {slug}: no video id in {entry.get('url')!r}")
            continue
        targets.append((slug, vid, entry.get("url")))

    if not targets:
        print("nothing to do")
        return 0

    print(f"will take down {len(targets)} video(s):")
    for slug, vid, url in targets:
        print(f"   {slug:24} {vid}  {url}")
    if args.dry_run:
        print("dry-run — nothing deleted")
        return 0

    from uploaders import YouTubeUploader
    up = YouTubeUploader(channel=args.channel)
    svc = up._service()
    up._guard_channel(svc)          # refuse to touch the wrong account

    failures = 0
    for slug, vid, _url in targets:
        try:
            svc.videos().delete(id=vid).execute()
            print(f"[deleted] {slug} ({vid})")
            posted.pop(slug, None)
        except Exception as e:  # noqa: BLE001
            print(f"[fail] {slug} ({vid}): {e}", file=sys.stderr)
            failures += 1

    log["posted"] = posted
    LOG_PATH.write_text(json.dumps(log, indent=2) + "\n")
    print(f"\ndone: {len(targets) - failures}/{len(targets)} taken down; "
          f"posted-log pruned")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
