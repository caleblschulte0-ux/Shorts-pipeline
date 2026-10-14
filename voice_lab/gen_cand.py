"""Round 11 (operator via coordinator, 2026-10-14: push the voice search and
bring back finished candidates). Every studio-clean voice (41-50) reads the
octopus story on the three processes round 10 tested beyond production:
Chatterbox calm with no speed-up (C), Zonos (E) and CosyVoice2 (F). A
naturalness model (UTMOS) then ranks everything, so the operator hears the
best few first instead of sixty files.
  python gen_cand.py ENGINE OUT i/n
"""
import json, subprocess, sys, time, traceback
from pathlib import Path
import torch, torchaudio
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from finish import finish
engine, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
shard, nshard = map(int, sys.argv[3].split("/"))
ORDER = ["libritts_8108", "libritts_839", "libritts_2428", "libritts_2952", "libritts_5536",
         "vctk_p311", "vctk_p315", "vctk_p334", "vctk_p345", "vctk_p360"]
VOICES = {str(41 + i): HERE / f"clean2/clean_{s}.flac" for i, s in enumerate(ORDER)}
VOICES = {v: r for i, (v, r) in enumerate(VOICES.items()) if i % nshard == shard}
LINES = json.loads((HERE / "final_stories.json").read_text())["octopus-nine-brains"]
LINES = [" ".join(l.replace("--", ",").replace("—", ",").split()) for l in LINES]
torch.set_num_threads(4); log = []

def wav_of(ref):
    w = out / f"_ref_{ref.stem}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ref), "-ac", "1", "-ar", "24000", str(w)], check=True)
    return str(w)

def run(name, say):
    t0 = time.time()
    try:
        wavs = []
        for i, t in enumerate(LINES):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; y, sr = say(t); torchaudio.save(str(w), y.cpu(), sr); wavs.append(w)
        finish(wavs, out / f"{name}.mp3", 1.0)
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-600:])
    print(log[-1], flush=True)

if engine == "chatterbox":
    from chatterbox.tts import ChatterboxTTS
    m = ChatterboxTTS.from_pretrained(device="cpu")
    for v, ref in VOICES.items():
        m.prepare_conditionals(wav_of(ref), exaggeration=0.5)
        run(f"cand_v{v}_C", lambda t: (m.generate(t, exaggeration=0.5, cfg_weight=0.5), m.sr))
elif engine == "zonos":
    sys.path.insert(0, "zonos_src")
    from zonos.model import Zonos
    from zonos.conditioning import make_cond_dict
    m = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device="cpu")
    for v, ref in VOICES.items():
        y, sr = torchaudio.load(wav_of(ref)); spk = m.make_speaker_embedding(y, sr)
        def say(t):
            c = m.prepare_conditioning(make_cond_dict(text=t, speaker=spk, language="en-us"))
            return m.autoencoder.decode(m.generate(c))[0], m.autoencoder.sampling_rate
        run(f"cand_v{v}_E", say)
else:
    sys.path[:0] = ["CosyVoice", "CosyVoice/third_party/Matcha-TTS"]
    import whisper
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import CosyVoice2
    asr = whisper.load_model("small.en")
    m = CosyVoice2(snapshot_download("FunAudioLLM/CosyVoice2-0.5B"), load_jit=False, load_trt=False, fp16=False)
    for v, ref in VOICES.items():
        r = wav_of(ref)
        # The prompt text must match the prompt audio, so transcribe a cut that
        # ends on silence rather than the 10s mark mid-word.
        txt = asr.transcribe(r)["text"].strip(); log.append(f"v{v} ref text: {txt}")
        def say(t):
            return torch.cat([j["tts_speech"] for j in m.inference_zero_shot(t, txt, r, stream=False)], 1), m.sample_rate
        run(f"cand_v{v}_F", say)
(out / f"log_{engine}_{shard}.txt").write_text("\n".join(log))
