#!/usr/bin/env python3
"""Generate the 6 Bigfoot-anchor mascot poses.

Character: "Squatch the News Guy" — sasquatch in a navy suit + red tie.
Big rounded fuzzy silhouette, oversized expressive face. The whole point
is the comic juxtaposition: a cryptid reading the news at a desk.

Procedural / PIL because we want repeatability + zero asset license
risk. Bigfoot is forgiving for procedural art — no realistic anatomy
required; the silhouette IS the joke.

Style notes that matter for legibility at the 260×260 final size:
  * Bold outlines (4-8 px on the 520 canvas)
  * High-contrast features (white sclera + black pupils, never gray)
  * Big eyes, big mouth, small body — chibi proportions for cuteness
  * Fur texture via short tuft strokes around the silhouette edge
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "mascot" / "anchor"

SIZE = 520

# Palette — kept narrow on purpose so the character reads as ONE shape.
FUR = (118, 78, 48, 255)
FUR_SHADOW = (78, 50, 28, 255)
FUR_HIGHLIGHT = (148, 100, 68, 255)
OUTLINE = (28, 18, 10, 255)
SUIT = (36, 52, 96, 255)
SUIT_SHADOW = (22, 34, 64, 255)
SHIRT = (248, 245, 236, 255)
TIE = (185, 40, 36, 255)
TIE_HIGHLIGHT = (218, 62, 52, 255)
EYE_WHITE = (255, 252, 245, 255)
EYE_DARK = (22, 18, 18, 255)
MOUTH_DARK = (58, 30, 24, 255)
TOOTH = (252, 248, 235, 255)


# ---------- low-level shape helpers ----------

def _ellipse(d, x1, y1, x2, y2, fill, outline=None, width=4):
    d.ellipse([x1, y1, x2, y2], fill=fill, outline=outline, width=width)


def _polygon(d, pts, fill, outline=None, width=4):
    d.polygon([(int(x), int(y)) for x, y in pts],
              fill=fill, outline=outline, width=width)


def _line(d, p1, p2, fill, width):
    d.line([(int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))],
           fill=fill, width=width)


def _fuzz_edge(d, points, color=OUTLINE, density=42, length=14, seed=0):
    """Draw short tuft strokes outward from the perimeter of a polygon
    to suggest fur. Tufts are deterministic per pose via the seed."""
    rng = random.Random(seed)
    n = len(points)
    for _ in range(density):
        # Pick a random edge segment
        i = rng.randint(0, n - 1)
        a = points[i]
        b = points[(i + 1) % n]
        # A random spot along the edge
        t = rng.random()
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        # Outward normal (rotate edge tangent by 90°)
        ex, ey = b[0] - a[0], b[1] - a[1]
        elen = max(1.0, math.hypot(ex, ey))
        # Normal points "outward" — we use the right-hand normal which
        # ends up outside the polygon for the clockwise vertex order
        # we use throughout this file.
        nx, ny = ey / elen, -ex / elen
        tip = (px + nx * length, py + ny * length)
        # Slight curve by jittering the tip
        tip = (tip[0] + rng.uniform(-3, 3), tip[1] + rng.uniform(-3, 3))
        _line(d, (px, py), tip, color, 3)


# ---------- body parts ----------

def _draw_body(d, *, pointing_right: bool = False, chin_hand: bool = False) -> None:
    """Big fuzzy torso + arms. Suit lapels + shirt + tie sit ON TOP of
    the fur so the character reads as 'sasquatch wearing a suit'."""
    s = SIZE

    # Main torso pear shape — slightly wider at hips than shoulders
    body_pts = [
        (s * 0.18, s * 0.62),   # left shoulder top
        (s * 0.10, s * 0.74),   # outer shoulder
        (s * 0.06, s * 0.88),   # ribs
        (s * 0.14, s * 1.00),   # bottom-left (off-canvas to lock)
        (s * 0.86, s * 1.00),   # bottom-right
        (s * 0.94, s * 0.88),   # ribs
        (s * 0.90, s * 0.74),   # outer shoulder
        (s * 0.82, s * 0.62),   # right shoulder top
    ]
    _polygon(d, body_pts, FUR, OUTLINE, 5)
    _fuzz_edge(d, body_pts, OUTLINE, density=50, length=12, seed=1)

    # LEFT arm — always at side
    left_arm = [
        (s * 0.06, s * 0.80),
        (s * 0.00, s * 0.84),
        (s * 0.02, s * 0.98),
        (s * 0.14, s * 0.96),
    ]
    _polygon(d, left_arm, FUR, OUTLINE, 4)
    _fuzz_edge(d, left_arm, OUTLINE, density=18, length=10, seed=2)

    if pointing_right:
        # Right arm raised, pointing diagonally up + out
        right_arm = [
            (s * 0.78, s * 0.66),    # shoulder
            (s * 0.96, s * 0.50),    # elbow
            (s * 1.06, s * 0.40),    # forearm out
            (s * 1.02, s * 0.32),    # hand top
            (s * 0.92, s * 0.42),    # hand bottom
            (s * 0.84, s * 0.60),    # back to shoulder
        ]
        _polygon(d, right_arm, FUR, OUTLINE, 4)
        _fuzz_edge(d, right_arm, OUTLINE, density=22, length=10, seed=3)
        # Index finger as a small extension past the hand
        _ellipse(d, s * 0.96, s * 0.30, s * 1.08, s * 0.40,
                 FUR, OUTLINE, 4)
    elif chin_hand:
        # Right arm bent UP so the hand rests under the chin
        right_arm = [
            (s * 0.78, s * 0.66),
            (s * 0.92, s * 0.74),
            (s * 0.86, s * 0.84),
            (s * 0.66, s * 0.62),
            (s * 0.56, s * 0.52),
            (s * 0.66, s * 0.46),
            (s * 0.84, s * 0.60),
        ]
        _polygon(d, right_arm, FUR, OUTLINE, 4)
        _fuzz_edge(d, right_arm, OUTLINE, density=18, length=8, seed=4)
        # The "hand" under chin
        _ellipse(d, s * 0.50, s * 0.46, s * 0.66, s * 0.58,
                 FUR, OUTLINE, 4)
    else:
        # Right arm matches left — relaxed at side
        right_arm = [
            (s * 0.94, s * 0.80),
            (s * 1.00, s * 0.84),
            (s * 0.98, s * 0.98),
            (s * 0.86, s * 0.96),
        ]
        _polygon(d, right_arm, FUR, OUTLINE, 4)
        _fuzz_edge(d, right_arm, OUTLINE, density=18, length=10, seed=2)

    # SUIT JACKET — covers the front of the torso, leaves arms furry
    jacket_pts = [
        (s * 0.20, s * 0.66),    # left lapel top
        (s * 0.16, s * 0.84),
        (s * 0.20, s * 1.00),
        (s * 0.80, s * 1.00),
        (s * 0.84, s * 0.84),
        (s * 0.80, s * 0.66),    # right lapel top
        (s * 0.58, s * 0.74),    # right lapel inner V
        (s * 0.50, s * 0.92),    # tie bottom anchor
        (s * 0.42, s * 0.74),    # left lapel inner V
    ]
    _polygon(d, jacket_pts, SUIT, OUTLINE, 4)
    # Inner suit shadow (creates a fold line down the center)
    _line(d, (s * 0.50, s * 0.92), (s * 0.50, s * 1.00),
          SUIT_SHADOW, 4)

    # Shirt — visible V between the lapels
    shirt_pts = [
        (s * 0.42, s * 0.66),
        (s * 0.58, s * 0.66),
        (s * 0.50, s * 0.86),
    ]
    _polygon(d, shirt_pts, SHIRT, OUTLINE, 3)

    # Tie knot (small triangle at the V)
    knot = [
        (s * 0.46, s * 0.68),
        (s * 0.54, s * 0.68),
        (s * 0.50, s * 0.74),
    ]
    _polygon(d, knot, TIE, OUTLINE, 2)
    # Tie body (trapezoidal, hangs from knot)
    tie_pts = [
        (s * 0.47, s * 0.74),
        (s * 0.53, s * 0.74),
        (s * 0.56, s * 0.92),
        (s * 0.44, s * 0.92),
    ]
    _polygon(d, tie_pts, TIE, OUTLINE, 2)
    # Tie highlight stripe
    _line(d, (s * 0.49, s * 0.76), (s * 0.51, s * 0.90),
          TIE_HIGHLIGHT, 4)


def _draw_head(d) -> None:
    """Big fuzzy head with brow ridge, ears, slight chin. Always
    drawn the same — the pose-specific stuff goes on top."""
    s = SIZE

    # Head silhouette — pear-ish, wider at top than chin
    head_pts = [
        (s * 0.26, s * 0.18),    # top-left
        (s * 0.22, s * 0.34),    # left temple
        (s * 0.26, s * 0.52),    # left jaw
        (s * 0.36, s * 0.62),    # left chin
        (s * 0.64, s * 0.62),    # right chin
        (s * 0.74, s * 0.52),    # right jaw
        (s * 0.78, s * 0.34),    # right temple
        (s * 0.74, s * 0.18),    # top-right
        (s * 0.62, s * 0.10),    # crown right
        (s * 0.50, s * 0.06),    # crown top
        (s * 0.38, s * 0.10),    # crown left
    ]
    _polygon(d, head_pts, FUR, OUTLINE, 5)
    _fuzz_edge(d, head_pts, OUTLINE, density=70, length=14, seed=7)

    # Hairy crown tufts (3 explicit peaks for "shaggy" feel)
    for cx in (0.36, 0.50, 0.64):
        _polygon(d, [
            (s * (cx - 0.04), s * 0.10),
            (s * cx, s * 0.02),
            (s * (cx + 0.04), s * 0.10),
        ], FUR, OUTLINE, 3)

    # Brow ridge — thick darker fur band across the upper face,
    # gives Bigfoot his unmistakable heavy-browed look
    brow_band = [
        (s * 0.24, s * 0.30),
        (s * 0.76, s * 0.30),
        (s * 0.74, s * 0.40),
        (s * 0.26, s * 0.40),
    ]
    _polygon(d, brow_band, FUR_SHADOW, OUTLINE, 3)

    # Face lighter patch (the "skin" area between brow and chin)
    face_patch = [
        (s * 0.30, s * 0.40),
        (s * 0.70, s * 0.40),
        (s * 0.66, s * 0.56),
        (s * 0.50, s * 0.60),
        (s * 0.34, s * 0.56),
    ]
    _polygon(d, face_patch, FUR_HIGHLIGHT, None, 0)

    # Nose — small dark patch under brow
    nose_pts = [
        (s * 0.46, s * 0.44),
        (s * 0.54, s * 0.44),
        (s * 0.52, s * 0.50),
        (s * 0.48, s * 0.50),
    ]
    _polygon(d, nose_pts, FUR_SHADOW, OUTLINE, 2)


# ---------- pose-specific features ----------

def _draw_eyes(d, *, wide=False, closed=False, looking_up=False,
               half_closed=False) -> None:
    """Eyes sit just below the brow band. Big and expressive at
    280-pix face."""
    s = SIZE
    cy = s * 0.36
    centers = [(s * 0.38, cy), (s * 0.62, cy)]

    if closed:
        # Closed-eye arc ^_^
        for cx, _ in centers:
            d.arc([
                int(cx - s * 0.05), int(cy - s * 0.025),
                int(cx + s * 0.05), int(cy + s * 0.025),
            ], 200, 340, fill=EYE_DARK, width=6)
        return

    # White sclera
    eye_w = s * 0.07 if wide else s * 0.055
    eye_h = s * 0.07 if wide else s * 0.055
    if half_closed:
        eye_h = s * 0.025
    for cx, _ in centers:
        d.ellipse([
            int(cx - eye_w), int(cy - eye_h),
            int(cx + eye_w), int(cy + eye_h),
        ], fill=EYE_WHITE, outline=OUTLINE, width=3)

    # Pupils
    pr = s * 0.025 if wide else s * 0.03
    pupil_y = cy + (s * -0.020 if looking_up else 0)
    if half_closed:
        pr = s * 0.018
    for cx, _ in centers:
        d.ellipse([
            int(cx - pr), int(pupil_y - pr),
            int(cx + pr), int(pupil_y + pr),
        ], fill=EYE_DARK)
        # Small white catch-light for life
        d.ellipse([
            int(cx + pr * 0.2), int(pupil_y - pr * 0.6),
            int(cx + pr * 0.6), int(pupil_y - pr * 0.2),
        ], fill=EYE_WHITE)


def _draw_brow_features(d, *, raised=False, furrowed=False,
                        asymmetric=False) -> None:
    """Extra brow strokes ON TOP of the brow ridge — these are what
    actually telegraph emotion since the ridge itself is constant."""
    s = SIZE
    y = s * 0.32
    if raised:
        # Both brows arched high
        d.arc([int(s*0.30), int(s*0.22), int(s*0.46), int(s*0.34)],
              180, 360, fill=OUTLINE, width=8)
        d.arc([int(s*0.54), int(s*0.22), int(s*0.70), int(s*0.34)],
              180, 360, fill=OUTLINE, width=8)
    elif furrowed:
        # Brows angle inward + down (anger / doubt)
        d.line([(int(s*0.30), int(s*0.30)), (int(s*0.46), int(s*0.36))],
               fill=OUTLINE, width=8)
        d.line([(int(s*0.54), int(s*0.36)), (int(s*0.70), int(s*0.30))],
               fill=OUTLINE, width=8)
    elif asymmetric:
        # Left flat, right arched (the thinking cocked brow)
        d.line([(int(s*0.30), int(s*0.34)), (int(s*0.46), int(s*0.34))],
               fill=OUTLINE, width=8)
        d.arc([int(s*0.54), int(s*0.20), int(s*0.70), int(s*0.32)],
              180, 360, fill=OUTLINE, width=8)
    else:
        # Default — gentle level lines
        d.line([(int(s*0.32), int(s*0.32)), (int(s*0.44), int(s*0.32))],
               fill=OUTLINE, width=7)
        d.line([(int(s*0.56), int(s*0.32)), (int(s*0.68), int(s*0.32))],
               fill=OUTLINE, width=7)


def _draw_mouth(d, *, pose: str) -> None:
    s = SIZE
    cx, cy = s * 0.50, s * 0.55
    if pose == "shock":
        # Big round O
        d.ellipse([int(cx - s*0.06), int(cy - s*0.05),
                   int(cx + s*0.06), int(cy + s*0.07)],
                  fill=MOUTH_DARK, outline=OUTLINE, width=4)
    elif pose == "laugh":
        # Wide open grin showing teeth
        d.chord([int(cx - s*0.11), int(cy - s*0.04),
                 int(cx + s*0.11), int(cy + s*0.10)],
                0, 180, fill=MOUTH_DARK, outline=OUTLINE, width=4)
        # Tooth row
        d.rectangle([int(cx - s*0.08), int(cy + s*0.005),
                     int(cx + s*0.08), int(cy + s*0.03)],
                    fill=TOOTH)
        # Tooth dividers
        for tx in (cx - s*0.04, cx, cx + s*0.04):
            d.line([(int(tx), int(cy + s*0.005)),
                    (int(tx), int(cy + s*0.03))],
                   fill=OUTLINE, width=2)
    elif pose == "point":
        # Slight smile — confident
        d.arc([int(cx - s*0.07), int(cy - s*0.02),
               int(cx + s*0.07), int(cy + s*0.05)],
              20, 160, fill=OUTLINE, width=6)
    elif pose == "think":
        # Pursed lip
        d.line([(int(cx - s*0.04), int(cy + s*0.02)),
                (int(cx + s*0.04), int(cy + s*0.02))],
               fill=OUTLINE, width=7)
        d.line([(int(cx + s*0.03), int(cy + s*0.02)),
                (int(cx + s*0.06), int(cy - s*0.01))],
               fill=OUTLINE, width=7)
    elif pose == "dismiss":
        # Smirk — left flat, right corner up
        d.line([(int(cx - s*0.07), int(cy + s*0.025)),
                (int(cx + s*0.03), int(cy + s*0.025))],
               fill=OUTLINE, width=7)
        d.line([(int(cx + s*0.02), int(cy + s*0.025)),
                (int(cx + s*0.07), int(cy - s*0.015))],
               fill=OUTLINE, width=7)
    else:  # idle
        d.arc([int(cx - s*0.06), int(cy - s*0.01),
               int(cx + s*0.06), int(cy + s*0.04)],
              20, 160, fill=OUTLINE, width=6)


# ---------- top-level ----------

def draw_pose(pose: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if pose == "point":
        _draw_body(d, pointing_right=True)
    elif pose == "think":
        _draw_body(d, chin_hand=True)
    else:
        _draw_body(d)

    _draw_head(d)

    if pose == "idle":
        _draw_brow_features(d)
        _draw_eyes(d)
    elif pose == "shock":
        _draw_brow_features(d, raised=True)
        _draw_eyes(d, wide=True)
    elif pose == "point":
        _draw_brow_features(d)
        _draw_eyes(d)
    elif pose == "laugh":
        _draw_brow_features(d, raised=True)
        _draw_eyes(d, closed=True)
    elif pose == "think":
        _draw_brow_features(d, asymmetric=True)
        _draw_eyes(d, looking_up=True)
    elif pose == "dismiss":
        _draw_brow_features(d, furrowed=True)
        _draw_eyes(d, half_closed=True)
    else:
        raise ValueError(f"unknown pose: {pose}")

    _draw_mouth(d, pose=pose)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for pose in ("idle", "shock", "point", "laugh", "think", "dismiss"):
        img = draw_pose(pose)
        path = OUT_DIR / f"{pose}.png"
        img.save(path, "PNG")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
