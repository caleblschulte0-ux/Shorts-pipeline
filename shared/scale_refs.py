"""TRUE size comparisons a hook may borrow — "a forest the size of France".

Operator, 2026-09-25, on the rainforest story: *"why a forest the size of
France disappeared, or something like that, right?"*

A comparison is the most clickable thing a data hook can say and the
easiest to fake, because it brings a number and a name the dataset does not
contain. So the comparisons are not written by the brain at all. This table
holds a small set of reference sizes a viewer already has a feel for, each
with the figure and where it comes from; `comparisons()` checks a story's own
data values against it and hands the brain ONLY the phrases that are
arithmetically true. The hook validator then admits those names and numbers
(`hook_doctrine.sharpen`), and nothing else from outside.

Add a row only with a sourced figure. Reference values are TOTAL area (land
+ water) from the CIA World Factbook / US Census Bureau unless noted.
"""
from __future__ import annotations

import re

#: name -> (km², how a person says it, source)
AREAS_KM2 = {
    "Texas":          (695_662, "Texas", "US Census Bureau"),
    "France":         (551_695, "France", "INSEE, metropolitan France"),
    "Spain":          (505_990, "Spain", "CIA World Factbook"),
    "California":     (423_970, "California", "US Census Bureau"),
    "Japan":          (377_975, "Japan", "CIA World Factbook"),
    "Germany":        (357_022, "Germany", "CIA World Factbook"),
    "Italy":          (301_340, "Italy", "CIA World Factbook"),
    "United Kingdom": (243_610, "the UK", "CIA World Factbook"),
    "Florida":        (170_312, "Florida", "US Census Bureau"),
    "New York State": (141_297, "New York State", "US Census Bureau"),
    "Portugal":       (92_212, "Portugal", "CIA World Factbook"),
    "Switzerland":    (41_285, "Switzerland", "CIA World Factbook"),
    "Belgium":        (30_528, "Belgium", "CIA World Factbook"),
    "Wales":          (20_779, "Wales", "UK Office for National Statistics"),
    "Connecticut":    (14_357, "Connecticut", "US Census Bureau"),
    "Delaware":       (6_446, "Delaware", "US Census Bureau"),
    "Rhode Island":   (4_001, "Rhode Island", "US Census Bureau"),
    "Greater London": (1_572, "London", "UK Office for National Statistics"),
    "New York City":  (783.8, "New York City", "US Census Bureau, land"),
    "Manhattan":      (59.1, "Manhattan", "US Census Bureau, land"),
    # 120 yd x 53.3 yd including end zones = 5,351 m²
    "football field": (0.005351, "a football field", "NFL rulebook dimensions"),
}

#: unit text -> km² per unit
_AREA_UNITS = (
    (re.compile(r"\b(km2|km²|sq\.? ?km|square kilomet)", re.I), 1.0),
    (re.compile(r"\bhectare", re.I), 0.01),
    (re.compile(r"\bacre", re.I), 0.0040468564),
    (re.compile(r"\b(sq\.? ?mi|square mile)", re.I), 2.589988),
)
_SCALE_WORDS = (("trillion", 1e12), ("billion", 1e9), ("million", 1e6),
                ("thousand", 1e3))


def to_km2(value: float, unit: str) -> float | None:
    """`value` in `unit` as km², or None when the unit is not an area."""
    u = str(unit or "")
    per = next((k for rx, k in _AREA_UNITS if rx.search(u)), None)
    if per is None:
        return None
    mult = next((m for w, m in _SCALE_WORDS if w in u.lower()), 1.0)
    return float(value) * mult * per


def phrase_for(km2: float, ref_km2: float, said: str) -> str | None:
    """The one true sentence fragment comparing `km2` with a reference."""
    if km2 <= 0 or ref_km2 <= 0:
        return None
    r = km2 / ref_km2
    if 1.0 <= r < 1.5:
        return f"bigger than {said}"
    if 0.85 <= r < 1.0:
        return f"almost the size of {said}"
    if 1.5 <= r <= 50:
        k = int(r)                     # floor: "more than k times" is true
        return f"more than {k} times the size of {said}"
    return None


def comparisons(values_units, limit: int = 4) -> list[dict]:
    """Every TRUE comparison for these (value, unit[, label]) rows, the
    closest fits first (a ratio near 1 reads better than "38 times
    Delaware"). A row whose label already names the reference is skipped —
    "France is bigger than France" is true and says nothing."""
    out, seen = [], set()
    for row in values_units:
        value, unit = row[0], row[1]
        label = str(row[2]).lower() if len(row) > 2 else ""
        km2 = to_km2(value, unit)
        if not km2:
            continue
        for name, (ref, said, src) in AREAS_KM2.items():
            ph = phrase_for(km2, ref, said)
            if name.lower() in label:
                continue
            if not ph or (value, name) in seen:
                continue
            seen.add((value, name))
            out.append({"phrase": ph, "name": name, "said": said,
                        "value": value, "unit": unit, "ratio": km2 / ref,
                        "label": row[2] if len(row) > 2 else "",
                        "source": src})
    out.sort(key=lambda c: abs(1.0 - c["ratio"]) if c["ratio"] < 1.5
             else 1 + c["ratio"] / 10)
    return out[:limit]
