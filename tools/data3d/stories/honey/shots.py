"""THE HONEY SHORT (the eighth 3D short, 2026-11-23): almost half the honey Europe imports is suspected fake; one bee
makes a twelfth of a teaspoon in her life; one pound is 55,000 miles of flying, twice round the Earth; tomb honey
thousands of years old was still preserved; syrup is cheap, so the fakes keep coming. Made from scratch under the look
bible, the notes ledger and NOT SHOWN: every line's fact is a picture a stranger reads with the sound off.

  1 hook      market_stall   low      he slams his dipper on the cheap stall and five of eleven labels flip to SYRUP
  2 one bee   hive_yard      wide     one bee's whole life is one drop in a spoon marked in twelve rings
  3 55,000    honey_house    medium   a bee flies a gold trail twice round his globe as the counter rolls to 55,000
  4 forever   museum_tomb    high     tomb honey thousands of years old comes out perfect; the mummy wants a taste
  5 fakes     market_alley   tracking a fake jar turned over gushes out like water; his own honey does not budge

Run through the shot harness (store/shots.py, STORY=honey). Built as drafts (world.py + one file per beat) and inlined
here in story order by build.sh; the world's continuity builders come first (bee hat, honey dipper, jar)."""
import locations as LOC


# ====================================================================================================
# world.py
# ====================================================================================================
"""THE BEEKEEPER'S WORLD (the honey short): what persists from beat to beat because the STORY carries it
(script.json world.continuity) and the materials the village is made of.

  bee_hat(data)              his wide beekeeper's hat, veil rolled up round the crown, riding his head
  honey_dipper(name)         his wooden honey dipper (a turned handle and a grooved head)
  jar(name, ...)             a honey jar: glass, the honey in it, a lid, a label (front and a back face that can flip)
  worker_bee(name, s)        a honey bee: striped body, head, see-through wings that beat
  village_light(...)         one clear summer day: a warm sun, a blue sky, a soft key on him
"""
import random as hw_random
from mathutils import Matrix as HW_M, Quaternion as HW_Q, Euler
import bmesh as HW_bmesh


HW_U = K.U


def hw_link(o):
    bpy.context.collection.objects.link(o); return o


def hw_noise(name, a, b, scale=4.0, rough=0.8, bump=0.2, detail=6.0, stretch=(1, 1, 1), lo=0.35, hi=0.7):
    """two colours mixed by a noise with a bump from a finer one (any surface of the village)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = stretch
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = detail
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = lo; rp.color_ramp.elements[1].position = hi
    rp.color_ramp.elements[0].color = (*K.lin(a), 1); rp.color_ramp.elements[1].color = (*K.lin(b), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = scale * 10
    nt.links.new(mp.outputs["Vector"], fine.inputs["Vector"]); nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def hw_local(root):
    """scene_kit builds children at ABSOLUTE positions; these props are built in their own local frame, so every
    child's location is made relative to its parent (identity parent inverse), whatever the root's pose"""
    for o in root.children_recursive:
        o.matrix_parent_inverse.identity()
    return root


def hw_wood(name="hw wood", a="#7A5232", b="#9C7048", scale=3.0):
    return hw_noise(name, a, b, scale=scale, rough=0.7, bump=0.25, stretch=(1, 1, 8))


def hw_glass(name="hw jar glass"):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0.95, 0.97, 0.96, 1); bs.inputs["Roughness"].default_value = 0.04
    bs.inputs["Transmission Weight"].default_value = 1.0; bs.inputs["IOR"].default_value = 1.45
    return m


def hw_honey(name="hw honey", col="#D98A12", glow=0.0, clear=0.55):
    """real honey: a deep amber that glows where the light comes through it (subsurface + a little transmission)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(col), 1); bs.inputs["Roughness"].default_value = 0.08
    bs.inputs["Transmission Weight"].default_value = clear; bs.inputs["IOR"].default_value = 1.49
    try:
        bs.inputs["Subsurface Weight"].default_value = 0.3; bs.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.08)
    except KeyError: pass
    if glow:
        bs.inputs["Emission Color"].default_value = (*K.lin(col), 1); bs.inputs["Emission Strength"].default_value = glow
    return m


def hw_ink(name, hexc, emit=0.0):
    return K.mat(name, hexc, rough=0.5, emit=emit)


# ---------------------------------------------------------------- the bee hat (continuity: on his head in every beat)
HW_HAT_ZB = 0.815


def hw_head_z(x, y):
    q = 1 - (x / 0.186) ** 2 - (y / 0.138) ** 2
    return 0.705 + 0.172 * math.sqrt(q) if q > 0 else -1.0


def hw_hat_mesh(to_world, ears):
    """a beekeeper's hat built ON his head (his rest frame, facing -Y): a round domed crown, a wide flat brim with a
    soft droop at its rim, holes cut where his ears pass through; the veil is rolled up round the crown (bee_hat)"""
    from mathutils import Vector as V
    A = (0.146, 0.118); B = (0.27, 0.245); H = 0.1; n = 60
    verts, faces, mi, rows = [], [], [], []
    rhos = [0.0, 0.1, 0.22, 0.35, 0.48, 0.6, 0.72, 0.82, 0.9, 0.95, 0.985, 1.0]
    for rho in rhos:
        row = []
        for i in range(n if rho > 0 else 1):
            th = 2 * math.pi * i / n; x, y = A[0] * rho * math.cos(th), A[1] * rho * math.sin(th)
            z = max(HW_HAT_ZB + H * math.sqrt(max(0.0, 1 - rho ** 2.2)), hw_head_z(x, y) + 0.012)
            verts.append((x, y, z)); row.append(len(verts) - 1)
        rows.append(row)
    for k in range(10):
        u = (k + 1) / 10; row = []
        for i in range(n):
            th = 2 * math.pi * i / n
            verts.append(((A[0] + (B[0] - A[0]) * u) * math.cos(th), (A[1] + (B[1] - A[1]) * u) * math.sin(th), HW_HAT_ZB - 0.022 * u ** 2.2))
            row.append(len(verts) - 1)
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append((a[0], b[i], b[j]) if len(a) == 1 else (a[i], b[i], b[j], a[j])); mi.append(0)
    keep = []
    for f, m in zip(faces, mi):
        c = sum((V(verts[v]) for v in f), V()) / len(f); cw = to_world @ c; out = True
        for tr in ears:
            loc, nor, _i, d = tr.find_nearest(cw)
            if loc is not None and ((cw - loc).dot(nor) < 0 or d < 0.011): out = False
        if out: keep.append((f, m))
    used = sorted({v for f, _ in keep for v in f}); remap = {v: i for i, v in enumerate(used)}
    me = bpy.data.meshes.new("bee hat")
    me.from_pydata([tuple(V(verts[v]) - V((0, 0, HW_HAT_ZB))) for v in used], [], [tuple(remap[v] for v in f) for f, _ in keep]); me.update()
    me.materials.append(hw_noise("bee hat straw", "#E9DFC4", "#D8C9A2", scale=60, rough=0.75, bump=0.35))
    for p in me.polygons: p.use_smooth = True
    return me


def bee_hat(data, name="bee hat"):
    """HIS HAT: a pale straw beekeeper's hat, the black mesh veil rolled up in a fat roll round the crown, parented to
    his head bone. Call right after load_data() and data.place(), before any animation. Returns dict(worn, veil)."""
    from mathutils.bvhtree import BVHTree as BVH
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ears = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith("Ear") and o.parent == data.arm:
            ev = o.evaluated_get(dg); me = ev.to_mesh()
            ears.append(BVH.FromPolygons([o.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]))
            ev.to_mesh_clear()
    rest = HW_M.Translation(data.arm.location) @ HW_M.Rotation(data.arm.rotation_euler.z, 4, 'Z')
    me = hw_hat_mesh(rest, ears)
    worn = hw_link(bpy.data.objects.new(name, me))
    sd = worn.modifiers.new("straw", 'SOLIDIFY'); sd.thickness = 0.006; sd.offset = 1.0
    # the veil, rolled up: a fat dark mesh roll round the crown's base
    bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.022, major_segments=48, minor_segments=12, location=(0, 0, 0))
    veil = bpy.context.active_object; veil.name = name + " veil"; veil.scale = (1.0, 0.82, 0.9)
    vm = hw_noise("bee veil mesh", "#1E1E20", "#3A3A3E", scale=400, rough=0.9, bump=0.6)
    veil.data.materials.append(vm)
    for p in veil.data.polygons: p.use_smooth = True
    for o in (worn, veil):
        o.parent = data.arm; o.parent_type = 'BONE'; o.parent_bone = "head"
    bpy.context.view_layer.update()
    pbh = data.pb["head"]
    inv = (data.arm.matrix_world @ pbh.matrix @ HW_M.Translation((0, pbh.bone.length, 0))).inverted()
    worn.matrix_parent_inverse = inv; worn.matrix_basis = rest @ HW_M.Translation((0, 0, HW_HAT_ZB))
    veil.matrix_parent_inverse = inv; veil.matrix_basis = rest @ HW_M.Translation((0, 0.0, HW_HAT_ZB + 0.028)) @ HW_M.Diagonal((1.0, 0.82, 0.9, 1.0))
    return dict(worn=worn, veil=veil)


# ---------------------------------------------------------------- the honey dipper (continuity: in his hand)
def honey_dipper(name="honey dipper", L=0.2, r_head=0.022, honey=True):
    """a turned wooden honey dipper, built along +Z from its butt at the origin: a slim handle, a grooved head of
    stacked rings at the top end, honey clinging to the grooves. Returns dict(root, head_z)."""
    root = K.empty(name, (0, 0, 0))
    wood = hw_noise("dipper wood", "#B98A56", "#D2A672", scale=6, rough=0.55, bump=0.2, stretch=(1, 1, 6))
    K.cyl(name + " handle", (0, 0, L * 0.36), 0.0065, L * 0.72, wood, v=16, bev=0.002, parent=root)
    K.sph(name + " knob", (0, 0, 0.0), 0.009, wood, parent=root)
    z0 = L * 0.72
    for k in range(7):
        rr = r_head * (0.72 + 0.28 * math.sin(math.pi * (k + 0.5) / 7))
        K.cyl(name + " ring", (0, 0, z0 + 0.008 + k * 0.0105), rr, 0.0075, wood, v=24, bev=0.002, parent=root)
    K.cyl(name + " core", (0, 0, z0 + 0.04), r_head * 0.55, 0.08, wood, v=16, bev=0.001, parent=root)
    if honey:
        K.sph(name + " honey", (0, 0, z0 + 0.04), 1.0, hw_honey(), scale=(r_head * 0.95, r_head * 0.95, 0.04), parent=root)
    hw_local(root)
    return dict(root=root, head_z=z0 + 0.04)


# ---------------------------------------------------------------- a honey jar (continuity: his jar against the fakes)
def jar(name, loc=(0, 0, 0), r=0.04, h=0.1, fill=0.92, honey_col="#D98A12", label="PURE HONEY", label_col="#F3E9CF",
        ink="#5A3A12", back=None, back_col="#C8261E", back_ink="#FFFFFF", lid_col="#C9A04A", yaw=0.0, parent=None, glow=0.0):
    """a glass honey jar standing on its base at `loc`: glass, the honey in it (`fill` of the height), a gold lid, and a
    paper label on its front (-Y). back=<text>: a second label on its BACK, <text> in white on red; jar_flip() spins
    the jar round to show it. Returns dict(root, spin, glass, honey, label, back, r, h, hz)."""
    root = K.empty(name, loc, parent=parent); root.rotation_euler = (0, 0, yaw)
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    g = K.cyl(name + " glass", (0, 0, h / 2), r, h, hw_glass(), v=40, bev=0.006, parent=spin)
    hm = hw_honey(f"hw honey {honey_col} {glow}", honey_col, glow=glow)
    hz = h * fill
    hon = K.cyl(name + " honey", (0, 0, hz / 2 + 0.002), r * 0.93, hz - 0.004, hm, v=40, bev=0.004, parent=spin)
    K.cyl(name + " lid", (0, 0, h + 0.008), r * 1.02, 0.016, K.mat(f"jar lid {lid_col}", lid_col, rough=0.3, metal=0.85), v=40, bev=0.003, parent=spin)
    # the label: a flat card a hair in front of the glass (a cylinder's front reads flat at phone size)
    lw, lh = r * 1.75, h * 0.5
    front = K.box(name + " label", (0, -r - 0.003, h * 0.45), (lw, 0.0015, lh), K.mat(f"label {label_col}", label_col, rough=0.6), bev=0, parent=spin)
    K.text(name + " label text", label.replace(" ", "\n"), (0, -r - 0.0045, h * 0.45), lh * 0.27, (math.pi / 2, 0, 0), hw_ink(f"ink {ink}", ink), extrude=0.0004, parent=spin)
    out = dict(root=root, spin=spin, pivot=spin, glass=g, honey=hon, label=front, r=r, h=h, hz=hz)
    if back:
        bk = K.box(name + " label back", (0, r + 0.003, h * 0.45), (lw * 1.05, 0.0015, lh * 1.1), K.mat(f"label {back_col}", back_col, rough=0.5, emit=0.25), bev=0, parent=spin)
        K.text(name + " label back text", back, (0, r + 0.0045, h * 0.45), lh * 0.34, (math.pi / 2, 0, math.pi), hw_ink(f"ink {back_ink}", back_ink, emit=0.6), extrude=0.0004, parent=spin)
        out["back"] = bk
    hw_local(root)
    return out


def jar_flip(j, t0, dur=0.3):
    """the jar spins round on the spot (a half turn with a little overshoot): its red back label to the front"""
    p = j["spin"]
    for t, a in ((0.0, 0.0), (t0, 0.0), (t0 + dur * 0.75, math.radians(192)), (t0 + dur, math.radians(180))):
        p.rotation_euler = (0, 0, a); p.keyframe_insert("rotation_euler", frame=F(t))


# ---------------------------------------------------------------- a worker bee
def worker_bee(name, s=1.0):
    """a honey bee at the village's scale (a little big, so it reads on a phone): a striped amber-and-black abdomen, a
    fuzzy thorax, a dark head with two eyes, six thin legs, two pairs of clear wings. Built facing -Y at the origin.
    Returns dict(root, wings=[...])."""
    root = K.empty(name, (0, 0, 0))
    gold = hw_noise("bee gold fuzz", "#D9A21E", "#F0C24A", scale=80, rough=0.8, bump=0.5)
    black = hw_noise("bee black", "#16120E", "#2A221A", scale=80, rough=0.6, bump=0.3)
    for k in range(5):            # the striped abdomen, back to front
        y = 0.008 + k * 0.0085; rr = 0.0105 * math.sin(math.pi * (k + 0.8) / 5.6) + 0.003
        K.sph(name + " stripe", (0, y * s, 0), rr * s, gold if k % 2 == 0 else black, scale=(1, 0.75, 0.95), parent=root)
    K.sph(name + " sting", (0, 0.05 * s, 0), 0.0025 * s, black, parent=root)
    K.sph(name + " thorax", (0, -0.006 * s, 0.001 * s), 0.0095 * s, gold, parent=root)
    K.sph(name + " head", (0, -0.019 * s, 0.0), 0.0075 * s, black, scale=(1.1, 0.8, 1.0), parent=root)
    eye = K.mat("bee eye", "#0B0B0E", rough=0.15)
    for sg in (-1, 1):
        K.sph(name + " eye", (sg * 0.0055 * s, -0.021 * s, 0.002 * s), 0.003 * s, eye, parent=root)
        K.capsule(name + " antenna", Vector((sg * 0.002 * s, -0.025 * s, 0.004 * s)), Vector((sg * 0.006 * s, -0.033 * s, 0.012 * s)), 0.0006 * s, black, parent=root)
        for j in range(3):
            a = Vector((sg * 0.006 * s, (-0.009 + 0.006 * j) * s, -0.006 * s)); b = a + Vector((sg * 0.007 * s, 0.002 * j * s, -0.008 * s))
            K.capsule(name + " leg", a, b, 0.0009 * s, black, parent=root)
    wm = bpy.data.materials.get("bee wing")
    if not wm:
        wm = bpy.data.materials.new("bee wing"); wm.use_nodes = True; bs = wm.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = (0.9, 0.95, 1.0, 1); bs.inputs["Roughness"].default_value = 0.1
        bs.inputs["Alpha"].default_value = 0.35
        try: wm.blend_method = 'BLEND'
        except AttributeError: pass
    wings = []
    for sg in (-1, 1):
        for k, (ln, wd) in enumerate(((0.024, 0.009), (0.017, 0.006))):
            pv = K.empty(name + " wing pivot", (sg * 0.004 * s, (-0.006 + 0.006 * k) * s, 0.008 * s), parent=root)
            K.sph(name + " wing", (sg * ln * 0.5 * s, 0.004 * s, 0), 1.0, wm, scale=(ln * 0.5 * s, wd * 0.5 * s, 0.0005 * s), parent=pv)
            wings.append((pv, sg))
    hw_local(root)
    return dict(root=root, wings=wings)


def bee_buzz(b, t0, t1, hz=7.0, amp=55):
    """the wings beat (a blur of a beat at 30 fps: a few distinct angles, never a frozen pose)"""
    for f in range(max(1, F(t0)), F(t1) + 1):
        for k, (pv, sg) in enumerate(b["wings"]):
            a = math.radians(amp) * math.sin(2 * math.pi * hz * (f / FPS) + 0.8 * k)
            pv.rotation_euler = (0, -sg * a, 0); pv.keyframe_insert("rotation_euler", frame=f)


def key_path(o, fn, t0, t1, face=True):
    """key an object along fn(t) -> point, turning to face where it goes"""
    prev = None
    for f in range(max(1, F(t0)), F(t1) + 1):
        t = (f - 1) / FPS; p = Vector(fn(t)); o.location = p; o.keyframe_insert("location", frame=f)
        if face:
            q = Vector(fn(t + 1 / FPS)) - p
            if q.length > 1e-5:
                e = (-q).to_track_quat('Y', 'Z').to_euler()
                if prev: e.make_compatible(prev)
                o.rotation_euler = e; o.keyframe_insert("rotation_euler", frame=f); prev = e


# ---------------------------------------------------------------- one clear summer day
def village_light(sun_elev=42, sun_az=-40, sun=3.6, sky=0.32, warm=(1.0, 0.94, 0.84)):
    """the village's day: a warm high sun from camera-left-front, a clear blue sky, and the soft warm key that follows
    him so his face always reads (look bible: lit, friendly, readable)"""
    return LOC.sky_light(sun_elev=sun_elev, sun_az=sun_az, sun=sun, sky=sky, warm=warm, haze=1.2)


# ---------------------------------------------------------------- his body: layers, kicks and smooth hand paths
def hw_layer(data, bone, off, t0, t1):
    """ADD off(t) (degrees, x y z) on top of whatever already keys `bone`, every frame of t0..t1"""
    pb = data.pb[bone]
    base = {}
    for f in range(max(1, F(t0)), min(NF + 15, F(t1)) + 1):
        sc.frame_set(f); base[f] = tuple(math.degrees(v) for v in pb.rotation_euler)
    for f, b in base.items():
        o = off((f - 1) / FPS)
        data._k(bone, (f - 1) / FPS, rot=tuple(x + y for x, y in zip(b, o)))


def hw_kick(dt, tau=0.09):
    """a smooth one-way kick: up to 1 at tau, then dying away, never swinging back"""
    u = dt / tau
    return 0.0 if dt <= 0 else u * u * math.exp(2 * (1 - u))


def hw_win(t, a, d):
    return ease(min(1.0, max(0.0, (t - a) / d)))


def hw_spline(keys):
    """a smooth (Hermite) path through timed points [(t, point)], at rest at both ends"""
    ts = [k[0] for k in keys]; ps = [Vector(k[1]) for k in keys]; n = len(ps)
    assert all(a < b for a, b in zip(ts, ts[1:])), ts
    def vel(i):
        if i == 0 or i == n - 1: return Vector((0, 0, 0))
        return (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1])
    def fn(t):
        if t <= ts[0]: return ps[0].copy()
        for i in range(n - 1):
            if t <= ts[i + 1]:
                h = ts[i + 1] - ts[i]; u = (t - ts[i]) / max(1e-6, h)
                h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
                return ps[i] * h00 + vel(i) * (h10 * h) + ps[i + 1] * h01 + vel(i + 1) * (h11 * h)
        return ps[-1].copy()
    return fn


def hw_frame(data, sd):
    """his shoulder and its frame now: (shoulder, forward, out, up)"""
    bpy.context.view_layer.update()
    sh = acts._shoulder(data, sd); c = Vector(data.arm.location)
    yaw = data.arm.rotation_euler.z; fw = Vector((math.sin(yaw), -math.cos(yaw), 0))
    out = sh - c; out.z = 0; out = out - fw * out.dot(fw); out.normalize()
    return sh, fw, out, Vector((0, 0, 1))


def hw_rel(data, sd, t, world):
    """a world point as (forward, out, up) from his shoulder at time t (to key a hand ON a thing in the set)"""
    sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, sd)
    d = Vector(world) - sh
    return (d.dot(fw), d.dot(out), d.z)


def hw_hand(data, sd, keys):
    """a hand path keyed (t, (forward, out, up)) from his shoulder, followed wherever his body goes"""
    path = hw_spline(keys)
    def fn(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, sd)
        v = path(t)
        return sh + fw * v.x + out * v.y + Vector((0, 0, v.z))
    return fn


def hw_ride(obj, data, sd, back=0.04, along=(0, 1, 0), fore=False):
    """key a held prop on his hand every frame (after data.finish()): its butt in his fist, along the fingers, or
    (fore=True) on along his forearm's line, so a strike drives its head where his arm drives"""
    hb = "hand." + sd
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb[hb].matrix
        p = M.translation + (M.to_3x3() @ Vector((0, 0.05, 0)))
        ax = (M.to_3x3() @ Vector(along)).normalized()
        if fore:
            ax = (M.translation - data.arm.matrix_world @ data.pb["fore." + sd].head).normalized()
        obj.location = p - ax * back; obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(ax).to_euler()
        obj.keyframe_insert("location", frame=f); obj.keyframe_insert("rotation_euler", frame=f)


# ====================================================================================================
# shot1.py
# ====================================================================================================
"""BEAT 1, THE HOOK: the cheap stall in the market square. Eleven identical jars of PURE HONEY under a 2 EUROS sign;
the beekeeper slams his dipper on the counter, the row jumps, and only one of the seven labels flips over to a red SYRUP
(46% of the EU's imported samples: almost half)."""

S1_FAKES = (3,)                     # the one jar in seven the old test catches (0 = the one nearest the lens)
S1_N = 7
S1_CH = 0.3                          # the counter's top: his waist


def s1_awning(name, x0, x1, y0, y1, z_back, z_front, a, b, n=10, parent=None):
    """a striped canvas awning sloping down toward the front, its scalloped valance hanging off the front edge"""
    ca, cb = K.mat(f"awning {a}", a, rough=0.85), K.mat(f"awning {b}", b, rough=0.85)
    w = (x1 - x0) / n; L = math.hypot(y1 - y0, z_back - z_front); ang = math.atan2(z_back - z_front, y1 - y0)
    for k in range(n):
        o = K.box(name + " stripe", (x0 + w * (k + 0.5), (y0 + y1) / 2, (z_back + z_front) / 2), (w, L, 0.006), ca if k % 2 == 0 else cb, bev=0, parent=parent)
        o.rotation_euler = (ang, 0, 0)
        K.box(name + " valance", (x0 + w * (k + 0.5), y0 - 0.003, z_front - 0.05), (w, 0.004, 0.1), ca if k % 2 == 0 else cb, bev=0, parent=parent)
        K.sph(name + " scallop", (x0 + w * (k + 0.5), y0 - 0.003, z_front - 0.1), 1.0, ca if k % 2 == 0 else cb, scale=(w * 0.5, 0.002, 0.03), parent=parent)


def s1_crate(name, loc, size, fruit_col, wood, rnd, n=14, parent=None):
    x, y, z = loc; sx, sy, sz = size
    for dy in (-sy / 2, sy / 2):
        K.box(name + " slat", (x, y + dy, z + sz / 2), (sx, 0.012, sz), wood, bev=0.002, parent=parent)
    for dx in (-sx / 2, sx / 2):
        K.box(name + " end", (x + dx, y, z + sz / 2), (0.012, sy, sz), wood, bev=0.002, parent=parent)
    K.box(name + " base", (x, y, z + 0.006), (sx, sy, 0.012), wood, bev=0.001, parent=parent)
    fm = hw_noise(f"fruit {fruit_col}", fruit_col, K.mute(fruit_col, 0.75), scale=20, rough=0.45, bump=0.08)
    for i in range(n):
        r = rnd.uniform(0.022, 0.028)
        K.sph(name + " fruit", (x + rnd.uniform(-sx / 2 + r, sx / 2 - r), y + rnd.uniform(-sy / 2 + r, sy / 2 - r), z + sz - 0.01 + rnd.uniform(0, 0.02)), r, fm, seg=16, ring=10, parent=parent)


def s1_facade(name, x, y, w, h, wall, rnd, door=False, parent=None):
    """a village house front across the square: plaster, two rows of shuttered windows, a tiled roof edge"""
    K.box(name, (x, y, h / 2), (w, 0.2, h), wall, bev=0.01, parent=parent)
    shut = K.mat(rnd.choice(["shutter green", "shutter blue", "shutter red"]), rnd.choice(["#4E7A5A", "#4D6E8E", "#9A4A3A"]), rough=0.6)
    glass = K.mat("window dark", "#2A3036", rough=0.15)
    for row, z in enumerate((h * 0.42, h * 0.75)):
        for k in range(max(1, int(w / 0.7))):
            wx = x - w / 2 + (k + 0.5) * w / max(1, int(w / 0.7))
            if door and row == 0 and k == 0:
                K.box(name + " door", (wx, y - 0.105, 0.42), (0.34, 0.02, 0.84), K.mat("door wood", "#5C3A22", rough=0.6), bev=0.006, parent=parent); continue
            K.box(name + " window", (wx, y - 0.104, z), (0.22, 0.01, 0.34), glass, bev=0.004, parent=parent)
            for sg in (-1, 1):
                K.box(name + " shutter", (wx + sg * 0.17, y - 0.11, z), (0.11, 0.012, 0.36), shut, bev=0.004, parent=parent)
            K.box(name + " sill", (wx, y - 0.12, z - 0.19), (0.3, 0.05, 0.025), K.mat("sill stone", "#CFC4AE", rough=0.8), bev=0.004, parent=parent)
    K.box(name + " roof", (x, y - 0.05, h + 0.06), (w + 0.12, 0.34, 0.1), K.mat("roof tile", "#A4512E", rough=0.8), bev=0.01, parent=parent)


def place_market_stall():
    """THE VILLAGE SQUARE ON MARKET DAY: a cobbled square under a clear morning sky, the cheap stall's plank counter
    under a red-and-cream striped awning in front, more stalls (fruit, flowers, bread) behind it, the plastered house
    fronts of the square with green and blue shutters, and the village's people (faceless, minimal) at the far stalls."""
    rnd = hw_random.Random(11)
    cob = hw_noise("square cobbles", "#9C8E7A", "#B9AC94", scale=9, rough=0.9, bump=0.8, detail=3, lo=0.42, hi=0.58)
    K.box("square ground", (0, 6, -0.01), (40, 40, 0.02), cob, bev=0)
    wood = hw_wood("stall planks", "#8A6440", "#A47C52")
    old = hw_wood("crate wood", "#9A7A52", "#B89468", scale=4)
    # the cheap stall: a plank counter along X with a front skirt, two posts, the awning over it, a sign on top
    K.box("stall counter", (-0.04, -0.05, S1_CH - 0.02), (1.52, 0.4, 0.04), wood, bev=0.004)
    for k in range(9):
        K.box("counter skirt plank", (-0.8 + 0.083 + k * 0.167, -0.24, S1_CH / 2 - 0.02), (0.16, 0.015, S1_CH - 0.04), wood, bev=0.003)
    for x in (-0.78, 0.68):
        K.box("stall post", (x, 0.13, 0.55), (0.04, 0.04, 1.1), old, bev=0.004)
    s1_awning("stall awning", -0.9, 0.8, -0.2, 0.3, 1.12, 0.98, "#C23A2E", "#F1E6CC")
    sign = K.box("price sign", (-0.1, 0.12, 0.74), (0.9, 0.02, 0.2), K.mat("sign board", "#F4EEDC", rough=0.7), bev=0.006)
    K.text("price sign text", "PURE HONEY  2 EUROS", (-0.1, 0.108, 0.74), 0.075, (math.pi / 2, 0, 0), hw_ink("sign paint", "#B0261C"), extrude=0.001)
    for x in (-0.45, 0.25):
        K.cyl("sign string", (x, 0.12, 0.91), 0.0015, 0.14, K.mat("string", "#5A4A3A"), bev=0)
    # stock under and behind the counter: crates of the same cheap jars
    for k, x in enumerate((-0.55, -0.15, 0.25)):
        s1_crate(f"jar crate {k}", (x, 0.42, 0.0), (0.34, 0.26, 0.16), "#E0A030", old, rnd, n=8)
    # the square round him: the other stalls and the house fronts on the far side (behind him, down the lens) and
    # along the back (past the stall); the village's people at the far stalls
    def stall_at(k, x, y, rot, a, b, fruit):
        root = K.empty(f"stall {k}", (0, 0, 0))
        K.box(f"stall {k} counter", (0, 0, 0.36), (1.3, 0.45, 0.05), wood, bev=0.004, parent=root)
        K.box(f"stall {k} front", (0, -0.2, 0.18), (1.3, 0.02, 0.36), old, bev=0.003, parent=root)
        for px in (-0.62, 0.62):
            K.box(f"stall {k} post", (px, 0.18, 0.55), (0.04, 0.04, 1.1), old, bev=0.004, parent=root)
        for j in range(3):
            s1_crate(f"stall {k} crate {j}", (-0.4 + 0.4 * j, 0, 0.385), (0.34, 0.3, 0.1), fruit, old, rnd, parent=root)
        s1_awning(f"stall {k} awning", -0.72, 0.72, -0.3, 0.35, 1.1, 0.95, a, b, n=8, parent=root)
        root.location = (x, y, 0); root.rotation_euler = (0, 0, rot)
    for k, (x, y, rot, a, b, fruit) in enumerate(((2.6, -0.5, -math.pi / 2, "#3E6E9E", "#EEE7D6", "#C8352A"),
                                                   (2.7, 1.2, -math.pi / 2, "#3F7D4E", "#F2EAD8", "#E58A1F"),
                                                   (2.5, -2.2, -math.pi / 2, "#B8862E", "#F4EBD6", "#7FAE3A"),
                                                   (-1.6, 2.6, 0.0, "#8C3A5E", "#F1E5D8", "#D8C04A"),
                                                   (1.0, 2.8, 0.0, "#3E6E9E", "#F0E8D6", "#B23A6A"))):
        stall_at(k, x, y, rot, a, b, fruit)
    for k, (x, y, yaw) in enumerate(((3.3, -0.3, math.pi / 2), (3.4, 1.4, math.pi / 2 + 0.4), (3.2, -2.0, math.pi / 2 - 0.3),
                                      (1.8, 0.4, -math.pi / 2 + 0.5), (-1.4, 3.3, math.pi), (1.2, 3.4, math.pi + 0.3), (2.0, -1.3, 0.6))):
        person(f"shopper {k}", (x, y, 0), yaw=yaw)
    walls = [hw_noise(f"plaster {c}", c, K.mute(c, 0.85), scale=2, rough=0.85, bump=0.06) for c in ("#E9D9B8", "#E2C59A", "#EFE4CF", "#D9B48A")]
    for name, (x, y, rot) in (("houses east", (5.0, 0.0, -math.pi / 2)), ("houses north", (0.0, 4.8, 0.0))):
        root = K.empty(name, (0, 0, 0)); xx = -6.0
        while xx < 6.0:
            w = rnd.uniform(1.1, 1.7); h = rnd.uniform(1.7, 2.4)
            s1_facade(name, xx + w / 2, rnd.uniform(-0.1, 0.1), w, h, rnd.choice(walls), rnd, door=rnd.random() < 0.5, parent=root); xx += w + 0.02
        root.location = (x, y, 0); root.rotation_euler = (0, 0, rot)
    tw = K.empty("church", (0, 0, 0))
    K.box("church tower", (0, 0, 2.0), (0.9, 0.9, 4.0), walls[2], bev=0.02, parent=tw)
    K.cyl("church roof", (0, 0, 4.35), 0.62, 0.7, K.mat("roof tile", "#A4512E", rough=0.8), v=4, bev=0.01, parent=tw)
    K.cyl("church clock", (0, -0.46, 3.3), 0.2, 0.02, K.mat("clock face", "#F4EEDC", rough=0.4), rot=(math.pi / 2, 0, 0), v=32, bev=0.003, parent=tw)
    tw.location = (6.2, -1.6, 0); tw.rotation_euler = (0, 0, -math.pi / 2)
    # a stone fountain in the square between the stalls, and barrels, sacks, a cart by the near stalls
    stone = hw_noise("fountain stone", "#B8AE9C", "#D2C8B4", scale=6, rough=0.85, bump=0.4)
    K.cyl("fountain basin", (1.9, 1.9, 0.14), 0.5, 0.28, stone, v=48, bev=0.02)
    K.cyl("fountain water", (1.9, 1.9, 0.26), 0.45, 0.02, K.mat("fountain water", "#6FA3B8", rough=0.05), v=48, bev=0)
    K.cyl("fountain column", (1.9, 1.9, 0.5), 0.07, 0.6, stone, v=24, bev=0.01)
    K.cyl("fountain bowl", (1.9, 1.9, 0.82), 0.2, 0.06, stone, v=32, bev=0.01)
    for k, (x, y) in enumerate(((1.4, -0.9), (1.55, -1.15), (2.0, 0.55), (-1.2, 1.4))):
        K.cyl(f"barrel {k}", (x, y, 0.15), 0.12, 0.3, old, v=24, bev=0.01)
        for z in (0.05, 0.25):
            K.cyl(f"barrel {k} hoop", (x, y, z), 0.123, 0.02, K.mat("hoop iron", "#3A3632", rough=0.5, metal=0.6), v=24, bev=0)
    sack = hw_noise("sack", "#C9B48A", "#DCC9A0", scale=30, rough=0.95, bump=0.5)
    for k, (x, y) in enumerate(((1.2, -0.4), (1.3, -0.15), (1.35, 0.1))):
        K.sph(f"sack {k}", (x, y, 0.1), 0.11, sack, scale=(1.0, 0.8, 1.0))
    # bunting across the square
    flagm = [K.mat(f"bunting {c}", c, rough=0.7) for c in ("#C23A2E", "#E8B33A", "#3E6E9E", "#3F7D4E")]
    for k in range(40):
        fx = -4 + k * 0.2; fz = 2.0 - 0.25 * math.sin(math.pi * k / 39)
        fl = K.box("bunting", (fx, 4.4, fz), (0.1, 0.004, 0.12), flagm[k % 4], bev=0); fl.rotation_euler = (0, 0, 0)

    def light():
        return village_light(sun_elev=40, sun_az=-35, sun=3.8, sky=0.35)
    return light


def shot1():
    """THE CHEAP STALL. The lens low at the near end of the counter, the row of seven jars running away from it to
    the beekeeper at the far end: he peers along the jars, straightens and frowns up at the 2 EUROS sign, raises his
    dipper and SLAMS it on the counter; the row jumps, and one label flips to a red
    SYRUP; he jumps back, then leans in and points his dipper down the six others at us, not convinced."""
    T_PEER = 0.1                                  # leaning in along the row
    T_SIGN = 0.5                                 # straightening up to the sign
    T_UP = 0.8                                   # the dipper goes up ...
    T_SLAM = 0.3 * DUR                            # ... and down on the counter (arc 0.30)
    T_FLIP = [0.45 * DUR + k * (0.17 * DUR) / 4 for k in range(5)]   # arc 0.45 .. 0.62
    T_BACK = T_FLIP[0] - 0.05                     # he jerks back at the first red label
    T_LEAN = T_FLIP[-1] + 0.1                     # leans in down the row
    T_POINT = 0.82 * DUR                          # points along the red ones at us (arc 0.82)
    light = place_market_stall()
    data = load_data()
    P0 = Vector((0.8, -0.4, 0.0)); YAW = math.radians(-135)       # at the counter's far corner, three-quarter to the row
    data.place(P0.x, P0.y, math.degrees(YAW))
    CAM = Vector((-1.45, -0.6, 0.72)); LOOK = Vector((0.45, -0.08, 0.42))
    HIT = Vector((0.68, -0.25, S1_CH + 0.08))       # his fist just over the counter's corner: the dipper's head on the planks
    side = min("LR", key=lambda s: (acts._shoulder(data, s) - CAM).length)
    fw = data.forward(); out = acts._shoulder(data, side) - data.pos(); out.z = 0; out = (out - fw * out.dot(fw)).normalized()
    P0 = Vector((HIT.x, HIT.y, 0)) - fw * 0.15 - out * 0.15                   # the corner in front of his dipper hand, clear of his head
    data.place(P0.x, P0.y, math.degrees(YAW))
    hat = bee_hat(data)
    # the jars: eleven along the counter, each label turned to the lens; the fakes' labels are flaps with a red back
    jars = []
    for k in range(S1_N):
        x = -0.42 + k * 0.165
        a = math.atan2(CAM.y - (-0.12), CAM.x - x)            # the jar's label (its -Y face) turned to the lens
        fake = k in S1_FAKES
        jars.append(jar(f"stall jar {k}", (x, -0.12, S1_CH), r=0.046, h=0.15, fill=0.9, honey_col="#E6A52A" if fake else "#D98A12",
                        label="PURE HONEY", back="SYRUP" if fake else None, yaw=a + math.pi / 2))
    fakes = [jars[k] for k in S1_FAKES]
    jar_flip(fakes[0], T_FLIP[0])                 # only one in seven flips
    for k, j in enumerate(jars):                  # the row JUMPS at the slam, a hop running down from his end
        r = j["root"]; z0 = r.location.z; d = (S1_N - 1 - k) * 0.012; yw = r.rotation_euler.z; sg = 1 if k % 2 else -1
        for t, dz, tilt in ((0.0, 0, 0), (T_SLAM + d, 0, 0), (T_SLAM + d + 0.08, 0.04, 0.12 * sg), (T_SLAM + d + 0.17, 0.0, -0.05 * sg),
                            (T_SLAM + d + 0.26, 0.008, 0.02 * sg), (T_SLAM + d + 0.36, 0, 0)):
            r.location.z = z0 + dz; r.keyframe_insert("location", frame=F(t))
            r.rotation_euler = (tilt, 0, yw); r.keyframe_insert("rotation_euler", frame=F(t))
    # ---- his body: peer, straighten, rise for the swing, dip into the slam, jerk back, lean in to point
    W = hw_win
    def body(t):
        p = P0.copy()
        p += Vector((-0.05, 0.05, 0)) * (W(t, T_PEER, 0.4) - W(t, T_SIGN, 0.3))                 # a step into the row ...
        p.z += 0.025 * W(t, T_UP - 0.1, 0.3) * (1 - W(t, T_SLAM - 0.08, 0.1))                  # up on his toes with the dipper high
        p.z -= 0.03 * hw_kick(t - T_SLAM + 0.02, 0.1)                                            # the slam drives him down
        p += Vector((0.05, -0.05, 0)) * (W(t, T_BACK, 0.2) - W(t, T_LEAN, 0.4))                   # jerks back from the red label
        p += Vector((-0.02, 0.02, 0)) * W(t, T_LEAN, 0.4)                                        # and leans in down the row
        p.z += 0.03 * hw_kick(t - T_BACK, 0.12)                                                  # (a little hop of surprise)
        p += Vector((-0.035, 0.03, 0)) * W(t, T_FLIP[2] - 0.15, 0.25) * (1 - W(t, T_LEAN - 0.05, 0.3))   # a double take down the row
        yaw = YAW + math.radians(-18) * W(t, T_SIGN, 0.3) * (1 - W(t, T_SLAM - 0.3, 0.25)) \
            + math.radians(12) * W(t, T_BACK, 0.2) - math.radians(22) * W(t, T_POINT - 0.2, 0.4)   # ... and turns to us to point
        return p, yaw
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (16 * W(t, T_PEER, 0.4) * (1 - W(t, T_SIGN, 0.3)) - 8 * W(t, T_UP - 0.1, 0.3) * (1 - W(t, T_SLAM - 0.1, 0.1))
                                      + 12 * W(t, T_SLAM - 0.15, 0.15) * (1 - W(t, T_BACK, 0.2)) - 10 * W(t, T_BACK, 0.2) * (1 - W(t, T_LEAN, 0.3)) + 14 * W(t, T_FLIP[2] - 0.15, 0.25) * (1 - W(t, T_LEAN - 0.05, 0.3))
                                      + 14 * W(t, T_LEAN, 0.35) * (1 - W(t, T_POINT + 0.25, 0.35)), 0,
                                      6 * math.sin(2 * math.pi * (t - T_LEAN) / 1.2) * W(t, T_LEAN, 0.3)), 0, DUR + 0.4)
    hw_layer(data, "chest", lambda t: (8 * W(t, T_PEER, 0.4) * (1 - W(t, T_SIGN, 0.3)) + 4 * W(t, T_SLAM - 0.15, 0.15) * (1 - W(t, T_BACK, 0.2)), 0, 0), 0, DUR + 0.4)
    # ---- the dipper hand (the one on the lens side) and the free hand
    sc.frame_set(1); bpy.context.view_layer.update()
    free = "R" if side == "L" else "L"
    hit = hw_rel(data, side, T_SLAM, HIT)
    REST = (0.06, 0.07, -0.13)
    HK = [(0.0, REST), (T_PEER + 0.3, (0.1, 0.08, -0.09)), (T_SIGN + 0.15, (0.07, 0.13, -0.05)),
          (T_UP + 0.15, (0.02, 0.15, 0.07)), (T_SLAM - 0.28, (0.05, 0.15, 0.06)), (T_SLAM, hit),
          (T_SLAM + 0.2, (hit[0], hit[1], hit[2] + 0.03)), (T_BACK + 0.25, (0.12, 0.1, -0.02)),
          (T_LEAN + 0.35, (0.13, 0.09, -0.03)), (T_POINT, (0.14, 0.08, 0.02)), (T_POINT + 0.35, (0.14, 0.085, 0.045)), (DUR + 0.3, (0.14, 0.08, 0.03))]
    FK = [(0.0, (0.04, 0.07, -0.14)), (T_SIGN + 0.1, (0.04, 0.07, -0.14)), (T_BACK - 0.1, (0.05, 0.08, -0.13)), (T_BACK + 0.35, (0.1, 0.1, 0.04)),
          (T_LEAN + 0.2, (0.08, 0.12, 0.0)), (T_POINT, (0.03, 0.1, -0.1)), (DUR + 0.3, (0.03, 0.1, -0.11))]
    data.reach(side, hw_hand(data, side, HK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(free, hw_hand(data, free, FK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.3)
    # ---- face and head
    LENS = CAM
    data.look_at(jars[3]["root"].location + Vector((0, 0, 0.08)), 0.0, max_yaw=40, max_pitch=40, blend=0.0)
    data.look_at(Vector((-0.1, 0.11, 0.78)), T_SIGN, max_yaw=40, max_pitch=40, blend=0.18)            # the 2 EUROS sign
    data.look_at(HIT, T_SLAM - 0.3, max_yaw=40, max_pitch=22, blend=0.12)
    data.look_at(fakes[0]["root"].location + Vector((0, 0, 0.08)), T_FLIP[0], max_yaw=40, max_pitch=40, blend=0.12)
    data.look_at(jars[1]["root"].location + Vector((0, 0, 0.08)), T_FLIP[3], max_yaw=40, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_POINT - 0.1, max_yaw=45, blend=0.18)
    data.expression("worried", 0.0, T_SIGN - 0.02)
    data.expression("angry", T_SIGN + 0.05, T_BACK - 0.03, blend=0.12)
    data.expression("surprised", T_BACK, T_LEAN, blend=0.1)
    data.expression("wry", T_POINT - 0.15, DUR + 1.0, blend=0.18)
    data.finish()
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, side, fore=True)
    # ---- the lens: low at the counter's near end, the row big in front of us running to him; a slow push in
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=40, fstop=7.0)
    camera_path(cam, lambda t: (CAM + (LOOK - CAM).normalized() * 0.12 * ease(t / DUR), LOOK, Vector((0.3, -0.15, 0.5))))
    return dict(lanes=[], kiosks=[], place="market_stall", light=light, data=data, rest=1, grips=("honey dipper",),
                conseq=[("he slams his dipper and only one of the seven labels flips to a red SYRUP", lambda: meshes([j["root"] for j in jars]), T_FLIP[0], DUR, {"hero": True}),
                        ("the slam makes the whole row of jars jump", lambda: meshes([j["root"] for j in jars]), T_SLAM, T_SLAM + 0.5)])


# ====================================================================================================
# shot2.py
# ====================================================================================================
"""BEAT 3, A QUARTER OF THE PRICE: the yard outside his honey house. Two flagpoles beside a tall price board marked
in euros a kilo. Hand over hand he hoists the white RICE SYRUP flag: it stops at 0.50. Then he hoists the gold HONEY
flag and it climbs past 1.00, 1.50, 2.00 to 2.17, four times as high (DG SANTE: imported honey 2.17 EUR/kg in 2021,
rice syrup about 0.40-0.60 EUR/kg)."""

S3_Z0 = 0.3                            # the price board's zero (the flags start here)
S3_PER = 0.36                          # metres per euro: 2.17 is 0.78 m up
S3_POLES = (Vector((0.0, 0.2, 0.0)), Vector((0.4, 0.2, 0.0)))   # syrup pole, honey pole
S3_DATA = Vector((0.2, 0.13, 0.0))     # he stands between them


def place_honey_house():
    """THE YARD OUTSIDE HIS HONEY HOUSE: the honey house's weathered plank wall across the back with a sunny window full
    of his jars, its open door, a tin roof edge, his steel extractor and stacked hive boxes by the wall, frames leaning
    to dry, a flagstone path through the grass, the stump he uses as a table, flowers, and the hill behind."""
    rnd = hw_random.Random(33)
    grass = hw_noise("yard grass", "#5E8A32", "#94B850", scale=26, rough=0.95, bump=1.0, detail=8, lo=0.36, hi=0.66)
    K.box("yard ground", (0, 4, -0.01), (30, 30, 0.02), grass, bev=0)
    stone = hw_noise("flagstone", "#A79F90", "#C4BCAC", scale=9, rough=0.85, bump=0.7, detail=6)
    x = -2.2
    while x < 2.4:                                     # the flagstone path he rolls it along
        w = rnd.uniform(0.18, 0.28)
        for yy in (-0.12, 0.12):
            o = K.box("flagstone", (x + w / 2, yy + rnd.uniform(-0.02, 0.02), 0.006), (w - 0.025, 0.21, 0.016), stone, bev=0.006)
            o.rotation_euler = (0, 0, rnd.uniform(-0.08, 0.08))
        x += w
    blade = [K.mat(f"blade {c}", c, rough=0.8) for c in ("#5E8A2E", "#7AA23C", "#8DB24A")]
    petals = [K.mat(f"flower {c}", c, rough=0.6) for c in ("#F2D43A", "#F4F0E6", "#C96BC0", "#E0583A")]
    for k in range(260):
        x, y = rnd.uniform(-2.0, 2.2), rnd.uniform(-1.4, 0.9)
        if -0.3 < y < 0.3: continue
        for b in range(3):
            h = rnd.uniform(0.06, 0.13); a = rnd.uniform(0, 6.28); ln = rnd.uniform(0.1, 0.35)
            o = K.box("yard blade", (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), h / 2), (0.007, 0.002, h), rnd.choice(blade), bev=0)
            o.rotation_euler = (ln * math.sin(a), -ln * math.cos(a), a)
        if k % 3 == 0:
            K.sph("yard flower", (x, y, rnd.uniform(0.08, 0.14)), rnd.uniform(0.012, 0.018), rnd.choice(petals), seg=10, ring=6)
    # the honey house: a long plank wall across the back with a window, a door, a tin roof edge
    WY = 1.05
    plank = hw_noise("weathered planks", "#9C7A52", "#B8966A", scale=3, rough=0.85, bump=0.5, detail=6, stretch=(6, 1, 1))
    for k in range(34):
        xx = -2.6 + k * 0.155
        if 0.55 < xx < 0.95: continue                   # the open door
        K.box("house plank", (xx, WY + rnd.uniform(-0.006, 0.006), 0.85), (0.15, 0.04, 1.7), plank, bev=0.006)
    K.box("door frame top", (0.75, WY - 0.03, 1.32), (0.46, 0.06, 0.06), plank, bev=0.006)
    K.box("door dark", (0.75, WY + 0.1, 0.66), (0.42, 0.02, 1.3), K.mat("inside dark", "#2E241C", rough=0.9), bev=0)
    door = K.box("open door", (0.98, WY - 0.2, 0.65), (0.04, 0.42, 1.28), hw_wood("door wood", "#6E4A2A", "#8A5E36"), bev=0.006)
    tin = K.mat("roof tin", "#8E969C", rough=0.4, metal=0.7)
    for k in range(18):
        K.box("roof tin sheet", (-2.6 + 0.3 * k, WY - 0.1, 1.78), (0.29, 0.5, 0.012), tin, bev=0.002).rotation_euler = (-0.25, 0, 0)
    frame_m = K.mat("window frame", "#EEE8DA", rough=0.4)
    K.box("window frame", (-0.55, WY - 0.03, 1.0), (0.78, 0.04, 0.56), frame_m, bev=0.006)
    K.box("window inside", (-0.55, WY - 0.01, 1.0), (0.7, 0.02, 0.48), K.mat("window inside warm", "#4A3626", rough=0.9), bev=0)
    K.box("window sill", (-0.55, WY - 0.08, 0.71), (0.86, 0.12, 0.03), frame_m, bev=0.004)
    shelf = hw_wood("window shelf", "#7A5A38", "#946E46")
    for z in (0.78, 0.99):
        K.box("window shelf", (-0.55, WY - 0.03, z), (0.7, 0.08, 0.015), shelf, bev=0.002)
        for k in range(6):
            jar(f"window jar {z} {k}", (-0.85 + k * 0.12, WY - 0.04, z + 0.008), r=0.035, h=0.09, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY")
    K.box("window mullion", (-0.55, WY - 0.06, 1.0), (0.02, 0.01, 0.5), frame_m, bev=0)
    # by the wall: the extractor, a stack of hive boxes, frames leaning to dry
    steel = K.mat("extractor steel", "#C9CED4", rough=0.25, metal=0.85)
    K.cyl("extractor drum", (1.45, WY - 0.35, 0.36), 0.22, 0.52, steel, v=48, bev=0.01)
    K.cyl("extractor lid", (1.45, WY - 0.35, 0.64), 0.23, 0.03, steel, v=48, bev=0.006)
    K.box("extractor crank", (1.45, WY - 0.35, 0.72), (0.02, 0.2, 0.02), steel, bev=0.003)
    white = hw_noise("hive paint", "#F4F1E8", "#E2DED2", scale=8, rough=0.7, bump=0.15)
    for k in range(4):
        K.box("stacked hive box", (-1.45, WY - 0.3, 0.07 + 0.135 * k), (0.32, 0.28, 0.125), white, bev=0.004)
    comb = hw_noise("comb wax", "#E8B033", "#F2CC5E", scale=60, rough=0.5, bump=0.6)
    fw_m = hw_wood("frame wood", "#C8A878", "#D8BC8C", scale=6)
    for k in range(5):
        o = K.box("drying frame", (-1.05 + 0.07 * k, WY - 0.12, 0.2), (0.02, 0.3, 0.42), fw_m, bev=0.002); o.rotation_euler = (0.25, 0, 1.57)
        o = K.box("drying comb", (-1.05 + 0.07 * k, WY - 0.13, 0.2), (0.012, 0.26, 0.36), comb, bev=0.001); o.rotation_euler = (0.25, 0, 1.57)
    K.cyl("water butt", (2.1, WY - 0.3, 0.3), 0.2, 0.6, hw_wood("butt wood", "#7A5A38", "#946E46", scale=8), v=32, bev=0.01)
    # the hill behind the roof, with the hives on it
    hill = hw_noise("far hill", "#6F9A40", "#A2BD62", scale=9, rough=0.95, bump=0.5, detail=5)
    K.sph("far hill", (0, 9, -3.6), 6.0, hill, scale=(3.0, 1.0, 0.9))
    leaf = hw_noise("tree leaves", "#4E7E32", "#6E9C40", scale=10, rough=0.85, bump=0.4)
    for k, (xx, yy) in enumerate(((-2.4, 2.4), (2.6, 2.2), (0.2, 3.2), (-1.0, 3.6))):
        K.cyl("tree trunk", (xx, yy, 0.8), 0.08, 1.6, hw_wood("tree bark", "#5A4330", "#6E5440", scale=8), v=12, bev=0.01)
        for jj in range(5):
            K.sph("tree crown", (xx + rnd.uniform(-0.4, 0.4), yy + rnd.uniform(-0.2, 0.2), 1.9 + rnd.uniform(-0.2, 0.3)), rnd.uniform(0.45, 0.6), leaf, seg=20, ring=12)

    def light():
        return village_light(sun_elev=40, sun_az=-30, sun=4.2, sky=0.33)
    return light


def s3_pole(name, base, col, word, price, side):
    """a flagpole with its halyard, and a flag that rides up it on the side away from him (the flag's root moves)"""
    pole = K.mat("pole white", "#EDEAE2", rough=0.4)
    K.cyl(name + " pole", tuple(base + Vector((0, 0, 0.66))), 0.013, 1.32, pole, v=16, bev=0.003)
    K.sph(name + " finial", tuple(base + Vector((0, 0, 1.335))), 0.024, K.mat("finial gold", "#D2A23A", rough=0.3, metal=0.8))
    K.cyl(name + " foot", tuple(base + Vector((0, 0, 0.02))), 0.065, 0.04, hw_noise("pole stone", "#9A958A", "#B5AFA2", scale=10), v=24, bev=0.006)
    K.box(name + " pulley arm", tuple(base + Vector((-side * 0.03, -0.035, 1.29))), (0.05, 0.07, 0.012), pole, bev=0.003)
    flag = K.empty(name + " flag", (0, 0, 0))
    K.box(name + " cloth", (side * 0.125, -0.004, 0), (0.23, 0.006, 0.27), K.mat(f"flag {col}", col, rough=0.7), bev=0.004, parent=flag)
    ink = hw_ink(f"flag ink {name}", "#2A1E12" if col != "#F2B02A" else "#3A1E04")
    K.text(name + " word", word, (side * 0.125, -0.0085, 0.055), 0.03, (math.pi / 2, 0, 0), ink, extrude=0.0005, parent=flag)
    K.text(name + " price", price, (side * 0.125, -0.0085, -0.045), 0.066, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=flag)
    hw_local(flag)
    return flag


def shot2():
    """A QUARTER OF THE PRICE. Between two flagpoles and the price board: hand over hand he hoists the RICE SYRUP flag
    and it stops at 0.50; he hops round to the HONEY pole and hoists its gold flag past 1.00, 1.50, 2.00 to 2.17;
    he points up at it and spreads his hands at us."""
    T_S0, T_S1 = 0.05 * DUR, 0.34 * DUR             # the syrup flag up to 0.50, two pulls
    T_H0, T_H1 = 0.48 * DUR, 0.82 * DUR            # the honey flag up to 2.17, two pulls for each hand
    T_PT, T_SPREAD = 0.86 * DUR, 0.91 * DUR
    NS, NH = 2, 2
    light = place_honey_house()
    W = hw_win
    board = hw_wood("price board", "#F0E6CC", "#E2D6B8", scale=3)
    ink = hw_ink("board ink", "#2A1E12")
    bx = (S3_POLES[0].x + S3_POLES[1].x) / 2; by = S3_POLES[0].y + 0.07
    K.box("price board", (bx, by, S3_Z0 + 0.47), (0.36, 0.02, 0.98), board, bev=0.006)
    K.text("price board head", "EUROS A KILO", (bx, by - 0.012, S3_Z0 + 0.92), 0.026, (math.pi / 2, 0, 0), ink, extrude=0.0006)
    for k in range(0, 5):
        v = 0.5 * k; z = S3_Z0 + S3_PER * v
        K.box("board line", (bx, by - 0.011, z), (0.34, 0.002, 0.005 if k else 0.009), ink, bev=0)
        if k: K.text("board euro", f"{v:.2f}", (bx + 0.13, by - 0.012, z + 0.02), 0.028, (math.pi / 2, 0, 0), ink, extrude=0.0006)
    sf = s3_pole("syrup", S3_POLES[0], "#FAFAF4", "RICE SYRUP", "0.50", -1)
    hf = s3_pole("honey", S3_POLES[1], "#F2B02A", "HONEY", "2.17", 1)
    rope_m = K.mat("rope", "#8A6A3A", rough=0.9)
    rope_x = (S3_POLES[0].x + 0.025, S3_POLES[1].x - 0.025); rope_y = S3_DATA.y - 0.02
    for i in (0, 1):
        K.cyl(("syrup", "honey")[i] + " rope", (rope_x[i], rope_y, 0.78), 0.008, 1.0, rope_m, v=8, bev=0)
        K.box(("syrup", "honey")[i] + " cleat", (rope_x[i] + (0.02, -0.02)[i], S3_POLES[i].y, 0.25), (0.012, 0.012, 0.05), board, bev=0.002)
    flags = (sf, hf); tops = (S3_Z0 + S3_PER * 0.5, S3_Z0 + S3_PER * 2.17)
    def flag_z(i, t):
        (t0, t1), n = ((T_S0, T_S1), NS) if i == 0 else ((T_H0, T_H1), NH)
        u = max(0.0, min(1.0, (t - t0) / (t1 - t0))) * n
        k = min(int(u), n - 1); fr = u - k
        return S3_Z0 + (tops[i] - S3_Z0) * (k + ease(min(1.0, fr * 1.25))) / n
    # ---- him: between the poles, turned to the pole he is hoisting, his near hand hand over hand on its rope
    data = load_data()
    XS, XH, YW = S3_DATA.x - 0.025, S3_DATA.x + 0.025, 50.0          # beside each rope, turned to it
    data.place(XS, S3_DATA.y, -YW)
    hat = bee_hat(data)
    tug = lambda t, t0, t1, n: (math.sin(math.pi * n * max(0.0, min(1.0, (t - t0) / (t1 - t0))))) ** 2 * W(t, t0, 0.1) * (1 - W(t, t1 - 0.05, 0.1))
    T_TURN = (T_S1 + T_H0) / 2
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        u = W(t, T_S1 + 0.03, T_H0 - T_S1 - 0.13)
        yaw = -YW + 2 * YW * u - YW * W(t, T_PT, 0.4)
        x = XS + (XH - XS) * u
        z = (0.035 * tug(t, T_S0, T_S1, 2 * NS) + 0.035 * tug(t, T_H0, T_H1, 2 * NH)          # up on his toes as he hauls
             + 0.05 * hw_kick(t - (T_TURN - 0.15), 0.15) + 0.06 * hw_kick(t - T_SPREAD, 0.15))
        x += 0.03 * tug(t, T_S0, T_S1, 2 * NS) - 0.045 * tug(t, T_H0, T_H1, 2 * NH)      # heaving back from the pole
        data._kobj(t, loc=(x, S3_DATA.y, z), rot=math.radians(yaw))
    hw_layer(data, "spine", lambda t: (-14 * tug(t, T_S0, T_S1, 2 * NS) - 14 * tug(t, T_H0, T_H1, 2 * NH) - 6 * W(t, T_H1 - 0.1, 0.3) * (1 - W(t, T_SPREAD, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    rope_at = lambda i, z: Vector((rope_x[i], rope_y, z))
    def pulls(sd, i, t0, t1, n, ph):
        ks = []
        for k in range(n):
            a = t0 + (t1 - t0) * (k + ph) / n; b = t0 + (t1 - t0) * (k + ph + 0.5) / n
            if a >= t0 - 0.01: ks += [(a + 0.02, hw_rel(data, sd, a + 0.02, rope_at(i, 0.49)))]
            if b <= t1 + 0.01: ks += [(b, hw_rel(data, sd, b, rope_at(i, 0.38)))]
        return ks
    # both hands hand over hand on the rope he is hauling, one up while the other comes down
    lk = [(0.0, hw_rel(data, lf, 0.0, rope_at(0, 0.46)))] + pulls(lf, 0, T_S0, T_S1, NS, 0.0)
    rk = [(0.0, hw_rel(data, rt, 0.0, rope_at(0, 0.42)))] + pulls(rt, 0, T_S0, T_S1, NS, 0.5)
    lk += [(T_H0 + 0.02, hw_rel(data, lf, T_H0 + 0.02, rope_at(1, 0.42)))] + pulls(lf, 1, T_H0, T_H1, NH, 0.5)
    rk += [(T_H0 - 0.03, hw_rel(data, rt, T_H0 - 0.03, rope_at(1, 0.48)))] + pulls(rt, 1, T_H0, T_H1, NH, 0.0)
    lk += [(T_H1 + 0.4, (0.1, 0.12, -0.04)), (T_SPREAD, (0.1, 0.15, 0.02)), (DUR + 0.3, (0.1, 0.15, 0.03))]
    rk += [(T_H1 + 0.32, (0.13, 0.1, 0.03)), (T_SPREAD + 0.22, (0.1, 0.15, 0.02)), (DUR + 0.3, (0.1, 0.15, 0.03))]
    for ks in (rk, lk):
        ks.sort(key=lambda k: k[0])
        i = 1
        while i < len(ks):
            if ks[i][0] <= ks[i - 1][0] + 0.03: ks.pop(i)
            else: i += 1
    data.reach(rt, hw_hand(data, rt, rk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(lf, hw_hand(data, lf, lk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    LENS = Vector((0.2, -1.38, 0.7))
    data.look_at(Vector((S3_POLES[0].x - 0.15, 0.2, tops[0])), 0.0, max_yaw=45, max_pitch=30, blend=0.0)
    data.look_at(LENS, T_S1 - 0.05, max_yaw=45, blend=0.15)
    data.look_at(Vector((S3_POLES[1].x + 0.15, 0.2, 0.75)), T_H0 + 0.3, max_yaw=45, max_pitch=35, blend=0.2)
    data.look_at(LENS, T_H0 + 1.0, max_yaw=45, blend=0.2)
    data.look_at(Vector((S3_POLES[1].x + 0.15, 0.2, tops[1])), T_H1 - 0.35, max_yaw=45, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_SPREAD - 0.2, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_S1)
    data.expression("pleased", T_S1 + 0.05, T_H0 - 0.05, blend=0.15)
    data.expression("determined", T_H0, T_H1 - 0.05, blend=0.15)
    data.expression("surprised", T_H1, T_SPREAD - 0.1, blend=0.1)
    data.expression("wry", T_SPREAD, DUR + 1.0, blend=0.18)
    data.finish()
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for i in (0, 1):
            flags[i].location = (S3_POLES[i].x + (-0.013, 0.013)[i], S3_POLES[i].y - 0.01, flag_z(i, t)); flags[i].keyframe_insert("location", frame=f)
    cam = K.camera(tuple(LENS), (0.2, 0.15, 0.66), lens=32, fstop=8.0)
    camera_path(cam, lambda t: (LENS + Vector((0.0, 0.06, 0.03)) * ease(t / DUR), Vector((0.2, 0.15, 0.64 + 0.04 * ease(t / DUR))), Vector((0.2, 0.15, 0.66))))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("syrup rope", "honey rope"),
                conseq=[("the HONEY flag climbs to 2.17, the RICE SYRUP flag stopped at 0.50", lambda: meshes([sf, hf]) + meshes_of("price board", "board", "syrup pole", "honey pole"), T_S1, DUR, {"hero": True}),
                        ("he hoists the honey flag hand over hand", lambda: meshes([hf]), T_H0, T_H1, {"moves": True}),
                        ("the syrup flag stops at 0.50", lambda: meshes([sf]), T_S0, T_S1 + 0.5, {"moves": True})])


# ====================================================================================================
# shot3.py
# ====================================================================================================
"""BEAT 3, TUNED TO PASS: the cheap stall's back room. He dips his honey dipper in the blending vat and touches it to
the old grey TEST box: red FAIL. He turns the SYRUP wheel on the syrup drum down a notch and tests again: still red.
One more notch: green PASS, while the vat's gauge still reads mostly syrup (DG SANTE: fraudsters use "analyses in
accredited laboratories to adapt honey/sugar blends to elude possible detection")."""

S3_P0 = Vector((0.0, 0.0, 0.0))                 # him, square to the lens
S3_VAT = Vector((-0.3, -0.1, 0.0))            # the blending vat, front left of him
S3_VR, S3_VZ0, S3_VZ1 = 0.085, 0.12, 0.4       # its radius, its body's bottom and mouth
S3_BOX = Vector((-0.14, -0.28, 0.25))            # the TEST box on its crate, to his left
S3_DRUM = Vector((0.34, -0.14, 0.0))            # the RICE SYRUP drum, front right of him
S3_DH = 0.5                                     # its height
S3_WHEEL = Vector((S3_DRUM.x - 0.112, S3_DRUM.y - 0.01, 0.44))   # the SYRUP valve wheel on its side, facing him
S3_SYRUP = (0.86, 0.79, 0.72)                   # the gauge's syrup share after each notch: still mostly syrup


def place_back_room():
    """THE CHEAP STALL'S BACK ROOM: rough plank floor and walls, a dusty window with the sun through it, sacks stamped
    SYRUP stacked by the wall, the steel blending vat on its stand fed by a pipe from a syrup drum, an old grey TEST box
    on a crate, a bare bulb."""
    rnd = hw_random.Random(31)
    floor = hw_wood("back room floor", "#5A4030", "#735440", scale=5)
    K.box("back room floor", (0, 0.4, -0.01), (6, 6, 0.02), floor, bev=0)
    for k in range(-14, 15):
        K.box("floor seam", (k * 0.16, 0.4, 0.0006), (0.006, 6, 0.0012), K.mat("seam dark", "#2E2018", rough=0.95), bev=0)
    wall = hw_wood("back room wall", "#6E5038", "#8A6848", scale=3)
    K.box("back wall", (0, 0.75, 1.0), (4, 0.05, 2.0), wall, bev=0)
    for k in range(-12, 13):
        K.box("wall plank", (k * 0.17, 0.72, 1.0), (0.008, 0.01, 2.0), K.mat("plank gap", "#3A281C", rough=0.95), bev=0)
    K.box("side wall", (-1.3, 0.0, 1.0), (0.05, 2.0, 2.0), wall, bev=0)
    # the window: a frame, dusty glass, the sun through it
    fr = K.mat("window frame", "#D8CFC0", rough=0.6)
    K.box("window glass", (0.55, 0.725, 1.05), (0.5, 0.01, 0.42), K.mat("dusty glass", "#F4E7C4", rough=0.4, emit=1.2), bev=0)
    for dx, dz, sx, sz in ((0, 0.22, 0.56, 0.04), (0, -0.22, 0.56, 0.04), (-0.27, 0, 0.04, 0.46), (0.27, 0, 0.04, 0.46), (0, 0, 0.025, 0.42), (0, 0, 0.5, 0.025)):
        K.box("window frame", (0.55 + dx, 0.715, 1.05 + dz), (sx, 0.03, sz), fr, bev=0.003)
    # sacks of SYRUP along the back wall, stencilled
    sack = hw_noise("syrup sack", "#C9B48A", "#DCC9A0", scale=14, rough=0.95, bump=0.5)
    ink = hw_ink("sack ink", "#7A2A18")
    for k in range(5):
        x = -0.95 + k * 0.24 + rnd.uniform(-0.02, 0.02); z = 0.13
        K.sph(f"syrup sack {k}", (x, 0.58, z), 1.0, sack, scale=(0.12, 0.09, 0.14), seg=20, ring=12)
        K.text("sack word", "SYRUP", (x, 0.49, z + 0.02), 0.035, (math.pi / 2, 0, 0), ink, extrude=0.0004)
    for k in range(3):
        x = -0.85 + k * 0.26
        K.sph(f"syrup sack top {k}", (x, 0.6, 0.36), 1.0, sack, scale=(0.12, 0.09, 0.12), seg=20, ring=12)
    # the syrup drum on the right, its SYRUP valve wheel, a hose across the floor to the vat
    steel = K.mat("vat steel", "#B8BCC0", rough=0.25, metal=0.9)
    drum = K.mat("syrup drum", "#2E5E8A", rough=0.45, metal=0.3)
    K.cyl("syrup drum", (S3_DRUM.x, S3_DRUM.y, S3_DH / 2), 0.11, S3_DH, drum, v=40, bev=0.01)
    for z in (0.08, S3_DH - 0.08):
        K.cyl("drum hoop", (S3_DRUM.x, S3_DRUM.y, z), 0.113, 0.018, steel, v=40, bev=0.003)
    K.cyl("drum valve", (S3_WHEEL.x + 0.012, S3_WHEEL.y, S3_WHEEL.z), 0.012, 0.03, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.002)
    K.text("drum word", "RICE\nSYRUP", (S3_DRUM.x, S3_DRUM.y - 0.113, 0.3), 0.032, (math.pi / 2, 0, 0), hw_ink("drum ink", "#F2EEE4"), extrude=0.0005)
    # the hose from the drum's foot along the floor into the vat's foot
    hose = K.mat("hose black", "#1E1E1E", rough=0.6)
    a, b = Vector((S3_DRUM.x - 0.08, S3_DRUM.y - 0.08, 0.03)), Vector((S3_VAT.x + 0.06, S3_VAT.y - 0.08, 0.03))
    mid = Vector(((a.x + b.x) / 2, min(a.y, b.y) - 0.1, 0.03))
    for p, q in ((a, mid), (mid, b)):
        d = q - p
        K.cyl("syrup hose", tuple((p + q) / 2), 0.014, d.length, hose, rot=tuple(Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()), v=12, bev=0)
    # the vat on its stand, with its gauge on the front: HONEY at the bottom, SYRUP at the top
    K.cyl("vat", (S3_VAT.x, S3_VAT.y, (S3_VZ0 + S3_VZ1) / 2), S3_VR, S3_VZ1 - S3_VZ0, steel, v=48, bev=0.006)
    K.cyl("vat rim", (S3_VAT.x, S3_VAT.y, S3_VZ1), S3_VR + 0.006, 0.012, steel, v=48, bev=0.003)
    K.cyl("vat blend", (S3_VAT.x, S3_VAT.y, S3_VZ1 - 0.02), S3_VR - 0.004, 0.01, hw_honey("vat blend", "#E8C070", clear=0.2), v=48, bev=0)
    for a in (0.6, 2.4, 4.2):
        K.box("vat leg", (S3_VAT.x + 0.07 * math.cos(a), S3_VAT.y + 0.07 * math.sin(a), S3_VZ0 / 2), (0.02, 0.02, S3_VZ0), steel, bev=0.003)
    K.box("gauge back", (S3_VAT.x, S3_VAT.y - S3_VR - 0.006, 0.26), (0.075, 0.006, 0.25), K.mat("gauge plate", "#F2EEE4", rough=0.5), bev=0.002)
    gi = hw_ink("gauge ink", "#2A1E12")
    K.text("gauge word", "SYRUP", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.365), 0.018, (math.pi / 2, 0, 0), gi, extrude=0.0003)
    K.text("gauge word", "HONEY", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.155), 0.018, (math.pi / 2, 0, 0), gi, extrude=0.0003)
    # the old TEST box on its crate: a grey case, a red and a green lamp, a little screen
    crate = hw_wood("crate wood", "#9C7048", "#B88A5C", scale=6)
    K.box("test crate", (S3_BOX.x, S3_BOX.y, S3_BOX.z / 2 - 0.005), (0.24, 0.16, S3_BOX.z - 0.01), crate, bev=0.006)
    case = K.mat("test case", "#8A8F94", rough=0.5, metal=0.3)
    K.box("test box", (S3_BOX.x, S3_BOX.y, S3_BOX.z + 0.07), (0.22, 0.13, 0.14), case, bev=0.012)
    K.text("test word", "TEST", (S3_BOX.x, S3_BOX.y - 0.067, S3_BOX.z + 0.12), 0.026, (math.pi / 2, 0, 0), hw_ink("test ink", "#1E2226"), extrude=0.0004)
    K.box("test screen", (S3_BOX.x + 0.035, S3_BOX.y - 0.066, S3_BOX.z + 0.06), (0.11, 0.004, 0.05), K.mat("screen dark", "#1A1E22", rough=0.3), bev=0.002)
    K.box("test probe plate", (S3_BOX.x - 0.05, S3_BOX.y + 0.035, S3_BOX.z + 0.142), (0.05, 0.05, 0.006), steel, bev=0.002)
    # a bare bulb on its flex
    K.cyl("bulb flex", (-0.1, 0.1, 1.55), 0.004, 0.5, K.mat("flex", "#1E1E1E"), v=8, bev=0)
    K.sph("bulb", (-0.1, 0.1, 1.28), 0.035, K.mat("bulb glow", "#FFE2A8", emit=6.0))

    def light():
        sc_ = bpy.context.scene; w = sc_.world or bpy.data.worlds.new("World"); sc_.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (1.0, 0.86, 0.66, 1); bg.inputs["Strength"].default_value = 0.3
        LOC._area("window sun", (0.6, 1.4, 1.6), 0.8, 90, (1.0, 0.88, 0.66), aim=(0.0, 0.0, 0.3))
        LOC._area("room fill", (0.4, -1.6, 1.8), 2.4, 55, (1.0, 0.92, 0.8), aim=(-0.1, 0.0, 0.4))
        LOC._area("bulb pool", (-0.1, 0.05, 1.2), 0.5, 24, (1.0, 0.85, 0.6), aim=(-0.1, -0.05, 0.3))
        return LOC._hero_key()
    return light


def s3_wheel(name, at):
    """the SYRUP valve wheel facing the lens, spinning about the pipe's +Y: a red rim, four spokes, a knob on the rim"""
    root = K.empty(name, tuple(at))
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    red = K.mat("wheel red", "#C8261E", rough=0.4, metal=0.2)
    K.cyl(name + " rim", (0, 0, 0), 0.085, 0.014, red, v=40, bev=0.004, parent=spin)
    K.cyl(name + " hub", (0, 0, -0.01), 0.014, 0.03, red, v=16, bev=0.002, parent=spin)
    for a in (0, math.pi / 2):
        K.box(name + " spoke", (0, 0, 0.0), (0.16 * abs(math.cos(a)) + 0.014, 0.16 * abs(math.sin(a)) + 0.014, 0.014), red, bev=0.002, parent=spin)
    K.cyl(name + " knob", (0.07, 0, 0.035), 0.009, 0.06, K.mat("knob black", "#1E1E1E", rough=0.4), v=12, bev=0.002, parent=spin)
    K.text(name + " word", "SYRUP", (0, 0.0, 0.0072), 0.022, (0, 0, 0), hw_ink("wheel ink", "#FFFFFF"), extrude=0.0003, parent=spin)
    hw_local(root)
    root.rotation_euler = (0, -math.pi / 2, 0)            # its face and knob to -X, to him
    return root, spin


def shot3():
    """TUNED TO PASS. The lens high and to his right: he dips his dipper in the vat and touches it to the TEST box (red
    FAIL), cranks the SYRUP wheel down a notch (the gauge drops), tests again (still red), one more notch, tests (green
    PASS) while the gauge still reads mostly syrup; he turns and gapes at us."""
    W = hw_win
    T_D = [0.04 * DUR, 0.38 * DUR, 0.64 * DUR]           # dips
    T_T = [t + 0.22 * DUR * 0.55 for t in T_D]           # tests (arc 0.10 / 0.50 / 0.78)
    T_T = [0.17 * DUR, 0.5 * DUR, 0.77 * DUR]
    T_D = [t - 0.55 for t in T_T]
    T_C = [0.27 * DUR, 0.6 * DUR]                        # cranks of the SYRUP wheel (arc 0.35 / 0.65 end)
    CR = 0.6                                            # a crank's length
    T_GAPE = 0.88 * DUR
    light = place_back_room()
    wheel, wspin = s3_wheel("syrup wheel", S3_WHEEL)
    # the gauge: a glass tube, the honey part at the bottom and the syrup above it, the line between them dropping
    tube_m = hw_glass("gauge glass")
    K.cyl("gauge tube", (S3_VAT.x, S3_VAT.y - S3_VR - 0.016, 0.26), 0.012, 0.185, tube_m, v=16, bev=0.002)
    hon = K.cyl("gauge honey", (0, 0, 0), 0.0095, 1.0, hw_honey("gauge honey", "#C87810", glow=0.4), v=16, bev=0)
    syr = K.cyl("gauge syrup", (0, 0, 0), 0.0095, 1.0, K.mat("gauge syrup", "#F6F0DA", rough=0.3, emit=0.3), v=16, bev=0)
    G0, G1 = 0.172, 0.348
    def share(t):
        s = S3_SYRUP[0]
        for k, tc in enumerate(T_C):
            s += (S3_SYRUP[k + 1] - S3_SYRUP[k]) * ease(max(0.0, min(1.0, (t - tc) / CR)))
        return s
    # the TEST box's lamps and words: dark, then lit
    red_on = K.sph("lamp red", (S3_BOX.x - 0.07, S3_BOX.y - 0.066, S3_BOX.z + 0.06), 0.02, K.mat("lamp red glow", "#FF2A1E", emit=8.0))
    grn_on = K.sph("lamp green", (S3_BOX.x - 0.03, S3_BOX.y - 0.066, S3_BOX.z + 0.06), 0.02, K.mat("lamp green glow", "#2AFF5A", emit=8.0))
    for nm, x in (("lamp red off", -0.07), ("lamp green off", -0.03)):
        K.sph(nm, (S3_BOX.x + x, S3_BOX.y - 0.062, S3_BOX.z + 0.06), 0.019, K.mat("lamp off", "#3A3A3A", rough=0.3))
    fail = K.text("screen fail", "FAIL", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.05), 0.03, (math.pi / 2, 0, 0), hw_ink("fail ink", "#FF3A2A", emit=4.0), extrude=0.0004)
    ok = K.text("screen pass", "PASS", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.05), 0.03, (math.pi / 2, 0, 0), hw_ink("pass ink", "#3AFF6A", emit=4.0), extrude=0.0004)
    def lit(o, spans):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = any(a <= t < b for a, b in spans)
            s = 1.0 if on else 1e-3
            o.scale = (s, s, s); o.keyframe_insert("scale", frame=f)
    lit(red_on, [(T_T[0], T_C[0] - 0.1), (T_T[1], T_C[1] - 0.1)]); lit(fail, [(T_T[0], T_C[0] - 0.1), (T_T[1], T_C[1] - 0.1)])
    lit(grn_on, [(T_T[2], DUR + 1)]); lit(ok, [(T_T[2], DUR + 1)])
    # ---- him: square to the lens between the vat and the wheel, turning to each job
    data = load_data()
    data.place(S3_P0.x, S3_P0.y, 0.0)
    hat = bee_hat(data)
    def yaw(t):
        y = 0.0
        for td, tt in zip(T_D, T_T):
            y += -38 * (W(t, td - 0.62, 0.35) if td > 0.5 else 1.0) * (1 - W(t, td + 0.2, 0.35))            # to the vat and the box
        for tc in T_C:
            y += 12 * W(t, tc - 0.25, 0.25) * (1 - W(t, tc + CR, 0.25))            # to the wheel
        y += 0.0
        return math.radians(y)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        z = sum(0.04 * hw_kick(t - tt - 0.1, 0.16) for tt in T_T[:2]) - sum(0.035 * math.sin(math.pi * max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C[:1]) + 0.06 * hw_kick(t - T_T[2] - 0.05, 0.15) + 0.04 * hw_kick(t - T_GAPE, 0.14)
        lean = sum(0.035 * W(t, tc - 0.3, 0.25) * (1 - W(t, tc + CR - 0.3, 0.25)) for tc in T_C[:1])
        data._kobj(t, loc=(S3_P0.x + lean, S3_P0.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (sum(6 * W(t, td - 0.1, 0.25) * (1 - W(t, td + 0.3, 0.25)) for td in T_D)
                                      + sum(8 * W(t, tc - 0.15, 0.2) * (1 - W(t, tc + CR, 0.2)) for tc in T_C)
                                      - 8 * W(t, T_T[2] + 0.05, 0.2) * (1 - W(t, T_GAPE - 0.1, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):           # his fist where the dipper's head reaches `world`
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    MOUTH = Vector((S3_VAT.x + 0.02, S3_VAT.y + 0.01, S3_VZ1 - 0.02))
    PLATE = Vector((S3_BOX.x - 0.05, S3_BOX.y + 0.035, S3_BOX.z + 0.15))
    # the dipper hand (his left): dip, lift, over to the box's plate, back up
    dk = [(0.0, short(lf, 0.0, MOUTH + Vector((0, 0, 0.09)), by=0.15))]
    for td, tt in zip(T_D, T_T):
        dk += [(td - 0.2, short(lf, td - 0.2, MOUTH + Vector((0, 0, 0.07)), by=0.15)), (td, short(lf, td, MOUTH + Vector((0, 0, 0.02)), by=0.15)), (td + 0.28, short(lf, td + 0.28, (MOUTH + PLATE) / 2 + Vector((-0.02, 0.02, 0.04)), by=0.15)),
               (tt - 0.05, short(lf, tt - 0.05, PLATE + Vector((0, 0, 0.05)), by=0.1)), (tt + 0.1, short(lf, tt + 0.1, PLATE + Vector((0, 0, 0.02)), by=0.09)), (tt + 0.35, (0.14, 0.1, -0.06))]
    dk += [(T_GAPE, (0.1, 0.15, 0.02)), (DUR + 0.3, (0.1, 0.15, 0.035))]
    # the wheel hand (his right): on the knob through each crank, the knob going round with the wheel
    def knob(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return wspin.matrix_world @ Vector((0.07, 0, 0.075))
    def wheel_turn(t):
        return math.radians(-140) + sum(math.radians(50) * ease(max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        wspin.rotation_euler = (0, 0, wheel_turn(t)); wspin.keyframe_insert("rotation_euler", frame=f)
    wk = [(0.0, (0.03, 0.08, -0.12)), (T_C[0] - 0.7, (0.03, 0.09, -0.11))]
    for tc in T_C:
        wk += [(tc - 0.12, hw_rel(data, rt, tc - 0.12, knob(tc - 0.12)))]
        wk += [(tc + CR * u, hw_rel(data, rt, tc + CR * u, knob(tc + CR * u))) for u in (0.35, 0.7, 1.0)]
        wk += [(tc + CR + 0.3, (0.03, 0.1, -0.1))]
    wk += [(T_GAPE, (0.05, 0.16, 0.04)), (DUR + 0.3, (0.05, 0.16, 0.05))]
    for ks in (dk, wk):
        ks.sort(key=lambda k: k[0])
        i = 1
        while i < len(ks):
            if ks[i][0] <= ks[i - 1][0] + 0.04: ks.pop(i)
            else: i += 1
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.09, back=None, elbow_out=0.5)
    data.reach(rt, hw_hand(data, rt, wk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.3)
    CAM = Vector((-0.3, -1.45, 0.9)); LOOK = Vector((0.0, -0.1, 0.42))
    data.look_at(MOUTH, 0.0, max_yaw=45, max_pitch=18, blend=0.0)
    for td, tt in zip(T_D, T_T):
        data.look_at(MOUTH, td - 0.25, max_yaw=45, max_pitch=18, blend=0.15)
        data.look_at(PLATE, tt - 0.25, max_yaw=50, max_pitch=18, blend=0.15)
        data.look_at(CAM, tt + 0.3, max_yaw=45, blend=0.15)
    for tc in T_C:
        data.look_at(S3_WHEEL, tc - 0.2, max_yaw=45, max_pitch=15, blend=0.15)
        data.look_at(Vector(S3_VAT) + Vector((0, -S3_VR, 0.3)), tc + 0.35, max_yaw=45, max_pitch=15, blend=0.15)    # the gauge
    data.look_at(CAM, T_GAPE - 0.25, max_yaw=45, blend=0.15)
    data.expression("determined", 0.0, T_T[0])
    data.expression("angry", T_T[0] + 0.05, T_C[0] + 0.2, blend=0.12)
    data.expression("wry", T_C[0] + 0.25, T_T[1], blend=0.15)
    data.expression("worried", T_T[1] + 0.05, T_C[1] + 0.2, blend=0.12)
    data.expression("determined", T_C[1] + 0.25, T_T[2], blend=0.15)
    data.expression("surprised", T_T[2] + 0.05, DUR + 1.0, blend=0.1)
    data.finish()
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, lf, fore=True)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; s = share(t)
        zl = G0 + (G1 - G0) * (1 - s)
        gy = S3_VAT.y - S3_VR - 0.016
        hon.location = (S3_VAT.x, gy, (G0 + zl) / 2); hon.scale = (1, 1, max(1e-3, zl - G0))
        syr.location = (S3_VAT.x, gy, (zl + G1) / 2); syr.scale = (1, 1, max(1e-3, G1 - zl))
        for o in (hon, syr):
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((0.04, 0.1, -0.06)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.0)) * ease(t / DUR), Vector((S3_BOX.x, S3_BOX.y, S3_BOX.z + 0.08))))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="back_room", light=light, data=data, rest=1, grips=("honey dipper", "syrup wheel", "test probe plate", "vat blend"),
                conseq=[("the old TEST box turns green PASS while the gauge still reads mostly syrup", lambda: meshes_of("test box", "test crate", "lamp", "screen", "gauge", "vat"), T_T[2], DUR, {"hero": True}),
                        ("he turns the SYRUP wheel on the drum down a notch and the gauge drops", lambda: meshes([wheel]) + meshes_of("syrup drum", "drum", "gauge honey", "gauge syrup"), T_C[0], T_C[0] + CR, {"moves": True}),
                        ("the TEST box flashes red FAIL", lambda: meshes_of("lamp red", "screen fail", "test box", "test crate"), T_T[0], T_C[0] - 0.1)])


# ====================================================================================================
# shot4.py
# ====================================================================================================
"""BEAT 4, THE SHARPER TEST: the village hall, where the EU's inspectors have set up their new test machine. He walks
up with the blend that passed in the back room, dips his honey dipper in it and lets one drop fall into the machine's
funnel; the big dial swings hard from PASS into FAKE, its screen lights RICE SYRUP FOUND and the beacon spins red; he jumps back and points at it
(DG SANTE: "a different set of methods with improved detection capability was used")."""

S4_M = Vector((-0.05, 0.14, 0.0))               # the machine's foot (its front face at y = S4_M.y - 0.14)
S4_MH = 0.8                                     # its height
S4_DIAL = Vector((S4_M.x, S4_M.y - 0.145, 0.55))   # the dial's centre on its front
S4_FUN = Vector((0.28, -0.15, 0.44))             # the funnel's mouth on its side bracket
S4_P = Vector((0.52, 0.0, 0.0))                  # where he stands
S4_JAR = Vector((0.38, -0.27, 0.0))             # the jar of the tuned blend on its stool
S4_STOOL = 0.3


def place_village_hall():
    """THE VILLAGE HALL: a parquet floor, cream walls over a wooden wainscot, tall windows full of sun, bunting from
    the summer fete strung across, rows of folding chairs, a VILLAGE HALL board over the stage at the back."""
    rnd = hw_random.Random(57)
    par = hw_wood("parquet", "#9C6A3E", "#B8844E", scale=7)
    K.box("hall floor", (0, 0.8, -0.01), (8, 8, 0.02), par, bev=0)
    for k in range(-20, 21):
        K.box("parquet seam", (k * 0.12, 0.8, 0.0006), (0.004, 8, 0.0012), K.mat("parquet seam", "#5A3A20", rough=0.9), bev=0)
    cream = K.mat("hall wall", "#F1E6CF", rough=0.8)
    wain = hw_wood("wainscot", "#7A5232", "#8E6440", scale=4)
    K.box("hall back wall", (0, 1.4, 1.2), (6, 0.06, 2.4), cream, bev=0)
    K.box("hall wainscot", (0, 1.36, 0.3), (6, 0.03, 0.6), wain, bev=0.004)
    K.box("hall side wall", (-1.5, 0.4, 1.2), (0.06, 3, 2.4), cream, bev=0)
    K.box("hall side wainscot", (-1.46, 0.4, 0.3), (0.03, 3, 0.6), wain, bev=0.004)
    # tall windows on the back wall, the sun through them
    fr = K.mat("hall window frame", "#FFFFFF", rough=0.5)
    for x in (-0.9, 0.9):
        K.box("hall window", (x, 1.365, 1.25), (0.5, 0.01, 0.9), K.mat("hall window glow", "#FFF3D6", emit=2.2), bev=0)
        for dx, dz, sx, sz in ((0, 0.46, 0.56, 0.04), (0, -0.46, 0.56, 0.04), (-0.27, 0, 0.04, 0.96), (0.27, 0, 0.04, 0.96), (0, 0, 0.03, 0.9), (0, 0.15, 0.5, 0.025), (0, -0.15, 0.5, 0.025)):
            K.box("hall window frame", (x + dx, 1.355, 1.25 + dz), (sx, 0.03, sz), fr, bev=0.003)
    # the stage at the back with its board
    K.box("hall stage", (0, 1.15, 0.12), (2.4, 0.4, 0.24), wain, bev=0.01)
    K.box("hall board", (0, 1.365, 1.95), (1.0, 0.02, 0.2), K.mat("hall board", "#1E4A7A", rough=0.5), bev=0.006)
    K.text("hall board word", "VILLAGE HALL", (0, 1.35, 1.92), 0.09, (math.pi / 2, 0, 0), hw_ink("board gold", "#F2C64A", emit=0.3), extrude=0.001)
    # bunting across the hall
    cols = ["#E53935", "#FDD835", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA"]
    for row, (y, z) in enumerate(((0.9, 1.62), (0.4, 1.7))):
        for k in range(22):
            x = -1.4 + k * 0.13
            sag = 0.08 * (1 - ((x / 1.45) ** 2))
            fl = K.box("bunting flag", (x, y, z - sag - 0.04), (0.08, 0.004, 0.08), K.mat(f"bunting {cols[(k + row) % 6]}", cols[(k + row) % 6], rough=0.7), bev=0)
            fl.rotation_euler = (0, math.pi / 4, 0); fl.scale = (1, 1, 1)
        K.cyl("bunting string", (0, y, z - 0.02), 0.002, 2.9, K.mat("string", "#EEEEEE"), rot=(0, math.pi / 2, 0), v=6, bev=0)
    # folding chairs in rows behind
    seat = K.mat("chair seat", "#3E6E9E", rough=0.5)
    leg = K.mat("chair leg", "#9EA4AA", rough=0.3, metal=0.8)
    for r in range(2):
        for k in range(7):
            x = -1.1 + k * 0.34 + (0.17 if r else 0); y = 0.6 + r * 0.32
            if abs(x - S4_P.x) < 0.25 and r == 0: continue
            K.box("chair seat", (x, y, 0.24), (0.2, 0.2, 0.02), seat, bev=0.004)
            K.box("chair back", (x, y + 0.1, 0.38), (0.2, 0.02, 0.18), seat, bev=0.004)
            for dx in (-0.09, 0.09):
                K.box("chair leg", (x + dx, y, 0.12), (0.012, 0.012, 0.24), leg, bev=0)

    def light():
        sc_ = bpy.context.scene; w = sc_.world or bpy.data.worlds.new("World"); sc_.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (1.0, 0.94, 0.84, 1); bg.inputs["Strength"].default_value = 0.45
        LOC._area("hall windows", (0.0, 1.0, 1.6), 2.0, 110, (1.0, 0.93, 0.8), aim=(0.1, 0.0, 0.4))
        LOC._area("hall fill", (0.6, -1.8, 1.4), 2.4, 70, (1.0, 0.95, 0.88), aim=(0.15, 0.0, 0.45))
        return LOC._hero_key()
    return light


def s4_machine():
    """the inspectors' new test machine: a white cabinet, a big dial (PASS green on the left, FAKE red on the right),
    a red beacon on top, a funnel on a side bracket"""
    white = K.mat("machine white", "#F4F6F8", rough=0.35)
    trim = K.mat("machine trim", "#1E4A7A", rough=0.4)
    steel = K.mat("machine steel", "#B8BCC0", rough=0.25, metal=0.9)
    K.box("test machine", (S4_M.x, S4_M.y, S4_MH / 2), (0.42, 0.28, S4_MH), white, bev=0.02)
    K.box("test machine band", (S4_M.x, S4_M.y - 0.141, S4_MH - 0.08), (0.42, 0.004, 0.06), trim, bev=0)
    K.text("test machine word", "EU LAB TEST", (S4_M.x, S4_M.y - 0.144, S4_MH - 0.09), 0.03, (math.pi / 2, 0, 0), hw_ink("machine word", "#FFFFFF"), extrude=0.0004)
    K.cyl("test machine dial", tuple(S4_DIAL), 0.14, 0.01, K.mat("dial face", "#FFFFFF", rough=0.4), rot=(math.pi / 2, 0, 0), v=48, bev=0.003)
    K.cyl("test machine bezel", tuple(S4_DIAL + Vector((0, 0.002, 0))), 0.15, 0.008, steel, rot=(math.pi / 2, 0, 0), v=48, bev=0.002)
    # the scale: ticks from green (left) through amber to red (right), along the top half of the dial
    for k in range(13):
        a = math.radians(-65 + k * (130 / 12))
        col = "#2E9E44" if k < 5 else ("#F2A51E" if k < 8 else "#D32F2F")
        p = S4_DIAL + Vector((0.115 * math.sin(a), -0.007, 0.115 * math.cos(a)))
        tk = K.box("dial tick", tuple(p), (0.012, 0.003, 0.03), K.mat(f"tick {col}", col, rough=0.5), bev=0)
        tk.rotation_euler = (0, a, 0)
    K.text("dial pass", "PASS", tuple(S4_DIAL + Vector((-0.07, -0.008, -0.045))), 0.026, (math.pi / 2, 0, 0), hw_ink("dial green", "#2E9E44"), extrude=0.0004)
    K.text("dial fake", "FAKE", tuple(S4_DIAL + Vector((0.07, -0.008, -0.045))), 0.026, (math.pi / 2, 0, 0), hw_ink("dial red", "#D32F2F"), extrude=0.0004)
    needle = K.empty("dial needle", tuple(S4_DIAL + Vector((0, -0.012, 0))))
    K.box("dial needle arm", (0, 0, 0.05), (0.01, 0.003, 0.11), K.mat("needle black", "#1A1A1A", rough=0.4), bev=0.001, parent=needle)
    K.cyl("dial needle hub", (0, -0.002, 0), 0.014, 0.008, K.mat("needle black", "#1A1A1A"), rot=(math.pi / 2, 0, 0), v=16, bev=0.001, parent=needle)
    hw_local(needle)
    # the beacon on top: a red glass dome with a mirror inside that spins
    K.cyl("beacon base", (S4_M.x, S4_M.y, S4_MH + 0.015), 0.05, 0.03, trim, v=24, bev=0.003)
    K.sph("beacon dome", (S4_M.x, S4_M.y, S4_MH + 0.06), 0.048, K.mat("beacon glass", "#FF3020", rough=0.15, emit=0.6), scale=(1, 1, 1.15))
    spin = K.empty("beacon spin", (S4_M.x, S4_M.y, S4_MH + 0.06))
    K.box("beacon mirror", (0, 0, 0), (0.07, 0.012, 0.05), K.mat("beacon lamp", "#FF5A3A", emit=12.0), bev=0.002, parent=spin)
    hw_local(spin)
    # the screen under the dial: dark, then RICE SYRUP FOUND in red
    K.box("test machine screen", (S4_M.x, S4_M.y - 0.142, 0.3), (0.3, 0.004, 0.09), K.mat("machine screen", "#14181C", rough=0.3), bev=0.003)
    found = K.text("screen found", "RICE SYRUP\nFOUND", (S4_M.x, S4_M.y - 0.146, 0.3), 0.032, (math.pi / 2, 0, 0), hw_ink("found red", "#FF3A2A", emit=5.0), extrude=0.0004)
    return needle, spin, found


def s4_funnel(at):
    """the funnel on its bracket off the machine's right side, its mouth at `at`"""
    steel = K.mat("machine steel", "#B8BCC0", rough=0.25, metal=0.9)
    K.cyl("funnel spout", (at.x, at.y, at.z - 0.07), 0.01, 0.06, steel, v=16, bev=0)
    for k in range(6):
        r = 0.012 + k * 0.009
        K.cyl("funnel ring", (at.x, at.y, at.z - 0.045 + k * 0.009), r, 0.01, steel, v=32, bev=0.001)
    a, b = Vector((S4_M.x + 0.21, S4_M.y - 0.08, at.z - 0.1)), Vector((at.x, at.y, at.z - 0.1))
    d = b - a
    K.cyl("funnel pipe", tuple((a + b) / 2), 0.01, d.length, steel, rot=tuple(Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()), v=12, bev=0)


def shot4():
    """THE SHARPER TEST. The lens low and wide in the hall: he walks up to the new machine with his dipper, dips it in
    the jar of the blend that passed, holds it over the funnel and lets one drop fall; the dial swings hard from PASS
    into FAKE, the beacon spins red; he jumps back and points at it, then at us."""
    W = hw_win
    T_IN = 0.2 * DUR                          # the walk up ends
    T_DIP = 0.28 * DUR
    T_DROP = 0.42 * DUR                        # the drop falls
    T_SWING = T_DROP + 0.32                    # ... lands, and the dial swings (arc 0.55)
    T_JUMP = T_SWING + 0.42
    T_POINT = 0.72 * DUR
    T_END = 0.9 * DUR                          # a last hop at us
    light = place_village_hall()
    needle, spin, found = s4_machine()
    # ---- him: walks up from the right, dips, holds the dipper over the funnel, jumps back, points
    data = load_data()
    P0 = S4_P + Vector((0.17, 0.13, 0))
    d0 = S4_P - P0
    data.place(P0.x, P0.y, math.degrees(math.atan2(d0.x, -d0.y)))
    hat = bee_hat(data)
    data.walk_to(S4_P, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw = data.arm.rotation_euler.z
    def yaw(t):
        y = math.degrees(yw) + (-22 - math.degrees(yw)) * W(t, T_IN, 0.35)       # turns to the jar and the machine
        y += 0 * W(t, T_DIP + 0.25, 0.3) * (1 - W(t, T_JUMP - 0.1, 0.3))      # to the funnel
        y += 25 * W(t, T_JUMP - 0.05, 0.25) - 20 * W(t, T_POINT - 0.3, 0.3) + 25 * W(t, T_END - 0.15, 0.25)   # back round to us
        return math.radians(y)
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        back = 0.07 * W(t, T_JUMP, 0.22) - 0.06 * W(t, T_POINT - 0.1, 0.3) + 0.05 * W(t, T_END - 0.1, 0.25)
        lean = 0.0 * (1 - W(t, T_JUMP - 0.1, 0.2))
        p = S4_P + Vector((back + lean, -0.02 * W(t, T_JUMP, 0.22), 0.0))
        z = 0.07 * hw_kick(t - T_JUMP - 0.04, 0.15) + 0.06 * hw_kick(t - T_POINT, 0.14) + 0.07 * hw_kick(t - T_END, 0.14) + 0.045 * hw_kick(t - T_DIP - 0.35, 0.13) + 0.035 * hw_kick(t - T_DROP - 0.05, 0.12) + 0.05 * hw_kick(t - T_IN - 0.08, 0.13)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (14 * W(t, T_DIP - 0.25, 0.25) * (1 - W(t, T_DIP + 0.2, 0.25)) + 8 * W(t, T_DROP - 0.3, 0.25) * (1 - W(t, T_SWING, 0.2))
                                      - 12 * W(t, T_JUMP, 0.15) * (1 - W(t, T_POINT - 0.1, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    MOUTH = Vector((S4_JAR.x, S4_JAR.y, S4_STOOL + 0.1))
    POINT_AT = S4_DIAL + Vector((0.05, 0, 0.02))
    OVER = S4_FUN + Vector((0, 0, 0.05))
    dk = [(0.0, (0.06, 0.09, -0.12)), (T_IN, (0.08, 0.1, -0.1)),
          (T_DIP - 0.25, (0.13, 0.05, -0.04)), (T_DIP, (0.13, 0.05, -0.1)), (T_DIP + 0.3, (0.13, 0.06, -0.04)),
          (T_DROP - 0.15, (0.09, 0.12, -0.02)), (T_DROP + 0.25, (0.09, 0.12, -0.01)),
          (T_JUMP, (0.1, 0.16, -0.03)), (T_JUMP + 0.3, (0.09, 0.17, 0.0)),
          (T_POINT, tuple(Vector(hw_rel(data, lf, T_POINT, POINT_AT)).normalized() * 0.15)), (T_POINT + 0.35, tuple(Vector(hw_rel(data, lf, T_POINT + 0.35, POINT_AT)).normalized() * 0.155)), (T_END, (0.1, 0.13, 0.03)), (DUR + 0.3, (0.1, 0.13, 0.04))]
    pk = [(0.0, (0.07, 0.1, -0.11)), (T_IN, (0.08, 0.1, -0.1)), (T_SWING, (0.1, 0.1, -0.08)),
          (T_JUMP, (0.08, 0.16, 0.03)), (T_JUMP + 0.3, (0.08, 0.16, 0.05)),
          (T_POINT, (0.06, 0.16, 0.0)), (T_POINT + 0.35, (0.09, 0.1, -0.09)), (T_END, (0.1, 0.14, 0.08)), (DUR + 0.3, (0.1, 0.14, 0.085))]
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.6)
    data.reach(rt, hw_hand(data, rt, pk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    CAM = Vector((0.29, -1.42, 0.55)); LOOK = Vector((0.24, 0.0, 0.47))
    data.look_at(CAM, 0.0, max_yaw=45, blend=0.0)
    data.look_at(S4_P + Vector((-0.12, -0.22, 0.32)), T_DIP - 0.45, max_yaw=50, max_pitch=20, blend=0.15)
    data.look_at(S4_P + Vector((-0.2, -0.12, 0.42)), T_DROP - 0.3, max_yaw=50, max_pitch=20, blend=0.15)
    data.look_at(S4_DIAL, T_SWING - 0.05, max_yaw=55, max_pitch=20, blend=0.12)
    data.look_at(CAM, T_JUMP + 0.25, max_yaw=45, blend=0.15)
    data.look_at(S4_DIAL, T_POINT - 0.1, max_yaw=55, max_pitch=20, blend=0.15)
    data.look_at(CAM, T_END - 0.2, max_yaw=45, blend=0.15)
    data.expression("determined", 0.0, T_DROP)
    data.expression("wry", T_DROP + 0.05, T_SWING - 0.05, blend=0.12)
    data.expression("surprised", T_SWING, T_POINT, blend=0.08)
    data.expression("pleased", T_POINT + 0.05, DUR + 1.0, blend=0.18)
    data.finish()
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, lf, fore=True)
    dr = dip["root"]
    # the jar of the blend sits where his dipper dips, the funnel where it drips (both built to his reach)
    sc.frame_set(F(T_DIP)); bpy.context.view_layer.update()
    hd = dr.matrix_world @ Vector((0, 0, dip["head_z"]))
    JH, JR = 0.11, 0.045
    jz = max(0.15, hd.z + 0.03 - JH)                   # the head just under the jar's rim
    K.cyl("blend stool", (hd.x, hd.y, jz / 2), 0.07, jz, hw_wood("stool wood", "#8A5E3A", "#A2744A", scale=5), v=24, bev=0.006)
    jr = jar("blend jar", (hd.x, hd.y, jz), r=JR, h=JH, fill=0.85, honey_col="#E6B850", label="PASSED")
    jr["root"].rotation_euler = (0, 0, math.radians(20))
    sc.frame_set(F(T_DROP)); bpy.context.view_layer.update()
    FUN = dr.matrix_world @ Vector((0, 0, dip["head_z"])) + Vector((0, 0, -0.06))
    s4_funnel(FUN)
    # ---- the drop: from the dipper's head into the funnel
    drop = K.sph("honey drop", (0, 0, 0), 0.012, hw_honey("drop honey", "#E6A52A", glow=1.5, clear=0.3), scale=(1, 1, 1.3))
    sc.frame_set(F(T_DROP)); bpy.context.view_layer.update()
    head0 = dr.matrix_world @ Vector((0, 0, dip["head_z"]))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t < T_DROP:
            sc.frame_set(f); bpy.context.view_layer.update()
            p = dr.matrix_world @ Vector((0, 0, dip["head_z"] - 0.02)); s = 0.4 + 0.6 * W(t, T_DIP, 0.3)
        else:
            u = min(1.0, (t - T_DROP) / 0.3)
            p = head0.lerp(FUN + Vector((0, 0, -0.02)), u * u); s = 1.0 if u < 1 else 1e-3
        drop.location = p; drop.scale = (s, s, 1.3 * s)
        drop.keyframe_insert("location", frame=f); drop.keyframe_insert("scale", frame=f)
    # ---- the dial swings hard from PASS into FAKE (an overshoot and a shiver), the beacon spins
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        u = max(0.0, (t - T_SWING) / 0.35)
        a = -55 + 115 * min(1.0, ease(min(1.0, u))) + 14 * math.sin(min(u, 4.0) * 5.0) * math.exp(-1.4 * u) * (u > 0) + 1.5 * math.sin(t * 37) * (u > 1)
        needle.rotation_euler = (0, math.radians(a), 0); needle.keyframe_insert("rotation_euler", frame=f)
        on = W(t, T_SWING, 0.1)
        spin.rotation_euler = (0, 0, on * (t - T_SWING) * 14.0); spin.scale = (max(1e-3, on),) * 3
        spin.keyframe_insert("rotation_euler", frame=f); spin.keyframe_insert("scale", frame=f)
        g = max(1e-3, W(t, T_SWING + 0.25, 0.12)); found.scale = (g, g, g); found.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=26, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.04, 0.12, 0.0)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.01)) * ease(t / DUR), S4_DIAL))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="village_hall", light=light, data=data, rest=1, grips=("honey dipper", "blend jar", "funnel"),
                conseq=[("the new machine catches the rice syrup: its dial swings from PASS into FAKE, RICE SYRUP FOUND lights up and the beacon spins", lambda: meshes_of("test machine", "dial", "beacon", "screen found"), T_SWING, DUR, {"hero": True}),
                        ("the needle swings from PASS to FAKE", lambda: meshes([needle]) + meshes_of("test machine dial"), T_SWING, T_SWING + 0.6, {"moves": True})])


# ====================================================================================================
# shot5.py
# ====================================================================================================
# ---------------------------------------------------------------- shot 5: the fakes keep coming (the alley)
"""5 THE FAKES KEEP COMING. The alley behind the cheap stall: real cobbles, brick walls, a back door, crates, bins,
a drainpipe, and a big blue drum stencilled SUGAR SYRUP on a stand, its tap filling PURE HONEY jars on a crate. The
lens tracks him in: he catches the tap filling another fake jar, grabs it and turns it upside down and the syrup
gushes out like water all over the cobbles; then he turns his own jar upside down beside it and his honey does not
budge; he holds both out to us, one empty, one full."""

S5_P = Vector((0.0, 0.0, 0.0))                  # where he stops at the crate
S5_YAW = math.radians(48)
S5_FW = Vector((math.sin(S5_YAW), -math.cos(S5_YAW), 0)); S5_OUT = Vector((math.cos(S5_YAW), math.sin(S5_YAW), 0))
S5_CT = 0.4                                      # the crate stack's top
S5_JAR = S5_P + S5_FW * 0.215 + S5_OUT * 0.06 + Vector((0, 0, S5_CT))   # the jar under the tap
S5_DRUM = S5_JAR + Vector((0.17, 0.31, 0.0))       # the drum's centre (its base on the stand at the crate's height)
S5_DR, S5_DH = 0.13, 0.38


def s5_brick(name, a="#9C4A32", b="#B8644A", mortar="#CFC4B2", scale=7.0):
    """a real brick wall: courses of bricks of two colours with a soft mortar joint and a rough bump"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord"); br = nt.nodes.new("ShaderNodeTexBrick")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (math.pi / 2, 0, 0)   # courses along x, rows up z
    br.inputs["Scale"].default_value = scale; br.inputs["Mortar Size"].default_value = 0.018; br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.2; br.offset = 0.5
    br.inputs["Color1"].default_value = (*K.lin(a), 1); br.inputs["Color2"].default_value = (*K.lin(b), 1)
    br.inputs["Mortar"].default_value = (*K.lin(mortar), 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 60
    mix = nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type = 'MULTIPLY'; mix.inputs["Fac"].default_value = 0.25
    nt.links.new(br.outputs["Color"], mix.inputs["Color1"]); nt.links.new(nz.outputs["Fac"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5; bp.invert = True
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def s5_crate(name, loc, size, rnd):
    """a slatted wooden crate"""
    wood = hw_wood(f"crate wood {rnd.randrange(3)}", "#8A6A44", "#A8865A", scale=5)
    dark = K.mat("crate gap", "#3A2C1E", rough=0.9)
    x, y, z = loc; sx, sy, sz = size
    K.box(name + " inside", (x, y, z + sz / 2), (sx - 0.01, sy - 0.01, sz - 0.01), dark, bev=0)
    n = 3
    for k in range(n):
        zz = z + sz * (k + 0.5) / n
        for s in (-1, 1):
            K.box(name + " slat", (x, y + s * sy / 2, zz), (sx, 0.012, sz / n - 0.012), wood, bev=0.003)
            K.box(name + " slat", (x + s * sx / 2, y, zz), (0.012, sy, sz / n - 0.012), wood, bev=0.003)
    K.box(name + " top", (x, y, z + sz - 0.006), (sx + 0.006, sy + 0.006, 0.012), wood, bev=0.003)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            K.box(name + " post", (x + sx_ * (sx / 2 - 0.01), y + sy_ * (sy / 2 - 0.01), z + sz / 2), (0.022, 0.022, sz), wood, bev=0.003)


def place_market_alley():
    """THE ALLEY BEHIND THE CHEAP STALL: cobbles (each stone a stone), brick walls with a back door and a drainpipe,
    crates, bins and sacks, the stall's canvas back, a lamp over the door, the drum of SUGAR SYRUP and its tap."""
    rnd = hw_random.Random(55)
    K.box("alley bed", (0, 0.5, -0.008), (8, 8, 0.012), K.mat("cobble joint", "#6A6258", rough=0.95), bev=0)
    stones = [hw_noise(f"cobble {k}", a, b, scale=18, rough=0.75, bump=0.6) for k, (a, b) in
              enumerate((("#7E7A72", "#9A958A"), ("#8C8070", "#A89A86"), ("#6E6A64", "#8A857C"), ("#9A8E7C", "#B2A690")))]
    for i in range(34):
        for j in range(21):
            x = -1.3 + i * 0.075 + (0.037 if j % 2 else 0.0) + rnd.uniform(-0.005, 0.005)
            y = -0.95 + j * 0.066 + rnd.uniform(-0.004, 0.004)
            K.sph("cobble", (x, y, -0.012), 1.0, rnd.choice(stones), scale=(0.04 + rnd.uniform(-0.003, 0.003), 0.035 + rnd.uniform(-0.003, 0.003), 0.012), seg=14, ring=7)
    brick = s5_brick("alley brick")
    K.box("alley back wall", (0, 0.62, 1.2), (6, 0.12, 2.4), brick, bev=0)
    K.box("alley side wall", (-1.35, 0.0, 1.2), (0.12, 2.4, 2.4), s5_brick("alley brick dark", "#7E3E2C", "#9A5440"), bev=0)
    door = hw_wood("back door", "#3E5A4A", "#557262", scale=4)
    K.box("back door", (-0.55, 0.555, 0.55), (0.42, 0.03, 1.1), door, bev=0.01)
    for k in range(5):
        K.box("door plank", (-0.55 - 0.16 + k * 0.08, 0.538, 0.55), (0.004, 0.006, 1.06), K.mat("plank gap", "#26342C", rough=0.9), bev=0)
    K.sph("door knob", (-0.38, 0.53, 0.55), 0.016, K.mat("brass", "#B89040", rough=0.3, metal=0.9))
    K.box("door step", (-0.55, 0.5, 0.02), (0.5, 0.12, 0.04), hw_noise("step stone", "#9A958A", "#B5AFA2", scale=10), bev=0.006)
    lampm = K.mat("lamp glass", "#FFE2A0", rough=0.3, emit=6.0)
    K.box("lamp arm", (-0.55, 0.52, 1.28), (0.02, 0.12, 0.02), K.mat("lamp iron", "#2E2A28", rough=0.5, metal=0.7), bev=0.003)
    K.cyl("lamp", (-0.55, 0.46, 1.22), 0.04, 0.09, lampm, v=16, bev=0.005)
    pipe = K.mat("drainpipe", "#3C4A42", rough=0.4, metal=0.5)
    K.cyl("drainpipe", (0.95, 0.54, 1.2), 0.025, 2.4, pipe, v=16, bev=0.002)
    K.box("drain shoe", (0.95, 0.5, 0.05), (0.06, 0.1, 0.05), pipe, bev=0.006)
    # the stall's back: striped canvas over the alley's far end
    for k in range(9):
        K.box("stall canvas", (1.3 + 0.0, -0.6 + k * 0.14, 0.9), (0.02, 0.14, 1.0),
              K.mat("canvas red" if k % 2 else "canvas cream", "#B8362C" if k % 2 else "#EDE2C8", rough=0.85), bev=0)
    # bins, sacks, a stack of empty crates by the door, a broom
    binm = K.mat("bin green", "#3E6A4A", rough=0.5, metal=0.3)
    K.cyl("bin", (-0.95, 0.38, 0.22), 0.16, 0.44, binm, v=24, bev=0.01)
    K.cyl("bin lid", (-0.95, 0.38, 0.45), 0.17, 0.03, binm, v=24, bev=0.006)
    sack = hw_noise("sack", "#B8A07A", "#CDB894", scale=20, rough=0.95, bump=0.6)
    for k, (x, y) in enumerate(((0.7, 0.4), (0.82, 0.32))):
        K.sph("sugar sack", (x, y, 0.15), 1.0, sack, scale=(0.13, 0.11, 0.16))
        K.text("sack print", "SUGAR", (x, y - 0.112, 0.16), 0.04, (math.pi / 2, 0, 0), K.mat("sack ink", "#3A3A6A", rough=0.8))
    for k in range(3):
        s5_crate(f"empty crate {k}", (-0.2 + 0.02 * k, 0.42, 0.22 * k), (0.28, 0.2, 0.22), rnd)
    K.cyl("broom handle", (-0.82, 0.5, 0.6), 0.012, 1.2, hw_wood("broom", "#A07A50", "#B89068"), rot=(0.12, 0, 0), v=12)
    # the drum of SUGAR SYRUP on its stand, its tap over the crate, and the crate stack with the jars it fills
    blue = K.mat("drum blue", "#1E5AA8", rough=0.35)
    K.cyl("drum", (S5_DRUM.x, S5_DRUM.y, S5_CT + S5_DH / 2), S5_DR, S5_DH, blue, v=40, bev=0.015)
    for z in (0.08, S5_DH - 0.08):
        K.cyl("drum rib", (S5_DRUM.x, S5_DRUM.y, S5_CT + z), S5_DR + 0.006, 0.02, blue, v=40, bev=0.006)
    K.cyl("drum cap", (S5_DRUM.x + 0.05, S5_DRUM.y, S5_CT + S5_DH + 0.01), 0.03, 0.025, K.mat("cap white", "#EEEEEE", rough=0.4), v=16)
    tv = (S5_JAR - S5_DRUM); tv.z = 0; ang = math.atan2(-tv.x, tv.y)
    K.text("drum stencil", "SUGAR\nSYRUP", (S5_DRUM.x + tv.normalized().x * (S5_DR + 0.003), S5_DRUM.y + tv.normalized().y * (S5_DR + 0.003), S5_CT + 0.24),
           0.05, (math.pi / 2, 0, ang + math.pi), K.mat("stencil white", "#F4F4F0", rough=0.6))
    s5_crate("drum stand", (S5_DRUM.x, S5_DRUM.y, 0.0), (0.3, 0.3, S5_CT), rnd)
    s5_crate("jar crate", (S5_JAR.x + 0.06, S5_JAR.y - 0.02, 0.0), (0.27, 0.23, S5_CT), rnd)
    steel = K.mat("tap steel", "#B0B4B8", rough=0.25, metal=0.9)
    spout = S5_JAR + Vector((0, 0, 0.13))
    K.capsule("tap pipe", S5_DRUM + Vector((0, 0, S5_CT + 0.2)) + tv.normalized() * (S5_DR - 0.01) - Vector((0, 0, S5_CT)), spout + Vector((0, 0, 0.02)), 0.012, steel)
    K.cyl("tap spout", tuple(spout), 0.012, 0.04, steel, v=16)
    K.box("tap handle", tuple(spout + Vector((0, 0, 0.045))), (0.05, 0.012, 0.012), K.mat("tap red", "#C8261E", rough=0.4), bev=0.003)
    return lambda: village_light(sun_elev=50, sun_az=-25, sun=3.2, sky=0.3)


def shot5():
    """THE FAKES KEEP COMING. The lens tracks him in to the crate: he catches the SUGAR SYRUP tap filling another
    PURE HONEY jar, grabs it and turns it upside down and the syrup gushes out like water onto the cobbles; he turns
    his own jar upside down beside it and his honey does not budge; he holds both out to us, one empty, one full."""
    T_STOP = 0.85                                 # he walks in
    T_GRAB = 0.3 * DUR                           # grabs the fake jar off the crate ...
    T_INV = T_GRAB + 0.4                         # ... and turns it upside down
    T_GUSH = 0.45 * DUR                          # it gushes out like water
    T_OWN = 0.65 * DUR                           # his own jar upside down: it does not budge
    T_SHOW = 0.85 * DUR                          # both out to us
    light = place_market_alley()
    fake = jar("fake jar", tuple(S5_JAR), r=0.048, h=0.12, fill=0.9, honey_col="#F2C35A", label="PURE HONEY")
    mine = jar("his jar", (0, 0, 0), r=0.062, h=0.15, fill=0.9, honey_col="#E49A1E", label="1 lb", glow=0.5)
    for j in (fake, mine):
        bpy.data.objects[("fake jar" if j is fake else "his jar") + " lid"].hide_render = True   # lids off: open jars
    rnd = hw_random.Random(3)
    for k, off in enumerate((Vector((0.1, -0.07, 0)), Vector((0.13, 0.04, 0)))):
        jar(f"filled fake {k}", tuple(S5_JAR + off), r=0.048, h=0.12, fill=0.9, honey_col="#F2C35A", label="PURE HONEY", yaw=math.radians(rnd.uniform(-15, 15)))
    for k in range(3):                           # and a tray of them waiting on the stack by the door
        jar(f"tray fake {k}", (-0.13 + 0.09 * k, 0.4, 0.66), r=0.04, h=0.1, fill=0.9, honey_col="#F2C35A", label="PURE HONEY")
    data = load_data()
    P0 = S5_P + Vector((-0.17, 0.08, 0.0))
    data.place(P0.x, P0.y, math.degrees(math.atan2((S5_P - P0).normalized().x, -(S5_P - P0).normalized().y)))
    hat = bee_hat(data)
    W = hw_win
    data.walk_to(Vector((S5_P.x, S5_P.y, 0)), 0.0, T_STOP)
    sc.frame_set(F(T_STOP)); bpy.context.view_layer.update()
    y_walk = data.arm.rotation_euler.z
    def body(t):
        p = S5_P.copy()
        p += -S5_FW * 0.06 * W(t, T_GRAB + 0.05, 0.4) - Vector((0, 0, 0)) # steps back off the crate with it
        p.z += 0.025 * hw_kick(t - T_GRAB - 0.1, 0.12)
        p += -S5_FW * 0.05 * hw_kick(t - T_GUSH - 0.1, 0.26)                                   # rocks back from the gush
        p.z += 0.03 * hw_kick(t - T_GUSH - 0.05, 0.12)
        p += -S5_FW * 0.0 * W(t, T_OWN - 0.6, 0.4)                                            # steps back for room
        p.z += 0.02 * math.sin(2 * math.pi * (t - T_OWN - 0.15) / 0.3) * W(t, T_OWN + 0.05, 0.2) * (1 - W(t, T_OWN + 0.65, 0.25))   # bounces with the shake
        p += S5_FW * 0.07 * W(t, T_SHOW - 0.3, 0.45)                                            # and comes to us
        p.z += 0.03 * hw_kick(t - T_SHOW - 0.2, 0.13)
        yaw = y_walk + (S5_YAW - y_walk) * W(t, T_STOP - 0.05, 0.4) - math.radians(38) * W(t, T_OWN - 0.6, 0.6)
        return p, yaw
    for f in range(F(T_STOP), NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (6 * math.sin(2 * math.pi * (t - T_OWN - 0.15) / 0.3) * W(t, T_OWN + 0.05, 0.2) * (1 - W(t, T_OWN + 0.65, 0.25)) - 8 * hw_kick(t - T_GUSH - 0.1, 0.26)
                                      + 6 * W(t, T_OWN - 0.3, 0.3) * (1 - W(t, T_SHOW - 0.5, 0.5)) - 5 * W(t, T_SHOW - 0.1, 0.5), 0, 0), 0, DUR + 0.4)
    sc.frame_set(F(T_STOP)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: (acts._shoulder(data, s) - Vector(data.arm.location)).dot(S5_OUT))
    left, right = sides                          # right: the crate's side (the fake); left: his own jar
    # ---- the fake jar: under the tap, filling; in his right hand from T_GRAB; upside down; empty; upright to us
    fr, fs, fh = fake["root"], fake["spin"], fake["honey"]
    def hold(sd, rel):
        return hw_hand(data, sd, rel)
    rk = [(0.0, (0.06, 0.1, -0.16)), (T_STOP, (0.07, 0.1, -0.15)), (T_GRAB - 0.35, (0.08, 0.06, -0.08)),
          (T_GRAB, hw_rel(data, right, T_GRAB, S5_JAR + Vector((0, 0, 0.06)))),
          (T_INV + 0.2, (0.11, 0.07, -0.02)), (T_GUSH + 0.5, (0.11, 0.09, -0.03)), (T_OWN - 0.2, (0.1, 0.12, -0.03)),
          (T_SHOW, (0.13, 0.08, -0.02)), (DUR + 0.3, (0.13, 0.08, -0.01))]
    lk = [(0.0, (0.06, 0.1, -0.14)), (T_STOP, (0.07, 0.1, -0.14)), (T_GUSH, (0.07, 0.11, -0.12)), (T_OWN - 0.45, (0.1, 0.08, -0.05)),
          (T_OWN - 0.1, (0.11, 0.06, -0.02)), (T_OWN + 0.15, (0.11, 0.06, 0.0)),
          (T_OWN + 0.3, (0.11, 0.08, 0.03)), (T_OWN + 0.45, (0.11, 0.08, -0.02)), (T_OWN + 0.6, (0.11, 0.08, 0.02)),   # shakes it: nothing
          (T_OWN + 0.8, (0.115, 0.075, 0.0)), (T_SHOW + 0.45, (0.13, 0.06, -0.04)), (DUR + 0.3, (0.13, 0.06, -0.04))]
    rh, lh_ = hold(right, rk), hold(left, lk)
    data.reach(right, rh, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(left, lh_, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    # ---- the face
    LENS = lambda t: Vector((-0.55 + 0.45 * ease(t / DUR), -1.25 + 0.2 * W(t, T_OWN, 1.0), 0.62))
    data.look_at(S5_JAR + Vector((0, 0, 0.1)), 0.0, max_yaw=45, max_pitch=35, blend=0.0)
    data.look_at(LENS(T_STOP), T_STOP + 0.05, max_yaw=45, blend=0.15)                          # a look at us: see that?
    data.look_at(S5_JAR + Vector((0, 0, 0.05)), T_GRAB - 0.4, max_yaw=45, max_pitch=35, blend=0.15)
    data.look_at(S5_JAR + Vector((0, -0.05, 0.1)), T_GUSH - 0.1, max_yaw=45, max_pitch=40, blend=0.12)
    data.look_at(LENS(T_OWN - 0.4), T_OWN - 0.5, max_yaw=45, blend=0.18)
    data.look_at(LENS(DUR), T_SHOW - 0.2, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_GRAB - 0.1)
    data.expression("determined", T_GRAB, T_GUSH - 0.05, blend=0.12)
    data.expression("surprised", T_GUSH, T_OWN - 0.3, blend=0.1)
    data.expression("pleased", T_OWN - 0.2, T_SHOW - 0.1, blend=0.15)
    data.expression("happy", T_SHOW, DUR + 1.0, blend=0.18)
    data.finish()
    # jars in his hands: the jar's middle in his fist, upright, upside down, upright again
    def carry(j, sd, t0, flip0, flip1, back0, back1, rest_at=None):
        root = j["root"]; hh = j["h"]
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < t0 and rest_at is not None:
                root.location = rest_at; root.rotation_euler = (0, 0, 0)
            else:
                sc.frame_set(f); bpy.context.view_layer.update()
                M = data.arm.matrix_world @ data.pb["hand." + sd].matrix
                fist = M.translation + (M.to_3x3() @ Vector((0, 0.045, 0)))
                yw = data.arm.rotation_euler.z
                a = math.pi * (W(t, flip0, 0.35) - W(t, back0, 0.4)) if back0 else math.pi * W(t, flip0, 0.35)
                Rm = Euler((0, 0, yw)).to_matrix() @ Euler((0, a, 0)).to_matrix()
                root.location = fist - Rm @ Vector((0, 0, hh / 2)); root.rotation_euler = Rm.to_euler()
                if rest_at is not None:
                    u = W(t, t0, 0.15); root.location = Vector(rest_at).lerp(root.location, u)
            root.keyframe_insert("location", frame=f); root.keyframe_insert("rotation_euler", frame=f)
    carry(fake, right, T_GRAB, T_INV - 0.05, None, T_SHOW - 0.5, None, rest_at=tuple(S5_JAR))
    carry(mine, left, 0.0, T_OWN - 0.35, None, T_SHOW - 0.4, None)
    # the fake fills under the tap, then (upside down) runs out of its mouth in a gush onto the cobbles
    hz = fake["hz"]
    for t, s_, z in ((0.0, 0.35, None), (T_GRAB - 0.15, 1.0, None), (T_GUSH, 1.0, "top"), (T_GUSH + 0.75, 0.02, "top")):
        fh.scale = (1, 1, s_); fh.location.z = (hz * s_ / 2 + 0.002) if z is None else (hz - hz * s_ / 2 + 0.002)
        fh.keyframe_insert("scale", frame=F(t)); fh.keyframe_insert("location", frame=F(t))
    syrup = hw_honey("cheap syrup", "#F4C65E", glow=0.6, clear=0.75)
    tap = K.cyl("tap stream", (0, 0, 0), 1.0, 1.0, syrup, v=12, bev=0)
    gush = K.cyl("gush", (0, 0, 0), 1.0, 1.0, syrup, v=16, bev=0)
    pud = K.cyl("syrup puddle", (0, 0, 0), 1.0, 0.004, hw_honey("puddle syrup", "#E8B44C", glow=0.3, clear=0.5), v=40, bev=0.0015)
    spout = S5_JAR + Vector((0, 0, 0.13)); land = Vector((0, 0, 0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        on = 1.0 - W(t, T_GRAB - 0.2, 0.15)
        top = fake["root"].matrix_world @ Vector((0, 0, hz)) if t < T_GRAB else spout - Vector((0, 0, 0.06))
        a, b = spout, top
        tap.location = (a + b) / 2; r = 0.006 * on + 1e-4; tap.scale = (r, r, max(1e-3, (a - b).length))
        for k in ("location", "scale"): tap.keyframe_insert(k, frame=f)
        mouth = fake["root"].matrix_world @ Vector((0, 0, fake["h"]))
        if f == F(T_GUSH): land = Vector((mouth.x, mouth.y, 0.0))
        g = W(t, T_GUSH, 0.12) * (1 - W(t, T_GUSH + 0.65, 0.2))
        gb = Vector((mouth.x, mouth.y, 0.0)); gl = max(1e-3, mouth.z)
        gush.location = (mouth + gb) / 2; rr = 0.018 * g + 1e-4; gush.scale = (rr, rr, gl)
        for k in ("location", "scale"): gush.keyframe_insert(k, frame=f)
        pr = 0.22 * W(t, T_GUSH + 0.05, 0.8) + 1e-3
        pud.location = (land.x if t >= T_GUSH else mouth.x, land.y if t >= T_GUSH else mouth.y, 0.003); pud.scale = (pr, pr * 0.8, 1)
        for k in ("location", "scale"): pud.keyframe_insert(k, frame=f)
    # splashes where it lands
    drops = []
    for k in range(12):
        d = K.sph("syrup splash", (0, 0, 0), 1.0, syrup, seg=10, ring=6); drops.append(d)
        th = 2 * math.pi * k / 12 + rnd.uniform(-0.2, 0.2); sp = rnd.uniform(0.25, 0.5); t0 = T_GUSH + 0.05 + rnd.uniform(0, 0.4)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - t0) / 0.35
            if 0 <= u <= 1:
                d.location = land + Vector((math.cos(th) * sp * 0.25 * u, math.sin(th) * sp * 0.25 * u, 0.12 * math.sin(math.pi * u) + 0.005)); s_ = 0.01
            else:
                d.location = land; s_ = 1e-4
            d.scale = (s_, s_, s_); d.keyframe_insert("location", frame=f); d.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(LENS(0)), tuple(S5_P + Vector((0.0, 0.0, 0.42))), lens=30, fstop=7.0)
    camera_path(cam, lambda t: (LENS(t), Vector((-0.12 + 0.2 * ease(t / DUR), 0.0, 0.42)) + S5_FW * 0.05 * W(t, T_OWN, 1.0), S5_P + Vector((0, 0, 0.5))))
    return dict(lanes=[], kiosks=[], place="market_alley", light=light, data=data, rest=1, grips=("fake jar", "his jar"),
                conseq=[("the fake PURE HONEY jar, upside down, gushes out like water onto the cobbles", lambda: meshes([fake["root"], gush, pud]), T_GUSH, T_GUSH + 0.8, {"hero": True}),
                        ("the SUGAR SYRUP drum's tap fills another PURE HONEY jar", lambda: meshes([fake["root"], tap]) + [o for o in bpy.data.objects if o.name.startswith(("drum", "tap"))], 0.1, T_GRAB),
                        ("his own jar upside down: the honey does not budge", lambda: meshes([mine["root"]]), T_OWN - 0.1, T_SHOW),
                        ("one empty, one full, held out to us", lambda: meshes([mine["root"], fake["root"]]), T_SHOW - 0.3, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
