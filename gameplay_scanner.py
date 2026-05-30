#!/usr/bin/env python3
"""Find the juicy parts of long gameplay clips.

Long parkour/gameplay videos have a lot of dead air — menus, slow
walks, respawn screens. Pure-random seeking lands on that crud about
half the time. This module scans a video once, scores each second by
how much motion it contains, and caches a list of high-motion window
start times in a sidecar JSON file. The composer then picks one of
those windows instead of seeking blindly.

The motion metric is the average luminance of the frame-to-frame
difference (via ffmpeg's tblend=difference + signalstats). High
difference = lots of pixel change = camera is moving = the player is
doing something.

Usage:
    from gameplay_scanner import juicy_starts
    starts = juicy_starts(Path("gameplay/foo.mp4"), window=30, top_n=20)
    seek = random.choice(starts)
"""
from __future__ import annotations

import bisect
import json
import re
import subprocess
import tempfile
from pathlib import Path


# Sample at 2 Hz when scanning. Fine enough to catch motion bursts,
# coarse enough that scanning a 30-min clip finishes in ~30s.
SCAN_FPS = 2.0
SCAN_W, SCAN_H = 160, 90  # downscale for speed; signalstats doesn't need detail


def _scan(video: Path) -> list[tuple[float, float]]:
    """Return [(time_seconds, motion_score), ...] for the whole video."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
        log_path = Path(tmp.name)
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-vf", (f"fps={SCAN_FPS},scale={SCAN_W}:{SCAN_H},"
                    f"tblend=all_mode=difference,signalstats,"
                    f"metadata=print:file={log_path}"),
            "-f", "null", "-",
        ], check=True)

        samples: list[tuple[float, float]] = []
        current_time: float | None = None
        for line in log_path.read_text().splitlines():
            m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", line)
            if m:
                current_time = float(m.group(1))
                continue
            m = re.match(r"lavfi\.signalstats\.YAVG=([\d.]+)", line)
            if m and current_time is not None:
                samples.append((current_time, float(m.group(1))))
                current_time = None
        return samples
    finally:
        log_path.unlink(missing_ok=True)


def _windows(samples: list[tuple[float, float]], window: float, step: float) -> list[tuple[float, float]]:
    """Slide a `window`-second window in `step` increments over the
    samples and return [(start_t, mean_score), ...]."""
    if not samples:
        return []
    times = [t for t, _ in samples]
    vals = [v for _, v in samples]
    out: list[tuple[float, float]] = []
    t = 0.0
    end_time = samples[-1][0]
    while t + window <= end_time:
        lo = bisect.bisect_left(times, t)
        hi = bisect.bisect_left(times, t + window)
        if hi > lo:
            out.append((t, sum(vals[lo:hi]) / (hi - lo)))
        t += step
    return out


def juicy_starts(
    video: Path,
    window: float = 30.0,
    step: float = 5.0,
    top_n: int = 20,
    cache: bool = True,
) -> list[float]:
    """Return start times (seconds) of the top-`top_n` highest-motion
    `window`-second segments in `video`. Result is cached as a JSON
    sidecar file next to the video so the scan only runs once."""
    sidecar = video.with_suffix(video.suffix + ".juicy.json")
    cache_key = f"w{int(window)}_s{int(step)}_n{top_n}"

    if cache and sidecar.exists():
        try:
            data = json.loads(sidecar.read_text())
            if data.get("cache_key") == cache_key:
                return data["starts"]
        except Exception:  # noqa: BLE001
            pass  # fall through and rescan

    samples = _scan(video)
    windows = _windows(samples, window, step)
    # Sort by score descending, slice top_n, then return chronological order
    # so a random pick still gives temporal variety across renders.
    top = sorted(windows, key=lambda x: -x[1])[:top_n]
    starts = sorted([t for t, _ in top])

    if cache:
        sidecar.write_text(json.dumps({
            "cache_key": cache_key,
            "starts": starts,
            "video_duration": samples[-1][0] if samples else 0,
            "n_samples": len(samples),
        }, indent=2))
    return starts


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("usage: gameplay_scanner.py <video> [window] [top_n]")
    v = Path(sys.argv[1])
    win = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    for s in juicy_starts(v, window=win, top_n=n):
        print(f"  {s:>7.1f}s")
