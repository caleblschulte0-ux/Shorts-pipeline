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
# A facecam is a small box in a corner of the stream. A face whose cam
# panel would take more than this share of the frame IS the frame — an IRL
# camera — and stacking it put the same picture on screen twice (operator,
# 2026-10-11, of Alinity in her kitchen: "what the fuck was this video").
CAM_AREA_MAX = 0.15

# stacked facecam_gameplay layout (16:9-ish sources)
CAM_PANEL_H = 560         # top: blown-up facecam
GAME_PANEL_H = 608        # middle: full-width source = action always visible
# bottom 752px: blurred fill — captions (y≈1350) land here


# The blurred fill is made from the TOP of the frame: the bottom is where a
# stream burns its own captions, and blown up behind ours they read as ghost
# text (vision QA, 2026-10-09). clip_edit's own blur fill uses the same.
BG_TOP = 0.6


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


# ONE CROP FOR A MULTI-CAMERA SOURCE CUTS SOMEBODY OFF (operator,
# 2026-11-03, of Wembanyama's sit-down interview: "The cutting sucks").
# The interviewer sat front-on right of centre; Wembanyama was shot in
# profile at the left edge. Every frontal face fell on the interviewer, so
# the one crop for the whole clip was his, and every shot of Wembanyama
# showed half a face, a jacket, then empty background. A camera cut is a
# new picture and gets its own framing, and a face in profile is a face.
try:
    import cv2 as _cv2
    PROFILE_CASCADE = str(Path(_cv2.data.haarcascades)
                          / "haarcascade_profileface.xml")
except Exception:  # noqa: BLE001
    PROFILE_CASCADE = ""
CUT_HIST = 0.30       # Bhattacharyya distance between frames = a new camera
CUT_DIFF = 8.0        # ...or a mean grey change on a 64x36 thumbnail this
CUT_RATIO = 5.0       # big AND this many times the clip's usual change
                      # (a dim sit-down cuts at 10-22 against a usual 0.5;
                      # a panning broadcast changes 10+ every frame)
MIN_SHOT_S = 0.6      # a "shot" shorter than this joins its neighbour
SHOT_PRESENCE = 0.4   # a face in this share of a shot's samples frames it
SHOT_FACE_H = 0.16    # ...and at least this tall (a party, not a player)


def _is_cut(a, b, usual: list | None = None) -> bool:
    """Is thumbnail `b` a different camera from thumbnail `a`? `usual`
    holds recent frame changes (this call appends to it)."""
    import cv2
    import numpy as np
    ha = cv2.calcHist([a], [0], None, [32], [0, 256])
    hb = cv2.calcHist([b], [0], None, [32], [0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    d = cv2.compareHist(ha, hb, cv2.HISTCMP_BHATTACHARYYA)
    diff = float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())
    base = sorted(usual)[len(usual) // 2] if usual else 0.0
    if usual is not None:
        usual.append(diff)
        del usual[:-30]
    # the ratio needs a clip's usual change to compare with; the first
    # frames only ever cut on a clear histogram change
    known = usual is not None and len(usual) > 5
    return d > CUT_HIST or (known and diff > CUT_DIFF
                            and diff > CUT_RATIO * max(base, 0.5))


def _profiles(cc, gray, sw: int, sh: int, t: float) -> list[tuple]:
    """Faces in profile, looking either way: (t, cx, cy, h, "profile").
    Run at half size (a profile face worth framing is a big one)."""
    import cv2
    half = cv2.resize(gray, (sw // 2, sh // 2))
    out = []
    for flip in (False, True):
        img = cv2.flip(half, 1) if flip else half
        for (fx, fy, fw, fh) in cc.detectMultiScale(
                img, 1.15, 6, minSize=(sh // 16, sh // 16)):
            cx = fx + fw / 2.0
            if flip:
                cx = sw / 2 - cx
            out.append((round(t, 3), cx * 2, (fy + fh / 2.0) * 2,
                        float(fh) * 2, "profile"))
    return out


def shots_of(an: dict) -> list[tuple]:
    """The source's camera shots as (t0, t1) seconds."""
    dur = float(an.get("dur") or 0)
    edges = [0.0] + [float(c) for c in an.get("cuts") or []
                     if MIN_SHOT_S <= c <= dur - MIN_SHOT_S] + [dur]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]


def _shot_face(an: dict, t0: float, t1: float) -> dict | None:
    """The face that frames shot [t0, t1): the most present big one."""
    sw, sh = an["sw"], an["sh"]
    n = sum(1 for t in an.get("ts") or [] if t0 <= t < t1)
    if not n:
        return None
    groups: list[dict] = []
    for (t, cx, cy, h, _k) in an.get("dets") or []:
        if not (t0 <= t < t1):
            continue
        g = next((g for g in groups if abs(g["cx"] - cx) < sw * 0.12), None)
        if g is None:
            g = {"cx": cx, "cy": cy, "hs": [], "times": set()}
            groups.append(g)
        k = len(g["hs"])
        g["cx"] = (g["cx"] * k + cx) / (k + 1)
        g["cy"] = (g["cy"] * k + cy) / (k + 1)
        g["hs"].append(h)
        g["times"].add(t)
    best = None
    for g in groups:
        hs = sorted(g["hs"])
        g["h"] = hs[len(hs) // 2]
        g["presence"] = len(g["times"]) / n
        if g["presence"] >= SHOT_PRESENCE and g["h"] >= SHOT_FACE_H * sh \
                and (best is None or len(g["times"]) * g["h"]
                     > len(best["times"]) * best["h"]):
            best = g
    return best


COLS = 10             # the framer's numbered columns
MAX_FRAMED_SHOTS = 8  # more shots than this: one look at each is too many


def crop_from_cols(sw: int, sh: int, a: int, b: int) -> tuple | None:
    """The window that keeps columns a..b: a 9:16 crop when they fit one,
    the 3:4 action window when they fit that, else None (the whole frame)."""
    cx = (a + b + 1) / 2 * sw / COLS
    span = (b - a + 1) * sw / COLS
    for aw, ah in ((9, 16), ACTION_CROP_ASPECT):
        w = int(round(sh * aw / ah))
        w -= w % 2
        if w >= sw:
            return None
        if span <= w * 1.02:
            x = int(min(max(cx - w / 2, 0), sw - w))
            return (w, sh - sh % 2, x - x % 2, 0)
    return None


def _column_frame(video: Path, t: float, sw: int, sh: int,
                  out: Path) -> Path | None:
    """One frame at `t` with COLS numbered columns drawn over it."""
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                        "-i", str(video), "-frames:v", "1", "-vf",
                        "scale=960:-2", str(out)],
                       check=True, timeout=60, capture_output=True)
        from PIL import Image, ImageDraw
        with Image.open(out) as im:
            im = im.convert("RGB")
            d = ImageDraw.Draw(im)
            try:
                from PIL import ImageFont
                font = ImageFont.load_default(size=22)
            except Exception:  # noqa: BLE001 — an old Pillow
                font = None
            cw = im.width / COLS
            for k in range(COLS):
                x = int(k * cw)
                if k:
                    d.line([(x, 0), (x, im.height)], fill=(255, 230, 0),
                           width=2)
                d.rectangle([x + 3, 3, x + 31, 33], fill=(0, 0, 0))
                d.text((x + 10, 6), str(k), fill=(255, 230, 0), font=font)
            im.save(out)
        return out
    except Exception:  # noqa: BLE001
        return None


def framed(an: dict, video: Path, work: Path, title: str = "") -> list | None:
    """Per-shot crops a BRAIN chose by looking — [{"t0","t1","crop","why"}]
    — or None (no brain, no answer, too many shots): then the face and
    motion heuristics frame it as before."""
    from shared import shot_relevance
    sw, sh = int(an.get("sw") or 0), int(an.get("sh") or 0)
    if sw <= sh or not shot_relevance.enabled():
        return None
    shots = shots_of(an)
    if not shots or len(shots) > MAX_FRAMED_SHOTS:
        return None
    work.mkdir(parents=True, exist_ok=True)
    imgs = []
    for i, (t0, t1) in enumerate(shots):
        p = _column_frame(video, (t0 + t1) / 2, sw, sh,
                          work / f"frame_cols{i}.png")
        if p is None:
            return None
        imgs.append((i, p))
    got = shot_relevance.frame_shots(imgs, title=title)
    if not got:
        return None
    out = []
    for i, (t0, t1) in enumerate(shots):
        g = got[i]
        crop = None if g.get("whole") else crop_from_cols(sw, sh, *g["cols"])
        f = _shot_face(an, t0, t1)
        if f is not None and (crop is None or not (
                crop[2] <= f["cx"] <= crop[2] + crop[0])):
            f = None                     # a band only for a face it shows
        out.append({"t0": t0, "t1": t1, "crop": crop, "face": f,
                    "why": "the framer: " + (g.get("why") or "")
                    + (" (whole frame)" if crop is None else "")})
    return out


def _window(an: dict, layout: str, subs: list, reason: str) -> tuple | None:
    """The crop the one-crop plan would use for the whole clip."""
    if layout == "wide":
        return action_window(an)
    if layout in ("closeup", "two_shot"):
        got = plan(an, layout, subs, reason)
        if got and got[0].crop:
            return got[0].crop
    return None


def cameras(an: dict, layout: str, subs: list, reason: str) -> list | None:
    """A framing PER CAMERA SHOT — [{"t0","t1","crop","why"}] — when the
    one crop of `layout` cuts a shot's own face off; None when one crop
    serves every shot (then nothing changes). A shot's crop is a 9:16
    window on its face; a shot with no big face keeps the one-crop window,
    or the whole frame when there is none."""
    sw, sh = int(an.get("sw") or 0), int(an.get("sh") or 0)
    if sw <= sh or layout not in ("closeup", "two_shot", "wide"):
        return None
    shots = shots_of(an)
    if len(shots) < 2:
        return None
    crop_w = int(round(sh * 9 / 16))
    crop_w -= crop_w % 2
    win = _window(an, layout, subs, reason)
    out, broken = [], False
    for (t0, t1) in shots:
        f = _shot_face(an, t0, t1)
        if f is None:
            out.append({"t0": t0, "t1": t1, "crop": win,
                        "why": "no face to frame — the clip's own window"
                        if win else "no face to frame — the whole frame"})
            continue
        if win is None or not (win[2] + win[0] * 0.08 <= f["cx"]
                               <= win[2] + win[0] * 0.92):
            broken = True
        x = int(min(max(f["cx"] - crop_w / 2, 0), sw - crop_w))
        out.append({"t0": t0, "t1": t1, "crop": (crop_w, sh, x - x % 2, 0),
                    "why": "framed on this shot's face", "face": f})
    return out if broken else None


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
        # EVERY CAMERA, not one average of them: per-frame cut detection and
        # per-sample faces (front-on AND in profile) with their times, so
        # `cameras()` can frame each shot of a multi-camera source on its
        # own. The tracks above stay frontal-only, exactly as they were.
        prof = cv2.CascadeClassifier(PROFILE_CASCADE) \
            if Path(PROFILE_CASCADE).exists() else None
        if prof is not None and prof.empty():
            prof = None
        cuts: list[float] = []
        dets: list[tuple] = []
        ts: list[float] = []
        prev_small, usual = None, []
        col_energy = np.zeros(sw, dtype=np.float64)
        row_energy = np.zeros(sh, dtype=np.float64)
        col_detail = np.zeros(sw, dtype=np.float64)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                               (64, 36), interpolation=cv2.INTER_AREA)
            if prev_small is not None and _is_cut(prev_small, small, usual):
                t = idx / fps
                if not cuts or t - cuts[-1] >= MIN_SHOT_S:
                    cuts.append(round(t, 3))
            prev_small = small
            if idx % step == 0:
                samples += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                t = idx / fps
                ts.append(round(t, 3))
                faces = cc.detectMultiScale(gray, 1.15, 5,
                                            minSize=(sh // 12, sh // 12))
                for (fx, fy, fw, fh) in faces:
                    dets.append((round(t, 3), fx + fw / 2.0, fy + fh / 2.0,
                                 float(fh), "front"))
                if prof is not None:
                    dets += _profiles(prof, gray, sw, sh, t)
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
                # WHERE the action is, horizontally. The face cascade only
                # answers "is there a trackable face"; on a clips channel
                # the answer is usually no (gameplay, IRL, moving camera),
                # and the whole frame was then shown at 31.6% of a 9:16
                # canvas. A column-wise frame-difference profile costs one
                # extra mean() on arrays we have already decoded and tells
                # us where to point the camera when no face does.
                if prev_gray is not None and prev_gray.shape == gray.shape:
                    d = np.abs(gray.astype(np.int16)
                               - prev_gray.astype(np.int16))
                    col_energy += d.mean(axis=0)
                    row_energy += d.mean(axis=1)
                # WHERE there is something to SEE, still or not: a texted
                # screenshot or a call log beside a commentator does not
                # move, so the motion profile above cannot find it.
                g16 = gray.astype(np.int16)
                col_detail[1:] += np.abs(np.diff(g16, axis=1)).mean(axis=0)
                prev_gray = gray
            idx += 1
        cap.release()
        if samples == 0:
            return None
        for s in subjects:
            s.presence = s.n / samples  # type: ignore[attr-defined]
        return {"sw": sw, "sh": sh, "samples": samples,
                "subjects": subjects, "fps": fps,
                "dur": idx / fps, "cuts": cuts, "dets": dets, "ts": ts,
                "col_energy": col_energy.tolist(),
                "row_energy": row_energy.tolist(),
                "col_detail": col_detail.tolist()}
    except Exception:  # noqa: BLE001
        return None


def _cam_area(s: "Subject", sw: float, sh: float) -> float:
    """Share of the frame the stacked layout's cam panel would crop —
    the same rectangle `_render_stacked` takes."""
    ch = s.med_h() * 2.4
    cw = ch * (CANVAS_W / CAM_PANEL_H)
    return (min(cw, sw) * min(ch, sh)) / float(sw * sh)


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
    if _cam_area(top, sw, sh) > CAM_AREA_MAX:
        return ("wide", [top], "face too big for a facecam — the camera IS "
                "the content, show the whole frame")
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


# How much of the 9:16 canvas the sharp picture should fill when no face
# is trackable. A 16:9 source fitted whole into 1080x1920 is 1080x607 —
# 31.6% BY CONSTRUCTION, with two thirds of the frame blurred padding. That
# is the single loudest "reposted clip" signal a Short can carry, and it was
# the default on 52 of the last 97 posted videos. Cropping to 3:4 of the
# source lifts the sharp area to ~75% while still leaving a soft band for
# the hook card and captions. Full 9:16 would fill it completely but throws
# away 68% of the width, which loses the HUD/second person too often.
ACTION_CROP_ASPECT = (3, 4)
MIN_ACTION_GAIN = 1.25       # don't bother re-encoding for a tiny win


def action_window(an: dict, aspect: tuple = ACTION_CROP_ASPECT) -> tuple | None:
    """(w, h, x, y): the `aspect` window over the busiest part of the frame.

    Used when classify() says "wide" — i.e. no persistent face. The choice
    is not arbitrary: it is the window maximising summed frame-difference
    energy, so the crop points at whatever is actually MOVING. Returns None
    when the source is already tall enough that cropping buys nothing."""
    sw, sh = int(an.get("sw") or 0), int(an.get("sh") or 0)
    if sw <= 0 or sh <= 0:
        return None
    aw, ah = aspect
    want_w = int(round(min(sw, sh * aw / ah)))
    if want_w >= sw * 0.98:
        return None                      # already >= this tall; nothing to do
    # sharp-area gain vs fitting the whole frame; skip a re-encode for <25%
    if (sw / want_w) < MIN_ACTION_GAIN:
        return None
    col = [float(v) for v in (an.get("col_energy") or [])]
    if len(col) != sw or sum(col) <= 0:
        x = (sw - want_w) / 2.0
    else:
        total = sum(col)
        # CENTRE ON THE ACTION, don't just contain it. Maximising summed
        # energy alone ties across every window that holds the busy region,
        # and argmax then returns the LEFTMOST of them — putting the subject
        # against the edge of frame. The energy centroid is where a camera
        # operator would point.
        centroid = sum(i * v for i, v in enumerate(col)) / total
        # A FLAT profile means motion is everywhere (a panning camera, a
        # busy scene). Its centroid is meaningless, so say so and centre.
        even = total / sw
        peaky = sum(abs(v - even) for v in col) / total
        x = (centroid - want_w / 2.0) if peaky > 0.25 else (sw - want_w) / 2.0
    x = max(0, min(int(x), sw - want_w))
    # even dimensions keep libx264 happy
    return (want_w - want_w % 2, sh - sh % 2, x - x % 2, 0)


# A FACE BESIDE WHAT IT IS TALKING ABOUT (operator, 2026-10-13, of a
# Kai/Reggie cut: a commentator on one side of the frame and the texts he
# was reading on the other, and one crop "split the difference and ended
# up catching nothing"). When a persistent face sits to one side and the
# rest of the frame has something on it, show both: what is shown on top,
# the face below, each its own half of the canvas. Nothing overlaps, so
# nothing is on screen twice.
SIDE_FACE = 0.40          # face centre outside the middle 20% of the width
CONTENT_MIN_W = 0.30      # the other side is at least this share of width
CONTENT_DETAIL = 0.6      # ...and at least this busy, relative to the frame
FACE_PANEL = 2.8          # face panel height, in face heights
PANEL_H = CANVAS_H // 2
PANEL_ASPECT = CANVAS_W / PANEL_H          # 9:8


def face_and_content(an: dict) -> dict | None:
    """{"face": (w,h,x,y), "content": (w,h,x,y), "side": "left"|"right"}
    for a landscape source whose persistent face sits to one side of
    something worth seeing; None otherwise."""
    sw, sh = int(an.get("sw") or 0), int(an.get("sh") or 0)
    if sw <= 0 or sh <= 0 or sw / sh < 1.5:
        return None
    faces = [s for s in an.get("subjects") or []
             if getattr(s, "presence", 0) >= PERSIST_MIN
             and s.med_h() >= FACECAM_H_MIN * sh]
    if len(faces) != 1:
        return None                      # two faces are the split's job
    f = faces[0]
    if SIDE_FACE * sw <= f.cx <= (1 - SIDE_FACE) * sw:
        return None
    fh = min(float(sh), f.med_h() * FACE_PANEL)
    fw = fh * PANEL_ASPECT
    if fw > sw * 0.6 or CANVAS_W / fw > MAX_UPSCALE:
        return None
    fx = min(max(f.cx - fw / 2, 0.0), sw - fw)
    fy = min(max(f.cy - fh / 2, 0.0), sh - fh)
    right = f.cx > sw / 2
    c0, c1 = (0.0, fx) if right else (fx + fw, float(sw))
    cw = c1 - c0
    if cw < CONTENT_MIN_W * sw or CANVAS_W / cw > MAX_UPSCALE:
        return None
    det = [float(v) for v in an.get("col_detail") or []]
    if len(det) != sw or sum(det) <= 0:
        return None
    side = det[int(c0):int(c1)]
    if sum(side) / len(side) < CONTENT_DETAIL * sum(det) / sw:
        return None                      # a blank wall beside him
    ch = min(float(sh), cw / PANEL_ASPECT)
    cw = ch * PANEL_ASPECT
    cx = c1 - cw if right else c0        # keep the edge next to the face
    cy = (sh - ch) / 2

    def ev(*v):
        return tuple(int(x) - int(x) % 2 for x in v)
    return {"face": ev(fw, fh, fx, fy), "content": ev(cw, ch, cx, cy),
            "side": "right" if right else "left"}


def _render_face_content(video: Path, boxes: dict, out: Path) -> Path | None:
    """What is shown on top, the face below: two 1080x960 halves."""
    cw, ch, cx, cy = boxes["content"]
    fw, fh, fx, fy = boxes["face"]
    fc = (f"[0:v]split=2[a][b];"
          f"[a]crop={cw}:{ch}:{cx}:{cy},scale={CANVAS_W}:{PANEL_H}[top];"
          f"[b]crop={fw}:{fh}:{fx}:{fy},scale={CANVAS_W}:{PANEL_H}[bot];"
          f"[top][bot]vstack=inputs=2[vout]")
    return _ff_complex(video, fc, out)


def _render_single_crop(video: Path, shot: Shot, out: Path) -> Path | None:
    w, h, x, y = shot.crop
    vf = f"crop={w}:{h}:{x}:{y},scale={CANVAS_W}:{CANVAS_H}"
    return _ff(video, vf, out)


def _render_action_crop(video: Path, shot: Shot, out: Path) -> Path | None:
    """Action crop -> full-width sharp picture, blur-filled to the canvas.

    NOT _render_single_crop: that force-scales the crop to 1080x1920, which
    is only correct because every other crop mode computes a 9:16 rectangle
    (crop_w = sh*9/16). A 3:4 action window pushed through it would be
    STRETCHED — everyone in frame 30% too wide. Preserve the aspect: scale
    to fill the width, then blur-fill the remaining band exactly the way the
    house layout does, so captions and the hook card still have somewhere to
    sit."""
    w, h, x, y = shot.crop
    fc = (f"[0:v]crop={w}:{h}:{x}:{y},split=2[c0][c1];"
          f"[c0]crop=iw:ih*{BG_TOP}:0:0,scale={CANVAS_W}:{CANVAS_H}:"
          f"force_original_aspect_ratio=increase,"
          f"crop={CANVAS_W}:{CANVAS_H},gblur=sigma=28,"
          f"eq=brightness=-0.03[bg];"
          f"[c1]scale={CANVAS_W}:{CANVAS_H}:"
          f"force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]")
    return _ff_complex(video, fc, out)


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
        f"[b]crop=iw:ih*{BG_TOP}:0:0,"
        f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
        f"increase,crop={CANVAS_W}:{CANVAS_H},gblur=sigma=24,"
        f"eq=brightness=-0.12:saturation=1.15[bg];"
        f"[bg][cam]overlay=0:0[t1];"
        f"[t1][game]overlay=0:{game_y}[vout]"
    )
    return _ff_complex(video, fc, out)


def _render_cameras(video: Path, cams: list, an: dict,
                    out: Path) -> Path | None:
    """Each camera shot cut out and framed on its own, joined back in
    order. A 9:16 crop fills the canvas; any other window (the action crop,
    or the whole frame) is blur-filled the way _render_action_crop does."""
    sw, sh = an["sw"], an["sh"]
    k = len(cams)
    parts = [f"[0:v]split={k}" + "".join(f"[v{i}]" for i in range(k))]
    for i, c in enumerate(cams):
        end = "" if i == k - 1 else f":end={c['t1']:.3f}"
        head = (f"[v{i}]trim=start={c['t0']:.3f}{end},setpts=PTS-STARTPTS")
        w, h, x, y = c["crop"] or (sw - sw % 2, sh - sh % 2, 0, 0)
        if abs(w / h - 9 / 16) < 0.01:
            parts.append(f"{head},crop={w}:{h}:{x}:{y},"
                         f"scale={CANVAS_W}:{CANVAS_H},setsar=1[s{i}]")
        else:
            parts.append(
                f"{head},crop={w}:{h}:{x}:{y},split=2[b{i}][f{i}];"
                f"[b{i}]crop=iw:ih*{BG_TOP}:0:0,scale={CANVAS_W}:{CANVAS_H}:"
                f"force_original_aspect_ratio=increase,"
                f"crop={CANVAS_W}:{CANVAS_H},gblur=sigma=28,"
                f"eq=brightness=-0.03[g{i}];"
                f"[f{i}]scale={CANVAS_W}:{CANVAS_H}:"
                f"force_original_aspect_ratio=decrease[h{i}];"
                f"[g{i}][h{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[s{i}]")
    parts.append("".join(f"[s{i}]" for i in range(k))
                 + f"concat=n={k}:v=1:a=0[vout]")
    return _ff_complex(video, ";".join(parts), out)


def _camera_bands(cams: list, an: dict) -> list:
    """Face bands of every framed shot (the overlay layer avoids them all)."""
    sh = an["sh"]
    bands = []
    for c in cams:
        f = c.get("face")
        if f and c.get("crop") and abs(c["crop"][0] / c["crop"][1]
                                       - 9 / 16) < 0.01:
            band = [round(max(0.0, (f["cy"] - f["h"]) / sh), 3),
                    round(min(1.0, (f["cy"] + f["h"]) / sh), 3)]
            if band not in bands:
                bands.append(band)
    return bands


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


SUB_BAND = 0.35        # the bottom of the source subtitles sit in
SUB_SPAN = 0.6         # text across this much of the width is a subtitle
SUB_FRAMES = 2         # ... in this many sampled frames


def _text_span(img: Path) -> float:
    """How much of the picture's width confident words (tesseract, >= 70,
    3+ letters) run across, 0..1. 0 without tesseract."""
    import re as _re
    import subprocess as _sp
    try:
        r = _sp.run(["tesseract", str(img), "-", "--psm", "11", "tsv"],
                    capture_output=True, text=True, timeout=60)
        from PIL import Image
        with Image.open(img) as im:
            width = im.width
    except Exception:  # noqa: BLE001
        return 0.0
    xs = []
    for row in (r.stdout or "").splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12:
            continue
        try:
            conf, left, w = float(c[10]), int(c[6]), int(c[8])
        except ValueError:
            continue
        if conf >= 70 and len(_re.sub(r"[^A-Za-z]", "", c[11])) >= 3:
            xs += [left, left + w]
    return (max(xs) - min(xs)) / width if xs and width else 0.0


def subtitle_spans(video: Path, dur: float, samples: int = 5) -> list:
    """How wide the words in the bottom band run, per sampled frame (0..1)."""
    import subprocess as _sp
    import tempfile as _tf
    spans = []
    try:
        with _tf.TemporaryDirectory() as td:
            for k in range(samples):
                t = dur * (k + 0.5) / samples
                fr = Path(td) / f"s{k}.png"
                _sp.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                         "-i", str(video), "-frames:v", "1", "-vf",
                         f"crop=iw:ih*{SUB_BAND}:0:ih*{1 - SUB_BAND},"
                         "scale=iw*2:-2,format=gray", str(fr)],
                        check=True, timeout=60, capture_output=True)
                spans.append(round(_text_span(fr), 3))
    except Exception:  # noqa: BLE001
        return spans
    return spans


def burned_subtitles(video: Path, dur: float, samples: int = 5) -> bool:
    """Does a landscape source carry subtitles burned into its bottom,
    running wider than any 9:16 crop could keep? Cropping them cuts every
    line off at both ends (Yaxel Lendeborg on Luka, posted 2026-10-23:
    a press conference whose own subtitles read "atching all the whining
    ar..."), so such a source is shown whole. Never raises."""
    spans = subtitle_spans(video, dur, samples)
    LAST_SPANS[:] = spans
    return sum(1 for x in spans if x >= SUB_SPAN) >= SUB_FRAMES


LAST_SPANS: list = []     # the last burned_subtitles() read, for the ledger


def build(video: Path, work: Path,
          analyze_on: Path | None = None,
          an: dict | None = None, title: str = "") -> tuple[Path | None, dict]:
    """Analyze → classify → plan → render. (path|None, summary). NEVER
    raises; None → caller's blur-fill whole-frame fallback.

    `analyze_on` (playbook §3): analysis belongs to the SOURCE — pass the
    unretimed cut here when `video` is the Stage-1 program, whose zooms and
    replays scatter a face across position clusters and dilute presence.
    Both share the same frame geometry, so the plan's crops apply to both.

    `an` is an ALREADY-COMPUTED analysis of `analyze_on`. clip_edit runs
    analyze(cut) up front to decide the calm treatment and then called this
    with analyze_on=cut, so the identical full cv2 decode + Haar pass ran
    twice per render for the same answer. Pass it through instead."""
    summary = {"layout": "wide", "reason": "analysis unavailable",
               "shots": []}
    try:
        if an is None:
            an = analyze(analyze_on or video)
        if an is None:
            return None, summary
        # NOT A CROP THAT CUTS THE FOOTAGE'S OWN SUBTITLES OFF: the whole
        # frame instead (operator, 2026-10-28: "we won't play clips that
        # don't make sense")
        subbed = an["sw"] > an["sh"] and burned_subtitles(
            analyze_on or video, _probe_wh_dur(analyze_on or video)[2])
        if an["sw"] > an["sh"]:
            summary["subtitle_spans"] = list(LAST_SPANS)
        if subbed:
            summary["reason"] = ("the footage has its own subtitles across "
                                 "the frame — shown whole, not cropped")
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
        if layout in ("wide", "closeup"):
            boxes = face_and_content(an)
            if boxes is not None:
                out = work / "shotplan.mp4"
                rendered = _render_face_content(video, boxes, out)
                if rendered is not None:
                    why = (f"face on the {boxes['side']} beside what it is "
                           "showing — that on top, the face below")
                    summary.update(layout="face_content", reason=why,
                                   shots=[{"mode": "face_content",
                                           "reason": why}],
                                   face_bands=[[0.5, 1.0]])
                    return rendered, summary
        # EVERY CAMERA GETS ITS OWN FRAMING when one crop would cut a
        # shot's face off; otherwise the one-crop plans below, unchanged
        same = analyze_on is None or abs(
            _probe_wh_dur(video)[2] - float(an.get("dur") or 0)) <= 0.25
        looked = framed(an, video, work, title) if same and layout in (
            "closeup", "two_shot", "wide") else None
        cams = looked or (cameras(an, layout, subs, reason) if same
                          else None)
        if cams:
            rendered = _render_cameras(video, cams, an, work / "shotplan.mp4")
            if rendered is not None:
                why = (f"{len(cams)} camera shot(s), each framed by a look "
                       "at it" if looked else
                       f"{len(cams)} camera shots, each framed on its own — "
                       f"one crop ({layout}) cut a face off")
                summary.update(
                    layout="cameras", reason=why,
                    shots=[{"mode": "camera", "t0": round(c["t0"], 2),
                            "t1": round(c["t1"], 2), "reason": c["why"],
                            "crop": list(c["crop"]) if c["crop"] else None}
                           for c in cams],
                    face_bands=_camera_bands(cams, an))
                return rendered, summary
        if layout == "wide":
            # NO TRACKABLE FACE IS NOT A REASON TO GIVE UP ON FRAMING.
            # This returned None, and the caller then blur-filled the whole
            # 16:9 frame into 9:16 — a 31.6% sharp band. Point the camera at
            # the motion instead; the footage fills three quarters of the
            # canvas and the clip stops looking like a repost.
            win = action_window(an)
            if win is not None:
                shot = Shot(mode="action", reason=reason + " — cropped to "
                            "the motion instead of shrinking the whole frame",
                            subjects=[], crop=win)
                out = work / "shotplan.mp4"
                rendered = _render_action_crop(video, shot, out)
                if rendered is not None:
                    summary.update(layout="action",
                                   reason=shot.reason,
                                   shots=[{"mode": "action",
                                           "reason": shot.reason}],
                                   crop=list(win))
                    return rendered, summary
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
