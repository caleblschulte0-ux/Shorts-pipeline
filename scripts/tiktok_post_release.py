"""Post already-published videos to their channel's TikTok.

Every video is a GitHub Release asset (shared/release_video.py puts it there
after its gated YouTube upload), so nothing here judges or re-renders
anything: it re-uses what already shipped, and only a title its channel's
posted log records as posted (the showrunner, or third's QA chain, passed
it and YouTube took it) may go. The channel comes from the tag
(`video-<channel>-...`) and must have TikTok switched on
(`channels.<id>.tiktok.post`). A video that went gets `tiktok.json` on its
release, so it never goes twice.

    --tag <tag>   post that one video now (tiktok_post_release.yml)
    --due         post every queued video whose YouTube publish_at has come
                  (tiktok_due.yml): TikTok cannot schedule, so this keeps
                  TikTok on the YouTube slots instead of dumping a day's
                  videos at render time.

Runs only in GitHub Actions on main — the site gives tokens to nothing else.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import crosspost, release_video  # noqa: E402
from shared.uploaders import TikTokUploader  # noqa: E402

STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
POSTED_LOGS = {"explainer": "state/explainer_posted_log.json",
               "trending": "state/posted_log.json",
               "third": "state/third_posted_log.json"}
#: a slot older than this is history, not a queue: the first run after
#: switching a channel on must not dump yesterday's videos onto TikTok.
LATE_LIMIT = timedelta(hours=3)


def _entries(log) -> list[dict]:
    if isinstance(log, list):
        return [e for e in log if isinstance(e, dict)]
    out = [e for e in (log.get("uploads") or []) if isinstance(e, dict)]
    posted = log.get("posted")
    if isinstance(posted, dict):
        out += [e for e in posted.values() if isinstance(e, dict)]
    return out


def posted_entry(channel: str, title: str) -> dict | None:
    """The posted-log record of this video, or None if it never passed its
    gate and reached YouTube."""
    p = ROOT / POSTED_LOGS.get(channel, "")
    if not p.is_file():
        return None
    for e in _entries(json.loads(p.read_text())):
        if e.get("title") == title and e.get("state", "posted") == "posted":
            return e
    return None


def passed_the_gate(channel: str, title: str) -> bool:
    return posted_entry(channel, title) is not None


def channel_of(tag: str) -> str:
    parts = tag.split("-")
    if len(parts) < 3 or parts[0] != "video":
        raise SystemExit(f"not a video release tag: {tag}")
    return parts[1]


def _when(s) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def is_due(entry: dict, now: datetime) -> bool:
    """Its YouTube slot has come, and not so long ago that it is history."""
    t = _when(entry.get("publish_at")) or _when(entry.get("at")) \
        or _when(entry.get("uploaded_at")) or _when(entry.get("ts"))
    return t is not None and now - LATE_LIMIT <= t <= now


#: how much earlier than its posted-log record a video's release asset may be
#: stamped and still be that upload (the asset goes up after YouTube takes it).
RENDER_SLACK = timedelta(minutes=30)


def uploaded_at(entry: dict) -> datetime | None:
    """When YouTube took it, by the posted log (not when it goes live)."""
    return _when(entry.get("at")) or _when(entry.get("ts")) \
        or _when(entry.get("posted_at")) or _when(entry.get("uploaded_at"))


def same_render(rel: dict, entry: dict) -> bool:
    """This release holds the file that upload was made from.

    A title is not a video: the twins story was rendered and uploaded on
    2026-10-07, lost from the posted log, rendered again in the new look and
    uploaded on 2026-10-09, and TikTok got the 2026-10-07 file because its
    release carried the same title. The mp4 is attached after the YouTube
    upload, so one stamped well before the posted record is an older render."""
    when = uploaded_at(entry)
    if when is None:
        return True
    for a in rel.get("assets") or []:
        if str(a.get("name", "")).endswith(".mp4"):
            made = _when(a.get("created_at"))
            if made is not None and made >= when - RENDER_SLACK:
                return True
    return False


def post(channel: str, tag: str, mp4: Path, title: str, description: str) -> str:
    """Upload, wait for TikTok to finish, mark the release. -> status."""
    import requests
    up = TikTokUploader(channel=channel)
    res = up.upload(file_path=mp4, title=title, description=description, tags=[])
    pid = res.raw["publish_id"]
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
    if status != "FAILED":
        release_video.attach_json(tag, release_video.TIKTOK_MARK,
                                  {"posted": res.url, "status": status, **res.raw})
    print(f"::notice::TikTok @{crosspost.tiktok_handle(channel)} {tag}: "
          f"{status} (privacy {res.raw.get('privacy_level')})", flush=True)
    return status


def _gh(path: str, **params):
    import requests
    r = requests.get(f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}/{path}",
                     headers=release_video._headers(), params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _download(asset: dict, to: Path) -> None:
    import requests
    r = requests.get(asset["url"], headers={**release_video._headers(),
                                            "Accept": "application/octet-stream"},
                     timeout=600)
    r.raise_for_status()
    to.write_bytes(r.content)


def due(now: datetime | None = None) -> int:
    """One video per channel per run, the oldest due first."""
    now = now or datetime.now(timezone.utc)
    queue: dict[str, list] = {}
    for rel in _gh("releases", per_page=60):
        tag = rel.get("tag_name", "")
        try:
            channel = channel_of(tag)
        except SystemExit:
            continue
        names = {a.get("name") for a in rel.get("assets") or []}
        if release_video.TIKTOK_MARK in names:
            continue
        if not crosspost.tiktok_posting_on(channel):
            continue
        entry = posted_entry(channel, rel.get("name", ""))
        if not entry or not is_due(entry, now):
            continue
        if not same_render(rel, entry):
            print(f"[tiktok] {tag}: an older render of {rel.get('name')!r} "
                  f"— not the video YouTube has", flush=True)
            continue
        queue.setdefault(channel, []).append(
            (_when(entry.get("publish_at")) or now, tag, rel))
    failed = 0
    for channel, items in queue.items():
        _, tag, rel = sorted(items, key=lambda x: x[0])[0]
        mp4s = [a for a in rel.get("assets") or [] if a["name"].endswith(".mp4")]
        if not mp4s:
            continue
        with tempfile.TemporaryDirectory() as d:
            mp4 = Path(d) / mp4s[0]["name"]
            _download(mp4s[0], mp4)
            try:
                if post(channel, tag, mp4, rel["name"], rel.get("body") or "") == "FAILED":
                    failed += 1
            except Exception as e:  # noqa: BLE001 — one channel never blocks another
                print(f"::warning::[tiktok] {tag}: {e}", flush=True)
                failed += 1
    if not queue:
        print("[tiktok] nothing due", flush=True)
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--mp4", type=Path)
    ap.add_argument("--title")
    ap.add_argument("--description-file", type=Path)
    a = ap.parse_args()
    if a.due:
        return due()
    channel = channel_of(a.tag)
    if not crosspost.tiktok_posting_on(channel):
        print(f"::error::TikTok is off for {channel}", flush=True)
        return 1
    if not passed_the_gate(channel, a.title):
        print(f"::error::{a.title!r} is not a posted {channel} video", flush=True)
        return 1
    status = post(channel, a.tag, a.mp4, a.title, a.description_file.read_text())
    return 0 if status != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
