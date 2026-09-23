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

P = look.SCENES


def vgrad(cr, stops, y0=0, y1=H, x0=0, x1=W):
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
_MOTES = [(_R.uniform(0, W), _R.uniform(0, H), _R.uniform(1.5, 4), _R.uniform(0.3, 1))
          for _ in range(90)]


def tree(cr, x, base, s, lit, shade, trunk, lean=0.0, a=1.0):
    """A rainforest tree: a trunk and a two-tone crown of three lobes.
    `lean` 0..1 topples it (radians = lean * 1.45)."""
    if s <= 0.02 or a <= 0.0:
        return
    cr.save()
    cr.translate(x, base)
    cr.rotate(lean * 1.45)
    cr.scale(s, s)
    cr.set_source_rgba(*_c(trunk, a))
    cr.rectangle(-7, -120, 14, 120)
    cr.fill()
    for dx, dy, r, col in ((-34, -128, 44, shade), (32, -132, 46, shade),
                           (0, -170, 56, lit), (-20, -140, 40, lit)):
        cr.set_source_rgba(*_c(col, a))
        cr.arc(dx, dy, r, 0, 2 * math.pi)
        cr.fill()
    cr.set_source_rgba(*_c(P["rim_leaf"], 0.55 * a))
    cr.arc(-10, -186, 30, math.pi * 1.1, math.pi * 1.7)
    cr.set_line_width(5)
    cr.stroke()
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
    cr.set_source_rgba(*_c(body, a))
    cr.save()
    cr.scale(1, 0.6)
    cr.arc(0, 0, 40, 0, 2 * math.pi)
    cr.restore()
    cr.fill()
    cr.set_source_rgba(*_c(patch, a))
    cr.arc(-12, -6, 12, 0, 2 * math.pi)
    cr.fill()
    cr.arc(16, 4, 9, 0, 2 * math.pi)
    cr.fill()
    dip = 10 * (0.5 + 0.5 * math.sin(t * 2.2 + x))
    cr.set_source_rgba(*_c(body, a))
    cr.arc(44, -4 + dip, 15, 0, 2 * math.pi)
    cr.fill()
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
    cr.set_source_rgba(*_c(P["truck"], a))
    cr.rectangle(-50, -34, 70, 34)
    cr.fill()
    cr.set_source_rgba(*_c(P["truck_cab"], a))
    cr.rectangle(20, -26, 30, 26)
    cr.fill()
    cr.set_source_rgba(*_c(P["log"], a))
    for k in range(3):
        cr.arc(-40 + k * 22, -40, 11, 0, 2 * math.pi)
        cr.fill()
    cr.set_source_rgba(*_c(P["cow_dark"], a))
    for wx in (-34, 0, 34):
        cr.arc(wx, 2, 9, 0, 2 * math.pi)
        cr.fill()
    cr.restore()


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
    return PACE_AMP * math.sin(2 * math.pi * t / PACE_PERIOD)


def place_host(cr, role, phase, insight, x, fy, h, t, pace=True):
    """Put Data in the scene at (x, fy), walking his stride — unless the
    scene has him doing something precise (climbing, tracing), when he
    holds his line."""
    return I._host(cr, role, phase, insight, "scene",
                   clamp(x + (stride(t) if pace else 0.0), 70, W - 70), fy, h)


def motes(cr, t, rgb, speed=24, a=0.22):
    """The air is never still: pollen, dust, mist or steam drifting across the
    whole frame. Sized and paced to REGISTER at the showrunner's scale (a
    192px-wide frame, a block must change by 6 grey levels): faint 2px motes
    drifting at 20px/s left every finished scene 40-96% held frames."""
    # the reference's deep-sea snow streams at 120-1020 px/s; slow drift
    # does not register at the gate's 24fps sampling at all
    sp = math.copysign(max(abs(speed) * 3.2, 200.0), speed or 1)
    for x, y, r, k in _MOTES:
        yy = (y + t * sp * k) % H
        xx = x + 26 * math.sin(t * 1.3 + k * 9)
        glow(cr, xx, yy, r * 5.0, rgb, min(0.5, a * 1.6 * k))
        cr.set_source_rgba(*_c(rgb, min(0.75, a * 2.6 * k)))
        cr.arc(xx, yy, r * 2.2, 0, 2 * math.pi)
        cr.fill()


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
    """Deforestation by year: the forest stands; each year a batch of trees
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
    k = min(n - 1, int(u * n * 1.02))
    year, val = pts[k]
    felled = sum(round(v / 1000.0) for _, v in pts[:k])
    batch = round(val / 1000.0)
    fb = seg(u * n - k, 0.0, 0.7)            # this year's batch topples
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
    motes(cr, t, P["mist"])
    fx = (felled + batch * fb) / max(1, len(stand)) * W
    host("climb" if val > 12000 else "cheer", clamp(fx + 90, 120, W - 120),
         FOREST_Y + 360, 230)
    fit_readout(cr, f"{int(val):,} km²", f"of rainforest cleared in {year}",
                80, 520, a=ease(seg(u, 0.0, 0.08)))
    text(cr, year, W - 80, 520, 64, look.INK, face="display", anchor="right",
         alpha=ease(seg(u, 0.0, 0.08)))


SCAR = (W / 2, 1270, 470)


def scar_path(cr):
    """The cleared scar, an organic patch; scenes 2 and 3 share it so the
    land France fell onto is the land that becomes pasture."""
    cx, cy, R = SCAR
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
    """750,000 km² lost vs France: France drops onto the cleared land with a
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
    motes(cr, t, P["dust"], speed=10, a=0.3)
    if u > 0.40:
        host("cheer" if u > 0.55 else "shock", cx + 30, fy - 8, 190)
        cr.set_source_rgba(*_c(look.INK))
        cr.set_line_width(5)
        cr.move_to(cx + 90, fy - 8)
        cr.line_to(cx + 90, fy - 150)
        cr.stroke()
        cr.set_source_rgba(*_c(P["flag"]))
        cr.move_to(cx + 90, fy - 150)
        cr.line_to(cx + 160, fy - 132 + 5 * math.sin(t * 6))
        cr.line_to(cx + 90, fy - 114)
        cr.close_path()
        cr.fill()
    else:
        host("point", cx - R + 40, cy - 40, 190)
    fit_readout(cr, f"{int(lost):,} km²", "of Amazon lost since 1970", W / 2, 470,
                anchor="center", a=ease(seg(u, 0.0, 0.1)))
    b = seg(u, 0.58, 0.8)
    if b > 0:
        diff = int(lost - fra)
        fit_readout(cr, f"{diff:,} km² more", f"than all of {lf.title() if lf.isupper() else 'France'}",
                    W / 2, 1690 - 160, anchor="center", a=ease(b), rgb=P["accent2"], size=78)


def amazon_where_it_goes(cr, t, u, pts, host):
    """What the cleared land becomes: grass spreads across that share of the
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
    cr.set_source_rgba(*_c(P["scar"]))
    cr.fill()
    x0, x1 = cx - R * 1.1, cx + R * 1.1
    split = x0 + (x1 - x0) * share * ease(seg(u, 0.05, 0.5))
    cr.save()
    scar_path(cr)
    cr.clip()
    cr.set_source_rgba(*_c(P["pasture"]))
    cr.rectangle(x0, 0, split - x0, H)
    cr.fill()
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
              + (stride(t) if k == 0 else 0.0))
        if hx > split - 40:
            continue
        s_ = 1.25 * pop(seg(u, 0.2 + k * 0.06, 0.3 + k * 0.06))
        cow(cr, hx, cy + R * 0.62 * fy, s_, t)
        if k == 0:
            lead = (hx, cy + R * 0.62 * fy)
    tx = x0 + (x1 - x0) * (share + (1 - share) / 2)
    la = ease(seg(u, 0.45, 0.6))
    truck(cr, tx + 30 * math.sin(t * 0.5), cy - 30, 1.2, a=la)
    for k in range(5):                        # the log pile
        cr.set_source_rgba(*_c(P["log"], la))
        cr.arc(tx - 40 + (k % 3) * 26 + (k // 3) * 13, cy + 90 - (k // 3) * 22, 13,
               0, 2 * math.pi)
        cr.fill()
    motes(cr, t, P["dust"], speed=12, a=0.25)
    if lead:   # he rides the lead cow: its walk is already his stride
        host("cheer", lead[0] - 4 - stride(t), lead[1] - 20, 180)
    else:
        host("point", x0 + 60, cy, 180)
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
    cr.set_source_rgba(*_c(P["counter_top"]))
    cr.rectangle(0, counter, W, 40)
    cr.fill()
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
    cr.set_source_rgba(*_c(P["cow"]))
    cr.move_to(-70, -120)
    cr.line_to(70, -120)
    cr.line_to(56, 0)
    cr.line_to(-56, 0)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(*_c(P["bean"]))
    cr.save()
    cr.translate(0, -120)
    cr.scale(1, 0.25)
    cr.arc(0, 0, 66, 0, 2 * math.pi)
    cr.restore()
    cr.fill()
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
    cr.set_source_rgba(*_c(P["sack"], a))
    cr.move_to(-46, 0)
    cr.curve_to(-54, -40, -44, -86, -30, -96)
    cr.line_to(30, -96)
    cr.curve_to(44, -86, 54, -40, 46, 0)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(*_c(P["sack_shade"], a))
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
    """The price of a pound of coffee, by year: a pound of beans on one pan
    of a brass scale, and the money on the other — one coin per 25 cents,
    piling up as the years tick. The pile IS the price."""
    rows = by_time([(str(l), float(v)) for l, v in pts])
    n = len(rows)
    CT = 1560                                  # the counter top
    cafe(cr, t, wy=(560, 1200), counter=CT)
    k = min(n - 1, int(u * n * 1.02))
    year, price = rows[k]
    prev = rows[k - 1][1] if k else price
    f = ease(seg(u * n - k, 0.0, 0.5))
    shown = prev + (price - prev) * f
    coins = shown / 0.25
    # the scale: beam tips toward the heavier (costlier) side a little
    cx, py = W / 2, 1050
    # the money side sinks as it outweighs the pound of beans
    tilt = clamp((coins - 6) / 14 * 0.16, -0.10, 0.18)
    cr.set_source_rgba(*_c(P["brass_shade"]))
    cr.rectangle(cx - 16, py, 32, CT - py)
    cr.fill()
    cr.rectangle(cx - 120, CT - 22, 240, 22)
    cr.fill()
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
        cr.set_source_rgba(*_c(P["brass"]))
        cr.save()
        cr.translate(px, pyy + 236)
        cr.scale(1, 0.22)
        cr.arc(0, 0, 140, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
    # a pound of beans on the left pan
    sack(cr, lx, ly + 232, 1.9)
    # the money on the right pan: whole coins, the last one arriving
    whole = int(coins)
    hand = (W - 110 + stride(t) - 40, CT - 170)     # Data's hand
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
    motes(cr, t, P["mist"], speed=14, a=0.18)
    moving = abs(price - prev) > 1e-9 and f < 1
    hx = W - 110 + stride(t) * 0.3
    bag = (hx - 60, CT - 250)                 # the bag he holds up, tipped
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
    host("hold_up" if moving else "cheer", hx, CT, 240, pace=False)
    fit_readout(cr, f"${shown:.2f}", f"a pound of arabica, {year}", 80, 520,
                a=ease(seg(u, 0.0, 0.06)), size=150)
    text(cr, year, W - 80, 520, 64, look.INK, face="display", anchor="right",
         alpha=ease(seg(u, 0.0, 0.06)))


def coffee_drought(cr, t, u, pts, host):
    """Brazil's crop forecast cut by drought: sacks stacked at the farm gate,
    the ground cracking, and the lost share of the pile crumbling to dust —
    the gap between the two estimates."""
    rows = [(str(l), float(v)) for l, v in pts[:2]]
    (l0, before), (l1, after) = rows if rows[0][1] >= rows[1][1] else rows[::-1]
    vgrad(cr, P["drought_sky"], 0, 1100)
    glow(cr, 760, 560, 420, P["sun_hot"], 0.85 + 0.1 * math.sin(t * 2))
    cr.set_source_rgba(*_c(P["sun_hot"]))
    cr.arc(760, 560, 110, 0, 2 * math.pi)
    cr.fill()
    vgrad(cr, P["dry_soil"], 1060, H)
    dry = ease(seg(u, 0.15, 0.6))
    for i in range(16):                      # coffee shrubs on the hills
        x = 40 + i * 68
        col = tuple(int(a + (b - a) * dry) for a, b in zip(P["shrub"], P["shrub_dry"]))
        cr.set_source_rgba(*_c(col))
        cr.arc(x, 1080 + 12 * (i % 3), 34, 0, 2 * math.pi)
        cr.fill()
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
    lost = ease(seg(u, 0.35, 0.8))
    idx = 0
    per_row = [11, 10, 9, 7, 5, 3]
    for r_, cnt in enumerate(per_row):
        for c in range(cnt):
            if idx >= total:
                break
            x = 540 - (cnt - 1) * 38 + c * 76
            y = 1440 - r_ * 74
            gone = idx >= keep
            a = 1.0 - (lost if gone else 0.0)
            sack(cr, x, y + (60 * lost if gone else 0), 0.8, a=a, label=False)
            if gone and 0 < lost < 1:
                cr.set_source_rgba(*_c(P["dust"], 0.5 * (1 - lost)))
                cr.arc(x, y - 30 - 80 * lost, 20 + 30 * lost, 0, 2 * math.pi)
                cr.fill()
            idx += 1
    heat_shimmer(cr, t, 900, 1600, a=0.22)
    motes(cr, t, P["dust"], speed=-20, a=0.3)
    host("strain" if 0.05 < lost < 0.95 else ("shock" if lost >= 0.95 else "point"),
         280, 1560, 220)
    shown = before - (before - after) * lost
    fit_readout(cr, f"{shown:.1f}M bags", "Brazil's arabica crop forecast", 80, 520,
                a=ease(seg(u, 0.0, 0.08)), size=130)
    b = ease(seg(u, 0.7, 0.85))
    if b > 0:
        fit_readout(cr, f"{before - after:.0f} million bags gone", "overnight",
                    W / 2, 800, anchor="center", a=b, rgb=P["accent2"], size=64)


def coffee_doubled(cr, t, u, pts, host):
    """A year apart, on the same scale: last February's pile of coins for a
    pound of beans, and Data tossing on the rest until it is this February's
    — the pile more than doubles in front of you."""
    rows = by_time([(str(l), float(v)) for l, v in pts[:2]])
    coffee_climb(cr, t, u, rows, host)        # first half: 2024's pile
    (l0, v0), (l1, v1) = rows
    b = ease(seg(u, 0.8, 0.92))
    if b > 0 and v0:
        fit_readout(cr, f"{v1 / v0:.1f}x", "in twelve months", W / 2, 820,
                    anchor="center", a=b, rgb=P["accent2"], size=110)


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
    cr.set_source_rgba(*_c(lit))
    cr.rectangle(x, base - h, w * 0.7, h)
    cr.fill()
    cr.set_source_rgba(*_c(shade))
    cr.rectangle(x + w * 0.7, base - h, w * 0.3, h)
    cr.fill()
    cr.set_source_rgba(*_c(shade))
    cr.move_to(x - 6, base - h)
    cr.line_to(x + w / 2, base - h - 40)
    cr.line_to(x + w + 6, base - h)
    cr.close_path()
    cr.fill()
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
            cr.set_source_rgba(*_c(P["trunk"]))
            cr.rectangle(x + dx + 20, base - 110, 12, 110)
            cr.fill()
            cr.set_source_rgba(*_c(P["treeleaf"]))
            cr.arc(x + dx + 26, base - 140 + 4 * math.sin(t * 1.5 + x), 52, 0, 2 * math.pi)
            cr.fill()


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
        cr.set_source_rgba(*_c(col))
        cr.rectangle(x - 70, lane - 34, 140, 34)
        cr.fill()
        cr.rectangle(x - 40, lane - 58, 80, 26)
        cr.fill()
        cr.set_source_rgba(*_c(P["glass"], 0.9))
        cr.rectangle(x - 32, lane - 54, 64, 18)
        cr.fill()
        cr.set_source_rgba(*_c(P["cow_dark"]))
        for wx in (-44, 44):
            cr.arc(x + wx, lane, 14, 0, 2 * math.pi)
            cr.fill()


def heat_by_city(cr, t, u, pts, host):
    """Added heat by city: a street thermometer on a lamppost; the city name
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
    k = min(n - 1, int(u * n * 1.02))
    city, deg = rows[k]
    prev = rows[k - 1][1] if k else 0.0
    shown = prev + (deg - prev) * ease(seg(u * n - k, 0.0, 0.5))
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
    host("climb" if rising else "strain", tx - 96, t1 - mh + 150, 200,
         pace=False)
    fit_readout(cr, f"+{shown:.1f}°F", f"extra heat from pavement · {city}", 80, 520,
                a=ease(seg(u, 0.0, 0.06)), size=140)


def heat_share(cr, t, u, pts, host):
    """Who lives in the hottest blocks: one street, the hot share of it
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
    """The 1930s map: a paper city map with the redlined zone outlined in
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
    cr.set_source_rgba(*_c(P["paper"]))
    cr.rectangle(mx, my, mw, mh)
    cr.fill()
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
        for k in range(16):                    # heat waves rise off the zone
            ph = (t * 0.45 + k / 16) % 1
            x = zx + 30 + (k * 53) % (zw - 60)
            y = zy + zh - ph * (zh + 320)
            cr.set_source_rgba(*_c(P["heat"], 0.9 * ht * (1 - ph)))
            cr.set_line_width(7)
            cr.move_to(x, y)
            for j in range(1, 6):
                cr.line_to(x + 14 * math.sin(t * 3 + j + k), y - j * 22)
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
        host("point", px_, py_ + 10, 180, pace=False)
    else:
        host("point", mx + mw - 120, my + mh + 20, 240)
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


#: Hand-authored TEACHER scenes, by story slug and beat. The brain is shown
#: these (and the reference) when it draws a new story's scenes.
TEACHERS = {
    "amazon-still-shrinking": [amazon_clearing, amazon_vs_france,
                               amazon_where_it_goes],
    "coffee-price-record": [coffee_climb, coffee_drought, coffee_doubled],
    "urban-heat-island-redlining": [heat_by_city, heat_share, heat_redlining],
}


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
    for f in range(frames):
        cr = cairo.Context(surf)

        def host(role, x, fy, h, pace=True, _cr=cr, _f=f):
            place_host(_cr, role, (_f % 120) / 120.0, insight, x, fy, h,
                       _f / 30.0, pace)
        scene(cr, f / 30.0, f / max(1, frames - 1), pts, host)
        surf.flush()
        surf.write_to_png(str(out_dir / f"{name}_build{f + 1:02d}.png"))
    insight.host_baked = True
    return str(out_dir / f"{name}_build%02d.png"), []
