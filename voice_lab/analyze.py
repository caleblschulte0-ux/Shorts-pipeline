"""Objective checks on every sample: does a speech recogniser hear the exact
words (pronunciation), how fast is it, and how much does the pitch move
(flat vs. lively delivery)."""
import json, re, sys
from pathlib import Path
import numpy as np
import librosa
from faster_whisper import WhisperModel

L = json.loads((Path(__file__).parent / "lines.json").read_text())
ref = re.sub(r"[^a-z' ]", " ", " ".join(L["lines"]).lower()).split()
d = Path(sys.argv[1])
m = WhisperModel("small.en", device="cpu", compute_type="int8")


def wer(a, b):
    D = np.zeros((len(a) + 1, len(b) + 1), int)
    D[:, 0] = range(len(a) + 1); D[0, :] = range(len(b) + 1)
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            D[i, j] = min(D[i-1, j] + 1, D[i, j-1] + 1, D[i-1, j-1] + (a[i-1] != b[j-1]))
    return D[-1, -1] / len(a)


def norm(t):
    t = t.lower().replace("1970", "nineteen seventy").replace("51", "fifty one")
    t = t.replace("50", "fifty").replace("13", "thirteen").replace("%", " percent")
    return re.sub(r"[^a-z' ]", " ", t).split()


rows = {}
for f in sorted(d.glob("*.mp3")):
    if f.name.startswith("posted_"):
        continue
    segs, _ = m.transcribe(str(f), language="en", beam_size=5)
    text = " ".join(s.text for s in segs)
    y, sr = librosa.load(str(f), sr=16000)
    f0, vf, _ = librosa.pyin(y, fmin=60, fmax=300, sr=sr)
    f0 = f0[~np.isnan(f0)]
    semis = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.array([0])
    dur = len(y) / sr
    rows[f.stem] = {"wer_pct": round(100 * wer(ref, norm(text)), 1),
                    "pitch_range_semitones": round(float(np.percentile(semis, 95) - np.percentile(semis, 5)), 1),
                    "words_per_min": round(len(ref) / dur * 60),
                    "seconds": round(dur, 1), "heard": text.strip()}
    print(f.stem, rows[f.stem])
(d / "analysis.json").write_text(json.dumps(rows, indent=1))
