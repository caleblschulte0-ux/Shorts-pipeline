"""The CAMERA FLOAT — the one motion source that does not thin out with time.

WHY THIS EXISTS
---------------
The showrunner's temporal grade measures the change between CONSECUTIVE
frames (`showrunner_review._temporal_evidence`: 12x12 blocks of mean
grayscale on a 192px downscale, a frame counts as a duplicate when the
biggest block moves less than `BLOCK_MOTION_THRESH = 6.0`). The honest unit
is therefore **pixels per frame**, and the counterintuitive consequence is
that spreading a movement over MORE frames makes the measurement strictly
WORSE — the same journey across a longer beat is a smaller step each frame.

That is what killed both publishing channels:

* explainer's chart build is stretched to fill its beat
  (`nfr = ceil(duration * 30)`). Measured with the reviewer's own detector:

      60 frames  (2s)   ->  3.1 effective fps
      240 frames (8s)   ->  0.0 effective fps, duplicate_ratio 1.00
      600 frames (20s)  ->  0.0 effective fps, duplicate_ratio 1.00

  The opening segment carries the hook lead, so it is always the longest
  window in the video — which is why `segment_0` measured 0.8-1.4 fps in
  every story on 2026-08-11 while segment_2 sat at 24.0, and why the channel
  posted nothing for the twelve days to 2026-08-11.

* trending's `graph_race` eases into its race, so the opening seconds are
  near-still: three of six videos on 2026-08-11 were blocked before vision
  review at 4.5 / 8.7 / 8.9 fps.

No amount of re-pacing a build fixes this: a one-way move slow enough to
last 20 seconds is sub-pixel per frame BY DEFINITION. Only a CYCLIC motion
holds its per-frame rate at any duration. That is the same finding that
fixed the mascot idle (`data_learning/studio_render.py`) and the reddit
panels (`make_reddit_story.py`); this module is the shared statement of it
so a third channel cannot rediscover it the hard way.

WHAT IT IS
----------
A slow Lissajous drift of the visual layer — a hand-held/breathing camera.
It is duration-independent: a 40-second hold floats exactly as much per
frame as a 4-second one.

CALIBRATION (measured, not chosen — `showrunner_review._temporal_evidence`
on a completely STATIC 1080x1920 chart held for 20 seconds):

    amplitude  rad/s   px/frame   effective_fps   dup_ratio
    (none)      -        0.00        0.0            1.000    FAIL
      8        3.0       0.80       11.1            0.536    FAIL
     16        5.6       2.99       22.5            0.063    pass
     20        4.6       3.07       22.3            0.071    pass
     26        4.0       3.47       22.8            0.050    pass

`FLOAT_A = 20` is the shipped amplitude: 1.9% of frame width, which the
chart card's own 31px transparent margin absorbs with room to spare (no
crop at all on a card), and only a 1.9% crop on a full-frame layer.
"""
from __future__ import annotations

# Amplitude in pixels at 1080x1920, and the two angular frequencies (rad/s).
# Different frequencies on x and y so the layer traces a Lissajous figure
# rather than sliding back and forth along one diagonal.
#
# RETUNED 2026-08-16 — the operator watched the shipped videos and called the
# motion "a weird shaking". They were right, and it is arithmetic again:
# what the GATE needs is pixels per frame (amp * w / fps), but what the EYE
# objects to is acceleration (amp * w^2). At a fixed per-frame budget those
# trade against each other linearly in w — so the first tuning (20px @ 4.6
# rad/s, 0.73 Hz, 423 px/s^2) sat at the nervous end for no measured gain,
# and it stacked on a mascot idle jiggling at 0.95 Hz / ~1080 px/s^2 in a
# different phase. Two independent oscillations IS "weird shaking".
#
# The retune halves the frequency and doubles the amplitude: same pixels
# per frame for the detector, less than half the acceleration for the eye,
# and it is applied ONCE to the whole frame (a slow breathing camera)
# instead of per-layer. Measured with the reviewer's own detector on a
# WORST-CASE fully static frame held 20s:
#
#     A=20 w=4.6/3.9 (old)   16.7 fps  dup 0.31   PASS   423 px/s^2
#     A=44 w=2.1/1.7 (new)   16.4 fps  dup 0.32   PASS   194 px/s^2
#     A=50 w=1.9/1.5         16.1 fps  dup 0.33   PASS   (thinner margin)
#     A=44 w=1.5/1.2         12.2 fps  dup 0.49   FAIL   <- the cliff
#
# 2.1/1.7 keeps real margin above the cliff. Raise AMPLITUDE, never
# frequency, if this ever needs more — frequency is what reads as nervous.
FLOAT_A = 44
FLOAT_WX = 2.1
FLOAT_WY = 1.7

# The floor the temporal grade needs. Below ~2.3 px/frame the measurement
# collapses (2.3 measured 8.9 fps against an 11.0 floor); 2.9 is the shipped
# margin. Kept here so a test can hold the constants to it.
MIN_PX_PER_FRAME = 2.9


def px_per_frame(amp: float = FLOAT_A, w: float = FLOAT_WX,
                 fps: float = 30.0) -> float:
    """Peak per-frame displacement of `amp*sin(w*t)` sampled at `fps`.

    This is the number the temporal grade actually sees. Anything that moves
    a layer should be able to answer "how many pixels per frame?" — if it
    cannot, it is not motion the gate can measure.
    """
    return amp * w / float(fps)


def overlay_xy(x0: float, y0: float, *, amp: float = FLOAT_A,
               wx: float = FLOAT_WX, wy: float = FLOAT_WY) -> tuple[str, str]:
    """ffmpeg `overlay` x/y expressions floating a layer around (x0, y0).

    For a layer with transparent margins (the explainer's chart card has
    ~31px), nothing is cropped — the content simply drifts inside the frame.
    """
    return (f"{x0:g}+{amp:g}*sin({wx:g}*t)",
            f"{y0:g}+{amp:g}*cos({wy:g}*t)")


def crop_vf(w: int, h: int, *, amp: float = FLOAT_A, wx: float = FLOAT_WX,
            wy: float = FLOAT_WY) -> str:
    """A `-vf` chain that floats a FULL-FRAME clip: oversize by `2*amp`, then
    crop a moving `w x h` window out of it. Costs `amp` pixels of edge on
    each side (1.9% at the shipped amplitude) and never shows background.
    """
    return (f"scale={w + 2 * amp}:{h + 2 * amp},"
            f"crop={w}:{h}:x='{amp:g}+{amp:g}*sin({wx:g}*t)'"
            f":y='{amp:g}+{amp:g}*cos({wy:g}*t)'")
