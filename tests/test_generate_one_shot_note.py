"""Doctor e61446f7bc2a: a one-shot package passes QA, so the success log
must not index shots[1].

    python -m unittest tests.test_generate_one_shot_note -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class OneShotNote(unittest.TestCase):
    def test_note_is_bounds_safe(self):
        from data_learning import generate
        self.assertEqual(generate.chart_note_for({"shots": [{"phrase": "a"}]}), "no chart")
        self.assertEqual(generate.chart_note_for({"shots": [{"image_url": "x"}]}), "with chart")
        self.assertEqual(generate.chart_note_for({"shots": [{}, {"image_url": "x"}]}), "with chart")
        self.assertEqual(generate.chart_note_for({}), "no chart")

    def test_no_unconditional_second_shot_read(self):
        self.assertNotIn('["shots"][1]', (ROOT / "data_learning" / "generate.py").read_text())


if __name__ == "__main__":
    unittest.main()
