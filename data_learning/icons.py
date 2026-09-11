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
    # EARTH. A data channel names it constantly — six scene subjects in the
    # config say "earth from space" or "planet in space" — and it was in no
    # table at all, so the only word that DID resolve was "space" and every
    # one of them opened on a cartoon ROCKET. An absent entry is not a
    # neutral: it hands the picture to whatever else in the phrase happens
    # to be listed. (`_SETTING` now stops the modifier deciding; this makes
    # sure the subject itself has an answer.)
    (("earth", "globe", "planet", "world map", "the world",
      "continent", "continents"), "1f30d"),
    (("antarctica", "antarctic", "arctic", "glacier", "iceberg",
      "polar"), "1f9ca"),
    (("daycare", "infant", "toddler", "child", "children", "kid"), "1f9d2"),
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
    # THE CAMERA ROW IS GONE. Its only key was "photo", so it existed to say
    # "if the label mentions a photograph, draw a camera" — and 35 of the 384
    # scene subjects in the config end in "photo" as a STYLE note ("bank vault
    # door photo", "erupting volcano lava photo", "cavendish banana photo").
    # All thirty-five drew a camera emoji. A camera is never the subject of a
    # data story; the word is stripped by `_MEDIUM` now, and there is no row
    # left for it to win.
    (("band", "dj", "music", "concert", "ticket", "tour"), "1f3b5"),
    (("chocolate", "cocoa", "candy"), "1f36b"),
    (("coffee", "caffeine", "espresso"), "2615"),
    (("flight", "plane", "airline", "air travel", "aviation"), "2708"),
    (("car", "auto", "vehicle", "ev"), "1f697"),
    (("college", "tuition", "student", "university", "degree"), "1f393"),
    (("insurance", "hospital", "health", "healthcare", "medical",
      "premium"), "1f3e5"),
    (("wildfire", "fire"), "1f525"),
    (("phone", "screen", "smartphone", "social"), "1f4f1"),
    # Before the generic water key: "drinking water" was a breaking WAVE.
    (("drinking water", "freshwater", "tap"), "1f6b0"),
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
    (("fossil", "coal", "oil", "petrol", "gas", "gasoline"), "1f6e2"),
    (("battery",), "1f50c"),
    (("internet", "broadband", "online", "web", "website"), "1f310"),
    (("computer", "laptop", "research", "science", "lab"), "1f52c"),
    # A SATELLITE IS NOT A ROCKET. It shared the rocket's row, so every
    # satellite, space station and satellite map in the config launched.
    (("satellite", "space station", "orbiter"), "1f6f0"),
    (("space", "rocket", "launch", "spacecraft"), "1f680"),
    (("toilet", "sanitation", "sewer"), "1f6bd"),
    (("rain", "precipitation"), "1f327"),
    (("city", "cities", "urban", "skyline"), "1f3d9"),
    (("village", "rural", "farmhouse"), "1f3e1"),
    (("people", "population", "crowd"), "1f465"),
    (("school", "classroom", "pupil", "literacy", "teacher"), "1f3eb"),
    (("book", "read"), "1f4d6"),
    (("factory", "industry", "manufactur", "emission"), "1f3ed"),
    (("smoke", "co2", "carbon", "greenhouse"), "1f4a8"),
    (("thermometer", "temperature", "heat"), "1f321"),
    (("glacier", "ice", "arctic", "snow"), "1f9ca"),
    # Before the generic passenger key: "rail passengers" is a TRAIN.
    (("train", "rail", "railway", "railroad"), "1f686"),
    (("plane travel", "tourism", "tourist", "passenger"), "1f9f3"),
    (("ship", "shipping", "port", "container"), "1f6a2"),
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


# A key matches a WORD, not a run of letters anywhere inside one.
#
# The old rule was `k in label.lower()`, and the showrunner's FATAL
# `junk_imagery` check spent a week telling us what that costs:
#
#   2026-09-02..09  f1-pit-stop-vanishing-act, SIX blocked renders
#       "a cartoon HOUSE icon sits on the 'Current record' bar"
#       — cur-RENT-record, matched against the housing key
#   2026-09-09      melatonin-kids-er-surge
#       "a red CAR clip-art sits on the 'Intensive care' row ... it fully
#        covers the 1% value it is meant to annotate"
#       — CAR-e, matched against the vehicle key
#
# `junk_imagery` is the ONE fatal check: it blocks at any score, on any
# policy, because mismatched imagery is a trust defect rather than a craft
# one. So every one of those was a video that did not post, from a substring
# collision nobody could see in the code.
#
# The same rule was quietly mislabelling plenty more: "tourism" -> music (via
# "tour"), "coalition" -> an oil pipe (via "coal"), "Costa Rica" -> a banknote
# (via "cost"), "kidney" -> a child (via "kid"), "beef" -> a bee. And `"ev"`
# for electric vehicles matched every "level", "seven", "revenue" and
# "development" in the catalogue.
#
# So: a key must be a PREFIX OF A WHOLE TOKEN, and what is left over after it
# has to be a plain inflection — unless the key is a deliberate stem, of which
# there are several ("vaccin", "immuniz", "agricultur", "manufactur",
# "pollinat", "employ"). Six characters is the line between the two; every
# stem in the table is at least that long and every collision above came from
# a key of four or fewer.
_WORD = __import__("re").compile(r"[a-z0-9]+")
# No bare "d": it turns "card" into "car", which is the exact defect this
# rule exists to stop.
_INFLECT = ("", "s", "es", "ed", "ing")
_STEM_LEN = 6


def _token_matches(token: str, key: str) -> bool:
    if not token.startswith(key):
        return False
    rest = token[len(key):]
    return not rest or len(key) >= _STEM_LEN or rest in _INFLECT


def _phrase_matches(tokens: list[str], key: str) -> bool:
    """A multi-word key ("drinking water") matches consecutive tokens."""
    parts = _WORD.findall(key)
    if not parts:
        return False
    for i in range(len(tokens) - len(parts) + 1):
        if all(_token_matches(tokens[i + j], parts[j])
               for j in range(len(parts))):
            return True
    return False


#: Words that name the MEDIUM, never the subject. Five scene subjects in the
#: config end in "photo" — "stack of cash bills photo", "pile of sand mound
#: photo" — and every one of them resolved to a CAMERA. The same shape as the
#: `VTM GOLD logo.svg` bug in `funnel/series_icons`: a word that describes the
#: FILE was allowed to decide the picture.
_MEDIUM = {
    "photo", "photos", "photograph", "image", "images", "picture", "pic",
    "illustration", "render", "rendering", "shot", "closeup", "stock",
    "footage", "graphic", "artwork", "art", "icon", "png", "jpg", "jpeg",
    "view", "angle", "background", "backdrop", "scene", "styled", "style",
}

#: After one of these the phrase describes the SETTING, not the subject.
#:
#: "earth from space" resolved to a ROCKET — `earth` is in no table, `space`
#: is, and nothing said the modifier may not decide the picture. It opened
#: the ozone video: eight seconds of cartoon rocket, a quarter of the runtime,
#: on the beat that decides whether anyone watches. Four more subjects in the
#: config say "in space" or "from space" and all four got the same rocket.
#:
#: `of`, `and` and `with` are deliberately NOT here: those are partitive or
#: compound, and the real subject usually FOLLOWS them — "stack of dollar
#: bills" wants the dollars, "pile of coal" wants the coal.
_SETTING = {
    "from", "in", "on", "over", "under", "against", "behind", "above",
    "below", "near", "beside", "across", "inside", "outside",
    "around", "beneath", "atop", "amid", "between", "before", "after",
    "during", "onto", "within", "beyond", "toward", "towards",
}
#: `at` and `through` were here and cost two GOOD matches — "staring at
#: ringing phone" (the phone is exactly the subject) and "trail through
#: forest" (a tree is a fair stand-in for a forest trail). Measured over the
#: 384 scene subjects in the config, they were the only two words in the set
#: that removed more signal than noise, so they are deliberately out.


def _subject_tokens(label: str) -> list:
    """The part of `label` that names WHAT IS BEING SHOWN.

    A picture is chosen from the subject, not from the medium it is delivered
    in and not from the place it happens to be. Both of those were deciding
    pictures that shipped.
    """
    toks = [t for t in _WORD.findall((label or "").lower())
            if t not in _MEDIUM]
    for i, t in enumerate(toks):
        if t in _SETTING:
            return toks[:i]
    return toks


def emoji_codepoint(label: str) -> str | None:
    tokens = _subject_tokens(label)
    if not tokens:
        return None
    for keys, cp in _MAP:
        for k in keys:
            if _phrase_matches(tokens, k):
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
