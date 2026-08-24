"""Gate 0 (NOVELTY) must fail CLOSED when it cannot run.

Doctor finding cf263a770061 (2026-08-08): `novelty_check`'s ffprobe call
swallowed every exception and returned [] — "no stale spans" — so a broken
or missing probe silently satisfied the HARD rule DIRECTOR.md calls gate 0.
The fix: a probe failure raises `NoveltyProbeError`, the DIRECTOR rejects
(exit 5) instead of blessing, and the outage is persisted in the findings so
it is visible in the report rather than laundered as a clean film.

    python -m unittest tests.test_novelty_fail_closed -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import no_dull_beats as ndb  # noqa: E402


def _broken_subprocess_run(*a, **kw):
    raise FileNotFoundError("ffprobe: command not found")


class TestProbeFailureIsNotClean(unittest.TestCase):
    def test_a_dead_ffprobe_raises_instead_of_passing(self):
        """The exact bug: subprocess failure used to come back as []."""
        with mock.patch.object(ndb.subprocess, "run",
                               side_effect=_broken_subprocess_run):
            with self.assertRaises(ndb.NoveltyProbeError) as cm:
                ndb.novelty_check(Path("/nonexistent/render.mp4"))
        self.assertIn("duration", str(cm.exception))

    def test_garbage_ffprobe_output_raises(self):
        """ffprobe running but answering nothing (empty stdout) is the same
        outage — float('') must not become 'clean'."""
        with mock.patch.object(ndb.subprocess, "run", return_value=(
                SimpleNamespace(stdout="", stderr="", returncode=1))):
            with self.assertRaises(ndb.NoveltyProbeError):
                ndb.novelty_check(Path("/nonexistent/render.mp4"))

    def test_undecodable_frames_raise(self):
        """ffprobe reads a duration but ffmpeg can decode no frame at all:
        every signature is None, zero pairs get compared, and the old code
        returned [] = clean. Same outage, different coat."""
        with mock.patch.object(ndb.subprocess, "run", return_value=(
                SimpleNamespace(stdout="12.0\n", stderr="", returncode=0))), \
             mock.patch.object(ndb, "_frame_sig", return_value=None):
            with self.assertRaises(ndb.NoveltyProbeError) as cm:
                ndb.novelty_check(Path("/nonexistent/render.mp4"))
        self.assertIn("frame pair", str(cm.exception))

    def test_a_video_too_short_to_violate_is_legitimately_clean(self):
        """A <=5s render has no room for a >5s hold — no comparable pair is
        the CORRECT answer there, not an outage."""
        with mock.patch.object(ndb.subprocess, "run", return_value=(
                SimpleNamespace(stdout="4.0\n", stderr="", returncode=0))), \
             mock.patch.object(ndb, "_frame_sig", return_value=None):
            self.assertEqual(ndb.novelty_check(Path("/x.mp4")), [])


class TestTheDirectorHoldsTheFilm(unittest.TestCase):
    """Drive `_direct` far enough to reach gate 0 with every other gate
    stubbed quiet, then break the probe: the run must REJECT (exit 5) and
    the outage must land in the persisted findings — never return 0."""

    def _run_direct(self, tmp: Path) -> int:
        story = tmp / "story.beats.json"
        story.write_text(json.dumps({"beats": [
            {"job": "HOOK", "narration": "words", "subject": "a lighthouse"},
        ]}))
        out = tmp / "film.mp4"
        with mock.patch.object(ndb, "_run", return_value=(
                SimpleNamespace(stdout="", stderr=""))), \
             mock.patch.object(ndb, "_judge", return_value=(
                {"dead_fraction": 0.0, "mean_appeal": 0.9}, [])), \
             mock.patch.object(ndb, "_hook_gate", return_value=None), \
             mock.patch.object(ndb, "pacing_check", return_value=[]), \
             mock.patch.object(ndb, "variety_check", return_value=[]), \
             mock.patch.object(ndb, "_record_memory", return_value=None), \
             mock.patch.object(
                 ndb, "novelty_check",
                 side_effect=ndb.NoveltyProbeError("ffprobe is down")):
            return ndb.run(story, out, rounds=1)

    def test_probe_outage_rejects_and_is_persisted(self):
        with tempfile.TemporaryDirectory(prefix="ndb-") as td:
            tmp = Path(td)
            rc = self._run_direct(tmp)
            self.assertEqual(rc, 5, "a probe outage must HOLD the film")
            findings = json.loads(
                (tmp / "film_pkg" / "director_findings.json").read_text())
            self.assertEqual(findings["director_rc"], 5)
            techs = [f for f in findings["findings"]
                     if f["defect_code"] == "TECHNICAL"]
            self.assertTrue(techs, findings)
            self.assertIn("ffprobe is down", techs[0]["complaint"])
            self.assertEqual(techs[0]["severity"], "blocker")


if __name__ == "__main__":
    unittest.main(verbosity=2)
