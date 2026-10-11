"""Round 9: clone every clean-source voice reading the two real posted
stories, exactly as production does it (full model, FULL_STYLE, tempo 1.12)."""
import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from finish import finish
refs, out = Path(sys.argv[1]), Path(sys.argv[2])
shard, nshard = map(int, sys.argv[3].split("/"))
out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(4); log = []
stories = json.loads((HERE / "final_stories.json").read_text())
voices = [v for i, v in enumerate(sorted(refs.glob("clean_*.wav"))) if i % nshard == shard]
from chatterbox.tts import ChatterboxTTS
kw = {"exaggeration": 0.75, "cfg_weight": 0.35}
m = ChatterboxTTS.from_pretrained(device="cpu")
for v in voices:
    m.prepare_conditionals(str(v), exaggeration=kw["exaggeration"])
    for story, lines in stories.items():
        name = f"say_{v.stem}_{story.split('-')[0]}"; t0 = time.time()
        try:
            wavs = []
            for i, t in enumerate(lines):
                torch.manual_seed(1000 + i)
                w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
            finish(wavs, out / f"{name}.mp3", 1.12)
            for w in wavs: w.unlink()
            log.append(f"{name}: {time.time()-t0:.0f}s")
        except Exception:
            log.append(name + " failed: " + traceback.format_exc()[-400:])
(out / f"log_{shard}.txt").write_text("\n".join(log)); print("\n".join(log))
