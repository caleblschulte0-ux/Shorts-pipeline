"""Variants of Voice 24: energy (exaggeration) and pace (cfg) on the full
model, the three reference cuts, and Turbo on each cut."""
import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
refs, out, which = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(4); log = []
JOBS = {
    "fullA": [("A", 0.5, 0.5), ("A", 1.0, 0.3)],
    "fullB": [("B", 0.75, 0.35), ("B", 1.0, 0.3)],
    "fullC": [("C", 0.75, 0.35), ("C", 1.0, 0.3)],
    "turbo": [("A", None, None), ("B", None, None), ("C", None, None)],
}[which]
if which == "turbo":
    from chatterbox.tts_turbo import ChatterboxTurboTTS as M
else:
    from chatterbox.tts import ChatterboxTTS as M
m = M.from_pretrained(device="cpu")
for cut, ex, cfg in JOBS:
    ref = str(refs / f"tune_{cut}.wav")
    name = f"tune_turbo_{cut}" if ex is None else f"tune_full_{cut}_e{int(ex*100)}_c{int(cfg*100)}"
    t0 = time.time()
    try:
        if ex is None: m.prepare_conditionals(ref); kw = {}
        else: m.prepare_conditionals(ref, exaggeration=ex); kw = {"exaggeration": ex, "cfg_weight": cfg}
        wavs = []
        for i, t in enumerate(L["lines"]):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
        finish(wavs, out / f"{name}.mp3", L["tempo"])
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-400:])
(out / f"log_tune_{which}.txt").write_text("\n".join(log)); print("\n".join(log))
