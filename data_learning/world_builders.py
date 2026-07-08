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
from manim import (BOLD, DOWN, LEFT, RIGHT, UP, Circle, Create, DashedLine,
                   Dot, FadeIn, Line, Polygon, Rectangle, Text, Transform,
                   ValueTracker, VGroup, rate_functions)

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


def builder(name):
    def reg(fn):
        BUILDERS[name] = fn
        return fn
    return reg


@builder("marker")
def _build_marker(wp: dict, theme: dict, scale: float, anchor=None):
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
    if anchor is not None:
        g.move_to(anchor)
    return g, [FadeIn(label, shift=UP * 0.2 * scale)]


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if float(v).is_integer():
        return f"{v:.0f}"
    return f"{v:,.1f}"


def _points(wp: dict) -> tuple[list[dict], str]:
    p = wp.get("params", {})
    f = p.get("file")
    if f:
        d = json.loads((DATA_DIR / f).read_text())
        return d.get("points", []), d.get("unit", p.get("unit", ""))
    return p.get("points", []), p.get("unit", "")


def _counter(v: ValueTracker, unit: str, size: int, color: str,
             anchor, direction=UP, buff=0.3):
    """A live number that stays glued to a sibling mobject (one-take
    safe). `anchor` may be a mobject or a callable returning one."""
    num = Text("0", font_size=size, weight=BOLD, color=color)

    def upd(m):
        a = anchor() if callable(anchor) else anchor
        new = Text(f"{_fmt(v.get_value())} {unit}".strip(),
                   font_size=size, weight=BOLD, color=color)
        new.next_to(a, direction, buff=buff)
        m.become(new)
    num.add_updater(upd)
    return num


# ===========================================================================
# ASSETS — the persistent object library. THE Earth. THE mountain.
# ===========================================================================
ASSETS = {}


def asset(name):
    def reg(fn):
        ASSETS[name] = fn
        return fn
    return reg


@asset("earth")
def _earth(scale=1.0):
    g = VGroup()
    g.add(Circle(radius=1.5 * scale, stroke_width=0, fill_color="#1c4a8c",
                 fill_opacity=1.0))
    for k, (x, y, r) in enumerate([(0.65, 0.55, 0.34), (-0.4, 0.7, 0.26),
                                   (0.2, -0.5, 0.42), (-0.75, -0.35, 0.3),
                                   (0.95, -0.15, 0.22)]):
        g.add(Circle(radius=r * scale, stroke_width=0, fill_color="#2f8f5b",
                     fill_opacity=0.95).move_to([x * scale, y * scale, 0]))
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


# ===========================================================================
# BUILDERS — waypoint exhibits (one-take safe).
# ===========================================================================
@builder("rank")
def _b_rank(wp, theme, scale, anchor=None):
    """Bars race in smallest -> biggest; the champion lands last."""
    pts, unit = _points(wp)
    pts = pts[:5]
    hi = theme.get("highlight", "#4FD1C5")
    vmax = max(p["value"] for p in pts) or 1.0
    n = len(pts)
    row_h = min(1.2, 5.0 / n) * scale
    bar_w = 6.4 * scale
    g = VGroup()
    rows = []
    for i, p in enumerate(sorted(pts, key=lambda q: q["value"])):
        y = (n / 2 - i - 0.5) * row_h * -1
        star = p["value"] == vmax
        label = Text(p["label"], font_size=int(28 * scale), color="#ffffff")
        label.move_to([-1.2 * scale - 0.35 * scale, y, 0], aligned_edge=RIGHT)
        bar = Rectangle(width=0.02, height=row_h * 0.5, stroke_width=0,
                        fill_color=hi if star else COOL, fill_opacity=0.95)
        bar.move_to([-1.2 * scale, y, 0], aligned_edge=LEFT)
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(26 * scale), "#ffffff",
                       anchor=bar, direction=RIGHT, buff=0.25 * scale)
        g.add(label, bar, num)
        rows.append((bar, v, p, star))
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims: .animate snapshots coords
    anims = []
    for bar, v, p, star in rows:
        target_w = max(0.03, bar_w * p["value"] / vmax)
        anims.append(_Par(
            [bar.animate(rate_func=rate_functions.ease_out_cubic)
             .stretch_to_fit_width(target_w, about_edge=LEFT),
             v.animate.set_value(p["value"])],
            run_time=1.5 if star else 1.0))
    return g, anims


class _Par:
    """Tiny AnimationGroup stand-in the engine can `self.play(*a.anims)`.
    Exposes .anims + .run_time; world_engine unpacks it."""

    def __init__(self, anims, run_time=1.0):
        self.anims = anims
        self.run_time = run_time


@builder("compare")
def _b_compare(wp, theme, scale, anchor=None):
    pts, unit = _points(wp)
    pts = sorted(pts[:2], key=lambda p: p["value"])
    if len(pts) < 2:
        pts = pts * 2
    small, big = pts
    hi = theme.get("highlight", "#4FD1C5")
    vmax = big["value"] or 1.0
    col_h = 4.0 * scale
    g = VGroup()
    cols = []
    for p, x, color in ((small, -1.4 * scale, COOL), (big, 1.4 * scale, hi)):
        col = Rectangle(width=1.5 * scale, height=0.03, stroke_width=0,
                        fill_color=color, fill_opacity=0.95)
        col.move_to([x, -2.0 * scale, 0], aligned_edge=DOWN)
        v = ValueTracker(0.0)
        num = _counter(v, unit, int(28 * scale), "#ffffff",
                       anchor=col, direction=UP, buff=0.3 * scale)
        label = Text(p["label"], font_size=int(24 * scale), color=GRAY_TEXT)
        label.move_to([x, -2.45 * scale, 0])
        g.add(col, num, label)
        cols.append((col, v, p))
    mult = None
    if small["value"] > 0 and big["value"] / small["value"] >= 1.5:
        mult = Text(f"{big['value'] / small['value']:,.0f}×",
                    font_size=int(52 * scale), weight=BOLD, color=hi)
        mult.move_to([0, 1.6 * scale, 0])
        mult.set_opacity(0)
        g.add(mult)
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims: .animate snapshots coords
    anims = []
    for col, v, p in cols:
        h = max(0.03, col_h * p["value"] / vmax)
        anims.append(_Par(
            [col.animate(rate_func=rate_functions.ease_out_cubic)
             .stretch_to_fit_height(h, about_edge=DOWN),
             v.animate.set_value(p["value"])],
            run_time=1.3 if p is small else 2.2))
    if mult is not None:
        anims.append(_Par([mult.animate.set_opacity(1.0)], run_time=0.5))
    return g, anims


@builder("gauge")
def _b_gauge(wp, theme, scale, anchor=None):
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
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims: .animate snapshots coords
    target_h = tube_h * (actual["value"] / vmax)
    anims = [
        _Par([fill.animate(rate_func=rate_functions.ease_in_out_sine)
              .stretch_to_fit_height(target_h, about_edge=DOWN),
              v.animate.set_value(actual["value"]),
              glow.animate.set_opacity(0.16)], run_time=3.2),
    ]
    return g, anims


@builder("flipcompare")
def _b_flipcompare(wp, theme, scale, anchor=None):
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
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims + Transform targets
    flipped = mtn.copy().rotate(math.pi)
    flipped.move_to(np.array(shaft.get_start()), aligned_edge=UP)
    anims = [
        _Par([Create(shaft), FadeIn(dlabel)], run_time=1.4),
        _Par([Transform(mtn, flipped)], run_time=1.8),
        _Par([rem.animate.set_opacity(1.0)], run_time=0.8),
    ]
    return g, anims


@builder("drilljourney")
def _b_drilljourney(wp, theme, scale, anchor=None):
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
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims: live world coords below
    top = np.array(string.get_start())
    anims = []
    prev = 0.0
    for stamp, p in stamps:
        y_world = stamp[0].get_center()[1]
        seg_rt = max(0.8, 2.2 * (p["value"] - prev) / vmax)
        anims.append(_Par(
            [string.animate(rate_func=rate_functions.ease_in_out_sine)
             .put_start_and_end_on(top, np.array([top[0], y_world, 0.0])),
             v.animate.set_value(p["value"]),
             stamp.animate.set_opacity(1.0)], run_time=seg_rt))
        prev = p["value"]
    return g, anims


@builder("scalelevel")
def _b_scalelevel(wp, theme, scale, anchor=None):
    """One level of a ScaleWorld: a tableau (earth / orbit / galaxy /
    human...) built from persistent assets at this level's scale, with the
    level's speed/size stamped on arrival."""
    p = wp.get("params", {})
    hi = theme.get("highlight", "#4FD1C5")
    kind = p.get("tableau", "earth")
    g = VGroup()
    if kind == "earth":
        g.add(ASSETS["earth"](scale))
    elif kind == "orbit":
        g.add(Circle(radius=0.5 * scale, stroke_width=0,
                     fill_color="#f4c34a", fill_opacity=1.0))
        g.add(Circle(radius=2.4 * scale, color=COOL,
                     stroke_width=3 * scale))
        g.add(ASSETS["earth"](scale * 0.12).move_to([2.4 * scale, 0, 0]))
    elif kind == "galaxy":
        for arm in range(4):
            th0 = arm * math.pi / 2
            pts_sp = [[r * math.cos(th0 + 2.4 * r / scale),
                       r * math.sin(th0 + 2.4 * r / scale), 0]
                      for r in np.linspace(0.25 * scale, 2.9 * scale, 36)]
            for a, b in zip(pts_sp, pts_sp[1:]):
                g.add(Line(a, b, color="#8fa8d9", stroke_width=3,
                           stroke_opacity=0.8))
        g.add(Circle(radius=0.45 * scale, stroke_width=0,
                     fill_color="#f4e6c0", fill_opacity=0.9))
    elif kind == "human":
        g.add(ASSETS["human"](scale * 2.2))
    label = Text(str(p.get("label", "")), font_size=int(30 * scale),
                 color=GRAY_TEXT)
    value = Text(str(p.get("display", "")), font_size=int(46 * scale),
                 weight=BOLD, color=hi)
    stamp = VGroup(label, value).arrange(DOWN, aligned_edge=LEFT,
                                         buff=0.12 * scale)
    stamp.move_to([2.9 * scale, -2.2 * scale, 0], aligned_edge=LEFT)
    stamp.set_opacity(0)
    g.add(stamp)
    if anchor is not None:
        g.move_to(anchor)          # BEFORE anims: .animate snapshots coords
    anims = [_Par([stamp.animate.set_opacity(1.0)], run_time=0.9)]
    return g, anims
