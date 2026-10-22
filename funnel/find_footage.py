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
                  r"analysis|explains?|talks?|says|speaks|rant|show|"
                  r"recalls?|opens? up|tells?|reveals?|remembers?|"
                  r"on why|story of|storytime)\b", re.I)


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
    if "v.redd.it" in str(url).lower():
        from funnel import reddit_video
        got = reddit_video.fetch(url, out, max_s=MAX_S)
        p = Path(got["path"]) if got and got.get("path") else None
        return p if p and p.exists() and _has_video(p) else None
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


def _frame(video: Path, at: float, out: Path, width: int = 640
           ) -> Path | None:
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}",
                        "-i", str(video), "-frames:v", "1", "-vf",
                        f"scale={width}:-2", str(out)],
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


def titled(title: str, words: list[str] | None) -> bool:
    """Every one of `words` is in `title` (case and punctuation aside)."""
    t = _norm(title)
    return all(_norm(w) in t for w in (words or []) if _norm(w))


#: Where a video is sampled when a MONTAGE wants several shots from it.
MANY_POINTS = tuple(round(0.1 + 0.05 * i, 2) for i in range(17))  # .1-.9
#: Reels tried per montage look: the rule "both of them, as teammates"
#: refuses most frames of most reels.
MANY_CANDIDATES = 5
SAME_PICTURE = 14          # mean grey difference (0-255) under which two
                           # shots are the same picture: Keenum's montage was
                           # one pre-snap line-up three times (2026-10-22)


def _thumb(png) -> bytes:
    """A 16x16 grey thumbnail of a frame, b"" when it cannot be read."""
    try:
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(png), "-vf",
             "scale=16:16,format=gray", "-f", "rawvideo", "-"],
            capture_output=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return b""


def same_picture(a: bytes, b: bytes) -> bool:
    return bool(a) and len(a) == len(b) and \
        sum(abs(x - y) for x, y in zip(a, b)) / len(a) < SAME_PICTURE


def find_many(who: str, look: str = "", *, n: int = 3, secs: float = SECS,
              work: Path | str = ".", title: str = "",
              skip: set | None = None,
              title_has: list[str] | None = None,
              max_s: int = MAX_S, per_video: int = 0,
              title_not: re.Pattern | None = None,
              query: str = "", avoid: set | None = None) -> list[dict]:
    """Up to `n` CHECKED shots showing `look`, from as few videos as it
    takes: a highlight reel of two players holds a dozen shots of them,
    and the tribute montage wants several (operator, 2026-10-21, of a
    three-shot montage: *"need to be significantly more basketball clips
    ... especially clips of just them on the basketball court"*). Each
    shot is its own scene, none overlapping another; `skip` holds
    (url, second) keys already used; `title_has` names words every
    candidate's title must hold (each person's surname, so a reel of one
    of them alone is never downloaded); `max_s` caps a candidate's
    length and `per_video` (0: no cap) how many shots one video gives, so
    a montage can be made of short clips of one play each instead of a
    fan reel's wide shots and cutaways; a title matching `title_not` is
    skipped. `query` is what YouTube is searched for when `look` (what
    the brain must see) is a sentence of rules — searching with the rules
    themselves returned one wrong video per search all of 2026-10-21.
    `avoid` holds the urls and the title of the clip being told: it is
    never its own montage. [] when none, or no brain. Never raises."""
    who = str(who or "").strip()
    look = str(look or "").strip() or who
    skip = skip if skip is not None else set()
    avoid = {a for a in (avoid or set()) if a}
    avoid_t = {_norm(a) for a in avoid}
    got: list[dict] = []
    if not who or n <= 0:
        return got
    work = Path(work)
    tag = _norm(look)[:24] or "x"
    thumbs: list[bytes] = []
    try:
        from funnel import hot_clips
        seen, cands = set(), []
        for q in queries(who, query or look):
            # YouTube first: a career's highlights live there, where
            # Reddit's search holds this month's posts (2026-10-22: a
            # "career highlights" montage cut from the clip being told).
            # Then Reddit's own video posts, short clips of one play that
            # v.redd.it serves when YouTube refuses the runner. Reddit's
            # search ANDs loosely and "highlights" is not how its posts are
            # titled: the words that name the play, without it
            found = hot_clips.youtube(q, days=365 * YEARS,
                                      n=MANY_CANDIDATES, max_s=max_s)
            rq = re.sub(r"\s*\bhighlights?\b", "", q, flags=re.I).strip()
            found += [{"url": r["media"], "title": r["post_title"],
                       "permalink": r.get("permalink", "")}
                      for r in hot_clips.reddit_videos(rq, limit=25)]
            for v in found:
                if v["url"] in avoid or v.get("permalink") in avoid \
                        or _norm(v.get("title") or "") in avoid_t:
                    continue
                if v["url"] not in seen and not is_talk(v.get("title")) \
                        and titled(v.get("title"), title_has) \
                        and not (title_not and title_not.search(
                            v.get("title") or "")):
                    seen.add(v["url"])
                    cands.append(v)
        print(f"[footage] {(query or look)[:50]!r}: {len(cands)} "
              "candidate(s)",
              flush=True)
        for k, v in enumerate(cands[:MANY_CANDIDATES * 2]):
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
                                      work / f"many_{tag}_{k}_{i}.png",
                                      width=1280))]   # numbers readable
            verdicts = judge(frames, look, title) if frames else None
            if verdicts is None:
                print(f"[footage] {who!r}: no brain to check the footage — "
                      "no montage shots", flush=True)
                return got
            yes = sum(bool((verdicts.get(i) or {}).get("depicts"))
                      for i, _p in frames)
            print(f"[footage] {v['title'][:60]!r} ({dur:.0f}s): {yes}/"
                  f"{len(frames)} frames show it", flush=True)
            spans: list[tuple[float, float]] = []
            for i, _p in frames:
                if len(got) >= n or (per_video and len(spans) >= per_video):
                    break
                if not (verdicts.get(i) or {}).get("depicts"):
                    continue
                th = _thumb(_p)
                if any(same_picture(th, t) for t in thumbs):
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
                    thumbs.append(th)
                    skip.add(key)
                    got.append({"path": str(clip), "url": v["url"],
                                "title": v["title"],
                                "from_s": round(start, 1),
                                "secs": round(length, 2),
                                # where the shot came from, so a caller can
                                # let it play on (outro.play_out)
                                "source": str(video),
                                "source_s": round(dur, 1),
                                "shot_end": round(s1 - 0.1, 2)})
                    print(f"[footage] {look!r}: {v['title'][:50]!r} "
                          f"@{start:.1f}s", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[footage] {look!r} failed ({type(e).__name__})",
              flush=True)
    return got
