"""render_qa — mechanical render-defect detection for any channel.

The first ANALYSIS engine in the shared layer: instead of producing a new
file, it inspects a finished render and returns a verdict dict. Born from a
real slot burn (third channel, 2026-07-29, run 30459022509): a clip went
through a full render + a paid vision QA call only for the critic to find a
solid-black final frame — a defect a $0, offline ffmpeg pass detects in
seconds. Every channel renders video; none should ship (or spend vision
budget on) a clip with a mechanical defect a filter can catch.

Checks (all ffmpeg/ffprobe, no network, no models):
  - black tail      final frames are solid black (broken concat/pad)
  - black open      the clip STARTS black (bad seek/extract)
  - freeze          any >= `freeze_min_s` stretch of frozen frames
  - A/V drift       video vs audio stream duration mismatch
  - letterbox       near-black bars leave the active picture area under
                    `min_active_ratio` of the frame (double-boxed renders)

Verdict semantics — the one place this differs from the render engines:
`None` from maybe_check() means the ANALYZER failed (ffmpeg missing, probe
error) and callers should proceed as if the engine didn't exist. A video
that fails QA returns a normal dict with ok=False and the problem list.
Never conflate the two: fail-open on analyzer errors, honest on defects.

    from engines.render_qa import maybe_check
    verdict = maybe_check(mp4)
    if verdict and not verdict["ok"]:
        ...reject before spending a vision call / uploading...
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_TIMEOUT = 120


def available() -> bool:
    return (shutil.which("ffmpeg") is not None
            and shutil.which("ffprobe") is not None)


def _probe_durations(video: Path) -> tuple[float, float, float]:
    """(container, video_stream, audio_stream) durations in seconds."""
    def _one(args: list[str]) -> float:
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", *args, "-of", "csv=p=0", str(video)],
            text=True, timeout=30).strip().splitlines()
        try:
            return float(out[0])
        except (IndexError, ValueError):
            return 0.0
    return (_one(["-show_entries", "format=duration"]),
            _one(["-select_streams", "v:0",
                  "-show_entries", "stream=duration"]),
            _one(["-select_streams", "a:0",
                  "-show_entries", "stream=duration"]))


def _detect_pass(video: Path) -> str:
    """One full decode with blackdetect+freezedetect chained; the filters
    log intervals to stderr, which is the only output we need."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
         "-vf", "blackdetect=d=0.3:pix_th=0.10,"
                "freezedetect=n=0.003:d=2.0",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=_TIMEOUT)
    return r.stderr


def _black_intervals(stderr: str) -> list[tuple[float, float]]:
    out = []
    for m in re.finditer(r"black_start:([\d.]+).*?black_end:([\d.]+)",
                         stderr):
        out.append((float(m.group(1)), float(m.group(2))))
    return out


def _freeze_spans(stderr: str) -> list[float]:
    return [float(m.group(1)) for m in
            re.finditer(r"freeze_duration:\s*([\d.]+)", stderr)]


def _active_ratio(video: Path, duration: float) -> float:
    """Largest active (non-black-bar) picture area across three sampled
    windows, as a fraction of the full frame. cropdetect only sees NEAR
    BLACK bars — blurred padding is a stylistic choice some layouts make
    on purpose and is left to the vision critic."""
    dims = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(video)], text=True, timeout=30).strip().split(",")
    full_w, full_h = int(dims[0]), int(dims[1])
    best = 0.0
    for frac in (0.1, 0.5, 0.9):
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats",
             "-ss", f"{max(0.0, duration * frac):.2f}", "-i", str(video),
             "-t", "0.5", "-vf", "cropdetect=limit=24:round=2",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=_TIMEOUT)
        crops = re.findall(r"crop=(\d+):(\d+):\d+:\d+", r.stderr)
        if crops:
            w, h = int(crops[-1][0]), int(crops[-1][1])
            best = max(best, (w * h) / float(full_w * full_h))
    return best if best else 1.0


def check(video: str | Path, *,
          tail_window_s: float = 0.8,
          open_window_s: float = 0.8,
          freeze_min_s: float = 2.0,
          max_av_drift_s: float = 0.35,
          min_active_ratio: float = 0.55) -> dict:
    """Full mechanical QA pass. Raises on analyzer failure (missing file,
    no ffmpeg, probe error) — callers that need the best-effort contract
    use maybe_check(). Returns:

        {"ok": bool, "problems": [str, ...], "metrics": {...}}

    Thresholds are deliberately conservative: this engine exists to catch
    BROKEN renders, not to make taste calls. Anything aesthetic (blurred
    padding, framing, subject size) belongs to a vision critic."""
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(video)
    container, vdur, adur = _probe_durations(video)
    dur = container or vdur
    if dur <= 0:
        raise RuntimeError(f"unprobeable duration for {video}")

    stderr = _detect_pass(video)
    blacks = _black_intervals(stderr)
    freezes = [f for f in _freeze_spans(stderr) if f >= freeze_min_s]

    problems: list[str] = []
    metrics: dict = {"duration_s": round(dur, 2),
                     "v_dur_s": round(vdur, 2), "a_dur_s": round(adur, 2)}

    for start, end in blacks:
        if end >= dur - tail_window_s and (end - start) >= 0.3:
            problems.append(
                f"black tail: final frames from {start:.1f}s are solid "
                f"black — broken output")
            metrics["black_tail_s"] = round(end - start, 2)
            break
    for start, end in blacks:
        if start <= 0.05 and end >= open_window_s:
            problems.append(
                f"black open: clip starts with {end - start:.1f}s of "
                f"black — bad seek/extract")
            metrics["black_open_s"] = round(end - start, 2)
            break
    if freezes:
        problems.append(
            f"freeze: {max(freezes):.1f}s of frozen frames "
            f"(>= {freeze_min_s:.0f}s) — stalled render or dead source")
        metrics["freeze_max_s"] = round(max(freezes), 2)
    if vdur and adur and abs(vdur - adur) > max_av_drift_s:
        problems.append(
            f"a/v drift: video {vdur:.2f}s vs audio {adur:.2f}s "
            f"(> {max_av_drift_s}s) — desync risk")
        metrics["av_drift_s"] = round(abs(vdur - adur), 2)

    ratio = _active_ratio(video, dur)
    metrics["active_area_ratio"] = round(ratio, 3)
    if ratio < min_active_ratio:
        problems.append(
            f"letterbox: active picture is only {ratio:.0%} of the frame "
            f"(< {min_active_ratio:.0%}) — double-boxed render")

    return {"ok": not problems, "problems": problems, "metrics": metrics}


def maybe_check(video, **kwargs) -> dict | None:
    """Best-effort wrapper. None = the ANALYZER failed (treat as 'engine
    absent', proceed unchanged). A dict with ok=False is a real verdict
    on a defective render — do not confuse the two."""
    try:
        if not available():
            print("[engines.render_qa] ffmpeg/ffprobe missing — skipping")
            return None
        return check(video, **kwargs)
    except Exception as e:  # noqa: BLE001 — contract: never raise into a caller
        print(f"[engines.render_qa] failed ({e}) — caller proceeds unchecked")
        return None
