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

import json
import math
import os
import re
import shutil
import subprocess
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
    # never-float fallback: on ANY data / chart / timeline / number beat, do
    # the EXTRA thing — ride the chart bird (per brand rule, even pure-data
    # beats get motion, not a standing host). Otherwise present the number
    # on a price tag.
    if (value or re.search(r"chart|data|percent|%|trend|rate|number|graph|"
                           r"timeline|year|since|over time|per\b|share|ratio",
                           hay)):
        return {"prop": "chart_bird", "action": "ride", "expr": "happy"}
    return {"prop": "price_tag", "action": "carry", "expr": "shock",
            "text": value or "?"}


# ==========================================================================
# PER-SCENE PERFORMANCE GENERATION — regenerate what Data is DOING per scene,
# on the fly. The rig can render ANY pose (see _a_pose); these produce the pose
# specs. Two sources, in order: (1) the Claude HEADLESS BRAIN authors a bespoke
# pose for the exact beat when MASCOT_BRAIN is on; (2) a deterministic library
# of distinct bespoke acts keyed to the beat. Both guarantee the never-float
# rule and never reuse an identical body across differing beats.
# ==========================================================================

# Rig coordinate cheatsheet (view is roughly x:60..400, y:40..470; shoulders at
# ~(128,206)/(212,206), face/mouth ~ (170,150), lap ~ (170,300)). Hand target =
# [wrist_x, wrist_y, bend]. lower ∈ stand|seated|ride.
POSE_PRESETS: dict[str, dict] = {
    # Sitting on a can, spooning soup to his mouth (one hand up at the face).
    "eat_soup": {"action": "pose", "prop": "soup_can", "pose": {
        "lower": "seated", "back": "soup_can", "back_at": [168, 372],
        "lh": [150, 300, -6], "rh": [214, 176, 22], "expr": "happy",
        "motion": {"limb": "r", "amp": 12}, "bob": 2}},
    # Riding a bird, BOTH hands down gripping it for dear life.
    "ride_bird_grip": {"action": "pose", "prop": "chart_bird", "pose": {
        "lower": "ride", "back": "chart_bird", "back_at": [170, 384],
        "lh": [150, 244, -18], "rh": [190, 244, 18], "expr": "strain",
        "motion": {"limb": "bob", "amp": 4}, "bob": 6}},
    # Straining to LIFT a stack of bills overhead — setup→action→payoff.
    "lift_bills": {"action": "pose", "prop": "dollar", "pose": {
        "lower": "stand", "front": "dollar", "front_at": [170, 96],
        "lh": [120, 150, -12], "rh": [220, 150, 12], "expr": "strain",
        "motion": {"limb": "both", "amp": 7}, "bob": 2}},
    # Getting crushed / buried under a falling receipt (arms up bracing).
    "brace_overhead": {"action": "pose", "prop": "price_tag", "pose": {
        "lower": "stand", "front": "price_tag", "front_at": [170, 70],
        "lh": [128, 120, -8], "rh": [212, 120, 8], "expr": "shock",
        "motion": {"limb": "both", "amp": 5}, "bob": 1}},
    # Shoving an overflowing cart (both hands forward on the handle).
    "shove_cart": {"action": "pose", "prop": "cart", "pose": {
        "lower": "stand", "front": "cart", "front_at": [250, 250],
        "lh": [210, 250, 8], "rh": [230, 250, 10], "expr": "strain",
        "motion": {"limb": "both", "amp": 4}, "bob": 3}},
    # Presenting / gesturing UP at the chart above him (one hand raised).
    "present_up": {"action": "pose", "prop": "clipboard", "pose": {
        "lower": "stand", "front": "clipboard", "front_at": [130, 250],
        "lh": [126, 250, -6], "rh": [236, 150, 14], "expr": "happy",
        "motion": {"limb": "r", "amp": 8}, "bob": 3}},
}

# Keyword -> preset. First match wins; distinct beats get distinct acts.
_PERF_RULES: list[tuple[str, str]] = [
    (r"soup|can|grocer|food|meal|eat|pantry", "eat_soup"),
    (r"bird|fly|soar|rise|rising|climb|takeoff|launch|up\b|surge", "ride_bird_grip"),
    (r"dollar|\$|wage|pay|income|salary|raise|cost|price|bill|expensive", "lift_bills"),
    (r"rent|receipt|debt|crush|burden|weight|heav|tax", "brace_overhead"),
    (r"cart|shop|spend|checkout|store", "shove_cart"),
    (r"chart|data|percent|%|trend|rate|share|ratio|graph|timeline", "present_up"),
]

_VIEW = (60.0, 40.0, 400.0, 470.0)   # x0,y0,x1,y1 sane bounds for hands/props


def validate_pose(spec: dict) -> bool:
    """Structural + bounds check on a 'pose' spec so a bad brain output can't
    throw or fling a limb off-canvas. Clamps hand/prop coords in place."""
    if not isinstance(spec, dict) or spec.get("action") != "pose":
        return False
    p = spec.get("pose")
    if not isinstance(p, dict):
        return False
    x0, y0, x1, y1 = _VIEW
    for key in ("lh", "rh"):
        v = p.get(key)
        if not (isinstance(v, list) and len(v) == 3):
            return False
        v[0] = float(min(max(v[0], x0), x1))
        v[1] = float(min(max(v[1], y0), y1))
        v[2] = float(min(max(v[2], -40), 40))
    for key in ("back_at", "front_at"):
        v = p.get(key)
        if isinstance(v, list) and len(v) == 2:
            v[0] = float(min(max(v[0], x0), x1))
            v[1] = float(min(max(v[1], y0), y1))
    if p.get("lower") not in ("stand", "seated", "ride"):
        p["lower"] = "stand"
    for key in ("back", "front"):
        if p.get(key) and p[key] not in PROPS:
            p[key] = None
    return True


_PERF_GUIDE = (
    "You choreograph a mascot named Data — a teal monster-professor in a lab "
    "coat — INTO one video beat. He must never just stand there; he ACTS on the "
    "beat's subject with a setup->action->payoff. Output ONE JSON pose spec the "
    "rig renders directly. Rig coords: view x 60..400, y 40..470; shoulders "
    "~(128,206)/(212,206); face/mouth ~(170,150); lap ~(170,300); feet ~(170,"
    "430). A hand target is [wrist_x, wrist_y, bend(-40..40)]. Fields: "
    "{\"action\":\"pose\",\"prop\":<name>,\"pose\":{\"lower\":\"stand|seated|"
    "ride\",\"lh\":[x,y,b],\"rh\":[x,y,b],\"back\":<prop|null>,\"back_at\":[x,"
    "y],\"front\":<prop|null>,\"front_at\":[x,y],\"expr\":\"happy|shock|laugh|"
    "think|strain|neutral\",\"motion\":{\"limb\":\"l|r|both|bob\",\"amp\":0-14},"
    "\"bob\":0-8}}. Props available: " + ", ".join(sorted(PROPS)) + ". Make the "
    "pose SPECIFIC to the subject (e.g. spooning soup off a can = seated + a "
    "hand at the face; gripping a bird mid-flight = ride + both hands down). "
    "Return ONLY the JSON."
)


def _brain_author(subject: str, label: str, value: str, kind: str) -> dict | None:
    """Ask the Claude HEADLESS BRAIN (the `claude` CLI, subscription token) to
    author a bespoke pose for THIS beat. Best-effort: returns None if the CLI is
    absent/errors so the caller falls back to the deterministic library."""
    if not shutil.which("claude"):
        return None
    ask = (_PERF_GUIDE + f"\n\nBEAT: subject={subject!r} label={label!r} "
           f"value={value!r} kind={kind!r}. Author Data's performance.")
    model = os.environ.get("MASCOT_BRAIN_MODEL", "sonnet")
    try:
        proc = subprocess.run(
            ["claude", "-p", ask, "--model", model, "--output-format", "text"],
            capture_output=True, text=True,
            timeout=int(os.environ.get("MASCOT_BRAIN_TIMEOUT", "120")))
        if proc.returncode != 0:
            return None
        m = re.search(r"\{.*\}", proc.stdout or "", re.S)
        if not m:
            return None
        spec = json.loads(m.group(0))
        if value and spec.get("prop") == "price_tag":
            spec["text"] = value
        return spec if validate_pose(spec) else None
    except Exception:  # noqa: BLE001
        return None


# A diverse rotation so consecutive beats never reuse the same act, even when
# their keywords overlap (three grocery beats must still differ).
_DIVERSE = ["ride_bird_grip", "lift_bills", "present_up", "shove_cart",
            "brace_overhead", "eat_soup"]


def author_performance(subject: str = "", label: str = "", value: str = "",
                       kind: str = "", *, index: int = 0,
                       use_brain: bool | None = None) -> dict:
    """The per-scene performance generator. Order: (1) headless-brain bespoke
    pose when MASCOT_BRAIN is on; (2) a distinct preset act, rotated by scene
    ``index`` so beats never repeat, biased toward a keyword match; (3) the
    classic :func:`choose` heuristic. Always returns a renderable, never-float
    spec."""
    if use_brain is None:
        use_brain = os.environ.get("MASCOT_BRAIN", "0").lower() in (
            "1", "true", "on", "yes")
    if use_brain:
        spec = _brain_author(subject, label, value, kind)
        if spec:
            return spec
    hay = " ".join((subject, label, kind)).lower()
    # DATA-CHART kinds read best with Data PRESENTING the chart (arms up at the
    # data he's narrating) — on-topic for ANY subject. The whimsical prop presets
    # (soup can, bird, money, cart) were authored for grocery's tone; handing one
    # to a CO2 / population / electricity story is exactly the off-topic
    # 'decorative mascot' the gate blocks. So when the brain is off, these kinds
    # fall back to the NEUTRAL presenting pose, not a themed prop. Genuine
    # per-scene variety + relevance comes from MASCOT_BRAIN, not the preset shelf.
    _KIND_POSE = {k: "present_up" for k in (
        "waffle_grid", "share", "pictorial_race", "bubbles", "geo_world",
        "geo_city", "trend", "rank", "comparison", "bars", "versus")}
    if kind in _KIND_POSE:
        preset = _KIND_POSE[kind]
    else:
        # Bias the rotation so a strong keyword match LEADS for this beat, then
        # pick by index so each beat lands on a different act.
        order = list(_DIVERSE)
        for pat, p in _PERF_RULES:
            if re.search(pat, hay) and p in order:
                order.remove(p)
                order.insert(0, p)
                break
        preset = order[index % len(order)]
    spec = json.loads(json.dumps(POSE_PRESETS[preset]))       # deep copy
    if value and spec.get("prop") == "price_tag":
        spec["text"] = value
    validate_pose(spec)
    return spec

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


# =====================================================================
# ANIMATION + ENVIRONMENT ENGINE
# Data must MOVE (keyframed rig, not a bobbing still) and live IN a place
# (a floor/shadow + a light setting behind him). These render a seamless
# per-action loop; the studio overlay composites it over the scene, so the
# environment is drawn on transparency (no bg fill) — just grounding + a
# little set that travels with him.
# =====================================================================
ANIM_VIEW = "-90 -60 520 520"       # square; stable scale across every beat


def _s(t, ph=0.0):
    return math.sin(2 * math.pi * (t + ph))


def _shadow():
    return ('<ellipse cx="170" cy="366" rx="116" ry="18" fill="#000000" '
            'opacity="0.26"/>')


# ---- environments (transparent; drawn behind Data) ----
def _env_kitchen():
    return (_shadow() +
            f'<rect x="-84" y="300" width="150" height="60" rx="6" '
            f'fill="#243642" stroke="{OUT}" stroke-width="5"/>'
            f'<rect x="-64" y="286" width="66" height="18" rx="4" fill="#C98A3C" '
            f'stroke="{OUT}" stroke-width="4"/>')


def _env_store():
    s = _shadow()
    for row in (150, 214, 278):
        s += f'<rect x="250" y="{row}" width="170" height="9" fill="#31485a"/>'
        for i, cx in enumerate((262, 300, 338, 376)):
            col = ("#E2433A", "#D8862F", "#8CC152", "#5AA9F0")[i]
            s += (f'<rect x="{cx}" y="{row-30}" width="22" height="30" rx="3" '
                  f'fill="{col}" stroke="{OUT}" stroke-width="3"/>')
    return s


def _env_chart():
    pts = [(-46, 330), (40, 302), (120, 250), (204, 214), (286, 150), (372, 92)]
    line = "M" + " L".join(f"{x},{y}" for x, y in pts)
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="#4FD1C5" '
                   f'stroke="{OUT}" stroke-width="3"/>' for x, y in pts)
    return (_shadow() + f'<path d="{line}" fill="none" stroke="#4FD1C5" '
            f'stroke-width="7" stroke-linecap="round" opacity="0.85"/>' + dots)


def _env_curb():
    return (_shadow() + f'<rect x="-90" y="360" width="520" height="10" '
            f'fill="#2b3a42" opacity="0.7"/>')


# Environments are just a grounding contact shadow for now: Data TRAVELS
# around the frame, so a full attached set (shelves, counter) would slide with
# him and read wrong. "He's in a place" returns later as a proper scene-wide
# background layer behind everything, not a sprite that moves with him.
ENVS: dict = {}


def _egg_a(cx, cy, rot=0):
    return (f'<g transform="rotate({rot:.0f} {cx:.0f} {cy:.0f})">'
            f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="20" ry="26" '
            f'fill="#FDF6E9" stroke="{OUT}" stroke-width="5"/></g>')


def _wheel(cx, cy, rot):
    return (f'<circle cx="{cx}" cy="{cy}" r="16" fill="#2B3A42" stroke="{OUT}" '
            f'stroke-width="5"/><g transform="rotate({rot:.0f} {cx} {cy})" '
            f'stroke="#8FA6AD" stroke-width="3"><line x1="{cx-12}" y1="{cy}" '
            f'x2="{cx+12}" y2="{cy}"/><line x1="{cx}" y1="{cy-12}" x2="{cx}" '
            f'y2="{cy+12}"/></g>')


def _talk_mouth(t):
    return R.mouth_open_smile() if int(t * 4) % 2 else R.mouth_smile()


# ---- animators: t in [0,1) -> (arms, lower, back, front, eyes, mouth, bob)
def _a_juggle(t, prop):
    lh = (120, 150 + _s(t) * 16)
    rh = (220, 150 + _s(t, 0.5) * 16)
    arms = R.arm(*R.SHL, lh[0], int(lh[1]), -10) + R.arm(*R.SHR, rh[0], int(rh[1]), 10)
    eggs = ""
    for k in range(3):
        a = 2 * math.pi * (t + k / 3.0)
        eggs += _egg_a(170 + 52 * math.sin(a), 96 - 34 * math.cos(a), math.degrees(a))
    return (arms, None, "", eggs, R.eye_open(R.LEX, 0, -6) + R.eye_open(R.REX, 0, -6),
            R.mouth_o(), _s(t) * 3)


def _a_push(t, prop):
    sw = _s(t) * 16
    lower = (R.limb(152, 300, int(138 + sw), 352, 0, 36, 27, 0) +
             R.limb(188, 300, int(202 - sw), 352, 0, 36, 27, 0) +
             f'<ellipse cx="{136+sw:.0f}" cy="356" rx="26" ry="13" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>'
             f'<ellipse cx="{204-sw:.0f}" cy="356" rx="26" ry="13" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>')
    arms = R.arm(*R.SHL, 250, 250, -6) + R.arm(*R.SHR, 258, 288, 6)
    cx, cy, rot = 330, 250, t * 360
    cart = (f'<circle cx="{cx-38}" cy="{cy-84}" r="24" fill="#EF5C46" stroke="{OUT}" stroke-width="6"/>'
            f'<circle cx="{cx+6}" cy="{cy-96}" r="28" fill="#F2A23C" stroke="{OUT}" stroke-width="6"/>'
            f'<path d="M{cx-88},{cy-64} L{cx+88},{cy-64} L{cx+64},{cy+28} L{cx-64},{cy+28} Z" '
            f'fill="#7FD9CD" stroke="{OUT}" stroke-width="8" stroke-linejoin="round"/>'
            + _wheel(cx - 46, cy + 62, rot) + _wheel(cx + 46, cy + 62, rot))
    return (arms, lower, "", cart, R.eye_open(R.LEX, 3, 2) + R.eye_open(R.REX, 3, 2),
            R.mouth_line(), abs(_s(t)) * 4)


def _a_ride(t, prop):
    flap = _s(t) * 14
    cx, cy = 170, 384
    bird = (f'<ellipse cx="{cx}" cy="{cy}" rx="62" ry="32" fill="#5AA9F0" stroke="{OUT}" stroke-width="7"/>'
            f'<path d="M{cx-42},{cy-4} q-36,{-4-flap:.0f} -62,{14-flap:.0f} q32,6 62,0 Z" '
            f'fill="#4A96DB" stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
            f'<circle cx="{cx+44}" cy="{cy-16}" r="16" fill="#5AA9F0" stroke="{OUT}" stroke-width="6"/>'
            f'<circle cx="{cx+48}" cy="{cy-18}" r="4" fill="{OUT}"/>'
            f'<path d="M{cx+60},{cy-14} l20,6 l-20,7 Z" fill="#F2A23C" stroke="{OUT}" stroke-width="4"/>')
    arms = R.arm(*R.SHL, 150, 244, -18) + R.arm(*R.SHR, 190, 244, 18)
    return (arms, R.lower_ride(), bird, "",
            R.eye_open(R.LEX, 0, 2) + R.eye_open(R.REX, 0, 2),
            R.mouth_open_smile(), _s(t) * 5)


def _a_stagger(t, prop):
    wob = _s(t, 0) * 6
    arms = R.arm(*R.SHL, int(120 + wob), 70, -14) + R.arm(*R.SHR, int(220 + wob), 70, 14)
    front = prop(int(170 + wob), 40)
    return (arms, R.lower_seated(), "", front,
            R.eye_closed(R.LEX) + R.eye_closed(R.REX), R.mouth_line(), abs(_s(t)) * 2)


def _a_carry(t, prop):
    sway = _s(t) * 4
    arms = R.arm(*R.SHL, 150, 252, -8) + R.arm(*R.SHR, 190, 252, 8)
    return (arms, None, "", prop(int(170 + sway), int(250 + _s(t, .25) * 4)),
            R.eye_open(R.LEX, 0, 1) + R.eye_open(R.REX, 0, 1), R.mouth_smile(), _s(t) * 3)


def _a_hold_up(t, prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, 250, int(150 + _s(t) * 8), 10)
    return (arms, None, "", prop(258, int(150 + _s(t) * 8)),
            R.eye_open(R.LEX, 2, -4) + R.eye_open(R.REX, 2, -4),
            R.mouth_pursed(), _s(t) * 3)


def _a_sit(t, prop):
    arms = R.arm(*R.SHL, 150, 252, -8) + R.arm(*R.SHR, 214, 176, 20)
    return (arms, R.lower_seated(), prop(170, 372), "",
            R.eye_open(R.LEX, 0, 3) + R.eye_open(R.REX, 0, 3),
            R.mouth_open_smile(), _s(t) * 2)


def _a_lean(t, prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, 286, 200, 12)
    return (arms, None, prop(320, 250), "",
            R.eye_open(R.LEX, 4, 1) + R.eye_open(R.REX, 4, 1),
            R.mouth_smile(), _s(t) * 3)


def _a_present(t, prop):
    ga = int(300 + _s(t) * 20)                    # gesturing arm sweeps
    arms = R.arm(*R.SHL, 150, 250, -8) + R.arm(*R.SHR, ga, int(210 + _s(t) * 12), 12)
    return (arms, None, "", prop(150, 250),
            R.eye_open(R.LEX, 0, 0) + R.eye_open(R.REX, 0, 0), _talk_mouth(t), _s(t) * 3)


def _a_cheer(t, prop):
    up = abs(_s(t)) * 16
    arms = R.arm(*R.SHL, 116, int(82 - up), -12) + R.arm(*R.SHR, 224, int(82 - up), 12)
    return (arms, None, "", "", R.eye_closed(R.LEX) + R.eye_closed(R.REX),
            R.mouth_grin(), -abs(_s(t)) * 10)


def _a_point(t, prop):
    arms = R.arm(*R.SHL, 116, 300, -4) + R.arm(*R.SHR, int(300 + _s(t) * 8), 150, 10)
    return (arms, None, prop(330, 150), "",
            R.eye_open(R.LEX, 5, 0) + R.eye_open(R.REX, 5, 0),
            _talk_mouth(t), _s(t) * 3)


# -------------------------------------------------------------------------
# DATA ACTIONS — prop-less animated performances Data does ON a chart element
# (he's POSITIONED on the bar / line / slice, so 'push' reads as pushing the
# BAR, not a cart). Authored in code: deterministic (no per-render variance),
# free (no brain call), and they genuinely ANIMATE (a named still pose renders
# the identical frame every time — a frozen sticker — these move).
# -------------------------------------------------------------------------
def _a_push_bar(t, _prop):
    """Braced stance, both arms shoving RIGHT into the bar he stands against;
    a big strain sway drives the effort. (This is _a_push with the cart removed.)"""
    sw = _s(t) * 30
    lower = (R.limb(152, 300, int(138 + sw), 352, 0, 36, 27, 0) +
             R.limb(188, 300, int(202 - sw), 352, 0, 36, 27, 0) +
             f'<ellipse cx="{136+sw:.0f}" cy="356" rx="26" ry="13" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>'
             f'<ellipse cx="{204-sw:.0f}" cy="356" rx="26" ry="13" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>')
    px = int(250 + sw)                    # arms swing far as he heaves
    arms = R.arm(*R.SHL, px, 250, -6) + R.arm(*R.SHR, px + 8, 288, 6)
    return (arms, lower, "", "",
            R.eye_open(R.LEX, 3, 2) + R.eye_open(R.REX, 3, 2),
            R.mouth_line(), abs(_s(t)) * 6)


def _a_ride_line(t, _prop):
    """Surfing stance, arms out for balance, leaning into the climb; bobs as he
    rides. (This is _a_ride with the bird removed — he rides the LINE.)"""
    lean = _s(t) * 18
    # arms flung OUT WIDE for balance (surfing the line), pumping with the ride
    arms = (R.arm(*R.SHL, int(64 - lean), int(196 - lean), -26)
            + R.arm(*R.SHR, int(276 + lean), int(196 + lean), 26))
    return (arms, R.lower_ride(), "", "",
            R.eye_open(R.LEX, 0, 2) + R.eye_open(R.REX, 0, 2),
            R.mouth_open_smile(), _s(t) * 12)


def _a_climb(t, _prop):
    """Hand-over-hand climb: arms reach up in alternation, legs cycle — he
    scales the chart element he's on."""
    up = _s(t) * 34
    arms = (R.arm(*R.SHL, 120, int(120 + up), -14)
            + R.arm(*R.SHR, 216, int(120 - up), 14))
    ll, rl = int(150 + up * 0.5), int(202 - up * 0.5)
    lower = (R.limb(152, 300, ll, 352, 0, 36, 27, 0) +
             R.limb(188, 300, rl, 352, 0, 36, 27, 0) +
             f'<ellipse cx="{ll}" cy="356" rx="24" ry="12" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>'
             f'<ellipse cx="{rl}" cy="356" rx="24" ry="12" fill="{R.TEAL}" '
             f'stroke="{OUT}" stroke-width="6"/>')
    return (arms, lower, "", "",
            R.eye_open(R.LEX, 2, -2) + R.eye_open(R.REX, 2, -2),
            R.mouth_line(), 0.0)


def _a_lift(t, _prop):
    """Both arms straining OVERHEAD, hoisting the number/slice; a heave bob."""
    up = abs(_s(t)) * 20
    # both arms straight UP overhead, hoisting — wrists high above the head
    arms = (R.arm(*R.SHL, 110, int(70 - up), -14)
            + R.arm(*R.SHR, 226, int(70 - up), 14))
    return (arms, R.lower_stand(), "", "",
            R.eye_open(R.LEX, 0, -4) + R.eye_open(R.REX, 0, -4),
            R.mouth_o(), -abs(_s(t)) * 6)


# -------------------------------------------------------------------------
# ARC data-actions — a genuine SETUP -> ACTION -> PAYOFF performance across the
# WHOLE beat, driven by beat-progress p (NOT a periodic loop phase). The three
# keyframes are visibly DIFFERENT silhouettes, so the showrunner's start/mid/end
# samples of a beat land on three distinct poses (a real bit), not the identical
# braced pose the gate keeps flagging as 'decorative_mascot / only translating'.
# Each keyframe: ([lh_x,lh_y,bend], [rh_x,rh_y,bend], lower_name, expr_name).
# -------------------------------------------------------------------------
def _lp(a, b, f):
    return a + (b - a) * f


_ARC_REPS = 3          # effort cycles during the action zone (visible reps)

# Phase boundaries come from the ONE scene-timeline owner (scene_timeline.py) so
# the mascot, the chart reveal, and the manifest all agree on when setup ends
# and the payoff starts — no animator guesses its own timing.
try:
    from data_learning.scene_timeline import SETUP_END as _T_SETUP
    from data_learning.scene_timeline import EFFORT_END as _T_EFFORT
except Exception:  # noqa: BLE001 — standalone use keeps the canonical values
    _T_SETUP, _T_EFFORT = 0.18, 0.74
_T_RESIST = 2.0 * _T_SETUP      # coupled bits: end of the winning-for-a-moment zone


def _braced_legs(crouch=0.0, sway=0.0):
    """Braced stance whose knees BEND with ``crouch`` (0=tall .. 1=deep squat) so
    the whole body drives, not just the arms. Feet stay planted (~y356) so he
    doesn't float off the datum. ``sway`` widens/shifts the stance a touch."""
    ky = 300 + 12 + crouch * 26                 # knees drop as he squats
    kx_l, kx_r = 138 - crouch * 8, 202 + crouch * 8
    fl, fr = 138 - sway, 202 + sway
    legs = (R.limb(152, 300, int(kx_l), int(ky), 0, 36, 27, 0) +
            R.limb(int(kx_l), int(ky), int(fl), 352, 0, 36, 27, 0) +
            R.limb(188, 300, int(kx_r), int(ky), 0, 36, 27, 0) +
            R.limb(int(kx_r), int(ky), int(fr), 352, 0, 36, 27, 0))
    feet = (f'<ellipse cx="{fl-2:.0f}" cy="356" rx="27" ry="13" fill="{R.TEAL}" '
            f'stroke="{OUT}" stroke-width="6"/>'
            f'<ellipse cx="{fr+2:.0f}" cy="356" rx="27" ry="13" fill="{R.TEAL}" '
            f'stroke="{OUT}" stroke-width="6"/>')
    return legs + feet


def _arc(kfs, p, wob_amp=7.0):
    """Perform kfs=[SETUP, ACTION, PAYOFF] across beat-progress p in [0,1] with a
    THREE-ZONE structure so even a long (~13s) beat reads as a bit, not a perch:

      SETUP  [0,0.18]  rise into the wind-up pose (kfs[0]).
      ACTION [0.18,0.74] EFFORT — the arms pump repeatedly between the wind-up
                         (kfs[0]) and the heave (kfs[1]): a shove/lift/pull done
                         several times, unmistakably ACTING the whole zone.
      PAYOFF [0.74,1.0] morph the heave -> overhead cheer (kfs[2]) and hold.

    The old single linear morph was too slow to register on a long beat, so the
    gate read 'Data just rides/stands'. Repeated reps fix that."""
    p = 0.0 if p < 0.0 else 1.0 if p > 1.0 else p
    _windup, _heave, _cheer = kfs[0], kfs[1], kfs[2]
    _ride = _heave[2] == "ride"                    # surfing bit keeps its straddle
    if p < _T_SETUP:                               # SETUP: settle into a crouch
        s = p / _T_SETUP
        lh = list(_windup[0]); rh = list(_windup[1])
        lower = R.lower_ride() if _ride else _braced_legs(crouch=0.8)
        expr_name = _windup[3]
        bob = 10.0 - s * 10.0                        # drop into the crouch
    elif p < _T_EFFORT:                            # ACTION: whole-body effort reps
        u = (p - _T_SETUP) / (_T_EFFORT - _T_SETUP)  # 0..1 across the action zone
        # (1-cos)/2 sweeps crouch/wind-up -> drive/heave -> crouch; _ARC_REPS reps.
        e = (1.0 - math.cos(u * math.pi * 2.0 * _ARC_REPS)) * 0.5
        lh = [_lp(_windup[0][i], _heave[0][i], e) for i in range(3)]
        rh = [_lp(_windup[1][i], _heave[1][i], e) for i in range(3)]
        # legs DRIVE with the heave: deep crouch at wind-up (e=0), tall on the
        # drive (e=1) — the whole silhouette pumps, so no sampled frame reads as
        # merely 'standing on the bar'.
        lower = R.lower_ride() if _ride else _braced_legs(crouch=0.9 * (1.0 - e),
                                                          sway=e * 7.0)
        expr_name = "strain" if e > 0.5 else _heave[3]
        bob = 9.0 - e * 20.0                        # rise up onto the drive
    else:                                          # PAYOFF: heave -> leaping cheer
        f = (p - _T_EFFORT) / (1.0 - _T_EFFORT)
        lh = [_lp(_heave[0][i], _cheer[0][i], f) for i in range(3)]
        rh = [_lp(_heave[1][i], _cheer[1][i], f) for i in range(3)]
        lower = _braced_legs(crouch=0.0)            # spring tall
        expr_name = _cheer[3]
        bob = -math.sin(f * math.pi) * 10.0         # a clear victory hop
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), int(lh[2]))
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), int(rh[2])))
    eyes, mouth = _expr(expr_name)
    return (arms, lower, "", "", eyes, mouth, bob)


_ARC_KFS = {
    # shove a BAR right: wind up low -> heave right -> throw arms up in triumph
    "push_bar_arc": [
        ([120, 250, -8], [150, 285, 4], "stand", "think"),
        ([250, 248, -4], [268, 286, 6], "stand", "strain"),
        ([116, 88, -12], [224, 88, 12], "stand", "laugh"),
    ],
    # surf the rising LINE: crouch to mount -> arms wide riding up -> summit cheer
    "ride_line_arc": [
        ([140, 250, -10], [200, 250, 10], "ride", "think"),
        ([64, 196, -26], [276, 196, 26], "ride", "happy"),
        ([110, 86, -12], [226, 86, 12], "stand", "laugh"),
    ],
    # hoist a SLICE/stack: grab low -> heave to chest -> press overhead
    "lift_arc": [
        ([132, 322, -6], [208, 322, 6], "stand", "think"),
        ([122, 176, -10], [218, 176, 10], "stand", "strain"),
        ([110, 70, -14], [226, 70, 14], "stand", "laugh"),
    ],
    # climb the chart: reach up -> pull through -> reach the top, arms up
    "climb_arc": [
        ([120, 120, -14], [214, 250, 10], "stand", "think"),
        ([128, 168, -12], [210, 150, 12], "stand", "strain"),
        ([116, 88, -12], [224, 88, 12], "stand", "laugh"),
    ],
}


def _arc_anim(name):
    kfs = _ARC_KFS[name]
    return lambda t, _prop: _arc(kfs, t)


# =========================================================================
# COUPLED performances — Data is MECHANICALLY tied to the chart object, not a
# sprite posed near it. Contact (hands ON the object) -> cause (he pulls/pushes)
# -> consequence (the data wins and moves HIM). Baked so his grip point sits on
# the datum; the chart's motion visibly acts on his body. Returns an 8th value:
# a whole-body tilt (deg). Rendered with ground=False (he leaves the floor).
# =========================================================================
def _dangle_legs(kick=0.0, spread=1.0):
    """Legs hanging in the air (feet OFF the ground), kicking by ``kick``."""
    lx = int(150 - 14 * spread - kick)
    rx = int(190 + 14 * spread - kick)
    legs = (R.limb(152, 300, lx, 360, 0, 34, 25, 0) +
            R.limb(188, 300, rx, 362, 0, 34, 25, 0))
    feet = (f'<ellipse cx="{lx-2}" cy="366" rx="25" ry="12" fill="{R.TEAL}" '
            f'stroke="{OUT}" stroke-width="6"/>'
            f'<ellipse cx="{rx+2}" cy="368" rx="25" ry="12" fill="{R.TEAL}" '
            f'stroke="{OUT}" stroke-width="6"/>')
    return legs + feet


def _a_hoist_stack(t, _prop):
    """Data stands UNDER the growing fill (waffle/stack) with both arms pressed
    overhead against its underside, holding it up:
      TAKE IT [0,0.3]  arms locked up, taking the load, standing.
      BUCKLE [0.3,0.7] the pile keeps growing heavier — knees give, he sinks
                       into a deep strain squat, trembling.
      HEAVE  [0.7,1]   one last desperate press — legs drive, arms lock out, a
                       wide-eyed 'it's huge' as he barely holds the full amount.
    His hands (sprite top) are baked onto the fill frontier, so the growing data
    presses down ON him."""
    p = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    tremble = math.sin(t * math.pi * 14) * 3.0
    lh = [150, 58, 16]; rh = [190, 58, -16]           # fists pressed up overhead
    lh[0] += tremble; rh[0] += tremble
    if p < _T_RESIST:                                  # TAKE IT
        lower = _braced_legs(crouch=0.2); expr = "strain"; bob = 2.0
    elif p < _T_EFFORT:                                 # BUCKLE (sink under load)
        s = (p - _T_RESIST) / (_T_EFFORT - _T_RESIST)
        lower = _braced_legs(crouch=0.2 + s * 0.7, sway=6); expr = "strain"
        bob = 2.0 + s * 10.0                           # sinks down
    else:                                              # HEAVE it back up
        s = (p - _T_EFFORT) / (1.0 - _T_EFFORT)
        lower = _braced_legs(crouch=0.9 - s * 0.85); expr = "shock"
        bob = 12.0 - s * 12.0                          # drives back up
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, 0.0)


def _a_shoved_bar(t, _prop):
    """Data braces both hands against the WINNING bar's advancing right FACE and
    pushes back to hold it — but it outgrows him and shoves him along:
      DIG IN [0,0.35]  hands flat on the bar face, heels planted, leaning HARD
                       into it (winning for a beat).
      SKID  [0.35,0.7] boots skidding, still pushing but sliding back.
      SHOVED [0.7,1]   overpowered — knocked upright, arms flailing, a startled
                       look as the bar wins.
    His hands (left side of the sprite) are baked onto the bar tip, so the bar's
    growth visibly drives him."""
    p = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    tremble = math.sin(t * math.pi * 12) * 2.5
    if p < _T_RESIST:                                  # DIG IN — deep crouch, back arched
        s = p / _T_RESIST
        lh = [66 - tremble, 210, -24]; rh = [92 - tremble, 252, -18]
        lower = _braced_legs(crouch=0.85, sway=16)
        expr = "strain"; tilt = 16 - s * 4; bob = 6.0
    elif p < _T_EFFORT:                                 # SKID — up on the toes, sliding
        s = (p - _T_RESIST) / (_T_EFFORT - _T_RESIST)
        lh = [80 + s * 14, 206, -16]; rh = [108 + s * 14, 250, -10]
        lower = _braced_legs(crouch=0.30 - s * 0.25, sway=22 + s * 10)
        expr = "strain"; tilt = 10 - s * 14; bob = 2.0 - s * 4
    else:                                               # LAUNCHED — flung UP off the bar
        s = (p - _T_EFFORT) / (1.0 - _T_EFFORT)
        fl = math.sin(s * math.pi * 2.5) * 16
        lh = [116 + fl, int(96 - s * 42), 8]; rh = [150 + fl, int(70 - s * 42), -8]
        lower = _dangle_legs(kick=fl + s * 10, spread=1.3)
        expr = "shock"; tilt = -10 + fl * 0.6; bob = -s * 26      # big upward launch
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_drag_line(t, _prop):
    """Data GRIPS the rising line's tip overhead and tries to hold it down, but
    the line keeps climbing and DRAGS him up:
      RESIST [0,0.35]  heels dug in, both fists clamped on the line overhead,
                       leaning back hauling down — he's winning for a moment.
      LOSING [0.35,0.7] feet break contact, body straightens, pulled upward.
      DRAGGED [0.7,1]  fully airborne, legs kicking, swinging from the line,
                       a startled 'whoa' — the data beat him.
    Hands stay clamped overhead the whole time (the contact point baked to the
    line tip); what changes is his BODY losing the fight."""
    p = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    # fists clamped together overhead — the grip point (baked onto the line tip)
    grip_y = 46
    lh = [156, grip_y, 18]
    rh = [184, grip_y, -18]
    strain = math.sin(t * math.pi * 12) * 3.0          # trembling effort
    lh[0] += strain; rh[0] += strain
    if p < _T_RESIST:                                   # RESIST: heels dug in
        s = p / _T_RESIST
        lower = _braced_legs(crouch=0.7 - s * 0.2, sway=12)
        expr = "strain"
        tilt = -16 + s * 6                             # leaning back, hauling down
        bob = 4.0
    elif p < _T_EFFORT:                                 # LOSING: lifted off
        s = (p - _T_RESIST) / (_T_EFFORT - _T_RESIST)
        # legs transition from braced to dangling as he leaves the floor
        lower = _dangle_legs(kick=s * 6, spread=1.0 - s * 0.4)
        expr = "shock"
        tilt = -10 + s * 10
        bob = 4.0 - s * 6.0
    else:                                               # DRAGGED: airborne swing
        s = (p - _T_EFFORT) / (1.0 - _T_EFFORT)
        sw = math.sin(s * math.pi * 3) * 14             # swinging under the line
        lower = _dangle_legs(kick=sw, spread=0.6)
        expr = "shock"
        tilt = sw                                       # swings side to side
        bob = -2.0
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_pull_down_win(t, _prop):
    """The FALLING-claim mirror of drag_line: Data grips the descending value's
    tip and hauls DOWN — and this time the data YIELDS. He wins:
      BRACE  heels dug in, fists clamped overhead, hauling (strain).
      YIELD  the value gives way — he sinks with it, still gripping, surprised.
      LANDED grounded, fists thrown up, a big win grin (payoff = victory)."""
    p = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    tremble = math.sin(t * math.pi * 12) * 3.0
    if p < _T_RESIST:                                  # BRACE + haul (pumping)
        s = p / _T_RESIST
        tug = (1.0 - math.cos(s * math.pi * 2 * 2)) * 0.5   # 2 downward tugs
        lh = [156 + tremble, int(46 + tug * 26), 18]
        rh = [184 + tremble, int(46 + tug * 26), -18]
        lower = _braced_legs(crouch=0.75 - tug * 0.25, sway=14)
        expr = "strain"; tilt = -14 + tug * 5; bob = 6.0 - tug * 5.0
    elif p < _T_EFFORT:                                 # YIELD: it comes down
        s = (p - _T_RESIST) / (_T_EFFORT - _T_RESIST)
        lh = [152, int(46 + s * 40), 14]; rh = [188, int(46 + s * 40), -14]
        lower = _braced_legs(crouch=0.75 - s * 0.55, sway=10)
        expr = "shock"; tilt = -14 + s * 14; bob = 4.0 - s * 4.0
    else:                                               # LANDED: victory
        s = (p - _T_EFFORT) / (1.0 - _T_EFFORT)
        up = abs(math.sin(s * math.pi)) * 10
        lh = [116, int(86 - up), -12]; rh = [224, int(86 - up), 12]
        lower = _braced_legs(crouch=0.0)
        expr = "laugh"; tilt = 0.0; bob = -up
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


# =========================================================================
# EXPANDED PERFORMANCE FAMILIES — a broader physical language than drag/shove
# (review Phase 5). Each is a full 3-zone bit (setup -> effort/reversal ->
# payoff/recovery) built on the same rig, distinct enough in silhouette to pass
# the primitive approval gate.
# =========================================================================
def _zone(p):
    """(zone, s) where zone is 0 setup / 1 effort / 2 payoff and s in [0,1]."""
    p = 0.0 if p < 0.0 else 1.0 if p > 1.0 else p
    if p < _T_RESIST:
        return 0, p / _T_RESIST
    if p < _T_EFFORT:
        return 1, (p - _T_RESIST) / (_T_EFFORT - _T_RESIST)
    return 2, (p - _T_EFFORT) / (1.0 - _T_EFFORT)


def _a_balance_beam(t, _prop):
    """BALANCE atop a narrow point: arms out, wobble grows, nearly topples,
    recovers to a steady stand (objective: stay on the datum as it moves)."""
    z, s = _zone(t)
    if z == 0:                                   # arms rise out for balance
        lh = [70 + (1 - s) * 60, 200, -20]; rh = [270 - (1 - s) * 60, 200, 20]
        tilt = 0.0; bob = 2.0; expr = "think"
        lower = _braced_legs(crouch=0.15, sway=2)
    elif z == 1:                                 # wobble builds to a near-fall
        w = math.sin(s * math.pi * 5) * (6 + s * 16)
        lh = [70, 200 - w, -20]; rh = [270, 200 + w, 20]
        tilt = w * 0.8; bob = 2.0 + abs(w) * 0.2; expr = "shock"
        lower = _braced_legs(crouch=0.2 + abs(w) * 0.01, sway=4 + abs(w) * 0.5)
    else:                                        # recovers, steady + relieved
        lh = [116, 180 - s * 40, -14]; rh = [224, 180 - s * 40, 14]
        tilt = (1 - s) * 6; bob = 1.0 - s; expr = "happy"
        lower = _braced_legs(crouch=0.1)
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_catch_fall(t, _prop):
    """CATCH a falling value: braced under it, impact squashes him into a deep
    squat, he holds it up trembling (objective: don't let it hit the floor)."""
    z, s = _zone(t)
    if z == 0:                                   # arms up, tracking the fall
        lh = [130, 90 - s * 20, -12]; rh = [210, 90 - s * 20, 12]
        lower = _braced_legs(crouch=0.25); bob = 2.0; tilt = 0; expr = "shock"
    elif z == 1:                                 # IMPACT: squashed to a squat
        imp = math.sin(min(1.0, s * 2) * math.pi * 0.5)
        lh = [126, 60 + imp * 30, -14]; rh = [214, 60 + imp * 30, 14]
        lower = _braced_legs(crouch=0.25 + imp * 0.65, sway=8)
        bob = 2.0 + imp * 14; tilt = math.sin(s * math.pi * 8) * 3
        expr = "strain"
    else:                                        # holds it aloft, trembling
        tr = math.sin(s * math.pi * 10) * 3
        lh = [122 + tr, 66, -14]; rh = [218 + tr, 66, 14]
        lower = _braced_legs(crouch=0.35 - s * 0.2)
        bob = 6.0 - s * 4; tilt = tr * 0.5; expr = "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_block_wall(t, _prop):
    """BLOCK an advancing mass with his whole back: heels skid, he's bent
    forward pushing backwards, finally braces it to a stop."""
    z, s = _zone(t)
    if z == 0:                                   # throws himself into the brace
        lh = [110 - s * 50, 220 + s * 30, -24]; rh = [140 - s * 60, 180 + s * 20, -18]
        lower = _braced_legs(crouch=0.2 + s * 0.3, sway=6 + s * 12)
        tilt = s * 18; bob = 1 + s * 3
        expr = "strain"
    elif z == 1:
        sk = math.sin(s * math.pi * 4) * 6
        lh = [58 + sk, 250, -24]; rh = [78 + sk, 198, -18]
        lower = _braced_legs(crouch=0.55 + s * 0.2, sway=20 + sk)
        tilt = 20 + s * 4; bob = 4 + s * 4; expr = "strain"
    else:
        lh = [70, 240 - s * 60, -20]; rh = [90, 190 - s * 60, -12]
        lower = _braced_legs(crouch=0.6 - s * 0.5, sway=14)
        tilt = 22 - s * 22; bob = 8 - s * 8; expr = "happy"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_get_buried(t, _prop):
    """GET BURIED by the accumulating amount: shields himself as it piles on,
    is pressed down and down — then pops an arm out (still here!)."""
    z, s = _zone(t)
    if z == 0:                                    # sees it coming, arms shield
        lh = [120, 110 - s * 20, -16]; rh = [220, 110 - s * 20, 16]
        lower = _braced_legs(crouch=0.2 + s * 0.2); bob = 2 + s * 4
        tilt = -4 * s; expr = "shock"
    elif z == 1:                                  # pressed down under the pile
        lh = [130, 120 + s * 60, -10]; rh = [210, 120 + s * 60, 10]
        lower = _braced_legs(crouch=0.4 + s * 0.5, sway=6)
        bob = 6 + s * 22; tilt = math.sin(s * math.pi * 6) * 3
        expr = "strain"
    else:                                         # one defiant arm punches out
        up = math.sin(s * math.pi) * 20
        lh = [150, 260, -6]; rh = [224, 60 - up, 14]
        lower = _braced_legs(crouch=0.85); bob = 26 - s * 6
        tilt = 0.0; expr = "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_overwhelmed(t, _prop):
    """OVERWHELMED by scale: backs away shielding his face as the value keeps
    growing, is dwarfed... then peeks through his fingers in awe."""
    z, s = _zone(t)
    if z == 0:
        lh = [130, 150, -10]; rh = [216, 200, 12]
        lower = _braced_legs(crouch=0.15); bob = 1; tilt = -3 * s
        expr = "shock"
    elif z == 1:
        cower = s * 0.5
        lh = [140 + s * 8, 120 + s * 20, -14]; rh = [206 - s * 8, 120 + s * 20, 14]
        lower = _braced_legs(crouch=0.2 + cower, sway=8)
        bob = 2 + s * 10; tilt = -6 - s * 8; expr = "shock"
    else:
        lh = [142, 128, -12]; rh = [200, 128, 12]
        lower = _braced_legs(crouch=0.45 - s * 0.3)
        bob = 10 - s * 8; tilt = -12 + s * 12; expr = "happy"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_race_sprint(t, _prop):
    """RACE the advancing value: full sprint lean with pumping arms, loses
    ground, dives across at the end (objective: beat the data to the mark)."""
    z, s = _zone(t)
    pump = math.sin(t * math.pi * 14) * 26
    if z == 0:                                    # crouch start
        lh = [110, 250 - s * 30, -18]; rh = [230, 210 + s * 30, 18]
        lower = _braced_legs(crouch=0.6, sway=10); bob = 4; tilt = 8 * s
        expr = "think"
    elif z == 1:                                  # sprint: arms pump, lean hard
        lh = [110, 190 - pump, -18]; rh = [230, 190 + pump, 18]
        lower = _braced_legs(crouch=0.25, sway=16 + abs(pump) * 0.3)
        bob = 2 + abs(pump) * 0.12; tilt = 14; expr = "strain"
    else:                                         # the dive
        lh = [70, 120 - s * 30, -22]; rh = [270, 120 - s * 30, 22]
        lower = _dangle_legs(kick=s * 14, spread=1.3)
        bob = -4 - s * 10; tilt = 26 + s * 30; expr = "shock"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_compressed(t, _prop):
    """COMPRESSED between two growing masses: pushes both arms outward against
    them, is squeezed into a crouch — then squirts free upward."""
    z, s = _zone(t)
    if z == 0:
        w = s * 30
        lh = [130 - w, 210, -20]; rh = [210 + w, 210, 20]
        lower = _braced_legs(crouch=0.2); bob = 2; tilt = 0; expr = "think"
    elif z == 1:
        sq = s
        lh = [96 + sq * 20, 210, -22]; rh = [244 - sq * 20, 210, 22]
        lower = _braced_legs(crouch=0.2 + sq * 0.6, sway=4)
        bob = 2 + sq * 16; tilt = math.sin(s * math.pi * 7) * 2
        expr = "strain"
    else:                                         # pops UP out of the squeeze
        up = math.sin(s * math.pi) * 24
        lh = [116, 90 - up, -14]; rh = [224, 90 - up, 14]
        lower = _dangle_legs(kick=6, spread=0.8)
        bob = 14 - s * 30 - up * 0.4; tilt = 0.0; expr = "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_stretched(t, _prop):
    """STRETCHED between two diverging values: gripping both, pulled wide as
    the gap grows, finally lets go of one and snaps to the winner."""
    z, s = _zone(t)
    if z == 0:
        w = 30 + s * 30
        lh = [170 - w, 190, -16]; rh = [170 + w, 190, 16]
        lower = _braced_legs(crouch=0.25); bob = 2; tilt = 0; expr = "think"
    elif z == 1:
        w = 60 + s * 50
        lh = [170 - w, 186, -22]; rh = [170 + w, 186, 22]
        lower = _braced_legs(crouch=0.3, sway=10 + s * 10)
        bob = 3 + s * 3; tilt = math.sin(s * math.pi * 5) * 4
        expr = "strain"
    else:                                          # released: snaps to one side
        lh = [116, 96, -14]; rh = [200 - s * 30, 120, 10]
        lower = _braced_legs(crouch=0.15)
        bob = -math.sin(s * math.pi) * 8; tilt = -6 + s * 6; expr = "happy"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_discover(t, _prop):
    """DISCOVER the number: leans in shading his eyes, peers closer and
    closer... recoils in a double-take, then presents it, delighted."""
    z, s = _zone(t)
    if z == 0:
        lh = [150, 252, -8]; rh = [206, 116 - s * 10, 16]
        lower = _braced_legs(crouch=0.1); bob = 2; tilt = 6 * s
        expr = "think"
    elif z == 1:
        lean = 8 + s * 8
        lh = [150, 250, -8]; rh = [210, 104, 18]
        lower = _braced_legs(crouch=0.15 + s * 0.1, sway=6)
        bob = 2 + s * 3; tilt = lean; expr = "think"
    else:                                          # the double-take + present
        rec = math.sin(s * math.pi) * 14
        lh = [116, 96 + rec, -14]; rh = [290, 190, 12]
        lower = _braced_legs(crouch=0.1)
        bob = -rec * 0.6; tilt = -10 + s * 10; expr = "shock" if s < 0.6 else "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_compare_scales(t, _prop):
    """COMPARE two values with his arms as the balance beam: both held level,
    one side sinks under the heavier value, tipping his whole body."""
    z, s = _zone(t)
    if z == 0:                                     # arms rise out to level
        lh = [130 - s * 40, 230 - s * 60, -18]; rh = [210 + s * 40, 230 - s * 60, 18]
        lower = _braced_legs(crouch=0.15); bob = 2 - s; tilt = 0; expr = "think"
    elif z == 1:                                   # heavier side sinks
        drop = s * 46
        lh = [88, 170 + drop, -20]; rh = [252, 170 - drop * 0.6, 18]
        lower = _braced_legs(crouch=0.2 + s * 0.15, sway=6)
        bob = 2 + s * 4; tilt = -s * 14; expr = "strain"
    else:                                          # tipped: verdict delivered
        lh = [92, 216, -20]; rh = [254, 130, 18]
        lower = _braced_legs(crouch=0.3 - s * 0.15, sway=8)
        bob = 6 - s * 4; tilt = -14 + s * 4; expr = "happy"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_transform_reveal(t, _prop):
    """TRANSFORM the picture: winds up a full-body spin and lands it arms
    flung wide — ta-da — presenting the changed visual."""
    z, s = _zone(t)
    if z == 0:                                     # wind-up twist
        lh = [190, 230, 10]; rh = [230, 150, 14]
        lower = _braced_legs(crouch=0.3, sway=8); bob = 3
        tilt = -10 * s; expr = "think"
    elif z == 1:                                   # the SPIN (big tilt sweep)
        tilt = math.sin(s * math.pi * 2) * 24
        lh = [110 + s * 30, 180, -16]; rh = [230 - s * 30, 180, 16]
        lower = _braced_legs(crouch=0.25, sway=12)
        bob = 2 - math.sin(s * math.pi) * 8; expr = "happy"
    else:                                          # TA-DA
        w = s * 30
        lh = [96 - w * 0.2, 120, -18]; rh = [244 + w * 0.2, 120, 18]
        lower = _braced_legs(crouch=0.1)
        bob = -math.sin(s * math.pi) * 6; tilt = 0.0; expr = "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_fail_recover(t, _prop):
    """FAIL AND RECOVER: knocked flat by the datum (a real face-plant tilt),
    pushes himself back up, dusts off, stands tall — resilience beat."""
    z, s = _zone(t)
    if z == 0:                                     # the hit: knocked over
        lh = [130, 160, -14]; rh = [210, 160, 14]
        lower = _braced_legs(crouch=0.2 + s * 0.3, sway=8)
        bob = s * 12; tilt = s * 26; expr = "shock"
    elif z == 1:                                   # pushing back up
        lh = [110, 250 - s * 60, -18]; rh = [230, 250 - s * 60, 18]
        lower = _braced_legs(crouch=0.6 - s * 0.4, sway=10 - s * 6)
        bob = 12 - s * 10; tilt = 26 - s * 24; expr = "strain"
    else:                                          # dust-off, stand tall
        du = math.sin(s * math.pi * 3) * 8
        lh = [140 + du, 240, -8]; rh = [216, 96, 14]
        lower = _braced_legs(crouch=0.05)
        bob = -s * 2; tilt = 0.0; expr = "happy"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


def _a_stack_tiles(t, _prop):
    """STACK/BUILD: places pieces onto the pile in a repeated squat-lift-place
    cycle, pile outpaces him, final slam-place and a proud stand-back."""
    z, s = _zone(t)
    if z == 0:                                     # first pick-up
        lh = [130, 250 + s * 40, -12]; rh = [210, 250 + s * 40, 12]
        lower = _braced_legs(crouch=0.2 + s * 0.4); bob = 2 + s * 8
        tilt = 4 * s; expr = "think"
    elif z == 1:                                   # place cycles (squat-lift)
        cyc = (1.0 - math.cos(s * math.pi * 2 * 3)) * 0.5
        lh = [128, 250 - cyc * 160, -12]; rh = [212, 250 - cyc * 160, 12]
        lower = _braced_legs(crouch=0.55 - cyc * 0.45, sway=6)
        bob = 8 - cyc * 10; tilt = math.sin(s * math.pi * 6) * 3
        expr = "strain"
    else:                                          # slam the last one, step back
        lh = [126, 96, -14]; rh = [214, 96, 14]
        lower = _braced_legs(crouch=0.1)
        bob = -math.sin(s * math.pi) * 8; tilt = -4 + s * 4; expr = "laugh"
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    eyes, mouth = _expr(expr)
    return (arms, lower, "", "", eyes, mouth, bob, tilt)


ANIMATORS = {
    "juggle": _a_juggle, "push": _a_push, "ride": _a_ride,
    "stagger_under": _a_stagger, "carry": _a_carry, "hold_up": _a_hold_up,
    "sit_on": _a_sit, "lean_on": _a_lean, "present": _a_present,
    "cheer": _a_cheer, "point_at": _a_point,
    # prop-less DATA actions (Data performs ON the chart element):
    "push_bar": _a_push_bar, "ride_line": _a_ride_line,
    "climb": _a_climb, "lift": _a_lift,
    # ARC data-actions (full setup->action->payoff across the beat):
    "push_bar_arc": _arc_anim("push_bar_arc"),
    "ride_line_arc": _arc_anim("ride_line_arc"),
    "lift_arc": _arc_anim("lift_arc"),
    "climb_arc": _arc_anim("climb_arc"),
    # COUPLED (mechanically tied to the chart object):
    "drag_line": _a_drag_line,
    "shoved_bar": _a_shoved_bar,
    "hoist_stack": _a_hoist_stack,
    "pull_down_win": _a_pull_down_win,
    # EXPANDED performance families (Phase 5):
    "balance_beam": _a_balance_beam,
    "catch_fall": _a_catch_fall,
    "block_wall": _a_block_wall,
    "get_buried": _a_get_buried,
    "overwhelmed": _a_overwhelmed,
    "race_sprint": _a_race_sprint,
    "compressed": _a_compressed,
    "stretched": _a_stretched,
    "discover": _a_discover,
    "compare_scales": _a_compare_scales,
    "transform_reveal": _a_transform_reveal,
    "fail_recover": _a_fail_recover,
    "stack_tiles": _a_stack_tiles,
}

# =========================================================================
# PERFORMANCES — "generate a performance, not an action name" (ChatGPT §).
# A constrained library of VERIFIED performances (each animator above passed the
# primitive approval gate). The director SELECTS and PARAMETERISES one from the
# story's actual CLAIM — rising vs falling vs contest vs part-of-whole — it does
# not invent arbitrary hand coordinates, and it is not a chart-kind lookup.
# Every entry states contact, cause and consequence plus its 3-beat structure.
# =========================================================================
VERIFIED_PERFORMANCES = {
    "drag_line": {
        "contact": "both fists clamped on the object's tip",
        "cause": "hauls DOWN trying to stop the rise",
        "consequence": "the data keeps rising and DRAGS HIM airborne",
        "family": "pull",
        "data_affects_mascot": True, "mascot_affects_data": False,
        "supported_shapes": ["trend", "part_to_whole", "two_value"],
        "supported_relationships": ["increase", "dominance", "growth"],
        "performance_meaning": "resist a growing value and lose",
        "requires": ["moving endpoint"],
        "beats": [
            {"phase": "setup", "pose": "anticipate", "contact": "approach"},
            {"phase": "objective", "pose": "engage", "contact": "both_hands"},
            {"phase": "effort", "pose": "work", "repetitions": 2},
            {"phase": "reversal", "pose": "turn"},
            {"phase": "consequence", "pose": "affected"},
            {"phase": "payoff", "pose": "land"},
            {"phase": "recovery", "pose": "settle"},
        ],
    },
    "pull_down_win": {
        "contact": "both fists clamped on the object's tip",
        "cause": "hauls DOWN on the falling value",
        "consequence": "the value yields — he lands it and celebrates",
        "family": "pull",
        "data_affects_mascot": True, "mascot_affects_data": True,
        "supported_shapes": ["trend", "two_value"],
        "supported_relationships": ["decrease", "decline"],
        "performance_meaning": "pull a falling value down and win",
        "requires": ["moving endpoint", "falling claim"],
        "beats": [
            {"phase": "setup", "pose": "anticipate", "contact": "approach"},
            {"phase": "objective", "pose": "engage", "contact": "both_hands"},
            {"phase": "effort", "pose": "work", "repetitions": 2},
            {"phase": "reversal", "pose": "turn"},
            {"phase": "consequence", "pose": "affected"},
            {"phase": "payoff", "pose": "land"},
            {"phase": "recovery", "pose": "settle"},
        ],
    },
    "shoved_bar": {
        "contact": "both hands braced on the bar's advancing face",
        "cause": "pushes back to hold the leader",
        "consequence": "the bar outgrows him — skids, then LAUNCHED off it",
        "family": "push",
        "data_affects_mascot": True, "mascot_affects_data": False,
        "supported_shapes": ["ranking", "trend"],
        "supported_relationships": ["dominance", "overtake", "increase",
                                    "imbalance"],
        "performance_meaning": "hold the leader back and be overpowered",
        "requires": ["advancing edge"],
        "beats": [
            {"phase": "setup", "pose": "anticipate", "contact": "approach"},
            {"phase": "objective", "pose": "engage", "contact": "both_hands"},
            {"phase": "effort", "pose": "work", "repetitions": 2},
            {"phase": "reversal", "pose": "turn"},
            {"phase": "consequence", "pose": "affected"},
            {"phase": "payoff", "pose": "land"},
            {"phase": "recovery", "pose": "settle"},
        ],
    },
    "hoist_stack": {
        "contact": "arms pressed overhead on the fill's underside",
        "cause": "holds the growing pile up",
        "consequence": "the load buckles him, he barely heaves it",
        "family": "carry",
        "data_affects_mascot": True, "mascot_affects_data": False,
        "supported_shapes": ["part_to_whole", "ranking"],
        "supported_relationships": ["accumulation", "dominance", "share",
                                    "imbalance"],
        "performance_meaning": "bear the growing total's weight",
        "requires": ["growing fill"],
        "beats": [
            {"phase": "setup", "pose": "anticipate", "contact": "approach"},
            {"phase": "objective", "pose": "engage", "contact": "both_hands"},
            {"phase": "effort", "pose": "work", "repetitions": 2},
            {"phase": "reversal", "pose": "turn"},
            {"phase": "consequence", "pose": "affected"},
            {"phase": "payoff", "pose": "land"},
            {"phase": "recovery", "pose": "settle"},
        ],
    },
}

def _perf_entry(family, contact, cause, consequence, meaning, shapes, rels,
                requires, dam, mad):
    """A full performance definition: 8-part beat structure + semantics."""
    return {
        "family": family, "contact": contact, "cause": cause,
        "consequence": consequence, "performance_meaning": meaning,
        "supported_shapes": shapes, "supported_relationships": rels,
        "requires": requires,
        "data_affects_mascot": dam, "mascot_affects_data": mad,
        "beats": [
            {"phase": "setup", "pose": "anticipate", "contact": "approach"},
            {"phase": "objective", "pose": "engage", "contact": "both_hands"},
            {"phase": "effort", "pose": "work", "repetitions": 2},
            {"phase": "reversal", "pose": "turn"},
            {"phase": "consequence", "pose": "affected"},
            {"phase": "payoff", "pose": "land"},
            {"phase": "recovery", "pose": "settle"},
        ],
    }


VERIFIED_PERFORMANCES.update({
    "balance_beam": _perf_entry(
        "balance", "feet planted on the datum's narrow top",
        "fights to stay balanced as it moves", "wobbles to a near-fall, steadies",
        "stay atop an unstable value", ["trend", "two_value"],
        ["volatility", "instability", "stable_high"], ["perch point"],
        True, False),
    "catch_fall": _perf_entry(
        "catch", "arms under the falling value", "catches the drop",
        "impact squashes him into a squat; he holds it", "arrest a falling value",
        ["trend", "two_value"], ["decrease", "decline", "crash"],
        ["falling element"], True, True),
    "block_wall": _perf_entry(
        "block", "back and hands braced against the advancing mass",
        "blocks its advance", "skids back, finally holds the line",
        "hold an advancing mass", ["ranking", "part_to_whole"],
        ["dominance", "increase", "spread"], ["advancing edge"], True, True),
    "get_buried": _perf_entry(
        "get_buried", "body under the accumulating pile", "shields himself",
        "pressed down until only an arm pops out", "be buried by accumulation",
        ["part_to_whole", "ranking", "trend"],
        ["accumulation", "dominance", "overwhelm"], ["growing fill"],
        True, False),
    "overwhelmed": _perf_entry(
        "get_overwhelmed", "dwarfed beside the towering value",
        "backs away shielding his face", "is dwarfed, then awed",
        "convey overwhelming scale", ["trend", "ranking", "part_to_whole"],
        ["scale", "dominance", "overwhelm"], ["dominant element"],
        True, False),
    "race_sprint": _perf_entry(
        "race", "sprinting flush with the advancing edge",
        "races the data to the mark", "loses ground and dives across",
        "race a fast-moving value", ["ranking", "trend"],
        ["overtake", "speed", "increase"], ["advancing edge"], True, False),
    "compressed": _perf_entry(
        "compress", "arms braced on the two closing masses",
        "pushes both back", "squeezed into a crouch, pops free",
        "be squeezed by converging values", ["two_value", "part_to_whole"],
        ["convergence", "imbalance", "squeeze"], ["two elements"],
        True, False),
    "stretched": _perf_entry(
        "stretch", "gripping both diverging values",
        "tries to hold them together", "stretched wide, snaps to the winner",
        "span a widening gap", ["two_value", "ranking"],
        ["divergence", "gap", "imbalance"], ["two elements"], True, False),
    "discover": _perf_entry(
        "discover", "leaning onto the datum, peering at it",
        "investigates the number", "double-takes and presents it",
        "reveal a surprising value", ["trend", "ranking", "two_value",
                                      "part_to_whole"],
        ["surprise", "outlier", "reveal"], [], False, False),
    "compare_scales": _perf_entry(
        "compare", "each arm holding one value like scale pans",
        "weighs the two", "the heavier side tips his whole body",
        "embody the comparison", ["two_value", "ranking"],
        ["imbalance", "dominance", "comparison"], ["two elements"],
        True, False),
    "transform_reveal": _perf_entry(
        "transform", "hands on the visual as it changes",
        "spins the picture into a new form", "lands the ta-da reveal",
        "transform the metaphor", ["part_to_whole", "trend"],
        ["reframe", "transformation", "share"], [], False, True),
    "fail_recover": _perf_entry(
        "recover", "knocked flat by the datum's force",
        "takes the hit", "gets back up, dusts off, stands tall",
        "fail and recover", ["trend", "ranking"],
        ["setback", "crash", "resilience"], [], True, False),
    "stack_tiles": _perf_entry(
        "stack", "hands placing each new piece on the pile",
        "builds the total himself", "the pile outpaces him; final slam-place",
        "assemble the accumulating total", ["part_to_whole", "ranking"],
        ["accumulation", "share", "growth"], ["growing fill"], False, True),
})

_FALLING = ("fell", "fall", "drop", "dropp", "declin", "below", "under",
            "shrink", "shrank", "down to", "lowest", "sank", "slid")
_RISING = ("rise", "rising", "climb", "grew", "grow", "surge", "accelerat",
           "record", "tripl", "doubl", "up to", "added", "highest", "only ever")


# Where each performance ATTACHES to the datum: sprite box_alignment so his
# CONTACT POINT sits on the data object (top-grip actions hang from it,
# feet-on actions stand on it, face-brace actions press against its edge).
ACTION_ALIGN = {
    "drag_line": (0.5, 0.80), "pull_down_win": (0.5, 0.80),
    "hoist_stack": (0.5, 0.80), "get_buried": (0.5, 0.60),
    "catch_fall": (0.5, 0.75), "compressed": (0.5, 0.5),
    "shoved_bar": (0.28, 0.5), "block_wall": (0.28, 0.5),
    "race_sprint": (0.35, 0.15), "stretched": (0.5, 0.5),
    "balance_beam": (0.5, 0.04), "discover": (0.5, 0.04),
    "compare_scales": (0.5, 0.04), "transform_reveal": (0.5, 0.04),
    "fail_recover": (0.5, 0.04), "overwhelmed": (0.5, 0.04),
    "stack_tiles": (0.5, 0.04),
}

_SHAPE_OF_KIND = {
    "trend": "trend", "timeline": "trend",
    "comparison": "two_value",
    "stack": "part_to_whole", "share": "part_to_whole",
    "waffle_grid": "part_to_whole",
    "pictorial_race": "ranking", "rank": "ranking", "bars": "ranking",
    "pictograph": "ranking", "bubbles": "ranking",
    "geo_us": "ranking", "geo_world": "ranking",
}

_REL_WORDS = {
    "decrease": ("fell", "fall", "drop", "declin", "below", "under", "shrank",
                 "down to", "sank", "slid", "lowest"),
    "increase": ("rise", "rising", "climb", "grew", "grow", "surge", "added",
                 "accelerat", "tripl", "doubl", "record", "only ever",
                 "highest"),
    "dominance": ("leads", "leader", "dominat", "tops", "biggest", "largest",
                  "most", "still leads", "pulls ahead", "no. 1", "number one"),
    "overtake": ("overtak", "passes", "passed", "surpass", "closing in",
                 "catching up", "tipping point"),
    "imbalance": ("gap", "versus", " vs ", "twice", "half the", "imbalance",
                  "far more", "far less"),
    "accumulation": ("adds", "added each", "stack", "accumulat", "pile",
                     "total", "combined"),
    "scale": ("billion", "trillion", "million", "vast", "unexplored", "dwarf",
              "massive", "per second"),
    "surprise": ("actually", "surpris", "you'd never", "turns out", "hidden",
                 "secretly"),
}


def analyze_claim(claim: str) -> dict:
    """The performance-selection INPUT (review Phase 5.2): claim ->
    relationship + direction. Selection then follows story MEANING, so the
    same chart kind supports different performances for different claims."""
    low = (claim or "").lower()
    rels = [r for r, ws in _REL_WORDS.items() if any(w in low for w in ws)]
    falling = "decrease" in rels and "increase" not in rels
    return {"claim": claim, "relationships": rels or ["dominance"],
            "direction": "falling" if falling else
            ("rising" if "increase" in rels else "stable_high")}


def performance_for(kind: str, claim: str = "", target: str = "",
                    phase: str = "action", used_families=None,
                    seed: int = 0) -> dict:
    """Select + parameterise a VERIFIED performance from the story's actual
    CLAIM — its relationship and direction — never merely the chart type.
    ``used_families`` (families already performed in this story) drives
    ANTI-REPETITION: the same family is not reused while a compatible
    alternative exists. Returns the full executable spec, including the
    selection input, for the manifest/attach record."""
    if phase == "payoff":
        return {"action": "cheer", "goal": "land the takeaway",
                "target": target, "beats": [
                    {"phase": "payoff", "pose": "cheer"}]}
    intent = analyze_claim(claim)
    shape = _SHAPE_OF_KIND.get(kind, "ranking")
    used = set(used_families or ())
    # candidates: performances that support this shape, ranked by relationship
    # overlap with the claim (2 pts) then by structural fit (1 pt baseline)
    scored = []
    for name, meta in VERIFIED_PERFORMANCES.items():
        if shape not in meta.get("supported_shapes", ()):
            continue
        overlap = len(set(meta.get("supported_relationships", ())) &
                      set(intent["relationships"]))
        # direction-specific hard preferences
        if name == "pull_down_win" and intent["direction"] != "falling":
            continue
        if name == "drag_line" and intent["direction"] == "falling":
            overlap -= 1
        scored.append((overlap, name, meta))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if not scored:
        scored = [(0, "shoved_bar", VERIFIED_PERFORMANCES["shoved_bar"])]
    # anti-repetition: first candidate whose FAMILY is unused; else best
    pick = None
    ordered = scored[seed % max(1, len(scored)):] + \
        scored[:seed % max(1, len(scored))] if scored else []
    ordered.sort(key=lambda x: -x[0])            # keep overlap dominant
    for ov, name, meta in ordered:
        if meta.get("family", name) not in used:
            pick = (name, meta)
            break
    if pick is None:
        pick = (scored[0][1], scored[0][2])
    act, spec = pick
    goal = f"{spec.get('performance_meaning', 'perform')} — {target or kind}"
    return {"action": act, "family": spec.get("family", act),
            "goal": goal, "target": target,
            "selection_input": {**intent, "shape": shape,
                                "used_families": sorted(used)},
            "contact": spec["contact"], "cause": spec["cause"],
            "consequence": spec["consequence"],
            "data_affects_mascot": spec.get("data_affects_mascot", True),
            "mascot_affects_data": spec.get("mascot_affects_data", False),
            "beats": spec["beats"]}

# Chart KIND -> the data action Data performs on it (deterministic, on-topic).
DATA_ACTION = {
    "trend": "ride_line", "timeline": "ride_line",
    "pictorial_race": "push_bar", "rank": "push_bar", "bars": "push_bar",
    "comparison": "push_bar",
    "waffle_grid": "lift", "share": "lift", "pictograph": "lift",
    "bubbles": "climb", "geo_world": "climb", "geo_us": "climb",
    "geo_city": "climb",
}


def data_action_spec(kind: str, phase: str = "action") -> dict:
    """A deterministic ANIMATED action spec for a chart kind. phase 'payoff'
    swaps to a celebration so the beat lands setup->action->PAYOFF."""
    if phase == "payoff":
        return {"action": "cheer", "prop": "none"}
    return {"action": DATA_ACTION.get(kind, "push_bar"), "prop": "none"}

# --------------------------------------------------------------------------
# GENERIC per-scene animator — the "regenerate the performance per scene"
# engine. Instead of reusing one of the fixed named actions, a beat can carry a
# full bespoke POSE: where each HAND goes (wrist x,y + bend), which lower body,
# a prop behind and/or in front at chosen spots, the expression, and which limb
# oscillates. Data performs ANY such pose with the SAME rig — nothing about HOW
# he's drawn changes — so two "sitting" beats can be totally different acts
# (spooning soup off a can vs. gripping a bird's feathers mid-flight). The brain
# authors these on the fly (author_performance); choose() is the fallback.
# --------------------------------------------------------------------------
_LOWER = {"stand": R.lower_stand, "seated": R.lower_seated, "ride": R.lower_ride}


def _a_pose(t, spec):
    p = spec.get("pose", {}) or {}
    lh = list(p.get("lh", [150, 252, -8]))     # left  wrist [x, y, bend]
    rh = list(p.get("rh", [190, 252, 8]))      # right wrist [x, y, bend]
    m = p.get("motion", {}) or {}
    osc = _s(t) * float(m.get("amp", 5))
    limb = m.get("limb", "bob")
    if limb in ("l", "both"):
        lh[1] = lh[1] + osc
    if limb in ("r", "both"):
        rh[1] = rh[1] + osc
    arms = (R.arm(*R.SHL, int(lh[0]), int(lh[1]), lh[2])
            + R.arm(*R.SHR, int(rh[0]), int(rh[1]), rh[2]))
    lower = _LOWER.get(p.get("lower", "stand"), R.lower_stand)()

    def _draw(name, at):
        d = PROPS.get(name)
        return d(int(at[0]), int(at[1])) if d else ""
    back = _draw(p["back"], p.get("back_at", [170, 372])) if p.get("back") else ""
    front = _draw(p["front"], p.get("front_at", [200, 250])) if p.get("front") else ""
    look = (0, 3) if p.get("lower") in ("seated", "ride") else (0, 0)
    eyes, mouth = _expr(p.get("expr", "happy"), look=look)
    bob = _s(t) * float(p.get("bob", 3))
    return (arms, lower, back, front, eyes, mouth, bob)


def compose_anim(spec: dict, t: float) -> str:
    """Animated scene-mascot SVG at phase t in [0,1): Data moving + a grounded
    environment. Seamless because every animator is periodic in t."""
    prop_name = spec.get("prop", "price_tag")
    action = spec.get("action", "present")
    text = spec.get("text", "")
    draw = PROPS.get(prop_name, price_tag)
    if prop_name == "price_tag":
        def prop(cx, cy, s=1.0): return draw(cx, cy, s, text=text)
    else:
        prop = draw
    if action == "pose":
        # bespoke per-scene performance authored for THIS beat
        res = _a_pose(t, spec)
    else:
        res = ANIMATORS.get(action, _a_carry)(t, prop)
    arms, lower, back, front, eyes, mouth, bob = res[:7]
    # COUPLED performances (Data attached to a chart object) return an 8th value:
    # a whole-body TILT (deg) so he leans/swings with the data's pull. They also
    # skip the ground shadow — a shadow under a mascot hanging off a rising line
    # reads as 'floating sprite', the very thing we're fixing.
    tilt = float(res[7]) if len(res) > 7 else 0.0
    grounded = spec.get("ground", True)
    env = ENVS.get(prop_name, _shadow)() if grounded else ""
    masc = R.assemble(arms, eyes, mouth, lower=lower,
                      extra_back=back, extra_front=front)
    inner = env + (f'<g transform="translate(0,{bob:.1f}) '
                   f'rotate({tilt:.1f},170,210)">{masc}</g>')
    return R.wrap(inner, view=ANIM_VIEW, label=f"Data {action} {prop_name}")


def render_frames(spec: dict, size: int, n: int = 20) -> list[bytes]:
    """Rasterise a seamless animation loop -> n square transparent PNGs."""
    return [_rasterise(compose_anim(spec, i / n), size) for i in range(n)]
