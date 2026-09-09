"""A DETECTOR NOBODY HEARS IS NOT A DETECTOR.

Operator, 2026-09-09: *"How do we make this never break again?"*

The honest answer turned out not to be another gate. The gates work — they
are the reason nothing posted that day. What did not work is that the
pipeline's own alarm could not reach a person.

`alarm.yml` is the only workflow allowed to be loud, and its premise is
right: *"every workflow reports on the STEPS it ran and none report on the
OUTCOME they produced."* It judges outcomes against the registry, comments,
and deliberately exits 1 so the run goes red. It fired correctly on
2026-09-06, 09-07, 09-08 and 09-09 — four consecutive days of "the day did
not do what it was supposed to."

Every one went unread, because:

* its only output was a comment on issue #1, which is also where scout
  results and daily reports land — a firehose, not a signal; and
* it was the one publishing-adjacent workflow with NO ntfy push, while
  `daily.yml` and `credentials.yml` both had one.

A run being red in a tab nobody watches is the same failure as a capability
nothing calls, one layer out.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"


class TheAlarmCanReachAPhone(unittest.TestCase):
    ALARM = WF / "alarm.yml"

    def test_the_alarm_pushes_when_it_fires(self):
        s = self.ALARM.read_text()
        self.assertIn("NTFY_TOPIC", s,
                      "the loudest workflow has no way to be loud")
        self.assertIn("ntfy.sh", s)

    def test_the_push_only_happens_when_something_is_wrong(self):
        """A daily 'all good' push is how people stop reading the alarm — the
        workflow's own header says so."""
        s = self.ALARM.read_text()
        push = s[s.index("Push the alarm to a phone"):]
        self.assertIn("steps.judge.outputs.status != '0'", push.split("run:")[0])

    def test_a_missing_topic_is_SAID_not_swallowed(self):
        """If the secret is unset the alarm still cannot reach anybody, and
        that fact must appear in the run rather than being a silent skip —
        otherwise the alarm about the alarm is silent too."""
        s = self.ALARM.read_text()
        self.assertIn("alarm-cannot-reach-you", s)

    def test_it_still_comments_and_still_goes_red(self):
        """The push is an ADDITION. The issue comment is the durable record
        and the red run is what a human sees in the Actions tab; neither was
        replaced."""
        s = self.ALARM.read_text()
        self.assertIn("gh issue comment", s)
        self.assertIn("exit 1", s)


class EveryLOUDPathHasTheSameReach(unittest.TestCase):
    """The gap was found by asking which workflows could push and which could
    not. The answer was arbitrary — an accident of which one was written when
    — so it is pinned here rather than left to be re-discovered."""

    LOUD = ("alarm.yml", "daily.yml", "credentials.yml")

    def test_every_workflow_that_alerts_can_push(self):
        missing = [n for n in self.LOUD
                   if "ntfy.sh" not in (WF / n).read_text()]
        self.assertEqual(missing, [],
                         f"these alert but cannot reach a phone: {missing}")


if __name__ == "__main__":
    unittest.main()
