"""The channel can show a number as a COUNT OF THINGS, not only as a chart.

"every video is stuck with the same graphs and nongraphs ... the channel has no
ability to, on the fly, make graphs or nongraphs ... preferably nongraphs."

The scene kit that was supposed to do this already existed — 1300 lines,
registered, working. Measuring it explained the sameness exactly:

  * a scene must contain at least one RICH element (something that actually
    depicts, not a bare caption), and all three rich types — `object`,
    `fill_object`, `stack` — need a SUBJECT CUTOUT, which means the generative
    image provider: 54-89s per build in testing, with HTTP 500s mid-run.
  * the only rich types that need no image are `orbit_group` and
    `timeline_axis`. Two.
  * offline, the director has exactly two deterministic scene builders. Every
    time-series story on the channel therefore got the identical spec —
    `{"elements": [{"type": "timeline_axis", "region": "full"}]}` — and every
    ranking got no scene at all and fell through to a chart.

So the fix is vocabulary, not another renderer. `unit_figures` is an ISOTYPE:
N copies of one icon, where counting them IS the number. It draws from the
offline icon library, so it costs no image budget and cannot time out, which is
what makes it reachable on any story.

Runs with pytest OR standalone:
    python3 tests/test_isotype_scene.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import viz_scene as vs  # noqa: E402
from data_learning import viz_director as vd  # noqa: E402
from data_learning import studio_render as sr  # noqa: E402


class _Pt:
    def __init__(self, label, value):
        self.label, self.value = label, value


class _Ins:
    def __init__(self, topic, items, unit="", main="", kind="scene"):
        self.topic, self.items, self.unit = topic, items, unit
        self.main_insight, self.kind = main, kind
        self.highlight_label = items[0].label if items else ""
        self.baseline = None


def _housing():
    return _Ins("home prices", [_Pt("2019", 270.0), _Pt("2026", 449.0)],
                "thousand dollars", "Home prices climbed")


class TheUnitIsAlwaysReadable(unittest.TestCase):
    def test_the_legend_unit_is_a_round_number(self):
        """Honouring the authored per_value produced "each = $24.9K", which is
        a worse thing to read than the figure it was meant to soften. A count
        only beats a number when the unit is one a person holds in their head."""
        for value in (449.0, 11.3, 6.72, 20570.0, 3.4, 128000.0):
            _n, per = vs.unit_plan(value, value / 18.0)
            mant = per
            while mant < 1.0:
                mant *= 10.0
            while mant >= 10.0:
                mant /= 10.0
            self.assertAlmostEqual(round(mant, 6) % 1.0, 0.0, places=6,
                                   msg=f"{value} -> each={per}")
            self.assertIn(round(mant), (1, 2, 5), f"{value} -> each={per}")

    def test_the_count_is_countable(self):
        """Three icons is a weak picture; ninety is wallpaper."""
        for value in (449.0, 11.3, 6.72, 20570.0, 3.4, 0.08, 128000.0):
            n, _per = vs.unit_plan(value, value / 18.0)
            self.assertGreaterEqual(n, 6, f"{value} -> {n} figures")
            self.assertLessEqual(n, 60, f"{value} -> {n} figures")

    def test_repackaging_never_changes_the_number(self):
        """The unit is re-scaled for readability; the VALUE is the data and is
        not negotiable. n * per must still be the figure, within one figure."""
        for value in (449.0, 11.3, 6.72, 20570.0, 128000.0):
            n, per = vs.unit_plan(value, value / 18.0)
            self.assertLessEqual(abs(n * per - value), per + 1e-6,
                                 f"{value} -> {n} x {per}")

    def test_a_degenerate_value_still_returns_something_drawable(self):
        for value in (0.0, 1.0, -5.0):
            n, per = vs.unit_plan(value, 1.0)
            self.assertGreaterEqual(n, 1)
            self.assertGreater(per, 0.0)


class ItIsAFirstClassSceneElement(unittest.TestCase):
    def test_it_counts_as_a_real_depiction(self):
        """A scene is rejected unless something in it actually DEPICTS. If the
        isotype were not rich, every scene built from one would be refused."""
        self.assertIn("unit_figures", vs._RICH_TYPES)

    def test_a_valid_isotype_scene_passes_validation(self):
        ins = _housing()
        self.assertTrue(vs.validate(vs.units_scene(ins), ins))

    def test_it_is_refused_without_a_subject_or_a_unit(self):
        ins = _housing()
        for bad in ({"type": "unit_figures", "region": "full",
                     "data": {"value_from": "star", "per_value": 20}},
                    {"type": "unit_figures", "region": "full", "subject": "house",
                     "data": {"value_from": "star"}}):
            self.assertFalse(vs.validate({"elements": [bad]}, ins))

    def test_it_never_reaches_the_generative_image_provider(self):
        """The whole reason it can be used freely. `_IMAGE_TYPES` is the set
        that routes through `scene_media`; the isotype must not be in it."""
        self.assertIn("unit_figures", vs._ICON_TYPES)
        self.assertNotIn("unit_figures", vs._IMAGE_TYPES)

    def test_the_director_can_choose_it_without_spending_image_budget(self):
        self.assertIn("units_scene", vd._SCENE_BUILDERS)
        self.assertFalse(vd.KINDS["units_scene"]["image"],
                         "an offline icon scene must not be rationed")


class ItIsReachableInAVideo(unittest.TestCase):
    def test_it_is_in_the_alternate_pool(self):
        self.assertTrue(any("units_scene" in c
                            for c in sr._SHAPE_CANDIDATES.values()))

    def test_it_reads_as_a_figure_not_a_chart(self):
        """Family alternation is what stops a beat being all charts; an isotype
        classed as a chart would defeat its own purpose."""
        self.assertEqual(sr._family("units_scene"), "figure")

    def test_a_scene_token_is_resolved_to_a_scene_before_rendering(self):
        """It is a BUILDER, not a renderer — rendering kind `units_scene`
        directly would find nothing and fall back to a chart."""
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_SCENE_TOKENS", src)
        self.assertIn('seg.insight.kind = "scene"', src)


class TheBalanceStatesTheTruth(unittest.TestCase):
    """Two numbers weighed against each other. A comparison drawn as two bars
    asks the viewer to measure two lengths against an axis; a balance states
    the same fact as a physical outcome, which needs no axis at all."""

    def test_the_heavier_side_goes_down(self):
        """THE ONE THAT MATTERS. The first version had the signs inverted and
        drew $449K riding UP over $270K — a picture stating the opposite of the
        data, and invisible to any test that only asks whether it rendered."""
        import math
        for a, b in ((449, 270), (270, 449), (11.3, 5.4), (1, 10)):
            dy = math.sin(math.radians(vs.balance_tilt(a, b))) * 300
            left_y, right_y = 500 + dy, 500 - dy       # as drawn
            if a > b:
                self.assertGreater(left_y, right_y, f"{a} vs {b} floats up")
            else:
                self.assertGreater(right_y, left_y, f"{a} vs {b} floats up")

    def test_equal_values_sit_level(self):
        self.assertEqual(vs.balance_tilt(5.0, 5.0), 0.0)

    def test_the_tilt_never_bottoms_out(self):
        """tanh of the log ratio: a 2x gap and a 200x gap must not look the
        same, or the picture stops carrying information exactly where it gets
        interesting."""
        two, big, huge = (vs.balance_tilt(2, 1), vs.balance_tilt(20, 1),
                          vs.balance_tilt(2000, 1))
        self.assertLess(two, big)
        self.assertLessEqual(big, huge)
        self.assertLessEqual(huge, 26.0)

    def test_a_zero_or_missing_side_does_not_explode(self):
        for a, b in ((0, 5), (5, 0), (0, 0)):
            self.assertIsInstance(vs.balance_tilt(a, b), float)

    def test_it_needs_a_second_number_to_weigh_against(self):
        ins = _housing()
        self.assertFalse(vs.validate(
            {"elements": [{"type": "balance", "region": "full",
                           "data": {"value_from": "star"}}]}, ins))

    def test_it_is_refused_when_there_is_no_pair(self):
        one = _Ins("only", [_Pt("A", 1.0)], "count")
        self.assertEqual(vs.balance_scene(one), {})

    def test_it_weighs_the_top_against_the_bottom(self):
        """Deterministic ends, never a cherry-picked middle pair — and both
        sides are labelled, so the viewer is told exactly what is on the
        scales rather than being shown 'the data' with three items dropped."""
        five = _Ins("cost", [_Pt(n, v) for n, v in
                             (("A", 11.3), ("B", 9.7), ("C", 8.2),
                              ("D", 6.8), ("E", 5.4))], "years")
        el = vs.balance_scene(five)["elements"][0]
        self.assertEqual(el["data"]["value_from"], "item:0")
        self.assertEqual(el["data"]["vs_from"], "item:4")


class TheDotFieldOnlyDrawsRealShares(unittest.TestCase):
    """"7 in 100" only means something when the percentage is a share of a
    countable population. The first version keyed off the UNIT alone and drew a
    hundred houses with seven lit for a 6.8% mortgage INTEREST RATE — which is
    not seven houses in a hundred, or seven of anything."""

    def _pct(self, topic, main, value=24.5):
        return _Ins(topic, [_Pt("2026", value)], "percent", main)

    def test_an_interest_rate_is_not_a_population(self):
        self.assertEqual(
            vs.rate_scene(self._pct("mortgage rates", "Rates doubled")), {})

    def test_a_growth_rate_is_not_a_population(self):
        self.assertEqual(
            vs.rate_scene(self._pct("gdp growth", "Growth hit 3.1%")), {})

    def test_a_real_share_is_drawn(self):
        self.assertTrue(vs.rate_scene(
            self._pct("teen licensing",
                      "Share of 17-year-olds with a license")))

    def test_a_non_percent_unit_is_refused(self):
        ins = _Ins("home prices", [_Pt("2026", 449.0)], "thousand dollars",
                   "Share of households priced out")
        self.assertEqual(vs.rate_scene(ins), {})

    def test_the_figures_are_what_the_share_is_a_share_of(self):
        """`icon_subject` picks by topic keyword and handed "teen licensing" an
        ICE CUBE. What the field counts is named in the share phrase that
        allowed the form at all."""
        el = vs.rate_scene(self._pct(
            "teen licensing", "Share of 17-year-olds with a license"))["elements"][0]
        self.assertEqual(el["subject"], "people")
        el2 = vs.rate_scene(self._pct(
            "ownership", "Share of households that own"))["elements"][0]
        self.assertEqual(el2["subject"], "household")

    def test_the_picture_may_round_but_not_restate(self):
        """A RELATIVE error bound was the first attempt and it let 66.7% render
        as "7 in 10" and 33.3% as "8 in 25" — five percent of a big percentage
        is a lot of percentage points."""
        for pct in (6.72, 3.9, 12.5, 25.0, 33.3, 45.6, 66.7, 99.0, 1.0, 2.0):
            k, n = vs.one_in_n(pct)
            self.assertGreater(n, 0, f"{pct} refused unexpectedly")
            self.assertLessEqual(abs(k * 100.0 / n - pct), 0.5,
                                 f"{pct}% drawn as {k} in {n}")

    def test_nothing_lit_is_not_a_picture(self):
        """0.4% used to come back as "0 in 100" — a field of a hundred with
        none of them lit, which says nothing at all."""
        for pct in (0.4, 0.05, 0.0):
            self.assertEqual(vs.one_in_n(pct), (0, 0))

    def test_the_unlit_are_not_a_fainter_copy_of_the_lit(self):
        """They were the same icon at 20% alpha and the field read as a
        hundred identical figures — the one thing the form exists to show
        was the thing you could not see.

        This asserted `"ellipse" in src`, i.e. that the unlit were drawn as
        a DISC. The disc was one way to be a different shape, not the
        property: when "colored dots are not something we should be using"
        (operator, 2026-09-10) turned the units into waffle tiles, a test
        named for shapes failed on a change that kept the shapes distinct.
        Assert the invariant — only the LIT branch may composite the icon.
        """
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(vs.draw_dot_field).lstrip())
        composites = [n for n in ast.walk(tree)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "alpha_composite"
                      and any(isinstance(a, ast.Name) and a.id == "icon"
                              for a in n.args)]
        self.assertEqual(len(composites), 1,
                         "the icon is drawn on more than the lit branch")
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and composites[0] in ast.walk(node):
                self.assertIn("lit", ast.unparse(node.test),
                              "the icon is not gated on `lit`")
                break
        else:
            self.fail("the icon composite is not inside a condition")


class ThePoolOnlyOffersWhatCanBeBuilt(unittest.TestCase):
    def test_a_refusing_builder_is_not_offered(self):
        """A token whose builder returns nothing fails validation and the
        render degrades to a chart: a slot spent, no variety, and nothing
        anywhere saying why."""
        rate_only = _Ins("mortgage rates", [_Pt("2026", 6.8)], "percent",
                         "Rates doubled")
        self.assertFalse(sr._buildable("rate_scene", rate_only))
        one_item = _Ins("solo", [_Pt("A", 1.0)], "count", "One thing")
        self.assertFalse(sr._buildable("balance_scene", one_item))

    def test_a_plain_renderer_is_always_offered(self):
        self.assertTrue(sr._buildable("bars", _housing()))

    def test_the_new_forms_are_reachable_in_a_real_sequence(self):
        seq = sr._depiction_sequence(
            _Ins("cost", [_Pt("A", 11.3), _Pt("B", 6.8)], "years", "A tops",
                 kind="bars"), set(), 12.0)
        # A non-chart FORM, not a scene token specifically: `fill_vessel` and
        # `orbit` are full-frame renderers rather than scene builders and they
        # satisfy this just as well. The first version named the wrong set and
        # broke the moment the picker's rotation chose a different figure.
        self.assertTrue(any(sr._family(k) == "figure" for k in seq[1:]),
                        f"no non-chart form reachable: {seq}")


class TheBrainKnowsWhatItCanCompose(unittest.TestCase):
    """An element the brain is never told about might as well not exist.

    Three offline forms were added to the scene vocabulary — registered,
    validated, rendered, tested — and the forge's ELEMENT KIT prompt still
    listed only the old ones, so the brain could not compose with the only
    elements that reliably work. Exactly the failure CLAUDE.md's rule zero is
    about: a capability nothing calls is not a capability.
    """

    _FORGE = (_REPO / "scripts" / "story_forge.py").read_text()
    _RAW = _FORGE[_FORGE.index("kit = ("):_FORGE.index("ELEMENT KIT")]
    # The prompt is built by concatenating adjacent string literals, so a
    # phrase like "interest rate" is split across a source line and a raw grep
    # misses it. Rejoin the literals to get the text the brain actually sees.
    _KIT = re.sub(r'"\s*\n\s*(#[^\n]*\n\s*)?"', "", _RAW)

    def test_every_offline_element_is_offered_to_the_brain(self):
        for kind in sorted(vs._ICON_TYPES | vs._DRAWN_TYPES):
            self.assertIn(kind, self._KIT,
                          f"{kind!r} exists but the brain is never told")

    def test_every_element_it_offers_actually_exists(self):
        """The other direction: a kit that names something the validator
        rejects sends every scene using it into the fallback chain."""
        import re as _re
        named = set(_re.findall(r"^\s+\"  ([a-z_]+) ", self._KIT, _re.M))
        for kind in named:
            if kind in ("region", "needs", "data"):
                continue
            self.assertIn(kind, vs._TYPES, f"kit offers unknown {kind!r}")

    def test_the_dot_field_warning_survives_in_the_prompt(self):
        """The rule that makes it honest — a percentage is not automatically a
        population — has to reach the thing writing the scene, not just the
        validator that refuses it afterwards."""
        self.assertIn("interest rate", self._KIT)
        self.assertIn("NEVER", self._KIT)

    def test_the_balance_pair_requirement_is_stated(self):
        self.assertIn("vs_from", self._KIT)


class TheHostIsOnIt(unittest.TestCase):
    def test_the_balance_bakes_a_host_too(self):
        import inspect
        self.assertIn("scene_host", inspect.getsource(vs.draw_balance))

    def test_the_scene_host_is_animated_not_a_sticker(self):
        """Every scene element reached for `charts._host_pose`, which loads ONE
        fixed expression PNG — so in a scene the host was a literal sticker for
        the whole beat, while the charts gave him a performance arc. The scene
        kit is the half of the system meant to be expressive."""
        import inspect
        src = inspect.getsource(vs)
        body = src.split("def scene_host", 1)[1]
        self.assertIn("compose_anim", body.split("def draw_caption")[0])
        for fn in (vs.draw_unit_figures, vs.draw_balance, vs.draw_dot_field):
            self.assertNotIn("_host_pose", inspect.getsource(fn),
                             f"{fn.__name__} still pins a single frame")

    def test_the_dot_field_bakes_a_host_too(self):
        import inspect
        self.assertIn("scene_host", inspect.getsource(vs.draw_dot_field))

    def test_the_element_bakes_a_host(self):
        """`render_scene` sets host_baked for EVERY scene, which suppresses the
        travelling overlay — so an element that draws no host ships a beat with
        no host at all. The first version of this did, and a hostless beat is
        what the showrunner records as the mascot missing."""
        import inspect
        self.assertIn("scene_host", inspect.getsource(vs.draw_unit_figures))

    def test_scene_anchors_cannot_crash_the_overlay(self):
        """A full-frame scene returns 4-tuples, not the label dicts the card
        charts produce, and `_stage_on_data` reads them with `.get`. It has
        never blown up only because scenes also set host_baked, which skips
        that path — a coincidence, not a guarantee."""
        seg = _housing()
        self.assertIsNone(sr._stage_on_data(seg, 0.0, 1.0, "point", None,
                                            anchors=[(449.0, "art", 10, 20)]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
