"""Operator, 2026-10-13, of the Kai/Reggie cut: a commentator sat on one
side of the frame with the texts he was reading on the other, and the
crop "tried to split the difference and ended up catching nothing". When a
face sits to one side of something worth seeing, both are shown: what is
shown on top, the face below, nothing on screen twice."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from third_capture import shot_plan as sp

SW, SH = 1920, 1080


def _face(cx, cy=540, h=260, presence=0.9):
    s = sp.Subject(cx=cx, cy=cy, n=10, hs=[h] * 10, xs=[cx] * 10)
    s.presence = presence
    return s


def _an(subjects, busy=(0, 1100), detail=8.0, rest=8.0):
    det = [detail if busy[0] <= i < busy[1] else rest for i in range(SW)]
    return {"sw": SW, "sh": SH, "subjects": subjects, "col_detail": det,
            "col_energy": [1.0] * SW}


class AFaceBesideWhatItShows(unittest.TestCase):

    def test_a_commentator_on_the_right_gets_the_texts_on_top(self):
        b = sp.face_and_content(_an([_face(1600)]))
        self.assertIsNotNone(b)
        self.assertEqual(b["side"], "right")
        cw, ch, cx, cy = b["content"]
        fw, fh, fx, fy = b["face"]
        self.assertLessEqual(cx + cw, fx, "the two halves never overlap")
        self.assertTrue(fx <= 1600 <= fx + fw, "the face is in its panel")
        self.assertAlmostEqual(cw / ch, 1080 / 960, places=1)
        self.assertAlmostEqual(fw / fh, 1080 / 960, places=1)

    def test_and_on_the_left_the_same(self):
        b = sp.face_and_content(_an([_face(300)], busy=(800, 1920)))
        self.assertEqual(b["side"], "left")
        self.assertGreaterEqual(b["content"][2],
                                b["face"][2] + b["face"][0])

    def test_a_centred_face_is_left_to_the_other_layouts(self):
        self.assertIsNone(sp.face_and_content(_an([_face(960)])))

    def test_a_blank_wall_beside_him_is_not_content(self):
        an = _an([_face(1600)], busy=(1300, 1920), detail=8.0, rest=0.5)
        self.assertIsNone(sp.face_and_content(an))

    def test_two_faces_stay_the_splits_job(self):
        self.assertIsNone(sp.face_and_content(
            _an([_face(300), _face(1600)])))

    def test_a_face_that_fills_the_frame_is_not_split(self):
        self.assertIsNone(sp.face_and_content(_an([_face(1500, h=900)])))

    def test_a_portrait_source_is_left_alone(self):
        an = _an([_face(900)])
        an.update(sw=1080, sh=1920, col_detail=[8.0] * 1080)
        self.assertIsNone(sp.face_and_content(an))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg")
class ItRendersAsTwoHalves(unittest.TestCase):

    def test_the_render_is_a_full_canvas(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                            "-i", f"testsrc2=s={SW}x{SH}:d=1:r=30",
                            "-pix_fmt", "yuv420p", str(src)], check=True)
            b = sp.face_and_content(_an([_face(1600)]))
            out = sp._render_face_content(src, b, Path(d) / "o.mp4")
            self.assertIsNotNone(out)
            wh = subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0",
                 str(out)], text=True).strip()
            self.assertEqual(wh, "1080,1920")


class TheAnalysisMeasuresWhatIsThereToSee(unittest.TestCase):

    def test_analyze_returns_a_detail_profile(self):
        import inspect
        self.assertIn('"col_detail"', inspect.getsource(sp.analyze))


if __name__ == "__main__":
    unittest.main()
