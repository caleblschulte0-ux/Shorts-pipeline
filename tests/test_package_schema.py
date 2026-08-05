"""Tests for `shared/package_schema.py` — the one structural gate every
producer of a trending package is held to.

The gate has to be strict enough that a package which would explode at
render time is refused before it takes a slot, and loose enough that real
authored packages actually pass. Both halves are tested here, the second by
running the gate over the REAL corpus in `state/trending_packages/` — a
validator nothing can satisfy is just a channel that never posts.

Was `tests/test_package_buffer.py`; the reserve-bank storage tests went with
the bank on 2026-08-05 (see the module docstring for why).

    python -m unittest tests.test_package_schema -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import package_schema as buf  # noqa: E402


# --------------------------------------------------------------------------
# These tests are about MECHANISM, not about today's operator ruling. They run
# against a fixture registry carrying the mix they were written for, so a
# future mix change in config/channel_registry.json breaks only the tests that
# are ABOUT the ruling (tests/test_channel_registry.py) instead of these.
# --------------------------------------------------------------------------
from tests.registry_fixture import LEGACY_MIX, registry   # noqa: E402

_FIXTURE = None


def setUpModule():
    global _FIXTURE
    _FIXTURE = registry(LEGACY_MIX)
    _FIXTURE.__enter__()


def tearDownModule():
    if _FIXTURE is not None:
        _FIXTURE.__exit__(None, None, None)


def reddit_pkg(slug="office-printer-justice", **over) -> dict:
    script = ("My coworker kept stealing my lunch from the office fridge. "
              "I labeled it with my name in permanent marker. I hid it "
              "behind the sad communal condiments nobody has touched since "
              "the last reorg. I even sent one of those painfully polite "
              "all-team emails asking whoever it was to please stop. "
              "Nothing worked, and every single day my food was gone by "
              "noon while he sat two desks over eating something that "
              "looked suspiciously familiar. So I stopped asking. I made a "
              "sandwich with the hottest peppers I could find, wrapped it "
              "in the exact same foil I always used, and left it front and "
              "center on the middle shelf where he could not possibly miss "
              "it. An hour later he came sprinting past my desk toward the "
              "water cooler with his whole face bright red, gulping "
              "straight from the tap. He never touched that fridge again, "
              "and he never once admitted why.")
    pkg = {"version": 1, "subreddit": "pettyrevenge", "slug": slug,
           "title": f"He Stopped Stealing Lunches: {slug}",
           "hashtags": [f"#tag{i}" for i in range(12)],
           "script": script,
           "shots": [{"phrase": "office fridge", "query": "office kitchen"},
                     {"phrase": "hottest peppers", "query": "chili peppers"},
                     {"phrase": "water cooler", "query": "office hallway"}],
           "punches": [{"phrase": "bright red", "text": "RED", "color": "#ff3030"}],
           "music_vibe": "dark"}
    pkg.update(over)
    return pkg


def text_card_pkg(slug="shrinkflation-chips", **over) -> dict:
    text = ("The bag is the same size. The chips inside are not.\n\n"
            "Manufacturers shrank package contents while holding the price "
            "steady, a practice economists call shrinkflation, and it is "
            "far easier to hide than a price increase.\n\n"
            "You are paying more per ounce and the label never says so.")
    pkg = {"version": 1, "format": "text_card", "slug": slug,
           "title": f"The Bag Is The Same Size: {slug}", "duration": 6,
           "broll_query": "potato chips",
           "hashtags": [f"#tag{i}" for i in range(12)],
           "text": text,
           "highlights": ["same size", "shrinkflation", "price increase",
                          "more per ounce"],
           "music_vibe": "dark"}
    pkg.update(over)
    return pkg


def graph_pkg(slug="streaming-vs-cable", **over) -> dict:
    pkg = {"version": 1, "format": "graph_race", "slug": slug,
           "title": f"Streaming Overtook Cable: {slug}",
           "y_label": "Subscribers",
           "duration": 13, "source": "Sources: company filings",
           "hashtags": [f"#tag{i}" for i in range(12)],
           "years": [2010, 2012, 2014, 2016, 2018, 2020, 2022],
           "series": [
               {"name": "Streaming", "color": "#e50914", "icon": "Netflix",
                "values": [20_000_000, 33_000_000, 57_000_000, 93_000_000,
                           139_000_000, 203_000_000, 230_000_000]},
               {"name": "Cable", "color": "#3388ff", "icon": "US",
                "values": [105_000_000, 100_000_000, 95_000_000, 90_000_000,
                           78_000_000, 62_000_000, 45_000_000]}],
           "music_vibe": "dark", "hook": "Watch 2016"}
    pkg.update(over)
    return pkg


class SchemaTestCase(unittest.TestCase):
    """The validator is PURE — no filesystem, no network. Nothing to set up
    beyond the fixture registry installed at module scope."""


class TestFormatDetection(SchemaTestCase):
    def test_each_format(self):
        self.assertEqual(buf.format_of(reddit_pkg()), "reddit_story")
        self.assertEqual(buf.format_of(text_card_pkg()), "text_card")
        self.assertEqual(buf.format_of(graph_pkg()), "graph_race")

    def test_the_legacy_stacked_shape_is_not_a_trending_format(self):
        pkg = {"slug": "old-shape", "script": "words", "shots": []}
        self.assertEqual(buf.format_of(pkg), "explainer")
        ok, why = buf.eligible(pkg)
        self.assertFalse(ok)
        self.assertIn("not registered", " ".join(why))

    def test_bare_slug_strips_ordering_prefix(self):
        self.assertEqual(buf.bare_slug("03_textcard-foo"), "textcard-foo")
        self.assertEqual(buf.bare_slug("textcard-foo"), "textcard-foo")


class TestEligibility(SchemaTestCase):
    def test_clean_packages_pass(self):
        for pkg in (reddit_pkg(), text_card_pkg(), graph_pkg()):
            ok, why = buf.eligible(pkg)
            self.assertTrue(ok, f"{buf.format_of(pkg)}: {why}")

    def test_date_anchored_script_refused(self):
        pkg = reddit_pkg()
        pkg["script"] = "Yesterday my coworker " + pkg["script"]
        ok, why = buf.eligible(pkg)
        self.assertFalse(ok)
        self.assertIn("date-anchored", " ".join(why))

    def test_weekday_refused(self):
        pkg = text_card_pkg()
        pkg["title"] = "What Happened Tuesday"
        self.assertFalse(buf.eligible(pkg)[0])

    def test_month_and_day_refused(self):
        pkg = text_card_pkg()
        pkg["text"] = pkg["text"] + "\n\nIt started on March 14."
        self.assertFalse(buf.eligible(pkg)[0])

    def test_citation_year_is_not_staleness(self):
        """A year in a source line or chart data is a citation, not a
        date anchor — flagging it would bar every graph package."""
        pkg = graph_pkg()
        pkg["source"] = "Sources: Nielsen 2023, company filings 2022"
        ok, why = buf.eligible(pkg)
        self.assertTrue(ok, why)

    def test_shot_phrase_must_be_a_substring(self):
        pkg = reddit_pkg()
        pkg["shots"][0]["phrase"] = "a phrase that is not in the script"
        ok, why = buf.eligible(pkg)
        self.assertFalse(ok)
        self.assertIn("shot.phrase", " ".join(why))

    def test_highlight_must_be_a_substring(self):
        pkg = text_card_pkg()
        pkg["highlights"].append("nowhere in the text at all")
        self.assertFalse(buf.eligible(pkg)[0])

    def test_graph_series_length_mismatch_refused(self):
        pkg = graph_pkg()
        pkg["series"][0]["values"] = pkg["series"][0]["values"][:-1]
        ok, why = buf.eligible(pkg)
        self.assertFalse(ok)
        self.assertIn("values for", " ".join(why))

    def test_all_problems_reported_at_once(self):
        pkg = reddit_pkg()
        pkg["script"] = "Yesterday it happened."      # stale AND too short
        why = buf.eligible(pkg)[1]
        self.assertTrue(any("date-anchored" in w for w in why))
        self.assertTrue(any("words" in w for w in why))


class TestAgainstTheRealCorpus(unittest.TestCase):
    """The gate has to be PASSABLE. A validator that nothing real satisfies
    is not a quality bar, it is a channel that never posts — and because
    every producer runs through this one gate, that failure would be total
    rather than partial."""

    def test_real_authored_packages_pass_the_gate(self):
        real = ROOT / "state" / "trending_packages"
        usable = 0
        checked = 0
        for day in sorted(real.glob("2026*")):
            for p in day.glob("*.json"):
                if p.name.startswith("_"):
                    continue
                try:
                    pkg = json.loads(p.read_text())
                except Exception:                      # noqa: BLE001
                    continue
                if buf.format_of(pkg) not in buf.formats():
                    continue
                checked += 1
                if buf.eligible(pkg)[0]:
                    usable += 1
        self.assertGreater(checked, 10, "no real 3-format packages to check")
        self.assertGreater(usable, 0,
                           "not one real package passes the structural gate "
                           "— the rules are too strict for the channel to "
                           "ever ship anything")


if __name__ == "__main__":
    unittest.main(verbosity=2)
