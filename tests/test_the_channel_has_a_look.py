"""THE WHOLE LOOK OF THE THING IS CHEAP.

The operator, 2026-09-10, after watching three shipped videos. The diagnosis
turned out not to be taste — it is the house data-viz anti-pattern list,
almost word for word:

    "Thick saturated blocks, heavy gridlines, no breathing room. Reads loud,
     even CHILDISH, at scale."

The data channel drew **165-point** fully saturated capsules on a flat navy
gradient in **DejaVu Sans Bold** — matplotlib's default face, and the single
loudest signal that a frame was made by a script — with the value printed on
every bar **in the series colour**. Every one of those is on the list.

## The look was already chosen. The channel just never adopted it.

`data_learning/flat2d.py` says so in its own docstring: *"the Vox /
Kurzgesagt register: deep gradient ground, restrained palette, one idea per
frame, big confident type, generous negative space, smooth motion. **This is
the look the operator picked on pixels (sample v2).**"* It has carried the
curiosity channel since, and `repair_planner` has had a defect code called
`CHEAP_TYPOGRAPHY` pointing at it the whole time.

So `shared/look.py` is not a new invention: its ground, its restraint, its
spaced kicker and its continuous push are flat2d's, made aspect-agnostic
(flat2d is 1920x1080; the shorts are 1080x1920) and joined to the mark specs
from the data-viz standard. One module, so the two channels cannot drift
apart again — which is exactly how they drifted in the first place.

Runs standalone:  python3 tests/test_the_channel_has_a_look.py
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

from shared import look  # noqa: E402


class TheChannelOwnsItsType(unittest.TestCase):
    """A render that falls back to DejaVu is a render that does not look like
    the channel — and if it falls back only in CI, every visual test is
    measuring a frame that never ships. This session has already fixed that
    exact divergence twice (cairosvg, and ten mascot-less machines), so the
    font is COMMITTED, not fetched."""

    def test_every_weight_is_present(self):
        self.assertTrue(look.fonts_are_real(),
                        f"missing type in {look.FONT_DIR}")

    def test_the_faces_are_committed_not_fetched(self):
        import subprocess
        for p in sorted(look.FONT_DIR.glob("Inter*.ttf")):
            r = subprocess.run(["git", "ls-files", "--error-unmatch",
                                str(p.relative_to(_REPO))],
                               cwd=_REPO, capture_output=True)
            self.assertEqual(r.returncode, 0, f"{p.name} is not committed")

    def test_each_face_is_under_the_repos_size_rule(self):
        """CLAUDE.md: never commit files >256KB. Subsetting Inter to Latin
        takes a weight from 410KB to 38KB, which is what makes committing it
        possible at all."""
        for p in sorted(look.FONT_DIR.glob("Inter*.ttf")):
            self.assertLess(p.stat().st_size, 256 * 1024, p.name)

    def test_the_licence_ships_with_the_font(self):
        self.assertTrue((look.FONT_DIR / "Inter-OFL.txt").exists(),
                        "Inter is OFL — the licence has to travel with it")

    def test_font_returns_a_real_face_not_the_fallback(self):
        f = look.font(48, "bold")
        self.assertIn("Inter", str(getattr(f, "path", "")) or f.getname()[0])

    def test_an_unknown_weight_still_returns_something_drawable(self):
        self.assertIsNotNone(look.font(30, "no-such-weight"))


class MarksAreTHIN(unittest.TestCase):
    def test_a_bar_is_capped_absolutely(self):
        """No band, however tall, may fatten the mark past the frame cap."""
        self.assertLessEqual(look.bar_thickness(1080, 10_000),
                             1080 * look.BAR_CAP_FRAC + 1)

    def test_a_bar_is_also_capped_by_its_own_band(self):
        """...and a short band keeps air even when the frame cap allows more."""
        self.assertLessEqual(look.bar_thickness(1080, 40), 40 * 0.5)

    def test_the_shipped_thickness_is_a_fraction_of_what_it_was(self):
        """The Moon video drew 109pt bars on a three-row chart."""
        from data_learning import charts
        self.assertLess(charts._bar_lw(3), 30.0)
        self.assertGreater(charts._bar_lw(3), 8.0)

    def test_the_cap_holds_at_every_row_count(self):
        from data_learning import charts
        for n in range(1, 12):
            self.assertLessEqual(charts._bar_lw(n), 30.0, n)


class TextWearsINKNeverTheSeriesColour(unittest.TestCase):
    """The one channel that carries identity is the coloured MARK. Colouring
    the text burns it, and a light hue is illegible as type on the ground."""

    def test_the_chart_tokens_come_from_the_design_system(self):
        from data_learning import charts
        self.assertEqual(charts.TEXT, charts._hex(look.INK))
        self.assertEqual(charts.SUBTLE, charts._hex(look.INK_2))

    def test_ink_is_never_one_of_the_accents(self):
        hues = {c for pair in look.ACCENTS.values() for c in pair}
        for name, ink in (("INK", look.INK), ("INK_2", look.INK_2),
                          ("INK_3", look.INK_3)):
            self.assertNotIn(ink, hues, name)

    def test_a_row_label_is_no_longer_tinted_the_accent(self):
        """No composer paints its own text in the mark's colour.

        This used to assert on the y-ticklabel tint loop that did the
        recolouring; the row names are drawn inside the axes now and there is
        no tick loop left, so it asserts the RULE instead of one expression
        of it — `shared/palette` states it in its own module docstring, and
        `_story_versus` and `_story_stack` were both breaking it (a column
        name in the dim accent, a segment label in its own series hue).
        """
        import ast
        import inspect
        from data_learning import charts
        #: The names a MARK is painted with. None of them may reach a `color=`
        #: on a text call. (`facecolor=col` on the mark itself is the point.)
        MARK = {"col", "gcol", "color", "HIGHLIGHT", "ACCENT", "REST",
                "series_color", "accent"}
        for fn in (charts._story_bars, charts._story_versus,
                   charts._story_stack, charts._story_pictorial_race):
            tree = ast.parse(inspect.getsource(fn).lstrip())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "text"):
                    continue
                for kw in node.keywords:
                    if kw.arg != "color":
                        continue
                    used = {n.id for n in ast.walk(kw.value)
                            if isinstance(n, ast.Name)}
                    self.assertFalse(
                        used & MARK,
                        f"{fn.__name__} line {node.lineno}: text coloured "
                        f"with {sorted(used & MARK)} — the mark beside it "
                        f"already carries the identity")

    def test_a_stacked_column_does_not_hand_out_six_hues(self):
        """One accent and a neutral ladder — not the categorical palette.

        A six-source breakdown shipped as blue/orange/violet/pink/yellow/
        green stacked into a tower: the loudest frame the channel made, and
        the anti-pattern the house standard names outright.
        """
        import inspect
        from data_learning import charts
        src = _code_only(inspect.getsource(charts._story_stack))
        self.assertNotIn("series_color", src)
        self.assertIn("_stack_tint", src)
        seen = {charts._stack_tint(i, 6, False) for i in range(6)}
        self.assertNotIn(charts.HIGHLIGHT, seen)
        self.assertEqual(charts._stack_tint(2, 6, True), charts.HIGHLIGHT)


def _code_only(src: str) -> str:
    """`src` with comments and docstrings stripped.

    Source-reading tests in this repo have asserted on prose more than once
    — a comment quoting the code it replaced is not the code.
    """
    import ast
    tree = ast.parse(src.lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


class TheGroundIsALIVE(unittest.TestCase):
    """A static plate reads as a frozen hold — to the cadence gate and to a
    viewer alike. flat2d learned this and wrote it down; every `temporal_gate`
    block on the data channel is the same finding from the other end."""

    def test_the_ground_renders_at_both_aspects(self):
        for w, h in ((1080, 1920), (1920, 1080)):
            im = look.ground(w, h)
            self.assertEqual(im.size, (w, h))

    def test_the_ground_is_not_a_flat_fill(self):
        import numpy as np
        a = np.asarray(look.ground(540, 960).convert("L"), dtype="float32")
        self.assertGreater(float(a.std()), 3.0, "the ground is flat")

    def test_the_push_changes_every_frame(self):
        import numpy as np
        base = look.ground(360, 640)
        seen = set()
        for i in range(6):
            a = np.asarray(look.push(base, i, 6).convert("L"), dtype="uint8")
            seen.add(a.tobytes())
        self.assertEqual(len(seen), 6, "the push repeats a frame")


class OneAccentPerStory(unittest.TestCase):
    def test_the_accent_is_deterministic(self):
        a = look.accent_for("nobody-has-walked-on-the-moon")
        for _ in range(4):
            self.assertEqual(look.accent_for("nobody-has-walked-on-the-moon"), a)

    def test_different_stories_get_different_accents(self):
        got = {look.accent_for(s) for s in
               ("moon", "buybacks", "cargo", "eagles", "vaccines", "mail")}
        self.assertGreater(len(got), 1, "every story gets the same accent")

    def test_every_accent_names_a_bright_and_a_dim(self):
        for name, pair in look.ACCENTS.items():
            self.assertEqual(len(pair), 2, name)
            self.assertGreater(sum(pair[0]), sum(pair[1]),
                               f"{name}: the bright one is not brighter")


class TheFITTERLivesWithTheType(unittest.TestCase):
    def test_it_shrinks_before_it_ellipsises(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        f, out = look.fit(d, "1966 (Apollo buildup)", 60, 700)
        self.assertEqual(out, "1966 (Apollo buildup)")
        self.assertLessEqual(d.textlength(out, font=f), 700)

    def test_it_gives_up_rather_than_draw_unreadably_small(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        _f, out = look.fit(d, "x" * 300, 60, 200)
        self.assertTrue(out.endswith("…"))


class EveryStringOnTheCardIsMEASURED(unittest.TestCase):
    """The headline goes through `fit_title`, the kicker through
    `_fit_text_to`, the value column through `_measure_pts` — and the SOURCE
    CREDIT went through nothing at all, drawn at a fixed 11pt with no width
    limit. A source string has no bounded length, so it simply ran off the
    card, and the showrunner reported it by name for weeks:

        "every source credit (seg1:mid, seg2:start, seg3:end) runs off the
         right frame edge at '...accessed 2026-08-2'"
                              container-ships-floating-cities, 2026-09-11

    Seen again unfixed in a full render on 2026-09-13, clipped mid-word at
    "...(Scientific Assessment of Ozone Depl".
    """

    LONG = ("World Meteorological Organization (WMO) / UN Environment "
            "Programme (UNEP)")

    def _card(self, publisher, name="Scientific Assessment of Ozone "
                                    "Depletion 2022 Executive Summary"):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        ins = Insight(kind="rank", topic="t", main_insight="m",
                      items=[DataPoint(label="a", value=1.0),
                             DataPoint(label="b", value=2.0)],
                      source=Source(name=name, publisher=publisher,
                                    url="https://x",
                                    access_date="2026-09-13"),
                      unit="count", highlight_label="b")
        from data_learning import charts as C
        fig, plt = C._card_base()
        C._compose_story(fig, plt, ins, 1.0)
        fig.canvas.draw()
        return fig, plt

    def _footer_text(self, fig):
        return [t for t in fig.texts if t.get_position()[1] < 0.03]

    def test_no_text_on_the_card_crosses_the_right_edge(self):
        fig, plt = self._card(self.LONG)
        try:
            w = fig.get_size_inches()[0] * fig.dpi
            over = [(t.get_text()[:50], t.get_window_extent().x1)
                    for t in fig.texts if t.get_window_extent().x1 > w]
            self.assertEqual(over, [], f"runs off the frame: {over}")
        finally:
            plt.close(fig)

    def test_it_SHRINKS_before_it_truncates(self):
        """A credit is an ATTRIBUTION. Losing the end of it is a real cost,
        not merely an ugly one, so the type gives up three points before any
        character is dropped — a credit that fits at 8pt is never cut."""
        fig, plt = self._card(self.LONG, name="ozone hole")
        try:
            ft = self._footer_text(fig)
            self.assertTrue(ft, "the source line vanished entirely")
            from data_learning import charts as C
            self.assertTrue(ft[0].get_fontsize() < C.FOOTER_PT
                            or "\n" in ft[0].get_text(),
                            "it neither wrapped nor shrank, so it must be clipping")
            self.assertNotIn("\u2026", ft[0].get_text(),
                             "truncated when shrinking would have fitted it")
            self.assertIn("UNEP", ft[0].get_text(),
                          "the end of the attribution was dropped")
        finally:
            plt.close(fig)

    def test_what_cannot_fit_at_the_floor_keeps_its_HEAD(self):
        """Some credits genuinely do not fit at 8pt — this one is 148
        characters. Then the ellipsis is the honest answer, and WHICH END
        survives is the whole question: the publisher identifies the source,
        so the cut takes the study title off the tail and never the
        organisation off the front."""
        fig, plt = self._card(self.LONG)
        try:
            got = self._footer_text(fig)[0].get_text()
            self.assertIn("\u2026", got, "a 148-char credit fitted?")
            self.assertIn("World Meteorological Organization", got,
                          "the cut took the publisher instead of the tail")
        finally:
            plt.close(fig)

    def test_a_short_credit_is_left_at_full_size(self):
        """The fitter must not tax every card for the worst case."""
        fig, plt = self._card("NASA", name="ozone hole")
        try:
            ft = self._footer_text(fig)
            self.assertTrue(ft)
            from data_learning import charts as C
            self.assertEqual(ft[0].get_fontsize(), C.FOOTER_PT)
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
