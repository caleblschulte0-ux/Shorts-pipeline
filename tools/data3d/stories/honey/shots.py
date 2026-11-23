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
the beekeeper slams his dipper on the counter, the row jumps, and five of the eleven labels flip over to a red SYRUP
(46% of the EU's imported samples: almost half)."""

S1_FAKES = (0, 2, 5, 7, 9)          # which of the eleven jars are syrup (0 = the one nearest the lens)
S1_N = 11
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
    """THE CHEAP STALL. The lens low at the near end of the counter, the row of eleven jars running away from it to
    the beekeeper at the far end: he peers along the jars, straightens and frowns up at the 2 EUROS sign, raises his
    dipper and SLAMS it on the counter; the row jumps, and five labels flip one after another down the row to a red
    SYRUP; he jumps back, then leans in and points his dipper down the five red ones at us."""
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
        x = -0.42 + k * 0.105
        a = math.atan2(CAM.y - (-0.12), CAM.x - x)            # the jar's label (its -Y face) turned to the lens
        fake = k in S1_FAKES
        jars.append(jar(f"stall jar {k}", (x, -0.12, S1_CH), r=0.046, h=0.15, fill=0.9, honey_col="#E6A52A" if fake else "#D98A12",
                        label="PURE HONEY", back="SYRUP" if fake else None, yaw=a + math.pi / 2))
    fakes = [jars[k] for k in S1_FAKES]
    for i, j in enumerate(sorted(fakes, key=lambda j: -j["root"].location.x)): jar_flip(j, T_FLIP[i])   # down the row from him to us
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
    data.look_at(fakes[3]["root"].location + Vector((0, 0, 0.08)), T_FLIP[0], max_yaw=40, max_pitch=40, blend=0.12)
    data.look_at(fakes[0]["root"].location + Vector((0, 0, 0.08)), T_FLIP[3], max_yaw=40, max_pitch=40, blend=0.2)
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
                conseq=[("he slams his dipper and five of the eleven labels flip to a red SYRUP", lambda: meshes([j["root"] for j in fakes]), T_FLIP[0], DUR, {"hero": True}),
                        ("the slam makes the whole row of jars jump", lambda: meshes([j["root"] for j in jars]), T_SLAM, T_SLAM + 0.5)])


# ====================================================================================================
# shot2.py
# ====================================================================================================
"""BEAT 2, ONE BEE'S LIFE: the hive yard on the hill. He flips open his hive and holds up a teaspoon as big as his arm,
its round bowl marked like a pie into twelve wedges; one bee flies out to it, wrings out her single golden drop, and
it fills ONE wedge of the twelve; she flops on the rim, worn out, and eleven more bees queue up in the air for the rest
(one bee makes about a twelfth of a teaspoon in her whole life)."""


def s2_tuft(name, x, y, rnd, grass):
    """a tuft of tall meadow grass: a few thin blades fanned out"""
    for k in range(4):
        h = rnd.uniform(0.08, 0.16); a = rnd.uniform(0, 2 * math.pi); lean = rnd.uniform(0.1, 0.35)
        b = K.box(name, (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), h / 2), (0.008, 0.002, h), grass, bev=0)
        b.rotation_euler = (lean * math.sin(a), -lean * math.cos(a), a)


def s2_hive(name, loc, rnd, paint="#F4F1E8", lid=True):
    """a white wooden beehive: a stand, three stacked boxes, an entrance slot at the bottom front, a gabled lid hinged
    at its back edge. Returns dict(root, lid) (lid is an empty at the hinge; the lid's mesh rides it)."""
    x, y = loc
    wood = hw_noise(f"hive paint {paint}", paint, K.mute(paint, 0.9), scale=8, rough=0.7, bump=0.15, stretch=(1, 1, 5))
    dark = K.mat("hive slot", "#2A2018", rough=0.9)
    W, D = 0.24, 0.26
    K.box(name + " stand", (x, y, 0.04), (W + 0.04, D + 0.04, 0.08), hw_wood("hive stand", "#6E5232", "#8A6A44"), bev=0.004)
    for k in range(2):
        K.box(name + " box", (x, y, 0.08 + 0.065 + k * 0.13), (W, D, 0.125), wood, bev=0.004)
        for sg in (-1, 1):
            K.box(name + " handle", (x + sg * (W / 2 + 0.004), y, 0.08 + 0.09 + k * 0.13), (0.008, 0.08, 0.016), wood, bev=0.002)
    K.box(name + " slot", (x, y - D / 2 - 0.002, 0.095), (0.16, 0.006, 0.014), dark, bev=0)
    K.box(name + " landing board", (x, y - D / 2 - 0.03, 0.085), (0.2, 0.06, 0.01), wood, bev=0.002)
    z_top = 0.08 + 0.26
    hinge = K.empty(name + " lid hinge", (x, y + D / 2 + 0.01, z_top))
    roofm = K.mat("hive roof tin", "#B8BCC0", rough=0.35, metal=0.7)
    lid_parts = [K.box(name + " lid", (x, y, z_top + 0.03), (W + 0.04, D + 0.04, 0.05), wood, bev=0.004)]
    for sg in (-1, 1):
        o = K.box(name + " lid roof", (x + sg * 0.09, y, z_top + 0.075), (0.2, D + 0.06, 0.008), roofm, bev=0.002)
        o.rotation_euler = (0, sg * 0.3, 0); lid_parts.append(o)
    for o in lid_parts:                     # built absolute: parent them to the hinge keeping where they are
        o.parent = hinge; o.matrix_parent_inverse = HW_M.Translation(-Vector((x, y + D / 2 + 0.01, z_top)))
    return dict(hinge=hinge, top=z_top, front=Vector((x, y - D / 2, z_top + 0.05)), slot=Vector((x, y - D / 2 - 0.03, 0.1)), W=W, D=D)


def s2_spoon(name, R=0.15, L=0.16):
    """the giant teaspoon, built upright: its grip at the origin, the handle up +Z, the round bowl at the top facing -Y,
    marked like a pie into twelve wedges by thin dark lines. Returns dict(root, center, fill, R)."""
    root = K.empty(name, (0, 0, 0))
    steel = K.mat("spoon steel", "#D9DDE2", rough=0.22, metal=0.85)
    K.capsule(name + " handle", Vector((0, 0, 0.0)), Vector((0, 0, L)), 0.018, steel, parent=root)
    c = Vector((0, 0, L + R * 0.95))
    K.cyl(name + " bowl", tuple(c + Vector((0, 0.012, 0))), R, 0.02, steel, rot=(math.pi / 2, 0, 0), v=64, bev=0.006, parent=root)
    K.cyl(name + " bowl rim", tuple(c + Vector((0, 0.0, 0))), R * 1.03, 0.012, steel, rot=(math.pi / 2, 0, 0), v=64, bev=0.004, parent=root)
    inner = K.cyl(name + " bowl face", tuple(c + Vector((0, -0.007, 0))), R * 0.94, 0.004, K.mat("spoon face", "#EEF0F2", rough=0.3, metal=0.4),
                  rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    ink = K.mat("spoon marks", "#2B2B30", rough=0.6)
    for k in range(12):                     # the twelve wedges, like a pie
        a = math.radians(30 * k + 15)
        o = K.box(name + " mark", tuple(c + Vector((math.cos(a) * R * 0.47, -0.01, math.sin(a) * R * 0.47))), (R * 0.94, 0.002, 0.004), ink, bev=0, parent=root)
        o.rotation_euler = (0, -a, 0)
    K.cyl(name + " hub", tuple(c + Vector((0, -0.011, 0))), 0.008, 0.002, ink, rot=(math.pi / 2, 0, 0), v=16, bev=0, parent=root)
    # the one wedge her drop fills: a gold fan pointing straight down (where a drop runs), grown out from the hub
    bm = HW_bmesh.new(); n = 10; rr = R * 0.92
    verts = [bm.verts.new((0, 0, 0))] + [bm.verts.new((rr * math.cos(math.radians(-105 + 30 * i / n)), 0, rr * math.sin(math.radians(-105 + 30 * i / n)))) for i in range(n + 1)]
    for i in range(n): bm.faces.new((verts[0], verts[i + 1], verts[i + 2]))
    me = bpy.data.meshes.new(name + " fill"); bm.to_mesh(me); bm.free()
    fill = bpy.data.objects.new(name + " fill", me); me.materials.append(K.mat("spoon honey gold", "#F2A81E", rough=0.2, emit=0.35))
    bpy.context.collection.objects.link(fill)
    sd = fill.modifiers.new("thick", 'SOLIDIFY'); sd.thickness = 0.006
    fill.parent = root; fill.location = c + Vector((0, -0.013, 0))
    hw_local(root)
    return dict(root=root, center=c, fill=fill, R=R)


def place_hive_yard():
    """HIS HIVE YARD on the hill above the village: a meadow of tall grass and wildflowers, his white hives in a row,
    a split-rail fence, two apple trees, a stone shed, and the village's red roofs and church far down the hill."""
    rnd = hw_random.Random(22)
    meadow = hw_noise("meadow", "#5E8A32", "#A4C45A", scale=22, rough=0.95, bump=1.0, detail=8, lo=0.36, hi=0.66)
    K.box("meadow ground", (0, 4, -0.01), (30, 30, 0.02), meadow, bev=0)
    hill = hw_noise("far hill", "#6F9A40", "#A2BD62", scale=9, rough=0.95, bump=0.5, detail=5)
    K.sph("far hill", (0, 12, -4.0), 6.0, hill, scale=(3.0, 1.2, 0.9))
    hedge = hw_noise("hedge", "#3F6E2A", "#5E8E38", scale=18, rough=0.9, bump=0.8, detail=5)
    for k in range(16):                         # a long hedge of round bushes behind the hives
        K.sph("hedge bush", (-3.0 + 0.4 * k + rnd.uniform(-0.05, 0.05), 2.6 + rnd.uniform(-0.1, 0.1), 0.3), rnd.uniform(0.28, 0.36), hedge, scale=(1.0, 0.8, 1.1), seg=20, ring=12)
    grass = [K.mat(f"blade {c}", c, rough=0.8) for c in ("#5E8A2E", "#7AA23C", "#8DB24A")]
    petals = [K.mat(f"flower {c}", c, rough=0.6) for c in ("#F2D43A", "#F4F0E6", "#C96BC0", "#E0583A", "#6E8CE0")]
    for k in range(320):
        x, y = rnd.uniform(-1.8, 2.0), rnd.uniform(-1.3, 2.4)
        if -0.5 < x < 0.6 and -0.55 < y < 0.45: continue                 # his patch and the hive's, trodden flat
        s2_tuft("meadow tuft", x, y, rnd, rnd.choice(grass))
    for k in range(220):                       # the meadow right under the lens: grass and flowers up close
        x, y = rnd.uniform(-1.0, 1.4), rnd.uniform(-1.25, -0.55)
        s2_tuft("near tuft", x, y, rnd, rnd.choice(grass))
        if k % 3 == 0:
            K.sph("near flower", (x + 0.02, y, rnd.uniform(0.08, 0.15)), rnd.uniform(0.012, 0.02), rnd.choice(petals), seg=10, ring=6)
        if k % 2 == 0:
            K.sph("wildflower", (x + 0.02, y, rnd.uniform(0.1, 0.17)), rnd.uniform(0.012, 0.02), rnd.choice(petals), seg=10, ring=6)
    hives = [s2_hive(f"hive {k}", (x, y), rnd) for k, (x, y) in enumerate(((-1.0, 1.0), (-0.35, 1.25), (0.35, 1.45), (1.0, 1.25), (1.6, 0.9)))]
    rail = hw_wood("fence rail", "#7C6446", "#9A7E5A", scale=4)
    for k in range(14):
        x = -2.4 + 0.42 * k
        K.box("fence post", (x, 3.1, 0.24), (0.04, 0.04, 0.48), rail, bev=0.004)
    for z in (0.18, 0.36):
        K.box("fence rail", (0.33, 3.1, z), (5.6, 0.025, 0.03), rail, bev=0.003)
    leaf = hw_noise("apple leaves", "#4E7E32", "#6E9C40", scale=10, rough=0.85, bump=0.4)
    bark = hw_wood("apple bark", "#5A4330", "#6E5440", scale=8)
    for k, (x, y) in enumerate(((-1.3, 1.9), (1.4, 2.0), (-0.2, 2.9), (0.7, 3.4), (2.4, 2.9), (-2.2, 2.8))):
        K.cyl("apple trunk", (x, y, 0.65), 0.07, 1.3, bark, v=12, bev=0.01)
        for j in range(5):
            K.sph("apple crown", (x + rnd.uniform(-0.35, 0.35), y + rnd.uniform(-0.2, 0.2), 1.55 + rnd.uniform(-0.15, 0.35)), rnd.uniform(0.4, 0.55), leaf, seg=20, ring=12)
        for j in range(8):
            K.sph("apple", (x + rnd.uniform(-0.4, 0.4), y - 0.25 + rnd.uniform(-0.1, 0.1), 1.4 + rnd.uniform(-0.1, 0.4)), 0.035, K.mat("apple red", "#C8352A", rough=0.4), seg=12, ring=8)
    stone = hw_noise("shed stone", "#B5AB98", "#CFC6B2", scale=10, rough=0.9, bump=0.5)
    K.box("stone shed", (-2.6, 3.8, 0.45), (1.2, 0.9, 0.9), stone, bev=0.02)
    K.box("shed roof", (-2.6, 3.8, 0.95), (1.35, 1.05, 0.1), K.mat("roof tile", "#A4512E", rough=0.8), bev=0.01)
    K.box("shed door", (-2.6, 3.34, 0.32), (0.3, 0.02, 0.6), K.mat("door wood", "#5C3A22", rough=0.6), bev=0.006)
    # the village far down the hill: red roofs and the church tower over the meadow's edge
    walls = [K.mat(f"far wall {c}", c, rough=0.9) for c in ("#E9D9B8", "#E2C59A", "#EFE4CF")]
    for k in range(16):
        x = -5 + k * 0.65 + rnd.uniform(-0.1, 0.1); y = 9 + rnd.uniform(-0.5, 0.8)
        K.box("far house", (x, y, -0.2), (0.5, 0.4, 0.6), rnd.choice(walls), bev=0.01)
        K.box("far roof", (x, y, 0.13), (0.56, 0.46, 0.1), K.mat("roof tile", "#A4512E", rough=0.8), bev=0.01)
    K.box("far church", (1.5, 9.6, 0.4), (0.4, 0.4, 1.6), walls[2], bev=0.01)
    K.cyl("far church roof", (1.5, 9.6, 1.4), 0.3, 0.45, K.mat("roof tile", "#A4512E", rough=0.8), v=4, bev=0.01).rotation_euler = (0, 0, math.pi / 4)

    def light():
        return village_light(sun_elev=48, sun_az=-30, sun=3.8, sky=0.35)
    return light, hives


def shot2():
    """ONE BEE'S LIFE. The lens wide and low in front of his hive; he leans over and flips its lid open, raises the giant
    spoon out beside him, its twelve wedges to us; one bee flies out to it, wrings her single drop into the bottom wedge
    and it fills; she flops on the rim; he gapes and pushes the spoon at us; eleven bees file out and queue behind it."""
    T_LID = 0.35                                  # his hand on the lid ...
    T_OPEN = 0.75                                 # ... it falls open (and the spoon comes up: arc 0.08)
    T_OUT = 0.25 * DUR                            # one bee flies out
    T_LAND = T_OUT + 0.7                          # ... and lands in the bowl
    T_DROP = 0.45 * DUR                           # her drop
    T_FULL = T_DROP + 0.5                         # one wedge full
    T_FLOP = 0.6 * DUR                            # she flops on the rim
    T_PUSH = T_FLOP + 0.5                         # he pushes the spoon at us: ONE wedge
    T_Q = 0.76 * DUR                              # eleven more file out
    T_SHRUG = T_Q + 0.6
    light, hives = place_hive_yard()
    hive = s2_hive("his hive", (-0.27, 0.04), hw_random.Random(5))
    data = load_data()
    P0 = Vector((0.08, -0.06, 0.0)); YAW = math.radians(-8)
    data.place(P0.x, P0.y, math.degrees(YAW))
    CAM = Vector((0.16, -1.28, 0.64)); LOOK = Vector((0.16, -0.08, 0.44))
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).x)        # [toward -X (the hive), toward +X]
    lid_side, sp_side = sides[0], sides[1]
    hat = bee_hat(data)
    W = hw_win
    # ---- his body: every beat of it a move you can see on a phone
    def body(t):
        p = P0.copy()
        p += Vector((-0.04, 0.04, 0)) * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35))           # leans over the hive for the lid
        p += Vector((0.05, -0.03, 0)) * W(t, T_OPEN, 0.4)                                    # steps out, the spoon up
        p += Vector((-0.04, 0.0, 0)) * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))   # ducks to the slot to see her out
        p.z -= 0.03 * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))
        p += Vector((0.06, -0.03, 0)) * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL + 0.05, 0.25))   # in close to the bowl for her drop
        p += Vector((0.07, -0.05, 0)) * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25))   # ... closer as it fills
        p.z -= 0.03 * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25))
        p += Vector((-0.03, 0.05, 0)) * hw_kick(t - T_FLOP, 0.18)                              # rocks back, gaping
        p.z += 0.025 * hw_kick(t - T_FLOP, 0.12)
        p += Vector((0.0, -0.06, 0)) * W(t, T_PUSH, 0.3) * (1 - W(t, T_Q + 0.2, 0.4))          # steps at us with the spoon
        p.z -= 0.02 * W(t, T_SHRUG, 0.25)
        p += Vector((0.04, 0.06, 0)) * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3))          # steps back to see the queue
        p += Vector((-0.03, -0.05, 0)) * W(t, T_SHRUG, 0.3)                                     # and comes to us for the shrug
        yaw = YAW - math.radians(6) * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35)) - math.radians(16) * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.45, 0.35)) \
            + math.radians(14) * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL, 0.3)) - math.radians(20) * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3))
        return p, yaw
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (7 * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35)) + 10 * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))
                                      + 12 * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL, 0.3)) + 10 * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25)) - 12 * hw_kick(t - T_FLOP, 0.2)
                                      + 8 * W(t, T_PUSH, 0.3) * (1 - W(t, T_Q, 0.4)) - 6 * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3)) + 10 * W(t, T_SHRUG, 0.3),
                                      0, -4 * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35))), 0, DUR + 0.4)
    for sd, sg in (("L", -1), ("R", 1)):          # the shrug: what can you do
        hw_layer(data, f"clav.{sd}", lambda t, sg=sg: (0, 0, sg * 20 * (W(t, T_SHRUG, 0.25) - W(t, T_SHRUG + 0.5, 0.3))), T_SHRUG - 0.1, DUR + 0.4)
    # ---- the lid: his hand lifts its front edge 30 degrees, then it falls open on its hinge
    hinge = hive["hinge"]
    ang = lambda t: math.radians(30) * W(t, T_LID + 0.1, T_OPEN - T_LID - 0.1) + math.radians(85) * W(t, T_OPEN, 0.25) \
        - math.radians(8) * hw_kick(t - T_OPEN - 0.25, 0.1)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; hinge.rotation_euler = (-ang(t), 0, 0); hinge.keyframe_insert("rotation_euler", frame=f)
    D = hive["D"]; hz = hive["top"]; hy = hinge.location.y
    def lid_front(t):                              # the lid's front edge by his side, where his fingers are
        a = ang(t); return Vector((hinge.location.x + 0.085, hy - (D + 0.02) * math.cos(a), hz + 0.05 + (D + 0.02) * math.sin(a)))
    # ---- the spoon: keyed in the world, his hand rides its grip
    spoon = s2_spoon("giant spoon")
    sr = spoon["root"]
    def spoon_at(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, sp_side)
        lo = sh + fw * 0.05 + out * 0.06 + Vector((0, 0, -0.14))                 # down by his side at first
        hi = sh + fw * 0.12 + out * 0.09 + Vector((0, 0, -0.13))                    # held out: the bowl beside his shoulder
        push = sh + fw * 0.15 + out * 0.06 + Vector((0, 0, -0.08))                # pushed at us
        g = lo.lerp(hi, W(t, T_OPEN - 0.1, 0.5)).lerp(push, W(t, T_PUSH, 0.35) * (1 - W(t, T_Q + 0.25, 0.4)))
        tilt = math.radians(34) * W(t, T_OPEN - 0.1, 0.5) - math.radians(8) * W(t, T_PUSH, 0.35)
        return g, tilt
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; g, tilt = spoon_at(t)
        yaw = data.arm.rotation_euler.z
        sr.location = g; sr.rotation_euler = (math.radians(-10), tilt, yaw + math.radians(10)); sr.keyframe_insert("location", frame=f); sr.keyframe_insert("rotation_euler", frame=f)
    grip = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), Vector(sr.matrix_world.translation) + sr.matrix_world.to_3x3() @ Vector((0, 0, 0.04)))[2]
    bowl = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), sr.matrix_world @ spoon["center"])[2]
    data.reach(sp_side, grip, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    tl = [T_LID + 0.1 + k * (T_OPEN - T_LID - 0.1) / 3 for k in range(4)]
    FK = [(0.0, (0.04, 0.07, -0.14))] + [(t, hw_rel(data, lid_side, t, lid_front(t) + Vector((0.0, -0.02, 0.02)))) for t in tl]
    le = Vector(FK[-1][1])
    FK += [(T_OPEN + 0.3, tuple(le.lerp(Vector((0.07, 0.1, -0.09)), 0.5) + Vector((0.02, 0.01, 0)))), (T_OPEN + 0.6, (0.07, 0.1, -0.09)), (T_DROP - 0.15, (0.06, 0.09, -0.11)), (T_DROP + 0.35, (0.11, 0.04, -0.02)), (T_FLOP - 0.1, (0.07, 0.08, -0.1)), (T_FLOP + 0.45, (0.1, 0.11, 0.05)),
           (T_PUSH + 0.35, (0.06, 0.12, -0.06)), (T_SHRUG, (0.06, 0.1, -0.1)), (T_SHRUG + 0.3, (0.08, 0.13, -0.02)), (DUR + 0.3, (0.07, 0.12, -0.05))]
    data.reach(lid_side, hw_hand(data, lid_side, FK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- the bee: out of the slot, up to the bowl, in to its middle; she squeezes, the drop runs down, the wedge
    # fills; she rolls off onto the bottom rim on her back
    bee = worker_bee("the bee", s=2.4)
    br = bee["root"]
    slot = hive["slot"]
    land = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((0, -0.03, spoon["R"] * 0.55)))
    rim = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((0.0, -0.035, -spoon["R"] * 0.98)))
    side_rim = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((spoon["R"] * 0.95, -0.035, spoon["R"] * 0.2)))
    def bee_at(t):
        if t < T_OUT: return slot + Vector((0, 0.04, 0))
        if t < T_LAND:
            u = ease((t - T_OUT) / (T_LAND - T_OUT)); a = slot.lerp(land(T_LAND), u)
            return a + Vector((0.0, -0.22 * math.sin(math.pi * u), 0.1 * math.sin(math.pi * u)))     # out in front of him, in an arc
        if t < T_FLOP: return land(t)
        u = ease(min(1.0, (t - T_FLOP) / 0.3)); return land(t).lerp(side_rim(t), u) + Vector((0, 0, 0.03 * math.sin(math.pi * u)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = bee_at(t); br.location = p; br.keyframe_insert("location", frame=f)
        if t < T_LAND:
            q = bee_at(t + 1 / FPS) - p
            e = (-q).to_track_quat('Y', 'Z').to_euler() if q.length > 1e-4 else Euler((0, 0, 0))
        else:
            e = Euler((math.radians(-60), 0, data.arm.rotation_euler.z))               # head up the bowl, belly to it
            if t >= T_FLOP: e = Euler((math.radians(-60) + math.pi * W(t, T_FLOP, 0.3), 0, data.arm.rotation_euler.z))   # on her back
        br.rotation_euler = e; br.keyframe_insert("rotation_euler", frame=f)
        sq = 1.0 - 0.25 * math.sin(math.pi * min(1.0, max(0.0, (t - T_DROP + 0.25) / 0.5)))   # she squeezes it out
        br.scale = (1.0 + 0.15 * (1 - sq), sq, 1.0 + 0.1 * (1 - sq)); br.keyframe_insert("scale", frame=f)
    bee_buzz(bee, T_OUT - 0.1, T_LAND + 0.1, hz=7, amp=55)
    for pv, sg in bee["wings"]:
        pv.rotation_euler = (0, -sg * 0.5, 0); pv.keyframe_insert("rotation_euler", frame=F(T_LAND + 0.2))
        pv.rotation_euler = (0, -sg * 0.1, 0); pv.keyframe_insert("rotation_euler", frame=F(T_FLOP + 0.3))   # drooping
    drop = K.sph("her drop", (0, 0, 0), 0.016, K.mat("drop gold", "#F2A81E", rough=0.15, emit=0.35), seg=16, ring=10)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        u = min(1.0, max(0.0, (t - T_DROP) / 0.35))
        drop.location = (land(t) + (sr.matrix_world.to_3x3() @ Vector((0, 0.01, -0.04)))).lerp(rim(t) + (sr.matrix_world.to_3x3() @ Vector((0, 0.02, 0.05))), ease_in(u)); drop.keyframe_insert("location", frame=f)
        s = 0.0 if t < T_DROP - 0.15 else (1.0 if u < 1 else max(0.0, 1 - (t - T_DROP - 0.35) / 0.15))
        drop.scale = (max(0.01, s),) * 3; drop.keyframe_insert("scale", frame=f)
    fl = spoon["fill"]
    for t, s in ((0.0, 0.01), (T_DROP + 0.3, 0.01), (T_FULL, 1.04), (T_FULL + 0.12, 1.0)):
        fl.scale = (s, 1, s); fl.keyframe_insert("scale", frame=F(t))
    # ---- the queue: eleven more come out of the slot round BEHIND him and hang in a line from the spoon back over the
    # meadow, each waiting her turn
    queue = []
    for k in range(11):
        b = worker_bee(f"queue bee {k}", s=2.0); queue.append(b)
        def spot(t, k=k):
            return bowl(t) + Vector((0.08 + 0.02 * k, 0.06 + 0.07 * k, 0.07 + 0.04 * k + 0.015 * math.sin(1.3 * k)))
        t_go = T_Q + 0.05 * k; dur = 0.5 + 0.03 * k
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            v = W(t, t_go, dur)
            a = slot + Vector((0, 0.1, 0.05)); z = spot(t)
            p = a.lerp(z, v) + Vector((0, 0.35 * math.sin(math.pi * v), 0.25 * math.sin(math.pi * v))) + Vector((0, 0, 0.006 * math.sin(2 * math.pi * 1.6 * t + k)))
            b["root"].location = p; b["root"].keyframe_insert("location", frame=f)
            b["root"].rotation_euler = (0, 0, math.radians(150)); b["root"].keyframe_insert("rotation_euler", frame=f)
            s = 0.01 if t < t_go else 1.0
            b["root"].scale = (s, s, s); b["root"].keyframe_insert("scale", frame=f)
        bee_buzz(b, t_go, DUR + 0.2, hz=6.5 + 0.2 * k, amp=50)
    # ---- face and head
    data.look_at(lid_front(T_OPEN * 0.6), 0.0, max_yaw=40, max_pitch=30, blend=0.0)
    data.look_at(slot, T_OUT - 0.15, max_yaw=40, max_pitch=40, blend=0.15)                        # out she comes
    data.look_at(bowl(T_LAND), T_LAND - 0.25, max_yaw=40, max_pitch=40, blend=0.18)             # into his spoon
    data.look_at(rim(T_FULL), T_FULL - 0.25, max_yaw=40, max_pitch=40, blend=0.15)               # the one wedge
    data.look_at(CAM, T_FLOP + 0.15, max_yaw=45, blend=0.15)                                   # at us, gaping
    data.look_at(bowl(DUR) + Vector((0.4, 0.6, 0.1)), T_Q + 0.2, max_yaw=40, max_pitch=40, blend=0.18)   # the queue
    data.look_at(CAM, T_SHRUG - 0.05, max_yaw=45, blend=0.2)
    data.expression("pleased", 0.0, T_LAND - 0.05)
    data.expression("determined", T_LAND, T_FLOP - 0.05, blend=0.15)
    data.expression("surprised", T_FLOP, T_Q - 0.05, blend=0.1)
    data.expression("worried", T_Q, DUR + 1.0, blend=0.18)
    data.finish()
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=21, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.06, 0.1, 0.0)) * ease(t / DUR), LOOK, Vector((0.1, -0.2, 0.5))))
    return dict(lanes=[], kiosks=[], place="hive_yard", light=light, data=data, rest=1, grips=("giant spoon", "his hive lid"),
                conseq=[("one bee's single drop fills one of the spoon's twelve wedges", lambda: meshes([sr, br]), T_LAND, DUR, {"hero": True}),
                        ("he flips his hive's lid open", lambda: [o for o in bpy.data.objects if o.name.startswith("his hive") and o.type == "MESH"], T_LID, T_OPEN + 0.4),
                        ("eleven more bees queue in the air", lambda: meshes([b["root"] for b in queue]), T_Q + 0.7, DUR)])


# ====================================================================================================
# shot3.py
# ====================================================================================================
"""BEAT 3, TWICE ROUND THE EARTH: the yard outside his honey house. He rolls a world globe as big as he is along
the path; a bee lifts off his hat and flies a glowing gold trail round the rolling globe once, then a second time; he
stops, snatches his empty one-pound jar off the stump, and the trail swoops into it and it fills gold in his hands (for
one pound of honey the hive's bees fly about 55,000 miles, more than twice round the Earth)."""

S3_R = 0.24                        # the globe's radius: up to his chest
S3_X0, S3_X1 = -0.62, 0.02         # where his feet start and stop along the path
S3_GO = 0.35                       # the globe's centre ahead of him


def s3_globe(name, R):
    """a big world globe ball: blue seas, raised green and sand continents, a thin gold equator. Returns dict(root,
    spin): key root.location to move it, spin.rotation_euler to roll it."""
    root = K.empty(name, (0, 0, 0))
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    sea = hw_noise("globe sea", "#2D6DAE", "#4B8DC9", scale=5, rough=0.3, bump=0.08)
    K.sph(name + " ball", (0, 0, 0), R, sea, seg=64, ring=32, parent=spin)
    rnd = hw_random.Random(7)
    lands = [hw_noise(f"globe land {c_}", c_, K.mute(c_, 0.8), scale=30, rough=0.6, bump=0.4) for c_ in ("#5E9A4A", "#7FAE56", "#C9B07A", "#8FB060")]
    for k in range(34):
        th = rnd.uniform(-1.1, 1.1); ph = rnd.uniform(0, 2 * math.pi)
        if 0.6 < ph < 1.3: continue
        n = Vector((math.cos(th) * math.cos(ph), math.cos(th) * math.sin(ph), math.sin(th)))
        o = K.sph(name + " land", tuple(n * (R * 0.985)), R * rnd.uniform(0.16, 0.3), rnd.choice(lands), scale=(1.0, 0.75, 0.1), seg=20, ring=10, parent=spin)
        o.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
    bpy.ops.mesh.primitive_torus_add(major_radius=R * 1.003, minor_radius=0.004, major_segments=96, minor_segments=6, location=(0, 0, 0))
    eq = bpy.context.active_object; eq.name = name + " equator"; eq.data.materials.append(K.mat("globe gold line", "#E2B649", rough=0.3, metal=0.8))
    eq.parent = spin
    for k in range(2):                         # the two ice caps
        K.sph(name + " ice", (0, 0, (1 if k else -1) * R * 0.97), R * 0.28, K.mat("globe ice", "#F2F5F8", rough=0.5), scale=(1, 1, 0.25), seg=24, ring=10, parent=spin)
    hw_local(root)
    return dict(root=root, spin=spin)


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


def shot3():
    """TWICE ROUND THE EARTH. The lens three-quarter in front of him at his chest height; he leans into a world globe as
    big as he is and rolls it along his path; a bee lifts off his hat and flies a glowing gold trail round the rolling
    globe, once, twice; he stops it, snatches his empty pound jar off the stump and holds it up, the trail swoops into it
    and it fills gold in his hands."""
    T_OFF = 0.08 * DUR                          # the bee lifts off his hat
    T_W0 = 0.25                                 # he starts rolling
    T_L2 = 0.55 * DUR                           # twice round
    T_W1 = T_L2 - 0.1                           # he stops it
    T_GRAB = T_L2 + 0.2                         # the jar off the stump
    T_IN = 0.75 * DUR                           # the trail swoops in
    T_FULL = 0.9 * DUR
    light = place_honey_house()
    G = s3_globe("big globe", S3_R)
    gr, gs = G["root"], G["spin"]
    data = load_data()
    YAW = math.radians(90)                      # facing +X, along the path
    data.place(S3_X0, 0.0, math.degrees(YAW))
    hat = bee_hat(data)
    W = hw_win
    walk = lambda t: S3_X0 + (S3_X1 - S3_X0) * (ease((t - T_W0) / (T_W1 - T_W0)) if T_W0 < t < T_W1 else (0.0 if t <= T_W0 else 1.0))
    data.walk_to(Vector((S3_X1, 0.0, 0.0)), T_W0, T_W1, pushing=True)
    # the globe rolls ahead of his hands: no slip, a little wobble
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; x = walk(t) + S3_GO
        gr.location = (x, 0.0, S3_R + 0.012); gr.keyframe_insert("location", frame=f)
        gs.rotation_euler = (0.03 * math.sin(2 * math.pi * t / 1.3), (x - S3_X0 - S3_GO) / S3_R, 0.0); gs.keyframe_insert("rotation_euler", frame=f)
    gc = lambda t: Vector((walk(t) + S3_GO, 0.0, S3_R + 0.012))
    # his body over it: leaning in to push, then up and round to the stump, the jar held up, a hop when it is full
    hw_layer(data, "spine", lambda t: (8 * W(t, 0.0, 0.3) * (1 - W(t, T_W1, 0.3)) + 4 * math.sin(2 * math.pi * (t - T_W0) / 0.55) * W(t, T_W0, 0.2) * (1 - W(t, T_W1, 0.2))
                                      - 8 * W(t, T_IN - 0.4, 0.3) * (1 - W(t, T_FULL, 0.3)), 0,
                                      0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).y)       # [toward -Y: the lens, toward +Y]
    near, far = sides                                                   # the jar in his near hand, the far one rolls it
    end_yaw = YAW - math.radians(30)                                  # turns to us with the jar
    sc.frame_set(F(T_W1)); bpy.context.view_layer.update()
    for f in range(F(T_W1), NF + 1):
        t = (f - 1) / FPS
        data._kobj(t, loc=(S3_X1 - 0.03 * W(t, T_IN - 0.4, 0.4) * (1 - W(t, T_FULL, 0.3)), 0.0, 0.035 * hw_kick(t - T_FULL, 0.15) + 0.04 * hw_kick(t - T_IN - 0.3, 0.12)),
                   rot=YAW + (end_yaw - YAW) * W(t, T_W1, 0.6) + math.radians(10) * W(t, T_FULL - 0.1, 0.3) - math.radians(14) * W(t, T_IN, 0.35) * (1 - W(t, T_IN + 0.4, 0.35)))
    # the jar: his empty pound jar in his near hand all along; held up for the trail
    pj = jar("pound jar", (0, 0, 0), r=0.065, h=0.15, fill=0.88, honey_col="#F0B030", label="1 lb", glow=1.5)
    jr = pj["root"]
    def jar_at(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, near)
        lo = sh + fw * 0.07 + out * 0.12 + Vector((0, 0, -0.2))
        hi = sh + fw * 0.11 + out * 0.13 + Vector((0, 0, -0.12))
        return lo.lerp(hi, W(t, T_GRAB, 0.6)) + Vector((0.0, -0.04, 0.05)) * W(t, T_IN - 0.15, 0.7)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = jar_at(t); p.z += 0.012 * hw_kick(t - T_IN, 0.1) + 0.006 * math.sin(2 * math.pi * (t - T_W0) / 0.55) * W(t, T_W0, 0.2) * (1 - W(t, T_W1, 0.2))
        jr.location = p; jr.keyframe_insert("location", frame=f)
        jr.rotation_euler = (0, 0, data.arm.rotation_euler.z - math.radians(80)); jr.keyframe_insert("rotation_euler", frame=f)
    hon = pj["honey"]
    for t, s_ in ((0.0, 0.02), (T_IN + 0.05, 0.02), (T_FULL, 1.0)):
        hon.scale = (1, 1, s_); hon.keyframe_insert("scale", frame=F(t))
        hon.location.z = pj["hz"] * s_ / 2 + 0.002; hon.keyframe_insert("location", frame=F(t))   # it fills from the bottom
    # ---- hands: both on the globe's back while he rolls it; the near one to the jar; the far one up when it fills
    on_g = lambda t: gc(t) + Vector((-S3_R * 0.78, 0.06, 0.15))
    gripj = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), jr.matrix_world.translation + Vector((0, 0, 0.04)))[2]
    data.reach(near, gripj, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    data.reach(far, on_g, 0.0, T_W1 + 0.1, lead=0.05, back=None, elbow_out=0.35)
    fk = [(T_W1 + 0.1, hw_rel(data, far, T_W1 + 0.1, on_g(T_W1 + 0.1))), (T_W1 + 0.6, (0.07, 0.09, -0.1)), (T_IN + 0.15, (0.06, 0.13, 0.02)),
          (T_FULL - 0.15, (0.08, 0.1, -0.07)), (T_FULL + 0.35, (0.08, 0.12, 0.08)), (DUR + 0.3, (0.08, 0.12, 0.06))]
    data.reach(far, hw_hand(data, far, fk), T_W1 + 0.1, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- the bee and her trail: off his hat, twice round the rolling globe, then into the jar
    bee = worker_bee("trail bee", s=1.8)
    br = bee["root"]
    orb = S3_R + 0.07
    def orbit(u, t):                            # u in loops; the loop faces the lens a little so it reads round
        a = 2 * math.pi * u + math.radians(110)
        e1 = Vector((0.57, 0.82, 0.0))         # a loop standing at 55 degrees to the path: it faces the lens, clear of him
        r = orb + 0.03 * min(u, 2.0) / 2.0     # the second ring a little wider, so two rings read
        return gc(t) + e1 * (r * math.cos(a)) + Vector((0, 0, r * math.sin(a)))
    def bee_at(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        wo = hat["worn"]; bb = [wo.matrix_world @ Vector(c_) for c_ in wo.bound_box]
        top = sum(bb, Vector()) / 8; top.z = max(b.z for b in bb) + 0.03
        if t < T_OFF: return top
        if t < T_OFF + 0.4:
            u = ease((t - T_OFF) / 0.4); return top.lerp(orbit(0.0, t), u) + Vector((0, 0, 0.08 * math.sin(math.pi * u)))
        if t < T_L2: return orbit(2.0 * (t - T_OFF - 0.4) / (T_L2 - T_OFF - 0.4), t)
        jt = jr.matrix_world.translation + Vector((0, 0, 0.12))
        if t < T_IN:
            u = ease((t - T_L2) / (T_IN - T_L2)); return orbit(2.0, t).lerp(jt, u) + Vector((0, -0.12 * math.sin(math.pi * u), 0.05 * math.sin(math.pi * u)))
        u = min(1.0, (t - T_IN) / 0.3); return jt.lerp(jt + Vector((0.02, -0.08, -0.02)), ease(u))
    pts = []
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = bee_at(t); br.location = p; br.keyframe_insert("location", frame=f); pts.append(p.copy())
    for f in range(1, NF + 1):
        q = pts[min(NF - 1, f)] - pts[f - 1]
        if q.length > 1e-4:
            br.rotation_euler = (-q).to_track_quat('Y', 'Z').to_euler(); br.keyframe_insert("rotation_euler", frame=f)
    bee_buzz(bee, 0.0, DUR + 0.3, hz=7, amp=55)
    # the trail rides the globe: drawn in its (unspun) frame, so the two rings she flew stay wrapped round it as it
    # rolls and the picture reads "twice round the Earth"; the globe has stopped before she leaves it for the jar
    tf0, tf1 = F(T_OFF + 0.05), F(T_IN)
    cu = bpy.data.curves.new("gold trail", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.005; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(tf1 - tf0)
    for i, f in enumerate(range(tf0, tf1 + 1)):
        p = pts[f - 1] - gc((f - 1) / FPS); sp.points[i].co = (p.x, p.y, p.z, 1)
    trail = bpy.data.objects.new("gold trail", cu); bpy.context.collection.objects.link(trail); trail.parent = gr
    cu.materials.append(K.mat("trail gold", "#FFC23A", rough=0.3, emit=4.0))
    for f in range(1, NF + 1):
        cu.bevel_factor_end = min(1.0, max(0.0, (f - tf0) / max(1, tf1 - tf0))); cu.keyframe_insert("bevel_factor_end", frame=f)
        cu.bevel_factor_start = min(0.999, max(0.0, (f - F(T_FULL)) / 10.0)); cu.keyframe_insert("bevel_factor_start", frame=f)
    # ---- face and head
    LENS = Vector((0.45, -1.4, 0.62))
    data.look_at(gc(0.0) + Vector((0, 0, 0.1)), 0.0, max_yaw=40, max_pitch=40, blend=0.0)
    data.look_at(gc(T_OFF) + Vector((-0.2, 0, 0.6)), T_OFF - 0.05, max_yaw=40, max_pitch=45, blend=0.12)   # up: she lifts off
    data.look_at(LENS, T_OFF + 0.7, max_yaw=45, blend=0.2)                                             # at us, pushing
    data.look_at(orbit(1.5, T_L2 - 0.6) + Vector((0, 0, 0.25)), T_L2 - 0.7, max_yaw=40, max_pitch=40, blend=0.2)
    data.look_at(jar_at(T_IN) + Vector((0, 0, 0.1)), T_IN - 0.35, max_yaw=40, max_pitch=40, blend=0.18)
    data.look_at(LENS, T_FULL + 0.05, max_yaw=45, blend=0.18)
    data.expression("determined", 0.0, T_OFF - 0.05)
    data.expression("surprised", T_OFF, T_OFF + 0.9, blend=0.1)
    data.expression("pleased", T_OFF + 1.0, T_IN - 0.1, blend=0.18)
    data.expression("happy", T_FULL - 0.1, DUR + 1.0, blend=0.18)
    data.finish()
    cam = K.camera(tuple(LENS), (-0.05, 0.05, 0.42), lens=28.5, fstop=7.0)
    push = lambda t: W(t, T_L2, T_FULL - T_L2)
    lx = lambda t: walk(t) + 0.12
    camera_path(cam, lambda t: (Vector((lx(t) + 0.85, -1.2, 0.56)) + (jar_at(T_FULL) - LENS).normalized() * 0.4 * push(t),
                                Vector((lx(t), 0.05, 0.42)).lerp(jar_at(T_FULL) + Vector((0, 0, 0.05)), 0.5 * push(t)), gc(t).lerp(jar_at(T_FULL), 0.6 * push(t))))
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("pound jar", "big globe"),
                conseq=[("the gold trail goes twice round the rolling globe", lambda: meshes([gr, trail]), T_OFF + 0.5, T_L2 + 0.3, {"hero": True}),
                        ("he rolls the globe along the path", lambda: meshes([gr]), T_W0, T_W1, {"moves": True}),
                        ("the trail swoops into his pound jar and it fills gold", lambda: meshes([jr, br]), T_IN - 0.2, DUR)])


# ====================================================================================================
# shot4.py
# ====================================================================================================
def shot4():
    raise SystemExit('shot4.py not built yet')


def place_museum_tomb():
    pass


# ====================================================================================================
# shot5.py
# ====================================================================================================
def shot5():
    raise SystemExit('shot5.py not built yet')


def place_market_alley():
    pass


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
