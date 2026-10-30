"""A clip that talks about a play SHOWS the play.

Operator, 2026-10-28, after the edit-basics fixes: *"Now we are going to
far the wrong way like that can skattebo clip show the plays he got fined
on"*. Skattebo talked about the fines for lowering his helmet; the author,
asked for `broll` among a dozen other things, gave none on any clip of
the batch, and the plays never appeared.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from scripts import sports_samples  # noqa: E402
from third_capture import author  # noqa: E402

WORDS = [{"w": w, "s": float(i), "e": i + 0.8} for i, w in enumerate(
    "I got fined for lowering my helmet and I will play for free".split())]
C = {"who": "Cam Skattebo", "post_title": "Skattebo says he'll play for free"}


class AClipWithNoCutInIsAsked(unittest.TestCase):
    def test_no_broll_gets_its_own_question(self):
        ans = {"broll": [{"who": "Cam Skattebo", "at": 2.1, "said": "fined",
                          "look": "Cam Skattebo lowers helmet run Giants"}]}
        with mock.patch.object(sports_samples, "_brain",
                               return_value=ans) as b:
            edit = sports_samples.broll(C, WORDS, 30.0, {"mood": ""})
        self.assertIn("own plays", b.call_args[0][1].lower())
        self.assertIn("[5.0] my helmet", b.call_args[0][0])  # fine stamps
        self.assertEqual(edit["broll"][0]["said"], "fined")

    def test_an_author_cut_in_and_picture_are_kept_and_nothing_asked(self):
        have = {"broll": [{"who": "x", "look": "x", "at": 3}],
                "show": [{"thing": "x", "kind": "thing", "at": 9}]}
        with mock.patch.object(sports_samples, "_brain") as b:
            sports_samples.broll(C, WORDS, 30.0, have)
        b.assert_not_called()

    def test_nothing_showable_leaves_the_clip_alone(self):
        with mock.patch.object(sports_samples, "_brain",
                               return_value={"broll": []}):
            self.assertNotIn("broll", sports_samples.broll(
                C, WORDS, 30.0, {}))
        with mock.patch.object(sports_samples, "_brain", return_value=None):
            self.assertNotIn("broll", sports_samples.broll(
                C, WORDS, 30.0, {}))

    def test_make_asks_and_the_ledger_says_what_was_cut_in(self):
        src = (REPO / "scripts" / "sports_samples.py").read_text()
        self.assertIn('broll(c, words, dur, meta["edit"], raw,', src)
        self.assertIn('"cut_in", "shown",', src)

    def test_the_author_is_told_their_own_plays_count(self):
        self.assertIn("Their OWN plays count", author.SYSTEM)
        self.assertNotIn("Never the person already on screen talking",
                         author.SYSTEM)


if __name__ == "__main__":
    unittest.main()


class APostTheyMentionIsShown(unittest.TestCase):
    """caaleb, 2026-10-28: *"when he says the nfl loves to post me is
    there any reason we can't get screenshots of their instagram and
    overlay them?"*"""
    WORDS = [{"w": w, "s": float(i), "e": i + 0.8} for i, w in enumerate(
        "you know the NFL loves to post me on their page".split())]

    def test_the_post_lands_on_the_word_that_names_it(self):
        ans = {"broll": [], "show": [{
            "thing": "The NFL's Instagram", "kind": "thing", "at": 6.0,
            "said": "post", "look": "NFL Instagram post of Cam Skattebo"}]}
        with mock.patch.object(sports_samples, "_brain", return_value=ans):
            edit = sports_samples.broll(C, self.WORDS, 30.0, {})
        self.assertEqual(edit["show"][0]["thing"], "The NFL's Instagram")
        self.assertEqual(edit["show"][0]["at"], 5.8)       # "post" at 6.0
        self.assertIn("Instagram", edit["show"][0]["look"])
        self.assertNotIn("broll", edit)

    def test_a_post_said_nowhere_near_is_dropped(self):
        ans = {"show": [{"thing": "A tweet", "at": 20, "said": "tweet"},
                        {"thing": "bad", "at": "soon"}]}
        with mock.patch.object(sports_samples, "_brain", return_value=ans):
            self.assertNotIn("show", sports_samples.broll(
                C, self.WORDS, 30.0, {}))

    def test_the_authors_own_cut_ins_are_kept_beside_a_new_picture(self):
        have = {"broll": [{"who": "x", "look": "x", "at": 3}]}
        ans = {"broll": [{"who": "y", "look": "y", "at": 9}], "show": [
            {"thing": "The NFL's Instagram", "at": 6, "said": "post"}]}
        with mock.patch.object(sports_samples, "_brain", return_value=ans):
            edit = sports_samples.broll(C, self.WORDS, 30.0, have)
        self.assertEqual(edit["broll"][0]["who"], "x")
        self.assertTrue(edit["show"])
        self.assertIn("instagram", sports_samples.BROLL_SYSTEM.lower())


class APictureIsSearchedUnderWhoItIsOf(unittest.TestCase):
    """Searched under its caption, "The NFL's Instagram", the funnel found
    two pictures and neither was the post (sample 40733502389)."""

    def test_about_reaches_the_funnel_as_the_entity(self):
        from funnel import find_image, media_funnel
        seen = []
        with mock.patch.object(media_funnel, "search",
                               side_effect=lambda a, e, **k: seen.append(
                                   (a, e[0])) or []):
            find_image.search_urls("The NFL's Instagram",
                                   "NFL Instagram post of Cam Skattebo",
                                   about="Cam Skattebo")
        self.assertEqual(seen[0], ("NFL Instagram post of Cam Skattebo",
                                   "Cam Skattebo"))

    def test_show_it_carries_about_to_the_finder(self):
        from third_capture import show_it
        from funnel import find_image
        items = show_it.plan(show_it.parse([{
            "thing": "The NFL's Instagram", "about": "Cam Skattebo",
            "look": "NFL Instagram post of Cam Skattebo", "at": 6}], 30),
            30.0)
        self.assertEqual(items[0]["about"], "Cam Skattebo")
        with mock.patch.object(find_image, "find",
                               return_value=None) as f:
            show_it.fetch(items[0], Path("/tmp/w"))
        self.assertEqual(f.call_args.kwargs["about"], "Cam Skattebo")


class TheGameItselfGetsNoCutIn(unittest.TestCase):
    def _run(self, talks):
        with mock.patch.object(sports_samples, "talking",
                               return_value=talks), \
             mock.patch.object(sports_samples, "_brain", return_value={
                 "broll": [{"who": "x", "look": "x", "at": 3,
                            "said": "fined"}]}) as b:
            edit = sports_samples.broll(C, WORDS, 30.0, {},
                                        Path("/tmp/raw.mp4"), Path("/tmp/w"))
        return edit, b

    def test_a_broadcast_of_the_play_is_left_alone(self):
        edit, b = self._run(False)
        b.assert_not_called()
        self.assertNotIn("broll", edit)

    def test_a_locker_room_is_asked(self):
        edit, b = self._run(True)
        self.assertTrue(edit["broll"])

    def test_no_brain_to_look_means_nothing_added(self):
        from shared import shot_relevance
        with mock.patch.object(shot_relevance, "judge_panels",
                               return_value=None), \
             mock.patch("funnel.find_footage._frame",
                        return_value=Path("/tmp/f.png")):
            self.assertFalse(sports_samples.talking(
                Path("/tmp/raw.mp4"), {}, 30.0, Path("/tmp/w")))
        with mock.patch.object(shot_relevance, "judge_panels",
                               return_value={0: {"depicts": True},
                                             1: {"depicts": True},
                                             2: {"depicts": False}}), \
             mock.patch("funnel.find_footage._frame",
                        return_value=Path("/tmp/f.png")):
            self.assertTrue(sports_samples.talking(
                Path("/tmp/raw.mp4"), {}, 30.0, Path("/tmp/w")))


class NeverSomeoneElsesEdit(unittest.TestCase):
    def test_a_phone_edit_is_skipped_and_the_judge_refuses_captions(self):
        from funnel import find_footage
        self.assertIn("NOT a fan edit", find_footage.ACTION)
        self.assertIn("if portrait(video):",
                      (REPO / "funnel" / "find_footage.py").read_text())
        fake = mock.Mock(stdout="1080,1920\n")
        with mock.patch("subprocess.run", return_value=fake):
            self.assertTrue(find_footage.portrait(Path("/x.mp4")))
        fake.stdout = "1920,1080\n"
        with mock.patch("subprocess.run", return_value=fake):
            self.assertFalse(find_footage.portrait(Path("/x.mp4")))


class ACutInIsWatchedNotTimed(unittest.TestCase):
    """caaleb, 2026-10-29: "it can't just be 4.5 seconds later ...
    something that checks, is this the beginning of the play? Yes. Is
    this the end of the play? Yes. Did they show what we needed to show?
    Yes ... not just a football play"."""

    def _find(self, watched, room=10.0):
        import tempfile
        from funnel import find_footage
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("funnel.hot_clips.youtube", return_value=[
                    {"url": "https://www.youtube.com/watch?v=x",
                     "title": "Skattebo runs"}]), \
                mock.patch.object(find_footage, "download",
                                  return_value=Path(td) / "v.mp4"), \
                mock.patch.object(find_footage, "portrait",
                                  return_value=False), \
                mock.patch.object(find_footage, "_seconds",
                                  return_value=100.0), \
                mock.patch.object(find_footage, "_frame",
                                  side_effect=lambda v, a, o: o), \
                mock.patch.object(find_footage, "judge", return_value={
                    0: {"depicts": True}}), \
                mock.patch.object(find_footage, "watch",
                                  return_value=watched), \
                mock.patch.object(find_footage, "cut",
                                  side_effect=lambda v, s, n, o: o):
            return find_footage.find("Cam Skattebo", "run", work=td,
                                     secs=room)

    def test_it_runs_from_the_moments_start_to_its_end(self):
        hit = self._find((19.0, 26.5))
        self.assertEqual((hit["from_s"], hit["secs"]), (19.0, 7.5))

    def test_footage_the_watcher_refuses_is_never_cut_in(self):
        self.assertIsNone(self._find(None))

    def test_a_moment_longer_than_the_room_is_not_cut_short(self):
        self.assertIsNone(self._find((10.0, 21.0), room=6.0))

    def test_the_watcher_names_frames_and_they_become_seconds(self):
        import shutil
        import subprocess
        import tempfile
        from funnel import find_footage
        from shared import shot_relevance
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 "testsrc=s=640x360:r=30:d=20", "-c:v", "libx264",
                 str(td / "reel.mp4")], check=True)
            with mock.patch.object(shot_relevance, "watch_moment",
                                   return_value={"shows": True, "begin": 4,
                                                 "end": 15, "why": "a run"}
                                   ) as wm:
                got = find_footage.watch(td / "reel.mp4", 10.0, 20.0,
                                         "a run", "run the ball", "t", td)
            sheets = wm.call_args[0][0]
            self.assertEqual(len(sheets), 3)        # 34 frames, 12 a sheet
            self.assertTrue(all(p.exists() for p in sheets))
            # frame 4 is 2.0 + 4 * 0.5 = 4.0s; frame 15 ends at 9.5 + 0.5
            self.assertEqual(got, (4.0, 10.0))
            with mock.patch.object(shot_relevance, "watch_moment",
                                   return_value={"shows": False,
                                                 "why": "a huddle"}):
                self.assertIsNone(find_footage.watch(
                    td / "reel.mp4", 10.0, 20.0, "a run", "", "t", td))

    def test_a_watchers_answer_is_validated(self):
        from shared import shot_relevance as sr
        self.assertIsNone(sr.moment({"begin": 1}))
        self.assertIsNone(sr.moment({"shows": True, "begin": 5, "end": 5}))
        self.assertIsNone(sr.moment({"shows": True, "begin": "x", "end": 3}))
        self.assertEqual(sr.moment({"shows": False})["shows"], False)
        self.assertEqual(sr.moment({"shows": True, "begin": 2, "end": 9}
                                   )["end"], 9)
        self.assertIn("not just", sr.watch_moment.__doc__)
        self.assertIn("BEGINS", sr._WATCH)

    def test_the_room_is_to_the_next_cut_in_or_the_end(self):
        from third_capture import cut_in
        got = cut_in.plan([{"who": "a", "at": 5}, {"who": "b", "at": 12},
                           {"who": "c", "at": 30}], 36.0)
        self.assertEqual([g["secs"] for g in got], [6.7, 10.0, 5.2])


class NeverTheSamePlayTwice(unittest.TestCase):
    def test_the_second_cut_in_avoids_the_first(self):
        from third_capture import cut_in
        from funnel import find_footage
        calls = []

        def fake(who, look, **kw):
            calls.append(kw.get("avoid"))
            return {"path": f"/x{len(calls)}.mp4", "url": "u", "from_s": 40.0,
                    "secs": 3.2}
        items = [{"who": "Cam Skattebo", "look": "a", "at": 5, "secs": 3.2},
                 {"who": "Cam Skattebo", "look": "b", "at": 15, "secs": 3.2}]
        with mock.patch.object(find_footage, "find", side_effect=fake):
            got = cut_in.ready(items, Path("/tmp"))
        self.assertEqual(calls[0], [])
        self.assertEqual(calls[1], [{"url": "u", "from_s": 40.0}])
        self.assertEqual(len(got), 2)

    def test_find_skips_an_avoided_shot_and_names_each_cut_apart(self):
        src = (REPO / "funnel" / "find_footage.py").read_text()
        self.assertIn("for a in avoid or []", src)
        self.assertIn('_{start:.0f}_cut.mp4', src)


class APhotoOfThemIsNotTheirPost(unittest.TestCase):
    """2026-10-29 sample: "Tatum's post" came up as two game photos of
    Tatum and Brown. The picture judge is told a post must be the post."""

    def test_the_judge_is_told(self):
        from shared import shot_relevance
        p = shot_relevance._PROMPT
        self.assertIn("the picture must BE that thing", p)
        self.assertIn("is NOT their post", p)
        p.format(title="t", shots="s")  # still a valid template
