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
        topic = Text(sp.get("topic", "").title(), font_size=44, weight=BOLD,
                     color="#ffffff")
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
