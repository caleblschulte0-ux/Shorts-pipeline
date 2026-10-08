import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
refs = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(4); log = []

def render(name, gen, sr):
    t0 = time.time(); wavs = []
    for i, t in enumerate(L["lines"]):
        w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), gen(t).cpu(), sr); wavs.append(w)
    finish(wavs, out / f"{name}.mp3", L["tempo"])
    for w in wavs: w.unlink()
    log.append(f"{name}: {time.time()-t0:.0f}s")

from chatterbox.tts_turbo import ChatterboxTurboTTS
from chatterbox.tts import ChatterboxTTS
turbo = ChatterboxTurboTTS.from_pretrained(device="cpu")
full = ChatterboxTTS.from_pretrained(device="cpu")
for ref in sorted(refs.glob("ref_*.wav")):
    s = ref.stem[4:]
    for name, fn, sr in [
        (f"chatterbox_turbo_human_{s}", lambda t, r=str(ref): turbo.generate(t, audio_prompt_path=r), turbo.sr),
        (f"chatterbox_human_{s}", lambda t, r=str(ref): full.generate(t, audio_prompt_path=r, exaggeration=0.6, cfg_weight=0.4), full.sr)]:
        try: render(name, fn, sr)
        except Exception: log.append(name + " failed: " + traceback.format_exc()[-400:])
(out / "chatterbox_human_log.txt").write_text("\n".join(log)); print("\n".join(log))
