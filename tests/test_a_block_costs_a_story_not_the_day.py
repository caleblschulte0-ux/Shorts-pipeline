"""A BLOCK COSTS A STORY. IT MUST NEVER COST THE DAY.

Operator, 2026-09-09: *"the gates can block stuff but then we try again — no,
never posting."*

They were describing a real bug, not a wish. `post_stories` counted its
per-run slate with `rendered`, and `rendered += 1` happened BEFORE the render
and before the showrunner ran. So a BLOCKED story consumed a slot exactly as
if it had posted.

That morning's explainer run:

    4 stories rendered, showrunner held all four
    budget (--max-per-run 4) exhausted
    all 79 remaining un-posted stories: "deferred to next run"
    videos posted: 0

Every gate was RIGHT — those videos genuinely freeze for two seconds. The
queue was full, the pipeline was working, the credentials were fine, and the
channel went dark for a day anyway, because the accounting counted attempts
as output.

So the slate is gated on `posted`, and a separate, wider `attempt_cap` bounds
the cost. The channel keeps reaching for the next story until it has the
slate the registry asked for or it has tried enough times to conclude
something is systematically wrong.

THIS IS NOT A WEAKENED GATE. Nothing here lets a blocked video through; a
held story stays held and is not posted. What changes is only whether the
NEXT story gets a turn.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = (Path(__file__).resolve().parent.parent
       / "scripts" / "post_stories.py").read_text()


class TheSlateCountsWhatPosted(unittest.TestCase):
    def test_the_budget_is_gated_on_posts_not_attempts(self):
        self.assertIn("if args.max_per_run and posted >= args.max_per_run:",
                      SRC)
        self.assertNotIn("rendered >= args.max_per_run", SRC,
                         "the slate is counting attempts again")

    def test_posted_only_increments_after_a_real_outcome(self):
        """It must sit after the upload, not before the render — that
        ordering IS the bug this file exists for."""
        up = SRC.index("_persist_posted_log_now(args.log, slug)\n"
                       "        posted += 1")
        gate = SRC.index("SHOWRUNNER gate")
        self.assertGreater(up, gate,
                           "posted is counted before the gate has spoken")

    def test_a_blocked_story_leaves_the_loop_before_it_can_count(self):
        """The real invariant, structurally: the block and hold paths end in
        `continue`, so they cannot reach any `posted += 1` no matter where it
        sits.

        A first version of this test scanned 600 characters before each
        increment and failed on the FROZEN path, which merely happens to be
        written next to the block path — a proximity check reading like a
        control-flow one. The code was right and the test was wrong; asserting
        the branch actually exits is the thing worth holding.
        """
        for marker in ('"error": "showrunner_block"',
                       '"error": "editorial_hold"'):
            i = SRC.index(marker)
            tail = SRC[i:i + 400]
            self.assertIn("continue", tail,
                          f"the {marker} path can fall through to a count")
            # ...and nothing increments between the marker and that exit.
            self.assertNotIn("posted += 1", tail[:tail.index("continue")])

    def test_attempts_are_still_bounded(self):
        """Unbounded retries would walk the whole catalogue on a day when
        something is systematically broken — which is a different way to
        waste a day, not a fix."""
        self.assertIn("attempts += 1", SRC)
        self.assertIn("if attempts >= attempt_cap:", SRC)
        self.assertIn("attempt_cap = max(", SRC)

    def test_the_cap_leaves_room_for_a_bad_patch_in_the_queue(self):
        """Four consecutive holds happened on the day this was found, so a
        cap of one-or-two tries per slot would have changed nothing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_ps", Path(__file__).resolve().parent.parent
            / "scripts" / "post_stories.py")
        # Read the expression rather than import the module (it has heavy
        # imports and a CLI); the arithmetic is what matters.
        m = re.search(r"attempt_cap = max\((\d+), \(args\.max_per_run or (\d+)\) \* (\d+)\)",
                      SRC)
        self.assertIsNotNone(m, "the attempt cap changed shape")
        floor, default, mult = (int(x) for x in m.groups())
        self.assertGreaterEqual(mult, 3, "fewer than 3 tries per slot")
        self.assertGreaterEqual(floor, 6)
        # the real slate is 4 -> at least 12 tries before the run gives up
        self.assertGreaterEqual(max(floor, 4 * mult), 12)


class NothingHereWeakensTheGate(unittest.TestCase):
    """The one thing this change must not do. `CLAUDE.md`: if a future task
    asks the channel to ship more, the answer is better videos, never a
    weaker gate."""

    def test_a_blocked_story_is_still_not_uploaded(self):
        self.assertIn("showrunner_block", SRC)
        self.assertNotIn("SHOWRUNNER=off", SRC.split("def main")[0])

    def test_the_editorial_hold_still_skips_the_story(self):
        self.assertIn('"error": "editorial_hold"', SRC)

    def test_the_per_day_cap_is_untouched(self):
        """The day cap was already posted-based and correct; only the
        per-RUN slate was miscounted."""
        self.assertIn("posted_today", SRC)


if __name__ == "__main__":
    unittest.main()
