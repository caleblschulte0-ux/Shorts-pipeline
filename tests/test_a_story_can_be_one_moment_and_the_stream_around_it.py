"""A story can be ONE hot moment told with the stream around it.

Four story backtests on 2026-10-07 examined about 150 grouped candidates;
the director called almost all of them "not a story" (two clips of one
stream are usually two unrelated moments, and a scout's saga built from
titles is rarely in the footage). The four cuts that reached the critic
failed on what the clips never contained: the setup and the payoff the
clipper cut off. A moment candidate is the clip plus the BEFORE and AFTER
fetched from its VOD, each its own source; the director and the critic
judge it exactly as they judge any story.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from third_capture import clip_edit, clip_memory, story_director, storyline

from tests.test_a_story_is_repaired_before_it_is_dropped import (
    _Harness, _review)

CLIP = "https://www.twitch.tv/soda/clip/Hot1"


def _pool_item(slug, views, vid="v9", off=600.0, **kw):
    return {"url": f"https://www.twitch.tv/soda/clip/{slug}",
            "channel": "soda", "title": slug, "views": views,
            "video_id": vid, "vod_offset": off, "duration": 30, **kw}


class FindMoments(unittest.TestCase):
    def test_hottest_first_and_only_clips_with_a_vod(self):
        ms = storyline.find_moments([
            _pool_item("A", 50, off=100), _pool_item("B", 900, off=3000),
            {"url": "https://www.twitch.tv/soda/clip/C", "views": 5000}])
        self.assertEqual([m["clips"][0]["title"] for m in ms], ["B", "A"])
        self.assertTrue(all(m["kind"] == "moment" for m in ms))

    def test_never_a_clip_already_posted(self):
        ms = storyline.find_moments([_pool_item("A", 50)],
                                    exclude_keys={"a"})
        self.assertEqual(ms, [])

    def test_one_moment_clipped_twice_is_one_candidate(self):
        ms = storyline.find_moments([_pool_item("A", 50, off=600),
                                     _pool_item("B", 90, off=610)])
        self.assertEqual(len(ms), 1)


MOMENT = {"who": ["soda"], "kind": "moment", "video_id": "v9",
          "score": 900.0,
          "clips": [{"source_url": CLIP, "title": "hot", "channel": "soda",
                     "date": "2026-10-05", "video_id": "v9",
                     "vod_offset": 600.0, "duration": 30.0}]}


class AMomentIsDirectedFromItsBeforeAndAfter(_Harness):
    def _run(self, segment_ok=True):
        import tempfile
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        seg = tmp / "seg.mp4"
        seg.write_bytes(b"x")
        self.segments = []

        def fake_seg(vid, a, b, work):
            self.segments.append((vid, a, b))
            return seg if segment_ok else None
        self.enterContext(mock.patch.object(
            clip_edit, "maybe_vod_segment", side_effect=fake_seg))
        self.enterContext(mock.patch.object(
            storyline, "find_moments", return_value=[]))
        # the harness hands its candidates in through find_vod_arcs; the
        # candidate's KIND is what makes it a moment
        led = self.run_attempt([_review(True, 85)], cluster=MOMENT)
        self.plan_calls = [
            ([r["source_id"] for r in c.args[0]], c.kwargs)
            for c in story_director.plan_story.call_args_list]
        return led

    def test_the_director_sees_before_clip_and_after_in_broadcast_order(self):
        led = self._run()
        self.assertIsNotNone(led, "the critic passed it at 85")
        self.assertEqual([(a, b) for _, a, b in self.segments],
                         [(480.0, 600.0), (630.0, 780.0)])
        srcs, kw = self.plan_calls[0]
        self.assertEqual(srcs, ["vodmine://v9/480-600", CLIP,
                                "vodmine://v9/630-780"])
        self.assertIn("ONE MOMENT", kw.get("moment", ""))

    def test_without_the_vod_it_is_not_padded_into_a_story(self):
        self._run(segment_ok=False)
        self.assertEqual(self.plan_calls, [])
        whys = " ".join(v.get("why", "") for v in self.verdicts())
        self.assertIn("vod_before:unavailable", whys)


if __name__ == "__main__":
    unittest.main()
