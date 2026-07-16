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
    # NASA asset hrefs can contain spaces/control chars (ids like
    # "NHQ_2020_1221_Earth Views"); urllib rejects them raw. Encode the path
    # while preserving the URL structure.
    if " " in url or any(ord(c) < 33 for c in url):
        from urllib.parse import quote, urlsplit, urlunsplit
        p = urlsplit(url)
        url = urlunsplit((p.scheme, p.netloc, quote(p.path),
                          quote(p.query, safe="=&?"), p.fragment))
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
    """A 1080p-sufficient mp4 from a NASA asset manifest. The pipeline renders
    at 1080p, so ~orig is usually a wasteful choice: for these ISS clips every
    rendition is the SAME resolution (720p) and ~orig is just a bloated-bitrate
    copy (6 GB vs 1.7 GB for ~large). Prefer an explicit 1080/~large rendition
    so downloads stay CI-disk-safe (three multi-GB ~orig clips overflow a
    GitHub runner) with no resolution loss; fall back to ~orig only if nothing
    smaller-but-adequate exists."""
    man = json.loads(_get(
        f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}"))
    hrefs = [i.get("href", "") for i in man["collection"]["items"]]
    mp4s = [h for h in hrefs if h.lower().endswith(".mp4")]
    if not mp4s:
        raise RuntimeError(f"no mp4 asset for {nasa_id}")
    # lower rank = preferred. A true 1080 rendition wins; else ~large (1080p or
    # a right-sized 720p); ~orig sits BELOW ~large so we never pull the bloated
    # copy when an adequate one exists; the small tiers are last resorts.
    def rank(h: str) -> int:
        h = h.lower()
        for i, tag in enumerate(("1080", "~large", "720", "~orig",
                                 "~medium", "480", "~small", "~mobile")):
            if tag in h:
                return i
        return 99
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


def _sample_frames(clip: Path, ss: float, dur: float, n: int = 8):
    """Grab n evenly-spaced small frames from the EXACT window [ss, ss+dur]."""
    import numpy as np
    from PIL import Image
    tmp = clip.parent / f"_win_{int(ss * 100)}.png"
    frames = []
    for k in range(n):
        t = ss + dur * (k + 0.5) / n
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
             "-i", str(clip), "-frames:v", "1", "-vf", "scale=192:-1",
             str(tmp)], check=True)
        frames.append(np.asarray(Image.open(tmp).convert("RGB"),
                                 dtype="float32"))
    tmp.unlink(missing_ok=True)
    return frames


def analyze_window(clip: Path, ss: float, dur: float) -> dict:
    """Inspect the EXACT time range the renderer plans to use (operator spec
    §1) — not a general sample of the source. Returns {ok, flags, ...}.

    Heuristic backstop that runs inside the render; the vision pass
    (window_contact_sheet + a judge) is the authoritative check. Catches the
    cheap, unambiguous failures: black frames, flat title-card/diagram frames
    (bright + desaturated + low detail — the 'nitrogen molecule on grey paper'
    tell), and a hard cut / sudden visual change inside the window."""
    import numpy as np
    fr = _sample_frames(clip, ss, dur)
    flags, black, cardish = [], 0, 0
    grays, is_card, is_black = [], [], []
    for a in fr:
        g = a.mean(2)
        grays.append(g)
        bright = float(g.mean())
        sat = float((a.max(2) - a.min(2)).mean())
        detail = float(g.std())
        lit = float((g > 55).mean())
        blk = bright < 12
        # a produced card / diagram / title / logo:
        #  - a LIGHT flat desaturated card (the 'nitrogen on grey paper' tell), or
        #  - a near-empty frame carrying only a small centred logo/watermark
        #    (mostly dark, very little lit content, low overall detail).
        card = (bright > 125 and sat < 34 and detail < 58) or \
               (lit < 0.05 and detail < 34 and not blk)
        is_black.append(blk)
        is_card.append(card)
        black += int(blk)
        cardish += int(card)
    n = len(fr)
    # A cut is only a defect when it lands ON a graphic/black frame
    # (footage -> card, the nitrogen transition). Cuts between two real shots
    # — a normal multi-camera launch montage — are fine and must be allowed.
    cut_to_graphic = False
    for i in range(1, n):
        jump = float(np.abs(grays[i] - grays[i - 1]).mean())
        if jump > 34 and (is_card[i] or is_black[i] or is_card[i - 1]):
            cut_to_graphic = True
    if black >= 2:
        flags.append("black_frames")
    if cardish >= 2:
        flags.append("graphic_or_title_card")
    if cut_to_graphic:
        flags.append("cut_to_graphic")
    return {"ok": not flags, "flags": flags,
            "black": black, "cardish": cardish}


def pick_window(clip: Path, dur: float, at: float = 0.5,
                head_skip: float = 3.0):
    """Choose the best usable window for a `dur`-second beat: scan the
    black-free windows, slide a `dur` sub-window through each, and return the
    first that passes analyze_window (subject-bearing, no card/cut/black).
    Returns (ss, report) or (None, report) if nothing in the source is clean."""
    reports = []
    for w0, w1 in clean_windows(clip, min_len=dur + 0.3, head_skip=head_skip):
        span = w1 - w0
        # candidate starts: the requested position first, then a sweep
        cands = [w0 + (span - dur) * at]
        steps = max(1, int(span // dur))
        cands += [w0 + i * (span - dur) / max(1, steps) for i in range(steps + 1)]
        for ss in cands:
            ss = max(w0, min(ss, w1 - dur))
            rep = analyze_window(clip, ss, dur)
            reports.append({"ss": round(ss, 1), **rep})
            if rep["ok"]:
                return round(ss, 2), reports
    return None, reports


def window_contact_sheet(clip: Path, ss: float, dur: float, out: Path,
                         cols: int = 5):
    """A dense contact sheet of ONLY the [ss, ss+dur] window — the artifact a
    vision judge (or the orchestrator) reads to confirm a segment is clean
    live-action footage before it is committed."""
    from PIL import Image, ImageDraw, ImageFont
    tiles, tw = [], 384
    tmp = out.parent / "_wct.png"
    for k in range(cols * 2):
        t = ss + dur * (k + 0.5) / (cols * 2)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
             "-i", str(clip), "-frames:v", "1", "-vf", f"scale={tw}:-1",
             str(tmp)], check=True)
        im = Image.open(tmp).convert("RGB")
        d = ImageDraw.Draw(im)
        try:
            f = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except Exception:  # noqa: BLE001
            f = ImageFont.load_default()
        d.text((5, 5), f"{t:0.1f}s", font=f, fill=(255, 235, 120))
        tiles.append(im)
    tmp.unlink(missing_ok=True)
    th = tiles[0].height
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (10, 10, 16))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out)
    return out


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
