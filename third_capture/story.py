#!/usr/bin/env python3
"""The dedicated story renderer — executes the director's EDL, nothing else.

STORY_DIRECTOR_PLAYBOOK §11. The old renderer built each beat as its own
miniature production (clip_edit.edit per beat: own money moment, own
pacing, own effects) and glued full-screen chapter cards between them.
That made compilations. This renderer is the inverse: the story director
owns the timeline; this module only executes it with low-level primitives:

    _extract_segment()   exact in/out cut + uniform 9:16 reframe +
                         captions + overlays + loudness, one ffmpeg pass
    _assemble()          hard-cut concat of pre-normalized segments

LAWS (acceptance-tested):
- NO CARDS. There is no card function, no card mp4, no blank frame. Every
  frame of the output is source footage. Context appears as a brief
  overlay ON the moving footage (upper third, 0.7-1.5s), the hook overlays
  the opening footage which starts at second zero.
- The renderer adds NO uncontrolled effects: only what the EDL budgeted.
- Uniform reframe (blur-fill center crop) across all sources — visual
  continuity beats per-beat cleverness (§15); per-beat layouts are a
  Phase Two decision for the DIRECTOR, not the renderer.
- One consistent audio mix: per-segment loudnorm to a shared target.

Contract: `render_story()` raises RuntimeError on an unrenderable story
(caller falls back to a normal clip); individual segment failure of a
MIDDLE beat degrades, but a failed first/last beat aborts (arc integrity
is enforced upstream by the director and re-checked here).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from third_capture import clip_edit

REPO = Path(__file__).resolve().parent.parent
FONT = str(REPO / "assets" / "fonts" / "Anton-Regular.ttf")
FONTS_DIR = str(REPO / "assets" / "fonts")
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
MIN_BEATS = 2
_T = 300

# §14: one consistent mix — every segment normalized to the same target
_LOUDNORM = "highpass=f=60,loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95"
# §2: context overlays are brief, upper-third, over moving footage
OVERLAY_DUR = 1.3
HOOK_DUR = 2.5


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=_T)
    if p.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed rc={p.returncode}: {p.stderr[-300:]}")


def _textfile(text: str, work: Path, tag: str) -> Path:
    tf = work / f"txt_{tag}.txt"
    tf.write_text(text)
    return tf


def _overlay_draw(text: str, work: Path, tag: str, *, y: int,
                  size: int, start: float, dur: float) -> str:
    """A drawtext fragment: boxed text over the footage for a bounded
    window. Upper-third placement; the footage keeps playing beneath."""
    text = (text or "").strip()
    if not text:
        return ""
    tf = _textfile(text, work, tag)
    return (f"drawtext=fontfile={FONT}:textfile={tf}:fontcolor=white:"
            f"fontsize={size}:x=(w-tw)/2:y={y}:box=1:boxcolor=black@0.55:"
            f"boxborderw=18:enable='between(t,{start:.2f},"
            f"{start + dur:.2f})'")


def _seg_words(words: list[dict], start: float, end: float) -> list[dict]:
    """Caption words inside [start, end], rebased to the segment clock."""
    out = []
    for w in words or []:
        if w["e"] > start + 0.05 and w["s"] < end - 0.05:
            out.append({"w": w["w"],
                        "s": max(0.0, w["s"] - start),
                        "e": min(end - start, w["e"] - start)})
    return out


def _extract_segment(src: Path, out: Path, work: Path, tag: str, *,
                     start: float, end: float, words: list[dict],
                     hook: str = "", context_overlay: str = "",
                     effects: list[dict] | None = None,
                     framing: str = "wide") -> None:
    """One beat: exact cut, uniform 9:16 blur-fill reframe (optional
    tight punch-in for reaction beats, §15), captions, overlays, budgeted
    emphasis, loudness — a single ffmpeg pass."""
    dur = end - start
    vf = ""
    if framing == "tight":
        # a modest centered punch-in for response/reaction beats — closer
        # without breaking continuity with the wide beats around it
        vf = "crop=iw/1.28:ih/1.28,"
    # uniform reframe: blurred cover background + contained foreground
    vf += (f"split=2[bg][fg];"
          f"[bg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
          f"increase,crop={CANVAS_W}:{CANVAS_H},boxblur=24:3[bgb];"
          f"[fg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
          f"decrease[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    seg_words = _seg_words(words, start, end)
    if seg_words:
        ass = work / f"cap_{tag}.ass"
        clip_edit.build_ass(seg_words, "", dur, ass)
        vf += f",ass={ass}:fontsdir={FONTS_DIR}"
    draws = []
    if hook:
        draws.append(_overlay_draw(hook, work, f"h{tag}", y=230, size=64,
                                   start=0.0, dur=HOOK_DUR))
    if context_overlay:
        draws.append(_overlay_draw(context_overlay, work, f"c{tag}",
                                   y=150, size=52, start=0.0,
                                   dur=OVERLAY_DUR))
    for i, fx in enumerate(effects or []):
        if fx.get("type") == "subtle_punch":
            at = min(max(0.0, float(fx.get("at", 0)) - start), dur - 0.1)
            draws.append(f"drawbox=c=white@0.5:t=fill:enable="
                         f"'between(t,{at:.2f},{at + 0.05:.2f})'")
    for d in draws:
        if d:
            vf += f",{d}"
    vf += f",fps={FPS},format=yuv420p"
    _run(["ffmpeg", "-y", "-v", "error",
          "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
          "-vf", vf, "-af", _LOUDNORM,
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
          str(out)])


def _render_replay(src: Path, out: Path, *, at: float,
                   span: float = 2.0) -> None:
    """§12: ONE budgeted replay — a slowed re-show of ~2s around `at`,
    labeled REPLAY, appended after its beat. Only when the director
    judged the action genuinely hard to see."""
    s0 = max(0.0, at - span * 0.6)
    vf = (f"split=2[bg][fg];"
          f"[bg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
          f"increase,crop={CANVAS_W}:{CANVAS_H},boxblur=24:3[bgb];"
          f"[fg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
          f"decrease[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2,"
          f"setpts=1.43*PTS,"
          f"drawtext=fontfile={FONT}:text=REPLAY:fontcolor=white:"
          f"fontsize=58:x=(w-tw)/2:y=150:box=1:boxcolor=red@0.7:"
          f"boxborderw=14,fps={FPS},format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error",
          "-ss", f"{s0:.2f}", "-to", f"{s0 + span:.2f}", "-i", str(src),
          "-vf", vf, "-af", f"atempo=0.7,{_LOUDNORM}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
          str(out)])


def _assemble(parts: list[Path], out: Path,
              joins: list[str] | None = None) -> None:
    """Assemble pre-normalized segments. Hard cuts use lossless concat.
    When any join is a j_cut/l_cut (§13), the audio BLENDS across that
    boundary (0.3s acrossfade — the next line enters over the cut / the
    previous line tails over the next visual) while video stays a hard
    cut; abrupt audio starts/stops disappear (§14)."""
    joins = joins or []
    if not any(j in ("j_cut", "l_cut") for j in joins):
        lst = out.parent / f"{out.stem}.concat.txt"
        lst.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
        _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
              "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
              str(out)])
        return
    # filter_complex path: video hard-concat; audio pairwise acrossfade
    # on j/l joins, plain concat elsewhere
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for pp in parts:
        cmd += ["-i", str(pp)]
    n = len(parts)
    fc = "".join(f"[{i}:v]" for i in range(n)) + \
         f"concat=n={n}:v=1:a=0[v];"
    acur = "[0:a]"
    for i in range(1, n):
        j = joins[i - 1] if i - 1 < len(joins) else "hard_cut"
        nxt = f"[a{i}]"
        if j in ("j_cut", "l_cut"):
            fc += f"{acur}[{i}:a]acrossfade=d=0.3:c1=tri:c2=tri{nxt};"
        else:
            fc += f"{acur}[{i}:a]concat=n=2:v=0:a=1{nxt};"
        acur = nxt
    fc = fc.rstrip(";")
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", acur.strip(),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            "-movflags", "+faststart", str(out)]
    _run(cmd)


def _maybe_narration(text: str, work: Path) -> Path | None:
    """§14: optional verified narration line via edge-tts. Best-effort —
    any failure returns None and the story ships without narration."""
    try:
        mp3 = work / "narration.mp3"
        _run(["edge-tts", "--voice", "en-US-ChristopherNeural",
              "--text", text, "--write-media", str(mp3)])
        return mp3 if mp3.exists() and mp3.stat().st_size > 1000 else None
    except Exception:  # noqa: BLE001
        return None


def _mix_narration(seg: Path, voice: Path, out: Path) -> None:
    """Duck the segment under the narration line, then restore."""
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(seg), "-i", str(voice),
          "-filter_complex",
          "[1:a]adelay=150|150,apad[nv];"
          "[0:a][nv]sidechaincompress=threshold=0.05:ratio=8:attack=5:"
          "release=300[duck];[duck][nv]amix=inputs=2:duration=first:"
          "dropout_transition=0.3[a]",
          "-map", "0:v", "-map", "[a]",
          "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2",
          "-b:a", "160k", str(out)])


def render_story(edl: dict, sources: dict[str, dict], out_mp4: Path,
                 work: Path) -> dict:
    """Execute a validated director EDL.

    `sources` maps source_id -> {"path": file, "words": [...], meta...}
    (from the scene reports — the footage and transcript are already on
    disk; this function performs no network access).

    Returns the ledger. Raises RuntimeError when the story cannot be
    rendered faithfully — a failed FIRST or LAST beat invalidates the arc
    (the hook must describe the real opening; a story with no ending
    doesn't ship); a failed middle beat is dropped."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    out_mp4 = Path(out_mp4)
    beats = edl["beats"]
    hold = float((edl.get("ending") or {}).get("duration", 1.0) or 1.0)
    parts: list[Path] = []
    joins: list[str] = []        # transition INTO each part after the first
    used: list[dict] = []
    final_words: list[dict] = []
    timeline = 0.0
    n_overlays = 0
    used_narration = False
    narr = edl.get("narration")

    for idx, beat in enumerate(beats):
        srcinfo = sources.get(beat["source_id"])
        is_edge = idx in (0, len(beats) - 1)
        if not srcinfo:
            if is_edge:
                raise RuntimeError(
                    f"story: {'opening' if idx == 0 else 'payoff'} source "
                    "missing — arc invalid")
            continue
        src = Path(srcinfo["path"])
        start, end = float(beat["start"]), float(beat["end"])
        if idx == len(beats) - 1:
            # §12/§10: the ending holds on the reaction — extend within
            # the source instead of cutting the last half-second
            src_dur = float(srcinfo.get("duration_s") or end)
            end = min(src_dur, end + hold)
        seg = work / f"seg_{idx}.mp4"
        try:
            _extract_segment(
                src, seg, work, str(idx), start=start, end=end,
                words=srcinfo.get("words") or [],
                hook=(edl.get("hook_overlay", "") if idx == 0 else ""),
                context_overlay=beat.get("context_overlay", ""),
                effects=beat.get("effects") or [],
                framing=beat.get("framing", "wide"))
        except Exception as e:  # noqa: BLE001
            if is_edge:
                raise RuntimeError(
                    f"story: {'opening' if idx == 0 else 'payoff'} beat "
                    f"failed to render ({e}) — arc invalid") from e
            print(f"::warning::[story] middle beat {idx} failed "
                  f"({type(e).__name__}) — dropped", flush=True)
            continue
        # §14 narration: mixed onto its beat, ducked, best-effort
        if narr and not used_narration and \
                int(narr.get("after_beat", -1)) == idx:
            voice = _maybe_narration(narr["text"], work)
            if voice:
                seg_n = work / f"seg_{idx}_narr.mp4"
                try:
                    _mix_narration(seg, voice, seg_n)
                    seg = seg_n
                    used_narration = True
                except Exception:  # noqa: BLE001
                    pass
        if parts:
            joins.append(beat.get("transition", "hard_cut"))
        parts.append(seg)
        # §12: the ONE budgeted replay appends a slowed re-show after
        # its beat (the director, not the beat, made this call)
        for fx in (beat.get("effects") or []):
            if fx.get("type") == "replay":
                rp = work / f"replay_{idx}.mp4"
                try:
                    _render_replay(seg, rp,
                                   at=max(0.0, float(fx.get("at", 0))
                                          - start))
                    joins.append("hard_cut")
                    parts.append(rp)
                except Exception:  # noqa: BLE001
                    print(f"::warning::[story] replay render failed — "
                          "skipped", flush=True)
        if beat.get("context_overlay"):
            n_overlays += 1
        for w in _seg_words(srcinfo.get("words") or [], start, end):
            final_words.append({"w": w["w"], "s": w["s"] + timeline,
                                "e": w["e"] + timeline})
        timeline += end - start
        used.append({"source_id": beat["source_id"],
                     "streamer": srcinfo.get("channel", ""),
                     "role": beat["role"], "purpose": beat["purpose"],
                     "start": start, "end": round(end, 2),
                     "source_url": srcinfo.get("source_url",
                                               beat["source_id"])})

    if len(used) < MIN_BEATS:
        raise RuntimeError(
            f"story: only {len(used)} beat(s) rendered — not a story")
    _assemble(parts, out_mp4, joins)
    dur = 0.0
    try:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(out_mp4)], text=True,
            timeout=30).strip())
    except Exception:  # noqa: BLE001
        pass
    n_fx = sum(len(b.get("effects") or []) for b in beats)
    return {"kind": "story",
            "story_structure": edl["structure"],
            "premise": edl["premise"],
            "n_beats": len(used), "duration_s": round(dur, 1),
            "hook": edl.get("hook_overlay", ""),
            "beats": used,
            "member_keys": [u["source_url"] for u in used],
            "final_words": final_words,
            "used_narration": used_narration,
            "transitions": [b.get("transition", "hard_cut")
                            for b in beats],
            "context_overlay_count": n_overlays,
            "replay_count": sum(1 for b in beats for f in
                                (b.get("effects") or [])
                                if f.get("type") == "replay"),
            "effect_count": n_fx}
