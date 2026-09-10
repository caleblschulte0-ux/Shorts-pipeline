"""series_icons — resolve a small square ICON for a named data series.

Top-of-funnel media capability (docs/PIPELINE_LAYOUT.md): any channel that
draws a chart, leaderboard, race, or comparison can ask for "the icon that
means USA / Netflix / SpaceX" and get a local PNG path back. Charts read
instantly when every line carries a recognisable mark instead of only a
colour the viewer has to map back to a legend.

Resolution order (all keyless, all cached under cache/series_icons/):
  1. explicit `http(s)://` URL in the spec       — the author knows best
  2. flag: 2-letter country code or a 🇺🇸-style flag emoji  -> flagcdn.com
  3. a known-country NAME ("United States", "China")        -> flagcdn.com
  4. anything else (brand, company, org) -> LOGO ONLY: Commons file
     search for "<name> logo", then Wikipedia's infobox image, each kept
     only if the filename reads as a mark (logo/wordmark/icon/.svg).
     News photos are deliberately NOT used — a press shot of a founder
     is worse than initials, because a face doesn't say the brand.

Returns None when nothing resolves — callers MUST have an offline visual
fallback (engines.chart_race draws an initials badge). Never raises.

    from funnel import series_icons
    p = series_icons.resolve("Netflix")          # -> Path | None
    p = series_icons.resolve("US", kind="flag")  # -> Path | None
"""
from __future__ import annotations

import re
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "series_icons"
FLAG_URL = "https://flagcdn.com/w160/{cc}.png"

# Only the countries that actually show up in "by country" chart data. A
# miss here is not fatal: the name falls through to entity_media, which
# resolves most country names via Wikipedia anyway.
_COUNTRY_CC = {
    "united states": "us", "united states of america": "us", "usa": "us",
    "us": "us", "america": "us",
    "united kingdom": "gb", "uk": "gb", "britain": "gb",
    "great britain": "gb", "england": "gb",
    "china": "cn", "india": "in", "japan": "jp", "germany": "de",
    "france": "fr", "italy": "it", "spain": "es", "portugal": "pt",
    "netherlands": "nl", "belgium": "be", "switzerland": "ch",
    "austria": "at", "sweden": "se", "norway": "no", "denmark": "dk",
    "finland": "fi", "iceland": "is", "ireland": "ie", "poland": "pl",
    "ukraine": "ua", "russia": "ru", "turkey": "tr", "greece": "gr",
    "canada": "ca", "mexico": "mx", "brazil": "br", "argentina": "ar",
    "chile": "cl", "colombia": "co", "peru": "pe",
    "australia": "au", "new zealand": "nz",
    "south korea": "kr", "korea": "kr", "north korea": "kp",
    "indonesia": "id", "philippines": "ph", "vietnam": "vn",
    "thailand": "th", "malaysia": "my", "singapore": "sg",
    "pakistan": "pk", "bangladesh": "bd", "iran": "ir", "iraq": "iq",
    "israel": "il", "saudi arabia": "sa",
    "united arab emirates": "ae", "uae": "ae", "qatar": "qa",
    "egypt": "eg", "nigeria": "ng", "kenya": "ke", "ethiopia": "et",
    "south africa": "za", "morocco": "ma", "algeria": "dz",
    "czechia": "cz", "czech republic": "cz", "hungary": "hu",
    "romania": "ro", "bulgaria": "bg", "croatia": "hr", "serbia": "rs",
    "taiwan": "tw", "hong kong": "hk",
}


def _slug(s: str) -> str:
    ascii_s = unicodedata.normalize("NFKD", s).encode("ascii",
                                                     "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_s.lower()).strip("-")[:60]
    # Emoji/CJK specs slugify to "" — hash instead of collapsing every one
    # of them onto a single shared cache file.
    if not slug:
        import hashlib
        slug = "x" + hashlib.sha1(s.encode()).hexdigest()[:12]
    return slug


def _flag_emoji_to_cc(s: str) -> str | None:
    """🇺🇸 -> 'us'. Regional-indicator pairs only."""
    cps = [ord(c) for c in s.strip() if ord(c) >= 0x1F1E6]
    if len(cps) == 2 and all(0x1F1E6 <= c <= 0x1F1FF for c in cps):
        return "".join(chr(c - 0x1F1E6 + ord("a")) for c in cps)
    return None


def _country_code(name: str) -> str | None:
    n = " ".join(name.strip().lower().split())
    cc = _flag_emoji_to_cc(name)
    if cc:
        return cc
    if len(n) == 2 and n.isalpha() and n in set(_COUNTRY_CC.values()):
        return n
    return _COUNTRY_CC.get(n)


def _download(url: str, out: Path) -> Path | None:
    from funnel import topic_media
    try:
        raw = topic_media._get(url)
    except Exception as e:  # noqa: BLE001
        print(f"  [series_icons] fetch failed {url}: {type(e).__name__}: {e}")
        return None
    # No meaningful size floor: a 3-bar flag (ru, de) is a legitimate
    # ~120-byte PNG. The PIL decode below is the real validator — HTML
    # error pages and truncated bodies fail it.
    if len(raw) < 40:
        return None
    tmp = out.with_suffix(".part")
    try:
        tmp.write_bytes(raw)
        # normalise to a square-ish RGBA png so callers never juggle formats
        from PIL import Image
        with Image.open(tmp) as im:
            im = im.convert("RGBA")
            im.thumbnail((160, 160))
            im.save(out, "PNG")
    except Exception as e:  # noqa: BLE001
        print(f"  [series_icons] decode failed {url}: {type(e).__name__}: {e}")
        return None
    finally:
        tmp.unlink(missing_ok=True)
    return out if out.exists() else None


#: Words a MARK's filename carries that say nothing about whose mark it is.
#: Stripped before the ownership check below, along with pure numbers (a
#: year or a size in "Airbus logo 2017.svg" / "Boeing logo 200px.png").
_MARK_WORDS = {
    "logo", "logos", "wordmark", "icon", "emblem", "symbol", "brandmark",
    "crest", "seal", "svg", "png", "jpg", "jpeg", "webp", "thumb", "file",
    "the", "of", "a", "an", "and", "new", "old", "current", "official",
    "vector", "colour", "color", "black", "white", "dark", "light", "flat",
    "transparent", "background", "bg", "square", "circle", "horizontal",
    "vertical", "rgb", "cmyk", "full", "text", "type", "mark", "sign",
    # Corporate suffixes belong to the NAME, not to a different owner:
    # "Visa Inc. logo.svg" is Visa's mark, and refusing it would trade the
    # false positive this function exists to stop for a false negative.
    "inc", "corp", "corporation", "co", "company", "ltd", "limited", "llc",
    "plc", "sa", "ag", "gmbh", "nv", "ab", "as", "oy", "spa", "srl", "pty",
    "group", "holdings", "international", "worldwide", "global",
    # A country's flag or arms IS its mark. ("Flag of Mexico" is still
    # refused for "United States" — it shares no token with the request and
    # never reaches the leftover test.)
    "flag", "flags", "ensign", "banner", "coat", "arms", "nation",
    "national", "state", "republic", "kingdom",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _is_about(url: str, name: str) -> bool:
    """Does this file depict THE THING ASKED FOR, or something else whose
    name merely contains it?

    THIS IS THE `junk_imagery` BUG, AND IT WAS FATAL.

    2026-09-10, "Bitcoin Closed The Gap On Gold" — showrunner BLOCK, the
    one auto-fail that blocks at any score:

        "The 'Gold' series icon is the VTM GOLD television-channel logo
         (a Belgian broadcaster's brand mark), sitting in the legend and
         riding the line tip in EVERY frame."

    `_brand_logo_url("Gold")` full-text searches Commons for "Gold logo",
    Commons returns `VTM GOLD logo.svg`, and `_looks_like_logo` approves it
    because the filename contains "logo" and ".svg". Both of those are true
    and neither is the question. The question is WHOSE logo, and nothing
    asked it — a fuzzy search with no verification, which is the same shape
    as the silent-default lookups CLAUDE.md already has a rule about.

    A containment test does not fix it: "vtm gold logo.svg" does contain
    "gold". What separates them is the LEFTOVER — a token that is neither
    the thing asked for, nor a generic mark word, nor a number:

        "Boeing logo.svg"        tokens {boeing, logo, svg}  leftover {}
        "Airbus Logo 2017.png"   ... {airbus, logo, 2017}    leftover {}
        "VTM GOLD logo.svg"      ... {vtm, gold, logo, svg}  leftover {vtm}

    A leftover content word means the mark belongs to somebody else, so it
    is refused and the caller draws its initials badge — which is exactly
    what the docstring at the top of this module already promises.
    """
    want = {t for t in _tokens(name) if t not in _MARK_WORDS}
    if not want:
        return False
    fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    got = _tokens(fname)
    if not want & set(got):
        return False                      # does not mention it at all
    leftover = [t for t in got
                if t not in want and t not in _MARK_WORDS and not t.isdigit()]
    return not leftover


def _looks_like_logo(url: str) -> bool:
    """Filename heuristic. An icon must READ as the brand at 30px, so a
    photograph never qualifies — a press shot of a company's founder is
    worse than initials, because the viewer has to decode a face."""
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]).lower()
    if any(w in name for w in ("logo", "wordmark", "icon", "emblem",
                               "symbol", "brandmark", "crest", "seal")):
        return True
    # SVG-derived PNGs on Commons are almost always marks, not photos
    return ".svg" in name


def _brand_logo_url(name: str) -> str | None:
    """A LOGO for a brand/company/org — never a news photo. Commons file
    search first (its filenames say what the image is), then Wikipedia's
    infobox image, which for a company is normally the wordmark."""
    from funnel import topic_media
    try:
        for u in topic_media._commons_files(f"{name} logo", limit=5):
            if _looks_like_logo(u) and _is_about(u, name):
                return u
    except Exception as e:  # noqa: BLE001
        print(f"  [series_icons] commons logo search failed {name!r}: {e}")
    try:
        u = topic_media._wikipedia_image(name)
        if u and _looks_like_logo(u) and _is_about(u, name):
            return u
    except Exception as e:  # noqa: BLE001
        print(f"  [series_icons] wikipedia image failed {name!r}: {e}")
    print(f"  [series_icons] no logo for {name!r} — initials badge")
    return None


def resolve(name: str, *, icon: str | None = None, kind: str | None = None,
            context: str = "") -> Path | None:
    """Best-effort local PNG for a series. `icon` overrides `name`
    (a URL, a country code, a flag emoji, or an alternate search term);
    `kind="flag"` forces flag lookup and skips the entity search."""
    spec = (icon or name or "").strip()
    if not spec:
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{_slug(spec)}.png"
    if out.exists():
        return out

    if spec.startswith(("http://", "https://")):
        return _download(spec, out)

    cc = _country_code(spec)
    if cc:
        return _download(FLAG_URL.format(cc=cc), out)
    if kind == "flag":
        return None

    url = _brand_logo_url(spec)
    if not url:
        return None
    try:
        from funnel import entity_media
        url = entity_media.commons_thumb_url(url, width=160)
    except Exception:  # noqa: BLE001
        pass
    return _download(url, out)


def resolve_many(series: list[dict], context: str = "") -> dict[str, Path]:
    """Resolve icons for a chart's series list. Each item may carry
    "icon" (URL / country code / flag emoji / search term) and "icon_kind".
    Missing/failed lookups are simply absent from the returned map."""
    out: dict[str, Path] = {}
    for s in series:
        name = s.get("name", "")
        p = resolve(name, icon=s.get("icon"), kind=s.get("icon_kind"),
                    context=context)
        if p is not None:
            out[name] = p
    return out


if __name__ == "__main__":
    import sys
    for q in sys.argv[1:] or ["United States", "Netflix", "🇯🇵"]:
        print(f"{q!r} -> {resolve(q)}")
