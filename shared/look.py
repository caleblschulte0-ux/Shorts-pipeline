"""THE CHANNEL'S DESIGN SYSTEM — one source of truth for how a frame looks.

The operator, 2026-09-10, on three shipped videos: *"the whole look of the
thing is cheap and shit ... we need a large scale rehaul of how the channel
looks."*

They were right, and the diagnosis is not taste. It is the house data-viz
anti-pattern list, almost verbatim:

    "Thick saturated blocks, heavy gridlines, no breathing room. Reads loud,
     even CHILDISH, at scale."

The data channel drew 165pt fully-saturated capsules on a flat navy gradient
in DejaVu Sans Bold — matplotlib's default face — with the value printed on
every bar in the series colour. Every one of those is on the list.

## This is not a new look. It is the look that was already chosen.

`data_learning/flat2d.py` says so in its own docstring: *"the Vox / Kurzgesagt
register: deep gradient ground, restrained palette, one idea per frame, big
confident type, generous negative space, smooth motion. **This is the look the
operator picked on pixels (sample v2).**"* It has carried the curiosity
channel since. The data channel simply never adopted it, and `repair_planner`
has had a defect code named `CHEAP_TYPOGRAPHY` pointing at `flat2d` the whole
time.

So the tokens here are seeded from flat2d's, not invented: its ground, its
gold-on-indigo restraint, its spaced kicker, its continuous push. What this
module adds is (a) an aspect-agnostic implementation, because flat2d is
1920x1080 and the shorts are 1080x1920, (b) the mark specs from the house
data-viz standard, and (c) one place to keep them, so the two channels cannot
drift apart again.

## The rules that are not negotiable

- **TEXT WEARS INK, NEVER THE SERIES COLOUR.** Values, labels and legends use
  `INK`/`INK_2`/`INK_3`; identity comes from the coloured mark beside them. A
  light hue is illegible as text on the ground, and colouring the text burns
  the one channel that carries identity.
- **MARKS ARE THIN.** A bar is capped — never fill the slot; the band's
  leftover is air. `bar_thickness()` computes it.
- **CHROME IS RECESSIVE.** Grid and axis rules are hairlines one step off the
  ground, solid, never dashed.
- **THE GROUND IS ALIVE.** A static plate reads as a frozen hold to the
  cadence gate and to a viewer alike. `ground()` drifts and `push()` never
  lets a frame equal the last — flat2d learned that one the hard way and wrote
  it down.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT_DIR = REPO / "assets" / "fonts"

# --------------------------------------------------------------------------
# INK — every piece of text on the channel is one of these three.
# --------------------------------------------------------------------------
INK = (242, 245, 250)          # primary: the thing being said
INK_2 = (150, 162, 184)        # secondary: labels, axis names
INK_3 = (92, 103, 128)         # muted: sources, grid, chrome

# --------------------------------------------------------------------------
# GROUND — deep indigo, seeded from flat2d.PALETTE so the channels match.
# --------------------------------------------------------------------------
GROUND_TOP = (13, 16, 48)
GROUND_BOT = (4, 4, 14)
STAR = (150, 160, 190)

# --------------------------------------------------------------------------
# ACCENT — ONE per story, and its dim partner for the supporting marks.
# Gold is flat2d's; blue is its cool counterpart. Both carry a 5-step ramp so
# a chart never needs a second hue to show ordered magnitude.
# --------------------------------------------------------------------------
ACCENTS = {
    "gold": ((255, 211, 122), (146, 116, 58)),
    "blue": ((120, 170, 255), (58, 84, 133)),
    "teal": ((79, 209, 197), (35, 100, 95)),
    "rose": ((244, 114, 182), (128, 56, 95)),
}
DEFAULT_ACCENT = "gold"

#: THE SUPPORTING MARK IS NEUTRAL, NOT A DIMMED ACCENT.
#:
#: A rank chart drew its leader in gold and every other bar in the accent's
#: dim partner — a muddy olive. Two problems, both visible in one frame: a
#: desaturated version of the highlight reads as "this one is DISABLED /
#: still loading" rather than "this one is context", and three tones of the
#: same hue is exactly the "everything is coloured, so nothing is" that the
#: house standard names as an anti-pattern. The supporting marks are ink.
#: Colour means ONE thing on this channel: the thing being said.
REST = (63, 72, 102)

#: A bar may never be thicker than this fraction of the frame's short side.
#: The dataviz standard caps a bar at ~24px on a ~900px chart — 2.7%. At 1080
#: that is 29px. The channel was drawing 165.
BAR_CAP_FRAC = 0.030
#: ...and never more than this fraction of its own row, so the band keeps air.
BAR_BAND_FRAC = 0.42
#: Hairline chrome.
RULE_PX = 2


def accent(name: str = DEFAULT_ACCENT):
    """`(bright, dim)` for a story's single accent."""
    return ACCENTS.get(name, ACCENTS[DEFAULT_ACCENT])


def accent_for(seed: str) -> str:
    """Deterministic accent per story, so a channel has variety across videos
    and none within one."""
    import hashlib
    keys = sorted(ACCENTS)
    h = int(hashlib.sha1((seed or "").encode()).hexdigest()[:8], 16)
    return keys[h % len(keys)]


# --------------------------------------------------------------------------
# TYPE — Inter for words, Anton for numbers.
#
# DejaVu Sans Bold is matplotlib's default and it is the single loudest signal
# that a frame was made by a script. Inter is subset to Latin (38KB a weight,
# under the repo's 256KB rule) and committed, NOT fetched: a font resolved at
# render time is a font CI does not have, and this session already fixed one
# CI-vs-production divergence exactly like that (cairosvg, and ten machines
# rendering with no mascot).
# --------------------------------------------------------------------------
DISPLAY = FONT_DIR / "Anton-Regular.ttf"        # numbers, hero figures
_WEIGHTS = {"regular": "Inter-Regular.ttf",
            "medium": "Inter-Medium.ttf",
            "semibold": "Inter-SemiBold.ttf",
            "bold": "Inter-Bold.ttf",
            "display": "InterDisplay-Bold.ttf"}
_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_CACHE: dict = {}


def font(size: int, weight: str = "semibold"):
    """A PIL font. `weight` is one of `_WEIGHTS`, or "anton" for the display
    face that carries every number."""
    key = (int(size), weight)
    if key in _CACHE:
        return _CACHE[key]
    from PIL import ImageFont
    if weight == "anton":
        path = DISPLAY
    else:
        path = FONT_DIR / _WEIGHTS.get(weight, _WEIGHTS["semibold"])
    try:
        f = ImageFont.truetype(str(path), int(size))
    except Exception:                       # noqa: BLE001 — never die on type
        try:
            f = ImageFont.truetype(_FALLBACK, int(size))
        except Exception:                   # noqa: BLE001
            f = ImageFont.load_default()
    _CACHE[key] = f
    return f


def fonts_are_real() -> bool:
    """Is the channel's own type actually present? A render that silently
    falls back to DejaVu is a render that does not look like the channel."""
    return all((FONT_DIR / n).exists() for n in _WEIGHTS.values()) \
        and DISPLAY.exists()


def bar_thickness(frame_short_side: int, band: float) -> int:
    """How thick a bar may be: capped absolutely AND relative to its band, so
    the leftover is air rather than more bar."""
    return max(6, int(min(frame_short_side * BAR_CAP_FRAC,
                          band * BAR_BAND_FRAC)))


def ground(w: int, h: int, seed: int = 7, stars: int = 110):
    """The channel's ground at ANY aspect: deep indigo, a soft radial lift,
    fine grain, and a drift of stars.

    flat2d's is 1920x1080 and hard-codes both; the shorts are 1080x1920. Same
    look, computed from the frame it is given.
    """
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (w, h), GROUND_BOT)
    d = ImageDraw.Draw(img)
    # vertical gradient, darkest at the bottom
    for y in range(0, h, 2):
        t = y / max(1, h - 1)
        c = tuple(int(GROUND_TOP[k] + (GROUND_BOT[k] - GROUND_TOP[k]) * t)
                  for k in range(3))
        d.rectangle([0, y, w, y + 2], fill=c)
    # a soft lift behind the headline so type always has ground under it
    lift = Image.new("L", (w, h), 0)
    ld = ImageDraw.Draw(lift)
    r = int(max(w, h) * 0.42)
    ld.ellipse([w // 2 - r, int(h * 0.30) - r, w // 2 + r, int(h * 0.30) + r],
               fill=54)
    lift = lift.filter(ImageFilter.GaussianBlur(max(w, h) // 9))
    img = Image.composite(Image.new("RGB", (w, h), (34, 42, 96)), img, lift)
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(stars):
        sx, sy = rnd.randrange(w), rnd.randrange(h)
        rad = rnd.choice((1, 1, 1, 2))
        d.ellipse([sx, sy, sx + rad, sy + rad],
                  fill=(*STAR, rnd.randint(40, 150)))
    return img


def push(img, i: int, n: int, amount: float = 0.06):
    """A continuous zoom so NO FRAME EVER EQUALS THE LAST.

    flat2d's comment says why, and this session measured the same thing from
    the other end: every `temporal_gate` block on the data channel is a frozen
    run in the closing seconds. A card that stops moving is a card the gate
    reads as dead air — and a viewer does too.
    """
    from PIL import Image
    w, h = img.size
    z = 1.0 + amount * (i / max(1, n - 1))
    nw, nh = int(round(w * z)), int(round(h * z))
    out = img.resize((nw, nh), Image.BILINEAR)
    ox, oy = (nw - w) // 2, (nh - h) // 2
    return out.crop((ox, oy, ox + w, oy + h))


def spaced(s: str, gap: str = " ") -> str:
    """A kicker: letterspaced small caps, flat2d's signature."""
    return gap.join((s or "").upper())


def fit(d, text: str, size: int, max_w: int, weight: str = "semibold",
        min_size: int = 14):
    """The largest font at or below `size` that keeps `text` inside `max_w`.

    Every renderer in this repo has now grown its own version of this after
    shipping clipped type — `viz_scene.fit_text`, `charts._fit_fontsize`, and
    `flat2d.comparison`, which still clips its own title to
    "ASA'S SHARE OF THE FEDERAL BUDGE". It belongs with the type tokens.
    """
    size = max(min_size, int(size))
    while size > min_size:
        f = font(size, weight)
        if d.textlength(text, font=f) <= max_w:
            return f, text
        size -= 2
    f = font(min_size, weight)
    if d.textlength(text, font=f) <= max_w:
        return f, text
    cut = text
    while cut and d.textlength(cut + "…", font=f) > max_w:
        cut = cut[:-1]
    return f, (cut + "…") if cut else ""


def wrap(d, text: str, f, max_w: int, max_lines: int = 4) -> list:
    words, lines, line = (text or "").split(), [], ""
    for w_ in words:
        t = f"{line} {w_}".strip()
        if d.textlength(t, font=f) > max_w and line:
            lines.append(line)
            line = w_
            if len(lines) == max_lines:
                return lines
        else:
            line = t
    if line:
        lines.append(line)
    return lines
