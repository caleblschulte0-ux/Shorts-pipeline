"""Ink: the hand-drawn line and fill every doodle is made of.

The look the operator pointed at (2026-09-23: History with Dave, Deep Epoch)
is a cartoon drawn with a marker: one confident dark outline that is never
ruler-straight, flat colour with a darker shadow side, a little paper grain.
Nothing here is sketchy or double-stroked and NOTHING BOILS — the outline of
a still thing is the same outline on every frame. A line that re-jitters on
a timer is a vibrating picture, and the operator ruled vibration out of every
channel (`shared/camera_float.py`, 2026-08-25). Things move because they are
DOING something (a fire burning, rain falling, a hand stirring a pot), never
because the drawing shivers.

Shapes are built as point lists, given a small seeded wobble once, and turned
into smooth closed/open Bezier paths. Determinism is the contract: the same
(shape, seed) is the same pixels on every frame and every run.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import cairo

INK = (0.13, 0.11, 0.12)            # the marker: warm near-black, never pure #000
LINE = 5.0                           # default outline width at 1920x1080


def rgb(h: str, a: float = 1.0) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(c1, c2, k: float) -> tuple:
    a = tuple(c1) + (1.0,) * (4 - len(c1))
    b = tuple(c2) + (1.0,) * (4 - len(c2))
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(4))


def shade(c, k: float = 0.78) -> tuple:
    """The shadow side of a flat colour: darker and a touch cooler."""
    c = tuple(c) + (1.0,) * (4 - len(c))
    return (c[0] * k * 0.97, c[1] * k * 0.98, min(1.0, c[2] * k * 1.04), c[3])


def lighten(c, k: float = 0.25) -> tuple:
    return mix(c, (1, 1, 1, c[3] if len(c) > 3 else 1), k)


# ------------------------------------------------------------------ geometry
def wobble(pts, amp: float, seed: int, closed: bool = True, step: float = 26.0):
    """Resample a polyline every ~`step` px and push each point along its
    normal by a smooth seeded wave. `amp` is in pixels; 1.5-3 reads as a
    steady hand."""
    if amp <= 0 or len(pts) < 2:
        return list(pts)
    r = random.Random(seed)
    ph = [r.uniform(0, 6.283) for _ in range(3)]
    fr = [r.uniform(0.010, 0.020), r.uniform(0.025, 0.045), r.uniform(0.06, 0.09)]
    seq = list(pts) + ([pts[0]] if closed else [])
    out = []
    dist = 0.0
    for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / step))
        nx, ny = (-(y1 - y0) / L, (x1 - x0) / L) if L else (0.0, 0.0)
        for i in range(n):
            t = i / n
            d = dist + L * t
            off = amp * (0.6 * math.sin(d * fr[0] + ph[0])
                         + 0.3 * math.sin(d * fr[1] + ph[1])
                         + 0.1 * math.sin(d * fr[2] + ph[2]))
            out.append((x0 + (x1 - x0) * t + nx * off, y0 + (y1 - y0) * t + ny * off))
        dist += L
    if not closed:
        out.append(seq[-1])
    return out


def smooth(cr, pts, closed: bool = True, tension: float = 0.5):
    """Catmull-Rom through `pts` as a cairo path."""
    n = len(pts)
    if n < 2:
        return
    if n == 2:
        cr.move_to(*pts[0])
        cr.line_to(*pts[1])
        return
    P = (lambda i: pts[i % n]) if closed else (lambda i: pts[max(0, min(n - 1, i))])
    cr.move_to(*pts[0])
    last = n if closed else n - 1
    k = tension / 3.0 * 2
    for i in range(last):
        p0, p1, p2, p3 = P(i - 1), P(i), P(i + 1), P(i + 2)
        c1 = (p1[0] + (p2[0] - p0[0]) * k / 2, p1[1] + (p2[1] - p0[1]) * k / 2)
        c2 = (p2[0] - (p3[0] - p1[0]) * k / 2, p2[1] - (p3[1] - p1[1]) * k / 2)
        cr.curve_to(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        cr.close_path()


def ellipse_pts(cx, cy, rx, ry, n: int = 28, rot: float = 0.0, start=0.0, end=2 * math.pi):
    pts = []
    full = abs(end - start - 2 * math.pi) < 1e-6
    m = n if full else n + 1
    for i in range(m):
        a = start + (end - start) * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts


def blob_pts(cx, cy, rx, ry, seed: int, lump: float = 0.12, n: int = 18):
    """A lumpy closed organic shape (bush, rock, cloud, hair tuft)."""
    r = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + r.uniform(-lump, lump)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


# ------------------------------------------------------------------ drawing
def path(cr, pts, closed=True, amp=2.0, seed=0):
    smooth(cr, wobble(pts, amp, seed, closed) if amp else pts, closed)


def fill_stroke(cr, pts, fill, *, closed=True, amp=2.0, seed=0, lw=LINE,
                ink=INK, shadow: tuple | None = None, shadow_dir=(1, 0.6),
                texture: str | None = None, tex_alpha=0.16):
    """The standard doodle mark: flat fill, a darker shadow side clipped to
    the shape, optional texture, then the ink outline over it."""
    wp = wobble(pts, amp, seed, closed) if amp else list(pts)
    if fill is not None:
        smooth(cr, wp, closed)
        cr.set_source_rgba(*fill)
        if shadow is not None or texture:
            cr.fill_preserve()
            cr.save()
            cr.clip()
            if shadow is not None:
                xs = [p[0] for p in wp]
                ys = [p[1] for p in wp]
                w, h = max(xs) - min(xs), max(ys) - min(ys)
                dx, dy = shadow_dir
                cr.translate(dx * w * 0.28, dy * h * 0.22)
                smooth(cr, wp, closed)
                cr.translate(-dx * w * 0.28, -dy * h * 0.22)
                # everything OUTSIDE the offset copy is the shadow side
                cr.rectangle(min(xs) - w, min(ys) - h, 3 * w, 3 * h)
                cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                cr.set_source_rgba(*shadow)
                cr.fill()
                cr.set_fill_rule(cairo.FILL_RULE_WINDING)
            if texture:
                cr.set_source(pattern(texture))
                cr.paint_with_alpha(tex_alpha)
            cr.restore()
            cr.new_path()
        else:
            cr.fill()
    if lw:
        smooth(cr, wp, closed)
        stroke(cr, lw, ink)


def stroke(cr, lw=LINE, ink=INK):
    cr.set_line_width(lw)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_source_rgba(*ink)
    cr.stroke()


def line(cr, pts, lw=LINE, ink=INK, amp=1.2, seed=0):
    smooth(cr, wobble(pts, amp, seed, closed=False) if amp else pts, closed=False)
    stroke(cr, lw, ink)


def dot(cr, x, y, r, color=INK):
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.set_source_rgba(*color)
    cr.fill()


def glow(cr, x, y, r, color, a=1.0):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, color[0], color[1], color[2], a)
    g.add_color_stop_rgba(0.45, color[0], color[1], color[2], a * 0.35)
    g.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
    cr.set_source(g)
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.fill()


def vnoise(t: float, rate: float, seed: int, eased: bool = False) -> float:
    """Value noise in [-1, 1]: a fresh random value `rate` times a second,
    interpolated between. This is how a flame or firelight really flickers —
    a new shape every few frames — where a sine wave only sways. Linear by
    default: cosine easing goes flat at every knot, and two frames on a flat
    spot are two frames the cadence probe rightly calls identical."""
    x = t * rate
    i = math.floor(x)
    f = x - i
    a = random.Random(seed * 1000003 + i).uniform(-1, 1)
    b = random.Random(seed * 1000003 + i + 1).uniform(-1, 1)
    k = (1 - math.cos(math.pi * f)) / 2 if eased else f
    return a + (b - a) * k


# ------------------------------------------------------------------ textures
@lru_cache(maxsize=None)
def _tex_surface(kind: str):
    """Small tileable textures, made once per process."""
    import numpy as np
    size = 256
    rng = np.random.default_rng({"grain": 1, "fur": 2, "hatch": 3, "paper": 4}.get(kind, 9))
    a = np.zeros((size, size, 4), np.uint8)
    if kind in ("grain", "paper"):
        n = rng.normal(0, 1, (size, size))
        # soften to a paper tooth, not TV static
        n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1) + np.roll(n, -1, 0)) / 4
        v = np.clip(128 + n * (70 if kind == "grain" else 40), 0, 255).astype(np.uint8)
        a[..., 0] = a[..., 1] = a[..., 2] = v
        a[..., 3] = 255
    elif kind == "fur":
        a[..., 3] = 0
        for _ in range(55):
            cx, cy = rng.integers(0, size, 2)
            rx, ry = rng.integers(7, 15), rng.integers(5, 11)
            yy, xx = np.ogrid[:size, :size]
            m = (((xx - cx) % size) / rx) ** 2 + (((yy - cy) % size) / ry) ** 2
            m2 = ((((xx - cx + size // 2) % size) - size // 2) / rx) ** 2 + \
                 ((((yy - cy + size // 2) % size) - size // 2) / ry) ** 2
            mask = m2 < 1
            a[mask] = (30, 34, 58, 255)          # BGRA: dark brown spots
    elif kind == "hatch":
        for i in range(0, size, 9):
            for t in range(2):
                idx = (np.arange(size) + i + t) % size
                a[np.arange(size), idx] = (0, 0, 0, 255)
    surf = cairo.ImageSurface.create_for_data(bytearray(a.tobytes()), cairo.FORMAT_ARGB32,
                                              size, size)
    return surf


def pattern(kind: str):
    p = cairo.SurfacePattern(_tex_surface(kind))
    p.set_extend(cairo.EXTEND_REPEAT)
    return p


def paper(cr, w, h, alpha=0.07):
    """A faint paper tooth over the whole frame — fixed, never animated."""
    cr.save()
    cr.set_source(pattern("paper"))
    cr.set_operator(cairo.OPERATOR_OVERLAY)
    cr.paint_with_alpha(alpha)
    cr.restore()
