"""Two videos that are the same video must not both go up.

2026-09-06, operator: "you keep putting the same videos ... we're getting
fucking nailed by YouTube right now."

The posted log deduped on SLUG and nothing else, so two rows of the config that
were the same VIDEO to a viewer both shipped. Auditing the real 234-upload log
found 25 such pairs, including straight repeats:

    2026-06-28  Human Brain Capacity            (twice, the same day)
    2026-06-28 / 2026-07-07  Space Debris Removal
    2026-07-01 / 2026-07-10  Space Exploration Milestones
    2026-08-21  World Hydropower Fell Below Its 1990 Level
    2026-08-25  World Coal Power Fell Below Its 1990 Level

That last pair is the shape the current story forge produces: one template with
one noun swapped. YouTube's repetitious-content policy is aimed squarely at it.

Runs with pytest OR standalone:
    python3 tests/test_no_duplicate_uploads.py
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    "post_stories", _REPO / "scripts" / "post_stories.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


class ItCatchesTheRealRepeats(unittest.TestCase):
    """Every case here is a pair that actually shipped."""

    CASES = (
        ("World Coal Power Fell Below Its 1990 Level",
         "World Hydropower Fell Below Its 1990 Level"),
        ("Human Memory Capacity", "Human Brain Capacity"),
        ("Caffeine Content Revealed", "Sugar Content Revealed"),
        ("Space Exploration Milestones", "Space Exploration Milestones"),
        ("Moons In Our Solar System", "Moon Counts in Our Solar System"),
        ("Longest Living Trees", "Longest Living Organisms"),
    )

    def test_each_one_is_refused(self):
        for later, earlier in self.CASES:
            self.assertEqual(ps.duplicate_of(later, [earlier]), earlier,
                             f"{later!r} would have shipped after {earlier!r}")

    def test_it_names_the_video_it_collided_with(self):
        """A refusal that says WHICH one is actionable; "too similar" sends
        somebody reading the whole log."""
        got = ps.duplicate_of("Human Memory Capacity", ["x", "Human Brain Capacity"])
        self.assertEqual(got, "Human Brain Capacity")


class ItLetsRealStoriesThrough(unittest.TestCase):
    POSTED = ["World Hydropower Fell Below Its 1990 Level",
              "Human Brain Capacity", "Sugar Content Revealed",
              "Why Empty Offices Will Never Fill Back Up (3 Charts)"]

    def test_genuinely_different_stories_ship(self):
        for title in ("The Lake That Basically Disappeared",
                      "Why 1 In 3 US Babies Are Born By Surgery (3 Charts)",
                      "Organ Transplants Hit A Record",
                      "Why Teens Aren't Getting Their License Anymore"):
            self.assertIsNone(ps.duplicate_of(title, self.POSTED), title)

    def test_an_empty_or_missing_title_is_not_a_duplicate(self):
        self.assertIsNone(ps.duplicate_of("", self.POSTED))
        self.assertIsNone(ps.duplicate_of(None, self.POSTED))
        self.assertIsNone(ps.duplicate_of("A Real Title", [None, ""]))

    def test_the_first_upload_ever_is_not_a_duplicate(self):
        self.assertIsNone(ps.duplicate_of("Anything At All", []))


class ARepeatIsAHoldNotAFault(unittest.TestCase):
    def test_it_does_not_turn_the_run_red(self):
        """The story is fine and stays in the queue — its PACKAGING repeats, so
        a retitle ships it. A run that goes red for one is the misleading
        exit-code defect all over again."""
        self.assertIn("duplicate_hold", ps.HELD_REASONS)
        buckets = ps.classify_results([
            {"slug": "a", "ok": True, "url": "https://youtu.be/x"},
            {"slug": "b", "ok": False, "error": "duplicate_hold"},
        ])
        self.assertEqual(len(buckets["held"]), 1)
        self.assertEqual(buckets["faults"], [])
        self.assertEqual(ps.exit_code_for(buckets), 0)

    def test_a_day_of_nothing_but_duplicates_is_still_not_a_fault(self):
        buckets = ps.classify_results(
            [{"slug": s, "ok": False, "error": "duplicate_hold"}
             for s in ("a", "b", "c")])
        self.assertEqual(ps.exit_code_for(buckets), 0)


class ItIsCheckedBeforeAnythingIsSpent(unittest.TestCase):
    def test_the_guard_runs_before_the_render(self):
        """It costs nothing, it cannot become un-true later in the run, and a
        repeat is the one refusal that protects the CHANNEL rather than the
        video — so it goes first."""
        src = (_REPO / "scripts" / "post_stories.py").read_text()
        dup = src.index("NEAR-DUPLICATE OF SOMETHING ALREADY UP")
        budget = src.index("Check the run's render budget FIRST")
        gate = src.index("PRE-RENDER editorial gate")
        self.assertLess(dup, budget)
        self.assertLess(dup, gate)

    def test_force_still_overrides_it(self):
        """An operator deliberately re-shipping a fixed video is not a
        scheduling bug."""
        src = (_REPO / "scripts" / "post_stories.py").read_text()
        blk = src[src.index("NEAR-DUPLICATE OF SOMETHING ALREADY UP"):]
        self.assertIn("if not args.force:", blk[:400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
