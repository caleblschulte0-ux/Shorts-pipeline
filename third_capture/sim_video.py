#!/usr/bin/env python3
"""Sim pillar renderer — full-frame themed_bottom worlds as Shorts.

Renders a procedural physics world (themed_bottom.py) at full 1080x1920,
overlays a live SPEED multiplier read from the SAME compounding formula
the sim itself runs on (truthful by construction), synthesizes an
accelerating pulse soundtrack from that formula too, and mixes optional
edge-tts hook/payoff voice lines.

The premise every video keeps: "this world gets faster every second —
watch how fast it ends." The number on screen IS the sim clock.
"""
from __future__ import annotations

import asyncio
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
SR = 44100
FONTS = Path("/usr/share/fonts/truetype/dejavu")

INK = (240, 246, 252)
YELLOW = (241, 196, 15)
GREEN = (63, 185, 80)


def F(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _sim_class(theme: str):
    import themed_bottom as tb
    return tb, tb._THEME_CLASSES[theme]


def speed_at(t: float, duration: float, growth: float) -> float:
    """The sim's own clock multiplier (themed_bottom.sim_scale formula)."""
    if not growth:
        return 1.0
    peak = growth ** 12.0
    return peak ** min(1.0, t / duration)


# ---------- overlays ----------

def _rounded(d, box, r, **kw):
    d.rounded_rectangle(box, radius=r, **kw)


def overlay(img: Image.Image, t: float, dur: float, growth: float,
            pkg: dict) -> Image.Image:
    d = ImageDraw.Draw(img, "RGBA")
    m = speed_at(t, dur, growth)

    # hook card, first ~3.2s, fades out
    if t < 3.2:
        a = int(255 * (1.0 if t < 2.6 else (3.2 - t) / 0.6))
        f = F("DejaVuSans-Bold.ttf", 72)
        lines = pkg["hook_lines"]
        ty = 210
        for ln in lines:
            tw = d.textlength(ln, font=f)
            _rounded(d, ((W - tw) / 2 - 28, ty - 8, (W + tw) / 2 + 28,
                         ty + 92), 24, fill=(0, 0, 0, min(200, a)))
            d.text(((W - tw) / 2, ty), ln, font=f,
                   fill=INK + (a,))
            ty += 108

    # live speed tag — the signature element (bottom, in safe area)
    f = F("DejaVuSans-Bold.ttf", 64)
    label = f"SPEED  x{m:.1f}"
    tw = d.textlength(label, font=f)
    frac = min(1.0, (m - 1) / (growth ** 12.0 - 1)) if growth else 0.0
    col = (int(241 * frac + 99 * (1 - frac)),
           int(196 * frac + 210 * (1 - frac)), 15)
    _rounded(d, ((W - tw) / 2 - 34, 1416, (W + tw) / 2 + 34, 1516), 26,
             fill=(0, 0, 0, 190), outline=col + (255,), width=5)
    d.text(((W - tw) / 2, 1428), label, font=f, fill=col + (255,))

    # payoff stamp, last 3.5s
    t_end = dur - 3.5
    if t >= t_end:
        k = min(1.0, (t - t_end) / 0.3)
        f2 = F("DejaVuSans-Bold.ttf", int(150 * (0.7 + 0.3 * k)))
        big = pkg["payoff_stamp"].format(peak=f"{growth ** 12.0:.1f}")
        tw = d.textlength(big, font=f2)
        _rounded(d, ((W - tw) / 2 - 44, 660, (W + tw) / 2 + 44, 880), 30,
                 fill=(0, 0, 0, 170), outline=GREEN + (255,), width=10)
        d.text(((W - tw) / 2, 690), big, font=f2, fill=GREEN + (255,))
        f3 = F("DejaVuSans-Bold.ttf", 56)
        nxt = pkg["escalation_line"]
        tw = d.textlength(nxt, font=f3)
        _rounded(d, ((W - tw) / 2 - 24, 930, (W + tw) / 2 + 24, 1020), 20,
                 fill=(0, 0, 0, 170))
        d.text(((W - tw) / 2, 944), nxt, font=f3, fill=INK + (255,))
    return img


# ---------- audio ----------

def synth_bed(dur: float, growth: float, out: Path) -> Path:
    """Accelerating pulse bed driven by the sim-speed formula: soft pad
    whose pitch eases up with the multiplier + a tick whose rate IS the
    multiplier. No external assets."""
    n = int(dur * SR)
    ts = np.arange(n) / SR
    m = np.array([speed_at(float(t), dur, growth) for t in ts[::441]])
    m = np.repeat(m, 441)[:n]                      # 100Hz control rate
    # pad: two detuned saw-ish sines, pitch rises ~1 octave across clip
    f0 = 82.0 * (1.0 + (m - 1) / (growth ** 12.0 - 1 + 1e-9))
    phase = np.cumsum(2 * np.pi * f0 / SR)
    pad = 0.16 * np.sin(phase) + 0.10 * np.sin(phase * 1.503)
    pad *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.23 * ts) ** 2   # slow swell
    # ticks: schedule by integrating the multiplier
    tick = np.zeros(n)
    t_next, base_iv = 0.6, 0.62
    while t_next < dur - 0.2:
        i0 = int(t_next * SR)
        L = min(int(0.05 * SR), n - i0)
        env = np.exp(-np.linspace(0, 9, L))
        freq = 660.0
        tick[i0:i0 + L] += 0.22 * env * np.sin(
            2 * np.pi * freq * np.arange(L) / SR)
        t_next += base_iv / speed_at(t_next, dur, growth)
    sig = pad + tick
    # gentle fade in/out
    fade = int(0.4 * SR)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    sig = np.clip(sig, -0.95, 0.95)
    with wave.open(str(out), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())
    return out


async def _tts(text: str, out: Path, voice: str) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate="+8%").save(str(out))


# ---------- main ----------

def compose_sim(pkg: dict, out_path: Path) -> dict:
    """Render the sim world full-frame with overlays + audio. Returns the
    sim ledger (what actually ran — theme, seed, growth, peak)."""
    spec = pkg["capture"]
    theme, seed = spec["theme"], int(spec["seed"])
    dur = float(spec["duration"])

    tb, cls = _sim_class(theme)
    oldWH = tb.W, tb.H
    tb.W, tb.H = W, H
    try:
        inst = cls(seed)
        growth = float(getattr(inst, "GROWTH", 0.0))
        # same arc setup as themed_bottom.render(): one full-clip ramp
        inst.duration = dur
        if growth:
            inst._peak_scale = growth ** 12.0
        if getattr(inst, "CYCLE", 0.0):
            inst.CYCLE = max(2.0, dur)

        ledger = {
            "kind": "sim", "theme": theme, "seed": seed,
            "duration_s": dur, "growth_per_s": growth,
            "peak_multiplier": round(growth ** 12.0, 2) if growth else 1.0,
            "notes": "speed overlay + audio derive from the sim's own "
                     "sim_scale formula (peak**(t/duration))",
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bed = synth_bed(dur, growth, tmp / "bed.wav")
            # ffmpeg input 0 = the raw video pipe; audio inputs start at 1
            inputs = ["-i", str(bed)]
            delays, idx = [], 2
            voice = pkg.get("voice", "en-US-ChristopherNeural")
            for key, at in (("hook", 0.3), ("payoff", dur - 3.3)):
                line = pkg["script"].get(key)
                if not line:
                    continue
                p = tmp / f"vo_{key}.mp3"
                asyncio.run(_tts(line.format(
                    peak=f"{growth ** 12.0:.1f}"), p, voice))
                inputs += ["-i", str(p)]
                ms = int(at * 1000)
                delays.append(f"[{idx}:a]adelay={ms}|{ms}[v{idx}]")
                idx += 1
            tags = "[1:a]" + "".join(f"[v{i}]" for i in range(2, idx))
            fc = ";".join(delays + [
                f"{tags}amix=inputs={idx - 1}:normalize=0[out]"])

            enc = subprocess.Popen(
                ["ffmpeg", "-y", "-v", "error",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                 "-r", str(FPS), "-i", "-", *inputs,
                 "-filter_complex", fc, "-map", "0:v", "-map", "[out]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                 "-t", f"{dur}", str(out_path)], stdin=subprocess.PIPE)
            n = int(dur * FPS)
            for i in range(n):
                t = i / FPS
                frame = inst.draw(t, i)
                frame = inst._pop(frame)
                img = Image.fromarray(frame)
                img = overlay(img, t, dur, growth, pkg)
                enc.stdin.write(np.asarray(img)[:, :, :3].tobytes())
            enc.stdin.close()
            enc.wait()
            if enc.returncode:
                raise RuntimeError("ffmpeg encode failed")
    finally:
        tb.W, tb.H = oldWH
    print(f"[sim] wrote {out_path} ({theme}, x{ledger['peak_multiplier']})")
    return ledger
