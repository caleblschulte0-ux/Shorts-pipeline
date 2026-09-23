"""Scene: one narrated beat's picture — validated, laid out, and rendered.

A scene spec is plain data an author writes next to the words it sits under:

    {"setting": "cave_mouth", "time": "night", "weather": "clear",
     "shot": "close",
     "cast":  [{"who": "man", "pose": "sit", "action": "warm_hands",
                "mood": "calm", "at": "left"}],
     "props": ["campfire", {"name": "wolf", "at": "right"}]}

`validate()` refuses any name the kit cannot draw (no silent defaults), any
action a pose cannot do, any prop from another era, and any scene with
nothing LIVING in it — a sleep video is calm, but a picture where nothing is
happening for thirty seconds is a still, and the showrunner is right to call
a still frozen.

Rendering is honest about what moves. The still world (sky, land, buildings,
anything that does not depend on time) is painted ONCE per scene into an
image; every frame paints that image, then the living things over it — fire,
water, weather, animals, and people doing their work — then the light. No
camera moves, nothing boils (see ink.py).
"""
from __future__ import annotations

import math
import random

import cairo

from . import ink, people, props, settings
from .props import PROPS
from .settings import SETTINGS, TIMES, WEATHER

W, H = settings.W, settings.H
ERAS = ("stone_age", "medieval")
SHOTS = ("close", "wide")
SLOTS = {"far_left": 0.1, "left": 0.24, "center_left": 0.37, "center": 0.5,
         "center_right": 0.63, "right": 0.76, "far_right": 0.9}
STILL = {"tent", "hut", "tree", "pine", "bush", "rock", "woodpile", "bedroll", "hide_rack",
         "table", "bench", "barrel", "stones", "basket", "bed", "cave_painting"}
MAX_CAST, MAX_PROPS = 4, 6
LIGHT_ITEMS = ("torch", "lantern")


# ------------------------------------------------------------------ contract
def _prop_list(spec):
    out = []
    for p in spec.get("props") or []:
        if isinstance(p, str):
            out.append({"name": p})
        elif isinstance(p, dict):
            out.append(dict(p))
        else:
            out.append({"name": repr(p)})
    return out


def is_living(spec: dict) -> bool:
    if spec.get("weather") in ("rain", "snow"):
        return True
    st = SETTINGS.get(spec.get("setting"))
    if st is not None and st.water:
        return True
    for p in _prop_list(spec):
        pr = PROPS.get(p.get("name"))
        if pr is not None and pr.living:
            return True
    for c in spec.get("cast") or []:
        if isinstance(c, dict) and c.get("item") in LIGHT_ITEMS:
            return True
    return False


def validate(spec, era: str) -> list[str]:
    """Everything wrong with one scene spec, or []."""
    if not isinstance(spec, dict):
        return ["scene is not an object"]
    bad = []
    if era not in ERAS:
        return [f"era {era!r} is not one of {ERAS}"]
    st = SETTINGS.get(spec.get("setting"))
    if st is None:
        bad.append(f"setting {spec.get('setting')!r} is not one of {sorted(SETTINGS)}")
    elif era not in st.eras:
        bad.append(f"setting {spec['setting']!r} does not exist in {era}")
    if spec.get("time") not in TIMES:
        bad.append(f"time {spec.get('time')!r} is not one of {TIMES}")
    if spec.get("weather", "clear") not in WEATHER:
        bad.append(f"weather {spec.get('weather')!r} is not one of {WEATHER}")
    if st is not None and st.interior and spec.get("weather", "clear") not in ("clear",):
        bad.append("an interior scene has no weather — use weather 'clear'")
    if spec.get("shot", "close") not in SHOTS:
        bad.append(f"shot {spec.get('shot')!r} is not one of {SHOTS}")
    cast = spec.get("cast") or []
    if not isinstance(cast, list) or len(cast) > MAX_CAST:
        bad.append(f"cast must be a list of at most {MAX_CAST}")
        cast = []
    for i, c in enumerate(cast):
        if not isinstance(c, dict):
            bad.append(f"cast[{i}] is not an object")
            continue
        if c.get("who") not in people.WHO:
            bad.append(f"cast[{i}].who {c.get('who')!r} is not one of {sorted(people.WHO)}")
        pose, action = c.get("pose", "stand"), c.get("action", "idle")
        if pose not in people.POSES:
            bad.append(f"cast[{i}].pose {pose!r} is not one of {people.POSES}")
        if action not in people.ACTIONS:
            bad.append(f"cast[{i}].action {action!r} is not one of {sorted(people.ACTIONS)}")
        elif pose in people.POSES and pose not in people.ACTIONS[action]["poses"]:
            bad.append(f"cast[{i}]: a person cannot {action!r} while {pose!r} "
                       f"(allowed: {people.ACTIONS[action]['poses']})")
        if c.get("mood", "calm") not in people.MOODS:
            bad.append(f"cast[{i}].mood {c.get('mood')!r} is not one of {people.MOODS}")
        if c.get("item") is not None and c.get("item") not in people.ITEMS:
            bad.append(f"cast[{i}].item {c.get('item')!r} is not one of {people.ITEMS}")
        if c.get("at") is not None and c.get("at") not in SLOTS:
            bad.append(f"cast[{i}].at {c.get('at')!r} is not one of {sorted(SLOTS)}")
        if c.get("facing") is not None and c.get("facing") not in ("left", "right"):
            bad.append(f"cast[{i}].facing must be left or right")
    pl = _prop_list(spec)
    if len(pl) > MAX_PROPS:
        bad.append(f"at most {MAX_PROPS} props")
    for i, p in enumerate(pl):
        pr = PROPS.get(p.get("name"))
        if pr is None:
            bad.append(f"props[{i}] {p.get('name')!r} is not one of {sorted(PROPS)}")
            continue
        if era not in pr.eras:
            bad.append(f"props[{i}] {p['name']!r} does not exist in {era}")
        if p.get("at") is not None and p.get("at") not in SLOTS:
            bad.append(f"props[{i}].at {p.get('at')!r} is not one of {sorted(SLOTS)}")
    if not bad and not is_living(spec):
        bad.append("nothing in this scene moves: add a living thing (a campfire, hearth, torch, "
                   "candle or cauldron; a river, lake or sea setting; rain or snow; or a person "
                   "holding a torch or lantern)")
    return bad


# ------------------------------------------------------------------ layout
def layout(spec: dict, seed: int) -> dict:
    """Place every prop and person. Deterministic in (spec, seed)."""
    r = random.Random(seed)
    cast = [dict(c) for c in (spec.get("cast") or [])]
    pl = _prop_list(spec)
    shot = spec.get("shot") or ("close" if len(cast) <= 2 else "wide")
    s = 2.05 if shot == "close" else 1.25
    gy = H * settings.GROUND_Y
    placed = []
    taken = []

    def free(x, w):
        return all(abs(x - tx) > (w + tw) / 2 * 0.8 for tx, tw in taken)

    def put(x, w):
        taken.append((x, w))

    # the focal thing: the first light/living prop, else the first prop
    focal = None
    for p in pl:
        if PROPS[p["name"]].light or PROPS[p["name"]].living:
            focal = p
            break
    if focal is None and pl:
        focal = pl[0]
    focal_x = W * SLOTS[focal["at"]] if focal and focal.get("at") else W * 0.5

    def prop_geom(p):
        pr = PROPS[p["name"]]
        ps = s * (0.82 if pr.layer == "back" else 1.0) * (0.95 if shot == "wide" else 1.0)
        py = gy + {"back": -60 * s, "mid": 10 * s, "front": 70 * s}[pr.layer]
        return pr, ps, py, pr.width * ps

    if focal:
        pr, ps, py, w = prop_geom(focal)
        placed.append(dict(name=focal["name"], x=focal_x, y=py, s=ps, layer=pr.layer,
                           seed=seed + 1))
        if pr.layer != "back":
            put(focal_x, w)

    # people next, around the focal thing and facing it
    slots_auto = [0.29, 0.71, 0.15, 0.85] if focal else [0.35, 0.65, 0.2, 0.8]
    figs = []
    pw = 190 * s
    for i, c in enumerate(cast):
        if c.get("at"):
            x = W * SLOTS[c["at"]]
        else:
            x = None
            for k in range(len(slots_auto)):
                cand = W * slots_auto[(i + k) % len(slots_auto)]
                if free(cand, pw):
                    x = cand
                    break
            x = x if x is not None else W * slots_auto[i % len(slots_auto)]
        facing = c.get("facing") or ("right" if x < focal_x else "left")
        pose = c.get("pose", "stand")
        if pose == "lie" and not c.get("at"):
            x = max(W * 0.12 + 200 * s, min(W * 0.88 - 200 * s, x))
        put(x, pw)
        figs.append(dict(who=c["who"], pose=pose, action=c.get("action", "idle"),
                         mood=c.get("mood", "calm"), item=c.get("item"), x=x,
                         y=gy + 30 * s, s=s, facing=facing, seed=seed * 13 + i * 101))

    # a pot or cauldron belongs in front of whoever is stirring it
    stirrer = next((f for f in figs if f["action"] == "stir"), None)
    rest = [p for p in pl if p is not focal]
    for p in rest:
        pr, ps, py, w = prop_geom(p)
        if p.get("at"):
            x = W * SLOTS[p["at"]]
        elif stirrer and p["name"] in ("pot", "cauldron") and not stirrer.get("_pot"):
            R = people.R0 * s * people.WHO[stirrer["who"]]["size"]
            d = 1 if stirrer["facing"] == "right" else -1
            x = stirrer["x"] + d * (1.55 * R + (50 if p["name"] == "pot" else 20) * ps)
            stirrer["_pot"] = True
        else:
            cands = ([0.12, 0.88, 0.28, 0.72, 0.5, 0.06, 0.94] if pr.layer == "back"
                     else [0.4, 0.6, 0.08, 0.92, 0.2, 0.8, 0.33, 0.67])
            x = None
            for cnd in cands:
                if pr.layer == "back" or free(W * cnd, w):
                    x = W * cnd
                    if pr.layer == "back" and not all(abs(W * cnd - q["x"]) > 250 for q in placed
                                                      if q["layer"] == "back"):
                        x = None
                        continue
                    break
            x = x if x is not None else W * r.uniform(0.1, 0.9)
        if pr.layer != "back":
            put(x, w)
        placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                           seed=seed + len(placed) * 17))
    for f in figs:
        f.pop("_pot", None)
    return dict(props=placed, people=figs, scale=s, ground_y=gy, shot=shot)


# ------------------------------------------------------------------ render
class Scene:
    """Renders frames of one scene. Build once, call frame(t) per frame."""

    def __init__(self, spec: dict, era: str, seed: int):
        bad = validate(spec, era)
        if bad:
            raise ValueError("; ".join(bad))
        self.spec, self.era, self.seed = spec, era, seed
        self.time = spec["time"]
        self.weather = spec.get("weather", "clear")
        self.setting = spec["setting"]
        self.lay = layout(spec, seed)
        self.still = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        cr = cairo.Context(self.still)
        self.facts = settings.draw_still(cr, self.setting, self.time, self.weather, seed)
        for layer in ("back", "mid", "front"):
            for p in self.lay["props"]:
                if p["layer"] != layer:
                    continue
                pr = PROPS[p["name"]]
                if p["name"] in STILL:
                    pr.draw(cr, p["x"], p["y"], p["s"], 0.0, p["seed"])
                elif pr.base is not None:
                    pr.base(cr, p["x"], p["y"], p["s"], 0.0, p["seed"])
        ink.paper(cr, W, H)
        self.still.flush()
        self._lightmaps = {}
        self.lights = []
        for p in self.lay["props"]:
            pr = PROPS[p["name"]]
            if pr.light:
                self.lights.append((p["x"], p["y"] - pr.height * p["s"], 1.0 * p["s"], p["seed"]))
        for f in self.lay["people"]:
            if f["item"] in LIGHT_ITEMS:
                self.lights.append((f["x"], f["y"] - 230 * f["s"], 0.7 * f["s"], f["seed"]))
        interior = SETTINGS[self.setting].interior
        base = settings.AMBIENT[self.time]
        if interior:
            base = (0.5, 0.46, 0.52) if self.time in ("night", "dusk") else (0.72, 0.68, 0.7)
        if self.weather == "rain":
            base = tuple(c * 0.85 for c in base)
        self.ambient_light = base
        self.lit = interior or self.time != "day" or self.weather == "rain"

    LIGHT_LEVELS = 12

    def _lightmap(self, level: int) -> cairo.ImageSurface:
        """The light over the whole frame at one of LIGHT_LEVELS flicker
        strengths, drawn once and reused: ambient everywhere, warm pools
        around every fire, torch and candle."""
        lm = self._lightmaps.get(level)
        if lm is not None:
            return lm
        lm = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        cr = cairo.Context(lm)
        cr.set_source_rgb(*self.ambient_light)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_ADD)
        fl = 0.94 + 0.12 * level / (self.LIGHT_LEVELS - 1)
        for (x, y, k, sd) in self.lights:
            rad = 560 * k * fl
            g = cairo.RadialGradient(x, y, 0, x, y, rad)
            g.add_color_stop_rgba(0, 0.95, 0.62, 0.32, 0.95 * fl)
            g.add_color_stop_rgba(0.35, 0.75, 0.45, 0.22, 0.55 * fl)
            g.add_color_stop_rgba(1, 0.5, 0.3, 0.15, 0.0)
            cr.set_source(g)
            cr.arc(x, y, rad, 0, 2 * math.pi)
            cr.fill()
        lm.flush()
        self._lightmaps[level] = lm
        return lm

    def _light(self, cr, t):
        if self.lights:
            u = (props._n(t, 7.5, self.seed * 0.13) + 1) / 2
            level = max(0, min(self.LIGHT_LEVELS - 1, int(u * self.LIGHT_LEVELS)))
        else:
            level = 0
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_source_surface(self._lightmap(level), 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

    def draw(self, cr, t: float):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_surface(self.still, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        settings.ambient(cr, self.setting, self.time, "clear" if self.weather in ("rain", "snow") else
                         self.weather, self.facts, t, self.seed)
        lay = self.lay
        for layer in ("back", "mid"):
            for p in lay["props"]:
                if p["layer"] == layer and p["name"] not in STILL:
                    PROPS[p["name"]].draw(cr, p["x"], p["y"], p["s"], t, p["seed"])
        for f in sorted(lay["people"], key=lambda f: f["y"]):
            people.draw(cr, who=f["who"], era=self.era, seed=f["seed"], pose=f["pose"],
                        action=f["action"], x=f["x"], ground_y=f["y"], scale=f["s"], t=t,
                        facing=f["facing"], mood=f["mood"], item=f["item"])
        for p in lay["props"]:
            if p["layer"] == "front" and p["name"] not in STILL:
                PROPS[p["name"]].draw(cr, p["x"], p["y"], p["s"], t, p["seed"])
        if self.weather == "rain":
            settings._rain(cr, t, self.seed)
        elif self.weather == "snow":
            settings._snow(cr, t, self.seed)
        if self.lit:
            self._light(cr, t)

    def frame(self, t: float, surf: cairo.ImageSurface | None = None) -> cairo.ImageSurface:
        surf = surf or cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        cr = cairo.Context(surf)
        self.draw(cr, t)
        surf.flush()
        return surf
