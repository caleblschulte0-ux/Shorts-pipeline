"""A 240pt NUMBER, A COMMENT SAYING WHEN IT LEADS, AND IT LED NOTHING.

`build_story_ass` carried a hero number for the cold open — the story's
headline figure at `\\fs240`, positioned at y=235 — behind this guard:

    if headline and not hook_visual and not _share_lead and not chart_hook:

Its caller derives BOTH flags from the same value:

    hook_visual = bool(receipt)
    chart_hook  = lead_hook = (receipt is None)

Those are exact complements, so `not hook_visual and not chart_hook` is a
contradiction. With a receipt the first is False; without one the second is.
It has never drawn.

Composited by hand to see what it would have looked like if it fired: the
chart's own title lands at screen y≈174 and its subtitle at 281, so 240pt
centred at 235 is drawn straight through both —

    "NASA[    ]s[  ]re of t[  ]e [  ]ed[  ]l budget"

which is the `unreadable` class the showrunner already blocks for, and the
reason this cannot simply be switched back on where it stood.

The design moved past it too. `lead_hook` exists so seg0's CHART carries the
cold open, and the comment at its assignment says why: a hook with no data on
screen is the `empty_void` / `decorative_mascot` the gate blocks, and the
data demonstration should be the star from frame 1.

So it is gone, and `chart_hook` — a parameter the caller computed and nobody
read — went with it. `_headline_number` stays: the thumbnail and long-form
both use it.

Runs standalone:  python3 tests/test_the_hero_number_never_drew.py
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as sr   # noqa: E402


class TheContradictionThatHidIt(unittest.TestCase):
    """Kept as an executable statement of WHY it was dead, so nobody
    reintroduces the same pair of flags believing they select something."""

    def test_hook_visual_and_chart_hook_were_exact_complements(self):
        for receipt in (None, "some/path.png"):
            hook_visual = bool(receipt)
            chart_hook = receipt is None
            self.assertFalse(
                (not hook_visual) and (not chart_hook),
                f"receipt={receipt!r} would have drawn the hero number")

    def test_the_caller_still_derives_hook_visual_from_the_receipt(self):
        src = inspect.getsource(sr)
        self.assertIn("hook_visual=bool(receipt)", src)


class ItIsGoneAndStaysGone(unittest.TestCase):
    def test_no_240pt_overlay_survives(self):
        src = inspect.getsource(sr.build_story_ass)
        self.assertNotIn("fs240", src)

    def test_the_unread_parameter_went_with_it(self):
        params = inspect.signature(sr.build_story_ass).parameters
        self.assertNotIn("chart_hook", params)

    def test_nothing_still_passes_it(self):
        """Asserted on the AST: the comment above the removed branch quotes
        the old flag on purpose, and a substring search cannot tell an
        explanation from a call."""
        import ast
        tree = ast.parse(
            (_REPO / "data_learning" / "studio_render.py").read_text())
        bad = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               for kw in n.keywords if kw.arg == "chart_hook"]
        self.assertEqual(bad, [], f"chart_hook still passed at {bad}")

    def test_the_hook_TEXT_is_untouched(self):
        """Only the number went. The spoken hook still plays over the
        chart-led open, which is the thing that carries it."""
        src = inspect.getsource(sr.build_story_ass)
        self.assertIn("hchunks = _chunks(st.hook, 2) if not hook_visual", src)
        self.assertIn("pos(540,470)", src)


class TheHELPERIsStillLive(unittest.TestCase):
    """Deleting a dead branch must not take a live capability with it —
    `_headline_number` has two other readers."""

    def test_headline_number_still_exists(self):
        self.assertTrue(callable(sr._headline_number))

    def test_and_is_still_called_for_the_thumbnail(self):
        self.assertGreaterEqual(
            inspect.getsource(sr).count("_headline_number("), 2)

    def test_longform_still_imports_it(self):
        src = (_REPO / "data_learning" / "longform_render.py").read_text()
        self.assertIn("_headline_number", src)


if __name__ == "__main__":
    unittest.main()
