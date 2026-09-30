"""Cross-post a video that ALREADY SHIPPED to YouTube to the feed-first
platforms: TikTok (every channel with a linked account) and Instagram Reels
(when Meta is configured).

Called only after a channel's own gate passed AND its YouTube upload
succeeded — it never judges anything and never blocks anything. Best-effort:
every failure is a warning, and the YouTube post stands regardless.

TikTok: the account is the one linked at shorts-media.netlify.app/app/ for
this channel — `tiktok.handle` in config/channel_registry.json, overridable
by TIKTOK_HANDLE_<CHANNEL>. A channel with no handle does NOT post: with
several accounts linked, "whichever one" is how a trending video lands on
the third channel's TikTok. A static TIKTOK_ACCESS_TOKEN[_<CHANNEL>] still
works as before.

TikTok's API cannot schedule: a cross-post goes out when the video is made,
not at its YouTube publish slot.

GitHub Releases: the same file is attached to a release of this repository
(shared/release_video.py), which is how it appears in the Shorts Media
library at shorts-media.netlify.app/app/ — the site lists any public
repository's release videos, ours included.
"""
from __future__ import annotations

import os
from pathlib import Path


def tiktok_handle(channel: str) -> str:
    """The TikTok handle this channel posts to, or ''."""
    env = os.environ.get(f"TIKTOK_HANDLE_{channel.upper()}", "")
    if env.strip():
        return env.strip().lstrip("@")
    try:
        from shared import channel_registry
        return str((channel_registry.channel(channel).get("tiktok") or {})
                   .get("handle") or "").strip().lstrip("@")
    except Exception:  # noqa: BLE001 — an unknown channel simply has none
        return ""


def _tiktok_ready(channel: str) -> tuple[bool, str]:
    from shared.uploaders import tiktok_broker_available
    if os.environ.get(f"TIKTOK_ACCESS_TOKEN_{channel.upper()}") or \
            os.environ.get("TIKTOK_ACCESS_TOKEN"):
        return True, ""
    if not tiktok_broker_available():
        return False, "no TikTok token and no GitHub OIDC (id-token: write)"
    if not tiktok_handle(channel):
        return False, (f"no TikTok account named for {channel} — set "
                       f"channels.{channel}.tiktok.handle in "
                       f"config/channel_registry.json")
    return True, ""


def crosspost(channel: str, mp4: Path, title: str, description: str,
              tags: list[str]) -> dict:
    """Returns {platform: url} for whatever landed."""
    out: dict = {}
    from shared import release_video
    if release_video.available()[0]:
        try:
            out["github_release"] = release_video.publish(
                mp4, title, description, channel)
            print(f"[crosspost] github release -> {out['github_release']}",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] github release failed ({e})",
                  flush=True)
    ready, why = _tiktok_ready(channel)
    if ready:
        try:
            from shared.uploaders import TikTokUploader
            up = TikTokUploader(channel=channel).upload(
                file_path=mp4, title=title, description=description, tags=tags)
            out["tiktok"] = getattr(up, "url", str(up))
            print(f"[crosspost] tiktok -> {out['tiktok']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] tiktok failed ({e})", flush=True)
    if all(os.environ.get(k) for k in
           ("META_ACCESS_TOKEN", "IG_USER_ID", "REELS_PUBLIC_HOST")):
        try:
            from shared.uploaders import InstagramUploader
            up = InstagramUploader().upload(
                file_path=mp4, title=title, description=description, tags=tags)
            out["instagram"] = getattr(up, "url", str(up))
            print(f"[crosspost] instagram -> {out['instagram']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] instagram failed ({e})", flush=True)
    if not any(k in out for k in ("tiktok", "instagram")):
        print(f"[crosspost] {channel}: YouTube only"
              + (f" — {why}" if why else "") + ".", flush=True)
    return out
