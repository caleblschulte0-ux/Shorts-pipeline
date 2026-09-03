"""An empty backlog and a dead reviewer look exactly the same.

The doctor is two halves and only one of them is ours. `doctor.yml` writes
the evidence pack every morning and the triage rules whatever is waiting —
both ran daily through 2026-08-12, and the loop completed end to end once:
08-10 findings -> 08-11 triage ruled all twenty -> fixes merged as #255,
#256, #263, #264, including a genuine fail-open in the third-capture QA gate.

Then the input stopped. `doctor/reports/` has nothing for 08-11 or 08-12, and
NOTHING SHOUTED — `daily_alarm` had no doctor check at all and `doctor.yml`
only warns when its own commit fails. `backlog --state new` prints "backlog
is empty", which is exactly what a healthy fully-ruled backlog prints too.

That is the shape this repo keeps re-learning: the 08-03 auto-pause (a green
check on a dead channel), Phase A exiting 0 with no packages. A queue with no
producer is not an empty queue.

    python -m unittest tests.test_doctor_reviewer_silence -v
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# APPEND, never insert: scripts/ has its own test_*.py and putting it first
# shadows the real tests package during discovery.
sys.path.append(str(ROOT / "scripts"))


class DoctorSilenceCase(unittest.TestCase):
    DATE = "20260812"

    def setUp(self):
        import daily_alarm as alarm
        self.alarm = alarm
        self.tmp = Path(tempfile.mkdtemp(prefix="docsilence-"))
        self._root = alarm.ROOT
        alarm.ROOT = self.tmp
        (self.tmp / "doctor" / "reports").mkdir(parents=True)

    def tearDown(self):
        self.alarm.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def filed(self, *stamps):
        for s in stamps:
            (self.tmp / "doctor" / "reports" / f"{s}.json").write_text("{}")

    def run_check(self):
        return self.alarm.check(self.DATE)

    def codes(self, r):
        return {a["code"]: a["severity"] for a in r["alarms"]}


class TestSilenceIsCaught(DoctorSilenceCase):

    def test_the_real_2026_08_12_state_raises(self):
        """Findings through 08-10, checked on 08-12 — two days quiet."""
        self.filed("20260808", "20260809", "20260810")
        self.assertIn("doctor_reviewer_silent", self.codes(self.run_check()))

    def test_two_days_is_a_warning_three_is_critical(self):
        self.filed("20260810")
        self.assertEqual(self.codes(self.run_check())["doctor_reviewer_silent"],
                         "warning")
        shutil.rmtree(self.tmp / "doctor" / "reports")
        (self.tmp / "doctor" / "reports").mkdir(parents=True)
        self.filed("20260809")
        self.assertEqual(self.codes(self.run_check())["doctor_reviewer_silent"],
                         "critical")

    def test_a_current_reviewer_raises_nothing_and_says_so(self):
        self.filed("20260811", "20260812")
        r = self.run_check()
        self.assertNotIn("doctor_reviewer_silent", self.codes(r))
        self.assertTrue(any("findings current" in n for n in r["notes"]))

    def test_yesterday_is_still_fine(self):
        """The reviewer runs nightly; one day's lag is normal, not an
        outage. Shouting daily about a working system is how people learn to
        ignore red."""
        self.filed("20260811")
        self.assertNotIn("doctor_reviewer_silent", self.codes(self.run_check()))

    def test_never_having_run_is_caught_too(self):
        r = self.run_check()
        self.assertIn("doctor_reviewer_silent", self.codes(r))

    def test_the_fix_text_points_at_the_right_half(self):
        """The repo side needs no changes — sending someone to edit the
        pipeline would be sending them to the wrong place."""
        self.filed("20260809")
        a = next(x for x in self.run_check()["alarms"]
                 if x["code"] == "doctor_reviewer_silent")
        self.assertIn("ChatGPT app", a["fix"])
        self.assertIn("doctor/reports/", a["fix"])

    def test_it_says_the_other_half_is_still_running(self):
        """Otherwise the reader concludes the whole doctor is dead and goes
        looking in the workflow, which is fine."""
        self.filed("20260809")
        a = next(x for x in self.run_check()["alarms"]
                 if x["code"] == "doctor_reviewer_silent")
        self.assertIn("triage", a["detail"])


class TestItSurvivesJunk(DoctorSilenceCase):

    def test_non_date_filenames_are_ignored(self):
        self.filed("20260812")
        (self.tmp / "doctor" / "reports" / "README.json").write_text("{}")
        (self.tmp / "doctor" / "reports" / "latest.json").write_text("{}")
        self.assertNotIn("doctor_reviewer_silent",
                         self.codes(self.run_check()))

    def test_a_missing_doctor_directory_is_not_an_error(self):
        shutil.rmtree(self.tmp / "doctor")
        r = self.run_check()
        self.assertIn("alarms", r)

    def test_the_check_never_raises_out_of_the_alarm(self):
        (self.tmp / "doctor" / "reports" / "2026081.json").write_text("{}")
        self.assertIn("alarms", self.run_check())


if __name__ == "__main__":
    unittest.main()
