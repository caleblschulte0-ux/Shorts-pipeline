"""Is this beat GOOD news or BAD news — so Data does not cheer the damage.

The showrunner, on the illustrated arm's amazon-still-shrinking
(2026-09-24): "Data cheers with both arms up while the clearing grows, which
celebrates the damage", and on the next render "Data holds an arms-up
celebratory pose over 'The bill still grows' ... tonally wrong for the
payoff". A machine picks "cheer" for the moment its number LANDS, which is
right for a rebound and wrong for a record drought — and nothing in the
pipeline knew which one it was drawing.

Direction is not tone: a rising lifespan is good and a rising price is bad.
So this reads the claim's WORDS, and it is deliberately one-sided: it only
ever turns a celebration into a reaction. Unsure means leave it alone.
"""
from __future__ import annotations

import re

_BAD = re.compile(
    r"\b(los[st]\w*|clear(ed|ing)|deforest\w*|died|deaths?|dead|dying|kill\w*|"
    r"drought|crisis|disaster|collaps\w*|extinct\w*|endanger\w*|shrink\w*|"
    r"vanish\w*|destroy\w*|damage\w*|pollut\w*|emission\w*|toxic|wildfire\w*|"
    r"flood\w*|famine|hunger|poverty|debt|shortage|shortfall|scarc\w*|"
    r"burn\w*|melt\w*|warming|disease|outbreak|cases|overdose\w*|"
    r"homeless\w*|evict\w*|layoff\w*|unemploy\w*|inflation|pricier|"
    r"price\w* (hit|soar\w*|surg\w*|spik\w*|climb\w*|doubl\w*)|"
    r"cost\w* (more|soar\w*|surg\w*|doubl\w*)|record (high|heat)|"
    r"(bill|rent|premium)s? (still )?(grow|rise|climb)\w*|"
    r"declin\w*|decimat\w*|wip\w+ out|gutted|hole)\b", re.I)
_GOOD = re.compile(
    r"\b(recover\w*|rebound\w*|comeback|saved|cured|surviv\w*|restor\w*|"
    r"return\w*|thriv\w*|record (low|harvest)|cheaper|fell to|dropped to|"
    r"cleaner|healthier|longer lives|lifespan|life expectancy)\b", re.I)


def _text(insight) -> str:
    if isinstance(insight, str):
        return insight
    return " ".join(str(getattr(insight, k, "") or "")
                    for k in ("topic", "main_insight", "title"))


def is_bad_news(insight) -> bool:
    """True only when the claim's words are clearly about harm."""
    t = _text(insight)
    bad = len(_BAD.findall(t))
    good = len(_GOOD.findall(t))
    return bad > 0 and bad > good


#: Roles and animators that CELEBRATE. Racing and climbing are effort, not
#: celebration, and stay as they are.
CELEBRATIONS = frozenset({"cheer"})


def honest_role(role: str, insight) -> str:
    """`role`, unless it celebrates bad news — then a reaction to it."""
    if role in CELEBRATIONS and is_bad_news(insight):
        return "shock"
    return role
