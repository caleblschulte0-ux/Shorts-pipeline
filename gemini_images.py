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

import hashlib
import io
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

# Content-addressed store for generated images (audit Ticket 5) — under the
# gitignored cache/ dir so actions/cache persists it between CI runs.
_GEN_CACHE_DIR = Path(__file__).resolve().parent / "cache" / "gen_images"

# Pollinations.ai — free, keyless image generation. Primary generator: it
# actually works (unlike the deprecated free Gemini image models) so any
# beat/thumbnail/cover that lacks real media gets an on-topic image for $0.
POLLINATIONS_IMG = "https://image.pollinations.ai/prompt/"

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
def generate_image(prompt, out_path, *, width: int = 1024, height: int = 1024,
                   seed=None) -> "Path | None":
    """Generate one on-topic image. Primary: Pollinations.ai (free, keyless,
    reliable); fallback: free-tier Gemini. Returns the written path or None;
    never raises.

    Use for ILLUSTRATIVE fill (animals, scenes, objects) when no real media
    exists — not to fabricate photos of specific real people/events.
    """
    if not prompt:
        return None
    out_path = Path(out_path)
    # Content-addressed cache (audit Ticket 5): identical prompt+params never
    # regenerate — the runner's cache/ dir is persisted via actions/cache, so
    # repeated daily renders reuse yesterday's generations for free.
    key = hashlib.sha1(
        f"{prompt}|{int(width)}x{int(height)}|{seed}".encode()).hexdigest()[:20]
    cached = _GEN_CACHE_DIR / f"{key}.png"
    if cached.is_file() and cached.stat().st_size > 2000:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, out_path)
        print(f"[gen-cache] hit -> {out_path.name}", flush=True)
        return out_path
    p = _pollinations_image(prompt, out_path, width, height, seed)
    if not p:
        p = _gemini_image(prompt, out_path)
    if p:
        try:
            _GEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, cached)
        except OSError:
            pass
    return p


def _pollinations_image(prompt, out_path, width, height, seed):
    """Fetch a generated image from Pollinations.ai. None on any failure."""
    try:
        styled = (prompt.strip()
                  + ". photorealistic, editorial news photo, sharp, well lit, "
                    "no text, no watermark, no caption")
        url = (POLLINATIONS_IMG + urllib.parse.quote(styled[:480])
               + f"?width={int(width)}&height={int(height)}&nologo=true&model=flux")
        if seed is not None:
            url += f"&seed={int(seed) % (2 ** 31)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
        if not data or len(data) < 2000:        # tiny payload = error page
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        print(f"[pollinations] image -> {out_path.name} ({len(data)} bytes)",
              flush=True)
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"[pollinations] image failed: {type(e).__name__}: {e}", flush=True)
        return None


def _gemini_image(prompt: str, out_path: Path) -> "Path | None":
    """Fallback generator: a FREE Gemini image model. None when unavailable."""
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


ACCENT = (255, 221, 0)   # punchy yellow for the highlighted hot word


def _vignette(img):
    """Darken the edges so the eye lands on the center subject + text."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        [-w * 0.25, -h * 0.25, w * 1.25, h * 1.25], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(140))
    return Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), mask)


def _hot_words(words: list[str]) -> set[str]:
    """Which words to paint in the accent color. Numbers grab the most
    attention, so highlight any token with a digit; otherwise fall back
    to the single longest word."""
    def clean(w):
        return w.strip(",.!?:;\"'").lower()
    hot = {clean(w) for w in words if any(c.isdigit() for c in w)}
    if not hot and words:
        hot = {clean(max(words, key=lambda w: len(clean(w))))}
    return hot


def _fit_lines(draw, words, max_w, font_fn, *, max_lines=3, start=148, floor=64):
    """Greedy-wrap `words`, shrinking the font until it fits in max_lines.
    Returns (font, [[word, ...], ...])."""
    size = start
    lines: list[list[str]] = []
    font = font_fn(size)
    while size >= floor:
        font = font_fn(size)
        lines, cur = [], []
        for wd in words:
            if not cur or draw.textlength(" ".join(cur + [wd]), font=font) <= max_w:
                cur.append(wd)
            else:
                lines.append(cur)
                cur = [wd]
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines:
            return font, lines
        size -= 8
    return font, lines[:max_lines]


def build_thumbnail(out_path, *, title: str, hook: str | None = None,
                    bg_image=None, bg_prompt: str | None = None) -> Path | None:
    """Compose a punchy 1280x720 thumbnail: a saturated, vignetted
    story photo (an existing pinned image, else a FREE Gemini gen, else
    a dark gradient), with a big auto-fit hook in heavy-stroked caps and
    the number / key word highlighted in yellow. Returns the path, or
    None if PIL is missing / anything fails (caller just skips it)."""
    try:
        from PIL import Image, ImageDraw, ImageEnhance
    except Exception:  # noqa: BLE001
        return None
    W, H = 1280, 720
    out_path = Path(out_path)
    try:
        bg = _load_bg(bg_image)
        if bg is None and bg_prompt:
            gp = generate_image(bg_prompt, out_path.with_suffix(".bg.png"))
            bg = _load_bg(gp) if gp else None
        has_photo = bg is not None
        if bg is None:
            bg = Image.new("RGB", (W, H), (16, 18, 30))
        bg = _cover(bg, W, H)

        if has_photo:
            # Make the photo pop, then pull the edges down.
            bg = ImageEnhance.Color(bg).enhance(1.35)
            bg = ImageEnhance.Contrast(bg).enhance(1.15)
            bg = ImageEnhance.Brightness(bg).enhance(1.03)
            bg = _vignette(bg)

        # Bottom-up dark scrim so the text always reads.
        black = Image.new("RGB", (W, H), (0, 0, 0))
        scrim = Image.new("L", (1, H), 0)
        px = scrim.load()
        for y in range(H):
            px[0, y] = int(245 * (y / H) ** 1.3)
        bg = Image.composite(black, bg, scrim.resize((W, H)))

        draw = ImageDraw.Draw(bg)
        text = (hook or title or "").upper().strip().strip("?!.,")
        if text:
            words = text.split()
            font, lines = _fit_lines(draw, words, W - 110, _font)
            hot = _hot_words(words)
            space = draw.textlength(" ", font=font)
            stroke = max(8, font.size // 11)
            lh = int(font.size * 1.06)
            y = H - 64 - lh * len(lines)
            for line in lines:
                x = 56
                for wd in line:
                    key = wd.strip(",.!?:;\"'").lower()
                    fill = ACCENT if key in hot else (255, 255, 255)
                    draw.text((x, y), wd, font=font, fill=fill,
                              stroke_width=stroke, stroke_fill=(0, 0, 0))
                    x += draw.textlength(wd, font=font) + space
                y += lh

        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg.save(out_path, "JPEG", quality=90)
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"[gemini] thumbnail failed: {type(e).__name__}: {e}", flush=True)
        return None


def build_cover_frame(out_path, *, title: str, hook: str | None = None,
                      bg_image=None) -> Path | None:
    """Compose a 1080x1920 HOOK COVER for the video's first ~1.3s — the frame
    that stops the swipe and seeds the in-feed preview. Same punch as the
    thumbnail (saturated/vignetted lead image, dark scrim, huge stroked hook
    with the number/key word in yellow), centered for vertical. Returns the
    path, or None on any failure (caller just skips the cover)."""
    try:
        from PIL import Image, ImageDraw, ImageEnhance
    except Exception:  # noqa: BLE001
        return None
    W, H = 1080, 1920
    out_path = Path(out_path)
    try:
        bg = _load_bg(bg_image)
        has_photo = bg is not None
        if bg is None:
            bg = Image.new("RGB", (W, H), (14, 16, 28))
        bg = _cover(bg, W, H)
        if has_photo:
            bg = ImageEnhance.Color(bg).enhance(1.35)
            bg = ImageEnhance.Contrast(bg).enhance(1.15)
            bg = _vignette(bg)
        # Center-weighted dark scrim so the centered hook always reads.
        black = Image.new("RGB", (W, H), (0, 0, 0))
        scrim = Image.new("L", (1, H), 0)
        px = scrim.load()
        for y in range(H):
            d = abs(y - H * 0.5) / (H * 0.5)        # 0 center -> 1 edges
            px[0, y] = int(120 + 70 * (1.0 - d))    # darker in the middle band
        bg = Image.composite(black, bg, scrim.resize((W, H)))

        draw = ImageDraw.Draw(bg)
        text = (hook or title or "").upper().strip().strip("?!.,")
        if text:
            words = text.split()
            font, lines = _fit_lines(draw, words, W - 120, _font,
                                     max_lines=4, start=180, floor=78)
            hot = _hot_words(words)
            space = draw.textlength(" ", font=font)
            stroke = max(10, font.size // 10)
            lh = int(font.size * 1.08)
            y = int(H * 0.5) - lh * len(lines) // 2   # vertically centered
            for line in lines:
                lw = sum(draw.textlength(w, font=font) for w in line) \
                    + space * (len(line) - 1)
                x = (W - lw) // 2                     # horizontally centered
                for wd in line:
                    key = wd.strip(",.!?:;\"'").lower()
                    fill = ACCENT if key in hot else (255, 255, 255)
                    draw.text((x, y), wd, font=font, fill=fill,
                              stroke_width=stroke, stroke_fill=(0, 0, 0))
                    x += draw.textlength(wd, font=font) + space
                y += lh

        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg.save(out_path, "JPEG", quality=90)
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"[gemini] cover frame failed: {type(e).__name__}: {e}", flush=True)
        return None
