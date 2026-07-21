#!/usr/bin/env python3
"""Text-card format renderer — the 'looping eye-candy on top, highlighted text
below' retention hack (business.raptor style).

Layout (1080x1920):
  * top ~40%  : a short looping clip (gameplay / b-roll) — visual filler
  * bottom    : the payload — centered bold paragraphs, key phrases in gold,
                over black, with a calm music bed
No TTS, no captions. The clip loops; the text takes longer to read than the
loop runs, so viewers replay to finish → watch-time/loops inflate.

    from make_text_card import build_text_card
    build_text_card(pkg, Path("out.mp4"))

Package schema:
  {"format":"text_card","title":"...","text":"para 1\\n\\npara 2\\n\\npara 3",
   "highlights":["glued","zero screws","0 out of 10"],
   "broll_query":"apple airpods","music_vibe":"calm"}
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import make_explainer_stacked as base

W, H, FPS = base.W, base.H, base.FPS
GAMEPLAY_DIR = base.GAMEPLAY_DIR
TOP_H = 770                      # top clip height (≈40%)
TEXT_TOP = TOP_H + 40            # text starts a touch below the seam
SIDE = 62
TEXT_W = W - SIDE * 2
BODY_SIZE = 56
LINE_GAP = int(BODY_SIZE * 0.42)
PARA_GAP = 46
WHITE = (255, 255, 255)
GOLD = (245, 197, 24)           # #F5C518

_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu",
              str(Path(__file__).resolve().parent / "assets" / "fonts")]


def _font(size: int, bold: bool = True):
    names = (["DejaVuSans-Bold.ttf"] if bold else ["DejaVuSans.ttf"])
    for d in _FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _mark_gold(words: list[str], highlights: list[str]) -> list[bool]:
    """Return, per word, whether it belongs to any highlight phrase."""
    low = [w.strip(".,!?;:'\"()").lower() for w in words]
    gold = [False] * len(words)
    for h in highlights:
        hw = [x.strip(".,!?;:'\"()").lower() for x in h.split() if x.strip()]
        if not hw:
            continue
        for i in range(len(low) - len(hw) + 1):
            if low[i:i + len(hw)] == hw:
                for j in range(len(hw)):
                    gold[i + j] = True
    return gold


def _wrap(draw, words, golds, font, max_w):
    """Word-wrap into lines of [(word, gold)], respecting max width."""
    lines, cur, cur_w = [], [], 0
    space = draw.textlength(" ", font=font)
    for w, g in zip(words, golds):
        ww = draw.textlength(w, font=font)
        add = ww + (space if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
            add = ww
        cur.append((w, g))
        cur_w += add
    if cur:
        lines.append(cur)
    return lines


def _layout(d0, text, highlights, size):
    """Lay out paragraphs at a given font size. Returns (laid, line_h,
    para_gap, total_h)."""
    font = _font(size, bold=True)
    line_h = font.getbbox("Ay")[3] + int(size * 0.42)
    para_gap = int(size * 0.82)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    laid = []
    for para in paragraphs:
        words = para.split()
        golds = _mark_gold(words, highlights)
        laid.append(_wrap(d0, words, golds, font, TEXT_W))
    total_h = sum(len(lines) * line_h for lines in laid) \
        + para_gap * max(0, len(laid) - 1)
    return font, laid, line_h, para_gap, max(total_h, 10)


def render_text_png(text: str, highlights: list[str], out: Path,
                    avail_h: int = H - TEXT_TOP - 48) -> Path:
    """Render the centered, gold-highlighted paragraph block to a transparent
    PNG, auto-shrinking the font so the whole block fits `avail_h`."""
    tmp = Image.new("RGBA", (10, 10))
    d0 = ImageDraw.Draw(tmp)
    size = 58
    font, laid, line_h, para_gap, total_h = _layout(d0, text, highlights, size)
    while total_h > avail_h and size > 30:
        size -= 2
        font, laid, line_h, para_gap, total_h = _layout(
            d0, text, highlights, size)

    img = Image.new("RGBA", (W, total_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    space = d.textlength(" ", font=font)
    y = 0
    for lines in laid:
        for line in lines:
            lw = sum(d.textlength(w, font=font) for w, _ in line) \
                + space * (len(line) - 1)
            x = (W - lw) / 2
            for w, g in line:
                d.text((x, y), w, font=font, fill=(GOLD if g else WHITE))
                x += d.textlength(w, font=font) + space
            y += line_h
        y += para_gap
    img.save(str(out))
    return out


def _run(cmd):
    subprocess.run(cmd, check=True)


def _dur(p: Path) -> float:
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    try:
        return float(o.stdout.strip())
    except ValueError:
        return 0.0


def _top_clip(tag: str, target: float, workdir: Path) -> Path:
    clips = [p for p in GAMEPLAY_DIR.iterdir()
             if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")] \
        if GAMEPLAY_DIR.exists() else []
    pool = [p for p in clips if tag.lower() in p.stem.lower()] or clips
    if not pool:
        raise RuntimeError(f"no clips in {GAMEPLAY_DIR}")
    src = random.choice(pool)
    sdur = _dur(src)
    seek = random.uniform(5, max(5, sdur - target - 20)) if sdur > target + 30 \
        else 0.0
    out = workdir / "top.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
          "-ss", f"{seek:.2f}", "-i", str(src), "-t", f"{target:.2f}",
          "-vf", f"scale={W}:{TOP_H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{TOP_H},setsar=1,fps={FPS}",
          "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          str(out)])
    return out


def build_text_card(pkg: dict, out_path: Path, *, duration: float = 7.0,
                    gameplay_tag: str = "minecraft") -> None:
    workdir = Path(tempfile.mkdtemp(prefix="textcard_"))
    try:
        duration = float(pkg.get("duration") or duration)
        text = pkg.get("text", "").strip()
        highlights = pkg.get("highlights", []) or []
        print("[1/4] text block")
        text_png = render_text_png(text, highlights, workdir / "text.png")
        # position text under the seam, vertically centered in the lower area
        th = Image.open(text_png).size[1]
        avail = H - TEXT_TOP
        ty = TEXT_TOP + max(0, (avail - th) // 2)

        print(f"[2/4] top clip ({duration:.1f}s loop)")
        top = _top_clip(gameplay_tag, duration, workdir)

        print("[3/4] music bed")
        music = workdir / "music.wav"
        has_music = True
        try:
            base.synth_music(duration, music, pkg.get("music_vibe", "dark"))
        except Exception as e:  # noqa: BLE001
            print(f"      music skipped: {e}")
            has_music = False

        print("[4/4] compose")
        # black canvas, top clip at y=0, text png overlaid at ty
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "lavfi", "-t", f"{duration:.2f}",
               "-i", f"color=c=black:s={W}x{H}:r={FPS}",   # 0 bg
               "-i", str(top),                              # 1 top clip
               "-loop", "1", "-t", f"{duration:.2f}", "-i", str(text_png)]  # 2
        if has_music:
            cmd += ["-i", str(music)]                       # 3
        graph = (f"[0:v][1:v]overlay=0:0[a];"
                 f"[a][2:v]overlay=0:{ty}[v]")
        cmd += ["-filter_complex", graph, "-map", "[v]"]
        if has_music:
            cmd += ["-map", "3:a", "-c:a", "aac", "-b:a", "160k"]
        cmd += ["-t", f"{duration:.2f}", "-c:v", "libx264", "-preset",
                "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart", str(out_path)]
        _run(cmd)
        try:
            Path(str(out_path) + ".audit.json").write_text(json.dumps({
                "out": str(out_path), "format": "text_card",
                "duration_s": duration}, indent=2) + "\n")
        except Exception:  # noqa: BLE001
            pass
        print(f"done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    import sys
    pkg = json.loads(Path(sys.argv[1]).read_text())
    build_text_card(pkg, Path(sys.argv[2] if len(sys.argv) > 2
                              else "textcard.mp4"))
