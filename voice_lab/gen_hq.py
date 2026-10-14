"""Round 12 (operator, 2026-10-14: "it still isn't fucking clear. It needs to
be clearer. Better quality."). Measured cause: every take so far had NOTHING
above ~12 kHz. Chatterbox and CosyVoice speak at 24 kHz, and the lab's own
finish() resampled even Zonos (44.1 kHz) down to 24 kHz. This regenerates the
top takes as lossless wavs at each engine's NATIVE rate, for enhance_hq.py.
  python gen_hq.py ENGINE OUT VOICE[,VOICE...]
"""
import json, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np, soundfile as sf, torch
HERE = Path(__file__).parent
engine, out, voices = sys.argv[1], Path(sys.argv[2]), sys.argv[3].split(",")
out.mkdir(parents=True, exist_ok=True)
ORDER = ["libritts_8108", "libritts_839", "libritts_2428", "libritts_2952", "libritts_5536",
         "vctk_p311", "vctk_p315", "vctk_p334", "vctk_p345", "vctk_p360"]
REF = {str(41 + i): HERE / f"clean2/clean_{s}.flac" for i, s in enumerate(ORDER)}
LINES = json.loads((HERE / "final_stories.json").read_text())["octopus-nine-brains"]
LINES = [" ".join(l.replace("--", ",").replace("—", ",").split()) for l in LINES]
torch.set_num_threads(4); log = []
TAG = {"chatterbox": "C", "zonos": "E", "cosyvoice": "F"}[engine]

def ref_wav(v, sr=24000):
    w = out / f"_ref_{v}_{sr}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(REF[v]), "-ac", "1", "-ar", str(sr), str(w)], check=True)
    return str(w)

def run(v, say):
    name = f"hq_v{v}_{TAG}"; t0 = time.time()
    try:
        parts, rate = [], None
        for i, t in enumerate(LINES):
            torch.manual_seed(1000 + i)
            y, rate = say(t)
            parts += [y.detach().cpu().numpy().reshape(-1), np.zeros(int(0.15 * rate), np.float32)]
        sf.write(str(out / f"{name}_raw.wav"), np.concatenate(parts), rate, subtype="FLOAT")
        log.append(f"{name}: {rate} Hz, {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-600:])
    print(log[-1], flush=True)

if engine == "chatterbox":
    from chatterbox.tts import ChatterboxTTS
    m = ChatterboxTTS.from_pretrained(device="cpu")
    for v in voices:
        m.prepare_conditionals(ref_wav(v), exaggeration=0.5)
        run(v, lambda t: (m.generate(t, exaggeration=0.5, cfg_weight=0.5), m.sr))
elif engine == "zonos":
    sys.path.insert(0, "zonos_src")
    import torchaudio
    from zonos.model import Zonos
    from zonos.conditioning import make_cond_dict
    m = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device="cpu")
    for v in voices:
        y, sr = torchaudio.load(ref_wav(v, 44100)); spk = m.make_speaker_embedding(y, sr)
        def say(t):
            c = m.prepare_conditioning(make_cond_dict(text=t, speaker=spk, language="en-us"))
            return m.autoencoder.decode(m.generate(c))[0], m.autoencoder.sampling_rate
        run(v, say)
else:
    sys.path[:0] = ["CosyVoice", "CosyVoice/third_party/Matcha-TTS"]
    import whisper
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import CosyVoice2
    asr = whisper.load_model("small.en")
    m = CosyVoice2(snapshot_download("FunAudioLLM/CosyVoice2-0.5B"), load_jit=False, load_trt=False, fp16=False)
    for v in voices:
        r = ref_wav(v); txt = asr.transcribe(r)["text"].strip()
        run(v, lambda t: (torch.cat([j["tts_speech"] for j in m.inference_zero_shot(t, txt, r, stream=False)], 1), m.sample_rate))
(out / f"log_{engine}_{voices[0]}.txt").write_text("\n".join(log))
