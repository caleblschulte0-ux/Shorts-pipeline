"""Crisp building artwork, drawn with Pillow in a 3/4 (oblique) view.

A flat, face-on box always reads as a sticker. So each building is drawn with
real dimension: a lit front face, a receding shadowed side, two angled roof
planes meeting at a ridge, snow with shading, icicles, a chimney, glowing
framed windows, warm light pooled on the snow, and a soft shadow cast on the
ground. Everything is drawn supersampled and downscaled for clean edges.

Output is one full-canvas transparent RGBA PNG per building that the scene
compositor drops into the foreground plate. Pillow is imported lazily by the
caller so the rest of the pipeline doesn't depend on it.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SS = 4                                  # supersample factor


def _rgb(hex_str: str) -> tuple[int, int, int]:
    c = hex_str.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(c, f, towards=(0, 0, 0)):
    """Blend colour c toward `towards` by (1-f); f=1 keeps c, f=0 -> towards."""
    return tuple(max(0, min(255, int(c[i] * f + towards[i] * (1 - f)))) for i in range(3))


def render_building(b, smoke_color: str, w: int, h: int, out: Path) -> None:
    cx = b.x * w
    by = b.base * h
    W = float(b.w)
    H = float(b.bh)
    R = float(b.rh)
    half = W / 2.0
    ov = W * 0.10                                  # roof overhang
    dvx, dvy = W * 0.42, -W * 0.24                 # depth vector (recede right + up)

    wood = _rgb(b.wood)
    roof = _rgb(b.roof)
    warm = _rgb(b.win_color)
    snow = (238, 243, 252)
    snow_sh = (205, 216, 235)                      # shaded snow (blue-ish)
    frame = (26, 19, 12)

    front_wall = _mix(wood, 1.5)                    # lit front (lift it off black)
    side_wall = _mix(wood, 0.80)                   # shadowed side
    gable_wall = _mix(wood, 1.25)
    roof_r = _mix(roof, 1.0)                        # right plane (toward light)
    roof_l = _mix(roof, 0.66)                       # left plane (shadow)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # ---------- cast shadow on the snow ----------
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(
        [cx - half * 1.5, by - H * 0.04, cx + half * 1.5 + dvx, by + H * 0.16],
        fill=(20, 26, 48, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(W * 0.06))
    canvas = Image.alpha_composite(canvas, sh)

    # ---------- warm glow behind the structure ----------
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    def blob(px, py, rx, ry, a):
        gd.ellipse([px - rx, py - ry, px + rx, py + ry], fill=(*warm, a))

    for dx, dy, wf, hf, _ in b.windows:
        blob(cx + dx * W, (by - H) + dy * H, wf * W * 2.0, hf * H * 2.0, 150)
    if b.door:
        dx, dy, wf, hf = b.door
        dxw, dyw = cx + dx * W, (by - H) + dy * H
        blob(dxw, dyw, wf * W * 2.0, hf * H * 1.4, 160)
        blob(dxw - wf * W * 1.4, dyw - hf * H * 0.3, W * 0.16, W * 0.16, 150)   # lantern halo
    if b.spill:
        blob(cx + dvx * 0.3, by + H * 0.05, W * 1.25, H * 0.32, 150)            # warm light on snow
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.08))
    canvas = Image.alpha_composite(canvas, glow)

    # ---------- the solid structure (supersampled tile) ----------
    minx = cx - half - ov - 6
    maxx = cx + half + ov + dvx + 6
    miny = (by - H - R) + dvy - 10
    maxy = by + 6
    tw, th = int(maxx - minx), int(maxy - miny)
    tile = Image.new("RGBA", (tw * SS, th * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)

    def P(x, y):
        return ((x - minx) * SS, (y - miny) * SS)

    def poly(pts, fill):
        d.polygon([P(*p) for p in pts], fill=(*fill, 255) if len(fill) == 3 else fill)

    def line(p0, p1, fill, wpx):
        d.line([P(*p0), P(*p1)], fill=(*fill, 255), width=max(1, int(wpx * SS)))

    # key points
    FBL, FBR = (cx - half, by), (cx + half, by)
    FTL, FTR = (cx - half, by - H), (cx + half, by - H)
    FA = (cx, by - H - R)                                   # front gable apex
    BA = (FA[0] + dvx, FA[1] + dvy)                         # back ridge apex
    eL = (cx - half - ov, by - H + ov * 0.4)               # front eaves (overhang)
    eR = (cx + half + ov, by - H + ov * 0.4)
    eRb = (eR[0] + dvx, eR[1] + dvy)                        # right eave, back
    eLb = (eL[0] + dvx, eL[1] + dvy)

    # left roof plane (mostly hidden, drawn first)
    poly([FA, BA, eLb, eL], roof_l)
    # right side wall (shadowed), receding
    poly([FTR, (FTR[0] + dvx, FTR[1] + dvy), (FBR[0] + dvx, FBR[1] + dvy), FBR], side_wall)
    # right roof plane (lit) + snow
    poly([FA, BA, eRb, eR], roof_r)
    # front wall + front gable (lit)
    poly([FTL, FTR, FBR, FBL], front_wall)
    poly([FTL, FTR, FA], gable_wall)

    # log courses on the front wall
    lw = max(1, int(SS * 1.1))
    step = H * 0.11
    yy = (by - H) + step
    while yy < by - 1:
        line((cx - half, yy), (cx + half, yy), _mix(front_wall, 0.78), 1.1)
        yy += step
    # corner post + eave shadow for depth
    line(FTR, FBR, _mix(wood, 0.5), 1.6)
    for i in range(int(H * 0.08)):
        a = int(70 * (1 - i / max(1, H * 0.08)))
        d.line([P(cx - half, by - H + i)[0], P(cx - half, by - H + i)[1],
                P(cx + half, by - H + i)[0], P(cx + half, by - H + i)[1]],
               fill=(0, 0, 0, a), width=SS)

    # chimney (3D-ish: front + side), near the back of the ridge
    if b.chimney:
        chx = cx + half * 0.30
        chw = W * 0.12
        cht = (by - H - R * 0.55)
        chtop = (by - H - R * 1.05)
        cf = _rgb("5d4b43")
        cs = _mix(cf, 0.6)
        poly([(chx + chw, chtop), (chx + chw + dvx * 0.18, chtop + dvy * 0.18),
              (chx + chw + dvx * 0.18, cht + dvy * 0.18), (chx + chw, cht)], cs)
        poly([(chx - chw, chtop), (chx + chw, chtop), (chx + chw, cht), (chx - chw, cht)], cf)

    # ---------- snow on the roof ----------
    poly(_band(FA, BA, eRb, eR, top=0.0, bottom=0.82), snow)   # blanket on the right plane
    poly(_band(FA, BA, eLb, eL, 0.0, 0.82), snow_sh)          # left plane snow (shaded)
    # ridge highlight
    line(FA, BA, snow, 2.2)
    # scalloped overhanging lip along the right eave
    lip = W * 0.045
    for i in range(7):
        t = i / 6
        ex = eR[0] + t * (eRb[0] - eR[0])
        ey = eR[1] + t * (eRb[1] - eR[1])
        d.ellipse([P(ex, ey)[0] - lip * SS, P(ex, ey)[1] - lip * SS * 0.6,
                   P(ex, ey)[0] + lip * SS, P(ex, ey)[1] + lip * SS], fill=(*snow, 255))
    # snow piled along the front gable eaves (the two top edges of the gable)
    line(FTL, FA, snow, 2.4)
    line(FTR, FA, snow, 2.4)
    if b.chimney:
        chx = cx + half * 0.30
        chw = W * 0.12
        d.ellipse([P(chx - chw, by - H - R * 1.05)[0], P(chx - chw, by - H - R * 1.05)[1] - SS * 6,
                   P(chx + chw + dvx * 0.18, by - H - R * 1.05)[0], P(chx + chw, by - H - R * 1.05)[1] + SS * 4],
                  fill=(*snow, 255))

    # icicles hanging from the front eave (thin, varied)
    for i in range(7):
        ix = eL[0] + (i + 0.5) / 7 * (eR[0] - eL[0])
        iy = eL[1] + (i + 0.5) / 7 * (eR[1] - eL[1])
        ln = W * (0.022 + 0.020 * ((i * 37) % 5) / 5)
        poly([(ix - 2, iy), (ix + 2, iy), (ix, iy + ln)], (222, 234, 250))

    # ---------- windows + door on the front face ----------
    def opening(wx, wy, hw, hh, style):
        if style == "round":                           # little attic porthole
            d.ellipse([P(wx - hw, wy - hh)[0], P(wx - hw, wy - hh)[1],
                       P(wx + hw, wy + hh)[0], P(wx + hw, wy + hh)[1]], fill=(*frame, 255))
            ins = max(SS * 1.6, hw * SS * 0.22)
            d.ellipse([P(wx - hw, wy - hh)[0] + ins, P(wx - hw, wy - hh)[1] + ins,
                       P(wx + hw, wy + hh)[0] - ins, P(wx + hw, wy + hh)[1] - ins], fill=(255, 208, 128, 255))
            d.line([P(wx, wy - hh)[0], P(wx, wy - hh)[1] + ins,
                    P(wx, wy + hh)[0], P(wx, wy + hh)[1] - ins], fill=(*frame, 255), width=lw)
            d.line([P(wx - hw, wy)[0] + ins, P(wx - hw, wy)[1],
                    P(wx + hw, wy)[0] - ins, P(wx + hw, wy)[1]], fill=(*frame, 255), width=lw)
            return
        d.rectangle([P(wx - hw, wy - hh)[0], P(wx - hw, wy - hh)[1],
                     P(wx + hw, wy + hh)[0], P(wx + hw, wy + hh)[1]], fill=(*frame, 255))
        ins = max(SS * 2.0, hw * SS * 0.16)
        pane = (255, 201, 120)                         # warm amber glass
        d.rectangle([P(wx - hw, wy - hh)[0] + ins, P(wx - hw, wy - hh)[1] + ins,
                     P(wx + hw, wy + hh)[0] - ins, P(wx + hw, wy + hh)[1] - ins], fill=(*pane, 255))
        d.ellipse([P(wx, wy)[0] - hw * SS * 0.66, P(wx, wy)[1] - hh * SS * 0.66,
                   P(wx, wy)[0] + hw * SS * 0.66, P(wx, wy)[1] + hh * SS * 0.66],
                  fill=(255, 242, 205, 180))           # bright lit-from-inside centre
        if style in ("cross", "vert"):
            d.line([P(wx, wy - hh)[0], P(wx, wy - hh)[1] + ins,
                    P(wx, wy + hh)[0], P(wx, wy + hh)[1] - ins], fill=(*frame, 255), width=lw)
        if style == "cross":
            d.line([P(wx - hw, wy)[0] + ins, P(wx - hw, wy)[1],
                    P(wx + hw, wy)[0] - ins, P(wx + hw, wy)[1]], fill=(*frame, 255), width=lw)

    for dx, dy, wf, hf, style in b.windows:
        wx, wy = cx + dx * W, (by - H) + dy * H
        hw, hh = wf * W / 2, hf * H / 2
        opening(wx, wy, hw, hh, style)
        if dy >= 0:
            d.ellipse([P(wx - hw * 1.2, wy + hh)[0], P(wx - hw * 1.2, wy + hh)[1] - SS * 2,
                       P(wx + hw * 1.2, wy + hh)[0], P(wx + hw * 1.2, wy + hh)[1] + SS * 6],
                      fill=(*snow, 255))
    if b.door:
        dx, dy, wf, hf = b.door
        wx, wy = cx + dx * W, (by - H) + dy * H
        hw, hh = wf * W / 2, hf * H / 2
        # door slab (dark wood) with a warm transom window and a knob
        d.rectangle([P(wx - hw, wy - hh)[0], P(wx - hw, wy - hh)[1],
                     P(wx + hw, wy + hh)[0], P(wx + hw, wy + hh)[1]], fill=(*_mix(wood, 0.55), 255))
        d.rectangle([P(wx - hw * 0.7, wy - hh * 0.85)[0], P(wx - hw * 0.7, wy - hh * 0.85)[1],
                     P(wx + hw * 0.7, wy - hh * 0.35)[0], P(wx + hw * 0.7, wy - hh * 0.35)[1]],
                    fill=(255, 214, 138, 255))
        d.ellipse([P(wx + hw * 0.5, wy + hh * 0.1)[0] - SS * 2, P(wx + hw * 0.5, wy + hh * 0.1)[1] - SS * 2,
                   P(wx + hw * 0.5, wy + hh * 0.1)[0] + SS * 2, P(wx + hw * 0.5, wy + hh * 0.1)[1] + SS * 2],
                  fill=(245, 220, 150, 255))
        # a little lantern glowing beside the door
        lx, ly = wx - hw * 1.4, wy - hh * 0.3
        lr = W * 0.022
        d.rectangle([P(lx - lr, ly - lr)[0], P(lx - lr, ly - lr)[1],
                     P(lx + lr, ly + lr)[0], P(lx + lr, ly + lr)[1]], fill=(*frame, 255))
        d.rectangle([P(lx - lr * 0.6, ly - lr * 0.6)[0], P(lx - lr * 0.6, ly - lr * 0.6)[1],
                     P(lx + lr * 0.6, ly + lr * 0.6)[0], P(lx + lr * 0.6, ly + lr * 0.6)[1]],
                    fill=(255, 226, 158, 255))

    tile = tile.resize((tw, th), Image.LANCZOS)
    canvas.alpha_composite(tile, (int(minx), int(miny)))

    # ---------- snow drifted against the base of the walls ----------
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(base).ellipse(
        [cx - half * 1.2, by - H * 0.03, cx + half * 1.2 + dvx * 0.5, by + H * 0.10],
        fill=(*snow, 165))
    base = base.filter(ImageFilter.GaussianBlur(8))
    canvas = Image.alpha_composite(canvas, base)

    # ---------- chimney smoke ----------
    if b.chimney and b.smoke:
        sm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        smd = ImageDraw.Draw(sm)
        sc = _rgb(smoke_color)
        sx, sy = cx + half * 0.30, by - H - R * 1.05
        for k in range(9):
            yy = sy - 2 - k * (H * 0.11)
            rad = 5 + k * 3.0
            a = max(0, 60 - k * 7)
            off = math.sin(k * 0.9) * (W * 0.05)
            smd.ellipse([sx + off - rad, yy - rad, sx + off + rad, yy + rad], fill=(*sc, a))
        sm = sm.filter(ImageFilter.GaussianBlur(6))
        canvas = Image.alpha_composite(canvas, sm)

    canvas.save(out)


def render_pond(out: Path, w: int, h: int, cxf: float, cyf: float,
                pw: int, ph: int, moon_xf: float = 0.7) -> None:
    """A frozen lake: smooth ice with a snowy rim, a moonlight streak and skate marks.
    Drawn supersampled so the ellipse edges stay clean."""
    S = 3
    cx, cy = cxf * w, cyf * h
    x0 = int(cx - pw / 2 - 16); y0 = int(cy - ph / 2 - 14)
    x1 = int(cx + pw / 2 + 16); y1 = int(cy + ph / 2 + 14)
    tw, th = x1 - x0, y1 - y0
    tile = Image.new("RGBA", (tw * S, th * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)

    def E(ax, ay, bx, by, fill):
        d.ellipse([(ax - x0) * S, (ay - y0) * S, (bx - x0) * S, (by - y0) * S], fill=fill)

    # snowy bank, then ice (a touch lighter toward the near/front edge)
    E(cx - pw / 2 - 12, cy - ph / 2 - 9, cx + pw / 2 + 12, cy + ph / 2 + 11, (224, 233, 246, 255))
    E(cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2, (78, 100, 138, 255))
    E(cx - pw * 0.46, cy - ph * 0.30, cx + pw * 0.46, cy + ph * 0.50, (104, 126, 162, 255))
    E(cx - pw * 0.34, cy - ph * 0.05, cx + pw * 0.34, cy + ph * 0.46, (126, 148, 184, 220))
    # etched skate marks (faint figure-8 arcs)
    for k, (rxf, ryf, yo) in enumerate([(0.30, 0.22, -0.04), (0.24, 0.16, 0.12)]):
        d.ellipse([(cx - pw * rxf - x0) * S, (cy + ph * yo - ph * ryf - y0) * S,
                   (cx + pw * rxf - x0) * S, (cy + ph * yo + ph * ryf - y0) * S],
                  outline=(150, 170, 205, 130), width=S)
    tile = tile.resize((tw, th), Image.LANCZOS)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.paste(tile, (x0, y0), tile)
    img = img.filter(ImageFilter.GaussianBlur(1))
    # moonlight reflection streak
    refl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mx = cx + (moon_xf - 0.5) * pw * 0.5
    ImageDraw.Draw(refl).ellipse([mx - pw * 0.045, cy - ph * 0.36, mx + pw * 0.045, cy + ph * 0.46],
                                 fill=(232, 240, 252, 140))
    refl = refl.filter(ImageFilter.GaussianBlur(int(ph * 0.06) + 4))
    img = Image.alpha_composite(img, refl)
    img.save(out)


def render_skater(out: Path, size: int, color: str, scarf: str = "b8443c") -> None:
    """A solid skater silhouette — leaning into a glide, one leg trailing, a flying scarf."""
    S = 4
    c = (*_rgb(color), 255)
    sc = (*_rgb(scarf), 255)
    img = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def pt(fx, fy):
        return (fx * size * S, fy * size * S)

    def limb(p0, p1, wf):
        d.line([pt(*p0), pt(*p1)], fill=c, width=max(2, int(wf * size * S)))
        d.ellipse([pt(*p1)[0] - wf * size * S / 2, pt(*p1)[1] - wf * size * S / 2,
                   pt(*p1)[0] + wf * size * S / 2, pt(*p1)[1] + wf * size * S / 2], fill=c)

    # back (push) leg and front (glide) leg, with little blades
    limb((0.50, 0.60), (0.30, 0.84), 0.085)
    limb((0.52, 0.60), (0.70, 0.90), 0.085)
    d.line([pt(0.24, 0.86), pt(0.36, 0.86)], fill=c, width=max(2, int(0.03 * size * S)))
    d.line([pt(0.64, 0.92), pt(0.78, 0.92)], fill=c, width=max(2, int(0.03 * size * S)))
    # coat/torso (filled, leaning forward)
    d.polygon([pt(0.42, 0.30), pt(0.60, 0.33), pt(0.56, 0.64), pt(0.44, 0.62)], fill=c)
    # arms (one reaching forward, one back)
    limb((0.54, 0.40), (0.74, 0.45), 0.06)
    limb((0.48, 0.40), (0.30, 0.50), 0.06)
    # head + hat
    d.ellipse([pt(0.44, 0.12)[0], pt(0.44, 0.12)[1], pt(0.60, 0.28)[0], pt(0.60, 0.28)[1]], fill=c)
    # flying scarf
    d.polygon([pt(0.46, 0.32), pt(0.30, 0.30), pt(0.26, 0.37), pt(0.44, 0.39)], fill=sc)
    img = img.resize((size, size), Image.LANCZOS)
    img.save(out)


def _band(a, bk, eb, ef, top, bottom):
    """A quad covering the [top, bottom] fraction of a roof plane a->ef (front edge)
    and bk->eb (back edge), measured from ridge (a/bk) down to eave (ef/eb)."""
    def lerp(p, q, t):
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    return [lerp(a, ef, top), lerp(bk, eb, top), lerp(bk, eb, bottom), lerp(a, ef, bottom)]
