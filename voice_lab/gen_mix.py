"""Round 7: what the operator asked for after round 6.
  tune11-*   Voice 11 (GLOBE S_008118) tuned like Voice 24: three cuts x energy
  blend-*    in between 11 and 24, two ways:
               clip mix  the 10s the model hears is 5s of one, then 5s of the other
               voice mix the voice-print is averaged 50/50 (the delivery comes from
                         whichever clip leads)
  turbo-*    Turbo was "a little bit too fast": every Turbo render is finished at
             the channel's tempo AND slower (1.05, 1.00)
  styled-*   the same lines with punctuation doing the directing (... pauses, a
             capitalised word, ! and ?), against the plain lines"""
import json, subprocess, sys, time, traceback
from pathlib import Path
import torch, torchaudio, torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).parent))
from finish import finish
HERE = Path(__file__).parent
PLAIN = json.loads((HERE / "lines.json").read_text())
STYLED = json.loads((HERE / "styled_lines.json").read_text())
refs, out, which = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(4); log = []
V24, V11 = str(HERE / "tune" / "tune_A.ogg"), str(HERE / "young" / "globe_06.ogg")

def wav(src, dst, start=0.0, dur=None):
    a = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", src]
    if dur: a += ["-t", str(dur)]
    subprocess.run(a + ["-ac", "1", "-ar", "24000", dst], check=True); return dst

def mix_clip(a, b, name):
    p = [wav(a, f"/tmp/{name}_a.wav", 0, 5), wav(b, f"/tmp/{name}_b.wav", 0, 5)]
    lst = Path(f"/tmp/{name}.txt"); lst.write_text("".join(f"file '{x}'\n" for x in p))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ac", "1", "-ar", "24000", f"/tmp/{name}.wav"], check=True)
    return f"/tmp/{name}.wav"

def render(m, name, kw, L=PLAIN, tempos=None):
    t0 = time.time()
    try:
        wavs = []
        for i, t in enumerate(L["lines"]):
            torch.manual_seed(1000 + i)
            w = out / f"_{name}_{i}.wav"; torchaudio.save(str(w), m.generate(t, **kw).cpu(), m.sr); wavs.append(w)
        for tp in (tempos or [L["tempo"]]):
            finish(wavs, out / (f"{name}.mp3" if tp == L["tempo"] else f"{name}_t{int(tp*100)}.mp3"), tp)
        for w in wavs: w.unlink()
        log.append(f"{name}: {time.time()-t0:.0f}s")
    except Exception:
        log.append(name + " failed: " + traceback.format_exc()[-500:])

def blend(m, a, b, ex):
    """Voice-print 50/50: prompt (delivery) from a, both speaker embeddings averaged."""
    m.prepare_conditionals(b, exaggeration=ex); cb = m.conds
    eb_t3, eb_gen = cb.t3.speaker_emb.clone(), cb.gen["embedding"].clone()
    m.prepare_conditionals(a, exaggeration=ex)
    m.conds.t3.speaker_emb = F.normalize(0.5 * m.conds.t3.speaker_emb + 0.5 * eb_t3, dim=-1)
    m.conds.gen["embedding"] = 0.5 * m.conds.gen["embedding"] + 0.5 * eb_gen

FULL = lambda ex: {"exaggeration": ex, "cfg_weight": 0.35 if ex < 1 else 0.3}
if which.startswith("turbo"):
    from chatterbox.tts_turbo import ChatterboxTurboTTS as M
else:
    from chatterbox.tts import ChatterboxTTS as M
m = M.from_pretrained(device="cpu")
TT = [1.12, 1.05, 1.0]
if which in ("tune11-e75", "tune11-e100"):
    ex = 0.75 if which.endswith("e75") else 1.0
    for cut, ref in [("A", V11), ("B", str(refs / "v11_B.wav")), ("C", str(refs / "v11_C.wav"))]:
        m.prepare_conditionals(ref, exaggeration=ex); render(m, f"v11_full_{cut}_e{int(ex*100)}", FULL(ex))
elif which == "turbo-tune":
    for cut, ref in [("A", V11), ("B", str(refs / "v11_B.wav")), ("C", str(refs / "v11_C.wav")), ("24A", V24)]:
        m.prepare_conditionals(ref); render(m, f"turbo_{'v24_A' if cut == '24A' else 'v11_' + cut}", {}, tempos=TT)
elif which == "blend-full":
    m.prepare_conditionals(mix_clip(V11, V24, "m1124"), exaggeration=0.75); render(m, "blend_full_clip_11then24", FULL(0.75))
    m.prepare_conditionals(mix_clip(V24, V11, "m2411"), exaggeration=0.75); render(m, "blend_full_clip_24then11", FULL(0.75))
    blend(m, V24, V11, 0.75); render(m, "blend_full_print_24delivery", FULL(0.75))
    blend(m, V11, V24, 0.75); render(m, "blend_full_print_11delivery", FULL(0.75))
elif which == "turbo-blend":
    m.prepare_conditionals(mix_clip(V11, V24, "m1124")); render(m, "blend_turbo_clip_11then24", {}, tempos=TT)
    m.prepare_conditionals(mix_clip(V24, V11, "m2411")); render(m, "blend_turbo_clip_24then11", {}, tempos=TT)
elif which == "styled-full":
    m.prepare_conditionals(V24, exaggeration=0.75); render(m, "styled_full_v24", FULL(0.75), L=STYLED)
    m.prepare_conditionals(V11, exaggeration=0.75); render(m, "styled_full_v11", FULL(0.75), L=STYLED)
elif which == "turbo-styled":
    m.prepare_conditionals(V24); render(m, "styled_turbo_v24", {}, L=STYLED, tempos=[1.05])
    m.prepare_conditionals(V11); render(m, "styled_turbo_v11", {}, L=STYLED, tempos=[1.05])
(out / f"log_{which}.txt").write_text("\n".join(log)); print("\n".join(log))
