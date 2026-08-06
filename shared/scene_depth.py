"""THE WORLD BEHIND THE FIGURE — depth strata for every designed scene.

THE DEFECT, in the judges' own words. Four independent blind judges, across
two films, named the same worst moment on screen:

    "a cartoon stick figure on an empty blue slide"
    "the character floats in a void with nothing around him"

and the labels that survive every render in `state/curiosity_quality_ledger`
are BORING (5 of 5 judged), LOW_ENERGY (4 of 5) and EMPTY_COMPOSITION (3 of 5).
Not SAMENESS — that one is gone since the cut/camera/staging work. What is
left is that the frame has almost nothing IN it.

THE CONSTANT WHERE A DECISION BELONGED. `scenes._vgrad(top, bot)` is the
entire environment of every designed scene in the channel: a two-stop vertical
wash. Its colour ramps over the beat, which is why "something changed" gates
pass, but the *space* is empty in every frame of every scene of every film. A
character standing in front of a gradient is a slide. A character standing in
front of a horizon, with towers behind and a floor under them, is a shot.

This is the fourth of these found the same way, after `cut_rhythm` (shot
length), `camera_grammar` (the move) and `transitions` (the join). The pattern
holds: look for the value the renderer supports and the planner never varies.

WHAT THIS IS NOT. It is not a filter stack and not "add some particles". Every
stratum is a real object in a real place: a ground plane the figure stands on,
a skyline at a distance, a ceiling the room is under. They parallax at
different rates, which is what makes them read as depth rather than wallpaper,
and the rate difference is the LOW_ENERGY answer — something is moving in the
wide field at all times, without stealing the eye from the subject.

WHAT KEEPS IT FROM BECOMING THE NEXT CONSTANT. The strata are chosen by the
scene's identity, and adjacent scenes may not draw the same environment. A
single beautiful skyline behind all forty shots would score exactly as well on
"is the frame empty" and be the same film. `environment_for()` is the decision;
`ENVIRONMENTS` is the vocabulary it decides between.

CONTRAST IS DELIBERATELY LOW. The figure is near-white (`FIG`) on a dark wash;
strata sit between the two, closer to the background than the subject. A
depth layer that competes with the character trades EMPTY_COMPOSITION for a
busier version of the same complaint. `_toward` is where that is enforced.

    from shared import scene_depth
    bg = scene_depth.paint(base_image, "work_scene", t, index=3)
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# The vocabulary. Each environment is a tuple of STRATA, drawn back to front.
# A stratum is (kind, y_top, y_bottom, tone, parallax) where:
#   y_*      fractions of frame height — where the stratum sits
#   tone     how far from the background toward the light, 0..1 (see _toward)
#   parallax how far it slides across the beat, in fractions of frame width.
#            Different values per stratum IS the depth cue; identical values
#            would be a single flat card sliding.
# ---------------------------------------------------------------------------
SKYLINE = (
    ("hills",   0.52, 0.74, 0.10, 0.012),
    ("towers",  0.44, 0.80, 0.17, 0.030),
    ("ground",  0.78, 1.00, 0.13, 0.055),
)
# ROOM carries the two most-used scenes in the channel (sleep, work) and was
# the emptiest world here: a wall, a window and a floor scored 0.051
# occupancy against night_city's 0.130. `furniture` is a row of low blocks
# along the wall — a bookcase-and-sideboard silhouette — because a room with
# nothing in it is the same complaint one shade warmer.
ROOM = (
    ("ceiling",   0.00, 0.14, 0.09, 0.012),
    ("wall",      0.14, 0.72, 0.05, 0.020),
    ("window",    0.22, 0.52, 0.20, 0.020),
    ("furniture", 0.44, 0.74, 0.11, 0.038),
    ("ground",    0.72, 1.00, 0.12, 0.062),
)
OPEN_FIELD = (
    ("clouds",  0.10, 0.34, 0.11, 0.032),
    ("hills",   0.58, 0.80, 0.09, 0.040),
    ("ground",  0.80, 1.00, 0.10, 0.078),
)
STREET = (
    ("towers",  0.30, 0.76, 0.13, 0.024),
    ("poles",   0.40, 0.82, 0.20, 0.070),
    ("ground",  0.80, 1.00, 0.14, 0.090),
)
HALL = (
    ("ceiling", 0.00, 0.12, 0.05, 0.008),
    ("columns", 0.18, 0.80, 0.15, 0.048),
    ("ground",  0.80, 1.00, 0.12, 0.062),
)
# `windows` shares `towers`' rate ON PURPOSE — lit windows ride the building
# they are cut into, and giving them their own parallax would slide them off
# it. The third plane is the far ridge behind, which is what stops the whole
# city reading as one card.
NIGHT_CITY = (
    ("hills",   0.40, 0.62, 0.06, 0.008),
    ("towers",  0.26, 0.78, 0.11, 0.020),
    ("windows", 0.30, 0.74, 0.26, 0.020),
    ("ground",  0.80, 1.00, 0.10, 0.044),
)

# SOME STRATA ARE MADE OF AIR AND MUST NOT HAVE EDGES. Drawn as hard ellipses,
# `clouds` read as flying saucers over the sunrise — a new artefact where an
# empty sky had been, which is not a trade worth making. Blur radius in pixels
# at 1080p; anything not listed is a solid object and keeps its edge.
SOFT = {"clouds": 26, "hills": 6}

# Base opacity of a stratum's body, leaving headroom above for its highlights
# and below for its shadow lines. See Depth.__init__.
_BODY = 232

ENVIRONMENTS = (SKYLINE, ROOM, OPEN_FIELD, STREET, HALL, NIGHT_CITY)
NAMES = ("skyline", "room", "open_field", "street", "hall", "night_city")

# A scene whose meaning names its own place gets that place. Everything else
# rotates. Pinning only the ones that MEAN something keeps the mapping honest:
# inventing a "correct" environment for every scene kind would be a lookup
# table pretending to be a decision.
PLACES = {
    "sleep": 1,      # ROOM — a bed is indoors
    "work": 1,       # ROOM — a desk is indoors
    "screen": 5,     # NIGHT_CITY — the world dim around the glow
    "free": 2,       # OPEN_FIELD — walking out into it
    "traffic": 3,    # STREET
    "queue": 4,      # HALL — the line that never moves
    "walkout": 4,    # HALL
    "hold": 4,       # HALL — waiting on someone else's schedule
    "money": 5,      # NIGHT_CITY — the motif stands in the city it is spent in
    "treadmill": 1,  # ROOM
    "rent": 1,
    "grocery": 3,    # STREET
    "gas": 3,
    "tax": 4,
    "paycheck": 4,
    "subs": 5,
    "savings": 4,
}


def _place_key(scene_key: str) -> str:
    """`scene_free`, `free_scene` and `free` all name the same place.

    Two callers spell this differently — `pro_render` dispatches on the shot
    KIND (`scene_free`) while `scenes` names the builder (`free_scene`) — and
    the first version of PLACES was keyed on only one of them. Nothing raised:
    every pinned scene silently fell through to the hash rotation, so a bed
    was as likely to be outdoors as in, and the "pinned scenes keep their
    place" rule in `environment_for` was decorative. Caught by looking at the
    rendered table, not by any test that existed.
    """
    k = str(scene_key or "").strip().lower()
    for pre in ("scene_",):
        if k.startswith(pre):
            k = k[len(pre):]
    for suf in ("_scene",):
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k


def environment_for(scene_key: str, index: int = 0) -> tuple:
    """Which world this shot happens in.

    `index` is the shot's position, and it exists so two shots of the SAME
    unpinned scene kind do not get the same world — the staging-variety fix
    one layer down. A pinned scene keeps its place: a bedroom that becomes a
    field on the second visit is not variety, it is a continuity error.
    """
    key = _place_key(scene_key)
    if key in PLACES:
        return ENVIRONMENTS[PLACES[key]]
    # Deterministic, and seeded by BOTH the name and the position so the same
    # kind twice in one film lands somewhere else the second time.
    h = sum(ord(c) * (i + 3) for i, c in enumerate(key))
    return ENVIRONMENTS[(h + int(index)) % len(ENVIRONMENTS)]


def name_for(scene_key: str, index: int = 0) -> str:
    env = environment_for(scene_key, index)
    return NAMES[ENVIRONMENTS.index(env)]


def _toward(bg_rgb, tone: float):
    """A stratum colour: the local background nudged toward light.

    Derived from the background rather than fixed, so a stratum inherits the
    scene's grade instead of fighting it — the reason a warm sunrise scene and
    a cold night scene do not get the same grey towers. Capped well below the
    figure's brightness: the environment must never be the brightest thing in
    the frame, which is the failure mode where a fix for EMPTY_COMPOSITION
    becomes a fix for nothing.
    """
    r, g, b = bg_rgb[:3]
    k = max(0.0, min(0.34, float(tone)))
    return (int(r + (255 - r) * k), int(g + (255 - g) * k),
            int(b + (255 - b) * k))


def _sample(im, y_frac: float):
    """The background colour at a height — one pixel, no cost."""
    w, h = im.size
    y = max(0, min(h - 1, int(h * y_frac)))
    try:
        return im.getpixel((w // 2, y))[:3]
    except Exception:  # noqa: BLE001 — a stratum never breaks a render
        return (20, 22, 30)


def _band(d, w, h, y0, y1, col):
    d.rectangle([0, int(h * y0), w * 3, int(h * y1)], fill=col)


def _draw_stratum(d, w, h, kind, y0, y1, col, seed: int):
    """One stratum, drawn across THREE screen widths so a parallax slide never
    exposes an edge. Cheap: this is drawn once per shot, not once per frame.

    COORDINATES ARE TILE-SPACE, ORIGIN AT THE TILE'S LEFT EDGE. The tile is
    3w wide and composited at -w, so the middle third [w, 2w) is what the
    viewer sees at t=0 and the slide walks rightward from there. The first
    version authored in SCREEN space, from -w to 2w, which put every
    single-instance element — the room's window most visibly — in the third
    that is never on camera. It measured as an empty room and looked like
    one, and nothing failed. Repeating kinds survived it by accident, which
    is worse: it made the bug look like a room-only problem.
    """
    top, bot = int(h * y0), int(h * y1)
    span = bot - top
    # WHERE THE PATTERN STARTS, per scene. Every repeating stratum used to
    # begin at x=0, so `seed` reached only the SPACING — and two scenes whose
    # seeds happened to agree mod 3 drew a pixel-identical background.
    # `scene_queue` and `scene_hold` did exactly that. A phase is what makes
    # two halls two different halls.
    phase = (seed * 137) % max(1, int(w * 0.33))
    if kind == "ground":
        _band(d, w, h, y0, y1, col)
        # a floor edge, so the plane reads as a surface and not a swatch
        d.rectangle([0, top, w * 3, top + max(2, span // 26)],
                    fill=_lighten(col, 26))
    elif kind in ("wall", "ceiling"):
        _band(d, w, h, y0, y1, col)
    elif kind == "hills":
        for j in range(9):
            cx = phase + int(j * w * 0.42) + (seed * 37 % 120)
            rw = int(w * (0.30 + 0.06 * ((j + seed) % 4)))
            rh = int(span * (0.85 + 0.25 * ((j + seed) % 3)))
            d.ellipse([cx - rw, bot - rh, cx + rw, bot + rh], fill=col)
    elif kind == "clouds":
        for j in range(11):
            cx = phase + int(j * w * 0.34) + (seed * 53 % 200)
            cy = top + int(span * (0.2 + 0.6 * (((j * 7 + seed) % 5) / 4.0)))
            rw, rh = int(w * 0.085), int(span * 0.26)
            d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=col)
    elif kind == "furniture":
        # low blocks of varied height sitting ON the band's bottom edge, so
        # they read as objects against a wall rather than floating panels
        x = -phase
        j = 0
        while x < w * 3:
            bw = int(w * (0.07 + 0.05 * ((j + seed) % 4)))
            bh = int(span * (0.30 + 0.42 * ((j * 3 + seed) % 4) / 3.0))
            d.rectangle([x, bot - bh, x + bw, bot], fill=col)
            d.rectangle([x, bot - bh, x + bw, bot - bh + max(2, span // 30)],
                        fill=_lighten(col, 20))
            x += bw + int(w * (0.03 + 0.03 * ((j + seed) % 3)))
            j += 1
    elif kind in ("towers", "windows"):
        x = -phase
        j = 0
        while x < w * 3:
            bw = int(w * (0.036 + 0.028 * ((j + seed) % 5)))
            bh = int(span * (0.34 + 0.16 * ((j * 3 + seed) % 5)))
            if kind == "towers":
                d.rectangle([x, bot - bh, x + bw, bot], fill=col)
            else:
                # lit windows: the only high-tone stratum, and it is made of
                # small marks — a bright BAND at this tone would flatten the
                # frame instead of populating it
                for r in range(max(1, bh // 46)):
                    for c in range(max(1, bw // 34)):
                        if (r * 5 + c * 3 + j + seed) % 3:
                            continue
                        wx = x + 10 + c * 34
                        wy = bot - bh + 12 + r * 46
                        d.rectangle([wx, wy, wx + 13, wy + 19], fill=col)
            x += bw + int(w * 0.014)
            j += 1
    elif kind == "poles":
        x = -phase
        j = 0
        while x < w * 3:
            pw = max(3, int(w * 0.004))
            d.rectangle([x, top, x + pw, bot], fill=col)
            x += int(w * (0.11 + 0.03 * ((j + seed) % 3)))
            j += 1
    elif kind == "columns":
        x = -phase
        j = 0
        while x < w * 3:
            cw = int(w * 0.028)
            d.rectangle([x, top, x + cw, bot], fill=col)
            d.rectangle([x - cw // 3, top, x + cw + cw // 3, top + span // 22],
                        fill=_lighten(col, 18))
            x += int(w * (0.155 + 0.02 * ((j + seed) % 3)))
            j += 1
    elif kind == "window":
        # one bright rectangle, off-centre: a room needs a light source or the
        # wall is just a darker void
        x0 = w + phase + int(w * 0.34)
        d.rectangle([x0, top, x0 + int(w * 0.17), bot], fill=col)
        d.rectangle([x0 + int(w * 0.083), top, x0 + int(w * 0.087), bot],
                    fill=_lighten(col, -30))


def _seed(scene_key: str, index: int) -> int:
    """A per-scene drawing seed.

    Was `len(scene_key) + index`, which made `scene_queue` and `scene_hold`
    — both pinned to HALL — draw the SAME columns in the same places. Two
    different scenes rendering an identical background is SAMENESS, the exact
    label this module exists downstream of; a length is not an identity.
    """
    k = str(scene_key or "")
    return (sum(ord(c) * (i * 7 + 11) for i, c in enumerate(k))
            + int(index) * 31) % 997


def _lighten(col, amt):
    """Brighter, whether `col` is a colour or a mask level.

    Strata are drawn into an alpha MASK now (the colour arrives at composite
    time so it can track a changing sky), so the highlights inside a stratum —
    a floor edge, the cap on a column — arrive here as a scalar 255. Returning
    a tuple for that would silently draw nothing.
    """
    if isinstance(col, (int, float)):
        return int(max(0, min(255, col + amt)))
    return tuple(max(0, min(255, c + amt)) for c in col[:3])


class Depth:
    """Strata for one shot; `at(im, t)` composites them onto a frame.

    SHAPES ARE DRAWN ONCE, COLOURS TRACK THE SKY. The geometry never changes,
    so the polygon work happens at construction and the hot path is a paste.
    The COLOUR does change, because most scenes ramp their background across
    the beat — `free_scene` goes from night to a warm sunrise — and a stratum
    tinted from frame 0 becomes a dark silhouette against a bright sky.

    On hills that reads as a ridge at sunset and is exactly right. On CLOUDS
    it read as dark blobs hanging over an orange sky: a fix for an empty sky
    that put something worse in it. Rather than delete the layer or special-
    case one kind, the tint is refreshed from the CURRENT frame every
    `_REFRESH` frames — the drift is smooth, so a few updates per second are
    invisible, and re-tinting a stored mask costs a fraction of redrawing.
    """

    _REFRESH = 10          # frames between re-tints; ~3/s at 30fps

    def __init__(self, base, scene_key: str, index: int = 0):
        from PIL import Image, ImageDraw, ImageFilter
        self.w, self.h = base.size
        self.spec = []
        self._n = 0
        for kind, y0, y1, tone, par in environment_for(scene_key, index):
            mask = Image.new("L", (self.w * 3, self.h), 0)
            d = ImageDraw.Draw(mask)
            # Drawn in pure alpha: the shape is the shape, the colour
            # arrives later. The body sits just under full opacity so the
            # highlights inside a stratum — a floor edge, the cap on a column
            # — have somewhere to go: MORE opaque means closer to the pure
            # stratum colour, which is lighter than the sky behind it. Drawn
            # at a flat 255 those highlights clamp away and the objects lose
            # their edges.
            _draw_stratum(d, self.w, self.h, kind, y0, y1, _BODY,
                          seed=_seed(scene_key, index))
            if kind in SOFT:
                mask = mask.filter(ImageFilter.GaussianBlur(SOFT[kind]))
            self.spec.append({"kind": kind, "mask": mask, "par": float(par),
                              "mid": (y0 + y1) / 2.0, "tone": tone,
                              "tile": None, "col": None})
        self._retint(base)

    def _retint(self, im):
        from PIL import Image
        for s in self.spec:
            col = _toward(_sample(im, s["mid"]), s["tone"])
            if col == s["col"] and s["tile"] is not None:
                continue                     # the sky has not moved
            tile = Image.new("RGBA", s["mask"].size, col + (0,))
            tile.putalpha(s["mask"])
            s["tile"], s["col"] = tile, col

    def at(self, im, t: float):
        """Composite every stratum onto `im` at its parallax offset for time t.

        The offsets are the whole point: a near ground plane slides several
        times as far as a distant skyline in the same beat, and that ratio is
        what the eye reads as space. `t` runs 0..1 across the shot.
        """
        t = max(0.0, min(1.0, float(t)))
        if self._n % self._REFRESH == 0:
            self._retint(im)
        self._n += 1
        out = im.convert("RGBA")
        for s in self.spec:
            dx = -self.w - int(self.w * s["par"] * t)
            out.alpha_composite(s["tile"], (dx, 0))
        return out.convert("RGB")


def paint(base, scene_key: str, t: float, index: int = 0):
    """One-shot convenience: strata onto a single frame. Prefer `Depth` in a
    render loop — this rebuilds the tiles every call."""
    return Depth(base, scene_key, index).at(base, t)


def occupancy(im) -> float:
    """Fraction of the frame that is not the flat background wash.

    THE MEASURE FOR EMPTY_COMPOSITION, and the reason this module can be
    checked without rendering a film or asking a judge. A `_vgrad` frame is
    constant along every row, so any pixel differing from its row's median is
    something that was PUT there. On an empty gradient this is ~0; on a frame
    with a horizon, towers and a floor it is a large fraction.

    Deliberately blind to whether the something is any good — it is a floor,
    not a score. A metric that claimed to know good composition would be the
    kind of measure `film_metrics` warns can be satisfied without improving
    the film.
    """
    import numpy as np
    a = np.asarray(im.convert("RGB"), np.int16)
    row_med = np.median(a, axis=1, keepdims=True)
    return float((np.abs(a - row_med).max(axis=2) > 6).mean())


def parallax_energy(frames) -> float:
    """Mean per-pixel change between consecutive frames, 0..255.

    THE MEASURE FOR LOW_ENERGY. A colour-ramp-only background moves every
    pixel by a fraction of a level per frame; strata sliding at different
    rates move real edges. Answers "is anything actually happening" without a
    judge, which is what makes it usable inside a test.
    """
    import numpy as np
    fs = [np.asarray(f.convert("RGB"), np.float32) for f in frames]
    if len(fs) < 2:
        return 0.0
    return float(sum(np.abs(b - a).mean() for a, b in zip(fs, fs[1:]))
                 / (len(fs) - 1))


def summary(scene_keys) -> str:
    seen = {}
    out = []
    for k in scene_keys:
        i = seen.get(k, 0)
        seen[k] = i + 1
        out.append(name_for(k, i))
    return f"{len(set(out))} distinct worlds over {len(out)} scenes"


__all__ = ["Depth", "paint", "environment_for", "name_for", "occupancy",
           "parallax_energy", "summary", "ENVIRONMENTS", "NAMES", "PLACES"]
