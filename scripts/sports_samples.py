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
PER_SUB = 2
MAX_SOURCE_S = 180

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

Skip: a plain highlight of a play with no human moment in it (a goal,
a dunk, a catch on its own), anything a viewer needs the game's context
to get, serious injuries, deaths, politics, gambling picks, and
anything sexual. Prefer footage that is NOT a league's TV broadcast
(fan-filmed, the athlete's own post, an interview, a podcast), because
league broadcasts get claimed; take a broadcast only when the human
moment is the whole point.

Return STRICT JSON:
{"picks": [{"i": int, "who": str, "why": str}, ...]}
`who` is the main person's name as fans search it (the athlete, coach
or team when no one person carries it), from the post title only.
`why` is one short sentence: what a stranger sees that makes them stay.
Best first. At most N picks, at most 2 from one subreddit."""

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
    "complete=false.")


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
        out.append(c)
    if not out:
        # no brain answered: the most upvoted, spread across subs
        for c in sorted(pool, key=lambda c: -c["upvotes"]):
            if per.get(c["sub"], 0) < 1:
                per[c["sub"]] = 1
                out.append({**c, "who": c["sub"], "why": "most upvoted"})
    return out[: n * 2]         # spares for downloads that fail


def fetch(c: dict, work: Path) -> dict | None:
    try:
        return clip_edit.download(c["url"], work, max_s=MAX_SOURCE_S)
    except Exception as e:  # noqa: BLE001
        print(f"[sports] yt-dlp refused {c['url']} ({type(e).__name__})",
              flush=True)
    if reddit_video.video_id(c.get("media", "")):
        stem = re.sub(r"\W+", "", c["media"])[-16:]
        return reddit_video.fetch(c["media"], work / f"rv_{stem}.mp4",
                                  title=c["post_title"], max_s=MAX_SOURCE_S)
    return None


def _dur(path: Path) -> float:
    try:
        return float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], text=True, timeout=30).strip())
    except Exception:  # noqa: BLE001
        return 0.0


def make(c: dict, info: dict, out_mp4: Path) -> dict:
    raw = Path(info["path"])
    words = clip_edit.transcribe_words(raw)
    dur = _dur(raw)
    meta = author.author_package(
        c["who"], c["post_title"], " ".join(w["w"] for w in words),
        c["upvotes"], words=words, clip_dur=dur, guidance=SPORTS_BRIEF)
    if meta and (meta.get("edit") or {}).get("complete") is False:
        return {"skipped": "author: no setup or no payoff in the clip",
                "meta": meta}
    hook = (meta or {}).get("hook") or c["post_title"][:60]
    led = clip_edit.edit(raw, out_mp4, credit=f"r/{c['sub']}", hook=hook,
                         words=words, series=(meta or {}).get("series",
                                                              "unknown"),
                         direct=(meta or {}).get("edit"))
    return {"meta": meta, "hook": hook,
            "ledger": {k: led.get(k) for k in ("duration", "moves", "mood",
                                               "shot_plan") if k in led}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sports")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--period", default="week")
    a = ap.parse_args()
    out = Path(a.out)
    work = out / "work"
    out.mkdir(parents=True, exist_ok=True)

    pool = discover(a.period)
    (out / "pool.json").write_text(json.dumps(pool, indent=1))
    if not pool:
        print("::error::no sports video posts reached the runner", flush=True)
        return 1
    picks = pick(pool, a.n)
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
