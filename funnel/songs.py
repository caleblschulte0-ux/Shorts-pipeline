"""Music for a clip's emotional turn: an INSTRUMENTAL with the vibe, no
lyrics, nothing a Content ID match dings on sight.

Operator, 2026-10-29: *"start moving away from like popular songs and
just doing maybe songs with no lyrics that give the vibe that we want?
Don't go so far as to go into the Kevin McLeod, whatever, but like, we
don't need these getting instantly dinged."* Before that (2026-10-17) the
shelf was real hits from 30-second store previews, and some of them got
videos blocked.

So the shelf is VIBES, not songs: each key says when it fits and which
moods of the NoCopyrightSounds catalogue carry it. `get(key, seed)` picks
an NCS release that has an instrumental version and those moods, takes
its instrumental (modern, produced, made for creators, free on YouTube
with credit in the description), and cuts the loudest stretch of it. The
credit the licence asks for comes back with it (`credit`, and `used()`
for everything one render played).

`SONGS` keeps its name and shape (`title`, `artist`, `mood`, `fits`) so
the author's menu and every caller read it as before. A TRACK that gets
one of our videos blocked comes off the shelf by its id (`ncs:<tid>`).
The synthesised piano (`third_capture/mood.py`) stays the fallback when
nothing can be fetched.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "cache" / "music" / "songs"
TIMEOUT_S = 30
MIN_S = 15.0               # a cut shorter than this is not the song
SECTION_S = 45.0           # how much of a track a render gets
WINDOW_S = 30.0            # the loudest stretch it is cut around
LEAD_S = 6.0               # and how far before it the cut starts
PAGES = 12                 # catalogue pages read (about 20 tracks each)
CATALOGUE_DAYS = 7
SEARCH = "https://ncs.io/music-search?q=&genre=&mood=&version=instrumental"
DOWNLOAD = "https://ncs.io/track/download/i_{tid}"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like "
      "Gecko) Chrome/124 Safari/537.36")

#: key -> the vibe: `title` (what the author reads), `mood`, when it
#: `fits`, and the NCS `tags` (catalogue moods) that carry it. The author
#: picks by key; a key not here is no music.
def _vibe(title, mood, fits, tags):
    return {"title": title, "artist": "instrumental", "mood": mood,
            "fits": fits, "tags": tuple(tags)}


SONGS: dict[str, dict] = {
    "tribute": _vibe("Tribute", "sad",
                     "a tribute: a teammate, friend or legend gone, retired "
                     "or moved on, looking back together",
                     ("sentimental", "hopeful", "sad", "dreamy")),
    "heartbreak": _vibe("Heartbreak", "sad",
                        "someone broken down, crying, a loss that hurts",
                        ("sad", "gloomy", "sentimental")),
    "goodbye": _vibe("Goodbye", "sad",
                     "a goodbye, a last game, leaving",
                     ("sentimental", "floating", "sad", "hopeful")),
    "fond": _vibe("Fond look back", "sad",
                  "a fond look back at the good days, nostalgia",
                  ("dreamy", "laid back", "peaceful", "sentimental")),
    "missing": _vibe("Missing them", "sad",
                     "missing someone, wishing it could go back",
                     ("sad", "dreamy", "floating", "romantic")),
    "downfall": _vibe("Downfall", "sad",
                      "a dark, heavy moment, a downfall",
                      ("dark", "gloomy", "dramatic", "tense")),
    # hype: the trash talk, then the play that backs it up
    "going_off": _vibe("Going off", "hype",
                       "a legend going off, a scoring run, refusing to lose",
                       ("energetic", "powerful", "exciting")),
    "statement": _vibe("Statement", "hype",
                       "a young player announcing himself, talking big "
                       "then proving it",
                       ("powerful", "dramatic", "energetic")),
    "dominance": _vibe("Dominance", "hype",
                       "pure dominance, a hit or a dunk so violent it is "
                       "disrespectful",
                       ("heavy", "angry", "dark", "powerful")),
    "cold": _vibe("Cold", "hype",
                  "ice cold, a villain, trash talk paid off",
                  ("dark", "tense", "restless", "chasing")),
    # triumph: the dream, then the moment it came true
    "legacy": _vibe("Legacy", "triumph",
                    "a career honoured, a record, the hall of fame",
                    ("epic", "majestic", "powerful")),
    "underdog": _vibe("Underdog", "triumph",
                      "an underdog, a comeback from nothing",
                      ("hopeful", "euphoric", "exciting")),
    "champions": _vibe("Champions", "triumph",
                       "winning the title, the trophy, the parade",
                       ("euphoric", "epic", "happy", "exciting")),
    "joy": _vibe("Joy", "triumph",
                 "a joyful run, a team on fire, everyone celebrating",
                 ("happy", "euphoric", "energetic", "positive")),
    # funny: the story is that it went wrong
    "chaos": _vibe("Chaos", "funny",
                   "a blooper reel, chaos, everything going wrong",
                   ("funny", "quirky", "eccentric", "weird")),
    "awkward": _vibe("Awkward", "funny",
                     "an awkward moment, a player getting clowned",
                     ("quirky", "weird", "eccentric", "laid back")),
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
                out.update(k for k in v.get("songs") or []
                           if k in SONGS or str(k).startswith("ncs:"))
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


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return r.read()


def _attr(row: str, name: str) -> str:
    m = re.search(rf'data-{name}="([^"]*)"', row)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_catalogue(page: str) -> list[dict]:
    """The rows of one NCS search page: {tid, track, artist, genre,
    moods, slug}, only releases that have an instrumental version."""
    out = []
    for row in page.split("<tr")[1:]:
        tid = _attr(row, "tid")
        if not tid or "instrumental" not in _attr(row, "versions").lower():
            continue
        slug = re.search(r'<a href="/([^"/?]+)">', row)
        out.append({
            "tid": tid, "track": _attr(row, "track"),
            "artist": _attr(row, "artistraw"), "genre": _attr(row, "genre"),
            "moods": sorted({html.unescape(m).strip().lower() for m in
                             re.findall(r'href="/music-search\?mood=\d+">'
                                        r'([^<]+)</a>', row)}),
            "slug": slug.group(1) if slug else ""})
    return out


def catalogue() -> list[dict]:
    """Every NCS release with an instrumental, from the first PAGES search
    pages, cached for CATALOGUE_DAYS. [] when the site cannot be read."""
    f = CACHE / "ncs_catalogue.json"
    try:
        if time.time() - f.stat().st_mtime < CATALOGUE_DAYS * 86400:
            return json.loads(f.read_text())
    except (OSError, ValueError):
        pass
    rows, seen = [], set()
    for n in range(1, PAGES + 1):
        try:
            got = parse_catalogue(_get(f"{SEARCH}&page={n}")
                                  .decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[songs] NCS page {n}: {type(e).__name__}",
                  flush=True)
            break
        new = [r for r in got if r["tid"] not in seen]
        if not new:
            break
        seen.update(r["tid"] for r in new)
        rows += new
    if rows:
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rows))
    return rows


def candidates(key: str, seed: str = "", rows: list | None = None) -> list:
    """The tracks that carry this vibe, best first: the most of its tags,
    then an order the seed decides, so two videos of one vibe differ.
    Tracks that got a video blocked are not here."""
    tags = set(SONGS[key]["tags"])
    off = blocked()
    out = []
    for r in catalogue() if rows is None else rows:
        hit = len(tags & set(r.get("moods") or []))
        if hit and f"ncs:{r['tid']}" not in off:
            h = hashlib.md5(f"{seed}|{r['tid']}".encode()).hexdigest()
            out.append((-hit, h, r))
    return [r for *_, r in sorted(out, key=lambda x: x[:2])]


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "format=duration", "-of", "csv=p=0",
             str(path)], capture_output=True, text=True, timeout=30)
        return float((out.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def loudest(levels: list[float], window: int = int(WINDOW_S)) -> int:
    """The second the loudest `window` seconds start at (the drop, the
    chorus), from per-second RMS levels in dB."""
    if len(levels) <= window:
        return 0
    best, at = None, 0
    for i in range(len(levels) - window + 1):
        m = sum(levels[i:i + window]) / window
        if best is None or m > best:
            best, at = m, i
    return at


def _levels(path: Path) -> list[float]:
    try:
        log = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-af",
             "aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,"
             "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"], capture_output=True, text=True,
            timeout=120).stdout
    except Exception:  # noqa: BLE001
        return []
    out = []
    for v in re.findall(r"RMS_level=(\S+)", log):
        try:
            out.append(max(-90.0, float(v)))
        except ValueError:
            out.append(-90.0)
    return out


def credit(path) -> str:
    """The credit NCS asks for, for a file `get` returned, or ''."""
    try:
        t = json.loads(Path(str(path) + ".json").read_text())
    except (OSError, ValueError, TypeError):
        return ""
    return (f"Song: {t['artist']} - {t['track']}\n"
            "Music provided by NoCopyrightSounds\n"
            f"Free Download/Stream: https://ncs.io/{t['slug']}")


def track_id(path) -> str:
    """`ncs:<tid>` for a file `get` returned, or ''."""
    m = re.search(r"ncs_([0-9a-f-]{36})", str(path or ""))
    return f"ncs:{m.group(1)}" if m else ""


_USED: list[str] = []


def reset_used() -> None:
    _USED.clear()


def used() -> list[str]:
    """Every file `get` handed out since `reset_used`, in order."""
    return list(dict.fromkeys(_USED))


def get(key: str, seed: str = "") -> Path | None:
    """An instrumental for this vibe as a WAV in cache/, its loudest
    stretch, with its credit beside it; or None when the key is not on
    the shelf or nothing could be fetched. Never raises."""
    key = clean(key)
    if not key:
        return None
    try:
        tracks = candidates(key, seed)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[songs] {key}: no catalogue ({type(e).__name__})",
              flush=True)
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    for t in tracks[:4]:
        out = CACHE / f"ncs_{t['tid']}.wav"
        try:
            if not (out.exists() and out.stat().st_size > 100_000):
                raw = CACHE / f"ncs_{t['tid']}.mp3"
                raw.write_bytes(_get(DOWNLOAD.format(tid=t["tid"])))
                start = max(0, loudest(_levels(raw)) - LEAD_S)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss",
                                f"{start:.1f}", "-t", f"{SECTION_S:.1f}",
                                "-i", str(raw), "-ac", "2", "-ar", "44100",
                                str(out)], check=True, timeout=120,
                               capture_output=True)
                raw.unlink(missing_ok=True)
            if _seconds(out) < MIN_S:
                out.unlink(missing_ok=True)
                continue
            Path(str(out) + ".json").write_text(json.dumps(t))
            print(f"[songs] {key}: {t['artist']} - {t['track']} "
                  f"(instrumental, {', '.join(t['moods'])})", flush=True)
            _USED.append(str(out))
            return out
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[songs] {key}: {t.get('track')} failed "
                  f"({type(e).__name__})", flush=True)
    return None
