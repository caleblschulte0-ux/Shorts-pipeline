#!/usr/bin/env python3
"""Proof Mode composer — capture artifacts -> 1080x1920 master.

Renders the four-beat format (THIRD_BRAIN.md §5) from a package JSON plus
a proof ledger produced by capture_cli.py. Every number shown on screen
is read from the ledger; the terminal replay draws the actual recorded
bytes at their true timestamps. Frames are generated with PIL and piped
raw to ffmpeg; per-beat voiceover comes from edge-tts and each beat's
screen time stretches to fit its narration.

Usage:
    python third_capture/compose.py <package.json> <ledger.json> <out.mp4>
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
# Safe area (house guardrails, THIRD_BRAIN.md §6)
SAFE_X0, SAFE_X1 = 70, 1010
SAFE_Y0, SAFE_Y1 = 160, 1580

BG = (13, 17, 23)          # gh-dark base
PANEL = (22, 27, 34)
INK = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
ORANGE = (210, 153, 34)
YELLOW = (241, 196, 15)
BLUE = (88, 166, 255)

FONTS = Path("/usr/share/fonts/truetype/dejavu")


def F(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\r")


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=width)


def caption(img, text, *, y=1440, color=INK):
    """Burned caption chunk, one readable block, inside the safe area."""
    d = ImageDraw.Draw(img)
    font = F("DejaVuSans-Bold.ttf", 52)
    lines = _wrap(d, text, font, SAFE_X1 - SAFE_X0 - 60)
    lh = 66
    bh = len(lines) * lh + 36
    rounded(d, (SAFE_X0, y, SAFE_X1, y + bh), 22, fill=(0, 0, 0))
    ty = y + 18
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) // 2, ty), ln, font=font, fill=color)
        ty += lh
    return img


def stopwatch_tag(img, label, cx=540, cy=1330, scale=1.0):
    d = ImageDraw.Draw(img)
    font = F("DejaVuSans-Bold.ttf", int(56 * scale))
    tw = d.textlength(label, font=font)
    w2, h2 = tw / 2 + 46, 52 * scale
    rounded(d, (cx - w2, cy - h2, cx + w2, cy + h2), 26,
            fill=(50, 42, 8), outline=YELLOW, width=4)
    d.text((cx - tw / 2, cy - 32 * scale), label, font=font, fill=YELLOW)


def stamp(img, text, color, cx=540, cy=760, scale=1.0, angle=-8):
    font = F("DejaVuSans-Bold.ttf", int(150 * scale))
    tmp = Image.new("RGBA", (1000, 320), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    tw = td.textlength(text, font=font)
    box = (500 - tw / 2 - 40, 30, 500 + tw / 2 + 40, 290)
    rounded(td, box, 30, outline=color + (255,), width=12)
    td.text((500 - tw / 2, 70), text, font=font, fill=color + (255,))
    tmp = tmp.rotate(angle, expand=False, resample=Image.BICUBIC)
    img.paste(tmp, (int(cx - 500), int(cy - 160)), tmp)


# ---------- data views ----------

def table_frame(rows, header, *, y0=300, n=10, hi=None, title=None,
                legend=None, col_x=(90, 420, 830),
                col_keys=("name", "email", "city")):
    """input_frame / output_card: a real slice of the CSV on a panel.
    hi = {row_index: color} highlight boxes; legend = [(color, text)]."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    rounded(d, (SAFE_X0 - 10, y0 - 90, SAFE_X1 + 10, y0 + n * 86 + 40),
            24, fill=PANEL, outline=(48, 54, 61), width=2)
    hf = F("DejaVuSansMono-Bold.ttf", 34)
    rf = F("DejaVuSansMono.ttf", 33)
    for x, k in zip(col_x, header):
        d.text((x, y0 - 60), k.upper(), font=hf, fill=DIM)
    d.line((SAFE_X0 + 10, y0 - 10, SAFE_X1 - 10, y0 - 10),
           fill=(48, 54, 61), width=2)
    for i, r in enumerate(rows[:n]):
        ry = y0 + 12 + i * 86
        if hi and i in hi:
            rounded(d, (SAFE_X0, ry - 8, SAFE_X1, ry + 66), 12,
                    outline=hi[i], width=5)
        for x, k in zip(col_x, col_keys):
            val = str(r.get(k, ""))
            # show whitespace defects explicitly
            shown = val.replace(" ", "·") if val != val.strip() else val
            maxw = (col_x[col_x.index(x) + 1] - x - 20
                    if x != col_x[-1] else SAFE_X1 - x - 26)
            while d.textlength(shown, font=rf) > maxw and len(shown) > 2:
                shown = shown[:-2]
            d.text((x, ry), shown, font=rf, fill=INK)
    if title:
        tf = F("DejaVuSans-Bold.ttf", 58)
        tw = d.textlength(title, font=tf)
        d.text(((W - tw) / 2, y0 - 190), title, font=tf, fill=INK)
    if legend:
        lf = F("DejaVuSans-Bold.ttf", 36)
        lx = SAFE_X0 + 10
        ly = y0 + n * 86 + 70
        for color, text in legend:
            d.rectangle((lx, ly + 6, lx + 34, ly + 40), outline=color,
                        width=5)
            d.text((lx + 50, ly), text, font=lf, fill=color)
            lx += 50 + d.textlength(text, font=lf) + 60
    return img


def terminal_panel(text_so_far, *, y0=430, y1=1240, cursor=True):
    """Real terminal replay panel: draws recorded bytes, nothing else."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    rounded(d, (SAFE_X0 - 10, y0, SAFE_X1 + 10, y1), 24,
            fill=(1, 4, 9), outline=(48, 54, 61), width=2)
    # window dots
    for i, c in enumerate(((248, 81, 73), (210, 153, 34), (63, 185, 80))):
        d.ellipse((SAFE_X0 + 18 + i * 44, y0 + 20,
                   SAFE_X0 + 46 + i * 44, y0 + 48), fill=c)
    font = F("DejaVuSansMono.ttf", 30)
    cols = int((SAFE_X1 - SAFE_X0 - 40) // d.textlength("M", font=font))
    lines = []
    for raw in ANSI.sub("", text_so_far).split("\n"):
        while len(raw) > cols:
            lines.append(raw[:cols])
            raw = raw[cols:]
        lines.append(raw)
    max_lines = (y1 - y0 - 100) // 44
    lines = lines[-max_lines:]
    ty = y0 + 76
    for i, ln in enumerate(lines):
        color = GREEN if ln.startswith("$") else INK
        d.text((SAFE_X0 + 20, ty), ln, font=font, fill=color)
        ty += 44
    if cursor and lines is not None:
        lw = d.textlength(lines[-1] if lines else "", font=font)
        d.rectangle((SAFE_X0 + 22 + lw, ty - 44, SAFE_X0 + 40 + lw, ty - 8),
                    fill=INK)
    return img


def task_card(img, text, y=210):
    d = ImageDraw.Draw(img)
    font = F("DejaVuSans-Bold.ttf", 46)
    lines = _wrap(d, text, font, SAFE_X1 - SAFE_X0 - 80)
    bh = len(lines) * 58 + 30
    rounded(d, (SAFE_X0, y, SAFE_X1, y + bh), 20, fill=(27, 32, 44),
            outline=BLUE, width=3)
    ty = y + 16
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, ty), ln, font=font, fill=BLUE)
        ty += 58
    return img


# ---------- beats ----------

class Beat:
    def __init__(self, name, vo_text, min_s, render, caption_text=None):
        self.name, self.vo, self.min_s = name, vo_text, min_s
        self.render = render                    # f(t_local, dur) -> Image
        self.caption = caption_text if caption_text is not None else vo_text
        self.dur = min_s
        self.audio: Path | None = None


def build_beats(pkg, led, fixture_rows, clean_rows):
    ev = led["events"]
    shell_line = led["notes"]["shell_line"]
    n_in = led["files"]["input"]["rows"]
    n_out = led["files"]["output"]["rows"]
    removed = n_in - n_out
    wall = led["wall_time_s"]
    fmt = dict(n_in=f"{n_in:,}", n_out=f"{n_out:,}",
               removed=f"{removed:,}", wall=f"{wall:.2f}")

    header = ("name", "email", "city")

    # find a real adjacent-duplicate pair to highlight honestly
    seen, dupe_pair = {}, (0, 1)
    for i, r in enumerate(fixture_rows[:60]):
        k = json.dumps(r, sort_keys=True)
        if k in seen:
            dupe_pair = (seen[k], i)
            break
        seen[k] = i
    show = fixture_rows[:10]
    if dupe_pair[1] >= 10:   # pull the real pair into view
        show = [fixture_rows[dupe_pair[0]], fixture_rows[dupe_pair[1]]] \
            + [r for i, r in enumerate(fixture_rows[:12])
               if i not in dupe_pair][:8]
        dupe_pair = (0, 1)

    def hook(t, dur):
        img = table_frame(show, header, title=None)
        img = img.filter(ImageFilter.GaussianBlur(6))
        img = Image.eval(img, lambda v: int(v * 0.45))
        d = ImageDraw.Draw(img)
        font = F("DejaVuSans-Bold.ttf", 96)
        for i, ln in enumerate(pkg["hook_lines"]):
            tw = d.textlength(ln, font=font)
            d.text(((W - tw) / 2, 560 + i * 130), ln, font=font, fill=INK)
        if t > 0.5:
            s = 0.7 + 0.3 * ease((t - 0.5) / 0.25)
            stamp(img, f"{fmt['removed']} DUPES", RED, cy=1120, scale=s * 0.62,
                  angle=-6)
        return img

    def input_beat(t, dur):
        # highlights arrive one per ~0.9s: change every 0.6-1.2s rule
        hi = {}
        def _is_messy(r):
            name = r.get("name", "")
            return (any(v != v.strip() for v in r.values())
                    or name.strip() in (name.strip().upper(),
                                        name.strip().lower()))
        messy = [i for i, r in enumerate(show[:10])
                 if i not in dupe_pair and _is_messy(r)][:3]
        steps = ([(dupe_pair[0], RED), (dupe_pair[1], RED)]
                 + [(i, ORANGE) for i in messy])
        for i, (row, color) in enumerate(steps):
            if t > 0.55 + i * 0.9:
                hi[row] = color
        # y0=460 clears the task_card (ends ~356); n=8 keeps the legend
        # above the caption block
        img = table_frame(
            show, header, hi=hi, y0=460, n=8,
            legend=[(RED, "exact duplicates"), (ORANGE, "messy formatting")])
        d = ImageDraw.Draw(img)
        tf = F("DejaVuSans-Bold.ttf", 58)
        title = f"{fmt['n_in']} rows of this."
        d.text(((W - d.textlength(title, font=tf)) / 2, 110), title,
               font=tf, fill=INK)
        return task_card(img, pkg["task_definition"])

    type_time = 1.6

    def proof(t, dur):
        # 1) type the real command  2) replay recorded output at true speed
        if t < type_time:
            n = int(len(shell_line) * ease(t / type_time))
            txt = "$ " + shell_line[:n]
        else:
            txt = "$ " + shell_line + "\n"
            rt = t - type_time
            for off, chunk in ev:
                if off <= rt:
                    txt += chunk
            if led["exit_code"] == 0 and rt > led["wall_time_s"] + 0.2:
                txt += f"\n$ # exit 0 — {fmt['wall']}s"
        img = terminal_panel(txt, y0=470, y1=1120)
        img = task_card(img, "One free command: Miller (mlr)")
        if t > type_time + led["wall_time_s"] + 0.4:
            s = min(1.0, (t - type_time - led["wall_time_s"] - 0.4) / 0.25)
            stopwatch_tag(img, f"⏱ {fmt['wall']}s measured", cy=1230,
                          scale=0.7 + 0.3 * s)
        return img

    def output_beat(t, dur):
        img = table_frame(clean_rows[:9], header, n=9,
                          title="Same file. Zero duplicates.")
        d = ImageDraw.Draw(img)
        if t > 0.8:
            stopwatch_tag(img, f"−{fmt['removed']} junk rows",
                          cy=1165, scale=0.9)
        # split_compare chips
        chip = F("DejaVuSans-Bold.ttf", 44)
        rounded(d, (SAFE_X0, 1250, 520, 1360), 20, fill=(60, 18, 18),
                outline=RED, width=3)
        d.text((SAFE_X0 + 30, 1274), f"BEFORE  {fmt['n_in']}", font=chip,
               fill=RED)
        rounded(d, (560, 1250, SAFE_X1, 1360), 20, fill=(12, 46, 22),
                outline=GREEN, width=3)
        d.text((590, 1274), f"AFTER  {fmt['n_out']}", font=chip, fill=GREEN)
        return img

    def verdict(t, dur):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        s = 0.7 + 0.3 * ease(t / 0.3)
        stamp(img, pkg["verdict"], GREEN, cy=640, scale=s)
        font = F("DejaVuSans-Bold.ttf", 54)
        ty = 900
        for i, block in enumerate(pkg["verdict_lines"]):
            for ln in _wrap(d, block, font, SAFE_X1 - SAFE_X0 - 40):
                tw = d.textlength(ln, font=font)
                d.text(((W - tw) / 2, ty), ln, font=font,
                       fill=INK if i == 0 else DIM)
                ty += 78
            ty += 26
        return img

    script = {k: v.format(**fmt) for k, v in pkg["script"].items()}
    return [
        Beat("hook", script["hook"], 2.8, hook),
        Beat("input", script["input"], 5.5, input_beat),
        Beat("proof", script["proof"],
             type_time + max(2.5, led["wall_time_s"] + 1.6), proof),
        Beat("output", script["output"], 5.0, output_beat),
        Beat("verdict", script["verdict"], 4.5, verdict),
    ]


# ---------- audio ----------

async def _tts(text, out, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate="+8%").save(str(out))


def make_audio(beats, tmp, voice):
    for i, b in enumerate(beats):
        p = tmp / f"vo_{i}.mp3"
        asyncio.run(_tts(b.vo, p, voice))
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)]).decode().strip())
        b.audio, b.dur = p, max(b.min_s, dur + 0.55)
    # assemble: each VO delayed to its beat start
    starts, t = [], 0.0
    for b in beats:
        starts.append(t)
        t += b.dur
    total = t
    inputs, filters, tags = [], [], []
    for i, (b, st) in enumerate(zip(beats, starts)):
        inputs += ["-i", str(b.audio)]
        ms = int(st * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        tags.append(f"[a{i}]")
    filters.append(f"{''.join(tags)}amix=inputs={len(beats)}"
                   f":normalize=0,apad=whole_dur={total}[out]")
    mix = tmp / "vo_mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs,
                    "-filter_complex", ";".join(filters),
                    "-map", "[out]", "-t", f"{total}", str(mix)], check=True)
    return mix, total


# ---------- main ----------

def compose(pkg_path: Path, ledger_path: Path, out_path: Path) -> Path:
    import csv as _csv
    pkg = json.loads(pkg_path.read_text())
    led = json.loads(ledger_path.read_text())
    with open(led["files"]["input"]["path"]) as fh:
        fixture_rows = list(_csv.DictReader(fh))
    with open(led["files"]["output"]["path"]) as fh:
        clean_rows = list(_csv.DictReader(fh))

    beats = build_beats(pkg, led, fixture_rows, clean_rows)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        vo, total = make_audio(beats, tmp, pkg.get("voice",
                                                   "en-US-ChristopherNeural"))
        print(f"[compose] {total:.1f}s total, beats: "
              + ", ".join(f"{b.name}={b.dur:.1f}s" for b in beats))
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", "-i", str(vo),
             "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
             "-shortest", str(out_path)], stdin=subprocess.PIPE)
        n_frames = int(total * FPS)
        bi, b_start = 0, 0.0
        for f in range(n_frames):
            t = f / FPS
            while bi < len(beats) - 1 and t >= b_start + beats[bi].dur:
                b_start += beats[bi].dur
                bi += 1
            b = beats[bi]
            img = b.render(t - b_start, b.dur)
            if b.caption:
                caption(img, b.caption)
            enc.stdin.write(img.tobytes())
        enc.stdin.close()
        enc.wait()
        if enc.returncode:
            raise RuntimeError("ffmpeg encode failed")
    print(f"[compose] wrote {out_path}")
    return out_path


if __name__ == "__main__":
    compose(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
