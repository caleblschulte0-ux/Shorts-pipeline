"""The repost edit for a SAD moment: the picture goes grey and a sad piano
comes in under the voices.

Operator, 2026-10-09: *"oh play some gray, but do a gray overlay and do
that specific sad song whenever something sad happens ... we are not
following the game plan that all these other big channels ... follow"*.
The author says whether a clip has a sad turn and the second it lands
(`author` -> edit.mood / edit.mood_at); from that second the picture is
desaturated and the bed fades in, ducked under speech.

The music is SYNTHESISED here (an A-minor piano progression, Am F C G),
not a commercial track: the trending sad songs are under Content ID and a
claim takes the video's revenue or blocks it. Generated once per run into
cache/ (gitignored); nothing binary is committed.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BED = REPO / "cache" / "music" / "sad_piano_v1.wav"
RATE = 44100
MOODS = {"sad"}
BED_GAIN = 0.32            # under the voices, before ducking
GREY = "hue=s=0.08"        # nearly black-and-white, not fully

_A4 = 440.0
# Am - F - C - G, two bars each, as (bass, arpeggio) in semitones from A4
_PROG = [(-24, [0, 3, 7, 12]), (-28, [-4, 0, 3, 8]),
         (-21, [3, 7, 10, 15]), (-26, [-2, 2, 5, 10])]
_BEAT = 0.6                # seconds per arpeggio note (100 bpm)


def _note(semi: int, secs: float, amp: float):
    import numpy as np
    f = _A4 * 2 ** (semi / 12)
    t = np.arange(int(secs * RATE)) / RATE
    tone = sum(h * np.sin(2 * np.pi * f * k * t)
               for k, h in ((1, 1.0), (2, 0.42), (3, 0.18), (4, 0.08)))
    return amp * np.minimum(1.0, t / 0.008) * np.exp(-2.6 * t) * tone


def _synth():
    import numpy as np
    bar = 8 * _BEAT
    total = int(len(_PROG) * bar * RATE) + RATE * 3
    mix = np.zeros(total)

    def add(sig, at):
        s = int(at * RATE)
        n = min(len(sig), total - s)
        mix[s:s + n] += sig[:n]
    for ci, (bass, arp) in enumerate(_PROG):
        t0 = ci * bar
        for seg in (0, 4 * _BEAT):
            add(_note(bass, 3.0, 0.5), t0 + seg)
        for k in range(8):
            semi = arp[k % 4] if k < 4 else arp[3 - (k % 4)]
            add(_note(semi, 2.4, 0.3), t0 + k * _BEAT)
    # a little room: two feedback taps
    for d, g in ((int(0.083 * RATE), 0.28), (int(0.191 * RATE), 0.18)):
        for i in range(d, total, d):
            mix[i:i + d] += g * mix[i - d:i][:len(mix[i:i + d])]
    return mix / (np.abs(mix).max() or 1.0) * 0.85


def bed() -> Path:
    """The sad piano loop (~20s) as a WAV, made once."""
    if BED.exists() and BED.stat().st_size > 1000:
        return BED
    BED.parent.mkdir(parents=True, exist_ok=True)
    samples = _synth()
    tmp = BED.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        import numpy as np
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2")
                      .tobytes())
    tmp.replace(BED)
    return BED


def treatment(mood: str, at: float, dur: float) -> dict | None:
    """What the renderer applies, or None for no mood edit.
    {"vf": video filter, "at": start second, "fade": seconds}."""
    if str(mood or "").lower() not in MOODS or dur <= 1.0:
        return None
    at = max(0.0, min(float(at or 0.0), dur - 1.0))
    return {"mood": "sad", "at": round(at, 2),
            "vf": f"{GREY}:enable='gte(t,{at:.2f})'", "fade": 1.2}


def audio_graph(t: dict, voice: str, bed_in: str, dur: float,
                out: str) -> str:
    """filter_complex fragment: the bed starts at t["at"], fades in, is
    ducked by the voice, and is mixed under it."""
    at, fade = t["at"], t["fade"]
    ms = int(at * 1000)
    return (f"[{bed_in}]aloop=loop=-1:size=2147483647,atrim=0:{dur:.3f},"
            f"volume={BED_GAIN},afade=t=in:st=0:d={fade},"
            f"adelay={ms}|{ms},atrim=0:{dur:.3f},aformat=channel_layouts=stereo"
            f"[bedr];"
            f"[{voice}]asplit=2[vk][vm];"
            f"[bedr][vk]sidechaincompress=threshold=0.04:ratio=6:"
            f"attack=20:release=400[bedd];"
            f"[vm][bedd]amix=inputs=2:duration=first:normalize=0[{out}]")
