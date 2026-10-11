"""Round 9 (operator, 2026-10-11: "you really need to be focusing on getting a
very clear and crisp original audio"). Chatterbox copies the microphone and
the room along with the voice, and every GLOBE voice so far was a Common
Voice volunteer on a phone or laptop mic. This round only keeps speakers
whose OWN recordings are clean.

Clean is MEASURED: torchaudio's SQUIM model estimates PESQ / STOI / SI-SDR
from the audio alone (no reference needed), plus how high the spectrum
reaches. Then the same filters as before: male, American (accent detector
>= 0.95), and, among the clean ones, closest to Voices 11 and 24, the two
the operator liked.

  python clean_refs.py vctk|libritts|globe SRC OUT HERE
"""
import json, subprocess, sys
from collections import defaultdict
from pathlib import Path
import numpy as np, soundfile as sf, librosa, torch
import torch.nn.functional as F
from torchaudio.pipelines import SQUIM_OBJECTIVE
from speechbrain.inference.classifiers import EncoderClassifier
from speechbrain.inference.speaker import EncoderClassifier as SpkEnc

kind, src, out, here = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
SR = 48000
FINALISTS = {"S_008118": "11", "S_019178": "24", "S_019135": "34", "S_001818": "38", "S_007123": "39"}
TAKE = {"vctk": 5, "libritts": 5, "globe": 4}[kind]

spk = SpkEnc.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="/tmp/spk")
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir="/tmp/accent")
US = [acc.hparams.label_encoder.decode_ndim(i) for i in range(16)].index("us")
squim = SQUIM_OBJECTIVE.get_model().eval()


def decode(b, sr):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sr),
                        "-f", "f32le", "pipe:1"], input=b, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def to16(y, sr):
    return librosa.resample(y, orig_sr=sr, target_sr=16000) if sr != 16000 else y


def emb(ys16):
    with torch.no_grad():
        e = [spk.encode_batch(torch.from_numpy(y).unsqueeze(0)).squeeze() for y in ys16]
    return F.normalize(torch.stack(e).mean(0), dim=-1)


def p_us(y16):
    with torch.no_grad():
        p = torch.softmax(30.0 * acc.classify_batch(torch.from_numpy(y16).unsqueeze(0))[0][0], -1)
    return float(p[US])


def quality(clips):
    """clips: [(y, sr)]. SQUIM per clip (averaged), and the 99.5% energy
    bandwidth of the native-rate audio (a phone mic tops out near 4-8 kHz)."""
    s, b = [], []
    for y, sr in clips:
        y16 = to16(y, sr)[: 16000 * 10]
        with torch.no_grad():
            stoi, pesq, sisdr = squim(torch.from_numpy(y16).unsqueeze(0))
        s.append((float(stoi), float(pesq), float(sisdr)))
        P = np.abs(np.fft.rfft(y)) ** 2
        c = np.cumsum(P) / max(P.sum(), 1e-12)
        b.append(float(np.fft.rfftfreq(len(y), 1 / sr)[np.searchsorted(c, 0.995)]))
    a = np.mean(s, 0)
    return {"stoi": round(a[0], 3), "pesq": round(a[1], 2), "si_sdr": round(a[2], 1),
            "bandwidth_khz": round(float(np.median(b)) / 1000, 1)}


def male(y16):
    f0 = librosa.yin(y16, fmin=60, fmax=400, sr=16000)
    return float(np.median(f0)) < 165


# ---- loaders: speaker -> [(y, sr, info)] longest first, at most 8 ----------
speakers, info = defaultdict(list), {}
if kind == "vctk":
    for line in (src / "speaker-info.txt").read_text().splitlines()[1:]:
        f = line.split()
        if len(f) < 4: continue
        sid = f[0] if f[0].startswith("p") else "p" + f[0]
        if f[2] != "M" or f[3] != "American" or not f[1].isdigit() or int(f[1]) > 32: continue
        info[sid] = {"age": int(f[1]), "region": " ".join(f[4:])}
        best = None
        for mic in ("mic2", "mic1"):
            d = next(src.rglob(f"wav48_silence_trimmed/{sid}"), None)
            if d is None: break
            fs = sorted(d.glob(f"*_{mic}.flac"),
                        key=lambda p: -sf.info(str(p)).duration)[:8]
            if not fs: continue
            cl = [(sf.read(str(p), dtype="float32")[0], 48000) for p in fs]
            q = quality(cl[:3])["pesq"]
            if best is None or q > best[0]: best = (q, cl, mic)
        if best:
            speakers[sid] = best[1]; info[sid]["mic"] = best[2]
elif kind == "libritts":
    g = {}
    for t in src.rglob("speakers.tsv"):
        for line in t.read_text().splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 2: g[f[0].strip()] = f[1].strip()
    print("gender labels:", len(g))
    by = defaultdict(list)
    for w in src.rglob("*.wav"):
        by[w.name.split("_")[0]].append(w)
    for sid, ws in by.items():
        if g and g.get(sid) != "M": continue
        ws = sorted(ws, key=lambda p: -sf.info(str(p)).duration)[:8]
        if sf.info(str(ws[0])).duration < 4: continue
        speakers[sid] = [(sf.read(str(p), dtype="float32")[0], 24000) for p in ws]
        info[sid] = {"subset": ws[0].parts[-4]}
else:
    import pyarrow.parquet as pq
    for f in sorted(src.glob("*.parquet")):
        t = pq.read_table(f, columns=["speaker_id", "age", "gender", "duration", "audio"])
        d = t.to_pydict()
        for i in range(t.num_rows):
            s = d["speaker_id"][i]
            if s not in FINALISTS:
                if d["age"][i] not in ("teens", "twenties") or not str(d["gender"][i]).lower().startswith("m"):
                    continue
            if d["duration"][i] < 3.0: continue
            speakers[s].append((d["audio"][i]["bytes"], d["duration"][i]))
            info.setdefault(s, {"age": d["age"][i]})
        for k in speakers:
            if len(speakers[k]) > 8: speakers[k] = sorted(speakers[k], key=lambda c: -c[1])[:8]
        print(f.name, len(speakers), flush=True)
    for s in list(speakers):
        speakers[s] = [(decode(b, SR), SR) for b, _ in sorted(speakers[s], key=lambda c: -c[1])]

print(kind, "candidates:", len(speakers), flush=True)

# ---- the favourites' voice-prints (from the refs the operator heard) ------
def load_ref(p):
    y = decode(Path(p).read_bytes(), 16000)
    return [y[i:i + 16000 * 3] for i in range(0, len(y) - 16000 * 3 + 1, 16000 * 3)] or [y]
fav = {"11": emb(load_ref(here / "young/globe_06.ogg")), "24": emb(load_ref(here / "tune/tune_A.ogg"))}

rows = {}
for s, cl in speakers.items():
    if len(cl) < 3: continue
    c16 = [to16(y, sr) for y, sr in cl[:4]]
    whole = np.concatenate(c16)
    r = dict(info.get(s, {}), **quality(cl[:3]))
    r["finalist"] = FINALISTS.get(s)
    if not r["finalist"] and not male(whole): continue
    e = emb(c16[:3])
    r["sim_11"], r["sim_24"] = round(float(e @ fav["11"]), 3), round(float(e @ fav["24"]), 3)
    rows[s] = r
print("scored:", len(rows), flush=True)

# The finalists' source audio, measured the same way: is the hypothesis right?
diag = {r["finalist"]: dict(r, speaker=s) for s, r in rows.items() if r.get("finalist")}

pool = [s for s, r in rows.items() if not r.get("finalist")]
pool.sort(key=lambda s: -(rows[s]["pesq"] + 0.05 * rows[s]["si_sdr"]))
clean = pool[: max(TAKE * 3, len(pool) // 4)] if kind != "vctk" else pool
clean.sort(key=lambda s: -max(rows[s]["sim_11"], rows[s]["sim_24"]))
picked = []
for s in clean:
    if len(picked) >= TAKE: break
    if rows[s]["pesq"] < 3.0: continue
    pu = p_us(np.concatenate([to16(y, sr) for y, sr in speakers[s][:4]]))
    rows[s]["p_us"] = round(pu, 3)
    if pu < 0.95 and kind != "vctk": continue   # VCTK's accent is the speaker's own word
    picked.append(s)

meta = {}
for s in picked:
    parts, dur = [], 0.0
    for y, sr in speakers[s]:
        y = librosa.resample(y, orig_sr=sr, target_sr=SR) if sr != SR else y
        y, _ = librosa.effects.trim(y, top_db=35)
        parts += [y, np.zeros(int(0.25 * SR), np.float32)]; dur += len(y) / SR
        if dur >= 10.5: break
    y = np.concatenate(parts)[: int(10 * SR)]
    y = 0.89 * y / max(np.abs(y).max(), 1e-6)
    name = f"clean_{kind}_{s}"
    sf.write(str(out / f"{name}.wav"), y, SR, subtype="PCM_24")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{name}.wav"), "-af",
                    "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "192k",
                    str(out / f"{name}_real.mp3")], check=True)
    meta[name] = dict(rows[s], speaker=s, source=kind)
(out / f"clean_{kind}.json").write_text(json.dumps({"picked": meta, "finalists": diag,
                                                     "candidates": len(rows)}, indent=1))
print(json.dumps({"picked": meta, "finalists": diag}, indent=1))
