"""Clone each round-5 (detector-American) reference with Chatterbox FULL (energy dial up) and
TURBO, plus Chatterbox's own built-in voice, on the lab's sand lines."""
import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
L = json.loads((Path(__file__).parent / "lines.json").read_text())
refs = Path(sys.argv[1]); out = Path(sys.argv[2]); which = sys.argv[3]; shard, nshard = map(int, sys.argv[4].split("/"))
out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(4); log = []
voices = sorted(refs.glob("us_*.wav"))
voices = [v for i, v in enumerate(voices) if i % nshard == shard]
if which == "turbo":
    from chatterbox.tts_turbo import ChatterboxTurboTTS as M; kw = {}
else:
    from chatterbox.tts import ChatterboxTTS as M; kw = {"exaggeration": 0.75, "cfg_weight": 0.35}
m = M.from_pretrained(device="cpu")
for v in voices:
    name = f"{which}_{v.stem if v else 'builtin'}"; t0 = time.time()
    try:
        if v is not None:
            if which == "turbo": m.prepare_conditionals(str(v))
            else: m.prepare_conditionals(str(v), exaggeration=kw["exaggeration"])
        elif which != "turbo":
            m = M.from_pretrained(device="cpu")  # built-in voice: fresh conds
        wavs = []
        for i, t in enumerate(L["lines"]):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
        finish(wavs, out / f"{name}.mp3", L["tempo"])
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-400:])
(out / f"log_{which}_{shard}.txt").write_text("\n".join(log)); print("\n".join(log))
