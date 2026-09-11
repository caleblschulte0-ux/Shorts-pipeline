"""Doctor finding 2127c6395c2c: unclassified Third clips must be labeled
"unknown", never silently folded into "chaos".

`third_capture/author.py` used to default any empty/invalid `series` value
straight to "chaos" -- so a clip the model failed to classify and a clip
the model genuinely called chaotic were indistinguishable in the posted
log and analytics. That made chaos look like both the channel's biggest
AND its weakest-performing series when part of the bucket was really
"we don't know". These tests hold the fix: `_postprocess` must reject
anything outside the documented series enum by calling it "unknown", and
`scripts/third_series_audit.py` must keep "unknown"/"story" out of the
content-mix comparison.

    python -m unittest tests.test_third_series_labels -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from third_capture import author                       # noqa: E402
from scripts import third_series_audit as audit_mod     # noqa: E402


def _out(**series_kwargs) -> dict:
    base = {
        "title": "Streamer Reacts To Something Wild",
        "hook": "WAIT FOR IT",
        "caption": "a normal caption",
        "cta": "Who's side are you on?",
        "hashtags": ["clips", "streamerclips"],
        "edit": {"slam": "", "emoji": "", "replay_worthy": True,
                  "complete": True},
    }
    base.update(series_kwargs)
    return base


class TestSeriesLabel(unittest.TestCase):
    def test_valid_series_passes_through(self):
        out = author._postprocess(_out(series="wholesome"), "streamer",
                                   "context text")
        self.assertEqual(out["series"], "wholesome")

    def test_empty_series_becomes_unknown_not_chaos(self):
        out = author._postprocess(_out(series=""), "streamer", "context")
        self.assertEqual(out["series"], "unknown")

    def test_missing_series_key_becomes_unknown(self):
        payload = _out()
        payload.pop("series", None)
        out = author._postprocess(payload, "streamer", "context")
        self.assertEqual(out["series"], "unknown")

    def test_invented_series_value_becomes_unknown(self):
        # a value outside the documented enum -- the model went off-script,
        # this must not be silently trusted OR silently marked "chaos".
        out = author._postprocess(_out(series="epic-moment"), "streamer",
                                   "context")
        self.assertEqual(out["series"], "unknown")

    def test_chaos_still_reachable_when_actually_chosen(self):
        out = author._postprocess(_out(series="chaos"), "streamer",
                                   "context")
        self.assertEqual(out["series"], "chaos")

    def test_every_documented_enum_value_is_valid(self):
        # keep _VALID_SERIES in sync with the SYSTEM prompt's own enum
        documented = {"drama", "beef", "rage", "chat-betrayal", "jumpscare",
                      "clutch", "fail", "win", "wholesome", "argument",
                      "chaos"}
        self.assertEqual(documented, author._VALID_SERIES)


class TestSeriesAudit(unittest.TestCase):
    def _video(self, series, vph, age=100.0):
        return {"series": series, "views_per_hour": vph, "age_hours": age}

    def test_unknown_and_story_excluded_from_content_comparison(self):
        videos = [
            self._video("chaos", 1.0), self._video("chaos", 2.0),
            self._video("unknown", 50.0), self._video("unknown", 60.0),
            self._video("story", 90.0),
        ]
        report = audit_mod.audit(videos)
        self.assertIn("chaos", report["content_series"])
        self.assertNotIn("unknown", report["content_series"])
        self.assertNotIn("story", report["content_series"])
        self.assertIn("unknown", report["excluded"])
        self.assertIn("story", report["excluded"])
        self.assertEqual(report["content_series"]["chaos"]["n"], 2)
        self.assertEqual(report["content_series"]["chaos"]["median_vph"], 1.5)

    def test_immature_videos_are_dropped(self):
        videos = [self._video("fail", 5.0, age=10.0),
                  self._video("fail", 9.0, age=200.0)]
        report = audit_mod.audit(videos)
        self.assertEqual(report["content_series"]["fail"]["n"], 1)
        self.assertEqual(report["content_series"]["fail"]["median_vph"], 9.0)

    def test_missing_series_field_reads_as_unknown_not_dropped(self):
        videos = [{"views_per_hour": 3.0, "age_hours": 100.0}]
        report = audit_mod.audit(videos)
        self.assertEqual(report["excluded"]["unknown"]["n"], 1)

    def test_malformed_snapshot_never_raises(self):
        self.assertEqual(audit_mod.load_videos(Path("/no/such/file.json")),
                          [])
        self.assertEqual(audit_mod.audit([])["content_series"], {})


if __name__ == "__main__":
    unittest.main()
