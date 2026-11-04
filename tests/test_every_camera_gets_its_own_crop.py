"""Operator, 2026-11-03, of Wembanyama's sit-down interview: "The cutting
sucks." The interviewer sat front-on right of centre and Wembanyama was
shot in profile at the left edge. The face finder saw only the front-on
face, so the one crop for the whole clip was the interviewer's, and every
shot of Wembanyama was half a face, a jacket, then empty background.

A camera cut is a new picture and gets its own framing, and a face in
profile is a face. A clip one crop already serves is left exactly as it
was."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from third_capture import shot_plan as sp

SW, SH = 1920, 1080


def _subject(cx, h=420):
    s = sp.Subject(cx=cx, cy=540, n=30, hs=[h] * 30, xs=[cx] * 30)
    s.presence = 0.9
    return s


def _an(shots, faces, dur=None):
    """`shots`: cut times. `faces`: (t0, t1, cx, h, kind) a face holds."""
    dur = dur or 10.0
    ts = [round(i / 6, 3) for i in range(int(dur * 6))]
    dets = [(t, cx, 540.0, float(h), kind) for (a, b, cx, h, kind) in faces
            for t in ts if a <= t < b]
    return {"sw": SW, "sh": SH, "dur": dur, "fps": 30.0, "cuts": shots,
            "ts": ts, "dets": dets, "samples": len(ts),
            "subjects": [], "col_energy": [1.0] * SW,
            "col_detail": [1.0] * SW}


def _holds(crop, cx):
    w, _h, x, _y = crop
    return x + w * 0.08 <= cx <= x + w * 0.92


class EveryCameraGetsItsOwnCrop(unittest.TestCase):

    def test_the_wembanyama_interview(self):
        # interviewer front-on at 1400, Wemby in profile at 300
        an = _an([5.0], [(0, 5, 1400, 420, "front"),
                         (5, 10, 300, 480, "profile")])
        cams = sp.cameras(an, "closeup", [_subject(1400)], "one face")
        self.assertIsNotNone(cams, "one crop cuts Wembanyama off")
        self.assertEqual([(c["t0"], c["t1"]) for c in cams],
                         [(0.0, 5.0), (5.0, 10.0)])
        self.assertTrue(_holds(cams[0]["crop"], 1400))
        self.assertTrue(_holds(cams[1]["crop"], 300),
                        "the shot of him is framed on him")
        for c in cams:
            self.assertAlmostEqual(c["crop"][0] / c["crop"][1], 9 / 16,
                                   places=2)

    def test_one_camera_is_left_as_it_was(self):
        an = _an([], [(0, 10, 1400, 420, "front")])
        self.assertIsNone(sp.cameras(an, "closeup", [_subject(1400)], ""))

    def test_cuts_that_one_crop_already_serves_change_nothing(self):
        an = _an([3.0, 6.0], [(0, 3, 1400, 420, "front"),
                              (3, 6, 1450, 420, "front"),
                              (6, 10, 1380, 420, "front")])
        self.assertIsNone(sp.cameras(an, "closeup", [_subject(1400)], ""))

    def test_a_shot_with_no_face_keeps_the_clips_window(self):
        an = _an([4.0, 7.0], [(0, 4, 1400, 420, "front"),
                              (7, 10, 300, 480, "profile")])
        cams = sp.cameras(an, "closeup", [_subject(1400)], "")
        self.assertEqual(cams[1]["crop"], cams[0]["crop"],
                         "the wide shot between them keeps the clip's crop")
        self.assertTrue(_holds(cams[2]["crop"], 300))

    def test_a_player_far_off_does_not_frame_a_shot(self):
        # game footage: a small face at the edge is not a party to frame on
        an = _an([5.0], [(5, 10, 200, 60, "front")])
        self.assertIsNone(sp.cameras(an, "wide", [], ""))

    def test_a_face_in_part_of_a_shot_does_not_frame_it(self):
        an = _an([5.0], [(0, 5, 1400, 420, "front"),
                         (5, 6, 300, 480, "profile")])
        self.assertIsNone(sp.cameras(an, "closeup", [_subject(1400)], ""))

    def test_a_portrait_source_is_left_alone(self):
        an = _an([5.0], [(0, 5, 500, 420, "front"),
                         (5, 10, 100, 480, "profile")])
        an.update(sw=1080, sh=1920)
        self.assertIsNone(sp.cameras(an, "closeup", [], ""))

    def test_the_split_and_the_facecam_layouts_are_not_touched(self):
        an = _an([5.0], [(0, 5, 1400, 420, "front"),
                         (5, 10, 300, 480, "profile")])
        for layout in ("split", "facecam_gameplay"):
            self.assertIsNone(sp.cameras(an, layout, [], ""))

    def test_a_flash_of_a_shot_joins_its_neighbour(self):
        an = _an([0.3, 5.0, 9.8], [])
        self.assertEqual(sp.shots_of(an), [(0.0, 5.0), (5.0, 10.0)])


class ACutIsSeen(unittest.TestCase):

    def setUp(self):
        try:
            import numpy  # noqa: F401
            import cv2  # noqa: F401
        except ImportError:
            self.skipTest("cv2")

    def test_a_dim_sit_down_cut_is_a_cut(self):
        import numpy as np
        usual = []
        a = np.full((36, 64), 20, np.uint8)
        a[5:30, 40:60] = 70                      # him, right of frame
        for _ in range(20):
            self.assertFalse(sp._is_cut(a, a, usual))
        b = np.full((36, 64), 20, np.uint8)
        b[2:36, 0:22] = 60                       # the other camera
        self.assertTrue(sp._is_cut(a, b, usual))

    def test_a_panning_broadcast_is_not_a_cut_every_frame(self):
        import numpy as np
        rng = np.random.default_rng(1)
        usual, frames = [], [rng.integers(0, 255, (36, 64), np.uint8)]
        for _ in range(40):
            frames.append(np.roll(frames[-1], 1, axis=1))
        hits = sum(sp._is_cut(a, b, usual) for a, b in zip(frames[10:],
                                                           frames[11:]))
        self.assertEqual(hits, 0)

    def test_the_profile_finder_is_installed(self):
        self.assertTrue(Path(sp.PROFILE_CASCADE).exists(),
                        "a face in profile is a face")


class TheGateRefusesABadCrop(unittest.TestCase):

    def test_a_speaker_cut_off_by_the_frame_is_junk(self):
        # the shipped Wembanyama cut passed at 91: the judge must look
        from scripts.showrunner_review import _format_directive
        text = _format_directive({"format": "sports_moment"})
        self.assertIn("CROP cuts off who matters", text)
        self.assertIn("half out of frame", text)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg")
class ItRendersEveryShot(unittest.TestCase):

    def test_the_render_is_a_full_canvas_of_the_whole_clip(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                            "-i", f"testsrc2=s={SW}x{SH}:d=4:r=30",
                            "-pix_fmt", "yuv420p", str(src)], check=True)
            an = _an([2.0], [(0, 2, 1400, 420, "front"),
                             (2, 4, 300, 480, "profile")], dur=4.0)
            cams = sp.cameras(an, "closeup", [_subject(1400)], "")
            out = sp._render_cameras(src, cams, an, Path(d) / "o.mp4")
            self.assertIsNotNone(out)
            got = subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height:format=duration",
                 "-of", "csv=p=0", str(out)], text=True).split()
            self.assertEqual(got[0], "1080,1920")
            self.assertAlmostEqual(float(got[1]), 4.0, delta=0.15)

    def test_a_whole_frame_shot_is_blur_filled_not_stretched(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                            "-i", f"testsrc2=s={SW}x{SH}:d=2:r=30",
                            "-pix_fmt", "yuv420p", str(src)], check=True)
            an = _an([], [], dur=2.0)
            cams = [{"t0": 0.0, "t1": 1.0, "crop": (608, 1080, 0, 0)},
                    {"t0": 1.0, "t1": 2.0, "crop": None}]
            out = sp._render_cameras(src, cams, an, Path(d) / "o.mp4")
            self.assertIsNotNone(out)


if __name__ == "__main__":
    unittest.main()
