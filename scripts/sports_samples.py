#!/usr/bin/env python3
"""Sample videos for Baller Bro's new direction: SPORTS MOMENTS.

Operator, 2026-10-11, of the OG channel (registry `trending`, 439 posts
at ~3 views each): *"we need to turn that into something"*, then picked
"sports moments" — real people on camera, edited the way the Twitch
channel's clips are, instead of graph races.

This makes a handful of finished cuts for the operator to look at and
uploads NOTHING (no YouTube credentials reach the workflow that runs it).
The channel does not switch until the operator has seen them.

  1. what the internet upvoted this week on the sports subreddits
     (`funnel.hot_clips.top_videos`, the same routes as r/LivestreamFail)
  2. the brain picks the moments a stranger would watch: people, not
     plays (trash talk, a fan, a mic'd-up line, a reaction, a scuffle,
     a funny or emotional moment). Fan-filmed, athlete-posted and
     interview footage is preferred over a league's broadcast, which the
     leagues claim fast.
  3. each is downloaded (yt-dlp; a Reddit video falls back to v.redd.it
     through `funnel.reddit_video`), transcribed, authored by the Twitch
     channel's author with a sports brief, and cut by `clip_edit.edit`:
     the one line of text, the moves kit, the mood.

    python scripts/sports_samples.py --out sports --n 6
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from funnel import hot_clips, reddit_video  # noqa: E402
from third_capture import author, clip_edit  # noqa: E402

SUBS = ("sports", "nba", "nfl", "soccer", "MMA", "baseball", "hockey",
        "CollegeBasketball")
PER_SUB = 4
MAX_SOURCE_S = 180
#: The shortest post worth cutting. Operator, 2026-10-12, of four samples
#: that ran 5 to 14 seconds (each the WHOLE post, so the edit was not what
#: shortened them): "the clips are too short". A five-second highlight has
#: no setup and no reaction for the cut to keep.
MIN_SOURCE_S = 15.0

PICK_SYSTEM = """You run a sports Shorts channel called Baller Bro. Its
videos are MOMENTS WITH PEOPLE in them, cut like the big repost channels
cut Twitch clips: one line of text on screen, a zoom on the reaction.

You are given this week's most upvoted video posts from sports
subreddits: [i] r/sub, upvotes, platform, post title.

Pick the ones a stranger scrolling would stop for and watch to the end:
trash talk, a fan doing something wild, a mic'd-up line, a player's
reaction, a scuffle or a bench clearing, a celebration that goes wrong,
a funny interview or press conference answer, a kid meeting a hero, an
athlete posting something unexpected. The PERSON is the story.

STORIES FIRST (operator, 2026-10-21: "they're not tribute clips ...
They are stories ... anytime we can do anything like that, whether it's
a sad thing or a happy thing or a tribute or whatever it is, we should
do it"). Rank first the posts that are a STORY with something on the
field we can show after it: a player telling a story about a teammate,
a rival, a game or a record (Melo on LeBron saving him from drowning:
then LeBron and Melo playing together); a retirement, a farewell, a
tribute, a first game back, a parent watching their kid; the aftermath
of a big win or loss (a locker-room speech, a tearful postgame, a
celebration): then the win or the play that caused it. For each of
those, `story` names what the ending shows, the way a YouTube clip of it
is titled ("LeBron and Carmelo Team USA highlights"). Moments with no
story (a fan doing something wild, a funny quote) come after, `story`
"".

Skip: a plain highlight of a play with no human moment in it (a goal,
a dunk, a catch on its own), anything a viewer needs the game's context
to get, serious injuries, deaths, politics, gambling picks, and
anything sexual. Prefer footage that is NOT a league's TV broadcast
(fan-filmed, the athlete's own post, an interview, a podcast), because
league broadcasts get claimed; take a broadcast only when the human
moment is the whole point.

Return STRICT JSON:
{"picks": [{"i": int, "who": str, "why": str, "story": str}, ...]}
`who` is the main person's name as fans search it (the athlete, coach
or team when no one person carries it), from the post title only.
`why` is one short sentence: what a stranger sees that makes them stay.
NOT A RESTREAM: skip a post that is someone else's stream or video
REACTING to the moment (a streamer's webcam in the corner, a chat column,
a video playing inside a video, "X reacts to"): it is cropped wrong and the
viewer sees the reaction, not the moment. And skip a post whose point is a
reference a stranger would not get from the clip alone (operator, of a
reaction-stream Jaylen Brown clip: "What the fuck are they even talking
about?").

LENGTH: the post must run long enough to tell the moment, at least 15-20
seconds with the build-up and the reaction: an interview answer, a mic'd
up exchange, a podcast bit, a fan's whole encounter. A post that is only
the five seconds of the play itself is too short; skip it.

Best first. At most N picks, at most 4 from one subreddit."""

SPORTS_BRIEF = (
    "This is a SPORTS clip for the Baller Bro channel, not a Twitch clip. "
    "The 'streamer' is the athlete, coach or team named; the 'original "
    "clip title' is the Reddit post title, the internet's own take; the "
    "'Twitch views' are its upvotes. Write the title and the one line of "
    "text for sports fans: the person's name first, the human moment "
    "(not the score), honest. Hashtags lead with the athlete and team "
    "names and the league, and end with 'sports' (never streamerclips). "
    "A clip that is only a play with no person reacting gets "
    "complete=false. The cut OPENS on the moment or the line that sets it "
    "up, with the person clear in the shot: never on a wide shot, a walk "
    "up a tunnel or a crowd before anything happens (the judge blocked "
    "'opens on a distant walk-away' and 'a static wide shot where he is "
    "barely visible'). It ENDS after the payoff line has been said in "
    "full and the reaction to it, never in the middle of a sentence. When "
    "the footage never shows the moment the post title promises, "
    "complete=false. Keep at least 15 seconds, more when the build-up "
    "and the reaction are there (the operator: 'the clips are too short'): "
    "keep the setup before the moment and the reaction after it, never "
    "only the moment itself. complete=false when the clip is a "
    "streamer or YouTuber reacting to the moment (someone talking over "
    "it, chat being read) rather than the moment itself, or when a "
    "stranger could not tell from the clip what they are talking about. "
    "Make it OUR OWN video, not a lifted moment (the operator: 'maybe "
    "that clip can spark a couple more clips ... making something of our "
    "own'): whenever the person refers to something not on screen (the "
    "play, the game, the player they are calling out, an old teammate, "
    "the record), broll real footage of it at that second. When someone "
    "talks about something that happened that we can show (a teammate, "
    "a rival, a game, a record, a title, a choke, a blooper), give it the "
    "outro: the clip plays as it is, then a song in the story's mood "
    "(sad, hype, triumph or funny) over the footage of it.")


def _brain(user: str, system: str) -> dict | None:
    out = author._call_claude(user, system=system)
    if out is None:
        out = author._call_text_fallback(user, system=system, tag="sports")
    return out


def discover(period: str) -> list[dict]:
    pool = []
    for i, sub in enumerate(SUBS):
        got = []
        # The RSS route 429s quick reads, and one 429 marks the route dead
        # for the whole run (hot_clips._DEAD): the first samples got r/nfl's
        # 429 and then never asked r/soccer, r/MMA... at all. A rate limit
        # on one subreddit is not a dead route, so each sub gets it back,
        # after a pause, and one more try after a longer one.
        for wait in ((12 if i else 0), 30):
            time.sleep(wait)
            hot_clips._DEAD.discard("rss")
            got = hot_clips.top_videos(sub, period=period, limit=50)
            if got:
                break
        print(f"[sports] r/{sub}: {len(got)} video posts", flush=True)
        pool += got[:15]
    return pool


def pick(pool: list[dict], n: int) -> list[dict]:
    lines = [f"[{i}] r/{c['sub']} {c['upvotes']} {c['platform']} "
             f"{c['post_title']}" for i, c in enumerate(pool)]
    got = _brain(f"N = {n}\n\n" + "\n".join(lines), PICK_SYSTEM) or {}
    out, per = [], {}
    for p in got.get("picks") or []:
        try:
            c = dict(pool[int(p["i"])])
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if per.get(c["sub"], 0) >= PER_SUB or \
                any(o["url"] == c["url"] for o in out):
            continue
        per[c["sub"]] = per.get(c["sub"], 0) + 1
        c["who"] = str(p.get("who") or "").strip() or c["sub"]
        c["why"] = str(p.get("why") or "").strip()
        c["story"] = str(p.get("story") or "").strip()
        out.append(c)
    if not out:
        # no brain answered: the most upvoted, spread across subs
        for c in sorted(pool, key=lambda c: -c["upvotes"]):
            if per.get(c["sub"], 0) < 1:
                per[c["sub"]] = 1
                out.append({**c, "who": c["sub"], "why": "most upvoted"})
    return out[: n * 2]         # spares for downloads that fail


def found(query: str, who: str, n: int) -> list[dict]:
    """Candidates for `--find`: YouTube videos for `query` (any age, clip
    length), shaped like a Reddit pick, so one moment the operator names
    ("when Russ is talking about KD") can be cut as a sample."""
    from funnel import hot_clips
    # Reddit's own video posts first: v.redd.it serves them when YouTube
    # and the free converters refuse the runner (2026-10-21)
    reddit = [{"sub": r["sub"] or "reddit", "credit": f"r/{r['sub']}",
               "who": who or query, "why": "named by the operator",
               "post_title": r["post_title"], "upvotes": 0,
               "url": r["permalink"], "media": r["media"],
               "permalink": r["permalink"]}
              for r in hot_clips.reddit_videos(query, limit=25)
              # Reddit's search matches loosely ("Kobe 81 points" returned a
              # HistoryMemes post): the post must name who it is about
              if (who or query).split()[-1].lower() in r["post_title"].lower()
              ][:n]
    return reddit + [{"sub": "youtube", "credit": v.get("channel") or "YouTube",
             "who": who or query, "why": "named by the operator",
             "post_title": v["title"], "upvotes": 0, "url": v["url"],
             "permalink": v["url"]}
            for v in hot_clips.youtube(query, days=365 * 15, n=n,
                                       max_s=MAX_SOURCE_S)]


def fetch(c: dict, work: Path) -> dict | None:
    if c.get("sub") == "youtube":
        # yt-dlp is refused from GitHub's runners; the converters are not
        from funnel import find_footage
        stem = re.sub(r"\W+", "", c["url"])[-12:]
        p = find_footage.download(c["url"], work / f"yt_{stem}.mp4")
        return {"path": str(p), "title": c["post_title"]} if p else None
    try:
        return clip_edit.download(c["url"], work, max_s=MAX_SOURCE_S)
    except Exception as e:  # noqa: BLE001
        print(f"[sports] yt-dlp refused {c['url']} ({type(e).__name__})",
              flush=True)
    if "streamable.com" in c.get("media", ""):
        from funnel import find_footage
        stem = re.sub(r"\W+", "", c["media"])[-12:]
        p = find_footage.download(c["media"], work / f"st_{stem}.mp4")
        return {"path": str(p), "title": c["post_title"]} if p else None
    if reddit_video.video_id(c.get("media", "")):
        stem = re.sub(r"\W+", "", c["media"])[-16:]
        return reddit_video.fetch(c["media"], work / f"rv_{stem}.mp4",
                                  title=c["post_title"], max_s=MAX_SOURCE_S)
    return None


def too_short(info: dict) -> str:
    """Why a downloaded post is too short to cut, or ''."""
    secs = _dur(Path(info["path"]))
    if 0 < secs < MIN_SOURCE_S:
        return f"too short: the post runs {secs:.1f}s (< {MIN_SOURCE_S:.0f}s)"
    return ""


# 2026-10-13: a Mike Evans post ended on a Marin Health sponsor card, a
# coloured wipe then a logo held for two seconds; the editor cut it in and
# the gate held the render as a freeze. A post that ENDS on a still
# stretch has its tail cut off, wipe and all.
TAIL_FREEZE_S = 1.0     # a still this long that runs to the end is a card
CARD_LEAD_S = 0.6       # the wipe that brings a card in (measured: 0.3-0.4s)


def unfit(info: dict) -> str:
    """Make a downloaded post fit to cut, or say why it never can be.
    Trims a frozen card off its end (`info["path"]` becomes the trimmed
    file) and refuses a post with no sound: the cut is captioned from what
    is said, and whisper cannot open a file with no audio track at all
    (a Ruben Dias post died in the render that way, 2026-10-13)."""
    path = Path(info["path"])
    if not _has_audio(path):
        return "no sound: the post has no audio track"
    end = _card_starts(path)
    if end:
        trimmed = path.with_name(path.stem + ".nocard" + path.suffix)
        try:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-t",
                 f"{end:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "18", "-c:a", "aac", str(trimmed)],
                check=True, timeout=300)
            info["path"] = str(trimmed)
            info["trimmed_card_at"] = round(end, 2)
        except Exception:  # noqa: BLE001 — untrimmed still goes to the gate
            pass
    return ""


def _has_audio(path: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            text=True, timeout=30)
    except Exception:  # noqa: BLE001 — unprobed: let the render decide
        return True
    return bool(out.strip())


def _card_starts(path: Path) -> float:
    """Where a still card that runs to the end of the post begins, backed
    up past the wipe that brings it in, or 0.0 when the post has none. A
    wipe over half the frame scores too low for scene detection to find,
    so the lead is a fixed margin: at worst the cut loses half a second
    of the post's end, never shows a logo."""
    dur = _dur(path)
    if dur <= 0:
        return 0.0
    try:
        log = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(path), "-an", "-vf",
             f"freezedetect=n=0.003:d={TAIL_FREEZE_S}", "-f", "null", "-"],
            capture_output=True, text=True, timeout=300).stderr
    except Exception:  # noqa: BLE001
        return 0.0
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    if not starts:
        return 0.0
    at = starts[-1]
    if len(ends) >= len(starts) and ends[-1] < dur - 0.3:
        return 0.0              # the last still ended: the post moves again
    if at < dur * 0.5:
        return 0.0              # a long still post, not a card on its end
    return max(0.0, at - CARD_LEAD_S)


def _dur(path: Path) -> float:
    try:
        return float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], text=True, timeout=30).strip())
    except Exception:  # noqa: BLE001
        return 0.0


def make(c: dict, info: dict, out_mp4: Path, notes: str = "",
         line_top: bool = False) -> dict:
    """Author and cut one post. `notes` is a refused cut's verdict for the
    author to repair from; `line_top` puts our line at the top because
    the judge saw it over the footage's own graphic."""
    raw = Path(info["path"])
    words = clip_edit.transcribe_words(raw)
    dur = _dur(raw)
    story = (f"\n\nTHE STORY'S ENDING: the picker saw a story here whose "
             f"ending shows \"{c['story']}\". Give the outro for it unless "
             f"the clip itself says otherwise.") if c.get("story") else ""
    meta = author.author_package(
        c["who"], c["post_title"], " ".join(w["w"] for w in words),
        c["upvotes"], words=words, clip_dur=dur,
        guidance=SPORTS_BRIEF + story + (f"\n\n{notes}" if notes else ""))
    if meta and (meta.get("edit") or {}).get("complete") is False:
        return {"skipped": "author: no setup or no payoff in the clip",
                "meta": meta}
    hook = (meta or {}).get("hook") or c["post_title"][:60]
    led = clip_edit.edit(raw, out_mp4, credit=c.get("credit")
                         or f"r/{c['sub']}", hook=hook,
                         words=words, series=(meta or {}).get("series",
                                                              "unknown"),
                         direct=dict((meta or {}).get("edit") or {},
                                     **({"line": "top"} if line_top else {})))
    return {"meta": meta, "hook": hook,
            "ledger": {k: led.get(k) for k in ("duration", "moves", "mood",
                                               "shot_plan") if k in led}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sports")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--period", default="week")
    ap.add_argument("--find", default="",
                    help="cut a named moment from YouTube instead of Reddit")
    ap.add_argument("--who", default="")
    a = ap.parse_args()
    out = Path(a.out)
    work = out / "work"
    out.mkdir(parents=True, exist_ok=True)

    pool = (found(a.find, a.who, max(3, a.n * 2)) if a.find
            else discover(a.period))
    (out / "pool.json").write_text(json.dumps(pool, indent=1))
    if not pool:
        print("::error::no sports video posts reached the runner", flush=True)
        return 1
    picks = pool if a.find else pick(pool, a.n)
    index, made = [], 0
    for c in picks:
        if made >= a.n:
            break
        row = {k: c.get(k) for k in ("sub", "who", "why", "post_title",
                                     "upvotes", "url", "permalink")}
        info = fetch(c, work)
        if not info:
            row["skipped"] = "download failed"
            index.append(row)
            continue
        why = unfit(info) or too_short(info)
        if why:
            row["skipped"] = why
            index.append(row)
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", c["who"].lower()).strip("-")[:40]
        mp4 = out / f"{made + 1:02d}_{slug or 'clip'}.mp4"
        try:
            row.update(make(c, info, mp4))
        except Exception as e:  # noqa: BLE001
            row["skipped"] = f"render failed: {type(e).__name__}: {e}"[:300]
        if mp4.exists() and not row.get("skipped"):
            row["file"] = mp4.name
            made += 1
            m = row.get("meta") or {}
            print(f"[sports] made {mp4.name}: {m.get('title')!r} / "
                  f"{row.get('hook')!r}", flush=True)
        index.append(row)
    (out / "index.json").write_text(json.dumps(index, indent=1,
                                               default=str))
    print(f"[sports] {made} sample(s) of {len(picks)} picks", flush=True)
    for r in index:
        print(f"  {r.get('file') or 'SKIP'}  r/{r['sub']}  {r['who']}  "
              f"{r.get('skipped') or ''}", flush=True)
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
