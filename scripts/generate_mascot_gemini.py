#!/usr/bin/env python3
"""Generate the mascot pose set via Google's Gemini 2.5 Flash Image
("Nano Banana") with true character-locking.

Character: the channel's teal monster professor — a friendly, rounded
teal creature, cartoon-professor vibe. Kept close to the original hand-
drawn concept the user approved, but pinned down aggressively so the
model can't drift (two matching horns, two same-size eyes, mitten hands
with no fingers to mangle, no stray forehead eyebrow — every prior AI
failure mode the user called out is nailed shut in the prompt).

The key upgrade over text-only generation: we generate ONE anchor pose
("idle") from text, then feed that PNG back as an IMAGE REFERENCE on
every subsequent pose ("same character, exact same colors/proportions,
new pose"). That is what makes the set actually recreatable across poses
instead of six unrelated drawings.

Pipeline per pose:
  1. Gemini generates the image on a plain white background
  2. rembg strips the background to alpha so the mascot sits cleanly
     over our video stack
  3. PIL resizes to the canonical 520x520 (renderer downscales)

Env: GEMINI_API_KEY required.
"""
from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "mascot" / "anchor"

# Character description used VERBATIM in every prompt. Every clause here
# exists to shut down a specific drift the user called out on earlier AI
# mascots: mismatched horns, different-sized eyes, an eyebrow floating on
# the forehead, mangled hands, colors changing between poses.
CHARACTER = (
    "A friendly cartoon MONSTER mascot named 'Data', drawn in a clean, "
    "modern flat-vector cartoon style (like a polished YouTube channel "
    "mascot, NOT a realistic render). "
    "BODY: one single rounded egg-shaped body in a solid TEAL color "
    "(blue-green, hex about #35B7A6), with a lighter MINT-GREEN oval "
    "belly patch on the front. "
    "HORNS: EXACTLY TWO short rounded horns on top of the head. Both "
    "horns are the SAME teal color as the body, the SAME size, and "
    "symmetric — one on the left, one on the right. Never a third horn, "
    "never mismatched colors. "
    "EYES: EXACTLY TWO large round white eyes, IDENTICAL in size, evenly "
    "spaced side by side, each with a single round black pupil looking "
    "the same direction. Never a third eye, never different-sized eyes. "
    "NO eyebrow floating on the forehead. "
    "FACE: a small friendly smile and a tiny rounded snout. Round black "
    "'professor' glasses resting on the face, and a small dark BOW TIE "
    "at the neck (smart, professorial look). "
    "HANDS: simple rounded MITTEN hands with NO separate fingers, same "
    "teal color as the body. Short rounded arms and short rounded legs "
    "with simple oval feet. "
    "STYLE: bold clean BLACK OUTLINES around every shape, FLAT solid "
    "color fills, no gradients, no realistic fur texture, no shading "
    "beyond simple flat cel-shading. Cute, professional, consistent. "
    "FULL BODY visible and centered. SOLID PURE WHITE background. "
    "SQUARE 1:1 aspect ratio. The exact SAME character in every image."
)

# Anchor pose generated first (text-only); its image is then fed back as
# a reference for every other pose. Keep 'idle' first in this dict.
POSES = {
    "idle": "POSE: Standing upright facing the viewer, relaxed and "
            "friendly. One mitten hand raised in a small wave. Calm "
            "closed-mouth smile, both eyes looking at the viewer. This "
            "is the clean reference pose.",
    "point": "POSE: Standing, enthusiastically POINTING with one arm "
             "fully extended out to the side and slightly up, mitten "
             "hand indicating something. Confident, encouraging smile, "
             "eyes following the point. Pointing arm clearly visible.",
    "shock": "POSE: SHOCKED / amazed. Both mitten hands raised up near "
             "the sides of the head, mouth open in a surprised 'O', eyes "
             "wide. Leaning back slightly in surprise. Reacting to a big "
             "number.",
    "laugh": "POSE: LAUGHING joyfully, head tilted back a little, mouth "
             "open in a big grin, eyes happy. One mitten hand on the "
             "belly. Genuinely delighted.",
    "think": "POSE: THINKING / curious. One mitten hand up touching the "
             "chin, head tilted, eyes looking up and to the side, small "
             "pondering mouth. Professor working something out.",
    "cheer": "POSE: CELEBRATING a win. BOTH arms thrown up high in the "
             "air, mitten hands open, big open-mouth grin, eyes bright "
             "and happy, jumping slightly. Triumphant.",
    "duck": "POSE: CROUCHED DOWN LOW, knees bent, leaning forward and "
            "reaching DOWN with both mitten hands as if catching or "
            "ducking under things falling from above. Looking downward, "
            "focused expression. Low, compact posture.",
    "ride": "POSE: SEATED as if RIDING a mount — legs straddling forward "
            "and apart, body leaning forward, BOTH mitten hands out in "
            "front gripping invisible reins, excited open grin, eyes "
            "forward. Posed so it can be composited sitting on top of "
            "another character. No mount drawn — just the rider.",
}

# Tried in order, picking the first with quota. The 2.5-flash-image
# series ("Nano Banana") is the one that properly honors an image
# reference for character-locking, so it is preferred; the 2.0 exp model
# is a text-mostly fallback. imagen-* are last-ditch (text only, no ref).
MODEL_CANDIDATES = (
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.5-flash-preview-image",
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.0-flash-preview-image-generation",
    "imagen-3.0-generate-002",
    "imagen-4.0-generate-001",
)


def list_available_models(client) -> set[str]:
    available: set[str] = set()
    for m in client.models.list():
        name = getattr(m, "name", "") or ""
        # API returns 'models/<id>' — strip the prefix.
        available.add(name.split("/", 1)[-1])
    return available


def generate_pose(client, model: str, pose: str, description: str,
                  ref_png: bytes | None = None) -> bytes:
    """One Gemini call per pose. When ref_png is given (and the model
    supports image input), it is passed alongside the text so the model
    keeps the exact same character — this is what makes the set
    consistent. Returns PNG bytes; raises if no image comes back."""
    from google.genai import types
    if ref_png is not None:
        prompt = (
            "Here is the reference drawing of the character. Redraw the "
            "EXACT SAME character — identical colors, identical horns, "
            "identical eyes, identical glasses and bow tie, identical "
            "proportions and art style — in a NEW pose.\n\n"
            f"{CHARACTER}\n\n{description}\n\nGenerate the image now."
        )
        contents = [
            types.Part.from_bytes(data=ref_png, mime_type="image/png"),
            prompt,
        ]
    else:
        prompt = f"{CHARACTER}\n\n{description}\n\nGenerate the image now."
        contents = prompt
    print(f"  [{pose}] generating"
          + (" (with character reference)" if ref_png else "") + "...",
          flush=True)
    response = client.models.generate_content(
        model=model,
        contents=contents,
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
    """Canonical mascot asset size. The renderer downscales when
    overlaying; keeping a 520 source means we can re-tune the final
    size without regenerating."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    img = img.resize((520, 520), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _supports_ref(model: str) -> bool:
    """imagen-* go through a different (image-only) path and don't take
    a reference image in generate_content; everything else does."""
    return not model.startswith("imagen")


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    from google import genai
    from google.genai import errors as genai_errors
    client = genai.Client(api_key=api_key)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    available = list_available_models(client)
    candidates = [m for m in MODEL_CANDIDATES if m in available]
    if not candidates:
        raise RuntimeError(
            f"no known image-gen model available to this key. "
            f"Tried {MODEL_CANDIDATES!r}. Available models: "
            f"{sorted(available)[:20]}..."
        )
    print(f"  trying candidate models in order: {candidates}")

    # Pick a working model by attempting the anchor pose with each
    # candidate until one succeeds. Surfaces 429 (quota) / billing errors
    # clearly so the user knows whether to enable billing.
    first_pose, first_desc = next(iter(POSES.items()))
    model: str | None = None
    last_err: Exception | None = None
    first_image: bytes | None = None
    for cand in candidates:
        try:
            print(f"  probing {cand}...")
            first_image = generate_pose(client, cand, first_pose, first_desc)
            model = cand
            print(f"  using image model: {model}")
            break
        except genai_errors.ClientError as e:
            last_err = e
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            print(f"    {cand} -> {code}: {str(e)[:140]}")
            continue
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"    {cand} -> {type(e).__name__}: {str(e)[:140]}")
            continue
    if model is None or first_image is None:
        raise RuntimeError(
            f"every candidate image-gen model rejected the call. "
            f"Last error: {last_err}. If this is a quota/billing error, "
            f"enable billing on the API key at "
            f"https://aistudio.google.com/apikey and re-run."
        )

    # The anchor image (white background, before rembg) is our character
    # reference for every subsequent pose.
    reference = first_image if _supports_ref(model) else None

    transparent = remove_bg_to_alpha(first_image)
    sized = resize_to_520(transparent)
    (OUT_DIR / f"{first_pose}.png").write_bytes(sized)
    print(f"  [{first_pose}] saved (anchor)")

    for pose, description in POSES.items():
        if pose == first_pose:
            continue
        time.sleep(2)
        raw = generate_pose(client, model, pose, description, ref_png=reference)
        transparent = remove_bg_to_alpha(raw)
        sized = resize_to_520(transparent)
        path = OUT_DIR / f"{pose}.png"
        path.write_bytes(sized)
        print(f"  [{pose}] saved -> {path} ({len(sized)} bytes)")

    print(f"\ndone: {len(POSES)} poses in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
