"""A Reddit-hosted video when reddit.com refuses the runner.

yt-dlp reads a Reddit video through the post's JSON on reddit.com, and
Reddit answers a cloud runner's anonymous requests with 403 (backtest 19,
2026-10-10). The video itself lives on v.redd.it, Reddit's CDN, which
serves the files directly: an HLS playlist with picture and sound
together, and DASH files with picture and sound apart.

`fetch(media, out)` takes the v.redd.it address a listing gave
(`funnel.hot_clips.top_videos(...)["media"]`), saves an mp4 with sound to
`out`, and returns the clip's meta in `clip_edit.download`'s shape, or
None. Never raises. The file is only accepted once ffprobe reads a video
stream from it.

Shared capability (any channel that needs "this Reddit video"), so it
lives in funnel/.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

TIMEOUT = 180
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
_ID = re.compile(r"v\.redd\.it/([A-Za-z0-9]+)")
# newest names first; Reddit renamed the DASH files in 2023
VIDEO = ("DASH_1080.mp4", "DASH_720.mp4", "DASH_480.mp4", "DASH_360.mp4",
         "DASH_1080", "DASH_720", "DASH_480")
AUDIO = ("DASH_AUDIO_128.mp4", "DASH_AUDIO_64.mp4", "DASH_audio.mp4",
         "audio")


def video_id(url: str) -> str | None:
    m = _ID.search(str(url or ""))
    return m.group(1) if m else None


def _probe(path: Path) -> dict | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=60).stdout
        info = json.loads(out or "{}")
    except Exception:  # noqa: BLE001
        return None
    kinds = {s.get("codec_type") for s in info.get("streams") or []}
    if "video" not in kinds:
        return None
    return {"duration": float((info.get("format") or {}).get("duration")
                              or 0.0),
            "audio": "audio" in kinds}


def _ffmpeg(args: list[str]) -> bool:
    try:
        return subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-user_agent", UA] + args,
            capture_output=True, timeout=TIMEOUT).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def fetch(media: str, out: Path, *, title: str = "",
          max_s: float | None = None) -> dict | None:
    """The v.redd.it video at `media` as an mp4 at `out`, or None."""
    vid = video_id(media)
    if not vid:
        return None
    base = f"https://v.redd.it/{vid}"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    got = None
    # 1. HLS: picture and sound in one playlist
    if _ffmpeg(["-i", f"{base}/HLSPlaylist.m3u8", "-c", "copy",
                "-bsf:a", "aac_adtstoasc", str(out)]):
        got = _probe(out)
    # 2. DASH: the best picture, muxed with whichever sound file exists
    if not got:
        for v in VIDEO:
            for a in AUDIO + (None,):
                args = ["-i", f"{base}/{v}"]
                if a:
                    args += ["-i", f"{base}/{a}", "-map", "0:v:0",
                             "-map", "1:a:0"]
                if _ffmpeg(args + ["-c", "copy", str(out)]):
                    got = _probe(out)
                    if got:
                        break
            if got:
                break
    if not got:
        print(f"::warning::[reddit_video] no file for {base}", flush=True)
        out.unlink(missing_ok=True)
        return None
    if max_s and got["duration"] > max_s:
        out.unlink(missing_ok=True)
        return None
    return {"path": out, "clip_id": vid, "title": title, "clipper": "",
            "views": 0, "duration": got["duration"], "url": media}
