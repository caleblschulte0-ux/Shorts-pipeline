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
        if t not in _TYPES:
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


def draw_object(d, canvas, box, cutout, value, label, color, reveal, vmax):
    """A subject cut-out sized ∝ value, bottom-anchored in the box, number above
    + label below. Placeholder silhouette if the cut-out is missing."""
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    frac = 0.55 + 0.45 * (value / vmax if vmax else 1.0)
    avail_h = bh - 150                                 # room for number + label
    if cutout is not None:
        asp = cutout.width / cutout.height
        oh = int(avail_h * frac)
        ow = int(oh * asp)
        if ow > bw:
            ow, oh = bw, int(bw / asp)
    else:
        oh = int(avail_h * frac)
        ow = int(oh * 0.9)
    cx = _cx(box)
    ground = by1 - 60
    top = ground - oh + int((1.0 - reveal) * 60)
    a = int(255 * reveal)
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


def draw_fill_object(d, canvas, box, cutout, value, label, color, reveal, unit=""):
    """Fill a SUBJECT silhouette bottom-up to a % while the number counts up —
    the 'filled globe' for shares. The cut-out's alpha is the fill mask. If the
    cut-out is missing, degrade to a filled rounded vessel (still depicts %)."""
    from PIL import Image, ImageChops
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
            layer = Image.new("RGBA", (ow, oh), _rgba(color, 235))
            layer.putalpha(clip)
            canvas.alpha_composite(layer, (ox, oy))
        num_cy = oy + oh // 2
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


def draw_timeline(d, box, insight, reveal):
    """A marker travels a time/number axis to its point (the loved timeline)."""
    items = _ordered_items(insight)
    vp = getattr(insight, "viz_params", {}) or {}
    star = max(items, key=lambda p: p.value)
    periods = [charts._num_or_none(getattr(p, "period", None)) for p in items]
    have_p = len(periods) >= 2 and all(v is not None for v in periods)
    lo = charts._num_or_none(vp.get("timeline_start"))
    hi = charts._num_or_none(vp.get("timeline_end"))
    if have_p:
        lo = min(periods) if lo is None else lo
        hi = max(periods) if hi is None else hi
        target, suffix = periods[items.index(star)], ""
    else:
        lo = 0.0 if lo is None else lo
        hi = (star.value * 1.12 or 1.0) if hi is None else hi
        target, suffix = star.value, (f" {insight.unit}" if insight.unit else "")
    if hi <= lo:
        hi = lo + 1.0
    frac = max(0.0, min(1.0, (target - lo) / (hi - lo)))
    axis_y = (box[1] + box[3]) // 2
    x0, x1 = box[0] + 70, box[2] - 70
    num_font, tick_font, lab_font = _pil_font(72), _pil_font(30), _pil_font(46)
    d.line([(x0, axis_y), (x1, axis_y)], fill=(120, 140, 170, 255), width=6)
    for k in range(5):
        tx = x0 + (x1 - x0) * k / 4
        d.line([(tx, axis_y - 14), (tx, axis_y + 14)], fill=(120, 140, 170, 255), width=4)
        lbl = _sci(lo + (hi - lo) * k / 4)
        lb = d.textbbox((0, 0), lbl, font=tick_font)
        d.text((tx - (lb[2] - lb[0]) // 2, axis_y + 28), lbl, font=tick_font,
               fill=(165, 180, 199, 255))
    mx = x0 + reveal * frac * (x1 - x0)
    d.line([(x0, axis_y), (mx, axis_y)], fill=_rgba(HIGHLIGHT, 255), width=12)
    for rad, alpha in ((48, 60), (34, 120), (23, 255)):
        d.ellipse([mx - rad, axis_y - rad, mx + rad, axis_y + rad], fill=_rgba(HIGHLIGHT, alpha))
    na = max(0.0, min(1.0, (reveal - 0.35) / 0.65))
    val = _sci(target) + suffix
    vb = d.textbbox((0, 0), val, font=num_font)
    vx = min(max(mx - (vb[2] - vb[0]) / 2, box[0]), box[2] - (vb[2] - vb[0]))
    d.text((vx, axis_y - 170), val, font=num_font, fill=_rgba(HIGHLIGHT, int(255 * na)),
           stroke_width=5, stroke_fill=(5, 8, 15, int(255 * na)))
    sb = d.textbbox((0, 0), star.label, font=lab_font)
    sx = min(max(mx - (sb[2] - sb[0]) / 2, box[0]), box[2] - (sb[2] - sb[0]))
    d.text((sx, axis_y + 78), star.label, font=lab_font,
           fill=(248, 250, 252, int(255 * na)), stroke_width=3,
           stroke_fill=(5, 8, 15, int(255 * na)))


# --------------------------------------------------------------------------- #
# Interpreter
# --------------------------------------------------------------------------- #
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


@_fullframe("scene")
def render_scene(insight, out_dir: Path, slug: str, frames: int = 16):
    from PIL import Image, ImageDraw
    spec = getattr(insight, "scene", None)
    if not validate(spec, insight):
        return None
    els = spec["elements"]
    out_dir.mkdir(parents=True, exist_ok=True)
    boxes = _layout(els)
    show_title = spec.get("title", True) and bool(insight.topic)
    # Pre-load cut-outs once (cached anyway) so we can bail to fallback if the
    # whole scene is image-only and every image failed.
    cuts = {}
    for i, el in enumerate(els):
        if el.get("type") in _IMAGE_TYPES:
            cuts[i] = _load_cutout(str(el.get("subject", "")), slug, f"s{i}")
    # `object`/`stack` are only meaningful WITH a cut-out (their placeholder is a
    # bare rectangle). If every element is one of those and all cut-outs failed,
    # bail to a cleaner FALLBACK depiction. fill_object/bar/bubble/orbit/timeline
    # all self-degrade, so a scene containing any of them still renders.
    hard = {"object", "stack"}
    if els and all(e.get("type") in hard for e in els) \
            and all(cuts.get(i) is None for i in range(len(els))):
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
                draw_timeline(d, box, insight, r)
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
                                          col, lr, insight.unit)
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
                                     col, lr, vmax)
                if f == frames and an:
                    anchors.append(an)
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, anchors
