"""Crisp building artwork, drawn with Pillow.

geq (ffmpeg) can only flat-fill and blur, which makes structures look like
programmer-art. This module draws each building (cabin, barn ...) with real
anti-aliased polygons, log/plank texture, a snow-laden roof, framed glowing
windows, a door, a chimney with smoke, and a soft warm glow + light pooled on
the snow. Output is one full-canvas transparent RGBA PNG per building that the
scene compositor drops into the foreground plate.

Pillow is imported lazily by the caller so the rest of the pipeline doesn't
depend on it.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SS = 4                                  # supersample factor for the solid structure


def _rgb(hex_str: str) -> tuple[int, int, int]:
    c = hex_str.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _scale(c: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _geo(b, w: int, h: int) -> dict:
    cx = b.x * w
    by = b.base * h
    half = b.w / 2
    return dict(
        cx=cx, by=by, half=half, bh=b.bh, rh=b.rh,
        roof_half=half + b.w * b.eaves,
        top_y=by - b.bh - b.rh,
        mid_y=by - b.bh,
        chcx=cx + half * 0.52,
        chw=b.w * 0.13,
        chy_top=by - b.bh - b.rh * 1.18,
        chy_bot=by - b.bh - b.rh * 0.45,
    )


def render_building(b, smoke_color: str, w: int, h: int, out: Path) -> None:
    g = _geo(b, w, h)
    cx, by, half, bh, rh = g["cx"], g["by"], g["half"], g["bh"], g["rh"]
    mid_y, top_y, roof_half = g["mid_y"], g["top_y"], g["roof_half"]
    wood = _rgb(b.wood)
    roof = _rgb(b.roof)
    warm = _rgb(b.win_color)
    pane = (min(255, warm[0] + 25), min(255, warm[1] + 18), min(255, warm[2] + 8))
    snow = (236, 242, 252, 255)
    frame = (28, 20, 13, 255)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # ---- warm glow + light pooled on the snow (behind the structure) ----
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    def blob(px, py, rx, ry, a):
        gd.ellipse([px - rx, py - ry, px + rx, py + ry], fill=(*warm, a))

    for dx, dy, wf, hf, _ in b.windows:
        blob(cx + dx * b.w, mid_y + dy * bh, wf * b.w * 1.7, hf * bh * 1.7, 120)
    if b.door:
        dx, dy, wf, hf = b.door
        blob(cx + dx * b.w, mid_y + dy * bh, wf * b.w * 1.7, hf * bh * 1.3, 130)
    if b.spill:
        blob(cx, by + bh * 0.07, b.w * 1.15, bh * 0.30, 110)
    glow = glow.filter(ImageFilter.GaussianBlur(b.w * 0.09))
    canvas = Image.alpha_composite(canvas, glow)

    # ---- the solid structure, drawn supersampled then downscaled ----
    tx0 = int(cx - roof_half - 14)
    ty0 = int(min(top_y, g["chy_top"]) - 14)
    tx1 = int(cx + roof_half + 14)
    ty1 = int(by + bh * 0.30)
    tw, th = tx1 - tx0, ty1 - ty0
    tile = Image.new("RGBA", (tw * SS, th * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)

    def X(x):
        return (x - tx0) * SS

    def Y(y):
        return (y - ty0) * SS

    lw = max(1, int(SS * 1.3))

    # walls
    d.rectangle([X(cx - half), Y(mid_y), X(cx + half), Y(by)], fill=(*wood, 255))
    # horizontal log courses
    step = bh * 0.12
    yy = mid_y + step
    while yy < by - 1:
        d.line([X(cx - half), Y(yy), X(cx + half), Y(yy)], fill=(*_scale(wood, 0.74), 255), width=lw)
        yy += step
    # soft shadow just under the eave (depth)
    for i in range(int(bh * 0.10)):
        a = int(70 * (1 - i / max(1, bh * 0.10)))
        d.line([X(cx - half), Y(mid_y + i), X(cx + half), Y(mid_y + i)], fill=(0, 0, 0, a), width=SS)
    # shaded gable end (light comes from the right)
    shade = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle([X(cx - half), Y(mid_y), X(cx - half * 0.45), Y(by)], fill=(0, 0, 0, 45))
    shade = shade.filter(ImageFilter.GaussianBlur(SS * 6))
    tile = Image.alpha_composite(tile, shade)
    d = ImageDraw.Draw(tile)

    # chimney (behind roof peak)
    if b.chimney:
        brick = _rgb("5a4a44")
        d.rectangle([X(g["chcx"] - g["chw"] / 2), Y(g["chy_top"]),
                     X(g["chcx"] + g["chw"] / 2), Y(g["chy_bot"])], fill=(*brick, 255))

    # roof
    d.polygon([(X(cx), Y(top_y)), (X(cx - roof_half), Y(mid_y)), (X(cx + roof_half), Y(mid_y))],
              fill=(*roof, 255))

    # snow blanket on the roof, with a scalloped overhanging lip
    d.polygon([(X(cx), Y(top_y - 5)), (X(cx - roof_half - 3), Y(mid_y + 1)),
               (X(cx + roof_half + 3), Y(mid_y + 1))], fill=snow)
    nb = 9
    lip = b.w * 0.05
    for i in range(nb + 1):
        ex = cx - roof_half + (i / nb) * 2 * roof_half
        d.ellipse([X(ex) - lip * SS, Y(mid_y + 1) - lip * SS * 0.7,
                   X(ex) + lip * SS, Y(mid_y + 1) + lip * SS], fill=snow)
    if b.chimney:
        d.ellipse([X(g["chcx"] - g["chw"] / 2 - 3), Y(g["chy_top"]) - SS * 6,
                   X(g["chcx"] + g["chw"] / 2 + 3), Y(g["chy_top"]) + SS * 5], fill=snow)

    # windows + door
    def opening(wx, wy, hw, hh, style):
        d.rectangle([X(wx - hw), Y(wy - hh), X(wx + hw), Y(wy + hh)], fill=frame)
        ins = max(SS * 2.0, hw * SS * 0.14)
        d.rectangle([X(wx - hw) + ins, Y(wy - hh) + ins, X(wx + hw) - ins, Y(wy + hh) - ins],
                    fill=(*pane, 255))
        # brighten the centre for a lit-from-inside feel
        d.ellipse([X(wx) - hw * SS * 0.62, Y(wy) - hh * SS * 0.62,
                   X(wx) + hw * SS * 0.62, Y(wy) + hh * SS * 0.62],
                  fill=(min(255, pane[0] + 20), min(255, pane[1] + 20), min(255, pane[2] + 30), 150))
        if style in ("cross", "vert"):
            d.line([X(wx), Y(wy - hh) + ins, X(wx), Y(wy + hh) - ins], fill=frame, width=lw)
        if style == "cross":
            d.line([X(wx - hw) + ins, Y(wy), X(wx + hw) - ins, Y(wy)], fill=frame, width=lw)

    for dx, dy, wf, hf, style in b.windows:
        wx, wy = cx + dx * b.w, mid_y + dy * bh
        hw, hh = wf * b.w / 2, hf * bh / 2
        opening(wx, wy, hw, hh, style)
        if dy >= 0:                                   # snowy sill (not the gable window)
            d.ellipse([X(wx - hw * 1.2), Y(wy + hh) - SS * 2,
                       X(wx + hw * 1.2), Y(wy + hh) + SS * 6], fill=snow)
    if b.door:
        dx, dy, wf, hf = b.door
        opening(cx + dx * b.w, mid_y + dy * bh, wf * b.w / 2, hf * bh / 2, "vert")

    tile = tile.resize((tw, th), Image.LANCZOS)
    canvas.alpha_composite(tile, (tx0, ty0))

    # ---- snow piled at the base, in front of the walls ----
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base)
    bd.ellipse([cx - half * 1.25, by - bh * 0.05, cx + half * 1.25, by + bh * 0.22], fill=snow)
    base = base.filter(ImageFilter.GaussianBlur(3))
    canvas = Image.alpha_composite(canvas, base)

    # ---- chimney smoke ----
    if b.chimney and b.smoke:
        sm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        smd = ImageDraw.Draw(sm)
        sc = _rgb(smoke_color)
        sx, sy = g["chcx"], g["chy_top"]
        for k in range(9):
            yy = sy - 2 - k * (bh * 0.11)
            rad = 5 + k * 3.0
            a = max(0, 64 - k * 7)
            off = math.sin(k * 0.9) * (b.w * 0.05)
            smd.ellipse([sx + off - rad, yy - rad, sx + off + rad, yy + rad], fill=(*sc, a))
        sm = sm.filter(ImageFilter.GaussianBlur(6))
        canvas = Image.alpha_composite(canvas, sm)

    canvas.save(out)
