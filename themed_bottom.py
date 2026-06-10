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

THEMES = ("space", "rain", "ember", "ocean", "plinko", "coins",
          "quake", "volcano", "runner")

# Keyword → theme. Checked in order; first hit wins. Scanned against
# title + script + hashtags lowercased.
_THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("space", ("spacex", "rocket", "nasa", "starship", "satellite",
               "mars", "moon", "asteroid", "meteor", "astronaut",
               "orbit", "launch", "quantum", "telescope", "comet")),
    ("volcano", ("volcano", "erupt", "wildfire", "blaze", "lava",
                 "burn", "explosion", "ash")),
    ("quake", ("earthquake", "quake", "tsunami", "seismic",
               "aftershock", "richter", "magnitude", "sinkhole")),
    ("rain",  ("storm", "tornado", "hurricane", "rain", "flood",
               "lightning", "blizzard", "cyclone", "weather")),
    ("runner", ("escape", "escaped", "on the run", "chase", "loose",
                "kangaroo", "devil", "raccoon", "zoo", "wildlife",
                "bear", "koala", "leopard", "animal")),
    ("ocean", ("shark", "whale", "ocean", "sea ", "marine", "coral",
               "fish", "beach")),
    ("coins", ("stock", "ipo", "market", "billion", "economy", "tax",
               "fee", "salary", "fine", "tariff", "bank", "crypto",
               "price", "invest", "visa")),
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


def _glitch(frame: np.ndarray, rng: random.Random,
            severity: float) -> np.ndarray:
    """Datamosh-style break: horizontal band displacement + RGB channel
    split + noise blocks. severity 0..1 scales everything. Operates on
    a copy — callers keep their clean frame for the post-reset cut."""
    out = frame.copy()
    # Horizontal slice displacement.
    n_bands = int(4 + 14 * severity)
    for _ in range(n_bands):
        y0 = rng.randrange(0, H - 8)
        bh = rng.randrange(6, 70)
        shift = rng.randrange(-int(180 * severity) - 8,
                              int(180 * severity) + 8)
        out[y0:y0 + bh] = np.roll(out[y0:y0 + bh], shift, axis=1)
    # Chromatic split: red left, blue right.
    px = int(3 + 14 * severity)
    out[..., 0] = np.roll(out[..., 0], -px, axis=1)
    out[..., 2] = np.roll(out[..., 2], px, axis=1)
    # Noise blocks.
    for _ in range(int(2 + 8 * severity)):
        y0 = rng.randrange(0, H - 40)
        x0 = rng.randrange(0, W - 120)
        bh, bw = rng.randrange(8, 36), rng.randrange(60, 320)
        out[y0:y0 + bh, x0:x0 + bw] = rng.randrange(0, 255)
    return out


class _Renderer:
    """Pipes raw RGB frames into ffmpeg. Subclass per theme and
    implement draw(t, frame_idx) -> np.ndarray (H, W, 3) uint8.

    Escalation cycle (the retention arc): themes that set
    ``CYCLE`` > 0 get a sawtooth intensity ramp. Within each cycle the
    scene starts calm, accelerates smoothly toward chaos, "breaks"
    in a ~0.5s glitch burst at the peak, then hard-cuts back to calm
    and starts over. Subclasses read ``self.intensity(t)`` (0..1
    eased ramp) and call ``self.maybe_glitch(frame, t)`` as the last
    step of draw(); both no-op when CYCLE == 0. ``cycle_index(t)``
    changes after every glitch so themes can regenerate their world
    (fresh constellation / skyline / terrain) on each reset."""

    CYCLE = 0.0           # seconds per escalation cycle; 0 = steady
    GLITCH_LEN = 0.55     # seconds of break at the peak

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        # Decaying additive trail layer shared by most themes.
        self.trail = np.zeros((H, W, 3), dtype=np.float32)

    # -- escalation helpers -------------------------------------------
    def _phase(self, t: float) -> float:
        return (t % self.CYCLE) if self.CYCLE else 0.0

    def cycle_index(self, t: float) -> int:
        return int(t // self.CYCLE) if self.CYCLE else 0

    def intensity(self, t: float) -> float:
        """0..1 eased ramp across the cycle's pre-glitch span. Quadratic
        on top of smoothstep so the last seconds feel like a runaway."""
        if not self.CYCLE:
            return 0.0
        ramp_span = self.CYCLE - self.GLITCH_LEN
        u = min(1.0, self._phase(t) / ramp_span)
        e = _ease(u)
        return e * e * 0.4 + e * 0.6  # gentle start, steep finish

    def in_glitch(self, t: float) -> bool:
        return bool(self.CYCLE) and self._phase(t) >= self.CYCLE - self.GLITCH_LEN

    def maybe_glitch(self, frame: np.ndarray, t: float) -> np.ndarray:
        if not self.in_glitch(t):
            return frame
        # Severity ramps WITHIN the glitch window too — it starts as a
        # stutter and tears itself apart right before the reset cut.
        g0 = self.CYCLE - self.GLITCH_LEN
        sev = (self._phase(t) - g0) / self.GLITCH_LEN
        return _glitch(frame, self.rng, 0.35 + 0.65 * sev)

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
    """A rocket arcs between glowing waypoint stars, leaving a teal
    trail. Each cycle it picks up speed — hops get faster, the trail
    runs hotter, the starfield streaks, screen-shake creeps in — until
    the whole scene tears itself apart in a glitch burst and resets to
    a fresh calm constellation."""

    CYCLE = 14.0
    HOP_BASE = 2.6        # seconds per hop at intensity 0
    HOP_MIN = 0.55        # seconds per hop at full intensity

    def __init__(self, seed=None):
        super().__init__(seed)
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 8 + 10 * (1 - g)     # faint navy at top
        self.bg[..., 1] = 8 + 14 * (1 - g)
        self.bg[..., 2] = 22 + 26 * (1 - g)
        self._cycle_seen = -1
        self._regen()

    def _regen(self):
        """Fresh world: new constellation, new starfield, rocket parked
        on waypoint 0. Called at construction and after every glitch."""
        rng = self.rng
        self.bg_stars = [(rng.uniform(0, W), rng.uniform(0, H),
                          rng.uniform(0.4, 1.6), rng.uniform(0, math.tau))
                         for _ in range(150)]
        self.nebulae = [(rng.uniform(0, W), rng.uniform(0, H),
                         rng.uniform(110, 240),
                         rng.choice([(40, 20, 70), (16, 40, 70),
                                     (60, 24, 50)]))
                        for _ in range(4)]
        self.waypoints = [(rng.uniform(120, W - 120),
                           rng.uniform(110, H - 110)) for _ in range(8)]
        self.visited = {0}
        self.current, self.next = 0, 1
        self.hop_u = 0.0            # progress 0..1 along current arc
        self._new_arc()
        self.pulses: list[tuple[float, float, float]] = []
        self.shooting: list[dict] = []
        self.trail[:] = 0

    def _new_arc(self):
        ax, ay = self.waypoints[self.current]
        bx, by = self.waypoints[self.next]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy) or 1.0
        k = self.rng.uniform(-0.4, 0.4)
        self.ctrl = (mx - dy / dist * dist * k, my + dx / dist * dist * k)

    def _bezier(self, u: float) -> tuple[float, float, float]:
        (ax, ay), (cx, cy) = self.waypoints[self.current], self.ctrl
        bx, by = self.waypoints[self.next]
        x = (1 - u) ** 2 * ax + 2 * (1 - u) * u * cx + u * u * bx
        y = (1 - u) ** 2 * ay + 2 * (1 - u) * u * cy + u * u * by
        dxu = 2 * (1 - u) * (cx - ax) + 2 * u * (bx - cx)
        dyu = 2 * (1 - u) * (cy - ay) + 2 * u * (by - cy)
        return x, y, math.atan2(dyu, dxu)

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        # Hard reset after every glitch window.
        if self.cycle_index(t) != self._cycle_seen:
            self._cycle_seen = self.cycle_index(t)
            if self._cycle_seen > 0:
                self._regen()
        k = self.intensity(t)
        dt = 1 / FPS

        # Hop speed scales with intensity. Advancing u by dt/duration
        # (instead of re-deriving from wall-clock) keeps motion smooth
        # while the duration itself shrinks frame to frame.
        hop_secs = self.HOP_BASE + (self.HOP_MIN - self.HOP_BASE) * k
        self.hop_u += dt / hop_secs
        if self.hop_u >= 1.0:
            x, y = self.waypoints[self.next]
            self.pulses.append((x, y, t))
            self.visited.add(self.next)
            if len(self.visited) == len(self.waypoints):
                self.visited = {self.next}
            self.current = self.next
            unvisited = [j for j in range(len(self.waypoints))
                         if j not in self.visited]
            self.next = rng.choice(unvisited or
                                   [j for j in range(len(self.waypoints))
                                    if j != self.current])
            self.hop_u = 0.0
            self._new_arc()
        x, y, heading = self._bezier(_ease(self.hop_u))

        # Occasional shooting star; more frequent as speed builds.
        if rng.random() < (0.004 + 0.05 * k):
            self.shooting.append({
                "x": rng.uniform(0, W), "y": rng.uniform(0, H * 0.5),
                "vx": rng.uniform(500, 900) * rng.choice([-1, 1]),
                "vy": rng.uniform(150, 360), "life": 1.0})

        # Trail: longer + hotter as intensity rises (teal -> white).
        self.trail *= 0.93 + 0.035 * k
        trail_col = (60 + 180 * k, 200 + 40 * k, 220 + 30 * k)
        _stamp_glow(self.trail, x, y, 26 + 10 * k, trail_col, 0.9 + 0.5 * k)

        frame = self.bg.copy() + self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Soft nebula blobs (depth, drawn dim under everything).
        for nx, ny, nr, ncol in self.nebulae:
            d.ellipse([nx - nr, ny - nr * 0.6, nx + nr, ny + nr * 0.6],
                      fill=(*ncol, 26))

        # Starfield: twinkle at rest, streak toward warp at speed.
        streak = 1 + 16 * k * k
        for sx, sy, sr, ph in self.bg_stars:
            a = int(120 + 90 * math.sin(t * 1.7 + ph))
            if streak > 2:
                dx_c, dy_c = sx - W / 2, sy - H / 2
                dist = math.hypot(dx_c, dy_c) or 1
                d.line([sx, sy, sx + dx_c / dist * streak,
                        sy + dy_c / dist * streak],
                       fill=(220, 225, 255, max(40, a)), width=2)
            else:
                d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                          fill=(220, 225, 255, max(40, a)))

        # Shooting stars.
        for s in self.shooting:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["life"] -= dt * 1.6
            if s["life"] > 0:
                a = int(230 * s["life"])
                d.line([s["x"], s["y"],
                        s["x"] - s["vx"] * 0.07, s["y"] - s["vy"] * 0.07],
                       fill=(255, 250, 230, a), width=3)
        self.shooting = [s for s in self.shooting if s["life"] > 0]

        # Waypoint stars: visited ones stay lit warm; target pulses.
        for j, (wx, wy) in enumerate(self.waypoints):
            is_target = (j == self.next)
            lit = j in self.visited
            base = 13 if is_target else (10 if lit else 8)
            r = base + (3.5 * math.sin(t * (3 + 4 * k) + j)
                        if is_target else 0)
            if is_target:
                col = (255, 235, 150, 255)
            elif lit:
                col = (255, 215, 170, 220)
            else:
                col = (200, 205, 235, 170)
            d.polygon([(wx, wy - r * 2), (wx + r * 0.5, wy - r * 0.5),
                       (wx + r * 2, wy), (wx + r * 0.5, wy + r * 0.5),
                       (wx, wy + r * 2), (wx - r * 0.5, wy + r * 0.5),
                       (wx - r * 2, wy), (wx - r * 0.5, wy - r * 0.5)],
                      fill=col)
            if lit and not is_target:
                d.ellipse([wx - base * 2.2, wy - base * 2.2,
                           wx + base * 2.2, wy + base * 2.2],
                          outline=(255, 220, 170, 60), width=2)

        # Arrival pulse rings; tighter + brighter at speed.
        ring_life = max(0.45, 0.9 - 0.4 * k)
        self.pulses = [(px, py, t0) for px, py, t0 in self.pulses
                       if t - t0 < ring_life]
        for px, py, t0 in self.pulses:
            pu = (t - t0) / ring_life
            pr = 14 + (90 + 60 * k) * _ease(pu)
            pa = int(220 * (1 - pu))
            d.ellipse([px - pr, py - pr, px + pr, py + pr],
                      outline=(140, 230, 255, pa), width=5)

        # The rocket; flame stretches with speed.
        def rot(px_, py_):
            c, s = math.cos(heading), math.sin(heading)
            return (x + px_ * c - py_ * s, y + px_ * s + py_ * c)

        L = 34
        flame = L * (0.8 + 0.45 * rng.random()) * (1 + 1.4 * k)
        d.polygon([rot(-L * 0.55, 0), rot(-L * 0.55 - flame, L * 0.16),
                   rot(-L * 0.55 - flame * 0.6, 0),
                   rot(-L * 0.55 - flame, -L * 0.16)],
                  fill=(255, 170 + int(60 * k), 60 + int(120 * k), 230))
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

        out = np.asarray(img, dtype=np.uint8)
        # Screen shake creeps in near the top of the ramp.
        if k > 0.6 and not self.in_glitch(t):
            amp = int(6 * (k - 0.6) / 0.4)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
                out = np.roll(out, rng.randint(-amp, amp), axis=1)
        return self.maybe_glitch(out, t)


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


# ---------- QUAKE: city + seismograph ramping to rupture ----------
# (Mindanao 7.8 / tsunami-class stories.)

class _Quake(_Renderer):
    """A night skyline under a live seismograph strip. The needle's
    amplitude grows, the buildings shake harder, cracks crawl up from
    the ground — until the big one hits, the frame ruptures in a
    glitch burst, and a fresh calm city fades in."""

    CYCLE = 14.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cycle_seen = -1
        self.seismo: list[float] = [0.0] * (W // 4)
        self._regen()

    def _regen(self):
        rng = self.rng
        self.buildings = []
        x = -20
        while x < W + 20:
            bw = rng.randint(70, 150)
            bh = rng.randint(180, 520)
            windows = [(rng.uniform(0.12, 0.88), rng.uniform(0.08, 0.9))
                       for _ in range(rng.randint(8, 26))]
            self.buildings.append({"x": x, "w": bw, "h": bh,
                                   "win": windows,
                                   "ph": rng.uniform(0, math.tau)})
            x += bw + rng.randint(6, 22)
        self.cracks: list[list[tuple[float, float]]] = []
        self.seismo = [0.0] * (W // 4)

    def _grow_crack(self):
        rng = self.rng
        x = rng.uniform(W * 0.05, W * 0.95)
        y = float(H)
        pts = [(x, y)]
        for _ in range(rng.randint(4, 9)):
            y -= rng.uniform(25, 75)
            x += rng.uniform(-55, 55)
            pts.append((x, y))
        self.cracks.append(pts)

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        if self.cycle_index(t) != self._cycle_seen:
            self._cycle_seen = self.cycle_index(t)
            if self._cycle_seen > 0:
                self._regen()
        k = self.intensity(t)

        # Seismograph feed: noise floor + intensity-scaled spikes.
        wob = (math.sin(t * 9) + math.sin(t * 23.7) * 0.6) * 6
        spike = rng.uniform(-1, 1) * (4 + 130 * k * k)
        self.seismo.append(wob + spike)
        self.seismo.pop(0)

        # Cracks spread once shaking gets real.
        if k > 0.45 and rng.random() < 0.06 * k:
            self._grow_crack()

        # Sky gradient dims + reddens as it builds.
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 14 + 26 * g + 30 * k * g
        frame[..., 1] = 16 + 26 * g - 8 * k * g
        frame[..., 2] = 30 + 40 * g - 14 * k * g

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Buildings: each gets its own shake phase; amplitude = k.
        shake_px = 26 * k * k
        for b in self.buildings:
            ox = math.sin(t * 17 + b["ph"]) * shake_px \
                + rng.uniform(-1, 1) * shake_px * 0.4
            oy = rng.uniform(-1, 1) * shake_px * 0.25
            x0, y0 = b["x"] + ox, H - b["h"] + oy
            d.rectangle([x0, y0, x0 + b["w"], H + 10],
                        fill=(26, 30, 44, 255),
                        outline=(50, 56, 80, 255), width=2)
            for wx, wy in b["win"]:
                lit = math.sin(t * 0.7 + wx * 50 + wy * 31) > -0.4
                # Lights flicker out as intensity rises.
                if lit and rng.random() > k * 0.5:
                    px_ = x0 + wx * b["w"]
                    py_ = y0 + wy * b["h"]
                    d.rectangle([px_, py_, px_ + 9, py_ + 13],
                                fill=(255, 222, 130, 230))

        # Ground cracks.
        for pts in self.cracks:
            d.line(pts, fill=(8, 8, 12, 255), width=5)
            d.line([(px_ + 3, py_ + 1) for px_, py_ in pts],
                   fill=(70, 40, 30, 160), width=2)

        # Seismograph strip on top, paper + needle trace.
        strip_h = 170
        d.rectangle([0, 0, W, strip_h], fill=(12, 16, 14, 235))
        for gy in range(0, strip_h, 24):
            d.line([0, gy, W, gy], fill=(30, 60, 40, 120), width=1)
        mid = strip_h // 2
        pts = [(i_ * 4, mid + v) for i_, v in enumerate(self.seismo)]
        hot = k > 0.55
        d.line(pts, fill=(255, 70, 60, 255) if hot
               else (90, 230, 120, 255), width=3)
        # Magnitude readout as a bar (no text dependencies).
        d.rectangle([W - 230, 18, W - 230 + 200 * k, 44],
                    fill=(255, 80, 60, 220) if hot
                    else (90, 230, 120, 200))
        d.rectangle([W - 232, 16, W - 28, 46],
                    outline=(200, 210, 200, 180), width=2)

        out = np.asarray(img, dtype=np.uint8)
        if shake_px > 2 and not self.in_glitch(t):
            out = np.roll(out, rng.randint(-int(shake_px / 2),
                                           int(shake_px / 2)), axis=0)
        return self.maybe_glitch(out, t)


# ---------- VOLCANO: smolder to full eruption ----------
# (Sakurajima grey-rain-class stories.)

class _Volcano(_Renderer):
    """A volcano smolders, then builds: lava bombs arc higher and
    faster, the crater glow swells, ash thickens — full eruption tears
    the frame, then it resets to a quiet smoking cone."""

    CYCLE = 14.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cycle_seen = -1
        self.peak = (W * 0.5, H * 0.42)
        self.bombs: list[dict] = []
        self.ash: list[dict] = []
        self._regen()

    def _regen(self):
        self.bombs.clear()
        self.ash.clear()
        self.trail[:] = 0
        rng = self.rng
        self.peak = (W * rng.uniform(0.4, 0.6), H * rng.uniform(0.38, 0.48))

    def _spawn_bomb(self, k: float):
        rng = self.rng
        px, py = self.peak
        return {"x": px + rng.uniform(-18, 18), "y": py,
                "vx": rng.uniform(-260, 260) * (0.5 + k),
                "vy": -rng.uniform(280, 620) * (0.5 + 0.9 * k),
                "r": rng.uniform(4, 11), "heat": 1.0}

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        if self.cycle_index(t) != self._cycle_seen:
            self._cycle_seen = self.cycle_index(t)
            if self._cycle_seen > 0:
                self._regen()
        k = self.intensity(t)
        dt = 1 / FPS
        px, py = self.peak

        # Spawn rates scale hard with intensity.
        for _ in range(int(1 + 14 * k * k)):
            if rng.random() < 0.5 + 0.5 * k:
                self.bombs.append(self._spawn_bomb(k))
        if rng.random() < 0.3 + 0.6 * k:
            self.ash.append({"x": px + rng.uniform(-26, 26), "y": py,
                             "vy": -rng.uniform(35, 90),
                             "vx": rng.uniform(-20, 50),
                             "r": rng.uniform(14, 44), "life": 1.0})

        self.trail *= 0.95
        # Crater glow breathes with intensity.
        _stamp_glow(self.trail, px, py + 8, 60 + 90 * k,
                    (255 * (0.4 + 0.6 * k), 90 * k + 40, 20), 0.5 + 0.9 * k)

        g_ = 900.0
        for b in self.bombs:
            b["vy"] += g_ * dt
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["heat"] -= dt * 0.55
            heat = max(0.0, b["heat"])
            _stamp_glow(self.trail, b["x"], b["y"], b["r"] * 2.0,
                        (255 * heat, 140 * heat * heat, 20 * heat ** 3),
                        0.8)
        self.bombs = [b for b in self.bombs
                      if b["y"] < H + 40 and b["heat"] > 0]

        # Sky: dusk purple, dimming + reddening with k.
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 30 + 26 * g + 50 * k * (1 - g)
        frame[..., 1] = 18 + 18 * g
        frame[..., 2] = 40 + 28 * g - 16 * k * g
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Ash puffs (behind the cone).
        for a in self.ash:
            a["y"] += a["vy"] * dt
            a["x"] += a["vx"] * dt
            a["r"] += 14 * dt
            a["life"] -= dt * 0.28
            if a["life"] > 0:
                shade = int(46 + 30 * a["life"])
                d.ellipse([a["x"] - a["r"], a["y"] - a["r"],
                           a["x"] + a["r"], a["y"] + a["r"]],
                          fill=(shade, shade - 4, shade - 6,
                                int(150 * a["life"])))
        self.ash = [a for a in self.ash if a["life"] > 0]

        # The cone.
        d.polygon([(px, py - 6), (px - W * 0.42, H + 10),
                   (px + W * 0.42, H + 10)], fill=(24, 18, 22, 255))
        d.polygon([(px - 26, py), (px + 26, py),
                   (px + 14, py + 26), (px - 14, py + 26)],
                  fill=(60, 24, 18, 255))
        # Lava streaks down the flanks once it's going.
        if k > 0.3:
            for sgn in (-1, 1):
                lx = px + sgn * 10
                pts = [(lx, py + 10)]
                for step in range(5):
                    lx += sgn * (18 + 26 * step * k)
                    pts.append((lx, py + 40 + step * (34 + 60 * k)))
                a_ = int(120 + 130 * k)
                d.line(pts, fill=(255, 120 + int(80 * k), 30, a_),
                       width=int(4 + 6 * k))

        out = np.asarray(img, dtype=np.uint8)
        if k > 0.55 and not self.in_glitch(t):
            amp = int(8 * (k - 0.55) / 0.45)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
        return self.maybe_glitch(out, t)


# ---------- RUNNER: critter on the loose ----------
# (Mary-the-Tasmanian-devil-class escape stories.)

class _Runner(_Renderer):
    """A little black critter bounds across rolling moonlit hills,
    hopping fences as the world scrolls faster and faster — full
    blur-sprint, glitch, reset. Endless-runner energy with no game
    over, because she always gets away."""

    CYCLE = 14.0
    BASE_SPEED = 260.0     # px/s ground scroll at k=0
    MAX_SPEED = 1500.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cycle_seen = -1
        self._regen()

    def _regen(self):
        rng = self.rng
        self.scroll = 0.0
        self.obstacles = [rng.uniform(600, 1400)]   # world-x of fences
        while self.obstacles[-1] < 30000:
            self.obstacles.append(self.obstacles[-1]
                                  + rng.uniform(420, 980))
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H * 0.5),
                       rng.uniform(0.5, 1.5)) for _ in range(60)]
        self.moon = (rng.uniform(W * 0.15, W * 0.85), rng.uniform(80, 200))
        self.ph = rng.uniform(0, math.tau)
        self.trail[:] = 0

    def _ground_y(self, world_x: float, layer: float = 1.0) -> float:
        """Rolling hills via layered sines; layer scales parallax."""
        x = world_x * layer
        return (H * 0.78
                + 36 * math.sin(x * 0.0021 + self.ph)
                + 18 * math.sin(x * 0.0057 + self.ph * 2))

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        if self.cycle_index(t) != self._cycle_seen:
            self._cycle_seen = self.cycle_index(t)
            if self._cycle_seen > 0:
                self._regen()
        k = self.intensity(t)
        dt = 1 / FPS
        speed = self.BASE_SPEED + (self.MAX_SPEED - self.BASE_SPEED) * k * k
        self.scroll += speed * dt

        critter_wx = self.scroll + W * 0.30   # world-x under the critter

        # Hop: bound cadence scales with speed; extra-high vault when a
        # fence is near so she always clears it.
        bound_freq = 2.2 + 5.5 * k
        bounce = abs(math.sin(t * bound_freq * math.pi))
        next_fence = next((o for o in self.obstacles
                           if o > critter_wx - 40), None)
        vault = 0.0
        if next_fence is not None:
            gap = next_fence - critter_wx
            if -60 < gap < 220:
                vault = _ease(1 - abs(gap - 80) / 140) * 90
        cy = self._ground_y(critter_wx) - 34 - bounce * 38 - vault

        # Night sky.
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 10 + 16 * g
        frame[..., 1] = 12 + 22 * g
        frame[..., 2] = 28 + 38 * g

        # Faint motion trail behind the critter.
        self.trail *= 0.88
        _stamp_glow(self.trail, W * 0.30, cy, 22 + 26 * k,
                    (120 + 100 * k, 140, 200), 0.5 + 0.8 * k)
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Moon + stars (fixed = infinite parallax).
        mx, my = self.moon
        d.ellipse([mx - 46, my - 46, mx + 46, my + 46],
                  fill=(235, 235, 215, 255))
        d.ellipse([mx - 30, my - 40, mx + 26, my + 16],
                  fill=(215, 215, 198, 255))
        for sx, sy, sr in self.stars:
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                      fill=(220, 225, 255, 160))

        # Far hill silhouette (slow parallax).
        far = [(x, self._ground_y(self.scroll * 0.35 + x * 1.0, 0.7) - 110)
               for x in range(0, W + 40, 40)]
        d.polygon([(0, H), *far, (W, H)], fill=(16, 22, 34, 255))

        # Near ground.
        near = [(x, self._ground_y(self.scroll + x))
                for x in range(0, W + 20, 20)]
        d.polygon([(0, H), *near, (W, H)], fill=(22, 32, 30, 255))
        # Grass tufts whip by.
        for x in range(0, W, 30):
            wx2 = self.scroll + x
            if int(wx2 / 30) % 3 == 0:
                gy = self._ground_y(wx2)
                lean = 6 + 18 * k
                d.line([x, gy, x - lean, gy - 14],
                       fill=(40, 70, 50, 255), width=2)

        # Fences (the obstacles she vaults).
        for o in self.obstacles:
            sx2 = o - self.scroll
            if -60 < sx2 < W + 60:
                gy = self._ground_y(o)
                d.rectangle([sx2 - 4, gy - 64, sx2 + 4, gy],
                            fill=(70, 52, 36, 255))
                d.rectangle([sx2 - 30, gy - 58, sx2 + 30, gy - 46],
                            fill=(70, 52, 36, 255))
                d.rectangle([sx2 - 30, gy - 32, sx2 + 30, gy - 20],
                            fill=(70, 52, 36, 255))

        # The critter: black blob body + ears + tail, squash/stretch
        # with the bounce; speed lines at high k.
        x0 = W * 0.30
        squash = 1 - 0.22 * bounce
        bw, bh = 56 * (2 - squash), 40 * squash
        d.ellipse([x0 - bw / 2, cy - bh / 2, x0 + bw / 2, cy + bh / 2],
                  fill=(18, 16, 16, 255))
        # head
        hx = x0 + bw * 0.42
        d.ellipse([hx - 18, cy - bh * 0.5 - 16, hx + 18, cy - bh * 0.5 + 16],
                  fill=(18, 16, 16, 255))
        # ears
        d.polygon([(hx - 12, cy - bh * 0.5 - 12), (hx - 4, cy - bh * 0.5 - 30),
                   (hx + 2, cy - bh * 0.5 - 10)], fill=(18, 16, 16, 255))
        d.polygon([(hx + 4, cy - bh * 0.5 - 12), (hx + 12, cy - bh * 0.5 - 28),
                   (hx + 16, cy - bh * 0.5 - 8)], fill=(18, 16, 16, 255))
        # eye
        d.ellipse([hx + 4, cy - bh * 0.5 - 4, hx + 10, cy - bh * 0.5 + 2],
                  fill=(255, 255, 255, 255))
        # tail
        d.line([x0 - bw / 2, cy, x0 - bw / 2 - 26,
                cy - 12 + 8 * math.sin(t * 12)],
               fill=(18, 16, 16, 255), width=8)
        # dust puffs on touchdown
        if bounce < 0.15:
            for _ in range(3):
                dx_ = rng.uniform(-24, 4)
                d.ellipse([x0 + dx_ - 5, cy + bh / 2 - 3,
                           x0 + dx_ + 5, cy + bh / 2 + 7],
                          fill=(90, 90, 80, 110))
        # speed lines
        if k > 0.45:
            for _ in range(int(10 * k)):
                ly = rng.uniform(H * 0.2, H * 0.9)
                ll = rng.uniform(40, 160) * k
                lx = rng.uniform(0, W)
                d.line([lx, ly, lx + ll, ly],
                       fill=(220, 225, 255, int(70 * k)), width=2)

        out = np.asarray(img, dtype=np.uint8)
        return self.maybe_glitch(out, t)


_THEME_CLASSES = {
    "space": _Space,
    "plinko": _Plinko,
    "coins": lambda seed=None: _Plinko(seed, gold=True),
    "rain": _Rain,
    "ember": _Ember,
    "ocean": _Ocean,
    "quake": _Quake,
    "volcano": _Volcano,
    "runner": _Runner,
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
