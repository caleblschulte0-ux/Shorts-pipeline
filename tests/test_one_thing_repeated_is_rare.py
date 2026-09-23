"""A FIELD OF ONE THING REPEATED IS RARE — AT MOST ONE PER VIDEO.

Operator, 2026-09-22: "putting a lot of like one thing on the screen ... the
thermostats ... to simplify like a lot of something. I'm not a big fan of
that. That should be used very, very sparingly."

Held here: an isotype (`units_scene`, `rate_scene`, `pictograph`, or a scene
the brain authored with `unit_figures` / `dot_field`) is the last alternate
offered, never a second one in a beat, never offered once the video has had
one; the director no longer lets it repeat; the brain is told the rule; and
the render loop enforces the budget on whatever actually draws.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as SR, viz_director as VD  # noqa: E402


class _Ins:
    kind = "bars"
    topic = "urban heat"
    items = []


def _seq(machines, used=frozenset(), dur=60.0, fallback=()):
    with mock.patch.object(SR, "_machines_for", return_value=tuple(machines)), \
            mock.patch.object(SR, "_alt_candidates_for", return_value=tuple(fallback)), \
            mock.patch.object(SR, "_buildable", return_value=True), \
            mock.patch.object(SR, "MAX_SPANS", 6):
        return SR._depiction_sequence(_Ins(), set(used), dur)


class WhatCountsAsOneThingRepeated(unittest.TestCase):
    def test_kinds_and_authored_scenes(self):
        self.assertTrue(SR.is_repeated_icon("units_scene"))
        self.assertTrue(SR.is_repeated_icon("rate_scene"))
        self.assertTrue(SR.is_repeated_icon("pictograph"))
        self.assertTrue(SR.is_repeated_icon(
            "scene", {"elements": [{"type": "unit_figures"}]}))
        self.assertTrue(SR.is_repeated_icon(
            "scene", {"elements": [{"type": "caption"}, {"type": "dot_field"}]}))
        self.assertFalse(SR.is_repeated_icon(
            "scene", {"elements": [{"type": "balance"}]}))
        self.assertFalse(SR.is_repeated_icon("balance_scene"))


class ItIsTheLastAlternate(unittest.TestCase):
    def test_every_other_machine_comes_first(self):
        seq = _seq(["units_scene", "balance_scene", "hurdle_scene"],
                   fallback=["trend"])
        self.assertIn("balance_scene", seq)
        if "units_scene" in seq:
            self.assertEqual(seq[-1], "units_scene")

    def test_never_two_in_one_beat(self):
        seq = _seq(["units_scene", "rate_scene"], fallback=["pictograph", "trend"])
        self.assertLessEqual(sum(k in SR.REPEATED_ICON_KINDS for k in seq), 1)

    def test_none_once_the_video_has_had_one(self):
        seq = _seq(["units_scene", "balance_scene"], used={"__repeated_icon__"},
                   fallback=["rate_scene", "trend"])
        self.assertFalse(any(k in SR.REPEATED_ICON_KINDS for k in seq), seq)


class TheDirectorDoesNotRepeatIt(unittest.TestCase):
    def test_not_repeatable(self):
        for k in ("units_scene", "rate_scene"):
            self.assertFalse(VD.KINDS[k].get("repeatable"), k)


class TheBrainIsToldAndTheLoopEnforces(unittest.TestCase):
    def test_the_prompt_says_sparingly(self):
        src = (ROOT / "scripts" / "story_forge.py").read_text()
        self.assertIn("USE VERY SPARINGLY", src)

    def test_the_render_loop_spends_and_checks_the_budget(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        body = src[src.index("def render("):]
        body = body[:body.index("\ndef ", 10)]
        tree_src = body
        self.assertIn("is_repeated_icon(", tree_src)
        self.assertIn('_kinds_used.add("__repeated_icon__")', tree_src)
        self.assertIn('"__repeated_icon__" in _kinds_used', tree_src)
        self.assertEqual(SR.REPEATED_ICON_BUDGET, 1)


if __name__ == "__main__":
    unittest.main()
