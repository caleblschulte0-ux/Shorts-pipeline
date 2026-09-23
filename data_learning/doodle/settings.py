"""Settings: the place a scene happens, at a time of day, in some weather.

A setting draws the STILL part of the world (sky, far land, ground) once per
scene into a cached image — nothing in it moves, because nothing in a
landscape should shiver. What does move is real: water flowing past, rain
falling, snow drifting, clouds crossing the sky slowly. Those are drawn every
frame by `ambient()`.

Night is not black. A sleep channel lives at dusk and night, and a frame the
showrunner measures as near-black is `empty_void`; so night is a deep
moonlit blue, lit warm wherever there is a fire (the light map in scene.py).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import cairo

from . import ink
from .ink import rgb, shade
from .props import pine, tree

W, H = 1920, 1080

TIMES = ("day", "dusk", "night", "dawn")
WEATHER = ("clear", "cloudy", "rain", "snow", "fog", "frost")

SKY = {
    "day": [(0, "#8ecae6"), (0.7, "#cfe8ef"), (1, "#f1f0dc")],
    "dawn": [(0, "#5f6f9e"), (0.55, "#e7a58f"), (1, "#f6d9a8")],
    "dusk": [(0, "#2e2f5e"), (0.5, "#8a5a82"), (0.8, "#e08a6a"), (1, "#f4c38a")],
    "night": [(0, "#101a33"), (0.6, "#1d2c52"), (1, "#2f4271")],
}
# ambient light multiplier per time (the light map's base colour)
AMBIENT = {"day": (1.0, 1.0, 1.0), "dawn": (0.92, 0.86, 0.86), "dusk": (0.74, 0.64, 0.74),
           "night": (0.40, 0.46, 0.70)}


@dataclass(frozen=True)
class Setting:
    ground: str                 # grass | snow | sand | rock | dirt | floor
    interior: bool = False
    water: str | None = None    # river | lake | sea
    eras: tuple = ("stone_age", "medieval", "ancient")
    horizon: float = 0.62       # fraction of H where the far land meets the sky


SETTINGS = {
    "grassland": Setting("grass"),
    "forest": Setting("grass"),
    "riverbank": Setting("grass", water="river"),
    "lakeshore": Setting("grass", water="lake"),
    "seashore": Setting("sand", water="sea"),
    "mountains": Setting("grass", horizon=0.66),
    "snowfield": Setting("snow"),
    "cave_mouth": Setting("rock", eras=("stone_age",)),
    "cave_inside": Setting("rock", interior=True, eras=("stone_age",)),
    "hut_inside": Setting("dirt", interior=True),
    "village": Setting("dirt", eras=("medieval",)),
    "field": Setting("dirt", eras=("medieval",)),
    "cottage_inside": Setting("floor", interior=True, eras=("medieval",)),
    "castle": Setting("grass", eras=("medieval",)),
    "forum": Setting("stone", eras=("ancient",)),                 # a town square: colonnade, town behind
    "villa_inside": Setting("floor", interior=True, eras=("ancient",)),
    "olive_grove": Setting("dirt", eras=("ancient",)),
}

GROUND = {"grass": "#8fb35f", "snow": "#eef2f5", "sand": "#e3cf9a", "rock": "#9b8f80",
          "dirt": "#b59a6d", "floor": "#8a6a48", "stone": "#cfc4b0"}
GROUND_Y = 0.80                  # fraction of H where people stand


def _sky(cr, time):
    g = cairo.LinearGradient(0, 0, 0, H * 0.8)
    for p, c in SKY[time]:
        g.add_color_stop_rgba(p, *rgb(c))
    cr.set_source(g)
    cr.paint()


def _sun_moon(cr, time, r):
    if time == "night":
        x, y = r.uniform(0.62, 0.85) * W, r.uniform(0.12, 0.2) * H
        ink.glow(cr, x, y, 180, (0.8, 0.85, 1.0), 0.25)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 46, 46, 28), rgb("#f3f0dc"), lw=0, amp=0)
        ink.dot(cr, x - 12, y - 8, 9, rgb("#dcd8c0"))
        ink.dot(cr, x + 14, y + 12, 6, rgb("#dcd8c0"))
    elif time in ("dusk", "dawn"):
        x, y = r.uniform(0.6, 0.8) * W, H * 0.56
        ink.glow(cr, x, y, 300, (1.0, 0.7, 0.45), 0.5)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 70, 70, 28), rgb("#ffd79a"), lw=0, amp=0)
    else:
        x, y = r.uniform(0.7, 0.88) * W, r.uniform(0.1, 0.18) * H
        ink.glow(cr, x, y, 160, (1.0, 0.95, 0.75), 0.4)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 52, 52, 28), rgb("#fff1b8"), lw=0, amp=0)


def _stars(cr, r, n=140):
    for _ in range(n):
        ink.dot(cr, r.uniform(0, W), r.uniform(0, H * 0.55), r.uniform(0.8, 2.2),
                (1, 1, 1, r.uniform(0.35, 0.9)))


def _hills(cr, r, y0, amp, color, seed, lw=4.0):
    pts = [(-50, H)]
    n = 9
    for i in range(n + 1):
        x = -50 + (W + 100) * i / n
        pts.append((x, y0 - amp * (0.5 + 0.5 * math.sin(i * 1.3 + seed)) * r.uniform(0.6, 1.0)))
    pts.append((W + 50, H))
    ink.fill_stroke(cr, pts, color, lw=lw, amp=3, seed=seed, closed=True)


def _mountains(cr, r, y0, color, seed, snowcaps=True):
    x = -100
    while x < W + 100:
        w = r.uniform(260, 420)
        h = r.uniform(180, 320)
        pts = [(x, y0), (x + w * 0.5, y0 - h), (x + w, y0)]
        ink.fill_stroke(cr, pts, color, lw=4, amp=2, seed=seed + int(x), shadow=shade(color, 0.85),
                        shadow_dir=(1, 0))
        if snowcaps:
            cx, cy = x + w * 0.5, y0 - h
            ink.fill_stroke(cr, [(cx, cy), (cx + w * 0.13, cy + h * 0.25), (cx + w * 0.03, cy + h * 0.2),
                                 (cx - w * 0.06, cy + h * 0.28), (cx - w * 0.13, cy + h * 0.24)],
                            rgb("#f4f6f8"), lw=3, amp=0.8, seed=seed + int(x) + 1)
        x += w * r.uniform(0.55, 0.8)


def _ground(cr, kind, gy, seed):
    c = rgb(GROUND[kind])
    pts = [(-40, gy - 40), (W * 0.3, gy - 55), (W * 0.62, gy - 38), (W + 40, gy - 50), (W + 40, H + 40),
           (-40, H + 40)]
    ink.fill_stroke(cr, pts, c, lw=4.5, amp=2.5, seed=seed, texture="grain", tex_alpha=0.12)
    r = random.Random(seed)
    tuft = shade(c, 0.8)
    if kind == "grass":
        for _ in range(40):
            x, y = r.uniform(0, W), r.uniform(gy - 20, H - 10)
            ink.line(cr, [(x, y), (x + 4, y - 14), (x + 8, y)], lw=2.8, ink=tuft, amp=0)
    elif kind in ("rock", "dirt", "sand"):
        for _ in range(22):
            x, y = r.uniform(0, W), r.uniform(gy, H - 10)
            ink.fill_stroke(cr, ink.ellipse_pts(x, y, r.uniform(6, 14), r.uniform(3, 6), 10), tuft, lw=0, amp=0)
    elif kind == "floor":
        for k in range(1, 6):
            y = gy - 30 + k * 50
            ink.line(cr, [(-10, y), (W + 10, y + r.uniform(-4, 4))], lw=3, ink=shade(c, 0.7), amp=1, seed=k)
    elif kind == "stone":
        # paving: a loose grid of flags
        for k in range(1, 6):
            y = gy - 40 + k * 52
            ink.line(cr, [(-10, y), (W + 10, y + r.uniform(-3, 3))], lw=2.5, ink=shade(c, 0.8), amp=0.8, seed=k)
            for j in range(9):
                x = j * 240 + (k % 2) * 120 + r.uniform(-8, 8)
                ink.line(cr, [(x, y), (x + r.uniform(-6, 6), y + 52)], lw=2.5, ink=shade(c, 0.8), amp=0.8, seed=k * 9 + j)


def _frost(cr, gy, seed):
    """A hard frost: the ground goes pale and every tuft carries a white
    edge. Still; the fire and the people carry the motion."""
    r = random.Random(seed)
    cr.set_source_rgba(0.92, 0.95, 1.0, 0.22)
    cr.rectangle(0, gy - 60, W, H - gy + 60)
    cr.fill()
    for _ in range(90):
        x, y = r.uniform(0, W), r.uniform(gy - 30, H - 6)
        w = r.uniform(8, 26)
        ink.line(cr, [(x - w, y), (x + w, y - r.uniform(1, 3))], lw=r.uniform(2, 3.5),
                 ink=(0.93, 0.96, 1.0), amp=0)


def _town(cr, r, y0, seed):
    """A row of Mediterranean houses on the skyline: cream walls, low
    terracotta roofs, a few dark windows."""
    for k in range(6):
        x = -80 + k * 380 + r.uniform(-50, 50)
        w = r.uniform(150, 240)
        h = r.uniform(110, 190)
        wall = ink.mix(rgb("#e6dcc4"), rgb("#d9c7a3"), r.random())
        ink.fill_stroke(cr, [(x - w / 2, y0), (x - w / 2, y0 - h), (x + w / 2, y0 - h), (x + w / 2, y0)], wall,
                        lw=4, amp=1, seed=seed + k, shadow=shade(wall), shadow_dir=(1, 0))
        roof = rgb("#b8623f")
        ink.fill_stroke(cr, [(x - w / 2 - 14, y0 - h), (x, y0 - h - r.uniform(30, 55)), (x + w / 2 + 14, y0 - h)],
                        roof, lw=4, amp=1, seed=seed + k + 7, shadow=shade(roof), shadow_dir=(1, 0))
        for j in range(int(w // 70)):
            wx = x - w / 2 + 35 + j * 70
            ink.fill_stroke(cr, [(wx - 12, y0 - h * 0.55), (wx + 12, y0 - h * 0.55), (wx + 12, y0 - h * 0.25),
                                 (wx - 12, y0 - h * 0.25)], rgb("#3d3a44"), lw=3, amp=0)


def _colonnade(cr, r, y0, seed):
    """A line of columns across the square, with the beam they carry."""
    from .props import column
    xs = [180 + k * 390 + r.uniform(-20, 20) for k in range(5)]
    ink.fill_stroke(cr, [(xs[0] - 60, y0 - 215), (xs[-1] + 60, y0 - 215), (xs[-1] + 60, y0 - 190), (xs[0] - 60, y0 - 190)],
                    rgb("#e3dbc9"), lw=4, amp=0.8, seed=seed, shadow=rgb("#cfc5b1"), shadow_dir=(0, 1))
    for k, x in enumerate(xs):
        column(cr, x, y0, 0.8, 0.0, seed + k)


def _interior(cr, name, seed, r):
    if name == "cave_inside":
        cr.set_source_rgba(*rgb("#4a4038"))
        cr.paint()
        for k in range(7):
            x = -100 + k * 330 + r.uniform(-60, 60)
            ink.fill_stroke(cr, ink.blob_pts(x, H * 0.35, 260, 330, seed + k, 0.12, 16),
                            ink.mix(rgb("#5e5247"), rgb("#6d6054"), r.random()), lw=5, amp=2, seed=seed + k,
                            shadow=rgb("#4b4139"), shadow_dir=(1, 0.5))
        # a darker passage leading further in, high on the wall so it sits
        # behind the scene, never across a face
        ink.fill_stroke(cr, ink.blob_pts(W * r.uniform(0.25, 0.75), H * 0.14, 190, 90, seed + 99, 0.1, 18),
                        rgb("#1d1a1c"), lw=5, amp=2, seed=seed + 99)
    elif name == "hut_inside":
        cr.set_source_rgba(*rgb("#6e5236"))
        cr.paint()
        for k in range(24):
            x = k * 90 + r.uniform(-10, 10)
            ink.line(cr, [(x, -10), (W / 2 + (x - W / 2) * 0.35, H * 0.55)], lw=6, ink=rgb("#5a4129"), amp=1, seed=k)
    elif name == "villa_inside":
        wall = rgb("#d9b9a0")
        cr.set_source_rgba(*wall)
        cr.paint()
        # a painted dado in deep red with a pale band, the way villa walls were
        ink.fill_stroke(cr, [(-10, H * 0.5), (W + 10, H * 0.5), (W + 10, H * 0.8), (-10, H * 0.8)], rgb("#8e3b34"),
                        lw=0, amp=0)
        ink.line(cr, [(-10, H * 0.5), (W + 10, H * 0.5)], lw=10, ink=rgb("#e8d9b8"), amp=0.6, seed=seed)
        ink.line(cr, [(-10, H * 0.5 + 24), (W + 10, H * 0.5 + 24)], lw=3, ink=rgb("#e8d9b8"), amp=0.6, seed=seed + 1)
        # a doorway to a sunlit courtyard
        dx = r.choice([380, 1000, 1500])
        ink.fill_stroke(cr, [(dx - 120, H * 0.8), (dx - 120, 200), (dx + 120, 200), (dx + 120, H * 0.8)],
                        rgb("#c9b08a"), lw=8, amp=0.8, seed=seed + 2)
        ink.fill_stroke(cr, [(dx - 100, H * 0.8), (dx - 100, 220), (dx + 100, 220), (dx + 100, H * 0.8)],
                        rgb("#a9c4e0"), lw=0, amp=0)
        ink.fill_stroke(cr, [(dx - 100, H * 0.8), (dx - 100, H * 0.62), (dx + 100, H * 0.62), (dx + 100, H * 0.8)],
                        rgb("#8fb35f"), lw=0, amp=0)
        ink.fill_stroke(cr, ink.blob_pts(dx + 30, H * 0.56, 50, 34, seed + 5, 0.12, 12), rgb("#8fa27a"), lw=3,
                        amp=1, seed=seed + 5)
        ink.line(cr, [(dx + 30, H * 0.62), (dx + 30, H * 0.58)], lw=6, ink=rgb("#6f5a44"), amp=0)
    elif name == "cottage_inside":
        wall = rgb("#d8c39a")
        cr.set_source_rgba(*wall)
        cr.paint()
        for x in (140, 700, 1260, 1800):
            ink.line(cr, [(x, -10), (x, H * 0.8)], lw=20, ink=rgb("#6d4b2d"), amp=0.8, seed=x)
        ink.line(cr, [(-10, 150), (W + 10, 150)], lw=22, ink=rgb("#6d4b2d"), amp=0.8, seed=7)
        # a small window showing the sky outside
        wx = r.choice([420, 980, 1500])
        ink.fill_stroke(cr, [(wx - 90, 280), (wx + 90, 280), (wx + 90, 470), (wx - 90, 470)], rgb("#27365e"),
                        lw=8, amp=0.8, seed=seed)
        ink.line(cr, [(wx, 280), (wx, 470)], lw=7, ink=rgb("#6d4b2d"), amp=0)
        ink.line(cr, [(wx - 90, 375), (wx + 90, 375)], lw=7, ink=rgb("#6d4b2d"), amp=0)


def _water(cr, kind, gy, seed):
    """The still body of the water; its flow is drawn in ambient()."""
    top = gy - 120 if kind == "river" else gy - 170
    bot = gy - 40 if kind == "river" else gy - 60
    c = rgb("#5b9bc0")
    pts = [(-40, top), (W * 0.4, top + 10), (W + 40, top - 6), (W + 40, bot), (W * 0.5, bot + 12), (-40, bot)]
    if kind == "sea":
        pts = [(-40, H * 0.58), (W + 40, H * 0.58), (W + 40, bot), (W * 0.5, bot + 15), (-40, bot)]
    ink.fill_stroke(cr, pts, c, lw=4.5, amp=2, seed=seed, shadow=shade(c, 0.88), shadow_dir=(0, -1))
    return top, bot


def draw_still(cr, name: str, time: str, weather: str, seed: int) -> dict:
    """Paint the still world for a scene. Returns layout facts the scene needs."""
    st = SETTINGS[name]
    r = random.Random(seed)
    gy = H * GROUND_Y
    facts = {"ground_y": gy, "water": None}
    if st.interior:
        _interior(cr, name, seed, r)
        _ground(cr, st.ground, gy, seed + 1)
        return facts
    _sky(cr, time if weather not in ("rain",) else ("night" if time == "night" else "dusk"))
    if time == "night" and weather in ("clear", "snow", "frost"):
        _stars(cr, r)
    if weather in ("clear", "cloudy", "snow", "frost") or time == "night":
        _sun_moon(cr, time, r)
    far = {"day": rgb("#9fb7a8"), "dawn": rgb("#9d8fa0"), "dusk": rgb("#7a6485"), "night": rgb("#34466b")}[time]
    # the cave mouth is the film's most-used picture: half the time it has
    # the range behind it, half the time only hills, so it is not one layout
    if name in ("mountains", "snowfield", "lakeshore") or (name == "cave_mouth" and r.random() < 0.5):
        _mountains(cr, r, H * st.horizon, far, seed, snowcaps=True)
    _hills(cr, r, H * st.horizon + 30, 60, ink.mix(far, rgb(GROUND[st.ground]), 0.45), seed + 3)
    if name == "castle":
        _castle(cr, W * r.uniform(0.3, 0.7), H * st.horizon + 60, seed)
    if name == "forum":
        _town(cr, r, H * st.horizon + 40, seed)
        _colonnade(cr, r, H * st.horizon + 150, seed)
    if name == "olive_grove":
        from .props import olive
        for k in range(6):
            olive(cr, k * 360 + r.uniform(-70, 70), H * 0.72, 0.7, 0.0, seed + k)
    if name in ("forest",):
        for k in range(9):
            x = k * 230 + r.uniform(-40, 40)
            (pine if k % 2 else tree)(cr, x, H * 0.72, 0.75, 0.0, seed + k)
    if name == "snowfield":
        for k in range(6):
            pine(cr, k * 360 + r.uniform(-60, 60), H * 0.71, 0.65, 0.0, seed + k, snow=True)
    if name == "village":
        from .props import cottage_base
        for k in range(3):
            cottage_base(cr, 250 + k * 700 + r.uniform(-60, 60), H * 0.69, 0.55, 0.0, seed + k)
    if name == "field":
        c = rgb("#a58c5e")
        for k in range(9):
            y = H * 0.66 + k * 22
            ink.line(cr, [(-10, y), (W + 10, y + 6)], lw=3, ink=shade(c, 0.8), amp=1.5, seed=k)
    _ground(cr, st.ground, gy, seed + 1)
    if weather == "frost":
        _frost(cr, gy, seed + 2)
    if st.water:
        top, bot = _water(cr, st.water, gy, seed + 2)
        facts["water"] = (st.water, top, bot)
    if name == "cave_mouth":
        _cave_mouth(cr, r, gy, seed)
    return facts


def _cave_mouth(cr, r, gy, seed):
    """A hill of rock on one side of the frame with an arched dark opening."""
    rockc = rgb("#857a6d")
    side = r.choice([-1, 1])
    x0 = 0 if side < 0 else W
    far = x0 - side * W * 0.62
    pts = [(x0 + side * 40, gy + 40), (x0 + side * 40, H * 0.05), (x0 - side * W * 0.18, H * 0.02),
           (x0 - side * W * 0.38, H * 0.16), (far + side * 60, H * 0.36), (far, gy - 20), (far - side * 30, gy + 30)]
    ink.fill_stroke(cr, pts, rockc, lw=6, amp=4, seed=seed + 7, shadow=shade(rockc, 0.84),
                    shadow_dir=(side, 0.4), texture="grain", tex_alpha=0.22)
    # a few cracks and ledges so it reads as rock, not a wall
    for k in range(5):
        cx = x0 - side * r.uniform(W * 0.05, W * 0.5)
        cy = r.uniform(H * 0.1, H * 0.45)
        ink.line(cr, [(cx, cy), (cx - side * r.uniform(30, 80), cy + r.uniform(20, 50)),
                      (cx - side * r.uniform(60, 120), cy + r.uniform(50, 90))], lw=4,
                 ink=shade(rockc, 0.6), amp=1.5, seed=seed + k)
    # the opening: an arch standing on the ground
    mx = x0 - side * W * 0.3
    ow, oh = W * 0.15, H * 0.4
    arch = [(mx - ow, gy + 5)]
    for i in range(17):
        a = math.pi + math.pi * i / 16
        arch.append((mx + ow * math.cos(a), gy - oh * 0.35 + oh * 0.65 * math.sin(a)))
    arch.append((mx + ow, gy + 5))
    ink.fill_stroke(cr, arch, rgb("#241e1e"), lw=6, amp=3, seed=seed + 8)
    g = cairo.RadialGradient(mx, gy - oh * 0.2, 10, mx, gy - oh * 0.2, ow * 1.1)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.6)
    g.add_color_stop_rgba(1, 0, 0, 0, 0)
    cr.save()
    ink.smooth(cr, arch, True)
    cr.clip()
    cr.set_source(g)
    cr.paint()
    cr.restore()


def _castle(cr, x, y, seed):
    c = rgb("#a8a29a")
    ink.fill_stroke(cr, [(x - 260, y), (x - 260, y - 180), (x + 260, y - 180), (x + 260, y)], c, lw=5, amp=1.5,
                    seed=seed, shadow=shade(c), shadow_dir=(1, 0), texture="grain", tex_alpha=0.2)
    for dx in (-260, 260, -60):
        h = 300 if dx else 360
        ink.fill_stroke(cr, [(x + dx - 55, y), (x + dx - 55, y - h), (x + dx + 55, y - h), (x + dx + 55, y)], c,
                        lw=5, amp=1.2, seed=seed + dx, shadow=shade(c), shadow_dir=(1, 0))
        for k in range(3):
            bx = x + dx - 55 + k * 40
            ink.fill_stroke(cr, [(bx, y - h), (bx, y - h - 26), (bx + 24, y - h - 26), (bx + 24, y - h)], c, lw=4,
                            amp=0)
        ink.fill_stroke(cr, [(x + dx - 10, y - h + 60), (x + dx + 10, y - h + 60), (x + dx + 10, y - h + 110),
                             (x + dx - 10, y - h + 110)], rgb("#f5c563"), lw=3, amp=0)
    ink.line(cr, [(x - 60, y - 360), (x - 60, y - 450)], lw=4, amp=0)


# ------------------------------------------------------------------ ambient
def ambient(cr, name: str, time: str, weather: str, facts: dict, t: float, seed: int):
    """What moves in the world itself: water, rain, snow, clouds, fog."""
    r = random.Random(seed * 3 + 1)
    if weather == "cloudy" or (weather == "clear" and not SETTINGS[name].interior and time != "night"):
        n = 5 if weather == "cloudy" else 3
        for k in range(n):
            speed = 6 + 4 * (k % 3)
            x = (r.uniform(0, W + 600) + t * speed) % (W + 600) - 300
            y = r.uniform(0.07, 0.3) * H
            c = (1, 1, 1, 0.85) if time == "day" else (0.8, 0.72, 0.8, 0.75)
            ink.fill_stroke(cr, ink.blob_pts(x, y, r.uniform(110, 170), r.uniform(36, 55), seed + k, 0.18, 16), c,
                            lw=3.5, amp=1, seed=seed + k, ink=(0.3, 0.3, 0.35, 0.35))
    w = facts.get("water")
    if w:
        kind, top, bot = w
        _flow(cr, kind, top, bot, t, seed, time)
    if weather == "rain":
        _rain(cr, t, seed)
    elif weather == "snow":
        _snow(cr, t, seed)
    elif weather == "fog":
        for k in range(3):
            x = (t * 14 * (k + 1) + k * 700) % (W + 1200) - 600
            ink.glow(cr, x, H * (0.55 + 0.08 * k), 520, (0.9, 0.92, 0.95), 0.35)


def _flow(cr, kind, top, bot, t, seed, time):
    """Water that runs: rows of light ripple dashes carried along by the
    current (a river) or rolling in (lake/sea), each dash a clear mark."""
    r = random.Random(seed + 11)
    hl = (1, 1, 1, 0.75) if time != "night" else (0.8, 0.88, 1.0, 0.6)
    rows = 6
    speed = 55 if kind == "river" else 22
    for i in range(rows):
        y = top + (bot - top) * (i + 0.6) / rows
        spacing = r.uniform(180, 260)
        off = r.uniform(0, spacing)
        L = r.uniform(50, 90) * (0.6 + 0.4 * i / rows)
        x = -spacing + (off + t * speed * (0.7 + 0.3 * i / rows)) % spacing
        while x < W + spacing:
            cr.move_to(x, y)
            cr.curve_to(x + L * 0.3, y - 5, x + L * 0.7, y + 5, x + L, y)
            cr.set_line_width(7)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(*hl)
            cr.stroke()
            x += spacing
    if kind in ("sea", "lake"):
        # the wash sliding up the shore and back
        k = (math.sin(t * 2 * math.pi / 6.0 + seed) + 1) / 2
        y = bot + 4 + k * 26
        ink.line(cr, [(-20, y), (W * 0.3, y + 8), (W * 0.65, y - 4), (W + 20, y + 6)], lw=9,
                 ink=(1, 1, 1, 0.85 if time != "night" else 0.55), amp=3, seed=seed)


def glints(cr, facts: dict, time: str, t: float, seed: int):
    """Sun or moon catching the ripples, each glint winking on and off the
    way light on moving water does. They are LIGHT, so a scene draws them
    after its light pass — at night the moon's glints are not darkened."""
    w = facts.get("water")
    if not w:
        return
    kind, top, bot = w
    r = random.Random(seed + 13)
    gl = (1, 0.97, 0.85) if time in ("day", "dawn", "dusk") else (0.88, 0.94, 1.0)
    for k in range(110 if kind == "sea" else 70):
        gx = r.uniform(0, W)
        gy = r.uniform(top + 8, bot - 8)
        w_ = r.uniform(16, 34)
        v = ink.vnoise(t, 5.0 + (k % 5), seed * 31 + k)
        if v > 0.1:
            a = min(1.0, (v - 0.1) * 1.6)
            ink.fill_stroke(cr, ink.ellipse_pts(gx, gy, w_, w_ * 0.24, 10), (gl[0], gl[1], gl[2], a),
                            lw=0, amp=0)


def _rain(cr, t, seed):
    r = random.Random(seed + 21)
    cr.set_line_width(3.4)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_source_rgba(0.86, 0.9, 1.0, 0.7)
    for _ in range(700):
        x0, y0 = r.uniform(-100, W), r.uniform(0, H)
        v = r.uniform(900, 1300)
        y = (y0 + t * v) % (H + 80) - 40
        x = x0 + (y - y0) * 0.12
        cr.move_to(x, y)
        cr.line_to(x + 6, y + 44)
    cr.stroke()


def _snow(cr, t, seed):
    r = random.Random(seed + 31)
    for _ in range(170):
        x0, y0 = r.uniform(0, W), r.uniform(0, H)
        depth = r.uniform(0.4, 1.0)
        v = 60 + 90 * depth
        y = (y0 + t * v) % (H + 40) - 20
        x = x0 + math.sin(t * 0.8 + y0) * 18 * depth
        ink.dot(cr, x, y, 2.5 + 5.5 * depth, (1, 1, 1, 0.55 + 0.4 * depth))
