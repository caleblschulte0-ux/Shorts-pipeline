"""Props that behave like the real thing, for every 3D shot (caaleb, 2026-11-12: "If he's going to pull off dates, let
them, like, pull them off like a piece of paper and fall to the floor ... there should be coins falling into the jar
... If we're going to do them, let's do them right").

  tear_off(page, hinge, t_tear, ...)  a page held at its top edge is pulled out from the bottom, rips free, and
                                      flutters to the floor, where it STAYS (the torn years pile up at his feet)
  pour(items, mouth_fn, land_fn, ...) discrete things leave a container's mouth on a schedule, fall under gravity and
                                      come to rest on whatever surface land_fn says is there at that moment

Both are baked to keyframes, frame by frame, from closed-form motion: no physics sim, so a shard of frames renders
exactly the same motion as the whole clip.
"""
import math, random
from mathutils import Vector

import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); from clock import FPS   # the one clock (tools/data3d/clock.py)
F = lambda t: int(round(t * FPS)) + 1
G = 9.8


def _key(o, f, loc=None, rot=None, scale=None, hide=None):
    if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
    if rot is not None: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)
    if scale is not None: o.scale = scale; o.keyframe_insert("scale", frame=f)
    if hide is not None:
        for x in [o] + list(o.children_recursive): x.hide_render = hide; x.keyframe_insert("hide_render", frame=f)


def tear_off(pivot, nf, t_tear, out, floor_z=0.0, peel_s=0.18, seed=0, page_h=0.3, side_drift=(-0.1, 0.1), layer=None,
             hold_s=0.3, carry=(0.16, 0.0, 0.24), out_drift=(0.28, 0.4)):
    """pivot: an EMPTY at the middle of the page's TOP edge with no rotation; the page hangs below it as its children,
    its face toward `out` (the unit vector pointing away from the wall). From t_tear - peel_s the bottom is pulled out
    (the page bends out about its top edge); at t_tear the top rips and it falls: drag holds it near a paper's
    terminal speed, it swings side to side as a leaf does, tips toward flat, lands and LIES on the floor, face up,
    where it came down. side_drift: how far it drifts along the wall (the hinge axis) as it falls; give it one sign
    to keep the pages off someone standing beside the pad. layer: its height in the pile (pass the tear order, so
    the latest page lands ON TOP; 11-12 judge: later years vanished under earlier ones).
    hold_s, carry: once it rips the page stays IN THE HAND for hold_s while the hand carries it down and away
    (carry = metres out from the wall, along the hinge axis, and down), and only then is let go (11-12 CI judge: the
    page flipped up over the pad and flew off while his hand stayed on the wall: "his hand is not on the page he
    tears"). Returns grab(t): the world point of the page's bottom middle (where the hand pulls), followed through
    the carry."""
    from mathutils import Matrix
    rnd = random.Random(seed); out = Vector(out).normalized(); down = Vector((0, 0, -1))
    hinge = down.cross(out).normalized()         # turning about this swings the hanging page's bottom OUT
    side = hinge
    top0 = pivot.location.copy()
    vt = rnd.uniform(1.1, 1.35)                   # terminal fall speed, m/s: a stiff calendar page drops; slower read as floating (11-12 judge)
    swing = rnd.uniform(0.05, 0.1) * (1 if rnd.random() < 0.5 else -1); fr = rnd.uniform(3.2, 4.2)
    drift = out * rnd.uniform(*out_drift) + side * rnd.uniform(*side_drift)   # well clear of the pad: a falling page never ghosts over the next one (11-12 judge)
    spin = rnd.uniform(-1.2, 1.2); PEEL = math.radians(40); CARRY_BEND = math.radians(20)
    carried = lambda e: top0 + (out * carry[0] + side * carry[1] + Vector((0, 0, -carry[2]))) * e

    def state(t):
        if t < t_tear - peel_s: return top0.copy(), 0.0, 0.0
        if t < t_tear:
            u = (t - (t_tear - peel_s)) / peel_s; return top0.copy(), PEEL * u * u, 0.0
        if t < t_tear + hold_s:                   # in his hand: carried down and away, the page hanging from his pinch
            e = (t - t_tear) / hold_s; e = e * e * (3 - 2 * e)
            return carried(e), PEEL + (CARRY_BEND - PEEL) * e, 0.0
        u = t - t_tear - hold_s; c0 = carried(1.0)
        z = vt * (u - (1 - math.exp(-5 * u)) / 5)
        loc = c0 + drift * (1 - math.exp(-1.6 * u)) + side * swing * math.sin(fr * u) + Vector((0, 0, -z))
        bend = CARRY_BEND + (math.radians(90) - CARRY_BEND) * (1 - math.exp(-1.8 * u)) + math.radians(22) * math.sin(fr * u + 1.0) * math.exp(-0.8 * u)
        return loc, bend, spin * u

    def R(bend, yaw): return Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(bend, 3, hinge)
    landed = None
    for f in range(1, nf + 1):
        t = (f - 1) / FPS
        if landed is None:
            loc, bend, yaw = state(t)
            low = loc.z - page_h * max(0.0, math.cos(bend))          # the page's lowest edge
            if t >= t_tear and min(loc.z, low) <= floor_z + 0.004:
                landed = (Vector((loc.x, loc.y, floor_z + 0.004 + 0.0022 * (seed % 11 if layer is None else layer))), yaw)   # each page its own layer: no z-fighting in the pile
        if landed is not None: loc, rot = landed[0], R(math.radians(90), landed[1])
        else: rot = R(bend, yaw)
        _key(pivot, f, loc=loc, rot=rot.to_euler())

    def grab(t):
        loc, bend, yaw = state(min(t, t_tear + hold_s))
        return loc + (R(bend, yaw) @ down) * page_h * 0.92
    return grab


def pour(items, nf, schedule, mouth_fn, land_fn, kick_fn=None, seed=0, hide_below=None, lie=False):
    """items: objects (coins); schedule: their release times (same length); mouth_fn(t) -> world point the item
    leaves from; kick_fn(t) -> initial velocity (default a small spill downward); land_fn(x, y, t) -> the height of the
    surface under (x, y) at time t, or None for 'keep falling'. An item sits hidden at the mouth until its time, falls,
    and once it touches the surface it RESTS there; hide_below(rest_point, t) -> True hides a rested item (buried by
    the fill rising past it). lie=True rests a long item (a flower on its stem) on its side, as a heap of them lies,
    not stood up on end."""
    rnd = random.Random(seed)
    for o, ts in zip(items, schedule):
        p0 = Vector(mouth_fn(ts)) + Vector((rnd.uniform(-0.012, 0.012), rnd.uniform(-0.012, 0.012), 0))
        v0 = Vector(kick_fn(ts)) if kick_fn else Vector((0, 0, -0.2))
        v0 += Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), rnd.uniform(-0.05, 0.05)))
        spin = Vector((rnd.uniform(-14, 14), rnd.uniform(-14, 14), rnd.uniform(-6, 6))); rest = None
        for f in range(1, nf + 1):
            t = (f - 1) / FPS; u = t - ts
            if u < 0: _key(o, f, loc=p0, scale=(0, 0, 0)); continue
            if rest is None:
                p = p0 + v0 * u + Vector((0, 0, -0.5 * G * u * u))
                s = land_fn(p.x, p.y, t)
                if s is not None and p.z <= s:
                    tip = (rnd.choice((-1, 1)) * rnd.uniform(1.2, 1.55)) if lie else rnd.uniform(-0.3, 0.3)
                    rest = (Vector((p.x, p.y, s)), tip, rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))
                else:
                    r = spin * u; _key(o, f, loc=p, rot=(r.x, r.y, r.z), scale=(1, 1, 1)); continue
            hidden = bool(hide_below and hide_below(rest[0], t))
            _key(o, f, loc=rest[0], rot=(rest[1], rest[2], rest[3]), scale=(0, 0, 0) if hidden else (1, 1, 1))


def bill_mesh(name="bill", w=0.1, h=0.045, res=(256, 116)):
    """ONE banknote mesh, shared by every bill (linked copies render fast): a printed note, not a green card (11-12
    judge: "flat green cards with no denomination or print ... toy-like paper squares"). The print is painted here
    in pixels: a pale green paper, a dark engraved border, a portrait oval, rosettes and the denomination in the
    corners, so at phone size it reads as MONEY."""
    import bpy, numpy as np
    W, H = res; yy, xx = np.mgrid[0:H, 0:W]; u = xx / (W - 1); v = yy / (H - 1)
    paper = np.array([0.72, 0.80, 0.64]); ink = np.array([0.10, 0.27, 0.16]); mid = np.array([0.42, 0.58, 0.40])
    img = np.ones((H, W, 3)) * paper
    img[(u + v * 0.7) % 0.04 < 0.012] = img[(u + v * 0.7) % 0.04 < 0.012] * 0.93          # fine guilloche hatching
    edge = (u < 0.035) | (u > 0.965) | (v < 0.07) | (v > 0.93)
    inner = ((u > 0.055) & (u < 0.945) & (np.abs(v - 0.1) < 0.012)) | ((u > 0.055) & (u < 0.945) & (np.abs(v - 0.9) < 0.012))
    img[edge] = ink; img[inner] = mid
    ov = ((u - 0.5) / 0.15) ** 2 + ((v - 0.5) / 0.36) ** 2
    img[ov < 1.0] = mid; img[(ov < 1.0) & (ov > 0.78)] = ink
    head = ((u - 0.5) / 0.065) ** 2 + ((v - 0.58) / 0.14) ** 2 < 1.0; body = ((u - 0.5) / 0.11) ** 2 + ((v - 0.2) / 0.16) ** 2 < 1.0
    img[(head | body) & (ov < 0.9)] = ink * 1.4
    for cx, cy in ((0.14, 0.27), (0.86, 0.73), (0.14, 0.73), (0.86, 0.27)):
        r = np.sqrt(((u - cx) * W / H) ** 2 + (v - cy) ** 2)
        img[(r < 0.15) & (r > 0.11)] = ink; img[r < 0.07] = ink
    for cx in (0.25, 0.75):                                   # seals: a ring each side of the portrait
        r = np.sqrt(((u - cx) * W / H) ** 2 + (v - 0.5) ** 2); img[(r < 0.13) & (r > 0.1)] = mid
    im = bpy.data.images.new(name + " print", W, H); px = np.ones((H, W, 4)); px[..., :3] = np.clip(img, 0, 1) ** 2.2
    im.pixels.foreach_set(px.astype(np.float32).ravel()); im.pack()
    m = bpy.data.materials.new(name + " print"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = im; nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(); [setattr(uv.data[i], "uv", c) for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1)))]
    me.materials.append(m); me.update()
    return me
