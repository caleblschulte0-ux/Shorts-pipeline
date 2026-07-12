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

Credit doctrine (THIRD_BRAIN.md): streamer name burned on screen the
whole video + source link in the description. Only channels on the
allowlist in the package are used.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
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


def _run(cmd: list[str], timeout: int = _RUN_TIMEOUT) -> str:
    return subprocess.check_output(cmd, text=True,
                                   stderr=subprocess.STDOUT,
                                   timeout=timeout)


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
                      "vod_offset": c.get("vod_offset")})
    return clips


# Kick and Rumble sit behind bot protection; yt-dlp's TLS impersonation
# (curl_cffi) gets through from clean egress (e.g. CI runners). Twitch
# needs nothing.
def _needs_impersonation(platform_or_url: str) -> bool:
    return any(s in platform_or_url for s in ("kick", "rumble"))


def _ytdlp(args: list[str], *, impersonate: bool = False) -> str:
    cmd = ["yt-dlp"] + (["--impersonate", "chrome"] if impersonate else [])
    return _run(cmd + args)


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
                hours = {"24hr": 24, "7d": 168, "30d": 720}.get(range_, 24)
                return _discover_helix(channel, top, hours=hours)
            except Exception as e:  # noqa: BLE001 — fall back to yt-dlp
                print(f"[helix] {channel}: {e} — falling back to yt-dlp",
                      flush=True)
        url = (f"https://www.twitch.tv/{channel}/clips"
               f"?filter=clips&range={range_}")
    elif platform == "kick":
        url = f"https://kick.com/{channel}/clips"
    elif platform == "rumble":
        url = f"https://rumble.com/c/{channel}"
    else:
        raise ValueError(f"unknown platform {platform!r}")
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
        if platform == "rumble" and (dur == 0 or dur > 120):
            continue                      # VODs/streams, not clip-length
        clips.append({"url": u, "views": int(float(views or 0)),
                      "duration": dur, "title": title,
                      "channel": channel, "platform": platform})
    return clips[:top]


# ---------- 2. download ----------

def download(url: str, work: Path) -> dict:
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
            str(meta), url],
           impersonate=_needs_impersonation(url))
    cid, title, clipper, views, dur = \
        meta.read_text().strip().splitlines()[-1].split("\t")
    return {"path": raw, "clip_id": cid, "title": title,
            "clipper": clipper, "views": int(float(views or 0)),
            "duration": float(dur), "url": url}


# ---------- 3. captions ----------

_JUNK = re.compile(r"^[\W_]+$|♪|^\[.*\]$|^\(.*\)$")


def transcribe_words(video: Path, model_name: str = "small") -> list[dict]:
    import whisper
    model = whisper.load_model(model_name)
    # condition_on_previous_text=False stops the music/crowd-noise
    # hallucination loops stream audio triggers
    res = model.transcribe(str(video), word_timestamps=True, fp16=False,
                           condition_on_previous_text=False)
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
_POP_FX = r"{\pos(540,1350)\fscx72\fscy72\t(0,70,\fscx100\fscy100)}"

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


def build_ass(words: list[dict], credit: str, dur: float, out: Path,
              max_group: int = 3) -> Path:
    """Word-pop subtitles (ALL-CAPS Anton, one yellow-emphasized word per
    group, pop-in) plus a permanent credit line. Groups split on gaps
    > 0.6s or punctuation. Groups containing blocklisted tokens are
    dropped entirely — no caption beats a catastrophic caption."""
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
        emph = max(range(len(toks)), key=lambda i: len(toks[i]))
        if len(toks[emph]) >= 4:
            toks[emph] = "{%s}%s{%s}" % (_YELLOW, toks[emph], _WHITE)
        lines.append(f"Dialogue: 1,{_ts(s)},{_ts(e)},Pop,"
                     f"{_POP_FX}{' '.join(toks)}\n")
        group.clear()

    for w in words:
        if group and (w["s"] - group[-1]["e"] > 0.6
                      or len(group) >= max_group
                      or group[-1]["w"][-1:] in ".?!,"):
            flush()
        group.append(w)
    flush()
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


def edit(raw: Path, out_path: Path, *, credit: str, hook: str = "",
         start: float = 0.0, end: float = 0.0,
         whisper_model: str = "small", words: list[dict] | None = None,
         auto: bool = True, series: str = "chaos",
         direct: dict | None = None) -> dict:
    """Compose the 9:16 edit. `credit` is the full on-screen label
    (e.g. "twitch.tv/xqc", "kick.com/adinross"). Pass precomputed `words`
    (from transcribe_words on the SAME uncut file) to skip re-transcribing —
    only valid when start/end are unset.

    `auto=True` runs the two-stage auto-editor (third_capture/auto_edit):
    Stage 1 retimes the clip into a dynamically edited program (punch-in
    zooms, slow-mo + replay of the money moment, dead-air speed-up, impact
    shake/flash, SFX); Stage 2 face-tracks the reframe and burns captions.
    Every layer degrades gracefully — on any failure this falls back to the
    plain reframe+captions render, so a clip always ships. Returns the ledger.
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
        t0 = max(0.0, words[0]["s"] - 0.8)
        t1 = min(src_dur, words[-1]["e"] + 2.2)
        if t1 - t0 > 45.0:
            cap = t0 + 45.0
            last_e = max((w["e"] for w in words if w["e"] <= cap - 1.0),
                         default=None)
            t1 = (last_e + 1.0) if last_e is not None else cap
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

        # ---- Stage 1: time-domain auto-edit (retime into a program) ----
        # Punch-in zooms, slow-mo + instant replay of the money moment,
        # dead-air speed-up, impact shake/flash, SFX. Never raises — on any
        # failure `program` stays the raw cut and words/dur are untouched, so
        # the simple render below still ships the clip.
        program = cut
        overlays: list[dict] = []
        ledger_ae = {"auto_edit": False, "fallback_reason": None,
                     "effects": [], "edl": None}
        if auto:
            try:
                from third_capture import auto_edit as ae
                st1 = ae.build(cut, words, dur, series, tmp, direct=direct)
                program, words, dur = st1["program"], st1["words"], st1["dur"]
                overlays = st1.get("overlays", [])
                ledger_ae = {k: st1[k] for k in
                             ("auto_edit", "fallback_reason", "effects", "edl")}
            except Exception as e:  # noqa: BLE001
                ledger_ae["fallback_reason"] = f"stage1:{type(e).__name__}"

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
                reframed, sp_summary = spn.build(program, tmp, analyze_on=cut)
                ledger_ae["shot_plan"] = sp_summary
            except Exception:  # noqa: BLE001
                reframed = None

        ass = build_ass(words, credit, dur, tmp / "caps.ass")

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
            _blur = (
                "[0:v]split=2[bg][fg];"
                f"[bg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
                "increase,crop=1080:1920,gblur=sigma=24,"
                "eq=brightness=-0.12:saturation=1.15[bgd];"
                "[fg]scale=1080:-2[fgs];"
                "[bgd][fgs]overlay=(W-w)/2:(H-h)/2[base]"
            )
            base_vf = _blur + f";[base]ass={ass}:fontsdir={FONTS_DIR}[capped]"
            plain_vf = _blur.replace("[base]", "[vout]")

        # ---- overlay effect layer (drawn on the final 1080x1920) ----
        # Text stamps (REPLAY) + hook card via drawtext textfile= (apostrophe-
        # safe), and a contextual reaction EMOJI that pops on the money moment
        # — the overlay energy the camera now holds still for. Emoji ride in as
        # extra image inputs; the graph and its inputs degrade together in the
        # render ladder so a bad overlay can never drop the clip.

        # Spatial safe-zones (§15): overlays pick a vertical position that
        # avoids the faces (bands exported by the shot plan) and the caption
        # zone, instead of hardcoded coordinates. Blur-fill wide look → the
        # centered source occupies the middle band.
        _bands = list((sp_summary or {}).get("face_bands")
                      or [[0.34, 0.66]])
        _bands.append([0.65, 0.80])                    # caption zone

        def _safe_y(cands: list[float], frac_h: float) -> float:
            for c in cands:
                if all(c + frac_h <= b0 or c >= b1 for b0, b1 in _bands):
                    return c
            return cands[0]

        emoji_y = _safe_y([0.15, 0.30, 0.50, 0.04], 0.16)
        word_y = _safe_y([0.40, 0.28, 0.55, 0.09], 0.09)
        # Text draws (top layer): REPLAY stamps, the big WORD slam, hook card.
        text_draws: list[str] = []
        for i, ov in enumerate(overlays):
            typ = ov.get("type")
            if typ in ("emoji", "lines"):
                continue
            if typ == "word":
                w = re.sub(r"[^A-Za-z0-9 !?']", "", str(ov.get("text", "")))[:14]
                if not w:
                    continue
                wf = tmp / f"word{i}.txt"
                wf.write_text(w)
                ws, we = float(ov["s"]), float(ov["e"])
                # slams in with a quick damped bounce, at the safe-zone y
                yb = (f"(H*{word_y:.3f})-55*exp(-7*(t-{ws:.2f}))"
                      f"*sin(15*(t-{ws:.2f}))")
                text_draws.append(
                    f"drawtext=fontfile={FONT_BOLD}:textfile={wf}:expansion=none"
                    ":fontsize=132:fontcolor=yellow:borderw=10:bordercolor=black"
                    f":x=(w-text_w)/2:y='{yb}'"
                    f":enable='between(t,{ws:.2f},{we:.2f})'")
                continue
            txt = re.sub(r"[^A-Za-z0-9 !?'.,]", "", str(ov.get("text", "")))[:24]
            if not txt:
                continue
            ovf = tmp / f"ov{i}.txt"
            ovf.write_text(txt)
            text_draws.append(
                f"drawtext=fontfile={FONT_BOLD}:textfile={ovf}:expansion=none"
                ":fontsize=64:fontcolor=white:box=1:boxcolor=red@0.75"
                ":boxborderw=18:x=(w-text_w)/2:y=150"
                f":enable='between(t,{ov['s']:.2f},{ov['e']:.2f})'")
        if hook:
            hf = tmp / "hook.txt"
            hf.write_text(hook)
            text_draws.append(
                f"drawtext=fontfile={FONT_BOLD}:textfile={hf}:expansion=none"
                ":fontsize=72:fontcolor=white:box=1:boxcolor=black@0.72"
                ":boxborderw=26:x=(w-text_w)/2:y=230"
                ":enable='between(t,0,3.0)'")

        # Image overlays (behind the text): speed-lines flash first, then the
        # emoji burst. Each -> (png, start, end, scale_h, x_expr). Asset-guarded.
        img_cues = []
        for ov in overlays:
            if ov.get("type") == "lines":
                png = FX_DIR / "speedlines.png"
                if png.exists():
                    img_cues.append((png, float(ov["s"]), float(ov["e"]),
                                     1180, "(W-w)/2"))
        for ov in overlays:
            if ov.get("type") == "emoji":
                png = EMOJI_DIR / f"{ov.get('name', '')}.png"
                if png.exists():
                    x = float(ov.get("x", 0.5))
                    img_cues.append((png, float(ov["s"]), float(ov["e"]),
                                     300, f"(W*{x:.3f})-w/2"))

        def _compose(with_text: bool, with_img: bool) -> tuple[str, list]:
            """Build (filter_complex, extra_input_paths) for the given layers."""
            parts, cur, inputs = [base_vf], "capped", []
            if with_img and img_cues:
                for k, (png, _s, _e, h, _x) in enumerate(img_cues):
                    inputs.append(png)
                    parts.append(f"[{k+1}:v]scale=-1:{h},format=rgba[i{k}]")
                for k, (_png, s, e, h, xe) in enumerate(img_cues):
                    nxt = f"im{k}"
                    if h <= 320:      # emoji — damped bounce at the safe y
                        ye = (f"(H*{emoji_y:.3f})-70*exp(-6*(t-{s:.2f}))"
                              f"*sin(14*(t-{s:.2f}))")
                    else:             # speed-lines — centered hard flash
                        ye = "(H-h)/2"
                    parts.append(
                        f"[{cur}][i{k}]overlay=x='{xe}':y='{ye}'"
                        f":enable='between(t,{s:.2f},{e:.2f})'[{nxt}]")
                    cur = nxt
            if with_text and text_draws:
                parts.append(f"[{cur}]" + ",".join(text_draws) + "[txt]")
                cur = "txt"
            parts.append(f"[{cur}]null[vout]")
            return ";".join(parts), inputs

        # §9: a 0.25s audio fade-out — the clip breathes out instead of the
        # audio slamming shut on the final frame
        afade = (f"loudnorm=I=-14:TP=-1.5,"
                 f"afade=t=out:st={max(0.0, dur - 0.25):.2f}:d=0.25")

        def _render(chain: str, extra_inputs: list | None = None) -> bool:
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
            for p in (extra_inputs or []):
                cmd += ["-i", str(p)]
            cmd += ["-filter_complex", chain, "-map", "[vout]", "-map", "0:a",
                    "-af", afade,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", str(out_path)]
            try:
                _run(cmd)
                return True
            except Exception:  # noqa: BLE001
                return False

        full_chain, full_inputs = _compose(with_text=True, with_img=True)
        text_chain, _ = _compose(with_text=True, with_img=False)
        caps_vf = base_vf.replace("[capped]", "[vout]")

        # Render ladder — a clip must ALWAYS ship. Full (captions + text
        # overlays + image FX) -> text overlays only (drop emoji/lines) ->
        # captions only -> plain reframe -> raw re-encode. Record what shipped.
        if _render(full_chain, full_inputs):
            render_level = "full"
        elif (text_draws or img_cues) and _render(text_chain):
            render_level = "text_only"
        elif _render(caps_vf):
            render_level = "captions_only"
        elif _render(plain_vf):
            render_level = "plain"
        else:
            _run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                  "-vf", f"scale={CANVAS_W}:{CANVAS_H}:"
                  "force_original_aspect_ratio=decrease,"
                  f"pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2",
                  "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                  "-pix_fmt", "yuv420p", "-r", "30",
                  "-c:a", "aac", "-b:a", "160k", str(out_path)])
            render_level = "raw"
        if render_level != "full":
            ledger_ae["render_fallback"] = render_level

    return {"kind": "twitch_clip", "credit": credit,
            "render_level": render_level,
            "cut": [t0, t1], "duration_s": round(dur, 2),
            "caption_words": len(words), "hook": hook,
            "reframe": "face" if reframed is not None else "blur",
            **ledger_ae}
