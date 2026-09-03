"""Titles are fitted by MEASUREMENT, and the consolidation changed nothing.

Two halves:

1. EQUIVALENCE. `_fit_title` moved out of `engines/chart_race.py` into
   `shared/fit_title.py` so the explainer could stop guessing. Per CLAUDE.md
   the test of a consolidation is equivalence against the original, so the
   pre-move implementation is kept verbatim below as an oracle and compared
   over generated input. A cleanup that quietly re-cuts every video is not a
   cleanup.

2. THE BUG IT FIXED. `charts._heading` picked its font size from
   `len(title)` under a comment claiming it "auto-shrink[s] so long titles
   never clip the right edge of the card". Character count is not width.
   Measured on that very card, before the fix:

       "Urban growth just hit a 50-year low"               0.929
       "World hydropower fell below its 1990 level"        0.966  <- shipped
       "Prevalence of undernourishment in the population"  1.120
       "Agricultural land area as a share of total land"   1.352
       "MMMMMMMMMMMMMMMMMMMMMMMM"  (24 chars)              1.481

   against a 0.915 right margin. The showrunner's note on the hydropower
   story on 2026-08-11 was "a headline clipped off the right edge".

    python -m unittest tests.test_fit_title -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from shared.fit_title import fit_title  # noqa: E402
from data_learning import charts as C  # noqa: E402


# --------------------------------------------------------------------------
# The ORIGINAL implementation, copied verbatim from engines/chart_race.py as
# it stood before the move. Do not "tidy" this — it is an oracle.
# --------------------------------------------------------------------------
def _fit_title_ORIGINAL(fig, text, font_path, max_w_px,
                        max_lines=2, hi=46, lo=26):
    import matplotlib.font_manager as fm
    words = text.split()
    if not words:
        return text, fm.FontProperties(size=hi)
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:  # noqa: BLE001
        return text, (fm.FontProperties(fname=font_path, size=hi)
                      if font_path else fm.FontProperties(weight="bold",
                                                          size=hi))

    def _fp(size):
        return (fm.FontProperties(fname=font_path, size=size) if font_path
                else fm.FontProperties(weight="bold", size=size))

    def _width(s, fp):
        probe = fig.text(0, 0, s, fontproperties=fp)
        w = probe.get_window_extent(renderer=renderer).width
        probe.remove()
        return w

    for size in range(hi, lo - 1, -2):
        fp = _fp(size)
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if cur and _width(trial, fp) > max_w_px:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines and all(_width(x, fp) <= max_w_px
                                           for x in lines):
            return "\n".join(lines), fp
    return "\n".join(words[:max_lines]), _fp(lo)


def _titles():
    """Generated input: real production titles, plus the shapes that break
    a character-count heuristic (all-caps, one very long word, empty)."""
    real = [
        "People per sq km",
        "Urban growth just hit a 50-year low",
        "Renewable electricity output (% of total)",
        "World hydropower fell below its 1990 level",
        "Prevalence of undernourishment in the population",
        "Agricultural land area as a share of total land area worldwide",
        "S&P 500 close",
        "CO2 emissions (metric tons per capita)",
    ]
    synth = ["", "   ", "A", "M" * 24, "i" * 24, "W" * 60,
             "Supercalifragilisticexpialidocious",
             "one two three four five six seven eight nine ten eleven"]
    caps = [t.upper() for t in real[:4]]
    return real + synth + caps


class TestTheMoveChangedNothing(unittest.TestCase):
    """Same figure, same input, same output — text AND font size."""

    def setUp(self):
        self.fig = plt.figure(figsize=(10.0, 15.6), dpi=110)
        self.fig.canvas.draw()

    def tearDown(self):
        plt.close(self.fig)

    def width(self, text, fp):
        """Widest rendered line of `text` at `fp`."""
        w = 0.0
        for line in text.split("\n"):
            probe = self.fig.text(0, 0, line, fontproperties=fp)
            w = max(w, probe.get_window_extent(
                renderer=self.fig.canvas.get_renderer()).width)
            probe.remove()
        return w

    def compare(self, title, band, **kw):
        """Identical wherever the original was CORRECT; strictly better
        where it overflowed. The move added one behaviour on purpose — an
        unbreakable token is now ellipsized instead of being returned
        untouched to run off the card — so blanket identity would be the
        wrong claim to pin, and asserting it loosely would hide real drift.
        """
        want_t, want_fp = _fit_title_ORIGINAL(self.fig, title, None,
                                              band, **kw)
        got_t, got_fp = fit_title(self.fig, title, None, band, **kw)
        if self.width(want_t, want_fp) <= band:
            self.assertEqual(got_t, want_t,
                             f"text drifted for {title!r} @ {band} {kw}")
            self.assertEqual(got_fp.get_size_in_points(),
                             want_fp.get_size_in_points(),
                             f"size drifted for {title!r} @ {band} {kw}")
            return "identical"
        self.assertLessEqual(
            self.width(got_t, got_fp), band,
            f"{title!r} @ {band}: the original overflowed and so does the "
            f"replacement — the one case the move existed to fix")
        return "improved"

    def test_identical_over_generated_input(self):
        seen = set()
        for title in _titles():
            for band in (300.0, 640.0, 913.0, 1400.0):
                seen.add(self.compare(title, band))
        self.assertIn("identical", seen)
        self.assertIn("improved", seen,
                      "no input exercised the overflow branch — the "
                      "generated set no longer covers what this fixes")

    def test_identical_across_the_size_and_line_knobs(self):
        for title in _titles()[:8]:
            for kw in ({"max_lines": 1}, {"max_lines": 3},
                       {"hi": 42, "lo": 22}, {"hi": 30, "lo": 30}):
                self.compare(title, 640.0, **kw)

    def test_an_unbreakable_token_is_ellipsized_not_let_off_frame(self):
        got_t, got_fp = fit_title(self.fig, "W" * 60, None, 640.0)
        self.assertTrue(got_t.endswith("\u2026"))
        self.assertLessEqual(self.width(got_t, got_fp), 640.0)

    def test_the_original_really_did_run_off_frame(self):
        """Pin the defect, so the improvement above is not measured against
        a straw man."""
        want_t, want_fp = _fit_title_ORIGINAL(self.fig, "W" * 60, None, 640.0)
        self.assertGreater(self.width(want_t, want_fp), 640.0)

    def test_chart_race_delegates_rather_than_keeping_a_copy(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        body = src.split("def _fit_title(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("return fit_title(", body)
        self.assertNotIn("get_window_extent", body,
                         "chart_race still has its own measuring copy")


class TestNothingClipsTheCard(unittest.TestCase):
    """The explainer's own card, measured. `_heading` places the title at
    HEAD_X and the card's matching right margin is HEAD_RIGHT."""

    def measure(self, title, subtitle=""):
        fig, _plt = C._card_base()
        C._heading(fig, title, subtitle)
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        W = fig.get_size_inches()[0] * fig.dpi
        H = fig.get_size_inches()[1] * fig.dpi
        t = fig.texts[0]
        tb = t.get_window_extent(r)
        out = {"right": tb.x1 / W, "bottom": tb.y0 / H,
               "lines": t.get_text().count("\n") + 1,
               "size": t.get_fontsize()}
        if subtitle:
            sb = fig.texts[1].get_window_extent(r)
            out["sub_top"] = sb.y1 / H
        _plt.close(fig)
        return out

    def test_every_title_stays_inside_the_card(self):
        for title in _titles():
            if not title.strip():
                continue
            m = self.measure(title)
            self.assertLessEqual(
                m["right"], C.HEAD_RIGHT + 0.005,
                f"{title!r} runs to {m['right']:.3f} past "
                f"{C.HEAD_RIGHT} — this is the shipped bug")

    def test_the_headline_that_shipped_clipped_now_fits(self):
        m = self.measure("World hydropower fell below its 1990 level")
        self.assertLessEqual(m["right"], C.HEAD_RIGHT)

    def test_a_short_title_is_not_needlessly_shrunk(self):
        """The old heuristic also went the other way — it shrank titles that
        would have fit. Measuring should give short titles the big size."""
        self.assertGreaterEqual(self.measure("People per sq km")["size"], 40)

    def test_shrinking_is_preferred_to_wrapping(self):
        """A second title line pushes toward the plot, so one line wins
        while a readable size can still hold it."""
        m = self.measure("World hydropower fell below its 1990 level")
        self.assertEqual(m["lines"], 1)

    def test_a_title_too_long_for_one_line_may_wrap(self):
        m = self.measure(
            "Agricultural land area as a share of total land area worldwide")
        self.assertEqual(m["lines"], 2)
        self.assertLessEqual(m["right"], C.HEAD_RIGHT + 0.005)

    def test_a_wrapped_title_never_reaches_the_subtitle(self):
        """The fix must not trade a clipped title for an overlapping one."""
        for title in _titles():
            if not title.strip():
                continue
            m = self.measure(title, "since 1990")
            self.assertGreater(
                m["bottom"], m["sub_top"],
                f"{title!r}: title bottom {m['bottom']:.3f} is below "
                f"subtitle top {m['sub_top']:.3f}")

    def test_the_subtitle_never_moves(self):
        """It sits at SUB_Y whatever the title does — anything else walks it
        down onto the chart axes, whose tallest variant tops out at 0.85."""
        for title in ("People per sq km",
                      "Agricultural land area as a share of total land area"):
            self.assertAlmostEqual(
                self.measure(title, "since 1990")["sub_top"], C.SUB_Y, 3)

    def test_an_empty_title_does_not_explode(self):
        for t in ("", "   "):
            self.measure(t, "since 1990")


class TestTheHeuristicIsGone(unittest.TestCase):
    def test_no_character_count_font_ladder(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _heading(", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("len(title) <=", body,
                         "the character-count guess is back")
        self.assertIn("fit_title(", body)


if __name__ == "__main__":
    unittest.main()
