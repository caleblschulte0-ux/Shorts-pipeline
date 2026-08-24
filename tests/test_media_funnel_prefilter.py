"""Entity-word title filtering must match WHOLE words, not substrings.

Doctor finding ab128687aaf7: `_prefilter`'s entity filter implemented
"the title must contain the entity's distinctive word" as a raw substring
test, so a search for "Elon Musk" kept "Muskox herd expands" and "Muskrat
population grows" in the scored candidate set. A surname is a word; these
tests hold the filter to word boundaries while proving that the headlines
it was built for — possessives, hyphenations, real surname usage — still
pass.

Fully offline: exercises `_prefilter` directly on synthetic candidates.

    python -m unittest tests.test_media_funnel_prefilter -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funnel import media_funnel as mf   # noqa: E402


def _survives(entity: str, title: str) -> bool:
    c = mf.Candidate(url="https://example.com/a.jpg", source="newsapi",
                     article_title=title,
                     article_url="https://example.com/article")
    return len(mf._prefilter([c], entity=entity)) == 1


class TestWholeWordEntityFilter(unittest.TestCase):
    # (entity, article title, should the candidate survive?)
    TABLE = [
        # -- the finding's literal lookalikes: substring hits, word misses --
        ("Elon Musk", "Muskox herd expands in the Arctic", False),
        ("Elon Musk", "Muskrat population grows near the delta", False),
        # (the filter requires the LAST distinctive entity token — the
        # surname — so single-token "Ann" is the boundary-collision case)
        ("Ann", "Annual report shows record profits", False),
        ("Elon Musk", "Muskmelon harvest sets a state record", False),
        # -- real surname headlines that must KEEP matching ----------------
        ("Elon Musk", "Musk announces new launch date", True),
        ("Elon Musk", "Musk's rocket lands upright again", True),
        ("Elon Musk", "Musk’s new venture raises billions", True),  # curly '
        ("Ann", "Ann returns to the stage after a decade", True),
        ("Elon Musk", "Why MUSK keeps winning contracts", True),          # case
        ("Elon Musk", "The Musk-led venture files for IPO", True),        # hyphen
        ("Elon Musk", "Ex-Musk engineers start a rival firm", True),
        ("Elon Musk", "Is this Musk? Insiders say yes", True),            # punct
        # -- hyphenated lookalike is still a different word ----------------
        ("Elon Musk", "Muskox-hunting season opens early", False),
        # -- apostrophes INSIDE a name survive tokenisation ----------------
        ("Conan O'Brien", "O'Brien signs a new streaming deal", True),
        ("Conan O'Brien", "Obrien Industries posts a loss", False),
        # -- a possessively-given entity still means the surname -----------
        ("Elon Musk's", "Musk shows off the new implant", True),
    ]

    def test_table(self):
        for entity, title, want in self.TABLE:
            with self.subTest(entity=entity, title=title):
                self.assertEqual(_survives(entity, title), want,
                                 f"{entity!r} vs {title!r}: expected "
                                 f"{'keep' if want else 'drop'}")

    def test_missing_title_metadata_is_still_kept(self):
        # Pre-existing contract: with no article_title there is nothing to
        # test against, so the candidate passes through to the ranker.
        c = mf.Candidate(url="https://example.com/a.jpg", source="newsapi",
                         article_title="", article_url="")
        self.assertEqual(len(mf._prefilter([c], entity="Elon Musk")), 1)

    def test_no_entity_disables_the_filter(self):
        c = mf.Candidate(url="https://example.com/a.jpg", source="newsapi",
                         article_title="Muskox herd expands",
                         article_url="")
        self.assertEqual(len(mf._prefilter([c], entity="")), 1)


if __name__ == "__main__":
    unittest.main()
