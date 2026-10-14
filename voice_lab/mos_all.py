"""UTMOS naturalness (1-5, trained on human listening scores) for every mp3
under the given folders, whole-file average over 8s windows."""
import json, sys
from pathlib import Path
import librosa, torch
p = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
rows = {}
for d in sys.argv[2:]:
    for f in sorted(Path(d).glob("*.mp3")):
        y, sr = librosa.load(str(f), sr=16000)
        ch = [y[i:i + 8 * sr] for i in range(0, max(len(y) - 2 * sr, 1), 8 * sr)] or [y]
        s = [float(p(torch.from_numpy(c).unsqueeze(0), sr)) for c in ch]
        rows[f.stem] = round(sum(s) / len(s), 3); print(f.stem, rows[f.stem], flush=True)
Path(sys.argv[1]).write_text(json.dumps(dict(sorted(rows.items(), key=lambda kv: -kv[1])), indent=1))
