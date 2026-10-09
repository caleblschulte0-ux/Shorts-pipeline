"""Publish a finished video as a GitHub Release asset, so it shows up in the
Shorts Media library (shorts-media.netlify.app/app/) like any other creator's
release video.

Called from shared/crosspost.py after a channel's YouTube upload succeeds,
so the release list IS the list of published videos. Best-effort: a failure
is a warning, never a blocked post. Needs GITHUB_TOKEN (Actions' own token,
`contents: write`) and GITHUB_REPOSITORY, both present in every publishing
workflow; without them it does nothing and says so.

One release per video: tag `video-<channel>-<date>-<slug>-<sha8>`, name = the
video's title, body = its description (Shorts Media uses those as the
title and the starting caption). Re-running the same video finds the
existing release and only uploads the file if it is not there yet.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
MAX_BODY = 2000


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:48] or "video"


def release_tag(channel: str, title: str, mp4: Path) -> str:
    """Deterministic per file: the same render always maps to one tag."""
    digest = hashlib.sha256(mp4.read_bytes()).hexdigest()[:8]
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"video-{_slug(channel)}-{day}-{_slug(title)}-{digest}"


def available() -> tuple[bool, str]:
    if not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
        return False, "no GITHUB_TOKEN"
    if not os.environ.get("GITHUB_REPOSITORY"):
        return False, "no GITHUB_REPOSITORY"
    return True, ""


TIKTOK_MARK = "tiktok.json"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def tag_of(release_url: str) -> str:
    return str(release_url or "").rstrip("/").rsplit("/tag/", 1)[-1]


def attach_json(tag: str, name: str, data: dict) -> None:
    """Attach a small JSON file to the video's release (e.g. tiktok.json,
    the record that this video went to TikTok, so it never goes twice).
    Raises on failure."""
    import json
    import requests
    ok, why = available()
    if not ok:
        raise RuntimeError(why)
    repo = os.environ["GITHUB_REPOSITORY"]
    r = requests.get(f"{API}/repos/{repo}/releases/tags/{tag}",
                     headers=_headers(), timeout=60)
    if not r.ok:
        raise RuntimeError(f"release {tag}: {r.status_code} {r.text[:200]}")
    rel = r.json()
    if any(a.get("name") == name for a in rel.get("assets") or []):
        return
    upload_url = str(rel["upload_url"]).split("{")[0]
    up = requests.post(f"{upload_url}?name={name}",
                       headers={**_headers(), "Content-Type": "application/json"},
                       data=json.dumps(data).encode(), timeout=60)
    if not up.ok:
        raise RuntimeError(f"attach {name} failed: {up.status_code} {up.text[:200]}")


def publish(mp4: Path, title: str, description: str, channel: str) -> str:
    """Create (or find) the release and attach the video. Returns the
    release's html_url. Raises on any failure; crosspost turns that into
    a warning."""
    import requests

    ok, why = available()
    if not ok:
        raise RuntimeError(why)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ["GITHUB_REPOSITORY"]
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    tag = release_tag(channel, title, mp4)
    body = {"tag_name": tag, "name": str(title or mp4.stem)[:100],
            "body": str(description or "")[:MAX_BODY],
            "draft": False, "prerelease": False}
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        body["target_commitish"] = sha
    r = requests.post(f"{API}/repos/{repo}/releases", headers=headers,
                      json=body, timeout=60)
    if r.status_code == 422:
        # The tag exists (a re-run): use that release.
        r = requests.get(f"{API}/repos/{repo}/releases/tags/{tag}",
                         headers=headers, timeout=60)
    if not r.ok:
        raise RuntimeError(f"github release failed: {r.status_code} {r.text[:300]}")
    rel = r.json()
    name = _slug(title) + ".mp4"
    if any(a.get("name") == name for a in rel.get("assets") or []):
        return rel["html_url"]
    upload_url = str(rel["upload_url"]).split("{")[0]
    with open(mp4, "rb") as f:
        up = requests.post(f"{upload_url}?name={name}",
                           headers={**headers, "Content-Type": "video/mp4"},
                           data=f, timeout=600)
    if not up.ok:
        raise RuntimeError(f"github asset upload failed: {up.status_code} {up.text[:300]}")
    return rel["html_url"]
