"""THE CTA WAS PRINTED ON TOP OF THE SOURCE CITATION.

    "payoff@-1.8, seg4:end, payoff@-0.4: the 'COMMENT BELOW ▼' CTA is drawn
     directly on top of the four-line source citation, rendering both into
     unreadable mush at the bottom of the screen"
                                 self-checkout-cashier-jobs, 2026-09-09

The closing's foot band is 1683..1920 and `studio_render` documents the stack
it budgeted for, in a comment right above the code:

    question  an5 fs42, <=2 lines   1690 .. 1800
    CTA       an5 fs54, 1 line      1802 .. 1870
    sources   an2 fs15              1880 .. 1898

Eighteen pixels for the sources — which is one line at fs15. The strip is one
ASS Dialogue with no wrap directive, so libass wraps it at the play width, and
`an2` anchors the block at its BOTTOM: a wrapped citation grows UPWARD,
straight through the CTA.

Three publishers is 223 characters and four lines. There is no room to give
it — the question and CTA already hold 180 of the band's 237 pixels — so the
line is BOUNDED, and it sheds in order: the access date, then the dataset
name, then it truncates. Every publisher is still NAMED, which is what the
strip is for; the full provenance lives in the dataset and the manifest,
which is where anyone checking it would look.

Cutting at the first comma instead — the obvious shortcut — splits
"(Cashiers, employment)" and leaves an unclosed bracket on screen.

Runs standalone:  python3 tests/test_the_sources_strip_is_one_line.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from data_learning import studio_render as sr   # noqa: E402

#: The real footers from the blocked video.
REAL = [
    "National Retail Federation (NRF) (Self-checkout adoption), "
    "accessed 2026-09-08",
    "U.S. Bureau of Labor Statistics (Cashiers, employment), "
    "accessed 2026-09-08",
    "World Bank (Fossil fuel energy consumption), accessed 2026-09-07",
]


def _shorten(uniq):
    """The strip's own logic, applied the way `_write_ass` applies it."""
    src = " · ".join(uniq)
    if len(src) > sr._CH_SRC:
        no_date = [sr._re_src.sub("", f).strip() for f in uniq]
        src = " · ".join(no_date)
        if len(src) > sr._CH_SRC:
            src = " · ".join(sr._re_name.sub("", f).strip() for f in no_date)
    if len(src) > sr._CH_SRC:
        src = src[:sr._CH_SRC - 1].rstrip(" ·") + "…"
    return src


class ItFitsOneLine(unittest.TestCase):
    def test_the_real_three_source_citation_fits(self):
        out = _shorten(REAL)
        self.assertLessEqual(len(out), sr._CH_SRC, out)

    def test_every_publisher_is_still_named(self):
        out = _shorten(REAL)
        for pub in ("National Retail Federation",
                    "U.S. Bureau of Labor Statistics", "World Bank"):
            self.assertIn(pub, out, f"{pub} vanished from {out!r}")

    def test_a_short_citation_is_left_completely_alone(self):
        one = ["World Bank (Fossil fuel), accessed 2026-09-07"]
        self.assertEqual(_shorten(one), one[0])

    def test_it_sheds_the_DATE_before_the_dataset_name(self):
        """The name says WHICH series; the date is the least useful thing on
        screen and the longest."""
        two = ["United States Environmental Protection Agency "
               "(Greenhouse gas inventory), accessed 2026-09-08",
               "International Energy Agency "
               "(World energy balances), accessed 2026-09-08"]
        self.assertGreater(len(" · ".join(two)), sr._CH_SRC, "case too short")
        out = _shorten(two)
        self.assertNotIn("accessed", out)
        self.assertIn("Greenhouse gas inventory", out)

    def test_it_never_leaves_an_unclosed_bracket(self):
        """`split(",")[0]` — the shortcut — cuts inside "(Cashiers,
        employment)" and ships "U.S. Bureau of Labor Statistics (Cashiers"."""
        for uniq in (REAL, REAL * 2, REAL + ["X (a, b, c), accessed 2026-01-01"]):
            out = _shorten(uniq)
            self.assertEqual(out.count("("), out.count(")"),
                             f"unbalanced brackets in {out!r}")

    def test_an_absurd_citation_still_ends_bounded(self):
        out = _shorten([f"Publisher {i} (Series {i}), accessed 2026-09-08"
                        for i in range(40)])
        self.assertLessEqual(len(out), sr._CH_SRC)
        self.assertTrue(out.endswith("…"))


class TheStripCannotWrapAtAll(unittest.TestCase):
    """Bounding the text is the fix; `\\q2` is the belt — libass will not wrap
    a line carrying it, whatever arrives."""

    def test_the_dialogue_carries_the_no_wrap_directive(self):
        import inspect
        src = inspect.getsource(sr)
        i = src.index("src_txt = (")
        self.assertIn("\\q2", src[i:i + 400],
                      "the sources line can still wrap")

    def test_the_budget_is_named_once(self):
        """A number the comment states and the code repeats is two numbers."""
        self.assertIsInstance(sr._CH_SRC, int)
        self.assertGreater(sr._CH_SRC, 60)


if __name__ == "__main__":
    unittest.main()
