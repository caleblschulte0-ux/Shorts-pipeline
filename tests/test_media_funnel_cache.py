"""Regression test for doctor findings 6be0849a55e4 / 3cca8a711ec4:
a cache hit in funnel.media_funnel.search() used to restore the score
computed at cache-write time verbatim, so the cross-video recent-use
penalty (funnel/media_usage.py) — and every other time-dependent score
component — never took effect for anything served from cache.

Fully offline; redirects CACHE_PATH and media_usage.LEDGER_PATH into a
temp dir so it never touches real state.

    python -m unittest tests.test_media_funnel_cache -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funnel import media_funnel as mf   # noqa: E402
from funnel import media_usage          # noqa: E402


class TestCacheHitRecomputesScore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        self._saved = (mf.CACHE_PATH, media_usage.LEDGER_PATH)
        mf.CACHE_PATH = root / "news_image_cache.json"
        media_usage.LEDGER_PATH = root / "media_usage.json"

    def tearDown(self):
        mf.CACHE_PATH, media_usage.LEDGER_PATH = self._saved
        self._td.cleanup()

    def _cache_one(self, url="https://example.com/photo.jpg"):
        c = mf.Candidate(url=url, source="newsapi",
                          article_title="Some Entity does a thing",
                          article_url="https://example.com/article",
                          source_class="unverified", license="")
        mf._cache_put("story-slug", "Some Entity", [c])
        return c

    def test_cache_hit_reflects_penalty_recorded_after_caching(self):
        url = "https://example.com/photo.jpg"
        self._cache_one(url)

        before = mf.search("angle", ["Some Entity"], story_slug="story-slug",
                            verbose=False)
        self.assertEqual(before[0].url, url)
        score_before = before[0].score

        # The candidate airs in a video *after* it was cached.
        media_usage.record(url, slug="some-video")

        after = mf.search("angle", ["Some Entity"], story_slug="story-slug",
                           verbose=False)
        self.assertEqual(after[0].url, url)
        self.assertLess(after[0].score, score_before,
                         "cache hit must apply the recent-use penalty "
                         "recorded after the entry was cached")
        self.assertAlmostEqual(score_before - after[0].score,
                                media_usage.REUSE_PENALTY, places=3)

    def test_cache_hit_does_not_just_replay_stale_llm_bonus_as_base(self):
        # A cached candidate's llm_bonus must be additive on top of a
        # freshly recomputed base score, not swallowed into an opaque
        # stored total that a later penalty can't touch.
        url = "https://example.com/photo2.jpg"
        c = mf.Candidate(url=url, source="ddg", article_title="",
                          article_url="", source_class="unverified")
        c.boosts["llm_bonus"] = 0.25
        c.score = 0.35 + 0.25  # base(ddg)=0.35 + llm bonus at write time
        mf._cache_put("story-slug-2", "Ent", [c])

        hit = mf.search("angle", ["Ent"], story_slug="story-slug-2",
                         verbose=False)
        self.assertEqual(hit[0].url, url)
        # base(ddg) recomputed fresh (0.35) + cached llm_bonus (0.25)
        self.assertAlmostEqual(hit[0].score, 0.60, places=3)


if __name__ == "__main__":
    unittest.main()
