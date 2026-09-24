"""THE A STYLE IS READABLE — every machine and every card chart, measured.

The showrunner blocked the current look (A) for `unreadable` on 71 of 72
renders on 2026-09-22, in words like "'11.7%' split by the mascot's legs",
"straddles the 2013 and 2006 rows, hiding the row bar and its label", "the
headline reads 'the vaping crackdow'". Every one of those was a label under
Data. `data_learning/a_audit.py` renders every A machine and every card
chart kind through the real renderer and records every label a viewer is
meant to read and every place Data is drawn over it; this holds the count at
zero, so a new machine or chart that parks him on a label fails here, not in
front of the judge.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class EveryAMachineIsReadable(unittest.TestCase):
    def test_no_machine_hides_clips_or_greys_out_a_label(self):
        """On its stock data AND on the three shapes production sends that a
        stock dataset hides: values close together, figures in the millions,
        and names longer than "Tokyo". The stock pass alone found three
        defects; the stress shapes found six more (a_audit.STRESS)."""
        from data_learning import a_audit as A
        self.assertEqual(set(A.STRESS), {"close", "huge", "long"})
        self.assertEqual(A.audit(frames=12), {})


class EveryCardChartIsReadable(unittest.TestCase):
    def test_no_chart_puts_data_on_a_label_or_off_the_card(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:  # noqa: BLE001
            self.skipTest("matplotlib not installed")
        from data_learning import a_audit as A
        self.assertEqual(A.audit_charts(frames=6), {})

    def test_the_clearing_step_runs_on_every_card_frame(self):
        import inspect
        from data_learning import charts
        src = inspect.getsource(charts.render_story_build)
        self.assertLess(src.index("_clear_host(fig)"),
                        src.index('fig.savefig(out_dir / f"{slug}_build'))


class TheColdOpenStartsWithAPicture(unittest.TestCase):
    """ "The hook opens on an almost empty gradient with a slow bar build"
    (container ships, 2026-09-24). A machine carrying the hook now opens a
    third built and bursts, like the card charts always did."""

    def test_a_machine_hook_is_not_an_empty_frame(self):
        import tempfile
        from PIL import Image
        from data_learning import a_audit as A, charts
        for nm in ("skyline", "staircase", "tower"):
            with self.subTest(machine=nm):
                _, build, ins = [c for c in A.cases() if c[0] == nm][0]
                ins.kind = "scene"
                ins.scene = build(ins)
                with tempfile.TemporaryDirectory() as td:
                    charts.render_story_build(ins, Path(td), "h", frames=40,
                                              hook_lead=True)
                    fs = sorted(Path(td).glob("h*.png"))
                    self.assertLessEqual(
                        A.empty_share(Image.open(fs[1]).convert("RGB")), 0.4)


class TheAuditSeesWhatItClaims(unittest.TestCase):
    """The auditor itself is checked, or a clean report means nothing."""

    def test_a_label_under_data_is_caught(self):
        from data_learning import a_audit as A
        ev = [(0, "text", ("11.7%", (100, 100, 180, 140), 1.0, (242, 245, 250))),
              (0, "data", (90, 60, 260, 320))]
        self.assertEqual(A._judge(ev, {})["covered"], ["11.7%"])

    def test_a_label_drawn_over_data_is_not(self):
        from data_learning import a_audit as A
        ev = [(0, "data", (90, 60, 260, 320)),
              (0, "text", ("11.7%", (100, 100, 180, 140), 1.0, (242, 245, 250)))]
        self.assertEqual(A._judge(ev, {})["covered"], [])

    def test_white_on_gold_is_faint_and_ink_on_gold_is_not(self):
        from PIL import Image
        from data_learning import a_audit as A
        from shared import look
        im = Image.new("RGB", (A.W, A.H), (255, 211, 122))
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        d.text((100, 100), "342", fill=look.INK, font_size=60)
        bb = d.textbbox((100, 100), "342", font_size=60)
        self.assertLess(A._glyph_contrast(im, bb, look.INK), A.MIN_CONTRAST)
        self.assertEqual(look.ink_on((255, 211, 122)), look.INK_ON_LIGHT)
        self.assertEqual(look.ink_on("#0d1030"), look.INK)


    def test_two_different_labels_on_one_canvas_collide(self):
        from data_learning import a_audit as A
        ev = [(0, "text", ("clears it by 1.7", (100, 100, 400, 140), 1.0, (1, 1, 1), 7)),
              (0, "text", ("65-city average 8", (120, 110, 420, 150), 1.0, (1, 1, 1), 7)),
              # the renderer's probe canvas is never seen with the frame
              (0, "text", ("probe 9", (100, 100, 400, 140), 1.0, (1, 1, 1), 99))]
        self.assertEqual(A._judge(ev, {})["collide"],
                         ["65-city average 8 / clears it by 1.7"])

    def test_data_on_another_canvas_covers_nothing(self):
        from data_learning import a_audit as A
        ev = [(0, "text", ("11.7%", (100, 100, 180, 140), 1.0, (9, 9, 9), 1)),
              (0, "data", (90, 60, 260, 320, 2))]
        self.assertEqual(A._judge(ev, {})["covered"], [])

    def test_an_ellipsis_is_reported(self):
        from data_learning import a_audit as A
        ev = [(0, "text", ("Formerly redli…", (0, 0, 90, 30), 1.0, (9, 9, 9), 1))]
        self.assertEqual(A._judge(ev, {})["truncated"], ["Formerly redli…"])


class ALabelIsNeverCut(unittest.TestCase):
    """fit_text: shrink to a readable floor, then WRAP, and a number is
    written short (19.4M), never ellipsised ("19378…")."""

    def _d(self):
        from PIL import Image, ImageDraw
        return ImageDraw.Draw(Image.new("RGB", (1080, 1920)))

    def test_a_long_name_wraps_at_a_readable_size(self):
        from data_learning import viz_scene as vs
        f, t = vs.fit_text(self._d(), "Riverside-San Bernardino", 30, 150, min_size=16)
        self.assertNotIn("…", t)
        self.assertIn("\n", t)
        self.assertGreaterEqual(f.size, 20)

    def test_a_number_is_compacted_not_cut(self):
        from data_learning import viz_scene as vs
        f, t = vs.fit_text(self._d(), "19378262", 34, 70, min_size=20)
        self.assertEqual(t, "19.4M")
        self.assertEqual(vs.compact_numbers("$1,460,000 in 2016"), "$1.46M in 2016")

    def test_a_short_label_is_untouched(self):
        from data_learning import viz_scene as vs
        f, t = vs.fit_text(self._d(), "Tokyo", 30, 400)
        self.assertEqual((t, f.size), ("Tokyo", 30))


class TheNumberOnScreenIsTheData(unittest.TestCase):
    """A readout prints a value the data HAS. Counting up (balance, gauge,
    thermometer, leaky) or interpolating between years (queue, burden)
    printed "2020  316" when 316 is no year's value; the picture moves, the
    number is the source's."""

    def test_no_machine_prints_a_number_the_data_does_not_have(self):
        import re
        import tempfile
        from pathlib import Path
        from PIL import ImageDraw
        from data_learning import a_audit as A, charts
        seen = []
        real = ImageDraw.ImageDraw.text

        def rec(self, xy, text, *a, **k):
            seen.append(str(text))
            return real(self, xy, text, *a, **k)
        C = {n: (b, i) for n, b, i in A.cases()}
        bad = {}
        for name in ("queue", "burden", "balance", "gauge", "thermometer", "leaky"):
            b, ins = C[name]
            if b is None:
                continue
            allowed = {charts._ulabel(p.value, ins.unit, group=g)
                       for p in ins.items for g in (True, False)}
            ins.scene = b(ins)
            seen.clear()
            ImageDraw.ImageDraw.text = rec
            try:
                with tempfile.TemporaryDirectory() as td:
                    charts.FULLFRAME_RENDERERS["scene"](ins, Path(td), "n", 12)
            finally:
                ImageDraw.ImageDraw.text = real
            labels = {str(p.label) for p in ins.items}
            for s in seen:
                for lab in labels:
                    m = re.match(re.escape(lab) + r"\s{2,}(\S+)", s)
                    if m and m.group(1) not in allowed:
                        bad.setdefault(name, set()).add(s)
        self.assertEqual(bad, {})


class ASeriesKeepsItsEnd(unittest.TestCase):
    """Five of seven years drawn must include the LAST: the coffee story's
    record ($4.41, 2025) was sliced off by `[:5]` and the hook drew a dip
    under the word "climbed"."""

    def _ins(self, kind, pairs):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-24")
        return Insight(kind=kind, topic="t", main_insight="m",
                       items=[DataPoint(label=a, value=b) for a, b in pairs],
                       source=src, unit="dollars", highlight_label=pairs[-1][0])

    def test_a_trend_keeps_its_first_and_last_year(self):
        from data_learning import charts
        coffee = [("2019", 1.05), ("2020", 1.2), ("2021", 2.55), ("2022", 2.4),
                  ("2023", 1.95), ("2024", 3.3), ("2025", 4.41)]
        for kind in ("trend", "comparison"):
            got = [p.label for p in charts.capped_items(self._ins(kind, coffee), 5)]
            self.assertEqual(len(got), 5)
            self.assertEqual((got[0], got[-1]), ("2019", "2025"), kind)

    def test_a_ranking_keeps_its_top(self):
        from data_learning import charts
        ranked = [("Tokyo", 37), ("Delhi", 32), ("Shanghai", 29), ("Dhaka", 23),
                  ("Cairo", 22), ("Lima", 11), ("Oslo", 1)]
        got = [p.label for p in charts.capped_items(self._ins("rank", ranked), 5)]
        self.assertEqual(got, ["Tokyo", "Delhi", "Shanghai", "Dhaka", "Cairo"])

    def test_no_renderer_slices_the_first_five_any_more(self):
        import re
        for f in ("data_learning/charts.py", "data_learning/viz_scene.py"):
            src = (ROOT / f).read_text()
            self.assertEqual(re.findall(r"_ordered_items\(insight\)\[:5\]", src), [], f)


if __name__ == "__main__":
    unittest.main()
