"""A story is told across months of streams, not one moment extended.

2026-10-21, the operator of four well-cut single moments: "those weren't
stories". The most-viewed streamer story shorts in the clipper study (run
39688618528) are origins, histories and betrayals told across streams
months or years apart, so the saga arm reads a streamer's whole history
(`clip_edit.history`) and the scout is told to find one."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))

from third_capture import clip_edit, story_director  # noqa: E402


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self._d}


class TheHistoryReachesBackYears(unittest.TestCase):
    def test_every_quarter_is_asked_for_its_own_top_clips(self):
        asked = []

        def get(url, params=None, headers=None, timeout=None):
            asked.append((params["started_at"], params["ended_at"]))
            return _Resp([{"url": f"https://clips.twitch.tv/c{len(asked)}",
                           "view_count": 1000, "duration": 30,
                           "title": "t", "id": f"c{len(asked)}",
                           "created_at": params["started_at"],
                           "vod_offset": None, "video_id": ""}])
        with mock.patch.object(clip_edit, "_helix_creds", return_value=True), \
                mock.patch.object(clip_edit, "_helix_user_id",
                                  return_value="1"), \
                mock.patch.object(clip_edit, "_helix_headers",
                                  return_value={}), \
                mock.patch("requests.get", side_effect=get):
            out = clip_edit.history("kaicenat", years=3, top=5)
        # three years of quarters, each window ending where the next began
        self.assertGreaterEqual(len(asked), 12)
        for (s0, _), (_, e1) in zip(asked, asked[1:]):
            self.assertEqual(s0, e1)
        self.assertEqual(len(out), len(asked))
        self.assertTrue(all(c["channel"] == "kaicenat" for c in out))

    def test_no_credentials_means_no_history(self):
        with mock.patch.object(clip_edit, "_helix_creds", return_value=False):
            self.assertEqual(clip_edit.history("kaicenat"), [])


class TheScoutLooksForASaga(unittest.TestCase):
    def test_the_saga_brief_reaches_the_scout(self):
        seen = {}

        def brain(prompt, system):
            seen["system"] = system
            return {"stories": [{"members": ["C1", "C2", "C3"],
                                 "premise": "When Kai met Tota",
                                 "why_connected": "x", "shape": "saga"}]}
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            out = story_director.scout_stories(
                ["C1 | a", "C2 | b", "C3 | c"], {"C1", "C2", "C3"},
                saga=True)
        self.assertIn("SAGA", seen["system"])
        self.assertIn("ORIGIN", seen["system"])
        self.assertEqual(out[0]["shape"], "saga")

    def test_the_ordinary_scout_is_unchanged(self):
        seen = {}

        def brain(prompt, system):
            seen["system"] = system
            return {"stories": []}
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            story_director.scout_stories(["C1 | a", "C2 | b"], {"C1", "C2"})
        self.assertEqual(seen["system"], story_director._SCOUT_SYSTEM)


class TheArmIsWired(unittest.TestCase):
    def test_the_saga_arm_reads_history_and_only_its_own_proposals(self):
        src = (REPO / "scripts" / "run_third.py").read_text()
        self.assertIn('spec.get("story_pick") == "saga"', src)
        self.assertIn("clip_edit.history(", src)
        self.assertIn("saga=_saga", src)
        self.assertIn("clusters = scouted", src)
        self.assertIn("_SAGA_CUT if _saga", src)
        bt = (REPO / "scripts" / "story_backtest.py").read_text()
        self.assertIn('"saga"', bt)


if __name__ == "__main__":
    unittest.main()
