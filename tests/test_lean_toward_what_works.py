"""The sports picker is shown the channel's own hits and flops, and a bio
change touches only the description (operator, 2026-11-05)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import channel_about as ca
from scripts import sports_samples as ss


def _vids(n, age=100):
    return [{"format": "sports_moment", "title": f"clip {i}", "views": i * 10,
             "age_hours": age} for i in range(n)]


class ThePickerSeesWhatWorked(unittest.TestCase):
    def _write(self, vids):
        d = Path(tempfile.mkdtemp()) / "latest.json"
        d.write_text(json.dumps({"videos": vids}))
        return d

    def test_hits_and_flops_are_named(self):
        txt = ss.track_record(self._write(_vids(20)))
        hits, flops = txt.split("Least watched:")
        self.assertIn("clip 19", hits)
        self.assertIn("clip 0", flops)
        self.assertNotIn("clip 0\n", hits)
        self.assertIn("lean", txt.lower())

    def test_too_young_or_too_few_says_nothing(self):
        self.assertEqual(ss.track_record(self._write(_vids(20, age=10))), "")
        self.assertEqual(ss.track_record(self._write(_vids(5))), "")
        self.assertEqual(ss.track_record(Path("/nonexistent.json")), "")

    def test_only_the_newest_posts_count(self):
        old = [{"format": "sports_moment", "title": f"old {i}", "views": 0,
                "age_hours": 900, "published_at": "2026-01-01"}
               for i in range(30)]
        new = [{**v, "published_at": "2026-11-01"} for v in _vids(40)]
        self.assertNotIn("old ", ss.track_record(self._write(old + new)))

    def test_other_formats_are_not_examples(self):
        v = _vids(20) + [{"format": "graph_race", "title": "a graph",
                          "views": 99999, "age_hours": 500}]
        self.assertNotIn("a graph", ss.track_record(self._write(v)))

    def test_pick_sends_it_to_the_brain(self):
        seen = {}
        with mock.patch.object(ss, "track_record", return_value="\nTRACK"), \
                mock.patch.object(ss, "_brain",
                                  side_effect=lambda u, s: seen.update(s=s)):
            ss.pick([{"sub": "nba", "upvotes": 1, "platform": "v",
                      "post_title": "t", "url": "u"}], 1)
        self.assertTrue(seen["s"].endswith("TRACK"))
        self.assertTrue(seen["s"].startswith(ss.PICK_SYSTEM))


class TheBioChangesOnlyTheDescription(unittest.TestCase):
    def test_other_branding_survives(self):
        b = {"channel": {"keywords": "nba nfl", "country": "US",
                         "description": "old"}}
        self.assertEqual(ca.with_description(b, "new"),
                         {"channel": {"keywords": "nba nfl", "country": "US",
                                      "description": "new"}})
        self.assertEqual(b["channel"]["description"], "old")

    def test_youtube_refusals_are_caught_first(self):
        self.assertTrue(ca.problems("a <b>"))
        self.assertTrue(ca.problems("x" * 1001))
        self.assertTrue(ca.problems("  "))
        self.assertEqual(ca.problems("Sports moments, every day."), [])

    def test_trending_uses_the_original_token(self):
        self.assertEqual(ca.token_slug("trending"), "")
        self.assertEqual(ca.token_slug("third"), "third")


if __name__ == "__main__":
    unittest.main()
