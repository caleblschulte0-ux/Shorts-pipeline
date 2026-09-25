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
        # while it counts, the header is the running count alone
        self.assertRegex(early, r"(^| )\d{2,3},000( |$)")
        self.assertNotIn("200,000", early)

    def test_on_the_cold_open_it_still_builds_across_the_whole_beat(self):
        """hook_reveal bursts to 3/4 by 22% of the span; an 11s opening
        stack finished at 3.7s and held (Waymo re-render, 52)."""
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count")
        mid = charts.hook_reveal(0.5)
        self.assertGreater(mid, 0.8)                 # the burst is real
        try:
            vs._HOOK_LEAD, vs._BEAT_PHASE = True, 0.5
            half = " | ".join(self._texts(ins, mid))
        finally:
            vs._HOOK_LEAD, vs._BEAT_PHASE = False, None
        self.assertNotIn("Feb 2025   200,000", half)

    def test_the_now_is_not_named_below_the_then(self):
        ins = mk([("2020", 1), ("2023", 3), ("2025", 5)], "cities")
        early = " | ".join(self._texts(ins, 0.05))
        self.assertNotIn("2025   1", early)

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


class ASecondPictureIsANewShape(unittest.TestCase):
    """"a plain three-bar chart; it repeats what the hook stack already
    showed" (Waymo), "the same largest-ship data twice, first as vertical
    bars and then as horizontal bars" (container ships)."""

    def _ins(self, kind):
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count",
                 topic="how many robotaxi rides waymo gives every week")
        ins.kind = kind
        if kind == "scene":
            ins.scene = {"title": True,
                         "elements": [{"type": "tower", "region": "full"}]}
        return ins

    def test_after_a_stack_the_beat_does_not_draw_heights_again(self):
        from data_learning import studio_render as sr
        for kind in ("scene", "bars"):
            ins = self._ins(kind)
            seq = sr._depiction_sequence(ins, set(), 11.1)
            self.assertTrue(sr._is_heights(seq[0], ins), seq)
            for k in seq[1:]:
                self.assertFalse(sr._is_heights(k), (kind, seq))

    def test_a_scene_is_heights_only_when_it_draws_heights(self):
        from data_learning import studio_render as sr
        ins = self._ins("scene")
        self.assertTrue(sr._is_heights("scene", ins))
        ins.scene = {"elements": [{"type": "balance"}]}
        self.assertFalse(sr._is_heights("scene", ins))


class ADateOnlyMeetsItsOwnValue(unittest.TestCase):
    """Waymo re-render (66): "the header reads 'Oct 2023 10,000 → Feb 2025
    100,000/120,000/140,000' while the counter ticks", and on the timeline
    "the 'Feb 2025' label sits at the 100K point, which was August 2024"."""

    def test_a_running_count_carries_no_date(self):
        t = TheTowerTellsTheTruthWhileItBuilds()
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count")
        mid = " | ".join(t._texts(ins, 0.6))
        # while it counts, the header is only the count — "Oct 2023 10,000
        # -> 120,000" still read as a mismatched date and value
        self.assertNotIn("Feb 2025", mid)
        self.assertNotIn("Oct 2023", mid)
        done = " | ".join(t._texts(ins, 1.0))
        self.assertIn("Oct 2023", done)
        self.assertIn("Feb 2025", done)

    def test_months_and_quarters_are_times(self):
        from data_learning import charts as C
        from data_learning.sources.base import DataPoint as D
        self.assertAlmostEqual(
            C._period_year(D(label="Oct 2023", value=1.0, period="2023-10")),
            2023.75)
        self.assertAlmostEqual(
            C._period_year(D(label="Aug 2024", value=1.0)), 2024 + 7 / 12)
        self.assertAlmostEqual(
            C._period_year(D(label="Q3 2024", value=1.0)), 2024.5)
        self.assertIsNone(
            C._period_year(D(label="September Estimate", value=1.0)))

    def test_the_timeline_draws_waymo_on_its_dates(self):
        """Dated data gets the dated timeline (stems at their months), not a
        0..224K number line with the last date riding the dot."""
        import tempfile
        from data_learning import charts as C
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count", topic="waymo rides a week")
        for p, per in zip(ins.items, ("2023-10", "2024-08", "2025-02")):
            p.period = per
        drawn = []
        real = ImageDraw.ImageDraw.text

        def spy(self_, xy, text, *a, **k):
            drawn.append(str(text))
            return real(self_, xy, text, *a, **k)

        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(ImageDraw.ImageDraw, "text", spy), \
                mock.patch.object(C, "_host_pose", lambda *a, **k: None):
            C._render_timeline(ins, Path(td), "t", frames=4)
        self.assertIn("Oct 2023", drawn)
        self.assertIn("Aug 2024", drawn)


class TheRaceKeepsEveryoneReadableAndInFrame(unittest.TestCase):
    """"the grey mascot cuts off the Cruise label ('...shutdow'), and both
    side labels are tiny and low-contrast" (Waymo re-render, 66)."""

    NAMES = ("Waymo, weekly rides (early 2025)",
             "Cruise, weekly rides (after Dec 2024 shutdown)")

    def _draw(self, reveal=1.0):
        runner = Image.new("RGBA", (100, 200), (40, 200, 180, 255))
        ins = mk([(self.NAMES[0], 200000), (self.NAMES[1], 0)], "count",
                 topic="waymo against cruise")
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        d = ImageDraw.Draw(img)
        texts, sprites = [], []
        rt, rc = d.text, img.alpha_composite

        def t_spy(xy, text, *a, **k):
            texts.append((xy, str(text), k.get("font"), k.get("anchor")))
            return rt(xy, text, *a, **k)

        def c_spy(im, dest=(0, 0), *a, **k):
            if im.size[1] > 150:
                sprites.append((dest, im.size))
            return rc(im, dest, *a, **k)

        d.text, img.alpha_composite = t_spy, c_spy
        with mock.patch.object(vs, "scene_host", lambda *a, **k: runner), \
                mock.patch.object(vs, "_race_objects", lambda items: None):
            vs.draw_race(d, img, (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT),
                         vs.drawable_insight(ins), charts.HIGHLIGHT,
                         reveal, "count")
        return texts, sprites

    def test_long_names_are_whole_and_large(self):
        texts, _ = self._draw()
        for name in self.NAMES:
            hit = [t for t in texts if t[1] == name]
            self.assertTrue(hit, name)
            self.assertGreaterEqual(hit[0][2].size, 30)

    def test_no_runner_leaves_the_frame_or_sits_on_a_name(self):
        texts, sprites = self._draw()
        names = [t for t in texts if t[1] in self.NAMES]
        self.assertTrue(sprites)
        boxes = []
        for (nx, ny), t, f, anchor in names:
            l, tp, r, b = f.getbbox(t, anchor=anchor or "la")
            boxes.append((nx + l, ny + tp, nx + r, ny + b))
        for (x, y), (w, h) in sprites:
            self.assertGreaterEqual(x, vs.RX0)
            self.assertLessEqual(x + w, vs.RX1)
            for (a0, b0, a1, b1) in boxes:
                overlap = not (x + w <= a0 or a1 <= x or y + h <= b0 or b1 <= y)
                self.assertFalse(overlap, ((x, y, w, h), (a0, b0, a1, b1)))


class TheStackIsMadeOfTheSubject(unittest.TestCase):
    """"Generic blocks, each worth 20K, stack up ... the blocks could be
    anything" (Waymo re-render). Each block carries ONE emblem of what it
    is made of; "robotaxi" had no icon at all."""

    def test_a_robotaxi_is_a_taxi(self):
        from data_learning import icons
        got = icons.icon_png("how many robotaxi rides waymo gives every week", 64)
        self.assertIsNotNone(got)
        self.assertIn("1f695", str(got))
        self.assertIsNone(icons.icon_png("cabinet makers", 64))

    def test_every_landed_block_carries_one_emblem(self):
        glyph = Image.new("RGBA", (128, 128), (250, 0, 250, 255))
        ins = mk([("Oct 2023", 1), ("Aug 2024", 3), ("Feb 2025", 5)], "cities",
                 topic="cities waymo serves")
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        stamps = []
        real = img.alpha_composite

        def spy(im, dest=(0, 0), *a, **k):
            px = im.getpixel((im.size[0] // 2, im.size[1] // 2))
            if px[:3] == (250, 0, 250):
                stamps.append(dest)
            return real(im, dest, *a, **k)

        img.alpha_composite = spy
        with mock.patch.object(vs, "_subject_glyph", lambda *a, **k: glyph), \
                mock.patch.object(vs, "scene_host", lambda *a, **k: None):
            vs._MACHINE_DRAW["tower"](ImageDraw.Draw(img), img,
                                      (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT),
                                      vs.drawable_insight(ins),
                                      charts.HIGHLIGHT, 1.0, "cities")
        self.assertEqual(len(stamps), 5)
        self.assertEqual(len({x for x, _y in stamps}), 1)   # one per block


class AnAuthoredScenesMachineCountsAsShown(unittest.TestCase):
    """"seg2 and seg3 both use the same seesaw back-to-back" (Waymo): beat 1
    picked the scales while beat 2's own scene was a balance."""

    def test_a_scene_names_the_machines_it_draws(self):
        from data_learning import studio_render as sr
        ins = mk([("Waymo", 200000), ("Cruise", 0)], "count")
        ins.kind = "scene"
        ins.scene = {"elements": [{"type": "balance"},
                                  {"type": "race_track"},
                                  {"type": "caption"}]}
        self.assertEqual(sr.scene_machine_tokens(ins),
                         {"balance_scene", "race_scene"})
        ins.kind = "bars"
        self.assertEqual(sr.scene_machine_tokens(ins), set())

    def test_the_master_seeds_the_used_set_with_them(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_kinds_used |= scene_machine_tokens(", src)
