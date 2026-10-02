"""OpenRangeInteractive sleep films — an EPISODE script to a finished
20-30 minute 1920x1080 video.

WHY THIS FORMAT (operator, 2026-09-23). *"the niche we really want to lean
into ... is like that going to sleep niche ... I put this on, turn my phone
over, so I'm not even watching the screen and I'm just like listening."* The
market says the same: the "Boring History For Sleep" / "History for Sleep"
channels run 1:50-2:50 videos, and "What Did Early Humans ACTUALLY Do All
Day?" and "Why You Wouldn't Last a Day in Medieval Times" sit at 2.6M and
4.3M views. Nearly every one of them is AI painting slideshows. His art rule
was the hand-drawn cartoon look of History with Dave and Deep Epoch — so
every picture here is DRAWN BY CODE (`data_learning/doodle`), none is
generated, and nothing in it looks like AI. Since 2026-10-01 ("throw in
some" real paintings, camera dead still) a few passages a film open on a
public-domain painting from a museum collection, held still by candlelight
(`data_learning/ori_paintings.py`) — real art, credited, never generated.

Input: `data_learning/ori_episodes/<slug>.json` (contract: `validate()`).
Every narrated beat carries the scene it sits over. Output, next to the mp4:

    <out>.jpg        1920x1080 thumbnail: a close doodle scene + 2-4 words
    <out>.meta.json  chapters (first at 0:00), duration, words, scene count
    <out>.srt        captions, one sentence at a time

    python -m data_learning.ori_sleep --slug <slug> --out output/x.mp4
    python -m data_learning.ori_sleep --slug <slug> --out /tmp/p.mp4 --max-seconds 90

How it stays honest to the gate. A sleep film is calm, and the showrunner
reads a held frame as frozen. Nothing here fakes motion — no camera moves,
no shimmering lines (operator ruling, `shared/camera_float.py`). Every scene
must contain something that really moves (a fire at night, water, rain,
someone chopping wood), and `doodle.scene.validate` refuses one that does not,
from strengths measured with the gate's own detector.
"""
from __future__ import annotations

import argparse
import json
import math
import functools
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

EPISODES = PKG / "ori_episodes"
FONTS = REPO / "assets" / "fonts"
MUSIC = PKG / "music" / "sleep"
W, H, FPS = 1920, 1080, 24
SR = 24000
EL_WORKERS = 3               # concurrent ElevenLabs requests: every paid plan allows three

VOICE = os.environ.get("ORI_VOICE", "bm_george")   # low, unhurried British narrator
SPEED = 0.82
SENTENCE_GAP = 0.7           # a breath between sentences — sleep narration is slow
BEAT_GAP = 1.9               # a longer rest when the picture changes
CHAPTER_GAP = 6.0            # music alone between chapters
XFADE = 0.6                  # scenes dissolve quickly into each other: a shot is a sentence long
MIN_WORDS, MAX_WORDS = 2400, 4000       # ~18 to ~30 minutes at this pace
# Measured in CI, 2026-09-24 (run #15): 19,611 words narrated to 149.1 min —
# 131 words a minute WITH the gaps. The operator's ruling that evening, on
# the 114-minute medieval film: "114 Mins is to long shoot for like 20-30
# mins". 4,000 words is ~30 minutes; the author aims at 25.
MIN_CHAPTERS, MAX_CHAPTERS = 3, 8
BEAT_WORDS = (20, 190)
TITLE_MAX = 100
MUSIC_GAIN = 0.55            # after the bed's own -24 LUFS: ~10 dB under the voice
LOUDNESS = -18               # quieter than a watch video: this plays in the dark


# ------------------------------------------------------------------ contract
def _words(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", s or ""))


def validate(ep: dict) -> list[str]:
    """Everything wrong with an episode script, or [] — the one structural
    gate every author (a Claude session, the in-CI brain) runs through before
    two hours of render is spent on it."""
    from data_learning.doodle import scene as S
    bad: list[str] = []
    for k in ("slug", "title", "thumbnail_text", "thumbnail_scene", "era", "chapters",
              "description"):
        if not ep.get(k):
            bad.append(f"missing {k}")
    if bad:
        return bad
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", ep["slug"]):
        bad.append("slug must be kebab-case")
    if not (25 <= len(ep["title"]) <= TITLE_MAX):
        bad.append(f"title is {len(ep['title'])} chars (25-{TITLE_MAX})")
    if not (2 <= len(ep["thumbnail_text"].split()) <= 4):
        bad.append("thumbnail_text must be 2-4 words")
    if ep["era"] not in S.ERAS:
        bad.append(f"era {ep['era']!r} is not one of {S.ERAS}")
        return bad
    tb = S.validate(ep["thumbnail_scene"], ep["era"])
    if tb:
        bad.append("thumbnail_scene: " + "; ".join(tb))
    chs = ep["chapters"]
    if not isinstance(chs, list) or not (MIN_CHAPTERS <= len(chs) <= MAX_CHAPTERS):
        bad.append(f"{len(chs) if isinstance(chs, list) else '?'} chapters "
                   f"({MIN_CHAPTERS}-{MAX_CHAPTERS})")
        return bad
    total = 0
    for i, ch in enumerate(chs):
        if not ch.get("title"):
            bad.append(f"chapter {i + 1} has no title")
        beats = ch.get("beats") or []
        if len(beats) < 3:
            bad.append(f"chapter {i + 1} has {len(beats)} beats (at least 3)")
        for j, b in enumerate(beats):
            w = _words(b.get("say", ""))
            total += w
            if not (BEAT_WORDS[0] <= w <= BEAT_WORDS[1]):
                bad.append(f"chapter {i + 1} beat {j + 1}: {w} words ({BEAT_WORDS[0]}-{BEAT_WORDS[1]})")
            sb = S.validate(b.get("scene"), ep["era"])
            if sb:
                bad.append(f"chapter {i + 1} beat {j + 1} scene: " + "; ".join(sb))
    if not (MIN_WORDS <= total <= MAX_WORDS):
        bad.append(f"{total} narrated words ({MIN_WORDS}-{MAX_WORDS})")
    return bad


def load(slug: str) -> dict:
    return json.loads((EPISODES / f"{slug}.json").read_text())


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------------------ voice
class Voice:
    def __init__(self, voice: str = VOICE, speed: float = SPEED):
        from data_learning.studio_render import KOKORO_MODEL, KOKORO_VOICES
        from kokoro_onnx import Kokoro
        if not (KOKORO_MODEL.exists() and KOKORO_VOICES.exists()):
            raise RuntimeError("Kokoro model files missing — the channel's voice is Kokoro; "
                               "refusing to narrate with another")
        self.k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
        self.voice, self.speed = voice, speed

    def say(self, text: str):
        import numpy as np
        from data_learning.studio_render import _tts_text
        a, sr = self.k.create(_tts_text(text), voice=self.voice, speed=self.speed, lang="en-us")
        a = np.asarray(a, dtype=np.float32)
        if sr != SR:
            n = int(round(len(a) * SR / sr))
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
        return a


@dataclass
class Beat:
    chapter: int
    index: int                   # global beat index
    text: str
    scene: dict
    start: float = 0.0           # when its narration starts
    end: float = 0.0             # when the next beat's narration starts
    lines: list = field(default_factory=list)     # (t0, t1, sentence)


_WORKER_VOICE = None


def _voice_init(factory):
    """Each narration worker loads the voice once (Kokoro is ~350 MB)."""
    global _WORKER_VOICE
    _WORKER_VOICE = factory()


def _say_beat(text: str) -> list:
    """A beat's sentences spoken in a worker: [(sentence, audio), ...]."""
    return [(sent, _WORKER_VOICE.say(sent)) for sent in sentences(text)]


def narrate(ep: dict, wav: Path, *, max_seconds: float | None = None, voice=None,
            workers: int = 1, voice_factory=None) -> list[Beat]:
    """Speak the whole script into one 24 kHz mono wav, written as it goes
    (two hours of float audio does not belong in memory), and time every
    sentence. Returns the beats with their timings.

    With `workers` > 1 the sentences are spoken in a process pool, a chapter
    at a time so no more than a chapter of float audio waits in memory, and
    written in order: measured in CI (run #15), one process spoke 149 min of
    narration in 62 min, the whole judge's budget. `voice` given (a fake in
    the tests) always narrates in this process."""
    import numpy as np
    import soundfile as sf
    pool = None
    if voice is None and workers > 1:
        pool = ProcessPoolExecutor(max_workers=workers, initializer=_voice_init,
                                   initargs=(voice_factory or Voice,))
    try:
        return _narrate(ep, wav, max_seconds, voice, pool)
    finally:
        if pool is not None:
            pool.shutdown(cancel_futures=True)   # a voice that fails mid-film leaves no workers behind


def _narrate(ep: dict, wav: Path, max_seconds, voice, pool) -> list[Beat]:
    import numpy as np
    import soundfile as sf
    v = voice or (None if pool else Voice())
    beats: list[Beat] = []
    t = 0.0
    k = 0
    with sf.SoundFile(str(wav), "w", samplerate=SR, channels=1, subtype="PCM_16") as out:
        def silence(sec):
            nonlocal t
            n = int(round(sec * SR))
            out.write(np.zeros(n, dtype=np.float32))
            t += n / SR
        silence(1.5)
        stop = False
        for ci, ch in enumerate(ep["chapters"]):
            if ci:
                silence(CHAPTER_GAP)
            if pool is not None:
                spoken = list(pool.map(_say_beat, [b["say"] for b in ch["beats"]]))
            else:
                spoken = None
            for bi, b in enumerate(ch["beats"]):
                bt = Beat(chapter=ci, index=k, text=b["say"], scene=b["scene"], start=t)
                k += 1
                said = spoken[bi] if spoken is not None else [(sent, v.say(sent)) for sent in sentences(b["say"])]
                for si, (sent, a) in enumerate(said):
                    peak = float(np.max(np.abs(a))) if len(a) else 0.0
                    if peak > 0:
                        a = a * min(1.0, 0.89 / peak)
                    t0 = t
                    out.write(a)
                    t += len(a) / SR
                    bt.lines.append((t0, t, sent))
                    silence(SENTENCE_GAP)
                silence(BEAT_GAP - SENTENCE_GAP)
                beats.append(bt)
                if max_seconds and t >= max_seconds:
                    stop = True
                    break
            if stop:
                break
        silence(4.0)
    for a, b in zip(beats, beats[1:]):
        a.end = b.start
    beats[-1].end = t
    beats[0].start = 0.0
    return beats


# ------------------------------------------------------------------ text on screen
def _text_surface(text: str, size: int, font: str = "PatrickHand-Regular.ttf",
                  color=(248, 240, 222), shadow=(20, 16, 18, 170), band: bool = False):
    """A cairo surface holding one line of hand-lettered text with a soft
    shadow, made once and painted with alpha as it fades."""
    import cairo
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    f = ImageFont.truetype(str(FONTS / font), size)
    bbox = f.getbbox(text)
    w, h = bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 40
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if band:
        # a soft dark band behind the words: the title is read over whatever
        # the opening scene happens to put there (a pale cloud, once)
        ImageDraw.Draw(sh).rounded_rectangle((4, 4, w - 4, h - 4), radius=26, fill=(20, 16, 18, 185))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
    ImageDraw.Draw(sh).text((20 - bbox[0] + 3, 20 - bbox[1] + 4), text, font=f, fill=shadow)
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    ImageDraw.Draw(sh).text((20 - bbox[0], 20 - bbox[1]), text, font=f, fill=color + (255,))
    # PIL RGBA -> cairo premultiplied BGRA
    import numpy as np
    a = np.asarray(sh).astype(np.float32)
    al = a[..., 3:4] / 255.0
    bgra = np.concatenate([a[..., 2:3] * al, a[..., 1:2] * al, a[..., 0:1] * al, a[..., 3:4]], axis=2)
    buf = bytearray(bgra.astype(np.uint8).tobytes())
    return cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h, w * 4), buf


# ------------------------------------------------------------------ video
def _scene_seed(slug: str, index: int, spec: dict | None = None) -> int:
    """Deterministic per beat; a scene's `variant` (set by the storyboard
    review when a layout was found broken) picks a different one."""
    import hashlib
    v = int((spec or {}).get("variant") or 0)
    return int(hashlib.md5(f"{slug}:{index}:{v}".encode()).hexdigest()[:8], 16) if v else \
        int(hashlib.md5(f"{slug}:{index}".encode()).hexdigest()[:8], 16)


def _render_chunk(args) -> str:
    """Render beats [lo, hi) to one mp4 (video only). Runs in a worker."""
    (ep_min, beats, lo, hi, out, captions) = args
    import cairo
    from data_learning.doodle import scene as S
    era, slug = ep_min["era"], ep_min["slug"]
    scenes: dict[int, S.Scene] = {}

    def scene(i):
        sc = scenes.get(i)
        if sc is None and beats[i].get("painting"):
            from data_learning.ori_paintings import PaintingScene
            sc = PaintingScene(Path(beats[i]["painting"]), int(beats[i].get("seed") or 0))
            scenes[i] = sc
        if sc is None:
            seed = beats[i].get("seed")
            sc = S.Scene(beats[i]["scene"], era, seed if seed is not None else _scene_seed(slug, i, beats[i]["scene"]))
            scenes[i] = sc
            for j in list(scenes):
                if j < i - 1:
                    del scenes[j]
        return sc

    t0 = beats[lo]["start"]
    t1 = beats[hi - 1]["end"]
    n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-tune", "animation", "-crf", "20", "-g", str(FPS * 10), "-pix_fmt", "yuv420p",
           "-threads", "2", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    a = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    b = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    texts = [(c["t0"], c["t1"], c["x"], c["y"], _text_surface(c["text"], c["size"], band=c.get("band", False),
                                                            color=c.get("color", (248, 240, 222))))
             for c in captions if c["t1"] > t0 and c["t0"] < t1]
    i = lo
    for n in range(n0, n1):
        T = n / FPS
        while i < hi - 1 and T >= beats[i]["end"]:
            i += 1
        bi = beats[i]
        # local time runs from XFADE before the beat starts, so a scene is
        # already alive while it dissolves in
        scene(i).frame(T - bi["start"] + XFADE, a)
        fade_at = bi["end"] - XFADE
        if T >= fade_at and i + 1 < len(beats):
            k = (T - fade_at) / XFADE
            k = k * k * (3 - 2 * k)
            scene(i + 1).frame(T - beats[i + 1]["start"] + XFADE, b)
            cr = cairo.Context(a)
            cr.set_source_surface(b, 0, 0)
            cr.paint_with_alpha(k)
        if texts:
            cr = cairo.Context(a)
            for (c0, c1, x, y, (surf, _buf)) in texts:
                if c0 <= T < c1:
                    al = min(1.0, (T - c0) / 1.2, (c1 - T) / 1.2)
                    cr.set_source_surface(surf, x, y)
                    cr.paint_with_alpha(max(0.0, al))
        a.flush()
        p.stdin.write(bytes(a.get_data()))
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on chunk {lo}-{hi}")
    return out


def _captions(ep: dict, beats: list[Beat]) -> list[dict]:
    """On-screen words: the title over the opening, then each chapter's
    title in the corner as it begins. Everything else is heard, not read."""
    out = [dict(text=ep["title"].split("|")[0].strip(), size=74, t0=1.0, t1=10.0,
                x=110, y=110, band=True)]
    # the second line of the title ("Cozy History for Sleep") says what this
    # is and invites the listener in — the hook the judge grades
    tail = ep["title"].split("|")[1].strip() if "|" in ep["title"] else ""
    if tail:
        # big and bright: at 44px in the band's grey it was "small and
        # low-contrast on the purple sky" to the ninth film's judge
        out.append(dict(text=tail, size=60, t0=1.8, t1=10.0, x=118, y=236, band=True,
                        color=(255, 250, 236)))
    seen = set()
    for bt in beats:
        if bt.chapter not in seen and bt.chapter > 0:
            seen.add(bt.chapter)
            out.append(dict(text=ep["chapters"][bt.chapter]["title"], size=58,
                            t0=max(0.0, bt.start - 2.5), t1=bt.start + 6.0, x=90, y=H - 180))
        elif bt.chapter == 0:
            seen.add(0)
    return out


SHOT_TARGET = 7.0    # seconds: a shot is one sentence, two when they are short together
SHOT_LONGEST = 8.0   # two sentences longer than this together are two shots
SHOT_SHORT = 3.5     # a sentence shorter than this shares its shot with the next

# words that say WHO a sentence is about, so the shot is of them
WHO_WORDS = {
    "girl": r"\b(girls?|daughters?)\b",
    "child": r"\b(child|children|boys?|sons?|baby|little ones?|kids?)\b",
    "old_woman": r"\b(grandmother|old woman|grandma)\b",
    "elder": r"\b(old man|old men|elders?|grandfather|grey|gray)\b",
    "woman": r"\b(she|her|woman|women|mother|wife|sister|wives)\b",
    "man": r"\b(he|him|his|man|men|father|husband|brother|watchman|fisherman|keeper|guard)\b",
}
LIGHT_WORDS = r"\b(fire|flames?|lamps?|embers?|candles?|hearth|brazier|coals?|glow|wick|torch(?:es)?|light)\b"
MOVE_WORDS = r"\b(walks?|walking|carr(?:y|ies|ying)|cross(?:es|ing)?|pass(?:es|ing)?|heads?|hurr(?:y|ies)|" \
             r"returns?|comes?|goes|leaves?|strolls?|wanders?|makes? (?:his|her|their) way)\b"
TABLE_ACTIONS = ("eat", "drink", "talk", "sew")
INSERT_ZOOM = 1.6    # a close-up of the fire or the lamp AND whoever is at it: framed in, held still
FIRE_ACTIONS = ("warm_hands", "feed_fire", "stir", "sew", "eat", "drink", "talk", "hold")
SINGLE_ZOOM = 1.3    # a shot of one person: framed on them


def coverage(spec: dict, era: str, seed: int, dur: float = 6.0) -> dict:
    """Every shot this place and these people can give, each checked valid
    and with nothing drawn into anything: `est` (wide, everyone), `two`
    (close, everyone), `single:<i>` (close on one person, with the light and
    the furniture they are using), `insert` (close on the fire or the lamp
    and the person at it — never the light alone: the Greek film's 45
    lamp-on-an-empty-floor shots were a third of what the judge called
    "junk imagery", 2026-10-02), `pan` (the camera going with whoever is walking), `arr` (the
    same picture, arranged again)."""
    from data_learning.doodle import scene as S
    from data_learning.doodle.props import PROPS
    cast = [c for c in spec.get("cast") or [] if isinstance(c, dict)]
    names = [p if isinstance(p, str) else (p or {}).get("name") for p in spec.get("props") or []]
    lights = [n for n in names if n in PROPS and (PROPS[n].light or PROPS[n].living)]

    def clean(sp):
        sp = dict(sp)
        sp.pop("variant", None)
        return sp
    cands = {"est": (clean(dict(spec, shot="wide")), seed + 1),
             "two": (clean(dict(spec, shot="close")), seed + 2),
             "arr": (clean(dict(spec)), seed + 3)}
    for i, c in enumerate(cast):
        if c.get("pose") == "walk":
            cands["pan"] = (clean(dict(spec, shot="close", cast=[dict(c, pose="walk")], pan=True,
                                       pan_s=round(dur, 2))), seed + 9)
            continue
        keep = list(lights)
        if c.get("action") in TABLE_ACTIONS and "table" in names:
            keep.append("table")
        if c.get("pose") == "lie" and "bed" in names:
            keep.append("bed")
        cands[f"single:{i}"] = (clean(dict(spec, shot="close", cast=[c], props=keep)), seed + 11 + i)
    still = [c for c in cast if c.get("pose") != "walk"]
    if lights and still:
        at = next((c for c in still if c.get("action") in FIRE_ACTIONS), still[0])
        cands["insert"] = (clean(dict(spec, shot="close", cast=[at], props=lights[:2])), seed + 7)
    if S.SETTINGS.get(spec.get("setting")) is not None and S.SETTINGS[spec["setting"]].interior:
        cands.pop("est", None)          # a wide room is small people in an empty wall
    out = {}
    for name, (sp, sd) in cands.items():
        if S.validate(sp, era):
            continue
        lay = S.layout(sp, sd)
        if lay["collisions"]:
            continue
        # close-ups are FRAMED in on what they are of, and held still
        if name == "insert":
            p = next((q for q in lay["props"] if q["name"] in lights), None)
            if p is None or not lay["people"]:
                continue
            f = lay["people"][0]
            ph = PROPS[p["name"]].height * p["s"]
            # framed on the light and the person together, both inside
            span = abs(f["x"] - p["x"]) + 260.0
            k = round(max(1.0, min(INSERT_ZOOM, S.W / span)), 2)
            from data_learning.doodle import people as P
            R = P.R0 * f["s"] * P.WHO[f["who"]]["size"]
            # high enough that the head is never cut: the person's middle
            # and the flame, whichever is higher
            cy = min(p["y"] - ph * 0.6, f["y"] - 2.4 * R)
            sp = dict(sp, frame=[round((f["x"] + p["x"]) / 2, 1), round(cy, 1), k])
        elif name.startswith("single:") and lay["people"]:
            f = lay["people"][0]
            from data_learning.doodle import people as P
            R = P.R0 * f["s"] * P.WHO[f["who"]]["size"]
            fr = [round(f["x"] + (R if f["facing"] == "right" else -R), 1), round(f["y"] - 3.2 * R, 1), SINGLE_ZOOM]
            # framed in only if what moves stays in the picture: a close-up
            # that crops the flame out is a held frame (the Greek film's
            # painting held 47 identical frames and the gate blocked it)
            k = SINGLE_ZOOM
            x0 = min(max(fr[0] * k - S.W / 2, 0.0), (k - 1) * S.W) / k
            x1 = x0 + S.W / k
            if any(x0 + 40 < q["x"] < x1 - 40 for q in lay["props"] if q["name"] in lights) or \
                    S.SETTINGS[sp["setting"]].water:
                sp = dict(sp, frame=fr)
        out[name] = (sp, sd)
    return out


SHOT_SPLIT = 8.0     # a sentence longer than this is cut at a comma into two shots


def _clauses(ln):
    """A long sentence as clauses at its commas, timed by their words (the
    voice reads at an even pace within a sentence)."""
    t0, t1, sent = ln
    if t1 - t0 <= SHOT_SPLIT:
        return [ln]
    parts = [p.strip() for p in re.split(r"(?<=[,;:—])\s+", sent) if p.strip()]
    if len(parts) < 2:
        return [ln]
    n = sum(len(p.split()) for p in parts)
    # the comma nearest the middle, or the two nearest the thirds when long
    k = 3 if t1 - t0 > 2 * SHOT_SPLIT and len(parts) >= 3 else 2
    cum, acc = [], 0
    for p in parts[:-1]:
        acc += len(p.split())
        cum.append(acc / n)
    cuts = sorted({min(range(len(cum)), key=lambda i: abs(cum[i] - q / k)) for q in range(1, k)})
    out, prev = [], 0
    for c in cuts + [len(parts) - 1]:
        text = " ".join(parts[prev:c + 1])
        out.append(text)
        prev = c + 1
    res, t = [], t0
    for text in out:
        d = (t1 - t0) * len(text.split()) / n
        res.append((t, t + d, text))
        t += d
    return res


def _groups(lines: list, start: float, end: float) -> list[tuple[float, float, str]]:
    """The passage's sentences as shots: one sentence a shot, a long one cut
    at a comma, two together only when both are short."""
    lines = [c for ln in lines for c in _clauses(ln)]
    groups, cur = [], []
    for ln in lines:
        if cur:
            span = ln[1] - cur[0][0]
            if len(cur) >= 2 or (cur[-1][1] - cur[0][0]) >= SHOT_SHORT or span > SHOT_LONGEST:
                groups.append(cur)
                cur = []
        cur.append(ln)
    if cur:
        groups.append(cur)
    edges = [start] + [g[0][0] for g in groups[1:]] + [end]
    return [(edges[k], edges[k + 1], " ".join(x[2] for x in g)) for k, g in enumerate(groups)]


def _choose(opts: dict, text: str, last: str | None, first: bool, used: list) -> str:
    """The shot that shows what this sentence is about."""
    import re as _re
    low = text.lower()

    def ok(name):
        return name in opts and name != last
    if first and ok("est"):
        return "est"
    if _re.search(MOVE_WORDS, low) and ok("pan"):
        return "pan"
    # a sentence about two people is a shot of both of them
    # (counted by the nouns: "a child holds her hands out" is one person)
    nouns = _re.sub(r"\b(he|him|his|she|her)\b", " ", low)
    nouns = _re.sub(r"\b(old wom[ae]n|grandmother|grandma)\b", " gm ", nouns)
    named = {w for w, pat in WHO_WORDS.items() if _re.search(pat, nouns)}
    if "old_woman" in nouns or " gm " in nouns:
        named.add("old_woman")
    if len(named) >= 2:
        for name in ("two", "arr", "est"):
            if ok(name) and len(opts[name][0].get("cast") or []) >= 2:
                return name
    for who, pat in WHO_WORDS.items():
        if _re.search(pat, low):
            for name, (sp, _sd) in opts.items():
                if name.startswith("single:") and ok(name) and sp["cast"][0].get("who") == who:
                    return name
    if _re.search(LIGHT_WORDS, low) and ok("insert"):
        return "insert"
    order = ["two", "est"] + sorted(n for n in opts if n.startswith("single:")) + ["arr", "insert", "pan"]
    fresh = [n for n in order if ok(n) and n not in used[-3:]]
    if fresh:
        return fresh[0]
    rest = [n for n in order if ok(n)]
    return rest[0] if rest else next(iter(opts))


def shots(ep: dict, beats: list[Beat], paintings: dict | None = None) -> list[dict]:
    """The pictures the film shows: one shot a sentence, two when they are
    short together. The operator, 2026-10-02: "All of our scenes are too
    long ... they should be one, two sentences tops. You display the
    sentence that we're talking about, and then new scene to display the
    next couple sentences" — and "if we're gonna have somebody walking,
    have the scene pan and have them actually walk across it". So each
    shot is chosen by what its words are about: the place when a passage
    opens, whoever is walking (followed by the camera), the person the
    sentence names, the fire or lamp it names, and otherwise the next
    angle on the place that has not just been seen."""
    out = []
    paints = paintings or {}
    prev_setting = None
    for b in beats:
        seed = _scene_seed(ep["slug"], b.index, b.scene)
        lines = list(b.lines)
        start = b.start
        if b.index in paints and len(lines) > 1:
            # a passage with a painting opens on it for its first sentence
            cut = lines[1][0]
            out.append(dict(start=b.start, end=cut, scene=b.scene, seed=seed, painting=str(paints[b.index])))
            lines, start = lines[1:], cut
        groups = _groups(lines, start, b.end) if lines else [(start, b.end, b.text)]
        if len(groups) == 1:
            out.append(dict(start=groups[0][0], end=groups[0][1], scene=b.scene, seed=seed))
            prev_setting = (b.scene or {}).get("setting")
            continue
        opts = coverage(b.scene, ep["era"], seed, dur=max(g[1] - g[0] for g in groups))
        if not opts:
            out.append(dict(start=start, end=b.end, scene=b.scene, seed=seed))
            prev_setting = (b.scene or {}).get("setting")
            continue
        last, used = None, []
        for k, (t0, t1, text) in enumerate(groups):
            first = k == 0 and (b.scene or {}).get("setting") != prev_setting
            name = _choose(opts, text, last, first, used)
            sp, sd = opts[name]
            if name == "pan":
                sp = dict(sp, pan_s=round(t1 - t0 + XFADE, 2))
            out.append(dict(start=t0, end=t1, scene=sp, seed=sd, shot=name))
            last = name
            used.append(name)
        prev_setting = (b.scene or {}).get("setting")
    return out


def painting_files(ep: dict, beats: list[Beat]) -> dict:
    """{beat index: image path} for the passages the script gave a painting,
    fetched now; a painting that cannot be fetched is simply not shown."""
    from data_learning import ori_paintings as P
    flat = [b for c in ep["chapters"] for b in c["beats"]]
    out = {}
    for bt in beats:
        p = flat[bt.index].get("painting") if bt.index < len(flat) else None
        if isinstance(p, dict):
            path = P.fetch(p)
            if path is not None:
                out[bt.index] = path
    return out


def render_video(ep: dict, beats: list[Beat], out: Path, work: Path, workers: int) -> Path:
    bl = shots(ep, beats, painting_files(ep, beats))
    caps = _captions(ep, beats)
    n = len(bl)
    workers = max(1, min(workers, n))
    # contiguous chunks of roughly equal DURATION
    total = bl[-1]["end"]
    bounds = [0]
    for k in range(1, workers):
        target = total * k / workers
        j = next((i for i, b in enumerate(bl) if b["start"] >= target), n)
        if j > bounds[-1]:
            bounds.append(j)
    bounds.append(n)
    jobs = []
    for c, (lo, hi) in enumerate(zip(bounds, bounds[1:])):
        if hi > lo:
            jobs.append((dict(era=ep["era"], slug=ep["slug"]), bl, lo, hi,
                         str(work / f"chunk{c:03d}.mp4"), caps))
    with ProcessPoolExecutor(max_workers=len(jobs)) as ex:
        parts = list(ex.map(_render_chunk, jobs))
    lst = work / "chunks.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    vid = work / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(vid)], check=True)
    return vid


# ------------------------------------------------------------------ audio
def music_bed(total: float, work: Path, slug: str) -> Path | None:
    """The sleep tracks, shuffled per episode and chained end to end with
    long crossfades until they cover the whole film."""
    tracks = sorted(MUSIC.glob("*.mp3")) if MUSIC.is_dir() else []
    if not tracks:
        return None
    r = random.Random(slug)
    order = tracks[:]
    r.shuffle(order)
    durs = {}
    for tr in order:
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                             "csv=p=0", str(tr)], capture_output=True, text=True)
        durs[tr] = float(pr.stdout.strip() or 0)
    seq, acc = [], 0.0
    while acc < total + 10:
        for tr in order:
            if durs[tr] < 30:
                continue
            seq.append(tr)
            acc += durs[tr] - 8
            if acc >= total + 10:
                break
    inputs, filt = [], []
    for i, tr in enumerate(seq):
        inputs += ["-i", str(tr)]
    prev = "[0:a]"
    for i in range(1, len(seq)):
        lab = f"[m{i}]"
        filt.append(f"{prev}[{i}:a]acrossfade=d=8:c1=tri:c2=tri{lab}")
        prev = lab
    bed = work / "bed.wav"
    fc = ";".join(filt) + (";" if filt else "") + \
        f"{prev}atrim=0:{total:.2f},aresample=48000,loudnorm=I=-24:TP=-3,afade=t=out:st={max(0, total - 8):.2f}:d=8[bed]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
                    "-map", "[bed]", "-ac", "2", str(bed)], check=True)
    return bed


def mix(narration: Path, bed: Path | None, total: float, out: Path) -> Path:
    """Voice over a quiet bed. No ducking: a pumping bed is exactly the kind
    of change that wakes a listener, so the bed simply sits low throughout."""
    if bed is None:
        fc = f"[0:a]aresample=48000,apad,atrim=0:{total:.2f},loudnorm=I={LOUDNESS}:TP=-2[a]"
        ins = ["-i", str(narration)]
    else:
        fc = (f"[0:a]aresample=48000,apad,atrim=0:{total:.2f}[v];"
              f"[1:a]volume={MUSIC_GAIN:.3f}[m];"
              f"[v][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I={LOUDNESS}:TP=-2[a]")
        ins = ["-i", str(narration), "-i", str(bed)]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-map", "[a]",
                    "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    return out


# ------------------------------------------------------------------ outputs
def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(beats: list[Beat], out: Path) -> Path:
    rows, k = [], 1
    for b in beats:
        for (t0, t1, s) in b.lines:
            rows.append(f"{k}\n{_ts(t0)} --> {_ts(t1)}\n{s}\n")
            k += 1
    out.write_text("\n".join(rows))
    return out


def thumbnail(ep: dict, out: Path) -> Path:
    """A close doodle scene with the 2-4 words in big lettering, the way the
    channels he pointed at do it: one character mid-moment, a question."""
    import cairo
    from PIL import Image, ImageDraw, ImageFont
    from data_learning.doodle import scene as S
    sp = dict(ep["thumbnail_scene"])
    sp.setdefault("shot", "close")
    sc = S.Scene(sp, ep["era"], _scene_seed(ep["slug"], -1))
    # push in on the first person, the way those thumbnails fill the frame
    # with one face mid-moment
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    cr = cairo.Context(surf)
    figs = sc.lay["people"]
    if figs:
        f = figs[0]
        z = 1.35
        lights = [p for p in sc.lay["props"] if p["layer"] != "back"]
        fx = (f["x"] + lights[0]["x"]) / 2 if lights else f["x"]
        fy = f["y"] - 190 * f["s"]
        cx = min(max(fx, W / (2 * z)), W - W / (2 * z))
        cy = min(max(fy, H / (2 * z)), H - H / (2 * z))
        cr.translate(W / 2, H / 2)
        cr.scale(z, z)
        cr.translate(-cx, -cy)
    sc.draw(cr, 2.0)
    surf.flush()
    png = out.with_suffix(".thumb.png")
    surf.write_to_png(str(png))
    im = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(im)
    words = ep["thumbnail_text"].upper().split()
    lines = [" ".join(words)] if len(" ".join(words)) <= 14 else \
        [" ".join(words[:(len(words) + 1) // 2]), " ".join(words[(len(words) + 1) // 2:])]
    size = 190 if len(lines) == 1 else 160
    f = ImageFont.truetype(str(FONTS / "LuckiestGuy-Regular.ttf"), size)
    while max(d.textlength(ln, font=f) for ln in lines) > W * 0.62 and size > 90:
        size -= 8
        f = ImageFont.truetype(str(FONTS / "LuckiestGuy-Regular.ttf"), size)
    y = 70
    for ln in lines:
        d.text((80, y), ln, font=f, fill=(255, 214, 70), stroke_width=max(8, size // 14),
               stroke_fill=(24, 18, 20))
        y += int(size * 1.02)
    im.save(out, quality=92)
    png.unlink(missing_ok=True)
    return out


JUDGED = ((0.25, "start"), (0.55, "mid"), (0.85, "end"))   # the showrunner's samples of each chapter


def judged_lines(beats, chapters, duration: float) -> dict:
    """The words being spoken at each moment the showrunner looks at, keyed
    as it labels its frames (seg<i>:start|mid|end). Its directive asks
    whether each scene shows what the narration says AT THAT MOMENT, and it
    was given each chapter's opening line only — so the Elizabethan film's
    final chapter, which tours the sleeping city, was graded against "you
    watch the last candle pinched out" at a harbour and a riverbank whose
    own words said harbour and riverbank."""
    starts = [float(c["t"]) for c in chapters]
    out = {}
    for i, s0 in enumerate(starts):
        s1 = starts[i + 1] if i + 1 < len(starts) else duration
        for f, tag in JUDGED:
            t = s0 + f * (s1 - s0)
            b = None
            for x in beats:
                if x.start <= t:
                    b = x
                else:
                    break
            if b is not None:
                out[f"seg{i}:{tag}"] = sentences(b.text)[0][:160] if sentences(b.text) else b.text[:160]
    return out


def probe_duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def render(ep: dict, out: Path, *, max_seconds: float | None = None,
           workers: int | None = None, voice=None) -> dict:
    bad = validate(ep) if not max_seconds else [x for x in validate(ep) if "narrated words" not in x]
    if bad:
        raise ValueError(f"{ep.get('slug')}: invalid episode: {'; '.join(bad[:8])}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    workers = workers or max(1, (os.cpu_count() or 2))
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        print(f"[ori_sleep] narrating {ep['slug']} ...", flush=True)
        beats, voice_used = None, VOICE
        if voice is None:
            # ElevenLabs first (the operator's paid voice, shared/elevenlabs.py),
            # the WHOLE film or none of it: a line it cannot speak re-narrates
            # everything with Kokoro, so the voice never changes mid-film
            from shared import elevenlabs as EL
            lines = [x for ch in ep["chapters"] for b in ch["beats"] for x in sentences(b["say"])]
            if EL.available("curiosity") and EL.can_afford(lines):
                try:
                    beats = narrate(ep, work / "narration.wav", max_seconds=max_seconds,
                                    voice=None if workers > 1 else EL.Voice("curiosity"),
                                    workers=min(workers, EL_WORKERS),
                                    voice_factory=functools.partial(EL.Voice, "curiosity"))
                    voice_used = "elevenlabs:" + EL.voice_for("curiosity")["voice_id"]
                except Exception as e:           # noqa: BLE001 — any failure: the whole film on Kokoro
                    print(f"[ori_sleep] ElevenLabs could not narrate the film ({str(e)[:160]}); "
                          f"re-narrating it all with Kokoro", flush=True)
                    beats = None
        if beats is None:
            beats = narrate(ep, work / "narration.wav", max_seconds=max_seconds, voice=voice, workers=workers)
        print(f"[ori_sleep] voice: {voice_used}", flush=True)
        total = beats[-1].end
        print(f"[ori_sleep] {len(beats)} scenes, {total / 60:.1f} min — drawing with {workers} workers",
              flush=True)
        vid = render_video(ep, beats, out, work, workers)
        bed = music_bed(total, work, ep["slug"])
        aud = mix(work / "narration.wav", bed, total, work / "audio.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-i", str(aud), "-map", "0:v",
                        "-map", "1:a", "-c", "copy", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)
    srt(beats, out.with_suffix(".srt"))
    thumbnail(ep, out.with_suffix(".jpg"))
    chapters, seen = [], set()
    for b in beats:
        if b.chapter not in seen:
            seen.add(b.chapter)
            chapters.append({"t": round(b.start, 2), "label": ep["chapters"][b.chapter]["title"]})
    chapters[0]["t"] = 0.0
    duration = round(probe_duration(out), 2)
    meta = {"slug": ep["slug"], "title": ep["title"], "duration": duration,
            "chapters": chapters, "scenes": len(beats), "era": ep["era"],
            "moments": judged_lines(beats, chapters, duration),
            "words": sum(_words(b.text) for b in beats), "voice": voice_used,
            "music": sorted(p.name for p in MUSIC.glob("*.mp3")) if MUSIC.is_dir() else [],
            "sources": ep.get("sources") or []}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    meta = render(load(a.slug), Path(a.out), max_seconds=a.max_seconds, workers=a.workers)
    print(json.dumps({k: meta[k] for k in ("duration", "scenes", "words")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
