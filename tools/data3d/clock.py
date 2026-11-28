"""THE ONE CLOCK of the 3D shorts: the frame rate and how a story's narration windows cut into shots.

Every module (the rig, the acts, the props, the checks, the shot harness, the range renderer, the assembler and both
workflows) reads FPS from here, so a story renders at one rate end to end. 30 fps since the second 3D short
(2026-11-12 brief: "native 1080x1920 at 30 FPS, verified, not upscaled"); DATA3D_FPS overrides it.

A story with N narration windows has N shots. Shot k (1-based) runs from the start of window k (0 for the first shot,
so the hook owns the first frame) to the start of window k+1; the last shot runs TAIL_S past the last word, so the
voice never ends on the final frame."""
import os

FPS = int(os.environ.get("DATA3D_FPS", "30"))
TAIL_S = 0.6


def F(t):
    """the frame a time in seconds lands on (frames are 1-based)"""
    return int(round(t * FPS)) + 1


def span(windows, shot):
    """(T0, T1, G0, NF) for shot k of a story: its start and end in seconds, its global frame offset (local frame f is
    written as global G0 + f) and its frame count. Shots tile the whole video with no gap and no overlap."""
    n = len(windows)
    T0 = 0.0 if shot == 1 else windows[shot - 1][0]
    T1 = windows[shot][0] if shot < n else windows[-1][1] + TAIL_S
    G0 = int(round(T0 * FPS))
    NF = int(round(T1 * FPS)) - G0 + (1 if shot == n else 0)
    return T0, T1, G0, NF


def total(windows):
    """frames in the whole video"""
    return int(round((windows[-1][1] + TAIL_S) * FPS)) + 1
