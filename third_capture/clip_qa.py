#!/usr/bin/env python3
"""Automated QA gate + vision review for rendered clips (playbook §16-17).

Runs AFTER the render, BEFORE upload. Two layers:

1. Mechanical checks (ffmpeg/ffprobe, cheap, deterministic): broken-clip
   signals the playbook's Cut/Crop QA calls out — black frames, frozen
   frames, long silence gaps (the "sound cuts off" class), missing/short
   audio, A/V duration drift, duration bounds, and face-visibility when the
   render chose a face crop (a face crop that lost the face is the
   midpoint-trap class of failure).
2. Vision review (best-effort): a labeled contact sheet of the final render
   goes to the same headless Claude CLI the author brain uses, answering the
   playbook's §17 checklist (right person visible? crop intentional?
   overlays covering faces? anything broken?). Only a confident "do not
   publish" blocks; no CLI/token or an unclear answer never blocks.

Contract: `review()` NEVER raises. A QA-internal error fails open (publish)
with the error recorded — the gate exists to catch broken clips, not to
become a new way to lose good ones. Verdict "fail" means: do not upload;
the slot's clip is rejected and a different clip competes next run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "assets" / "models"

_T = 120  # per-ffmpeg-call ceiling (s)

# mechanical thresholds (playbook §16)
DUR_MIN, DUR_MAX = 4.0, 62.0
SILENCE_DB, SILENCE_MAX = "-45dB", 2.5   # internal gap that long = broken
TAIL_SILENCE_MAX = 2.0                   # ending on this much silence = abrupt
BLACK_MAX = 0.7                          # black screen that long = broken
FREEZE_MAX = 2.5                         # frozen frame that long = broken
AV_DRIFT_MAX = 0.6                       # |video_dur - audio_dur|
FACE_MIN_RATE = 0.35                     # face-crop must still show a face


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=_T).stderr


def _probe(video: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
         "-show_format", str(video)], text=True, timeout=_T)
    return json.loads(out)


def _mechanical(video: Path, led: dict, problems: list[str]) -> None:
    info = _probe(video)
    vdur = adur = 0.0
    for s in info.get("streams", []):
        d = float(s.get("duration") or info["format"].get("duration") or 0)
        if s.get("codec_type") == "video":
            vdur = d
        elif s.get("codec_type") == "audio":
            adur = d
    dur = float(info["format"].get("duration") or max(vdur, adur))

    if adur <= 0:
        problems.append("no audio stream")
    if not (DUR_MIN <= dur <= DUR_MAX):
        problems.append(f"duration {dur:.1f}s outside {DUR_MIN}-{DUR_MAX}s")
    if adur and vdur and abs(vdur - adur) > AV_DRIFT_MAX:
        problems.append(f"a/v duration drift {abs(vdur - adur):.2f}s")

    # silence gaps (the "sound cuts off" class) + abrupt silent ending
    err = _run(["ffmpeg", "-v", "info", "-i", str(video), "-af",
                f"silencedetect=noise={SILENCE_DB}:d=2.0", "-f", "null", "-"])
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", err)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", err)]
    for i, st in enumerate(starts):
        en = ends[i] if i < len(ends) else dur
        gap = en - st
        if gap >= SILENCE_MAX and st > 0.5 and en < dur - 0.5:
            problems.append(f"audio dead for {gap:.1f}s at {st:.1f}s")
    if starts and len(ends) < len(starts):        # silence runs to EOF
        tail = dur - starts[-1]
        if tail >= TAIL_SILENCE_MAX:
            problems.append(f"ends on {tail:.1f}s of silence (abrupt cut)")

    # black frames
    err = _run(["ffmpeg", "-v", "info", "-i", str(video), "-an", "-vf",
                f"blackdetect=d={BLACK_MAX}:pic_th=0.98", "-f", "null", "-"])
    for m in re.finditer(r"black_start:([\d.]+).*?black_duration:([\d.]+)",
                         err):
        problems.append(f"black screen {float(m.group(2)):.1f}s "
                        f"at {float(m.group(1)):.1f}s")

    # frozen frames (broken concat / stuck segment)
    err = _run(["ffmpeg", "-v", "info", "-i", str(video), "-an", "-vf",
                f"freezedetect=n=-60dB:d={FREEZE_MAX}", "-f", "null", "-"])
    for m in re.finditer(r"freeze_start:\s*([\d.]+)", err):
        problems.append(f"frozen video at {float(m.group(1)):.1f}s")

    # a face crop that lost the face = the wrong-subject/midpoint class
    if led.get("reframe") == "face":
        rate = _face_rate(video, dur)
        if rate is not None and rate < FACE_MIN_RATE:
            problems.append(
                f"face crop but a face is visible in only {rate:.0%} "
                "of sampled frames")


def _face_rate(video: Path, dur: float) -> float | None:
    """Fraction of sampled frames containing a detectable face. None when
    OpenCV/cascade are unavailable (check skipped, never blocks)."""
    try:
        import cv2
        cascade = MODELS_DIR / "haarcascade_frontalface_default.xml"
        cc = cv2.CascadeClassifier(str(cascade))
        if cc.empty():
            return None
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return None
        n_samples, hits, seen = 10, 0, 0
        for k in range(n_samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES,
                    int(total * (k + 0.5) / n_samples))
            ok, frame = cap.read()
            if not ok:
                continue
            seen += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h = gray.shape[0]
            if len(cc.detectMultiScale(gray, 1.15, 5,
                                       minSize=(h // 12, h // 12))):
                hits += 1
        cap.release()
        return hits / seen if seen else None
    except Exception:  # noqa: BLE001
        return None


def contact_sheet(video: Path, out_jpg: Path, cols: int = 3,
                  rows: int = 4) -> list[float] | None:
    """Tile `cols*rows` evenly spaced, timestamp-labeled frames into one
    review image. Returns the timestamps used, or None on failure."""
    try:
        from PIL import Image, ImageDraw
        dur = float(_probe(video)["format"]["duration"])
        n = cols * rows
        stamps = [dur * (k + 0.5) / n for k in range(n)]
        tw, th = 270, 480
        sheet = Image.new("RGB", (cols * tw, rows * th), (16, 16, 16))
        draw = ImageDraw.Draw(sheet)
        with tempfile.TemporaryDirectory() as td:
            for k, ts in enumerate(stamps):
                f = Path(td) / f"{k}.png"
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.2f}",
                     "-i", str(video), "-frames:v", "1",
                     "-vf", f"scale={tw}:{th}", str(f)],
                    timeout=_T, check=True)
                tile = Image.open(f).convert("RGB")
                x, y = (k % cols) * tw, (k // cols) * th
                sheet.paste(tile, (x, y))
                label = f"{ts:.1f}s"
                draw.rectangle([x + 4, y + 4, x + 12 + 8 * len(label), y + 26],
                               fill=(0, 0, 0))
                draw.text((x + 8, y + 8), label, fill=(255, 255, 80))
        sheet.save(out_jpg, quality=82)
        return stamps
    except Exception:  # noqa: BLE001
        return None


_VISION_PROMPT = """You are the final quality reviewer for a Twitch-clip
Shorts channel. The image at {sheet} is a contact sheet of the FINAL RENDER:
{n} frames in reading order (left-to-right, top-to-bottom), each labeled with
its timestamp. Read that image file now.

Clip context: title {title!r}, hook card {hook!r}, series {series!r},
duration {dur:.1f}s, effects applied: {effects}.

Judge it like a human editor (a viewer should think "well-edited clip", never
"where did the person go / why is that emoji on his face / why did it cut"):
1. Is a person or the clear subject of the action properly visible in most
   frames (not cropped half out, not empty space between two people)?
2. Do overlays (emoji, big word, REPLAY stamp, captions) cover a face or the
   main action?
3. Any obviously broken frame: black, garbled, stretched, duplicated?
4. Does the framing look intentional and consistent?

Small imperfections are fine — block ONLY clearly embarrassing/broken output.
Return ONLY a JSON object: {{"publish": true|false,
"problems": ["short strings"], "confidence": 0.0-1.0}}"""


def _vision(sheet: Path, led: dict, dur: float) -> dict | None:
    """Best-effort §17 review via the headless Claude CLI (same brain as the
    author). Returns parsed verdict or None (unreviewed). Never raises."""
    try:
        if not shutil.which("claude"):
            return None
        if not (os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
                or os.environ.get("ANTHROPIC_API_KEY", "").strip()):
            return None
        prompt = _VISION_PROMPT.format(
            sheet=sheet, n=12,
            title=str(led.get("authored_title")
                      or led.get("clip_title") or "")[:80],
            hook=str(led.get("hook", ""))[:60],
            series=str(led.get("series", led.get("edl", {}) and
                       (led.get("edl") or {}).get("style", "chaos"))),
            dur=dur, effects=led.get("effects") or [])
        r = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True, text=True, timeout=240)
        m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
        if not m:
            return None
        out = json.loads(m.group(0))
        return {"publish": bool(out.get("publish", True)),
                "problems": [str(p)[:120] for p in
                             (out.get("problems") or [])][:6],
                "confidence": float(out.get("confidence", 0.0))}
    except Exception:  # noqa: BLE001
        return None


def preflight(video: Path) -> list[str]:
    """Validate a downloaded SOURCE before any authoring/rendering money is
    spent on it (the cheap end of §16). A broken source caught here costs
    ~2s; caught after the render it costs 100s+ and an upload slot.
    Returns a list of problems (empty = good to go). Never raises."""
    problems: list[str] = []
    try:
        info = _probe(video)
    except Exception:  # noqa: BLE001
        return ["source unreadable (corrupt download)"]
    try:
        have_v = have_a = False
        w = h = 0
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                have_v = True
                w = int(s.get("width") or 0)
                h = int(s.get("height") or 0)
            elif s.get("codec_type") == "audio":
                have_a = True
        dur = float(info["format"].get("duration") or 0)
        if not have_v:
            problems.append("no video stream")
        if not have_a:
            problems.append("no audio stream")
        if dur < 6.0:
            problems.append(f"source only {dur:.1f}s — too short to edit")
        if w and h and max(w, h) < 640:
            problems.append(f"resolution too low ({w}x{h}) for Shorts")
        # DARKNESS GATE (IRL/party footage): a genuinely dark source renders
        # to near-black frames the blur-fill can't save — the #1 QA-reject on
        # Streamer University IRL clips. Sample average luma (YAVG 0-255) over
        # the first ~20s; reject in ~2s instead of after a 5-min render. Very
        # conservative threshold so only truly-unwatchable clips are cut.
        if have_v:
            try:
                p = subprocess.run(
                    ["ffmpeg", "-v", "error", "-t", "20", "-i", str(video),
                     "-vf", "fps=2,scale=48:27,signalstats,"
                     "metadata=print:file=-", "-f", "null", "-"],
                    capture_output=True, text=True, timeout=30)
                blob = (p.stdout or "") + (p.stderr or "")
                yavgs = [float(m) for m in re.findall(
                    r"lavfi\.signalstats\.YAVG=([\d.]+)", blob)]
                if yavgs and (sum(yavgs) / len(yavgs)) < 28.0:
                    problems.append(
                        f"source too dark (avg luma "
                        f"{sum(yavgs)/len(yavgs):.0f}/255) — unwatchable IRL/"
                        "night footage")
                # STILL/FROZEN SOURCE GATE (diagnosis #5): a source that
                # barely moves (a paused screen, a static "starting soon"
                # card, a screenshot re-encoded as video) makes a dead Short.
                # signalstats YDIF is the frame-to-frame luma delta; a whole
                # sampled clip averaging near-zero motion is a still, not a
                # moment. Conservative floor so only genuinely static footage
                # is cut — real clips (even calm talking) sit well above it.
                ydifs = [float(m) for m in re.findall(
                    r"lavfi\.signalstats\.YDIF=([\d.]+)", blob)]
                if len(ydifs) >= 6 and (sum(ydifs) / len(ydifs)) < 0.6:
                    problems.append(
                        f"source barely moves (avg frame delta "
                        f"{sum(ydifs)/len(ydifs):.2f}) — static image/paused "
                        "screen, not a clip")
            except Exception as e:  # noqa: BLE001 — motion/luma check best-effort
                print(f"[preflight] luma/motion check skipped ({e})",
                      flush=True)
            # SOURCE BLACK-FRAME GATE (diagnosis #5): a long black stretch in
            # the SOURCE (a scene-transition fade, a dropped-feed gap, a clip
            # that opens on black) is caught here in ~2s instead of after a
            # full render fails QA on it. Reuses the same blackdetect the
            # post-render mechanical gate runs, just on the raw download.
            try:
                err = subprocess.run(
                    ["ffmpeg", "-v", "info", "-t", "30", "-an", "-i",
                     str(video), "-vf", "blackdetect=d=1.0:pic_th=0.98",
                     "-f", "null", "-"],
                    capture_output=True, text=True, timeout=45).stderr
                m = re.search(r"black_duration:([\d.]+)", err or "")
                if m and float(m.group(1)) >= 1.5:
                    problems.append(
                        f"source has {float(m.group(1)):.1f}s of black frames "
                        "— dropped feed / hard fade")
            except Exception as e:  # noqa: BLE001 — black check best-effort
                print(f"[preflight] black check skipped ({e})", flush=True)
    except Exception as e:  # noqa: BLE001 — fail open, the render QA backstops
        print(f"[preflight] check error (ignored): {e}", flush=True)
    return problems


def review(video: Path, led: dict, work: Path) -> dict:
    """Full QA gate. Returns {"verdict": "pass"|"fail", "problems": [...],
    "vision": {...}|None, "contact_sheet": str|None}. NEVER raises; a
    QA-internal error fails open with the error recorded."""
    problems: list[str] = []
    vision = None
    sheet_rel = None
    try:
        _mechanical(video, led, problems)
        dur = float(_probe(video)["format"].get("duration") or 0)
        sheet = work / f"{video.stem}.qa.jpg"
        if contact_sheet(video, sheet) is not None:
            sheet_rel = str(sheet)
            vision = _vision(sheet, led, dur)
        mech_fail = bool(problems)
        vis_fail = bool(vision and not vision["publish"]
                        and vision["confidence"] >= 0.6)
        if vis_fail:
            problems.extend(f"vision: {p}" for p in vision["problems"])
        verdict = "fail" if (mech_fail or vis_fail) else "pass"
    except Exception as e:  # noqa: BLE001 — the gate must not lose clips
        problems.append(f"qa internal error (failed open): "
                        f"{type(e).__name__}: {e}"[:140])
        verdict = "pass"
    return {"verdict": verdict, "problems": problems,
            "vision": vision, "contact_sheet": sheet_rel}
