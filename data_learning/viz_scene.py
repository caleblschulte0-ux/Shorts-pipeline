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

import math as _math
import re
from pathlib import Path

from PIL import Image as _PImg

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
          "unit_figures", "balance", "dot_field", "race_track", "staircase",
          "elevator", "burden", "gauge", "number", "bar", "bubble",
          "caption"}
# Machines that read the WHOLE insight and own their box.
_HOLISTIC = {"orbit_group", "timeline_axis", "race_track", "staircase",
             "elevator", "burden", "gauge"}
_IMAGE_TYPES = {"object", "fill_object", "stack"}
# Elements drawn from the OFFLINE icon library only. They never reach the
# generative provider, so they cost no image budget and cannot time out — the
# reason the scene kit had so little offline range is that every one of its
# subject-bearing types went through `scene_media`.
_ICON_TYPES = {"unit_figures", "dot_field"}
# Drawn entirely from primitives — no subject, no icon, no network at all.
_DRAWN_TYPES = {"balance", "race_track", "staircase", "elevator",
                "burden", "gauge"}
_DATA_TYPES = {"object", "fill_object", "stack", "unit_figures", "balance",
               "dot_field", "number", "bar", "bubble"}
_ANIM = {"fade", "rise", "travel", "count", "fill", "grow"}
_JUST_NUMERIC = __import__("re").compile(r"[\d\s.,:%+\-/]+")
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
_RICH_TYPES = _IMAGE_TYPES | _HOLISTIC | _ICON_TYPES | _DRAWN_TYPES


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
        if t in ("stack", "unit_figures") and not charts._num_or_none(
                (el.get("data") or {}).get("per_value")):
            return False
        if t in _ICON_TYPES and not str(el.get("subject", "")).strip():
            return False
        if t == "dot_field":
            lv = _resolve((el.get("data") or {}).get("value_from"), insight)
            if lv is None or one_in_n(lv[1])[1] <= 0:
                return False       # below ~0.5% there is no honest denominator
        if t == "balance":
            dat = el.get("data") or {}
            # `_resolve(None)` returns the STAR, so an omitted `vs_from` would
            # silently weigh the biggest item against itself and draw a level
            # beam with the same number on both pans — a confident picture of
            # nothing. The key has to be there AND name a different item.
            if "vs_from" not in dat:
                return False
            a = _resolve(dat.get("value_from"), insight)
            b = _resolve(dat.get("vs_from"), insight)
            if a is None or b is None or a[0] == b[0]:
                return False
    # QUALITY GATE: a scene must SHOW something — at least one image/subject
    # element or a holistic time depiction. An abstract-only scene (just a
    # number/caption, or the old bar) is rejected so the director re-picks an
    # image-first depiction instead of shipping the lazy look.
    if not any(e.get("type") in _RICH_TYPES for e in els):
        return False
    return True


def prune(spec, insight):
    """Drop elements that can't bind to this insight, instead of discarding the
    whole scene.

    A scene authored with six rows against five data items used to fail
    `validate` outright and the segment degraded to a bare chart — the exact
    "data stated, not demonstrated" the review gate blocks. One unbindable row
    is not a reason to throw away a good scene; it is a reason to drop the row.
    Returns a new spec, or None if nothing renderable survives.
    """
    if not isinstance(spec, dict) or not isinstance(spec.get("elements"), list):
        return None
    keep = []
    for el in spec["elements"]:
        if not isinstance(el, dict):
            continue
        if el.get("type") in _DATA_TYPES and _resolve(
                (el.get("data") or {}).get("value_from"), insight) is None:
            continue
        keep.append(el)
    if not keep:
        return None
    out = dict(spec)
    out["elements"] = keep[:6]
    return out if validate(out, insight) else None


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


_SCENE_HOST_CACHE: dict = {}


def scene_host(action: str, phase: float):
    """The host as a PIL image, ANIMATED — the pose for this point in the beat.

    Every scene element reached for `charts._host_pose`, which loads ONE fixed
    expression PNG. So in a scene the host has always been a literal sticker:
    the charts give him a performance arc through `_bake_host`, and the scene
    kit — the half of the system meant to be the expressive one — pinned him to
    a single frame for the whole beat.

    That is a look problem and a cadence problem at once. It is what pushed a
    video with two scene visuals to a duplicate ratio of 0.462 against a
    ceiling of 0.45: once an element finishes revealing, a static host means
    the entire frame is static.
    """
    key = (action, round(max(0.0, min(1.0, phase)) * 60) / 60)
    if key in _SCENE_HOST_CACHE:
        return _SCENE_HOST_CACHE[key]
    img = None
    try:
        import io
        from PIL import Image as _PImage
        from . import mascot_director as _md
        svg = _md.compose_anim({"action": action, "prop": "none",
                                "ground": True},
                               charts._perf_phase(key[1]))
        img = _PImage.open(io.BytesIO(_md._rasterise(svg, 300))).convert("RGBA")
    except Exception:  # noqa: BLE001 — a scene must never die over the host
        img = charts._host_pose(action)
    if len(_SCENE_HOST_CACHE) > 400:
        _SCENE_HOST_CACHE.clear()
    _SCENE_HOST_CACHE[key] = img
    return img


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
                side=False, photo=None, phase=1.0):
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
        # SIZE CARRIES THE VALUE. This was a flat bh*0.84 for every row, so a
        # 15.6 and a 73.6 drew the same picture at the same size and only the
        # numeral differed — the literal definition of data stated rather than
        # demonstrated. sqrt keeps the smallest row recognisable while the
        # leader is unmistakably the biggest thing on screen.
        _vr = max(0.0, min(1.0, (value / vmax) if vmax else 1.0))
        _full = bh * (0.40 + 0.44 * (_vr ** 0.5))
        # GROW IN, then hold. An earlier version multiplied this by a sine on
        # the build phase to keep frames non-identical; that pulsing is a
        # shake by another name and it is gone. Motion inside a beat comes from
        # the reveal, the counting numeral and the host's performance.
        _grow = 0.42 + 0.58 * max(0.0, min(1.0, reveal))
        ih = max(8, int(_full * _grow))
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
            im = _fit(cutout, iw, ih)
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
        # Count up with the reveal so the type carries motion too (it landed
        # final-value-on-frame-one before, adding nothing between frames).
        num = _vfmt(value * max(0.0, min(1.0, reveal * 1.06)))
        nf = _pil_font(nfs)
        nb = d.textbbox((0, 0), num, font=nf)
        while nfs > 48 and (nb[2] - nb[0]) > avail:     # shrink number to fit
            nfs -= 8
            nf = _pil_font(nfs)
            nb = d.textbbox((0, 0), num, font=nf)
        _num_top = cy - (nb[3] - nb[1]) - 6
        d.text((nx, _num_top), num, font=nf,
               fill=_rgba(color, int(255 * na)), stroke_width=6,
               stroke_fill=(5, 8, 15, int(255 * na)))
        lfs = 46
        lf = _pil_font(lfs)
        while lfs > 24 and d.textbbox((0, 0), label, font=lf)[2] > avail:
            lfs -= 4                                    # shrink label to fit
            lf = _pil_font(lfs)
        # BELOW the number, clear of its glyph box — the two were overlapping
        # ("2005" printed across "15.6"), which the gate reads as collided type.
        # Anchored to the numeral's real glyph bottom. A fixed offset from the
        # row centre printed the year straight through the value.
        d.text((nx, _num_top + nb[3] + 10), label, font=lf,
               fill=(248, 250, 252, int(255 * na)), stroke_width=3,
               stroke_fill=(5, 8, 15, int(255 * na)))
        return {"value": float(value), "cx": float(nx + (nb[2] - nb[0]) / 2),
                "cy": float(cy - (nb[3] - nb[1]) / 2), "w": 240.0, "h": 120.0}
    # A 4.7x difference in the data compressed to 1.55x on screen under the old
    # 0.55..1.00 mapping — the objects read as the same size and the number did
    # all the work, which is exactly the "stated, not demonstrated" block. A
    # sqrt mapping over a wider range keeps the small one legible while making
    # the big one unmistakably bigger.
    _r = (value / vmax) if vmax else 1.0
    frac = 0.30 + 0.70 * (max(0.0, min(1.0, _r)) ** 0.5)
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


def unit_plan(value: float, per_value: float, cap: int = 60) -> tuple:
    """How many figures to draw, and what each one is worth.

    An isotype is only readable in a narrow band of counts: three icons is a
    weak picture and ninety is wallpaper you cannot count. The AUTHORED
    `per_value` is honoured when it lands in that band; when it does not, the
    unit is re-scaled to a round number (1, 2, 5, 10, 25, 50, ...) that does.
    The value never changes — only how it is packaged — and the legend states
    the unit, so the picture stays exactly as true as the number.
    """
    per = abs(float(per_value or 0)) or 1.0
    v = abs(float(value))
    # ALWAYS a round unit. Honouring the authored `per_value` produced legends
    # like "each = $24.9K", which is a worse thing to read than the raw number
    # it was meant to make friendly. A count is only easier than a figure when
    # the unit is something a person holds in their head.
    best = None
    step = 10.0 ** -6
    while step <= max(v, 1.0) * 10.0:
        for mult in (1.0, 2.0, 5.0):
            cand = step * mult
            k = int(round(v / cand))
            if 6 <= k <= cap:
                # Prefer counts near 18 — enough to read as "a lot", few enough
                # to actually count, and it tiles into a tidy block.
                score = abs(k - 18)
                if best is None or score < best[0]:
                    best = (score, k, cand)
        step *= 10.0
    if best is not None:
        return best[1], best[2]
    k = int(round(v / per))
    return max(1, min(cap, k)), per


def draw_unit_figures(d, canvas, box, cutout, value, per_value, label, color,
                      reveal, unit=""):
    """AN ISOTYPE: N copies of one thing, where counting them IS the number.

    This is the oldest non-chart way to show a quantity and the channel had no
    version of it. `stack` is the closest thing and it tiles at most EIGHT
    copies up a single column, which reads as a totem rather than a count.

    The figures appear one at a time across the build, so the count is
    something the viewer watches happen rather than a block that fades in —
    which is also honest motion for the whole span, not a decoration bolted on
    to satisfy the cadence gate.
    """
    bx0, by0, bx1, by1 = box
    n, per = unit_plan(value, per_value)
    # The scene's TOPIC caption is drawn at y=250 by render_scene, and the first
    # version of this started the grid at by0+120 — so the title landed on the
    # first row of houses. Start below it; the value line goes above it.
    top = max(by0 + 120, 320)
    bot = by1 - 110                              # room for the legend
    bw, bh = max(1, bx1 - bx0), max(1, bot - top)
    # Choose a column count whose cell is as square as possible, so the block
    # reads as a group rather than a line or a tower.
    best, cols = None, 1
    for c in range(1, min(n, 12) + 1):
        rows = -(-n // c)
        cw, chh = bw / c, bh / rows
        score = abs(cw - chh) + max(0.0, 90.0 - min(cw, chh)) * 4
        if best is None or score < best:
            best, cols = score, c
    rows = -(-n // cols)
    cell_w, cell_h = bw / cols, bh / rows
    side = int(min(cell_w, cell_h) * 0.84)
    if side < 12:
        return None
    icon = _fit(cutout, side, side) if cutout is not None else None
    gx = bx0 + (bw - cols * cell_w) / 2.0
    gy = top + (bh - rows * cell_h) / 2.0
    # A CASCADE, NOT A METRONOME.
    #
    # One icon popping in per slot left every frame between arrivals identical
    # to the last — 22 figures over 5.8s is an arrival every ~8 frames, so
    # seven frames in eight were duplicates and the video hit a duplicate ratio
    # of 0.465 against a 0.45 ceiling. Each figure now FADES over a window that
    # overlaps its neighbours', so three or four are always in flight and no
    # two frames of the fill are the same. It also simply looks better: a
    # cascade rather than a tick.
    prog = max(0.0, min(1.0, reveal))
    # Starts spread across 88% of the visual, each fade about one slot long.
    # An overlap of 3 was the first try and it was worse than the pop it
    # replaced: with three figures sharing every fade, each one's per-frame
    # change fell under the detector's threshold and the last icons crawled to
    # full opacity, leaving a 29-frame still stretch at the end. One snappy
    # arrival at a time is both the stronger signal and the better cascade.
    fill_by = 0.88
    span = fill_by / max(1, n)
    overlap = 1.3                                # figures fading at any moment
    cx_last = cy_last = None
    for k in range(n):
        a = (prog - k * span) / (span * overlap)
        if a <= 0.0:
            break
        a = min(1.0, a)
        rr, cc = divmod(k, cols)
        x = int(gx + cc * cell_w + (cell_w - side) / 2.0)
        y = int(gy + rr * cell_h + (cell_h - side) / 2.0)
        if icon is not None:
            im = icon
            if a < 0.995:
                im = icon.copy()
                im.putalpha(im.getchannel("A").point(
                    lambda v, _a=a: int(v * _a)))
            canvas.alpha_composite(im, (x, y))
        else:
            d.ellipse([x, y, x + side, y + side],
                      fill=_rgba(color, int(235 * a)))
        if a > 0.5:
            cx_last, cy_last = x + side // 2, y + side // 2
    # THE LEGEND IS THE HONESTY. Without "each = 50" the picture is a pile of
    # icons that could mean anything, which is the "what am I looking at"
    # failure in its purest form.
    each = charts._ulabel(per, unit)
    d.text((_cx(box), bot + 34), f"each  =  {each}", font=_pil_font(44),
           fill=_rgba(TEXT, int(255 * min(1.0, reveal * 2))), anchor="mm")
    total = charts._ulabel(value, unit, group=True)
    d.text((_cx(box), by0 + 58), f"{label}   {total}", font=_pil_font(60),
           fill=_rgba(color, int(255 * min(1.0, max(0.0, reveal - 0.25) * 2))),
           anchor="mm")
    if cx_last is None:
        return None
    # BAKE THE HOST ONTO THE COUNT.
    #
    # `render_scene` sets `insight.host_baked = True` for every scene, which
    # suppresses the travelling overlay — so an element that draws no host
    # ships a beat with NO host at all. The first render of this did exactly
    # that, and a hostless beat is what the showrunner records as the mascot
    # being decorative or missing.
    #
    # He stands on the figure that just landed, so he ADVANCES along the block
    # as the count grows: contact for STRICT_CONTACT, and honest motion for the
    # whole build rather than a sprite parked in a corner.
    host = scene_host("point", reveal)
    if host is not None:
        mh = int(max(150, min(300, side * 1.7)))
        mw = int(host.width * mh / host.height)
        hx = int(min(max(cx_last + side * 0.55, 8), W - mw - 8))
        hy = int(cy_last - side // 2 - mh + side * 0.30)
        canvas.alpha_composite(_fit(host, mw, mh), (hx, max(0, hy)))
    return (value, "art", cx_last, cy_last)


def balance_tilt(a: float, b: float, limit: float = 26.0) -> float:
    """Beam angle in degrees for a vs b, positive = a is heavier (a side down).

    tanh of the LOG ratio, so the tilt reads proportionally at every scale: a
    2x difference and a 200x difference must not both bottom the beam out, or
    the picture stops carrying information the moment it is most interesting.
    Equal values sit dead level, which is itself the finding on a "these are
    the same" beat.
    """
    a, b = abs(float(a)), abs(float(b))
    if a <= 0 or b <= 0:
        return 0.0 if a == b else (limit if a > b else -limit)
    return float(limit * _math.tanh(_math.log(a / b)))


def draw_balance(d, canvas, box, value, other, label, other_label, color,
                 reveal, unit="", cutout=None):
    """A SET OF SCALES: two pans, tipping by how the numbers actually compare.

    A comparison drawn as two bars asks the viewer to measure two lengths
    against an axis. A balance states the same fact as a physical outcome —
    this side went down — which needs no axis, no gridline and no reading.
    It is the clearest non-chart form the kit has for exactly two numbers, and
    it is the shape a two-item beat kept being forced into a chart to show.
    """
    bx0, by0, bx1, by1 = box
    cx = (bx0 + bx1) // 2
    pivot_y = by0 + int((by1 - by0) * 0.38)
    arm = int(min((bx1 - bx0) * 0.36, 350))
    # Level, then settle into the true tilt — the tip IS the reveal, so the
    # element animates for the whole span without anything decorative added.
    #
    # See `settle`: linear-ish and still moving at the end. A cubic-out here
    # left a 6-second visual's back half a fraction of a degree from still.
    ease = settle(reveal)
    ang = _math.radians(balance_tilt(value, other) * ease)
    dx, dy = _math.cos(ang) * arm, _math.sin(ang) * arm
    # HEAVY SIDE GOES DOWN. The first version had the signs the other way and
    # drew $449K riding UP over $270K — a picture that states the opposite of
    # the data, which is the worst thing this kit can do and is invisible to
    # every test that only asks whether something rendered.
    lx, ly = int(cx - dx), int(pivot_y + dy)          # left pan hangs here
    rx, ry = int(cx + dx), int(pivot_y - dy)
    # the stand
    d.polygon([(cx, pivot_y), (cx - 46, by1 - 150), (cx + 46, by1 - 150)],
              fill=_rgba(TEXT, 90))
    d.line([(cx - 120, by1 - 150), (cx + 120, by1 - 150)],
           fill=_rgba(TEXT, 120), width=12)
    d.line([(lx, ly), (rx, ry)], fill=_rgba(TEXT, 220), width=14)
    d.ellipse([cx - 18, pivot_y - 18, cx + 18, pivot_y + 18],
              fill=_rgba(TEXT, 230))
    hi = value >= other
    for (px, py, val, lab, heavy) in ((lx, ly, value, label, hi),
                                      (rx, ry, other, other_label, not hi)):
        col = color if heavy else ACCENT
        d.line([(px, py), (px, py + 78)], fill=_rgba(TEXT, 150), width=6)
        pan_w = 210
        d.rounded_rectangle([px - pan_w // 2, py + 78, px + pan_w // 2, py + 118],
                            radius=18, fill=_rgba(col, 235))
        # The numbers are up almost immediately. They used to fade in over
        # reveal 0.2-0.7, which left the first fifth of the visual as a nearly
        # level beam with two empty pans — a frame that tells you nothing while
        # the narration is already talking about the comparison.
        na = max(0.0, min(1.0, (reveal - 0.04) / 0.16))
        # The figures COUNT UP as the pans settle, so the largest text on the
        # card is changing every frame of the tip rather than fading in once.
        # It lands on the exact value and holds it — a mid-count that outlived
        # the animation would be a number the script never says.
        # On the SAME curve as the tip. This had its own ease-out, so the
        # largest text on the card stopped changing before the pans did — the
        # identical defect one line away from where it was just fixed.
        shown_v = val * ease
        d.text((px, py + 168), charts._ulabel(shown_v, unit, group=True),
               font=_pil_font(72), fill=_rgba(col, int(255 * na)), anchor="mm")
        d.text((px, py + 234), str(lab)[:18], font=_pil_font(44),
               fill=_rgba(TEXT, int(230 * na)), anchor="mm")
    # THE HOST RIDES THE HEAVY PAN. `render_scene` marks every scene
    # host_baked, which suppresses the travelling overlay — so an element that
    # draws no host ships a beat with none at all.
    host = scene_host("cheer" if hi else "point", reveal)
    if host is not None:
        mh = 230
        mw = int(host.width * mh / host.height)
        hx, hy = (lx, ly) if hi else (rx, ry)
        canvas.alpha_composite(
            _fit(host, mw, mh),
            (int(min(max(hx - mw // 2, 8), W - mw - 8)), int(hy + 78 - mh)))
    return (value, "art", int(lx), int(ly + 98))


def one_in_n(pct: float, cap: int = 100) -> tuple:
    """A percentage as "k out of n", with n a number people say out loud.

    6.8% is a figure; "7 in 100" is a mental picture, and "1 in 15" is a
    sentence. Tries the denominators people actually use, smallest first, and
    keeps the first whose rounding error is under half a person — so the
    picture is never a rounder claim than the data supports. Falls back to
    /100, which is what a percentage already is.
    """
    p = abs(float(pct))
    if p <= 0:
        return 0, 0
    for n in (10, 20, 25, 50, 100):
        k = int(round(p * n / 100.0))
        if k < 1:
            continue                       # nothing lit is not a picture
        shown = k * 100.0 / n
        # The picture may ROUND, it may not RESTATE. Half a percentage point,
        # absolute — a RELATIVE bound was the first attempt and it let 66.7%
        # render as "7 in 10" and 33.3% as "8 in 25", because 5% of a big
        # percentage is a lot of percentage points. The exact figure is printed
        # underneath either way.
        if abs(shown - p) <= 0.5:
            return k, n
    # Below about half a percent there is no denominator a person says out
    # loud that also fits on screen. Refuse rather than draw "0 in 100", which
    # is what the first version did for 0.4%.
    return 0, 0


def draw_dot_field(d, canvas, box, cutout, value, label, color, reveal,
                   unit="", denom=None):
    """"k IN n": a field of figures with k of them lit.

    The form a rate WANTS. A percentage on a bar asks the viewer to hold an
    abstraction; a field of a hundred people with seven of them coloured in is
    the same fact as a thing you can see and count, and it is the classic
    non-chart depiction the kit had no version of.
    """
    bx0, by0, bx1, by1 = box
    k, n = one_in_n(value) if denom is None else (
        int(round(abs(value) * denom / 100.0)), int(denom))
    if n <= 0 or k < 0:
        return None
    top, bot = max(by0 + 120, 320), by1 - 110
    bw, bh = max(1, bx1 - bx0), max(1, bot - top)
    cols = int(round(_math.sqrt(n * bw / max(1.0, bh))))
    cols = max(1, min(n, cols))
    rows = -(-n // cols)
    cell_w, cell_h = bw / cols, bh / rows
    side = int(min(cell_w, cell_h) * 0.78)
    if side < 8:
        return None
    icon = _fit(cutout, side, side) if cutout is not None else None
    gx = bx0 + (bw - cols * cell_w) / 2.0
    gy = top + (bh - rows * cell_h) / 2.0
    lit_now = max(0.0, min(1.0, reveal * 1.35)) * k    # the lit ones fill in
    cx_last = cy_last = None
    for i in range(n):
        rr, cc = divmod(i, cols)
        x = int(gx + cc * cell_w + (cell_w - side) / 2.0)
        y = int(gy + rr * cell_h + (cell_h - side) / 2.0)
        lit = i < int(lit_now)
        # LIT AND UNLIT MUST NOT BE THE SAME PICTURE AT DIFFERENT OPACITY.
        # The first version ghosted the icon to 20% alpha and the field read as
        # a hundred identical houses — the one thing the form exists to show
        # (which ones) was the thing you could not see. The unlit are now a
        # flat dim disc: a different SHAPE, not a fainter copy.
        if lit and icon is not None:
            canvas.alpha_composite(icon, (x, y))
        elif lit:
            d.ellipse([x, y, x + side, y + side], fill=_rgba(color, 240))
        else:
            pad = int(side * 0.14)
            d.ellipse([x + pad, y + pad, x + side - pad, y + side - pad],
                      fill=_rgba(TEXT, 38))
        if lit:
            cx_last, cy_last = x + side // 2, y + side // 2
    na = max(0.0, min(1.0, (reveal - 0.2) / 0.4))
    d.text((_cx(box), by0 + 58), f"{k} in {n}", font=_pil_font(78),
           fill=_rgba(color, int(255 * na)), anchor="mm")
    d.text((_cx(box), bot + 40), f"{label}   {charts._ulabel(value, unit)}",
           font=_pil_font(44), fill=_rgba(TEXT, int(235 * na)), anchor="mm")
    host = scene_host("point", reveal)
    if host is not None and cx_last is not None:
        mh = int(max(150, min(280, side * 2.2)))
        mw = int(host.width * mh / host.height)
        canvas.alpha_composite(
            _fit(host, mw, mh),
            (int(min(max(cx_last + side * 0.6, 8), W - mw - 8)),
             int(max(0, cy_last - side // 2 - mh + side * 0.3))))
    if cx_last is None:
        return None
    return (value, "art", cx_last, cy_last)


def _series_points(insight, cap: int = 8):
    """The data points a time machine walks through, oldest first, capped."""
    items = list(getattr(insight, "items", None) or [])
    if len(items) > cap:                       # keep the ends, thin the middle
        step = (len(items) - 1) / (cap - 1)
        items = [items[int(round(i * step))] for i in range(cap)]
    return items


def draw_staircase(d, canvas, box, insight, color, reveal, unit=""):
    """A STAIRCASE: progress becomes height, and Data climbs it.

    For a series that rises. A line chart asks the viewer to read a slope; a
    staircase says "he had to climb this", and the climb is the same motion the
    cadence gate wants — he is moving for the whole visual because the data is.
    """
    items = _series_points(insight)
    if len(items) < 3:
        return None
    vals = [float(getattr(p, "value", 0) or 0) for p in items]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    bx0, by0, bx1, by1 = box
    top, bot = max(by0 + 200, 340), by1 - 120
    n = len(items)
    w = (bx1 - bx0 - 160) / n
    x0 = bx0 + 80
    # Steps rise as the reveal walks along them, so the staircase BUILDS.
    e = max(0.0, min(1.0, reveal))
    shown = e * n
    top_xy = None
    for i, (p, v) in enumerate(zip(items, vals)):
        a = max(0.0, min(1.0, shown - i))
        if a <= 0.0:
            break
        # A floor of 12% keeps the first step visible on a series whose low
        # point is its start — otherwise the climb begins from nothing and the
        # first third of the visual is an empty frame.
        frac = 0.12 + 0.88 * ((v - lo) / span)
        h = (bot - top) * frac * a
        sx = int(x0 + i * w)
        sy = int(bot - h)
        d.rounded_rectangle([sx + 6, sy, int(sx + w - 6), bot], radius=10,
                            fill=_rgba(color if i == n - 1 else ACCENT,
                                       int(235 * a)))
        if a > 0.6:
            # The last step carries the host, so its value moves to the side
            # rather than sitting under his feet where he covers it.
            vx = int(sx + w / 2) if i < n - 1 else int(sx - 12)
            va = "mm" if i < n - 1 else "rm"
            d.text((vx, sy - 30), charts._ulabel(v, unit),
                   font=_pil_font(34), fill=_rgba(TEXT, 235), anchor=va)
            d.text((int(sx + w / 2), bot + 34),
                   str(getattr(p, "label", ""))[:6], font=_pil_font(30),
                   fill=_rgba(TEXT, 190), anchor="mm")
            top_xy = (int(sx + w / 2), sy)
    host = scene_host("climb", reveal)
    if host is not None and top_xy is not None:
        mh = int(min(280, (bot - top) * 0.34))
        mw = int(host.width * mh / host.height)
        canvas.alpha_composite(
            _fit(host, mw, mh),
            (int(min(max(top_xy[0] - mw // 2, 8), W - mw - 8)),
             int(top_xy[1] - mh + 10)))
    return (vals[-1], "art", top_xy[0], top_xy[1]) if top_xy else None


def draw_elevator(d, canvas, box, insight, color, reveal, unit=""):
    """AN ELEVATOR: the value is a floor, and Data rides it down.

    For a series that falls. A descending line is a fact; a lift dropping past
    labelled floors is a place he ends up, and the car is travelling for the
    whole visual.
    """
    items = _series_points(insight, cap=6)
    if len(items) < 3:
        return None
    vals = [float(getattr(p, "value", 0) or 0) for p in items]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    bx0, by0, bx1, by1 = box
    top, bot = max(by0 + 200, 340), by1 - 110
    sx0 = int((bx0 + bx1) / 2 - 190)
    sx1 = sx0 + 380
    d.rounded_rectangle([sx0, top, sx1, bot], radius=18,
                        outline=_rgba(TEXT, 90), width=5)
    for i, (p, v) in enumerate(zip(items, vals)):
        fy = int(bot - (bot - top) * ((v - lo) / span) * 0.86 - 40)
        d.line([(sx0 + 10, fy), (sx1 - 10, fy)], fill=_rgba(TEXT, 55), width=3)
        d.text((sx1 + 22, fy), f"{getattr(p, 'label', '')}  "
               f"{charts._ulabel(v, unit)}", font=_pil_font(32),
               fill=_rgba(TEXT, 200), anchor="lm")
    # The car travels through the whole series, ending on the last value.
    e = max(0.0, min(1.0, reveal))
    pos = e * (len(vals) - 1)
    i0 = min(int(pos), len(vals) - 2)
    frac = pos - i0
    v = vals[i0] + (vals[i0 + 1] - vals[i0]) * frac
    cy = int(bot - (bot - top) * ((v - lo) / span) * 0.86 - 40)
    ch = 150
    d.rounded_rectangle([sx0 + 16, cy - ch // 2, sx1 - 16, cy + ch // 2],
                        radius=14, fill=_rgba(color, 235))
    host = scene_host("point", reveal)
    if host is not None:
        mh = ch - 18
        mw = int(host.width * mh / host.height)
        canvas.alpha_composite(_fit(host, mw, mh),
                               (int((sx0 + sx1) / 2 - mw // 2), cy - mh // 2))
    return (vals[-1], "art", int((sx0 + sx1) / 2), cy)


def draw_burden(d, canvas, box, insight, color, reveal, unit=""):
    """A LOAD HE HOLDS UP: a cost is weight, and the weight is on him.

    For money going up. "$480K" is a number; a slab pressing down on him that
    grows until he is buckling is the same number as a feeling, which is the
    whole reason to have a mascot.

    It is a load ABOVE him rather than a pack on his back, and that is a rig
    constraint honestly accommodated rather than fought. Three versions tried
    to put bricks on his back — beside him, overlapping him, in a pack behind
    him — and every one read as a bar chart standing next to a mascot, because
    the sprite faces FORWARD and a front-facing character cannot wear a
    rucksack. He can visibly strain under something on top of him, and the
    director already has the pose for it (`hoist_stack`: arms pressed overhead
    against the underside of a load).
    """
    items = _series_points(insight, cap=10)
    if len(items) < 2:
        return None
    vals = [float(getattr(p, "value", 0) or 0) for p in items]
    lo, hi = min(vals), max(vals)
    bx0, by0, bx1, by1 = box
    cx = (bx0 + bx1) // 2
    ground = by1 - 130
    e = max(0.0, min(1.0, reveal))
    pos = e * (len(vals) - 1)
    i0 = min(int(pos), len(vals) - 2)
    v = vals[i0] + (vals[i0 + 1] - vals[i0]) * (pos - i0)
    lab = getattr(items[min(int(round(pos)), len(items) - 1)], "label", "")
    frac = (v - lo) / ((hi - lo) or 1.0)
    # The slab is the LOAD: its thickness is the value against the range, so
    # the picture is the increase. The exact figure is in the line above.
    n_slabs = max(1, int(round(1 + frac * 7)))
    host = scene_host("hoist_stack", reveal)
    mh = 430
    mw = int(host.width * mh / host.height) if host is not None else 280
    # He SINKS as it gets heavier — the knees give, so the load descends on him
    # rather than the frame just gaining bricks at the top.
    sink = int(70 * frac)
    hy = ground - mh + sink
    if host is not None:
        canvas.alpha_composite(_fit(host, mw, mh), (int(cx - mw // 2), hy))
    # The load sits ON HIS HANDS. `hoist_stack` puts them at y=45 in the rig's
    # 0-470 space — about a tenth of the way down the sprite — so anchoring the
    # stack to the image's top edge left a visible gap between him and the
    # thing he is supposed to be holding up.
    sw, sh, gap = int(mw * 1.55), 34, 7
    hands_y = hy + int(mh * 0.095)
    for k in range(n_slabs):
        sy = hands_y - sh - k * (sh + gap)
        d.rounded_rectangle([int(cx - sw // 2), sy, int(cx + sw // 2), sy + sh],
                            radius=9,
                            fill=_rgba(color if k == n_slabs - 1 else ACCENT, 240),
                            outline=_rgba(charts.CARD, 255), width=3)
    d.text((cx, by0 + 58), f"{lab}   {charts._ulabel(v, unit, group=True)}",
           font=_pil_font(76), fill=_rgba(color, 255), anchor="mm")
    d.text((cx, ground + 52), "what he's carrying", font=_pil_font(38),
           fill=_rgba(TEXT, 200), anchor="mm")
    return (v, "art", cx, hy - 18)


def draw_gauge(d, canvas, box, insight, color, reveal, unit=""):
    """A DIAL: a rate is a needle, and it sweeps.

    A percentage on a bar is an abstraction. A needle climbing toward a red
    zone is a speed, and it is moving every frame it is on screen.
    """
    items = list(getattr(insight, "items", None) or [])
    if not items:
        return None
    star = max(items, key=lambda p: abs(float(getattr(p, "value", 0) or 0)))
    v = float(getattr(star, "value", 0) or 0)
    vmax = max(abs(v) * 1.35, 1e-6)
    bx0, by0, bx1, by1 = box
    cx = (bx0 + bx1) // 2
    cy = max(by0 + 430, 620)
    R = int(min((bx1 - bx0) * 0.36, 320))
    a0, sweep = 200.0, 140.0                    # a车-style dial, open at the top
    d.arc([cx - R, cy - R, cx + R, cy + R], a0, a0 + sweep,
          fill=_rgba(TEXT, 70), width=26)
    # the red zone — the last fifth of the dial
    d.arc([cx - R, cy - R, cx + R, cy + R], a0 + sweep * 0.8, a0 + sweep,
          fill=_rgba(WARN, 200), width=26)
    e = settle(reveal)
    ang = _math.radians(a0 + sweep * (abs(v) / vmax) * e)
    nx, ny = cx + _math.cos(ang) * (R - 40), cy + _math.sin(ang) * (R - 40)
    d.line([(cx, cy), (int(nx), int(ny))], fill=_rgba(color, 255), width=14)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=_rgba(TEXT, 235))
    shown = v * e
    d.text((cx, cy + 96), charts._ulabel(shown, unit, group=True),
           font=_pil_font(96), fill=_rgba(color, 255), anchor="mm")
    d.text((cx, cy + 176), str(getattr(star, "label", ""))[:22],
           font=_pil_font(40), fill=_rgba(TEXT, 220), anchor="mm")
    host = scene_host("point", reveal)
    if host is not None:
        mh = 230
        mw = int(host.width * mh / host.height)
        canvas.alpha_composite(_fit(host, mw, mh),
                               (int(cx + R * 0.55), int(cy - mh * 0.2)))
    return (v, "art", int(nx), int(ny))


def settle(reveal: float) -> float:
    """A machine's motion curve: 0 to 1, and STILL MOVING at the end.

    Every machine here animates by driving some geometry with the reveal, and
    the obvious choice — an ease-out — is wrong for this pipeline. Its slope at
    the end is nearly zero, so the last third of a visual moves by fractions of
    a pixel per frame, which is below the cadence detector's threshold and is,
    correctly, read as a frozen frame. It cost the balance a video and then the
    race a video, with an identical-looking curve each time.

    So: mostly linear, with enough shape to read as a surge out of the blocks.
    The end slope is what matters and it is tested.
    """
    r = max(0.0, min(1.0, float(reveal)))
    return 0.72 * r + 0.28 * (1.0 - (1.0 - r) ** 2)


def draw_race(d, canvas, box, insight, color, reveal, unit=""):
    """A RACE: rank becomes position, and the gap becomes literal distance.

    A ranked bar chart asks the viewer to compare five lengths against an axis.
    A race asks them to see who is in front, which they can do before reading
    anything. It is also the form that solves the cadence problem honestly —
    the runners are still moving for the whole visual, so nothing has to be
    kept alive with camera tricks.

    Every runner is Data. The channel's identity is a mascot in a world where
    numbers are physical, and "five clones racing, ours in the lead" is that,
    where five coloured rectangles is Bloomberg with a TikTok account.
    """
    items = _ordered_items(insight)[:8]
    if len(items) < 2:
        return None
    vals = [float(getattr(p, "value", 0) or 0) for p in items]
    vmax = max(vals) or 1.0
    bx0, by0, bx1, by1 = box
    top = max(by0 + 190, 330)
    bot = by1 - 90
    n = len(items)
    lane_h = (bot - top) / n
    # Room for the longest NAME on the left and for the leader's VALUE on the
    # right. The first version guessed both and clipped both — "Los Angeles"
    # rendered as "os Angeles" and the leader's "11.3 yrs" ran off the edge.
    name_f = _pil_font(38)
    name_w = max((d.textbbox((0, 0), str(getattr(p, "label", ""))[:16],
                             font=name_f)[2] for p in items), default=0)
    x0 = int(bx0 + min(max(name_w + 40, 200), (bx1 - bx0) * 0.42))
    x1 = int(bx1 - 40)                   # the finish line
    # Ease so the field surges out of the blocks and settles into its order,
    # rather than sliding at a constant rate like a loading bar.
    e = settle(reveal)
    runner = scene_host("cheer", reveal)
    rh = int(max(96, min(170, lane_h * 0.86)))
    rw = int(runner.width * rh / runner.height) if runner is not None else rh
    # the finish line
    for k in range(0, int(bot - top), 26):
        d.rectangle([x1, top + k, x1 + 14, top + min(k + 13, int(bot - top))],
                    fill=_rgba(TEXT, 190 if (k // 26) % 2 == 0 else 60))
    lead_xy = None
    for i, (p, v) in enumerate(zip(items, vals)):
        cy = int(top + lane_h * (i + 0.5))
        d.line([(x0, cy + rh // 2 - 2), (x1, cy + rh // 2 - 2)],
               fill=_rgba(TEXT, 40), width=4)
        px = int(x0 + (v / vmax) * (x1 - x0) * e)
        lead = (i == 0)
        col = color if lead else ACCENT
        d.text((x0 - 22, cy), str(getattr(p, "label", ""))[:16],
               font=name_f, fill=_rgba(col, 240), anchor="rm")
        if runner is not None:
            im = runner
            if not lead:
                # The field is ghosted so the leader reads instantly; without
                # it five identical sprites are a crowd, not a ranking.
                im = runner.copy()
                im.putalpha(im.getchannel("A").point(lambda a: int(a * 0.62)))
            canvas.alpha_composite(_fit(im, rw, rh),
                                   (int(px - rw // 2), int(cy - rh // 2)))
        else:
            d.ellipse([px - 26, cy - 26, px + 26, cy + 26], fill=_rgba(col, 235))
        na = max(0.0, min(1.0, (reveal - 0.25) / 0.35))
        vf = _pil_font(44)
        vtxt = charts._ulabel(v, unit)
        vw = d.textbbox((0, 0), vtxt, font=vf)[2]
        # Ahead of the runner, unless that would cross the finish line — then
        # it rides behind them instead. A runner near the line is exactly the
        # one whose number the viewer most wants to read.
        if px + rw // 2 + 16 + vw < x1:
            d.text((px + rw // 2 + 16, cy), vtxt, font=vf,
                   fill=_rgba(col, int(255 * na)), anchor="lm")
        else:
            d.text((px - rw // 2 - 16, cy), vtxt, font=vf,
                   fill=_rgba(col, int(255 * na)), anchor="rm")
        if lead:
            lead_xy = (px, cy)
    return (vals[0], "art", lead_xy[0], lead_xy[1]) if lead_xy else None


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
    pb, pt = int(H * 0.80), int(H * 0.30)       # baseline low / ceiling — fills
    #                                             the lower frame (no dead third)
    unit = insight.unit

    def X(yr):
        return px0 + (yr - y0v) / span_x * (px1 - px0)

    def Y(v):
        return pb - (v / vmax) * (pb - pt)

    r = reveal                                  # already linear from render_scene
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
    host = scene_host("point" if bars else "cheer", r)
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
    host = scene_host("cheer", reveal)
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


def units_scene(insight) -> dict:
    """A COUNT of one thing, drawn as that thing, N times.

    The channel's offline scene vocabulary was two builders plus a bare
    timeline axis, so every time-series story got the identical picture and
    every ranking fell through to a chart. This one costs no image budget and
    cannot time out — it draws from the deterministic icon library — so it can
    be reached on any story, which is the whole point of it existing.

    `per_value` is a first guess only; `unit_plan` re-scales it to whatever
    puts the count in a readable band, and the legend states the result.
    """
    star = max(insight.items, key=lambda p: abs(p.value)) if insight.items else None
    if star is None:
        return {}
    subject = icon_subject(insight)
    return {"title": True,
            "elements": [{"type": "unit_figures", "region": "full",
                          "subject": subject,
                          "data": {"value_from": "star",
                                   "per_value": abs(star.value) / 18.0 or 1.0},
                          "anim": "count"}]}


# "7 in 100" only means anything when the percentage is a SHARE OF A COUNTABLE
# POPULATION. The first version keyed off the unit alone and produced a field of
# a hundred houses with seven lit for a 6.8% MORTGAGE INTEREST RATE — which is
# not seven houses in a hundred, or seven of anything. A percent sign is not a
# licence to draw a population; an interest rate, a growth rate, a change and a
# yield are all percentages of something that cannot be counted out in figures.
_SHARE_PHRASE = re.compile(
    r"\b(share|proportion|percent(age)? of|of all|of every|of american|"
    r"of household|of adult|of women|of men|of children|of worker|"
    r"of student|of famil|of people|of population|of voter|of driver|"
    r"of home|of car|of job)\w*", re.I)


def rate_scene(insight) -> dict:
    """A share of a population as "k in n" — never any other kind of percent.

    Lighting 7 of 100 figures says "seven of every hundred OF THEM". That is
    true of a prevalence, a turnout or an ownership share, and false of an
    interest rate, a growth rate or a yield, so the claim has to say which one
    it is before this form is allowed.
    """
    unit = (getattr(insight, "unit", "") or "").strip().lower()
    if unit not in ("percent", "%", "rate", "pct"):
        return {}
    text = f"{getattr(insight, 'topic', '')} {getattr(insight, 'main_insight', '')}"
    if not _SHARE_PHRASE.search(text or ""):
        return {}
    star = max(insight.items, key=lambda p: abs(p.value)) if insight.items else None
    if star is None or one_in_n(star.value)[1] <= 0:
        return {}
    # THE FIGURES ARE WHAT THE SHARE IS A SHARE OF.
    #
    # `icon_subject` picks by topic keyword and handed "teen licensing" an ICE
    # CUBE, which is a confident picture of nothing. What the field is counting
    # is stated right there in the share phrase that allowed this form at all,
    # so read it from there and default to people — because a share of a
    # population is a share of people unless it says otherwise.
    # Scan the WHOLE claim, not just the matched phrase: "Share of households
    # that own" matches on "share" and the noun is three words later, so
    # reading only the match handed a households story a field of people.
    low = (text or "").lower()
    subject = "people"
    for word, noun in (("household", "household"), ("home", "household"),
                       ("driver", "car"), ("car", "car"), ("worker", "worker"),
                       ("job", "worker"), ("student", "student")):
        if word in low:
            subject = noun
            break
    return {"title": True,
            "elements": [{"type": "dot_field", "region": "full",
                          "subject": subject,
                          "data": {"value_from": "star"}, "anim": "fill"}]}


def _machine_scene(kind: str, need: int = 3):
    def build(insight) -> dict:
        if len(list(getattr(insight, "items", None) or [])) < need:
            return {}
        return {"title": True,
                "elements": [{"type": kind, "region": "full", "anim": "grow"}]}
    return build


# Each takes the whole insight and needs no parameters — the relationship
# router already decided this is the right picture, so there is nothing left
# for a builder to choose.
staircase_scene = _machine_scene("staircase", 3)
elevator_scene = _machine_scene("elevator", 3)
burden_scene = _machine_scene("burden", 2)
gauge_scene = _machine_scene("gauge", 1)


def race_scene(insight) -> dict:
    """A ranking, run as a race. Needs a real field — two runners is a duel and
    belongs on the scales, one is not a race at all."""
    items = list(insight.items or [])
    if not (3 <= len(items) <= 8):
        return {}
    return {"title": True,
            "elements": [{"type": "race_track", "region": "full",
                          "anim": "travel"}]}


def balance_scene(insight) -> dict:
    """Two numbers, weighed against each other.

    Only ever built for a genuine PAIR. Putting five metros on a two-pan scale
    would mean silently dropping three of them, which is a chart that lies by
    omission rather than a picture.
    """
    items = list(insight.items or [])
    if len(items) < 2:
        return {}
    hi, lo = items[0], items[-1]
    return {"title": True,
            "elements": [{"type": "balance", "region": "full",
                          "data": {"value_from": "item:0",
                                   "vs_from": f"item:{len(items) - 1}"},
                          "anim": "grow"}]}


def icon_subject(insight) -> str:
    """The noun this story is COUNTING, chosen so the icon library answers.

    Tries the topic, then the headline claim, then the item labels — the first
    that maps to a real icon wins, because an isotype of the wrong object is
    worse than a chart. Falls back to a plain marker, which `draw_unit_figures`
    renders as dots: still a count, still readable, just less charming.
    """
    from . import icons
    for cand in (getattr(insight, "topic", ""),
                 getattr(insight, "main_insight", ""),
                 *[getattr(p, "label", "") for p in (insight.items or [])[:3]]):
        text = str(cand or "").strip()
        if text and icons.icon_png(text, 64):
            return text
    return "marker"


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


_RESIZE_CACHE: dict = {}


def _fit(img, w: int, h: int):
    """Resize memoised on (image identity, w, h). Every frame re-resized the
    same cut-out from source before this — with hundreds of frames per beat
    that dominated the render."""
    w, h = max(1, int(w)), max(1, int(h))
    key = (id(img), w, h)
    hit = _RESIZE_CACHE.get(key)
    if hit is None:
        if len(_RESIZE_CACHE) > 512:
            _RESIZE_CACHE.clear()
        hit = img.resize((w, h))
        _RESIZE_CACHE[key] = hit
    return hit


def _push(canvas, r: float):
    """A slow camera push-in over the build (1.00 -> 1.04), cropped back to
    frame. Cheap, subtle, and it means a fully-revealed scene still moves."""
    z = 1.0 + 0.04 * max(0.0, min(1.0, r))
    if z <= 1.0005:
        return canvas
    w, h = canvas.size
    zw, zh = int(w * z), int(h * z)
    big = canvas.resize((zw, zh))
    x, y = (zw - w) // 2, (zh - h) // 2
    return big.crop((x, y, x + w, y + h))


def _load_cutout(subject, slug, tag):
    """A transparent graphic for `subject`: the AI cutout when it answers, else
    a deterministic Twemoji icon.

    The fallback is the point. Pollinations returns 500/429 often enough that
    whole scenes were losing their subjects and degrading to bare chart cards —
    which the review gate blocks, correctly, as data that is stated rather than
    demonstrated. An icon is a weaker picture than a bespoke illustration and a
    far better video than an empty frame.
    """
    from . import icons, scene_media
    from PIL import Image
    # ICON FIRST. The generative provider is not just flaky (500/429) — when it
    # does answer it returns off-topic slop: a malaria scene came back as two
    # human faces on a white background, which is exactly the "composition is
    # wrecked / mostly empty frame" the review gate blocks. A correct, clean,
    # transparent mosquito beats a plausible-looking stranger every time, so the
    # deterministic icon wins whenever the subject maps to one.
    cp = icons.icon_png(subject, 512)
    if cp:
        print(f"[scene] icon subject {subject!r}", flush=True)
    else:
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
    spec = prune(getattr(insight, "scene", None), insight)
    if spec is None:
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
            lab = (lv[0] if lv else "").strip()
            authored = str(el.get("subject", "")).strip()
            # On a TIME SERIES the row label is a year — "2005" is not a thing
            # you can photograph, and asking for a picture of it is how a
            # malaria scene came back as two human faces. Fall back to the
            # authored subject whenever the label is just a number/date.
            subj = authored if (not lab or _JUST_NUMERIC.fullmatch(lab)) else lab
            import hashlib
            sh = hashlib.sha1(subj.lower().encode()).hexdigest()[:6]  # subject-keyed cache
            # Deterministic icon first (inside _load_cutout), real photo only
            # when the subject maps to no icon.
            cuts[i] = _load_cutout(subj, slug, f"s{i}-{sh}")
            if cuts[i] is None:
                photos[i] = _load_photo(subj, slug, f"p{i}-{sh}")
        elif t == "fill_object":
            subj = str(el.get("subject", ""))
            cuts[i] = _load_cutout(subj, slug, f"s{i}")     # silhouette mask
            photos[i] = _load_photo(subj, slug, f"pf{i}")   # real fill content
        elif t in _ICON_TYPES:
            # OFFLINE ONLY. An isotype needs dozens of copies of ONE glyph; a
            # generated cut-out would be a 54-89s round trip (with 500s) for a
            # picture that gets drawn at 90px. The deterministic icon is both
            # the right look and the reason this element can be used freely.
            from . import icons as _ic
            from PIL import Image as _Im
            cp = _ic.icon_png(str(el.get("subject", "")), 256)
            if cp:
                try:
                    cuts[i] = _Im.open(cp).convert("RGBA")
                except Exception:  # noqa: BLE001 — a drawn dot still counts
                    cuts[i] = None
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
        # LINEAR reveal (was ease-out, and _draw_climb eased AGAIN) — the double
        # ease front-loaded the build so the last ~40% barely moved, which read
        # as a ~4s dead hold. Steady growth keeps visible motion the whole beat.
        r = 1.0 if f == frames else f / frames
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
            if t in ("staircase", "elevator", "burden", "gauge"):
                _fn = {"staircase": draw_staircase, "elevator": draw_elevator,
                       "burden": draw_burden, "gauge": draw_gauge}[t]
                an = _fn(d, canvas, box, insight,
                         _color_for(insight.items[0].label, insight)
                         if insight.items else HIGHLIGHT, lr, insight.unit)
                if f == frames and an:
                    anchors.append(an)
            elif t == "race_track":
                an = draw_race(d, canvas, box, insight,
                               _color_for(insight.items[0].label, insight)
                               if insight.items else HIGHLIGHT, lr, insight.unit)
                if f == frames and an:
                    anchors.append(an)
            elif t == "orbit_group":
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
            elif t == "dot_field":
                lv = _resolve((el.get("data") or {}).get("value_from"), insight)
                if not lv:
                    continue
                an = draw_dot_field(d, canvas, box, cuts.get(i), lv[1], lv[0],
                                    _color_for(lv[0], insight), lr, insight.unit)
                if f == frames and an:
                    anchors.append(an)
            elif t == "balance":
                lv = _resolve((el.get("data") or {}).get("value_from"), insight)
                rv = _resolve((el.get("data") or {}).get("vs_from"), insight)
                if not (lv and rv):
                    continue
                an = draw_balance(d, canvas, box, lv[1], rv[1], lv[0], rv[0],
                                  _color_for(lv[0], insight), lr, insight.unit)
                if f == frames and an:
                    anchors.append(an)
            elif t == "unit_figures":
                lv = _resolve((el.get("data") or {}).get("value_from"), insight)
                if not lv:
                    continue
                per = charts._num_or_none((el.get("data") or {}).get("per_value"))
                an = draw_unit_figures(d, canvas, box, cuts.get(i), lv[1], per,
                                       lv[0], _color_for(lv[0], insight), lr,
                                       insight.unit)
                if f == frames and an:
                    anchors.append(an)
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
                                     phase=r,
                                     photo=photos.get(i))
                if f == frames and an:
                    anchors.append(an)
        # CAMERA PUSH. Element reveals finish partway through a beat and every
        # frame after that was identical — per-element "breathing" only covered
        # ranking rows, so a scene built from fill_object/stack/timeline still
        # froze (segment_0 measured 0.5 fps while the other two hit 24.0). A
        # slow 4% push across the build is what a real edit does anyway, and it
        # guarantees no two frames of the beat are the same whatever the scene
        # is made of.
        canvas = _push(canvas, r)
        # compress_level=1: these are intermediate build frames that ffmpeg
        # reads once and throws away, so the default level-6 deflate is pure
        # cost. This is most of what made a full-length scene beat
        # unaffordable — and an unaffordable beat is why scene segments came
        # out at ~1 effective fps against an 11.0 floor.
        canvas.save(out_dir / f"{slug}_build{f:02d}.png", compress_level=1)
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
        # CAMERA PUSH. Element reveals finish partway through a beat and every
        # frame after that was identical — per-element "breathing" only covered
        # ranking rows, so a scene built from fill_object/stack/timeline still
        # froze (segment_0 measured 0.5 fps while the other two hit 24.0). A
        # slow 4% push across the build is what a real edit does anyway, and it
        # guarantees no two frames of the beat are the same whatever the scene
        # is made of.
        canvas = _push(canvas, r)
        # compress_level=1: these are intermediate build frames that ffmpeg
        # reads once and throws away, so the default level-6 deflate is pure
        # cost. This is most of what made a full-length scene beat
        # unaffordable — and an unaffordable beat is why scene segments came
        # out at ~1 effective fps against an 11.0 floor.
        canvas.save(out_dir / f"{slug}_build{f:02d}.png", compress_level=1)
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
