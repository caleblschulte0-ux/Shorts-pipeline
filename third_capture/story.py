#!/usr/bin/env python3
"""Multi-clip STORY compilation — the reality-TV recap format.

A single decontextualized moment travels poorly; a *story* — a beef that
starts, escalates and resolves; a challenge set up and paid off; a
friendship arc — is what the feed rewards, because a stranger understands
the human situation and stays for the payoff (THIRD_INTERNET_PLAYBOOK §1).

This module stitches several source clips (from different streamers/times)
into one 9:16 narrative video: a chapter card, then the beat, for each beat
in the arc. It deliberately REUSES the battle-tested single-clip path —
each beat is rendered by `clip_edit.edit()` (the same reframe + captions +
render-ladder every daily clip goes through), so the story engine only owns
what is genuinely new: per-beat gathering, chapter cards, and the concat.

The showrunner brain (`author.order_story`) decides the arc and writes the
cards; this module executes it. Contract mirrors the rest of the pipeline:
best-effort per beat (a bad beat is skipped, never fatal), and the whole
build raises only if fewer than two beats survive — a one-beat "story" is
just a clip, so it should fall back to the normal single-clip path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from third_capture import clip_edit, clip_qa

REPO = Path(__file__).resolve().parent.parent
FONT = str(REPO / "assets" / "fonts" / "Anton-Regular.ttf")
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
CARD_DUR = 1.5            # seconds per chapter card
MIN_BEATS = 2            # fewer than this isn't a story — fall back to a clip
MAX_BEATS = 4            # 3-4 beats lands the 25-90s story range reliably
_T = 300                 # per-ffmpeg ceiling (s)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, capture_output=True, text=True, timeout=_T, check=True)


def _drawtext(text: str, work: Path, tag: str, *, size: int, y: str,
              box_alpha: float = 0.0) -> str:
    """A drawtext filter fragment reading its text from a file (apostrophe /
    special-char safe, exactly as clip_edit does its cards). Returns "" for
    empty text so it composes cleanly."""
    text = (text or "").strip()
    if not text:
        return ""
    tf = work / f"card_{tag}.txt"
    tf.write_text(text)
    box = (f":box=1:boxcolor=black@{box_alpha}:boxborderw=28"
           if box_alpha > 0 else "")
    return (f"drawtext=fontfile={FONT}:textfile={tf}:fontcolor=white:"
            f"fontsize={size}:x=(w-tw)/2:y={y}{box}")


def _card(title: str, subtitle: str, out: Path, work: Path, tag: str,
          dur: float = CARD_DUR) -> None:
    """Render a chapter title card: dark canvas, big Anton title, small
    subtitle (who/when), gentle fade in/out, silent stereo audio so it
    concatenates cleanly with the beats."""
    draws = [d for d in (
        _drawtext(title, work, f"{tag}t", size=118, y="(h-th)/2-70"),
        _drawtext(subtitle, work, f"{tag}s", size=52,
                  y="(h-th)/2+90", box_alpha=0.0),
    ) if d]
    vf = ",".join(draws) if draws else "null"
    vf += (f",fade=t=in:st=0:d=0.25,"
           f"fade=t=out:st={max(0.0, dur - 0.3):.2f}:d=0.3,format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", f"color=c=0x0b0b12:s={CANVAS_W}x{CANVAS_H}:"
          f"r={FPS}:d={dur}",
          "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
          "-vf", vf, "-t", f"{dur}",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
          "-shortest", str(out)])


def _has_audio(video: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
            text=True, timeout=30)
        return bool(out.strip())
    except Exception:  # noqa: BLE001
        return False


def _normalize(src: Path, out: Path) -> None:
    """Re-encode a beat to the canonical concat contract (1080x1920, 30fps,
    yuv420p, aac 48k stereo). Beats come from clip_edit.edit already at
    1080x1920, so this is mostly a codec/fps/timebase alignment — but the
    scale+pad makes it robust to any stray geometry, and silent audio is
    synthesized if a beat somehow lost its track (concat needs matching
    streams on every part)."""
    vf = (f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=decrease,"
          f"pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
          f"fps={FPS},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if not _has_audio(src):
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            str(out)]
    _run(cmd)


def _concat(parts: list[Path], out: Path) -> None:
    """Concat pre-normalized parts by ABSOLUTE path (unlike auto_edit._concat,
    which keys on basenames and so needs every part beside the list file —
    story parts live in the work dir but `out` may not, so absolute is safer).
    All parts already share the canonical codec/geometry, so `-c copy` holds."""
    lst = out.parent / f"{out.stem}.concat.txt"
    lst.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])


def _subtitle(streamer: str, clip: dict) -> str:
    """The small who/when line under a chapter title."""
    who = (streamer or clip.get("streamer") or "").strip()
    when = str(clip.get("date") or clip.get("ts") or "")[:10]
    who = who.upper()
    return f"{who}  •  {when}" if (who and when) else who or when


def build_story(beats: list[dict], out_mp4: Path, work: Path, *,
                hook: str = "", whisper_model: str = "small") -> dict:
    """Render an ordered arc into one 9:16 story video.

    `beats`: ordered list of {clip, role, card} from `author.order_story`,
    where `clip` carries at least a source URL (`source_url`/`url`) and a
    streamer (`channel`/`streamer`). Each beat is downloaded, preflighted,
    rendered through the normal single-clip path, prefixed with a chapter
    card, and concatenated. A beat that fails any step is skipped. Returns a
    ledger dict; raises RuntimeError if fewer than MIN_BEATS survive (the
    caller should then fall back to a single-clip post)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    out_mp4 = Path(out_mp4)
    parts: list[Path] = []
    used: list[dict] = []

    # PLAYBOOK §5: never open on a title card that delays the actual clip.
    # The hook is burned as an OVERLAY on the first beat's opening seconds
    # (clip_edit.edit's own hook-card mechanic — text over the video, the
    # clip playing underneath immediately). Chapter cards appear only
    # BETWEEN beats, where they're act breaks, not a delayed start.

    def _render_beat(idx: int, beat: dict) -> dict | None:
        """Download + render + normalize one beat, appending its parts.
        Returns the used-record, or None when the beat fails any step."""
        clip = beat.get("clip", {})
        url = clip.get("source_url") or clip.get("url")
        if not url:
            return None
        try:
            info = clip_edit.download(url, work)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[story] beat {idx} download failed "
                  f"({type(e).__name__}) — skipped", flush=True)
            return None
        src = Path(info["path"])
        if not src.is_absolute():
            src = REPO / src
        pf = clip_qa.preflight(src)
        if pf:
            print(f"::warning::[story] beat {idx} preflight: "
                  f"{'; '.join(pf)[:120]} — skipped", flush=True)
            return None
        streamer = (clip.get("channel") or clip.get("streamer")
                    or info.get("clipper") or "")
        platform = clip.get("platform", "twitch")
        beat_out = work / f"beat_{idx}.mp4"
        opens_video = not used     # first surviving beat opens the story
        try:
            led = clip_edit.edit(
                src, beat_out,
                credit=clip_edit.credit_label(platform, streamer),
                hook=(hook if opens_video else ""),
                whisper_model=whisper_model, auto=True,
                series=clip.get("series", "chaos"))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[story] beat {idx} render failed "
                  f"({type(e).__name__}: {e}) — skipped", flush=True)
            return None
        if not beat_out.exists():
            return None
        beat_norm = work / f"beat_{idx}_n.mp4"
        try:
            _normalize(beat_out, beat_norm)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[story] beat {idx} normalize failed "
                  f"({type(e).__name__}) — skipped", flush=True)
            return None
        if opens_video:
            parts.append(beat_norm)
        else:
            card_mp4 = work / f"card_{idx}.mp4"
            _card(beat.get("card", ""), _subtitle(streamer, clip),
                  card_mp4, work, str(idx))
            # extend(), never `+=`: augmented assignment on a closed-over
            # name makes it local to this nested function (UnboundLocal —
            # the same scoping class as the 2026-07-23 canary crash)
            parts.extend([card_mp4, beat_norm])
        return {
            "source_url": url, "streamer": streamer, "platform": platform,
            "role": beat.get("role", ""), "card": beat.get("card", ""),
            "render_level": led.get("render_level"),
            "duration_s": led.get("duration_s"),
        }

    # ARC INTEGRITY (reviewer rail): the showrunner ordered setup ->
    # ... -> payoff. Dropping a MIDDLE beat still tells a coherent story;
    # losing the SETUP (the hook no longer matches what opens the video)
    # or the PAYOFF (a "full story" with no ending) invalidates the arc —
    # abort so the slot falls back to a normal clip instead of publishing
    # a broken story.
    planned = beats[:MAX_BEATS]
    for idx, beat in enumerate(planned):
        rec = _render_beat(idx, beat)
        if rec is None:
            if idx == 0:
                raise RuntimeError(
                    "story: SETUP beat failed — arc invalid without its "
                    "opening; fall back to a single clip")
            if idx == len(planned) - 1:
                raise RuntimeError(
                    "story: PAYOFF beat failed — a story with no ending "
                    "doesn't ship; fall back to a single clip")
            continue
        used.append(rec)

    if len(used) < MIN_BEATS:
        raise RuntimeError(
            f"story: only {len(used)} beat(s) survived render — "
            f"need >={MIN_BEATS}; fall back to a single clip")

    _concat(parts, out_mp4)
    dur = 0.0
    try:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(out_mp4)], text=True, timeout=30).strip())
    except Exception:  # noqa: BLE001
        pass
    return {"kind": "story", "n_beats": len(used), "duration_s": round(dur, 1),
            "hook": hook, "beats": used,
            "member_keys": [u["source_url"] for u in used]}
