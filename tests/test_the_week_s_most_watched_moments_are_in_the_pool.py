"""Operator, 2026-10-13: "the clips are trash and its not our editor its
the clips at there raw". The followed streamers' own top clips are often
their least boring minute, and Reddit refuses the runner most days. Twitch's
own category charts (the week's most-watched clips in Just Chatting, GTA V
and IRL, from any streamer) join the story pool every run."""
import inspect
import unittest
from unittest import mock

from third_capture import clip_edit


class _R:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self._d}


def _clip(i, views):
    return {"id": f"slug{i}", "url": f"https://clips.twitch.tv/slug{i}",
            "view_count": views, "duration": 30, "title": f"t{i}",
            "broadcaster_name": "SomeOne", "created_at":
            "2026-10-10T12:00:00Z", "vod_offset": 100, "video_id": "9",
            "game_id": "509658"}


class TheCategoryChartsAreRead(unittest.TestCase):

    def test_each_category_is_asked_for_its_week(self):
        calls = []

        def get(url, params=None, **k):
            calls.append(params)
            return _R([_clip(len(calls), 90000)])
        with mock.patch.object(clip_edit, "_helix_creds",
                               return_value=("a", "b")), \
                mock.patch.object(clip_edit, "_helix_headers",
                                  return_value={}), \
                mock.patch("requests.get", side_effect=get):
            got = clip_edit.top_by_category(["509658", "32982"], top=10)
        self.assertEqual([c["game_id"] for c in calls], ["509658", "32982"])
        self.assertTrue(all("started_at" in c for c in calls))
        self.assertEqual(len(got), 2)
        g = got[0]
        self.assertEqual(g["channel"], "someone")
        self.assertEqual(g["views"], 90000)
        self.assertEqual((g["video_id"], g["vod_offset"]), ("9", 100))
        self.assertEqual(g["category_top"], "Just Chatting")

    def test_no_credentials_is_no_harm(self):
        with mock.patch.object(clip_edit, "_helix_creds", return_value=None):
            self.assertEqual(clip_edit.top_by_category(), [])

    def test_a_failing_category_does_not_lose_the_others(self):
        n = []

        def get(url, params=None, **k):
            n.append(1)
            if len(n) == 1:
                raise RuntimeError("down")
            return _R([_clip(2, 5000)])
        with mock.patch.object(clip_edit, "_helix_creds",
                               return_value=("a", "b")), \
                mock.patch.object(clip_edit, "_helix_headers",
                                  return_value={}), \
                mock.patch("requests.get", side_effect=get):
            got = clip_edit.top_by_category(["1", "2"])
        self.assertEqual(len(got), 1)


class TheStoryPoolReadsThem(unittest.TestCase):

    def test_run_third_adds_them_to_the_pool(self):
        import scripts.run_third as rt
        self.assertIn("clip_edit.top_by_category(", inspect.getsource(rt))


if __name__ == "__main__":
    unittest.main()
