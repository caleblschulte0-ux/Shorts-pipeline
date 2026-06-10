"""Themed procedural bottom-half loops — the topic-aware replacement
for Minecraft gameplay.

Instead of random parkour under a SpaceX story, the bottom half gets a
generated "satisfying loop" themed to the story: a rocket arcing from
star to star, rain with lightning for storm coverage, rising embers
for a volcano, a plinko ball-drop as the universal default. Everything
is drawn procedurally (numpy + PIL piped raw into ffmpeg) so renders
are deterministic-ish, need zero API keys, and can't be flagged as
reused third-party content.

Design rules learned from the satisfying-video genre:
  * Smooth easing everywhere — nothing teleports, nothing jitters.
  * Trails: a decaying float buffer accumulates motion history, which
    reads as glow + afterimage and makes even simple dots feel lush.
  * One hero object (rocket / ball / bolt), many ambient objects
    (stars / pegs / streaks). The eye follows the hero, the ambience
    fills the frame.
  * Loop-friendly: motion is continuous for arbitrary durations.

Output contract (matches pick_gameplay_clip): W x HALF_H (1080x960),
30fps, h264, no audio.

Public API:
    pick_theme(title, script, hashtags) -> str
    render(theme, duration, out_path, seed=None) -> Path
    THEMES — the valid theme names
"""
from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 1080, 960
FPS = 30

THEMES = ("space", "rain", "ember", "ocean", "plinko", "coins")

# Keyword → theme. Checked in order; first hit wins. Scanned against
# title + script + hashtags lowercased.
_THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("space", ("spacex", "rocket", "nasa", "starship", "satellite",
               "mars", "moon", "asteroid", "meteor", "astronaut",
               "orbit", "launch", "quantum", "telescope", "comet")),
    ("ember", ("volcano", "erupt", "wildfire", "blaze", "lava",
               "burn", "explosion", "ash")),
    ("rain",  ("storm", "tornado", "hurricane", "rain", "flood",
               "tsunami", "earthquake", "quake", "lightning",
               "blizzard", "cyclone", "weather")),
    ("ocean", ("shark", "whale", "ocean", "sea ", "marine", "coral",
               "fish", "beach", "koala", "kangaroo", "zoo", "leopard",
               "animal", "wildlife", "devil", "raccoon", "bear")),
    ("coins", ("stock", "ipo", "market", "billion", "economy", "tax",
               "fee", "salary", "fine", "tariff", "bank", "crypto",
               "price", "invest")),
]


def pick_theme(title: str = "", script: str = "",
               hashtags: list[str] | None = None) -> str:
    """Keyword-route a story to a theme. Plinko is the universal
    fallback — it reads as 'satisfying' with no topical claim, so it
    never clashes with the story the way a wrong theme would."""
    blob = " ".join([title or "", script or "",
                     " ".join(hashtags or [])]).lower()
    for theme, words in _THEME_KEYWORDS:
        if any(w in blob for w in words):
            return theme
    return "plinko"


# ---------- shared helpers ----------

def _ease(t: float) -> float:
    """Smoothstep ease-in-out, 0..1 -> 0..1."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _stamp_glow(buf: np.ndarray, x: float, y: float, radius: float,
                color: tuple[float, float, float], strength: float = 1.0):
    """Additively stamp a soft radial blob into the float trail buffer.
    The decaying buffer turns successive stamps into a glowing trail."""
    x0, x1 = int(x - radius), int(x + radius) + 1
    y0, y1 = int(y - radius), int(y + radius) + 1
    if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H:
        return
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x1), min(H, y1)
    yy, xx = np.mgrid[y0c:y1c, x0c:x1c]
    d2 = (xx - x) ** 2 + (yy - y) ** 2
    falloff = np.exp(-d2 / (radius * radius * 0.35)) * strength
    for c in range(3):
        buf[y0c:y1c, x0c:x1c, c] += falloff * color[c]


class _Renderer:
    """Pipes raw RGB frames into ffmpeg. Subclass per theme and
    implement draw(t, frame_idx) -> np.ndarray (H, W, 3) uint8."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        # Decaying additive trail layer shared by most themes.
        self.trail = np.zeros((H, W, 3), dtype=np.float32)

    def draw(self, t: float, i: int) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def render(self, duration: float, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        n = int(duration * FPS) + 1
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p",
             str(out_path)],
            stdin=subprocess.PIPE,
        )
        try:
            for i in range(n):
                frame = self.draw(i / FPS, i)
                proc.stdin.write(frame.tobytes())
        finally:
            proc.stdin.close()
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg exited {proc.returncode} for {out_path}")
        return out_path


# ---------- SPACE: rocket pinging from star to star ----------

class _Space(_Renderer):
    """A little rocket arcs between glowing waypoint stars, leaving a
    teal trail; each arrival fires an expanding pulse ring and the next
    star lights up. Background starfield twinkles."""

    HOP_SECONDS = 2.8

    def __init__(self, seed=None):
        super().__init__(seed)
        rng = self.rng
        # Static dim background stars.
        self.bg_stars = [(rng.uniform(0, W), rng.uniform(0, H),
                          rng.uniform(0.4, 1.4), rng.uniform(0, math.tau))
                         for _ in range(110)]
        # Gradient background, precomputed.
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 8 + 10 * (1 - g)     # faint navy at top
        self.bg[..., 1] = 8 + 14 * (1 - g)
        self.bg[..., 2] = 22 + 26 * (1 - g)
        # Waypoint stars — spread across the frame with margins.
        self.waypoints = [(rng.uniform(120, W - 120), rng.uniform(110, H - 110))
                          for _ in range(7)]
        self.current = 0
        self.next = 1
        self.hop_started = 0.0
        # Control point for the current arc (perpendicular offset).
        self._new_arc()
        self.pulses: list[tuple[float, float, float]] = []  # (x, y, t0)

    def _new_arc(self):
        ax, ay = self.waypoints[self.current]
        bx, by = self.waypoints[self.next]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy) or 1.0
        # Perpendicular bulge, proportional to hop distance.
        k = self.rng.uniform(-0.45, 0.45)
        self.ctrl = (mx - dy / dist * dist * k, my + dx / dist * dist * k)

    def _bezier(self, u: float) -> tuple[float, float, float]:
        (ax, ay), (cx, cy) = self.waypoints[self.current], self.ctrl
        bx, by = self.waypoints[self.next]
        x = (1 - u) ** 2 * ax + 2 * (1 - u) * u * cx + u * u * bx
        y = (1 - u) ** 2 * ay + 2 * (1 - u) * u * cy + u * u * by
        # Heading from derivative.
        dxu = 2 * (1 - u) * (cx - ax) + 2 * u * (bx - cx)
        dyu = 2 * (1 - u) * (cy - ay) + 2 * u * (by - cy)
        return x, y, math.atan2(dyu, dxu)

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        # Advance hop state.
        u_raw = (t - self.hop_started) / self.HOP_SECONDS
        if u_raw >= 1.0:
            x, y = self.waypoints[self.next]
            self.pulses.append((x, y, t))
            self.current = self.next
            choices = [j for j in range(len(self.waypoints))
                       if j != self.current]
            self.next = rng.choice(choices)
            self.hop_started = t
            u_raw = 0.0
            self._new_arc()
        u = _ease(u_raw)
        x, y, heading = self._bezier(u)

        # Trail decay + new stamp.
        self.trail *= 0.93
        _stamp_glow(self.trail, x, y, 26, (60, 200, 220), 0.9)

        frame = self.bg.copy()
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Background stars twinkle.
        for sx, sy, sr, ph in self.bg_stars:
            a = int(120 + 90 * math.sin(t * 1.7 + ph))
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                      fill=(220, 225, 255, max(40, a)))

        # Waypoint stars: 4-point sparkles; target pulses brighter.
        for j, (wx, wy) in enumerate(self.waypoints):
            is_target = (j == self.next)
            base = 13 if is_target else 8
            r = base + (3.5 * math.sin(t * 3 + j) if is_target else 0)
            col = (255, 235, 150, 255) if is_target else (200, 205, 235, 170)
            d.polygon([(wx, wy - r * 2), (wx + r * 0.5, wy - r * 0.5),
                       (wx + r * 2, wy), (wx + r * 0.5, wy + r * 0.5),
                       (wx, wy + r * 2), (wx - r * 0.5, wy + r * 0.5),
                       (wx - r * 2, wy), (wx - r * 0.5, wy - r * 0.5)],
                      fill=col)

        # Arrival pulse rings (expand + fade over 0.9s).
        self.pulses = [(px, py, t0) for px, py, t0 in self.pulses
                       if t - t0 < 0.9]
        for px, py, t0 in self.pulses:
            pu = (t - t0) / 0.9
            pr = 14 + 90 * _ease(pu)
            pa = int(220 * (1 - pu))
            d.ellipse([px - pr, py - pr, px + pr, py + pr],
                      outline=(140, 230, 255, pa), width=5)

        # The rocket: body triangle + fins + window + flicker flame,
        # rotated to heading.
        def rot(px, py):
            c, s = math.cos(heading), math.sin(heading)
            return (x + px * c - py * s, y + px * s + py * c)

        L = 34  # rocket length scale
        flame = L * (0.8 + 0.45 * rng.random())
        d.polygon([rot(-L * 0.55, 0), rot(-L * 0.55 - flame, L * 0.16),
                   rot(-L * 0.55 - flame * 0.6, 0),
                   rot(-L * 0.55 - flame, -L * 0.16)],
                  fill=(255, 170, 60, 230))
        d.polygon([rot(-L * 0.5, L * 0.30), rot(-L * 0.78, L * 0.52),
                   rot(-L * 0.3, L * 0.30)], fill=(200, 60, 60, 255))
        d.polygon([rot(-L * 0.5, -L * 0.30), rot(-L * 0.78, -L * 0.52),
                   rot(-L * 0.3, -L * 0.30)], fill=(200, 60, 60, 255))
        d.polygon([rot(L * 0.62, 0), rot(L * 0.2, L * 0.26),
                   rot(-L * 0.55, L * 0.26), rot(-L * 0.55, -L * 0.26),
                   rot(L * 0.2, -L * 0.26)], fill=(235, 238, 245, 255))
        wx_, wy_ = rot(L * 0.18, 0)
        d.ellipse([wx_ - L * 0.13, wy_ - L * 0.13,
                   wx_ + L * 0.13, wy_ + L * 0.13],
                  fill=(80, 180, 230, 255))

        return np.asarray(img, dtype=np.uint8)


# ---------- PLINKO: the universal satisfying default ----------

class _Plinko(_Renderer):
    """Glowing balls cascade through a peg grid with soft bounces and
    color-cycling trails. Gold variant doubles as the 'coins' theme."""

    def __init__(self, seed=None, gold: bool = False):
        super().__init__(seed)
        self.gold = gold
        rng = self.rng
        # Offset peg grid.
        self.pegs: list[tuple[float, float]] = []
        rows, cols = 7, 9
        for r in range(rows):
            off = (W / cols / 2) if r % 2 else 0
            for c in range(cols + 1):
                px = c * W / cols + off
                py = 130 + r * (H - 260) / rows
                if 0 <= px <= W:
                    self.pegs.append((px, py))
        self.peg_r = 11
        self.balls = [self._spawn(stagger=True) for _ in range(13)]
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        if gold:
            self.bg[..., 0] = 24 - 10 * g
            self.bg[..., 1] = 18 - 8 * g
            self.bg[..., 2] = 8
        else:
            self.bg[..., 0] = 14 - 8 * g
            self.bg[..., 1] = 10 - 4 * g
            self.bg[..., 2] = 30 - 12 * g

    def _spawn(self, stagger=False):
        rng = self.rng
        return {
            "x": rng.uniform(W * 0.2, W * 0.8),
            "y": rng.uniform(-H * 0.9, -20) if stagger else rng.uniform(-90, -20),
            "vx": rng.uniform(-60, 60),
            "vy": rng.uniform(0, 120),
            "hue": rng.random(),
            "r": rng.uniform(13, 19),
        }

    @staticmethod
    def _hue_rgb(h: float) -> tuple[float, float, float]:
        i = int(h * 6) % 6
        f = h * 6 - int(h * 6)
        p, q, v = 60.0, 255 * (1 - f * 0.7), 255.0
        return [(v, q, p), (q, v, p), (p, v, q),
                (p, q, v), (q, p, v), (v, p, q)][i]

    def draw(self, t: float, i: int) -> np.ndarray:
        dt = 1 / FPS
        g = 1500.0
        for b in self.balls:
            b["vy"] += g * dt
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["hue"] = (b["hue"] + 0.15 * dt) % 1.0
            # Walls.
            if b["x"] < b["r"]:
                b["x"], b["vx"] = b["r"], abs(b["vx"]) * 0.8
            elif b["x"] > W - b["r"]:
                b["x"], b["vx"] = W - b["r"], -abs(b["vx"]) * 0.8
            # Pegs.
            for px, py in self.pegs:
                dx, dy = b["x"] - px, b["y"] - py
                dist = math.hypot(dx, dy)
                min_d = b["r"] + self.peg_r
                if 0 < dist < min_d:
                    nx, ny = dx / dist, dy / dist
                    dot = b["vx"] * nx + b["vy"] * ny
                    if dot < 0:
                        b["vx"] -= 2 * dot * nx
                        b["vy"] -= 2 * dot * ny
                        b["vx"] *= 0.72
                        b["vy"] *= 0.72
                        b["vx"] += self.rng.uniform(-25, 25)
                    b["x"] = px + nx * min_d
                    b["y"] = py + ny * min_d
            if b["y"] > H + 60:
                b.update(self._spawn())

        self.trail *= 0.90
        for b in self.balls:
            col = ((255, 200, 60) if self.gold
                   else self._hue_rgb(b["hue"]))
            _stamp_glow(self.trail, b["x"], b["y"], b["r"] * 1.7,
                        tuple(c * 0.55 for c in col), 0.8)

        frame = self.bg.copy() + self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")
        for px, py in self.pegs:
            d.ellipse([px - self.peg_r, py - self.peg_r,
                       px + self.peg_r, py + self.peg_r],
                      fill=(70, 75, 100, 255),
                      outline=(150, 160, 200, 180), width=2)
        for b in self.balls:
            col = ((255, 205, 70) if self.gold
                   else tuple(int(c) for c in self._hue_rgb(b["hue"])))
            r = b["r"]
            d.ellipse([b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r],
                      fill=(*col, 255))
            # Specular dot sells the "ball" read.
            d.ellipse([b["x"] - r * 0.45, b["y"] - r * 0.5,
                       b["x"] - r * 0.05, b["y"] - r * 0.1],
                      fill=(255, 255, 255, 160))
        return np.asarray(img, dtype=np.uint8)


# ---------- RAIN: storm streaks + lightning ----------

class _Rain(_Renderer):
    def __init__(self, seed=None):
        super().__init__(seed)
        rng = self.rng
        self.layers = []
        for depth, (speed, length, alpha, count) in enumerate(
                [(2000, 46, 200, 70), (1400, 30, 130, 90),
                 (900, 18, 80, 110)]):
            self.layers.append([{
                "x": rng.uniform(0, W), "y": rng.uniform(0, H),
                "speed": speed * rng.uniform(0.9, 1.1),
                "len": length, "alpha": alpha,
            } for _ in range(count)])
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 16 + 12 * g
        self.bg[..., 1] = 20 + 14 * g
        self.bg[..., 2] = 30 + 18 * g
        self.next_bolt = rng.uniform(3, 6)
        self.bolt_frames = 0
        self.bolt_path: list[tuple[float, float]] = []

    def _make_bolt(self):
        rng = self.rng
        x = rng.uniform(W * 0.15, W * 0.85)
        y = 0.0
        pts = [(x, y)]
        while y < H * rng.uniform(0.55, 0.9):
            y += rng.uniform(30, 80)
            x += rng.uniform(-70, 70)
            pts.append((x, y))
        return pts

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        dt = 1 / FPS
        frame = self.bg.copy()

        # Lightning scheduling.
        if t >= self.next_bolt and self.bolt_frames == 0:
            self.bolt_frames = 5
            self.bolt_path = self._make_bolt()
            self.next_bolt = t + rng.uniform(4.0, 8.0)

        if self.bolt_frames > 0:
            # Full-frame flash on first 2 frames, decaying after.
            flash = 70 if self.bolt_frames >= 4 else 22
            frame += flash
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Cloud band.
        for k in range(5):
            cx = (W * 0.25 * k + t * 18 + k * 60) % (W + 400) - 200
            d.ellipse([cx - 240, -90 + 14 * math.sin(t * 0.4 + k),
                       cx + 240, 95], fill=(26, 30, 42, 200))

        # Bolt itself.
        if self.bolt_frames > 0:
            a = int(255 * self.bolt_frames / 5)
            d.line(self.bolt_path, fill=(250, 250, 220, a), width=6)
            d.line(self.bolt_path, fill=(160, 190, 255, a // 2), width=12)
            self.bolt_frames -= 1

        # Rain streaks, slight diagonal.
        for layer in self.layers:
            for drop in layer:
                drop["y"] += drop["speed"] * dt
                drop["x"] -= drop["speed"] * 0.18 * dt
                if drop["y"] > H + 50:
                    drop["y"] = rng.uniform(-80, -10)
                    drop["x"] = rng.uniform(0, W * 1.15)
                d.line([drop["x"], drop["y"],
                        drop["x"] + drop["len"] * 0.18,
                        drop["y"] - drop["len"]],
                       fill=(170, 195, 230, drop["alpha"]), width=2)
        return np.asarray(img, dtype=np.uint8)


# ---------- EMBER: rising sparks for fire / volcano ----------

class _Ember(_Renderer):
    def __init__(self, seed=None):
        super().__init__(seed)
        rng = self.rng
        self.parts = [self._spawn(warm=True) for _ in range(90)]
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 10 + 40 * g          # red glow at the bottom
        self.bg[..., 1] = 6 + 12 * g
        self.bg[..., 2] = 8 + 4 * g

    def _spawn(self, warm=False):
        rng = self.rng
        return {
            "x": rng.uniform(0, W),
            "y": rng.uniform(H * 0.4, H) if warm else H + rng.uniform(5, 60),
            "v": rng.uniform(70, 220),
            "wob": rng.uniform(0.6, 2.2),
            "ph": rng.uniform(0, math.tau),
            "r": rng.uniform(2.5, 7),
            "life": rng.uniform(0, 1),
        }

    def draw(self, t: float, i: int) -> np.ndarray:
        dt = 1 / FPS
        self.trail *= 0.94
        for p in self.parts:
            p["y"] -= p["v"] * dt
            p["x"] += math.sin(t * p["wob"] + p["ph"]) * 40 * dt
            p["life"] += dt * 0.25
            if p["y"] < -20 or p["life"] > 1:
                p.update(self._spawn())
            heat = max(0.0, 1 - p["life"])
            col = (255 * heat, 150 * heat * heat, 30 * heat ** 3)
            _stamp_glow(self.trail, p["x"], p["y"], p["r"] * 2.4,
                        tuple(c * 0.5 for c in col), 0.9)
        frame = self.bg.copy() + self.trail
        return np.clip(frame, 0, 255).astype(np.uint8)


# ---------- OCEAN: bubbles + gliding fish + god rays ----------

class _Ocean(_Renderer):
    def __init__(self, seed=None):
        super().__init__(seed)
        rng = self.rng
        self.bubbles = [self._bubble(True) for _ in range(40)]
        self.fish = [{
            "y": rng.uniform(H * 0.18, H * 0.85),
            "speed": rng.uniform(90, 170) * rng.choice([-1, 1]),
            "x": rng.uniform(0, W),
            "size": rng.uniform(26, 52),
            "ph": rng.uniform(0, math.tau),
            "col": rng.choice([(255, 150, 60), (110, 200, 230),
                               (240, 220, 110)]),
        } for _ in range(4)]
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 8 + 6 * (1 - g)
        self.bg[..., 1] = 40 + 55 * (1 - g)
        self.bg[..., 2] = 70 + 90 * (1 - g)

    def _bubble(self, stagger=False):
        rng = self.rng
        return {
            "x": rng.uniform(0, W),
            "y": rng.uniform(0, H) if stagger else H + rng.uniform(5, 40),
            "v": rng.uniform(50, 140),
            "r": rng.uniform(3, 14),
            "ph": rng.uniform(0, math.tau),
        }

    def draw(self, t: float, i: int) -> np.ndarray:
        dt = 1 / FPS
        img = Image.fromarray(
            np.clip(self.bg, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # God rays — translucent slanted beams swaying slowly.
        for k in range(3):
            bx = W * (0.2 + 0.3 * k) + 60 * math.sin(t * 0.15 + k * 2)
            d.polygon([(bx - 40, 0), (bx + 60, 0),
                       (bx + 260, H), (bx + 60, H)],
                      fill=(180, 230, 250, 16))

        # Fish: ellipse body + wagging triangle tail + eye.
        for f in self.fish:
            f["x"] += f["speed"] * dt
            if f["speed"] > 0 and f["x"] > W + 80:
                f["x"] = -80
            elif f["speed"] < 0 and f["x"] < -80:
                f["x"] = W + 80
            fy = f["y"] + 12 * math.sin(t * 1.2 + f["ph"])
            s = f["size"]
            direction = 1 if f["speed"] > 0 else -1
            wag = math.sin(t * 7 + f["ph"]) * 0.45
            d.ellipse([f["x"] - s, fy - s * 0.45,
                       f["x"] + s, fy + s * 0.45], fill=(*f["col"], 235))
            tail_x = f["x"] - direction * s
            d.polygon([(tail_x, fy),
                       (tail_x - direction * s * 0.8, fy - s * (0.5 + wag)),
                       (tail_x - direction * s * 0.8, fy + s * (0.5 - wag))],
                      fill=(*f["col"], 235))
            ex = f["x"] + direction * s * 0.55
            d.ellipse([ex - 4, fy - 6, ex + 4, fy + 2], fill=(20, 20, 30, 255))

        # Bubbles with highlight arc.
        for b in self.bubbles:
            b["y"] -= b["v"] * dt
            b["x"] += math.sin(t * 1.5 + b["ph"]) * 25 * dt
            if b["y"] < -20:
                b.update(self._bubble())
            r = b["r"]
            d.ellipse([b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r],
                      outline=(225, 245, 255, 170), width=2)
            d.arc([b["x"] - r * 0.55, b["y"] - r * 0.55,
                   b["x"] + r * 0.25, b["y"] + r * 0.25],
                  200, 320, fill=(255, 255, 255, 220), width=2)
        return np.asarray(img, dtype=np.uint8)


_THEME_CLASSES = {
    "space": _Space,
    "plinko": _Plinko,
    "coins": lambda seed=None: _Plinko(seed, gold=True),
    "rain": _Rain,
    "ember": _Ember,
    "ocean": _Ocean,
}


def render(theme: str, duration: float, out_path: Path,
           seed: int | None = None) -> Path:
    """Render `duration` seconds of the named theme to `out_path`
    (1080x960@30, h264, silent). Unknown themes fall back to plinko."""
    cls = _THEME_CLASSES.get(theme, _Plinko)
    print(f"      [themed_bottom] generating {theme!r} "
          f"({duration:.1f}s procedural)")
    return cls(seed).render(duration, out_path)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("theme", choices=list(_THEME_CLASSES))
    ap.add_argument("--duration", type=float, default=8.0)
    ap.add_argument("--out", type=Path, default=Path("/tmp/themed.mp4"))
    a = ap.parse_args()
    print(render(a.theme, a.duration, a.out))
