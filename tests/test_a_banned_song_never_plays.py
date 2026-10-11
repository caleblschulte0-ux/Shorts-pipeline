"""A song the operator banned never plays again.

Operator, 2026-10-11, of the medical-debt video: *"Whatever song we're using
in the background of the medical debt videos, never use that song again."*
Its bed was "calm", which the slug rotated to Almost New. It is gone from
the fetch list, and the picker skips it by name, because the CI music cache
restores an older folder that still holds the file.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as S  # noqa: E402
from scripts import fetch_music as FM  # noqa: E402


class TheBannedSongNeverPlays(unittest.TestCase):
    def test_almost_new_is_banned(self):
        self.assertIn("almost-new", S.BANNED_TRACKS)

    def test_it_is_not_fetched(self):
        for vibe, titles in FM.LIBRARY.items():
            for t in titles:
                self.assertNotIn(FM._slug(t), S.BANNED_TRACKS, (vibe, t))

    def test_a_cached_copy_is_never_picked(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for vibe in ("calm", "dark"):
                (d / vibe).mkdir()
                for stem in ("almost-new", "carefree", "wholesome"):
                    (d / vibe / f"{stem}.mp3").write_bytes(b"x")
            with mock.patch.object(S, "MUSIC_DIR", d):
                for i in range(300):
                    for vibe in ("calm", "dark"):
                        got = S._music_track(vibe, f"story-{i}")
                        self.assertNotIn(got.stem, S.BANNED_TRACKS)

    def test_the_medical_debt_story_no_longer_gets_it(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "calm"
            d.mkdir()
            for stem in ("almost-new", "carefree", "wholesome"):
                (d / f"{stem}.mp3").write_bytes(b"x")
            with mock.patch.object(S, "MUSIC_DIR", Path(td)):
                got = S._music_track("calm", "medical-debt-credit-score-fix")
            self.assertNotEqual(got.stem, "almost-new")

    def test_only_the_banned_list_left_the_pool(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "calm"
            d.mkdir()
            (d / "almost-new.mp3").write_bytes(b"x")
            with mock.patch.object(S, "MUSIC_DIR", Path(td)):
                self.assertIsNone(S._music_track("calm", "x"))


if __name__ == "__main__":
    unittest.main()
