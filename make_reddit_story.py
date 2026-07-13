#!/usr/bin/env python3
"""Reddit drama storytime renderer — the genre format, done right.

Composes the signature look instead of the generic explainer stack:
  * full-screen satisfying gameplay (no top b-roll / no split)
  * the Reddit post card overlaid while the TITLE is narrated, then it
    dings, whooshes, and fades to reveal the gameplay
  * bold word-by-word ("karaoke") captions, centered in the safe zone
  * subtle tension bed + notification ding + whoosh SFX
  * a clean hold on the final line so the loop is seamless

Reuses the proven helpers from make_explainer_stacked (TTS, Whisper word
timings, music) so only the composition is new.

    from make_reddit_story import build_reddit_story
    build_reddit_story(pkg, Path("out.mp4"))
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_explainer_stacked as base
import reddit_card

W, H, FPS = base.W, base.H, base.FPS
GAMEPLAY_DIR = base.GAMEPLAY_DIR
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Caption safe zone: centered, but nudged up so it never collides with the
# Shorts bottom UI (like/comment rail + title chrome ≈ bottom 15%).
CAP_FONT_SIZE = 92
CAP_MARGIN_V = 620          # px from bottom (Alignment=2) → sits ~mid-screen
CAP_MAX_CHARS = 20          # per caption chunk
CAP_MAX_WORDS = 3


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _gameplay_fullscreen(tag: str, target: float, workdir: Path) -> Path:
    """Pick a gameplay clip and crop it to the FULL 1080x1920 frame for
    `target` seconds, looping the source if it is too short."""
    clips = [p for p in GAMEPLAY_DIR.iterdir()
             if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")] \
        if GAMEPLAY_DIR.exists() else []
    pool = [p for p in clips if tag.lower() in p.stem.lower()] or clips
    if not pool:
        raise RuntimeError(f"no gameplay clips in {GAMEPLAY_DIR}")
    src = random.choice(pool)
    sdur = _dur(src)
    seek = random.uniform(5, max(5, sdur - target - 25)) if sdur > target + 35 \
        else 0.0
    out = workdir / "bg.mp4"
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", "-1", "-ss", f"{seek:.3f}", "-i", str(src),
        "-t", f"{target:.3f}",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H},setsar=1,fps={FPS}",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(out),
    ])
    return out


def _ass_t(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600); m = int((t % 3600) // 60); s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _chunk_words(words: list[base.Word]) -> list[tuple[float, float, str]]:
    """Group Whisper words into short caption chunks (word-by-word feel)."""
    chunks, cur, start = [], [], None
    for w in words:
        t = w.text.strip()
        if not t:
            continue
        if start is None:
            start = w.start
        cur.append(w)
        joined = " ".join(x.text.strip() for x in cur)
        ends_sentence = t[-1] in ".!?"
        if len(cur) >= CAP_MAX_WORDS or len(joined) >= CAP_MAX_CHARS \
                or ends_sentence:
            chunks.append((start, w.end, joined.upper()))
            cur, start = [], None
    if cur:
        chunks.append((start, cur[-1].end, " ".join(
            x.text.strip() for x in cur).upper()))
    return chunks


def _karaoke_ass(words: list[base.Word], path: Path, start_after: float,
                 total: float) -> None:
    """Bold centered word-by-word captions with a quick pop-in."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,{CAP_FONT_SIZE},&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,7,3,2,80,80,{CAP_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    for start, end, text in _chunk_words(words):
        if end <= start_after:
            continue
        start = max(start, start_after)
        end = min(end, total)
        if end <= start:
            continue
        # pop-in: scale 70->100 over 90ms, tiny fade
        eff = (r"{\fad(40,40)\t(0,90,\fscx100\fscy100)\fscx82\fscy82}")
        txt = text.replace("{", "(").replace("}", ")")
        lines.append(
            f"Dialogue: 0,{_ass_t(start)},{_ass_t(end)},Cap,,0,0,0,,{eff}{txt}")
    path.write_text("\n".join(lines))


def _esc(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _ding(workdir: Path) -> Path:
    """Reddit-ish notification 'ding' (two quick bells)."""
    out = workdir / "ding.wav"
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
        "aevalsrc='0.6*sin(2*PI*1660*t)*exp(-9*t)+0.5*sin(2*PI*2490*t)*"
        "exp(-11*t)':d=0.5:s=44100",
        "-af", "volume=0.7", str(out),
    ])
    return out


def build_reddit_story(pkg: dict, out_path: Path, *,
                       gameplay_tag: str = "minecraft") -> None:
    workdir = Path(tempfile.mkdtemp(prefix="reddit_"))
    try:
        cf = reddit_card.card_fields(pkg)
        title = pkg.get("title", "").strip()
        body = base.normalize_for_tts(pkg.get("script", "").strip())
        # Narrate the title first (read over the card), then the story.
        narration = base.normalize_for_tts(title) + " ... " + body

        print("[1/6] TTS narration")
        voice = workdir / "voice.mp3"
        base.tts(narration, voice)
        total = _dur(voice)

        print("[2/6] transcribe for word timings")
        words = base.transcribe(voice)
        # title ends roughly after its word count (title read first)
        n_title = len(base.normalize_for_tts(title).split())
        title_end = (words[min(n_title, len(words)) - 1].end + 0.25
                     if words and n_title else 2.5)
        title_end = min(title_end, max(2.0, total * 0.45))

        print(f"[3/6] gameplay full-screen ({total:.1f}s)")
        bg = _gameplay_fullscreen(gameplay_tag, total, workdir)

        print("[4/6] Reddit card + captions")
        card = workdir / "card.png"
        reddit_card.build_card(
            card, subreddit=cf["subreddit"], username=cf["username"],
            title=title, upvotes=str(cf["upvotes"]),
            comments=str(cf["comments"]), avatar_seed=cf["avatar_seed"])
        caps = workdir / "caps.ass"
        _karaoke_ass(words, caps, title_end, total)

        print("[5/6] audio bed + SFX")
        music = workdir / "music.wav"
        try:
            base.synth_music(total, music, pkg.get("music_vibe", "dark"))
            has_music = True
        except Exception as e:  # noqa: BLE001
            print(f"      music skipped: {e}")
            has_music = False
        ding = _ding(workdir)

        # Card slides up the screen a touch and fades as it hands off.
        fade_st = max(0.3, title_end - 0.4)
        card_w = 980
        graph = (
            f"[0:v]format=yuv420p[bg];"
            f"[3:v]scale={card_w}:-1,format=rgba,"
            f"fade=t=out:st={fade_st:.2f}:d=0.4:alpha=1,setpts=PTS-STARTPTS[card];"
            f"[bg][card]overlay=(W-w)/2:220:enable='lt(t,{title_end:.2f})'[bv];"
            f"[bv]subtitles='{_esc(caps)}'[v]"
        )

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(bg),      # 0
            "-i", str(voice),   # 1
        ]
        if has_music:
            cmd += ["-i", str(music)]   # 2
        else:
            cmd += ["-f", "lavfi", "-t", f"{total:.3f}",
                    "-i", "anullsrc=r=44100:cl=stereo"]  # 2 (silent)
        cmd += ["-loop", "1", "-t", f"{title_end:.2f}", "-i", str(card)]  # 3
        cmd += ["-i", str(ding)]        # 4

        a_graph = (
            "[1:a]volume=1.0,adelay=0|0[vo];"
            "[2:a]volume=0.16[mu];"
            "[4:a]adelay=120|120[dg];"
            "[vo][mu]amix=inputs=2:duration=first:dropout_transition=0[vm];"
            "[vm][dg]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
        full = graph + ";" + a_graph
        cmd += [
            "-filter_complex", full,
            "-map", "[v]", "-map", "[a]",
            "-t", f"{total + 0.3:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(out_path),
        ]
        print("[6/6] compose")
        _run(cmd)
        print(f"done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    import json
    import sys
    pkg = json.loads(Path(sys.argv[1]).read_text())
    build_reddit_story(pkg, Path(sys.argv[2] if len(sys.argv) > 2
                                 else "reddit_out.mp4"))
