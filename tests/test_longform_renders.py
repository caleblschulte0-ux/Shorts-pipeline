"""Long-form actually STARTS rendering — the colour comes from the look.

Every weekly long-form from 2026-09-13 to 2026-10-04 died on line one of
`longform_render.render()` with `KeyError: 'highlight'`: the 2026-09-10 look
rehaul took colour out of `studio_render.THEMES`, and this renderer still
read it. `tests/test_longform_gated.py` mocks `render()` whole, so four red
Sundays passed with every test green. This calls the real `render()` up to
the point it hands off to the story builder.

    python -m unittest tests.test_longform_renders -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_learning import charts, longform_render as LR   # noqa: E402
from shared import look                                    # noqa: E402


class _Reached(Exception):
    pass


class TestRenderGetsPastTheTheme(unittest.TestCase):

    def _render_until_story(self, slug: str) -> dict:
        seen = {}
        cfg = {"stories": [{"slug": slug, "title": "T", "segments": []}]}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            p.write_text(json.dumps(cfg))

            def _build(*a, **k):
                seen["highlight"] = charts.HIGHLIGHT
                raise _Reached

            with mock.patch.object(LR.story, "build", _build):
                with self.assertRaises(_Reached):
                    LR.render(slug, Path(td) / "o.mp4", config_path=p)
        return seen

    def test_every_theme_renders(self):
        # The theme is picked by slug hash; walk enough slugs to hit all.
        from data_learning.studio_render import THEMES, _theme_for
        hit = set()
        for i in range(200):
            slug = f"story-{i}"
            hit.add(id(_theme_for(slug)))
            self._render_until_story(slug)
            if len(hit) == len(THEMES):
                break
        self.assertEqual(len(hit), len(THEMES))

    def test_accent_is_the_design_systems(self):
        slug = "octopus-nine-brains"
        want = charts._hex(look.accent(look.accent_for(slug))[0])
        self.assertEqual(self._render_until_story(slug)["highlight"], want)


if __name__ == "__main__":
    unittest.main()
