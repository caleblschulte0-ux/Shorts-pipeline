#!/usr/bin/env python3
"""CHARACTER SCENES — the soul (TASTE_JUDGE.md palette #1 and #2).

The clean data-cards (flat2d) are the MINORITY treatment. The video is carried by
a character actually LIVING the idea. The character is the universal white
bathroom-sign pictogram — a simple silhouette everyone reads instantly — posed in
bespoke, moody, moving SCENES:

    sleep_scene   the figure asleep in bed as years fly past      ("26 asleep")
    work_scene    hunched at a desk, days blurring by             ("13 at work")
    screen_scene  curled around a glowing phone, the world dim    ("11 on a screen")
    free_scene    walking out into an open sunrise, arms rising   ("9 are yours")

Each scene: a full-frame environment with its own light and mood (never the same
starfield), continuous meaningful motion (Z's rising, a sun arcing, a phone glow,
a horizon opening), and the number as a small ACCENT — the scene is the star.

    from data_learning import scenes
    scenes.sleep_scene(out, 6.0, number="26", label="YEARS ASLEEP")
"""
from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
REPO = Path(__file__).resolve().parent.parent
ANTON = str(REPO / "assets" / "fonts" / "Anton-Regular.ttf")
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FIG = (240, 244, 252)          # the pictogram silhouette — clean warm white


def _font(path, size):
    return ImageFont.truetype(path, size)


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _center_x(d, text, font):
    bb = d.textbbox((0, 0), text, font=font)
    return (W - (bb[2] - bb[0])) // 2


def _spaced(s):
    return "   ".join(s.upper())


def _vgrad(top, bot):
    """A vertical gradient background as an RGB array — every scene starts from a
    designed sky/room wash, never flat black."""
    yy = np.linspace(0, 1, H)[:, None]
    g = np.zeros((H, W, 3), np.uint8)
    for c in range(3):
        g[..., c] = np.clip(top[c] + (bot[c] - top[c]) * yy, 0, 255)
    return Image.fromarray(g, "RGB")


def _capsule(d, x0, y0, x1, y1, w, col):
    """A rounded limb — a thick line with round caps."""
    d.line([x0, y0, x1, y1], fill=col, width=w)
    r = w // 2
    for (x, y) in ((x0, y0), (x1, y1)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)


# --------------------------------------------------------------------------
# THE CHARACTER — the universal bathroom-sign pictogram. DEAD SIMPLE iconic
# silhouettes: a circle head + clean, symmetric rounded shapes. No articulated
# capsule rig, no shaded back-limbs — that made lumpy "cryptids". Each pose is a
# small set of deliberate shapes that reads instantly, like a real door sign.
# --------------------------------------------------------------------------
def _rrect(d, x0, y0, x1, y1, col, r=None):
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    r = r if r is not None else min(x1 - x0, y1 - y0) / 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=max(1, r), fill=col)


def _limb(d, x0, y0, x1, y1, w, col):
    """A clean straight limb — rounded rectangle drawn as a thick capsule line."""
    d.line([x0, y0, x1, y1], fill=col, width=int(w))
    r = w / 2
    for (x, y) in ((x0, y0), (x1, y1)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)


def _stand(d, cx, feet_y, h, col, arms_up=0.0, stride=0.0):
    """The iconic standing pictogram — chunky, symmetric, door-sign clean.
    arms_up 0=at sides, 1=raised in a wide V. Returns (cx, head_cy, r)."""
    # THE ADA / AIGA bathroom-sign proportions (reference-matched): broad ROUNDED
    # shoulders, a torso that tapers to the waist, arms hanging CLOSE to the body
    # (near-vertical) with a thin slit, ending mid-thigh, and two thick legs with a
    # thin inseam slit. An average solid build — not skinny, not fat.
    r = h * 0.11                                     # head
    head_cy = feet_y - h + r
    sh_y = head_cy + r + h * 0.012                   # tiny neck
    hip_y = feet_y - h * 0.46                        # where the legs split
    SW = h * 0.34                                    # broad shoulders
    WW = h * 0.185                                   # waist (clear taper)
    aw = h * 0.088                                   # arm thickness
    lw = h * 0.125                                   # thick legs
    shr = h * 0.055                                  # shoulder round
    # LEGS first (behind), thick with a thin inseam slit
    slit = h * 0.022
    lx = slit / 2 + lw / 2
    _limb(d, cx - lx, hip_y - lw * 0.1, cx - lx - stride, feet_y, lw, col)
    _limb(d, cx + lx, hip_y - lw * 0.1, cx + lx + stride, feet_y, lw, col)
    hipw = 2 * lx + lw
    # TORSO — rounded broad shoulders tapering to the waist, blending into the hips
    d.polygon([(cx - SW / 2, sh_y + shr), (cx + SW / 2, sh_y + shr),
               (cx + WW / 2, hip_y), (cx - WW / 2, hip_y)], fill=col)
    _rrect(d, cx - SW / 2, sh_y, cx + SW / 2, sh_y + 2 * shr, col, r=shr)   # shoulders
    _rrect(d, cx - hipw / 2, hip_y - lw * 0.3, cx + hipw / 2, hip_y + lw * 0.2,
           col, r=lw * 0.35)                                                # hips
    # ARMS — from the shoulder, hanging close & near-vertical with a thin gap to
    # mid-thigh; arms_up lifts them to a wide V.
    shx = SW / 2 - aw * 0.42
    hxd = WW / 2 + aw * 0.5 + h * 0.02              # DOWN: just outside the waist
    hyd = hip_y - sh_y + h * 0.02                   # ends mid-thigh (short arms)
    hxu, hyu = h * 0.23, -(sh_y - head_cy) - h * 0.09   # UP: high + wide V
    hx = hxd + (hxu - hxd) * arms_up
    hy = hyd + (hyu - hyd) * arms_up
    for sgn in (-1, 1):
        _limb(d, cx + sgn * shx, sh_y + shr * 0.7, cx + sgn * hx, sh_y + hy, aw, col)
    # head last, on top
    d.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], fill=col)
    return (cx, head_cy, r)


def _sit(d, hipx, hipy, h, col, lean=14, reach=0.0, on_ground=False):
    """The iconic SEATED pictogram, side-on, facing right. Clean rounded shapes:
    torso (leaning `lean` deg toward the right), a bent leg (thigh forward, shin
    down), a head, and one arm reaching forward by `reach` (0..1). If on_ground,
    the knee is raised (sitting on the floor); else seated on a chair."""
    r = h * 0.135
    lw = h * 0.12
    tw = h * 0.20
    la = math.radians(lean)
    # torso from hip up to shoulder, leaning forward-right
    sh = (hipx + math.sin(la) * h * 0.44, hipy - math.cos(la) * h * 0.44)
    _limb(d, hipx, hipy, sh[0], sh[1], tw, col)
    # leg
    if on_ground:
        knee = (hipx + h * 0.30, hipy - h * 0.16)          # knee raised in front
        foot = (knee[0] + h * 0.06, hipy + h * 0.04)
    else:
        knee = (hipx + h * 0.34, hipy + h * 0.01)          # thigh ~horizontal
        foot = (knee[0] + h * 0.02, hipy + h * 0.40)       # shin down to floor
    _limb(d, hipx, hipy, knee[0], knee[1], lw, col)
    _limb(d, knee[0], knee[1], foot[0], foot[1], lw, col)
    # head just forward of the shoulders
    hc = (sh[0] + math.sin(la) * r * 1.3, sh[1] - math.cos(la) * (r * 1.3) + r * 0.2)
    # arm reaches forward-down from the shoulder
    aw = h * 0.10
    hand = (sh[0] + h * (0.10 + 0.22 * reach), sh[1] + h * (0.16 - 0.04 * reach))
    _limb(d, sh[0], sh[1] + aw * 0.1, hand[0], hand[1], aw, col)
    d.ellipse([hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r], fill=col)
    return {"head": hc, "hand": hand, "hr": r, "shoulder": sh}


def _glow(im, draw_fn, blur, ):
    """Composite a blurred glow layer under the frame."""
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(lay, "RGBA"))
    return Image.alpha_composite(im.convert("RGBA"),
                                 lay.filter(ImageFilter.GaussianBlur(blur)))


def _label(im, number, label, y=0.12, col=(255, 211, 122)):
    """The small number/label ACCENT — corner-of-the-frame, not the hero."""
    d = ImageDraw.Draw(im, "RGBA")
    numf = _font(ANTON, 120)
    labf = _font(DEJAVU, 34)
    x = int(W * 0.08)
    d.text((x + 3, int(H * y) + 3), number, font=numf, fill=(0, 0, 0, 150))
    d.text((x, int(H * y)), number, font=numf, fill=(*col, 255))
    lab = _spaced(label)
    d.text((x + 4, int(H * y) + 150), lab, font=labf, fill=(*FIG, 230))
    return im


# --------------------------------------------------------------------------
# COLOR MOODS — the film travels through distinct color WORLDS instead of one
# navy wash. The single biggest cure for "every scene looks the same": each
# chapter sets a mood (scenes.set_mood(...)) and a gentle final grade is applied
# to EVERY frame of that chapter's scenes in _render, so taxes read cold-steel,
# housing warm-amber, the trap red-alarm, the payoff golden. Kept moderate so it
# is a lighting mood, not a cheap Instagram filter.
# --------------------------------------------------------------------------
_MOOD = None
MOODS = {                       # (r_mult, g_mult, b_mult, r_add, g_add, b_add)
    "cash":      (1.04, 1.03, 0.93,  4,  3, -5),   # opening — warm greenback
    "tax":       (0.90, 0.97, 1.15, -6, -2, 16),   # cold steel blue — the state
    "housing":   (1.13, 1.02, 0.82, 12,  3, -8),   # warm amber — home light
    "transport": (0.91, 1.05, 1.12, -5,  2, 10),   # teal dusk — the commute
    "food":      (1.02, 1.11, 0.86,  2,  9, -8),   # warm green — the table
    "leaks":     (1.09, 0.92, 1.15,  9, -6, 12),   # violet — invisible drains
    "trap":      (1.18, 0.85, 0.85, 16,-11,-11),   # red alarm — lifestyle creep
    "payoff":    (1.15, 1.06, 0.80, 15,  9,-10),   # golden dawn — what's yours
}


def set_mood(m):
    """Set the color world for the scenes that follow (None = neutral)."""
    global _MOOD
    _MOOD = m if m in MOODS else None


def _grade(im):
    if _MOOD is None:
        return im
    r, g, b, ra, ga, ba = MOODS[_MOOD]
    a = np.asarray(im, np.float32)
    a[..., 0] = np.clip(a[..., 0] * r + ra, 0, 255)
    a[..., 1] = np.clip(a[..., 1] * g + ga, 0, 255)
    a[..., 2] = np.clip(a[..., 2] * b + ba, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGB")


def _render(draw_fn, out: Path, seconds: float, bg_fn):
    """Pipe raw RGB straight to ffmpeg. bg_fn(i,n)->Image builds the per-frame
    environment; draw_fn(i,n,im)->Image adds the character + props + accent.
    A per-chapter color grade (set_mood) is applied to every finished frame."""
    n = max(2, int(round(seconds * FPS)))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        im = _grade(draw_fn(i, n, bg_fn(i, n)).convert("RGB"))
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    proc.wait()
    return out


# --------------------------------------------------------------------------
# SLEEP — the figure asleep in bed, years flying past on a wall calendar/clock
# --------------------------------------------------------------------------
def sleep_scene(out: Path, seconds: float = 6.0, number: str = "26",
                label: str = "YEARS ASLEEP") -> Path:
    rnd = random.Random(3)
    stars = [(rnd.uniform(0, W), rnd.uniform(0, H * 0.44), rnd.choice([1, 1, 2]))
             for _ in range(90)]
    bx0, bx1 = int(W * 0.20), int(W * 0.80)          # bed (big, centred)
    bed_y = int(H * 0.58)

    def bg(i, n):
        # NIGHTS FLY BY while you sleep: the room lightens dark -> dawn across the
        # whole beat (a MONOTONIC whole-frame change = years passing, and it clears
        # 'something new every 5s' without aliasing the way a cycle would).
        t = i / max(1, n - 1)
        k = t
        top = (int(16 + 74 * k), int(20 + 66 * k), int(50 + 48 * k))
        bot = (int(6 + 44 * k), int(8 + 36 * k), int(20 + 30 * k))
        return _vgrad(top, bot)

    def draw(i, n, im):
        t = i / max(1, n - 1)
        d = ImageDraw.Draw(im, "RGBA")
        # window whose sky brightens toward dawn with the room; a body arcs across
        # it (moon -> sun) as day after day rips past.
        wx0, wy0, wx1, wy1 = int(W * 0.62), int(H * 0.08), int(W * 0.92), int(H * 0.40)
        k = t
        sky = (int(20 + 90 * k), int(30 + 80 * k), int(70 + 40 * k))
        d.rectangle([wx0, wy0, wx1, wy1], fill=(*sky, 255),
                    outline=(70, 84, 140, 255), width=6)
        d.line([(wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1], fill=(70, 84, 140), width=4)
        d.line([wx0, (wy0 + wy1) // 2, wx1, (wy0 + wy1) // 2], fill=(70, 84, 140), width=4)
        # the celestial body races across the window (fast days)
        arc = (t * 3.2) % 1.0
        bx = wx0 + 20 + arc * (wx1 - wx0 - 40)
        by = wy1 - 24 - math.sin(arc * math.pi) * (wy1 - wy0 - 48)
        sun = arc > 0.5                        # alternate moon / sun as days flip
        bcol = (255, 214, 140) if sun else (244, 244, 224)
        im = _glow(im, lambda dd: dd.ellipse([bx - 40, by - 40, bx + 40, by + 40],
                                             fill=(*bcol, 200)), 20)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([bx - 26, by - 26, bx + 26, by + 26], fill=(*bcol, 255))
        for sx, sy, sr in stars:
            tw = 0.5 + 0.5 * math.sin(i * 0.14 + sx)
            c = int(150 * tw * (1 - k * 0.6))
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(c, c, int(c * 1.1)))
        breathe = 7 * math.sin(i * 0.09)
        # bed: frame, mattress, headboard, pillow
        d.rounded_rectangle([bx0, bed_y + 6, bx1, bed_y + 210], radius=30,
                            fill=(52, 40, 60, 255))                       # frame
        d.rounded_rectangle([bx0 - 6, bed_y - 96, bx0 + 40, bed_y + 60], radius=18,
                            fill=(64, 50, 74, 255))                       # headboard
        d.rounded_rectangle([bx0 + 20, bed_y + 30, bx1 - 12, bed_y + 96], radius=22,
                            fill=(206, 210, 226, 255))                    # mattress edge
        # pillow + a CLEAR sleeping head resting on it
        d.ellipse([bx0 + 44, bed_y - 20, bx0 + 220, bed_y + 70], fill=(232, 236, 248, 255))
        hx, hy = bx0 + 150, bed_y + 4
        d.ellipse([hx - 46, hy - 46, hx + 46, hy + 46], fill=FIG)         # head
        d.arc([hx - 30, hy - 8, hx - 6, hy + 16], 20, 160, fill=(120, 130, 150), width=4)  # closed eye
        # blanket shaped like a reclining BODY: high at the chest, tapering to feet
        by = bed_y + 40 - breathe
        d.polygon([(hx + 30, bed_y + 96), (hx + 60, by - 20), (hx + 250, by - 34),
                   (bx1 - 120, bed_y + 20), (bx1 - 40, bed_y + 96)],
                  fill=(120, 92, 150, 255))
        d.ellipse([bx1 - 150, by - 46, bx1 - 70, by + 24], fill=(120, 92, 150, 255))  # shoulder
        d.rounded_rectangle([bx1 - 70, bed_y + 40, bx1 - 20, bed_y + 96], radius=14,
                            fill=(150, 120, 178, 255))                    # feet bump
        # Z Z Z rising and fading from the head — the sleep, always moving
        zf = _font(ANTON, 54)
        for k in range(3):
            ph = (t * 1.6 + k * 0.33) % 1.0
            zx = hx + 40 + ph * 120
            zy = hy - 60 - ph * 160
            a = int(230 * (1 - ph))
            sz = 40 + int(ph * 44)
            d.text((zx, zy), "Z", font=zf.font_variant(size=sz), fill=(*FIG, a))
        # a wall clock whose hands SPIN fast — years flying by (bottom-left corner)
        cx, cy, cr = int(W * 0.12), int(H * 0.84), 64
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(28, 34, 66, 255),
                  outline=(*FIG, 220), width=6)
        for hh in range(12):
            a = hh / 12 * 2 * math.pi
            d.line([cx + math.cos(a) * (cr - 12), cy + math.sin(a) * (cr - 12),
                    cx + math.cos(a) * (cr - 4), cy + math.sin(a) * (cr - 4)],
                   fill=(*FIG, 200), width=3)
        spin = t * 26
        d.line([cx, cy, cx + math.cos(spin) * (cr - 20), cy + math.sin(spin) * (cr - 20)],
               fill=(*FIG, 255), width=5)
        d.line([cx, cy, cx + math.cos(spin * 12) * (cr - 30),
                cy + math.sin(spin * 12) * (cr - 30)], fill=(255, 211, 122, 255), width=3)
        im = _label(im, number, label)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# WORK — hunched at a desk, monitor glow, sun arcing past the window (days)
# --------------------------------------------------------------------------
def work_scene(out: Path, seconds: float = 6.0, number: str = "13",
               label: str = "YEARS AT WORK") -> Path:
    desk_y = int(H * 0.70)

    def bg(i, n):
        t = i / max(1, n - 1)
        # DAY AFTER DAY: the wall sweeps MONOTONICALLY from a bright morning to a
        # dark late night across the beat (big whole-frame change = time flying,
        # clears novelty without aliasing).
        k = 1.0 - 0.9 * t
        top = (int(24 + 120 * k), int(30 + 88 * k), int(56 + 22 * k))
        bot = (int(10 + 34 * k), int(12 + 26 * k), int(24 + 16 * k))
        return _vgrad(top, bot)

    def draw(i, n, im):
        t = i / max(1, n - 1)
        d = ImageDraw.Draw(im, "RGBA")
        # window with a SUN that arcs across, again and again (days blurring)
        wx0, wy0, wx1, wy1 = int(W * 0.08), int(H * 0.10), int(W * 0.40), int(H * 0.46)
        d.rectangle([wx0, wy0, wx1, wy1], fill=(60, 70, 120, 255),
                    outline=(90, 100, 150, 255), width=6)
        arc = (t * 4.0) % 1.0
        sx = wx0 + arc * (wx1 - wx0)
        sy = wy1 - math.sin(arc * math.pi) * (wy1 - wy0) * 0.9
        im = _glow(im, lambda dd: dd.ellipse([sx - 40, sy - 40, sx + 40, sy + 40],
                                             fill=(255, 210, 120, 220)), 20)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([sx - 26, sy - 26, sx + 26, sy + 26], fill=(255, 226, 150, 255))
        d.line([(wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1], fill=(90, 100, 150), width=4)
        # desk
        d.rectangle([0, desk_y, W, desk_y + 12], fill=(58, 44, 40, 255))
        d.rectangle([int(W * 0.30), desk_y + 12, int(W * 0.34), H], fill=(48, 36, 33, 255))
        d.rectangle([int(W * 0.66), desk_y + 12, int(W * 0.70), H], fill=(48, 36, 33, 255))
        # monitor with a cool pulsing glow on the figure
        mx0, my0, mx1, my1 = int(W * 0.54), int(H * 0.40), int(W * 0.74), int(H * 0.66)
        im = _glow(im, lambda dd: dd.rectangle([mx0 - 20, my0 - 20, mx1 + 20, my1 + 20],
                                               fill=(90, 150, 230, 130)), 26)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([mx0, my0, mx1, my1], radius=10, fill=(120, 175, 240, 255))
        for r in range(4):                                   # scrolling lines of "work"
            ly = my0 + 24 + ((r * 40 + int(t * 260)) % (my1 - my0 - 40))
            d.line([mx0 + 20, ly, mx1 - 20, ly], fill=(30, 50, 90, 200), width=6)
        d.rectangle([int(W * 0.62), my1, int(W * 0.66), desk_y], fill=(40, 44, 60, 255))
        # papers STACKING at the desk's left edge as time passes
        stack = int((t * 5) % 6) + 1
        for s in range(stack):
            py = desk_y - 8 - s * 12
            d.rounded_rectangle([int(W * 0.20), py - 8, int(W * 0.30), py + 4],
                                radius=3, fill=(230, 232, 240, 255),
                                outline=(150, 150, 160, 255))
        # chair (seat + back) behind the figure
        cx = int(W * 0.40)
        hip = (cx, desk_y + 8)
        d.rounded_rectangle([cx - 96, hip[1] - 8, cx + 30, hip[1] + 14], radius=10,
                            fill=(44, 40, 52, 255))                        # seat
        d.rounded_rectangle([cx - 96, hip[1] - 150, cx - 74, hip[1] + 8], radius=12,
                            fill=(44, 40, 52, 255))                        # back
        # keyboard on the desk in front of him
        d.rounded_rectangle([int(W * 0.50), desk_y - 14, int(W * 0.61), desk_y - 2],
                            radius=4, fill=(60, 64, 82, 255))
        # the FIGURE — the clean seated pictogram at the desk, arm reaching to the
        # keyboard with a tiny typing bob.
        reach = 0.55 + 0.08 * math.sin(i * 0.6)
        _sit(d, cx, desk_y + 4, h=420, col=FIG, lean=16, reach=reach, on_ground=False)
        im = _label(im, number, label)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# SCREEN — curled around a huge glowing phone, the rest of the world dark
# --------------------------------------------------------------------------
def screen_scene(out: Path, seconds: float = 6.0, number: str = "11",
                 label: str = "YEARS ON A SCREEN") -> Path:
    def bg(i, n):
        return _vgrad((16, 20, 40), (4, 5, 12))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.82)
        d = ImageDraw.Draw(im, "RGBA")
        # a dim room with a couch behind — context so it isn't an empty void
        d.rectangle([0, floor_y, W, H], fill=(14, 16, 28, 255))
        d.rounded_rectangle([int(W * 0.20), int(H * 0.52), int(W * 0.66), floor_y + 10],
                            radius=30, fill=(26, 28, 44, 255))          # couch base
        d.rounded_rectangle([int(W * 0.20), int(H * 0.44), int(W * 0.28), floor_y],
                            radius=24, fill=(32, 34, 52, 255))          # couch arm
        # the FIGURE sits on the floor against the couch (blue-lit), holding a phone
        # up toward the face. The clean seated pictogram — grounded, absorbed.
        lit = (150, 185, 235)
        reach = 0.42 + 0.05 * math.sin(i * 0.3)
        joints = _sit(d, int(W * 0.40), floor_y + 6, h=430, col=lit, lean=8,
                      reach=reach, on_ground=True)
        # the phone in the reaching hand, tilted up toward the face, feed scrolling.
        hf = joints["hand"]
        pcx, pcy = hf[0] + 6, hf[1] - 34
        pw, ph = 132, 250
        phone = Image.new("RGBA", im.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(phone)
        px0, py0 = int(pcx - pw / 2), int(pcy - ph / 2)
        pd.rounded_rectangle([px0, py0, px0 + pw, py0 + ph], radius=22,
                             fill=(18, 22, 36, 255), outline=(80, 92, 130, 255), width=5)
        for r in range(4):
            ry = py0 + 16 + ((r * 66 + int(t * 300)) % (ph - 48))
            pd.rounded_rectangle([px0 + 12, ry, px0 + pw - 12, ry + 36], radius=8,
                                 fill=(170, 205, 252, 255))
            pd.ellipse([px0 + 18, ry + 5, px0 + 42, ry + 29], fill=(255, 224, 150, 255))
        phone = phone.rotate(18, resample=Image.BICUBIC, center=(pcx, pcy))
        # phone glow onto the face/room before compositing the phone over the hands
        im2 = _glow(im, lambda dd: dd.ellipse([pcx - 240, pcy - 220, pcx + 200, pcy + 220],
                                              fill=(90, 150, 230, 160)), 60)
        im2 = Image.alpha_composite(im2.convert("RGBA"), phone)
        im = _label(im2, number, label)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# FREE — the figure walks out into an open sunrise, arms rising (the payoff)
# --------------------------------------------------------------------------
def free_scene(out: Path, seconds: float = 6.0, number: str = "9",
               label: str = "YEARS ARE YOURS") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        # dark -> warm sunrise as the payoff lands
        warm = _ease(t)
        top = (int(30 + 60 * warm), int(34 + 70 * warm), int(70 + 40 * warm))
        bot = (int(20 + 120 * warm), int(16 + 70 * warm), int(30 + 20 * warm))
        return _vgrad(top, bot)

    def draw(i, n, im):
        t = i / max(1, n - 1)
        # the rising sun on the horizon
        hz = int(H * 0.72)
        sx, sy = int(W * 0.5), hz - int(_ease(t) * H * 0.22)
        im = _glow(im, lambda dd: dd.ellipse([sx - 150, sy - 150, sx + 150, sy + 150],
                                             fill=(255, 200, 120, 200)), 80)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([sx - 90, sy - 90, sx + 90, sy + 90], fill=(255, 224, 168, 255))
        # ground
        d.rectangle([0, hz, W, H], fill=(26, 22, 34, 255))
        for gx in range(0, W, 90):                          # ground texture streaks
            d.line([gx + int(t * 30) % 90, hz + 20, gx + 40 + int(t * 30) % 90, hz + 20],
                   fill=(40, 34, 48, 200), width=3)
        # the FIGURE walks toward the light; arms rise to a V as it frees up.
        cx = int(W * 0.30 + t * W * 0.16)
        feet = hz + 34
        rise = _ease(max(0.0, (t - 0.35) / 0.65))
        stride = 12 * math.sin(i * 0.4)
        _stand(d, cx, feet, h=360, col=FIG, arms_up=rise, stride=stride)
        im = _label(im, number, label, col=(255, 224, 168))
        return im

    return _render(draw, out, seconds, bg)


def _clock(d, cx, cy, cr, t, spin=26.0):
    """A little wall clock with fast-spinning hands — time flying, always moving."""
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(28, 34, 66, 255),
              outline=(*FIG, 220), width=6)
    for hh in range(12):
        a = hh / 12 * 2 * math.pi
        d.line([cx + math.cos(a) * (cr - 12), cy + math.sin(a) * (cr - 12),
                cx + math.cos(a) * (cr - 4), cy + math.sin(a) * (cr - 4)],
               fill=(*FIG, 200), width=3)
    sp = t * spin
    d.line([cx, cy, cx + math.cos(sp) * (cr - 20), cy + math.sin(sp) * (cr - 20)],
           fill=(*FIG, 255), width=5)
    d.line([cx, cy, cx + math.cos(sp * 12) * (cr - 30), cy + math.sin(sp * 12) * (cr - 30)],
           fill=(255, 211, 122, 255), width=3)


# --------------------------------------------------------------------------
# QUEUE — the figure stuck in a slow line; the people ahead shuffle off, but the
# wait never seems to end. ("years in line")
# --------------------------------------------------------------------------
def queue_scene(out: Path, seconds: float = 6.0, number: str = "6",
                label: str = "MONTHS IN LINE") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 1.0 - 0.4 * t                             # the endless afternoon dims
        return _vgrad((int(20 + 44 * k), int(22 + 44 * k), int(28 + 46 * k)),
                      (18, 20, 28))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.82)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(24, 26, 36, 255))
        # a service counter on the right with a glowing "please wait" panel
        d.rounded_rectangle([int(W * 0.82), int(H * 0.5), W + 10, floor_y], radius=12,
                            fill=(42, 44, 60, 255))
        im = _glow(im, lambda dd: dd.rounded_rectangle(
            [int(W * 0.845), int(H * 0.55), int(W * 0.965), int(H * 0.66)], radius=10,
            fill=(230, 120, 90, 160)), 24)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([int(W * 0.845), int(H * 0.55), int(W * 0.965), int(H * 0.66)],
                            radius=10, fill=(228, 120, 92, 255))
        # a floor rope-line
        d.line([int(W * 0.14), floor_y + 30, int(W * 0.80), floor_y + 30],
               fill=(70, 74, 96, 200), width=5)
        # the line advances monotonically to the right; grey people ahead peel off
        adv = t * W * 0.16
        spacing = int(W * 0.135)
        for k in range(3):
            gx = int(W * 0.34) + k * spacing + int(adv)
            fade = 1.0 - max(0.0, min(1.0, (t * 2.4) - k))    # front leaves first
            if fade <= 0.02:
                continue
            g = int(96 * fade + 24)
            _stand(d, gx, floor_y + 20, 300, (g, g, int(g * 1.1)))
        # OUR figure (bright) at the back, shifting weight impatiently
        sway = 7 * math.sin(i * 0.32)
        ox = int(W * 0.20) + int(adv) + sway
        _stand(d, ox, floor_y + 20, 320, FIG,
               stride=6 * math.sin(i * 0.32 + 1))
        # scene-specific device (NOT the shared clock): a NOW-SERVING ticket that
        # crawls up while our number stays far away.
        px0, py0, px1, py1 = int(W * 0.845), int(H * 0.55), int(W * 0.965), int(H * 0.66)
        nsf, sf = _font(DEJAVU, 22), _font(ANTON, 64)
        d.text((px0 + 8, py0 - 34), "N O W   S E R V I N G", font=nsf, fill=(*FIG, 210))
        serve = 38 + int(t * 6)
        s = f"{serve}"
        d.text(((px0 + px1) // 2 - sf.getlength(s) // 2, py0 + 6), s, font=sf,
               fill=(20, 22, 30, 255))
        im = _label(im, number, label)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# TRAFFIC — the figure stuck at a red light that never turns green; cars pile up
# behind. ("months at red lights")
# --------------------------------------------------------------------------
def traffic_scene(out: Path, seconds: float = 6.0, number: str = "5",
                  label: str = "MONTHS AT RED LIGHTS") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        # stuck so long the sky creeps toward dawn: dark -> pre-dawn light. The
        # OPPOSITE direction from the neighbouring scenes so the cut reads as new.
        k = 0.15 + 0.85 * t
        return _vgrad((int(14 + 92 * k), int(18 + 66 * k), int(34 + 50 * k)),
                      (6, 7, 14))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        road_y = int(H * 0.78)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, road_y, W, H], fill=(20, 21, 30, 255))
        for gx in range(0, W, 160):                   # lane dashes
            d.rounded_rectangle([gx + 40, road_y + 80, gx + 120, road_y + 92],
                                radius=6, fill=(60, 62, 78, 200))
        # a traffic light on the right, stuck RED (it glows, pulsing)
        lx, ly = int(W * 0.86), int(H * 0.20)
        d.rounded_rectangle([lx - 34, ly - 20, lx + 34, ly + 220], radius=20,
                            fill=(26, 28, 40, 255))
        pr = 0.6 + 0.4 * math.sin(i * 0.4)
        im = _glow(im, lambda dd: dd.ellipse([lx - 40, ly, lx + 40, ly + 80],
                                             fill=(235, 70, 60, int(120 + 90 * pr))), 26)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([lx - 26, ly + 4, lx + 26, ly + 56], fill=(240, 80, 70, 255))     # red on
        d.ellipse([lx - 26, ly + 70, lx + 26, ly + 122], fill=(70, 60, 30, 255))    # amber off
        d.ellipse([lx - 26, ly + 136, lx + 26, ly + 188], fill=(40, 70, 50, 255))   # green off
        # cars PILE UP behind over the beat (one-way): our car in front + more behind
        def car(cx, col, lit=False):
            cy = road_y - 4
            d.rounded_rectangle([cx - 150, cy - 70, cx + 150, cy - 4], radius=26, fill=col)
            d.rounded_rectangle([cx - 96, cy - 118, cx + 74, cy - 58], radius=30, fill=col)
            d.rounded_rectangle([cx - 80, cy - 108, cx + 58, cy - 66], radius=18,
                                fill=(150, 180, 220, 255))       # windshield
            d.ellipse([cx - 110, cy - 30, cx - 50, cy + 30], fill=(18, 18, 24, 255))
            d.ellipse([cx + 50, cy - 30, cx + 110, cy + 30], fill=(18, 18, 24, 255))
            if lit:
                for bx in (cx - 148, cx + 130):
                    d.rounded_rectangle([bx, cy - 54, bx + 18, cy - 30], radius=6,
                                        fill=(255, 90, 70, 255))
        ncars = int(t * 3.2)                          # cars accumulate behind
        for k in range(ncars):
            car(int(W * 0.10) - k * int(W * 0.20), (34, 36, 52, 255))
        # our car in front (brake lights on)
        shake = 1.5 * math.sin(i * 0.9)
        car(int(W * 0.44) + shake, (58, 92, 150, 255), lit=True)
        # a little driver head in the window (drums the wheel — impatient)
        drum = 3 * math.sin(i * 0.8)
        d.ellipse([int(W * 0.44) - 26, road_y - 118 + drum,
                   int(W * 0.44) + 26, road_y - 66 + drum], fill=FIG)
        # the traffic light's own device: a WALK/countdown that's stuck (no clock)
        d.text((lx - 30, ly + 232), "0:00", font=_font(ANTON, 40),
               fill=(235, 80, 70, 255))
        im = _label(im, number, label)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# HOLD — the figure sits on hold, phone to the ear, slowly slumping as the same
# music loops. ("days on hold")
# --------------------------------------------------------------------------
def hold_scene(out: Path, seconds: float = 6.0, number: str = "43",
               label: str = "DAYS ON HOLD") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 1.0 - 0.78 * t                            # room darkens as time drags on
        return _vgrad((int(16 + 60 * k), int(16 + 50 * k), int(28 + 44 * k)),
                      (10, 11, 18))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.84)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(18, 19, 30, 255))
        # a couch/chair
        d.rounded_rectangle([int(W * 0.28), int(H * 0.50), int(W * 0.66), floor_y + 8],
                            radius=30, fill=(30, 32, 50, 255))
        d.rounded_rectangle([int(W * 0.60), int(H * 0.40), int(W * 0.68), floor_y],
                            radius=24, fill=(36, 38, 58, 255))
        # the figure sits and SLUMPS more as time drags (one-way droop)
        droop = _ease(t) * 16
        joints = _sit(d, int(W * 0.42), floor_y + 2, h=430, col=FIG,
                      lean=10 + droop, reach=0.0, on_ground=False)
        # arm bent up to the ear, holding a phone against the head
        hd = joints["head"]
        sh = joints["shoulder"]
        ear = (hd[0] - joints["hr"] * 0.7, hd[1])
        _limb(d, sh[0], sh[1], ear[0], ear[1], 430 * 0.10, FIG)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([ear[0] - 22, ear[1] - 40, ear[0] + 14, ear[1] + 40],
                            radius=12, fill=(22, 26, 40, 255), outline=(80, 92, 130), width=4)
        # hold music — little notes (drawn as shapes) drift up and fade, endlessly
        for k in range(4):
            ph = (t * 1.5 + k * 0.25) % 1.0
            nx = ear[0] - 40 - ph * 120
            ny = ear[1] - 20 - ph * 200
            a = int(230 * (1 - ph))
            s = 12
            col = (150, 190, 245, a)
            d.ellipse([nx - s, ny - s * 0.7, nx + s, ny + s * 0.7], fill=col)  # head
            d.line([nx + s - 1, ny, nx + s - 1, ny - s * 3], fill=col, width=4)  # stem
            d.line([nx + s - 1, ny - s * 3, nx + s + s, ny - s * 2.3],
                   fill=col, width=4)                                          # flag
        # this scene's own device (NOT the shared clock): a hold-time counter that
        # keeps climbing, mm:ss, under a small "ON HOLD" tag.
        d = ImageDraw.Draw(im, "RGBA")
        mm = 40 + int(t * 3)
        ss = int((t * 220) % 60)
        tm = f"{mm}:{ss:02d}"
        tf, tg = _font(ANTON, 60), _font(DEJAVU, 24)
        tx = int(W * 0.16)
        d.text((tx, int(H * 0.20)), "O N   H O L D", font=tg, fill=(*FIG, 210))
        d.text((tx, int(H * 0.20) + 34), tm, font=tf, fill=(150, 190, 245, 255))
        im = _label(im, number, label)
        return im

    return _render(draw, out, seconds, bg)


def walkout_scene(out: Path, seconds: float = 6.0, number: str = "",
                  label: str = "STOP WAITING") -> Path:
    """A DISTINCT payoff (not the recycled sunrise): the figure walks out of a
    dim room through a bright open doorway — leaving the waiting behind."""
    def bg(i, n):
        t = i / max(1, n - 1)
        k = t
        return _vgrad((int(18 + 34 * k), int(18 + 28 * k), int(26 + 32 * k)),
                      (10, 11, 16))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.80)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(14, 15, 22, 255))
        # a bright open doorway on the right; its light grows as the door opens
        dx0, dy0, dx1, dy1 = int(W * 0.66), int(H * 0.18), int(W * 0.84), floor_y
        openk = _ease(t)
        im = _glow(im, lambda dd: dd.rectangle(
            [dx0 - 40, dy0 - 30, dx1 + 40, dy1],
            fill=(255, 236, 190, int(110 + 130 * openk))), 80)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([dx0, dy0, dx1, dy1], fill=(255, 240, 208, int(170 + 80 * openk)))
        # light spills across the floor toward the figure
        spill = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(spill).polygon(
            [(dx0, floor_y), (dx1, floor_y), (int(W * 0.30), H), (0, H)],
            fill=(255, 236, 190, int(40 + 40 * openk)))
        im = Image.alpha_composite(im.convert("RGBA"),
                                   spill.filter(ImageFilter.GaussianBlur(30)))
        d = ImageDraw.Draw(im, "RGBA")
        # door frame
        d.rectangle([dx0 - 16, dy0 - 16, dx0, dy1], fill=(40, 42, 58, 255))
        d.rectangle([dx1, dy0 - 16, dx1 + 16, dy1], fill=(40, 42, 58, 255))
        d.rectangle([dx0 - 16, dy0 - 16, dx1 + 16, dy0], fill=(40, 42, 58, 255))
        # the figure strides from the dim room toward the light
        cx = int(W * 0.20 + t * W * 0.34)
        stride = 13 * math.sin(i * 0.45)
        _stand(d, cx, floor_y + 6, h=360, col=FIG, stride=stride)
        im = _label(im, number, label, col=(255, 224, 168))
        return im

    return _render(draw, out, seconds, bg)


# ==========================================================================
# MONEY — a lifetime of pay, chapter by chapter, draining away.
#
# The recurring MOTIF (money_scene) is the spine of the long-form piece: one
# horizontal bar = a whole life's take-home pay. Each chapter it drains another
# labelled chunk, the bright "still yours" part shrinks, coins spill off, and a
# running total ticks down — so the viewer FEELS the money leaving. Around it the
# character LIVES each cut in a bespoke scene (payday, the tax window, rent, the
# gas pump, the checkout, the little subscriptions), ending on the tiny sliver
# that's actually theirs. Palette: cool slate rooms, warm gold money.
# ==========================================================================
GOLD = (255, 205, 108)
GOLD_D = (196, 148, 66)
GREEN = (120, 196, 140)
GREEN_D = (70, 138, 100)
SLATE_T = (34, 40, 58)
SLATE_B = (13, 16, 26)

# A life's gross pay, in $thousands (2000 = $2.0M) and where it goes. The order
# is the chapter order; money_scene(upto=k) drains segment k this beat.
LIFETIME = [
    ("TAXES", 500, (150, 122, 236)),
    ("HOUSING", 500, (238, 128, 108)),
    ("GETTING AROUND", 250, (86, 186, 206)),
    ("FOOD", 300, (120, 188, 132)),
    ("LITTLE LEAKS", 150, (240, 178, 92)),
    ("ACTUALLY YOURS", 300, (255, 226, 170)),
]
LIFE_TOTAL = sum(a for _, a, _ in LIFETIME)


def _money_str(k_thousands: float) -> str:
    """$1.2M / $500K from a value in $thousands."""
    v = k_thousands * 1000
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M".replace(".0M", "M")
    return f"${int(round(v / 1000))}K"


def _slate_bg(top=SLATE_T, bot=SLATE_B):
    return _vgrad(top, bot)


def _coin(d, cx, cy, r, a=255, face=True):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*GOLD, a),
              outline=(*GOLD_D, a), width=max(2, int(r / 6)))
    d.ellipse([cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62],
              outline=(*GOLD_D, a), width=max(1, int(r / 9)))
    if face and r > 11:
        f = _font(ANTON, int(r * 1.25))
        d.text((cx - f.getlength("$") / 2, cy - r * 0.74), "$", font=f,
               fill=(*GOLD_D, a))


def _coin_fall(d, seed, t, x0, x1, y0, count=10, spread=260):
    """A deterministic spray of coins spilling down from a source edge, gravity +
    fade, looping — the money leaving. Cheap circles, readable at a glance."""
    rnd = random.Random(seed)
    for _ in range(count):
        ph = (t * (0.7 + rnd.random() * 0.7) + rnd.random()) % 1.0
        sx = rnd.uniform(x0, x1)
        cx = sx + math.sin(ph * 3 + rnd.random() * 6) * 24
        cy = y0 + ph * spread
        r = int(12 + rnd.random() * 10)
        a = int(240 * (1 - ph) ** 0.7)
        if a > 12:
            _coin(d, int(cx), int(cy), r, a=a, face=r > 13)


def _cash_pile(d, cx, base_y, frac, seed, glow_coin=False):
    """A dense, DIMENSIONAL heap of banknotes + coins whose size encodes `frac`
    (0..1) of a life's money — a physical pile you can see shrink, not a chart.
    Bills are packed into a real mound (half-width narrows with height), shaded by
    depth (dark, cool at the shadowed base; bright, warm at the lit crown), grounded
    by a soft contact shadow and finished with lit top edges so it reads as money
    catching light. Systemic: every money_scene in every video uses this."""
    frac = max(0.02, min(1.0, frac))
    pw = int(W * 0.32 * math.sqrt(frac)) + 46          # heap half-spread
    ph = int(H * 0.34 * math.sqrt(frac)) + 30          # heap height
    rnd = random.Random(seed)
    # soft contact shadow grounding the heap on the floor
    d.ellipse([cx - pw * 1.08, base_y - 10, cx + pw * 1.08, base_y + 50],
              fill=(0, 0, 0, 95))
    items = []
    for _ in range(int(46 + 240 * frac)):              # DENSE — a real mound
        rise = rnd.random() ** 1.25                    # bias to the base
        halfw = pw * (1 - rise) ** 0.7                 # mound profile
        x = cx + rnd.uniform(-1, 1) * halfw
        y = base_y - rise * ph + rnd.uniform(-6, 6)
        items.append((x, y, rnd.uniform(-0.6, 0.6), rise))
    items.sort(key=lambda p: p[1])                     # back (top) to front (base)
    bw2, bh2 = 66, 31
    for (x, y, skew, rise) in items:
        lit = 0.5 + 0.55 * rise                        # crown catches the light
        g = (min(255, int(GREEN[0] * lit) + 10), min(255, int(GREEN[1] * lit) + 14),
             min(255, int(GREEN[2] * lit) + 8))
        gd = (int(GREEN_D[0] * lit * 0.9), int(GREEN_D[1] * lit * 0.9),
              int(GREEN_D[2] * lit * 0.9))
        dx = skew * 12
        top = [(x - bw2 / 2 + dx, y - bh2 / 2), (x + bw2 / 2 + dx, y - bh2 / 2)]
        d.polygon([top[0], top[1], (x + bw2 / 2 - dx, y + bh2 / 2),
                   (x - bw2 / 2 - dx, y + bh2 / 2)], fill=(*g, 255))
        d.line([top[0], top[1]],                       # lit leading edge
               fill=(min(255, g[0] + 46), min(255, g[1] + 46), min(255, g[2] + 40), 255),
               width=2)
        d.ellipse([x - 9, y - 8, x + 9, y + 8], outline=(*gd, 255), width=2)  # seal
    # gold coins glinting across the mound (more toward the lit crown)
    for _ in range(int(6 + 22 * frac)):
        rise = rnd.random() ** 0.8
        halfw = pw * (1 - rise) ** 0.7
        x = cx + rnd.uniform(-1, 1) * halfw
        y = base_y - rise * ph
        _coin(d, int(x), int(y), int(11 + rnd.random() * 7), face=False)
    if glow_coin:
        _coin(d, cx, base_y - ph - 26, 32)


def money_scene(out: Path, seconds: float = 4.0, upto: int = 0,
                final: bool = False, number: str = "", label: str = "") -> Path:
    """THE RECURRING MOTIF — physical, not a chart. The figure stands beside a
    HEAP of a life's money that visibly shrinks chapter to chapter. This beat the
    named chunk blows off the top of the pile and away; the pile is smaller than
    last time and smaller again when it's over. A hanging tag reads what's left."""
    spent_before = sum(LIFETIME[k][1] for k in range(upto))
    active_amt = 0 if final else LIFETIME[upto][1]
    cat = LIFETIME[min(upto, len(LIFETIME) - 1)][0]
    start_frac = (LIFE_TOTAL - spent_before) / LIFE_TOTAL
    end_frac = (LIFE_TOTAL - spent_before - active_amt) / LIFE_TOTAL
    # STAGING VARIES each appearance so the motif never reads as one repeated
    # template: the camera/figure/pile swap sides and scale, and the figure ACTS
    # (steps after the money, throws up its arms) instead of just standing.
    layout = upto % 3
    if layout == 0:
        figx, figh, pcx, dirx = int(W * 0.20), 440, int(W * 0.60), 1
    elif layout == 1:                                   # mirrored
        figx, figh, pcx, dirx = int(W * 0.80), 470, int(W * 0.40), -1
    else:                                               # closer + lower
        figx, figh, pcx, dirx = int(W * 0.30), 520, int(W * 0.66), 1
    base_y = int(H * (0.80 if layout != 2 else 0.86))
    tagx = pcx + dirx * int(W * 0.13)

    def bg(i, n):
        # a big MONOTONIC vault-light swing (dim -> lit, or the reverse on the
        # payoff) so a large fraction of the frame changes every few seconds. On
        # the payoff the WHOLE frame warms (top AND bottom) to a golden dawn.
        t = i / max(1, n - 1)
        k = (1.0 - 0.85 * t) if not final else (0.15 + 0.85 * t)
        top = (int(20 + 96 * k), int(24 + 74 * k), int(40 + 44 * k))
        bot = (int(10 + 54 * k), int(12 + 40 * k), int(20 + 24 * k)) if final else (10, 12, 20)
        return _vgrad(top, bot)

    def draw(i, n, im):
        t = i / max(1, n - 1)
        drain = _ease(min(1.0, t / 0.85))
        frac = start_frac + (end_frac - start_frac) * drain
        d = ImageDraw.Draw(im, "RGBA")
        # floor
        d.rectangle([0, base_y + 8, W, H], fill=(16, 18, 28, 255))
        # the figure ACTS: on a drain beat it throws its arms up and steps after
        # the leaving money (alarm/grab-back); on the payoff it lifts the last of
        # it. Arms + stride swing so it reads as a reacting character, not an icon.
        if final:
            armsu = 0.30 + 0.10 * math.sin(i * 0.3)
            strd = 6 * math.sin(i * 0.3)
        else:
            armsu = 0.44 + 0.20 * (0.5 + 0.5 * math.sin(i * 0.7))   # grabbing up
            strd = dirx * (10 + 6 * math.sin(i * 0.7))              # stepping after it
        _stand(d, figx, base_y + 12, h=figh, col=FIG, arms_up=armsu, stride=strd)
        # the pile of money (shrinking), a soft warm glow beneath it
        im = _glow(im, lambda dd: dd.ellipse(
            [pcx - int(W * 0.22 * math.sqrt(max(0.04, frac))), base_y - 30,
             pcx + int(W * 0.22 * math.sqrt(max(0.04, frac))), base_y + 40],
            fill=(255, 205, 108, 70)), 40)
        d = ImageDraw.Draw(im, "RGBA")
        _cash_pile(d, pcx, base_y, frac, seed=upto * 13 + 7, glow_coin=final)
        # this chapter's chunk BLOWS off the top of the pile and away (in the
        # layout's direction), stamped with what's taking it — a physical leak.
        if not final:
            rnd = random.Random(upto * 3 + 5)
            topy = base_y - int(H * 0.30 * math.sqrt(max(0.04, start_frac)))
            for _k in range(14):
                ph = (t * 1.15 + rnd.random()) % 1.0
                bx = pcx + dirx * (ph * (W * 0.30)) + math.sin(ph * 5) * 20
                by = topy - ph * (H * 0.22) + rnd.uniform(-14, 14)
                a = int(230 * (1 - ph))
                if a > 14:
                    _rrect(d, bx, by, bx + 52, by + 28, (*GREEN, a), r=6)
                    d.ellipse([bx + 17, by + 5, bx + 35, by + 23], outline=(*GREEN_D, a), width=2)
            # the category taking the money, as a stamp riding the stream
            stf = _font(ANTON, 40)
            sxp = (pcx + dirx * int(W * 0.24)) if dirx > 0 else (pcx + dirx * int(W * 0.24) - int(stf.getlength("— " + cat)))
            d.text((sxp, int(H * 0.28)), "— " + cat, font=stf,
                   fill=(238, 128, 108, 235))
        else:
            # PAYOFF: coins rain down across a WIDE band and settle onto the little
            # pile that's yours to keep — the moving element the drain gave the rest.
            rnd = random.Random(77)
            for _k in range(22):
                ph = (t * 0.85 + rnd.random()) % 1.0
                cxp = rnd.uniform(int(W * 0.20), int(W * 0.92))
                cyp = (base_y - int(H * 0.40)) + ph * int(H * 0.40)
                a = int(240 * (1 - ph) ** 0.6)
                if a > 16:
                    _coin(d, int(cxp), int(cyp), int(12 + rnd.random() * 6), a=a,
                          face=False)
            # a soft golden light-shaft sweeps the full frame — a whole-frame moving
            # element so the long payoff never sits still.
            sweep = (t * 1.15) % 1.15
            sx = int(sweep * W * 1.2) - int(W * 0.1)
            band = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(band).polygon(
                [(sx, 0), (sx + 150, 0), (sx + 40, H), (sx - 110, H)],
                fill=(255, 226, 160, 46))
            im = Image.alpha_composite(im.convert("RGBA"),
                                       band.filter(ImageFilter.GaussianBlur(28)))
            d = ImageDraw.Draw(im, "RGBA")
        # a small price-tag on a string above the pile: what's actually LEFT — a
        # physical tag, not a centred dashboard readout.
        remaining = (LIFE_TOTAL - spent_before - active_amt * drain)
        tag = _money_str(remaining)
        tf, tg = _font(ANTON, 60), _font(DEJAVU, 24)
        tcol = GOLD if final else GREEN
        tw = tf.getlength(tag)
        ty = int(H * 0.20)
        piletop = base_y - int(H * 0.30 * math.sqrt(max(0.04, frac)))
        d.line([tagx, ty + 60, tagx, piletop], fill=(120, 128, 150, 110), width=2)
        cap = "STILL YOURS" if final else "LEFT"
        _rrect(d, tagx - tw / 2 - 16, ty - 8, tagx + tw / 2 + 16, ty + 92,
               (22, 26, 40, 210), r=14)
        d.text((tagx - tw / 2, ty), tag, font=tf, fill=(*tcol, 255))
        d.text((tagx - tg.getlength(cap) / 2, ty + 62), cap, font=tg, fill=(*FIG, 220))
        im = _label(im, number, label, col=(GOLD if final else (238, 128, 108)))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# PAYDAY — the cold open. A paycheck lands in the figure's hands and the money
# immediately starts leaking away. Sets up the whole piece.
# --------------------------------------------------------------------------
def paycheck_scene(out: Path, seconds: float = 6.0, number: str = "",
                   label: str = "EVERY PAYCHECK", extra: dict | None = None) -> Path:
    ex = extra or {}
    def bg(i, n):
        t = i / max(1, n - 1)
        # a bright payday morning that cools as the money leaves (one-way)
        k = 1.0 - 0.94 * t
        return _vgrad((int(22 + 100 * k), int(26 + 78 * k), int(46 + 46 * k)),
                      (10, 12, 22))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.80)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(16, 18, 28, 255))
        # a window of morning light behind
        wx0, wy0, wx1, wy1 = int(W * 0.60), int(H * 0.10), int(W * 0.90), int(H * 0.44)
        k = 1.0 - 0.6 * t
        im = _glow(im, lambda dd: dd.rectangle([wx0, wy0, wx1, wy1],
                   fill=(255, 224, 150, int(120 * k))), 60)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([wx0, wy0, wx1, wy1], fill=(int(60 + 120 * k), int(70 + 90 * k),
                    int(90 + 40 * k), 255), outline=(90, 100, 140, 255), width=6)
        d.line([(wx0 + wx1) // 2, wy0, (wx0 + wx1) // 2, wy1], fill=(90, 100, 140), width=4)
        # the figure, centre-left, holding a paycheck up in one hand; if express, joy fades to resignation
        cx = int(W * 0.36)
        arms = 0.0
        if ex.get("express"):
            arms = 0.5 - 0.4 * t                # arm drops as money drains (joy fades)
        _stand(d, cx, floor_y + 6, h=380, col=FIG, arms_up=arms)
        # the paycheck (a slip) held at the raised hand
        px, py = cx + 96, int(H * 0.40)
        d.rounded_rectangle([px, py, px + 190, py + 96], radius=10,
                            fill=(238, 240, 248, 255), outline=(150, 155, 172, 255), width=3)
        d.line([px + 16, py + 26, px + 174, py + 26], fill=(120, 128, 150), width=4)
        d.text((px + 16, py + 40), "PAY", font=_font(ANTON, 34), fill=(60, 120, 90, 255))
        chk = _font(ANTON, 40)
        amt = "$3,200"
        d.text((px + 174 - chk.getlength(amt), py + 40), amt, font=chk, fill=(40, 100, 70, 255))
        # money immediately streams OUT of the check toward the left and off-frame
        _coin_fall(d, 91, t, px - 40, px + 40, py + 60, count=14, spread=460)
        for _ in range(0):
            pass
        rnd = random.Random(5)
        for _k in range(9):
            ph = (t * 1.1 + rnd.random()) % 1.0
            bx = px - ph * (W * 0.42)
            byy = py + 30 + math.sin(ph * 5 + rnd.random() * 6) * 40
            a = int(230 * (1 - ph))
            if a > 14:
                _rrect(d, bx, byy, bx + 54, byy + 30, (*GREEN, a), r=6)
                d.ellipse([bx + 18, byy + 6, bx + 36, byy + 24], outline=(*GREEN_D, a), width=2)
        im = _label(im, number, label, col=GOLD)
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# TAXES — the figure at a cold official window, handing a thick stack of cash
# through the slot. A stamp thuds down.
# --------------------------------------------------------------------------
def tax_scene(out: Path, seconds: float = 6.0, number: str = "",
              label: str = "THE GOVERNMENT'S CUT", extra: dict | None = None) -> Path:
    ex = extra or {}
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 0.08 + 0.9 * t                      # cold hall opens up into light
        return _vgrad((int(18 + 96 * k), int(24 + 80 * k), int(40 + 70 * k)),
                      (8, 10, 20))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.82)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(18, 20, 32, 255))
        # official building: columns + a pediment, a service window glowing
        for col_x in (int(W * 0.60), int(W * 0.72), int(W * 0.84), int(W * 0.96)):
            d.rounded_rectangle([col_x - 22, int(H * 0.20), col_x + 22, floor_y],
                                radius=8, fill=(52, 58, 78, 255))
        d.polygon([(int(W * 0.54), int(H * 0.20)), (int(W * 1.02), int(H * 0.20)),
                   (int(W * 0.78), int(H * 0.08))], fill=(60, 66, 88, 255))
        # the teller window with a warm glow + a "TAX" sign
        wx0, wy0, wx1, wy1 = int(W * 0.62), int(H * 0.34), int(W * 0.80), int(H * 0.56)
        im = _glow(im, lambda dd: dd.rectangle([wx0, wy0, wx1, wy1],
                   fill=(255, 210, 130, 150)), 30)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([wx0, wy0, wx1, wy1], fill=(255, 224, 168, 255),
                    outline=(120, 100, 60, 255), width=5)
        d.text((wx0 + 8, wy0 - 40), "T A X", font=_font(ANTON, 40), fill=(*FIG, 230))
        # the figure at the window, arm reaching to push cash through
        cx = int(W * 0.34)
        reach = 0.5 + 0.4 * (0.5 + 0.5 * math.sin(i * 0.5))
        # emotional reaction: if express=true, arms lift higher in shock/resignation as t progresses
        base_arms = 0.28 + 0.12 * (0.5 + 0.5 * math.sin(i * 0.5))
        if ex.get("express"):
            base_arms = 0.28 + 0.4 * t           # arms lift higher over time = shock/resignation
        _stand(d, cx, floor_y + 6, h=380, col=FIG,
               arms_up=base_arms)
        # a stack of cash travelling from the figure into the window slot, repeating
        ph = (t * 1.6) % 1.0
        sx = cx + 90 + ph * (wx0 - (cx + 90))
        sy = int(H * 0.46)
        for b in range(4):
            _rrect(d, sx, sy - b * 6, sx + 74, sy + 36 - b * 6, (*GREEN, 255), r=6)
        d.ellipse([sx + 26, sy + 6, sx + 48, sy + 28], outline=(*GREEN_D, 255), width=3)
        # a red "PAID" stamp thuds down onto the window periodically
        stph = (t * 2.0) % 1.0
        if stph < 0.5:
            sc = 1.0 + (0.5 - stph) * 1.2
            sf = _font(ANTON, int(46 * sc))
            a = int(255 * min(1.0, (0.5 - stph) * 4))
            d.text((wx0 + 10, wy0 + 40), "PAID", font=sf, fill=(230, 70, 60, a))
        im = _label(im, number, label, col=(150, 122, 236))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# HOUSING — the figure small in a doorway of a lit home; each month a chunk of
# money floats out the window and drifts away.
# --------------------------------------------------------------------------
def rent_scene(out: Path, seconds: float = 6.0, number: str = "",
               label: str = "A ROOF OVER YOUR HEAD", extra: dict | None = None) -> Path:
    ex = extra or {}
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 1.0 - 0.92 * t                      # day sinks into deep evening
        return _vgrad((int(24 + 98 * k), int(28 + 80 * k), int(48 + 52 * k)),
                      (9, 10, 18))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        ground_y = int(H * 0.82)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, ground_y, W, H], fill=(16, 17, 26, 255))
        # a house silhouette centre-right: body + pitched roof + a warm window
        hx0, hx1 = int(W * 0.44), int(W * 0.80)
        hy0 = int(H * 0.40)
        d.rectangle([hx0, hy0, hx1, ground_y], fill=(40, 44, 62, 255))
        d.polygon([(hx0 - 30, hy0), (hx1 + 30, hy0),
                   ((hx0 + hx1) // 2, int(H * 0.24))], fill=(52, 56, 76, 255))
        # a door the figure stands in, and a lit window
        dxc = int(W * 0.52)
        d.rounded_rectangle([dxc - 34, ground_y - 150, dxc + 34, ground_y],
                            radius=8, fill=(26, 28, 42, 255))
        wx0, wy0 = int(W * 0.64), int(H * 0.50)
        im = _glow(im, lambda dd: dd.rectangle([wx0, wy0, wx0 + 90, wy0 + 90],
                   fill=(255, 214, 140, 170)), 26)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([wx0, wy0, wx0 + 90, wy0 + 90], fill=(255, 220, 150, 255),
                    outline=(120, 100, 60, 255), width=4)
        d.line([wx0 + 45, wy0, wx0 + 45, wy0 + 90], fill=(120, 100, 60), width=3)
        d.line([wx0, wy0 + 45, wx0 + 90, wy0 + 45], fill=(120, 100, 60), width=3)
        # the figure standing small in the doorway; if express, show the weight/burden
        stride = 0.0
        if ex.get("express"):
            stride = 0.3 * t                    # figure leans forward under weight, gets more tired
        _stand(d, dxc, ground_y, h=150, col=FIG, stride=stride)
        # RENT DUE — money floats up out of the chimney/window and drifts off
        chx, chy = int(W * 0.70), int(H * 0.28)
        d.rectangle([chx, chy, chx + 34, chy + 70], fill=(36, 40, 56, 255))
        rnd = random.Random(12)
        for _k in range(7):
            ph = (t * 0.9 + rnd.random()) % 1.0
            bx = chx + 8 + math.sin(ph * 5 + rnd.random() * 6) * 60
            byy = chy - ph * (H * 0.22)
            a = int(230 * (1 - ph))
            if a > 12:
                _rrect(d, bx, byy, bx + 52, byy + 28, (*GREEN, a), r=6)
                d.ellipse([bx + 17, byy + 5, bx + 35, byy + 23], outline=(*GREEN_D, a), width=2)
        # a small "RENT DUE" mailbox tag, lower-left
        d.text((int(W * 0.10), int(H * 0.70)), "RENT DUE", font=_font(DEJAVU, 26),
               fill=(238, 128, 108, 255))
        d.text((int(W * 0.10), int(H * 0.74)), "$1,800 / mo", font=_font(ANTON, 44),
               fill=(*FIG, 255))
        im = _label(im, number, label, col=(238, 128, 108))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# TRANSPORT — the figure at a gas pump, the dollar meter spinning up fast.
# --------------------------------------------------------------------------
def gas_scene(out: Path, seconds: float = 6.0, number: str = "",
              label: str = "GETTING AROUND", extra: dict | None = None) -> Path:
    ex = extra or {}
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 0.05 + 0.92 * t                     # night falls over the station
        return _vgrad((int(20 + 92 * (1 - k)), int(24 + 78 * (1 - k)), int(46 + 60 * (1 - k))),
                      (8, 10, 18))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        ground_y = int(H * 0.80)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, ground_y, W, H], fill=(18, 19, 28, 255))
        # a station canopy overhead, glowing
        im = _glow(im, lambda dd: dd.rectangle([int(W * 0.30), int(H * 0.12),
                   int(W * 0.98), int(H * 0.20)], fill=(150, 200, 240, 120)), 30)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([int(W * 0.30), int(H * 0.12), int(W * 0.98), int(H * 0.20)],
                    fill=(44, 52, 74, 255))
        # the pump on the right: body + a bright digital price board
        pxc = int(W * 0.72)
        d.rounded_rectangle([pxc - 70, int(H * 0.30), pxc + 70, ground_y], radius=14,
                            fill=(48, 52, 70, 255))
        bx0, by0 = pxc - 54, int(H * 0.34)
        im = _glow(im, lambda dd: dd.rectangle([bx0, by0, bx0 + 108, by0 + 90],
                   fill=(120, 235, 150, 120)), 20)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([bx0, by0, bx0 + 108, by0 + 90], fill=(14, 26, 18, 255),
                    outline=(60, 120, 80, 255), width=4)
        d.text((bx0 + 8, by0 + 6), "TOTAL", font=_font(DEJAVU, 18), fill=(120, 200, 140, 255))
        total = 18.0 + t * 62.0                 # the meter races up
        ds = f"${total:.2f}"
        d.text((bx0 + 8, by0 + 30), ds, font=_font(ANTON, 48), fill=(140, 250, 170, 255))
        # a hose from the pump to a car, and the figure holding the nozzle
        cxc = int(W * 0.40)
        d.rounded_rectangle([cxc - 150, ground_y - 70, cxc + 150, ground_y - 4],
                            radius=24, fill=(58, 92, 150, 255))
        d.rounded_rectangle([cxc - 96, ground_y - 116, cxc + 74, ground_y - 58],
                            radius=28, fill=(58, 92, 150, 255))
        d.rounded_rectangle([cxc - 80, ground_y - 106, cxc + 58, ground_y - 66],
                            radius=16, fill=(150, 180, 220, 255))
        d.ellipse([cxc - 110, ground_y - 28, cxc - 50, ground_y + 32], fill=(18, 18, 24, 255))
        d.ellipse([cxc + 50, ground_y - 28, cxc + 110, ground_y + 32], fill=(18, 18, 24, 255))
        d.line([pxc - 40, int(H * 0.52), cxc + 120, ground_y - 40],
               fill=(30, 32, 44, 255), width=8)
        # the figure between car and pump, arm up holding the nozzle; if express, show frustration
        arms = 0.30
        if ex.get("express"):
            arms = 0.30 + 0.2 * t               # arm lifts higher = frustration at rising price
        _stand(d, int(W * 0.58), ground_y + 6, h=300, col=FIG, arms_up=arms)
        # coins drain out of the pump base — fuel = money burning
        _coin_fall(d, 44, t, pxc - 30, pxc + 30, ground_y - 30, count=9, spread=140)
        im = _label(im, number, label, col=(86, 186, 206))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# FOOD — the figure at a checkout, items beeping across a scanner, the total
# climbing, the receipt printing longer and longer.
# --------------------------------------------------------------------------
def grocery_scene(out: Path, seconds: float = 6.0, number: str = "",
                  label: str = "STAYING ALIVE") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 0.05 + 0.92 * t                     # store lights ramp up bright
        return _vgrad((int(24 + 104 * k), int(28 + 96 * k), int(40 + 74 * k)),
                      (12, 14, 22))

    def _product(dd, x, base, kind, col):
        """A single grocery item drawn to READ as an object, not a bar: a can, a
        box, a bottle, or a piece of produce."""
        if kind == 0:      # can
            dd.rounded_rectangle([x - 16, base - 46, x + 16, base], radius=8, fill=(*col, 255))
            dd.ellipse([x - 16, base - 52, x + 16, base - 40], fill=(*[min(255, c + 30) for c in col], 255))
        elif kind == 1:    # box
            dd.rounded_rectangle([x - 20, base - 50, x + 20, base], radius=4, fill=(*col, 255))
            dd.line([x - 20, base - 30, x + 20, base - 30], fill=(255, 255, 255, 90), width=3)
        elif kind == 2:    # bottle
            dd.rounded_rectangle([x - 12, base - 40, x + 12, base], radius=6, fill=(*col, 255))
            dd.rectangle([x - 5, base - 58, x + 5, base - 40], fill=(*col, 255))
            dd.ellipse([x - 6, base - 64, x + 6, base - 54], fill=(220, 220, 230, 255))
        else:              # produce (round)
            dd.ellipse([x - 18, base - 36, x + 18, base], fill=(*col, 255))
            dd.line([x, base - 36, x + 3, base - 44], fill=(90, 140, 90, 255), width=4)

    PALS = [(196, 96, 84), (86, 150, 196), (120, 188, 132), (214, 176, 92),
            (170, 120, 200), (210, 130, 150)]

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.82)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(20, 22, 32, 255))
        # shelves behind, stocked with VARIED products (cans/boxes/bottles/produce)
        for row in range(3):
            sy = int(H * 0.16) + row * int(H * 0.15)
            d.rectangle([int(W * 0.05), sy, int(W * 0.62), sy + 12], fill=(52, 44, 38, 255))
            for c in range(11):
                bxx = int(W * 0.07) + c * int(W * 0.05)
                _product(d, bxx, sy, (row * 2 + c) % 4, PALS[(row * 3 + c) % len(PALS)])
        # the checkout counter + a conveyor of REAL-looking items sliding in
        cy = floor_y - 40
        d.rectangle([0, cy, W, cy + 16], fill=(56, 60, 80, 255))
        for k in range(5):
            ph = (t * 0.9 + k * 0.2) % 1.0
            ix = int(W * 0.06) + ph * int(W * 0.34)
            _product(d, ix, cy, k % 4, PALS[k % len(PALS)])
        # a shopping cart beside the figure, loaded with groceries (character prop)
        cxx = int(W * 0.26)
        d.line([cxx - 70, floor_y - 150, cxx - 56, floor_y - 30], fill=(150, 156, 176), width=6)  # handle
        d.polygon([(cxx - 56, floor_y - 96), (cxx + 60, floor_y - 96),
                   (cxx + 44, floor_y - 30), (cxx - 40, floor_y - 30)],
                  fill=(60, 66, 86, 220), outline=(150, 156, 176, 255))
        for gx in range(-4, 5):                             # basket wires
            d.line([cxx + gx * 12, floor_y - 96, cxx + gx * 10, floor_y - 30],
                   fill=(120, 126, 146, 160), width=2)
        for j, kx in enumerate((-30, 4, 34)):               # items poking out
            _product(d, cxx + kx, floor_y - 92, j % 4, PALS[(j + 2) % len(PALS)])
        d.ellipse([cxx - 44, floor_y - 34, cxx - 20, floor_y - 10], fill=(28, 30, 42, 255))
        d.ellipse([cxx + 26, floor_y - 34, cxx + 50, floor_y - 10], fill=(28, 30, 42, 255))
        # the scanner glow at the register
        rxc = int(W * 0.46)
        im = _glow(im, lambda dd: dd.ellipse([rxc - 40, cy - 30, rxc + 40, cy + 30],
                   fill=(120, 200, 255, 150)), 20)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([rxc - 20, cy - 60, rxc + 20, cy], radius=8, fill=(40, 46, 64, 255))
        # the figure at the register, reaching to scan an item
        reach = 0.30 + 0.14 * (0.5 + 0.5 * math.sin(i * 0.6))
        _stand(d, int(W * 0.62), floor_y + 6, h=420, col=FIG, arms_up=reach)
        # a register total board climbing + the receipt printing longer
        total = 40 + t * 118
        d.rounded_rectangle([int(W * 0.70), int(H * 0.28), int(W * 0.88), int(H * 0.39)],
                            radius=8, fill=(14, 20, 26, 255), outline=(60, 120, 90, 255), width=4)
        ts = f"${total:5.2f}"
        d.text((int(W * 0.71), int(H * 0.29)), ts, font=_font(ANTON, 52), fill=(140, 240, 170, 255))
        rl = int(30 + t * 220)
        d.rectangle([int(W * 0.80), int(H * 0.39), int(W * 0.80) + 46, int(H * 0.39) + rl],
                    fill=(236, 238, 246, 255))
        for ry in range(int(H * 0.41), int(H * 0.39) + rl, 18):
            d.line([int(W * 0.805), ry, int(W * 0.80) + 40, ry], fill=(150, 154, 168), width=2)
        im = _label(im, number, label, col=(120, 188, 132))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# LITTLE LEAKS — the figure on the couch, phone in hand, ringed by little
# subscription tiles each quietly siphoning a coin every month.
# --------------------------------------------------------------------------
def subs_scene(out: Path, seconds: float = 6.0, number: str = "",
               label: str = "THE LITTLE LEAKS") -> Path:
    tiles = [("STREAM", (230, 80, 70)), ("MUSIC", (120, 200, 140)),
             ("CLOUD", (120, 170, 240)), ("GAME", (200, 150, 240)),
             ("NEWS", (240, 180, 90)), ("GYM", (240, 120, 160))]

    def bg(i, n):
        t = i / max(1, n - 1)
        k = 1.0 - 0.92 * t                      # the room sinks toward dark
        return _vgrad((int(18 + 96 * k), int(20 + 80 * k), int(34 + 60 * k)),
                      (9, 10, 18))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.84)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(16, 17, 27, 255))
        # a couch
        d.rounded_rectangle([int(W * 0.22), int(H * 0.52), int(W * 0.56), floor_y + 8],
                            radius=30, fill=(30, 32, 50, 255))
        d.rounded_rectangle([int(W * 0.20), int(H * 0.44), int(W * 0.28), floor_y],
                            radius=24, fill=(36, 38, 58, 255))
        # the figure sits, phone-lit, scrolling
        joints = _sit(d, int(W * 0.36), floor_y + 4, h=420, col=(150, 178, 228),
                      lean=10, reach=0.4, on_ground=False)
        hf = joints["hand"]
        px, py = hf[0] + 4, hf[1] - 30
        im = _glow(im, lambda dd: dd.ellipse([px - 150, py - 140, px + 150, py + 160],
                   fill=(90, 150, 230, 130)), 44)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([px - 28, py - 52, px + 28, py + 52], radius=12,
                            fill=(18, 22, 36, 255), outline=(80, 92, 130, 255), width=4)
        # the subscription tiles floating around, each pulling a coin to itself
        cxc, cyc = int(W * 0.66), int(H * 0.46)
        for k, (name, col) in enumerate(tiles):
            ang = k / len(tiles) * 2 * math.pi + t * 0.6
            tx = cxc + math.cos(ang) * int(W * 0.20)
            ty = cyc + math.sin(ang) * int(H * 0.26)
            pulse = 0.5 + 0.5 * math.sin(i * 0.3 + k)
            _rrect(d, tx - 54, ty - 40, tx + 54, ty + 40, (*col, 255), r=16)
            nf = _font(DEJAVU, 22)
            d.text((tx - nf.getlength(name) / 2, ty - 30), name, font=nf, fill=(20, 22, 30, 255))
            d.text((tx - 26, ty + 2), f"${5 + k}/mo", font=_font(ANTON, 30), fill=(20, 22, 30, 255))
            # a coin siphons from the figure toward this tile
            ph = (t * 1.3 + k / len(tiles)) % 1.0
            mx = joints["shoulder"][0] + (tx - joints["shoulder"][0]) * ph
            my = joints["shoulder"][1] - 40 + (ty - (joints["shoulder"][1] - 40)) * ph
            a = int(230 * (1 - abs(ph - 0.5) * 2))
            if a > 20:
                _coin(d, int(mx), int(my), 14, a=a)
        im = _label(im, number, label, col=(240, 178, 92))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# WHAT'S LEFT — the payoff. The figure holds the small glowing amount that's
# actually theirs and walks toward a warm horizon: little, but yours to choose.
# --------------------------------------------------------------------------
def savings_scene(out: Path, seconds: float = 6.0, number: str = "",
                  label: str = "ACTUALLY YOURS") -> Path:
    def bg(i, n):
        t = i / max(1, n - 1)
        warm = _ease(t)
        return _vgrad((int(28 + 58 * warm), int(32 + 70 * warm), int(64 + 44 * warm)),
                      (18, 16 + int(20 * warm), 30))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        hz = int(H * 0.72)
        sx, sy = int(W * 0.62), hz - int(_ease(t) * H * 0.20)
        im = _glow(im, lambda dd: dd.ellipse([sx - 150, sy - 150, sx + 150, sy + 150],
                   fill=(255, 200, 120, 200)), 80)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([sx - 90, sy - 90, sx + 90, sy + 90], fill=(255, 224, 168, 255))
        d.rectangle([0, hz, W, H], fill=(26, 22, 34, 255))
        for gx in range(0, W, 90):
            d.line([gx + int(t * 30) % 90, hz + 20, gx + 40 + int(t * 30) % 90, hz + 20],
                   fill=(40, 34, 48, 200), width=3)
        # the figure walks toward the light, one arm raised holding a small coin
        cx = int(W * 0.30 + t * W * 0.10)
        feet = hz + 30
        rise = _ease(max(0.0, (t - 0.3) / 0.7))
        stride = 11 * math.sin(i * 0.4)
        top = _stand(d, cx, feet, h=340, col=FIG, arms_up=0.5 * rise, stride=stride)
        # a single warm coin glowing in the raised hand
        hx = cx + int(70 * (0.5 + 0.5 * rise))
        hy = top[1] - int(60 * rise) - 30
        im = _glow(im, lambda dd: _coin(dd, hx, hy, 30, a=200), 16)
        d = ImageDraw.Draw(im, "RGBA")
        _coin(d, hx, hy, 26)
        im = _label(im, number, label, col=(255, 224, 168))
        return im

    return _render(draw, out, seconds, bg)


# --------------------------------------------------------------------------
# THE TRAP — the figure runs on a treadmill going nowhere: every raise gets
# spent, so more money in just means more money out. Running to stand still.
# --------------------------------------------------------------------------
def treadmill_scene(out: Path, seconds: float = 6.0, number: str = "",
                    label: str = "RUNNING TO STAND STILL", extra: dict | None = None) -> Path:
    ex = extra or {}
    def bg(i, n):
        t = i / max(1, n - 1)
        k = 0.05 + 0.92 * t                     # the gym lights climb
        return _vgrad((int(20 + 100 * k), int(24 + 86 * k), int(40 + 66 * k)),
                      (10, 12, 20))

    def draw(i, n, im):
        t = i / max(1, n - 1)
        floor_y = int(H * 0.80)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, floor_y, W, H], fill=(16, 18, 28, 255))
        # the treadmill: a slanted deck + a scrolling belt + an upright console
        cx = int(W * 0.40)
        deck_y = floor_y - 6
        d.rounded_rectangle([cx - 210, deck_y, cx + 150, deck_y + 34], radius=14,
                            fill=(40, 44, 62, 255))
        # belt scroll lines racing backward (motion under the runner)
        for k in range(9):
            bxp = (cx + 150) - ((k * 44 + int(t * 520)) % 360)
            d.line([bxp, deck_y + 8, bxp - 22, deck_y + 8], fill=(70, 76, 100, 255), width=5)
        # the console with a speed readout climbing
        d.rounded_rectangle([cx + 150, deck_y - 150, cx + 176, deck_y + 20],
                            radius=8, fill=(46, 50, 68, 255))
        d.rounded_rectangle([cx + 120, deck_y - 200, cx + 206, deck_y - 150],
                            radius=8, fill=(14, 22, 26, 255), outline=(60, 120, 90, 255), width=3)
        spd = 4.0 + t * 8.0
        d.text((cx + 128, deck_y - 194), f"{spd:0.1f}", font=_font(ANTON, 40),
               fill=(140, 240, 170, 255))
        d.text((cx + 128, deck_y - 150), "MPH", font=_font(DEJAVU, 16), fill=(120, 200, 140, 255))
        # the figure runs IN PLACE — legs swing but it never moves forward; if express, show exhaustion
        stride = 34 * math.sin(i * 0.9)
        bob = int(6 * abs(math.sin(i * 0.9)))
        arms = 0.14
        if ex.get("express"):
            arms = 0.14 + 0.25 * t              # arms lift higher = exhaustion/struggle
        _stand(d, cx - 30, deck_y - bob, h=360, col=FIG, arms_up=arms, stride=stride)
        # money pours IN from the top-right and immediately drains OUT bottom-left:
        # every raise you earn is instantly spent — net zero, forever.
        _coin_fall(d, 71, t, int(W * 0.66), int(W * 0.72), int(H * 0.14),
                   count=8, spread=int(H * 0.30))
        rnd = random.Random(23)
        for _k in range(8):
            ph = (t * 1.2 + rnd.random()) % 1.0
            bx = int(W * 0.36) - ph * (W * 0.34)
            byy = int(H * 0.44) + ph * (H * 0.30)
            a = int(220 * (1 - ph))
            if a > 14:
                _rrect(d, bx, byy, bx + 50, byy + 27, (*GREEN, a), r=6)
                d.ellipse([bx + 16, byy + 5, bx + 34, byy + 22], outline=(*GREEN_D, a), width=2)
        im = _label(im, number, label, col=(240, 178, 92))
        return im

    return _render(draw, out, seconds, bg)


if __name__ == "__main__":
    out = REPO / "scene_smoke"
    out.mkdir(exist_ok=True)
    sleep_scene(out / "sleep.mp4", 6)
    work_scene(out / "work.mp4", 6)
    screen_scene(out / "screen.mp4", 6)
    free_scene(out / "free.mp4", 6)
    print("scenes ->", out)
