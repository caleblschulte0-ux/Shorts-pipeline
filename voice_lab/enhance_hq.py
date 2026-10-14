"""Round 12: make each native-rate take CLEAR, two ways, then master it.
  sr   ClearerVoice MossFormer2_SR_48K (Apache-2.0): rebuilds the missing top
       end to 48 kHz.
  re   Resemble Enhance (MIT): denoise + enhance to 44.1 kHz (run separately,
       its pinned deps clash; this script masters whatever it finds).
Every version, the untouched one too, then gets the same broadcast chain:
rumble cut, a little less mud, a little more presence, de-ess, gentle
compression, -14 LUFS, 48 kHz 320k mp3.
  python enhance_hq.py IN OUT [sr]
"""
import subprocess, sys
from pathlib import Path
src, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
CHAIN = ("highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=4500:t=q:w=1.2:g=2.5,"
         "deesser=i=0.35,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80:makeup=2,"
         "loudnorm=I=-14:TP=-1:LRA=9")

def master(wav, name):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", CHAIN, "-ac", "1",
                    "-ar", "48000", "-b:a", "320k", str(out / f"{name}.mp3")], check=True)
    print("mastered", name, flush=True)

if len(sys.argv) > 3 and sys.argv[3] == "sr":
    from clearvoice import ClearVoice
    cv = ClearVoice(task="speech_super_resolution", model_names=["MossFormer2_SR_48K"])
    for w in sorted(src.glob("hq_*_raw.wav")):
        o = src / w.name.replace("_raw", "_sr")
        cv.write(cv(input_path=str(w), online_write=False), output_path=str(o))
        print("sr", o.name, flush=True)
for w in sorted(src.glob("hq_*_*.wav")):
    master(w, w.stem)
