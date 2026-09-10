"""THE WHOLE LOOK OF THE THING IS CHEAP.

The operator, 2026-09-10, after watching three shipped videos. The diagnosis
turned out not to be taste — it is the house data-viz anti-pattern list,
almost word for word:

    "Thick saturated blocks, heavy gridlines, no breathing room. Reads loud,
     even CHILDISH, at scale."

The data channel drew **165-point** fully saturated capsules on a flat navy
gradient in **DejaVu Sans Bold** — matplotlib's default face, and the single
loudest signal that a frame was made by a script — with the value printed on
every bar **in the series colour**. Every one of those is on the list.

## The look was already chosen. The channel just never adopted it.

`data_learning/flat2d.py` says so in its own docstring: *"the Vox /
Kurzgesagt register: deep gradient ground, restrained palette, one idea per
frame, big confident type, generous negative space, smooth motion. **This is
the look the operator picked on pixels (sample v2).**"* It has carried the
curiosity channel since, and `repair_planner` has had a defect code called
`CHEAP_TYPOGRAPHY` pointing at it the whole time.

So `shared/look.py` is not a new invention: its ground, its restraint, its
spaced kicker and its continuous push are flat2d's, made aspect-agnostic
(flat2d is 1920x1080; the shorts are 1080x1920) and joined to the mark specs
from the data-viz standard. One module, so the two channels cannot drift
apart again — which is exactly how they drifted in the first place.

Runs standalone:  python3 tests/test_the_channel_has_a_look.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from shared import look  # noqa: E402


class TheChannelOwnsItsType(unittest.TestCase):
    """A render that falls back to DejaVu is a render that does not look like
    the channel — and if it falls back only in CI, every visual test is
    measuring a frame that never ships. This session has already fixed that
    exact divergence twice (cairosvg, and ten mascot-less machines), so the
    font is COMMITTED, not fetched."""

    def test_every_weight_is_present(self):
        self.assertTrue(look.fonts_are_real(),
                        f"missing type in {look.FONT_DIR}")

    def test_the_faces_are_committed_not_fetched(self):
        import subprocess
        for p in sorted(look.FONT_DIR.glob("Inter*.ttf")):
            r = subprocess.run(["git", "ls-files", "--error-unmatch",
                                str(p.relative_to(_REPO))],
                               cwd=_REPO, capture_output=True)
            self.assertEqual(r.returncode, 0, f"{p.name} is not committed")

    def test_each_face_is_under_the_repos_size_rule(self):
        """CLAUDE.md: never commit files >256KB. Subsetting Inter to Latin
        takes a weight from 410KB to 38KB, which is what makes committing it
        possible at all."""
        for p in sorted(look.FONT_DIR.glob("Inter*.ttf")):
            self.assertLess(p.stat().st_size, 256 * 1024, p.name)

    def test_the_licence_ships_with_the_font(self):
        self.assertTrue((look.FONT_DIR / "Inter-OFL.txt").exists(),
                        "Inter is OFL — the licence has to travel with it")

    def test_font_returns_a_real_face_not_the_fallback(self):
        f = look.font(48, "bold")
        self.assertIn("Inter", str(getattr(f, "path", "")) or f.getname()[0])

    def test_an_unknown_weight_still_returns_something_drawable(self):
        self.assertIsNotNone(look.font(30, "no-such-weight"))


class MarksAreTHIN(unittest.TestCase):
    def test_a_bar_is_capped_absolutely(self):
        """No band, however tall, may fatten the mark past the frame cap."""
        self.assertLessEqual(look.bar_thickness(1080, 10_000),
                             1080 * look.BAR_CAP_FRAC + 1)

    def test_a_bar_is_also_capped_by_its_own_band(self):
        """...and a short band keeps air even when the frame cap allows more."""
        self.assertLessEqual(look.bar_thickness(1080, 40), 40 * 0.5)

    def test_the_shipped_thickness_is_a_fraction_of_what_it_was(self):
        """The Moon video drew 109pt bars on a three-row chart."""
        from data_learning import charts
        self.assertLess(charts._bar_lw(3), 30.0)
        self.assertGreater(charts._bar_lw(3), 8.0)

    def test_the_cap_holds_at_every_row_count(self):
        from data_learning import charts
        for n in range(1, 12):
            self.assertLessEqual(charts._bar_lw(n), 30.0, n)


class TextWearsINKNeverTheSeriesColour(unittest.TestCase):
    """The one channel that carries identity is the coloured MARK. Colouring
    the text burns it, and a light hue is illegible as type on the ground."""

    def test_the_chart_tokens_come_from_the_design_system(self):
        from data_learning import charts
        self.assertEqual(charts.TEXT, charts._hex(look.INK))
        self.assertEqual(charts.SUBTLE, charts._hex(look.INK_2))

    def test_ink_is_never_one_of_the_accents(self):
        hues = {c for pair in look.ACCENTS.values() for c in pair}
        for name, ink in (("INK", look.INK), ("INK_2", look.INK_2),
                          ("INK_3", look.INK_3)):
            self.assertNotIn(ink, hues, name)

    def test_a_row_label_is_no_longer_tinted_the_accent(self):
        import inspect
        from data_learning import charts
        src = inspect.getsource(charts._story_bars)
        self.assertIn("lbl.set_color(TEXT)", src)
        self.assertNotIn("lbl.set_color(HIGHLIGHT)", src)


class TheGroundIsALIVE(unittest.TestCase):
    """A static plate reads as a frozen hold — to the cadence gate and to a
    viewer alike. flat2d learned this and wrote it down; every `temporal_gate`
    block on the data channel is the same finding from the other end."""

    def test_the_ground_renders_at_both_aspects(self):
        for w, h in ((1080, 1920), (1920, 1080)):
            im = look.ground(w, h)
            self.assertEqual(im.size, (w, h))

    def test_the_ground_is_not_a_flat_fill(self):
        import numpy as np
        a = np.asarray(look.ground(540, 960).convert("L"), dtype="float32")
        self.assertGreater(float(a.std()), 3.0, "the ground is flat")

    def test_the_push_changes_every_frame(self):
        import numpy as np
        base = look.ground(360, 640)
        seen = set()
        for i in range(6):
            a = np.asarray(look.push(base, i, 6).convert("L"), dtype="uint8")
            seen.add(a.tobytes())
        self.assertEqual(len(seen), 6, "the push repeats a frame")


class OneAccentPerStory(unittest.TestCase):
    def test_the_accent_is_deterministic(self):
        a = look.accent_for("nobody-has-walked-on-the-moon")
        for _ in range(4):
            self.assertEqual(look.accent_for("nobody-has-walked-on-the-moon"), a)

    def test_different_stories_get_different_accents(self):
        got = {look.accent_for(s) for s in
               ("moon", "buybacks", "cargo", "eagles", "vaccines", "mail")}
        self.assertGreater(len(got), 1, "every story gets the same accent")

    def test_every_accent_names_a_bright_and_a_dim(self):
        for name, pair in look.ACCENTS.items():
            self.assertEqual(len(pair), 2, name)
            self.assertGreater(sum(pair[0]), sum(pair[1]),
                               f"{name}: the bright one is not brighter")


class TheFITTERLivesWithTheType(unittest.TestCase):
    def test_it_shrinks_before_it_ellipsises(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        f, out = look.fit(d, "1966 (Apollo buildup)", 60, 700)
        self.assertEqual(out, "1966 (Apollo buildup)")
        self.assertLessEqual(d.textlength(out, font=f), 700)

    def test_it_gives_up_rather_than_draw_unreadably_small(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        _f, out = look.fit(d, "x" * 300, 60, 200)
        self.assertTrue(out.endswith("…"))


if __name__ == "__main__":
    unittest.main()
