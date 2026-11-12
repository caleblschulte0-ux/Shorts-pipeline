"""frames + narration -> the finished short, the explainer's own way: the narration as voiced, the explainer's music
bed and mix (studio_render._build_soundtrack), the hook on screen from frame one, word-chunk captions under it.
usage: python assemble.py FRAMEDIR NARRDIR MAIN_CHECKOUT OUT.mp4"""
import json, subprocess, sys, os, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); from clock import FPS   # the one clock
frames, narr, main, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(main)); sys.path.insert(0, str(main / "data_learning"))
import studio_render as sr
meta = json.load(open(narr / "narration.json")); lines, win = meta["lines"], meta["windows"]
work = out.parent / "work"; work.mkdir(parents=True, exist_ok=True)


def speech_end(wav):
    """Where the last real word ends. A TTS take can end on a short isolated burst of noise (a breath or a clipped
    syllable); the 3D short of 2026-11-11 cut into one at its last frame and caaleb heard "that weird sound at the
    end". A trailing sound shorter than BURST_S after a gap is that, not speech."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "silencedetect=n=-38dB:d=0.12", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                               capture_output=True, text=True).stdout)
    starts = [float(x.split("silence_start: ")[1].split()[0]) for x in r.splitlines() if "silence_start" in x]
    ends = [float(x.split("silence_end: ")[1].split()[0]) for x in r.splitlines() if "silence_end" in x]
    sounds, t = [], 0.0                      # the non-silent stretches
    for a, b in zip(starts, ends + [dur]):
        if a > t: sounds.append((t, a))
        t = b
    if t < dur - 0.01: sounds.append((t, dur))
    while len(sounds) > 1 and sounds[-1][1] - sounds[-1][0] < BURST_S: sounds.pop()
    return sounds[-1][1] if sounds else dur


BURST_S, TAIL_S, FADE_S = 0.3, 0.9, 0.7      # trailing noise; music after the last word; the fade out at the end
n = len(list(frames.glob("f*.png"))); said = speech_end(narr / "narration.wav")
total = max(n / FPS, said + TAIL_S)           # never end on the voice: the picture holds its last frame if it must
clean = work / "narration_clean.wav"         # the voice up to its last word, then silence to the end
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(narr / "narration.wav"), "-af",
                f"atrim=0:{said + 0.06:.3f},afade=t=out:st={said - 0.02:.3f}:d=0.08,apad=whole_dur={total:.3f}", str(clean)],
               check=True)
vibe = json.load(open(main / "data_learning/niche.config.json")).get("music_vibe", "calm")
mix0 = sr._build_soundtrack(clean, [tuple(w) for w in win], [], total, vibe, work, slug=meta.get("slug", ""))
mix = work / "soundtrack_faded.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mix0), "-af",
                f"atrim=0:{total:.3f},afade=t=out:st={total - FADE_S:.3f}:d={FADE_S}", str(mix)], check=True)

# NATIVE, never upscaled (2026-11-12 brief: "native 1080x1920 at 30 FPS, verified, not upscaled"): the frames must
# already be 1080x1920; a smaller render is refused here instead of being stretched into a soft video.
from PIL import Image
_first = sorted(frames.glob("f*.png"))[0]; SRC_W, SRC_H = Image.open(_first).size
if (SRC_W, SRC_H) != (1080, 1920) and os.environ.get("ALLOW_UPSCALE") != "1":
    sys.exit(f"frames are {SRC_W}x{SRC_H}, not native 1080x1920: render at pct=100 (ALLOW_UPSCALE=1 only for a preview)")


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"
# THE SAFE AREA (2026-11-12 brief: "captions positioned for Shorts and TikTok"). Both apps lay their own interface
# over the video: the title, caption, music line and buttons over the bottom ~22% (to y ~1500 of 1920), the like /
# comment / share column down the right edge (x > ~930), the tabs and search over the top ~12%. The hook hangs
# below the top band; the word captions sit above the bottom band, clear of the right-hand column.
SAFE_L, SAFE_R = 100, 190          # px from the left / right edge
HOOK_TOP = 270                     # px from the top to the hook's first line
CAP_BOTTOM = 560                   # px from the bottom to the caption's baseline: the caption ends at y ~1360
ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "", "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       f"Style: Hook,DejaVu Sans,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,8,{SAFE_L},{SAFE_R},{HOOK_TOP},1",
       f"Style: Cap,DejaVu Sans,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,{SAFE_L},{SAFE_R},{CAP_BOTTOM},1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
# the hook: the whole line on screen from frame one, the said word lit (hook_karaoke)
# ACCURATE TIMING (2026-11-12 brief: "accurate, readable captions"): each line's words are spread over where the
# voice is actually SPEAKING inside its window (silencedetect on the take), weighted by syllables, not by characters
# over the whole window (which ran every caption late into the pause after its line).
_sil = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(narr / "narration.wav"), "-af", "silencedetect=n=-38dB:d=0.12", "-f", "null", "-"],
                      capture_output=True, text=True).stderr
_s0 = [float(x.split("silence_start: ")[1].split()[0]) for x in _sil.splitlines() if "silence_start" in x]
_s1 = [float(x.split("silence_end: ")[1].split()[0]) for x in _sil.splitlines() if "silence_end" in x]
SILENT = list(zip(_s0, _s1 + [1e9]))


def spoken(a0, a1):
    """where the voice starts and stops inside a window"""
    s, e = a0, a1
    for x0, x1 in SILENT:
        if x0 <= s + 0.01 and x1 > s: s = min(x1, a1)
        if x1 >= e - 0.01 and x0 < e: e = max(x0, s + 0.2)
    return s, max(s + 0.2, e)


def syl(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    if any(ch.isdigit() for ch in w): return 2 * len(w)          # a number is said as words: long
    return max(1, len(re.findall(r"[aeiouy]+", w)) - (1 if w.endswith("e") and len(w) > 3 else 0))


h0, h1 = spoken(*win[0]); hw = lines[0].split(); speak = (h1 - h0)
acc = 0; tot = sum(syl(w) for w in hw)
for i, w in enumerate(hw):
    a = h0 + speak * acc / tot; acc += syl(w); b = h0 + speak * acc / tot if i < len(hw) - 1 else win[0][1]
    txt = " ".join(("{\\c&H00D7FF&}" + x + "{\\c&HFFFFFF&}") if j == i else x for j, x in enumerate(hw))
    ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Hook,,0,0,0,,{txt}")
# every other line: chunks of up to three words, timed by their length
for (a0, a1), line in list(zip(win, lines))[1:]:
    ws = line.split(); chunks = [ws[i:i + 3] for i in range(0, len(ws), 3)]
    s0, s1 = spoken(a0, a1); speak = s1 - s0; tot = sum(syl(w) for c in chunks for w in c); acc = 0
    for c in chunks:
        a = s0 + speak * acc / tot; acc += sum(syl(w) for w in c); b = s0 + speak * acc / tot
        ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{' '.join(c).upper()}")
(work / "caps.ass").write_text("\n".join(ass) + "\n")
# atadenoise: a temporal average that follows motion, the last guard against frame-to-frame grain ("the Dr. Katz
# effect", caaleb 2026-11-11); the shots carry their own camera moves, so there is no global zoom over the cuts
hold = max(0.0, total - n / FPS)
vf = (f"atadenoise=0a=0.04:0b=0.08:1a=0.04:1b=0.08:2a=0.04:2b=0.08:s=7,scale=1080:1920:flags=lanczos,"
      f"curves=all='0/0 0.25/0.235 0.8/0.81 1/1',eq=saturation=0.96,unsharp=5:5:0.4,ass={work / 'caps.ass'},format=yuv420p"
      + (f",tpad=stop_mode=clone:stop_duration={hold:.3f}" if hold > 0.01 else ""))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-pattern_type", "glob", "-i", str(frames / "f*.png"),
                "-i", str(mix), "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)], check=True)
print("ASSEMBLED", out, f"{total:.2f}s", f"last word {said:.2f}s", meta.get("tts"))
# THE ACTUAL RENDER, measured off the file (2026-11-12 brief: "actual render metadata"): what was rendered and what
# came out, so nobody has to take a number on trust
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
                               capture_output=True, text=True).stdout)
vs = next(s for s in pr["streams"] if s["codec_type"] == "video"); au = next((s for s in pr["streams"] if s["codec_type"] == "audio"), {})
num, den = map(int, vs["r_frame_rate"].split("/"))
render = {"frames_rendered": n, "frame_size": [SRC_W, SRC_H], "native": (SRC_W, SRC_H) == (1080, 1920), "fps": FPS,
          "video": {"width": vs["width"], "height": vs["height"], "fps": round(num / den, 3), "codec": vs["codec_name"],
                    "frames": int(vs.get("nb_frames", 0) or 0), "pix_fmt": vs.get("pix_fmt")},
          "audio": {"codec": au.get("codec_name"), "sample_rate": au.get("sample_rate")},
          "duration_s": round(float(pr["format"]["duration"]), 3), "bytes": int(pr["format"]["size"]),
          "last_word_s": round(said, 3), "tts": meta.get("tts"), "lines": lines, "windows": win}
(out.parent / "render.json").write_text(json.dumps(render, indent=1))
ok = render["video"]["width"] == 1080 and render["video"]["height"] == 1920 and abs(render["video"]["fps"] - FPS) < 0.01
print("RENDER", json.dumps({k: render[k] for k in ("frame_size", "native", "fps", "duration_s")}), render["video"], "OK" if ok else "WRONG")
if not ok: sys.exit("the output is not 1080x1920 at the story's frame rate")
