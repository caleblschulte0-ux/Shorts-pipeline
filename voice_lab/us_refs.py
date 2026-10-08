"""Round 5: the GLOBE accent labels are self-reported and the operator heard
that none of round 4's "Americans" were American. So the label is not
trusted: every young speaker (any label) is run through an accent detector
(CommonAccent ECAPA, MIT) and kept only when it hears "us" with high
confidence. Round 4's picks are scored too, as a check on the detector.
Then the same liveliness score picks the voices."""
import io, json, subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf, librosa, torch

src = Path(sys.argv[1]); out = Path(sys.argv[2]); prev = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
SR = 24000
from speechbrain.inference.classifiers import EncoderClassifier
clf = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir="/tmp/accent")
labels = [clf.hparams.label_encoder.decode_ndim(i) for i in range(16)]
US = labels.index("us")

def decode(b, sr=SR):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sr),
                        "-f", "f32le", "pipe:1"], input=b, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).copy()

def accent(y16):
    with torch.no_grad():
        p = clf.classify_batch(torch.from_numpy(y16).unsqueeze(0))[0][0]
    p = torch.softmax(p, -1) if p.min() < 0 else p
    p = p / p.sum()
    top = int(p.argmax())
    return float(p[US]), labels[top], float(p[top])

check = {}
for ogg in sorted(prev.glob("globe_*.ogg")):
    y, sr = librosa.load(str(ogg), sr=16000)
    check[ogg.stem] = accent(y)
print("round 4 picks, detector says:", json.dumps(check, indent=1))

rows = defaultdict(list)
for f in sorted(src.glob("*.parquet")):
    t = pq.read_table(f, columns=["speaker_id", "age", "gender", "accent", "transcript", "duration", "audio"])
    d = t.to_pydict()
    for i in range(t.num_rows):
        if d["age"][i] not in ("teens", "twenties") or d["duration"][i] < 3.0: continue
        rows[d["speaker_id"][i]].append({"g": d["gender"][i], "age": d["age"][i], "acc": d["accent"][i],
                                         "txt": d["transcript"][i], "dur": d["duration"][i],
                                         "audio": d["audio"][i]["bytes"]})
print("young speakers with >=4 clips:", sum(len(v) >= 4 for v in rows.values()))
feat = []
for spk, cl in rows.items():
    if len(cl) < 4: continue
    cl = sorted(cl, key=lambda c: -c["dur"])[:6]
    y16 = np.concatenate([decode(c["audio"], 16000) for c in cl[:4]])
    pus, top, ptop = accent(y16)
    if pus < 0.85: continue
    st, rate, snr, f0s = [], [], [], []
    for c in cl[:3]:
        y = decode(c["audio"])
        f0, _, _ = librosa.pyin(librosa.resample(y, orig_sr=SR, target_sr=16000), fmin=60, fmax=400, sr=16000)
        f0 = f0[~np.isnan(f0)]
        if len(f0) < 20: continue
        st.append(float(np.std(12 * np.log2(f0 / np.median(f0))))); f0s.append(float(np.median(f0)))
        rate.append(len(c["txt"].split()) / c["dur"])
        db = 20 * np.log10(librosa.feature.rms(y=y)[0] + 1e-6)
        snr.append(float(np.percentile(db, 95) - np.percentile(db, 10)))
    if len(st) < 2: continue
    feat.append({"spk": spk, "g": cl[0]["g"], "age": cl[0]["age"], "acc_label": cl[0]["acc"], "p_us": pus,
                 "pitch_move_st": np.mean(st), "words_s": np.mean(rate), "range_db": np.mean(snr),
                 "f0": float(np.median(f0s)), "clips": cl})
print("detector-American speakers scored:", len(feat))
def z(k):
    v = np.array([f[k] for f in feat]); return (v - v.mean()) / (v.std() + 1e-9)
zs = z("pitch_move_st") + 0.8 * z("words_s") + 0.6 * z("range_db") + 1.0 * z("p_us")
for f, s in zip(feat, zs): f["score"] = float(s)
# gender by pitch as well as label: a "male" at 220 Hz is a mislabel
male = sorted([f for f in feat if str(f["g"]).lower().startswith("m") and f["f0"] < 165 and f["range_db"] > 30], key=lambda f: -f["score"])[:10]
female = sorted([f for f in feat if str(f["g"]).lower().startswith("f") and f["f0"] > 165 and f["range_db"] > 30], key=lambda f: -f["score"])[:4]
meta = {"round4_check": check}
for n, f in enumerate(male + female, 1):
    parts, dur = [], 0.0
    for c in f["clips"]:
        y = decode(c["audio"]); y, _ = librosa.effects.trim(y, top_db=35)
        parts += [y, np.zeros(int(0.2 * SR), np.float32)]; dur += len(y) / SR
        if dur >= 10.5: break
    ref = np.concatenate(parts)[: int(10.0 * SR)]
    name = f"us_{n:02d}"
    sf.write(str(out / f"{name}.wav"), ref, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{name}.wav"), "-af",
                    "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "160k",
                    str(out / f"{name}_real.mp3")], check=True)
    meta[name] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in f.items() if k != "clips"}
    meta[name]["transcripts"] = [c["txt"] for c in f["clips"]]
(out / "us_refs.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
