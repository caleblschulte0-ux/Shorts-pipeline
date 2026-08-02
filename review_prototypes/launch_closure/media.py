from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
ARCHETYPES = ("money", "share", "ranking", "comparison", "single")
COLORS = {
    "money": ("0x10131C", "0x4FD1C5"),
    "share": ("0x120D1D", "0xA78BFA"),
    "ranking": ("0x151007", "0xFBBF24"),
    "comparison": ("0x07151A", "0x22D3EE"),
    "single": ("0x170A10", "0xFB7185"),
}


def require_media_tools() -> None:
    if not FFMPEG or not FFPROBE:
        raise RuntimeError("ffmpeg and ffprobe are required for the rehearsal")


def render_rehearsal_clip(out_path: Path, *, archetype: str, shadow: bool, duration: float = 1.2) -> Path:
    require_media_tools()
    if archetype not in ARCHETYPES:
        raise ValueError(f"unsupported archetype: {archetype}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg, accent = COLORS[archetype]
    frequency = 340 + 35 * ARCHETYPES.index(archetype)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={bg}:s=1080x1920:r=30:d={duration}"]
    if shadow:
        cmd += [
            "-f", "lavfi", "-i", f"color=c={accent}:s=180x180:r=30:d={duration}",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
            "-filter_complex",
            "[0:v][1:v]overlay="
            f"x='80+(W-w-160)*t/{duration}':"
            "y='420+120*sin(7*t)':eval=frame,"
            "drawbox=x=110:y=260:w=860:h=520:color=white@0.08:t=fill,"
            "format=yuv420p[v]",
            "-map", "[v]", "-map", "2:a",
        ]
    else:
        cmd += [
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
            "-vf",
            f"drawbox=x=160:y=560:w=180:h=180:color={accent}:t=fill,"
            "drawbox=x=110:y=260:w=860:h=520:color=white@0.08:t=fill,"
            "format=yuv420p",
            "-map", "0:v", "-map", "1:a",
        ]
    cmd += [
        "-t", f"{duration:.3f}", "-r", "30", "-c:v", "libx264",
        "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-map_metadata", "-1",
        "-movflags", "+faststart", str(out_path),
    ]
    subprocess.run(cmd, check=True, timeout=60)
    if not out_path.exists() or out_path.stat().st_size < 1000:
        raise RuntimeError("rehearsal clip was not created")
    return out_path


def probe_clip(path: Path) -> dict:
    require_media_tools()
    raw = subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout
    payload = json.loads(raw)
    video = next(s for s in payload["streams"] if s.get("codec_type") == "video")
    audio = next((s for s in payload["streams"] if s.get("codec_type") == "audio"), None)
    fps_num, fps_den = (video.get("avg_frame_rate") or "0/1").split("/")
    fps = float(fps_num) / max(1.0, float(fps_den))
    return {
        "width": int(video["width"]), "height": int(video["height"]),
        "fps": round(fps, 3), "duration": round(float(payload["format"]["duration"]), 3),
        "has_audio": audio is not None, "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def frame_hashes(path: Path, sample_fps: int = 10) -> list[str]:
    require_media_tools()
    out = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-vf", f"fps={sample_fps},scale=160:-1,format=gray", "-f", "framemd5", "-"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout
    hashes = []
    for line in out.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6 and parts[0] == "0":
            hashes.append(parts[-1])
    if not hashes:
        raise RuntimeError("no frame hashes were produced")
    return hashes


def motion_ratio(path: Path) -> float:
    hashes = frame_hashes(path)
    changes = sum(a != b for a, b in zip(hashes, hashes[1:]))
    return round(changes / max(1, len(hashes) - 1), 3)


def content_fingerprint(path: Path) -> str:
    blob = json.dumps(
        {"probe": probe_clip(path), "frames": frame_hashes(path)},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    return hashlib.sha256(blob).hexdigest()
