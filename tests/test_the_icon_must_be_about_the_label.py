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
    """`melatonin-kids-er-surge`: "a red CAR clip-art sits on the 'Intensive
    care' row ... it fully covers the 1% value it is meant to annotate" — and
    `junk_imagery` is FATAL, so that one collision cost the whole story.

    THIS ASSERTS THE PROPERTY, NOT THE MECHANISM. It used to read the source
    for `textcoords="offset pixels"`, which was the *first* fix: push the
    value a measured icon-width past the tip. That fix was real and it is
    gone, because a tip carries an icon AND the mascot, and pushing the
    number along the tip only moved which of the two covered it — on the moon
    render the 1980 row's "8 yrs" ended up entirely behind Data. The value
    lives in a measured right-aligned column at the margin now, where nothing
    rides. Asserting on the old mechanism's spelling would have failed that
    strictly better fix, and passed a future one that put the number back
    under the icon in some new way. So: RENDER IT AND MEASURE THE BOXES.
    """

    @staticmethod
    def _render(values):
        import matplotlib
        matplotlib.use("Agg")
        from data_learning import charts as C
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        ins = Insight(kind="pictorial_race", topic="T", main_insight="m",
                      items=[DataPoint(label=l, value=v) for l, v in values],
                      source=Source(name="X", publisher="P", url="https://x",
                                    access_date="2026-09-13"),
                      unit="percent", highlight_label=values[0][0])
        fig, plt = C._card_base()
        ax, specs = C._story_pictorial_race(fig, plt, ins, "", 1.0)
        fig.canvas.draw()
        return fig, plt, ax, specs

    @staticmethod
    def _boxes(ax):
        """Every IMAGE riding the frame — the tip icons AND the mascot."""
        from matplotlib.offsetbox import AnnotationBbox
        out = []
        for a in ax.artists:
            if isinstance(a, AnnotationBbox):
                try:
                    out.append(a.get_window_extent())
                except Exception:               # noqa: BLE001
                    continue
        return out

    def test_no_value_label_is_covered_by_an_icon_or_the_mascot(self):
        """A short bar is the hard case: its tip is deep inside the frame, so
        the icon and the host sit right where a tip-hung number would be."""
        fig, plt, ax, specs = self._render(
            [("Intensive care", 1.0), ("Emergency room", 62.0),
             ("Urgent care", 31.0), ("Clinic", 6.0)])
        try:
            imgs = self._boxes(ax)
            self.assertTrue(imgs, "nothing rides the tips — test is vacuous")
            for value, kind, art, _ in specs:
                bb = art.get_window_extent()
                for ib in imgs:
                    ov = (max(0.0, min(bb.x1, ib.x1) - max(bb.x0, ib.x0))
                          * max(0.0, min(bb.y1, ib.y1) - max(bb.y0, ib.y0)))
                    self.assertEqual(
                        ov, 0.0,
                        f"{art.get_text()!r} is under an image "
                        f"({ov:.0f}px^2 of overlap)")
        finally:
            plt.close(fig)

    def test_the_values_line_up_in_one_column(self):
        """Which is WHY nothing can cover them: they are not at the tips at
        all. A column also makes the numbers comparable down the page, which
        a ragged right edge never was."""
        fig, plt, ax, specs = self._render(
            [("Alpha", 3.0), ("Beta", 58.0), ("Gamma", 91.0)])
        try:
            rights = {round(a.get_window_extent().x1) for _, _, a, _ in specs}
            self.assertEqual(len(rights), 1,
                             f"values do not share a right edge: {rights}")
        finally:
            plt.close(fig)


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
