"""ElevenLabs narration — the paid voice every channel tries first.

Operator, 2026-09-24: *"i have a elevn labs account that i pay for how do we
hook that up"*. This is the one place the pipeline talks to ElevenLabs; every
channel's narration path asks here first and keeps its old voice as the
fallback:

    curiosity (sleep films)   data_learning/ori_sleep.py      -> Kokoro
    explainer                 data_learning/studio_render.py  -> Speechify -> Kokoro
    explainer long-form       data_learning/longform_render.py -> Kokoro -> edge
    trending (reddit_story)   make_explainer_stacked.tts      -> Gemini -> Kokoro -> edge
    third                     third_capture/compose.py, sim_video.py -> edge

Rules, each held by tests/test_elevenlabs.py:

- **One voice per video.** A caller synthesizes EVERY line with ElevenLabs or
  none of them: one failed line throws the batch away and the whole video is
  re-voiced by the fallback. A voice that changes mid-clip is worse than
  either voice alone.
- **Never raises.** `speak()` returns audio or None (the engines' `maybe_*`
  contract): a dead key, an exhausted quota, a network blip or a voice id
  the account does not have all end in the old voice, never in a failed run.
- **A dead account is dead for the run.** 401/402/403 (bad key, quota spent,
  plan without the voice) stop every later call in the process, so a
  hundred-line film does not make a hundred refused requests. 429 and 5xx
  are retried with backoff first.
- **A character budget per run** (`ELEVENLABS_MAX_CHARS_PER_RUN`, default
  60,000) is checked BEFORE a video starts, so a run cannot spend a month's
  quota and cannot run out halfway through a video.
- **The voice is policy, so it lives in the registry**:
  `config/channel_registry.json` -> `channels.<id>.voice.elevenlabs`
  (`voice_id`, `model`, `stability`, `similarity_boost`, `style`). The env
  `ELEVENLABS_VOICE_ID` overrides every channel (a one-off test).
- **No key, no change.** Without `ELEVENLABS_API_KEY` every channel narrates
  exactly as it did before this module existed.

    python -m shared.elevenlabs voices      # the account's voices, to pick from
    python -m shared.elevenlabs say curiosity "A line to hear" out.wav
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KEY_ENV = "ELEVENLABS_API_KEY"
API = "https://api.elevenlabs.io/v1"
SR = 24000                                  # pcm_24000: available on every paid plan
DEFAULT = {
    # "George": a warm, unhurried storyteller — an ElevenLabs premade voice
    # every account has. A channel's registry entry overrides it.
    "voice_id": "JBFqnCBsd6RMkjVDRZzb",
    "model": "eleven_multilingual_v2",
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
}
MAX_CHARS_DEFAULT = 60000
RETRIES = 3

_dead: str | None = None                    # why the account stopped answering, for the run
_spent = 0                                  # characters sent this run
_logged: set = set()


def _log(msg: str) -> None:
    print(f"[elevenlabs] {msg}", file=sys.stderr, flush=True)


def key() -> str | None:
    # the repository secret is ELEVEN_LABS_API_KEY (the operator's name for
    # it); the workflows hand it over as ELEVENLABS_API_KEY. Either works.
    k = (os.environ.get(KEY_ENV) or os.environ.get("ELEVEN_LABS_API_KEY") or "").strip()
    return k or None


def voice_for(channel: str) -> dict:
    """The ElevenLabs settings for a channel: the registry's
    `voice.elevenlabs` block over the defaults, then ELEVENLABS_VOICE_ID."""
    cfg = dict(DEFAULT)
    try:
        from shared import channel_registry as CR
        ch = CR.channel(channel)
        cfg.update(((ch.get("voice") or {}).get("elevenlabs")) or {})
    except Exception:                        # noqa: BLE001 — an unregistered caller gets the default
        pass
    if os.environ.get("ELEVENLABS_VOICE_ID"):
        cfg["voice_id"] = os.environ["ELEVENLABS_VOICE_ID"].strip()
    return cfg


def budget() -> int:
    try:
        return int(os.environ.get("ELEVENLABS_MAX_CHARS_PER_RUN", MAX_CHARS_DEFAULT))
    except ValueError:
        return MAX_CHARS_DEFAULT


def available(channel: str) -> bool:
    """True when a key is set and the account has not refused this run."""
    return key() is not None and _dead is None


def can_afford(texts) -> bool:
    """Whether a WHOLE video fits in what is left of the run's budget. Asked
    before the first line, so a video is never started and abandoned."""
    need = sum(len(t or "") for t in texts)
    left = budget() - _spent
    if need > left:
        _log(f"this video needs {need:,} characters and the run has {left:,} left of "
             f"{budget():,} (ELEVENLABS_MAX_CHARS_PER_RUN): using the fallback voice")
        return False
    return True


def _request(url: str, body: bytes | None, headers: dict, timeout: float = 90):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    return urllib.request.urlopen(req, timeout=timeout)


def _pcm_to_float(raw: bytes):
    import numpy as np
    n = len(raw) // 2
    return (np.frombuffer(raw[: n * 2], dtype="<i2").astype(np.float32) / 32768.0)


def _resample(a, sr_from: int, sr_to: int):
    import numpy as np
    if sr_from == sr_to or len(a) == 0:
        return a
    n = int(round(len(a) * sr_to / sr_from))
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def speak(text: str, channel: str, sr: int = SR, _opener=None):
    """One line, spoken in the channel's ElevenLabs voice, as float32 mono
    samples at `sr`. None when there is no key, the account refused, the
    budget is spent or the request failed after retries. Never raises."""
    global _dead, _spent
    text = (text or "").strip()
    k = key()
    if not text or k is None or _dead is not None:
        return None
    if _spent + len(text) > budget():
        _log(f"character budget for the run spent ({budget():,}); falling back")
        return None
    cfg = voice_for(channel)
    url = f"{API}/text-to-speech/{cfg['voice_id']}?output_format=pcm_{SR}"
    settings = {"stability": cfg["stability"], "similarity_boost": cfg["similarity_boost"],
                "style": cfg["style"], "use_speaker_boost": True}
    if cfg.get("speed") is not None:
        settings["speed"] = cfg["speed"]     # a sleep film is read slowly
    headers = {"xi-api-key": k, "Content-Type": "application/json", "Accept": "audio/pcm"}
    opener = _opener or _request
    for attempt in range(RETRIES):
        body = json.dumps({"text": text, "model_id": cfg["model"], "voice_settings": settings}).encode()
        try:
            with opener(url, body, headers) as r:
                raw = r.read()
            if len(raw) < 200:
                raise ValueError(f"only {len(raw)} bytes of audio")
            _spent += len(text)
            if (channel, cfg["voice_id"]) not in _logged:
                _logged.add((channel, cfg["voice_id"]))
                _log(f"{channel}: voice {cfg['voice_id']} on {cfg['model']}")
            return _resample(_pcm_to_float(raw), SR, sr)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode(errors="replace")[:300]
            except Exception:                # noqa: BLE001
                pass
            if e.code in (401, 402, 403):
                _dead = f"HTTP {e.code}: {detail}"
                _log(f"the account refused ({_dead}); every channel uses its fallback voice for the rest "
                     f"of this run. A spent quota, a revoked key or a plan without this voice reads like this.")
                return None
            if e.code in (400, 422) and "speed" in settings:
                # a model that does not take a speed: say it once, go on without
                _log(f"{channel}: the model refused a speed setting (HTTP {e.code}); speaking at its own pace")
                settings.pop("speed")
                continue
            if e.code in (400, 404, 422):
                _log(f"{channel}: voice {cfg['voice_id']!r} / model {cfg['model']!r} refused "
                     f"(HTTP {e.code}: {detail}); run `python -m shared.elevenlabs voices` for the ids "
                     f"this account has")
                _list_voices_once(k)
                return None
            if attempt == RETRIES - 1:
                _log(f"{channel}: HTTP {e.code} after {RETRIES} tries: {detail[:160]}")
                return None
            time.sleep(2 ** attempt * (3 if e.code == 429 else 1))
        except Exception as e:               # noqa: BLE001 — network, timeout, short read
            if attempt == RETRIES - 1:
                _log(f"{channel}: {type(e).__name__}: {str(e)[:160]}")
                return None
            time.sleep(2 ** attempt)
    return None


def speak_to_file(text: str, channel: str, out: Path) -> bool:
    """One line to a file: .wav written directly, anything else (.mp3)
    through ffmpeg. False on any failure, with nothing left at `out`."""
    import subprocess
    import soundfile as sf
    a = speak(text, channel)
    if a is None:
        return False
    out = Path(out)
    try:
        if out.suffix.lower() == ".wav":
            sf.write(str(out), a, SR)
        else:
            tmp = out.with_suffix(".eleven.wav")
            sf.write(str(tmp), a, SR)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-codec:a", "libmp3lame",
                            "-qscale:a", "2", str(out)], check=True)
            tmp.unlink(missing_ok=True)
        return out.exists() and out.stat().st_size > 200
    except Exception as e:                   # noqa: BLE001
        _log(f"could not write {out.name}: {e}")
        out.unlink(missing_ok=True)
        return False


def speak_all(texts, channel: str, outs) -> bool:
    """Every line or none: True only when every text was written to its
    path. On any failure the files already written are removed, so the
    caller re-voices the whole video with its fallback."""
    texts, outs = list(texts), [Path(o) for o in outs]
    if not available(channel) or not can_afford(texts):
        return False
    for t, o in zip(texts, outs):
        if not speak_to_file(t, channel, o):
            for p in outs:
                p.unlink(missing_ok=True)
            _log(f"{channel}: a line failed, so the whole video uses the fallback voice (one voice per video)")
            return False
    return True


class Voice:
    """A `.say(text) -> samples` voice for renderers that take one (the sleep
    film). Raises VoiceUnavailable when a line cannot be spoken, so the
    caller re-narrates the whole film with its fallback. Picklable, so it
    can be built in a process pool."""

    def __init__(self, channel: str = "curiosity", sr: int = SR):
        self.channel, self.sr = channel, sr

    def say(self, text: str):
        a = speak(text, self.channel, self.sr)
        if a is None:
            raise VoiceUnavailable(_dead or f"ElevenLabs could not speak a line for {self.channel}")
        return a


class VoiceUnavailable(RuntimeError):
    pass


_listed = False


def _list_voices_once(k: str) -> None:
    global _listed
    if _listed:
        return
    _listed = True
    for v in list_voices(k)[:40]:
        _log(f"  voice {v['voice_id']}  {v['name']}  ({v.get('category', '')})")


def list_voices(k: str | None = None) -> list[dict]:
    k = k or key()
    if not k:
        return []
    try:
        with _request(f"{API}/voices", None, {"xi-api-key": k}, timeout=30) as r:
            data = json.loads(r.read())
        return [{"voice_id": v.get("voice_id"), "name": v.get("name"), "category": v.get("category")}
                for v in data.get("voices", [])]
    except Exception as e:                   # noqa: BLE001
        _log(f"could not list voices: {e}")
        return []


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("voices", "say"):
        print(__doc__)
        return 2
    if key() is None:
        print(f"{KEY_ENV} is not set")
        return 1
    if argv[0] == "voices":
        for v in list_voices():
            print(f"{v['voice_id']}  {v['name']}  ({v.get('category', '')})")
        return 0
    channel, text, out = argv[1], argv[2], Path(argv[3] if len(argv) > 3 else "eleven.wav")
    ok = speak_to_file(text, channel, out)
    print(f"{'wrote' if ok else 'FAILED'} {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
