"""Blind listener test: each clip is sent to Gemini under a neutral name and
it rates how likely the voice is a real human. Real human recordings are mixed
in as controls so the scale is calibrated. Standard library only."""
import base64, json, os, random, sys, time, urllib.request, urllib.error
from pathlib import Path
d = Path(sys.argv[1]); key = os.environ["GEMINI_API_KEY"]
U = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
P = ("You are screening narration for a YouTube Shorts channel. Listen carefully. "
     "Viewers swipe away the moment a narrator sounds AI-generated. Rate how likely it is "
     "that this narrator is a REAL HUMAN recording rather than text-to-speech. Be skeptical: "
     "modern TTS is good, so listen for flat or repeated intonation, odd stress, robotic "
     "breaths, metallic timbre, unnatural pacing. Reply with JSON only: "
     '{"human_probability": 0-100, "tells": "short list of what gave it away, or none"}')
files = [f for f in d.glob("*.mp3")]; random.seed(7); random.shuffle(files)
res = {}
for f in files:
    scores, tells = [], []
    for rep in range(2):
        body = {"contents": [{"parts": [{"text": P}, {"inline_data": {"mime_type": "audio/mpeg",
                "data": base64.b64encode(f.read_bytes()).decode()}}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
        req = urllib.request.Request(U, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                t = json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
            j = json.loads(t); scores.append(int(j["human_probability"])); tells.append(j.get("tells", ""))
        except urllib.error.HTTPError as e:
            tells.append(f"HTTP {e.code}: {e.read().decode()[:160]}")
        except Exception as e:
            tells.append(str(e)[:160])
        time.sleep(7)
    res[f.stem] = {"human_probability": round(sum(scores) / len(scores)) if scores else None,
                   "tells": tells}
    print(f.stem, res[f.stem])
(d / "judge.json").write_text(json.dumps(res, indent=1))
