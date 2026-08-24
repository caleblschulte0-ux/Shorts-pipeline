"""Every provider search() starts must reach a recorded terminal state.

Doctor finding e02d4cf673bd: search() abandons slow providers when the
latency window expires (shutdown(wait=False, cancel_futures=True)), but the
abandoned ones used to leave NO record at all — their threads lived on and
could still mutate the shared quota state after the run, with nothing tying
that write back to the search that had already returned. The fix is a
per-provider outcome ledger (completed / failed / timed_out / cancelled),
published as `media_funnel.LAST_SEARCH_OUTCOMES` and logged before the
result is finalized. These tests prove the ledger is total: started
providers never vanish from it, whichever way they ended.

Fully offline: `_PROVIDERS` is swapped for synthetic functions and the
latency window is shrunk so the timeout path runs in milliseconds.

    python -m unittest tests.test_media_funnel_outcomes -v
"""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funnel import media_funnel as mf   # noqa: E402


class TestProviderOutcomeLedger(unittest.TestCase):
    def setUp(self):
        self._providers = mf._PROVIDERS
        self._window = mf.SEARCH_WINDOW_S
        # Let stragglers finish before the interpreter exits — the executor
        # threads are non-daemon, so a long sleep would stall the test run
        # exactly the way a slow provider used to stall the orchestrator.
        self._release = threading.Event()

    def tearDown(self):
        self._release.set()
        mf._PROVIDERS = self._providers
        mf.SEARCH_WINDOW_S = self._window

    def _search(self):
        # story_slug="" bypasses the disk cache; no provider touches the
        # network, so the whole pipeline below the fan-out runs on [].
        return mf.search("angle", ["Some Entity"], story_slug="",
                         verbose=False)

    def test_ledger_is_total_over_fast_failed_and_slow(self):
        release = self._release

        def fast(entity, angle):
            return []

        def broken(entity, angle):
            raise RuntimeError("simulated provider crash")

        def slow(entity, angle):
            # Still running when the window closes — the exact shape that
            # used to vanish without a terminal record.
            release.wait(timeout=10)
            return []

        mf._PROVIDERS = [("fast", fast), ("broken", broken), ("slow", slow)]
        mf.SEARCH_WINDOW_S = 0.3

        t0 = time.monotonic()
        self._search()
        elapsed = time.monotonic() - t0

        led = mf.LAST_SEARCH_OUTCOMES
        # TOTALITY: every started provider has a verdict...
        self.assertEqual(set(led), {"fast", "broken", "slow"})
        # ...and the verdicts are the honest ones.
        self.assertEqual(led["fast"], "completed")
        self.assertEqual(led["broken"], "failed")
        self.assertEqual(led["slow"], "timed_out")
        # The latency limit itself survived the fix: the run returned at
        # the window, it did not wait out the straggler.
        self.assertLess(elapsed, 5.0)

    def test_all_completed_when_everyone_is_fast(self):
        mf._PROVIDERS = [("a", lambda e, s: []), ("b", lambda e, s: [])]
        mf.SEARCH_WINDOW_S = 5.0
        self._search()
        self.assertEqual(mf.LAST_SEARCH_OUTCOMES,
                         {"a": "completed", "b": "completed"})


if __name__ == "__main__":
    unittest.main()
