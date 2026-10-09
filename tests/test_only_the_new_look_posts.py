"""Only the new (illustrated, "B") look posts.

Operator, 2026-10-09: *"We are only posting b type videos from here on
out."* The registry gives the current look no weight, so every story is
planned in the new look and the day's quota is all new look. A story whose
scenes cannot all be drawn falls back to the current look at render time;
that render is not judged and does not post — it is kept for another day.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import style_arms as A  # noqa: E402


def _code(src: str) -> str:
    """Source with string constants blanked, so prose cannot pass a test."""
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            n.value = ""
    return ast.unparse(tree)


class TheRegistrySaysBOnly(unittest.TestCase):
    def test_every_slot_is_the_new_look(self):
        self.assertEqual(A.weights(), {"illustrated": 1.0})
        self.assertEqual(A.quota(4), {"illustrated": 4})
        for slug in ("plastic-in-your-body", "measles-ninety-five-rule", "x"):
            self.assertEqual(A.choose(slug), "illustrated")


class AFallbackIsNotJudged(unittest.TestCase):
    def test_the_rendered_look_is_checked_before_the_showrunner(self):
        code = _code((ROOT / "scripts" / "post_stories.py").read_text())
        render = code.index("studio_render.render(slug, out, config_path=args.config)")
        check = code.index("_style_arms0.read(out)", render)
        review = code.index("will_upload = ", render)
        self.assertLess(check, review)


if __name__ == "__main__":
    unittest.main()
