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


def _build_hook_receipt(story_cfg: dict, work: Path, slug: str):
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
            stamp=(f"+{pct}%" if pct else ""), frames=64)
        import glob as _glob
        return pat, len(_glob.glob(pat.replace("%02d", "*")))
    except Exception as e:  # noqa: BLE001 — never let the cold-open kill a render
        print(f"[studio] hook receipt skipped: {e}", flush=True)
        return None


def build_story_ass(st: story.Story, windows, events, out: Path,
                    accent: str = "&H4FD1F5&", hook_visual: bool = False) -> None:
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
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Cap,,0,0,0,,"
                         f"{ch.strip()}")

    # 0: HOOK — LEAD WITH THE PUNCHLINE. The single biggest shock-number slams
    # onto frame 1 as the hero (the same gut-punch the thumbnail promises),
    # with the take spelled out beneath it in fast 2-word bursts. No more five
    # seconds of an idle mascot before any substance — the payoff is on screen
    # at t=0, which is the only moment that decides whether they keep watching.
    h0, h1 = windows[0]
    headline = _headline_number(st)
    # When a full-frame HOOK VISUAL (the receipt) is on screen it IS the hero —
    # the big number + claim would just collide with it, so they're suppressed
    # and the receipt + VO captions carry the open.
    if headline and not hook_visual:
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
        q = ("{\\an5\\pos(540,1330)\\fs46\\c&HFFFFFF&\\b1\\bord3\\3c&H000000&"
             "\\shad0\\fad(300,0)}" + _wrap(question, 24))
        lines.append(f"Dialogue: 5,{_ass_time(qs)},{_ass_time(c1)},Cap,,0,0,0,,{q}")
        # CTA pops in late (below the big central mascot) with a bounce.
        cta = ("{\\an5\\move(540,1454,540,1442,0,900)\\fs54\\c&H" + acc
               + "&\\b1\\bord5\\3c&H000000&\\shad0\\fad(300,0)"
               "\\fscx82\\fscy82\\t(0,300,\\fscx100\\fscy100)}COMMENT BELOW ▼")
        lines.append(f"Dialogue: 5,{_ass_time(cs)},{_ass_time(c1)},Cap,,0,0,0,,{cta}")
    src = " · ".join(st.sources)
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


def _place_mascot(active, seg_anchors):
    """Stand the mascot right beside the active number, inside the chart, in
    empty space that doesn't cover ANY number. Returns (body_cx, body_cy,
    variant) where variant is 'L' (left of number, points right), 'R' (right
    of number, points left) or 'U' (fallback below the card, points up)."""
    S = MASCOT_SIZE
    bw, bh = 0.52 * S, 0.78 * S
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
        # Custom thumbnail next to the video (title-aligned packaging). Cheap —
        # reuses the already-built story; the uploader picks it up by path.
        try:
            make_thumbnail(st, theme, out_path.with_suffix(".jpg"))
        except Exception as e:  # noqa: BLE001 — never fail a render over a thumb
            print(f"[studio] thumbnail skipped: {e}", file=sys.stderr)
        sentences = st.sentences()
        narration, windows = synth_narration(sentences, work, voice)
        total = _dur(narration) + 0.3

        bokeh = ambient.make_bokeh_strip(work / "bokeh.png", seed=theme["seed"])
        footmask = work / "foot_mask.png"
        _make_mandel_mask(footmask, W, FOOT_H, feather=130, bottom=70)
        events = _plan_events(st, windows)
        # Full soundtrack: narration + ducked theme music + visual-synced SFX.
        soundtrack = _build_soundtrack(narration, windows, events, total,
                                       theme.get("vibe", "calm"), work, slug)
        # HOOK VISUAL: a receipt whose total races up (built from the story's own
        # data). When present it becomes the cold-open and the ASS hero number is
        # suppressed so they don't collide.
        receipt = _build_hook_receipt(story_cfg, work, slug)
        ass = work / "cap.ass"
        build_story_ass(st, windows, events, ass, accent=accent_ass,
                        hook_visual=bool(receipt))
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
            if (getattr(st.segments[i], "kind", "") in HOST_BAKED_KINDS
                    or getattr(st.segments[i], "host_baked", False)):
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

            # HOOK: Data REACTS with a bespoke bit. If the receipt visual is up
            # (it fills the top ~60%), he sits BELOW it reacting up; otherwise he
            # is the central visual himself.
            hook_y = float(H * 0.62) if receipt else float(H * 0.40)
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
            # 8th tuple field = per-beat SCALE. Hook + closing get a BIG mascot
            # (fills the frame, and his looping animation is large-area continuous
            # motion — the reliable way to kill a frozen 'dead card' run and the
            # empty void the gate flags on those beats).
            seq.append((Cx, hook_y, windows[0][0], windows[0][1],
                        UP_ANGLE, False, hook_perf, 1.2))
            for i in range(nseg):
                wi = windows[1 + i] if 1 + i < len(windows) else None
                if not wi:
                    continue
                spec = _seg_spec(i)
                act = spec.get("action") if isinstance(spec, dict) else ""
                x, y = _spot(i, act)
                seq.append((x, y, wi[0], wi[1], UP_ANGLE, False, spec, 1.0))
            # CLOSING: Data is the SPEAKER — big and central so his celebration
            # is the payoff and nothing sits frozen.
            close_act = _director.celebrate() if _director else "cheer"
            seq.append((Cx, float(H * 0.30), windows[-1][0], windows[-1][1],
                        UP_ANGLE, False, close_act, 1.35))
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
        seq.sort(key=lambda s: s[2])
        filled, cursor = [], 0.0
        for entry in seq:
            w0, w1 = entry[2], entry[3]
            if w0 - cursor > 0.05:
                filled.append((home[0], home[1], cursor, w0,
                               UP_ANGLE, False, gap_fill, 1.0))
            filled.append(entry)
            cursor = max(cursor, w1)
        if total - cursor > 0.05:
            filled.append((home[0], home[1], cursor, total,
                           UP_ANGLE, False, gap_fill, 1.0))
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
        _grad = (("0x0C0E13", "0x0E1118", "0x12161F", "0x0A0C11")
                 if CLEAN else theme["grad"])       # CLEAN = flat dark editorial
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
        seg_idx = {}
        import glob as _glob
        for i, seg in enumerate(st.segments):
            if seg.chart_path:
                # chart_path is a printf build sequence (..._build%02d.png). Play
                # it at a framerate that spans MOST of the beat instead of a fixed
                # 24fps that finishes in <1s and then freezes — that static hold
                # is what tanks pace / reads as dead air. tpad below covers only a
                # short tail.
                nfr = len(_glob.glob(seg.chart_path.replace("%02d", "*"))) or 24
                wi = windows[1 + i] if 1 + i < len(windows) else None
                beat = (wi[1] - wi[0]) if wi else 2.0
                # Play at a smooth framerate (>=18fps) so growth doesn't step in
                # visible jumps; with ~60 build frames this spans typical beats,
                # and a short settle tail on longer beats stays under dead-air.
                cfps = max(18.0, min(30.0, nfr / max(0.8, beat - 0.2)))
                inputs += ["-framerate", f"{cfps:.2f}", "-i", seg.chart_path]
                seg_idx[i] = idx
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
            fc = [f"[0:v]format=rgba,vignette=PI/6,"
                  f"drawbox=x=0:y=0:w={W}:h=8:color=0x{_ac}@1.0:t=fill[bg]"]
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
            # KEN BURNS: the hook image is a still, so a static hold of it for the
            # whole hook window is the #1 swipe-away trigger. Push in slowly
            # (zoompan) so the first frame is ALWAYS moving — never a frozen photo.
            zframes = max(1, int((he + 0.6) * FPS))
            # HARD, fast push-in (1.12 -> ~1.6) so frame 1 is already moving with
            # energy — a slow drift reads as a static slide and gets swiped.
            fc.append(
                f"[{hook_idx}:v]scale={int(W*1.6)}:{int(H*1.6)}:"
                f"force_original_aspect_ratio=increase,crop={int(W*1.6)}:{int(H*1.6)},"
                f"zoompan=z='min(zoom+0.0032,1.6)':d={zframes}:fps={FPS}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H},"
                f"eq=brightness=-0.14:saturation=1.12:contrast=1.06,format=rgba,"
                f"fade=t=out:st={max(0.1, he - 0.5):.2f}:d=0.5:alpha=1[hookimg]")
            fc.append(
                f"[{prev}][hookimg]overlay=0:0:"
                f"enable='between(t,0,{he:.2f})'[hk]")
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
        for i, seg in enumerate(st.segments):
            if i not in seg_idx:
                continue
            gi = seg_idx[i]
            s0, s1 = windows[1 + i]
            fd = 0.14        # short cross-fade so no frame lands on near-black
            hold = max(0.5, (s1 - s0)) + 1.0
            # Full-frame viz (diorama, timeline, fill_vessel, ...) are authored
            # at 1080x1920 and fill the whole frame; card charts/maps stay in the
            # top chart region. The registry is charts' single source of truth.
            full = getattr(st.segments[i], "kind", "") in charts.FULLFRAME_RENDERERS
            vw, vh = (W, H) if full else (CHART_W, CHART_H)
            vx, vy = (0, 0) if full else (CHART_X, CHART_Y)
            fc.append(
                f"[{gi}:v]tpad=stop_mode=clone:stop_duration={hold:.2f},"
                f"setpts=PTS-STARTPTS+{s0:.2f}/TB,"
                f"scale={vw}:{vh},format=rgba,"
                f"fade=t=in:st={s0:.2f}:d=0.12:alpha=1,"
                f"fade=t=out:st={max(s0, s1 - fd):.2f}:d={fd}:alpha=1[g{i}]")
            fc.append(
                f"[{prev}][g{i}]overlay=x={vx}:y={vy}:"
                f"enable='between(t,{s0:.2f},{s1:.2f})'[b{i}]")
            prev = f"b{i}"
        # Mascots — Data TRAVELS. He glides from his previous spot to this
        # beat's spot across the WHOLE beat (not a quick slide-then-park), so
        # his x/y is always changing — he's never static in one place. A gentle
        # bob rides on top. In CLEAN this traces a path around the frame; in
        # legacy it still walks between numbers.
        prev_tl = home
        for k, (tlx, tly, w0, w1, _a, _f, _p, sc) in enumerate(seq):
            gi = masc_input[k]
            # Glide over most of the beat, easing in the last bit so he settles
            # only briefly before the next move — motion fills the whole window.
            arrive = w0 + max(0.5, (w1 - w0) * 0.82)
            xe = _piecewise([(w0, prev_tl[0]), (arrive, tlx)], 1)
            ye = f"({_piecewise([(w0, prev_tl[1]), (arrive, tly)], 1)})+5*sin(1.7*t)"
            Sk = int(round(S * sc))
            off = (Sk - S) // 2            # keep the bigger sprite centred on target
            fc.append(f"[{gi}:v]format=rgba,scale={Sk}:{Sk}[mk{k}]")
            fc.append(f"[{prev}][mk{k}]overlay=x='({xe})-{off}':y='({ye})-{off}':"
                      f"eval=frame:enable='between(t,{w0:.2f},{w1:.2f})'[mb{k}]")
            prev = f"mb{k}"
            prev_tl = (tlx, tly)
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
