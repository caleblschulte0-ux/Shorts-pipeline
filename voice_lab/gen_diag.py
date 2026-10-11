"""Round 10 (operator, 2026-10-11, of 14 clean-source clones: "Something is
bad about them all"). The common factor is no longer the recording, so this
round isolates the PROCESS on two clean voices (41 = LibriTTS-R 8108,
46 = VCTK p311), one story:

  chatterbox  B  production settings, no 12% speed-up
              C  calm settings (exaggeration 0.5, cfg 0.5), no speed-up
              D  calm settings, story voiced in two long takes, not per line
  zonos       E  a different engine (Zyphra Zonos v0.1, Apache-2.0)
  cosyvoice   F  a different engine (CosyVoice2 0.5B, Apache-2.0)

(A, the production render, already exists from round 9.)
  python gen_diag.py ENGINE OUT
"""
import json, subprocess, sys, time, traceback
from pathlib import Path
import torch, torchaudio
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from finish import finish
engine, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
REFS = {"41": HERE / "clean2/clean_libritts_8108.flac", "46": HERE / "clean2/clean_vctk_p311.flac"}
LINES = json.loads((HERE / "final_stories.json").read_text())["octopus-nine-brains"]
LINES = [" ".join(l.replace("--", ",").replace("—", ",").split()) for l in LINES]
torch.set_num_threads(4); log = []

def wav_of(ref):  # 24 kHz mono wav copy of the flac ref (every engine reads wav)
    w = out / f"_ref_{ref.stem}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ref), "-ac", "1", "-ar", "24000", str(w)], check=True)
    return w

def run(name, takes, say, tempo=1.0):
    t0 = time.time()
    try:
        wavs = []
        for i, t in enumerate(takes):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; y, sr = say(t); torchaudio.save(str(w), y.cpu(), sr); wavs.append(w)
        finish(wavs, out / f"{name}.mp3", tempo)
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-600:])
    print(log[-1], flush=True)

if engine == "chatterbox":
    from chatterbox.tts import ChatterboxTTS
    m = ChatterboxTTS.from_pretrained(device="cpu")
    two = [" ".join(LINES[:2]), " ".join(LINES[2:])]
    for v, ref in REFS.items():
        r = str(wav_of(ref))
        m.prepare_conditionals(r, exaggeration=0.75)
        run(f"diag_v{v}_B", LINES, lambda t: (m.generate(t, exaggeration=0.75, cfg_weight=0.35), m.sr))
        m.prepare_conditionals(r, exaggeration=0.5)
        run(f"diag_v{v}_C", LINES, lambda t: (m.generate(t, exaggeration=0.5, cfg_weight=0.5), m.sr))
        run(f"diag_v{v}_D", two, lambda t: (m.generate(t, exaggeration=0.5, cfg_weight=0.5), m.sr))
elif engine == "zonos":
    from zonos.model import Zonos
    from zonos.conditioning import make_cond_dict
    m = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device="cpu")
    for v, ref in REFS.items():
        y, sr = torchaudio.load(str(wav_of(ref)))
        spk = m.make_speaker_embedding(y, sr)
        def say(t):
            c = m.prepare_conditioning(make_cond_dict(text=t, speaker=spk, language="en-us"))
            return m.autoencoder.decode(m.generate(c))[0], m.autoencoder.sampling_rate
        run(f"diag_v{v}_E", LINES, say)
else:
    sys.path[:0] = ["CosyVoice", "CosyVoice/third_party/Matcha-TTS"]
    import whisper
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav
    asr = whisper.load_model("base.en")
    m = CosyVoice2(snapshot_download("FunAudioLLM/CosyVoice2-0.5B"), load_jit=False, load_trt=False, fp16=False)
    for v, ref in REFS.items():
        r = str(wav_of(ref)); txt = asr.transcribe(r)["text"].strip(); log.append(f"v{v} ref text: {txt}")
        p = load_wav(r, 16000)
        def say(t):
            return torch.cat([j["tts_speech"] for j in m.inference_zero_shot(t, txt, p, stream=False)], 1), m.sample_rate
        run(f"diag_v{v}_F", LINES, say)
(out / f"log_{engine}.txt").write_text("\n".join(log))
