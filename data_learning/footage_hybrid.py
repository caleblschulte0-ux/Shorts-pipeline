#!/usr/bin/env python3
"""THE FOOTAGE HYBRID (CURIOSITY_BRAIN §7.5 v9 — proven on pixels).

Ten rounds of pure procedural/Cycles renders never cleared the ledger-blind
judge panel: 4-core CPU Cycles with no denoiser tops out below photoreal, and
the panel called every attempt what it was — GENERIC_CG, EMPTY_COMPOSITION,
WEAK_TRANSFORMATION. Real NASA footage does clear it — the *same* panel that
failed Preview #7 (2/3/2) and failed a sloppily-cut footage proof (adversarial
4, viewer 2) returned a UNANIMOUS PASS (viewer 90 / editor 79 / adversarial 84,
zero critical failures) on footage assembled with three rules and nothing else:

  1. REAL footage only — NASA hosts data-visualizations and artist animations
     alongside camera footage; the animations read as GENERIC_CG to the panel.
     `is_real_footage()` rejects them from metadata before download.
  2. FULL-FRAME, with a matched continuous move — the footage IS the beat
     (scaled/cropped to fill 1920x1080 + a slow zoompan push), never a small
     rectangle pasted into an animation. `full_frame_beat()`.
  3. A motion-matched DISSOLVE between beats — never a hard cut from motion to a
     near-static image (that is the PASTED_MEDIA tell), never a fade to black.
     `dissolve_join()`.

Plus a slate/black-frame guard: NASA broadcast clips carry burned-in production
slates and black leader that torpedoed the first proof. `clean_windows()` skips
the head and refuses spans containing black frames.

Standalone:
    python3 -m data_learning.footage_hybrid search "earth from space station"
    python3 -m data_learning.footage_hybrid beat <src.mp4> <ss> <dur> <out.mp4>
    python3 -m data_learning.footage_hybrid join out.mp4 a.mp4 b.mp4 ...

The blind panel (scripts/visual_judge.py) remains the gate: this module makes
footage-primary assembly *possible*; a clip is certified only by the panel.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

W, H, FPS = 1920, 1080, 30

# --- the real-footage gate ------------------------------------------------
# NASA's video library mixes three things under one search: camera FOOTAGE
# (what we want), data VISUALIZATIONS (SVS/Goddard scientific animations), and
# artist CONCEPTS. The last two are exactly the "generic CG / screensaver" look
# the panel rejects — and we already make our own CG, so borrowed CG is the
# worst of both. Reject on the words the animators themselves use.
_ANIMATION_TELLS = (
    "animation", "animated", "visualization", "visualisation",
    "conceptual", "concept", "artist", "simulation", "simulated",
    "rendering", "rendered", "illustration", "graphic", "cgi",
    "data visualization", "model of", "depiction", "depicts",
    "scientific visualization", "svs", "computer-generated",
)
# ...but these words alone over-reject (a launch clip may say "animation of the
# trajectory" in passing). Positive footage signals rescue a borderline item.
_FOOTAGE_TELLS = (
    "footage", "camera", "views", "timelapse", "time-lapse", "time lapse",
    "hdev", "gopro", "onboard", "cockpit", "cupola", "liftoff", "launch",
    "landing", "splashdown", "recorded", "filmed", "captured by",
    "b-roll", "broll", "raw", "4k", "uhd", "high definition",
)


def is_real_footage(title: str, desc: str, keywords) -> bool:
    """True when metadata reads as camera footage, not an animation/viz.

    Rule: any animation tell disqualifies UNLESS a footage tell also appears
    and outnumbers it — real launch/orbit footage occasionally mentions an
    accompanying animation, but a pure viz never claims to be filmed."""
    hay = " ".join([title or "", desc or "",
                    " ".join(keywords or [])]).lower()
    anim = sum(1 for t in _ANIMATION_TELLS if t in hay)
    real = sum(1 for t in _FOOTAGE_TELLS if t in hay)
    if anim == 0:
        return True
    return real > anim


# --- NASA video search + download ----------------------------------------
def _get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "curiosity-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search_footage(query: str, limit: int = 12) -> list[dict]:
    """NASA media_type=video search, animation-filtered. Returns a list of
    {nasa_id, title, desc, keywords} for items that read as real footage."""
    res = json.loads(_get(
        "https://images-api.nasa.gov/search?media_type=video&q="
        + urllib.parse.quote(query)))
    out = []
    for it in res["collection"]["items"][:limit * 2]:
        d = (it.get("data") or [{}])[0]
        title, desc = d.get("title", ""), d.get("description", "") or ""
        kw = d.get("keywords") or []
        if not d.get("nasa_id"):
            continue
        if not is_real_footage(title, desc, kw):
            continue
        out.append({"nasa_id": d["nasa_id"], "title": title,
                    "desc": desc[:200], "keywords": kw})
        if len(out) >= limit:
            break
    return out


def download_video(nasa_id: str, dest: Path) -> Path:
    """Largest reasonable mp4 from a NASA asset manifest (~orig / 1080p)."""
    man = json.loads(_get(
        f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}"))
    hrefs = [i.get("href", "") for i in man["collection"]["items"]]
    mp4s = [h for h in hrefs if h.lower().endswith(".mp4")]
    if not mp4s:
        raise RuntimeError(f"no mp4 asset for {nasa_id}")
    # prefer an explicit large/orig/1080 rendition, else the biggest by a
    # crude filename heuristic (NASA names them ~orig, ~large, -1080, -720)
    def rank(h: str) -> int:
        h = h.lower()
        for i, tag in enumerate(("~orig", "1080", "~large", "720",
                                 "~medium", "480")):
            if tag in h:
                return i
        return 9
    pick = sorted(mp4s, key=rank)[0]
    dest.write_bytes(_get(pick))
    return dest


# --- clean-window detection (kill slates + black leader) ------------------
def _duration(clip: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0.0)


def _black_spans(clip: Path) -> list[tuple[float, float]]:
    """ffmpeg blackdetect — spans where the frame is (near) black. NASA
    broadcast clips bookend segments with black leader and slates."""
    out = subprocess.run(
        ["ffmpeg", "-i", str(clip), "-vf",
         "blackdetect=d=0.15:pic_th=0.96:pix_th=0.10", "-an",
         "-f", "null", "-"], capture_output=True, text=True)
    spans = []
    for m in re.finditer(
            r"black_start:([\d.]+)\s+black_end:([\d.]+)", out.stderr):
        spans.append((float(m.group(1)), float(m.group(2))))
    return spans


def clean_windows(clip: Path, min_len: float = 4.0,
                  head_skip: float = 3.0) -> list[tuple[float, float]]:
    """Spans of at least `min_len` seconds that contain no black frames and
    skip the first `head_skip` seconds (where slates/leader live). Returns
    [(start, end), ...] longest-first — pick [0] for the best clean take."""
    dur = _duration(clip)
    if dur <= head_skip + 0.5:
        return []
    blacks = _black_spans(clip)
    # build the complement of black spans, within [head_skip, dur]
    cursor = head_skip
    windows = []
    for b0, b1 in sorted(blacks):
        if b1 <= head_skip:
            continue
        b0 = max(b0, head_skip)
        if b0 - cursor >= min_len:
            windows.append((cursor, b0))
        cursor = max(cursor, b1)
    if dur - cursor >= min_len:
        windows.append((cursor, dur))
    windows.sort(key=lambda w: w[1] - w[0], reverse=True)
    return windows


# --- the three rules as ffmpeg -------------------------------------------
def full_frame_beat(src: Path, ss: float, dur: float, out: Path,
                    push: float = 1.06, direction: str = "in") -> Path:
    """Rule 2: the footage IS the beat. Scale/crop to fill the whole 16:9
    frame (no letterbox, no rectangle) and add a slow matched push so a real
    still or slow orbit reads as continuous motion, not a frozen photo.

    `push` is the total zoom factor over the beat; `direction` in/out chooses
    push-in (default, into the subject) or pull-out."""
    frames = max(2, int(round(dur * FPS)))
    step = (push - 1.0) / frames
    if direction == "in":
        z = f"min(1.0+{step:.7f}*on,{push:.4f})"
    else:
        z = f"max({push:.4f}-{step:.7f}*on,1.0)"
    # upscale before zoompan so small zoom factors don't jitter, then crop
    # to fill, then the push.
    vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
          f"crop={W * 2}:{H * 2},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d=1:s={W}x{H}:fps={FPS},format=yuv420p")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ss:.3f}",
         "-i", str(src), "-t", f"{dur:.3f}", "-vf", vf, "-an",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", str(out)], check=True)
    return out


def dissolve_join(clips: list[Path], out: Path,
                  xfade: float = 0.7) -> Path:
    """Rule 3: motion-matched dissolve between beats — never a hard cut from
    motion to a near-static image, never a fade to black. Chains xfade so beat
    N dissolves into beat N+1 over `xfade` seconds of overlap.

    A single clip is passed through unchanged."""
    clips = [Path(c) for c in clips]
    if not clips:
        raise RuntimeError("dissolve_join needs at least one clip")
    if len(clips) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(clips[0]),
             "-c", "copy", str(out)], check=True)
        return out
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    durs = [_duration(c) for c in clips]
    # build the xfade chain; offset = running total minus the overlaps so far
    filt, prev, offset = [], "[0:v]", 0.0
    for i in range(1, len(clips)):
        offset += durs[i - 1] - xfade
        label = f"[v{i}]" if i < len(clips) - 1 else "[vout]"
        filt.append(
            f"{prev}[{i}:v]xfade=transition=dissolve:duration={xfade}:"
            f"offset={offset:.3f}{label}")
        prev = label
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filt), "-map", "[vout]",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def build_sequence(beats: list[dict], out: Path, work: Path,
                   xfade: float = 0.7) -> Path:
    """Assemble a footage-primary sequence from beat specs and gate-ready
    output. Each beat: {src, ss, dur, push?, direction?}. Cuts every beat
    full-frame with a matched move, then dissolve-joins them."""
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, b in enumerate(beats):
        c = work / f"beat_{i:02d}.mp4"
        full_frame_beat(Path(b["src"]), float(b["ss"]), float(b["dur"]), c,
                        push=float(b.get("push", 1.06)),
                        direction=b.get("direction", "in"))
        clips.append(c)
    return dissolve_join(clips, out, xfade=xfade)


# --- CLI ------------------------------------------------------------------
def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "search":
        for it in search_footage(argv[1]):
            print(f"{it['nasa_id']}\n   {it['title'][:74]}")
        return 0
    if cmd == "windows":
        for w in clean_windows(Path(argv[1])):
            print(f"{w[0]:.2f} - {w[1]:.2f}  ({w[1] - w[0]:.1f}s)")
        return 0
    if cmd == "beat":
        full_frame_beat(Path(argv[1]), float(argv[2]), float(argv[3]),
                        Path(argv[4]))
        print(f"beat -> {argv[4]}")
        return 0
    if cmd == "join":
        dissolve_join([Path(p) for p in argv[2:]], Path(argv[1]))
        print(f"joined -> {argv[1]}")
        return 0
    print(f"unknown command {cmd!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
