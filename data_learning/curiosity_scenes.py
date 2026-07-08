#!/usr/bin/env python3
"""Manim beat library for the curiosity channel's long-form renderer.

Each beat of a story renders as a real MOTION scene (bars race up while
counters spin, lines draw on, columns duel) instead of a static chart with
a pan. Spec-driven so the pipeline stays headless: the renderer writes a
JSON spec, sets $CURIO_SPEC, and invokes `manim render` on this module.

Deliberately TeX-free: every glyph is Pango `Text` (Manim's `Integer`/
`MathTex` would drag a LaTeX install into CI for no benefit).

Spec shape (written by longform_render._manim_beat):
    {
      "kind": "rank" | "comparison" | "trend",
      "role": "1 · THE RECORD", "topic": "deepest points ever reached",
      "unit": "m", "source": "Source: ...",
      "bg": "#0a0e20", "accent": "#60A5FA", "highlight": "#4FD1C5",
      "points": [{"label": "Kola Borehole", "value": 12262,
                  "period": "1979"?}, ...]     # trend points use period
    }

Manual test:
    CURIO_SPEC=/tmp/spec.json python -m manim render -qm --fps 30 \
        -r 1920,1080 data_learning/curiosity_scenes.py RankBeat
"""
from __future__ import annotations

import json
import os

from manim import (BOLD, DOWN, LEFT, RIGHT, UP, Dot, Line, Rectangle,
                   Scene, Text, ValueTracker, VGroup, always_redraw,
                   rate_functions)

GRAY_TEXT = "#98a2b4"
FAINT = "#3a4356"


def _spec() -> dict:
    return json.loads(open(os.environ["CURIO_SPEC"]).read())


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if float(v).is_integer():
        return f"{v:.0f}"
    return f"{v:,.1f}"


class _BeatBase(Scene):
    """Shared chrome: theme background, heading (role + topic), source
    footer — the same visual system on every beat, per the style bible."""

    def setup_chrome(self, sp: dict):
        self.camera.background_color = sp.get("bg", "#0a0e20")
        role = Text(sp.get("role", "").upper(), font_size=26, weight=BOLD,
                    color=sp.get("accent", "#60A5FA"))
        # str.title() breaks on apostrophes ("Earth'S"); cap word-starts only.
        heading = " ".join(w[:1].upper() + w[1:]
                           for w in sp.get("topic", "").split())
        topic = Text(heading, font_size=44, weight=BOLD, color="#ffffff")
        head = VGroup(role, topic).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        head.to_corner(UP + LEFT, buff=0.55)
        rule = Rectangle(width=1.6, height=0.07, stroke_width=0,
                         fill_color=sp.get("highlight", "#4FD1C5"),
                         fill_opacity=1.0)
        rule.next_to(head, DOWN, buff=0.22).align_to(head, LEFT)
        src = Text(sp.get("source", "")[:95], font_size=17, color=GRAY_TEXT)
        src.to_corner(DOWN + LEFT, buff=0.35)
        self.add(head, rule, src)

    def hold(self, seconds: float = 1.0):
        self.wait(seconds)


class RankBeat(_BeatBase):
    """Horizontal bars race in one by one, counters spinning at the tips;
    the champion pulses last. Natural length ~10-16s for 3-5 points."""

    def construct(self):
        sp = _spec()
        self.setup_chrome(sp)
        pts = sp["points"][:5]
        vmax = max(p["value"] for p in pts) or 1.0
        hi, unit = sp.get("highlight", "#4FD1C5"), sp.get("unit", "")
        n = len(pts)
        top_y, row_h = 1.6, min(1.25, 5.2 / n)
        bar_max_w = 7.6
        x0 = -1.4

        rows = []
        for i, p in enumerate(pts):
            y = top_y - i * row_h
            label = Text(p["label"], font_size=30, color="#ffffff")
            label.move_to([x0 - 0.35, y, 0], aligned_edge=RIGHT)
            v = ValueTracker(0.0)
            color = hi if p["value"] == vmax else "#5b8fd9"
            bar = always_redraw(lambda v=v, y=y, color=color: Rectangle(
                width=max(0.02, bar_max_w * v.get_value() / vmax),
                height=row_h * 0.52, stroke_width=0,
                fill_color=color, fill_opacity=0.95,
            ).move_to([x0, y, 0], aligned_edge=LEFT))
            num = always_redraw(lambda v=v, y=y: Text(
                f"{_fmt(v.get_value())} {unit}".strip(), font_size=27,
                weight=BOLD, color="#ffffff",
            ).move_to([x0 + max(0.02, bar_max_w * v.get_value() / vmax) + 0.25,
                       y, 0], aligned_edge=LEFT))
            self.add(label, bar, num)
            rows.append((v, p))

        # Reveal smallest -> biggest so the record lands LAST (the payoff).
        for v, p in sorted(rows, key=lambda r: r[1]["value"]):
            self.play(v.animate.set_value(p["value"]),
                      run_time=1.6 if p["value"] == vmax else 1.1,
                      rate_func=rate_functions.ease_out_cubic)
        # Champion pulse.
        star_v = max(rows, key=lambda r: r[1]["value"])[0]
        self.play(star_v.animate.set_value(vmax * 1.0), run_time=0.01)
        self.hold(1.2)


class CompareBeat(_BeatBase):
    """Two columns duel: the small one lands first, then the big one keeps
    going... and going — then the multiple stamps on. ~10-14s."""

    def construct(self):
        sp = _spec()
        self.setup_chrome(sp)
        pts = sorted(sp["points"][:2], key=lambda p: p["value"])
        if len(pts) < 2:
            pts = pts * 2
        small, big = pts[0], pts[1]
        hi, unit = sp.get("highlight", "#4FD1C5"), sp.get("unit", "")
        vmax = big["value"] or 1.0
        col_max_h, base_y = 4.4, -2.6
        xs = [1.2, 4.6]

        cols = []
        for p, x, color in ((small, xs[0], "#5b8fd9"), (big, xs[1], hi)):
            v = ValueTracker(0.0)
            col = always_redraw(lambda v=v, x=x, color=color: Rectangle(
                width=1.7, height=max(0.03, col_max_h * v.get_value() / vmax),
                stroke_width=0, fill_color=color, fill_opacity=0.95,
            ).move_to([x, base_y, 0], aligned_edge=DOWN))
            num = always_redraw(lambda v=v, x=x: Text(
                f"{_fmt(v.get_value())} {unit}".strip(), font_size=30,
                weight=BOLD, color="#ffffff",
            ).move_to([x, base_y + max(0.03, col_max_h * v.get_value() / vmax)
                       + 0.35, 0]))
            label = Text(p["label"], font_size=26, color=GRAY_TEXT)
            label.move_to([x, base_y - 0.45, 0])
            self.add(col, num, label)
            cols.append((v, p))

        self.play(cols[0][0].animate.set_value(small["value"]), run_time=1.4,
                  rate_func=rate_functions.ease_out_cubic)
        self.hold(0.4)
        self.play(cols[1][0].animate.set_value(big["value"]), run_time=2.6,
                  rate_func=rate_functions.ease_out_cubic)
        if small["value"] > 0 and big["value"] / small["value"] >= 1.5:
            mult = Text(f"{big['value'] / small['value']:,.0f}× more",
                        font_size=54, weight=BOLD, color=hi)
            mult.move_to([(xs[0] + xs[1]) / 2 - 3.6, 0.6, 0])
            self.play(mult.animate.scale(1.0), run_time=0.4)
        self.hold(1.2)


class TrendBeat(_BeatBase):
    """A line draws itself point to point (hand-built — no Axes, no TeX),
    a dot rides it, the counter chases the value. ~10-14s."""

    def construct(self):
        sp = _spec()
        self.setup_chrome(sp)
        pts = sp["points"]
        hi, unit = sp.get("highlight", "#4FD1C5"), sp.get("unit", "")
        vals = [p["value"] for p in pts]
        vmin, vmax = min(vals), max(vals)
        span = (vmax - vmin) or 1.0
        x_left, x_right, y_bot, y_top = 0.0, 6.4, -2.4, 1.9

        def xy(i, v):
            x = x_left + (x_right - x_left) * (i / max(1, len(pts) - 1))
            y = y_bot + (y_top - y_bot) * ((v - vmin) / span)
            return [x, y, 0]

        # Baseline + period labels.
        self.add(Line([x_left - 0.2, y_bot - 0.35, 0],
                      [x_right + 0.2, y_bot - 0.35, 0],
                      color=FAINT, stroke_width=2))
        for i, p in enumerate(pts):
            t = Text(str(p.get("period", p.get("label", ""))),
                     font_size=22, color=GRAY_TEXT)
            t.move_to([xy(i, vmin)[0], y_bot - 0.7, 0])
            self.add(t)

        v = ValueTracker(vals[0])
        prog = ValueTracker(0.0)          # fractional index along the series

        def polyline():
            f = prog.get_value()
            segs = VGroup()
            i = 0
            while i + 1 <= f and i + 1 < len(pts):
                segs.add(Line(xy(i, vals[i]), xy(i + 1, vals[i + 1]),
                              color=hi, stroke_width=7))
                i += 1
            if i < len(pts) - 1 and f > i:
                u = f - i
                a, b = xy(i, vals[i]), xy(i + 1, vals[i + 1])
                mid = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 0]
                segs.add(Line(a, mid, color=hi, stroke_width=7))
            return segs

        def head():
            f = min(prog.get_value(), len(pts) - 1)
            i = int(f)
            u = f - i
            if i >= len(pts) - 1:
                p = xy(len(pts) - 1, vals[-1])
            else:
                a, b = xy(i, vals[i]), xy(i + 1, vals[i + 1])
                p = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 0]
            return Dot(p, radius=0.11, color="#ffffff")

        line = always_redraw(polyline)
        dot = always_redraw(head)
        num = always_redraw(lambda: Text(
            f"{_fmt(v.get_value())} {unit}".strip(), font_size=48,
            weight=BOLD, color=hi).to_corner(UP + RIGHT, buff=0.7))
        self.add(line, dot, num)

        for i in range(1, len(pts)):
            self.play(prog.animate.set_value(i),
                      v.animate.set_value(vals[i]),
                      run_time=max(1.0, 4.5 / (len(pts) - 1)),
                      rate_func=rate_functions.ease_in_out_sine)
        self.hold(1.4)


SCENE_FOR_KIND = {"rank": "RankBeat", "comparison": "CompareBeat",
                  "trend": "TrendBeat"}


# ==========================================================================
# ILLUSTRATIVE PRIMITIVES — the visual storytelling engine (tier 1/2).
# Journeys, not graphs: the camera travels, numbers stamp in as waypoints.
# All plain Scenes animating a WORLD group (chrome stays fixed), all
# spec-driven, all reusable across stories.
# ==========================================================================
import numpy as np
from manim import (Arc, ArcBetweenPoints, Circle, DashedLine, FadeIn,
                   FadeOut, ORIGIN, Polygon, Triangle)


class DescentBeat(_BeatBase):
    """The camera falls down a cross-section shaft past depth markers —
    ...and keeps falling through the empty distance to the deepest value.
    points: [{label, value}] where value is a DEPTH in `unit`."""

    def construct(self):
        sp = _spec()
        hi = sp.get("highlight", "#4FD1C5")
        unit = sp.get("unit", "")
        pts = sorted(sp["points"], key=lambda p: p["value"])
        deepest = pts[-1]["value"] or 1.0
        # Log-ish mapping so a 12 km marker and a 6,371 km floor can share
        # one shaft without the top markers overlapping.
        import math
        def depth_y(v):
            return -math.log10(1 + 9 * v / deepest) * 16.0   # 0..-16 units

        world = VGroup()
        ground = Line([-8, 0.9, 0], [8, 0.9, 0], color="#e8ecf4",
                      stroke_width=5)
        world.add(ground)
        # Strata bands with alternating tones + drifting rock blobs.
        y_floor = depth_y(deepest) - 2.5
        band_cols = ["#141a2c", "#101626", "#0c1220", "#0a0e1a"]
        n_bands = 12
        for i in range(n_bands):
            y0 = 0.9 + (y_floor - 0.9) * i / n_bands
            y1 = 0.9 + (y_floor - 0.9) * (i + 1) / n_bands
            world.add(Rectangle(width=16, height=abs(y1 - y0), stroke_width=0,
                                fill_color=band_cols[i % 4], fill_opacity=1.0)
                      .move_to([0, (y0 + y1) / 2, 0]))
            for j in range(3):
                bx = ((i * 37 + j * 53) % 130) / 10.0 - 6.5
                by = y0 + (y1 - y0) * (((i * 17 + j * 29) % 10) / 10.0)
                world.add(Circle(radius=0.06 + ((i + j) % 3) * 0.05,
                                 stroke_width=0, fill_color="#232c44",
                                 fill_opacity=0.8).move_to([bx, by, 0]))
        # The shaft.
        world.add(Line([0, 0.9, 0], [0, depth_y(deepest), 0], color=hi,
                       stroke_width=6))
        # Waypoint markers.
        for p in pts:
            y = depth_y(p["value"])
            star = p["value"] == deepest
            world.add(DashedLine([-3.4, y, 0], [3.4, y, 0],
                                 color=hi if star else "#5b8fd9",
                                 stroke_width=4 if star else 2.5))
            world.add(Text(p["label"], font_size=30 if star else 25,
                           weight=BOLD, color="#ffffff")
                      .move_to([-3.7, y, 0], aligned_edge=RIGHT))
            world.add(Text(f"{_fmt(p['value'])} {unit}".strip(),
                           font_size=32 if star else 25, weight=BOLD,
                           color=hi if star else GRAY_TEXT)
                      .move_to([3.7, y, 0], aligned_edge=LEFT))
        self.add(world)
        self.setup_chrome(sp)          # chrome AFTER the world = on top
        # Depth counter riding the fall.
        v = ValueTracker(0.0)
        counter = always_redraw(lambda: Text(
            f"{_fmt(v.get_value())} {unit}".strip(), font_size=46,
            weight=BOLD, color=hi).to_corner(UP + RIGHT, buff=0.7))
        self.add(counter)
        # The fall: ease through the marker cluster, cruise the empty gulf.
        total_shift = -depth_y(deepest) + 1.2
        self.play(world.animate.shift(UP * total_shift),
                  v.animate.set_value(deepest),
                  run_time=11.0, rate_func=rate_functions.ease_in_out_sine)
        self.hold(1.6)


class ZoomOutBeat(_BeatBase):
    """The cosmic address: each tableau shrinks into a dot of the next,
    stamping its number on the way out (powers-of-ten grammar).
    points: [{label, value}] ordered small scale -> large scale."""

    def _tableau(self, idx: int, hi: str):
        g = VGroup()
        if idx == 0:                                   # the spinning Earth
            earth = Circle(radius=1.5, stroke_width=0, fill_color="#1c4a8c",
                           fill_opacity=1.0)
            g.add(earth)
            for k in range(4):
                g.add(Circle(radius=0.28 + (k % 2) * 0.12, stroke_width=0,
                             fill_color="#2f8f5b", fill_opacity=0.95)
                      .move_to([0.7 - k * 0.5, 0.5 - (k % 3) * 0.55, 0]))
            g.add(Arc(radius=1.95, start_angle=-0.6, angle=2.0,
                      color=hi, stroke_width=6))
            g.add(Triangle(stroke_width=0, fill_color=hi, fill_opacity=1.0)
                  .scale(0.14).rotate(-1.2).move_to(
                      [1.95 * np.cos(1.4), 1.95 * np.sin(1.4), 0]))
        elif idx == 1:                                 # orbit around the Sun
            g.add(Circle(radius=0.55, stroke_width=0, fill_color="#f4c34a",
                         fill_opacity=1.0))
            g.add(Circle(radius=2.6, color="#5b8fd9", stroke_width=3))
            g.add(Circle(radius=0.16, stroke_width=0, fill_color="#1c4a8c",
                         fill_opacity=1.0).move_to([2.6, 0, 0]))
            g.add(Arc(radius=2.6, start_angle=0.15, angle=1.1, color=hi,
                      stroke_width=6))
        else:                                          # the galaxy
            for arm in range(4):
                th0 = arm * np.pi / 2
                spiral = [
                    [r * np.cos(th0 + 2.4 * r), r * np.sin(th0 + 2.4 * r), 0]
                    for r in np.linspace(0.25, 3.1, 40)]
                for a, b in zip(spiral, spiral[1:]):
                    g.add(Line(a, b, color="#8fa8d9", stroke_width=3,
                               stroke_opacity=0.8))
            g.add(Circle(radius=0.5, stroke_width=0, fill_color="#f4e6c0",
                         fill_opacity=0.9))
            g.add(Dot([2.1 * np.cos(1.1), 2.1 * np.sin(1.1), 0], radius=0.09,
                      color="#ffe9a0"))
        return g

    def construct(self):
        sp = _spec()
        self.setup_chrome(sp)
        hi = sp.get("highlight", "#4FD1C5")
        unit = sp.get("unit", "")
        pts = sorted(sp["points"], key=lambda p: p["value"])[:3]
        center = [1.9, -0.3, 0]
        current = self._tableau(0, hi).move_to(center)
        self.add(current)
        stamp = None
        for i, p in enumerate(pts):
            v = ValueTracker(0.0)
            label = always_redraw(lambda v=v, p=p: VGroup(
                Text(p["label"], font_size=30, color=GRAY_TEXT),
                Text(f"{_fmt(v.get_value())} {unit}".strip(), font_size=44,
                     weight=BOLD, color=hi),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
             .to_corner(DOWN + RIGHT, buff=0.7))   # clear of the heading
            self.add(label)
            self.play(v.animate.set_value(p["value"]), run_time=1.6,
                      rate_func=rate_functions.ease_out_cubic)
            self.hold(0.7)
            if i < len(pts) - 1:
                nxt = self._tableau(i + 1, hi).move_to(center)
                # Shrink the outgoing tableau ONTO its dot in the next one:
                # Earth -> the orbit's planet dot; orbit -> the galaxy's sun.
                dest = ([center[0] + 2.6, center[1], 0] if i == 0 else
                        [center[0] + 2.1 * np.cos(1.1),
                         center[1] + 2.1 * np.sin(1.1), 0])
                self.play(current.animate.scale(0.05).move_to(dest),
                          FadeIn(nxt), run_time=1.8,
                          rate_func=rate_functions.ease_in_out_sine)
                self.remove(label)
                current = nxt
        self.hold(1.2)


class CutawayBeat(_BeatBase):
    """A planet cross-section builds itself layer by layer, then the probe
    line shows how little of it we've touched.
    points: 2 values — the WHOLE (layer thickness) and the PART reached."""

    def construct(self):
        sp = _spec()
        self.setup_chrome(sp)
        hi = sp.get("highlight", "#4FD1C5")
        unit = sp.get("unit", "")
        pts = sorted(sp["points"], key=lambda p: p["value"], reverse=True)
        whole, part = pts[0], pts[-1]
        cx = [2.3, -4.6, 0]                     # planet center, below frame
        r_out = 6.4
        layers = [(r_out, "#2a3350", "surface"),
                  (r_out - 1.5, "#3d2f28", ""),
                  (r_out - 3.0, "#5c3a22", ""),
                  (r_out - 4.4, "#8c5a2a", "")]
        world = VGroup()
        for r, col, _ in layers:
            world.add(Circle(radius=r, stroke_width=0, fill_color=col,
                             fill_opacity=1.0).move_to(cx))
        self.play(FadeIn(world), run_time=1.2)
        # The whole layer: a bracket spanning the outer band.
        depth_frac = 1.5 / r_out                # outer band visual share
        y_top, y_bot = cx[1] + r_out, cx[1] + r_out - 1.5
        wv = ValueTracker(0.0)
        wlabel = always_redraw(lambda: VGroup(
            Text(whole["label"], font_size=24, color=GRAY_TEXT),
            Text(f"{_fmt(wv.get_value())} {unit}".strip(), font_size=32,
                 weight=BOLD, color="#ffffff"),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
         .move_to([5.25, (y_top + y_bot) / 2, 0], aligned_edge=LEFT))
        self.add(Line([5.0, y_top, 0], [5.0, y_bot, 0], color="#ffffff",
                      stroke_width=4),
                 Line([4.85, y_top, 0], [5.15, y_top, 0], color="#ffffff",
                      stroke_width=4),
                 Line([4.85, y_bot, 0], [5.15, y_bot, 0], color="#ffffff",
                      stroke_width=4), wlabel)
        self.play(wv.animate.set_value(whole["value"]), run_time=1.6,
                  rate_func=rate_functions.ease_out_cubic)
        self.hold(0.5)
        # The part: the probe line drills its true fraction of the band.
        frac = max(0.02, min(1.0, part["value"] / whole["value"]))
        probe_y = y_top - 1.5 * frac
        pv = ValueTracker(0.0)
        probe = always_redraw(lambda: Line(
            [cx[0], y_top, 0],
            [cx[0], y_top - 1.5 * frac * min(1.0, pv.get_value()
                                             / max(1e-9, part["value"])), 0],
            color=hi, stroke_width=7))
        plabel = always_redraw(lambda: Text(
            f"{part['label']}: {_fmt(pv.get_value())} {unit}".strip(),
            font_size=34, weight=BOLD, color=hi
        ).move_to([cx[0] - 0.4, probe_y - 0.55, 0], aligned_edge=RIGHT))
        self.add(probe, plabel)
        self.play(pv.animate.set_value(part["value"]), run_time=2.4,
                  rate_func=rate_functions.ease_out_cubic)
        self.hold(1.6)


SCENE_FOR_KIND.update({})
# Named scene overrides a story can request per beat ("scene": "descent").
SCENE_BY_NAME = {"descent": "DescentBeat", "zoomout": "ZoomOutBeat",
                 "cutaway": "CutawayBeat"}
