"""The last-resort illustration for a story beat: the thing it names, as an
icon on the channel's ground. Offline, deterministic, instant.

Trending's reddit_story renders one top-half panel per beat. On 2026-09-25
every source of those panels was down at once: ChatGPT's media worker had
produced nothing for four days (`state/chatgpt_tasks/*/media.json`:
FAILED_NO_ARTIFACT), Pollinations answered 429 or timed out on nearly every
call, and Gemini's free tier was exhausted. What was left was keyword stock
for fictional lines ("sealed box", "my boss stared"), which the relevance
check rightly dropped — and five stories shipped as bare gameplay under
captions, every one blocked by the showrunner: "the story is told but never
shown".

An icon of the named object is a modest picture, but it is the RIGHT
picture or none at all: it is only drawn when the icon library maps the
beat's own words to an object, and the panel still goes through
`shared/shot_relevance` like any other image, which drops it if the object
does not fit the line. It never invents a scene, a person or a place.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def icon_panel(texts, dest, size=(1080, 1080), accent: str = "gold"):
    """A panel for the first of `texts` the icon library can depict, written
    to `dest`. Returns the path, or None when none of them maps to an icon.
    Never raises."""
    try:
        from PIL import Image, ImageDraw, ImageFilter

        from data_learning import icons
        from shared import look
    except Exception:  # noqa: BLE001
        return None
    src = None
    for t in texts or []:
        t = str(t or "").strip()
        if not t:
            continue
        try:
            src = icons.icon_png(t, 512)
        except Exception:  # noqa: BLE001
            src = None
        if src:
            break
    if not src:
        return None
    try:
        w, h = int(size[0]), int(size[1])
        seed = int(hashlib.sha1(str(src).encode()).hexdigest()[:6], 16)
        ground = look.ground(w, h, seed=seed, stars=60).convert("RGBA")
        hi = look.ACCENTS.get(accent, look.ACCENTS[look.DEFAULT_ACCENT])[0]
        # a soft pool of the accent behind the object, so it sits in light
        glow = Image.new("L", (w, h), 0)
        r = int(min(w, h) * 0.34)
        ImageDraw.Draw(glow).ellipse(
            [w // 2 - r, int(h * 0.52) - r, w // 2 + r, int(h * 0.52) + r],
            fill=120)
        glow = glow.filter(ImageFilter.GaussianBlur(min(w, h) // 8))
        tint = Image.new("RGBA", (w, h), hi + (255,))
        tint.putalpha(glow.point(lambda v: int(v * 0.55)))
        ground.alpha_composite(tint)
        icon = Image.open(src).convert("RGBA")
        side = int(min(w, h) * 0.58)
        icon = icon.resize((side, side), Image.Resampling.LANCZOS)
        # a grounded shadow under it
        shadow = Image.new("L", (w, h), 0)
        sw = int(side * 0.62)
        sy = int(h * 0.52 + side * 0.46)
        ImageDraw.Draw(shadow).ellipse(
            [w // 2 - sw // 2, sy - 22, w // 2 + sw // 2, sy + 22], fill=150)
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        dark = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        dark.putalpha(shadow)
        ground.alpha_composite(dark)
        ground.alpha_composite(icon, (w // 2 - side // 2,
                                      int(h * 0.52) - side // 2))
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        ground.convert("RGB").save(dest, "PNG")
        return dest
    except Exception:  # noqa: BLE001
        return None
