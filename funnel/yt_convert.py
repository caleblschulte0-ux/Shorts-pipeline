"""A YouTube video when yt-dlp is refused — the converter route.

YouTube refuses yt-dlp from GitHub's servers ("sign in to confirm you're
not a bot"), so every YouTube source a story needed died at download:
backtest 21 found four of Reggie's videos for the Kai Cenat feud and could
fetch none of them. Operator, 2026-10-11: *"put those YouTube videos in a
fucking YouTube converter ... it's just a small part of a story that we're
putting together"* — a fair-use excerpt, cut to seconds in the story.

`fetch(url, out)` asks the public converters, one after another, for a
file of the video and saves it to `out`:

  1. loader.to   (the free converter site: ``/ajax/download.php`` starts
                  a 720p mp4, its ``progress_url`` hands back the file —
                  the one that answered from GitHub on 2026-10-11, when
                  every route below refused or was down)
  2. Piped       (``/streams/<id>`` — a combined audio+video stream)
  3. Invidious   (``/latest_version?itag=18&local=true`` — 360p mp4,
                  proxied through the instance)
  4. cobalt      (``POST /`` — a tunnel or redirect URL)

Instances come from each project's public instance list, with a few known
hosts behind it. Every one is a stranger's server that can be down, so a
host that fails is skipped for the rest of the run (`_DEAD`), the whole
search has a time budget, and the file is only accepted once ffprobe reads
a real video with sound from it. Returns the clip's meta like
`clip_edit.download`, or None — never raises.

Shared capability (any channel that needs "this YouTube video"), so it
lives in funnel/, not in a channel.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 30
BUDGET_S = 360          # all converters together, per video
MAX_BYTES = 400 << 20
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

LOADER = ["https://loader.to"]
LOADER_WAIT_S = 180     # it converts before it hands the file over
PIPED = ["https://pipedapi.kavin.rocks", "https://pipedapi.adminforge.de",
         "https://api.piped.private.coffee", "https://pipedapi.r4fo.com"]
INVIDIOUS = ["https://inv.nadeko.net", "https://invidious.nerdvpn.de",
             "https://yewtu.be", "https://invidious.f5.si"]
COBALT: list[str] = []
INVIDIOUS_LIST = "https://api.invidious.io/instances.json?sort_by=health"
COBALT_LIST = "https://instances.cobalt.best/api/instances.json"

_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/|/live/)"
                 r"([A-Za-z0-9_-]{11})")
_DEAD: set[str] = set()
_HOSTS: dict[str, list[str]] = {}


def video_id(url: str) -> str | None:
    """The 11-character id of a YouTube URL, or None for anything else."""
    if not re.search(r"(?:^|\.|//)(youtube\.com|youtu\.be)/", url or ""):
        return None
    m = _ID.search(url)
    return m.group(1) if m else None


def _open(url: str, *, data: bytes | None = None, headers: dict | None = None,
          timeout: float = TIMEOUT):
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def _json(url: str, **kw) -> dict | list:
    with _open(url, **kw) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _hosts(kind: str) -> list[str]:
    """Live instances first (from the project's own list), then the known
    ones; fetched once per run."""
    if kind in _HOSTS:
        return _HOSTS[kind]
    found: list[str] = []
    try:
        if kind == "invidious":
            for _name, i in _json(INVIDIOUS_LIST):
                if i.get("type") == "https" and i.get("api") and i.get("uri"):
                    found.append(i["uri"].rstrip("/"))
            found = found[:6]
        elif kind == "cobalt":
            for i in _json(COBALT_LIST):
                svc = i.get("services") or {}
                if i.get("online") and svc.get("youtube") is True and i.get("api"):
                    api = str(i["api"]).rstrip("/")
                    found.append(api if api.startswith("http") else "https://" + api)
            found = found[:6]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[yt_convert] {kind} instance list "
              f"({type(e).__name__})", flush=True)
    known = {"loader": LOADER, "piped": PIPED, "invidious": INVIDIOUS, "cobalt": COBALT}[kind]
    _HOSTS[kind] = list(dict.fromkeys(found + known))
    return _HOSTS[kind]


# ---- each converter: (media url, headers for it, meta) or None -----------

def _loader(host: str, vid: str):
    watch = urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}",
                               safe="")
    j = _json(f"{host}/ajax/download.php?format=720&url={watch}")
    if not j.get("success"):
        print(f"::warning::[yt_convert] loader {vid}: refused "
              f"({str(j)[:160]})", flush=True)
        return None
    # the site's own progress.php reports "Finished" with the file while
    # the progress_url it hands out can sit at 50% (seen 2026-10-11)
    polls = [u for u in (f"{host}/ajax/progress.php?id={j.get('id', '')}"
                         if j.get("id") else None, j.get("progress_url")) if u]
    meta = {"title": (j.get("info") or {}).get("title") or j.get("title") or ""}
    t0 = time.monotonic()
    while polls and time.monotonic() - t0 < LOADER_WAIT_S:
        for poll in polls:
            try:
                p = _json(poll)
            except Exception:  # noqa: BLE001 — the other poll may answer
                continue
            if p.get("download_url"):
                print(f"[yt_convert] loader {vid}: {str(p)[:200]}", flush=True)
                return p["download_url"], {}, meta
            if str(p.get("text", "")).lower().startswith("error"):
                print(f"::warning::[yt_convert] loader {vid}: "
                      f"{str(p)[:160]}", flush=True)
                return None
        time.sleep(3)
    print(f"::warning::[yt_convert] loader {vid}: not ready after "
          f"{LOADER_WAIT_S}s", flush=True)
    return None


def _piped(host: str, vid: str):
    j = _json(f"{host}/streams/{vid}")
    both = [s for s in j.get("videoStreams") or []
            if not s.get("videoOnly") and s.get("url")]
    if not both:
        return None
    both.sort(key=lambda s: -(int(s.get("height") or 0)))
    pick = next((s for s in both if int(s.get("height") or 0) <= 720), both[-1])
    return pick["url"], {}, {"title": j.get("title") or "",
                             "uploader": j.get("uploader") or "",
                             "views": j.get("views") or 0,
                             "duration": j.get("duration") or 0}


def _invidious(host: str, vid: str):
    meta = {}
    try:
        m = _json(f"{host}/api/v1/videos/{vid}"
                  "?fields=title,author,lengthSeconds,viewCount")
        meta = {"title": m.get("title") or "", "uploader": m.get("author") or "",
                "views": m.get("viewCount") or 0,
                "duration": m.get("lengthSeconds") or 0}
    except Exception:  # noqa: BLE001 — the file is what matters
        pass
    return f"{host}/latest_version?id={vid}&itag=18&local=true", {}, meta


def _cobalt(host: str, vid: str):
    body = json.dumps({"url": f"https://www.youtube.com/watch?v={vid}",
                       "videoQuality": "720", "downloadMode": "auto",
                       "youtubeVideoCodec": "h264"}).encode()
    j = _json(host + "/", data=body, headers={
        "Accept": "application/json", "Content-Type": "application/json"})
    if j.get("status") in ("tunnel", "redirect", "stream") and j.get("url"):
        return j["url"], {}, {}
    if j.get("status") == "picker":
        for p in j.get("picker") or []:
            if p.get("type") == "video" and p.get("url"):
                return p["url"], {}, {}
    return None


ROUTES = (("loader", _loader), ("piped", _piped), ("invidious", _invidious), ("cobalt", _cobalt))


def _api_meta(vid: str) -> dict:
    """Title and channel from the YouTube Data API (a cobalt answer carries
    none); {} without YOUTUBE_API_KEY."""
    try:
        from funnel import hot_clips
        it = (hot_clips._yt({"_api": "videos", "part": "snippet,statistics",
                             "id": vid}).get("items") or [{}])[0]
        sn = it.get("snippet") or {}
        return {"title": sn.get("title") or "",
                "uploader": sn.get("channelTitle") or "",
                "views": int((it.get("statistics") or {}).get("viewCount") or 0)}
    except Exception:  # noqa: BLE001
        return {}


def _probe(path: Path) -> float:
    """Seconds of real video WITH sound in `path`, else 0."""
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type:format=duration", "-of", "json", str(path)],
            text=True, timeout=30)
        j = json.loads(out)
        kinds = {s.get("codec_type") for s in j.get("streams") or []}
        if not {"video", "audio"} <= kinds:
            return 0.0
        return float((j.get("format") or {}).get("duration") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


_REDIRECT = re.compile(
    rb"""(?:http-equiv=["']?refresh["']?[^>]*content=["'][^"']*?url=|"""
    rb"""location(?:\.href)?\s*=\s*|location\.replace\(\s*)"""
    rb"""["']?([^"'\s>)]+)""", re.I)


def _save(media_url: str, headers: dict, out: Path, hops: int = 2) -> bool:
    tmp = out.with_suffix(out.suffix + ".part")
    n = 0
    with _open(media_url, headers=headers, timeout=90) as r, \
            open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            n += len(b)
            if n > MAX_BYTES:
                raise ValueError("too large")
            f.write(b)
    if n < 50_000:
        body = tmp.read_bytes() if tmp.exists() else b""
        tmp.unlink(missing_ok=True)
        # a converter's file host can answer with a "Redirect" page that
        # sends a browser on to the real file (loader.to, 2026-10-21)
        m = _REDIRECT.search(body)
        print(f"[yt_convert] {media_url[:90]} answered a page: {body[:1200]!r}",
              flush=True)
        if m and hops:
            nxt = urllib.parse.urljoin(
                media_url,
                m.group(1).decode("utf-8", "replace").replace("&amp;", "&"))
            if nxt != media_url:
                return _save(nxt, {**headers, "Referer": media_url}, out,
                             hops - 1)
        print(f"::warning::[yt_convert] {media_url[:90]} gave {n} bytes: "
              f"{body[:1000]!r}", flush=True)
        return False
    tmp.replace(out)
    return True


def _to_mp4(path: Path, mp4: Path) -> Path:
    """Remux (re-encode only if it must) to an mp4 the renderer reads."""
    for args in (["-c", "copy"], ["-c:v", "libx264", "-c:a", "aac"]):
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path)]
                           + args + [str(mp4)], capture_output=True,
                           timeout=600)
        if r.returncode == 0 and _probe(mp4):
            path.unlink(missing_ok=True)
            return mp4
    return path


def fetch(url: str, out: Path, *, max_s: float | None = None,
          budget_s: float = BUDGET_S) -> dict | None:
    """Save the YouTube video at `url` to `out` (an .mp4 path) through the
    first converter that hands over a real file. Returns {path, clip_id,
    title, clipper, views, duration, url, via} or None. A video longer
    than `max_s` is refused (None) before or after the download."""
    vid = video_id(url)
    if not vid:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    for kind, route in ROUTES:
        for host in _hosts(kind):
            if host in _DEAD:
                continue
            if time.monotonic() - t0 > budget_s:
                print(f"::warning::[yt_convert] {vid}: out of time", flush=True)
                return None
            try:
                got = route(host, vid)
                if not got:
                    continue
                media_url, hdr, meta = got
                dur = float(meta.get("duration") or 0)
                if max_s and dur > max_s:
                    print(f"[yt_convert] {vid}: {int(dur)}s is longer than "
                          f"{int(max_s)}s — not fetched", flush=True)
                    return None
                raw = out.with_suffix(".src")
                if not _save(media_url, hdr, raw):
                    print(f"::warning::[yt_convert] {kind} {vid}: the file "
                          f"it handed over was empty", flush=True)
                    continue
                path = _to_mp4(raw, out)
                real = _probe(path) if path == out else 0.0
                if not real:
                    try:
                        info = subprocess.run(
                            ["ffprobe", "-v", "error", "-show_entries",
                             "stream=codec_type,codec_name:format=duration",
                             "-of", "compact", str(path)], capture_output=True,
                            text=True, timeout=30)
                        head = path.read_bytes()[:200] if path.exists() else b""
                        what = (f"{path.stat().st_size if path.exists() else 0}"
                                f" bytes, {info.stdout.strip()[:200]!r} "
                                f"{info.stderr.strip()[:120]!r} {head!r}")
                    except Exception as e:  # noqa: BLE001
                        what = type(e).__name__
                    print(f"::warning::[yt_convert] {kind} {vid}: the file "
                          f"it handed over has no video and sound ({what})",
                          flush=True)
                    path.unlink(missing_ok=True)
                    continue
                if max_s and real > max_s:
                    path.unlink(missing_ok=True)
                    return None
                if not meta.get("title"):
                    meta = {**_api_meta(vid), **{k: v for k, v in meta.items() if v}}
                print(f"[yt_convert] {vid}: fetched by {kind} {host} "
                      f"({real:.0f}s)", flush=True)
                return {"path": out, "clip_id": vid,
                        "title": meta.get("title") or "",
                        "clipper": meta.get("uploader") or "",
                        "views": int(meta.get("views") or 0),
                        "duration": real, "url": url, "via": kind}
            except Exception as e:  # noqa: BLE001
                _DEAD.add(host)
                print(f"::warning::[yt_convert] {kind} {host}: "
                      f"{type(e).__name__} {str(e)[:120]}", flush=True)
    print(f"::warning::[yt_convert] {vid}: no converter answered", flush=True)
    return None
