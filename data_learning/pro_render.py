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
from data_learning import scenes                          # noqa: E402
from data_learning import footage_hybrid as fh           # noqa: E402

W, H, FPS = 1920, 1080, 30
XFADE = 0.6
LEAD = 0.45          # silence before a line starts inside its shot
TAIL = 0.9           # breathing room after a line ends
MIN_SHOT = 2.8
VOICE = "en-US-GuyNeural"


# Attribution ledger — CC BY / BY-SA imagery pulled through the media gateway
# needs credit. Every image shot appends its source here; build() writes it to
# the package as credits.json / CREDITS.txt so the operator can attribute.
_ATTRIB: list[dict] = []

# FALLBACK ledger — every time the render degrades (TTS→silence, motion→still,
# a missing image, a swallowed sidecar), it is recorded here with a SEVERITY so
# the producer can decide pass / quarantine / fail instead of pretending the
# render "succeeded" (audit: "render completed ≠ quality preserved"). Severities:
#   equivalent   — an acceptable substitution; publish normally.
#   degraded     — reviewable; the producer should re-judge before publishing.
#   unacceptable — the video FAILS: never ship this render.
_FALLBACKS: list[dict] = []


def _fallback(kind: str, severity: str, detail: str = "", beat=None) -> None:
    _FALLBACKS.append({"kind": kind, "severity": severity, "detail": detail,
                       "beat": beat})
    print(f"[pro] FALLBACK[{severity}] {kind}: {detail}", file=sys.stderr)


def _fallback_verdict() -> str:
    """Worst severity across the ledger: ok < degraded < unacceptable."""
    order = {"equivalent": 0, "degraded": 1, "unacceptable": 2}
    worst = max((order.get(f["severity"], 1) for f in _FALLBACKS), default=0)
    return {0: "ok", 1: "degraded", 2: "unacceptable"}[worst]


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
        # a real narration line lost to silence is UNACCEPTABLE (audit) — the
        # render must not pass. Keep the silent gap so assembly still completes
        # and the producer can quarantine, but flag it hard.
        _fallback("tts_silence", "unacceptable",
                  f"narration lost to silence: {line[:50]!r} ({e})")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
              "anullsrc=r=48000:cl=mono", "-t", "1.5", str(dest)])
        return 0.0


# --- per-shot visual ------------------------------------------------------
def _footage_shot(shot: dict, seconds: float, out: Path, work: Path, idx: int):
    # cache sources by id — a story often reuses one long clip across beats,
    # and these downloads are hundreds of MB.
    local = shot.get("_local_src")     # a clip the MOTION-FIRST gate already got
    if local:
        src = Path(local)
    else:
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
                f"no clean window in {src.name} for a {seconds:.1f}s beat "
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
        # the context caption above the number — brighter + stronger shadow so
        # it reads against bright footage (a faint caption leaves a bare number
        # like "26" cryptic; the caption is what says what the number MEANS).
        vf.insert(0, f"drawtext=fontfile={dj}:text='{esc(' '.join(label))}':"
                  "fontcolor=0xEAF0FF:fontsize=34:x=(w-tw)/2:y=h*0.50:"
                  "shadowcolor=black@0.9:shadowx=2:shadowy=2:borderw=1:"
                  "bordercolor=black@0.5:"
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


def _image_source(shot: dict, work: Path, idx: int) -> dict:
    """Resolve an image shot to a real photo on disk via the MEDIA GATEWAY.
    A shot may pin a direct ``image_url`` (+ optional attribution) or declare an
    ``image_query`` (+ perspective) and let the gateway pick the highest-appeal
    commercial-licensed photo. The chosen image's attribution is recorded for
    the CC credits sidecar."""
    from data_learning import media
    # cache key by QUERY (not shot idx) so every chunk of one image beat — and any
    # later re-render — reuses a single download instead of re-hitting the (flaky,
    # rate-limited) media API. A sidecar .json carries the attribution across reuse.
    key = str(shot.get("image_query") or shot.get("image_url") or idx)
    safe = "".join(c if c.isalnum() else "_" for c in key)[:60]
    dest = work / f"img_{safe}.jpg"
    side = dest.with_suffix(".json")
    if dest.exists() and dest.stat().st_size > 4096 and side.exists():
        try:
            cand = json.loads(side.read_text())
            cand["path"] = str(dest)
            return cand
        except Exception:  # noqa: BLE001 — a corrupt sidecar just re-resolves
            pass
    if shot.get("image_url"):
        cand = {"source": shot.get("image_source", "pinned"),
                "url": shot["image_url"], "kind": "image",
                "license": shot.get("image_license", ""),
                "attribution": shot.get("image_attribution", ""),
                "title": shot.get("image_title", "")}
        try:
            if not dest.exists() or dest.stat().st_size < 1024:
                media.acquire(cand, dest)      # re-fetch if missing/truncated
            cand["path"] = str(dest)
            side.write_text(json.dumps(cand))
            return cand
        except Exception as e:  # noqa: BLE001 — a rotted hotlink falls back to
            print(f"[pro] pinned image failed ({str(e)[:60]}); "  # a live search
                  "falling back to the media gateway", file=sys.stderr)
            if not shot.get("image_query"):
                raise
    # ROBUST: an ACCENT photo missing must never kill a whole render. Try the
    # requested appeal floor, then progressively lower floors (take the best the
    # gateway can find) before giving up. Only a total gateway miss raises.
    floor0 = float(shot.get("min_appeal", 0.42))
    for floor in (floor0, 0.25, 0.12, 0.0):
        if floor > floor0:
            continue
        picked = media.best_image(
            str(shot["image_query"]), dest,
            perspective=shot.get("perspective", ""),
            min_appeal=floor, must_match=shot.get("must_match"))
        if picked is not None:
            if floor < floor0:
                # a photo taken well below the requested appeal floor is a
                # DEGRADED beat; below ~0.12 it is effectively "any image" and
                # unacceptable for a flagship shot.
                _fallback("image_low_appeal",
                          "unacceptable" if floor < 0.12 else "degraded",
                          f"{shot.get('image_query')!r} took best at floor "
                          f"{floor} (wanted {floor0})")
            try:
                side.write_text(json.dumps(picked))
            except Exception:  # noqa: BLE001
                pass
            return picked
    raise RuntimeError(
        f"media gateway found NO photo at all for "
        f"{shot.get('image_query')!r} — perspective "
        f"{shot.get('perspective', '')!r}")


def _depict_source(shot: dict, seconds: float, work: Path, idx: int):
    """MOTION-FIRST resolution for a DEPICTION shot. Ask the gate for a moving
    clip of the subject; on a hit, return ('video', footage_shot_dict); on a
    miss, fall back to the declared still and return ('image', None). The
    decision (and WHY, when it falls back) is logged so a still is never a silent
    default — only an earned one."""
    from data_learning import media
    q = str(shot.get("motion_query", "")).strip()
    if q:
        hit = media.motion_first(
            q, seconds, work, perspective=str(shot.get("perspective", "")),
            log=lambda m: print(m, file=sys.stderr))
        if hit:
            # hand the resolved clip to the normal footage path: a local file
            # (already downloaded by the gate) pinned to its clean window.
            foot = {"kind": "footage", "seconds": seconds,
                    "ss": hit["ss"], "push": float(shot.get("push", 1.06)),
                    "direction": shot.get("direction", "in"),
                    "_local_src": hit["path"],
                    "footage_nasa_id": hit.get("nasa_id") or f"mf_{idx}"}
            _ATTRIB.append({"idx": idx, "source": hit.get("source"),
                            "license": hit.get("license"),
                            "attribution": hit.get("title"),
                            "title": hit.get("title")})
            return "video", foot
    print(f"[pro] depict {q!r}: no moving clip — using the still fallback",
          file=sys.stderr)
    return "image", None


def _depict_shot(shot, seconds, out, work, idx):
    mode, foot = _depict_source(shot, seconds, work, idx)
    if mode == "video":
        return _footage_shot(foot, seconds, out, work, idx)
    try:
        return _image_shot(shot, seconds, out, work, idx)
    except Exception as e:  # noqa: BLE001 — escalation must NEVER kill a render:
        # motion missed AND no usable still -> keep the beat's designed treatment,
        # but flag it: a statement card standing in for intended media is DEGRADED.
        _fallback("depict_to_statement", "degraded",
                  f"{shot.get('motion_query')!r}: no motion, no still "
                  f"({str(e)[:50]})", beat=shot.get("_beat"))
        return flat2d.statement(shot.get("line", "") or shot.get("text", ""),
                                out, seconds)


def _depict_text_shot(shot, seconds, out, work, idx):
    mode, foot = _depict_source(shot, seconds, work, idx)
    if mode == "video":
        base = work / f"dt_base_{idx}.mp4"
        _footage_shot(foot, seconds, base, work, idx)
        return _overlay_text(base, shot, out)
    try:
        return _image_text_shot(shot, seconds, out, work, idx)
    except Exception as e:  # noqa: BLE001 — see _depict_shot: never crash.
        _fallback("depict_to_statement", "degraded",
                  f"{shot.get('motion_query')!r}: no motion, no still "
                  f"({str(e)[:50]})", beat=shot.get("_beat"))
        base = work / f"dt_fallback_{idx}.mp4"
        flat2d.statement(shot.get("line", ""), base, seconds)
        return _overlay_text(base, shot, out)


def _image_shot(shot, seconds, out, work, idx):
    try:
        src = _image_source(shot, work, idx)
    except Exception as e:  # noqa: BLE001 — a missing ACCENT never kills a render:
        # degrade to a designed statement of the beat's own line, and flag it.
        _fallback("image_to_statement", "degraded",
                  f"{shot.get('image_query')!r}: no photo ({str(e)[:60]})",
                  beat=shot.get("_beat"))
        # A degraded beat must NOT dump the narration as a wall of text — and it
        # must NEVER burn the raw search QUERY on screen (a stock-descriptor like
        # "friends laughing outdoors" reads as an unfinished artifact). Show only a
        # short clause of the actual narration line; a silent development cut with
        # no line falls back to a clean drifting field (no text at all).
        line = (shot.get("line", "") or "").strip()
        short = line.split(".")[0].strip()
        if len(short.split()) > 6:
            short = " ".join(short.split()[:6])
        return flat2d.statement(short, out, seconds)
    _ATTRIB.append({"idx": idx, "source": src.get("source"),
                    "license": src.get("license"),
                    "attribution": src.get("attribution"),
                    "title": src.get("title")})
    fh.image_beat(Path(src["path"]), seconds, out,
                  push=float(shot.get("push", 1.14)),
                  direction=shot.get("direction", "in"),
                  pan=shot.get("pan", "auto"))
    return out


def _image_text_shot(shot, seconds, out, work, idx):
    base = work / f"imt_base_{idx}.mp4"
    _image_shot(shot, seconds, base, work, idx)
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
        _fallback("blender_missing", "degraded",
                  "Blender absent — hero beat became a statement card",
                  beat=shot.get("_beat"))
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
        _fallback("blender_no_frames", "degraded",
                  "Blender produced no frames — hero beat became a statement",
                  beat=shot.get("_beat"))
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
    if k == "image":
        return _image_shot(shot, seconds, out, work, idx)
    if k == "image_text":
        return _image_text_shot(shot, seconds, out, work, idx)
    if k == "depict":
        return _depict_shot(shot, seconds, out, work, idx)
    if k == "depict_text":
        return _depict_text_shot(shot, seconds, out, work, idx)
    if k == "composite":
        return _composite_shot(shot, seconds, out, work, idx)
    if k == "flat_number":
        return flat2d.number_reveal(
            shot["text"], shot.get("sub", ""), out, seconds,
            label=shot.get("label", ""), entity=shot.get("entity", ""),
            extra=shot.get("extra"))
    if k == "flat_compare":
        return flat2d.comparison(shot["rows"], out, seconds,
                                 title=shot.get("title", ""))
    if k == "flat_title":
        return flat2d.title_card(shot.get("kicker", ""), shot["title"], out,
                                 seconds)
    if k == "flat_statement":
        return flat2d.statement(shot["statement"], out, seconds)
    if k == "flat_hidden_motion":
        return flat2d.hidden_motion(
            shot.get("text", "0"), out, seconds, sub=shot.get("sub", "MPH"),
            label=shot.get("label", "YOU'RE MOVING AT"), extra=shot.get("extra"))
    if k == "flat_spin":
        return flat2d.spinning_world(
            shot.get("text", "0"), out, seconds, sub=shot.get("sub", "MPH"),
            label=shot.get("label", "THE EARTH'S SPIN"), extra=shot.get("extra"))
    if k in ("scene_sleep", "scene_work", "scene_screen", "scene_free",
             "scene_queue", "scene_traffic", "scene_hold", "scene_walkout",
             "scene_paycheck", "scene_tax", "scene_rent", "scene_gas",
             "scene_grocery", "scene_subs", "scene_savings", "scene_treadmill"):
        fn = {"scene_sleep": scenes.sleep_scene, "scene_work": scenes.work_scene,
              "scene_screen": scenes.screen_scene, "scene_free": scenes.free_scene,
              "scene_queue": scenes.queue_scene, "scene_traffic": scenes.traffic_scene,
              "scene_hold": scenes.hold_scene, "scene_walkout": scenes.walkout_scene,
              "scene_paycheck": scenes.paycheck_scene, "scene_tax": scenes.tax_scene,
              "scene_rent": scenes.rent_scene, "scene_gas": scenes.gas_scene,
              "scene_grocery": scenes.grocery_scene, "scene_subs": scenes.subs_scene,
              "scene_savings": scenes.savings_scene,
              "scene_treadmill": scenes.treadmill_scene}[k]
        scenes.set_mood(shot.get("mood"))       # per-chapter color world
        return fn(out, seconds, number=str(shot.get("number", "")),
                  label=str(shot.get("label", "")))
    if k == "scene_money":
        scenes.set_mood(shot.get("mood"))       # per-chapter color world
        return scenes.money_scene(out, seconds, upto=int(shot.get("upto", 0)),
                                  final=bool(shot.get("final", False)),
                                  number=str(shot.get("number", "")),
                                  label=str(shot.get("label", "")))
    if k == "flat_life_grid":
        return flat2d.life_grid(
            out, seconds, segments=shot.get("segments"),
            total_years=int(shot.get("total_years", 76)),
            final_label=shot.get("final_label", "YOURS"),
            extra=shot.get("extra"))
    if k == "flat_shrinking_years":
        return flat2d.shrinking_years(
            out, seconds, label=shot.get("label", "HOW LONG EACH YEAR FEELS"),
            you_age=int(shot.get("you_age", 25)),
            max_age=int(shot.get("max_age", 60)), extra=shot.get("extra"))
    if k == "flat_orbit":
        return flat2d.orbit_reveal(shot.get("center", "THE SUN"),
                                   shot.get("satellite", "EARTH"), out,
                                   seconds)
    if k == "flat_zoom":
        return flat2d.cosmic_zoom(
            out, seconds, highlight=shot.get("highlight", "THE SUN"),
            stages=tuple(shot.get("stages",
                                  ["OUR SOLAR SYSTEM", "THE MILKY WAY"])))
    if k == "flat_hook":
        return flat2d.hook_card(shot["text"], shot.get("sub", ""), out, seconds,
                                line=shot.get("label", ""))
    if k == "flat_engine":
        return flat2d.heat_engine(
            out, seconds,
            stages=tuple(shot.get("stages",
                         ["WARM OCEAN", "RISING, COOLING AIR",
                          "HEAT RELEASED"])))
    if k == "hero3d":
        return _hero_shot(shot, seconds, out, work, idx)
    raise RuntimeError(f"unknown shot kind {k!r}")


# --- assembly -------------------------------------------------------------
def build(story: dict, out: Path, work: Path, voice: str = VOICE) -> dict:
    """Render a story and RETURN A STRUCTURED RESULT (not just a path), so the
    producer can decide pass / quarantine / fail instead of trusting that a
    completed file means a good film. Result:
        {"out", "duration", "shots", "pkg", "fallbacks", "verdict"}
    where verdict is ok / degraded / unacceptable (worst fallback severity)."""
    work.mkdir(parents=True, exist_ok=True)
    _ATTRIB.clear()
    _FALLBACKS.clear()
    planned = "beats" in story
    if planned:
        # BEAT INTENT PLANNER: synth each beat's narration, then expand the
        # declared beats into a phased shot list (planner.py is the director).
        from data_learning.planner import plan_story
        from data_learning import contrast_director   # medium variety
        beats = story["beats"]
        contrast_director.contrast_pass(beats)         # cut real footage into
        beat_durs = []                                 # long animation runs
        for bi, b in enumerate(beats):
            bvf = work / f"beatvo_{bi}.mp3"
            beat_durs.append(_synth(b.get("narration", ""), bvf, voice))
        shots = plan_story(beats, beat_durs)
        from data_learning import extra_director   # the "be extra" pass
        extra_director.apply(shots)                # attach escalating character
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
        _fallback("audio_mastering", "degraded", f"mastering skipped ({e})")
    # 6) mux
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i",
          str(final_audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
          "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
          "-shortest", str(out)])
    total = _dur(out)
    print(f"[pro] built {out}  ({total:.1f}s, {len(clips)} shots)")
    pkg = out.with_name(out.stem + "_pkg")
    beats = story.get("beats", [])
    # 7) 720p viewing copy
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-vf",
          "scale=1280:720", "-c:v", "libx264", "-preset", "slow", "-crf",
          "26", "-c:a", "aac", "-b:a", "128k",
          str(out.with_name(out.stem + "_720p.mp4"))])
    # 8) blind-judge EVIDENCE package (verdicts are enforced by the producer,
    # scripts/produce.py — a missing package is DEGRADED, not silently fine).
    try:
        _run([sys.executable, str(REPO / "scripts" / "visual_judge.py"),
              str(out), "--out", str(pkg), "--grid", "6x4"])
    except Exception as e:  # noqa: BLE001
        _fallback("judge_package", "degraded", f"visual_judge package failed ({e})")
    # 9) the REAL beat->time map + continuity — required inputs for the judges.
    if planned:
        try:
            _emit_beatmap(story, shots, shot_start, seconds, pkg)
        except Exception as e:  # noqa: BLE001
            _fallback("beatmap", "degraded", f"beatmap emission failed ({e})")
        try:
            _check_continuity(story, shots, clips, pkg)
        except Exception as e:  # noqa: BLE001
            _fallback("continuity", "degraded", f"continuity check failed ({e})")
    # 10) PUBLISHING PACKAGE — the sidecars the publisher consumes (parity with
    # the legacy renderer): chapters/duration/sources, captions, thumbnail.
    try:
        _emit_meta(story, beats, shots, shot_start, total, out)
    except Exception as e:  # noqa: BLE001
        _fallback("meta", "unacceptable", f"meta.json emission failed ({e})")
    try:
        _emit_srt(shots, shot_start, durs, out)
    except Exception as e:  # noqa: BLE001
        _fallback("captions", "unacceptable", f"srt emission failed ({e})")
    try:
        _emit_thumbnail(out, total, story.get("title", ""))
    except Exception as e:  # noqa: BLE001
        _fallback("thumbnail", "degraded", f"thumbnail failed ({e})")
    # 11) CC attribution
    if _ATTRIB:
        try:
            _emit_credits(pkg)
        except Exception as e:  # noqa: BLE001
            _fallback("credits", "degraded", f"credits emission failed ({e})")
    # 12) fallback report + structured verdict
    pkg.mkdir(parents=True, exist_ok=True)
    verdict = _fallback_verdict()
    (pkg / "fallbacks.json").write_text(json.dumps(
        {"verdict": verdict, "fallbacks": list(_FALLBACKS)}, indent=2))
    print(f"[pro] fallback verdict = {verdict} ({len(_FALLBACKS)} recorded)")
    return {"out": out, "duration": total, "shots": len(shots), "pkg": pkg,
            "fallbacks": list(_FALLBACKS), "verdict": verdict}


def _emit_credits(pkg: Path):
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "credits.json").write_text(json.dumps(_ATTRIB, indent=2))
    lines = ["IMAGE CREDITS (Creative Commons — attribution required for "
             "BY / BY-SA)", ""]
    for a in _ATTRIB:
        cred = a.get("attribution") or a.get("title") or "(unknown)"
        lines.append(f"- {cred}  [{a.get('source', '')} / "
                     f"{a.get('license', '')}]")
    (pkg / "CREDITS.txt").write_text("\n".join(lines) + "\n")
    print(f"[pro] credits -> {pkg / 'CREDITS.txt'} ({len(_ATTRIB)} images)")


def _check_continuity(story, shots, clips, pkg):
    """One representative clip per BEAT -> continuity.analyze -> pkg report.
    A beat may declare ``"callback": true`` to permit a deliberate return to an
    earlier image (the payoff); those matches are never flagged."""
    from data_learning import continuity
    beats = story["beats"]
    # Only beats that pull EXTERNAL media (footage / images) can accidentally
    # reuse a source clip. Designed-2D cards (flat_hook, flat_engine, galaxy…)
    # are distinct by construction, so hashing them against footage only yields
    # coarse-dHash false positives — e.g. a fiery number card and a storm in
    # space both read as "bright centre on dark". Exclude designed beats.
    _SOURCED = {"footage", "footage_number", "footage_text",
                "image", "image_text", "depict", "depict_text"}
    by_beat = []
    for bi, b in enumerate(beats):
        idxs = [i for i, sh in enumerate(shots) if sh.get("_beat") == bi]
        if not idxs:
            continue
        if shots[idxs[0]].get("kind") not in _SOURCED:
            continue
        by_beat.append({"idx": bi, "job": b.get("job", str(bi)),
                        "callback": bool(b.get("callback")),
                        "clip": clips[idxs[0]]})
    report = continuity.analyze(by_beat, pkg)
    if report["findings"]:
        for f in report["findings"]:
            print(f"[pro] CONTINUITY {f['label']}: {f['reason']}",
                  file=sys.stderr)
    else:
        print(f"[pro] continuity OK — {len(by_beat)} beats, no reuse")


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


# --- publishing package (parity with the legacy publisher's expectations) ---
def _chapters_from_beats(beats, shots, shot_start):
    """YouTube chapters (first at 0:00, >=3, each >=10s) from CHAPTER beats."""
    chapters = [{"t": 0.0, "label": "Intro"}]
    for bi, b in enumerate(beats):
        if str(b.get("job", "")).upper() != "CHAPTER":
            continue
        idxs = [i for i, sh in enumerate(shots) if sh.get("_beat") == bi]
        if not idxs:
            continue
        lab = (b.get("flat") or {}).get("title") or b.get("understand", "Chapter")
        chapters.append({"t": round(shot_start[idxs[0]], 2), "label": str(lab)[:60]})
    clean, last = [], -100.0
    for c in chapters:                       # enforce the >=10s spacing rule
        if c["t"] - last >= 10.0:
            clean.append(c)
            last = c["t"]
    return clean if len(clean) >= 3 else chapters


def _collect_sources(beats):
    """Fact sources (from a beat's `facts[]`) + media credits, de-duped."""
    src = []
    for b in beats:
        for f in (b.get("facts") or []):
            if f.get("source"):
                src.append(str(f["source"]))
    for a in _ATTRIB:
        cred = a.get("attribution") or a.get("title")
        if cred:
            src.append(f"{cred} ({a.get('source', '')}/{a.get('license', '')})")
    seen, uniq = set(), []
    for s in src:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _emit_meta(story, beats, shots, shot_start, total, out):
    meta = {"title": story.get("title", story.get("slug", "")),
            "slug": story.get("slug", ""), "duration": round(total, 1),
            "chapters": _chapters_from_beats(beats, shots, shot_start),
            "sources": _collect_sources(beats),
            "hook": (beats[0].get("narration", "") if beats else "")[:150]}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[pro] meta -> {out.with_suffix('.meta.json').name} "
          f"({len(meta['chapters'])} chapters, {len(meta['sources'])} sources)")


def _emit_srt(shots, shot_start, durs, out):
    def ts(t):
        return (f"{int(t//3600):02d}:{int(t%3600//60):02d}:{t%60:06.3f}"
                ).replace(".", ",")
    cues, n = [], 0
    for i, sh in enumerate(shots):
        line = str(sh.get("line", "")).strip()
        if not line or durs[i] <= 0:
            continue
        a, span = shot_start[i] + LEAD, max(durs[i], 1.0)
        words = line.split()
        chunks = [" ".join(words[j:j + 8]) for j in range(0, len(words), 8)] or [line]
        each = span / len(chunks)
        for k, ch in enumerate(chunks):
            n += 1
            cues.append(f"{n}\n{ts(a + k*each)} --> {ts(a + (k+1)*each)}\n{ch}\n")
    out.with_suffix(".srt").write_text("\n".join(cues), encoding="utf-8")
    print(f"[pro] srt -> {out.with_suffix('.srt').name} ({n} cues)")


def _emit_thumbnail(out, total, title):
    from PIL import Image, ImageDraw, ImageFont
    import textwrap
    frame = out.with_name(out.stem + "_thumbsrc.png")
    try:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{total*0.35:.1f}",
              "-i", str(out), "-frames:v", "1", str(frame)])
        im = Image.open(frame).convert("RGB").resize((1920, 1080))
    except Exception:  # noqa: BLE001
        im = Image.new("RGB", (1920, 1080), (14, 16, 26))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 740, 1920, 1080], fill=(0, 0, 0, 150))
    try:
        f = ImageFont.truetype(
            str(REPO / "assets" / "fonts" / "Anton-Regular.ttf"), 96)
    except Exception:  # noqa: BLE001
        f = ImageFont.load_default()
    for li, ln in enumerate(textwrap.wrap(str(title).upper(), 26)[:2]):
        d.text((70, 780 + li * 110), ln, font=f, fill=(255, 255, 255))
    im.save(out.with_suffix(".jpg"), quality=90)
    print(f"[pro] thumbnail -> {out.with_suffix('.jpg').name}")


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
    result = build(story, a.out, work, voice=a.voice)
    # an unacceptable fallback (lost narration, no-image floor, missing sidecar)
    # means this render must NOT be trusted — exit non-zero so callers quarantine.
    if isinstance(result, dict) and result.get("verdict") == "unacceptable":
        print(f"[pro] UNACCEPTABLE render: "
              f"{[f['kind'] for f in result['fallbacks'] if f['severity']=='unacceptable']}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
