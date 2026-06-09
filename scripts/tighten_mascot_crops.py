"""Tighten the mascot PNG crops so the character fills the visible
frame instead of floating in transparent padding.

The original extraction (b23db86) used a 40px margin around each
character — generous on purpose so we wouldn't accidentally clip a
finger or the tip of a fur tuft. The downside is that when the
renderer downscales 520x520 to the on-screen overlay size, the
character ends up much smaller than the allocated space, which
reads as "static PNG slapped in the corner" instead of "character
on screen".

This script reloads each pose PNG, finds the bbox of all non-
transparent pixels (the actual character outline), and re-pads with
only an 8px margin. Net effect: the character ~doubles in apparent
size at the same overlay dimensions.

Idempotent — re-running won't keep shrinking; the bbox-then-pad is
stable once tight.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import numpy as np

ANCHOR_DIR = Path(__file__).resolve().parent.parent / "assets" / "mascot" / "anchor"
POSES = ("idle", "shock", "point", "laugh", "think", "dismiss")
TARGET = 520
MARGIN = 8


def tighten(path: Path) -> tuple[int, int]:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[..., 3]
    # alpha > 16 to ignore faint anti-aliased edges that drift toward
    # transparent — those would inflate the bbox.
    mask = alpha > 16
    if not mask.any():
        return img.size
    ys, xs = np.where(mask)
    bbox = (int(xs.min()), int(ys.min()),
            int(xs.max()) + 1, int(ys.max()) + 1)
    cropped = img.crop(bbox)
    w, h = cropped.size
    side = max(w, h) + MARGIN * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)
    canvas = canvas.resize((TARGET, TARGET), Image.LANCZOS)
    canvas.save(path, "PNG")
    return w, h


def main() -> None:
    for pose in POSES:
        p = ANCHOR_DIR / f"{pose}.png"
        if not p.exists():
            print(f"  {pose:8s} -> MISSING ({p})")
            continue
        w, h = tighten(p)
        print(f"  {pose:8s} -> tightened (char {w}x{h} in {TARGET}x{TARGET})")


if __name__ == "__main__":
    main()
