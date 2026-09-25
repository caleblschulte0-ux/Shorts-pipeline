"""The highlight ring goes AROUND the number, never through it.

"a cyan highlight circle covers the '10000' digits" (Waymo, 2026-09-25).
The ring was `w/2 + 24, h/2 + 14`: a fixed pad only contains a box that is
nearly square, so on a wide number the ellipse ran inside the box's corners.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as sr  # noqa: E402


class TheRingClearsEveryCorner(unittest.TestCase):
    def test_square_to_very_wide(self):
        for w, h in ((40, 40), (90, 50), (150, 50), (300, 50), (520, 60),
                     (60, 140)):
            rx, ry = sr.ring_radii(w, h)
            # the stroke's INNER edge, and the box's corner with its pad
            ix, iy = rx - sr.RING_BORD / 2, ry - sr.RING_BORD / 2
            cx, cy = w / 2 + sr.RING_PAD * 0.99, h / 2 + sr.RING_PAD * 0.99
            self.assertLess((cx / ix) ** 2 + (cy / iy) ** 2, 1.0, (w, h))

    def test_the_old_ring_did_cut_a_wide_number(self):
        """The regression, stated: the fixed pad ran through the corners."""
        w, h = 300, 50
        rx, ry = w / 2 + 24, h / 2 + 14
        self.assertGreater(((w / 2) / rx) ** 2 + ((h / 2) / ry) ** 2, 1.0)

    def test_the_compositor_uses_it(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn('ring_radii(e["box"][0], e["box"][1])', src)
        self.assertNotIn('e["box"][0] / 2 + 24', src)


if __name__ == "__main__":
    unittest.main()
