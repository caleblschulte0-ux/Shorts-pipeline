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
#: Text INSIDE a light mark (a value printed in the gold highlight bar). White
#: on gold measured a luminance gap of ~40 — "342" on the staircase's lit
#: step was the audit's one faint value (data_learning/a_audit.py).
INK_ON_LIGHT = (13, 16, 48)


def ink_on(fill) -> tuple:
    """The ink for text sitting ON a fill: INK on anything dark, INK_ON_LIGHT
    on anything light. `fill` is an (r, g, b) tuple or a '#rrggbb' string."""
    if isinstance(fill, str):
        h = fill.lstrip("#")
        fill = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = [float(c) for c in fill[:3]]
    return INK_ON_LIGHT if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 150 else INK

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

#: THE ALARM. A baseline, a threshold, "this is the line you are crossing" —
#: the ONE colour that means something on its own, so it may never be
#: confused with the story's accent.
#:
#: It was `#F59E0B`, an amber, and it sat ΔE 13.1 from the GOLD accent in
#: ordinary vision — under the hard floor of 15 that `shared/palette` says
#: no labelling excuses. Gold is the default accent and lands on 82 of the
#: channel's 309 stories, so on a quarter of them the subject of the video
#: and the alarm were the same colour to the eye. Measured, not guessed:
#: this clears every one of the four accents at 16.2 normal / 15.6 CVD, with
#: 5.5:1 contrast on the ground. `tests/test_palette.py` holds all of it.
WARN = (242, 84, 45)

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

# --------------------------------------------------------------------------
# THE ILLUSTRATED ARM — worlds, not grounds (docs/CHANNEL_LOOK.md §Worlds).
#
# Operator, 2026-09-23, on the illustrated 2D style sample: "that 2D
# animation, I want to start A/B testing that on the mascot channel." Its
# frames are full-bleed illustrated WORLDS: layered gradients, two-tone
# shaded forms (a LIT face and a SHADOW face), rim light, soft glows and a
# foreground layer. Those colours are a new PALETTE, so they live here and
# nowhere else, same as the ground and the accents above. The rules do not
# change: ONE accent on the subject (`accent()`), text in INK, supporting
# marks neutral — here the world's own `form` tones, lit and shadow.
#
# Each world names: `sky` (top-to-bottom gradient stops), `glow` (the light
# source), `far`/`mid`/`near` (layered terrain, back to front), `form`
# (lit, shadow) for the neutral data marks, `rim` (edge light), `mote`
# (ambient particles). Colour means something: the subject is warm, the
# setting is cool, depth darkens.
# --------------------------------------------------------------------------
#: The NEUTRAL form every supporting mark wears in a world: a desaturated
#: slate, lit and shadow. A world-tinted form (blue under the sea, lilac at
#: dusk) sat within a few steps of the blue and teal accents, so the subject
#: stopped standing out — the same "desaturated accent reads as disabled"
#: failure REST exists to prevent. Farm keeps a sage of its own.
ILLU_FORM = ((122, 128, 140), (80, 86, 100))

WORLDS = {
    "dusk": {       # sky over open land — the default world
        "sky": [(0.0, (27, 31, 92)), (0.55, (106, 79, 163)),
                (0.85, (243, 154, 107)), (1.0, (255, 208, 138))],
        "glow": (255, 226, 168), "far": (59, 63, 110), "mid": (48, 42, 96),
        "near": (42, 35, 96), "form": ILLU_FORM,
        "rim": (207, 211, 245), "mote": (255, 255, 255),
    },
    "city": {       # a skyline at blue hour
        "sky": [(0.0, (14, 18, 58)), (0.6, (58, 52, 128)),
                (1.0, (232, 128, 112))],
        "glow": (255, 196, 150), "far": (40, 44, 92), "mid": (30, 33, 74),
        "near": (18, 20, 48), "form": ILLU_FORM,
        "rim": (190, 205, 255), "mote": (255, 214, 150),
    },
    "ocean": {      # sky band above water that darkens with depth
        "sky": [(0.0, (39, 182, 217)), (0.18, (15, 110, 168)),
                (0.45, (7, 58, 112)), (1.0, (2, 6, 23))],
        "glow": (200, 245, 255), "far": (42, 35, 80), "mid": (26, 21, 58),
        "near": (18, 13, 36), "form": ILLU_FORM,
        "rim": (93, 79, 176), "mote": (200, 235, 255),
    },
    "space": {      # stars and a planet's limb
        "sky": [(0.0, (5, 6, 26)), (1.0, (20, 26, 74))],
        "glow": (180, 190, 255), "far": (70, 72, 104), "mid": (118, 120, 150),
        "near": (34, 36, 62), "form": ILLU_FORM,
        "rim": (180, 190, 255), "mote": (255, 255, 255),
    },
    "farm": {       # golden hour over fields
        "sky": [(0.0, (46, 58, 120)), (0.6, (236, 150, 98)),
                (1.0, (255, 214, 140))],
        "glow": (255, 230, 170), "far": (96, 88, 120), "mid": (122, 104, 70),
        "near": (78, 64, 42), "form": ((132, 150, 138), (84, 100, 92)),
        "rim": (255, 232, 180), "mote": (255, 240, 200),
    },
    "industry": {   # a factory yard at dusk, haze and sparks
        "sky": [(0.0, (22, 24, 48)), (0.7, (92, 70, 96)),
                (1.0, (214, 132, 96))],
        "glow": (255, 170, 110), "far": (54, 52, 78), "mid": (38, 38, 60),
        "near": (24, 24, 40), "form": ILLU_FORM,
        "rim": (255, 190, 140), "mote": (255, 180, 120),
    },
}
#: SUBJECT SCENES (data_learning/subject_scenes.py) — the reference's own
#: palette: dawn over forest, cleared earth, pasture. The subject is warm,
#: the setting is cool, and the readout is the sample's gold.
SCENES = {
    "readout": (255, 209, 102), "accent2": (124, 240, 255),
    "dawn": [(0.0, (27, 31, 92)), (0.5, (106, 79, 163)),
             (0.82, (243, 154, 107)), (1.0, (255, 208, 138))],
    "sun": (255, 226, 168), "sun_glow": (255, 204, 128), "mist": (255, 236, 214),
    "leaf": (46, 158, 104), "leaf_shade": (24, 104, 74), "rim_leaf": (190, 255, 200),
    "leaf_far": (58, 92, 110), "leaf_far_shade": (40, 66, 88),
    "trunk": (92, 60, 44), "trunk_far": (50, 48, 76),
    "earth": [(0.0, (60, 40, 50)), (1.0, (22, 14, 26))],
    "stump": (120, 80, 56), "stump_top": (214, 170, 120),
    "cleared": [(0.0, (120, 84, 66)), (1.0, (40, 26, 30))],
    "scar": (168, 112, 78), "dust": (230, 190, 150),
    "france_lit": (130, 150, 230), "france_shade": (80, 96, 176),
    "france_rim": (206, 214, 255), "flag": (255, 209, 102),
    "pasture": (120, 170, 80), "pasture_lit": (176, 214, 120),
    "cow": (246, 240, 232), "cow_patch": (60, 48, 50), "cow_dark": (40, 32, 36),
    "truck": (214, 96, 70), "truck_cab": (240, 200, 90), "log": (150, 100, 66),
    # coffee: a cafe at dawn, a farm in drought
    "cafe_wall": [(0.0, (46, 30, 44)), (1.0, (92, 56, 52))],
    "window": [(0.0, (255, 196, 130)), (1.0, (255, 150, 110))],
    "counter": (120, 74, 52), "counter_top": (168, 110, 72),
    "brass": (230, 176, 80), "brass_shade": (170, 120, 50),
    "coin": (255, 214, 110), "coin_edge": (190, 140, 50),
    "sack": (196, 160, 110), "sack_shade": (140, 108, 72), "sack_ink": (110, 70, 44),
    "bean": (92, 52, 36), "bean_lit": (140, 86, 58), "steam": (255, 245, 235),
    "chalk_board": (36, 52, 46), "chalk_frame": (120, 80, 52), "chalk": (240, 240, 230),
    "drought_sky": [(0.0, (70, 110, 180)), (0.6, (240, 180, 110)), (1.0, (255, 214, 140))],
    "sun_hot": (255, 236, 170), "dry_soil": [(0.0, (190, 132, 84)), (1.0, (96, 58, 40))],
    "crack": (70, 40, 30), "shrub": (70, 130, 70), "shrub_dry": (150, 140, 70),
    # urban heat: a street in a heatwave, a 1930s map
    "heat_sky": [(0.0, (92, 36, 62)), (0.32, (196, 84, 70)), (0.62, (255, 168, 90)),
                 (1.0, (255, 226, 170))],
    "brick": (170, 84, 64), "brick_shade": (120, 56, 48), "brick_cool": (110, 120, 150),
    "brick_cool_shade": (78, 86, 116), "street": (60, 58, 70), "curb": (150, 146, 150),
    "heat": (255, 90, 50), "cool": (120, 200, 255), "mercury": (240, 60, 50),
    "glass": (230, 240, 255), "paper": (236, 222, 186), "paper_ink": (90, 70, 50),
    "redline": (200, 50, 40), "treeleaf": (70, 150, 90),
}

#: The subject's warm light on a lit face, and its shade, derived from the
#: story's accent so there is still exactly ONE accent per story.
ILLU_SHADE = 0.62          # shadow face = accent * this
ILLU_RIM = 0.35            # rim light mixes this much white into the lit face


def world(name: str) -> dict:
    """A world's tokens, falling back to the default world."""
    return WORLDS.get(name) or WORLDS["dusk"]


#: A bar may never be thicker than this fraction of the frame's short side.
#: The dataviz standard caps a bar at ~24px on a ~900px chart — 2.7%. At 1080
#: that is 29px. The channel was drawing 165.
BAR_CAP_FRAC = 0.030
#: ...and never more than this fraction of its own row, so the band keeps air.
BAR_BAND_FRAC = 0.42
#: Hairline chrome.
RULE_PX = 2


def gradient_fill(ax, xs, ys, base: float, color: str, zorder: int = 2,
                  top: float = 0.30):
    """The area under a line, fading OUT downward instead of a flat wash.

    Lives here because BOTH chart renderers need it and neither may own it:
    `data_learning/charts` draws the explainer's fallback charts and
    `engines/chart_race` draws trending's `graph_race`, and on 2026-09-10
    the showrunner blocked three graph_races in one slate for `empty_void`
    — "roughly the lower 40% of the picture is empty", "the entire middle
    ~60% of the frame unbroken black". A line on a dark ground leaves the
    space under it empty by construction; a fill is what makes that space
    part of the picture.

    A FLAT low-alpha fill is not the answer and was the previous bug: warm
    ink at 10% over a cold ground composites to a grey-brown slab, and the
    bigger the area the greyer it gets — the shape stops reading as "under
    the line" and starts reading as a rectangle behind it. Fading from
    `top` at the line to nothing at the baseline keeps the density where
    the line is, which is where it means something.

    One column of image data clipped to the fill polygon: no vectors, no
    network, one draw. Never raises — a fill is a look, not a blocker.
    """
    try:
        import numpy as np
        from matplotlib.colors import to_rgb
        from matplotlib.patches import Polygon
        xs, ys = list(xs), list(ys)
        if len(xs) < 2:
            return
        x0, x1, y1 = min(xs), max(xs), max(ys)
        if not (y1 > base and x1 > x0):
            # A FLAT SERIES HAS NO AREA. Every value identical makes
            # `base == y1`, and imshow warns "identical low and high ylims
            # makes transformation singular" and draws a degenerate strip.
            return
        r, g, b = to_rgb(color)
        grad = np.empty((256, 1, 4))
        grad[:, :, 0], grad[:, :, 1], grad[:, :, 2] = r, g, b
        grad[:, :, 3] = np.linspace(0.0, top, 256)[:, None]
        im = ax.imshow(grad, aspect="auto", origin="lower", zorder=zorder,
                       extent=(x0, x1, base, y1))
        poly = Polygon(list(zip(xs, ys)) + [(x1, base), (x0, base)],
                       closed=True, facecolor="none", edgecolor="none")
        ax.add_patch(poly)
        im.set_clip_path(poly)
    except Exception:  # noqa: BLE001 — a fill is a look, never a blocker
        try:
            ax.fill_between(xs, ys, base, color=color, alpha=0.10,
                            zorder=zorder)
        except Exception:  # noqa: BLE001
            pass


def frame_the_data(lo: float, hi: float, zero_band: float = 0.15,
                   pad: float = 0.12) -> float:
    """The y-axis FLOOR for a chart of data spanning [lo, hi].

    THIS IS THE `empty_void` AUTO-FAIL, MEASURED IN A SHIPPED FRAME.

    2026-09-10, "The US Quietly Became The World's Top Oil Producer" —
    showrunner BLOCK:

        "The whole 0-5M band of the plot is pure black in every frame ...
         roughly the lower 40% of the picture is empty because the y-axis
         floors at 0 while all data lives 5.5M-12.9M; dark_fraction 1.0."

    A hard zero floor is a rendering default pretending to be an editorial
    choice. It is RIGHT when the data actually reaches for zero — a race
    from 417 eagles to 71,467 is a growth story and starting anywhere else
    would flatter it — and wrong when the whole series lives in a band far
    above it, where it spends the frame on emptiness and squashes the very
    change the video is about.

    So: keep zero when the low end is within `zero_band` of the span of it,
    otherwise frame the data with `pad` of the span underneath. The axis
    carries tick labels either way, so a framed axis still says where it is.
    """
    span = float(hi) - float(lo)
    if span <= 0:
        return min(0.0, float(lo))
    if float(lo) < 0:
        # ZERO IS NOT A FLOOR FOR NEGATIVE DATA — it is a mid-line, and
        # returning it would put every point BELOW the axis and off the
        # frame entirely. Worse than the bug this function exists to fix,
        # and caught by `test_negatives_are_not_clipped_away` rather than by
        # a chart of a deficit shipping empty.
        return float(lo) - span * pad
    if float(lo) <= span * zero_band:
        return 0.0
    return float(lo) - span * pad


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
