"""EMPTY: the set reads flat and bare (the lightning rough cut, 2026-11-20: the ridge "a flat lawn with cutout pines",
the tower "a lit cabin", the beach "an empty plane" where the glass looked like foam). The judge says it after a proof
round; this says it from the frames shots.py just rendered, before any judge sees them.

What is measured: the frame at phone size (W px wide, the size a Short is seen at), split into B x B blocks; a block
is SMOOTH when its mean luminance gradient (|dx| + |dy|, 0-255 levels) is under T. Data himself is masked out (his
projected box, a margin round it): his face and coat are smooth on purpose. The share of what is left that is ONE
connected smooth region is the set's emptiness; its MEDIAN over the rendered frames must be at most EMPTY_MAX.

Calibration (W 180, B 6, T 4; median over each proof's frames, Data masked):
  approved   checkout store (caaleb: "exactly how I want it")   0.08 unmasked (no animation dump to mask it by; the
                                                                 trail's masked figure is 0.03 above its unmasked)
  passed     trail, lightning beat 3 (judge 72)                  0.11
  failed     tower (56: "a lit cabin")                           0.31
             ridge, round-3 rewrite (50: "a flat lawn")          0.33
             beach rewrite (44: "an empty plane")                0.41
             beach (52)                                          0.49
             truck (60; the judge did not call its set bare)     0.12
EMPTY_MAX 0.22 is twice the trail and under every set the judge called bare. At T 3 and T 5 the order holds (trail
0.10 / 0.18, the least failing 0.25 / 0.33), so the threshold is not sitting on a knife edge.

Pure numpy + PIL: it runs where the proof renders (the CI proof job installs numpy and pillow), no bpy."""
import numpy as np
from PIL import Image

W, B, T = 180, 6, 4.0
EMPTY_MAX = 0.22
MARGIN = 0.12          # of his height: the mask round Data's projected box


def blocks(path, w=W, b=B, t=T):
    """(smooth mask of blocks, (rows, cols)) for one frame"""
    im = Image.open(path).convert("L"); h = max(b, int(round(im.height * w / im.width)))
    a = np.asarray(im.resize((w, h), Image.BILINEAR), dtype=np.float32)
    g = np.abs(np.diff(a, axis=1))[:-1, :] + np.abs(np.diff(a, axis=0))[:, :-1]
    nb = (g.shape[0] // b, g.shape[1] // b)
    blk = g[:nb[0] * b, :nb[1] * b].reshape(nb[0], b, nb[1], b).mean(axis=(1, 3))
    return blk < t, nb


def largest(mask):
    """the size (in blocks) of the largest 4-connected True region"""
    seen = np.zeros(mask.shape, bool); best = 0; R, C = mask.shape
    for i in range(R):
        for j in range(C):
            if mask[i, j] and not seen[i, j]:
                st = [(i, j)]; seen[i, j] = True; n = 0
                while st:
                    y, x = st.pop(); n += 1
                    for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= yy < R and 0 <= xx < C and mask[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True; st.append((yy, xx))
                best = max(best, n)
    return best


def emptiness(path, box=None):
    """the share of the frame (Data masked out) that is one smooth region. box: Data's projected (x0, x1, y0, y1) in
    0..1 of the frame, y up (bpy's world_to_camera_view), or None"""
    sm, nb = blocks(path)
    keep = np.ones(nb, bool)
    if box:
        x0, x1, y0, y1 = box; m = MARGIN * (y1 - y0)
        ys = 1 - (np.arange(nb[0]) + 0.5) / nb[0]; xs = (np.arange(nb[1]) + 0.5) / nb[1]
        keep = ~((ys[:, None] >= y0 - m) & (ys[:, None] <= y1 + m * 1.5) & (xs[None, :] >= x0 - m) & (xs[None, :] <= x1 + m))
    return largest(sm & keep) / max(1, int(keep.sum()))


def check(frames, name="shot"):
    """frames: [(png path, Data's box or None)]. Prints the EMPTY line; True when the set is not bare"""
    v = sorted(emptiness(p, b) for p, b in frames)
    if not v:
        print(f"EMPTY {name}: no frames rendered to measure -> OK", flush=True); return True
    med = v[len(v) // 2]; ok = med <= EMPTY_MAX
    print(f"EMPTY {name}: one smooth, bare region is {med:.0%} of the set behind him (median of {len(v)} frames, worst {v[-1]:.0%}; "
          f"max {EMPTY_MAX:.0%}) -> {'OK' if ok else 'FAIL: the set reads flat and bare; dress the ground and the background with detail'}",
          flush=True)
    return ok
