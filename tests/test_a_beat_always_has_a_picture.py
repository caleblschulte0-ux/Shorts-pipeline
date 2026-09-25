"""When every image source is down, a beat still gets the object it names.

2026-09-25: ChatGPT's media worker had produced nothing for four days,
Pollinations answered 429 on nearly every call and Gemini's free tier was
spent. Fictional beats fell to keyword stock, the relevance check dropped it,
and five trending stories shipped as bare gameplay — every one blocked.
`funnel/icon_panel.py` is the last resort that needs nothing.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from funnel import icon_panel as IP  # noqa: E402


def _fake_icon(tmp):
    p = Path(tmp) / "icon.png"
    Image.new("RGBA", (64, 64), (200, 80, 80, 255)).save(p)
    return p


class TheIconPanel(unittest.TestCase):
    def test_it_draws_the_named_object_on_the_channel_ground(self):
        with tempfile.TemporaryDirectory() as td:
            icon = _fake_icon(td)
            with mock.patch("data_learning.icons.icon_png",
                            lambda t, px=512: icon if "phone" in t else None):
                got = IP.icon_panel(["no match here", "robocall phone"],
                                    Path(td) / "p.png")
            self.assertIsNotNone(got)
            with Image.open(got) as im:
                self.assertEqual(im.size, (1080, 1080))

    def test_nothing_it_cannot_depict(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("data_learning.icons.icon_png",
                            lambda t, px=512: None):
                self.assertIsNone(IP.icon_panel(["sealed box"],
                                                Path(td) / "p.png"))


class TheBackfillFallsBackToIt(unittest.TestCase):
    def test_a_dead_generator_still_leaves_a_picture(self):
        from funnel import entity_media, gemini_images
        import scripts.run_trending_daily as R
        pkg = {"title": "t", "script": "x", "shots": [
            {"phrase": "the same recorded voice called four times",
             "query": "robocall phone screen"},
            {"phrase": "a sealed box sat there", "query": "sealed box"}]}
        with tempfile.TemporaryDirectory() as td:
            icon = _fake_icon(td)
            keyword_only = [s["phrase"][:50] for s in pkg["shots"]]
            with mock.patch.object(gemini_images, "generate_image",
                                   lambda *a, **k: None), \
                    mock.patch.object(entity_media, "validate_package",
                                      lambda p: {"keyword_only_shots":
                                                 keyword_only}), \
                    mock.patch("data_learning.icons.icon_png",
                               lambda t, px=512: icon if t and "phone" in t
                               else None), \
                    mock.patch.object(R, "OUTPUT_DIR", Path(td)):
                R._backfill_illustrations(pkg)
            self.assertTrue(pkg["shots"][0].get("image_url"))
            self.assertFalse(pkg["shots"][1].get("image_url"))


if __name__ == "__main__":
    unittest.main()
