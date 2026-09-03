"""The repair loop must repair the scene that FAILED.

2026-08-11. All four explainer stories were blocked BEFORE vision review
(a temporal hard-fail produces no `weakest_scene` and no `segN` prose), so
`failing_scene` fell through to its documented last-segment default. Every
one of them "repaired" segment 2 — measuring 24.0 effective fps, i.e.
passing — while segment 0, measuring 0.8-1.4 against an 11.0 floor, was
never touched. Two renders, two showrunner reviews, ~20 minutes of runner
time per story, aimed at a scene that was fine.

The evidence to aim correctly was already on disk the whole time:
`studio_render._scene_metrics` writes a per-scene `metrics.json` carrying
that scene's own measured gate. Nothing read it. That is the exact shape
CLAUDE.md's rule zero calls out — a capability nothing calls.

    python -m unittest tests.test_repair_targets_the_failure -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from scripts import scene_repair as sr  # noqa: E402


class SceneMetricsCase(unittest.TestCase):
    SLUG = "a-story-slug"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="repair-"))
        self._root = sr.REPO
        sr.REPO = self.tmp

    def tearDown(self):
        sr.REPO = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scene(self, i: int, *, gate: str, fps: float):
        d = self.tmp / "output" / "scenes" / self.SLUG / f"segment_{i}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "metrics.json").write_text(json.dumps({
            "slug": self.SLUG, "scene": i, "id": f"segment_{i}",
            "gate": gate, "effective_fps": fps,
            "temporal": {"effective_fps": fps}}))


class TestItAimsAtTheMeasuredFailure(SceneMetricsCase):

    def test_the_2026_08_11_case_targets_seg0_not_seg2(self):
        """The literal production numbers from that day."""
        self.scene(0, gate="effective_fps 1.0 < 11.0 (phase-1 floor)", fps=1.0)
        self.scene(1, gate="pass", fps=17.2)
        self.scene(2, gate="pass", fps=24.0)
        self.assertEqual(sr.failing_scene({}, 3, slug=self.SLUG), 0)

    def test_the_last_segment_default_would_have_got_this_wrong(self):
        """Pin the counterfactual so the value of the measurement is
        explicit: with no slug there is nothing to read and the emergency
        default picks the passing scene."""
        self.scene(0, gate="effective_fps 1.0 < 11.0", fps=1.0)
        self.scene(2, gate="pass", fps=24.0)
        self.assertEqual(sr.failing_scene({}, 3), 2)

    def test_the_worst_failing_scene_wins_when_several_fail(self):
        self.scene(0, gate="duplicate_ratio 0.47 > 0.45", fps=12.7)
        self.scene(1, gate="effective_fps 2.5 < 11.0", fps=2.5)
        self.scene(2, gate="pass", fps=24.0)
        self.assertEqual(sr.failing_scene({}, 3, slug=self.SLUG), 1)

    def test_all_passing_falls_through_to_the_judge(self):
        """When no scene fails its OWN gate the block is a craft judgment,
        and the judge's structured diagnosis is the right source."""
        for i in range(3):
            self.scene(i, gate="pass", fps=24.0)
        v = {"weakest_scene": {"index": 1}}
        self.assertEqual(sr.failing_scene(v, 3, slug=self.SLUG), 1)

    def test_a_structured_verdict_never_beats_a_measured_failure(self):
        """A vision judge saying 'scene 2 is weak' does not change the fact
        that scene 0 is frozen. Fix what is measurably broken first."""
        self.scene(0, gate="effective_fps 0.8 < 11.0", fps=0.8)
        self.scene(2, gate="pass", fps=24.0)
        v = {"weakest_scene": {"index": 2}}
        self.assertEqual(sr.failing_scene(v, 3, slug=self.SLUG), 0)


class TestItIsRobustToMissingOrJunkEvidence(SceneMetricsCase):

    def test_no_metrics_on_disk_falls_back_quietly(self):
        v = {"weakest_scene": {"id": "segment_1"}}
        self.assertEqual(sr.failing_scene(v, 3, slug=self.SLUG), 1)

    def test_a_corrupt_sidecar_is_skipped_not_fatal(self):
        d = self.tmp / "output" / "scenes" / self.SLUG / "segment_0"
        d.mkdir(parents=True)
        (d / "metrics.json").write_text("{not json")
        self.scene(1, gate="effective_fps 2.0 < 11.0", fps=2.0)
        self.assertEqual(sr.failing_scene({}, 3, slug=self.SLUG), 1)

    def test_a_scene_index_beyond_the_segment_count_is_ignored(self):
        self.scene(7, gate="effective_fps 1.0 < 11.0", fps=1.0)
        self.assertEqual(sr.measured_failures(self.SLUG, 3), [])

    def test_an_older_sidecar_shape_still_reads(self):
        """Sidecars written before `gate`/`effective_fps` were promoted to
        top level carry them nested. Reading only the new shape would make
        the repair silently blind on the first run after a deploy."""
        d = self.tmp / "output" / "scenes" / self.SLUG / "segment_0"
        d.mkdir(parents=True)
        (d / "metrics.json").write_text(json.dumps({
            "verdict": {"gate": "effective_fps 1.0 < 11.0"},
            "temporal": {"effective_fps": 1.0}}))
        self.assertEqual(sr.failing_scene({}, 3, slug=self.SLUG), 0)


class TestProposePassesTheSlugThrough(unittest.TestCase):
    def test_the_call_site_supplies_it(self):
        """`failing_scene` cannot read the evidence without knowing which
        story it is looking at."""
        src = (ROOT / "scripts" / "scene_repair.py").read_text()
        self.assertIn("failing_scene(verdict, len(segs), slug=slug)", src)


if __name__ == "__main__":
    unittest.main()
