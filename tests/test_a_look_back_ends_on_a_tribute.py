"""A clip that LOOKS BACK on someone ends on a tribute: the clip plays as
it is, then a real song over a montage of them.

Operator, 2026-10-18: *"when Kevin Durant was talking about how sad he
was that him and Russ aren't playing anymore, you play just that clip,
and then after that clip's done, play some sad music, and then cut to,
like, clips of them playing together ... Not what you just did, not two
overlays on top ... they're two different situations"*.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from funnel import find_footage, songs
from third_capture import author, moves, outro

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
OUTRO = {"song": "see_you_again", "who": "Kevin Durant Russell Westbrook",
         "looks": ["Durant and Westbrook celebrating on the Thunder",
                   "Westbrook lob to Durant"]}


class TheAuthorMarksIt(unittest.TestCase):
    def test_an_outro_needs_a_song_who_and_two_shots(self):
        self.assertEqual(outro.parse(OUTRO)["song"], "see_you_again")
        self.assertIsNone(outro.parse({**OUTRO, "song": "stock piano"}))
        self.assertIsNone(outro.parse({**OUTRO, "looks": ["one shot"]}))
        self.assertIsNone(outro.parse({**OUTRO, "who": ""}))
        self.assertIsNone(outro.parse(None))

    def test_the_author_keeps_it_and_is_told_what_it_is(self):
        out = author._postprocess(
            {"title": "Kevin Durant Misses Playing With Russ",
             "hook": "KD on Russ 🥀", "hashtags": ["kevindurant"],
             "series": "drama", "edit": {"mood": "", "outro": OUTRO}},
            "Kevin Durant", "kd talks about russ", 30.0)
        self.assertEqual(out["edit"]["outro"]["who"], OUTRO["who"])
        self.assertIn("you play just that clip", author.SYSTEM)

    def test_it_is_not_a_cut_in(self):
        # two different situations: the cut-ins stay, the outro is extra
        self.assertIn("- broll:", author.SYSTEM)
        self.assertIn("- outro:", author.SYSTEM)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class TheClipPlaysThenTheTribute(unittest.TestCase):
    """2026-10-21: "need to be significantly more basketball clips ...
    The cut is abrasive. Maybe make it like gray ... just for this
    one"."""
    def _media(self, td: Path):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=c=red:s=1280x720:r=30:d=14", "-f", "lavfi", "-i",
             "sine=f=300:d=14", "-shortest", "-c:v", "libx264", "-c:a",
             "aac", str(td / "src.mp4")], check=True)
        for c in ("blue", "green"):
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 f"color=c={c}:s=1280x720:r=30:d=3", "-c:v", "libx264",
                 str(td / f"{c}.mp4")], check=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "sine=f=600:d=30", "-ac", "2", str(td / "song.wav")],
            check=True)

    def _edit(self, td: Path, shots: list[str], item=OUTRO):
        from third_capture import clip_edit
        it = iter(shots)

        def find(who, look, n=1, **k):
            c = next(it, None)
            return [{"path": str(td / f"{c}.mp4"), "url": c,
                     "title": c, "from_s": 0, "secs": 2.8}] if c else []
        words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4}
                 for i, w in enumerate(
                     ("me and him used to be so good together " * 3).split())]
        with mock.patch.object(songs, "get",
                               return_value=td / "song.wav"), \
                mock.patch.object(find_footage, "find_many", side_effect=find):
            return clip_edit.edit(
                td / "src.mp4", td / "out.mp4", credit="r/nba",
                hook="KD on Russ", words=words,
                direct={"mood": "sad", "mood_at": 3, "outro": item})

    def _px(self, path: Path, t: float) -> bytes:
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path),
             "-frames:v", "1", "-vf", "crop=8:8:536:200,scale=1:1", "-f",
             "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=True).stdout

    def test_the_montage_follows_the_clip_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            led = self._edit(td, ["blue", "green"])
            self.assertEqual(led["outro"]["shots"], ["blue", "green"])
            # no sad bed or grey under the words: the song comes after
            self.assertEqual(led["moves"], [])
            dur = outro._seconds(td / "out.mp4")
            self.assertAlmostEqual(dur, led["duration_s"], delta=0.3)
            clip = self._px(td / "out.mp4", 3.0)
            self.assertGreater(clip[0], clip[2] + 60)      # red, in colour
            end = self._px(td / "out.mp4", dur - 3.4)
            self.assertGreater(end[2] + end[1], end[0] + 40)  # the footage

    def test_a_shot_that_will_not_join_is_dropped_not_the_tribute(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            (td / "broken.mp4").write_bytes(b"not a video")
            led = self._edit(td, ["blue", "broken", "green"], item={
                **OUTRO, "looks": OUTRO["looks"] + ["Durant dunk on OKC"]})
            self.assertEqual(led["outro"]["shots"], ["blue", "green"])

    def test_grey_is_the_authors_call_and_drains_the_colour(self):
        self.assertEqual(outro.parse(OUTRO)["grade"], "faded")
        self.assertEqual(outro.parse({**OUTRO, "grade": "grey"})["grade"],
                         "grey")
        self.assertEqual(outro.parse({**OUTRO, "grade": "neon"})["grade"],
                         "faded")
        self.assertIn('"grade"', author.SYSTEM)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            led = self._edit(td, ["blue", "green"],
                             item={**OUTRO, "grade": "grey"})
            self.assertEqual(led["outro"]["grade"], "grey")
            end = self._px(td / "out.mp4", outro._seconds(td / "out.mp4")
                           - 3.4)
            self.assertLess(max(end) - min(end), 30)        # grey, not blue

    def test_the_cut_is_soft_and_the_last_word_is_kept(self):
        g = outro.graph(3, [2.4] * 3, 12.0, 1080, 1920, None)
        # the clip's last frame is held under the dissolve, not cut off
        self.assertIn(f"stop_duration={outro.XFADE_S}", g)
        self.assertIn("offset=12.00", g)
        # the song starts under the clip's last words, before the picture
        lead = 12.0 - outro.PRELAP_S
        self.assertIn(f"adelay={int(lead * 1000)}", g)
        self.assertGreaterEqual(outro.XFADE_S, 0.8)

    def test_the_montage_asks_for_many_shots_of_them_playing(self):
        asked = []

        def many(who, look, n=1, **k):
            asked.append((look, n))
            return []
        with mock.patch.object(find_footage, "find_many", side_effect=many):
            outro.shots({**OUTRO, "looks": OUTRO["looks"] + ["x"]},
                        Path(tempfile.mkdtemp()))
        self.assertGreaterEqual(sum(n for _l, n in asked),
                                outro.TARGET_SHOTS)
        self.assertGreaterEqual(outro.TARGET_SHOTS, 6)
        self.assertTrue(all("the game" in l for l, _n in asked))

    def test_reels_of_different_shapes_still_join(self):
        # 2026-10-21: a 16:9 reel beside a #shorts one scaled to sizes
        # whose SAR differed, and concat refused every montage of the run
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=green:s=406x720:r=30:d=3", "-c:v", "libx264",
                 str(td / "tall.mp4")], check=True)
            led = self._edit(td, ["blue", "tall"])
            self.assertEqual(led["outro"]["shots"], ["blue", "tall"])

    def test_every_shot_shows_both_of_them(self):
        # 2026-10-21: "the basketball clip was ass and not of Russ and KD"
        item = outro.parse({**OUTRO, "people": ["Kevin Durant",
                                                "Russell Westbrook"]})
        self.assertEqual(item["people"], ["Kevin Durant",
                                          "Russell Westbrook"])
        look = outro.frame_look("Thunder highlights", item["people"])
        self.assertIn("BOTH", look)
        self.assertIn("only one of them", look)
        asked = []
        with mock.patch.object(find_footage, "find_many", side_effect=(
                lambda *a, **k: asked.append(k.get("title_has")) or [])):
            outro.shots(item, Path(tempfile.mkdtemp()))
        self.assertTrue(all(t == ["Durant", "Westbrook"] for t in asked))
        self.assertTrue(find_footage.titled(
            "Kevin Durant & Russell Westbrook 2012 Highlights",
            ["Durant", "Westbrook"]))
        self.assertFalse(find_footage.titled(
            "Russell Westbrook's Most EXPLOSIVE Dunks", ["Durant",
                                                         "Westbrook"]))
        self.assertIn('"people"', author.SYSTEM)
        # then KD on the Suns guarding Russ passed as "together"
        mates = outro.frame_look("x", item["people"], "Oklahoma City Thunder")
        self.assertIn("Oklahoma City Thunder uniforms", mates)
        self.assertIn("another team's", mates)
        # then a Hornets guard and a Kobe close-up from a long fan reel
        self.assertIn("close-up of one face", mates)
        self.assertIn("wide shot", mates)
        caps = []
        with mock.patch.object(find_footage, "find_many", side_effect=(
                lambda *a, **k: caps.append((k["max_s"], k["per_video"]))
                or [])):
            outro.shots({**item, "team": "Oklahoma City Thunder"},
                        Path(tempfile.mkdtemp()))
        self.assertTrue(all(m <= 300 and 0 < p <= 3 for m, p in caps))
        # then three shots of a "Westbrook vs Durant" video
        nums = outro.parse({**OUTRO, "people": item["people"],
                            "team": "Oklahoma City Thunder",
                            "numbers": ["35", "0"]})
        self.assertEqual(nums["numbers"], ["35", "0"])
        look = outro.frame_look("x", nums["people"], nums["team"],
                                nums["numbers"])
        self.assertIn("#35 or #0 in a Oklahoma City Thunder uniform", look)
        self.assertIn("another team", look)
        self.assertTrue(outro.VERSUS.search("Westbrook vs Durant 😳"))
        self.assertFalse(outro.VERSUS.search("Westbrook to Durant alley oop"))
        nots = []
        with mock.patch.object(find_footage, "find_many", side_effect=(
                lambda *a, **k: nots.append(k) or [])):
            outro.shots(nums, Path(tempfile.mkdtemp()))
        self.assertTrue(all(k["title_not"] is outro.VERSUS for k in nots))
        # YouTube is searched for the play, never for the rules
        self.assertEqual([k["query"] for k in nots], nums["looks"])
        self.assertIn('"numbers"', author.SYSTEM)
        # and without a team, both of them in the same play
        self.assertIn("same play", outro.frame_look("x", item["people"]))
        self.assertIn('"team"', author.SYSTEM)

    def test_the_song_is_heard_well_before_the_picture_changes(self):
        # 2026-10-21: "the music needs to start to fade in earlier ...
        # before the clip switches"
        self.assertGreaterEqual(outro.PRELAP_S, 4.0)
        g = outro.graph(3, [2.4] * 3, 20.0, 1080, 1920, None)
        self.assertIn(f"adelay={int((20.0 - outro.PRELAP_S) * 1000)}", g)
        self.assertIn(f"{outro.PRELAP_GAIN}*t", g)       # under the voice

    def test_one_shot_is_not_a_tribute(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            led = self._edit(td, ["blue"])
            self.assertIsNone(led["outro"])
            self.assertLess(outro._seconds(td / "out.mp4"), 13.0)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class AReelGivesSeveralShots(unittest.TestCase):
    def test_find_many_takes_distinct_shots_from_one_reel(self):
        from funnel import hot_clips
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cols = ["red", "blue", "green", "yellow", "white", "purple",
                    "orange", "cyan", "pink", "gray"]
            ins = []
            for c in cols:
                ins += ["-f", "lavfi", "-i", f"color=c={c}:s=640x360:r=30:d=3"]
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex",
                 "".join(f"[{i}:v]" for i in range(len(cols)))
                 + f"concat=n={len(cols)}:v=1:a=0", "-c:v", "libx264",
                 str(td / "reel.mp4")], check=True)
            vid = {"url": "u1", "title": "Durant Westbrook highlights"}
            with mock.patch.object(hot_clips, "youtube",
                                   return_value=[vid]), \
                    mock.patch.object(hot_clips, "reddit_videos",
                                      return_value=[]), \
                    mock.patch.object(find_footage, "download",
                                      return_value=td / "reel.mp4"), \
                    mock.patch.object(find_footage, "judge", side_effect=(
                        lambda frames, *a, **k: {i: {"depicts": True}
                                                 for i, _p in frames})):
                skip = set()
                got = find_footage.find_many("KD Russ", "them", n=4,
                                             secs=2.4, work=td, skip=skip)
                again = find_footage.find_many("KD Russ", "them", n=10,
                                               secs=2.4, work=td, skip=skip)
            self.assertEqual(len(got), 4)
            starts = sorted(g["from_s"] for g in got + again)
            self.assertTrue(all(b - a >= 2.4 for a, b in zip(starts,
                                                              starts[1:])))
            self.assertFalse({g["from_s"] for g in got}
                             & {g["from_s"] for g in again})


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class TheLastShotPlaysOut(unittest.TestCase):
    """2026-10-21: "why did we cut the clip at the end? ... At the very
    least, let that last clip finish playing out"."""

    def test_the_last_shot_runs_to_the_end_of_its_play(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=blue:s=640x360:r=30:d=9", "-c:v", "libx264",
                 str(td / "play.mp4")], check=True)
            hit = {"path": "x", "url": "u", "from_s": 1.0, "secs": 2.4,
                   "source": str(td / "play.mp4"), "source_s": 9.0,
                   "shot_end": 3.4}
            out = outro.play_out(hit, td)
            self.assertTrue(out["hold"])
            # a short clip of one play runs on past its camera cut
            self.assertAlmostEqual(out["secs"], outro.LAST_MAX_S, delta=0.1)
            self.assertGreater(outro._seconds(Path(out["path"])), 5.5)
            # a long reel stops at the end of the shot, not in the next play
            reel = outro.play_out({**hit, "source_s": 600.0,
                                   "shot_end": 5.0}, td)
            self.assertAlmostEqual(reel["secs"], 4.0, delta=0.1)
            # nothing to play out: the hit as it was
            self.assertIs(outro.play_out({**hit, "source": None}, td).get(
                "hold"), None)

    def test_the_montage_holds_the_last_shot_and_fades_after(self):
        g = outro.graph(3, [2.4, 2.4, 6.0], 12.0, 1080, 1920, None)
        self.assertIn("trim=0:6.00", g)
        self.assertIn(f"st={10.8 - outro.TAIL_FADE_S:.2f}", g)


class ItIsAStoryNotATribute(unittest.TestCase):
    """2026-10-21: "it's not just tributes ... anytime we can do anything
    like that, whether it's a sad thing or a happy thing or a tribute or
    whatever it is, we should do it"."""

    def test_the_shelf_has_every_mood_a_payoff_can_have(self):
        for mood in ("sad", "hype", "triumph", "funny"):
            self.assertGreaterEqual(len(songs.names(mood)), 2, mood)
        everything = songs.menu("")
        for mood in songs.MOODS:
            self.assertIn(f"[{mood}]", everything)

    def test_the_author_is_told_to_use_it_on_any_showable_story(self):
        self.assertIn("it's not just tributes", author.SYSTEM)
        self.assertIn("till_i_collapse", author.SYSTEM)     # a hype song
        self.assertIn("yakety_sax", author.SYSTEM)          # a funny one
        self.assertNotIn("{OUTRO_MENU}", author.SYSTEM)

    def test_a_hype_payoff_of_one_player(self):
        item = outro.parse({"song": "till_i_collapse", "who": "Kobe Bryant",
                            "people": ["Kobe Bryant"],
                            "team": "Los Angeles Lakers", "numbers": ["8"],
                            "grade": "hype",
                            "looks": ["Kobe 81 point game highlights",
                                      "Kobe 81 points fadeaway"]})
        self.assertEqual(item["grade"], "hype")
        self.assertIn("#8", outro.frame_look("x", item["people"],
                                             item["team"], item["numbers"]))
        asked = []
        with mock.patch.object(find_footage, "find_many", side_effect=(
                lambda *a, **k: asked.append(k["title_has"]) or [])):
            outro.shots(item, Path(tempfile.mkdtemp()))
        self.assertTrue(all(t == ["Bryant"] for t in asked))
        self.assertIn("hype", outro.GRADES)


class TheClipIsNeverItsOwnMontage(unittest.TestCase):
    """2026-10-22: Verlander's "career highlights" montage was cut from
    the very post being told (his daughter coming out to get him), and
    Scherzer's from his own standing ovation: Reddit's search returns
    the post itself. The outro carries the clip's urls and title as
    `avoid`, and no candidate matching one is downloaded."""

    def test_the_source_post_is_not_downloaded(self):
        from funnel import find_footage, hot_clips
        src = {"url": "https://v.redd.it/abc", "title": "Verlander's daughter "
               "has come out to get her dad", "permalink": "/r/sports/x"}
        other = {"url": "https://youtu.be/k", "title": "Verlander no-hitter"}
        asked = []
        with mock.patch.object(hot_clips, "youtube", return_value=[
                    {"url": "https://youtu.be/same", "title": src["title"]},
                    other]), \
                mock.patch.object(hot_clips, "reddit_videos", return_value=[
                    {"media": src["url"], "post_title": "something else",
                     "permalink": src["permalink"]}]), \
                mock.patch.object(find_footage, "download",
                                  side_effect=lambda u, *a, **k:
                                  asked.append(u)):
            find_footage.find_many(
                "Justin Verlander", "him pitching", n=2,
                work=Path(tempfile.mkdtemp()),
                avoid={src["permalink"], src["title"]})
        self.assertEqual(asked, [other["url"]])

    def test_the_outro_keeps_what_to_avoid(self):
        item = outro.parse({**OUTRO, "avoid": ["https://v.redd.it/abc"]})
        self.assertEqual(item["avoid"], ["https://v.redd.it/abc"])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class AMontageIsNotOnePictureThreeTimes(unittest.TestCase):
    """2026-10-22: Keenum's payoff was one pre-snap line-up, three shots
    of the same picture. A shot that looks like one already taken is
    passed over."""

    def test_a_still_reel_gives_one_shot(self):
        from funnel import hot_clips
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=green:s=320x180:r=30:d=30", "-c:v", "libx264",
                 str(td / "still.mp4")], check=True)
            with mock.patch.object(hot_clips, "youtube", return_value=[
                        {"url": "u1", "title": "Keenum hard count"}]), \
                    mock.patch.object(hot_clips, "reddit_videos",
                                      return_value=[]), \
                    mock.patch.object(find_footage, "download",
                                      return_value=td / "still.mp4"), \
                    mock.patch.object(find_footage, "shot_around",
                                      side_effect=lambda v, at: (at - 2, at + 2)), \
                    mock.patch.object(find_footage, "judge", side_effect=(
                        lambda frames, *a, **k: {i: {"depicts": True}
                                                 for i, _p in frames})):
                got = find_footage.find_many("Case Keenum", "him", n=4,
                                             secs=2.4, work=td)
            self.assertEqual(len(got), 1)


class YouTubeSearchOutlivesTheQuota(unittest.TestCase):
    """2026-10-22: the Data API's quota ran out and every montage fell
    back to this month's Reddit posts. With no API answer, YouTube's own
    search page (yt-dlp) is asked, and over-long videos are still left
    out."""

    def test_its_own_search_page_answers(self):
        from funnel import hot_clips
        with mock.patch.object(hot_clips, "_yt", return_value={}), \
                mock.patch.object(hot_clips, "_ytsearch", return_value=[
                    {"id": "a1", "title": "Scherzer 20 K", "channel": "MLB",
                     "duration": 200},
                    {"id": "b2", "title": "full game", "channel": "MLB",
                     "duration": 9000}]):
            got = hot_clips.youtube("Max Scherzer 20 strikeouts", max_s=600)
        self.assertEqual([g["url"] for g in got],
                         ["https://www.youtube.com/watch?v=a1"])
