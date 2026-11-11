"""frames + narration -> the finished short, the explainer's own way: the narration as voiced, the explainer's music
bed and mix (studio_render._build_soundtrack), the hook on screen from frame one, word-chunk captions under it.
usage: python assemble.py FRAMEDIR NARRDIR MAIN_CHECKOUT OUT.mp4"""
import json, subprocess, sys, os
from pathlib import Path
frames, narr, main, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(main)); sys.path.insert(0, str(main / "data_learning"))
import studio_render as sr
meta = json.load(open(narr / "narration.json")); lines, win = meta["lines"], meta["windows"]
n = len(list(frames.glob("f*.png"))); total = n / 24
work = out.parent / "work"; work.mkdir(parents=True, exist_ok=True)
vibe = json.load(open(main / "data_learning/niche.config.json")).get("music_vibe", "calm")
mix = sr._build_soundtrack(narr / "narration.wav", [tuple(w) for w in win], [], total, vibe, work, slug=meta.get("slug", ""))

def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"
ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "", "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Hook,DejaVu Sans,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,8,90,90,230,1",
       "Style: Cap,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,90,90,210,1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
# the hook: the whole line on screen from frame one, the said word lit (hook_karaoke)
h0, h1 = win[0]; hw = lines[0].split(); speak = (h1 - h0 - 0.12)
acc = 0; tot = sum(len(w) + 1 for w in hw)
for i, w in enumerate(hw):
    a = h0 + speak * acc / tot; acc += len(w) + 1; b = h0 + speak * acc / tot if i < len(hw) - 1 else h1
    txt = " ".join(("{\\c&H00D7FF&}" + x + "{\\c&HFFFFFF&}") if j == i else x for j, x in enumerate(hw))
    ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Hook,,0,0,0,,{txt}")
# every other line: chunks of up to three words, timed by their length
for (a0, a1), line in list(zip(win, lines))[1:]:
    ws = line.split(); chunks = [ws[i:i + 3] for i in range(0, len(ws), 3)]
    speak = a1 - a0 - 0.12; tot = sum(len(" ".join(c)) + 1 for c in chunks); acc = 0
    for c in chunks:
        a = a0 + speak * acc / tot; acc += len(" ".join(c)) + 1; b = a0 + speak * acc / tot
        ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{' '.join(c).upper()}")
(work / "caps.ass").write_text("\n".join(ass) + "\n")
# atadenoise: a temporal average that follows motion, the last guard against frame-to-frame grain ("the Dr. Katz
# effect", caaleb 2026-11-11); the shots carry their own camera moves, so there is no global zoom over the cuts
vf = (f"atadenoise=0a=0.04:0b=0.08:1a=0.04:1b=0.08:2a=0.04:2b=0.08:s=7,scale=1080:1920:flags=lanczos,"
      f"curves=all='0/0 0.25/0.235 0.8/0.81 1/1',eq=saturation=0.96,unsharp=5:5:0.4,ass={work / 'caps.ass'},format=yuv420p")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-pattern_type", "glob", "-i", str(frames / "f*.png"),
                "-i", str(mix), "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", "24",
                "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
print("ASSEMBLED", out, f"{total:.2f}s", meta.get("tts"))
