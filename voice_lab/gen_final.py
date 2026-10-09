"""Finalists (operator, 2026-10-09: "stop finding new voices ... narrow one
down"): Voices 11, 24, 34, 38, 39, each voicing two real posted stories
exactly as the channel's code spoke them, full model at the channel's
tempo and Turbo a notch slower."""
import json, sys, time, traceback
from pathlib import Path
import torch, torchaudio
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from finish import finish
REFS = {"11": "young/globe_06.ogg", "24": "tune/tune_A.ogg", "34": "sim/sim_04.ogg",
        "38": "sim/sim_08.ogg", "39": "sim/sim_09.ogg"}
voice, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stories = json.loads((HERE / "final_stories.json").read_text())
ref = str(HERE / REFS[voice]); torch.set_num_threads(4); log = []
from chatterbox.tts import ChatterboxTTS
from chatterbox.tts_turbo import ChatterboxTurboTTS
for model, M, kw, tempo in [("full", ChatterboxTTS, {"exaggeration": 0.75, "cfg_weight": 0.35}, 1.12),
                            ("turbo", ChatterboxTurboTTS, {}, 1.05)]:
    m = M.from_pretrained(device="cpu")
    if kw: m.prepare_conditionals(ref, exaggeration=kw["exaggeration"])
    else: m.prepare_conditionals(ref)
    for story, lines in stories.items():
        name = f"final_v{voice}_{model}_{story.split('-')[0]}"; t0 = time.time()
        try:
            wavs = []
            for i, t in enumerate(lines):
                torch.manual_seed(1000 + i)
                w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
            finish(wavs, out / f"{name}.mp3", tempo)
            for w in wavs: w.unlink()
            log.append(f"{name}: {time.time()-t0:.0f}s")
        except Exception:
            log.append(name + " failed: " + traceback.format_exc()[-400:])
    del m
(out / f"log_{voice}.txt").write_text("\n".join(log)); print("\n".join(log))
