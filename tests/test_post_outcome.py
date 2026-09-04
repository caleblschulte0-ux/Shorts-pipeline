"""A run's exit code must mean "something is broken" — and nothing else.

For days every explainer run was red. Not because the pipeline was broken, but
because `post_stories` returned `0 if ok == len(results) else 1`: one story
HELD BY THE REVIEW GATE turned a three-video day into a failure. A gate hold is
the fail-closed review doing its job.

The cost of that showed up on 2026-09-04. The 09:32 run was killed at 09:44 —
"the runner has received a shutdown signal", GitHub reclaiming the machine
mid-job — and the channel posted nothing that morning. On the Actions page it
looked exactly like the three runs before it, which had all shipped videos and
gone red over held stories. A real outage hid inside a wall of expected red.

So: exit code reports FAULTS. Whether the channel actually published today is a
different question, asked separately by the workflow's day-level check, because
a quiet day and a broken day need different reactions from a human.

Runs with pytest OR standalone:
    python3 tests/test_post_outcome.py
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
    "post_stories_mod", _REPO / "scripts" / "post_stories.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def _posted(slug="a"):
    return {"slug": slug, "ok": True, "url": f"https://youtube.com/shorts/{slug}"}


def _held(slug="b", why="showrunner_block"):
    return {"slug": slug, "ok": False, "error": why}


def _fault(slug="c", why="HttpError 500 backendError"):
    return {"slug": slug, "ok": False, "error": why}


class PostOutcome(unittest.TestCase):
    def _exit(self, results):
        return ps.exit_code_for(ps.classify_results(results))

    def test_a_good_day_with_one_gate_hold_is_green(self):
        """THE REGRESSION. Three uploaded, one held — this was red, and that
        red is what hid a real outage."""
        results = [_posted("a"), _posted("b"), _posted("c"), _held("d")]
        b = ps.classify_results(results)
        self.assertEqual(len(b["posted"]), 3)
        self.assertEqual(len(b["held"]), 1)
        self.assertEqual(b["faults"], [])
        self.assertEqual(self._exit(results), 0)

    def test_every_story_held_is_not_a_fault(self):
        """The gate refusing a whole slate is the system working. It is loud in
        the annotations and in the day-level check — it is not an exception."""
        results = [_held(s) for s in "abcd"]
        self.assertEqual(self._exit(results), 0)

    def test_an_upload_error_is_a_fault(self):
        self.assertEqual(self._exit([_fault()]), 1)

    def test_a_fault_beats_a_success(self):
        """Shipping two and crashing on the third still needs a human."""
        self.assertEqual(self._exit([_posted("a"), _posted("b"), _fault("c")]), 1)

    def test_editorial_hold_counts_as_held_not_fault(self):
        results = [_held("a", "editorial_hold")]
        self.assertEqual(ps.classify_results(results)["faults"], [])
        self.assertEqual(self._exit(results), 0)

    def test_doing_nothing_at_all_is_a_fault(self):
        """No upload, no hold, no render, no explanation. That is broken."""
        self.assertEqual(self._exit([]), 1)

    def test_a_dry_run_is_not_a_post(self):
        """`(dry-run)` and `(frozen)` are ok-but-not-published: they must not
        be counted as videos reaching the channel, or a frozen preview would
        report as a shipping day."""
        results = [{"slug": "a", "ok": True, "url": "(dry-run)"},
                   {"slug": "b", "ok": True, "url": "(frozen)"}]
        b = ps.classify_results(results)
        self.assertEqual(b["posted"], [])
        self.assertEqual(len(b["dry"]), 2)
        self.assertEqual(self._exit(results), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
