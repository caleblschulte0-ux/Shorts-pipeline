#!/usr/bin/env python3
"""THE PRO RENDERER (CURIOSITY_BRAIN §7.5 v10 — built from scratch).

The old spine — world_engine's cartoon Earth, the 3D bar slabs (monoliths), the
comparison lanes, the counters — is gone. This renderer assembles a video from
only the three grammars the operator picked on pixels:

    footage   real NASA footage, full-frame + matched move (footage_hybrid)
    flat2d    designed 2D motion graphics for numbers/ideas (flat2d)
    hero3d    rare stylized Blender showpieces, used 2-3x to POP (blender_hero)

A story is a SHOT LIST — an ordered list of shots, each with a narration line:

    {"kind": "footage",  "footage_nasa_id": "...", "push": 1.06, "line": "..."}
    {"kind": "flat_title","kicker": "...","title": "...", "line": "..."}
    {"kind": "flat_number","text":"828,000","sub":"KM / H","label":"...",
        "entity":"THE SUN","line":"..."}
    {"kind": "flat_compare","title":"...","rows":[{name,value,display},...],"line":...}
    {"kind": "flat_statement","statement":"...","line":"..."}
    {"kind": "hero3d","template":"earth_spin","line":"..."}

Each shot's on-screen length is derived from its narration (so the voice never
gets cut off), clips dissolve into each other, a music bed sits ducked under the
voice, and the whole thing is handed to the blind judge panel before anyone
sees it.

    python3 -m data_learning.pro_render <story.json> <out.mp4> [--work DIR]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import flat2d                         # noqa: E402
from data_learning import footage_hybrid as fh           # noqa: E402

W, H, FPS = 1920, 1080, 30
XFADE = 0.6
LEAD = 0.45          # silence before a line starts inside its shot
TAIL = 0.9           # breathing room after a line ends
MIN_SHOT = 2.8
VOICE = "en-US-GuyNeural"


def _run(cmd):
    subprocess.run(cmd, check=True)


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0.0)


# --- narration ------------------------------------------------------------
def _synth(line: str, dest: Path, voice: str) -> float:
    """edge-tts a single line; returns its audio duration. Falls back to a
    short silence if TTS is unavailable so the render never dies on a line."""
    if not line.strip():
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
              "anullsrc=r=48000:cl=mono", "-t", "0.4", str(dest)])
        return 0.0
    try:
        import edge_tts

        async def go():
            c = edge_tts.Communicate(line, voice, rate="-6%")
            await c.save(str(dest))
        asyncio.run(go())
        return _dur(dest)
    except Exception as e:  # noqa: BLE001
        print(f"[pro] TTS failed for {line[:40]!r} ({e}) — silent gap",
              file=sys.stderr)
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
              "anullsrc=r=48000:cl=mono", "-t", "1.5", str(dest)])
        return 0.0


# --- per-shot visual ------------------------------------------------------
def _footage_shot(shot: dict, seconds: float, out: Path, work: Path, idx: int):
    # cache sources by id — a story often reuses one long clip across beats,
    # and these downloads are hundreds of MB.
    nid = shot.get("footage_nasa_id")
    if not nid:
        hits = fh.search_footage(str(shot.get("footage_query", "")), limit=6)
        if not hits:
            raise RuntimeError(f"no footage for {shot.get('footage_query')!r}")
        nid = hits[0]["nasa_id"]
    safe = "".join(c if c.isalnum() else "_" for c in str(nid))[:60]
    src = work / f"srccache_{safe}.mp4"
    if not src.exists():
        fh.download_video(str(nid), src)
    # Operator spec §1: inspect the EXACT window and reject black / card /
    # diagram / cut segments — never pick a clip just because the id matched.
    if shot.get("ss") is not None:
        ss = float(shot["ss"])
        rep = fh.analyze_window(src, ss, seconds)
        if not rep["ok"]:
            print(f"[pro] pinned ss={ss} flagged {rep['flags']}; "
                  "re-picking a clean window", file=sys.stderr)
            ss = None
    else:
        ss = None
    if ss is None:
        picked, reports = fh.pick_window(src, seconds,
                                         at=float(shot.get("at", 0.5)))
        if picked is None:
            raise RuntimeError(
                f"no clean window in {nid} for a {seconds:.1f}s beat "
                f"(inspected {len(reports)})")
        ss = picked
    fh.full_frame_beat(src, ss, seconds, out,
                       push=float(shot.get("push", 1.05)),
                       direction=shot.get("direction", "in"))
    return out  # keep src cached; the story reuses it across beats


def _overlay_number(base: Path, shot: dict, out: Path):
    """Burn a hero number + unit + caption onto ANY base clip (footage OR a
    designed 2D clip). The number interacts with a moving world, never a static
    dashboard card."""
    anton = str(REPO / "assets" / "fonts" / "Anton-Regular.ttf")
    dj = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    num, sub = str(shot["text"]), str(shot.get("sub", ""))
    label = str(shot.get("label", "")).upper()
    esc = lambda s: s.replace(",", r"\,").replace(":", r"\:").replace("'", "")
    vf = [
        f"drawtext=fontfile={anton}:text='{esc(num)}':fontcolor=white:"
        f"fontsize=170:x=(w-tw)/2:y=h*0.60:shadowcolor=black@0.6:shadowx=3:"
        "shadowy=3:alpha='if(lt(t,0.5),0,min((t-0.5)/0.5,1))'",
        f"drawtext=fontfile={anton}:text='{esc(sub)}':fontcolor=0xFFD37A:"
        f"fontsize=52:x=(w-tw)/2:y=h*0.82:shadowcolor=black@0.6:shadowx=2:"
        "shadowy=2:alpha='if(lt(t,0.8),0,min((t-0.8)/0.5,1))'",
    ]
    if label:
        vf.insert(0, f"drawtext=fontfile={dj}:text='{esc(' '.join(label))}':"
                  "fontcolor=0xB9C4E0:fontsize=32:x=(w-tw)/2:y=h*0.50:"
                  "shadowcolor=black@0.7:shadowx=2:shadowy=2:"
                  "alpha='if(lt(t,0.3),0,min((t-0.3)/0.5,1))'")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base), "-vf",
          ",".join(vf), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
          "-pix_fmt", "yuv420p", str(out)])
    return out


def _overlay_text(base: Path, shot: dict, out: Path):
    """Burn a thesis/annotation line onto ANY base clip. role 'thesis' ->
    larger, centered; 'annotation' -> smaller, lower third."""
    import textwrap
    dj = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    role = shot.get("text_role", "thesis")
    text = str(shot.get("text", "")).strip()
    fs = 60 if role == "thesis" else 40
    y0 = 0.40 if role == "thesis" else 0.72
    wrapped = textwrap.wrap(text, 30 if role == "thesis" else 40)
    esc = lambda s: s.replace(",", r"\,").replace(":", r"\:").replace("'", "’")
    vf = [f"drawtext=fontfile={dj}:text='{esc(ln)}':fontcolor=white:"
          f"fontsize={fs}:x=(w-tw)/2:y=h*{y0}+{li * int(fs * 1.35)}:"
          "shadowcolor=black@0.7:shadowx=2:shadowy=3:"
          "alpha='if(lt(t,0.6),0,min((t-0.6)/0.7,1))'"
          for li, ln in enumerate(wrapped)]
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base), "-vf",
          ",".join(vf), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
          "-pix_fmt", "yuv420p", str(out)])
    return out


def _footage_number_shot(shot, seconds, out, work, idx):
    base = work / f"fn_base_{idx}.mp4"
    _footage_shot(shot, seconds, base, work, idx)
    return _overlay_number(base, shot, out)


def _footage_text_shot(shot, seconds, out, work, idx):
    base = work / f"ft_base_{idx}.mp4"
    _footage_shot(shot, seconds, base, work, idx)
    return _overlay_text(base, shot, out)


def _composite_shot(shot, seconds, out, work, idx):
    """Render the beat's designed-2D base (e.g. the galaxy pull-back), then
    overlay a number or text on it — for beats whose subject cannot be filmed
    (the galaxy: tier C). Kills FOOTAGE_MISMATCH (no Earth footage under a
    galaxy line) and gives the climax a DISTINCT image."""
    base_spec = dict(shot["base"])
    base = work / f"co_base_{idx}.mp4"
    _render_shot(base_spec, seconds, base, work, idx)
    if shot.get("text") is not None:
        return _overlay_text(base, shot, out)
    return _overlay_number(base, shot, out)


def _hero_shot(shot: dict, seconds: float, out: Path, work: Path, idx: int):
    """Render a Blender showpiece via blender_hero, dressed to 1080p. Kept for
    the 2-3 pop moments; falls back to a flat statement if Blender is absent."""
    import shutil
    if shutil.which("blender") is None:
        return flat2d.statement(shot.get("line", ""), out, seconds)
    rfps = int(shot.get("render_fps", 10))
    spec = dict(shot.get("spec", {}))
    spec.setdefault("template", shot.get("template", "earth_spin"))
    spec["seconds"] = seconds
    spec["fps"] = rfps
    spec.setdefault("continents", _continents())
    sj = work / f"hero_{idx}.json"
    sj.write_text(json.dumps(spec))
    raw = work / f"hero_{idx}_raw"
    raw.mkdir(exist_ok=True)
    _run(["blender", "-b", "--factory-startup", "--python",
          str(REPO / "data_learning" / "blender_hero.py"), "--",
          str(sj), str(raw)])
    frames = sorted(raw.glob("hero_*.png"))
    if not frames:
        return flat2d.statement(shot.get("line", ""), out, seconds)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(rfps),
          "-start_number", "1", "-i", str(raw / "hero_%04d.png"),
          "-vf", (f"minterpolate=fps={FPS}:mi_mode=mci,"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},format=yuv420p"),
          "-c:v", "libx264", "-crf", "18", "-preset", "medium", str(out)])
    return out


def _continents():
    try:
        from data_learning.continents import LANDMASSES
        return LANDMASSES
    except Exception:  # noqa: BLE001
        return None


def _render_shot(shot: dict, seconds: float, out: Path, work: Path, idx: int):
    k = shot["kind"]
    if k == "footage":
        return _footage_shot(shot, seconds, out, work, idx)
    if k == "footage_number":
        return _footage_number_shot(shot, seconds, out, work, idx)
    if k == "footage_text":
        return _footage_text_shot(shot, seconds, out, work, idx)
    if k == "composite":
        return _composite_shot(shot, seconds, out, work, idx)
    if k == "flat_number":
        return flat2d.number_reveal(
            shot["text"], shot.get("sub", ""), out, seconds,
            label=shot.get("label", ""), entity=shot.get("entity", ""))
    if k == "flat_compare":
        return flat2d.comparison(shot["rows"], out, seconds,
                                 title=shot.get("title", ""))
    if k == "flat_title":
        return flat2d.title_card(shot.get("kicker", ""), shot["title"], out,
                                 seconds)
    if k == "flat_statement":
        return flat2d.statement(shot["statement"], out, seconds)
    if k == "flat_orbit":
        return flat2d.orbit_reveal(shot.get("center", "THE SUN"),
                                   shot.get("satellite", "EARTH"), out,
                                   seconds)
    if k == "flat_zoom":
        return flat2d.cosmic_zoom(
            out, seconds, highlight=shot.get("highlight", "THE SUN"),
            stages=tuple(shot.get("stages",
                                  ["OUR SOLAR SYSTEM", "THE MILKY WAY"])))
    if k == "hero3d":
        return _hero_shot(shot, seconds, out, work, idx)
    raise RuntimeError(f"unknown shot kind {k!r}")


# --- assembly -------------------------------------------------------------
def build(story: dict, out: Path, work: Path, voice: str = VOICE) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    planned = "beats" in story
    if planned:
        # BEAT INTENT PLANNER: synth each beat's narration, then expand the
        # declared beats into a phased shot list (planner.py is the director).
        from data_learning.planner import plan_story
        beats = story["beats"]
        beat_durs = []
        for bi, b in enumerate(beats):
            bvf = work / f"beatvo_{bi}.mp3"
            beat_durs.append(_synth(b.get("narration", ""), bvf, voice))
        shots = plan_story(beats, beat_durs)
        print(f"[pro] planned {len(beats)} beats -> {len(shots)} shots")
    else:
        shots = story["shots"]
    # 1) narration per shot — the line rides only the phase that carries it.
    # For planned shots `seconds` is set by the planner; legacy shots derive it.
    vo_files, durs, seconds = [], [], []
    for i, sh in enumerate(shots):
        vf = work / f"vo_{i}.mp3"
        d = _synth(sh.get("line", ""), vf, voice)
        vo_files.append(vf)
        durs.append(d)
        if planned:
            seconds.append(float(sh.get("seconds", max(MIN_SHOT,
                           LEAD + d + TAIL))))
        else:
            seconds.append(max(MIN_SHOT, (LEAD + d + TAIL) if d else
                           float(sh.get("seconds", 4.0))))
        print(f"[pro] shot {i} {sh['kind']}: line {d:.1f}s -> "
              f"{seconds[-1]:.1f}s")
    # 2) render each shot's visual to its length
    clips = []
    for i, sh in enumerate(shots):
        c = work / f"shot_{i:02d}.mp4"
        _render_shot(sh, seconds[i], c, work, i)
        clips.append(c)
        print(f"[pro] shot {i} rendered -> {c.name}")
    # 3) dissolve-join the visuals
    silent = work / "silent.mp4"
    fh.dissolve_join(clips, silent, xfade=XFADE)
    total = _dur(silent)
    # 4) lay the voice at each shot's start offset (accounting for xfades)
    offset, delays, shot_start = 0.0, [], []
    for i in range(len(shots)):
        shot_start.append(offset)
        delays.append(offset + LEAD)
        offset += seconds[i] - XFADE
    amix_in, filt = [], []
    for i, vf in enumerate(vo_files):
        if durs[i] <= 0:
            continue
        amix_in += ["-i", str(vf)]
        filt.append(f"[{len(amix_in)//2 - 1}]adelay={int(delays[i]*1000)}|"
                    f"{int(delays[i]*1000)}[v{i}]")
    voice_lbls = "".join(f"[v{i}]" for i in range(len(shots)) if durs[i] > 0)
    vo_mix = work / "vo.m4a"
    _run(["ffmpeg", "-y", "-loglevel", "error", *amix_in, "-filter_complex",
          ";".join(filt) + f";{voice_lbls}amix=inputs="
          f"{voice_lbls.count('[')}:normalize=0,volume=2.0,"
          f"aresample=48000[vo]", "-map", "[vo]", "-t", f"{total:.2f}",
          str(vo_mix)])
    # 5) music bed, ducked under the voice
    music = _music_track()
    final_audio = work / "mix.m4a"
    if music:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo_mix),
              "-stream_loop", "-1", "-i", str(music), "-filter_complex",
              "[1:a]volume=0.18,aresample=48000[m];"
              "[m][0:a]sidechaincompress=threshold=0.03:ratio=6:release=800"
              "[duck];[duck][0:a]amix=inputs=2:normalize=0[a]",
              "-map", "[a]", "-t", f"{total:.2f}", str(final_audio)])
    else:
        final_audio = vo_mix
    # 5.5) AUDIO FINISHING (PRO_DOCTRINE — the mix measured true-peak over 0
    # dBFS). EBU R128 loudness to -14 LUFS + a hard true-peak limiter so the
    # ENCODED deliverable can never clip.
    mastered = work / "master.m4a"
    try:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final_audio),
              "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.9",
              "-ar", "48000", str(mastered)])
        final_audio = mastered
    except Exception as e:  # noqa: BLE001 — never fail the render on mastering
        print(f"[pro] audio mastering skipped ({e})", file=sys.stderr)
    # 6) mux
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i",
          str(final_audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
          "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
          "-shortest", str(out)])
    print(f"[pro] built {out}  ({_dur(out):.1f}s, {len(clips)} shots)")
    # 7) blind-judge package + 720p viewing copy
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-vf",
          "scale=1280:720", "-c:v", "libx264", "-preset", "slow", "-crf",
          "26", "-c:a", "aac", "-b:a", "128k",
          str(out.with_name(out.stem + "_720p.mp4"))])
    try:
        pkg = out.with_name(out.stem + "_pkg")
        _run([sys.executable, str(REPO / "scripts" / "visual_judge.py"),
              str(out), "--out", str(pkg), "--grid", "6x4"])
    except Exception as e:  # noqa: BLE001
        print(f"[pro] judge package skipped ({e})", file=sys.stderr)
    # 8) the REAL beat->time map (editorial package measures true boundaries,
    # not a hand-estimated guess). Only for planned stories, where each shot
    # carries `_beat`.
    if planned:
        try:
            _emit_beatmap(story, shots, shot_start, seconds,
                          out.with_name(out.stem + "_pkg"))
        except Exception as e:  # noqa: BLE001
            print(f"[pro] beatmap emission skipped ({e})", file=sys.stderr)
    return out


def _emit_beatmap(story, shots, shot_start, seconds, pkg):
    """Write pkg/beatmap.json: for each declared BEAT, the render's true
    [start,end] (from the first to the last of that beat's phased shots),
    plus the beat's job/narration/intended-understanding. This is the exact
    input scripts/editorial_review.py needs — no more guessing time ranges."""
    beats = story["beats"]
    ends = [shot_start[i] + seconds[i] for i in range(len(shots))]
    entries = []
    for bi, b in enumerate(beats):
        idxs = [i for i, sh in enumerate(shots) if sh.get("_beat") == bi]
        if not idxs:
            continue
        a = shot_start[idxs[0]]
        z = ends[idxs[-1]]
        entries.append({
            "t": f"{a:.1f}-{z:.1f}",
            "job": b.get("job", ""),
            "narration": b.get("narration", ""),
            "intended_understanding": b.get("understand", ""),
            "visual": b.get("mode", "") or b.get("function", ""),
        })
    pkg.mkdir(parents=True, exist_ok=True)
    bmap = {"topic": story.get("title", story.get("slug", "")),
            "beats": entries}
    (pkg / "beatmap.json").write_text(json.dumps(bmap, indent=2))
    print(f"[pro] beatmap -> {pkg / 'beatmap.json'} ({len(entries)} beats)")


def _music_track():
    for p in sorted((REPO / "data_learning" / "music").glob("*.mp3")) \
            if (REPO / "data_learning" / "music").exists() else []:
        return p
    return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("story", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--voice", default=VOICE)
    a = ap.parse_args(argv)
    story = json.loads(a.story.read_text())
    work = a.work or a.out.with_name(a.out.stem + "_work")
    build(story, a.out, work, voice=a.voice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
