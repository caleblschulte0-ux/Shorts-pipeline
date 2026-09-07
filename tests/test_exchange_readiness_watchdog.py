"""Tests for the Phase A readiness watchdog (doctor finding 5187e34e11f3).

Fully offline: a FakeSession stands in for `requests.Session`, and the clock
+ sleep function are injected so a "timeout" branch runs in microseconds
instead of the real 30-minute budget.

    python -m unittest tests.test_exchange_readiness_watchdog -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import exchange_bundle as xb                      # noqa: E402
from scripts import exchange_readiness_watchdog as watchdog   # noqa: E402

DATE = "20260830"
REPO = "caleblschulte0-ux/Shorts-pipeline"
TOKEN = "fake-token"


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", on_return=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self._on_return = on_return

    def json(self):
        if self._on_return:
            self._on_return()
        return self._json


class FakeSession:
    """Pops canned responses off ordered queues; call order encodes the
    scenario each test wants (list-runs, then get-run, repeated)."""

    def __init__(self, post_response=None, get_queue=None):
        self.post_response = post_response
        self.get_queue = list(get_queue or [])
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("post", url, json))
        return self.post_response

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("get", url))
        if not self.get_queue:
            raise AssertionError(f"no more fake GET responses queued for {url}")
        return self.get_queue.pop(0)


def runs_list_response(run: dict | None):
    payload = {"workflow_runs": [run]} if run else {"workflow_runs": []}
    return FakeResponse(200, payload)


class WatchdogTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_root = xb.BUNDLE_ROOT
        self._tmp = tempfile.TemporaryDirectory()
        xb.BUNDLE_ROOT = Path(self._tmp.name)

    def tearDown(self):
        xb.BUNDLE_ROOT = self._orig_root
        self._tmp.cleanup()

    def _fake_clock(self, step=15.0):
        state = {"t": 0.0}

        def clock():
            state["t"] += step
            return state["t"]
        return clock


class TestBundleReady(WatchdogTestCase):
    def test_absent_bundle_is_not_ready(self):
        self.assertFalse(watchdog.bundle_ready(DATE))

    def test_written_bundle_is_ready(self):
        xb.write_bundle(DATE, [], [])
        self.assertTrue(watchdog.bundle_ready(DATE))


class TestAlreadyReadyShortCircuits(WatchdogTestCase):
    def test_no_network_call_when_bundle_exists(self):
        xb.write_bundle(DATE, [], [])
        session = FakeSession()  # raises if .post/.get is ever called
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            sleep_fn=lambda s: None, clock=self._fake_clock())
        self.assertEqual(outcome["status"], "already_ready")
        self.assertEqual(session.calls, [])


class TestDispatchFailure(WatchdogTestCase):
    def test_non_204_dispatch_is_a_named_failure(self):
        session = FakeSession(post_response=FakeResponse(403, text="forbidden"))
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            sleep_fn=lambda s: None, clock=self._fake_clock())
        self.assertEqual(outcome["status"], "dispatch_failed")
        self.assertIn("403", outcome["detail"])


class TestRunNeverFound(WatchdogTestCase):
    def test_timeout_before_a_run_ever_appears(self):
        session = FakeSession(
            post_response=FakeResponse(204),
            get_queue=[runs_list_response(None), runs_list_response(None)],
        )
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            timeout_s=30, poll_interval_s=15,
            sleep_fn=lambda s: None, clock=self._fake_clock(step=15.0))
        self.assertEqual(outcome["status"], "run_not_found")


class TestRunTimesOut(WatchdogTestCase):
    def test_run_found_but_never_completes(self):
        run_stub = {"id": 42, "html_url": "https://x/runs/42",
                    "status": "queued", "conclusion": None,
                    "created_at": "2030-01-01T00:00:00Z"}
        in_progress = {"id": 42, "html_url": "https://x/runs/42",
                       "status": "in_progress", "conclusion": None}
        session = FakeSession(
            post_response=FakeResponse(204),
            get_queue=[
                runs_list_response(run_stub),   # found on first look
                FakeResponse(200, in_progress),  # still running
                FakeResponse(200, in_progress),  # still running
            ],
        )
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            timeout_s=40, poll_interval_s=15,
            sleep_fn=lambda s: None, clock=self._fake_clock(step=15.0))
        self.assertEqual(outcome["status"], "timeout")
        self.assertEqual(outcome["run_id"], 42)


class TestRunFailedConclusion(WatchdogTestCase):
    def test_completed_but_not_successful_is_a_named_failure(self):
        run_stub = {"id": 7, "html_url": "https://x/runs/7",
                    "status": "queued", "conclusion": None,
                    "created_at": "2030-01-01T00:00:00Z"}
        failed = {"id": 7, "html_url": "https://x/runs/7",
                  "status": "completed", "conclusion": "failure"}
        session = FakeSession(
            post_response=FakeResponse(204),
            get_queue=[runs_list_response(run_stub), FakeResponse(200, failed)],
        )
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            sleep_fn=lambda s: None, clock=self._fake_clock())
        self.assertEqual(outcome["status"], "run_failed")
        self.assertEqual(outcome["conclusion"], "failure")


class TestRunSucceeded(WatchdogTestCase):
    def test_success_without_a_bundle_is_the_legitimate_empty_day(self):
        """exchange_phase_a.py's own contract: a day with nothing to ask any
        channel for exits 0 and writes no bundle. The watchdog must not
        manufacture a failure out of that."""
        run_stub = {"id": 9, "html_url": "https://x/runs/9",
                    "status": "queued", "conclusion": None,
                    "created_at": "2030-01-01T00:00:00Z"}
        succeeded = {"id": 9, "html_url": "https://x/runs/9",
                     "status": "completed", "conclusion": "success"}
        session = FakeSession(
            post_response=FakeResponse(204),
            get_queue=[runs_list_response(run_stub), FakeResponse(200, succeeded)],
        )
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            sleep_fn=lambda s: None, clock=self._fake_clock())
        self.assertEqual(outcome["status"], "run_succeeded_no_bundle")

    def test_success_with_a_bundle_is_recovered(self):
        run_stub = {"id": 11, "html_url": "https://x/runs/11",
                    "status": "queued", "conclusion": None,
                    "created_at": "2030-01-01T00:00:00Z"}
        succeeded_payload = {"id": 11, "html_url": "https://x/runs/11",
                             "status": "completed", "conclusion": "success"}

        def write_the_bundle():
            xb.write_bundle(DATE, [], [])

        session = FakeSession(
            post_response=FakeResponse(204),
            get_queue=[
                runs_list_response(run_stub),
                FakeResponse(200, succeeded_payload, on_return=write_the_bundle),
            ],
        )
        self.assertFalse(watchdog.bundle_ready(DATE))
        outcome = watchdog.run_watchdog(
            DATE, "trending", REPO, TOKEN, session=session,
            sleep_fn=lambda s: None, clock=self._fake_clock())
        self.assertEqual(outcome["status"], "recovered")
        self.assertTrue(watchdog.bundle_ready(DATE))


class TestWriteOutcome(WatchdogTestCase):
    def test_outcome_lands_under_the_bundle_dir(self):
        path = watchdog.write_outcome(DATE, {"status": "timeout", "date": DATE})
        self.assertEqual(path, xb.bundle_dir(DATE) / watchdog.OUTCOME_FILENAME)
        self.assertTrue(path.exists())


class TestOkStatuses(unittest.TestCase):
    def test_ok_statuses_are_exactly_the_non_refusal_ones(self):
        self.assertEqual(
            watchdog.OK_STATUSES,
            {"already_ready", "recovered", "run_succeeded_no_bundle"})


if __name__ == "__main__":
    unittest.main()
