"""Trending analytics must carry the registered format (doctor c8ca85c0ce21).

fetch_analytics._entries copied only url/catalog_id/posted_at/title for the
list-shaped trending log, so every trending row reached build_retro with no
format and was bucketed "unknown" — the 4/2 graph_race/reddit_story mix could
not be compared at any maturity band.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TrendingFormatSurvives(unittest.TestCase):
    def test_entries_carry_format(self):
        fa = _load("fetch_analytics_t", "scripts/fetch_analytics.py")
        log = {"posted": [
            {"video_url": "https://youtube.com/shorts/aaaaaaaaaaa",
             "posted_at": "2026-09-30T13:50:33Z", "title": "T",
             "format": "graph_race", "topic": "x"}]}
        out = fa._entries(log)
        self.assertEqual(out[0]["format"], "graph_race")

    def test_format_reaches_retro_cohort_key(self):
        fa = _load("fetch_analytics_t2", "scripts/fetch_analytics.py")
        br = _load("build_retro_t", "scripts/build_retro.py")
        e = fa._entries({"posted": [
            {"video_url": "https://youtube.com/shorts/aaaaaaaaaaa",
             "format": "reddit"}]})[0]
        self.assertEqual(br.format_of({"format": e["format"]}), "reddit")


if __name__ == "__main__":
    unittest.main()
