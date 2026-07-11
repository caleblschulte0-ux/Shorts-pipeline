#!/usr/bin/env python3
"""Shot-plan layer: analyze → classify layout → plan shots → execute.

Playbook §3-§8: the renderer executes an explicit, reasoned plan instead of
improvising a crop from raw detections. Flow per clip (runs on the Stage-1
program, so timestamps are output-timeline):

1. `analyze()` — sample frames ~6Hz, detect faces, cluster them into SUBJECT
   TRACKS (position, size, presence, talk activity from mouth motion,
   position stability). The largest face is NOT automatically the subject.
2. `classify()` — pick a LAYOUT CLASS with different logic per class:
     closeup           one persistent large face → it IS the content
     two_shot          two persistent faces that fit one deliberate wide crop
     split             two persistent faces too far apart → designed stacked
                       split-screen so BOTH stay visible (no midpoint, no
                       ping-pong cuts)
     facecam_gameplay  persistent small locked cam + screen content → designed
                       stacked layout: cam panel up top, FULL-WIDTH gameplay
                       below (the action is never cropped out), captions zone
                       at the bottom
     wide              no reliable subject → caller's blur-fill whole frame
3. `plan()` — emit Shot entries (mode, crop, subjects, REASON) and refuse any
   shot whose crop doesn't contain its subjects (midpoint-trap guard).
4. `render()` — execute the plan with static ffmpeg crops/stacks. The camera
   never moves inside a shot; this phase emits calm single-shot plans (the
   split/stacked layouts replace speaker-chasing entirely).

Contract: `build()` returns (rendered_1080x1920_path | None, summary_dict).
None → the caller uses the blur-fill whole-frame look. NEVER raises.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "assets" / "models"
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
_T = 240

# classification thresholds (fractions of source frame height/width)
PERSIST_MIN = 0.45        # subject must appear in ≥45% of samples
CLOSEUP_H = 0.32          # median face height for "the face IS the content"
TWOSHOT_H = 0.16          # min face height to count as a conversation party
FACECAM_H_MIN = 0.08      # smaller than this = too mushy to blow up (Law 8)
FACECAM_JITTER = 0.05     # locked cam: center wanders < 5% of frame width
MAX_UPSCALE = 3.2         # never enlarge a cam region beyond this (Law 8)

# stacked facecam_gameplay layout (16:9-ish sources)
CAM_PANEL_H = 560         # top: blown-up facecam
GAME_PANEL_H = 608        # middle: full-width source = action always visible
# bottom 752px: blurred fill — captions (y≈1350) land here


@dataclass
class Subject:
    cx: float = 0.0           # running-mean center x (source px)
    cy: float = 0.0
    n: int = 0                # samples seen
    hs: list = field(default_factory=list)    # face heights
    xs: list = field(default_factory=list)    # center-x history
    talk: float = 0.0         # summed mouth-motion score

    def med_h(self) -> float:
        s = sorted(self.hs)
        return s[len(s) // 2] if s else 0.0

    def jitter(self) -> float:
        if len(self.xs) < 2:
            return 0.0
        mean = sum(self.xs) / len(self.xs)
        return (sum((x - mean) ** 2 for x in self.xs) / len(self.xs)) ** 0.5


@dataclass
class Shot:
    mode: str                 # closeup | two_shot | split | stacked
    reason: str
    subjects: list            # participating Subject objects
    crop: tuple | None = None  # (w, h, x, y) for single-crop modes


def _probe_wh_dur(video: Path) -> tuple[int, int, float]:
    import json
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
         "-show_format", str(video)], text=True, timeout=_T)
    info = json.loads(out)
    w = h = 0
    for s in info["streams"]:
        if s.get("codec_type") == "video":
            w, h = int(s["width"]), int(s["height"])
    return w, h, float(info["format"].get("duration") or 0)


def analyze(video: Path) -> dict | None:
    """Subject tracks + frame geometry. None when analysis is impossible."""
    try:
        import cv2
        import numpy as np
        cc = cv2.CascadeClassifier(
            str(MODELS_DIR / "haarcascade_frontalface_default.xml"))
        if cc.empty():
            return None
        cap = cv2.VideoCapture(str(video))
        sw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        sh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or FPS
        if sw == 0 or sh == 0:
            cap.release()
            return None
        step = max(1, int(round(fps / 6)))
        subjects: list[Subject] = []
        prev_gray, idx, samples = None, 0, 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                samples += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cc.detectMultiScale(gray, 1.15, 5,
                                            minSize=(sh // 12, sh // 12))
                for (fx, fy, fw, fh) in faces:
                    cxf, cyf = fx + fw / 2.0, fy + fh / 2.0
                    m = 0.0
                    if prev_gray is not None:
                        my0, my1 = fy + int(fh * 0.55), min(fy + fh, sh)
                        mx0, mx1 = max(fx, 0), min(fx + fw, sw)
                        if my1 > my0 and mx1 > mx0:
                            a = gray[my0:my1, mx0:mx1].astype(np.int16)
                            b = prev_gray[my0:my1, mx0:mx1].astype(np.int16)
                            if a.shape == b.shape and a.size:
                                m = float(np.abs(a - b).mean())
                    # nearest existing track within 12% of width, else new
                    best, bd = None, sw * 0.12
                    for s in subjects:
                        d = ((s.cx - cxf) ** 2 + (s.cy - cyf) ** 2) ** 0.5
                        if d < bd:
                            best, bd = s, d
                    if best is None:
                        best = Subject(cx=cxf, cy=cyf)
                        subjects.append(best)
                    best.cx = (best.cx * best.n + cxf) / (best.n + 1)
                    best.cy = (best.cy * best.n + cyf) / (best.n + 1)
                    best.n += 1
                    best.hs.append(float(fh))
                    best.xs.append(cxf)
                    best.talk += m
                prev_gray = gray
            idx += 1
        cap.release()
        if samples == 0:
            return None
        for s in subjects:
            s.presence = s.n / samples  # type: ignore[attr-defined]
        return {"sw": sw, "sh": sh, "samples": samples,
                "subjects": subjects}
    except Exception:  # noqa: BLE001
        return None


def classify(an: dict) -> tuple[str, list, str]:
    """(layout, ranked_subjects, reason). Ranked by subject SCORE — presence
    + talk activity + size — never just the biggest face (§4)."""
    sw, sh = an["sw"], an["sh"]
    persistent = [s for s in an["subjects"]
                  if getattr(s, "presence", 0) >= PERSIST_MIN
                  and s.med_h() >= FACECAM_H_MIN * sh]
    if not persistent:
        return "wide", [], "no persistent subject — show the whole frame"
    max_talk = max(s.talk for s in persistent) or 1.0
    for s in persistent:
        s.score = (0.5 * getattr(s, "presence", 0)          # type: ignore
                   + 0.3 * (s.talk / max_talk)
                   + 0.2 * min(1.0, s.med_h() / (CLOSEUP_H * sh)))
    ranked = sorted(persistent, key=lambda s: -s.score)     # type: ignore

    big = [s for s in ranked if s.med_h() >= TWOSHOT_H * sh]
    crop_w = sh * 9 / 16
    if len(big) >= 2:
        a, b = big[0], big[1]
        span = abs(a.cx - b.cx) + (a.med_h() + b.med_h()) / 2
        if span <= crop_w * 0.92:
            return ("two_shot", [a, b],
                    "two conversation faces fit one deliberate wide crop")
        return ("split", [a, b],
                "two faces too far apart for one crop — stacked split keeps "
                "both visible (no midpoint, no ping-pong)")
    top = ranked[0]
    if top.med_h() >= CLOSEUP_H * sh:
        return ("closeup", [top],
                "one large persistent face — the face is the content")
    if top.jitter() <= FACECAM_JITTER * sw:
        return ("facecam_gameplay", [top],
                "small locked facecam + screen content — stacked layout "
                "keeps the full-width action AND the reaction visible")
    return "wide", [top], "small moving subject — whole frame is safest"


def plan(an: dict, layout: str, subs: list, reason: str) -> list[Shot] | None:
    """Explicit shots with midpoint-trap guard: every single-crop shot must
    contain its subjects' centers, or the plan is refused (→ wide)."""
    sw, sh = an["sw"], an["sh"]
    crop_w = int(round(sh * 9 / 16))
    if crop_w >= sw:
        return None                       # already portrait — nothing to plan

    def guarded(cx: float, members: list) -> tuple | None:
        x = min(max(cx - crop_w / 2, 0), sw - crop_w)
        for s in members:
            if not (x + crop_w * 0.08 <= s.cx <= x + crop_w * 0.92):
                return None               # MIDPOINT_TRAP / subject outside
        return (crop_w, sh, int(x), 0)

    if layout == "closeup":
        crop = guarded(subs[0].cx, subs)
        return [Shot("closeup", reason, subs, crop)] if crop else None
    if layout == "two_shot":
        pair_cx = (subs[0].cx + subs[1].cx) / 2
        crop = guarded(pair_cx, subs)
        if crop:
            return [Shot("two_shot", reason, subs, crop)]
        return [Shot("split", reason + " (pair crop failed the subject-"
                     "containment guard)", subs)]
    if layout == "split":
        return [Shot("split", reason, subs)]
    if layout == "facecam_gameplay":
        return [Shot("stacked", reason, subs)]
    return None


def _render_single_crop(video: Path, shot: Shot, out: Path) -> Path | None:
    w, h, x, y = shot.crop
    vf = f"crop={w}:{h}:{x}:{y},scale={CANVAS_W}:{CANVAS_H}"
    return _ff(video, vf, out)


def _render_split(video: Path, shot: Shot, an: dict, out: Path) -> Path | None:
    """Designed stacked split-screen: two 1080x960 panels, one per subject."""
    sw, sh = an["sw"], an["sh"]
    pw = min(sw, int(round(sh * 1080 / 960)))       # panel crop, full height
    parts, labels = [], []
    subs = sorted(shot.subjects[:2], key=lambda s: s.cx)
    for i, s in enumerate(subs):
        x = int(min(max(s.cx - pw / 2, 0), sw - pw))
        parts.append(f"[v{i}]crop={pw}:{sh}:{x}:0,"
                     f"scale={CANVAS_W}:{CANVAS_H // 2}[p{i}]")
        labels.append(f"[p{i}]")
    fc = (f"[0:v]split=2[v0][v1];{parts[0]};{parts[1]};"
          f"{labels[0]}{labels[1]}vstack=inputs=2[vout]")
    return _ff_complex(video, fc, out)


def _render_stacked(video: Path, shot: Shot, an: dict,
                    out: Path) -> Path | None:
    """Facecam panel on top, FULL-WIDTH gameplay in the middle (the action is
    never cropped out), blurred fill below where the captions live."""
    sw, sh = an["sw"], an["sh"]
    cam = shot.subjects[0]
    ch = cam.med_h() * 2.4                          # cam crop around the face
    cw = ch * (CANVAS_W / CAM_PANEL_H)
    if cw > sw or CANVAS_W / cw > MAX_UPSCALE:      # Law 8: don't zoom to mush
        return None
    cx = min(max(cam.cx - cw / 2, 0), sw - cw)
    cy = min(max(cam.cy - ch / 2, 0), sh - ch)
    game_h = int(round(sh * CANVAS_W / sw))         # fit full width
    game_h -= game_h % 2
    game_y = CAM_PANEL_H
    fc = (
        f"[0:v]split=3[c][g][b];"
        f"[c]crop={int(cw)}:{int(ch)}:{int(cx)}:{int(cy)},"
        f"scale={CANVAS_W}:{CAM_PANEL_H}[cam];"
        f"[g]scale={CANVAS_W}:{game_h}[game];"
        f"[b]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
        f"increase,crop={CANVAS_W}:{CANVAS_H},gblur=sigma=24,"
        f"eq=brightness=-0.12:saturation=1.15[bg];"
        f"[bg][cam]overlay=0:0[t1];"
        f"[t1][game]overlay=0:{game_y}[vout]"
    )
    return _ff_complex(video, fc, out)


def _face_bands(shot: Shot, an: dict) -> list:
    """Vertical [y0, y1] bands (fractions of the 1920 output height) that
    contain faces — the overlay layer must not place graphics there (§15).
    Bands are generous (±1 face height around the center)."""
    sh = an["sh"]
    bands = []
    if shot.mode in ("closeup", "two_shot"):
        # full-height crop scaled to 1920: y fractions carry over directly
        for s in shot.subjects:
            h = s.med_h()
            bands.append([max(0.0, (s.cy - h) / sh),
                          min(1.0, (s.cy + h) / sh)])
    elif shot.mode == "split":
        subs = sorted(shot.subjects[:2], key=lambda s: s.cx)
        for i, s in enumerate(subs):
            h = s.med_h()
            y0 = max(0.0, (s.cy - h) / sh) * 0.5 + i * 0.5
            y1 = min(1.0, (s.cy + h) / sh) * 0.5 + i * 0.5
            bands.append([y0, y1])
    elif shot.mode == "stacked":
        bands.append([0.0, CAM_PANEL_H / CANVAS_H])   # whole cam panel
    return [[round(a, 3), round(b, 3)] for a, b in bands]


def _ff(video: Path, vf: str, out: Path) -> Path | None:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", vf,
             "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
             "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)],
            check=True, timeout=_T)
        return out if out.exists() else None
    except Exception:  # noqa: BLE001
        return None


def _ff_complex(video: Path, fc: str, out: Path) -> Path | None:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video),
             "-filter_complex", fc, "-map", "[vout]", "-map", "0:a?",
             "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
             "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)],
            check=True, timeout=_T)
        return out if out.exists() else None
    except Exception:  # noqa: BLE001
        return None


def build(video: Path, work: Path,
          analyze_on: Path | None = None) -> tuple[Path | None, dict]:
    """Analyze → classify → plan → render. (path|None, summary). NEVER
    raises; None → caller's blur-fill whole-frame fallback.

    `analyze_on` (playbook §3): analysis belongs to the SOURCE — pass the
    unretimed cut here when `video` is the Stage-1 program, whose zooms and
    replays scatter a face across position clusters and dilute presence.
    Both share the same frame geometry, so the plan's crops apply to both."""
    summary = {"layout": "wide", "reason": "analysis unavailable",
               "shots": []}
    try:
        an = analyze(analyze_on or video)
        if an is None:
            return None, summary
        if analyze_on is not None:
            vw, vh, _ = _probe_wh_dur(video)
            if (vw, vh) != (an["sw"], an["sh"]):
                summary["reason"] = ("source/program geometry mismatch "
                                     f"({an['sw']}x{an['sh']} vs {vw}x{vh})")
                return None, summary
        layout, subs, reason = classify(an)
        summary.update(layout=layout, reason=reason,
                       n_subjects=len([s for s in an["subjects"]
                                       if getattr(s, "presence", 0)
                                       >= PERSIST_MIN]))
        if layout == "wide":
            return None, summary
        shots = plan(an, layout, subs, reason)
        if not shots:
            summary["reason"] += " (plan refused: containment guard)"
            return None, summary
        summary["shots"] = [{"mode": s.mode, "reason": s.reason}
                            for s in shots]
        shot = shots[0]                    # calm single-shot plans this phase
        out = work / "shotplan.mp4"
        if shot.mode in ("closeup", "two_shot"):
            rendered = _render_single_crop(video, shot, out)
        elif shot.mode == "split":
            rendered = _render_split(video, shot, an, out)
        elif shot.mode == "stacked":
            rendered = _render_stacked(video, shot, an, out)
        else:
            rendered = None
        if rendered is None:
            summary["shots"] = []
            summary["reason"] += " (render fell back to whole frame)"
        else:
            summary["face_bands"] = _face_bands(shot, an)
        return rendered, summary
    except Exception as e:  # noqa: BLE001
        summary["reason"] = f"shot_plan error (fell back): " \
                            f"{type(e).__name__}"
        return None, summary
