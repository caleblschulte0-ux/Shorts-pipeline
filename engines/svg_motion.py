"""svg_motion — animated vector renders: per-frame SVG -> PNG -> mp4.

Why this exists: the ChatGPT integration experiments proved that crisp
animated vector graphics (title cards, diagrams, funnels, stat pops) are a
strong Shorts visual — and that authoring them as SVG TEXT is something any
LLM brain in this pipeline does well. This engine makes that a first-class,
dependency-light capability no external service is needed for.

How it works (and one honest limitation): cairosvg rasterizes STATIC svg —
SMIL/CSS animations are ignored. So this engine animates by interpolation:
the caller supplies ``frame_fn(t)`` returning the full SVG document for
normalized time t in [0, 1]; we rasterize every frame and assemble with
ffmpeg. Deterministic, CPU-cheap (~1080x1920@30fps renders faster than
realtime for typical vector scenes).

Contract (engines standard): ``available()`` offline; ``maybe_svg_motion``
returns the output Path or None, never raises.

    from engines.svg_motion import maybe_svg_motion, title_card, ease

    fn = title_card("TAX SEASON", "3 things nobody tells you")
    maybe_svg_motion(fn, "out.mp4", duration=2.5, fps=30)

    # or fully custom:
    def fn(t):
        y = ease.out_cubic(t) * 400
        return f'<svg xmlns="http://www.w3.org/2000/svg" ...>{...}</svg>'
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def available() -> bool:
    """Offline + deterministic: cairosvg importable, ffmpeg on PATH."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        import cairosvg  # noqa: F401
        return True
    except Exception:
        return False


class ease:
    """Easing helpers for frame functions (t in [0,1] -> [0,1])."""

    @staticmethod
    def linear(t: float) -> float:
        return max(0.0, min(1.0, t))

    @staticmethod
    def out_cubic(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 3

    @staticmethod
    def in_out(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    @staticmethod
    def pop(t: float, overshoot: float = 1.12) -> float:
        """Scale-in with a small overshoot then settle — the stat-pop feel."""
        t = max(0.0, min(1.0, t))
        if t < 0.7:
            return ease.out_cubic(t / 0.7) * overshoot
        return overshoot + (1.0 - overshoot) * ease.in_out((t - 0.7) / 0.3)


def interp(a: float, b: float, t: float, fn=ease.linear) -> float:
    return a + (b - a) * fn(t)


def seg(t: float, start: float, end: float) -> float:
    """Re-normalize global t to a sub-window [start, end] (clamped 0..1) —
    lets one frame_fn run several staggered animations."""
    if end <= start:
        return 1.0
    return max(0.0, min(1.0, (t - start) / (end - start)))


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def title_card(title: str, subtitle: str = "", *, width: int = 1080,
               height: int = 1920, bg: str = "#0b0b0f",
               fg: str = "#ffffff", accent: str = "#ff7a00"):
    """Built-in frame function: title rises+fades in, accent rule draws on,
    subtitle follows. The house style of the funnel sketch: bold on dark."""
    t_esc, s_esc = _esc(title), _esc(subtitle)
    cx = width // 2

    def frame(t: float) -> str:
        a1 = ease.out_cubic(seg(t, 0.00, 0.45))          # title
        a2 = ease.out_cubic(seg(t, 0.25, 0.70))          # rule draw-on
        a3 = ease.out_cubic(seg(t, 0.40, 0.85))          # subtitle
        ty = interp(height * 0.50, height * 0.44, a1)
        rule_w = interp(0, width * 0.62, a2)
        sy = interp(height * 0.56, height * 0.52, a3)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  <text x="{cx}" y="{ty:.1f}" fill="{fg}" fill-opacity="{a1:.3f}"
        font-family="DejaVu Sans" font-weight="bold" font-size="96"
        text-anchor="middle">{t_esc}</text>
  <rect x="{cx - rule_w / 2:.1f}" y="{height * 0.47:.0f}" width="{rule_w:.1f}"
        height="10" rx="5" fill="{accent}"/>
  <text x="{cx}" y="{sy:.1f}" fill="{fg}" fill-opacity="{a3 * 0.85:.3f}"
        font-family="DejaVu Sans" font-size="52"
        text-anchor="middle">{s_esc}</text>
</svg>'''
    return frame


def stat_pop(value: str, label: str = "", **kw):
    """Built-in frame function: a big number pops in over a label."""
    width = kw.get("width", 1080)
    height = kw.get("height", 1920)
    bg = kw.get("bg", "#0b0b0f")
    accent = kw.get("accent", "#ff7a00")
    fg = kw.get("fg", "#ffffff")
    v_esc, l_esc = _esc(value), _esc(label)
    cx, cy = width // 2, int(height * 0.46)

    def frame(t: float) -> str:
        s = ease.pop(seg(t, 0.0, 0.6))
        a = ease.out_cubic(seg(t, 0.35, 0.8))
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  <g transform="translate({cx} {cy}) scale({max(s, 0.001):.4f})">
    <text x="0" y="0" fill="{accent}" font-family="DejaVu Sans"
          font-weight="bold" font-size="200" text-anchor="middle">{v_esc}</text>
  </g>
  <text x="{cx}" y="{cy + 130}" fill="{fg}" fill-opacity="{a:.3f}"
        font-family="DejaVu Sans" font-size="56"
        text-anchor="middle">{l_esc}</text>
</svg>'''
    return frame


def maybe_svg_motion(frame_fn, out_path, *, duration: float = 3.0,
                     fps: int = 30, width: int = 1080, height: int = 1920,
                     timeout: int = 600) -> Path | None:
    """Render frame_fn(t) for t in [0,1] to an mp4. Path on success, None on
    ANY failure (missing deps, bad SVG, ffmpeg error) — never raises."""
    try:
        if not available():
            return None
        import cairosvg

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        n = max(2, int(round(duration * fps)))
        with tempfile.TemporaryDirectory(prefix="svgmotion_") as td:
            for i in range(n):
                t = i / (n - 1)
                svg = frame_fn(t)
                if not svg or "<svg" not in svg:
                    return None
                cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                                 write_to=f"{td}/f_{i:05d}.png",
                                 output_width=width, output_height=height)
            run = subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-framerate", str(fps), "-i", f"{td}/f_%05d.png",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-preset", "veryfast", "-crf", "19", str(out_path)],
                capture_output=True, text=True, timeout=timeout)
        if run.returncode == 0 and out_path.exists() and out_path.stat().st_size:
            return out_path
        return None
    except Exception:
        return None
