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
        import data_learning.world_builders as wb
        from data_learning.world_builders import BUILDERS   # canonical copy
        from data_learning.shots import (CAPS, DEFAULT_DWELL, DEFAULT_TRAVEL,
                                         EMOTION_INTENSITY, INTENSITY,
                                         LEDGER, SHOTS, cold_open_rush,
                                         log_event, set_intensity)
        LEDGER.clear()
        wb.STATE.clear()          # the world remembers — per render only
        CAPS.clear()              # capabilities are earned per render
        INTENSITY.update(level=0, stretch=1.0)   # calm until the facts hit
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

        # --- the DUST LAYER (§7.5 v5): frame-relative particles whose
        # drift velocity reads the world INTENSITY live. Invisible while
        # calm; a streaming field by cosmic — continuous, automatic proof
        # that the world is accelerating. Deterministic phases (no RNG).
        dust = VGroup()
        _phase = {}
        for di in range(46):
            dot = Dot([0, 0, 0], radius=0.03, color="#9fb0cd")
            _phase[di] = ((di * 37) % 100) / 100.0
            yfrac = ((di * 61) % 100) / 100.0 - 0.5

            def dust_upd(m, dt, di=di, yfrac=yfrac):
                lv = INTENSITY["level"]
                fw, fh = frame.width, frame.height
                _phase[di] = (_phase[di] + dt * (0.02 + 0.16 * lv)) % 1.0
                c = frame.get_center()
                m.move_to([c[0] + (0.55 - 1.1 * _phase[di]) * fw,
                           c[1] + yfrac * fh * 1.02, 0.0])
                m.set(width=max(1e-4, fw * (0.004 + 0.002 * (di % 3))))
                m.set_opacity(0.0 if lv == 0 else 0.10 + 0.07 * lv)
            dot.add_updater(dust_upd)
            dust.add(dot)
        self.add(dust)

        # --- the GRANTED STAR LAYER (§7.5 v8 no-downgrade law): a
        # parallax starfield that fades in when a hero grants
        # environment:space and NEVER leaves — every later beat runs
        # inside the environment the hero introduced. Frame-relative
        # with per-dot depth drift (same trick as the dust layer), so it
        # survives any zoom. Invisible until granted.
        _grant = {"o": 0.0, "target": 0.0}
        space_layer = VGroup()
        _sphase = {}
        for si in range(30):
            sdot = Dot([0, 0, 0], radius=0.03, color="#dfe8ff")
            _sphase[si] = ((si * 53) % 100) / 100.0
            s_yf = ((si * 71) % 100) / 100.0 - 0.5
            s_depth = 0.25 + ((si * 29) % 80) / 100.0

            def star_upd(m, dt, si=si, s_yf=s_yf, s_depth=s_depth):
                fw, fh = frame.width, frame.height
                _sphase[si] = (_sphase[si]
                               + dt * 0.014 * (0.4 + s_depth)) % 1.0
                c = frame.get_center()
                m.move_to([c[0] + (0.55 - 1.1 * _sphase[si]) * fw,
                           c[1] + s_yf * fh * 1.04, 0.0])
                m.set(width=max(1e-4, fw * 0.0035 * (0.5 + s_depth)))
                m.set_opacity(_grant["o"] * (0.30 + 0.38 * s_depth))
            sdot.add_updater(star_upd)
            space_layer.add(sdot)
        space_layer.add_updater(lambda m, dt: _grant.update(
            o=min(_grant["target"], _grant["o"] + dt * 0.45)))
        self.add(space_layer)

        def grant_fx(scene, ctx, grants):
            """Consumed by the breach's covered span: turning the granted
            environment ON is part of the hero's persistent consequence."""
            if (_grant["target"] == 0.0
                    and any(str(g).startswith("environment:")
                            for g in grants)):
                _grant["target"] = 1.0
                scene.wait(0.9)
                return 0.9
            return 0.0

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
                # Scale levels build at unit design scale, then the
                # builder's _settle zooms the group geometrically BEFORE
                # creating animations — anim targets snapshot coords at
                # creation, so scaling here (after build) would warp
                # played objects back to unit-scale positions.
                g, anims = build(wp, theme, 1.0, np.array(anchor),
                                 post_scale=fw / 11.0)
            else:
                g, anims = build(wp, theme, fw / 11.0, np.array(anchor))
            # Updaters (live counters) only run while their waypoint is
            # active — a passed or unvisited exhibit costs nothing.
            g.suspend_updating()
            self.add(g)
            arrival_anims.append(anims)
            groups.append(g)

        # --- LEGIBILITY QA (§7.5 v8): the engine KNOWS every text's
        # rendered size at its beat's planned frame width — px height =
        # h / fw * 1080 — and where it sits relative to the frame. A
        # violation is a ledger fact the gate fails on, found at build
        # time, not in a finished 4-hour render. Sub-pixel texts are
        # size-reveal seeds (scale 1e-3 stamps), not mistakes — skipped.
        from manim import Text as _Text
        for i, (g, wp) in enumerate(zip(groups, wps)):
            anchor, fw = anchors[i]
            for m in g.family_members_with_points():
                if not isinstance(m, _Text):
                    continue
                px = m.height / max(fw, 1e-9) * 1080.0
                if px < 1.0:                      # reveal seed
                    continue
                if px < 18.0:
                    log_event(self, "legibility", beat=i, what="too-small",
                              text=m.text[:24], px=round(px, 1))
                c = np.array(m.get_center()) - np.array(anchor)
                if (abs(c[0]) + m.width / 2 > fw * 0.46
                        or abs(c[1]) + m.height / 2 > fw * 0.252):
                    log_event(self, "legibility", beat=i, what="off-frame",
                              text=m.text[:24],
                              dx=round(float(c[0]) / fw, 3),
                              dy=round(float(c[1]) / fw, 3))

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
        #
        # The gates live on the BACKDROP (always updating), not on the
        # groups: (a) groups can then suspend/resume like every other
        # world's — counters and idle motion only cost while their level
        # is visited; (b) become()-style counters swap their glyphs every
        # frame, so the gate walks the LIVE family (base opacities cached
        # by id, unknown members default to designed-1.0) — otherwise a
        # deep level's counter would ignore the gate and ghost through
        # every other level at full opacity.
        if is_scale:
            for g, (anchor, fw) in zip(groups, anchors):
                base = {id(m): (m.get_fill_opacity(), m.get_stroke_opacity(),
                                m.get_stroke_width())
                        for m in g.family_members_with_points()}

                def vis(_b, g=g, fw=fw, base=base):
                    ratio = frame.width / fw
                    o = 1.0 if 0.45 <= ratio <= 2.4 else max(
                        0.0, 1.0 - 0.9 * abs(math.log(max(ratio, 1e-6), 3)))
                    for m in g.family_members_with_points():
                        f0, s0, w0 = base.get(id(m), (1.0, 1.0, 0.0))
                        m.set_fill(opacity=f0 * o)
                        if w0 > 0:      # never conjure a stroke that wasn't
                            m.set_stroke(opacity=s0 * o)   # designed in
                bands.add_updater(vis)

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

        def make_surge_counter(v, unit, dy=-0.30, hscale=0.075, role=None):
            """Frame-pinned live number used by the cold open AND the
            returning-counter ending (§7.5 v5). `role` (v8 value-role
            clarity) captions WHAT this number answers — RIGHT NOW vs
            the story's FINAL total — so big values never read as three
            competing answers."""
            def _mk(v=v, unit=unit):
                t = Text(f"{int(v.get_value()):,} {unit}".strip(),
                         font_size=54, weight=BOLD, color=hi)
                t.scale(frame.height * hscale / max(t.height, 1e-6))
                t.move_to(frame.get_center()
                          + np.array([0, frame.height * dy, 0]))
                if not role:
                    return t
                r = Text(str(role).upper(), font_size=26, weight=BOLD,
                         color="#98a2b4")
                r.scale(t.height * 0.30 / max(r.height, 1e-6))
                r.next_to(t, UP, buff=t.height * 0.22)
                return VGroup(r, t)
            return always_redraw(_mk)

        cold = world.get("cold_open")
        if cold:
            # The hook is a RIDE: sprint through the WHOLE world with the
            # title pinned to the frame — show the ride first, explain it
            # second — then reset to level 0 for the narrated journey.
            frame.set(width=fw0 * 1.15).move_to(np.array(a0))
            surge, counter = None, None
            if isinstance(cold, dict) and cold.get("value"):
                v = ValueTracker(0.0)
                counter = make_surge_counter(v, str(cold.get("unit", "")),
                                             role=cold.get("role",
                                                           "right now"))
                self.add(counter)
                surge = (v, float(cold["value"]))
            # cold_open.levels picks which waypoints the rush flies
            # through — chart exhibits sit un-raced ("0" counters, flat
            # bars) until visited, so authors rush the TABLEAU levels.
            lvls = cold.get("levels") if isinstance(cold, dict) else None
            rush_anchors = ([anchors[i] for i in lvls
                             if 0 <= i < len(anchors)] if lvls else
                            list(anchors))
            if not rush_anchors or rush_anchors[0] != anchors[0]:
                rush_anchors = [anchors[0]] + rush_anchors
            cold_open_rush(self, {"frame": frame,
                                  "anchors_all": rush_anchors,
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
            # Drift compensation: manim rounds every play to frame
            # boundaries, so bookkept time slips ~0.02s per play behind
            # the real clock. Each beat re-syncs by consuming up to its
            # window END as measured by the renderer — otherwise beat 7
            # of a 130-play video starts seconds late vs narration.
            now = float(getattr(self.renderer, "time", t0))
            dur = max(3.0, t1 - max(t0, now))
            anchor, fw = anchors[i]
            name = wp.get("shot")
            if not name or name not in SHOTS:
                name = travel_cycle[i % len(travel_cycle)]
                if name == last_shot:
                    name = next((s for s in travel_cycle if s != last_shot),
                                name)
            # World intensity (§7.5 v5): explicit override, else the
            # emotion map CAPPED by story position so the ladder always
            # RISES calm -> cosmic (set_intensity keeps it monotonic).
            cap = int(math.ceil(3 * (i + 1) / max(1, len(wps))))
            lv = wp.get("intensity",
                        min(EMOTION_INTENSITY.get(wp.get("emotion"), cap),
                            cap))
            # SEMANTIC PROGRESSION (§7.5 v8): what this arrival changes
            # in the viewer's understanding — logged as engine facts.
            sems = [{"dim": "metaphor", "what": wp.get("builder",
                                                       "marker")}]
            if is_scale:
                sems.append({"dim": "scale", "what": f"band:{i}"})
            tab = wp.get("params", {}).get("tableau")
            if tab:
                sems.append({"dim": "environment", "what": str(tab)})
            ctx = {
                "frame": frame, "anchor": np.array(anchor), "fw": fw,
                "dur": dur, "group": groups[i],
                "arrival_anims": arrival_anims[i],
                "chrome_factory": (lambda i=i: chrome_for(i)),
                "idx": i, "is_scale": is_scale, "anchors_all": anchors,
                "dwell": wp.get("dwell") or dwell_cycle[i % len(dwell_cycle)],
                "reveal_target": (groups[i] if not is_scale
                                  and wp.get("reveal", True) else None),
                "shot_name": name, "backdrop": blobs,
                "react": wp.get("react"), "emotion": wp.get("emotion"),
                "discovery": wp.get("discovery"), "state": wb.STATE,
                "intensity": lv,
                # v8 hero-integration + no-downgrade plumbing
                "accent": hi, "hero_plan": wp.get("hero_plan"),
                "in_world": wp.get("params", {}).get("mode") == "in_world",
                "grant_fx": grant_fx, "semantics": sems,
            }
            SHOTS[name](self, ctx)
            last_shot = name
            groups[i].suspend_updating()   # gates live on the backdrop

        # Exit: the biggest pullback in the video (engine law).
        t0, t1 = windows[-1]
        closing = Text(sp.get("closing", ""), font_size=48, weight=BOLD,
                       color="#ffffff")
        cpin = VGroup(closing)

        close_ratio = 0.62

        # Scale worlds park their level stamps bottom-right, so the
        # closing line pins to the UPPER third there to avoid colliding
        # with the top level's stamp during the pullback.
        close_y = 0.30 if world.get("template") == "scale" else -0.30

        def pin_close(m):
            m.set_width(frame.width * close_ratio)
            m.move_to(frame.get_center()
                      + np.array([0, frame.height * close_y, 0]))
        cpin.add_updater(pin_close)
        self.add(cpin)
        # HERO ECHO (§7.5 v8 contract stage 5): the ending recalls what
        # the heroes left behind — each consequence object pulses as the
        # finale begins, and the ride-out passes them all again.
        for key, mobj in [(k, m) for k, m in wb.STATE.items()
                          if str(k).startswith("consequence:")][:2]:
            self.play(mobj.animate.scale(1.12), run_time=0.25,
                      rate_func=rate_functions.ease_out_quad)
            self.play(mobj.animate.scale(1 / 1.12), run_time=0.25,
                      rate_func=rate_functions.ease_in_out_sine)
            log_event(self, "echo", hero=str(key).split(":", 1)[1],
                      rt=0.5)
        now = float(getattr(self.renderer, "time", t0))
        exit_rt = max(2.0, t1 - max(t0, now))
        log_event(self, "exit", rt=round(exit_rt, 2))
        if world.get("template") == "scale":
            # ENDING LAW v2 (§7.5 v5): return to the opening with new
            # meaning. Rewind to level 0, force the world to COSMIC (max
            # streaks, dust storm), then one accelerating ride-out
            # THROUGH every band — the camera can no longer hold — while
            # the cold-open's counter RETURNS and surges past its opening
            # value to the story's TRUE final number. The answer persists
            # on screen with the world still streaking past.
            a0, fw0 = anchors[0]
            rewind = min(1.6, exit_rt * 0.2)
            self.play(frame.animate.move_to(np.array(a0)).set(width=fw0),
                      run_time=rewind,
                      rate_func=rate_functions.ease_in_out_cubic)
            spent_x = rewind + set_intensity(
                self, {"backdrop": blobs, "idx": None}, 3)
            ride_anims = [frame.animate.set(
                width=max(fw for _, fw in anchors) * 3.2)]
            if (isinstance(cold, dict) and cold.get("value")
                    and cold.get("final")):
                v_end = ValueTracker(float(cold["value"]))
                # the ANSWER, huge and central, over the streaking world
                self.add(make_surge_counter(v_end,
                                            str(cold.get("unit", "")),
                                            dy=-0.04, hscale=0.105,
                                            role=cold.get("final_role",
                                                          "in total")))
                ride_anims.append(
                    v_end.animate.set_value(float(cold["final"])))
            self.play(*ride_anims,
                      run_time=max(0.5, exit_rt - spent_x),
                      rate_func=rate_functions.ease_in_quad)
        else:
            whole_h = abs(anchors[-1][0][1] - anchors[0][0][1]) + 14
            mid = [(anchors[0][0][0] + anchors[-1][0][0]) / 2,
                   (anchors[0][0][1] + anchors[-1][0][1]) / 2, 0]
            self.play(frame.animate.move_to(mid).set(
                width=max(whole_h * 16 / 9, anchors[0][1] * 2.2)),
                run_time=exit_rt,
                rate_func=rate_functions.ease_in_out_sine)

        # THE LEDGER — written for scripts/qa_escalation.py (design QA
        # runs on rules the engine logged, not on pixel inference).
        log_path = os.environ.get("CURIO_WORLD_LOG")
        if log_path:
            Path(log_path).write_text(json.dumps(
                {"windows": windows, "rows": LEDGER}, indent=1))
