#!/usr/bin/env python3
"""Generate the 6 Bigfoot-anchor mascot poses via Google's Gemini
2.5 Flash Image model.

Character: "Squatch the News Guy" — a friendly Saturday-morning-cartoon
sasquatch in a navy suit + red tie reading the news. Six poses
(idle/shock/point/laugh/think/dismiss) generated with an aggressively
specific character description repeated verbatim across every prompt
so the model stays on-character.

Pipeline per pose:
  1. Gemini generates the image on a plain white background
  2. rembg strips the background to alpha so the mascot sits cleanly
     over our top/bottom video stack
  3. PIL resizes to the canonical 520x520 (renderer downscales to 260)

Env: GEMINI_API_KEY required. Free tier of gemini-2.5-flash-image
covers ~10 RPM which is plenty for 6 sequential calls.
"""
from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "mascot" / "anchor"

# Character description used VERBATIM in every prompt. Aggressively
# specific about color + style so Gemini doesn't drift between poses.
CHARACTER = (
    "A cute Saturday-morning-cartoon mascot: a friendly cartoon "
    "SASQUATCH/BIGFOOT character. He wears a NAVY BLUE suit jacket "
    "with visible lapels, a WHITE dress shirt with collar, and a "
    "SOLID RED necktie. Light reddish-brown shaggy fur covers his "
    "round head, neck, and the parts of his arms not covered by "
    "the suit. He has VERY LARGE round white eyes with black pupils, "
    "a small black triangle nose, and visible thick cartoon eyebrows. "
    "Bold BLACK OUTLINES around every shape (clean vector cartoon "
    "style, like Cartoon Network or Cocomelon). FLAT solid color "
    "fills, no realistic textures or shading. Chest-up framing, "
    "centered in the frame. SOLID WHITE background. SQUARE 1:1 "
    "aspect ratio. Same character across the whole series."
)

POSES = {
    "idle": "POSE: Calm, neutral expression. Small closed-mouth "
            "smile. Both eyes open and looking directly at the "
            "viewer. Eyebrows relaxed and level. Arms at his sides. "
            "Default at-the-news-desk pose.",
    "shock": "POSE: SHOCKED expression. Eyes WIDE OPEN in surprise, "
             "pupils small. Mouth in a big round 'O' shape, gasping. "
             "Eyebrows raised HIGH on the forehead. Hands raised "
             "near the sides of the head in surprise.",
    "point": "POSE: He is enthusiastically POINTING to the RIGHT "
             "side of the frame with his right arm fully extended "
             "and his index finger out. Confident expression, "
             "small smile, eyebrows neutral. The pointing arm and "
             "hand are clearly visible and unobstructed.",
    "laugh": "POSE: He is LAUGHING joyfully. Eyes squeezed shut "
             "into upward smile arcs (^_^ shape). Mouth WIDE OPEN "
             "showing a row of white teeth in a big grin. Head "
             "tilted back slightly. Eyebrows raised happily.",
    "think": "POSE: THINKING / pondering. His right hand is held "
             "up to his chin, finger touching the chin. Eyes looking "
             "UP AND TO THE SIDE. ONE eyebrow raised quizzically, "
             "the other flat. Mouth in a small pursed line.",
    "dismiss": "POSE: SKEPTICAL / dismissive. One eyebrow raised "
               "HIGH, the other lowered down. Mouth in a one-sided "
               "SMIRK (left corner flat, right corner pulled up). "
               "Eyes half-lidded looking sideways. Arms crossed "
               "over the chest in a 'really?' gesture.",
}

MODEL = "gemini-2.5-flash-image-preview"


def generate_pose(client, pose: str, description: str) -> bytes:
    """One Gemini call per pose. Returns PNG bytes of the generated
    image. Raises if no image part comes back in the response."""
    from google.genai import types
    prompt = f"{CHARACTER}\n\n{description}\n\nGenerate the image now."
    print(f"  [{pose}] generating...", flush=True)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError(f"no image in Gemini response for pose {pose!r}")


def remove_bg_to_alpha(png_bytes: bytes) -> bytes:
    """rembg strips the solid white background to alpha so the mascot
    overlays cleanly over the video stack."""
    from PIL import Image
    from rembg import remove
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    out = remove(img)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def resize_to_520(png_bytes: bytes) -> bytes:
    """Canonical mascot asset size. The renderer downscales to 260
    when overlaying; keeping a 520 source means we can re-tune the
    final size without regenerating."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    img = img.resize((520, 520), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    from google import genai
    client = genai.Client(api_key=api_key)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for pose, description in POSES.items():
        # Tiny pause to stay polite to the free-tier RPM.
        time.sleep(2)
        raw = generate_pose(client, pose, description)
        transparent = remove_bg_to_alpha(raw)
        sized = resize_to_520(transparent)
        path = OUT_DIR / f"{pose}.png"
        path.write_bytes(sized)
        print(f"  [{pose}] saved -> {path} ({len(sized)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
