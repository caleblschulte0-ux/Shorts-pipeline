"""Operator, 2026-10-14: "We need to be making sure things are posting at
proper times we can't drop 3 videos in 2 hours".

That day the explainer went live at 15:50Z (a mailbox ship, public on
upload), 16:20Z (a run's "an hour from now", picked at run start and passed
by the time it uploaded) and 17:23Z (an earlier run's scheduled slot). Every
upload path now takes its time from shared/post_spacing, against the posted
log, with the registry's gap.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from shared import channel_registry, post_spacing as ps


def Z(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


#: the explainer's posted log as it stood when the 16:20 video uploaded
EXPLAINER_LOG = {"posted": {
    "plane-tickets": {"title": "Why Plane Tickets Cost More",
                      "at": "2026-10-14T11:41:34+00:00",
                      "publish_at": "2026-10-14T11:23:36Z", "state": "posted"},
    "penny": {"title": "Every Penny", "at": "2026-10-14T13:32:54+00:00",
              "publish_at": "2026-10-14T17:23:36Z", "state": "posted"},
    "back-pain": {"title": "Back Pain", "at": "2026-10-14T15:50:13Z",
                  "publish_at": None, "state": "posted",
                  "via": "showrunner-rejudge"},
}}


class TheRegistryOwnsTheGap(unittest.TestCase):
    def test_every_enabled_channel_has_a_gap(self):
        for cid in channel_registry.channel_ids():
            self.assertGreater(ps.min_gap(cid), timedelta(0), cid)

    def test_explainer_and_baller_bro_are_three_hours_apart(self):
        self.assertEqual(ps.min_gap("explainer"), timedelta(hours=3))
        self.assertEqual(ps.min_gap("trending"), timedelta(hours=3))

    def test_third_keeps_its_ninety_minute_slots(self):
        self.assertEqual(ps.min_gap("third"), timedelta(minutes=90))


class TheMorningOf20261014(unittest.TestCase):
    def test_a_late_run_does_not_land_between_two_posts(self):
        now = Z("2026-10-14T16:37:00Z")
        got = ps.schedule("explainer", EXPLAINER_LOG,
                          want=Z("2026-10-14T16:20:57Z"), now=now)
        self.assertIsNotNone(got)
        for x in ps.taken(EXPLAINER_LOG, now=now):
            self.assertGreaterEqual(abs(Z(got) - x), timedelta(hours=3), got)
        self.assertEqual(got, "2026-10-14T20:23:36Z")

    def test_a_mailbox_ship_waits_for_the_next_free_time(self):
        log = {"posted": {k: v for k, v in EXPLAINER_LOG["posted"].items()
                          if k != "back-pain"}}
        got = ps.schedule("explainer", log, now=Z("2026-10-14T15:50:00Z"))
        self.assertEqual(got, "2026-10-14T20:23:36Z")

    def test_a_clear_hour_still_posts_now(self):
        log = {"posted": {"plane-tickets": EXPLAINER_LOG["posted"]["plane-tickets"]}}
        self.assertIsNone(ps.schedule("explainer", log,
                                      now=Z("2026-10-14T15:00:00Z")))

    def test_a_planned_time_that_is_clear_is_kept(self):
        got = ps.schedule("explainer", {"posted": {}},
                          want=Z("2026-10-14T18:00:00Z"),
                          now=Z("2026-10-14T12:00:00Z"))
        self.assertEqual(got, "2026-10-14T18:00:00Z")


class BallerBroTakesTheNextFreeSlot(unittest.TestCase):
    SLOTS = [(11, 0), (15, 0), (19, 0)]

    def test_a_slot_a_catch_up_post_crowds_is_skipped(self):
        from scripts import run_sports
        now = Z("2026-10-14T15:30:00Z")
        log = {"posted": [{"title": "caught up", "publish_at": None,
                           "posted_at": "2026-10-14T15:20:00Z"}]}
        self.assertEqual(run_sports.next_slot(self.SLOTS, now=now, log=log),
                         "2026-10-14T20:00:00Z")

    def test_a_second_run_does_not_reuse_a_claimed_slot(self):
        from scripts import run_sports
        now = Z("2026-10-14T12:00:00Z")
        log = {"posted": [{"title": "a", "publish_at": "2026-10-14T16:00:00Z",
                           "posted_at": "2026-10-14T01:00:00Z"}],
               "uploads": [{"title": "a", "claimed_at": "2026-10-14T00:58:00Z",
                            "state": "posted"}]}
        self.assertEqual(run_sports.next_slot(self.SLOTS, now=now, log=log),
                         "2026-10-14T20:00:00Z")

    def test_a_scheduled_claim_counts_at_its_go_live_time(self):
        log = {"posted": [{"title": "a", "publish_at": "2026-10-14T16:00:00Z",
                           "posted_at": "2026-10-14T01:00:00Z"}],
               "uploads": [{"title": "a", "claimed_at": "2026-10-14T00:58:00Z",
                            "state": "posted"}]}
        self.assertEqual(ps.taken(log, now=Z("2026-10-14T12:00:00Z")),
                         [Z("2026-10-14T16:00:00Z")])


class EveryUploadPathAsks(unittest.TestCase):
    """A path that picks its own time is how the bunching happened."""

    def _src(self, path):
        from pathlib import Path
        return (Path(__file__).resolve().parents[1] / path).read_text()

    def test_the_paths_call_post_spacing(self):
        for path in ("scripts/post_stories.py", "scripts/claim_reviews.py",
                     "scripts/run_sports.py", "scripts/run_third.py"):
            self.assertIn("post_spacing", self._src(path), path)

    def test_the_mailbox_never_posts_public_regardless(self):
        self.assertNotIn("publish_at=None", self._src("scripts/claim_reviews.py"))


if __name__ == "__main__":
    unittest.main()
