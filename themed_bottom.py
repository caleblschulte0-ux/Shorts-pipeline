"""Themed procedural bottom-half loops — the topic-aware replacement
for Minecraft gameplay.

Instead of random parkour under a SpaceX story, the bottom half gets a
generated "satisfying game" themed to the story. Everything is drawn
procedurally (numpy + PIL piped raw into ffmpeg): zero API keys, zero
reused-content flags, deterministic per seed.

=====================================================================
DESIGN CHARTER — the bar every theme must clear before it ships.
Extracted from operator feedback across five revision rounds; these
are requirements, not suggestions. When adding or editing a theme,
audit it against ALL of them:

 1. TOPIC-MATCHED. The scene is a visual metaphor for the story
    (rocket for a launch, fireball rain for a volcano, a sprinting
    critter for an animal escape). If no theme fits, route to plinko
    — a wrong theme is worse than a neutral one.

 2. ESCALATE OR DIE. Nothing idles at one speed. A compounding
    sim-clock multiplier (GROWTH) makes the scene start calm and
    continuously accelerate. Flat ambient loops are rejected.

 3. THE BREAK MUST BE REAL. Never schedule a glitch effect. The sim
    clock feeds the ACTUAL physics step (sim_dt = dt * scale); the
    breakdown must emerge from the math failing: explicit-Euler
    energy gain, tunneling, constraint non-convergence, temporal
    aliasing past the Nyquist limit of a cadence, vertex-budget
    collapse. The theme watches its own state (velocity bounds,
    per-frame motion vs. cycle length) and calls declare_fail() when
    the numbers leave reality.

 4. EMERGENT RESET. After failure: hang the last coherent frame like
    a not-responding process (handle_fail), then reboot into a
    REGENERATED world — new layout every cycle so the loop never
    visibly repeats. Cycle length varies per seed; that's a feature.

 5. PLINKO MENTALITY. Objects are physical and they INTERACT — with
    the terrain (surface-normal reflection), with set pieces
    (boulders, platforms), and with EACH OTHER (pairwise collision).
    Impacts have consequences: sparks, fragments, knockback. Nothing
    drifts through anything else while the sim is healthy.

 6. NOTHING FLOATS. Every element is planted in the composition:
    silhouettes overlap their background layers, bases extend below
    occluding ridges, set pieces cast contact shadows. If a viewer
    can ask "what is that standing on?", it's a bug.

 7. FOREGROUND IS THE SHOW. The story element can sit in the
    distance (the volcano on the horizon) but the ACTION plays out
    close to camera (its fireballs bouncing in front of you).

 8. VARIETY INSIDE THE LOOP. The repeated beat must not repeat
    exactly: vary obstacle types, ball sizes, spawn angles, layouts.
    One identical-looking event per second reads as a screensaver.

 9. FLAVOR PASS. Living details are mandatory, not optional polish:
    blinks, ear twitches, birds flushing, smoke wisps, paw scuffs,
    catchlights, constellation threads, confetti. One hero object
    carries the eye; ambient details make the world feel inhabited.

10. SMOOTH. Cadence is driven by distance travelled (no foot-slide),
    squash & stretch follows real velocity, easing on every
    transition, smoothed cameras. Jitter that isn't emergent
    overload is a defect.

11. LEAN INTO THE MEDIUM. This renderer is geometry + physics +
    glow: balls, particles, vehicles, silhouettes, parallax. If a
    concept needs representational drawing to be understood —
    people, hands, branded props, complex equipment — it is the
    WRONG CONCEPT for this engine; find the physics metaphor that
    says the same thing (a fight = two orbs clashing in an octagon,
    not a drawn glove hitting a drawn bag). Screenshot test: pause
    on any random frame and a stranger must name the scene in three
    words. Fail that, redesign the concept — don't polish it.

POLISH IS THE DEFAULT. Every rule above ships in the FIRST version
of a theme. "Make it polished" is never a follow-up request; an
unpolished theme is an unfinished theme.
=====================================================================

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
          "quake", "volcano", "runner", "stacker", "fight", "train")

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
    ("fight", ("ufc", "mma", "boxing", "boxer", "knockout",
               "octagon", "wrestl", "fight card", "title bout",
               "heavyweight")),
    ("train", ("train", "railway", "locomotive", "railroad", "kim jong",
               "north korea", "summit", "metro", "subway", "amtrak",
               "derail")),
    ("stacker", ("world record", "record-breaking", "tallest",
                 "largest", "biggest", "assembl", "built the",
                 "stacked", "lego", "potato head", "guinness")),
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

    # -- REAL overload: accelerating sim clock until physics breaks ----
    #
    # The honest version of the escalation arc. Instead of a scheduled
    # glitch, the simulation's time multiplier compounds every second
    # (GROWTH). Physics steps with dt * scale — an explicit-Euler
    # integrator stepped with an ever-growing dt genuinely destabilizes:
    # penetration depths blow up, restitution amplifies into energy
    # gain, per-frame motion crosses the Nyquist limit of the bound /
    # hop cadence and starts aliasing. Themes DETECT their own failure
    # (velocity blowup, motion > 1 cycle/frame) and call declare_fail();
    # the renderer hangs on the last coherent frame, then reboots.
    # Cycle length is therefore emergent, not scripted.

    GROWTH = 0.0          # sim clock multiplies by this factor each second

    def sim_scale(self, t: float) -> float:
        """Compounding time multiplier since the last reboot."""
        if not self.GROWTH:
            return 1.0
        return self.GROWTH ** (t - getattr(self, "reset_t", 0.0))

    def kk(self, ts: float) -> float:
        """Visual-intensity proxy (0..1) derived from the sim scale —
        drives flourishes like trail heat and star streaks so the look
        escalates in lockstep with the actual physics load."""
        return min(1.0, (ts - 1.0) / 6.0)

    def declare_fail(self, t: float):
        if getattr(self, "failed_at", None) is None:
            self.failed_at = t

    def handle_fail(self, frame: np.ndarray, t: float) -> np.ndarray | None:
        """While failed: hold + dim the breakdown frame (engine 'not
        responding'); after HANG_LEN, regen the world and restart the
        clock. Returns the held frame, or None when running normally."""
        failed_at = getattr(self, "failed_at", None)
        if failed_at is None:
            return None
        if t - failed_at < self.HANG_LEN:
            if self._hang_frame is None:
                self._hang_frame = frame.copy()
            fade = 1.0 - 0.25 * (t - failed_at) / self.HANG_LEN
            return (self._hang_frame * fade).astype(np.uint8)
        # Reboot.
        self._regen()
        self.reset_t = t
        self.failed_at = None
        self._hang_frame = None
        return None

    def lag(self, frame: np.ndarray, ts: float) -> np.ndarray:
        """Load-proportional frame drops: once the sim clock is several
        times real-time the 'machine' starts missing frames — a frame
        repeats, occasionally with a thin mid-write tear."""
        out = frame
        p = max(0.0, (ts - 3.5) / 9.0)
        if p > 0 and self._last_frame is not None \
                and self.rng.random() < p:
            out = self._last_frame
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
    """A rocket arcs between glowing waypoint stars, drawing a gold
    constellation thread behind it. A ringed planet drifts in the deep
    background.

    Escalation is REAL: the sim clock compounds (GROWTH), so hops
    genuinely get faster — not because the hop time shrinks, but
    because time itself runs hotter. When per-frame progress along an
    arc exceeds a full hop, the rocket's motion can no longer be
    resolved at 30fps (true temporal aliasing — it teleports), the
    sim declares failure, hangs, and reboots into a fresh sky."""

    GROWTH = 1.20         # sim clock compounds 20%/s -> ~13x at 14s
    HOP_SECONDS = 2.6

    STAR_TINTS = [(255, 255, 255), (190, 210, 255), (255, 240, 190),
                  (255, 200, 170)]

    def __init__(self, seed=None):
        super().__init__(seed)
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.bg = np.zeros((H, W, 3), dtype=np.float32)
        self.bg[..., 0] = 8 + 10 * (1 - g)
        self.bg[..., 1] = 8 + 14 * (1 - g)
        self.bg[..., 2] = 22 + 26 * (1 - g)
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.bg_stars = [(rng.uniform(0, W), rng.uniform(0, H),
                          rng.uniform(0.4, 1.7), rng.uniform(0, math.tau),
                          rng.choice(self.STAR_TINTS))
                         for _ in range(170)]
        self.nebulae = [(rng.uniform(0, W), rng.uniform(0, H),
                         rng.uniform(110, 240),
                         rng.choice([(40, 20, 70), (16, 40, 70),
                                     (60, 24, 50)]))
                        for _ in range(4)]
        px = rng.choice([rng.uniform(70, W * 0.25),
                         rng.uniform(W * 0.75, W - 70)])
        self.planet = {"x": px, "y": rng.uniform(90, H * 0.4),
                       "r": rng.uniform(34, 56),
                       "tilt": rng.uniform(-0.5, 0.5),
                       "col": rng.choice([(160, 120, 90), (110, 130, 160),
                                          (150, 110, 140)])}
        self.waypoints = []
        tries = 0
        while len(self.waypoints) < 14 and tries < 400:
            tries += 1
            cand = (rng.uniform(90, W - 90), rng.uniform(80, H - 80))
            if all(math.hypot(cand[0] - wx, cand[1] - wy) > 150
                   for wx, wy in self.waypoints):
                self.waypoints.append(cand)
        self.visit_order = [0]
        self.current, self.next = 0, 1
        self.hop_u = 0.0
        self._new_arc()
        self.pulses: list[tuple[float, float, float]] = []
        self.bursts: list[dict] = []
        self.shooting: list[dict] = []
        self.exhaust: list[dict] = []
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

    def _star4(self, d, x, y, r, col):
        d.polygon([(x, y - r * 2), (x + r * 0.5, y - r * 0.5),
                   (x + r * 2, y), (x + r * 0.5, y + r * 0.5),
                   (x, y + r * 2), (x - r * 0.5, y + r * 0.5),
                   (x - r * 2, y), (x - r * 0.5, y - r * 0.5)],
                  fill=col)

    def _arrive(self, t: float):
        rng = self.rng
        ax, ay = self.waypoints[self.next]
        self.pulses.append((ax, ay, t))
        for _ in range(10):
            a = rng.uniform(0, math.tau)
            v = rng.uniform(80, 320)
            self.bursts.append({"x": ax, "y": ay,
                                "vx": math.cos(a) * v,
                                "vy": math.sin(a) * v,
                                "life": rng.uniform(0.3, 0.6)})
        self.visit_order.append(self.next)
        if len(set(self.visit_order)) == len(self.waypoints):
            self.visit_order = [self.next]
        self.current = self.next
        unvisited = [j for j in range(len(self.waypoints))
                     if j not in set(self.visit_order)]
        self.next = rng.choice(unvisited or
                               [j for j in range(len(self.waypoints))
                                if j != self.current])
        self.hop_u = 0.0
        self._new_arc()

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        sim_dt = dt * ts

        # Advance along the arc with the ACCELERATED clock. When the
        # per-frame step exceeds a whole hop, the motion can't be
        # resolved anymore — that's the genuine failure condition.
        du = sim_dt / self.HOP_SECONDS
        if du >= 1.0:
            self.declare_fail(t)
        self.hop_u += du
        # At high ts the rocket may complete SEVERAL hops in one frame:
        # resolve them all — visible as multi-arrival chaos right
        # before it tips over.
        guard = 0
        while self.hop_u >= 1.0 and guard < 6:
            self._arrive(t)
            self.hop_u += 0.0   # _arrive zeroes hop_u; leftover dropped
            guard += 1
        x, y, heading = self._bezier(_ease(min(1.0, self.hop_u)))

        if rng.random() < 0.5 + 0.5 * k:
            self.exhaust.append({
                "x": x - math.cos(heading) * 22,
                "y": y - math.sin(heading) * 22,
                "r": rng.uniform(3, 7), "life": rng.uniform(0.35, 0.7)})
        if rng.random() < (0.004 + 0.05 * k):
            self.shooting.append({
                "x": rng.uniform(0, W), "y": rng.uniform(0, H * 0.5),
                "vx": rng.uniform(500, 900) * rng.choice([-1, 1]),
                "vy": rng.uniform(150, 360), "life": 1.0})

        self.trail *= 0.93 + 0.035 * k
        trail_col = (60 + 180 * k, 200 + 40 * k, 220 + 30 * k)
        _stamp_glow(self.trail, x, y, 26 + 10 * k, trail_col, 0.9 + 0.5 * k)

        frame = self.bg.copy() + self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        for nx, ny, nr, ncol in self.nebulae:
            d.ellipse([nx - nr, ny - nr * 0.6, nx + nr, ny + nr * 0.6],
                      fill=(*ncol, 26))

        p = self.planet
        ppx = p["x"] + 6 * math.sin(t * 0.05)
        ppy = p["y"] + 4 * math.sin(t * 0.04 + 2)
        pr = p["r"]
        ring_w, ring_h = pr * 2.4, pr * 0.7
        cs, sn = math.cos(p["tilt"]), math.sin(p["tilt"])
        ring_pts = []
        for a_ in range(0, 360, 12):
            ra = math.radians(a_)
            ex_, ey_ = math.cos(ra) * ring_w, math.sin(ra) * ring_h
            ring_pts.append((ppx + ex_ * cs - ey_ * sn,
                             ppy + ex_ * sn + ey_ * cs))
        back = [pt for a_, pt in zip(range(0, 360, 12), ring_pts)
                if a_ > 180]
        front = [pt for a_, pt in zip(range(0, 360, 12), ring_pts)
                 if a_ <= 180]
        if len(back) > 1:
            d.line(back, fill=(200, 190, 160, 110), width=3)
        d.ellipse([ppx - pr, ppy - pr, ppx + pr, ppy + pr],
                  fill=(*p["col"], 255))
        d.arc([ppx - pr, ppy - pr * 0.5, ppx + pr, ppy + pr * 0.2],
              200, 340, fill=tuple(int(c * 0.75) for c in p["col"])
              + (255,), width=4)
        d.ellipse([ppx - pr * 0.2, ppy - pr, ppx + pr * 1.6, ppy + pr],
                  fill=(8, 8, 18, 90))
        if len(front) > 1:
            d.line(front, fill=(220, 210, 180, 170), width=4)

        streak = 1 + 16 * k * k
        for sx, sy, sr, ph, tint in self.bg_stars:
            a = int(120 + 90 * math.sin(t * 1.7 + ph))
            if streak > 2:
                dx_c, dy_c = sx - W / 2, sy - H / 2
                dist = math.hypot(dx_c, dy_c) or 1
                d.line([sx, sy, sx + dx_c / dist * streak,
                        sy + dy_c / dist * streak],
                       fill=(*tint, max(40, a)), width=2)
            else:
                d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                          fill=(*tint, max(40, a)))
                if sr > 1.3:
                    fa = max(30, a // 2)
                    d.line([sx - sr * 3, sy, sx + sr * 3, sy],
                           fill=(*tint, fa), width=1)
                    d.line([sx, sy - sr * 3, sx, sy + sr * 3],
                           fill=(*tint, fa), width=1)

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

        if len(self.visit_order) > 1:
            n_seg = len(self.visit_order) - 1
            for si in range(n_seg):
                a_pt = self.waypoints[self.visit_order[si]]
                b_pt = self.waypoints[self.visit_order[si + 1]]
                age = n_seg - si
                alpha = max(40, 130 - age * 12)
                d.line([a_pt, b_pt], fill=(255, 220, 150, alpha), width=2)

        visited = set(self.visit_order)
        for j, (wx, wy) in enumerate(self.waypoints):
            is_target = (j == self.next)
            lit = j in visited
            base = 12 if is_target else (9 if lit else 6)
            r = base + (3.5 * math.sin(t * (3 + 4 * k) + j)
                        if is_target else 0)
            if is_target:
                col = (255, 235, 150, 255)
            elif lit:
                col = (255, 215, 170, 220)
            else:
                col = (185, 195, 230, 150)
            self._star4(d, wx, wy, r, col)
            if lit and not is_target:
                d.ellipse([wx - base * 2.0, wy - base * 2.0,
                           wx + base * 2.0, wy + base * 2.0],
                          outline=(255, 220, 170, 55), width=2)

        ring_life = max(0.45, 0.9 - 0.4 * k)
        self.pulses = [(px_, py_, t0) for px_, py_, t0 in self.pulses
                       if t - t0 < ring_life]
        for px_, py_, t0 in self.pulses:
            pu = (t - t0) / ring_life
            pr_ = 14 + (90 + 60 * k) * _ease(pu)
            pa = int(220 * (1 - pu))
            d.ellipse([px_ - pr_, py_ - pr_, px_ + pr_, py_ + pr_],
                      outline=(140, 230, 255, pa), width=5)
        for b in self.bursts:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["life"] -= dt
            if b["life"] > 0:
                a = int(255 * min(1, b["life"] * 2.5))
                d.line([b["x"], b["y"],
                        b["x"] - b["vx"] * 0.03, b["y"] - b["vy"] * 0.03],
                       fill=(255, 235, 170, a), width=2)
        self.bursts = [b for b in self.bursts if b["life"] > 0]

        for e in self.exhaust:
            e["r"] += 9 * dt
            e["life"] -= dt
            if e["life"] > 0:
                a = int(90 * min(1, e["life"] * 2))
                d.ellipse([e["x"] - e["r"], e["y"] - e["r"],
                           e["x"] + e["r"], e["y"] + e["r"]],
                          outline=(190, 200, 220, a), width=2)
        self.exhaust = [e for e in self.exhaust if e["life"] > 0]

        def rot(px_, py_):
            c, s = math.cos(heading), math.sin(heading)
            return (x + px_ * c - py_ * s, y + px_ * s + py_ * c)

        L = 34
        flame = L * (0.8 + 0.45 * rng.random()) * (1 + 1.4 * k)
        d.polygon([rot(-L * 0.55, 0), rot(-L * 0.55 - flame, L * 0.16),
                   rot(-L * 0.55 - flame * 0.6, 0),
                   rot(-L * 0.55 - flame, -L * 0.16)],
                  fill=(255, 170 + int(60 * k), 60 + int(120 * k), 230))
        d.polygon([rot(-L * 0.55, 0),
                   rot(-L * 0.55 - flame * 0.55, L * 0.08),
                   rot(-L * 0.55 - flame * 0.55, -L * 0.08)],
                  fill=(255, 245, 200, 240))
        d.polygon([rot(-L * 0.5, L * 0.30), rot(-L * 0.78, L * 0.52),
                   rot(-L * 0.3, L * 0.30)], fill=(200, 60, 60, 255))
        d.polygon([rot(-L * 0.5, -L * 0.30), rot(-L * 0.78, -L * 0.52),
                   rot(-L * 0.3, -L * 0.30)], fill=(200, 60, 60, 255))
        d.polygon([rot(L * 0.62, 0), rot(L * 0.2, L * 0.26),
                   rot(-L * 0.55, L * 0.26), rot(-L * 0.55, -L * 0.26),
                   rot(L * 0.2, -L * 0.26)], fill=(235, 238, 245, 255))
        d.line([rot(L * 0.5, -L * 0.1), rot(-L * 0.5, -L * 0.1)],
               fill=(205, 210, 222, 255), width=2)
        d.polygon([rot(L * 0.62, 0), rot(L * 0.34, L * 0.2),
                   rot(L * 0.34, -L * 0.2)], fill=(210, 80, 80, 255))
        wx_, wy_ = rot(L * 0.14, 0)
        d.ellipse([wx_ - L * 0.13, wy_ - L * 0.13,
                   wx_ + L * 0.13, wy_ + L * 0.13],
                  fill=(80, 180, 230, 255))
        d.ellipse([wx_ - L * 0.13, wy_ - L * 0.13,
                   wx_ + L * 0.13, wy_ + L * 0.13],
                  outline=(160, 170, 190, 255), width=2)

        out = np.asarray(img, dtype=np.uint8)
        if k > 0.6:
            amp = int(6 * (k - 0.6) / 0.4)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
                out = np.roll(out, rng.randint(-amp, amp), axis=1)
        return self.lag(out, ts)

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
        return self.overload(out, t)# ---------- VOLCANO: distant eruption raining fireballs ----------
# (Sakurajima grey-rain-class stories.)

class _Volcano(_Renderer):
    """A volcano erupts on the horizon while its fireballs rain into
    the foreground — bouncing off terrain, a boulder, and EACH OTHER,
    shattering into fragments, cooling from white-hot to rock.

    Escalation is REAL: the sim clock compounds, so the explicit-Euler
    integrator steps with an ever-growing dt. That genuinely
    destabilizes — bounces overshoot, restitution turns into energy
    gain, balls start rocketing off at impossible speeds. The sim
    watches its own velocities and declares failure when the math
    blows past plausibility; hang; reboot."""

    GROWTH = 1.18
    GRAV = 1300.0
    MAX_BALLS = 70
    BLOWUP_V = 6500.0     # any ball faster than this = integrator lost

    def __init__(self, seed=None):
        super().__init__(seed)
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.trail[:] = 0
        self.balls: list[dict] = []
        self.sparks: list[dict] = []
        self.plume: list[dict] = []
        self.wisps: list[dict] = []
        self.bolts: list[dict] = []
        self.vx = W * rng.uniform(0.25, 0.75)
        self.horizon = H * rng.uniform(0.52, 0.60)
        self.vh = rng.uniform(150, 210)
        self.ground_phase = rng.uniform(0, math.tau)
        self.boulder = (W * rng.uniform(0.25, 0.75),
                        rng.uniform(60, 95))
        self.trees = []
        for _ in range(rng.randint(2, 3)):
            tx = rng.uniform(40, W - 40)
            if abs(tx - self.boulder[0]) > 150:
                self.trees.append((tx, rng.uniform(60, 110),
                                   rng.uniform(-0.25, 0.25)))
        self.flank = []
        for sgn in (-1, 1):
            pts = [(0.0, 0.0)]
            run_x = 0.0
            for step in range(6):
                run_x += sgn * rng.uniform(12, 30)
                pts.append((run_x, (step + 1) * rng.uniform(18, 26)))
            self.flank.append(pts)

    def _ground_y(self, x: float) -> float:
        return (H * 0.86
                + 26 * math.sin(x * 0.006 + self.ground_phase)
                + 12 * math.sin(x * 0.017 + self.ground_phase * 2))

    def _ground_normal(self, x: float) -> tuple[float, float]:
        slope = (26 * 0.006 * math.cos(x * 0.006 + self.ground_phase)
                 + 12 * 0.017 * math.cos(x * 0.017 + self.ground_phase * 2))
        nx, ny = -slope, -1.0
        n = math.hypot(nx, ny)
        return nx / n, ny / n

    def _spawn_ball(self, k: float, *, x=None, y=None, r=None,
                    vx=None, vy=None, heat=1.0):
        rng = self.rng
        if r is None:
            r = rng.uniform(12, 26) * (1 + 0.9 * k * rng.random())
        if x is None:
            x = rng.uniform(-60, W + 60)
        return {"x": x,
                "y": y if y is not None else -r - rng.uniform(0, 200),
                "vx": vx if vx is not None else
                      (self.vx - x) * rng.uniform(-0.25, 0.05)
                      + rng.uniform(-90, 90),
                "vy": vy if vy is not None else
                      rng.uniform(120, 320) * (1 + 0.8 * k),
                "r": r, "heat": heat, "bounces": 0,
                "spin": rng.uniform(-7, 7)}

    def _burst(self, x: float, y: float, power: float):
        rng = self.rng
        for _ in range(int(7 + 13 * power)):
            a = rng.uniform(math.pi, math.tau)
            v = rng.uniform(120, 460) * power
            self.sparks.append({
                "x": x, "y": y,
                "vx": math.cos(a) * v, "vy": math.sin(a) * v,
                "life": rng.uniform(0.3, 0.8)})

    def _ball_collisions(self):
        n = len(self.balls)
        for i_ in range(n):
            a = self.balls[i_]
            for j_ in range(i_ + 1, n):
                b = self.balls[j_]
                dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                dist = math.hypot(dx, dy)
                min_d = a["r"] + b["r"]
                if not (0 < dist < min_d):
                    continue
                nx, ny = dx / dist, dy / dist
                overlap = (min_d - dist) / 2
                a["x"] -= nx * overlap
                a["y"] -= ny * overlap
                b["x"] += nx * overlap
                b["y"] += ny * overlap
                van = a["vx"] * nx + a["vy"] * ny
                vbn = b["vx"] * nx + b["vy"] * ny
                rel = van - vbn
                if rel <= 0:
                    continue
                e = 0.78
                a["vx"] -= (1 + e) / 2 * rel * nx
                a["vy"] -= (1 + e) / 2 * rel * ny
                b["vx"] += (1 + e) / 2 * rel * nx
                b["vy"] += (1 + e) / 2 * rel * ny
                if rel > 220 and (a["heat"] > 0.3 or b["heat"] > 0.3):
                    mx_, my_ = (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2
                    self._burst(mx_, my_, min(1.0, rel / 700))

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        sim_dt = dt * ts          # the genuinely growing timestep

        if (rng.random() < (0.018 + 0.5 * k * k) * min(ts, 4)
                and len(self.balls) < self.MAX_BALLS):
            self.balls.append(self._spawn_ball(k))

        if rng.random() < 0.25 + 0.55 * k:
            self.plume.append({
                "x": self.vx + rng.uniform(-12, 12),
                "y": self.horizon - self.vh,
                "vy": -rng.uniform(30, 80) * (1 + k),
                "vx": rng.uniform(-12, 26),
                "r": rng.uniform(8, 20), "life": 1.0})
        if k > 0.55 and rng.random() < 0.05 * k:
            bx0 = self.vx + rng.uniform(-50, 50)
            by0 = self.horizon - self.vh - rng.uniform(30, 110)
            pts = [(bx0, by0)]
            for _ in range(rng.randint(2, 4)):
                pts.append((pts[-1][0] + rng.uniform(-36, 36),
                            pts[-1][1] + rng.uniform(14, 42)))
            self.bolts.append({"pts": pts, "life": 0.12})

        # ---- physics on the accelerated clock ----
        self.trail *= 0.92
        for b in self.balls:
            b["vy"] += self.GRAV * sim_dt
            b["x"] += b["vx"] * sim_dt
            b["y"] += b["vy"] * sim_dt
            b["heat"] = max(0.0, b["heat"] - sim_dt * 0.10)

            # The integrator watching itself: when explicit Euler at
            # this dt has pumped a ball past any plausible speed, the
            # sim is gone.
            if (abs(b["vx"]) > self.BLOWUP_V
                    or abs(b["vy"]) > self.BLOWUP_V):
                self.declare_fail(t)

            if b["heat"] > 0.45 and rng.random() < 0.12:
                self.wisps.append({"x": b["x"], "y": b["y"] - b["r"],
                                   "vy": -rng.uniform(20, 50),
                                   "vx": rng.uniform(-15, 15),
                                   "r": b["r"] * 0.4, "life": 0.8})

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

            gy = self._ground_y(b["x"])
            if b["y"] + b["r"] > gy:
                impact_speed = b["vy"]
                # NOTE: penetration correction + restitution applied to
                # a velocity integrated at sim_dt — this is exactly the
                # combination that goes unstable as ts grows. On a hot
                # clock the ball is already deep underground, the
                # push-out is violent, and the reflected velocity has a
                # full overgrown gravity step baked in: energy GAIN.
                pen = b["y"] + b["r"] - gy
                b["y"] = gy - b["r"]
                nx, ny = self._ground_normal(b["x"])
                dot = b["vx"] * nx + b["vy"] * ny
                if dot < 0:
                    b["vx"] -= 2 * dot * nx
                    b["vy"] -= 2 * dot * ny
                    rest = 0.62 - 0.07 * b["bounces"]
                    # Deep tunneling converts to extra bounce speed —
                    # physically wrong, numerically honest.
                    rest *= 1.0 + min(2.0, pen / 200.0)
                    b["vx"] *= rest
                    b["vy"] *= rest
                    b["vx"] += rng.uniform(-30, 30)
                    b["bounces"] += 1
                    b["heat"] = max(0.0, b["heat"] - 0.22)
                    self._burst(b["x"], gy, min(1.0, b["r"] / 20)
                                * (1.2 - 0.25 * b["bounces"]))
                    if (b["bounces"] == 1 and b["r"] > 17
                            and impact_speed > 500
                            and len(self.balls) < self.MAX_BALLS - 3):
                        for _ in range(rng.randint(2, 3)):
                            self.balls.append(self._spawn_ball(
                                k, x=b["x"] + rng.uniform(-8, 8),
                                y=b["y"] - b["r"] * 0.5,
                                r=b["r"] * rng.uniform(0.35, 0.5),
                                vx=b["vx"] * 0.4 + rng.uniform(-260, 260),
                                vy=-abs(impact_speed)
                                   * rng.uniform(0.25, 0.45),
                                heat=min(1.0, b["heat"] + 0.25)))
                        b["r"] *= 0.82
            if b["heat"] > 0.25:
                _stamp_glow(self.trail, b["x"], b["y"], b["r"] * 1.9,
                            (255 * b["heat"], 130 * b["heat"] ** 2, 18),
                            0.65)

        self._ball_collisions()

        self.balls = [b for b in self.balls
                      if -400 < b["x"] < W + 400 and b["y"] > -2000
                      and not (b["heat"] <= 0.05 and abs(b["vy"]) < 30
                               and b["bounces"] >= 2)]

        for s in self.sparks:
            s["vy"] += self.GRAV * 0.6 * dt
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["life"] -= dt
        self.sparks = [s for s in self.sparks if s["life"] > 0]

        # ---- paint ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 26 + 46 * g + 60 * k * g
        frame[..., 1] = 20 + 26 * g + 8 * k * g
        frame[..., 2] = 44 + 30 * g - 10 * k * g
        frame *= (1.0 - 0.12 * k)
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

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

        for bolt in self.bolts:
            bolt["life"] -= dt
            if bolt["life"] > 0:
                a = int(255 * bolt["life"] / 0.12)
                d.line(bolt["pts"], fill=(230, 220, 255, a), width=3)
        self.bolts = [b_ for b_ in self.bolts if b_["life"] > 0]

        # Distant volcano — base extends WELL below the ridge line so
        # the cone is planted in the landscape instead of floating on
        # the horizon seam.
        vx, hz, vh = self.vx, self.horizon, self.vh
        base_y = hz + 60
        d.polygon([(vx, hz - vh),
                   (vx - vh * 1.8, base_y), (vx + vh * 1.8, base_y)],
                  fill=(30, 22, 30, 255))
        for pts in self.flank:
            world = [(vx + dx_, hz - vh + dy_) for dx_, dy_ in pts]
            a = int(90 + 150 * k)
            d.line(world, fill=(255, 110 + int(70 * k), 24, a),
                   width=2 + int(2 * k))
        glow_r = 16 + 26 * k + 5 * math.sin(t * 6)
        d.ellipse([vx - glow_r, hz - vh - glow_r * 0.6,
                   vx + glow_r, hz - vh + glow_r * 0.5],
                  fill=(255, int(120 + 80 * k), 30, int(140 + 90 * k)))
        # Ridge sits IN FRONT of the cone's flanks (drawn after), so
        # the base seam is always covered.
        ridge = [(x, hz + 14 * math.sin(x * 0.01 + 2) + 8)
                 for x in range(0, W + 40, 40)]
        d.polygon([(0, H), *ridge, (W, H)], fill=(22, 17, 24, 255))

        for tx, th, lean in self.trees:
            base_ty = self._ground_y(tx)
            top = (tx + lean * th, base_ty - th)
            d.line([tx, base_ty, *top], fill=(14, 10, 12, 255), width=7)
            for fb, fl, fa in ((0.45, 0.45, -0.9), (0.65, 0.35, 0.8),
                               (0.82, 0.28, -0.6)):
                bx_ = tx + lean * th * fb
                by_ = base_ty - th * fb
                d.line([bx_, by_, bx_ + math.cos(fa) * th * fl,
                        by_ - abs(math.sin(fa)) * th * fl],
                       fill=(14, 10, 12, 255), width=4)

        ground = [(x, self._ground_y(x)) for x in range(0, W + 20, 20)]
        d.polygon([(0, H), *ground, (W, H)], fill=(16, 12, 14, 255))
        d.line(ground, fill=(70 + int(60 * k), 42, 34, 255), width=3)

        bx, br = self.boulder
        by = self._ground_y(bx) - br * 0.55
        d.ellipse([bx - br, by - br * 0.8, bx + br, by + br * 0.8],
                  fill=(34, 28, 30, 255), outline=(64, 50, 48, 255),
                  width=3)
        d.arc([bx - br * 0.6, by - br * 0.6, bx + br * 0.3, by],
              180, 290, fill=(80, 64, 60, 255), width=3)

        for w_ in self.wisps:
            w_["y"] += w_["vy"] * dt
            w_["x"] += w_["vx"] * dt
            w_["r"] += 10 * dt
            w_["life"] -= dt
            if w_["life"] > 0:
                a = int(80 * min(1, w_["life"] * 2))
                d.ellipse([w_["x"] - w_["r"], w_["y"] - w_["r"],
                           w_["x"] + w_["r"], w_["y"] + w_["r"]],
                          fill=(70, 64, 64, a))
        self.wisps = [w_ for w_ in self.wisps if w_["life"] > 0]

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
                a0 = t * b["spin"]
                for j in range(3):
                    aa = a0 + j * 2.1
                    d.arc([b["x"] - r * 0.7, b["y"] - r * 0.7,
                           b["x"] + r * 0.7, b["y"] + r * 0.7],
                          math.degrees(aa), math.degrees(aa) + 50,
                          fill=(255, 230, 140, int(255 * heat)), width=3)
            else:
                d.arc([b["x"] - r * 0.6, b["y"] - r * 0.6,
                       b["x"] + r * 0.6, b["y"] + r * 0.6],
                      30, 80, fill=(18, 14, 14, 255), width=2)

        for s in self.sparks:
            a = int(255 * min(1, s["life"] * 2.2))
            d.line([s["x"], s["y"],
                    s["x"] - s["vx"] * 0.03, s["y"] - s["vy"] * 0.03],
                   fill=(255, 210, 110, a), width=2)

        out = np.asarray(img, dtype=np.uint8)
        if k > 0.55:
            amp = int(7 * (k - 0.55) / 0.45)
            if amp:
                out = np.roll(out, rng.randint(-amp, amp), axis=0)
        return self.lag(out, ts)


# ---------- RUNNER: critter on the loose ----------
# (Mary-the-Tasmanian-devil-class escape stories.)

class _Runner(_Renderer):
    """A little black critter bounds across rolling moonlit hills,
    clearing fences, rocks, logs and bushes as the world scrolls
    faster and faster. She always gets away.

    Escalation is REAL: the sim clock compounds, so per-frame ground
    travel grows until a single frame covers more than half a bound —
    the stride crosses its Nyquist limit and the legs/bounce alias
    (genuine temporal undersampling, the wagon-wheel effect). At the
    same time the terrain tessellation budget drops so the hills go
    visibly low-poly. When a frame eats a whole bound, the sim
    declares failure, hangs, reboots."""

    GROWTH = 1.18
    BASE_SPEED = 240.0
    BOUND_LEN = 190.0

    # Obstacle types: vault height + ground footprint.
    OBSTACLES = {
        "fence": {"vault": 86},
        "rock":  {"vault": 58},
        "log":   {"vault": 48},
        "bush":  {"vault": 66},
    }

    def __init__(self, seed=None):
        super().__init__(seed)
        self._cam_y = H * 0.5
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.scroll = 0.0
        kinds = list(self.OBSTACLES)
        self.obstacles = []
        ox = rng.uniform(700, 1500)
        while ox < 120000:
            self.obstacles.append({"x": ox, "kind": rng.choice(kinds),
                                   "seed": rng.random()})
            ox += rng.uniform(480, 1100)
        self.flushed: set[int] = set()
        self.birds: list[dict] = []
        self.trees = []
        tx = rng.uniform(400, 1200)
        while tx < 120000:
            self.trees.append((tx, rng.uniform(90, 150)))
            tx += rng.uniform(900, 2200)
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
        self.shooting: list[dict] = []
        self.scuffs: list[float] = []
        self._was_grounded = True
        self.ph = rng.uniform(0, math.tau)
        self.trail[:] = 0

    def _ground_y(self, world_x: float, layer: float = 1.0) -> float:
        x = world_x * layer
        return (H * 0.80
                + 34 * math.sin(x * 0.0019 + self.ph)
                + 16 * math.sin(x * 0.0053 + self.ph * 2))

    def _draw_obstacle(self, d, kind: str, sx: float, gy: float,
                       seed: float):
        if kind == "fence":
            wood = (76, 56, 38, 255)
            d.rectangle([sx - 5, gy - 66, sx + 5, gy], fill=wood)
            d.rectangle([sx - 34, gy - 60, sx + 34, gy - 47], fill=wood)
            d.rectangle([sx - 34, gy - 34, sx + 34, gy - 21], fill=wood)
            d.line([sx - 5, gy - 66, sx + 5, gy - 66],
                   fill=(96, 74, 52, 255), width=3)
        elif kind == "rock":
            w_ = 30 + seed * 16
            d.polygon([(sx - w_, gy), (sx - w_ * 0.5, gy - 40 - seed * 14),
                       (sx + w_ * 0.4, gy - 34), (sx + w_, gy)],
                      fill=(58, 58, 64, 255))
            d.line([(sx - w_ * 0.5, gy - 40 - seed * 14),
                    (sx - w_ * 0.1, gy - 12)],
                   fill=(82, 82, 90, 255), width=2)
        elif kind == "log":
            d.rounded_rectangle([sx - 44, gy - 30, sx + 44, gy - 4],
                                radius=13, fill=(82, 58, 38, 255))
            d.ellipse([sx + 32, gy - 30, sx + 56, gy - 4],
                      fill=(120, 92, 62, 255))
            d.ellipse([sx + 39, gy - 23, sx + 49, gy - 11],
                      fill=(82, 58, 38, 255))
            d.line([sx - 36, gy - 22, sx + 20, gy - 22],
                   fill=(60, 42, 28, 255), width=2)
        elif kind == "bush":
            for bx_, by_, br_ in ((-20, -22, 22), (12, -26, 24),
                                  (0, -12, 26)):
                d.ellipse([sx + bx_ - br_, gy + by_ - br_,
                           sx + bx_ + br_, gy + by_ + br_],
                          fill=(26, 46, 32, 255))
            d.ellipse([sx - 4, gy - 38, sx + 4, gy - 30],
                      fill=(150, 60, 80, 255))   # little berry

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        speed = self.BASE_SPEED * ts
        step = speed * dt
        # Nyquist check on the bound cadence: more than a whole bound
        # in one frame = motion no longer resolvable.
        if step / self.BOUND_LEN >= 1.0:
            self.declare_fail(t)
        self.scroll += step

        critter_wx = self.scroll + W * 0.30
        phase = (self.scroll / self.BOUND_LEN) % 1.0
        hop = math.sin(phase * math.pi)
        hop_v = math.cos(phase * math.pi)

        nxt = next((o for o in self.obstacles
                    if o["x"] > critter_wx - 60), None)
        vault = 0.0
        if nxt is not None:
            gap = nxt["x"] - critter_wx
            vh_ = self.OBSTACLES[nxt["kind"]]["vault"]
            if -80 < gap < 240:
                vault = _ease(1 - abs(gap - 80) / 160) * vh_
        gy_here = self._ground_y(critter_wx)
        cy = gy_here - 34 - hop * (34 + 18 * k) - vault

        if nxt is not None and nxt["kind"] == "fence":
            f_id = int(nxt["x"])
            if nxt["x"] - critter_wx < 320 and f_id not in self.flushed:
                self.flushed.add(f_id)
                fx0 = nxt["x"] - self.scroll
                fy0 = self._ground_y(nxt["x"]) - 70
                for _ in range(rng.randint(1, 3)):
                    self.birds.append({
                        "x": fx0 + rng.uniform(-12, 12), "y": fy0,
                        "vx": rng.uniform(-160, -60),
                        "vy": -rng.uniform(110, 200),
                        "ph": rng.uniform(0, math.tau), "life": 2.0})

        grounded = hop < 0.08 and vault < 4
        if grounded and not self._was_grounded:
            self.scuffs.append(critter_wx)
            self.scuffs = self.scuffs[-24:]
        self._was_grounded = grounded

        if rng.random() < 0.005:
            self.shooting.append({
                "x": rng.uniform(0, W), "y": rng.uniform(0, H * 0.3),
                "vx": rng.uniform(400, 700) * rng.choice([-1, 1]),
                "vy": rng.uniform(100, 220), "life": 1.0})

        gy_cam = gy_here - H * 0.62
        self._cam_y += (gy_cam - self._cam_y) * min(1.0, 4.0 * dt)
        cam = self._cam_y

        # Terrain tessellation budget collapses under load: 20px steps
        # at rest, growing to 120px — the hills genuinely go low-poly
        # because the "engine" can't afford the vertices anymore.
        tess = int(20 * max(1.0, ts / 2.5))

        # ---- sky ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 12 + 30 * g
        frame[..., 1] = 14 + 24 * g
        frame[..., 2] = 30 + 44 * g
        band = np.exp(-((np.linspace(0, 1, H) - 0.62) ** 2) / 0.012)
        frame[..., 0] += band[:, None] * 26
        frame[..., 1] += band[:, None] * 12

        self.trail *= 0.88
        _stamp_glow(self.trail, W * 0.30 - 14, cy - cam, 20 + 26 * k,
                    (110 + 110 * k, 130, 190), 0.4 + 0.9 * k)
        frame += self.trail

        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

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
        for s in self.shooting:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["life"] -= dt * 1.4
            if s["life"] > 0:
                a = int(220 * s["life"])
                d.line([s["x"], s["y"],
                        s["x"] - s["vx"] * 0.06, s["y"] - s["vy"] * 0.06],
                       fill=(255, 250, 230, a), width=2)
        self.shooting = [s for s in self.shooting if s["life"] > 0]
        for c in self.clouds:
            c["x"] = (c["x"] - c["s"] * dt) % (W + 300) - 150
            d.ellipse([c["x"], c["y"], c["x"] + c["w"], c["y"] + 36],
                      fill=(40, 46, 66, 120))

        far = [(x, self._ground_y(self.scroll * 0.30 + x, 0.65)
                - 150 - cam * 0.4) for x in range(0, W + 40, max(40, tess))]
        far.append((W, far[-1][1]))
        d.polygon([(0, H), *far, (W, H)], fill=(17, 23, 36, 255))
        mid = [(x, self._ground_y(self.scroll * 0.60 + x, 0.85)
                - 70 - cam * 0.7) for x in range(0, W + 30, max(30, tess))]
        mid.append((W, mid[-1][1]))
        d.polygon([(0, H), *mid, (W, H)], fill=(19, 28, 32, 255))

        for twx, th in self.trees:
            sx2 = (twx - self.scroll * 0.60)
            if -120 < sx2 < W + 120:
                base = self._ground_y(self.scroll * 0.60 + sx2, 0.85) \
                    - 70 - cam * 0.7
                trunk_top = base - th
                d.line([sx2, base, sx2 + th * 0.12, trunk_top],
                       fill=(15, 21, 25, 255), width=6)
                for cb, cr in ((0.95, 0.30), (0.75, 0.24), (0.6, 0.18)):
                    cx_ = sx2 + th * 0.12 * cb
                    cy_ = base - th * cb
                    d.ellipse([cx_ - th * cr, cy_ - th * cr * 0.7,
                               cx_ + th * cr, cy_ + th * cr * 0.7],
                              fill=(16, 24, 27, 255))

        near = [(x, self._ground_y(self.scroll + x) - cam)
                for x in range(0, W + 20, tess)]
        near.append((W, near[-1][1]))
        d.polygon([(0, H), *near, (W, H)], fill=(24, 34, 31, 255))
        d.line(near, fill=(52, 74, 58, 255), width=3)
        for x in range(0, W, 26):
            wx2 = self.scroll + x
            if int(wx2 / 26) % 3 == 0:
                gy = self._ground_y(wx2) - cam
                lean = 5 + 22 * k
                d.line([x, gy, x - lean, gy - 13],
                       fill=(44, 78, 54, 255), width=2)

        for swx in self.scuffs:
            sx2 = swx - self.scroll
            if -40 < sx2 < W:
                gy = self._ground_y(swx) - cam
                age = (critter_wx - swx) / 2200
                a = int(max(0, 120 * (1 - age)))
                if a > 8:
                    d.line([sx2 - 7, gy - 2, sx2 + 2, gy - 4],
                           fill=(14, 20, 18, a), width=3)
                    d.line([sx2 + 6, gy - 2, sx2 + 13, gy - 4],
                           fill=(14, 20, 18, a), width=3)

        for f in self.fireflies:
            fy = f["y"] + 10 * math.sin(t * 1.3 + f["ph"]) - cam * 0.9
            fx = (f["x"] - speed * 0.08 * t) % W
            a = int(110 + 110 * math.sin(t * 3 + f["ph"]))
            d.ellipse([fx - 3, fy - 3, fx + 3, fy + 3],
                      fill=(220, 255, 140, max(40, a)))

        for o in self.obstacles:
            sx2 = o["x"] - self.scroll
            if -80 < sx2 < W + 80:
                gy = self._ground_y(o["x"]) - cam
                self._draw_obstacle(d, o["kind"], sx2, gy, o["seed"])

        for b in self.birds:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["vy"] -= 20 * dt
            b["life"] -= dt * 0.5
            if b["life"] > 0:
                flap = math.sin(t * 16 + b["ph"]) * 7
                by_ = b["y"] - cam * 0.3
                a = int(min(255, 255 * b["life"]))
                d.line([b["x"] - 11, by_ - flap, b["x"], by_],
                       fill=(20, 22, 28, a), width=3)
                d.line([b["x"], by_, b["x"] + 11, by_ - flap],
                       fill=(20, 22, 28, a), width=3)
        self.birds = [b for b in self.birds if b["life"] > 0]

        # ---- the critter ----
        x0 = W * 0.30
        cyv = cy - cam
        airborne = hop > 0.08 or vault > 4
        stretch = 1.0 + 0.18 * abs(hop_v) * (1 if airborne else 0)
        squash = 1.0 / stretch
        bw, bh = 58 * squash * 1.15, 42 * stretch * 0.95
        body_col = (20, 17, 17, 255)
        tail_y = cyv - 6 + 10 * math.sin(phase * math.tau + 1.4)
        d.line([x0 - bw / 2, cyv, x0 - bw / 2 - 30, tail_y],
               fill=body_col, width=9)
        d.ellipse([x0 - bw / 2, cyv - bh / 2, x0 + bw / 2, cyv + bh / 2],
                  fill=body_col)
        d.ellipse([x0 - bw * 0.55, cyv - bh * 0.30,
                   x0 - bw * 0.05, cyv + bh * 0.55], fill=body_col)
        d.arc([x0 - bw * 0.05, cyv - bh * 0.25,
               x0 + bw * 0.5, cyv + bh * 0.55],
              40, 150, fill=(235, 235, 230, 255), width=5)
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
        hx = x0 + bw * 0.46
        hy = cyv - bh * 0.52
        d.ellipse([hx - 19, hy - 17, hx + 19, hy + 17], fill=body_col)
        d.ellipse([hx + 8, hy - 4, hx + 30, hy + 10], fill=body_col)
        d.ellipse([hx + 22, hy + 1, hx + 27, hy + 6],
                  fill=(60, 45, 45, 255))
        twitch = 4 if math.sin(t * 0.9) > 0.96 else 0
        d.polygon([(hx - 13, hy - 13), (hx - 6, hy - 30 - twitch),
                   (hx, hy - 11)], fill=body_col)
        d.polygon([(hx - 10, hy - 14), (hx - 6, hy - 25 - twitch),
                   (hx - 2, hy - 12)], fill=(200, 120, 130, 255))
        d.polygon([(hx + 2, hy - 12), (hx + 9, hy - 27), (hx + 14, hy - 9)],
                  fill=body_col)
        blink = (t % 3.4) < 0.12
        if not blink:
            d.ellipse([hx + 4, hy - 6, hx + 11, hy + 1],
                      fill=(255, 255, 255, 255))
            d.ellipse([hx + 7, hy - 4, hx + 10, hy - 1],
                      fill=(0, 0, 0, 255))
        else:
            d.line([hx + 4, hy - 2, hx + 11, hy - 2],
                   fill=(60, 50, 50, 255), width=2)

        if grounded:
            for _ in range(3):
                dx_ = rng.uniform(-30, 0)
                d.ellipse([x0 + dx_ - 5, cyv + bh / 2 - 2,
                           x0 + dx_ + 5, cyv + bh / 2 + 8],
                          fill=(96, 96, 84, 100))
        if k > 0.5:
            for _ in range(int(12 * k)):
                ly = rng.uniform(H * 0.25, H * 0.9)
                ll = rng.uniform(40, 170) * k
                lx = rng.uniform(0, W)
                d.line([lx, ly, lx + ll, ly],
                       fill=(220, 225, 255, int(60 * k)), width=2)

        out = np.asarray(img, dtype=np.uint8)
        return self.lag(out, ts)
# ---------- STACKER: world-record tower assembly ----------
# (Mr.-Potato-Head-speed-record-class stories: records, builds,
# assemblies, "world's biggest X".)

class _Stacker(_Renderer):
    """Toy blocks rain onto a table and snap into a growing tower
    while a ruler tracks the record line. Drop cadence and fall speed
    ride the compounding sim clock; at high clock a falling block
    covers more than a block-height per frame, tunnels straight
    through the stack top (genuine missed collision), wedges into the
    tower and knocks it loose — the whole stack converts to scatter
    bodies whose floor bounces gain energy from the oversized
    timestep until velocities leave reality. Fail, hang, fresh table.

    Charter audit: topic-matched (record assembly) / escalates /
    real break (tunneling + Euler energy gain) / emergent reset /
    plinko interaction (block-block + floor) / table has legs +
    shadow (nothing floats) / foreground show / variety (block
    widths, colors, landing offsets) / flavor (confetti every 5th,
    ruler ticks, dust motes, wobble lean, landing squash) / smooth
    (eased conveyor shift, squash on land)."""

    GROWTH = 1.18
    GRAV = 1500.0
    BLOWUP_V = 6000.0
    PALETTES = [
        [(235, 90, 80), (250, 180, 60), (90, 180, 220), (130, 200, 120)],
        [(250, 140, 160), (160, 130, 230), (90, 200, 210), (250, 210, 90)],
        [(230, 120, 70), (110, 160, 230), (240, 200, 80), (170, 210, 110)],
    ]

    def __init__(self, seed=None):
        super().__init__(seed)
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.trail[:] = 0
        self.palette = rng.choice(self.PALETTES)
        self.table_y = H * 0.86
        self.table_cx = W / 2 + rng.uniform(-60, 60)
        self.table_w = rng.uniform(360, 440)
        self.stack: list[dict] = []      # settled blocks, bottom->top
        self.falling: dict | None = None
        self.scatter: list[dict] = []    # collapse bodies
        self.confetti: list[dict] = []
        self.motes = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H),
                       "ph": rng.uniform(0, math.tau)} for _ in range(14)]
        self.best_h = 0.0               # record line (px above table)
        self.shift = 0.0                # eased conveyor offset
        self.shift_target = 0.0
        self.lean = 0.0                 # accumulated wobble
        self.placed = 0
        self.collapsing = False

    def _top_y(self) -> float:
        y = self.table_y + self.shift
        for b in self.stack:
            y -= b["h"]
        return y

    def _spawn_block(self):
        rng = self.rng
        top_x = (self.stack[-1]["x"] if self.stack else self.table_cx)
        return {"x": top_x + rng.uniform(-70, 70),
                "y": -40.0, "vy": 0.0,
                "vx": rng.uniform(-14, 14),
                "w": rng.uniform(90, 150), "h": rng.uniform(44, 62),
                "color": rng.choice(self.palette),
                "settle": 0.0}

    def _collapse(self):
        """Tower comes apart: every settled block becomes a body."""
        rng = self.rng
        self.collapsing = True
        y = self.table_y + self.shift
        for b in self.stack:
            y -= b["h"]
            self.scatter.append({
                "x": b["x"], "y": y + b["h"] / 2,
                "vx": rng.uniform(-420, 420),
                "vy": rng.uniform(-520, -60),
                "w": b["w"], "h": b["h"], "color": b["color"],
                "rot": 0.0, "vrot": rng.uniform(-7, 7)})
        self.stack = []

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        sim_dt = dt * ts

        # Eased conveyor shift (tower sinks as it grows so the top
        # stays in frame).
        self.shift += (self.shift_target - self.shift) * min(1, 6 * dt)

        if self.falling is None and not self.collapsing:
            self.falling = self._spawn_block()

        if self.falling is not None:
            f = self.falling
            f["vy"] += self.GRAV * sim_dt
            step = f["vy"] * sim_dt
            f["x"] += f["vx"] * sim_dt
            top_y = self._top_y()
            # REAL tunneling check: if this frame's travel exceeds the
            # block's own height, the collision test below can be
            # skipped over — that's the failure seed.
            tunneled = step > f["h"] and f["y"] + step > top_y + f["h"]
            f["y"] += step
            if f["y"] + f["h"] / 2 >= top_y and not tunneled:
                # Clean landing?
                base_x = (self.stack[-1]["x"] if self.stack
                          else self.table_cx)
                base_w = (self.stack[-1]["w"] if self.stack
                          else self.table_w)
                off = f["x"] - base_x
                if abs(off) < (f["w"] + base_w) / 2 * 0.55:
                    self.stack.append({"x": f["x"], "w": f["w"],
                                       "h": f["h"], "color": f["color"],
                                       "settle": t})
                    self.placed += 1
                    self.lean += off * 0.04
                    height = sum(b["h"] for b in self.stack)
                    self.best_h = max(self.best_h, height)
                    if height > H * 0.5:
                        self.shift_target += f["h"] * 1.6
                    if self.placed % 5 == 0:
                        for _ in range(26):
                            a = rng.uniform(0, math.tau)
                            v = rng.uniform(120, 420)
                            self.confetti.append({
                                "x": f["x"], "y": self._top_y(),
                                "vx": math.cos(a) * v,
                                "vy": math.sin(a) * v - 180,
                                "col": rng.choice(self.palette),
                                "life": rng.uniform(0.6, 1.2)})
                else:
                    # Missed the stack — block tumbles off as a body.
                    self.scatter.append({
                        "x": f["x"], "y": f["y"], "vx": f["vx"] * 6,
                        "vy": -120.0, "w": f["w"], "h": f["h"],
                        "color": f["color"], "rot": 0.0,
                        "vrot": rng.uniform(-6, 6)})
                self.falling = None
            elif tunneled and self.stack:
                # Wedged INTO the tower between frames: knock it all
                # down. The break the clock was building toward.
                self._collapse()
                self.falling = None

        # Scatter bodies: floor bounce with timestep energy gain.
        for s in self.scatter:
            s["vy"] += self.GRAV * sim_dt
            s["x"] += s["vx"] * sim_dt
            s["y"] += s["vy"] * sim_dt
            s["rot"] += s["vrot"] * sim_dt
            floor = self.table_y + self.shift
            if s["y"] + s["h"] / 2 > floor and s["vy"] > 0:
                pen = s["y"] + s["h"] / 2 - floor
                s["y"] = floor - s["h"] / 2
                rest = 0.6 * (1.0 + min(2.0, pen / 200.0))
                s["vy"] = -s["vy"] * rest
                s["vx"] += rng.uniform(-40, 40)
            if (abs(s["vx"]) > self.BLOWUP_V
                    or abs(s["vy"]) > self.BLOWUP_V):
                self.declare_fail(t)
        self.scatter = [s for s in self.scatter
                        if -400 < s["x"] < W + 400 and s["y"] < H + 400]
        if self.collapsing and not self.scatter:
            # Everything flew out before velocities blew up — still a
            # dead sim; reboot.
            self.declare_fail(t)

        # ---- paint ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 38 + 26 * g
        frame[..., 1] = 32 + 20 * g
        frame[..., 2] = 44 + 18 * g
        frame += self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Dust motes in the room light.
        for m in self.motes:
            mx = (m["x"] + 12 * math.sin(t * 0.4 + m["ph"])) % W
            my = (m["y"] + 8 * math.sin(t * 0.3 + m["ph"] * 2)) % H
            a = int(40 + 30 * math.sin(t + m["ph"]))
            d.ellipse([mx - 2, my - 2, mx + 2, my + 2],
                      fill=(255, 245, 220, max(20, a)))

        # Ruler on the right: ticks + the record line.
        rx = W - 70
        d.line([rx, 60, rx, self.table_y + self.shift],
               fill=(180, 170, 150, 200), width=3)
        for yy in range(int(self.table_y + self.shift), 60, -60):
            d.line([rx - 12, yy, rx, yy], fill=(180, 170, 150, 200),
                   width=2)
        if self.best_h > 0:
            ry = self.table_y + self.shift - self.best_h
            for xx in range(int(rx) - 50, int(rx), 12):
                d.line([xx, ry, xx + 6, ry],
                       fill=(250, 200, 90, 230), width=3)

        # Table: top + legs + soft contact shadow (nothing floats).
        ty = self.table_y + self.shift
        d.ellipse([self.table_cx - self.table_w * 0.7, ty + 26,
                   self.table_cx + self.table_w * 0.7, ty + 48],
                  fill=(14, 12, 16, 120))
        d.rectangle([self.table_cx - self.table_w / 2, ty,
                     self.table_cx + self.table_w / 2, ty + 18],
                    fill=(120, 86, 56, 255))
        for sgn in (-1, 1):
            lx = self.table_cx + sgn * self.table_w * 0.4
            d.rectangle([lx - 9, ty + 18, lx + 9, min(H, ty + 120)],
                        fill=(96, 68, 44, 255))

        # The tower (with its accumulated lean wobble).
        y = ty
        wob = self.lean * math.sin(t * 1.1) * 0.4
        for n_, b in enumerate(self.stack):
            y -= b["h"]
            bx = b["x"] + wob * (n_ + 1)
            squash = 1.0
            if t - b["settle"] < 0.25:
                u = (t - b["settle"]) / 0.25
                squash = 1.0 - 0.18 * (1 - u) * math.cos(u * 9)
            bw_, bh_ = b["w"], b["h"] * squash
            d.rounded_rectangle(
                [bx - bw_ / 2, y + b["h"] - bh_,
                 bx + bw_ / 2, y + b["h"]],
                radius=10, fill=(*b["color"], 255),
                outline=(20, 18, 24, 255), width=3)
            d.line([bx - bw_ / 2 + 8, y + b["h"] - bh_ + 8,
                    bx + bw_ / 2 - 8, y + b["h"] - bh_ + 8],
                   fill=(255, 255, 255, 70), width=3)

        # Falling block + drop shadow on the landing zone.
        if self.falling is not None:
            f = self.falling
            top_y = self._top_y()
            sh_w = f["w"] * (0.4 + 0.6 * min(1, (top_y - f["y"]) / 600))
            d.ellipse([f["x"] - sh_w / 2, top_y - 6,
                       f["x"] + sh_w / 2, top_y + 6],
                      fill=(10, 10, 14, 90))
            d.rounded_rectangle(
                [f["x"] - f["w"] / 2, f["y"] - f["h"] / 2,
                 f["x"] + f["w"] / 2, f["y"] + f["h"] / 2],
                radius=10, fill=(*f["color"], 255),
                outline=(20, 18, 24, 255), width=3)

        # Scatter bodies (rotated rects via polygon).
        for s in self.scatter:
            c, sn = math.cos(s["rot"]), math.sin(s["rot"])
            hw, hh = s["w"] / 2, s["h"] / 2
            pts = [(s["x"] + dx_ * c - dy_ * sn,
                    s["y"] + dx_ * sn + dy_ * c)
                   for dx_, dy_ in ((-hw, -hh), (hw, -hh),
                                    (hw, hh), (-hw, hh))]
            d.polygon(pts, fill=(*s["color"], 255),
                      outline=(20, 18, 24, 255))

        # Confetti.
        for cf in self.confetti:
            cf["vy"] += 500 * dt
            cf["x"] += cf["vx"] * dt
            cf["y"] += cf["vy"] * dt
            cf["life"] -= dt
            if cf["life"] > 0:
                a = int(255 * min(1, cf["life"] * 2))
                d.rectangle([cf["x"] - 4, cf["y"] - 2,
                             cf["x"] + 4, cf["y"] + 2],
                            fill=(*cf["col"], a))
        self.confetti = [cf for cf in self.confetti if cf["life"] > 0]

        out = np.asarray(img, dtype=np.uint8)
        return self.lag(out, ts)

# ---------- FIGHT: red vs blue clash in the octagon ----------
# (UFC-fight-card-class stories.)

class _Fight(_Renderer):
    """Two glowing orbs — red corner, blue corner — circle each other
    inside an octagon and CLASH, throwing sparks and knocking each
    other back, over and over, harder and faster. Camera flashes pop
    in the dark crowd. Screenshot test: octagon + red vs blue = a
    fight, readable in under a second.

    The break is real: each orb steers toward its opponent with an
    acceleration integrated at sim_dt. Explicit-Euler steering at a
    growing timestep is the textbook divergent oscillator — the
    correction overshoots harder every step until both orbs slingshot
    past each other at impossible speeds. Velocity watchdog fails the
    sim; hang; fresh arena."""

    GROWTH = 1.17
    BLOWUP_V = 6800.0
    R_BALL = 36.0

    def __init__(self, seed=None):
        super().__init__(seed)
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.trail[:] = 0
        self.cx = W / 2 + rng.uniform(-40, 40)
        self.cy = H * 0.52
        self.R = rng.uniform(300, 350)
        # Octagon edges (inward normals precomputed).
        self.verts = []
        rot0 = rng.uniform(0, math.pi / 4)
        for n_ in range(8):
            a = rot0 + n_ * math.tau / 8
            self.verts.append((self.cx + math.cos(a) * self.R,
                               self.cy + math.sin(a) * self.R))
        self.balls = []
        for sgn, col, glow in ((-1, (235, 60, 55), (200, 50, 40)),
                               (1, (70, 130, 240), (50, 90, 220))):
            self.balls.append({
                "x": self.cx + sgn * self.R * 0.55,
                "y": self.cy + rng.uniform(-40, 40),
                "vx": 0.0, "vy": 0.0,
                "col": col, "glow": glow,
                "clash_t": -9.0, "clash_ax": 1.0, "clash_ay": 0.0,
                "ph": rng.uniform(0, math.tau)})
        self.sparks: list[dict] = []
        self.flashes: list[dict] = []     # crowd camera flashes
        self.ring_pulse = -9.0

    def _edges(self):
        for n_ in range(8):
            a = self.verts[n_]
            b = self.verts[(n_ + 1) % 8]
            yield a, b

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        sim_dt = dt * ts

        # ---- physics ----
        a_, b_ = self.balls
        for me, foe in ((a_, b_), (b_, a_)):
            dx, dy = foe["x"] - me["x"], foe["y"] - me["y"]
            dist = math.hypot(dx, dy) or 1e-6
            ux, uy = dx / dist, dy / dist
            # Charge at the opponent + a tangential circling bias that
            # breathes, so they orbit, line up, and slam.
            charge = 900.0
            circ = 520.0 * math.sin(t * 0.9 + me["ph"])
            ax = ux * charge - uy * circ - me["vx"] * 1.4
            ay = uy * charge + ux * circ - me["vy"] * 1.4
            me["vx"] += ax * sim_dt
            me["vy"] += ay * sim_dt
            me["x"] += me["vx"] * sim_dt
            me["y"] += me["vy"] * sim_dt
            if (abs(me["vx"]) > self.BLOWUP_V
                    or abs(me["vy"]) > self.BLOWUP_V):
                self.declare_fail(t)

        # Ball-ball clash.
        dx, dy = b_["x"] - a_["x"], b_["y"] - a_["y"]
        dist = math.hypot(dx, dy)
        min_d = self.R_BALL * 2
        if 0 < dist < min_d:
            nx, ny = dx / dist, dy / dist
            overlap = (min_d - dist) / 2
            a_["x"] -= nx * overlap
            a_["y"] -= ny * overlap
            b_["x"] += nx * overlap
            b_["y"] += ny * overlap
            van = a_["vx"] * nx + a_["vy"] * ny
            vbn = b_["vx"] * nx + b_["vy"] * ny
            rel = van - vbn
            if rel > 0:
                e = 1.05          # clash knockback: slightly springy
                a_["vx"] -= (1 + e) / 2 * rel * nx
                a_["vy"] -= (1 + e) / 2 * rel * ny
                b_["vx"] += (1 + e) / 2 * rel * nx
                b_["vy"] += (1 + e) / 2 * rel * ny
                mx_, my_ = (a_["x"] + b_["x"]) / 2, (a_["y"] + b_["y"]) / 2
                power = min(1.0, rel / 1400)
                for _ in range(int(10 + 22 * power)):
                    sa = rng.uniform(0, math.tau)
                    sv = rng.uniform(150, 700) * (0.4 + power)
                    self.sparks.append({
                        "x": mx_, "y": my_,
                        "vx": math.cos(sa) * sv, "vy": math.sin(sa) * sv,
                        "col": rng.choice([a_["col"], b_["col"],
                                           (255, 240, 200)]),
                        "life": rng.uniform(0.25, 0.6)})
                for me in (a_, b_):
                    me["clash_t"] = t
                    me["clash_ax"], me["clash_ay"] = nx, ny
                self.ring_pulse = t
                # Crowd reacts: a burst of camera flashes.
                for _ in range(rng.randint(2, 5)):
                    fa = rng.uniform(0, math.tau)
                    fr = self.R * rng.uniform(1.15, 1.55)
                    self.flashes.append({
                        "x": self.cx + math.cos(fa) * fr,
                        "y": self.cy + math.sin(fa) * fr * 0.8,
                        "life": rng.uniform(0.08, 0.2)})

        # Octagon wall reflection (inward normals).
        for ball in self.balls:
            for ea, eb in self._edges():
                ex, ey = eb[0] - ea[0], eb[1] - ea[1]
                el = math.hypot(ex, ey)
                nx, ny = -ey / el, ex / el     # normal
                # Ensure normal points inward (toward center).
                if (self.cx - ea[0]) * nx + (self.cy - ea[1]) * ny < 0:
                    nx, ny = -nx, -ny
                d_ = (ball["x"] - ea[0]) * nx + (ball["y"] - ea[1]) * ny
                if d_ < self.R_BALL:
                    push = self.R_BALL - d_
                    ball["x"] += nx * push
                    ball["y"] += ny * push
                    vn = ball["vx"] * nx + ball["vy"] * ny
                    if vn < 0:
                        ball["vx"] -= 1.85 * vn * nx
                        ball["vy"] -= 1.85 * vn * ny

        # Trails.
        self.trail *= 0.90
        for ball in self.balls:
            _stamp_glow(self.trail, ball["x"], ball["y"],
                        self.R_BALL * (1.3 + 0.5 * k),
                        tuple(c * (0.45 + 0.4 * k) for c in ball["glow"]),
                        0.8)

        # Idle crowd flashes (sparse) — bursts come from clashes.
        if rng.random() < 0.06 + 0.10 * k:
            fa = rng.uniform(0, math.tau)
            fr = self.R * rng.uniform(1.15, 1.6)
            self.flashes.append({"x": self.cx + math.cos(fa) * fr,
                                 "y": self.cy + math.sin(fa) * fr * 0.8,
                                 "life": rng.uniform(0.06, 0.16)})

        # ---- paint ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 16 + 10 * g
        frame[..., 1] = 13 + 8 * g
        frame[..., 2] = 18 + 10 * g
        frame += self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Crowd camera flashes (outside the cage, in the dark).
        for fl in self.flashes:
            fl["life"] -= dt
            if fl["life"] > 0:
                a = int(255 * min(1, fl["life"] * 8))
                r_ = 3 + 5 * fl["life"] * 8
                d.ellipse([fl["x"] - r_, fl["y"] - r_,
                           fl["x"] + r_, fl["y"] + r_],
                          fill=(255, 250, 235, a))
        self.flashes = [fl for fl in self.flashes if fl["life"] > 0]

        # Octagon floor: slightly lit canvas + center emblem.
        d.polygon(self.verts, fill=(34, 30, 34, 255))
        d.ellipse([self.cx - 70, self.cy - 70,
                   self.cx + 70, self.cy + 70],
                  outline=(70, 62, 60, 255), width=4)
        d.ellipse([self.cx - 44, self.cy - 44,
                   self.cx + 44, self.cy + 44],
                  outline=(58, 52, 52, 255), width=3)

        # Cage edge: a ring pulse flashes on every clash.
        pulse = max(0.0, 1 - (t - self.ring_pulse) / 0.35)
        edge_col = (160 + int(70 * pulse), 150 + int(60 * pulse),
                    140 + int(60 * pulse), 255)
        d.polygon(self.verts, outline=edge_col)
        d.line(self.verts + [self.verts[0]], fill=edge_col, width=6)
        # Corner posts with little glow caps.
        for vx_, vy_ in self.verts:
            d.ellipse([vx_ - 9, vy_ - 9, vx_ + 9, vy_ + 9],
                      fill=(120, 112, 104, 255))
            d.ellipse([vx_ - 4, vy_ - 4, vx_ + 4, vy_ + 4],
                      fill=(255, 235, 180, 200))

        # The fighters: glow halo + ball + squash on clash + face-off
        # eye dot so they read as combatants, not particles.
        for ball in self.balls:
            foe = self.balls[1] if ball is self.balls[0] else self.balls[0]
            r_ = self.R_BALL
            # Contact shadow on the canvas.
            d.ellipse([ball["x"] - r_ * 0.9, self.cy + self.R * 0.78,
                       ball["x"] + r_ * 0.9, self.cy + self.R * 0.78 + 14],
                      fill=(10, 9, 11, 70))
            # Squash along the clash axis right after impact.
            sq = 1.0
            if t - ball["clash_t"] < 0.14:
                sq = 1.0 - 0.28 * (1 - (t - ball["clash_t"]) / 0.14)
            ang = math.atan2(ball["clash_ay"], ball["clash_ax"])
            wr, hr = r_ * sq, r_ * (2 - sq) * 0.5 + r_ * 0.5
            # Approximate squashed circle with an ellipse aligned by
            # drawing in unrotated frame (cheap, reads fine at speed).
            d.ellipse([ball["x"] - wr, ball["y"] - hr,
                       ball["x"] + wr, ball["y"] + hr],
                      fill=(*ball["col"], 255))
            d.ellipse([ball["x"] - wr, ball["y"] - hr,
                       ball["x"] + wr, ball["y"] + hr],
                      outline=tuple(int(c * 0.6) for c in ball["col"])
                      + (255,), width=4)
            # Specular + an "eye" facing the opponent.
            d.ellipse([ball["x"] - wr * 0.5, ball["y"] - hr * 0.55,
                       ball["x"] - wr * 0.1, ball["y"] - hr * 0.15],
                      fill=(255, 255, 255, 130))
            fx, fy = foe["x"] - ball["x"], foe["y"] - ball["y"]
            fl_ = math.hypot(fx, fy) or 1
            ex_ = ball["x"] + fx / fl_ * wr * 0.45
            ey_ = ball["y"] + fy / fl_ * hr * 0.45
            d.ellipse([ex_ - 7, ey_ - 7, ex_ + 7, ey_ + 7],
                      fill=(252, 252, 252, 255))
            d.ellipse([ex_ - 3, ey_ - 3, ex_ + 3, ey_ + 3],
                      fill=(15, 15, 18, 255))

        # Clash sparks.
        for s in self.sparks:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vy"] += 900 * dt
            s["life"] -= dt
            if s["life"] > 0:
                a = int(255 * min(1, s["life"] * 3))
                d.line([s["x"], s["y"],
                        s["x"] - s["vx"] * 0.02, s["y"] - s["vy"] * 0.02],
                       fill=(*s["col"], a), width=3)
        self.sparks = [s for s in self.sparks if s["life"] > 0]

        out = np.asarray(img, dtype=np.uint8)
        return self.lag(out, ts)


# ---------- TRAIN: armored express through the night ----------
# (Xi-Kim-summit-class stories — Kim's famous armored train — plus
# any rail/transit story.)

class _Train(_Renderer):
    """A dark-green armored train with a gold stripe barrels through
    a moonlit landscape, coupling rods churning, smoke streaming,
    telegraph poles whipping past. Rectangles + spoked wheels +
    parallax: reads as 'train at night' from any frame.

    The break is the wagon-wheel effect made load-bearing: wheel
    rotation is derived from distance travelled, so as the sim clock
    compounds, rotation-per-frame climbs toward (and past) the
    sampling limit — spokes genuinely stutter, freeze, then spin
    backwards on screen. When a single frame advances the wheels more
    than half a turn (Nyquist) the motion is unresolvable: fail,
    hang, fresh night."""

    GROWTH = 1.16
    BASE_SPEED = 330.0
    WHEEL_R = 30.0
    N_SPOKES = 4

    def __init__(self, seed=None):
        super().__init__(seed)
        self.reset_t = 0.0
        self.failed_at = None
        self._regen()

    def _regen(self):
        rng = self.rng
        self.trail[:] = 0
        self.scroll = 0.0
        self.track_y = H * 0.74
        self.moon = (rng.uniform(W * 0.6, W * 0.9),
                     rng.uniform(90, 180))
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H * 0.5),
                       rng.uniform(0.5, 1.5)) for _ in range(60)]
        self.ridge_ph = rng.uniform(0, math.tau)
        self.poles_gap = rng.uniform(420, 520)
        self.smoke: list[dict] = []
        self.n_cars = rng.randint(3, 4)
        self.window_ph = rng.uniform(0, 10)
        # Signal lights appear at world positions.
        self.signals = []
        sx = rng.uniform(1500, 2500)
        while sx < 200000:
            self.signals.append(sx)
            sx += rng.uniform(2600, 5200)

    def draw(self, t: float, i: int) -> np.ndarray:
        rng = self.rng
        held = self.handle_fail(self._last_frame
                                if self._last_frame is not None
                                else np.zeros((H, W, 3), np.uint8), t)
        if held is not None:
            return held

        ts = self.sim_scale(t)
        k = self.kk(ts)
        dt = 1 / FPS
        speed = self.BASE_SPEED * ts
        step = speed * dt
        self.scroll += step

        # The honest Nyquist failure: wheel turn per frame.
        turn_per_frame = step / self.WHEEL_R          # radians
        spoke_period = math.tau / self.N_SPOKES
        if turn_per_frame > spoke_period * 2:
            self.declare_fail(t)
        wheel_rot = self.scroll / self.WHEEL_R

        # Track clack: tiny bounce as ties pass under the wheels,
        # amplitude grows with speed.
        tie_gap = 64.0
        clack_ph = (self.scroll % tie_gap) / tie_gap
        bounce = math.sin(clack_ph * math.pi) * min(5.0, 1.2 + 2.4 * k)

        # Smoke from the funnel.
        loco_x = W * 0.30
        body_y = self.track_y - 64 + bounce
        if rng.random() < 0.5 + 0.4 * k:
            self.smoke.append({
                "x": loco_x + 58, "y": body_y - 36,
                "vx": -speed * 0.12 - rng.uniform(10, 50),
                "vy": -rng.uniform(36, 80),
                "r": rng.uniform(7, 14), "life": 1.0})

        # ---- paint ----
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        frame = np.zeros((H, W, 3), dtype=np.float32)
        frame[..., 0] = 10 + 16 * g
        frame[..., 1] = 12 + 18 * g
        frame[..., 2] = 26 + 30 * g
        frame += self.trail
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img, "RGBA")

        # Moon + stars.
        mx, my = self.moon
        for hr_, ha in ((60, 26), (50, 44)):
            d.ellipse([mx - hr_, my - hr_, mx + hr_, my + hr_],
                      fill=(230, 230, 212, ha))
        d.ellipse([mx - 40, my - 40, mx + 40, my + 40],
                  fill=(233, 233, 216, 255))
        d.ellipse([mx - 12, my - 16, mx + 2, my - 4],
                  fill=(212, 212, 196, 255))
        for sx, sy, sr in self.stars:
            tw = 130 + 70 * math.sin(t * 2 + sx)
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                      fill=(220, 225, 255, int(max(60, tw))))

        # Far ridge (slow parallax).
        ridge = [(x, H * 0.58
                  + 40 * math.sin((self.scroll * 0.12 + x) * 0.004
                                  + self.ridge_ph)
                  + 18 * math.sin((self.scroll * 0.12 + x) * 0.011))
                 for x in range(0, W + 40, 40)]
        d.polygon([(0, H), *ridge, (W, H)], fill=(15, 19, 30, 255))

        # Telegraph poles + sagging wire (mid parallax).
        pole_scroll = self.scroll * 0.55
        first = -(pole_scroll % self.poles_gap)
        px_list = []
        x_ = first
        while x_ < W + self.poles_gap:
            px_list.append(x_)
            x_ += self.poles_gap
        pole_top = H * 0.40
        for px_ in px_list:
            d.line([px_, self.track_y - 6, px_, pole_top],
                   fill=(20, 24, 32, 255), width=7)
            d.line([px_ - 22, pole_top + 12, px_ + 22, pole_top + 12],
                   fill=(20, 24, 32, 255), width=5)
        for pa, pb in zip(px_list, px_list[1:]):
            mid = (pa + pb) / 2
            d.line([pa, pole_top + 12, mid, pole_top + 44],
                   fill=(26, 30, 40, 255), width=2)
            d.line([mid, pole_top + 44, pb, pole_top + 12],
                   fill=(26, 30, 40, 255), width=2)

        # Passing signal lights (red blinker on a post).
        for swx in self.signals:
            sx2 = swx - self.scroll
            if -60 < sx2 < W + 60:
                d.line([sx2, self.track_y, sx2, self.track_y - 110],
                       fill=(30, 32, 40, 255), width=6)
                on = math.sin(t * 9) > 0
                d.ellipse([sx2 - 10, self.track_y - 132,
                           sx2 + 10, self.track_y - 112],
                          fill=(255, 60, 50, 255) if on
                          else (90, 28, 26, 255))

        # Track bed: ballast strip, rail, ties scrolling at full speed.
        d.rectangle([0, self.track_y + 10, W, H],
                    fill=(16, 17, 22, 255))
        d.line([0, self.track_y + 10, W, self.track_y + 10],
               fill=(70, 72, 84, 255), width=4)
        tie_first = -(self.scroll % tie_gap)
        x_ = tie_first
        while x_ < W + tie_gap:
            d.line([x_, self.track_y + 12, x_ - 10, self.track_y + 30],
                   fill=(36, 32, 30, 255), width=8)
            x_ += tie_gap

        # Smoke trail (drawn behind the train).
        for sm in self.smoke:
            sm["x"] += sm["vx"] * dt
            sm["y"] += sm["vy"] * dt
            sm["r"] += 14 * dt
            sm["life"] -= dt * 0.5
            if sm["life"] > 0:
                sh = int(54 + 30 * sm["life"])
                d.ellipse([sm["x"] - sm["r"], sm["y"] - sm["r"],
                           sm["x"] + sm["r"], sm["y"] + sm["r"]],
                          fill=(sh, sh, sh + 4, int(140 * sm["life"])))
        self.smoke = [sm for sm in self.smoke if sm["life"] > 0]

        # ---- the train (fixed on screen; the world moves) ----
        GREEN = (26, 56, 40, 255)
        GREEN_D = (18, 40, 30, 255)
        GOLD = (212, 174, 78, 255)
        car_w, car_h, gap2 = 218, 64, 14
        # Ground shadow.
        total_w = 90 + (car_w + gap2) * self.n_cars + car_w
        d.ellipse([loco_x - 60, self.track_y + 6,
                   loco_x + total_w * 0.9, self.track_y + 22],
                  fill=(6, 7, 10, 110))

        def wheels(x0, x1, y0):
            xs = [x0 + 36, (x0 + x1) / 2, x1 - 36]
            cranks = []
            for wx_ in xs:
                d.ellipse([wx_ - self.WHEEL_R, y0 - self.WHEEL_R,
                           wx_ + self.WHEEL_R, y0 + self.WHEEL_R],
                          fill=(24, 24, 28, 255),
                          outline=(90, 92, 102, 255), width=4)
                # Spokes — THE aliasing showcase.
                for s_ in range(self.N_SPOKES):
                    a = wheel_rot + s_ * math.tau / self.N_SPOKES
                    d.line([wx_, y0,
                            wx_ + math.cos(a) * (self.WHEEL_R - 5),
                            y0 + math.sin(a) * (self.WHEEL_R - 5)],
                           fill=(120, 122, 132, 255), width=4)
                d.ellipse([wx_ - 6, y0 - 6, wx_ + 6, y0 + 6],
                          fill=(140, 142, 150, 255))
                cranks.append((wx_ + math.cos(wheel_rot) * 16,
                               y0 + math.sin(wheel_rot) * 16))
            # Coupling rod linking the cranks (classic loco motion).
            d.line(cranks, fill=(150, 152, 160, 255), width=6)
            for cx_, cy_ in cranks:
                d.ellipse([cx_ - 4, cy_ - 4, cx_ + 4, cy_ + 4],
                          fill=(190, 192, 200, 255))

        wheel_y = self.track_y - 4

        # Locomotive: armored nose + cab + funnel + headlight beam.
        lx0, lx1 = loco_x - 40, loco_x + 150
        d.polygon([(lx1, body_y + 50), (lx1 + 54, body_y + 50),
                   (lx1 + 54, body_y + 26), (lx1 + 20, body_y - 2),
                   (lx1, body_y - 2)], fill=GREEN_D)          # nose
        d.rounded_rectangle([lx0, body_y - 26, lx1, body_y + 50],
                            radius=10, fill=GREEN,
                            outline=GREEN_D, width=3)
        d.rectangle([lx0 + 12, body_y - 48, lx0 + 74, body_y - 22],
                    fill=GREEN, outline=GREEN_D, width=3)      # cab
        d.rectangle([lx0 + 22, body_y - 42, lx0 + 50, body_y - 28],
                    fill=(255, 224, 150, 230))                # cab window
        d.rectangle([lx1 - 36, body_y - 44, lx1 - 18, body_y - 24],
                    fill=GREEN_D)                              # funnel
        d.line([lx0, body_y + 20, lx1 + 40, body_y + 20],
               fill=GOLD, width=5)                             # gold stripe
        # Headlight + beam.
        d.ellipse([lx1 + 40, body_y + 6, lx1 + 56, body_y + 22],
                  fill=(255, 240, 190, 255))
        d.polygon([(lx1 + 52, body_y + 8), (lx1 + 52, body_y + 20),
                   (W + 80, body_y + 70), (W + 80, body_y - 60)],
                  fill=(255, 240, 190, 26))
        wheels(lx0, lx1, wheel_y)

        # Cars.
        for c_ in range(self.n_cars):
            cx0 = lx0 - (c_ + 1) * (car_w + gap2)
            cx1 = cx0 + car_w
            d.rounded_rectangle([cx0, body_y - 22, cx1, body_y + 50],
                                radius=10, fill=GREEN,
                                outline=GREEN_D, width=3)
            d.line([cx0, body_y + 20, cx1, body_y + 20],
                   fill=GOLD, width=5)
            # Lit windows with a slow flicker.
            for wn in range(4):
                wx_ = cx0 + 26 + wn * 46
                lit = math.sin(self.window_ph + c_ * 3 + wn
                               + t * 0.6) > -0.5
                d.rounded_rectangle(
                    [wx_, body_y - 12, wx_ + 26, body_y + 8], radius=4,
                    fill=(255, 224, 150, 230) if lit
                    else (40, 52, 48, 255))
            # Coupling to the next car.
            d.line([cx1, body_y + 30, cx1 + gap2, body_y + 30],
                   fill=(80, 82, 90, 255), width=6)
            wheels(cx0, cx1, wheel_y)

        # Speed lines once it's flying.
        if k > 0.45:
            for _ in range(int(10 * k)):
                ly = rng.uniform(H * 0.3, H * 0.85)
                ll = rng.uniform(50, 200) * k
                lx = rng.uniform(0, W)
                d.line([lx, ly, lx + ll, ly],
                       fill=(220, 225, 255, int(55 * k)), width=2)

        out = np.asarray(img, dtype=np.uint8)
        return self.lag(out, ts)

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
    "stacker": _Stacker,
    "fight": _Fight,
    "train": _Train,
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
