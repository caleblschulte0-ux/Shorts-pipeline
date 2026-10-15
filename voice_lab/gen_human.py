"""Round 13 (operator, 2026-10-15, of the round-12 takes: "none of those talk
like a normal person, and they all sound very robotic"). Two changes at once,
kept separable:

  engines trained on real CONVERSATION, not audiobooks:
    orpheus  Canopy Labs Orpheus 3B (Apache-2.0, Llama 3.2 base) with its own
             real single-speaker voices leo / dan / zac, run on CPU through
             llama.cpp, decoded by SNAC (MIT)
    dia      Nari Labs Dia 1.6B (Apache-2.0), cloning a studio voice
    cosyvoice the round-12 best (control: same engine, new script)
  a script written the way a person TELLS it (spoken_lines.json) beside the
  written lines the channel posted.

Writes hq_<engine>_<voice>_<script>_raw.wav for enhance_hq.py.
  python gen_human.py ENGINE OUT VOICE SCRIPT[,SCRIPT]
"""
import json, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np, soundfile as sf
HERE = Path(__file__).parent
engine, out, voice, scripts = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4].split(",")
out.mkdir(parents=True, exist_ok=True); log = []
S = json.loads((HERE / "spoken_lines.json").read_text())
ORDER = ["libritts_8108", "libritts_839", "libritts_2428", "libritts_2952", "libritts_5536",
         "vctk_p311", "vctk_p315", "vctk_p334", "vctk_p345", "vctk_p360"]
REF = {str(41 + i): HERE / f"clean2/clean_{s}.flac" for i, s in enumerate(ORDER)}

def ref_wav(v, sr):
    w = out / f"_ref_{v}_{sr}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(REF[v]), "-ac", "1", "-ar", str(sr), str(w)], check=True)
    return str(w)

def run(script, say):
    name = f"hq_{engine}_{voice}_{script}"; t0 = time.time()
    try:
        parts, rate = [], None
        for i, t in enumerate(S[script]):
            y, rate = say(t, i)
            parts += [np.asarray(y, np.float32).reshape(-1), np.zeros(int(0.18 * rate), np.float32)]
        sf.write(str(out / f"{name}_raw.wav"), np.concatenate(parts), rate, subtype="FLOAT")
        log.append(f"{name}: {rate} Hz, {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-800:])
    print(log[-1], flush=True)

if engine == "orpheus":
    import torch
    from huggingface_hub import hf_hub_download, list_repo_files
    from llama_cpp import Llama
    from snac import SNAC
    path = None
    for repo in ["isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF", "lex-au/Orpheus-3b-FT-Q8_0.gguf",
                 "unsloth/orpheus-3b-0.1-ft-GGUF"]:
        try:
            fs = [f for f in list_repo_files(repo) if f.endswith(".gguf")]
            pick = next((f for f in fs if "Q8_0" in f), None) or next((f for f in fs if "Q4_K_M" in f), None) or fs[0]
            path = hf_hub_download(repo, pick); log.append(f"model {repo}/{pick}"); break
        except Exception as e:
            log.append(f"no {repo}: {e}")
    llm = Llama(model_path=path, n_ctx=8192, n_threads=4, verbose=False)
    snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval()
    def say(t, i):
        ids = [128259] + llm.tokenize(f"{voice}: {t}".encode(), add_bos=True, special=False) + [128009, 128260, 128261, 128257]
        codes = []
        for tok in llm.generate(ids, temp=0.6, top_p=0.95, repeat_penalty=1.1, reset=True):
            if tok in (128258, 128009) or len(codes) > 7 * 12 * 40:
                break
            if tok >= 128266:
                codes.append(tok - 128266 - (len(codes) % 7) * 4096)
        n = len(codes) // 7 * 7; c = np.array(codes[:n]).reshape(-1, 7)
        c = c[((c >= 0) & (c < 4096)).all(1)]
        l1 = torch.tensor(c[:, 0])[None]; l2 = torch.tensor(c[:, [1, 4]].reshape(-1))[None]
        l3 = torch.tensor(c[:, [2, 3, 5, 6]].reshape(-1))[None]
        with torch.no_grad():
            return snac.decode([l1, l2, l3]).squeeze().numpy(), 24000
    for s in scripts: run(s, say)
elif engine == "dia":
    import torch, whisper
    from transformers import AutoProcessor, DiaForConditionalGeneration
    torch.set_num_threads(4)
    proc = AutoProcessor.from_pretrained("nari-labs/Dia-1.6B-0626")
    m = DiaForConditionalGeneration.from_pretrained("nari-labs/Dia-1.6B-0626").eval()
    r = ref_wav(voice, 44100); txt = whisper.load_model("small.en").transcribe(r)["text"].strip()
    y_ref, _ = sf.read(r, dtype="float32")
    def say(t, i):
        torch.manual_seed(1000 + i)
        inp = proc(text=[f"[S1] {txt} [S1] {t}"], audio=[y_ref], padding=True, return_tensors="pt")
        plen = proc.get_audio_prompt_len(inp["decoder_attention_mask"])
        with torch.no_grad():
            o = m.generate(**inp, max_new_tokens=86 * 20, guidance_scale=3.0, temperature=1.8, top_p=0.9, top_k=45)
        a = proc.batch_decode(o, audio_prompt_len=plen)[0]
        return np.asarray(a.cpu() if hasattr(a, "cpu") else a, np.float32), 44100
    for s in scripts: run(s, say)
else:
    import torch, whisper
    sys.path[:0] = ["CosyVoice", "CosyVoice/third_party/Matcha-TTS"]
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import CosyVoice2
    torch.set_num_threads(4)
    m = CosyVoice2(snapshot_download("FunAudioLLM/CosyVoice2-0.5B"), load_jit=False, load_trt=False, fp16=False)
    r = ref_wav(voice, 24000); txt = whisper.load_model("small.en").transcribe(r)["text"].strip()
    def say(t, i):
        torch.manual_seed(1000 + i)
        return torch.cat([j["tts_speech"] for j in m.inference_zero_shot(t, txt, r, stream=False)], 1).numpy(), m.sample_rate
    for s in scripts: run(s, say)
(out / f"log_{engine}_{voice}.txt").write_text("\n".join(log))
