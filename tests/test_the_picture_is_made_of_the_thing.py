"""An isotype is N copies of ONE THING — and the thing has to resolve.

Operator, 2026-09-13: *"I want more globes and less charts and I always want
a good video to post."* This file holds the half of that which is measurable.

`units_scene` is the MOST-USED machine in the whole queue — 32 of 176
un-posted beats, 18% of everything this channel draws. Rendered offline it
had a photo cut-out on NONE of them, and its no-cutout path was
`d.ellipse(...)`. So the machine that gets the most screen time was shipping
thirty featureless grey discs, which is both "colored dots are not something
we should be using" (operator, 2026-09-10) and the deeper failure underneath
it: a form whose entire claim is *count these* rendered as thirty things that
are not anything.

Three rules, each of which was a defect in a frame rendered on 2026-09-13:

  - THERE IS A SECOND CHOICE. `icons.icon_for` is cached, offline after the
    first fetch, and already caps the bars of `_story_pictorial_race`. It was
    simply never asked. Twelve container ships instead of twelve discs.
  - ASK ABOUT THE TOPIC, NOT JUST THE LABEL. On a trend the item label is a
    YEAR, and a year deliberately matches no icon — so the commonest shape of
    data on this channel could never resolve a unit no matter how good the
    table got.
  - WHEN NOTHING RESOLVES IT IS A TILE. A waffle unit says "one of these"
    without pretending to be a picture of anything. A disc claims to be a
    picture and is not.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import viz_scene as VS                    # noqa: E402
from data_learning import charts as C                        # noqa: E402
from data_learning.insights import Insight                   # noqa: E402
from data_learning.sources.base import DataPoint, Source     # noqa: E402

SRC = Source(name="X", publisher="P", url="https://x", access_date="2026-09-13")


def _ins(topic, pairs, hi, unit="count"):
    return Insight(kind="trend", topic=topic, main_insight="m",
                   items=[DataPoint(label=a, value=b) for a, b in pairs],
                   source=SRC, unit=unit, highlight_label=hi)


class AUnitIsAPictureOfSomething(unittest.TestCase):

    def test_a_year_label_still_resolves_a_unit_through_the_topic(self):
        """THE CASE THAT MADE THIS WHOLE CLASS INVISIBLE. Asked only about
        "2024" every trend fell to the blob path, and a trend is most of what
        this channel renders."""
        self.assertIsNotNone(
            VS.unit_glyph(None, "2024", 64, "container ship capacity"),
            "a year + a topic still gets no picture")

    def test_the_label_is_asked_FIRST(self):
        """When the item itself names a thing, that thing is the unit — the
        topic is the fallback, not the other way round."""
        by_label = VS.unit_glyph(None, "houses", 64, "container ship capacity")
        by_topic = VS.unit_glyph(None, "2024", 64, "container ship capacity")
        self.assertIsNotNone(by_label)
        self.assertIsNotNone(by_topic)
        self.assertNotEqual(list(by_label.getdata())[:64],
                            list(by_topic.getdata())[:64],
                            "the label lost to the topic")

    def test_nothing_resolving_is_None_not_a_blob(self):
        """`None` is the honest answer, and it is what routes the caller to a
        waffle TILE. A drawer that got a blob here could not tell the
        difference between 'a picture of a ship' and 'a circle'."""
        self.assertIsNone(VS.unit_glyph(None, "qzzx", 64, "wgggq"))

    def test_a_real_cutout_still_wins(self):
        from PIL import Image
        cut = Image.new("RGBA", (10, 10), (1, 2, 3, 255))
        got = VS.unit_glyph(cut, "houses", 40, "houses")
        self.assertEqual(got.size, (40, 40))
        self.assertEqual(got.getpixel((0, 0))[:3], (1, 2, 3))


class NeitherFieldFallsBackToADot(unittest.TestCase):
    """`draw_dot_field` was fixed on 2026-09-10 and its sibling was not —
    which is the shape of bug this repo keeps finding: a rule applied where it
    was noticed instead of where it is true."""

    def test_neither_unit_drawer_draws_an_ellipse(self):
        import ast
        import inspect
        for fn in (VS.draw_unit_figures, VS.draw_dot_field):
            tree = ast.parse(inspect.getsource(fn).lstrip())
            calls = [n for n in ast.walk(tree)
                     if isinstance(n, ast.Call)
                     and getattr(n.func, "attr", "") == "ellipse"]
            self.assertEqual(calls, [], f"{fn.__name__} still draws a disc")

    def test_both_ask_for_a_real_unit_before_falling_back(self):
        import inspect
        for fn in (VS.draw_unit_figures, VS.draw_dot_field):
            self.assertIn("unit_glyph", inspect.getsource(fn), fn.__name__)


class TypeOnTheGroundIsREADABLE(unittest.TestCase):
    """`legible` is a MEASUREMENT, so it cannot go stale when a token moves.

    A drawer holds one colour for its mark and its number both. That is fine
    at `HIGHLIGHT` (13.1:1) and invisible at `look.REST` (2.05:1), and which
    one it holds depends on whether the depicted item happens to be the
    story's subject — so the same machine was legible on one beat and not on
    the next."""

    def test_the_neutral_never_reaches_type(self):
        self.assertEqual(VS.legible(C.REST), C.TEXT)
        self.assertEqual(VS.legible(C.ACCENT), C.TEXT)

    def test_an_accent_is_left_alone(self):
        self.assertEqual(VS.legible(C.HIGHLIGHT), C.HIGHLIGHT)
        self.assertEqual(VS.legible(C.WARN), C.WARN)

    def test_everything_it_returns_clears_the_text_floor(self):
        for c in (C.REST, C.ACCENT, C.HIGHLIGHT, C.WARN, C.TEXT, C.SUBTLE,
                  C.GRID, C.CARD, C.NAME_REST):
            self.assertGreaterEqual(VS._contrast_on_ground(VS.legible(c)), 4.5,
                                    f"{c} came back unreadable")

    def test_the_two_headers_go_through_it(self):
        import inspect
        for fn in (VS.draw_unit_figures, VS.draw_dot_field):
            src = inspect.getsource(fn)
            self.assertIn("legible(color)", src,
                          f"{fn.__name__}'s number can still be drawn in the "
                          f"mark's colour")


class TheACCENTGoesOnTheSUBJECT(unittest.TestCase):
    """`shared/look`: "ONE accent per story, and it goes on the SUBJECT —
    decided by the story, never by draw order."

    The machines were told `_color_for(insight.items[0].label, insight)`: the
    colour of whatever happened to be item ZERO. Measured over the un-posted
    queue on 2026-09-13, 71 of 176 beats (40%) therefore drew their ENTIRE
    machine — globe, tower, scales, hourglass — in `ACCENT`, a mid-tone that
    separates from `HIGHLIGHT` by only 3.11:1 and so fails at the one job a
    supporting colour has."""

    def test_the_lead_is_the_accent_whatever_item_zero_is(self):
        ins = _ins("T", [("2015", 30.0), ("2024", 14.0)], "2024")
        self.assertEqual(VS._lead_color(ins), C.HIGHLIGHT)

    def test_a_baseline_subject_gets_the_alarm_colour(self):
        ins = _ins("T", [("2015", 30.0), ("2024", 14.0)], "target")
        ins.baseline = DataPoint(label="target", value=10.0)
        self.assertEqual(VS._lead_color(ins), C.WARN)

    def test_no_machine_is_handed_item_zeros_colour(self):
        """The call that caused it, by shape, so it cannot come back.

        ON CODE, NOT ON PROSE. The first cut of this grepped the raw file for
        the offending call and failed on `_lead_color`'s own docstring, which
        quotes it in order to explain what went wrong. A source-reading test
        in this repo asserts on the AST with string constants blanked —
        otherwise writing down why a bug happened reintroduces the bug.
        """
        import ast
        src = Path(ROOT / "data_learning" / "viz_scene.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "_color_for"):
                continue
            arg = node.args[0] if node.args else None
            self.assertFalse(
                isinstance(arg, ast.Attribute) and arg.attr == "label"
                and isinstance(arg.value, ast.Subscript),
                f"viz_scene.py:{node.lineno} colours a machine by DRAW ORDER "
                f"(items[0]) — the subject is `insight.highlight_label`")

    def test_the_mid_tone_reaches_no_drawer(self):
        """`ACCENT` survives only as a name in the brain's sandbox, for
        mechanics already authored against it."""
        import ast
        src = Path(ROOT / "data_learning" / "viz_scene.py").read_text()
        tree = ast.parse(src)
        # blank every docstring/comment-bearing constant so prose about the
        # defect does not count as the defect (the repo's standing rule for
        # source-reading tests).
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        uses = [n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.Name) and n.id == "ACCENT"]
        self.assertLessEqual(
            len(uses), 2,
            f"ACCENT is back in the drawers at lines {uses} — it is a "
            f"mid-tone 3.11:1 from HIGHLIGHT; supporting marks are REST")


class OneAccentREACHESTheWholeFrame(unittest.TestCase):
    """`shared/look`: ONE accent per story. It was TWO, on three palettes
    out of four, for as long as the machines have existed.

    `studio_render.render` themes each video by REBINDING the token —
    `charts.HIGHLIGHT, charts.ACCENT = look.accent(look.accent_for(slug))` —
    so the channel varies across videos and not within one. `viz_scene` then
    did `from .charts import HIGHLIGHT`, which is a SNAPSHOT taken at import
    and never updated. So the charts wore the story's blue/teal/rose and every
    machine beside them wore the module-load GOLD, in the same video, and the
    only reason it was not glaring is that one palette in four happens to be
    the gold.

    This is the failure mode a from-import has and a module read does not, so
    the test is the arithmetic of that: move the token, and check the machine
    moved with it.
    """

    def test_the_lead_colour_follows_the_story_accent(self):
        before = C.HIGHLIGHT
        ins = _ins("T", [("2015", 30.0), ("2024", 14.0)], "2024")
        try:
            for hexa in ("#FFD37A", "#F472B6", "#5EC8C8", "#60A5FA"):
                C.HIGHLIGHT = hexa
                self.assertEqual(VS._lead_color(ins), hexa,
                                 "the machines are still on the import-time "
                                 "accent while the charts moved")
        finally:
            C.HIGHLIGHT = before

    def test_the_token_is_not_snapshotted_at_import(self):
        """The mechanism, so the next `from .charts import HIGHLIGHT` is
        caught at the line that writes it rather than in a rendered frame."""
        import ast
        src = Path(ROOT / "data_learning" / "viz_scene.py").read_text()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.ImportFrom):
                continue
            for a in node.names:
                self.assertNotIn(
                    a.name, ("HIGHLIGHT", "ACCENT"),
                    f"viz_scene.py:{node.lineno} snapshots {a.name} — the "
                    f"studio rebinds it per story, so this file would draw "
                    f"the previous video's accent forever")

    def test_a_rendered_machine_actually_changes_colour(self):
        """Not the helper — the PIXELS. A machine drawn under two different
        story accents must not come out the same picture."""
        before = C.HIGHLIGHT
        ins = _ins("container ship capacity",
                   [("2006", 12500.0), ("2013", 18000.0), ("2019", 23000.0),
                    ("2024", 24000.0)], "2024")
        import tempfile
        shots = []
        try:
            for hexa in ("#FFD37A", "#F472B6"):
                C.HIGHLIGHT = hexa
                spec = VS.tower_scene(ins)
                self.assertTrue(spec, "tower_scene refused — test is vacuous")
                ins.scene, ins.kind = spec, "scene"
                with tempfile.TemporaryDirectory() as td:
                    res = VS.render_scene(ins, Path(td), "t", 3)
                    self.assertIsNotNone(res)
                    pat = res[0] if isinstance(res, tuple) else res
                    from PIL import Image
                    shots.append(list(Image.open(str(pat) % 3)
                                      .convert("RGB").getdata()))
        finally:
            C.HIGHLIGHT = before
        self.assertNotEqual(shots[0], shots[1],
                            "the machine rendered identically under two "
                            "different story accents")


if __name__ == "__main__":
    unittest.main()
