"""Baselines: the paid voices the pipeline uses today, same lines.
Also reads the ElevenLabs subscription (costs no credits).
Standard library only: this job holds the API keys."""
import base64, json, os, sys, urllib.request, urllib.error, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
log = {}


def call(req):
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read(), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:300]


ek = os.environ.get("ELEVEN", "").strip()
if ek:
    b, err = call(urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription",
                                         headers={"xi-api-key": ek}))
    if b:
        s = json.loads(b)
        log["elevenlabs_subscription"] = {k: s.get(k) for k in (
            "tier", "character_count", "character_limit",
            "next_character_count_reset_unix", "status", "billing_period",
            "can_use_instant_voice_cloning", "can_use_professional_voice_cloning")}
    else:
        log["elevenlabs_subscription"] = err
    voice = os.environ.get("EL_VOICE") or "pNInz6obpgDQGcFmaJgB"
    for model in ["eleven_flash_v2_5", "eleven_multilingual_v2"]:
        wavs, err = [], None
        for i, t in enumerate(L["lines"]):
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_24000",
                data=json.dumps({"text": t, "model_id": model, "voice_settings":
                                 {"stability": 0.45, "similarity_boost": 0.8}}).encode(),
                headers={"xi-api-key": ek, "Content-Type": "application/json"}, method="POST")
            b, err = call(req)
            if not b:
                break
            w = out / f"_e_{model}_{i}.wav"
            with wave.open(str(w), "wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(b)
            wavs.append(w)
        if err:
            log[f"elevenlabs_{model}"] = err
        else:
            finish(wavs, out / f"elevenlabs_{model}.mp3", L["tempo"])
            log[f"elevenlabs_{model}"] = "ok"
        for w in wavs:
            w.unlink()
else:
    log["elevenlabs"] = "no key"

sk = os.environ.get("SPEECHIFY_API_KEY", "").strip()
if sk:
    wavs, err = [], None
    for i, t in enumerate(L["lines"]):
        req = urllib.request.Request(
            "https://api.speechify.ai/v1/audio/speech",
            data=json.dumps({"input": t, "voice_id": os.environ.get("SP_VOICE") or "henry",
                             "audio_format": "wav",
                             "model": os.environ.get("SP_MODEL") or "simba-3.2"}).encode(),
            headers={"Authorization": f"Bearer {sk}", "Content-Type": "application/json"},
            method="POST")
        b, err = call(req)
        if not b:
            break
        w = out / f"_s_{i}.wav"
        w.write_bytes(base64.b64decode(json.loads(b)["audio_data"]))
        wavs.append(w)
    if err:
        log["speechify"] = err
    else:
        finish(wavs, out / "speechify_henry_live.mp3", L["tempo"])
        log["speechify"] = "ok"
    for w in wavs:
        w.unlink()
else:
    log["speechify"] = "no key"
(out / "cloud_log.json").write_text(json.dumps(log, indent=1))
print(json.dumps(log, indent=1))
