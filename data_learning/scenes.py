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
    # SLIM average build (matches the seated figure the operator likes): narrow
    # torso, legs pulled in (small hips), and arms drawn OUTSIDE the body with a
    # real gap so he never reads as a fat armless blob.
    r = h * 0.10                                     # head radius
    head_cy = feet_y - h + r
    sh_y = head_cy + r + h * 0.015
    hip_y = feet_y - h * 0.44
    tw = h * 0.185                                   # SLIM shoulders
    waist = h * 0.15                                 # slim waist/hip (small hips)
    lw = h * 0.092                                   # slim legs
    aw = h * 0.075                                   # slim arms
    leg_dx = lw * 0.6                                # legs close together (narrow hips)
    # legs — drop from the bottom of the torso, close together
    _limb(d, cx - leg_dx, hip_y - lw * 0.2, cx - leg_dx - stride, feet_y, lw, col)
    _limb(d, cx + leg_dx, hip_y - lw * 0.2, cx + leg_dx + stride, feet_y, lw, col)
    # torso — a slim body, only a slight taper
    d.polygon([(cx - tw / 2, sh_y), (cx + tw / 2, sh_y),
               (cx + waist / 2, hip_y), (cx - waist / 2, hip_y)], fill=col)
    _rrect(d, cx - tw / 2, sh_y - lw * 0.2, cx + tw / 2, sh_y + lw * 0.3, col, r=lw * 0.3)
    _rrect(d, cx - waist / 2, hip_y - lw * 0.15, cx + waist / 2, hip_y + lw * 0.1, col, r=lw * 0.25)
    # arms — start at the shoulder corner and hang DOWN-and-out, sitting OUTSIDE
    # the torso so a clear triangular gap (the armpit) shows. Up -> a wide V.
    shx = tw * 0.46
    hxd = tw / 2 + aw * 0.5 + h * 0.035              # DOWN: hand outside body (gap)
    hyd = hip_y - sh_y - h * 0.03
    hxu, hyu = h * 0.24, -(sh_y - head_cy) - h * 0.09  # UP: high + wide V
    hx = hxd + (hxu - hxd) * arms_up
    hy = hyd + (hyu - hyd) * arms_up
    for sgn in (-1, 1):
        _limb(d, cx + sgn * shx, sh_y + aw * 0.2, cx + sgn * hx, sh_y + hy, aw, col)
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


def _render(draw_fn, out: Path, seconds: float, bg_fn):
    """Pipe raw RGB straight to ffmpeg. bg_fn(i,n)->Image builds the per-frame
    environment; draw_fn(i,n,im)->Image adds the character + props + accent."""
    n = max(2, int(round(seconds * FPS)))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        im = draw_fn(i, n, bg_fn(i, n)).convert("RGB")
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


if __name__ == "__main__":
    out = REPO / "scene_smoke"
    out.mkdir(exist_ok=True)
    sleep_scene(out / "sleep.mp4", 6)
    work_scene(out / "work.mp4", 6)
    screen_scene(out / "screen.mp4", 6)
    free_scene(out / "free.mp4", 6)
    print("scenes ->", out)
