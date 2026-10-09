"""Clone each round-8 look-alike: full model (energy as on the rows the
operator liked) and Turbo finished a notch slower (1.05)."""
import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
refs, out, which = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
shard, nshard = map(int, sys.argv[4].split("/"))
out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(4); log = []
voices = [v for i, v in enumerate(sorted(refs.glob("sim_*.wav"))) if i % nshard == shard]
if which == "turbo":
    from chatterbox.tts_turbo import ChatterboxTurboTTS as M; kw = {}; tempo = 1.05
else:
    from chatterbox.tts import ChatterboxTTS as M; kw = {"exaggeration": 0.75, "cfg_weight": 0.35}; tempo = L["tempo"]
m = M.from_pretrained(device="cpu")
for v in voices:
    name = f"{which}_{v.stem}"; t0 = time.time()
    try:
        if which == "turbo": m.prepare_conditionals(str(v))
        else: m.prepare_conditionals(str(v), exaggeration=kw["exaggeration"])
        wavs = []
        for i, t in enumerate(L["lines"]):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
        finish(wavs, out / f"{name}.mp3", tempo)
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-400:])
(out / f"log_{which}_{shard}.txt").write_text("\n".join(log)); print("\n".join(log))
