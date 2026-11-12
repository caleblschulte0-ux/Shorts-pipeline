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

FPS = 24
F = lambda t: int(round(t * FPS)) + 1
G = 9.8


def _key(o, f, loc=None, rot=None, scale=None, hide=None):
    if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
    if rot is not None: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)
    if scale is not None: o.scale = scale; o.keyframe_insert("scale", frame=f)
    if hide is not None:
        for x in [o] + list(o.children_recursive): x.hide_render = hide; x.keyframe_insert("hide_render", frame=f)


def tear_off(pivot, nf, t_tear, out, floor_z=0.0, peel_s=0.18, seed=0, page_h=0.3):
    """pivot: an EMPTY at the middle of the page's TOP edge with no rotation; the page hangs below it as its children,
    its face toward `out` (the unit vector pointing away from the wall). From t_tear - peel_s the bottom is pulled out
    (the page bends out about its top edge); at t_tear the top rips and it falls: drag holds it near a paper's
    terminal speed, it swings side to side as a leaf does, tips toward flat, lands and LIES on the floor, face up,
    where it came down. Returns grab(t): the world point of the page's bottom middle (where the hand pulls)."""
    from mathutils import Matrix
    rnd = random.Random(seed); out = Vector(out).normalized(); down = Vector((0, 0, -1))
    hinge = down.cross(out).normalized()         # turning about this swings the hanging page's bottom OUT
    side = hinge
    top0 = pivot.location.copy()
    vt = rnd.uniform(0.7, 0.9)                    # terminal fall speed, m/s: paper, not a brick
    swing = rnd.uniform(0.1, 0.18) * (1 if rnd.random() < 0.5 else -1); fr = rnd.uniform(3.2, 4.2)
    drift = out * rnd.uniform(0.12, 0.22) + side * rnd.uniform(-0.1, 0.1)
    spin = rnd.uniform(-1.2, 1.2); PEEL = math.radians(40)

    def state(t):
        if t < t_tear - peel_s: return top0.copy(), 0.0, 0.0
        if t < t_tear:
            u = (t - (t_tear - peel_s)) / peel_s; return top0.copy(), PEEL * u * u, 0.0
        u = t - t_tear
        z = vt * (u - (1 - math.exp(-5 * u)) / 5)
        loc = top0 + drift * (1 - math.exp(-1.6 * u)) + side * swing * math.sin(fr * u) + Vector((0, 0, -z))
        bend = PEEL + (math.radians(90) - PEEL) * (1 - math.exp(-1.8 * u)) + math.radians(22) * math.sin(fr * u + 1.0) * math.exp(-0.8 * u)
        return loc, bend, spin * u

    def R(bend, yaw): return Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(bend, 3, hinge)
    landed = None
    for f in range(1, nf + 1):
        t = (f - 1) / FPS
        if landed is None:
            loc, bend, yaw = state(t)
            low = loc.z - page_h * max(0.0, math.cos(bend))          # the page's lowest edge
            if t >= t_tear and min(loc.z, low) <= floor_z + 0.004:
                landed = (Vector((loc.x, loc.y, floor_z + 0.004)), yaw)
        if landed is not None: loc, rot = landed[0], R(math.radians(90), landed[1])
        else: rot = R(bend, yaw)
        _key(pivot, f, loc=loc, rot=rot.to_euler())

    def grab(t):
        loc, bend, yaw = state(min(t, t_tear))
        return loc + (R(bend, yaw) @ down) * page_h * 0.92
    return grab


def pour(items, nf, schedule, mouth_fn, land_fn, kick_fn=None, seed=0, hide_below=None):
    """items: objects (coins); schedule: their release times (same length); mouth_fn(t) -> world point the item
    leaves from; kick_fn(t) -> initial velocity (default a small spill downward); land_fn(x, y, t) -> the height of the
    surface under (x, y) at time t, or None for 'keep falling'. An item sits hidden at the mouth until its time, falls,
    and once it touches the surface it RESTS there; hide_below(rest_point, t) -> True hides a rested item (buried by
    the fill rising past it)."""
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
                    rest = (Vector((p.x, p.y, s)), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))
                else:
                    r = spin * u; _key(o, f, loc=p, rot=(r.x, r.y, r.z), scale=(1, 1, 1)); continue
            hidden = bool(hide_below and hide_below(rest[0], t))
            _key(o, f, loc=rest[0], rot=(rest[1], rest[2], rest[3]), scale=(0, 0, 0) if hidden else (1, 1, 1))
