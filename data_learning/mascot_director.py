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
    # Bias the rotation so a strong keyword match LEADS for this beat, then pick
    # by index so each beat in the video lands on a different act.
    order = list(_DIVERSE)
    for pat, preset in _PERF_RULES:
        if re.search(pat, hay) and preset in order:
            order.remove(preset)
            order.insert(0, preset)
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


ANIMATORS = {
    "juggle": _a_juggle, "push": _a_push, "ride": _a_ride,
    "stagger_under": _a_stagger, "carry": _a_carry, "hold_up": _a_hold_up,
    "sit_on": _a_sit, "lean_on": _a_lean, "present": _a_present,
    "cheer": _a_cheer, "point_at": _a_point,
}

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
        arms, lower, back, front, eyes, mouth, bob = _a_pose(t, spec)
    else:
        arms, lower, back, front, eyes, mouth, bob = \
            ANIMATORS.get(action, _a_carry)(t, prop)
    env = ENVS.get(prop_name, _shadow)()
    masc = R.assemble(arms, eyes, mouth, lower=lower,
                      extra_back=back, extra_front=front)
    inner = env + f'<g transform="translate(0,{bob:.1f})">{masc}</g>'
    return R.wrap(inner, view=ANIM_VIEW, label=f"Data {action} {prop_name}")


def render_frames(spec: dict, size: int, n: int = 20) -> list[bytes]:
    """Rasterise a seamless animation loop -> n square transparent PNGs."""
    return [_rasterise(compose_anim(spec, i / n), size) for i in range(n)]
