#!/usr/bin/env python3
"""The dedicated story renderer — executes the director's EDL, nothing else.

STORY_DIRECTOR_PLAYBOOK §11. The old renderer built each beat as its own
miniature production (clip_edit.edit per beat: own money moment, own
pacing, own effects) and glued full-screen chapter cards between them.
That made compilations. This renderer is the inverse: the story director
owns the timeline; this module only executes it with low-level primitives:

    _extract_segment()   exact in/out cut + uniform 9:16 reframe (subject-
                         aware tight punch-in when the director asks) +
                         captions + overlays + loudness, one ffmpeg pass
    _assemble()          video hard-cut concat; every segment's audio stays
                         locked to its own picture, and a J/L cut adds a
                         SEPARATE bridge of real source dialogue in the
                         overlap — audio locked to the video duration

LAWS (acceptance-tested):
- NO CARDS. There is no card function, no card mp4, no blank frame. Every
  frame of the output is source footage. Context appears as a brief
  overlay ON the moving footage (upper third, 0.7-1.5s), the hook overlays
  the opening footage which starts at second zero.
- The renderer adds NO uncontrolled effects: only what the EDL budgeted.
  The ONE budgeted replay is rendered from the RAW source at its source
  timestamp (never the reframed beat) and advances the caption timeline.
- Each beat is FRAMED like a clip: the same shot plan the clip arm uses
  (stacked facecam over full-width gameplay, a face crop, or a crop to the
  motion), decided ONCE PER SOURCE so every beat cut from one clip keeps
  one look. Blur-fill of the whole frame is the fallback, not the default:
  on 2026-10-05 the first story in eleven days shipped with every beat a
  1080x607 strip in two thirds blurred padding — 31.6% of the screen.
- Real J-cuts (the next line's actual audio leads its picture) and L-cuts
  (the previous line's actual audio tails over the next picture) built from
  genuine source pre-/post-roll — each segment's own audio stays lip-synced,
  the lead/lag is a separate bridge, and a cut degrades to a hard cut when
  the source has no real dialogue to lead/tail with. Audio trimmed/padded to
  the exact video length so audio and video never drift.
- One consistent audio mix: per-segment highpass+loudnorm+limiter.

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
# the story's own line of text (hook, overlay, context) — sentence case in
# a clean bold sans, apart from the speech captions' all-caps Anton
CAPTION_FONT = str(REPO / "assets" / "fonts" / "InterDisplay-Bold.ttf")
# the BOTTOM THIRD, as in the reposts (operator, 2026-10-08: "the text is
# in the bottom third not the middle"): below the speech captions
# (centred, ~960), above the platform's own bottom bar
from third_capture.caption_line import LINE_Y as CAPTION_Y  # noqa: E402
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
MIN_BEATS = 2
_T = 300
# §13: how far real audio leads/tails its picture on a J/L cut. A bridge is
# only built when the source actually holds this much pre-/post-roll dialogue.
LEAD = 0.4
# During a bridge the overlapping segment is ducked to this gain so the
# carried-over line stays intelligible instead of two voices at equal volume
# (reviewer #11). The limiter still guards peaks; ducking guards clarity.
DUCK_GAIN = 0.35
# A bridge window must contain at least this many seconds of transcribed
# speech, or it is silence/noise and the cut degrades to a hard cut.
BRIDGE_MIN_SPEECH = 0.15
# a beat's edges sit on a line's edges (snap_beat)
PHRASE_GAP = 0.3
SNAP_BACK = 2.0
SNAP_ON = 2.5

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


MAX_TEXT_W = CANVAS_W - 2 * 70          # the box's border stays on screen


def _text_w(text: str, size: int) -> float:
    try:
        from PIL import ImageFont
        return ImageFont.truetype(CAPTION_FONT, size).getlength(text)
    except Exception:  # noqa: BLE001
        return len(text) * size * 0.55    # Inter Display Bold's advance


def _wrap(text: str, size: int) -> tuple[list[str], int]:
    """Lines that FIT the frame, and the size that makes them fit.

    Backtest #5: "EMIRU FIGHTS A MATTRESS OUT OF A BOX" is wider than
    1080px at 64px, and drawtext does not wrap — the critic read the hook
    as cut off. Greedy wrap to the measured width; at most two lines, and
    the size steps down until they fit."""
    words = text.split()
    while True:
        lines, cur = [], ""
        for w in words:
            cand = f"{cur} {w}".strip()
            if cur and _text_w(cand, size) > MAX_TEXT_W:
                lines.append(cur)
                cur = w
            else:
                cur = cand
        if cur:
            lines.append(cur)
        if len(lines) == 2:
            # balanced, not greedy: no one-word orphan under a full line
            lines = min(([" ".join(words[:k]), " ".join(words[k:])]
                         for k in range(1, len(words))),
                        key=lambda ls: max(_text_w(x, size) for x in ls))
        if (len(lines) <= 2 and all(_text_w(l, size) <= MAX_TEXT_W
                                    for l in lines)) or size <= 28:
            return lines, size
        size -= 4


def _read_secs(text: str, floor: float) -> float:
    """Long enough to READ: half a second to notice it, then 0.3s a word
    (a six-word overlay held 1.3s was gone before it could be read)."""
    return max(floor, 0.5 + 0.3 * len((text or "").split()))


def beat_captions(idx: int, beat_secs: float, hook: str = "",
                  overlay: str = "", text: str = "") -> list[dict]:
    """What caption is on screen during one beat, in the beat's seconds:
    ONE at a time, in one place, `[{kind, text, at, secs}]`.

    The story has no narrator (operator, 2026-10-08: *"No narrator but
    like any clip your allowed like a line or 2 of text on the screen"*,
    with three reposts as the look: one short line mid-frame, white with
    a black outline, no box, there the whole clip). So the hook is that
    line and it STAYS; a time-jump overlay or a line of context (who
    someone is, how one clip leads to the next) takes its place long
    enough to read, and the hook comes back. On the opening the hook is
    read first."""
    out, t = [], 0.0

    def show(kind, txt, floor):
        nonlocal t
        if not txt or t >= beat_secs - 0.3:
            return
        secs = min(beat_secs - t, _read_secs(txt, floor))
        out.append({"kind": kind, "text": txt, "at": round(t, 2),
                    "secs": round(secs, 2)})
        t += secs
    if idx == 0:
        show("title", hook, HOOK_DUR)
    show("overlay", overlay, OVERLAY_DUR)
    show("text", text, 2.5)
    if hook and t < beat_secs - 0.3:
        out.append({"kind": "title", "text": hook, "at": round(t, 2),
                    "secs": round(beat_secs - t, 2)})
    return out


def _overlay_draw(text: str, work: Path, tag: str, *, y: int,
                  size: int, start: float, dur: float) -> str:
    """drawtext fragments: the caption over the footage for a bounded
    window, each line centred and measured to fit the frame — white,
    a heavy black outline, no box (a bordered panel is a UI widget; the
    reposts this channel is told to look like have none)."""
    text = (text or "").strip()
    if not text:
        return ""
    lines, size = _wrap(text, size)
    out = []
    for i, line in enumerate(lines):
        tf = _textfile(line, work, f"{tag}_{i}")
        out.append(
            f"drawtext=fontfile={CAPTION_FONT}:textfile={tf}:"
            f"fontcolor=white:fontsize={size}:x=(w-tw)/2:"
            f"y={y + i * int(size * 1.25)}:"
            f"borderw={max(4, size // 9)}:bordercolor=black:"
            f"enable='between(t,{start:.2f},{start + dur:.2f})'")
    return ",".join(out)


def _tight_crop(src: Path) -> str:
    """Subject-aware tight-crop filter (reviewer #5): crop a 1/1.28 window
    centred on the DOMINANT subject (shot_plan's face-tracked centroid),
    not a blind centre crop that can cut the actual action out of frame.
    Falls back to a centred crop when analysis is unavailable."""
    default = "crop=iw/1.28:ih/1.28"
    try:
        from third_capture import shot_plan
        an = shot_plan.analyze(src)
        if not an or not an.get("subjects"):
            return default
        sw, sh = an["sw"], an["sh"]
        top = max(an["subjects"],
                  key=lambda s: getattr(s, "presence", 0.0)
                  + getattr(s, "talk", 0.0) / 1000.0)
        cw, ch = sw / 1.28, sh / 1.28
        # clamp the crop window so it stays inside the frame
        x = min(max(top.cx - cw / 2.0, 0.0), sw - cw)
        y = min(max(top.cy - ch / 2.0, 0.0), sh - ch)
        return f"crop=iw/1.28:ih/1.28:{x:.0f}:{y:.0f}"
    except Exception:  # noqa: BLE001
        return default


def _cover_crop(src: Path) -> str:
    """ONE picture, filling the frame: a 9:16 window of the source centred
    on its dominant subject, scaled up. The plain fallback (`safe` render):
    the shot plan's stacked/split layouts and the blur-fill's blurred copy
    behind the picture both put the streamer on screen twice, and the clip
    QA refused the first story the critic ever passed in a backtest for
    exactly that (2026-10-08: "the same streamer appears twice in the same
    frame, once as a close crop and once as a wide shot")."""
    default = (f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
               f"scale={CANVAS_W}:{CANVAS_H}")
    try:
        an = _source_analysis(src)
        if not an or not an.get("subjects"):
            return default
        sw, sh = float(an["sw"]), float(an["sh"])
        top = max(an["subjects"],
                  key=lambda s: getattr(s, "presence", 0.0)
                  + getattr(s, "talk", 0.0) / 1000.0)
        cw, ch = min(sw, sh * 9 / 16), min(sh, sw * 16 / 9)
        x = min(max(top.cx - cw / 2.0, 0.0), sw - cw)
        y = min(max(top.cy - ch / 2.0, 0.0), sh - ch)
        return (f"crop={cw:.0f}:{ch:.0f}:{x:.0f}:{y:.0f},"
                f"scale={CANVAS_W}:{CANVAS_H}")
    except Exception:  # noqa: BLE001
        return default


_AN_CACHE: dict[str, dict | None] = {}


def _source_analysis(src: Path) -> dict | None:
    """shot_plan's subject analysis of a whole SOURCE, once per file — every
    beat (and every revision's re-render) cut from it reuses it, so beats
    from one clip get one framing and the cv2 pass runs once."""
    key = str(Path(src).resolve())
    if key not in _AN_CACHE:
        try:
            from third_capture import shot_plan
            _AN_CACHE[key] = shot_plan.analyze(Path(src))
        except Exception:  # noqa: BLE001
            _AN_CACHE[key] = None
    return _AN_CACHE[key]


def _framed_cut(src: Path, work: Path, tag: str, start: float,
                end: float) -> tuple[Path | None, str]:
    """(1080x1920 framed cut of [start, end] | None, layout).

    The clip arm's shot plan applied to one beat: exact cut at source
    geometry, then `shot_plan.build` with the SOURCE's analysis. None means
    no plan applies and the caller blur-fills — never raises."""
    an = _source_analysis(src)
    if an is None:
        return None, "wide"
    try:
        from third_capture import shot_plan
        cut = work / f"cut_{tag}.mp4"
        _run(["ffmpeg", "-y", "-v", "error",
              "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
              "-c:a", "aac", "-ar", "48000", "-ac", "2", str(cut)])
        bdir = work / f"sp_{tag}"
        bdir.mkdir(parents=True, exist_ok=True)
        framed, summ = shot_plan.build(cut, bdir, analyze_on=Path(src), an=an)
        return framed, str((summ or {}).get("layout") or "wide")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[story] shot plan failed for beat {tag} "
              f"({type(e).__name__}) — blur-fill", flush=True)
        return None, "wide"


def _next_word_at(words: list[dict], end: float) -> float:
    """When the next word after `end` starts (inf if none).

    The ending's hold extends the last beat into the source; backtest #4's
    best cut was trimmed to "...than my bed." and the hold then let "I
    have" back in. The hold may run into silence, never into a new line —
    and never shorter than the beat itself."""
    nxt = [float(w["s"]) for w in words or [] if float(w["s"]) >= end - 0.02]
    return max(end + 0.05, min(nxt)) if nxt else float("inf")


_OWN_CAPS: dict = {}


def _captions_itself(src: Path, srcinfo: dict) -> bool:
    """The source already shows what is said — the scene analysis saw it,
    or the frames read back the transcript (clip_edit.own_captions). Never
    a second set of captions on top (operator, 2026-10-09)."""
    if srcinfo.get("own_subtitles"):
        return True
    key = str(src)
    if key not in _OWN_CAPS:
        try:
            _OWN_CAPS[key] = clip_edit.own_captions(
                src, srcinfo.get("words") or [])
        except Exception:  # noqa: BLE001
            _OWN_CAPS[key] = False
    return _OWN_CAPS[key]


def snap_beat(words: list[dict], start: float, end: float, *,
              keep_start: bool = False,
              keep_end: bool = False) -> tuple[float, float]:
    """Move a beat's edges off the middle of a line.

    Backtest 14's critic, on nearly every cut: "opens mid-sentence",
    "cut off at the splice", "ends mid-sentence on 'And I have messages of
    me expressing, bro.'" The director picks seconds from a transcript and
    lands inside a phrase. An edge inside a word, or with the next word
    under `PHRASE_GAP` away, moves to the phrase's edge: the start back (at
    most `SNAP_BACK`) to where the phrase begins, the end on (at most
    `SNAP_ON`) to where it stops. Too far either way and the edge goes to
    the nearest word edge instead — never through the middle of a word.

    A J/L cut overlaps a line across the join ON PURPOSE, so the edge it
    bridges is kept (`keep_start` for a j_cut in, `keep_end` for an l_cut
    out)."""
    ws = sorted((w for w in words or []
                 if "s" in w and "e" in w), key=lambda w: float(w["s"]))
    if not ws or end - start < 1.0:
        return start, end
    ss = [float(w["s"]) for w in ws]
    es = [float(w["e"]) for w in ws]
    n = len(ws)

    def phrase_start(i):          # word i begins a phrase
        return i == 0 or ss[i] - es[i - 1] >= PHRASE_GAP

    def phrase_end(i):            # word i ends a phrase
        return i == n - 1 or ss[i + 1] - es[i] >= PHRASE_GAP

    # ---- start: the first word at or after it, unless start cuts into one
    i = None if keep_start else next(
        (k for k in range(n) if es[k] > start + 0.02), None)
    if i is not None and (ss[i] < start - 0.02 or (
            not phrase_start(i) and ss[i] - start < PHRASE_GAP)):
        j = i
        while j > 0 and not phrase_start(j) and start - ss[j - 1] <= SNAP_BACK:
            j -= 1
        if phrase_start(j) and start - ss[j] <= SNAP_BACK:
            start = max(0.0, ss[j] - 0.05)
        elif ss[i] < start:
            start = max(0.0, ss[i] - 0.05)
    # ---- end: the last word at or before it, unless end cuts into one
    k = None if keep_end else max(
        (m for m in range(n) if ss[m] < end - 0.02), default=None)
    if k is not None and (es[k] > end + 0.02 or not phrase_end(k)):
        j = k
        while j < n - 1 and not phrase_end(j) and es[j + 1] - end <= SNAP_ON:
            j += 1
        if phrase_end(j) and es[j] - end <= SNAP_ON:
            end = es[j] + 0.1
        elif es[k] > end:
            end = es[k] + 0.05
    return start, end


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
                     captions: list[dict] | None = None,
                     effects: list[dict] | None = None,
                     framing: str = "wide", safe: bool = False) -> str:
    """One beat: exact cut, the clip arm's shot-plan framing (blur-fill
    when no plan applies; optional tight punch-in for reaction beats on
    that fallback, §15), captions, overlays, budgeted emphasis, loudness.
    Returns the layout used, for the ledger."""
    dur = end - start
    framed, layout = ((None, "cover") if safe
                      else _framed_cut(src, work, tag, start, end))
    vf = ""
    if safe:
        vf = _cover_crop(src)
    elif framed is not None:
        # already a sharp 1080x1920 shot; the clip arm grades the same way
        vf = "eq=saturation=1.05"
    else:
        layout = "blur_fill"
        if framing == "tight":
            # subject-aware punch-in for response/reaction beats (§15) —
            # crop centred on the tracked subject, computed once per source
            vf = _tight_crop(src) + ","
        # blurred cover background + contained foreground
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
    for i, c in enumerate(captions or []):
        draws.append(_overlay_draw(c["text"], work, f"c{tag}_{i}",
                                   y=CAPTION_Y, size=64, start=c["at"],
                                   dur=c["secs"]))
    for i, fx in enumerate(effects or []):
        if fx.get("type") == "subtle_punch":
            at = min(max(0.0, float(fx.get("at", 0)) - start), dur - 0.1)
            draws.append(f"drawbox=c=white@0.5:t=fill:enable="
                         f"'between(t,{at:.2f},{at + 0.05:.2f})'")
    for d in draws:
        if d:
            vf += f",{d}"
    vf += f",fps={FPS},format=yuv420p"
    # the framed cut is already trimmed to [start, end]
    inp = (["-i", str(framed)] if framed is not None else
           ["-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src)])
    _run(["ffmpeg", "-y", "-v", "error", *inp,
          "-vf", vf, "-af", _LOUDNORM,
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
          str(out)])
    return layout


def _render_replay(src: Path, out: Path, *, at: float,
                   span: float = 2.0) -> None:
    """§12: ONE budgeted replay — a slowed re-show of ~2s around `at`,
    labeled REPLAY. `src` is the RAW source and `at` is a SOURCE-relative
    timestamp (reviewer #6): rendering from the raw footage — not the
    already-reframed+captioned+overlaid beat — avoids a vertical-in-vertical
    double reframe, duplicated captions, and (for a first beat) replaying
    the opening hook. Only the final reframe + REPLAY label are applied."""
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


def _probe_dur(p: Path) -> float:
    try:
        return float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)], text=True, timeout=30).strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def _extract_audio(src: Path, out: Path, s: float, e: float) -> None:
    """Pull a real, loudness-matched audio snippet [s, e] from a RAW source.
    Used to build J/L-cut bridges: the actual dialogue outside a beat's
    visible video window (never silence, never a shifted copy of the beat's
    own track)."""
    _run(["ffmpeg", "-y", "-v", "error",
          "-ss", f"{s:.2f}", "-to", f"{e:.2f}", "-i", str(src), "-vn",
          "-af", _LOUDNORM,
          "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
          str(out)])


def _speech_secs(words: list[dict], s: float, e: float) -> float:
    """Seconds of TRANSCRIBED speech inside [s, e]. A J/L bridge is only
    honest when the pre-/post-roll window it pulls actually contains dialogue
    (reviewer #11) — enough source DURATION existing does not mean the source
    was TALKING there (it may be silence, music, or crowd noise). Best-effort;
    no words → 0.0 → the cut degrades to a hard cut."""
    tot = 0.0
    for w in words or []:
        try:
            a = max(s, float(w["s"]))
            b = min(e, float(w["e"]))
        except (KeyError, TypeError, ValueError):
            continue
        if b > a:
            tot += b - a
    return tot


def _assemble(parts: list[Path], out: Path,
              joins: list[str] | None = None,
              bridges: list[tuple] | None = None, lead: float = LEAD) -> None:
    """Assemble pre-normalized segments. Video is ALWAYS a plain hard-cut
    concat (full duration V = sum of segment durations). Stories with no
    J/L bridge take the lossless demuxer path, and — crucially — every
    segment keeps its OWN audio locked to its OWN picture.

    Real J/L cuts (reviewer #8): the old code shifted a whole segment's
    audio 0.4s early (a j_cut desynced the visible speaker for the ENTIRE
    shot) and l_cut just apad'd silence (recovering no real dialogue). Now
    each segment's audio stays at its true offset (adelay=video_off[i]), and
    the lead/lag is a SEPARATE bridge of genuine source audio placed in the
    overlap region:
      - "lead" (j_cut INTO part p): ~`lead`s of part p's source dialogue
        from BEFORE its visible start, ending at O_p — the next line is
        heard under the previous picture, then picture+sound resync.
      - "tail" (l_cut INTO part p): ~`lead`s of the PREVIOUS beat's real
        source dialogue AFTER its visible end, starting at O_p — the
        previous line genuinely continues over the next picture.
    Bridges are inputs n..n+k; each is placed with adelay and amixed with
    the (synced) segment tracks, limited, then atrim+apad to EXACTLY V so
    final audio and video never drift regardless of join count.

    `bridges` entries are (part_index, "lead"|"tail", audio_path). render_
    story only emits a bridge when the source actually holds the pre-/post-
    roll, so an L-cut here always carries continuing speech, not padding."""
    joins = joins or []
    bridges = bridges or []
    if not bridges:
        # no real J/L bridge survived the pre-/post-roll test → hard cuts
        # only → lossless demuxer concat (each part's audio untouched)
        lst = out.parent / f"{out.stem}.concat.txt"
        lst.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
        _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
              "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
              str(out)])
        return
    n = len(parts)
    durs = [_probe_dur(p) for p in parts]
    video_off = [sum(durs[:i]) for i in range(n)]   # each seg's video start
    total = sum(durs)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for pp in parts:
        cmd += ["-i", str(pp)]
    for (_p, _kind, bpath) in bridges:
        cmd += ["-i", str(bpath)]
    # video: plain hard-cut concat, full length
    fc = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v];"
    labels = []
    # Per-part DUCK windows (output seconds): during a bridge the OTHER
    # segment is dipped so the carried line stays intelligible (reviewer #11).
    #   lead (j_cut into p): the incoming line leads UNDER the previous
    #     picture → duck the OUTGOING (part p-1) audio over [O_p-lead, O_p].
    #   tail (l_cut into p): the previous line carries OVER the new picture →
    #     duck the INCOMING (part p) audio over [O_p, O_p+lead].
    duck: dict[int, list[tuple[float, float]]] = {}
    for (p, kind, _bp) in bridges:
        p = max(0, min(int(p), n - 1))
        if kind == "lead":
            tgt, w0, w1 = p - 1, video_off[p] - lead, video_off[p]
        else:
            tgt, w0, w1 = p, video_off[p], video_off[p] + lead
        if 0 <= tgt < n:
            duck.setdefault(tgt, []).append((max(0.0, w0), w1))
    # each segment's audio stays SYNCED to its own picture — no whole-clip
    # shift (that was the lip-sync bug); the J/L lead/lag is a bridge below
    for i in range(n):
        off = int(video_off[i] * 1000)
        lbl = f"[a{i}]"
        chain = f"[{i}:a]adelay={off}|{off}"
        if duck.get(i):
            # after adelay, `t` is the OUTPUT timeline, so the window is
            # absolute; enable is truthy inside ANY of this part's windows
            expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in duck[i])
            chain += f",volume=enable='{expr}':volume={DUCK_GAIN}"
        fc += chain + lbl + ";"
        labels.append(lbl)
    # bridges: real source audio placed in the overlap region around O_p
    for j, (p, kind, _bp) in enumerate(bridges):
        inp = n + j
        p = max(0, min(int(p), n - 1))
        if kind == "lead":       # j_cut: ends at O_p, under the prev picture
            off = int(max(0.0, video_off[p] - lead) * 1000)
        else:                    # tail (l_cut): starts at O_p, over next pic
            off = int(video_off[p] * 1000)
        lbl = f"[b{j}]"
        fc += f"[{inp}:a]adelay={off}|{off}{lbl};"
        labels.append(lbl)
    ninputs = n + len(bridges)
    fc += "".join(labels) + (
        f"amix=inputs={ninputs}:normalize=0:dropout_transition=0,"
        # two dialogues briefly sum in the overlap — cap peaks, then lock
        # audio to the video length exactly (A/V alignment guarantee)
        f"alimiter=limit=0.95,atrim=0:{total:.3f},"
        f"apad=whole_dur={total:.3f}[a]")
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            "-movflags", "+faststart", str(out)]
    _run(cmd)


def plan_ledger(edl: dict, sources: dict[str, dict]) -> dict:
    """The ledger `render_story` WOULD write, without rendering anything:
    each beat's place on the output clock, the words a viewer would hear
    there, and what the edit lays on top. The same arithmetic as the
    renderer (the last beat's hold into silence, the hook and overlay read
    times, the narrator line per beat), minus replays, which add no words.

    It is what the critic reads at the TABLE READ (`run_third`): a plan is
    judged and repaired on paper before a single frame is cut, so the
    render budget goes to the plans that read like a story."""
    beats = edl.get("beats") or []
    hold = float((edl.get("ending") or {}).get("duration", 1.0) or 1.0)
    narr_by_beat: dict = {}
    for ln in (edl.get("narration_lines")
               or ([edl["narration"]] if isinstance(edl.get("narration"), dict)
                   else edl.get("narration") or [])):
        try:
            narr_by_beat.setdefault(
                int(ln.get("over_beat", ln.get("after_beat", -1))), ln)
        except (TypeError, ValueError, AttributeError):
            continue
    timeline = 0.0
    used, words, on_screen = [], [], []
    for idx, beat in enumerate(beats):
        srcinfo = sources.get(beat.get("source_id"))
        if not srcinfo:
            continue
        start, end = snap_beat(
            srcinfo.get("words") or [], float(beat["start"]),
            float(beat["end"]),
            keep_start=beat.get("transition") == "j_cut",
            keep_end=(idx + 1 < len(beats) and
                      beats[idx + 1].get("transition") == "l_cut"))
        if idx == len(beats) - 1:
            src_dur = float(srcinfo.get("duration_s") or end)
            end = min(src_dur, end + hold, _next_word_at(
                srcinfo.get("words") or [], end) - 0.05)
        for c in beat_captions(
                idx, end - start, edl.get("hook_overlay", ""),
                beat.get("context_overlay", ""),
                (narr_by_beat.get(idx) or {}).get("text", "")):
            on_screen.append({"at": round(timeline + c["at"], 1),
                              "kind": c["kind"], "secs": round(c["secs"], 1),
                              "text": c["text"]})
        for w in _seg_words(srcinfo.get("words") or [], start, end):
            words.append({"w": w["w"], "s": w["s"] + timeline,
                          "e": w["e"] + timeline})
        used.append({"source_id": beat["source_id"],
                     "role": beat.get("role", ""),
                     "purpose": beat.get("purpose", ""),
                     "start": start, "end": round(end, 2), "beat": idx,
                     "out_start": round(timeline, 2),
                     "out_end": round(timeline + end - start, 2)})
        timeline += end - start
    return {"beats": used, "final_words": words, "on_screen": on_screen,
            "duration_s": round(timeline, 1)}


def render_story(edl: dict, sources: dict[str, dict], out_mp4: Path,
                 work: Path, safe_framing: bool = False) -> dict:
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
    # REALIZED transitions between rendered BEATS (excludes replay part-gaps).
    # The ledger reports THIS, not the EDL's requested transitions, so a
    # j/l cut that degraded to a hard cut is not attributed to the learning
    # loop as a j/l cut that happened (reviewer #11).
    realized_joins: list[str] = []
    # per-part source anchor (parallel to `parts`, replays included) so a
    # J/L bridge can reach real dialogue outside the visible window
    part_meta: list[dict] = []
    bridges: list[tuple] = []    # (part_index, "lead"|"tail", audio_path)
    used: list[dict] = []
    final_words: list[dict] = []
    timeline = 0.0
    n_overlays = 0
    # one line of on-screen text per beat at most
    # (story_director.narration_lines; the key kept its old name)
    _lines = edl.get("narration_lines")
    if _lines is None:
        _lines = [edl["narration"]] if edl.get("narration") else []
    narr_by_beat = {}
    for _ln in _lines:
        try:
            narr_by_beat.setdefault(
                int(_ln.get("over_beat", _ln.get("after_beat", -1))), _ln)
        except (TypeError, ValueError, AttributeError):
            continue
    n_text = 0
    # what the cut SHOWS and SAYS beyond the source's own words, on the
    # output clock — the critic is told (it samples frames and reads a
    # transcript, so a voice-over and a 1-2s overlay are otherwise unknown
    # to it; backtest #5's critic asked for context the narrator gave)
    on_screen: list[dict] = []

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
        start, end = snap_beat(
            srcinfo.get("words") or [], float(beat["start"]),
            float(beat["end"]),
            keep_start=beat.get("transition") == "j_cut",
            keep_end=(idx + 1 < len(beats) and
                      beats[idx + 1].get("transition") == "l_cut"))
        if idx == len(beats) - 1:
            # §12/§10: the ending holds on the reaction — extend within
            # the source instead of cutting the last half-second
            src_dur = float(srcinfo.get("duration_s") or end)
            end = min(src_dur, end + hold, _next_word_at(
                srcinfo.get("words") or [], end) - 0.05)
        seg = work / f"seg_{idx}.mp4"
        caps = beat_captions(idx, end - start, edl.get("hook_overlay", ""),
                             beat.get("context_overlay", ""),
                             (narr_by_beat.get(idx) or {}).get("text", ""))
        try:
            _lay = _extract_segment(
                src, seg, work, str(idx), start=start, end=end,
                words=([] if _captions_itself(src, srcinfo)
                       else srcinfo.get("words") or []),
                captions=caps,
                effects=beat.get("effects") or [],
                framing=beat.get("framing", "wide"),
                safe=safe_framing)
        except Exception as e:  # noqa: BLE001
            if is_edge:
                raise RuntimeError(
                    f"story: {'opening' if idx == 0 else 'payoff'} beat "
                    f"failed to render ({e}) — arc invalid") from e
            print(f"::warning::[story] middle beat {idx} failed "
                  f"({type(e).__name__}) — dropped", flush=True)
            continue
        if parts:
            # build a REAL J/L bridge (reviewer #8) or fall back to a hard
            # cut when the source lacks the pre-/post-roll to do it honestly
            tr = beat.get("transition", "hard_cut")
            p = len(parts)               # index this segment will occupy
            src_dur = float(srcinfo.get("duration_s") or end)
            my_words = srcinfo.get("words") or []
            if tr == "j_cut" and start >= LEAD and _speech_secs(
                    my_words, start - LEAD, start) >= BRIDGE_MIN_SPEECH:
                # 0.4s of THIS source's real DIALOGUE from before the visible
                # start (confirmed present above), heard under the prev picture
                bp = work / f"bridge_j_{idx}.m4a"
                try:
                    _extract_audio(src, bp, start - LEAD, start)
                    bridges.append((p, "lead", bp))
                except Exception:  # noqa: BLE001
                    tr = "hard_cut"
            elif tr == "l_cut":
                prev = part_meta[-1] if part_meta else None
                # only from a real beat (not a replay) with post-roll that is
                # actually SPEECH, not just enough duration (reviewer #11)
                if (prev and not prev.get("replay")
                        and prev["end"] + LEAD <= prev["src_dur"]
                        and _speech_secs(prev.get("words"), prev["end"],
                                         prev["end"] + LEAD) >= BRIDGE_MIN_SPEECH):
                    bp = work / f"bridge_l_{idx}.m4a"
                    try:
                        _extract_audio(prev["src"], bp, prev["end"],
                                       prev["end"] + LEAD)
                        bridges.append((p, "tail", bp))
                    except Exception:  # noqa: BLE001
                        tr = "hard_cut"
                else:
                    tr = "hard_cut"        # no honest post-roll dialogue
            elif tr in ("j_cut", "l_cut"):
                tr = "hard_cut"            # requested but no pre-/post-roll
            joins.append(tr)
            realized_joins.append(tr)     # what was ACTUALLY rendered
        parts.append(seg)
        part_meta.append({"src": src, "start": start, "end": end,
                          "src_dur": float(srcinfo.get("duration_s") or end),
                          "words": srcinfo.get("words") or []})
        if beat.get("context_overlay"):
            n_overlays += 1
        if narr_by_beat.get(idx):
            n_text += 1
        for c in caps:
            on_screen.append({"at": round(timeline + c["at"], 1),
                              "kind": c["kind"], "secs": round(c["secs"], 1),
                              "text": c["text"]})
        # where this beat sits on the OUTPUT clock — the critic names
        # problems in output seconds and the reviser edits source seconds
        # (`story_director.locate`)
        out_start = timeline
        # this beat's caption words are placed at the CURRENT timeline
        # offset (before any replay that follows it)
        for w in _seg_words(srcinfo.get("words") or [], start, end):
            final_words.append({"w": w["w"], "s": w["s"] + timeline,
                                "e": w["e"] + timeline})
        timeline += end - start
        # §12: the ONE budgeted replay appends a slowed re-show after its
        # beat — rendered from the RAW source at the SOURCE timestamp
        # (reviewer #6), and its rendered duration ADVANCES the timeline
        # (reviewer #7) so later beats' transcript timestamps stay aligned
        # with the assembled video (else the critic's "problem at Xs" drifts)
        for fx in (beat.get("effects") or []):
            if fx.get("type") == "replay":
                rp = work / f"replay_{idx}.mp4"
                try:
                    _render_replay(src, rp, at=max(0.0, float(fx.get("at", 0))))
                    joins.append("hard_cut")
                    parts.append(rp)
                    # replay is not a bridge source (slowed re-show) — mark
                    # it so a following l_cut won't tail from it
                    part_meta.append({"src": src, "start": 0.0, "end": 0.0,
                                      "src_dur": 0.0, "words": [],
                                      "replay": True})
                    timeline += _probe_dur(rp)
                except Exception:  # noqa: BLE001
                    print(f"::warning::[story] replay render failed — "
                          "skipped", flush=True)
        used.append({"source_id": beat["source_id"],
                     "streamer": srcinfo.get("channel", ""),
                     "role": beat["role"], "purpose": beat["purpose"],
                     "start": start, "end": round(end, 2),
                     "beat": idx, "out_start": round(out_start, 2),
                     "out_end": round(out_start + end - start, 2),
                     "layout": _lay,
                     "source_url": srcinfo.get("source_url",
                                               beat["source_id"])})

    if len(used) < MIN_BEATS:
        raise RuntimeError(
            f"story: only {len(used)} beat(s) rendered — not a story")
    _assemble(parts, out_mp4, joins, bridges)
    # SHARED ENGINE PASS (engines/render_qa): a stitched story has more
    # seams than a single clip — every join is a chance for a black gap,
    # a frozen bridge, or A/V drift. The free mechanical pass FAILS the
    # render here (raise → the slot falls back to a normal clip) instead
    # of letting a broken stitch reach the critic or the channel.
    # maybe_* contract: None (engine absent/failed) changes nothing.
    try:
        from engines.render_qa import maybe_check as _rqa_check
        _rqa = _rqa_check(out_mp4)
        if _rqa and not _rqa["ok"]:
            raise RuntimeError("story: render_qa rejected the stitch — "
                               + "; ".join(_rqa["problems"]))
    except ImportError:
        pass
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
            # no voice-over, ever: the story's added words are TEXT
            "used_narration": False,
            "text_lines": n_text,
            "on_screen": on_screen,
            # REALIZED transitions (reviewer #11): what the renderer actually
            # produced, so a degraded j/l→hard cut is not logged as a j/l cut
            # that happened. `transitions_requested` keeps the EDL's intent for
            # debugging the gap between asked-for and delivered.
            "transitions": realized_joins,
            "transitions_requested": [b.get("transition", "hard_cut")
                                      for b in beats[1:]],
            "j_l_cuts_realized": sum(1 for t in realized_joins
                                     if t in ("j_cut", "l_cut")),
            "context_overlay_count": n_overlays,
            "replay_count": sum(1 for b in beats for f in
                                (b.get("effects") or [])
                                if f.get("type") == "replay"),
            "effect_count": n_fx}
