#!/usr/bin/env python3
"""Smoke suite for the clip pipeline — catches "worked on my one clip" bugs.

Every failure we hit in production was an unusual INPUT breaking an
assumption, found only after it wasted a slot: an apostrophe hook crashing
the filtergraph, a near-silent clip collapsing to a 2s cut, a portrait
source. This runs the REAL edit() + preflight + QA on synthetic fixtures
that deliberately carry those tricky inputs, so a regression goes red here
(seconds, no network, no upload) instead of on the channel.

Run locally before pushing; runs in CI on every push to the third pipeline.
Exit 0 = all green, 1 = a case failed.

    python scripts/smoke_third.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from third_capture import clip_edit, clip_qa  # noqa: E402


def _fixture(path: Path, dur: int = 12, w: int = 1280, h: int = 720) -> None:
    """A moving-pattern + tone clip: animated (no freeze), audible (no
    silence), 16:9 — a stand-in for a real streamer clip."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=30:d={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)], check=True, timeout=120)


def _dur(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True, timeout=30)
    return float(out.strip() or 0)


CASES = [
    # (name, words, hook, series) — words are cut-relative {w,s,e}
    ("apostrophe_hook",
     [{"w": "CAN'T", "s": 1.0, "e": 1.4}, {"w": "believe", "s": 1.5, "e": 2.0},
      {"w": "it", "s": 2.1, "e": 2.3}, {"w": "happened", "s": 2.4, "e": 3.0},
      {"w": "bro", "s": 3.1, "e": 3.4}, {"w": "no", "s": 5.0, "e": 5.3},
      {"w": "way", "s": 5.4, "e": 5.8}],
     "HE CAN'T BELIEVE IT", "fail"),
    # near-silent reaction: 1 word — the cut must NOT collapse to ~2s
    ("sparse_speech",
     [{"w": "yo", "s": 1.0, "e": 1.3}],
     "", "chaos"),
    # empty transcript (screaming/crowd moment)
    ("no_speech", [], "WAIT FOR IT", "rage"),
]


def run_case(name, words, hook, series, work: Path,
             edit_mode: bool = False) -> list[str]:
    fails = []
    src = work / f"{name}_src.mp4"
    out = work / f"{name}_out.mp4"
    _fixture(src)

    if clip_qa.preflight(src):
        return [f"{name}: a valid fixture failed preflight"]

    try:
        led = clip_edit.edit(src, out, credit="twitch.tv/test", hook=hook,
                             words=list(words), auto=True, series=series,
                             edit_mode=edit_mode)
    except Exception as e:  # noqa: BLE001
        return [f"{name}: edit() RAISED {type(e).__name__}: {e}"]

    if not out.exists():
        return [f"{name}: no output file produced"]
    d = _dur(out)
    if not (4.0 <= d <= 62.0):
        fails.append(f"{name}: output duration {d:.1f}s out of bounds")
    # the sparse/no-speech cases must keep a real clip, not a 2s sliver
    if name in ("sparse_speech", "no_speech") and d < 8.0:
        fails.append(f"{name}: cut collapsed to {d:.1f}s (sparse guard)")
    qa = clip_qa.review(out, led, work)
    mech = [p for p in qa["problems"] if not p.startswith("vision:")]
    if mech:
        fails.append(f"{name}: QA mechanical problems {mech}")
    print(f"  [{name}] dur={d:.1f}s render_level={led.get('render_level')} "
          f"qa={qa['verdict']} mech_ok={not mech}", flush=True)
    return fails


def main() -> int:
    print("smoke_third: pipeline self-test on synthetic tricky inputs")
    all_fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        # preflight negatives
        (work / "corrupt.mp4").write_bytes(b"not a video")
        if not clip_qa.preflight(work / "corrupt.mp4"):
            all_fails.append("preflight: corrupt file passed (should fail)")
        _fixture(work / "tiny.mp4", dur=3, w=320, h=240)
        if not clip_qa.preflight(work / "tiny.mp4"):
            all_fails.append("preflight: 3s/320p passed (should fail)")
        for name, words, hook, series in CASES:
            all_fails += run_case(name, words, hook, series, work)
        # A/B EDIT ARM: the montage render path must also survive the tricky
        # inputs (it's what the 3 daily edit-arm slots use). Re-run the base
        # case with edit_mode=True and hold it to the same mechanical bar.
        base = CASES[0]
        all_fails += run_case("edit_" + base[0], base[1], base[2], base[3],
                              work, edit_mode=True)
    if all_fails:
        print("\nSMOKE FAILED:")
        for f in all_fails:
            print("  -", f)
        return 1
    print("\nSMOKE PASSED — pipeline healthy on tricky inputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
