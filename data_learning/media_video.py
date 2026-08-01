"""REAL MOVING B-ROLL, keylessly — the capability jump from slideshow to film.

A 9.5/10 documentary is carried by *motion*: real clips of real places and
people, not still photos with a drift. This gateway finds, scores, downloads and
normalizes actual VIDEO from two keyless sources:

  1. WIKIMEDIA COMMONS — modern CC/PD clips (cities, traffic, food, hands,
     machines). Full license metadata via the API.
  2. INTERNET ARCHIVE (Prelinger + stock collections) — public-domain archival
     film: money printing, factories, suburbs, shopping, 1940s-60s Americana.
     This is the exact texture professional money-docs cut to.

`best_video(query, work)` returns {"path", "source", "license", "attribution",
"title", "duration"} for the best playable clip, already transcoded to a clean
1920x1080 h264 intermediate, or None. All hits are cached per work dir.

Scoring: relevance (query terms in title/description) x quality (resolution,
duration fitness 4-90s, real motion probed on the downloaded file). A clip that
fails to decode is discarded — never trust a URL, trust ffprobe.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "CuriosityRenderer/1.0 (contact: openrange.interactive)"}
VIDEO_EXT = (".webm", ".ogv", ".mp4", ".mov", ".mpg", ".avi")


def _get(url: str, timeout: float = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url: str, timeout: float = 25):
    return json.loads(_get(url, timeout).decode("utf-8", "replace"))


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2}


def _relevance(query: str, text: str) -> float:
    qw = _words(query)
    if not qw:
        return 0.0
    tw = _words(text)
    return len(qw & tw) / len(qw)


# ---------------------------------------------------------------- Commons ----
def _commons_candidates(query: str, limit: int = 8) -> list[dict]:
    q = urllib.parse.quote(f"filetype:video {query}")
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           f"&list=search&srsearch={q}&srnamespace=6&srlimit={limit}")
    out = []
    try:
        for hit in _get_json(url)["query"]["search"]:
            title = hit["title"]
            if not title.lower().endswith(VIDEO_EXT):
                continue
            out.append({"provider": "commons", "title": title,
                        "snippet": re.sub(r"<[^>]+>", "", hit.get("snippet", "")),
                        "rel": _relevance(query, title + " " + hit.get("snippet", ""))})
    except Exception:  # noqa: BLE001 — a dead source is a ranking miss, not a crash
        pass
    return out


def _commons_resolve(cand: dict) -> dict | None:
    """File page -> direct URL + license via imageinfo/extmetadata."""
    t = urllib.parse.quote(cand["title"])
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           f"&titles={t}&prop=imageinfo&iiprop=url|size|extmetadata")
    try:
        pages = _get_json(url)["query"]["pages"]
        info = next(iter(pages.values()))["imageinfo"][0]
        meta = info.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", ""))
        return {**cand, "url": info["url"], "width": info.get("width", 0),
                "license": lic or "see Commons",
                "attribution": f"{cand['title'].replace('File:', '')} by {artist or 'unknown'} (Wikimedia Commons, {lic})"}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------- Internet Archive --
_IA_COLLECTIONS = "(prelinger OR fedflix OR stock_footage)"


def _ia_candidates(query: str, limit: int = 8) -> list[dict]:
    q = urllib.parse.quote(f"collection:{_IA_COLLECTIONS} AND mediatype:movies AND ({query})")
    url = ("https://archive.org/advancedsearch.php?q=" + q +
           "&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=description"
           f"&rows={limit}&output=json&sort%5B%5D=downloads+desc")
    out = []
    try:
        for doc in _get_json(url)["response"]["docs"]:
            desc = doc.get("description", "")
            desc = " ".join(desc) if isinstance(desc, list) else str(desc)
            out.append({"provider": "ia", "identifier": doc["identifier"],
                        "title": str(doc.get("title", doc["identifier"])),
                        "rel": _relevance(query, str(doc.get("title", "")) + " " + desc)})
    except Exception:  # noqa: BLE001
        pass
    return out


def _ia_resolve(cand: dict) -> dict | None:
    """Item metadata -> the smallest decent h264/mpeg derivative file URL."""
    try:
        meta = _get_json(f"https://archive.org/metadata/{cand['identifier']}")
        files = meta.get("files", [])
        best, best_score = None, -1.0
        for f in files:
            name = f.get("name", "")
            if not name.lower().endswith((".mp4", ".mpg", ".m4v")):
                continue
            size = float(f.get("size", 0) or 0)
            if size <= 0 or size > 250e6:
                continue
            width = float(f.get("width", 0) or 0)
            # RESOLUTION FIRST (the 320x240 "512kb" derivative looks mushy at
            # 1080p; the plain .mp4 is usually 640x480+), then modest size.
            score = width + (50 if name.lower().endswith(".mp4") else 0) \
                - size / 50e6
            if score > best_score:
                best, best_score = f, score
        if best and float(best.get("width", 0) or 0) < 560:
            return None                        # nothing sharp enough on this item
        if not best:
            return None
        return {**cand,
                "url": f"https://archive.org/download/{cand['identifier']}/" +
                       urllib.parse.quote(best['name']),
                "license": "Public Domain (Prelinger/IA)",
                "attribution": f"\"{cand['title']}\" (Internet Archive: {cand['identifier']}, public domain)"}
    except Exception:  # noqa: BLE001
        return None


# ----------------------------------------------------------------- probing ----
def _probe(path: Path) -> dict | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,duration:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        st = d["streams"][0]
        dur = float(st.get("duration") or d.get("format", {}).get("duration") or 0)
        return {"w": int(st.get("width", 0)), "h": int(st.get("height", 0)),
                "duration": dur}
    except Exception:  # noqa: BLE001
        return None


def _motion(path: Path, at: float, seconds: float = 2.0) -> float:
    """Mean inter-frame pixel delta over a short window — is anything moving?
    metadata=print writes at INFO level, so route it to a file (-v error would
    silently swallow it on stderr and read every clip as frozen)."""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            mpath = tf.name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.1f}", "-t", f"{seconds:.1f}",
             "-i", str(path), "-vf", "scale=96:54,tblend=all_mode=difference,"
             "crop=94:52:1:1,signalstats,"
             f"metadata=print:key=lavfi.signalstats.YAVG:file={mpath}",
             "-f", "null", "-"], capture_output=True, text=True, timeout=90)
        text = Path(mpath).read_text()
        Path(mpath).unlink(missing_ok=True)
        vals = [float(m) for m in re.findall(r"YAVG=([0-9.]+)", text)]
        return sum(vals) / len(vals) if vals else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


# -------------------------------------------------------------------- main ----
def best_video(query: str, work: Path, *, want_seconds: float = 6.0,
               min_rel: float = 0.34) -> dict | None:
    """Find, download and normalize the best real moving clip for `query`.
    Returns a dict with a local 1080p h264 `path` (whole source clip; the caller
    picks a window), or None when no acceptable clip exists (caller degrades to
    a photo — never silently to a text card)."""
    work.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "_", query.lower())[:60]
    cachetag = work / f"vid_{safe}.json"
    if cachetag.exists():
        cached = json.loads(cachetag.read_text())
        return cached if cached and Path(cached.get("path", "")).exists() else None

    import time
    cands = sorted(_commons_candidates(query) + _ia_candidates(query),
                   key=lambda c: -c["rel"])
    result = None
    for k, cand in enumerate(cands[:6]):
        if cand["rel"] < min_rel:
            break
        if k:
            time.sleep(2.0)          # stay under Commons' rate limit (429s)
        res = (_commons_resolve(cand) if cand["provider"] == "commons"
               else _ia_resolve(cand))
        if not res:
            continue
        raw = work / f"vidraw_{safe}{Path(urllib.parse.urlparse(res['url']).path).suffix.lower()}"
        try:
            print(f"[video] fetching {res['provider']}: {res['title'][:70]!r} rel={cand['rel']:.2f}")
            req = urllib.request.Request(res["url"], headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r_in, \
                    open(raw, "wb") as f_out:      # stream: no whole-file in RAM
                while chunk := r_in.read(1 << 20):
                    f_out.write(chunk)
        except Exception as e:  # noqa: BLE001
            print(f"[video]   download failed ({str(e)[:60]})")
            raw.unlink(missing_ok=True)
            continue
        info = _probe(raw)
        if not info or info["duration"] < want_seconds + 1 or info["w"] < 480:
            print(f"[video]   rejected: probe={info}")
            raw.unlink(missing_ok=True)
            continue
        mid_motion = _motion(raw, max(0.0, info["duration"] * 0.35))
        if mid_motion < 0.8:                      # effectively a frozen slate
            print(f"[video]   rejected: motion {mid_motion:.2f} too low")
            raw.unlink(missing_ok=True)
            continue
        norm = work / f"vid_{safe}.mp4"
        # normalize ONLY A WINDOW, never the whole source: a 6s cutaway does not
        # need a 30-minute archival reel transcoded (that blew the timeout and
        # ~600MB of disk per query). Long reels contribute a mid-film segment —
        # past the titles, where the actual footage lives.
        seg = min(info["duration"], max(75.0, want_seconds * 4))
        start = 0.0 if info["duration"] <= seg + 2 else \
            max(0.0, info["duration"] * 0.45 - seg / 2)
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.1f}",
             "-t", f"{seg:.1f}", "-i", str(raw),
             "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,"
                    "crop=1920:1080,fps=30", "-an",
             "-c:v", "libx264", "-preset", "fast", "-crf", "19", str(norm)],
            capture_output=True, timeout=600)
        raw.unlink(missing_ok=True)
        if r.returncode != 0 or not norm.exists():
            continue
        result = {"path": str(norm), "source": res["provider"],
                  "license": res["license"], "attribution": res["attribution"],
                  "title": res["title"], "duration": _probe(norm)["duration"],
                  "motion": round(mid_motion, 2)}
        break
    cachetag.write_text(json.dumps(result))
    if result:
        print(f"[video] LANDED {result['source']}: {result['title'][:60]!r} "
              f"{result['duration']:.0f}s motion={result['motion']}")
    return result


def pick_window(src: Path, seconds: float, out: Path, *, prefer: float = 0.4) -> Path:
    """Cut the most ALIVE `seconds` window from the normalized clip: probe motion
    at several offsets, take the liveliest, hard-cut (documentary, no dissolve)."""
    info = _probe(src) or {"duration": seconds}
    dur = max(info["duration"], seconds)
    offsets = [dur * f for f in (0.15, 0.35, 0.55, 0.75)]
    offsets = [o for o in offsets if o + seconds <= dur - 0.5] or [0.0]
    scored = [(o, _motion(src, o)) for o in offsets]
    at = max(scored, key=lambda t: t[1])[0] if scored else 0.0
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}",
         "-t", f"{seconds:.2f}", "-i", str(src),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-an", str(out)], check=True, timeout=300)
    return out


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "city traffic"
    r = best_video(q, Path("/tmp/vidtest"))
    print(json.dumps(r, indent=2))
