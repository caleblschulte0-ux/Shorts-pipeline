#!/usr/bin/env python3
"""Reddit post card generator — the genre's signature visual.

Renders an authentic-looking Reddit post card (subreddit, avatar, username,
title, upvote / comment counts) as a transparent PNG sized to overlay on a
1080-wide vertical video. Shown over the gameplay for the first few seconds
while the TTS reads the title, then it fades and the captions take over.

    from reddit_card import build_card
    build_card(out="card.png", subreddit="AmItheAsshole",
               username="throwaway_bride22", title="AITA for ...",
               upvotes="24.5k", comments="3.1k")

Pure Pillow, no network. Fonts fall back to DejaVu (bundled on CI runners).
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Reddit palette
ORANGE = (255, 69, 0)       # upvote / brand
CARD_BG = (255, 255, 255)
TITLE_CLR = (26, 26, 27)
META_CLR = (124, 124, 124)
ICON_CLR = (135, 138, 140)
VERIFIED = (0, 121, 211)

_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    str(Path(__file__).resolve().parent / "assets" / "fonts"),
]


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    names = (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for d in _FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def build_card(out: str | Path, *, subreddit: str, username: str, title: str,
               upvotes: str = "24.5k", comments: str = "3.1k",
               width: int = 980, avatar_seed: int = 0) -> Path:
    """Render the card to `out` (transparent PNG). Returns the path."""
    pad = 40
    inner = width - pad * 2
    f_sub = _font(True, 34)
    f_meta = _font(False, 28)
    f_title = _font(True, 46)
    f_stat = _font(True, 32)

    # measure title
    tmp = Image.new("RGBA", (10, 10))
    d0 = ImageDraw.Draw(tmp)
    title_lines = _wrap(d0, title, f_title, inner)
    title_lh = f_title.getbbox("Ay")[3] + 12

    header_h = 92
    title_h = len(title_lines) * title_lh
    footer_h = 78
    card_h = pad + header_h + 18 + title_h + 20 + footer_h + pad

    shadow_pad = 30
    W = width + shadow_pad * 2
    H = card_h + shadow_pad * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # soft shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    _rounded(ds, (shadow_pad, shadow_pad + 6, shadow_pad + width,
                  shadow_pad + card_h + 6), 26, (0, 0, 0, 90))
    from PIL import ImageFilter
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(sh)

    ox, oy = shadow_pad, shadow_pad
    _rounded(d, (ox, oy, ox + width, oy + card_h), 26, CARD_BG)

    # header: avatar + subreddit + username line
    ax, ay = ox + pad, oy + pad
    av_d = 68
    palette = [(255, 69, 0), (0, 121, 211), (70, 210, 120), (170, 100, 220),
               (240, 160, 40)]
    av_clr = palette[avatar_seed % len(palette)]
    d.ellipse((ax, ay, ax + av_d, ay + av_d), fill=av_clr)
    # little snoo-ish head
    d.ellipse((ax + 20, ay + 22, ax + av_d - 20, ay + av_d - 14),
              fill=(255, 255, 255))
    d.ellipse((ax + 26, ay + 30, ax + 33, ay + 37), fill=av_clr)
    d.ellipse((ax + av_d - 33, ay + 30, ax + av_d - 26, ay + 37), fill=av_clr)

    tx = ax + av_d + 20
    d.text((tx, ay + 2), f"r/{subreddit}", font=f_sub, fill=TITLE_CLR)
    d.text((tx, ay + 44), f"u/{username} · 5h", font=f_meta, fill=META_CLR)

    # "Join" pill (brand)
    join_w = 120
    jx = ox + width - pad - join_w
    _rounded(d, (jx, ay + 6, jx + join_w, ay + 6 + 56), 28, ORANGE)
    jt = "Join"
    jtw = d.textlength(jt, font=f_stat)
    d.text((jx + (join_w - jtw) / 2, ay + 18), jt, font=f_stat,
           fill=(255, 255, 255))

    # title
    ty = ay + header_h + 6
    for ln in title_lines:
        d.text((ox + pad, ty), ln, font=f_title, fill=TITLE_CLR)
        ty += title_lh

    # footer: upvote arrow + count, comment icon + count
    fy = ty + 24
    cx = ox + pad
    # upvote triangle
    d.polygon([(cx + 4, fy + 20), (cx + 26, fy + 20), (cx + 15, fy + 2)],
              fill=ORANGE)
    d.text((cx + 40, fy - 4), upvotes, font=f_stat, fill=TITLE_CLR)
    cx += 40 + int(d.textlength(upvotes, font=f_stat)) + 60
    # comment bubble
    _rounded(d, (cx, fy - 2, cx + 30, fy + 22), 8, None)
    d.rounded_rectangle((cx, fy - 2, cx + 30, fy + 22), radius=8,
                        outline=ICON_CLR, width=4)
    d.polygon([(cx + 6, fy + 22), (cx + 16, fy + 22), (cx + 6, fy + 32)],
              fill=ICON_CLR)
    d.text((cx + 44, fy - 4), comments, font=f_stat, fill=META_CLR)

    img.save(str(out))
    return Path(out)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "reddit_card_sample.png"
    build_card(
        out=out, subreddit="AmItheAsshole", username="throwaway_bride22",
        title="AITA for reading my sister's texts out loud at my wedding "
              "after I caught what she did?",
        upvotes="41.2k", comments="5.8k", avatar_seed=1)
    print("wrote", out)
