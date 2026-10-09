"""Cut three references for one GLOBE speaker (Voice 24 = S_019178, Voice 11 = S_008118):
gather EVERY clip of that speaker in the downloaded shards and cut three
different 10s references, because Chatterbox copies the delivery of the
exact 10 seconds it hears.
  A: the round-5 cut (six longest clips, in that order)
  B: the most expressive clips (pitch moves most)
  C: the fastest-talking clips"""
import json, subprocess, sys
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf, librosa
src, out, spk = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
PFX = sys.argv[4] if len(sys.argv) > 4 else "tune"
out.mkdir(parents=True, exist_ok=True); SR = 24000

def decode(b):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "pipe:1"], input=b, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).copy()

clips = []
for f in sorted(src.glob("*.parquet")):
    t = pq.read_table(f, columns=["speaker_id", "transcript", "duration", "audio"], filters=[("speaker_id", "=", spk)])
    d = t.to_pydict()
    for i in range(t.num_rows):
        y = decode(d["audio"][i]["bytes"]); y, _ = librosa.effects.trim(y, top_db=35)
        f0, _, _ = librosa.pyin(librosa.resample(y, orig_sr=SR, target_sr=16000), fmin=60, fmax=300, sr=16000)
        f0 = f0[~np.isnan(f0)]
        move = float(np.std(12 * np.log2(f0 / np.median(f0)))) if len(f0) > 20 else 0.0
        clips.append({"txt": d["transcript"][i], "dur": d["duration"][i], "y": y, "move": move,
                      "wps": len(d["transcript"][i].split()) / d["duration"][i]})
print(spk, "clips found:", len(clips))

def cut(order, name):
    parts, dur, used = [], 0.0, []
    for c in order:
        parts += [c["y"], np.zeros(int(0.2 * SR), np.float32)]; dur += len(c["y"]) / SR; used.append(c["txt"])
        if dur >= 10.5: break
    sf.write(str(out / f"{PFX}_{name}.wav"), np.concatenate(parts)[: int(10 * SR)], SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{PFX}_{name}.wav"), "-af",
                    "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100", "-b:a", "160k",
                    str(out / f"{PFX}_{name}_real.mp3")], check=True)
    return used

meta = {"speaker": spk, "clips": len(clips),
        "A": cut(sorted([c for c in clips if c["dur"] >= 3], key=lambda c: -c["dur"])[:6], "A"),
        "B": cut(sorted(clips, key=lambda c: -c["move"]), "B"),
        "C": cut(sorted(clips, key=lambda c: -c["wps"]), "C")}
(out / f"{PFX}_refs.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
