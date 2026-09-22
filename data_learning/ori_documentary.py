"""OpenRangeInteractive documentary renderer — an EPISODE script to a finished
8-10 minute 1920x1080 watch-page video.

WHY THIS EXISTS (2026-09-22). The channel posted one video (2026-07-08) and
then nothing: the "pro" producer took two-plus hours a render and its own
blind judges returned five of five cuts as BORING, so every run quarantined.
The operator's ask, in his words: "producing videos reliably that work and
look good ... People do them all the time on the internet ... they get
hundreds and thousands of views." The format those channels share is plain
and proven: calm narration over REAL footage that changes every few seconds,
chapter cards, the numbers put on screen as they are said, a music bed, and
a thumbnail made from a real frame. That is what this builds, in minutes.

Input: an episode script (`data_learning/ori_episodes/<slug>.json`, see
`validate()` for the contract). Output, next to the mp4:

    <out>.jpg        1920x1080 thumbnail from a real frame of the hook
    <out>.meta.json  chapters (first at 0:00), duration, sources, credits
    <out>.srt        captions timed to the narration

Every shot is real stock footage (Pexels / Pixabay / Mixkit through
`funnel.stock_search`), full frame, never the same clip twice in one film,
graded to one look. No camera move is ever added (operator ruling, every
channel): the footage moves; the overlays arrive.

    python -m data_learning.ori_documentary --slug <slug> --out output/x.mp4
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

EPISODES = PKG / "ori_episodes"
W, H, FPS = 1920, 1080, 30
SR = 24000
SFX = REPO / "assets" / "sfx"

VOICE = "am_michael"                 # calm US documentary narrator
SPEED = 1.0
BEAT_PAD = 0.30                      # breath between beats
CHAPTER_CARD_S = 3.2                 # a silent card: music + whoosh
SHOT_TARGET_S = 4.2                  # a new picture about every four seconds
SHOT_MIN_S = 2.4

MIN_WORDS, MAX_WORDS = 1150, 1900    # ~8-12 minutes at documentary pace
GOLD = (255, 211, 122)


# ------------------------------------------------------------------ contract
def validate(ep: dict) -> list[str]:
    """Everything wrong with an episode script, or [] — the one structural
    gate every author (a Claude session, the in-CI brain, ChatGPT) runs
    through before a render is spent on it."""
    bad: list[str] = []
    for k in ("slug", "title", "thumbnail_text", "chapters", "sources"):
        if not ep.get(k):
            bad.append(f"missing {k}")
    if bad:
        return bad
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", ep["slug"]):
        bad.append("slug must be kebab-case")
    if not (20 <= len(ep["title"]) <= 70):
        bad.append(f"title is {len(ep['title'])} chars (20-70)")
    if len(ep["thumbnail_text"].split()) > 5:
        bad.append("thumbnail_text over 5 words — a phone cannot read it")
    chs = ep["chapters"]
    if not (5 <= len(chs) <= 10):
        bad.append(f"{len(chs)} chapters (5-10)")
    words = 0
    for i, ch in enumerate(chs):
        if i and not (ch.get("title") or "").strip():
            bad.append(f"chapter {i} has no title")
        beats = ch.get("beats") or []
        if not beats:
            bad.append(f"chapter {i} has no beats")
        for j, b in enumerate(beats):
            say = (b.get("say") or "").strip()
            if not say:
                bad.append(f"chapter {i} beat {j} has no narration")
            words += len(say.split())
            shots = b.get("shots") or []
            if not shots:
                bad.append(f"chapter {i} beat {j} has no shots")
            for q in shots:
                if not (1 <= len(str(q).split()) <= 5):
                    bad.append(f"shot query {q!r} must be 1-5 plain words")
            st = b.get("stat")
            if st and not (str(st.get("value", "")).strip()
                           and str(st.get("label", "")).strip()):
                bad.append(f"chapter {i} beat {j} stat needs value + label")
            if st and str(st.get("value")).strip() not in say and \
                    _digits(st.get("value")) not in _digits(say):
                bad.append(f"chapter {i} beat {j} stat {st.get('value')!r} "
                           "is not said in its own narration")
    if not (MIN_WORDS <= words <= MAX_WORDS):
        bad.append(f"{words} narrated words ({MIN_WORDS}-{MAX_WORDS})")
    for s in ep["sources"]:
        if not str(s.get("url", "")).startswith("http") or not s.get("name"):
            bad.append(f"source {s!r} needs a name and an http url")
    if len(ep["sources"]) < 3:
        bad.append("fewer than 3 sources")
    return bad


def _digits(s) -> str:
    return re.sub(r"[^0-9]", "", str(s or ""))


def load(slug: str) -> dict:
    return json.loads((EPISODES / f"{slug}.json").read_text())


# ------------------------------------------------------------------ helpers
def _run(cmd: list[str], **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def probe_duration(p: Path) -> float:
    try:
        out = _run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "default=nk=1:nw=1", str(p)])
        return float(out.stdout.decode().strip() or 0)
    except Exception:                                   # noqa: BLE001
        return 0.0


def _font(size: int, weight: str = "semibold"):
    from shared import look
    return look.font(size, weight)


# ------------------------------------------------------------------ footage
#: The showrunner's cadence detector, reproduced for one clip: gray frames at
#: 24fps scaled to 192 wide, a 12x12 grid of blocks, and a pair of frames is
#: a DUPLICATE when no block's mean absolute difference reaches the
#: threshold (`showrunner_review._max_block_diff` / BLOCK_MOTION_THRESH).
#: A calm, beautiful shot of a still sea reads as FROZEN to it — measured on
#: this channel's first render: 4s of moonlit water was a 93-frame hold. So a
#: clip is probed before it is used, and one that barely moves is passed over
#: for one that does, which is also what keeps a viewer watching.
PROBE_S = 3.0
MAX_DUP = 0.35
MAX_RUN = 28
STATIC_MAX_S = 1.6          # the longest a clip that barely moves may hold


def motion_profile(path: Path, ss: float = 0.0, seconds: float = PROBE_S):
    """(duplicate_ratio, longest_duplicate_run) of `seconds` from `ss`."""
    import numpy as np
    try:
        raw = _run(["ffmpeg", "-loglevel", "error", "-ss", f"{ss:.2f}",
                    "-i", str(path), "-t", f"{seconds:.2f}", "-vf",
                    "fps=24,scale=192:108,format=gray", "-f", "rawvideo",
                    "-"]).stdout
    except Exception:                                   # noqa: BLE001
        return 1.0, 999
    n = len(raw) // (192 * 108)
    if n < 3:
        return 1.0, 999
    from scripts.showrunner_review import BLOCK_MOTION_THRESH
    f = np.frombuffer(raw[: n * 192 * 108], np.uint8).reshape(n, 108, 192)
    f = f.astype(np.int16)
    d = np.abs(np.diff(f, axis=0))                      # (n-1, 108, 192)
    blocks = d.reshape(n - 1, 12, 9, 12, 16).mean(axis=(2, 4))
    dup = blocks.max(axis=(1, 2)) < BLOCK_MOTION_THRESH
    run = best = 0
    for x in dup:
        run = run + 1 if x else 0
        best = max(best, run)
    return float(dup.mean()), best + 1 if best else 0


@dataclass
class Footage:
    """Finds a clip per shot, never the same clip twice in one film (a repeat
    is the one flaw a viewer notices unprompted), and records the credit."""
    work: Path
    used: set = field(default_factory=set)
    credits: list = field(default_factory=list)
    misses: list = field(default_factory=list)
    static: list = field(default_factory=list)
    fallback: list = field(default_factory=list)

    last_static: bool = False

    def get(self, queries: list[str], need: float) -> Path | None:
        from funnel import stock_search
        self.static = []
        self.last_static = False
        for q in [x for x in list(queries) + list(self.fallback) if x]:
            try:
                cands, _ = stock_search._collect(q, min_duration=3,
                                                 max_duration=60, per_page=15)
            except Exception:                           # noqa: BLE001
                continue
            cands.sort(key=stock_search._score_key)
            for c in cands[:10]:
                key = f"{c.get('provider')}:{c.get('id')}"
                if key in self.used:
                    continue
                try:
                    p = stock_search._download(c, self.work / "dl")
                except Exception:                       # noqa: BLE001
                    continue
                have = probe_duration(p)
                if have < 1.5:
                    continue
                ss = max(0.0, min(1.2, (have - need) / 3)) if have > need + 0.5 else 0.0
                dup, run = motion_profile(p, ss, min(PROBE_S, max(1.0, have - ss)))
                if dup > MAX_DUP or run > MAX_RUN:
                    self.static.append((dup, run, key, p, c, q))
                    continue
                self.used.add(key)
                self.credits.append({"provider": c.get("provider"),
                                     "id": c.get("id"),
                                     "page": c.get("url") or "",
                                     "author": c.get("user") or "",
                                     "query": q})
                return p
        # nothing lively enough: the liveliest unused clip beats no clip
        for dup, run, key, p, c, q in sorted(self.static, key=lambda t: t[0]):
            if key in self.used:
                continue
            self.used.add(key)
            self.last_static = True
            self.credits.append({"provider": c.get("provider"),
                                 "id": c.get("id"), "page": c.get("url") or "",
                                 "author": c.get("user") or "", "query": q,
                                 "static": round(dup, 2)})
            return p
        self.misses.append(queries)
        return None


# ------------------------------------------------------------------ overlays
def _png(img, path: Path) -> Path:
    img.save(path)
    return path


def stat_overlay(value: str, label: str, path: Path) -> Path:
    """Lower-left stat: the number as it is said, big, with its label."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # soft shadow plate so the number reads over any footage
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([60, H - 400, 1100, H - 60], fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(img)
    f_v = _font(150, "anton")
    d.rectangle([110, H - 330, 190, H - 322], fill=(*GOLD, 255))
    d.text((104, H - 316), value, font=f_v, fill=(255, 255, 255, 255))
    f_l = _font(40, "semibold")
    from shared import look
    lines = look.wrap(d, label, f_l, 1000, 2)
    y = H - 120 - 48 * (len(lines) - 1)
    for ln in lines:
        d.text((110, y), ln, font=f_l, fill=(235, 238, 245, 255))
        y += 48
    return _png(img, path)


def chapter_overlay(num: int, title: str, path: Path) -> Path:
    from PIL import Image, ImageDraw
    from shared import look
    img = Image.new("RGBA", (W, H), (6, 8, 18, 150))
    d = ImageDraw.Draw(img)
    f_n = _font(44, "semibold")
    d.text((140, 380), look.spaced(f"chapter {num}"), font=f_n,
           fill=(*GOLD, 255))
    f_t = _font(104, "display")
    y = 450
    for ln in look.wrap(d, title, f_t, W - 280, 3):
        d.text((140, y), ln, font=f_t, fill=(255, 255, 255, 255))
        y += 118
    d.rectangle([140, y + 30, 380, y + 40], fill=(*GOLD, 255))
    return _png(img, path)


def line_overlay(text: str, path: Path) -> Path:
    """The words of a shot the footage library could not fill, set as a
    statement over the moving ground — a labelled fallback, never a black or
    frozen hole, and never somebody else's footage passed off as this."""
    from PIL import Image, ImageDraw
    from shared import look
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    f = _font(76, "display")
    lines = look.wrap(d, first, f, W - 360, 4)
    y = (H - len(lines) * 92) // 2
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y), ln, font=f, fill=(255, 255, 255, 255))
        y += 92
    return _png(img, path)


def title_overlay(title: str, path: Path) -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (6, 8, 18, 110))
    d = ImageDraw.Draw(img)
    from shared import look
    f_t = _font(120, "display")
    lines = look.wrap(d, title, f_t, W - 300, 3)
    y = (H - len(lines) * 132) // 2
    for ln in lines:
        tw = d.textlength(ln, font=f_t)
        d.text(((W - tw) / 2, y), ln, font=f_t, fill=(255, 255, 255, 255))
        y += 132
    d.rectangle([W / 2 - 120, y + 26, W / 2 + 120, y + 36], fill=(*GOLD, 255))
    return _png(img, path)


# ------------------------------------------------------------------ shots
GRADE = ("scale=1920:1080:force_original_aspect_ratio=increase,"
         "crop=1920:1080,fps=30,eq=contrast=1.06:saturation=1.08:"
         "brightness=-0.02,vignette=PI/5,format=yuv420p")


def cut(src: Path | None, dur: float, out: Path, overlay: Path | None = None,
        fade_overlay: float = 0.45, dim: float = 0.0) -> Path:
    """One shot: `dur` seconds of `src` (looped if short), graded to the
    channel look, with an overlay that fades in. No source -> a slow dark
    drift, never a black hole (and the miss is on the report)."""
    vf = GRADE
    if dim:
        vf += f",eq=brightness={-dim:.2f}"
    if src is not None:
        have = probe_duration(src)
        ss = max(0.0, min(1.2, (have - dur) / 3)) if have > dur + 0.5 else 0.0
        inp = (["-stream_loop", "-1"] if have < dur + ss + 0.1 else []) + \
            ["-ss", f"{ss:.2f}", "-i", str(src)]
    else:
        inp = ["-f", "lavfi", "-i",
               "gradients=s=1920x1080:c0=0x0b1030:c1=0x241a4a:c2=0x10304a:"
               "n=3:speed=0.3:r=30"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inp]
    if overlay is not None:
        cmd += ["-loop", "1", "-i", str(overlay), "-filter_complex",
                f"[0:v]{vf}[b];[1:v]format=rgba,fade=t=in:st=0.15:"
                f"d={fade_overlay}:alpha=1[o];[b][o]overlay=0:0:shortest=1,"
                "format=yuv420p[v]", "-map", "[v]"]
    else:
        cmd += ["-vf", vf]
    cmd += ["-t", f"{dur:.3f}", "-r", str(FPS), "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]
    _run(cmd)
    return out


def split(total: float) -> list[float]:
    """A beat's window cut into shots of about SHOT_TARGET_S."""
    n = max(1, round(total / SHOT_TARGET_S))
    while n > 1 and total / n < SHOT_MIN_S:
        n -= 1
    return [total / n] * n


# ------------------------------------------------------------------ voice
class Voice:
    def __init__(self, voice: str = VOICE, speed: float = SPEED):
        from data_learning.studio_render import KOKORO_MODEL, KOKORO_VOICES
        from kokoro_onnx import Kokoro
        if not (KOKORO_MODEL.exists() and KOKORO_VOICES.exists()):
            raise RuntimeError("Kokoro model files missing — the channel's "
                               "voice is Kokoro; refusing to narrate with "
                               "another")
        self.k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
        self.voice, self.speed = voice, speed

    def say(self, text: str):
        import numpy as np
        from data_learning.studio_render import _tts_text
        a, sr = self.k.create(_tts_text(text), voice=self.voice,
                              speed=self.speed, lang="en-us")
        a = np.asarray(a, dtype=np.float32)
        if sr != SR:
            n = int(round(len(a) * SR / sr))
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)),
                          a).astype(np.float32)
        return a


# ------------------------------------------------------------------ render
@dataclass
class Seg:
    kind: str                 # beat | card
    text: str = ""
    shots: list = field(default_factory=list)
    stat: dict | None = None
    chapter: int = 0
    title: str = ""
    audio: object = None
    start: float = 0.0
    dur: float = 0.0


def plan(ep: dict) -> list[Seg]:
    segs: list[Seg] = []
    for i, ch in enumerate(ep["chapters"]):
        if i:
            segs.append(Seg("card", chapter=i, title=ch["title"],
                            shots=list(ch["beats"][0].get("shots") or [])))
        for b in ch["beats"]:
            segs.append(Seg("beat", text=b["say"].strip(),
                            shots=list(b.get("shots") or []),
                            stat=b.get("stat"), chapter=i))
    return segs


def _mix(segs: list[Seg], work: Path, slug: str) -> Path:
    import numpy as np
    import soundfile as sf
    total = segs[-1].start + segs[-1].dur
    n = int(math.ceil(total * SR)) + SR
    voice = np.zeros(n, np.float32)
    sfx = np.zeros(n, np.float32)
    whoosh = None
    try:
        w, wsr = sf.read(str(SFX / "whoosh.wav"), dtype="float32")
        w = w.mean(axis=1) if w.ndim > 1 else w
        if wsr != SR:
            w = np.interp(np.linspace(0, len(w) - 1, int(len(w) * SR / wsr)),
                          np.arange(len(w)), w).astype(np.float32)
        whoosh = w * 0.4
    except Exception:                                   # noqa: BLE001
        pass
    for s in segs:
        i = int(s.start * SR)
        if s.audio is not None:
            voice[i:i + len(s.audio)] += s.audio[: max(0, n - i)]
        if s.kind == "card" and whoosh is not None:
            sfx[i:i + len(whoosh)] += whoosh[: max(0, n - i)]
    vp, sp = work / "voice.wav", work / "sfx.wav"
    sf.write(str(vp), voice, SR)
    sf.write(str(sp), sfx, SR)
    from data_learning.studio_render import _music_track
    track = _music_track("cinematic", slug)
    out = work / "mix.wav"
    if track:
        fc = (f"[2:a]volume=0.32,atrim=0:{total:.3f},afade=t=in:d=2,"
              f"afade=t=out:st={max(0.0, total - 5):.3f}:d=5,aresample=48000,"
              "aformat=channel_layouts=stereo[m];"
              "[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[v][k];"
              "[m][k]sidechaincompress=threshold=0.02:ratio=8:attack=20:"
              "release=600[d];"
              "[1:a]aresample=48000,aformat=channel_layouts=stereo[s];"
              "[v][d][s]amix=inputs=3:duration=first:normalize=0,"
              "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vp), "-i", str(sp),
              "-stream_loop", "-1", "-i", str(track), "-filter_complex", fc,
              "-map", "[a]", "-ar", "48000", str(out)])
    else:
        print("[ori] no music library — narration + sfx only", file=sys.stderr)
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vp), "-i", str(sp),
              "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:"
              "normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]", "-map", "[a]",
              "-ar", "48000", str(out)])
    return out


def thumbnail(frame: Path, text: str, out: Path) -> Path:
    """A real frame, darkened toward the words, three to five words a phone
    can read at thumbnail size, one accent bar."""
    from PIL import Image, ImageDraw
    from shared import look
    img = Image.open(frame).convert("RGB").resize((W, H))
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(215 * max(0.0, 1 - x / (W * 0.72))))
    img = Image.composite(Image.new("RGB", (W, H), (4, 6, 14)), img, shade)
    d = ImageDraw.Draw(img)
    words = text.upper()
    size = 190
    f = _font(size, "display")
    lines = look.wrap(d, words, f, 1150, 9)
    while (len(lines) > 3 or len(lines) * size * 1.02 > H - 260) and size > 100:
        size -= 10
        f = _font(size, "display")
        lines = look.wrap(d, words, f, 1150, 9)
    y = (H - len(lines) * int(size * 1.02)) // 2
    d.rectangle([90, y - 60, 330, y - 44], fill=GOLD)
    for k, ln in enumerate(lines):
        col = GOLD if k == len(lines) - 1 else (255, 255, 255)
        d.text((96, y + 6), ln, font=f, fill=(0, 0, 0))
        d.text((90, y), ln, font=f, fill=col)
        y += int(size * 1.02)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def _srt(segs: list[Seg], out: Path) -> Path:
    from data_learning.longform_render import write_srt
    beats = [s for s in segs if s.kind == "beat"]
    return write_srt([s.text for s in beats],
                     [(s.start, s.start + s.dur - BEAT_PAD) for s in beats], out)


def render(ep: dict, out: Path, *, max_seconds: float | None = None) -> dict:
    """Render `ep` to `out`. Returns the meta dict (also written beside it)."""
    problems = validate(ep)
    if problems and not max_seconds:
        raise ValueError("episode script invalid: " + "; ".join(problems))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    segs = plan(ep)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        v = Voice(ep.get("voice", VOICE), float(ep.get("speed", SPEED)))
        t = 0.0
        kept = []
        for s in segs:
            if s.kind == "beat":
                s.audio = v.say(s.text)
                s.dur = len(s.audio) / SR + BEAT_PAD
            else:
                s.dur = CHAPTER_CARD_S
            s.start = t
            t += s.dur
            kept.append(s)
            if max_seconds and t >= max_seconds:
                break
        segs = kept
        total = t
        print(f"[ori] {ep['slug']}: {len(segs)} segments, {total / 60:.1f} min",
              flush=True)

        foot = Footage(work)
        # broad, on-topic stand-ins for a shot the library cannot fill
        foot.fallback = list(ep.get("thumbnail_shots") or []) + \
            [t for t in ep.get("tags") or [] if len(t.split()) <= 3][:4]
        last_intro = max(i for i, s in enumerate(segs)
                         if s.kind == "beat" and s.chapter == 0)
        # PASS 1, sequential: choose every shot's footage (the no-repeat set
        # has to see the film in order). PASS 2, parallel: cut them.
        jobs = []                      # (src, dur, out, overlay, fade)
        for si, s in enumerate(segs):
            if s.kind == "card":
                src = foot.get(s.shots + [ep["title"]], s.dur)
                ov = chapter_overlay(s.chapter, s.title, work / f"card{si}.png")
                jobs.append((src, s.dur, work / f"c{si:03d}.mp4", ov, 0.35))
                continue
            parts = split(s.dur)
            for k, d in enumerate(parts):
                qs = s.shots[k % len(s.shots):] + s.shots[:k % len(s.shots)]
                src = foot.get(qs, d)
                # a near-static clip may hold the screen for STATIC_MAX_S at
                # most; the rest of the shot is another clip (a cut is motion)
                spare = 0
                while foot.last_static and d > STATIC_MAX_S * 1.25 \
                        and spare < 3:
                    jobs.append((src, STATIC_MAX_S,
                                 work / f"c{si:03d}_{k}s{spare}.mp4", None, 0.45))
                    d -= STATIC_MAX_S
                    spare += 1
                    src = foot.get(qs[1:] + qs[:1], d)
                ov = None
                if src is None:
                    ov = line_overlay(s.text, work / f"line{si}_{k}.png")
                elif si == last_intro and k == len(parts) - 1:
                    # the title lands over the cold open's last shot: by the
                    # first chapter the viewer knows what this video is
                    ov = title_overlay(ep["title"], work / "title.png")
                elif s.stat and k == min(1, len(parts) - 1):
                    ov = stat_overlay(str(s.stat["value"]), s.stat["label"],
                                      work / f"stat{si}.png")
                jobs.append((src, d, work / f"c{si:03d}_{k}.mp4", ov, 0.45))
            if si % 10 == 0:
                print(f"[ori] footage chosen for {si + 1}/{len(segs)} segments",
                      flush=True)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            clips = list(pool.map(lambda j: cut(j[0], j[1], j[2], j[3],
                                                fade_overlay=j[4]), jobs))
        # the thumbnail is its own shot: the frame that sells the video is
        # not necessarily the one it opens on
        hook_frame = None
        tsrc = foot.get(list(ep.get("thumbnail_shots") or [])
                        + list(segs[0].shots), 1.0)
        if tsrc is not None:
            hook_frame = work / "hook.jpg"
            at = max(0.5, min(2.0, probe_duration(tsrc) / 2))
            _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}",
                  "-i", str(tsrc), "-frames:v", "1", "-vf",
                  "scale=1920:1080:force_original_aspect_ratio=increase,"
                  "crop=1920:1080", str(hook_frame)])
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips))
        video = work / "video.mp4"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(lst), "-c", "copy", str(video)])
        audio = _mix(segs, work, ep["slug"])
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i",
              str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags",
              "+faststart", str(out)])
        if hook_frame is None or not hook_frame.exists():
            hook_frame = work / "hook.jpg"
            _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i",
                  str(out), "-frames:v", "1", str(hook_frame)])
        thumbnail(hook_frame, ep["thumbnail_text"], out.with_suffix(".jpg"))
    _srt(segs, out.with_suffix(".srt"))
    chapters = [{"t": 0.0, "label": "Intro"}]
    for s in segs:
        if s.kind == "card":
            chapters.append({"t": round(s.start, 2), "label": s.title})
    meta = {"slug": ep["slug"], "title": ep["title"],
            "duration": round(probe_duration(out) or total, 2),
            "chapters": chapters,
            "sources": [f"{s['name']} — {s['url']}" for s in ep["sources"]],
            "footage": foot.credits, "footage_misses": foot.misses}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[ori] {out} ({meta['duration'] / 60:.1f} min, "
          f"{len(foot.credits)} clips, {len(foot.misses)} misses)", flush=True)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=None,
                    help="preview: stop after this many seconds")
    args = ap.parse_args()
    render(load(args.slug), args.out, max_seconds=args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
