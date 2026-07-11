#!/usr/bin/env python3
"""Persistent assets + object builders for the simulation engine.

Two registries, both consumed by world_engine.WorldScene:

ASSETS — the persistent object library (CURIOSITY_BRAIN.md §7.5): ONE
canonical Earth, ONE mountain, ONE drill... defined once, referenced by
every video forever. Procedural vector construction (crisp at any camera
zoom, zero external files); an asset is `ASSETS[name](scale) -> VGroup`.

BUILDERS — waypoint exhibits: `BUILDERS[name](wp, theme, scale) ->
(VGroup, [Animation])`. The group is placed at the waypoint's anchor by
the world template; the animations play when the camera arrives.

One-take rule: builders NEVER use absolute-coordinate `always_redraw`
(the template moves the group after building) — live counters/fills
anchor to sibling mobjects via updaters, so they stay correct wherever
the world puts them and however the camera moves.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from manim import (BOLD, DOWN, LEFT, RIGHT, UP, Arc, Circle, Create,
                   DashedLine, Dot, FadeIn, Line, Polygon, Rectangle, Rotate,
                   Text, Transform, ValueTracker, VGroup, rate_functions)

try:
    from data_learning import continents as cont
except ImportError:          # loaded with data_learning/ itself on the path
    import continents as cont

PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
GRAY_TEXT = "#98a2b4"
COOL = "#5b8fd9"

# ---------------------------------------------------------------------------
# The registries live HERE (canonical import path data_learning.world_builders)
# because manim loads world_engine.py by file path — if the registry lived
# there, the engine and the builders would each see a different copy.
# ---------------------------------------------------------------------------
BUILDERS = {}

# THE WORLD REMEMBERS (§7.5 v4): a per-render dict of named entity
# handles. A builder registers what it creates (STATE["earth"] = mobject);
# later beats' events may MUTATE the entity (crack it, warm it, add a
# satellite) and mutations are NEVER undone — the final pullback rides
# past the accumulated world. The engine clears this at construct start.
STATE: dict = {}


def builder(name):
    def reg(fn):
        BUILDERS[name] = fn
        return fn
    return reg


@builder("marker")
def _build_marker(wp: dict, theme: dict, scale: float, anchor=None,
                  post_scale: float = 1.0):
    """Simplest waypoint: a glowing dot + label."""
    hi = theme.get("highlight", "#4FD1C5")
    p = wp.get("params", {})
    dot = Dot([0, 0, 0], radius=0.16 * scale, color=hi)
    halo = Circle(radius=0.34 * scale, stroke_width=6 * scale,
                  color=hi, stroke_opacity=0.5)
    label = Text(str(p.get("label", "")), font_size=int(34 * scale),
                 weight=BOLD, color="#ffffff").next_to(dot, DOWN,
                                                       buff=0.3 * scale)
    g = VGroup(dot, halo, label)
    _settle(g, anchor, post_scale)
    return g, [
        _Par([FadeIn(label, shift=UP * 0.2 * scale * post_scale)],
             run_time=0.8),
        _Par([halo.animate.scale(1.35)], run_time=0.9),
        _Par([dot.animate.scale(1.3), halo.animate.scale(1.15)],
             run_time=0.7, punch=True),
    ]


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if float(v).is_integer():
        return f"{v:.0f}"
    return f"{v:,.1f}"


def _diet(s, max_words: int = 2) -> str:
    """Text diet (mute-test doctrine): a stamp is a number + at most two
    words — the visual carries the noun."""
    return " ".join(str(s).split()[:max_words])


def _settle(g, anchor, post_scale: float = 1.0, about: str = "bbox"):
    """Anchor-first AND scale-first: position and zoom the group BEFORE
    any animation is created. .animate/Transform targets snapshot coords
    at creation time — an engine-side scale applied after the builder
    returns would warp played objects back to unit-scale positions.

    Scale worlds build at unit design scale (a 15,000pt Pango font would
    not survive) and geometrically zoom here with scale_stroke=True so
    hairline strokes stay visible at ×343. manim 0.20 quirk: scale_stroke
    CONJURES a stroke on width-0 mobjects (Text stickers, rims on
    stroke-less fills) — designed-zero widths are re-zeroed after.

    about="bbox" centres the group's bounding box on the anchor (right
    for symmetric exhibits). about="origin" translates design coords to
    the anchor verbatim — REQUIRED when the build-time bbox lies about
    the final composition (rank's bars are 0.02 wide at build and race
    outward later; bbox-centring would shove the whole layout
    off-frame)."""
    if anchor is not None:
        if about == "origin":
            g.shift(np.array(anchor))
        else:
            g.move_to(anchor)
    if post_scale and post_scale != 1.0:
        ap = (np.array(anchor) if anchor is not None
              else g.get_center().copy())
        zeros = [m for m in g.family_members_with_points()
                 if m.get_stroke_width() == 0]
        g.scale(post_scale, about_point=ap, scale_stroke=True)
        for m in zeros:
            m.set_stroke(width=0)
    return g


def _points(wp: dict) -> tuple[list[dict], str]:
    p = wp.get("params", {})
    f = p.get("file")
    if f:
        d = json.loads((DATA_DIR / f).read_text())
        return d.get("points", []), d.get("unit", p.get("unit", ""))
    return p.get("points", []), p.get("unit", "")


def _counter(v: ValueTracker, unit: str, size: int, color: str,
             anchor, direction=UP, buff=0.3, size_ref=None):
    """A live number that stays glued to a sibling mobject (one-take
    safe). `anchor` may be a mobject or a callable returning one.

    size_ref=(mobject, attr, ratio): size the number each frame as
    ratio × the sibling's stable dimension instead of a fixed font size.
    REQUIRED in scale worlds — the group is geometrically scaled AFTER
    build, but become() targets are created at font scale, so a fixed-size
    counter is microscopic at deep zoom levels. Pick a dimension the
    arrival anims don't stretch (bar HEIGHT, column WIDTH)."""
    num = Text("0", font_size=size, weight=BOLD, color=color)

    def upd(m):
        a = anchor() if callable(anchor) else anchor
        new = Text(f"{_fmt(v.get_value())} {unit}".strip(),
                   font_size=size, weight=BOLD, color=color)
        b = buff
        if size_ref is not None:
            ref, attr, ratio = size_ref
            ref = ref() if callable(ref) else ref
            target = max(1e-6, getattr(ref, attr) * ratio)
            new.scale(target / max(new.height, 1e-9))
            b = new.height * 0.45
        new.next_to(a, direction, buff=b)
        m.become(new)
    num.add_updater(upd)
    upd(num)     # groups may stay suspended until visited — position and
    return num   # format the counter NOW, not on its first update


# ===========================================================================
# ASSETS — the persistent object library. THE Earth. THE mountain.
# ===========================================================================
ASSETS = {}


def asset(name):
    def reg(fn):
        ASSETS[name] = fn
        return fn
    return reg


def _earth_face(scale):
    """The Atlantic hemisphere as landmass Polygons (v8: THE continents,
    not green circles). One shared sinusoidal projection keeps the
    geography coherent; vertices past the disc edge clamp radially onto
    the limb — the same smear a real globe shows at its horizon."""
    outlines = []
    for name in cont.ATLANTIC_FACE:
        pts = cont.LANDMASSES[name]
        if name == "eurasia":
            pts = [p for p in pts if p[0] <= cont.EURASIA_FACE_MAX_LON]
        outlines.append([((lon - cont.ATLANTIC_LON0) * math.cos(
            math.radians(lat)), lat) for lon, lat in pts])
    xs = [x for o in outlines for x, _ in o]
    ys = [y for o in outlines for _, y in o]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    s = 2.84 * scale / max(max(xs) - min(xs), max(ys) - min(ys))
    lim = 1.44 * scale
    polys = []
    for o in outlines:
        anchors = []
        for x, y in o:
            px, py = (x - cx) * s, (y - cy) * s
            rr = math.hypot(px, py)
            if rr > lim:
                px, py = px * lim / rr, py * lim / rr
            anchors.append([px, py, 0])
        polys.append(Polygon(*anchors, stroke_width=0,
                             fill_color="#2f8f5b", fill_opacity=0.95))
    return polys


@asset("earth")
def _earth(scale=1.0):
    g = VGroup()
    g.add(Circle(radius=1.5 * scale, stroke_width=0, fill_color="#1c4a8c",
                 fill_opacity=1.0))
    for poly in _earth_face(scale):
        g.add(poly)       # [1:-1] — the spin updater's rotating slice
    g.add(Circle(radius=1.62 * scale, stroke_width=3 * scale,
                 color="#7fb4ff", stroke_opacity=0.35))     # atmosphere
    return g


@asset("mountain")
def _mountain(scale=1.0):
    g = VGroup()
    g.add(Polygon([-1.6 * scale, 0, 0], [0, 2.2 * scale, 0],
                  [1.6 * scale, 0, 0], stroke_width=0,
                  fill_color="#3d4358", fill_opacity=1.0))
    g.add(Polygon([-0.45 * scale, 1.58 * scale, 0], [0, 2.2 * scale, 0],
                  [0.45 * scale, 1.58 * scale, 0],
                  [0.18 * scale, 1.45 * scale, 0],
                  [-0.2 * scale, 1.5 * scale, 0], stroke_width=0,
                  fill_color="#e8ecf4", fill_opacity=1.0))   # snow cap
    return g


@asset("drill")
def _drill(scale=1.0):
    g = VGroup()
    g.add(Polygon([-0.5 * scale, 0, 0], [0.5 * scale, 0, 0],
                  [0.16 * scale, 1.5 * scale, 0], [-0.16 * scale, 1.5 * scale, 0],
                  stroke_width=3 * scale, stroke_color="#8fa0bd",
                  fill_color="#232c44", fill_opacity=0.9))   # derrick
    for fy in (0.4, 0.8, 1.15):
        g.add(Line([-0.42 * scale * (1 - fy / 2), fy * scale, 0],
                   [0.42 * scale * (1 - fy / 2), fy * scale, 0],
                   stroke_width=2.5 * scale, color="#8fa0bd"))
    g.add(Polygon([-0.12 * scale, 0, 0], [0.12 * scale, 0, 0],
                  [0, -0.35 * scale, 0], stroke_width=0,
                  fill_color="#cdd6ea", fill_opacity=1.0))   # bit
    return g


@asset("thermometer")
def _thermometer(scale=1.0):
    g = VGroup()
    g.add(Rectangle(width=0.42 * scale, height=2.6 * scale,
                    stroke_width=4 * scale, stroke_color="#cdd6ea",
                    fill_color="#0c1220", fill_opacity=1.0)
          .move_to([0, 1.3 * scale, 0]))
    g.add(Circle(radius=0.4 * scale, stroke_width=4 * scale,
                 stroke_color="#cdd6ea", fill_color="#0c1220",
                 fill_opacity=1.0))
    return g


@asset("human")
def _human(scale=1.0):
    s = scale * 0.62
    g = VGroup()
    g.add(Circle(radius=0.22 * s, stroke_width=0, fill_color="#cdd6ea",
                 fill_opacity=1.0).move_to([0, 1.5 * s, 0]))
    g.add(Polygon([-0.3 * s, 1.2 * s, 0], [0.3 * s, 1.2 * s, 0],
                  [0.22 * s, 0.35 * s, 0], [-0.22 * s, 0.35 * s, 0],
                  stroke_width=0, fill_color="#cdd6ea", fill_opacity=1.0))
    g.add(Line([-0.14 * s, 0.35 * s, 0], [-0.2 * s, -0.6 * s, 0],
               stroke_width=7 * s, color="#cdd6ea"))
    g.add(Line([0.14 * s, 0.35 * s, 0], [0.2 * s, -0.6 * s, 0],
               stroke_width=7 * s, color="#cdd6ea"))
    return g


@asset("jet")
def _jet(scale=1.0):
    s = scale
    g = VGroup()
    g.add(Polygon([-1.3 * s, 0, 0], [0.9 * s, 0.16 * s, 0],
                  [1.3 * s, 0, 0], [0.9 * s, -0.16 * s, 0],
                  stroke_width=0, fill_color="#cdd6ea", fill_opacity=1.0))
    g.add(Polygon([-0.1 * s, 0, 0], [-0.75 * s, -0.7 * s, 0],
                  [-0.35 * s, 0, 0], stroke_width=0, fill_color="#9fb0cd",
                  fill_opacity=1.0))
    g.add(Polygon([-0.1 * s, 0, 0], [-0.75 * s, 0.7 * s, 0],
                  [-0.35 * s, 0, 0], stroke_width=0, fill_color="#9fb0cd",
                  fill_opacity=1.0))
    g.add(Polygon([-1.3 * s, 0, 0], [-1.55 * s, 0.42 * s, 0],
                  [-1.15 * s, 0.06 * s, 0], stroke_width=0,
                  fill_color="#9fb0cd", fill_opacity=1.0))
    return g


@asset("bullet")
def _bullet(scale=1.0):
    s = scale * 0.9
    g = VGroup()
    g.add(Rectangle(width=0.9 * s, height=0.34 * s, stroke_width=0,
                    fill_color="#d9b06a", fill_opacity=1.0)
          .move_to([-0.15 * s, 0, 0]))                       # casing
    g.add(Polygon([0.3 * s, 0.17 * s, 0], [0.78 * s, 0, 0],
                  [0.3 * s, -0.17 * s, 0], stroke_width=0,
                  fill_color="#b8874a", fill_opacity=1.0))   # nose
    for k, dy in enumerate((-0.11, 0.02, 0.13)):
        g.add(Line([(-1.15 - 0.12 * k) * s, dy * s, 0],
                   [-0.68 * s, dy * s, 0], stroke_width=2.5 * s,
                   color="#cdd6ea", stroke_opacity=0.5))     # speed lines
    return g


@asset("comet")
def _comet(scale=1.0):
    s = scale
    g = VGroup()
    for dy, ln, o in ((0.0, 1.5, 0.6), (0.09, 1.1, 0.4), (-0.08, 1.2, 0.35)):
        g.add(Line([-ln * s, (dy + ln * 0.18) * s, 0], [0, dy * s, 0],
                   stroke_width=4 * s, color="#bcd4ff", stroke_opacity=o))
    g.add(Circle(radius=0.16 * s, stroke_width=0, fill_color="#eaf2ff",
                 fill_opacity=1.0))
    return g


@asset("moon")
def _moon(scale=1.0):
    s = scale
    g = VGroup()
    g.add(Circle(radius=1.0 * s, stroke_width=0, fill_color="#b9beca",
                 fill_opacity=1.0))
    for x, y, r in ((0.3, 0.25, 0.16), (-0.35, -0.1, 0.22),
                    (0.1, -0.45, 0.12), (-0.15, 0.5, 0.1)):
        g.add(Circle(radius=r * s, stroke_width=0, fill_color="#8f95a3",
                     fill_opacity=0.9).move_to([x * s, y * s, 0]))
    return g


@asset("satellite")
def _satellite(scale=1.0):
    s = scale
    g = VGroup()
    g.add(Rectangle(width=0.5 * s, height=0.3 * s, stroke_width=0,
                    fill_color="#cdd6ea", fill_opacity=1.0))       # body
    for sx in (-1, 1):
        g.add(Line([sx * 0.25 * s, 0, 0], [sx * 0.34 * s, 0, 0],
                   stroke_width=3 * s, color="#8fa0bd"))
        g.add(Rectangle(width=0.62 * s, height=0.26 * s, stroke_width=0,
                        fill_color="#3b6bd6", fill_opacity=0.95)
              .move_to([sx * 0.68 * s, 0, 0]))                     # panels
    return g


@asset("iss")
def _iss(scale=1.0):
    s = scale
    g = VGroup()
    g.add(Rectangle(width=1.6 * s, height=0.08 * s, stroke_width=0,
                    fill_color="#9fb0cd", fill_opacity=1.0))       # truss
    g.add(Rectangle(width=0.42 * s, height=0.26 * s, stroke_width=0,
                    fill_color="#cdd6ea", fill_opacity=1.0))       # modules
    for sx in (-0.62, 0.62):
        for dy in (0.24, -0.24):
            g.add(Rectangle(width=0.34 * s, height=0.3 * s, stroke_width=0,
                            fill_color="#3b6bd6", fill_opacity=0.95)
                  .move_to([sx * s, dy * s, 0]))                   # arrays
    return g


# ===========================================================================
# CONSEQUENCES — what a premium hero leaves behind in the 2D world
# (§7.5 v8 hero-integration contract, stage 4). Built during the covered
# span (the 2D take keeps rendering under the splice), registered in
# STATE["consequence:<hero id>"], adopted into the beat's GROUP so the
# scale-world zoom gate governs their visibility, and pulsed by the
# ending's echo pass. Each returns seconds consumed.
# ===========================================================================
CONSEQUENCES = {}


def consequence(name):
    def reg(fn):
        CONSEQUENCES[name] = fn
        return fn
    return reg


def _adopt(scene, ctx, m):
    scene.remove(m)                  # Create/FadeIn parked it at the root
    g = ctx.get("group")
    if g is not None:
        g.add(m)                     # ride the exhibit; obey the zoom gate
    else:
        scene.add(m)


@consequence("orbit_ring")
def _c_orbit_ring(scene, ctx, plan):
    """earth_spin's speed band stays behind: a glowing equatorial ring
    around the subject — the world remembers the hero happened."""
    hi = ctx.get("accent", "#4FD1C5")
    sub = STATE.get("level:earth") or ctx.get("group")
    c = (np.array(sub.get_center()) if sub is not None
         else np.array(ctx["anchor"]))
    w = (sub.width if sub is not None and sub.width > 1e-6
         else ctx["fw"] * 0.4)
    ring = Circle(radius=w * 0.60, color=hi, stroke_width=w * 0.55,
                  stroke_opacity=0.75).stretch(0.34, 1).move_to(c)
    rt = 1.2
    scene.play(Create(ring), run_time=rt,
               rate_func=rate_functions.ease_in_out_sine)
    _adopt(scene, ctx, ring)
    STATE[f"consequence:{plan.get('id')}"] = ring
    return rt


@consequence("standing_trail")
def _c_standing_trail(scene, ctx, plan):
    """monoliths leave their ground behind: a lit baseline + under-glow
    beneath the lineup — the 2D slabs now stand on the hero's floor."""
    hi = ctx.get("accent", "#4FD1C5")
    g = ctx.get("group")
    if g is None or g.width < 1e-6:
        return 0.0
    x0, x1 = float(g.get_left()[0]), float(g.get_right()[0])
    y = float(g.get_bottom()[1])
    pad = (x1 - x0) * 0.10
    base = Line([x0 - pad, y, 0], [x1 + pad, y, 0], color=hi,
                stroke_width=(x1 - x0) * 0.8, stroke_opacity=0.9)
    glow = Line([x0 - pad * 2, y, 0], [x1 + pad * 2, y, 0], color=hi,
                stroke_width=(x1 - x0) * 2.6, stroke_opacity=0.16)
    keep = VGroup(glow, base)
    rt = 1.0
    scene.play(Create(base), FadeIn(glow), run_time=rt,
               rate_func=rate_functions.ease_out_cubic)
    _adopt(scene, ctx, keep)
    STATE[f"consequence:{plan.get('id')}"] = keep
    return rt


@consequence("depth_mark")
def _c_depth_mark(scene, ctx, plan):
    """earth_dive leaves the bottom of the world behind: a glowing mark
    at the exhibit's deepest point."""
    hi = ctx.get("accent", "#4FD1C5")
    g = ctx.get("group")
    bottom = (np.array(g.get_bottom()) if g is not None
              else np.array(ctx["anchor"]))
    w = (g.width if g is not None and g.width > 1e-6
         else ctx["fw"] * 0.3)
    dot = Dot([bottom[0], bottom[1], 0], radius=w * 0.035, color=hi)
    tick = Line([bottom[0] - w * 0.12, bottom[1], 0],
                [bottom[0] + w * 0.12, bottom[1], 0], color=hi,
                stroke_width=w * 0.5, stroke_opacity=0.8)
    keep = VGroup(tick, dot)
    rt = 0.9
    scene.play(FadeIn(tick), dot.animate.scale(1.6),
               run_time=rt, rate_func=rate_functions.ease_out_back)
    _adopt(scene, ctx, keep)
    STATE[f"consequence:{plan.get('id')}"] = keep
    return rt


# ===========================================================================
# BUILDERS — waypoint exhibits (one-take safe).
# ===========================================================================
def _rank_in_world(wp, theme, scale, anchor=None, post_scale=1.0):
    """NO-DOWNGRADE MODE (§7.5 v8): after the world gains an environment,
    comparisons PHYSICALIZE — bars become lit monolith slabs standing on
    a floor in the persistent starfield, values riding their tops, and a
    second phase re-compares by ratio. Never a flat standalone chart
    right after a cinematic reveal."""
    pts, unit = _points(wp)
    pts = pts[:5]
    p = wp.get("params", {})
    hi = theme.get("highlight", "#4FD1C5")
    vmax = max(q["value"] for q in pts) or 1.0
    vmin = min(q["value"] for q in pts) or 1.0
    n = len(pts)
    col_w = min(1.5, 6.6 / n) * scale
    col_h = 3.0 * scale
    x00 = -(n - 1) / 2 * col_w
    g = VGroup()
    span = n * col_w
    glow = Line([x00 - col_w, -0.02 * scale, 0],
                [x00 + span, -0.02 * scale, 0], color=hi,
                stroke_width=span * 1.1, stroke_opacity=0.10)
    floor = Line([x00 - col_w, 0, 0], [x00 + span, 0, 0],
                 color="#8fa0bd", stroke_width=span * 0.28,
                 stroke_opacity=0.8)
    g.add(glow, floor)
    slabs = []
    for i, q in enumerate(sorted(pts, key=lambda r: r["value"])):
        x = x00 + i * col_w
        star = q["value"] == vmax
        slab = Rectangle(width=col_w * 0.44, height=0.02, stroke_width=0,
                         fill_color=hi if star else COOL,
                         fill_opacity=0.95)
        slab.move_to([x, 0, 0], aligned_edge=DOWN)
        label = Text(_diet(q["label"]), font_size=int(20 * scale),
                     color="#ffffff").move_to([x, -0.45 * scale, 0])
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(24 * scale), "#ffffff",
                       anchor=slab, direction=UP, buff=0.22 * scale,
                       size_ref=(slab, "width", 0.55))
        g.add(slab, label, num)
        slabs.append((slab, v, q, star))
    # phase 2: the same facts re-compared as a RATIO (new comparison
    # method = a real semantic event, not more of the same grammar).
    ratio = Text(f"{vmax / max(vmin, 1e-9):,.0f}× "
                 + _diet(p.get("ratio_label", "the slowest")),
                 font_size=int(30 * scale), weight=BOLD, color=hi)
    ratio.move_to([x00 + span * 0.5, col_h * 1.12, 0])
    g.add(ratio)
    _settle(g, anchor, post_scale, about="origin")
    ratio.scale(1e-3)                      # size-reveal (zoom-gate safe)
    anims = [_Par([Create(floor), FadeIn(glow)], run_time=0.9,
                  sem=("environment", "monolith-floor"), focus="floor")]
    for slab, v, q, star in slabs:
        target_h = max(0.05, col_h * q["value"] / vmax) * post_scale
        anims.append(_Par(
            [slab.animate(rate_func=rate_functions.ease_out_cubic)
             .stretch_to_fit_height(target_h, about_edge=DOWN),
             v.animate.set_value(q["value"])],
            run_time=1.4 if star else 0.9,
            state=True, focus="champion" if star else None))
    anims.append(_Par([ratio.animate(
        rate_func=rate_functions.ease_out_back).scale(1e3)],
        run_time=1.0, punch=True, state=True,
        sem=("comparison", "ratio-stamp"), focus="ratio"))
    return g, anims


@builder("rank")
def _b_rank(wp, theme, scale, anchor=None, post_scale=1.0):
    """Bars race in smallest -> biggest; the champion lands last."""
    if wp.get("params", {}).get("mode") == "in_world":
        return _rank_in_world(wp, theme, scale, anchor, post_scale)
    pts, unit = _points(wp)
    pts = pts[:5]
    hi = theme.get("highlight", "#4FD1C5")
    vmax = max(p["value"] for p in pts) or 1.0
    n = len(pts)
    row_h = min(1.2, 5.0 / n) * scale
    # The whole composition — longest label left, champion bar + its
    # riding "828,000 km/h" counter right — must fit the tightest dwell
    # frame (0.88 fw → usable half-width ≈4.8). Design coords are world
    # coords: rank settles about="origin", because its build-time bbox
    # (0.02-wide bars) lies about where the raced bars will end.
    bar_w = 3.3 * scale
    x0 = -1.3 * scale
    g = VGroup()
    rows = []
    for i, p in enumerate(sorted(pts, key=lambda q: q["value"])):
        y = (n / 2 - i - 0.5) * row_h * -1
        star = p["value"] == vmax
        label = Text(p["label"], font_size=int(22 * scale), color="#ffffff")
        label.move_to([x0 - 0.35 * scale, y, 0], aligned_edge=RIGHT)
        bar = Rectangle(width=0.02, height=row_h * 0.5, stroke_width=0,
                        fill_color=hi if star else COOL, fill_opacity=0.95)
        bar.move_to([x0, y, 0], aligned_edge=LEFT)
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(26 * scale), "#ffffff",
                       anchor=bar, direction=RIGHT, buff=0.25 * scale,
                       size_ref=(bar, "height", 0.45))   # width animates
        g.add(label, bar, num)
        rows.append((bar, v, p, star))
    _settle(g, anchor, post_scale, about="origin")   # BEFORE anims
    anims = []
    for bar, v, p, star in rows:
        target_w = max(0.03, bar_w * p["value"] / vmax) * post_scale
        anims.append(_Par(
            [bar.animate(rate_func=rate_functions.ease_out_cubic)
             .stretch_to_fit_width(target_w, about_edge=LEFT),
             v.animate.set_value(p["value"])],
            run_time=1.5 if star else 1.0,
            punch=star,             # the champion landing IS the payoff
            state=True,             # landed bars stay landed
            focus="champion" if star else None))
    if anims:
        anims[0].sem = ("comparison", "bar-lineup")
    return g, anims


class _Par:
    """Tiny AnimationGroup stand-in the engine can `self.play(*a.anims)`.
    Exposes .anims + .run_time; the shot scheduler unpacks it.

    Escalation contract (§7.5 v4): a builder returns a TIMELINE of these —
    the first is the subject's arrival (plays as the reveal), the rest are
    scheduled across the beat's whole window. punch=True marks a PAYOFF:
    it lands with a camera pop and the ledger logs it as such (the gate
    requires >=1 payoff per beat).

    World-consequence contract (§7.5 v5):
    - cam=callable(ctx)->[anims]: the bundle STEERS THE CAMERA (follow
      the winner, get pulled along the path) — played in the same
      scene.play; dwell legs re-centre afterwards.
    - state=True: the bundle PERMANENTLY changes the world (bars stay
      landed, ticks stay lit); logged as a `state` ledger row for the
      payoff grade. Defaults to punch (payoffs persist unless said
      otherwise).

    Semantic-progression contract (§7.5 v8):
    - sem=("dim", "what"): this bundle introduces a NEW VISUAL IDEA (a
      new phase, comparison method, object role...). A counter climbing,
      a bar extending, a trail growing is NOT one — never tag those.
    - focus="name": who owns the frame when this bundle plays (the
      dominant-subject contract; one primary at a time)."""

    def __init__(self, anims, run_time=1.0, punch=False, cam=None,
                 state=None, sem=None, focus=None):
        self.anims = anims
        self.run_time = run_time
        self.punch = punch
        self.cam = cam
        self.state = punch if state is None else state
        self.sem = sem
        self.focus = focus


@builder("compare")
def _b_compare(wp, theme, scale, anchor=None, post_scale=1.0):
    pts, unit = _points(wp)
    pts = sorted(pts[:2], key=lambda p: p["value"])
    if len(pts) < 2:
        pts = pts * 2
    small, big = pts
    hi = theme.get("highlight", "#4FD1C5")
    vmax = big["value"] or 1.0
    col_h = 3.6 * scale
    g = VGroup()
    cols = []
    for p, x, color in ((small, -1.9 * scale, COOL), (big, 1.9 * scale, hi)):
        col = Rectangle(width=1.5 * scale, height=0.03, stroke_width=0,
                        fill_color=color, fill_opacity=0.95)
        col.move_to([x, -2.0 * scale, 0], aligned_edge=DOWN)
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(28 * scale), "#ffffff",
                       anchor=col, direction=UP, buff=0.3 * scale,
                       size_ref=(col, "width", 0.34))    # height animates
        label = Text(_diet(p["label"]), font_size=int(24 * scale),
                     color=GRAY_TEXT)
        label.move_to([x, -2.45 * scale, 0])
        g.add(col, num, label)
        cols.append((col, v, p))
    mult = None
    if small["value"] > 0 and big["value"] / small["value"] >= 1.5:
        r = big["value"] / small["value"]
        # honest formatting: 1.6x must not read as "2x"
        mult = Text(f"{r:.1f}×" if r < 3 else f"{r:,.0f}×",
                    font_size=int(52 * scale), weight=BOLD, color=hi)
        mult.move_to([0, 1.6 * scale, 0])
        mult.scale(1e-3)     # size reveal — opacity anims fight the gate
        g.add(mult)
    _settle(g, anchor, post_scale)   # BEFORE anims: targets snapshot coords
    anims = []
    for col, v, p in cols:
        h = max(0.03, col_h * p["value"] / vmax) * post_scale
        anims.append(_Par(
            [col.animate(rate_func=rate_functions.ease_out_cubic)
             .stretch_to_fit_height(h, about_edge=DOWN),
             v.animate.set_value(p["value"])],
            run_time=1.3 if p is small else 2.2))
    if mult is not None:
        anims.append(_Par(
            [mult.animate(rate_func=rate_functions.ease_out_back)
             .scale(1e3)], run_time=0.5, punch=True,
            sem=("comparison", "multiplier"), focus="multiplier"))
    else:
        anims[-1].punch = True      # the tall column landing is the payoff
    return g, anims


@builder("gauge")
def _b_gauge(wp, theme, scale, anchor=None, post_scale=1.0):
    """The metaphor for limits: THE thermometer fills past its expected
    marker into the red; the surround glows molten as it climbs."""
    pts, unit = _points(wp)
    pts = sorted(pts[:2], key=lambda p: p["value"])
    expected, actual = (pts[0], pts[-1]) if len(pts) > 1 else (pts[0], pts[0])
    hi = theme.get("highlight", "#4FD1C5")
    g = VGroup()
    therm = ASSETS["thermometer"](scale * 1.4)
    g.add(therm)
    tube_h = 2.6 * scale * 1.4
    vmax = actual["value"] * 1.15
    glow = Circle(radius=2.9 * scale, stroke_width=0, fill_color="#ff5a2a",
                  fill_opacity=0.0)
    g.add(glow)
    fill = Rectangle(width=0.24 * scale * 1.4, height=0.02, stroke_width=0,
                     fill_color="#ff5a2a", fill_opacity=1.0)
    fill.move_to(therm.get_bottom() + np.array([0, 0.32 * scale, 0]),
                 aligned_edge=DOWN)
    bulb = Circle(radius=0.26 * scale * 1.4, stroke_width=0,
                  fill_color="#ff5a2a", fill_opacity=1.0)
    bulb.move_to(therm[1].get_center())
    g.add(bulb, fill)
    # Expected marker on the tube.
    ey = therm.get_bottom()[1] + 0.32 * scale + tube_h * (
        expected["value"] / vmax)
    mark = DashedLine([therm.get_left()[0] - 0.7 * scale, ey, 0],
                      [therm.get_right()[0] + 0.7 * scale, ey, 0],
                      color="#ffffff", stroke_width=3 * scale)
    mlabel = Text(f"{expected['label']}: {_fmt(expected['value'])} {unit}",
                  font_size=int(24 * scale), color="#ffffff")
    mlabel.next_to(mark, LEFT, buff=0.3 * scale)
    g.add(mark, mlabel)
    v = ValueTracker(0.0)
    num = _counter(v, unit, int(40 * scale), "#ff8a5a",
                   anchor=therm, direction=RIGHT, buff=0.8 * scale)
    g.add(num)
    _settle(g, anchor, post_scale)   # BEFORE anims: targets snapshot coords
    target_h = tube_h * (actual["value"] / vmax) * post_scale
    expected_h = max(0.05, tube_h * (expected["value"] / vmax) * post_scale)
    anims = [
        # 1) climb to the expected marker — tension
        _Par([fill.animate(rate_func=rate_functions.ease_in_out_sine)
              .stretch_to_fit_height(expected_h, about_edge=DOWN),
              v.animate.set_value(expected["value"])], run_time=1.6,
             state=True),
        # 2) BLOW PAST it — the payoff
        _Par([fill.animate(rate_func=rate_functions.ease_in_quad)
              .stretch_to_fit_height(target_h, about_edge=DOWN),
              v.animate.set_value(actual["value"]),
              glow.animate.set_opacity(0.16)], run_time=1.9, punch=True,
             sem=("state", "past-the-limit"), focus="gauge"),
        # 3) the surround keeps heating — consequence lingers
        _Par([glow.animate.set_opacity(0.26)], run_time=1.2),
    ]
    return g, anims


@builder("flipcompare")
def _b_flipcompare(wp, theme, scale, anchor=None, post_scale=1.0):
    """THE mountain flips upside-down into the shaft — X fits inside Y
    with room to spare. For 'Everest, inverted' class comparisons."""
    pts, unit = _points(wp)
    pts = sorted(pts[:2], key=lambda p: p["value"])
    small, big = pts
    hi = theme.get("highlight", "#4FD1C5")
    depth_h = 3.8 * scale
    mh = depth_h * small["value"] / (big["value"] or 1.0)
    g = VGroup()
    ground = Line([-4.2 * scale, 0, 0], [4.2 * scale, 0, 0],
                  color="#e8ecf4", stroke_width=4 * scale)
    shaft = Line([1.2 * scale, 0, 0], [1.2 * scale, -depth_h, 0],
                 color=hi, stroke_width=6 * scale)
    dlabel = Text(f"{big['label']} — {_fmt(big['value'])} {unit}",
                  font_size=int(26 * scale), color=hi)
    dlabel.move_to([1.7 * scale, -depth_h, 0], aligned_edge=LEFT)
    g.add(ground, shaft, dlabel)
    mtn = ASSETS["mountain"](scale * mh / 2.2)
    mtn.move_to([-2.4 * scale, 0, 0], aligned_edge=DOWN)
    mlabel = Text(f"{small['label']} — {_fmt(small['value'])} {unit}",
                  font_size=int(26 * scale), color="#ffffff")
    mlabel.next_to(mtn, UP, buff=0.25 * scale)
    g.add(mtn, mlabel)
    # remainder bracket appears after the flip
    ry0, ry1 = -mh, -depth_h
    rem = VGroup(
        Line([2.6 * scale, ry0, 0], [2.6 * scale, ry1, 0],
             color="#ffffff", stroke_width=3 * scale),
        Text(f"{_fmt(big['value'] - small['value'])} {unit} to spare",
             font_size=int(24 * scale), color=GRAY_TEXT))
    rem[1].next_to(rem[0], RIGHT, buff=0.25 * scale)
    rem.set_opacity(0)
    g.add(rem)
    _settle(g, anchor, post_scale)   # BEFORE anims + Transform targets
    flipped = mtn.copy().rotate(math.pi)
    flipped.move_to(np.array(shaft.get_start()), aligned_edge=UP)
    anims = [
        _Par([Create(shaft), FadeIn(dlabel)], run_time=1.4),
        _Par([Transform(mtn, flipped)], run_time=1.8, punch=True,
             sem=("metaphor", "flip"), focus="mountain"),
        _Par([rem.animate.set_opacity(1.0)], run_time=0.8),
    ]
    return g, anims


@builder("drilljourney")
def _b_drilljourney(wp, theme, scale, anchor=None, post_scale=1.0):
    """THE drill descends as years stamp in at their depths — progress
    over time as a physical journey, not a line chart."""
    pts, unit = _points(wp)
    hi = theme.get("highlight", "#4FD1C5")
    vals = [p["value"] for p in pts]
    vmax = max(vals) or 1.0
    depth_h = 4.6 * scale
    g = VGroup()
    rig = ASSETS["drill"](scale * 1.0)
    rig.move_to([0, 0, 0], aligned_edge=DOWN)
    ground = Line([-3.8 * scale, 0, 0], [3.8 * scale, 0, 0],
                  color="#e8ecf4", stroke_width=4 * scale)
    g.add(ground, rig)
    string = Line([0, 0, 0], [0, -0.02, 0], color=hi,
                  stroke_width=5 * scale)
    g.add(string)
    v = ValueTracker(0.0)
    num = _counter(v, unit, int(32 * scale), hi,
                   anchor=lambda: string, direction=DOWN, buff=0.35 * scale)
    g.add(num)
    stamps = []
    for p in pts:
        y = -depth_h * p["value"] / vmax
        stamp = VGroup(
            DashedLine([-1.6 * scale, y, 0], [1.6 * scale, y, 0],
                       color=COOL, stroke_width=2.5 * scale),
            Text(f"{p.get('period', p['label'])} · "
                 f"{_fmt(p['value'])} {unit}",
                 font_size=int(24 * scale), color=GRAY_TEXT))
        stamp[1].next_to(stamp[0], RIGHT, buff=0.3 * scale)
        stamp.set_opacity(0)
        g.add(stamp)
        stamps.append((stamp, p))
    _settle(g, anchor, post_scale)   # BEFORE anims: live world coords below
    top = np.array(string.get_start())
    anims = []
    prev = 0.0
    for k, (stamp, p) in enumerate(stamps):
        y_world = stamp[0].get_center()[1]
        seg_rt = max(0.8, 2.2 * (p["value"] - prev) / vmax)
        anims.append(_Par(
            [string.animate(rate_func=rate_functions.ease_in_out_sine)
             .put_start_and_end_on(top, np.array([top[0], y_world, 0.0])),
             v.animate.set_value(p["value"]),
             stamp.animate.set_opacity(1.0)], run_time=seg_rt,
            punch=(k == len(stamps) - 1),    # deepest stamp = payoff
            state=True))                     # stamped depths persist
        prev = p["value"]
    return g, anims


@builder("comparison_race")
def _b_comparison_race(wp, theme, scale, anchor=None, post_scale=1.0):
    """THE physical metaphor for any speed compare (doctrine: every
    explanation names a metaphor humans already understand — this one is
    a race). Two persistent assets run the same track with live counters
    riding them; the gap on screen IS the ratio in the data. Motion is
    the message, so the slower racer being left behind needs no caption.

    params.points: 2–4 {label, value, asset?} entries. Racers launch
    STAGGERED, slowest first — each new racer blows past the previous
    one (escalation is the choreography, not an afterthought). The
    fastest's landing (or the ratio stamp) is the payoff punch.
    params.ticker {rate, unit}: an odometer event accumulates real
    distance at `rate`/second — 'you travelled THIS while watching'."""
    pts, unit = _points(wp)
    pts = sorted(pts[:4], key=lambda q: q["value"], reverse=True)
    if len(pts) < 2:
        pts = pts * 2
    fast, slow = pts[0], pts[-1]
    hi = theme.get("highlight", "#4FD1C5")
    n = len(pts)
    span = min(3.8, 1.35 * (n - 1)) * scale
    # nudged down so the top lane's name clears the frame-pinned chrome
    ys = [span / 2 - k * (span / max(1, n - 1)) - 0.4 * scale
          for k in range(n)]
    x0, x1 = -2.3 * scale, 4.2 * scale        # labels own the left column
    defaults = ["jet", "bullet", "human", "iss"]
    g = VGroup()
    lanes = []
    for k, (p, y) in enumerate(zip(pts, ys)):   # fastest = top lane
        color = hi if p is fast else COOL
        # lanes are SUPPORT, not the subject — thin and dim; the racers,
        # trails and camera carry the beat (§7.5 v5)
        lane = Line([x0, y, 0], [x1, y, 0],
                    color="#1c2338", stroke_width=2.5 * scale)
        tick = Line([x1, y - 0.2 * scale, 0], [x1, y + 0.2 * scale, 0],
                    color="#8fa0bd", stroke_width=3 * scale)  # finish
        name = Text(_diet(p["label"]), font_size=int(22 * scale),
                    color=GRAY_TEXT)
        name.move_to([x0 - 0.35 * scale, y, 0], aligned_edge=RIGHT)
        racer = ASSETS.get(p.get("asset", defaults[k % len(defaults)]),
                           ASSETS["jet"])(scale * 0.42)
        racer.move_to([x0 + 0.45 * scale, y, 0])
        start_mark = Dot([x0 + 0.45 * scale, y, 0], radius=0.02 * scale)
        start_mark.set_opacity(0)               # invisible trail anchor
        trail = Line([x0 + 0.45 * scale, y, 0],
                     [x0 + 0.47 * scale, y, 0], color=color,
                     stroke_width=3.5 * scale, stroke_opacity=0.45)

        def trail_upd(m, r=racer, s=start_mark):
            a_pt = np.array(s.get_center())
            b_pt = np.array(r.get_center())
            if np.linalg.norm(b_pt - a_pt) < 1e-4:
                b_pt = a_pt + np.array([1e-4, 0.0, 0.0])
            m.put_start_and_end_on(a_pt, b_pt)
        trail.add_updater(trail_upd)
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(22 * scale), color,
                       anchor=racer, direction=UP, buff=0.16 * scale,
                       size_ref=(racer, "width", 0.22))
        g.add(lane, tick, name, start_mark, trail, racer, num)
        lanes.append((racer, v, p, lane))
    ratio_txt = None
    if slow["value"] > 0 and fast["value"] / slow["value"] >= 1.5:
        r = fast["value"] / slow["value"]
        ratio_txt = Text(f"{r:.1f}× faster" if r < 3 else
                         f"{r:,.0f}× faster",
                         font_size=int(44 * scale), weight=BOLD, color=hi)
        ratio_txt.move_to([0.9 * scale, -span / 2 - 1.1 * scale, 0])
        # Size-based reveal: an opacity anim would fight the scale-world
        # zoom gate — growth is gate-proof.
        ratio_txt.scale(1e-3)
        g.add(ratio_txt)
    tick_spec = wp.get("params", {}).get("ticker")
    odo = odo_v = None
    if tick_spec:
        odo_v = ValueTracker(0.0)
        odo = _counter(odo_v, str(tick_spec.get("unit", "km")),
                       int(30 * scale), "#ffffff",
                       anchor=lanes[0][3], direction=UP,
                       buff=0.7 * scale,
                       size_ref=(lanes[0][3], "width", 0.055))
        g.add(odo)
    _settle(g, anchor, post_scale)   # BEFORE anims: targets snapshot coords
    anims = []
    for racer, v, p, lane in sorted(lanes, key=lambda L: L[2]["value"]):
        s_pt = np.array(lane.get_start())
        e_pt = np.array(lane.get_end())
        frac = p["value"] / (fast["value"] or 1.0)
        target = s_pt + (e_pt - s_pt) * (0.10 + 0.84 * frac)
        target[1] = racer.get_center()[1]          # hold the lane
        cam = None
        if p is fast:
            # CONSEQUENCE: the camera abandons the field and rides with
            # the winner — the losers visibly fall away behind the
            # frame. The next dwell leg pulls back to reveal the gap.
            w_target = target.copy()

            def cam(c, wt=w_target):
                return [c["frame"].animate(
                    rate_func=rate_functions.ease_in_quad)
                    .move_to([wt[0] - c["fw"] * 0.06, wt[1], 0.0])
                    .set(width=c["fw"] * 0.62)]
        anims.append(_Par(
            [racer.animate(rate_func=rate_functions.ease_in_quad)
             .move_to(target),
             v.animate.set_value(p["value"])],
            run_time=2.0 if p is fast else 1.5,
            punch=(p is fast and ratio_txt is None),
            cam=cam, state=True,
            focus="winner" if p is fast else None))
    if ratio_txt is not None:
        anims.append(_Par(
            [ratio_txt.animate(rate_func=rate_functions.ease_out_back)
             .scale(1e3)], run_time=0.5, punch=True,
            sem=("comparison", "ratio-stamp"), focus="ratio"))
    if odo_v is not None:
        rate = float(tick_spec.get("rate", 1.0))
        anims.append(_Par(                       # honest odometer: real
            [odo_v.animate(rate_func=rate_functions.linear)   # rate x 5 s
             .set_value(rate * 5.0)], run_time=5.0))
    return g, anims


@builder("speedometer")
def _b_speedometer(wp, theme, scale, anchor=None, post_scale=1.0):
    """THE final-number-in-context finale: a dial whose tick marks are
    the ENTIRE ladder of values seen so far; the needle sweeps up and
    passes every tick — each passage is an event, a recap and an
    escalation at once — then pins at the maximum with the payoff punch.
    Physical metaphor: the speedometer (log-scaled so 45 and 1,330,000
    share one dial honestly — the ticks say so)."""
    pts, unit = _points(wp)
    pts = sorted((p for p in pts if p["value"] > 0),
                 key=lambda q: q["value"])[:8]
    if not pts:
        pts = [{"label": "value", "value": 1.0}]
    hi = theme.get("highlight", "#4FD1C5")
    vmin, vmax = pts[0]["value"], pts[-1]["value"]
    lo = math.log10(max(vmin, 1e-9) / 2.0)
    hi_log = math.log10(vmax * 1.3)

    def frac(v):
        return (math.log10(v) - lo) / max(1e-9, hi_log - lo)

    a0, a1 = math.radians(215), math.radians(-35)     # sweep, left → right
    r = 2.7 * scale
    hub = np.array([0.0, -0.7 * scale, 0.0])

    def at(ang, k):
        return hub + np.array([math.cos(ang) * r * k,
                               math.sin(ang) * r * k, 0.0])

    g = VGroup()
    g.add(Arc(radius=r, start_angle=a1, angle=a0 - a1, arc_center=hub,
              color="#2a3350", stroke_width=7 * scale))
    ticks = []
    for k, p in enumerate(pts):
        ang = a0 + (a1 - a0) * frac(p["value"])
        tick = Line(at(ang, 0.93), at(ang, 1.05),
                    color="#8fa0bd", stroke_width=4 * scale)
        # log scale crowds the top values — alternate label radii so
        # neighbouring ticks never stack their numbers
        tval = Text(_fmt(p["value"]), font_size=int(17 * scale),
                    color=GRAY_TEXT).move_to(
                        at(ang, 1.20 if k % 2 == 0 else 1.42))
        g.add(tick, tval)
        ticks.append((tick, p, ang))
    dial = g[0]
    needle = Line(hub, at(a0, 0.82), color=hi, stroke_width=6 * scale)
    hub_dot = Dot(hub, radius=0.09 * scale, color=hi)
    v = ValueTracker(0.0)
    v_ang = ValueTracker(a0)

    # Tracker-driven needle (ABSOLUTE angles): the scheduler may drop
    # intermediate tick bundles in a tight window — relative Rotate
    # deltas would corrupt the sweep, absolute targets just jump farther.
    def _needle_upd(m, dial=dial, hubd=hub_dot, va=v_ang):
        c = hubd.get_center()
        rl = dial.width / 2
        ang = va.get_value()
        m.put_start_and_end_on(
            c, c + np.array([math.cos(ang), math.sin(ang), 0.0]) * rl * 0.82)
    needle.add_updater(_needle_upd)
    num = _counter(v, unit, int(34 * scale), "#ffffff",
                   anchor=hub_dot, direction=DOWN, buff=0.45 * scale,
                   size_ref=(dial, "width", 0.085))
    g.add(needle, hub_dot, num)
    _settle(g, anchor, post_scale)   # BEFORE anims: targets snapshot coords
    anims = []
    for k, (tick, p, ang) in enumerate(ticks):
        last = k == len(ticks) - 1
        anims.append(_Par(
            [v_ang.animate.set_value(ang),
             v.animate.set_value(p["value"]),
             tick.animate.set_color(hi)],         # passed ticks stay lit
            run_time=1.6 if last else 1.0,
            punch=last,                           # pinning at max = payoff
            state=True))                          # lit ticks stay lit
    return g, anims


@builder("scalelevel")
def _b_scalelevel(wp, theme, scale, anchor=None, post_scale=1.0):
    """One level of a ScaleWorld: a tableau (earth / orbit / galaxy /
    human...) built from persistent assets at this level's scale, with the
    level's speed/size stamped on arrival."""
    p = wp.get("params", {})
    hi = theme.get("highlight", "#4FD1C5")
    kind = p.get("tableau", "earth")
    g = VGroup()
    # Idle motion doctrine: objects EXIST, they don't float. Every tableau
    # gets cheap persistent motion (dt updaters, suspended off-screen by
    # the engine). All idle motion is ANGLE-based or sized off a sibling —
    # scale worlds geometrically rescale the group after build, so a
    # fixed-offset shift would become invisible at deep zoom.
    if kind == "earth":
        earth = ASSETS["earth"](scale)

        def spin(m, dt):
            c = m[0].get_center()          # [0]=disc, [-1]=atmosphere
            for sub in m.submobjects[1:-1]:
                sub.rotate(dt * 0.10, about_point=c)
        earth.add_updater(spin)
        g.add(earth)
    elif kind == "sky":
        for (cx, cy, r, o) in ((-2.2, 0.9, 0.55, 0.30), (1.6, -0.7, 0.7, 0.24),
                               (2.6, 1.2, 0.45, 0.20), (-1.0, -1.3, 0.5, 0.18)):
            g.add(Circle(radius=r * scale, stroke_width=0,
                         fill_color="#cdd6ea", fill_opacity=o)
                  .stretch(0.45, 1).move_to([cx * scale, cy * scale, 0]))
        jet = ASSETS["jet"](scale * 0.6)
        jet.move_to([-1.4 * scale, 0.3 * scale, 0])
        trail = Line([0, 0, 0], [0.01, 0, 0], color="#e8ecf4",
                     stroke_width=3 * scale, stroke_opacity=0.45)
        jet.add_updater(lambda m, dt: m.shift(
            np.array([dt * 0.06 * m.width, 0, 0])))       # endless drift

        def ride(m, jet=jet):
            tail = np.array(jet.get_left())
            m.put_start_and_end_on(
                tail + np.array([-jet.width * 1.9, 0, 0]), tail)
        trail.add_updater(ride)                # after jet in family order
        g.add(jet, trail)
    elif kind == "orbit":
        sun = Circle(radius=0.5 * scale, stroke_width=0,
                     fill_color="#f4c34a", fill_opacity=1.0)
        ring = Circle(radius=2.4 * scale, color=COOL,
                      stroke_width=3 * scale)
        planet = ASSETS["earth"](scale * 0.12).move_to([2.4 * scale, 0, 0])
        planet.add_updater(lambda m, dt, sun=sun: m.rotate(
            dt * 0.16, about_point=sun.get_center()))     # rides the ring
        # ORBIT RIDE (§7.5 v5): the path LIGHTS UP behind the travelling
        # planet — the Sun visibly drags Earth along a growing arc.
        trail = Arc(radius=2.4 * scale, start_angle=0.0, angle=1e-3,
                    color=hi, stroke_width=4.5 * scale, stroke_opacity=0.8)
        _ride = {"cum": 0.0, "prev": 0.0}

        def orbit_trail(m, planet=planet, sun=sun, ring=ring, st=_ride):
            c = np.array(sun.get_center())
            rel = np.array(planet.get_center()) - c
            ang = math.atan2(rel[1], rel[0])
            d = ang - st["prev"]
            while d < -math.pi:
                d += 2 * math.pi
            while d > math.pi:
                d -= 2 * math.pi
            st["cum"] = min(2 * math.pi - 1e-3, st["cum"] + max(0.0, d))
            st["prev"] = ang
            new = Arc(radius=float(np.linalg.norm(rel)),
                      start_angle=ang - st["cum"], angle=st["cum"],
                      arc_center=c, color=trail.get_color(),
                      stroke_width=ring.get_stroke_width() * 1.6,
                      stroke_opacity=0.8)
            m.become(new)
        trail.add_updater(orbit_trail)
        g.add(sun, ring, trail, planet)
    elif kind == "galaxy":
        arms = VGroup()
        for arm in range(4):
            th0 = arm * math.pi / 2
            pts_sp = [[r * math.cos(th0 + 2.4 * r / scale),
                       r * math.sin(th0 + 2.4 * r / scale), 0]
                      for r in np.linspace(0.25 * scale, 2.9 * scale, 36)]
            for a, b in zip(pts_sp, pts_sp[1:]):
                arms.add(Line(a, b, color="#8fa8d9", stroke_width=3,
                              stroke_opacity=0.8))
        core = Circle(radius=0.45 * scale, stroke_width=0,
                      fill_color="#f4e6c0", fill_opacity=0.9)
        arms.add_updater(lambda m, dt, core=core: m.rotate(
            dt * 0.045, about_point=core.get_center()))
        # GALAXY CARRY (§7.5 v5): the whole solar system — a marked gold
        # dot with a trail — is VISIBLY carried outward along a spiral
        # arm. Being carried is the fact; the dot riding is the proof.
        sol = Dot([0.0, 0.0, 0.0], radius=0.085 * scale, color="#ffd9a0")
        soltrail = Line([0, 0, 0], [1e-4, 0, 0], color="#ffd9a0",
                        stroke_width=4 * scale, stroke_opacity=0.55)
        _carry = {"s": 6.0}

        def sol_ride(m, dt, arms=arms, st=_carry):
            st["s"] = min(33.9, st["s"] + dt * 0.9)
            i0 = int(st["s"])
            frac = st["s"] - i0
            seg = arms[i0]          # arm 0 = segments [0..34], live coords
            p = ((1 - frac) * np.array(seg.get_start())
                 + frac * np.array(seg.get_end()))
            m.move_to(p)
        sol.add_updater(sol_ride)

        def sol_trail(m, sol=sol, arms=arms, st=_carry):
            back = arms[max(0, int(st["s"]) - 5)]
            a_pt = np.array(back.get_start())
            b_pt = np.array(sol.get_center())
            if np.linalg.norm(b_pt - a_pt) < 1e-4:
                b_pt = a_pt + np.array([1e-4, 0.0, 0.0])
            m.put_start_and_end_on(a_pt, b_pt)
        soltrail.add_updater(sol_trail)
        g.add(arms, core, soltrail, sol)
    elif kind == "human":
        g.add(ASSETS["human"](scale * 2.2))
    label = Text(_diet(p.get("label", "")), font_size=int(30 * scale),
                 color=GRAY_TEXT)
    value = Text(str(p.get("display", "")), font_size=int(46 * scale),
                 weight=BOLD, color=hi)
    stamp = VGroup(label, value).arrange(DOWN, aligned_edge=RIGHT,
                                         buff=0.12 * scale)
    # RIGHT-aligned inside the push-in frame (half-width ~4.8 at 0.88 fw)
    # so a wide number never clips the edge.
    stamp.move_to([4.2 * scale, -2.2 * scale, 0], aligned_edge=RIGHT)
    g.add(stamp)
    _settle(g, anchor, post_scale)
    STATE.setdefault(f"level:{kind}", g)     # the world remembers
    # The zoom itself is the REVEAL (the gate fades the level in — an
    # opacity anim would fight it), but the level still owes the beat an
    # escalating timeline: gate-safe POSITIONAL events (the tableau's own
    # physics on fast-forward) plus the stamp payoff.
    value = stamp[1]
    anims = []
    if kind == "earth":
        c = np.array(earth.get_center())
        motions = [_Par([Rotate(earth, ang, about_point=c)], run_time=rt)
                   for ang, rt in ((0.55, 2.2), (0.7, 2.6), (0.6, 2.4))]
    elif kind == "sky":
        motions = [_Par([jet.animate(
            rate_func=rate_functions.ease_in_out_sine)
            .shift(np.array([jet.width * dx, 0.0, 0.0]))], run_time=rt)
            for dx, rt in ((1.3, 1.5), (1.1, 1.4), (1.4, 1.6))]
    elif kind == "orbit":
        c = np.array(sun.get_center())
        motions = [_Par([Rotate(planet, ang, about_point=c)], run_time=rt)
                   for ang, rt in ((1.3, 2.0), (1.6, 2.4), (1.2, 2.0))]
        # CONSEQUENCE: for one stretch the camera is PULLED ALONG with
        # the dragged planet — the viewer rides the orbit, then the
        # dwell re-centres to reveal the lit path behind it.
        motions[1].cam = (lambda cx, p=planet: [
            cx["frame"].animate(rate_func=rate_functions.ease_in_out_sine)
            .move_to(np.array(p.get_center()))
            .set(width=cx["fw"] * 0.55)])
    elif kind == "galaxy":
        c = np.array(core.get_center())
        motions = [_Par([Rotate(arms, ang, about_point=c)], run_time=rt)
                   for ang, rt in ((0.4, 2.4), (0.5, 2.8), (0.45, 2.6))]
    else:
        motions = [_Par([Rotate(g[0], sgn * 0.05)], run_time=1.2)
                   for sgn in (1, -1, 1)]
    # the tableau's physics build first; the number lands LAST — the
    # beat culminates (payoff grade C: end stronger than you started)
    anims.extend(motions)
    anims.append(_Par([value.animate(
        rate_func=rate_functions.ease_out_back).scale(1.18)],
        run_time=0.7, punch=True, focus="stamp"))
    return g, anims
