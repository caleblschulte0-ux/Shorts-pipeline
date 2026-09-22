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


class ARejectedPanelGetsOneReplacementRound(unittest.TestCase):
    """2026-09-22 20:15, the staff story at 65: "after the post card there
    is not a single story illustration". Dropping the wrong picture opened
    the next hole. The brain's own better query is searched once through
    the self-fill lanes, materialised and judged again."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        self._env = mock.patch.dict("os.environ", {"SHOT_RELEVANCE": "on"})
        self._env.start()
        self.pkg = {"title": "t", "slug": "t", "shots": [
            {"phrase": "walked every room", "query": "apartment", "image_url": "u0"},
            {"phrase": "the deposit law", "query": "gavel", "image_url": "u1",
             "media_sha256": "abc", "media_bytes": 5},
            {"phrase": "a cracked mirror", "query": "mirror", "image_url": "u2"}]}
        self.dropped = [{"index": 1, "why": "a gavel on a medicine book",
                         "better_query": "security deposit form"}]
        self.made = []

    def tearDown(self):
        self._env.stop()
        self.td.cleanup()

    def materialise(self, i, url):
        p = self.d / f"panel_{i}.jpg"
        p.write_bytes(b"x")
        self.made.append((i, url))
        return p

    def _round(self, answer, fill="https://img/deposit-form.jpg"):
        with mock.patch("scripts.exchange_phase_b.self_fill",
                        return_value=fill) as sf, \
                mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(SR.subprocess, "run", return_value=_proc(answer)):
            kept, again = SR.replace_dropped(self.pkg, self.dropped,
                                             self.materialise, title="t")
        return kept, again, sf

    def test_the_brains_query_is_searched_materialised_and_judged_again(self):
        answer = json.dumps({"shots": [{"index": 1, "depicts": True, "why": "a form"}]})
        kept, again, sf = self._round(answer)
        self.assertEqual(sorted(kept), [1])
        self.assertEqual(again, [])
        sf.assert_called_once_with(self.pkg, 1)
        shot = self.pkg["shots"][1]
        self.assertEqual(shot["query"], "security deposit form")
        self.assertEqual(shot["image_url"], "https://img/deposit-form.jpg")
        self.assertNotIn("media_sha256", shot)       # a new picture, no old attestation
        self.assertEqual(self.made, [(1, "https://img/deposit-form.jpg")])

    def test_a_second_no_keeps_the_gap(self):
        answer = json.dumps({"shots": [{"index": 1, "depicts": False, "why": "still a gavel"}]})
        kept, again, _ = self._round(answer)
        self.assertEqual(kept, {})
        self.assertEqual([d["index"] for d in again], [1])
        self.assertNotIn("image_url", self.pkg["shots"][1])

    def test_no_search_hit_restores_the_shot_and_leaves_the_gap(self):
        kept, again, _ = self._round("{}", fill=None)
        self.assertEqual((kept, again), ({}, []))
        self.assertEqual(self.pkg["shots"][1]["query"], "gavel")
        self.assertEqual(self.pkg["shots"][1]["media_sha256"], "abc")
        self.assertEqual(self.made, [])

    def test_no_better_query_means_no_search(self):
        with mock.patch("scripts.exchange_phase_b.self_fill") as sf:
            kept, again = SR.replace_dropped(
                self.pkg, [{"index": 1, "why": "x", "better_query": ""}], self.materialise)
        sf.assert_not_called()
        self.assertEqual((kept, again), ({}, []))

    def test_the_first_verdict_carries_the_better_query(self):
        answer = json.dumps({"shots": [
            {"index": 1, "depicts": False, "why": "gavel", "better_query": "deposit form"}]})
        with mock.patch.object(SR.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(SR.subprocess, "run", return_value=_proc(answer)):
            _, dropped = SR.filter_panels({1: self.d / "p.jpg"}, self.pkg["shots"])
        self.assertEqual(dropped[0]["better_query"], "deposit form")
        self.assertIn("better_query", SR._PROMPT)


class TheRendererRoutesItsPanelsThroughIt(unittest.TestCase):
    def test_a_dropped_panel_is_replaced_before_the_render(self):
        src = (ROOT / "make_reddit_story.py").read_text()
        body = src[src.index("def _shot_panels("):src.index("def _shot_windows(")]
        self.assertLess(body.index("filter_panels"), body.index("replace_dropped"))
        self.assertIn("_rel.replace_dropped(", body)
        self.assertIn("out.update(replaced)", body)

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
