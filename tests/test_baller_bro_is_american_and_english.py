"""Baller Bro posts American sports plus soccer, in English, and never a
cut too short to hold a moment — held in CODE, so it holds whichever model
is running (operator, 2026-11-11: "no more videos that aren't English, and
no more weird-ass sports ... some clips were like 2 seconds long ... I'm
going to have this run on a local model")."""
import json
import unittest
from pathlib import Path
from unittest import mock

from scripts import claim_reviews as cr
from scripts import sports_samples as ss
from shared import channel_registry, sports_scope as sc


def _words(text, start=0.0, step=0.4):
    return [{"w": w, "s": start + i * step, "e": start + i * step + 0.3}
            for i, w in enumerate(text.split())]


class OnlyAmericanSportsAndSoccer(unittest.TestCase):
    def test_the_week_the_fallbacks_ran_is_refused(self):
        for sub, title in [
            ("sports", "Lightest active sumo wrestler made his debut today"),
            ("sports", "Nathan Lyon gets offered sandpaper by a fan"),
            ("sports", "South Africa fan heckles at the Test match"),
            ("baseball", "NPB walk-off in the Japan Series"),
            ("hockey", "KHL brawl in the third period"),
            ("sports", "Rugby player's try celebration"),
        ]:
            self.assertTrue(sc.out_of_scope(sub, title), (sub, title))

    def test_american_sports_and_soccer_pass(self):
        for sub, title in [
            ("nfl", "Mike Tomlin says the Cowboys have blinkers"),
            ("nba", "Luka confronts a fan"),
            ("sports", "Brewers fan shows a photo of her dad"),
            ("sports", "Winnipeg Jets pull off a four-goal comeback"),
            ("soccer", "Matheus Cunha dives into the stands"),
            ("CollegeBasketball", "Justus McNair wins it for Valparaiso"),
            ("MMA", "Conor McGregor dying laughing"),
        ]:
            self.assertEqual(sc.out_of_scope(sub, title), "", (sub, title))

    def test_a_catch_all_sub_must_name_an_american_sport(self):
        self.assertTrue(sc.out_of_scope("sports", "Wild finish to the final"))
        self.assertTrue(sc.out_of_scope("formula1", "Verstappen wins"))

    def test_the_policy_is_the_registry(self):
        scope = channel_registry.format_spec(
            "trending", "sports_moment")["scope"]
        self.assertEqual(scope["language"], "en")
        self.assertEqual(tuple(scope["sources"]), ss.SUBS)
        self.assertGreaterEqual(scope["min_cut_s"], 15)

    def test_the_picker_never_sees_an_out_of_scope_post(self):
        seen = {}
        pool = [{"sub": "sports", "upvotes": 9, "platform": "v",
                 "post_title": "Sumo debut", "url": "a"},
                {"sub": "nfl", "upvotes": 1, "platform": "v",
                 "post_title": "Tomlin rant", "url": "b"}]
        with mock.patch.object(ss, "_brain",
                               side_effect=lambda u, s: seen.update(u=u)):
            out = ss.pick(pool, 1)
        self.assertNotIn("Sumo", seen["u"])
        self.assertEqual([c["url"] for c in out], ["b"])


class OnlyEnglish(unittest.TestCase):
    def test_whisper_hears_the_language(self):
        w = _words("hola " * 20)
        with mock.patch.object(sc, "english_probability", return_value=0.04):
            self.assertIn("not English", sc.not_english(Path("x"), w))
        with mock.patch.object(sc, "english_probability", return_value=0.93):
            self.assertEqual(sc.not_english(Path("x"), w), "")

    def test_without_whisper_the_words_still_tell(self):
        spanish = _words("Os pido perdón porque os acompaño y la verdad "
                         "es que no puedo decir más que esto")
        english = _words("I just want to say that the guys played hard "
                         "and we are going to get it done")
        with mock.patch.object(sc, "english_probability", return_value=None):
            self.assertIn("not English", sc.not_english(Path("x"), spanish))
            self.assertEqual(sc.not_english(Path("x"), english), "")

    def test_a_crowd_with_no_words_is_not_a_language(self):
        with mock.patch.object(sc, "english_probability", return_value=0.0):
            self.assertEqual(sc.not_english(Path("x"), _words("goal goal")), "")


class NeverTooShort(unittest.TestCase):
    def test_tomlins_two_seconds_are_widened_back_to_the_setup(self):
        words = (_words("We had a great week of practice.", 20)
                 + _words("I told them to stay sharp.", 30)
                 + _words("They're blinkers.", 41.7)
                 + _words("They've got to cut their eyelids off.", 42.5))
        edit = {"cut": {"start": 41.4, "end": 44.6}}
        ss.hold_length(edit, words, 44.8, min_s=15)
        lo, hi = edit["cut"]["start"], edit["cut"]["end"]
        self.assertGreaterEqual(hi - lo, 15)
        self.assertEqual(hi, 44.6)          # the payoff the brain chose stays
        self.assertLess(lo, 41.4)

    def test_never_opens_mid_sentence(self):
        words = _words("We don't know anything else about Jack yet.", 10.0)
        edit = {"cut": {"start": 11.0, "end": 40.0}}
        ss.hold_length(edit, words, 45.0, min_s=15)
        self.assertLessEqual(edit["cut"]["start"], 10.0)
        self.assertEqual(edit["cut"]["end"], 40.0)

    def test_never_past_a_broadcast_card(self):
        edit = {"cut": {"start": 0.0, "end": 8.0}, "card_at": 12.0}
        ss.hold_length(edit, _words("a b c", 1), 60.0, min_s=15)
        self.assertLessEqual(edit["cut"]["end"], 12.0)

    def test_a_long_cut_is_left_alone(self):
        edit = {"cut": {"start": 3.0, "end": 25.0}}
        ss.hold_length(edit, [], 40.0, min_s=15)
        self.assertEqual(edit["cut"], {"start": 3.0, "end": 25.0})

    def test_the_render_floor(self):
        self.assertTrue(sc.too_short(3.0))
        self.assertEqual(sc.too_short(22.0), "")

    def test_the_run_checks_before_and_after_the_judge(self):
        src = Path(ss.__file__).with_name("run_sports.py").read_text()
        self.assertEqual(src.count("sports_scope.too_short("), 2)
        self.assertIn("ss.not_english(info)", src)
        self.assertIn("hold_length(meta[\"edit\"]", Path(ss.__file__).read_text())


class TheMailboxCannotPostThemEither(unittest.TestCase):
    def _req(self, dur, title, topic):
        return {"channel": "trending", "id": "r", "slug": "s", "title": title,
                "temporal": {"duration_s": dur},
                "ctx": {"package": "config/channel_registry.json",
                        "topic": topic}}

    def test_too_short_or_out_of_scope_is_unpublishable(self):
        self.assertIn("too short", cr.unpublishable(self._req(
            3.0, "Tomlin", "https://www.reddit.com/r/nfl/comments/x/y")))
        self.assertIn("American", cr.unpublishable(self._req(
            30.0, "Lyon gets sandpaper",
            "https://www.reddit.com/r/sports/comments/x/y")))
        self.assertIsNone(cr.unpublishable(self._req(
            30.0, "Tomlin", "https://www.reddit.com/r/nfl/comments/x/y")))

    def test_a_grade_on_a_floored_request_holds(self):
        req = self._req(3.0, "Tomlin",
                        "https://www.reddit.com/r/nfl/comments/x/y")
        with mock.patch.object(cr.rm, "verdict_for", return_value=({}, "")), \
                mock.patch.object(cr.rm, "grader_of", return_value="chatgpt"), \
                mock.patch.object(cr.rm, "verdict_by", return_value="chatgpt"), \
                mock.patch.object(cr.rm, "settle") as settle:
            out = cr.claim(req, publish=True, workdir=Path("/tmp"))
        self.assertEqual(out["decision"], "hold")
        settle.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class CodeChecksTheFramersLook(unittest.TestCase):
    """A weak framer that says "whole frame" for a podium shot leaves the
    speaker a thumbnail in a blurred band (Golden, Frelick, Nov 2026)."""

    def _an(self, faces):
        from third_capture import shot_plan as sp  # noqa: F401
        ts = [round(i / 6, 3) for i in range(60)]
        dets = [(t, cx, 540.0, float(h), "frontal")
                for (cx, h) in faces for t in ts]
        return {"sw": 1920, "sh": 1080, "dur": 10.0, "fps": 30.0,
                "cuts": [], "ts": ts, "dets": dets, "samples": len(ts),
                "subjects": [], "col_energy": [1.0] * 1920,
                "col_detail": [1.0] * 1920}

    def _framed(self, an, answer):
        from third_capture import shot_plan as sp
        with mock.patch("shared.shot_relevance.enabled", return_value=True), \
                mock.patch("shared.shot_relevance.frame_shots",
                           return_value={0: answer}), \
                mock.patch.object(sp, "_column_frame",
                                  return_value=Path("f.png")):
            return sp.framed(an, Path("x.mp4"), Path("/tmp"), "t")

    def test_whole_frame_on_one_speaker_is_overruled(self):
        out = self._framed(self._an([(1500, 300)]),
                           {"whole": True, "why": "a press room"})
        w, _h, x, _y = out[0]["crop"]
        self.assertTrue(x <= 1500 <= x + w)
        self.assertIn("overruled", out[0]["why"])

    def test_columns_that_miss_the_speaker_are_overruled(self):
        out = self._framed(self._an([(1500, 300)]),
                           {"cols": (0, 2), "why": "the backdrop"})
        w, _h, x, _y = out[0]["crop"]
        self.assertTrue(x <= 1500 <= x + w)

    def test_two_faces_far_apart_stay_whole(self):
        out = self._framed(self._an([(300, 250), (1650, 250)]),
                           {"whole": True, "why": "too far apart"})
        self.assertIsNone(out[0]["crop"])

    def test_no_face_trusts_the_look(self):
        out = self._framed(self._an([]), {"whole": True, "why": "a crowd"})
        self.assertIsNone(out[0]["crop"])
