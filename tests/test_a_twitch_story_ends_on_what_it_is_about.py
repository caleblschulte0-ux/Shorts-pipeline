"""A Twitch story is told the way Baller Bro's are: the moment plays, then
a song over a montage of the bigger thing it is about.

2026-10-28, the operator: "Bro how are stories still broken". Stories cut
out of streams failed because most streams hold no setup, turn and
fallout; Baller Bro's stories work because the story is not in the clip
(third_capture/outro.py). So an extended clip that passes its measured
checks is asked for that outro, and with one it is a story."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))
sys.path.append(str(REPO / "scripts"))

import run_third  # noqa: E402
from third_capture import outro  # noqa: E402


def _cluster():
    return {"who": "xqc", "clips": [{
        "source_url": "https://clips.twitch.tv/abc", "channel": "xqc",
        "title": "xqc on ethan", "views": 900,
        "internet": {"post_title": "xQc on Ethan Klein",
                     "permalink": "/r/LivestreamFail/x"}}]}


_LED = {"final_words": [{"w": "cheater", "s": 0.0, "e": 0.4}],
        "duration_s": 40.0}


class TheExtendedClipIsAskedForItsStory(unittest.TestCase):
    def test_an_outro_the_author_names_is_built_onto_the_cut(self):
        authored = {"edit": {"outro": {
            "song": "x", "who": "Ethan Klein",
            "looks": ["xQc Ethan Klein h3", "Ethan Klein xQc debate"],
            "team": "H3", "numbers": ["1"]}}}
        built = {"song": "s", "shots": ["a", "b"], "secs": 14.0}
        with mock.patch.object(run_third.author, "author_package",
                               return_value=authored) as ap, \
                mock.patch.object(outro, "parse",
                                  side_effect=lambda r: dict(r)), \
                mock.patch.object(outro, "build",
                                  return_value=built) as b:
            got = run_third._payoff_outro(Path("cut.mp4"), _LED,
                                          _cluster(), Path("w"))
        self.assertEqual(got, built)
        self.assertIn("STORY", ap.call_args.kwargs["guidance"])
        item = b.call_args.args[1]
        # Twitch has no jerseys: the shots are checked by who they show
        self.assertEqual((item["team"], item["numbers"]), ("", []))
        # never the clip itself again as its own ending
        self.assertIn("https://clips.twitch.tv/abc", item["avoid"])

    def test_no_outro_means_an_extended_clip(self):
        with mock.patch.object(run_third.author, "author_package",
                               return_value={"edit": {"outro": None}}), \
                mock.patch.object(outro, "build") as b:
            self.assertIsNone(run_third._payoff_outro(
                Path("cut.mp4"), _LED, _cluster(), Path("w")))
        b.assert_not_called()

    def test_a_failure_never_costs_the_clip(self):
        with mock.patch.object(run_third.author, "author_package",
                               side_effect=RuntimeError("down")):
            self.assertIsNone(run_third._payoff_outro(
                Path("cut.mp4"), _LED, _cluster(), Path("w")))


class TheArmIsWired(unittest.TestCase):
    def test_with_an_outro_it_is_a_story_without_one_an_extended_clip(self):
        src = (REPO / "scripts" / "run_third.py").read_text()
        self.assertIn('spec.get("story_payoff")', src)
        self.assertIn("_extended = not _payoff", src)
        bt = (REPO / "scripts" / "story_backtest.py").read_text()
        self.assertIn('"story_payoff"', bt)


if __name__ == "__main__":
    unittest.main()
