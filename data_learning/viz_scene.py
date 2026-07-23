"""Generative depiction interpreter.

A *scene* is a small JSON spec the creative director (LLM) composes per data
point to INVENT a bespoke depiction, instead of picking a fixed chart kind. This
module validates a scene and renders it by composing a bounded set of robust
PIL "element" primitives (each drawn by the same hand-tuned code the named
depictions use), so an invented scene looks as good as a purpose-built one.

    scene = {
      "title": true,
      "elements": [
        {"type": "orbit_group", "region": "full"},
        {"type": "fill_object", "region": "center", "subject": "planet Earth",
         "data": {"value_from": "star"}, "anim": "fill"},
        {"type": "object", "region": "ground-row", "subject": "blue whale",
         "data": {"value_from": "item:0"}},
        ...
      ]
    }

Register the ``"scene"`` full-frame renderer into ``charts.FULLFRAME_RENDERERS``
so ``render_story_build`` / ``studio_render`` treat it like any other full-frame
depiction. Invalid or unrenderable scenes return ``None`` → the caller's FALLBACK
chain degrades to another DEPICTION (never bare numbers).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import charts
from .charts import (ACCENT, HIGHLIGHT, TEXT, WARN, _fullframe, _ordered_items,
                     _pil_font, _rgba, _sci, _vfmt)

W, H = 1080, 1920
RX0, RX1, RTOP, RBOT = 40, 1040, 80, 1180          # safe box (above the game strip)
_MIDX, _MIDY = (RX0 + RX1) // 2, (RTOP + RBOT) // 2

# region name -> pixel box (x0, y0, x1, y1)
REGIONS: dict[str, tuple[int, int, int, int]] = {
    "full":   (RX0, RTOP, RX1, RBOT),
    "center": (RX0 + 150, RTOP + 140, RX1 - 150, RBOT - 140),
    "hero":   (RX0, RTOP, RX0 + int((RX1 - RX0) * 0.56), RBOT),
    "left":   (RX0, RTOP, _MIDX - 20, RBOT),
    "right":  (_MIDX + 20, RTOP, RX1, RBOT),
    "top":    (RX0, RTOP, RX1, _MIDY),
    "bottom": (RX0, _MIDY, RX1, RBOT),
}
_TYPES = {"object", "fill_object", "stack", "orbit_group", "timeline_axis",
          "number", "bar", "bubble", "caption"}
_HOLISTIC = {"orbit_group", "timeline_axis"}       # render all items, own the box
_IMAGE_TYPES = {"object", "fill_object", "stack"}
_DATA_TYPES = {"object", "fill_object", "stack", "number", "bar", "bubble"}
_ANIM = {"fade", "rise", "travel", "count", "fill", "grow"}
_ROW_REGIONS = {"ground-row"} | {f"grid-{i}" for i in range(1, 5)}
_VALID_REGIONS = set(REGIONS) | _ROW_REGIONS


# --------------------------------------------------------------------------- #
# Data selectors
# --------------------------------------------------------------------------- #
def _resolve(sel, insight):
    """Resolve a `value_from` selector to a (label, value) pair, or None."""
    items = list(insight.items or [])
    if not items:
        return None
    if sel in (None, "", "star"):
        p = max(items, key=lambda q: q.value)
        return (p.label, p.value)
    if sel == "total":
        return ("Total", sum(q.value for q in items))
    if isinstance(sel, str) and sel.startswith("item:"):
        k = sel[5:].strip()
        if k.isdigit() and 0 <= int(k) < len(items):
            p = items[int(k)]
            return (p.label, p.value)
        for p in items:
            if p.label.lower() == k.lower():
                return (p.label, p.value)
    return None


def _color_for(label, insight):
    if insight.baseline and label == insight.baseline.label:
        return WARN
    if label == insight.highlight_label:
        return HIGHLIGHT
    return ACCENT


# --------------------------------------------------------------------------- #
# Validation + cost
# --------------------------------------------------------------------------- #
# Abstract chart shapes we REFUSE to render as a depiction — a bare bar / bubble
# / lone number is exactly the "lazy" look the channel bans. A scene must show
# the SUBJECT (a real photo / cut-out) and depict the value THROUGH it, or be a
# genuine holistic time depiction. These types are rejected outright.
_BANNED_TYPES = {"bar", "bubble"}
# Elements that count as a real, subject-bearing depiction.
_RICH_TYPES = _IMAGE_TYPES | _HOLISTIC


def validate(spec, insight) -> bool:
    if not isinstance(spec, dict):
        return False
    els = spec.get("elements")
    if not isinstance(els, list) or not (1 <= len(els) <= 6):
        return False
    for el in els:
        if not isinstance(el, dict):
            return False
        t = el.get("type")
        if t not in _TYPES or t in _BANNED_TYPES:
            return False
        reg = el.get("region", "center")
        if reg not in _VALID_REGIONS:
            return False
        if el.get("anim") not in (None, *_ANIM):
            return False
        if t in _IMAGE_TYPES and not str(el.get("subject", "")).strip():
            return False
        if t in _DATA_TYPES and _resolve((el.get("data") or {}).get("value_from"),
                                         insight) is None:
            return False
        if t == "stack" and not charts._num_or_none((el.get("data") or {})
                                                    .get("per_value")):
            return False
    # QUALITY GATE: a scene must SHOW something — at least one image/subject
    # element or a holistic time depiction. An abstract-only scene (just a
    # number/caption, or the old bar) is rejected so the director re-picks an
    # image-first depiction instead of shipping the lazy look.
    if not any(e.get("type") in _RICH_TYPES for e in els):
        return False
    return True


def image_cost(spec) -> int:
    if not isinstance(spec, dict):
        return 0
    return sum(1 for el in spec.get("elements", [])
               if isinstance(el, dict) and el.get("type") in _IMAGE_TYPES)


# --------------------------------------------------------------------------- #
# Layout — assign each element a disjoint pixel box
# --------------------------------------------------------------------------- #
def _layout(els):
    """Return a list parallel to `els` of boxes (x0,y0,x1,y1)."""
    boxes = [None] * len(els)
    used_single: set[str] = set()
    row_idx = [i for i, e in enumerate(els) if e.get("region") in _ROW_REGIONS]
    # Holistic / single-slot elements take their named region (demote on clash).
    for i, e in enumerate(els):
        reg = e.get("region", "center")
        if reg in _ROW_REGIONS:
            continue
        if reg in used_single:                     # clash -> fall to center/full
            reg = "center" if "center" not in used_single else "full"
        used_single.add(reg)
        boxes[i] = REGIONS.get(reg, REGIONS["center"])
    # Row/grid elements share a band along the bottom, laid out left-to-right.
    if row_idx:
        band_top = RTOP + 220 if any(e.get("region") not in _ROW_REGIONS
                                     for e in els) else RTOP + 60
        y0, y1 = band_top, RBOT
        n = len(row_idx)
        gap = 30
        cw = (RX1 - RX0 - gap * (n - 1)) / n
        for j, i in enumerate(row_idx):
            x0 = RX0 + j * (cw + gap)
            boxes[i] = (int(x0), y0, int(x0 + cw), y1)
    for i in range(len(boxes)):
        if boxes[i] is None:
            boxes[i] = REGIONS["center"]
    return boxes


def _object_ranking(els):
    """Indices of a set of `object` elements that form a ranking we should render
    as big vertical rows (image + number), or [] if the scene isn't one."""
    obj = [i for i, e in enumerate(els)
           if e.get("type") == "object" and e.get("region") in _ROW_REGIONS]
    holistic = any(e.get("type") in _HOLISTIC for e in els)
    # 2-5 illustrated things, no full-frame holistic element sharing the frame.
    return obj if (2 <= len(obj) <= 5 and not holistic) else []


def _vlist_layout(els, rows):
    """Full-width horizontal strips stacked top->bottom for a ranking, so big
    subject pictures fill the whole frame (no dead top third)."""
    boxes = [None] * len(els)
    for i, e in enumerate(els):
        if i not in rows:
            boxes[i] = REGIONS.get(e.get("region", "center"), REGIONS["center"])
    top, bot = RTOP + 10, RBOT
    rh = (bot - top) / len(rows)
    for k, i in enumerate(rows):
        boxes[i] = (RX0, int(top + k * rh), RX1, int(top + (k + 1) * rh))
    return boxes


def _stagger(reveal, i, n):
    span = 1.0 / max(1, n)
    lr = (reveal - i * span) / (span * 0.8)
    lr = max(0.0, min(1.0, lr))
    return 1.0 - (1.0 - lr) ** 2


# --------------------------------------------------------------------------- #
# Element draw-fns  (draw into a caller-supplied box)
# --------------------------------------------------------------------------- #
def _cx(box):
    return (box[0] + box[2]) // 2


def draw_caption(d, box, text, reveal, size=42, color=TEXT):
    f = _pil_font(size)
    tb = d.textbbox((0, 0), text, font=f)
    x = _cx(box) - (tb[2] - tb[0]) // 2
    d.text((x, box[1]), text, font=f, fill=(248, 250, 252, 255),
           stroke_width=3, stroke_fill=(5, 8, 15, 255))


def draw_number(d, box, value, label, color, reveal, unit=""):
    eased = 1.0 - (1.0 - reveal) ** 3
    shown = value * eased
    s = (f"{shown:,.0f}" if abs(shown) >= 100 or float(shown).is_integer()
         else f"{shown:,.1f}")
    u = (unit or "").lower()
    txt = s + ("%" if u in ("percent", "%", "rate", "pct")
               else "" if not u else "")
    nf = _pil_font(118)
    nb = d.textbbox((0, 0), txt, font=nf)
    cy = (box[1] + box[3]) // 2
    d.text((_cx(box) - (nb[2] - nb[0]) // 2, cy - 70), txt, font=nf,
           fill=_rgba(color, 255), stroke_width=6, stroke_fill=(5, 8, 15, 255))
    if label:
        lf = _pil_font(44)
        lb = d.textbbox((0, 0), label, font=lf)
        d.text((_cx(box) - (lb[2] - lb[0]) // 2, cy + 66), label, font=lf,
               fill=(248, 250, 252, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))


def _cover_round(photo, w, h, radius=28):
    """Cover-crop a real photo to (w,h) with rounded corners -> RGBA."""
    from PIL import Image, ImageDraw, ImageOps
    w, h = max(1, int(w)), max(1, int(h))
    im = ImageOps.fit(photo.convert("RGB"), (w, h), method=Image.LANCZOS)
    im = im.convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    im.putalpha(mask)
    return im


def draw_object(d, canvas, box, cutout, value, label, color, reveal, vmax,
                side=False, photo=None):
    """A subject cut-out with its number + label. Two modes:
      * side=True  -> a full-width RANKING ROW: a BIG recognizable picture on the
        left, a big number + label on the right (rows stack to fill the frame).
      * side=False -> the classic bottom-anchored object sized by value.
    Placeholder silhouette if the cut-out is missing."""
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    if side:
        # Big image on the left, filling most of the row height so viewers can
        # actually SEE what the thing looks like; number + label on the right.
        rise = int((1.0 - reveal) * 40)
        cy = (by0 + by1) // 2 + rise
        ih = int(bh * 0.84)
        if photo is not None:
            # A REAL photo of the thing, framed as a rounded card filling the left.
            iw = int(bw * 0.48)
            card = _cover_round(photo, iw, ih, radius=30)
            if reveal < 1.0:
                card.putalpha(card.split()[3].point(lambda v: int(v * reveal)))
            px = bx0 + int(bw * 0.03)
            d.rounded_rectangle([px - 4, int(cy - ih / 2) - 4, px + iw + 4,
                                 int(cy + ih / 2) + 4], radius=34,
                                outline=_rgba(color, int(255 * reveal)), width=5)
            canvas.alpha_composite(card, (px, int(cy - ih / 2)))
        elif cutout is not None:
            img_cx = bx0 + int(bw * 0.26)
            asp = cutout.width / cutout.height
            iw = int(ih * asp)
            iw_cap = int(bw * 0.46)
            if iw > iw_cap:
                iw, ih = iw_cap, int(iw_cap / asp)
            im = cutout.resize((max(1, iw), max(1, ih)))
            if reveal < 1.0:
                im.putalpha(im.split()[3].point(lambda v: int(v * reveal)))
            canvas.alpha_composite(im, (int(img_cx - iw / 2), int(cy - ih / 2)))
        else:
            img_cx = bx0 + int(bw * 0.26)
            iw = int(ih * 0.9)
            d.rounded_rectangle([img_cx - iw // 2, cy - ih // 2,
                                 img_cx + iw // 2, cy + ih // 2],
                                radius=24, fill=_rgba(color, int(255 * reveal)))
        na = max(0.0, min(1.0, (reveal - 0.35) / 0.5))
        nx = bx0 + int(bw * 0.56)
        avail = bx1 - nx - 12                     # keep text inside the frame
        nfs = min(150, max(84, int(bh * 0.42)))
        num = _vfmt(value)
        nf = _pil_font(nfs)
        nb = d.textbbox((0, 0), num, font=nf)
        while nfs > 48 and (nb[2] - nb[0]) > avail:     # shrink number to fit
            nfs -= 8
            nf = _pil_font(nfs)
            nb = d.textbbox((0, 0), num, font=nf)
        d.text((nx, cy - (nb[3] - nb[1]) - 6), num, font=nf,
               fill=_rgba(color, int(255 * na)), stroke_width=6,
               stroke_fill=(5, 8, 15, int(255 * na)))
        lfs = 46
        lf = _pil_font(lfs)
        while lfs > 24 and d.textbbox((0, 0), label, font=lf)[2] > avail:
            lfs -= 4                                    # shrink label to fit
            lf = _pil_font(lfs)
        d.text((nx, cy + 14), label, font=lf,
               fill=(248, 250, 252, int(255 * na)), stroke_width=3,
               stroke_fill=(5, 8, 15, int(255 * na)))
        return {"value": float(value), "cx": float(nx + (nb[2] - nb[0]) / 2),
                "cy": float(cy - (nb[3] - nb[1]) / 2), "w": 240.0, "h": 120.0}
    frac = 0.55 + 0.45 * (value / vmax if vmax else 1.0)
    avail_h = bh - 150                                 # room for number + label
    cx = _cx(box)
    ground = by1 - 60
    a = int(255 * reveal)
    if photo is not None:                              # real photo -> framed card
        ph = int(avail_h * max(0.7, frac))
        pw = int(min(bw * 0.94, ph * 1.35))
        ph = int(pw / 1.35)
        top = ground - ph + int((1.0 - reveal) * 60)
        card = _cover_round(photo, pw, ph, radius=30)
        if reveal < 1.0:
            card.putalpha(card.split()[3].point(lambda v: int(v * reveal)))
        d.rounded_rectangle([cx - pw // 2 - 4, top - 4, cx + pw // 2 + 4, top + ph + 4],
                            radius=34, outline=_rgba(color, a), width=5)
        canvas.alpha_composite(card, (int(cx - pw / 2), int(top)))
        oh = ph
    else:
        if cutout is not None:
            asp = cutout.width / cutout.height
            oh = int(avail_h * frac)
            ow = int(oh * asp)
            if ow > bw:
                ow, oh = bw, int(bw / asp)
        else:
            oh = int(avail_h * frac)
            ow = int(oh * 0.9)
        top = ground - oh + int((1.0 - reveal) * 60)
        if cutout is not None and ow > 0 and oh > 0:
            im = cutout.resize((ow, oh))
            if reveal < 1.0:
                im.putalpha(im.split()[3].point(lambda v: int(v * reveal)))
            canvas.alpha_composite(im, (int(cx - ow / 2), int(top)))
        else:
            d.rounded_rectangle([cx - ow // 2, top, cx + ow // 2, top + oh],
                                radius=24, fill=_rgba(color, a))
    na = max(0.0, min(1.0, (reveal - 0.45) / 0.55))
    nf, lf = _pil_font(60), _pil_font(36)
    num = _vfmt(value)
    nb = d.textbbox((0, 0), num, font=nf)
    ny = top - 74
    d.text((cx - (nb[2] - nb[0]) // 2, ny), num, font=nf,
           fill=_rgba(color, int(255 * na)), stroke_width=5,
           stroke_fill=(5, 8, 15, int(255 * na)))
    lb = d.textbbox((0, 0), label, font=lf)
    d.text((cx - (lb[2] - lb[0]) // 2, ground + 8), label, font=lf,
           fill=(248, 250, 252, int(255 * na)), stroke_width=3,
           stroke_fill=(5, 8, 15, int(255 * na)))
    return {"value": float(value), "cx": float(cx), "cy": float(ny + 30),
            "w": 220.0, "h": 90.0}


def _fmt_stat(value, unit):
    s = (f"{value:,.0f}" if abs(value) >= 100 or float(value).is_integer()
         else f"{value:,.1f}")
    u = (unit or "").lower()
    if u in ("percent", "%", "rate", "pct"):
        return s + "%"
    if u in ("dollars", "usd", "$"):
        return "$" + s
    return s


def draw_fill_object(d, canvas, box, cutout, value, label, color, reveal, unit="",
                     photo=None):
    """Fill a SUBJECT silhouette bottom-up to a % while the number counts up —
    the 'filled globe/brain' viz. The cut-out's alpha is the shape mask; when a
    REAL PHOTO of the subject is available it fills the shape (a real brain in a
    brain outline, real Earth in the globe) instead of a flat colour. Degrades to
    a rounded vessel if there's no cut-out at all."""
    from PIL import Image, ImageChops, ImageOps
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    is_pct = (unit or "").lower() in ("percent", "%", "rate", "pct")
    frac = (max(0.06, min(1.0, value / 100.0)) if is_pct else 1.0)
    eased = 1.0 - (1.0 - reveal) ** 3
    fill_frac = frac * eased
    avail_h = bh - 150
    cx = _cx(box)
    if cutout is not None:
        asp = cutout.width / cutout.height
        oh = int(min(avail_h, bw / asp))
        ow = int(oh * asp)
        im = cutout.resize((max(1, ow), max(1, oh)))
        ox, oy = cx - ow // 2, by0 + 120 + (avail_h - oh) // 2
        mask = im.split()[3]
        # dim ghost so the unfilled part reads as a hollow outline
        ghost = im.copy()
        ghost.putalpha(mask.point(lambda v: int(v * 0.28)))
        canvas.alpha_composite(ghost, (ox, oy))
        # rising fill clipped to the silhouette
        fh = int(oh * fill_frac)
        if fh > 4:
            band = Image.new("L", (ow, oh), 0)
            band.paste(255, (0, oh - fh, ow, oh))
            clip = ImageChops.multiply(mask, band)
            if photo is not None:      # fill the shape with a REAL photo
                layer = ImageOps.fit(photo.convert("RGB"), (ow, oh),
                                     method=Image.LANCZOS).convert("RGBA")
                # a faint colour wash so the waterline still reads
                wash = Image.new("RGBA", (ow, oh), _rgba(color, 70))
                layer = Image.alpha_composite(layer, wash)
            else:
                layer = Image.new("RGBA", (ow, oh), _rgba(color, 235))
            layer.putalpha(clip)
            canvas.alpha_composite(layer, (ox, oy))
        num_cy = oy + oh // 2
    elif photo is not None:                        # no silhouette -> real photo card
        ph = int(avail_h * 0.9)
        pw = int(min(bw * 0.82, ph * 1.35))
        ph = int(pw / 1.35)
        px, py = cx - pw // 2, by0 + 120
        card = _cover_round(photo, pw, ph, radius=30)
        d.rounded_rectangle([px - 4, py - 4, px + pw + 4, py + ph + 4], radius=34,
                            outline=_rgba(color, 255), width=5)
        canvas.alpha_composite(card, (px, py))
        num_cy = py + ph // 2
    else:                                          # vessel degrade
        vw, vh = int(bw * 0.6), int(avail_h * 0.9)
        vx, vy = cx - vw // 2, by0 + 120
        d.rounded_rectangle([vx, vy, vx + vw, vy + vh], radius=48,
                            outline=(150, 170, 200, 255), width=8)
        fh = int((vh - 16) * fill_frac)
        if fh > 4:
            d.rounded_rectangle([vx + 10, vy + vh - 8 - fh, vx + vw - 10, vy + vh - 8],
                                radius=40, fill=_rgba(color, 235))
        num_cy = vy + vh // 2
    num = _fmt_stat(value * eased, unit)
    nf = _pil_font(104)
    nb = d.textbbox((0, 0), num, font=nf)
    d.text((cx - (nb[2] - nb[0]) // 2, num_cy - 64), num, font=nf,
           fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(5, 8, 15, 255))
    if label:
        lf = _pil_font(46)
        lb = d.textbbox((0, 0), label, font=lf)
        d.text((cx - (lb[2] - lb[0]) // 2, by1 - 60), label, font=lf,
               fill=(248, 250, 252, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))
    return {"value": float(value), "cx": float(cx), "cy": float(num_cy - 20),
            "w": 240.0, "h": 140.0}


def draw_stack(d, canvas, box, cutout, value, per_value, label, color, reveal, unit=""):
    """Stack N=value/per_value copies of a cut-out to depict a magnitude."""
    bx0, by0, bx1, by1 = box
    n = max(1, int(round(value / per_value))) if per_value else 1
    cap = min(n, 8)
    top, bot = by0 + 150, by1 - 20
    gap = 8
    ch = int((bot - top - gap * (cap - 1)) / cap)
    if cutout is not None:
        cw = int(ch * cutout.width / cutout.height)
        icon = cutout.resize((max(1, cw), max(1, ch)))
    else:
        cw, icon = int(ch * 0.9), None
    cx = _cx(box)
    shown = int(round(reveal * cap))
    for k in range(min(shown, cap)):
        y = bot - ch - k * (ch + gap)
        if icon is not None:
            canvas.alpha_composite(icon, (cx - cw // 2, y))
        else:
            d.rounded_rectangle([cx - cw // 2, y, cx + cw // 2, y + ch],
                                radius=14, fill=_rgba(color, 235))
    na = max(0.0, min(1.0, (reveal - 0.35) / 0.6))
    val = f"{value:,.0f} {unit}".strip()
    vf = _pil_font(60)
    vb = d.textbbox((0, 0), val, font=vf)
    d.text((cx - (vb[2] - vb[0]) // 2, by0 + 60), val, font=vf,
           fill=_rgba(HIGHLIGHT, 255), stroke_width=5, stroke_fill=(5, 8, 15, 255))
    cap_txt = f"= {n:,} × {label}"
    cf = _pil_font(40)
    cb = d.textbbox((0, 0), cap_txt, font=cf)
    d.text((cx - (cb[2] - cb[0]) // 2, by0 + 120), cap_txt, font=cf,
           fill=(248, 250, 252, int(255 * na)), stroke_width=3,
           stroke_fill=(5, 8, 15, int(255 * na)))
    return None


def draw_bar(d, box, value, label, color, reveal, vmax):
    """A horizontal bar whose length ∝ value, with the number at the tip."""
    bx0, by0, bx1, by1 = box
    cy = (by0 + by1) // 2
    x0, x1 = bx0 + 20, bx1 - 120
    tip = x0 + (x1 - x0) * (value / vmax if vmax else 1.0) * reveal
    d.line([(x0, cy), (x1, cy)], fill=_rgba(charts.BAR_BASE, 255), width=54)
    d.line([(x0, cy), (max(x0 + 4, tip), cy)], fill=_rgba(color, 255), width=54)
    lf = _pil_font(30)
    d.text((bx0 + 20, by0 + 6), label, font=lf, fill=(248, 250, 252, 255),
           stroke_width=3, stroke_fill=(5, 8, 15, 255))
    na = max(0.0, min(1.0, (reveal - 0.8) / 0.2))
    nf = _pil_font(40)
    d.text((tip + 16, cy - 24), _vfmt(value), font=nf, fill=_rgba(color, int(255 * na)),
           stroke_width=3, stroke_fill=(5, 8, 15, int(255 * na)))
    return {"value": float(value), "cx": float(tip + 60), "cy": float(cy),
            "w": 120.0, "h": 60.0}


def draw_bubble(d, box, value, label, color, reveal, vmax):
    """A proportional circle (area ∝ value)."""
    import math as _m
    bx0, by0, bx1, by1 = box
    cx, cy = _cx(box), (by0 + by1) // 2
    rmax = min(bx1 - bx0, by1 - by0) / 2 - 60
    r = rmax * _m.sqrt(value / vmax if vmax else 1.0) * reveal
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_rgba(color, 235),
              outline=(255, 255, 255, 255), width=3)
    na = max(0.0, min(1.0, (reveal - 0.8) / 0.2))
    nf, lf = _pil_font(46), _pil_font(34)
    nb = d.textbbox((0, 0), _vfmt(value), font=nf)
    d.text((cx - (nb[2] - nb[0]) // 2, cy - 28), _vfmt(value), font=nf,
           fill=(11, 16, 32, int(255 * na)), stroke_width=0)
    lb = d.textbbox((0, 0), label, font=lf)
    d.text((cx - (lb[2] - lb[0]) // 2, cy + r + 8), label, font=lf,
           fill=(248, 250, 252, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))
    return {"value": float(value), "cx": float(cx), "cy": float(cy), "w": 120.0, "h": 60.0}


def draw_orbit(d, box, insight, reveal):
    """Bodies orbit a centre at radii ∝ value (the loved solar-system look)."""
    import math as _m
    items = _ordered_items(insight)[:5]
    vals = [max(0.0001, p.value) for p in items]
    vmax = max(vals)
    cx, cy = _cx(box), (box[1] + box[3]) // 2
    r_out = int(min(box[2] - box[0], box[3] - box[1]) / 2 * 0.92)
    r_in = max(120, int(r_out * 0.34))
    radii = [r_in + (r_out - r_in) * (v / vmax) for v in vals]
    ang0 = [-90 + i * (360.0 / max(1, len(items))) for i in range(len(items))]
    lab_font = _pil_font(36)
    for rad in radii:
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                  outline=(90, 110, 140, 120), width=3)
    for rad, alpha in ((66, 60), (48, 130), (34, 255)):
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=_rgba(WARN, alpha))
    for i, (p, rad) in enumerate(zip(items, radii)):
        na = max(0.0, min(1.0, (reveal - i * 0.12) / 0.6))
        if na <= 0:
            continue
        ang = _m.radians(ang0[i] + reveal * 300.0)
        bx, by = cx + rad * _m.cos(ang), cy + rad * _m.sin(ang)
        col = HIGHLIGHT if p.label == insight.highlight_label else ACCENT
        d.ellipse([bx - 26, by - 26, bx + 26, by + 26], fill=_rgba(col, int(255 * na)))
        txt = f"{p.label} {_vfmt(p.value)}"
        tw = d.textbbox((0, 0), txt, font=lab_font)
        lx = min(max(bx + 34, box[0]), box[2] - (tw[2] - tw[0]))
        d.text((lx, by - 18), txt, font=lab_font,
               fill=(248, 250, 252, int(255 * na)), stroke_width=3,
               stroke_fill=(5, 8, 15, int(255 * na)))


def draw_timeline(d, canvas, box, insight, reveal):
    """Depict 'X over time'. When we have a real value series across years, plot
    it as a RISING FILLED AREA that climbs the frame (value on Y, year on X) with
    Data riding the leading edge UP and the number counting — so the beat
    DEMONSTRATES the climb and fills the frame, instead of a lone number floating
    over a flat line in a void. Falls back to the flat time-axis for a single
    value / no periods."""
    items = _ordered_items(insight)
    periods = [charts._num_or_none(getattr(p, "period", None)) for p in items]
    have_p = len(periods) >= 2 and all(v is not None for v in periods)
    vals = [p.value for p in items]
    if have_p and len({round(v, 4) for v in vals}) >= 2:
        _draw_climb(d, canvas, insight, items, periods, reveal)
        return
    _draw_flat_timeline(d, canvas, box, insight, reveal)


def _draw_climb(d, canvas, insight, items, periods, reveal):
    """Rising filled-area chart of a value series over years, revealed L→R, with
    Data climbing the leading edge and the value counting up. Fills the frame."""
    from PIL import Image as _Im
    order = sorted(range(len(items)), key=lambda i: periods[i])
    yrs = [float(periods[i]) for i in order]
    vals = [float(items[i].value) for i in order]
    y0v, y1v = yrs[0], yrs[-1]
    span_x = (y1v - y0v) or 1.0
    vmax = (max(vals) * 1.12) or 1.0            # honest 0-based axis
    px0, px1 = 120, W - 100
    pb, pt = int(H * 0.72), int(H * 0.30)       # baseline / ceiling
    unit = insight.unit

    def X(yr):
        return px0 + (yr - y0v) / span_x * (px1 - px0)

    def Y(v):
        return pb - (v / vmax) * (pb - pt)

    r = 1.0 - (1.0 - reveal) ** 2               # ease-out reveal
    # (title is drawn once by render_scene's show_title — do NOT draw it here or
    # it stacks twice, which reads as a broken render.)
    n = len(yrs)
    seg = r * (n - 1)
    hi = min(int(seg), n - 1)
    fr = seg - hi
    # DIFFERENTIATE demonstrations so two time-series beats don't look identical:
    # a money magnitude STACKS UP as growing columns; anything else CLIMBS as a
    # filled area. (Data's act is varied to match — see pose below.)
    u = (unit or "").lower()
    bars = u in ("dollars", "usd", "$")
    pts = []
    if bars:
        bw = (px1 - px0) / n * 0.60
        hx = hy = None
        for i in range(n):
            grow = max(0.0, min(1.0, seg - i + 1))     # column i rises 0→1
            if grow <= 0:
                continue
            top = pb - (vals[i] / vmax) * (pb - pt) * grow
            cx = X(yrs[i])
            d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, pb],
                                radius=10, fill=_rgba(HIGHLIGHT, 220))
            hx, hy = cx, top
        if hx is None:
            hx, hy = X(yrs[0]), pb
    else:
        pts = [(X(yrs[i]), Y(vals[i])) for i in range(hi + 1)]
        if hi < n - 1:
            hx = X(yrs[hi]) + fr * (X(yrs[hi + 1]) - X(yrs[hi]))
            hy = Y(vals[hi]) + fr * (Y(vals[hi + 1]) - Y(vals[hi]))
            pts.append((hx, hy))
        hx, hy = pts[-1]
        if len(pts) >= 2:
            d.polygon(pts + [(hx, pb), (pts[0][0], pb)], fill=_rgba(HIGHLIGHT, 66))
    d.line([(px0, pb), (px1, pb)], fill=(90, 105, 130, 255), width=5)  # baseline
    tick_font = _pil_font(30)
    for i in range(n):
        tx = X(yrs[i])
        d.line([(tx, pb - 8), (tx, pb + 10)], fill=(120, 140, 170, 255), width=3)
        lbl = str(int(yrs[i]))
        lb = d.textbbox((0, 0), lbl, font=tick_font)
        d.text((tx - (lb[2] - lb[0]) // 2, pb + 18), lbl, font=tick_font,
               fill=(165, 180, 199, 255))
    if not bars and len(pts) >= 2:
        d.line(pts, fill=_rgba(HIGHLIGHT, 255), width=11, joint="curve")
    for rad, a in ((40, 55), (28, 120), (18, 255)):
        d.ellipse([hx - rad, hy - rad, hx + rad, hy + rad], fill=_rgba(HIGHLIGHT, a))
    # Data's act varies with the demonstration: he POINTS OUT the stacking bill
    # (bars) vs. CHEERS/rides the climbing line (area) — a distinct bit per beat.
    host = charts._host_pose("point" if bars else "cheer")
    mh = 268        # a strong presence, but not so big it collides with text
    if host is not None:
        mw = int(host.width * mh / host.height)
        px = int(min(max(hx - mw / 2, 8), W - mw - 8))
        canvas.alpha_composite(host.resize((mw, mh), _Im.LANCZOS),
                               (px, int(hy - mh + 12)))
    # Hero value shows the FINAL figure (fading in) — NOT a mid-count that could
    # read as e.g. "11.3%" when the script says 11.8% (a data-consistency flag).
    # The chart itself carries the motion; the number stays truthful throughout.
    na = max(0.0, min(1.0, (r - 0.15) / 0.85))
    nf = _pil_font(78)
    val = _fmt_stat(vals[-1], unit)
    vb = d.textbbox((0, 0), val, font=nf)
    # Hero number sits in a FIXED slot centred just under the title — decoupled
    # from the (moving, now-larger) mascot so it never collides with the title or
    # clips off the right edge.
    vx = int((W - (vb[2] - vb[0])) / 2)
    vy = 352
    d.text((vx, vy), val, font=nf, fill=_rgba(HIGHLIGHT, int(255 * na)),
           stroke_width=6, stroke_fill=(5, 8, 15, 255))
    # start value + the delta gap (physical +$X since the first year)
    sf = _pil_font(34)
    d.text((px0 - 6, int(Y(vals[0])) - 46), _fmt_stat(vals[0], unit), font=sf,
           fill=(170, 185, 205, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))
    if r > 0.55:
        dv = vals[-1] - vals[0]
        dtxt = ("+" if dv >= 0 else "−") + _fmt_stat(abs(dv), unit) \
            + f" since {int(yrs[0])}"
        db = d.textbbox((0, 0), dtxt, font=sf)
        d.text(((W - (db[2] - db[0])) // 2, pt - 6), dtxt, font=sf,
               fill=_rgba(HIGHLIGHT, int(255 * na)), stroke_width=3,
               stroke_fill=(5, 8, 15, 255))


def _draw_flat_timeline(d, canvas, box, insight, reveal):
    """The original flat time-axis: a marker travels to a single value's year."""
    items = _ordered_items(insight)
    vp = getattr(insight, "viz_params", {}) or {}
    star = max(items, key=lambda p: p.value)
    periods = [charts._num_or_none(getattr(p, "period", None)) for p in items]
    have_p = len(periods) >= 2 and all(v is not None for v in periods)
    lo = charts._num_or_none(vp.get("timeline_start"))
    hi = charts._num_or_none(vp.get("timeline_end"))
    if have_p:
        # Time series: the dot travels the YEAR axis, but the hero number is the
        # METRIC VALUE at that point (e.g. $1,030 / 11.8%) — not the year — with
        # the year shown small beneath the dot. (Showing the year as the headline
        # was a real bug: "the grocery bill" read "2,026" instead of "$1,030".)
        lo = min(periods) if lo is None else lo
        hi = max(periods) if hi is None else hi
        pos = periods[items.index(star)]
        foot = str(int(pos)) if float(pos).is_integer() else _sci(pos)
    else:
        lo = 0.0 if lo is None else lo
        hi = (star.value * 1.12 or 1.0) if hi is None else hi
        pos = star.value
        foot = star.label
    if hi <= lo:
        hi = lo + 1.0
    frac = max(0.0, min(1.0, (pos - lo) / (hi - lo)))
    # Centre the axis in the FULL frame (not the legacy top-biased safe box that
    # reserved a bottom strip CLEAN mode no longer draws) so the host + line sit
    # balanced in the middle instead of jammed into the top third over a void.
    axis_y = min(box[3] - 90, max((box[1] + box[3]) // 2, int(H * 0.50)))
    x0, x1 = box[0] + 70, box[2] - 70
    num_font, tick_font, lab_font = _pil_font(72), _pil_font(30), _pil_font(46)
    d.line([(x0, axis_y), (x1, axis_y)], fill=(120, 140, 170, 255), width=6)
    for k in range(5):
        tx = x0 + (x1 - x0) * k / 4
        d.line([(tx, axis_y - 14), (tx, axis_y + 14)], fill=(120, 140, 170, 255), width=4)
        tv = lo + (hi - lo) * k / 4
        lbl = str(int(round(tv))) if have_p else _sci(tv)   # years: no comma
        lb = d.textbbox((0, 0), lbl, font=tick_font)
        d.text((tx - (lb[2] - lb[0]) // 2, axis_y + 28), lbl, font=tick_font,
               fill=(165, 180, 199, 255))
    mx = x0 + reveal * frac * (x1 - x0)
    d.line([(x0, axis_y), (mx, axis_y)], fill=_rgba(HIGHLIGHT, 255), width=12)
    for rad, alpha in ((48, 60), (34, 120), (23, 255)):
        d.ellipse([mx - rad, axis_y - rad, mx + rad, axis_y + rad], fill=_rgba(HIGHLIGHT, alpha))
    # Data rides the dot along the axis (composited straight into the beat).
    host = charts._host_pose("cheer")
    if host is not None:
        from PIL import Image as _Im
        mh = 250
        mw = int(host.width * mh / host.height)
        hx = int(min(max(mx - mw / 2, box[0]), box[2] - mw))
        canvas.alpha_composite(host.resize((mw, mh), _Im.LANCZOS),
                               (hx, int(axis_y - mh + 18)))
    na = max(0.0, min(1.0, (reveal - 0.35) / 0.65))
    val = _fmt_stat(star.value, insight.unit)
    vb = d.textbbox((0, 0), val, font=num_font)
    vx = min(max(mx - (vb[2] - vb[0]) / 2, box[0]), box[2] - (vb[2] - vb[0]))
    # Value floats above Data's head (clear of the host so both read cleanly).
    vy = max(box[1] + 6, axis_y - 320)
    d.text((vx, vy), val, font=num_font, fill=_rgba(HIGHLIGHT, int(255 * na)),
           stroke_width=5, stroke_fill=(5, 8, 15, int(255 * na)))
    sb = d.textbbox((0, 0), foot, font=lab_font)
    sx = min(max(mx - (sb[2] - sb[0]) / 2, box[0]), box[2] - (sb[2] - sb[0]))
    d.text((sx, axis_y + 78), foot, font=lab_font,
           fill=(248, 250, 252, int(255 * na)), stroke_width=3,
           stroke_fill=(5, 8, 15, int(255 * na)))


# --------------------------------------------------------------------------- #
# Interpreter
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Canonical scene builders — deterministic scenes the director can attach when
# there's no LLM-authored scene (so shares get a filled globe, etc.).
# --------------------------------------------------------------------------- #
_GEO_WORDS = re.compile(r"\b(earth|ocean|sea|water|planet|world|global|globe|"
                        r"land|continent|surface|atmosphere|freshwater|ice)\b", re.I)


def globe_subject(insight) -> str:
    """Pick the object to fill for a share/percentage — a globe for Earth/water
    topics, else a noun derived from the topic."""
    topic = insight.topic or ""
    if _GEO_WORDS.search(topic):
        return "planet Earth, whole globe seen from space"
    noun = re.sub(r"\b(share|percent|of|the|by|in|rate|amount|total|increase|"
                  r"growth|change|rise|decline|drop|length|duration|level|"
                  r"season|per|vs|and)\b", " ", topic, flags=re.I)
    noun = re.sub(r"\s+", " ", noun).strip()
    return noun or "a glass jar"


def fill_scene(insight) -> dict:
    """A single subject filled to the headline value — shares & shock stats."""
    return {"elements": [{"type": "fill_object", "region": "center",
                          "subject": globe_subject(insight),
                          "data": {"value_from": "star"}, "anim": "fill"}]}


def object_scene(insight) -> dict:
    """A ranking of REAL THINGS: one `object` per item (its own label as the
    photo subject) in a ground-row. render_scene turns this into big vertical
    rows with a real photo of each thing — the 'show me what it looks like' viz."""
    items = list(insight.items)[:5]
    els = [{"type": "object", "region": "ground-row",
            "subject": (p.label or "").strip(),
            "data": {"value_from": f"item:{i}"}}
           for i, p in enumerate(items)]
    return {"title": True, "elements": els}


def _load_cutout(subject, slug, tag):
    from . import scene_media
    from PIL import Image
    cp = scene_media.subject_cutout(subject, slug, tag)
    if not cp:
        return None
    try:
        return Image.open(cp).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _load_photo(subject, slug, tag):
    """A REAL internet photo of the subject (Wikipedia/Commons), as a PIL RGB."""
    from . import scene_media
    from PIL import Image
    pp = scene_media.subject_photo(subject, slug, tag)
    if not pp:
        return None
    try:
        return Image.open(pp).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


@_fullframe("scene")
def render_scene(insight, out_dir: Path, slug: str, frames: int = 16):
    from PIL import Image, ImageDraw
    spec = getattr(insight, "scene", None)
    if not validate(spec, insight):
        return None
    els = spec["elements"]
    # Mechanics that composite Data straight into the beat (he rides the element)
    # so the travelling overlay must be suppressed to avoid a duplicate host.
    if any(el.get("type") == "timeline_axis" for el in els):
        insight.host_baked = True
    out_dir.mkdir(parents=True, exist_ok=True)
    # A ranking of illustrated things -> big vertical rows (picture + number)
    # that FILL the frame, instead of a cramped bottom row with a dead top third.
    rank_rows = _object_ranking(els)
    boxes = _vlist_layout(els, rank_rows) if rank_rows else _layout(els)
    side_set = set(rank_rows)
    # Only show the standalone title when NOT a vertical ranking (the rows own
    # the whole frame; the topic is spoken + captioned by the renderer anyway).
    show_title = (spec.get("title", True) and bool(insight.topic)
                  and not rank_rows)
    # Pre-load cut-outs once (cached anyway) so we can bail to fallback if the
    # whole scene is image-only and every image failed.
    cuts, photos = {}, {}
    for i, el in enumerate(els):
        t = el.get("type")
        # CRITICAL: for an `object` the image must match the number/label the row
        # shows. That comes from the RESOLVED item (value_from), NOT the element's
        # authored `subject` (which can be misaligned after value-sorting). Fetch
        # the photo for the item this row actually displays.
        if t == "object":
            lv = _resolve((el.get("data") or {}).get("value_from"), insight)
            subj = (lv[0] if lv else str(el.get("subject", ""))).strip()
            import hashlib
            sh = hashlib.sha1(subj.lower().encode()).hexdigest()[:6]  # subject-keyed cache
            photos[i] = _load_photo(subj, slug, f"p{i}-{sh}")
            if photos[i] is None:
                cuts[i] = _load_cutout(subj, slug, f"s{i}-{sh}")
        elif t == "fill_object":
            subj = str(el.get("subject", ""))
            cuts[i] = _load_cutout(subj, slug, f"s{i}")     # silhouette mask
            photos[i] = _load_photo(subj, slug, f"pf{i}")   # real fill content
        elif t in _IMAGE_TYPES:
            cuts[i] = _load_cutout(str(el.get("subject", "")), slug, f"s{i}")
    # `object`/`stack` need SOME image (photo or cut-out). If every element is one
    # of those and none produced an image, bail to a cleaner FALLBACK depiction.
    hard = {"object", "stack"}
    if els and all(e.get("type") in hard for e in els) \
            and all(cuts.get(i) is None and photos.get(i) is None
                    for i in range(len(els))):
        return None
    vmax = max((p.value for p in insight.items), default=1.0) or 1.0
    n = len(els)
    anchors: list = []
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        r = 1.0 - (1.0 - r) ** 2
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        if show_title:
            draw_caption(d, (RX0, 250, RX1, 250), insight.topic, 1.0, size=52)
        for i, el in enumerate(els):
            lr = _stagger(r, i, n)
            if lr <= 0:
                continue
            t = el.get("type")
            box = boxes[i]
            if t == "orbit_group":
                draw_orbit(d, box, insight, r)
            elif t == "timeline_axis":
                draw_timeline(d, canvas, box, insight, r)
            elif t == "caption":
                draw_caption(d, box, str(el.get("text", "")), lr)
            elif t == "number":
                lv = _resolve((el.get("data") or {}).get("value_from"), insight)
                if lv:
                    draw_number(d, box, lv[1], lv[0], _color_for(lv[0], insight),
                                lr, insight.unit)
            elif t in ("object", "fill_object", "stack", "bar", "bubble"):
                lv = _resolve((el.get("data") or {}).get("value_from"), insight)
                if not lv:
                    continue
                col = _color_for(lv[0], insight)
                if t == "fill_object":
                    an = draw_fill_object(d, canvas, box, cuts.get(i), lv[1], lv[0],
                                          col, lr, insight.unit, photo=photos.get(i))
                elif t == "stack":
                    per = charts._num_or_none((el.get("data") or {}).get("per_value"))
                    an = draw_stack(d, canvas, box, cuts.get(i), lv[1], per, lv[0],
                                    col, lr, insight.unit)
                elif t == "bar":
                    an = draw_bar(d, box, lv[1], lv[0], col, lr, vmax)
                elif t == "bubble":
                    an = draw_bubble(d, box, lv[1], lv[0], col, lr, vmax)
                else:
                    an = draw_object(d, canvas, box, cuts.get(i), lv[1], lv[0],
                                     col, lr, vmax, side=(i in side_set),
                                     photo=photos.get(i))
                if f == frames and an:
                    anchors.append(an)
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, anchors


# --------------------------------------------------------------------------- #
# PROCEDURAL mechanics — the AI INVENTS A BRAND-NEW depiction by writing the
# drawing code itself, run in a locked-down sandbox. This is the "make something
# new first" path: a spec is {"mechanic": name, "concept": text, "code": body}
# where `code` draws ONE frame given a safe namespace (an ImageDraw `d`, the data
# in `values`/`labels`, subject `images`, `reveal` 0..1, and a few helpers). No
# imports, no builtins beyond a whitelist, guarded by a wall-clock alarm, dry-run
# validated before use, and it MUST place a real subject image (so a new mechanic
# still SHOWS the thing — never abstract shapes).
# --------------------------------------------------------------------------- #
_SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict)
                  else getattr(__builtins__, k)
                  for k in ("range", "len", "min", "max", "abs", "int", "float",
                            "round", "enumerate", "zip", "list", "tuple",
                            "sorted", "sum", "map", "filter", "str", "bool",
                            "True", "False", "None") if True}
# Tokens that must never appear in generated mechanic code (defense in depth on
# top of the stripped builtins).
# Function-like tokens are only dangerous when CALLED — require the paren so a
# subject phrase like 'crocodile open jaws' or 'evaluation of...' isn't flagged.
_FORBIDDEN = re.compile(
    r"__|\bimport\b|\bwhile\b|"
    r"\b(?:open|eval|exec|compile|globals|locals|getattr|setattr|delattr|"
    r"vars|input|exit|quit)\s*\(")
_IMAGE_CALL = re.compile(r"\b(paste|fill_image|images|subject_image)\b")


def validate_mechanic(spec) -> bool:
    """Structural check for a procedural mechanic spec (not a dry-run)."""
    if not isinstance(spec, dict):
        return False
    code = spec.get("code")
    if not isinstance(code, str) or not (10 <= len(code) <= 6000):
        return False
    if _FORBIDDEN.search(code):
        return False
    if not _IMAGE_CALL.search(code):        # must place a real subject
        return False
    try:
        compile(code, "<mechanic>", "exec")
    except SyntaxError:
        return False
    return True


def _mechanic_env(insight, slug):
    """Build the sandbox helpers + preloaded subject images for a mechanic."""
    from PIL import Image, ImageDraw, ImageOps, ImageChops
    items = list(insight.items or [])
    values = [float(p.value) for p in items]
    labels = [p.label for p in items]
    vmax = max(values) if values else 1.0
    # Preload a real subject image per label (photo -> cut-out); best-effort.
    images = {}
    for i, p in enumerate(items):
        import hashlib
        sh = hashlib.sha1((p.label or "").lower().encode()).hexdigest()[:6]
        img = _load_photo(p.label, slug, f"m{i}-{sh}")
        if img is None:
            img = _load_cutout(p.label, slug, f"mc{i}-{sh}")
        images[p.label] = img.convert("RGBA") if img is not None else None

    _extra: dict = {}

    def subject_image(name):
        """Fetch ANY subject the mechanic names (cached), so a new mechanic can
        show things beyond the row labels (a flame, a lung, a droplet)."""
        name = str(name or "").strip()
        if not name:
            return None
        if name in images and images[name] is not None:
            return images[name]
        if name in _extra:
            return _extra[name]
        import hashlib
        sh = hashlib.sha1(name.lower().encode()).hexdigest()[:6]
        img = _load_cutout(name, slug, f"mx-{sh}") or _load_photo(name, slug, f"mp-{sh}")
        img = img.convert("RGBA") if img is not None else None
        _extra[name] = img
        return img

    return dict(values=values, labels=labels, vmax=vmax, n=len(values),
                images=images, subject_image=subject_image,
                _Image=Image, _ImageDraw=ImageDraw, _ImageOps=ImageOps,
                _ImageChops=ImageChops)


def _run_mechanic_frame(code_obj, canvas, base, reveal):
    """Exec the mechanic body for one frame in the sandbox, drawing onto canvas."""
    from PIL import Image, ImageDraw, ImageOps, ImageChops
    d = ImageDraw.Draw(canvas)
    Image, ImageOps, ImageChops = base["_Image"], base["_ImageOps"], base["_ImageChops"]

    def clamp(v, lo=0.0, hi=1.0):
        return lo if v < lo else hi if v > hi else v

    def lerp(a, b, t):
        return a + (b - a) * clamp(t, 0.0, 1.0)

    def rgba(c, a=255):
        # Accept a hex string ("#60A5FA"), an (r,g,b[,a]) tuple, or a palette name.
        if isinstance(c, str):
            return _rgba(c, int(a))
        if isinstance(c, (tuple, list)):
            r, g, b = int(c[0]), int(c[1]), int(c[2])
            return (r, g, b, int(c[3]) if len(c) > 3 else int(a))
        return _rgba(ACCENT, int(a))

    def font(size=48):
        return _pil_font(int(size))

    def text(s, x, y, size=48, color=TEXT, center=False, stroke=4):
        fnt = _pil_font(int(size))
        s = str(s)
        if center:
            bb = d.textbbox((0, 0), s, font=fnt)
            x = x - (bb[2] - bb[0]) / 2
        d.text((int(x), int(y)), s, font=fnt, fill=rgba(color),
               stroke_width=int(stroke), stroke_fill=(5, 8, 15, 255))

    def paste(img, x, y, w=None, h=None):
        if img is None:
            return
        im = img.convert("RGBA")
        if w or h:
            ww = int(w or im.width)
            hh = int(h or im.height)
            im = im.resize((max(1, ww), max(1, hh)))
        canvas.alpha_composite(im, (int(x), int(y)))

    def fill_image(img, frac, x, y, w, h, direction="up", color=None):
        """Reveal a subject filled to `frac` of the box (bottom-up by default) —
        the workhorse for gauges/thermometers/'X% of a thing' mechanics."""
        w, h = int(w), int(h)
        frac = clamp(frac, 0.0, 1.0)
        if img is not None:
            im = ImageOps.fit(img.convert("RGBA"), (w, h))
            if color is not None:                       # optional tint wash
                wash = Image.new("RGBA", (w, h), rgba(color, 90))
                im = Image.alpha_composite(im, wash)
            a = im.split()[3]
            mask = Image.new("L", (w, h), 0)
            md = ImageDraw.Draw(mask)
            fp = int(h * frac)
            if direction == "down":
                md.rectangle([0, 0, w, fp], fill=255)
            elif direction == "left":
                md.rectangle([w - int(w * frac), 0, w, h], fill=255)
            elif direction == "right":
                md.rectangle([0, 0, int(w * frac), h], fill=255)
            else:                                       # up
                md.rectangle([0, h - fp, w, h], fill=255)
            im.putalpha(ImageChops.multiply(a, mask))
            canvas.alpha_composite(im, (int(x), int(y)))
        else:                                           # no image -> rounded fill
            col = color or ACCENT
            fp = int(h * frac)
            d.rounded_rectangle([int(x), int(y + h - fp), int(x + w), int(y + h)],
                                radius=18, fill=rgba(col))

    ns = {"__builtins__": _SAFE_BUILTINS,
          "d": d, "canvas": canvas, "reveal": reveal,
          "W": W, "H": H, "RX0": RX0, "RX1": RX1, "RTOP": RTOP, "RBOT": RBOT,
          "ACCENT": ACCENT, "HIGHLIGHT": HIGHLIGHT, "WARN": WARN, "TEXT": TEXT,
          "clamp": clamp, "lerp": lerp, "rgba": rgba, "font": font, "text": text,
          "paste": paste, "fill_image": fill_image,
          "values": base["values"], "labels": base["labels"],
          "vmax": base["vmax"], "n": base["n"],
          "images": base["images"], "subject_image": base["subject_image"]}
    import math as _math
    ns["math"] = _math
    exec(code_obj, ns)   # noqa: S102 — sandboxed (no builtins/imports; token-scanned)


@_fullframe("mechanic")
def render_procedural(insight, out_dir: Path, slug: str, frames: int = 16):
    """Render an AI-invented procedural mechanic. Returns (pattern, []) or None
    (bad code / it raised / drew nothing) -> caller FALLBACK chain takes over."""
    from PIL import Image
    spec = getattr(insight, "scene", None)
    if not (isinstance(spec, dict) and validate_mechanic(spec)):
        return None
    try:
        code_obj = compile(spec["code"], "<mechanic>", "exec")
    except SyntaxError:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _mechanic_env(insight, slug)
    show_title = bool(spec.get("title", True)) and bool(insight.topic)
    pattern = str(out_dir / f"{slug}_build%02d.png")
    import signal
    have_alarm = hasattr(signal, "SIGALRM")

    def _guard(seconds):
        if have_alarm:
            def _raise(*_a):
                raise TimeoutError("mechanic frame timed out")
            signal.signal(signal.SIGALRM, _raise)
            signal.setitimer(signal.ITIMER_REAL, seconds)

    def _unguard():
        if have_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)

    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        r = 1.0 - (1.0 - r) ** 2
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        try:
            _guard(3.0)
            _run_mechanic_frame(code_obj, canvas, base, r)
            _unguard()
        except Exception as e:  # noqa: BLE001
            _unguard()
            print(f"[mechanic] '{spec.get('mechanic','?')}' failed on frame {f}: "
                  f"{type(e).__name__}: {e}", flush=True)
            return None                     # bail -> deterministic fallback
        if show_title:
            from PIL import ImageDraw
            draw_caption(ImageDraw.Draw(canvas), (RX0, 40, RX1, 40),
                         insight.topic, 1.0, size=50)
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


def mechanic_dry_ok(spec, insight) -> bool:
    """Validate a mechanic by actually rendering ONE frame to a throwaway canvas.
    Cheap, catches runtime errors before we commit the mechanic to a full render."""
    if not validate_mechanic(spec):
        return False
    from PIL import Image
    try:
        code_obj = compile(spec["code"], "<mechanic>", "exec")
        base = _mechanic_env(insight, getattr(insight, "slug", "dry"))
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _run_mechanic_frame(code_obj, canvas, base, 1.0)
        return canvas.getbbox() is not None      # it drew SOMETHING
    except Exception as e:  # noqa: BLE001
        print(f"[mechanic] dry-run rejected: {type(e).__name__}: {e}", flush=True)
        return False
