"""The attribution report must never launder noise into a mandate.

This is the file most likely to be quoted in a decision — "inversion hooks
retain 15 points above baseline, so write inversion hooks" — off two videos.
The retro loop's own doctrine says a report that dresses noise as a finding is
worse than no report, so the honesty rules are tested, not just documented.

Runs with pytest OR standalone:
    python3 tests/test_what_works.py
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    "what_works", _REPO / "scripts" / "what_works.py")
ww = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ww)


def _v(pct, views, **kw):
    row = {"average_view_percentage": pct, "views": views,
           "catalog_id": kw.pop("slug", "s")}
    row.update(kw)
    return row


class WhatWorks(unittest.TestCase):
    def test_a_looping_short_cannot_swamp_a_group(self):
        """A Short that loops reports >100% — real, but a different
        phenomenon, and one of them drags a small group anywhere you like."""
        rows = ww.usable([_v(471.3, 900), _v(40, 100), _v(30, 100)], 25)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["average_view_percentage"] <= 100 for r in rows))

    def test_videos_under_the_view_floor_are_not_evidence(self):
        rows = ww.usable([_v(90, 3), _v(35, 200)], 25)
        self.assertEqual([r["views"] for r in rows], [200])

    def test_thin_groups_are_labelled_not_hidden(self):
        """They stay visible — a two-video group can still be a lead worth
        chasing — but they carry the word `thin` so nobody quotes them as a
        result."""
        data = {"videos": [_v(70, 100, hook="inversion"),
                           _v(60, 100, hook="inversion"),
                           _v(30, 100, hook="question"),
                           _v(31, 100, hook="question"),
                           _v(32, 100, hook="question"),
                           _v(33, 100, hook="question")]}
        rep = ww.report(data, min_views=25, min_group=4)
        blk = rep["dimensions"]["hook"]
        self.assertIn("inversion", blk["groups"])
        self.assertIn("inversion", blk["thin"], "a 2-video group must be thin")
        self.assertNotIn("question", blk["thin"], "a 4-video group is a finding")

    def test_a_dimension_with_only_thin_groups_is_declared_unanswerable(self):
        data = {"videos": [_v(70, 100, hook="a"), _v(30, 100, hook="b")]}
        rep = ww.report(data, min_views=25, min_group=4)
        self.assertTrue(any("anecdote" in s for s in rep["not_yet_answerable"]),
                        rep["not_yet_answerable"])

    def test_an_unrecorded_dimension_says_so(self):
        """Silence and 'no effect' must not look the same."""
        data = {"videos": [_v(40, 100), _v(50, 100)]}
        rep = ww.report(data, min_views=25, min_group=1)
        self.assertTrue(any("not recorded" in s
                            for s in rep["not_yet_answerable"]))

    def test_no_evidence_at_all_is_reported_not_crashed(self):
        rep = ww.report({"videos": []}, min_views=25, min_group=4)
        self.assertEqual(rep["videos_considered"], 0)
        self.assertTrue(rep["not_yet_answerable"])

    def test_the_ledger_join_uses_the_slug(self):
        """The join everyone reached for was `video_id`, which the ledger never
        learned — 92 rows of creative decisions that could not reach a single
        outcome. `catalog_id` IS the slug, and that is the working key."""
        led = ww._ledger_by_slug()
        if not led:
            self.skipTest("no ledger in this checkout")
        slug = next(iter(led))
        rows = ww._enrich([{"catalog_id": slug, "average_view_percentage": 40,
                            "views": 100}])
        self.assertEqual(rows[0].get("hook"), led[slug].get("hook_type"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
