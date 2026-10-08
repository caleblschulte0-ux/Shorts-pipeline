"""Predicted naturalness (UTMOS, a model trained on human 1-5 listening
scores) for every committed sample, per line-sized 8s window."""
import json, sys
from pathlib import Path
import librosa, torch
p = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
d = Path(sys.argv[1]); rows = {}
for f in sorted(d.glob("*.mp3")):
    y, sr = librosa.load(str(f), sr=16000)
    chunks = [y[i:i + 8 * sr] for i in range(0, len(y) - 2 * sr, 8 * sr)]
    s = [float(p(torch.from_numpy(c).unsqueeze(0), sr)) for c in chunks]
    rows[f.stem] = round(sum(s) / len(s), 2)
    print(f.stem, rows[f.stem], [round(x, 2) for x in s])
(d / "mos.json").write_text(json.dumps(rows, indent=1))
