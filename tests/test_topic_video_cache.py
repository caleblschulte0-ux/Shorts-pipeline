"""A nonempty file in the media cache is not a valid one.

Doctor finding aab2495524a2. `funnel.topic_video._download` returned any
existing cache entry whose size was above zero, wrote new downloads straight
to the final path, and accepted whatever came back as long as it cleared
10 KB. Three ways that produces a permanently poisoned cache entry:

  * a server that ignores `Range` — the loop stops at the byte cap, mid-atom,
    and the container is unplayable;
  * a process interrupted mid-write — the `except` cleanup only runs if this
    process lives long enough to reach it;
  * any of the above, once, forever: every later call short-circuits on
    `st_size > 0` and never looks again.

The fix is staging plus an actual decode probe, and the probe is tri-state —
"no ffprobe installed" must never read as "corrupt", because refusing every
clip because a tool is missing is a worse failure than the one being caught.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from funnel import topic_video as tv                      # noqa: E402
from shared import video_qa                               # noqa: E402


class TheProbeIsTriState(unittest.TestCase):
    def test_garbage_that_clears_the_size_floor_is_not_decodable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            junk = Path(td) / "clip.mp4"
            junk.write_bytes(b"\x00" * 20_000)     # well over the 10KB floor
            self.assertIs(video_qa.probe_decodable(junk), False)

    def test_a_missing_ffprobe_is_unknown_not_corrupt(self):
        with mock.patch.object(video_qa.shutil, "which", return_value=None):
            self.assertIsNone(video_qa.probe_decodable("anything.mp4"))

    def test_a_probe_timeout_is_unknown_not_corrupt(self):
        with mock.patch.object(video_qa.shutil, "which", return_value="/x"), \
             mock.patch.object(video_qa.subprocess, "run",
                               side_effect=TimeoutError("slow")):
            self.assertIsNone(video_qa.probe_decodable("anything.mp4"))

    def test_a_nonzero_exit_is_corrupt_not_unknown(self):
        """The distinction the old `_ffprobe` helper collapsed: it returns
        None both when the tool is missing and when the file is rejected."""
        done = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(video_qa.shutil, "which", return_value="/x"), \
             mock.patch.object(video_qa.subprocess, "run", return_value=done):
            self.assertIs(video_qa.probe_decodable("anything.mp4"), False)


class TheCacheIsVerifiedNotAssumed(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.dest = Path(self.td.name) / "clip.mp4"

    def test_an_undecodable_cache_entry_is_evicted_not_returned(self):
        self.dest.write_bytes(b"\x00" * 20_000)
        with mock.patch.object(tv, "probe_decodable", return_value=False), \
             mock.patch.object(tv.urllib.request, "urlopen",
                               side_effect=OSError("no network")):
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertIsNone(out, "returned a file it had just judged unusable")
        self.assertFalse(self.dest.exists(), "poisoned entry left in the cache")

    def test_a_good_cache_entry_is_still_a_hit(self):
        self.dest.write_bytes(b"\x00" * 20_000)
        with mock.patch.object(tv, "probe_decodable", return_value=True), \
             mock.patch.object(tv.urllib.request, "urlopen") as opened:
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertEqual(out, self.dest)
        opened.assert_not_called()

    def test_an_unprobeable_cache_entry_is_still_a_hit(self):
        """No ffprobe must not mean no media."""
        self.dest.write_bytes(b"\x00" * 20_000)
        with mock.patch.object(tv, "probe_decodable", return_value=None), \
             mock.patch.object(tv.urllib.request, "urlopen") as opened:
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertEqual(out, self.dest)
        opened.assert_not_called()


class TheDownloadIsStagedAndVerified(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.dest = Path(self.td.name) / "clip.mp4"

    def _serve(self, body: bytes):
        resp = mock.MagicMock()
        chunks = [body, b""]
        resp.read.side_effect = lambda _n=0: chunks.pop(0) if chunks else b""
        resp.__enter__.return_value = resp
        return resp

    def test_an_undecodable_download_never_becomes_a_cache_entry(self):
        with mock.patch.object(tv.urllib.request, "urlopen",
                               return_value=self._serve(b"\x01" * 20_000)), \
             mock.patch.object(tv, "probe_decodable", return_value=False):
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertIsNone(out)
        self.assertFalse(self.dest.exists())
        self.assertFalse((self.dest.parent / (self.dest.name + ".part")).exists(),
                         "the staging file was left behind")

    def test_a_good_download_lands_at_the_final_path(self):
        with mock.patch.object(tv.urllib.request, "urlopen",
                               return_value=self._serve(b"\x01" * 20_000)), \
             mock.patch.object(tv, "probe_decodable", return_value=True):
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertEqual(out, self.dest)
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.stat().st_size, 20_000)

    def test_a_crash_mid_download_leaves_no_final_file(self):
        """The point of staging: dest only ever exists once it is verified."""
        resp = mock.MagicMock()
        resp.read.side_effect = [b"\x01" * 20_000, OSError("connection reset")]
        resp.__enter__.return_value = resp
        with mock.patch.object(tv.urllib.request, "urlopen", return_value=resp):
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertIsNone(out)
        self.assertFalse(self.dest.exists())

    def test_a_stub_under_the_size_floor_is_still_refused(self):
        with mock.patch.object(tv.urllib.request, "urlopen",
                               return_value=self._serve(b"nope")):
            out = tv._download("http://x/clip.mp4", self.dest)
        self.assertIsNone(out)
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
