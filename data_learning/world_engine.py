#!/usr/bin/env python3
"""The simulation engine's compositor — one place, one camera, one take.

Executes a renderer-agnostic VISUAL SCRIPT (the IR): a world template lays
out waypoints as points of interest in ONE connected place; a single camera
makes one continuous journey through it, arriving at each waypoint as its
narration beat begins. There are no cuts in the body — transitions ARE
camera moves, and the frame is never locked (dwell = slow real frame creep,
not post-hoc Ken Burns).

Manim's MovingCameraScene is used strictly as the 2.5D compositor/camera
behind the IR — an implementation detail, not the engine's identity
(CURIOSITY_BRAIN.md §7.5). Blender heroes and footage are sibling backends
spliced by the assembler (longform_render) over their waypoint's window.

IR (the "world" block of a story in curiosity.config.json):
    {
      "template": "depth" | "scale" | "system",
      "story_template": "mystery-reveal" | "question-journey-discovery" |
                        "scale-comparison-perspective" | "countdown-winner-surprise",
      "waypoints": [
        {"builder": "<object builder name>",
         "params": {...},                  # builder-specific (incl. data file)
         "camera": "dive|glide|push|pullback|track",   # entry move flavor
         "hero": "earth_dive"|"monoliths"?  # blender splice over this window
        }, ...                             # waypoint i <-> narration beat i+1
      ]
    }

The renderer writes a full runtime spec (IR + narration windows + theme +
chrome strings) to a JSON file and invokes:

    CURIO_WORLD_SPEC=/path/spec.json python -m manim render -qm --fps 30 \
        -r 1920,1080 data_learning/world_engine.py WorldScene
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from manim import (BOLD, DOWN, LEFT, RIGHT, UP, UL, Circle, Dot, FadeIn,
                   FadeOut, Line, MovingCameraScene, Rectangle, Text,
                   ValueTracker, VGroup, always_redraw, rate_functions)

# manim runs this file by path — make the repo importable so the canonical
# builder registry (data_learning.world_builders) resolves to ONE module.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

FRAME_W0 = 14.222                 # manim default frame width (1920x1080)
GRAY_TEXT = "#98a2b4"


# ---------------------------------------------------------------------------
# World templates — ONE PLACE per archetype. A template returns, for each
# waypoint index, (anchor xy, frame_width at that waypoint) plus builds the
# world's connective tissue (backdrop, path geometry) so the journey reads
# as one continuous place, never as islands.
# ---------------------------------------------------------------------------
def _layout_depth(n: int):
    """Vertical descent: surface at the top, waypoints stacked downward.
    Spacing generous enough that neighbours aren't co-visible at dwell zoom."""
    fw = 11.0
    step = fw * 1.35
    return [([0.0, -i * step, 0.0], fw) for i in range(n)], step


def _layout_scale(n: int):
    """One continuous zoom axis: all waypoints share a centre; each level's
    frame is Z× wider than the last (powers-of-ten). Objects for level i are
    built at scale fw_i/11 so each fills its own frame."""
    z = 7.0
    return [([0.0, 0.0, 0.0], 11.0 * (z ** i)) for i in range(n)], z


def _layout_system(n: int):
    """A map/flow surface the camera tracks across, left to right with a
    gentle meander."""
    fw = 11.0
    step = fw * 1.30
    return ([([i * step, 2.2 * math.sin(i * 1.1), 0.0], fw)
             for i in range(n)], step)


LAYOUTS = {"depth": _layout_depth, "scale": _layout_scale,
           "system": _layout_system}


def _backdrop_depth(anchors, theme):
    """Strata bands + drifting rock blobs spanning the whole journey."""
    g = VGroup()
    top = anchors[0][1] + 8
    bot = anchors[-1][1] - 10
    band_cols = ["#141a2c", "#101626", "#0c1220", "#0a0e1a"]
    n_bands = max(6, int((top - bot) / 6))
    for i in range(n_bands):
        y0 = top + (bot - top) * i / n_bands
        y1 = top + (bot - top) * (i + 1) / n_bands
        g.add(Rectangle(width=90, height=abs(y1 - y0) + 0.05, stroke_width=0,
                        fill_color=band_cols[i % 4], fill_opacity=1.0)
              .move_to([0, (y0 + y1) / 2, 0]))
    rocks = VGroup()
    for i in range(90):
        rx = ((i * 37) % 700) / 10.0 - 35
        ry = top + (bot - top) * (((i * 61) % 100) / 100.0)
        rocks.add(Circle(radius=0.08 + (i % 4) * 0.07, stroke_width=0,
                         fill_color="#232c44", fill_opacity=0.75)
                  .move_to([rx, ry, 0]))
    return g, rocks


def _backdrop_space(anchors, theme):
    """Star field spanning the widest frame (scale worlds zoom, not travel)."""
    g = VGroup()                                     # no strata bands
    span = (max(fw for _, fw in anchors) * 1.6) if anchors else 100
    stars = VGroup()
    for i in range(160):
        x = (((i * 73) % 1000) / 1000.0 - 0.5) * span
        y = (((i * 149) % 1000) / 1000.0 - 0.5) * span * 0.6
        r = (0.02 + (i % 3) * 0.015) * max(1.0, span / 100)
        stars.add(Dot([x, y, 0], radius=r,
                      color="#cdd6ea").set_opacity(0.5 + (i % 5) * 0.1))
    return g, stars


BACKDROPS = {"depth": _backdrop_depth, "scale": _backdrop_space,
             "system": _backdrop_depth}


# ---------------------------------------------------------------------------
# The one-take scene.
# ---------------------------------------------------------------------------
def _spec() -> dict:
    return json.loads(open(os.environ["CURIO_WORLD_SPEC"]).read())


class WorldScene(MovingCameraScene):
    def construct(self):
        from data_learning.world_builders import BUILDERS   # canonical copy
        from data_learning.shots import (DEFAULT_DWELL, DEFAULT_TRAVEL,
                                         SHOTS, cold_open_rush)
        sp = _spec()
        theme = sp.get("theme", {})
        self.camera.background_color = theme.get("bg", "#080a14")
        world = sp["world"]
        wps = world["waypoints"]
        windows = sp["windows"]              # [[t0,t1], ...] == sentences
        chrome_meta = sp.get("chrome", [])   # per-beat {role, topic}
        hi = theme.get("highlight", "#4FD1C5")
        accent = theme.get("accent", "#60A5FA")

        anchors, _step = LAYOUTS[world.get("template", "depth")](len(wps))

        # --- backdrop (far + mid parallax layers) ---
        bands, blobs = BACKDROPS[world.get("template", "depth")](anchors, theme)
        frame = self.camera.frame
        # Positional parallax: far layers lag the camera. base positions
        # captured at build time; updaters re-anchor relative to the frame.
        blob_base = blobs.get_center().copy()
        def parallax(m, k=0.35, base=blob_base):
            m.move_to(base + frame.get_center() * k)
        blobs.add_updater(parallax)
        self.add(bands, blobs)

        # --- waypoint objects, placed in the one place ---
        is_scale = world.get("template") == "scale"
        arrival_anims, groups = [], []
        for i, wp in enumerate(wps):
            anchor, fw = anchors[i]
            build = BUILDERS.get(wp.get("builder", "marker"),
                                 BUILDERS["marker"])
            # Builders position themselves at the anchor BEFORE creating
            # animations — .animate targets snapshot coordinates at
            # creation time, so a post-hoc group move would teleport
            # transformed objects back toward the origin (one-take rule).
            if is_scale:
                # Scale levels build at unit design scale, then the GROUP
                # scales geometrically — Text glyphs are vector outlines,
                # so this survives zooms where a 15,000pt font would not.
                g, anims = build(wp, theme, 1.0, np.array(anchor))
                g.scale(fw / 11.0, about_point=np.array(anchor),
                        scale_stroke=True)
            else:
                g, anims = build(wp, theme, fw / 11.0, np.array(anchor))
            # Updaters (live counters) only run while their waypoint is
            # active — a passed or unvisited exhibit costs nothing.
            g.suspend_updating()
            self.add(g)
            arrival_anims.append(anims)
            groups.append(g)

        # Reveal doctrine (non-scale worlds): subjects are BORN as the
        # camera arrives, not pre-placed geometry waiting. Each group is
        # pre-shrunk to a ghost seed; the shot Restores it on arrival.
        # save_state() is taken at designed size/opacity, and builder
        # arrival anims snapshot their targets at creation, so the
        # Restore lands exactly on the coordinates the anims expect.
        # Scale worlds skip this — their zoom visibility gate IS the
        # reveal, and a Restore would fight it.
        if not is_scale:
            for g, wp in zip(groups, wps):
                if wp.get("reveal", True):
                    # Seed stays readable as a DISTANT LANDMARK — the cold
                    # open rushes past unvisited exhibits, and an empty
                    # world reads as a broken render, not anticipation.
                    g.save_state()
                    g.scale(0.45).set_opacity(0.22)
                else:
                    g.save_state()   # shots may Restore unconditionally

        # Scale worlds nest all levels around one centre (powers of ten) —
        # each level is only visible while the camera is near its zoom, so
        # a galaxy arm never slashes through the couch-level frame. The
        # fade PRESERVES each submobject's designed opacity (an atmosphere
        # ring at 0.35 must never become an opaque disc).
        if is_scale:
            for g, (anchor, fw) in zip(groups, anchors):
                designed = [(m, m.get_fill_opacity(), m.get_stroke_opacity(),
                             m.get_stroke_width())
                            for m in g.family_members_with_points()]

                def vis(_g, fw=fw, designed=designed):
                    ratio = frame.width / fw
                    o = 1.0 if 0.45 <= ratio <= 2.4 else max(
                        0.0, 1.0 - 0.9 * abs(math.log(max(ratio, 1e-6), 3)))
                    for m, f0, s0, w0 in designed:
                        m.set_fill(opacity=f0 * o)
                        if w0 > 0:      # never conjure a stroke that wasn't
                            m.set_stroke(opacity=s0 * o)   # designed in
                g.add_updater(vis)
                g.resume_updating()          # visibility must always run

        # --- connective tissue for depth/system worlds: the journey line ---
        if world.get("template") in (None, "depth", "system"):
            pts = [a for a, _ in anchors]
            for a, b in zip(pts, pts[1:]):
                self.add(Line(a, b, color=hi, stroke_width=5,
                              stroke_opacity=0.55))

        # --- chrome pinned to the camera frame (rides the journey) ---
        def chrome_for(i):
            meta = (chrome_meta[i] if i < len(chrome_meta) else {})
            role = Text(str(meta.get("role", "")).upper(), font_size=26,
                        weight=BOLD, color=accent)
            topic = Text(" ".join(w[:1].upper() + w[1:] for w in
                                  str(meta.get("topic", "")).split()),
                         font_size=42, weight=BOLD, color="#ffffff")
            g = VGroup(role, topic).arrange(DOWN, aligned_edge=LEFT, buff=0.15)

            base_w = g.width or 1.0

            def pin(m, base_w=base_w):
                s = frame.width / FRAME_W0
                m.set_width(min(base_w, 5.4) * s)   # absolute each frame
                m.move_to(frame.get_corner(UL)
                          + np.array([0.6, -0.65, 0]) * s, aligned_edge=UL)
            g.add_updater(pin)
            return g

        # --- the journey ---
        title_w = windows[0][1] - windows[0][0]
        a0, fw0 = anchors[0]
        title = Text(sp.get("title", ""), font_size=64, weight=BOLD,
                     color="#ffffff")
        title_pin = VGroup(title)

        title_base_w = min(title_pin.width or 9.0, 9.0)

        def pin_title(m):
            m.set_width(title_base_w * frame.width / FRAME_W0)
            m.move_to(frame.get_center() + np.array([0, frame.height * 0.28, 0]))
        title_pin.add_updater(pin_title)
        self.add(title_pin)

        cold = world.get("cold_open")
        if cold:
            # The hook is a RIDE: sprint through the WHOLE world with the
            # title pinned to the frame — show the ride first, explain it
            # second — then reset to level 0 for the narrated journey.
            frame.set(width=fw0 * 1.15).move_to(np.array(a0))
            surge, counter = None, None
            if isinstance(cold, dict) and cold.get("value"):
                v = ValueTracker(0.0)
                unit = str(cold.get("unit", ""))

                def _mk_counter(v=v, unit=unit):
                    t = Text(f"{int(v.get_value()):,} {unit}".strip(),
                             font_size=54, weight=BOLD, color=hi)
                    t.scale(frame.height * 0.075 / max(t.height, 1e-6))
                    t.move_to(frame.get_center()
                              + np.array([0, -frame.height * 0.30, 0]))
                    return t
                counter = always_redraw(_mk_counter)
                self.add(counter)
                surge = (v, float(cold["value"]))
            cold_open_rush(self, {"frame": frame, "anchors_all": anchors,
                                  "dur": max(2.5, title_w - 0.35),
                                  "surge": surge})
            if counter is not None:
                self.remove(counter)     # always_redraw defeats FadeOut
            self.play(FadeOut(title_pin), run_time=0.35)
        else:
            # Classic entry: start wide above the first waypoint, glide in.
            frame.set(width=fw0 * 2.6).move_to(
                np.array(a0) + np.array([0, fw0 * 0.5, 0]))
            self.play(frame.animate.set(width=fw0 * 1.9),
                      run_time=title_w * 0.8,
                      rate_func=rate_functions.ease_in_out_sine)
            self.play(FadeOut(title_pin), run_time=max(0.3, title_w * 0.2))

        # The waypoint loop is a thin dispatcher over the shot vocabulary
        # (data_learning/shots.py): a SHOT owns the approach, arrival
        # choreography, chrome in/out, and dwell for exactly its window.
        # Un-annotated waypoints draw from the template's default cycle,
        # never repeating the same shot back-to-back.
        tpl = world.get("template", "depth")
        travel_cycle = DEFAULT_TRAVEL.get(tpl, DEFAULT_TRAVEL["depth"])
        dwell_cycle = DEFAULT_DWELL.get(tpl, DEFAULT_DWELL["depth"])
        last_shot = None
        for i, wp in enumerate(wps):
            t0, t1 = windows[i + 1]
            dur = t1 - t0
            anchor, fw = anchors[i]
            name = wp.get("shot")
            if not name or name not in SHOTS:
                name = travel_cycle[i % len(travel_cycle)]
                if name == last_shot:
                    name = next((s for s in travel_cycle if s != last_shot),
                                name)
            ctx = {
                "frame": frame, "anchor": np.array(anchor), "fw": fw,
                "dur": dur, "group": groups[i],
                "arrival_anims": arrival_anims[i],
                "chrome_factory": (lambda i=i: chrome_for(i)),
                "idx": i, "is_scale": is_scale, "anchors_all": anchors,
                "dwell": wp.get("dwell") or dwell_cycle[i % len(dwell_cycle)],
                "reveal_target": (groups[i] if not is_scale
                                  and wp.get("reveal", True) else None),
            }
            SHOTS[name](self, ctx)
            last_shot = name
            if not is_scale:
                groups[i].suspend_updating()   # scale keeps visibility upds

        # Exit: final pullback reveals the whole journey; closing text pins.
        t0, t1 = windows[-1]
        if world.get("template") == "scale":
            # Exit for a zoom world: pull out past the widest level.
            whole_h = max(fw for _, fw in anchors) * 0.9
        else:
            whole_h = abs(anchors[-1][0][1] - anchors[0][0][1]) + 14
        mid = [(anchors[0][0][0] + anchors[-1][0][0]) / 2,
               (anchors[0][0][1] + anchors[-1][0][1]) / 2, 0]
        closing = Text(sp.get("closing", ""), font_size=48, weight=BOLD,
                       color="#ffffff")
        cpin = VGroup(closing)

        close_ratio = 0.62

        def pin_close(m):
            m.set_width(frame.width * close_ratio)
            m.move_to(frame.get_center()
                      + np.array([0, -frame.height * 0.30, 0]))
        cpin.add_updater(pin_close)
        self.add(cpin)
        self.play(frame.animate.move_to(mid).set(
            width=max(whole_h * 16 / 9, anchors[0][1] * 2.2)),
            run_time=(t1 - t0),
            rate_func=rate_functions.ease_in_out_sine)
