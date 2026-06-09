"""Extract the 6 mascot poses from the ChatGPT-generated 2x3 sheet.

Source: ChatGPT-rendered cartoon Bigfoot anchor, 1536x1024 on a white
background, 2 rows x 3 columns. We crop each cell, flood-fill the
white background to transparent (preserving white inside the eyes
because they're not connected to the cell border), tightly crop to
the character, pad to square, and downsize to 520x520 — the size the
renderer expects in assets/mascot/anchor/.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "mascot" / "anchor"

SOURCE = Path(
    "/root/.claude/uploads/a688cd2c-2064-5aca-8564-b8d7228f1156/"
    "c7b73af6-258647E98B3345ADBA1AAFE996F2B798.png"
)

# Visual mapping of the 2x3 grid (col, row) -> pose name
POSE_GRID = {
    (0, 0): "idle",
    (1, 0): "shock",
    (2, 0): "point",
    (0, 1): "laugh",
    (1, 1): "think",
    (2, 1): "dismiss",
}

# Sentinel color we flood-fill the background to. RGB chosen so it
# can't conflict with anything in the artwork.
SENTINEL = (1, 254, 1)
# Threshold for "this pixel is close enough to white to be part of
# the background". The art uses pure white (255,255,255), but JPEG-
# style edge artifacts can drop a few values, so we accept up to ~15
# off pure white.
FLOOD_THRESH = 16


def _flood_corners(img: Image.Image) -> Image.Image:
    """Flood-fill from all four corners with SENTINEL. Anything that
    gets recolored is connected white background; anything left in
    its original color (including the white inside the eyes which is
    isolated by black outlines) survives."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        # Skip if the corner isn't actually white-ish — picking a non-bg
        # seed would erase the character.
        r, g, b = rgb.getpixel(xy)
        if r < 240 or g < 240 or b < 240:
            continue
        ImageDraw.floodfill(rgb, xy, SENTINEL, thresh=FLOOD_THRESH)
    return rgb


def _key_out_sentinel(rgb: Image.Image) -> Image.Image:
    """Convert any SENTINEL pixel to fully transparent; everything
    else gets full opacity."""
    rgba = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    src_data = list(rgb.getdata())
    out_data = []
    sr, sg, sb = SENTINEL
    for r, g, b in src_data:
        if r == sr and g == sg and b == sb:
            out_data.append((0, 0, 0, 0))
        else:
            out_data.append((r, g, b, 255))
    rgba.putdata(out_data)
    return rgba


def _character_bbox(rgb: Image.Image) -> tuple[int, int, int, int]:
    """Find the bounding box of the CHARACTER, not the cell artifacts.

    After flood-fill the background should be SENTINEL, but ChatGPT
    sheets tend to have faint near-white halos / gradient noise at the
    cell boundaries that the flood-fill thresh doesn't catch. Using
    bbox of "non-sentinel pixels" then catches that halo and inflates
    the bbox to the full cell.

    The fix: bbox of pixels whose max(R,G,B) is clearly below white —
    i.e. the cartoon's BLACK OUTLINES and shading. That gives the real
    character extent because every pose has dark outline strokes
    around the silhouette. The white shirt + eye-whites sit INSIDE
    that outline-defined bbox, so they're included automatically once
    we crop the original image to it."""
    import numpy as np
    arr = np.array(rgb)               # H x W x 3
    # "darkish" = at least one channel < 200, i.e. clearly not white
    dark = arr.max(axis=2) < 200      # H x W bool
    if not dark.any():
        return (0, 0, rgb.size[0], rgb.size[1])
    ys, xs = np.where(dark)
    return (int(xs.min()), int(ys.min()),
            int(xs.max()) + 1, int(ys.max()) + 1)


def _square_pad_resize(rgba: Image.Image, bbox: tuple[int, int, int, int],
                       target: int = 520, margin: int = 40) -> Image.Image:
    """Crop the keyed image to ``bbox``, pad to a square with margin,
    then resize to target x target. Margin is generous (40px on the
    pre-resize square) so the character has breathing room — viewers
    notice clipping at the edges more than they notice extra
    transparent space."""
    cropped = rgba.crop(bbox)
    w, h = cropped.size
    side = max(w, h) + margin * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)
    return canvas.resize((target, target), Image.LANCZOS)


def extract_one(src: Image.Image, col: int, row: int, pose: str,
                cell_w: int, cell_h: int) -> Path:
    cell = src.crop((col * cell_w, row * cell_h,
                     (col + 1) * cell_w, (row + 1) * cell_h))
    flooded = _flood_corners(cell)
    bbox = _character_bbox(flooded)
    keyed = _key_out_sentinel(flooded)
    final = _square_pad_resize(keyed, bbox)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{pose}.png"
    final.save(out_path, "PNG")
    return out_path


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        return 1
    src = Image.open(SOURCE).convert("RGBA")
    W, H = src.size
    cell_w, cell_h = W // 3, H // 2
    print(f"source {W}x{H}, cell {cell_w}x{cell_h}")
    for (col, row), pose in POSE_GRID.items():
        path = extract_one(src, col, row, pose, cell_w, cell_h)
        print(f"  {pose:8s} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
