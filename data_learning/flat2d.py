#!/usr/bin/env python3
"""FLAT 2D MOTION-GRAPHIC ENGINE (CURIOSITY_BRAIN §7.5 v10 — the pro rebuild).

The retired grammar (cartoon Earth, 3D bar slabs, comparison lanes, counters)
is gone. Numbers and ideas are now shown as *designed* flat 2D — the Vox /
Kurzgesagt register: deep gradient ground, restrained palette, one idea per
frame, big confident type, generous negative space, smooth motion. This is the
look the operator picked on pixels (sample v2).

Every template renders a self-contained clip at 1920x1080 / 30fps:

    number_reveal(text, sub, out, seconds)   one hero number counts up on an arc
    comparison(rows, out, seconds, title)    2-4 entities, bars grow left-aligned
    title_card(kicker, title, out, seconds)  chapter / statement card
    statement(line, out, seconds)            a single sentence, centered, calm

Design tokens live in PALETTE. Anton (assets/fonts) carries every number; a
bold grotesque carries labels. No 3D, no charts-with-axes, no lanes.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
REPO = Path(__file__).resolve().parent.parent
ANTON = str(REPO / "assets" / "fonts" / "Anton-Regular.ttf")
_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PALETTE = {
    "bg_top": (13, 16, 48),      # deep indigo
    "bg_bot": (4, 4, 14),        # near black
    "ink": (255, 255, 255),
    "muted": (185, 196, 224),    # soft blue-grey label
    "gold": (255, 211, 122),     # warm accent
    "blue": (120, 170, 255),     # cool accent
    "star": (150, 160, 190),
}


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _bg(seed: int = 7) -> Image.Image:
    """Vertical indigo→black gradient with a scatter of faint stars — the
    shared ground so every flat beat reads as one designed system."""
    yy = np.linspace(0, 1, H)[:, None]
    t, b = PALETTE["bg_top"], PALETTE["bg_bot"]
    grad = np.zeros((H, W, 3), np.uint8)
    for c in range(3):
        grad[..., c] = np.clip(t[c] + (b[c] - t[c]) * yy, 0, 255)
    im = Image.fromarray(grad, "RGB")
    d = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    for _ in range(150):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([1, 1, 1, 2])
        c = rnd.randint(70, 150)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(c, c, int(c * 1.1)))
    return im


def _glow_text(base: Image.Image, xy, text, font, fill, glow, blur=10):
    """Draw text with a soft colored glow underneath — the premium tell that
    separates designed type from a default template. Glow is blurred at half
    resolution (visually identical for a soft halo, ~4x faster)."""
    small = (base.width // 2, base.height // 2)
    layer = Image.new("RGBA", small, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((xy[0] // 2, xy[1] // 2), text,
           font=font.font_variant(size=max(1, font.size // 2)), fill=glow)
    layer = layer.filter(ImageFilter.GaussianBlur(max(1, blur // 2)))
    layer = layer.resize(base.size, Image.BILINEAR)
    out = Image.alpha_composite(base.convert("RGBA"), layer)
    d2 = ImageDraw.Draw(out)
    d2.text(xy, text, font=font, fill=fill)
    return out.convert("RGB")


def _center_x(draw, text, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return (W - (bb[2] - bb[0])) // 2


def _spaced(s: str) -> str:
    return "   ".join(s.upper())


def _encode(frames_dir: Path, out: Path):
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", str(frames_dir / "f%05d.png"), "-c:v", "libx264",
         "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)],
        check=True)


def _render(draw_fn, out: Path, seconds: float, seed: int = 7):
    """Render `seconds` of frames with draw_fn(i, n, im)->im, piping raw RGB
    straight into ffmpeg — no per-frame PNG I/O (the old bottleneck)."""
    import subprocess
    n = max(2, int(round(seconds * FPS)))
    bg = _bg(seed)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        im = draw_fn(i, n, bg.copy())
        proc.stdin.write(im.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    return out


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
def number_reveal(text: str, sub: str, out: Path, seconds: float = 6.0,
                  label: str = "", entity: str = "") -> Path:
    """One hero number counting up, riding a soft orbital arc with a glowing
    particle (sample v2 — the look the operator picked). `text` is the final
    number string (commas ok); `sub` the unit; `label` the caption above;
    `entity` names the moving particle (e.g. 'THE SUN')."""
    try:
        target = int("".join(ch for ch in text if ch.isdigit()) or "0")
    except ValueError:
        target = 0
    big = _font(ANTON, 200)
    unit = _font(ANTON, 66)
    capf = _font(_DEJAVU, 34)
    lblf = _font(_DEJAVU, 24)
    cx, cy, rad = W // 2, int(H * 1.9), int(H * 1.55)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        d.arc([cx - rad, cy - rad, cx + rad, cy + rad], 250, 290,
              fill=(*PALETTE["blue"], 90), width=3)
        p = _ease(min(i / (n * 0.75), 1.0))
        ang = math.radians(250 + 40 * p)
        px, py = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        for k in range(1, 10):
            pa = _ease(min((i - k * 1.5) / (n * 0.75), 1.0))
            a2 = math.radians(250 + 40 * pa)
            tx, ty = cx + rad * math.cos(a2), cy + rad * math.sin(a2)
            d.ellipse([tx - 4, ty - 4, tx + 4, ty + 4],
                      fill=(*PALETTE["gold"], max(0, 120 - k * 12)))
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([px - 26, py - 26, px + 26, py + 26],
                                     fill=(*PALETTE["gold"], 150))
        glow = glow.filter(ImageFilter.GaussianBlur(12))
        im2 = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
        d = ImageDraw.Draw(im2, "RGBA")
        d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 238, 200, 255))
        if entity:
            d.text((px + 16, py - 10), entity, font=lblf,
                   fill=(230, 235, 255, 220))
        cnt = int(target * _ease(min(max(i - 18, 0) / (FPS * 1.8), 1.0)))
        s = f"{cnt:,}"
        nx, ny = _center_x(d, s, big), int(H * 0.30)
        im2 = _glow_text(im2, (nx, ny), s, big, (*PALETTE["ink"], 255),
                         (*PALETTE["gold"], 120), blur=12)
        d = ImageDraw.Draw(im2, "RGBA")
        if sub:
            d.text((_center_x(d, sub, unit), ny + 172), sub, font=unit,
                   fill=(*PALETTE["gold"], 255))
        if label:
            a = min(max(i - 30, 0) / 12, 1.0)
            cap = _spaced(label)
            d.text((_center_x(d, cap, capf), ny - 58), cap, font=capf,
                   fill=(*PALETTE["muted"], int(230 * a)))
        return im2

    return _render(draw, out, seconds)


def comparison(rows: list[dict], out: Path, seconds: float = 6.0,
               title: str = "") -> Path:
    """2-4 entities compared by a value, drawn as clean left-aligned bars that
    grow — NOT lanes, NOT 3D slabs. Each row: {name, value, display}. The
    largest sets the scale; bars are thin, rounded, gold, with the value in
    Anton at the bar's end. This is a *chart done with taste*, used briefly."""
    rows = rows[:4]
    vmax = max((float(r["value"]) for r in rows), default=1.0) or 1.0
    namef = _font(_DEJAVU, 34)
    valf = _font(ANTON, 46)
    titlef = _font(_DEJAVU, 30)
    x0, x1 = int(W * 0.16), int(W * 0.82)
    top, gap = int(H * 0.34), int(H * 0.135)
    barh = 26

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        if title:
            t = _spaced(title)
            d.text((_center_x(d, t, titlef), int(H * 0.18)), t, font=titlef,
                   fill=(*PALETTE["muted"], 235))
        grow = _ease(min(i / (n * 0.6), 1.0))
        for k, r in enumerate(rows):
            y = top + k * gap
            d.text((x0, y - 44), str(r["name"]), font=namef,
                   fill=(*PALETTE["ink"], 235))
            full = (x1 - x0) * (float(r["value"]) / vmax)
            w = max(4.0, full * grow)
            d.rounded_rectangle([x0, y, x0 + (x1 - x0), y + barh], radius=13,
                                fill=(*PALETTE["blue"], 40))
            d.rounded_rectangle([x0, y, x0 + w, y + barh], radius=13,
                                fill=(*PALETTE["gold"], 255))
            disp = str(r.get("display", r["value"]))
            av = min(max((i - n * 0.5) / (n * 0.3), 0), 1)
            d.text((x0 + w + 18, y - 12), disp, font=valf,
                   fill=(*PALETTE["ink"], int(255 * av)))
        return im

    return _render(draw, out, seconds)


def title_card(kicker: str, title: str, out: Path,
               seconds: float = 3.0) -> Path:
    """A chapter / opening card: small spaced kicker over a big Anton title,
    fading up on the shared ground. Never a bare title-on-black."""
    kf = _font(_DEJAVU, 30)
    tf = _font(ANTON, 130)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        a = min(i / (n * 0.35), 1.0)
        k = _spaced(kicker)
        d.text((_center_x(d, k, kf), int(H * 0.40)), k, font=kf,
               fill=(*PALETTE["gold"], int(235 * a)))
        im2 = _glow_text(im, (_center_x(d, title, tf), int(H * 0.46)),
                         title, tf, (*PALETTE["ink"], 255),
                         (*PALETTE["blue"], int(90 * a)), blur=14)
        return im2

    return _render(draw, out, seconds)


def statement(line: str, out: Path, seconds: float = 4.0) -> Path:
    """A single calm sentence, wrapped and centered — the reflective beat."""
    f = _font(_DEJAVU, 52)
    words, lines, cur = line.split(), [], ""
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for wd in words:
        t = (cur + " " + wd).strip()
        if tmp.textbbox((0, 0), t, font=f)[2] > W * 0.72 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = t
    if cur:
        lines.append(cur)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        a = min(i / (n * 0.3), 1.0)
        total = len(lines) * 68
        y = (H - total) // 2
        for ln in lines:
            d.text((_center_x(d, ln, f), y), ln, font=f,
                   fill=(*PALETTE["ink"], int(240 * a)))
            y += 68
        return im

    return _render(draw, out, seconds)


if __name__ == "__main__":
    # smoke: render one of each into ./flat2d_smoke/
    out = REPO / "flat2d_smoke"
    out.mkdir(exist_ok=True)
    number_reveal("828,000", "KM / H", out / "num.mp4", 5,
                  label="our speed through the galaxy", entity="THE SUN")
    comparison([{"name": "Usain Bolt", "value": 44, "display": "44 km/h"},
                {"name": "Jet airliner", "value": 900, "display": "900 km/h"},
                {"name": "Rifle bullet", "value": 3400, "display": "3,400 km/h"}],
               out / "cmp.mp4", 5, title="how fast is fast")
    title_card("Chapter One", "The Sky", out / "title.mp4", 3)
    statement("You have never been still — not for one second of your life.",
              out / "stmt.mp4", 4)
    print("smoke clips ->", out)
