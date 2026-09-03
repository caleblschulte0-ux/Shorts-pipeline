"""Regression tests for shared/video_qa.py span parsing.

Doctor finding 4754c87f0f7e: `_collect_spans` paired ffmpeg's
`<kind>_start` / `<kind>_end` filter tokens, but a defect still running at
EOF never gets an `_end` token, so the dangling `start` was dropped on the
floor and a render that goes black/frozen/silent through its final frames
reported 0% for that defect. These tests exercise the parser directly
against synthetic ffmpeg stderr text so they need no ffmpeg binary; one
integration test (skipped without ffmpeg) proves the fix actually holds a
tail-black render at the `passes()` layer.

    python -m unittest tests.test_video_qa -v
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import video_qa                                  # noqa: E402

FFMPEG = shutil.which("ffmpeg")


def _lavfi_line(kind: str, which: str, val: float) -> str:
    # Matches video_qa._LAVFI (a `[xxxdetect ...]` prefix) and _SPAN
    # (`<kind>_<start|end>: <float>`), the same shape ffmpeg actually emits.
    tag = {"black": "blackdetect", "freeze": "freezedetect",
           "silence": "silencedetect"}[kind]
    return f"[{tag} @ 0x0] {kind}_{which}:{val}"


class TestCollectSpansEOF(unittest.TestCase):
    def test_closed_interval_unaffected(self):
        stderr = "\n".join([
            _lavfi_line("black", "start", 1.0),
            _lavfi_line("black", "end", 2.5),
        ])
        self.assertEqual(video_qa._collect_spans(stderr, "black", 10.0),
                         [(1.0, 2.5)])

    def test_black_start_with_no_end_closes_at_duration(self):
        stderr = _lavfi_line("black", "start", 8.0)
        self.assertEqual(video_qa._collect_spans(stderr, "black", 10.0),
                         [(8.0, 10.0)])

    def test_freeze_start_with_no_end_closes_at_duration(self):
        stderr = _lavfi_line("freeze", "start", 7.5)
        self.assertEqual(video_qa._collect_spans(stderr, "freeze", 9.0),
                         [(7.5, 9.0)])

    def test_silence_start_with_no_end_closes_at_duration(self):
        stderr = _lavfi_line("silence", "start", 6.25)
        self.assertEqual(video_qa._collect_spans(stderr, "silence", 9.0),
                         [(6.25, 9.0)])

    def test_no_duration_still_closes_instead_of_dropping(self):
        # Caller couldn't supply a duration (e.g. probe was partial) — the
        # span must still surface rather than vanish, even at zero length.
        stderr = _lavfi_line("black", "start", 4.0)
        spans = video_qa._collect_spans(stderr, "black", None)
        self.assertEqual(spans, [(4.0, 4.0)])

    def test_malformed_end_before_start_never_precedes_start(self):
        # A dangling start beyond a (bogus) duration must not yield end<start.
        stderr = _lavfi_line("black", "start", 12.0)
        spans = video_qa._collect_spans(stderr, "black", 10.0)
        self.assertEqual(spans, [(12.0, 12.0)])

    def test_mixed_closed_and_dangling(self):
        stderr = "\n".join([
            _lavfi_line("black", "start", 0.5),
            _lavfi_line("black", "end", 1.0),
            _lavfi_line("black", "start", 8.0),
        ])
        self.assertEqual(video_qa._collect_spans(stderr, "black", 10.0),
                         [(0.5, 1.0), (8.0, 10.0)])

    def test_tail_defect_crosses_pass_threshold(self):
        # 10s render, black from 8s to EOF (20% of runtime) — well past
        # DEFAULT_POLICY's 10% max_black_frac. Before the fix this closed
        # span was dropped entirely and black_frac read 0.0.
        black = video_qa._collect_spans(
            _lavfi_line("black", "start", 8.0), "black", 10.0)
        frac = round(sum(e - s for s, e in black) / 10.0, 4)
        self.assertEqual(frac, 0.2)
        report = {"analyzable": True, "duration": 10.0, "has_video": True,
                  "has_audio": True, "black_frac": frac, "freeze_frac": 0.0,
                  "silence_frac": 0.0, "loudness_lufs": -14.0}
        ok, reasons = video_qa.passes(report)
        self.assertFalse(ok)
        self.assertTrue(any("black" in r for r in reasons))


class TestQAReportIntegration(unittest.TestCase):
    """End-to-end proof the fix holds a real tail-black render, when ffmpeg
    is available to synthesize one."""

    @unittest.skipUnless(FFMPEG, "ffmpeg required")
    def test_tail_black_render_fails_qa(self):
        tmp = Path(tempfile.mkdtemp(prefix="video_qa_eof_"))
        clip = tmp / "tail_black.mp4"
        # 6s of pattern, then hard-cut to 2s of solid black at the very
        # end — the black run is still open when ffmpeg hits EOF.
        filt = ("[0:v]trim=0:6,setpts=PTS-STARTPTS[a];"
                "color=c=black:s=320x568:d=2[b];"
                "[a][b]concat=n=2:v=1:a=0[v]")
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=size=320x568:rate=24:duration=6",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
             "-filter_complex", filt, "-map", "[v]", "-map", "1:a",
             "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(clip)],
            capture_output=True, timeout=120)
        if r.returncode != 0 or not clip.exists():
            self.skipTest(f"fixture render failed: {r.stderr[:300]}")
        report = video_qa.qa_report(str(clip))
        self.assertIsNotNone(report)
        self.assertGreater(report["black_frac"], 0.0,
                            "tail-black span must not read as 0%")
        ok, reasons = video_qa.passes(report)
        self.assertFalse(ok, f"tail-black render should fail QA: {reasons}")


if __name__ == "__main__":
    unittest.main()
