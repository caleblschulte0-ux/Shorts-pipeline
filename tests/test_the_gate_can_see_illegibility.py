"""THE GATE COULD NOT SEE WHETHER A FRAME WAS READABLE.

Operator, 2026-09-09: *"this isn't about fixing this video. This is never
about a singular video. It is about the system that allows this video to
happen."*

They had just watched a video the showrunner PASSED, and read back what was
on screen:

    8s   "90 (pre-vaccine)"       the leading "19" outside the frame
    28s  "Not yet vaccinated  9"  the percent sign outside the frame
    20s  two labels printed on top of one another
    36s  the mascot standing on the title, covering "vaccinated"

**The judge was right to pass it.** Its five hard checks — junk_imagery,
decorative_mascot, bare_number_card, dead_air, empty_void — are every one
about CONTENT and MOTION. Not one asks whether the frame can be READ, so
there was no box to tick for a label cut off at the edge.

Five machines were patched that evening for the same class of defect. That
is not the fix. The fix is that the standing quality authority now has a
concept of legibility, so the NEXT renderer to reintroduce it is caught by
the gate rather than by somebody watching a video that already shipped.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "showrunner_review", ROOT / "scripts" / "showrunner_review.py")
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


class TheAuthorityAsksAboutLegibility(unittest.TestCase):
    def test_unreadable_is_a_hard_check(self):
        self.assertIn("unreadable", sr.AUTOFAIL_CHECKS)

    def test_a_present_unreadable_blocks(self):
        self.assertIn("unreadable", sr.failed_autofails(
            {"unreadable": {"present": True, "evidence": "label cut off"}}))

    def test_a_clean_frame_does_not_block(self):
        self.assertEqual(sr.failed_autofails(
            {"unreadable": {"present": False, "evidence": ""}}), [])

    def test_the_judge_is_ASKED_about_it(self):
        """A check in the list that the prompt never mentions is a check the
        model answers by guessing."""
        p = sr._GRADE_PROMPT
        self.assertIn("unreadable", p)
        for cue in ("cut off by", "on top of other text", "low-contrast"):
            self.assertIn(cue, p, f"the rubric does not describe {cue!r}")

    def test_the_returned_schema_has_a_slot_for_it(self):
        """`failed_autofails` reads `checks[name]["present"]`. Without a slot
        in the JSON the model returns, the check is silently absent — which
        reads exactly like "not present"."""
        p = sr._GRADE_PROMPT
        schema = p[p.index('"checks"'):p.index('"weakest_scene"')]
        self.assertIn("unreadable", schema)

    def test_every_hard_check_appears_in_both_the_rubric_and_the_schema(self):
        """The general form of the bug above: a check can be listed, asked
        for, or returned, and any one of the three being missing makes it
        silently inert."""
        p = sr._GRADE_PROMPT
        schema = p[p.index('"checks"'):p.index('"weakest_scene"')]
        missing = {c: [] for c in sr.AUTOFAIL_CHECKS}
        for c in sr.AUTOFAIL_CHECKS:
            if c not in p:
                missing[c].append("rubric")
            if c not in schema:
                missing[c].append("schema")
        bad = {k: v for k, v in missing.items() if v}
        self.assertEqual(bad, {}, f"checks that cannot fire: {bad}")


class ItDoesNotStOPTheChannelOnDayOne(unittest.TestCase):
    """Strengthening a gate is always allowed; stopping the channel with it
    the day it lands is a different decision, and not one to make silently
    while the operator is watching for videos."""

    def test_it_is_not_fatal_so_rebuild_still_posts(self):
        self.assertNotIn("unreadable", sr.FATAL_CHECKS)

    def test_junk_imagery_is_still_the_only_fatal_one(self):
        self.assertEqual(tuple(sr.FATAL_CHECKS), ("junk_imagery",))


class TheGateWasNotWEAKENED(unittest.TestCase):
    """`CLAUDE.md`: if a future task asks the channel to ship more, the
    answer is better videos, never a weaker gate. This adds a check; it must
    remove none."""

    def test_every_original_check_survives(self):
        for c in ("junk_imagery", "decorative_mascot", "bare_number_card",
                  "dead_air", "empty_void"):
            self.assertIn(c, sr.AUTOFAIL_CHECKS)

    def test_any_present_autofail_still_blocks_under_standard(self):
        for c in sr.AUTOFAIL_CHECKS:
            self.assertIn(c, sr.failed_autofails(
                {c: {"present": True, "evidence": "x"}}), c)


if __name__ == "__main__":
    unittest.main()
