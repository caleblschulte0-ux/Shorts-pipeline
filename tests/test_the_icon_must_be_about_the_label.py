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


class TheSecondCoverageBlock(unittest.TestCase):
    """2026-09-13. Measured over the whole story config, 499 of 989 segment
    TOPICS — half of every queued beat — resolved no picture at all.

    Most of the commonest words in that miss list SHOULD stay unmatched: a
    "rate", a "share", an "average" is not a picture of anything and forcing
    one is how `junk_imagery` happens. Under them sat three dozen ordinary
    subjects with no row, and an absent row is not neutral — it hands the
    picture to whatever else in the phrase IS listed, which is how "earth
    from space" once opened on a rocket.

    Every key added that day is named here, because `CLAUDE.md` says so and
    because it was earned: "A NAME LOOKED UP WITH A SILENT DEFAULT IS A
    CAPABILITY THAT DOES NOT EXIST."
    """

    ADDED = (
        ("space debris", "1f6f0"), ("orbital debris", "1f6f0"),
        ("debris", "1f6f0"),
        ("box office", "1f3ac"),
        ("office", "1f3e2"), ("workplace", "1f3e2"), ("cubicle", "1f3e2"),
        ("country", "1f30d"), ("countries", "1f30d"), ("nation", "1f30d"),
        ("nations", "1f30d"), ("worldwide", "1f30d"),
        ("language", "1f5e3"), ("languages", "1f5e3"),
        ("linguistic", "1f5e3"), ("spoken", "1f5e3"),
        ("species", "1f43e"), ("animal", "1f43e"), ("animals", "1f43e"),
        ("mammal", "1f43e"), ("mammals", "1f43e"), ("wildlife", "1f43e"),
        ("death", "26b0"), ("deaths", "26b0"), ("fatalities", "26b0"),
        ("mortality", "26b0"),
        ("lake", "1f3de"), ("lakes", "1f3de"), ("reservoir", "1f3de"),
        ("mail", "2709"), ("postal", "2709"), ("post office", "2709"),
        ("letters", "2709"),
        ("transplant", "1fac0"), ("transplants", "1fac0"),
        ("organ donor", "1fac0"),
        ("wolves", "1f43a"),
        ("nebula", "1f30c"), ("galaxy", "1f30c"), ("milky way", "1f30c"),
        ("eclipse", "1f311"), ("solar eclipse", "1f311"),
        ("totality", "1f311"),
        ("cash", "1f4b5"), ("banknote", "1f4b5"), ("paper money", "1f4b5"),
        ("vote", "1f5f3"), ("votes", "1f5f3"), ("voter", "1f5f3"),
        ("voters", "1f5f3"), ("ballot", "1f5f3"), ("election", "1f5f3"),
        ("refugee", "1f9f3"), ("refugees", "1f9f3"), ("asylum", "1f9f3"),
        ("displaced", "1f9f3"),
        ("airport", "1f6eb"), ("airports", "1f6eb"), ("runway", "1f6eb"),
        ("antibiotic", "1f48a"), ("antibiotics", "1f48a"),
        ("prescription", "1f48a"),
        ("surgery", "1f3e5"), ("surgeries", "1f3e5"), ("surgical", "1f3e5"),
        ("operating room", "1f3e5"),
        ("prison", "26d3"), ("prisons", "26d3"), ("inmate", "26d3"),
        ("flood", "1f30a"), ("flooding", "1f30a"),
        ("workweek", "1f4c5"), ("work week", "1f4c5"),
        ("four-day week", "1f4c5"),
        ("pension", "1f3e6"), ("retirement", "1f3e6"),
        ("earthquake", "1f3da"), ("seismic", "1f3da"),
        ("aftershock", "1f3da"),
    )

    def test_every_key_added_that_day_resolves(self):
        bad = {w: (E(w) or "MISS") for w, want in self.ADDED if E(w) != want}
        self.assertEqual(bad, {}, f"keys that do not resolve: {bad}")

    def test_space_debris_is_a_SATELLITE_not_a_launch(self):
        """The whole reason the row moved. `debris` on a row of its own at the
        bottom of the table did NOTHING, because "space" is on the rocket row
        far above it and the first match wins — so every orbital-debris topic
        in the config still launched, and the test that would have caught it
        is this one."""
        for w in ("Space Debris", "orbiting debris", "debris removal cost",
                  "space_debris_removal_debris_growth"):
            self.assertEqual(E(w), "1f6f0", w)
        self.assertEqual(E("rocket launch"), "1f680",
                         "a real launch stopped launching")

    def test_a_box_office_is_a_CINEMA(self):
        """"box office" has to precede "office" or a film-revenue story opens
        on an office block."""
        self.assertEqual(E("box office"), "1f3ac")
        self.assertEqual(E("box office revenue"), "1f3ac")
        self.assertEqual(E("office vacancy rate"), "1f3e2")

    def test_the_subject_beats_the_generic_money_row(self):
        """Every one of these used to come back a banknote because the only
        word in them with a row was an economic one. The table's own stated
        rule — "last resort so specific subjects win first" — now holds one
        level further down."""
        self.assertEqual(E("treatment coverage by country income"), "1f30d")
        self.assertEqual(E("who hosts the displaced, by income level"),
                         "1f9f3")
        self.assertEqual(E("median retirement savings by age"), "1f3e6")

    DELIBERATELY_ABSENT = ("life", "stock", "americans", "obesity",
                           "migration", "rate", "share", "average")

    def test_the_words_left_out_are_still_left_out(self):
        """An abstraction with a picture is worse than an abstraction
        without one: "rate" resolving to ANYTHING puts an unrelated object in
        a frame, and `junk_imagery` is the one FATAL showrunner check.

        The five judgement calls are recorded next to the block in
        `icons.py`, each with its reason — "life" is shelf/battery/expectancy
        and the bare word is a coin flip; "stock" 's honest emoji is a CHART;
        "americans" in "Americans aged 100 and older" is about old age, not a
        flag; "obesity" would take the balance machine's own mark; human and
        bird "migration" want opposite pictures."""
        for w in self.DELIBERATELY_ABSENT:
            self.assertIsNone(E(w), f"{w!r} acquired a picture — if that was "
                                    f"deliberate, move it out of this list "
                                    f"and say why in icons.py")


class ADegreeIsATemperatureNotADiploma(unittest.TestCase):
    """The urban-heat/redlining payoff shipped its unit grid as twenty-one
    graduation caps: "degree" was a graduation key, and in this catalogue a
    degree is almost always heat (FATAL `junk_imagery`, 2026-09-22)."""

    def test_a_bare_degree_finds_no_cap(self):
        from data_learning import icons
        self.assertIsNone(icons.emoji_codepoint("8 degrees hotter"))
        self.assertIsNone(icons.emoji_codepoint("Formerly redlined neighborhoods"))

    def test_heat_and_college_still_resolve(self):
        from data_learning import icons
        self.assertEqual(icons.emoji_codepoint("degrees of heat"), "1f321")
        self.assertEqual(icons.emoji_codepoint("college degree"), "1f393")


if __name__ == "__main__":
    unittest.main()
