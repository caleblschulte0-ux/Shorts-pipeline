"""AI-generated, reskinnable sprites for the bottom-half games.

Given a story's hero subject (tortoise, backhoe, warship, duck, goat…),
generate a clean side-view cartoon sprite on a transparent background — so a
game's protagonist can BE the story's subject instead of a hardcoded critter or
car. This is what makes reskinning OPEN-ENDED: no sprite list to maintain, any
noun works.

Pollinations.ai (free, keyless) generates the image on a solid-white background;
we cut the white to alpha with PIL+numpy (no rembg dependency). Best-effort:
returns None on any failure so callers fall back to the theme's default sprite.
Cached on disk by subject so a re-render is instant.
"""
from __future__ import annotations

import io
import re
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path("/tmp/game_sprites")
_POLL = "https://image.pollinations.ai/prompt/"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40] or "x"


def subject_sprite(subject: str, *, seed: int | None = None,
                   timeout: float = 25.0):
    """Return a Path to a transparent-PNG cartoon sprite of `subject`, or None.

    Cached by subject. Never raises.
    """
    if not subject or not subject.strip():
        return None
    try:
        from PIL import Image
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{_slug(subject)}.png"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    try:
        prompt = (f"a single {subject}, flat 2D cartoon sticker, side view, "
                  "full body, thick dark outline, bright flat colors, solid "
                  "pure white background, centered, no text, no shadow")
        url = (_POLL + urllib.parse.quote(prompt[:400])
               + "?width=512&height=512&nologo=true&model=flux")
        if seed is not None:
            url += f"&seed={int(seed) % (2 ** 31)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=timeout).read()
        if not data or len(data) < 2000:
            return None
        img = Image.open(io.BytesIO(data)).convert("RGB")
        import numpy as np
        a = np.asarray(img).astype(np.int16)
        white = (a[:, :, 0] > 238) & (a[:, :, 1] > 238) & (a[:, :, 2] > 238)
        rgba = np.dstack([np.asarray(img), (~white * 255).astype(np.uint8)])
        out = Image.fromarray(rgba, "RGBA")
        bbox = out.getbbox()
        if bbox:
            out = out.crop(bbox)
        out.save(dest)
        print(f"[sprite] {subject!r} -> {dest.name} {out.size}", flush=True)
        return dest
    except Exception as e:  # noqa: BLE001
        print(f"[sprite] {subject!r} failed: {type(e).__name__}: {e}", flush=True)
        return None


def load_sprite(path, target_h: int):
    """Load a sprite PNG and scale to target height (keeps aspect). None on fail."""
    if not path:
        return None
    try:
        from PIL import Image
        im = Image.open(path).convert("RGBA")
        if im.height != target_h:
            w = max(1, int(im.width * target_h / im.height))
            im = im.resize((w, target_h), Image.LANCZOS)
        return im
    except Exception:  # noqa: BLE001
        return None
