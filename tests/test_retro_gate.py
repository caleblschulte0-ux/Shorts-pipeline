"""The retro loop cannot finish green having produced no review.

Doctor finding 694ab7c3e1d4. Analytics refresh, experiment advance, failure
census, brief build and triage are all `continue-on-error: true` in
`retro.yml`, and the commit step that follows is fail-closed only around
whatever files happen to exist. So `build_retro.py` and
`review_proposals.py` could BOTH fail, `ci_commit_state.sh` would find older
state to commit, and the run finished green. A missing daily review looked
exactly like a quiet day — a workflow reporting on the steps it ran instead
of the outcome it produced, which is the failure this repo keeps relearning.

`scripts/retro_gate.py` checks the outputs by name for the RESOLVED date.
It runs before the commit (so it cannot be skipped) and only records its
verdict; the run is failed at the end, after the diagnostics that do exist
have been committed. A red run with its evidence kept is worth far more than
a red run that threw the evidence away.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "retro_gate", ROOT / "scripts" / "retro_gate.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)

DATE = "20260909"


class _Tree(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.day = self.root / DATE

    def write(self, **files):
        self.day.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            name = name.replace("__", ".")
            p = self.day / name
            p.write_text(body if isinstance(body, str)
                         else json.dumps(body, indent=2))

    def problems(self, mode="nightly"):
        return rg._problems(DATE, mode, root=self.root)


class ACompleteDayPasses(_Tree):
    def test_nightly_with_everything(self):
        self.write(brief__json={"date": DATE}, brief__md="# brief",
                   triage__json={"date": DATE})
        self.assertEqual(self.problems(), [])

    def test_triage_only_needs_only_the_triage(self):
        """The proposals-push path deliberately does not rebuild the brief —
        that would move the evidence out from under the proposals just
        written against it."""
        self.write(triage__json={"date": DATE})
        self.assertEqual(self.problems("triage"), [])


class AMissingReviewIsNotAQuietDay(_Tree):
    def test_no_directory_at_all(self):
        self.assertTrue(self.problems())

    def test_the_exact_failure_the_finding_describes(self):
        """Both scripts failed; older state was still committable."""
        self.day.mkdir(parents=True)
        (self.day / "proposals").mkdir()
        problems = self.problems()
        self.assertTrue(any("brief.json" in p for p in problems), problems)
        self.assertTrue(any("triage.json" in p for p in problems), problems)

    def test_a_brief_without_a_triage_still_fails_nightly(self):
        self.write(brief__json={"date": DATE}, brief__md="# brief")
        self.assertTrue(any("triage.json" in p for p in self.problems()))

    def test_an_empty_file_is_not_an_output(self):
        self.write(brief__json="", brief__md="# b", triage__json={"date": DATE})
        self.assertTrue(any("empty" in p for p in self.problems()))

    def test_unparseable_json_is_not_an_output(self):
        self.write(brief__json="{not json", brief__md="# b",
                   triage__json={"date": DATE})
        self.assertTrue(any("not valid JSON" in p for p in self.problems()))

    def test_another_days_file_in_this_days_folder_is_caught(self):
        """A rerun that resolved a different date would otherwise be
        indistinguishable from success."""
        self.write(brief__json={"date": "20260101"}, brief__md="# b",
                   triage__json={"date": DATE})
        self.assertTrue(any("another day" in p for p in self.problems()))

    def test_a_json_list_is_not_an_output(self):
        self.write(brief__json=[1, 2], brief__md="# b",
                   triage__json={"date": DATE})
        self.assertTrue(any("not an object" in p for p in self.problems()))


class TheGateIsWiredIntoTheWorkflow(unittest.TestCase):
    def setUp(self):
        import yaml
        self.wf = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "retro.yml").read_text())
        self.steps = self.wf["jobs"][next(iter(self.wf["jobs"]))]["steps"]

    def _index(self, needle: str) -> int:
        for i, s in enumerate(self.steps):
            if needle in (s.get("run") or "") or needle in (s.get("name") or ""):
                return i
        self.fail(f"no step matching {needle!r}")

    def test_the_gate_runs(self):
        self._index("scripts/retro_gate.py")

    def test_the_gate_runs_before_the_commit(self):
        """After the commit it could be skipped by an earlier failure; the
        point is that it always runs."""
        self.assertLess(self._index("scripts/retro_gate.py"),
                        self._index("Commit brief + triage"))

    def test_the_gate_does_not_block_the_commit(self):
        gate = self.steps[self._index("scripts/retro_gate.py")]
        self.assertTrue(gate.get("continue-on-error"),
                        "a failing gate must not throw away the diagnostics")
        self.assertTrue(gate.get("id"), "the final step needs its outcome")

    def test_a_failed_gate_really_fails_the_run(self):
        gate_id = self.steps[self._index("scripts/retro_gate.py")]["id"]
        last = self.steps[-1]
        self.assertIn(f"steps.{gate_id}.outcome == 'failure'",
                      " ".join(str(last.get("if", "")).split()))
        self.assertIn("exit 1", last.get("run", ""))

    def test_the_gate_is_the_last_word(self):
        """Nothing may run after the failure step and mask it."""
        self.assertIn("exit 1", self.steps[-1].get("run", ""))


if __name__ == "__main__":
    unittest.main()
