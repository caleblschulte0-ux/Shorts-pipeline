#!/usr/bin/env python3
"""Procedural "satisfying" bottom-strip animations — fully original (no
stock, no copyright), rendered to match the pipeline's animated look so the
bottom strip feels like part of the same motion graphic.

Four styles:

  * ``bouncing`` — glowing balls bouncing/colliding inside a ring, with trails
  * ``ballpit``  — colorful balls rain down and settle with soft physics
  * ``flow``     — colored paths grow across a grid (the old Flow-game vibe)
  * ``plinko``   — balls fall through a peg field, bouncing to the bottom

Output is 1080x720 @30fps (the strip size the studio renderer samples from).

Usage:
    python -m data_learning.broll_gen --style bouncing --seconds 12 \
        --out output/sample_bouncing.mp4
    python -m data_learning.broll_gen --demo          # all four short samples
    python -m data_learning.broll_gen --build         # long satisfying.mp4
"""
from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PKG = Path(__file__).resolve().parent
BROLL_DIR = PKG / "broll"
OUT = BROLL_DIR / "satisfying.mp4"

W, H, FPS = 1080, 720, 30

# Brand palette (matches ambient.ORB_COLORS, a couple extra for variety).
PALETTE = [
    (79, 209, 197),    # teal
    (96, 165, 250),    # blue
    (165, 180, 252),   # periwinkle
    (245, 158, 11),    # amber
    (244, 114, 182),   # pink
    (52, 211, 153),    # green
]


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def _background() -> np.ndarray:
    """Dark diagonal gradient with a soft vignette, as a float HxWx3 array."""
    ys = np.linspace(0, 1, H)[:, None]
    xs = np.linspace(0, 1, W)[None, :]
    t = (ys * 0.7 + xs * 0.3)
    c0 = np.array([10, 14, 32], float)     # #0a0e20
    c1 = np.array([16, 43, 64], float)     # #102b40
    bg = c0[None, None, :] * (1 - t[..., None]) + c1[None, None, :] * t[..., None]
    # vignette
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vig = np.clip(1.0 - 0.35 * np.clip(d - 0.4, 0, None), 0.5, 1.0)
    return bg * vig[..., None]


def _writer(out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
         "-preset", "veryfast", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)


def _splat(buf: np.ndarray, x: float, y: float, r: float, color, *,
           glow: float = 0.6, additive: bool = False, alpha: float = 1.0) -> None:
    """Draw an anti-aliased glowing ball into a float HxWx3 buffer."""
    pad = r * 2.2
    x0, x1 = int(max(0, math.floor(x - pad))), int(min(W, math.ceil(x + pad)))
    y0, y1 = int(max(0, math.floor(y - pad))), int(min(H, math.ceil(y + pad)))
    if x0 >= x1 or y0 >= y1:
        return
    xs = np.arange(x0, x1)[None, :]
    ys = np.arange(y0, y1)[:, None]
    d = np.sqrt((xs - x) ** 2 + (ys - y) ** 2)
    core = np.clip(r - d + 0.6, 0, 1) * alpha
    col = np.array(color, float)
    reg = buf[y0:y1, x0:x1, :]
    if additive:
        reg += col[None, None, :] * core[..., None]
    else:
        reg[:] = reg * (1 - core[..., None]) + col[None, None, :] * core[..., None]
        # glossy highlight
        hl = np.clip(r * 0.5 - np.sqrt((xs - (x - r * 0.3)) ** 2 +
                                       (ys - (y - r * 0.3)) ** 2), 0, 1) * 0.5 * alpha
        reg[:] = np.clip(reg + 255 * hl[..., None], 0, 255)
    if glow:
        halo = np.exp(-(d / (r * 1.4)) ** 2) * glow * alpha
        reg[:] = np.clip(reg + col[None, None, :] * halo[..., None], 0, 255)


def _emit(proc, buf: np.ndarray) -> None:
    proc.stdin.write(np.clip(buf, 0, 255).astype(np.uint8).tobytes())


# --------------------------------------------------------------------------
# Style 1: bouncing balls + trails inside a ring
# --------------------------------------------------------------------------
def render_bouncing(out: Path, seconds: float, seed: int = 1) -> None:
    rng = random.Random(seed)
    bg = _background()
    cx, cy, R = W / 2, H / 2, H * 0.42
    n = 6
    balls = []
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(20, 34)
        sp = rng.uniform(6, 10)
        balls.append({
            "x": cx + math.cos(a) * R * 0.4, "y": cy + math.sin(a) * R * 0.4,
            "vx": math.cos(a + 1.7) * sp, "vy": math.sin(a + 1.7) * sp,
            "r": rr, "c": PALETTE[i % len(PALETTE)]})
    accum = np.zeros((H, W, 3), float)
    proc = _writer(out)
    frames = int(seconds * FPS)
    for _ in range(frames):
        accum *= 0.86                       # fade trails
        for b in balls:
            b["x"] += b["vx"]; b["y"] += b["vy"]
            dx, dy = b["x"] - cx, b["y"] - cy
            dist = math.hypot(dx, dy)
            if dist > R - b["r"]:            # bounce off ring (radial normal)
                nx, ny = dx / dist, dy / dist
                dot = b["vx"] * nx + b["vy"] * ny
                b["vx"] -= 2 * dot * nx; b["vy"] -= 2 * dot * ny
                over = dist - (R - b["r"])
                b["x"] -= nx * over; b["y"] -= ny * over
        # ball-ball elastic collisions (equal mass)
        for i in range(n):
            for j in range(i + 1, n):
                a, c = balls[i], balls[j]
                dx, dy = c["x"] - a["x"], c["y"] - a["y"]
                dist = math.hypot(dx, dy) or 1e-6
                if dist < a["r"] + c["r"]:
                    nx, ny = dx / dist, dy / dist
                    p = (a["vx"] - c["vx"]) * nx + (a["vy"] - c["vy"]) * ny
                    if p > 0:
                        a["vx"] -= p * nx; a["vy"] -= p * ny
                        c["vx"] += p * nx; c["vy"] += p * ny
                    over = a["r"] + c["r"] - dist
                    a["x"] -= nx * over / 2; a["y"] -= ny * over / 2
                    c["x"] += nx * over / 2; c["y"] += ny * over / 2
        frame = bg.copy()
        # ring outline
        _ring(frame, cx, cy, R, (60, 90, 120), 3)
        for b in balls:                     # trail (additive) + solid head
            _splat(accum, b["x"], b["y"], b["r"] * 0.8, b["c"],
                   glow=0.0, additive=True)
        frame = np.clip(frame + accum, 0, 255)
        for b in balls:
            _splat(frame, b["x"], b["y"], b["r"], b["c"], glow=0.7)
        _emit(proc, frame)
    proc.stdin.close(); proc.wait()


def _ring(buf, cx, cy, R, color, width):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.abs(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - R)
    m = np.clip(width - d, 0, 1)
    col = np.array(color, float)
    buf[:] = buf * (1 - m[..., None]) + col[None, None, :] * m[..., None]


# --------------------------------------------------------------------------
# Style 2: ball pit drop
# --------------------------------------------------------------------------
def render_ballpit(out: Path, seconds: float, seed: int = 2) -> None:
    rng = random.Random(seed)
    bg = _background()
    g = 0.55
    floor = H - 6
    balls: list[dict] = []
    max_active = 70

    def step(f: int) -> None:
        if f % 3 == 0:                      # spawn continuously, forever
            r = rng.uniform(16, 30)
            balls.append({"x": rng.uniform(r, W - r), "y": -r,
                          "vx": rng.uniform(-1.2, 1.2), "vy": rng.uniform(0, 2),
                          "r": r, "c": rng.choice(PALETTE), "rest": 0,
                          "a": 1.0, "fade": False})
        for b in balls:
            b["vy"] += g; b["x"] += b["vx"]; b["y"] += b["vy"]
            if b["x"] < b["r"]:
                b["x"] = b["r"]; b["vx"] = -b["vx"] * 0.5
            if b["x"] > W - b["r"]:
                b["x"] = W - b["r"]; b["vx"] = -b["vx"] * 0.5
            if b["y"] > floor - b["r"]:
                b["y"] = floor - b["r"]; b["vy"] = -b["vy"] * 0.32
                b["vx"] *= 0.8
            if abs(b["vx"]) + abs(b["vy"]) < 0.7:
                b["rest"] += 1
            else:
                b["rest"] = max(0, b["rest"] - 2)
        for i in range(len(balls)):
            for j in range(i + 1, len(balls)):
                a, c = balls[i], balls[j]
                dx, dy = c["x"] - a["x"], c["y"] - a["y"]
                dist = math.hypot(dx, dy) or 1e-6
                mind = a["r"] + c["r"]
                if dist < mind:
                    nx, ny = dx / dist, dy / dist
                    over = mind - dist
                    a["x"] -= nx * over / 2; a["y"] -= ny * over / 2
                    c["x"] += nx * over / 2; c["y"] += ny * over / 2
                    p = (a["vx"] - c["vx"]) * nx + (a["vy"] - c["vy"]) * ny
                    if p > 0:
                        a["vx"] -= p * nx * 0.6; a["vy"] -= p * ny * 0.6
                        c["vx"] += p * nx * 0.6; c["vy"] += p * ny * 0.6
        # recycle: once full, fade out the longest-settled ball so the pit
        # keeps churning and new balls always have room to drop.
        live = [b for b in balls if not b["fade"]]
        if len(live) > max_active:
            m = max(live, key=lambda b: b["rest"])
            if m["rest"] > 15:
                m["fade"] = True
        for b in balls:
            if b["fade"]:
                b["a"] -= 0.05
        balls[:] = [b for b in balls if b["a"] > 0.02 and b["y"] < H + 60]

    for f in range(170):                    # warmup: start already populated
        step(f)
    proc = _writer(out)
    for f in range(int(seconds * FPS)):
        step(f + 170)
        frame = bg.copy()
        for b in sorted(balls, key=lambda b: b["y"]):
            _splat(frame, b["x"], b["y"], b["r"], b["c"], glow=0.45, alpha=b["a"])
        _emit(proc, frame)
    proc.stdin.close(); proc.wait()


# --------------------------------------------------------------------------
# Style 3: flow-style path fill (drawn with PIL for clean thick lines)
# --------------------------------------------------------------------------
def _flow_paths(rng, gw, gh):
    """Fill ~85% of the grid with non-overlapping snake paths (cycling the
    palette) so the animation covers the whole frame."""
    occ = set()
    paths = []
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    ci = 0
    cells = gw * gh
    guard = 0
    while len(occ) < cells * 0.85 and guard < 400:
        guard += 1
        starts = [(x, y) for x in range(gw) for y in range(gh)
                  if (x, y) not in occ]
        if not starts:
            break
        cur = rng.choice(starts)
        path = [cur]; occ.add(cur)
        target = rng.randint(5, 16)
        while len(path) < target:
            rng.shuffle(dirs)
            moved = False
            for dx, dy in dirs:
                nxt = (cur[0] + dx, cur[1] + dy)
                if (0 <= nxt[0] < gw and 0 <= nxt[1] < gh
                        and nxt not in occ):
                    cur = nxt; path.append(cur); occ.add(cur); moved = True
                    break
            if not moved:
                break
        if len(path) >= 2:
            paths.append((PALETTE[ci % len(PALETTE)], path)); ci += 1
    return paths


def render_flow(out: Path, seconds: float, seed: int = 3) -> None:
    bg_arr = _background().astype(np.uint8)
    bg_img = Image.fromarray(bg_arr, "RGB")
    gw, gh = 13, 9
    cw, ch = W / gw, H / gh
    lw = int(min(cw, ch) * 0.5)

    def cell_xy(c):
        return (c[0] * cw + cw / 2, c[1] * ch + ch / 2)

    def draw(paths, prog, alpha):
        img = bg_img.copy()
        d = ImageDraw.Draw(img, "RGBA")
        for color, path in paths:
            pts = [cell_xy(c) for c in path]
            grown = prog * (len(pts) - 1)
            k = int(grown); frac = grown - k
            show = pts[:k + 1]
            if k < len(pts) - 1:
                x0, y0 = pts[k]; x1, y1 = pts[k + 1]
                show = show + [(x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac)]
            for ep in (pts[0], pts[-1]):
                d.ellipse([ep[0] - lw * 0.7, ep[1] - lw * 0.7,
                           ep[0] + lw * 0.7, ep[1] + lw * 0.7], fill=color + (80,))
                d.ellipse([ep[0] - lw * 0.5, ep[1] - lw * 0.5,
                           ep[0] + lw * 0.5, ep[1] + lw * 0.5], fill=color + (255,))
            if len(show) >= 2:
                d.line(show, fill=color + (255,), width=lw, joint="curve")
                for px, py in show:
                    d.ellipse([px - lw / 2, py - lw / 2,
                               px + lw / 2, py + lw / 2], fill=color + (255,))
        glow = img.filter(ImageFilter.GaussianBlur(7))
        img = Image.blend(img, glow, 0.35)
        if alpha < 1.0:                      # fade whole frame toward bg
            img = Image.blend(bg_img, img, alpha)
        return np.asarray(img.convert("RGB")).tobytes()

    proc = _writer(out)
    total = int(seconds * FPS)
    grow, hold, fade = int(4.5 * FPS), int(1.5 * FPS), int(0.8 * FPS)
    cycle = grow + hold + fade
    f = 0
    cseed = seed
    while f < total:
        paths = _flow_paths(random.Random(cseed), gw, gh); cseed += 1
        for cf in range(cycle):
            if f >= total:
                break
            if cf < grow:
                prog, alpha = (cf / grow), 1.0
            elif cf < grow + hold:
                prog, alpha = 1.0, 1.0
            else:
                prog, alpha = 1.0, 1.0 - (cf - grow - hold) / fade
            proc.stdin.write(draw(paths, prog, alpha))
            f += 1
    proc.stdin.close(); proc.wait()


# --------------------------------------------------------------------------
# Style 4: plinko / peg bounce
# --------------------------------------------------------------------------
def render_plinko(out: Path, seconds: float, seed: int = 4) -> None:
    rng = random.Random(seed)
    bg = _background()
    # Proper staggered (triangular) peg grid spanning the full width.
    cols, rows = 9, 10
    top, bottom = 130, H - 80
    sx = W / (cols + 1)
    pegs = []
    for row in range(rows):
        y = top + row * (bottom - top) / (rows - 1)
        off = sx / 2 if row % 2 else 0.0
        for c in range(cols):
            x = sx * (c + 1) + off - sx / 2
            if 10 < x < W - 10:
                pegs.append((x, y))
    pegr, ballr, g, rest = 9, 14, 0.45, 0.7
    balls: list[dict] = []
    accum = np.zeros((H, W, 3), float)

    def step(f: int) -> None:
        if f % 7 == 0 and len(balls) < 20:
            balls.append({"x": rng.uniform(W * 0.2, W * 0.8), "y": -10,
                          "vx": rng.uniform(-1.5, 1.5), "vy": 1.5,
                          "r": ballr, "c": rng.choice(PALETTE)})
        for b in balls:
            b["vy"] += g; b["x"] += b["vx"]; b["y"] += b["vy"]
            b["vx"] = max(-9, min(9, b["vx"]))
            for (px, py) in pegs:
                dx, dy = b["x"] - px, b["y"] - py
                dist = math.hypot(dx, dy)
                if dist < b["r"] + pegr:
                    nx, ny = (dx / dist, dy / dist) if dist else (
                        rng.choice((-1, 1)), -1)
                    dot = b["vx"] * nx + b["vy"] * ny
                    b["vx"] -= (1 + rest) * dot * nx
                    b["vy"] -= (1 + rest) * dot * ny
                    b["vx"] += rng.uniform(-0.9, 0.9)   # scatter
                    over = b["r"] + pegr - dist
                    b["x"] += nx * over; b["y"] += ny * over
            if b["x"] < b["r"]:
                b["x"] = b["r"]; b["vx"] = abs(b["vx"]) * 0.6
            if b["x"] > W - b["r"]:
                b["x"] = W - b["r"]; b["vx"] = -abs(b["vx"]) * 0.6
        balls[:] = [b for b in balls if b["y"] < H + 40]

    for f in range(120):                    # warmup so it starts mid-action
        step(f)
    proc = _writer(out)
    for f in range(int(seconds * FPS)):
        step(f + 120)
        accum *= 0.80
        frame = bg.copy()
        for (px, py) in pegs:
            _splat(frame, px, py, pegr, (90, 120, 150), glow=0.2)
        for b in balls:
            _splat(accum, b["x"], b["y"], b["r"] * 0.7, b["c"],
                   glow=0.0, additive=True)
        frame = np.clip(frame + accum, 0, 255)
        for b in balls:
            _splat(frame, b["x"], b["y"], b["r"], b["c"], glow=0.6)
        _emit(proc, frame)
    proc.stdin.close(); proc.wait()


STYLES = {
    "bouncing": render_bouncing,
    "ballpit": render_ballpit,
    "flow": render_flow,
    "plinko": render_plinko,
}


def _concat(parts: list[Path], out: Path) -> None:
    listf = out.parent / "_genlist.txt"
    listf.write_text("\n".join(f"file '{p.resolve()}'" for p in parts) + "\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listf), "-c", "copy", str(out)],
                   check=True)
    listf.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=list(STYLES))
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--demo", action="store_true",
                    help="render a short sample of every style to output/")
    ap.add_argument("--build", action="store_true",
                    help="render all styles long and concat into satisfying.mp4")
    args = ap.parse_args()

    if args.demo:
        outdir = PKG.parent / "output"
        for i, (name, fn) in enumerate(STYLES.items()):
            dst = outdir / f"sample_{name}.mp4"
            print(f"[gen] {name} -> {dst}")
            fn(dst, args.seconds, seed=i + 1)
        return 0
    if args.build:
        parts = []
        tmp = BROLL_DIR / "_gen"
        tmp.mkdir(parents=True, exist_ok=True)
        for i, (name, fn) in enumerate(STYLES.items()):
            p = tmp / f"{name}.mp4"
            print(f"[gen] {name} (45s)")
            fn(p, 45.0, seed=i + 1)
            parts.append(p)
        _concat(parts, OUT)
        print(f"[gen] built {OUT}")
        return 0
    if not args.style or not args.out:
        ap.error("give --style and --out, or use --demo / --build")
    STYLES[args.style](args.out, args.seconds, seed=args.seed)
    print(f"[gen] {args.style} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
