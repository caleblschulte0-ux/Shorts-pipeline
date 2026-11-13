"""Post already-published videos to their channel's Instagram and Facebook.

The Meta twin of scripts/tiktok_post_release.py, and it reuses that file's
rules: only a video its channel's posted log records as posted (it passed
its gate and YouTube took it) may go, at its YouTube slot, never more than
3 hours late, never a video pulled from YouTube, never an older render.

Which accounts: `channels.<id>.meta` in config/channel_registry.json —
    {"post": true, "instagram_id": "<IG business id>", "facebook_page_id": "<page id>"}
Either id may be empty (that platform is skipped). `post: false` turns the
channel off. A video that went gets `instagram.json` / `facebook.json` on
its release, so it never goes twice.

    --due          post every due video (meta_due.yml, every 15 min)
    --tag <tag>    post that one video now, due or not (meta_post_release.yml)
    --accounts     print every Page and Instagram account the token can
                   post to, with their ids (meta_check.yml). Posts nothing.

Token: META_ACCESS_TOKEN (a Business-portfolio system-user token), or
META_ACCESS_TOKEN_<CHANNEL> for one channel.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import release_video  # noqa: E402
from shared.uploaders import (FacebookUploader, InstagramUploader,  # noqa: E402
                              META_GRAPH)
from scripts import tiktok_post_release as tk  # noqa: E402

MARKS = {"instagram": "instagram.json", "facebook": "facebook.json"}
UPLOADERS = {"instagram": InstagramUploader, "facebook": FacebookUploader}
ID_KEYS = {"instagram": "instagram_id", "facebook": "facebook_page_id"}


def meta_cfg(channel: str) -> dict:
    try:
        from shared import channel_registry
        return dict(channel_registry.channel(channel).get("meta") or {})
    except Exception:  # noqa: BLE001 — an unknown channel has none
        return {}


def targets(channel: str) -> dict[str, str]:
    """{platform: account id} this channel posts to right now."""
    cfg = meta_cfg(channel)
    if cfg.get("post") is not True:
        return {}
    if not (os.environ.get(f"META_ACCESS_TOKEN_{channel.upper()}")
            or os.environ.get("META_ACCESS_TOKEN")):
        return {}
    return {p: str(cfg.get(k) or "").strip() for p, k in ID_KEYS.items()
            if str(cfg.get(k) or "").strip()}


def post_one(channel: str, tag: str, rel: dict, platforms: dict[str, str]) -> int:
    mp4s = [a for a in rel.get("assets") or [] if a["name"].endswith(".mp4")]
    if not mp4s:
        return 0
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        mp4 = Path(d) / mp4s[0]["name"]
        tk._download(mp4s[0], mp4)
        for platform, target in platforms.items():
            try:
                up = UPLOADERS[platform](channel=channel, target_id=target)
                res = up.upload(mp4, title=rel.get("name", ""),
                                description=rel.get("body") or "", tags=[])
                release_video.attach_json(tag, MARKS[platform],
                                          {"posted": res.url, **res.raw})
                print(f"::notice::{platform} {channel} {tag}: {res.url}",
                      flush=True)
            except Exception as e:  # noqa: BLE001 — one platform never blocks another
                print(f"::warning::[meta] {platform} {tag}: {e}", flush=True)
                failed += 1
    return failed


def _release_queue(now: datetime, force_tag: str = ""):
    for rel in tk._gh("releases", per_page=60):
        tag = rel.get("tag_name", "")
        if force_tag and tag != force_tag:
            continue
        try:
            channel = tk.channel_of(tag)
        except SystemExit:
            continue
        want = targets(channel)
        names = {a.get("name") for a in rel.get("assets") or []}
        want = {p: t for p, t in want.items() if MARKS[p] not in names}
        if not want:
            continue
        entry = tk.posted_entry(channel, rel.get("name", ""))
        if not entry:
            continue
        if not force_tag and not tk.is_due(entry, now):
            continue
        if tk.pulled(entry) or not tk.same_render(rel, entry):
            print(f"[meta] {tag}: pulled or older render — not posted", flush=True)
            continue
        yield (tk._when(entry.get("publish_at")) or now, channel, tag, rel, want)


def due(now: datetime | None = None, force_tag: str = "") -> int:
    """One video per channel per run, the oldest due first."""
    now = now or datetime.now(timezone.utc)
    queue: dict[str, list] = {}
    for item in _release_queue(now, force_tag):
        queue.setdefault(item[1], []).append(item)
    failed = 0
    for channel, items in queue.items():
        _, _, tag, rel, want = sorted(items, key=lambda x: x[0])[0]
        failed += post_one(channel, tag, rel, want)
    if not queue:
        print("[meta] nothing due", flush=True)
    return 1 if failed else 0


def accounts() -> int:
    """Every Page (and its linked Instagram) the token reaches."""
    import requests
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not token:
        print("::error::META_ACCESS_TOKEN secret is not set", flush=True)
        return 1
    me = requests.get(f"{META_GRAPH}/me", timeout=30,
                      params={"access_token": token}).json()
    if me.get("error"):
        print(f"::error::token rejected: {me['error']}", flush=True)
        return 1
    print(f"token belongs to: {me.get('name')} ({me.get('id')})")
    dbg = requests.get(f"{META_GRAPH}/debug_token", timeout=30, params={
        "input_token": token, "access_token": token}).json().get("data") or {}
    print(f"scopes: {', '.join(dbg.get('scopes') or [])}")
    print(f"expires: {dbg.get('expires_at') or 'never'}")
    r = requests.get(f"{META_GRAPH}/me/accounts", timeout=30, params={
        "fields": "id,name,instagram_business_account{id,username}",
        "limit": 100, "access_token": token}).json()
    if r.get("error"):
        print(f"::error::listing Pages failed: {r['error']}", flush=True)
        return 1
    pages = r.get("data") or []
    if not pages:
        print("::warning::the token reaches NO Facebook Pages — assign the "
              "Pages (and Instagram accounts) to the system user", flush=True)
    for p in pages:
        ig = p.get("instagram_business_account") or {}
        print(f"PAGE {p.get('name')!r} facebook_page_id={p.get('id')} | "
              f"INSTAGRAM @{ig.get('username', '-')} instagram_id={ig.get('id', '-')}")
    for ch in ("explainer", "third", "trending"):
        print(f"registry {ch}: {meta_cfg(ch)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--accounts", action="store_true")
    a = ap.parse_args()
    if a.accounts:
        return accounts()
    if a.tag:
        return due(force_tag=a.tag)
    return due()


if __name__ == "__main__":
    sys.exit(main())
