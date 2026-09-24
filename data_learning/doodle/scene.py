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
ERAS = ("stone_age", "medieval", "ancient", "victorian", "egypt", "early_modern")
SHOTS = ("close", "wide")
SLOTS = {"far_left": 0.1, "left": 0.24, "center_left": 0.37, "center": 0.5,
         "center_right": 0.63, "right": 0.76, "far_right": 0.9}
STILL = {"tent", "hut", "tree", "pine", "bush", "rock", "woodpile", "bedroll", "hide_rack",
         "table", "bench", "barrel", "stones", "basket", "bed", "cave_painting",
         "column", "temple", "villa", "amphora", "stall", "olive",
         "terrace", "chair", "bookshelf", "clock", "chimney_pot",
         "pyramid", "palm", "obelisk", "jar", "reed_boat", "mudbrick_house", "date_basket",
         "timber_house", "crates", "mooring_post"}
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
EARTH_FLOORS = ("cave_inside", "hut_inside")     # interiors where an open fire on the floor is the hearth
STRONG_ACTIONS = ("chop", "wave")
FIRE_ACTIONS = ("feed_fire", "warm_hands", "stir")     # done AT the fire, so drawn beside it


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
            if fog and p["name"] in ("cauldron", "brazier"):
                k = max(0, k - 1)     # measured: a cauldron 0.06 clear / 0.34 in fog; a brazier 0.18 / 0.47
            score += k
    for c in spec.get("cast") or []:
        if not isinstance(c, dict):
            continue
        if c.get("item") in LIGHT_ITEMS:
            score += _fire_strength("torch", time, shot, st.interior)
        if shot == "close" and time in ("day", "dawn") and not st.interior:
            # Measured 2026-09-24 against the showrunner's OWN duplicate-frame
            # detector (4 s clips, one figure, a tree): chop 0.137 dup / run 5,
            # wave 0.179 / 4, hoe 0.463 / 18 — and a WALKER 0.75-1.0 / 96: legs
            # swing on the spot, and at a child's size in a close shot the
            # detector calls every frame a duplicate. Run #16's medieval film
            # was blocked at 11:36 for exactly that (43 s frozen), on a scene
            # this table had called alive. eat 0.78 / 44, yawn 0.62 / 60 and
            # stir 0.93 / 49 sit at or over the gate's 45-frame ceiling, so
            # they count for nothing here either.
            if c.get("action") in STRONG_ACTIONS:
                score += 2
            elif c.get("action") == "hoe":
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
    if not bad and st is not None and st.interior and spec.get("setting") not in EARTH_FLOORS:
        # a fire on a cave or hut floor is the Stone Age's hearth; a built room has one
        for i, p in enumerate(pl):
            if p.get("name") == "campfire":
                bad.append(f"props[{i}] a campfire does not burn on an indoor floor (run #18's judge: 'an open "
                           f"campfire burns on an indoor floor, right beside a sleeper'): use a hearth, brazier, "
                           f"candle, oil lamp or stove")
    if not bad and not is_living(spec):
        bad.append("nothing in this scene moves enough to read as alive: add a campfire, brazier or "
                   "cauldron at dusk or night (close shot), a hearth, a candle or oil lamp indoors, "
                   "a river/lake/sea at dusk or night (the sea by day too), rain, or (in daylight, "
                   "close shot) someone chopping or waving")
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
SOLID_BACK = {"deer", "mammoth", "cow", "cart", "well", "hut", "cottage", "tent", "fish_rack", "hide_rack", "torch",
              "hearth", "temple", "villa", "column", "terrace", "gas_lamp", "carriage", "stove", "bookshelf",
              "clock", "obelisk", "mudbrick_house", "timber_house", "ship"}


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
                        pid=None, on=None, head=(f["x"] - 1.25 * R, f["x"] + 1.25 * R)))
    for i, p in enumerate(lay["props"]):
        pr = PROPS[p["name"]]
        if p["layer"] == "back" and p["name"] not in SOLID_BACK and pr.solid_width is None:
            continue
        # scenery with a trunk: only the trunk takes room (the fourth film's
        # judge: "a tree growing out of a man's head")
        w = (pr.solid_width if (p["layer"] == "back" and p["name"] not in SOLID_BACK) else pr.width) * p["s"]
        out.append(dict(label=p["name"], lo=p["x"] - w / 2, hi=p["x"] + w / 2, fig=None,
                        under=p.get("under"), pid=i, on=p.get("on")))
    for b in lay.get("blocked") or ():
        out.append(dict(label=b["label"], lo=b["lo"], hi=b["hi"], fig=None, under=None, pid=None, on=None,
                        ground=True))
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
            if A["under"] is not None and A["under"] == B["under"]:
                continue          # the bedroll and the wolf at the same sleeper's feet
            if (A.get("on") is not None and A["on"] == B.get("pid")) or \
               (B.get("on") is not None and B["on"] == A.get("pid")):
                continue          # a lamp on its table
            if A.get("ground") or B.get("ground"):
                # ground the setting owns keeps a person's HEAD off it (a face
                # against the dark opening is a mask); a prop, an arm or a pot
                # may stand there
                g, o = (A, B) if A.get("ground") else (B, A)
                if o["fig"] is None:
                    if PROPS[o["label"]].light or PROPS[o["label"]].width < SMALL_PROP or o["under"] is not None:
                        continue      # a fire, something small, or a bed under its sleeper, reads there
                    over = min(o["hi"], g["hi"]) - max(o["lo"], g["lo"])
                    if over > MARGIN:
                        bad.append(f"{o['label']} stands in front of {g['label']} by {over:.0f}px")
                    continue
                hlo, hhi = o["head"]
                over = min(hhi, g["hi"]) - max(hlo, g["lo"])
                if over > MARGIN:
                    bad.append(f"{o['label']}'s head is in front of {g['label']} by {over:.0f}px")
                continue
            over = min(A["hi"], B["hi"]) - max(A["lo"], B["lo"])
            if over > MARGIN:
                bad.append(f"{A['label']} overlaps {B['label']} by {over:.0f}px")
    return bad


SHRINK = (1.0, 0.92, 0.84, 0.76, 0.68, 0.6)
# where people stand when nobody said: around the focal thing first; spread
# to the edges when the middle is full of furniture; close in when the
# edges are
# the last two put everyone on ONE side of the fire (which sits in the
# middle half of the frame, so "one side" is still in the picture)
SLOT_SETS = ([0.29, 0.71, 0.15, 0.85], [0.18, 0.82, 0.5, 0.34], [0.24, 0.76, 0.42, 0.58], [0.12, 0.88, 0.5, 0.3],
             [0.7, 0.86, 0.55, 0.95], [0.3, 0.14, 0.45, 0.05])


def layout(spec: dict, seed: int) -> dict:
    """Place every prop and person. Deterministic in (spec, seed). A shot
    too crowded to fit at its natural size tries the other standing spots,
    then is drawn a little smaller, in steps, until nothing overlaps; the
    last try is kept regardless and `collisions` says what still touches."""
    lay = None
    # the standing spots are tried in a seed-chosen order, so two scenes at a
    # fire are not the same arrangement by default (the seventh film's judge:
    # one composition in 16 of 42 samples)
    rot = seed % len(SLOT_SETS)
    sets = SLOT_SETS[rot:] + SLOT_SETS[:rot]
    # whoever acts at the fire is put beside it — but closer to the fire is
    # never smaller: at each size the adjacent arrangement is tried first
    # and the plain slots second, so a cook keeps her natural size (the
    # test that held it) and a hand-warmer sits by the hearth wherever
    # both fit
    adj = ((True, False) if any(isinstance(c, dict) and c.get("action") in FIRE_ACTIONS
                                for c in spec.get("cast") or []) else (False,))
    for k in SHRINK:
        for shift in FOCAL_SHIFTS:
            for slots in sets:
                for fire_adjacent in adj:
                    lay = _layout(spec, seed, k, slots, shift, fire_adjacent)
                    if not lay["collisions"]:
                        return lay
    return lay


# the fire is placed first and by seed; when the people cannot fit around
# it (a cook with her pot between the fire and the cave opening), it moves
# a little before anyone is drawn smaller
FOCAL_SHIFTS = (0.0, -0.12, 0.12, -0.24, 0.24)
SMALL_PROP = 200
TREE_KEEP = 60                   # half-width of a tree-line trunk-and-canopy column, at scale 1
TREE_TALL = 440                  # a prop tree's height at scale 1 (tree 400, pine 420, both with a canopy)
TOP_ROOM = 40                    # a prop tree's crown stays this far inside the top edge                 # narrower than this (stones, a basket) reads fine in the mouth of the cave
SCENERY_K = 1.35                 # a tree's scale against the shot's: about twice a standing figure


def _layout(spec: dict, seed: int, shrink: float, slots_auto=None, focal_shift: float = 0.0,
            fire_adjacent: bool = True) -> dict:
    r = random.Random(seed)
    cast = [dict(c) for c in (spec.get("cast") or [])]
    pl = _prop_list(spec)
    shot = shot_of(spec)
    s = (2.05 if shot == "close" else 1.25) * shrink
    gy = H * settings.GROUND_Y
    placed = []
    taken = []                      # (lo, hi) in world x, everything that must not overlap
    blocked = []                    # ground the SETTING owns: no PERSON is drawn in front of it
    # the setting's trees: a back prop (a tent, a rack) or a tall one (a torch)
    # keeps off their trunks and canopies — "a tree trunk drawn through the
    # tent", "a torch flame at the top of the pine" (the eighth film's board)
    trees = [(x - TREE_KEEP * ts, x + TREE_KEEP * ts) for x, _kind, ts, _ty in
             settings.tree_line(spec.get("setting"), seed, shot)]
    if spec.get("setting") == "cave_mouth":
        # the fifth film's judge: dark hair and a beard against the black of
        # the opening left "a floating white mask". A fire or a curled wolf
        # in front of it still reads; a face does not
        _, mx, ow = settings.cave_opening(seed, shot)
        blocked.append(dict(label="the cave opening", lo=mx - ow, hi=mx + ow))

    def clash(lo, hi, head=None, keep_off=False, off_trees=False):
        """How much (lo, hi) overlaps what is taken. `head` is a person's
        head column: THAT is what must stay off ground the setting owns —
        an arm or a pot over the dark opening still reads, a face does not.
        `keep_off` is a prop that must not stand on that ground either: the
        seventh film's judge saw "a tipi drawn inside the cave mouth" and a
        wolf there as "an unclear grey blob" — only a light reads against it."""
        c = sum(max(0.0, min(hi, thi) - max(lo, tlo) - MARGIN) for tlo, thi in taken)
        if off_trees:
            c += sum(max(0.0, min(hi, thi) - max(lo, tlo) - MARGIN) for tlo, thi in trees)
        if head is not None:
            hlo, hhi = head
            c += sum(max(0.0, min(hhi, b["hi"]) - max(hlo, b["lo"]) - MARGIN) for b in blocked)
        elif keep_off:
            c += sum(max(0.0, min(hi, b["hi"]) - max(lo, b["lo"]) - MARGIN) for b in blocked)
        return c

    def free(lo, hi, head=None, keep_off=False, off_trees=False):
        return clash(lo, hi, head, keep_off, off_trees) <= 0

    def put(lo, hi):
        taken.append((lo, hi))

    has_pot = next((q["name"] for q in pl if q["name"] in ("pot", "cauldron")), None)

    def fig_span(c, x, facing, R):
        lo, hi = figure_extent(c.get("pose", "stand"), R, c.get("action", "idle"), c.get("item"))
        if c.get("action") == "stir" and has_pot:
            # the pot goes on her far side from the fire (below), and she
            # turns to it: it is part of her span, or she is placed at the
            # frame edge with her pot outside it
            hi = max(hi, (1.55 * R + (50 if has_pot == "pot" else 20) * s + PROPS[has_pot].width * s / 2) / R + PAD)
            facing = "right" if x >= focal_x else "left"
        if facing == "left":
            lo, hi = -hi, -lo
        return x + lo, x + hi

    def head_span(x, R):
        return x - 1.25 * R, x + 1.25 * R

    def settle(x, span_of, lo_lim, hi_lim, head_of=None, keep_off=False, off_trees=False):
        """Slide x away from the focal thing, then toward it, until its span
        is clear of everything placed; the least-crowded x if nothing is."""
        d = -1 if x < focal_x else 1
        best, best_c = x, None
        for sign in (d, -d):
            for k in range(0, 40):
                cand = x + sign * k * 30
                lo, hi = span_of(cand)
                if lo < lo_lim or hi > hi_lim:
                    # out of the frame on the side we are walking toward: this
                    # direction is spent. Out on the OTHER side (a mammoth
                    # whose first spot hangs off the left edge): keep walking
                    # in — giving up here left it cut by the frame at every size
                    if (sign > 0 and hi > hi_lim) or (sign < 0 and lo < lo_lim):
                        break
                    continue
                c = clash(lo, hi, head_of(cand) if head_of else None, keep_off, off_trees)
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
    # the fourth film's judge: "cave mouth on the left, a campfire in the
    # centre, one seated figure and a moon" repeated — so the focal thing
    # sits somewhere between 38% and 62% of the width, by seed
    # ... and the seventh's still saw one composition in 16 of 42 samples, so
    # the fire now ranges over the middle half of the frame
    focal_x = W * SLOTS[focal["at"]] if focal and focal.get("at") else W * (0.25 + 0.5 * r.random() + focal_shift)
    focal_x = min(max(focal_x, W * 0.12), W * 0.88)

    st = SETTINGS.get(spec.get("setting"))
    water = st.water if st is not None else None
    # the near edge of the water band (settings._water): back props stand
    # on the far shore, above it, a little smaller — not in the water
    far_shore = None
    if water in ("river", "lake"):
        far_shore = gy - settings.WATER_BAND[water][0] - 8
    elif water == "sea":
        far_shore = H * 0.58 - 8            # the sea runs to the horizon; things stand across the bay

    def prop_geom(p):
        pr = PROPS[p["name"]]
        # scenery with a trunk stands well over a person's head: at the old
        # 0.82 a close-shot man was "about as tall as the trees" (the sixth
        # film's judge). Solid back props (a hut, a mammoth) keep their size
        scenery_k = SCENERY_K if (pr.layer == "back" and pr.solid_width) else 0.82
        ps = s * (scenery_k if pr.layer == "back" else 1.0) * (0.95 if shot == "wide" else 1.0)
        if pr.living and shot == "wide":
            ps *= 1.35          # a fire is the heart of a wide shot, not a speck in it
        py = gy + {"back": -60 * s, "mid": 10 * s, "front": 70 * s}[pr.layer]
        if pr.layer == "back" and far_shore is not None:
            ps *= 0.8
            py = far_shore
        if pr.layer == "back" and pr.solid_width:
            # a prop tree stays inside the frame: at 2.77 its canopy was
            # "cut off by the top edge" in every close forest scene
            ps = min(ps, (py - TOP_ROOM) / TREE_TALL)
        return pr, ps, py, pr.width * ps

    if focal:
        pr, ps, py, w = prop_geom(focal)
        placed.append(dict(name=focal["name"], x=focal_x, y=py, s=ps, layer=pr.layer,
                           seed=seed + 1))
        on_table = focal["name"] in ("candle", "oil_lamp") and any(q["name"] == "table" for q in pl)
        if (pr.layer != "back" or focal["name"] in SOLID_BACK) and not on_table:
            put(focal_x - w / 2, focal_x + w / 2)   # a lamp that will stand on the table takes no floor

    rest = [p for p in pl if p is not focal]
    # big solid scenery (a mammoth, a hut, a cart) is placed BEFORE the
    # people, so they find room around it: placed after, a 1000px mammoth
    # had nowhere to go and was cut by the frame at every size
    early = [p for p in rest if PROPS[p['name']].layer == 'back' and p['name'] in SOLID_BACK
             and not PROPS[p['name']].living]
    late = [p for p in rest if p not in early]
    stirrer = sleeper = None
    def place_prop(p):
        """Place one non-focal prop; bedroll and pot go with their person."""
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
            return
        elif sleeper and p["name"] in ("wolf", "dog") and not sleeper.get("_dog"):
            # curled at the sleeper's feet, on the side away from the fire —
            # its own spot in the crowd never fit beside a sleeper and a fire
            # in the mouth of a cave, and a wolf pushed into the dark opening
            # was "an unclear grey blob" to the seventh film's judge
            R = people.R0 * s * people.WHO[sleeper["who"]]["size"]
            d = -1 if sleeper["x"] < focal_x else 1
            lo, hi = figure_extent("lie", R)
            edge = sleeper["x"] + d * (hi if d > 0 else -lo)
            x = edge + d * (w / 2 + 0.15 * R)      # beside the sleeper, touching, not under the bed
            x = min(max(x, EDGE + w / 2), W - EDGE - w / 2)
            sleeper["_dog"] = True
            put(x - w / 2, x + w / 2)
            placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                               seed=seed + len(placed) * 17, under=figs.index(sleeper)))
            return
        elif stirrer and p["name"] in ("pot", "cauldron") and not stirrer.get("_pot"):
            R = people.R0 * s * people.WHO[stirrer["who"]]["size"]
            # the pot goes on the cook's far side from the fire, and the cook
            # turns to it — a pot between a person and the flames hides both
            d = 1 if stirrer["x"] >= focal_x else -1
            stirrer["facing"] = "right" if d > 0 else "left"
            x = stirrer["x"] + d * (1.55 * R + (50 if p["name"] == "pot" else 20) * ps)
            stirrer["_pot"] = True
            # between the cook's knees on purpose: exempt from the crowding
            # check against HER — but it still takes room from everything else
            put(x - w / 2, x + w / 2)
            placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                               seed=seed + len(placed) * 17, under=figs.index(stirrer)))
            return
        else:
            scenery = pr.layer == "back" and p["name"] not in SOLID_BACK
            tw = pr.solid_width * ps if (scenery and pr.solid_width) else w   # what takes room
            keep_off = not pr.light and pr.width >= SMALL_PROP   # a light, or something small, may be in the cave mouth
            off_trees = pr.layer == "back" or bool(pr.height)     # stands at the tree line, or reaches its canopy
            cands = ([0.12, 0.88, 0.28, 0.72, 0.5, 0.06, 0.94] if pr.layer == "back"
                     else [0.4, 0.6, 0.5, 0.08, 0.92, 0.2, 0.8, 0.33, 0.67])
            x = None
            for cnd in cands:
                if not (EDGE <= W * cnd - w / 2 and W * cnd + w / 2 <= W - EDGE):
                    continue
                if (scenery and not pr.solid_width) or free(W * cnd - tw / 2, W * cnd + tw / 2, keep_off=keep_off,
                                                          off_trees=off_trees):
                    x = W * cnd
                    if pr.layer == "back" and not all(abs(W * cnd - q["x"]) > 250 for q in placed
                                                      if q["layer"] == "back"):
                        x = None
                        continue
                    break
            if x is None and (not scenery or pr.solid_width):
                x = settle(W * cands[0], lambda xx: (xx - tw / 2, xx + tw / 2), EDGE, W - EDGE, keep_off=keep_off,
                       off_trees=off_trees)
            if x is None:
                x = W * r.uniform(max(0.1, w / 2 / W), min(0.9, 1 - w / 2 / W))
        if pr.layer != "back" or p["name"] in SOLID_BACK:
            put(x - w / 2, x + w / 2)
        elif pr.solid_width:
            put(x - pr.solid_width * ps / 2, x + pr.solid_width * ps / 2)
        placed.append(dict(name=p["name"], x=x, y=py, s=ps, layer=pr.layer,
                           seed=seed + len(placed) * 17))
    for p in early:
        place_prop(p)
    # people next, around the focal thing and facing it — each one's REAL
    # width (a sleeper is five heads long) kept clear of the fire and of
    # each other. The judge's first note on the first film: "sleepers are
    # drawn lying in the fire".
    slots_auto = list(slots_auto or SLOT_SETS[0])
    # whoever is DOING something at the fire is placed first and tries the
    # slots nearest it: measured before this, a woman warming her hands
    # landed 6 to 15 heads from the hearth while an idle child stood a head
    # away, and the storyboard editor's commonest note on the medieval film
    # was "sits away from the hearth" / "no hands held out to the fire"
    at_fire = bool(fire_adjacent and focal and (PROPS[focal["name"]].light or PROPS[focal["name"]].living))
    order = sorted(range(len(cast)),
                   key=lambda i: 0 if (at_fire and cast[i].get("action") in FIRE_ACTIONS) else 1)
    figs: list = [None] * len(cast)
    for i in order:
        c = cast[i]
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
            if at_fire and c.get("action") in FIRE_ACTIONS:
                # right beside the fire, on whichever side has room: the
                # fire's own half-width plus this figure's, and a hand's gap
                fp = placed[0]
                half = PROPS[fp["name"]].width * fp["s"] / 2
                for side in ((1, -1) if (seed + i) % 2 else (-1, 1)):
                    facing = "right" if side < 0 else "left"
                    lo0, hi0 = fig_span(c, 0.0, facing, R)
                    cand = focal_x + side * (half + (hi0 if side > 0 else -lo0) + 0.35 * R)
                    got = settle(cand, lambda xx: fig_span(c, xx, facing, R), EDGE, W - EDGE,
                                 head_of=lambda xx: head_span(xx, R))
                    lo, hi = fig_span(c, got, facing, R)
                    if lo >= EDGE and hi <= W - EDGE and free(lo, hi, head_span(got, R)):
                        x = got
                        break
            for k in range(len(slots_auto)):
                if x is not None:
                    break
                cand = W * slots_auto[(i + k) % len(slots_auto)]
                facing = c.get("facing") or ("right" if cand < focal_x else "left")
                got = settle(cand, lambda xx: fig_span(c, xx, facing, R), EDGE, W - EDGE,
                             head_of=lambda xx: head_span(xx, R))
                lo, hi = fig_span(c, got, facing, R)
                if lo >= EDGE and hi <= W - EDGE and free(lo, hi, head_span(got, R)):
                    x = got
                    break
            if x is None:
                cand = W * slots_auto[i % len(slots_auto)]
                facing = c.get("facing") or ("right" if cand < focal_x else "left")
                x = settle(cand, lambda xx: fig_span(c, xx, facing, R), EDGE, W - EDGE,
                           head_of=lambda xx: head_span(xx, R))
        put(*fig_span(c, x, facing, R))
        figs[i] = dict(who=c["who"], pose=pose, action=c.get("action", "idle"),
                       mood=c.get("mood", "calm"), item=c.get("item"), x=x,
                       y=gy + 30 * s, s=s, facing=facing, seed=seed * 13 + i * 101)

    # a pot or cauldron belongs in front of whoever is stirring it; a bedroll
    # goes under whoever is lying down
    stirrer = next((f for f in figs if f["action"] == "stir"), None)
    sleeper = next((f for f in figs if f["pose"] == "lie"), None)
    for p in late:
        place_prop(p)
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
    lay = dict(props=placed, people=figs, scale=s, ground_y=gy, shot=shot, blocked=blocked)
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
        self.facts = settings.draw_still(cr, self.setting, self.time, self.weather, seed, shot_of(spec))
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
                        facing=f["facing"], mood=f["mood"], item=f["item"],
                        cold=self.weather in ("frost", "snow"))
        for p in lay["props"]:
            if p["layer"] == "front" and p["name"] not in STILL:
                PROPS[p["name"]].draw(cr, p["x"], p["y"], p["s"], t, p["seed"])
        if self.weather == "rain":
            settings._rain(cr, t, self.seed)
        elif self.weather == "snow":
            settings._snow(cr, t, self.seed)
        if self.lit:
            self._light(cr, t)
        # the glints are light, so they come after the light pass (drawn
        # before it, the night ambient dims them below the gate's notice and
        # a river at night measures frozen) — but they are the WATER's, so
        # they are clipped away from everybody standing in front of it
        # (run #18's judge: "water sparkle strokes are drawn across the
        # fisherman's body", "a white streak crosses the figure's head")
        if self.facts.get("water"):
            cr.save()
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.rectangle(0, 0, W, H)
            for lo, hi, top, bot in self._figure_holes():
                cr.rectangle(lo, top, hi - lo, bot - top)
            cr.clip()
            settings.glints(cr, self.facts, self.time, t, self.seed)
            cr.restore()

    def _figure_holes(self) -> list[tuple[float, float, float, float]]:
        """Each person's footprint as (lo, hi, top, bottom), the x-spans
        merged where they touch so the even-odd clip never re-admits an
        overlap."""
        spans_ = []
        for f in self.lay["people"]:
            R = people.R0 * f["s"] * people.WHO[f["who"]]["size"]
            lo, hi = figure_extent(f["pose"], R, f.get("action", "idle"), f.get("item"))
            if f["facing"] == "left":
                lo, hi = -hi, -lo
            spans_.append((f["x"] + lo - 0.1 * R, f["x"] + hi + 0.1 * R, f["y"] - 5.6 * R, f["y"] + 0.4 * R))
        spans_.sort()
        merged: list = []
        for lo, hi, top, bot in spans_:
            if merged and lo <= merged[-1][1]:
                m = merged[-1]
                merged[-1] = (m[0], max(m[1], hi), min(m[2], top), max(m[3], bot))
            else:
                merged.append((lo, hi, top, bot))
        return merged

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
        "cave or hut; or, in daylight close shots, someone chopping or waving. "
        "Helpers that count for half: a torch, a wide-shot campfire or cauldron at "
        "dusk/night. A daytime fire alone does NOT pass.",
    ])
