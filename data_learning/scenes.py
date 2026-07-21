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
        # the FIGURE — clearly seated on a chair, hunched toward the monitor
        cx = int(W * 0.42)
        hips_y = desk_y - 40
        bob = 4 * math.sin(i * 0.5)
        # chair back behind
        d.rounded_rectangle([cx - 70, hips_y - 190, cx - 46, hips_y + 10], radius=12,
                            fill=(44, 40, 52, 255))
        d.rounded_rectangle([cx - 72, hips_y - 6, cx + 40, hips_y + 18], radius=10,
                            fill=(44, 40, 52, 255))                        # seat
        # hunched spine: hips -> shoulders leaning toward the screen
        sh_x, sh_y = cx + 40, hips_y - 150 + bob
        _capsule(d, cx - 18, hips_y, sh_x, sh_y, 60, FIG)                  # back/torso
        d.ellipse([sh_x - 4, sh_y - 78, sh_x + 68, sh_y - 6], fill=FIG)    # head, tipped forward
        _capsule(d, sh_x + 24, sh_y - 20, int(W * 0.52), desk_y - 12, 24, FIG)  # arm to keyboard
        _capsule(d, cx - 12, hips_y + 8, cx + 30, desk_y + 40, 26, (210, 214, 226))  # thigh/leg
        # keyboard
        d.rounded_rectangle([int(W * 0.49), desk_y - 16, int(W * 0.60), desk_y - 4],
                            radius=4, fill=(60, 64, 82, 255))
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
        cx, cy = int(W * 0.52), int(H * 0.56)
        # the phone — big, tilted, a bright feed scrolling; it lights the figure
        pw, ph = 300, 560
        phone = Image.new("RGBA", im.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(phone)
        px0, py0 = cx - pw // 2, cy - ph // 2
        pd.rounded_rectangle([px0, py0, px0 + pw, py0 + ph], radius=44,
                             fill=(20, 24, 40, 255), outline=(60, 70, 100, 255), width=6)
        # bright scrolling feed
        for r in range(7):
            ry = py0 + 30 + ((r * 90 + int(t * 420)) % (ph - 120))
            pd.rounded_rectangle([px0 + 24, ry, px0 + pw - 24, ry + 60], radius=12,
                                 fill=(150, 190, 245, 255))
            pd.ellipse([px0 + 34, ry + 8, px0 + 74, ry + 48], fill=(255, 224, 150, 255))
        phone = phone.rotate(-12, resample=Image.BICUBIC, center=(cx, cy))
        # cast the phone's glow onto the scene BEFORE compositing the phone
        im = _glow(im, lambda dd: dd.ellipse([cx - 260, cy - 300, cx + 200, cy + 260],
                                             fill=(90, 150, 230, 150)), 60)
        # the FIGURE curled toward the phone, face lit
        d = ImageDraw.Draw(im, "RGBA")
        fx, fy = int(W * 0.30), int(H * 0.60)
        lit = (150, 185, 235)
        d.ellipse([fx - 40, fy - 210, fx + 40, fy - 130], fill=lit)         # head (lit blue)
        _capsule(d, fx, fy - 140, fx + 60, fy + 10, 62, lit)                # curled torso
        _capsule(d, fx + 40, fy - 60, cx - 90, cy - 20, 26, lit)           # arm reaching phone
        _capsule(d, fx + 30, fy + 6, fx + 150, fy + 40, 30, lit)           # legs tucked
        im = Image.alpha_composite(im.convert("RGBA"), phone)
        # a faint pull — motion lines from the figure into the phone
        d = ImageDraw.Draw(im, "RGBA")
        for k in range(5):
            ph2 = (t * 1.4 + k * 0.2) % 1.0
            ax = fx + 60 + ph2 * (cx - fx - 100)
            ay = fy - 90 + ph2 * (cy - fy + 40)
            d.ellipse([ax - 4, ay - 4, ax + 4, ay + 4],
                      fill=(150, 190, 245, int(200 * (1 - ph2))))
        im = _label(im, number, label)
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
        # the FIGURE walking toward the light, arms rising as it frees up
        cx = int(W * 0.30 + t * W * 0.16)
        feet = hz + 30
        rise = _ease(max(0.0, (t - 0.4) / 0.6))
        d.ellipse([cx - 34, feet - 250, cx + 34, feet - 182], fill=FIG)     # head
        _capsule(d, cx, feet - 186, cx, feet - 70, 58, FIG)                 # torso
        arm = -1.2 * rise
        _capsule(d, cx - 4, feet - 160, cx - 70, feet - 160 + int(90 * arm), 22, FIG)
        _capsule(d, cx + 4, feet - 160, cx + 70, feet - 160 + int(90 * arm), 22, FIG)
        stride = 26 * math.sin(i * 0.4)
        _capsule(d, cx - 4, feet - 74, cx - 24 - stride, feet, 26, FIG)
        _capsule(d, cx + 4, feet - 74, cx + 24 + stride, feet, 26, FIG)
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
