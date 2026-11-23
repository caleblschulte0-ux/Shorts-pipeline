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
from mathutils import Matrix as HW_M, Quaternion as HW_Q


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
        ink="#5A3A12", back=None, back_col="#C8261E", back_ink="#FFFFFF", lid_col="#C9A04A", yaw=0.0, parent=None):
    """a glass honey jar standing on its base at `loc`: glass, the honey in it (`fill` of the height), a gold lid, and a
    paper label on its front (-Y). back=<text>: a second label on its BACK, <text> in white on red; jar_flip() spins
    the jar round to show it. Returns dict(root, spin, glass, honey, label, back, r, h, hz)."""
    root = K.empty(name, loc, parent=parent); root.rotation_euler = (0, 0, yaw)
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    g = K.cyl(name + " glass", (0, 0, h / 2), r, h, hw_glass(), v=40, bev=0.006, parent=spin)
    hm = hw_honey(f"hw honey {honey_col}", honey_col)
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
def shot2():
    raise SystemExit('shot2.py not built yet')


def place_hive_yard():
    pass


# ====================================================================================================
# shot3.py
# ====================================================================================================
def shot3():
    raise SystemExit('shot3.py not built yet')


def place_honey_house():
    pass


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
