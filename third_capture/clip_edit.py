#!/usr/bin/env python3
"""Clip pillar — Twitch/Kick clip -> edited 9:16 Short.

Pipeline per clip:
  1. discover(channel) — yt-dlp reads the channel's top clips of the last
     24h (no API key needed; Twitch Helix can slot in later).
  2. download(url) — grabs the source mp4 + metadata.
  3. edit(...) — reframe to 1080x1920 (blurred fill + centered clip),
     whisper word-timed captions in 1-3 word pops, streamer credit
     banner, optional hook card over the first seconds, loudness
     normalize. One ffmpeg pass for the visual chain.

Credit doctrine (THIRD_BRAIN.md): the streamer is credited + source-linked
in every platform's CAPTION/description, and any clip is taken down on
request. Credit is NO LONGER burned on screen by default (edit(burn_credit)
opts back in): a full-video third-party watermark is the single loudest
"reposted / unoriginal" signal to TikTok's originality filter and caps a
clip at ~300 views on the FYP. Attribution in the caption honors the doctrine
without the watermark that strangles reach. Only allowlisted channels used.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

CANVAS_W, CANVAS_H = 1080, 1920
REPO = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO / "assets" / "fonts"            # bundled Anton (OFL)
FONT_BOLD = str(FONTS_DIR / "Anton-Regular.ttf")
EMOJI_DIR = REPO / "assets" / "emoji"            # baked reaction-emoji PNGs
FX_DIR = REPO / "assets" / "fx"                  # procedural FX overlays


# Hard ceiling on every external tool call (yt-dlp download, ffprobe,
# ffmpeg encode). Without this a stalled download/encode hangs the whole
# run until GitHub's 60-min job timeout — the batch-4 incident. On
# timeout the package raises and the orchestrator moves to the next one.
_RUN_TIMEOUT = 300  # seconds
# a VOD window is minutes of HLS segments, not one clip file
_VOD_TIMEOUT = 480


def _run(cmd: list[str], timeout: int = _RUN_TIMEOUT) -> str:
    return subprocess.check_output(cmd, text=True,
                                   stderr=subprocess.STDOUT,
                                   timeout=timeout)


def _opening_guard(raw: Path, t0: float, t1: float) -> tuple[float, float]:
    """Never let a scroller's FIRST glimpse be a dead frame. The cut chooses
    t0 for narrative/audio reasons and never checks what is actually ON SCREEN
    there — a Twitch clip can open on a black scene-transition, a loading
    screen, an alt-tab, or a stuck/frozen frame, and QA (which only flags
    black >0.7s / frozen >2.5s ANYWHERE) waves it through. This probes just
    the first ~0.6s from t0 and, when it opens on black/near-black or a
    freeze, advances t0 past it — bounded to <=0.5s and never past t1-3.0s,
    so the moment itself is untouched. This is the audio 'never open on dead
    air' rule extended to VIDEO, and it compounds the retention opening-steer
    from the visual side. Returns (t0, advanced_by). Fail-open: any error or
    a healthy opening returns the original t0 unchanged."""
    MAX_ADV = 0.5
    headroom = (t1 - t0) - 3.0            # keep >=3s of real clip after t0
    if headroom <= 0.1:
        return t0, 0.0
    win = min(0.6, headroom)
    if win < 0.15:
        return t0, 0.0
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", f"{t0}", "-t", f"{win}",
             "-i", str(raw), "-an", "-vf",
             # lenient pic_th catches dark/low-detail, not just pure black;
             # freezedetect d=0.3 catches a genuinely STUCK opening frame
             # (paused clip) while ignoring the 1-2 near-identical frames any
             # normal video opens with — those tripped a false trim at d=0.05.
             "blackdetect=d=0.05:pic_th=0.90,"
             "freezedetect=n=-55dB:d=0.3",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=30)
        err = (p.stderr or "") + (p.stdout or "")
    except Exception:  # noqa: BLE001 — a probe must never break a render
        return t0, 0.0
    adv = 0.0
    # black lead-in that STARTS at the very opening (within ~0.12s)
    for m in re.finditer(r"black_start:([\d.]+).*?black_duration:([\d.]+)",
                         err):
        if float(m.group(1)) <= 0.12:
            adv = max(adv, min(float(m.group(2)), MAX_ADV))
    # frozen opening frame (stuck at the start)
    if re.search(r"freeze_start:\s*0(\.0\d*)?\b", err):
        fe = re.search(r"freeze_end:\s*([\d.]+)", err)
        adv = max(adv, min(float(fe.group(1)) if fe else 0.3, MAX_ADV))
    if adv <= 0.02:
        return t0, 0.0
    adv = min(adv, MAX_ADV, headroom)
    return round(t0 + adv, 2), round(adv, 2)


def _closing_guard(raw: Path, t0: float, t1: float) -> tuple[float, float]:
    """Never let the LAST frame be a dead frame — the closing twin of
    _opening_guard, which existed alone for months while nothing ever
    checked t1. Production proof (2026-07-29, run 30459022509): the +2.2s
    reaction tail ran a cut into the source's fade-to-black, the black tail
    was under QA's 0.7s blackdetect floor, and — because the contact sheet
    stamps its last tile at 0.958*dur — it was GUARANTEED to be the frame
    the vision critic saw: 'last frame (~14.7s) is solid black'.

    Probes the final ~1.2s before t1; if black or a frozen frame runs to
    the very end, pulls t1 back to where the dead tail starts. Bounded to
    <=2.5s (the reaction-tail scale) and never below t0+3.0s. Returns
    (t1, trimmed_by). Fail-open: errors or a healthy ending return t1."""
    MAX_TRIM = 2.5
    room = (t1 - t0) - 3.0
    if room <= 0.1:
        return t1, 0.0
    # PROBE THE WHOLE BUDGET. `win` was 1.2s while MAX_TRIM was 2.5, and
    # `trim` is derived entirely from offsets inside the probe window — so
    # the 2.5s budget was unreachable and the docstring's stated contract
    # was false. A clip whose source fades to black over 2.0s filled the
    # whole 1.2s window, trimmed 1.2s, and left 0.8s of black tail: enough
    # for render_qa's black-tail check to fire, which self-heals to the
    # simple render, which makes the identical 1.2s trim, fails again, and
    # blocklists a good clip. (_opening_guard already gets this right —
    # its window, 0.6s, is WIDER than its 0.5s budget.)
    win = min(MAX_TRIM + 0.5, room)
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", f"{max(0.0, t1 - win)}",
             "-t", f"{win}", "-i", str(raw), "-an", "-vf",
             "blackdetect=d=0.2:pic_th=0.90,freezedetect=n=-55dB:d=0.4",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=30)
        err = (p.stderr or "") + (p.stdout or "")
    except Exception:  # noqa: BLE001 — a probe must never break a render
        return t1, 0.0
    trim = 0.0
    # black that runs to (or within ~0.15s of) the end of the window
    for m in re.finditer(r"black_start:([\d.]+).*?black_end:([\d.]+)", err):
        if float(m.group(2)) >= win - 0.15:
            trim = max(trim, win - float(m.group(1)))
    # frozen final frames (stream-end stall) — keep a 0.3s beat of the hold
    fz = re.search(r"freeze_start:\s*([\d.]+)", err)
    if fz and not re.search(r"freeze_end", err):
        trim = max(trim, win - float(fz.group(1)) - 0.3)
    if trim <= 0.05:
        return t1, 0.0
    trim = min(trim, MAX_TRIM, room)
    return round(t1 - trim, 2), round(trim, 2)


def _content_crop(src: Path, dur: float) -> str:
    """Detect near-black letterbox/pillarbox bars baked into the SOURCE and
    return a crop filter prefix ('crop=W:H:X:Y,') that strips them — or ''
    when the frame is genuinely full. Without this, an already-boxed source
    (vertical stream inside 1920x1080, small game window with bars) goes
    through the blur-fill graph bars and all: shrunk a second time into a
    'tiny letterboxed rectangle surrounded by blurred/dead padding' (the
    2026-07-29 vision reject, and the recurring letterbox-class reject in
    third_qa_stats). Conservative on purpose: only crops when the detected
    picture is 25-92% of the frame — under 25% is a detection failure, over
    92% is normal edge noise. Fail-open: any error returns ''."""
    try:
        probe = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             str(src)], text=True, timeout=30).strip().split(",")
        full_w, full_h = int(probe[0]), int(probe[1])
        rects = []
        for frac in (0.25, 0.5, 0.75):
            p = subprocess.run(
                ["ffmpeg", "-v", "info", "-ss", f"{max(0.0, dur * frac)}",
                 "-t", "0.5", "-i", str(src), "-an",
                 "-vf", "cropdetect=limit=24:round=2", "-f", "null", "-"],
                capture_output=True, text=True, timeout=30)
            for m in re.finditer(r"crop=(\d+):(\d+):(\d+):(\d+)",
                                 p.stderr or ""):
                rects.append(tuple(int(g) for g in m.groups()))
        if not rects:
            return ""
        # take the LARGEST detected rect across samples — content moves,
        # bars don't, so the union over time is the safe crop
        w = max(r[0] for r in rects)
        h = max(r[1] for r in rects)
        x = min(r[2] for r in rects)
        y = min(r[3] for r in rects)
        ratio = (w * h) / float(full_w * full_h)
        if not (0.25 <= ratio <= 0.92):
            return ""
        print(f"[reframe] source carries baked-in bars — cropping to "
              f"{w}x{h}+{x}+{y} ({ratio:.0%} of frame) before compose",
              flush=True)
        return f"crop={w}:{h}:{x}:{y},"
    except Exception:  # noqa: BLE001 — a probe must never break a render
        return ""


# ---------- 1. discover ----------

# Twitch Helix path — used automatically when TWITCH_CLIENT_ID/SECRET are
# set. Gives exact created_at (real velocity, no per-clip age probes),
# proper 24h windowing, and vod offsets for future VOD mining.
_HELIX_TOKEN: dict = {}
_HELIX_IDS: dict[str, str] = {}


def _helix_creds() -> tuple[str, str] | None:
    import os
    cid = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    sec = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    return (cid, sec) if cid and sec else None


def _helix_headers() -> dict:
    import time
    import requests
    cid, sec = _helix_creds()
    if not _HELIX_TOKEN or _HELIX_TOKEN["exp"] < time.time() + 60:
        r = requests.post("https://id.twitch.tv/oauth2/token",
                          data={"client_id": cid, "client_secret": sec,
                                "grant_type": "client_credentials"},
                          timeout=20)
        r.raise_for_status()
        d = r.json()
        _HELIX_TOKEN.update(tok=d["access_token"],
                            exp=time.time() + d.get("expires_in", 3600))
    return {"Client-Id": cid,
            "Authorization": f"Bearer {_HELIX_TOKEN['tok']}"}


def _helix_user_id(login: str) -> str | None:
    import requests
    if login not in _HELIX_IDS:
        r = requests.get("https://api.twitch.tv/helix/users",
                         params={"login": login},
                         headers=_helix_headers(), timeout=20)
        r.raise_for_status()
        data = r.json().get("data", [])
        _HELIX_IDS[login] = data[0]["id"] if data else ""
    return _HELIX_IDS[login] or None


_HELIX_GAMES: dict = {}


def helix_game_names(ids) -> dict:
    """{game_id: name} for helix clip `game_id`s, cached for the run.

    A story the critic calls confusing is usually one where a stranger
    cannot tell who the streamer is or what they are playing ("a stranger
    doesn't know who Forsen is, or that this is Terraria", backtest
    2026-10-07) — and nobody on stream says it out loud, so the director
    could not either. Twitch knows; this is that fact. Best-effort: {} on
    any failure, never raises."""
    want = [str(i) for i in dict.fromkeys(ids or []) if i
            and str(i) not in _HELIX_GAMES]
    if want and _helix_creds():
        try:
            import requests
            for k in range(0, len(want), 100):
                chunk = want[k:k + 100]
                r = requests.get("https://api.twitch.tv/helix/games",
                                 params=[("id", g) for g in chunk],
                                 headers=_helix_headers(), timeout=20)
                r.raise_for_status()
                for g in r.json().get("data", []):
                    _HELIX_GAMES[str(g.get("id"))] = str(g.get("name", ""))
                for g in chunk:
                    _HELIX_GAMES.setdefault(g, "")
        except Exception as e:  # noqa: BLE001
            print(f"[helix] game names unavailable ({type(e).__name__})",
                  flush=True)
    return {str(i): _HELIX_GAMES.get(str(i), "") for i in ids or [] if i}


_HELIX_VIDEOS: dict[str, str] = {}


def helix_video_titles(ids) -> dict:
    """{video_id: broadcast title} for the VODs clips were cut from, cached
    for the run. The title is the STREAMER'S OWN line for that stream
    ("FNCS QUALIFIERS DAY 2 | !gfuel") — the context a stranger is missing
    and nobody on stream says: story backtest 9's best cut (Lacy, 78) was
    marked down because "a stranger never learns what the qualifier was".
    Best-effort: {} on any failure, never raises."""
    want = [str(i) for i in dict.fromkeys(ids or []) if i
            and str(i) not in _HELIX_VIDEOS]
    if want and _helix_creds():
        try:
            import requests
            for k in range(0, len(want), 100):
                chunk = want[k:k + 100]
                r = requests.get("https://api.twitch.tv/helix/videos",
                                 params=[("id", v) for v in chunk],
                                 headers=_helix_headers(), timeout=20)
                r.raise_for_status()
                for v in r.json().get("data", []):
                    _HELIX_VIDEOS[str(v.get("id"))] = \
                        str(v.get("title", ""))[:140]
                for v in chunk:
                    _HELIX_VIDEOS.setdefault(v, "")
        except Exception as e:  # noqa: BLE001
            print(f"[helix] stream titles unavailable ({type(e).__name__})",
                  flush=True)
    return {str(i): _HELIX_VIDEOS.get(str(i), "") for i in ids or [] if i}


def _discover_helix(channel: str, top: int, hours: int = 24) -> list[dict]:
    import time
    import requests
    from datetime import datetime, timezone, timedelta
    bid = _helix_user_id(channel)
    if not bid:
        return []
    started = (datetime.now(timezone.utc) - timedelta(hours=hours)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get("https://api.twitch.tv/helix/clips",
                     params={"broadcaster_id": bid, "started_at": started,
                             "first": max(top, 12)},
                     headers=_helix_headers(), timeout=20)
    r.raise_for_status()
    clips = []
    now = time.time()
    for c in r.json().get("data", [])[:top]:   # helix returns views desc
        created = datetime.fromisoformat(
            c["created_at"].replace("Z", "+00:00")).timestamp()
        clips.append({"url": c["url"], "views": int(c["view_count"]),
                      "duration": float(c.get("duration", 0)),
                      "title": c["title"], "channel": channel,
                      "platform": "twitch",
                      "age_h": max(0.05, (now - created) / 3600),
                      "vod_offset": c.get("vod_offset"),
                      "video_id": c.get("video_id"),
                      "game_id": c.get("game_id") or ""})
    return clips


def helix_clips(ids) -> list[dict]:
    """Twitch clips by id (slug), in discovery's own shape — the clips
    the internet picked (funnel/hot_clips.py) join the story pool with
    their VOD coordinates like any discovered clip. [] without creds."""
    import time
    import requests
    from datetime import datetime
    ids = [str(i) for i in ids if i][:100]
    if not ids or not _helix_creds():
        return []
    try:
        r = requests.get("https://api.twitch.tv/helix/clips",
                         params=[("id", i) for i in ids],
                         headers=_helix_headers(), timeout=20)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[helix] clips by id failed ({type(e).__name__})",
              flush=True)
        return []
    out, now = [], time.time()
    for c in r.json().get("data", []):
        created = datetime.fromisoformat(
            c["created_at"].replace("Z", "+00:00")).timestamp()
        out.append({"url": c["url"], "views": int(c["view_count"]),
                    "duration": float(c.get("duration", 0)),
                    "title": c["title"],
                    "channel": str(c.get("broadcaster_name", "")).lower(),
                    "platform": "twitch", "slug": c["id"],
                    "age_h": max(0.05, (now - created) / 3600),
                    "vod_offset": c.get("vod_offset"),
                    "video_id": c.get("video_id"),
                    "game_id": c.get("game_id") or ""})
    return out


def maybe_vod_window(clip: dict, work: Path, *, before: float = 60.0,
                     after: float = 60.0) -> dict | None:
    """VOD context expansion (STORY_DIRECTOR_PLAYBOOK §6): a Twitch clip
    often starts after the setup or ends before the reaction. When helix
    gave us the source VOD id + offset, pull the surrounding window so the
    story director can recover the missing context. Returns
    {"path", "vod_start_s", "clip_offset_s"} or None (sub-only VODs,
    deleted VODs, non-helix sources) — callers must REJECT a story whose
    essential context can't be recovered, never invent it."""
    vid = clip.get("video_id")
    off = clip.get("vod_offset")
    if not vid or off is None:
        return None
    try:
        start = max(0.0, float(off) - before)
        end = float(off) + float(clip.get("duration") or 30.0) + after
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        stem = f"vod_{vid}_{int(start)}_{int(end)}"
        out = work / f"{stem}.mp4"
        # STREAM COPY, not a re-encode. `--force-keyframes-at-cuts` plus
        # `--recode-video` re-encoded every expanded window on a 2-core
        # runner and ran into the 300s timeout (story backtest 2026-10-07:
        # `TimeoutExpired`, twice on one video) — so the stories that most
        # needed the setup or payoff around a clip never got it. A copy
        # snaps the start to the keyframe before `start` (Twitch: every 2s);
        # the director plans from this FILE's own transcript, so its cuts
        # stay exact and only `vod_start_s` is approximate.
        if not out.exists():
            t = time.monotonic()
            _ytdlp(["--download-sections", f"*{start:.0f}-{end:.0f}",
                    "-f", "b[height<=720]/b",
                    "-o", str(out), "--remux-video", "mp4",
                    f"https://www.twitch.tv/videos/{vid}"],
                   timeout=_VOD_TIMEOUT)
            print(f"[vod] expanded video {vid} {start:.0f}-{end:.0f}s "
                  f"in {time.monotonic() - t:.0f}s", flush=True)
        if not out.exists() or out.stat().st_size < 10_000:
            return None
        return {"path": str(out), "vod_start_s": start,
                "clip_offset_s": float(off) - start}
    except Exception as e:  # noqa: BLE001
        print(f"[vod] expansion failed for video {vid} "
              f"({type(e).__name__}) — context unrecoverable", flush=True)
        return None


def maybe_vod_segment(video_id: str, start: float, end: float,
                      work: Path) -> Path | None:
    """One stretch of a broadcast as its own file, or None. The moment
    story's BEFORE and AFTER (storyline.find_moments): what led up to the
    clip and what came of it, each a source the director can cut from.
    Same stream copy and timeout as `maybe_vod_window`; never raises."""
    if not video_id or end - start < 5:
        return None
    try:
        start = max(0.0, float(start))
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        out = work / f"vodseg_{video_id}_{int(start)}_{int(end)}.mp4"
        if not out.exists():
            t = time.monotonic()
            _ytdlp(["--download-sections", f"*{start:.0f}-{end:.0f}",
                    "-f", "b[height<=720]/b",
                    "-o", str(out), "--remux-video", "mp4",
                    f"https://www.twitch.tv/videos/{video_id}"],
                   timeout=_VOD_TIMEOUT)
            print(f"[vod] segment {video_id} {start:.0f}-{end:.0f}s "
                  f"in {time.monotonic() - t:.0f}s", flush=True)
        if not out.exists() or out.stat().st_size < 10_000:
            return None
        return out
    except Exception as e:  # noqa: BLE001
        print(f"[vod] segment failed for video {video_id} "
              f"({type(e).__name__})", flush=True)
        return None


# Kick and Rumble sit behind bot protection; yt-dlp's TLS impersonation
# (curl_cffi) gets through from clean egress (e.g. CI runners). Twitch
# needs nothing.
def _needs_impersonation(platform_or_url: str) -> bool:
    return any(s in platform_or_url for s in ("kick", "rumble"))


def _ytdlp(args: list[str], *, impersonate: bool = False,
           timeout: int = _RUN_TIMEOUT) -> str:
    cmd = ["yt-dlp"] + (["--impersonate", "chrome"] if impersonate else [])
    return _run(cmd + args, timeout=timeout)


def _discover_kick(channel: str, top: int, range_: str) -> list[dict]:
    """Kick has NO working yt-dlp channel-clips extractor — kick.com/<ch>/
    clips misroutes to the live-stream extractor (`kick:live`) and dies, so
    the old path returned nothing on every run. Hit Kick's public clips API
    directly with the same TLS impersonation yt-dlp uses for single Kick
    clips (curl_cffi chrome), and hand the resulting clip PAGE urls to the
    normal download() path (yt-dlp's KickClipIE handles those). Best-effort:
    returns [] on any failure so a Kick outage never blocks the run."""
    from datetime import datetime, timezone
    period = {"24hr": "day", "7d": "week", "30d": "month"}.get(range_, "day")
    url = (f"https://kick.com/api/v2/channels/{channel}/clips"
           f"?sort=view&time={period}")
    try:
        from curl_cffi import requests as _creq
        r = _creq.get(url, impersonate="chrome", timeout=25)
        if r.status_code != 200:
            print(f"::warning::[kick] {channel}: HTTP {r.status_code}",
                  flush=True)
            return []
        items = r.json().get("clips") or r.json().get("data") or []
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[kick] {channel}: {type(e).__name__} {e}",
              flush=True)
        return []
    out = []
    for c in items:
        cid = str(c.get("id") or "")
        if not cid:
            continue
        views = int(c.get("view_count") or c.get("views") or 0)
        dur = float(c.get("duration") or 0)
        title = (str(c.get("title") or "").strip() or f"{channel} clip")
        # exact age → real velocity (like Helix), when the API gives it
        age_h = None
        created = c.get("created_at") or c.get("clipped_at")
        if created:
            try:
                dt = datetime.fromisoformat(
                    str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_h = max(0.5, (datetime.now(timezone.utc) - dt)
                            .total_seconds() / 3600.0)
            except (ValueError, TypeError):
                pass
        d = {"url": f"https://kick.com/{channel}/clips/{cid}",
             "views": views, "duration": dur, "title": title,
             "channel": channel, "platform": "kick"}
        if age_h is not None:
            d["age_h"] = round(age_h, 2)
        out.append(d)
    if not out:
        # Kick's failure was SILENT: a 200 that parsed to zero clips
        # returned [] with no log line at all, which is worse than
        # Rumble's loud one — 0 of 168 posted videos have ever come from
        # Kick and nothing in the logs said why. Say it.
        print(f"::warning::[kick] {channel}: API responded but yielded 0 "
              f"clips — adapter or response shape may have drifted",
              flush=True)
    return out[:top]


def credit_label(platform: str, channel: str) -> str:
    return {"twitch": f"twitch.tv/{channel}",
            "kick": f"kick.com/{channel}",
            "rumble": f"rumble.com/c/{channel}"}[platform]


def discover(platform: str, channel: str, *, top: int = 8,
             range_: str = "24hr") -> list[dict]:
    """Top clips for a channel, best-first. No API keys on any platform.
    twitch: clips page sorted by views in the window. kick: the channel's
    clips page (site-ranked). rumble: latest channel uploads filtered to
    clip-length (<=2min) — rumble has no clip system, streamers post
    short highlights as videos."""
    if platform == "twitch":
        if _helix_creds():
            try:
                hours = {"24hr": 24, "7d": 168, "30d": 720,
                         "90d": 2160}.get(range_, 24)
                return _discover_helix(channel, top, hours=hours)
            except Exception as e:  # noqa: BLE001 — fall back to yt-dlp
                print(f"[helix] {channel}: {e} — falling back to yt-dlp",
                      flush=True)
        url = (f"https://www.twitch.tv/{channel}/clips"
               f"?filter=clips&range={range_}")
    elif platform == "kick":
        # Kick has no yt-dlp channel-clips extractor — use the API adapter.
        return _discover_kick(channel, top, range_)
    elif platform == "rumble":
        # Rumble has no clip system; streamers post highlights as short
        # videos on their channel. The handle can live under /c/ (brand
        # channel) OR /user/ (user page) — try both, first that yields wins.
        rumble_urls = [f"https://rumble.com/c/{channel}",
                       f"https://rumble.com/user/{channel}"]
        for i, ru in enumerate(rumble_urls):
            try:
                return _discover_ytdlp(ru, channel, "rumble", top)
            except Exception as e:  # noqa: BLE001
                # Surface yt-dlp's OWN message. _run merges stderr into
                # e.output, and both this handler and run_third's used to
                # print only the exception TYPE — so "CalledProcessError"
                # was the entire diagnosis available for days. The string
                # that explains the failure (e.g. "HTTP Error 403:
                # Forbidden") was captured and then discarded.
                detail = (getattr(e, "output", "") or "").strip()
                detail = detail.splitlines()[-1][:200] if detail else ""
                if i == len(rumble_urls) - 1:
                    if detail:
                        print(f"[rumble] {channel}: {ru} failed — {detail}",
                              flush=True)
                    raise
                print(f"[rumble] {channel}: {ru} failed "
                      f"({type(e).__name__}) {detail} — trying next form",
                      flush=True)
    else:
        raise ValueError(f"unknown platform {platform!r}")
    return _discover_ytdlp(url, channel, platform, top)


def _discover_ytdlp(url: str, channel: str, platform: str,
                    top: int) -> list[dict]:
    """Flat-playlist scrape of a channel/clips page via yt-dlp (Twitch
    non-Helix + Rumble). Kick/Rumble get TLS impersonation."""
    out = _ytdlp(
        ["--flat-playlist", "--playlist-items", f"1-{max(top, 12)}",
         "--print", "%(url)s\t%(view_count|0)s\t%(duration|0)s\t%(title)s",
         url],
        impersonate=_needs_impersonation(platform))
    clips = []
    for line in out.strip().splitlines():
        try:
            u, views, dur, title = line.split("\t", 3)
        except ValueError:
            continue
        dur = float(dur or 0)
        # Rumble's channel extractor yields bare url_result entries, so
        # under --flat-playlist duration renders as 0 for EVERY row. The
        # old `dur == 0` drop therefore discarded the entire page — a
        # second bug stacked under the 403, which would have kept Rumble
        # at zero results even if the bot-wall were solved. Unknown
        # duration is now let through (the preflight + content gate judge
        # the actual file); only a known-too-long video is dropped.
        if platform == "rumble" and dur > 120:
            continue                      # VODs/streams, not clip-length
        clips.append({"url": u, "views": int(float(views or 0)),
                      "duration": dur, "title": title,
                      "channel": channel, "platform": platform})
    return clips[:top]


# ---------- 2. download ----------

def download(url: str, work: Path, *, max_s: float | None = None) -> dict:
    """yt-dlp the clip at `url` (any platform it supports). `max_s` refuses
    a longer video BEFORE downloading it: a story's other side can be a
    forty-minute YouTube upload, and only a clip-length source is footage
    a story can cut from (ValueError)."""
    work.mkdir(parents=True, exist_ok=True)
    # per-clip filenames — a shared name collides when several packages
    # run in one invocation (and --print-to-file APPENDS across runs)
    stem = f"raw_{hashlib.sha1(url.encode()).hexdigest()[:10]}"
    raw = work / f"{stem}.mp4"
    meta = work / f"{stem}.meta"
    meta.unlink(missing_ok=True)
    _ytdlp(["-q", "--force-overwrites",
            "-o", str(work / (stem + ".%(ext)s")),
            "--recode-video", "mp4",
            "--print-to-file",
            "%(id)s\t%(title)s\t%(uploader)s\t%(view_count|0)s\t%(duration)s",
            str(meta)]
           + (["--match-filter", f"duration<=?{int(max_s)}"] if max_s else [])
           + [url],
           impersonate=_needs_impersonation(url))
    if max_s and not meta.exists():
        raise ValueError(f"longer than {int(max_s)}s")
    cid, title, clipper, views, dur = \
        meta.read_text().strip().splitlines()[-1].split("\t")
    return {"path": raw, "clip_id": cid, "title": title,
            "clipper": clipper, "views": _num(views),
            "duration": float(_num(dur, float)), "url": url}


def _num(v, kind=int):
    """yt-dlp prints "NA" for a field a site does not report (an X post
    has no view count)."""
    try:
        return kind(float(v))
    except (TypeError, ValueError):
        return kind(0)


# ---------- 3. captions ----------

_JUNK = re.compile(r"^[\W_]+$|♪|^\[.*\]$|^\(.*\)$")


def _transcript_cache_path(video: Path, model_name: str) -> Path | None:
    """Content-addressed transcript cache key: sha1 of the media bytes +
    model name, under cache/ (gitignored; persisted by actions/cache).
    Whisper-small on CPU costs 30-60s per clip and a story build transcribes
    every beat — the same clip re-picked across runs (or reused as a story
    member) should never pay that twice. None on any hashing error (cache
    silently disabled for that call)."""
    try:
        h = hashlib.sha1()
        with open(video, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return (REPO / "cache" / "transcripts"
                / f"{h.hexdigest()[:24]}-{model_name}.json")
    except Exception:  # noqa: BLE001
        return None


_WHISPER: dict = {}


# THE EARS. Whisper-small on CPU hears a streamer over game audio as
# "what do you to fucking do it? Hold on wait?" — backtest 15's critic docked
# cut after cut for garbled lines the viewer would have understood, the
# director chose its seconds from those words, and the burned captions
# showed them. THIRD_ASR=groq sends the audio to Groq's large-v3-turbo
# (free tier, seconds per clip) and falls back to the local model on any
# failure; a 429 rests it for the run.
GROQ_ASR_MODEL = "whisper-large-v3-turbo"
GROQ_ASR_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_GROQ_ASR_DOWN = {"until": 0.0}


def _groq_words(video: Path) -> list[dict] | None:
    """Word timestamps from Groq's large Whisper, or None (caller falls
    back). Same filters as the local path: segments Whisper calls
    no-speech are dropped, junk tokens skipped."""
    import os
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if (os.environ.get("THIRD_ASR", "").lower() != "groq" or not key
            or time.time() < _GROQ_ASR_DOWN["until"]):
        return None
    try:
        import requests
        with tempfile.TemporaryDirectory() as td:
            aud = Path(td) / "a.mp3"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
                            str(aud)], check=True, timeout=300)
            if aud.stat().st_size > 24 * 1024 * 1024:
                return None
            with open(aud, "rb") as f:
                r = requests.post(
                    GROQ_ASR_URL, headers={"Authorization": f"Bearer {key}"},
                    files={"file": ("a.mp3", f, "audio/mpeg")},
                    data=[("model", GROQ_ASR_MODEL), ("language", "en"),
                          ("response_format", "verbose_json"),
                          ("timestamp_granularities[]", "word"),
                          ("timestamp_granularities[]", "segment")],
                    timeout=120)
        if r.status_code == 429:
            _GROQ_ASR_DOWN["until"] = time.time() + 600
            print("::warning::[asr] groq 429 — local whisper for 10 min",
                  flush=True)
            return None
        r.raise_for_status()
        return groq_words_from(r.json())
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[asr] groq failed ({type(e).__name__}) — local "
              f"whisper", flush=True)
        return None


def groq_words_from(res: dict) -> list[dict]:
    """Groq's verbose_json -> [{w, s, e}], minus words inside a segment
    Whisper marked as no speech (the local path's 0.66 rule)."""
    quiet = [(float(sg.get("start", 0)), float(sg.get("end", 0)))
             for sg in res.get("segments") or []
             if float(sg.get("no_speech_prob", 0) or 0) > 0.66]
    out = []
    for w in res.get("words") or []:
        token = str(w.get("word", "")).strip()
        s, e = float(w.get("start", 0)), float(w.get("end", 0))
        if not token or _JUNK.match(token):
            continue
        if any(a <= (s + e) / 2 <= b for a, b in quiet):
            continue
        out.append({"w": token, "s": s, "e": e})
    return out


def _ocr_text(img: Path) -> str:
    """Letters tesseract reads in a frame, lowercased and run together, so
    a word glued to its neighbour ("SOMEBODYSTOLE") still matches."""
    out = []
    for psm in ("11", "6"):
        r = subprocess.run(["tesseract", str(img), "-", "--psm", psm],
                           capture_output=True, text=True, timeout=60)
        out.append(re.sub(r"[^a-z]", "", (r.stdout or "").lower()))
    return " ".join(out)


def own_captions(video: Path, words: list[dict], samples: int = 8) -> bool:
    """Does the video ALREADY show what is said, as text on screen?

    Operator, 2026-10-09: *"don't put captions over the captions of the
    video. Like, you can't read either of them then"*. Plenty of streamers
    run live captions. A frame is read (tesseract, white pixels only) while someone is
    talking, and the words the transcript says within a second and a half
    are looked for in it: two found is a caption, a game's
    HUD never matches speech. Two such frames, and at least 40% of those
    read, says the video captions itself. No tesseract -> False (the old
    behaviour)."""
    import shutil
    if not shutil.which("tesseract") or not words:
        return False
    spoken = [w for w in words if len(re.sub(r"[^a-z']", "",
                                             str(w["w"]).lower())) >= 3]
    if len(spoken) < 4:
        return False
    step = max(1, len(spoken) // samples)
    times = [float(spoken[i]["s"]) + 0.15
             for i in range(0, len(spoken), step)][:samples]
    hits = read = 0
    with tempfile.TemporaryDirectory() as td:
        for k, t in enumerate(times):
            fr = Path(td) / f"f{k}.png"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                     "-i", str(video), "-frames:v", "1",
                     # captions are WHITE: keep only near-white pixels, as
                     # black text on white, so busy footage drops out
                     # 2.5x: a stream's captions are often SMALL (a
                     # reaction's purple-bar captions at ~20px tall)
                     "-vf", "crop=iw:ih*0.7:0:ih*0.3,scale=iw*2.5:-2,"
                     "format=gray,lut=y='if(gt(val\\,215)\\,0\\,255)'",
                     str(fr)], check=True, timeout=60)
                seen = _ocr_text(fr)
            except Exception:  # noqa: BLE001
                continue
            read += 1
            seq = [re.sub(r"[^a-z]", "", str(w["w"]).lower())
                   for w in words if abs(float(w["s"]) - t) <= 1.5]
            near = set(seq)
            # two words a HUD never says, or two SPOKEN IN A ROW read
            # together ("ohmygod", "thatpoorman"): short captions are
            # mostly short words
            pairs = {a + b for a, b in zip(seq, seq[1:])
                     if a and b and len(a + b) >= 6}
            if (sum(1 for n in near if len(n) >= 4 and n in seen) >= 2
                    or any(p in seen for p in pairs)):
                hits += 1
    return hits >= 2 and hits >= 0.4 * max(1, read)


def transcribe_words(video: Path, model_name: str = "small") -> list[dict]:
    import os
    if os.environ.get("THIRD_ASR", "").lower() == "groq":
        gpath = _transcript_cache_path(Path(video), "groq-" + GROQ_ASR_MODEL)
        if gpath is not None and gpath.exists():
            try:
                return json.loads(gpath.read_text())
            except Exception:  # noqa: BLE001
                pass
        got = _groq_words(Path(video))
        if got is not None:
            if gpath is not None:
                try:
                    gpath.parent.mkdir(parents=True, exist_ok=True)
                    gpath.write_text(json.dumps(got))
                except Exception:  # noqa: BLE001
                    pass
            return got
    cpath = _transcript_cache_path(Path(video), model_name)
    if cpath is not None and cpath.exists():
        try:
            return json.loads(cpath.read_text())
        except Exception:  # noqa: BLE001 — corrupt cache entry: re-transcribe
            pass
    import whisper
    # MEMOIZE THE WEIGHTS. load_model re-reads and re-initialises the
    # 461MB `small` checkpoint on EVERY cache miss — 8-15s of pure
    # overhead, ~15 times a run on the story arm, for a model that never
    # changes within a process.
    model = _WHISPER.get(model_name)
    if model is None:
        model = _WHISPER[model_name] = whisper.load_model(model_name)
    # condition_on_previous_text=False stops the music/crowd-noise
    # hallucination loops stream audio triggers.
    # language="en" is REQUIRED: without it whisper auto-detects language on
    # noisy/music/crowd audio and hallucinates foreign-script warning text
    # ("CẨN TRỌNG", Vietnamese for CAUTION, burned into a live batch) that then
    # gets burned into the captions. Our channel is English streamer content —
    # pin the decode to English so a mishear is at worst an English word the
    # blocklist/low-probability filters can catch, never foreign glyphs.
    res = model.transcribe(str(video), word_timestamps=True, fp16=False,
                           condition_on_previous_text=False, language="en")
    words = []
    for seg in res["segments"]:
        if seg.get("no_speech_prob", 0) > 0.66:
            continue
        for w in seg.get("words", []):
            token = w["word"].strip()
            # low-probability words are usually crowd-noise mishears —
            # better no caption than a wrong (or offensive) one
            if (token and not _JUNK.match(token)
                    and w.get("probability", 1.0) >= 0.35):
                words.append({"w": token, "s": w["start"], "e": w["end"]})
    # WRITE the cache (reviewer-caught bug: the original cache read but
    # never wrote, so it stayed empty forever). Best-effort — a failed
    # write must never lose the transcription we just paid for.
    if cpath is not None:
        try:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps(words))
        except Exception:  # noqa: BLE001
            pass
    return words


_ASS_HEADER = """[Script Info]
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Anton,116,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,10,2,5,60,60,0,1
Style: Credit,Anton,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,5,0,2,40,40,64,1

[Events]
Format: Layer, Start, End, Style, Text
"""

# ASS colors are &HAABBGGRR
_YELLOW = r"\c&H00FFFF&"
_WHITE = r"\c&HFFFFFF&"
# Kinetic word-pop (the "someone edited this" caption): the word snaps in
# small, OVERSHOOTS past full size, then settles — the bounce every TikTok/
# Shorts editor uses, instead of a flat scale. Two chained \t transforms:
# 0-80ms grow 50%→114% (the snap), 80-150ms ease 114%→100% (the settle).
# A soft drop-shadow (\shad, \4c black) lifts it off busy footage. This is
# the biggest universal look upgrade — it renders on every caption in BOTH
# A/B arms, calm or not, so it improves clips the edit effects can't touch.
# Centre of the word-pop captions: ABOVE the story/clip line of text in
# the bottom third (caption_line.LINE_Y), never on it. At 1350 the two sat
# on top of each other (operator, 2026-10-09: "don't put captions over the
# captions ... you can't read either of them").
from third_capture.caption_line import SPEECH_Y as _SPEECH_Y  # noqa: E402
_POP_FX = (r"{\pos(540," + str(_SPEECH_Y) + r")\shad3\4c&H000000&\fscx50\fscy50"
           r"\t(0,80,\fscx114\fscy114)\t(80,150,\fscx100\fscy100)}")

# Caption safety: whisper mishears crowd noise into words we must never
# burn on screen ("higger" was a real incident). Any group containing a
# match is dropped entirely — no caption beats a catastrophic caption.
_CAPTION_BLOCKLIST = re.compile(
    r"n+[i1e]+gg+|higger|f+a+gg+[oe]t|retard|tranny|k[i1]ke|"
    r"sp[i1]c\b|ch[i1]nk|c+o+o+n\b|wetback",
    re.IGNORECASE)


def _ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(token: str) -> str:
    return re.sub(r"[{}\\]", "", token).upper()


# Words that are never the point of a line, so never the word we colour.
_CAP_DULL = set("""
a an the and or but so if then than that this these those there here
i me my we us our you your he him his she her it its they them their
is am are was were be been being do does did done have has had
of to in on at by for from with without into onto up down out off over
about like just so very really too also not ok okay
im ive youre youve hes shes its theyre thats what when where who how why
gonna wanna gotta kinda sorta
""".split())


def _emphasis_index(group: list[dict], toks: list[str]) -> int | None:
    """Which word in this caption group should carry the colour, if any.

    This used to be `max(len(tok))` — the LONGEST word. That is a character
    count, not emphasis: it colours "ACTUALLY" over "NO" and highlights
    something in nearly every group, which is how captions end up looking
    auto-generated. Two better signals, both already in hand:

      1. DRAWL. We have per-word timings. A speaker stretching a word is
         literally stressing it, so duration-per-character is real prosodic
         emphasis rather than a proxy for it.
      2. It has to be a content word. A drawn-out "THEEE" is not the point
         of the line.

    Returns None when nothing in the group stands out — an uncoloured
    caption is the correct, common answer, and rationing the colour is what
    makes it mean anything when it does appear."""
    best, best_r = None, 0.0
    for i, g in enumerate(group):
        tok = toks[i].strip()
        core = re.sub(r"[^A-Za-z']", "", tok).lower()
        # >=2, not >=3: "NO", "OH", "WHY" are the punchiest words a
        # streamer says, and a 3-char floor excluded exactly those. The
        # stoplist, not the length, is what keeps "we"/"it"/"is" out.
        if len(core) < 2 or core in _CAP_DULL:
            continue
        dur = float(g.get("e", 0)) - float(g.get("s", 0))
        if dur <= 0:
            continue
        # seconds per character, normalised against a natural ~0.075 s/char
        r = (dur / len(core)) / 0.075
        if r > best_r:
            best, best_r = i, r
    # 1.25x the natural rate = audibly held. Calibrated against real word
    # timings: "INSANE" drawn out over 0.60s (0.10 s/char, 1.33x) is
    # emphasis and must qualify; "BRO" clipped at 0.15s (0.67x) is not.
    # Below the line nothing is being stressed and the caption reads fine
    # in one colour, which is the common case by design.
    return best if best is not None and best_r >= 1.25 else None


# Rough advance width of Anton in ALL CAPS, as a fraction of font size.
# Anton is a condensed grotesque; measured over A-Z it averages ~0.52em.
_ANTON_ADV = 0.52


def wrap_hook(hook: str, max_w: int = 980, size: int = 72,
              max_lines: int = 2) -> tuple[str, int]:
    """(text_with_newlines, fontsize) for the hook card.

    The card was drawn at a fixed 72px with no wrapping and centred by
    x=(w-text_w)/2. The author is instructed to write 4-8 words IN CAPS, and
    at 72px Anton that passes 1080px around 30 characters — past which
    text_w exceeds the canvas, x goes NEGATIVE and the hook runs off both
    edges of the first frame every viewer sees. Wrap to at most two lines,
    then shrink only if two lines still do not fit."""
    words = str(hook or "").split()
    if not words:
        return "", size
    for fs in range(size, 39, -4):
        per = max(1.0, fs * _ANTON_ADV)
        budget = int(max_w / per)
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if len(trial) <= budget or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines and all(len(ln) <= budget for ln in lines):
            return "\n".join(lines), fs
    # Nothing fits in two lines even at the floor: let it wrap to as many as
    # it needs at the smallest size rather than clipping it off-screen.
    fs = 40
    per = max(1.0, fs * _ANTON_ADV)
    budget = int(max_w / per)
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= budget or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines), fs


def build_ass(words: list[dict], credit: str, dur: float, out: Path,
              max_group: int = 3, burn_credit: bool = False) -> Path:
    """Word-pop subtitles (ALL-CAPS Anton, one yellow-emphasized word per
    group, pop-in). Groups split on gaps > 0.6s or punctuation. Groups
    containing blocklisted tokens are dropped entirely — no caption beats a
    catastrophic caption.

    burn_credit: draw a PERMANENT on-screen credit line. Default OFF — a
    full-video third-party watermark is the loudest "reposted / unoriginal"
    signal to TikTok's originality filter (the thing that caps a clip at
    ~300 views on the FYP). Credit is preserved in every platform's caption/
    description instead, which honors the credit+takedown doctrine without
    the watermark that strangles reach."""
    lines = [_ASS_HEADER]
    group: list[dict] = []

    def flush():
        if not group:
            return
        s, e = group[0]["s"], max(group[-1]["e"], group[0]["s"] + 0.35)
        toks = [_clean(g["w"]) for g in group]
        if _CAPTION_BLOCKLIST.search(" ".join(toks)):
            group.clear()
            return
        emph = _emphasis_index(group, toks)
        if emph is not None:
            toks[emph] = "{%s}%s{%s}" % (_YELLOW, toks[emph], _WHITE)
        lines.append(f"Dialogue: 1,{_ts(s)},{_ts(e)},Pop,"
                     f"{_POP_FX}{' '.join(toks)}\n")
        group.clear()

    # Grouping math is shared/captions.py — one grouper for every renderer
    # (audit finding C; five near-identical private copies existed). These
    # arguments reproduce this function's previous behaviour exactly,
    # including that a BLANK word broke a line here (the old test was
    # `w[-1:] in ".?!,"`, and `"" in ".?!,"` is True in Python).
    # tests/test_captions.py holds that equivalence.
    from shared import captions
    for grp in captions.group_words(
            words, max_words=max_group, max_gap=0.6, max_span=float("inf"),
            break_on_punct=True, break_chars=".?!,", drop_empty=False,
            blank_breaks=True):
        group.extend(grp)
        flush()
    if burn_credit and credit:
        lines.append(
            f"Dialogue: 0,{_ts(0)},{_ts(dur)},Credit,{credit}\n")
    out.write_text("".join(lines))
    return out


# ---------- 4. edit ----------

def fetch_age_hours(url: str) -> float:
    """Clip age in hours from a metadata-only probe. 0.0 when unknown."""
    try:
        import time
        out = _ytdlp(["--skip-download", "--print", "%(timestamp|0)s", url],
                     impersonate=_needs_impersonation(url))
        ts = float(out.strip().splitlines()[-1] or 0)
        return max(0.0, (time.time() - ts) / 3600) if ts else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


from third_capture.shot_plan import BG_TOP  # noqa: E402,F401  one share, both fills


def edit(raw: Path, out_path: Path, *, credit: str, hook: str = "",
         start: float = 0.0, end: float = 0.0,
         whisper_model: str = "small", words: list[dict] | None = None,
         auto: bool = True, series: str = "chaos",
         direct: dict | None = None, edit_mode: bool = False,
         when: float | None = None) -> dict:
    """Compose the 9:16 edit. `credit` is the full on-screen label
    (e.g. "twitch.tv/xqc", "kick.com/adinross"). Pass precomputed `words`
    (from transcribe_words on the SAME uncut file) to skip re-transcribing —
    only valid when start/end are unset.

    `auto=True` reframes with the shot plan, burns the speech captions
    (skipped when the video already shows its own), lays the ONE line of
    text in the bottom third (caption_line) and, when the author marked a
    sad turn, greys the picture and brings in the piano from that second
    (mood). The auto-editor's slow-mo, replay, speed-up and sticker
    overlays were retired 2026-10-09. Every layer degrades gracefully, so a
    clip always ships. Returns the ledger.
    """
    probe = json.loads(_run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(raw)]))
    src_dur = float(probe["format"]["duration"])
    t0 = max(0.0, start)
    t1 = min(src_dur, end) if end else src_dur
    # Auto tight-cut when no explicit cut was authored (playbook §9): never
    # open on dead air (start just before the first spoken word); keep a
    # 2.2s REACTION TAIL after the last word so the laugh/stunned-silence
    # lands (the reaction often IS the payoff); and cap at 45s WORD-SAFELY —
    # snap the cap back to the end of the last word that fully fits plus a
    # 1.0s tail, never slicing mid-word or mid-payoff.
    if not start and not end and words:
        dcut = (direct or {}).get("cut")
        if dcut:
            # DIRECTOR CUT (§9): the author read the timestamped transcript
            # and chose a window that includes the setup AND the full payoff
            # + reaction — so a clip never starts mid-story or ends before
            # the payoff lands. Validated upstream against clip length.
            t0 = max(0.0, min(float(dcut["start"]), src_dur - 3.0))
            t1 = min(src_dur, max(float(dcut["end"]), t0 + 3.0))
        else:
            t0 = max(0.0, words[0]["s"] - 0.8)
            t1 = min(src_dur, words[-1]["e"] + 2.2)
            if t1 - t0 > 45.0:
                cap = t0 + 45.0
                last_e = max((w["e"] for w in words if w["e"] <= cap - 1.0),
                             default=None)
                t1 = (last_e + 1.0) if last_e is not None else cap
            # SPARSE-SPEECH GUARD: on a near-silent reaction clip whisper
            # hears a word or two and the transcript cut collapses to
            # seconds (live incident: a 2.0s render, QA-rejected 4x). The
            # moment on a quiet clip is VISUAL — words can't locate it, so
            # keep the whole clip (front 45s) instead of a cut from nothing.
            if t1 - t0 < 8.0 or len(words) < 4:
                t0, t1 = 0.0, min(src_dur, 45.0)
    # OPENING GUARD (opening visual craft): never open on a dead frame —
    # nudge t0 past a black/near-black/frozen lead-in. Runs for EVERY cut
    # (auto, director, explicit, whole-clip) and BEFORE the caption rebase so
    # the burned-in word times stay aligned to the guarded start.
    t0, opening_adv = _opening_guard(raw, t0, t1)
    if opening_adv:
        print(f"[opening] trimmed {opening_adv:.2f}s of dead lead-in "
              f"(t0 -> {t0:.2f}s)", flush=True)
    # CLOSING GUARD: the symmetric check on t1 — never END on black or a
    # stream-end freeze (the reaction tail and whole-clip fallbacks read
    # timestamps, not pixels). Runs before the caption rebase so word
    # filtering sees the final cut.
    t1, closing_trim = _closing_guard(raw, t0, t1)
    if closing_trim:
        print(f"[closing] trimmed {closing_trim:.2f}s of dead tail "
              f"(t1 -> {t1:.2f}s)", flush=True)
    if not start and not end and words:
        # captions: only words that fit ENTIRELY inside the cut — a caption
        # for a half-sliced word reads as a broken edit
        words = [{"w": w["w"], "s": w["s"] - t0, "e": w["e"] - t0}
                 for w in words if t0 <= w["s"] and w["e"] <= t1 - 0.05]
    dur = t1 - t0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cut = tmp / "cut.mp4"
        if t0 > 0.01 or t1 < src_dur - 0.01:
            _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0}",
                  "-to", f"{t1}", "-i", str(raw), "-c:v", "libx264",
                  "-preset", "veryfast", "-crf", "18", "-c:a", "aac",
                  str(cut)])
        else:
            cut = raw

        if words is None:
            words = transcribe_words(cut, whisper_model)

        # Detect chaotic / no-stable-subject footage (IRL, party, crowd) up
        # front: shot_plan classifies "wide" when nothing trackable persists.
        # Such clips get a CALM Stage 1 (no slow-mo/replay/impact — those smear
        # on unanchored motion) and the whole-frame reframe. This is the fix
        # for the IRL QA-rejects. Best-effort: no cv2/analysis → normal path.
        calm = False
        _cut_an = None      # reused by Stage 2 — see below
        if auto:
            try:
                from third_capture import shot_plan as _spn
                _an = _cut_an = _spn.analyze(cut)
                if _an is not None:
                    _layout, _, _ = _spn.classify(_an)
                    calm = (_layout == "wide")
                    if calm:
                        print("[edit] chaotic/no-subject footage — calm "
                              "treatment (no slow-mo/replay/impact)", flush=True)
            except Exception:  # noqa: BLE001 — default to the normal path
                calm = False

        # ---- Stage 1: RETIRED (operator, 2026-10-09) ----
        # The auto-editor's slow-mo + instant replay, dead-air speed-up,
        # impact shake/flash, slam word, sticker emoji and SFX: "That weird
        # slowdown thing we do never works, and then we speed up randomly
        # after it. It sucks." The clip plays at its own speed, as the
        # repost channels play it; the edit is the line of text and, on a
        # sad turn, the grey and the piano (third_capture/mood.py).
        program = cut
        ledger_ae = {"auto_edit": False, "fallback_reason": "retired",
                     "effects": [], "edl": None, "edit_mode": bool(edit_mode)}

        # ---- Stage 2: presentation ----
        # Shot-plan layer (playbook §3-§8): analyze subjects, classify the
        # layout, and execute an explicit reasoned plan — static close-up /
        # deliberate two-shot / designed split-screen / stacked facecam+
        # full-width-gameplay. None → blur-fill whole frame (action always
        # visible). Never blocks the render.
        reframed, sp_summary = None, None
        if auto:
            try:
                from third_capture import shot_plan as spn
                # analysis on the SOURCE cut (§3), plan executed on the program
                #
                # PASS THE ANALYSIS WE ALREADY HAVE. The calm probe above
                # runs spn.analyze(cut) and throws the result away; build()
                # then ran analyze(analyze_on=cut) on the identical file —
                # a full cv2 decode plus a Haar pass, 15-45s, twice per
                # render, ~10 renders a run.
                reframed, sp_summary = spn.build(program, tmp, analyze_on=cut,
                                                 an=_cut_an)
                ledger_ae["shot_plan"] = sp_summary
            except Exception:  # noqa: BLE001
                reframed = None

        # NO CAPTIONS OVER CAPTIONS (operator, 2026-10-09): a stream that
        # already shows what is said gets no second copy on top of it
        own_subs = own_captions(cut, words) if auto else False
        if own_subs:
            print("[edit] the video captions itself — no speech captions",
                  flush=True)
        ass = build_ass([] if own_subs else words, credit, dur,
                        tmp / "caps.ass")

        if reframed is not None:
            # program is already a sharp 1080x1920 face crop — just grade +
            # burn captions (reuse the longform grade: gentle sat + vignette).
            src = reframed
            base_vf = (
                "[0:v]eq=saturation=1.05,vignette=PI/5[base];"
                f"[base]ass={ass}:fontsdir={FONTS_DIR}[capped]"
            )
            # bulletproof visual if even captions fail: the crop is already 9:16
            plain_vf = "[0:v]null[vout]"
        else:
            # blur-fill center reframe — the guaranteed, battle-tested look
            # (auto=False renders exactly this path).
            src = program
            # strip baked-in letterbox/pillarbox bars FIRST, so a source
            # that is already boxed doesn't get boxed again inside the blur
            # fill (the 'tiny rectangle in dead padding' reject class)
            bar_crop = _content_crop(src, dur)
            _blur = (
                f"[0:v]{bar_crop}split=2[bg][fg];"
                # the fill is made from the TOP of the frame: the bottom is
                # where a stream burns its own captions, and blown up and
                # blurred they sat under ours as ghost text ("burned-in
                # stream captions ... and a blurred ghost caption in the
                # bottom padding all stack up", vision QA 2026-10-09)
                f"[bg]crop=iw:ih*{BG_TOP}:0:0,"
                f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
                "increase,crop=1080:1920,gblur=sigma=24,"
                # was brightness=-0.12 — darkening an already-dark IRL clip
                # crushed the whole frame to near-black (the top QA-reject on
                # Streamer University footage). A hair of darken keeps the
                # centered clip popping without swallowing dim sources.
                "eq=brightness=-0.03:saturation=1.15[bgd];"
                # fit INSIDE the canvas (identical 1080-wide result for 16:9,
                # but a taller-than-9:16 source now scales to fit instead of
                # overflowing and being silently edge-cropped by the overlay)
                f"[fg]scale={CANVAS_W}:{CANVAS_H}:"
                "force_original_aspect_ratio=decrease[fgs];"
                "[bgd][fgs]overlay=(W-w)/2:(H-h)/2[base]"
            )
            base_vf = _blur + f";[base]ass={ass}:fontsdir={FONTS_DIR}[capped]"
            plain_vf = _blur.replace("[base]", "[vout]")

        # ---- the line of text, and the mood (operator, 2026-10-09) ----
        # The hook card (3s, top), the REPLAY stamp, the slam word and the
        # sticker emoji are gone: "The fucking overlays we do suck." What
        # the repost channels put on a clip is ONE line, sentence case,
        # white with a black outline, in the bottom third, there the whole
        # video, emoji in the text (third_capture/caption_line.py) — and on
        # a sad turn the picture goes grey and a piano comes in under the
        # voices (third_capture/mood.py), from the second the author named.
        from third_capture import caption_line
        from third_capture import moves as moves_mod
        # The moves (operator, same day: "you have to add stuff other
        # clippers do ... we can't just do the sad grey thing"): a punch-in
        # with a boom, a shake, an awkward push-in with crickets, the sad
        # grey and piano or the hype colour and beat, and a second line at
        # the turn — each on the second the author named
        # (third_capture/moves.py).
        mv = moves_mod.plan(direct if (auto and direct) else {}, dur,
                            offset=t0)
        line_png, line2_png = None, None
        if hook:
            try:
                line_png = caption_line.render(hook, tmp / "line.png")
                if mv["line2"]:
                    line2_png = caption_line.render(mv["line2"]["text"],
                                                    tmp / "line2.png")
            except Exception as e:  # noqa: BLE001
                print(f"::warning::[edit] caption line failed "
                      f"({type(e).__name__})", flush=True)
        try:
            # make every sound now, so a synth failure drops the moves
            # rather than the render
            moves_mod.audio_graph(mv, "0:a", 1, dur, "amv")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[edit] move sounds failed "
                  f"({type(e).__name__}) — no moves", flush=True)
            mv = moves_mod.plan({}, dur)
        # the THING they're talking about, shown for a few seconds when
        # it is named (operator, 2026-10-09: "put a picture of the stock
        # he is talking about as a layover ... so they can get it") —
        # only an exact match is shown (third_capture/show_it.py)
        from third_capture import show_it
        shows = []
        if auto and direct and direct.get("show"):
            shows = show_it.ready(show_it.plan(direct["show"], dur,
                                               offset=t0), tmp, when)
        ledger_ae["shown"] = [f"{s['thing']}@{s['at']}" for s in shows]
        _bed = mv["bed"]
        ledger_ae["mood"] = _bed["move"] if _bed else None
        ledger_ae["mood_at"] = _bed["at"] if _bed else None
        ledger_ae["moves"] = moves_mod.summary(mv)
        print(f"[edit] moves: {', '.join(ledger_ae['moves']) or 'none'}",
              flush=True)
        ledger_ae["own_captions"] = own_subs

        # §9: a 0.25s audio fade-out — the clip breathes out instead of the
        # audio slamming shut on the final frame
        afade = (f"loudnorm=I=-14:TP=-1.5,"
                 f"afade=t=out:st={max(0.0, dur - 0.25):.2f}:d=0.25")
        _has_moves = bool(mv["hits"] or mv["bed"] or line2_png or shows)

        def _compose(with_line: bool, with_mood: bool) -> tuple[str, list]:
            """(filter_complex, extra_input_paths); it ends in [vout] and
            [aout]. with_mood carries every move."""
            vf0, inputs = base_vf, []
            if with_mood:
                # the camera and the colour act on the PICTURE, under the
                # captions, so the words neither zoom nor go grey
                pre = ",".join(f for f in (
                    moves_mod.camera(mv, CANVAS_W, CANVAS_H),
                    moves_mod.look(mv)) if f)
                if pre:
                    vf0 = vf0.replace("[base]ass=", f"[base]{pre},ass=")
            parts, cur = [vf0], "capped"
            if with_line and line_png:
                inputs.append(line_png)
                if with_mood and line2_png:
                    a2 = mv["line2"]["at"]
                    parts.append(f"[{cur}][{len(inputs)}:v]overlay=0:"
                                 f"{caption_line.LINE_Y}:"
                                 f"enable='lt(t,{a2:.2f})'[ln1]")
                    inputs.append(line2_png)
                    parts.append(f"[ln1][{len(inputs)}:v]overlay=0:"
                                 f"{caption_line.LINE_Y}:"
                                 f"enable='gte(t,{a2:.2f})'[ln]")
                else:
                    parts.append(f"[{cur}][{len(inputs)}:v]overlay=0:"
                                 f"{caption_line.LINE_Y}[ln]")
                cur = "ln"
            if with_mood:
                for i, sh in enumerate(shows):
                    inputs.append(sh["png"])
                    parts.append(show_it.overlay(cur, len(inputs), sh,
                                                 f"sh{i}"))
                    cur = f"sh{i}"
            parts.append(f"[{cur}]null[vout]")
            a_in = "0:a"
            if with_mood and (mv["hits"] or mv["bed"]):
                frag, files = moves_mod.audio_graph(
                    mv, "0:a", len(inputs) + 1, dur, "amood")
                inputs += files
                parts.append(frag)
                a_in = "amood"
            parts.append(f"[{a_in}]{afade}[aout]")
            return ";".join(parts), inputs

        def _render(chain: str, extra_inputs: list | None = None) -> bool:
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
            for p in (extra_inputs or []):
                cmd += ["-i", str(p)]
            cmd += ["-filter_complex", chain, "-map", "[vout]",
                    "-map", "[aout]",
                    # cap the container at the cut length: without -t, an
                    # audio stream that outlasts the video (yt-dlp recode)
                    # extends the file with picture-less tail — the afade
                    # timing and QA's AV_DRIFT allowance both assume `dur`
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", str(out_path)]
            try:
                _run(cmd)
                return True
            except Exception:  # noqa: BLE001
                return False

        full_chain, full_inputs = _compose(with_line=True, with_mood=True)
        line_chain, line_inputs = _compose(with_line=True, with_mood=False)
        _a = f";[0:a]{afade}[aout]"
        caps_vf = base_vf.replace("[capped]", "[vout]") + _a
        plain_vf = plain_vf + _a

        # Render ladder — a clip must ALWAYS ship. Full (captions + line +
        # mood) -> line without the mood -> captions only -> plain reframe
        # -> raw re-encode. Record what shipped.
        if _render(full_chain, full_inputs):
            render_level = "full"
        elif _has_moves and _render(line_chain, line_inputs):
            render_level = "text_only"
        elif _render(caps_vf):
            render_level = "captions_only"
        elif _render(plain_vf):
            render_level = "plain"
        else:
            # LAST-RESORT RUNG — its whole premise is "a clip must ALWAYS
            # ship", so it must produce something QA can pass.
            # `pad` defaults to BLACK, which on a 16:9 source is 68% of
            # the frame — the letterbox check used to reject exactly this,
            # making the guaranteed-ship rung guaranteed to fail. It now
            # blur-fills like every other rung (same graph, no captions,
            # no overlays), so the fallback is a plainer video rather than
            # a mechanically-defective one. It also carries the same -t cap
            # as every other rung; without it this branch could still emit
            # the picture-less audio tail the cap was added to prevent,
            # which then trips the a/v-drift check too.
            _raw_vf = (f"[0:v]scale={CANVAS_W}:{CANVAS_H}:"
                       "force_original_aspect_ratio=increase,"
                       f"crop={CANVAS_W}:{CANVAS_H},gblur=sigma=28,"
                       "eq=brightness=-0.03[bg];"
                       f"[0:v]scale={CANVAS_W}:{CANVAS_H}:"
                       "force_original_aspect_ratio=decrease[fg];"
                       "[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]")
            _raw_cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src),
                        "-filter_complex", _raw_vf, "-map", "[vout]",
                        "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                        "-pix_fmt", "yuv420p", "-r", "30",
                        "-c:a", "aac", "-b:a", "160k"]
            if dur and dur > 0:
                _raw_cmd += ["-t", f"{dur:.3f}"]
            _run(_raw_cmd + [str(out_path)])
            render_level = "raw"
        if render_level != "full":
            ledger_ae["render_fallback"] = render_level

    return {"kind": "twitch_clip", "credit": credit,
            "render_level": render_level,
            "cut": [t0, t1], "duration_s": round(dur, 2),
            "opening_trim_s": opening_adv, "closing_trim_s": closing_trim,
            "caption_words": len(words), "hook": hook,
            # NAME THE REFRAME BY WHAT IT ACTUALLY IS. This said "face"
            # for ANY reframe, which was true while every reframe mode was
            # face-driven (closeup/two_shot/split/stacked). The action crop
            # is aimed at MOTION and by definition runs when no face is
            # trackable — labelling it "face" makes clip_qa run its
            # face-visibility check and reject it for containing no face,
            # which is every clip the crop exists to serve. Caught by
            # scripts/smoke_third.py before it reached the channel.
            "reframe": ("blur" if reframed is None else
                        (sp_summary or {}).get("layout") or "face"),
            **ledger_ae}
