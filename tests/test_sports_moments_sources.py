"""Baller Bro's sports moments are read off the sports subreddits the way
the Twitch channel reads r/LivestreamFail (operator, 2026-10-11: the OG
channel "we need to turn that into something", then "sports moments").

`hot_clips.top_videos` keeps only posts that link to footage, drops NSFW
and removed posts, ranks by upvotes, and hands a Reddit-hosted video's
v.redd.it address on as `media`, which `reddit_video.fetch` reads when
reddit.com refuses the runner.
"""
import unittest
from unittest import mock

from funnel import hot_clips, reddit_video


def _listing(*posts):
    return {"data": {"children": [{"data": p} for p in posts]}}


class TopVideos(unittest.TestCase):
    def test_keeps_footage_ranked_and_carries_the_cdn_address(self):
        posts = _listing(
            {"title": "Fan catches a foul ball in his beer",
             "url": "https://v.redd.it/abc123", "ups": 900,
             "permalink": "/r/baseball/comments/x1/fan/"},
            {"title": "Coach loses it at the ref",
             "url": "https://streamable.com/qwe", "ups": 4000,
             "permalink": "/r/nba/comments/x2/coach/"},
            {"title": "Box score thread", "url": "https://espn.com/a",
             "ups": 9000, "permalink": "/r/nba/comments/x3/box/"},
            {"title": "nsfw", "url": "https://v.redd.it/zzz", "ups": 1,
             "over_18": True, "permalink": "/r/nba/comments/x4/n/"},
            {"title": "gone", "url": "https://streamable.com/r",
             "ups": 50, "removed_by_category": "moderator",
             "permalink": "/r/nba/comments/x5/g/"})
        with mock.patch.object(hot_clips, "_first",
                               return_value=posts) as first:
            got = hot_clips.top_videos("sports")
        self.assertIn("/r/sports/top.json", first.call_args[0][0])
        self.assertEqual([g["post_title"] for g in got],
                         ["Coach loses it at the ref",
                          "Fan catches a foul ball in his beer"])
        reddit = got[1]
        self.assertEqual(reddit["platform"], "reddit")
        self.assertEqual(reddit["media"], "https://v.redd.it/abc123")
        self.assertEqual(reddit["sub"], "sports")
        self.assertEqual(got[0]["media"], got[0]["url"])

    def test_unreachable_reddit_is_an_empty_pool(self):
        with mock.patch.object(hot_clips, "_first", return_value=None):
            self.assertEqual(hot_clips.top_videos("nba"), [])


class RedditVideo(unittest.TestCase):
    def test_reads_the_cdn_id(self):
        self.assertEqual(reddit_video.video_id("https://v.redd.it/abc123"),
                         "abc123")
        self.assertIsNone(reddit_video.video_id("https://streamable.com/x"))

    def test_not_a_reddit_video_is_none_without_a_request(self):
        with mock.patch.object(reddit_video, "_ffmpeg") as ff:
            self.assertIsNone(reddit_video.fetch("https://x.com/a", "o.mp4"))
        ff.assert_not_called()



class TwoWordNames(unittest.TestCase):
    """A two-word name already in the title is not prefixed again (the
    first samples: "Jaylen Brown: Jaylen Brown Claps Back...")."""

    def test_no_double_name(self):
        from third_capture import author
        t = "Jaylen Brown Claps Back At Anthony Edwards"
        self.assertEqual(author.anchor_streamer(t, "Jaylen Brown"), t)

    def test_missing_name_still_anchored(self):
        from third_capture import author
        self.assertEqual(
            author.anchor_streamer("Claps Back At Ant", "Jaylen Brown"),
            "Jaylen Brown: Claps Back At Ant")
if __name__ == "__main__":
    unittest.main()


class ASurnameIsTheName(unittest.TestCase):
    """2026-10-14: 'Steven Gerrard: Gerrard Fires Back At City Fans' and
    'Alex Ovechkin: Ovechkin's Sons Introduce...' went live."""

    def test_the_surname_becomes_the_full_name_once(self):
        from third_capture import author
        self.assertEqual(
            author.anchor_streamer("Gerrard Fires Back At City Fans",
                                   "Steven Gerrard"),
            "Steven Gerrard Fires Back At City Fans")
        self.assertEqual(
            author.anchor_streamer("Ovechkin's Sons Introduce Their Dad",
                                   "Alex Ovechkin"),
            "Alex Ovechkin's Sons Introduce Their Dad")
        self.assertEqual(
            author.anchor_streamer("Watch Anunoby Cook", "OG Anunoby"),
            "Watch OG Anunoby Cook")
