"""Operator, 2026-10-08: "Our hook and first 10 seconds need to be better."

Rendered, two posted openings began on the SMALLEST state of their picture:
an empty dark frame with "Your kid's" under it while a bar chart grew out of
nothing, and a knee-high pile of sand that only became the 50-billion-tonne
mountain at second five. The opening picture now flashes forward: its
finished frame fills the first FLASH_S seconds, then the build plays."""
import ast
import inspect
import tempfile
import unittest
from pathlib import Path

from PIL import Image


def _seq(d: Path, n: int) -> str:
    for k in range(1, n + 1):
        Image.new("RGB", (8, 8), (k * 5 % 256, 0, 0)).save(d / f"b_build{k:02d}.png")
    return str(d / "b_build%02d.png")


class TheOpeningShowsTheFinishedPicture(unittest.TestCase):

    def test_the_first_frames_are_the_last_frame(self):
        from data_learning import studio_render as R
        with tempfile.TemporaryDirectory() as td:
            pat = _seq(Path(td), 60)
            last = Image.open(pat % 60).tobytes()
            n = R.flash_forward(pat, secs=0.5)
            self.assertEqual(n, 15)
            for k in range(1, 16):
                self.assertEqual(Image.open(pat % k).tobytes(), last, k)
            # then it cuts back and builds
            self.assertNotEqual(Image.open(pat % 16).tobytes(), last)

    def test_a_short_build_is_left_alone(self):
        from data_learning import studio_render as R
        with tempfile.TemporaryDirectory() as td:
            pat = _seq(Path(td), 20)
            first = Image.open(pat % 1).tobytes()
            self.assertEqual(R.flash_forward(pat, secs=0.5), 0)
            self.assertEqual(Image.open(pat % 1).tobytes(), first)

    def test_not_a_sequence_is_left_alone(self):
        from data_learning import studio_render as R
        self.assertEqual(R.flash_forward("/nonexistent/x%02d.png"), 0)

    def test_the_render_opens_with_it(self):
        from data_learning import studio_render as R
        calls = [n for n in ast.walk(ast.parse(inspect.getsource(R.render)))
                 if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "flash_forward"]
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(R.FLASH_S, 0.5)
        # short enough that it is a flash, not a freeze the gate would call held
        self.assertLess(R.FLASH_S, R.MAX_STILL_TAIL)


class TheWholeHookIsReadableAtOnce(unittest.TestCase):
    """It came up two words at a time: a sound-off viewer met "Your kid's"
    over frame one and waited three seconds to learn what the video was."""

    HOOK = ("Your kid's classmates already have phones: 31 percent of "
            "8-year-olds, nearly triple 2015.")

    def test_every_word_is_on_screen_in_every_hook_caption(self):
        import re
        from data_learning import studio_render as R
        for lit in ((0, 2), (6, 8), (12, 14)):
            txt = R.hook_karaoke(self.HOOK, lit, "&H4FD1F5&")
            shown = re.sub(r"\{[^}]*\}", "", txt).replace("\\N", " ").split()
            self.assertEqual(shown, self.HOOK.split())

    def test_it_fits_in_the_lines_it_is_allowed(self):
        from data_learning import studio_render as R
        long = " ".join(["unbelievable"] * 16)
        self.assertEqual(R.hook_layout(long)[1], [])     # never crammed
        self.assertIn("unbelievable unbelievable",
                      R.hook_karaoke(long, (0, 2), "&H4FD1F5&"))
        for h in (self.HOOK,):
            fs, lines = R.hook_layout(h)
            self.assertTrue(lines)
            self.assertLessEqual(len(lines), R.HOOK_LINES)
            self.assertGreaterEqual(fs, R.HOOK_FS[1])
            f = R._font(fs)
            for line in lines:
                self.assertLessEqual(f.getlength(" ".join(line)), R.HOOK_W + 1)

    def test_the_said_word_is_lit_and_the_rest_to_come_dimmed(self):
        from data_learning import studio_render as R
        txt = R.hook_karaoke(self.HOOK, (2, 4), "&H4FD1F5&")
        self.assertIn("&H4FD1F5&\\1a&H00&}classmates", txt)
        self.assertIn("\\1a&H70&}have", txt)
        self.assertIn("\\1a&H00&}Your", txt)

    def test_the_first_picture_does_not_fade_in_from_nothing(self):
        from data_learning import studio_render as R
        src = inspect.getsource(R.render)
        self.assertIn('("" if t0 < 0.05 else', src)


if __name__ == "__main__":
    unittest.main()
