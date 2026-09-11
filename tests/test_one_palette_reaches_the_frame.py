"""`shared/look.py` decides the colour, and nothing downstream overrules it.

Rendered end-to-end on 2026-09-10, the ozone story came out in teal and
green with a gold design system sitting unused one import away. Four
separate places were deciding colour, and `look` was the one with the least
say:

    studio_render.THEMES     six hardcoded triples, picked by MD5 of the slug,
                             assigned straight onto charts.HIGHLIGHT/ACCENT/WARN
                             six lines into every render
    studio_render CLEAN bg   an 8px full-opacity accent bar across the top of
                             every frame and a 5px accent divider, both reading
                             a theme key
    story.py                 GREEN/RED/ORANGE = "#50ff80"/"#ff3030"/"#ffaa30",
                             painting the SPOKEN NUMBER — the loudest text in
                             the video — in pure web-safe RGB
    charts.WARN              an amber sitting under the separation floor from
                             the gold accent, which is the default on 82 of
                             the channel's 309 stories

Each of these is held closed here, because each one was invisible from
inside the module that owned it.
"""
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import charts as C                        # noqa: E402
from data_learning import story as ST                        # noqa: E402
from data_learning import studio_render as SR                # noqa: E402
from shared import look, palette as pal                      # noqa: E402


def _H(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(c) for c in rgb)


def _code(fn) -> str:
    tree = ast.parse(inspect.getsource(fn).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


class TheThemeDoesNotDecideAColour(unittest.TestCase):
    def test_no_theme_carries_a_colour_key(self):
        for i, t in enumerate(SR.THEMES):
            for k in ("highlight", "accent", "warn"):
                self.assertNotIn(k, t, f"THEMES[{i}] still carries {k!r}")

    def test_the_theme_still_carries_the_variety_that_is_not_colour(self):
        """Per-video variety was the right instinct; only its palette was
        wrong. The voice, the music bed and the bokeh seed still vary."""
        for t in SR.THEMES:
            for k in ("voice", "vibe", "seed"):
                self.assertIn(k, t)

    def test_the_accent_comes_from_the_design_system(self):
        code = _code(SR.render)
        self.assertIn("_look.accent_for(slug)", code)
        self.assertNotIn("theme['highlight']", code)

    def test_the_alarm_is_not_themed_at_all(self):
        """A baseline warning that is teal on one video and amber on the
        next says nothing by being either."""
        code = _code(SR.render)
        self.assertNotIn("charts.WARN =", code.replace(" ", ""))

    def test_a_story_gets_one_accent_and_the_channel_gets_four(self):
        for slug in ("ozone-hole-recovery", "sand-mining-crisis"):
            a = look.accent_for(slug)
            self.assertEqual(a, look.accent_for(slug), "not deterministic")
            self.assertIn(a, look.ACCENTS)


class TheChromeIsInkNotColour(unittest.TestCase):
    """Two saturated full-width rules on every frame, spending the channel's
    ONE colour on chrome — the exact opposite of "colour means one thing
    here: the thing being said"."""

    def _bg_filter(self) -> str:
        return _code(SR.render)

    def test_the_top_accent_bar_is_gone(self):
        src = _code(SR.render)
        self.assertNotIn("y=0:w={W}:h=8", src.replace(" ", ""))

    def test_the_divider_is_a_grid_hairline(self):
        src = _code(SR.render)
        self.assertIn("charts.GRID", src)

    def test_nothing_reads_the_dead_theme_key(self):
        src = _code(SR.render)
        self.assertNotIn("theme.get('accent')", src)

    def test_the_caption_panel_survives(self):
        """It has a real job — the band below the chart was bare gradient
        and the gate called it a 'dead navy strip'."""
        self.assertIn("FOOT_Y", _code(SR.render))


class TheSpokenNumberWearsTheChannelsColours(unittest.TestCase):
    def test_the_neon_constants_are_gone(self):
        src = (ROOT / "data_learning" / "story.py").read_text()
        tree = ast.parse(src)
        lits = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for dead in ("#50ff80", "#ff3030", "#ffaa30",
                     "#0d2818", "#220404", "#2a1d05"):
            self.assertNotIn(dead, lits, f"{dead} still hardcoded")

    def test_the_lead_number_is_the_storys_accent(self):
        C.HIGHLIGHT = "#FFD37A"
        self.assertEqual(ST.LEAD(), "#FFD37A")
        C.HIGHLIGHT = "#4FD1C5"
        self.assertEqual(ST.LEAD(), "#4FD1C5",
                         "LEAD is frozen — it must follow the story")

    def test_the_neutral_and_the_alarm_do_NOT_follow_the_story(self):
        """A neutral that drifted per video would not be a neutral."""
        before = (ST.SECOND(), ST.ALARM(), ST.PLAIN())
        C.HIGHLIGHT = "#F472B6"
        self.assertEqual((ST.SECOND(), ST.ALARM(), ST.PLAIN()), before)

    def test_the_flash_plate_is_derived_from_the_number(self):
        plate = ST._flash_bg("#FFD37A")
        self.assertIsNotNone(plate)
        self.assertLess(pal.contrast(plate, pal.CARD), 1.6,
                        "the plate is a glow off the ground, not a colour")

    def test_plain_ink_gets_no_plate(self):
        for c in (C.TEXT, C.SUBTLE, "", None):
            self.assertIsNone(ST._flash_bg(c))

    def test_a_bad_colour_does_not_take_the_render_down(self):
        self.assertIsNone(ST._flash_bg("not-a-colour"))


class TheAlarmSeparatesFromEveryAccent(unittest.TestCase):
    def test_it_clears_the_floors(self):
        warn = _H(look.WARN)
        for name in sorted(look.ACCENTS):
            a = _H(look.accent(name)[0])
            self.assertGreaterEqual(pal.delta_e(a, warn), pal.NORMAL_FLOOR,
                                    f"{name} vs WARN")
            self.assertGreaterEqual(pal.delta_e(a, warn, "deuteranopia"),
                                    pal.CVD_FLOOR, f"{name} vs WARN (cvd)")

    def test_the_amber_it_replaced_would_still_fail(self):
        self.assertLess(pal.delta_e(_H(look.accent("gold")[0]), "#F59E0B"),
                        pal.NORMAL_FLOOR)

    def test_charts_takes_it_from_look(self):
        self.assertEqual(C.WARN, _H(look.WARN))


if __name__ == "__main__":
    unittest.main()
