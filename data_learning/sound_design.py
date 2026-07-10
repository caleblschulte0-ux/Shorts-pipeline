#!/usr/bin/env python3
"""Ledger-driven sound design for long-form (CURIOSITY_BRAIN §7.5 v7).

The engine already KNOWS when everything happens — the ledger timestamps
every travel, payoff, discovery, cold open and exit — so sound design is
automatic, not authored:

    travel      -> whoosh          payoff     -> impact (deep)
    discovery   -> shimmer         cold open  -> riser
    exit        -> riser + impact

SFX volumes scale with the world's intensity level at that moment (also
in the ledger). The music bed runs under everything and is
SIDECHAIN-DUCKED by the narration — during breathing gaps it swells on
its own, no authoring.

Reuses the shorts pipeline's synthesized, license-free kit
(`studio_render._synth_sfx` / `_build_music`): drop real tracks into
`data_learning/music/<vibe>/*.mp3` and the same wiring upgrades the bed
(the operator's "revisit sounds later" path).
"""
from __future__ import annotations

from pathlib import Path

from data_learning.studio_render import _build_music, _run, _synth_sfx

# volumes are relative to the narration (post-mix loudnorm happens in
# _finish); long-form sits quieter than the shorts kit
VOLUMES = {"whoosh": 0.40, "impact": 0.50, "shimmer": 0.34, "riser": 0.50}


def _extra_sfx(work: Path) -> dict[str, Path]:
    """Long-form one-shots the shorts kit lacks (documentary weights)."""
    recipes = {
        "riser": ("anoisesrc=duration=3.2:color=pink:amplitude=0.5",
                  "highpass=f=120,lowpass=f=1100,"
                  "volume='0.06+0.8*t/3.2':eval=frame,afade=t=in:d=0.4"),
        "impact": ("aevalsrc='0.9*sin(2*PI*(150-90*min(t*6\\,1))*t)"
                   "*exp(-4.5*t)+0.5*sin(2*PI*52*t)*exp(-3.2*t)'"
                   ":d=1.1:s=44100",
                   "lowpass=f=2400"),
        "shimmer": ("aevalsrc='0.28*sin(2*PI*1245*t)*exp(-2.4*t)+"
                    "0.2*sin(2*PI*1865*t)*exp(-2.8*t)+"
                    "0.16*sin(2*PI*2490*t)*exp(-3.2*t)':d=1.6:s=44100",
                    "highpass=f=700"),
    }
    out: dict[str, Path] = {}
    for name, (src, af) in recipes.items():
        p = work / f"sfx_{name}.wav"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
               "-i", src]
        if af:
            cmd += ["-af", af]
        _run(cmd + [str(p)])
        out[name] = p
    return out


def _level_fn(rows):
    steps = sorted((r["t"], int(r.get("to", 0))) for r in rows
                   if r.get("kind") == "state"
                   and r.get("what") == "intensity")

    def lvl(t: float) -> int:
        cur = 0
        for st_t, st_lv in steps:
            if st_t <= t:
                cur = max(cur, st_lv)
        return cur
    return lvl


def build_soundtrack(ledger: dict, narration: Path, total: float,
                     work: Path, vibe: str, slug: str) -> Path:
    """narration + sidechain-ducked bed + ledger-placed SFX -> one wav."""
    music = work / "music_bed.wav"
    _build_music(total, music, vibe, slug)
    kit = {**_synth_sfx(work), **_extra_sfx(work)}
    rows = ledger.get("rows", [])
    lvl = _level_fn(rows)

    plays: list[tuple[float, Path, float]] = []

    def add(t, name, base):
        if 0 <= t < total - 0.3:
            plays.append((t, kit[name],
                          base * (0.85 + 0.12 * lvl(t))))

    seen_cold = False
    for r in rows:
        k, t = r.get("kind"), float(r.get("t", 0))
        if k == "cold_open" and not seen_cold:
            seen_cold = True
            add(t, "riser", VOLUMES["riser"])
        elif k == "travel":
            add(t, "whoosh", VOLUMES["whoosh"])
        elif k == "payoff":
            # payoff rows log at the END of their play — land the hit
            # slightly early so it reads as the cause, not the echo
            add(t - float(r.get("rt", 1.0)) * 0.5, "impact",
                VOLUMES["impact"])
        elif k == "discovery":
            add(t - float(r.get("rt", 1.0)), "shimmer",
                VOLUMES["shimmer"])
        elif k == "exit":
            add(t, "riser", VOLUMES["riser"] + 0.08)
            add(min(total - 1.5, t + 3.0), "impact",
                VOLUMES["impact"] + 0.05)

    out = work / "soundtrack.wav"
    inputs = ["-i", str(narration), "-i", str(music)]
    fc = [
        f"[1:a]volume=0.45,atrim=0:{total:.2f},"
        f"afade=t=out:st={max(0.0, total - 3):.2f}:d=3[mraw]",
        "[mraw][0:a]sidechaincompress=threshold=0.06:ratio=4:"
        "attack=80:release=500[duck]",
    ]
    labels = []
    for k, (t, f, vol) in enumerate(sorted(plays)):
        inputs += ["-i", str(f)]
        ms = max(0, int(t * 1000))
        fc.append(f"[{2 + k}:a]adelay={ms}|{ms},volume={vol:.2f}[s{k}]")
        labels.append(f"[s{k}]")
    if labels:
        fc.append("".join(labels)
                  + f"amix=inputs={len(labels)}:duration=longest:"
                    f"normalize=0,apad=whole_dur={total:.2f}[sfx]")
        fc.append("[0:a][duck][sfx]amix=inputs=3:duration=first:"
                  "normalize=0,alimiter=limit=0.95[a]")
    else:
        fc.append("[0:a][duck]amix=inputs=2:duration=first:normalize=0,"
                  "alimiter=limit=0.95[a]")
    _run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
          "-filter_complex", ";".join(fc),
          "-map", "[a]", "-ar", "44100", "-ac", "2",
          "-c:a", "pcm_s16le", str(out)])
    print(f"[sound] bed + {len(plays)} ledger-placed SFX mixed")
    return out
