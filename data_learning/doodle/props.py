"""Props: the things in a doodle scene, drawn with feet on the ground.

Each prop is `PROPS[name]`: how wide it sits on the ground (layout), which
layer it lives in, which eras it belongs to, and whether it is LIVING —
something that genuinely moves on every frame (a fire burning, water running,
an animal breathing smoke in the cold). The showrunner's cadence probe reads a
held frame as a duplicate, and the operator ruled out every trick that makes a
still picture shiver (`shared/camera_float.py`). So a sleep scene earns its
motion honestly: every scene has at least one living thing, and
`tests/test_ori_sleep.py` renders each living prop alone on a plain ground and
measures it with the gate's own detector.

Draw functions take (cr, x, ground_y, s, t, seed) where s is the scene scale
(1.0 = a person 46px head radius) and t is seconds into the scene.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from . import ink
from .ink import rgb, shade

WOOD = rgb("#7a5233")
WOOD_D = rgb("#5a3b24")
STONE = rgb("#9a958d")
FLAME_O = rgb("#f4892a")
FLAME_Y = rgb("#ffd55c")
FLAME_R = rgb("#e2562a")


def _n(t, f, ph):
    """A fast, smooth, deterministic flicker in [-1, 1]."""
    return (0.55 * math.sin(t * f + ph) + 0.3 * math.sin(t * f * 1.73 + ph * 2.1)
            + 0.15 * math.sin(t * f * 3.11 + ph * 0.7))


def flame(cr, x, y, size, t, seed=0, glow_r=3.2, glow_a=0.35):
    """A living flame. Every tongue takes a new height about ten times a
    second and the whole fire leans and breathes — a real fire changes shape
    between frames, so this one does too."""
    r = random.Random(seed)
    ph = [r.uniform(0, 6.28) for _ in range(7)]
    if glow_r:
        k = 0.8 + 0.2 * ink.vnoise(t, 8.0, seed + 5)
        ink.glow(cr, x, y - size * 0.45, size * glow_r * k, (1.0, 0.72, 0.35), glow_a * (0.8 + 0.3 * k))
    lean = 0.18 * ink.vnoise(t, 3.0, seed + 7)
    for layer, (col, sc) in enumerate(((FLAME_R, 1.12), (FLAME_O, 1.0), (FLAME_Y, 0.58))):
        n = 5
        pts = [(x - size * 0.55 * sc, y)]
        for i in range(n):
            u = (i + 0.5) / n
            h = size * sc * (0.55 + 0.45 * math.sin(math.pi * u)) * \
                (0.66 + 0.34 * ink.vnoise(t, 11.0 + i, seed * 7 + i * 3 + layer))
            sway = size * (0.14 * ink.vnoise(t, 6.0, seed * 11 + i) + lean)
            pts.append((x + size * sc * (u - 0.5) * 1.05 + sway, y - h * 1.45))
            pts.append((x + size * sc * (u - 0.5 + 0.1) * 1.05 + sway * 0.3, y - h * 0.55))
        pts.append((x + size * 0.55 * sc, y))
        pts.append((x, y + size * 0.08))
        ink.fill_stroke(cr, pts, col, lw=0, amp=0)
    del ph


def _logs(cr, x, y, s, seed):
    lw = 4.5 * s
    for a, dx in ((-0.35, -1), (0.35, 1), (0.0, 0)):
        L = 70 * s
        cx, cy = x + dx * 8 * s, y - 6 * s
        p0 = (cx - L * math.cos(a), cy + L * math.sin(a) * 0.4)
        p1 = (cx + L * math.cos(a), cy - L * math.sin(a) * 0.4)
        nxv, nyv = -(p1[1] - p0[1]), (p1[0] - p0[0])
        d = math.hypot(nxv, nyv) or 1
        nxv, nyv = nxv / d * 11 * s, nyv / d * 11 * s
        pts = [(p0[0] + nxv, p0[1] + nyv), (p1[0] + nxv, p1[1] + nyv),
               (p1[0] - nxv, p1[1] - nyv), (p0[0] - nxv, p0[1] - nyv)]
        ink.fill_stroke(cr, pts, WOOD, lw=lw, amp=0.8, seed=seed + int(dx * 10),
                        shadow=WOOD_D, shadow_dir=(0, 1))


def campfire_base(cr, x, y, s, t, seed):
    r = random.Random(seed)
    for i in range(9):
        a = math.pi * (0.95 + 1.1 * i / 8)
        sx, sy = x + math.cos(a) * 92 * s, y + math.sin(a) * 22 * s + 10 * s
        ink.fill_stroke(cr, ink.blob_pts(sx, sy, 20 * s, 13 * s, seed + i, 0.15, 12),
                        mix_stone(r), lw=3.6 * s, amp=0.8, seed=seed + i, shadow=shade(STONE),
                        shadow_dir=(0, 1))
    _logs(cr, x, y, s, seed)


def embers(cr, x, y, s, t, seed, n=34, spread=46.0, rise=240.0):
    """Sparks lifting off a fire: bright, fast, each one winking out as it
    cools. They are what a camp fire at night actually looks like, and the
    one part of a fire bright enough against the dark to read from across
    the room."""
    r = random.Random(seed + 77)
    for k in range(n):
        speed = r.uniform(0.7, 1.3)
        period = rise * 1.6 / (speed * 150)
        u = ((t / period) + r.random()) % 1.0
        sx = x + (r.uniform(-1, 1) * spread * 0.5 + math.sin(t * 2.3 + k) * spread * u) * s
        sy = y - (rise * u * speed * 1.6) * s
        rad = (1.6 + 2.6 * (1 - u)) * s
        a = max(0.0, 1 - u) * (0.65 + 0.35 * ink.vnoise(t, 9.0, seed + k))
        ink.dot(cr, sx, sy, rad, (1.0, 0.9, 0.55, a))


def campfire(cr, x, y, s, t, seed):
    flame(cr, x, y - 10 * s, 64 * s, t, seed)
    embers(cr, x, y - 70 * s, s, t, seed)


def mix_stone(r):
    return ink.mix(STONE, rgb("#b8b2a8"), r.random() * 0.6)


def hearth_base(cr, x, y, s, t, seed):
    """A stone fireplace with a cooking fire (inside a cottage or hut)."""
    ink.fill_stroke(cr, [(x - 150 * s, y), (x - 150 * s, y - 250 * s), (x - 110 * s, y - 290 * s),
                         (x + 110 * s, y - 290 * s), (x + 150 * s, y - 250 * s), (x + 150 * s, y)],
                    rgb("#8f8a82"), lw=5 * s, amp=1.5, seed=seed, texture="grain", tex_alpha=0.2,
                    shadow=shade(rgb("#8f8a82")), shadow_dir=(1, 0))
    ink.fill_stroke(cr, [(x - 95 * s, y), (x - 95 * s, y - 170 * s), (x, y - 205 * s),
                         (x + 95 * s, y - 170 * s), (x + 95 * s, y)], rgb("#2b211d"), lw=4 * s, amp=1,
                    seed=seed + 1)
    _logs(cr, x, y - 4 * s, s * 0.7, seed)


def hearth(cr, x, y, s, t, seed):
    flame(cr, x, y - 12 * s, 50 * s, t, seed, glow_r=3.6, glow_a=0.4)
    embers(cr, x, y - 60 * s, s, t, seed, n=14, spread=60, rise=110)


def torch_base(cr, x, y, s, t, seed):
    """A torch in a bracket on a wall, flame at about head height."""
    top = y - 260 * s
    ink.line(cr, [(x, top + 90 * s), (x + 6 * s, top)], lw=9 * s, ink=WOOD, amp=0)
    ink.line(cr, [(x - 18 * s, top + 70 * s), (x + 20 * s, top + 70 * s)], lw=5 * s, amp=0)


def torch_wall(cr, x, y, s, t, seed):
    top = y - 260 * s
    flame(cr, x + 6 * s, top + 4 * s, 34 * s, t, seed, glow_r=4.0, glow_a=0.3)
    embers(cr, x + 6 * s, top - 30 * s, s, t, seed, n=18, spread=28, rise=150)


def candle_base(cr, x, y, s, t, seed):
    """A fat candle on a small stand — a close living light for interiors."""
    ink.fill_stroke(cr, [(x - 40 * s, y), (x + 40 * s, y), (x + 30 * s, y - 20 * s), (x - 30 * s, y - 20 * s)],
                    rgb("#6d5a44"), lw=4 * s, amp=0)
    ink.fill_stroke(cr, [(x - 20 * s, y - 20 * s), (x + 20 * s, y - 20 * s), (x + 20 * s, y - 120 * s),
                         (x - 20 * s, y - 120 * s)], rgb("#efe4c8"), lw=4 * s, amp=0.6, seed=seed,
                    shadow=rgb("#d9cba6"), shadow_dir=(1, 0))


def candle(cr, x, y, s, t, seed):
    flame(cr, x, y - 122 * s, 34 * s, t, seed, glow_r=5.0, glow_a=0.45)


def pot_base(cr, x, y, s, t, seed):
    """A clay pot on stones, steam curling up."""
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 45 * s, 58 * s, 48 * s, 26), rgb("#a4613b"), lw=5 * s,
                    amp=1.2, seed=seed, shadow=shade(rgb("#a4613b")), shadow_dir=(1, 0.5))
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 88 * s, 44 * s, 10 * s, 18), rgb("#5e3522"), lw=4 * s, amp=0)


def pot(cr, x, y, s, t, seed):
    _steam(cr, x, y - 100 * s, s, t, seed)


def _steam(cr, x, y, s, t, seed):
    for k in range(3):
        u = ((t * 0.28) + k / 3.0) % 1.0
        cx = x + math.sin(u * 5 + k) * 14 * s
        cy = y - u * 120 * s
        ink.dot(cr, cx, cy, (10 + 16 * u) * s, (1, 1, 1, 0.32 * math.sin(math.pi * u)))


def cauldron_base(cr, x, y, s, t, seed):
    for sx in (-1, 1):
        ink.line(cr, [(x + sx * 70 * s, y), (x + sx * 20 * s, y - 190 * s)], lw=7 * s, ink=WOOD, amp=0)
    ink.line(cr, [(x - 60 * s, y - 175 * s), (x + 60 * s, y - 175 * s)], lw=6 * s, ink=WOOD, amp=0)
    ink.line(cr, [(x, y - 175 * s), (x, y - 130 * s)], lw=3 * s, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 85 * s, 55 * s, 45 * s, 24), rgb("#3c3a3a"), lw=5 * s, amp=0.8,
                    seed=seed)


def cauldron(cr, x, y, s, t, seed):
    flame(cr, x, y - 5 * s, 34 * s, t, seed, glow_r=2.6)
    embers(cr, x, y - 20 * s, s, t, seed, n=12, spread=60, rise=60)
    _steam(cr, x, y - 125 * s, s, t, seed)


def tent(cr, x, y, s, t, seed):
    """A hide tent on poles."""
    c = rgb("#c49a67")
    ink.fill_stroke(cr, [(x - 170 * s, y), (x, y - 250 * s), (x + 170 * s, y)], c, lw=5 * s, amp=2,
                    seed=seed, shadow=shade(c), shadow_dir=(1, 0), texture="grain", tex_alpha=0.18)
    ink.fill_stroke(cr, [(x - 40 * s, y), (x, y - 120 * s), (x + 40 * s, y)], rgb("#3a2a20"), lw=4 * s, amp=1,
                    seed=seed + 1)
    for dx in (-18, 0, 20):
        ink.line(cr, [(x + dx * s * 0.4, y - 245 * s), (x + dx * s, y - 300 * s)], lw=5 * s, ink=WOOD, amp=0)


def hut(cr, x, y, s, t, seed):
    """A round hut with a thatched roof."""
    wall = rgb("#b48a5c")
    ink.fill_stroke(cr, [(x - 150 * s, y), (x - 145 * s, y - 130 * s), (x + 145 * s, y - 130 * s),
                         (x + 150 * s, y)], wall, lw=5 * s, amp=1.5, seed=seed, shadow=shade(wall),
                    shadow_dir=(1, 0), texture="grain", tex_alpha=0.2)
    thatch = rgb("#d9b25e")
    ink.fill_stroke(cr, [(x - 190 * s, y - 115 * s), (x, y - 300 * s), (x + 190 * s, y - 115 * s)], thatch,
                    lw=5 * s, amp=2.5, seed=seed + 1, shadow=shade(thatch), shadow_dir=(1, 0),
                    texture="hatch", tex_alpha=0.12)
    ink.fill_stroke(cr, [(x - 35 * s, y), (x - 35 * s, y - 85 * s), (x + 35 * s, y - 85 * s), (x + 35 * s, y)],
                    rgb("#3a2a20"), lw=4 * s, amp=0.8, seed=seed + 2)


def cottage_base(cr, x, y, s, t, seed):
    """A medieval cottage: wattle walls, timber frame, thatch, a lit window."""
    wall = rgb("#e3d2ae")
    ink.fill_stroke(cr, [(x - 190 * s, y), (x - 190 * s, y - 170 * s), (x + 190 * s, y - 170 * s),
                         (x + 190 * s, y)], wall, lw=5 * s, amp=1.2, seed=seed, shadow=shade(wall),
                    shadow_dir=(1, 0), texture="grain", tex_alpha=0.15)
    for dx in (-190, -60, 60, 190):
        ink.line(cr, [(x + dx * s, y), (x + dx * s, y - 170 * s)], lw=7 * s, ink=WOOD_D, amp=0.6, seed=dx)
    thatch = rgb("#caa35a")
    ink.fill_stroke(cr, [(x - 225 * s, y - 150 * s), (x - 120 * s, y - 320 * s), (x + 120 * s, y - 320 * s),
                         (x + 225 * s, y - 150 * s)], thatch, lw=5 * s, amp=2.2, seed=seed + 1,
                    shadow=shade(thatch), shadow_dir=(1, 0), texture="hatch", tex_alpha=0.12)
    ink.fill_stroke(cr, [(x - 30 * s, y), (x - 30 * s, y - 110 * s), (x + 30 * s, y - 110 * s), (x + 30 * s, y)],
                    rgb("#5a3b24"), lw=4 * s, amp=0.6, seed=seed + 2)
    ink.fill_stroke(cr, [(x + 90 * s, y - 70 * s), (x + 150 * s, y - 70 * s), (x + 150 * s, y - 125 * s),
                         (x + 90 * s, y - 125 * s)], rgb("#f5c563"), lw=4 * s, amp=0.5, seed=seed + 3)


def cottage(cr, x, y, s, t, seed):
    """The cottage's chimney smoke drifting up (its walls are cottage_base)."""
    for k in range(4):
        u = ((t * 0.12) + k / 4.0) % 1.0
        ink.dot(cr, x - 80 * s + u * 60 * s + math.sin(u * 4 + k) * 12 * s, y - 330 * s - u * 200 * s,
                (16 + 22 * u) * s, (0.85, 0.85, 0.85, 0.35 * math.sin(math.pi * u)))


def tree(cr, x, y, s, t, seed):
    r = random.Random(seed)
    trunk = rgb("#7a5634")
    h = (220 + r.random() * 90) * s
    ink.fill_stroke(cr, [(x - 22 * s, y), (x - 14 * s, y - h), (x + 14 * s, y - h), (x + 24 * s, y)], trunk,
                    lw=5 * s, amp=1.2, seed=seed, shadow=shade(trunk), shadow_dir=(1, 0))
    leaf = r.choice([rgb("#6f9a4a"), rgb("#5f8a45"), rgb("#7da356")])
    for k, (dx, dy, rr) in enumerate(((0, -h - 40 * s, 120), (-80, -h + 20 * s, 90), (80, -h + 10 * s, 95))):
        ink.fill_stroke(cr, ink.blob_pts(x + dx * s, y + dy, rr * s, rr * 0.8 * s, seed + k, 0.14, 16),
                        leaf, lw=5 * s, amp=1.5, seed=seed + k, shadow=shade(leaf), shadow_dir=(1, 0.8))


def pine(cr, x, y, s, t, seed, snow=False):
    r = random.Random(seed)
    h = (300 + r.random() * 120) * s
    g = rgb("#3f6b4f") if not snow else rgb("#4f7560")
    ink.line(cr, [(x, y), (x, y - 40 * s)], lw=16 * s, ink=rgb("#5d4128"), amp=0)
    for k in range(4):
        top = y - h + k * h * 0.2
        w = (70 + k * 38) * s
        base = top + h * 0.34
        ink.fill_stroke(cr, [(x, top), (x + w, base), (x - w, base)], g, lw=5 * s, amp=1.4, seed=seed + k,
                        shadow=shade(g), shadow_dir=(1, 0))
        if snow:
            ink.fill_stroke(cr, [(x, top), (x + w * 0.45, top + h * 0.15), (x - w * 0.45, top + h * 0.15)],
                            rgb("#f4f6f8"), lw=0, amp=0)


def bush(cr, x, y, s, t, seed):
    g = rgb("#6c9448")
    ink.fill_stroke(cr, ink.blob_pts(x, y - 45 * s, 90 * s, 55 * s, seed, 0.18, 16), g, lw=5 * s, amp=1.5,
                    seed=seed, shadow=shade(g), shadow_dir=(1, 0.8))
    r = random.Random(seed)
    for k in range(5):
        ink.dot(cr, x + r.uniform(-60, 60) * s, y - r.uniform(30, 80) * s, 7 * s, rgb("#b0334a"))


def rock(cr, x, y, s, t, seed):
    c = rgb("#8f8a82")
    ink.fill_stroke(cr, ink.blob_pts(x, y - 40 * s, 95 * s, 50 * s, seed, 0.16, 14), c, lw=5 * s, amp=1.2,
                    seed=seed, shadow=shade(c), shadow_dir=(1, 0.8), texture="grain", tex_alpha=0.15)


def reeds(cr, x, y, s, t, seed):
    r = random.Random(seed)
    for k in range(9):
        dx = r.uniform(-60, 60) * s
        h = r.uniform(80, 150) * s
        sway = math.sin(t * 0.9 + k) * 6 * s
        ink.line(cr, [(x + dx, y), (x + dx + sway * 0.5, y - h * 0.5), (x + dx + sway, y - h)], lw=4 * s,
                 ink=rgb("#5a7a3a"), amp=0)
        if k % 3 == 0:
            ink.fill_stroke(cr, ink.ellipse_pts(x + dx + sway, y - h - 10 * s, 6 * s, 18 * s, 10), rgb("#7a4f2e"),
                            lw=2.5 * s, amp=0)


def woodpile(cr, x, y, s, t, seed):
    for row in range(3):
        for k in range(4 - row):
            cx = x + (k - (3 - row) / 2) * 42 * s
            cy = y - 22 * s - row * 38 * s
            ink.fill_stroke(cr, ink.ellipse_pts(cx, cy, 21 * s, 19 * s, 14), rgb("#b58a5a"), lw=4 * s, amp=0.6,
                            seed=seed + row * 5 + k)
            ink.fill_stroke(cr, ink.ellipse_pts(cx, cy, 9 * s, 8 * s, 10), rgb("#8c6440"), lw=0, amp=0)


def bedroll(cr, x, y, s, t, seed):
    c = rgb("#9a6a40")
    ink.fill_stroke(cr, [(x - 150 * s, y), (x - 140 * s, y - 28 * s), (x + 150 * s, y - 30 * s), (x + 160 * s, y)],
                    c, lw=4.5 * s, amp=1.5, seed=seed, texture="fur", tex_alpha=0.5)


def hide_rack(cr, x, y, s, t, seed):
    for dx in (-100, 100):
        ink.line(cr, [(x + dx * s, y), (x + dx * s, y - 230 * s)], lw=8 * s, ink=WOOD, amp=0)
    ink.line(cr, [(x - 110 * s, y - 220 * s), (x + 110 * s, y - 220 * s)], lw=7 * s, ink=WOOD, amp=0)
    c = rgb("#c9a06c")
    ink.fill_stroke(cr, [(x - 85 * s, y - 215 * s), (x + 85 * s, y - 215 * s), (x + 70 * s, y - 80 * s),
                         (x + 20 * s, y - 60 * s), (x - 30 * s, y - 75 * s), (x - 80 * s, y - 95 * s)], c, lw=4.5 * s,
                    amp=2, seed=seed, shadow=shade(c), shadow_dir=(1, 0), texture="grain", tex_alpha=0.2)


def deer(cr, x, y, s, t, seed):
    """A deer grazing: the head dips to the grass and comes back up."""
    c = rgb("#a36b3c")
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 120 * s, 95 * s, 45 * s, 24), c, lw=5 * s, amp=1, seed=seed,
                    shadow=shade(c), shadow_dir=(0, 1))
    for dx in (-60, -35, 50, 72):
        ink.line(cr, [(x + dx * s, y - 95 * s), (x + dx * s, y)], lw=7 * s, ink=shade(c, 0.6), amp=0)
    g = (math.sin(t * 2 * math.pi / 7.0 + seed) + 1) / 2
    hx, hy = x + 115 * s, y - 185 * s + g * 150 * s
    ink.line(cr, [(x + 70 * s, y - 135 * s), (hx, hy)], lw=22 * s, ink=c, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(hx + 10 * s, hy, 30 * s, 20 * s, 16, rot=0.4 + g * 0.6), c, lw=4 * s, amp=0)
    ink.dot(cr, hx + 12 * s, hy - 4 * s, 4 * s)
    for k in (-1, 1):
        ink.line(cr, [(hx - 5 * s, hy - 15 * s), (hx - 5 * s + k * 18 * s, hy - 55 * s),
                      (hx - 5 * s + k * 30 * s, hy - 70 * s)], lw=4 * s, ink=rgb("#5a3d25"), amp=0)


def mammoth(cr, x, y, s, t, seed):
    """A woolly mammoth: shaggy domed body, column legs, curled tusks, the
    trunk swinging slowly."""
    c = rgb("#7a5236")
    cd = shade(c, 0.8)
    for dx in (-110, 95):                                  # far legs
        ink.fill_stroke(cr, [(x + (dx - 30) * s, y - 150 * s), (x + (dx + 30) * s, y - 150 * s),
                             (x + (dx + 28) * s, y - 8 * s), (x + (dx - 28) * s, y - 8 * s)], cd,
                        lw=5 * s, amp=1, seed=seed + dx)
    body = ink.blob_pts(x - 10 * s, y - 225 * s, 205 * s, 135 * s, seed, 0.05, 30)
    ink.fill_stroke(cr, body, c, lw=6 * s, amp=3, seed=seed, shadow=cd, shadow_dir=(0, 1),
                    texture="hatch", tex_alpha=0.1)
    for dx in (-140, 60):                                  # near legs
        ink.fill_stroke(cr, [(x + (dx - 34) * s, y - 150 * s), (x + (dx + 34) * s, y - 150 * s),
                             (x + (dx + 32) * s, y), (x + (dx - 32) * s, y)], c,
                        lw=5 * s, amp=1, seed=seed + dx + 1, shadow=cd, shadow_dir=(1, 0))
    hx, hy = x + 190 * s, y - 280 * s
    ink.fill_stroke(cr, ink.blob_pts(hx, hy, 88 * s, 95 * s, seed + 3, 0.08, 18), c, lw=6 * s, amp=2, seed=seed + 3,
                    shadow=cd, shadow_dir=(1, 0.6))
    sw = math.sin(t * 2 * math.pi / 6.0 + seed) * 34 * s
    ink.line(cr, [(hx + 55 * s, hy + 40 * s), (hx + 95 * s + sw * 0.3, hy + 140 * s),
                  (hx + 80 * s + sw, hy + 245 * s), (hx + 50 * s + sw, hy + 265 * s)], lw=38 * s, ink=c, amp=0)
    ink.line(cr, [(hx + 30 * s, hy + 60 * s), (hx + 85 * s, hy + 130 * s), (hx + 170 * s, hy + 120 * s),
                  (hx + 205 * s, hy + 60 * s)], lw=15 * s, ink=rgb("#f1e8d6"), amp=0)
    ink.dot(cr, hx + 30 * s, hy - 15 * s, 7 * s)
    ink.fill_stroke(cr, ink.blob_pts(hx - 45 * s, hy + 10 * s, 40 * s, 60 * s, seed + 4, 0.12, 12), cd,
                    lw=4 * s, amp=1, seed=seed + 4)


def wolf(cr, x, y, s, t, seed):
    """A dog/wolf lying curled by the fire, tail flicking."""
    c = rgb("#8d8479")
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 38 * s, 95 * s, 38 * s, 22), c, lw=5 * s, amp=1.2, seed=seed,
                    shadow=shade(c), shadow_dir=(0, 1))
    ink.fill_stroke(cr, [(x + 70 * s, y - 55 * s), (x + 135 * s, y - 70 * s), (x + 150 * s, y - 45 * s),
                         (x + 120 * s, y - 25 * s), (x + 75 * s, y - 20 * s)], c, lw=5 * s, amp=1, seed=seed + 1)
    ink.fill_stroke(cr, [(x + 95 * s, y - 68 * s), (x + 102 * s, y - 100 * s), (x + 117 * s, y - 72 * s)], c,
                    lw=4 * s, amp=0)
    ink.line(cr, [(x + 125 * s, y - 55 * s), (x + 135 * s, y - 52 * s)], lw=4 * s, amp=0)
    f = math.sin(t * 2 * math.pi / 3.0 + seed) * 20 * s
    ink.line(cr, [(x - 90 * s, y - 40 * s), (x - 140 * s, y - 55 * s + f), (x - 165 * s, y - 30 * s + f)],
             lw=14 * s, ink=c, amp=0)


def sheep(cr, x, y, s, t, seed):
    c = rgb("#f1ede4")
    ink.fill_stroke(cr, ink.blob_pts(x, y - 75 * s, 80 * s, 50 * s, seed, 0.12, 18), c, lw=5 * s, amp=1.5,
                    seed=seed)
    for dx in (-45, -20, 30, 52):
        ink.line(cr, [(x + dx * s, y - 35 * s), (x + dx * s, y)], lw=7 * s, amp=0)
    g = (math.sin(t * 2 * math.pi / 6.0 + seed) + 1) / 2
    ink.fill_stroke(cr, ink.ellipse_pts(x + 85 * s, y - 95 * s + g * 55 * s, 26 * s, 22 * s, 16),
                    rgb("#3c3632"), lw=4 * s, amp=0)


def cow(cr, x, y, s, t, seed):
    c = rgb("#f2ece0")
    ink.fill_stroke(cr, [(x - 110 * s, y - 70 * s), (x - 105 * s, y - 165 * s), (x + 95 * s, y - 170 * s),
                         (x + 110 * s, y - 75 * s)], c, lw=5 * s, amp=1.5, seed=seed)
    for k, (dx, dy) in enumerate(((-50, -130), (30, -110))):
        ink.fill_stroke(cr, ink.blob_pts(x + dx * s, y + dy * s, 30 * s, 22 * s, seed + k, 0.2, 10),
                        rgb("#4a3a30"), lw=0, amp=0)
    for dx in (-90, -60, 70, 95):
        ink.line(cr, [(x + dx * s, y - 72 * s), (x + dx * s, y)], lw=10 * s, amp=0)
    g = (math.sin(t * 2 * math.pi / 8.0 + seed) + 1) / 2
    hx, hy = x + 140 * s, y - 150 * s + g * 90 * s
    ink.fill_stroke(cr, ink.ellipse_pts(hx, hy, 40 * s, 34 * s, 18), c, lw=5 * s, amp=0.8, seed=seed + 4)
    ink.fill_stroke(cr, ink.ellipse_pts(hx + 20 * s, hy + 18 * s, 22 * s, 14 * s, 12), rgb("#e8b7a8"), lw=3 * s,
                    amp=0)
    tail = math.sin(t * 2 * math.pi / 2.5 + seed) * 15 * s
    ink.line(cr, [(x - 110 * s, y - 150 * s), (x - 130 * s + tail, y - 90 * s)], lw=5 * s, amp=0)


def chicken(cr, x, y, s, t, seed):
    c = rgb("#f4efe3")
    peck = max(0.0, math.sin(t * 2 * math.pi / 1.6 + seed)) ** 3
    ink.fill_stroke(cr, ink.ellipse_pts(x, y - 40 * s, 32 * s, 24 * s, 16), c, lw=4 * s, amp=0.8, seed=seed)
    hx, hy = x + 30 * s, y - 62 * s + peck * 40 * s
    ink.fill_stroke(cr, ink.ellipse_pts(hx, hy, 14 * s, 13 * s, 12), c, lw=3.5 * s, amp=0)
    ink.fill_stroke(cr, [(hx + 12 * s, hy), (hx + 26 * s, hy + 4 * s), (hx + 12 * s, hy + 7 * s)], rgb("#e8a23c"),
                    lw=2 * s, amp=0)
    ink.dot(cr, hx, hy - 16 * s, 6 * s, rgb("#d63b2e"))
    for dx in (-8, 8):
        ink.line(cr, [(x + dx * s, y - 18 * s), (x + dx * s, y)], lw=3 * s, ink=rgb("#e8a23c"), amp=0)


def table(cr, x, y, s, t, seed):
    top = y - 110 * s
    ink.fill_stroke(cr, [(x - 190 * s, top), (x + 190 * s, top), (x + 190 * s, top + 22 * s),
                         (x - 190 * s, top + 22 * s)], WOOD, lw=5 * s, amp=0.8, seed=seed,
                    shadow=WOOD_D, shadow_dir=(0, 1))
    for dx in (-165, 165):
        ink.line(cr, [(x + dx * s, top + 22 * s), (x + dx * s, y)], lw=14 * s, ink=WOOD_D, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(x - 60 * s, top - 14 * s, 50 * s, 14 * s, 16), rgb("#a0673e"), lw=4 * s, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(x + 70 * s, top - 18 * s, 44 * s, 22 * s, 16), rgb("#d5a25c"), lw=4 * s,
                    amp=0.6, seed=seed + 2)


def bench(cr, x, y, s, t, seed):
    top = y - 60 * s
    ink.fill_stroke(cr, [(x - 130 * s, top), (x + 130 * s, top), (x + 130 * s, top + 16 * s),
                         (x - 130 * s, top + 16 * s)], WOOD, lw=4.5 * s, amp=0.5, seed=seed)
    for dx in (-110, 110):
        ink.line(cr, [(x + dx * s, top + 16 * s), (x + dx * s, y)], lw=10 * s, ink=WOOD_D, amp=0)


def well(cr, x, y, s, t, seed):
    ink.fill_stroke(cr, [(x - 95 * s, y), (x - 95 * s, y - 110 * s), (x + 95 * s, y - 110 * s), (x + 95 * s, y)],
                    STONE, lw=5 * s, amp=1.2, seed=seed, texture="grain", tex_alpha=0.22, shadow=shade(STONE),
                    shadow_dir=(1, 0))
    for dx in (-80, 80):
        ink.line(cr, [(x + dx * s, y - 110 * s), (x + dx * s, y - 280 * s)], lw=10 * s, ink=WOOD, amp=0)
    ink.fill_stroke(cr, [(x - 130 * s, y - 260 * s), (x, y - 340 * s), (x + 130 * s, y - 260 * s)], rgb("#9a6a3a"),
                    lw=5 * s, amp=1, seed=seed + 1)
    sw = math.sin(t * 1.2 + seed) * 6 * s
    ink.line(cr, [(x, y - 270 * s), (x + sw, y - 190 * s)], lw=2.5 * s, amp=0)
    ink.fill_stroke(cr, [(x - 22 * s + sw, y - 190 * s), (x + 22 * s + sw, y - 190 * s),
                         (x + 18 * s + sw, y - 150 * s), (x - 18 * s + sw, y - 150 * s)], WOOD, lw=4 * s, amp=0)


def cart(cr, x, y, s, t, seed):
    ink.fill_stroke(cr, [(x - 150 * s, y - 70 * s), (x + 150 * s, y - 70 * s), (x + 140 * s, y - 150 * s),
                         (x - 140 * s, y - 150 * s)], WOOD, lw=5 * s, amp=1, seed=seed, shadow=WOOD_D, shadow_dir=(0, 1))
    for dx in (-90, 90):
        ink.fill_stroke(cr, ink.ellipse_pts(x + dx * s, y - 55 * s, 55 * s, 55 * s, 24), rgb("#8a6440"), lw=6 * s,
                        amp=0.5, seed=seed + dx)
        ink.dot(cr, x + dx * s, y - 55 * s, 10 * s)
    ink.line(cr, [(x + 150 * s, y - 100 * s), (x + 290 * s, y - 80 * s)], lw=9 * s, ink=WOOD, amp=0)
    ink.fill_stroke(cr, ink.blob_pts(x, y - 175 * s, 120 * s, 40 * s, seed, 0.2, 14), rgb("#d6b25e"), lw=4 * s,
                    amp=1.5, seed=seed + 3, texture="hatch", tex_alpha=0.15)


def barrel(cr, x, y, s, t, seed):
    c = rgb("#9a6a40")
    ink.fill_stroke(cr, [(x - 50 * s, y), (x - 60 * s, y - 70 * s), (x - 50 * s, y - 140 * s),
                         (x + 50 * s, y - 140 * s), (x + 60 * s, y - 70 * s), (x + 50 * s, y)], c, lw=5 * s,
                    amp=0.6, seed=seed, shadow=shade(c), shadow_dir=(1, 0))
    for yy in (-30, -110):
        ink.line(cr, [(x - 56 * s, y + yy * s), (x + 56 * s, y + yy * s)], lw=5 * s, ink=rgb("#4e4a45"), amp=0)


def canoe(cr, x, y, s, t, seed):
    c = rgb("#8a5e36")
    bob = math.sin(t * 2 * math.pi / 4.0 + seed) * 4 * s
    ink.fill_stroke(cr, [(x - 190 * s, y - 50 * s + bob), (x + 190 * s, y - 50 * s + bob),
                         (x + 130 * s, y - 5 * s + bob), (x - 130 * s, y - 5 * s + bob)], c, lw=5 * s, amp=1,
                    seed=seed, shadow=shade(c), shadow_dir=(0, 1))


def wheat(cr, x, y, s, t, seed):
    r = random.Random(seed)
    for k in range(14):
        dx = r.uniform(-110, 110) * s
        h = r.uniform(110, 170) * s
        sway = math.sin(t * 0.8 + dx * 0.02) * 10 * s
        ink.line(cr, [(x + dx, y), (x + dx + sway, y - h)], lw=3.5 * s, ink=rgb("#b99a4a"), amp=0)
        ink.fill_stroke(cr, ink.ellipse_pts(x + dx + sway, y - h - 16 * s, 7 * s, 20 * s, 10), rgb("#e3c270"),
                        lw=2.5 * s, amp=0)


def cave_painting(cr, x, y, s, t, seed):
    """Ochre animals on the cave wall, roughly at eye height."""
    c = rgb("#b5552e", 0.85)
    cy = y - 330 * s
    for k, dx in enumerate((-120, 60)):
        ink.fill_stroke(cr, ink.ellipse_pts(x + dx * s, cy, 60 * s, 26 * s, 16), c, lw=0, amp=1.5, seed=seed + k)
        for lx in (-35, -15, 20, 40):
            ink.line(cr, [(x + (dx + lx) * s, cy + 18 * s), (x + (dx + lx) * s, cy + 55 * s)], lw=6 * s, ink=c, amp=0)
        ink.line(cr, [(x + (dx + 55) * s, cy - 10 * s), (x + (dx + 85) * s, cy - 30 * s)], lw=14 * s, ink=c, amp=0)
    for k in range(3):
        ink.fill_stroke(cr, ink.blob_pts(x + (140 + k * 38) * s, cy + 20 * s, 14 * s, 18 * s, seed + 9 + k, 0.2, 10),
                        rgb("#8e3d22", 0.8), lw=0, amp=0)


def stones(cr, x, y, s, t, seed):
    """A little pile of flint and stone tools on the ground."""
    r = random.Random(seed)
    for k in range(5):
        ink.fill_stroke(cr, ink.blob_pts(x + r.uniform(-50, 50) * s, y - 12 * s, 18 * s, 10 * s, seed + k, 0.25, 8),
                        ink.mix(STONE, rgb("#5f6b73"), r.random()), lw=3 * s, amp=0)


def basket(cr, x, y, s, t, seed):
    c = rgb("#b88a4d")
    ink.fill_stroke(cr, [(x - 60 * s, y - 80 * s), (x + 60 * s, y - 80 * s), (x + 45 * s, y), (x - 45 * s, y)], c,
                    lw=4.5 * s, amp=0.8, seed=seed, texture="hatch", tex_alpha=0.28, shadow=shade(c), shadow_dir=(1, 0))
    r = random.Random(seed)
    for k in range(6):
        ink.dot(cr, x + r.uniform(-40, 40) * s, y - 82 * s - r.uniform(0, 12) * s, 10 * s,
                r.choice([rgb("#b0334a"), rgb("#6a3a6a"), rgb("#d98a3a")]))


def fish_rack(cr, x, y, s, t, seed):
    for dx in (-90, 90):
        ink.line(cr, [(x + dx * s, y), (x + dx * s, y - 170 * s)], lw=7 * s, ink=WOOD, amp=0)
    ink.line(cr, [(x - 100 * s, y - 165 * s), (x + 100 * s, y - 165 * s)], lw=6 * s, ink=WOOD, amp=0)
    for k in range(4):
        fx = x + (-60 + k * 40) * s
        sw = math.sin(t * 0.9 + k) * 4 * s
        ink.line(cr, [(fx, y - 165 * s), (fx + sw, y - 140 * s)], lw=2 * s, amp=0)
        ink.fill_stroke(cr, ink.ellipse_pts(fx + sw, y - 105 * s, 12 * s, 36 * s, 14), rgb("#9fb2b8"), lw=3 * s, amp=0)


def bed(cr, x, y, s, t, seed):
    """A straw-stuffed bed with a wool blanket (medieval interiors)."""
    ink.fill_stroke(cr, [(x - 190 * s, y), (x - 190 * s, y - 70 * s), (x + 190 * s, y - 70 * s), (x + 190 * s, y)],
                    WOOD, lw=5 * s, amp=0.6, seed=seed)
    c = rgb("#8c6d9e")
    ink.fill_stroke(cr, [(x - 170 * s, y - 70 * s), (x - 160 * s, y - 115 * s), (x + 175 * s, y - 110 * s),
                         (x + 180 * s, y - 70 * s)], c, lw=4.5 * s, amp=1.5, seed=seed + 1, shadow=shade(c),
                    shadow_dir=(0, 1))


@dataclass(frozen=True)
class Prop:
    draw: object
    width: float                 # footprint on the ground at scale 1 (px)
    layer: str                   # back | mid | front
    eras: tuple
    living: bool = False
    light: bool = False          # casts firelight at night
    height: float = 200.0        # rough height at scale 1 (for light position)
    base: object = None          # the part that never moves, drawn once per scene


BOTH = ("stone_age", "medieval")
STONE_AGE = ("stone_age",)
MEDIEVAL = ("medieval",)

PROPS = {
    "campfire": Prop(campfire, 220, "mid", BOTH, living=True, light=True, height=90, base=campfire_base),
    "hearth": Prop(hearth, 300, "back", MEDIEVAL, living=True, light=True, height=110, base=hearth_base),
    "torch": Prop(torch_wall, 60, "back", BOTH, living=True, light=True, height=260, base=torch_base),
    "candle": Prop(candle, 90, "front", MEDIEVAL, living=True, light=True, height=125, base=candle_base),
    "cauldron": Prop(cauldron, 160, "mid", BOTH, living=True, light=True, height=40, base=cauldron_base),
    "pot": Prop(pot, 130, "mid", BOTH, base=pot_base),
    "tent": Prop(tent, 360, "back", STONE_AGE),
    "hut": Prop(hut, 390, "back", BOTH),
    "cottage": Prop(cottage, 470, "back", MEDIEVAL, base=cottage_base),
    "tree": Prop(tree, 300, "back", BOTH),
    "pine": Prop(pine, 280, "back", BOTH),
    "bush": Prop(bush, 190, "mid", BOTH),
    "rock": Prop(rock, 200, "mid", BOTH),
    "reeds": Prop(reeds, 150, "front", BOTH),
    "woodpile": Prop(woodpile, 180, "mid", BOTH),
    "bedroll": Prop(bedroll, 320, "mid", STONE_AGE),
    "hide_rack": Prop(hide_rack, 240, "back", STONE_AGE),
    "deer": Prop(deer, 280, "back", BOTH),
    "mammoth": Prop(mammoth, 520, "back", STONE_AGE),
    "wolf": Prop(wolf, 330, "mid", STONE_AGE),
    "dog": Prop(wolf, 330, "mid", MEDIEVAL),
    "sheep": Prop(sheep, 200, "mid", MEDIEVAL),
    "cow": Prop(cow, 330, "back", MEDIEVAL),
    "chicken": Prop(chicken, 90, "front", MEDIEVAL),
    "table": Prop(table, 400, "mid", MEDIEVAL),
    "bench": Prop(bench, 280, "mid", MEDIEVAL),
    "well": Prop(well, 280, "back", MEDIEVAL),
    "cart": Prop(cart, 460, "back", MEDIEVAL),
    "barrel": Prop(barrel, 130, "mid", MEDIEVAL),
    "canoe": Prop(canoe, 400, "mid", STONE_AGE),
    "wheat": Prop(wheat, 240, "front", MEDIEVAL),
    "cave_painting": Prop(cave_painting, 360, "back", STONE_AGE),
    "stones": Prop(stones, 120, "front", STONE_AGE),
    "basket": Prop(basket, 130, "front", BOTH),
    "fish_rack": Prop(fish_rack, 220, "back", STONE_AGE),
    "bed": Prop(bed, 400, "mid", MEDIEVAL),
}
