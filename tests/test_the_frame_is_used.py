"""A picture must USE the 9:16 frame, not leave half of it empty.

`empty_void` is the showrunner's most-cited block on the data channel, and its
notes are exact enough to be turned into a number:

    "the seesaw in the top ~40% and the entire bottom half as empty gradient"
    "the entire lower two-thirds as blank blue gradient"
    "a hairline timeline at ~45% height ... everything below it empty"
    "one lone bill tile top-left ... and the entire lower 70% empty"

Every one of those is a wide horizontal band of frame with no ink in it. A
vision model catching that is slow, expensive, non-deterministic and only
happens AFTER a full render. `shared/frame_occupancy.py` computes the same
fact from the drawn layer in milliseconds, which is what lets a machine be
TUNED against it rather than argued about.

The root cause was one constant. `RBOT` was 1180 of 1920 — "above the game
strip", a layout this channel has not had for a long time — so the whole
scene kit drew inside the top 61% and left 39% of the frame empty. 158 of the
configured scenes have more than one element and every one of them was
drawing into that box.

MEASURED WITH THE FURNITURE. The studio draws the beat title near the top and
burns the spoken caption near the bottom of every frame, so measuring a bare
machine over-reports the void at both ends — the first cut of this test
flagged ten machines that are fine in production. Only a gap still empty WITH
the title and caption present is a real one.

Runs standalone:  python3 tests/test_the_frame_is_used.py
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

from PIL import Image, ImageDraw                          # noqa: E402
from data_learning import charts, viz_scene as vs         # noqa: E402
from shared import frame_occupancy as fo                  # noqa: E402

BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)


def _furniture(d, topic):
    """What the studio puts on every frame, so the measure matches reality."""
    vs.draw_caption(d, (vs.RX0, 250, vs.RX1, 250), str(topic), 1.0, size=52)
    d.rounded_rectangle([300, 1690, 780, 1748], radius=8,
                        fill=(255, 255, 255, 255))
    d.rounded_rectangle([420, 1860, 660, 1884], radius=6,
                        fill=(255, 255, 255, 160))


class TheSceneKitOwnsTheFrame(unittest.TestCase):
    def test_the_safe_box_reaches_down_the_frame(self):
        """The one constant this whole class is about."""
        self.assertGreaterEqual(
            vs.RBOT, 1500,
            "the scene box stops in the upper half again — every "
            "multi-element scene will leave the bottom of the frame empty")
        self.assertLessEqual(vs.RBOT, 1600,
                             "the box now runs into the caption band")

    def test_a_lone_machine_uses_the_same_box(self):
        self.assertEqual(vs.MACHINE_BOT, vs.RBOT)

    def test_the_regions_all_reach_it(self):
        for name in ("full", "hero", "left", "right", "bottom"):
            self.assertEqual(vs.REGIONS[name][3], vs.RBOT, name)


class NoMachineLeavesAVoid(unittest.TestCase):
    """Every machine, at production size, with the production furniture."""

    CEILING = 0.34

    def test_every_machine_fills_its_box(self):
        from tests._machine_samples import SAMPLES
        bad = {}
        for kind, ins in SAMPLES.items():
            if kind not in vs._MACHINE_DRAW:
                continue
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            safe = vs.drawable_insight(ins)
            if safe is None:
                continue
            got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX, safe,
                              charts.HIGHLIGHT, 0.95, safe.unit)
            if got is None:
                continue
            _furniture(d, ins.topic)
            v = fo.verdict(img, max_void=self.CEILING)
            if not v["ok"]:
                bad[kind] = f"{v['void'] * 100:.0f}% at {v['void_at'] * 100:.0f}%"
        self.assertEqual(bad, {}, f"machines leaving a void: {bad}")


class ANumberIsDEMONSTRATEDNotStated(unittest.TestCase):
    """`bare_number_card` — the reviewer's other standing block on this
    channel, and it had one cause.

    `draw_timeline` has a good depiction: a rising filled area with Data
    riding the leading edge. It reached it only when every item carried a
    `period` attribute, and fell back to `_draw_flat_timeline` — a hairline
    ruler with a number floating above it — when one did not. Requiring a
    separate `period` field is an accident of the data shape: the items were
    labelled 2007..2025.

    The showrunner blocked exactly that on 2026-09-07: "just the text
    '$1,000B' and '2025' floating above a hairline timeline — no filling,
    stacking or comparison; the number is stated, not demonstrated." 122 of
    the configured beats are authored as a `timeline_axis`.

    Measured on the same data before and after: coverage 5.4% -> 35.5%,
    void 31% -> 12%.
    """

    def _render(self, pairs, unit="billion dollars"):
        import tempfile
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-01-01")
        ins = Insight(kind="scene", topic="t", main_insight="m",
                      items=[DataPoint(label=l, value=float(v))
                             for l, v in pairs],
                      source=src, unit=unit, highlight_label=pairs[-1][0])
        ins.scene = {"title": True,
                     "elements": [{"type": "timeline_axis", "region": "full"}]}
        with tempfile.TemporaryDirectory() as td:
            charts.FULLFRAME_RENDERERS["scene"](ins, Path(td), "t", 4)
            fs = sorted(Path(td).glob("*.png"))
            self.assertTrue(fs, "the scene rendered nothing")
            return Image.open(fs[-1]).convert("RGBA")

    def test_a_year_labelled_series_gets_the_CLIMB_not_a_ruler(self):
        img = self._render([(str(2007 + k), v) for k, v in
                            enumerate([560, 600, 640, 700, 760, 820, 880,
                                       940, 1000])])
        m = fo.measure(img)
        self.assertGreater(
            m["coverage"], 0.15,
            f"coverage {m['coverage'] * 100:.1f}% — this is the hairline "
            f"ruler again, not a demonstration")

    def test_the_period_is_derived_from_the_label(self):
        import inspect
        src = inspect.getsource(vs.draw_timeline)
        self.assertIn("THE LABEL IS THE PERIOD", src)

    def test_a_series_with_NO_year_labels_still_falls_back_safely(self):
        """The flat axis is the right answer when there is genuinely no time
        in the data — it must not start claiming one."""
        img = self._render([("Alpha", 5), ("Beta", 9), ("Gamma", 2)])
        self.assertIsNotNone(img)


class TheMeasureItself(unittest.TestCase):
    def test_a_blank_layer_is_all_void(self):
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        self.assertAlmostEqual(fo.measure(img)["void"], 1.0, places=3)

    def test_a_full_layer_has_none(self):
        img = Image.new("RGBA", (200, 400), (255, 255, 255, 255))
        self.assertAlmostEqual(fo.measure(img)["void"], 0.0, places=3)

    def test_it_finds_the_band_and_says_where(self):
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 199, 99], fill=(255, 255, 255, 255))
        d.rectangle([0, 300, 199, 399], fill=(255, 255, 255, 255))
        m = fo.measure(img)
        self.assertAlmostEqual(m["void"], 0.5, places=2)
        self.assertAlmostEqual(m["void_at"], 0.25, places=2)

    def test_a_single_rule_is_not_content(self):
        """A 1px line across an otherwise empty band must not count as ink —
        that is exactly the "hairline timeline" the reviewer blocked."""
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.line([(0, 200), (199, 200)], fill=(255, 255, 255, 255), width=1)
        self.assertGreater(fo.measure(img)["void"], 0.45)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class CoverageThatDependsOnTHEDATA(unittest.TestCase):
    """One sample per machine is not enough for a machine whose geometry
    follows its numbers.

    `test_every_machine_fills_its_box` renders each machine once and passed
    the nest at 28%. On 2026-09-09 the showrunner held
    `melatonin-kids-er-surge` with "the fits-into diagram occupies a small
    box in the upper third" — and at that story's 7.5x ratio the nest
    measured **40% void** against a 34% ceiling. Same machine, same code,
    different data.

    The cause was `side = min(w*0.72, h*0.44, 600)`: a hard 600px cap and a
    0.44 height factor, both left over from when the render box stopped at
    y=1180. In a 1480-tall box they pin the nest to the upper third whatever
    the ratio is.

    It mattered that week because the nest had just been added to `duel` and
    `dominance` — 40% of the catalogue — so a latent void became a daily one.
    """

    CEILING = 0.34      # the same ceiling the per-machine sweep uses

    #: Machines whose drawn area is a function of the values, not just the
    #: item count. These get swept across their whole accepted range.
    DATA_DEPENDENT = {
        "nest": [(r, 1.0) for r in (1.6, 2.5, 4.0, 7.5, 20.0, 60.0, 140.0)],
        "density": [(r, 1.0) for r in (2.0, 10.0, 100.0, 1000.0)],
        "hourglass": [(r, 1.0) for r in (1.2, 3.0, 12.0, 50.0)],
        "tape": [(r, 1.0) for r in (1.05, 2.0, 10.0, 200.0)],
    }

    def test_the_frame_is_filled_at_every_ratio_not_just_one(self):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-09")
        bad = {}
        for kind, pairs in self.DATA_DEPENDENT.items():
            if kind not in vs._MACHINE_DRAW:
                continue
            for big, small in pairs:
                ins = Insight(kind="scene", topic="t", main_insight="m",
                              items=[DataPoint(label="Big", value=float(big)),
                                     DataPoint(label="Small", value=float(small))],
                              source=src, unit="count", highlight_label="Big")
                safe = vs.drawable_insight(ins)
                if safe is None:
                    continue
                img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX,
                                  safe, charts.HIGHLIGHT, 0.95, "count")
                if got is None:
                    continue          # refused honestly, nothing to judge
                _furniture(d, ins.topic)
                v = fo.verdict(img, max_void=self.CEILING)
                if not v["ok"]:
                    bad[f"{kind}@{big:g}x"] = f"{v['void'] * 100:.0f}%"
        self.assertEqual(bad, {}, f"void at some ratios but not others: {bad}")

    def test_the_nest_is_not_capped_to_the_old_render_box(self):
        """The 600px cap and the 0.44 height factor were sized for a frame
        that ended at y=1180. Both are gone; if either returns the nest goes
        back to a square in the upper third."""
        import inspect
        src = inspect.getsource(vs.draw_nest)
        self.assertNotIn("* 0.44", src)
        self.assertNotIn(", 600)", src)


class TheFURNITUREMustNotRescueABareFrame(unittest.TestCase):
    """`NoMachineLeavesAVoid` measures the COMPOSITED frame, and the studio
    puts furniture on every frame it renders. That is right for asking "is the
    finished frame acceptable" and useless for asking "did the machine fill
    the space it was given", because **a band is only as long as the first
    thing that interrupts it**.

    The burnt-in caption at y≈1690 and the progress rule at y≈1860 sit inside
    the bottom void of a short picture and cut it into pieces. A machine that
    stops at 55% of the frame height therefore scores 24% — comfortably inside
    the 34% ceiling — while a viewer sees the bottom half as empty gradient
    and the showrunner writes `empty_void` in exactly those words.

    Measured on 2026-09-09 across the whole kit: **not one machine exceeded
    the composite ceiling**, and ten exceeded 22% inside their own box —
    queue 33%, basket 32%, spotlight 32%, bridge 26%, road 26%, trophies 26%,
    hurdle 26%, density 25%, slider 25%, wheel 22%. Every one of them was a
    picture parked in the upper half of a 9:16 frame.

    So this asks the machine's own question, over the box it was handed, with
    only the studio TITLE composited — that much is genuinely above every
    machine and none of them can be blamed for it.
    """

    #: 24%, against a floor of 12.1% that is simply the gap between the top of
    #: the box and the title. A machine at 24% has roughly a ninth of its own
    #: frame doing nothing, which is the point at which a reviewer starts to
    #: notice; the worst in the kit now sits at 22%.
    CEILING = 0.24

    def _worst(self):
        """The SAME sample per machine the composite sweep uses. Measuring the
        two questions against different data is how a machine ends up with two
        numbers and no answer."""
        from tests._machine_samples import SAMPLES
        worst = {}
        for kind, ins in SAMPLES.items():
            if kind not in vs._MACHINE_DRAW:
                continue
            safe = vs.drawable_insight(ins)
            if safe is None:
                continue
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX, safe,
                              charts.HIGHLIGHT, 0.95, safe.unit)
            if got is None:
                continue              # refused honestly, nothing to judge
            # ONLY the title. The caption and the progress rule are BELOW the
            # box this machine was handed, so letting them into the
            # measurement is letting furniture answer for the picture.
            vs.draw_caption(d, (vs.RX0, 250, vs.RX1, 250), ins.topic, 1.0,
                            size=52)
            worst[kind] = fo.measure(img, top=vs.RTOP,
                                     bottom=vs.MACHINE_BOT)["void"]
        return worst

    def test_no_machine_leaves_a_quarter_of_its_own_box_empty(self):
        bad = {k: f"{v * 100:.0f}%" for k, v in self._worst().items()
               if v > self.CEILING}
        self.assertEqual(bad, {}, f"empty inside their own box: {bad}")

    def test_the_measure_can_be_restricted_to_a_band(self):
        """If `top`/`bottom` were ignored the sweep above would silently be
        measuring the whole frame and passing for the wrong reason."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 20, 99, 30], fill=(255, 255, 255, 255))
        self.assertAlmostEqual(fo.measure(img)["void"], 0.69, places=2)
        self.assertAlmostEqual(fo.measure(img, top=10, bottom=60)["void"],
                               0.58, places=2)

    def test_head_and_tail_are_reported_separately(self):
        """A picture that started late and one that stopped early are
        different defects and get different fixes; one number for both sends
        you to the wrong end of the machine."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 20, 99, 30], fill=(255, 255, 255, 255))
        m = fo.measure(img)
        self.assertAlmostEqual(m["head"], 0.20, places=2)
        self.assertAlmostEqual(m["tail"], 0.69, places=2)

    def test_an_empty_layer_is_all_void_not_an_exception(self):
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        m = fo.measure(img, top=10, bottom=90)
        self.assertEqual((m["void"], m["head"], m["tail"]), (1.0, 1.0, 1.0))

    def test_the_composite_ceiling_is_still_enforced(self):
        """This adds a question; it removes none. The whole-frame sweep in
        `NoMachineLeavesAVoid` stays exactly as it was."""
        import inspect
        src = inspect.getsource(NoMachineLeavesAVoid)
        self.assertIn("_furniture", src)
        self.assertIn("0.34", src + inspect.getsource(fo.verdict))


class TextStaysINSIDETheFrame(unittest.TestCase):
    """The operator watched a video that had already SHIPPED and read back
    what the gate had passed:

        8s   "90 (pre-vaccine)"        the leading 19 outside the frame
        28s  "Not yet vaccinated  9"   the percent sign outside the frame
        20s  two labels printed on top of one another

    The showrunner passed all of it. It reads motion and emptiness; it does
    not read the frame. Nothing in the suite measured whether text was
    INSIDE the picture either — `frame_occupancy` asks whether the frame is
    filled, which a label spilling off the edge technically helps with.

    Measured on the drawn layer with a realistic label ("1990 (pre-vaccine)")
    rather than the test-friendly "A"/"B", five machines put ink in the outer
    six pixels: burden 2.37%, queue 2.22%, tower 1.54%, road 1.34%, pipes
    0.55%. Every one centres its headline with `anchor="mm"` at a fixed x and
    never asks whether it fits.
    """

    #: Deliberately awkward, because the short labels the other sweeps use
    #: are what hid this. The last one is longer than any real dataset label
    #: — a machine that survives it will survive the catalogue.
    LABELS = (
        [("1990 (pre-vaccine)", 4000.0), ("2019 (two-dose era)", 100.0)],
        [("Before the vaccine was introduced nationally", 4000.0),
         ("After", 100.0)],
        [("Massachusetts", 96.5), ("Mississippi", 52.7)],
    )
    EDGE_PX = 6

    def test_no_machine_draws_text_off_the_edge_of_the_frame(self):
        import numpy as np
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-09")
        bad = {}
        for kind in sorted(vs._MACHINE_DRAW):
            for pairs in self.LABELS:
                ins = Insight(kind="scene", topic="cases per year",
                              main_insight="m",
                              items=[DataPoint(label=a, value=float(b))
                                     for a, b in pairs],
                              source=src, unit="count",
                              highlight_label=pairs[0][0])
                safe = vs.drawable_insight(ins)
                if safe is None:
                    continue
                img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX,
                                  safe, charts.HIGHLIGHT, 0.95, "count")
                if got is None:
                    continue
                a = np.asarray(img.split()[-1], dtype=np.float32) > 8
                m = self.EDGE_PX
                worst = max(a[:, :m].mean(), a[:, -m:].mean()) * 100
                if worst > 0.05:
                    bad[kind] = max(bad.get(kind, 0), round(worst, 2))
        self.assertEqual(bad, {}, f"machines drawing past the frame: {bad}")

    def test_the_fitter_shrinks_before_it_truncates(self):
        """The label IS the claim's subject — "1990 (pre-vac..." is a worse
        answer than the same words two points smaller."""
        img = Image.new("RGBA", (1080, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        f, out = vs.fit_text(d, "1990 (pre-vaccine)   4,000", 76, 900)
        self.assertEqual(out, "1990 (pre-vaccine)   4,000", "it truncated")
        self.assertLessEqual(d.textlength(out, font=f), 900)

    def test_it_gives_up_and_ellipsises_rather_than_draw_unreadably_small(self):
        img = Image.new("RGBA", (1080, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        f, out = vs.fit_text(d, "x" * 400, 76, 300)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(d.textlength(out, font=f), 300)
