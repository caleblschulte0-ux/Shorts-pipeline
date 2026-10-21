"""A few seconds of REAL FOOTAGE of the people a clip talks about.

Operator, 2026-10-17, of Russell Westbrook talking about Kevin Durant:
*"show highlights of the two together, like stuff like that"*. When a
person on screen talks about someone or something that is not on screen
(an old teammate, the game everyone remembers, the night it happened),
the edit cuts to footage of it while the voice carries on: the b-roll a
human editor would lay in.

`find(who, look)` searches YouTube for highlights (the Data API, through
`funnel.hot_clips.youtube`, any age), downloads a candidate (yt-dlp, then
the public converters of `funnel.yt_convert` when YouTube refuses the
runner), and shows the brain one frame from a few points well inside it
(never the intro or the outro card). The first frame the brain says
DEPICTS `look` is where the cut is taken. With no brain to look, nothing
is cut in: unchecked footage of the wrong people is worse than none,
which is `funnel/find_image.py`'s rule too.

Copyrighted highlights are used briefly and transformatively (operator,
2026-10-09: *"we 100% can use copyrighted images. This is 100% fair
use"*); the cut is seconds long and carries none of the source's sound.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SECS = 3.2                 # on screen this long, per cut-in
MAX_S = 900                # a highlight reel, not a full game
YEARS = 25                 # how far back the search reaches
CANDIDATES = 3             # videos tried per request
POINTS = (0.22, 0.40, 0.58, 0.76)   # where in a video a frame is judged
MIN_SHOT = 1.6             # a shot shorter than this is a flash, not a cut-in
SCENE = 0.3                # ffmpeg scene score that counts as a new shot


#: What a cut-in must be: the GAME, not people talking about it (operator,
#: 2026-10-17, of a Russ-on-KD sample that cut to Stephen A at a news desk:
#: "there was no basketball clips in there. There was maybe one").
ACTION = ("real game footage of play on the court or field, the athletes "
          "playing; NOT a studio show, news desk, interview, podcast, press "
          "conference or someone talking to the camera")
#: A video whose title says it is talk is never downloaded.
TALK = re.compile(r"\b(react(s|ion|ing)?|podcast|interview|press conference|"
                  r"presser|breaking news|debate|first take|undisputed|"
                  r"analysis|explains?|talks?|says|speaks|rant|show)\b", re.I)


def is_talk(title: str) -> bool:
    return bool(TALK.search(str(title or "")))


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def queries(who: str, look: str) -> list[str]:
    """What is searched, most specific first."""
    qs = []
    for q in (f"{look} highlights" if look else "", f"{who} highlights"):
        q = re.sub(r"\s+", " ", q).strip()
        if q and q.lower() not in (x.lower() for x in qs):
            qs.append(q)
    return qs


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30)
        return float((out.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def _has_video(path: Path) -> bool:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             str(path)], capture_output=True, text=True, timeout=30)
        return "video" in (out.stdout or "")
    except Exception:  # noqa: BLE001
        return False


def download(url: str, out: Path) -> Path | None:
    """The video at `url` as an mp4, or None. yt-dlp first; YouTube
    refuses it from GitHub's runners, so the converters next."""
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["yt-dlp", "-q", "--no-playlist", "-f",
                        "bv*[height<=720][ext=mp4]+ba/b[height<=720]/b",
                        "--merge-output-format", "mp4", "-o", str(out), url],
                       capture_output=True, timeout=240)
        if out.exists() and _has_video(out):
            return out
    except Exception:  # noqa: BLE001
        pass
    try:
        from funnel import yt_convert
        got = yt_convert.fetch(url, out, max_s=MAX_S, budget_s=240)
        p = Path(got["path"]) if got and got.get("path") else None
        return p if p and p.exists() and _has_video(p) else None
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[footage] convert failed ({type(e).__name__})",
              flush=True)
        return None


def _frame(video: Path, at: float, out: Path) -> Path | None:
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}",
                        "-i", str(video), "-frames:v", "1", "-vf",
                        "scale=640:-2", str(out)],
                       check=True, capture_output=True, timeout=60)
        return out if out.exists() else None
    except Exception:  # noqa: BLE001
        return None


def judge(frames: list[tuple[int, Path]], look: str, title: str = ""
          ) -> dict[int, dict] | None:
    """The brain's per-frame verdict on whether it DEPICTS `look`, or None
    when no brain could look (shared.shot_relevance)."""
    from shared import shot_relevance
    return shot_relevance.judge_panels(
        [(i, p, f"{look} -- {ACTION}") for i, p in frames],
        title=title or look)


def shot_around(video: Path, at: float, span: float = 8.0) -> tuple[float, float]:
    """(start, end) of the SHOT that holds second `at`: a highlight reel
    cuts every second or two, and the first sample (2026-10-17) judged a
    frame of Westbrook and Durant and cut in Kobe Bryant from the next
    shot. Scene changes within `span` either side bound it."""
    lo = max(0.0, at - span)
    try:
        log = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", f"{lo:.2f}", "-t",
             f"{2 * span:.2f}", "-i", str(video), "-an", "-vf",
             f"scale=320:-2,select='gt(scene,{SCENE})',showinfo",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120).stderr
    except Exception:  # noqa: BLE001
        return at, at
    cuts = [lo + float(x) for x in re.findall(r"pts_time:([\d.]+)", log)]
    start = max([c for c in cuts if c <= at] or [lo])
    end = min([c for c in cuts if c > at] or [lo + 2 * span])
    return start, end


def cut(video: Path, start: float, secs: float, out: Path) -> Path | None:
    """`secs` of `video` from `start`, picture only, 30fps mp4."""
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}",
                        "-i", str(video), "-t", f"{secs:.2f}", "-an",
                        "-vf", "scale=-2:720,fps=30", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", str(out)],
                       check=True, capture_output=True, timeout=120)
        return out if _seconds(out) >= secs * 0.8 else None
    except Exception:  # noqa: BLE001
        return None


def find(who: str, look: str = "", *, secs: float = SECS,
         work: Path | str = ".", title: str = "") -> dict | None:
    """A CHECKED cut of footage showing `look` (who it is of: `who`):
    {"path", "url", "title", "from_s"}, or None. Never raises."""
    who = str(who or "").strip()
    look = str(look or "").strip() or who
    if not who:
        return None
    work = Path(work)
    tag = _norm(who)[:24] or "x"
    try:
        from funnel import hot_clips
        seen, cands = set(), []
        for q in queries(who, look):
            for v in hot_clips.youtube(q, days=365 * YEARS, n=CANDIDATES,
                                       max_s=MAX_S):
                if v["url"] not in seen and not is_talk(v.get("title")):
                    seen.add(v["url"])
                    cands.append(v)
        for n, v in enumerate(cands[:CANDIDATES]):
            video = download(v["url"], work / f"foot_{tag}_{n}.mp4")
            if not video:
                continue
            dur = _seconds(video)
            if dur < secs * 3:
                continue
            frames = []
            for i, f in enumerate(POINTS):
                p = _frame(video, dur * f, work / f"foot_{tag}_{n}_{i}.png")
                if p:
                    frames.append((i, p))
            verdicts = judge(frames, look, title) if frames else None
            if verdicts is None:
                print(f"[footage] {who!r}: no brain to check the footage — "
                      "nothing cut in", flush=True)
                return None
            for i, _p in frames:
                if (verdicts.get(i) or {}).get("depicts"):
                    at = dur * POINTS[i]
                    s0, s1 = shot_around(video, at)
                    if s1 - s0 < MIN_SHOT:
                        continue
                    # only the shot the brain saw, never the next one
                    start = min(max(s0 + 0.1, at - secs / 2),
                                max(s0 + 0.1, s1 - 0.1 - secs))
                    length = min(secs, s1 - 0.1 - start)
                    clip = cut(video, start, length,
                               work / f"foot_{tag}_{n}_cut.mp4")
                    if clip:
                        print(f"[footage] {who!r}: {v['title'][:60]!r} "
                              f"@{start:.1f}s", flush=True)
                        return {"path": str(clip), "url": v["url"],
                                "title": v["title"], "from_s": round(start, 1),
                                "secs": round(length, 2)}
        print(f"[footage] {who!r}: no footage showed {look!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[footage] {who!r} failed ({type(e).__name__})",
              flush=True)
    return None


#: Where a video is sampled when a MONTAGE wants several shots from it.
MANY_POINTS = (0.12, 0.2, 0.28, 0.36, 0.44, 0.52, 0.6, 0.68, 0.76, 0.84)


def find_many(who: str, look: str = "", *, n: int = 3, secs: float = SECS,
              work: Path | str = ".", title: str = "",
              skip: set | None = None) -> list[dict]:
    """Up to `n` CHECKED shots showing `look`, from as few videos as it
    takes: a highlight reel of two players holds a dozen shots of them,
    and the tribute montage wants several (operator, 2026-10-21, of a
    three-shot montage: *"need to be significantly more basketball clips
    ... especially clips of just them on the basketball court"*). Each
    shot is its own scene, none overlapping another; `skip` holds
    (url, second) keys already used. [] when none, or no brain. Never
    raises."""
    who = str(who or "").strip()
    look = str(look or "").strip() or who
    skip = skip if skip is not None else set()
    got: list[dict] = []
    if not who or n <= 0:
        return got
    work = Path(work)
    tag = _norm(look)[:24] or "x"
    try:
        from funnel import hot_clips
        seen, cands = set(), []
        for q in queries(who, look):
            for v in hot_clips.youtube(q, days=365 * YEARS, n=CANDIDATES,
                                       max_s=MAX_S):
                if v["url"] not in seen and not is_talk(v.get("title")):
                    seen.add(v["url"])
                    cands.append(v)
        for k, v in enumerate(cands[:CANDIDATES]):
            if len(got) >= n:
                break
            video = download(v["url"], work / f"many_{tag}_{k}.mp4")
            if not video:
                continue
            dur = _seconds(video)
            if dur < secs * 3:
                continue
            frames = [(i, p) for i, f in enumerate(MANY_POINTS)
                      if (p := _frame(video, dur * f,
                                      work / f"many_{tag}_{k}_{i}.png"))]
            verdicts = judge(frames, look, title) if frames else None
            if verdicts is None:
                print(f"[footage] {who!r}: no brain to check the footage — "
                      "no montage shots", flush=True)
                return got
            spans: list[tuple[float, float]] = []
            for i, _p in frames:
                if len(got) >= n:
                    break
                if not (verdicts.get(i) or {}).get("depicts"):
                    continue
                at = dur * MANY_POINTS[i]
                s0, s1 = shot_around(video, at)
                if s1 - s0 < MIN_SHOT or any(a < s1 and s0 < b
                                             for a, b in spans):
                    continue
                key = (v["url"], round(s0))
                if key in skip:
                    continue
                start = min(max(s0 + 0.1, at - secs / 2),
                            max(s0 + 0.1, s1 - 0.1 - secs))
                length = min(secs, s1 - 0.1 - start)
                clip = cut(video, start, length,
                           work / f"many_{tag}_{k}_{i}_cut.mp4")
                if clip:
                    spans.append((s0, s1))
                    skip.add(key)
                    got.append({"path": str(clip), "url": v["url"],
                                "title": v["title"],
                                "from_s": round(start, 1),
                                "secs": round(length, 2)})
                    print(f"[footage] {look!r}: {v['title'][:50]!r} "
                          f"@{start:.1f}s", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[footage] {look!r} failed ({type(e).__name__})",
              flush=True)
    return got
