"""THE FORGE READS THE WHOLE CATALOGUE, NOT THE CORNER IT CAN PRONOUNCE.

Explainer run 44833841540 (2026-11-21 00:22 UTC), forge step with
`--count 8`: "themes available: population(3) / [population] only 0 usable
series — banked / forged 0". With 69 indicators used and 31 remembered as
unusable, THREE candidates were left in four World Bank databases of
thousands. The well was dry because `candidates()` drank from a corner:

  * THEMES named "migration" and "refugee" but `_FAMILIES` had no `SM.`,
    so every migration indicator was dropped — a theme with no members;
  * gender and society (`SG.`) had neither a family nor a theme;
  * every name with a comma was refused, and the World Bank writes
    "Mortality rate, infant", "Population, total", "School enrollment,
    primary" — the standard naming — to catch "Immunization, DPT", whose
    fault is the catalogue CODE, not the comma.

Held here: the qualifier is turned round into words a voice can say, a
capitals-only token is refused, SM. and SG. are read, and the refusals
that were right (gendered, over-long, parenthesised unit) still stand.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import story_forge as sf                   # noqa: E402

CATALOGUE = [
    {"id": "SP.DYN.IMRT.IN", "name": "Mortality rate, infant (per 1,000 live births)", "source": 2},
    {"id": "SP.POP.TOTL", "name": "Population, total", "source": 2},
    {"id": "SE.PRM.ENRR", "name": "School enrollment, primary (% gross)", "source": 12},
    {"id": "SH.IMM.IDPT", "name": "Immunization, DPT (% of children ages 12-23 months)", "source": 16},
    {"id": "SH.DYN.AIDS.ZS", "name": "Prevalence of HIV, total (% of population ages 15-49)", "source": 16},
    {"id": "SP.POP.TOTL.FE.IN", "name": "Population, female", "source": 2},
    {"id": "SM.POP.NETM", "name": "Net migration", "source": 2},
    {"id": "SM.POP.REFG", "name": "Refugee population by country or territory of asylum", "source": 2},
    {"id": "SG.GEN.PARL.ZS", "name": "Proportion of seats held by women in national parliaments (%)", "source": 75},
    # a short gender name (synthetic): the family and theme, not the length
    {"id": "SG.GEN.TEST.ZS", "name": "Women in parliament (% of seats)", "source": 75},
    {"id": "EN.ATM.CO2E.PC", "name": "CO2 emissions (metric tons per capita)", "source": 2},
    {"id": "NY.GDP.MKTP.CD", "name": "GDP (current US$)", "source": 2},
    {"id": "SE.PRM.UNER.MA", "name": "Children out of school, primary, male", "source": 12},
]


def _topics():
    with mock.patch.object(sf, "wb_indicators", lambda: CATALOGUE):
        pool = sf.candidates(set())
    return {s["id"]: (theme, s["topic"]) for theme, lst in pool.items() for s in lst}


class TheQualifierIsTurnedIntoWords(unittest.TestCase):
    def test_mortality_rate_infant_is_infant_mortality_rate(self):
        self.assertEqual(sf._speakable("Mortality rate, infant"), "infant mortality rate")
        self.assertEqual(sf._speakable("Population, total"), "total population")
        self.assertEqual(sf._speakable("School enrollment, primary"), "primary school enrollment")

    def test_a_long_or_double_qualifier_keeps_its_comma_and_is_refused(self):
        self.assertIn(",", sf._speakable("Children out of school, primary, male"))
        self.assertIn(",", sf._speakable("Mortality rate, adult, female"))
        self.assertNotIn("SE.PRM.UNER.MA", _topics())

    def test_a_comma_free_name_is_untouched(self):
        self.assertEqual(sf._speakable("Forest area"), "Forest area")


class TheCatalogueCodeIsTheFault(unittest.TestCase):
    def test_a_capitals_only_token_is_refused(self):
        got = _topics()
        self.assertNotIn("SH.IMM.IDPT", got, "DPT is a code, not a word")
        self.assertNotIn("SH.DYN.AIDS.ZS", got, "HIV is a code")
        self.assertNotIn("NY.GDP.MKTP.CD", got, "GDP is money, and a code")

    def test_co2_is_spoken_and_kept(self):
        self.assertEqual(_topics()["EN.ATM.CO2E.PC"], ("climate", "CO2 emissions"))


class TheWellIsAsWideAsTheDoctrine(unittest.TestCase):
    def test_the_standard_names_are_drawn(self):
        got = _topics()
        self.assertEqual(got["SP.DYN.IMRT.IN"], ("health", "infant mortality rate"))
        self.assertEqual(got["SP.POP.TOTL"], ("population", "total population"))
        self.assertEqual(got["SE.PRM.ENRR"], ("learning", "primary school enrollment"))

    def test_a_theme_has_members(self):
        """THEMES named refugees and migration; the family filter dropped
        every one of them. A name looked up with a silent default."""
        got = _topics()
        self.assertEqual(got["SM.POP.NETM"], ("population", "Net migration"))
        self.assertNotIn("SM.POP.REFG", got, "eight words is not a subject")
        self.assertEqual(got["SG.GEN.TEST.ZS"], ("society", "Women in parliament"))
        self.assertNotIn("SG.GEN.PARL.ZS", got, "nine words is not a subject")
        for theme, keys in sf.THEMES.items():
            self.assertTrue(keys, theme)

    def test_every_theme_keyword_can_reach_a_family(self):
        """No theme keyword names a World Bank topic whose family prefix is
        excluded: 'refugee' -> SM., 'women' -> SG."""
        for fam in ("SM.", "SG."):
            self.assertIn(fam, sf._FAMILIES)

    def test_the_right_refusals_still_stand(self):
        got = _topics()
        self.assertNotIn("SP.POP.TOTL.FE.IN", got, "gendered subjects are refused")
        self.assertNotIn("SE.PRM.UNER.MA", got, "three-part names are refused")


if __name__ == "__main__":
    unittest.main()
