"""Round 4: find YOUNG, lively narrators. GLOBE v2 (CC0: Common Voice
recordings, enhanced, with the speaker's own age/gender/accent labels).
Keep US-accented speakers who said they are in their teens or twenties,
score each on how much their pitch moves (expressive, not monotone), how
fast they talk and how clean the recording is, and cut a 10s reference
for the best ones. Prints the label distribution so the choice is visible."""
import io, json, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf, librosa

src = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
SR = 24000

def decode(b):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "pipe:1"], input=b, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32)

rows = defaultdict(list); ages, accents = Counter(), Counter()
for f in sorted(src.glob("*.parquet")):
    t = pq.read_table(f, columns=["speaker_id", "age", "gender", "accent", "transcript", "duration", "audio"])
    d = t.to_pydict()
    for i in range(t.num_rows):
        ages[d["age"][i]] += 1; accents[d["accent"][i]] += 1
        if d["age"][i] not in ("teens", "twenties"): continue
        if "united states" not in str(d["accent"][i]).lower(): continue
        if d["duration"][i] < 3.0: continue
        rows[d["speaker_id"][i]].append({"g": d["gender"][i], "age": d["age"][i], "acc": d["accent"][i],
                                         "txt": d["transcript"][i], "dur": d["duration"][i],
                                         "audio": d["audio"][i]["bytes"]})
print("ages", ages.most_common()); print("accents", accents.most_common(15))
print("young US speakers with >=4 clips:", sum(len(v) >= 4 for v in rows.values()))

feat = []
for spk, cl in rows.items():
    if len(cl) < 4: continue
    cl = sorted(cl, key=lambda c: -c["dur"])[:6]
    st, rate, snr = [], [], []
    for c in cl[:3]:
        y = decode(c["audio"])
        f0, _, _ = librosa.pyin(librosa.resample(y, orig_sr=SR, target_sr=16000), fmin=60, fmax=400, sr=16000)
        f0 = f0[~np.isnan(f0)]
        if len(f0) < 20: continue
        s = 12 * np.log2(f0 / np.median(f0)); st.append(float(np.std(s)))
        rate.append(len(c["txt"].split()) / c["dur"])
        r = librosa.feature.rms(y=y)[0] + 1e-6; db = 20 * np.log10(r)
        snr.append(float(np.percentile(db, 95) - np.percentile(db, 10)))
        c["f0"] = float(np.median(f0))
    if len(st) < 2: continue
    feat.append({"spk": spk, "g": cl[0]["g"], "age": cl[0]["age"], "acc": cl[0]["acc"],
                 "pitch_move_st": np.mean(st), "words_s": np.mean(rate), "range_db": np.mean(snr),
                 "f0": float(np.median([c["f0"] for c in cl if "f0" in c])), "clips": cl})
print("scored", len(feat))
def z(k):
    v = np.array([f[k] for f in feat]); return (v - v.mean()) / (v.std() + 1e-9)
zs = z("pitch_move_st") + 0.8 * z("words_s") + 0.6 * z("range_db")
for f, s in zip(feat, zs): f["score"] = float(s)
male = sorted([f for f in feat if str(f["g"]).lower().startswith("m") and f["range_db"] > 30], key=lambda f: -f["score"])[:8]
female = sorted([f for f in feat if str(f["g"]).lower().startswith("f") and f["range_db"] > 30], key=lambda f: -f["score"])[:4]
meta = {}
for n, f in enumerate(male + female, 1):
    parts, dur = [], 0.0
    for c in f["clips"]:
        y = decode(c["audio"]); y, _ = librosa.effects.trim(y, top_db=35)
        parts += [y, np.zeros(int(0.2 * SR), np.float32)]; dur += len(y) / SR
        if dur >= 10.5: break
    ref = np.concatenate(parts)[: int(10.0 * SR)]
    name = f"globe_{n:02d}"
    sf.write(str(out / f"{name}.wav"), ref, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{name}.wav"), "-af",
                    "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "160k",
                    str(out / f"{name}_real.mp3")], check=True)
    meta[name] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in f.items() if k != "clips"}
    meta[name]["transcripts"] = [c["txt"] for c in f["clips"]]
(out / "young_refs.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
