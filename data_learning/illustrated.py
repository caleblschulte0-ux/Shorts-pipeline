"""THE ILLUSTRATED ARM — the explainer drawn as a world, not a chart on a ground.

Operator, 2026-09-23, on an illustrated 2D style sample made for another
channel (`docs/style_samples/illustrated_2d/`): *"that 2D animation, I want
to start A/B testing that on the mascot channel ... throw the mascot on there
and input our data and make sure that we can constantly make something that
looks that good in a wide variety of situations and a wide variety of data."*

The sample was drawn by hand for one script. This module is the general
version: a WORLD (sky, city, ocean, space, farm, industry — `look.WORLDS`)
behind a DATA DRAWING chosen from the claim the data makes, with Data acting
inside it. It is an arm of the existing renderer, not a fork:

  * `relationships.classify` still decides what the data says; `drawing_for`
    maps that claim to an illustrated drawing, or None, in which case the
    beat falls back to the current renderer and `studio_render` records it.
  * every number drawn comes from the insight's own items — decoration moves,
    it never adds a quantity;
  * colour comes from `shared/look.py` only — the world's tokens, the story's
    ONE accent on the subject, text in INK;
  * nothing is ever still: clouds drift, one mover crosses, light pulses, so the
    cadence gate never sees a freeze (`tests/test_the_illustrated_arm.py`
    measures it with the gate's own detector on every world x drawing).

Frames are 1080x1920, opaque, written as `<name>_build%02d.png` like every
other build, so `studio_render` lays them on the timeline unchanged.
"""
from __future__ import annotations

import math
import random
import re
from pathlib import Path

import cairo

from shared import look


def _ensure_fonts() -> None:
    """Register the repo's Anton + Inter with fontconfig, once.

    cairo's text API finds faces through fontconfig, which knows nothing of
    `assets/fonts/`. Without this every label silently falls back to a
    default sans — the "cheap typography" the look ruling was about."""
    import shutil
    import subprocess
    try:
        dest = Path.home() / ".local" / "share" / "fonts"
        need = [f for f in look.FONT_DIR.glob("*.ttf")
                if not (dest / f.name).exists()]
        if not need:
            return
        dest.mkdir(parents=True, exist_ok=True)
        for f in need:
            shutil.copy2(f, dest / f.name)
        subprocess.run(["fc-cache", "-f", str(dest)], capture_output=True,
                       timeout=60)
    except Exception:  # noqa: BLE001 — fonts are best-effort, never a crash
        pass


_ensure_fonts()

W, H = 1080, 1920
FPS = 30
TITLE_Y = 250            # the beat title's baseline band (same as viz_scene)
STAGE_TOP = 430          # the data may not draw above this (title clearance)
GROUND_Y = 1440          # the world's ground line under the data. Every
                         # label sits above y=1584: the closing recap keeps
                         # only y 336..1584 of the frame (recap_geometry), and
                         # labels below that were cut off in the closing.
CAPTION_TOP = 1650       # captions are burned below here: keep it calm
HOST_H = 230             # Data's height in a world

# ---------------------------------------------------------------- colour ---


def _c(rgb, a: float = 1.0):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, a)


def _mix(a, b, k: float):
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def _scale(rgb, k: float):
    return tuple(max(0, min(255, int(round(v * k)))) for v in rgb)


def accent_pair(seed: str = ""):
    """(lit, shadow, rim) for the story's ONE accent. It is the accent the
    renderer already set for this story (`charts.HIGHLIGHT`, chosen per slug
    by `look.accent_for`), so both arms give a story the same colour."""
    try:
        from data_learning import charts
        h = str(charts.HIGHLIGHT).lstrip("#")
        bright = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:  # noqa: BLE001
        bright, _dim = look.accent(look.accent_for(seed or "story"))
    return (bright, _scale(bright, look.ILLU_SHADE),
            _mix(bright, (255, 255, 255), look.ILLU_RIM))


# --------------------------------------------------------------- easing ---


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def pop(x, s: float = 1.6):
    """Ease-out with a small overshoot — the sample's entrance 'pop'."""
    x = clamp(x) - 1.0
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def seg(t, a, b):
    return clamp((t - a) / max(1e-6, b - a))


# ---------------------------------------------------------------- paint ---


def vgrad(cr, stops, y0=0, y1=H, x0=0, x1=W):
    """Fill x0..x1, y0..y1 with a top-to-bottom gradient. `stops` is
    [(position 0..1, rgb), ...], or plain [rgb, ...] spaced evenly."""
    # Plain colours are what the brain writes first: "too many values to
    # unpack (expected 2)" at `vgrad(cr, [(120, 156, 196), ...])` was the
    # crash on attempt 1 of most drafts, 2026-10-07. Same picture either way.
    stops = list(stops)
    if stops and all(isinstance(s, (tuple, list)) and len(s) in (3, 4)
                     and all(isinstance(v, (int, float)) for v in s)
                     for s in stops):
        n = max(1, len(stops) - 1)
        stops = [(k / n, c) for k, c in enumerate(stops)]
    g = cairo.LinearGradient(0, y0, 0, y1)
    for p, c in stops:
        g.add_color_stop_rgba(p, *_c(c))
    cr.set_source(g)
    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    cr.fill()


def glow(cr, x, y, r, rgb, a=1.0):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, *_c(rgb, a))
    g.add_color_stop_rgba(1, *_c(rgb, 0))
    cr.set_source(g)
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.fill()


def ridge_path(cr, pts, base):
    cr.move_to(pts[0][0], base)
    for x, y in pts:
        cr.line_to(x, y)
    cr.line_to(pts[-1][0], base)
    cr.close_path()


def hills(cr, base, amp, wave, phase, rgb, rim=None):
    pts = [(x, base - amp * (0.55 + 0.45 * math.sin(x / wave + phase))
            - amp * 0.25 * math.sin(x / (wave * 0.37) + phase * 1.7))
           for x in range(-20, W + 41, 20)]
    ridge_path(cr, pts, H)
    cr.set_source_rgba(*_c(rgb))
    cr.fill()
    if rim is not None:
        cr.set_line_width(3)
        cr.set_source_rgba(*_c(rim, 0.55))
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.stroke()


def flow(cr, pts, t, rgb, spacing=36.0, speed=560.0, r=9.0, a=0.9):
    """Glowing beads streaming along a polyline, forever.

    Once a drawing has built, its world's drift alone measured ~85% held
    frames at the gate's own scale (192px wide, 12x12 blocks, a block must
    change by 6 grey levels): a 47-second preview was blocked at
    duplicate_ratio 0.459 before the judge looked. The data keeps MOVING
    instead — time flows along a ridge, light rises up a column — which is
    decoration on the subject that adds no quantity."""
    if len(pts) < 2:
        return
    segs, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        segs.append((x0, y0, x1, y1, total, L))
        total += L
    if total <= 0:
        return
    d = (t * speed) % spacing
    while d < total:
        for x0, y0, x1, y1, s0, L in segs:
            if s0 <= d <= s0 + L and L > 0:
                k = (d - s0) / L
                x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
                glow(cr, x, y, r * 2.4, rgb, a * 0.45)
                cr.set_source_rgba(*_c(rgb, a))
                cr.arc(x, y, r, 0, 2 * math.pi)
                cr.fill()
                break
        d += spacing


# ------------------------------------------------------------- light ---
#
# Operator, 2026-10-05: "the art in general on the B clips needs to be
# better." Every subject was a flat-filled polygon with a hard edge — a
# gold pile of identical ellipses, a scale of two flat pans, a coffin of
# plank lines — sitting in a world of soft gradients it did not belong to.
# ONE light model for everything solid, so a scene is lit like a scene:
# a key light from the upper-left, a lit face falling to a shadow face, a
# rim on the lit edge, an ink edge, and a contact shadow where a thing
# meets the ground. `scene_author.craft_problems` MEASURES it: a frame
# whose hero band is mostly exact-colour slabs is refused as clip art.

KEY = (-0.55, -0.83)                 # where the light comes from (unit-ish)
KEY_LIT = 1.0                        # the lit face is the colour itself
KEY_SHADE = look.ILLU_SHADE          # the shadow face = colour * this
# The edge is a soft ink line, not a cartoon outline, and the rim carries the
# silhouette instead (operator 2026-10-07: "it just needs to look cleaner").
# A 4px line at 90% read as clip art at phone size.
KEY_RIM = 0.50                       # rim = colour mixed this far to white
EDGE_K = 0.60                        # the ink edge = colour * this
EDGE_W = 2.0                         # ...this wide
EDGE_A = 0.7                         # ...at this opacity
FINISH = 0.55                        # strength of finish(), every frame
FINISHES = ("matte", "gloss", "metal", "glass", "ice")


_GRAIN = None


def _grain_surface():
    """A tile of paper grain: one-level noise, repeated. Painted over every
    lit solid so no two pixels of a surface are exactly alike — the way
    printed colour never is — which also kills gradient banding."""
    global _GRAIN
    if _GRAIN is None:
        import random
        rnd = random.Random(7)
        n = 64
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        buf = surf.get_data()
        for i in range(n * n):
            v = rnd.choice((0, 255))
            a = 10                                        # ~4% of a level
            buf[i * 4:i * 4 + 4] = bytes((v * a // 255, v * a // 255, v * a // 255, a))
        surf.mark_dirty()
        _GRAIN = cairo.SurfacePattern(surf)
        _GRAIN.set_extend(cairo.EXTEND_REPEAT)
        _GRAIN.set_filter(cairo.FILTER_NEAREST)
    return _GRAIN


def grain(cr):
    """Paper grain over the CURRENT PATH (kept)."""
    cr.save()
    cr.clip_preserve()
    cr.identity_matrix()
    cr.set_source(_grain_surface())
    cr.paint()
    cr.restore()


def _path_box(cr):
    x0, y0, x1, y1 = cr.fill_extents()
    return x0, y0, x1, y1


def _lit_shade(rgb, finish):
    # the lit face is always lighter than the colour: a matte lit face equal
    # to the colour left the first half of every gradient a flat run
    lit = _mix(rgb, (255, 255, 255), 0.16 if finish in ("gloss", "metal") else 0.12)
    shade = _scale(rgb, KEY_SHADE)
    if finish == "ice":
        lit = _mix(rgb, (255, 255, 255), 0.25)
        shade = _mix(_scale(rgb, 0.78), (40, 80, 140), 0.25)
    return lit, shade


def solid(cr, rgb, finish="matte", a=1.0, edge=True, rim=True, depth=1.0):
    """Fill the CURRENT PATH as a lit solid: lit face (upper-left) falling
    to the shadow face (lower-right), a rim highlight along the lit edge,
    an ink edge. Use it where you would have called cr.fill() on a
    subject. `depth` 0..1 scales how far the shading falls; `finish` is
    one of FINISHES. Consumes the path."""
    x0, y0, x1, y1 = _path_box(cr)
    if x1 <= x0 or y1 <= y0:
        cr.new_path()
        return
    w, h = x1 - x0, y1 - y0
    lit, shade = _lit_shade(rgb, finish)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    L = max(w, h) * 0.75 * max(0.15, depth)
    g = cairo.LinearGradient(cx + KEY[0] * L, cy + KEY[1] * L,
                             cx - KEY[0] * L, cy - KEY[1] * L)
    g.add_color_stop_rgba(0.0, *_c(lit, a))
    g.add_color_stop_rgba(0.45, *_c(rgb, a))
    g.add_color_stop_rgba(1.0, *_c(shade, a))
    cr.save()
    cr.set_source(g)
    cr.fill_preserve()
    grain(cr)
    if finish in ("gloss", "metal", "glass", "ice"):
        # a specular streak across the lit third
        s = cairo.LinearGradient(x0, y0, x0 + w * 0.6, y0 + h * 0.9)
        hi = 0.42 if finish == "metal" else 0.30 if finish == "glass" else 0.22
        s.add_color_stop_rgba(0.00, 1, 1, 1, 0)
        s.add_color_stop_rgba(0.28, 1, 1, 1, hi * a)
        s.add_color_stop_rgba(0.40, 1, 1, 1, 0)
        if finish == "metal":                 # a second, dimmer band
            s.add_color_stop_rgba(0.62, 1, 1, 1, 0.14 * a)
            s.add_color_stop_rgba(0.72, 1, 1, 1, 0)
        cr.set_source(s)
        cr.fill_preserve()
    if rim:
        # the rim: the path's own outline, offset toward the light, clipped
        # to the shape so only the lit edge shows
        cr.save()
        cr.clip_preserve()
        cr.translate(-KEY[0] * 3.0, -KEY[1] * 3.0)
        cr.set_line_width(5.0)
        cr.set_source_rgba(*_c(_mix(rgb, (255, 255, 255), KEY_RIM), 0.55 * a))
        cr.stroke_preserve()
        cr.restore()
    if edge:
        cr.set_line_width(EDGE_W)
        cr.set_source_rgba(*_c(_scale(rgb, EDGE_K), EDGE_A * a))
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke_preserve()
    cr.restore()
    cr.new_path()


def box(cr, x, y, w, h, rgb, depth=None, finish="matte", a=1.0):
    """A three-quarter box standing on (x, y) its bottom-left: lit front,
    shadow side on the right, light top. `depth` defaults to 0.22 * w."""
    d = (w * 0.22) if depth is None else depth
    dy = d * 0.55
    lit, shade = _lit_shade(rgb, finish)
    cr.rectangle(x, y - h, w, h)
    solid(cr, rgb, finish=finish, a=a, rim=False)
    cr.move_to(x + w, y - h)
    cr.line_to(x + w + d, y - h - dy)
    cr.line_to(x + w + d, y - dy)
    cr.line_to(x + w, y)
    cr.close_path()
    solid(cr, shade, finish="matte", a=a, rim=False, depth=0.5)
    cr.move_to(x, y - h)
    cr.line_to(x + d, y - h - dy)
    cr.line_to(x + w + d, y - h - dy)
    cr.line_to(x + w, y - h)
    cr.close_path()
    solid(cr, _mix(lit, (255, 255, 255), 0.18), finish="matte", a=a, depth=0.5)


def cylinder(cr, x, y, w, h, rgb, finish="matte", a=1.0):
    """An upright cylinder standing on (x, y) its bottom-left: the body
    shaded across its width, an elliptical top."""
    ry = w * 0.16
    lit, shade = _lit_shade(rgb, finish)
    g = cairo.LinearGradient(x, 0, x + w, 0)
    g.add_color_stop_rgba(0.00, *_c(shade, a))
    g.add_color_stop_rgba(0.28, *_c(lit, a))
    g.add_color_stop_rgba(0.55, *_c(rgb, a))
    g.add_color_stop_rgba(1.00, *_c(_scale(shade, 0.85), a))
    cr.save()
    cr.rectangle(x, y - h, w, h)
    cr.set_source(g)
    cr.fill_preserve()
    grain(cr)
    cr.new_path()
    for yy in (y, y - h):                      # the bottom and the top rims
        cr.save()
        cr.translate(x + w / 2, yy)
        cr.scale(w / 2, ry)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        if yy == y:
            cr.set_source_rgba(*_c(shade, a))
            cr.fill()
        else:
            solid(cr, _mix(lit, (255, 255, 255), 0.12), finish=finish, a=a, depth=0.6)
    cr.set_line_width(EDGE_W)
    cr.set_source_rgba(*_c(_scale(rgb, EDGE_K), EDGE_A * a))
    cr.move_to(x, y - h)
    cr.line_to(x, y)
    cr.move_to(x + w, y - h)
    cr.line_to(x + w, y)
    cr.stroke()
    cr.restore()


def disc(cr, x, y, r, rgb, finish="matte", a=1.0):
    """A sphere: a radial highlight toward the key light, a dark limb, a
    rim and an edge."""
    lit, shade = _lit_shade(rgb, finish)
    g = cairo.RadialGradient(x + KEY[0] * r * 0.45, y + KEY[1] * r * 0.45, r * 0.08,
                             x, y, r * 1.05)
    g.add_color_stop_rgba(0.0, *_c(_mix(lit, (255, 255, 255), 0.25), a))
    g.add_color_stop_rgba(0.45, *_c(rgb, a))
    g.add_color_stop_rgba(1.0, *_c(shade, a))
    cr.save()
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.set_source(g)
    cr.fill_preserve()
    grain(cr)
    if finish in ("gloss", "metal", "glass"):
        cr.save()
        cr.clip_preserve()
        glow(cr, x + KEY[0] * r * 0.5, y + KEY[1] * r * 0.5, r * 0.45, (255, 255, 255),
             0.55 * a)
        cr.restore()
    cr.set_line_width(EDGE_W)
    cr.set_source_rgba(*_c(_scale(rgb, EDGE_K), EDGE_A * a))
    cr.stroke()
    cr.restore()


def contact_shadow(cr, x, y, w, a=0.35, h=None):
    """A soft shadow on the ground under a thing that stands at (x, y),
    `w` wide. Call it BEFORE drawing the thing."""
    h = h or max(10.0, w * 0.16)
    cr.save()
    cr.translate(x, y)
    cr.scale(max(1.0, w / 2), max(1.0, h / 2))
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0.0, 0, 0, 0, a)
    g.add_color_stop_rgba(0.6, 0, 0, 0, a * 0.55)
    g.add_color_stop_rgba(1.0, 0, 0, 0, 0)
    cr.set_source(g)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.fill()
    cr.restore()


def haze(cr, y0, y1, rgb, a=0.35):
    """Atmospheric depth: fade what is already painted between y0 and y1
    toward the sky colour, strongest at the top. Paint it over the far
    layers, before the hero."""
    g = cairo.LinearGradient(0, y0, 0, y1)
    g.add_color_stop_rgba(0.0, *_c(rgb, a))
    g.add_color_stop_rgba(1.0, *_c(rgb, 0))
    cr.set_source(g)
    cr.rectangle(0, y0, W, y1 - y0)
    cr.fill()


def vignette(cr, a=0.30):
    """Darken the corners so the eye lands on the hero. Last thing drawn
    before the text."""
    g = cairo.RadialGradient(W / 2, H * 0.46, H * 0.30, W / 2, H * 0.46, H * 0.78)
    g.add_color_stop_rgba(0.0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1.0, 0, 0, 0, a)
    cr.set_source(g)
    cr.rectangle(0, 0, W, H)
    cr.fill()


def finish(cr, strength=1.0):
    """The frame's last light pass, under the text: the key light falling
    across the whole picture from the upper-left (soft light, so lit areas
    glow and shadows keep their colour) and a gentle lift that takes the
    harshness off the darkest ink."""
    if strength <= 0:
        return
    cr.save()
    cr.set_operator(cairo.OPERATOR_SOFT_LIGHT)
    g = cairo.RadialGradient(W * 0.18, H * 0.12, 0, W * 0.18, H * 0.12, H * 0.95)
    g.add_color_stop_rgba(0.0, 1.0, 0.97, 0.90, 0.55 * strength)
    g.add_color_stop_rgba(0.55, 1.0, 0.97, 0.90, 0.12 * strength)
    g.add_color_stop_rgba(1.0, 0.10, 0.12, 0.22, 0.30 * strength)
    cr.set_source(g)
    cr.rectangle(0, 0, W, H)
    cr.fill()
    cr.set_operator(cairo.OPERATOR_SCREEN)
    cr.set_source_rgba(0.16, 0.17, 0.22, 0.10 * strength)
    cr.rectangle(0, 0, W, H)
    cr.fill()
    cr.restore()


def edge(cr, rgb, width=None, a=None):
    """Ink the current path's outline (keeps nothing)."""
    width = EDGE_W if width is None else width
    a = EDGE_A if a is None else a
    cr.set_line_width(width)
    cr.set_source_rgba(*_c(_scale(rgb, EDGE_K), a))
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.stroke()


def pil_surface(img):
    """A PIL RGBA image as a premultiplied cairo surface."""
    img = img.convert("RGBA")
    w, h = img.size
    try:
        # the same premultiply (`c * a // 255`), vectorised: the per-pixel
        # Python loop was 1.5 s on a full frame (2026-10-01)
        import numpy as _np
        px = _np.frombuffer(img.tobytes("raw", "BGRA"), dtype=_np.uint8)
        px = px.reshape(-1, 4).astype(_np.uint16)
        a_ = px[:, 3:4]
        px[:, :3] = px[:, :3] * a_ // 255
        raw = bytearray(px.astype(_np.uint8).tobytes())
    except Exception:  # noqa: BLE001 — no numpy: the loop
        raw = bytearray(img.tobytes("raw", "BGRA"))
        for i in range(0, len(raw), 4):          # premultiply
            a = raw[i + 3]
            if a < 255:
                raw[i] = raw[i] * a // 255
                raw[i + 1] = raw[i + 1] * a // 255
                raw[i + 2] = raw[i + 2] * a // 255
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    if stride != w * 4:
        buf = bytearray(stride * h)
        for y in range(h):
            buf[y * stride:y * stride + w * 4] = raw[y * w * 4:(y + 1) * w * 4]
        raw = buf
    return cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, w, h,
                                              stride)


# ----------------------------------------------------------------- type ---

_FACES = {"display": "Anton", "bold": "Inter", "text": "Inter"}


def _face(cr, face, size):
    fam = _FACES.get(face, "Inter")
    weight = (cairo.FONT_WEIGHT_NORMAL if face in ("display", "text")
              else cairo.FONT_WEIGHT_BOLD)
    cr.select_font_face(fam, cairo.FONT_SLANT_NORMAL, weight)
    cr.set_font_size(size)


def text_w(cr, s, size, face="bold"):
    _face(cr, face, size)
    return cr.text_extents(s).x_advance


def fit_size(cr, s, size, max_w, face="bold", floor=22):
    while size > floor and text_w(cr, s, size, face) > max_w:
        size -= 2
    return size


def _ground_under(cr, x, y, w, h):
    """Mean luminance (0-255) of what is already painted under a box, or
    None when the target cannot be read. A 12x4 sample: cheap per label."""
    try:
        surf = cr.get_target()
        surf.flush()
        sw, sh = surf.get_width(), surf.get_height()
        stride = surf.get_stride()
        buf = surf.get_data()
        tot = n = 0
        for i in range(12):
            for j in range(4):
                px = int(x + (i + 0.5) * w / 12)
                py = int(y + (j + 0.5) * h / 4)
                if 0 <= px < sw and 0 <= py < sh:
                    o = py * stride + px * 4          # BGRA, premultiplied
                    b_, g_, r_, a_ = buf[o], buf[o + 1], buf[o + 2], buf[o + 3]
                    if a_ == 0:
                        continue
                    tot += 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_
                    n += 1
        return tot / n if n else None
    except Exception:  # noqa: BLE001 — unreadable target: keep the ink
        return None


#: While a frame is being drawn, text is COLLECTED here and painted last
#: (`text_layer`). None outside a frame loop: text draws immediately.
_TEXT_LAYER = None


class text_layer:
    """Every label drawn inside this block is painted AFTER the art.

    Props and Data were drawn over the numbers they were there to show: "the
    mascot and the crane beam cover the '25.8M boxes' headline", "a falling
    log passes over the headline number", "the YOURS box overlaps the TEU"
    (the judge, 2026-09-24). Each was a draw-order accident in one scene; the
    rule that ends all of them is that nothing is drawn on top of text.
    The ink check then samples the finished picture, not a half-drawn one.
    """

    def __init__(self, cr):
        self.cr = cr

    def __enter__(self):
        global _TEXT_LAYER
        self._prev, _TEXT_LAYER = _TEXT_LAYER, []
        return self

    def __exit__(self, *exc):
        global _TEXT_LAYER
        pending, _TEXT_LAYER = _TEXT_LAYER, self._prev
        for m, args in pending or []:
            self.cr.save()
            self.cr.set_matrix(m)
            _draw_text(self.cr, *args)
            self.cr.restore()
        return False


def text(cr, s, x, y, size, rgb=look.INK, face="bold", anchor="left",
         alpha=1.0, shadow=True):
    """Draw `s` with its baseline at y. Returns its (x0, y0, x1, y1) box."""
    _face(cr, face, size)
    ext = cr.text_extents(s)
    if anchor == "center":
        x -= ext.x_advance / 2
    elif anchor == "right":
        x -= ext.x_advance
    if _TEXT_LAYER is not None:
        # with the transform in force NOW — a scene that translated or
        # scaled before its label must get it back when the label is painted
        _TEXT_LAYER.append((cr.get_matrix(),
                            (s, x, y, size, rgb, face, alpha, shadow)))
        return (x + ext.x_bearing, y + ext.y_bearing,
                x + ext.x_bearing + ext.width, y + ext.y_bearing + ext.height)
    return _draw_text(cr, s, x, y, size, rgb, face, alpha, shadow)


def _draw_text(cr, s, x, y, size, rgb, face, alpha, shadow):
    _face(cr, face, size)
    ext = cr.text_extents(s)
    # THE INK IS CHOSEN AGAINST WHAT IS ACTUALLY UNDER IT. A label's colour
    # was picked for the palette, not for the pixels behind it: "'3.6x the
    # 1996 ship' is pale blue on blue water and barely visible", "the white
    # caption ... is low-contrast against the pale sky" (the judge,
    # 2026-09-24). The ground under the text box is sampled; if the chosen
    # ink is too close to it, the ink that reads there is used instead, and
    # the outline takes the opposite tone.
    out_rgb = (0.02, 0.03, 0.08)
    # in DEVICE pixels: a scene may have scaled or moved the canvas
    _dx0, _dy0 = cr.user_to_device(x + ext.x_bearing, y + ext.y_bearing)
    _dx1, _dy1 = cr.user_to_device(x + ext.x_bearing + ext.width,
                                   y + ext.y_bearing + ext.height)
    bg = _ground_under(cr, min(_dx0, _dx1), min(_dy0, _dy1),
                       abs(_dx1 - _dx0), abs(_dy1 - _dy0))
    if bg is not None:
        lt = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        if abs(lt - bg) < 95:
            rgb = look.INK if bg < 128 else look.INK_ON_LIGHT
            if bg >= 128:
                out_rgb = (0.97, 0.97, 1.0)
    if shadow and alpha > 0:
        # A DARK OUTLINE, not just a drop shadow: grey values over an orange
        # sky and a number over a pale sun were "faint ... nearly disappears"
        # in the first previews. An outline reads on any part of any world.
        cr.move_to(x, y)
        cr.text_path(s)
        cr.set_source_rgba(*out_rgb, 0.78 * alpha)
        cr.set_line_width(max(3.0, min(9.0, size * 0.13)))
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()
    cr.set_source_rgba(*_c(rgb, alpha))
    cr.move_to(x, y)
    cr.show_text(s)
    return (x + ext.x_bearing, y + ext.y_bearing,
            x + ext.x_bearing + ext.width, y + ext.y_bearing + ext.height)


def wrap2(cr, s, size, max_w, face="bold", floor=22):
    """One line if it fits at >= floor, else two balanced lines."""
    sz = fit_size(cr, s, size, max_w, face, floor)
    if text_w(cr, s, sz, face) <= max_w or " " not in s:
        return sz, [s]
    words = s.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        wmax = max(text_w(cr, a, size, face), text_w(cr, b, size, face))
        if best is None or wmax < best[0]:
            best = (wmax, a, b)
    _, a, b = best
    sz = min(fit_size(cr, a, size, max_w, face, floor),
             fit_size(cr, b, size, max_w, face, floor))
    return sz, [a, b]


# --------------------------------------------------------------- worlds ---

_RND = random.Random(11)
_STARS = [(_RND.uniform(0, W), _RND.uniform(0, H * 0.8), _RND.uniform(0.7, 2.4),
           _RND.uniform(0, 6.28)) for _ in range(260)]
_TOWERS = [(_RND.uniform(0, W), _RND.uniform(160, 520), _RND.uniform(60, 130))
           for _ in range(22)]
_FISH = [(_RND.uniform(0, 1), _RND.uniform(0.2, 0.9), _RND.uniform(0.6, 1.2),
          _RND.choice([-1, 1])) for _ in range(10)]

#: Topic words that put a story in a world. Checked in order; the first
#: world whose words appear wins, and a story matching none gets "dusk".
WORLD_WORDS = (
    ("space", ("space", "orbit", "satellite", "moon", "mars", "planet",
               "astronaut", "rocket", "launch", "asteroid", "star")),
    ("ocean", ("ocean", "sea", "ship", "shipping", "container", "fish",
               "coral", "reef", "port", "marine", "whale", "tide",
               "shark", "coast", "flood", "river", "water")),
    ("farm", ("farm", "crop", "harvest", "wheat", "corn", "coffee", "cocoa",
              "food", "grocery", "egg", "beef", "cattle", "dairy", "rice",
              "agricultur", "bee", "fruit", "vegetable")),
    ("industry", ("factory", "steel", "manufactur", "plant", "coal", "oil",
                  "gas", "mining", "mine", "emission", "carbon", "e-waste",
                  "waste", "recycl", "battery", "chip", "semiconductor",
                  "power", "energy", "electric")),
    ("city", ("city", "urban", "rent", "housing", "home", "house", "mortgage",
              "commute", "traffic", "office", "job", "wage", "worker",
              "neighborhood", "teen", "school", "store", "retail")),
)


def world_for(insight) -> str:
    """The world one beat's words point at. Deterministic."""
    return world_for_text(" ".join(str(x or "") for x in (
        getattr(insight, "topic", ""), getattr(insight, "main_insight", ""),
        *[getattr(p, "label", "") for p in (getattr(insight, "items", None)
                                            or [])[:6]])))


def world_for_story(st) -> str:
    """ONE world for the whole video, from its title and every beat's words.
    A video that walks from dusk into a farm between beats reads as two
    videos cut together."""
    parts = [getattr(st, "title", ""), getattr(st, "hook", "")]
    for sg in getattr(st, "segments", None) or []:
        ins = getattr(sg, "insight", None)
        parts += [getattr(sg, "topic", ""), getattr(ins, "topic", "")]
    return world_for_text(" ".join(str(x or "") for x in parts))


def world_for_text(blob: str) -> str:
    blob = (blob or "").lower()
    for name, words in WORLD_WORDS:
        if any(re.search(r"\b" + re.escape(w), blob) for w in words):
            return name
    return "dusk"


def _clouds(cr, t, y0, tone, n=5, speed=38, a=0.20):
    """Soft, flat-bottomed cloud banks: overlapping radial puffs over a long
    low ellipse, so they read as cloud and not as a row of bubbles."""
    for i in range(n):
        x = (i * 470 + t * speed * (1 + i % 2)) % (W + 500) - 250
        y = y0 + i * 64
        cr.save()
        cr.translate(x + 90, y + 18)
        cr.scale(1.0, 0.32)
        glow(cr, 0, 0, 170, tone, a * 0.9)
        cr.restore()
        for dx, dy, r in ((0, 0, 48), (55, -22, 62), (120, -6, 52), (170, 8, 38)):
            glow(cr, x + dx, y + dy, r * 1.25, tone, a * 1.4)


def world_back(cr, name, t):
    """Sky, light and far terrain: everything BEHIND the data."""
    w = look.world(name)
    vgrad(cr, w["sky"])
    if name == "space":
        for x, y, r, ph in _STARS:
            cr.set_source_rgba(*_c(w["mote"], 0.30 + 0.35 * math.sin(t * 2.2 + ph)))
            cr.arc(x, y, r, 0, 2 * math.pi)
            cr.fill()
        glow(cr, 260 + 30 * math.sin(t * 0.2), 520, 420, w["glow"], 0.16)
        glow(cr, 860, 980 + 20 * math.cos(t * 0.25), 360, look.ACCENTS["rose"][0], 0.08)
        # a planet's limb as the ground
        rg = cairo.RadialGradient(540, GROUND_Y + 1500, 1300, 540, GROUND_Y + 1500, 1560)
        rg.add_color_stop_rgba(0, *_c(w["mid"]))
        rg.add_color_stop_rgba(1, *_c(w["far"]))
        cr.set_source(rg)
        cr.arc(540, GROUND_Y + 1520, 1540, 0, 2 * math.pi)
        cr.fill()
        return
    if name == "ocean":
        for i in range(6):                   # light rays sway
            x = 60 + i * 190 + 36 * math.sin(t * 0.7 + i)
            cr.move_to(x, 0)
            cr.line_to(x + 70, 0)
            cr.line_to(x + 230, 1300)
            cr.line_to(x + 110, 1300)
            cr.close_path()
            lg = cairo.LinearGradient(0, 0, 0, 1300)
            lg.add_color_stop_rgba(0, 1, 1, 1, 0.13)
            lg.add_color_stop_rgba(1, 1, 1, 1, 0)
            cr.set_source(lg)
            cr.fill()
        for fx, fy, fs, d in _FISH:
            x = ((fx * W + d * t * 150 * fs) % (W + 300)) - 150
            y = STAGE_TOP + 120 + fy * 760
            _fish(cr, x, y, fs * 1.7, d, w["mote"], 0.55)
        hills(cr, GROUND_Y - 40, 70, 150, 0.8, w["far"], w["rim"])
        return
    gx = 780 + 20 * math.sin(t * 0.3)
    gy = GROUND_Y - 420
    glow(cr, gx, gy, 460, w["glow"], 0.50 + 0.06 * math.sin(t * 1.3))
    # No sun DISK: a pale disk sits exactly where the right-hand values land
    # ("the '$2' label sits on the pale sun disk and nearly disappears").
    # The glow alone carries the light.
    _clouds(cr, t, 330, look.INK, a=0.16 if name == "city" else 0.20)
    if name == "city":
        for x, h, bw in _TOWERS:
            top = GROUND_Y - 60 - h
            cr.set_source_rgba(*_c(w["far"]))
            cr.rectangle(x, top, bw, h + 80)
            cr.fill()
            for r_ in range(int(h // 34)):
                for c_ in range(int(bw // 26)):
                    on = math.sin(x * 0.7 + r_ * 3.1 + c_ * 1.7 + t * 0.9) > 0.35
                    if on:
                        cr.set_source_rgba(*_c(w["mote"], 0.55))
                        cr.rectangle(x + 8 + c_ * 26, top + 12 + r_ * 34, 10, 14)
                        cr.fill()
        return
    if name == "industry":
        for i, (x, h) in enumerate(((140, 420), (330, 520), (820, 460), (960, 380))):
            cr.set_source_rgba(*_c(w["far"]))
            cr.rectangle(x, GROUND_Y - 60 - h, 56, h + 80)
            cr.fill()
            for k in range(5):               # smoke drifts up and away
                ph = (t * 0.25 + k / 5 + i * 0.13) % 1
                cr.set_source_rgba(*_c(w["mid"], 0.45 * (1 - ph)))
                cr.arc(x + 28 + ph * 120, GROUND_Y - 80 - h - ph * 360,
                       26 + ph * 60, 0, 2 * math.pi)
                cr.fill()
        hills(cr, GROUND_Y - 20, 60, 190, 2.1, w["mid"], w["rim"])
        return
    hills(cr, GROUND_Y - 150, 170, 170, 0.4 + t * 0.01, w["far"])
    hills(cr, GROUND_Y - 40, 110, 120, 1.9 - t * 0.012, w["mid"], w["rim"])


def world_ground(cr, name, t):
    """The ground plane the data stands on (drawn before the data)."""
    w = look.world(name)
    cr.move_to(0, GROUND_Y)
    for x in range(0, W + 21, 20):
        cr.line_to(x, GROUND_Y + 10 * math.sin(x / 140 + 0.6))
    cr.line_to(W, H)
    cr.line_to(0, H)
    cr.close_path()
    g = cairo.LinearGradient(0, GROUND_Y, 0, H)
    g.add_color_stop_rgba(0, *_c(w["near"]))
    g.add_color_stop_rgba(1, *_c(_scale(w["near"], 0.45)))
    cr.set_source(g)
    cr.fill()
    cr.set_line_width(4)
    cr.set_source_rgba(*_c(w["rim"], 0.6))
    cr.move_to(0, GROUND_Y)
    for x in range(0, W + 21, 20):
        cr.line_to(x, GROUND_Y + 10 * math.sin(x / 140 + 0.6))
    cr.stroke()
    if name == "farm":                       # field rows running to the horizon
        for i in range(-8, 9):
            cr.set_source_rgba(*_c(w["mid"], 0.55))
            cr.move_to(540 + i * 24, GROUND_Y + 6)
            cr.line_to(540 + i * 190, H)
            cr.set_line_width(5)
            cr.stroke()
    if name == "city":                       # headlights along the street
        for k in range(7):
            x = (k * 190 + t * 160) % (W + 120) - 60
            glow(cr, x, GROUND_Y + 70, 26, w["mote"], 0.7)


def world_air(cr, name, t):
    """The world's one strong mover, IN FRONT of everything.

    Each world carries ONE strong mover — bubbles in the ocean, embers
    over industry, a meteor in space, birds over land — because faint drift
    alone measured as frozen: ocean and industry both held a 52-frame still
    run once the data had built (`tests/test_the_illustrated_arm.py`)."""
    w = look.world(name)
    if name == "ocean":
        for k in range(14):                   # bubbles rise past the data
            ph = (t * 0.45 + k / 14) % 1
            x = 70 + (k * 149) % (W - 140) + 18 * math.sin(t * 2 + k)
            y = H - ph * (H - 200)
            cr.set_source_rgba(*_c(w["mote"], 0.55 * (1 - ph)))
            cr.set_line_width(3)
            cr.arc(x, y, 7 + 9 * ph, 0, 2 * math.pi)
            cr.stroke()
    elif name == "industry":
        for k in range(16):                   # embers drift up from the yard
            ph = (t * 0.35 + k / 16) % 1
            x = 60 + (k * 131) % (W - 120) + 30 * math.sin(t * 1.4 + k)
            y = GROUND_Y + 40 - ph * 1100
            glow(cr, x, y, 16, w["mote"], 0.75 * (1 - ph))
    elif name == "space":
        ph = (t * 0.22) % 1                   # a meteor crosses every few s
        mx, my = -200 + ph * (W + 600), 380 + ph * 520
        lg = cairo.LinearGradient(mx - 260, my - 150, mx, my)
        lg.add_color_stop_rgba(0, *_c(w["mote"], 0))
        lg.add_color_stop_rgba(1, *_c(w["mote"], 0.9))
        cr.set_source(lg)
        cr.set_line_width(5)
        cr.move_to(mx - 260, my - 150)
        cr.line_to(mx, my)
        cr.stroke()
    else:
        for k in range(5):                    # birds cross the sky
            ph = (t * 0.08 + k * 0.21) % 1
            bx = -80 + ph * (W + 160)
            by = 520 + 60 * k + 18 * math.sin(t * 2 + k)
            flap = 10 * math.sin(t * 9 + k)
            cr.set_source_rgba(*_c(w["near"], 0.8))
            cr.set_line_width(4)
            cr.move_to(bx - 22, by - flap)
            cr.line_to(bx, by)
            cr.line_to(bx + 22, by - flap)
            cr.stroke()
    # No speck layer over the world. 160 drifting motes in front of every
    # frame read as SNOW on every second of every video (operator,
    # 2026-09-23: "a bug that happened to affect every video ... snow
    # overlay on every video on every second of it"). The world's one
    # strong mover above is its motion.


def _fish(cr, x, y, s, d, rgb, a=1.0):
    cr.save()
    cr.translate(x, y)
    cr.scale(d * s, s)
    cr.set_source_rgba(*_c(rgb, a))
    cr.move_to(-30, 0)
    cr.curve_to(-10, -16, 20, -14, 30, 0)
    cr.curve_to(20, 14, -10, 16, -30, 0)
    cr.fill()
    cr.move_to(-26, 0)
    cr.line_to(-44, -12)
    cr.line_to(-44, 12)
    cr.close_path()
    cr.fill()
    cr.restore()


# ----------------------------------------------------------------- host ---


def _host(cr, role, phase, insight, kind, cx, foot_y, height):
    """Data, posed for this moment, standing with his feet at (cx, foot_y)."""
    img = None
    try:
        from data_learning import viz_scene as vs
        # his clock is this beat's phase — set for THIS call only. Left set,
        # it froze every later scene_host call in the process on one phase
        # (the current look's mascot too).
        _prev = getattr(vs, "_BEAT_PHASE", None)
        vs._BEAT_PHASE = phase
        try:
            img = vs.scene_host(role, phase, insight, kind)
        finally:
            vs._BEAT_PHASE = _prev
    except Exception:  # noqa: BLE001 — no rig available: no host, not a crash
        img = None
    if img is None:
        return None
    k = height / max(1, img.height)
    img = img.resize((max(1, int(img.width * k)), max(1, int(height))))
    surf = pil_surface(img)
    x = int(cx - img.width / 2)
    y = int(foot_y - img.height)
    glow(cr, cx, foot_y - 6, img.width * 0.55, (0, 0, 0), 0.35)   # his shadow
    cr.set_source_surface(surf, x, y)
    cr.paint()
    return (x, y, x + img.width, y + img.height)


def _agent(cr, verb, phase, insight, kind, at, height, floor=None,
           flip=False):
    """Data DOING the verb, his anchor on ``at`` — the world's own
    `place_agent`. Plans with the scene kit's placer and paints only the
    SPRITE (and his ladder, in cairo): a full-frame PIL layer per frame went
    through `pil_surface` at 1.5 s a frame. Returns (box, tip) or
    (None, None)."""
    try:
        from data_learning import viz_scene as vs
        _prev = getattr(vs, "_BEAT_PHASE", None)
        vs._BEAT_PHASE = phase
        try:
            plan = vs.plan_agent(verb, phase, insight, kind, at, height=height,
                                 floor=floor, xlim=(30, W - 30), flip=flip)
        finally:
            vs._BEAT_PHASE = _prev
    except Exception:  # noqa: BLE001 — no rig available: no host, not a crash
        return None, None
    if plan is None:
        return None, None
    sprite, (x, y), box, tip, ladder = plan
    if ladder is not None:
        lcx, feet, floor_y, lw = ladder
        hw = max(28, int(lw * 0.22))
        cr.set_source_rgba(*_c(look.INK, 0.78))
        cr.rectangle(lcx - hw - 6, feet - 6, 2 * hw + 12, 16)
        cr.fill()
        cr.set_source_rgba(*_c(look.INK, 0.59))
        cr.set_line_width(8)
        for sx in (lcx - hw, lcx + hw):
            cr.move_to(sx, feet)
            cr.line_to(sx, floor_y)
        cr.stroke()
        cr.set_line_width(6)
        yy = feet + 56
        while yy < floor_y - 20:
            cr.move_to(lcx - hw, yy)
            cr.line_to(lcx + hw, yy)
            yy += 56
        cr.stroke()
    glow(cr, (box[0] + box[2]) / 2, box[3] - 6, (box[2] - box[0]) * 0.55,
         (0, 0, 0), 0.35)
    cr.set_source_surface(pil_surface(sprite), x, y)
    cr.paint()
    return box, tip


def _cairo_stream(cr, src, dst, rgb, t):
    """What he pours, in the world: a swaying column to the surface."""
    sx, sy = src
    dx, dy = dst
    if dy <= sy + 6:
        return
    n = max(2, int((dy - sy) / 14))
    cr.set_source_rgba(*_c(rgb, 0.95))
    cr.set_line_width(16)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(sx, sy)
    for k in range(1, n + 1):
        u = k / n
        cr.line_to(sx + (dx - sx) * u + 5.0 * math.sin(u * 9.0 + t * 40.0) * (1 - u),
                   sy + (dy - sy) * u)
    cr.stroke()
    for k in range(5):
        a = (k / 5.0) * math.pi + t * 7.0
        r_ = 10 + 8 * ((k * 7) % 3)
        glow(cr, dx + math.cos(a) * r_ * 2.2, dy - abs(math.sin(a)) * r_, 9,
             rgb, 0.8)


# ----------------------------------------------------------------- data ---


def _items(insight):
    return [p for p in (getattr(insight, "items", None) or [])
            if isinstance(getattr(p, "value", None), (int, float))]


def _fmt(v, unit):
    try:
        from data_learning import charts
        return charts._ulabel(v, unit, group=True)
    except Exception:  # noqa: BLE001
        return f"{v:,.0f}"


def _title(cr, insight, a=1.0):
    s = str(getattr(insight, "topic", "") or "").strip()
    if not s:
        return
    sz, lines = wrap2(cr, s, 52, W - 120, "bold", 30)
    for k, ln in enumerate(lines):
        text(cr, ln, W / 2, TITLE_Y + k * (sz + 12), sz, look.INK,
             anchor="center", alpha=a)


def _column(cr, x, w, base, h, lit, shade, top):
    """A two-tone shaded column: lit face, shadow face, and its top."""
    if h <= 0:
        return
    d = w * 0.22
    cr.set_source_rgba(*_c(lit))
    cr.rectangle(x, base - h, w * 0.64, h)
    cr.fill()
    cr.set_source_rgba(*_c(shade))
    cr.rectangle(x + w * 0.64, base - h, w * 0.36, h)
    cr.fill()
    cr.set_source_rgba(*_c(top))
    cr.move_to(x, base - h)
    cr.line_to(x + d, base - h - d * 0.55)
    cr.line_to(x + w + d, base - h - d * 0.55)
    cr.line_to(x + w, base - h)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(*_c(shade))
    cr.move_to(x + w, base - h)
    cr.line_to(x + w + d, base - h - d * 0.55)
    cr.line_to(x + w + d, base - d * 0.55)
    cr.line_to(x + w, base)
    cr.close_path()
    cr.fill()


def draw_columns(cr, insight, world, t, reveal, phase):
    """RANK: each item a shaded column standing in the world, height = value.
    The subject wears the story's accent; Data stands on top of it."""
    items = _items(insight)[:6]
    if len(items) < 2 or any(p.value < 0 for p in items):
        return None
    w_ = look.world(world)
    lit, shade, rim = accent_pair(getattr(insight, "topic", ""))
    sub = getattr(insight, "highlight_label", None) or items[0].label
    vmax = max(p.value for p in items) or 1.0
    n = len(items)
    slot = (W - 160) / n
    cw = min(170.0, slot * 0.62)
    base = GROUND_Y + 4
    room = base - (STAGE_TOP + 150 + HOST_H)
    anchors, lead = [], None
    for i, p in enumerate(items):
        k = pop(seg(reveal, i * 0.08, 0.55 + i * 0.08))
        h = room * (p.value / vmax) * max(0.0, k)
        x = 80 + slot * i + (slot - cw) / 2
        is_sub = str(p.label) == str(sub)
        f_lit, f_sh = (lit, shade) if is_sub else w_["form"]
        _column(cr, x, cw, base, h, f_lit, f_sh,
                _mix(f_lit, (255, 255, 255), 0.25))
        if h > 40 and is_sub:
            # light streaming up past the leader, against the sky — a bright
            # accent face (gold) leaves a white bead too faint to register
            for sx in (x - 16, x + cw + cw * 0.22 + 16):
                flow(cr, [(sx, base), (sx, base - h)], t + (0.07 if sx > x else 0),
                     _mix(f_lit, (255, 255, 255), 0.6), spacing=64, speed=480,
                     r=10, a=0.95)
        if h > 40:
            cr.save()
            cr.rectangle(x, base - h, cw * 0.64, h)
            cr.clip()
            flow(cr, [(x + cw * 0.32, base), (x + cw * 0.32, base - h)], t,
                 _mix(f_lit, (255, 255, 255), 0.75), spacing=64, speed=480,
                 r=13 if is_sub else 9, a=1.0 if is_sub else 0.7)
            cr.restore()
        if world == "city" and h > 60:                    # lit windows
            for r_ in range(int((h - 30) // 44)):
                for c_ in range(3):
                    if math.sin(i * 5 + r_ * 2.3 + c_ * 1.9 + t * 0.7) > -0.2:
                        cr.set_source_rgba(*_c(w_["mote"], 0.75))
                        cr.rectangle(x + cw * (0.10 + c_ * 0.18), base - h + 22 + r_ * 44,
                                     cw * 0.1, 16)
                        cr.fill()
        va = seg(reveal, 0.30 + i * 0.08, 0.55 + i * 0.08)
        vs_ = 64 if is_sub else 46
        # the subject's number rides ABOVE Data, who stands on its roof
        vtop = base - h - cw * 0.22 - 26 - (HOST_H + 10 if is_sub else 0)
        text(cr, _fmt(p.value, getattr(insight, "unit", "")), x + cw / 2, vtop,
             fit_size(cr, _fmt(p.value, getattr(insight, "unit", "")), vs_, slot - 8,
                      "display"), look.INK if is_sub else look.INK_2,
             face="display", anchor="center", alpha=va)
        sz, lines = wrap2(cr, str(p.label), 30, slot - 10, "bold", 20)
        for li, ln in enumerate(lines):
            text(cr, ln, x + cw / 2, base + 60 + li * (sz + 8), sz,
                 look.INK if is_sub else look.INK_2, anchor="center",
                 alpha=seg(reveal, 0.1, 0.4))
        anchors.append({"value": float(p.value), "cx": x + cw / 2, "cy": vtop,
                        "w": 160.0, "h": 70.0, "measured": False})
        if is_sub:
            lead = (x + 22, base - h)
    # HE BUILDS THE SUBJECT'S COLUMN: hands on its top-left corner as it
    # rises, from a ladder on the ground. Riding its roof up he was "standing
    # on top of the tallest bar", carried by the number.
    return lead, anchors, ("agent", "stack", {"floor": base})


def draw_ridge(cr, insight, world, t, reveal, phase):
    """TREND: the series is the crest of a ridge; Data drives it to 'now'."""
    items = _items(insight)
    if len(items) < 3:
        return None
    lit, shade, rim = accent_pair(getattr(insight, "topic", ""))
    vals = [p.value for p in items]
    lo, hi = min(vals), max(vals)
    if lo >= 0 and lo < hi * 0.6:
        lo = 0.0                              # a rise from zero reads true
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - (pad if lo != 0 else 0), hi + pad
    top_y, base = STAGE_TOP + 130 + HOST_H, GROUND_Y + 4
    x0, x1 = 100, W - 100
    n = len(items)
    pts = [(x0 + (x1 - x0) * i / (n - 1),
            base - (base - top_y) * (v - lo) / (hi - lo)) for i, v in enumerate(vals)]
    u = ease(seg(reveal, 0.0, 0.9))
    xr = x0 + (x1 - x0) * u
    cr.save()
    cr.rectangle(0, 0, xr + 2, H)
    cr.clip()
    ridge_path(cr, pts, base)
    g = cairo.LinearGradient(0, top_y, 0, base)
    g.add_color_stop_rgba(0, *_c(lit))
    g.add_color_stop_rgba(1, *_c(shade))
    cr.set_source(g)
    cr.fill()
    cr.set_line_width(6)
    cr.set_source_rgba(*_c(rim))
    cr.move_to(*pts[0])
    for pt in pts[1:]:
        cr.line_to(*pt)
    cr.stroke()
    flow(cr, pts, t, _mix(rim, (255, 255, 255), 0.6), spacing=52, speed=520,
         r=13, a=1.0)
    cr.restore()
    # where the walk has reached, on the crest
    i = min(n - 2, int((xr - x0) / ((x1 - x0) / (n - 1))))
    f = clamp((xr - pts[i][0]) / max(1e-6, pts[i + 1][0] - pts[i][0]))
    hx = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
    hy = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
    unit = getattr(insight, "unit", "")
    idx = sorted({0, n - 1, vals.index(max(vals)), vals.index(min(vals))})
    anchors = []
    for j in idx:
        px, py = pts[j]
        if px > xr + 1:
            continue
        a = seg(reveal, (px - x0) / (x1 - x0) * 0.9, (px - x0) / (x1 - x0) * 0.9 + 0.1)
        glow(cr, px, py, 30, rim, 0.8 * a)
        cr.set_source_rgba(*_c(look.INK, a))
        cr.arc(px, py, 8, 0, 2 * math.pi)
        cr.fill()
        s = _fmt(vals[j], unit)
        _lift = HOST_H + 20 if j == n - 1 else 0
        text(cr, s, clamp(px, 80, W - 80), py - 44 - _lift,
             fit_size(cr, s, 46 if j == n - 1 else 38, 260, "display"),
             look.INK if j == n - 1 else look.INK_2, face="display",
             anchor="center", alpha=a)
        anchors.append({"value": float(vals[j]), "cx": px, "cy": py - 60,
                        "w": 160.0, "h": 60.0, "measured": False})
    for j in sorted({0, n // 2, n - 1}):     # the years stand under the ridge
        lab = str(getattr(items[j], "period", None) or items[j].label)
        text(cr, lab, clamp(pts[j][0], 60, W - 60), base + 60, 32, look.INK,
             anchor="center", alpha=seg(reveal, 0.05, 0.3))
    # HE DRIVES THE CREST: a car along the ridge to 'now' — the series is
    # a road he is taking, not a rail he is carried along.
    return (hx, hy + 6), anchors, ("agent", "travel", {}), 190


def _share_value(insight):
    items = _items(insight)
    if not items:
        return None, None
    sub = getattr(insight, "highlight_label", None)
    p = next((x for x in items if str(x.label) == str(sub)), items[0])
    unit = str(getattr(insight, "unit", "") or "").lower()
    if "percent" in unit or unit in ("%", "pct", "share"):
        if 0 <= p.value <= 100:
            return p, p.value / 100.0
        return None, None
    tot = sum(x.value for x in items if x.value > 0)
    if len(items) >= 2 and tot > 0 and p.value >= 0:
        return p, p.value / tot
    return None, None


def draw_tank(cr, insight, world, t, reveal, phase):
    """SHARE: a glass tank in the world filling to the share; the rest stays
    empty glass. The number counts up as it fills."""
    p, frac = _share_value(insight)
    if p is None:
        return None
    lit, shade, rim = accent_pair(getattr(insight, "topic", ""))
    x0, x1 = 300, 780
    top, base = STAGE_TOP + 250, GROUND_Y - 6
    lvl = frac * ease(seg(reveal, 0.02, 0.45))
    ly = base - (base - top) * lvl
    # glass back
    cr.set_source_rgba(*_c(look.INK, 0.08))
    cr.rectangle(x0, top, x1 - x0, base - top)
    cr.fill()
    # liquid, with a moving surface
    if lvl > 0:
        cr.move_to(x0, base)
        for x in range(x0, x1 + 1, 10):
            cr.line_to(x, ly + 7 * math.sin(x / 38 + t * 3.0))
        cr.line_to(x1, base)
        cr.close_path()
        g = cairo.LinearGradient(x0, 0, x1, 0)
        g.add_color_stop_rgba(0, *_c(lit, 0.95))
        g.add_color_stop_rgba(0.62, *_c(lit, 0.95))
        g.add_color_stop_rgba(0.63, *_c(shade, 0.95))
        g.add_color_stop_rgba(1, *_c(shade, 0.95))
        cr.set_source(g)
        cr.fill()
        cr.save()
        cr.rectangle(x0, ly + 10, x1 - x0, base - ly - 10)
        cr.clip()
        for k in range(9):                   # bubbles stream up through it
            bx = x0 + 34 + k * (x1 - x0 - 68) / 8 + 10 * math.sin(t * 3 + k)
            flow(cr, [(bx, base), (bx, ly)], t + k * 0.13,
                 _mix(rim, (255, 255, 255), 0.5), spacing=90, speed=300,
                 r=7, a=0.8)
        cr.restore()
    # glass walls, rim light, ticks
    cr.set_line_width(6)
    cr.set_source_rgba(*_c(look.world(world)["rim"], 0.8))
    cr.move_to(x0, top)
    cr.line_to(x0, base)
    cr.line_to(x1, base)
    cr.line_to(x1, top)
    cr.stroke()
    # Ticks on the RIGHT wall: the left is where he stands, on his ladder,
    # and the rails ran through "75%".
    for q in range(1, 4):
        y = base - (base - top) * q / 4
        cr.set_source_rgba(*_c(look.INK_3, 0.9))
        cr.set_line_width(3)
        cr.move_to(x1 - 30, y)
        cr.line_to(x1, y)
        cr.stroke()
        text(cr, f"{q * 25}%", x1 + 14, y + 10, 26, look.INK_2, anchor="left")
    rest = [x for x in _items(insight) if x is not p]
    if rest and frac < 0.93:
        rl = str(rest[0].label) if len(rest) == 1 else "the rest"
        rs = f"{rl}  {(1 - frac) * 100:.0f}%"
        text(cr, rs, x1 - 18, (top + ly) / 2 + 12,
             fit_size(cr, rs, 30, (x1 - x0) * 0.55), look.INK_2, anchor="right",
             alpha=seg(reveal, 0.5, 0.8))
    shown = frac * 100 * ease(seg(reveal, 0.02, 0.45))
    s = f"{shown:.0f}%" if frac * 100 >= 10 else f"{shown:.1f}%"
    text(cr, s, W / 2, STAGE_TOP + 170, 120, look.INK, face="display",
         anchor="center", alpha=seg(reveal, 0.02, 0.2))
    sz, lines = wrap2(cr, str(p.label), 34, W - 160, "bold", 22)
    for li, ln in enumerate(lines):
        text(cr, ln, W / 2, GROUND_Y + 70 + li * (sz + 8), sz, look.INK_2,
             anchor="center", alpha=seg(reveal, 0.1, 0.4))
    anchors = [{"value": float(p.value), "cx": W / 2, "cy": STAGE_TOP + 130,
                "w": 300.0, "h": 120.0, "measured": False}]
    # HE FILLS IT. On a ladder at the tank's left rim, pouring from a bucket
    # — the level rises because he is pouring, and the stream lands on the
    # surface. He used to ride the level on a raft (operator, 2026-10-01:
    # "sits there and flails his arms like always. Why doesn't he have a
    # thing of water in his hands? ... he's the one that's making the water
    # rise"), and before that stood on a ledge "he never used" (the judge,
    # 2026-09-23).
    return ((x0 + 56, top - 26), anchors,
            ("agent", "fill", {"floor": GROUND_Y,
                               "stream_to": (x0 + 150, ly + 4),
                               "stream_rgb": _mix(lit, (255, 255, 255), 0.5)}),
            230)


#: What the claim is -> how it is drawn in a world. Claims not here fall back
#: to the current renderer, and `studio_render` records that they did.
DRAWINGS = {
    "rank": draw_columns, "dominance": draw_columns, "record": draw_columns,
    "duel": draw_columns, "before_after": draw_columns,
    "growth": draw_ridge, "decline": draw_ridge, "reversal": draw_ridge,
    "acceleration": draw_ridge, "volatile": draw_ridge, "cycle": draw_ridge,
    "share": draw_tank, "rate": draw_tank,
}


def drawing_for(insight):
    """(relationship, draw_fn) for this insight, or (relationship, None)."""
    try:
        from data_learning import relationships as rel
        r = rel.classify(insight)
    except Exception:  # noqa: BLE001
        r = None
    fn = DRAWINGS.get(r)
    # Percentages that add up to the whole ARE a share, whatever the
    # classifier called the pair ("By sea 80% / Everything else 20%" came
    # back as a duel and was drawn as two columns).
    _its = _items(insight)
    _u = str(getattr(insight, "unit", "") or "").lower()
    if (("percent" in _u or _u == "%") and 2 <= len(_its) <= 4
            and abs(sum(p.value for p in _its) - 100) <= 1.5):
        fn = draw_tank
    if fn is draw_ridge and len(_items(insight)) < 3:
        fn = draw_columns
    if fn is draw_tank and _share_value(insight)[0] is None:
        fn = draw_columns
    if fn is draw_columns and len(_items(insight)) < 2:
        fn = None
    return r, fn


def render_build(insight, out_dir: Path, name: str, frames: int = 90,
                 full_by: float = 0.85, world: str | None = None,
                 draw=None, t0: float = 0.0):
    """Render one beat as an illustrated world. Returns (pattern, anchors),
    or (None, []) when no illustrated drawing fits this data."""
    if draw is None:
        _r, draw = drawing_for(insight)
    if draw is None:
        return None, []
    world = world or world_for(insight)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    anchors = []
    kind = draw.__name__.replace("draw_", "")
    for f in range(frames):
        t = t0 + f / FPS
        reveal = min(1.0, (f + 1) / max(1.0, frames * full_by))
        phase = (f + 1) / frames
        cr = cairo.Context(surf)
        with text_layer(cr):
            world_back(cr, world, t)
            world_ground(cr, world, t)
            _title(cr, insight, a=seg(f, 0, 6))
            got = draw(cr, insight, world, t, reveal, phase)
            if got is None:
                return None, []
            (hx, hy), anc, role = got[:3]
            hgt = got[3] if len(got) > 3 else HOST_H
            if isinstance(role, tuple) and role and role[0] == "agent":
                # DATA IS THE CAUSE: the drawing names the verb and where
                # its moving part is; he is placed with his hands on it.
                _verb = role[1]
                _opts = role[2] if len(role) > 2 else {}
                _box, _tip = _agent(cr, _verb, phase, insight, kind, (hx, hy),
                                    hgt, floor=_opts.get("floor"),
                                    flip=_opts.get("flip", False))
                if _tip is not None and _opts.get("stream_to") is not None:
                    _cairo_stream(cr, _tip, _opts["stream_to"],
                                  _opts.get("stream_rgb", look.INK), t)
            else:
                _host(cr, role, phase, insight, kind, hx, hy + 4, hgt)
            world_air(cr, world, t)
        if f == frames - 1:
            anchors = anc
        surf.flush()
        surf.write_to_png(str(out_dir / f"{name}_build{f + 1:02d}.png"))
    insight.host_baked = True
    return str(out_dir / f"{name}_build%02d.png"), anchors
