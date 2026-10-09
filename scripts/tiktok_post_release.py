"""Post ONE already-published video to its channel's TikTok, by hand.

The video is a GitHub Release asset (shared/release_video.py puts every
video there after its gated YouTube upload), so nothing here judges or
re-renders anything: it re-uses what already shipped. The channel comes
from the tag (`video-<channel>-...`) and must have TikTok switched on
(`channels.<id>.tiktok.post`). Runs only in GitHub Actions on main
(tiktok_post_release.yml) — the site gives tokens to nothing else.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import crosspost  # noqa: E402
from shared.uploaders import TikTokUploader  # noqa: E402

STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
ROOT = Path(__file__).resolve().parent.parent
POSTED_LOGS = {"explainer": "state/explainer_posted_log.json",
               "trending": "state/posted_log.json",
               "third": "state/third_posted_log.json"}


def passed_the_gate(channel: str, title: str) -> bool:
    """The quality judgement already happened: a video reaches its
    channel's posted log as `posted` only after the showrunner (or third's
    QA chain) passed it and YouTube took it. Anything else is refused."""
    import json
    p = ROOT / POSTED_LOGS.get(channel, "")
    if not p.is_file():
        return False
    log = json.loads(p.read_text())
    ups = log.get("uploads", []) if isinstance(log, dict) else log
    return any(isinstance(u, dict) and u.get("title") == title
               and u.get("state", "posted") == "posted" for u in ups)


def channel_of(tag: str) -> str:
    parts = tag.split("-")
    if len(parts) < 3 or parts[0] != "video":
        raise SystemExit(f"not a video release tag: {tag}")
    return parts[1]


def main() -> int:
    import requests
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--mp4", required=True, type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description-file", required=True, type=Path)
    a = ap.parse_args()
    channel = channel_of(a.tag)
    if not crosspost.tiktok_posting_on(channel):
        print(f"::error::TikTok is off for {channel}", flush=True)
        return 1
    if not passed_the_gate(channel, a.title):
        print(f"::error::{a.title!r} is not a posted {channel} video",
              flush=True)
        return 1
    up = TikTokUploader(channel=channel)
    res = up.upload(file_path=a.mp4, title=a.title,
                    description=a.description_file.read_text(), tags=[])
    pid = res.raw["publish_id"]
    print(f"[tiktok] {channel}: publish_id={pid} {res}", flush=True)
    status = "unknown"
    for _ in range(24):
        time.sleep(10)
        r = requests.post(STATUS_URL, json={"publish_id": pid}, timeout=30,
                          headers={"Authorization": f"Bearer {up._token()}",
                                   "Content-Type": "application/json; charset=UTF-8"})
        data = (r.json().get("data") or {}) if r.ok else {}
        status = data.get("status") or f"HTTP {r.status_code} {r.text[:200]}"
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            break
    print(f"::notice::TikTok @{crosspost.tiktok_handle(channel)} {a.tag}: "
          f"{status} (privacy {res.raw.get('privacy_level')})", flush=True)
    return 0 if status != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
