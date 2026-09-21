"""THE RETRO MEASURES WHETHER THE BESPOKE PICTURES PAY, INSTEAD OF ASSERTING IT.

Operator, 2026-09-21: *"every time we have a good one of those [per-video
animations], the video gets a ton of views."* That is a claim about
retention, and until now nothing in the repo could check it: the judge's
per-depiction grades went to the verdict log and the library, and the retro
brief read analytics. `build_retro.depictions_vs_performance` joins the two
— best `bespoke` grade per video, from the LAST verdict for its slug, against
views-per-hour on videos old enough to have been watched — and is honest
about thinness: a bucket under `MIN_SAMPLES` is labelled thin, and videos
that shipped before the judge graded depictions are counted as `ungraded`,
never guessed.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_retro as BR                        # noqa: E402


def _video(slug, vph, age=48.0):
    return {"catalog_id": slug, "views": vph * age, "age_hours": age,
            "published_at": "2026-09-01T00:00:00Z", "title": slug}


def _verdict(slug, grades):
    return json.dumps({"slug": slug, "verdict": "ship", "score": 80,
                       "depictions": [{"id": f"seg{i}", "kind": "bespoke",
                                       "bespoke": g, "proves_claim": g}
                                      for i, g in enumerate(grades)]})


class TheJoinIsHonest(unittest.TestCase):
    def _run(self, videos, lines, min_samples=1):
        with tempfile.TemporaryDirectory() as td:
            ap = Path(td) / "latest.json"
            ap.write_text(json.dumps({"videos": videos}))
            lp = Path(td) / "verdicts.jsonl"
            lp.write_text("\n".join(lines) + "\n")
            with mock.patch.object(BR, "ROOT", Path(td)), \
                    mock.patch.object(BR, "MIN_SAMPLES", min_samples):
                return BR.depictions_vs_performance("latest.json", verdict_log=lp)

    def test_videos_are_bucketed_by_their_best_grade(self):
        out = self._run(
            [_video("a", 10.0), _video("b", 2.0), _video("c", 1.0)],
            [_verdict("a", [1, 3]), _verdict("b", [1, 1]), _verdict("c", [0])])
        self.assertEqual(out["buckets"]["tier1_bespoke"]["n"], 1)
        self.assertEqual(out["buckets"]["tier1_bespoke"]["median_vph"], 10.0)
        self.assertEqual(out["buckets"]["tier2_machine"]["n"], 1)
        self.assertEqual(out["buckets"]["tier0_chart"]["n"], 1)
        self.assertEqual(out["ungraded"], 0)
        self.assertEqual(out["tier1_vs_rest"],
                         {"tier1_median_vph": 10.0, "rest_best_median_vph": 2.0})

    def test_the_last_verdict_for_a_slug_wins(self):
        """A repair re-renders and re-judges; the log is append-only, so the
        entry that shipped is the last one."""
        out = self._run([_video("a", 5.0)],
                        [_verdict("a", [3]), _verdict("a", [1])])
        self.assertIn("tier2_machine", out["buckets"])
        self.assertNotIn("tier1_bespoke", out["buckets"])

    def test_ungraded_and_too_young_are_counted_not_guessed(self):
        out = self._run([_video("old-ungraded", 5.0), _video("young", 5.0, age=3.0),
                         _video("graded", 5.0)],
                        [_verdict("graded", [2])])
        self.assertEqual(out["ungraded"], 1)
        self.assertEqual(sum(b["n"] for b in out["buckets"].values()), 1)

    def test_a_thin_bucket_is_labelled_and_no_conclusion_is_drawn(self):
        out = self._run([_video("a", 10.0), _video("b", 1.0)],
                        [_verdict("a", [3]), _verdict("b", [1])], min_samples=3)
        self.assertEqual(set(out["thin"]), {"tier1_bespoke", "tier2_machine"})
        self.assertNotIn("tier1_vs_rest", out)

    def test_no_analytics_is_a_note_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(BR, "ROOT", Path(td)):
            out = BR.depictions_vs_performance("missing.json",
                                               verdict_log=Path(td) / "none")
        self.assertEqual(out["buckets"], {})
        self.assertIn("no explainer analytics", out["note"])


class ItIsInTheBrief(unittest.TestCase):
    def test_build_carries_the_section_and_markdown_prints_it(self):
        import inspect
        self.assertIn('"depictions": depictions_vs_performance()',
                      inspect.getsource(BR.build))
        brief = {"date": "2026-09-21", "generated_at": "x", "posted_today": 0,
                 "channels": {}, "pipeline_health": {},
                 "repo": {"head": "h", "commit_count": 0, "commits_since": "d"},
                 "depictions": {"note": "n", "ungraded": 2, "thin": ["tier1_bespoke"],
                                "buckets": {"tier1_bespoke": {"n": 1, "median_vph": 4.0,
                                                              "max_vph": 4.0}}}}
        md = BR.to_markdown(brief)
        self.assertIn("## Bespoke pictures vs performance", md)
        self.assertIn("tier1_bespoke: n=1", md)
        self.assertIn("_(thin)_", md)
        self.assertIn("ungraded", md)

    def test_the_summary_speaks_only_when_the_buckets_are_thick(self):
        base = {"date": "d", "channels": {}, "pipeline_health": {},
                "continuity": {}, "what_you_owe_today": {}}
        quiet = BR.executive_summary(dict(base, depictions={"buckets": {}}))
        self.assertNotIn("Do the bespoke pictures pay?", quiet)
        loud = BR.executive_summary(dict(base, depictions={
            "tier1_vs_rest": {"tier1_median_vph": 3.0, "rest_best_median_vph": 1.0}}))
        self.assertIn("Do the bespoke pictures pay?", loud)
        self.assertIn("3.0 vph", loud)


if __name__ == "__main__":
    unittest.main()
