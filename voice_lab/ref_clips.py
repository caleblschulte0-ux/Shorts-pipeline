"""Cut each lab speaker's reference to the 10s Chatterbox actually reads
(DEC_COND_LEN), as a small Opus clip the pipeline can keep in git. Same
selection as pick_refs.py; records which corpus utterances went in."""
import json, sys, subprocess
from pathlib import Path
import numpy as np, soundfile as sf

root = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
want = ["3000", "2086", "2902", "3170", "6319"]
spk = {}
for w in root.rglob("*.wav"):
    spk.setdefault(w.parts[-3], []).append(w)
meta = {}
for s in want:
    ws = sorted(spk[s], key=lambda p: -p.stat().st_size)[:12]
    parts, dur, i, used = [], 0.0, 0, []
    while dur < 12 and i < len(ws) - 1:
        y, sr = sf.read(str(ws[i])); parts.append(y); dur += len(y) / sr; used.append(ws[i].name); i += 1
    ref = np.concatenate([np.concatenate([p, np.zeros(int(0.25 * sr))]) for p in parts])[: int(10.0 * sr)]
    wav = out / f"_ref_{s}.wav"; sf.write(str(wav), ref, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1",
                    "-c:a", "libopus", "-b:a", "96k", str(out / f"libritts_r_{s}.ogg")], check=True)
    wav.unlink()
    meta[s] = {"utterances": used, "seconds": 10.0, "source_rate": sr,
               "bytes": (out / f"libritts_r_{s}.ogg").stat().st_size}
(out / "ref_clips.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
