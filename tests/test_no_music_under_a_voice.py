"""No music under someone talking, and a song that gets a video blocked
comes off the shelf.

Operator, 2026-10-28, of Baller Bro: *"It played loud music over the guy
talking the whole time. It's like, well, what the fuck? That's so
annoying"* (Shai Gilgeous-Alexander's postgame under "Fix You" from second
four, Shadab Khan's dismissal under the hype beat from second zero); and
*"sometimes we get away with using songs that are copyrighted, but
sometimes we don't"*.
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

from funnel import songs  # noqa: E402
from third_capture import moves, outro  # noqa: E402


class TheClipHasNoMusicUnderIt(unittest.TestCase):
    def _plan(self, **edit):
        return moves.plan(dict(edit), dur=40.0)

    def test_a_sad_song_keeps_its_grey_and_loses_its_sound(self):
        p = self._plan(moves=[{"move": "sad", "at": 4}], song="heartbreak",
                       music=False)
        self.assertTrue(p["bed"]["silent"])
        self.assertNotIn("song", p["bed"])
        self.assertIn("hue=s=", moves.look(p))          # still grey
        frag, files = moves.audio_graph(p, "0:a", 1, 40.0, "amood")
        self.assertEqual(files, [])
        self.assertNotIn("sidechaincompress", frag)

    def test_the_hype_beat_is_silent_too(self):
        p = self._plan(moves=[{"move": "hype", "at": 0.3}], music=False)
        frag, files = moves.audio_graph(p, "0:a", 1, 40.0, "amood")
        self.assertEqual(files, [])
        self.assertIn("(silent)", moves.summary(p)[0])

    def test_without_the_flag_the_twitch_edit_is_unchanged(self):
        p = self._plan(moves=[{"move": "hype", "at": 0.3}])
        _, files = moves.audio_graph(p, "0:a", 1, 40.0, "amood")
        self.assertEqual(len(files), 1)

    def test_every_sports_cut_asks_for_no_music(self):
        src = (REPO / "scripts" / "sports_samples.py").read_text()
        self.assertIn('meta["edit"]["music"] = False', src)

    def test_the_outro_song_comes_in_well_under_the_voice(self):
        # 0.35 was about 9 dB down: a song over the person, on a phone
        self.assertLessEqual(outro.PRELAP_GAIN, 0.2)


class ABlockedSongComesOffTheShelf(unittest.TestCase):
    def _with(self, rows):
        d = Path(tempfile.mkdtemp())
        f = d / "latest.json"
        f.write_text(json.dumps({"videos": rows}))
        return mock.patch.object(songs, "ANALYTICS", [f])

    def test_a_block_takes_it_off_and_a_claim_does_not(self):
        rows = [{"songs": ["heartbreak"], "blocked_in": ["DE", "RU"]},
                {"songs": ["tribute"], "blocked_in": []}]
        with self._with(rows):
            self.assertEqual(songs.blocked(), {"heartbreak"})
            self.assertNotIn("heartbreak", songs.names("sad"))
            self.assertIn("tribute", songs.names("sad"))
            self.assertNotIn("heartbreak", songs.menu(""))

    def test_a_story_that_asks_for_it_gets_another_of_its_mood(self):
        with self._with([{"songs": ["heartbreak"], "rejection": "claim"}]):
            got = songs.clean("heartbreak")
        self.assertTrue(got)
        self.assertNotEqual(got, "heartbreak")
        self.assertEqual(songs.SONGS[got]["mood"], "sad")

    def test_no_analytics_means_the_whole_shelf(self):
        with mock.patch.object(songs, "ANALYTICS",
                               [Path("/nonexistent/latest.json")]):
            self.assertEqual(songs.blocked(), set())
            self.assertEqual(songs.clean("heartbreak"), "heartbreak")

    def test_the_upload_records_which_songs_it_played(self):
        sys.path.insert(0, str(REPO / "scripts"))
        from scripts.sports_samples import songs_in
        self.assertEqual(
            songs_in({"outro": {"song": "heartbreak"},
                      "moves": ["zoom@1", "sad@4(tribute)",
                                "hype@0.3(silent)"]}),
            ["heartbreak", "tribute"])
        run = (REPO / "scripts" / "run_sports.py").read_text()
        self.assertIn('extra={"songs": made.get("songs")}', run)
        fa = (REPO / "scripts" / "fetch_analytics.py").read_text()
        self.assertIn('"regionRestriction"', fa)
        self.assertIn('"songs": e.get("songs")', fa)


if __name__ == "__main__":
    unittest.main()
