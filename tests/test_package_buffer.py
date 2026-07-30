"""Tests for the reserve package bank — the dead-brain fallback.

The bank only earns its keep if three things hold: it refuses anything that
would read stale weeks later, it never serves the same package twice (a
second serving means a duplicate upload), and it never displaces work the
brain actually produced. Each of those gets a test here, plus a corpus test
proving the eligibility gate is not so strict that nothing can ever bank.

    python -m unittest tests.test_package_buffer -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import package_buffer as buf  # noqa: E402


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


class BankTestCase(unittest.TestCase):
    """Redirects the module's on-disk locations into a temp dir so tests
    never touch the real bank or the real package directories."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bank-test-"))
        self._saved = (buf.BUFFER_DIR, buf.PKG_DIR, buf.USED_LOG, buf.DAY_DIR)
        buf.BUFFER_DIR = self.tmp / "package_buffer"
        buf.PKG_DIR = buf.BUFFER_DIR / "packages"
        buf.USED_LOG = buf.BUFFER_DIR / "used.json"
        buf.DAY_DIR = self.tmp / "trending_packages"
        buf.PKG_DIR.mkdir(parents=True)
        buf.DAY_DIR.mkdir(parents=True)

    def tearDown(self):
        (buf.BUFFER_DIR, buf.PKG_DIR, buf.USED_LOG,
         buf.DAY_DIR) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bank_all(self):
        for maker, n in ((reddit_pkg, 2), (text_card_pkg, 2), (graph_pkg, 2)):
            for i in range(n):
                path, why = buf.deposit(maker(slug=f"{maker.__name__}-{i}"),
                                        source="test")
                self.assertIsNotNone(path, why)


class TestFormatDetection(BankTestCase):
    def test_each_format(self):
        self.assertEqual(buf.format_of(reddit_pkg()), "reddit_story")
        self.assertEqual(buf.format_of(text_card_pkg()), "text_card")
        self.assertEqual(buf.format_of(graph_pkg()), "graph_race")

    def test_legacy_stacked_is_not_bankable(self):
        pkg = {"slug": "old-shape", "script": "words", "shots": []}
        self.assertEqual(buf.format_of(pkg), "explainer")
        ok, why = buf.eligible(pkg)
        self.assertFalse(ok)
        self.assertIn("not bankable", " ".join(why))

    def test_bare_slug_strips_ordering_prefix(self):
        self.assertEqual(buf.bare_slug("03_textcard-foo"), "textcard-foo")
        self.assertEqual(buf.bare_slug("textcard-foo"), "textcard-foo")


class TestEligibility(BankTestCase):
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


class TestDeposit(BankTestCase):
    def test_deposit_and_inventory(self):
        self.bank_all()
        inv = buf.inventory()
        self.assertEqual({f: len(v) for f, v in inv.items()},
                         {"reddit_story": 2, "text_card": 2, "graph_race": 2})

    def test_duplicate_slug_refused(self):
        buf.deposit(reddit_pkg(), source="test")
        path, why = buf.deposit(reddit_pkg(), source="test")
        self.assertIsNone(path)
        self.assertIn("already in the bank", " ".join(why))

    def test_ordering_prefix_is_not_a_different_package(self):
        buf.deposit(reddit_pkg(slug="office-printer-justice"), source="test")
        path, why = buf.deposit(reddit_pkg(slug="01_office-printer-justice"),
                                source="test")
        self.assertIsNone(path, "prefix made a duplicate look new")
        self.assertIn("already in the bank", " ".join(why))

    def test_already_authored_slug_refused(self):
        day = buf.DAY_DIR / "20260730"
        day.mkdir(parents=True)
        (day / "01_office-printer-justice.json").write_text(
            json.dumps(reddit_pkg()))
        path, why = buf.deposit(reddit_pkg(), source="test")
        self.assertIsNone(path)
        self.assertIn("already authored", " ".join(why))

    def test_internal_keys_are_stripped(self):
        pkg = reddit_pkg()
        pkg["_path"] = "state/trending_packages/20260730/01_x.json"
        path, _ = buf.deposit(pkg, source="test")
        entry = json.loads(path.read_text())
        self.assertNotIn("_path", entry["package"])

    def test_force_banks_an_ineligible_package(self):
        pkg = reddit_pkg()
        pkg["script"] = "Yesterday " + pkg["script"]
        self.assertIsNone(buf.deposit(pkg, source="test")[0])
        self.assertIsNotNone(buf.deposit(pkg, source="test", force=True)[0])

    def test_low_water(self):
        self.assertEqual(set(buf.low_formats()), set(buf.FORMATS))
        self.bank_all()
        self.assertEqual(set(buf.low_formats()), set(buf.FORMATS))  # 2 < 4


class TestDraw(BankTestCase):
    def test_select_honours_the_222_mix(self):
        self.bank_all()
        got = [e["format"] for e in buf.select(6)]
        self.assertEqual(sorted(got),
                         ["graph_race", "graph_race", "reddit_story",
                          "reddit_story", "text_card", "text_card"])

    def test_select_backfills_when_a_format_is_empty(self):
        for i in range(4):
            buf.deposit(reddit_pkg(slug=f"r-{i}"), source="test")
        got = buf.select(4)
        self.assertEqual(len(got), 4)
        self.assertTrue(all(e["format"] == "reddit_story" for e in got))

    def test_select_is_read_only(self):
        self.bank_all()
        buf.select(6)
        self.assertEqual(sum(len(v) for v in buf.inventory().values()), 6)

    def test_draw_consumes_exactly_once(self):
        self.bank_all()
        drawn = buf.draw(buf.select(2), date="20260801", reason="test")
        self.assertEqual(len(drawn), 2)
        self.assertEqual(sum(len(v) for v in buf.inventory().values()), 4)
        self.assertEqual(buf.drawn_count(), 2)
        # And the drawn slugs can never come back.
        gone = {p["slug"] for p in drawn}
        self.assertFalse(gone & {e["package"]["slug"] for e in buf.entries()})
        for slug in gone:
            self.assertIsNone(
                buf.deposit(reddit_pkg(slug=slug), source="test")[0],
                "a package that already aired was allowed back into the bank")

    def test_drawn_package_records_its_provenance(self):
        self.bank_all()
        pkg = buf.draw(buf.select(1), date="20260801", reason="brain dark")[0]
        self.assertEqual(pkg["_reserve"]["drawn_on"], "20260801")
        self.assertEqual(pkg["_reserve"]["reason"], "brain dark")
        self.assertTrue(pkg["_reserve"]["banked_at"])


class TestFillDay(BankTestCase):
    def test_full_day_is_untouched(self):
        self.bank_all()
        day = buf.DAY_DIR / "20260801"
        day.mkdir(parents=True)
        for i in range(6):
            (day / f"0{i + 1}_authored.json").write_text("{}")
        report = buf.fill_day("20260801", target=6)
        self.assertEqual(report["need"], 0)
        self.assertEqual(report["drawn"], [])
        self.assertEqual(sum(len(v) for v in buf.inventory().values()), 6,
                         "a full day drew from the bank anyway")

    def test_empty_day_is_filled(self):
        self.bank_all()
        report = buf.fill_day("20260801", target=6, reason="dead brain")
        self.assertEqual(report["need"], 6)
        self.assertEqual(len(report["drawn"]), 6)
        self.assertEqual(report["shortfall"], 0)
        written = sorted((buf.DAY_DIR / "20260801").glob("*.json"))
        self.assertEqual(len(written), 6)
        pkg = json.loads(written[0].read_text())
        self.assertEqual(pkg["_reserve"]["reason"], "dead brain")

    def test_partial_day_is_topped_up_without_filename_collisions(self):
        self.bank_all()
        day = buf.DAY_DIR / "20260801"
        day.mkdir(parents=True)
        for i in range(2):
            (day / f"0{i + 1}_authored.json").write_text("{}")
        report = buf.fill_day("20260801", target=6)
        self.assertEqual(report["need"], 4)
        self.assertEqual(len(report["drawn"]), 4)
        self.assertEqual(len(list(day.glob("*.json"))), 6,
                         "a reserve file overwrote an authored one")

    def test_shortfall_is_reported_not_hidden(self):
        buf.deposit(reddit_pkg(slug="only-one"), source="test")
        report = buf.fill_day("20260801", target=6)
        self.assertEqual(len(report["drawn"]), 1)
        self.assertEqual(report["shortfall"], 5)

    def test_empty_bank_is_a_clean_no_op(self):
        report = buf.fill_day("20260801", target=6)
        self.assertEqual(report["drawn"], [])
        self.assertEqual(report["shortfall"], 6)
        self.assertFalse((buf.DAY_DIR / "20260801").exists())

    def test_dry_run_consumes_nothing(self):
        self.bank_all()
        report = buf.fill_day("20260801", target=6, dry_run=True)
        self.assertEqual(len(report["drawn"]), 6)
        self.assertEqual(sum(len(v) for v in buf.inventory().values()), 6)
        self.assertFalse((buf.DAY_DIR / "20260801").exists())

    def test_underscore_config_files_do_not_count_as_packages(self):
        self.bank_all()
        day = buf.DAY_DIR / "20260801"
        day.mkdir(parents=True)
        (day / "_schedule.json").write_text("{}")
        self.assertEqual(buf.fill_day("20260801", target=6)["need"], 6)


class TestAgainstTheRealCorpus(unittest.TestCase):
    """The gate has to be passable. If no package the channel has ever
    authored could be banked, the bank can never fill and the fallback is
    decorative."""

    def test_some_real_authored_packages_are_bankable(self):
        real = ROOT / "state" / "trending_packages"
        bankable = 0
        checked = 0
        for day in sorted(real.glob("2026*")):
            for p in day.glob("*.json"):
                if p.name.startswith("_"):
                    continue
                try:
                    pkg = json.loads(p.read_text())
                except Exception:                      # noqa: BLE001
                    continue
                if buf.format_of(pkg) not in buf.FORMATS:
                    continue
                checked += 1
                if buf.eligible(pkg)[0]:
                    bankable += 1
        self.assertGreater(checked, 10, "no real 3-format packages to check")
        self.assertGreater(bankable, 0,
                           "not one real package passes the bank's gate — "
                           "the eligibility rules are too strict to ever fill")


if __name__ == "__main__":
    unittest.main(verbosity=2)
