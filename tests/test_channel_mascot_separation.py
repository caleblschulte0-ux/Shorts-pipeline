"""Regression tests for the 2026-08-03 channel-brand correction.

Added by ChatGPT. Data belongs to Explainer only; Trending renderers must not
load or composite the Explainer mascot.
"""

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


class TestChannelMascotSeparation(unittest.TestCase):
    def test_trending_renderers_do_not_import_data_mascot(self):
        for rel in ("engines/chart_race.py", "make_reddit_story.py"):
            source = (REPO / rel).read_text()
            self.assertNotIn("assets/mascot/host", source, rel)
            self.assertNotIn("mascot_dir", source, rel)

    def test_reddit_contract_does_not_request_mascot_pose(self):
        registry = json.loads(
            (REPO / "config/channel_registry.json").read_text())
        fields = registry["channels"]["trending"]["formats"]["reddit_story"][
            "media"]["per_shot"]
        self.assertEqual(fields, ["phrase", "query"])

    def test_explainer_still_owns_its_mascot(self):
        source = (REPO / "make_explainer_stacked.py").read_text()
        self.assertIn('assets" / "mascot" / "anchor', source)


if __name__ == "__main__":
    unittest.main()
