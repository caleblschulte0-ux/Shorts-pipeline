#!/usr/bin/env python3
"""Find the juicy parts of long gameplay clips.

Long parkour/gameplay videos have a lot of dead air — menus, slow
walks, respawn screens. Pure-random seeking lands on that crud about
half the time. This module scans a video once, scores each second by
how much motion it contains, and caches a list of high-motion window
start times in a sidecar JSON file. The composer then picks one of
those windows instead of seeking blindly.

Two scan modes:

* `scan_mode="full"` (default, used by the bottom-half gameplay path).
  Averages the frame-to-frame luminance difference (`YAVG` after
  `tblend=difference`). Optimised for full-screen gameplay where the
  whole frame changes when the player moves.

* `scan_mode="center"` (used by topic_video clips). Center-crops to
  50%x60% of the frame BEFORE the difference filter, then scores
  windows by `YMAX_avg + 2*YSTD_avg` — peak motion plus richness-of-
  content. This handles the wide-shot rocket-vs-sky case where the
  rocket is <5% of pixels and YAVG stays near zero even mid-action;
  YMAX captures the brightest changed pixel and YSTD rejects uniform
  blue-sky / cloud-pan frames.

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


def _scan(video: Path, scan_mode: str = "full") -> list[tuple[float, float, float, float]]:
    """Return [(time_seconds, YAVG, YMAX, YRANGE), ...] for the whole
    video. `scan_mode="center"` center-crops before the diff filter so
    small bright moving objects (rockets against sky) aren't drowned
    out by the unchanged majority of the frame.

    `YRANGE = YHIGH - YLOW` is a robust spread proxy from the same
    signalstats output (ffmpeg's signalstats doesn't emit a YSTD
    field). High range = varied content (interesting frame); low
    range = flat color (sky, fade, slate).
    """
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
        log_path = Path(tmp.name)
    try:
        # Build the filter chain. For "center" mode we crop to the
        # middle 50%x60% region first; that's where rockets, launch
        # pads, news anchors and sports action tend to live in framed
        # event footage, so dropping the edges removes static-sky
        # dilution without losing the subject.
        if scan_mode == "center":
            pre = f"crop=iw*0.5:ih*0.6,scale={SCAN_W}:{SCAN_H}"
        else:
            pre = f"scale={SCAN_W}:{SCAN_H}"
        vf = (f"fps={SCAN_FPS},{pre},"
              f"tblend=all_mode=difference,signalstats,"
              f"metadata=print:file={log_path}")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-vf", vf,
            "-f", "null", "-",
        ], check=True)

        samples: list[tuple[float, float, float, float]] = []
        current_time: float | None = None
        cur_yavg = cur_ymax = cur_yhigh = cur_ylow = None

        def _flush():
            if (current_time is not None and cur_yavg is not None
                    and cur_ymax is not None and cur_yhigh is not None
                    and cur_ylow is not None):
                yrange = max(0.0, cur_yhigh - cur_ylow)
                samples.append((current_time, cur_yavg, cur_ymax, yrange))

        for line in log_path.read_text().splitlines():
            m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", line)
            if m:
                _flush()
                current_time = float(m.group(1))
                cur_yavg = cur_ymax = cur_yhigh = cur_ylow = None
                continue
            m = re.match(r"lavfi\.signalstats\.YAVG=([\d.]+)", line)
            if m:
                cur_yavg = float(m.group(1))
                continue
            m = re.match(r"lavfi\.signalstats\.YMAX=([\d.]+)", line)
            if m:
                cur_ymax = float(m.group(1))
                continue
            m = re.match(r"lavfi\.signalstats\.YHIGH=([\d.]+)", line)
            if m:
                cur_yhigh = float(m.group(1))
                continue
            m = re.match(r"lavfi\.signalstats\.YLOW=([\d.]+)", line)
            if m:
                cur_ylow = float(m.group(1))
                continue
        # Flush the last frame.
        _flush()
        return samples
    finally:
        log_path.unlink(missing_ok=True)


def _windows(samples: list[tuple[float, float, float, float]],
             window: float, step: float,
             scan_mode: str = "full") -> list[tuple[float, float]]:
    """Slide a `window`-second window in `step` increments over the
    samples and return [(start_t, score), ...]. The score differs by
    mode: `full` averages YAVG (whole-frame motion); `center` uses
    `YMAX_avg + 2*YSTD_avg` so peaked local motion + frame richness
    both contribute."""
    if not samples:
        return []
    times = [s[0] for s in samples]
    out: list[tuple[float, float]] = []
    t = 0.0
    end_time = samples[-1][0]
    while t + window <= end_time:
        lo = bisect.bisect_left(times, t)
        hi = bisect.bisect_left(times, t + window)
        if hi > lo:
            seg = samples[lo:hi]
            n = len(seg)
            if scan_mode == "center":
                ymax = sum(s[2] for s in seg) / n
                yrange = sum(s[3] for s in seg) / n
                # Reject flat-color windows outright — they're sky pans,
                # fades, or solid-colored title cards no matter how
                # high their YMAX happens to be from frame noise.
                if yrange < 15.0:
                    t += step
                    continue
                score = ymax + 2.0 * yrange
            else:
                yavg = sum(s[1] for s in seg) / n
                score = yavg
            out.append((t, score))
        t += step
    return out


def juicy_starts(
    video: Path,
    window: float = 30.0,
    step: float = 5.0,
    top_n: int = 20,
    cache: bool = True,
    scan_mode: str = "full",
) -> list[float]:
    """Return start times (seconds) of the top-`top_n` highest-motion
    `window`-second segments in `video`. Result is cached as a JSON
    sidecar file next to the video so the scan only runs once.

    `scan_mode` is folded into the cache key so switching modes
    re-scans rather than returning stale results from the other metric.
    """
    sidecar = video.with_suffix(video.suffix + ".juicy.json")
    cache_key = f"v2_{scan_mode}_w{int(window)}_s{int(step)}_n{top_n}"

    if cache and sidecar.exists():
        try:
            data = json.loads(sidecar.read_text())
            if data.get("cache_key") == cache_key:
                return data["starts"]
        except Exception:  # noqa: BLE001
            pass  # fall through and rescan

    samples = _scan(video, scan_mode=scan_mode)
    windows = _windows(samples, window, step, scan_mode=scan_mode)
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
        sys.exit("usage: gameplay_scanner.py <video> [window] [top_n] [mode]")
    v = Path(sys.argv[1])
    win = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    mode = sys.argv[4] if len(sys.argv) > 4 else "full"
    for s in juicy_starts(v, window=win, top_n=n, scan_mode=mode):
        print(f"  {s:>7.1f}s")
