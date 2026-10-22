"""A story has no narrator: what the edit says is a line of text on screen.

Operator, 2026-10-08: *"No narrator but like any clip your allowed like a
line or 2 of text on the screen"*, with three reposts as the look — one
short sentence-case line mid-frame ("Los thought he ended stream"), white
with a black outline, no box, there the whole clip. And the line may say
who someone is when the footage never does: the critic's most frequent
refusal across story backtests 6-11 was a stranger not knowing who Reggie,
Ron or Bruce was. That "who" comes from general knowledge only when a
second, different model agrees it is accurate.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import story, story_director     # noqa: E402


class ThereIsNoVoice(unittest.TestCase):
    def test_the_renderer_has_no_text_to_speech(self):
        src = (ROOT / "third_capture" / "story.py").read_text()
        for gone in ("edge-tts", "_maybe_narration", "_mix_narration",
                     "sidechaincompress"):
            self.assertNotIn(gone, src)

    def test_the_director_is_told_it_is_text(self):
        self.assertIn("there is NO voice-over", story_director._PLAN_SYSTEM)
        self.assertIn("on-screen TEXT (never a voice)",
                      story_director._REVISE_SYSTEM)


class OneCaptionAtATime(unittest.TestCase):
    HOOK = "Los thought he ended stream"

    def test_the_hook_is_read_first_and_stays(self):
        caps = story.beat_captions(0, 12.0, self.HOOK, "",
                                   "Reggie is Kai Cenat's cousin")
        self.assertEqual([c["kind"] for c in caps], ["title", "text", "title"])
        self.assertEqual(caps[0]["at"], 0.0)
        self.assertAlmostEqual(caps[-1]["at"] + caps[-1]["secs"], 12.0)

    def test_later_beats_keep_the_hook_around_their_overlay(self):
        caps = story.beat_captions(1, 3.0, self.HOOK, "Minutes later", "")
        self.assertEqual([c["kind"] for c in caps], ["overlay", "title"])

    def test_they_never_overlap_and_never_outlast_the_beat(self):
        for secs in (0.8, 2.0, 4.0, 9.0):
            caps = story.beat_captions(0, secs, self.HOOK, "Earlier that day",
                                       "Reggie is Kai Cenat's cousin")
            for a, b in zip(caps, caps[1:]):
                self.assertLessEqual(a["at"] + a["secs"], b["at"] + 1e-6)
            for c in caps:
                self.assertLessEqual(c["at"] + c["secs"], secs + 1e-6)

    def test_a_time_jump_is_up_long_enough_to_read(self):
        caps = story.beat_captions(1, 8.0, self.HOOK, "Two days later", "")
        self.assertGreaterEqual(caps[0]["secs"], 2.5)

    def test_no_hook_no_words_no_caption(self):
        self.assertEqual(story.beat_captions(1, 5.0), [])


class ItLooksLikeTheReposts(unittest.TestCase):
    def test_outlined_white_no_box_one_font(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = story._overlay_draw("Los thought he ended stream", Path(td),
                                    "x", y=story.CAPTION_Y, size=64,
                                    start=0.0, dur=2.0)
        self.assertNotIn("box=1", f)
        self.assertIn("borderw=", f)
        self.assertIn("bordercolor=black", f)
        self.assertIn(story.CAPTION_FONT, f)
        self.assertTrue(Path(story.CAPTION_FONT).exists())

    def test_it_sits_in_the_bottom_third(self):
        # two lines at 64px still end above the platform's bottom bar
        self.assertGreaterEqual(story.CAPTION_Y, story.CANVAS_H * 2 // 3)
        self.assertLess(story.CAPTION_Y + 2 * 80, story.CANVAS_H - 300)

    def test_the_hook_keeps_its_case(self):
        from tests.test_the_story_critic_sees_the_whole_edit import _edl
        v = story_director.validate_edl(_edl("Los thought he ended stream"),
                                        {"a": 60.0, "b": 60.0})
        self.assertEqual(v["hook_overlay"], "Los thought he ended stream")


class TheCriticKnowsTheCaptionStays(unittest.TestCase):
    """Backtest 12: 12 of 27 cuts were marked down because the title was
    "repeated across the entire video" — listed to the critic once per
    piece, it read as a card shown over and over, when staying up IS the
    format."""

    def test_the_caption_is_listed_once_as_the_format(self):
        caps = (story.beat_captions(0, 8.0, "Los thought he ended stream",
                                    "", "Los is xQc's friend")
                + [dict(c, at=c["at"] + 8.0) for c in story.beat_captions(
                    1, 6.0, "Los thought he ended stream",
                    "Minutes later", "")])
        brief = story_director._fmt_on_screen(caps)
        self.assertEqual(brief.count("Los thought he ended stream"), 1)
        self.assertIn("on screen the whole video by design", brief)
        self.assertIn('ON-SCREEN TEXT: "Los is xQc\'s friend"', brief)
        self.assertIn('ON-SCREEN OVERLAY: "Minutes later"', brief)


class WhoSomeoneIsIsCheckedTwice(unittest.TestCase):
    def setUp(self):
        story_director._WHO_CACHE.clear()
        from funnel import feeds
        p = mock.patch.object(feeds, "entries", return_value=[])
        self.entries = p.start()
        self.addCleanup(p.stop)

    def _run(self, proposed, verdict):
        with mock.patch.object(story_director, "_call_claude",
                               return_value={"who": proposed}), \
                mock.patch.object(story_director, "_call_text_fallback",
                                  return_value={"ok": verdict}) as v:
            out = story_director.known_people(
                "kaicenat", ["Reggie", "Bruce", "kaicenat"])
        return out, v

    def test_only_what_the_second_model_confirms_is_kept(self):
        out, _ = self._run({"Reggie": "Kai Cenat's cousin",
                            "Bruce": "a streamer in AMP"},
                           {"Reggie": True, "Bruce": False})
        self.assertEqual(out, {"Reggie": "Kai Cenat's cousin"})

    def test_events_and_accusations_never_reach_the_checker(self):
        out, v = self._run({"Reggie": "accused Kai of ghosting him",
                            "Bruce": None},
                           {"Reggie": True})
        self.assertEqual(out, {})
        v.assert_not_called()

    def test_the_streamer_is_not_asked_about(self):
        seen = {}

        def claude(user, system=None, **k):
            seen["user"] = user
            return {"who": {}}
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=claude):
            story_director.known_people("kaicenat", ["KaiCenat", "Reggie"])
        self.assertNotIn('"KaiCenat"', seen["user"])

    def test_the_analysis_descriptions_become_bare_names(self):
        # backtest 25's own `people` strings: asked verbatim, the news
        # found 0 headlines and both models answered None for Reggie.
        seen = {}

        def claude(user, system=None, **k):
            seen["user"] = user
            return {"who": {}}
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=claude):
            story_director.known_people("kaicenat", [
                "Kai Cenat (streamer, speaking to camera)",
                "Reggie (the contact in the on-screen tex",
                "Rod (mentioned, not shown)", "a shirtless friend",
                "Other players on the side facecams", "Reggie"])
        self.assertIn('NAMES: ["Reggie", "Rod"]', seen["user"])
        self.assertIn("Reggie", self.entries.call_args_list[0].args[0])
        self.assertNotIn("contact", self.entries.call_args_list[0].args[0])

    def test_a_login_with_an_underscore_is_still_the_streamer(self):
        # backtest 27 asked who "Joe Bartolozzi" is to joe_bartolozzi
        seen = {}

        def claude(user, system=None, **k):
            seen["user"] = user
            return {"who": {}}
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=claude):
            story_director.known_people(
                "joe_bartolozzi", ["Joe Bartolozzi", "Twitch", "Franklin"])
        self.assertIn('NAMES: ["Franklin"]', seen["user"])

    def test_a_dead_brain_costs_nothing(self):
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=RuntimeError("down")):
            self.assertEqual(
                story_director.known_people("kaicenat", ["Reggie"]), {})

    def test_a_confirmed_who_may_be_said_on_screen(self):
        rep = [{"source_id": "a", "channel": "kaicenat", "duration_s": 9,
                "summary": "Reggie talks", "people": ["Reggie"],
                "known_people": {"Reggie": "Kai Cenat's cousin"}}]
        self.assertTrue(story_director.narration_grounded(
            "Reggie is Kai Cenat's cousin", rep))
        self.assertFalse(story_director.narration_grounded(
            "Reggie is Kai Cenat's cousin", [dict(rep[0], known_people={})]))
        self.assertIn("Reggie = Kai Cenat's cousin",
                      story_director._fmt_reports(rep))

    def test_someone_too_new_for_the_models_is_found_in_the_news(self):
        """Backtest 24 (2026-10-12): every Kai/Reggie cut failed on "who
        is Reggie?" — no model knew him, the press did."""
        self.entries.return_value = [
            {"title": "Kai Cenat Says He Is Suing Reggie, his former "
                      "friend", "published": "Thu, 01 Oct 2026"}]
        seen = []

        def claude(user, system=None, **k):
            seen.append(user)
            return {"who": {"Reggie": "Kai Cenat's former friend"}}

        def verify(user, system=None, **k):
            seen.append(user)
            return {"ok": {"Reggie": True}}
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=claude), \
                mock.patch.object(story_director, "_call_text_fallback",
                                  side_effect=verify):
            out = story_director.known_people("kaicenat", ["Reggie"])
        self.assertEqual(out, {"Reggie": "Kai Cenat's former friend"})
        self.assertTrue(all("his former friend" in u for u in seen))
        self.assertEqual(len(seen), 2)
        url = self.entries.call_args[0][0]
        self.assertIn("news.google.com", url)
        self.assertIn("Reggie", url)
        self.assertIn("Kai+Cenat", url)   # the name people write, not the login

    def test_no_news_is_no_harm(self):
        self.entries.side_effect = RuntimeError("offline")
        out, _ = self._run({"Reggie": "Kai Cenat's cousin"},
                           {"Reggie": True})
        self.assertEqual(out, {"Reggie": "Kai Cenat's cousin"})

    def test_the_people_the_premise_names_are_looked_up_too(self):
        """Live run 2026-10-12: the scout wrote "Tony rugs" Buddha, the
        scene analysis saw "a suited man", and the critic held the story
        at 68 for never saying who he is."""
        self.assertEqual(story_director.premise_names(
            "Buddha is promised his coin will pump, then loses $800 when "
            "Tony rugs him"), ["Tony"])
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn("story_director.premise_names(", src)

    def test_a_short_form_of_the_streamer_is_not_asked_about(self):
        seen = {}

        def claude(user, system=None, **k):
            seen["user"] = user
            return {"who": {}}
        with mock.patch.object(story_director, "_call_claude",
                               side_effect=claude):
            story_director.known_people("kaicenat", ["Kai", "Ron"])
        self.assertNotIn('"Kai"', seen["user"])
        self.assertIn('"Ron"', seen["user"])

    def test_the_story_is_about_the_followed_streamer_not_the_clipper(self):
        """Live run 2026-10-12: the Kai/Reggie story's first source was the
        27club clip channel, so Reggie was looked up "to 27club"."""
        reps = [{"channel": "27club"}, {"channel": "kaicenat"},
                {"channel": "xevi"}]
        self.assertEqual(story_director.lead_streamer(reps), "kaicenat")
        self.assertEqual(story_director.lead_streamer(
            [{"channel": "27club"}], ["27club", "kaicenat"]), "kaicenat")
        self.assertEqual(story_director.lead_streamer(
            [{"channel": "someone"}]), "someone")
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn("story_director.lead_streamer(", src)

    def test_the_story_arm_asks(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn("story_director.known_people(", src)


if __name__ == "__main__":
    unittest.main()
