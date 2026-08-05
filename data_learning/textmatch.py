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
    """Content words, plural-stripped then prefix-stemmed to 5 chars.

    The plural strip is not cosmetic. Without it "tree" stems to "tree" and
    "trees" to "trees", so a shot querying `old tree forest sunlight` under the
    line "it has been through the leaves of trees" was counted as depicting
    something else entirely — a false positive in the one metric that decides
    whether a shot is about its own beat. A measure that cries wolf gets
    ignored, which is worse than not having it.

    Only a trailing "s" is removed, and only from words long enough that the
    stem still carries meaning. Nothing cleverer: this runs offline in CI with
    no model, and every rule added here is a rule that can misfire.
    """
    out = set()
    for w in re.findall(r"[a-z]+", str(s).lower()):
        if len(w) < 3 or w in STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w[:5] if len(w) > 5 else w)
    return out


def shares(a, b) -> bool:
    """Do these two strings share any content word?"""
    return bool(words(a) & words(b))
