"""Bigfoot mascot — procedural cartoon news anchor for baller_bro_2.0.

Chest-up bust framing (no limbs) so the character reads as a polished
on-screen anchor instead of a stick-figure wobbling in the corner. Big
expressive head with real facial detail, navy suit collar + red tie
visible. Drawn purely from code (PIL), deterministic — looks identical
every render, no image-model drift.

Animation: subtle head bob + slow head-tilt sway + periodic blink +
occasional ear twitch. No flailing arms (there are none to flail).

:func:`build_bigfoot_loop` renders the loop to a .mov with an alpha
channel (qtrle) the explainer renderer overlays via ``-stream_loop``.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Palette — warm browns for fur, navy/red for the anchor outfit.
# Solid fills only so the silhouette holds up when scaled down over
# busy B-roll.
FUR = (138, 96, 62, 255)
FUR_DK = (88, 58, 36, 255)
FUR_LT = (174, 128, 88, 255)
FUR_LL = (208, 162, 118, 255)
SUIT = (28, 48, 92, 255)
SUIT_DK = (18, 32, 64, 255)
SHIRT = (248, 245, 236, 255)
SHIRT_DK = (210, 208, 198, 255)
TIE = (182, 38, 32, 255)
TIE_LT = (220, 64, 54, 255)
TIE_DK = (132, 22, 18, 255)
WHITE = (250, 252, 252, 255)
DARK = (16, 14, 12, 255)
NOSE = (38, 24, 16, 255)
SS = 3                            # supersample for smooth edges


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _draw(size: int, bob: float, blink: float, head_tilt: float,
          ear_twitch: float) -> Image.Image:
    """One chest-up Bigfoot anchor frame.

    bob: px (head + body translate together).
    blink: 0..1, >0.6 = closed.
    head_tilt: degrees, small sway around the neck.
    ear_twitch: 0..1, scales ears briefly.
    """
    S = size * SS
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Body + suit first, on the base canvas (not tilted with the head).
    bd = ImageDraw.Draw(base)
    cx = S // 2
    oy = int(bob * SS)

    # ---------- Shoulders + suit jacket ----------
    shoulder_y = int(S * 0.70) + oy
    shoulder_w = int(S * 0.88)
    jacket_pts = [
        (cx - shoulder_w // 2, shoulder_y),       # left shoulder
        (cx - int(shoulder_w * 0.58), S),         # left side off-canvas
        (cx + int(shoulder_w * 0.58), S),         # right side off-canvas
        (cx + shoulder_w // 2, shoulder_y),       # right shoulder
        (cx + int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),  # collar pt R
        (cx, shoulder_y + int(S * 0.22)),         # tie point at top
        (cx - int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),  # collar pt L
    ]
    bd.polygon(jacket_pts, fill=SUIT)

    # Lapel inner edges — slightly darker shadow line
    bd.line([(cx - int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),
             (cx - int(shoulder_w * 0.30), S - int(S * 0.02))],
            fill=SUIT_DK, width=max(3, S // 200))
    bd.line([(cx + int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),
             (cx + int(shoulder_w * 0.30), S - int(S * 0.02))],
            fill=SUIT_DK, width=max(3, S // 200))

    # White shirt V-collar
    bd.polygon([
        (cx - int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),
        (cx + int(shoulder_w * 0.10), shoulder_y + int(S * 0.06)),
        (cx, shoulder_y + int(S * 0.22)),
    ], fill=SHIRT)

    # Red tie (knot + body w/ highlight + shadow)
    knot_w = int(S * 0.055)
    knot_y0 = shoulder_y + int(S * 0.16)
    bd.polygon([
        (cx - knot_w, knot_y0),
        (cx + knot_w, knot_y0),
        (cx + int(knot_w * 0.6), knot_y0 + int(S * 0.06)),
        (cx - int(knot_w * 0.6), knot_y0 + int(S * 0.06)),
    ], fill=TIE)
    # tie body
    tie_top_w = int(S * 0.038)
    tie_bot_w = int(S * 0.075)
    tie_top_y = knot_y0 + int(S * 0.06)
    bd.polygon([
        (cx - tie_top_w, tie_top_y),
        (cx + tie_top_w, tie_top_y),
        (cx + tie_bot_w, S),
        (cx - tie_bot_w, S),
    ], fill=TIE)
    # highlight + shadow stripes on the tie
    bd.line([(cx - int(tie_top_w * 0.4), tie_top_y + int(S * 0.01)),
             (cx - int(tie_bot_w * 0.35), S)],
            fill=TIE_LT, width=max(2, S // 360))
    bd.line([(cx + int(tie_top_w * 0.5), tie_top_y + int(S * 0.01)),
             (cx + int(tie_bot_w * 0.45), S)],
            fill=TIE_DK, width=max(2, S // 360))

    # Neck (a stub of fur between collar and head)
    neck_y0 = shoulder_y - int(S * 0.04)
    neck_w = int(S * 0.16)
    bd.rounded_rectangle(
        [cx - neck_w // 2, neck_y0 - int(S * 0.05),
         cx + neck_w // 2, shoulder_y + int(S * 0.03)],
        radius=int(neck_w * 0.3), fill=FUR_DK)

    # ---------- Head — drawn into its own layer so we can rotate it ----------
    head_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head_layer)

    head_cx = cx
    head_cy = int(S * 0.40) + oy
    head_r = int(S * 0.28)            # big head fills most of the canvas

    # Fur tufts sticking up (5 little peaks for a wilder Bigfoot mane)
    tuft_y_base = head_cy - int(head_r * 0.90)
    for i, offset in enumerate((-0.85, -0.45, 0.0, 0.45, 0.85)):
        bx = head_cx + int(head_r * offset)
        ty = head_cy - int(head_r * (1.20 + 0.18 * (1 - abs(offset))))
        tw_ = int(head_r * 0.22)
        hd.polygon([
            (bx - tw_ // 2, tuft_y_base),
            (bx + tw_ // 2, tuft_y_base),
            (bx + int(tw_ * 0.15 * (1 if i % 2 else -1)), ty),
        ], fill=FUR_DK)

    # Head silhouette — slightly egg-shaped (wider at top of crown)
    crown_top = head_cy - int(head_r * 1.05)
    jaw_bot = head_cy + int(head_r * 1.15)
    crown_w = int(head_r * 2.20)
    jaw_w = int(head_r * 1.85)
    head_pts = [
        (head_cx - crown_w // 2, head_cy - int(head_r * 0.35)),
        (head_cx - int(crown_w * 0.42), crown_top),
        (head_cx + int(crown_w * 0.42), crown_top),
        (head_cx + crown_w // 2, head_cy - int(head_r * 0.35)),
        (head_cx + int(crown_w * 0.48), head_cy + int(head_r * 0.55)),
        (head_cx + jaw_w // 2, jaw_bot - int(head_r * 0.25)),
        (head_cx + int(jaw_w * 0.30), jaw_bot),
        (head_cx - int(jaw_w * 0.30), jaw_bot),
        (head_cx - jaw_w // 2, jaw_bot - int(head_r * 0.25)),
        (head_cx - int(crown_w * 0.48), head_cy + int(head_r * 0.55)),
    ]
    hd.polygon(head_pts, fill=FUR)

    # Side fur fringe (slightly darker patches near the cheeks)
    for sgn in (-1, 1):
        cheek_x = head_cx + sgn * int(head_r * 0.95)
        cheek_y = head_cy + int(head_r * 0.30)
        hd.ellipse([cheek_x - int(head_r * 0.35),
                    cheek_y - int(head_r * 0.30),
                    cheek_x + int(head_r * 0.35),
                    cheek_y + int(head_r * 0.45)], fill=FUR_DK)

    # Re-paint main face oval on top of the cheek shadow patches
    # so the front of the face is the lighter fur tone.
    face_oval = [
        head_cx - int(head_r * 0.78), head_cy - int(head_r * 0.10),
        head_cx + int(head_r * 0.78), head_cy + int(head_r * 1.00),
    ]
    hd.ellipse(face_oval, fill=FUR_LT)

    # Muzzle — a lighter raised area around mouth + nose
    muzzle_pts = [
        head_cx - int(head_r * 0.42), head_cy + int(head_r * 0.18),
        head_cx + int(head_r * 0.42), head_cy + int(head_r * 0.18),
        head_cx + int(head_r * 0.50), head_cy + int(head_r * 0.92),
        head_cx - int(head_r * 0.50), head_cy + int(head_r * 0.92),
    ]
    hd.polygon([(muzzle_pts[i], muzzle_pts[i+1])
                for i in range(0, len(muzzle_pts), 2)], fill=FUR_LL)

    # Ears — pop out from behind the head (twitch scale)
    ear_scale = 1.0 + ear_twitch * 0.10
    for sgn in (-1, 1):
        ex = head_cx + sgn * int(head_r * 1.05)
        ey = head_cy - int(head_r * 0.05)
        er = int(head_r * 0.22 * ear_scale)
        hd.ellipse([ex - er, ey - er, ex + er, ey + er], fill=FUR_DK)
        hd.ellipse([ex - int(er * 0.55), ey - int(er * 0.55),
                    ex + int(er * 0.55), ey + int(er * 0.55)],
                   fill=NOSE)

    # ---------- Heavy brow ridge — defines the Bigfoot silhouette ----------
    brow_y = head_cy - int(head_r * 0.18)
    brow_w = int(head_r * 1.55)
    brow_h = int(head_r * 0.26)
    hd.rounded_rectangle(
        [head_cx - brow_w // 2, brow_y - brow_h // 2,
         head_cx + brow_w // 2, brow_y + brow_h // 2],
        radius=int(brow_h * 0.5), fill=FUR_DK)

    # ---------- Eyes ----------
    eye_dx = int(head_r * 0.42)
    eye_y = head_cy + int(head_r * 0.08)
    eye_r = int(head_r * 0.22)
    pup_r = int(head_r * 0.12)
    for sgn in (-1, 1):
        ex2 = head_cx + sgn * eye_dx
        if blink > 0.6:
            hd.arc([ex2 - eye_r, eye_y - eye_r, ex2 + eye_r, eye_y + eye_r],
                   start=200, end=340, fill=DARK, width=max(3, S // 110))
        else:
            _circle(hd, ex2, eye_y, eye_r, WHITE)
            _circle(hd, ex2, eye_y + int(eye_r * 0.10), pup_r, DARK)
            # catchlight
            _circle(hd, ex2 - pup_r // 2, eye_y - pup_r // 3,
                    max(2, int(pup_r * 0.38)), WHITE)

    # Eyebrows — focused anchor angle (inner lower than outer)
    bw = int(eye_r * 1.20)
    for sgn in (-1, 1):
        ex2 = head_cx + sgn * eye_dx
        by0 = eye_y - int(eye_r * 1.55)
        inner_y = by0 + int(eye_r * 0.38)
        outer_y = by0
        if sgn < 0:
            p_inner = (ex2 + bw // 2, inner_y)
            p_outer = (ex2 - bw // 2, outer_y)
        else:
            p_inner = (ex2 - bw // 2, inner_y)
            p_outer = (ex2 + bw // 2, outer_y)
        hd.line([p_outer, p_inner], fill=DARK, width=max(5, S // 90))

    # ---------- Nose ----------
    nose_top_y = head_cy + int(head_r * 0.45)
    nose_w = int(head_r * 0.16)
    hd.polygon([
        (head_cx - nose_w, nose_top_y),
        (head_cx + nose_w, nose_top_y),
        (head_cx + int(nose_w * 0.65), nose_top_y + int(head_r * 0.20)),
        (head_cx - int(nose_w * 0.65), nose_top_y + int(head_r * 0.20)),
    ], fill=NOSE)
    # nose highlight
    hd.line([(head_cx - int(nose_w * 0.4), nose_top_y + int(head_r * 0.04)),
             (head_cx + int(nose_w * 0.4), nose_top_y + int(head_r * 0.04))],
            fill=FUR_LL, width=max(2, S // 280))

    # ---------- Mouth — closed, slight smile, just a curved line ----------
    mw = int(head_r * 0.30)
    my = head_cy + int(head_r * 0.82)
    hd.arc([head_cx - mw, my - int(mw * 0.55),
            head_cx + mw, my + int(mw * 0.45)],
           start=18, end=162, fill=DARK, width=max(5, S // 85))

    # ---------- Rotate the head layer by head_tilt and composite ----------
    if abs(head_tilt) > 0.05:
        # Rotate around the head center, not the canvas center
        head_layer = head_layer.rotate(
            head_tilt, resample=Image.BICUBIC,
            center=(head_cx, head_cy))
    base.alpha_composite(head_layer)

    return base.resize((size, size), Image.LANCZOS)


def build_bigfoot_loop(out_path: Path, *, size: int = 540, fps: int = 30,
                       seconds: float = 4.0, flip: bool = False) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink + head
    tilt + ear twitch. ``flip`` mirrors the whole frame so he can stand
    on either side of the canvas."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            # gentle vertical bob (1 cycle per loop)
            bob = math.sin(t * 2 * math.pi) * (size * 0.018)
            # slow side-to-side head tilt (1 cycle per loop, ±2°)
            head_tilt = math.sin(t * 2 * math.pi) * 2.0
            # brief blink window
            blink = 1.0 if 0.78 <= t <= 0.82 else 0.0
            # ear twitch (sharp pulse twice per loop)
            tw = math.sin(t * 2 * math.pi * 4)
            ear_twitch = max(0.0, tw) ** 6
            im = _draw(size, bob, blink, head_tilt, ear_twitch)
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 540) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0, 0.0, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bigfoot.png")
    save_static(out)
    print("wrote", out)
