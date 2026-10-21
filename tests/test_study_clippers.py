"""The clipper study reads a channel's numbers right (scripts/study_clippers.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "scripts"))

import study_clippers as s  # noqa: E402


class ReadsDurations(unittest.TestCase):
    def test_iso_durations(self):
        self.assertEqual(s.iso_seconds("PT45S"), 45)
        self.assertEqual(s.iso_seconds("PT1M5S"), 65)
        self.assertEqual(s.iso_seconds("PT2H"), 7200)
        self.assertEqual(s.iso_seconds("P1DT1S"), 86401)
        self.assertEqual(s.iso_seconds(""), 0)

    def test_best_and_worst_never_overlap(self):
        ranked = [{"id": str(i)} for i in range(7)]
        ids = [v["id"] for v in s.pick_studied(ranked, 10, 4)]
        self.assertEqual(ids, [str(i) for i in range(7)])
        ids = [v["id"] for v in s.pick_studied(ranked, 3, 2)]
        self.assertEqual(ids, ["0", "1", "2", "5", "6"])

    def test_transcript_reads_clip_edit_words(self):
        """clip_edit hands back {w, s, e}; the first study read "word" and
        "start" and wrote sixteen blank transcripts."""
        words = [{"w": "he", "s": 1.0, "e": 1.2},
                 {"w": "fell.", "s": 1.2, "e": 1.5},
                 {"w": "No", "s": 3.0, "e": 3.2}]
        self.assertEqual(s.transcript_lines(words),
                         ["[  1.0] he fell.", "[  3.0] No"])

    def test_calibration_ranks_scores_against_views(self):
        studied = [{"views": v, "critic": {"story_score": sc, "publish": p}}
                   for v, sc, p in [(100, 90, True), (50, 70, False),
                                    (10, 40, False), (5, 30, False)]]
        studied.append({"views": 1, "critic": {"story_score": -1}})
        c = s.calibration(studied)
        self.assertEqual(c["judged"], 4)
        self.assertEqual(c["would_publish"], 1)
        self.assertEqual(c["score_vs_views"], 1.0)

    def test_calibration_counts_each_rubric_by_group(self):
        studied = [
            {"views": 900, "group": "top", "critics": {
                "narrative": {"story_score": 40, "publish": False},
                "audience": {"story_score": 85, "publish": True}}},
            {"views": 9, "group": "ours", "critics": {
                "narrative": {"story_score": 70, "publish": False},
                "audience": {"story_score": 30, "publish": False}}},
            {"views": 5, "group": "ours", "critics": {
                "audience": {"story_score": 20, "publish": False}}}]
        a = s.calibration(studied, "audience")
        self.assertEqual(a["publish_by_group"], {"ours": "0/2", "top": "1/1"})
        self.assertEqual(a["score_vs_views"], 1.0)
        self.assertEqual(s.calibration(studied, "narrative")["judged"], 2)

    def test_both_rubrics_are_real(self):
        from third_capture import story_director as sd
        self.assertEqual(set(s.RUBRICS), set(sd.RUBRICS))
        self.assertIn("premise_at", sd.RUBRICS["audience"])
        # the gate itself is unchanged until calibration says otherwise
        import inspect
        sig = inspect.signature(sd.review_rough_cut)
        self.assertEqual(sig.parameters["rubric"].default, "narrative")

    def test_it_never_uploads(self):
        src = (ROOT / "scripts" / "study_clippers.py").read_text()
        wf = (ROOT / ".github" / "workflows" / "study-clippers.yml").read_text()
        self.assertNotIn("uploaders", src)
        self.assertNotIn("YOUTUBE_TOKEN", wf)
        # the brain is handed over only when a run asks to judge
        self.assertIn("inputs.judge && secrets.CLAUDE_CODE_OAUTH_TOKEN", wf)


if __name__ == "__main__":
    unittest.main()
