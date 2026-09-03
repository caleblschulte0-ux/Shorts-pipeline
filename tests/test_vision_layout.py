"""Regression tests for the ChatGPT 2026-08-02 Reddit layout repair."""

import unittest

from funnel.gemini_images import _vision_layout


class TestVisionLayoutContract(unittest.TestCase):
    def test_illustrated_reddit_describes_both_real_halves(self):
        prompt = _vision_layout("reddit_illustrated")
        self.assertIn("TOP half is a story illustration", prompt)
        self.assertIn("BOTTOM half is gameplay", prompt)

    def test_gameplay_card_does_not_require_a_news_photo(self):
        prompt = _vision_layout("reddit_gameplay_card")
        self.assertIn("does NOT require a news photo", prompt)

    def test_default_layout_preserves_the_existing_stacked_contract(self):
        prompt = _vision_layout("stacked")
        self.assertIn("TOP half is a news/stock photo", prompt)
        self.assertIn("BOTTOM half is an abstract game animation", prompt)


if __name__ == "__main__":
    unittest.main()
