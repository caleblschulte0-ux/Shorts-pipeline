"""Crude word matching, shared by everything that asks "is this ABOUT that?".

Two parts of the pipeline need the same cheap test — does one short string
share subject matter with another — and they must not grow separate copies of
it (`tests/test_no_second_source_of_truth.py` is the standing rule; captions
already had to be consolidated once).

  * `auto_repair` asks whether a beat's media query depicts what the beat SAYS,
    so an interchangeable stock shot can be repaired instead of shipped.
  * `planner` asks which designed scene a beat's own words support, so a scene
    staged for one subject is not rotated onto a beat about another.

Deliberately not a stemmer or an embedding: a five-character prefix catches
breathe/breathing/breath and glacier/glaciers, costs nothing, and never needs a
model download in CI. It will miss synonyms — that is a known limit, and both
callers are written so a MISS means "leave it alone", never "guess".
"""
from __future__ import annotations

import re

STOP = frozenset("""a an and are as at be been but by can do does for from had has have
how in into is it its more most no not of on one or other our out over so some such than
that the their them then there these they this to too up very was were what when where
which while who will with would you your""".split())


def words(s) -> set[str]:
    """Content words, prefix-stemmed to 5 chars. Stopwords and 1-2 letter
    tokens dropped — they anchor nothing."""
    out = set()
    for w in re.findall(r"[a-z]+", str(s).lower()):
        if len(w) < 3 or w in STOP:
            continue
        out.add(w[:5] if len(w) > 5 else w)
    return out


def shares(a, b) -> bool:
    """Do these two strings share any content word?"""
    return bool(words(a) & words(b))
