"""SUBJECT SCENES — the illustrated arm drawn the way the reference is drawn.

Operator, 2026-09-23, on the first illustrated previews (columns, a ridge and
a tank in a pretty world): *"you're not getting it ... This is something real.
It has vibes. It has feelings. It's not just a chart on a gradient
background. You need to be far more throwing the mascot on top of this video
than trying to drag this video into what we already have."*

The reference (`docs/style_samples/illustrated_2d/sample_a.py`) has no chart
in it anywhere. Everest IS a mountain and it drops into the trench; the
moonwalkers ARE astronauts popping onto the Moon; depth IS a submarine
sinking while a readout counts. The number is a caption on the scene, and the
scene is the subject.

So a subject scene is `scene(cr, t, u, pts, host)`:
  * `t` seconds since the beat began, `u` the beat's progress 0..1;
  * `pts` the beat's sourced data, [(label, value), ...] — every number drawn
    comes from here or is arithmetic on it (a difference, a share);
  * `host(role, x, foot_y, height)` puts Data IN the scene, acting.

The kit below is the reference's own vocabulary, vertical (1080x1920):
layered gradients, two-tone forms with a lit and a shadow face, rim light,
soft glows, drifting ambient life, Anton for the big numbers and Inter for
labels, dips to black between beats. Colours come from `look.SCENES`.
"""
from __future__ import annotations

import math
import random

import cairo

from shared import look
from data_learning import illustrated as I
from data_learning.illustrated import W, H, clamp, ease, pop, seg, glow, text, _c
from data_learning.illustrated import (solid, box, cylinder, disc, contact_shadow,  # noqa: F401 — the light kit
                                       haze, vignette, edge, KEY, FINISHES)

P = look.SCENES


def vgrad(cr, stops, y0=0, y1=H, x0=0, x1=W):
    """Fill x0..x1, y0..y1 with a top-to-bottom gradient. `stops` is
    [(position 0..1, rgb), ...], or plain [rgb, ...] spaced evenly."""
    I.vgrad(cr, stops, y0, y1, x0, x1)


def by_time(rows):
    """Rows in TIME order, by the year in each label — never by list order.
    The renderer may hand a beat its items newest-first, and a scene that
    trusted the order chalked last year's price in as the new one ("0.5x in
    twelve months" over a price that had doubled)."""
    import re as _re

    def key(r):
        m = _re.search(r"(1[6-9]|20)\d{2}", str(r[0]))
        return (0, int(m.group(0))) if m else (1, 0)
    if all(key(r)[0] == 0 for r in rows):
        return sorted(rows, key=key)
    return list(rows)


def step_through(u, n, hold_first=0.28, hold_last=0.4):
    """(k, f): item k of a sequence is ARRIVING, f its progress 0..1.

    The FIRST item holds the opening stretch and the LAST the closing one —
    the last 40% of the beat, so the finished picture is up long enough to
    read (operator, 2026-10-07: a payoff held under a second was
    "whiplash"; scene_author.PAYOFF_BY).
    The showrunner looks at each beat at 25%, 55% and 85% of it; stepped
    evenly, a seven-year series showed it 2020 first while the narration
    said 2019, and the judge called the scene a contradiction (coffee,
    2026-09-23). Now the first frame it sees is the first year."""
    if n <= 1:
        return 0, clamp(u / max(1e-6, hold_first))
    if u < hold_first:
        return 0, u / hold_first
    pos = (u - hold_first) / max(1e-6, 1 - hold_first - hold_last) * (n - 1)
    if pos >= n - 1:
        return n - 1, 1.0
    k = int(pos) + 1
    return k, pos - (k - 1)


#: A readout shows at most this many of a series' points in one beat: the
#: first, the last, and evenly spaced ones between. Eight years stepped
#: through a six-second beat put a new number up every quarter second — the
#: picture may glide through every year, the reader cannot.
READOUT_SHOWS = 3


def landed(rows, k, f, at=0.6, shows=READOUT_SHOWS):
    """The (label, value) a READOUT may print: the item that has arrived.

    A readout that counts up between two data points and wears the second
    one's label prints a number the data does not have — "$3.24 · February
    2025", when February 2025 was $4.41. The picture may glide; the number
    only ever shows a data point — and only `shows` of them in a beat (the
    first, the last, evenly spaced between), so each stays up to be read."""
    n = len(rows)
    got = k if (k == 0 or f >= at) else k - 1
    if n <= shows:
        return rows[got]
    keep = sorted({round(i * (n - 1) / (shows - 1)) for i in range(shows)})
    return rows[max(i for i in keep if i <= got)]


def fit_readout(cr, big, small, x, y, anchor="left", a=1.0, rgb=None,
                size=120, max_w=W - 120):
    """The reference's readout: a big Anton number, a small Inter line."""
    sz = I.fit_size(cr, big, size, max_w, "display")
    text(cr, big, x, y, sz, rgb or P["readout"], face="display", anchor=anchor,
         alpha=a)
    if small:
        ss = I.fit_size(cr, small, 38, max_w, "bold", 24)
        text(cr, small, x + (4 if anchor == "left" else 0), y + ss + 22, ss,
             look.INK, face="text", anchor=anchor, alpha=a)


# ------------------------------------------------------------------ props --

_R = random.Random(5)
_TREES = [(_R.uniform(-40, W + 40), _R.uniform(0, 1), _R.uniform(0.75, 1.25))
          for _ in range(64)]


def tree(cr, x, base, s, lit, shade, trunk, lean=0.0, a=1.0):
    """A rainforest tree: a trunk and a two-tone crown of three lobes.
    `lean` 0..1 topples it (radians = lean * 1.45)."""
    if s <= 0.02 or a <= 0.0:
        return
    cr.save()
    cr.translate(x, base)
    cr.rotate(lean * 1.45)
    cr.scale(s, s)
    cr.rectangle(-7, -120, 14, 120)
    solid(cr, trunk, a=a, rim=False)
    for dx, dy, r, col in ((-34, -128, 44, shade), (32, -132, 46, shade),
                           (0, -170, 56, lit), (-20, -140, 40, lit)):
        disc(cr, dx, dy, r, col, a=a)
    cr.restore()


def stump(cr, x, base, s):
    cr.set_source_rgba(*_c(P["stump"]))
    cr.rectangle(x - 9 * s, base - 16 * s, 18 * s, 16 * s)
    cr.fill()
    cr.set_source_rgba(*_c(P["stump_top"]))
    cr.save()
    cr.translate(x, base - 16 * s)
    cr.scale(1, 0.35)
    cr.arc(0, 0, 9 * s, 0, 2 * math.pi)
    cr.restore()
    cr.fill()


def cow(cr, x, y, s, t, a=1.0):
    """A grazing cow in two tones; its head dips to graze."""
    if s <= 0.02 or a <= 0.0:
        return
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    body, patch, dark = P["cow"], P["cow_patch"], P["cow_dark"]
    for lx in (-26, -12, 14, 28):
        cr.set_source_rgba(*_c(dark, a))
        cr.rectangle(lx - 4, 8, 8, 26)
        cr.fill()
    cr.save()
    cr.scale(1, 0.6)
    cr.arc(0, 0, 40, 0, 2 * math.pi)
    cr.restore()
    solid(cr, body, a=a)
    cr.set_source_rgba(*_c(patch, a))
    cr.arc(-12, -6, 12, 0, 2 * math.pi)
    cr.fill()
    cr.arc(16, 4, 9, 0, 2 * math.pi)
    cr.fill()
    dip = 10 * (0.5 + 0.5 * math.sin(t * 2.2 + x))
    disc(cr, 44, -4 + dip, 15, body, a=a)
    cr.set_source_rgba(*_c(dark, a))
    cr.arc(52, 0 + dip, 5, 0, 2 * math.pi)
    cr.fill()
    cr.restore()


def truck(cr, x, y, s, a=1.0):
    if s <= 0.02 or a <= 0.0:
        return
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    contact_shadow(cr, 0, 8, 120, a=0.35 * a)
    cr.rectangle(-50, -34, 70, 34)
    solid(cr, P["truck"], a=a)
    cr.rectangle(20, -26, 30, 26)
    solid(cr, P["truck_cab"], finish="gloss", a=a)
    for k in range(3):
        disc(cr, -40 + k * 22, -40, 11, P["log"], a=a)
    for wx in (-34, 0, 34):
        disc(cr, wx, 2, 9, P["cow_dark"], a=a)
    cr.restore()



# ---------------------------------------------------------------- THE SHOT ---
# Operator, 2026-10-07, on a flat front-on barn over an empty field: "still
# very much lacking" — then, on the same beat drawn as a SHOT (a low sun, hills
# fading into the distance, the barn in three-quarter view, hens right by the
# camera): "ok now we are talking". These are the pieces of that shot, so
# every scene can start from it instead of from a gradient.

#: The setting's colours, far to near: sky top, sky mid, sky at the horizon,
#: far ridge, near ridge, ground near the horizon, ground at the camera.
SETTINGS = {
    "field":  [(108, 150, 196), (186, 200, 210), (248, 212, 166), (170, 182, 176),
               (138, 160, 128), (150, 168, 84), (74, 104, 46)],
    "desert": [(112, 156, 204), (196, 210, 220), (250, 220, 176), (196, 168, 138),
               (204, 160, 112), (226, 190, 132), (176, 128, 80)],
    "snow":   [(96, 140, 190), (178, 196, 216), (236, 222, 214), (176, 190, 206),
               (210, 220, 232), (226, 232, 240), (176, 190, 210)],
    "coast":  [(100, 150, 200), (182, 204, 220), (248, 214, 172), (160, 178, 188),
               (64, 124, 160), (226, 204, 156), (196, 168, 118)],
    "town":   [(104, 146, 194), (184, 198, 212), (246, 210, 168), (150, 156, 170),
               (118, 124, 138), (188, 172, 150), (128, 112, 96)],
}
SUN = (230, 760)         # the low sun, upper left: where KEY comes from


def ridge(cr, base, amp, seed=0.0, n=5):
    """Trace (do not fill) a soft hill line `amp` px above `base`, closed down
    to the bottom of the frame — then solid(..., edge=False) it."""
    cr.move_to(0, H)
    cr.line_to(0, base)
    step = W / n
    for i in range(n):
        x0 = i * step
        y1 = base - amp * (0.6 + 0.4 * math.sin(i * 1.7 + seed))
        cr.curve_to(x0 + step * 0.3, y1, x0 + step * 0.7, y1,
                    x0 + step, base - amp * 0.3 * math.cos(i + seed))
    cr.line_to(W, H)
    cr.close_path()


def treeline(cr, y, rgb, n=14, seed=0):
    """A band of rounded tree crowns standing on y, edge to edge."""
    for i in range(n):
        k = i * 37 + seed * 11
        x, r = 20 + i * (W / n) + k % 30, 34 + (k * 13) % 18
        yy = y - k % 40
        for dx, dy, rr in ((0, 0, 1), (-0.6, 0.25, 0.75), (0.6, 0.2, 0.8),
                           (0, -0.45, 0.7)):
            cr.arc(x + dx * r, yy + dy * r, r * rr, 0, 2 * math.pi)
            cr.new_sub_path()
    solid(cr, rgb, edge=False)


def landscape(cr, t=0.0, kind="field", horizon=1170):
    """Paints a whole outdoor setting (kind: field, desert, snow, coast,
    town) under a low sun; returns the ground's top y.

    Far to near: sky, sun, clouds, two ridges under haze, ground whose
    stripes run to the horizon."""
    sky0, sky1, sky2, far, near, g0, g1 = SETTINGS.get(kind, SETTINGS["field"])
    vgrad(cr, [(0, sky0), (0.45, sky1), (0.8, sky2), (1, sky2)], 0, horizon + 20)
    glow(cr, SUN[0], SUN[1], 520, (255, 236, 196), 0.55)
    glow(cr, SUN[0], SUN[1], 140, (255, 250, 232), 0.9)
    for cx, cy, s in ((760, 380, 1.0), (300, 520, 0.7), (930, 640, 0.6)):
        cx = (cx + t * 6 * s) % (W + 300) - 150      # clouds drift slowly
        for dx, r in ((-80, 60), (0, 85), (90, 65), (170, 45)):
            cr.save()
            cr.translate(cx + dx * s, cy)
            cr.scale(1, 0.55)
            cr.arc(0, 0, r * s, 0, 2 * math.pi)
            cr.restore()
        cr.set_source_rgba(1, 0.98, 0.95, 0.55)
        cr.fill()
    ridge(cr, horizon - 60, 90, 0.3, 4)
    solid(cr, far, edge=False, rim=False)
    if kind == "town":                                # a far skyline
        for i in range(16):
            bw, bh = 40 + (i * 29) % 40, 60 + (i * 53) % 140
            cr.rectangle(i * 70 - 10, horizon - 20 - bh, bw, bh + 20)
        solid(cr, near, edge=False, rim=False)
    else:
        ridge(cr, horizon - 20, 70, 2.1, 5)
        solid(cr, near, edge=False, rim=False)
    if kind == "field":
        treeline(cr, horizon - 20, _mix3(near, (40, 70, 40), 0.35))
    haze(cr, horizon - 170, horizon + 30, sky2, a=0.45)
    if kind == "coast":                               # the sea, then the beach
        vgrad(cr, [(0, (96, 150, 180)), (1, (48, 104, 140))], horizon, horizon + 160)
        horizon += 160
    vgrad(cr, [(0, g0), (0.4, _mix3(g0, g1, 0.4)), (1, g1)], horizon, H)
    vx = W / 2
    for k in range(-9, 10):                          # stripes run to the horizon
        cr.move_to(vx + k * 40, horizon)
        cr.line_to(vx + k * 420, H)
        cr.line_to(vx + k * 420 + 210, H)
        cr.line_to(vx + k * 40 + 20, horizon)
        cr.close_path()
        cr.set_source_rgba(1, 1, 0.85, 0.05 if k % 2 else 0.0)
        cr.fill()
    return horizon


def _mix3(a, b, f):
    return tuple(int(x + (y - x) * f) for x, y in zip(a, b))


def foreground(cr, kind="field", y0=1560):
    """Things right by the camera, from y0 to the bottom: grass tufts on a
    field, pebbles on desert/coast/town, drifts on snow. Paint it after the
    hero and before vignette()."""
    for i in range(40):
        gx, gy = (i * 137) % W, y0 + (i * 71) % (H - y0 - 20)
        sh = 0.6 + 0.6 * (gy - y0) / max(1, H - y0)
        if kind == "field":
            for b in (-1, 0, 1):
                cr.move_to(gx, gy)
                cr.curve_to(gx + b * 6 * sh, gy - 14 * sh, gx + b * 10 * sh,
                            gy - 22 * sh, gx + b * 14 * sh, gy - 30 * sh)
            cr.set_source_rgba(*_c((60, 92, 38), 0.8))
            cr.set_line_width(3 * sh)
            cr.stroke()
        elif kind == "snow":
            cr.save()
            cr.translate(gx, gy)
            cr.scale(1, 0.3)
            cr.arc(0, 0, 40 * sh, math.pi, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.fill()
        else:
            cr.save()
            cr.translate(gx, gy)
            cr.scale(1, 0.6)
            cr.arc(0, 0, 7 * sh, 0, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(*_c((90, 70, 52), 0.55))
            cr.fill()


def cast_shadow(cr, x0, x1, y, length=300, a=0.3):
    """The long shadow a thing standing on x0..x1 at ground y throws to the
    lower right, away from the low sun. Draw it before the thing."""
    cr.move_to(x0, y)
    cr.line_to(x1, y)
    cr.line_to(x1 + length, y + length * 0.18)
    cr.line_to(x0 + length * 0.5, y + length * 0.22)
    cr.close_path()
    cr.set_source_rgba(0.08, 0.10, 0.04, a)
    cr.fill()


def building(cr, x0, x1, base, wall_h, rgb, roof_rgb=(96, 102, 114),
             roof="gable", depth=None, boards=True):
    """Three-quarter building, front face x0..x1 on base; returns the front's
    {"x0","x1","top","base","peak"} for doors and signs. roof: gable/gambrel/flat.

    The side wall runs back to the right in shadow, the roof is lit, and it
    throws its own long shadow."""
    d = (x1 - x0) * 0.62 if depth is None else depth
    top = base - wall_h
    sx, sb, st = x1 + d, base - d * 0.26, top + d * 0.06
    rx = (x0 + x1) / 2
    rise = {"gable": 0.5, "gambrel": 0.58, "flat": 0.0}.get(roof, 0.5) * (x1 - x0)
    shade = _mix3(rgb, (20, 10, 10), 0.38)
    cast_shadow(cr, x1, sx, base, length=320)
    contact_shadow(cr, (x0 + sx) / 2, base + 6, (sx - x0) * 1.05, a=0.45)
    cr.move_to(x1, base)                              # side wall
    cr.line_to(sx, sb)
    cr.line_to(sx, st)
    cr.line_to(x1, top)
    cr.close_path()
    solid(cr, shade, rim=False)
    if boards:
        cr.save()
        cr.move_to(x1, base)
        cr.line_to(sx, sb)
        cr.line_to(sx, st)
        cr.line_to(x1, top)
        cr.clip()
        for k in range(1, 14):
            f = k / 14
            cr.move_to(x1 + d * f, top + (st - top) * f)
            cr.line_to(x1 + d * f, base + (sb - base) * f)
        cr.set_source_rgba(0, 0, 0, 0.18)
        cr.set_line_width(2)
        cr.stroke()
        cr.restore()
    if rise:                                          # the roof's long side
        cr.move_to(x1 + 26, top + 6)
        cr.line_to(sx + 22, st + 4)
        cr.line_to(sx - 40 - (x1 - x0) * 0.1, st - rise * 0.5)
        cr.line_to(rx + (x1 - rx) * 0.4, top - rise * 0.62)
        cr.close_path()
        solid(cr, roof_rgb, finish="metal")
        cr.move_to(rx + (x1 - rx) * 0.4, top - rise * 0.62)
        cr.line_to(sx - 40 - (x1 - x0) * 0.1, st - rise * 0.5)
        cr.line_to(sx - (x1 - x0) * 0.4, st - rise * 0.8)
        cr.line_to(rx, top - rise)
        cr.close_path()
        solid(cr, _mix3(roof_rgb, (255, 255, 255), 0.18), finish="metal")
    else:
        cr.move_to(x0, top)
        cr.line_to(x1, top)
        cr.line_to(sx, st)
        cr.line_to(sx - (x1 - x0) * 0.2, st - 30)
        cr.line_to(x0 + 20, top - 30)
        cr.close_path()
        solid(cr, roof_rgb)

    def front():
        cr.move_to(x0, base)
        cr.line_to(x1, base)
        cr.line_to(x1, top)
        if roof == "gambrel":
            cr.line_to(x1 - (x1 - x0) * 0.12, top - rise * 0.62)
            cr.line_to(rx, top - rise)
            cr.line_to(x0 + (x1 - x0) * 0.12, top - rise * 0.62)
        elif rise:
            cr.line_to(rx, top - rise)
        cr.line_to(x0, top)
        cr.close_path()
    front()
    solid(cr, rgb)
    cr.save()
    front()
    cr.clip()
    if boards:
        for x in range(int(x0) + 28, int(x1), 28):
            cr.move_to(x, top - rise - 10)
            cr.line_to(x, base)
        cr.set_source_rgba(0, 0, 0, 0.16)
        cr.set_line_width(2)
        cr.stroke()
    g = cairo.LinearGradient(x0, top - rise, x1, base)   # the sun on the face
    g.add_color_stop_rgba(0, 1, 0.9, 0.7, 0.28)
    g.add_color_stop_rgba(1, 1, 0.9, 0.7, 0)
    cr.set_source(g)
    cr.paint()
    cr.restore()
    if rise:                                          # eave trim
        cr.move_to(x0 - 20, top + 10)
        if roof == "gambrel":
            cr.line_to(x0 + (x1 - x0) * 0.1, top - rise * 0.64)
            cr.line_to(rx, top - rise - 12)
            cr.line_to(x1 - (x1 - x0) * 0.1, top - rise * 0.64)
        else:
            cr.line_to(rx, top - rise - 12)
        cr.line_to(x1 + 20, top + 10)
        cr.set_source_rgba(*_c((240, 234, 222)))
        cr.set_line_width(14)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()
    return {"x0": x0, "x1": x1, "top": top, "base": base, "peak": top - rise}


def hen(cr, x, y, s, t, i=0, flip=False):
    """A white hen standing at (x, y), s ~1 is 60px tall, pecking now and
    then (i staggers the peck), with its long shadow."""
    peck = max(0.0, math.sin(t * 2.4 + i * 1.9)) ** 3
    cr.save()
    cr.translate(x + 30 * s, y + 18 * s)
    cr.scale(1.0, 0.28)
    cr.arc(0, 0, 46 * s, 0, 2 * math.pi)
    cr.restore()
    cr.set_source_rgba(0.12, 0.10, 0.06, 0.28)
    cr.fill()
    cr.save()
    cr.translate(x, y)
    cr.scale(-1 if flip else 1, 1)
    cr.set_source_rgba(*_c((214, 150, 50)))
    cr.set_line_width(4 * s)
    for lx in (-8, 8):
        cr.move_to(lx * s, 6 * s)
        cr.line_to(lx * s, 20 * s)
        cr.stroke()
    cr.move_to(-22 * s, -10 * s)                      # tail
    cr.curve_to(-46 * s, -30 * s, -44 * s, -54 * s, -30 * s, -50 * s)
    cr.curve_to(-26 * s, -30 * s, -16 * s, -22 * s, -10 * s, -14 * s)
    cr.close_path()
    solid(cr, (236, 230, 220), edge=False)
    for k in range(2):                                # body, then its lift
        cr.move_to(-26 * s, -12 * s)
        cr.curve_to(-30 * s, 14 * s, 18 * s, 18 * s, 26 * s, -6 * s)
        cr.curve_to(30 * s, -22 * s, 10 * s, -30 * s, -6 * s, -24 * s)
        cr.close_path()
        if k == 0:
            solid(cr, (252, 250, 244), edge=False)
        else:   # white feathers stay white in shade: lift the shadow face
            cr.set_source_rgba(1, 1, 1, 0.32)
            cr.fill()
    cr.move_to(-14 * s, -10 * s)                      # wing
    cr.curve_to(-8 * s, 6 * s, 10 * s, 6 * s, 14 * s, -4 * s)
    cr.curve_to(4 * s, -8 * s, -6 * s, -12 * s, -14 * s, -10 * s)
    cr.close_path()
    solid(cr, (234, 228, 216), edge=False, rim=False)
    hx, hy = 24 * s + 6 * s * peck, -30 * s + 30 * s * peck
    cr.move_to(10 * s, -22 * s)                       # neck
    cr.line_to(hx - 6 * s, hy + 4 * s)
    cr.line_to(hx + 6 * s, hy + 8 * s)
    cr.line_to(22 * s, -8 * s)
    cr.close_path()
    solid(cr, (250, 248, 240), edge=False, rim=False)
    cr.arc(hx, hy, 10 * s, 0, 2 * math.pi)
    solid(cr, (252, 250, 244), edge=False)
    cr.move_to(hx - 7 * s, hy - 7 * s)                # comb
    for k in range(3):
        cr.curve_to(hx - 6 * s + k * 5 * s, hy - 19 * s, hx - 2 * s + k * 5 * s,
                    hy - 19 * s, hx - 1 * s + k * 5 * s, hy - 8 * s)
    cr.close_path()
    solid(cr, (210, 40, 36), edge=False, rim=False)
    cr.move_to(hx + 8 * s, hy - 2 * s)                # beak
    cr.line_to(hx + 18 * s, hy + 2 * s)
    cr.line_to(hx + 8 * s, hy + 5 * s)
    cr.close_path()
    solid(cr, (236, 170, 50), edge=False, rim=False)
    cr.arc(hx + 3 * s, hy - 2 * s, 1.8 * s, 0, 2 * math.pi)
    cr.set_source_rgba(0.08, 0.08, 0.1, 1)
    cr.fill()
    cr.restore()


# ------------------------------------------------------- SCALE IN THE SHOT ---
# Operator, 2026-10-07, on a bar strip laid over the top of the frame: "boxes
# on top of the video doesn't help ... it just needs to be able to more
# easily glance at it and gauge the scale." The scale belongs ON the subject:
# where it used to reach, how big it used to be, how many times over it is.

def then_mark(cr, x0, x1, y, label, a=1.0):
    """Mark ON the subject where an earlier value reached: a dashed line from
    x0 to x1 at y, `label` (its year, say) at the right end. Draw it after
    the subject; returns the label's (x0, y0, x1, y1) box."""
    cr.save()
    cr.set_dash([18, 12])
    cr.set_line_width(5)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_source_rgba(0.05, 0.06, 0.12, 0.55 * a)        # its dark keyline
    cr.move_to(x0, y + 2)
    cr.line_to(x1, y + 2)
    cr.stroke()
    cr.set_source_rgba(*_c(look.INK, a))
    cr.move_to(x0, y)
    cr.line_to(x1, y)
    cr.stroke()
    cr.restore()
    return text(cr, str(label), x1 + 14, y + 13, 36, look.INK, face="bold", alpha=a)


def ghost(cr, a=0.9):
    """Stroke the CURRENT PATH as a dashed white outline and consume it: the
    earlier size drawn where it stood, beside or inside the current one, so
    the growth reads in one look."""
    cr.save()
    cr.set_dash([16, 10])
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    path = cr.copy_path()
    cr.set_line_width(8)
    cr.set_source_rgba(0.05, 0.06, 0.12, 0.45 * a)
    cr.stroke()
    cr.append_path(path)
    cr.set_line_width(4)
    cr.set_source_rgba(*_c(look.INK, a))
    cr.stroke()
    cr.restore()


def times_ticks(cr, x, base, unit_h, n, a=1.0):
    """Ticks up from `base` every `unit_h` px labelled 1x, 2x ... nx, at x:
    the subject measured in its own earlier size. unit_h is the earlier
    value's height in your drawing; n = ceil(new / old)."""
    for k in range(1, int(n) + 1):
        y = base - k * unit_h
        cr.set_source_rgba(*_c(look.INK, a))
        cr.set_line_width(5)
        cr.move_to(x - 18, y)
        cr.line_to(x + 18, y)
        cr.stroke()
        text(cr, f"{k}x", x + 28, y + 12, 34, look.INK, face="bold", alpha=a)

#: France, coarse on purpose (lon, lat) — the hexagone, same register as
#: `data_learning/continents.py`.
FRANCE = [(-4.8, 48.4), (-1.8, 48.6), (-1.3, 49.7), (1.6, 50.9), (2.6, 51.1),
          (4.2, 50.0), (6.4, 49.5), (8.2, 49.0), (7.6, 47.6), (6.9, 46.4),
          (7.0, 45.9), (6.6, 45.1), (7.6, 43.8), (6.2, 43.1), (4.8, 43.4),
          (3.1, 43.1), (3.2, 42.4), (1.7, 42.5), (-1.8, 43.4), (-1.2, 44.6),
          (-1.1, 46.0), (-2.2, 47.1), (-4.4, 47.8)]


def shape_path(cr, pts, cx, cy, width):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    sx = width / (max(xs) - min(xs))
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    for k, (lx, ly) in enumerate(pts):
        X = cx + (lx - mx) * sx
        Y = cy - (ly - my) * sx * 1.35
        (cr.move_to if k == 0 else cr.line_to)(X, Y)
    cr.close_path()


PACE_AMP = 110.0         # px each way
PACE_PERIOD = 3.4        # seconds per walk there and back


def stride(t: float) -> float:
    """Data PACES while he presents: a steady walk back and forth along the
    scene. The one mover big and sharp enough to register at the gate's
    scale — a high-contrast 230px figure moving ~9px a frame — where every
    finished scene with a still host measured 40-96% held frames."""
    return PACE_AMP * (2 / math.pi) * math.asin(math.sin(2 * math.pi * t / PACE_PERIOD))


STEP_BOB = 40.0          # px: the top of each step's lift
#: Data's centre never comes closer to a frame edge than this: at 230px tall
#: his reach is ~110px either side, and at 70 his pointing hand was clipped
#: by the frame (showrunner, 2026-09-23).
EDGE = 130


def walk(x, fy, t, amp=PACE_AMP):
    """Where Data actually stands at time t when he paces around (x, fy).

    Two things the plain stride got wrong, both measured with the gate's
    detector over every teacher (71 held frames in 6.8s of each):
      * a sine walk STOPS at each end. For one sampled frame every 1.7s he
        was the only mover and he was still. Each step now lifts him, and
        the lift is fastest exactly where the walk turns.
      * a walk centred near the edge was CLAMPED against it, so he stood
        pinned for part of every cycle. The centre now moves inward so the
        whole swing fits the frame.
    Anything a scene draws in his hand must use this position too."""
    cx = clamp(x, EDGE + amp, W - EDGE - amp)
    w = 2 * math.pi * t / PACE_PERIOD
    # A CONSTANT-SPEED walk that turns sharply (a triangle wave), not a sine:
    # a sine spends a third of each stride crawling into its turn, and in the
    # real render — Data's pose changing only every other frame — those were
    # held frames at the gate (measured on the render clock, 2026-09-23).
    tri = (2 / math.pi) * math.asin(math.sin(w))
    return cx + amp * tri, fy - STEP_BOB * (0.5 + 0.5 * math.sin(2 * w))


# ONE VIDEO, NO REPEATED GESTURE. A role ("shock", "cheer") resolves to an
# animator by hashing the beat's topic, over pools of two to four. The hook,
# the first beat and the closing share the first beat's data, so they hashed
# alike, and the showrunner saw "the hands-on-head pose repeats in the hook,
# seg3 and seg4, so Data's acting reads as one reused gesture" (2026-09-23).
# `render_build` names the scene it is drawing; each (scene, role) takes the
# act this video has used least. `reset_acts()` starts a video.
_SCENE_KEY = None
_ACTS: dict = {}
_ACT_USE: dict = {}


def reset_acts() -> None:
    _ACTS.clear()
    _ACT_USE.clear()


def act_for(scene_key, role: str) -> str:
    """The animator (scene, role) performs in this video — the least used in
    the role's pool so far. Outside a render (no scene key) the role passes
    through unchanged, exactly as before."""
    from data_learning import viz_scene as vs
    pool = vs.SCENE_ROLES.get(role)
    if scene_key is None or not pool:
        return role
    key = (scene_key, role)
    if key not in _ACTS:
        _ACTS[key] = min(pool, key=lambda a: (_ACT_USE.get(a, 0), pool.index(a)))
        _ACT_USE[_ACTS[key]] = _ACT_USE.get(_ACTS[key], 0) + 1
    return _ACTS[key]


def place_host(cr, role, phase, insight, x, fy, h, t, pace=False):
    """Put Data in the scene at (x, fy). He stands where the scene puts him
    and moves when the scene moves him: pacing is opt-in, not a default.
    (He used to walk back and forth through every scene and it read as
    random motion — operator, 2026-09-23: "decisive movement beats constant
    movement".)"""
    if pace:
        x, fy = walk(x, fy, t)
    return I._host(cr, act_for(_SCENE_KEY, role), phase, insight, "scene",
                   clamp(x, EDGE, W - EDGE), fy, h)


def birds(cr, t, y0=520, n=5, rgb=(30, 26, 60)):
    for k in range(n):
        ph = (t * 0.07 + k * 0.23) % 1
        bx = -80 + ph * (W + 160)
        by = y0 + 50 * k + 16 * math.sin(t * 2 + k)
        f = 11 * math.sin(t * 9 + k)
        cr.set_source_rgba(*_c(rgb, 0.8))
        cr.set_line_width(4)
        cr.move_to(bx - 22, by - f)
        cr.line_to(bx, by)
        cr.line_to(bx + 22, by - f)
        cr.stroke()


def dawn_sky(cr, t, y1=1100):
    vgrad(cr, P["dawn"], 0, y1)
    glow(cr, 820 + 12 * math.sin(t * 0.3), y1 - 220, 520, P["sun_glow"], 0.55)
    cr.set_source_rgba(*_c(P["sun"]))
    cr.arc(820 + 12 * math.sin(t * 0.3), y1 - 220, 80, 0, 2 * math.pi)
    cr.fill()
    for i in range(4):                       # mist banks drift
        x = (i * 360 + t * 30) % (W + 600) - 300
        cr.save()
        cr.translate(x, 700 + i * 90)
        cr.scale(1, 0.25)
        glow(cr, 0, 0, 300, P["mist"], 0.35)
        cr.restore()


# --------------------------------------------------------------- AMAZON ----

FOREST_Y = 1260          # the canopy's ground line


def forest_floor(cr):
    vgrad(cr, P["earth"], FOREST_Y - 10, H)


def amazon_clearing(cr, t, u, pts, host):
    """HERO: a standing rainforest
    SUBSTANCE: trees
    CAUSE: Data runs the treeline ahead of the saws that fell one tree per 1,000 km²
    Deforestation by year: the forest stands; each year a batch of trees
    topples — one tree per 1,000 km² cleared that year — while the readout
    names the year and the km². Data runs the treeline ahead of the saws."""
    pts = by_time([(str(l), float(v)) for l, v in pts])
    n = len(pts)
    dawn_sky(cr, t, y1=FOREST_Y)
    # far forest band, then the near trees that fall
    for x, d, s in _TREES[:30]:
        tree(cr, x, FOREST_Y - 150 - 60 * d, 0.55 * s, P["leaf_far"], P["leaf_far_shade"],
             P["trunk_far"])
    forest_floor(cr)
    k, fk = step_through(u, n)
    year, val = pts[k]
    felled = sum(round(v / 1000.0) for _, v in pts[:k])
    batch = round(val / 1000.0)
    fb = seg(fk, 0.0, 0.7)                   # this year's batch topples
    # THREE ROWS of forest, back to front, so the forest fills the frame
    # down to the captions; the clearing front sweeps left to right through
    # all of them at once (one tree = 1,000 km²).
    rows = ((FOREST_Y + 40, 1.0), (FOREST_Y + 170, 1.25), (FOREST_Y + 320, 1.55))
    cols = 34
    stand = []
    for c in range(cols):
        for r_, (by, sc) in enumerate(rows):
            x = -30 + c * (W + 60) / (cols - 1) + (r_ * 17) % 31 - 15
            stand.append((x, by + (c * 13 % 23), sc * (0.9 + 0.2 * ((c * 7 + r_) % 5) / 4)))
    for i, (xx, base, sc) in sorted(enumerate(stand), key=lambda q: q[1][1]):
        if i < felled:
            stump(cr, xx, base, 1.3 * sc)
        elif i < felled + batch:
            tree(cr, xx, base, 0.9 * sc, P["leaf"], P["leaf_shade"], P["trunk"],
                 lean=ease(fb), a=1 - 0.8 * ease(seg(fb, 0.6, 1.0)))
        else:
            tree(cr, xx, base, 0.9 * sc, P["leaf"], P["leaf_shade"], P["trunk"],
                 lean=0.02 * math.sin(t * 1.3 + i))
    birds(cr, t)
    fx = (felled + batch * fb) / max(1, len(stand)) * W
    # he fights the big years, hauls in the small ones, and at the end stops
    # to look at what one year of "falling" clearing still takes
    host("shock" if u > 0.86 else ("climb" if val > 12000 else "strain"),
         clamp(fx + 90, 120, W - 120),
         FOREST_Y + 250, 230)                  # above the caption band
    say_year, say_val = landed(pts, k, fk)
    fit_readout(cr, f"{int(say_val):,} km²", f"of rainforest cleared in {say_year}",
                80, 520, a=ease(seg(u, 0.0, 0.08)))
    text(cr, say_year, W - 80, 520, 64, look.INK, face="display", anchor="right",
         alpha=ease(seg(u, 0.0, 0.08)))



def amazon_bill_grows(cr, t, u, pts, host):
    """HERO: a scar of cleared land in the forest
    SUBSTANCE: bare earth
    CAUSE: the scar's rim advances a ring per year and shoves Data outward
    THE CLOSING — "Fewer trees fall each year. The bill still grows."
    The scar from the France and pasture beats, seen again, growing one RING
    per year like a tree's rings, each ring as thick as that year's clearing.
    The rings get thinner (fewer trees fall) and the scar still grows (the
    bill) — the line's two halves as two opposite motions in one picture,
    which is what the showrunner asked for on 2026-09-23. Data is shoved
    outward by the rim as it advances."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    n = len(rows)
    total = sum(v for _, v in rows) or 1.0
    cx, cy, R = SCAR
    HZ = 960                                      # the horizon
    vgrad(cr, P["dawn"], 0, HZ)
    sun_y = HZ - 220 + 170 * ease(u)              # the day is ending
    glow(cr, 800, sun_y, 480, P["sun_glow"], 0.6)
    cr.set_source_rgba(*_c(P["sun"]))
    cr.arc(800, sun_y, 80, 0, 2 * math.pi)
    cr.fill()
    # the scar eats a FOREST: canopy to the frame's foot, drawn back to front
    vgrad(cr, [(0.0, P["leaf_far_shade"]), (1.0, P["leaf_shade"])], HZ - 10, H)
    for x, d, s_ in _TREES[:40]:
        tree(cr, x, HZ + 20 * d, 0.45 * s_, P["leaf_far"], P["leaf_far_shade"],
             P["trunk_far"], lean=0.03 * math.sin(t * 1.1 + x))
    for q in range(90):                           # the canopy, crown on crown
        gx = (q * 137) % (W + 120) - 60
        gy = HZ + 40 + (q * 71) % (H - HZ - 40)
        sw = 5 * math.sin(t * 1.4 + q)
        glow(cr, gx + sw, gy, 70, P["leaf"], 0.55)
        cr.set_source_rgba(*_c(P["leaf"] if q % 3 else P["leaf_shade"]))
        cr.arc(gx + sw, gy, 34 + (q * 13) % 22, 0, 2 * math.pi)
        cr.fill()
    run = seg(u, 0.04, 0.86)                      # the years, then the bill
    k = min(n - 1, int(run * n))
    year, val = rows[k]
    fb = ease(seg(run * n - k, 0.0, 0.75)) if run < 1 else 1.0
    cum = [sum(v for _, v in rows[:j + 1]) for j in range(n)]
    ks = [math.sqrt(c / total) for c in cum]     # radius ∝ sqrt(area)
    k_prev = ks[k - 1] if k else 0.0
    k_now = k_prev + (ks[k] - k_prev) * fb
    # rings, outermost first; the newest one is still spreading
    shades = (P["scar"], tuple(int(c * 0.82) for c in P["scar"]))
    for j in range(k, -1, -1):
        kj = k_now if j == k else ks[j]
        if kj <= 0.01:
            continue
        scar_path(cr, kj)
        cr.set_source_rgba(*_c(shades[j % 2]))
        cr.fill()
    # stumps inside what has been cleared
    for q in range(60):
        a_ = q * 2.399
        rr = math.sqrt((q + 0.5) / 60)
        if rr > k_now * 0.92:
            continue
        stump(cr, cx + math.cos(a_) * rr * R * 0.95,
              cy + math.sin(a_) * rr * R * 0.95 * 0.62 + 10, 1.0)
    # the trees at the advancing rim topple as it passes them
    for q in range(14):
        a_ = math.pi * (1.1 + 0.8 * q / 13)
        rx_ = cx + math.cos(a_) * R * (k_now + 0.06)
        ry_ = cy + math.sin(a_) * R * (k_now + 0.06) * 0.62
        tree(cr, rx_, ry_, 0.55, P["leaf"], P["leaf_shade"], P["trunk"],
             lean=0.08 + 0.92 * fb, a=1 - 0.6 * ease(seg(fb, 0.7, 1.0)))
        # each year's ring fells the trees at its edge: one decisive fall a
        # year, not a forest jiggling forever
    birds(cr, t)
    ang = math.radians(48)                        # he is shoved by the rim
    ex = cx + math.cos(ang) * R * max(0.3, k_now)
    ey = cy + math.sin(ang) * R * max(0.3, k_now) * 0.62
    host("point" if run < 0.12 else ("strain" if run < 1 else "shock"),
         ex + 40, ey + 40, 220)       # shoved outward as the rim advances
    # ONE headline, and it SHRINKS: the first year's clearing while the rings
    # begin, the latest year's once they are laid. Every year in between is
    # a ring, not a readout — eight numbers in six seconds were each on
    # screen for 0.6s, too fast to read (the dwell check).
    ry, rv = rows[0] if run < 0.6 else rows[-1]
    vmax = max(v for _, v in rows) or 1.0
    fit_readout(cr, f"{int(rv):,} km²", f"cleared in {ry}", 80, 700,
                a=ease(seg(u, 0.0, 0.05)), size=70 + 90 * (rv / vmax))


SCAR = (W / 2, 1270, 470)


def scar_path(cr, k=1.0):
    """The cleared scar, an organic patch; scenes 2 and 3 share it so the
    land France fell onto is the land that becomes pasture. `k` scales it
    (the closing grows it ring by ring)."""
    cx, cy, R = SCAR
    R *= k
    cr.save()
    cr.translate(cx, cy)
    cr.scale(1, 0.62)
    cr.move_to(R, 0)
    for k in range(1, 49):
        a_ = k / 48 * 2 * math.pi
        r = R * (1 + 0.06 * math.sin(a_ * 5 + 0.4) + 0.03 * math.sin(a_ * 11))
        cr.line_to(r * math.cos(a_), r * math.sin(a_))
    cr.close_path()
    cr.restore()


def amazon_vs_france(cr, t, u, pts, host):
    """HERO: a map of France dropped on cleared land
    SUBSTANCE: land
    CAUSE: France falls onto the clearing and Data measures the land left uncovered
    750,000 km² lost vs France: France drops onto the cleared land with a
    thud, and the land left uncovered is measured — the difference."""
    (la, lost), (lf, fra) = [(str(l), float(v)) for l, v in pts[:2]]
    if fra > lost:
        (la, lost), (lf, fra) = (lf, fra), (la, lost)
    dawn_sky(cr, t, y1=900)
    vgrad(cr, P["cleared"], 880, H)
    # the cleared scar: an organic patch whose AREA is `lost`
    cx, cy, R = SCAR
    scar_path(cr)
    cr.set_source_rgba(*_c(P["scar"]))
    cr.fill()
    for x, d, s in _TREES[:40]:              # the forest that remains, around
        yy = 900 + 40 * d
        tree(cr, x, yy, 0.5 * s, P["leaf_far"], P["leaf_far_shade"], P["trunk_far"])
    # France falls in, sized by AREA: width scales with sqrt(area ratio)
    fall = ease(seg(u, 0.18, 0.40))
    bounce = math.sin(seg(u, 0.40, 0.48) * math.pi) * 18 * (1 - seg(u, 0.40, 0.48))
    fw = 2 * R * 0.78 * math.sqrt(fra / lost)
    fy = -500 + (cy + 500) * fall - bounce
    cr.save()
    shape_path(cr, FRANCE, cx, fy, fw)
    g = cairo.LinearGradient(cx - fw / 2, 0, cx + fw / 2, 0)
    g.add_color_stop_rgba(0, *_c(P["france_lit"]))
    g.add_color_stop_rgba(1, *_c(P["france_shade"]))
    cr.set_source(g)
    cr.fill_preserve()
    cr.set_source_rgba(*_c(P["france_rim"]))
    cr.set_line_width(6)
    cr.stroke()
    cr.restore()
    dust = seg(u, 0.40, 0.62)
    if 0 < dust < 1:
        for k in range(16):
            ang = math.pi + k / 15 * math.pi
            r = 60 + dust * 360
            cr.set_source_rgba(*_c(P["dust"], 0.8 * (1 - dust)))
            cr.arc(cx + math.cos(ang) * r, cy + 150 + math.sin(ang) * r * 0.3,
                   14 * (1 - dust) + 4, 0, 2 * math.pi)
            cr.fill()
    # the land France does NOT cover, traced out — the "bigger than France"
    # claim as a line drawn round what is left over
    tr = ease(seg(u, 0.46, 0.62))   # traced while the flag goes in: done by 0.6
    if tr > 0:
        ring = []
        for k in range(97):
            a_ = k / 96 * 2 * math.pi
            r_ = R * (1 + 0.06 * math.sin(a_ * 5 + 0.4) + 0.03 * math.sin(a_ * 11))
            ring.append((cx + r_ * math.cos(a_), cy + r_ * math.sin(a_) * 0.62))
        m_ = max(2, int(len(ring) * tr))
        cr.set_source_rgba(*_c(P["accent2"]))
        cr.set_line_width(10)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(*ring[0])
        for q in ring[1:m_]:
            cr.line_to(*q)
        cr.stroke()
        glow(cr, *ring[m_ - 1], 40, P["accent2"], 0.9)
    if u > 0.40:            # he drives the flag into France, then reacts
        host("strain" if u < 0.86 else "cheer", cx + 30, fy - 8, 190)
        sink = 80 * ease(seg(u, 0.42, 0.6))      # the pole goes in, blow by blow
        top = fy - 230 + sink
        cr.set_source_rgba(*_c(look.INK))
        cr.set_line_width(5)
        cr.move_to(cx + 90, fy - 8)
        cr.line_to(cx + 90, top)
        cr.stroke()
        cr.set_source_rgba(*_c(P["flag"]))
        cr.move_to(cx + 90, top)
        cr.line_to(cx + 160, top + 18)
        cr.line_to(cx + 90, top + 36)
        cr.close_path()
        cr.fill()
    else:
        # he carries the flag in along the scar's rim while France falls
        host("point" if u < 0.08 else "hold_up", cx - R + 40 + 200 * seg(u, 0.08, 0.4),
             cy - 40, 190)
    fit_readout(cr, f"{int(lost):,} km²", "of Amazon lost since 1970", W / 2, 470,
                anchor="center", a=ease(seg(u, 0.0, 0.1)))
    b = seg(u, 0.48, 0.58)
    if b > 0:
        diff = int(lost - fra)
        fit_readout(cr, f"{diff:,} km² more", f"than all of {lf.title() if lf.isupper() else 'France'}",
                    W / 2, 820, anchor="center", a=ease(b), rgb=P["accent2"], size=78)


def amazon_where_it_goes(cr, t, u, pts, host):
    """HERO: a scar of cleared land
    SUBSTANCE: pasture grass
    CAUSE: Data rides the lead cow in as grass spreads over the cattle's share
    What the cleared land becomes: grass spreads across that share of the
    SAME scar France fell onto, a few cattle wander in to graze it, and the
    rest of the scar goes to a logging truck and its pile. The share is the
    AREA of land — the cattle are life, not a count. Data rides the lead cow."""
    rows = [(str(l), float(v)) for l, v in pts]
    tot = sum(v for _, v in rows) or 1.0
    (lp, vp) = max(rows, key=lambda r: r[1])
    share = vp / tot
    cx, cy, R = SCAR
    dawn_sky(cr, t, y1=900)
    vgrad(cr, P["cleared"], 880, H)
    for x, d, s_ in _TREES[:40]:
        tree(cr, x, 900 + 40 * d, 0.5 * s_, P["leaf_far"], P["leaf_far_shade"],
             P["trunk_far"])
    scar_path(cr)
    solid(cr, P["scar"], rim=False, edge=False)
    x0, x1 = cx - R * 1.1, cx + R * 1.1
    split = x0 + (x1 - x0) * share * ease(seg(u, 0.05, 0.5))
    cr.save()
    scar_path(cr)
    cr.clip()
    cr.rectangle(x0, 0, split - x0, H)
    solid(cr, P["pasture"], rim=False, edge=False)
    for i in range(70):                       # grass tufts sway
        gx = x0 + (i * 131) % int(max(1, split - x0))
        gy = cy - R * 0.6 + (i * 71) % int(R * 1.2)
        cr.set_source_rgba(*_c(P["pasture_lit"]))
        cr.set_line_width(4)
        cr.move_to(gx, gy)
        cr.line_to(gx + 6 * math.sin(t * 2 + i), gy - 20)
        cr.stroke()
    cr.restore()
    herd = [(0.22, -0.10), (0.42, 0.18), (0.58, -0.22), (0.30, 0.34), (0.66, 0.10)]
    lead = None
    for k, (fx, fy) in enumerate(herd):
        hx = (x0 + (x1 - x0) * fx * share / 0.8 + 18 * math.sin(t * 0.35 + k)
              + (stride(t) * 0.6 if k == 0 else 0.0))
        if hx > split - 40:
            continue
        s_ = 1.25 * pop(seg(u, 0.2 + k * 0.06, 0.3 + k * 0.06))
        cow(cr, hx, cy + R * 0.62 * fy, s_, t)
        if k == 0:
            lead = (hx, cy + R * 0.62 * fy)
    tx = x0 + (x1 - x0) * (share + (1 - share) / 2)
    la = ease(seg(u, 0.45, 0.6))
    truck(cr, tx + 30 * math.sin(t * 0.5), cy - 30, 1.2, a=la)
    contact_shadow(cr, tx, cy + 104, 120, a=0.35 * la)
    for k in range(5):                        # the log pile
        disc(cr, tx - 40 + (k % 3) * 26 + (k // 3) * 13, cy + 90 - (k // 3) * 22, 13,
             P["log"], a=la)
    if lead:   # he rides the lead cow: its walk is his motion
        host("hold_up" if u < 0.85 else "cheer", lead[0] - 4, lead[1] - 20,
             180)                  # the reins while the herd spreads
    else:
        host("strain", x0 + 60, cy, 180)   # driving the first cows in
    fit_readout(cr, f"{int(round(share * 100))}%", f"becomes {lp.lower()}", 80, 470,
                a=ease(seg(u, 0.0, 0.1)), size=150)
    rest = f"{int(round((1 - share) * 100))}%"
    text(cr, rest, W - 80, 470, 90, look.INK, face="display", anchor="right",
         alpha=ease(seg(u, 0.45, 0.6)))
    _rl = rows[1][0] if rows[0][0] == lp else rows[0][0]
    text(cr, _rl, W - 80, 530, I.fit_size(cr, _rl, 36, 460), look.INK,
         anchor="right", alpha=ease(seg(u, 0.45, 0.6)))


# --------------------------------------------------------------- COFFEE ----

def cafe(cr, t, wy=(640, 1160), counter=1330):
    """A cafe at dawn: warm wall, a window of sunrise, a wooden counter."""
    vgrad(cr, P["cafe_wall"])
    y0, y1 = wy
    cr.save()
    cr.rectangle(120, y0, 840, y1 - y0)
    cr.clip()
    vgrad(cr, P["window"], y0, y1)
    glow(cr, 700, y1 - 100, 360, P["sun"], 0.7)
    for i in range(3):
        x = (i * 380 + t * 22) % 1200 - 180
        cr.save()
        cr.translate(x, y0 + 120 + i * 70)
        cr.scale(1, 0.3)
        glow(cr, 0, 0, 200, P["mist"], 0.45)
        cr.restore()
    cr.restore()
    cr.set_source_rgba(*_c(P["chalk_frame"]))
    cr.set_line_width(18)
    cr.rectangle(120, y0, 840, y1 - y0)
    cr.stroke()
    cr.move_to(540, y0)
    cr.line_to(540, y1)
    cr.stroke()
    cr.rectangle(0, counter, W, 40)
    solid(cr, P["counter_top"], finish="gloss", rim=False, edge=False)
    vgrad(cr, [(0.0, P["counter"]), (1.0, (40, 24, 20))], counter + 40, H)


def steam(cr, x, y, t, strength=1.0):
    for k in range(3):
        ph = (t * 0.6 + k / 3) % 1
        cr.set_source_rgba(*_c(P["steam"], 0.45 * (1 - ph) * strength))
        cr.set_line_width(8)
        cr.move_to(x - 20 + k * 20, y)
        for j in range(1, 7):
            cr.line_to(x - 20 + k * 20 + 16 * math.sin(t * 2 + j + k), y - j * 26 - ph * 50)
        cr.stroke()


def cup(cr, x, y, s=1.0):
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    contact_shadow(cr, 0, 4, 150, a=0.3)
    cr.move_to(-70, -120)
    cr.line_to(70, -120)
    cr.line_to(56, 0)
    cr.line_to(-56, 0)
    cr.close_path()
    solid(cr, P["cow"], finish="gloss")
    cr.save()
    cr.translate(0, -120)
    cr.scale(1, 0.25)
    cr.arc(0, 0, 66, 0, 2 * math.pi)
    cr.restore()
    solid(cr, P["bean"], finish="glass", rim=False)
    cr.set_source_rgba(*_c(P["cow"]))
    cr.set_line_width(14)
    cr.arc(80, -64, 30, -math.pi / 2, math.pi / 2)
    cr.stroke()
    cr.restore()


def sack(cr, x, y, s=1.0, a=1.0, label=True):
    if s <= 0.02 or a <= 0:
        return
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    contact_shadow(cr, 0, 4, 110, a=0.3 * a)
    cr.move_to(-46, 0)
    cr.curve_to(-54, -40, -44, -86, -30, -96)
    cr.line_to(30, -96)
    cr.curve_to(44, -86, 54, -40, 46, 0)
    cr.close_path()
    # lit, with a dark edge: a beige sack on beige dry soil was one mush of
    # colour — hard to count by eye, invisible in grey when it moved
    solid(cr, P["sack"], a=a)
    cr.set_source_rgba(*_c(P["sack_shade"], 0.6 * a))
    cr.move_to(10, 0)
    cr.curve_to(40, -30, 44, -80, 30, -96)
    cr.line_to(46, 0)
    cr.close_path()
    cr.fill()
    if label:
        cr.set_source_rgba(*_c(P["sack_ink"], a))
        cr.arc(-6, -46, 12, 0, 2 * math.pi)
        cr.fill()
    cr.restore()


def coffee_climb(cr, t, u, pts, host):
    """HERO: a brass balance scale with a pound of coffee
    SUBSTANCE: coins
    CAUSE: Data carries a coin per 25 cents to the money pan, which sinks under them
    The price of a pound of coffee, by year: a pound of beans on one pan
    of a brass scale, and the money on the other — one coin per 25 cents,
    piling up as the years tick. The pile IS the price."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    n = len(rows)
    CT = 1520                                  # the counter top, above the captions
    cafe(cr, t, wy=(560, 1200), counter=CT)
    k, fk = step_through(u, n)
    year, price = rows[k]
    prev = rows[k - 1][1] if k else price
    f = ease(seg(fk, 0.0, 0.5))
    shown = prev + (price - prev) * f          # the coins glide...
    say_year, say_price = landed(rows, k, fk)  # ...the readout only lands
    coins = shown / 0.25
    # the scale: beam tips toward the heavier (costlier) side a little
    cx, py = W / 2, 1050
    # the money side sinks as it outweighs the pound of beans
    tilt = clamp((coins - 6) / 14 * 0.16, -0.10, 0.18)
    contact_shadow(cr, cx, CT, 320, a=0.35)
    cylinder(cr, cx - 16, CT - 22, 32, CT - 22 - py, P["brass"], finish="metal")
    cr.rectangle(cx - 120, CT - 22, 240, 22)
    solid(cr, P["brass_shade"], finish="metal")
    L = 360
    lx, ly = cx - L * math.cos(tilt), py - L * math.sin(-tilt)
    rx, ry = cx + L * math.cos(tilt), py + L * math.sin(tilt)
    cr.set_source_rgba(*_c(P["brass"]))
    cr.set_line_width(14)
    cr.move_to(lx, ly)
    cr.line_to(rx, ry)
    cr.stroke()
    glow(cr, cx, py, 26, P["brass"], 1.0)
    for (px, pyy) in ((lx, ly), (rx, ry)):
        cr.set_source_rgba(*_c(P["brass_shade"]))
        cr.set_line_width(4)
        cr.move_to(px, pyy)
        cr.line_to(px - 120, pyy + 230)
        cr.move_to(px, pyy)
        cr.line_to(px + 120, pyy + 230)
        cr.stroke()
        cr.save()
        cr.translate(px, pyy + 236)
        cr.scale(1, 0.22)
        cr.arc(0, 0, 140, 0, 2 * math.pi)
        cr.restore()
        solid(cr, P["brass"], finish="metal")
    # a pound of beans on the left pan
    sack(cr, lx, ly + 232, 1.9)
    # the money on the right pan: whole coins, the last one arriving
    whole = int(coins)
    top = max(r[1] for r in rows) / 0.25 or 1.0
    # he paces beside the scale, and steps back as the pile outgrows him
    hx, hy = W - 150 - 220 * clamp(coins / top), CT   # he backs off as it piles
    hand = (hx - 40, hy - 170)                 # Data's hand
    for c in range(whole + 1):
        a = 1.0 if c < whole else coins - whole
        if a <= 0.02:
            continue
        cx_ = rx - 80 + (c % 5) * 40 + (c // 5 % 2) * 20
        cy_ = ry + 226 - (c // 5) * 24
        big = 1.0
        if c == whole:                        # the coin he is tossing, in flight
            q = ease(a)
            for tr in (0.12, 0.24, 0.36):     # its trail
                qq = max(0.0, q - tr)
                glow(cr, hand[0] + (cx_ - hand[0]) * qq,
                     hand[1] + (cy_ - hand[1]) * qq - 260 * math.sin(math.pi * qq),
                     26, P["coin"], 0.45 * (1 - tr * 2))
            cx_ = hand[0] + (cx_ - hand[0]) * q
            cy_ = hand[1] + (cy_ - hand[1]) * q - 260 * math.sin(math.pi * q)
            a, big = 1.0, 1.5 - 0.5 * q
        cr.set_source_rgba(*_c(P["coin_edge"], a))
        cr.save()
        cr.translate(cx_, cy_ + 7)
        cr.scale(big, 0.35 * big)
        cr.arc(0, 0, 34, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
        cr.set_source_rgba(*_c(P["coin"], a))
        cr.save()
        cr.translate(cx_, cy_)
        cr.scale(big, 0.35 * big)
        cr.arc(0, 0, 34, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
    cup(cr, 110, CT, 0.9)
    steam(cr, 110, CT - 120, t, 0.5 + 0.5 * clamp(price / max(r[1] for r in rows)))
    moving = abs(price - prev) > 1e-9 and f < 1
    bag = (hx - 60, hy - 250)                 # the bag he holds up, tipped
    sack(cr, bag[0], bag[1], 0.7)
    if moving:                                # coins stream pan-ward, or back
        top = (rx, ry + 200 - (int(coins) // 5) * 24)
        up = price < prev                     # falling price: he scoops them back
        for j in range(7):
            q = (t * 2.4 + j / 7) % 1
            q = 1 - q if up else q
            x_ = bag[0] + (top[0] - bag[0]) * q
            y_ = bag[1] + (top[1] - bag[1]) * q - 90 * math.sin(math.pi * q)
            cr.set_source_rgba(*_c(P["coin"]))
            cr.save()
            cr.translate(x_, y_)
            cr.scale(1, 0.45)
            cr.arc(0, 0, 18, 0, 2 * math.pi)
            cr.restore()
            cr.fill()
    host("hold_up" if moving else ("strain" if u < 0.9 else "cheer"), hx, hy, 240,
         pace=False)               # tossing, hauling the next coin, then the reaction
    fit_readout(cr, f"${say_price:.2f}", f"a pound of arabica, {say_year}", 80, 520,
                a=ease(seg(u, 0.0, 0.06)), size=150)
    text(cr, say_year, W - 80, 520, 64, look.INK, face="display", anchor="right",
         alpha=ease(seg(u, 0.0, 0.06)))


def coffee_drought(cr, t, u, pts, host):
    """HERO: sacks of coffee stacked at a farm gate
    SUBSTANCE: coffee sacks
    CAUSE: the drought cracks the ground and the lost share of the pile crumbles to dust as Data strains to hold it
    Brazil's crop forecast cut by drought: sacks stacked at the farm gate,
    the ground cracking, and the lost share of the pile crumbling to dust —
    the gap between the two estimates."""
    rows = [(str(l), float(v)) for l, v in pts[:2]]
    (l0, before), (l1, after) = rows if rows[0][1] >= rows[1][1] else rows[::-1]
    vgrad(cr, P["drought_sky"], 0, 1100)
    glow(cr, 760, 560, 420, P["sun_hot"], 0.85 + 0.1 * math.sin(t * 2))
    disc(cr, 760, 560, 110, P["sun_hot"], finish="gloss")
    vgrad(cr, P["dry_soil"], 1060, H)
    dry = ease(seg(u, 0.1, 0.45))
    for i in range(16):                      # coffee shrubs on the hills
        x = 40 + i * 68
        col = tuple(int(a + (b - a) * dry) for a, b in zip(P["shrub"], P["shrub_dry"]))
        disc(cr, x, 1080 + 12 * (i % 3), 34, col)
    for k in range(int(26 * dry)):           # the ground cracks
        x = 60 + (k * 173) % 960
        y = 1480 + (k * 97) % 160
        cr.set_source_rgba(*_c(P["crack"]))
        cr.set_line_width(4)
        cr.move_to(x, y)
        cr.line_to(x + 30, y + 16)
        cr.line_to(x + 22, y + 44)
        cr.stroke()
    # the pile: one sack per million bags, stacked in a pyramid
    total = int(round(before))
    keep = int(round(after))
    lost = ease(seg(u, 0.25, 0.55))
    # the lost sacks go ONE AT A TIME — each drops and crumbles in its own
    # moment — instead of the whole top sinking 60px over four seconds
    drop = seg(u, 0.25, 0.58) * max(1, total - keep)
    idx = 0
    per_row = [11, 10, 9, 7, 5, 3]
    contact_shadow(cr, 540, 1452, 900, a=0.4)
    for r_, cnt in enumerate(per_row):
        for c in range(cnt):
            if idx >= total:
                break
            x = 540 - (cnt - 1) * 38 + c * 76
            y = 1440 - r_ * 74
            gone = idx >= keep
            pj = seg(drop - (total - 1 - idx), 0.0, 0.6) if gone else 0.0
            pj = pj * pj                          # it FALLS — gravity, not a glide
            sack(cr, x, y + 420 * pj, 0.8, a=1.0 - pj, label=False)
            if gone and 0 < pj < 1:              # it bursts as it goes
                cr.set_source_rgba(*_c(P["dust"], 0.6 * (1 - pj)))
                cr.arc(x, y - 20 + 120 * pj, 20 + 50 * pj, 0, 2 * math.pi)
                cr.fill()
            idx += 1
    heat_shimmer(cr, t, 900, 1600, a=0.22)
    # his bit: he points at the pile, climbs it to hold up the top sacks as
    # they crumble, and lands in shock on what is left
    climb = ease(seg(u, 0.08, 0.4))
    host("point" if climb <= 0 else ("climb" if lost < 0.95 else
                                     ("strain" if u < 0.92 else "shock")),
         280 + 200 * climb, 1520 - 330 * climb, 220)
    lab, val = (l1, after) if lost >= 0.6 else (l0, before)
    fit_readout(cr, f"{val:.1f}M bags", f"Brazil arabica forecast · {lab.lower()}", 80, 520,
                a=ease(seg(u, 0.0, 0.08)), size=130)
    b = ease(seg(u, 0.48, 0.58))
    if b > 0:
        fit_readout(cr, f"{before - after:.0f} million bags gone", "overnight",
                    W / 2, 800, anchor="center", a=b, rgb=P["accent2"], size=64)



# ----------------------------------------------------------- URBAN HEAT ----

STREET_Y = 1450


def heat_shimmer(cr, t, y0, y1, a=0.18):
    for k in range(9):
        y = y0 + (k * 97 + t * 60) % max(1, (y1 - y0))
        cr.set_source_rgba(*_c(P["mist"], a))
        cr.set_line_width(3)
        cr.move_to(0, y)
        for x in range(0, W + 30, 30):
            cr.line_to(x, y + 6 * math.sin(x / 40 + t * 4 + k))
        cr.stroke()


def rowhouse(cr, x, w, h, base, lit, shade, hot=0.0, t=0.0, trees=False):
    contact_shadow(cr, x + w / 2, base, w * 1.3, a=0.3)
    cr.rectangle(x, base - h, w * 0.7, h)
    solid(cr, lit, rim=False)
    cr.rectangle(x + w * 0.7, base - h, w * 0.3, h)
    solid(cr, shade, rim=False, depth=0.5)
    cr.move_to(x - 6, base - h)
    cr.line_to(x + w / 2, base - h - 40)
    cr.line_to(x + w + 6, base - h)
    cr.close_path()
    solid(cr, shade, depth=0.5)
    for r_ in range(int((h - 60) // 90)):
        for c_ in range(2):
            cr.set_source_rgba(*_c(P["glass"], 0.85))
            cr.rectangle(x + 16 + c_ * (w * 0.7 - 50) / 1.0 * 0.6, base - h + 30 + r_ * 90,
                         26, 40)
            cr.fill()
    if hot > 0:
        glow(cr, x + w / 2, base - h / 2, w * 0.9, P["heat"],
             0.28 * hot * (0.8 + 0.2 * math.sin(t * 3 + x)))
    if trees:
        for dx in (-10, w * 0.55):
            cr.rectangle(x + dx + 20, base - 110, 12, 110)
            solid(cr, P["trunk"], rim=False)
            disc(cr, x + dx + 26, base - 140 + 4 * math.sin(t * 1.5 + x), 52, P["treeleaf"])


def street(cr):
    cr.set_source_rgba(*_c(P["curb"]))
    cr.rectangle(0, STREET_Y, W, 22)
    cr.fill()
    vgrad(cr, [(0.0, P["street"]), (1.0, (26, 24, 32))], STREET_Y + 22, H)
    cr.set_source_rgba(*_c(P["coin"], 0.7))
    for k in range(6):
        cr.rectangle(40 + k * 190, STREET_Y + 160, 110, 12)
        cr.fill()


def traffic(cr, t):
    """Cars driving the street both ways — a city is never still."""
    for k, (lane, v, col) in enumerate(((STREET_Y + 70, 260, P["truck"]),
                                        (STREET_Y + 120, -220, P["brick_cool"]),
                                        (STREET_Y + 70, 260, P["truck_cab"]))):
        x = (k * 420 + t * v) % (W + 300) - 150
        contact_shadow(cr, x, lane + 6, 170, a=0.35)
        cr.rectangle(x - 70, lane - 34, 140, 34)
        solid(cr, col, finish="gloss")
        cr.rectangle(x - 40, lane - 58, 80, 26)
        solid(cr, col, finish="gloss")
        cr.rectangle(x - 32, lane - 54, 64, 18)
        solid(cr, P["glass"], finish="glass", a=0.9, rim=False)
        for wx in (-44, 44):
            disc(cr, x + wx, lane, 14, P["cow_dark"])


def heat_by_city(cr, t, u, pts, host):
    """HERO: a street thermometer on a lamppost
    SUBSTANCE: mercury
    CAUSE: Data climbs the lamppost and the mercury rises to each city's added degrees
    Added heat by city: a street thermometer on a lamppost; the city name
    changes and the mercury rises to that city's added degrees. Coolest to
    hottest, so it lands on the top city whatever order the data came in."""
    rows = sorted(((str(l), float(v)) for l, v in pts), key=lambda r: r[1])
    n = len(rows)
    vgrad(cr, P["heat_sky"], 0, STREET_Y)
    glow(cr, 780, 420, 380, P["sun_hot"], 0.9)
    for i, x in enumerate(range(-20, W, 150)):   # the block behind
        rowhouse(cr, x, 140, 420 + (i * 83) % 260, STREET_Y, P["brick"], P["brick_shade"],
                 hot=0.6, t=t)
    heat_shimmer(cr, t, 700, STREET_Y)
    street(cr)
    traffic(cr, t)
    k, fk = step_through(u, n)
    city, deg = rows[k]
    prev = rows[k - 1][1] if k else 0.0
    shown = prev + (deg - prev) * ease(seg(fk, 0.0, 0.5))   # the mercury glides
    say_city, say_deg = landed(rows, k, fk)                  # the number lands
    vmax = max(v for _, v in rows) * 1.15
    tx, t0, t1 = 780, 700, 1330                  # the thermometer
    cr.set_source_rgba(*_c(P["curb"]))
    cr.rectangle(tx - 10, t1, 20, STREET_Y - t1)
    cr.fill()
    cr.set_source_rgba(*_c(P["glass"]))
    cr.rectangle(tx - 34, t0, 68, t1 - t0)
    cr.fill()
    cr.arc(tx, t1 + 20, 56, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgba(*_c(P["mercury"]))
    cr.arc(tx, t1 + 20, 42, 0, 2 * math.pi)
    cr.fill()
    mh = (t1 - t0 - 30) * shown / vmax
    cr.rectangle(tx - 18, t1 - mh, 36, mh + 20)
    cr.fill()
    for q in range(0, int(vmax) + 1, 2):
        y = t1 - (t1 - t0 - 30) * q / vmax
        cr.set_source_rgba(*_c(P["paper_ink"]))
        cr.set_line_width(3)
        cr.move_to(tx + 34, y)
        cr.line_to(tx + 54, y)
        cr.stroke()
        text(cr, f"+{q}°", tx + 64, y + 10, 26, look.INK, anchor="left")
    # he rides the mercury itself, city after city — climbing while it rises,
    # hanging on and fanning himself while it holds
    rising = shown < deg - 0.05
    host("climb" if rising else "strain", tx - 96, t1 - mh + 150, 200)
    fit_readout(cr, f"+{say_deg:.1f}°F", f"extra heat from pavement · {say_city}", 80, 520,
                a=ease(seg(u, 0.0, 0.06)), size=140)


def heat_share(cr, t, u, pts, host):
    """HERO: one city street, half treeless
    SUBSTANCE: shade trees
    CAUSE: Data walks from the hot treeless share into the shade
    Who lives in the hottest blocks: one street, the hot share of it
    treeless and glowing, the rest shaded by trees. Data walks from the heat
    into the shade."""
    rows = [(str(l), float(v)) for l, v in pts]
    tot = sum(v for _, v in rows) or 1.0
    (lh, vh) = max(rows, key=lambda r: r[1])
    share = vh / tot
    vgrad(cr, P["heat_sky"], 0, STREET_Y)
    glow(cr, 300, 420, 380, P["sun_hot"], 0.85)
    split = W * share * ease(seg(u, 0.05, 0.4)) if u < 0.4 else W * share
    w = 150
    for i, x in enumerate(range(-20, W, w)):
        hot = (x + w / 2) < split
        rowhouse(cr, x, w - 10, 520 + (i * 61) % 200, STREET_Y,
                 P["brick"] if hot else P["brick_cool"],
                 P["brick_shade"] if hot else P["brick_cool_shade"],
                 hot=1.0 if hot else 0.0, t=t, trees=not hot)
    heat_shimmer(cr, t, 700, STREET_Y, a=0.22)
    street(cr)
    traffic(cr, t)
    cr.set_source_rgba(*_c(look.INK, 0.6))
    cr.set_dash([14, 12])
    cr.set_line_width(4)
    cr.move_to(W * share, 640)
    cr.line_to(W * share, STREET_Y)
    cr.stroke()
    cr.set_dash([])
    hx = 120 + (W * share + 120 - 120) * ease(seg(u, 0.5, 0.95))
    host("strain" if hx < W * share else "cheer", hx, STREET_Y + 10, 230)
    fit_readout(cr, f"{int(round(share * 100))}%", "live in the hottest blocks", 80, 520,
                a=ease(seg(u, 0.0, 0.08)), size=150)
    text(cr, f"{int(round((1 - share) * 100))}%", W - 80, 520, 90, P["cool"],
         face="display", anchor="right", alpha=ease(seg(u, 0.3, 0.45)))
    text(cr, "in the shade", W - 80, 580, 32, look.INK, anchor="right",
         alpha=ease(seg(u, 0.3, 0.45)))


def heat_redlining(cr, t, u, pts, host):
    """HERO: a paper city map with a redlined zone
    SUBSTANCE: heat shimmer
    CAUSE: Data traces the redlined zone and heat rises off exactly those blocks
    The 1930s map: a paper city map with the redlined zone outlined in
    red, and heat rising off exactly that zone today — the redlined blocks'
    added degrees against their neighbours'."""
    rows = [(str(l), float(v)) for l, v in pts]
    (lr, vr) = max(rows, key=lambda r: r[1])
    (lb, vb) = min(rows, key=lambda r: r[1])
    vgrad(cr, P["cafe_wall"])
    mx, my, mw, mh = 110, 660, 860, 880
    cr.set_source_rgba(0, 0, 0, 0.35)
    cr.rectangle(mx + 14, my + 18, mw, mh)
    cr.fill()
    cr.rectangle(mx, my, mw, mh)
    solid(cr, P["paper"], rim=False, depth=0.3)     # a sheet: lit, barely shaded
    cr.set_source_rgba(*_c(P["paper_ink"], 0.55))
    cr.set_line_width(3)
    for k in range(1, 8):                        # the street grid
        cr.move_to(mx + k * mw / 8, my)
        cr.line_to(mx + k * mw / 8 + 12 * math.sin(k), my + mh)
        cr.move_to(mx, my + k * mh / 8)
        cr.line_to(mx + mw, my + k * mh / 8 + 10 * math.cos(k))
    cr.stroke()
    text(cr, "RESIDENTIAL SECURITY MAP · 1930s", mx + mw / 2, my + 60, 34,
         P["paper_ink"], anchor="center", shadow=False)
    zx, zy, zw, zh = mx + 90, my + 300, 440, 380
    rl = ease(seg(u, 0.1, 0.35))
    cr.set_source_rgba(*_c(P["redline"], 0.25 * rl))
    cr.rectangle(zx, zy, zw, zh)
    cr.fill()
    cr.set_source_rgba(*_c(P["redline"], rl))
    cr.set_line_width(8)
    cr.rectangle(zx, zy, zw, zh)
    cr.stroke()
    text(cr, "HAZARDOUS", zx + zw / 2, zy + zh / 2 + 16, 52, P["redline"],
         face="display", anchor="center", alpha=rl, shadow=False)
    ht = ease(seg(u, 0.4, 0.7))               # heat rises off that zone, today
    if ht > 0:
        glow(cr, zx + zw / 2, zy + zh / 2, 340, P["heat"], 0.55 * ht)
        for k in range(24):                    # heat waves rise off the zone
            ph = (t * 0.55 + k / 24) % 1
            x = zx + 30 + (k * 53) % (zw - 60)
            y = zy + zh - ph * (zh + 320)
            # bold and dark enough to read against the paper: thin orange on
            # beige was invisible in grey, to the eye at a glance as much as
            # to the gate's detector — and enough of them that the rising
            # heat IS the scene's motion (a lit sheet under them measured
            # as stiller than a flat one, 2026-10-05)
            cr.set_source_rgba(*_c(P["redline"], 0.95 * ht * (1 - ph)))
            cr.set_line_width(16)
            cr.move_to(x, y)
            for j in range(1, 7):
                cr.line_to(x + 18 * math.sin(t * 3 + j + k), y - j * 24)
            cr.stroke()
    # HAZARDOUS on top of the heat, outlined so the glow cannot wash it out
    cr.move_to(zx + zw / 2 - I.text_w(cr, "HAZARDOUS", 52, "display") / 2, zy + zh / 2 + 16)
    I._face(cr, "display", 52)
    cr.text_path("HAZARDOUS")
    cr.set_source_rgba(1, 1, 1, 0.9 * rl)
    cr.set_line_width(8)
    cr.stroke_preserve()
    cr.set_source_rgba(*_c(P["redline"], rl))
    cr.fill()
    if 0 < rl < 1:   # he walks the line as it is drawn round the zone
        per = 2 * (zw + zh)
        d_ = per * rl
        if d_ < zw:
            px_, py_ = zx + d_, zy
        elif d_ < zw + zh:
            px_, py_ = zx + zw, zy + d_ - zw
        elif d_ < 2 * zw + zh:
            px_, py_ = zx + zw - (d_ - zw - zh), zy + zh
        else:
            px_, py_ = zx, zy + zh - (d_ - 2 * zw - zh)
        host("strain", px_, py_ + 10, 180)     # dragging the line round the zone
    else:                # then he fans the heat rising off the old zone
        host("hold_up" if (ht < 0.9 or u < 0.88) else "shock", mx + mw - 120,
             min(my + mh + 20, 1520), 240)
    if u < 0.45:     # the top of the frame carries the 1930s until the heat lands
        fit_readout(cr, "1930s", "a map drew these lines", 80, 520,
                    a=ease(seg(u, 0.0, 0.08)) * (1 - ease(seg(u, 0.38, 0.45))),
                    rgb=look.INK, size=150)
    fit_readout(cr, f"+{vr:.0f}°F", "hotter today in the redlined blocks", 80, 520,
                a=ease(seg(u, 0.45, 0.6)), size=150)
    text(cr, f"+{vb:.0f}°F", mx + mw - 60, zy + 80, 90, P["cow_dark"], face="display",
         anchor="right", alpha=ease(seg(u, 0.55, 0.7)), shadow=False)
    text(cr, "next door", mx + mw - 60, zy + 130, 36, P["cow_dark"], anchor="right",
         alpha=ease(seg(u, 0.55, 0.7)), shadow=False)


# ------------------------------------------------------------ BIRD FLU -----

def bird_flu_barn(cr, t, u, pts, host):
    """HERO: a red barn full of hens
    SUBSTANCE: the white hens
    CAUSE: Data shoves the big barn door shut on the flock, one push per year of deaths
    THE SHOT, not a diagram (operator 2026-10-07: "ok now we are talking"):
    a low sun upper left, hills fading into the distance, the barn in
    three-quarter view throwing a long shadow, hens right by the camera.
    Each year's toll slides the door further across the doorway: the closed
    share of it is that year's cumulative deaths over the latest total, and
    the readout prints a year only once the door has landed on it. THE SCALE
    is on the barn: each landed year leaves a notch on the track, the first
    and the latest named, so how far it closed reads at a glance."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    n = len(rows)
    top = max(v for _, v in rows) or 1.0
    a0, a1 = 0.08, 0.56                     # done by 0.56, then it HOLDS
    span = (a1 - a0) / max(1, n)
    k = int(clamp((u - a0) / span, 0, n - 0.001))
    f = clamp((u - a0 - k * span) / span)
    slide = ease(seg(f, 0.2, 0.6))           # lands on the shove, then holds
    prev = rows[k - 1][1] if k > 0 else 0.0
    frac = 0.0 if u < a0 else (prev + (rows[k][1] - prev) * slide) / top
    # the readout names only the years landed() would — the first, one
    # between, the last — so each stays up long enough to read
    landed_to = k if slide >= 0.999 else k - 1
    keep = sorted({round(i * (n - 1) / max(1, READOUT_SHOWS - 1))
                   for i in range(READOUT_SHOWS)}) if n > READOUT_SHOWS else list(range(n))
    named = max((i for i in keep if i <= landed_to), default=None)
    shown = None if (u < a0 or named is None) else rows[named]

    landscape(cr, t, "field")
    # a dirt track from the camera to the door
    cr.move_to(330, 1440)
    cr.curve_to(320, 1600, 260, 1760, 180, H)
    cr.line_to(640, H)
    cr.curve_to(560, 1760, 500, 1600, 470, 1440)
    cr.close_path()
    solid(cr, (186, 150, 104), edge=False)
    # the silo behind, then the barn
    contact_shadow(cr, 895, 1334, 190, a=0.4)
    cylinder(cr, 820, 1330, 150, 520, (196, 190, 178), finish="metal")
    cr.save()
    cr.translate(895, 810)
    cr.scale(1, 0.5)
    cr.arc(0, 0, 76, math.pi, 2 * math.pi)
    cr.restore()
    solid(cr, (120, 128, 140), finish="metal")
    b = building(cr, 150, 650, 1440, 380, (196, 56, 42), roof="gambrel")
    rx = (b["x0"] + b["x1"]) / 2
    cr.rectangle(rx - 55, b["top"] - 170, 110, 120)          # hayloft
    solid(cr, (150, 36, 30), rim=False)
    cr.set_source_rgba(*_c((244, 238, 226)))
    cr.set_line_width(8)
    cr.rectangle(rx - 55, b["top"] - 170, 110, 120)
    cr.move_to(rx - 55, b["top"] - 170)
    cr.line_to(rx + 55, b["top"] - 50)
    cr.move_to(rx + 55, b["top"] - 170)
    cr.line_to(rx - 55, b["top"] - 50)
    cr.stroke()

    # the doorway: a dark barn full of hens, warm light on the straw
    DX0, DX1, DY, GY = 230, 570, 1150, b["base"]
    dw = DX1 - DX0
    cr.save()
    cr.rectangle(DX0, DY, dw, GY - DY)
    cr.clip()
    vgrad(cr, [(0, (40, 28, 22)), (1, (96, 70, 44))], DY, GY, DX0, DX1)
    glow(cr, (DX0 + DX1) / 2, GY, 220, (230, 180, 110), 0.35)
    for i in range(7):
        hen(cr, DX0 + 40 + i * 48, GY - 30 - (i % 2) * 26, 0.7, t, i + 10,
            flip=i % 3 == 0)
    cr.restore()
    cr.set_source_rgba(*_c((244, 238, 226)))
    cr.set_line_width(12)
    cr.rectangle(DX0, DY, dw, GY - DY)
    cr.stroke()
    # the sliding door, parked left of the opening and shoved across it
    dx = DX0 - dw + dw * frac
    cr.set_source_rgba(*_c((46, 44, 48)))
    cr.set_line_width(10)
    cr.move_to(b["x0"] - 120, DY - 18)
    cr.line_to(DX1 + 30, DY - 18)
    cr.stroke()
    cr.rectangle(dx, DY - 8, dw, GY - DY + 8)
    solid(cr, (182, 48, 38))
    cr.set_source_rgba(*_c((244, 238, 226)))
    cr.set_line_width(10)
    cr.rectangle(dx + 12, DY + 6, dw - 24, GY - DY - 18)
    cr.move_to(dx + 12, DY + 6)
    cr.line_to(dx + dw - 12, GY - 12)
    cr.move_to(dx + dw - 12, DY + 6)
    cr.line_to(dx + 12, GY - 12)
    cr.stroke()
    for wx in (dx + 40, dx + dw - 40):
        disc(cr, wx, DY - 18, 11, (70, 70, 76), finish="metal")
    # THE SCALE, on the barn itself: every year the door has landed on leaves
    # a notch on the track, so a glance reads how far each year closed it
    for j in range(0, landed_to + 1):
        if u < a0:
            break
        nx = DX0 + dw * rows[j][1] / top
        cr.set_source_rgba(*_c((244, 238, 226)))
        cr.set_line_width(6)
        cr.move_to(nx, DY - 40)
        cr.line_to(nx, DY - 2)
        cr.stroke()
        first_x = DX0 + dw * rows[0][1] / top
        if j == named or (j == 0 and nx - first_x < 1 and named is not None and
                          dw * (rows[named][1] - rows[0][1]) / top > 110):
            text(cr, rows[j][0], nx, DY - 52, 30, look.INK, face="bold", anchor="center")

    # right by the camera: the rest of the flock, the grass
    for i in range(5):
        hen(cr, 600 + i * 95, 1600 + (i % 2) * 50 + i * 8, 1.35 + 0.1 * (i % 2), t, i,
            flip=i % 2 == 1)
    foreground(cr, "field")
    vignette(cr, a=0.28)

    fx = max(dx + 90, 110)
    if u < a0:
        host("point", 760, 1452, 220)
    elif u < a1 + 0.04:
        host("shove", fx, 1452, 220, beat=k)
    else:
        host("shock", fx, 1452, 220)

    if shown is not None:
        lab, v = shown
        fit_readout(cr, f"{int(round(v))}M birds", f"dead of bird flu in the US · {lab}",
                    80, 520, a=ease(seg(u, a0, a0 + 0.05)), size=130)
    else:
        fit_readout(cr, "Bird flu", f"US flocks since {rows[0][0]}", 80, 520,
                    a=ease(seg(u, 0.0, 0.05)), size=130)



#: Hand-authored TEACHER scenes, by story slug and beat. The brain is shown
#: these (and the reference) when it draws a new story's scenes.
# ------------------------------------------------------------ THE PILE ---

def heap_path(cr, cx, base, h, hw):
    """A heap's outline, a rounded mound with a ragged top, as the current
    path: `h` tall, `hw` half-wide, sitting on `base` at `cx`."""
    cr.move_to(cx - hw, base)
    for i in range(1, 32):
        x = -1 + 2 * i / 32
        y = base - h * (1 - x * x) ** 0.8 - 7 * math.sin(i * 2.3) * (1 - abs(x))
        cr.line_to(cx + hw * x, y)
    cr.line_to(cx + hw, base)
    cr.close_path()


def heap_top(cx, base, h, hw, x):
    """The y of the heap's surface above `x` (for standing Data on it)."""
    d = clamp((x - cx) / max(1.0, hw), -1.0, 1.0)
    return base - h * (1 - d * d) ** 0.8


#: The colours plastic comes in, for a pile of it.
PLASTIC = [(70, 140, 210), (232, 234, 238), (206, 62, 52), (240, 200, 64),
            (88, 176, 118), (150, 205, 225)]


def bottle(cr, x, y, ang, s, rgb, a=1.0):
    """A plastic bottle, lit, with its cap: `s` 1.0 is about 50px long."""
    cr.save()
    cr.translate(x, y)
    cr.rotate(ang)
    cr.scale(s, s)
    cr.move_to(-20, -8)
    cr.line_to(10, -8)
    cr.line_to(16, -4)
    cr.line_to(22, -4)
    cr.line_to(22, 4)
    cr.line_to(16, 4)
    cr.line_to(10, 8)
    cr.line_to(-20, 8)
    cr.close_path()
    solid(cr, rgb, finish="gloss", a=a)
    cr.rectangle(22, -5, 6, 10)
    solid(cr, (40, 90, 170), a=a, rim=False)
    cr.restore()


def recycling_pile(cr, t, u, pts, host):
    """THE PILE (2026-10-07), brain-drawn, the scene the operator picked:
    "I like the pile one but the bone one no." One number, a heap that
    triples, its old size drawn on it. Kept as the brain drew it, except its
    clock: the heap is done by 0.56 and held (PAYOFF_BY, same day).
    HERO: a towering dump of plastic waste
    SUBSTANCE: plastic bottles and bags
    CAUSE: Data tosses armfuls of plastic onto the dump and the heap grows with every throw
    The 2019 heap stands at 353 million tons; throw by throw it swells to
    the 2060 projection. Its height is the tonnage, so the 2019 heap stays
    as a dashed ghost with its top marked, and 1x/2x ticks up the side
    measure the new heap in the old one — about three times as much."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    (l0, v0), (l1, v1) = rows[0], rows[-1]
    v0 = v0 or 1.0
    ratio = v1 / v0
    n = 6
    a0, a1 = 0.08, 0.5
    span = (a1 - a0) / n
    k = int(clamp((u - a0) / span, 0, n - 0.001))
    f = clamp((u - a0 - k * span) / span)
    fly = seg(f, 0.0, 0.35)
    grow = ease(seg(f, 0.3, 0.7))
    if u < a0:
        step = 0.0
    else:
        step = (k + grow) / n
    val = v0 + (v1 - v0) * step

    CX, BASE = 600, 1440
    H0 = 250.0
    h = H0 * val / v0
    hw = min(480.0, 1.2 * h)
    h0, hw0 = H0, min(480.0, 1.2 * H0)

    landscape(cr, t, "field")
    birds(cr, t, y0=760, n=4, rgb=(60, 60, 70))

    cast_shadow(cr, CX - hw, CX + hw, BASE, length=320, a=0.3)
    contact_shadow(cr, CX, BASE + 4, 2 * hw + 60, a=0.4)
    heap_path(cr, CX, BASE, h, hw)
    solid(cr, (122, 112, 98))
    # the plastic the heap is made of, packed into its profile
    cr.save()
    heap_path(cr, CX, BASE, h, hw)
    cr.clip()
    count = int(40 + 110 * (val - v0) / max(1.0, v1 - v0) + 0.5)
    for i in range(count):
        dx = ((i * 0.6180339) % 1.0) * 1.9 - 0.95
        py = ((i * 0.4142136) % 1.0)
        px = CX + hw * dx
        top_y = heap_top(CX, BASE, h, hw, px)
        py_ = BASE - (BASE - top_y) * py * 0.95 - 6
        bottle(cr, px, py_, i * 1.7, 0.9 + 0.5 * ((i * 0.37) % 1.0),
                PLASTIC[i % len(PLASTIC)])
    cr.restore()
    heap_path(cr, CX, BASE, h, hw)
    edge(cr, (40, 36, 32))

    # THE SCALE on the heap: 2019's heap as a ghost, its top marked, ticks up the side
    if step > 0.02:
        heap_path(cr, CX, BASE, h0, hw0)
        ghost(cr, a=0.9)
        then_mark(cr, CX - 140, CX + 140, BASE - h0, l0)
        times_ticks(cr, 1010, BASE, h0, max(1, int(ratio)))

    # Data on the heap's left flank, climbing as it widens
    hx = CX - hw * 0.72
    hy = min(1500.0, heap_top(CX, BASE, h, hw, hx) + 10)

    # the armful in flight, from his hands to the summit
    if u >= a0 and 0 < fly < 1:
        sx, sy = hx + 40, hy - 190
        ex, ey = CX + 20, BASE - h - 10
        bx = sx + (ex - sx) * fly
        by = sy + (ey - sy) * fly - 260 * math.sin(math.pi * fly)
        for j in range(3):
            bottle(cr, bx + 22 * (j - 1), by + 10 * (j % 2), fly * 6 + j * 2.1, 1.6,
                    PLASTIC[(k + j) % len(PLASTIC)])

    # once the heap is done the world keeps moving, not the story: loose
    # bottles keep tumbling down its flank
    if u > a1:
        for j in range(3):
            ph = ((u - a1) / 0.16 + j / 3) % 1.0
            side = 1 if j % 2 else -1
            bx = CX + side * hw * (0.08 + 0.8 * ph)
            by = heap_top(CX, BASE, h, hw, bx) - 10
            bottle(cr, bx, by, side * ph * 9 + j, 1.5, PLASTIC[(j * 2 + 1) % len(PLASTIC)])

    # right by the camera: bottles washed out into the grass
    for i in range(5):
        bottle(cr, 120 + i * 210, 1640 + (i % 2) * 70 + i * 10, i * 0.9 + 0.3,
                2.6 + 0.4 * (i % 2), PLASTIC[(i * 2) % len(PLASTIC)])
    foreground(cr, "field")
    vignette(cr, a=0.28)

    if u < a0:
        host("point", hx, hy, 220)
    elif u < a1 + 0.04:
        host("toss", hx, hy, 220, beat=k)
    elif u < 0.9:                       # the heap is done: he holds up one more
        host("hold_up", hx, hy, 220)
    else:
        host("shock", hx, hy, 220)

    done = u >= a0 and k == n - 1 and grow >= 0.999
    if done:
        fit_readout(cr, f"{int(round(v1)):,}M tons", f"plastic waste a year · {l1}",
                    80, 520, size=130)
        text(cr, f"{ratio:.1f}x", W - 80, 650, 90, look.INK, face="display",
             anchor="right", alpha=ease(seg(u, a1, a1 + 0.05)))
    else:
        fit_readout(cr, f"{int(round(v0)):,}M tons", f"plastic waste a year · {l0}",
                    80, 520, a=ease(seg(u, 0.0, 0.05)), size=130)


def _co_cart(cr, x, y, s):
    """A shopping cart rolling past the camera, a few groceries in it."""
    contact_shadow(cr, x - 5 * s, y, 230 * s, a=0.4)
    cr.move_to(x - 105 * s, y - 175 * s)
    cr.line_to(x + 95 * s, y - 175 * s)
    cr.line_to(x + 72 * s, y - 72 * s)
    cr.line_to(x - 82 * s, y - 72 * s)
    cr.close_path()
    solid(cr, (168, 176, 188), finish="metal")
    cr.set_source_rgba(*_c((92, 98, 110)))
    cr.set_line_width(3 * s)
    for i in range(1, 8):
        fx = i / 8.0
        cr.move_to(x - 105 * s + 200 * s * fx, y - 175 * s)
        cr.line_to(x - 82 * s + 154 * s * fx, y - 72 * s)
    cr.move_to(x - 94 * s, y - 124 * s)
    cr.line_to(x + 84 * s, y - 124 * s)
    cr.stroke()
    box(cr, x - 60 * s, y - 172 * s, 46 * s, 54 * s, (214, 120, 52))
    disc(cr, x + 10 * s, y - 186 * s, 22 * s, (196, 60, 48), finish="gloss")
    box(cr, x + 34 * s, y - 172 * s, 34 * s, 70 * s, (70, 132, 196))
    cr.set_source_rgba(*_c((70, 74, 84)))
    cr.set_line_width(7 * s)
    cr.move_to(x - 105 * s, y - 175 * s)
    cr.line_to(x - 140 * s, y - 210 * s)
    cr.move_to(x - 82 * s, y - 72 * s)
    cr.line_to(x - 72 * s, y - 24 * s)
    cr.line_to(x + 64 * s, y - 24 * s)
    cr.line_to(x + 72 * s, y - 72 * s)
    cr.stroke()
    cr.set_source_rgba(*_c((200, 50, 44)))
    cr.set_line_width(12 * s)
    cr.move_to(x - 150 * s, y - 214 * s)
    cr.line_to(x - 128 * s, y - 206 * s)
    cr.stroke()
    for wx in (x - 70 * s, x + 60 * s):
        disc(cr, wx, y - 12 * s, 12 * s, (40, 40, 46))


def _co_basket(cr, x, y, s):
    """A red hand basket on the floor by the camera, its handle up."""
    contact_shadow(cr, x, y, 200 * s, a=0.4)
    cr.move_to(x - 95 * s, y - 90 * s)
    cr.line_to(x + 95 * s, y - 90 * s)
    cr.line_to(x + 78 * s, y)
    cr.line_to(x - 78 * s, y)
    cr.close_path()
    solid(cr, (200, 50, 44), finish="gloss")
    cr.set_source_rgba(*_c((120, 26, 22)))
    cr.set_line_width(4 * s)
    for i in range(1, 6):
        cr.move_to(x - 95 * s + 190 * s * i / 6, y - 84 * s)
        cr.line_to(x - 78 * s + 156 * s * i / 6, y - 6 * s)
    cr.stroke()
    box(cr, x - 50 * s, y - 80 * s, 40 * s, 50 * s, (232, 220, 190), depth=10 * s)
    disc(cr, x + 20 * s, y - 96 * s, 20 * s, (226, 170, 40), finish="gloss")
    cr.set_source_rgba(*_c((60, 62, 70)))
    cr.set_line_width(8 * s)
    cr.arc(x, y - 90 * s, 70 * s, math.pi * 1.05, math.pi * 1.95)
    cr.stroke()


def _co_till(cr, x, y, s, a):
    """A staffed checkout: a cashier in a green apron behind a belt counter."""
    if a <= 0.01:
        return
    contact_shadow(cr, x + 50 * s, y, 130 * s, a=0.3 * a)
    cr.move_to(x + 40 * s, y - 60 * s)
    cr.line_to(x + 82 * s, y - 60 * s)
    cr.line_to(x + 76 * s, y - 178 * s)
    cr.line_to(x + 46 * s, y - 178 * s)
    cr.close_path()
    solid(cr, (46, 130, 90), a=a)
    disc(cr, x + 61 * s, y - 200 * s, 21 * s, (222, 178, 140), a=a)
    box(cr, x, y, 100 * s, 110 * s, (150, 152, 160), depth=34 * s, a=a)
    cr.rectangle(x + 4 * s, y - 120 * s, 70 * s, 10 * s)
    solid(cr, (30, 30, 34), finish="gloss", a=a, rim=False)
    box(cr, x + 74 * s, y - 110 * s, 24 * s, 30 * s, (60, 62, 70), depth=8 * s, a=a)
    for i in range(2):
        box(cr, x + 10 * s + i * 30 * s, y - 120 * s, 20 * s, 22 * s + 8 * s * i,
            [(214, 120, 52), (70, 132, 196)][i], depth=6 * s, a=a)


def _co_kiosk(cr, x, y, s, a, drop):
    """A self-checkout kiosk: a tall pillar, a tilted screen, a bagging stand."""
    if a <= 0.01:
        return
    yy = y - drop
    contact_shadow(cr, x + 50 * s, y, 120 * s, a=0.35 * a)
    box(cr, x + 72 * s, yy, 30 * s, 100 * s, (176, 180, 190), depth=10 * s, a=a)
    cr.move_to(x + 74 * s, yy - 100 * s)
    cr.line_to(x + 104 * s, yy - 100 * s)
    cr.line_to(x + 100 * s, yy - 140 * s)
    cr.line_to(x + 78 * s, yy - 140 * s)
    cr.close_path()
    solid(cr, (236, 236, 230), a=a)
    box(cr, x + 8 * s, yy, 60 * s, 200 * s, (206, 210, 218), depth=20 * s,
        finish="metal", a=a)
    cr.move_to(x + 2 * s, yy - 198 * s)
    cr.line_to(x + 78 * s, yy - 198 * s)
    cr.line_to(x + 72 * s, yy - 262 * s)
    cr.line_to(x + 8 * s, yy - 262 * s)
    cr.close_path()
    solid(cr, (24, 30, 42), finish="glass", a=a)
    cr.move_to(x + 10 * s, yy - 204 * s)
    cr.line_to(x + 70 * s, yy - 204 * s)
    cr.line_to(x + 66 * s, yy - 256 * s)
    cr.line_to(x + 14 * s, yy - 256 * s)
    cr.close_path()
    cr.set_source_rgba(*_c(P["accent2"], 0.8 * a))
    cr.fill()
    cr.rectangle(x + 16 * s, yy - 150 * s, 44 * s, 8 * s)
    cr.set_source_rgba(*_c((230, 60, 50), 0.9 * a))
    cr.fill()


def _co_at(L, z):
    z = clamp(z, 0, len(L) - 1)
    i = int(z)
    if i >= len(L) - 1:
        return L[-1]
    f = z - i
    return tuple(p + (q - p) * f for p, q in zip(L[i], L[i + 1]))


def checkout_lanes(cr, t, u, pts, host):
    """THE CHECKOUT (2026-10-09), brain-drawn, the opening the operator called
    "perfect, beautiful ... what I want everything to look like. And it had
    the creativity." Kept exactly as the brain drew it for the posted
    self-checkout video, helpers renamed only. His one note, for every
    scene after it: Data could have pushed a shopping cart down the line as
    each cashier gave way to a kiosk — he is IN the story, not beside it.
    HERO: a supermarket's row of checkout lanes
    SUBSTANCE: self-checkout kiosks
    CAUSE: Data places a self-checkout kiosk into each cashier lane, replacing the cashier, lane after lane
    Inside one supermarket, its ten checkout lanes running from right by the
    camera back into the store: the WHOLE is the front end. Each year Data
    sets kiosks down into lanes, working from the far end toward the camera,
    and the cashier there is gone, until that year's share of lanes is
    self-checkout; the overhead sign is cut at the exact share, the
    SELF-CHECKOUT part in the accent, and every landed year leaves a notch on
    it. Done by 0.56 and held: one cashier lane is left, nearest the camera,
    and carts keep rolling past."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    n = len(rows)
    N = 10
    a0, a1 = 0.08, 0.56
    span = (a1 - a0) / max(1, n)
    k = int(clamp((u - a0) / span, 0, n - 0.001))
    f = clamp((u - a0 - k * span) / span)
    slide = ease(seg(f, 0.05, 0.85))
    prev = rows[k - 1][1] if k > 0 else 0.0
    share = 0.0 if u < a0 else clamp((prev + (rows[k][1] - prev) * slide) / 100.0)
    landed_to = k if slide >= 0.999 else k - 1
    keep = sorted({round(i * (n - 1) / max(1, READOUT_SHOWS - 1))
                   for i in range(READOUT_SHOWS)}) if n > READOUT_SHOWS else list(range(n))
    named = max((i for i in keep if i <= landed_to), default=None)
    shown = None if (u < a0 or named is None) else rows[named]

    # the lanes, big by the camera on the left, running back to the right
    lanes = []
    x, y, s = 50.0, 1440.0, 2.0
    for j in range(N + 1):
        lanes.append((x, y, s))
        x += 70 * s
        y -= 30 * s
        s *= 0.9

    # which year turns which lane over — rank 0 is the FAR lane
    step_of = []
    for r in range(N):
        thr = (r + 0.5) / N * 100.0
        step_of.append(next((i for i in range(n) if rows[i][1] >= thr), None))
    now = [r for r in range(N) if step_of[r] == k]
    conv_r = []
    for r in range(N):
        sr = step_of[r]
        if u < a0 or sr is None or sr > k:
            conv_r.append(0.0)
        elif sr < k:
            conv_r.append(1.0)
        else:
            q = now.index(r)
            conv_r.append(clamp((slide * (len(now) + 1) - q) / 2.0))
    conv = [conv_r[N - 1 - j] for j in range(N)]

    # the store: a warm ceiling with light panels running back into it
    vgrad(cr, [(0, (70, 66, 64)), (0.5, (168, 160, 148)), (1, (214, 206, 190))], 0, 1100)
    for i in range(8):
        z = i / 7.0
        lx = 40 + 900 * z ** 0.8
        ly = 140 + 560 * z ** 0.9
        sc = 1.0 - 0.7 * z
        glow(cr, lx + 90 * sc, ly, 200 * sc, (255, 240, 205), 0.4)
        box(cr, lx, ly, 180 * sc, 22 * sc, (246, 242, 230), depth=40 * sc)
    # the far aisles: tall stocked shelving under haze
    vgrad(cr, [(0, (176, 170, 160)), (1, (120, 114, 106))], 1080, H)
    for i in range(10):
        bx = 10 + i * 108
        hgt = 420 - i * 14
        contact_shadow(cr, bx + 45, 1100, 110, a=0.25)
        box(cr, bx, 1100, 92, hgt, (142, 134, 122), depth=18)
        rows_n = int(hgt // 62)
        for r_ in range(rows_n):
            cr.rectangle(bx + 2, 1100 - 8 - r_ * 62, 90, 5)
            cr.set_source_rgba(*_c((90, 84, 76)))
            cr.fill()
            for c_ in range(4):
                col = [(190, 70, 60), (214, 168, 70), (80, 124, 170), (110, 156, 90)][(i + r_ + c_) % 4]
                cr.rectangle(bx + 6 + c_ * 21, 1100 - 48 - r_ * 62, 17, 38)
                cr.set_source_rgba(*_c(col, 0.9))
                cr.fill()
    haze(cr, 600, 1110, (200, 194, 182), a=0.55)
    # a polished floor running to the camera
    cr.save()
    cr.rectangle(0, 1100, W, H - 1100)
    cr.clip()
    cr.set_source_rgba(*_c((90, 84, 76), 0.3))
    cr.set_line_width(3)
    for i in range(14):
        cr.move_to(1300, 1000)
        cr.line_to(-900 + i * 200, H)
    cr.stroke()
    cr.restore()
    glow(cr, 540, 1350, 560, (255, 236, 200), 0.2)
    cast_shadow(cr, lanes[0][0], lanes[N][0] + 40, 1450, length=240, a=0.2)

    # the lanes, far first
    for j in reversed(range(N)):
        lx, ly, ls = lanes[j]
        c = conv[j]
        cr.rectangle(lx + 88 * ls, ly - 300 * ls, 6 * ls, 190 * ls)
        solid(cr, (70, 72, 80), finish="metal", rim=False)
        lit = P["accent2"] if c > 0.5 else (240, 214, 140)
        glow(cr, lx + 91 * ls, ly - 300 * ls, 30 * ls, lit, 0.6)
        disc(cr, lx + 91 * ls, ly - 300 * ls, 12 * ls, lit, finish="gloss")
        _co_till(cr, lx, ly + 30 * ls * clamp(c / 0.45), ls, 1.0 - clamp(c / 0.45))
        d = clamp((c - 0.35) / 0.65)
        _co_kiosk(cr, lx, ly, ls, clamp(d * 3), (1 - pop(d)) * 260 * ls)

    # the overhead sign over the whole front end, cut at the share
    def _band(z0, z1, rgb):
        if z1 - z0 < 0.01:
            return
        top, bot = [], []
        for i in range(13):
            bx_, by_, bs_ = _co_at(lanes, z0 + (z1 - z0) * i / 12)
            top.append((bx_, by_ - 340 * bs_))
            bot.append((bx_, by_ - 340 * bs_ + 44 * bs_))
        cr.move_to(*top[0])
        for p_ in top[1:]:
            cr.line_to(*p_)
        for p_ in reversed(bot):
            cr.line_to(*p_)
        cr.close_path()
        solid(cr, rgb)
    L = share * N
    cut = N - L
    cr.set_source_rgba(*_c((60, 62, 70)))
    cr.set_line_width(4)
    for z in (0.4, 4.0, 8.0):
        bx_, by_, bs_ = _co_at(lanes, z)
        cr.move_to(bx_, by_ - 340 * bs_)
        cr.line_to(bx_, by_ - 340 * bs_ - 200)
    cr.stroke()
    _band(0, cut, (150, 152, 158))
    _band(cut, N, P["accent2"])
    if L > 3.0:
        tx_, ty_, ts_ = _co_at(lanes, cut + 0.3)
        text(cr, "SELF-CHECKOUT", tx_ + 6, ty_ - 340 * ts_ + 32 * ts_,
             max(20, int(22 * ts_)), look.INK, face="bold", shadow=False)
    if u >= a0:
        for j in range(0, landed_to + 1):
            nx, ny, ns = _co_at(lanes, N - rows[j][1] / 100.0 * N)
            cr.set_source_rgba(*_c((244, 238, 226)))
            cr.set_line_width(6)
            cr.move_to(nx, ny - 340 * ns - 6)
            cr.line_to(nx, ny - 340 * ns + 50 * ns)
            cr.stroke()
            if j == named or (j == 0 and named is not None and named != 0):
                text(cr, rows[j][0], nx, ny - 340 * ns - 18, 30, look.INK,
                     face="bold", anchor="center")

    # right by the camera: carts rolling through, a basket on the floor
    for j in range(2):
        cx = -240 + ((t * 190 + j * 780) % 1560)
        _co_cart(cr, cx, 1790 + j * 60, 1.35 + 0.15 * j)
    _co_basket(cr, 940, 1880, 1.3)
    vignette(cr, a=0.28)

    # Data works his way from the far lane toward the camera
    P_ = sum(conv)
    dx_, dy_, ds_ = _co_at(lanes, clamp(N - P_ - 0.5, 0, N - 1))
    hx, hy = dx_ + 30 * ds_, min(1500.0, dy_ + 50 * ds_)
    hh = clamp(120 * ds_, 180, 240)
    if u < a0:
        hx, hy, hh = lanes[N - 1][0] + 30 * lanes[N - 1][2], lanes[N - 1][1] + 50 * lanes[N - 1][2], 180
        host("point", hx, hy, hh)
    elif u < a1 + 0.04:
        host("place", hx, hy, hh, beat=k)
    else:
        host("hold_up", hx, hy, hh)

    if shown is not None:
        lab, v = shown
        fit_readout(cr, f"{int(round(v))}%", f"of major grocery chains have self-checkout · {lab}",
                    80, 520, a=ease(seg(u, a0, a0 + 0.05)), size=130)
    else:
        fit_readout(cr, "Self-checkout", f"major grocery chains, {rows[0][0]}–{rows[-1][0]}",
                    80, 520, a=ease(seg(u, 0.0, 0.05)), size=130)


TEACHERS = {
    "amazon-still-shrinking": [amazon_clearing, amazon_vs_france,
                               amazon_where_it_goes],
    # beat 2 is the brain's: its teacher re-ran coffee_climb's balance, and
    # the judge marked the video down for showing the same machine twice
    "coffee-price-record": [coffee_climb, coffee_drought],
    "urban-heat-island-redlining": [heat_by_city, heat_share, heat_redlining],
    # THE SHOT (2026-10-07): beats 1-2 are the brain's, drawn from this one
    "bird-flu-species-jump": [bird_flu_barn],
    # THE PILE (2026-10-07): beats 1-2 are the brain's
    "recycling-myth-reality": [recycling_pile],
}


#: The CLOSING scene per story, with the beat whose data it draws. The
#: closing lands the story's last line as a picture of its own, full bleed
#: — never the last beat shrunk into an inset under a card, which the
#: showrunner scored payoff 1/2 on the 74 (2026-09-23).
CLOSINGS = {
    "amazon-still-shrinking": (amazon_bill_grows, 0),
}


def closing_for(slug: str):
    """(closing scene, index of the beat whose data it draws), or None."""
    return CLOSINGS.get(slug)


#: Hand-drawn HOOK scenes. None yet: the brain draws each story's hook from
#: its hook line (scene_author.HOOK_BRIEF), verified like every scene.
HOOKS: dict = {}


def hook_for(slug: str):
    """(hook scene, index of the beat whose data it draws), or None."""
    return HOOKS.get(slug)


def scene_for(slug: str, index: int):
    """The subject scene for beat `index` of story `slug`, or None."""
    fns = TEACHERS.get(slug) or []
    return fns[index] if 0 <= index < len(fns) else None


def render_build(scene, insight, out_dir, name, frames, t0=0.0):
    """Render one beat's subject scene to `<name>_build%02d.png` (opaque,
    1080x1920) — the same frame contract every other visual uses."""
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pts = [(str(getattr(p, "label", "")), float(getattr(p, "value", 0) or 0))
           for p in (getattr(insight, "items", None) or [])]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    global _SCENE_KEY
    _prev_key, _SCENE_KEY = _SCENE_KEY, name
    try:
        _render_frames(scene, insight, out_dir, name, frames, pts, surf)
    finally:
        _SCENE_KEY = _prev_key
    insight.host_baked = True
    return str(out_dir / f"{name}_build%02d.png"), []


#: Where the narration is burned in (studio_render: anchored at y=1734,
#: two lines reach ~1560). A full-bleed scene put its clouds and bricks
#: right under it: "subtitles lost in clouds and bricks" held a 79.
SCRIM_TOP = 1480


def caption_scrim(cr):
    """A soft dark fade at the foot of every scene, under the captions.
    Not a card: no edge, no border — the scene just darkens toward the
    bottom, the way a film darkens under its subtitles."""
    g = cairo.LinearGradient(0, SCRIM_TOP, 0, H)
    g.add_color_stop_rgba(0.0, 0.02, 0.03, 0.07, 0.0)
    g.add_color_stop_rgba(0.45, 0.02, 0.03, 0.07, 0.45)
    g.add_color_stop_rgba(1.0, 0.02, 0.03, 0.07, 0.72)
    cr.set_source(g)
    cr.rectangle(0, SCRIM_TOP, W, H - SCRIM_TOP)
    cr.fill()


#: How long one of Data's acts takes to play, in seconds. An act is an arc
#: (set up, do it, land it); it plays ONCE when his role changes and then
#: holds its last pose until the story gives him the next thing to do. It
#: used to loop every four seconds for the whole beat — arms going all the
#: time, which read as flailing.
ACT_S = 1.1


def act_phase(clock: dict, role, f: int, fps: int = 30) -> float:
    """The act's clock 0..1 at frame f: it restarts when `role` changes and
    holds at 1 once the act has played. `role` may be a (role, beat) pair:
    a scene advances `beat` each time the thing changes, and the act plays
    again — one pick swing per crack, never a wobble (2026-10-02)."""
    if clock.get("role") != role:
        clock["role"], clock["start"] = role, f
    return min(1.0, (f - clock["start"]) / (ACT_S * fps))


def _render_frames(scene, insight, out_dir, name, frames, pts, surf):
    clock: dict = {}
    # PACED to its window (operator, 2026-10-09: "some animations hold too
    # long at the end after all the cool stuff has already happened"). A
    # scene that finishes its story early is stretched to land by the
    # beat's `land_by`, so the build fills the beat and only the last
    # moments are the held picture.
    from data_learning import scene_author as _sa
    secs = frames / 30.0
    try:
        landed = _sa.landed_at(scene, pts)
    except Exception:  # noqa: BLE001 — unmeasurable: drawn as authored
        landed = None
    target = _sa.land_by(secs)
    for f in range(frames):
        cr = cairo.Context(surf)

        def host(role, x, fy, h, pace=False, beat=0, _cr=cr, _f=f):
            place_host(_cr, role, act_phase(clock, (role, int(beat)), _f),
                       insight, x, fy, h, _f / 30.0, pace)
        with I.text_layer(cr):          # labels are painted last, on top
            scene(cr, f / 30.0,
                  _sa.paced(f / max(1, frames - 1), landed, target), pts, host)
            I.finish(cr, I.FINISH)      # one key light over the whole frame
        caption_scrim(cr)
        surf.flush()
        surf.write_to_png(str(out_dir / f"{name}_build{f + 1:02d}.png"))
