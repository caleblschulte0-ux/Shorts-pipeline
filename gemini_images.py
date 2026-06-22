"""Gemini image generation + vision-QA helpers shared by the daily pipeline.

Three jobs, all best-effort:
  * generate_image()  — FREE-tier image generation for shot backfill +
                        thumbnail backgrounds (feature 2 / 1).
  * vision_judge()    — frame QA on the finished video (feature 3).
  * build_thumbnail() — compose a 1280x720 thumbnail (feature 1).

Hard rule: NOTHING here may raise into the render or upload path. Every
entry point catches everything and degrades — returns None / a fail-open
verdict / a plain gradient — so a missing key, an uninstalled SDK, or a
quota error can never break a daily run.

Cost policy: image GENERATION only ever calls the free / experimental
Gemini image models below. The paid models (gemini-2.5-flash-image*,
imagen-*) are deliberately NOT in the list, so we never incur per-image
charges. Vision QA runs on the free flash text+vision tier.
"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

# Free / experimental image-gen models ONLY (no paid models here).
FREE_IMAGE_MODELS = (
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.0-flash-preview-image-generation",
)
VISION_MODEL = "gemini-2.5-flash"


def enabled() -> bool:
    """True only when a key is configured. Cheap gate callers check first."""
    return bool(os.environ.get("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def _client():
    if not enabled():
        return None
    try:
        from google import genai
        return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    except Exception as e:  # noqa: BLE001
        print(f"[gemini] client unavailable: {type(e).__name__}: {e}", flush=True)
        return None


@lru_cache(maxsize=1)
def _available_models() -> frozenset:
    c = _client()
    if not c:
        return frozenset()
    try:
        return frozenset(
            getattr(m, "name", "").split("/")[-1] for m in c.models.list()
        )
    except Exception:  # noqa: BLE001
        return frozenset()  # empty -> don't filter, just try


# --------------------------------------------------------------------------- #
# image generation (free models only)
# --------------------------------------------------------------------------- #
def generate_image(prompt: str, out_path: Path) -> Path | None:
    """Generate one image from `prompt` using a FREE Gemini image model.

    Returns the written path, or None when generation isn't available
    (no key, the free model isn't offered to this key, quota, or any
    error). Never raises.
    """
    c = _client()
    if not c or not prompt:
        return None
    avail = _available_models()
    models = [m for m in FREE_IMAGE_MODELS if (not avail or m in avail)]
    if not models:
        return None
    try:
        from google.genai import types
    except Exception:  # noqa: BLE001
        return None
    full = (
        prompt.strip()
        + "\n\nStyle: clean, photorealistic, vertical 9:16 framing, no text, "
        "no captions, no watermarks, no logos. Generate the image now."
    )
    out_path = Path(out_path)
    for model in models:
        try:
            resp = c.models.generate_content(
                model=model,
                contents=full,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]),
            )
            for part in resp.candidates[0].content.parts:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if data:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(data)
                    print(f"[gemini] image via {model} -> {out_path.name}",
                          flush=True)
                    return out_path
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] image gen via {model} skipped: "
                  f"{type(e).__name__}: {e}", flush=True)
            continue
    return None


# --------------------------------------------------------------------------- #
# vision QA
# --------------------------------------------------------------------------- #
def vision_judge(frame_paths, *, topic: str = "", title: str = "") -> dict:
    """Judge whether sampled video frames are broken/unsafe.

    Returns {"ok": bool, "verdict": str, "reason": str}. Fail-open: any
    error, missing key, or unpartseable reply returns ok=True so QA can
    never block a good video on an infrastructure hiccup.
    """
    fail_open = {"ok": True, "verdict": "skip", "reason": "gemini unavailable"}
    c = _client()
    frame_paths = [p for p in (frame_paths or []) if Path(p).exists()]
    if not c or not frame_paths:
        return fail_open
    try:
        from google.genai import types
        parts = []
        for fp in frame_paths:
            parts.append(types.Part.from_bytes(
                data=Path(fp).read_bytes(), mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text=(
            "You QA frames from an automated vertical short-video pipeline. "
            f"The video is about: {(title or topic)!r}. Each frame is a "
            "stacked composite: the TOP half is a news/stock photo, the "
            "BOTTOM half is an abstract game animation (this is expected, "
            "NOT an error). Reply with STRICT JSON and nothing else: "
            '{"broken": bool, "unsafe": bool, "reason": "short"}. '
            "Set broken=true ONLY if the TOP image is corrupt, garbled, "
            "smeared, a gray/blank placeholder, or an obvious render error. "
            "Set unsafe=true ONLY for graphic gore, nudity, or hateful "
            "imagery. Mildly off-topic imagery is NOT broken."
        )))
        resp = c.models.generate_content(model=VISION_MODEL, contents=parts)
        text = (getattr(resp, "text", "") or "").strip()
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
        broken, unsafe = bool(data.get("broken")), bool(data.get("unsafe"))
        return {
            "ok": not (broken or unsafe),
            "verdict": "broken" if broken else "unsafe" if unsafe else "ok",
            "reason": str(data.get("reason", ""))[:200],
        }
    except Exception as e:  # noqa: BLE001
        print(f"[gemini] vision judge failed (allowing upload): "
              f"{type(e).__name__}: {e}", flush=True)
        return fail_open


# --------------------------------------------------------------------------- #
# thumbnail
# --------------------------------------------------------------------------- #
def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    try:
        import matplotlib
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name
        return ImageFont.truetype(str(path), size)
    except Exception:  # noqa: BLE001
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()


def _load_bg(src):
    """Open a background from a local path OR an http(s) URL. None on miss."""
    if not src:
        return None
    try:
        from PIL import Image
        if str(src).startswith(("http://", "https://")):
            req = urllib.request.Request(str(src), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        if Path(src).exists():
            return Image.open(src).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    return None


def _cover(img, w: int, h: int):
    """Resize+center-crop so img fills w x h (no letterboxing)."""
    from PIL import Image
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))), Image.LANCZOS)
    iw, ih = img.size
    left, top = (iw - w) // 2, (ih - h) // 2
    return img.crop((left, top, left + w, top + h))


def build_thumbnail(out_path, *, title: str, hook: str | None = None,
                    bg_image=None, bg_prompt: str | None = None) -> Path | None:
    """Compose a 1280x720 thumbnail: a story-relevant background (an
    existing pinned image, else a FREE Gemini generation, else a dark
    gradient) with the hook overlaid in bold. Returns the path, or None
    if PIL is missing / anything fails (caller just skips it)."""
    try:
        from PIL import Image, ImageDraw
    except Exception:  # noqa: BLE001
        return None
    W, H = 1280, 720
    out_path = Path(out_path)
    try:
        bg = _load_bg(bg_image)
        if bg is None and bg_prompt:
            gp = generate_image(bg_prompt, out_path.with_suffix(".bg.png"))
            bg = _load_bg(gp) if gp else None
        if bg is None:
            bg = Image.new("RGB", (W, H), (16, 18, 30))
        bg = _cover(bg, W, H)

        # Bottom-up dark scrim for legibility.
        black = Image.new("RGB", (W, H), (0, 0, 0))
        scrim = Image.new("L", (1, H), 0)
        px = scrim.load()
        for y in range(H):
            px[0, y] = int(235 * (y / H) ** 1.4)
        bg = Image.composite(black, bg, scrim.resize((W, H)))

        draw = ImageDraw.Draw(bg)
        text = (hook or title or "").upper().strip().strip("?!.,")
        if text:
            font = _font(96)
            # Greedy word-wrap to the width.
            words, lines, cur = text.split(), [], ""
            for wd in words:
                trial = (cur + " " + wd).strip()
                if draw.textlength(trial, font=font) <= W - 120:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = wd
            if cur:
                lines.append(cur)
            lines = lines[:4]
            lh = int(font.size * 1.12)
            y = H - 60 - lh * len(lines)
            for ln in lines:
                draw.text((60, y), ln, font=font, fill=(255, 255, 255),
                          stroke_width=6, stroke_fill=(0, 0, 0))
                y += lh

        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg.save(out_path, "JPEG", quality=88)
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"[gemini] thumbnail failed: {type(e).__name__}: {e}", flush=True)
        return None
