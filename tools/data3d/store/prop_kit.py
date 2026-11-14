"""THE PROP KIT: props that carry a beat by themselves, for ANY story (2026-11-14). Each one was first built inline for
one short and is kept here so the next short starts from it instead of rebuilding it:

  wall_clock(name, loc, r)          a round wall clock: white face, black rim, twelve ticks, two hands
  spin_clock(hour, minute, t0, t1)  its hands race round `hours` hours, easing in and out
  alarm_clock(name, loc, r)         the wall clock as an ALARM CLOCK: a body behind it, two bells on top. Returns a dict
                                    with ring(t) (the shake angle of a ringing clock), race(t0, t1) and `moving` (its
                                    hands, for a consequence's {"moves": ...}). Saffron shot 4's clock, kept.
  wilt(obj, t0, t1)                 a living thing dies on camera: its OWN copy of each material fades to brown, it droops
                                    (returns droop(t) to fold into whatever moves it; key_rotation=True keys it itself),
                                    and its 'closed' shape key, if it has one, shuts. Saffron shot 4's flower, kept.
  zero_mark(name, hub, r, rest_deg) a bold mark on a dial where its needle rests: "barely moved" is measured FROM it.

wall_clock and spin_clock moved here verbatim from store/saffron_kit.py, which re-exports them; saffron_kit.gram_scale
draws its zero mark with zero_mark. tests/test_data3d_prop_kit.py holds every one EQUIVALENT to the code it came from
(the originals kept verbatim as oracles), so a story that switches to the kit is not quietly re-cut."""
import math
import bpy
from mathutils import Vector
import scene_kit as K
from clock import FPS

F = lambda t: int(round(t * FPS)) + 1


def _place(root, loc, yaw, parent):
    """children are built in the root's own frame (the root sits at the origin while they are made); then it moves"""
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    if parent is not None: root.parent = parent


def _mat(name, hexc, rough=0.5, emit=0.0, metal=0.0):
    return bpy.data.materials.get(name) or K.mat(name, hexc, rough=rough, emit=emit, metal=metal)


# ------------------------------------------------------------------ clocks
def wall_clock(name, loc, r=0.16, yaw=0.0, parent=None):
    """a round wall clock facing -Y (rotate with yaw): white face, black rim, twelve ticks, two hands.
    Returns (root, hour, minute): key hand.rotation_euler.y (radians, + clockwise from the front)."""
    root = K.empty(name, (0, 0, 0))
    K.cyl(name + " rim", (0, 0, 0), r, 0.03, _mat("clock rim", "#1E1D20", rough=0.35, metal=0.3), rot=(math.pi / 2, 0, 0), parent=root, bev=0.006)
    K.cyl(name + " face", (0, -0.016, 0), r * 0.9, 0.004, _mat("clock face", "#F8F5EC", rough=0.5), rot=(math.pi / 2, 0, 0), parent=root, bev=0.001)
    ink = _mat("clock ink", "#1E1D20", rough=0.5)
    for k in range(12):
        a = math.radians(30 * k)
        K.box(f"{name} tick {k}", (r * 0.78 * math.sin(a), -0.02, r * 0.78 * math.cos(a)), (0.008 if k % 3 == 0 else 0.004, 0.002, r * (0.16 if k % 3 == 0 else 0.09)), ink,
              bev=0, parent=root).rotation_euler = (0, a, 0)
    hands = []
    for nm, L, w, dy in (("hour", r * 0.5, 0.012, -0.022), ("minute", r * 0.75, 0.008, -0.025)):
        p = K.empty(f"{name} {nm}", (0, dy, 0), parent=root)
        K.box(f"{name} {nm} hand", (0, dy, L / 2 - 0.01), (w, 0.002, L), ink if nm == "hour" else _mat("clock minute", "#C42A1C", rough=0.4), bev=0, parent=p)
        hands.append(p)
    K.cyl(name + " hub", (0, -0.027, 0), 0.01, 0.004, ink, rot=(math.pi / 2, 0, 0), parent=root)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root, hands[0], hands[1]


def spin_clock(hour, minute, t0, t1, hours=8.0, start_h=7.0):
    """the hands race round: `hours` hours from t0 to t1 (minute hand: 2*pi per hour), easing in and out"""
    for f in range(1, F(t1) + 30):
        t = (f - 1) / FPS; u = 0.0 if t < t0 else 1.0 if t > t1 else (t - t0) / (t1 - t0)
        u = u * u * (3 - 2 * u); hh = start_h + hours * u
        minute.rotation_euler = (0, 2 * math.pi * (hh % 1.0) + 2 * math.pi * int(hh), 0); minute.keyframe_insert("rotation_euler", frame=f)
        hour.rotation_euler = (0, 2 * math.pi * hh / 12.0, 0); hour.keyframe_insert("rotation_euler", frame=f)


def ring(t, t0=0.0, amp_deg=7.0, hz=11.0, ramp=0.4, t1=None):
    """the shake of a RINGING clock at time t (radians, about the lens axis): a fast buzz that builds over `ramp`"""
    u = t - t0
    if u < 0 or (t1 is not None and t > t1): return 0.0
    return math.radians(amp_deg) * math.sin(2 * math.pi * hz * u) * (1.0 if u > ramp else u / ramp)


def alarm_clock(name, loc=(0, 0, 0), r=0.075, yaw=0.0, parent=None):
    """an ALARM CLOCK facing -Y: the wall clock's face and racing hands on a dark body, two brass bells on top. Sized by
    r (the face radius; the bells and body scale with it). Returns dict(root, hour, minute, bells, body, moving,
    ring=ring(t, ...), race=race(t0, t1, hours, start_h)). Hold it with follow(root, ..., rot_fn=lambda t: (0, ring(t), 0))."""
    root, hh, mm = wall_clock(name, (0, 0, 0), r=r)
    bell_m = _mat("clock bell", "#C9A227", rough=0.3, metal=0.8)
    k = r / 0.075
    bells = [K.sph(f"{name} bell {sg}", (sg * 0.05 * k, 0.0, 0.075 * k), 0.03 * k, bell_m, parent=root)
             for sg in (-1, 1)]
    body = K.box(f"{name} body", (0, 0.012 * k, 0), (0.17 * k, 0.03 * k, 0.17 * k), _mat("clock rim", "#1E1D20"), bev=0.03 * k, parent=root)
    _place(root, loc, yaw, parent)
    moving = [o for p in (hh, mm) for o in p.children if o.type == 'MESH']
    return dict(root=root, hour=hh, minute=mm, bells=bells, body=body, moving=moving, ring=ring,
                race=lambda t0, t1, hours=5.0, start_h=5.0: spin_clock(hh, mm, t0, t1, hours=hours, start_h=start_h))


# ------------------------------------------------------------------ a living thing dies on camera
def wilt(obj, t0, t1, brown="#6B4A2E", to=0.85, droop_deg=75.0, closed=True, key_rotation=False, axis=0, sign=-1.0, slots=None):
    """`obj` wilts from t0 to t1: each of its materials is COPIED for it alone (so nothing else browns) and its base
    colour is mixed toward `brown` up to `to`; its 'closed' shape key (if it has one and closed=True) shuts; and it
    droops `droop_deg`, eased. Returns droop(t), the droop angle in radians at t (>= 0), to fold into a rot_fn of
    whatever carries it; key_rotation=True keys obj.rotation_euler[axis] itself (its rest rotation + sign * droop).
    slots: which material slots brown (None: all of them; (0,) the petals of a crocus, as saffron shot 4 did)."""
    for i, slot in enumerate(obj.material_slots):
        if slots is not None and i not in slots: continue
        if slot.material is None or not slot.material.use_nodes: continue
        pm = slot.material.copy(); pm.name = f"wilting {obj.name}" if i == 0 else f"wilting {obj.name} {i}"
        slot.material = pm
        nt = pm.node_tree; bsdf = nt.nodes.get("Principled BSDF")
        if bsdf is None: continue
        inp = bsdf.inputs["Base Color"]
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'
        mix.inputs["B"].default_value = (*K.lin(brown), 1)
        if inp.is_linked: nt.links.new(inp.links[0].from_socket, mix.inputs["A"])
        else: mix.inputs["A"].default_value = tuple(inp.default_value)
        nt.links.new(mix.outputs["Result"], inp)
        fac = mix.inputs["Factor"]
        for t_, v in ((0.0, 0.0), (t0, 0.0), (t1, to)):
            fac.default_value = v; fac.keyframe_insert("default_value", frame=F(t_))
    sk = obj.data.shape_keys if closed and getattr(obj.data, "shape_keys", None) else None
    if sk and "closed" in sk.key_blocks:
        kb = sk.key_blocks["closed"]
        for t_, v in ((0.0, 0.0), (t0, 0.0), (t1, 1.0)):
            kb.value = v; kb.keyframe_insert("value", frame=F(t_))
    droop = lambda t: math.radians(droop_deg) * (lambda u: u * u * (3 - 2 * u))(max(0.0, min(1.0, (t - t0) / max(1e-6, t1 - t0))))
    if key_rotation:
        r0 = obj.rotation_euler[axis]
        for f in range(1, F(t1) + 2):
            obj.rotation_euler[axis] = r0 + sign * droop((f - 1) / FPS); obj.keyframe_insert("rotation_euler", index=axis, frame=f)
    return droop


# ------------------------------------------------------------------ gauges
def zero_mark(name, hub, r, rest_deg, mat, size=(0.006, 0.0015, 0.012), parent=None):
    """a bold mark on a dial at the angle its needle RESTS at (rest_deg, + clockwise from 12 as seen from the front),
    r from the needle's hub (x, y, z): a change is read FROM it, so "the needle hardly moved" is a gap you can see"""
    a = math.radians(rest_deg)
    z0 = K.box(name, tuple(hub), size, mat, bev=0, parent=parent)
    z0.location = (hub[0] + r * math.sin(a), hub[1], hub[2] + r * math.cos(a))
    z0.rotation_euler = (0, a, 0)
    return z0
