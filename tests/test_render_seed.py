"""Doctor 66d90578bc9b: renderer randomness is reproducible and attributable."""
import re
import unittest
from pathlib import Path

from shared import render_seed

ROOT = Path(__file__).resolve().parent.parent
RENDERERS = ["make_reddit_story.py", "make_text_card.py",
             "make_explainer_stacked.py"]


class Seed(unittest.TestCase):
    def draw(self, ident, attempt):
        render_seed.begin(ident, attempt)
        r = render_seed.rng("p")
        return [r.random() for _ in range(5)]

    def test_same_package_same_attempt_same_plan(self):
        self.assertEqual(self.draw({"a": 1}, 0), self.draw({"a": 1}, 0))

    def test_new_attempt_or_package_changes_plan(self):
        self.assertNotEqual(self.draw({"a": 1}, 0), self.draw({"a": 1}, 1))
        self.assertNotEqual(self.draw({"a": 1}, 0), self.draw({"a": 2}, 0))

    def test_purposes_are_independent(self):
        render_seed.begin("x", 0)
        self.assertNotEqual(render_seed.rng("a").random(),
                            render_seed.rng("b").random())

    def test_manifest_records_choices(self):
        render_seed.begin("x", 3)
        render_seed.note("p", src="a.mp4", seek_s=1.0)
        m = render_seed.manifest()
        self.assertEqual(m["attempt"], 3)
        self.assertEqual(m["choices"][0]["src"], "a.mp4")

    def test_env_attempt(self):
        import os
        os.environ["RENDER_ATTEMPT"] = "7"
        try:
            render_seed.begin("x")
            self.assertEqual(render_seed.manifest()["attempt"], 7)
        finally:
            del os.environ["RENDER_ATTEMPT"]


class Wired(unittest.TestCase):
    def test_renderers_use_no_global_random(self):
        for f in RENDERERS:
            src = (ROOT / f).read_text()
            self.assertIsNone(re.search(r"\brandom\.(choice|uniform|random|randint|shuffle)\(", src), f)
            self.assertIn("render_seed.begin(", src, f)
            self.assertIn("render_seed.manifest()", src, f)


if __name__ == "__main__":
    unittest.main()
