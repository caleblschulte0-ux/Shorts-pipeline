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
        [(i, p, look) for i, p in frames], title=title or look)


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
                if v["url"] not in seen:
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
                    start = max(0.0, dur * POINTS[i] - secs / 2)
                    clip = cut(video, start, secs,
                               work / f"foot_{tag}_{n}_cut.mp4")
                    if clip:
                        print(f"[footage] {who!r}: {v['title'][:60]!r} "
                              f"@{start:.1f}s", flush=True)
                        return {"path": str(clip), "url": v["url"],
                                "title": v["title"], "from_s": round(start, 1)}
        print(f"[footage] {who!r}: no footage showed {look!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[footage] {who!r} failed ({type(e).__name__})",
              flush=True)
    return None
