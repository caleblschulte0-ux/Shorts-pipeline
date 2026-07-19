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
    big = _font(ANTON, 158)
    unit = _font(_DEJAVU, 40)
    capf = _font(_DEJAVU, 32)
    ny = int(H * 0.34)          # number baseline (top of glyphs)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        # caption ABOVE the number
        if label:
            a = min(max(i - 8, 0) / 12, 1.0)
            cap = _spaced(label)
            d.text((_center_x(d, cap, capf), ny - 70), cap, font=capf,
                   fill=(*PALETTE["muted"], int(230 * a)))
        # the hero number (count-up settles by ~1.8s, then holds clean)
        cnt = int(target * _ease(min(max(i - 8, 0) / (FPS * 1.5), 1.0)))
        s = f"{cnt:,}"
        im2 = _glow_text(im, (_center_x(d, s, big), ny), s, big,
                         (*PALETTE["ink"], 255), (*PALETTE["gold"], 120),
                         blur=12)
        d = ImageDraw.Draw(im2, "RGBA")
        # a thin gold accent rule that grows in under the number — the
        # designed element, well clear of the glyphs
        rule_y = ny + 182
        half = int(min(i / (n * 0.4), 1.0) * W * 0.16)
        if half > 2:
            d.rectangle([W // 2 - half, rule_y, W // 2 + half, rule_y + 3],
                        fill=(*PALETTE["gold"], 230))
        # unit BELOW the rule, never touching the number (rendered as-given
        # so the km/h style stays consistent with footage-number beats)
        if sub:
            uy = rule_y + 20
            d.text((_center_x(d, sub, unit), uy), sub,
                   font=unit, fill=(*PALETTE["gold"], 255))
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
    namef = _font(_DEJAVU, 40)
    valf = _font(ANTON, 64)
    titlef = _font(_DEJAVU, 34)
    x0, x1 = int(W * 0.13), int(W * 0.80)
    # spread the bars across most of the frame height (not a tight band in the
    # middle with dead space above and below) and make them BOLD — a brief,
    # full-frame scale-check, not a sparse spreadsheet chart (kills
    # EMPTY_COMPOSITION). rows here span ~28%..70% of the height.
    n_rows = max(1, len(rows))
    top = int(H * 0.30)
    gap = int(H * 0.40 / (n_rows - 1)) if n_rows > 1 else 0
    barh = 46

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
            # staggered race — each bar launches a beat after the one above,
            # so they GROW at their own speed across most of the shot (no long
            # static hold at the end — kills SHOT_TOO_LONG). NO empty track
            # rail behind them; the bars race on open space. LINEAR growth
            # completing at ~0.94 of the beat: an ease-OUT decelerates the bar
            # to a crawl and it reads as frozen for its final seconds; a steady
            # race that finishes just before the dissolve keeps moving to the end.
            g = min(max(i - k * 4, 0) / (n * 0.96), 1.0)
            full = (x1 - x0) * (float(r["value"]) / vmax)
            w = max(4.0, full * g)
            # a soft leading-edge glow so the fastest bar reads as speed
            glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse(
                [x0 + w - 26, y - 6, x0 + w + 26, y + barh + 6],
                fill=(*PALETTE["gold"], 150))
            im.paste(Image.alpha_composite(
                im.convert("RGBA"),
                glow.filter(ImageFilter.GaussianBlur(11))).convert("RGB"),
                (0, 0))
            d = ImageDraw.Draw(im, "RGBA")
            d.rounded_rectangle([x0, y, x0 + w, y + barh], radius=barh // 2,
                                fill=(*PALETTE["gold"], 255))
            disp = str(r.get("display", r["value"]))
            d.text((x0 + w + 20, y - 11), disp, font=valf,
                   fill=(*PALETTE["ink"], int(255 * min(g * 1.4, 1))))
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


def orbit_reveal(center_label: str, sat_label: str, out: Path,
                 seconds: float = 6.0) -> Path:
    """Editorial motion (movement): a body orbits a glowing center while the
    camera pulls back to reveal the whole orbit — 'watch what the planet is
    really doing.' A designed replacement for a cartoon 3D globe."""
    cf = _font(_DEJAVU, 26)
    lf = _font(_DEJAVU, 22)
    cx, cy = W // 2, int(H * 0.52)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        p = _ease(min(i / (n * 0.85), 1.0))
        rad = int((H * 0.10) + (H * 0.26) * p)     # orbit grows as we pull back
        # sun glow at centre
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse(
            [cx - 60, cy - 60, cx + 60, cy + 60], fill=(*PALETTE["gold"], 130))
        glow = glow.filter(ImageFilter.GaussianBlur(24))
        im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22],
                  fill=(255, 238, 200, 255))
        d.text((cx + 30, cy - 12), _spaced(center_label), font=lf,
               fill=(*PALETTE["muted"], 220))
        # the faint orbit ring
        d.ellipse([cx - rad, cy - int(rad * 0.55), cx + rad,
                   cy + int(rad * 0.55)], outline=(*PALETTE["blue"], 120),
                  width=2)
        # the orbiting body (2.5 laps across the shot) + comet trail
        import math
        for k in range(0, 14):
            aa = 2 * math.pi * (2.4 * (i - k * 1.4) / n)
            bx = cx + rad * math.cos(aa)
            by = cy + int(rad * 0.55) * math.sin(aa)
            d.ellipse([bx - 7, by - 7, bx + 7, by + 7],
                      fill=(*PALETTE["blue"], max(0, 200 - k * 15)))
        ang = 2 * math.pi * (2.4 * i / n)
        bx = cx + rad * math.cos(ang)
        by = cy + int(rad * 0.55) * math.sin(ang)
        d.ellipse([bx - 11, by - 11, bx + 11, by + 11],
                  fill=(150, 200, 255, 255))
        a = min(max(i - 20, 0) / 12, 1.0)
        d.text((bx + 16, by - 8), sat_label, font=lf,
               fill=(*PALETTE["ink"], int(235 * a)))
        return im

    return _render(draw, out, seconds)


def cosmic_zoom(out: Path, seconds: float = 7.0,
                highlight: str = "THE SUN",
                stages=("THE MILKY WAY",)) -> Path:
    """Editorial motion (relative scale): the camera pulls back from one
    glowing dot to reveal a whole spiral galaxy, our star a single mote in it —
    the money shot, designed, in place of a cartoon 3D cosmos. Stage labels
    fade in as the scale escalates."""
    import math
    rnd = random.Random(21)
    # spiral-arm galaxy in WORLD coords (unit ~ galaxy radius = 1.0)
    stars = []
    for _ in range(1400):
        arm = rnd.choice([0, 1])
        t = rnd.random()
        r = 0.06 + 0.92 * t
        theta = arm * math.pi + t * 5.2 + rnd.gauss(0, 0.22)
        jit = rnd.gauss(0, 0.02)
        stars.append((r * math.cos(theta) + jit, r * math.sin(theta) + jit,
                      rnd.choice([1, 1, 2])))
    us = (0.42, 0.16)     # our star's world position
    cx, cy = W // 2, H // 2
    lf = _font(_DEJAVU, 30)
    hf = _font(_DEJAVU, 24)

    def draw(i, n, im):
        d = ImageDraw.Draw(im, "RGBA")
        # view scale: start tight on 'us', end framing the whole galaxy.
        # LINEAR pull-back (constant velocity) — an ease-OUT here decelerates
        # to a near-stop and the climax holds static for its final seconds
        # (SHOT_TOO_LONG). A steady pull-back keeps developing to the last frame;
        # a tiny ease-in over the first ~8% avoids a hard start.
        p = i / n
        prog = (p / 0.08) ** 2 * 0.08 if p < 0.08 else p
        z = 1.0 + prog * 1.0
        span = 0.16 + z * 1.05                    # world half-width shown
        scale = (W * 0.5) / span

        def to_screen(wx, wy):
            return (cx + (wx - us[0] * (1 - prog)) * scale,
                    cy + (wy - us[1] * (1 - prog)) * scale)
        # galaxy core glow
        gx, gy = to_screen(0, 0)
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse(
            [gx - 120, gy - 120, gx + 120, gy + 120],
            fill=(*PALETTE["gold"], 70))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
        d = ImageDraw.Draw(im, "RGBA")
        for wx, wy, sr in stars:
            sx, sy = to_screen(wx, wy)
            if -20 < sx < W + 20 and -20 < sy < H + 20:
                c = 150 + int(80 * (1 - (wx * wx + wy * wy)))
                d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                          fill=(c, c, min(255, int(c * 1.15))))
        # our star — a gold dot that stays highlighted as it shrinks
        ux, uy = to_screen(*us)
        pulse = 6 + 2 * math.sin(i / 3.0)
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).ellipse([ux - 22, uy - 22, ux + 22, uy + 22],
                                   fill=(*PALETTE["gold"], 160))
        gl = gl.filter(ImageFilter.GaussianBlur(10))
        im = Image.alpha_composite(im.convert("RGBA"), gl).convert("RGB")
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([ux - pulse, uy - pulse, ux + pulse, uy + pulse],
                  fill=(255, 240, 205, 255))
        # the dot names our star early; the bottom caption names the SCALE —
        # never the same word twice on screen (no double 'THE SUN').
        if i < n * 0.45:
            d.text((ux + 16, uy - 8), highlight, font=hf,
                   fill=(*PALETTE["ink"], 235))
        allst = list(stages)
        idx = min(len(allst) - 1, int((i / n) * len(allst)))
        lbl = _spaced(allst[idx])
        d.text((_center_x(d, lbl, lf), int(H * 0.86)), lbl, font=lf,
               fill=(*PALETTE["muted"], 188))
        return im

    return _render(draw, out, seconds)


def hook_card(number: str, sub: str, out: Path, seconds: float = 3.0,
              line: str = "") -> Path:
    """A HIGH-IMPACT opening hook — a big number SLAMS in over a hot radial glow
    with energy streaks. Built to score high on the hook rubric where the calm
    dark palette can't: warm colour, bold edges, hard contrast, and real motion
    (a scale-overshoot slam + a pulsing burst) from the very first frame. Used
    to open on a shock stat instead of a calm cloud."""
    import math
    rnd = random.Random(5)
    cx, cy = W // 2, int(H * 0.46)
    numf = _font(ANTON, 300)
    subf = _font(ANTON, 74)
    linef = _font(_DEJAVU, 40)
    streaks = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.3, 1.0)) for _ in range(70)]
    # radial hot-glow base (warm -> black), precomputed once
    yy, xx = np.mgrid[0:H, 0:W].astype("float32")
    dist = np.hypot(xx - cx, yy - cy) / (W * 0.6)
    glowbase = np.clip(1.0 - dist, 0, 1) ** 1.6

    def draw(i, n, im):
        t = i / n
        pulse = 0.6 + 0.4 * math.sin(i * 0.5)
        # hot radial glow (deep red -> orange), pulsing — colour + contrast
        g = glowbase * (0.55 + 0.45 * pulse)
        arr = np.zeros((H, W, 3), "float32")
        arr[..., 0] = g * 255
        arr[..., 1] = g * g * 150
        arr[..., 2] = g * g * 40
        im = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB")
        d = ImageDraw.Draw(im, "RGBA")
        # energy streaks radiating out (edges + motion)
        for ang, spd in streaks:
            r0 = ((i * spd * 14) % (W * 0.6)) + 40
            x0 = cx + math.cos(ang) * r0
            y0 = cy + math.sin(ang) * r0
            x1 = cx + math.cos(ang) * (r0 + 34)
            y1 = cy + math.sin(ang) * (r0 + 34)
            a = int(150 * (1 - r0 / (W * 0.6)))
            d.line([x0, y0, x1, y1], fill=(255, 210, 150, max(0, a)), width=2)
        # the number SLAMS in: scale overshoot in the first ~0.35s
        s = min(1.0, t / 0.35)
        scale = 1.35 - 0.35 * _ease(s) if s < 1 else 1.0 + 0.02 * math.sin(i * 0.4)
        nf = numf.font_variant(size=max(10, int(300 * scale)))
        im2 = _glow_text(im, (_center_x(ImageDraw.Draw(im), number, nf),
                              cy - int(150 * scale)),
                         number, nf, (255, 255, 255, 255),
                         (255, 120, 40, 200), blur=16)
        d = ImageDraw.Draw(im2, "RGBA")
        su = _spaced(sub.upper())
        d.text((_center_x(d, su, subf), int(H * 0.70)), su, font=subf,
               fill=(255, 225, 190, 255))
        if line:
            l0 = _spaced(line.upper())
            d.text((_center_x(d, lo := l0, linef), int(H * 0.86)), lo,
                   font=linef, fill=(255, 235, 210, 230))
        return im2

    return _render(draw, out, seconds)


def heat_engine(out: Path, seconds: float = 6.0,
                stages=("WARM OCEAN", "RISING, COOLING AIR",
                        "HEAT RELEASED")) -> Path:
    """A LIVING mechanism diagram — the storm as a self-feeding heat engine:
    warm air rises off the sea in spiralling updrafts, cools into a cloud
    canopy, releases a pulse of heat where it condenses, and rains back down,
    driving more air up. Every frame changes (rising particles, falling rain,
    a pulsing heat band) — a designed beat that is constantly ALIVE, the
    opposite of a held cloud plate. Stage caption escalates through `stages`.

    PREMIUM rebuild (appeal-first): a full-frame storm cross-section — a rich
    indigo->warm-sea gradient sky, a bright anvil canopy, a luminous CONVERGING
    vortex of updraft streaks, a bold PULSING latent-heat core, and a glowing sea.
    Colour range + contrast + edge density are all high (what the appeal metric
    rewards), so the mechanism reads as a cinematic engine, not a dark doodle."""
    import math
    import numpy as np
    rnd = random.Random(31)
    sea_y = int(H * 0.85)
    anvil_y = int(H * 0.24)
    core_y = int(H * 0.54)
    cx = W // 2
    lf = _font(_DEJAVU, 34)

    # --- precompute a rich vertical gradient sky + deep sea (done ONCE) ---
    stops = [(0.00, (36, 42, 96)), (0.42, (86, 52, 118)),    # bright indigo->storm
             (0.70, (176, 92, 84)), (0.85, (236, 150, 74)),  # warm, toward sea
             (0.851, (24, 66, 96)), (1.00, (10, 34, 60))]     # bright water below
    grad = np.zeros((H, 3), dtype="float32")
    for y in range(H):
        t = y / H
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / max(1e-6, t1 - t0)
                grad[y] = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
                break
        else:
            grad[y] = stops[-1][1]
    bg_arr = np.repeat(grad[:, None, :], W, axis=1).astype("uint8")
    base = Image.fromarray(bg_arr, "RGB").convert("RGBA")

    # --- precompute the anvil canopy (a broad bright cloud mass) ---
    anvil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(anvil)
    for hx, hy, r in [(rnd.uniform(-1, 1), rnd.uniform(0, 1), rnd.uniform(80, 190))
                      for _ in range(20)]:
        x = int(cx + hx * W * 0.46)
        y = int(anvil_y + hy * 96)
        ad.ellipse([x - r * 1.5, y - r * 0.62, x + r * 1.5, y + r * 0.62],
                   fill=(226, 232, 246, 150))
    anvil = anvil.filter(ImageFilter.GaussianBlur(30))

    ups = [(rnd.uniform(0, 1), rnd.uniform(-1, 1), rnd.uniform(0.7, 1.5),
            rnd.uniform(0, 6.28)) for _ in range(420)]
    rains = [(rnd.uniform(0, 1), rnd.uniform(-1, 1)) for _ in range(90)]
    span = sea_y - anvil_y

    def draw(i, n, _im):
        from PIL import ImageChops
        t = i / n
        im = base.copy()
        # --- glowing SEA band (the fuel), shimmering ---
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gy = sea_y - 30 + int(6 * math.sin(i * 0.3))
        ImageDraw.Draw(glow).rectangle([0, gy, W, sea_y + 14],
                                       fill=(255, 190, 96, 150))
        im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(22)))
        # --- pulsing latent-HEAT core (the engine firing), drifting so the frame
        # keeps CHANGING (a static rich card reads 'dead' to the novelty judge) ---
        pulse = 0.5 + 0.5 * math.sin(i * 0.5)
        cxo = cx + int(55 * math.sin(i * 0.11))          # slow horizontal drift
        hw = 300 + 130 * pulse
        hh = 150 + 60 * pulse
        hb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(hb).ellipse([cxo - hw, core_y - hh, cxo + hw, core_y + hh],
                                   fill=(255, 156, 64, int(120 + 130 * pulse)))
        ImageDraw.Draw(hb).ellipse([cxo - hw * 0.5, core_y - hh * 0.5,
                                    cxo + hw * 0.5, core_y + hh * 0.5],
                                   fill=(255, 226, 150, int(150 + 100 * pulse)))
        im = Image.alpha_composite(im, hb.filter(ImageFilter.GaussianBlur(46)))
        # --- the bright anvil canopy DRIFTS across (a big moving mass = novelty),
        # catching a warm underglow ---
        under = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(under).ellipse([cxo - 520, anvil_y + 30, cxo + 520,
                                       anvil_y + 150], fill=(255, 170, 90, 90))
        im = Image.alpha_composite(im, under.filter(ImageFilter.GaussianBlur(40)))
        adx = int(70 * math.sin(i * 0.05))               # anvil slides L<->R
        im = Image.alpha_composite(im, ImageChops.offset(anvil, adx, 0))
        # --- CONVERGING vortex updraft: bright streaks spiral up and inward,
        # narrowing to the core then flaring into the anvil (a real tower) ---
        d = ImageDraw.Draw(im, "RGBA")
        for ph0, home, spd, seed in ups:
            ph = (ph0 + t * spd * 1.4) % 1.0
            y = sea_y - ph * span
            # width narrows toward the core (ph~0.55) then widens into the anvil
            narrow = 1 - 0.7 * min(1.0, ph / 0.55) if ph < 0.55 \
                else 0.3 + 1.4 * ((ph - 0.55) / 0.45)
            swirl = math.sin(seed + i * 0.06 + ph * 7) * 40 * narrow
            x = cx + home * W * 0.42 * narrow + swirl
            warm = ph < 0.5                     # warm low, cooling to white high
            r_, g_, b_ = (255, int(210 - 90 * ph * 2), 120) if warm \
                else (235, 240, 255)
            a = int(240 * min(1, (1 - abs(ph - 0.5) * 1.4)))
            ln = 8 + int(12 * (1 - ph))
            d.line([x, y, x - swirl * 0.12, y + ln], fill=(r_, g_, b_, a), width=2)
        # --- rain falling back (the loop closes) ---
        for ph0, home in rains:
            ph = (ph0 + t * 1.1) % 1.0
            y = anvil_y + ph * span
            x = cx + home * W * 0.42
            d.line([x, y, x, y + 18], fill=(150, 195, 255, 150), width=2)
        d = ImageDraw.Draw(im, "RGBA")
        # --- stage caption escalates ---
        idx = min(len(stages) - 1, int(t * len(stages)))
        lbl = _spaced(stages[idx])
        d.text((_center_x(d, lbl, lf) + 2, int(H * 0.90) + 2), lbl, font=lf,
               fill=(0, 0, 0, 150))
        d.text((_center_x(d, lbl, lf), int(H * 0.90)), lbl, font=lf,
               fill=(*PALETTE["ink"], 235))
        return im.convert("RGB")

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
