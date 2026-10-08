"""Join per-line WAVs the way studio_render does: per-line tempo, 0.12s
breath, loudnorm to -16 LUFS, then mp3 for listening."""
import json, subprocess, sys, tempfile
from pathlib import Path

def run(*a):
    subprocess.run(a, check=True)

def finish(wavs, out_mp3, tempo):
    td = Path(tempfile.mkdtemp())
    parts = []
    for i, w in enumerate(wavs):
        p = td / f"p{i}.wav"
        run("ffmpeg", "-y", "-loglevel", "error", "-i", str(w), "-af",
            f"aresample=24000,atempo={tempo:.4f},apad=pad_dur=0.12", "-ac", "1",
            "-c:a", "pcm_s16le", str(p))
        parts.append(p)
    lst = td / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
        str(lst), "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", "-ar", "44100",
        "-b:a", "160k", str(out_mp3))

if __name__ == "__main__":
    tempo = float(sys.argv[1]); out = sys.argv[2]; wavs = sys.argv[3:]
    finish(wavs, out, tempo)
