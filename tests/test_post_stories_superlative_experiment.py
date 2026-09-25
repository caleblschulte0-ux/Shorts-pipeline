"""Doctor finding f6aa3e1f1c66 (ruled `doing` 2026-08-18): superlative-titled
explainer stories measured a 50.1% median average-view-percentage against
29.1% for the rest (state/analytics_explainer/latest.json). This holds the
built experiment's two moving parts — the queue-order treatment and the
analytics tagging it is measured through — so neither regresses silently.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import post_stories as ps  # noqa: E402


class TestSuperlativeClassifier(unittest.TestCase):
    def test_matches_the_evidence_regex_family(self):
        for title in ("The Largest Cities In The World",
                      "Why Is This The Hottest Place On Earth",
                      "The Deepest Point In The Ocean",
                      "The World's Most Dangerous Animal"):
            self.assertTrue(ps._is_superlative_topic(title), title)

    def test_plain_and_finance_titles_do_not_match(self):
        for title in ("Home Prices Are Rising Again",
                      "Why Is America Growing 4 Times More 100-Year-Olds?",
                      "Your Grocery Bill Explained"):
            self.assertFalse(ps._is_superlative_topic(title), title)

    def test_empty_title_is_safe(self):
        self.assertFalse(ps._is_superlative_topic(""))
        self.assertFalse(ps._is_superlative_topic(None))


class TestReserveSuperlativeSlot(unittest.TestCase):
    def _stories(self):
        return {
            "finance-one": {"title": "Grocery Bills Keep Climbing"},
            "superlative-one": {"title": "The Largest Lake On Earth"},
            "finance-two": {"title": "Rent Just Keeps Going Up"},
        }

    def test_promotes_the_first_unposted_superlative_story(self):
        slugs = ["finance-one", "superlative-one", "finance-two"]
        ps._reserve_superlative_slot(slugs, self._stories(), {"posted": {}})
        self.assertEqual(slugs[0], "superlative-one")

    def test_does_not_touch_the_order_with_no_candidate_in_queue(self):
        stories = {"finance-one": {"title": "Grocery Bills Keep Climbing"},
                   "finance-two": {"title": "Rent Just Keeps Going Up"}}
        slugs = ["finance-one", "finance-two"]
        ps._reserve_superlative_slot(slugs, stories, {"posted": {}})
        self.assertEqual(slugs, ["finance-one", "finance-two"])

    def test_does_not_reserve_a_second_slot_once_todays_is_spent(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).isoformat()
        stories = self._stories()
        stories["superlative-two"] = {"title": "The Fastest Animal Alive"}
        slugs = ["finance-one", "superlative-two", "finance-two"]
        log = {"posted": {"superlative-one": {"at": today}}}
        ps._reserve_superlative_slot(slugs, stories, log)
        self.assertEqual(slugs, ["finance-one", "superlative-two",
                                  "finance-two"])

    def test_skips_a_superlative_story_already_posted_today(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).isoformat()
        stories = self._stories()
        stories["superlative-two"] = {"title": "The Fastest Animal Alive"}
        slugs = ["finance-one", "superlative-two", "finance-two"]
        # superlative-one already posted today but isn't in this run's
        # queue — the guard reads the LOG, not queue membership.
        log = {"posted": {"superlative-one": {"at": today}}}
        ps._reserve_superlative_slot(slugs, stories, log)
        self.assertNotEqual(slugs[0], "superlative-two")

    def test_ignores_skipped_log_entries(self):
        log = {"posted": {"superlative-one": {"skipped": True}}}
        slugs = ["finance-one", "superlative-one", "finance-two"]
        ps._reserve_superlative_slot(slugs, self._stories(), log)
        self.assertEqual(slugs[0], "superlative-one")


class TestCreativeFactsTagging(unittest.TestCase):
    def test_tags_the_experiment_arm_from_the_story_title(self):
        facts = ps._creative_facts(
            "slug", {"title": "The Largest Lake On Earth", "segments": []},
            Path("/nonexistent.mp4"), None)
        self.assertEqual(facts["experiment_arm"], "superlative_topic")
        self.assertEqual(facts["actual_structure"], "superlative_topic")

    def test_tags_other_topics_distinctly(self):
        facts = ps._creative_facts(
            "slug", {"title": "Grocery Bills Keep Climbing", "segments": []},
            Path("/nonexistent.mp4"), None)
        self.assertEqual(facts["experiment_arm"], "other_topic")
        self.assertEqual(facts["actual_structure"], "other_topic")


if __name__ == "__main__":
    unittest.main()
