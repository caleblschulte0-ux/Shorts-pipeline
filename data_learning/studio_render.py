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


def _seg_is_baked(seg) -> bool:
    return (getattr(seg, "kind", "") in BAKED_CHART_KINDS
            or getattr(seg, "kind", "") in HOST_BAKED_KINDS
            or getattr(seg, "host_baked", False)
            or getattr(getattr(seg, "insight", None), "host_baked", False))

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
THEMES = [
    dict(highlight="#4FD1C5", accent="#60A5FA", warn="#F59E0B",
         grad=("0x080A14", "0x0e2444", "0x175852", "0x0a0e20"),
         seed=7, voice="am_fenrir", vibe="calm"),
    dict(highlight="#A78BFA", accent="#F472B6", warn="#FBBF24",
         grad=("0x0c0814", "0x241040", "0x3a1763", "0x120a20"),
         seed=13, voice="am_michael", vibe="dark"),
    dict(highlight="#FBBF24", accent="#FB7185", warn="#34D399",
         grad=("0x141005", "0x3a2410", "0x4e3417", "0x1a1408"),
         seed=21, voice="bm_george", vibe="cinematic"),
    dict(highlight="#34D399", accent="#22D3EE", warn="#FBBF24",
         grad=("0x07140e", "0x0e3a2a", "0x175852", "0x0a201a"),
         seed=29, voice="am_adam", vibe="pulse"),
    dict(highlight="#FB7185", accent="#A78BFA", warn="#FBBF24",
         grad=("0x140810", "0x40102a", "0x5a1740", "0x200a18"),
         seed=37, voice="bm_lewis", vibe="dark"),
    dict(highlight="#60A5FA", accent="#34D399", warn="#FBBF24",
         grad=("0x06101e", "0x102044", "0x174a72", "0x0a1428"),
         seed=43, voice="am_fenrir", vibe="cinematic"),
]


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
SPAN_TARGET = 4.5          # seconds one depiction owns the screen
MAX_SPANS = 3              # per beat, so a 3-beat story tops out at 9 visuals


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


def build_story_ass(st: story.Story, windows, events, out: Path,
                    accent: str = "&H4FD1F5&", hook_visual: bool = False,
                    chart_hook: bool = False) -> None:
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
        chunks = _chunks(sent, 3)
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
    headline = _headline_number(st)
    # A bare share % ("22%") slammed on frame 1 is meaningless without its whole
    # and reads as the 'bare number card' the gate blocks — so when the OPENING
    # beat is a part-of-whole depiction (waffle / pie / share), suppress the hero
    # number and let the mascot + the share chart carry the hook. A striking
    # standalone value (427 ppm, 1.4 billion) still leads.
    _share_lead = (st.segments and getattr(st.segments[0], "kind", "") in
                   ("share", "waffle_grid", "pie", "donut", "pictorial_pie"))
    # When a full-frame HOOK VISUAL (the receipt) is on screen it IS the hero —
    # the big number + claim would just collide with it, so they're suppressed
    # and the receipt + VO captions carry the open. A chart-led hook (chart_hook)
    # or a share-led open likewise drops the giant number (the chart carries it).
    if headline and not hook_visual and not _share_lead and not chart_hook:
        # Hero number: huge, accent-filled, punches in hard on the first frame.
        num = ("{\\an5\\pos(540,235)\\fs240\\1c" + accent + "\\3c&H101010&"
               "\\bord7\\shad0\\fad(0,90)\\fscx150\\fscy150"
               "\\t(0,150,\\fscx100\\fscy100)\\blur1.2}" + headline)
        lines.append(f"Dialogue: 1,{_ass_time(h0)},{_ass_time(h1)},Hook,,0,0,0,,{num}")
    hchunks = _chunks(st.hook, 2) if not hook_visual else []
    if hchunks:
        hstep = (h1 - h0) / len(hchunks)
        for j, ch in enumerate(hchunks):
            cs, ce = h0 + j * hstep, h0 + (j + 1) * hstep
            # The take sits BELOW the hero number (and above the mascot) so the
            # number, the claim, and the host never fight for the same pixels.
            if j == 0:
                pop = ("{\\an5\\pos(540,470)\\fs92\\fad(0,70)\\fscx120\\fscy120"
                       "\\t(0,130,\\fscx100\\fscy100)\\3c" + accent + "\\bord8\\blur5}")
            else:
                pop = ("{\\an5\\pos(540,470)\\fs92\\fad(70,70)\\fscx108\\fscy108"
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
        color = _hex_to_ass(p.get("color", "#ffffff"))
        if e["xy"] and e["box"]:
            mx, my = int(e["xy"][0]), int(e["xy"][1])
            rx = e["box"][0] / 2 + 24      # encase the WHOLE number + padding
            ry = e["box"][1] / 2 + 14
            ring = ("{\\an7\\pos(0,0)\\org(" + f"{mx},{my}" + ")\\1a&HFF&"
                    "\\3c&HF0E14F&\\bord5\\shad0\\fad(120,150)"
                    "\\t(0,200,\\fscx106\\fscy106)\\t(200,420,\\fscx100\\fscy100)"
                    "\\p1}" + _ellipse_path_abs(mx, my, rx, ry) + "{\\p0}")
            lines.append(f"Dialogue: 3,{_ass_time(max(0, ps - 0.15))},"
                         f"{_ass_time(pe)},Mark,,0,0,0,,{ring}")
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
    qs = c0 + 0.40 * cd
    cs = c0 + 0.62 * cd
    bubble = ("{\\an7\\pos(0,0)\\1c&H241A12&\\3c&H" + acc + "&\\bord4\\shad0"
              "\\fad(250,0)\\p1}"
              + _round_rect_tail(90, 150, 990, 470, 30, 540, (540, 588))
              + "{\\p0}")
    lines.append(f"Dialogue: 4,{_ass_time(c0)},{_ass_time(c1)},Src,,0,0,0,,{bubble}")
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
        lines.append(f"Dialogue: 5,{_ass_time(cs)},{_ass_time(c1)},Cap,,0,0,0,,{cta}")
    # Dedupe + strip the 'Source:' prefix each footer already carries, so the
    # line reads 'Sources: NOAA ...' ONCE — not 'Sources: Source: X · Source: X'
    # (the duplicate the gate flagged when both segments share a publisher).
    _uniq = []
    for _f in st.sources:
        _f = _f.strip()
        if _f.lower().startswith("source:"):
            _f = _f[len("source:"):].strip()
        if _f and _f not in _uniq:
            _uniq.append(_f)
    src = " · ".join(_uniq)
    src_txt = ("{\\an2\\pos(540,1898)\\fs15\\c&HA5B4C7&\\b0\\bord1\\shad0"
               "\\fad(200,0)}Sources: " + src)
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


def _phrase_frac(sentence: str, phrase: str) -> float:
    """Fraction through the sentence (by word) where ``phrase`` starts —
    approximates *when* it's spoken, so markers/monster line up with the
    narration instead of even slots."""
    idx = sentence.lower().find(phrase.lower())
    total = max(1, len(sentence.split()))
    if idx < 0:
        return 0.5
    return len(sentence[:idx].split()) / total


def _plan_events(st: story.Story, windows):
    """One event per spoken number: when it's said, which data point it is,
    and (later) where the mascot should stand. Timed to where the number
    falls in the sentence so marker/monster hit it as the voice says it. Each
    event also gets a show-window so exactly one mascot is up at a time."""
    events = []
    for i, seg in enumerate(st.segments):
        s0, s1 = windows[1 + i]
        seg_events = []
        for p in seg.punches:
            frac = _phrase_frac(seg.sentence, p.get("phrase", ""))
            ps = s0 + frac * (s1 - s0)
            dur = min(float(p.get("duration", 1.8)), max(0.6, s1 - ps))
            a = _anchor_for_punch(seg, p)
            xy = _screen(a["cx"], a["cy"]) if a else None
            box = (a["w"] * SCALE_X, a["h"] * SCALE_Y) if a else None
            seg_events.append({"ps": ps, "pe": ps + dur, "punch": p, "xy": xy,
                               "box": box, "anchor": a, "seg": i})
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
    if not anchors:
        return None
    isc = 0.62
    S = MASCOT_SIZE
    Sk = S * isc

    def _tl(cx, cy):                    # centre -> full-size top-left, clamped
        return (min(max(cx - S / 2, 2.0), float(W - S - 2)),
                min(max(cy - S / 2, 2.0), float(H - S - 2)))

    def _onto(a):                       # stand ON element a (feet on top, off #)
        cx, cy, _w, _h = _screen_box(a)
        cxc = max(cx - Sk * 0.5 - 15.0, float(CHART_X) + Sk * 0.5 + 6.0)
        return _tl(cxc, cy - Sk * 0.40)

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
def _scene_metrics(st, slug: str, work: Path, out_path: Path) -> None:
    """Encode each scene's chart build alone (tiny 540x960 proxy) and measure it
    with the SAME temporal detector + hard gate the reviewer uses. One JSON per
    scene under output/scenes/ — the scene-level metrics + verdict that make
    repair scene-addressable (fix the failing scene, not the whole video)."""
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
    for i, seg in enumerate(st.segments):
        if not seg.chart_path:
            continue
        pat = seg.chart_path
        n = len(_g.glob(pat.replace("%02d", "*")))
        if n < 2:
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
        # MEASURE WHAT SHIPS — and what ships no longer floats (2026-08-25
        # ruling: the camera shake is out). The rule this probe exists for is
        # unchanged and now cuts the other way: measuring motion the master
        # does not have would let a beat that is actually static score as
        # lively, which is exactly the "fps 1.0 measured, 1.0 shipped" bug
        # with the sign flipped. So the proxy composites the build at rest,
        # full stop, and a beat that measures short is a beat that needs more
        # REAL motion.
        try:
            _sp.run(
                [_ff, "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=0x10131C:s=540x960:r=30",
                 "-framerate", "30", "-i", pat,
                 "-filter_complex",
                 f"[1:v]scale=540:-1,format=rgba[c];"
                 f"[0:v][c]overlay=0:0:shortest=1,format=yuv420p",
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


# Ways of drawing a figure that are HONEST for a given shape of data, best
# first. Widening these lists is how a video gets more distinct visuals, so the
# constraint that keeps them short is worth stating plainly: a depiction must
# not assert something the data does not say.
#
#   * `share` and `waffle_grid` claim the items are PARTS OF A WHOLE. Drawing a
#     run of years that way says the years sum to something, which is false.
#   * `trend` claims an ORDERED progression. Drawing a ranking of cities as a
#     line says Miami comes after Seattle in some sequence, which is false.
#   * `geo_us` / `geo_world` claim the items are PLACES, so they never appear
#     as an alternate for non-geographic data — a map of "cost per year" is a
#     lie with a nice texture.
#
# Everything listed under a shape is a fair redraw of that shape. The point of
# a second and third depiction is to show the SAME truth another way, and a
# channel whose whole editorial gate is about real, sourced numbers cannot buy
# variety with a misleading chart.
_SHAPE_CANDIDATES = {
    # values over time: any magnitude comparison is fair, sequence included
    "series": ("trend", "bars", "stack", "comparison", "pictograph"),
    # named things being compared: anything but a false sequence
    "ranking": ("pictorial_race", "bars", "rank", "pictograph", "comparison",
                "bubbles", "waffle_grid", "share", "stack"),
    "other":   ("bars", "pictograph", "stack", "rank", "bubbles",
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


def _depiction_sequence(insight, used: set, dur: float) -> list:
    """The ORDERED, NON-REPEATING depictions one beat shows, front to back.

    Element 0 is the beat's own chart; the rest are different contact-verified
    ways to draw the SAME number. Each appears exactly once and is retired when
    its span ends — the list is the edit, and the edit only ever moves forward.

    ``used`` is every kind already on screen anywhere in this video, so the
    third visual is a genuine change of subject rather than the neighbouring
    beat's chart again. Length comes from the beat's duration, not from a fixed
    count: a short beat stays on one visual rather than being chopped up, which
    is the "we're cutting so much for no reason" half of the ruling.
    """
    kind = str(getattr(insight, "kind", "") or "")
    n = max(1, min(MAX_SPANS, int(round(max(0.0, dur) / SPAN_TARGET))))
    seq = [kind]
    if n == 1:
        return seq
    cands = list(_alt_candidates_for(insight))
    for c in _ALT_DEPICTION.get(kind, ()):
        if c not in cands:
            cands.append(c)
    # Prefer kinds no beat has shown yet...
    for c in cands:
        if len(seq) >= n:
            break
        if c and c != kind and c not in seq and c not in used:
            seq.append(c)
    # ...but a kind another beat used still beats repeating one inside THIS
    # beat, which is the thing the viewer actually notices as a bounce-back.
    for c in cands:
        if len(seq) >= n:
            break
        if c and c not in seq:
            seq.append(c)
    return seq


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
    charts.HIGHLIGHT, charts.ACCENT, charts.WARN = (
        theme["highlight"], theme["accent"], theme["warn"])
    accent_ass = _hex_to_ass(theme["highlight"])
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
            kinds = _depiction_sequence(seg.insight, _kinds_used, dur)
            spans = _visual_spans(start, end, len(kinds))
            seg.spans = []
            _orig_kind = seg.insight.kind
            for j, (kind, (t0, t1)) in enumerate(zip(kinds, spans)):
                nfr = int(max(30, min(1200, _mfr.ceil((t1 - t0) * 30))))
                cpath, anc = None, []
                try:
                    seg.insight.kind = kind
                    # Build LINEARLY across the WHOLE span (no early
                    # completion): the chart keeps moving for as long as it is
                    # on screen, so there is never a finished-and-held stretch
                    # (that was the dead_air / 5fps).
                    cpath, anc = charts.render_story_build(
                        seg.insight, chart_dir, f"{slug}_seg{i:02d}_v{j}",
                        frames=nfr,
                        # only the opening visual bursts up out of the hook
                        hook_lead=(i == 0 and lead_hook and j == 0))
                except Exception as e:  # noqa: BLE001 — a missing extra visual
                    print(f"[studio] seg{i} visual {j} ({kind}) skipped: {e}",
                          flush=True)   # is fewer things, never a failed render
                finally:
                    seg.insight.kind = _orig_kind
                if not cpath:
                    continue
                seg.spans.append({"kind": kind, "path": str(cpath),
                                  "anchors": anc, "t0": t0, "t1": t1})
                _kinds_used.add(kind)
                if j == 0:
                    seg.chart_path = str(cpath)
            if seg.spans:
                print(f"[studio] seg{i}: "
                      + " -> ".join(f"{sp['kind']}({sp['t1'] - sp['t0']:.1f}s)"
                                    for sp in seg.spans), flush=True)

        # SCENE-ADDRESSABLE METRICS: encode each scene's build alone and run the
        # reviewer's own cadence detector + the build-time temporal gate on it,
        # writing output/scenes/{slug}_sceneN.json. When a video fails, the
        # repair loop reads these to target the failing SCENE instead of
        # re-rolling the whole video; they also make every scene debuggable.
        try:
            _scene_metrics(st, slug, work, out_path)
        except Exception as e:  # noqa: BLE001 — metrics never fail a render
            print(f"[studio] scene metrics skipped: {e}", flush=True)

        bokeh = ambient.make_bokeh_strip(work / "bokeh.png", seed=theme["seed"])
        footmask = work / "foot_mask.png"
        _make_mandel_mask(footmask, W, FOOT_H, feather=130, bottom=70)
        events = _plan_events(st, windows)
        # Full soundtrack: narration + ducked theme music + visual-synced SFX.
        soundtrack = _build_soundtrack(narration, windows, events, total,
                                       theme.get("vibe", "calm"), work, slug)
        # A full-frame receipt suppresses BOTH the hero number and the hook text
        # (it IS the open). A chart-led hook keeps the punchy hook TEXT but drops
        # the giant hero number so it doesn't collide with the chart.
        ass = work / "cap.ass"
        build_story_ass(st, windows, events, ass, accent=accent_ass,
                        hook_visual=bool(receipt), chart_hook=lead_hook)
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
            # Beats that composite Data straight INTO the chart (he rides the
            # gauge arc / walks the timeline dot): suppress the traveling
            # overlay so there's exactly one host on the beat. Covered either by
            # a baked chart kind or a scene mechanic that flagged host_baked.
            if _seg_is_baked(st.segments[i]):
                return {"hidden": True}
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

        entries: dict = {}                 # seq index -> glide start (sweep-in)
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
            # entries[k] = where Data's glide STARTS for seq[k] (his sweep-in
            # point); absent -> he glides from his previous spot. Set for data
            # beats so he sweeps UP onto the datum (a moving bit + smooth cadence).
            entries: dict = {}

            def _add(entry_tuple, entry_xy=None):
                if entry_xy is not None:
                    entries[len(seq)] = entry_xy
                seq.append(entry_tuple)

            # When the opening chart leads the hook, Data performs ON it from
            # frame 1 (sweeping onto its star datum) instead of standing below it.
            staged_hook = None
            def _act(seg, phase="action"):
                # Deterministic, on-topic, ANIMATED action for this chart kind
                # (push the bar / ride the line / hoist the slice; a celebration
                # on the payoff). No brain call -> free + no run-to-run variance.
                kind = getattr(seg, "kind", "")
                if _director and hasattr(_director, "data_action_spec"):
                    return _director.data_action_spec(kind, phase)
                return "cheer" if phase == "payoff" else "point"

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
                if isinstance(spec, dict) and spec.get("hidden"):
                    continue                       # host baked into the chart
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
                sub = [(sp["t0"], sp["t1"], sp.get("anchors"))
                       for sp in (getattr(st.segments[i], "spans", []) or [])]
                if not sub:
                    sub = [(wi[0], wi[1], None)]
                for t0, t1, anc in sub:
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
            # If the recap chart bakes the host in, add NO closing overlay.
            _close_baked = bool(st.segments) and _seg_is_baked(st.segments[-1])
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
        baked_spans = []
        for _bi, _bseg in enumerate(st.segments):
            if _seg_is_baked(_bseg) and _bi in disp_start:
                baked_spans.append((disp_start[_bi], disp_end[_bi]))

        def _baked_at(t):
            return any(a - 0.06 <= t <= b + 0.06 for a, b in baked_spans)

        # FULLY-BAKED story: Data lives entirely INSIDE the charts every beat, so
        # the traveling/gap-fill overlay must add NOTHING — otherwise the home
        # host parks at bottom-centre through the hook/payoff windows (when
        # lead_hook/lead_payoff are off those windows aren't in baked_spans),
        # which the gate reads as a SECOND, pixel-identical, decorative Data.
        if st.segments and all(_seg_is_baked(s) for s in st.segments):
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
            elif isinstance(act, dict):
                # director spec → Data doing a scene-specific action with a prop.
                # 30fps so his body/prop motion matches the smooth ffmpeg glide
                # (was 20fps → he slid smoothly but his pose stuttered).
                mascot.build_scene_loop(mv, act, size=Sk, seconds=2.2,
                                        flip=flip, fps=30)
            else:
                mascot.build_mascot_loop(mv, size=Sk, seconds=2.2,
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
            _ac = (theme.get("accent") or "#4FD1C5").lstrip("#")
            # LOWER-THIRD PANEL: the band below the chart card used to be bare
            # gradient — the gate's 'dead navy strip / empty_void'. Fill it with a
            # subtle raised panel + an accent divider so it reads as an
            # intentional caption zone (a pro lower-third), not wasted space.
            fc = [f"[0:v]format=rgba,vignette=PI/6,"
                  f"drawbox=x=0:y=0:w={W}:h=8:color=0x{_ac}@1.0:t=fill,"
                  f"drawbox=x=0:y={FOOT_Y}:w={W}:h={FOOT_H}:color=0x161D2E@0.62:t=fill,"
                  f"drawbox=x=0:y={FOOT_Y}:w={W}:h=5:color=0x{_ac}@0.55:t=fill[bg]"]
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
                fc.append(
                    f"[{gi}:v]tpad=stop_mode=clone:stop_duration={hold:.2f},"
                    f"setpts=PTS-STARTPTS+{t0:.2f}/TB,"
                    f"scale={vw}:{vh},format=rgba,"
                    f"fade=t=in:st={t0:.2f}:d=0.12:alpha=1,"
                    f"fade=t=out:st={max(t0, t1 - fd):.2f}:d={fd}:alpha=1"
                    f"[{lab}]")
                fc.append(
                    f"[{prev}][{lab}]overlay=x={vx}:y={vy}:"
                    f"enable='between(t,{t0:.2f},{t1:.2f})'[b{i}_{j}]")
                prev = f"b{i}_{j}"
                n_visuals += 1
        print(f"[studio] {n_visuals} distinct visuals, each shown once",
              flush=True)
        # Mascots — Data TRAVELS. He glides from his previous spot to this
        # beat's spot across the WHOLE beat (not a quick slide-then-park), so
        # his x/y is always changing — he's never static in one place. A gentle
        # bob rides on top. In CLEAN this traces a path around the frame; in
        # legacy it still walks between numbers.
        prev_tl = home
        for k, (tlx, tly, w0, w1, _a, _f, _p, sc) in enumerate(seq):
            gi = masc_input[k]
            # Glide across nearly the WHOLE beat (settle only the last ~8%), and
            # ride a continuous 2D idle on top — a vertical bob plus a small
            # horizontal sway — so Data is NEVER globally static, even when he's
            # "parked". A static host is what the temporal grade reads as a held
            # frame (the payoff's static pose). Keep him alive every frame.
            # Sweep in FAST (arrive by ~30% of the beat), then hold position and
            # PERFORM the animated action for the rest — so the sampled frames
            # catch him ACTING on the data, not endlessly sliding across it.
            arrive = w0 + max(0.4, (w1 - w0) * 0.30)
            # A data beat sweeps in from its own entry point (onto the datum);
            # otherwise Data glides from where he last was.
            start = entries.get(k, prev_tl)
            # THE IDLE IS A HOVER NOW, NOT THE GATE'S MOTION SOURCE.
            #
            # History, because this line has been retuned twice and each
            # tuning was right about one constraint and wrong about another.
            # The original `6*sin(1.3*t)` moved 0.26 px/frame — invisible to
            # the temporal grade, and the channel posted nothing for eleven
            # days. The fix cranked it to `30*sin(6.0*t)`: 6 px/frame, gate
            # satisfied — but 6.0 rad/s is 0.95 Hz at ~1080 px/s^2 of
            # acceleration, a visible one-per-second jiggle stacked on a
            # card float wobbling at a different frequency. The operator
            # watched the shipped videos and called it "a weird shaking
            # motion". Both tunings chased one number and shipped the other.
            #
            # A third tuning moved the budget onto a whole-frame camera
            # breath and left the mascot a gentle hover. Calmer, still fake,
            # and the operator called it out again on 2026-08-25: rip the
            # camera shake out all the way. Both are gone.
            #
            # The budget is carried by REAL motion now — struggle reps
            # through the whole beat (charts._perf_phase) and an anchor that
            # WALKS the ranking instead of parking when the build finishes
            # (charts._tour_index). If a beat measures short, it needs more
            # of that, not a wobble. His glide between beats and his
            # performed bits are unchanged.
            # NO HOVER OSCILLATION either (2026-08-25 ruling: "no semblance
            # of the camera shake"). This 12px/9px sine pair was the last
            # survivor of the shake family — a sprite bobbing on the spot in
            # its own phase, which is what made two oscillations read as
            # "weird shaking" in the first place. His MOTION is his glide to
            # the beat's anchor (the piecewise below) and the performance
            # baked into the sprite; neither needs a bob to be alive.
            xe = f"({_piecewise([(w0, start[0]), (arrive, tlx)], 1)})"
            ye = f"({_piecewise([(w0, start[1]), (arrive, tly)], 1)})"
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
            prev_tl = (tlx, tly)
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
