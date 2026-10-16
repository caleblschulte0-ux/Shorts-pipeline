"""The explainer's narrator: a Google Gemini voice, DIRECTED like a person.

caaleb, 2026-10-16, after fourteen rounds of the voice lab in which every
clone "still sounds like AI", was "robotic", and did not "talk like a normal
person": of six Gemini voices reading the spoken script, *"I like these
voices."* Chatterbox's Voice 38 (2026-10-09) was reversed on 10-11.

What made them land is the DIRECTION, not the voice alone. Gemini's speech
model takes a director's note, and a note written as plain prose is READ
ALOUD (the lab's first take ran 45 s for a 25 s script). Its own prompting
guide puts the note above a `#### TRANSCRIPT` heading, so `NOTE` does.

Free tier, measured: ~100 requests a day per model (the 429 quota says so
whatever AI Studio shows), resetting at midnight Pacific; each model has its
own quota, so `MODELS` is two. A line it voiced is never voiced again (the
caller's line cache), so a redraft only pays for the lines it changed. A
per-DAY 429 turns that model off for the run; a per-minute one waits the
delay Google names, within `WAIT_MAX_S`.

Like every voice here it is LISTENED to (`chatterbox_tts.heard`): an LLM
voice can ad-lib, or read its direction aloud, and the showrunner judges
frames, not audio. A line that will not come out right makes `maybe_voice`
return None and the caller voices the WHOLE video with its next engine,
never half and half. Standard library only; it never raises.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta/models"
#: caaleb's pick from round 14 (repo variable GEMINI_TTS_VOICE). One voice
#: for every video; never rotated, never matched to a topic.
DEFAULT_VOICE = "Charon"
VOICES = ("Charon", "Orus", "Iapetus", "Umbriel", "Achird", "Schedar",
          "Algenib", "Alnilam")
#: Each has its own free daily quota. Round 14 voiced on both.
MODELS = ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts")
RATE = 24000                       # 16-bit mono PCM, what the API returns
WAIT_MAX_S = 75.0
REDRAWS = 1

#: The direction round 14 was voiced with, verbatim in substance.
NOTE = """# AUDIO PROFILE: Mike
A regular guy in his mid twenties from the Midwest. Low, relaxed, confident voice.

## THE SCENE
He's on the couch telling his buddy a wild fact he just read. Casual, not performing.

### DIRECTOR'S NOTES
Talk, don't narrate. Natural American rhythm, small pauses where a person breathes,
a little grin in the voice on the funny parts. Not an announcer, not a radio voice,
not a YouTube narrator. Read only the transcript below.

#### TRANSCRIPT
"""

#: model -> why it is off for the rest of this run.
_DEAD: dict[str, str] = {}
LAST_FAILURE: str | None = None


def voice() -> str:
    v = os.environ.get("GEMINI_TTS_VOICE", "").strip()
    return next((x for x in VOICES if x.lower() == v.lower()), DEFAULT_VOICE)


def cache_model() -> str:
    """What the line cache keys on besides the voice: the direction. A new
    note is a new read, so it must not reuse lines voiced under the old."""
    import hashlib
    return "note-" + hashlib.sha256(NOTE.encode()).hexdigest()[:12]


def _key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def available() -> bool:
    return bool(_key()) and any(m not in _DEAD for m in MODELS)


def _retry_s(body: str) -> float | None:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body or "")
    return float(m.group(1)) if m else None


def _per_day(body: str) -> bool:
    return bool(re.search(r"PerDay|per_day|RequestsPerDay", body or "", re.I))


def _post(model: str, text: str, name: str):
    """One request. (pcm bytes, None) or (None, (http code, body))."""
    body = {"contents": [{"parts": [{"text": NOTE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": name}}}}}
    req = urllib.request.Request(
        f"{API}/{model}:generateContent", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": _key()},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        part = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        return base64.b64decode(part), None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:2000]
        except Exception:  # noqa: BLE001
            detail = ""
        return None, (e.code, detail)
    except Exception as e:  # noqa: BLE001
        return None, (0, str(e)[:300])


def _write(pcm: bytes, out: Path) -> None:
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(pcm)


def _trim(wav: Path) -> None:
    """Leading/trailing silence off (the caller adds its own breath)."""
    import subprocess
    tmp = wav.with_suffix(".trim.wav")
    cut = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                        "-af", f"{cut},areverse,{cut},areverse", "-ar", str(RATE),
                        "-ac", "1", "-c:a", "pcm_s16le", str(tmp)],
                       check=True, capture_output=True)
        tmp.replace(wav)
    except Exception:  # noqa: BLE001
        tmp.unlink(missing_ok=True)       # an untrimmed line is still a line


def voice_line(text: str, out: Path) -> tuple[bool, str]:
    """Voice ONE line into `out` (24 kHz mono WAV), across the models.
    (ok, why)."""
    name = voice()
    last = "no model left"
    for model in MODELS:
        waited = 0.0
        while model not in _DEAD:
            pcm, err = _post(model, text, name)
            if pcm and len(pcm) > 4000:
                _write(pcm, out)
                _trim(out)
                return True, model
            code, body = err or (0, "no audio")
            last = f"{model}: HTTP {code} {body[:160]}"
            if code == 429 and not _per_day(body):
                d = _retry_s(body) or 30.0
                if waited + d <= WAIT_MAX_S:
                    time.sleep(d); waited += d
                    continue
            if code in (0, 500, 503) and waited == 0.0:
                time.sleep(5); waited = 5.0   # one retry for a blip
                continue
            if code in (401, 403, 404, 429):
                _DEAD[model] = last
                print(f"[tts] gemini {model} off for this run: {last}",
                      file=sys.stderr, flush=True)
            break
    return False, last


def _fail(why: str) -> None:
    global LAST_FAILURE
    LAST_FAILURE = why
    print(f"[tts] gemini failed: {why}", file=sys.stderr, flush=True)


def maybe_voice(texts: list[str], outs: list[Path], *, normalize=None,
                listen: bool = True) -> list[Path] | None:
    """Voice every line into its `outs` path, each one listened to. The
    paths, or None on ANY failure (reason in LAST_FAILURE). Never raises."""
    global LAST_FAILURE
    LAST_FAILURE = None
    try:
        if not texts or len(texts) != len(outs):
            _fail("no lines")
            return None
        if not _key():
            _fail("no GEMINI_API_KEY")
            return None
        from engines.chatterbox_tts import heard
        for i, text in enumerate(texts):
            for attempt in range(REDRAWS + 1):
                ok, why = voice_line(text, Path(outs[i]))
                if not ok:
                    _fail(f"line {i}: {why}")
                    return None
                if not listen:
                    break
                ok, why = heard(Path(outs[i]), text, normalize)
                if ok:
                    break
                if why.startswith("listener unavailable"):
                    _fail(f"line {i}: {why}")
                    return None
                print(f"[tts] gemini line {i} redraw: {why}", file=sys.stderr,
                      flush=True)
            else:
                _fail(f"line {i} would not come out right: {why}")
                return None
        return [Path(o) for o in outs]
    except Exception as e:  # noqa: BLE001
        _fail(f"{type(e).__name__}: {str(e)[:200]}")
        return None
