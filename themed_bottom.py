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


class _Renderer:
    """Pipes raw RGB frames into ffmpeg. Subclass per theme and
    implement draw(t, frame_idx) -> np.ndarray (H, W, 3) uint8.

    Escalation cycle (the retention arc): themes that set ``CYCLE`` > 0
    get a sawtooth intensity ramp. The scene starts calm and
    accelerates until the "engine" visibly can't keep up — NOT a
    scheduled VFX glitch, but emergent overload symptoms that scale
    with load: dropped/held frames (lag stutter), then a hard hang on
    the final overwhelmed frame, then a clean reboot into a freshly
    regenerated world. Subclasses read ``self.intensity(t)`` and call
    ``self.overload(frame, t)`` as the last step of draw().
    ``cycle_index(t)`` changes after every reboot so themes regenerate
    their world (fresh constellation / skyline / terrain)."""

    CYCLE = 0.0           # seconds per escalation cycle; 0 = steady
    HANG_LEN = 0.45       # seconds the engine freezes before reboot

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        # Decaying additive trail layer shared by most themes.
        self.trail = np.zeros((H, W, 3), dtype=np.float32)
        self._last_frame: np.ndarray | None = None
        self._hang_frame: np.ndarray | None = None

    # -- escalation helpers -------------------------------------------
    def _phase(self, t: float) -> float:
        return (t % self.CYCLE) if self.CYCLE else 0.0

    def cycle_index(self, t: float) -> int:
        return int(t // self.CYCLE) if self.CYCLE else 0

    def intensity(self, t: float) -> float:
        """0..1 eased ramp across the cycle's pre-hang span. Quadratic
        on top of smoothstep so the last seconds feel like a runaway."""
        if not self.CYCLE:
            return 0.0
        ramp_span = self.CYCLE - self.HANG_LEN
        u = min(1.0, self._phase(t) / ramp_span)
        e = _ease(u)
        return e * e * 0.4 + e * 0.6  # gentle start, steep finish

    def in_hang(self, t: float) -> bool:
        return bool(self.CYCLE) and self._phase(t) >= self.CYCLE - self.HANG_LEN

    def overload(self, frame: np.ndarray, t: float) -> np.ndarray:
        """Simulation-overload symptoms, proportional to load.

        k < 0.82      — clean.
        0.82..1       — lag: rising chance a frame simply repeats (the
                        sim 'missed' a frame), with the occasional thin
                        scanline tear where the repeat composited
                        against the new frame mid-write.
        final HANG    — the engine locks: the last frame freezes and
                        dims slightly, like a process that stopped
                        responding, then the cycle reboot cuts in.
        """
        if not self.CYCLE:
            return frame
        if self.in_hang(t):
            if self._hang_frame is None:
                self._hang_frame = frame.copy()
            # Dim slowly while hung — "not responding".
            hung_for = self._phase(t) - (self.CYCLE - self.HANG_LEN)
            fade = 1.0 - 0.25 * (hung_for / self.HANG_LEN)
            return (self._hang_frame * fade).astype(np.uint8)
        self._hang_frame = None

        k = self.intensity(t)
        out = frame
        if k > 0.82 and self._last_frame is not None:
            # Frame-drop probability ramps with load.
            if self.rng.random() < (k - 0.82) * 3.5:
                out = self._last_frame
                # Mid-write tear: 1-2 thin bands of the NEW frame poke
                # through the held frame, slightly offset.
                if self.rng.random() < 0.6:
                    out = out.copy()
                    for _ in range(self.rng.randint(1, 2)):
                        y0 = self.rng.randrange(0, H - 24)
                        bh = self.rng.randrange(6, 24)
                        shift = self.rng.randrange(-30, 30)
                        out[y0:y0 + bh] = np.roll(frame[y0:y0 + bh],
                                                  shift, axis=1)
        self._last_frame = frame
        return out

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
        if k > 0.6 and not self.in_hang(t):
            amp = int(6 * (k - 0.6) / 0.4)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
                out = np.roll(out, rng.randint(-amp, amp), axis=1)
        return self.overload(out, t)


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
        if shake_px > 2 and not self.in_hang(t):
            out = np.roll(out, rng.randint(-int(shake_px / 2),
                                           int(shake_px / 2)), axis=0)
        return self.overload(out, t)

# ---------- VOLCANO: distant eruption raining fireballs ----------
# (Sakurajima grey-rain-class stories.)

class _Volcano(_Renderer):
    """A volcano erupts on the horizon while its fireballs rain down
    HERE, in the foreground — big molten balls that arc in from above,
    slam into the rocky ground, and BOUNCE, throwing sparks on every
    impact, cooling from white-hot to dead rock as they tumble off
    screen. Plinko physics wearing a disaster-movie skin. The eruption
    ramps until fireballs saturate the frame and the sim gives out."""

    CYCLE = 14.0
    GRAV = 1300.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cycle_seen = -1
        self._regen()

    def _regen(self):
        rng = self.rng
        self.trail[:] = 0
        self.balls: list[dict] = []
        self.sparks: list[dict] = []
        self.plume: list[dict] = []
        # Distant volcano position on the horizon.
        self.vx = W * rng.uniform(0.25, 0.75)
        self.horizon = H * rng.uniform(0.52, 0.60)
        self.vh = rng.uniform(150, 210)          # cone height
        # Rocky foreground terrain: bumpy ground line across the bottom.
        self.ground_phase = rng.uniform(0, math.tau)
        # One big foreground boulder the balls can ricochet off.
        self.boulder = (W * rng.uniform(0.25, 0.75),
                        rng.uniform(60, 95))      # (x, radius)

    def _ground_y(self, x: float) -> float:
        return (H * 0.86
                + 26 * math.sin(x * 0.006 + self.ground_phase)
                + 12 * math.sin(x * 0.017 + self.ground_phase * 2))

    def _ground_normal(self, x: float) -> tuple[float, float]:
        """Unit normal of the terrain at x (points up-ish)."""
        slope = (26 * 0.006 * math.cos(x * 0.006 + self.ground_phase)
                 + 12 * 0.017 * math.cos(x * 0.017 + self.ground_phase * 2))
        nx, ny = -slope, -1.0
        n = math.hypot(nx, ny)
        return nx / n, ny / n

    def _spawn_ball(self, k: float):
        """A fireball lobbed from the distant volcano toward the
        foreground. Spawn above the frame with inward drift so they
        feel like incoming artillery, not screen-savers."""
        rng = self.rng
        x = rng.uniform(-60, W + 60)
        r = rng.uniform(12, 26) * (1 + 0.9 * k * rng.random())
        return {"x": x, "y": -r - rng.uniform(0, 200),
                "vx": (self.vx - x) * rng.uniform(-0.25, 0.05)
                      + rng.uniform(-90, 90),
                "vy": rng.uniform(120, 320) * (1 + 0.8 * k),
                "r": r, "heat": 1.0, "bounces": 0,
                "spin": rng.uniform(-7, 7)}

    def _burst(self, x: float, y: float, power: float):
        rng = self.rng
        for _ in range(int(7 + 13 * power)):
            a = rng.uniform(math.pi, math.tau)      # upward half
            v = rng.uniform(120, 460) * power
            self.sparks.append({
                "x": x, "y": y,
                "vx": math.cos(a) * v, "vy": math.sin(a) * v,
                "life": rng.uniform(0.3, 0.8)})

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        if self.cycle_index(t) != self._cycle_seen:
            self._cycle_seen = self.cycle_index(t)
            if self._cycle_seen > 0:
                self._regen()
        k = self.intensity(t)
        dt = 1 / FPS

        # Spawn rate ramps from a lone fireball every couple seconds
        # to a constant barrage.
        if rng.random() < (0.018 + 0.5 * k * k):
            self.balls.append(self._spawn_ball(k))

        # Eruption plume puffs at the distant crater.
        if rng.random() < 0.25 + 0.55 * k:
            self.plume.append({
                "x": self.vx + rng.uniform(-12, 12),
                "y": self.horizon - self.vh,
                "vy": -rng.uniform(30, 80) * (1 + k),
                "vx": rng.uniform(-12, 26),
                "r": rng.uniform(8, 20), "life": 1.0})

        # ---- physics ----
        self.trail *= 0.92
        for b in self.balls:
            b["vy"] += self.GRAV * dt
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["heat"] = max(0.0, b["heat"] - dt * 0.10)

            # Boulder ricochet (circle-circle).
            bx, br = self.boulder
            by = self._ground_y(bx) - br * 0.55
            dx, dy = b["x"] - bx, b["y"] - by
            dist = math.hypot(dx, dy)
            min_d = b["r"] + br
            if 0 < dist < min_d:
                nx, ny = dx / dist, dy / dist
                dot = b["vx"] * nx + b["vy"] * ny
                if dot < 0:
                    b["vx"] -= 2 * dot * nx
                    b["vy"] -= 2 * dot * ny
                    b["vx"] *= 0.65
                    b["vy"] *= 0.65
                    b["bounces"] += 1
                    b["heat"] = max(0.0, b["heat"] - 0.18)
                    self._burst(b["x"], b["y"], min(1.0, b["r"] / 22))
                b["x"] = bx + nx * min_d
                b["y"] = by + ny * min_d

            # Terrain bounce: reflect about the local ground normal.
            gy = self._ground_y(b["x"])
            if b["y"] + b["r"] > gy:
                b["y"] = gy - b["r"]
                nx, ny = self._ground_normal(b["x"])
                dot = b["vx"] * nx + b["vy"] * ny
                if dot < 0:
                    b["vx"] -= 2 * dot * nx
                    b["vy"] -= 2 * dot * ny
                    rest = 0.62 - 0.07 * b["bounces"]
                    b["vx"] *= rest
                    b["vy"] *= rest
                    b["vx"] += rng.uniform(-30, 30)
                    b["bounces"] += 1
                    b["heat"] = max(0.0, b["heat"] - 0.22)
                    self._burst(b["x"], gy, min(1.0, b["r"] / 20)
                                * (1.2 - 0.25 * b["bounces"]))
            # Molten glow trail while still hot.
            if b["heat"] > 0.25:
                _stamp_glow(self.trail, b["x"], b["y"], b["r"] * 1.9,
                            (255 * b["heat"], 130 * b["heat"] ** 2, 18),
                            0.65)
        # Retire dead rocks that have rolled off / settled cold.
        self.balls = [b for b in self.balls
                      if b["x"] > -120 and b["x"] < W + 120
                      and not (b["heat"] <= 0.05 and abs(b["vy"]) < 30
                               and b["bounces"] >= 2)]

        for s in self.sparks:
            s["vy"] += self.GRAV * 0.6 * dt
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["life"] -= dt
        self.sparks = [s for s in self.sparks if s["life"] > 0]

        # ---- paint ----
        # Dusk sky; horizon glow warms with intensity.
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 26 + 46 * g + 60 * k * g
        frame[..., 1] = 20 + 26 * g + 8 * k * g
        frame[..., 2] = 44 + 30 * g - 10 * k * g
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Plume smoke (behind the cone, drifting up).
        for p in self.plume:
            p["y"] += p["vy"] * dt
            p["x"] += p["vx"] * dt
            p["r"] += 16 * dt
            p["life"] -= dt * 0.30
            if p["life"] > 0:
                sh = int(40 + 26 * p["life"])
                d.ellipse([p["x"] - p["r"], p["y"] - p["r"],
                           p["x"] + p["r"], p["y"] + p["r"]],
                          fill=(sh, sh - 5, sh - 6, int(160 * p["life"])))
        self.plume = [p for p in self.plume if p["life"] > 0]

        # Distant volcano silhouette + crater glow + tiny lava arcs.
        vx, hz, vh = self.vx, self.horizon, self.vh
        d.polygon([(vx, hz - vh), (vx - vh * 1.5, hz), (vx + vh * 1.5, hz)],
                  fill=(30, 22, 30, 255))
        glow_r = 16 + 26 * k + 5 * math.sin(t * 6)
        d.ellipse([vx - glow_r, hz - vh - glow_r * 0.6,
                   vx + glow_r, hz - vh + glow_r * 0.5],
                  fill=(255, int(120 + 80 * k), 30, int(140 + 90 * k)))
        # Distant ridge in front of the volcano.
        ridge = [(x, hz + 14 * math.sin(x * 0.01 + 2) + 8)
                 for x in range(0, W + 40, 40)]
        d.polygon([(0, H), *ridge, (W, H)], fill=(22, 17, 24, 255))

        # Foreground terrain.
        ground = [(x, self._ground_y(x)) for x in range(0, W + 20, 20)]
        d.polygon([(0, H), *ground, (W, H)], fill=(16, 12, 14, 255))
        d.line(ground, fill=(60, 40, 38, 255), width=3)

        # The boulder.
        bx, br = self.boulder
        by = self._ground_y(bx) - br * 0.55
        d.ellipse([bx - br, by - br * 0.8, bx + br, by + br * 0.8],
                  fill=(34, 28, 30, 255), outline=(64, 50, 48, 255),
                  width=3)

        # Fireballs: molten core + dark crust forming as they cool,
        # crackle highlight while hot.
        for b in self.balls:
            r, heat = b["r"], b["heat"]
            core = (int(255 * min(1, heat * 1.4)),
                    int(200 * heat), int(60 * heat ** 2))
            crust = (38, 30, 30)
            mix = tuple(int(crust[c] + (core[c] - crust[c]) * heat)
                        for c in range(3))
            d.ellipse([b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r],
                      fill=(*mix, 255))
            if heat > 0.3:
                # Hot cracks: short bright arcs rotating with spin.
                a0 = t * b["spin"]
                for j in range(3):
                    aa = a0 + j * 2.1
                    d.arc([b["x"] - r * 0.7, b["y"] - r * 0.7,
                           b["x"] + r * 0.7, b["y"] + r * 0.7],
                          math.degrees(aa), math.degrees(aa) + 50,
                          fill=(255, 230, 140, int(255 * heat)), width=3)

        # Impact sparks.
        for s in self.sparks:
            a = int(255 * min(1, s["life"] * 2.2))
            d.line([s["x"], s["y"],
                    s["x"] - s["vx"] * 0.03, s["y"] - s["vy"] * 0.03],
                   fill=(255, 210, 110, a), width=2)

        out = np.asarray(img, dtype=np.uint8)
        # Heavy impacts rattle the camera a touch at high intensity.
        if k > 0.55 and not self.in_hang(t):
            amp = int(7 * (k - 0.55) / 0.45)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
        return self.overload(out, t)


# ---------- RUNNER: critter on the loose ----------
# (Mary-the-Tasmanian-devil-class escape stories.)

class _Runner(_Renderer):
    """A little black critter bounds across rolling moonlit hills,
    vaulting fences as the world scrolls faster and faster until the
    sim can't keep up. She always gets away.

    v2 polish: bound cadence is driven by DISTANCE TRAVELLED (no
    foot-sliding at speed), squash-and-stretch follows the actual
    vertical velocity, legs and tail animate with the bound phase,
    Tasmanian-devil white chest blaze, dawn-gradient sky, drifting
    clouds, firefly motes, and a smoothed camera that breathes with
    the terrain instead of locking the critter to a fixed row."""

    CYCLE = 14.0
    BASE_SPEED = 240.0
    MAX_SPEED = 1450.0
    BOUND_LEN = 190.0     # px of ground per bound

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cycle_seen = -1
        self._cam_y = H * 0.5
        self._regen()

    def _regen(self):
        rng = self.rng
        self.scroll = 0.0
        self.obstacles = [rng.uniform(700, 1500)]
        while self.obstacles[-1] < 60000:
            self.obstacles.append(self.obstacles[-1]
                                  + rng.uniform(480, 1100))
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H * 0.45),
                       rng.uniform(0.5, 1.5)) for _ in range(70)]
        self.clouds = [{"x": rng.uniform(0, W), "y": rng.uniform(40, 240),
                        "w": rng.uniform(120, 260), "s": rng.uniform(6, 18)}
                       for _ in range(4)]
        self.moon = (rng.uniform(W * 0.15, W * 0.85),
                     rng.uniform(90, 200))
        self.fireflies = [{"x": rng.uniform(0, W),
                           "y": rng.uniform(H * 0.55, H * 0.8),
                           "ph": rng.uniform(0, math.tau)}
                          for _ in range(10)]
        self.ph = rng.uniform(0, math.tau)
        self.trail[:] = 0

    def _ground_y(self, world_x: float, layer: float = 1.0) -> float:
        x = world_x * layer
        return (H * 0.80
                + 34 * math.sin(x * 0.0019 + self.ph)
                + 16 * math.sin(x * 0.0053 + self.ph * 2))

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

        critter_wx = self.scroll + W * 0.30

        # Bound phase from distance, so strides lengthen naturally
        # with speed instead of feet sliding under a fixed sine.
        phase = (self.scroll / self.BOUND_LEN) % 1.0
        hop = math.sin(phase * math.pi)            # 0 at touchdown
        hop_v = math.cos(phase * math.pi)          # +rising / -falling

        # Fence vault: blend extra height in/out around the fence.
        next_fence = next((o for o in self.obstacles
                           if o > critter_wx - 60), None)
        vault = 0.0
        if next_fence is not None:
            gap = next_fence - critter_wx
            if -80 < gap < 240:
                vault = _ease(1 - abs(gap - 80) / 160) * 86
        gy_here = self._ground_y(critter_wx)
        cy = gy_here - 34 - hop * (34 + 18 * k) - vault

        # Smoothed camera: track terrain so hills feel like motion,
        # not noise.
        target_cam = gy_here - H * 0.62
        self._cam_y += (target_cam - self._cam_y) * min(1.0, 4.0 * dt)
        cam = self._cam_y

        # ---- sky ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 12 + 30 * g
        frame[..., 1] = 14 + 24 * g
        frame[..., 2] = 30 + 44 * g
        # Horizon warmth (pre-dawn band).
        band = np.exp(-((np.linspace(0, 1, H) - 0.62) ** 2) / 0.012)
        frame[..., 0] += band[:, None] * 26
        frame[..., 1] += band[:, None] * 12

        # Motion glow behind the critter.
        self.trail *= 0.88
        _stamp_glow(self.trail, W * 0.30 - 14, cy - cam, 20 + 26 * k,
                    (110 + 110 * k, 130, 190), 0.4 + 0.9 * k)
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Moon + halo, stars, clouds.
        mx, my = self.moon
        for hr, ha in ((66, 26), (56, 46)):
            d.ellipse([mx - hr, my - hr, mx + hr, my + hr],
                      fill=(235, 235, 215, ha))
        d.ellipse([mx - 44, my - 44, mx + 44, my + 44],
                  fill=(236, 236, 218, 255))
        d.ellipse([mx - 14, my - 20, mx + 2, my - 6],
                  fill=(214, 214, 198, 255))
        d.ellipse([mx + 8, my + 6, mx + 24, my + 20],
                  fill=(218, 218, 200, 255))
        for sx, sy, sr in self.stars:
            tw = 130 + 70 * math.sin(t * 2 + sx)
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                      fill=(220, 225, 255, int(max(60, tw))))
        for c in self.clouds:
            c["x"] = (c["x"] - c["s"] * dt) % (W + 300) - 150
            d.ellipse([c["x"], c["y"], c["x"] + c["w"], c["y"] + 36],
                      fill=(40, 46, 66, 120))

        # Parallax hills: far (slow) and mid.
        far = [(x, self._ground_y(self.scroll * 0.30 + x, 0.65)
                - 150 - cam * 0.4) for x in range(0, W + 40, 40)]
        d.polygon([(0, H), *far, (W, H)], fill=(17, 23, 36, 255))
        mid = [(x, self._ground_y(self.scroll * 0.60 + x, 0.85)
                - 70 - cam * 0.7) for x in range(0, W + 30, 30)]
        d.polygon([(0, H), *mid, (W, H)], fill=(19, 28, 32, 255))

        # Near ground with a lit top edge.
        near = [(x, self._ground_y(self.scroll + x) - cam)
                for x in range(0, W + 20, 20)]
        d.polygon([(0, H), *near, (W, H)], fill=(24, 34, 31, 255))
        d.line(near, fill=(52, 74, 58, 255), width=3)
        # Grass tufts lean harder with speed.
        for x in range(0, W, 26):
            wx2 = self.scroll + x
            if int(wx2 / 26) % 3 == 0:
                gy = self._ground_y(wx2) - cam
                lean = 5 + 22 * k
                d.line([x, gy, x - lean, gy - 13],
                       fill=(44, 78, 54, 255), width=2)

        # Fireflies.
        for f in self.fireflies:
            fy = f["y"] + 10 * math.sin(t * 1.3 + f["ph"]) - cam * 0.9
            fx = (f["x"] - speed * 0.08 * t) % W
            a = int(110 + 110 * math.sin(t * 3 + f["ph"]))
            d.ellipse([fx - 3, fy - 3, fx + 3, fy + 3],
                      fill=(220, 255, 140, max(40, a)))

        # Fences.
        for o in self.obstacles:
            sx2 = o - self.scroll
            if -70 < sx2 < W + 70:
                gy = self._ground_y(o) - cam
                wood = (76, 56, 38, 255)
                d.rectangle([sx2 - 5, gy - 66, sx2 + 5, gy], fill=wood)
                d.rectangle([sx2 - 34, gy - 60, sx2 + 34, gy - 47],
                            fill=wood)
                d.rectangle([sx2 - 34, gy - 34, sx2 + 34, gy - 21],
                            fill=wood)

        # ---- the critter ----
        x0 = W * 0.30
        cyv = cy - cam
        # Squash & stretch from vertical motion: stretch rising/falling,
        # squash on touchdown.
        airborne = hop > 0.08 or vault > 4
        stretch = 1.0 + 0.18 * abs(hop_v) * (1 if airborne else 0)
        squash = 1.0 / stretch
        bw, bh = 58 * squash * 1.15, 42 * stretch * 0.95
        body_col = (20, 17, 17, 255)
        # tail (whips with phase)
        tail_y = cyv - 6 + 10 * math.sin(phase * math.tau + 1.4)
        d.line([x0 - bw / 2, cyv, x0 - bw / 2 - 30, tail_y],
               fill=body_col, width=9)
        # haunch + body
        d.ellipse([x0 - bw / 2, cyv - bh / 2, x0 + bw / 2, cyv + bh / 2],
                  fill=body_col)
        d.ellipse([x0 - bw * 0.55, cyv - bh * 0.30,
                   x0 - bw * 0.05, cyv + bh * 0.55], fill=body_col)
        # white chest blaze (the Tasmanian devil signature)
        d.arc([x0 - bw * 0.05, cyv - bh * 0.25,
               x0 + bw * 0.5, cyv + bh * 0.55],
              40, 150, fill=(235, 235, 230, 255), width=5)
        # legs: two arcs scissoring with phase when grounded, tucked
        # when airborne
        if airborne:
            d.line([x0 - bw * 0.2, cyv + bh * 0.4,
                    x0 - bw * 0.05, cyv + bh * 0.62], fill=body_col, width=7)
            d.line([x0 + bw * 0.25, cyv + bh * 0.4,
                    x0 + bw * 0.4, cyv + bh * 0.58], fill=body_col, width=7)
        else:
            swing = math.sin(phase * math.tau * 2) * 14
            d.line([x0 - bw * 0.2, cyv + bh * 0.35,
                    x0 - bw * 0.2 - swing, cyv + bh * 0.75],
                   fill=body_col, width=7)
            d.line([x0 + bw * 0.25, cyv + bh * 0.35,
                    x0 + bw * 0.25 + swing, cyv + bh * 0.75],
                   fill=body_col, width=7)
        # head + snout + ears + eye
        hx = x0 + bw * 0.46
        hy = cyv - bh * 0.52
        d.ellipse([hx - 19, hy - 17, hx + 19, hy + 17], fill=body_col)
        d.ellipse([hx + 8, hy - 4, hx + 30, hy + 10], fill=body_col)
        d.ellipse([hx + 22, hy + 1, hx + 27, hy + 6],
                  fill=(60, 45, 45, 255))               # nose
        d.polygon([(hx - 13, hy - 13), (hx - 6, hy - 30), (hx, hy - 11)],
                  fill=body_col)
        d.polygon([(hx - 10, hy - 14), (hx - 6, hy - 25), (hx - 2, hy - 12)],
                  fill=(200, 120, 130, 255))            # inner ear
        d.polygon([(hx + 2, hy - 12), (hx + 9, hy - 27), (hx + 14, hy - 9)],
                  fill=body_col)
        d.ellipse([hx + 4, hy - 6, hx + 11, hy + 1],
                  fill=(255, 255, 255, 255))
        d.ellipse([hx + 7, hy - 4, hx + 10, hy - 1],
                  fill=(0, 0, 0, 255))

        # touchdown dust
        if not airborne and hop < 0.05:
            for _ in range(3):
                dx_ = rng.uniform(-30, 0)
                d.ellipse([x0 + dx_ - 5, cyv + bh / 2 - 2,
                           x0 + dx_ + 5, cyv + bh / 2 + 8],
                          fill=(96, 96, 84, 100))
        # speed lines once she's flying
        if k > 0.5:
            for _ in range(int(12 * k)):
                ly = rng.uniform(H * 0.25, H * 0.9)
                ll = rng.uniform(40, 170) * k
                lx = rng.uniform(0, W)
                d.line([lx, ly, lx + ll, ly],
                       fill=(220, 225, 255, int(60 * k)), width=2)

        out = np.asarray(img, dtype=np.uint8)
        return self.overload(out, t)

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
