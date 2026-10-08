"""Pick human reference voices from LibriTTS-R dev-clean (CC BY 4.0: a corpus
recorded for speech research and restored for TTS). For each chosen speaker:
a ~12s reference clip for cloning, and a different held-out clip used as a
REAL-HUMAN control for the listener test."""
import json, sys, subprocess
from pathlib import Path
import numpy as np, soundfile as sf, librosa

root = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
spk = {}
for w in root.rglob("*.wav"):
    spk.setdefault(w.parts[-3], []).append(w)
rows = []
for s, ws in spk.items():
    ws = sorted(ws, key=lambda p: -p.stat().st_size)[:12]
    y, sr = sf.read(str(ws[0]))
    f0, _, _ = librosa.pyin(librosa.resample(y, orig_sr=sr, target_sr=16000), fmin=60, fmax=350, sr=16000)
    f0 = f0[~np.isnan(f0)]
    if not len(f0): continue
    rows.append((s, float(np.median(f0)), ws, sr))
male = sorted([r for r in rows if r[1] < 150], key=lambda r: -sum(w.stat().st_size for w in r[2]))[:4]
female = sorted([r for r in rows if r[1] > 175], key=lambda r: -sum(w.stat().st_size for w in r[2]))[:1]
meta = {}
for s, f0, ws, sr in male + female:
    parts, dur, i = [], 0.0, 0
    while dur < 12 and i < len(ws) - 1:
        y, sr = sf.read(str(ws[i])); parts.append(y); dur += len(y) / sr; i += 1
    ref = np.concatenate([np.concatenate([p, np.zeros(int(0.25 * sr))]) for p in parts])
    sf.write(str(out / f"ref_{s}.wav"), ref, sr)
    ctl, _ = sf.read(str(ws[-1]))
    sf.write(str(out / f"_control_{s}.wav"), ctl, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"_control_{s}.wav"),
                    "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "160k",
                    str(out / f"human_control_{s}.mp3")], check=True)
    (out / f"_control_{s}.wav").unlink()
    meta[s] = {"median_f0_hz": round(f0), "ref_seconds": round(dur, 1),
               "gender_guess": "male" if f0 < 150 else "female"}
(out / "refs.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
