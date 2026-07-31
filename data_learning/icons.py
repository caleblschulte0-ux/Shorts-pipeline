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
    # --- subjects the story forge actually produces (World Bank themes) ---
    (("mosquito", "malaria"), "1f99f"),
    (("virus", "disease", "infection", "immuniz", "vaccin"), "1f9a0"),
    (("pill", "medicine", "drug", "pharma"), "1f48a"),
    (("tree", "forest", "woodland"), "1f333"),
    (("crop", "farm", "arable", "agricultur", "cereal", "grain", "wheat"), "1f33e"),
    (("fishing", "capture fisheries", "trawler"), "1f3a3"),
    (("coral", "reef", "marine", "protected area"), "1fab8"),
    (("solar", "renewable"), "2600"),
    (("nuclear", "atom", "reactor"), "269b"),
    (("fossil", "coal", "oil", "petrol", "gas"), "1f6e2"),
    (("battery",), "1f50c"),
    (("internet", "broadband", "online", "web"), "1f310"),
    (("computer", "laptop", "research", "science", "lab"), "1f52c"),
    (("satellite", "space", "rocket", "launch"), "1f680"),
    (("toilet", "sanitation", "sewer"), "1f6bd"),
    (("drinking water", "freshwater", "tap"), "1f6b0"),
    (("rain", "precipitation"), "1f327"),
    (("city", "urban", "skyline"), "1f3d9"),
    (("village", "rural", "farmhouse"), "1f3e1"),
    (("people", "population", "crowd"), "1f465"),
    (("school", "classroom", "pupil", "literacy", "teacher"), "1f3eb"),
    (("book", "read"), "1f4d6"),
    (("factory", "industry", "manufactur", "emission"), "1f3ed"),
    (("smoke", "co2", "carbon", "greenhouse"), "1f4a8"),
    (("thermometer", "temperature", "heat"), "1f321"),
    (("glacier", "ice", "arctic", "snow"), "1f9ca"),
    (("plane travel", "tourism", "tourist", "passenger"), "1f9f3"),
    (("train", "rail"), "1f686"),
    (("ship", "port", "container"), "1f6a2"),
    (("road", "highway", "truck"), "1f6e3"),
    (("worker", "labor", "labour", "employ", "job"), "1f477"),
    (("heart", "cardiac", "blood"), "2764"),
    (("bone", "skeleton"), "1f9b4"),
    (("brain", "cognitive", "memory"), "1f9e0"),
    (("eye", "vision", "sight"), "1f441"),
    (("cow", "cattle", "livestock", "beef"), "1f404"),
    (("chicken", "poultry", "egg"), "1f414"),
    (("bee", "pollinat", "honey"), "1f41d"),
    (("waste", "trash", "garbage", "landfill"), "1f5d1"),
    (("clock", "time", "hour", "duration"), "23f0"),
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


_SVG_CDN = ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/"
            "{cp}.svg")


def icon_png(label: str, px: int = 512) -> Path | None:
    """A CRISP transparent graphic for `label` at `px`, or None.

    The 72x72 raster above is fine for a pictograph dot but turns to mush when
    it has to fill a full-frame strip, so this rasterises Twemoji's SVG at the
    size actually needed. This is the OFFLINE-safe path for scene subjects: the
    AI cutout provider (Pollinations) answers 500/429 often enough that scenes
    were silently degrading to empty chart frames, which the review gate
    correctly blocks as "the data is stated, not demonstrated".
    """
    cp = emoji_codepoint(label)
    if not cp:
        return None
    px = max(64, min(1024, int(px)))
    dest = CACHE / f"{cp}-{px}.png"
    if dest.exists() and dest.stat().st_size > 400:
        return dest
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            _SVG_CDN.format(cp=cp),
            headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            svg = r.read()
        if len(svg) < 80:
            raise ValueError("empty svg")
        import cairosvg
        cairosvg.svg2png(bytestring=svg, write_to=str(dest),
                         output_width=px, output_height=px)
        return dest if dest.stat().st_size > 400 else None
    except Exception:  # noqa: BLE001 — fall back to the 72px raster
        return icon_for(label)
