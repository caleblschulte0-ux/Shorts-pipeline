import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
ref = sys.argv[2] if len(sys.argv) > 2 else None
torch.set_num_threads(4)
log = []

def render(name, gen, sr):
    t0 = time.time(); wavs = []
    for i, t in enumerate(L["lines"]):
        w = out / f"_{name}_{i}.wav"
        torchaudio.save(str(w), gen(t).cpu(), sr); wavs.append(w)
    finish(wavs, out / f"{name}.mp3", L["tempo"])
    for w in wavs: w.unlink()
    log.append(f"{name}: {time.time()-t0:.0f}s on CPU")

try:
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    m = ChatterboxTurboTTS.from_pretrained(device="cpu")
    if ref:
        render("chatterbox_turbo_clone_michael",
               lambda t: m.generate(t, audio_prompt_path=ref), m.sr)
except Exception:
    log.append("turbo failed: " + traceback.format_exc()[-600:])

try:
    from chatterbox.tts import ChatterboxTTS
    m = ChatterboxTTS.from_pretrained(device="cpu")
    render("chatterbox_default", lambda t: m.generate(t, exaggeration=0.55, cfg_weight=0.45), m.sr)
    if ref:
        render("chatterbox_clone_michael",
               lambda t: m.generate(t, audio_prompt_path=ref, exaggeration=0.6,
                                    cfg_weight=0.4), m.sr)
except Exception:
    log.append("chatterbox failed: " + traceback.format_exc()[-600:])
(out / "chatterbox_log.txt").write_text("\n".join(log))
print("\n".join(log))
