"""A chart has to be READABLE, and it has to be TRUE.

The operator watched a finished video and asked the only question that matters:
"I'm a smart fucking person, significantly smaller than our target demographic.
And it's like, what the fuck am I looking at?"

Pulling the frames found three separate defects, and only one of them was in
the charts themselves.

  1. NOBODY EVER SAW THEM FINISHED. The build reached its final state on the
     LAST FRAME of its window and then cut away, and the value labels faded in
     over the last 20% on top of that. With a 12-20s beat that still left a few
     seconds of readable chart; when the monotonic edit cut a visual to ~4s the
     same fractions left well under a second, fading, immediately before the
     cut. The charts were fine. They were legible only in frames nobody was
     shown — a defect introduced by shortening the spans without touching the
     ramp that fills them.
  2. NO UNITS. The axis read `449`. 449 what? The renderers had `_ulabel` for
     exactly this and the ranked-bar renderer called `_vfmt` instead.
  3. FALSE CLAIMS, rendered at 40pt. A composition chart generates its subtitle
     from the chart KIND with no reference to what the data is, so a run of
     mortgage rates by year shipped "2019 IS 9% OF THE WHOLE" and a ranking of
     metros shipped "San Jose is 27% of the whole". Those numbers do not sum to
     anything. This is the one that matters most: a channel whose entire
     editorial gate is about real, sourced numbers cannot render a false
     sentence in its largest font.

Runs with pytest OR standalone:
    python3 tests/test_charts_are_readable.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import charts as ch  # noqa: E402
from data_learning import studio_render as sr  # noqa: E402


class _Pt:
    def __init__(self, label, value):
        self.label, self.value = label, value


class _Ins:
    def __init__(self, kind, items, unit=""):
        self.kind, self.items, self.unit = kind, items, unit


def _years(unit="percent"):
    return _Ins("scene", [_Pt(str(y), 3.0 + (y % 5)) for y in range(2019, 2027)],
                unit)


def _cities():
    return _Ins("geo_city", [_Pt(n, v) for n, v in
                             (("San Jose", 11.3), ("Los Angeles", 9.7),
                              ("Miami", 8.2), ("Seattle", 6.8))], "years")


class ReadingTime(unittest.TestCase):
    def test_the_build_finishes_well_before_the_cut(self):
        """The bound moved with the pacing, not to make a number go green.

        0.45 was set when a visual was 3.8s and bought 2.1s of finished chart.
        At the slower 5.8-7.9s spans the same fraction holds a still frame for
        over three seconds, and measured across a whole video that put the
        duplicate ratio at 0.464 against a 0.45 ceiling. 0.62 leaves 2.2-3.0s
        to read — MORE than the old setting gave — while the build keeps moving
        for most of the visual. The invariant that actually matters is the
        reading time, and it is tested directly below."""
        self.assertLessEqual(sr.READ_BY, 0.65)
        self.assertGreaterEqual(sr.READ_BY, 0.25, "no time left to build")

    def test_the_renderer_is_told_to_finish_early(self):
        """`full_by` existed the whole time and nothing passed it."""
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        self.assertIn("full_by=READ_BY", src)

    def test_a_visual_is_readable_for_at_least_a_second_and_a_half(self):
        for dur in (4.0, 8.0, 12.0, 20.0):
            kinds = sr._depiction_sequence(_years(), set(), dur)
            span = (sr._visual_spans(0.0, dur, len(kinds))[0][1]
                    - sr._visual_spans(0.0, dur, len(kinds))[0][0])
            self.assertGreaterEqual(span * (1 - sr.READ_BY), 1.5,
                                    f"{dur}s beat leaves no reading time")

    def test_the_numbers_are_up_before_the_build_ends(self):
        """They used to reach full opacity only at reveal 1.0 — the last frame
        of the span.

        `_lblalpha` takes BUILD progress, not span fraction: reveal reaches 1.0
        at READ_BY of the span. An earlier version of this test compared it
        against READ_BY directly, which conflated the two and broke the moment
        READ_BY moved for an unrelated reason."""
        self.assertEqual(ch._lblalpha(0.3), 0.0,
                         "labels must not appear before the chart draws")
        self.assertEqual(ch._lblalpha(0.7), 1.0,
                         "labels must be fully up well before the build ends")
        self.assertLess(ch._lblalpha(0.5), 1.0, "they should still land, not pop")

    def test_the_host_keeps_performing_after_the_chart_is_done(self):
        """`reveal` saturates, so a host driven by it freezes mid-gesture on a
        finished chart — the whole frame holds still. That dropped segments to
        10.8 fps against a floor of 11.0 the first time reading time was
        added."""
        src = (_REPO / "data_learning" / "charts.py").read_text()
        body = src[src.index("def _bake_host"):]
        self.assertEqual(body.count("_bake_host(") - 0, body.count("_bake_host("))
        calls = [ln for ln in src.splitlines() if "_bake_host(" in ln
                 and not ln.strip().startswith("def ")]
        self.assertTrue(calls)
        joined = "\n".join(src.split("_bake_host(")[1:])
        self.assertNotIn(", reveal,", joined.split("insight.host_baked")[0],
                         "a baked host is still keyed to the saturating reveal")


class UnitsTravelWithTheNumber(unittest.TestCase):
    def test_the_units_this_channel_actually_publishes(self):
        for value, unit, want in ((449, "thousand dollars", "$449K"),
                                  (11.3, "years", "11.3 yrs"),
                                  (6.72, "percent", "6.7%"),
                                  (1500, "dollars", "$1500"),
                                  (3.2, "ratio", "3.2x")):
            self.assertEqual(ch._ulabel(value, unit), want)

    def test_an_unknown_unit_degrades_to_a_bare_number(self):
        self.assertEqual(ch._ulabel(42, "widgets per fortnight"), "42")
        self.assertEqual(ch._ulabel(42, ""), "42")

    def test_no_renderer_labels_a_value_without_its_unit(self):
        """`_vfmt` is the unit-less formatter. It is fine for ticks and ids;
        it is not fine for the number a viewer is meant to take away."""
        src = (_REPO / "data_learning" / "charts.py").read_text()
        bad = [ln.strip() for ln in src.splitlines()
               if "_vfmt(" in ln and ".text(" in ln]
        self.assertEqual(bad, [], f"value labels without units: {bad}")


class ChartsMustNotLie(unittest.TestCase):
    def test_a_time_series_is_never_called_a_share_of_a_whole(self):
        sub = ch._whole_subtitle(_years(), _years().items[0])
        self.assertNotIn("of the whole", sub)
        self.assertIn("2019", sub)

    def test_a_real_composition_still_gets_its_share(self):
        """The bound must not flatten the honest case too."""
        parts = _Ins("stack", [_Pt("A", 50), _Pt("B", 30), _Pt("C", 20)], "")
        self.assertIn("of the whole", ch._whole_subtitle(parts, parts.items[0]))

    def test_the_segment_labels_follow_the_same_rule(self):
        """"2024  16%" beside a mortgage rate is the identical false claim in a
        smaller font. The segment must carry its own VALUE instead — which is
        what the viewer wanted anyway."""
        yrs = _years(unit="thousand dollars")     # not a % unit, so the share
        lab = ch._seg_label(yrs, yrs.items[0], 16.0)   # would be unmistakable
        self.assertNotIn("16%", lab)
        self.assertIn(ch._ulabel(yrs.items[0].value, yrs.unit), lab)

    def test_a_real_composition_segment_still_shows_its_share(self):
        parts = _Ins("stack", [_Pt("A", 50), _Pt("B", 30)], "")
        self.assertIn("16%", ch._seg_label(parts, parts.items[0], 16.0))

    def test_composition_depictions_are_never_chosen_for_other_data(self):
        for ins in (_years(), _cities()):
            seq = sr._depiction_sequence(ins, set(), 20.0)
            for kind in seq[1:]:
                self.assertNotIn(kind, sr._ASSERTS_A_WHOLE,
                                 f"{kind} asserts a whole this data lacks")

    def test_the_filter_is_on_the_pool_not_on_each_list(self):
        """The shape lists are not the only source of candidates — the legacy
        `_ALT_DEPICTION` lookup feeds them too, and pruning the lists alone let
        `stack` back in through the side door."""
        self.assertTrue(sr._ASSERTS_A_WHOLE)
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        self.assertIn("c not in _ASSERTS_A_WHOLE", src)


class NotEverythingIsAChart(unittest.TestCase):
    """Operator: "you don't have to do a fucking chart every time. Right? Like,
    there's millions of ways to convey data." The alternate pool was nine chart
    types, because every candidate was required to be in `viz_director._CONTACT_OK`
    — a set describing CHART couplings — while eight full-frame renderers that
    bake the host themselves sat unused."""

    def test_a_beat_alternates_between_charts_and_figures(self):
        seq = sr._depiction_sequence(_cities(), set(), 20.0)
        fams = [sr._family(k) for k in seq]
        self.assertIn("figure", fams[1:], f"all charts: {seq}")

    def test_every_figure_form_actually_resolves_to_a_renderer(self):
        """Either it IS a full-frame renderer, or it is a scene TOKEN whose
        builder attaches a spec that `scene` renders. A name in neither camp
        silently falls back to a chart, which is how this pool ends up all
        charts again without anything looking broken."""
        import data_learning.charts as c
        for kind in sr._SELF_HOSTED:
            self.assertTrue(
                kind in c.FULLFRAME_RENDERERS or kind in sr._SCENE_TOKENS,
                f"{kind!r} renders nothing — it will degrade to a chart")

    def test_every_scene_token_has_a_builder_that_exists(self):
        from data_learning import viz_scene as vs
        for token, builder in sr._SCENE_TOKENS.items():
            self.assertTrue(callable(getattr(vs, builder, None)),
                            f"{token!r} names a builder that is not there")

    def test_the_slow_image_renderers_stay_out_of_the_pool(self):
        """`diorama`, `mechanic`, `scene` and `race` need generated imagery —
        54-89s per build with HTTP 500s mid-run. Fine as a primary the story
        commits to; not as an alternate that can time out a render."""
        for kind in ("diorama", "mechanic", "race"):
            for cands in sr._SHAPE_CANDIDATES.values():
                self.assertNotIn(kind, cands)

    def test_the_primary_depiction_counts_as_a_figure(self):
        """`scene` is the primary on most beats. Calling it a chart made the
        alternation start on the wrong foot and hand the beat two figures."""
        self.assertEqual(sr._family("scene"), "figure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
