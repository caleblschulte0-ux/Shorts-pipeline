"""A HOUSE ON "CURRENT RECORD", A CAR ON "INTENSIVE CARE".

`junk_imagery` is the showrunner's ONE fatal check. It blocks at any score, on
any policy, because mismatched imagery is a trust defect rather than a craft
one — "quality can dip" does not cover publishing visuals that misrepresent
the data. So every time it fires, the story is gone: not held for a rebuild,
gone.

It fired 63 times in 405 recorded verdicts. On the data channel the same
sentence kept coming back:

    2026-09-02  f1-pit-stop-vanishing-act
        "a cartoon HOUSE icon sits on the 'Current record' row marker"
    2026-09-03  f1-pit-stop-vanishing-act   (twice)
    2026-09-04  f1-pit-stop-vanishing-act   (twice)
    2026-09-08  f1-pit-stop-vanishing-act
    2026-09-09  f1-pit-stop-vanishing-act
        "a yellow house/building glyph is parked on the 'Current record' bar,
         clipping through it and covering the label text"
    2026-09-09  melatonin-kids-er-surge
        "a red CAR clip-art sits on the 'Intensive care' row ... the car is an
         off-topic vehicle cutout and it fully covers the 1% value it is meant
         to annotate"

Six blocked renders of ONE story in a week, and every one of them was
`emoji_codepoint` doing `key in label.lower()`:

    "cur-RENT-record"   matched the housing key   -> 🏠
    "CAR-e"             matched the vehicle key   -> 🚗

The judge was right every single time. Nobody read the code.

Two fixes, both here. A key now has to be a prefix of a whole TOKEN with only
a plain inflection left over (a longer key may be a deliberate stem —
"vaccin", "immuniz", "agricultur"), and the short-bar value label is offset
past the icon's real display width instead of past the bar tip.

Runs standalone:  python3 tests/test_the_icon_must_be_about_the_label.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data_learning import icons  # noqa: E402

E = icons.emoji_codepoint
HOUSE, CAR, MICROBE, MONEY = "1f3e0", "1f697", "1f9a0", "1f4b5"


class TheVerdictsThatCostUsAWeek(unittest.TestCase):
    """Named cases, quoted from the ledger. These are not hypotheticals."""

    def test_current_record_is_not_a_house(self):
        self.assertIsNone(E("Current record"))
        self.assertIsNone(E("current record"))

    def test_intensive_care_is_not_a_car(self):
        self.assertIsNone(E("Intensive care"))

    def test_the_rest_of_that_chart_is_clean_too(self):
        for label in ("Emergency department", "Poison control calls",
                      "Hospitalised", "Pit stop", "Fastest lap"):
            got = E(label)
            self.assertNotIn(got, (HOUSE, CAR), f"{label!r} -> {got}")


class ASubstringIsNotAWord(unittest.TestCase):
    """The general form. Every one of these was live in the table."""

    CASES = (
        # label,               must NOT be
        ("Detour signage", None),           # "tour" -> music
        ("Coalition seats", None),          # "coal" -> oil pipe
        ("Costa Rica", None),               # "cost" -> banknote
        ("Kidney disease", CAR),            # "kid" -> child (disease wins)
        ("Development index", None),        # "ev" -> vehicle
        ("Revenue per user", None),         # "ev" -> vehicle
        ("Seven-day average", None),        # "ev" -> vehicle
        ("Level crossing", None),           # "ev" -> vehicle
        ("Category share", None),           # "cat" -> cat
        ("Bandwidth", None),                # "band" -> music
        ("Search volume", None),            # "sea" -> ocean
        ("Seasonal average", None),         # "sea" -> ocean
        ("Readiness score", None),          # "read" -> book
        ("Reporting lag", None),            # "port" -> ship
        ("Card payments", None),            # "car"+"d" -> vehicle
    )

    def test_none_of_these_pick_up_a_stray_icon(self):
        bad = {}
        for label, forbidden in self.CASES:
            got = E(label)
            if forbidden is None:
                if got is not None:
                    bad[label] = got
            elif got == forbidden:
                bad[label] = got
        self.assertEqual(bad, {}, f"substring collisions: {bad}")

    def test_ev_only_matches_the_word_ev(self):
        self.assertEqual(E("EV"), CAR)
        self.assertEqual(E("EVs"), CAR)
        self.assertIsNone(E("Every household"))


class ItStillMatchesWhatItIsFOR(unittest.TestCase):
    """A stricter rule that stops matching the real catalogue is not a fix,
    it is the same bug with the icons removed."""

    CASES = (
        ("Rent", HOUSE), ("Housing costs", HOUSE), ("Mortgage", HOUSE),
        ("Cars sold", CAR), ("Vehicle registrations", CAR),
        ("Vaccination rate", MICROBE), ("Immunization coverage", MICROBE),
        ("Measles cases", None),
        ("Median wage", MONEY), ("Household income", MONEY),
        ("Agriculture, value added", "1f33e"),
        ("Employment rate", "1f477"),
        ("Manufacturing output", "1f3ed"),
        ("Children under five", "1f9d2"),
        ("Cattle", "1f404"), ("Beef production", "1f404"),
        ("Coal", "1f6e2"), ("Natural gas", "1f6e2"),
        ("Cities over 1m", "1f3d9"),
        ("Rail passengers", "1f686"),
        ("Seasonal workers", "1f477"),
    )

    def test_the_real_labels_still_get_their_icon(self):
        bad = {}
        for label, want in self.CASES:
            got = E(label)
            if got != want:
                bad[label] = f"{got} (wanted {want})"
        self.assertEqual(bad, {}, f"lost matches: {bad}")

    def test_a_stem_key_still_matches_its_whole_family(self):
        """Several keys are deliberate stems. The word-boundary rule must not
        break them, which is what the six-character line is for."""
        for w in ("vaccine", "vaccinated", "vaccination"):
            self.assertEqual(E(w), MICROBE, w)
        for w in ("agriculture", "agricultural"):
            self.assertEqual(E(w), "1f33e", w)

    def test_the_more_specific_key_wins(self):
        """The table says so in a comment; "drinking water" used to come out a
        breaking WAVE because the generic water key was listed first."""
        self.assertEqual(E("Drinking water"), "1f6b0")
        self.assertEqual(E("Freshwater access"), "1f6b0")
        self.assertEqual(E("Ocean temperature"), "1f30a")


class TheIconDoesNotCoverTheNumber(unittest.TestCase):
    """`melatonin-kids-er-surge`: "it fully covers the 1% value it is meant to
    annotate". A short bar's value was placed a few DATA units past the tip
    while the icon centred on that tip is ~65 DISPLAY pixels wide."""

    def test_the_short_bar_value_is_offset_past_the_icon(self):
        import inspect
        from data_learning import charts
        src = inspect.getsource(charts._story_pictorial_race)
        self.assertIn("_icon_px", src)
        self.assertIn('textcoords="offset pixels"', src)

    def test_the_offset_is_derived_from_the_image_not_guessed(self):
        import inspect
        from data_learning import charts
        src = inspect.getsource(charts._story_pictorial_race)
        self.assertIn('getattr(img, "shape"', src)


class NoLabelEverGetsAnIconFromANUMBER(unittest.TestCase):
    """Years and bare values are labels too, and none of them mean anything
    pictorially."""

    def test_years_and_numbers_match_nothing(self):
        for label in ("2019", "1990", "12.4", "-3", "0", "1,400", "%"):
            self.assertIsNone(E(label), label)

    def test_an_empty_label_is_not_an_error(self):
        for label in ("", None, "   "):
            self.assertIsNone(E(label))


if __name__ == "__main__":
    unittest.main()
