"""Turn a beat's SHOT DESCRIPTION into a stock search, when it asks for a person.

THE DEFECT, in one beat:

    understand: "a figure taking one deliberate breath"
    image.query: null
    what shipped: a white clip-art stick figure on an orange gradient

Five of shared-air's twenty beats carry no media query, and ALL FIVE of them
explicitly ask for a human being. With no query the planner cannot search, so
each falls through to the designed scene library — and those plates are the
single thing four independent blind judges, across two different films, named
as the worst moment on screen ("a cartoon stick figure on an empty blue
slide"). Meanwhile every judge's MEMORABLE frame was real footage of people:
"four teens under a sodium traffic light in green fog", "three swimmers
silhouetted against a red sunset".

The author asked for a person. The pipeline had no way to go and find one.

WHY THIS IS NOT THE TRANSFORMATION I REFUSED. `film_metrics` documents, at
length, that deriving media queries from NARRATION is forbidden: it took
unanchored 8/15 to 0/15 while producing 'means next person breathe' and 'every
argument anyone ever'. That ruling stands and this does not violate it. Three
differences, each load-bearing:

  1. The source is `understand`, not narration. It is already a SHOT
     DESCRIPTION written by the authoring brain — short, concrete, and about
     what should be visible. Narration is prose about an idea; extracting a
     picture from it is the hard problem that failed.
  2. It only fires where there is NO authored query. It can never override an
     author, so the "a measure satisfied without improving the film" failure
     mode has nothing to act on.
  3. The fallback it replaces is the WORST-RATED element in the film. If the
     search misses, the beat still gets its designed scene exactly as before.
     The change is strictly additive: the floor cannot drop.

It is deliberately narrow. It does not fire on landscapes, objects or
abstractions — a beat asking for "clouds moving over the horizon" already has
a query, and inventing searches for everything is how you get wallpaper.
"""
from __future__ import annotations

import re

# Words that mean A PERSON IS THE SUBJECT. Deliberately concrete: no "life",
# "someone's", "we" — a beat about humanity in the abstract is not a beat that
# wants a stock clip of a human, and over-matching here would start inventing
# searches for the whole film.
_HUMAN = (
    "figure", "person", "people", "human", "man", "woman", "men", "women",
    "child", "children", "kid", "boy", "girl", "hand", "hands", "face",
    "someone", "crowd", "worker", "family", "couple", "stranger", "strangers",
)

# `figure` is the pictogram's name for itself and a poor stock-search term —
# it returns statues and diagrams. Every provider indexes "person".
_SUBJECT_SWAP = {
    "figure": "person", "someone": "person", "human": "person",
    "kid": "child", "strangers": "people", "stranger": "person",
}

# Dropped before the query is built: articles, filler, and the editorial
# adjectives an author writes for a HUMAN reader ("real", "unmistakably",
# "deliberate"). A provider does not index sincerity.
#
# "still" is NOT dropped, though it reads like filler. In "standing still" it
# is the entire action of the shot, and losing it turned a usable
# `person standing still` into `person standing world moves`.
_DROP = frozenset("""a an the and or but of to in on at as is are was were be been
being with for from by into over under through while then than that this these those
one two some any its their his her our your my it they them he she we us
real really actual actually genuine genuinely unmistakably clearly very quite just
same own nothing something anything everything
deliberate calm quiet slow simple ordinary plain single whole entire""".split())


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z]+", str(text or "").lower())]


def wants_a_person(understand: str) -> bool:
    """Does this shot description put a human being on screen?"""
    return any(w in _HUMAN for w in _words(understand))


def search_query_from(understand: str, max_terms: int = 3) -> str | None:
    """A short stock-search phrase for a shot description, or None.

    Returns None when the description does not ask for a person — silence is
    correct there, and a caller that gets None must leave the beat alone.

    The subject word comes first because providers weight leading terms, then
    the action and setting words in the order the author wrote them. Capped at
    four terms: every provider degrades badly past that, which is the reason
    authored queries are short in the first place.
    """
    if not wants_a_person(understand):
        return None
    words = _words(understand)
    subject = None
    rest: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in _DROP:
            continue
        term = _SUBJECT_SWAP.get(w, w)
        if subject is None and (w in _HUMAN):
            subject = term
            seen.add(term)
            continue
        if term in seen or len(term) < 3:
            continue
        seen.add(term)
        rest.append(term)
    if not subject:
        return None
    # A bare subject ("person") is a worse search than no search: it returns
    # generic portrait stock that belongs to no beat, which is the wallpaper
    # this exists to stop.
    if not rest:
        return None
    return " ".join([subject] + rest[:max(0, max_terms - 1)])
