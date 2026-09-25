"""The reddit post card ARRIVES and keeps coming; it does not sit still.

"The post card holds statically over the gameplay for the first ~2.5s",
"the hook is a static post card over gameplay" — every reddit_story
verdict of 2026-09-25. The card now eases up from 82% and pushes in while
the title is read. It grows about its own centre, and it is MONOTONIC: an
overshoot would be a time-driven oscillator, the retired camera shake's
signature (tests/test_camera_float.py).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import make_reddit_story as M  # noqa: E402


def _card_span(png: Path):
    """Columns the (opaque, white-ish) card covers on row 400."""
    from PIL import Image
    with Image.open(png) as im:
        im = im.convert("RGB")
        xs = [x for x in range(im.width)
              if sum(im.getpixel((x, 400))) > 600]
    return (min(xs), max(xs)) if xs else None


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class TheCardArrives(unittest.TestCase):
    def test_it_grows_monotonically_about_its_centre(self):
        import reddit_card
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            card = reddit_card.build_card(
                td / "card.png", subreddit="r/test", username="u/x",
                title="My landlord kept my deposit so I kept a receipt")
            te = 2.4
            ch = M._card_height(card, 980)
            graph = (
                f"[1:v]format=rgba,scale=w='{M.card_scale_expr(980, te)}'"
                f":h=-2:eval=frame[c];"
                f"[0:v][c]overlay=x='(W-w)/2':y='220+({ch}-h)/2'[v]")
            out = td / "o.mp4"
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={te}",
                 "-loop", "1", "-t", str(te), "-i", str(card),
                 "-filter_complex", graph, "-map", "[v]", "-r", "24",
                 str(out)], check=True)
            widths, centres = [], []
            for k, t in enumerate((0.04, 0.2, 0.6, 1.4, 2.3)):
                f = td / f"f{k}.png"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                                "-ss", str(t), "-i", str(out),
                                "-frames:v", "1", str(f)], check=True)
                span = _card_span(f)
                self.assertIsNotNone(span, t)
                widths.append(span[1] - span[0])
                centres.append((span[0] + span[1]) / 2)
            self.assertEqual(widths, sorted(widths), widths)
            self.assertLess(widths[0], widths[-1] * 0.9)     # it arrives
            self.assertGreater(widths[-1], widths[2])        # it keeps coming
            for c in centres:
                self.assertAlmostEqual(c, 540, delta=6)


class ItIsWired(unittest.TestCase):
    def test_the_renderer_scales_the_card_per_frame(self):
        src = (ROOT / "make_reddit_story.py").read_text()
        self.assertIn("card_scale_expr(card_w, title_end)", src)
        self.assertIn("eval=frame", src)

    def test_the_expression_has_no_oscillator(self):
        e = M.card_scale_expr(980, 2.4)
        self.assertNotIn("sin(", e)
        self.assertNotIn("cos(", e)


if __name__ == "__main__":
    unittest.main()
