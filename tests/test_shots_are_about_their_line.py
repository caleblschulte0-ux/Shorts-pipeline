"""A TOP-PANEL SHOT THAT DOES NOT DEPICT ITS LINE IS NOT PLACED.

junk_imagery was 27 of 101 trending verdicts in the twelve days to
2026-09-22, every one a keyword-matched stock photo nothing had looked at.
`shared/shot_relevance` asks the headless brain about every panel before
it is composited; a "no" removes the panel, everything else keeps it.
Held here by injection: the brain says no -> dropped; the brain is absent,
fails, or answers garbage -> every panel kept (the status quo); the
renderer routes its panels through it; the switch turns it off.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import shot_relevance as SR                      # noqa: E402


def _proc(stdout: str, rc: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr="")


class TheBrainsNoRemovesThePanel(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        d = Path(self.td.name)
        self.panels = {0: d / "p0.jpg", 1: d / "p1.jpg", 2: d / "p2.jpg"}
        for p in self.panels.values():
            p.write_bytes(b"x")
        self.shots = [{"phrase": "the landlord walked every room"},
                      {"phrase": "the state's security deposit law"},
                      {"phrase": "a cracked mirror"}]

        self._env = mock.patch.dict("os.environ", {"SHOT_RELEVANCE": "on"})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self.td.cleanup()

    def test_it_is_on_in_ci_and_off_on_a_laptop_unless_asked(self):
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=False):
            import os
            os.environ.pop("SHOT_RELEVANCE", None)
            self.assertTrue(SR.enabled())
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(SR.enabled())
        with mock.patch.dict("os.environ", {"SHOT_RELEVANCE": "on"}, clear=True):
            self.assertTrue(SR.enabled())

    def test_a_no_drops_only_that_panel(self):
        answer = json.dumps({"shots": [
            {"index": 0, "depicts": True, "why": "a person in an empty room"},
            {"index": 1, "depicts": False, "why": "a gavel on a medicine book"},
            {"index": 2, "depicts": True, "why": "a cracked mirror"}]})
        with mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(SR.subprocess, "run", return_value=_proc(answer)) as run:
            kept, dropped = SR.filter_panels(self.panels, self.shots, title="t")
        self.assertEqual(sorted(kept), [0, 2])
        self.assertEqual([d["index"] for d in dropped], [1])
        self.assertIn("gavel", dropped[0]["why"])
        prompt = run.call_args[0][0][2]
        self.assertIn("the state's security deposit law", prompt)
        self.assertIn(str(self.panels[1]), prompt)
        self.assertEqual(run.call_args[0][0][0], "claude")

    def test_no_cli_keeps_every_panel(self):
        with mock.patch.object(SR.shutil, "which", return_value=None):
            kept, dropped = SR.filter_panels(self.panels, self.shots)
        self.assertEqual(kept, self.panels)
        self.assertEqual(dropped, [])

    def test_a_failed_or_garbled_answer_keeps_every_panel(self):
        for proc in (_proc("", rc=1), _proc("I could not open the files"),
                     _proc('{"verdict": "ship"}')):
            with mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                    mock.patch.object(SR.subprocess, "run", return_value=proc):
                kept, dropped = SR.filter_panels(self.panels, self.shots)
            self.assertEqual(kept, self.panels)
            self.assertEqual(dropped, [])

    def test_a_timeout_keeps_every_panel(self):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
        with mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(SR.subprocess, "run", side_effect=boom):
            kept, dropped = SR.filter_panels(self.panels, self.shots)
        self.assertEqual(kept, self.panels)

    def test_a_shot_the_brain_did_not_rule_on_is_kept(self):
        answer = json.dumps({"shots": [{"index": 1, "depicts": False, "why": "x"}]})
        with mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(SR.subprocess, "run", return_value=_proc(answer)):
            kept, _ = SR.filter_panels(self.panels, self.shots)
        self.assertEqual(sorted(kept), [0, 2])

    def test_the_switch_turns_it_off(self):
        with mock.patch.dict("os.environ", {"SHOT_RELEVANCE": "off"}), \
                mock.patch.object(SR.subprocess, "run") as run:
            kept, dropped = SR.filter_panels(self.panels, self.shots)
        self.assertEqual(kept, self.panels)
        run.assert_not_called()


class TheRendererRoutesItsPanelsThroughIt(unittest.TestCase):
    def test_shot_panels_calls_the_gate_after_materialising(self):
        src = (ROOT / "make_reddit_story.py").read_text()
        i = src.index("def _shot_panels(")
        body = src[i:src.index("def _shot_windows(")]
        self.assertIn("shot_relevance", body)
        self.assertIn("_rel.filter_panels(out, pkg.get(\"shots\") or []", body)
        self.assertLess(body.index("shot panel {i} skipped"), body.index("filter_panels"))

    def test_the_render_job_installs_the_cli(self):
        wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
        self.assertIn("Prepare showrunner judge", wf)


if __name__ == "__main__":
    unittest.main()
