"""A sad turn gets a REAL song, and the people talked about are SHOWN.

Operator, 2026-10-17: *"when Russ is talking about KD and it's like all
sad and it's like, oh man, him and KD used to be so good together. We put
some sad music over it. Not sad like your fucking Kevin McLeod, whatever
bullshit stock art sound we use, but like an actual like wistful sad song
people might recognize potentially, and like show highlights of the two
together"*.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from funnel import find_footage, songs
from third_capture import author, cut_in, moves

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


class TheSongShelf(unittest.TestCase):
    def test_every_song_resolves_and_is_a_real_record(self):
        self.assertGreaterEqual(len(songs.names("sad")), 6)
        for k, s in songs.SONGS.items():
            self.assertEqual(songs.clean(k), k)
            self.assertTrue(s["artist"] and s["title"] and s["fits"])
            self.assertIn(s["mood"], songs.MOODS)

    def test_a_name_not_on_the_shelf_is_no_song(self):
        self.assertEqual(songs.clean("kevin macleod sad piano"), "")
        self.assertIsNone(songs.get("kevin macleod sad piano"))
        self.assertEqual(songs.clean("See You Again"), "see_you_again")

    def test_the_author_is_shown_the_shelf_itself(self):
        self.assertNotIn("{SONG_MENU}", author.SYSTEM)
        for k in songs.names("sad"):
            self.assertIn(f"{k}: {songs.SONGS[k]['title']}", author.SYSTEM)

    def test_the_store_match_is_the_song_not_a_cover(self):
        s = songs.SONGS["see_you_again"]
        self.assertTrue(songs._match(
            s, "See You Again (feat. Charlie Puth)", "Wiz Khalifa"))
        self.assertFalse(songs._match(s, "See You Again", "Piano Covers"))


class TheSongIsWhatPlays(unittest.TestCase):
    def test_the_author_keeps_a_song_only_on_a_sad_turn(self):
        def post(edit):
            return author._postprocess(
                {"title": "Russell Westbrook Misses Playing With KD",
                 "hook": "Russ on KD 🥀", "hashtags": ["westbrook"],
                 "series": "drama", "edit": edit},
                "Russell Westbrook", "russ talks about kd", 30.0)["edit"]
        self.assertEqual(post({"mood": "sad", "mood_at": 6,
                               "song": "see_you_again"})["song"],
                         "see_you_again")
        self.assertNotIn("song", post({"mood": "hype", "mood_at": 6,
                                       "song": "see_you_again"}))
        self.assertNotIn("song", post({"mood": "sad", "mood_at": 6,
                                       "song": "stock piano"}))

    def test_the_plan_carries_it_to_the_bed(self):
        p = moves.plan({"mood": "sad", "mood_at": 5, "song": "fix_you"}, 30)
        self.assertEqual(p["bed"]["song"], "fix_you")
        self.assertIn("sad@5.0(fix_you)", moves.summary(p))
        self.assertNotIn("song", moves.plan(
            {"mood": "hype", "mood_at": 5, "song": "fix_you"}, 30)["bed"])

    def test_the_song_file_is_mixed_and_the_piano_is_only_the_fallback(self):
        p = moves.plan({"mood": "sad", "mood_at": 5, "song": "fix_you"}, 30)
        fake = Path("/tmp/fix_you.wav")
        with mock.patch.object(songs, "get", return_value=fake):
            frag, files = moves.audio_graph(p, "0:a", 1, 30, "a")
        self.assertEqual(files, [fake])
        self.assertIn(f"volume={moves.SONG_GAIN}", frag)
        with mock.patch.object(songs, "get", return_value=None):
            _frag, files = moves.audio_graph(p, "0:a", 1, 30, "a")
        self.assertEqual(files, [moves.sound("sad")])


class TheFootageIsCutIn(unittest.TestCase):
    def test_the_author_names_who_and_when(self):
        out = author._postprocess(
            {"title": "Russell Westbrook Misses Playing With KD",
             "hook": "Russ on KD 🥀", "hashtags": ["westbrook"],
             "series": "drama",
             "edit": {"mood": "sad", "mood_at": 6, "broll": [
                 {"who": "Russell Westbrook Kevin Durant",
                  "look": "Westbrook and Durant together on the Thunder",
                  "at": 8.5}, {"who": "", "at": 3}]}},
            "Russell Westbrook", "russ talks about kd", 30.0)
        self.assertEqual(out["edit"]["broll"], [
            {"who": "Russell Westbrook Kevin Durant",
             "look": "Westbrook and Durant together on the Thunder",
             "at": 8.5}])

    def test_any_clip_can_cut_in_not_only_a_sad_one(self):
        # operator, 2026-10-17: "It doesn't just need to be about
        # emotional moments ... making something of our own"
        out = author._postprocess(
            {"title": "Josh Allen Calls Out The Hurdle Doubters",
             "hook": "Josh Allen on the hurdle", "hashtags": ["joshallen"],
             "series": "win", "edit": {"mood": "", "broll": [
                 {"who": "Josh Allen", "look": "Josh Allen hurdle",
                  "at": 4}]}},
            "Josh Allen", "allen talks about the hurdle", 30.0)
        self.assertEqual(len(out["edit"]["broll"]), 1)
        brief = author.SYSTEM[author.SYSTEM.index("- broll:"):]
        self.assertIn("OUR OWN", brief[:200])
        self.assertNotIn("sad", brief[:brief.index("- outro:")])

    def test_the_plan_is_on_the_cuts_clock_and_spaced(self):
        items = [{"who": "A", "at": 8}, {"who": "B", "at": 10},
                 {"who": "C", "at": 20}, {"who": "D", "at": 1.5},
                 {"who": "E", "at": 29}]
        got = cut_in.plan(items, 30, offset=1.0)
        self.assertEqual([(g["who"], g["at"]) for g in got],
                         [("A", 7.0), ("C", 19.0)])

    def test_a_cut_in_is_the_game_not_people_talking(self):
        # operator, 2026-10-17, of a cut-in of Stephen A at a news desk:
        # "there was no basketball clips in there. There was maybe one"
        self.assertTrue(find_footage.is_talk(
            "Stephen A reacts to Kevin Durant joining the Warriors"))
        self.assertTrue(find_footage.is_talk("Russ Westbrook FULL Interview"))
        self.assertFalse(find_footage.is_talk(
            "OKC vs GSW Game 7 2016 Western Conference Finals Highlights"))
        with mock.patch("shared.shot_relevance.judge_panels",
                        return_value={}) as jp:
            find_footage.judge([(0, Path("f.png"))], "KD on the Warriors")
        self.assertIn("NOT a studio show", jp.call_args[0][0][0][2])
        self.assertIn("players playing", author.SYSTEM)

    def test_unchecked_footage_is_never_cut_in(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("funnel.hot_clips.youtube", return_value=[
                    {"url": "https://www.youtube.com/watch?v=x",
                     "title": "KD and Russ highlights"}]), \
                mock.patch.object(find_footage, "download",
                                  return_value=Path(td) / "v.mp4"), \
                mock.patch.object(find_footage, "_seconds",
                                  return_value=200.0), \
                mock.patch.object(find_footage, "_frame",
                                  side_effect=lambda v, a, o: o), \
                mock.patch.object(find_footage, "judge", return_value=None):
            self.assertIsNone(find_footage.find("Russ KD", "together",
                                                work=td))

    def test_the_first_checked_frame_is_where_it_is_cut(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("funnel.hot_clips.youtube", return_value=[
                    {"url": "https://www.youtube.com/watch?v=x",
                     "title": "KD and Russ highlights"}]), \
                mock.patch.object(find_footage, "download",
                                  return_value=Path(td) / "v.mp4"), \
                mock.patch.object(find_footage, "_seconds",
                                  return_value=200.0), \
                mock.patch.object(find_footage, "_frame",
                                  side_effect=lambda v, a, o: o), \
                mock.patch.object(find_footage, "judge", return_value={
                    0: {"depicts": False}, 1: {"depicts": True}}), \
                mock.patch.object(find_footage, "shot_around",
                                  return_value=(0.0, 200.0)), \
                mock.patch.object(find_footage, "cut",
                                  side_effect=lambda v, s, n, o: o):
            hit = find_footage.find("Russ KD", "together", work=td)
        self.assertAlmostEqual(hit["from_s"],
                               200 * find_footage.POINTS[1]
                               - find_footage.PLAY_LEAD, places=1)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
    def test_only_the_shot_the_brain_saw_is_cut_in(self):
        # 2026-10-17: the brain saw Westbrook and Durant, the cut showed
        # Kobe Bryant from the reel's next shot
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=red:s=640x360:r=30:d=4.6", "-f", "lavfi", "-i",
                 "color=c=blue:s=640x360:r=30:d=6", "-filter_complex",
                 "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-c:v",
                 "libx264", str(td / "reel.mp4")], check=True)
            s0, s1 = find_footage.shot_around(td / "reel.mp4", 4.0)
            self.assertAlmostEqual(s1, 4.6, delta=0.1)
            with mock.patch("funnel.hot_clips.youtube", return_value=[
                    {"url": "u", "title": "reel"}]), \
                    mock.patch.object(find_footage, "download",
                                      return_value=td / "reel.mp4"), \
                    mock.patch.object(find_footage, "POINTS", (0.42,)), \
                    mock.patch.object(find_footage, "judge",
                                      return_value={0: {"depicts": True}}):
                hit = find_footage.find("Russ KD", "together", work=td)
            self.assertLessEqual(hit["from_s"] + hit["secs"], 4.6)
            px = subprocess.run(
                ["ffmpeg", "-v", "error", "-sseof", "-0.1", "-i",
                 hit["path"], "-frames:v", "1", "-vf", "scale=1:1",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                capture_output=True, check=True).stdout
            self.assertGreater(px[0], px[2])             # still red

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
    def test_it_renders_over_the_whole_frame_under_the_words(self):
        from third_capture import clip_edit
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=red:s=1280x720:r=30:d=14", "-f", "lavfi", "-i",
                 "sine=f=300:d=14", "-shortest", "-c:v", "libx264", "-c:a",
                 "aac", str(td / "src.mp4")], check=True)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=blue:s=1280x720:r=30:d=4", "-c:v", "libx264",
                 str(td / "foot.mp4")], check=True)
            words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4}
                     for i, w in enumerate(
                         ("me and him used to be so good together " * 3)
                         .split())]
            with mock.patch.object(find_footage, "find", return_value={
                    "path": str(td / "foot.mp4"), "url": "u", "title": "t",
                    "from_s": 0}):
                led = clip_edit.edit(
                    td / "src.mp4", td / "out.mp4", credit="r/nba",
                    hook="Russ on KD", words=words,
                    # "him" is said at 5.0s: the footage lands on it
                    # (cut_in.snap)
                    direct={"broll": [{"who": "Russ KD", "look": "x",
                                       "at": 5, "said": "him"}]})
            self.assertEqual(led["render_level"], "full")
            self.assertEqual(len(led["cut_in"]), 1)
            self.assertTrue(led["cut_in"][0].startswith("Russ KD@"))

            def corner(t):
                return subprocess.run(
                    ["ffmpeg", "-v", "error", "-ss", str(t), "-i",
                     str(td / "out.mp4"), "-frames:v", "1", "-vf",
                     "crop=8:8:536:200,scale=1:1", "-f", "rawvideo",
                     "-pix_fmt", "rgb24", "-"],
                    capture_output=True, check=True).stdout
            before, during = corner(2.0), corner(6.5)
            self.assertGreater(before[0], before[2])     # the red clip
            self.assertGreater(during[2], during[0])     # the blue footage


if __name__ == "__main__":
    unittest.main()
