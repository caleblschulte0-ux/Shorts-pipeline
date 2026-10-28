"""A REAL song for a clip's emotional turn, one people know.

Operator, 2026-10-21, after the first tribute: *"it's not just tributes
... anytime we can do anything like that, whether it's a sad thing or a
happy thing or a tribute or whatever it is, we should do it"*. So the
shelf carries every mood a story's payoff can have — sad, hype, triumph,
funny — and `menu()` with no mood lists them all.

Operator, 2026-10-17, of Russell Westbrook talking about Kevin Durant:
*"We put some sad music over it. Not sad like your fucking Kevin McLeod,
whatever bullshit stock art sound we use, but like an actual like wistful
sad song people might recognize"*. The synthesised piano
(`third_capture/mood.py`) stays only as the fallback when no song can be
fetched.

`SONGS` is the shelf, by mood; the author picks one by its key
(`edit.song`) from the clip's own words. `get(key)` fetches its 30-second
store preview (the iTunes Search API, Deezer as the second source), the
part of the song people recognise, into cache/ (gitignored); nothing
binary is committed.

A recognisable song will often draw a Content ID claim on YouTube: the
claimant takes the ad money or, rarely, blocks the video in some
countries. It is not a channel strike, and the operator asked for real
songs knowing it. A song that gets a video BLOCKED comes off the shelf.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "cache" / "music" / "songs"
TIMEOUT_S = 20
MIN_S = 15.0               # a preview shorter than this is not the song

#: key -> the song, the mood it carries and when it fits. The author is
#: shown `fits` and picks by key; a key not here is no song.
SONGS: dict[str, dict] = {
    "see_you_again": {"artist": "Wiz Khalifa", "title": "See You Again",
                      "mood": "sad",
                      "fits": "a tribute: a teammate, friend or legend gone, "
                              "retired or moved on, looking back together"},
    "another_love": {"artist": "Tom Odell", "title": "Another Love",
                     "mood": "sad",
                     "fits": "heartbreak, a falling out, a bond that broke"},
    "the_night_we_met": {"artist": "Lord Huron", "title": "The Night We Met",
                         "mood": "sad",
                         "fits": "wishing it could go back to how it was"},
    "glimpse_of_us": {"artist": "Joji", "title": "Glimpse of Us",
                      "mood": "sad",
                      "fits": "missing someone, still thinking about them"},
    "let_her_go": {"artist": "Passenger", "title": "Let Her Go",
                   "mood": "sad",
                   "fits": "only knowing what you had once it is gone"},
    "fix_you": {"artist": "Coldplay", "title": "Fix You", "mood": "sad",
                "fits": "someone broken down, crying, a loss that hurts"},
    "memories": {"artist": "Maroon 5", "title": "Memories", "mood": "sad",
                 "fits": "a fond look back at the good days"},
    "somewhere_only_we_know": {"artist": "Keane",
                               "title": "Somewhere Only We Know",
                               "mood": "sad",
                               "fits": "nostalgia, an old place or old "
                                       "team, growing up"},
    "daylight": {"artist": "David Kushner", "title": "Daylight",
                 "mood": "sad",
                 "fits": "a dark, heavy moment, a downfall"},
    "too_good_at_goodbyes": {"artist": "Sam Smith",
                             "title": "Too Good at Goodbyes", "mood": "sad",
                             "fits": "a goodbye, a last game, leaving"},
    # hype: the trash talk, then the play that backs it up
    "till_i_collapse": {"artist": "Eminem", "title": "Till I Collapse",
                        "mood": "hype",
                        "fits": "a legend going off, a scoring run, "
                                "refusing to lose"},
    "remember_the_name": {"artist": "Fort Minor",
                          "title": "Remember the Name", "mood": "hype",
                          "fits": "a young player announcing himself, "
                                  "a breakout night"},
    "power": {"artist": "Kanye West", "title": "POWER", "mood": "hype",
              "fits": "pure dominance, a player bullying everyone"},
    "x_gon_give_it_to_ya": {"artist": "DMX",
                            "title": "X Gon' Give It to Ya", "mood": "hype",
                            "fits": "a dunk or a hit so violent it is "
                                    "disrespectful, trash talk paid off"},
    "humble": {"artist": "Kendrick Lamar", "title": "HUMBLE.",
               "mood": "hype",
               "fits": "someone talking big, then proving it, cold"},
    # triumph: the dream, then the moment it came true
    "hall_of_fame": {"artist": "The Script", "title": "Hall of Fame",
                     "mood": "triumph",
                     "fits": "a career honoured, a record, the hall of "
                             "fame"},
    "eye_of_the_tiger": {"artist": "Survivor", "title": "Eye of the Tiger",
                         "mood": "triumph",
                         "fits": "an underdog, a comeback from nothing"},
    "we_are_the_champions": {"artist": "Queen",
                             "title": "We Are the Champions",
                             "mood": "triumph",
                             "fits": "winning the title, the trophy, the "
                                     "parade"},
    "cant_hold_us": {"artist": "Macklemore & Ryan Lewis",
                     "title": "Can't Hold Us", "mood": "triumph",
                     "fits": "a joyful run, a team on fire, everyone "
                             "celebrating"},
    # funny: the story is that it went wrong
    "yakety_sax": {"artist": "Boots Randolph", "title": "Yakety Sax",
                   "mood": "funny",
                   "fits": "a blooper reel, chaos, everything going wrong"},
    "frolic": {"artist": "Luciano Michelini", "title": "Frolic",
               "mood": "funny",
               "fits": "an awkward moment, a player getting clowned, "
                       "Curb Your Enthusiasm energy"},
}

MOODS = ("sad", "hype", "triumph", "funny")


#: The analytics snapshots that say which uploads are blocked, each row
#: carrying the shelf songs it played (scripts/fetch_analytics.py).
ANALYTICS = [REPO / "state" / d / "latest.json"
             for d in ("analytics", "analytics_third")]


def blocked() -> set[str]:
    """Shelf songs that got one of OUR uploads blocked somewhere, or
    rejected. A claim that only takes the ad money leaves the video up and
    the song on the shelf; a block takes the video away, so that song is
    off the shelf for good (operator, 2026-10-28: "sometimes we get away
    with using songs that are copyrighted, but sometimes we don't")."""
    out: set[str] = set()
    for f in ANALYTICS:
        try:
            rows = json.loads(f.read_text()).get("videos") or []
        except (OSError, ValueError, AttributeError):
            continue
        for v in rows:
            if isinstance(v, dict) and (v.get("blocked_in")
                                        or v.get("rejection")):
                out.update(k for k in v.get("songs") or [] if k in SONGS)
    return out


def names(mood: str = "sad") -> list[str]:
    off = blocked()
    return [k for k, s in SONGS.items() if s["mood"] == mood
            and k not in off]


def menu(mood: str = "sad") -> str:
    """The shelf as prompt lines: `key: Title (Artist) - when it fits`;
    with mood "" every mood, each line tagged with its own."""
    keys = names(mood) if mood else [k for m in MOODS for k in names(m)]
    return "\n".join(f"    {k}: {SONGS[k]['title']} ({SONGS[k]['artist']})"
                     + ("" if mood else f" [{SONGS[k]['mood']}]")
                     + f" - {SONGS[k]['fits']}" for k in keys)


def clean(key) -> str:
    """The key if it is on the shelf, else ''. A song taken off the shelf
    for a block is swapped for the next one of its mood, so a story keeps
    its ending and loses only the song that got a video blocked."""
    k = re.sub(r"[^a-z0-9]+", "_", str(key or "").strip().lower()).strip("_")
    if k not in SONGS:
        return ""
    if k in blocked():
        left = names(SONGS[k]["mood"])
        return left[0] if left else ""
    return k


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _match(song: dict, title: str, artist: str) -> bool:
    """The store's track is this song: the title starts with ours (a
    "(feat. ...)" tail is fine) and the artist names ours."""
    t, a = _norm(title), _norm(artist)
    return t.startswith(_norm(song["title"])) and _norm(song["artist"]) in a


def itunes(song: dict) -> str | None:
    q = urllib.parse.urlencode({"term": f"{song['artist']} {song['title']}",
                                "media": "music", "entity": "song",
                                "limit": 10})
    for r in (_json(f"https://itunes.apple.com/search?{q}")
              .get("results") or []):
        if r.get("previewUrl") and _match(song, r.get("trackName", ""),
                                          r.get("artistName", "")):
            return r["previewUrl"]
    return None


def deezer(song: dict) -> str | None:
    q = urllib.parse.quote(f'artist:"{song["artist"]}" '
                           f'track:"{song["title"]}"')
    for r in (_json(f"https://api.deezer.com/search?q={q}")
              .get("data") or []):
        if r.get("preview") and _match(song, r.get("title", ""),
                                       (r.get("artist") or {}).get("name",
                                                                   "")):
            return r["preview"]
    return None


SOURCES = (itunes, deezer)


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "format=duration", "-of", "csv=p=0",
             str(path)], capture_output=True, text=True, timeout=30)
        return float((out.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def get(key: str) -> Path | None:
    """The song's preview as a WAV in cache/, fetched once, or None when
    the key is not on the shelf or no source handed over real audio.
    Never raises."""
    key = clean(key)
    if not key:
        return None
    out = CACHE / f"{key}.wav"
    if out.exists() and out.stat().st_size > 100_000:
        return out
    song = SONGS[key]
    CACHE.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        try:
            url = src(song)
            if not url:
                continue
            raw = CACHE / f"{key}.{src.__name__}.src"
            req = urllib.request.Request(url,
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                raw.write_bytes(r.read())
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                            "-ac", "2", "-ar", "44100", str(out)],
                           check=True, timeout=60, capture_output=True)
            raw.unlink(missing_ok=True)
            if _seconds(out) >= MIN_S:
                print(f"[songs] {song['title']} ({song['artist']}) via "
                      f"{src.__name__}", flush=True)
                return out
            out.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[songs] {key} via {src.__name__} failed "
                  f"({type(e).__name__})", flush=True)
    return None
