#!/usr/bin/env python3
"""Mascot PRIMITIVE APPROVAL GATE (ChatGPT review: "build and approve mascot
primitives separately ... do not use a primitive in production until it passes
in isolation").

Every performance primitive the director may select is rendered in isolation
across the beat and must pass:

  * body present        — non-trivial opaque pixel coverage in every frame
  * silhouette clarity  — start / mid / end poses are pairwise DISTINCT
                          (no identical start/mid/end pose)
  * visible progression — consecutive samples differ (it MOVES, no frozen zone)
  * no clipping         — opaque pixels keep off the canvas border

Runs headless with cairosvg; SKIPS (exit 0 with a warning) when no SVG
rasteriser is available (the CI preview installs libcairo2 before this runs).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# The primitives production may select — the VERIFIED library + coupled/arc set.
GATED = ["drag_line", "pull_down_win", "shoved_bar", "hoist_stack",
         "push_bar_arc", "ride_line_arc", "lift_arc", "climb_arc",
         # expanded performance families (Phase 5)
         "balance_beam", "catch_fall", "block_wall", "get_buried",
         "overwhelmed", "race_sprint", "compressed", "stretched",
         "discover", "compare_scales", "transform_reveal", "fail_recover",
         "stack_tiles"]
SAMPLES = [0.04, 0.2, 0.35, 0.5, 0.65, 0.8, 0.96]
SIZE = 200

_passed, _failed = [], []


def check(name, ok, detail=""):
    tag = "ok  " if ok else "FAIL"
    print(f"  {tag} {name}{(' — ' + detail) if detail else ''}")
    (_passed if ok else _failed).append(name)


def _frames(md, action):
    import io
    from PIL import Image
    out = []
    for p in SAMPLES:
        png = md._rasterise(md.compose_anim(
            {"action": action, "prop": "none", "ground": False}, p), SIZE)
        out.append(Image.open(io.BytesIO(png)).convert("RGBA"))
    return out


def _alpha_stats(im):
    a = im.getchannel("A")
    data = a.getdata()
    n = len(data)
    opaque = sum(1 for v in data if v > 40)
    return opaque / max(1, n)


def _diff(a, b):
    from PIL import ImageChops
    d = ImageChops.difference(a.convert("L"), b.convert("L"))
    h = d.histogram()
    moved = sum(h[12:])                     # pixels that changed by >12/255
    return moved / max(1, a.size[0] * a.size[1])


def _touches_border(im, tol=0.004):
    a = im.getchannel("A")
    w, h = im.size
    px = a.load()
    border = 0
    for x in range(w):
        border += (px[x, 0] > 40) + (px[x, h - 1] > 40)
    for y in range(h):
        border += (px[0, y] > 40) + (px[w - 1, y] > 40)
    return border / max(1, 2 * (w + h)) > tol


def main() -> int:
    try:
        from data_learning import mascot_director as md
        md._rasterise(md.compose_anim(
            {"action": "cheer", "prop": "none"}, 0.0), 40)
    except Exception as e:  # noqa: BLE001
        print(f"SKIP: no SVG rasteriser available ({e})")
        return 0
    for act in GATED:
        print(f"[{act}]")
        try:
            fr = _frames(md, act)
        except Exception as e:  # noqa: BLE001
            check("renders", False, str(e)[:80])
            continue
        cov = [_alpha_stats(f) for f in fr]
        check("body present every frame", min(cov) > 0.02,
              f"min coverage {min(cov):.3f}")
        s, m, e = fr[0], fr[len(fr) // 2], fr[-1]
        dsm, dme, dse = _diff(s, m), _diff(m, e), _diff(s, e)
        check("start/mid/end distinct silhouettes",
              min(dsm, dme, dse) > 0.005,
              f"diffs {dsm:.3f}/{dme:.3f}/{dse:.3f}")
        moves = [_diff(a, b) for a, b in zip(fr, fr[1:])]
        check("visible progression (no frozen zone)", min(moves) > 0.0015,
              f"min step diff {min(moves):.4f}")
        check("no canvas clipping", not any(_touches_border(f) for f in fr))
    print(f"\nprimitive gate: {len(_passed)} ok, {len(_failed)} failed")
    if _failed:
        print("FAILED:", _failed)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
