"""Acting glue for the checkout shot: the straight-arm cart push, grips, measurement.
THE ARM RULE: side-on, Data's near arm is ONE STRAIGHT LINE shoulder -> handle end. So the cart is placed EVERY FRAME
where a straight arm reaches the bar from the CURRENT shoulder (the walk leans the torso; a lead fixed at t0 leaves slack
and the elbow bends). Each hand takes the handle end on ITS OWN side. `arm_bend` MEASURES it; never eyeball it."""
import bpy, math, os
from mathutils import Vector

import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); from clock import FPS   # the one clock (tools/data3d/clock.py)
F = lambda t: int(round(t * FPS)) + 1

def ease(u): u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)
def ease_out(u): u = max(0.0, min(1.0, u)); return 1 - (1 - u) ** 3
def ease_in(u): u = max(0.0, min(1.0, u)); return u ** 3
def ease_out_back(u, s=1.2):
    u = max(0.0, min(1.0, u)) - 1; return 1 + u * u * ((s + 1) * u + s)
def lerp(a, b, u): return a + (b - a) * u

HAND_PITCH = -30.0     # degrees: the mitten sits OVER the bar
WRIST_UP = 0.012       # the wrist target sits just above the bar axis: the mitten wraps OVER the bar, hand ON it
REACH_K = 0.998
LEAN_PUSH = float(os.environ.get("LEAN_PUSH", "11"))   # degrees: a person pushing a loaded cart leans into it; 5 read as standing bolt upright


def world(o):
    bpy.context.view_layer.update(); return o.matrix_world.translation.copy()


def _shoulder(data, s):
    M = data.arm.matrix_world; return M @ data.pb[f"arm.{s}"].head


def _own_side_anchor(data, cart, s):
    """the handle end on the hand's OWN side: the anchor laterally nearest that shoulder (never crossed). The rig names
    its bones from the viewer's side, so this is decided by geometry, not by the letter."""
    sh = _shoulder(data, s); fw = data.forward()
    def lat(p): r = p - sh; return (r - fw * r.dot(fw)).length
    a, b = world(cart["handle_L"]), world(cart["handle_R"])
    return cart["handle_L"] if lat(a) <= lat(b) else cart["handle_R"]


def _key_cart(cart, t, loc, rot_z=None):
    r = cart["root"]; r.location = loc; r.keyframe_insert("location", frame=F(t))
    if rot_z is not None: r.rotation_euler = (0, 0, rot_z); r.keyframe_insert("rotation_euler", frame=F(t))


def push(data, cart, target, t0, t1, hold_until=None, near="L"):
    """Data walks from where he stands at t0 to `target` by t1 pushing the cart; per frame the cart is placed where a
    STRAIGHT near arm (shoulder -> bar end) reaches the handle. Returns the frame range pushed."""
    sc = data.sc
    data.walk_to(target, t0, t1, pushing=True, lean=LEAN_PUSH)
    tend = hold_until if hold_until is not None else t1
    dirn = None; reach = (data.U + data.Fo) * REACH_K   # U, Fo are in METRES already (character.py bakes SCALE in)
    hz_local = (cart["root"].matrix_world.inverted() @ world(cart["handle_L"])).z
    # root offset: handle bar axis -> cart root, in cart local
    hl = cart["root"].matrix_world.inverted() @ world(cart["handle_L"]); hr = cart["root"].matrix_world.inverted() @ world(cart["handle_R"])
    bar_mid_local = (hl + hr) / 2
    for f in range(F(t0), F(tend) + 1):
        t = (f - 1) / FPS
        sc.frame_set(f)
        p = Vector(data.arm.location); yaw = data.arm.rotation_euler.z; fw = data.forward(yaw)
        # bar centre must sit where both straight arms reach their own ends: use the mean shoulder
        shL, shR = _shoulder(data, "L"), _shoulder(data, "R"); sh = (shL + shR) / 2
        bar_z = hz_local + 0.0
        dz = bar_z + WRIST_UP - sh.z
        dy = 0.0
        ahead = math.sqrt(max(0.0, reach * reach - dz * dz - dy * dy))
        bar_mid_world = Vector((sh.x, sh.y, 0)) + fw * ahead; bar_mid_world.z = 0
        rot = math.atan2(fw.y, fw.x)                    # cart +X along his facing
        # root = bar_mid_world - R(rot) @ bar_mid_local(xy)
        c, s_ = math.cos(rot), math.sin(rot)
        off = Vector((c * bar_mid_local.x - s_ * bar_mid_local.y, s_ * bar_mid_local.x + c * bar_mid_local.y, 0))
        root0 = bar_mid_world - off
        if dirn is None: dirn = Vector(fw); lat0 = root0 - dirn * root0.dot(dirn)   # the cart runs on ONE line: the hips' turn never rocks it sideways
        root0 = lat0 + dirn * root0.dot(dirn); root0.z = 0
        _key_cart(cart, t, root0, rot)
        # refine: the NEAR arm's own anchor must sit exactly `reach` from ITS shoulder (lateral offset and the lean
        # make the mean-shoulder estimate short by a few cm, and a few cm of slack is a bent elbow)
        for _ in range(3):
            sc.frame_set(f)
            anc = _own_side_anchor(data, cart, near); a = world(anc); a.z += WRIST_UP
            shn = _shoulder(data, near); rel = a - shn
            along = rel.dot(fw); lat = rel - fw * along; lat_z = lat.z; lat_h = (lat - Vector((0, 0, lat_z))).length
            want = math.sqrt(max(0.0, reach * reach - lat_h * lat_h - lat_z * lat_z))
            root0 = root0 + fw * (want - along)
            _key_cart(cart, t, root0, rot)
        sc.frame_set(f)
        for s in "LR":
            anc = _own_side_anchor(data, cart, s); tgt = world(anc); tgt.z += WRIST_UP
            data._arm_ik(s, tgt, t, elbow_out=0.15)
            data._k(f"hand.{s}", t, rot=(HAND_PITCH, 0, 0))
    spin_wheels(cart, t0, tend)
    return F(t0), F(tend)


def spin_wheels(cart, t0, t1):
    """wheels rotate with travel: integrate the root's path"""
    sc = bpy.context.scene; r = cart["wheel_r"]; ang = 0.0; prev = None
    for f in range(F(t0), F(t1) + 1):
        sc.frame_set(f); p = Vector(cart["root"].location)
        if prev is not None: ang += (p - prev).length / r
        prev = p
        for w in cart["wheels"]:
            w.rotation_euler = (math.radians(90), -ang, 0); w.keyframe_insert("rotation_euler", frame=f)


def arm_slope(data, f0, f1, side="L"):
    """degrees BELOW horizontal of the straight line shoulder -> wrist over [f0,f1]; returns (min, mean, max)"""
    sc = data.sc; vals = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f); M = data.arm.matrix_world
        d = (M @ data.pb[f"hand.{side}"].head) - (M @ data.pb[f"arm.{side}"].head)
        vals.append(-math.degrees(math.atan2(d.z, Vector((d.x, d.y, 0)).length)))
    return min(vals), sum(vals) / len(vals), max(vals)


def arm_bend(data, f0, f1, side="L"):
    """degrees between upper arm and forearm directions over [f0,f1]; returns (max, mean). ~0 = straight."""
    sc = data.sc; vals = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f); M = data.arm.matrix_world
        A, Fo = data.pb[f"arm.{side}"], data.pb[f"fore.{side}"]
        u = (M @ A.tail - M @ A.head).normalized(); v = (M @ Fo.tail - M @ Fo.head).normalized()
        vals.append(math.degrees(math.acos(max(-1, min(1, u.dot(v))))))
    return max(vals), sum(vals) / len(vals)


def near_side(data, cam):
    """which arm the camera sees: the shoulder nearer the camera"""
    bpy.context.view_layer.update(); c = cam.matrix_world.translation
    return "L" if (_shoulder(data, "L") - c).length < (_shoulder(data, "R") - c).length else "R"


def hand_on_bar(data, cart, side):
    """distance from the mitten's wrist to its own handle end (metres) at the current frame"""
    M = data.arm.matrix_world; w = M @ data.pb[f"hand.{side}"].head
    return (w - world(_own_side_anchor(data, cart, side))).length
