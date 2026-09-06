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


class TheHostIsOnIt(unittest.TestCase):
    def test_the_element_bakes_a_host(self):
        """`render_scene` sets host_baked for EVERY scene, which suppresses the
        travelling overlay — so an element that draws no host ships a beat with
        no host at all. The first version of this did, and a hostless beat is
        what the showrunner records as the mascot missing."""
        import inspect
        self.assertIn("_host_pose", inspect.getsource(vs.draw_unit_figures))

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
