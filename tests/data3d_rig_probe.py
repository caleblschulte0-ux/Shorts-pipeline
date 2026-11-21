"""Run INSIDE Blender's python (bpy) by tests/test_data3d_rig.py: builds Data and the kit for real and prints one JSON
line of measurements, so the 2026-11-14 system checks are held on the rig itself and not only on its source.

    <blender python> -I tests/data3d_rig_probe.py"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D3 = os.path.join(ROOT, "tools", "data3d")
sys.path[:0] = [D3, os.path.join(D3, "store")]
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

OUT = {}


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import scene_kit; scene_kit._MATS.clear()                  # its material cache points at the scene just thrown away
    sc = bpy.context.scene; sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    return sc


def data_in(sc):
    import character as CH
    d = CH.load(sc); d.place(0, 0, 0); return d


import character as CH
import facelint
F = CH.F

# ---------------------------------------------------------------- 1. the face lint catches tonight's defect class
def face_case(clear):
    sc = fresh(); d = data_in(sc)
    if not clear:                                             # the code before 2026-11-14's fixes: no clearing, releases go to rest
        d._clear_face = lambda a, b: None
        d._release_face = lambda i: CH.Data.EXPRESSIONS["neutral"]
    d.expression("worried", 0.0, 2.0, blend=0.3)              # its release keys his resting face at 2.3 ...
    d.perform("alarmed", 2.05, hold=1.5, arms=False)          # ... inside the alarm that began at 2.05
    n = d.finish()
    return facelint.check(d, n, name="probe")


OUT["face_lint_with_fix"] = face_case(True)
OUT["face_lint_without_fix"] = face_case(False)


def hook_case(rekey_starts):
    """the posted banana hook's order: happy, a 'surprised' flash, THEN an open-ended 'alarmed' that began before the
    flash. The flash's blend-in start was keyed with the resting face before the alarm existed."""
    sc = fresh(); d = data_in(sc)
    if not rekey_starts:
        d._held_at = lambda i, r: None
    d.expression("happy", 0.0, 1.95)
    d.expression("surprised", 2.85, 3.4, blend=0.06)
    d.expression("alarmed", 2.1, blend=0.08)
    n = d.finish()
    return facelint.check(d, n, name="probe")


OUT["hook_with_fix"] = hook_case(True)
OUT["hook_without_fix"] = hook_case(False)

# ---------------------------------------------------------------- 2. one-sided face: the state reads back, wry is lopsided
sc = fresh(); d = data_in(sc)
d._face(0.0, **CH.Data.EXPRESSIONS["wry"]); sc.frame_set(1); bpy.context.view_layer.update()
st = d._face_state()
OUT["wry_state"] = {k: round(v, 3) for k, v in st.items()}
bz = {d.BROW_SIDE[b.name]: (b.matrix_world @ Vector(b.data.splines[0].points[0].co[:3])).z for b in d.brows}
OUT["brow_sides"] = sorted(d.BROW_SIDE.values())
OUT["wry_brow_dz_mm"] = round((bz["R"] - bz["L"]) * 1000, 2)
kb = d.lips.data.shape_keys.key_blocks
OUT["lip_keys"] = sorted(kb.keys())
OUT["inside_keys"] = sorted(d.mouth_inside.data.shape_keys.key_blocks.keys())
co = facelint.coeffs(CH._mouth_paths(), CH.MOUTH_KEYS)
OUT["smile_read"] = {k: round(facelint.smile_read(e, co), 3) for k, e in CH.Data.EXPRESSIONS.items()}
for e in ("neutral", "worried", "happy"):
    d._face(0.0, **CH.Data.EXPRESSIONS[e]); sc.frame_set(1)
    s2 = d._face_state()
    OUT.setdefault("roundtrip_err", {})[e] = round(max(abs(s2[k] - CH.Data.EXPRESSIONS[e].get(k, 0.0)) for k in ("brow", "frown", "worry", "mad", "smile", "grin", "cock", "side")), 4)

# ---------------------------------------------------------------- 3. a look down bends the neck and the eyes follow
sc = fresh(); d = data_in(sc)
sc.frame_set(1); bpy.context.view_layer.update()
head0 = d.arm.matrix_world @ d.pb["head"].head
tgt = Vector((0.03, -0.3, 0.3))                       # a flower held low in front of him, at table height
d.look_at(tgt, 1.0); d.idle(0.0, 2.5)                  # idle keys the neck AFTER the look: the look must survive it
n = d.finish(); f = F(1.6); sc.frame_set(f); bpy.context.view_layer.update()
M = d.arm.matrix_world
c0, c1 = M @ d.pb["chest"].head, M @ d.pb["chest"].tail; h0, h1 = M @ d.pb["head"].head, M @ d.pb["head"].tail
ang = lambda u, v: math.degrees(u.normalized().angle(v.normalized()))
OUT["look_down_bend_deg"] = round(ang(c1 - c0, h1 - h0), 1)
OUT["look_down_neck_deg"] = round(math.degrees(d.pb["neck"].rotation_euler.x), 1)
g = d.EYE["Lgaze"]; eye = g.matrix_world.translation
look = (g.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
OUT["gaze_off_target_deg"] = round(math.degrees(look.angle((tgt - eye).normalized())), 1)
hd = (M.to_3x3() @ (d.pb["head"].matrix @ d.pb["head"].bone.matrix_local.inverted()).to_3x3() @ Vector((0, -1, 0))).normalized()
OUT["head_off_target_deg"] = round(math.degrees(hd.angle((tgt - eye).normalized())), 1)
import anatomy, twitch
OUT["look_down_anatomy"] = anatomy.check(d, n, name="probe")
OUT["look_down_twitch"] = twitch.check(d, n, name="probe")
OUT["tilt_table"] = {p: round(CH.Data._tilt(p), 1) for p in (-10, -22, -40, -60, 10, 40)}

# ---------------------------------------------------------------- 4. hands solved after body acting
def hands_case(resolve):
    sc = fresh(); d = data_in(sc)
    sc.frame_set(1); bpy.context.view_layer.update()
    P = d.arm.matrix_world @ d.pb["chest"].tail + Vector((0.08, -0.15, -0.08))
    d.reach("R", lambda t: P, 0.4, 2.4, lead=0.3, back=None)
    d.perform("worried", 0.8, hold=0.9, arms=False)        # chest, spine and shoulders move AFTER the hand was solved
    if not resolve: d._resolve_hands = lambda tol=0.01: None
    n = d.finish(); worst = 0.0
    for f in range(F(0.6), F(2.4) + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        worst = max(worst, ((d.arm.matrix_world @ d.pb["fore.R"].tail) - P).length)
    return worst, d.hands_resolved[0]


OUT["hands_drift_resolved_cm"], OUT["hands_resolved_frames"] = (lambda w, k: (round(w * 100, 2), k))(*hands_case(True))
OUT["hands_drift_unresolved_cm"] = round(hands_case(False)[0] * 100, 2)

# ---------------------------------------------------------------- 5. motion you can see
import scene_kit as K, staging
def motion_case(deg):
    sc = fresh()
    K.camera((0, -0.6, 0.2), (0, 0, 0.2), lens=40)
    body = K.box("scale body", (0, 0, 0.2), (0.14, 0.1, 0.14), K.mat("b", "#EEEEEE"))
    piv = K.empty("needle pivot", (0, -0.06, 0.2))
    nd = K.box("needle", (0, -0.06, 0.225), (0.004, 0.002, 0.05), K.mat("n", "#CC2222"), parent=piv)
    for f, a in ((1, 0.0), (20, deg), (40, deg)):
        piv.rotation_euler = (0, math.radians(a), 0); piv.keyframe_insert("rotation_euler", frame=f)
    return staging.consequence(sc.camera, 40, [("the needle flicks", [body, nd], 0.0, 1.3, {"moves": [nd]})], name="probe")


OUT["motion_small_ok"] = motion_case(6)
OUT["motion_big_ok"] = motion_case(90)

# ---------------------------------------------------------------- 6. the prop kit is EQUIVALENT to the code it came from
ORACLE = r'''
def _mat(name, hexc, rough=0.5, emit=0.0, metal=0.0):
    return bpy.data.materials.get(name) or K.mat(name, hexc, rough=rough, emit=emit, metal=metal)


def _place(root, loc, yaw, parent):
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    if parent is not None: root.parent = parent


def wall_clock(name, loc, r=0.16, yaw=0.0, parent=None):
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
    for f in range(1, F(t1) + 30):
        t = (f - 1) / FPS; u = 0.0 if t < t0 else 1.0 if t > t1 else (t - t0) / (t1 - t0)
        u = u * u * (3 - 2 * u); hh = start_h + hours * u
        minute.rotation_euler = (0, 2 * math.pi * (hh % 1.0) + 2 * math.pi * int(hh), 0); minute.keyframe_insert("rotation_euler", frame=f)
        hour.rotation_euler = (0, 2 * math.pi * hh / 12.0, 0); hour.keyframe_insert("rotation_euler", frame=f)


def follow(obj, fn, t0=0.0, t1=None, rot_fn=None):
    for f in range(F(t0), F(t1 if t1 is not None else DUR) + 1):
        t = (f - 1) / FPS; obj.location = fn(t); obj.keyframe_insert("location", frame=f)
        if rot_fn: obj.rotation_euler = rot_fn(t); obj.keyframe_insert("rotation_euler", frame=f)


def shot4_props():
    # saffron shot 4 (commit 915f2c39e), its alarm clock and its wilting crocus, verbatim but for the data and the field
    hero = SK.crocus("dawn crocus", (0, 0, 0), yaw=0.6, scale=1.25, seed=61)
    pm = hero.active_material.copy(); pm.name = "wilting petal"
    hero.material_slots[0].material = pm
    nt = pm.node_tree; bsdf = nt.nodes["Principled BSDF"]
    src = bsdf.inputs["Base Color"].links[0].from_socket
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'
    mix.inputs["B"].default_value = (*K.lin("#6B4A2E"), 1)
    nt.links.new(src, mix.inputs["A"]); nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    fac = mix.inputs["Factor"]
    T_W0, T_W1 = 0.6, DUR - 0.8
    for t_, v in ((0.0, 0.0), (T_W0, 0.0), (T_W1, 0.85)):
        fac.default_value = v; fac.keyframe_insert("default_value", frame=F(t_))
    kb = hero.data.shape_keys.key_blocks["closed"]
    for t_, v in ((0.0, 0.0), (T_W0, 0.0), (T_W1, 1.0)):
        kb.value = v; kb.keyframe_insert("value", frame=F(t_))
    droop = lambda t: math.radians(75) * ease(max(0.0, min(1.0, (t - T_W0) / (T_W1 - T_W0))))
    follow(hero, lambda t: G - Vector((0, 0, 0.05)), 0.0, DUR, rot_fn=lambda t: (-droop(t), 0, 0.6))
    CK = Vector((-0.15, -0.36, 0.7))
    clock, hh, mm = wall_clock("alarm clock", (0, 0, 0), r=0.075)
    bell_m = _mat("clock bell", "#C9A227", rough=0.3, metal=0.8)
    for sg in (-1, 1):
        K.sph(f"alarm bell {sg}", (sg * 0.05, 0.0, 0.075), 0.03, bell_m, parent=clock)
    K.box("alarm clock body", (0, 0.012, 0), (0.17, 0.03, 0.17), _mat("clock rim", "#1E1D20"), bev=0.03, parent=clock)
    spin_clock(hh, mm, 0.2, DUR - 0.3, hours=5.0, start_h=5.0)
    ring = lambda t: math.radians(7) * math.sin(2 * math.pi * 11 * t) * (1.0 if t > 0.4 else t / 0.4)
    follow(clock, lambda t: CK, 0.0, DUR, rot_fn=lambda t: (0, ring(t), 0))
    ink = _mat("scale ink", "#1C1B1E", rough=0.5)
    z0 = K.box("scale zero mark", (0, -0.0535, 0.036), (0.006, 0.0015, 0.012), ink, bev=0, parent=None)
    z0.location = (0.026 * math.sin(math.radians(-120)), -0.0535, 0.036 + 0.026 * math.cos(math.radians(-120)))
    z0.rotation_euler = (0, math.radians(-120), 0)
'''

KIT = r'''
def shot4_props():
    # the same props from the shared kit
    hero = SK.crocus("dawn crocus", (0, 0, 0), yaw=0.6, scale=1.25, seed=61)
    T_W0, T_W1 = 0.6, DUR - 0.8
    droop = PK.wilt(hero, T_W0, T_W1, slots=(0,))
    follow(hero, lambda t: G - Vector((0, 0, 0.05)), 0.0, DUR, rot_fn=lambda t: (-droop(t), 0, 0.6))
    CK = Vector((-0.15, -0.36, 0.7))
    ac = PK.alarm_clock("alarm clock", r=0.075)
    ac["race"](0.2, DUR - 0.3, hours=5.0, start_h=5.0)
    follow(ac["root"], lambda t: CK, 0.0, DUR, rot_fn=lambda t: (0, ac["ring"](t), 0))
    PK.zero_mark("scale zero mark", (0, -0.0535, 0.036), 0.026, -120, PK._mat("scale ink", "#1C1B1E", rough=0.5))
'''


def snapshot():
    sc = bpy.context.scene; out = []
    for f in (1, 30, 61, 95):
        sc.frame_set(f); bpy.context.view_layer.update()
        for o in sorted(bpy.data.objects, key=lambda o: (o.type, tuple(round(v, 4) for v in o.matrix_world.translation), o.name)):
            if o.type not in ('MESH', 'EMPTY'): continue
            row = [f, o.type, [round(v, 4) for r in o.matrix_world for v in r], [round(v, 4) for v in o.dimensions]]
            if o.type == 'MESH':
                row.append(sorted(round(sum(m.diffuse_color[:3]), 3) for m in o.data.materials if m))
                sk = o.data.shape_keys
                row.append([round(k.value, 4) for k in sk.key_blocks] if sk else [])
            out.append(row)
        mixes = []
        for m in bpy.data.materials:
            if m.use_nodes:
                mixes.append(sorted(round(n.inputs["Factor"].default_value, 4) for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeMix" and n.data_type == 'RGBA' and n.blend_type == 'MIX' and n.inputs["B"].default_value[0] > 0.1))
        out.append([f, "mix", sorted(mixes)])
    return out


def build(code):
    sc = fresh()
    import scene_kit as K, saffron_kit as SK, prop_kit as PK
    from clock import FPS
    ns = dict(bpy=bpy, math=math, Vector=Vector, K=K, SK=SK, PK=PK, F=F, FPS=FPS, DUR=3.2, G=Vector((0.11, -0.34, 0.48)),
              ease=lambda u: (lambda v: v * v * (3 - 2 * v))(max(0.0, min(1.0, u))))
    exec(code, ns)
    if "follow" not in ns: exec(ORACLE.split("def shot4_props")[0], ns); exec(code, ns)
    ns["shot4_props"]()
    return snapshot()


a, b = build(ORACLE), build(KIT)
OUT["kit_rows"] = len(a)
OUT["kit_equivalent"] = a == b
if a != b:
    OUT["kit_first_diff"] = next(([x, y] for x, y in zip(a, b) if x != y), "length")
print("PROBE " + json.dumps(OUT, default=str))
