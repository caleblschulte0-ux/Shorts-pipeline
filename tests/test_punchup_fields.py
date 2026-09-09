"""A punch-up may not fabricate in the TITLE either (doctor 0bf9780d6272).

`punchup_guard.apply` copies title, hook, hashtags and punches straight out
of the rewrite, and for a year `check()` inspected none of them — only
script-to-script. So a rewrite could leave the script byte-identical, pass
every claim and structure check, and put an unsupported percentage or the
wrong company on the one line most viewers actually read.

These are the three cases the finding named, plus the swap cases that an
invention check alone does not catch.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import punchup_guard as pg          # noqa: E402

SCRIPT = (
    "Rents in Austin fell twelve percent last year, the steepest drop the city "
    "has recorded. Landlords blamed a wave of new supply: 21 towers opened in "
    "eighteen months. Tenants who signed in 2023 are still paying the old "
    "rate. The city council meets in March to decide whether the incentives "
    "that built those towers continue. Austin is not alone, but it fell "
    "hardest, and 12% is the number every other market is now watching very "
    "closely as leases come up for renewal across the whole country."
)


def _pkg(**over) -> dict:
    base = {
        "title": "Austin Rents Fell 12%",
        "hook": "Austin rents fell 12% and nobody noticed",
        "script": SCRIPT,
        "shots": [{"phrase": "Rents in Austin", "query": "austin skyline"}],
        "punches": [{"phrase": "fell twelve percent", "text": "12% DOWN",
                     "color": "#fff"}],
        "hashtags": ["#austin", "#rent"],
    }
    base.update(over)
    return base


class TheScriptIsNotTheOnlyPlaceAClaimLives(unittest.TestCase):
    def test_an_unsupported_percentage_in_the_title_is_refused(self):
        """The finding's headline case: script untouched, title fabricated."""
        bad = _pkg(title="Austin Rents Fell 40%")
        ok, problems = pg.check(_pkg(), bad)
        self.assertFalse(ok, "a 40% nowhere in the package shipped in the title")
        self.assertTrue(any("title" in p for p in problems), problems)
        self.assertIsNone(pg.apply(_pkg(), bad))

    def test_a_rate_swapped_for_another_rate_the_script_contains(self):
        """The case an invention check alone cannot catch.

        Both 12% and 8% appear in the original, so neither is invented — but
        the title said one thing and now says the other, and the story it
        summarizes did not change."""
        orig = _pkg(script=SCRIPT + " Dallas fell 8% over the same period.")
        bad = dict(orig, title="Austin Rents Fell 8%")
        ok, problems = pg.check(orig, bad)
        self.assertFalse(ok, "12% -> 8% in the title passed")
        self.assertTrue(any("SWAP" in p.upper() for p in problems), problems)

    def test_the_wrong_company_in_the_title_is_refused(self):
        orig = _pkg(title="Tesla Recalls Two Million Cars",
                    hook="Tesla recalls two million cars",
                    script=SCRIPT + " Tesla and Ford both build here.")
        bad = dict(orig, title="Ford Recalls Two Million Cars")
        ok, problems = pg.check(orig, bad)
        self.assertFalse(ok, "a Tesla headline became a Ford headline")
        self.assertTrue(any("entity" in p.lower() for p in problems), problems)

    def test_an_entity_from_nowhere_in_the_hook_is_refused(self):
        bad = _pkg(hook="Blackstone quietly caused Austin's 12% drop")
        ok, problems = pg.check(_pkg(), bad)
        self.assertFalse(ok, "Blackstone appears nowhere in the original")
        self.assertTrue(any("hook" in p for p in problems), problems)

    def test_a_fabricated_punch_overlay_is_refused(self):
        bad = _pkg(punches=[{"phrase": "fell twelve percent",
                             "text": "40% DOWN", "color": "#fff"}])
        ok, problems = pg.check(_pkg(), bad)
        self.assertFalse(ok, "the burned-in overlay was never checked")
        self.assertTrue(any("punch" in p.lower() for p in problems), problems)

    def test_an_invented_hashtag_entity_is_refused(self):
        """Casing-dependent by admission — see the note in field_problems."""
        bad = _pkg(hashtags=["#austin", "#Blackstone"])
        ok, problems = pg.check(_pkg(), bad)
        self.assertFalse(ok)
        self.assertTrue(any("hashtag" in p.lower() for p in problems), problems)


class LegitimatePunchUpsStillPass(unittest.TestCase):
    """A guard that refuses everything is an off switch, not a guard."""

    def test_wording_only_title_change_passes(self):
        good = _pkg(title="Austin Rents Just Fell 12%")
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)
        self.assertIsNotNone(pg.apply(_pkg(), good))

    def test_a_title_that_drops_its_number_passes(self):
        """A headline that states less is not a headline that states false."""
        good = _pkg(title="The Austin Rent Drop Nobody Saw Coming")
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)

    def test_pulling_a_number_out_of_the_script_into_the_title_passes(self):
        """21 towers is in the script; promoting it to the title is a punch-up,
        not a fabrication — the pool is the whole original package."""
        good = _pkg(title="21 Towers Opened And Austin Rents Fell")
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)

    def test_emphasis_recasing_in_the_hook_is_not_an_invented_entity(self):
        good = _pkg(hook="Austin rents FELL 12% and NOBODY noticed")
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)

    def test_an_unchanged_package_passes(self):
        ok, problems = pg.check(_pkg(), _pkg())
        self.assertTrue(ok, problems)

    def test_a_rewrite_that_omits_the_title_keeps_the_original(self):
        """`apply` only copies truthy fields, so an absent title is not a
        change and must not be judged as one."""
        good = {k: v for k, v in _pkg().items() if k != "title"}
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)
        merged = pg.apply(_pkg(), good)
        self.assertEqual(merged["title"], "Austin Rents Fell 12%")


class TheGuardIsNotAnOffSwitch(unittest.TestCase):
    """Measured against every real package in the tree, not reasoned about.

    A claim guard that refuses honest rewords costs the channel every
    punch-up silently — the original ships and nothing turns red. The first
    draft of the field rules did exactly that: `proper_nouns` reads a Title
    Case headline as a line of entities, so "The Austin Rent Drop Nobody Saw
    Coming" was refused for inventing "Saw". These numbers are why
    `_field_entities` exists.
    """

    @classmethod
    def setUpClass(cls):
        import glob
        import json
        cls.pkgs = []
        for f in sorted(glob.glob(str(ROOT / "state" / "trending_packages"
                                      / "*" / "*.json"))):
            try:
                with open(f) as fh:
                    d = json.load(fh)
            except Exception:
                continue
            for pkg in (d if isinstance(d, list) else [d]):
                if isinstance(pkg, dict) and pkg.get("script") and pkg.get("title"):
                    cls.pkgs.append(pkg)

    def test_there_are_real_packages_to_measure(self):
        self.assertGreaterEqual(len(self.pkgs), 50,
                                "no corpus — the measurements below prove nothing")

    def test_no_real_package_rejects_itself(self):
        bad = [p["title"] for p in self.pkgs if not pg.check(p, p)[0]]
        self.assertEqual(bad, [], "a package the pipeline shipped fails its own guard")

    def test_a_wording_only_title_reword_is_never_refused(self):
        bad = []
        for p in self.pkgs:
            r = dict(p, title="The " + str(p["title"]).strip())
            ok, problems = pg.check(p, r)
            if not ok:
                bad.append((p["title"], problems))
        self.assertEqual(bad[:3], [], f"{len(bad)}/{len(self.pkgs)} refused")

    def test_a_fabricated_title_percentage_is_caught_across_the_corpus(self):
        missed = [p["title"] for p in self.pkgs
                  if pg.check(p, dict(p, title=p["title"] + " - 97% Of Them"))[0]]
        # Not 100%: a package whose script already says 97% is not fabricating.
        self.assertLess(len(missed), max(3, len(self.pkgs) * 0.02),
                        f"{len(missed)} packages accepted an unsupported 97%")

    def test_an_invented_entity_in_the_hook_is_caught_across_the_corpus(self):
        missed = [p["title"] for p in self.pkgs
                  if pg.check(p, dict(p, hook="Zorbatek confirmed every word"))[0]]
        self.assertEqual(missed, [])


class TitleCaseIsNotAListOfNames(unittest.TestCase):
    def test_a_camelcase_brand_invented_in_a_title_is_still_caught(self):
        """The one entity signal that survives Title Case."""
        bad = _pkg(title="SpaceX Caused The Austin Rent Drop")
        ok, problems = pg.check(_pkg(), bad)
        self.assertFalse(ok, problems)
        self.assertTrue(any("entity" in p.lower() for p in problems), problems)

    def test_an_all_caps_overlay_reword_is_not_an_invented_entity(self):
        """A punch overlay is ALL CAPS by spec, so casing says nothing."""
        good = _pkg(punches=[{"phrase": "fell twelve percent",
                              "text": "12% LOWER", "color": "#fff"}])
        ok, problems = pg.check(_pkg(), good)
        self.assertTrue(ok, problems)

    def test_informative_caps_reads_a_sentence_and_a_headline_apart(self):
        self.assertTrue(pg._informative_caps("Austin rents fell 12% last year"))
        self.assertFalse(pg._informative_caps("Austin Rents Fell 12% Last Year"))
        self.assertFalse(pg._informative_caps("12% DOWN AND FALLING"))


class TheGuardIsWiredIntoApply(unittest.TestCase):
    def test_apply_refuses_a_title_only_fabrication(self):
        """The whole point: the script is perfect, so only the field check
        can stop this."""
        orig = _pkg()
        bad = _pkg(title="Austin Rents Fell 40%")
        self.assertEqual(bad["script"], orig["script"])
        self.assertIsNone(pg.apply(orig, bad))

    def test_field_problems_is_callable_on_its_own(self):
        self.assertEqual(pg.field_problems(_pkg(), _pkg()), [])
        self.assertTrue(pg.field_problems(_pkg(), _pkg(title="Rents Fell 40%")))


if __name__ == "__main__":
    unittest.main()
