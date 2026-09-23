"""THE SOURCES LIVE IN THE DESCRIPTION; THE SCREEN SAYS WHERE.

History, because each step was a real frame:

  * the CTA was printed on top of a four-line citation (self-checkout-cashier-
    jobs, 2026-09-09), so the strip was bounded to one line at fs15;
  * at fs15 the judge failed it as "microscopic grey text you cannot read on
    a phone", and at fs24 within 80 characters as "tiny ... cut off at
    'compiled fro...'" — `unreadable`, on videos that otherwise scored 74
    (2026-09-23).

The foot band (1683..1920) has room for one short line under the question and
the CTA. So the screen now carries one line a phone can read — "Sources in
the description" — and the full citation (publisher, dataset, link, access
date) goes into the upload description, where nothing is truncated.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
sys.path.append(str(_REPO / "scripts"))

from data_learning import studio_render as sr   # noqa: E402


class TheScreenCarriesOneReadableLine(unittest.TestCase):
    def test_it_is_short_and_big_enough_to_read(self):
        self.assertLessEqual(len(sr.SRC_TEXT), 40)
        self.assertGreaterEqual(sr.SRC_FS, 24)
        self.assertIn("description", sr.SRC_TEXT.lower())

    def test_the_dialogue_cannot_wrap(self):
        import inspect
        src = inspect.getsource(sr)
        i = src.index("src_txt = (")
        self.assertIn("\\q2", src[i:i + 400], "the sources line can still wrap")
        self.assertIn("SRC_TEXT", src[i:i + 400])


class TheDescriptionCarriesTheFullCitation(unittest.TestCase):
    def test_every_dataset_publisher_link_and_date_is_listed(self):
        import post_stories as ps
        cfg = json.loads((_REPO / "data_learning" / "niche.config.json").read_text())
        sc = next(x for x in cfg["stories"] if x["slug"] == "amazon-still-shrinking")
        block = ps._sources_block(sc)
        self.assertTrue(block.startswith("Sources:"))
        for pub in ("INPE", "Mongabay", "Yale School of the Environment"):
            self.assertIn(pub, block)
        self.assertIn("https://", block)
        self.assertIn("accessed", block)
        self.assertNotIn("…", block)

    def test_the_description_includes_it(self):
        import post_stories as ps
        cfg = json.loads((_REPO / "data_learning" / "niche.config.json").read_text())
        sc = next(x for x in cfg["stories"] if x["slug"] == "amazon-still-shrinking")
        self.assertIn(ps._sources_block(sc), ps._description(sc))

    def test_a_story_without_datasets_is_not_an_error(self):
        import post_stories as ps
        self.assertEqual(ps._sources_block({"segments": [{}]}), "")


if __name__ == "__main__":
    unittest.main()
