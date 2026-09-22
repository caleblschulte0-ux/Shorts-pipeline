"""WHAT THE JUDGE NAMED ON THE FIRST RUN OF THE LAYOUT FIXES.

Explainer run 457 (2026-09-22, the first on #419) rendered fourteen videos
and the showrunner blocked all fourteen at 26-43. Four of its complaints
were things drawn wrong in one place each, and are held here by measuring
what is drawn:

  * junk_imagery (FATAL): "the unit icons for teen vaping are yellow
    office/hospital buildings with a clock on top" (a SCHOOL, from "high
    schoolers who vape"), "graduation caps whose tassels read like vape
    pens" (from "high school students currently using e-cigarettes"), "an
    alarm-clock emoji fills a whole 'each = 5%' grid" (from "few
    times/month"). The population a behaviour is measured in, and a
    frequency, were choosing the picture.
  * junk_imagery again: "seg3:end/seg4 wrap the bars in film-strip frames".
    The skyline's windows were two columns of squares hugging each wall.
  * "seg2's two labels are composited on top of each other into
    unreadable mush" - the tape printed both post labels on one line.
  * "the header 'ave used one at least once 72' is clipped on both edges".
  * "the non-subject values are low-contrast grey that almost disappears"
    (five stories) - supporting values printed in `look.REST`, 2.05:1.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
from PIL import Image, ImageDraw                          # noqa: E402

from data_learning import charts, icons, viz_scene as vs  # noqa: E402
from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402
from shared import look                                   # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-22")


def _insight(pairs, unit="percent", topic="teens and their AI chatbot"):
    return Insight(kind="scene", topic=topic, main_insight="m",
                   items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                   source=SRC, unit=unit, highlight_label=pairs[0][0])


class _Record(vs.InkDraw):
    """InkDraw that remembers every string it drew and where."""

    def __init__(self, img):
        super().__init__(ImageDraw.Draw(img))
        self.texts = []

    def text(self, xy, text, fill=None, *a, **k):
        self.texts.append((str(text), self._draw.textbbox(
            xy, str(text), font=k.get("font"), anchor=k.get("anchor")),
            vs._lift_rest(fill)))
        return super().text(xy, text, fill, *a, **k)


class TheCountedThingChoosesThePicture(unittest.TestCase):
    def test_the_three_labels_the_judge_saw(self):
        for label in ("percent of high schoolers who vape",
                      "High school students currently using e-cigarettes (percent)",
                      "High school e-cigarette use: 2019 peak vs. 2024",
                      "Current tobacco/nicotine product use among high school "
                      "students, by product (2024)",
                      "Use one regularly (few times/month+)"):
            self.assertIsNone(icons.emoji_codepoint(label), label)

    def test_the_good_picks_are_untouched(self):
        keep = {"F1 pit stop time": "23f0",            # a duration IS a clock
                "time spent": "23f0",
                "School enrollment, primary (gross), gender parity index": "1f3eb",
                "Banana varieties that exist vs. varieties actually exported": "1f34c",
                "People forcibly displaced worldwide (millions)": "1f465",
                "Average monthly student loan payment": "1f393"}
        for label, cp in keep.items():
            self.assertEqual(icons.emoji_codepoint(label), cp, label)

    def test_the_behaviour_decides_when_it_has_a_picture(self):
        self.assertEqual(icons.emoji_codepoint("Share of kids who own a smartphone"),
                         icons.emoji_codepoint("smartphone"))


class ASkylineIsBuildingsNotFilm(unittest.TestCase):
    def test_windows_are_a_grid_across_the_face(self):
        for face in (100, 140, 200, 300, 420):
            cols, rows, (x, _y), (ww, _h), (gx, _gy) = vs.skyline_windows(
                100, 100 + face, 400, 1400)
            self.assertGreaterEqual(cols, 3, face)
            self.assertGreaterEqual(x - 100, 12, "no column on the left wall")
            right = x + (cols - 1) * gx + ww
            self.assertGreaterEqual(100 + face - right, 11,
                                    "no column on the right wall")
            self.assertGreater(rows, 0)

    def test_a_face_too_narrow_for_a_grid_gets_no_windows(self):
        self.assertEqual(vs.skyline_windows(0, 60, 0, 900)[0], 0)

    def test_the_lead_value_is_not_printed_over_a_window(self):
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        d = _Record(img)
        ins = vs.drawable_insight(_insight(
            [("E-cigarettes", 7.8), ("Nicotine pouches", 1.8), ("Cigarettes", 1.7)]))
        box = (vs.RX0, vs.title_clearance(ins.topic), vs.RX1, vs.MACHINE_BOT)
        vs.draw_skyline(d, img, box, ins, charts.HIGHLIGHT, 1.0, "percent")
        val = next(b for t, b, _ in d.texts if t.startswith("7.8"))
        px = img.getpixel(((val[0] + val[2]) // 2, val[3] + 6))
        card = tuple(int(charts.CARD.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) \
            if isinstance(charts.CARD, str) else tuple(charts.CARD)[:3]
        self.assertNotEqual(px[:3], card[:3], "a window under the lead value")


class TheTapeLabelsNeverMeet(unittest.TestCase):
    def test_two_close_posts_with_long_labels(self):
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        d = _Record(img)
        ins = vs.drawable_insight(_insight(
            [("AI over a human", 31.0),
             ("Shared personal info with an AI companion", 23.0)]))
        box = (vs.RX0, vs.title_clearance(ins.topic), vs.RX1, vs.MACHINE_BOT)
        vs.draw_tape(d, img, box, ins, charts.HIGHLIGHT, 1.0, "percent")
        labs = [b for t, b, _ in d.texts if "AI" in t]
        self.assertEqual(len(labs), 2)
        a, b = labs
        overlap = not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
        self.assertFalse(overlap, f"labels overlap: {a} {b}")
        for bb in labs:
            self.assertGreaterEqual(bb[0], 0)
            self.assertLessEqual(bb[2], 1080)


class TheUnitHeaderFitsTheFrame(unittest.TestCase):
    def test_a_long_label_and_its_total_stay_on_screen(self):
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        d = _Record(img)
        box = (vs.RX0, 420, vs.RX1, vs.MACHINE_BOT)
        vs.draw_unit_figures(d, img, box, None, 72.0, 5.0,
                             "have used one at least once", charts.HIGHLIGHT,
                             1.0, unit="percent")
        head = [b for t, b, _ in d.texts if "at least once" in t]
        self.assertTrue(head)
        self.assertGreaterEqual(head[0][0], 0)
        self.assertLessEqual(head[0][2], 1080)
        self.assertTrue(any("72" in t for t, _, _ in d.texts if "once" in t),
                        "the total the grid counts is still printed")


class TypeIsNeverDrawnInTheRestNeutral(unittest.TestCase):
    def test_rest_text_is_lifted_to_the_secondary_ink(self):
        self.assertEqual(vs._lift_rest((*look.REST, 200)), (*look.INK_2, 200))
        self.assertEqual(vs._lift_rest((*look.INK, 255)), (*look.INK, 255))
        self.assertEqual(vs._lift_rest(None), None)

    def test_no_machine_prints_a_value_in_rest(self):
        pairs = [("Prevention", 9.9), ("Damage", 88.7), ("Other", 1.4)]
        rest = tuple(look.REST)
        for kind in sorted(vs._MACHINE_DRAW):
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = _Record(img)
            ins = vs.drawable_insight(_insight(pairs))
            if ins is None:
                continue
            box = (vs.RX0, vs.title_clearance(ins.topic), vs.RX1, vs.MACHINE_BOT)
            vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, box, ins,
                        charts.HIGHLIGHT, 1.0, "percent")
            for t, _bb, fill in d.texts:
                if isinstance(fill, tuple):
                    self.assertNotEqual(tuple(fill[:3]), rest, f"{kind}: {t!r}")

    def test_render_scene_draws_through_it(self):
        src = (ROOT / "data_learning" / "viz_scene.py").read_text()
        body = src[src.index("def render_scene("):]
        self.assertIn("d = InkDraw(ImageDraw.Draw(canvas))", body[:20000])


if __name__ == "__main__":
    unittest.main()
