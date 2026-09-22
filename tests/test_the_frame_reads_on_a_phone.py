"""EVERY WORD ON THE FRAME IS READABLE ON A PHONE, AND DATA COVERS NONE OF THEM.

Ninety-nine of the 110 verdicts since 2026-09-15 were blocks, and the
showrunner's notes on them repeat five defects that are all geometry:

  "the mascot stands on the 2006 bar's value label: '12500' reads '1 0'"
  "Data is parked on top of the header so 'largest container ship capacity
   by year' is occluded mid-word"
  "'it never settled' collides with the scene title"
  "'Prevention & man' is sliced off by the right frame edge ... the
   seesaw's own values off the left edge"
  "'Soy, Mining, Logging &' is cut by the right frame edge"
  "recap labels ~8px grey on dark and vanish at arm's length"

Each is measured here on the drawn layer, the way `test_the_frame_is_used`
measures the void, so the fix can be held rather than argued about.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

import numpy as np                                        # noqa: E402
from PIL import Image, ImageDraw                          # noqa: E402
from data_learning import charts, viz_scene as vs         # noqa: E402
from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-09")
TOPIC = "Amazon deforestation by year"
SERIES = [("1990 (pre-vaccine)", 4000.0), ("2005", 2600.0),
          ("2010", 3100.0), ("2019 (two-dose era)", 100.0)]


def _insight(pairs, kind="scene", unit="count", topic=TOPIC):
    ins = Insight(kind=kind, topic=topic, main_insight="m",
                  items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                  source=SRC, unit=unit, highlight_label=pairs[0][0])
    return ins


def _alpha(img):
    return np.asarray(img.split()[-1]) > 8


class TheTitleBandIsTheTitles(unittest.TestCase):
    """Seven machines drew through the beat title at y=250 (fan 18.6% of the
    band, sorter 17.9%, nest 16.7%, gears, darts, staircase, spotlight —
    measured 2026-09-22). `render_scene` now starts every box under the
    title as drawn."""

    def test_the_clearance_is_measured_from_the_drawn_title(self):
        one = vs.title_clearance("short title")
        two = vs.title_clearance("a title so long that the fitter has to wrap "
                                 "it onto a second line to keep it readable")
        self.assertGreater(one, 300)
        self.assertGreater(two, one, "a two-line title clears more")
        self.assertEqual(vs.title_clearance(""), vs.RTOP)

    def test_no_machine_puts_ink_in_the_title_band(self):
        clear = vs.title_clearance(TOPIC)
        box = (vs.RX0, clear, vs.RX1, vs.MACHINE_BOT)
        bad = {}
        for kind in sorted(vs._MACHINE_DRAW):
            safe = vs.drawable_insight(_insight(SERIES))
            if safe is None:
                continue
            for rv in (0.5, 0.95):
                img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, box,
                                  safe, charts.HIGHLIGHT, rv, "count")
                if got is None:
                    continue
                a = _alpha(img)
                band = a[vs.TITLE_Y:vs.TITLE_Y + 66, :].mean() * 100
                above = a[:clear, :].mean() * 100
                if band > 0.3 or above > 0.05:
                    bad[kind] = (round(band, 1), round(above, 2))
        self.assertEqual(bad, {}, f"machines drawing into the title: {bad}")

    def test_render_scene_lowers_the_boxes_only_under_a_title(self):
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        i = src.index("def render_scene(")
        body = src[i:i + 12000]
        self.assertIn("title_clearance(insight.topic)", body)
        self.assertIn("if show_title:", body[:body.index("title_clearance")])


class TheClimberNeverStandsOnANumber(unittest.TestCase):
    STEPS = [(str(y), float(v)) for y, v in
             ((1996, 6600), (2006, 12500), (2013, 18000), (2019, 24000))]

    def _box(self):
        return (vs.RX0, vs.title_clearance(TOPIC), vs.RX1, vs.MACHINE_BOT)

    def test_his_head_clears_the_box_top_on_the_tallest_step(self):
        box = self._box()
        safe = vs.drawable_insight(_insight(self.STEPS))
        for rv in (0.4, 0.7, 1.0):
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            vs.draw_staircase(ImageDraw.Draw(img), img, box, safe,
                              charts.HIGHLIGHT, rv, "count")
            self.assertEqual(_alpha(img)[:box[1], :].sum(), 0,
                             f"ink above the box top at reveal {rv}")

    def test_the_value_he_arrives_on_is_not_under_his_feet(self):
        """A solid magenta stand-in for Data; none of it may land where the
        step's value is printed, at any point of the climb."""
        box = self._box()
        safe = vs.drawable_insight(_insight(self.STEPS))
        bx0, by0, bx1, by1 = box
        top = max(by0 + vs.STAIR_HOST_H + 30, 340)
        bot = by1 - 120
        n = len(self.STEPS)
        w = (bx1 - bx0 - 160) / n
        vals = [v for _, v in self.STEPS]
        lo, hi = min(vals), max(vals)
        sprite = Image.new("RGBA", (200, 300), (255, 0, 255, 255))
        for rv in (0.42, 0.68, 0.93, 1.0):
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            with mock.patch.object(vs, "scene_host", return_value=sprite):
                vs.draw_staircase(ImageDraw.Draw(img), img, box, safe,
                                  charts.HIGHLIGHT, rv, "count")
            px = np.asarray(img)
            magenta = (px[:, :, 0] > 200) & (px[:, :, 1] < 60) & (px[:, :, 2] > 200)
            shown = rv * n
            for i, v in enumerate(vals):
                a = max(0.0, min(1.0, shown - i))
                if a <= 0.6:
                    continue
                frac = 0.12 + 0.88 * ((v - lo) / (hi - lo))
                h = (bot - top) * frac * a
                if h < vs.STAIR_VALUE_ROOM:
                    continue
                sy = int(bot - h)
                sx = int(bx0 + 80 + i * w)
                cell = magenta[sy + 16:sy + 56, sx + 6:int(sx + w - 6)]
                self.assertEqual(cell.sum(), 0,
                                 f"host over the value of step {i} at reveal {rv}")

    def test_the_value_sits_inside_its_step(self):
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        i = src.index("def draw_staircase(")
        body = src[i:src.index("def draw_elevator(")]
        self.assertIn("sy + 36", body, "the value is drawn under the step's top edge")
        self.assertNotIn("sy - 30", body, "the value is no longer drawn above the step")


class TheBalanceFitsItsWords(unittest.TestCase):
    def test_long_labels_and_big_numbers_stay_inside_the_frame(self):
        box = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        vs.draw_balance(ImageDraw.Draw(img), img, box, 4096930.0, 2609874.0,
                        "Prevention & management", "Damage & losses",
                        charts.HIGHLIGHT, 0.95, unit="count")
        a = _alpha(img)
        self.assertEqual(a[:, :6].sum(), 0, "ink in the left 6px")
        self.assertEqual(a[:, -6:].sum(), 0, "ink in the right 6px")

    def test_a_long_label_wraps_before_it_shrinks_to_nothing(self):
        img = Image.new("RGBA", (1080, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        box = (40, 0, 1040, 400)
        lines = vs.fit_centred_lines(d, "Prevention & management", 44, 190,
                                     box, min_size=30)
        self.assertEqual(len(lines), 2)
        self.assertEqual([t for _, t in lines], ["Prevention &", "management"])
        for f, t in lines:
            self.assertGreaterEqual(f.size, 30)
            self.assertLessEqual(d.textlength(t, font=f), 2 * (190 - 40))
        short = vs.fit_centred_lines(d, "Damage", 44, 190, box, min_size=30)
        self.assertEqual(len(short), 1)

    def test_no_label_is_truncated_by_character_count_any_more(self):
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        i = src.index("def draw_balance(")
        body = src[i:src.index("def one_in_n(")]
        self.assertNotIn("[:18]", body)


class TheStackLabelsStayInside(unittest.TestCase):
    def test_long_segment_names_wrap_instead_of_running_off(self):
        import tempfile
        ins = _insight([("Properly recycled", 22.0),
                        ("Not properly recycled", 60.0),
                        ("Soy, Mining, Logging & Other", 18.0)],
                       kind="stack", unit="percent", topic="e-waste")
        ins.highlight_label = "Not properly recycled"
        with tempfile.TemporaryDirectory() as td:
            p = charts.render_chart(ins, Path(td) / "stack.png")
            self.assertIsNotNone(p)
            img = Image.open(p).convert("RGBA")
        a = _alpha(img)
        self.assertEqual(a[:, -8:].sum(), 0, "ink in the right 8px of the card")

    def test_the_fitter_wraps_at_the_middle_space(self):
        src = (_REPO / "data_learning" / "charts.py").read_text()
        i = src.index("def _story_stack(")
        body = src[i:src.index("def _story_bubbles(")]
        self.assertIn("def _fit_seg_label", body)
        self.assertIn("_lab_x", body)
        self.assertNotIn("cx1 + 0.045, _gy", body)


class TheHostFitsHisRow(unittest.TestCase):
    def test_the_zoom_arithmetic_matches_the_clamp(self):
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(10.0, 15.6), dpi=110)
        try:
            z = charts._zoom_for_height(fig, 500, 0.18)
            self.assertAlmostEqual(500 * z / (72.0 * 15.6), 0.18, places=6)
        finally:
            plt.close(fig)

    def test_both_row_charts_hand_in_their_pitch(self):
        tree = ast.parse((_REPO / "data_learning" / "charts.py").read_text())
        found = {}
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name in (
                    "_story_pictorial_race", "_story_bars"):
                for c in ast.walk(fn):
                    if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                            and c.func.id == "_bake_host"):
                        found[fn.name] = {k.arg for k in c.keywords}
        for name in ("_story_pictorial_race", "_story_bars"):
            self.assertIn("max_h_frac", found.get(name, set()), name)


class TheRecapIsReadable(unittest.TestCase):
    """At a uniform 0.62 the recap's row names were "~8px grey". The recap
    is now the visual's CONTENT BAND — heading and footer cropped off —
    scaled to the room under the bubble, so a card keeps its type at full
    size and a full-frame scene keeps most of it."""

    def test_a_card_keeps_its_type_at_full_size(self):
        from data_learning import studio_render as sr
        g = sr.recap_geometry(sr.CHART_W, sr.CHART_H)
        self.assertGreaterEqual(g["scale"], 0.95)
        self.assertGreaterEqual(g["ry"], 470)
        self.assertLessEqual(g["ry"] + g["rh"], 1683)
        self.assertEqual(g["rw"] % 2 + g["rh"] % 2, 0, "even, for yuv420p")

    def test_a_full_frame_scene_keeps_most_of_it(self):
        from data_learning import studio_render as sr
        g = sr.recap_geometry(sr.W, sr.H)
        self.assertGreaterEqual(g["scale"], 0.80)   # was 0.62 uniform
        self.assertGreaterEqual(g["ry"], 470)
        self.assertLessEqual(g["ry"] + g["rh"], 1683)
        self.assertLessEqual(g["rw"], sr.W - 24)

    def test_the_heading_is_what_gets_trimmed_and_the_trim_is_centred(self):
        """A centred trim, the same band off both ends — not a punch-in:
        the operator's ruling against camera moves stands, and
        `test_edit_pacing` holds that no crop here carries an offset."""
        from data_learning import studio_render as sr
        g = sr.recap_geometry(sr.CHART_W, sr.CHART_H)
        # the card's heading band ends at SUB_Y (0.845 from the bottom)
        self.assertGreaterEqual(g["crop_top"], int(sr.CHART_H * (1 - 0.845)) - 20)
        self.assertEqual(g["crop_h"] + 2 * g["crop_top"], sr.CHART_H - (sr.CHART_H % 2))
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        blk = src[src.index("_rg = recap_geometry(vw, vh)"):]
        blk = blk[:blk.index("n_visuals += 1")]
        self.assertIn("crop={vw}:{_ch},", blk)


class TheSecondLayerFromTheFirstRunOnTheFixes(unittest.TestCase):
    """The 13:43 run on the first fixes was judged at 14:07-15:06 and blocked
    every video for the SAME class in OTHER visuals: the hook caption on the
    leading chart's top rows, bubble labels off the edge and over each
    other, scene hosts over the title and the sub-caption, a dot-field label
    off the left edge. Each is held here."""

    def test_the_hook_take_sits_on_the_lower_plate_not_the_chart(self):
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        i = src.index("hchunks = _chunks(st.hook, 2)")
        blk = src[i:i + 2500]
        self.assertNotIn("pos(540,470)", blk, "the hook take is back on the chart's top rows")
        self.assertEqual(blk.count("\\pos(540,1734)"), 2)

    def test_bubble_labels_fit_their_slot_and_stay_on_the_card(self):
        import tempfile
        ins = _insight([("Classified as harmful invasive", 3500.0),
                        ("Live in 8F+ heat-island exposure", 2100.0),
                        ("Established", 900.0), ("Prevention & management", 400.0),
                        ("Damage", 120.0)], kind="bubbles", topic="invasive species")
        with tempfile.TemporaryDirectory() as td:
            pth = charts.render_chart(ins, Path(td) / "b.png")
            self.assertIsNotNone(pth)
            a = _alpha(Image.open(pth).convert("RGBA"))
        self.assertEqual(a[:, :8].sum() + a[:, -8:].sum(), 0, "a bubble label reached the edge")
        t, fs = charts.fit_label_lines("Live in 8F+ heat-island exposure", 120.0, 22)
        self.assertIn("\n", t)
        self.assertGreaterEqual(fs, 13)

    def _host_rows(self, draw, box, *args, **kw):
        sprite = Image.new("RGBA", (200, 300), (255, 0, 255, 255))
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        with mock.patch.object(vs, "scene_host", return_value=sprite):
            draw(ImageDraw.Draw(img), img, box, *args, **kw)
        px = np.asarray(img)
        m = (px[:, :, 0] > 200) & (px[:, :, 1] < 60) & (px[:, :, 2] > 200)
        rows = np.where(m.any(axis=1))[0]
        return (int(rows.min()), int(rows.max())) if len(rows) else None

    def test_the_unit_grid_and_dot_field_hosts_start_under_the_value_line(self):
        box = (vs.RX0, vs.title_clearance(TOPIC), vs.RX1, vs.MACHINE_BOT)
        for rv in (0.15, 0.5, 1.0):
            r = self._host_rows(vs.draw_unit_figures, box, None, 14.0, 1.0,
                                "teen vaping", charts.HIGHLIGHT, rv, unit="percent")
            if r:
                self.assertGreaterEqual(r[0], box[1] + 96, f"unit grid host at reveal {rv}")
            r = self._host_rows(vs.draw_dot_field, box, None, 68.0, "Formerly redlined",
                                charts.HIGHLIGHT, rv, unit="percent")
            if r:
                self.assertGreaterEqual(r[0], box[1] + 110, f"dot field host at reveal {rv}")

    def test_the_spotlight_host_starts_under_its_sub_caption(self):
        box = (vs.RX0, vs.title_clearance(TOPIC), vs.RX1, vs.MACHINE_BOT)
        safe = vs.drawable_insight(_insight([("2019", 1.1), ("2020", 2.4), ("2021", 4.4),
                                             ("2022", 3.1), ("2023", 2.2)]))
        bx0, by0, bx1, by1 = box
        cy = by1 - 430
        lane = int(min(88, (by1 - by0) * 0.075))
        cap_bot = cy + lane + 124 + 22
        r = self._host_rows(vs.draw_spotlight, box, safe, charts.HIGHLIGHT, 0.9, "dollars")
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r[0], cap_bot)

    def test_the_dot_field_label_is_fitted(self):
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        i = src.index("def draw_dot_field(")
        body = src[i:i + 6000]
        self.assertIn("fit_centred(d, f\"{label}   {charts._ulabel(value, unit)}\"", body)


if __name__ == "__main__":
    unittest.main()
