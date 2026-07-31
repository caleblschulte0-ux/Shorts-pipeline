"""Tests for levity — the humour capability.

Two things must hold, and they pull against each other. The gate must never
let a joke near a tragedy, because that is unrecoverable. And it must not
over-refuse, because an over-cautious gate produces exactly the humourless
channel this module exists to fix. Most of these test the second thing,
since that failure is the quiet one.

    python -m unittest tests.test_levity -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import levity  # noqa: E402


class TestTheGateRefusesTragedy(unittest.TestCase):
    """A quip next to a death is not a tone miss. Fails closed."""

    def _refused(self, title: str) -> bool:
        return not levity.allowed({"title": title})[0]

    def test_death_and_injury(self):
        for t in ("Three killed in a highway pileup",
                  "Body found in the reservoir",
                  "Driver died after the crash",
                  "One fatality confirmed overnight"):
            self.assertTrue(self._refused(t), t)

    def test_crime_against_a_person(self):
        for t in ("Man charged with assault outside the bar",
                  "Police search for a missing girl",
                  "Suspect arrested for kidnapping"):
            self.assertTrue(self._refused(t), t)

    def test_war_illness_and_disaster(self):
        for t in ("Airstrike hits the market district",
                  "New cancer treatment enters trials",
                  "Earthquake levels the old town",
                  "Refugee camp runs out of water"):
            self.assertTrue(self._refused(t), t)

    def test_the_reason_is_specific_not_generic(self):
        ok, why = levity.allowed({"title": "Two killed in the blast"})
        self.assertFalse(ok)
        self.assertIn("killed", why)


class TestTheGateDoesNotOverRefuse(unittest.TestCase):
    """The quiet failure. Every false positive here is a video that had to
    stay dry for no reason, which is the complaint that started this."""

    def _allowed(self, title: str) -> bool:
        return levity.allowed({"title": title})[0]

    def test_technical_fatal_is_not_a_death(self):
        self.assertTrue(self._allowed(
            "Quantum chip fixes a fatal error in the stack"))

    def test_an_oil_terminal_is_not_a_terminal_illness(self):
        self.assertTrue(self._allowed(
            "Drones hit the Baltic oil terminal"))

    def test_airport_terminal_is_fine(self):
        self.assertTrue(self._allowed(
            "Raccoon shuts down an airport terminal for six hours"))

    def test_ordinary_absurd_news_passes(self):
        for t in ("A kangaroo named Hunter escaped in Kentucky",
                  "High schoolers built a record-breaking blanket fort",
                  "Town votes for mayor with a blank ballot",
                  "Shrinkflation hits the cereal aisle"):
            self.assertTrue(self._allowed(t), t)

    def test_most_of_the_real_corpus_is_joke_eligible(self):
        """If the gate refused most real videos it would be useless."""
        pkgs = []
        for f in sorted((ROOT / "state" / "trending_packages").glob(
                "2026*/*.json")):
            try:
                p = json.loads(f.read_text())
            except Exception:                        # noqa: BLE001
                continue
            if isinstance(p, dict) and p.get("title"):
                pkgs.append(p)
        self.assertGreater(len(pkgs), 50, "no corpus to check")
        ok = sum(1 for p in pkgs if levity.allowed(p)[0])
        self.assertGreater(ok / len(pkgs), 0.5,
                           f"the gate refused {len(pkgs) - ok}/{len(pkgs)} "
                           f"real videos — it is too strict to be useful")


class TestLightSubjectsAreFlagged(unittest.TestCase):
    def test_an_absurd_subject_expects_a_joke(self):
        self.assertTrue(levity.is_light(
            {"title": "A kangaroo escaped and it took three hours"}))

    def test_a_serious_subject_does_not(self):
        self.assertFalse(levity.is_light(
            {"title": "Fed holds rates steady at the September meeting"}))

    def test_a_tragedy_is_never_light_even_if_it_reads_absurd(self):
        self.assertFalse(levity.is_light(
            {"title": "Escaped zoo lion killed a keeper"}))


class TestTheDetector(unittest.TestCase):
    """It measures the SHAPE of an aside. The first version counted any
    short sentence and reported 84% of scripts as funny while the operator
    had never heard one — the operator was right."""

    def test_an_undercut_is_detected(self):
        text = ("The chase went on for two hours across three separate "
                "counties before ending in a retention pond. Top speed: "
                "twelve.")
        self.assertTrue(levity.has_levity(text)["has_levity"])

    def test_a_dry_hedge_is_detected(self):
        self.assertTrue(levity.has_levity(
            "He had, apparently, been doing this for months.")["has_levity"])

    def test_understatement_is_detected(self):
        self.assertTrue(levity.has_levity(
            "The hive tipped onto the highway. This did not go well for "
            "the bees.")["has_levity"])

    def test_flat_recitation_is_not_mistaken_for_humour(self):
        text = ("A robot worked 200 hours straight without a single "
                "failure. The company sorted 250,000 packages on a live "
                "stream. The system ran continuously for eight days.")
        self.assertFalse(levity.has_levity(text)["has_levity"],
                         "pure recitation registered as funny")

    def test_a_short_sentence_alone_is_not_a_joke(self):
        """The exact bug: a lone short sentence mid-exposition."""
        text = ("The company announced the layoffs on Tuesday morning. "
                "It was 6 a.m. The stock rose four percent on the news "
                "and analysts raised their targets for the coming quarter.")
        self.assertFalse(levity.has_levity(text)["has_levity"])

    def test_it_is_honest_about_what_it_cannot_measure(self):
        self.assertIn("not whether it is funny",
                      levity.has_levity("x")["note"])


class TestTheWritersBrief(unittest.TestCase):
    def test_a_tragedy_brief_says_write_it_straight(self):
        b = levity.brief_for({"title": "Four killed in the collapse"})
        self.assertEqual(b["levity"], "none")
        self.assertIn("straight", b["instruction"])
        self.assertNotIn("moves", b)

    def test_a_light_brief_expects_a_joke_and_shows_how(self):
        b = levity.brief_for({"title": "A raccoon shut down the airport"})
        self.assertEqual(b["levity"], "expected")
        self.assertTrue(b["moves"])
        self.assertTrue(b["never"])

    def test_the_brief_asks_for_exactly_one_aside(self):
        b = levity.brief_for({"title": "Town renames itself for a bet"})
        self.assertIn("ONE", b["instruction"])

    def test_the_anti_patterns_ban_the_obvious_failures(self):
        joined = " ".join(levity.ANTI_PATTERNS).lower()
        for bad in ("pun", "punchline", "exclamation", "wait for it", "emoji"):
            self.assertIn(bad, joined)

    def test_every_move_carries_a_worked_example(self):
        """'Be funny' is not actionable; a move without an example is the
        same adjective in a different coat."""
        for m in levity.MOVES:
            self.assertTrue(m.get("example"), m.get("name"))
            self.assertTrue(m.get("how"), m.get("name"))


class TestItIsWiredWhereScriptsAreWritten(unittest.TestCase):
    def test_the_punchup_mission_asks_for_a_joke(self):
        from shared import exchange_bundle as xb
        mission = xb.build_bundle("20260801", [], [])[
            "instructions"]["punchup_mission"]
        self.assertIn("levity", mission)
        self.assertIn("ONE dry aside", mission["levity"])

    def test_the_takeover_brief_carries_the_moves(self):
        from shared import authoring_brief as brief
        req = brief.build_request("20260801", "trending")
        self.assertTrue(req["levity"]["moves"])
        self.assertIn("death", req["levity"]["hard_gate"].lower())

    def test_the_routine_doc_shows_the_moves(self):
        text = (ROOT / "CLAUDE_ROUTINE_INSTRUCTIONS.md").read_text()
        self.assertIn("flat undercut", text)
        self.assertIn("Top speed: twelve", text)
        self.assertIn("stay completely straight", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
