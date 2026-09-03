"""Three defects the showrunner named, in its own words, while holding every
explainer video on 2026-08-11/12.

The motion fix (#259) worked — every segment measured 17.8-24.0 effective fps
against an 11.0 floor, and not one video was blocked on temporal grounds. The
gate stopped refusing to look and started actually watching, and then held
everything at 39-57 against a bar of 70. These are what it saw.

1. "The headline stat — hydro falling from 18.4% to 16.1% — is never actually
   shown" / "a hairline timeline and an empty lower frame that no scroller
   would stay for" / "no frame is >30% empty".

   The trend chart padded its y-axis by a fraction of the ABSOLUTE VALUE
   (`max(values) * 1.22`) rather than of the variation. For a series living
   in a narrow band high above zero — which is most of them — that is huge
   dead space, and it flattens the change the video is about:

       values 16.1 .. 18.7 (span 2.6)  ->  ylim 15.63 .. 22.81
       data occupied 36% of the axis and 20.3% of the CARD

2. "One chart-draw template is doing all the work for three very different
   numbers, so the video is 89 seconds of the same rising line" / "Three
   different indicators rendered as the same faded line chart".

   `_take` lets any `time` kind repeat freely. True for maps — two countries
   are two pictures — false for the line-chart template, and explainer
   stories are nearly all time series.

3. The repair loop could not rank anything: `scene_repair` handed the judge
   2-tuples `(label, path)` where it unpacks 3, so EVERY call died on "not
   enough values to unpack (expected 3, got 2)". Production logged
   "DEGRADED: vision ranking unavailable" on every repair, and the objective
   fallback saturates at exactly 1.0 for all three candidates — so repair
   picked blind, and picked the same `trend+drag_line` every single time.

    python -m unittest tests.test_explainer_actually_ships -v
"""
from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import charts as C, viz_director as V  # noqa: E402
from data_learning.insights import Insight  # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="WDI", publisher="World Bank", url="https://example",
             access_date="2026-08-11")

# The actual hydropower series from the blocked story.
HYDRO = [("1990", 18.4), ("1997", 18.7), ("2005", 17.2),
         ("2014", 16.4), ("2024", 16.1)]


def series(pts, unit="percent", kind="trend"):
    return Insight(kind=kind, topic="Renewable electricity output",
                   main_insight="World hydropower fell below its 1990 level",
                   items=[DataPoint(label=l, value=v) for l, v in pts],
                   source=SRC, unit=unit, highlight_label=pts[-1][0])


class TrendCase(unittest.TestCase):
    def frame(self, pts, unit="percent"):
        fig, plt = C._card_base()
        ax, _arts = C._story_trend(fig, plt, series(pts, unit), "sub", 1.0)
        fig.canvas.draw()
        y0, y1 = ax.get_ylim()
        vals = [v for _l, v in pts]
        span = max(vals) - min(vals)
        box = ax.get_position()
        out = {"ylim": (y0, y1),
               "axis_share": span / (y1 - y0) if y1 > y0 else 0.0,
               "card_share": (span / (y1 - y0) * box.height
                              if y1 > y0 else 0.0),
               "yticklabels": [t.get_text()
                               for t in ax.get_yticklabels()],
               "top": box.y1}
        plt.close(fig)
        return out


class TestTheChangeIsActuallyVisible(TrendCase):

    def test_the_hydropower_fall_fills_the_frame(self):
        """20.3% of the card was the shipped state."""
        f = self.frame(HYDRO)
        self.assertGreater(f["axis_share"], 0.45,
                           f"data uses {f['axis_share']:.0%} of the axis")
        self.assertGreater(f["card_share"], 0.30,
                           f"data uses {f['card_share']:.0%} of the card")

    def test_headroom_scales_with_the_span_not_the_magnitude(self):
        """The defect in one line: identical shape, different absolute size,
        must frame identically. The old `max(values) * 1.22` made the big-
        number version nearly flat."""
        small = self.frame([("a", 1.0), ("b", 3.0), ("c", 2.0)])
        big = self.frame([("a", 1000.0), ("b", 3000.0), ("c", 2000.0)])
        self.assertAlmostEqual(small["axis_share"], big["axis_share"],
                               places=6)

    def test_a_narrow_band_high_above_zero_is_the_hard_case(self):
        near = self.frame([("a", 980.0), ("b", 1000.0), ("c", 990.0)])
        self.assertGreater(near["axis_share"], 0.45)

    def test_the_old_multiplier_is_gone(self):
        """Comments are stripped first — the fix's own explanation quotes the
        dead expression, and a test that matches prose instead of code would
        fail on a correct file."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _story_trend(", 1)[1].split("\ndef ", 1)[0]
        code = "\n".join(l for l in body.splitlines()
                         if not l.lstrip().startswith("#"))
        self.assertNotIn("max(values) * 1.22", code)


class TestATruncatedAxisSaysSo(TrendCase):
    """Framing the data range is fine for a line chart; framing it with NO
    scale is a way of overstating a change. `set_yticks([])` drew none."""

    def test_the_y_axis_is_labelled(self):
        labels = [t for t in self.frame(HYDRO)["yticklabels"] if t.strip()]
        self.assertGreaterEqual(len(labels), 2)

    def test_the_labels_carry_the_real_values(self):
        labels = " ".join(self.frame(HYDRO)["yticklabels"])
        self.assertIn("16.1", labels)
        self.assertIn("18.7", labels)

    def test_the_empty_tick_list_is_gone(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _story_trend(", 1)[1].split("\ndef ", 1)[0]
        code = "\n".join(l for l in body.splitlines()
                         if not l.lstrip().startswith("#"))
        self.assertNotIn("ax.set_yticks([])", code)


class TestEdgeSeries(TrendCase):
    def test_a_flat_series_does_not_divide_by_zero(self):
        f = self.frame([("a", 5.0), ("b", 5.0), ("c", 5.0)])
        self.assertLess(f["ylim"][0], f["ylim"][1])

    def test_an_all_zero_series_survives(self):
        f = self.frame([("a", 0.0), ("b", 0.0)])
        self.assertLess(f["ylim"][0], f["ylim"][1])

    def test_negative_values_survive(self):
        f = self.frame([("a", -4.0), ("b", -1.0), ("c", -9.0)])
        self.assertGreater(f["axis_share"], 0.45)

    def test_the_peak_callout_stays_inside_the_axis(self):
        """Raising the plot box must not push the peak label into the
        subtitle band."""
        for pts in (HYDRO, [("a", 1.0), ("b", 9.0), ("c", 3.0)]):
            f = self.frame(pts)
            vals = [v for _l, v in pts]
            span = max(vals) - min(vals)
            self.assertLess(max(vals) + span * 0.12, f["ylim"][1])
            self.assertLessEqual(f["top"], 0.845)


class TestOneLineChartPerVideo(unittest.TestCase):
    def ts(self, name):
        return Insight(
            kind="trend", topic=name, main_insight=f"{name} rose over time",
            items=[DataPoint(label=str(1990 + i * 8), value=10.0 + i)
                   for i in range(5)],
            source=SRC, unit="percent", highlight_label="2024")

    def run_postpass(self, n):
        """The post-pass exactly as `assign` runs it."""
        inss = [self.ts(f"S{i}") for i in range(n)]
        feats = [V._features(i) for i in inss]
        chosen, used, images = ["trend"] * n, {"trend"}, 0
        for lim in ("trend", "timeline"):
            seen = False
            for i in range(n):
                if chosen[i] != lim:
                    continue
                if not seen:
                    seen = True
                    continue

                def free(c):
                    m = V.KINDS.get(c, {})
                    return (m.get("place") or m.get("repeatable")
                            or c not in used)
                alt = next((c for c in V._candidates(inss[i], feats[i])
                            if c != lim and c not in ("trend", "timeline")
                            and V.renderable(c) and free(c)
                            and not (V.KINDS.get(c, {}).get("image")
                                     and images >= 12)), None)
                if alt:
                    chosen[i] = alt
                    used.add(alt)
        return chosen

    def test_three_time_series_do_not_become_three_line_charts(self):
        self.assertEqual(len(set(self.run_postpass(3))), 3)

    def test_the_first_one_keeps_its_line_chart(self):
        """A line is the right depiction for a time series — the complaint
        was the REPEAT, so exactly one survives."""
        self.assertEqual(self.run_postpass(3)[0], "trend")

    def test_the_replacement_is_not_itself_a_repeat(self):
        """The first cut of this pass turned trend/trend/trend into
        trend/waffle/waffle — the same complaint, different template."""
        for n in (3, 4, 5):
            got = self.run_postpass(n)
            self.assertEqual(len(set(got)), n, f"n={n}: {got}")

    def test_no_segment_is_left_without_a_depiction(self):
        """Refusing inside `_take` could strand a segment; the post-pass only
        ever moves one to a renderable alternative."""
        for n in (2, 3, 4, 5, 6):
            self.assertTrue(all(self.run_postpass(n)))

    def test_maps_may_still_repeat(self):
        """Two countries are two pictures — the rule is about templates."""
        src = (ROOT / "data_learning" / "viz_director.py").read_text()
        body = src.split("ONE LINE CHART PER VIDEO", 1)[1]
        self.assertIn('m.get("place")', body)


class TestTheRepairJudgeCanBeCalledAtAll(unittest.TestCase):
    """Shapes, checked against each other — no network, no CLI."""

    REPAIR = (ROOT / "scripts" / "scene_repair.py").read_text()
    REVIEW = (ROOT / "scripts" / "showrunner_review.py").read_text()

    def test_the_judge_unpacks_three(self):
        self.assertIn("for p, lab, ts in labeled", self.REVIEW)

    def test_scene_repair_sends_three(self):
        m = re.search(r"labeled\.append\(\((.*?)\)\)", self.REPAIR, re.S)
        self.assertIsNotNone(m)
        parts = [x for x in m.group(1).split(",") if x.strip()]
        self.assertEqual(len(parts), 3, f"sends {len(parts)}, judge wants 3")

    def test_the_path_comes_first(self):
        """(label, path) was the old order — right count, wrong meaning, and
        it would have listed the label as the filename."""
        m = re.search(r"labeled\.append\(\((.*?)\)\)", self.REPAIR, re.S)
        self.assertIn("fs[pick]", m.group(1).split(",")[0])

    def test_the_two_tuple_really_did_raise(self):
        """Pin the production error so the fix is measured against it."""
        with self.assertRaises(ValueError) as cm:
            for _p, _l, _t in [("a", "b")]:
                pass
        self.assertIn("expected 3", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class TestTheClosingTextClearsTheChart(unittest.TestCase):
    """"the strong bubble finale is buried under overlapping text" — and the
    fix note that came with it: "Move the CTA block below the bubble cluster
    ... so it never overlaps 'Hong Kong SAR, China' or 'Gibraltar'".

    On a `lead_payoff` close the LAST segment's chart spans the closing, so
    anything drawn inside the chart region lands on its value labels. The
    answer was already in the same function: narration is pinned to the
    lower-band plate "so it never lands on the chart". The closing's question
    and CTA now join it.
    """

    SRC = (ROOT / "data_learning" / "studio_render.py").read_text()

    def ys(self):
        import data_learning.studio_render as S
        block = self.SRC.split('question = getattr(st, "question", "")', 1)[1]
        block = block.split("# Dedupe", 1)[0]
        q = int(re.search(r"pos\(540,(\d+)\)", block).group(1))
        cta = int(re.search(r"move\(540,\d+,540,(\d+),", block).group(1))
        return q, cta, S

    def test_both_sit_below_the_chart(self):
        q, cta, S = self.ys()
        chart_bottom = S.CHART_Y + S.CHART_H
        # an5 is centred; a 2-line fs42 block reaches ~55px above its centre
        self.assertGreater(q - 55, chart_bottom - 20,
                           f"question at {q} still overlaps the chart "
                           f"(bottom {chart_bottom})")
        self.assertGreater(cta - 34, chart_bottom)

    def test_both_sit_inside_the_foot_band(self):
        q, cta, S = self.ys()
        self.assertGreaterEqual(q - 55, S.FOOT_Y - 5)
        self.assertLess(cta + 34, 1920)

    def test_they_do_not_overlap_each_other(self):
        q, cta, _S = self.ys()
        self.assertGreater(cta - 34, q + 55,
                           "the CTA overlaps the question")

    def test_they_clear_the_sources_strip(self):
        """Sources are an2 fs15 at y=1898, so they occupy ~1880..1898."""
        _q, cta, _S = self.ys()
        self.assertIn("pos(540,1898)", self.SRC)
        self.assertLess(cta + 34, 1880)

    def test_the_question_cannot_grow_to_three_lines(self):
        """A third line pushes its top back over the chart, so the wrap is
        part of the geometry, not a formatting preference."""
        block = self.SRC.split('question = getattr(st, "question", "")', 1)[1]
        self.assertIn("_wrap(question, 30)", block)

    def test_it_matches_the_plate_the_narration_already_uses(self):
        """The precedent is three lines up in the same function — if that
        plate ever moves, this should move with it."""
        self.assertIn("pos(540,1734)", self.SRC)


class TestRepairKeepsTheBestCut(unittest.TestCase):
    """Bounded self-repair re-rendered over the output and replaced the
    verdict UNCONDITIONALLY, so a repair that landed worse discarded a better
    video. Its own docstring claimed the opposite ("a repair that lands worse
    simply keeps the video held, exactly as before"). Measured on the
    2026-08-12 explainer slate:

        urban   53 -> 48      hydro   48 -> 39
        hunger  44 -> 35      macao   56 -> 69

    three of four downhill, each discarding the better cut. The gate still
    decides everything — this only stops throwing away its best judgment.
    """

    SRC = (ROOT / "scripts" / "post_stories.py").read_text()

    def body(self):
        return self.SRC.split("BOUNDED SELF-REPAIR", 1)[1].split(
            "\n        if args.dry_run", 1)[0]

    def test_the_new_verdict_is_compared_before_it_is_adopted(self):
        b = self.body()
        self.assertIn("_better", b)
        self.assertIn("> _prev_score", b)

    def test_a_worse_repair_reverts_the_video(self):
        b = self.body()
        self.assertIn("REVERTING to the better cut", b)
        self.assertIn("_sh.move(", b)

    def test_the_kept_verdict_is_re_logged(self):
        """Otherwise the sidecar on disk describes a cut that was thrown
        away, and the next repair reads the wrong diagnosis."""
        self.assertIn("_gate.log(gate, slug)", self.body())

    def test_the_gate_still_decides(self):
        """Nothing here may turn a BLOCK into a ship — it only chooses which
        of two judged cuts to keep."""
        b = self.body()
        self.assertNotIn("blocked = False", b)
        self.assertNotIn('"ship"', b)

    def test_the_scratch_copy_is_cleaned_up(self):
        self.assertIn("unlink(missing_ok=True)", self.body())
