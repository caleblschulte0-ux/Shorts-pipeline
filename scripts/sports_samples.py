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
celebration). But a moment that is complete on screen is a CLIP,
not a story (operator, 2026-10-22, of Verlander's daughter walking him
off and Josh Allen in tears: "that doesn't need to be a story. That's
just a singular clip"): `story` "" for those, they just play. A story
points at something bigger the clip never shows (a teammate who is gone,
a player who died, a broadcaster's decades in the booth). When in doubt,
it is a clip. For each STORY, `story` names what the ending shows:
the story's SUBJECT, the person or thing the moment is about, who is
often not the person on camera (Campbell giving the game ball to the
Lions' radio voice: "Dan Miller's famous Lions radio calls", never Lions
plays; whoever GIVES a ball, a
captaincy or an award, the subject is who RECEIVES it: Thornton naming
Celebrini captain is "Celebrini playing", never Thornton). Moments with no
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
    "the record), broll real footage of it at that second: it plays "
    "over their voice, then cuts back to them. Only a STORY gets the "
    "outro (the clip plays as it is, then a song over footage of what it "
    "is about): something bigger than the clip that it never shows. A "
    "moment complete on screen (a tearful postgame, a family moment, a "
    "celebration) is a clip: outro null. The cut OPENS on the moment: "
    "never skating, warming up, walking or the crowd before it (the "
    "operator: 'they skate around the ice for 30 seconds ... I would "
    "swipe away'). Never name a "
    "team, a city, a year or a fact the post title and the transcript do "
    "not say (a title once put Case Keenum's Bears locker room in Dallas).")


BROLL_SYSTEM = (
    "You find the cut-ins for a sports clip. Someone is talking; whenever "
    "they talk about something that happened somewhere else (the play, "
    "the hit they got fined for, the game, the shot, the player they call "
    "out, the old teammate, the record), we cut to real game footage of "
    "it for three seconds while their voice carries on, then back to "
    "them (the operator, 2026-10-28: \"that skattebo clip show the plays "
    "he got fined on\"). Their OWN plays count. Return STRICT JSON "
    "{\"broll\": [{\"who\": str, \"look\": str, \"at\": number, "
    "\"said\": str}]}: who = the players or teams as a search finds "
    "them; look = the GAME ACTION the footage must show, in search words "
    "(\"Cam Skattebo lowers helmet run Giants\"), never a press "
    "conference or interview; at = the second it is said, from the "
    "time-stamped transcript; said = the word or two of the transcript "
    "that name it there. 0-3, at least 4s apart. [] when the words name "
    "nothing showable; never a guess at what they do not name.")


def _fine_stamps(words: list[dict], n: int = 5) -> str:
    """The transcript in lines of `n` words, each with its start second:
    the author's lines run to eight seconds, wider than `cut_in.snap`
    looks for the word."""
    return "\n".join(
        f"[{float(words[i]['s']):.1f}] "
        + " ".join(str(w["w"]).strip() for w in words[i:i + n])
        for i in range(0, len(words), n))


def broll(c: dict, words: list[dict], dur: float, edit: dict) -> dict:
    """SHOW WHAT THE CLIP TALKS ABOUT. The author is asked for `broll`
    among a dozen other things and, on the 10-28 batch, gave none on any
    clip: Skattebo talked about the fines and the plays never appeared.
    A clip with words and no cut-in gets one question of its own."""
    if edit.get("broll") or not words:
        return edit
    from third_capture import cut_in
    user = (f"Who: {c.get('who')}\nThe post: {c.get('post_title')}\n"
            f"Transcript, each line with the second it starts:\n"
            f"{_fine_stamps(words)[:3000]}")
    try:
        got = cut_in.parse((_brain(user, BROLL_SYSTEM) or {}).get("broll"),
                           dur)
    except Exception as e:  # noqa: BLE001
        print(f"[cut-in] no answer on what to show ({e})", flush=True)
        got = []
    print(f"[cut-in] asked what the clip talks about: "
          f"{', '.join(g['look'] for g in got) or 'nothing showable'}",
          flush=True)
    if got:
        edit["broll"] = got
    return edit


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


# How long the clip itself may run before what follows it (operator,
# 2026-10-22: "they skate around the ice for 30 seconds ... I would swipe
# away, I wouldn't even get to make it to the tribute part. So shorten
# some of those beginning clips up"). A story's song and montage come
# after FRONT_MAX_S; a clip on its own runs at most CLIP_MAX_S. What goes
# is the START: the payoff and its reaction are at the end.
FRONT_MAX_S = 25.0
CLIP_MAX_S = 40.0
# a sentence start this far past the cap is still taken; one later than
# that would cut most of the clip away (a cheer with no words for 17s left
# Gaudreau's kids 8 seconds), so the cut starts at the cap instead
SNAP_S = 5.0


def trim_front(edit: dict, words: list[dict], dur: float) -> dict:
    """Move the cut's start forward until the clip fits its cap, onto the
    first sentence that begins within SNAP_S of it (a word after a pause
    or after . ? !), so it never opens mid-sentence. The end is never
    moved, and the clip keeps at least FRONT/CLIP_MAX_S - SNAP_S."""
    cut = edit.get("cut") or {"start": 0.0, "end": dur}
    lo, hi = float(cut.get("start") or 0.0), float(cut.get("end") or dur)
    cap = FRONT_MAX_S if edit.get("outro") else CLIP_MAX_S
    if hi - lo <= cap:
        return edit
    want = hi - cap
    starts = [w["s"] for i, w in enumerate(words or [])
              if want + 0.3 <= w["s"] <= want + SNAP_S
              and (i == 0 or w["s"] - words[i - 1]["e"] >= 0.5
                   or str(words[i - 1]["w"]).rstrip()[-1:] in ".?!")]
    new = max(lo, starts[0] - 0.3) if starts else want
    edit["cut"] = {"start": round(new, 2), "end": round(hi, 2)}
    return edit


TAIL_S = 8.0              # how far back from the end to look for a card
CARD_LOOK = ("the moment itself: people, players, coaches, a broadcast "
             "studio, the crowd, the game. NOT a network logo, a show's "
             "bumper or title card, a sponsor card, a graphic or an end "
             "screen")


def _cuts_in(raw: Path, lo: float, hi: float) -> list[float]:
    """Scene changes between lo and hi seconds of `raw`."""
    from funnel.find_footage import SCENE
    try:
        log = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", f"{lo:.2f}", "-t",
             f"{hi - lo:.2f}", "-i", str(raw), "-an", "-vf",
             f"scale=320:-2,select='gt(scene,{SCENE})',showinfo",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120).stderr
    except Exception:  # noqa: BLE001
        return []
    return sorted(lo + float(x) for x in re.findall(r"pts_time:([\d.]+)",
                                                    log))


def end_card(raw: Path, edit: dict, work: Path) -> dict:
    """The cut never ENDS on the broadcast's own card (operator,
    2026-10-28: "we won't play clips that don't make sense"; the sample
    of Charles Barkley and Shaq ran four seconds into ESPN's logo and the
    "Tip-Off presented by Lilly" bumper). Each shot in the last TAIL_S
    seconds is shown to the brain; the cut ends where the first one that
    is a logo, bumper or card begins. No brain: as it was."""
    from funnel import find_footage
    cut = edit.get("cut") or {}
    try:
        lo, hi = float(cut["start"]), float(cut["end"])
    except (KeyError, TypeError, ValueError):
        return edit
    starts = [t for t in _cuts_in(raw, max(lo, hi - TAIL_S), hi)
              if t - lo >= 10.0 and hi - t >= 0.5]
    if not starts:
        return edit
    work.mkdir(parents=True, exist_ok=True)
    panels = []
    for i, (a, b) in enumerate(zip(starts, starts[1:] + [hi])):
        fr = find_footage._frame(raw, (a + b) / 2, work / f"tail{i}.png")
        if fr:
            panels.append((i, fr))
    from shared import shot_relevance
    got = shot_relevance.judge_panels([(i, p, CARD_LOOK) for i, p in panels],
                                      title="the last seconds of a clip")
    if not got:
        return edit
    for i, a in enumerate(starts):
        if i in got and not got[i].get("depicts", True):
            print(f"[sports] the cut ran into a card at {a:.1f}s "
                  f"({got[i].get('why', '')[:80]}) — it ends there",
                  flush=True)
            edit["cut"] = {"start": round(lo, 2), "end": round(a - 0.05, 2)}
            break
    return edit


def make(c: dict, info: dict, out_mp4: Path, notes: str = "",
         line_top: bool = False, used_songs: list | None = None) -> dict:
    """Author and cut one post. `notes` is a refused cut's verdict for the
    author to repair from; `line_top` puts our line at the top because
    the judge saw it over the footage's own graphic."""
    raw = Path(info["path"])
    words = clip_edit.transcribe_words(raw)
    dur = _dur(raw)
    story = (f"\n\nTHE STORY'S ENDING: the picker saw a story here whose "
             f"ending shows \"{c['story']}\". Give the outro for it unless "
             f"the clip itself says otherwise.") if c.get("story") else ""
    if used_songs:
        story += ("\n\nSONGS ALREADY USED in this batch: "
                  + ", ".join(used_songs) + ". Pick another song that fits "
                  "this story's own mood; the same song on every video "
                  "makes the channel sound like one video.")
    meta = author.author_package(
        c["who"], c["post_title"], " ".join(w["w"] for w in words),
        c["upvotes"], words=words, clip_dur=dur,
        guidance=SPORTS_BRIEF + story + (f"\n\n{notes}" if notes else ""))
    if meta and (meta.get("edit") or {}).get("complete") is False:
        return {"skipped": "author: no setup or no payoff in the clip",
                "meta": meta}
    if meta and isinstance(meta.get("edit"), dict):
        trim_front(meta["edit"], words, dur)
        broll(c, words, dur, meta["edit"])
        end_card(raw, meta["edit"], out_mp4.parent / "work" / out_mp4.stem)
        # NO MUSIC UNDER THE CLIP (operator, 2026-10-28: "It played loud
        # music over the guy talking the whole time ... so annoying"). A
        # sports clip is someone talking; the sad song or hype beat the
        # author asks for keeps its look and loses its sound. A song plays
        # only AFTER the clip, over the montage (third_capture/outro.py).
        meta["edit"]["music"] = False
    o = ((meta or {}).get("edit") or {}).get("outro")
    if isinstance(o, dict):
        perm = str(c.get("permalink") or "")
        o["avoid"] = [x for x in (c.get("url"), c.get("media"), perm,
                                  re.sub(r"^https?://[^/]+", "", perm),
                                  c.get("post_title")) if x]
    hook = (meta or {}).get("hook") or c["post_title"][:60]
    led = clip_edit.edit(raw, out_mp4, credit=c.get("credit")
                         or f"r/{c['sub']}", hook=hook,
                         words=words, series=(meta or {}).get("series",
                                                              "unknown"),
                         direct=dict((meta or {}).get("edit") or {},
                                     **({"line": "top"} if line_top else {})))
    return {"meta": meta, "hook": hook,
            "ledger": {k: led.get(k) for k in ("duration", "moves", "mood",
                                               "shot_plan", "outro",
                                               "cut_in")
                       if k in led},
            "songs": songs_in(led)}


def songs_in(led: dict) -> list[str]:
    """Every shelf song a render plays, so a song that gets a video
    blocked can come off the shelf (funnel/songs.py `blocked`)."""
    out = [((led or {}).get("outro") or {}).get("song")]
    out += [re.sub(r".*\((\w+)\).*", r"\1", m) for m in
            (led or {}).get("moves") or [] if "(" in m and "silent" not in m]
    return [s for s in dict.fromkeys(out) if s]


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
    index, made, songs_used = [], 0, []
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
            row.update(make(c, info, mp4, used_songs=songs_used))
        except Exception as e:  # noqa: BLE001
            row["skipped"] = f"render failed: {type(e).__name__}: {e}"[:300]
        if mp4.exists() and not row.get("skipped"):
            row["file"] = mp4.name
            made += 1
            m = row.get("meta") or {}
            song = (((m.get("edit") or {}).get("outro") or {}).get("song")
                    or (m.get("edit") or {}).get("song"))
            if song and song not in songs_used:
                songs_used.append(song)
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
