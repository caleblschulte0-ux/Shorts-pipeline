#!/usr/bin/env python3
"""Render the clip channel's reaction-emoji overlay set to transparent PNGs.

The overlay effect layer (third_capture/auto_edit) pops a contextual emoji on
the money moment. Rather than depend on a color-emoji font at render time
(ffmpeg drawtext + NotoColorEmoji is finicky), we bake a small curated set to
RGBA PNGs here and overlay the images. Re-run to regenerate; the committed
PNGs are what the renderer uses.

Font: Noto Color Emoji (system package fonts-noto-color-emoji, OFL 1.1).
Only the rendered glyphs are redistributed, each a standard Unicode emoji.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
STRIKE = 109          # NotoColorEmoji ships a single ~136px bitmap strike
PAD = 8

# name -> emoji codepoint. Names are what the renderer references by series.
EMOJI = {
    "skull": "\U0001F480",       # 💀 fail / dead
    "fire": "\U0001F525",        # 🔥 clutch / win / hype
    "sob": "\U0001F62D",         # 😭 pain / loss
    "joy": "\U0001F602",         # 😂 funny
    "eyes": "\U0001F440",        # 👀 suspicious / argument
    "mindblown": "\U0001F92F",   # 🤯 chaos / shock
    "scream": "\U0001F631",      # 😱 jumpscare / shock
    "flushed": "\U0001F633",     # 😳 awkward
    "pleading": "\U0001F97A",    # 🥹 wholesome
    "rage": "\U0001F621",        # 😡 rage
}


def render(name: str, ch: str) -> None:
    font = ImageFont.truetype(FONT, STRIKE)
    canvas = Image.new("RGBA", (STRIKE * 2, STRIKE * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((STRIKE // 2, STRIKE // 2), ch, font=font, embedded_color=True)
    bbox = canvas.getbbox()
    if not bbox:
        print(f"!! {name}: no pixels rendered")
        return
    crop = canvas.crop((max(0, bbox[0] - PAD), max(0, bbox[1] - PAD),
                        bbox[2] + PAD, bbox[3] + PAD))
    crop.save(HERE / f"{name}.png")
    print(f"wrote {name}.png {crop.size}")


if __name__ == "__main__":
    for n, c in EMOJI.items():
        render(n, c)
