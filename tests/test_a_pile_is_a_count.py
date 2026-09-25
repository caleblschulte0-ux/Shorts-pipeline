"""A pile of pieces is read as a count, so it must BE the count.

Waymo, 2026-09-25, four renders running: "4 city icons in the '3 cities'
bar and 8 in the '5 cities' bar, so the picture contradicts the data". The
staircase filled each step with subject icons up to its height; the balance
always loaded six blocks on the bigger pan. `viz_scene.piece_counts` is the
one rule both use now.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from data_learning import charts                   # noqa: E402
from data_learning import viz_scene as vs          # noqa: E402
from tests._machine_samples import mk              # noqa: E402


class PieceCounts(unittest.TestCase):
    def test_small_whole_counts_are_exact(self):
        self.assertEqual(vs.piece_counts([1, 3, 5], "cities"), [1, 3, 5])
        self.assertEqual(vs.piece_counts([0, 3], ""), [0, 3])

    def test_everything_else_is_a_bounded_proportion(self):
        self.assertEqual(vs.piece_counts([10000, 200000], "rides"), [1, 6])
        # whole numbers in a measure are not a count of anything
        self.assertEqual(vs.piece_counts([5, 12], "percent"), [2, 6])
        self.assertFalse(vs.is_count([2.0, 4.41], "usd"))
        self.assertFalse(vs.is_count([3, 40], "count"))


class TheStaircaseStacksExactlyTheCount(unittest.TestCase):
    def _icons_per_step(self, pairs, unit):
        glyph = Image.new("RGBA", (128, 128), (250, 0, 250, 255))
        ins = mk(pairs, unit, topic="robotaxi cities")
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        stamps = []
        real = img.alpha_composite

        def spy(im, dest=(0, 0), *a, **k):
            if im.size[0] == im.size[1] and im.size[0] <= 78 and \
                    im.getpixel((im.size[0] // 2, im.size[1] // 2))[:3] == (250, 0, 250):
                stamps.append(dest)
            return real(im, dest, *a, **k)

        img.alpha_composite = spy
        with mock.patch.object(vs, "_subject_glyph", lambda *a, **k: glyph), \
                mock.patch.object(vs, "scene_host", lambda *a, **k: None):
            vs._guarded("staircase", vs._MACHINE_DRAW["staircase"],
                        ImageDraw.Draw(img), img,
                        (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT),
                        vs.drawable_insight(ins), charts.HIGHLIGHT, 1.0, unit)
        cols: dict[int, int] = {}
        for x, _y in stamps:
            cols[x] = cols.get(x, 0) + 1
        return [cols[x] for x in sorted(cols)]

    def test_one_three_five_cities_draw_one_three_five(self):
        got = self._icons_per_step(
            [("Oct 2023", 1), ("Aug 2024", 3), ("Feb 2025", 5)], "cities")
        self.assertEqual(got, [1, 3, 5])

    def test_a_price_is_not_counted_out_in_cups(self):
        got = self._icons_per_step(
            [("2019", 2.1), ("2021", 3.4), ("2023", 4.8), ("2025", 6.2)], "usd")
        self.assertTrue(all(n <= 1 for n in got), got)


if __name__ == "__main__":
    unittest.main()


class ABeatDoesNotRepeatAnotherBeatsFigure(unittest.TestCase):
    """"seg3 repeats seg0's scale machine, so two of five beats look the
    same" (Waymo, 2026-09-25). A figure another beat showed ranks below any
    chart no beat has shown."""

    def test_every_pick_is_new_while_anything_new_is_left(self):
        from data_learning import studio_render as sr
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "rides",
                 topic="how many robotaxi rides waymo gives every week")
        ins.kind = "bars"
        used = {m for m in sr._machines_for(ins) if sr._family(m) == "figure"}
        used.add("balance_scene")
        charts_seen = 0
        for _ in range(12):
            seq = sr._depiction_sequence(ins, set(used), 13.0)
            if len(seq) < 2 or seq[1] in used:
                break                       # nothing new left: a repeat is fair
            charts_seen += sr._family(seq[1]) == "chart"
            used.add(seq[1])
        # the unshown charts came BEFORE any repeat of a shown figure
        self.assertGreaterEqual(charts_seen, 2)


class TheTowerTellsTheTruthWhileItBuilds(unittest.TestCase):
    """Waymo, local render 2026-09-25 (score 44): "the header shows 200,000
    from frame 1 but only 1 of 10 blocks (20K) is lit", "'each block = 0.4'
    is a nonsensical unit for cities", "the stack never fills and holds
    unchanged from 1.7s to 10.6s"."""

    def _texts(self, ins, reveal):
        drawn = []
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        d = ImageDraw.Draw(img)
        real = d.text

        def spy(xy, text, *a, **k):
            drawn.append(str(text))
            return real(xy, text, *a, **k)

        d.text = spy
        with mock.patch.object(vs, "scene_host", lambda *a, **k: None):
            vs._MACHINE_DRAW["tower"](d, img, (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT),
                                      vs.drawable_insight(ins),
                                      charts.HIGHLIGHT, reveal, ins.unit)
        return drawn

    def test_cities_are_counted_in_ones(self):
        ins = mk([("Oct 2023", 1), ("Aug 2024", 3), ("Feb 2025", 5)], "cities")
        texts = " | ".join(self._texts(ins, 1.0))
        self.assertIn("each block  =  1", texts)
        self.assertNotIn("0.4", texts)

    def test_the_answer_arrives_it_is_not_printed_on_frame_one(self):
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count")
        early = " | ".join(self._texts(ins, 0.3))
        done = " | ".join(self._texts(ins, 1.0))
        self.assertIn("Feb 2025   200,000", done)
        self.assertNotIn("Feb 2025   200,000", early)
        self.assertIn("10,000", early)          # the then is named throughout

    def test_a_then_smaller_than_a_block_keeps_the_framing(self):
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count")
        texts = " | ".join(self._texts(ins, 1.0))
        self.assertIn("→", texts)


class TheRecapKeepsTheClaim(unittest.TestCase):
    """"the scale beam goes level even though it is 200,000 against 0": the
    closing recap replayed the scales from empty under the takeaway."""

    def test_a_figure_replays_from_halfway_a_chart_from_zero(self):
        from data_learning import studio_render as sr
        self.assertGreater(sr.recap_replay_from("balance_scene", 1.0, 10.0), 0)
        self.assertEqual(sr.recap_replay_from("bars", 1.0, 10.0), 0.0)
        self.assertEqual(sr.recap_replay_from("subject_scene", 1.0, 10.0), 0.0)

    def test_the_master_trims_the_recap_to_it(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("recap_replay_from(sp.get(\"kind\")", src)
        self.assertIn("trim=start=", src)
