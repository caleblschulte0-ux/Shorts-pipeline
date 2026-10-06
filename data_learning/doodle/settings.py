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
    eras: tuple = ("stone_age", "medieval", "ancient", "victorian", "egypt", "early_modern")
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
    "hut_inside": Setting("dirt", interior=True, eras=("stone_age", "medieval")),
    "village": Setting("dirt", eras=("medieval",)),
    "field": Setting("dirt", eras=("medieval",)),
    "cottage_inside": Setting("floor", interior=True, eras=("medieval", "victorian", "early_modern")),
    "castle": Setting("grass", eras=("medieval",)),
    "forum": Setting("stone", eras=("ancient",)),                 # a town square: colonnade, town behind
    "villa_inside": Setting("floor", interior=True, eras=("ancient",)),
    "house_inside": Setting("floor", interior=True, eras=("ancient",)),     # a plain whitewashed home
    "olive_grove": Setting("dirt", eras=("ancient",)),
    "street": Setting("cobbles", eras=("victorian",)),            # a gas-lit terrace street
    "parlour_inside": Setting("boards", interior=True, eras=("victorian",)),
    "farmyard": Setting("dirt", eras=("medieval", "victorian", "early_modern")),
    "nile_bank": Setting("sand", water="river", eras=("egypt",)),   # palms and reeds along the river
    "desert": Setting("sand", eras=("egypt",), horizon=0.64),       # dunes, the pyramids on the skyline
    "mudbrick_inside": Setting("dirt", interior=True, eras=("egypt",)),
    "harbour": Setting("stone", water="sea", eras=("early_modern",)),    # a quay, a ship at anchor
    "tavern_inside": Setting("boards", interior=True, eras=("early_modern",)),
    "market_square": Setting("cobbles", eras=("medieval", "early_modern")),
    # a brook across open ground, and a spring below a town wall: the Greek
    # film's judge, twice, on a stream and a spring both drawn as the open
    # sea: "harbor, spring and stream all use the same seashore"
    "stream": Setting("grass", water="stream"),
    "spring": Setting("stone", water="spring", eras=("ancient", "medieval", "egypt", "early_modern")),
}

GROUND = {"grass": "#8fb35f", "snow": "#eef2f5", "sand": "#e3cf9a", "rock": "#9b8f80",
          "dirt": "#b59a6d", "floor": "#8a6a48", "stone": "#cfc4b0", "cobbles": "#8c8781",
          "boards": "#9a6f4a"}
GROUND_Y = 0.80                  # fraction of H where people stand


def _sky(cr, time):
    g = cairo.LinearGradient(0, 0, 0, H * 0.8)
    for p, c in SKY[time]:
        g.add_color_stop_rgba(p, *rgb(c))
    cr.set_source(g)
    cr.paint()


def _open_column(lo: float, hi: float, r, clear) -> float:
    """An x in [lo, hi], by seed, out of every span in `clear` where it can
    be: the sun's path on the water is the one thing on an open shore that
    really moves, and placed behind whoever stands on the sand it is
    clipped away with the glints (run 98: a close shot of the shore at
    dawn read 96% held with the path behind the woman and the rock)."""
    x = r.uniform(lo, hi)
    if not clear:
        return x
    # its own range first; when that is all covered, anywhere across the sky
    for lo_, hi_ in ((lo, hi), (0.12 * W, 0.88 * W)):
        free = [(lo_, hi_)]
        for c0, c1 in clear:
            nxt = []
            for a, b in free:
                if c1 <= a or c0 >= b:
                    nxt.append((a, b))
                else:
                    if c0 - a >= 160:
                        nxt.append((a, c0))
                    if b - c1 >= 160:
                        nxt.append((c1, b))
            free = nxt
        if free:
            a, b = max(free, key=lambda ab: ab[1] - ab[0])
            return r.uniform(a + 50, b - 50) if b - a > 100 else (a + b) / 2
    return x


def _sun_moon(cr, time, r, clear=()):
    """The sun or the moon; returns where it is, so the water can carry
    its path. `clear` is the x-spans the path must not sit behind."""
    if time == "night":
        x, y = _open_column(0.62 * W, 0.85 * W, r, clear), r.uniform(0.12, 0.2) * H
        ink.glow(cr, x, y, 180, (0.8, 0.85, 1.0), 0.25)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 46, 46, 28), rgb("#f3f0dc"), lw=0, amp=0)
        ink.dot(cr, x - 12, y - 8, 9, rgb("#dcd8c0"))
        ink.dot(cr, x + 14, y + 12, 6, rgb("#dcd8c0"))
    elif time in ("dusk", "dawn"):
        x, y = _open_column(0.6 * W, 0.8 * W, r, clear), H * 0.56
        ink.glow(cr, x, y, 300, (1.0, 0.7, 0.45), 0.5)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 70, 70, 28), rgb("#ffd79a"), lw=0, amp=0)
    else:
        x, y = _open_column(0.7 * W, 0.88 * W, r, clear), r.uniform(0.1, 0.18) * H
        ink.glow(cr, x, y, 160, (1.0, 0.95, 0.75), 0.4)
        ink.fill_stroke(cr, ink.ellipse_pts(x, y, 52, 52, 28), rgb("#fff1b8"), lw=0, amp=0)
    return x, y


def _stars(cr, r, n=140):
    for _ in range(n):
        ink.dot(cr, r.uniform(0, W), r.uniform(0, H * 0.55), r.uniform(0.8, 2.2),
                (1, 1, 1, r.uniform(0.35, 0.9)))


def _milky_way(cr, r):
    """A band of dense faint stars across the sky, the way a clear night
    away from any town really looks — and the picture the seventh film's
    judge asked for under a sky chapter. Soft haze first, then the stars."""
    x0, y0 = r.uniform(-200, 200), r.uniform(H * 0.05, H * 0.35)
    x1, y1 = W + r.uniform(-200, 200), r.uniform(H * 0.1, H * 0.45)
    if r.random() < 0.5:
        y0, y1 = y1, y0
    # soft haze: many faint glows along the band, never a hard-edged bar
    # (the first cut was three stroked lines and read as a grey stripe)
    for _ in range(90):
        u = r.random()
        gx = x0 + (x1 - x0) * u
        gy_ = y0 + (y1 - y0) * u + r.gauss(0, 40)
        ink.glow(cr, gx, gy_, r.uniform(90, 170), (0.85, 0.88, 1.0), r.uniform(0.03, 0.06))
    for _ in range(420):
        u = r.random()
        x = x0 + (x1 - x0) * u
        y = y0 + (y1 - y0) * u + r.gauss(0, 55)
        ink.dot(cr, x, y, r.uniform(0.5, 1.4), (1, 1, 1, r.uniform(0.25, 0.75)))


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
    elif kind == "cobbles":
        for k in range(1, 7):
            y = gy - 40 + k * 46
            for j in range(18):
                x = j * 112 + (k % 2) * 56 + r.uniform(-6, 6)
                ink.fill_stroke(cr, ink.ellipse_pts(x, y, 44, 16, 10), shade(c, 0.94 if (j + k) % 3 else 0.86),
                                lw=2.5, amp=0.6, seed=k * 31 + j)
    elif kind == "boards":
        for k in range(1, 7):
            y = gy - 30 + k * 44
            ink.line(cr, [(-10, y), (W + 10, y + r.uniform(-2, 2))], lw=3, ink=shade(c, 0.75), amp=0.6, seed=k)
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


def _town(cr, r, y0, seed, facts=None):
    """A row of Mediterranean houses on the skyline: cream walls, low
    terracotta roofs, a few dark windows. Records where the windows and the
    roof ridges are, so the evening can come to them (`ambient`)."""
    town = (facts or {}).setdefault("town", {"windows": [], "roofs": []})
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
        town["roofs"].append((x + r.uniform(-w / 4, w / 4), y0 - h - 20))
        for j in range(int(w // 70)):
            wx = x - w / 2 + 35 + j * 70
            ink.fill_stroke(cr, [(wx - 12, y0 - h * 0.55), (wx + 12, y0 - h * 0.55), (wx + 12, y0 - h * 0.25),
                                 (wx - 12, y0 - h * 0.25)], rgb("#3d3a44"), lw=3, amp=0)
            town["windows"].append((wx, y0 - h * 0.4))


STOA_WALL = rgb("#cdc2ab")


def _colonnade(cr, r, y0, seed, wall: bool = False, facts: dict | None = None):
    """A line of columns across the square, with the beam they carry. Close
    in, the stoa's back wall stands behind the columns: with the town's
    roofs showing between them the beam read as a parapet and the judge saw
    "a figure in a dress on a rooftop" (run 97); a wall is the stone the
    words put the fire against."""
    from .props import column
    xs = [180 + k * 390 + r.uniform(-20, 20) for k in range(5)]
    if wall:
        if facts is not None and facts.get("town"):
            facts["town"]["hidden_below"] = y0 - 195     # the windows behind the wall do not light up on it
        ink.fill_stroke(cr, [(-40, y0 - 195), (W + 40, y0 - 195), (W + 40, y0 + 6), (-40, y0 + 6)],
                        STOA_WALL, lw=4, amp=1.0, seed=seed + 3, shadow=shade(STOA_WALL, 0.92), shadow_dir=(0, 1))
        for k in range(1, 5):
            yy = y0 - 195 + k * 48
            ink.line(cr, [(-40, yy), (W + 40, yy)], lw=2, ink=shade(STOA_WALL, 0.85), amp=1.2, seed=seed + 20 + k)
    ink.fill_stroke(cr, [(xs[0] - 60, y0 - 215), (xs[-1] + 60, y0 - 215), (xs[-1] + 60, y0 - 190), (xs[0] - 60, y0 - 190)],
                    rgb("#e3dbc9"), lw=4, amp=0.8, seed=seed, shadow=rgb("#cfc5b1"), shadow_dir=(0, 1))
    for k, x in enumerate(xs):
        column(cr, x, y0, 0.8, 0.0, seed + k)


def _dunes(cr, r, y0, seed):
    """Sand dunes on the skyline, two ridges."""
    for k, (c, amp) in enumerate(((rgb("#d9c08a"), 50), (rgb("#e3cf9a"), 34))):
        pts = [(-40, y0 + 80 + k * 40)]
        for i in range(9):
            pts.append((i * 250 + r.uniform(-40, 40), y0 + k * 40 - r.uniform(0, amp)))
        pts += [(W + 40, y0 + 60 + k * 40), (W + 40, y0 + 200), (-40, y0 + 200)]
        ink.fill_stroke(cr, pts, c, lw=4, amp=2, seed=seed + k, shadow=shade(c, 0.9), shadow_dir=(1, 0.3))


def _outside(time: str):
    """What shows through a door or a window: the sky's horizon colour and
    the ground under it, at THIS time of day (run #18's judge: "the
    doorway shows a bright daytime hill in night/candle scenes")."""
    sky = rgb(SKY[time][-1][1])
    k = {"day": 1.0, "dawn": 0.8, "dusk": 0.45, "night": 0.18}[time]
    ground = ink.mix(rgb("#8fb35f"), rgb("#101a33"), 1 - k)
    tree = ink.mix(rgb("#8fa27a"), rgb("#101a33"), 1 - k)
    return sky, ground, tree


def _interior(cr, name, seed, r, time: str = "night"):
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
        # a Greek or Roman room: plastered walls with a painted dado, a
        # doorway onto the courtyard at this hour, a niche with a jar. Drawn
        # with straight edges (ink.box) — four bare corners were smoothed
        # into a curved "horizon" and an arch with a blob in it, and the
        # operator called the film "3/10 AI slop"
        wall = rgb(("#e2cdb0", "#d9c6a4", "#e8d6bc")[seed % 3])      # not one room every time (run 95)
        cr.set_source_rgba(*wall)
        cr.paint()
        top, bot = H * 0.5, H * GROUND_Y
        ink.fill_stroke(cr, ink.box(-20, top, W + 20, bot + 10), rgb("#8e3b34"), lw=0, amp=0)
        ink.line(cr, [(-10, top), (W + 10, top)], lw=12, ink=rgb("#efe2c6"), amp=0.4, seed=seed)
        ink.line(cr, [(-10, top + 30), (W + 10, top + 30)], lw=4, ink=rgb("#efe2c6"), amp=0.4, seed=seed + 1)
        # a meander band along the top of the wall
        for k in range(0, W + 60, 60):
            ink.line(cr, [(k, 150), (k, 120), (k + 40, 120), (k + 40, 140), (k + 20, 140)], lw=4,
                     ink=rgb("#9a5a3c"), amp=0)
        ink.line(cr, [(-10, 106), (W + 10, 106)], lw=5, ink=rgb("#9a5a3c"), amp=0.3, seed=seed + 2)
        ink.line(cr, [(-10, 164), (W + 10, 164)], lw=5, ink=rgb("#9a5a3c"), amp=0.3, seed=seed + 3)
        sky, ground, tree = _outside(time)
        dx = villa_doorway(r)
        # the doorway: a stone frame, a lintel, the courtyard beyond
        ink.fill_stroke(cr, ink.box(dx - 150, 250, dx + 150, bot), rgb("#cdb894"), lw=7, amp=0.6, seed=seed + 4)
        ink.fill_stroke(cr, ink.box(dx - 115, 285, dx + 115, bot), sky, lw=5, amp=0, seed=seed + 5)
        ink.fill_stroke(cr, ink.box(dx - 115, bot - 120, dx + 115, bot), ground, lw=0, amp=0)
        # a courtyard column and a few stars through the door
        ink.fill_stroke(cr, ink.box(dx + 30, 330, dx + 62, bot - 40), ink.mix(rgb("#d8d0c0"), sky, 0.55), lw=4,
                        amp=0, seed=seed + 6)
        if time in ("night", "dusk"):
            for k in range(6):
                ink.dot(cr, dx - 95 + r.uniform(0, 180), 300 + r.uniform(0, 140), 2.2, (1, 1, 0.9, 0.8))
        ink.fill_stroke(cr, ink.box(dx - 170, 226, dx + 170, 262), rgb("#bfa77f"), lw=6, amp=0.4, seed=seed + 7)
        # a wall niche holding a jar, on the other side of the room
        nx = W - dx + r.uniform(-120, 120)
        ink.fill_stroke(cr, ink.box(nx - 90, 300, nx + 90, 470), shade(wall, 0.72), lw=6, amp=0.5, seed=seed + 8)
        ink.fill_stroke(cr, [(nx - 34, 466), (nx - 50, 420), (nx - 30, 360), (nx - 16, 336), (nx + 16, 336),
                             (nx + 30, 360), (nx + 50, 420), (nx + 34, 466)], rgb("#b5643a"), lw=5, amp=0.4,
                        seed=seed + 9, shadow=rgb("#8a4a2a"), shadow_dir=(1, 0))
        ink.line(cr, [(nx - 40, 400), (nx + 40, 400)], lw=4, ink=rgb("#2a1c16"), amp=0)
    elif name == "house_inside":
        # a plain Greek or Roman house: whitewash, ceiling beams, a small
        # high window with a shutter, a shelf of pots and a loom
        wall = rgb(("#ece3d0", "#e4d8bf", "#f0e9d8")[seed % 3])      # not one room every time (run 95)
        cr.set_source_rgba(*wall)
        cr.paint()
        bot = H * GROUND_Y
        for k in range(5):
            y = 40 + k * 4
            ink.line(cr, [(-10, y), (W + 10, y)], lw=2, ink=shade(wall, 0.95), amp=0.4, seed=seed + k)
        for x in range(-40, W + 80, 320):
            ink.fill_stroke(cr, ink.box(x, -10, x + 46, 70), rgb("#7a5a3c"), lw=5, amp=0.5, seed=seed + x)
        ink.fill_stroke(cr, ink.box(-20, 60, W + 20, 92), rgb("#6a4c32"), lw=5, amp=0.5, seed=seed + 1)
        wx = r.choice([420, 1500]) + r.uniform(-60, 60)
        ink.fill_stroke(cr, ink.box(wx - 80, 200, wx + 80, 330), _outside(time)[0], lw=8, amp=0.6, seed=seed + 2)
        ink.fill_stroke(cr, ink.box(wx + 80, 200, wx + 150, 330), rgb("#7a5a3c"), lw=6, amp=0.5, seed=seed + 3)
        # a shelf with pots on the far wall
        sx = W - wx + r.uniform(-100, 100)
        ink.fill_stroke(cr, ink.box(sx - 200, 380, sx + 200, 400), rgb("#6a4c32"), lw=5, amp=0.4, seed=seed + 4)
        for k, (w_, h_, c) in enumerate(((40, 70, "#b5643a"), (30, 50, "#c9a36a"), (46, 80, "#9a5a3c"),
                                         (28, 44, "#d8c39a"))):
            px = sx - 150 + k * 100
            ink.fill_stroke(cr, [(px - w_ * 0.6, 380), (px - w_, 380 - h_ * 0.6), (px - w_ * 0.5, 380 - h_),
                                 (px + w_ * 0.5, 380 - h_), (px + w_, 380 - h_ * 0.6), (px + w_ * 0.6, 380)],
                            rgb(c), lw=4, amp=0.4, seed=seed + 10 + k, shadow=shade(rgb(c)), shadow_dir=(1, 0))
        _wall_hanging(cr, house_hanging_x(seed), seed)
        # a skirting of beaten earth colour where the wall meets the floor
        ink.fill_stroke(cr, ink.box(-20, bot - 40, W + 20, bot + 10), rgb("#cdb48e"), lw=0, amp=0)
    elif name == "mudbrick_inside":
        wall = rgb("#e4d3ac")
        cr.set_source_rgba(*wall)
        cr.paint()
        # whitewashed walls, a band of painted lotus, a high small window
        ink.line(cr, [(-10, 240), (W + 10, 240)], lw=6, ink=rgb("#2f8f8f"), amp=0.6, seed=seed)
        for k in range(0, W, 160):
            ink.fill_stroke(cr, [(k + 60, 236), (k + 80, 196), (k + 100, 236)], rgb("#c99a2e"), lw=3, amp=0)
        wx = r.choice([420, 1000, 1500])
        ink.fill_stroke(cr, [(wx - 60, 120), (wx + 60, 120), (wx + 60, 200), (wx - 60, 200)], rgb("#8fc0e0"), lw=6,
                        amp=0.6, seed=seed + 1)
        for k in range(1, 4):
            ink.line(cr, [(wx - 60 + k * 30, 120), (wx - 60 + k * 30, 200)], lw=4, ink=rgb("#b39a6a"), amp=0)
    elif name == "tavern_inside":
        wall = rgb("#a08a66")
        cr.set_source_rgba(*wall)
        cr.paint()
        # dark beams, plaster between, a small leaded window, a shelf of tankards
        for x in (120, 620, 1180, 1720):
            ink.line(cr, [(x, -10), (x, H * 0.8)], lw=26, ink=rgb("#4a3424"), amp=0.8, seed=x)
        ink.line(cr, [(-10, 140), (W + 10, 140)], lw=28, ink=rgb("#4a3424"), amp=0.8, seed=seed)
        wx = r.choice([380, 900, 1450])
        ink.fill_stroke(cr, [(wx - 80, 260), (wx + 80, 260), (wx + 80, 420), (wx - 80, 420)], rgb("#3a4a6a"), lw=8,
                        amp=0.8, seed=seed + 1)
        for k in range(1, 4):
            ink.line(cr, [(wx - 80 + k * 40, 260), (wx - 80 + k * 40, 420)], lw=4, ink=rgb("#6a5a44"), amp=0)
            ink.line(cr, [(wx - 80, 260 + k * 40), (wx + 80, 260 + k * 40)], lw=4, ink=rgb("#6a5a44"), amp=0)
        sx = wx + 400 if wx < 1000 else wx - 500
        ink.line(cr, [(sx - 150, 330), (sx + 150, 330)], lw=10, ink=rgb("#4a3424"), amp=0.5, seed=seed + 2)
        for k in range(4):
            ink.fill_stroke(cr, [(sx - 130 + k * 70, 330), (sx - 96 + k * 70, 330), (sx - 100 + k * 70, 280),
                                 (sx - 126 + k * 70, 280)], rgb("#8a8d92"), lw=3, amp=0)
    elif name == "parlour_inside":
        wall = rgb("#6f7c5c")
        cr.set_source_rgba(*wall)
        cr.paint()
        # striped paper, a picture rail, a framed picture
        for k in range(0, W, 90):
            ink.line(cr, [(k, -10), (k, H * 0.8)], lw=18, ink=shade(wall, 0.92), amp=0)
        ink.line(cr, [(-10, 170), (W + 10, 170)], lw=10, ink=rgb("#e6dcc4"), amp=0.5, seed=seed)
        px = r.choice([420, 1000, 1500])
        ink.fill_stroke(cr, [(px - 110, 300), (px + 110, 300), (px + 110, 470), (px - 110, 470)], rgb("#c9a36a"),
                        lw=10, amp=0.6, seed=seed + 1)
        ink.fill_stroke(cr, [(px - 90, 320), (px + 90, 320), (px + 90, 450), (px - 90, 450)], rgb("#8fb3c9"), lw=0, amp=0)
        ink.fill_stroke(cr, [(px - 90, 400), (px - 20, 350), (px + 40, 410), (px + 90, 370), (px + 90, 450),
                             (px - 90, 450)], rgb("#7a9a5c"), lw=0, amp=0)
        # skirting
        ink.line(cr, [(-10, H * 0.8 - 12), (W + 10, H * 0.8 - 12)], lw=16, ink=rgb("#e6dcc4"), amp=0)
    elif name == "cottage_inside":
        wall = rgb("#d8c39a")
        cr.set_source_rgba(*wall)
        cr.paint()
        for x in (140, 700, 1260, 1800):
            ink.line(cr, [(x, -10), (x, H * 0.8)], lw=20, ink=rgb("#6d4b2d"), amp=0.8, seed=x)
        ink.line(cr, [(-10, 150), (W + 10, 150)], lw=22, ink=rgb("#6d4b2d"), amp=0.8, seed=7)
        # a small window showing the sky outside, at this hour
        wx = r.choice([420, 980, 1500])
        ink.fill_stroke(cr, [(wx - 90, 280), (wx + 90, 280), (wx + 90, 470), (wx - 90, 470)], _outside(time)[0],
                        lw=8, amp=0.8, seed=seed)
        ink.line(cr, [(wx, 280), (wx, 470)], lw=7, ink=rgb("#6d4b2d"), amp=0)
        ink.line(cr, [(wx - 90, 375), (wx + 90, 375)], lw=7, ink=rgb("#6d4b2d"), amp=0)


# the water band, (top, bottom) above the ground line: the near bank is a
# clear strip of ground, so a fire by the river is on the bank, not "drawn on
# top of the river" (the eighth film's storyboard)
WATER_BAND = {"river": (190, 100), "lake": (230, 110), "sea": (230, 110), "stream": (150, 96),
              "spring": (160, 70)}
SPRING_X = (0.56, 0.86)          # the spring's pool spans this part of the frame; the wall is above it


def _water(cr, kind, gy, seed):
    """The still body of the water; its flow is drawn in ambient()."""
    top = gy - WATER_BAND[kind][0]
    bot = gy - WATER_BAND[kind][1]
    c = rgb("#5b9bc0")
    pts = [(-40, top), (W * 0.4, top + 10), (W + 40, top - 6), (W + 40, bot), (W * 0.5, bot + 12), (-40, bot)]
    if kind == "sea":
        pts = [(-40, H * 0.58), (W + 40, H * 0.58), (W + 40, bot), (W * 0.5, bot + 15), (-40, bot)]
    elif kind == "stream":
        # a narrow brook winding across the grass, its banks in the open
        r = random.Random(seed + 5)
        a = r.uniform(-18, 18)
        pts = [(-40, top + a), (W * 0.22, top - 12 + a), (W * 0.5, top + 14 - a), (W * 0.78, top - 10 + a),
               (W + 40, top + 6 - a), (W + 40, bot - 4 + a), (W * 0.74, bot + 10 - a), (W * 0.48, bot - 8 + a),
               (W * 0.2, bot + 8 - a), (-40, bot + a)]
        c = rgb("#6aa6c8")
    elif kind == "spring":
        # a pool at the foot of the wall, fed from a stone spout
        x0, x1 = W * SPRING_X[0], W * SPRING_X[1]
        pts = ink.ellipse_pts((x0 + x1) / 2, (top + bot) / 2 + 20, (x1 - x0) / 2, (bot - top) / 2 - 8, 26)
        c = rgb("#5f9cc0")
    ink.fill_stroke(cr, pts, c, lw=4.5, amp=2, seed=seed, shadow=shade(c, 0.88), shadow_dir=(0, -1))
    if kind == "stream":
        # a few stones in and along it
        r = random.Random(seed + 9)
        for k in range(7):
            sx = r.uniform(60, W - 60)
            sy = r.uniform(top + 6, bot + 14)
            st = rgb("#8f8a80")
            ink.fill_stroke(cr, ink.blob_pts(sx, sy, r.uniform(16, 34), r.uniform(9, 16), seed + k, 0.1, 10), st,
                            lw=3, amp=0.8, seed=seed + k, shadow=shade(st), shadow_dir=(0, 1))
    if kind == "spring":
        # a rim of flat stones round the pool
        x0, x1 = W * SPRING_X[0], W * SPRING_X[1]
        r = random.Random(seed + 9)
        for k in range(10):
            ang = math.pi * (0.1 + 0.8 * k / 9)
            sx = (x0 + x1) / 2 + math.cos(ang) * (x1 - x0) / 2 * 1.02
            sy = (top + bot) / 2 + 20 + math.sin(ang) * ((bot - top) / 2 - 2)
            st = rgb("#b9ad98")
            ink.fill_stroke(cr, ink.blob_pts(sx, sy, r.uniform(22, 40), r.uniform(10, 16), seed + k, 0.1, 10), st,
                            lw=3, amp=0.8, seed=seed + k, shadow=shade(st), shadow_dir=(0, 1))
    return top, bot


def _spring_wall(cr, r, gy, seed):
    """The town wall the spring runs out from: dressed stone across the
    back, a lion's-mouth spout over the pool, a few ferns at the wet foot."""
    top = H * 0.36
    foot = gy - WATER_BAND["spring"][0] - 10
    stone = rgb("#c9bca4")
    ink.fill_stroke(cr, [(-40, foot), (-40, top), (W + 40, top - 8), (W + 40, foot)], stone, lw=5, amp=2,
                    seed=seed + 21, shadow=shade(stone, 0.9), shadow_dir=(0, 1), texture="grain", tex_alpha=0.15)
    # courses of ashlar
    rows = 5
    for i in range(rows + 1):
        y = top + (foot - top) * i / rows
        ink.line(cr, [(-40, y + r.uniform(-3, 3)), (W + 40, y + r.uniform(-3, 3))], lw=3, ink=shade(stone, 0.72),
                 amp=1.2, seed=seed + i)
        step = r.uniform(230, 300)
        x = r.uniform(0, step) if i % 2 else r.uniform(-step, 0) + step / 2
        while x < W:
            ink.line(cr, [(x, y), (x + 2, y + (foot - top) / rows)], lw=3, ink=shade(stone, 0.72), amp=1.0,
                     seed=seed + int(x))
            x += step
    # the spout, a carved mouth, above the pool's far side
    sx = W * (SPRING_X[0] + SPRING_X[1]) / 2
    sy = foot - 38
    mouth = rgb("#a89b84")
    ink.fill_stroke(cr, ink.blob_pts(sx, sy - 24, 46, 34, seed + 31, 0.12, 14), mouth, lw=4, amp=1.2,
                    seed=seed + 31, shadow=shade(mouth), shadow_dir=(0, 1))
    ink.fill_stroke(cr, [(sx - 18, sy - 10), (sx + 18, sy - 10), (sx + 12, sy + 6), (sx - 12, sy + 6)],
                    rgb("#3a3330"), lw=3, amp=0)
    # ferns and moss where the wall is always wet
    fern = rgb("#5d8a4a")
    for k in range(6):
        fx = W * SPRING_X[0] + r.uniform(-80, (SPRING_X[1] - SPRING_X[0]) * W + 80)
        fy = foot + r.uniform(-6, 10)
        for j in range(3):
            ink.line(cr, [(fx, fy), (fx + r.uniform(-30, 30), fy - r.uniform(20, 46))], lw=3.2, ink=fern, amp=0.6,
                     seed=seed + k * 3 + j)


def tree_line(name: str, seed: int, shot: str = "wide") -> list[tuple[float, str, float, float]]:
    """The setting's own trees as (x, kind, scale, base y), a pure function
    of (name, seed, shot): drawn by draw_still and read by the layout. The
    tree line is nearer in a close shot, so the trees are bigger and fewer:
    at one size for every shot a seated woman was "about as tall as the
    trees" (the sixth film's judge)."""
    st = SETTINGS.get(name)
    if st is None:
        return []
    r = random.Random(seed * 7 + 11)
    tk = CLOSE_TREES if shot == "close" else 1.0
    out = []
    if name == "nile_bank":
        for k in range(int(5 / tk) + 1):
            out.append((k * 430 * tk + r.uniform(-60, 60), "palm", 0.75 * tk, H * st.horizon + 30))
    elif name == "olive_grove":
        for k in range(int(6 / tk) + 1):
            out.append((k * 360 * tk + r.uniform(-70, 70), "olive", 0.7 * tk, H * 0.72))
    elif name == "forest":
        for k in range(int(9 / tk) + 1):
            out.append((k * 230 * tk + r.uniform(-40, 40), "pine" if k % 2 else "tree", 0.75 * tk, H * 0.72))
    elif name == "snowfield":
        for k in range(int(6 / tk) + 1):
            out.append((k * 360 * tk + r.uniform(-60, 60), "snow_pine", 0.65 * tk, H * 0.71))
    return out


CITY_ERAS = ("victorian", "early_modern")     # a river or lake in these eras is a city's river or park lake


def draw_still(cr, name: str, time: str, weather: str, seed: int, shot: str = "wide", era: str | None = None,
               clear=()) -> dict:
    """Paint the still world for a scene. Returns layout facts the scene
    needs. `clear` is the x-spans the people and the big props take, so the
    sun or the moon stands where its path on the water is in view."""
    st = SETTINGS[name]
    r = random.Random(seed)
    gy = H * GROUND_Y
    facts = {"ground_y": gy, "water": None}
    if st.interior:
        _interior(cr, name, seed, r, time)
        _ground(cr, st.ground, gy, seed + 1)
        return facts
    _sky(cr, time if weather not in ("rain",) else ("night" if time == "night" else "dusk"))
    if time == "night" and weather in ("clear", "snow", "frost"):
        _stars(cr, r)
        if weather == "clear" and name in OPEN_SKY and r.random() < 0.5:
            _milky_way(cr, r)
    if weather in ("clear", "cloudy", "snow", "frost") or time == "night":
        facts["sky_light"] = _sun_moon(cr, time, r, clear if st.water else ())
    far = {"day": rgb("#9fb7a8"), "dawn": rgb("#9d8fa0"), "dusk": rgb("#7a6485"), "night": rgb("#34466b")}[time]
    # the cave mouth is the film's most-used picture: half the time it has
    # the range behind it, half the time only hills, so it is not one layout
    city_water = era in CITY_ERAS and name in ("lakeshore", "riverbank")
    if city_water:
        # run #21's judge: "mountains and a lake appear in a London street
        # story" — a Victorian park lake or the Thames has roofs behind it
        _town(cr, r, H * st.horizon + 40, seed, facts)
    elif name in ("mountains", "snowfield", "lakeshore") or (name == "cave_mouth" and r.random() < 0.5):
        _mountains(cr, r, H * st.horizon, far, seed, snowcaps=True)
    if not city_water:
        _hills(cr, r, H * st.horizon + 30, 60, ink.mix(far, rgb(GROUND[st.ground]), 0.45), seed + 3)
    if name == "castle":
        _castle(cr, W * r.uniform(0.3, 0.7), H * st.horizon + 60, seed)
    if name == "forum":
        _town(cr, r, H * st.horizon + 40, seed, facts)
        _colonnade(cr, r, H * st.horizon + 150, seed, wall=(shot == "close"), facts=facts)
    if name == "street":
        from .props import terrace
        for k in range(4):
            terrace(cr, 260 + k * 480 + r.uniform(-30, 30), H * st.horizon + 190, 0.8, 0.0, seed + k)
    if name == "farmyard":
        from .props import barn
        barn(cr, W * r.uniform(0.25, 0.75), H * st.horizon + 90, 0.75, 0.0, seed)
        for k in range(6):
            x = -60 + k * 400 + r.uniform(-30, 30)
            ink.line(cr, [(x, H * st.horizon + 90), (x, H * st.horizon + 30)], lw=6, ink=rgb("#6a5236"), amp=0.5, seed=k)
            ink.line(cr, [(x, H * st.horizon + 55), (x + 400, H * st.horizon + 55)], lw=4, ink=rgb("#6a5236"), amp=0.5, seed=k + 9)
    if name == "market_square":
        from .props import timber_house
        for k in range(4):
            timber_house(cr, 250 + k * 480 + r.uniform(-40, 40), H * st.horizon + 170, 0.8, 0.0, seed + k)
    if name == "harbour":
        from .props import ship
        ship(cr, W * r.uniform(0.3, 0.7), H * 0.58 + 40, 0.9, 0.0, seed)
    if name == "spring":
        _spring_wall(cr, r, gy, seed)
    if name == "stream":
        # a few bushes along the far bank
        from .props import bush
        for k in range(4):
            bush(cr, 200 + k * 520 + r.uniform(-120, 120), gy - WATER_BAND["stream"][0] - 16, 0.6, 0.0, seed + k)
    if name == "desert":
        _dunes(cr, r, H * st.horizon + 20, seed)
        from .props import pyramid
        for k, (fx, sc) in enumerate(((0.18, 0.55), (0.42, 0.75), (0.7, 0.45))):
            pyramid(cr, W * fx + r.uniform(-60, 60), H * st.horizon + 40, sc, 0.0, seed + k)
    # the tree line is data (tree_line): the layout reads the same list, so
    # a tent is never placed on a trunk and a torch never in a canopy
    for k, (x, kind, ts, ty) in enumerate(tree_line(name, seed, shot)):
        if kind == "palm":
            from .props import palm
            palm(cr, x, ty, ts, 0.0, seed + k)
        elif kind == "olive":
            from .props import olive
            olive(cr, x, ty, ts, 0.0, seed + k)
        elif kind == "snow_pine":
            pine(cr, x, ty, ts, 0.0, seed + k, snow=True)
        elif kind == "pine":
            pine(cr, x, ty, ts, 0.0, seed + k)
        else:
            tree(cr, x, ty, ts, 0.0, seed + k)
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
        _cave_mouth(cr, r, gy, seed, shot)
    return facts


# how much nearer the world is in a close shot: the cave mouth grows with
# it, so a woman is not "filling the cave mouth" (the sixth film's judge)
# settings with a wide open sky where a clear night may show the Milky Way
OPEN_SKY = ("grassland", "mountains", "riverbank", "lakeshore", "snowfield", "seashore", "desert", "field",
            "harbour", "nile_bank", "stream")
CLOSE_WORLD = 1.35
CLOSE_TREES = 1.9                # the tree line, nearer still: about twice a standing figure


VILLA_DOOR_HALF = 150            # half-width of the villa's doorway, at scale 1


def house_hanging_x(seed: int) -> float:
    """Where the house's cloak and bag hang: under the window's side, a
    pure function of the seed (the window itself is the room RNG's first
    draw)."""
    r = random.Random(seed)
    wx = r.choice([420, 1500]) + r.uniform(-60, 60)
    return wx + 230 if wx < W / 2 else wx - 230


def _wall_hanging(cr, x: float, seed: int):
    """Two pegs with a cloak and a bag on them, at eye height: the plain
    wall behind a close-up was "the upper half ... blank wall" to run 94's
    and 96's judge."""
    r = random.Random(seed + 5)
    peg = rgb("#6a4c32")
    for dx in (-40, 40):
        ink.fill_stroke(cr, ink.box(x + dx - 7, 470, x + dx + 7, 486), peg, lw=3, amp=0.4, seed=seed + dx)
    cloak = rgb(r.choice(["#7a5a8c", "#8c4a3a", "#4e6a52", "#9a7a3c"]))
    ink.fill_stroke(cr, [(x - 60, 486), (x - 20, 486), (x - 8, 500), (x + 2, 486), (x + 8, 500),
                         (x + 24, 486), (x + 70, 486), (x + 62, 700), (x + 26, 712), (x - 14, 706),
                         (x - 52, 700)], cloak, lw=5, amp=1.4, seed=seed + 8, shadow=shade(cloak),
                    shadow_dir=(1, 0.5), texture="hatch", tex_alpha=0.2)
    bag = rgb("#b89a66")
    ink.fill_stroke(cr, [(x + 40, 486), (x + 44, 520), (x + 88, 520), (x + 84, 486)], (0, 0, 0, 0), lw=3, amp=0)
    ink.fill_stroke(cr, ink.blob_pts(x + 66, 560, 34, 42, seed + 9, 0.1, 12), bag, lw=4, amp=1.2, seed=seed + 9,
                    shadow=shade(bag), shadow_dir=(1, 0.6))


def villa_doorway(r_or_seed) -> float:
    """Centre x of the villa's doorway: a pure function of the seed (the
    first thing the room's RNG decides), so the layout can keep a sleeper
    out of it — a woman drawn asleep across the courtyard door read as
    lying in the doorway."""
    r = r_or_seed if isinstance(r_or_seed, random.Random) else random.Random(r_or_seed)
    return r.choice([300, 1620]) + r.uniform(-40, 40)


def cave_opening(seed: int, shot: str = "wide") -> tuple[int, float, float]:
    """(side, centre x, half width) of the cave mouth's dark opening for a
    seed — a pure function, so the layout (which runs before the still is
    painted) can keep people out of it. The fifth film's judge: dark hair
    and a beard against the black of the opening left "a floating white
    mask", so nobody stands in front of it."""
    side = 1 if seed % 2 else -1
    x0 = 0 if side < 0 else W
    k = CLOSE_WORLD if shot == "close" else 1.0
    return side, x0 - side * W * 0.3, W * 0.15 * k


def _cave_mouth(cr, r, gy, seed, shot="wide"):
    """A hill of rock on one side of the frame with an arched dark opening."""
    rockc = rgb("#857a6d")
    side, mx, ow = cave_opening(seed, shot)
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
    oh = H * 0.4 * (CLOSE_WORLD if shot == "close" else 1.0)
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
    _evening(cr, name, time, weather, facts, t, seed)
    if weather == "rain":
        _rain(cr, t, seed)
    elif weather == "snow":
        _snow(cr, t, seed)
    elif weather == "fog":
        for k in range(3):
            x = (t * 14 * (k + 1) + k * 700) % (W + 1200) - 600
            ink.glow(cr, x, H * (0.55 + 0.08 * k), 520, (0.9, 0.92, 0.95), 0.35)


def _spring_flow(cr, top, bot, t, seed, hl):
    """Water falling from the spout into the pool, and the rings it makes."""
    sx = W * (SPRING_X[0] + SPRING_X[1]) / 2
    sy0 = top - 10 - 32                   # the spout mouth (settings._spring_wall)
    sy1 = (top + bot) / 2 + 8
    # the falling thread: beads carried down it
    cr.set_line_width(7)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_source_rgba(hl[0], hl[1], hl[2], 0.75)
    cr.move_to(sx, sy0)
    cr.curve_to(sx + 2, sy0 + 20, sx + 6, sy1 - 30, sx + 8, sy1)
    cr.stroke()
    for k in range(5):
        u = (t * 1.6 + k / 5) % 1.0
        y = sy0 + (sy1 - sy0) * u
        ink.dot(cr, sx + 8 * u * u, y, 5 + 3 * u, (1, 1, 1, 0.9))
    # rings spreading on the pool, and a few ripple dashes drifting out
    for k in range(3):
        u = ((t / 1.1) + k / 3) % 1.0
        rad = 10 + u * 120
        cr.set_source_rgba(hl[0], hl[1], hl[2], 0.8 * (1 - u))
        cr.set_line_width(5)
        cr.save()
        cr.translate(sx + 8, sy1 + 6)
        cr.scale(1, 0.32)
        cr.arc(0, 0, rad, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()
    r = random.Random(seed + 17)
    x0, x1 = W * SPRING_X[0], W * SPRING_X[1]
    for k in range(10):
        gx = r.uniform(x0 + 40, x1 - 40)
        gy = r.uniform(top + 20, bot + 10)
        ph = r.uniform(0, 6.28)
        v = (math.sin(t * 2.2 + ph) + 1) / 2
        cr.set_source_rgba(hl[0], hl[1], hl[2], 0.7 * v)
        cr.set_line_width(6)
        cr.move_to(gx - 20, gy)
        cr.curve_to(gx - 8, gy - 4, gx + 8, gy + 4, gx + 20, gy)
        cr.stroke()


# px/s the ripple dashes travel: a river runs, a stream hurries, the sea and
# a lake roll in. Measured with the cadence probe on a CLOSE shot by the
# water with no fire in it (the shore at dawn, run 98): at 40 the dashes
# move a sixth of a pixel a frame at the probe's width and 96% of frames
# read as held; the shot has nothing else that moves
WATER_SPEED = {"river": 120, "stream": 170, "sea": 40, "lake": 40}


def _flow(cr, kind, top, bot, t, seed, time):
    """Water that runs: rows of light ripple dashes carried along by the
    current (a river) or rolling in (lake/sea), each dash a clear mark."""
    r = random.Random(seed + 11)
    # bright, thick, quick: the current is what keeps a riverbank alive when
    # nothing else moves, and it has to read at a glance — measured with the
    # gate's probe, a river whose ripples were a shade dimmer sat under its
    # block threshold once the band moved by half a block row
    hl = (1, 1, 1, 0.8) if time != "night" else (0.85, 0.92, 1.0, 0.8)
    if kind == "spring":
        _spring_flow(cr, top, bot, t, seed, hl)
        return
    rows = 9 if kind != "stream" else 4
    speed = WATER_SPEED.get(kind, WATER_SPEED["sea"])
    for i in range(rows):
        y = top + (bot - top) * (i + 0.6) / rows
        spacing = r.uniform(150, 220)
        off = r.uniform(0, spacing)
        L = r.uniform(60, 100) * (0.6 + 0.4 * i / rows)
        x = -spacing + (off + t * speed * (0.7 + 0.3 * i / rows)) % spacing
        while x < W + spacing:
            cr.move_to(x, y)
            cr.curve_to(x + L * 0.3, y - 5, x + L * 0.7, y + 5, x + L, y)
            cr.set_line_width(9)
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


def _evening(cr, name: str, time: str, weather: str, facts: dict, t: float, seed: int):
    """The evening doing what evenings do, so a held picture is still a
    living place (the operator: "more movement ... purposeful movement"):
    at dusk the town's lamps are lit one window at a time and its hearths
    send up smoke; at night the windows glow and the smoke still rises; at
    dusk the birds go home across the sky. Nothing here moves for the sake
    of moving — each is a thing the evening is actually doing."""
    town = facts.get("town")
    r = random.Random(seed * 13 + 5)
    if town and time in ("dusk", "night"):
        hidden = town.get("hidden_below")
        for k, (wx, wy) in enumerate(town["windows"]):
            if r.random() < 0.35:
                continue                        # not every house has a lamp lit
            if hidden is not None and wy > hidden:
                continue                        # behind the stoa's wall in a close shot
            on = 0.0 if time == "night" else r.uniform(1.0, 11.0)
            if t < on:
                continue
            k_in = min(1.0, (t - on) / 0.6)     # a lamp catching, not a switch
            fl = 0.8 + 0.2 * (ink.vnoise(t, 6.0, seed + k) + 1) / 2
            ink.glow(cr, wx, wy, 34, (1.0, 0.72, 0.35), 0.55 * k_in * fl)
            cr.rectangle(wx - 10, wy - 22, 20, 44)
            cr.set_source_rgba(1.0, 0.78, 0.42, 0.85 * k_in * fl)
            cr.fill()
        for k, (sx, sy) in enumerate(town["roofs"]):
            if k % 2:
                continue                        # supper is on in every other house
            for j in range(6):
                u = ((t / 9.0) + j / 6.0 + k * 0.13) % 1.0
                px = sx + u * 70 + math.sin(t * 0.7 + j + k) * 8
                py = sy - u * 190
                al = (0.34 if time == "dusk" else 0.24) * math.sin(math.pi * u)
                c = (0.82, 0.8, 0.8) if time == "dusk" else (0.6, 0.62, 0.7)
                ink.glow(cr, px, py, 16 + 26 * u, c, al)
    if time == "dusk" and weather in ("clear", "cloudy") and not SETTINGS[name].interior:
        # a flock going home to roost: once across the sky, slowly
        span = W + 600
        x0 = (t * 70 + r.uniform(0, 400)) - 300
        if x0 < span:
            y0 = H * r.uniform(0.14, 0.26)
            for b in range(7):
                bx = x0 - abs(b - 3) * 46 - (b // 4) * 12
                by = y0 + abs(b - 3) * 22 + math.sin(t * 3 + b) * 4
                flap = math.sin(t * 7.0 + b * 1.3) * 7
                ink.line(cr, [(bx - 14, by - flap), (bx, by + 3), (bx + 14, by - flap)], lw=3.2,
                         ink=(0.18, 0.14, 0.2), amp=0)


PATH_GLINTS = 36          # glints in the sun's or the moon's path on the water
PATH_HALF_WIDTH = 260.0   # px either side of it


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
    x0, x1 = (W * SPRING_X[0] + 40, W * SPRING_X[1] - 40) if kind == "spring" else (0, W)
    for k in range({"sea": 130, "stream": 60, "spring": 30}.get(kind, 110)):
        gx = r.uniform(x0, x1)
        gy = r.uniform(top + 8, bot - 8)
        w_ = r.uniform(20, 40)
        v = ink.vnoise(t, 7.0 + (k % 5), seed * 31 + k)
        if v > 0.1:
            a = min(1.0, (v - 0.1) * 1.6)
            ink.fill_stroke(cr, ink.ellipse_pts(gx, gy, w_, w_ * 0.24, 10), (gl[0], gl[1], gl[2], a),
                            lw=0, amp=0)
    sky = facts.get("sky_light")
    if sky and kind != "spring":
        # the sun's or the moon's path: a column of broader glints under it,
        # each winking at its own rate — the one thing on open water that
        # really moves at a glance. Measured with the cadence probe on a
        # close shot of the shore at dawn with no fire in it: the ripple
        # dashes alone left 96% of frames reading as held at any speed, the
        # scattered glints are too small to count, and the path carries it
        rp = random.Random(seed + 29)
        sx = sky[0]
        for k in range(PATH_GLINTS):
            gx = sx + rp.gauss(0, PATH_HALF_WIDTH / 2)
            gy = rp.uniform(top + 8, bot - 8)
            w_ = rp.uniform(34, 70)
            v = ink.vnoise(t, 6.0 + (k % 4), seed * 37 + k)
            if v > 0.0:
                ink.fill_stroke(cr, ink.ellipse_pts(gx, gy, w_, w_ * 0.26, 10), (gl[0], gl[1], gl[2], min(0.9, v * 1.4)),
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
