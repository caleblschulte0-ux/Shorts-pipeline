"""Happenings: things that HAPPEN in a shot, not arms going round.

The operator, 2026-10-03, on the Greek film cut into sentence-long shots:
"sure, you're doing more cuts, but at the end of the day, it's still just
stick figures moving their arms. More needs to be happening per scene.
Significantly more."

A shot carries `happen`: a short list of events, and `happen_s`, how long
it lasts. Each event is worked out against the picture's own layout, so
nobody walks to a spot somebody else is sitting in, and an event that does
not fit the picture is never planned (`possible`). The events:

    arrive   somebody walks in from the edge and sits down — at the fire to
             warm their hands, otherwise beside the others
    leave    somebody already there gets up and walks out
    feed     somebody comes in with wood, crouches at the fire and pushes it
             in, and the fire FLARES and throws sparks
    serve    somebody comes in with bread or a cup and hands it to whoever is
             sitting; they take it and eat or drink
    light    somebody walks to the unlit lamp with a burning spill and lights
             it, and the room brightens as it catches
    snuff    somebody leans to the lamp and blows it out, and the room dims
    child    a child runs in to an adult and sits close; the adult's arm goes
             round them
    passer   out of doors, somebody goes by on the far side, a lantern in
             hand after dark
    turn     a sleeper stirs: the blanket lifts and they turn over
    dog      a dog trots in and lies down by the fire (or crosses)
    cat      a cat walks along the floor and sits
    hens     hens peck their way across the yard
    birds    a flock crosses the sky
    fish     a fish jumps, and the water rings where it fell
    bats     bats flit across the dusk
    mouse    a mouse scurries along the floor in front, stops, and runs on
    moth     a moth circles a flame

Every one moves something across the picture or changes its light, which is
what an arm going round never does. Nothing here moves the camera.
"""
from __future__ import annotations

import math
import random

from . import ink, people
from .ink import rgb, shade
from .props import PROPS, flame, embers

W, H = 1920, 1080
EDGE = 30.0
GAP = 12.0

PEOPLE_KINDS = ("arrive", "leave", "feed", "serve", "light", "snuff", "child", "passer", "turn", "stretch")
BACK_K = 0.56            # the far side of the picture: scene.WALK_LANE
ANIMAL_KINDS = ("dog", "cat", "hens", "birds", "fish", "bats", "mouse", "moth")
KINDS = PEOPLE_KINDS + ANIMAL_KINDS

FIRES = ("campfire", "hearth", "brazier", "cauldron")
LAMPS = ("candle", "oil_lamp")
# where the flame sits on each light, against its feet, at scale 1: (dx, dy, size)
FLAME_AT = {"campfire": (0, -10, 78), "hearth": (0, -12, 62), "brazier": (0, -96, 62), "cauldron": (0, -5, 44),
            "candle": (0, -73, 26), "oil_lamp": (27.6, -55, 18), "torch": (6, -196, 46)}
WALK_V = 2.48 / 1.1          # head radii a second at a stroll (people.skeleton's no-slip stride)
RUN_V = 2.0 * WALK_V
RISE_S = 0.9                 # standing up or sitting down
# what a person does once they are in their place, by what is beside them
SETTLE = {"fire": "warm_hands", "none": "talk"}


def _ease(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _R(who: str, s: float) -> float:
    return people.R0 * s * people.WHO[who]["size"]


# ------------------------------------------------------------------ space
def _taken(lay: dict, skip: int | None = None) -> list[tuple[float, float]]:
    from .scene import spans
    out = []
    for it in spans(lay):
        if it.get("fig") is not None and it["fig"] == skip:
            continue
        out.append((it["lo"], it["hi"]))
    return out


def _blocking(lay: dict, lights: bool = False) -> list[tuple[float, float]]:
    """What nobody walks through in front of: people and anything big. With
    `lights`, any light on the floor too — an animal goes round a lamp (the
    83 film's judge: "the dog's tail tip is drawn as a flame" — it was the
    lamp the dog had trotted across); a person steps past it."""
    from .scene import spans, SMALL_PROP
    out = []
    for it in spans(lay):
        if it.get("fig") is not None:
            out.append((it["lo"], it["hi"]))
        elif it.get("pid") is not None:
            p = lay["props"][it["pid"]]
            if PROPS[p["name"]].width * p["s"] >= SMALL_PROP * 1.2 or (lights and PROPS[p["name"]].light):
                out.append((it["lo"], it["hi"]))
    return out


def _free(lo, hi, taken, x0, x1) -> bool:
    if lo < x0 + EDGE or hi > x1 - EDGE:
        return False
    return all(min(hi, b) - max(lo, a) <= GAP for a, b in taken)


def _spot(lay, extent, near_x, taken, x0, x1, r):
    """The free x nearest `near_x` where a figure of this extent fits, facing
    toward `near_x` (None when nowhere fits)."""
    best = None
    for step in range(0, 60):
        for sgn in (1, -1):
            x = near_x + sgn * step * 18.0
            facing = "left" if x > near_x else "right"
            lo, hi = extent(facing)
            if _free(x + lo, x + hi, taken, x0, x1):
                d = abs(x - near_x)
                if best is None or d < best[0]:
                    best = (d, x, facing)
        if best is not None and step * 18.0 > best[0] + 40:
            break
    return None if best is None else (best[1], best[2])


def _extent_fn(pose, R, action="idle", item=None):
    from .scene import figure_extent

    def f(facing):
        lo, hi = figure_extent(pose, R, action, item)
        return (-hi, -lo) if facing == "left" else (lo, hi)
    return f


def window(spec: dict) -> tuple[float, float]:
    """The part of the world the shot shows, in world x."""
    fr = spec.get("frame")
    if fr and not spec.get("pan"):
        cx, _cy, k = fr
        ox = min(max(cx * k - W / 2, 0.0), (k - 1) * W)
        return ox / k, ox / k + W / k
    return 0.0, float(W)


# ------------------------------------------------------------------ planning
def _fires(lay):
    return [p for p in lay["props"] if p["name"] in FIRES]


def _lamps(lay):
    return [p for p in lay["props"] if p["name"] in LAMPS]


def _sitters(lay):
    return [i for i, f in enumerate(lay["people"]) if f["pose"] in ("sit", "sit_on", "crouch", "recline")]


def build(kind: str, spec: dict, lay: dict, seed: int, dur: float, setting=None, used=None):
    """One happening worked out against this layout: a dict the Scene draws,
    or None when it does not fit the picture."""
    r = random.Random(seed * 7919 + KINDS.index(kind))
    x0, x1 = window(spec)
    s, gy = lay["scale"], lay["ground_y"] + 30 * lay["scale"]
    taken = _taken(lay) + list(used or [])
    who_pool = ["woman", "man", "old_woman", "elder"]
    era_ok = True
    if kind in ("arrive", "feed", "serve", "child"):
        who = "child" if kind == "child" else r.choice(who_pool)
        R = _R(who, s)
        fires = [p for p in _fires(lay) if x0 < p["x"] < x1]
        if kind == "feed":
            if not fires:
                return None
            target_x, action, end_pose, item = fires[0]["x"], "feed_fire", "crouch", "branch"
        elif kind == "serve":
            sit = [i for i in _sitters(lay) if x0 < lay["people"][i]["x"] < x1]
            if not sit:
                return None
            gi = sit[r.randrange(len(sit))]
            target_x, action, end_pose, item = lay["people"][gi]["x"], "hold", "stand", r.choice(("bread", "cup"))
        elif kind == "child":
            if any(f["who"] in ("child", "girl") for f in lay["people"]):
                return None               # the 79 film: a second child sat up awake beside the sleeping one
            adults = [i for i, f in enumerate(lay["people"]) if f["who"] != "child" and
                      f["pose"] in ("sit", "sit_on", "stand", "crouch", "recline") and x0 < f["x"] < x1]
            if not adults:
                return None
            gi = adults[r.randrange(len(adults))]
            target_x, action, end_pose, item = lay["people"][gi]["x"], "idle", "sit", None
        else:
            target_x = fires[0]["x"] if fires else (x0 + x1) / 2
            action, end_pose, item = ("warm_hands" if fires else "talk"), "sit", None
        ext = _extent_fn(end_pose if kind != "serve" else "stand", R, action, item)
        got = _spot(lay, ext, target_x, taken, x0, x1, r)
        if got is None and kind == "feed":
            return _feed_in_place(spec, lay, fires[0], dur, x0, x1)
        if got is None:
            return None
        x, facing = got
        if kind == "serve" and abs(x - target_x) > 4.2 * R:
            return None                   # too far to hand anything across
        if kind == "child" and abs(x - target_x) > 4.5 * R:
            return None
        # in from the nearer side of the shot — already WHOLE inside the
        # frame's edge at the cut (the dissolve hides the appearance), never
        # half across it: the 79 film's judge, three times, "clipped at the
        # right edge" on a figure caught walking in — and by a path that
        # crosses nobody ("a second figure merges into her")
        side = _clear_side(lay, x, x0, x1, R)
        if side is None:
            return None
        start = (x0 + 1.4 * R) if side < 0 else (x1 - 1.4 * R)
        v = (RUN_V if kind == "child" else WALK_V) * R
        walk_t = abs(x - start) / v
        # arrive about a third of the way in, starting in view if the walk is long
        t_arr = min(max(1.4, dur * 0.38), dur - 2.2)
        t0 = t_arr - walk_t
        if t0 < 0:
            start = x - (x - start) * (t_arr / walk_t)
            t0 = 0.0
        if not _head_fits(spec, gy + 4 * s, R):
            return None                   # a framed close-up: the standing newcomer's head would be cut
        a = dict(kind=kind, who=who, s=s, y=gy + 4 * s, seed=seed * 31 + 17, R=R,
                 item=("branch" if kind == "feed" else item),
                 keys=[(t0, start, "walk", "carry" if kind == "feed" else ("hold" if item else "idle"),
                        "right" if x > start else "left"),
                       (t_arr, x, "stand", "idle", facing)],
                 claim=ext(facing), x=x)
        a["claim"] = (x + a["claim"][0], x + a["claim"][1])
        if kind == "child":
            a["keys"][0] = (t0, start, "walk", "idle", "right" if x > start else "left")
            a["run"] = True
        # each key's action is what they do from that moment on
        first = {"feed": "feed_fire", "serve": "hold", "child": "idle"}.get(kind, action)
        if end_pose != "stand":
            a["keys"].append((t_arr + RISE_S, x, end_pose, first, facing))
        else:
            a["keys"][-1] = (t_arr, x, "stand", first, facing)
        after = t_arr + RISE_S + 0.2
        if kind == "feed":
            f = fires[0]
            a["keys"].append((after + 1.6, x, end_pose, "warm_hands", facing))
            a["flare"] = dict(x=f["x"], y=f["y"], s=f["s"], name=f["name"], t=after + 0.7)
            a["keys"].append((dur + 5, x, end_pose, "warm_hands", facing))
            a["item_until"] = after + 1.5
        elif kind == "serve":
            g = lay["people"][gi]
            gR = _R(g["who"], g["s"])
            mid_x = (x + g["x"]) / 2
            mid_y = g["y"] - (2.6 if g["pose"] in ("sit_on",) else 1.9) * gR
            a["give"] = dict(to=gi, x=mid_x, y=mid_y, t0=t_arr + 0.3, tm=t_arr + 1.3, t1=t_arr + 2.2,
                             after=("eat" if item == "bread" else "drink"))
            a["keys"].append((t_arr + 2.4, x, "stand", "talk", facing))
            a["keys"].append((dur + 5, x, "stand", "talk", facing))
        elif kind == "child":
            a["hug"] = dict(by=gi, t=after)
            a["keys"].append((dur + 5, x, "sit", "idle", facing))
        else:
            a["keys"].append((dur + 5, x, end_pose, action, facing))
        return a
    if kind == "leave":
        figs = [i for i, f in enumerate(lay["people"]) if f["pose"] in ("sit", "sit_on", "crouch", "stand", "recline")
                and x0 < f["x"] < x1 and f["who"] != "child"]
        if len(lay["people"]) < 2 or not figs:
            return None                    # the only person in the picture does not walk out of it
        r.shuffle(figs)
        for gi in figs:
            f = lay["people"][gi]
            if not _alive_without(spec, person=f):
                continue             # whoever walks out must not take the picture's life with them
            R = _R(f["who"], f["s"])
            side = _clear_side(lay, f["x"], x0, x1, R, skip=gi)
            if side is None:
                continue
            out = (x0 + 1.4 * R) if side < 0 else (x1 - 1.4 * R)
            if abs(out - f["x"]) < 3.0 * R:
                continue                   # already at the edge: nothing to see them do
            break
        else:
            return None
        t_up = max(0.6, dur * 0.22)
        facing = "left" if side < 0 else "right"
        walk_t = abs(out - f["x"]) / (WALK_V * R)
        a = dict(kind=kind, who=f["who"], s=f["s"], y=f["y"] + 4 * f["s"], seed=f["seed"], R=R, owns=gi,
                 item=f.get("item"), mood=f.get("mood", "calm"),
                 keys=[(0.0, f["x"], f["pose"], f["action"], f["facing"]),
                       (t_up, f["x"], f["pose"], "idle", f["facing"])])
        if f["pose"] != "stand":
            a["keys"].append((t_up + RISE_S, f["x"], "stand", "idle", facing))
            t_up += RISE_S
        a["keys"].append((t_up + 0.3, f["x"], "stand", "idle", facing))
        a["keys"].append((t_up + 0.3 + walk_t, out, "walk", "idle", facing))
        return a
    if kind == "turn":
        sleepers = [i for i, f in enumerate(lay["people"]) if f["pose"] == "lie" and x0 < f["x"] < x1]
        if not sleepers:
            return None
        gi = sleepers[r.randrange(len(sleepers))]
        f = lay["people"][gi]
        R = _R(f["who"], f["s"])
        t_turn = max(1.0, min(dur * 0.45, dur - 1.5))
        other = "left" if f["facing"] == "right" else "right"
        return dict(kind=kind, who=f["who"], s=f["s"], y=f["y"] + 4 * f["s"], seed=f["seed"], R=R, owns=gi,
                    item=None, mood=f.get("mood", "calm"),
                    keys=[(0.0, f["x"], "lie", f["action"], f["facing"]),
                          (t_turn, f["x"], "lie", f["action"], other),
                          (dur + 5, f["x"], "lie", f["action"], other)],
                    turn=dict(t0=t_turn - 0.7, tm=t_turn, t1=t_turn + 0.8))
    if kind == "stretch":
        # somebody already here gets up, stands a moment, and sits back down:
        # what happens in a room too full for anyone new to walk into (the
        # lone woman by her lamp had nothing but a mouse to offer)
        sitters = [i for i, f in enumerate(lay["people"]) if f["pose"] in ("sit", "sit_on", "crouch")
                   and x0 < f["x"] < x1]
        if not sitters:
            return None
        gi = sitters[r.randrange(len(sitters))]
        f = lay["people"][gi]
        R = _R(f["who"], f["s"])
        if not _head_fits(spec, f["y"], R):
            return None                 # standing, the head would be above the window
        t_up = max(1.0, min(dur * 0.3, dur - 3.0))
        return dict(kind=kind, who=f["who"], s=f["s"], y=f["y"], seed=f["seed"], R=R, owns=gi,
                    item=f.get("item"), mood=f.get("mood", "calm"),
                    keys=[(0.0, f["x"], f["pose"], f["action"], f["facing"]),
                          (t_up, f["x"], f["pose"], f["action"], f["facing"]),
                          (t_up + RISE_S, f["x"], "stand", "idle", f["facing"]),
                          (t_up + RISE_S + 1.3, f["x"], "stand", "idle", f["facing"]),
                          (t_up + 2 * RISE_S + 1.3, f["x"], f["pose"], f["action"], f["facing"]),
                          (dur + 5, f["x"], f["pose"], f["action"], f["facing"])])
    if kind in ("light", "snuff"):
        lamps = [p for p in _lamps(lay) if x0 < p["x"] < x1]
        if kind == "snuff":
            # the Greek film with happenings, blocked at 3:50: a candle blown
            # out in a wide room where it was the only thing alive, and 61
            # identical frames after it. A lamp goes out only where something
            # else in the picture still moves
            lamps = [p for p in lamps if _alive_without(spec, prop=p["name"])]
        for lp in lamps:
            a = _at_the_lamp(kind, lp, spec, lay, seed, dur, x0, x1, s, gy, taken, r, who_pool)
            if a is not None:
                return a
        return None
    # ---- animals
    if kind == "dog":
        R = 60 * s / 2.05 * 1.0
        fires = [p for p in _fires(lay) if x0 < p["x"] < x1]
        dsz = 0.62 * s
        span = 240 * dsz
        target = fires[0]["x"] if fires else r.uniform(x0 + 300, x1 - 300)
        got = _spot(lay, lambda fc: (-span / 2, span / 2), target, taken, x0, x1, r)
        side = r.choice((-1, 1))
        # whole, just inside the frame (the 83 film's judge: "the dog is cut
        # off by the right frame edge"); the dissolve hides the appearance
        start = (x0 + EDGE + span / 2) if side < 0 else (x1 - EDGE - span / 2)
        if got is not None:
            # it may lie down only where it can get to without walking over
            # anybody (the first sample: a dog trotting across a man in bed)
            lo_, hi_ = sorted((start, got[0]))
            if any(min(hi_, b) - max(lo_, a) > 0 for a, b in _blocking(lay, lights=True)):
                side = -side
                start = (x0 + EDGE + span / 2) if side < 0 else (x1 - EDGE - span / 2)
                lo_, hi_ = sorted((start, got[0]))
                if any(min(hi_, b) - max(lo_, a) > 0 for a, b in _blocking(lay, lights=True)):
                    got = None
        if got is None:
            if not _far_lane(spec):
                return None
            # it just goes by, on the far side of everybody
            end = (x1 + span) if side < 0 else (x0 - span)
            return dict(kind=kind, s=dsz * BACK_K, y=lay["ground_y"] - 66 * s, x0=start, x1=end, t0=0.0,
                        t1=dur * 1.3, lie=None, seed=seed, behind=True)
        end = got[0]
        t_arr = min(max(1.5, dur * 0.45), dur - 1.0)
        return dict(kind=kind, s=dsz, y=gy + 46 * s, x0=start, x1=end, t0=0.0, t1=t_arr,
                    lie=end, seed=seed, claim=(end - span / 2, end + span / 2))
    if kind == "cat":
        dsz = 0.75 * s
        span = 200 * dsz
        block = _blocking(lay, lights=True)
        got = _spot(lay, lambda fc: (-span / 2, span / 2), r.uniform(x0 + 0.3 * (x1 - x0), x0 + 0.7 * (x1 - x0)),
                    taken, x0, x1, r)
        start = end = None
        for side in r.sample((-1, 1), 2):
            st_ = (x0 + EDGE + span / 2) if side < 0 else (x1 - EDGE - span / 2)
            if got is None:
                break
            lo_, hi_ = sorted((st_, got[0]))
            if not any(min(hi_, b) - max(lo_, a) > 0 for a, b in block):
                start, end = st_, got[0]
                break
        if start is None:
            side = r.choice((-1, 1))
            start = (x0 + EDGE + span / 2) if side < 0 else (x1 - EDGE - span / 2)
            end = None
        if end is None:
            # nowhere to sit it can reach without walking over somebody: it
            # goes by on the far side, where there is a far side
            if not _far_lane(spec):
                return None
            end = (x1 + 200) if side < 0 else (x0 - 200)
            return dict(kind=kind, s=dsz * BACK_K, y=lay["ground_y"] - 66 * s, x0=start, x1=end, t0=0.0,
                        t1=dur * 1.2, seed=seed, behind=True)
        return dict(kind=kind, s=dsz, y=gy + 44 * s, x0=start, x1=end, t0=0.0, t1=min(dur * 0.6, dur - 1),
                    seed=seed)
    if kind == "passer":
        # somebody going home along the far side, a light in hand after dark
        who = r.choice(("man", "woman", "elder"))
        sw = s * BACK_K
        R = _R(who, sw)
        side = r.choice((-1, 1))
        # whole at both ends (run 92: "a figure is cut off at the right frame
        # edge" was a passer walking out through it): in just inside one
        # edge, across the back, and stopped whole just inside the other
        start = (x0 + EDGE + 1.4 * R) if side > 0 else (x1 - EDGE - 1.4 * R)
        far = (x1 - EDGE - 1.4 * R) if side > 0 else (x0 + EDGE + 1.4 * R)
        travel = min(abs(far - start), WALK_V * R * dur * 1.05)
        end = start + side * travel
        t_end = max(0.5, travel / max(1e-6, WALK_V * R))
        dark = spec.get("time") in ("dusk", "night")
        facing = "right" if side > 0 else "left"
        return dict(kind=kind, who=who, s=sw, y=lay["ground_y"] - 66 * s, seed=seed * 31 + 41, R=R,
                    item=("lantern" if dark else r.choice(("basket", "bundle", "none"))),
                    keys=[(0.0, start, "walk", "carry" if not dark else "idle", facing),
                          (t_end, end, "walk", "idle", facing),
                          (t_end + 0.01, end, "stand", "idle", facing)], behind=True)
    if kind == "hens":
        dsz = 0.85 * s
        side = r.choice((-1, 1))
        n = 3
        return dict(kind=kind, s=dsz, y=gy + 10 * s, side=side, n=n, x0=x0, x1=x1, dur=dur, seed=seed)
    if kind in ("birds", "bats"):
        side = r.choice((-1, 1))
        return dict(kind=kind, y=r.uniform(H * 0.12, H * 0.3), side=side, n=7 if kind == "birds" else 4,
                    x0=x0, x1=x1, dur=dur, seed=seed)
    if kind == "mouse":
        side = r.choice((-1, 1))
        return dict(kind=kind, s=0.7 * s, y=gy + 38 * s, side=side, x0=x0, x1=x1, dur=dur, seed=seed,
                    stop=r.uniform(0.35, 0.6))
    if kind == "moth":
        lights = [p for p in lay["props"] if p["name"] in FLAME_AT and x0 < p["x"] < x1]
        if not lights:
            return None
        lp = lights[r.randrange(len(lights))]
        dx, dy, size = FLAME_AT[lp["name"]]
        return dict(kind=kind, x=lp["x"] + dx * lp["s"], y=lp["y"] + dy * lp["s"] - size * lp["s"] * 0.5,
                    rad=max(40.0, size * lp["s"] * 1.4), seed=seed)
    if kind == "fish":
        w = (setting or {}).get("water")
        if not w:
            return None
        wy = (w[1] + w[2]) / 2
        return dict(kind=kind, y=wy, x=r.uniform(x0 + 0.2 * (x1 - x0), x0 + 0.8 * (x1 - x0)),
                    t=r.uniform(0.6, max(0.8, dur * 0.5)), seed=seed, every=max(2.6, dur * 0.55))
    return None


def _at_the_lamp(kind, lp, spec, lay, seed, dur, x0, x1, s, gy, taken, r, who_pool):
    """Somebody lights this lamp or blows it out: whoever is nearest leans
    in; if nobody is near, somebody comes. None when nobody can reach it."""
    dx, dy, _sz = FLAME_AT[lp["name"]]
    fx, fy = lp["x"] + dx * lp["s"], lp["y"] + dy * lp["s"]
    near = [(abs(f["x"] - fx), i) for i, f in enumerate(lay["people"])
            if f["pose"] in ("sit", "sit_on", "crouch", "stand", "recline")]
    near.sort()
    t_act = max(1.2, dur * 0.35)
    if near and near[0][0] < 3.8 * _R(lay["people"][near[0][1]]["who"], s):
        gi = near[0][1]
        f = lay["people"][gi]
        R = _R(f["who"], f["s"])
        face = "right" if fx > f["x"] else "left"
        a = dict(kind=kind, who=f["who"], s=f["s"], y=f["y"] + 4 * f["s"], seed=f["seed"], R=R, owns=gi,
                 item=None, mood=f.get("mood", "calm"),
                 keys=[(0.0, f["x"], f["pose"], f["action"] if kind == "snuff" else "idle", f["facing"]),
                       (t_act - 0.8, f["x"], f["pose"], "idle", face),
                       (dur + 5, f["x"], f["pose"], f["action"] if kind == "light" else "idle", face)])
    else:
        who = r.choice(who_pool)
        R = _R(who, s)
        ext = _extent_fn("stand", R)
        got = _spot(lay, ext, fx, taken, x0, x1, r)
        if got is None or abs(got[0] - fx) > 3.6 * R:
            return None
        x, face = got
        side = _clear_side(lay, x, x0, x1, R)
        if side is None or not _head_fits(spec, gy + 4 * s, R):
            return None
        start = (x0 + 1.4 * R) if side < 0 else (x1 - 1.4 * R)
        walk_t = abs(x - start) / (WALK_V * R)
        t_arr = t_act - 0.6
        t0 = t_arr - walk_t
        if t0 < 0:
            start = x - (x - start) * (t_arr / walk_t)
            t0 = 0.0
        a = dict(kind=kind, who=who, s=s, y=gy + 4 * s, seed=seed * 31 + 23, R=R, item=None,
                 keys=[(t0, start, "walk", "idle", "right" if x > start else "left"),
                       (t_arr, x, "stand", "idle", face), (dur + 5, x, "stand", "idle", face)])
        a["claim"] = (x + ext(face)[0], x + ext(face)[1])
    a["lamp"] = dict(name=lp["name"], x=fx, y=fy, s=lp["s"], t=t_act, on=(kind == "light"),
                     prop=lay["props"].index(lp))
    a["reach_to"] = dict(x=fx, y=fy, t0=t_act - 0.7, t1=t_act + 0.6, spill=(kind == "light"))
    return a


YARDS = ("village", "farmyard", "forum", "market_square", "street", "field", "olive_grove")


def _alive_without(spec: dict, prop: str | None = None, person: dict | None = None) -> bool:
    """Whether the picture still passes the measured motion rule
    (scene.is_living, what validate asks) once this light is out or this
    person has gone."""
    from .scene import is_living
    sp = dict(spec)
    sp.pop("happen", None)
    if prop is not None:
        names = list(sp.get("props") or [])
        for i, p in enumerate(names):
            if (p if isinstance(p, str) else (p or {}).get("name")) == prop:
                names.pop(i)
                break
        sp["props"] = names
    if person is not None:
        cast = list(sp.get("cast") or [])
        for i, c in enumerate(cast):
            if isinstance(c, dict) and c.get("who") == person["who"] and c.get("pose") == person["pose"]:
                cast.pop(i)
                break
        sp["cast"] = cast
    return is_living(sp)


def _far_lane(spec: dict) -> bool:
    """Whether the picture has ground behind the people to walk on: not
    indoors (it is the wall) and not by the water (it is the water)."""
    from .settings import SETTINGS
    st = SETTINGS.get(spec.get("setting"))
    return st is not None and not st.interior and not st.water


def fits(kind: str, spec: dict) -> bool:
    """Whether a happening belongs in this place at this hour at all: hens
    are not out at night, bats are not out by day, nobody walks in on a
    sleeping house, a cat stays indoors or in a yard."""
    from .settings import SETTINGS
    st = SETTINGS.get(spec.get("setting"))
    if st is None:
        return False
    time = spec.get("time")
    inside = st.interior
    asleep = any(isinstance(c, dict) and c.get("pose") == "lie" for c in spec.get("cast") or [])
    if kind in ("arrive", "serve", "child", "leave", "feed") and asleep:
        return False
    if kind == "feed" and spec.get("fire") == "low":
        return False                  # the words banked it; nobody builds it up again
    if kind == "passer":
        return not inside and not st.water
    if kind == "turn":
        return asleep
    if kind == "stretch":
        return any(isinstance(c, dict) and c.get("pose") in ("sit", "sit_on", "crouch") for c in spec.get("cast") or [])
    if kind == "hens":
        return spec.get("setting") in YARDS and time in ("day", "dawn", "dusk")
    if kind == "birds":
        return not inside and time in ("day", "dawn", "dusk")
    if kind == "bats":
        return not inside and time in ("dusk", "night")
    if kind == "fish":
        return bool(st.water)
    if kind == "mouse":
        return inside and time in ("dusk", "night")
    if kind == "moth":
        return time in ("dusk", "night")
    if kind == "cat":
        return inside or spec.get("setting") in YARDS
    return True


def _clear_side(lay, x, x0, x1, R, skip=None):
    """Which edge of the window somebody walks in from (or out to) without
    crossing anybody: the nearer side first; None when both paths cross a
    person or a big thing."""
    # people, and the furniture nobody walks through (a table, a couch, a
    # bed, a boat); a brazier or a basket is walked past in front
    from .scene import spans
    block = []
    for it in spans(lay):
        if it.get("fig") is not None:
            if it["fig"] != skip:
                block.append((it["lo"], it["hi"]))
        elif it.get("pid") is not None:
            p = lay["props"][it["pid"]]
            if PROPS[p["name"]].width >= 300 and p["layer"] != "back":
                block.append((it["lo"], it["hi"]))
    sides = [-1, 1] if x - x0 < x1 - x else [1, -1]
    for side in sides:
        start = (x0 + 1.4 * R) if side < 0 else (x1 - 1.4 * R)
        lo_, hi_ = sorted((start, x))
        if not any(min(hi_, b) - max(lo_, a) > 0.3 * R for a, b in block):
            return side
    return None


def _head_fits(spec, y, R) -> bool:
    """In a framed close-up, a standing person at (y) keeps their head under
    the top of the window."""
    fr = spec.get("frame")
    if not fr or spec.get("pan"):
        return True
    cx, cy, k = fr
    oy = min(max(cy * k - H / 2, 0.0), (k - 1) * H)
    top = oy / k
    return y - 5.9 * R >= top + 8


def _feed_in_place(spec, lay, fire, dur, x0, x1):
    """Nobody new has room at the fire: whoever already sits nearest it
    reaches in with a stick, and it flares."""
    near = sorted((abs(f["x"] - fire["x"]), i) for i, f in enumerate(lay["people"])
                  if f["pose"] in ("sit", "sit_on", "crouch", "stand") and x0 < f["x"] < x1)
    if not near:
        return None
    gi = near[0][1]
    f = lay["people"][gi]
    R = _R(f["who"], f["s"])
    if near[0][0] > 4.5 * R:
        return None
    face = "right" if fire["x"] > f["x"] else "left"
    t_act = max(1.0, dur * 0.3)
    return dict(kind="feed", who=f["who"], s=f["s"], y=f["y"] + 4 * f["s"], seed=f["seed"], R=R, owns=gi,
                item="branch", mood=f.get("mood", "calm"), item_until=t_act + 2.2,
                keys=[(0.0, f["x"], f["pose"], f["action"], f["facing"]),
                      (t_act - 0.6, f["x"], f["pose"], "feed_fire", face),
                      (t_act + 2.2, f["x"], f["pose"], "warm_hands", face),
                      (dur + 5, f["x"], f["pose"], "warm_hands", face)],
                flare=dict(x=fire["x"], y=fire["y"], s=fire["s"], name=fire["name"], t=t_act + 0.6))


def plan(kinds: list, spec: dict, lay: dict, seed: int, dur: float, facts=None) -> list[dict]:
    """Every asked-for happening that fits, worked out in order; a later one
    keeps out of the ground an earlier one claimed."""
    out, used = [], []
    owned = set()
    for k in kinds:
        if not fits(k, spec):
            continue
        a = build(k, spec, lay, seed + 101 * len(out), dur, facts, used)
        if a is None:
            continue
        if a.get("owns") is not None:
            if a["owns"] in owned:
                continue
            owned.add(a["owns"])
        if a.get("claim"):
            used.append(a["claim"])
        out.append(a)
    return out


def possible(spec: dict, lay: dict, seed: int, dur: float, facts=None) -> list[str]:
    return [k for k in KINDS if fits(k, spec) and build(k, spec, lay, seed, dur, facts) is not None]


# ------------------------------------------------------------------ the actors at t
def _state(a: dict, t: float):
    """(x, pose, action, facing, pose_to, blend, moving) of a person's track."""
    keys = a["keys"]
    if t <= keys[0][0]:
        k = keys[0]
        return k[1], k[2], k[3], k[4], None, 0.0, k[2] == "walk"
    for (ta, xa, pa, aa, fa), (tb, xb, pb, ab, fb) in zip(keys, keys[1:]):
        if ta <= t < tb:
            u = (t - ta) / max(1e-6, tb - ta)
            if abs(xb - xa) > 1.0:
                return xa + (xb - xa) * u, "walk", aa if pa == "walk" else "idle", \
                    ("right" if xb > xa else "left"), None, 0.0, True
            if pb != pa:
                return xa, pa, "idle", fb, pb, u, False
            return xa, pa, aa, fa, None, 0.0, False
    k = keys[-1]
    return k[1], k[2], k[3], k[4], None, 0.0, False


def _gait(a: dict, t: float) -> float:
    """The walk cycle's clock from the distance actually travelled, so the
    planted foot never slides."""
    keys = a["keys"]
    d = 0.0
    for (ta, xa, *_), (tb, xb, *_r) in zip(keys, keys[1:]):
        if t <= ta:
            break
        seg = min(t, tb) - ta
        if abs(xb - xa) > 1.0 and tb > ta:
            d += abs(xb - xa) * seg / (tb - ta)
    return d / (2.48 * a["R"]) * 1.1


def visible(a: dict, t: float) -> bool:
    if a.get("owns") is not None:
        return True
    return t >= a["keys"][0][0] - 0.01


def person(cr, a: dict, era: str, t: float, scene=None, cold=False):
    if not visible(a, t):
        return
    x, pose, action, facing, pose_to, blend, moving = _state(a, t)
    item = a.get("item") or "none"
    if a.get("item_until") is not None and t > a["item_until"]:
        item = "none"
    reach = reach_back = None
    R = a["R"]
    if "give" in a:
        g = a["give"]
        if t >= g["tm"]:
            item = "none"
        u = _bump(t, g["t0"], g["tm"], g["t1"])
        if u > 0:
            reach = _toward(a, x, pose, action, facing, t, (g["x"], g["y"]), u)
    if "reach_to" in a:
        rt = a["reach_to"]
        u = _bump(t, rt["t0"], (rt["t0"] + rt["t1"]) / 2, rt["t1"])
        if u > 0:
            reach = _toward(a, x, pose, action, facing, t, (rt["x"], rt["y"]), u)
    if a.get("run") and moving:
        gait = _gait(a, t) * 0.8
    else:
        gait = _gait(a, t) if moving else None
    lift = 0.0
    if "turn" in a:
        tn = a["turn"]
        lift = _bump(t, tn["t0"], tn["tm"], tn["t1"])
        action = a["keys"][0][3]
    people.draw(cr, who=a["who"], era=era, seed=a["seed"], pose=pose, action=action, x=x, ground_y=a["y"],
                scale=a["s"], t=t, facing=facing, mood=a.get("mood", "calm"), item=item,
                cold=cold, pose_to=pose_to, blend=blend, reach=reach, reach_back=reach_back, gait=gait, lift=lift)
    if "reach_to" in a and a["reach_to"]["spill"]:
        rt = a["reach_to"]
        u = _bump(t, rt["t0"], (rt["t0"] + rt["t1"]) / 2, rt["t1"])
        if 0 < u and t < (rt["t0"] + rt["t1"]) / 2 + 0.2:
            # the burning spill in the reaching hand
            hx = x + (reach[0] if facing == "right" else -reach[0]) if reach else rt["x"]
            hy = a["y"] + reach[1] if reach else rt["y"]
            flame(cr, hx, hy - 8 * a["s"], 16 * a["s"], t, a["seed"] + 3, glow_r=4.0, glow_a=0.35)


def _bump(t, t0, tm, t1) -> float:
    """0 before t0, up to 1 at tm, back to 0 by t1."""
    if t <= t0 or t >= t1:
        return 0.0
    if t < tm:
        return _ease((t - t0) / max(1e-6, tm - t0))
    return _ease(1 - (t - tm) / max(1e-6, t1 - tm))


def _toward(a, x, pose, action, facing, t, target, u):
    """The front hand part way from where the action holds it to a point in
    the picture, as an offset from the feet in the picture's x direction."""
    R = a["R"]
    ph = (a["seed"] % 97) * 0.37
    sk = people.skeleton(pose if pose != "lie" else "sit", R, t, ph)
    f, _b = people.hand_targets(action if action in people.ACTIONS else "idle", sk, R, t, ph)
    sx = 1.0 if facing == "right" else -1.0
    nat = (f[0] * sx, f[1])
    tgt = (target[0] - x, target[1] - a["y"])
    # never further than the arm reaches
    sh = (sk["neck"][0] * sx, sk["neck"][1] + 0.28 * R)
    dx, dy = tgt[0] - sh[0], tgt[1] - sh[1]
    d = math.hypot(dx, dy)
    if d > 1.8 * R:
        tgt = (sh[0] + dx / d * 1.8 * R, sh[1] + dy / d * 1.8 * R)
    p = (nat[0] + (tgt[0] - nat[0]) * u, nat[1] + (tgt[1] - nat[1]) * u)
    return (p[0] * sx, p[1])


# what an owned figure does once the happening has changed it
def owned_overrides(acts: list, t: float) -> dict:
    """{figure index: dict of draw overrides} for figures someone else's
    happening touches without owning them: the one being served reaches up
    and then eats; the adult whose child sits close puts an arm round."""
    out = {}
    for a in acts:
        if "give" in a:
            g = a["give"]
            u = _bump(t, g["t0"] + 0.2, g["tm"], g["t1"])
            d = out.setdefault(g["to"], {})
            if t >= g["tm"]:
                d["item"] = "bread" if g["after"] == "eat" else "cup"
                if t > g["t1"]:
                    d["action"] = g["after"]
            if u > 0:
                d["reach_pt"] = (g["x"], g["y"], u)
        if "hug" in a and t >= a["hug"]["t"]:
            u = _ease((t - a["hug"]["t"]) / 0.8)
            d = out.setdefault(a["hug"]["by"], {})
            x, *_ = _state(a, t)
            d["hug"] = (x, a["y"] - 3.2 * a["R"], u)
    return out


def draw_person_override(cr, f: dict, era: str, t: float, ov: dict, cold=False):
    R = _R(f["who"], f["s"])
    action = ov.get("action", f["action"])
    item = ov.get("item", f.get("item"))
    reach = reach_back = None
    tmp = dict(R=R, seed=f["seed"], y=f["y"])
    if "reach_pt" in ov:
        x, y, u = ov["reach_pt"]
        reach = _toward(tmp, f["x"], f["pose"], action, f["facing"], t, (x, y), u)
    if "hug" in ov:
        x, y, u = ov["hug"]
        reach_back = _toward(tmp, f["x"], f["pose"], action, f["facing"], t, (x, y), u)
    people.draw(cr, who=f["who"], era=era, seed=f["seed"], pose=f["pose"], action=action, x=f["x"],
                ground_y=f["y"], scale=f["s"], t=t, facing=f["facing"], mood=f.get("mood", "calm"), item=item,
                cold=cold, reach=reach, reach_back=reach_back)


# ------------------------------------------------------------------ light and fire
def flare(cr, a: dict, t: float):
    """The fire taking the new wood: it leaps, then settles, and throws a
    burst of sparks."""
    fl = a.get("flare")
    if not fl or t < fl["t"]:
        return
    u = (t - fl["t"]) / 2.4
    if u > 1:
        return
    env = math.sin(math.pi * min(1.0, u * 1.6)) if u < 0.62 else max(0.0, 1 - (u - 0.62) / 0.38) * 0.35
    dx, dy, size = FLAME_AT[fl["name"]]
    x, y, s = fl["x"] + dx * fl["s"], fl["y"] + dy * fl["s"], fl["s"]
    flame(cr, x, y, size * s * (0.5 + 0.9 * env), t, fl.get("seed", 5) + 11, glow_r=4.5, glow_a=0.5 * env)
    embers(cr, x, y - size * s * 0.6, s * 1.2, t * 1.6, 91, n=int(10 + 40 * env), spread=70.0, rise=320.0)


def lamp_level(acts: list, prop_index: int, t: float) -> float | None:
    """How lit a lamp is at t (0 dark .. 1 burning), or None when no
    happening touches it."""
    for a in acts:
        lm = a.get("lamp")
        if lm and lm["prop"] == prop_index:
            u = _ease((t - lm["t"]) / 0.7)
            return u if lm["on"] else 1 - u
    return None


def lamp_flame(cr, name, x, y, s, t, seed, level):
    """The lamp's flame at a level: it catches small and grows."""
    if level <= 0.02:
        return
    dx, dy, size = FLAME_AT[name]
    flame(cr, x, y, size * s * 0.6 * (0.35 + 0.65 * level), t, seed, glow_r=5.0 * level, glow_a=0.45 * level)


# ------------------------------------------------------------------ animals
def animal(cr, a: dict, t: float):
    k = a["kind"]
    if k == "dog":
        _dog(cr, a, t)
    elif k == "cat":
        _cat(cr, a, t)
    elif k == "hens":
        _hens(cr, a, t)
    elif k in ("birds", "bats"):
        _flock(cr, a, t)
    elif k == "fish":
        _fish(cr, a, t)
    elif k == "mouse":
        _mouse(cr, a, t)
    elif k == "moth":
        _moth(cr, a, t)


def _mouse(cr, a, t):
    """Across the floor in front of everything, in two dashes with a pause
    to sniff between them."""
    s = a["s"]
    span = a["x1"] - a["x0"] + 300
    T = a["dur"]
    st = a["stop"]
    # position along the run: dash, pause (a fifth of the time), dash
    u = t / T
    if u < st:
        q = u / st * st
    elif u < st + 0.2:
        q = st
    else:
        q = st + (u - st - 0.2) / 0.8 * (1 - st)
    q = min(1.1, q * 1.15)
    x = (a["x0"] - 150 + q * span) if a["side"] > 0 else (a["x1"] + 150 - q * span)
    moving = not (st <= u < st + 0.2)
    cr.save()
    cr.translate(x, a["y"])
    cr.scale(a["side"], 1)
    c = rgb("#8b8177")
    bob = math.sin(t * 40) * 2 * s if moving else 0
    ink.line(cr, [(-40 * s, -10 * s), (-80 * s, -6 * s), (-110 * s, -16 * s)], lw=4 * s, ink=c, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(0, -22 * s + bob, 42 * s, 22 * s, 16), c, lw=4 * s, amp=0.6, seed=2,
                    shadow=shade(c), shadow_dir=(0, 1))
    sniff = 0 if moving else math.sin(t * 18) * 3 * s
    ink.fill_stroke(cr, [(30 * s, -34 * s + bob), (66 * s + sniff, -18 * s + bob), (30 * s, -8 * s + bob)], c,
                    lw=4 * s, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(22 * s, -40 * s + bob, 12 * s, 12 * s, 10), rgb("#c9a7a0"), lw=3 * s,
                    amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(48 * s, -24 * s + bob, 3.5 * s, 3.5 * s, 8), ink.INK, lw=0, amp=0)
    cr.restore()


def _moth(cr, a, t):
    """A moth in loops round the flame, never into it."""
    w = 2 * math.pi * t / 2.3
    x = a["x"] + math.cos(w) * a["rad"] + math.sin(w * 2.7) * a["rad"] * 0.25
    y = a["y"] + math.sin(w * 1.3) * a["rad"] * 0.55
    flap = abs(math.sin(t * 2 * math.pi / 0.12))
    cr.set_source_rgba(0.93, 0.88, 0.76, 0.95)
    for sgn in (-1, 1):
        cr.save()
        cr.translate(x, y)
        cr.scale(1, 0.3 + 0.7 * flap)
        cr.move_to(0, 0)
        cr.curve_to(sgn * 6, -8, sgn * 14, -6, sgn * 13, 0)
        cr.curve_to(sgn * 12, 5, sgn * 5, 4, 0, 0)
        cr.restore()
        cr.fill()


def _along(a, t):
    u = min(1.0, max(0.0, (t - a["t0"]) / max(1e-6, a["t1"] - a["t0"])))
    return a["x0"] + (a["x1"] - a["x0"]) * u, u < 1.0


DOG_C = rgb("#b07a45")
DOG_PALE = rgb("#f0e2c8")


def _dog(cr, a, t):
    from .props import dog as curled
    x, moving = _along(a, t)
    s = a["s"]
    if not moving and a.get("lie") is not None:
        lie_t = t - a["t1"]
        if lie_t > 0.5:
            curled(cr, x, a["y"], s * 0.9, t, a["seed"])
            return
    d = 1 if a["x1"] > a["x0"] else -1
    cr.save()
    cr.translate(x, a["y"])
    cr.scale(d, 1)
    _quadruped(cr, s, t if moving else 0.0, DOG_C, DOG_PALE, tail_up=True, ears=True, length=1.0)
    cr.restore()


def _cat(cr, a, t):
    x, moving = _along(a, t)
    d = 1 if a["x1"] > a["x0"] else -1
    cr.save()
    cr.translate(x, a["y"])
    cr.scale(d, 1)
    c = rgb("#5a5550") if a["seed"] % 2 else rgb("#d08a3c")
    if moving:
        _quadruped(cr, a["s"], t, c, None, tail_up=True, ears=True, length=0.8, cat=True)
    else:
        _sitting_cat(cr, a["s"], t, c)
    cr.restore()


def _quadruped(cr, s, t, c, pale, tail_up=False, ears=False, length=1.0, cat=False):
    """A trotting four-legged animal facing +x, feet at y=0: legs swinging in
    diagonal pairs, the head bobbing with the step, the tail swaying."""
    L = 120 * s * length
    leg = 46 * s * (0.85 if cat else 1.0)
    c_t = 2 * math.pi * t / 0.5
    body_y = -leg - 18 * s
    bob = math.sin(2 * c_t) * 3 * s
    # far legs first, darker; each bends at the knee (forward at the front,
    # back at the hind) and lifts its paw as it swings forward
    for k, (bx, ph, front) in enumerate(((-0.34 * L, math.pi, False), (0.4 * L, 0, True),
                                         (-0.42 * L, 0, False), (0.32 * L, math.pi, True))):
        sw = math.sin(c_t + ph) * 16 * s
        lift = max(0.0, math.cos(c_t + ph)) * 9 * s
        col = shade(c, 0.75) if k < 2 else c
        knee = (bx + sw * 0.4 + (5 if front else -7) * s, -leg * 0.5 - lift * 0.5)
        paw = (bx + sw, -lift)
        ink.line(cr, [(bx, body_y + 12 * s + bob), knee, paw], lw=9 * s, ink=col, amp=0)
        ink.fill_stroke(cr, ink.ellipse_pts(paw[0] + 5 * s, paw[1] - 2 * s, 9 * s, 5 * s, 10), col, lw=2.5 * s,
                        amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(0, body_y + bob, L * 0.62, 30 * s, 20), c, lw=5 * s, amp=1.0, seed=3,
                    shadow=shade(c), shadow_dir=(0, 1))
    if pale is not None:
        ink.fill_stroke(cr, ink.ellipse_pts(0.36 * L, body_y + 14 * s + bob, 24 * s, 14 * s, 12), pale, lw=0,
                        amp=0)
    # tail
    sway = math.sin(c_t * 0.5) * 10 * s
    if tail_up:
        tip = (-0.62 * L - 30 * s, body_y - (60 if cat else 34) * s + sway)
        ink.line(cr, [(-0.55 * L, body_y + bob), (-0.66 * L, body_y - 20 * s), tip], lw=(9 if cat else 12) * s,
                 ink=c, amp=0)
    # head and neck
    hx, hy = 0.62 * L + 18 * s, body_y - 34 * s + bob * 1.5
    ink.line(cr, [(0.5 * L, body_y + bob), (hx - 8 * s, hy + 10 * s)], lw=20 * s, ink=c, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(hx, hy, 30 * s, 24 * s, 16), c, lw=5 * s, amp=0.8, seed=5,
                    shadow=shade(c), shadow_dir=(0, 1))
    ink.fill_stroke(cr, ink.ellipse_pts(hx + 28 * s, hy + 8 * s, 14 * s, 10 * s, 12), pale or c, lw=4 * s, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(hx + 40 * s, hy + 6 * s, 5 * s, 4 * s, 8), ink.INK, lw=0, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(hx + 8 * s, hy - 4 * s, 4 * s, 4.5 * s, 8), ink.INK, lw=0, amp=0)
    if ears:
        for dx in (-14, 2):
            ink.fill_stroke(cr, [(hx + dx * s, hy - 16 * s), (hx + (dx + 5) * s, hy - 42 * s),
                                 (hx + (dx + 15) * s, hy - 18 * s)], c, lw=3.5 * s, amp=0)


def _sitting_cat(cr, s, t, c):
    ink.fill_stroke(cr, ink.ellipse_pts(0, -55 * s, 42 * s, 58 * s, 18), c, lw=5 * s, amp=1, seed=4,
                    shadow=shade(c), shadow_dir=(-1, 0))
    sway = math.sin(2 * math.pi * t / 1.4) * 22 * s
    ink.line(cr, [(-30 * s, -8 * s), (-75 * s, -6 * s), (-90 * s + sway * 0.3, -40 * s + sway)], lw=9 * s,
             ink=c, amp=0)
    hx, hy = 12 * s, -122 * s
    ink.fill_stroke(cr, ink.ellipse_pts(hx, hy, 30 * s, 26 * s, 16), c, lw=5 * s, amp=0.8, seed=6)
    for dx in (-22, 8):
        ink.fill_stroke(cr, [(hx + dx * s, hy - 16 * s), (hx + (dx + 7) * s, hy - 44 * s),
                             (hx + (dx + 16) * s, hy - 18 * s)], c, lw=3.5 * s, amp=0)
    blink = (t % 3.3) < 0.15
    for dx in (-8, 12):
        if blink:
            ink.line(cr, [(hx + (dx - 4) * s, hy), (hx + (dx + 4) * s, hy)], lw=2.5 * s, amp=0)
        else:
            ink.fill_stroke(cr, ink.ellipse_pts(hx + dx * s, hy, 4 * s, 5 * s, 8), ink.INK, lw=0, amp=0)


def _hens(cr, a, t):
    s = a["s"]
    span = a["x1"] - a["x0"]
    v = span / max(4.0, a["dur"] * 1.6)
    for i in range(a["n"]):
        base = (a["x0"] + 0.08 * span + i * 130 * s) if a["side"] > 0 else (a["x1"] - 0.08 * span - i * 130 * s)
        x = base + a["side"] * v * t
        y = a["y"] - (i % 2) * 14 * s
        peck = max(0.0, math.sin(2 * math.pi * (t / 0.9 + i * 0.37)))
        cr.save()
        cr.translate(x, y)
        cr.scale(a["side"], 1)
        c = rgb("#efe6d6") if i % 2 else rgb("#a8653a")
        step = math.sin(2 * math.pi * t / 0.45 + i) * 8 * s
        for dx, st in ((-6, step), (6, -step)):
            ink.line(cr, [(dx * s, -30 * s), (dx * s + st, 0)], lw=4 * s, ink=rgb("#d9a441"), amp=0)
        ink.fill_stroke(cr, ink.ellipse_pts(0, -50 * s, 38 * s, 26 * s, 16), c, lw=4 * s, amp=1, seed=i,
                        shadow=shade(c), shadow_dir=(0, 1))
        ink.fill_stroke(cr, [(-34 * s, -56 * s), (-52 * s, -84 * s), (-26 * s, -70 * s)], c, lw=4 * s, amp=0)
        hx, hy = 34 * s + peck * 14 * s, -76 * s + peck * 52 * s
        ink.fill_stroke(cr, ink.ellipse_pts(hx, hy, 15 * s, 14 * s, 12), c, lw=4 * s, amp=0)
        ink.fill_stroke(cr, [(hx - 4 * s, hy - 12 * s), (hx + 4 * s, hy - 22 * s), (hx + 8 * s, hy - 11 * s)],
                        rgb("#c8402e"), lw=2.5 * s, amp=0)
        ink.fill_stroke(cr, [(hx + 13 * s, hy - 3 * s), (hx + 26 * s, hy + 2 * s), (hx + 13 * s, hy + 6 * s)],
                        rgb("#d9a441"), lw=2 * s, amp=0)
        cr.restore()


def _flock(cr, a, t):
    span = a["x1"] - a["x0"]
    bat = a["kind"] == "bats"
    v = span / (a["dur"] * (0.7 if bat else 0.9))
    r = random.Random(a["seed"] + 5)
    for i in range(a["n"]):
        off = r.uniform(-0.25, 0.1) * span
        x = (a["x0"] + off + v * t) if a["side"] > 0 else (a["x1"] - off - v * t)
        y = a["y"] + r.uniform(-60, 60) + (math.sin(t * 7 + i) * 26 if bat else math.sin(t * 1.3 + i) * 8)
        flap = math.sin(2 * math.pi * t / (0.22 if bat else 0.45) + i * 1.3)
        w = (18 if bat else 24) + r.uniform(-3, 4)
        col = (0.16, 0.13, 0.16) if bat else (0.2, 0.18, 0.22)
        cr.set_source_rgba(*col, 0.9)
        cr.set_line_width(3.2)
        cr.move_to(x - w, y - flap * w * 0.55)
        cr.curve_to(x - w * 0.5, y - flap * w * 0.25 - 4, x - 3, y - 2, x, y + 2)
        cr.curve_to(x + 3, y - 2, x + w * 0.5, y - flap * w * 0.25 - 4, x + w, y - flap * w * 0.55)
        cr.stroke()


def _fish(cr, a, t):
    u = ((t - a["t"]) % a["every"]) / 1.0 if t >= a["t"] else -1
    x, y = a["x"], a["y"]
    if 0 <= u <= 1:
        # the leap: an arc out of the water and back in
        px = x + (u - 0.5) * 120
        py = y - math.sin(math.pi * u) * 110
        ang = math.atan2(-math.cos(math.pi * u) * 110 * math.pi, 120)
        cr.save()
        cr.translate(px, py)
        cr.rotate(ang)
        c = rgb("#c9d3d6")
        ink.fill_stroke(cr, ink.ellipse_pts(0, 0, 34, 12, 14), c, lw=3.5, amp=0)
        ink.fill_stroke(cr, [(-30, 0), (-50, -14), (-50, 14)], c, lw=3, amp=0)
        cr.restore()
    for k, ring_t in enumerate((0.0, 1.0)):
        v = u - ring_t - (0.0 if k == 0 else 0.0)
        if 0 <= v <= 1.4:
            rx = x + (-60 if k == 0 else 60)
            rad = 12 + v * 70
            cr.set_source_rgba(1, 1, 1, 0.55 * (1 - v / 1.4))
            cr.set_line_width(3)
            cr.save()
            cr.translate(rx, y)
            cr.scale(1, 0.25)
            cr.arc(0, 0, rad, 0, 2 * math.pi)
            cr.restore()
            cr.stroke()
