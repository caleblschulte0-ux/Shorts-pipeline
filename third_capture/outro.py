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

Operator, 2026-10-21, of the first three-shot montage: *"need to be
significantly more basketball clips ... especially clips of just them on
the basketball court ... The cut is abrasive. Maybe make it like gray
... a little gray scale, just to make it sad ... just for this one"*. So
the montage runs `TARGET_SHOTS` shots, several from each good highlight
reel (`find_footage.find_many`), every one checked to show THEM on the
court; the song comes in under the last `PRELAP_S` of the clip and the
clip's last frame dissolves into the montage over `XFADE_S`, so nothing
it says is cut and the music arrives before the picture changes; and the
author picks the montage's `grade` per clip — `faded` by default, `grey`
for the sad edit.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SHOT_S = 2.4            # each shot of the montage
MIN_SHOTS = 2
MAX_SHOTS = 4           # looks the author may name
TARGET_SHOTS = 7        # shots the montage runs, taken across the looks
#: Each shot comes from a SHORT clip of one play, one or two per clip: a
#: long fan reel gave wide shots, cutaways and other players (2026-10-21:
#: a Hornets guard and a Kobe close-up in a KD/Russ tribute).
PLAY_MAX_S = 300        # a clip of a play, or the league's own short best-of
PER_CLIP = 3
#: A clip of them on opposite sides, when the tribute is to teammates
#: (2026-10-21: three shots of a "Westbrook vs Durant" video).
VERSUS = re.compile(r"\b(vs\.?|versus|against|v\.)\s", re.I)
XFADE_S = 1.0           # the clip's last frame dissolves into the montage
PRELAP_S = 5.0          # the song starts under the clip's last words
PRELAP_GAIN = 0.35      # ... quietly, under the voice, until the cut
TAIL_FADE_S = 1.2       # the song and the picture fade out together
#: The LAST shot plays the moment out instead of stopping at SHOT_S
#: (operator, 2026-10-21: *"why did we cut the clip at the end? ... At the
#: very least, let that last clip finish playing out"*).
LAST_MAX_S = 6.5
ONE_PLAY_S = 120        # a source this short is one play: run on past cuts
#: The montage's colour, chosen by the author per clip.
GRADES = {
    "faded": "eq=saturation=0.78:contrast=1.04",     # memory, not live
    "grey": "hue=s=0.12,eq=contrast=1.08:brightness=-0.03,vignette=PI/5",
}
LOOK = GRADES["faded"]


def _text(v, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def parse(raw) -> dict | None:
    """The author's `outro`, validated, or None."""
    from funnel import songs
    if not isinstance(raw, dict):
        return None
    song = songs.clean(raw.get("song"))
    who = _text(raw.get("who"), 80)
    people = [_text(x, 40) for x in (raw.get("people") or [])
              if isinstance(x, str) and _text(x, 40)][:4]
    looks = [_text(x, 90) for x in (raw.get("looks") or [])
             if isinstance(x, str) and _text(x, 90)][:MAX_SHOTS]
    if not (song and who and len(looks) >= MIN_SHOTS):
        return None
    grade = str(raw.get("grade") or "").strip().lower()
    return {"song": song, "who": who, "looks": looks,
            "people": people or [who],
            "numbers": [_text(x, 4) for x in (raw.get("numbers") or [])
                        if _text(x, 4)][:len(people)]
            if len(raw.get("numbers") or []) == len(people) else [],
            "team": _text(raw.get("team"), 40),
            "grade": grade if grade in GRADES else "faded"}


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30)
        return float((out.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def frame_look(look: str, people: list[str], team: str = "",
               numbers: list[str] | None = None) -> str:
    """What the brain must SEE in a montage frame (operator, 2026-10-21:
    *"the basketball clip was ass and not of Russ and KD"* — KD alone on
    the Warriors and Russ alone on the Clippers had passed as "them"; then
    KD on the Suns guarding Russ passed as "together")."""
    if len(people) > 1 and team and numbers:
        # the clip's TITLE names all of them (`title_has`); the frame has
        # to be their team's play with one of their numbers on it (a face
        # is too small to tell at broadcast distance; then: KD guarding
        # Russ passed as "together"; and asking for every number in one
        # frame refused all 17 frames of a "Top 10 connections" reel)
        nums = " or ".join(f"#{n}" for n in numbers)
        return (f"{look}: the play itself, a {team} player wearing {nums} "
                f"in a {team} uniform making it; NOT a player of another "
                "team, a close-up of one face, a far-away wide shot, a "
                "replay graphic, a studio or the crowd")
    if len(people) > 1 and team:
        # The clip's TITLE names every one of them (`title_has`); asking
        # the brain to pick both faces out of a 640px frame refused six
        # shots in seven (2026-10-21) and the montage was dropped.
        return (f"{look}: the play itself, {team} players in {team} "
                "uniforms on the court, close enough to see them; NOT a "
                "far-away wide shot, a close-up of one face, another "
                "team's player, a replay graphic, a studio or the crowd")
    if len(people) > 1:
        both = " and ".join(people)
        return (f"{look}: {both} BOTH clearly visible in this same frame, "
                "on the same team, as teammates, playing on the court; a "
                "frame with only one of them, neither, or them on opposing "
                "teams does not count")
    return f"{look}: {people[0]} clearly visible, playing on the court"


def shots(item: dict, work: Path, title: str = "") -> list[dict]:
    """The checked shots for the montage: `TARGET_SHOTS` across the
    looks, several from each good reel, every one of THEM on the court,
    none used twice."""
    from funnel import find_footage
    got, seen = [], set()
    looks = item["looks"]
    people = item.get("people") or [item["who"]]
    for i, look in enumerate(looks):
        left = TARGET_SHOTS - len(got)
        if left <= 0:
            break
        want = -(-left // (len(looks) - i))        # share what is left
        d = Path(work) / f"outro{i}"
        d.mkdir(parents=True, exist_ok=True)
        hits = find_footage.find_many(
            item["who"], frame_look(look, people, item.get("team", ""),
                                    item.get("numbers")),
            n=want, secs=SHOT_S, max_s=PLAY_MAX_S, per_video=PER_CLIP,
            title_not=VERSUS if item.get("team") else None, query=look,
            work=d, title=title, skip=seen,
            title_has=[n.split()[-1] for n in people] if len(people) > 1
            else None)
        got += hits
        print(f"[outro] {look!r}: {len(hits)} shot(s)", flush=True)
    return got[:TARGET_SHOTS]


def play_out(hit: dict, work: Path) -> dict:
    """`hit` re-cut to play its moment out: to the end of a short clip of
    one play (camera cuts and all), or to the end of its shot in a longer
    reel, at most `LAST_MAX_S`. The hit as it was when it cannot be."""
    from funnel import find_footage
    src, start = hit.get("source"), float(hit.get("from_s") or 0)
    if not src or not Path(src).exists():
        return hit
    total = float(hit.get("source_s") or 0)
    end = (total - 0.2 if 0 < total <= ONE_PLAY_S
           else float(hit.get("shot_end") or 0))
    length = min(LAST_MAX_S, end - start)
    if length <= float(hit.get("secs") or SHOT_S) + 0.3:
        return hit
    out = find_footage.cut(Path(src), start, length,
                           Path(work) / f"outro_last_{Path(src).stem}_"
                           f"{int(start * 10)}.mp4")
    if not out:
        return hit
    print(f"[outro] last shot plays out: {length:.1f}s", flush=True)
    return {**hit, "path": str(out), "secs": round(length, 2), "hold": True}


def graph(n: int, durs: list[float], clip_s: float, w: int, h: int,
          line_y: int | None, grade: str = "faded") -> str:
    """filter_complex joining input 0 (the rendered clip) to inputs 1..n
    (the shots), with input n+1 the song and, when line_y is set, input
    n+2 the line of text. Ends in [vout] and [aout]; runs clip_s +
    sum(durs): the clip's last frame is held under the dissolve, so
    nothing it says is cut."""
    look = GRADES.get(grade, LOOK)
    parts = []
    for i in range(n):
        k = i + 1
        parts.append(
            f"[{k}:v]setpts=PTS-STARTPTS,fps=30,setsar=1,split=2[b{k}][f{k}];"
            f"[b{k}]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma=24,eq=brightness=-0.05[bd{k}];"
            f"[f{k}]scale={w}:{h}:force_original_aspect_ratio=decrease:"
            f"force_divisible_by=2"
            f"[fs{k}];"
            f"[bd{k}][fs{k}]overlay=(W-w)/2:(H-h)/2,{look},format=yuv420p,"
            f"setsar=1,trim=0:{durs[i]:.2f},setpts=PTS-STARTPTS[s{k}]")
    parts.append("".join(f"[s{i + 1}]" for i in range(n))
                 + f"concat=n={n}:v=1:a=0[mont]")
    mont_s = sum(durs)
    total = clip_s + mont_s
    cur = "mont"
    if line_y is not None:
        parts.append(f"[{cur}][{n + 2}:v]overlay=0:{line_y}[montl]")
        cur = "montl"
    parts.append(f"[{cur}]fade=t=out:st={mont_s - TAIL_FADE_S:.2f}:"
                 f"d={TAIL_FADE_S},fps=30,settb=1/30[montf]")
    parts.append(f"[0:v]fps=30,format=yuv420p,setsar=1,"
                 f"tpad=stop_mode=clone:stop_duration={XFADE_S},"
                 f"settb=1/30[clipv];"
                 f"[clipv][montf]xfade=transition=fade:duration={XFADE_S}:"
                 f"offset={clip_s:.2f}[vout]")
    pre = min(PRELAP_S, clip_s * 0.5)
    song_s = pre + mont_s
    lead_ms = int((clip_s - pre) * 1000)
    parts.append(
        f"[{n + 1}:a]atrim=0:{song_s:.2f},asetpts=PTS-STARTPTS,"
        f"aformat=sample_rates=44100:channel_layouts=stereo,"
        f"loudnorm=I=-15:TP=-1.5,"
        # rises to PRELAP_GAIN under the voice, then up to full at the cut
        f"volume='if(lt(t,{pre:.2f}),{PRELAP_GAIN}*t/{max(pre, 0.01):.2f},"
        f"min(1,{PRELAP_GAIN}+(1-{PRELAP_GAIN})*(t-{pre:.2f})/0.8))'"
        f":eval=frame,"
        f"afade=t=out:st={song_s - TAIL_FADE_S:.2f}:d={TAIL_FADE_S},"
        f"adelay={lead_ms}|{lead_ms}[song];"
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        f"apad=whole_dur={total:.2f}[clipa];"
        f"[clipa][song]amix=inputs=2:duration=longest:normalize=0,"
        f"atrim=0:{total:.2f}[aout]")
    return ";".join(parts)


def _render(clip: Path, got: list[dict], song: Path, out: Path,
            clip_s: float, w: int, h: int, line_png, line_y,
            grade: str = "faded") -> list | None:
    """One try at joining `got` to the clip into `out`; the shot lengths,
    or None with ffmpeg's own reason printed."""
    durs = [min(LAST_MAX_S if g.get("hold") else SHOT_S,
                float(g.get("secs") or SHOT_S)) for g in got]
    with_line = bool(line_png) and line_y is not None
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(clip)]
    for g in got:
        cmd += ["-i", str(g["path"])]
    cmd += ["-i", str(song)]
    if with_line:
        cmd += ["-loop", "1", "-i", str(line_png)]
    cmd += ["-filter_complex",
            graph(len(got), durs, clip_s, w, h,
                  line_y if with_line else None, grade),
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{clip_s + sum(durs):.3f}",
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
        if clip_s <= 3:
            return None
        out = Path(work) / "with_outro.mp4"
        # a shot ffmpeg cannot join is dropped, not the whole tribute
        tries = [got] + ([got[:i] + got[i + 1:] for i in range(len(got))]
                         if len(got) > MIN_SHOTS else [])
        for use in tries:
            use = use[:-1] + [play_out(use[-1], work)]
            durs = _render(clip, use, song, out, clip_s, w, h,
                           line_png, line_y, item.get("grade", "faded"))
            if durs:
                got = use
                break
        else:
            return None
        out.replace(clip)
        print(f"[outro] {item['song']} over {len(got)} {item.get('grade')} "
              f"shots of {item['who']!r}", flush=True)
        return {"song": item["song"], "grade": item.get("grade", "faded"),
                "shots": [g["url"] for g in got],
                "secs": round(sum(durs), 2)}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[outro] failed ({type(e).__name__}) — the clip "
              "ships without it", flush=True)
        return None
