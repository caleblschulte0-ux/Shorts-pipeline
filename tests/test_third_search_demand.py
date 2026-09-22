"""The title author is told how viewers actually find the channel.

`fetch_analytics.py` wrote Third's top YouTube search queries into
`state/analytics_third/latest.json` for weeks and nothing read them — on a
channel whose views were ~89% search (2026-09-22: 3,956 of 4,442). A
capability built and never wired is the thing CLAUDE.md's rule zero names.

The queries are specific: people search Buddha as "lang buddha", and
Jasontheween as "jasontheween news". A title that says only "Buddha" does
not match the first.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KNOWN = ["jynxzi", "jasontheween", "buddha", "xqc", "lirik"]


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_third_search", ROOT / "scripts" / "run_third.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _guidance(streamer, snap):
    m = _load()
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "latest.json"
        f.write_text(json.dumps(snap))
        with mock.patch.object(m, "ANALYTICS_LATEST", f):
            m._SEARCH_SNAP = None
            return m._search_guidance(streamer, KNOWN)


SEARCHY = {
    "traffic_sources": {"YT_SEARCH": 900, "SHORTS": 100},
    "search_terms": [
        {"term": "jynxzi", "views": 497},
        {"term": "caternado", "views": 105},
        {"term": "jasontheween news", "views": 87},
        {"term": "nopixel", "views": 42},
        {"term": "lang buddha", "views": 14},
        {"term": "jason and sakura", "views": 13},
        {"term": "xqc", "views": 13},
    ],
}


class TheAuthorHearsTheRealQueries(unittest.TestCase):
    def test_a_streamers_own_queries_are_named(self):
        g = _guidance("jynxzi", SEARCHY)
        self.assertIn('"jynxzi" (497)', g)
        self.assertIn("90%", g)

    def test_the_way_people_spell_a_name_reaches_the_author(self):
        """The case that justifies the whole wire."""
        self.assertIn('"lang buddha"', _guidance("buddha", SEARCHY))

    def test_an_alias_counts_as_a_mention(self):
        self.assertIn('"jason and sakura"', _guidance("jasontheween", SEARCHY))

    def test_event_and_game_phrases_are_offered(self):
        g = _guidance("jynxzi", SEARCHY)
        self.assertIn('"caternado"', g)
        self.assertIn('"nopixel"', g)


class ItNeverInvitesAFalseTitle(unittest.TestCase):
    def test_another_streamers_queries_are_not_offered(self):
        g = _guidance("jynxzi", SEARCHY)
        for other in ('"xqc"', '"jasontheween news"', '"lang buddha"'):
            with self.subTest(term=other):
                self.assertNotIn(other, g)

    def test_another_streamers_ALIAS_is_not_offered(self):
        """'jason and sakura' names jasontheween as 'jason' — it leaked into
        jynxzi's list in the first draft of this wire."""
        self.assertNotIn("jason and sakura", _guidance("jynxzi", SEARCHY))

    def test_the_honesty_rule_travels_with_every_note(self):
        self.assertIn("ONLY when this clip genuinely involves it",
                      _guidance("jynxzi", SEARCHY))

    def test_short_aliases_do_not_match_ordinary_words(self):
        """ALIASES maps 'ron' to stableronaldo and 'case' to caseoh; matched
        as substrings they would claim half the queries on the channel."""
        snap = dict(SEARCHY, search_terms=[
            {"term": "iron man case", "views": 50}])
        g = _guidance("stableronaldo", snap)
        self.assertNotIn("Real queries that brought viewers to stableronaldo", g)


class ItStaysQuietWhenItShould(unittest.TestCase):
    def test_a_feed_driven_channel_is_not_told_to_write_for_search(self):
        snap = dict(SEARCHY, traffic_sources={"YT_SEARCH": 100, "SHORTS": 900})
        self.assertEqual(_guidance("jynxzi", snap), "")

    def test_no_queries_means_no_note(self):
        self.assertEqual(_guidance("jynxzi", dict(SEARCHY, search_terms=[])), "")

    def test_no_snapshot_means_no_note(self):
        m = _load()
        with mock.patch.object(m, "ANALYTICS_LATEST", Path("/nonexistent.json")):
            m._SEARCH_SNAP = None
            self.assertEqual(m._search_guidance("jynxzi", KNOWN), "")


class ItIsWired(unittest.TestCase):
    def test_the_author_call_passes_it(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn("search=_search_guidance(streamer, _known)", src)

    def test_the_prompt_carries_it_in_its_own_section(self):
        from third_capture import author
        p = author._build_user_prompt("jynxzi", "t", "words here and more",
                                      100, search="QUERIES")
        self.assertIn("SEARCH DEMAND (use for title + hashtags): QUERIES", p)
        self.assertNotIn("SEARCH DEMAND",
                         author._build_user_prompt("jynxzi", "t", "w", 100))


if __name__ == "__main__":
    unittest.main()
