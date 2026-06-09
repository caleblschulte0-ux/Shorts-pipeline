"""Extract the 6 mascot poses from individual single-character images.

Differs from extract_mascot_sheet.py only in input: instead of one
multi-pose grid, we take a {pose: image_path} mapping and process
each image as a standalone character on white. Same flood-fill +
character-outline bbox + square-pad + resize pipeline.

Usage:
  python3 scripts/extract_mascot_singles.py

Edit POSE_SOURCES below to swap art later.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "mascot" / "anchor"
UPLOAD_DIR = Path(
    "/root/.claude/uploads/a688cd2c-2064-5aca-8564-b8d7228f1156"
)

# Map each pose to its source PNG. All images are single-character on
# white background; the extractor keys out the white from the four
# corners (preserves the white inside the eyes because those pixels
# aren't connected to the image edge through the cartoon outlines).
POSE_SOURCES = {
    "idle":    UPLOAD_DIR / "2be786bf-9ECA4635C9B541AEBAFB8194C6C7B781.png",
    "shock":   UPLOAD_DIR / "e603be95-AF1C6AD52F7A4DB692AE41A9E650F078.png",
    "point":   UPLOAD_DIR / "bb12a7bf-BDF3FCC54E094C0D9F0A41D43489047F.png",
    "laugh":   UPLOAD_DIR / "e034770d-E67CDAAD5EE44B4C978C0315D82C54DB.png",
    "think":   UPLOAD_DIR / "c3d203b3-7D0D4CEF257B4641B41C3C7F3D3D50E9.png",
    "dismiss": UPLOAD_DIR / "54e2317b-79EC2FA801BF4106A9854F740C0E61C9.png",
}

SENTINEL = (1, 254, 1)
FLOOD_THRESH = 16


def _flood_corners(img: Image.Image) -> Image.Image:
    """Flood-fill from all four corners with SENTINEL. The white inside
    the eyes survives because it's isolated by the black cartoon
    outlines and never gets reached by the corner-seeded fill."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        r, g, b = rgb.getpixel(xy)
        if r < 240 or g < 240 or b < 240:
            continue
        ImageDraw.floodfill(rgb, xy, SENTINEL, thresh=FLOOD_THRESH)
    return rgb


def _key_out_sentinel(rgb: Image.Image) -> Image.Image:
    import numpy as np
    arr = np.array(rgb)
    sr, sg, sb = SENTINEL
    mask = (arr[..., 0] == sr) & (arr[..., 1] == sg) & (arr[..., 2] == sb)
    rgba = np.dstack([arr, np.where(mask, 0, 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA")


def _character_bbox(rgb: Image.Image) -> tuple[int, int, int, int]:
    """Bbox of the character via its black outlines, not flood-fill
    residue. See extract_mascot_sheet.py for the full rationale."""
    import numpy as np
    arr = np.array(rgb)
    dark = arr.max(axis=2) < 200
    if not dark.any():
        return (0, 0, rgb.size[0], rgb.size[1])
    ys, xs = np.where(dark)
    return (int(xs.min()), int(ys.min()),
            int(xs.max()) + 1, int(ys.max()) + 1)


def _square_pad_resize(rgba: Image.Image, bbox: tuple[int, int, int, int],
                       target: int = 520, margin: int = 40) -> Image.Image:
    cropped = rgba.crop(bbox)
    w, h = cropped.size
    side = max(w, h) + margin * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)
    return canvas.resize((target, target), Image.LANCZOS)


def extract_one(src_path: Path, pose: str) -> Path:
    src = Image.open(src_path).convert("RGBA")
    flooded = _flood_corners(src)
    bbox = _character_bbox(flooded)
    keyed = _key_out_sentinel(flooded)
    final = _square_pad_resize(keyed, bbox)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{pose}.png"
    final.save(out_path, "PNG")
    return out_path


def main() -> int:
    missing = [p for p in POSE_SOURCES.values() if not p.exists()]
    if missing:
        print("ERROR: missing source files:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1
    for pose, src in POSE_SOURCES.items():
        path = extract_one(src, pose)
        print(f"  {pose:8s} <- {src.name[:32]}...  ->  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
