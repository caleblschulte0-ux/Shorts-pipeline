"""Round 14 (operator, 2026-10-16, of round 13: all robotic, several too
soft). Gemini's speech model takes a DIRECTOR'S NOTE in plain words, so it can
be told how a person would say it. Deeper male voices only, on the spoken
script. Standard library only: this job holds the key. Writes
hq_gemini_<voice>_raw.wav (24 kHz) for enhance_hq.py in a job with no key.
"""
import base64, json, os, sys, time, urllib.request, urllib.error, wave
from pathlib import Path
HERE = Path(__file__).parent
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
key = os.environ["GEMINI_API_KEY"]; log = {}
B = "https://generativelanguage.googleapis.com/v1beta/models"
LINES = json.loads((HERE / "spoken_lines.json").read_text())["spoken"]
NOTE = ("Read this the way a regular guy in his mid twenties tells a buddy a wild fact he just "
        "learned. Low, relaxed, confident American voice. Natural rhythm, small pauses where a "
        "person would breathe, a little grin in the voice. Not a narrator, not an announcer, not "
        "a radio voice. Just talking:\n\n")
VOICES = os.environ.get("TTS_VOICES", "Charon,Orus,Algenib,Iapetus,Alnilam,Umbriel,Achird,Schedar").split(",")

def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key},
                                 method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=240) as r: return json.loads(r.read()), None
    except urllib.error.HTTPError as e: return None, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e: return None, str(e)[:300]

ms, err = get(f"{B}?pageSize=200")
tts = [m["name"].split("/")[1] for m in (ms or {}).get("models", []) if "tts" in m["name"]]
log["tts_models"] = tts or err
pref = ["pro", "flash"]
model = next((m for p in pref for m in sorted(tts, reverse=True) if p in m), None)
log["model_used"] = model
for v in VOICES:
    for attempt, mdl in enumerate([model] + [m for m in sorted(tts, reverse=True) if m != model][:2]):
        r, err = get(f"{B}/{mdl}:generateContent", {
            "contents": [{"parts": [{"text": NOTE + " ".join(LINES)}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}}}})
        if r: break
        log[f"{v}_{mdl}"] = err; time.sleep(30)
    if not r: continue
    pcm = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open(str(out / f"hq_gemini_{v}_raw.wav"), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(pcm)
    log[v] = f"ok ({mdl})"; time.sleep(25)
(out / "log_gemini.txt").write_text(json.dumps(log, indent=1)); print(json.dumps(log, indent=1))
