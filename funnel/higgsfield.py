"""Higgsfield AI video integration — image-to-video / text-to-video.

DORMANT BY DEFAULT. This module is wired into the pipeline so any channel
can use Higgsfield on demand, but it does NOTHING unless explicitly turned
on. It only activates when BOTH are set in the environment:

    HIGGSFIELD_API_KEY   — your reseller/API bearer token
    HIGGSFIELD_ENABLE=1  — master on-switch (so a stray key never costs money)

There is no official first-party Higgsfield API; access is via REST
resellers (VideoGenAPI, Segmind, etc.). The endpoint shape is therefore
configurable so we are not locked to one provider:

    HIGGSFIELD_API_URL   — POST endpoint (default: VideoGenAPI generate)
    HIGGSFIELD_STATUS_URL— optional poll endpoint template ({id} substituted)
    HIGGSFIELD_MODEL     — model name (default: higgsfield_v1)

Every function is best-effort and NEVER raises into the render: on any
failure (not configured, network, timeout, bad response) it returns None,
and the caller falls back to its existing behaviour (stock / Ken Burns).
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

_DEFAULT_API_URL = "https://api.videogenapi.com/api/v1/generate"
_TIMEOUT = 30
_POLL_INTERVAL = 5
_POLL_MAX = 36  # 36 * 5s = 3 min ceiling per generation


def is_enabled() -> bool:
    """True only when the master switch AND an API key are both present."""
    return bool(os.environ.get("HIGGSFIELD_API_KEY")
                and os.environ.get("HIGGSFIELD_ENABLE") in ("1", "true", "yes"))


def _api_url() -> str:
    return os.environ.get("HIGGSFIELD_API_URL", _DEFAULT_API_URL)


def _model() -> str:
    return os.environ.get("HIGGSFIELD_MODEL", "higgsfield_v1")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('HIGGSFIELD_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> dict | None:
    try:
        req = urllib.request.Request(
            _api_url(), data=json.dumps(payload).encode("utf-8"),
            headers=_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:  # noqa: BLE001
        print(f"[higgsfield] request failed ({type(e).__name__}: {e})", flush=True)
        return None


def _extract_video_url(resp: dict) -> str | None:
    """Pull a finished video URL out of a variety of response shapes."""
    for key in ("video_url", "url", "output", "result"):
        v = resp.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
        if isinstance(v, dict):
            for k2 in ("video_url", "url"):
                if isinstance(v.get(k2), str) and v[k2].startswith("http"):
                    return v[k2]
        if isinstance(v, list) and v and isinstance(v[0], str) \
                and v[0].startswith("http"):
            return v[0]
    return None


def _poll(job_id: str) -> str | None:
    tmpl = os.environ.get("HIGGSFIELD_STATUS_URL")
    if not tmpl:
        return None
    url = tmpl.replace("{id}", job_id)
    for _ in range(_POLL_MAX):
        time.sleep(_POLL_INTERVAL)
        try:
            req = urllib.request.Request(url, headers=_headers())
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                resp = json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:  # noqa: BLE001
            print(f"[higgsfield] poll failed ({type(e).__name__}: {e})",
                  flush=True)
            return None
        status = str(resp.get("status", "")).lower()
        if status in ("completed", "succeeded", "success", "done"):
            return _extract_video_url(resp)
        if status in ("failed", "error", "canceled", "cancelled"):
            print(f"[higgsfield] job {job_id} status={status}", flush=True)
            return None
    print(f"[higgsfield] job {job_id} timed out polling", flush=True)
    return None


def _download(url: str, out: Path) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT * 2) as r:
            data = r.read()
        out.write_bytes(data)
        return out if out.stat().st_size > 1024 else None
    except Exception as e:  # noqa: BLE001
        print(f"[higgsfield] download failed ({type(e).__name__}: {e})",
              flush=True)
        return None


def _generate(payload: dict, out: Path) -> Path | None:
    resp = _post(payload)
    if not resp:
        return None
    url = _extract_video_url(resp)
    if not url:
        job_id = resp.get("id") or resp.get("job_id") or resp.get("request_id")
        if job_id:
            url = _poll(str(job_id))
    if not url:
        print("[higgsfield] no video url in response", flush=True)
        return None
    return _download(url, out)


def text_to_video(prompt: str, out: Path, *, duration: int = 5,
                  resolution: str = "1080p") -> Path | None:
    """Generate a video clip from a text prompt. Returns the output path,
    or None if disabled/failed. Safe to call unconditionally."""
    if not is_enabled():
        return None
    print(f"[higgsfield] text->video: {prompt[:60]!r}", flush=True)
    return _generate({
        "model": _model(), "prompt": prompt,
        "duration": duration, "resolution": resolution,
    }, out)


def image_to_video(image_path: str | Path, out: Path, *,
                   prompt: str = "subtle cinematic camera motion, parallax",
                   duration: int = 5, resolution: str = "1080p") -> Path | None:
    """Animate a still image into a video clip (cinematic motion). Returns
    the output path, or None if disabled/failed. Safe to call
    unconditionally — falls back silently when Higgsfield is off."""
    if not is_enabled():
        return None
    try:
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    except Exception as e:  # noqa: BLE001
        print(f"[higgsfield] read image failed ({type(e).__name__}: {e})",
              flush=True)
        return None
    print(f"[higgsfield] image->video: {Path(image_path).name}", flush=True)
    return _generate({
        "model": _model(), "prompt": prompt,
        "image": f"data:image/jpeg;base64,{img_b64}",
        "duration": duration, "resolution": resolution,
    }, out)


def maybe_animate_still(image_path: str | Path, out: Path, *,
                        prompt: str = "subtle cinematic camera motion, parallax",
                        duration: float = 5.0) -> Path | None:
    """Renderer entry point. Returns an animated mp4 path when Higgsfield is
    enabled and succeeds, else None so the caller keeps its Ken Burns path.
    This is the single hook the video pipeline calls — dormant unless
    HIGGSFIELD_ENABLE=1 and HIGGSFIELD_API_KEY are set."""
    if not is_enabled():
        return None
    return image_to_video(image_path, out, prompt=prompt,
                          duration=max(3, int(round(duration))))
