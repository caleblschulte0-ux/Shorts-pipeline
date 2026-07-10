#!/usr/bin/env python3
"""Synthesize the channel's impact SFX one-shots (self-authored = CC0).

Generates whoosh / boom / riser / pop 48kHz mono WAVs with numpy — no
external samples, so there is zero licensing risk on the clip channel.
Re-run to regenerate; the committed .wav files are what the renderer uses.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000


def _write(name: str, sig: np.ndarray) -> None:
    sig = np.clip(sig, -1.0, 1.0)
    # short fade in/out so nothing clicks
    n = len(sig)
    f = min(int(0.004 * SR), n // 2)
    if f:
        sig[:f] *= np.linspace(0, 1, f)
        sig[-f:] *= np.linspace(1, 0, f)
    pcm = (sig * 32767).astype(np.int16)
    with wave.open(str(HERE / name), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {name} ({n/SR:.2f}s)")


def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(dur * SR), endpoint=False)


def whoosh() -> None:
    """Filtered-noise swish for punch-in zooms. ~0.35s, rising then falling."""
    t = _t(0.35)
    noise = np.random.default_rng(1).standard_normal(len(t))
    # one-pole lowpass sweeping up then down (band feel) via cumulative smoothing
    env = np.clip(np.sin(np.pi * t / t[-1]), 0, None) ** 1.5   # bell envelope
    # pitch-ish coloring: multiply noise by a sweeping sine band
    sweep = np.sin(2 * np.pi * (400 + 3000 * env) * t)
    sig = 0.6 * noise * env * (0.4 + 0.6 * (sweep * 0.5 + 0.5))
    _write("whoosh.wav", 0.5 * sig / (np.max(np.abs(sig)) + 1e-9))


def boom() -> None:
    """Sub-heavy impact for the peak hit. ~0.5s, pitched-down thump + click."""
    t = _t(0.5)
    f0 = 120 * np.exp(-6 * t)                        # pitch drops fast
    phase = 2 * np.pi * np.cumsum(f0) / SR
    body = np.sin(phase) * np.exp(-7 * t)
    click = (np.random.default_rng(2).standard_normal(len(t))
             * np.exp(-120 * t) * 0.5)
    sig = 0.9 * body + 0.3 * click
    _write("boom.wav", sig / (np.max(np.abs(sig)) + 1e-9))


def riser() -> None:
    """Tension riser leading into a reveal. ~0.8s, pitch + noise crescendo."""
    t = _t(0.8)
    env = (t / t[-1]) ** 2
    tone = np.sin(2 * np.pi * (200 + 1200 * env) * t) * env
    noise = (np.random.default_rng(3).standard_normal(len(t))
             * env * 0.5)
    sig = 0.7 * tone + 0.3 * noise
    _write("riser.wav", 0.6 * sig / (np.max(np.abs(sig)) + 1e-9))


def pop() -> None:
    """Tiny UI pop for caption emphasis. ~0.09s."""
    t = _t(0.09)
    sig = np.sin(2 * np.pi * 900 * t) * np.exp(-40 * t)
    _write("pop.wav", 0.5 * sig / (np.max(np.abs(sig)) + 1e-9))


if __name__ == "__main__":
    whoosh(); boom(); riser(); pop()
