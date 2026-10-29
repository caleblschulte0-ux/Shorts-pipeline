"""The music is an INSTRUMENTAL with the vibe, never a hit that gets dinged.

Operator, 2026-10-29: *"Can we maybe start moving away from like popular
songs and just doing maybe songs with no lyrics that give the vibe that we
want? Don't go so far as to go into the Kevin McLeod, whatever, but like,
we don't need these getting instantly dinged."* The shelf is vibes; each
picks a NoCopyrightSounds release's INSTRUMENTAL by its moods, and the
credit the licence asks for goes in the description.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from funnel import songs  # noqa: E402

# a row as the NCS search page renders it (2026-10-29, trimmed)
ROW = ('<tr><td><a class="player-play" data-url="https://x/free.mp3" '
       'data-artistraw="Reece Ros&eacute;" data-track="Free" '
       'data-tid="dc515b2d-711f-42f4-9bd0-6dc258819e2f" '
       'data-versions="Regular, Instrumental" data-genre="House"></a></td>'
       '<td><a href="/RR_Free"><p>Free</p></a></td><td>'
       '<a class="tag" href="/music-search?genre=10">House</a>'
       '<a class="tag" href="/music-search?mood=6">energetic</a>'
       '<a class="tag" href="/music-search?mood=37">exciting</a></td></tr>')
SAD = ROW.replace("dc515b2d", "aaaaaaaa").replace("energetic", "sad") \
    .replace("exciting", "Sentimental").replace("RR_Free", "sadtrack")
VOCAL_ONLY = ROW.replace("dc515b2d", "bbbbbbbb").replace(
    "Regular, Instrumental", "Regular")


class TheCatalogueIsRead(unittest.TestCase):
    def test_a_row_becomes_a_track_with_its_moods(self):
        got = songs.parse_catalogue("<tbody>" + ROW + VOCAL_ONLY)
        self.assertEqual(len(got), 1)              # no instrumental, no row
        t = got[0]
        self.assertEqual(t["track"], "Free")
        self.assertEqual(t["artist"], "Reece Rosé")
        self.assertEqual(t["moods"], ["energetic", "exciting"])
        self.assertEqual(t["slug"], "RR_Free")


class AVibePicksByMood(unittest.TestCase):
    def setUp(self):
        self.rows = songs.parse_catalogue(ROW + SAD)

    def test_a_sad_vibe_gets_the_sad_track(self):
        with mock.patch.object(songs, "blocked", return_value=set()):
            got = songs.candidates("tribute", "x", rows=self.rows)
        self.assertEqual([r["track"] for r in got], ["Free"][:0] + [
            r["track"] for r in self.rows if "sad" in r["moods"]])

    def test_a_hype_vibe_gets_the_energetic_one(self):
        with mock.patch.object(songs, "blocked", return_value=set()):
            got = songs.candidates("going_off", "x", rows=self.rows)
        self.assertEqual([r["slug"] for r in got], ["RR_Free"])

    def test_a_blocked_track_is_off_the_shelf(self):
        with mock.patch.object(songs, "blocked", return_value={
                "ncs:dc515b2d-711f-42f4-9bd0-6dc258819e2f"}):
            self.assertEqual(songs.candidates("going_off", "x",
                                              rows=self.rows), [])

    def test_the_loudest_stretch_is_where_it_is_cut(self):
        self.assertEqual(songs.loudest([-40] * 20 + [-6] * 30 + [-40] * 30),
                         20)


class TheCreditGoesInTheDescription(unittest.TestCase):
    def test_the_credit_names_the_track_and_ncs(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ncs_dc515b2d-711f-42f4-9bd0-6dc258819e2f.wav"
            f.write_bytes(b"x")
            Path(str(f) + ".json").write_text(json.dumps(
                songs.parse_catalogue(ROW)[0]))
            c = songs.credit(f)
            self.assertIn("Song: Reece Rosé - Free", c)
            self.assertIn("Music provided by NoCopyrightSounds", c)
            self.assertIn("https://ncs.io/RR_Free", c)
            self.assertEqual(songs.track_id(f),
                             "ncs:dc515b2d-711f-42f4-9bd0-6dc258819e2f")

    def test_the_sports_description_carries_it(self):
        import run_sports
        d = run_sports.description(
            {"caption": "cap"}, {"sub": "nba", "permalink": "/r/nba/x"},
            [{"track": "ncs:1", "credit": "Song: A - B\nMusic provided by "
                                          "NoCopyrightSounds"}])
        self.assertIn("Music provided by NoCopyrightSounds", d)

    def test_the_render_records_what_it_played(self):
        import inspect
        from third_capture import clip_edit
        src = inspect.getsource(clip_edit.edit)
        self.assertIn("_songs.reset_used()", src)
        self.assertIn('"music": [{"track": _songs.track_id(f)', src)


if __name__ == "__main__":
    unittest.main()
