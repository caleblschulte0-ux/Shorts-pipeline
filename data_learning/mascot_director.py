"""Mascot action director — the system that puts Data INTO every scene.

Rule (from the brand owner): the host never floats in the void. Every time
he is on screen he is living inside the scene — sitting on the soup cans,
shoving the overflowing cart, staggering under the rent, riding the chart
between data points. This module is the generator: given any scene's
subject / label / number it decides, on its own, WHAT he is doing and WHICH
prop he is interacting with, then composes him + the prop into one image.

Two layers:
  * a PROP library (draw_* functions, rig coordinate space) — extensible.
  * an ACTION library (hold / carry / push / sit_on / ride / stagger_under /
    lean_on / juggle / point_at) that poses the rig around a prop so they
    actually interact.
  * :func:`choose` — the autonomous chooser: keyword + intent -> (prop,
    action, expression). It NEVER returns a floating pose; the fallback is
    "ride the chart" for pure-data beats and "hold a price tag with the
    number" for everything else.

The renderer calls :func:`compose_svg` (or :func:`render_png`) per scene.
A scene may also carry a brain-authored spec (segment.mascot) which, when
present, overrides the heuristic — the brain can invent richer actions, but
the heuristic guarantees the never-float rule even before the brain is tuned.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from scripts import build_mascot_svg as R   # noqa: E402

OUT = R.OUTLINE
INK = "#17272E"

# ---------------------------------------------------------------- expressions
def _expr(name: str, look=(0, 0)):
    dx, dy = look
    if name == "shock":
        return (R.eye_open(R.LEX, 0, 0, 25) + R.eye_open(R.REX, 0, 0, 25),
                R.mouth_o())
    if name == "laugh":
        return (R.eye_closed(R.LEX) + R.eye_closed(R.REX), R.mouth_grin())
    if name == "think":
        return (R.eye_open(R.LEX, dx, dy) + R.eye_open(R.REX, dx, dy),
                R.mouth_pursed())
    if name == "strain":
        return (R.eye_closed(R.LEX) + R.eye_closed(R.REX), R.mouth_line())
    if name == "happy":
        return (R.eye_open(R.LEX, dx, dy) + R.eye_open(R.REX, dx, dy),
                R.mouth_open_smile())
    return (R.eye_open(R.LEX, dx, dy) + R.eye_open(R.REX, dx, dy),
            R.mouth_smile())      # neutral

# ------------------------------------------------------------------- props
# All in rig coords (mascot occupies ~x 78..262, y 24..372).
def egg(cx, cy, s=1.0, rot=0):
    rx, ry = 26 * s, 34 * s
    return (f'<g transform="rotate({rot} {cx} {cy})">'
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#FDF6E9" '
            f'stroke="{OUT}" stroke-width="6"/>'
            f'<ellipse cx="{cx-rx*0.3}" cy="{cy-ry*0.3}" rx="{rx*0.28}" '
            f'ry="{ry*0.3}" fill="#FFFFFF" opacity="0.7"/></g>')


def soup_can(cx, cy, s=1.0):
    w, h = 74 * s, 96 * s
    x, y = cx - w / 2, cy - h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
            f'fill="#D7DDE3" stroke="{OUT}" stroke-width="6"/>'
            f'<rect x="{x}" y="{y+h*0.30}" width="{w}" height="{h*0.42}" '
            f'fill="#E23B33" stroke="{OUT}" stroke-width="5"/>'
            f'<ellipse cx="{cx}" cy="{y}" rx="{w/2}" ry="{6*s}" fill="#EDF1F4" '
            f'stroke="{OUT}" stroke-width="5"/>')


def soup_cans(cx, cy, s=1.0):
    """A little stack/cluster of cans to sit on."""
    return (soup_can(cx - 42 * s, cy, s) + soup_can(cx + 42 * s, cy, s) +
            soup_can(cx, cy - 70 * s, s))


def cart(cx, cy, s=1.0):
    def P(x, y): return f"{cx+x*s},{cy+y*s}"
    return (
        f'<circle cx="{cx-38*s}" cy="{cy-84*s}" r="{24*s}" fill="#EF5C46" stroke="{OUT}" stroke-width="6"/>'
        f'<circle cx="{cx+6*s}" cy="{cy-96*s}" r="{28*s}" fill="#F2A23C" stroke="{OUT}" stroke-width="6"/>'
        f'<circle cx="{cx+50*s}" cy="{cy-80*s}" r="{22*s}" fill="#8CC152" stroke="{OUT}" stroke-width="6"/>'
        f'<path d="M{P(-88,-64)} L{P(88,-64)} L{P(64,28)} L{P(-64,28)} Z" '
        f'fill="#7FD9CD" stroke="{OUT}" stroke-width="8" stroke-linejoin="round"/>'
        f'<path d="M{P(-88,-64)} L{P(-114,-64)} L{P(-126,-98)}" fill="none" '
        f'stroke="{OUT}" stroke-width="8" stroke-linecap="round"/>'
        f'<circle cx="{cx-46*s}" cy="{cy+62*s}" r="{16*s}" fill="#2B3A42" stroke="{OUT}" stroke-width="5"/>'
        f'<circle cx="{cx+46*s}" cy="{cy+62*s}" r="{16*s}" fill="#2B3A42" stroke="{OUT}" stroke-width="5"/>')


def dollar(cx, cy, s=1.0):
    w, h = 130 * s, 64 * s
    x, y = cx - w / 2, cy - h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" '
            f'fill="#5BB98B" stroke="{OUT}" stroke-width="6"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{19*s}" fill="none" stroke="#0F3D2A" stroke-width="3"/>'
            f'<text x="{cx}" y="{cy+11*s}" font-family="Georgia,serif" '
            f'font-size="{30*s}" font-weight="700" fill="#0F3D2A" text-anchor="middle">$</text>')


def coins(cx, cy, s=1.0):
    out = ""
    for i, w in enumerate((0, -1, 1, 0)):
        yy = cy - i * 15 * s
        out += (f'<ellipse cx="{cx+w*4*s}" cy="{yy}" rx="{34*s}" ry="{12*s}" '
                f'fill="#F2C14E" stroke="{OUT}" stroke-width="5"/>')
    return out


def house(cx, cy, s=1.0):
    def P(x, y): return f"{cx+x*s},{cy+y*s}"
    return (f'<rect x="{cx-44*s}" y="{cy-30*s}" width="{88*s}" height="{74*s}" '
            f'fill="#EED7C4" stroke="{OUT}" stroke-width="7"/>'
            f'<path d="M{P(-56,-30)} L{P(0,-72)} L{P(56,-30)} Z" fill="#C0553F" '
            f'stroke="{OUT}" stroke-width="7" stroke-linejoin="round"/>'
            f'<rect x="{cx-14*s}" y="{cy+4*s}" width="{28*s}" height="{40*s}" '
            f'fill="#7C5B3A" stroke="{OUT}" stroke-width="5"/>')


def gas_pump(cx, cy, s=1.0):
    return (f'<rect x="{cx-30*s}" y="{cy-84*s}" width="{60*s}" height="{128*s}" '
            f'rx="10" fill="#D24B4B" stroke="{OUT}" stroke-width="7"/>'
            f'<rect x="{cx-18*s}" y="{cy-70*s}" width="{36*s}" height="{30*s}" '
            f'rx="4" fill="#0E1219" stroke="{OUT}" stroke-width="4"/>'
            f'<text x="{cx}" y="{cy-47*s}" font-family="Arial,sans-serif" '
            f'font-size="{18*s}" fill="#F2C14E" text-anchor="middle">$$$</text>')


def pill_bottle(cx, cy, s=1.0):
    return (f'<rect x="{cx-32*s}" y="{cy-58*s}" width="{64*s}" height="{104*s}" '
            f'rx="9" fill="#F6A23C" stroke="{OUT}" stroke-width="7"/>'
            f'<rect x="{cx-36*s}" y="{cy-72*s}" width="{72*s}" height="{22*s}" '
            f'rx="5" fill="#D5872B" stroke="{OUT}" stroke-width="6"/>'
            f'<rect x="{cx-24*s}" y="{cy-30*s}" width="{48*s}" height="{58*s}" '
            f'fill="#FBE9CE"/>' )


def price_tag(cx, cy, s=1.0, text=""):
    w, h = 118 * s, 66 * s
    return (f'<path d="M{cx-w/2},{cy-h/2} L{cx+w/2-16*s},{cy-h/2} '
            f'L{cx+w/2},{cy} L{cx+w/2-16*s},{cy+h/2} L{cx-w/2},{cy+h/2} Z" '
            f'fill="#F2C14E" stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
            f'<circle cx="{cx-w/2+14*s}" cy="{cy}" r="{6*s}" fill="{OUT}"/>'
            f'<text x="{cx+4*s}" y="{cy+9*s}" font-family="Arial Black,sans-serif" '
            f'font-size="{26*s}" font-weight="900" fill="{INK}" '
            f'text-anchor="middle">{text}</text>')


def chart_bird(cx, cy, s=1.0):
    """A little bird Data rides across a chart."""
    def P(x, y): return f"{cx+x*s},{cy+y*s}"
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{60*s}" ry="{34*s}" '
            f'fill="#5AA9F0" stroke="{OUT}" stroke-width="7"/>'
            f'<path d="M{P(-58,-6)} q-40,-4 -64,18 q34,6 64,2 Z" fill="#4A96DB" '
            f'stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
            f'<circle cx="{cx+44*s}" cy="{cy-16*s}" r="{18*s}" fill="#5AA9F0" '
            f'stroke="{OUT}" stroke-width="7"/>'
            f'<circle cx="{cx+48*s}" cy="{cy-18*s}" r="{4*s}" fill="{OUT}"/>'
            f'<path d="M{P(60,-14)} l22,6 l-22,8 Z" fill="#F2A23C" '
            f'stroke="{OUT}" stroke-width="4" stroke-linejoin="round"/>')


def clipboard(cx, cy, s=1.0):
    """A host clipboard — so 'no-prop' host moments still read as ON SET."""
    w, h = 66 * s, 90 * s
    x, y = cx - w / 2, cy - h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="#C98A3C" stroke="{OUT}" stroke-width="6"/>'
            f'<rect x="{x+7*s}" y="{y+9*s}" width="{w-14*s}" height="{h-16*s}" '
            f'rx="3" fill="#FBF6EC" stroke="{OUT}" stroke-width="3"/>'
            f'<rect x="{cx-13*s}" y="{y-7*s}" width="{26*s}" height="{14*s}" '
            f'rx="4" fill="#9AA6AD" stroke="{OUT}" stroke-width="5"/>'
            + "".join(f'<path d="M{x+13*s},{y+22*s+i*15*s} L{x+w-13*s},'
                      f'{y+22*s+i*15*s}" stroke="#9FB0AD" stroke-width="3"/>'
                      for i in range(4)))


PROPS = {
    "eggs": egg, "soup_cans": soup_cans, "soup_can": soup_can, "cart": cart,
    "dollar": dollar, "coins": coins, "house": house, "gas_pump": gas_pump,
    "pill_bottle": pill_bottle, "price_tag": price_tag, "chart_bird": chart_bird,
    "clipboard": clipboard,
}

# ------------------------------------------------------------------ actions
# Each returns (arms, lower, extra_back, extra_front). Prop is a zero-arg
# callable that draws the prop where the action expects it.
def _carry(prop):
    arms = R.arm(*R.SHL, 150, 252, -8) + R.arm(*R.SHR, 190, 252, 8)
    return arms, R.lower_stand(), "", prop(170, 250)


def _hold_up(prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, 250, 150, 10)
    return arms, R.lower_stand(), "", prop(258, 150)


def _push(prop):
    arms = R.arm(*R.SHL, 250, 250, -6) + R.arm(*R.SHR, 258, 288, 6)
    return arms, R.lower_stand(), prop(330, 250), ""


def _sit_on(prop):
    arms = R.arm(*R.SHL, 150, 252, -8) + R.arm(*R.SHR, 214, 176, 20)
    return arms, R.lower_seated(), prop(170, 372), ""


def _ride(prop):
    arms = R.arm(*R.SHL, 150, 244, -18) + R.arm(*R.SHR, 190, 244, 18)
    return arms, R.lower_ride(), prop(170, 384), ""


def _stagger(prop):
    arms = R.arm(*R.SHL, 120, 70, -14) + R.arm(*R.SHR, 220, 70, 14)
    return arms, R.lower_seated(), "", prop(170, 40)


def _lean_on(prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, 286, 200, 12)
    return arms, R.lower_stand(), prop(320, 250), ""


def _juggle(prop):
    arms = R.arm(*R.SHL, 120, 66, -18) + R.arm(*R.SHR, 220, 66, 18)
    air = prop(120, 30) + prop(220, 30) + prop(170, -12)
    return arms, R.lower_stand(), "", air


def _point_at(prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, 300, 150, 10)
    return arms, R.lower_stand(), prop(330, 150), ""


def _present(prop):
    """Host beat: holds a clipboard and gestures — reads as on-set, not void."""
    arms = R.arm(*R.SHL, 150, 250, -8) + R.arm(*R.SHR, 300, 210, 12)
    return arms, R.lower_stand(), "", prop(150, 250)


def _cheer(_prop):
    arms = R.arm(*R.SHL, 116, 82, -12) + R.arm(*R.SHR, 224, 82, 12)
    return arms, R.lower_stand(), "", ""


ACTIONS = {
    "carry": _carry, "hold_up": _hold_up, "push": _push, "sit_on": _sit_on,
    "ride": _ride, "stagger_under": _stagger, "lean_on": _lean_on,
    "juggle": _juggle, "point_at": _point_at, "present": _present,
    "cheer": _cheer,
}


def default_host() -> dict:
    """The never-float default for hook / gaps / host moments."""
    return {"prop": "clipboard", "action": "present", "expr": "happy"}


def celebrate() -> dict:
    return {"prop": "clipboard", "action": "cheer", "expr": "laugh"}

# --------------------------------------------------------------- the chooser
# keyword -> (prop, action, expression). First match wins; order matters.
_RULES = [
    (r"egg", ("eggs", "juggle", "shock")),
    (r"soup|can\b|canned|grocery aisle|shelf", ("soup_cans", "sit_on", "happy")),
    (r"cart|grocery|groceries|supermarket|checkout|receipt",
        ("cart", "push", "strain")),
    (r"rent|housing|mortgage|home price|house|apartment",
        ("house", "stagger_under", "strain")),
    (r"gas|fuel|gallon|pump|oil price", ("gas_pump", "lean_on", "neutral")),
    (r"wage|salary|pay\b|paycheck|income|earn", ("coins", "carry", "neutral")),
    (r"debt|loan|credit|owe|student", ("coins", "stagger_under", "strain")),
    (r"drug|pill|prescription|health|medical|insurance",
        ("pill_bottle", "hold_up", "shock")),
    (r"dollar|inflation|buying power|purchasing|worth|value of",
        ("dollar", "hold_up", "think")),
    (r"tax|price|cost|expensive|\$", ("price_tag", "carry", "shock")),
]


def choose(subject: str = "", label: str = "", value: str = "",
           kind: str = "") -> dict:
    """Autonomously pick what Data is DOING for this scene. Never floats:
    pure-data beats ride the chart; anything else at least carries a tagged
    prop. Returns a spec dict the renderer/compositor consumes."""
    hay = " ".join((subject, label, kind)).lower()
    for pat, (prop, action, expr) in _RULES:
        if re.search(pat, hay):
            spec = {"prop": prop, "action": action, "expr": expr}
            if prop == "price_tag":
                spec["text"] = value or "$$$"
            return spec
    # never-float fallback: on a data/chart/number beat, ride the chart bird;
    # otherwise present the number on a price tag.
    if re.search(r"chart|data|percent|%|trend|rate|number|graph", hay) or value:
        return {"prop": "chart_bird", "action": "ride", "expr": "happy"}
    return {"prop": "price_tag", "action": "carry", "expr": "shock",
            "text": value or "?"}

# -------------------------------------------------------------- composition
def compose_svg(spec: dict) -> str:
    """Build the full scene-mascot SVG (Data + prop, posed to interact)."""
    prop_name = spec.get("prop", "price_tag")
    action = spec.get("action", "carry")
    expr = spec.get("expr", "neutral")
    text = spec.get("text", "")
    draw = PROPS.get(prop_name, price_tag)
    if prop_name == "price_tag":
        def prop(cx, cy, s=1.0): return draw(cx, cy, s, text=text)
    else:
        prop = draw
    arms, lower, back, front = ACTIONS.get(action, _carry)(prop)
    eyes, mouth = _expr(expr, look=(0, 3) if action in ("sit_on", "ride") else (0, 0))
    inner = R.assemble(arms, eyes, mouth, lower=lower,
                       extra_back=back, extra_front=front)
    return R.wrap(inner, view="-70 -50 480 490",
                  label=f"Data {action} {prop_name}")


def render_png(spec: dict, size: int, out_path: Path) -> Path:
    """Rasterise the composed scene-mascot to a transparent square PNG.
    cairosvg in CI; playwright locally; never raises (falls back to the
    idle host PNG) so a render can't die over a prop."""
    svg = compose_svg(spec)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        png = _rasterise(svg, size)
        out_path.write_bytes(png)
    except Exception as e:  # noqa: BLE001
        print(f"[director] compose failed ({e}); using idle host", flush=True)
        from data_learning import mascot
        mascot.save_static(out_path, size=size, pose="idle")
    return out_path


def _rasterise(svg: str, size: int) -> bytes:
    """SVG -> square transparent PNG bytes. viewBox is square (480x490 ~ 1:1)."""
    from PIL import Image
    import io
    try:
        import cairosvg
        raw = cairosvg.svg2png(bytestring=svg.encode(), output_width=size,
                               output_height=size)
    except Exception:
        from playwright.sync_api import sync_playwright
        import os
        html = ("<!doctype html><body style='margin:0'>"
                f"<div style='width:{size}px'>{svg}</div></body>")
        exe = "/opt/pw-browsers/chromium"
        with sync_playwright() as pw:
            b = (pw.chromium.launch(executable_path=exe)
                 if os.path.exists(exe) else pw.chromium.launch())
            pg = b.new_page(viewport={"width": size, "height": size},
                            device_scale_factor=2)
            pg.set_content(html); pg.wait_for_timeout(150)
            raw = pg.screenshot(omit_background=True,
                                clip={"x": 0, "y": 0, "width": size, "height": size})
            b.close()
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    side = max(img.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    if sq.size != (size, size):
        sq = sq.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO(); sq.save(buf, "PNG")
    return buf.getvalue()
