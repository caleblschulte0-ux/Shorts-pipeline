import json, sys, soundfile as sf
from pathlib import Path
from kokoro_onnx import Kokoro
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
k = Kokoro("kokoro_models/kokoro-v1.0.onnx", "kokoro_models/voices-v1.0.bin")
for v in ["am_michael", "am_fenrir", "bm_george", "am_puck", "am_echo"]:
    wavs = []
    for i, t in enumerate(L["lines"]):
        s, sr = k.create(t, voice=v, speed=1.0, lang="en-us")
        w = out / f"_k_{v}_{i}.wav"; sf.write(str(w), s, sr); wavs.append(w)
    finish(wavs, out / f"kokoro_{v}.mp3", L["tempo"])
# reference clip for the cloning engines: a voice we own outright (Apache-2.0)
s, sr = k.create(L["reference_text"], voice="am_michael", speed=1.0, lang="en-us")
sf.write(str(out / "ref_kokoro_michael.wav"), s, sr)
for f in out.glob("_k_*.wav"): f.unlink()
