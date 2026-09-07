"""Four uploads a day of one template is what gets a channel penalised.

2026-09-06: "we're getting fucking nailed by YouTube right now."

Measured on what actually shipped — 234 uploads, 96 with recorded creative
facts:

    beat count    3 on EVERY video ever posted
    title         every one ending "(3 Charts)"
    ending_type   consequence 64, inversion 20, escalation 11, question 1
    hook_type     shock_stat  49, inversion 24, stake      12, question 11

None of that was a drift. It was written down: the forge hardcoded three
segments, and the Routine's own story template literally contained
`"title": "Hooky Title (3 Charts)"`. The pipeline was doing exactly as told.

These tests hold the shape open. They do not assert that any particular video
is varied — a single video cannot be — they assert that nothing in the code or
the doctrine forces every video to be the same.

Runs with pytest OR standalone:
    python3 tests/test_format_is_not_a_template.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    "story_forge", _REPO / "scripts" / "story_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)

_FORGE_SRC = (_REPO / "scripts" / "story_forge.py").read_text()
_DOCTRINE = (_REPO / "CLAUDE_ROUTINE_INSTRUCTIONS.md").read_text()
_BEATS = (2, 3, 3, 4)


def _target(theme: str, lead: str = "") -> int:
    """Mirrors the forge: keyed on the theme AND the leading indicator."""
    return _BEATS[forge._stable_hash(theme + lead) % 4]


class TheBeatCountVaries(unittest.TestCase):
    THEMES = ("health", "energy", "population", "climate", "education",
              "money", "transport", "water", "food", "tech", "nature", "work")

    def test_a_real_spread_of_themes_produces_more_than_one_length(self):
        got = {_target(t) for t in self.THEMES}
        self.assertGreater(len(got), 1, f"every theme still gets {got}")

    def test_two_stories_in_the_same_theme_can_differ(self):
        """Keying on the theme alone would give every health story ever made
        the identical length — a smaller template, still a template."""
        lengths = {_target("health", f"WB.IND.{i}") for i in range(12)}
        self.assertGreater(len(lengths), 1, f"same theme always {lengths}")

    def test_every_length_is_one_a_video_can_carry(self):
        for t in self.THEMES:
            self.assertIn(_target(t), (2, 3, 4))

    def test_it_is_stable_for_a_given_theme(self):
        """`hash()` is salted per process, so using it would give the same
        theme a different shape on every run — worse than a fixed template,
        because a story that re-forges would silently change length."""
        for t in self.THEMES:
            self.assertEqual(_target(t, "WB.X"), _target(t, "WB.X"))
        # `_stable_hash(theme)` contains the substring "hash(theme)", so the
        # check has to name the BUILTIN specifically.
        self.assertNotRegex(_FORGE_SRC, r"(?<![_a-z])hash\(theme\)")
        self.assertIn("_stable_hash(", _FORGE_SRC)

    def test_the_floor_is_two_not_three(self):
        """One measurement is a stat, not a story you can build to — but two
        is a real comparison and the forge used to bank it as unusable."""
        self.assertIn("if len(dss) < 2:", _FORGE_SRC)
        self.assertNotIn("if len(dss) < 3:", _FORGE_SRC)

    def test_nothing_still_collects_a_hardcoded_three(self):
        self.assertNotIn("len(dss) < 3", _FORGE_SRC)


class TheTitleIsNotAFillInTheBlank(unittest.TestCase):
    def test_the_story_template_does_not_ship_a_fixed_suffix(self):
        """The template literally read `"title": "Hooky Title (3 Charts)"`, so
        every title the Routine wrote ended the same way."""
        for line in _DOCTRINE.splitlines():
            if re.match(r'\s*"title":', line):
                self.assertNotIn("(3 Charts)", line, line.strip())
                self.assertNotIn("(Explained)", line, line.strip())

    def test_the_doctrine_says_titles_must_not_share_a_template(self):
        self.assertIn("TITLES MUST NOT SHARE A TEMPLATE", _DOCTRINE)

    def test_the_format_is_no_longer_named_after_a_beat_count(self):
        """Calling the format "X in 3 Charts" is itself the instruction that
        made every video three beats."""
        self.assertNotIn('"X in 3 Charts"', _DOCTRINE)


class TheShapeVariesToo(unittest.TestCase):
    def test_the_doctrine_names_the_measured_skew(self):
        """A rule with the evidence attached survives; a bare "vary it" gets
        re-litigated by the next writer."""
        self.assertIn("SO MUST THE SHAPE OF THE VIDEO", _DOCTRINE)
        for token in ("ending_type", "hook_type", "consequence", "shock_stat"):
            self.assertIn(token, _DOCTRINE)

    def test_it_points_at_the_report_that_can_check_it(self):
        self.assertIn("what_works.py", _DOCTRINE)


class ThePickerIsNotItselfATemplate(unittest.TestCase):
    """A ranked candidate list is a template too.

    Simulated over the 74 un-posted stories, the first version picked
    units_scene, then balance_scene, then fill_vessel — for EVERY ONE.
    A fixed ranking plus a per-story `used` set gives the same three in the
    same order every time, `orbit` was never chosen once, and every video would
    have opened its second beat on an isotype. Better than three charts, and
    still a fingerprint.
    """

    class _Pt:
        def __init__(self, label, value):
            self.label, self.value = label, value

    class _Ins:
        def __init__(self, kind, topic, items, unit=""):
            self.kind, self.topic, self.items, self.unit = kind, topic, items, unit
            self.main_insight = topic
            self.highlight_label = items[0].label if items else ""
            self.baseline = None

    def _story(self, topic):
        pts = [self._Pt(str(y), 10 + y % 7) for y in range(2018, 2027)]
        return self._Ins("bars", topic, pts, "count")

    TOPICS = ("home prices", "mortgage rates", "teen licensing", "sea level",
              "bird migration", "electricity use", "coffee output",
              "rail freight", "hospital beds", "wildfire area",
              "phone ownership", "school size", "bee colonies", "tunnel length",
              "shipping cost", "solar output", "river flow", "book sales")

    def test_the_first_alternate_is_not_the_same_kind_every_time(self):
        import matplotlib
        matplotlib.use("Agg")
        from data_learning import studio_render as sr
        import collections
        firsts = collections.Counter()
        for t in self.TOPICS:
            seq = sr._depiction_sequence(self._story(t), set(), 12.0)
            if len(seq) > 1:
                firsts[seq[1]] += 1
        total = sum(firsts.values())
        self.assertGreater(total, 0, "no alternates offered at all")
        self.assertGreater(len(firsts), 2,
                           f"the picker collapsed to {dict(firsts)}")
        top = firsts.most_common(1)[0][1]
        self.assertLess(top / total, 0.75,
                        f"one form dominates the opening: {dict(firsts)}")

    def test_the_rotation_is_deterministic(self):
        """A re-render must produce the identical video. Varied is not the same
        as random — random would mean the same story rendering differently on
        a retry, which breaks every comparison the repair loop makes."""
        import matplotlib
        matplotlib.use("Agg")
        from data_learning import studio_render as sr
        for t in self.TOPICS[:6]:
            a = sr._depiction_sequence(self._story(t), set(), 12.0)
            b = sr._depiction_sequence(self._story(t), set(), 12.0)
            self.assertEqual(a, b, t)


class TheRendererCanActuallyDoIt(unittest.TestCase):
    """A doctrine that asks for two- and four-beat videos is a lie if the
    renderer only handles three. Both shapes were rendered end to end and
    passed the cadence gate; these pin the assumptions that would break it."""

    def test_nothing_in_the_renderer_assumes_three_segments(self):
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        self.assertNotIn("st.segments[:3]", src)
        self.assertNotIn("len(st.segments) == 3", src)

    def test_the_still_tail_fits_inside_the_frozen_stretch_ceiling(self):
        """THE ARITHMETIC THAT BIT. The gate allows 45 duplicate frames and
        samples at 24fps, so the budget is 1.875s — and it was set to 2.2,
        which is 53 frames: over the ceiling by construction whenever nothing
        else in the frame happens to be moving. The three-beat video got away
        with it; a two-beat and a four-beat one both failed on a closing tail.
        """
        import matplotlib
        matplotlib.use("Agg")
        from data_learning import studio_render as sr
        self.assertLess(sr.MAX_STILL_TAIL * 24, 45,
                        "the tail budget exceeds the gate's own ceiling")
        for span in (4.0, 5.8, 7.9, 12.0, 20.0, 30.0):
            for tail in (sr.MAX_STILL_TAIL, sr.CLOSING_STILL_TAIL):
                held = (1.0 - sr._full_by(span, tail)) * span
                self.assertLess(held * 24, 45,
                                f"{span}s span -> {held * 24:.0f} frames")

    def test_the_closing_gets_a_tighter_budget_than_mid_video(self):
        """The tail budget is really "how long may THIS layer hold while the
        rest of the frame carries it". Mid-video the host performs and the
        captions turn over; the closing lands its last reveal at 62% and after
        that only the recap moves."""
        import matplotlib
        matplotlib.use("Agg")
        from data_learning import studio_render as sr
        self.assertLess(sr.CLOSING_STILL_TAIL, sr.MAX_STILL_TAIL)
        for span in (5.8, 7.9, 13.0):
            mid = (1.0 - sr._full_by(span)) * span
            close = (1.0 - sr._full_by(span, sr.CLOSING_STILL_TAIL)) * span
            self.assertLess(close, mid, f"{span}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
