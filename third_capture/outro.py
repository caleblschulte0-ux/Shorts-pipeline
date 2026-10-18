"""The TRIBUTE ending: the clip plays untouched, then a real sad song over
a montage of the people it was about.

Operator, 2026-10-18, after the cut-ins (third_capture/cut_in.py, which
stay the standard for any clip that names something): *"when Kevin
Durant was talking about how sad he was that him and Russ aren't playing
anymore, you play just that clip, and then after that clip's done, play
some sad music, and then cut to, like, clips of them playing together
... Not what you just did, not two overlays on top ... they're two
different situations"*.

The author marks it (`edit.outro`: the song, who it is about, and two to
four shots of them to show, in search words); after the clip is
rendered, `build` finds each shot through the SHARED finder
(`funnel/find_footage.py`: game footage, checked by the brain), lays the
song (`funnel/songs.py`) under them alone, with the clip's line of text
on top, and joins the montage to the end of the clip with a short
crossfade. Fewer than `MIN_SHOTS` checked shots, or no song, and the
clip ships as it was: an outro of one shot is a cut-in, not a tribute.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SHOT_S = 2.8            # each shot of the montage
MIN_SHOTS = 2
MAX_SHOTS = 4
XFADE_S = 0.5           # clip -> montage
TAIL_FADE_S = 1.6       # the song and the picture fade out together
LOOK = "eq=saturation=0.78:contrast=1.04"   # a little faded: memory, not live


def _text(v, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def parse(raw) -> dict | None:
    """The author's `outro`, validated, or None."""
    from funnel import songs
    if not isinstance(raw, dict):
        return None
    song = songs.clean(raw.get("song"))
    who = _text(raw.get("who"), 80)
    looks = [_text(x, 90) for x in (raw.get("looks") or [])
             if isinstance(x, str) and _text(x, 90)][:MAX_SHOTS]
    if not (song and who and len(looks) >= MIN_SHOTS):
        return None
    return {"song": song, "who": who, "looks": looks}


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30)
        return float((out.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def shots(item: dict, work: Path, title: str = "") -> list[dict]:
    """The checked shots for the montage, one per look, each distinct."""
    from funnel import find_footage
    got, seen = [], set()
    for i, look in enumerate(item["looks"]):
        d = Path(work) / f"outro{i}"
        d.mkdir(parents=True, exist_ok=True)
        hit = find_footage.find(item["who"], look, secs=SHOT_S, work=d,
                                title=title)
        key = (hit or {}).get("url"), round((hit or {}).get("from_s") or 0)
        if hit and key not in seen:
            seen.add(key)
            got.append(hit)
        print(f"[outro] {look!r}: {'shot' if hit else 'no checked footage'}",
              flush=True)
    return got


def graph(n: int, durs: list[float], clip_s: float, w: int, h: int,
          line_y: int | None) -> str:
    """filter_complex joining input 0 (the rendered clip) to inputs 1..n
    (the shots), with input n+1 the song and, when line_y is set, input
    n+2 the line of text. Ends in [vout] and [aout]."""
    parts = []
    for i in range(n):
        k = i + 1
        parts.append(
            f"[{k}:v]setpts=PTS-STARTPTS,fps=30,setsar=1,split=2[b{k}][f{k}];"
            f"[b{k}]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma=24,eq=brightness=-0.05[bd{k}];"
            f"[f{k}]scale={w}:{h}:force_original_aspect_ratio=decrease"
            f"[fs{k}];"
            f"[bd{k}][fs{k}]overlay=(W-w)/2:(H-h)/2,{LOOK},format=yuv420p,"
            f"trim=0:{durs[i]:.2f},setpts=PTS-STARTPTS[s{k}]")
    parts.append("".join(f"[s{i + 1}]" for i in range(n))
                 + f"concat=n={n}:v=1:a=0[mont]")
    mont_s = sum(durs)
    cur = "mont"
    if line_y is not None:
        parts.append(f"[{cur}][{n + 2}:v]overlay=0:{line_y}[montl]")
        cur = "montl"
    parts.append(f"[{cur}]fade=t=out:st={mont_s - TAIL_FADE_S:.2f}:"
                 f"d={TAIL_FADE_S},fps=30,settb=1/30[montf]")
    parts.append(f"[0:v]fps=30,format=yuv420p,setsar=1,settb=1/30[clipv];"
                 f"[clipv][montf]xfade=transition=fade:duration={XFADE_S}:"
                 f"offset={clip_s - XFADE_S:.2f}[vout]")
    parts.append(
        f"[{n + 1}:a]atrim=0:{mont_s:.2f},asetpts=PTS-STARTPTS,"
        f"aformat=sample_rates=44100:channel_layouts=stereo,"
        f"loudnorm=I=-15:TP=-1.5,afade=t=in:st=0:d=0.6,"
        f"afade=t=out:st={mont_s - TAIL_FADE_S:.2f}:"
        f"d={TAIL_FADE_S}[song];"
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[clipa];"
        f"[clipa][song]acrossfade=d={XFADE_S}[aout]")
    return ";".join(parts)


def _render(clip: Path, got: list[dict], song: Path, out: Path,
            clip_s: float, w: int, h: int, line_png, line_y) -> list | None:
    """One try at joining `got` to the clip into `out`; the shot lengths,
    or None with ffmpeg's own reason printed."""
    durs = [min(SHOT_S, float(g.get("secs") or SHOT_S)) for g in got]
    with_line = bool(line_png) and line_y is not None
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(clip)]
    for g in got:
        cmd += ["-i", str(g["path"])]
    cmd += ["-i", str(song)]
    if with_line:
        cmd += ["-loop", "1", "-i", str(line_png)]
    cmd += ["-filter_complex",
            graph(len(got), durs, clip_s, w, h,
                  line_y if with_line else None),
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{clip_s - XFADE_S + sum(durs):.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "160k", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or _seconds(out) < clip_s:
        tail = " | ".join((r.stderr or "").strip().splitlines()[-3:])
        print(f"[outro] {len(got)} shots would not join: {tail[:300]}",
              flush=True)
        return None
    return durs


def build(clip: Path, item: dict, work: Path, *, w: int, h: int,
          line_png: Path | None = None, line_y: int | None = None,
          title: str = "") -> dict | None:
    """Append the tribute montage to `clip` IN PLACE. Returns what was
    added ({"song", "shots", "secs"}) or None, leaving `clip` as it was.
    Never raises."""
    from funnel import songs
    try:
        song = songs.get(item["song"])
        if song is None:
            print(f"[outro] song {item['song']} not fetched — no outro",
                  flush=True)
            return None
        got = shots(item, work, title)
        if len(got) < MIN_SHOTS:
            print(f"[outro] {len(got)} checked shot(s) — no outro",
                  flush=True)
            return None
        clip_s = _seconds(clip)
        if clip_s <= XFADE_S + 1:
            return None
        out = Path(work) / "with_outro.mp4"
        # a shot ffmpeg cannot join is dropped, not the whole tribute
        tries = [got] + ([got[:i] + got[i + 1:] for i in range(len(got))]
                         if len(got) > MIN_SHOTS else [])
        for use in tries:
            durs = _render(clip, use, song, out, clip_s, w, h,
                           line_png, line_y)
            if durs:
                got = use
                break
        else:
            return None
        out.replace(clip)
        print(f"[outro] {item['song']} over {len(got)} shots of "
              f"{item['who']!r}", flush=True)
        return {"song": item["song"], "shots": [g["url"] for g in got],
                "secs": round(sum(durs) - XFADE_S, 2)}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[outro] failed ({type(e).__name__}) — the clip "
              "ships without it", flush=True)
        return None
