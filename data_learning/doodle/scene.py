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
ERAS = ("stone_age", "medieval", "ancient", "victorian")
SHOTS = ("close", "wide")
SLOTS = {"far_left": 0.1, "left": 0.24, "center_left": 0.37, "center": 0.5,
         "center_right": 0.63, "right": 0.76, "far_right": 0.9}
STILL = {"tent", "hut", "tree", "pine", "bush", "rock", "woodpile", "bedroll", "hide_rack",
         "table", "bench", "barrel", "stones", "basket", "bed", "cave_painting",
         "column", "temple", "villa", "amphora", "stall", "olive",
         "terrace", "chair", "bookshelf", "clock", "chimney_pot"}
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


def shot_of(spec: dict) -> str:
    return spec.get("shot") or ("close" if len(spec.get("cast") or []) <= 2 else "wide")


# How strongly each living thing moves, MEASURED with the showrunner's own
# cadence detector on the thing alone in a scene (tests/test_ori_sleep.py
# re-measures every claim). 2 = alone it keeps a scene moving (<= 35% held
# frames); 1 = it helps; 0 = it is calm enough to read as a still. A scene
# needs a total of 2. The numbers are why: a fire at night throws sparks
# against the dark and makes the walls flicker; the same fire at noon is a
# small orange shape on bright grass and barely registers.
STRONG_ACTIONS = ("chop", "wave")


def _fire_strength(name, time, shot, interior):
    """Measured 2026-09-23 with the real probe (4 s clips, the fire alone):
    campfire night close 0.04, dusk close 0.17, night wide 0.39, dusk wide
    0.44, inside a cave 0.00/0.16; hearth 0.06/0.24; cauldron close 0.08-0.10,
    wide 0.45; torch 0.29-0.54; candle 0.26. Daylight fires: not measured
    alive. 2 is <= 0.30 held frames alone; 1 is a helper."""
    dark = interior or time in ("night", "dusk")
    if name == "hearth":
        return 2
    if name == "campfire":
        if time == "dawn" and not interior:
            # measured 2026-09-23: dawn close 0.06-0.10 (alive), dawn wide 0.52-0.63
            return 2 if shot == "close" else 0
        if not dark:
            return 0
        return 2 if (shot == "close" or interior) else 1
    if name == "cauldron":
        if not dark:
            return 0
        return 2 if shot == "close" else 1
    if name == "torch":
        return 1
    if name in ("candle", "oil_lamp"):
        # measured 2026-09-23: 0.26-0.28 inside (the flicker plays on a wall),
        # 0.53 on open grass at night — a small flame needs a room around it
        return 2 if interior else 0
    if name == "gas_lamp":
        # measured 2026-09-23: 0.53 alone at night, but 0.19 with someone
        # walking under it, 0.17 with a held lantern, 0.33 in falling snow —
        # a street lamp lights a scene; something has to move in its light
        return 1
    if name == "stove":
        # measured 2026-09-23: 0.04 close, 0.23 wide (always indoors)
        return 2
    if name == "brazier":
        # measured 2026-09-23: night close 0.18, night wide 0.32, day close 0.37, day wide 0.59
        if shot == "close":
            return 2 if dark else 1
        return 1 if dark else 0
    return 0


def _water_strength(kind, time, fog) -> int:
    """Measured 2026-09-23 with the real probe (4 s clips, the water alone,
    the same in a close and a wide shot): river day 0.88, dusk 0.27, night
    0.17, dawn 0.67; lake day 0.80, dusk 0.33, night 0.24, dawn 0.66; sea
    day 0.43, dusk 0.08, night 0.04, dawn 0.26. Fog: a river holds 0.20 at
    night and 0.97 by day. Daylight water is a still picture with a few
    glints; the glints carry it only against a darker sky."""
    if fog and time != "night":
        return 0
    table = {
        "river": {"day": 0, "dusk": 2, "night": 2, "dawn": 0},
        "lake": {"day": 0, "dusk": 1, "night": 2, "dawn": 0},
        "sea": {"day": 1, "dusk": 2, "night": 2, "dawn": 2},
    }
    return table.get(kind, {}).get(time, 0)


def motion_strength(spec: dict) -> int:
    st = SETTINGS.get(spec.get("setting"))
    if st is None:
        return 0
    time, shot = spec.get("time"), shot_of(spec)
    fog = spec.get("weather") == "fog"
    score = 0
    if st.water:
        score += _water_strength(st.water, time, fog)
    if spec.get("weather") == "rain":
        score += 2
    if spec.get("weather") == "snow":
        score += 1                  # measured: 1.0 alone (too small for the probe), 0.33 with a lamp
    lit = any(PROPS.get(p.get("name")) is not None and PROPS[p["name"]].light for p in _prop_list(spec))
    for p in _prop_list(spec):
        pr = PROPS.get(p.get("name"))
        if pr is not None and pr.living:
            k = _fire_strength(p["name"], time, shot, st.interior)
            if fog and p["name"] == "cauldron":
                k = max(0, k - 1)     # measured: dusk close 0.06 clear, 0.34 in fog
            score += k
    for c in spec.get("cast") or []:
        if not isinstance(c, dict):
            continue
        if c.get("item") in LIGHT_ITEMS:
            score += _fire_strength("torch", time, shot, st.interior)
        if shot == "close" and time in ("day", "dawn") and not st.interior:
            if c.get("action") in STRONG_ACTIONS or c.get("pose") == "walk":
                score += 2
            elif c.get("action") in ("hoe", "yawn", "eat", "drink", "stir"):
                score += 1
        elif shot == "close" and c.get("pose") == "walk" and lit and not st.interior:
            # measured: a walker under a street lamp at night 0.19; the same
            # walker on an unlit street 1.0 (a black frame)
            score += 1
    return score


def is_living(spec: dict) -> bool:
    return motion_strength(spec) >= 2


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
        elif pr.settings is not None and spec.get("setting") not in pr.settings:
            # the third film's judge: "cave-painting animals float in the
            # open night sky" — a painting needs a wall
            bad.append(f"props[{i}] {p['name']!r} only belongs in {', '.join(pr.settings)}")
        if p.get("at") is not None and p.get("at") not in SLOTS:
            bad.append(f"props[{i}].at {p.get('at')!r} is not one of {sorted(SLOTS)}")
    if not bad and not is_living(spec):
        bad.append("nothing in this scene moves enough to read as alive: add a campfire, brazier or "
                   "cauldron at dusk or night (close shot), a hearth, a candle or oil lamp indoors, "
                   "a river/lake/sea at dusk or night (the sea by day too), rain, or (in daylight, "
                   "close shot) someone walking, chopping or waving")
    return bad


# ------------------------------------------------------------------ layout
MARGIN = 12.0        # px two things may share before they count as touching
EDGE = 30.0          # px of frame kept clear on each side of anything drawn
PAD = 0.35           # head radii of air kept around every figure

# how far a figure reaches, in head radii, left and right of its feet when
# facing +x — read off the rig (people.skeleton / people._draw_lying)
_EXTENT = {
    "stand": (-0.9, 1.1), "walk": (-1.0, 1.2), "sit": (-1.0, 2.0), "sit_on": (-1.1, 1.5),
    "crouch": (-1.1, 1.3), "lie": (-3.2, 3.2),
}
# how far in front of the feet, in head radii, an action or a held thing
# reaches — an ABSOLUTE extent, taken against the pose's own (a sitter's
# legs already reach two heads forward, so a stirring hand adds nothing;
# a fishing rod adds a lot). The third film's judge: "the torch-bearer's
# outstretched arm crosses the seated elder's head".
ACTION_REACH = {"point": 1.9, "carry": 1.8, "wave": 1.2, "play": 1.8, "feed_fire": 2.2, "stir": 1.9,
                "fish": 3.9, "hoe": 2.4, "chop": 1.8, "gather": 1.7, "talk": 1.3, "warm_hands": 1.6,
                "knap": 1.4, "sew": 1.6, "eat": 1.3, "drink": 1.3}
ITEM_REACH = {"spear": 2.1, "torch": 1.3, "stick": 1.2, "axe": 1.4, "hoe": 2.4, "rod": 3.9,
              "bundle": 1.8, "basket": 1.2, "lantern": 1.0}
# back-layer props with a body: a deer standing "behind" the fire in the
# same place reads as a deer in the fire, so they take room like anything
# else. Trees, tents and walls stay scenery.
SOLID_BACK = {"deer", "mammoth", "cow", "cart", "well", "hut", "cottage", "fish_rack", "hide_rack", "torch",
              "hearth", "temple", "villa", "column", "terrace", "gas_lamp", "carriage", "stove", "bookshelf",
              "clock"}


def figure_extent(pose: str, R: float, action: str = "idle", item: str | None = None) -> tuple[float, float]:
    lo, hi = _EXTENT[pose]
    if pose != "lie":
        held = item if item is not None else people.ACTIONS.get(action, {}).get("item")
        hi = max(hi, ACTION_REACH.get(action, 0.0), ITEM_REACH.get(held or "", 0.0))
    return (lo - PAD) * R, (hi + PAD) * R


def spans(lay: dict) -> list[dict]:
    """Every drawn thing that occupies the ground plane (people, mid and
    front props) as {label, lo, hi, fig, under}: `fig` is the figure's own
    index, `under` the index of the sleeper a bedroll was put beneath."""
    out = []
    for i, f in enumerate(lay["people"]):
        R = people.R0 * f["s"] * people.WHO[f["who"]]["size"]
        lo, hi = figure_extent(f["pose"], R, f.get("action", "idle"), f.get("item"))
        if f["facing"] == "left":
            lo, hi = -hi, -lo
        out.append(dict(label=f"{f['who']}:{f['pose']}", lo=f["x"] + lo, hi=f["x"] + hi, fig=i, under=None,
                        pid=None, on=None))
    for i, p in enumerate(lay["props"]):
        if p["layer"] == "back" and p["name"] not in SOLID_BACK:
            continue
        w = PROPS[p["name"]].width * p["s"]
        out.append(dict(label=p["name"], lo=p["x"] - w / 2, hi=p["x"] + w / 2, fig=None,
                        under=p.get("under"), pid=i, on=p.get("on")))
    return out


def collisions(lay: dict) -> list[str]:
    """Pairs of things drawn over each other: a sleeper in the fire, a pot on
    a lap, two people in one spot. A bedroll under its own sleeper is the
    one overlap that is meant. Empty means the picture is readable."""
    items = spans(lay)
    bad = []
    for it in items:
        if it["lo"] < EDGE or it["hi"] > W - EDGE:
            bad.append(f"{it['label']} is cut by the frame edge")
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            A, B = items[a], items[b]
            if (A["under"] is not None and A["under"] == B["fig"]) or \
               (B["under"] is not None and B["under"] == A["fig"]):
                continue
            if (A.get("on") is not None and A["on"] == B.get("pid")) or \
               (B.get("on") is not None and B["on"] == A.get("pid")):
                continue          # a lamp on its table
            over = min(A["hi"], B["hi"]) - max(A["lo"], B["lo"])
            if over > MARGIN:
                bad.append(f"{A['label']} overlaps {B['label']} by {over:.0f}px")
    return bad


SHRINK = (1.0, 0.92, 0.84, 0.76, 0.68)


def layout(spec: dict, seed: int) -> dict:
    """Place every prop and person. Deterministic in (spec, seed). A shot
    too crowded to fit at its natural size is drawn a little smaller, in
    steps, until nothing overlaps; the last step is kept regardless and
    `collisions` says what still touches."""
    lay = None
    for k in SHRINK:
        lay = _layout(spec, seed, k)
        if not lay["collisions"]:
            break
    return lay


def _layout(spec: dict, seed: int, shrink: float) -> dict:
    r = random.Random(seed)
    cast = [dict(c) for c in (spec.get("cast") or [])]
    pl = _prop_list(spec)
    shot = shot_of(spec)
    s = (2.05 if shot == "close" else 1.25) * shrink
    gy = H * settings.GROUND_Y
    placed = []
    taken = []                      # (lo, hi) in world x, everything that must not overlap

    def clash(lo, hi):
        return sum(max(0.0, min(hi, thi) - max(lo, tlo) - MARGIN) for tlo, thi in taken)

    def free(lo, hi):
        return clash(lo, hi) <= 0

    def put(lo, hi):
        taken.append((lo, hi))

    def fig_span(c, x, facing, R):
        lo, hi = figure_extent(c.get("pose", "stand"), R, c.get("action", "idle"), c.get("item"))
        if facing == "left":
            lo, hi = -hi, -lo
        return x + lo, x + hi

    def settle(x, span_of, lo_lim, hi_lim):
        """Slide x away from the focal thing, then toward it, until its span
        is clear of everything placed; the least-crowded x if nothing is."""
        d = -1 if x < focal_x else 1
        best, best_c = x, None
        for sign in (d, -d):
            for k in range(0, 40):
                cand = x + sign * k * 30
                lo, hi = span_of(cand)
                if lo < lo_lim or hi > hi_lim:
                    break
                c = clash(lo, hi)
                if c <= 0:
                    return cand
                if best_c is None or c < best_c:
                    best, best_c = cand, c
        return best

    # the focal thing: the first light/living prop, else the first prop
    focal = None
    for p in pl:
        if PROPS[p["name"]].light or PROPS[p["name"]].living:
            focal = p
            break
    if focal is None and pl:
        focal = pl[0]
    focal_x = W * SLOTS[focal["at"]] if focal and focal.get("at") else W * 0.5

    st = SETTINGS.get(spec.get("setting"))
    water = st.water if st is not None else None
    # the near edge of the water band (settings._water): back props stand
    # on the far shore, above it, a little smaller — not in the water
    far_shore = None
    if water == "river":
        far_shore = gy - 120 - 8
    elif water == "lake":
        far_shore = gy - 170 - 8
    elif water == "sea":
        far_shore = H * 0.58 - 8            # the sea runs to the horizon; things stand across the bay

    def prop_geom(p):
        pr = PROPS[p["name"]]
        ps = s * (0.82 if pr.layer == "back" else 1.0) * (0.95 if shot == "wide" else 1.0)
        if pr.living and shot == "wide":
            ps *= 1.35          # a fire is the heart of a wide shot, not a speck in it
        py = gy + {"back": -60 * s, "mid": 10 * s, "front": 70 * s}[pr.layer]
        if pr.layer == "back" and far_shore is not None:
            ps *= 0.8
            py = far_shore
        return pr, ps, py, pr.width * ps

    if focal:
        pr, ps, py, w = prop_geom(focal)
        placed.append(dict(name=focal["name"], x=focal_x, y=py, s=ps, layer=pr.layer,
                           seed=seed + 1))
        if pr.layer != "back" or focal["name"] in SOLID_BACK:
            put(focal_x - w / 2, focal_x + w / 2)

    # people next, around the focal thing and facing it — each one's REAL
    # width (a sleeper is five heads long) kept clear of the fire and of
    # each other. The judge's first note on the first film: "sleepers are
    # drawn lying in the fire".
    slots_auto = [0.29, 0.71, 0.15, 0.85] if focal else [0.35, 0.65, 0.2, 0.8]
    figs = []
    for i, c in enumerate(cast):
        R = people.R0 * s * people.WHO[c["who"]]["size"]
        pose = c.get("pose", "stand")
        if c.get("at"):
            x = W * SLOTS[c["at"]]
            facing = c.get("facing") or ("right" if x < focal_x else "left")
        else:
            # its own slot first, slid clear of the fire if it has to be —
            # jumping to the far slot instead put a cook at the frame edge
            # with her pot outside it
            x = None
            for k in range(len(slots_auto)):
                cand = W * slots_auto[(i + k) % len(slots_auto)]
                facing = c.get("facing") or ("right" if cand < focal_x else "left")
                got = settle(cand, lambda xx: fig_span(c, xx, facing, R), EDGE, W - EDGE)
                lo, hi = fig_span(c, got, facing, R)
                if lo >= EDGE and hi <= W - EDGE and free(lo, hi):
                    x = got
                    break
            if x is None:
                cand = W * slots_auto[i % len(slots_auto)]
                facing = c.get("facing") or ("right" if cand < focal_x else "left")
                x = settle(cand, lambda xx: fig_span(c, xx, facing, R), EDGE, W - EDGE)
        put(*fig_span(c, x, facing, R))
        figs.append(dict(who=c["who"], pose=pose, action=c.get("action", "idle"),
                         mood=c.get("mood", "calm"), item=c.get("item"), x=x,
                         y=gy + 30 * s, s=s, facing=facing, seed=seed * 13 + i * 101))

    # a pot or cauldron belongs in front of whoever is stirring it; a bedroll
    # goes under whoever is lying down
    stirrer = next((f for f in figs if f["action"] == "stir"), None)
    sleeper = next((f for f in figs if f["pose"] == "lie"), None)
    rest = [p for p in pl if p is not focal]
    for p in rest:
        pr, ps, py, w = prop_geom(p)
        if p.get("at"):
            x = W * SLOTS[p["at"]]
        elif sleeper and p["name"] in ("bedroll", "bed") and not sleeper.get("_bed"):
            # under the sleeper, centred on the body (head to feet), and
            # exempt from the crowding check — it is meant to be under them
            size = people.WHO[sleeper["who"]]["size"]
            R = people.R0 * s * size
            d = 1 if sleeper["facing"] == "right" else -1
            lo, hi = figure_extent("lie", R)
            x = sleeper["x"] + d * (lo + hi) / 2
            py = sleeper["y"] - 4 * s
            ps = s * size             # a child's bed is a child's size
            sleeper["_bed"] = True
            put(x - pr.width * ps / 2, x + pr.width * ps / 2)
            placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                               seed=seed + len(placed) * 17, under=figs.index(sleeper)))
            continue
        elif stirrer and p["name"] in ("pot", "cauldron") and not stirrer.get("_pot"):
            R = people.R0 * s * people.WHO[stirrer["who"]]["size"]
            # the pot goes on the cook's far side from the fire, and the cook
            # turns to it — a pot between a person and the flames hides both
            d = 1 if stirrer["x"] >= focal_x else -1
            stirrer["facing"] = "right" if d > 0 else "left"
            x = stirrer["x"] + d * (1.55 * R + (50 if p["name"] == "pot" else 20) * ps)
            stirrer["_pot"] = True
            # between the cook's knees on purpose: exempt from the crowding check
            placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                               seed=seed + len(placed) * 17, under=figs.index(stirrer)))
            continue
        else:
            scenery = pr.layer == "back" and p["name"] not in SOLID_BACK
            cands = ([0.12, 0.88, 0.28, 0.72, 0.5, 0.06, 0.94] if pr.layer == "back"
                     else [0.4, 0.6, 0.08, 0.92, 0.2, 0.8, 0.33, 0.67])
            x = None
            for cnd in cands:
                if not (EDGE <= W * cnd - w / 2 and W * cnd + w / 2 <= W - EDGE):
                    continue
                if scenery or free(W * cnd - w / 2, W * cnd + w / 2):
                    x = W * cnd
                    if pr.layer == "back" and not all(abs(W * cnd - q["x"]) > 250 for q in placed
                                                      if q["layer"] == "back"):
                        x = None
                        continue
                    break
            if x is None and not scenery:
                x = settle(W * cands[0], lambda xx: (xx - w / 2, xx + w / 2), EDGE, W - EDGE)
            if x is None:
                x = W * r.uniform(max(0.1, w / 2 / W), min(0.9, 1 - w / 2 / W))
        if pr.layer != "back" or p["name"] in SOLID_BACK:
            put(x - w / 2, x + w / 2)
        placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                           seed=seed + len(placed) * 17))
    # a small light stands ON a table when there is one (a lamp on the
    # floor under the table was where the crowding check put it)
    tables = [i for i, q in enumerate(placed) if q["name"] == "table"]
    if tables:
        ti = tables[0]
        tb = placed[ti]
        for q in placed:
            if q["name"] in ("candle", "oil_lamp") and "on" not in q and not q.get("at"):
                q["x"] = tb["x"] + 120 * tb["s"]
                q["y"] = tb["y"] - props.TABLE_TOP * tb["s"]
                q["on"] = ti
                break
    for f in figs:
        f.pop("_pot", None)
        f.pop("_bed", None)
    lay = dict(props=placed, people=figs, scale=s, ground_y=gy, shot=shot)
    lay["collisions"] = collisions(lay)
    return lay


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

    LIGHT_LEVELS = 24

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
        fl = 0.68 + 0.64 * level / (self.LIGHT_LEVELS - 1)
        for (x, y, k, sd) in self.lights:
            rad = 560 * k * fl
            g = cairo.RadialGradient(x, y, 0, x, y, rad)
            g.add_color_stop_rgba(0, 0.48 * fl, 0.34 * fl, 0.19 * fl, 1.0)
            g.add_color_stop_rgba(0.45, 0.4 * fl, 0.27 * fl, 0.14 * fl, 1.0)
            g.add_color_stop_rgba(1, 0.0, 0.0, 0.0, 1.0)
            cr.set_source(g)
            cr.arc(x, y, rad, 0, 2 * math.pi)
            cr.fill()
        lm.flush()
        self._lightmaps[level] = lm
        return lm

    def _light(self, cr, t):
        if self.lights:
            u = (ink.vnoise(t, 8.0, self.seed + 3) + 1) / 2
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
        settings.glints(cr, self.facts, self.time, t, self.seed)

    def frame(self, t: float, surf: cairo.ImageSurface | None = None) -> cairo.ImageSurface:
        surf = surf or cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        cr = cairo.Context(surf)
        self.draw(cr, t)
        surf.flush()
        return surf


# ------------------------------------------------------------------ for authors
def vocabulary(era: str) -> str:
    """Every name a scene may use in `era`, generated from the kit itself so
    an author's brief can never promise a picture the kit cannot draw."""
    sets = [k for k, v in SETTINGS.items() if era in v.eras]
    prs = [k for k, v in PROPS.items() if era in v.eras]
    living = [k for k in prs if PROPS[k].living]
    acts = "; ".join(f"{a} ({'/'.join(v['poses'])})" for a, v in people.ACTIONS.items())
    return "\n".join([
        f"setting: one of {', '.join(sets)} (interiors: "
        f"{', '.join(k for k in sets if SETTINGS[k].interior)} — weather must be clear)",
        f"time: one of {', '.join(TIMES)}",
        f"weather: one of {', '.join(WEATHER)}",
        f"shot: close (1-2 people, big) or wide (3-4 people or a landscape)",
        f"cast: 0-{MAX_CAST} people, each {{who, pose, action, mood, item?, at?}}",
        f"  who: {', '.join(people.WHO)}",
        f"  pose: {', '.join(people.POSES)}",
        f"  action (poses it works in): {acts}",
        f"  mood: {', '.join(people.MOODS)}",
        f"  item (optional, held): {', '.join(i for i in people.ITEMS if i != 'none')}",
        f"  at (optional): {', '.join(SLOTS)}",
        f"props: 0-{MAX_PROPS} of {', '.join(prs)} (living: {', '.join(living)})",
        "EVERY scene must move enough to read as alive. It passes if it has ANY of: "
        "a river/lake/seashore setting; rain; a hearth or a candle (interiors); a "
        "campfire or cauldron at dusk or night in a CLOSE shot, or a campfire inside a "
        "cave or hut; or, in daylight close shots, someone walking, chopping or waving. "
        "Helpers that count for half: a torch, a wide-shot campfire or cauldron at "
        "dusk/night. A daytime fire alone does NOT pass.",
    ])
