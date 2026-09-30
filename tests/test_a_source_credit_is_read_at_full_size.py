"""A SOURCE CREDIT IS READ AT FULL SIZE, WHOLE — ON BOTH CHANNELS.

2026-09-30, the first day the headless judge was back after its weekly
limit: 21 verdicts on 7 stories named the source line, 19 of them inside an
`unreadable` auto-fail, on the trending races and the explainer alike:

    "the source footer runs off the right edge in every frame. At hook@0.3
     through payoff@-0.4 it ends mid-sentence at '...McDonald's US', and it
     is also tiny and grey on black"          dollar_general, 2026-09-30
    "'Source: Federal Reserve Bank of New York...' is tiny grey text on
     black and cannot be read on a phone"      student_debt, 2026-09-30
    "the source footer ('Source: United Nations Institute for Training and
     Research (UNITAR) / International Telecommunication Union (ITU...') is
     tiny and truncated"                        global-ewaste, 2026-09-30

Three earlier fixes (09-11, 09-24, 09-25) each measured the line and fitted
it, and the fitter did the only thing a fitter can do with a string that is
too long: shrink it, then cut it. The defect was the LENGTH. The trending
credit kept up to 96 characters and cut "(fiscal year-end). McDonald's US
restaurant counts" mid-sentence because a sentence ending after a bracket
was not a sentence end; the explainer drew the full provenance —
publisher, dataset name, access date — median 83 characters, up to 318.

So the credit is SHORT (the publisher), and it is drawn at its full size.
The full provenance still goes to the description; see
`test_chart_race.test_the_full_source_still_reaches_the_description`.
"""
from __future__ import annotations

import glob
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engines import chart_race as cr  # noqa: E402

DOLLAR_GENERAL = (
    "Dollar General store counts from company 10-K annual reports (fiscal "
    "year-end). McDonald's US restaurant counts from company annual reports "
    "/ franchise disclosure documents. Figures approximate as publicly "
    "reported, rounded to the nearest hundred.")
FED = ("Federal Reserve Bank of New York, Center for Microeconomic Data, "
       "Household Debt and Credit Report — student loan and auto loan "
       "balances. Figures approximate as publicly reported, rounded to the "
       "nearest $10 billion.")


def _race_sources():
    seen = []
    for f in sorted(glob.glob(str(ROOT / "state" / "trending_packages" / "**"
                                  / "*.json"), recursive=True)):
        try:
            p = json.loads(Path(f).read_text())
        except Exception:  # noqa: BLE001
            continue
        if isinstance(p, dict) and p.get("format") == "graph_race" \
                and p.get("source") and p["source"] not in seen:
            seen.append(p["source"])
    return seen


def _race_fig():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt.figure(figsize=(10.8, 19.2), dpi=100), plt


class TheRaceCreditIsWhole(unittest.TestCase):

    def test_the_dollar_general_credit_does_not_stop_inside_mcdonalds(self):
        got = cr.credit_line(DOLLAR_GENERAL)
        self.assertFalse(got.endswith("McDonald's US"), got)
        self.assertNotIn("McDonald's US", got,
                         "a second source cut mid-name reads as cut off")
        self.assertIn("Dollar General", got)

    def test_the_fed_credit_ends_on_a_whole_name(self):
        got = cr.credit_line(FED)
        self.assertIn("Federal Reserve Bank of New York", got)
        self.assertFalse(got.endswith(("and Credit", "Microeconomic")), got)

    def test_a_trim_drops_whole_items_not_the_tail_of_a_name(self):
        got = cr.credit_line(
            "Combined annual sales of Novo Nordisk's Ozempic + Wegovy and "
            "Eli Lilly's Mounjaro + Zepbound, from company annual reports")
        self.assertFalse(got.endswith("Eli"), got)
        self.assertLessEqual(len(got), len("Source: ") + cr.CREDIT_MAX_CHARS)

    def test_every_real_race_credit_fits_at_full_size(self):
        """Measured exactly as the renderer measures it: at CREDIT_PT, in
        the regular weight it is drawn in, against 92% of a 1080 frame. A
        credit that does not fit here is the one the renderer shrinks."""
        fig, plt = _race_fig()
        try:
            too_wide = []
            for src in _race_sources() + [DOLLAR_GENERAL, FED]:
                got = cr.credit_line(src)
                if got and cr._text_px(fig, got, cr.CREDIT_PT, "normal") \
                        > 1080 * 0.92:
                    too_wide.append(got)
            self.assertEqual(too_wide, [],
                             "these are shrunk below full size on screen")
        finally:
            plt.close(fig)

    def test_the_fitter_measures_the_weight_it_draws(self):
        src = Path(cr.__file__).read_text()
        self.assertIn('_text_px(fig, credit, credit_size, "normal")', src)


class TheExplainerCreditIsThePublisher(unittest.TestCase):

    def _drawn(self, fig, source):
        from data_learning import charts as C
        C._footer(fig, types.SimpleNamespace(source=source))
        t = fig.texts[-1]
        out = (t.get_text(), t.get_fontsize())
        t.remove()
        return out

    def _sources(self):
        from data_learning.sources.base import Source
        seen, out = set(), []
        for f in sorted(glob.glob(str(ROOT / "data_learning" / "data"
                                      / "*.json"))):
            try:
                s = json.loads(Path(f).read_text()).get("source")
            except Exception:  # noqa: BLE001
                continue
            if not (isinstance(s, dict) and s.get("publisher")):
                continue
            key = (s.get("publisher"), s.get("name"))
            if key in seen:
                continue
            seen.add(key)
            out.append(Source(**{k: s[k] for k in (
                "name", "publisher", "url", "officiality", "access_date")
                if k in s}))
        return out

    def test_the_ewaste_credit_is_whole_and_full_size(self):
        from data_learning import charts as C
        from data_learning.sources.base import Source
        src = Source(name="Global E-waste Monitor 2024",
                     publisher="United Nations Institute for Training and "
                               "Research (UNITAR) / International "
                               "Telecommunication Union (ITU)",
                     url="https://ewastemonitor.info",
                     access_date="2026-09-16")
        fig, plt = C._card_base()
        try:
            txt, size = self._drawn(fig, src)
        finally:
            plt.close(fig)
        self.assertEqual(size, C.FOOTER_PT, "shrunk")
        self.assertNotIn("…", txt, "cut")
        self.assertIn("(ITU)", txt)
        self.assertNotIn("accessed", txt)

    def test_the_description_keeps_the_full_provenance(self):
        from data_learning.sources.base import Source
        s = Source(name="N", publisher="P", url="u", access_date="2026-09-30")
        self.assertEqual(s.credit(), "Source: P")
        self.assertIn("(N), accessed 2026-09-30", s.footer())

    def test_no_real_publisher_of_ordinary_length_is_shrunk_or_cut(self):
        """Over every dataset on disk. On the old footer 399 of 700 were
        drawn shrunk or cut (170 with an ellipsis). A publisher field that is
        itself a paragraph (a brain-written bibliography) still goes through
        the fitter; anything of ordinary length is read at full size."""
        from data_learning import charts as C
        fig, plt = C._card_base()
        try:
            bad = []
            for src in self._sources():
                if len(src.publisher) > 120:
                    continue
                txt, size = self._drawn(fig, src)
                if size < C.FOOTER_PT or "…" in txt:
                    bad.append((size, txt))
        finally:
            plt.close(fig)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
