"""An unmeasured cadence probe is not evidence of a good video.

Doctor finding 3de32f29a8e4. `_temporal_evidence` caught every failure —
ffmpeg missing, a PIL decode error, too few sampled frames — into
`ev["error"]` and returned the cadence fields as None. Downstream:

    temporal_hard_fail(unknown)  -> None   ("never block blind")
    temporal_grade(unknown)      -> 2      ("don't punish blind")

so the review continued to the vision judge carrying a measurement that had
not happened, the judge could answer `ship` with a bounded score, and
`shared/showrunner_gate.decide()` — which is fail-closed on reviewer failure
— saw a complete verdict and had nothing to hold on. Nothing raised, nothing
went red, and the objective half of the gate had silently been skipped.

"Never block blind" is correct for the code FLOOR: it may only add blocks on
measured badness. It is not a licence to PUBLISH blind. So the unknown state
raises out of `review_video`, which is the one place this repo decides
publish-vs-preview — the publish run holds, the preview run skips, both by
the existing rules in `showrunner_gate`.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util                                     # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "showrunner_review", ROOT / "scripts" / "showrunner_review.py")
sr = importlib.util.module_from_spec(_spec)
sys.modules["showrunner_review"] = sr
_spec.loader.exec_module(sr)

from shared import showrunner_gate as gate                # noqa: E402

MEASURED = {"sample_fps": 24, "duplicate_ratio": 0.1, "effective_fps": 21.6,
            "max_dup_run": 3, "measured": True}


class TheProbeSaysWhetherItMeasured(unittest.TestCase):
    def test_a_real_measurement_is_flagged_measured(self):
        self.assertIsNone(sr.temporal_unmeasured(MEASURED))

    def test_ffmpeg_missing_is_unmeasured(self):
        with mock.patch.object(sr.subprocess, "run",
                               side_effect=FileNotFoundError("ffmpeg")):
            with mock.patch("tempfile.TemporaryDirectory"):
                ev = sr._temporal_evidence(Path("x.mp4"), Path("/tmp"))
        self.assertFalse(ev["measured"])
        self.assertIn("ffmpeg", ev.get("error", ""))
        self.assertIsNotNone(sr.temporal_unmeasured(ev))

    def test_too_few_frames_is_unmeasured_and_says_so(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(sr.subprocess, "run", return_value=None):
                ev = sr._temporal_evidence(Path("x.mp4"), Path(td))
        self.assertFalse(ev["measured"])
        self.assertIn("sampled frames", ev.get("error", ""))
        # The specific shape the finding named: numbers still None, and the
        # old code read that as "nothing to report".
        self.assertIsNone(ev["effective_fps"])
        self.assertIsNotNone(sr.temporal_unmeasured(ev))

    def test_an_evidence_dict_with_no_flag_at_all_is_unmeasured(self):
        """Fail closed on a shape we do not recognise, not open."""
        self.assertIsNotNone(sr.temporal_unmeasured({}))
        self.assertIsNotNone(sr.temporal_unmeasured({"effective_fps": 30}))


class TheGradersStillNeverBlockBlind(unittest.TestCase):
    """The floor's own contract is unchanged — it adds blocks on measured
    badness only. The fix is upstream of it, not inside it."""

    def test_the_hard_floor_still_passes_unknown_evidence(self):
        self.assertIsNone(sr.temporal_hard_fail(
            {"effective_fps": None, "duplicate_ratio": None}))

    def test_the_grade_is_still_neutral_for_unknown(self):
        self.assertEqual(sr.temporal_grade({"effective_fps": None}), 2)

    def test_a_measured_bad_cadence_still_fails(self):
        bad = {"effective_fps": 4.0, "duplicate_ratio": 0.9,
               "max_dup_run": 90, "measured": True}
        self.assertIsNotNone(sr.temporal_hard_fail(bad))


class MissingMilestonesAreAnUnappliedGate(unittest.TestCase):
    def test_an_unloadable_phase_raises_rather_than_passing(self):
        """Measured cadence with no floor to measure it against is not a
        pass — before this it returned None, i.e. 'no failure'."""
        with mock.patch.dict(sys.modules, {"data_learning.quality_milestones": None}):
            with self.assertRaises(RuntimeError) as ctx:
                sr.temporal_hard_fail(MEASURED)
        self.assertIn("milestones", str(ctx.exception))


class ReviewVideoRaisesSoTheGateCanDecide(unittest.TestCase):
    def test_review_video_raises_on_an_unmeasured_probe(self):
        with mock.patch.object(sr, "_extract_frames", return_value=["a.png"]), \
             mock.patch.object(sr, "_motion_evidence", return_value={}), \
             mock.patch.object(sr, "_temporal_evidence",
                               return_value={"measured": False,
                                             "error": "ffmpeg not found"}), \
             mock.patch.object(sr, "_judge") as judged:
            with self.assertRaises(RuntimeError) as ctx:
                sr.review_video(Path("x.mp4"), {"chapters": []})
        self.assertIn("cadence probe", str(ctx.exception))
        judged.assert_not_called()      # and it costs no vision call

    def test_that_raise_holds_a_publish_run(self):
        d = gate.decide(will_upload=True, gate_on=True, verdict=None,
                        error="cadence probe produced no measurement")
        self.assertTrue(d["blocked"], d)

    def test_that_raise_only_skips_a_preview_run(self):
        d = gate.decide(will_upload=False, gate_on=True, verdict=None,
                        error="cadence probe produced no measurement")
        self.assertFalse(d["blocked"], d)


class TheFixIsWhereItSaysItIs(unittest.TestCase):
    def test_review_video_calls_the_check_before_the_judge(self):
        import ast
        src = (ROOT / "scripts" / "showrunner_review.py").read_text()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "review_video")
        order = [(n.lineno, n.func.id if isinstance(n.func, ast.Name)
                  else getattr(n.func, "attr", ""))
                 for n in ast.walk(fn) if isinstance(n, ast.Call)]
        checked = [ln for ln, name in order if name == "temporal_unmeasured"]
        judged = [ln for ln, name in order if name == "_judge"]
        self.assertTrue(checked, "review_video no longer checks the probe")
        self.assertTrue(judged)
        self.assertLess(min(checked), min(judged),
                        "the check must run before the vision spend")


if __name__ == "__main__":
    unittest.main()
