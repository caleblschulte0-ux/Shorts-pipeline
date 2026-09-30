"""A series that turned once is not a series that zig-zagged.

2026-09-30: landlines rose to 1.26B in 2006 and fell to 815M. `reversal`
drew the coaster captioned "158M to 1.3B / up and down the whole way" and
the spotlight captioned "it never settled ... anywhere between 158M and
1.3B", under a title saying landlines are dying. The showrunner blocked it
three times for exactly that contradiction.
"""
import unittest
from types import SimpleNamespace as N

from data_learning import studio_render as sr
from data_learning import viz_scene as vs

LANDLINES = [("1972", 158436054), ("1982", 351911500), ("1991", 543078177),
             ("2006", 1260900000), ("2015", 1046000000), ("2025", 815000000)]


def _pts(rows):
    return [N(label=l, value=v) for l, v in rows]


class ATurnIsNotAZigzag(unittest.TestCase):
    def test_one_turn_says_where_it_turned_and_where_it_is(self):
        p = _pts(LANDLINES)
        head, sub = vs.coaster_caption(p, [x.value for x in p])
        self.assertEqual(sub, "peaked in 2006, falling since")
        self.assertTrue(head.endswith("815M"), head)
        self.assertNotIn("up and down", head + sub)

    def test_a_trough_says_climbing(self):
        p = _pts([("1", 9), ("2", 6), ("3", 2), ("4", 5), ("5", 8)])
        self.assertEqual(vs.coaster_caption(p, [x.value for x in p])[1],
                         "bottomed out in 3, climbing since")

    def test_a_real_zigzag_still_says_up_and_down(self):
        p = _pts([(str(i), v) for i, v in enumerate([1, 5, 2, 6, 1, 7])])
        self.assertEqual(vs.coaster_caption(p, [x.value for x in p])[1],
                         "up and down the whole way")

    def test_reversal_is_never_drawn_as_a_spotlight(self):
        self.assertNotIn("spotlight_scene", sr._MACHINES["reversal"])
        self.assertTrue(sr._MACHINES["reversal"])


if __name__ == "__main__":
    unittest.main()
