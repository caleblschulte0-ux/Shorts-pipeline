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
# THE CHARACTER — one clean, consistently-proportioned pictogram, posed by real
# forward-kinematics joints (never hand-placed blobs). Angles are degrees, y-down:
# 0=right, 90=down, -90=up, 180=left. Every scene draws the SAME figure so the
# desk/phone poses read as deliberate, not clunky.
# --------------------------------------------------------------------------
def _pt(base, deg, length):
    a = math.radians(deg)
    return (base[0] + math.cos(a) * length, base[1] + math.sin(a) * length)


def _chain(d, pts, w, col):
    for a, b in zip(pts, pts[1:]):
        _capsule(d, a[0], a[1], b[0], b[1], w, col)


def _person(d, hip, pose, col=FIG, s=1.0):
    """Draw the figure from a hip anchor + a pose (joint angles). Returns key
    joints (head, hands) so a scene can attach props (a phone, a keyboard)."""
    L = {"torso": 150 * s, "ua": 82 * s, "fa": 78 * s, "th": 96 * s, "sh": 96 * s}
    hr = int(44 * s)
    tw, lw = int(58 * s), int(28 * s)
    back = tuple(int(c * 0.82) for c in col)          # far-side limbs, shaded
    shoulder = _pt(hip, pose["torso"], L["torso"])
    head_c = _pt(shoulder, pose.get("neck", pose["torso"]), hr + int(20 * s))
    knee_f = _pt(hip, pose["thigh_f"], L["th"]); foot_f = _pt(knee_f, pose["shin_f"], L["sh"])
    knee_b = _pt(hip, pose["thigh_b"], L["th"]); foot_b = _pt(knee_b, pose["shin_b"], L["sh"])
    el_f = _pt(shoulder, pose["ua_f"], L["ua"]); ha_f = _pt(el_f, pose["fa_f"], L["fa"])
    el_b = _pt(shoulder, pose["ua_b"], L["ua"]); ha_b = _pt(el_b, pose["fa_b"], L["fa"])
    # far side first (behind torso), then torso, then near side, then head
    _chain(d, [hip, knee_b, foot_b], lw, back)
    _chain(d, [shoulder, el_b, ha_b], lw, back)
    _chain(d, [hip, shoulder], tw, col)
    _chain(d, [hip, knee_f, foot_f], lw, col)
    _chain(d, [shoulder, el_f, ha_f], lw, col)
    d.ellipse([head_c[0] - hr, head_c[1] - hr, head_c[0] + hr, head_c[1] + hr], fill=col)
    return {"head": head_c, "hr": hr, "hand_f": ha_f, "hand_b": ha_b,
            "shoulder": shoulder, "hip": hip}


# clean named poses (front/back limb angles). Small sways are added per-scene.
POSE_STAND = {"torso": -90, "thigh_f": 78, "shin_f": 90, "thigh_b": 102,
              "shin_b": 90, "ua_f": 60, "fa_f": 80, "ua_b": 120, "fa_b": 100}
POSE_ARMS_UP = {"torso": -90, "thigh_f": 80, "shin_f": 92, "thigh_b": 100,
                "shin_b": 92, "ua_f": -55, "fa_f": -35, "ua_b": -125, "fa_b": -145}
POSE_DESK = {"torso": -68, "thigh_f": 6, "shin_f": 92, "thigh_b": 12, "shin_b": 92,
             "ua_f": 26, "fa_f": 40, "ua_b": 34, "fa_b": 46}
# seated on the floor, knees up, back upright but shoulders rounded, both hands
# holding a phone up in front of a downward-tilted head — a grounded doomscroller,
# NOT tilted/falling.
POSE_PHONE = {"torso": -86, "neck": -66, "thigh_f": -34, "shin_f": 72,
              "thigh_b": -20, "shin_b": 80, "ua_f": -52, "fa_f": -20,
              "ua_b": -64, "fa_b": -30}


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
        # the FIGURE — one clean rig, seated at the desk, reaching to the keyboard.
        # a tiny typing bob keeps it alive.
        pose = dict(POSE_DESK)
        pose["fa_f"] += 6 * math.sin(i * 0.6)        # near forearm taps
        joints = _person(d, hip, pose, col=FIG, s=0.95)
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
        # up to a downward-tilted face. Grounded, upright — absorbed, not falling.
        lit = (150, 185, 235)
        hip = (int(W * 0.40), floor_y + 8)
        pose = dict(POSE_PHONE)
        pose["fa_f"] += 3 * math.sin(i * 0.3)        # tiny scroll-thumb motion
        joints = _person(d, hip, pose, col=lit, s=1.05)
        # the phone in the hands, tilted up toward the face, feed scrolling.
        hf = joints["hand_f"]
        pcx, pcy = hf[0] + 4, hf[1] - 30
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
        # the FIGURE walks toward the light; arms rise from its sides to overhead
        # as it frees up (the clean rig, interpolating stand -> arms-up).
        cx = int(W * 0.30 + t * W * 0.16)
        hip = (cx, hz + 6)
        rise = _ease(max(0.0, (t - 0.35) / 0.65))
        stride = 10 * math.sin(i * 0.4)
        pose = dict(POSE_STAND)
        for key in ("ua_f", "fa_f", "ua_b", "fa_b"):
            pose[key] = POSE_STAND[key] + (POSE_ARMS_UP[key] - POSE_STAND[key]) * rise
        pose["thigh_f"] = 78 + stride
        pose["thigh_b"] = 102 - stride
        _person(d, hip, pose, col=FIG, s=1.0)
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
