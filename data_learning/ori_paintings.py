"""Real paintings in the sleep films, with the camera dead still.

The operator, 2026-10-01, on the Greek film ("3/10 AI slop"): "throw in some"
real paintings, and asked of his standing ruling against camera movement
whether a painting may glide: "Keep the camera dead still". So a painting
holds the frame whole and still, and what moves is REAL: dust drifting
through the lamplight in front of it and the warm light itself breathing,
the way a painting looks in a dim room. Nothing pans, zooms or wobbles.

Where they come from: the public-domain collections of the Art Institute
of Chicago and the Metropolitan Museum of Art, both free and keyless, and
both flagging each work's public-domain status, which is the only status
accepted here. A painting is chosen for a passage only when the words of
its TITLE are in the passage's words (a symposium for a symposium, a
harbour for a harbour), at most one a chapter, so a film is "some"
paintings and not a slideshow. Every one is credited in the description.

    python -m data_learning.ori_paintings search "greek symposium"
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "cache" / "paintings"
UA = "OpenRangeInteractive-sleep-films/1.0 (public-domain artwork, credited)"
W, H = 1920, 1080
MIN_WIDTH = 900               # smaller than this is a thumbnail, not a picture
PER_CHAPTER = 1               # "throw in some": at most one painting a chapter
KINDS = ("painting", "print", "drawing", "watercolor")

# what to call each era when asking a museum
ERA_QUERY = {"stone_age": "prehistoric", "ancient": "ancient", "egypt": "Egypt",
             "medieval": "medieval", "early_modern": "Elizabethan sixteenth century",
             "victorian": "Victorian nineteenth century"}

STOP = set("""a an the and or but of to in on at by for with from into onto over under as is are was were be
been being it its this that these those you your yours he she they them their his her we our us i me my
there here then than so very just still now once again all some any each every one two three few more most
other another such no not nor only own same too can will would should could may might must do does did
done have has had having up down out off through across around about between before after while when where
which who whom what why how long little last first night evening dark day low soft slow quiet""".split())


def _get(url: str, timeout: float = 25.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "AIC-User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def words(text: str) -> set:
    """Content words, singular."""
    out = set()
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) < 4 or w in STOP:
            continue
        w = SPELL.get(w, w)
        out.add(w[:-1] if w.endswith("s") and not w.endswith("ss") else w)
    return out


SPELL = {"harbour": "harbor", "harbours": "harbors", "colour": "color", "neighbour": "neighbor",
         "theatre": "theater", "grey": "gray", "lantern": "lamp", "lamps": "lamp"}


# ------------------------------------------------------------------ search
def _aic(query: str, n: int) -> list[dict]:
    q = urllib.parse.quote(query)
    url = (f"https://api.artic.edu/api/v1/artworks/search?q={q}&limit={n}"
           "&query[term][is_public_domain]=true"
           "&fields=id,title,image_id,artist_title,artist_display,date_display,artwork_type_title,"
           "is_public_domain,thumbnail")
    data = json.loads(_get(url.replace("[", "%5B").replace("]", "%5D")))
    out = []
    for d in data.get("data") or []:
        kind = (d.get("artwork_type_title") or "").lower()
        width = ((d.get("thumbnail") or {}).get("width")) or 0
        if not d.get("is_public_domain") or not d.get("image_id") or not any(k in kind for k in KINDS):
            continue
        if width and width < MIN_WIDTH:
            continue
        out.append(dict(source="Art Institute of Chicago", id=f"aic:{d['id']}", title=d.get("title") or "",
                        artist=d.get("artist_title") or (d.get("artist_display") or "").split("\n")[0],
                        made=(d.get("artist_display") or "").replace("\n", " "),
                        date=d.get("date_display") or "", kind=kind, license="public domain",
                        image_url=f"https://www.artic.edu/iiif/2/{d['image_id']}/full/1686,/0/default.jpg",
                        page=f"https://www.artic.edu/artworks/{d['id']}"))
    return out


def _met(query: str, n: int) -> list[dict]:
    q = urllib.parse.quote(query)
    ids = (json.loads(_get(f"https://collectionapi.metmuseum.org/public/collection/v1.1/search?hasImages=true"
                           f"&isPublicDomain=true&q={q}&limit={n}")) or {}).get("objectIDs") or []
    out = []
    for oid in ids[:min(n, 6)]:
        try:
            d = json.loads(_get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}"))
        except Exception:                       # noqa: BLE001 — one object failing is not the search failing
            continue
        kind = (d.get("classification") or d.get("objectName") or "").lower()
        if not d.get("isPublicDomain") or not d.get("primaryImage") or not any(k in kind for k in KINDS):
            continue
        out.append(dict(source="The Metropolitan Museum of Art", id=f"met:{oid}", title=d.get("title") or "",
                        artist=d.get("artistDisplayName") or "", date=d.get("objectDate") or "", kind=kind,
                        made=" ".join(x for x in (d.get("artistNationality"), d.get("culture"), d.get("country"))
                                      if x),
                        license="public domain (Met Open Access)", image_url=d["primaryImage"],
                        page=d.get("objectURL") or ""))
    return out


def search(query: str, n: int = 15) -> list[dict]:
    """Public-domain paintings, prints and drawings for a query, from both
    museums. Never raises: a museum that does not answer adds nothing."""
    out = []
    for fn in (_aic, _met):
        try:
            out += fn(query, n)
        except Exception as e:                  # noqa: BLE001
            print(f"[ori_paintings] {fn.__name__} {query!r}: {e}", file=sys.stderr, flush=True)
    return out


# the era a painting must SHOW: by the year it was made for the eras the
# museums hold paintings from, by the words of its title for the ones they
# can only show through later eyes (a Victorian painting of a Greek supper)
ERA_YEARS = {"victorian": (1830, 1905), "early_modern": (1540, 1700), "medieval": (1000, 1500)}
# words that mean the ANCIENT world, not a modern place: "Greek Lovers"
# (1825) is the War of Independence, in the costume of its own day
ERA_TITLE = {"ancient": ("ancient", "antique", "antiquity", "pompeii", "socrates", "sappho", "plato",
                         "symposium", "acropolis", "parthenon", "vestal", "gladiator", "toga", "athenian",
                         "spartan", "homer", "odysseus", "achilles", "trojan", "troy", "delphi", "olympia",
                         "caesar", "augustus", "roman banquet", "roman bath", "greek temple", "roman temple"),
             "egypt": ("egypt", "egyptian", "nile", "pharaoh", "pyramid", "thebes", "luxor", "karnak"),
             "stone_age": ("prehistoric", "cave", "mammoth", "stone age"),
             "medieval": ("medieval", "middle ages", "castle", "knight", "monk", "abbey")}


def year(p: dict) -> int | None:
    m = re.search(r"(\d{3,4})", p.get("date") or "")
    return int(m.group(1)) if m else None


# the eras that are a PLACE as well as a time: a Victorian or Elizabethan
# film is London, and a Monet of Argenteuil is the right year in France
ERA_PLACE = {"victorian": ("english", "british", "london", "england", "scottish", "thames", "welsh"),
             "early_modern": ("english", "british", "london", "england", "elizabeth", "tudor", "scottish")}


def era_ok(p: dict, era: str) -> bool:
    """Whether a painting shows the film's era: a Maine harbour painted in
    1877 is a harbour, and it is not a Greek one."""
    title = (p.get("title") or "").lower()
    if any(w in title for w in ERA_TITLE.get(era, ())):
        return True
    span = ERA_YEARS.get(era)
    y = year(p)
    if not (span and y and span[0] <= y <= span[1]):
        return False
    place = ERA_PLACE.get(era)
    return not place or any(w in (title + " " + (p.get("made") or "").lower()) for w in place)


# a sleep film is after dark: a painting is a night scene, or a subject that
# belongs to the evening indoors. A sunlit landscape answers "the river" and
# contradicts "the river moves dark under the moon"
NIGHT = ("night", "moon", "evening", "nocturne", "twilight", "dusk", "candle", "lamplight", "firelight",
         "sunset", "dark")
EVENING_SUBJECTS = set(words("""symposium banquet feast supper dinner meal lamp candle hearth loom weaving
spinning cradle sleep sleeping bed tavern inn music lyre story storyteller kitchen"""))


def after_dark(p: dict) -> bool:
    title = (p.get("title") or "").lower()
    return any(w in title for w in NIGHT) or bool(words(title) & EVENING_SUBJECTS)


# a sleep film is calm and for everyone: a title naming nudity or violence
# is refused whatever it matches (the museums do not flag either)
REFUSE = ("nude", "naked", "venus", "bather", "bathing", "leda", "satyr", "bacchan", "rape", "abduct",
          "death", "dead", "dying", "murder", "massacre", "battle", "war ", "execution", "martyr", "crucif",
          "slaughter", "sacrifice", "drunk", "orgy", "skull", "plague", "torment", "hell")


def suitable(p: dict) -> bool:
    t = " " + (p.get("title") or "").lower() + " "
    return not any(w in t for w in REFUSE)


def score(p: dict, passage: str) -> float:
    """How well a painting's TITLE says what the passage says: nothing
    unless a SUBJECT (a symposium, a harbour, a loom) is in both, then one
    point per shared subject and a little for each other shared word."""
    # era words say WHEN, not what: "ancient" is no match for a passage, but
    # "symposium" is, era word or not
    tw = words(p.get("title", "")) - ({w for ws in ERA_TITLE.values() for w in ws} - SUBJECTS)
    pw = words(passage)
    subj = tw & pw & SUBJECTS
    if not subj:
        return 0.0
    return len(subj) + 0.2 * len((tw & pw) - SUBJECTS)


# what a painting can be OF: concrete scenes and things. Asked for by these
# words only ("small", "light" and "rather" found a penitent saint)
SUBJECTS = set(words("""symposium banquet feast supper dinner meal bread wine harbor port ship boat sailor
fisherman fishing net market stall merchant temple altar prayer priest festival procession loom weaving
spinning spindle wool lamp candle hearth fire kitchen cook stars moon river stream olive vineyard grape
harvest shepherd sheep goat cattle cow farmer plough field garden courtyard fountain well street tavern inn
theater actor music lyre flute dance dancer story storyteller philosopher scholar school lesson child mother
family cradle sleep sleeping bed night watchman guard soldier gate wall city village cottage house castle
monastery monk bath baths forum chariot horse camel nile pyramid desert sunset evening twilight moonlight
lantern torch kitchen bakery baker blacksmith potter pottery mill sailing boatman ferry bridge"""))


def _subjects(passages: list[str], title: str = "", k: int = 4) -> list[str]:
    """A chapter's subjects to ask a museum for: the concrete ones its title
    names first, then the ones its passages repeat most."""
    import collections
    n = collections.Counter(w for p in passages for w in words(p) if w in SUBJECTS)
    first = [w for w in words(title) if w in SUBJECTS]
    rest = [w for w, _c in n.most_common() if w not in first]
    return (first + rest)[:k]


def pick_for_film(ep: dict, search_fn=search, log=print, threshold: float = 1.0) -> int:
    """Give up to PER_CHAPTER passages a chapter a matching painting
    (beat["painting"]). A few searches a chapter, each asked once, every
    result scored against every passage: a chapter with nothing that
    matches well keeps its drawings. Returns how many were chosen."""
    era = ep.get("era", "")
    era_q = ERA_QUERY.get(era, "")
    used = {b["painting"]["id"] for c in ep.get("chapters") or [] for b in c.get("beats") or []
            if isinstance(b, dict) and isinstance(b.get("painting"), dict)}
    asked: dict = {}
    chosen = 0
    for ci, ch in enumerate(ep.get("chapters") or []):
        beats = [b for b in ch.get("beats") or [] if isinstance(b, dict)]
        if any(b.get("painting") for b in beats):
            continue
        found = []
        for subj in _subjects([b.get("say", "") for b in beats], ch.get("title", "")):
            # the subject alone, then at night: "symposium ancient" found
            # nothing where "symposium" found Plato's
            for q in (subj, f"{subj} night"):
                if q not in asked:
                    asked[q] = [p for p in search_fn(q, 10) if era_ok(p, era) and suitable(p) and after_dark(p)]
                found += [p for p in asked[q] if p["id"] not in {x["id"] for x in found}]
        best = None
        for bi, b in enumerate(beats):
            if ci == 0 and bi == 0:
                continue                    # the opening keeps its drawn establishing shot
            for p in found:
                if p["id"] in used:
                    continue
                # the chapter's title is part of what a passage is about:
                # "The Men's Symposium" never says the word in its passages
                sc = score(p, b.get("say", "") + " " + ch.get("title", "")) + 0.01 * score(p, b.get("say", ""))
                if sc >= threshold and (best is None or sc > best[0]):
                    best = (sc, bi, p)
        if best:
            _sc, bi, p = best
            beats[bi]["painting"] = p
            used.add(p["id"])
            chosen += 1
            log(f"[ori_paintings] chapter {ci + 1} beat {bi + 1}: {p['title']!r} ({p['artist'] or 'unknown'}, "
                f"{p['source']}), score {_sc:.1f}")
    return chosen


def credits(ep: dict) -> str:
    """The description's credit lines for the paintings a film shows."""
    lines = []
    for c in ep.get("chapters") or []:
        for b in c.get("beats") or []:
            p = b.get("painting") if isinstance(b, dict) else None
            if isinstance(p, dict):
                who = f", {p['artist']}" if p.get("artist") else ""
                when = f", {p['date']}" if p.get("date") else ""
                lines.append(f"- {p['title']}{who}{when}. {p['source']}, {p.get('license', 'public domain')}.")
    return ("Paintings:\n" + "\n".join(lines)) if lines else ""


# ------------------------------------------------------------------ pictures
def fetch(p: dict, cache: Path = CACHE) -> Path | None:
    """The painting's image on disk (cached by id), or None."""
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / (re.sub(r"[^a-z0-9]+", "_", p["id"].lower()) + ".jpg")
    if out.exists() and out.stat().st_size > 10_000:
        return out
    try:
        out.write_bytes(_get(p["image_url"], timeout=60))
        return out if out.stat().st_size > 10_000 else None
    except Exception as e:                      # noqa: BLE001
        print(f"[ori_paintings] fetch {p.get('id')}: {e}", file=sys.stderr, flush=True)
        return None


class PaintingScene:
    """A painting held whole and still over a softened, darkened copy of
    itself, with dust drifting through warm light in front of it. Same
    frame(t, surface) interface as doodle.scene.Scene."""

    MOTES = 70

    def __init__(self, image: Path, seed: int):
        import cairo
        from PIL import Image, ImageFilter, ImageEnhance
        im = Image.open(image).convert("RGB")
        # the backdrop: the painting itself, covering, blurred and dimmed
        k = max(W / im.width, H / im.height)
        bg = im.resize((int(im.width * k) + 2, int(im.height * k) + 2))
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W,
                      (bg.height - H) // 2 + H)).filter(ImageFilter.GaussianBlur(28))
        bg = ImageEnhance.Brightness(bg).enhance(0.38)
        # the painting: whole, as large as fits with a margin
        k2 = min((W - 160) / im.width, (H - 110) / im.height)
        fg = im.resize((max(1, int(im.width * k2)), max(1, int(im.height * k2))), Image.LANCZOS)
        x0, y0 = (W - fg.width) // 2, (H - fg.height) // 2
        bg.paste(fg, (x0, y0))
        self.box = (x0, y0, fg.width, fg.height)
        rgba = bg.convert("RGBA")
        import numpy as np
        a = np.asarray(rgba).copy()
        a = a[..., [2, 1, 0, 3]]                # RGBA -> BGRA for cairo
        self._buf = bytearray(a.tobytes())
        self.still = cairo.ImageSurface.create_for_data(self._buf, cairo.FORMAT_ARGB32, W, H, W * 4)
        r = random.Random(seed)
        self.motes = [(r.uniform(0, W), r.uniform(0, H), r.uniform(0.6, 1.8), r.uniform(9, 22),
                       r.uniform(0, 6.283), r.uniform(1.6, 3.6)) for _ in range(self.MOTES)]
        # the candle stands by whichever lower corner the painting leaves
        # most room in, and the light comes from it
        side = -1 if r.random() < 0.5 else 1
        room = x0 if side < 0 else W - (x0 + fg.width)
        cx = (room / 2 if side < 0 else W - room / 2) if room > 150 else (W * (0.12 if side < 0 else 0.88))
        self.candle = (cx, H - 30)
        self.light = (cx, H - 200)
        self.seed = seed

    def frame(self, t: float, surf) -> None:
        import cairo
        from data_learning.doodle import props as PR
        cr = cairo.Context(surf)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_surface(self.still, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        # the candle the painting is seen by, on a ledge at the foot of the
        # frame: its flame is the motion the frozen-frame gate measures (the
        # dust alone measured 1.0 held frames), and it is real
        cx, cy = self.candle
        PR.candle_base(cr, cx, cy, 2.2, t, self.seed)
        PR.candle(cr, cx, cy, 2.2, t, self.seed)
        # the candle's light on the picture, flickering as a flame does (the
        # same value noise, at the same rate, as firelight in the drawn
        # rooms): bright near the candle, the far side of the frame in shade
        from data_learning.doodle import ink
        lx, ly = self.light
        k = (ink.vnoise(t, 8.0, self.seed + 3) + 1) / 2
        reach = W * (0.62 + 0.10 * k)
        g = cairo.RadialGradient(lx, ly, 30, lx, ly, reach)
        g.add_color_stop_rgba(0.0, 1.0, 0.80, 0.50, 0.08 + 0.42 * k)
        g.add_color_stop_rgba(0.45, 0.85, 0.55, 0.25, 0.02 + 0.20 * k)
        g.add_color_stop_rgba(1.0, 0.04, 0.02, 0.02, 0.0)
        cr.set_source(g)
        cr.paint()
        shade = cairo.RadialGradient(lx, ly, reach * 0.55, lx, ly, W * 1.1)
        shade.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
        shade.add_color_stop_rgba(1.0, 0.02, 0.01, 0.01, 0.55 - 0.30 * k)
        cr.set_source(shade)
        cr.paint()
        # dust drifting up through the light: slow, each mote on its own path
        for (x, y, rad, speed, ph, wob) in self.motes:
            yy = (y - speed * t) % (H + 40) - 20
            xx = x + math.sin(t / wob + ph) * 14
            d = math.hypot(xx - lx, yy - ly) / W
            al = max(0.0, 0.55 - d) * (0.6 + 0.4 * math.sin(t * 1.3 + ph))
            if al <= 0.01:
                continue
            cr.arc(xx, yy, rad * 2.2, 0, 2 * math.pi)
            cr.set_source_rgba(1.0, 0.9, 0.7, al)
            cr.fill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    a = ap.parse_args()
    if a.cmd == "search":
        for p in search(a.query):
            print(f"{p['id']:>14}  {p['kind']:<10} {p['title'][:60]!r}  {p['artist'][:30]}  {p['date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
