"""Listen back to every round-4 sample with whisper and score how much of
the script it actually said (a garbled clone is out before anyone hears it)."""
import json, re, sys, difflib
from pathlib import Path
import whisper
L = json.loads((Path(__file__).parent / "lines.json").read_text())
want = re.sub(r"[^a-z' ]", " ", " ".join(L["lines"]).lower()).split()
m = whisper.load_model("base.en"); res = {}
for mp3 in sorted(Path(sys.argv[1]).glob("*.mp3")):
    if mp3.stem.endswith("_real"): continue
    got = re.sub(r"[^a-z' ]", " ", m.transcribe(str(mp3))["text"].lower()).split()
    res[mp3.stem] = round(difflib.SequenceMatcher(None, want, got).ratio(), 3)
Path(sys.argv[1], "heard.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
