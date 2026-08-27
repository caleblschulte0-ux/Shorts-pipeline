"""Finished-video technical QA — catch broken renders BEFORE they upload.

Runs pure-ffmpeg analysis (no new dependencies) over a rendered file and
reports the defects that have actually shipped from this pipeline at least
once: black frames, frozen frames, silent stretches, missing audio, and
loudness way off the platform target. One ffmpeg pass, CPU-cheap.

Contract (matches engines/): ``qa_report()`` returns a dict or ``None`` —
it NEVER raises into a caller. ``passes()`` is a pure function over the
report, so channels can share the analysis but keep their own thresholds.

Usage (opt-in from any channel, right before upload):

    from shared import video_qa
    report = video_qa.qa_report(mp4_path)
    ok, reasons = video_qa.passes(report)
    if not ok:
        ...  # hold the upload / re-render / log — channel's call

CLI:  python -m shared.video_qa out.mp4 [--json]
Exit: 0 pass, 1 fail, 2 could-not-analyze.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

# Detection tunings. Deliberately conservative: flag what a viewer would
# actually notice, not every quiet frame.
BLACK_MIN_S = 0.4       # blackdetect: minimum run length reported
FREEZE_MIN_S = 2.0      # freezedetect: shorter static shots are normal
SILENCE_DB = "-35dB"    # silencedetect threshold
SILENCE_MIN_S = 2.5

# Default pass/fail policy (overridable per call).
DEFAULT_POLICY = {
    "max_black_frac": 0.10,      # >10% of runtime black -> broken render
    "max_freeze_frac": 0.35,     # >35% frozen -> slideshow, not a video
    "max_silence_frac": 0.50,    # >50% silent -> narration probably missing
    "require_audio": True,
    "min_duration_s": 3.0,
    "max_duration_s": 0,         # 0 = no cap
    "loudness_low": -30.0,       # integrated LUFS sanity band; YouTube
    "loudness_high": -8.0,       # normalizes to ~-14, this only flags junk
}

_SPAN = re.compile(
    r"(black|silence|freeze)_(start|end|duration)[:\s]+([0-9.]+)")
_LAVFI = re.compile(r"\[(?:blackdetect|freezedetect|silencedetect)")
_I_LUFS = re.compile(r"I:\s*(-?[0-9.]+)\s*LUFS")


def _ffprobe(path: str) -> dict | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout) if out.returncode == 0 else None
    except Exception:
        return None


def _collect_spans(stderr: str, kind: str,
                    duration: float | None = None) -> list[tuple[float, float]]:
    """Pair up <kind>_start / <kind>_end times from ffmpeg filter logs.

    A defect that is still running when the encode hits EOF never gets an
    `_end` token from ffmpeg, so a dangling `start` used to be dropped on the
    floor here — a render that goes black or silent for its last three
    seconds reported 0% black/silence for that run. If ``duration`` is
    known, an unclosed start is closed at the media's end (clamped so it
    never precedes its own start); otherwise it is closed at zero length so
    it is at least visible rather than silently discarded.
    """
    spans, start = [], None
    for line in stderr.splitlines():
        if not _LAVFI.search(line):
            continue
        for m in _SPAN.finditer(line):
            k, which, val = m.group(1), m.group(2), float(m.group(3))
            if k != kind:
                continue
            if which == "start":
                start = val
            elif which == "end" and start is not None:
                spans.append((start, val))
                start = None
    if start is not None:
        end = duration if duration is not None else start
        spans.append((start, max(start, end)))
    return spans


def qa_report(path, *, timeout: int = 300, black_min_s: float = BLACK_MIN_S,
              pic_th: float = 0.98, freeze_min_s: float = FREEZE_MIN_S,
              silence_db: str = SILENCE_DB, silence_min_s: float = SILENCE_MIN_S
              ) -> dict | None:
    """Analyze a finished render. Returns a report dict, or None if the
    file cannot be analyzed at all (missing ffmpeg, unreadable file).

    Detection knobs are per-call: a deliberately dark-styled channel (black
    background + line art) should raise ``pic_th`` toward 1.0 so its house
    style doesn't read as dead frames; a music-heavy channel can loosen
    ``silence_db``. Pass/fail thresholds live separately in ``passes()``."""
    try:
        probe = _ffprobe(path)
        if probe is None or not probe.get("streams"):
            return None
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration") or 0.0)
        vstreams = [s for s in probe["streams"] if s.get("codec_type") == "video"]
        astreams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        if not vstreams or duration <= 0:
            return {"duration": duration, "has_video": bool(vstreams),
                    "has_audio": bool(astreams), "analyzable": False}

        vf = (f"blackdetect=d={black_min_s}:pic_th={pic_th},"
              f"freezedetect=n=-60dB:d={freeze_min_s}")
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
               "-vf", vf]
        if astreams:
            cmd += ["-af",
                    f"silencedetect=n={silence_db}:d={silence_min_s},"
                    f"ebur128=framelog=quiet"]
        cmd += ["-f", "null", "-"]
        run = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout)
        err = run.stderr

        black = _collect_spans(err, "black", duration)
        freeze = _collect_spans(err, "freeze", duration)
        silence = _collect_spans(err, "silence", duration)
        loud = None
        mloud = _I_LUFS.findall(err)
        if mloud:
            loud = float(mloud[-1])

        def frac(spans):
            return round(sum(e - s for s, e in spans) / duration, 4)

        return {
            "analyzable": True,
            "duration": round(duration, 3),
            "width": vstreams[0].get("width"),
            "height": vstreams[0].get("height"),
            "has_video": True,
            "has_audio": bool(astreams),
            "black_spans": black, "black_frac": frac(black),
            "freeze_spans": freeze, "freeze_frac": frac(freeze),
            "silence_spans": silence, "silence_frac": frac(silence),
            "loudness_lufs": loud,
        }
    except Exception:
        return None


def passes(report: dict | None, policy: dict | None = None
           ) -> tuple[bool, list[str]]:
    """Pure pass/fail over a report. None/unanalyzable -> fail closed
    with a reason, so a QA infrastructure failure can't silently ship."""
    p = dict(DEFAULT_POLICY, **(policy or {}))
    if report is None:
        return False, ["not analyzable (ffmpeg/ffprobe failed or missing)"]
    reasons: list[str] = []
    if not report.get("has_video"):
        reasons.append("no video stream")
    if not report.get("analyzable"):
        reasons.append("stream present but not analyzable")
        return False, reasons
    d = report["duration"]
    if d < p["min_duration_s"]:
        reasons.append(f"too short: {d:.1f}s < {p['min_duration_s']}s")
    if p["max_duration_s"] and d > p["max_duration_s"]:
        reasons.append(f"too long: {d:.1f}s > {p['max_duration_s']}s")
    if p["require_audio"] and not report["has_audio"]:
        reasons.append("no audio stream")
    if report["black_frac"] > p["max_black_frac"]:
        reasons.append(f"black {report['black_frac']:.0%} of runtime "
                       f"(max {p['max_black_frac']:.0%})")
    if report["freeze_frac"] > p["max_freeze_frac"]:
        reasons.append(f"frozen {report['freeze_frac']:.0%} of runtime "
                       f"(max {p['max_freeze_frac']:.0%})")
    if report["has_audio"] and report["silence_frac"] > p["max_silence_frac"]:
        reasons.append(f"silent {report['silence_frac']:.0%} of runtime "
                       f"(max {p['max_silence_frac']:.0%})")
    loud = report.get("loudness_lufs")
    if loud is not None and not (p["loudness_low"] <= loud <= p["loudness_high"]):
        reasons.append(f"loudness {loud:.1f} LUFS outside "
                       f"[{p['loudness_low']}, {p['loudness_high']}]")
    return (not reasons), reasons


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    report = qa_report(args.video)
    ok, reasons = passes(report)
    if args.json:
        print(json.dumps({"report": report, "pass": ok, "reasons": reasons},
                         indent=2))
    else:
        if report:
            print(f"{args.video}: {report['duration']}s "
                  f"{report.get('width')}x{report.get('height')} "
                  f"audio={report['has_audio']} "
                  f"black={report.get('black_frac', 0):.0%} "
                  f"freeze={report.get('freeze_frac', 0):.0%} "
                  f"silence={report.get('silence_frac', 0):.0%} "
                  f"loudness={report.get('loudness_lufs')}")
        print("PASS" if ok else "FAIL: " + "; ".join(reasons))
    if report is None:
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
