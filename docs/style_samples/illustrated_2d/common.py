import json, math, subprocess, cairo
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
W, H, FPS = 1920, 1080, 30
FONT_DIR = str(REPO / "assets" / "fonts")
T = json.load(open(HERE / "timing.json"))
B1, B2, B3 = T["beats"]
TOTAL = T["total"]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def seg(t, a, b):
    return clamp((t - a) / max(1e-6, b - a))


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def text(cr, s, x, y, size, color=(1, 1, 1, 1), face="Inter", weight=cairo.FONT_WEIGHT_BOLD,
         anchor="left", alpha=1.0):
    cr.select_font_face(face, cairo.FONT_SLANT_NORMAL, weight)
    cr.set_font_size(size)
    ext = cr.text_extents(s)
    if anchor == "center":
        x -= ext.width / 2 + ext.x_bearing
    elif anchor == "right":
        x -= ext.width + ext.x_bearing
    cr.set_source_rgba(color[0], color[1], color[2], (color[3] if len(color) > 3 else 1) * alpha)
    cr.move_to(x, y)
    cr.show_text(s)
    return ext


def render(frame_fn, out, audio=None, music=None):
    n = int(TOTAL * FPS)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    tmp = out + ".v.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", tmp],
                         stdin=subprocess.PIPE)
    for f in range(n):
        cr = cairo.Context(surf)
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        frame_fn(cr, f / FPS)
        surf.flush()
        p.stdin.write(bytes(surf.get_data()))
    p.stdin.close()
    p.wait()
    if not audio:  # no narration on hand: keep the silent render
        Path(tmp).replace(out)
        return
    mus = music or str(REPO / "data_learning/music/cinematic/lightless-dawn.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-i", audio, "-stream_loop", "-1",
                    "-i", mus, "-filter_complex",
                    f"[2:a]volume=0.22,atrim=0:{TOTAL:.2f},afade=t=out:st={TOTAL-2:.2f}:d=2[m];"
                    "[1:a]aresample=48000[v];[v][m]amix=inputs=2:duration=first:normalize=0,"
                    "loudnorm=I=-14:TP=-1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", out], check=True)
