import json, sys, time, traceback
from pathlib import Path
import soundfile as sf
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ref = sys.argv[2]
log = []


def render(name, gen):
    t0 = time.time(); ws = []
    for i, t in enumerate(L["lines"]):
        w = out / f"_n_{name}_{i}.wav"
        sf.write(str(w), gen(t), 24000); ws.append(w)
    finish(ws, out / f"{name}.mp3", L["tempo"])
    for w in ws:
        w.unlink()
    log.append(f"{name}: {time.time()-t0:.0f}s on CPU")


try:
    from neutts import NeuTTS
    tts = NeuTTS(backbone_repo="neuphonic/neutts-air", backbone_device="cpu",
                 codec_repo="neuphonic/neucodec", codec_device="cpu")
    codes = tts.encode_reference(ref)
    render("neutts_air_clone_michael", lambda t: tts.infer(t, codes, L["reference_text"]))
except Exception:  # noqa: BLE001
    log.append("neutts air failed: " + traceback.format_exc()[-800:])
try:
    from neutts import NeuTTS2E
    tts2 = NeuTTS2E()
    for spk in ["paul", "steven"]:
        render(f"neutts_2e_{spk}", lambda t, s=spk: tts2.infer(t, speaker=s, emotion="neutral"))
except Exception:  # noqa: BLE001
    log.append("neutts 2e failed: " + traceback.format_exc()[-800:])
(out / "neutts_log.txt").write_text("\n".join(log))
print("\n".join(log))
