"""Baller Bro posted nothing from 2026-11-18 to 11-23, and what it posted
the week before was mostly not the channel (operator, 2026-11-23: "what
the fuck is going on here? ... have you watched the last videos?").

- Reddit refused every discovery route (API 403, feed 404/429, PullPush
  429), ~30 runs failed at step one, and the health check stayed quiet
  because it only read runs that made cuts. Discovery now has Arctic
  Shift, old.reddit's feed and a wait on 429; the health check goes red
  when nothing has posted for SILENT_H hours.
- With the picker down, `who` fell back to the subreddit and two titles
  posted as "Nba: ..." / "Nfl: ...".
- Two posts were another channel's finished edit (burned-in captions
  under ours); one was 32 seconds of two talking heads with nothing shown;
  one ran 14.8s under a 15s floor.
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# APPEND, never insert at 0: `scripts/test_exchange.py` shadows
# `tests/test_exchange.py` the moment scripts/ sits ahead of tests/, and this
# module sorts before `test_exchange`, so `unittest discover -s tests` died
# at import on main from 2026-11-23 (#773) until this line changed.
sys.path.append(str(ROOT / "scripts"))

from funnel import hot_clips  # noqa: E402


def _post(i, score, comments=0, url="https://v.redd.it/x"):
    return {"id": str(i), "title": f"post {i}", "score": score,
            "num_comments": comments, "url": f"{url}{i}",
            "permalink": f"/r/nfl/comments/{i}/p/",
            "created_utc": time.time() - 3600 * i}


class DiscoveryHasARouteReddit_DoesNotBlock(unittest.TestCase):

    def setUp(self):
        hot_clips._DEAD.clear()

    def test_arctic_shift_is_ranked_most_upvoted_first(self):
        page = {"data": [_post(1, 5), _post(2, 900, 40), _post(3, 50)]}
        with mock.patch.object(hot_clips, "_fetch",
                               return_value=json.dumps(page).encode()):
            got = hot_clips._arctic("week", 50, "nfl")
        scores = [k["data"]["score"] for k in got["data"]["children"]]
        self.assertEqual(scores, [900, 50, 5])

    def test_when_api_and_pullpush_refuse_arctic_answers(self):
        page = {"data": [_post(1, 10), _post(2, 300)]}
        with mock.patch.object(hot_clips, "_get", return_value=None), \
                mock.patch.object(hot_clips, "_pullpush", return_value=None), \
                mock.patch.object(hot_clips, "_rss", return_value=None), \
                mock.patch.object(hot_clips, "_fetch",
                                  return_value=json.dumps(page).encode()):
            vids = hot_clips.top_videos("nfl")
        self.assertEqual(len(vids), 2)
        self.assertEqual(vids[0]["upvotes"], 300)

    def test_every_route_runs_on_its_own_code(self):
        """2026-11-24: _pullpush shadowed `urllib` with a local import and
        crashed every run; the route tests above mocked it out. Each
        route here runs its real body against a stubbed fetch."""
        page = {"data": [_post(1, 10)]}
        raw = json.dumps(page).encode()
        with mock.patch.object(hot_clips, "_fetch", return_value=raw):
            self.assertTrue(hot_clips._pullpush(None, "week", 50, "nfl"))
            self.assertTrue(hot_clips._arctic("week", 50, "nfl"))
        atom = (b'<feed><entry><title>t</title><link href="https://www.'
                b'reddit.com/r/nfl/comments/1/t/"/><updated>2026-11-20T00:'
                b'00:00+00:00</updated></entry></feed>')
        with mock.patch.object(hot_clips, "_fetch", return_value=atom):
            got = hot_clips._rss("/r/nfl/top.json?t=week", "nfl")
        self.assertEqual(len(got["data"]["children"]), 1)

    def test_a_crashing_route_does_not_end_discovery(self):
        page = {"data": [_post(1, 10)]}
        with mock.patch.object(hot_clips, "_get", return_value=None), \
                mock.patch.object(hot_clips, "_pullpush",
                                  side_effect=UnboundLocalError("urllib")), \
                mock.patch.object(hot_clips, "_fetch",
                                  return_value=json.dumps(page).encode()):
            self.assertEqual(len(hot_clips.top_videos("nfl")), 1)

    def test_arctic_is_tried_before_the_feed(self):
        src = Path(hot_clips.__file__).read_text()
        body = src[src.index("def _first("):]
        self.assertLess(body.index('"arctic"'), body.index('"rss"'))


class SilenceTurnsTheHealthCheckRed(unittest.TestCase):

    def test_six_quiet_days_is_a_problem(self):
        import sports_health as h
        log = {"posted": [{"format": "sports_moment",
                           "posted_at": "2026-11-17T20:48:59Z"}]}
        now = time.mktime(time.strptime("2026-11-23 23:00",
                                        "%Y-%m-%d %H:%M"))
        found = h.silence(log, now=now)
        self.assertEqual(len(found), 1)
        self.assertIn("nothing posted", found[0])

    def test_a_post_today_is_fine(self):
        import sports_health as h
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log = {"posted": [{"format": "sports_moment", "posted_at": stamp}]}
        self.assertEqual(h.silence(log), [])

    def test_other_channels_posts_do_not_count(self):
        import sports_health as h
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log = {"posted": [{"format": "explainer", "posted_at": stamp},
                          {"format": "sports_moment",
                           "posted_at": "2026-11-01T00:00:00Z"}]}
        self.assertTrue(h.silence(log))

    def test_main_reads_the_posted_log(self):
        src = (ROOT / "scripts" / "sports_health.py").read_text()
        main = src[src.index("def main("):]
        self.assertIn("silence(", main)


class NeverASubredditAsAName(unittest.TestCase):

    def test_who_comes_from_the_post_title(self):
        import sports_samples as ss
        self.assertEqual(ss.who_in({"post_title": "Keyshawn Bryant jumps "
                                    "right over him", "sub": "nba"}),
                         "Keyshawn Bryant")
        self.assertEqual(ss.who_in({"post_title": "what a play",
                                    "sub": "nba"}), "")

    def test_the_fallback_never_uses_the_sub(self):
        import sports_samples as ss
        pool = [{"sub": "nba", "upvotes": 9, "platform": "reddit",
                 "url": "u1", "post_title": "Rick Carlisle calls LeBron "
                 "an AI machine"}]
        with mock.patch.object(ss, "_brain", return_value=None), \
                mock.patch.object(ss, "in_scope", side_effect=lambda p: p):
            got = ss.pick(pool, 1)
        self.assertEqual(got[0]["who"], "Rick Carlisle")
        src = (ROOT / "scripts" / "sports_samples.py").read_text()
        self.assertNotIn('"who": c["sub"]', src)
        self.assertNotIn('or c["sub"]', src)


class NotSomeoneElsesEditNotATalkingHead(unittest.TestCase):

    def test_burned_in_captions_are_someone_elses_edit_for_good(self):
        import run_sports as rs
        why = rs.someone_elses_edit({"own_captions": True})
        self.assertTrue(why.startswith(rs.FOR_GOOD))
        self.assertEqual(rs.someone_elses_edit({"own_captions": False}), "")

    def test_a_talking_head_with_nothing_shown(self):
        import run_sports as rs
        self.assertTrue(rs.talking_head({"talking": True, "cut_in": [],
                                         "outro": None}))
        self.assertFalse(rs.talking_head({"talking": True,
                                          "cut_in": ["LeBron@4.0"]}))
        self.assertFalse(rs.talking_head({"talking": True,
                                          "outro": {"secs": 6}}))
        self.assertFalse(rs.talking_head({"talking": False}))

    def test_both_are_checked_before_the_judge(self):
        src = (ROOT / "scripts" / "run_sports.py").read_text()
        run = src[src.index("made = ss.make(c, info, mp4)"):]
        self.assertLess(run.index("someone_elses_edit("),
                        run.index("judge(mp4"))
        self.assertLess(run.index("talking_head("), run.index("judge(mp4"))

    def test_the_ledger_carries_what_the_checks_read(self):
        src = (ROOT / "scripts" / "sports_samples.py").read_text()
        self.assertIn('"own_captions"', src)
        self.assertIn('"talking": talk', src)


class TheFloorIsTheFloor(unittest.TestCase):

    def test_fourteen_point_eight_is_under_fifteen(self):
        from shared import sports_scope as sc
        self.assertTrue(sc.too_short(14.8))
        self.assertEqual(sc.too_short(15.0), "")


if __name__ == "__main__":
    unittest.main()
