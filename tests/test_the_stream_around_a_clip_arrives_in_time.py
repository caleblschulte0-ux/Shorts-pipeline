"""The minutes around a clip have to ARRIVE, or no story can be repaired.

Story backtest 2026-10-07: the critic refused cut after cut for a setup or
payoff the 30-second clips never contained ("nothing explains how the bag
got into the sewer"). The VOD window that recovers them was re-encoded on
the runner and ran into the 300s timeout (`TimeoutExpired`, twice on one
video), so the stories that most needed it never got it.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from third_capture import clip_edit


class TheVodWindowIsAStreamCopy(unittest.TestCase):
    def _fetch(self):
        calls = []

        def fake(args, *, impersonate=False, timeout=clip_edit._RUN_TIMEOUT):
            calls.append((args, timeout))
            out = Path(args[args.index("-o") + 1])
            out.write_bytes(b"\0" * 20_000)
            return ""

        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(clip_edit, "_ytdlp", side_effect=fake):
            got = clip_edit.maybe_vod_window(
                {"video_id": "123", "vod_offset": 600, "duration": 30}, td)
        return got, calls

    def test_it_copies_the_stream_instead_of_re_encoding(self):
        got, calls = self._fetch()
        self.assertIsNotNone(got)
        args, _ = calls[0]
        self.assertNotIn("--recode-video", args)
        self.assertNotIn("--force-keyframes-at-cuts", args)
        self.assertIn("--remux-video", args)

    def test_it_gets_longer_than_a_single_clip_download(self):
        _, calls = self._fetch()
        self.assertGreater(calls[0][1], clip_edit._RUN_TIMEOUT)

    def test_the_window_is_where_the_clip_is(self):
        got, _ = self._fetch()
        self.assertEqual(got["vod_start_s"], 540.0)
        self.assertEqual(got["clip_offset_s"], 60.0)


class EnoughWindowsAreFetched(unittest.TestCase):
    def test_the_channel_allows_more_than_two(self):
        import json
        spec = json.loads(Path("state/third_packages/default_clip.json")
                          .read_text())["capture"]
        self.assertGreaterEqual(spec.get("story_max_vod_expansions", 2), 4)


if __name__ == "__main__":
    unittest.main()
