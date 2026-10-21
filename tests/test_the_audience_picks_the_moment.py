"""The audience arm: people pick the moment, measured checks hold the cut.

2026-10-21: both critic rubrics ran AGAINST real views over 26 clips with
known counts, so a cut in this arm is held to what it measures, never to a
critic's score (third_capture/structure_check.py)."""
import ast
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))

from third_capture import structure_check as sc  # noqa: E402


def _led(words, dur, beats=None):
    return {"final_words": [{"w": w, "s": s, "e": e} for w, s, e in words],
            "duration_s": dur,
            "beats": beats or [{"source_id": "hot", "out_start": 0,
                                "out_end": dur}]}


GOOD = [("Wait,", 0.3, 0.6), ("is", 0.6, 0.8), ("this", 0.8, 1.0),
        ("soundproof?", 1.0, 1.6)] + [
    (f"w{i}", 2 + i, 2.5 + i) for i in range(25)] + [("done.", 28, 28.5)]


class MeasuredChecks(unittest.TestCase):
    def test_a_clean_cut_passes(self):
        self.assertEqual(sc.check(_led(GOOD, 30), "hot"), [])

    def test_it_must_open_talking(self):
        late = [(w, s + 4, e + 4) for w, s, e in GOOD]
        self.assertTrue(any("silence" in p
                            for p in sc.check(_led(late, 34), "hot")))

    def test_throat_clearing_is_refused(self):
        w = [("You", 0.2, 0.4), ("know", 0.4, 0.6), ("what", 0.6, 0.8)] \
            + GOOD[3:]
        self.assertTrue(any("filler" in p for p in sc.check(_led(w, 30))))

    def test_dead_air_is_refused(self):
        w = GOOD[:4] + [(x, s + 6, e + 6) for x, s, e in GOOD[4:]]
        self.assertTrue(any("dead air" in p
                            for p in sc.check(_led(w, 36), "hot")))

    def test_it_ends_on_a_finished_sentence(self):
        w = GOOD[:-1] + [("and", 28, 30.0)]
        self.assertTrue(any("mid-sentence" in p
                            for p in sc.check(_led(w, 30), "hot")))

    def test_the_picked_moment_stays_in_and_near_the_end(self):
        self.assertIn("the moment the audience picked is not in the cut",
                      sc.check(_led(GOOD, 30), "other"))
        early = [{"source_id": "hot", "out_start": 0, "out_end": 8},
                 {"source_id": "after", "out_start": 8, "out_end": 30}]
        self.assertTrue(any("trails" in p for p in
                            sc.check(_led(GOOD, 30, early), "hot")))


class AStillOpeningIsRefused(unittest.TestCase):
    """Jynxzi's first cut opened on an idle Xbox screen (mean frame
    difference 0.10); the talking heads that passed sat at 0.40+."""
    def _rows(self, ydif_at):
        return [(i / 30, ydif_at(i / 30)) for i in range(300)]

    def test_a_frozen_stretch_in_the_opening_is_named(self):
        rows = self._rows(lambda t: 0.1 if 4 <= t < 8 else 3.0)
        self.assertAlmostEqual(sc.still_opening(rows), 4.0, delta=0.2)
        self.assertTrue(any("stands still" in p for p in
                            sc.check(_led(GOOD, 30), "hot", rows)))

    def test_a_quiet_talking_head_is_not(self):
        self.assertIsNone(sc.still_opening(self._rows(lambda t: 0.4)))


class LiveCaptionsAreLookedForWhileSomeoneTalks(unittest.TestCase):
    def test_the_story_line_is_placed_from_speech_times(self):
        src = (REPO / "third_capture" / "story.py").read_text()
        self.assertIn("said_at=[w[\"s\"] + 0.3 for w in seg_words]", src)
        ce = (REPO / "third_capture" / "clip_edit.py").read_text()
        self.assertIn("said[::step][:samples]", ce)


class TheArmNeverAsksTheCritic(unittest.TestCase):
    def test_the_audience_branch_continues_before_the_critic(self):
        src = (REPO / "scripts" / "run_third.py").read_text()
        i = src.index("from third_capture import structure_check")
        j = src.index("review = story_director.review_rough_cut(", i)
        branch = src[i:j]
        self.assertIn("continue", branch)
        self.assertNotIn("review_rough_cut", branch)
        # never publishes: nothing it keeps is a pass the channel promotes
        self.assertIn('"publish": False', branch)
        # the director is told the picked clip is the core, kept whole
        self.assertIn("_AUDIENCE_CUT if _audience", src)
        ast.parse(src)


if __name__ == "__main__":
    unittest.main()
