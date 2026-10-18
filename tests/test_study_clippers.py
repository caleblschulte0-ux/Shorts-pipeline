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

    def test_it_never_uploads(self):
        src = (ROOT / "scripts" / "study_clippers.py").read_text()
        wf = (ROOT / ".github" / "workflows" / "study-clippers.yml").read_text()
        self.assertNotIn("uploaders", src)
        self.assertNotIn("YOUTUBE_TOKEN", wf)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", wf)


if __name__ == "__main__":
    unittest.main()
