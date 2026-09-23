#!/usr/bin/env python3
"""Studio renderer — the data channel's own production renderer.

Renders a STORY: a punchy hook, then several *distinct* charts (each from its
own data pull) that build a narrative, then a sources card. Over the top: a
calming flowing-bokeh background, a humanoid mascot host that points at the
data, the pipeline's Kokoro voice, and burned kinetic captions + punch
stingers.

It is an add-on — it imports from data_learning and reuses the base
pipeline's Kokoro model files, but never modifies any base module.

Usage:
    python -m data_learning.studio_render --slug us-economy-squeeze \
        --out output/economy_story.mp4
"""
from __future__ import annotations

import argparse
import hashlib as _hashlib
import json
import math
import re
import sys
import tempfile
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from shared import look as _look                                  # noqa: E402
from data_learning import ambient, charts, mascot, story           # noqa: E402
from data_learning.demo_render import (                            # noqa: E402
    _ass_time, _chunks, _dur, _hex_to_ass, _run)

W, H, FPS = 1080, 1920, 30
KOKORO_MODEL = REPO / "kokoro_models" / "kokoro-v1.0.onnx"
KOKORO_VOICES = REPO / "kokoro_models" / "voices-v1.0.bin"

# Layout (1080x1920): the chart is BIG (data is the focus) across the top
# ~60%; a strip of oddly-satisfying process footage fills the bottom. A
# pulsing marker lands on each spoken number and the mascot tucks beside it.
CHART_PNG_W = int(charts.SERIES_W * charts.SERIES_DPI)   # 1100
CHART_PNG_H = int(charts.SERIES_H * charts.SERIES_DPI)   # 1232
CHART_X, CHART_Y = 12, 26
CHART_W = 1056
CHART_H = round(CHART_W * CHART_PNG_H / CHART_PNG_W)      # keep aspect
SCALE_X = CHART_W / CHART_PNG_W
SCALE_Y = CHART_H / CHART_PNG_H

FOOT_Y = CHART_Y + CHART_H + 10
FOOT_H = (H - FOOT_Y) & ~1       # keep even (yuv420p / filter sizing)

# Chart kinds that composite the host directly into the chart PNG (Data rides
# the animated element). The travelling overlay is hidden on these beats.
HOST_BAKED_KINDS = ("fill_vessel", "bignum", "timeline")
# Card chart kinds that now BAKE the host into their frames (charts._bake_host):
# Data is drawn inside the chart riding/pushing/building the data, so the
# travelling overlay must be suppressed for these beats — keyed by KIND so it's
# robust regardless of when the host_baked flag propagates.
BAKED_CHART_KINDS = frozenset({
    "trend", "timeline", "pictorial_race", "rank", "comparison", "bars",
    "waffle_grid", "share", "pictograph", "stack",
    # geo beats bake the host too (winning bar tip / winning pin) — before
    # 2026-08-24 they relied on the host_baked flag alone, and geo_city had
    # no bake at all, so the travelling overlay drifted over the map.
    "geo_us", "geo_world", "geo_city"})


def _kind_bakes(kind: str | None) -> bool:
    """Does a visual of this kind draw Data INSIDE itself?

    The charts do (`charts._bake_host`). The brain-authored `mechanic`, and
    the `scene`/`diorama` it falls back to, draw exactly what their code says
    and nothing else — so a beat showing one of those needs the travelling
    overlay, or the mascot is absent from the frame entirely.
    """
    return bool(kind) and (kind in BAKED_CHART_KINDS or kind in HOST_BAKED_KINDS)


def _seg_is_baked(seg) -> bool:
    return (getattr(seg, "kind", "") in BAKED_CHART_KINDS
            or getattr(seg, "kind", "") in HOST_BAKED_KINDS
            or getattr(seg, "host_baked", False)
            or getattr(getattr(seg, "insight", None), "host_baked", False))


def _span_bakes(sp: dict) -> bool:
    """Did THIS rendered span draw Data inside itself?

    Two sources of truth, and the second is the one that was missing. A chart
    KIND bakes him by construction (`_kind_bakes`). A `scene` span bakes him
    only when the scene it drew is one of the self-hosting DATA MACHINES
    (`viz_scene._SELF_HOSTING`) — the renderer says so by setting
    `insight.host_baked` while it draws, and the span loop records that
    answer on the span as `host_baked` the moment the span finishes.

    THE SECOND DATA WITH THE CLIPBOARD. `invasive-species-price-tag`,
    2026-09-21, held at 48 twice: "a SECOND copy of Data is composited in
    the lower third holding a clipboard in an identical arm-out pose in every
    frame from seg1:start (t=4.32s) through payoff (t=36.13s) — he never
    moves, never touches a stat, and covers the caption line". The
    trajectory machine drew Data on its tip, the segment was rightly marked
    baked, the overlay for it was rightly hidden — and then the GAP-FILLER,
    which trusted only chart kinds, saw a `scene` span, called it unbaked,
    and parked the home host over the whole beat. `fusion-net-energy-gain`
    was blocked on "two mascots on screen" the same way. A flag set on the
    INSIGHT cannot answer a per-span question, so the answer is recorded
    per span.
    """
    return bool(sp.get("host_baked")) or _kind_bakes(sp.get("kind"))


def baked_spans_of(segments, disp_start: dict, disp_end: dict) -> list:
    """Time ranges where something on screen already draws Data — the ranges
    the travelling/gap-fill overlay must leave alone. Per SPAN when the
    segment rendered spans; the segment's own verdict only as a fallback for
    a story read before render (`spans` does not exist yet)."""
    out = []
    for i, seg in enumerate(segments):
        sp = getattr(seg, "spans", None) or []
        if sp:
            out += [(x["t0"], x["t1"]) for x in sp if _span_bakes(x)]
        elif _seg_is_baked(seg) and i in disp_start:
            out.append((disp_start[i], disp_end[i]))
    return out


def fully_baked(segments) -> bool:
    """Does EVERY visual in the story draw Data itself? Then the overlay adds
    nothing at all — otherwise the home host parks at bottom-centre through
    the hook/payoff windows as a second, pixel-identical Data."""
    allsp = [x for s in segments for x in (getattr(s, "spans", None) or [])]
    if allsp:
        return all(_span_bakes(x) for x in allsp)
    return bool(segments) and all(_seg_is_baked(s) for s in segments)

MASCOT_SIZE = 520                # the brand's face — the lead, a big central presence
SIDE_ANGLE = 16                  # near-horizontal point (toward a number beside it)
UP_ANGLE = 90                    # points up (hook / closing / fallback)
MASCOT_HOME = ((W - MASCOT_SIZE) // 2, 520)   # hook / closing rest spot
PUNCH_X, PUNCH_Y = 540, FOOT_Y + FOOT_H // 2
CAP_MARGINV = 70

# Voice: a friendly male Kokoro voice at natural pitch (not deep/scary).
VOICE_PITCH = 1.0

# Per-video THEME. Every story gets a different palette, background gradient,
# bokeh layout, and narrator voice (picked deterministically from the slug), so
# uploads don't look/sound like the same template stamped out over and over —
# which is what trips TikTok's "unoriginal / spam" filter on faceless channels.
# THE THEME NO LONGER CARRIES COLOUR.
#
# It used to, and that is where the design system died. `shared/look.py` is
# the one place a colour is decided, `charts.py` derives every token from it
# — and then `render()` did this, six lines in:
#
#     charts.HIGHLIGHT, charts.ACCENT, charts.WARN = (
#         theme["highlight"], theme["accent"], theme["warn"])
#
# ...throwing the whole chain away and substituting one of six hardcoded
# triples picked by an MD5 of the slug. Both paths inherit it: the charts
# through those module globals, and the 42 machines through the same
# globals, so ONE assignment decided the colour of every picture the channel
# draws. Rendered on 2026-09-10, the ozone story came out in teal and blue
# with a gold design system sitting unused one import away.
#
# Per-video variety was the right instinct and it is kept — `look.accent_for`
# is deterministic per slug and exists for exactly this. What the theme keeps
# is the variety that is NOT colour: the voice, the music bed, the bokeh
# seed. (`grad` survives only for `LEGACY_LOOK=1`; the CLEAN ground is a
# fixed editorial slate.)
THEMES = [
    dict(grad=("0x080A14", "0x0e2444", "0x175852", "0x0a0e20"),
         seed=7, voice="am_fenrir", vibe="calm"),
    dict(grad=("0x0c0814", "0x241040", "0x3a1763", "0x120a20"),
         seed=13, voice="am_michael", vibe="dark"),
    dict(grad=("0x141005", "0x3a2410", "0x4e3417", "0x1a1408"),
         seed=21, voice="bm_george", vibe="cinematic"),
    dict(grad=("0x07140e", "0x0e3a2a", "0x175852", "0x0a201a"),
         seed=29, voice="am_adam", vibe="pulse"),
    dict(grad=("0x140810", "0x40102a", "0x5a1740", "0x200a18"),
         seed=37, voice="bm_lewis", vibe="dark"),
    dict(grad=("0x06101e", "0x102044", "0x174a72", "0x0a1428"),
         seed=43, voice="am_fenrir", vibe="cinematic"),
]


def _hex(rgb) -> str:
    """`look`'s tuples -> the hex strings `charts` and libass both want."""
    return charts._hex(rgb)


def _theme_for(slug: str) -> dict:
    import hashlib
    h = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    return THEMES[h % len(THEMES)]


# --------------------------------------------------------------------------
# Soundtrack — the thing that separates "slideshow" from "produced video".
# A subtle per-theme music bed ducked under the voice, plus SFX synced to
# the visuals: a whoosh when each chart sweeps in, a color-keyed tick when
# the ring lands on a number, a pop when the closing bubble appears.
# --------------------------------------------------------------------------
_VIBES = {
    # Gentle pad + slow heartbeat kick — the default teaching vibe.
    "calm": dict(
        drone="0.22*sin(2*PI*98*t)+0.10*sin(2*PI*196*t)",
        kick="0.30*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.12*sin(2*PI*294*t)*sin(2*PI*0.1*t)"),
    # Sub drone + 90bpm pulse — for the doom-ier money topics.
    "dark": dict(
        drone="0.26*sin(2*PI*55*t)+0.14*sin(2*PI*110*t)",
        kick="0.40*sin(2*PI*58*t)*exp(-7*mod(t,0.667))",
        pad="0.10*sin(2*PI*220*t)*sin(2*PI*0.125*t)"),
    # Low swell, sparse 60bpm pulse — space/nature awe.
    "cinematic": dict(
        drone="0.26*sin(2*PI*49*t)+0.10*sin(2*PI*98*t)",
        kick="0.34*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.10*sin(2*PI*196*t)*sin(2*PI*0.0625*t)"),
    # Brighter 120bpm tick — tech/behavior energy.
    "pulse": dict(
        drone="0.18*sin(2*PI*82*t)",
        kick="0.38*sin(2*PI*65*t)*exp(-9*mod(t,0.5))",
        pad="0.09*sin(2*PI*330*t)*sin(2*PI*0.2*t)"),
}


def _synth_music(total: float, out: Path, vibe: str) -> None:
    v = _VIBES.get(vibe, _VIBES["calm"])
    d = max(8.0, total + 1.0)
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-f", "lavfi", "-i", f"aevalsrc='{v['drone']}':d={d}:s=44100",
          "-f", "lavfi", "-i", f"aevalsrc='{v['kick']}':d={d}:s=44100",
          "-f", "lavfi", "-i", f"aevalsrc='{v['pad']}':d={d}:s=44100",
          "-filter_complex",
          "[0][1][2]amix=inputs=3:duration=longest:weights=1 1.3 0.6,"
          "highpass=f=30,lowpass=f=3500,"
          "acompressor=threshold=0.4:ratio=4[m]",
          "-map", "[m]", "-ac", "2", "-ar", "44100",
          "-c:a", "pcm_s16le", str(out)])


def _synth_sfx(work: Path) -> dict[str, Path]:
    """Small synthesized one-shot library (no asset files needed)."""
    recipes = {
        # Chart sweep-in: short filtered noise whoosh.
        "whoosh": ("anoisesrc=duration=0.22:color=brown:amplitude=0.6",
                   "highpass=f=400,lowpass=f=6000,volume=0.6"),
        # Ring lands on a number — tone keyed to the punch color.
        "pos": ("aevalsrc='0.45*sin(2*PI*880*t)*exp(-8*t)+"
                "0.25*sin(2*PI*1320*t)*exp(-10*t)':d=0.35:s=44100",
                "highpass=f=400,lowpass=f=8000"),
        "warn": ("aevalsrc='0.5*sin(2*PI*420*t)*exp(-7*t)+"
                 "0.3*sin(2*PI*660*t)*exp(-10*t)':d=0.33:s=44100",
                 "highpass=f=200,lowpass=f=5000"),
        "shock": ("aevalsrc='0.8*sin(2*PI*40*t)*exp(-5*t)+"
                  "0.45*sin(2*PI*55*t)*exp(-8*t)':d=0.40:s=44100",
                  "highpass=f=25,lowpass=f=2200"),
        "money": ("aevalsrc='0.4*sin(2*PI*1480*t)*exp(-12*t)+"
                  "0.28*sin(2*PI*2100*t)*exp(-14*t)+"
                  "0.4*sin(2*PI*1480*(t-0.095))*exp(-12*(t-0.095))*gt(t,0.095)':"
                  "d=0.4:s=44100",
                  "highpass=f=600"),
        "neutral": ("aevalsrc='0.6*sin(2*PI*70*t)*exp(-10*t)+"
                    "0.3*sin(2*PI*45*t)*exp(-6*t)':d=0.30:s=44100", None),
        # Closing bubble pops in.
        "pop": ("aevalsrc='0.5*sin(2*PI*620*t)*exp(-9*t)+"
                "0.3*sin(2*PI*930*t)*exp(-12*t)':d=0.30:s=44100",
                "highpass=f=300"),
    }
    sfx: dict[str, Path] = {}
    for name, (src, af) in recipes.items():
        p = work / f"sfx_{name}.wav"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src]
        if af:
            cmd += ["-af", af]
        _run(cmd + [str(p)])
        sfx[name] = p
    return sfx


MUSIC_DIR = PKG_DIR / "music"


def _music_track(vibe: str, slug: str) -> Path | None:
    """A real royalty-free track for this vibe (rotated by slug), or None to
    fall back to the synthesized bed. Populated by scripts/fetch_music.py."""
    import hashlib
    d = MUSIC_DIR / vibe
    files = sorted(d.glob("*.mp3")) if d.is_dir() else []
    if not files:
        # try any vibe so a partial library still gives real music
        files = sorted(MUSIC_DIR.glob("*/*.mp3")) if MUSIC_DIR.is_dir() else []
    if not files:
        return None
    h = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    return files[h % len(files)]


def _build_music(total: float, out: Path, vibe: str, slug: str) -> None:
    """Real looped track (loudness-normalized so it's consistently present),
    else the synthesized fallback."""
    trk = _music_track(vibe, slug)
    if trk:
        _run(["ffmpeg", "-y", "-loglevel", "error",
              "-stream_loop", "-1", "-i", str(trk), "-t", f"{total + 1:.2f}",
              "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=30,lowpass=f=14000",
              "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(out)])
        return
    _synth_music(total, out, vibe)


def _build_soundtrack(narration: Path, windows, events, total: float,
                      vibe: str, work: Path, slug: str = "") -> Path:
    """Mix narration + ducked music bed + visual-synced SFX into one track."""
    music = work / "music.wav"
    _build_music(total, music, vibe, slug)
    sfx = _synth_sfx(work)

    # (time, file, volume) placements.
    plays: list[tuple[float, Path, float]] = []
    for i in range(1, len(windows) - 1):              # each chart sweeps in
        plays.append((windows[i][0], sfx["whoosh"], 0.7))
    for e in events:                                  # ring lands on a number
        p = e["punch"]
        c = (p.get("color") or "").lower()
        if "$" in p.get("text", ""):
            f = sfx["money"]
        elif c == "#ff3030":
            f = sfx["shock"]
        elif c == "#ffaa30":
            f = sfx["warn"]
        elif c == "#50ff80":
            f = sfx["pos"]
        else:
            f = sfx["neutral"]
        plays.append((e["ps"], f, 0.45))
    plays.append((windows[-1][0], sfx["pop"], 0.8))   # closing bubble

    out = work / "soundtrack.wav"
    inputs = ["-i", str(narration), "-i", str(music)]
    fc = [
        # Music sits low and ducks further whenever the voice speaks.
        # Louder, more present bed; the gentler duck keeps it audible under
        # the voice instead of crushing it to nothing.
        # Bed is loudness-normalized to -16 LUFS (same as the voice), so it's
        # loud and present; it sits just under and ducks while the voice talks.
        f"[1:a]volume=0.45,atrim=0:{total:.2f}[mraw]",
        "[mraw][0:a]sidechaincompress=threshold=0.06:ratio=4:"
        "attack=80:release=400[duck]",
    ]
    labels = []
    for k, (t, f, vol) in enumerate(plays):
        inputs += ["-i", str(f)]
        ms = max(0, int(t * 1000))
        fc.append(f"[{2 + k}:a]adelay={ms}|{ms},volume={vol:.2f}[s{k}]")
        labels.append(f"[s{k}]")
    if labels:
        fc.append("".join(labels) +
                  f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
                  f"apad=whole_dur={total:.2f}[sfx]")
        fc.append("[0:a][duck][sfx]amix=inputs=3:duration=first:normalize=0,"
                  "alimiter=limit=0.95[a]")
    else:
        fc.append("[0:a][duck]amix=inputs=2:duration=first:normalize=0,"
                  "alimiter=limit=0.95[a]")
    _run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
          "-filter_complex", ";".join(fc),
          "-map", "[a]", "-ar", "44100", "-ac", "2",
          "-c:a", "pcm_s16le", str(out)])
    return out

# Oddly-satisfying b-roll for the bottom strip. If broll/styles/*.mp4 exist
# (built by broll_gen.py --styles) the renderer round-robins through them so
# each video gets a different style; otherwise it falls back to the single
# broll/satisfying.mp4, then to a soft mandelbrot.
BROLL = PKG_DIR / "broll" / "satisfying.mp4"
BROLL_STYLES = PKG_DIR / "broll" / "styles"
BROLL_OFFSET = PKG_DIR / "broll" / ".offset"
BROLL_ROTATION = PKG_DIR / "broll" / ".rotation"


def _pick_broll(total: float):
    """Round-robin style selection. Returns (path, start_offset) or
    (None, 0.0) if no b-roll is available. A persisted counter advances each
    render: every video steps to the next style, and each full lap shifts the
    start offset so a repeated style never shows the exact same footage."""
    clips = sorted(BROLL_STYLES.glob("*.mp4")) if BROLL_STYLES.is_dir() else []
    if clips:
        try:
            n = int(BROLL_ROTATION.read_text().strip())
        except Exception:  # noqa: BLE001
            n = 0
        chosen = clips[n % len(clips)]
        dur = max(1.0, _dur(chosen))
        off = ((n // len(clips)) * max(total, 11.0)) % dur
        return chosen, off
    if BROLL.exists():
        dur = max(1.0, _dur(BROLL))
        try:
            off = float(BROLL_OFFSET.read_text().strip()) % dur
        except Exception:  # noqa: BLE001
            off = 0.0
        return BROLL, off
    return None, 0.0


def _advance_broll(total: float) -> None:
    """Step the rotation counter / offset for the next render."""
    if BROLL_STYLES.is_dir() and any(BROLL_STYLES.glob("*.mp4")):
        try:
            n = int(BROLL_ROTATION.read_text().strip())
        except Exception:  # noqa: BLE001
            n = 0
        BROLL_ROTATION.write_text(f"{n + 1}\n")
    elif BROLL.exists():
        dur = max(1.0, _dur(BROLL))
        try:
            off = float(BROLL_OFFSET.read_text().strip())
        except Exception:  # noqa: BLE001
            off = 0.0
        BROLL_OFFSET.write_text(f"{(off + total) % dur:.2f}\n")


# --------------------------------------------------------------------------
# Kokoro narration (the pipeline voice).
# --------------------------------------------------------------------------
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _card(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        r = n % 100
        return _ONES[n // 100] + " hundred" + (" " + _card(r) if r else "")
    r = n % 1000
    return _card(n // 1000) + " thousand" + (" " + _card(r) if r else "")


def _year(n: int) -> str:
    if 2000 <= n <= 2009:
        return "two thousand" + (" " + _ONES[n % 10] if n % 10 else "")
    hi, lo = n // 100, n % 100
    if lo == 0:
        return _card(hi) + " hundred"
    if lo < 10:
        return _card(hi) + " oh " + _ONES[lo]
    return _card(hi) + " " + _card(lo)


def _spell_numbers(text: str) -> str:
    """Spell every number out in words so the TTS pronounces it correctly
    (e.g. '5.3' -> 'five point three', '2023' -> 'twenty twenty three').
    Applied to the spoken audio ONLY — captions keep the digits."""
    def _dec(m):
        whole, frac = m.group(0).split(".")
        return (_card(int(whole)) + " point "
                + " ".join(_ONES[int(d)] for d in frac))
    text = re.sub(r"\d+\.\d+", _dec, text)

    def _int(m):
        n = int(m.group(0))
        return _year(n) if 1900 <= n <= 2099 else _card(n)
    return re.sub(r"\d+", _int, text)


def _say_num(s: str) -> str:
    """Spell a number string (commas/decimal ok) as cardinal words — never a
    year. '1,920' -> 'one thousand nine hundred twenty', '50.4' -> 'fifty point
    four'."""
    s = s.replace(",", "")
    if "." in s:
        whole, frac = s.split(".")
        return _card(int(whole)) + " point " + " ".join(_ONES[int(d)] for d in frac)
    return _card(int(s))


def _tts_text(text: str) -> str:
    # CORE: spoken numbers must come out clean for a number-heavy channel.
    #   "$1,920" -> "one thousand nine hundred twenty dollars" (cardinal + unit,
    #   never a year), "5,600" -> "five thousand six hundred", "200%" -> "two
    #   hundred percent". Dollar amounts and comma'd quantities are forced to
    #   cardinals; only BARE 4-digit numbers (1990, 2020) read as years. The
    #   captions keep the original digits; only the audio changes.
    text = re.sub(r"\$\s?(\d[\d,]*(?:\.\d+)?)",
                  lambda m: " " + _say_num(m.group(1)) + " dollars ", text)
    text = re.sub(r"\b(\d{1,3}(?:,\d{3})+)\b",
                  lambda m: " " + _say_num(m.group(1)) + " ", text)
    text = text.replace("%", " percent ")
    return _spell_numbers(text)


_SPEECHIFY_MODEL_OK = None            # cache the model that actually worked
_SPEECHIFY_DEAD = False               # set on 429/401 so we stop hammering the API


def _speechify_try(text: str, out_wav: Path, key: str, voice: str, model: str):
    """One request. Returns (True, None) on success or (False, err_detail)."""
    import base64
    import urllib.error
    import urllib.request
    body = json.dumps({"input": text, "voice_id": voice,
                       "audio_format": "wav", "model": model}).encode()
    req = urllib.request.Request(
        "https://api.speechify.ai/v1/audio/speech", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        out_wav.write_bytes(base64.b64decode(data["audio_data"]))
        return (out_wav.exists() and out_wav.stat().st_size > 1000), None
    except urllib.error.HTTPError as he:
        detail = ""
        try:
            detail = he.read().decode()[:220]
        except Exception:  # noqa: BLE001
            pass
        return False, f"HTTP {he.code}: {detail}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:180]


def _speechify_wav(text: str, out_wav: Path) -> bool:
    """Synthesize ONE line with Speechify -> WAV. Tries the requested model
    (default simba-3.2), then falls back through valid API models so a bad model
    string still lets Speechify win before we drop to the local Kokoro voice."""
    global _SPEECHIFY_MODEL_OK, _SPEECHIFY_DEAD
    import os
    key = os.environ.get("SPEECHIFY_API_KEY")
    if not key or _SPEECHIFY_DEAD:
        return False
    voice = os.environ.get("SPEECHIFY_VOICE", "henry")
    # Known good model first (once one works, reuse it — no re-probing). Only
    # explore other models before we've found one, to avoid hammering the API.
    if _SPEECHIFY_MODEL_OK:
        order = [_SPEECHIFY_MODEL_OK]
    else:
        order = []
        for m in [os.environ.get("SPEECHIFY_MODEL", "simba-3.2"),
                  "simba-english", "simba-multilingual", "simba-turbo"]:
            if m and m not in order:
                order.append(m)
    last = None
    for model in order:
        ok, err = _speechify_try(text, out_wav, key, voice, model)
        if ok:
            if _SPEECHIFY_MODEL_OK != model:
                print(f"[tts] speechify OK on model={model!r} voice={voice!r}",
                      flush=True)
                _SPEECHIFY_MODEL_OK = model
            return True
        last = err
        # Rate-limited or unauthorized -> stop for the whole run (don't hammer).
        if err and ("HTTP 429" in err or "HTTP 401" in err or "HTTP 403" in err):
            _SPEECHIFY_DEAD = True
            break
    print(f"[tts] speechify unavailable ({last}) — using Kokoro for this batch",
          file=sys.stderr)
    if last and "HTTP 429" not in last:
        _speechify_list_voices_once(key)
    return False


_VOICES_LOGGED = False


def _speechify_list_voices_once(key: str) -> None:
    """On first failure, log the account's real voice_ids so a bad SPEECHIFY_VOICE
    can be corrected from the CI log (the /v1/audio/speech error doesn't name them)."""
    global _VOICES_LOGGED
    if _VOICES_LOGGED:
        return
    _VOICES_LOGGED = True
    import urllib.request
    try:
        req = urllib.request.Request("https://api.speechify.ai/v1/voices",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            voices = json.loads(r.read())
        items = voices.get("voices", voices) if isinstance(voices, dict) else voices
        ids = []
        for v in (items or []):
            if isinstance(v, dict):
                ids.append(v.get("id") or v.get("voice_id") or v.get("name"))
            else:
                ids.append(v)
        print(f"[tts] speechify voice_ids: {ids[:30]}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[tts] speechify voices list failed: {str(e)[:140]}", file=sys.stderr)


def synth_narration(sentences, workdir: Path, voice: str):
    import os
    import soundfile as sf

    # Speechify first (if a key is set) — whole-video, so the voice never
    # switches mid-clip: if ANY line fails (quota/error) we throw the batch away
    # and re-synth everything on the local Kokoro voice.
    wavs, windows, t = [], [], 0.0
    if os.environ.get("SPEECHIFY_API_KEY"):
        ok = True
        for i, sent in enumerate(sentences):
            w = workdir / f"s{i}.wav"
            if not _speechify_wav(_tts_text(sent), w):
                ok = False
                break
            d = _dur(w) + 0.12
            windows.append((t, t + d)); t += d; wavs.append(w)
        if ok and wavs:
            print(f"[tts] speechify {os.environ.get('SPEECHIFY_MODEL','simba-3.2')} "
                  f"({len(wavs)} lines)", flush=True)
        else:
            wavs, windows, t = [], [], 0.0          # reset -> Kokoro below

    if not wavs:
        from kokoro_onnx import Kokoro
        k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
        # Validate the themed voice once; fall back to the house voice if the id
        # isn't in this Kokoro build, so a theme can never break a render.
        try:
            k.create("test", voice=voice, lang="en-us")
        except Exception:  # noqa: BLE001
            voice = "am_fenrir"
        for i, sent in enumerate(sentences):
            samples, sr = k.create(_tts_text(sent), voice=voice, speed=1.10,
                                   lang="en-us")
            w = workdir / f"s{i}.wav"
            sf.write(str(w), samples, sr)
            d = _dur(w) + 0.12       # tight breath between lines (pace = retention)
            windows.append((t, t + d))
            t += d
            wavs.append(w)
    listf = workdir / "list.txt"
    listf.write_text("\n".join(f"file '{w}'" for w in wavs) + "\n")
    raw = workdir / "raw.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(listf), "-af", "apad=pad_dur=0.18", "-c:a", "pcm_s16le",
          str(raw)])
    narration = workdir / "narration.wav"
    # Optional gentle pitch shift (asetrate shifts pitch+tempo; atempo undoes
    # the tempo), then loudness-normalize. Skip the shift at natural pitch.
    sr0 = 24000
    af = "loudnorm=I=-16:LRA=11:TP=-1.5"
    if abs(VOICE_PITCH - 1.0) > 0.005:
        af = (f"asetrate={int(sr0 * VOICE_PITCH)},aresample={sr0},"
              f"atempo={1 / VOICE_PITCH:.4f}," + af)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
          "-af", af, str(narration)])
    return narration, windows


# --------------------------------------------------------------------------
# ASS: hook card, kinetic captions, punches, sources card.
# --------------------------------------------------------------------------
def _wrap(text: str, width: int = 22) -> str:
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return "\\N".join(out)


# --------------------------------------------------------------------------
# Custom thumbnail — packaging. YouTube otherwise auto-picks a mid-video chart
# frame that mismatches the title (a "fewer kids" video showing a "cost to
# raise a child" chart). We render a purpose-built 1280x720 card from the same
# per-video theme: the hook as the claim + the single biggest on-chart number
# as a giant accent, so the channel grid reads as one coherent brand and the
# thumbnail always matches the title.
# --------------------------------------------------------------------------
THUMB_W, THUMB_H = 1280, 720


def _font(size: int, bold: bool = True):
    """DejaVu Sans (Bold) — bundled with matplotlib, so it's guaranteed to
    exist wherever the renderer runs (CI included) and matches the burned-in
    caption font for a consistent look."""
    import matplotlib
    from PIL import ImageFont
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name
    return ImageFont.truetype(str(path), size)


def _num_magnitude(text: str) -> float:
    """Parse the numeric magnitude out of a punch label like '1,920', '200%'
    or '$50.4' so we can pick the most striking number for the thumbnail."""
    m = re.search(r"-?[\d,]*\.?\d+", text.replace(",", ""))
    return abs(float(m.group())) if m else -1.0


def _headline_number(st: "story.Story") -> str | None:
    """The number to lead the cold-open with: the most eye-catching stat from
    the OPENING beat (segment 1), not merely the biggest number anywhere in the
    video. Leading with segment 1's stat keeps frame 1 on-topic with the hook —
    otherwise a late, mundane figure (e.g. a baseline '80%') can hijack the open.
    Falls back to a whole-story scan if the first segment names no number."""
    def biggest(segs) -> str | None:
        best, best_mag = None, -1.0
        for seg in segs:
            for p in seg.punches:
                t = (p.get("text") or "").strip()
                if not t:
                    continue
                mag = _num_magnitude(t)
                if mag > best_mag:
                    best, best_mag = t, mag
        return best
    return biggest(st.segments[:1]) or biggest(st.segments)


def _vgradient(top_hex: str, bot_hex: str):
    """A vertical gradient Image from two '0xRRGGBB' / '#RRGGBB' colors."""
    from PIL import Image
    def rgb(h):
        h = h.lstrip("#").replace("0x", "")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    t, b = rgb(top_hex), rgb(bot_hex)
    col = Image.new("RGB", (1, THUMB_H))
    for y in range(THUMB_H):
        f = y / (THUMB_H - 1)
        col.putpixel((0, y), tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3)))
    return col.resize((THUMB_W, THUMB_H))


def make_thumbnail(st: "story.Story", theme: dict, out_path: Path) -> Path:
    """Render a 1280x720 thumbnail card for a built story and return its path.
    Title-aligned by construction: the claim text IS the spoken hook."""
    from PIL import Image, ImageDraw

    grad = theme.get("grad", ("0x0e2444", "0x080A14"))
    img = _vgradient(grad[1], grad[0]).convert("RGB")
    draw = ImageDraw.Draw(img)
    M = 70

    # Giant accent number, top-right — the gut-punch the title promises.
    big = _headline_number(st)
    if big:
        nf = _font(300)
        nb = draw.textbbox((0, 0), big, font=nf)
        nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        # Shrink to fit the right ~62% of the card.
        if nw > THUMB_W * 0.62:
            nf = _font(int(300 * (THUMB_W * 0.62) / nw))
            nb = draw.textbbox((0, 0), big, font=nf)
            nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        nx = THUMB_W - M - nw - nb[0]
        ny = M - nb[1]
        draw.text((nx + 6, ny + 6), big, font=nf, fill=(0, 0, 0))           # shadow
        draw.text((nx, ny), big, font=nf, fill=theme.get("highlight", "#4FD1C5"))

    # Claim text (the hook), bottom-left, big and white. Manual wrap to width.
    claim = (st.hook or st.title or "").strip().rstrip("?!.") or st.title
    cf = _font(96)
    words, lines, line = claim.split(), [], ""
    maxw = THUMB_W - 2 * M
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=cf) > maxw and line:
            lines.append(line)
            line = w
        else:
            line = trial
    if line:
        lines.append(line)
    # Shrink the font if it would overflow more than 4 lines of the lower half.
    while len(lines) > 4 and cf.size > 48:
        cf = _font(cf.size - 8)
        lines, line = [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if draw.textlength(trial, font=cf) > maxw and line:
                lines.append(line)
                line = w
            else:
                line = trial
        if line:
            lines.append(line)

    lh = int(cf.size * 1.12)
    block_h = lh * len(lines)
    y = THUMB_H - M - block_h
    # Accent rule above the claim.
    draw.rectangle([M, y - 26, M + 150, y - 14],
                   fill=theme.get("accent", "#60A5FA"))
    for ln in lines:
        draw.text((M + 4, y + 4), ln, font=cf, fill=(0, 0, 0))              # shadow
        draw.text((M, y), ln, font=cf, fill=(255, 255, 255))
        y += lh

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=90)
    return out_path


def _make_mandel_mask(path: Path, w: int, h: int, feather: int = 180,
                      bottom: int = 120) -> None:
    """Vertical alpha gradient so the mandelbrot feathers in at the top and
    out at the very bottom (blends into the ambient instead of a hard edge)."""
    from PIL import Image
    col = Image.new("L", (1, h), 0)
    for y in range(h):
        if y < feather:
            a = 255 * y / feather
        elif y > h - bottom:
            a = 255 * (h - y) / bottom
        else:
            a = 255
        col.putpixel((0, y), int(max(0, min(255, a))))
    col.resize((w, h)).save(path)


def _ellipse_path_abs(cx: float, cy: float, rx: float, ry: float) -> str:
    """ASS vector path for an ellipse outline centred at absolute (cx,cy).
    Using absolute coords (with \\pos(0,0)) avoids libass \\an/\\pos quirks
    that were offsetting the ring from the number."""
    kx, ky = 0.5523 * rx, 0.5523 * ry
    return (f"m {cx - rx:.0f} {cy:.0f} "
            f"b {cx - rx:.0f} {cy - ky:.0f} {cx - kx:.0f} {cy - ry:.0f} {cx:.0f} {cy - ry:.0f} "
            f"b {cx + kx:.0f} {cy - ry:.0f} {cx + rx:.0f} {cy - ky:.0f} {cx + rx:.0f} {cy:.0f} "
            f"b {cx + rx:.0f} {cy + ky:.0f} {cx + kx:.0f} {cy + ry:.0f} {cx:.0f} {cy + ry:.0f} "
            f"b {cx - kx:.0f} {cy + ry:.0f} {cx - rx:.0f} {cy + ky:.0f} {cx - rx:.0f} {cy:.0f}")


def _round_rect_tail(x0, y0, x1, y1, r=30, tail_x=540, tip=(540, 520)) -> str:
    """ASS \\p1 path: a rounded rectangle (a speech bubble) with a downward
    tail at tail_x pointing to `tip`. Used \\pos(0,0) + absolute coords."""
    tlx, tly = tip
    p = [
        f"m {x0 + r} {y0}", f"l {x1 - r} {y0}",
        f"b {x1} {y0} {x1} {y0} {x1} {y0 + r}",   # TR
        f"l {x1} {y1 - r}",
        f"b {x1} {y1} {x1} {y1} {x1 - r} {y1}",   # BR
        f"l {tail_x + 34} {y1}", f"l {tlx} {tly}", f"l {tail_x - 34} {y1}",
        f"l {x0 + r} {y1}",
        f"b {x0} {y1} {x0} {y1} {x0} {y1 - r}",   # BL
        f"l {x0} {y0 + r}",
        f"b {x0} {y0} {x0} {y0} {x0 + r} {y0}",   # TL
    ]
    return " ".join(p)


def _build_hook_receipt(story_cfg: dict, work: Path, slug: str,
                        hook_dur: float = 3.0):
    """Assemble a RECEIPT cold-open from the story's OWN data: category jumps as
    line items + a dollar total that races from its first year to its last.
    Returns (printf_pattern, nframes) or None if the story lacks the pieces
    (then the plain hero-number hook is used)."""
    try:
        cats = dollars = None
        for seg in story_cfg.get("segments", []):
            fn = (seg.get("params") or {}).get("file") or f"{seg.get('key', '')}.json"
            p = REPO / "data_learning" / "data" / fn
            if not p.exists():
                continue
            data = json.loads(p.read_text())
            pts = data.get("points", [])
            unit = (data.get("unit") or "").lower()
            has_period = len([1 for q in pts if q.get("period")]) >= 2
            if not has_period and len(pts) >= 3 and cats is None:
                cats = data
            if unit in ("dollars", "usd") and has_period and dollars is None:
                sp = sorted(pts, key=lambda q: float(q["period"]))
                dollars = (float(sp[0]["value"]), float(sp[-1]["value"]))
        if not cats or not dollars:
            return None
        cu = (cats.get("unit") or "").lower()

        def _fmt(v):
            s = f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.1f}"
            if cu in ("percent", "%", "pct"):
                return "+" + s + "%"
            if cu in ("dollars", "usd"):
                return "$" + s
            return s
        lines = [(str(q["label"])[:12], _fmt(float(q["value"])))
                 for q in cats.get("points", [])[:5]]
        lo, hi = dollars
        pct = int(round((hi / lo - 1) * 100)) if lo else 0
        pat, _ = charts.render_hook_receipt(
            work / "receipt", slug, "RECEIPT", lines, lo, hi, "dollars",
            stamp=(f"+{pct}%" if pct else ""),
            frames=int(max(24, min(180, round(hook_dur * 30)))))
        import glob as _glob
        return pat, len(_glob.glob(pat.replace("%02d", "*")))
    except Exception as e:  # noqa: BLE001 — never let the cold-open kill a render
        print(f"[studio] hook receipt skipped: {e}", flush=True)
        return None


# --------------------------------------------------------------------------- #
# THE EDIT — one visual per span, strictly forward, never revisited
# --------------------------------------------------------------------------- #
# Three edits have been tried on this channel and the operator has ruled on
# each, so the history matters more than the code here:
#
#   1. ONE CHART PER BEAT, held 8-20 seconds. "we sit on a fucking one chart
#      as it slowly moves for twenty seconds. Like, that's boring."
#   2. CUT THE SAME CHART INTO TIGHTER FRAMINGS. "the jump cut zoom ins are
#      not it ... there is like 4 'things' and then movement, that's not good
#      enough" — a punch-in is one subject with a camera on it, not a second
#      thing. The crop helper that did this is DELETED, not parked: it is the
#      literal thing being complained about and a dead helper gets re-wired by
#      the next session that finds it.
#   3. ALTERNATE two depictions across the beat (A-B-A-B). Also refused, and
#      this one was mine: "we'll open on a fucking graph, and then we'll cut to
#      a different graph, and then we'll cut back to the original graph ...
#      and we'll still be talking about the same beat the whole time, and it
#      just does not roll cohesively."
#
# The ruling that replaces all three: "Once we show a graph and explain it and
# it does its thing, it's gone. We move on to the next one."
#
# So the edit is MONOTONIC. A beat is a sequence of spans; each span shows one
# depiction, full-frame and static; when a span ends that depiction is finished
# and never comes back. A cut always means a new subject — there is no cut that
# merely re-frames what you were already looking at, and nothing on screen is
# ever something you have already seen.
#
# SPAN_TARGET is the other half of the ruling ("we're cutting so much for no
# reason"). At ~3s the edit was chopping a single sentence into four pieces; a
# visual now gets long enough to be read and understood before it is retired.
# Calibrated against the real thing, not guessed. This channel's beats have a
# DISPLAY window of roughly 6-12s (seg0 carries the hook, the last carries the
# closing), so at 5.5 a mid-length beat rounded down to a single visual and a
# whole video came out with five. The operator's floor is explicit — "there is
# like 4 'things' ... we need 7-8 things" — and 4.5 is what actually clears it:
# measured on housing-affordability-wall, 5 visuals -> 8.
# Retuned down from 3 visuals per beat at 4.5s. Eight things in 31 seconds was
# over-packed — "we're trying to force too much into too little amount of time
# ... the whole video felt like the guy was on crack." At 6.5s a 12s beat takes
# two visuals instead of three and each gets six seconds to build and be read,
# which lands a video at 5-6 depictions plus the hook and the closing card.
# Still well clear of the four it started at; the count was never the point.
SPAN_TARGET = 6.5          # seconds one depiction owns the screen
MAX_SPANS = 2              # per beat, so a 3-beat story tops out at 6 visuals

# A CHART NOBODY SEES FINISHED IS A CHART NOBODY CAN READ.
#
# The build used to reach its finished state on the LAST FRAME of its window
# and then cut away, and the value labels faded in over the last 20% on top of
# that. With a 12-20s beat that still left a few seconds of readable chart. At
# four seconds it left well under one, fading, and the operator watched a whole
# video of charts caught mid-build: "I'm a smart fucking person ... what the
# fuck am I looking at?" The charts were fine. They were only ever legible in
# frames nobody was shown — a defect I introduced by shortening the spans
# without touching the ramp that fills them.
#
# So the build completes at READ_BY of its span and the rest is READING TIME.
# The frame does not freeze: the host keeps performing on the finished chart
# (his tour is driven by beat progress, not by the reveal, precisely so it
# outlives the build) and the next visual is only a couple of seconds away.
# RETUNED with the slower pacing. 0.45 was set when a visual was 3.8 seconds,
# where it bought 2.1s of finished chart. Spans are 5.8-7.9s now, so the same
# fraction holds a still frame for over three seconds — and measured across a
# whole video that put the duplicate ratio at 0.464 against a 0.45 ceiling.
# 0.62 still leaves 2.2-3.0s to read, which is MORE than the old setting gave,
# while the build keeps moving for most of the visual.
READ_BY = 0.62
# ...but as a FRACTION it scales the wrong way. A 5.8s visual at 0.62 holds a
# finished chart for 2.2s; the same fraction on a 7.9s visual holds it for 3.0,
# and the per-segment measurement (once it was measuring the shipped pixels)
# put that beat at a duplicate ratio of 0.500 on its own while the video passed
# at 0.367. Reading time is a HUMAN quantity — it does not grow because the
# sentence ran long — so the still tail is capped in seconds and the build
# simply keeps going on a longer visual.
# 1.6s, not 2.2. The gate's ceiling on a frozen stretch is 45 frames and it
# samples at 24fps — so 2.2s IS 53 frames, over the ceiling by construction
# whenever nothing else in the frame moves. The three-beat video got away with
# it because the host and captions were still going; a two- or four-beat one
# did not, and both failed on a closing tail. A budget that only holds when
# something else happens to be moving is not a budget.
MAX_STILL_TAIL = 1.6       # seconds a finished chart may sit before the cut
# ...and TIGHTER during the closing, because the tail budget is really a budget
# for "how long may THIS layer hold while the rest of the frame carries it".
# Mid-video the host is performing and the captions turn over. The closing has
# neither: the card lands its last reveal (the CTA) at 62% and after that only
# the recap moves. A two-beat and a four-beat video both failed there on a tail
# that was fine everywhere else — 47 and 79 frozen frames against a 45 ceiling.
# 0.35, not 0.8. The closing is the LEAST-covered part of the video — once the
# card's reveals land there is nothing else in the frame — so the recap behind
# it has to keep moving almost to the cut. It is also the cheapest place to buy
# motion honestly: the chart is already there and already building.
CLOSING_STILL_TAIL = 0.35
# ...AND THE GAPS BETWEEN THE CLOSING'S REVEALS ARE BOUNDED IN SECONDS TOO.
#
# The tail was fixed and the gaps were left proportional. `qs`/`cs`/`ls` were
# fixed FRACTIONS of the closing window (0.40 / 0.62 / 0.86), so every gap
# between them grows with the window — the exact thing the comment above
# already says about reading time, applied to one end of the closing and not
# the other. `container-ships-floating-cities`, 2026-09-10, held at score 5:
#
#     "temporal_gate: max_dup_run 47 frames > 45 (phase-1 ceiling) — a frozen
#      stretch outside any intentional hold starting at t=46.0s of 49.08s"
#
# t=46.0 is exactly `cs` on that video. Its four gaps, in frames at the 24fps
# the gate samples at: 78, 43, 47, 27 — against a ceiling of 45. Two over,
# and the reveal schedule guaranteed it the moment the closing ran past ~7s.
#
# 1.45s is 35 frames, which leaves real margin under the 45 ceiling for a
# beat that lands slightly late.
CLOSING_MAX_GAP = 1.45
#: How long one CTA pulse animates (`\t` up then back). A pulse ends and the
#: base CTA underneath it keeps drawing, so pulses never stack.
CLOSING_PULSE_S = 0.62
# Where the recap goes during the closing. The card is a 900x320 bubble ending
# at y=470; the foot band with the question and CTA starts at 1683. This sits
# between them, centred, in space these frames were leaving empty.
#
# AT 0.62 THE RECAP'S TYPE WAS UNREADABLE. A chart's row names are 23pt on
# the card; shrunk to 62% under the closing they were "~8px grey on dark and
# vanish at arm's length" (showrunner, invasive species, 2026-09-22 — the
# same note on container ships, sleep divorce, brain microplastics). The
# shrink was uniform because the whole visual had to fit 1213px, and a
# full-frame scene is 1920 tall. But the top of every visual is its heading
# (a card's kicker/headline/subtitle band, a scene's title band) and the
# bottom is its footer or the empty strip under MACHINE_BOT — neither is
# the picture the payoff wants behind it. So the recap is TRIMMED to its
# content band first — a CENTRED crop, the same band off the top and the
# bottom, no offsets and no motion (the operator's ruling against camera
# moves stands; `tests/test_edit_pacing.py` holds that a crop here never
# carries a computed offset) — and only then scaled to the room: a card
# keeps its type at full size, a scene at ~94%. `recap_geometry` is the
# one place this is computed; `tests/test_the_frame_reads_on_a_phone.py`
# holds it.
RECAP_TOP = 490                  # 20px under the bubble (ends y=470)
RECAP_BAND_H = 1683 - 20 - RECAP_TOP   # ...to 20px above the foot band
RECAP_TRIM = 0.175               # trimmed off the top AND the bottom


def recap_geometry(vw: int, vh: int) -> dict:
    """Where and how big a visual's CONTENT BAND is drawn under the closing.

    Returns the centred crop (crop_top rows off each end, crop_h kept) and
    the scaled size and position (rw, rh, rx, ry) — all even, for yuv420p.
    Scale never exceeds 1.0: a card already fits, so its type stays exactly
    as set."""
    vw, vh = int(vw), int(vh)
    crop_top = int(vh * RECAP_TRIM)
    crop_h = max(2, vh - 2 * crop_top) & ~1
    s = min(1.0, RECAP_BAND_H / float(crop_h), (W - 2 * 12) / float(vw))
    rw = max(2, int(vw * s)) & ~1
    rh = max(2, int(crop_h * s)) & ~1
    return {"crop_top": crop_top, "crop_h": crop_h, "scale": s,
            "rw": rw, "rh": rh, "rx": (W - rw) // 2,
            "ry": RECAP_TOP + (RECAP_BAND_H - rh) // 2}


def _full_by(span: float, tail: float = MAX_STILL_TAIL) -> float:
    """What fraction of a visual the build gets, so its tail is bounded.

    There is NO upper clamp, and that is deliberate. It had one (0.85, then
    0.92) meant to guarantee some reading time — but `1 - tail/span` already
    guarantees exactly `tail` seconds of it at every length, and the clamp only
    ever fired on LONG spans, where it broke the very bound it sat next to: at
    0.92 a 30-second visual holds for 2.4s, 58 frames against a ceiling of 45.
    A cap that turns a bounded tail into an unbounded one is worse than none.
    """
    if span <= 0:
        return READ_BY
    return float(max(READ_BY, 1.0 - tail / span))


def _visual_spans(s0: float, s1: float, n: int) -> list[tuple[float, float]]:
    """Split one beat's display window into ``n`` consecutive spans.

    Consecutive and non-overlapping is the whole contract: span k's depiction
    is built to cover exactly [t0, t1) and is positioned on the timeline at its
    own t0, so nothing is ever asked to hold a frame it does not have. The
    earlier design laid every depiction from the BEAT's start, which is how a
    half-length build ran out and ffmpeg's tpad cloned its last frame for 3.0
    seconds — 73 duplicate frames against a ceiling of 45.
    """
    n = max(1, int(n))
    if n == 1:
        return [(s0, s1)]
    step = (s1 - s0) / n
    return [(s0 + k * step, s0 + (k + 1) * step if k < n - 1 else s1)
            for k in range(n)]


def _readable_punch(hex_color: str) -> str:
    """A spoken-number punch colour that can be READ on the dark footer.
    A story whose punch was a dark accent burned "6,288" in near-navy under
    the caption ("a faint dark-navy '6,288' ... nearly disappears", the
    judge, 2026-09-23). Too-dark colours are lifted toward white until the
    relative luminance clears 0.45; bright colours pass unchanged."""
    try:
        h = str(hex_color).lstrip("#")
        rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except Exception:  # noqa: BLE001
        return "#ffffff"

    def lum(c):
        v = [x / 255.0 for x in c]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    k = 0.0
    out = rgb
    while lum(out) < 0.45 and k < 1.0:
        k += 0.1
        out = [int(round(c + (255 - c) * k)) for c in rgb]
    return "#" + "".join(f"{c:02x}" for c in out)


def _dash(text: str) -> str:
    """A typed '--' is a dash on screen. It burned in raw ('to 6,288 --')."""
    import re as _re
    return _re.sub(r"\s*--\s*", " \u2014 ", text or "").strip()


def build_story_ass(st: story.Story, windows, events, out: Path,
                    accent: str = "&H4FD1F5&", hook_visual: bool = False,
                    closing_scene: bool = False,
                    scene_beats: frozenset = frozenset()) -> None:
    """Burn the hook, the kinetic captions and the closing into one ASS file.

    `chart_hook` used to be a parameter here. Its only reader was the hero
    number removed below, and the caller derived it as the exact complement of
    `hook_visual` — so it never selected anything. A parameter a caller
    carefully computes and nobody reads is the same rot as a capability
    nothing calls; it goes with the branch it served.
    """
    acc = accent.strip("&H").rstrip("&")          # bare BBGGRR for inline tags
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,60,&HFFFFFF&,&H000000&,&H66000000&,1,1,4,1,2,90,90,{CAP_MARGINV},1
Style: Hook,DejaVu Sans,118,&HFFFFFF&,&H000000&,&H000000&,1,1,8,2,8,50,50,300,1
Style: Punch,DejaVu Sans,150,&HFFFFFF&,&H000000&,&H000000&,1,1,6,3,5,40,40,0,1
Style: Src,DejaVu Sans,40,&HA5B4C7&,&H000000&,&H000000&,0,1,3,1,5,120,120,0,1
Style: Chip,DejaVu Sans,38,&HFFFFFF&,&H6A5C7C&,&H000000&,1,3,0,0,8,60,60,26,1
Style: Mark,DejaVu Sans,40,&HC5D14F&,&HFFFFFF&,&H000000&,1,1,4,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    sentences = st.sentences()

    def kinetic(sent, s0, s1):
        chunks = _chunks(_dash(sent), 3)
        if not chunks:
            return
        step = (s1 - s0) / len(chunks)
        for j, ch in enumerate(chunks):
            cs, ce = s0 + j * step, s0 + (j + 1) * step
            # Pin narration to a CONSISTENT lower-band plate (below the tall
            # chart) with a heavy outline — so it never lands on the chart or
            # collides with the host performing inside it.
            cap = ("{\\an2\\pos(540,1734)\\fs62\\c&HFFFFFF&\\b1\\bord7"
                   "\\3c&H0A0C12&\\shad0\\fad(70,70)}" + ch.strip())
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Cap,,0,0,0,,"
                         f"{cap}")

    # 0: HOOK — LEAD WITH THE PUNCHLINE. The single biggest shock-number slams
    # onto frame 1 as the hero (the same gut-punch the thumbnail promises),
    # with the take spelled out beneath it in fast 2-word bursts. No more five
    # seconds of an idle mascot before any substance — the payoff is on screen
    # at t=0, which is the only moment that decides whether they keep watching.
    h0, h1 = windows[0]
    # THE HERO NUMBER IS GONE, because it never once drew.
    #
    # It was guarded by `not hook_visual and not chart_hook`, and its caller
    # derives BOTH from the same value — `hook_visual=bool(receipt)` and
    # `chart_hook=(receipt is None)`. Those are exact complements, so the
    # conjunction is a contradiction: with a receipt the first is False,
    # without one the second is. A 240pt number at y=235, described in a
    # comment that said when it "still leads", and it has led nothing.
    #
    # Composited by hand to see what it would have looked like if it fired:
    # the chart's own title lands at screen y≈174 and its subtitle at 281,
    # so 240pt centred at 235 is drawn straight through both — "NASA[  ]s[ ]re
    # of t[ ]e [  ]ed[  ]l budget". That is the `unreadable` class the
    # showrunner already blocks for, and it is why this cannot simply be
    # switched back on where it stood.
    #
    # The design also moved past it. `lead_hook` exists so seg0's CHART
    # carries the cold open — see the comment at its assignment: a hook with
    # no data on screen is the `empty_void` / `decorative_mascot` the gate
    # blocks, and the data demonstration should be the star from frame 1.
    # `_headline_number` is still live for the thumbnail and for long-form.
    hchunks = _chunks(_dash(st.hook), 2) if not hook_visual else []
    if hchunks:
        hstep = (h1 - h0) / len(hchunks)
        for j, ch in enumerate(hchunks):
            cs, ce = h0 + j * hstep, h0 + (j + 1) * hstep
            # THE HOOK TAKE SITS ON THE LOWER PLATE, WHERE EVERY OTHER CAPTION
            # SITS. It was pinned at y=470 — the top rows of whichever chart
            # leads the cold open, which is the ONLY case this branch runs
            # (`hook_visual` is false exactly when seg0's chart is on screen
            # from frame 1). Three of seven verdicts on 2026-09-22 named it:
            # "'A pit / stop used' overlapping the '1950s' label and bar",
            # "'Your coffee' set straight across the 2019 row, covering that
            # row's $1.1 value", "'That's more' lands on top of the 1970 row
            # label and its $1.6B value". The lower plate is below the card
            # and above the source line, and seg0's own captions only start
            # when the hook window ends, so nothing shares these pixels.
            if j == 0:
                pop = ("{\\an2\\pos(540,1734)\\fs78\\fad(0,70)\\fscx118\\fscy118"
                       "\\t(0,130,\\fscx100\\fscy100)\\3c" + accent + "\\bord8\\blur5}")
            else:
                pop = ("{\\an2\\pos(540,1734)\\fs78\\fad(70,70)\\fscx106\\fscy106"
                       "\\t(0,110,\\fscx100\\fscy100)\\bord8}")
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Hook,,0,0,0,,"
                         f"{pop}{ch.strip()}")

    # Per segment: step chip + kinetic captions. In CLEAN mode the chart draws
    # its own title, so the studio role chip is dropped (it was overlapping it).
    import os as _osc
    _clean = _osc.environ.get("LEGACY_LOOK") != "1"
    for i, seg in enumerate(st.segments):
        s0, s1 = windows[1 + i]
        if seg.role and not _clean:
            chip = "{\\fad(150,150)} " + seg.role + " "
            lines.append(f"Dialogue: 2,{_ass_time(s0)},{_ass_time(s1)},Chip,,0,0,0,,"
                         f"{chip}")
        kinetic(seg.sentence, s0, s1)

    # Per spoken number: a pulsing marker ON the data point + the big punch.
    for e in events:
        ps, pe, p = e["ps"], e["pe"], e["punch"]
        color = _hex_to_ass(_readable_punch(p.get("color", "#ffffff")))
        _a = e.get("anchor")
        if (e["xy"] and e["box"]
                and not (isinstance(_a, dict) and _a.get("measured") is False)):
            mx, my = int(e["xy"][0]), int(e["xy"][1])
            rx = e["box"][0] / 2 + 24      # encase the WHOLE number + padding
            ry = e["box"][1] / 2 + 14
            ring = ("{\\an7\\pos(0,0)\\org(" + f"{mx},{my}" + ")\\1a&HFF&"
                    "\\3c&HF0E14F&\\bord5\\shad0\\fad(120,150)"
                    "\\t(0,200,\\fscx106\\fscy106)\\t(200,420,\\fscx100\\fscy100)"
                    "\\p1}" + _ellipse_path_abs(mx, my, rx, ry) + "{\\p0}")
            # the ring's own window: on the number as it is said, but never
            # before the build has put the number there (`_plan_events`)
            r0 = e.get("ring0") if e.get("ring0") is not None else max(0, ps - 0.15)
            r1 = e.get("ring1") if e.get("ring1") is not None else pe
            lines.append(f"Dialogue: 3,{_ass_time(max(0, r0))},"
                         f"{_ass_time(r1)},Mark,,0,0,0,,{ring}")
        if e.get("seg") in scene_beats:
            # A SUBJECT SCENE prints its own readout. The punch put the same
            # number a third time under the caption that already says it —
            # the "faded ghost '6,288' under the caption" the showrunner
            # named twice (2026-09-23).
            continue
        styled = ("{\\fad(120,120)\\pos(" + str(PUNCH_X) + "," + str(PUNCH_Y)
                  + ")\\fs104\\c" + color + "}" + p.get("text", ""))
        lines.append(f"Dialogue: 1,{_ass_time(ps)},{_ass_time(pe)},Punch,,0,0,0,,"
                     f"{styled}")

    # CLOSING — the mascot delivers its quip in a speech bubble (the focus),
    # with the sources shrunk to tiny text at the very bottom.
    c0, c1 = windows[-1]
    cd = max(1.2, c1 - c0)
    # STAGGER the closing reveals across the WHOLE window so content keeps
    # appearing (no long frozen 'read the card' hold — the dead-air the gate
    # measures). Bubble+quip land first, the question ~40% in, the CTA ~62% in
    # with a bounce, so nothing sits static for 4s.
    # BOUNDED, NOT PROPORTIONAL — see `CLOSING_MAX_GAP`. On a short closing
    # these are still the old fractions; on a long one they stop stretching.
    qs = c0 + min(0.40 * cd, CLOSING_MAX_GAP)
    cs = qs + min(0.22 * cd, CLOSING_MAX_GAP)
    # ...and one LAST reveal, so the card is not silent through its final
    # third. Everything used to land by 62%: on a 31s video that left ~1.5s of
    # nothing new, which the host and a still recap could just about carry, and
    # on a 43s one it left 3.3s — a 79-frame frozen stretch against a ceiling
    # of 45. The closing failed the gate on exactly the videos whose closing
    # was longest, which is the wrong way round for a payoff.
    # ...and the last reveal REPEATS to the cut instead of firing once.
    #
    # One pulse at 0.86 bounded the tail after it and left the run BEFORE it
    # unbounded — 47 frozen frames between the CTA landing and the pulse.
    # The pulse is the cheapest honest motion in the frame (the CTA is
    # already drawn; this is an emphasis on it), so it runs on a cadence and
    # no stretch of the closing is ever longer than one gap.
    _pulses = []
    _t = cs + min(0.24 * cd, CLOSING_MAX_GAP)
    while _t < c1 - 0.25:
        _pulses.append(_t)
        _t += CLOSING_MAX_GAP
    ls = _pulses[0] if _pulses else cs
    bubble = ("{\\an7\\pos(0,0)\\1c&H241A12&\\3c&H" + acc + "&\\bord4\\shad0"
              "\\fad(250,0)\\p1}"
              + _round_rect_tail(90, 150, 990, 470, 30, 540, (540, 588))
              + "{\\p0}")
    if closing_scene:
        # The closing is a full-bleed scene of its own: the line sits on the
        # sky it keeps clear (y 140..480), outlined like every caption — no
        # bordered card. The showrunner named the card a UI widget.
        quip = ("{\\an5\\pos(540,308)\\fs62\\c&HFFFFFF&\\b1\\bord5\\3c&H000000&"
                "\\shad0\\fad(300,0)}" + _wrap(st.closing, 22))
    else:
        lines.append(f"Dialogue: 4,{_ass_time(c0)},{_ass_time(c1)},Src,,0,0,0,,"
                     f"{bubble}")
        quip = ("{\\an5\\pos(540,308)\\fs54\\c&HFFFFFF&\\b1\\bord0\\shad2"
                "\\fad(300,0)}" + _wrap(st.closing, 20))
    lines.append(f"Dialogue: 5,{_ass_time(c0)},{_ass_time(c1)},Cap,,0,0,0,,{quip}")
    # Engagement CTA — ask the question + nudge a comment (drives the algorithm).
    question = getattr(st, "question", "")
    if question:
        # THE CLOSING STILL HAS A CHART UNDER IT.
        #
        # These sat at y=1330 and y=1442, inside the chart region (26..1673),
        # so on a `lead_payoff` close — where the last segment's chart spans
        # the closing — they printed straight over its value labels. The
        # showrunner on 2026-08-11: "the strong bubble finale is buried under
        # overlapping text", and its own fix note, "Move the CTA block below
        # the bubble cluster ... so it never overlaps 'Hong Kong SAR, China'
        # or 'Gibraltar'".
        #
        # The answer is three lines up in this same function: narration is
        # already pinned to the lower-band plate at y=1734 precisely "so it
        # never lands on the chart". The closing's two lines join it. The
        # foot band is 1683..1920 and is free during the closing except the
        # sources strip at 1898, so the stack is:
        #
        #     question  an5 fs42, <=2 lines   1690 .. 1800
        #     CTA       an5 fs54, 1 line      1802 .. 1870
        #     sources   an2 fs15              1880 .. 1898
        #
        # Wrapped at 30 rather than 24 to hold the question to two lines; a
        # third would push its top back over the chart.
        q = ("{\\an5\\pos(540,1745)\\fs42\\c&HFFFFFF&\\b1\\bord3\\3c&H000000&"
             "\\shad0\\fad(300,0)}" + _wrap(question, 30))
        lines.append(f"Dialogue: 5,{_ass_time(qs)},{_ass_time(c1)},Cap,,0,0,0,,{q}")
        # CTA pops in late, under the question, with the same bounce.
        cta = ("{\\an5\\move(540,1848,540,1836,0,900)\\fs54\\c&H" + acc
               + "&\\b1\\bord5\\3c&H000000&\\shad0\\fad(300,0)"
               "\\fscx82\\fscy82\\t(0,300,\\fscx100\\fscy100)}COMMENT BELOW ▼")
        # The steady CTA steps aside while a pulse copy plays: two copies at
        # different scales printed "COMMENT BELOW ▼▼" (the judge, 2026-09-23).
        _gaps, _t = [], cs
        for _pt in sorted(p_ for p_ in _pulses if cs <= p_ < c1):
            if _pt > _t:
                _gaps.append((_t, _pt))
            _t = max(_t, min(c1, _pt + CLOSING_PULSE_S))
        if _t < c1:
            _gaps.append((_t, c1))
        for _k, (_a, _b) in enumerate(_gaps):
            _c = cta if _k == 0 else cta.replace("\\fad(300,0)", "")
            lines.append(f"Dialogue: 5,{_ass_time(_a)},{_ass_time(_b)},Cap,,0,0,0,,{_c}")
        # THE LAST BEAT OF THE VIDEO. The CTA gives one more push right at the
        # end — a real emphasis a viewer reads as "now", and the only thing
        # still changing in the final second.
        pulse = ("{\\an5\\pos(540,1836)\\fs54\\c&H" + acc
                 + "&\\b1\\bord5\\3c&H000000&\\shad0"
                 "\\fscx100\\fscy100\\t(0,260,\\fscx112\\fscy112)"
                 "\\t(260,560,\\fscx100\\fscy100)}COMMENT BELOW ▼")
        for _pt in _pulses:
            lines.append(f"Dialogue: 6,{_ass_time(_pt)},"
                         f"{_ass_time(min(c1, _pt + CLOSING_PULSE_S))},"
                         f"Cap,,0,0,0,,{pulse}")
    # THE SOURCES LIVE IN THE DESCRIPTION; THE SCREEN SAYS WHERE.
    #
    # The strip used to carry the citation itself, and the foot band has room
    # for exactly one short line: at fs15 it was "microscopic grey text you
    # cannot read on a phone", at fs24 inside an 80-character budget it was
    # still "tiny ... cut off at 'compiled fro...'" (the judge, 2026-09-23),
    # and it failed `unreadable` on videos that otherwise scored 74. The full
    # citation — publisher, dataset, link, access date — now goes into the
    # upload description (`post_stories._sources_block`), where nothing is
    # truncated, and the screen carries one line a phone can read.
    src_txt = ("{\\an2\\pos(540,1898)\\fs" + str(SRC_FS)
               + "\\c&HE8EEF4&\\b1\\bord2\\shad0"
               "\\q2\\fad(200,0)}" + SRC_TEXT)
    lines.append(f"Dialogue: 0,{_ass_time(c0)},{_ass_time(c1)},Src,,0,0,0,,{src_txt}")

    out.write_text(head + "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# Targeting — a "point" (marker) lands on the exact data value being spoken,
# and the mascot walks to it, re-targeting for every number in the script.
# --------------------------------------------------------------------------
def _screen(px, py):
    """Chart-PNG pixel -> screen pixel (independent x/y scale + offset)."""
    return (CHART_X + px * SCALE_X, CHART_Y + py * SCALE_Y)


def _anchor_for_punch(seg: story.Segment, punch: dict):
    """The data point whose value matches this punch's number."""
    txt = punch.get("text", "").replace("%", "").replace(",", "").strip()
    try:
        val = float(txt)
    except ValueError:
        return None
    if not seg.anchors:
        return None
    return min(seg.anchors, key=lambda a: abs(a["value"] - val))


def _phrase_frac(sentence: str, phrase: str):
    """Fraction of the way through the SPOKEN sentence where ``phrase`` is
    said — or None when it cannot be found.

    THE RING CAME EARLY OR LATE. Operator, 2026-09-21: *"the blue circle
    that circles the data we are talking about misses about 75% of the time
    or it comes too early or late."* This measured the fraction by WORD
    COUNT of the written sentence, and a written word is not a spoken
    length: "$1,920" is one word on the page and eleven syllables in the
    voice ("one thousand nine hundred twenty dollars"), "82%" is one word
    and five syllables, "a" is one word and one. A sentence front-loaded
    with numbers put every ring seconds early; one that ended in a number
    put it late. So this now measures CHARACTERS of the text the voice
    actually reads (`_tts_text`, numbers spelled out), which tracks speaking
    time far more closely, and it looks for the phrase in that same spelled
    text so "82M" finds "eighty-two million".

    None instead of a guess: a phrase that is not in the sentence used to
    return 0.5 — a ring at mid-sentence, on a number the voice was not
    saying. The caller draws NO ring for None (the punch text still shows).
    """
    if not phrase or not sentence:
        return None
    spoken = _tts_text(sentence)
    target = _tts_text(phrase).strip()
    idx = spoken.lower().find(target.lower()) if target else -1
    if idx >= 0:
        return len(spoken[:idx]) / max(1, len(spoken))
    idx = sentence.lower().find(phrase.lower())
    if idx >= 0:
        return len(sentence[:idx]) / max(1, len(sentence))
    return None


#: The closing's one-line pointer to the full citation in the description.
SRC_FS = 28
SRC_TEXT = "Sources in the description"


def _plan_events(st: story.Story, windows):
    """One event per spoken number: when it's said, which data point it is,
    and (later) where the mascot should stand. Timed to where the number
    falls in the sentence so marker/monster hit it as the voice says it. Each
    event also gets a show-window so exactly one mascot is up at a time."""
    events = []
    for i, seg in enumerate(st.segments):
        s0, s1 = windows[1 + i]
        seg_events = []
        spans = getattr(seg, "spans", None) or []
        for p in seg.punches:
            frac = _phrase_frac(seg.sentence, p.get("phrase", ""))
            timed = frac is not None
            ps = s0 + (frac if timed else 0.5) * (s1 - s0)
            dur = min(float(p.get("duration", 1.8)), max(0.6, s1 - ps))
            # THE RING MISSED 75% OF THE TIME. It was placed from
            # `seg.anchors` — the coordinates of the CHEAP build story.build
            # ran to discover which numbers the line names — and that chart
            # is, since the per-span edit, almost never the visual on screen:
            # a beat shows a mechanic, then a machine, then maybe a chart, each
            # with its own geometry, and the ring circled where a number sat
            # on a picture nobody saw. It is placed now from the anchors of the
            # span that is ON SCREEN when the number is said; a full-frame
            # visual (mechanic / scene / diorama) records no number positions,
            # so during one there is NO ring rather than a wrong one.
            a, xy, box, ring0 = None, None, None, None
            sp = _span_at(spans, ps)
            if sp is not None:
                a = _anchor_in(sp.get("anchors") or [], p) if timed else None
                if a:
                    if sp.get("kind") in charts.FULLFRAME_RENDERERS:
                        xy = (float(a["cx"]), float(a["cy"]))
                        box = (float(a["w"]), float(a["h"]))
                    else:
                        xy = _screen(a["cx"], a["cy"])
                        box = (a["w"] * SCALE_X, a["h"] * SCALE_Y)
                    # ...AND NOT BEFORE THE NUMBER IS THERE. A build reaches
                    # its final frame — where the anchors are — at `full_by`
                    # of its span; a ring drawn while the bar is still rising
                    # circles empty space. Wait for the build, never past the
                    # span's end.
                    done_at = sp["t0"] + (sp["t1"] - sp["t0"]) * float(sp.get("full_by", 1.0))
                    ring0 = min(max(ps - 0.15, done_at), max(sp["t0"], sp["t1"] - 0.6))
            elif not spans and timed:
                # a story read before render (no spans yet): the old answer
                a = _anchor_for_punch(seg, p)
                if a:
                    xy = _screen(a["cx"], a["cy"])
                    box = (a["w"] * SCALE_X, a["h"] * SCALE_Y)
                    ring0 = ps - 0.15
            seg_events.append({"ps": ps, "pe": ps + dur, "punch": p, "xy": xy,
                               "box": box, "anchor": a, "seg": i,
                               "timed": timed,
                               "ring0": ring0,
                               "ring1": (max(ring0 + 0.8, ps + dur)
                                         if ring0 is not None else None)})
        # Show-windows: split the segment among its numbers (mascot stays on
        # number j until the next number is spoken).
        seg_events.sort(key=lambda e: e["ps"])
        bounds = [s0]
        for k in range(len(seg_events) - 1):
            bounds.append((seg_events[k]["ps"] + seg_events[k + 1]["ps"]) / 2)
        bounds.append(s1)
        for k, e in enumerate(seg_events):
            e["w0"], e["w1"] = bounds[k], bounds[k + 1]
        events.extend(seg_events)
    return events


def _span_at(spans, t: float):
    """The recorded visual span covering time ``t`` (the last one whose
    start is at or before ``t``), or None."""
    hit = None
    for sp in spans or []:
        try:
            if float(sp["t0"]) <= t and (hit is None or sp["t0"] >= hit["t0"]):
                hit = sp
        except (KeyError, TypeError, ValueError):
            continue
    if hit is not None and t >= float(hit.get("t1", t + 1)) + 0.05:
        return None
    return hit


def _anchor_in(anchors, punch: dict):
    """The label-dict anchor whose value matches this punch's number, among
    THESE anchors (a span's), ignoring any non-dict entry a full-frame
    visual may record."""
    txt = punch.get("text", "").replace("%", "").replace(",", "").strip()
    try:
        val = float(txt)
    except ValueError:
        return None
    dicts = [a for a in (anchors or []) if isinstance(a, dict) and "value" in a]
    if not dicts:
        return None
    best = min(dicts, key=lambda a: abs(float(a["value"]) - val))
    # a match, not the nearest stranger: within 2% (or 0.5 absolute)
    if abs(float(best["value"]) - val) > max(0.5, 0.02 * abs(val)):
        return None
    return best


def _screen_box(a):
    cx, cy = _screen(a["cx"], a["cy"])
    return cx, cy, a["w"] * SCALE_X, a["h"] * SCALE_Y


def _place_mascot(active, seg_anchors, scale: float = 1.0):
    """Stand the mascot right beside the active number, inside the chart, in
    empty space that doesn't cover ANY number. Returns (body_cx, body_cy,
    variant) where variant is 'L' (left of number, points right), 'R' (right
    of number, points left) or 'U' (fallback below the card, points up).
    ``scale`` sizes his footprint so a smaller in-chart host fits beside a bar
    where a full-size one would be pushed out to the 'U' fallback."""
    S = MASCOT_SIZE
    bw, bh = 0.52 * S * scale, 0.78 * S * scale
    acx, acy, aw, ah = _screen_box(active)
    obox = []
    for o in seg_anchors:
        if o is active:
            continue
        cx, cy, w, h = _screen_box(o)
        obox.append((cx - w / 2 - 6, cy - h / 2 - 6, cx + w / 2 + 6, cy + h / 2 + 6))
    chart = (CHART_X + 6, CHART_Y + 44, CHART_X + CHART_W - 6,
             CHART_Y + CHART_H - 28)

    def fits(bcx, bcy):
        b = (bcx - bw / 2, bcy - bh / 2, bcx + bw / 2, bcy + bh / 2)
        if b[0] < chart[0] or b[2] > chart[2] or b[1] < chart[1] or b[3] > chart[3]:
            return False
        return all(b[2] <= o[0] or b[0] >= o[2] or b[3] <= o[1] or b[1] >= o[3]
                   for o in obox)

    gap = 12
    room_right = (CHART_X + CHART_W) - (acx + aw / 2)
    room_left = (acx - aw / 2) - CHART_X
    order = [("R", 1), ("L", -1)] if room_right >= room_left else [("L", -1), ("R", 1)]
    for variant, sgn in order:
        bcx = acx + sgn * (aw / 2 + gap + bw / 2)
        for dy in (0.0, bh * 0.35, -bh * 0.35, bh * 0.7):
            if fits(bcx, acy + dy):
                return bcx, acy + dy, variant
    return acx, CHART_Y + CHART_H + bh * 0.55, "U"


# Data is the MAIN CHARACTER and he PERFORMS ON THE DATA. For each beat he is
# staged beside that beat's star data point and given a stat-tied bit that
# matches the depiction — he rides the climbing line to its peak, shoves the
# tallest bar, presents the filling grid. Not parked at the bottom. (Poses come
# from the director; this maps the KIND to the bit + how big he is in-chart.)
_DATA_BIT = {
    "trend":          ("ride_peak", "point"),      # ride up to the line's top
    "timeline":       ("ride_peak", "point"),
    "pictorial_race": ("shove_top", "present_up"), # push the winning bar
    "rank":           ("shove_top", "present_up"),
    "bars":           ("shove_top", "present_up"),
    "comparison":     ("shove_top", "present_up"), # push the bigger column
    "waffle_grid":    ("present_fill", "present_up"),
    "share":          ("present_fill", "present_up"),
    "pictograph":     ("present_fill", "present_up"),
    "bubbles":        ("beside_hero", "point"),
    "geo_world":      ("beside_hero", "point"),
    "geo_us":         ("beside_hero", "point"),
    "geo_city":       ("beside_hero", "point"),
}
IN_CHART_SCALE = 0.66     # smaller so he fits beside a bar without covering it


def _hero_anchor(seg):
    """The STAR data point of a beat — the one Data performs on. The point the
    spoken line names if we can find it, else the peak value (tallest bar /
    highest point / biggest slice)."""
    anchors = getattr(seg, "anchors", None)
    if not anchors:
        return None
    for p in getattr(seg, "punches", []) or []:
        a = _anchor_for_punch(seg, p)
        if a is not None:
            return a
    return max(anchors, key=lambda a: a.get("value", 0.0))


def _stage_on_data(seg, w0, w1, pose, prev_tl, anchors=None):
    """Stage Data ON this beat's winning datum, performing an ANIMATED action on
    it: he SWEEPS in from the smallest datum (setup travel) up onto the winner
    (tallest bar / line peak / biggest slice), where his authored data-action
    (push the bar / ride the line / hoist the slice) loops in place. Feet on the
    element, right edge just LEFT of the tip so he never covers the value number
    (collision rule). ``pose`` is the animated action spec. Returns (seq_tuple,
    entry_xy) or None if the beat has no anchors.

    ``anchors`` overrides the beat's own set, so Data is staged on the
    depiction ACTUALLY on screen for this span. A beat shows several in
    sequence and their geometry differs completely — the peak of a line is
    nowhere near the top bar of a race."""
    anchors = anchors or getattr(seg, "anchors", None)
    # A FULL-FRAME SCENE returns its anchors as 4-tuples, not the label dicts
    # the card charts produce, and this reads them with `.get`. Passing a
    # scene's anchors straight in would raise inside the overlay loop and take
    # the whole render with it — it has not happened only because scenes also
    # set `host_baked`, which skips this path. That is a coincidence, not a
    # guarantee, so drop anything that is not a label dict.
    anchors = [a for a in (anchors or []) if isinstance(a, dict)]
    if not anchors:
        return None
    isc = 0.62
    S = MASCOT_SIZE
    Sk = S * isc

    def _tl(cx, cy):                    # centre -> full-size top-left, clamped
        return (min(max(cx - S / 2, 2.0), float(W - S - 2)),
                min(max(cy - S / 2, 2.0), float(H - S - 2)))

    def _onto(a):                       # stand BESIDE element a, never on it
        # THE OLD ARITHMETIC PUT HIS RIGHT EDGE 15px LEFT OF THE LABEL'S
        # CENTRE — i.e. across its left half. The docstring above always
        # said "right edge just LEFT of the tip so he never covers the value
        # number", and the showrunner read the difference for weeks: "the
        # mascot is parked directly on the '60' value label", "his legs
        # cross through '27.5%'", "'12500' reads '1 0'". Clear the label's
        # LEFT edge by a gap; if that pushes him off the card, stand on its
        # RIGHT edge instead.
        # The sprite is DRAWN at Sk wide from the tuple's top-left (see the
        # overlay loop: `Sk = round(S * sc)` placed at (x, y)), so the
        # geometry is done on the drawn box, not on a full-size centre.
        cx, cy, w, _h = _screen_box(a)
        gap = 14.0
        sprite_left = cx - w / 2.0 - gap - Sk
        if sprite_left < float(CHART_X) + 6.0:
            sprite_left = cx + w / 2.0 + gap
        tlx = min(max(sprite_left, 2.0), float(W - Sk - 2))
        tly = min(max(cy - Sk * 0.40 - S / 2, 2.0), float(H - S - 2))
        return (tlx, tly)

    peak = max(anchors, key=lambda a: a.get("value", 0.0))
    low = min(anchors, key=lambda a: a.get("value", 0.0))
    tlx, tly = _onto(peak)
    entry = _onto(low)                  # sweep up from the smallest datum
    # The authored actions face right/up (push -> extends the bar, ride -> up the
    # slope), so no mirroring.
    return (tlx, tly, w0, w1, SIDE_ANGLE, False, pose, isc), entry


def _piecewise(kfs, axis: int) -> str:
    """Smoothstep ffmpeg expression interpolating x/y across keyframes."""
    ts = [k[0] for k in kfs]
    vs = [k[axis] for k in kfs]
    expr = f"{vs[-1]:.1f}"
    for i in range(len(kfs) - 2, -1, -1):
        t0, t1, v0, v1 = ts[i], ts[i + 1], vs[i], vs[i + 1]
        dt = max(0.001, t1 - t0)
        u = f"clip((t-{t0:.3f})/{dt:.3f},0,1)"
        s = f"({u})*({u})*(3-2*({u}))"
        expr = f"if(lt(t,{t1:.3f}),({v0:.1f}+({v1:.1f}-{v0:.1f})*{s}),{expr})"
    return f"if(lt(t,{ts[0]:.3f}),{vs[0]:.1f},{expr})"


# --------------------------------------------------------------------------
# Composite.
# --------------------------------------------------------------------------
def _scene_metrics(st, slug: str, work: Path, out_path: Path,
                   spans: list | None = None) -> None:
    """Measure each segment AS IT SHIPS and write a scene-addressable verdict.

    This used to encode the segment's chart build ALONE — the PNG sequence over
    a flat colour, no host, no captions, none of the other visuals — and then
    judge it with `temporal_hard_fail`, which is the FULL-VIDEO gate. So it was
    measuring one layer of a composite and grading it against the threshold for
    the finished thing, and it read `gate=fail` on segments of videos the real
    gate passed comfortably: 9.6 and 10.9 fps per segment against a floor of
    11.0, on a master that measured 15.2.

    That is not just noisy logging. The repair loop reads these to decide which
    SCENE to re-plan, so a systematically pessimistic probe sends it to fix
    scenes that are fine, and a green master with three red segments tells the
    next session nothing it can act on. Same defect class as a run that exited
    red whatever happened.

    So it now cuts each segment's window out of the FINISHED master and
    measures that. The number means what it says, and it is comparable with the
    whole-video number because it is the same measurement of the same pixels.
    """
    import glob as _g
    import json as _sj
    import subprocess as _sp
    import tempfile as _tf
    sdir = out_path.parent / "scenes"
    sdir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO))
    try:
        from scripts.showrunner_review import _temporal_evidence, \
            temporal_hard_fail
    except Exception:  # noqa: BLE001
        return
    if not out_path.exists():
        return
    for i, seg in enumerate(st.segments):
        if not seg.chart_path:
            continue
        pat = seg.chart_path
        n = len(_g.glob(pat.replace("%02d", "*")))
        if n < 2:
            continue
        win = (spans[i] if spans and i < len(spans) else None)
        if not win or (win[1] - win[0]) < 0.5:
            continue
        mp4 = work / f"scene_{i:02d}.mp4"
        import shutil as _sh
        _ff = _sh.which("ffmpeg")
        if not _ff:
            try:
                import imageio_ffmpeg
                _ff = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:  # noqa: BLE001
                return
        try:
            _sp.run(
                [_ff, "-y", "-loglevel", "error",
                 "-ss", f"{win[0]:.2f}", "-t", f"{win[1] - win[0]:.2f}",
                 "-i", str(out_path),
                 "-vf", "scale=540:-1", "-an",
                 "-pix_fmt", "yuv420p", str(mp4)], check=True, timeout=180)
            with _tf.TemporaryDirectory() as td:
                ev = _temporal_evidence(mp4, Path(td))
            gate = temporal_hard_fail(ev)
            attach_p = Path(pat.replace("_build%02d.png", "_attach.json"))
            attach = (_sj.loads(attach_p.read_text())
                      if attach_p.exists() else {})
            # SCENE PACKAGE: output/scenes/{slug}/segment_{i}/ holding the
            # scene's own mp4, metrics and a scene-level verdict — the same
            # scene ids the full-video judge references (segN == segment_N).
            seg_dir = sdir / slug / f"segment_{i}"
            seg_dir.mkdir(parents=True, exist_ok=True)
            import shutil as _shm
            _shm.copy2(mp4, seg_dir / "scene.mp4")
            metrics = {"slug": slug, "scene": i, "id": f"segment_{i}",
                       "kind": getattr(seg, "kind", ""),
                       "frames": n, "temporal": ev, "gate": gate or "pass",
                       "effective_fps": ev.get("effective_fps"),
                       "performance": attach.get("performance"),
                       "contact_frames": attach.get("contact_frames"),
                       "timeline": attach.get("timeline")}
            (seg_dir / "metrics.json").write_text(_sj.dumps(metrics))
            # Scene VERDICT — code-graded dimensions (motion/cadence/contact).
            # Perceptual dims (clarity, composition, narrative, payoff,
            # caption interaction) are judged at the full-video level by the
            # vision showrunner referencing these same segment ids; they are
            # explicitly marked unscored here, never silently passed.
            fps = ev.get("effective_fps") or 0.0
            sc_verdict = {
                "id": f"segment_{i}",
                "verdict": "fail" if gate else "pass",
                "gate": gate or "pass",
                "dimensions": {
                    "motion": 3 if fps >= 24 else 2 if fps >= 17 else
                    1 if fps >= 11 else 0,
                    "mascot_contact": 3 if (attach.get("contact_frames", 0)
                                            >= n) else 0,
                    "clarity": None, "data_demonstration": None,
                    "composition": None, "narrative_progression": None,
                    "payoff": None, "caption_interaction": None,
                },
                "unscored_note": "None dims are perceptual — graded by the "
                                 "full-video vision judge against this same "
                                 "segment id",
            }
            (seg_dir / "verdict.json").write_text(_sj.dumps(sc_verdict))
            print(f"[studio] segment_{i} metrics: fps={fps} "
                  f"gate={sc_verdict['gate']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[studio] scene{i} metrics failed: {e}", flush=True)


# A SECOND WAY TO SHOW THE SAME NUMBER.
#
# A video had four "things" in it: three chart cards and a host. Cutting the
# same card into tighter framings does not add a fourth — a punch-in is the
# same subject, closer, and the operator called it: "the jump cut zoom ins are
# not it ... there is like 4 things and then movement, that's not good enough,
# we need 7-8 things".
#
# So each beat now carries TWO depictions of its own number and cuts between
# them: the chart, then the same figure as a stack of objects, a share grid, a
# ranked race. Three beats become six distinct visuals; with the hook image and
# the closing card that is eight things in a 35-second video, and every one of
# them is the data rather than a decoration.
#
# Only contact-verified kinds appear here (viz_director._CONTACT_OK): the host
# must be able to physically attach to whatever is on screen.
_ALT_DEPICTION = {
    "trend":          ("stack", "pictograph", "bars"),
    "timeline":       ("trend", "stack"),
    "bars":           ("pictograph", "stack", "waffle_grid"),
    "rank":           ("pictorial_race", "pictograph", "bars"),
    "pictorial_race": ("bars", "pictograph", "stack"),
    "comparison":     ("stack", "bars", "pictograph"),
    "share":          ("waffle_grid", "pictograph"),
    "waffle_grid":    ("pictograph", "stack"),
    "pictograph":     ("stack", "bars"),
    "stack":          ("pictograph", "bars"),
    "bubbles":        ("pictograph", "bars"),
    "geo_us":         ("pictorial_race", "bars"),
    # The kinds this channel ACTUALLY renders: an authored element-kit scene
    # and the metro map. Both were missing, which is why the first version of
    # this produced no second depiction at all on a real video.
    "scene":          ("trend", "pictorial_race", "bars", "pictograph"),
    "geo_city":       ("pictorial_race", "bars", "pictograph"),
    "geo_world":      ("pictorial_race", "bars"),
}


# Ways of showing a figure that are HONEST for a given shape of data, best
# first. Widening these lists is how a video gets more distinct visuals, so the
# constraint that keeps them short is worth stating plainly: a depiction must
# not assert something the data does not say.
#
#   * `share`, `waffle_grid` and `stack` claim the items are PARTS OF A WHOLE.
#     All three are gone from every list. A ranking of five metros by
#     house-price-to-income shipped with the subtitle "San Jose is 27% of the
#     whole", and a run of mortgage rates by year shipped "2019 IS 9% OF THE
#     WHOLE" — those numbers do not sum to anything, so the sentences are not
#     merely odd, they are false, and they are rendered at 40pt under the
#     title. The first pass here dropped `share` and `waffle_grid` and left
#     `stack`, which makes the identical claim; caught by reading the rendered
#     frames rather than the code. They remain available as a PRIMARY kind for
#     data that genuinely is a composition — this list is only about what a
#     beat may be redrawn AS.
#   * `trend` claims an ORDERED progression. Drawing a ranking of cities as a
#     line says Miami comes after Seattle in some sequence, which is false.
#   * `geo_*` claims the items are PLACES, so it never appears as an alternate
#     for non-geographic data — a map of "cost per year" is a lie with a nice
#     texture.
#
# NOT EVERYTHING HAS TO BE A CHART. Operator: "you don't have to do a fucking
# chart every time. Right? Like, there's millions of ways to convey data." The
# first version of this list was nine chart types, so a video that got its
# variety from here got nine flavours of the same idea. The full-frame
# renderers were sitting right there unused because I had required every
# alternate to be in viz_director._CONTACT_OK — a set that describes CHART
# couplings, while these bake the host in themselves (the primary depiction on
# this channel, `scene`, is one of them and always has been).
#
#   fill_vessel   the number, huge, in a filling gauge ring — the single most
#                 readable thing this system can draw
#   orbit         items as orbiting bodies, each labelled with its value
#   timeline      a value's position on a real number line
#
# Chosen by rendering all eight full-frame renderers on real data and looking
# at the output: these three are fast (0.2-0.3s), need no network, and put the
# number on screen at size. `diorama`, `mechanic`, `scene` and `race` need
# generated imagery — 54-89s per build with HTTP 500s in the middle — so they
# stay primary-only rather than becoming an alternate that can time out.
_SELF_HOSTED = ("fill_vessel", "orbit", "timeline", "units_scene",
                "balance_scene", "rate_scene", "race_scene",
                "staircase_scene", "elevator_scene", "burden_scene",
                "gauge_scene", "skyline_scene", "tower_scene",
                "hurdle_scene", "funnel_scene", "conveyor_scene",
                "pipes_scene", "spotlight_scene", "road_scene",
                "tape_scene", "bridge_scene", "centre_scene",
                "coaster_scene", "thermometer_scene", "wheel_scene",
                "darts_scene", "queue_scene", "bottleneck_scene",
                "leaky_scene", "inout_scene", "sorter_scene", "chain_scene",
                "spinner_scene", "doors_scene", "fan_scene", "gears_scene",
                "slider_scene", "density_scene", "nest_scene",
                "chairs_scene", "hourglass_scene", "trophies_scene",
                "basket_scene")

# Pseudo-kinds that are not renderers but a SCENE the director attaches. They
# resolve to kind "scene" with `insight.scene` set by their builder — see
# viz_director._SCENE_BUILDERS, which is the same mechanism and the reason this
# is a lookup rather than a special case for one name.
_SCENE_TOKENS = {t: t for t in (
    "units_scene", "balance_scene", "rate_scene", "race_scene",
    "staircase_scene", "elevator_scene", "burden_scene",
    "gauge_scene", "skyline_scene", "tower_scene", "hurdle_scene",
    "funnel_scene", "conveyor_scene", "pipes_scene",
    "spotlight_scene", "road_scene", "tape_scene", "bridge_scene",
    "centre_scene", "coaster_scene", "thermometer_scene",
    "wheel_scene", "darts_scene", "queue_scene", "bottleneck_scene",
    "leaky_scene", "inout_scene", "sorter_scene", "chain_scene",
    "spinner_scene", "doors_scene", "fan_scene", "gears_scene",
    "slider_scene", "density_scene", "nest_scene", "chairs_scene",
    "hourglass_scene", "trophies_scene", "basket_scene",
)}

# Depictions that ASSERT A COMPOSITION — that the items are parts of one whole
# — and so may never be chosen as an alternate for data that is not one. Held
# as a set rather than by curating each list, because the shape lists are not
# the only source of candidates: `_ALT_DEPICTION` below is a legacy kind->kind
# lookup that also feeds them, and pruning the lists alone left `stack` coming
# in through the back door and rendering "2019 IS 9% OF THE WHOLE" over a run
# of mortgage rates. A false claim at 40pt under the title is worse than a
# repeated chart, so this is a filter on the pool and not an ordering hint.
_ASSERTS_A_WHOLE = frozenset({"share", "waffle_grid", "stack"})

_SHAPE_CANDIDATES = {
    # values over time: any magnitude comparison is fair, sequence included
    "series": ("trend", "units_scene", "bars", "rate_scene", "balance_scene",
               "timeline", "fill_vessel", "comparison", "pictograph"),
    # named things being compared: anything but a false sequence
    "ranking": ("pictorial_race", "units_scene", "bars", "rate_scene",
                "balance_scene", "fill_vessel", "rank", "orbit", "pictograph",
                "comparison", "bubbles"),
    "other":   ("bars", "units_scene", "rate_scene", "balance_scene",
                "fill_vessel", "pictograph", "orbit", "rank", "bubbles",
                "comparison"),
}


def _shape_of(insight) -> str:
    """Which kind of thing this insight IS, independent of how it is drawn."""
    items = list(getattr(insight, "items", []) or [])
    labels = [str(getattr(p, "label", "")) for p in items]
    years = sum(1 for l in labels if l[:4].isdigit() and len(l) <= 7)
    if years >= max(3, len(labels) * 0.6):
        return "series"
    if 2 <= len(items) <= 6:
        return "ranking"
    return "other"


def _alt_candidates_for(insight) -> tuple:
    """Alternates chosen from the DATA's shape, not just the current kind.

    The lookup table alone missed every real video: the kinds actually in play
    were `scene` (an authored element-kit depiction) and `geo_city` (the metro
    map), neither of which is a chart name. Shape is the durable question —
    a run of years wants a line, a handful of named things wants a race.
    """
    return _SHAPE_CANDIDATES[_shape_of(insight)]


# WHAT THE RELATIONSHIP WANTS TO BE DRAWN AS.
#
# The operator's direction, 2026-09-07: pick the picture from the RELATIONSHIP
# the data expresses, not from the chart kind someone authored — speed becomes
# motion, imbalance becomes weight, rank becomes position, a gap becomes
# literal space. "Data has physics."
#
# So a chart is now the FALLBACK, not the default. This table is consulted
# first; only if nothing here fits, or nothing here can build for this
# particular data, does the ranked chart list below get a say.
#
# The lists are short on purpose. A machine that does not genuinely say the
# thing is worse than a bar chart, because a bar chart at least does not claim
# anything extra — which is why `volatile` maps to a line and always will: a
# series that zig-zags is honestly a line, and drawing it as a climb would be
# a picture of a story the data does not tell.
_MACHINES = {
    # rank -> position, and the gap becomes distance
    # A SKYLINE IS A RANKING, and a shelf of trophies is a ranking of counts
    # — trophies refuses above thirty, which is what keeps it honest here.
    # Both were locked to one rarely-classified relationship each and so led
    # nothing; a ranking is the second-biggest bucket in the catalogue.
    "rank":        ("race_scene", "skyline_scene", "trophies_scene",
                    "units_scene", "orbit"),
    # two THINGS -> weight, or two lanes side by side
    # FIVE, not three. `duel` is 30% of the live catalogue and the three
    # machines it used to name were also named by most of its neighbours, so
    # balance/race/units took HALF of every beat the channel drew while ten
    # machines led nothing at all. The two additions are honest for a pair
    # and both REFUSE what they cannot say — the tape needs two magnitudes it
    # can lay end to end, the nest only draws a ratio between 1.5x and 150x —
    # so a duel they do not fit falls straight through to the other three.
    "duel":        ("balance_scene", "race_scene", "tape_scene",
                    "nest_scene", "units_scene"),
    # a then and a NOW -> the subject itself growing: a stack gaining blocks,
    # a tank filling, or the two weighed against each other
    "before_after": ("tower_scene", "fill_vessel", "balance_scene",
                     "units_scene"),
    # rising -> a climb he has to make, or a total built block by block
    "growth":      ("staircase_scene", "tower_scene", "timeline"),
    # falling -> a lift going down past labelled floors
    "decline":     ("elevator_scene", "timeline", "fill_vessel"),
    # money going up -> weight on him
    "burden":      ("burden_scene", "staircase_scene", "balance_scene"),
    # a share of a countable whole -> figures lit, or one flow splitting
    "share":       ("rate_scene", "pipes_scene", "fill_vessel"),
    # one item dwarfing the rest -> a tower you look UP at
    "dominance":   ("skyline_scene", "nest_scene", "units_scene",
                    "balance_scene"),
    # a line it has to clear -> a hurdle
    "threshold":   ("hurdle_scene", "balance_scene", "units_scene"),
    # stages, each smaller than the last -> a funnel
    "dropoff":     ("funnel_scene", "race_scene", "units_scene"),
    # a rate -> a needle that sweeps
    "rate":        ("gauge_scene", "rate_scene"),
    # a count PER unit of time -> things arriving on a belt
    "frequency":   ("conveyor_scene", "gauge_scene"),
    # NO DIRECTION TO CLAIM. A zig-zag has none, so every other machine here
    # would assert one. A spotlight says only "it was somewhere in this range
    # and it moved around", which is exactly what is true — so `volatile`
    # finally has a picture that is not a lie, having had none at all.
    # NO DIRECTION TO CLAIM. Both of these say only where the number lived and
    # that it moved around — neither asserts where it ended up.
    "volatile":    ("spotlight_scene", "coaster_scene"),
    "uncertainty": ("spotlight_scene",),
    # it barely moved, and that IS the finding
    "stable":      ("road_scene",),
    # the SIZE of a change, drawn as distance
    "delta":       ("tape_scene", "tower_scene", "fill_vessel"),
    # how far SHORT of a line it falls
    "gap":         ("bridge_scene", "hurdle_scene"),
    # where the middle of a spread sits
    "centre":      ("centre_scene", "race_scene"),
    # the rise is compounding, not merely rising
    "acceleration": ("staircase_scene", "tower_scene", "coaster_scene"),
    # it went one way, then turned and stayed turned
    "reversal":    ("coaster_scene", "spotlight_scene", "elevator_scene"),
    # it REPEATS — a stronger claim than volatility, and a wheel is the claim
    "cycle":       ("wheel_scene", "coaster_scene"),
    # they are all basically the same, which a sorted bar chart hides
    "spread":      ("darts_scene", "units_scene"),
    # a backlog: a rising number of things WAITING
    "queue":       ("queue_scene", "units_scene"),
    # ONE step is doing the damage -> a pipe that pinches there. A funnel is
    # the runner-up and not the lead: a funnel says they leak away all the way
    # down, which is a description; a pinch names the culprit.
    "bottleneck":  ("bottleneck_scene", "funnel_scene"),
    # most of it does not stay -> a bucket with a hole in it
    "retention":   ("leaky_scene", "funnel_scene", "rate_scene"),
    # one pipe filling and one draining -> the LEVEL is the story
    "in_out":      ("inout_scene", "balance_scene"),
    # where it WENT, not what it is made of -> parcels dropped into bins
    "routing":     ("sorter_scene", "pipes_scene"),
    # each step hands to the next, so the worst one sets the pace
    "chain":       ("chain_scene", "conveyor_scene", "funnel_scene"),
    # ONE TRIAL, not a share of a population. The dot field lights k figures
    # in n and asserts a countable population; a chance is a single spin. The
    # doors are the same claim told long, and only fit a genuine "1 in n".
    "probability": ("spinner_scene", "doors_scene"),
    # a PROJECTION is not a measurement, and must not join the same line
    "forecast":    ("fan_scene",),
    # the finding is that they move TOGETHER, which two bars cannot say
    "correlation": ("gears_scene", "balance_scene"),
    # every unit of one is a unit of the other you did not get
    "tradeoff":    ("slider_scene", "balance_scene"),
    # the same square, packed differently — the box must NOT also scale
    "density":     ("density_scene", "rate_scene"),
    # how many of the small one fit in the big one, tiled by AREA
    "scale":       ("nest_scene", "skyline_scene"),
    # more claimants than there are places, drawn as people left standing
    "scarcity":    ("chairs_scene", "queue_scene"),
    # a length of TIME, as sand that will not stop falling
    "duration":    ("hourglass_scene", "tape_scene"),
    # a tally where the objects are the point: one cup, one title
    "record":      ("trophies_scene", "units_scene"),
    # what the same money actually buys, which is never the price
    "buying_power": ("basket_scene", "units_scene"),
    # A SPEED IS ALREADY MOTION, so it is run rather than drawn: the lanes
    # ARE the encoding and the fastest is furthest. This is the one place
    # where the race's own rule about a runaway leader is guaranteed to hold,
    # because the router hands dominant sets to the skyline instead.
    "speed":       ("race_scene",),
    # A DISTANCE IS ALREADY A SPAN, and the race encodes value AS distance
    # travelled, which makes it the one picture that needs no translation at
    # all. The tape is second because it states how far APART two numbers are
    # rather than comparing them — true, and a different sentence. Heights and
    # depths never arrive here; the router keeps them for the skyline.
    "distance":    ("race_scene", "tape_scene"),
    "other":       (),
}


# Relationships where the listed machines are EQUALLY apt, so the order is
# arbitrary and rotating it is variety rather than a demotion. Everything not
# here has a definitively right first choice — a duel is a set of scales, a
# zig-zag is a spotlight — and keeps its order.
#
# Measured on the live queue before this existed: `staircase` took all 27
# growth beats and `tower` took none, because a fixed order plus a per-story
# `used` set means the runner-up only ever appears when a story has two beats
# of the same relationship. Four machines were effectively dead.
_ROTATABLE = frozenset({"rank", "growth", "decline", "dominance",
                        "before_after", "share", "duel", "delta", "gap",
                        "centre", "acceleration", "reversal", "volatile",
                        "cycle", "spread", "queue", "routing",
                        "probability", "record", "distance"})


def _machines_for(insight) -> tuple:
    """The physical forms that fit what this data is SAYING, best first.

    A RATE is appended rather than substituted, because it co-occurs: a
    percentage that is also climbing is two true things at once, and a dial
    beside a staircase is a fair second way to show the same beat.
    """
    try:
        from data_learning import relationships as _rel
        _r = _rel.classify(insight)
        out = list(_MACHINES.get(_r, ()))
        if _r in _ROTATABLE and len(out) > 1:
            _k = int(_hashlib.sha1(
                str(getattr(insight, "topic", "") or _r).encode()
            ).hexdigest()[:8], 16) % len(out)
            out = out[_k:] + out[:_k]
        # FREQUENCY and RATE co-occur with everything else: a count per day
        # that is also climbing is two true things at once, and a belt or a
        # dial beside a staircase is a fair second way to show the same beat.
        if _rel.is_frequency(insight):
            for k in _MACHINES["frequency"]:
                if k not in out:
                    out.append(k)
        if _rel.is_rate(insight):
            for k in _MACHINES["rate"]:
                if k not in out:
                    out.append(k)
        return tuple(out)
    except Exception:  # noqa: BLE001 — no router, no machines, still a chart
        return ()


def _family(kind: str) -> str:
    """A chart, or a figure. The distinction the VIEWER makes.

    Axes-and-marks (`bars`, `trend`, `pictorial_race`) all read as "a chart",
    however different they are to draw. A gauge with the number at 200pt, or
    metros orbiting a sun, reads as something else entirely. Alternating
    between the two is what stops a beat from being three charts in a row.
    """
    # Every full-frame renderer counts, not just the three usable as
    # alternates: `scene` is the primary depiction on most beats and it is a
    # figure, so calling it a chart made the alternation start on the wrong
    # foot and hand the beat two figures in a row.
    return ("figure" if (kind in _SELF_HOSTED
                         or kind in charts.FULLFRAME_RENDERERS) else "chart")


def _buildable(kind: str, insight) -> bool:
    """Would this candidate actually produce something for THIS data?

    The scene builders refuse honestly — `rate_scene` will not draw a
    population share for an interest rate, `balance_scene` will not put a
    single item on a two-pan scale. Without asking them first, the pool hands
    a beat a token whose builder returns nothing, the scene fails validation,
    and the render quietly degrades to a chart: a slot spent, no variety, and
    nothing anywhere saying why.
    """
    builder = _SCENE_TOKENS.get(kind)
    if not builder:
        return True
    try:
        from data_learning import viz_scene as _vs
        return bool(getattr(_vs, builder)(insight))
    except Exception:  # noqa: BLE001 — a broken builder is just not offered
        return False


#: A FIELD OF ONE THING REPEATED — thirty thermometers, forty houses, a
#: waffle of little people. Operator, 2026-09-22: "putting a lot of like one
#: thing on the screen ... to simplify like a lot of something. I'm not a big
#: fan of that. That should be used very, very sparingly." So these are the
#: LAST alternates offered, and a video gets at most `REPEATED_ICON_BUDGET`
#: of them however it was reached — the director, an alternate, or a scene
#: the brain authored with a `unit_figures` / `dot_field` element.
REPEATED_ICON_KINDS = frozenset({"units_scene", "rate_scene", "pictograph"})
REPEATED_ICON_ELEMENTS = frozenset({"unit_figures", "dot_field"})
REPEATED_ICON_BUDGET = 1


def is_repeated_icon(kind: str, scene: dict | None = None) -> bool:
    """Does drawing `kind` (with this authored `scene`) fill the frame with
    copies of one icon?"""
    if kind in REPEATED_ICON_KINDS:
        return True
    if kind == "scene" and isinstance(scene, dict):
        return any(isinstance(e, dict) and e.get("type") in REPEATED_ICON_ELEMENTS
                   for e in (scene.get("elements") or []))
    return False


def cover_every_window(kinds, windows, draw, spare, start, log=print) -> list:
    """Render one picture per window, leaving NO window empty.

    `draw(kind, t0, t1, tag, first) -> span dict | None`. A window whose
    picture fails first tries the `spare` candidates for the same window; if
    none builds, the neighbouring picture is re-drawn across both windows (it
    builds for the longer time rather than freezing). Only a beat where
    nothing at all renders is left without spans.
    """
    spare = list(spare)
    out, holes = [], []
    for j, (kind, (t0, t1)) in enumerate(zip(kinds, windows)):
        sp = draw(kind, t0, t1, j, j == 0)
        while sp is None and spare:
            alt = spare.pop(0)
            log(f"visual {j} ({kind}) did not render -> trying {alt} for the "
                f"same window")
            sp = draw(alt, t0, t1, f"{j}s", j == 0)
        if sp is None:
            holes.append((t0, t1))
            continue
        out.append(sp)
    for (h0, h1) in holes:
        prev = next((x for x in out if abs(x["t1"] - h0) < 1e-6), None)
        nxt = next((x for x in out if abs(x["t0"] - h1) < 1e-6), None)
        host = prev or nxt
        if host is None:
            continue
        a0, a1 = (prev["t0"], h1) if prev is not None else (h0, nxt["t1"])
        wide = draw(host["kind"], a0, a1, f"w{len(out)}", a0 == start)
        if wide is not None:
            out[out.index(host)] = wide
            log(f"{host['kind']} widened over the empty window "
                f"{h0:.1f}-{h1:.1f}s")
    out.sort(key=lambda x: x["t0"])
    return out


def _depiction_sequence(insight, used: set, dur: float,
                        cap: int | None = None) -> list:
    """The ORDERED, NON-REPEATING depictions one beat shows, front to back.

    Element 0 is the beat's own chart; the rest are different ways to show the
    SAME number. Each appears exactly once and is retired when its span ends —
    the list is the edit, and the edit only ever moves forward.

    Two preferences, in order. FAMILY ALTERNATION first: after a chart, prefer
    a figure, and after a figure, prefer a chart. Without it the ranked
    candidate lists just hand back their first three entries, which are chart,
    chart, chart — the shape of the bug the operator named ("you don't have to
    do a fucking chart every time"). Then NOVELTY: prefer kinds no beat has
    shown yet, so the third visual is a genuine change of subject rather than
    the neighbouring beat's chart again.

    Length comes from the beat's duration, not a fixed count: a short beat
    stays on one visual rather than being chopped up, which is the "we're
    cutting so much for no reason" half of the ruling.
    """
    kind = str(getattr(insight, "kind", "") or "")
    n = max(1, min(cap or MAX_SPANS, int(round(max(0.0, dur) / SPAN_TARGET))))
    seq = [kind]
    if n == 1:
        return seq
    # RELATIONSHIP FIRST, chart as the fallback — in two TIERS, because the
    # anti-template rotation below must shuffle within a tier and never across
    # it. Rotating one flat list put a chart ahead of the machine that actually
    # said the thing, which is the whole philosophy inverted by a line of
    # variety code.
    machines = [c for c in _machines_for(insight) if c != kind]
    fallback = []
    for c in list(_alt_candidates_for(insight)) + list(
            _ALT_DEPICTION.get(kind, ())):
        if c not in machines and c not in fallback:
            fallback.append(c)
    def _usable(seq):
        return [c for c in seq
                if c and c != kind and c not in _ASSERTS_A_WHOLE
                and _buildable(c, insight)]

    machines, fallback = _usable(machines), _usable(fallback)
    # A repeated-icon grid is the LAST thing offered, and not at all once
    # this video has had its one (`used` carries the marker the render loop
    # adds when it draws one).
    _icon_spent = "__repeated_icon__" in used
    _icons = [c for c in machines + fallback if c in REPEATED_ICON_KINDS]
    machines = [c for c in machines if c not in REPEATED_ICON_KINDS]
    fallback = [c for c in fallback if c not in REPEATED_ICON_KINDS]
    # ROTATE THE PREFERENCE, or the ranked list is itself a template.
    #
    # Simulated across the 74 un-posted stories: every single one picked
    # units_scene, then balance_scene, then fill_vessel — because a fixed
    # ranking plus a per-story `used` set produces the same three in the same
    # order every time. Better than three charts, and still a fingerprint:
    # every video would open its second beat on an isotype.
    #
    # Rotating by the beat's own topic varies it story to story AND beat to
    # beat while staying deterministic, so a re-render is identical and the
    # novelty/family rules below are untouched.
    def _rotate(seq):
        if len(seq) < 2:
            return seq
        r = int(_hashlib.sha1(
            str(getattr(insight, "topic", "") or kind).encode()
        ).hexdigest()[:8], 16) % len(seq)
        return seq[r:] + seq[:r]

    # THE MACHINE ORDER IS EDITORIAL, NOT ARBITRARY — so it is NOT rotated.
    # For a duel the scales are simply the right picture, and rotating them
    # away for variety demoted the form that actually said the thing. The
    # variety comes from the RELATIONSHIPS varying across beats (rank -> race,
    # duel -> scales, growth -> a count, decline -> a timeline), which is the
    # data driving the picture, which is the entire point. Only the chart
    # fallback rotates, because there one bar chart is much like another.
    cands = machines + _rotate(fallback) + ([] if _icon_spent else _icons[:1])

    def _pick(want_family, avoid_used):
        for c in cands:
            if c in seq:
                continue
            if c in REPEATED_ICON_KINDS and any(
                    k in REPEATED_ICON_KINDS for k in seq):
                continue
            if want_family and _family(c) != want_family:
                continue
            if avoid_used and c in used:
                continue
            return c
        return None

    while len(seq) < n:
        want = "figure" if _family(seq[-1]) == "chart" else "chart"
        # Alternate family AND stay novel; then give up novelty (another beat's
        # kind still beats a third chart in a row); then give up alternation
        # rather than return a short sequence.
        c = (_pick(want, True) or _pick(want, False)
             or _pick(None, True) or _pick(None, False))
        if c is None:
            break
        seq.append(c)
    return seq


#: Config segments whose `scene` was written by the renderer this run —
#: `_save_persisted_mechanics` flushes them to disk once, after the loop.
_PERSISTED: list = []


def _persist_rendered_mechanic(insight, slug: str,
                               rendered_as: str | None = None) -> None:
    """The moment a brain mechanic is COMMITTED to a render, write it down.

    THE BEST ANIMATION ON THE CHANNEL WAS LOST FROM EVERY PLACE THE BRAIN
    LEARNS FROM. `fusion-net-energy-gain`, 2026-09-16: the showrunner called
    its bolt-per-0.2-megajoule grid "a genuinely good demonstration" twice,
    blocked it twice on craft alone, and the run that finally shipped had
    re-invented the story from scratch without it. Today its code is in
    neither the config, nor the 60-slot library, nor the ledger, nor git.
    The operator, asked what makes a video work: "that laser one".

    Three separate mechanisms let it vanish, and this is the fix for the
    first: NOTHING IN CODE PERSISTED A MECHANIC THAT RENDERED. The only
    caller of `_record_mechanic` is the render-time invention pass, which is
    OFF in CI; the pre-render brain is asked to save its work by a line in a
    prompt, inside a 720-second budget. A capability that depends on a
    headless model remembering step 5 is not a capability.

    So the renderer does it, here, at the one point where it is certain the
    mechanic drew: `render_story_build` returned frames for kind "mechanic".
    Two writes, both idempotent:

      * the LIBRARY (`viz_director._record_mechanic`, dedup by signature,
        `moves: True` because the motion probe just passed it) — so the next
        brain studies it as an example;
      * the CONFIG SEGMENT it came from, via the pointer `story.build` set,
        never by index (that function reorders and drops segments) — so the
        next run RE-RENDERS the same animation through the now-measured
        sandbox instead of re-inventing, and a craft block costs a repair,
        not the idea. `_save_persisted_mechanics` flushes once per render.

    Never raises: losing a record is bad, losing a render over it is worse.
    """
    try:
        sc = getattr(insight, "scene", None)
        if not (isinstance(sc, dict) and sc.get("code")):
            return
        try:
            from data_learning import viz_director as _vd
            _vd._record_mechanic(insight, sc)
        except Exception as e:  # noqa: BLE001
            print(f"[studio] library record skipped: {e}", flush=True)
        cfg_seg = getattr(insight, "seg_cfg", None)
        if isinstance(cfg_seg, dict):
            keep = {k: sc[k] for k in ("mechanic", "concept", "code") if k in sc}
            # The judge grades by RENDERED segment id ("seg1"), and
            # `story.build` reorders, so the config segment carries the id it
            # rendered as — that is how a grade finds its way back to the
            # mechanic it was about (`viz_director.grade_mechanics`).
            if rendered_as:
                keep["rendered_as"] = rendered_as
            if isinstance(cfg_seg.get("scene"), dict) and cfg_seg["scene"].get("grade"):
                keep["grade"] = cfg_seg["scene"]["grade"]   # never lose a grade
            if cfg_seg.get("scene") != keep:
                cfg_seg["scene"] = keep
                _PERSISTED.append(slug)
    except Exception as e:  # noqa: BLE001
        print(f"[studio] mechanic persist skipped: {e}", flush=True)


def _save_persisted_mechanics(config_path: Path, story_cfg: dict, slug: str) -> None:
    """Flush any `scene` written by `_persist_rendered_mechanic` to the config
    file — ONE read-modify-write per render, touching only this story, so a
    concurrent author's edits to other stories survive. The workflow's
    persist step commits the file; that is what makes it durable."""
    if slug not in _PERSISTED:
        return
    try:
        _PERSISTED[:] = [x for x in _PERSISTED if x != slug]
        cfg = json.loads(Path(config_path).read_text())
        for st_ in cfg.get("stories", []):
            if st_.get("slug") != slug:
                continue
            for a, b in zip(st_.get("segments", []), story_cfg.get("segments", [])):
                if isinstance(b.get("scene"), dict) and b["scene"].get("code"):
                    a["scene"] = b["scene"]
                if b.get("illustrated_scene"):          # a verified brain scene
                    a["illustrated_scene"] = b["illustrated_scene"]
            for k in ("closing_scene", "closing_data",     # its bookends
                      "hook_scene", "hook_data"):
                if story_cfg.get(k) is not None:
                    st_[k] = story_cfg[k]
            break
        Path(config_path).write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        print(f"[studio] persisted rendered mechanic(s) for '{slug}' to "
              f"{Path(config_path).name}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[studio] mechanic save skipped: {e}", flush=True)


def _resolve_scene(slug: str, story_cfg: dict, i: int, insight):
    """Beat i's subject scene: saved code first (a brain draft, or a REDRAW
    that beat the teacher under the keep-best rule, scripts/scene_redraw.py),
    then the hand-drawn teacher, then a fresh brain draft — verified — or
    None."""
    from data_learning import scene_author as _sa
    from data_learning import subject_scenes as _ss
    segs = story_cfg.get("segments") or []
    seg_cfg = segs[i] if i < len(segs) else {}
    log = (lambda m: print(f"[studio] seg{i}: {m}", flush=True))
    scene = _sa.saved_scene(seg_cfg, log=log)
    if scene is None:
        scene = _ss.scene_for(slug, i)
    if scene is None:
        had = bool(seg_cfg.get("illustrated_scene"))
        scene = _sa.scene_for_segment(story_cfg, i, insight, log=log)
        if scene is not None and not had:
            _PERSISTED.append(slug)
    return scene


def render(slug: str, out_path: Path, voice: str | None = None,
           config_path: Path | None = None) -> Path:
    """`config_path` lets a sibling channel (e.g. curiosity) render from its
    own story config; default stays the explainer's niche.config.json."""
    config_path = Path(config_path) if config_path else PKG_DIR / "niche.config.json"
    cfg = json.loads(config_path.read_text())
    story_cfg = next((s for s in cfg.get("stories", []) if s["slug"] == slug), None)
    if not story_cfg:
        raise KeyError(f"no story with slug {slug!r} in {config_path.name}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-video theme: chart palette, background gradient, bokeh, voice — so no
    # two uploads look or sound like the same stamped-out template.
    theme = _theme_for(slug)
    # THE ACCENT COMES FROM THE DESIGN SYSTEM — see THEMES above for what
    # this replaced. `accent_for` is deterministic per slug, so the channel
    # still has variety ACROSS videos and none WITHIN one, which is the rule.
    # WARN is NOT themed: it is the semantic alarm colour, and a baseline
    # warning that is teal on one video and amber on the next says nothing
    # by being either.
    charts.HIGHLIGHT, charts.ACCENT = (
        _hex(c) for c in _look.accent(_look.accent_for(slug)))
    accent_ass = _hex_to_ass(_readable_punch(charts.HIGHLIGHT))
    # WHICH LOOK — the A/B arm, from the registry (shared/style_arms.py).
    from shared import style_arms as _style_arms
    try:                          # a new video: no gesture used yet
        from data_learning import subject_scenes as _ss0
        _ss0.reset_acts()
    except Exception:  # noqa: BLE001 — no pycairo: no subject scenes either
        pass
    _style = {"style_arm": _style_arms.choose(slug),
              "illustrated_beats": [], "fallback_beats": []}
    print(f"[studio] style arm: {_style['style_arm']}", flush=True)
    if voice is None:
        voice = theme["voice"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        st = story.build(story_cfg, cfg, work, REPO)
        # SCENE PLAN: apply any repaired scene choices (state/scene_plans/{slug}
        # .json, written by scripts/scene_repair.py keep-best selection). A plan
        # LOCKS that segment's kind + performance — scene-addressable repair,
        # not a whole-video reroll.
        try:
            _pf = REPO / "state" / "scene_plans" / f"{slug}.json"
            if _pf.exists():
                import json as _pj
                _plan = _pj.loads(_pf.read_text())
                for _i, _seg in enumerate(st.segments):
                    _p = _plan.get(str(_i))
                    if _p and getattr(_seg, "insight", None):
                        _seg.insight.kind = _p["viz"]
                        _seg.insight.plan_locked = True
                        _seg.insight.perf_override = _p.get("perf")
                        _seg.kind = _p["viz"]
                        print(f"[studio] scene plan seg{_i}: "
                              f"{_p['viz']}+{_p.get('perf')}", flush=True)
        except Exception as e:  # noqa: BLE001 — a bad plan never kills a render
            print(f"[studio] scene plan skipped: {e}", flush=True)
        # Custom thumbnail next to the video (title-aligned packaging). Cheap —
        # reuses the already-built story; the uploader picks it up by path.
        try:
            make_thumbnail(st, theme, out_path.with_suffix(".jpg"))
        except Exception as e:  # noqa: BLE001 — never fail a render over a thumb
            print(f"[studio] thumbnail skipped: {e}", file=sys.stderr)
        sentences = st.sentences()
        narration, windows = synth_narration(sentences, work, voice)
        total = _dur(narration) + 0.3

        # HOOK VISUAL: a receipt cold-open (built from the story's own data) when
        # the data supports it. Computed HERE (before the 30fps re-render) so the
        # opening chart can LEAD the hook when there is no receipt — otherwise the
        # hook is ~3s of a mascot on the gradient with no data on screen, which is
        # the empty_void / decorative_mascot the gate blocks. The data
        # demonstration should be the star from frame 1.
        receipt = _build_hook_receipt(story_cfg, work, slug,
                                      hook_dur=windows[0][1] - windows[0][0])
        lead_hook = receipt is None          # seg0's chart carries the cold-open

        # ONE VIDEO, ONE LOOK. Every beat's subject scene is found BEFORE the
        # render — saved code, then the teacher, then a brain draft — and if
        # any beat has none, the whole video renders in the current look. A
        # beat that fell back alone put an old chart between drawn scenes
        # (kelp, 2026-09-23): two looks in one video is a craft defect the
        # judge takes points for, whichever look is better.
        _prepared: dict = {}
        if _style["style_arm"] == "illustrated":
            for _i, _sg in enumerate(st.segments):
                if not getattr(_sg, "insight", None):
                    continue
                _got = _resolve_scene(slug, story_cfg, _i, _sg.insight)
                if _got is None:
                    _style["style_arm"] = "current"
                    _style["illustrated_fallback"] = f"beat {_i}: no verified scene"
                    print(f"[studio] style arm: current — beat {_i} has no "
                          f"verified subject scene, and one video has one look",
                          flush=True)
                    _prepared = {}
                    break
                _prepared[_i] = _got

        # TRUE 30fps: re-render each chart at frames = span*30 now that the beat
        # length is known, so the build animates smoothly across the WHOLE window
        # (no held/duplicate frames — the choppiness the temporal grade caught).
        # seg0 spans hook+seg0 when it leads the hook, so it builds continuously
        # from frame 1 with no frozen hook.
        # The LAST chart likewise spans its beat + the CLOSING when there's no
        # receipt, so the payoff isn't a mascot-on-void either — a data recap
        # holds the frame while Data lands the takeaway.
        lead_payoff = receipt is None
        last_i = len(st.segments) - 1
        chart_dir = work / "charts"
        # Kinds already on screen in THIS video, so a second depiction is a
        # genuine change of subject and not the neighbouring beat's chart again.
        _kinds_used: set = {str(getattr(sg, "insight", None)
                                and sg.insight.kind or "")
                            for sg in st.segments}
        disp_start: dict = {}                 # per-seg chart DISPLAY start (s0)
        disp_end: dict = {}                   # per-seg chart DISPLAY end (s1)
        for i, seg in enumerate(st.segments):
            wi = windows[1 + i] if 1 + i < len(windows) else None
            if not (wi and getattr(seg, "insight", None) and seg.chart_path):
                continue
            start = windows[0][0] if (i == 0 and lead_hook) else wi[0]
            end = windows[-1][1] if (i == last_i and lead_payoff) else wi[1]
            disp_start[i] = start
            disp_end[i] = end
            import math as _mfr
            # THE BEAT'S VISUALS — a forward-only sequence, one per span.
            #
            # Each depiction is built for EXACTLY its own span and positioned on
            # the timeline at its own t0, so no build is ever asked to hold a
            # frame it does not have. That is also the fix for the freeze: the
            # previous design laid every depiction from the BEAT's start, so a
            # build shorter than the beat ran out and ffmpeg's tpad cloned its
            # last frame for 3.0 seconds (73 duplicates against a ceiling of
            # 45). Per-span framing makes that unrepresentable rather than
            # merely fixed.
            #
            # Cap 1200 frames (=40s) is a safety bound, not a rate limiter.
            dur = max(0.0, end - start)
            # THE ILLUSTRATED ARM (shared/style_arms.py, docs/CHANNEL_LOOK.md
            # §Worlds). The beat is ONE illustrated world when its claim has
            # an illustrated drawing; otherwise it falls back to the current
            # pictures below, and the fallback is recorded with its claim.
            if _style["style_arm"] == "illustrated":
                from data_learning import illustrated as _il
                from data_learning import subject_scenes as _ss
                from data_learning import scene_author as _sa
                # A SUBJECT SCENE first (operator 2026-09-23: the reference
                # is the subject itself, not a chart in a world); the
                # illustrated chart drawings only where no scene exists.
                _scene = _prepared.get(i)
                # THE CLOSING IS ITS OWN SCENE. The last beat used to run on
                # under the closing, shrunk into an inset beneath a bordered
                # bubble; the showrunner gave that payoff 1/2 on the 74
                # ("a static reprise under a text card ... nothing shows
                # 'the bill still grows'"). The last beat now stops where
                # the closing starts and the closing line gets a picture.
                # THE HOOK IS ITS OWN SCENE TOO: the first seconds state the
                # story's surprise as a picture, instead of opening on the
                # first beat's machine ("the hook uses the same machine as
                # seg1, so the opening and the first data beat look the
                # same" — showrunner, 2026-09-23).
                _hook, _hpath = None, None
                if (i == 0 and lead_hook and _scene is not None
                        and windows[0][1] - start >= 1.0
                        and end - windows[0][1] >= 2.0):
                    _hook = (_sa.saved_bookend(story_cfg, "hook", len(st.segments))
                             or _ss.hook_for(slug))
                    if _hook is None:
                        _hadh = bool(story_cfg.get("hook_scene"))
                        _hook = _sa.scene_for_bookend(
                            story_cfg, "hook", [sg.insight for sg in st.segments],
                            log=lambda m: print(f"[studio] hook: {m}", flush=True))
                        if _hook is not None and not _hadh:
                            _PERSISTED.append(slug)
                if _hook is not None:
                    _h1 = windows[0][1]
                    try:
                        _hfn, _hidx = _hook
                        _hpath, _ = _ss.render_build(
                            _hfn, st.segments[_hidx].insight, chart_dir,
                            f"{slug}_hook_ss",
                            int(max(30, min(1800, _mfr.ceil((_h1 - start) * 30)))),
                            t0=start)
                    except Exception as e:  # noqa: BLE001
                        print(f"[studio] hook scene failed: {e}", flush=True)
                        _hpath = None
                    if _hpath:
                        _hspan = {"kind": "subject_scene", "path": _hpath,
                                  "anchors": [], "t0": start, "t1": _h1,
                                  "full_by": 1.0, "host_baked": True,
                                  "scene": _hfn.__name__}
                        start = _h1
                        dur = max(0.0, end - start)
                _close = None
                if i == last_i and lead_payoff and windows[-1][0] > start + 1.0:
                    _close = (_sa.saved_closing(story_cfg, len(st.segments))
                              or _ss.closing_for(slug))
                    if _close is None:
                        _hadc = bool(story_cfg.get("closing_scene"))
                        _close = _sa.scene_for_closing(
                            story_cfg, [sg.insight for sg in st.segments],
                            log=lambda m: print(f"[studio] closing: {m}",
                                                flush=True))
                        if _close is not None and not _hadc:
                            _PERSISTED.append(slug)
                _cpath = None
                if _scene is not None and _close is not None:
                    _c0 = windows[-1][0]
                    try:
                        _cfn, _cidx = _close
                        _cpath, _ = _ss.render_build(
                            _cfn, st.segments[_cidx].insight, chart_dir,
                            f"{slug}_closing_ss",
                            int(max(30, min(1800, _mfr.ceil((end - _c0) * 30)))),
                            t0=_c0)
                    except Exception as e:  # noqa: BLE001
                        print(f"[studio] closing scene failed: {e}", flush=True)
                        _cpath = None
                    if _cpath:
                        end = _c0
                        dur = max(0.0, end - start)
                if _scene is not None:
                    try:
                        _spath, _ = _ss.render_build(
                            _scene, seg.insight, chart_dir,
                            f"{slug}_seg{i:02d}_ss",
                            int(max(30, min(1800, _mfr.ceil(dur * 30)))),
                            t0=start)
                    except Exception as e:  # noqa: BLE001
                        print(f"[studio] seg{i} subject scene failed: {e}",
                              flush=True)
                        _spath = None
                    if _spath:
                        seg.spans = [{"kind": "subject_scene", "path": _spath,
                                      "anchors": [], "t0": start, "t1": end,
                                      "full_by": 1.0, "host_baked": True,
                                      "scene": _scene.__name__}]
                        if _hpath:
                            seg.spans.insert(0, _hspan)
                            print(f"[studio] hook: subject scene "
                                  f"{_hspan['scene']}", flush=True)
                        if _cpath:
                            seg.spans.append(
                                {"kind": "subject_scene", "path": _cpath,
                                 "anchors": [], "t0": end,
                                 "t1": windows[-1][1], "full_by": 1.0,
                                 "host_baked": True,
                                 "scene": _close[0].__name__})
                            _style["closing_scene"] = True
                            print(f"[studio] closing: subject scene "
                                  f"{_close[0].__name__}", flush=True)
                        seg.chart_path = _spath
                        _style["illustrated_beats"].append(i)
                        _style.setdefault("scene_beats", []).append(i)
                        print(f"[studio] seg{i}: subject scene "
                              f"{_scene.__name__} ({dur:.1f}s)", flush=True)
                        continue
                _rel, _ifn = _il.drawing_for(seg.insight)
                _ipath, _ianc = None, []
                if _ifn is not None:
                    _ifb = _full_by(
                        dur, CLOSING_STILL_TAIL
                        if (windows and end - windows[-1][0] > 0.35)
                        else MAX_STILL_TAIL)
                    try:
                        _ipath, _ianc = _il.render_build(
                            seg.insight, chart_dir, f"{slug}_seg{i:02d}_il",
                            frames=int(max(30, min(1800, _mfr.ceil(dur * 30)))),
                            full_by=_ifb, draw=_ifn, t0=start,
                            world=_il.world_for_story(st))
                    except Exception as e:  # noqa: BLE001
                        print(f"[studio] seg{i} illustrated skipped: {e}",
                              flush=True)
                if _ipath:
                    seg.spans = [{"kind": "illustrated", "path": _ipath,
                                  "anchors": _ianc, "t0": start, "t1": end,
                                  "full_by": float(_ifb), "host_baked": True,
                                  "world": _il.world_for_story(st),
                                  "drawing": _ifn.__name__}]
                    seg.chart_path = _ipath
                    _style["illustrated_beats"].append(i)
                    print(f"[studio] seg{i}: illustrated {_ifn.__name__} in "
                          f"{_il.world_for_story(st)} ({dur:.1f}s)",
                          flush=True)
                    continue
                _style["fallback_beats"].append(
                    {"seg": i, "relationship": _rel,
                     "why": "no illustrated drawing" if _ifn is None
                     else "illustrated render failed"})
                print(f"[studio] seg{i}: illustrated arm FELL BACK to the "
                      f"current look (claim {_rel!r})", flush=True)
            kinds = _depiction_sequence(seg.insight, _kinds_used, dur)
            spans = _visual_spans(start, end, len(kinds))
            seg.spans = []
            _orig_kind = seg.insight.kind

            def _draw(kind, t0, t1, tag, first):
                """Render `kind` for exactly [t0, t1]; the span dict, or None."""
                nfr = int(max(30, min(1200, _mfr.ceil((t1 - t0) * 30))))
                cpath, anc = None, []
                _fb = 1.0
                # Per-span truth: the renderer SETS this while it draws Data
                # into the visual (every chart's `_bake_host`, every
                # self-hosting machine in `render_scene`). Cleared before each
                # span so the answer belongs to THIS span, not to whatever
                # rendered before it on the same insight (`_span_bakes`).
                seg.insight.host_baked = False
                _icon_kind = is_repeated_icon(
                    kind, getattr(seg.insight, "scene", None)
                    if kind == "scene" else None)
                if _icon_kind and "__repeated_icon__" in _kinds_used:
                    # this video already had its one field of copies
                    print(f"[studio] seg{i} visual {tag} ({kind}) is a field "
                          f"of one repeated icon and this video has had its "
                          f"one", flush=True)
                    return None
                try:
                    seg.insight.kind = kind
                    if kind in _SCENE_TOKENS:
                        # A scene token is a BUILDER, not a renderer: attach the
                        # spec it produces and render as kind "scene".
                        from data_learning import viz_scene as _vs
                        seg.insight.scene = getattr(
                            _vs, _SCENE_TOKENS[kind])(seg.insight)
                        seg.insight.kind = "scene"
                    # Build LINEARLY across the WHOLE span (no early
                    # completion): the chart keeps moving for as long as it is
                    # on screen, so there is never a finished-and-held stretch
                    # (that was the dead_air / 5fps).
                    _fb = _full_by(
                        t1 - t0,
                        CLOSING_STILL_TAIL
                        if (windows and t1 - windows[-1][0] > 0.35)
                        else MAX_STILL_TAIL)
                    cpath, anc = charts.render_story_build(
                        seg.insight, chart_dir, f"{slug}_seg{i:02d}_v{tag}",
                        frames=nfr,
                        full_by=_fb,
                        # only the opening visual bursts up out of the hook
                        hook_lead=(i == 0 and lead_hook and first))
                except Exception as e:  # noqa: BLE001 — a missing extra visual
                    print(f"[studio] seg{i} visual {tag} ({kind}) skipped: {e}",
                          flush=True)
                finally:
                    seg.insight.kind = _orig_kind
                if not cpath:
                    return None
                if kind == "mechanic":
                    _persist_rendered_mechanic(seg.insight, slug,
                                               rendered_as=f"seg{i}")
                _kinds_used.add(kind)
                if _icon_kind:
                    _kinds_used.add("__repeated_icon__")
                return {"kind": kind, "path": str(cpath),
                        "anchors": anc, "t0": t0, "t1": t1,
                        # when this build reaches its final frame —
                        # the ring waits for it (`_plan_events`)
                        "full_by": float(_fb),
                        "host_baked": bool(getattr(seg.insight,
                                                   "host_baked", False))}

            # A WINDOW THAT FAILED TO RENDER IS NEVER LEFT EMPTY.
            #
            # Every span is laid at its own t0 and enabled only for its own
            # window, so a picture that failed simply left its window with
            # nothing in it: "seg3:end (t=32.92s) is a completely empty
            # gradient frame with only the caption 'that should worry'. The
            # whole picture drops out while the narration is at its key line"
            # (teen-ai-companion-boom, three verdicts, 2026-09-22/23). A failed
            # window first tries the next candidate for the SAME window; if
            # none builds, the neighbouring picture is re-rendered across both
            # windows, so it builds for the longer time instead of freezing.
            _spare = [c for c in _depiction_sequence(
                seg.insight, set(_kinds_used), SPAN_TARGET * 8, cap=8)[1:]
                if c not in kinds][:3]
            seg.spans = cover_every_window(
                kinds, spans, _draw, _spare, start,
                log=lambda m: print(f"[studio] seg{i}: {m}", flush=True))
            seg.spans.sort(key=lambda x: x["t0"])
            if seg.spans:
                seg.chart_path = seg.spans[0]["path"]
            if seg.spans:
                print(f"[studio] seg{i}: "
                      + " -> ".join(f"{sp['kind']}({sp['t1'] - sp['t0']:.1f}s)"
                                    for sp in seg.spans), flush=True)
        _save_persisted_mechanics(config_path, story_cfg, slug)

        # SCENE-ADDRESSABLE METRICS: encode each scene's build alone and run the
        # reviewer's own cadence detector + the build-time temporal gate on it,
        # writing output/scenes/{slug}_sceneN.json. When a video fails, the
        # repair loop reads these to target the failing SCENE instead of
        # re-rolling the whole video; they also make every scene debuggable.
        # (scene metrics run AFTER the master exists — see the call below the
        # final encode; measuring the build alone graded one layer of a
        # composite against the finished video's threshold.)

        bokeh = ambient.make_bokeh_strip(work / "bokeh.png", seed=theme["seed"])
        footmask = work / "foot_mask.png"
        _make_mandel_mask(footmask, W, FOOT_H, feather=130, bottom=70)
        events = _plan_events(st, windows)
        # Full soundtrack: narration + ducked theme music + visual-synced SFX.
        soundtrack = _build_soundtrack(narration, windows, events, total,
                                       theme.get("vibe", "calm"), work, slug)
        # A full-frame receipt suppresses the hook TEXT — it IS the open. With
        # no receipt, seg0's chart leads and the hook text plays over it.
        ass = work / "cap.ass"
        build_story_ass(st, windows, events, ass, accent=accent_ass,
                        hook_visual=bool(receipt),
                        closing_scene=bool(_style.get("closing_scene")),
                        scene_beats=frozenset(_style.get("scene_beats") or ()))
        ass_esc = str(ass).replace("\\", "/").replace(":", "\\:")

        # Ordered mascot sequence: hook (up, centred), one per number (tucked
        # beside it, pointing at it, never covering a number), then closing.
        S = MASCOT_SIZE
        import os as _osm
        _clean = _osm.environ.get("LEGACY_LOOK") != "1"
        # The action DIRECTOR puts Data INTO each scene doing a topic-specific
        # thing (juggling eggs, on the soup cans, shoving the cart, riding the
        # chart) instead of a generic reaction. Optional — if it or its SVG
        # rasteriser is unavailable the seq carries plain pose names and the
        # host still renders, just without props.
        try:
            from data_learning import mascot_director as _director
        except Exception:  # noqa: BLE001
            _director = None

        def _seg_spec(i):
            """A director spec for segment i (its whole beat), or a pose name.
            Gauge beats bake Data INTO the chart (he rides the arc), so the
            travelling overlay is hidden there to avoid a duplicate mascot."""
            # Whether the overlay is HIDDEN for a beat is decided per SPAN in
            # the loop below (`_span_bakes`): a beat that shows a machine and
            # then a mechanic needs Data hidden for the first and drawn for
            # the second. This only authors WHAT he does.
            if not _director:
                return ("point", "shock", "point", "think")[i % 4]
            try:
                seg = st.segments[i]
                val = ""
                if getattr(seg, "anchors", None):
                    v = seg.anchors[0].get("value")
                    if v is not None:
                        val = story._fmtnum(v)
                # Per-scene performance: a bespoke pose generated for THIS beat
                # (brain-authored when MASCOT_BRAIN is on, else a distinct preset
                # rotated by scene index so no two beats reuse the same act).
                return _director.author_performance(
                    subject=f"{seg.topic} {seg.sentence}", label=seg.topic,
                    value=val, kind=getattr(seg, "kind", ""), index=i)
            except Exception:  # noqa: BLE001
                return "shock"

        if _clean:
            # MASCOT-FIRST composition. Data is the camera: the video is built
            # around WHERE HE IS and WHAT HE'S DOING. He is NEVER parked — each
            # beat sends him to a different spot and he TRAVELS there across the
            # whole beat (see the overlay glide below), so his x/y is always
            # changing (never static >4s): he paces side to side, rides UP into
            # the chart on data beats, walks the cart across. Action per beat
            # comes from the director; position comes from this trajectory.
            gap_fill = _director.default_host() if _director else "idle"
            nseg = len(st.segments)
            Cx = float((W - S) // 2)
            # A card chart lives in the TOP region; the space BELOW it used to be
            # dead black. Data works that lower "stage" — he never stands on the
            # chart (covering the data), he fills the bottom and presents it from
            # below. He paces across the stage (x alternates) so he keeps moving.
            stage_y = min(float(CHART_Y + CHART_H + 8), float(H - S - 120))
            Lx, Rx = 60.0, float(W - S - 60)

            def _spot(i, action):
                if action == "ride":                 # ride UP into the chart
                    return Rx if i % 2 else Lx, float(H * 0.24)
                x = Lx if i % 2 == 0 else Rx          # pace across the stage
                return x, stage_y

            # HOOK: Data REACTS with a bespoke bit. When a visual fills the top
            # (the receipt, OR the opening chart leading the hook) he presents it
            # from the lower stage at normal size — big enough to read, not so big
            # he covers the data. With NO top visual he is the central hero, large.
            hook_leads = bool(receipt) or lead_hook
            hook_y = stage_y if hook_leads else float(H * 0.40)
            hook_scale = 1.0 if hook_leads else 1.45
            home = (Cx, hook_y)
            hook_perf = gap_fill
            if _director:
                try:
                    hnum = _headline_number(st) or ""
                    hook_perf = _director.author_performance(
                        subject=f"{st.hook} {st.title}", label="",
                        value=hnum, kind="hook", index=nseg + 1)
                except Exception:  # noqa: BLE001
                    hook_perf = gap_fill
            seq = []
            # Data no longer glides — he is PLACED at each cut (see the
            # overlay loop). `_stage_on_data` still returns the old sweep-in
            # point; it is accepted and ignored so the staging helpers keep one
            # signature.
            def _add(entry_tuple, _entry_xy=None):
                seq.append(entry_tuple)

            # When the opening chart leads the hook, Data performs ON it from
            # frame 1 (sweeping onto its star datum) instead of standing below it.
            staged_hook = None
            def _act(seg, phase="action"):
                # THE DIRECTOR ALREADY CHOSE, PER BEAT — honour it.
                #
                # `viz_director.assign` runs `performance_for` over the whole
                # story with an anti-repetition set, so beat 0 gets block_wall,
                # beat 1 shoved_bar, beat 2 race_sprint and so on. This
                # function threw that away and asked `data_action_spec(kind)`
                # instead, which is keyed on the CHART KIND — and bars,
                # comparison, rank and pictorial_race all map to `push_bar`,
                # so a story of three ranking beats got the identical pose
                # three times. `scene` is not in that map at all, so every
                # machine beat fell through to `push_bar` too.
                #
                # The showrunner blocked a video for exactly this on
                # 2026-09-07: "Data holds the same arms-out standing pose in
                # hook@0.3, seg1:mid, seg2:end, seg3:start and seg4:mid — only
                # rescaled and re-parked on the bar tip".
                #
                # The payoff still celebrates: that is the beat landing, not a
                # repeat.
                if phase == "payoff":
                    if _director and hasattr(_director, "data_action_spec"):
                        return _director.data_action_spec(
                            getattr(seg, "kind", ""), phase)
                    return "cheer"
                ins = getattr(seg, "insight", None)
                chosen = getattr(ins, "perf_spec", None) if ins else None
                if isinstance(chosen, dict) and chosen.get("action"):
                    return chosen
                chosen = getattr(ins, "perf_override", None) if ins else None
                if chosen:
                    return chosen
                kind = getattr(seg, "kind", "")
                if _director and hasattr(_director, "data_action_spec"):
                    return _director.data_action_spec(kind, phase)
                # `point_at`, not `point` — the latter is not in `ANIMATORS`
                # and resolves to the generic carry pose, which is the thing
                # this whole chain exists to avoid.
                return "point_at"

            # If the opening chart BAKES the host in (Data rides the drawing
            # line/bar), add NO overlay for the hook — he's already in the chart.
            _hook_baked = bool(st.segments) and _seg_is_baked(st.segments[0])
            if lead_hook and st.segments and not _hook_baked:
                staged_hook = _stage_on_data(st.segments[0], windows[0][0],
                                             windows[0][1], _act(st.segments[0]),
                                             None)
            if staged_hook is not None:
                _add(staged_hook[0], staged_hook[1])
            elif not _hook_baked:
                _add((Cx, hook_y, windows[0][0], windows[0][1],
                      UP_ANGLE, False, hook_perf, hook_scale))
            for i in range(nseg):
                wi = windows[1 + i] if 1 + i < len(windows) else None
                if not wi:
                    continue
                spec = _seg_spec(i)
                # Data sweeps up onto THIS beat's winning datum and performs his
                # authored ANIMATED action ON it (push / ride / hoist) — moves in
                # place (not a frozen sticker), on-topic (no random prop).
                #
                # PER SPAN, NOT PER BEAT. A beat now shows a SEQUENCE of
                # different depictions (see THE EDIT), and each has its own
                # geometry — the peak of a line is nowhere near the top bar of
                # a race. Staging once per beat left him standing in mid-air
                # for every visual after the first, which is precisely what the
                # showrunner records as `decorative_mascot`. He re-stages on
                # each depiction as it comes up, so STRICT_CONTACT holds for
                # every second the video is on screen, not just the first few.
                sub = [(sp["t0"], sp["t1"], sp.get("anchors"), _span_bakes(sp))
                       for sp in (getattr(st.segments[i], "spans", []) or [])]
                if not sub:
                    # no spans recorded: the segment's own verdict decides
                    sub = [(wi[0], wi[1], None, _seg_is_baked(st.segments[i]))]
                for t0, t1, anc, baked in sub:
                    if baked:
                        continue       # this visual draws Data itself: ONE host
                    staged = _stage_on_data(st.segments[i], t0, t1,
                                            _act(st.segments[i]), None,
                                            anchors=anc)
                    if staged is not None:
                        _add(staged[0], staged[1])
                    else:                          # no anchor -> fall to the stage
                        x, y = _spot(i, "")
                        _add((x, y, t0, t1, UP_ANGLE, False, spec, 1.0))
            # CLOSING: Data is the SPEAKER — big and central so his celebration
            # is the payoff and nothing sits frozen.
            close_act = _director.celebrate() if _director else "cheer"
            # With a recap chart behind the payoff, Data presents from the lower
            # stage at normal size (so he doesn't cover it); with an empty payoff
            # he is the big central celebration that lands the takeaway.
            close_y = stage_y if lead_payoff else float(H * 0.30)
            close_scale = 1.0 if lead_payoff else 1.55
            # With a recap chart behind the payoff, Data sweeps ON it (beside its
            # star datum) rather than standing below; otherwise he is the big
            # central celebration.
            # If the recap chart bakes the host in, add NO closing overlay —
            # but ONLY when that chart is actually on screen during the
            # closing, which is exactly the `lead_payoff` case.
            #
            # Without that condition this suppressed the closing celebration
            # for almost every video the moment the data machines started
            # baking their own host (they must, or a machine gets a second
            # mascot beside it during its beat). The result was six seconds of
            # a still mascot under a speech bubble over an empty frame: the
            # single longest frozen run in the batch (2.46s, against a
            # 45-frame ceiling) and a fifth of the video spent on a card with
            # nothing happening in it.
            _close_baked = (lead_payoff and bool(st.segments)
                            and _seg_is_baked(st.segments[-1]))
            staged_close = None
            if lead_payoff and st.segments and not _close_baked:
                staged_close = _stage_on_data(st.segments[-1], windows[-1][0],
                                              windows[-1][1],
                                              _act(st.segments[-1], "payoff"),
                                              None)
            if staged_close is not None:
                _add(staged_close[0], staged_close[1])
            elif not _close_baked:
                _add((Cx, close_y, windows[-1][0], windows[-1][1],
                      UP_ANGLE, False, close_act, close_scale))
        else:
            gap_fill = "idle"
            home = (float(MASCOT_HOME[0]), float(MASCOT_HOME[1]))
            seq = [(home[0], home[1], windows[0][0], windows[0][1],
                    UP_ANGLE, False, "idle", 1.0)]
            for e in events:
                if e["anchor"]:
                    bcx, bcy, variant = _place_mascot(
                        e["anchor"], st.segments[e["seg"]].anchors)
                else:
                    bcx, bcy, variant = home[0] + S / 2, home[1] + S / 2, "U"
                tlx = min(max(bcx - S / 2, 2), W - S - 2)
                tly = min(max(bcy - S / 2, 2), H - S - 2)
                seq.append((tlx, tly, e["w0"], e["w1"],
                            UP_ANGLE if variant == "U" else SIDE_ANGLE,
                            variant == "R",
                            "idle" if variant == "U" else "point", 1.0))
            seq.append((home[0], home[1], windows[-1][0], windows[-1][1],
                        UP_ANGLE, False, "idle", 1.0))

        # Guarantee the host is on-screen for EVERY frame. Any beat whose line
        # names no on-chart number produces no events, which left a hole in the
        # tiling above and made the mascot briefly vanish. Sort by start time
        # and patch every gap (and the head/tail) with the home/up mascot so
        # coverage runs unbroken from 0 to the end of the video.
        # BAKED spans: time ranges where a chart already draws the host INSIDE it
        # (charts._bake_host). The gap-filler must NOT drop a second standing host
        # over these — that was the duplicate 'clipboard Data' welded to the frame.
        # BAKED IS A PROPERTY OF THE SPAN, NOT OF THE SEGMENT.
        #
        # THIS IS WHY DATA WAS MISSING FROM THE BEST BEATS.
        #
        # A segment renders a SEQUENCE of visuals (`seg.spans` — the
        # "[studio] seg2: mechanic(6.9s) -> bars(6.9s)" line), and only some of
        # them draw him. Marking the whole segment baked from its INSIGHT kind
        # says "a chart draws Data here" for the mechanic half too, where
        # nothing does — so the gap-filler skipped it and he simply was not in
        # the frame.
        #
        # On `ozone-hole-recovery` all three segments are trend/comparison/rank
        # — all in BAKED_CHART_KINDS — and all three also carry a brain
        # mechanic. So `all(_seg_is_baked(...))` was True, the overlay was
        # switched off for the ENTIRE video, and Data appeared only where a
        # chart happened to draw him. The opening eight seconds — the hook —
        # had no mascot at all.
        # `_span_bakes` — a chart KIND, or a scene that recorded `host_baked`
        # while it drew (the data machines). The kind-only version of this
        # is what parked the clipboard Data over a trajectory machine.
        baked_spans = baked_spans_of(st.segments, disp_start, disp_end)

        def _baked_at(t):
            return any(a - 0.06 <= t <= b + 0.06 for a, b in baked_spans)

        # FULLY-BAKED story: Data lives entirely INSIDE the charts every beat, so
        # the traveling/gap-fill overlay must add NOTHING — otherwise the home
        # host parks at bottom-centre through the hook/payoff windows (when
        # lead_hook/lead_payoff are off those windows aren't in baked_spans),
        # which the gate reads as a SECOND, pixel-identical, decorative Data.
        if fully_baked(st.segments):
            gap_fill = {"hidden": True}

        seq.sort(key=lambda s: s[2])
        filled, cursor = [], 0.0

        def _fill_gap(a, b):                 # add a home host over [a,b] MINUS baked spans
            segs = [(a, b)]
            for (ba, bb) in baked_spans:
                nxt = []
                for (sa, sb) in segs:
                    if bb <= sa or ba >= sb:
                        nxt.append((sa, sb)); continue
                    if ba > sa:
                        nxt.append((sa, min(ba, sb)))
                    if bb < sb:
                        nxt.append((max(bb, sa), sb))
                segs = nxt
            for (sa, sb) in segs:
                if sb - sa > 0.15:
                    filled.append((home[0], home[1], sa, sb,
                                   UP_ANGLE, False, gap_fill, 1.0))

        for entry in seq:
            w0, w1 = entry[2], entry[3]
            if w0 - cursor > 0.05:
                _fill_gap(cursor, w0)
            filled.append(entry)
            cursor = max(cursor, w1)
        if total - cursor > 0.05:
            _fill_gap(cursor, total)
        seq = filled

        import os as _os2
        # REHAUL: keep the CLEAN look (flat dark bg, no glowing b-roll strip, real
        # photos) BUT keep the MASCOT — he's the brand's face and gets a bigger,
        # central role. LEGACY_LOOK=1 restores the old bokeh + b-roll strip.
        CLEAN = _os2.environ.get("LEGACY_LOOK") != "1"
        mascot_movs = []
        for k, (_x, _y, _w0, _w1, angle, flip, act, sc) in enumerate(seq):
            mv = work / f"masc_{k}.mov"
            Sk = int(round(S * sc))              # per-beat mascot size
            if isinstance(act, dict) and act.get("hidden"):
                # Data is baked into the chart this beat (e.g. riding the gauge)
                # — overlay nothing, but keep the index aligned with a blank mov.
                mascot.build_blank_loop(mv, size=Sk)
            # ONE DELIBERATE ACTION PER VISUAL, NOT A LOOP OF ONE.
            #
            # This was a flat 2.2s. A pose primitive is a complete dramatic arc
            # — setup, action, payoff — so 2.2s meant he performed that whole
            # arc, start to finish, roughly twice per visual and about fourteen
            # times across a 31.5s video. Nothing in the narration cycles that
            # fast; he was just going. The operator, watching: "he was still
            # tweaking out and moving too much and too fast without reason."
            #
            # The action now takes exactly as long as the thing it is about is
            # on screen, so it plays ONCE and lands. That is also why it needs
            # no floor beyond a sane minimum: the reason it was short is gone.
            # A frantic host used to be the only thing keeping the frame from
            # scoring as frozen, and the charts carry that on their own now
            # (23.9 effective fps against a floor of 11).
            _span = max(2.5, min(12.0, float(_w1) - float(_w0)))
            if isinstance(act, dict):
                # director spec → Data doing a scene-specific action with a prop.
                # 30fps so his body/prop motion is as smooth as everything else
                # (was 20fps → his pose stuttered).
                mascot.build_scene_loop(mv, act, size=Sk, seconds=_span,
                                        flip=flip, fps=30)
            else:
                mascot.build_mascot_loop(mv, size=Sk, seconds=_span,
                                         point_angle=float(angle), flip=flip,
                                         pose=act)
            mascot_movs.append(mv)

        # Bottom footage: round-robin through the per-style b-roll clips so
        # each video gets a different vibe and never obviously repeats (falls
        # back to a soft mandelbrot if no b-roll has been built).
        broll_path, off = _pick_broll(total)
        use_broll = broll_path is not None

        # HOOK = full-bleed REAL subject photo (never AI) behind the VO hook,
        # pushed hard with Ken Burns so frame 1 is motion + a real image. This is
        # the pro open: full-frame visual + the spoken hook + a bold caption, no
        # black cards, no charts, no stock-looking AI still.
        hook_img = None
        try:
            from data_learning import scene_media
            hook_img = scene_media.fetch_hook_image(st)   # real photo
        except Exception as e:  # noqa: BLE001 — never block a render on this
            print(f"[studio] hook image skipped: {e}", flush=True)

        # Inputs: 0 gradient, 1 bokeh, 2 footage, 3 mask, [hook img], charts, mascots, audio
        # CLEAN = dark EDITORIAL gradient with genuine depth: a lifted blue/slate
        # diagonal (mean well above the dark threshold) fading to near-black
        # corners. The old palette sat so dark the whole frame read as a black
        # VOID on beats without a chart (hook/payoff) — the gate's empty_void
        # flag. This keeps the professional dark look but gives the frame body.
        _grad = (("0x10131C", "0x1E2740", "0x243141", "0x0D0F16")
                 if CLEAN else theme["grad"])
        inputs = ["-f", "lavfi", "-i",
                  ambient.gradient_lavfi(total, colors=_grad)]
        inputs += ["-loop", "1", "-i", str(bokeh)]
        if use_broll:
            inputs += ["-stream_loop", "-1", "-i", str(broll_path)]
        else:
            inputs += ["-f", "lavfi", "-i",
                       f"mandelbrot=size=540x{FOOT_H // 2}:rate={FPS}"]
        inputs += ["-loop", "1", "-i", str(footmask)]
        foot_idx, mask_idx = 2, 3
        idx = 4
        hook_idx = None
        if hook_img:
            inputs += ["-loop", "1", "-i", str(hook_img)]
            hook_idx = idx
            idx += 1
        receipt_idx = None
        if receipt:
            rpat, rnfr = receipt
            hw = windows[0][1] - windows[0][0]
            rfps = max(18.0, min(30.0, rnfr / max(0.8, hw - 0.2)))
            inputs += ["-framerate", f"{rfps:.2f}", "-i", rpat]
            receipt_idx = idx
            idx += 1
        # Input index of EVERY visual, keyed (segment, span). A beat is a
        # forward-only sequence of depictions (see THE EDIT above), so this is
        # one input per thing the viewer ever sees, in the order they see it.
        span_idx: dict = {}
        for i, seg in enumerate(st.segments):
            for j, sp in enumerate(getattr(seg, "spans", []) or []):
                # Each build is a printf sequence (..._build%02d.png) rendered
                # for EXACTLY its own span, and played at 30fps — the export
                # rate — so no source frame is ever duplicated or dropped into
                # the master timeline. A short settle tail (tpad, below) covers
                # rounding only.
                inputs += ["-framerate", "30.00", "-i", sp["path"]]
                span_idx[(i, j)] = idx
                idx += 1
        masc_input = []
        for mv in mascot_movs:
            inputs += ["-stream_loop", "-1", "-i", str(mv)]
            masc_input.append(idx)
            idx += 1
        inputs += ["-i", str(soundtrack)]
        audio_idx = idx

        if CLEAN:
            # Flat dark editorial bg + a thin brand accent bar at the very top,
            # a soft vignette to settle the eye. No orbs, no blur haze.
            # CHROME IS INK, NOT COLOUR.
            #
            # There was an 8px full-width bar of the accent at FULL opacity
            # across the top of every frame, and a 5px accent divider above
            # the caption band. Two saturated rules on every single frame is
            # the single most Twitch-overlay thing in the render — and it
            # spent the channel's ONE colour on chrome, which is exactly
            # what "colour means one thing here: the thing being said" is
            # meant to prevent. The operator's word for the result was
            # "cheap".
            #
            # (It also read `theme["accent"]`, a key that no longer exists,
            # so it had already fallen through to a hardcoded teal — the
            # green rule top and bottom of the 2026-09-10 ozone render.)
            #
            # The LOWER-THIRD PANEL stays: the band below the chart was bare
            # gradient and the gate called it a 'dead navy strip'. It just
            # doesn't need a coloured rule to say where it starts — a
            # hairline in the grid tone is what every other divider on this
            # channel wears.
            _rule = charts.GRID.lstrip("#")
            fc = [f"[0:v]format=rgba,vignette=PI/6,"
                  f"drawbox=x=0:y={FOOT_Y}:w={W}:h={FOOT_H}:color=0x161D2E@0.62:t=fill,"
                  f"drawbox=x=0:y={FOOT_Y}:w={W}:h=2:color=0x{_rule}@0.9:t=fill[bg]"]
        else:
            fc = ambient.bg_filter(1, fps=FPS)    # -> [bg]
        if CLEAN:
            prev = "bg"                           # no bottom footage strip
        else:
            # Footage strip in the bottom (feathered into the ambient).
            if use_broll:
                fc.append(
                    f"[{foot_idx}:v]trim=start={off:.2f},setpts=PTS-STARTPTS,"
                    f"scale={W}:{FOOT_H}:force_original_aspect_ratio=increase,"
                    f"crop={W}:{FOOT_H},eq=saturation=0.96:brightness=-0.04,"
                    f"format=rgba[ftex]")
            else:
                fc.append(f"[{foot_idx}:v]scale={W}:{FOOT_H},"
                          f"eq=saturation=0.4:brightness=-0.06,format=rgba[ftex]")
            fc.append(f"[{mask_idx}:v]format=gray,scale={W}:{FOOT_H}[fmask]")
            fc.append("[ftex][fmask]alphamerge[foot]")
            fc.append(f"[bg][foot]overlay=0:{FOOT_Y}[bg2]")
            prev = "bg2"
        # Image-led hook: full-frame subject photo during the hook window only,
        # darkened so the white hero number/claim stay legible, fading out as the
        # first chart arrives. The hero number + claim are ASS, drawn last on top.
        if hook_idx is not None:
            he = windows[0][1]
            # NO KEN BURNS PUSH-IN. The 2026-08-25 ruling took the camera
            # motion out of this render, and this survived it: a zoompan from
            # 1.12 to 1.6 across the hook, on a FULL-FRAME image. zoompan
            # truncates its pan expressions to whole pixels every frame, so an
            # aggressive push judders the entire picture — the shake that
            # opened every video, still there after the float came out. The
            # hook photo is a static fill; the hook's motion is the chart
            # build, the captions and the host.
            # AND IT IS AN ESTABLISHING SHOT, NOT A HOLD. Covering the whole
            # hook window with a full-frame still is what made segment_0
            # measure 0.8-1.8 fps while segment_1 and segment_2 sat at 24 —
            # the animating chart was underneath it the entire time, hidden.
            # Every "fix" for that number added camera movement instead of
            # asking why the frame was static.
            #
            # Measured with the reviewer's own detector: a still frame with
            # only the host moving on it scores 0.0 fps (a 90px sprite moving
            # 4px is sub-threshold once the detector downscales to 192px), and
            # the max-duplicate-run ceiling is 45 frames = 1.5s. So the photo
            # gets ~1.2s — an establishing beat, comfortably inside the
            # ceiling — and then hands off to the chart build, which animates
            # across the rest of the hook and measures 24.
            _hook_hold = min(he, 1.2)
            fc.append(
                f"[{hook_idx}:v]scale={W}:{H}:"
                f"force_original_aspect_ratio=increase,crop={W}:{H},"
                f"eq=brightness=-0.14:saturation=1.12:contrast=1.06,format=rgba,"
                f"fade=t=out:st={max(0.1, _hook_hold - 0.3):.2f}:d=0.3:alpha=1"
                f"[hookimg]")
            fc.append(
                f"[{prev}][hookimg]overlay=0:0:"
                f"enable='between(t,0,{_hook_hold:.2f})'[hk]")
            prev = "hk"
        # HOOK RECEIPT: the total races up over the hook window, then holds
        # briefly and fades as the first chart arrives. Full-frame; Data reacts
        # below it (mascot overlay is drawn after this).
        if receipt_idx is not None:
            he = windows[0][1]
            fc.append(
                f"[{receipt_idx}:v]tpad=stop_mode=clone:stop_duration={he + 0.5:.2f},"
                f"setpts=PTS-STARTPTS,scale={W}:{H},format=rgba,"
                f"fade=t=out:st={max(0.1, he - 0.3):.2f}:d=0.3:alpha=1[rcpt]")
            fc.append(
                f"[{prev}][rcpt]overlay=0:0:enable='between(t,0,{he:.2f})'[rk]")
            prev = "rk"
        # Charts DRAW ON: the build sequence plays (~0.7s) then tpad holds the
        # final frame for the rest of the beat. setpts shifts the clip so its
        # frame 0 lands at s0; the final frame is the exact static chart, so the
        # rings/mascot still anchor. No static 12s hold any more.
        # The host stays on screen across BOTH depictions of a beat — he is
        # one of the video's subjects, not an overlay to hide. (This used to
        # hold him off the punch-in shots; there are no punch-ins now.)
        punch_windows: list[tuple[float, float]] = []
        n_visuals = 0
        for i, seg in enumerate(st.segments):
            spans = getattr(seg, "spans", []) or []
            if not spans:
                continue
            fd = 0.14        # short cross-fade so no frame lands on near-black
            # Full-frame viz (diorama, timeline, fill_vessel, ...) are authored
            # at 1080x1920 and fill the whole frame; card charts/maps stay in the
            # top chart region. The registry is charts' single source of truth.
            full = getattr(st.segments[i], "kind", "") in charts.FULLFRAME_RENDERERS
            # A SUBJECT SCENE is drawn at 1080x1920 and is the whole shot. It
            # inherited its segment's chart kind here, so a bar-race story's
            # scenes were shrunk into the chart region with a dark border and
            # a dead band under them — the "inset" the showrunner named.
            full = full or any(sp.get("kind") == "subject_scene" for sp in spans)
            vw, vh = (W, H) if full else (CHART_W, CHART_H)
            vx, vy = (0, 0) if full else (CHART_X, CHART_Y)
            # NO per-layer float here any more. The card used to drift on its
            # own (20px @ 4.6 rad/s) while the mascot jiggled at a different
            # frequency on top — two independent oscillations, which the
            # operator watched and called "a weird shaking motion". They were
            # right: perceived shake is acceleration (amp*w^2), and layers
            # oscillating out of phase multiply it. The gate's per-frame
            # motion now comes from ONE slow whole-frame drift applied to the
            # finished composite just before the captions burn in (see the
            # CAMERA BREATH step below) — same measured pixels per frame,
            # less than half the acceleration, one coherent camera.
            #
            # ONE OVERLAY PER SPAN, EACH SOURCE CONSUMED EXACTLY ONCE.
            #
            # Every visual is laid at its OWN t0 and enabled only for its own
            # window, so a depiction is on screen once and then finished. There
            # is nothing to split and no label to reuse: the earlier alternating
            # edit reused [g0] across shots and ffmpeg refused the whole graph
            # (exit 234, no render at all), which cannot happen in this shape.
            for j, sp in enumerate(spans):
                gi = span_idx.get((i, j))
                if gi is None:
                    continue
                t0, t1 = float(sp["t0"]), float(sp["t1"])
                hold = max(0.5, t1 - t0) + 1.0
                lab = f"v{i}_{j}"
                # A SUBJECT SCENE CUTS. It is an opaque full frame, so there is
                # no near-black to hide, and a cross-fade laid two scenes'
                # readouts — which sit at the same spot — over each other: the
                # "garbled crossfade number" that blocked a 73 (2026-09-23).
                _fades = ("" if sp.get("kind") == "subject_scene" else
                          f",fade=t=in:st={t0:.2f}:d=0.12:alpha=1,"
                          f"fade=t=out:st={max(t0, t1 - fd):.2f}:d={fd}:alpha=1")
                fc.append(
                    f"[{gi}:v]tpad=stop_mode=clone:stop_duration={hold:.2f},"
                    f"setpts=PTS-STARTPTS+{t0:.2f}/TB,"
                    f"scale={vw}:{vh},format=rgba"
                    f"{_fades}"
                    f"[{lab}]")
                # THE CLOSING CARD OWNS THE FRAME.
                #
                # The last visual runs into the closing window (that is what
                # `lead_payoff` is for — a recap behind the takeaway beats a
                # mascot on a void), and the card is a 900x320 bubble at the
                # TOP of that frame. So the two competed: the card printed over
                # the chart's heading, clipped the host's head, and the balance
                # beam ran out from under it. An earlier pass moved the
                # question and CTA down to the foot band for exactly this
                # reason and left the bubble where it was.
                #
                # Dimming the recap was the first attempt and it was wrong
                # twice: the card is OPAQUE, so the problem was never text
                # legibility — it was the card eating the top third of the
                # picture underneath — and the recap turned out to be what
                # carried the closing's motion, so fading it to 30% produced a
                # 54-frame frozen stretch against a 45 ceiling.
                #
                # So the recap MOVES instead. During the closing it shrinks and
                # drops below the card, into the lower half that every one of
                # these frames was leaving empty anyway. Nothing overlaps,
                # nothing dims, and the frame finally uses its bottom.
                _close0 = windows[-1][0] if windows else t1
                if t1 - _close0 > 0.35 and t0 < _close0:
                    _rg = recap_geometry(vw, vh)
                    _rw, _rh, _rx, _ry = _rg["rw"], _rg["rh"], _rg["rx"], _rg["ry"]
                    _ch = _rg["crop_h"]           # centred trim: no offsets
                    # THE RECAP REPLAYS ITS BUILD, it does not carry on with
                    # the tail of one.
                    #
                    # Measured on `colorado-wolves-return` 2026-09-09, the
                    # video held that morning: during the frozen window the
                    # recap IS moving — 3-8% of its pixels — and it does not
                    # matter, because the gate reads the MEAN change inside a
                    # 16x16 block and 8% of a block changing by 43 is a mean
                    # of 3.4 against a threshold of 6. A chart 98% built moves
                    # by sub-pixels, and shrinking it to 62% for the closing
                    # shrinks that again.
                    #
                    # Replaying is the honest large-amplitude motion the
                    # closing needs and the one it can have for free: the
                    # payoff chart redraws itself under the takeaway. `setpts`
                    # compresses the whole sequence into the closing window,
                    # so the bars sweep across bands that were dead.
                    _span = max(0.05, t1 - t0)
                    _k = (t1 - _close0) / _span
                    # A SUBJECT SCENE is not replayed: its first frames are an
                    # empty chalkboard or a map with no red line yet, and the
                    # scene is alive to its last frame anyway (Data, steam,
                    # heat). It carries on in the recap panel, on its own clock.
                    _pts = (f"setpts=PTS-STARTPTS+{t0:.3f}/TB"
                            if sp.get("kind") == "subject_scene" else
                            f"setpts=(PTS-STARTPTS)*{_k:.5f}+{_close0:.3f}/TB")
                    fc.append(f"[{lab}]split=2[{lab}a][{lab}b]")
                    fc.append(
                        f"[{lab}b]crop={vw}:{_ch},"
                        f"scale={_rw}:{_rh},"
                        f"{_pts}"
                        f"[{lab}d]")
                    fc.append(
                        f"[{prev}][{lab}a]overlay=x={vx}:y={vy}:"
                        f"enable='between(t,{t0:.2f},{_close0:.2f})'"
                        f"[b{i}_{j}p]")
                    fc.append(
                        f"[b{i}_{j}p][{lab}d]overlay=x={_rx}:y={_ry}:"
                        f"enable='between(t,{_close0:.2f},{t1:.2f})'[b{i}_{j}]")
                else:
                    fc.append(
                        f"[{prev}][{lab}]overlay=x={vx}:y={vy}:"
                        f"enable='between(t,{t0:.2f},{t1:.2f})'[b{i}_{j}]")
                prev = f"b{i}_{j}"
                n_visuals += 1
        print(f"[studio] {n_visuals} distinct visuals, each shown once",
              flush=True)
        # Beat map, so a frozen stretch found by the gate can be located
        # against the thing that owns that second instead of guessed at. Three
        # rounds of this session's cadence work were spent inferring which
        # layer a freeze belonged to from its timestamp alone.
        print("[studio] beat map: " + " | ".join(
            f"{a:.1f}-{b:.1f}s seg{i}"
            for i, (a, b) in enumerate(
                [(disp_start.get(k, 0.0), disp_end.get(k, 0.0))
                 for k in range(len(st.segments))]))
            + f" | closing {windows[-1][0]:.1f}-{windows[-1][1]:.1f}s"
            + f" | payoff_recap={'yes' if lead_payoff else 'NO'}", flush=True)
        # Mascots — Data IS PLACED, HE DOES NOT SLIDE.
        #
        # He used to glide from his previous spot to each new one, sweeping in
        # over the first ~30% of the window. With three beats that was three
        # moves. The monotonic edit re-stages him on every SPAN so he stays in
        # contact with whichever depiction is actually on screen — and that
        # turned three glides into eight, one every four seconds. The operator
        # watched it: "the fucking mascot's tweaking out all over the screen
        # all the time."
        #
        # Every span boundary is a HARD CUT to a new chart, and a cut is the
        # one moment repositioning is free — the viewer expects everything to
        # change. So he is simply THERE, in position, when the new visual
        # arrives. No travel, no sweep-in, no easing across the cut.
        #
        # The reason this is safe now and would not have been before: the glide
        # existed to keep something moving, because a chart that finished
        # building and then held was scored as a frozen frame. That is no
        # longer true — each depiction is built across exactly its own span, so
        # the charts carry 23.9 effective fps on their own (the floor is 11).
        # Data's motion is his PERFORMANCE — the sprite is an animated loop of
        # him acting on the data — which is the motion that was worth having
        # all along. The frantic version was compensation for a static frame,
        # and the operator named that too, months ago: "making the mascot moves
        # its arm a lot to account for the fact that there's not enough
        # motion."
        for k, (tlx, tly, w0, w1, _a, _f, _p, sc) in enumerate(seq):
            gi = masc_input[k]
            # NO HOVER OSCILLATION (2026-08-25 ruling: "no semblance of the
            # camera shake"). A sprite bobbing on the spot in its own phase is
            # what made two oscillations read as "weird shaking" in the first
            # place. His position is a constant for the whole span.
            xe = f"{tlx:.0f}"
            ye = f"{tly:.0f}"
            Sk = int(round(S * sc))
            off = (Sk - S) // 2            # keep the bigger sprite centred on target
            # HOLD HIM OFF THE PUNCH-INS. When the edit cuts to a datum, the
            # frame is the datum — a host composited on top of a close-up is
            # the mascot filling space, which is exactly what the arms were
            # doing before there was an edit to carry the beat.
            _off_shots = "".join(
                f"*not(between(t,{a0:.2f},{a1:.2f}))"
                for a0, a1 in punch_windows if a0 < w1 and a1 > w0)
            fc.append(f"[{gi}:v]format=rgba,scale={Sk}:{Sk}[mk{k}]")
            fc.append(f"[{prev}][mk{k}]overlay=x='({xe})-{off}':y='({ye})-{off}':"
                      f"eval=frame:"
                      f"enable='between(t,{w0:.2f},{w1:.2f}){_off_shots}'[mb{k}]")
            prev = f"mb{k}"
        # NO CAMERA MOTION. Operator ruling 2026-08-25, verbatim: "that
        # camera shake that keeps plaguing our videos — rip it out all the
        # way, it's a cancer, I want no semblance of the camera shake to
        # exist."
        #
        # It was here for one reason: the temporal grade measures per-frame
        # pixel change, and a chart that finishes drawing and then HOLDS
        # reads as duplicate frames. Rather than make the content move, a
        # whole-frame Lissajous drift was added to manufacture the motion the
        # detector wanted. That is gaming a gate, and the operator could see
        # it — twice ("a weird shaking"), through two retunes that only ever
        # traded amplitude against frequency.
        #
        # The honest fix is the one the content now supports: the mascot
        # performs struggle reps through the whole beat (`_perf_phase`) and
        # his anchor TOURS the ranking instead of parking once the build
        # finishes (`charts._tour_index`), so real motion is present in
        # frames that used to be static. If a beat still measures short, the
        # answer is more REAL motion in that beat — never a camera that
        # shakes to fool the meter. Captions were already pinned; with no
        # crop they simply stay where they are drawn.
        fc.append(f"[{prev}]ass='{ass_esc}'[v]")

        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(fc),
               "-map", "[v]", "-map", f"{audio_idx}:a",
               "-t", f"{total:.2f}", "-r", str(FPS),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
               "-crf", "22", "-maxrate", "4M", "-bufsize", "8M",
               "-c:a", "aac", "-b:a", "160k",
               "-movflags", "+faststart", str(out_path)]
        _run(cmd)
        # Advance the rotation so the next render uses the next style.
        if use_broll:
            _advance_broll(total)

        # RESET (one controlled format): the video is a SINGLE render pass. The
        # old 3D Blender bookends + a separately-stitched kinetic cold-open were
        # an extra layer stapled on around the body — redundant with the body's
        # own hero-number hook and outro. Removed, so there is exactly one
        # format: flat dark bg, one real chart, Data, narration, captions.

    # SCENE-ADDRESSABLE METRICS, measured on the FINISHED master so the number
    # is the same measurement the whole-video gate makes. The repair loop reads
    # these to target the failing SCENE instead of re-rolling the whole video.
    try:
        _spans = [(disp_start.get(i, windows[1 + i][0]),
                   disp_end.get(i, windows[1 + i][1]))
                  if 1 + i < len(windows) else None
                  for i in range(len(st.segments))]
        _scene_metrics(st, slug, work, out_path, _spans)
    except Exception as e:  # noqa: BLE001 — metrics never fail a render
        print(f"[studio] scene metrics skipped: {e}", flush=True)

    # Render manifest: the actual beat windows so the showrunner samples frames
    # at real scene boundaries (hook / each segment / payoff) instead of blind
    # evenly-spaced stills.
    try:
        manifest = {
            "slug": slug, "total": round(total, 2),
            "hook_window": [round(windows[0][0], 2), round(windows[0][1], 2)],
            "segment_windows": [[round(a, 2), round(b, 2)] for a, b in windows],
            "kinds": [getattr(s, "kind", "") for s in st.segments],
        }
        out_path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
    except Exception as e:  # noqa: BLE001
        print(f"[studio] manifest skipped: {e}", file=sys.stderr)
    try:
        _style_arms.sidecar(out_path).write_text(json.dumps(_style))
    except Exception as e:  # noqa: BLE001
        print(f"[studio] style sidecar skipped: {e}", file=sys.stderr)

    print(f"[studio] story '{slug}': {len(st.segments)} charts, "
          f"{len(sentences)} beats, {total:.1f}s -> {out_path}")
    print(f"[studio] title: {st.title}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="story slug from niche.config.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice", default=None,
                    help="Kokoro voice id (default am_fenrir)")
    ap.add_argument("--config", type=Path, default=None,
                    help="story config JSON (default: data_learning/niche.config.json)")
    args = ap.parse_args()
    render(args.slug, args.out, voice=args.voice, config_path=args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
