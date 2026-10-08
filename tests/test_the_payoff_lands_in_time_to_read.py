"""Operator, 2026-10-07, of the bird flu video's closing: "the picket fence
at the end is already hard to understand, then we only have it on screen for
like a second ... it's like whiplash, I didn't even have time to process.
Now I'm not saying we necessarily need to be sitting on beats longer, but we
need to fix this."

Its last number arrived at 78% of a four-second scene. Two things let that
through: every scene taught the brain to finish its story near the end, and
the checks thought a beat was ten seconds long. Held here: a scene's whole
payoff is up by `land_by(secs)` of its REAL length and holds to the end; a
readout steps through at most READOUT_SHOWS values; a scene saved before the
rule is redrawn, not replayed; and the lengths match the posted log."""
import inspect
import json
import statistics
import unittest
from pathlib import Path
from unittest import mock

from tests.test_the_brain_draws_the_scene import GOOD_MIN, HAVE_CAIRO

ROOT = Path(__file__).resolve().parents[1]
PTS = [["2019", 1.05], ["2025", 4.41]]

#: the fence's shape: the finished number arrives at u=0.8
LATE = GOOD_MIN.replace(
    "lab, val = rows[-1]",
    "lab, val = rows[-1] if u >= 0.8 else rows[0]")


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheFinishedPictureIsUpLongEnoughToRead(unittest.TestCase):

    def test_a_number_that_lands_at_the_end_is_refused(self):
        from data_learning import scene_author as SA
        ps = SA.verify(SA.compile_scene(LATE), PTS)
        self.assertTrue(any("only lands at u=0.80" in p for p in ps), ps)

    def test_a_payoff_up_from_the_start_passes(self):
        from data_learning import scene_author as SA
        self.assertEqual(SA.payoff_problems(SA.compile_scene(GOOD_MIN), PTS), [])

    def test_a_shorter_scene_must_land_sooner(self):
        from data_learning import scene_author as SA
        self.assertLess(SA.land_by(4.0), SA.land_by(6.0) + 1e-9)
        self.assertGreaterEqual((1 - SA.land_by(4.0)) * 4.0, SA.READ_S - 1e-9)

    def test_the_closing_teachers_land_in_time(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        import tests.test_subject_scenes as T
        for slug, (fn0, idx) in SS.CLOSINGS.items():
            with self.subTest(closing=fn0.__name__):
                fn = SA.compile_scene(inspect.getsource(fn0).replace(
                    f"def {fn0.__name__}(", "def scene("))
                self.assertEqual(SA.payoff_problems(
                    fn, T._beats(slug)[idx], SA.SCENE_SECS["closing"]), [])

    def test_a_saved_late_scene_is_redrawn_not_replayed(self):
        from data_learning import scene_author as SA
        from shared import rewrite_mailbox as RW
        data = {"points": [{"label": l, "value": v} for l, v in PTS]}
        story = {"closing_scene": LATE, "closing_data": 0, "segments": [{}]}
        with mock.patch.object(RW, "_dataset", return_value=data), \
                mock.patch.object(SA, "craft_problems", return_value=[]):
            self.assertIsNone(SA.saved_closing(story, 1, log=lambda m: None))
            story["closing_scene"] = GOOD_MIN
            self.assertIsNotNone(SA.saved_closing(story, 1, log=lambda m: None))

    def test_the_brain_is_told(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "x", "y", PTS, "", secs=4.0)
        self.assertIn("LAND IT, THEN HOLD IT", p)
        self.assertIn(f"by u={SA.land_by(4.0):.2f}", p)


class AReadoutStepsThroughFewValues(unittest.TestCase):

    def test_seven_rows_show_three_values(self):
        from data_learning import subject_scenes as SS
        rows = [(str(2000 + i), float(i)) for i in range(7)]
        seen = {SS.landed(rows, k, 1.0)[0] for k in range(7)}
        self.assertLessEqual(len(seen), SS.READOUT_SHOWS)
        self.assertEqual(SS.landed(rows, 6, 1.0), rows[-1])


class TheLengthsAreTheRealOnes(unittest.TestCase):
    """SCENE_SECS must not claim more time than a posted video gave."""

    def test_no_kind_is_longer_than_its_posted_median(self):
        from data_learning import scene_author as SA
        path = ROOT / "state" / "explainer_posted_log.json"
        log = json.loads(path.read_text()) if path.exists() else {}
        posted = (log.get("posted") or {}) if isinstance(log, dict) else {}
        # beat_s_max is each video's LONGEST beat: a beat budget above its
        # median would hand most videos time they never had
        beats = [e["beat_s_max"] for e in posted.values()
                 if isinstance(e, dict) and e.get("beat_s_max")]
        if len(beats) < 3:
            self.skipTest("too few posted beats to judge")
        self.assertLessEqual(SA.SCENE_SECS["beat"], statistics.median(beats) + 1e-9)
        self.assertLessEqual(SA.SCENE_SECS["closing"], SA.SCENE_SECS["beat"])


if __name__ == "__main__":
    unittest.main()
