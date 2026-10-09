"""Round 8: find REAL people who sound like the operator's two favourites,
Voice 24 (GLOBE S_019178) and Voice 11 (S_008118). No blending: every
candidate is one real speaker.

A speaker-recognition model (SpeechBrain ECAPA, VoxCeleb, Apache-2.0) turns
each voice into a voice-print; candidates are ranked by how close their
print is to each favourite, the closest are checked by the accent detector
(must be >= 0.98 American), and a 10s reference is cut for each keeper."""
import json, subprocess, sys
from collections import defaultdict
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf, librosa, torch
import torch.nn.functional as F
from speechbrain.inference.classifiers import EncoderClassifier
from speechbrain.inference.speaker import EncoderClassifier as SpkEnc

src, out, here = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True); SR = 24000
FAV = {"24": "S_019178", "11": "S_008118"}
spk = SpkEnc.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="/tmp/spk")
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir="/tmp/accent")
US = [acc.hparams.label_encoder.decode_ndim(i) for i in range(16)].index("us")

def decode(b, sr):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sr),
                        "-f", "f32le", "pipe:1"], input=b, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).copy()

def emb(ys):
    with torch.no_grad():
        e = [spk.encode_batch(torch.from_numpy(y).unsqueeze(0)).squeeze() for y in ys]
    return F.normalize(torch.stack(e).mean(0), dim=-1)

def p_us(y16):
    with torch.no_grad():
        p = torch.softmax(30.0 * acc.classify_batch(torch.from_numpy(y16).unsqueeze(0))[0][0], -1)
    return float(p[US])

rows = defaultdict(list)
for f in sorted(src.glob("*.parquet")):
    t = pq.read_table(f, columns=["speaker_id", "age", "gender", "transcript", "duration", "audio"])
    d = t.to_pydict()
    for i in range(t.num_rows):
        s = d["speaker_id"][i]
        if s not in FAV.values():
            if d["age"][i] not in ("teens", "twenties") or not str(d["gender"][i]).lower().startswith("m"): continue
        if d["duration"][i] < 3.0: continue
        rows[s].append({"txt": d["transcript"][i], "dur": d["duration"][i], "audio": d["audio"][i]["bytes"],
                        "age": d["age"][i]})
    for k in rows:  # keep RAM bounded: only the 8 longest clips per speaker matter
        if len(rows[k]) > 8: rows[k] = sorted(rows[k], key=lambda c: -c["dur"])[:8]
    print(f.name, "speakers so far", len(rows), flush=True)

def clips16(s, n=4):
    cl = sorted(rows[s], key=lambda c: -c["dur"])[:n]
    return [decode(c["audio"], 16000) for c in cl]

target = {k: emb(clips16(s, 8)) for k, s in FAV.items()}
print("favourites' own similarity:", float(target["24"] @ target["11"]))
sim = {}
for s, cl in rows.items():
    if s in FAV.values() or len(cl) < 4: continue
    e = emb(clips16(s, 3))
    sim[s] = {"24": float(e @ target["24"]), "11": float(e @ target["11"])}
print("candidates scored:", len(sim))
picked, meta = [], {}
def take(key, n, why):
    order = sorted(sim, key=key, reverse=True)
    got = 0
    for s in order:
        if got >= n: break
        if s in picked: continue
        pu = p_us(np.concatenate(clips16(s, 4)))
        if pu < 0.98: continue
        picked.append(s); got += 1
        meta[s] = {"why": why, "sim_24": round(sim[s]["24"], 3), "sim_11": round(sim[s]["11"], 3),
                   "p_us": round(pu, 3), "age": rows[s][0]["age"], "clips": len(rows[s])}
take(lambda s: sim[s]["24"], 4, "sounds like Voice 24")
take(lambda s: sim[s]["11"], 4, "sounds like Voice 11")
take(lambda s: min(sim[s]["24"], sim[s]["11"]), 2, "sounds like both")
for n, s in enumerate(picked, 1):
    parts, dur = [], 0.0
    for c in sorted(rows[s], key=lambda c: -c["dur"])[:6]:
        y = decode(c["audio"], SR); y, _ = librosa.effects.trim(y, top_db=35)
        parts += [y, np.zeros(int(0.2 * SR), np.float32)]; dur += len(y) / SR
        if dur >= 10.5: break
    name = f"sim_{n:02d}"
    sf.write(str(out / f"{name}.wav"), np.concatenate(parts)[: int(10 * SR)], SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{name}.wav"), "-af",
                    "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "160k",
                    str(out / f"{name}_real.mp3")], check=True)
    meta[s]["name"] = name
(out / "sim_refs.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
