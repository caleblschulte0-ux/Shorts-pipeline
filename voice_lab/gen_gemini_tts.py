"""Gemini TTS (free tier) on the same story, several voices, with a short
director's note. Standard library only: this job holds the key."""
import base64, json, os, sys, time, urllib.request, urllib.error, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
key = os.environ["GEMINI_API_KEY"]; log = {}
B = "https://generativelanguage.googleapis.com/v1beta/models"

def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key},
                                 method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read()), None
    except urllib.error.HTTPError as e: return None, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e: return None, str(e)[:300]

ms, err = get(f"{B}?pageSize=200")
tts = [m["name"].split("/")[1] for m in (ms or {}).get("models", []) if "tts" in m["name"]]
log["tts_models"] = tts or err
model = next((m for m in ["gemini-2.5-pro-preview-tts", "gemini-2.5-flash-preview-tts"] if m in tts), tts[0] if tts else None)
log["model_used"] = model
note = ("Read this like a curious, friendly YouTube Shorts narrator telling a friend a "
        "surprising fact. Natural, conversational, brisk pace, real emphasis on the "
        "numbers, no announcer voice:\n\n")
text = " ".join(L["lines"])
for v in ["Charon", "Puck", "Orus", "Fenrir", "Iapetus", "Algieba"]:
    r, err = get(f"{B}/{model}:generateContent", {
        "contents": [{"parts": [{"text": note + text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}}}})
    if not r: log[v] = err; time.sleep(20); continue
    pcm = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    w = out / f"_g_{v}.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(pcm)
    finish([w], out / f"gemini_{v}.mp3", 1.0); w.unlink(); log[v] = "ok"; time.sleep(8)
(out / "gemini_tts_log.json").write_text(json.dumps(log, indent=1)); print(json.dumps(log, indent=1))
