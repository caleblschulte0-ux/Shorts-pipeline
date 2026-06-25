"""Map a data label to a real graphic (emoji art) so charts SYMBOLIZE the data —
a dog/cat/house/etc. instead of an abstract dot. Used by the pictograph viz.

Graphics are Twemoji PNGs (CC-BY, transparent) fetched on demand from a CDN and
cached under state/icons/. Best-effort: no match or no network -> returns None
and the caller falls back to plain dots, so a render never breaks.
"""
from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "state" / "icons"
_CDN = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{cp}.png"

# (keyword substrings) -> twemoji codepoint. First match wins, so put the more
# specific concepts before the generic money/category ones.
_MAP: list[tuple[tuple[str, ...], str]] = [
    (("daycare", "infant", "toddler", "child", "kid"), "1f9d2"),   # child
    (("baby", "birth", "newborn", "maternity"), "1f476"),          # baby
    (("dog", "puppy"), "1f415"),
    (("cat", "kitten"), "1f408"),
    (("bird",), "1f426"),
    (("fish",), "1f41f"),
    (("pet",), "1f43e"),                                           # paw prints
    (("wedding", "marriage", "bride", "groom", "engage"), "1f48d"),  # ring
    (("rent", "mortgage", "home", "house", "housing"), "1f3e0"),
    (("venue",), "1f3db"),                                         # classical bldg
    (("cater", "grocery", "food", "meal"), "1f37d"),
    (("flower", "floral"), "1f490"),
    (("dress", "gown"), "1f457"),
    (("photo",), "1f4f8"),
    (("band", "dj", "music", "concert", "ticket", "tour"), "1f3b5"),
    (("chocolate", "cocoa", "candy"), "1f36b"),
    (("coffee", "caffeine", "espresso"), "2615"),
    (("flight", "plane", "airline", "air travel", "aviation"), "2708"),
    (("car", "auto", "vehicle", "ev"), "1f697"),
    (("college", "tuition", "student", "university", "degree"), "1f393"),
    (("insurance", "hospital", "health", "medical", "premium"), "1f3e5"),
    (("wildfire", "fire"), "1f525"),
    (("phone", "screen", "smartphone", "social"), "1f4f1"),
    (("ocean", "water", "sea"), "1f30a"),
    (("sleep",), "1f634"),
    (("energy", "power", "electric"), "26a1"),
    (("pig",), "1f437"),
    # generic money/value — last resort so specific subjects win first.
    (("cost", "price", "spend", "wage", "income", "savings", "debt",
      "dollar", "money", "pay", "salary"), "1f4b5"),
]


def emoji_codepoint(label: str) -> str | None:
    s = (label or "").lower()
    for keys, cp in _MAP:
        if any(k in s for k in keys):
            return cp
    return None


def icon_for(label: str) -> Path | None:
    """Return a cached transparent PNG graphic for `label`, or None."""
    cp = emoji_codepoint(label)
    if not cp:
        return None
    dest = CACHE / f"{cp}.png"
    if dest.exists() and dest.stat().st_size > 200:
        return dest
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        ctx = ssl.create_default_context()
        req = urllib.request.Request(_CDN.format(cp=cp),
                                     headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            data = r.read()
        if len(data) < 200:
            return None
        dest.write_bytes(data)
        return dest
    except Exception:  # noqa: BLE001 — no network / bad fetch -> caller uses dots
        return None
