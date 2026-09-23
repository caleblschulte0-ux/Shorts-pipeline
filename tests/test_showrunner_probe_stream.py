"""The showrunner's motion probes stream now — and say exactly what they said.

`_motion_evidence` and `_temporal_evidence` used to write every sampled frame
to a PNG and hold all of them as Python lists. For a 40-second short that is
nothing; for a two-hour OpenRangeInteractive sleep film it is 172,800 frames
and the runner runs out of memory, which the gate reads as an unmeasured
probe and HOLDS — every week, green the whole way. They now pipe raw frames
through the same ffmpeg filters and keep only what the arithmetic needs.

This is a cleanup of a load-bearing gate, so the test is EQUIVALENCE
(`tests/test_captions.py` pattern): the previous implementations are kept
below VERBATIM as oracles, and both are run on the same videos. A probe
that answered differently would be a quietly moved gate.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import showrunner_review as SR  # noqa: E402


# ---------------------------------------------------------------- the oracles
# (scripts/showrunner_review.py before 2026-09-23, verbatim but for names)
def old_motion_evidence(mp4: Path, td: Path) -> dict:
    """Objective, code-measured motion facts (NOT a judgement). Samples the whole
    clip at ~3fps and reports the longest near-frozen run (seconds) and the
    fraction of near-black frames. Vision judges whether motion is *meaningful*;
    this decides whether motion *exists* — so 'dead air' can't be averaged away."""
    ev = {"longest_static_s": 0.0, "static_at_s": None, "dark_fraction": 0.0,
          "sampled": 0}
    try:
        from PIL import Image
        fps = 3
        seq = td / "mv"
        seq.mkdir(exist_ok=True)
        # 160px (was 96) so a moving mascot registers as motion the way a human
        # sees it — 96px was too coarse and false-flagged a moving closing.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
             "-vf", f"fps={fps},scale=160:-1,format=gray", str(seq / "m%04d.png")],
            check=True)
        imgs = sorted(seq.glob("m*.png"))
        ev["sampled"] = len(imgs)
        if len(imgs) < 2:
            return ev
        px = [list(Image.open(p).getdata()) for p in imgs]
        n = len(px)
        dark = sum(1 for p in px if (sum(p) / len(p)) < 22)
        ev["dark_fraction"] = round(dark / n, 3)
        # DEAD AIR = a stretch where NO block changes over ~1s (1s LOOKBACK, not
        # consecutive frames) so a SMOOTH build reads as motion; only a genuine
        # static hold registers. Block-max (not a whole-frame mean) so a small
        # animating region still counts as motion. Also report WHERE it starts.
        lb = fps
        run = best = best_end = 0
        for i in range(lb, n):
            a, b = px[i], px[i - lb]
            diff = SR._max_block_diff(a, b, 160)
            if diff < SR.BLOCK_MOTION_THRESH:
                run += 1
                if run > best:
                    best, best_end = run, i
            else:
                run = 0
        ev["longest_static_s"] = round(best / fps, 2)
        if best:
            ev["static_at_s"] = round((best_end - best) / fps, 2)   # run start
    except Exception as e:  # noqa: BLE001
        ev["error"] = str(e)[:120]
    return ev


def old_temporal_evidence(mp4: Path, td: Path) -> dict:
    """CADENCE facts: does the video actually move at its export rate, or is a
    low-fps source animation duplicated into a 30fps timeline (visible judder)?
    Samples at 24fps and reports the duplicate-frame ratio, the EFFECTIVE unique
    frame rate, and the longest duplicate run. Objective — this is what a 90 on
    pretty stills was hiding."""
    ev = {"sample_fps": 24, "duplicate_ratio": None, "effective_fps": None,
          "max_dup_run": None, "measured": False}
    try:
        from PIL import Image
        sf = 24
        seq = td / "tc"
        seq.mkdir(exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
             "-vf", f"fps={sf},scale=192:-1,format=gray", str(seq / "t%05d.png")],
            check=True)
        imgs = sorted(seq.glob("t*.png"))
        if len(imgs) < 3:
            ev["error"] = f"only {len(imgs)} sampled frames — nothing to measure"
            return ev
        px = [list(Image.open(p).getdata()) for p in imgs]
        n = len(px)
        dup = run = maxrun = 0
        run_start = maxrun_start = 0
        for _i, (a, b) in enumerate(zip(px, px[1:])):
            # Block-max, not a whole-frame mean: a frame is a DUPLICATE only if
            # NO block moved. A whole-frame mean diluted a chart that fills part
            # of the frame down below 0.8 and mislabelled smooth builds as held
            # (effective_fps ~10 on a genuinely-30fps render). Choppy low-fps
            # source dup still shows identical blocks -> still caught.
            if SR._max_block_diff(a, b, 192) < SR.BLOCK_MOTION_THRESH:
                dup += 1
                if run == 0:
                    run_start = _i
                run += 1
                if run > maxrun:
                    maxrun, maxrun_start = run, run_start
            else:
                run = 0
        pairs = n - 1
        ev["duplicate_ratio"] = round(dup / pairs, 3)
        ev["effective_fps"] = round(sf * (1 - dup / pairs), 1)
        ev["max_dup_run"] = maxrun + 1        # frames
        # WHERE it froze, not just that it did. Every frozen-stretch block so
        # far has cost a full render to localise by guesswork; the timestamp
        # turns the next one into a single look at the video.
        ev["max_dup_at_s"] = round(maxrun_start / float(sf), 2)
        ev["duration_s"] = round(n / float(sf), 2)
        ev["measured"] = True
    except Exception as e:  # noqa: BLE001
        ev["error"] = str(e)[:120]
    return ev


def _video(path: Path, w: int, h: int) -> None:
    """Motion, a hard hold, a dark stretch, a slow fade and small local
    motion — everything the probes are meant to tell apart."""
    lav = (f"testsrc2=s={w}x{h}:r=24:d=3[a];"
           f"color=c=0x303a50:s={w}x{h}:r=24:d=2[b];"
           f"color=c=black:s={w}x{h}:r=24:d=1.5[c];"
           f"testsrc=s={w}x{h}:r=24:d=2,fade=t=out:st=0.5:d=1.5[d];"
           f"color=c=0x507040:s={w}x{h}:r=24:d=2,drawbox=x='mod(t*60,{w})':y=20:w=30:h=30:c=white:t=fill[e];"
           f"[a][b][c][d][e]concat=n=5:v=1:a=0[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", lav, "-map", "[v]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(path)], check=True)


class TheStreamingProbesAnswerExactlyAsBefore(unittest.TestCase):
    def _both(self, w, h):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mp4 = tdp / "v.mp4"
            _video(mp4, w, h)
            o1 = tdp / "o1"
            o1.mkdir()
            o2 = tdp / "o2"
            o2.mkdir()
            return ((old_motion_evidence(mp4, o1), SR._motion_evidence(mp4, o2)),
                    (old_temporal_evidence(mp4, o1), SR._temporal_evidence(mp4, o2)))

    def test_landscape(self):
        (m_old, m_new), (t_old, t_new) = self._both(640, 360)
        self.assertEqual(m_old, m_new)
        self.assertEqual(t_old, t_new)
        self.assertTrue(t_new["measured"])
        self.assertGreater(t_new["duplicate_ratio"], 0.0)       # the hold registered
        self.assertLess(t_new["duplicate_ratio"], 1.0)          # and so did the motion

    def test_portrait(self):
        (m_old, m_new), (t_old, t_new) = self._both(360, 640)
        self.assertEqual(m_old, m_new)
        self.assertEqual(t_old, t_new)

    def test_block_diff_matches_on_every_shape(self):
        import numpy as np
        r = random.Random(7)
        for w, h in ((192, 108), (160, 90), (160, 284), (192, 341), (50, 9), (37, 23)):
            for _ in range(20):
                a = [r.randrange(256) for _ in range(w * h)]
                b = [min(255, max(0, v + r.randrange(-30, 31))) if r.random() < 0.3 else v for v in a]
                self.assertAlmostEqual(
                    SR._max_block_diff(a, b, w),
                    SR._max_block_diff_np(np.array(a, np.uint8), np.array(b, np.uint8), w), places=9)

    def test_a_missing_file_is_unmeasured_not_a_pass(self):
        with tempfile.TemporaryDirectory() as td:
            ev = SR._temporal_evidence(Path(td) / "nope.mp4", Path(td))
        self.assertFalse(ev["measured"])
        self.assertIn("error", ev)
        self.assertIsNotNone(SR.temporal_unmeasured(ev))


if __name__ == "__main__":
    unittest.main()
