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
import compose        # frame-first placement (store/compose.py): Data framed by the lens, signs and props by their screen box
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
    # the brim is narrow and turned UP at the front (board 2026-11-23: "the hat brim hides his face", shots 3 and 5,
    # "his head bowed under it"): from any lens at or above his eyes the face reads under it
    A = (0.146, 0.118); B = (0.225, 0.2); H = 0.1; n = 60
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
            front = max(0.0, -math.sin(th)) ** 1.5                       # the front (-Y) turns up off his eyes
            verts.append(((A[0] + (B[0] - A[0]) * u) * math.cos(th), (A[1] + (B[1] - A[1]) * u) * math.sin(th),
                          HW_HAT_ZB - 0.022 * u ** 2.2 * (1 - front) + 0.06 * u ** 1.4 * front))
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


# ---------------------------------------------------------------- cobbles that read as cobbles
def hw_cobbles(name="hw cobbles", a="#8C8174", b="#ABA08E", joint="#4E463E", scale=14.0):
    """a cobbled ground as ONE material (board 2026-11-23: rows of spheres "read as grey polka-dot fabric"): Voronoi
    stones, each its own tint between a and b, dark sunken joints between them, a rounded bump on every stone"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.85
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale * 1.25, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    vc = nt.nodes.new("ShaderNodeTexVoronoi"); vc.feature = 'F1'; vc.inputs["Randomness"].default_value = 0.85
    ve = nt.nodes.new("ShaderNodeTexVoronoi"); ve.feature = 'DISTANCE_TO_EDGE'; ve.inputs["Randomness"].default_value = 0.85
    for v in (vc, ve): nt.links.new(mp.outputs["Vector"], v.inputs["Vector"])
    tint = nt.nodes.new("ShaderNodeValToRGB"); tint.color_ramp.elements[0].color = (*K.lin(a), 1); tint.color_ramp.elements[1].color = (*K.lin(b), 1)
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(vc.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[0], tint.inputs["Fac"])
    edge = nt.nodes.new("ShaderNodeMapRange"); edge.inputs["From Min"].default_value = 0.02; edge.inputs["From Max"].default_value = 0.12
    nt.links.new(ve.outputs["Distance"], edge.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMixRGB"); mix.inputs["Color1"].default_value = (*K.lin(joint), 1)
    nt.links.new(edge.outputs["Result"], mix.inputs["Fac"]); nt.links.new(tint.outputs["Color"], mix.inputs["Color2"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 90
    dirt = nt.nodes.new("ShaderNodeMixRGB"); dirt.blend_type = 'MULTIPLY'; dirt.inputs["Fac"].default_value = 0.18
    nt.links.new(mix.outputs["Color"], dirt.inputs["Color1"]); nt.links.new(nz.outputs["Fac"], dirt.inputs["Color2"])
    nt.links.new(dirt.outputs["Color"], bs.inputs["Base Color"])
    dome = nt.nodes.new("ShaderNodeMath"); dome.operation = 'SQRT'; nt.links.new(edge.outputs["Result"], dome.inputs[0])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.7; bp.inputs["Distance"].default_value = 0.02
    nt.links.new(dome.outputs["Value"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def hw_person(name, loc, yaw=0.0, coat="#2F6FA6", legs="#33363C"):
    """a villager, still MINIMAL (caaleb 2026-11-11, person() in store/shots.py): faceless, head, body, tube arms, two
    legs; only the coat's colour is the village's own instead of the store's staff blue (board: "big blue blobs")"""
    root = person(name, loc, yaw)
    cm = K.mat(f"villager coat {coat}", coat, rough=0.7); lm = K.mat(f"villager legs {legs}", legs, rough=0.65)
    for o in root.children:
        if o.name.startswith(("body", "arm")): o.data.materials.clear(); o.data.materials.append(cm)
        elif o.name.startswith("leg"): o.data.materials.clear(); o.data.materials.append(lm)
    return root


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


def hw_named(*prefixes):
    """every drawn object whose name starts with one of the prefixes (a sign's board, its words, its strings)"""
    return [o for o in bpy.data.objects if o.type in ('MESH', 'FONT', 'CURVE', 'EMPTY') and o.name.startswith(prefixes) and o.parent is None]


def hw_drawn(*prefixes):
    return [o for o in bpy.data.objects if o.type in ('MESH', 'FONT', 'CURVE') and o.name.startswith(prefixes)]


# ====================================================================================================
# shot1.py
# ====================================================================================================
"""BEAT 1, THE HOOK: the cheap stall in the market square. Eleven identical jars of PURE HONEY under a 2 EUROS sign;
the beekeeper slams his dipper on the counter, the row jumps, and only one of the seven labels flips over to a red SYRUP
(46% of the EU's imported samples: almost half)."""

S1_FAKES = (3,)                     # the one jar in seven the old test catches (0 = the one nearest the lens)
S1_N = 7
S1_CH = 0.18                         # the counter's top: his waist


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
    cob = hw_cobbles("square cobbles", "#93877A", "#B5A992", scale=6)
    K.box("square ground", (0, 6, -0.01), (40, 40, 0.02), cob, bev=0)
    wood = hw_wood("stall planks", "#8A6440", "#A47C52")
    old = hw_wood("crate wood", "#9A7A52", "#B89468", scale=4)
    # the cheap stall: a plank counter along X with a front skirt, two posts, the awning over it, a sign on top
    # a trestle counter across the lens (board: "turn the counter so all seven jars sit side by side across the
    # frame"), open underneath so he is whole behind it; the sign hangs from the awning over the jars, in frame
    K.box("stall counter", (0.06, -0.08, S1_CH - 0.02), (1.16, 0.4, 0.04), wood, bev=0.004)
    for x in (-0.42, 0.54):
        for y in (-0.25, 0.09):
            K.box("trestle leg", (x, y, (S1_CH - 0.04) / 2), (0.03, 0.03, S1_CH - 0.04), old, bev=0.003)
        K.box("trestle brace", (x, -0.08, 0.06), (0.025, 0.34, 0.025), old, bev=0.002)
    for x in (-0.56, 0.68):
        K.box("stall post", (x, 0.3, 0.6), (0.04, 0.04, 1.2), old, bev=0.004)
    s1_awning("stall awning", -0.66, 0.78, 0.05, 0.45, 1.36, 1.24, "#C23A2E", "#F1E6CC", n=8)
    sign = K.box("price sign", (0.06, 0.06, 1.01), (0.72, 0.02, 0.15), K.mat("sign board", "#F4EEDC", rough=0.7), bev=0.006)
    K.text("price sign text", "PURE HONEY  2 EUROS", (0.06, 0.048, 1.01), 0.05, (math.pi / 2, 0, 0), hw_ink("sign paint", "#B0261C"), extrude=0.001)
    for x in (-0.22, 0.34):
        K.cyl("sign string", (x, 0.06, 1.13), 0.0015, 0.1, K.mat("string", "#5A4A3A"), bev=0)
    # stock under and behind the counter: crates of the same cheap jars
    for k, x in enumerate((-0.4, 0.0)):
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
    coats = ("#B5543C", "#4E7A5A", "#C9A24A", "#6A5A8E", "#3E6E9E", "#A04A6A", "#7A8A3A")
    for k, (x, y, yaw) in enumerate(((3.3, -0.3, math.pi / 2), (3.4, 1.4, math.pi / 2 + 0.4), (-2.2, 3.4, math.pi - 0.4),
                                      (-0.9, 3.5, math.pi), (1.6, 3.6, math.pi + 0.3), (0.4, 3.9, math.pi - 0.2), (2.6, 3.2, math.pi + 0.6))):
        hw_person(f"shopper {k}", (x, y, 0), yaw=yaw, coat=coats[k])          # far off, across the square, in their own clothes
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
    for k, (x, y) in enumerate(((1.25, -0.3), (1.2, 0.05))):            # produce crates stacked by the next stall (not sacks: "egg-like balls")
        s1_crate(f"produce crate {k}", (x, y, 0.0), (0.34, 0.26, 0.16), ("#C8352A", "#7FAE3A")[k], old, rnd)
        s1_crate(f"produce crate {k} top", (x, y, 0.17), (0.34, 0.26, 0.16), ("#E58A1F", "#D8C04A")[k], old, rnd)
    # bunting across the square
    flagm = [K.mat(f"bunting {c}", c, rough=0.7) for c in ("#C23A2E", "#E8B33A", "#3E6E9E", "#3F7D4E")]
    for k in range(40):
        fx = -4 + k * 0.2; fz = 2.0 - 0.25 * math.sin(math.pi * k / 39)
        fl = K.box("bunting", (fx, 4.4, fz), (0.1, 0.004, 0.12), flagm[k % 4], bev=0); fl.rotation_euler = (0, 0, 0)

    def light():
        return village_light(sun_elev=40, sun_az=-35, sun=3.8, sky=0.35)
    return light


def shot1():
    """THE CHEAP STALL. The lens square on the trestle counter, seven identical PURE HONEY jars side by side across the
    frame under the 2 EUROS sign, the beekeeper behind them at the right: he leans in and peers along them, frowns up at
    the sign, raises his dipper and SLAMS it on the counter; the row jumps, and the middle jar spins round to a big red
    SYRUP; he jumps back, then leans in and points his dipper at the six others, not convinced."""
    T_PEER = 0.1                                  # leaning in along the row
    T_SIGN = 0.5                                 # straightening up to the sign
    T_UP = 0.8                                   # the dipper goes up ...
    T_SLAM = 0.3 * DUR                            # ... and down on the counter
    T_FLIP = [0.45 * DUR + k * (0.17 * DUR) / 4 for k in range(5)]
    T_BACK = T_FLIP[0] - 0.05                     # he jerks back at the red label
    T_LEAN = T_FLIP[-1] + 0.1                     # leans in over the row
    T_POINT = 0.82 * DUR                          # points along the others at us
    light = place_market_stall()
    data = load_data()
    YAW = 0.0                                     # facing the lens, behind the counter
    data.place(0.3, 0.2, 0.0)
    CAM = Vector((-0.62, -0.98, 0.72)); LOOK = Vector((0.06, -0.04, 0.42))    # above the row, three-quarter: seven jars running to him
    HIT = Vector((0.55, 0.04, S1_CH + 0.11))      # his fist over the counter's right end: the dipper's head on the planks
    side = max("LR", key=lambda s: acts._shoulder(data, s).x)        # the hand on the slam's side
    fw = data.forward(); out = acts._shoulder(data, side) - data.pos(); out.z = 0; out = (out - fw * out.dot(fw)).normalized()
    P0 = Vector((HIT.x, HIT.y, 0)) - fw * 0.17 - out * 0.12
    data.place(P0.x, P0.y, 0.0)
    hat = bee_hat(data)
    # the jars: seven across the counter, labels to the lens; the one fake (the middle one) has a red back label
    jars = []
    for k in range(S1_N):
        x = -0.27 + k * 0.112
        fake = k in S1_FAKES
        jars.append(jar(f"stall jar {k}", (x, -0.2, S1_CH), r=0.05, h=0.17, fill=0.9, honey_col="#E6A52A" if fake else "#D98A12",
                        label="PURE HONEY", back="SYRUP" if fake else None, yaw=math.radians(-34), glow=0.3))      # labels turned toward the lens
    fakes = [jars[k] for k in S1_FAKES]
    jar_flip(fakes[0], T_FLIP[0])                 # only one in seven flips
    for k, j in enumerate(jars):                  # the row JUMPS at the slam, a hop running down from his end
        r = j["root"]; z0 = r.location.z; d = (S1_N - 1 - k) * 0.012; yw = r.rotation_euler.z; sg = 1 if k % 2 else -1
        for t, dz, tilt in ((0.0, 0, 0), (T_SLAM + d, 0, 0), (T_SLAM + d + 0.08, 0.05, 0.12 * sg), (T_SLAM + d + 0.17, 0.0, -0.05 * sg),
                            (T_SLAM + d + 0.26, 0.01, 0.02 * sg), (T_SLAM + d + 0.36, 0, 0)):
            r.location.z = z0 + dz; r.keyframe_insert("location", frame=F(t))
            r.rotation_euler = (tilt, 0, yw); r.keyframe_insert("rotation_euler", frame=F(t))
    # ---- his body: peer, straighten, rise for the swing, dip into the slam, jerk back, lean in to point
    W = hw_win
    left = -out                                   # along the row, away from the slam end
    def body(t):
        p = P0.copy()
        p += (left * 0.06) * (W(t, T_PEER, 0.4) - W(t, T_SIGN, 0.3))                         # a step along the row ...
        p.z += 0.03 * W(t, T_UP - 0.1, 0.3) * (1 - W(t, T_SLAM - 0.08, 0.1))                  # up on his toes with the dipper high
        p.z -= 0.03 * hw_kick(t - T_SLAM + 0.02, 0.1)                                            # the slam drives him down
        p += (-fw * 0.07 + out * 0.03) * (W(t, T_BACK, 0.2) - W(t, T_LEAN, 0.4))                 # jerks back from the red label
        p.z += 0.05 * hw_kick(t - T_BACK, 0.13)                                                  # a hop of surprise
        p += left * 0.05 * W(t, T_LEAN, 0.4)                                                     # and leans in over the row
        p += fw * 0.04 * W(t, T_FLIP[2] - 0.15, 0.25) * (1 - W(t, T_LEAN - 0.1, 0.3))            # a double take at the red one
        p.z += 0.045 * hw_kick(t - T_FLIP[2] - 0.05, 0.13)
        yaw = YAW + math.radians(22) * W(t, T_PEER, 0.35) * (1 - W(t, T_SIGN, 0.3)) - math.radians(15) * W(t, T_SIGN, 0.3) * (1 - W(t, T_SLAM - 0.3, 0.25)) \
            + math.radians(15) * W(t, T_FLIP[2] - 0.15, 0.25) * (1 - W(t, T_POINT - 0.3, 0.3))
        return p, yaw
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (16 * W(t, T_PEER, 0.4) * (1 - W(t, T_SIGN, 0.3)) - 8 * W(t, T_UP - 0.1, 0.3) * (1 - W(t, T_SLAM - 0.1, 0.1))
                                      + 14 * W(t, T_SLAM - 0.15, 0.15) * (1 - W(t, T_BACK, 0.2)) - 10 * W(t, T_BACK, 0.2) * (1 - W(t, T_LEAN, 0.3))
                                      + 14 * W(t, T_LEAN, 0.35) * (1 - W(t, T_POINT + 0.25, 0.35)), 0,
                                      6 * math.sin(2 * math.pi * (t - T_LEAN) / 1.2) * W(t, T_LEAN, 0.3)), 0, DUR + 0.4)
    hw_layer(data, "chest", lambda t: (8 * W(t, T_PEER, 0.4) * (1 - W(t, T_SIGN, 0.3)) + 4 * W(t, T_SLAM - 0.15, 0.15) * (1 - W(t, T_BACK, 0.2)), 0, 0), 0, DUR + 0.4)
    # ---- the dipper hand and the free hand
    sc.frame_set(1); bpy.context.view_layer.update()
    free = "R" if side == "L" else "L"
    hit = hw_rel(data, side, T_SLAM, HIT)
    REST = (0.06, 0.07, -0.13)
    HK = [(0.0, REST), (T_PEER + 0.3, (0.1, 0.08, -0.09)), (T_SIGN + 0.15, (0.07, 0.13, -0.05)),
          (T_UP + 0.15, (0.02, 0.15, 0.07)), (T_SLAM - 0.28, (0.05, 0.15, 0.06)), (T_SLAM, hit),
          (T_SLAM + 0.2, (hit[0], hit[1], hit[2] + 0.03)), (T_BACK + 0.25, (0.12, 0.1, -0.02)), (T_FLIP[2] + 0.25, (0.15, 0.05, -0.01)),
          (T_LEAN + 0.35, (0.13, 0.09, -0.03)), (T_POINT, (0.14, 0.08, 0.02)), (T_POINT + 0.35, (0.14, 0.085, 0.045)), (DUR + 0.3, (0.14, 0.08, 0.03))]
    FK = [(0.0, (0.04, 0.07, -0.14)), (T_SIGN + 0.1, (0.04, 0.07, -0.14)), (T_BACK - 0.1, (0.05, 0.08, -0.13)), (T_BACK + 0.35, (0.1, 0.1, 0.04)), (T_FLIP[2] + 0.25, (0.12, 0.15, -0.05)),
          (T_LEAN + 0.2, (0.08, 0.12, 0.0)), (T_POINT, (0.03, 0.1, -0.1)), (DUR + 0.3, (0.03, 0.1, -0.11))]
    data.reach(side, hw_hand(data, side, HK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(free, hw_hand(data, free, FK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.3)
    # ---- face and head
    LENS = CAM
    data.look_at(jars[1]["root"].location + Vector((0, 0, 0.08)), 0.0, max_yaw=40, max_pitch=40, blend=0.0)
    data.look_at(Vector((0.06, 0.06, 0.86)), T_SIGN, max_yaw=40, max_pitch=40, blend=0.18)            # the 2 EUROS sign
    data.look_at(HIT, T_SLAM - 0.3, max_yaw=40, max_pitch=30, blend=0.12)
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
    # ---- the lens: square on the counter at jar height, a slow push in
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 27.5, face_at=(0.6, 0.66), height=0.33, t=0.5 * DUR)   # framed first: he stands behind the row's far end
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=27.5, fstop=7.0)
    camera_path(cam, lambda t: (CAM + (LOOK - CAM).normalized() * 0.02 * ease(t / DUR), LOOK, Vector((0.0, -0.1, 0.4))))
    compose.place(hw_named("price sign", "sign string"), cam, (0.03, 0.72, 0.97, 0.99), frame=NF, label="the 2 EUROS sign")   # whole, over the row, at the push's end
    return dict(lanes=[], kiosks=[], place="market_stall", light=light, data=data, rest=1, grips=("honey dipper",),
                boxes=[("the 2 EUROS sign", lambda: hw_drawn("price sign"), (0.0, 0.62, 1.0, 1.0)),
                       ("the seven jars", lambda: meshes([j["root"] for j in jars]), (0.0, 0.0, 1.0, 0.7))],
                conseq=[("he slams his dipper and only one of the seven jars spins round to a red SYRUP", lambda: meshes([j["root"] for j in jars]), T_FLIP[0], DUR, {"hero": True}),
                        ("the slam makes the whole row of jars jump", lambda: meshes([j["root"] for j in jars]), T_SLAM, T_SLAM + 0.5)])


# ====================================================================================================
# shot2.py
# ====================================================================================================
"""BEAT 3, A QUARTER OF THE PRICE: the yard outside his honey house. Two flagpoles beside a tall price board marked
in euros a kilo. Hand over hand he hoists the white RICE SYRUP flag: it stops at 0.50. Then he hoists the gold HONEY
flag and it climbs past 1.00, 1.50, 2.00 to 2.17, four times as high (DG SANTE: imported honey 2.17 EUR/kg in 2021,
rice syrup about 0.40-0.60 EUR/kg)."""

S3_Z0 = 0.3                            # the price board's zero: a flag's top edge reads its price against it
S3_PER = 0.36                          # metres per euro: 2.17 is 0.78 m up
S3_POLES = (Vector((-0.16, 0.34, 0.0)), Vector((0.3, 0.34, 0.0)))   # syrup pole, honey pole, the board behind both
S3_DATA = Vector((0.625, 0.17, 0.0))    # beside the honey pole, at its halyard


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
    # the honey house: a tall plank wall across the back with a deep-set window and an open door with a lit inside
    WY = 1.05
    plank = hw_noise("weathered planks", "#9C7A52", "#B8966A", scale=3, rough=0.85, bump=0.5, detail=6, stretch=(6, 1, 1))
    wx, wz, ww, wh = -1.05, 1.03, 0.74, 0.62          # out past the board: a window cut by the frame edge cuts its jars
    for k in range(34):
        xx = -2.6 + k * 0.155
        if 0.55 < xx < 0.95: continue                   # the open door
        if wx - ww / 2 - 0.08 < xx < wx + ww / 2 + 0.08: K.box("house plank", (xx, WY, 0.33), (0.15, 0.04, 0.66), plank, bev=0.006); K.box("house plank", (xx, WY, 1.84), (0.15, 0.04, 0.88), plank, bev=0.006); continue
        K.box("house plank", (xx, WY + rnd.uniform(-0.006, 0.006), 1.14), (0.15, 0.04, 2.28), plank, bev=0.006)
    trim = hw_wood("door trim", "#5E4026", "#74502E", scale=6)
    K.box("door post", (0.535, WY - 0.03, 0.68), (0.05, 0.06, 1.36), trim, bev=0.006)
    K.box("door post", (0.965, WY - 0.03, 0.68), (0.05, 0.06, 1.36), trim, bev=0.006)
    K.box("door lintel", (0.75, WY - 0.03, 1.38), (0.48, 0.06, 0.06), trim, bev=0.006)
    K.box("door top planks", (0.75, WY, 1.84), (0.46, 0.04, 0.88), plank, bev=0.006)
    inside = K.mat("inside wall", "#8A6A48", rough=0.9)
    K.box("inside back wall", (0.75, WY + 0.6, 0.8), (0.6, 0.02, 1.6), inside, bev=0)
    K.box("inside floor", (0.75, WY + 0.3, 0.005), (0.6, 0.6, 0.01), K.mat("inside floor", "#5A4430", rough=0.9), bev=0)
    for z in (0.5, 0.8, 1.1):
        K.box("inside shelf", (0.75, WY + 0.52, z), (0.5, 0.14, 0.02), hw_wood("inside shelf", "#7A5A38", "#946E46"), bev=0.003)
        for k in range(5):
            jar(f"inside jar {z} {k}", (0.57 + k * 0.09, WY + 0.5, z + 0.012), r=0.03, h=0.08, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY")
    lamp = K.sph("inside lamp", (0.75, WY + 0.3, 1.3), 0.04, K.mat("inside lamp", "#FFE2A0", rough=0.3, emit=4.0))
    door = K.box("open door", (0.98, WY - 0.2, 0.67), (0.04, 0.42, 1.3), hw_wood("door wood", "#6E4A2A", "#8A5E36"), bev=0.006)
    K.sph("door knob", (0.955, WY - 0.36, 0.68), 0.018, K.mat("knob brass", "#C8A040", rough=0.3, metal=0.8))
    frame_m = K.mat("window frame", "#EEE8DA", rough=0.4)
    for dx, sx in ((-ww / 2, 0.05), (ww / 2, 0.05)):
        K.box("window jamb", (wx + dx, WY - 0.02, wz), (sx, 0.1, wh + 0.05), frame_m, bev=0.006)
    K.box("window head", (wx, WY - 0.02, wz + wh / 2), (ww + 0.05, 0.1, 0.05), frame_m, bev=0.006)
    K.box("window sill", (wx, WY - 0.08, wz - wh / 2 - 0.01), (ww + 0.14, 0.18, 0.035), frame_m, bev=0.006)
    K.box("window back", (wx, WY + 0.28, wz), (ww, 0.02, wh), K.mat("window room", "#6E5238", rough=0.9), bev=0)
    K.box("window reveal", (wx - ww / 2 + 0.01, WY + 0.13, wz), (0.02, 0.3, wh), inside, bev=0)
    K.box("window reveal", (wx + ww / 2 - 0.01, WY + 0.13, wz), (0.02, 0.3, wh), inside, bev=0)
    shelf = hw_wood("window shelf", "#7A5A38", "#946E46")
    for z in (wz - 0.2, wz + 0.04):
        K.box("window shelf", (wx, WY + 0.16, z), (ww - 0.04, 0.16, 0.015), shelf, bev=0.002)
        for k in range(6):
            jar(f"window jar {z} {k}", (wx - 0.29 + k * 0.115, WY + 0.15, z + 0.008), r=0.036, h=0.1, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY", glow=0.4)
    for dx in (-ww / 6, ww / 6):
        K.box("window mullion", (wx + dx, WY - 0.03, wz), (0.022, 0.025, wh), frame_m, bev=0.002)
    K.box("window transom", (wx, WY - 0.03, wz + 0.08), (ww, 0.025, 0.022), frame_m, bev=0.002)
    K.box("flower box", (wx, WY - 0.2, wz - wh / 2 - 0.08), (ww, 0.1, 0.1), hw_wood("flower box", "#5E7A3A", "#6E8A44"), bev=0.004)
    for k in range(5):
        K.sph("box flower", (wx - 0.3 + 0.15 * k, WY - 0.2, wz - wh / 2 - 0.01), 0.04, K.mat(f"box flower {k}", ("#E0583A", "#F2D43A", "#C96BC0", "#F4F0E6", "#E0583A")[k], rough=0.6))
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


def s3_pole(name, base, col, word, side):
    """a flagpole with a pulley at its top, its halyard down to a cleat on the side he hauls from, and a cloth flag
    clipped to the pole that flies to `side`. The flag's TOP EDGE is its price. Returns (flag, rope-to-flag scaler)."""
    pole = K.mat("pole white", "#EDEAE2", rough=0.4)
    H = 1.36
    K.cyl(name + " pole", tuple(base + Vector((0, 0, H / 2))), 0.016, H, pole, v=16, bev=0.003)
    K.sph(name + " finial", tuple(base + Vector((0, 0, H + 0.02))), 0.026, K.mat("finial gold", "#D2A23A", rough=0.3, metal=0.8))
    K.cyl(name + " foot", tuple(base + Vector((0, 0, 0.03))), 0.07, 0.06, hw_noise("pole stone", "#9A958A", "#B5AFA2", scale=10), v=24, bev=0.006)
    steel = K.mat("pulley steel", "#7A8288", rough=0.3, metal=0.8)
    K.cyl(name + " pulley", tuple(base + Vector((0, -0.024, H - 0.04))), 0.022, 0.012, steel, rot=(math.pi / 2, 0, 0), v=20, bev=0.002)
    rope = K.mat("halyard", "#F2ECDA", rough=0.8)
    rx = base.x - side * 0.02                  # the hauling run, on the front of the pole away from the flag
    K.capsule(name + " halyard", Vector((rx, base.y - 0.05, 0.22)), Vector((rx, base.y - 0.024, H - 0.04)), 0.007, rope)
    K.box(name + " cleat", (rx, base.y - 0.03, 0.22), (0.016, 0.02, 0.07), steel, bev=0.003)
    # the flag-side run of the halyard, from the pulley down to the flag's top clip: scaled on z every frame
    run = K.empty(name + " flag run", tuple(base + Vector((side * 0.02, -0.03, H - 0.04))))
    K.cyl(name + " flag run rope", (0, 0, -0.5), 0.006, 1.0, rope, v=8, bev=0, parent=run)
    hw_local(run)
    flag = K.empty(name + " flag", (0, 0, 0))
    cloth = K.mat(f"flag {col}", col, rough=0.75)
    W_, H_ = 0.26, 0.22
    for k in range(6):                         # the cloth in six panels with a gentle ripple
        u = (k + 0.5) / 6
        o = K.box(name + " cloth", (side * (0.02 + W_ * u), 0.004 * math.sin(u * 5.0), -H_ / 2), (W_ / 6 + 0.002, 0.006, H_ - 0.01 * u), cloth, bev=0.002, parent=flag)
        o.rotation_euler = (0, 0, 0.12 * math.cos(u * 5.0) * side)
    for z in (-0.012, -H_ + 0.012):            # the two clips that hold it to the halyard at the pole
        K.box(name + " clip", (side * 0.02, -0.005, z), (0.02, 0.016, 0.014), steel, bev=0.002, parent=flag)
    K.box(name + " hoist edge", (side * 0.02, -0.005, -H_ / 2), (0.012, 0.012, H_), K.mat("hoist tape", "#3A3A3A", rough=0.7), bev=0.002, parent=flag)
    ink = hw_ink(f"flag ink {name}", "#2A1E12" if col != "#F2B02A" else "#3A1E04")
    K.text(name + " word", word, (side * (0.02 + W_ / 2), -0.016, -H_ / 2), 0.05 if len(word) < 7 else 0.036, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=flag)
    hw_local(flag)
    return flag, run


def shot2():
    """A QUARTER OF THE PRICE. Two flagpoles in front of a tall price board banded every 0.50 euro a kilo. The RICE
    SYRUP flag already flies at the first band, 0.50. Beside the HONEY pole he hauls its halyard hand over hand and the
    gold flag climbs band by band, 1.00, 1.50, 2.00, to 2.17: four bands to the syrup's one. He looks from one to the
    other and rubs his hands: every spoonful of syrup is profit."""
    W = hw_win
    T_IN = 0.75                                     # walks in to the honey pole, looking over at the syrup flag
    T_LOOK = 0.25
    T_H0, T_H1 = 0.95, 3.25                          # the honey flag up to 2.17, hand over hand
    T_BACK = 3.45                                   # steps back from the pole, looking up
    T_RUB = 3.85                                    # rubs his hands
    NH = 4
    light = place_honey_house()
    board = hw_noise("price board", "#F4EEDC", "#E8E0C8", scale=4, rough=0.7, bump=0.1)
    band = hw_noise("price band", "#DDBF7E", "#D2B270", scale=4, rough=0.7, bump=0.1)
    ink = hw_ink("board ink", "#2A1E12")
    bx0, bx1 = -0.31, 0.52; by = S3_POLES[0].y + 0.16; bxc = (bx0 + bx1) / 2
    K.box("price board back", (bxc, by + 0.02, S3_Z0 + 0.43), (bx1 - bx0 + 0.06, 0.03, 1.0), hw_wood("board frame", "#6E4A2A", "#8A5E36"), bev=0.008)
    for k in range(5):
        z0 = S3_Z0 + S3_PER * 0.5 * k
        K.box("price band", (bxc, by, z0 + S3_PER * 0.25), (bx1 - bx0, 0.01, S3_PER * 0.5 - 0.004), board if k % 2 else band, bev=0.002)
    for k in range(0, 5):
        v = 0.5 * k; z = S3_Z0 + S3_PER * v
        K.box("board line", (bxc, by - 0.008, z), (bx1 - bx0, 0.004, 0.008 if k else 0.012), ink, bev=0)
        if k: K.text("board euro", f"{v:.2f}", ((S3_POLES[0].x + 0.04 + S3_POLES[1].x - 0.26) / 2, by - 0.01, z + 0.026), 0.05, (math.pi / 2, 0, 0), ink, extrude=0.0008)   # between the poles, clear of both flags
    K.text("price board head", "EUROS A KILO", (bxc, by - 0.01, S3_Z0 + S3_PER * 2.25 + 0.03), 0.05, (math.pi / 2, 0, 0), ink, extrude=0.0008)
    sf, srun = s3_pole("syrup", S3_POLES[0], "#FAFAF4", "RICE SYRUP", 1)
    hf, hrun = s3_pole("honey", S3_POLES[1], "#F2B02A", "HONEY", -1)
    tops = (S3_Z0 + S3_PER * 0.5, S3_Z0 + S3_PER * 2.17)
    def honey_z(t):
        return S3_Z0 + (tops[1] - S3_Z0) * ease(max(0.0, min(1.0, (t - T_H0) / (T_H1 - T_H0))))   # wound up with the crank
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for i, (fl, run, z) in enumerate(((sf, srun, tops[0]), (hf, hrun, honey_z(t)))):
            side = (1, -1)[i]
            fl.location = (S3_POLES[i].x, S3_POLES[i].y, z); fl.keyframe_insert("location", frame=f)
            run.scale = (1, 1, max(0.01, run.location.z - z)); run.keyframe_insert("scale", frame=f)
    # ---- the winch at the honey pole's foot: he cranks it and the halyard winds the flag up
    steel = K.mat("winch steel", "#5E666C", rough=0.35, metal=0.7)
    red = K.mat("winch red", "#B8261E", rough=0.45)
    HUB = Vector((S3_POLES[1].x + 0.14, S3_POLES[1].y - 0.16, 0.38))      # the crank's axis points at him
    K.box("winch post", (HUB.x - 0.07, HUB.y, 0.16), (0.07, 0.07, 0.32), hw_wood("winch post", "#6E4A2A", "#8A5E36"), bev=0.006)
    K.box("winch box", (HUB.x - 0.07, HUB.y, 0.38), (0.1, 0.12, 0.12), red, bev=0.01)
    K.cyl("winch drum", (HUB.x - 0.07, HUB.y, 0.465), 0.035, 0.1, steel, rot=(math.pi / 2, 0, 0), v=24, bev=0.003)
    K.capsule("winch rope", Vector((HUB.x - 0.07, HUB.y + 0.02, 0.5)), Vector((S3_POLES[1].x + 0.02, S3_POLES[1].y - 0.024, 1.32)), 0.006, K.mat("halyard", "#F2ECDA", rough=0.8))
    crank = K.empty("winch crank", tuple(HUB))
    K.cyl("crank hub", (-0.005, 0, 0), 0.022, 0.04, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.003, parent=crank)
    K.box("crank arm", (0.02, 0.025, 0), (0.012, 0.07, 0.02), steel, bev=0.003, parent=crank)
    K.cyl("crank handle", (0.045, 0.055, 0), 0.014, 0.05, red, rot=(0, math.pi / 2, 0), v=16, bev=0.003, parent=crank)
    hw_local(crank)
    TURNS = 4
    ang = lambda t: 2 * math.pi * TURNS * ease(max(0.0, min(1.0, (t - T_H0) / (T_H1 - T_H0))))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        crank.rotation_euler = (ang(t), 0, 0); crank.keyframe_insert("rotation_euler", frame=f)
    handle = lambda t: HUB + Vector((0.065, 0.055 * math.cos(ang(t)), 0.055 * math.sin(ang(t))))
    # ---- him: walks in to the winch, cranks, looks up at the flag, turns to us and rubs his hands
    data = load_data()
    YW = -82.0
    P0 = S3_DATA + Vector((0.22, 0.0, 0))
    data.place(P0.x, P0.y, -90)
    hat = bee_hat(data)
    data.walk_to(S3_DATA, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw0 = math.degrees(data.arm.rotation_euler.z)
    crankb = lambda t: math.sin(ang(t)) * W(t, T_H0, 0.2) * (1 - W(t, T_H1 - 0.1, 0.2))
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        yaw = yw0 + (YW - yw0) * W(t, T_IN - 0.05, 0.3) + 55 * W(t, T_BACK, 0.4) + 7 * crankb(t)
        p = S3_DATA + Vector((0.04, 0, 0)) * crankb(t) + Vector((0.04, -0.12, 0)) * W(t, T_BACK, 0.45)
        z = 0.035 * abs(crankb(t)) + 0.05 * hw_kick(t - T_BACK - 0.35, 0.14) + 0.04 * hw_kick(t - T_RUB - 0.6, 0.13)
        data._kobj(t, loc=(p.x, p.y, z), rot=math.radians(yaw))
    hw_layer(data, "spine", lambda t: (18 * crankb(t) + 8 * W(t, T_H0, 0.3) * (1 - W(t, T_H1, 0.3)) + 10 * W(t, T_RUB, 0.3), 0,
                                      10 * math.sin(2 * math.pi * (t - T_RUB) / 0.9) * W(t, T_RUB, 0.3)), 0, DUR + 0.4)
    sc.frame_set(F(T_H0)); bpy.context.view_layer.update()
    near, far = sorted("LR", key=lambda s: (acts._shoulder(data, s) - HUB).length)
    rub = [(T_BACK + 0.2, (0.12, 0.09, -0.05)), (T_RUB, (0.13, 0.0, -0.08))]
    for k in range(3):
        rub.append((T_RUB + 0.3 + 0.3 * k, (0.13 + (0.02 if k % 2 else -0.01), 0.0, -0.08 + (0.015 if k % 2 else 0))))
    rub.append((DUR + 0.3, (0.12, 0.01, -0.07)))
    rest_n = hw_hand(data, near, [(0.0, (0.06, 0.08, -0.12)), (T_IN, (0.08, 0.08, -0.1)), (T_H1, (0.08, 0.08, -0.1))] + rub)
    def near_fn(t):
        g = W(t, T_H0 - 0.35, 0.3) * (1 - W(t, T_H1 + 0.05, 0.3))
        return rest_n(t).lerp(handle(t), g)
    lid = HUB + Vector((0.03, 0.03, 0.4 - HUB.z + 0.005))
    rest_f = hw_hand(data, far, [(0.0, (0.06, 0.08, -0.12)), (T_IN + 0.2, (0.07, 0.08, -0.1)), (T_H0 + 0.3, (0.05, 0.08, -0.11)), (T_H1, (0.05, 0.08, -0.11))] + rub)   # pumping with the crank
    def far_fn(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, far)
        return rest_f(t) + (fw * 0.025 + Vector((0, 0, 0.025))) * crankb(t)      # his free fist pumps with every turn
    data.reach(near, near_fn, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(far, far_fn, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    LENS = Vector((0.3, -1.6, 0.68))
    data.look_at(Vector((S3_POLES[0].x, S3_POLES[0].y, tops[0])), 0.0, max_yaw=50, max_pitch=30, blend=0.15)
    data.look_at(Vector((S3_POLES[1].x, S3_POLES[1].y, 0.8)), T_H0 + 0.3, max_yaw=28, max_pitch=40, blend=0.2)
    data.look_at(Vector((S3_POLES[1].x, S3_POLES[1].y, tops[1])), T_H1 - 0.3, max_yaw=28, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_RUB - 0.1, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_H0)
    data.expression("determined", T_H0 + 0.05, T_H1 - 0.1, blend=0.15)
    data.expression("surprised", T_H1, T_RUB - 0.1, blend=0.1)
    data.expression("pleased", T_RUB, DUR + 1.0, blend=0.18)
    data.finish()
    LOOK = Vector((0.3, 0.3, 0.7))
    LENS, LOOK = compose.frame_data(data, LENS, LOOK, 30, face_at=(0.76, 0.47), height=0.346, t=0.5 * DUR)   # framed first: at the winch, board clear
    cam = K.camera(tuple(LENS), tuple(LOOK), lens=30, fstop=8.0)
    compose.drop_cut(hw_named("window jar", "inside jar"), cam, NF, label="the honey house's jars")
    camera_path(cam, lambda t: (LENS + Vector((0.02, 0.08, 0.0)) * ease(t / DUR), LOOK + Vector((0.0, 0.0, 0.05 * ease(t / DUR))), LOOK))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("crank handle", "winch box"),
                boxes=[("the price board and both flags", lambda: hw_drawn("price band", "board line", "board euro", "syrup flag", "honey flag", "syrup cloth", "honey cloth"), (0.0, 0.2, 1.0, 1.0)),
                       ("the board's words", lambda: hw_drawn("board euro", "price board head", "syrup word", "honey word"), (0.0, 0.2, 1.0, 1.0))],
                conseq=[("he hauls the HONEY flag up the board to 2.17, four bands to the RICE SYRUP flag's one at 0.50", lambda: meshes([sf, hf, srun, hrun]) + meshes_of("price band", "board line", "syrup pole", "honey pole"), T_H0, DUR, {"hero": True, "moves": lambda: meshes([hf])}),
                        ("he cranks the winch and the honey flag climbs", lambda: meshes([hf, crank]), T_H0, T_H1, {"moves": True})])


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
        K.box(f"syrup sack {k}", (x, 0.58, 0.14), (0.21, 0.15, 0.28), sack, bev=0.05); K.box(f"sack neck {k}", (x, 0.58, 0.3), (0.07, 0.05, 0.06), sack, bev=0.02); K.cyl(f"sack tie {k}", (x, 0.58, 0.285), 0.038, 0.012, K.mat("sack tie", "#5A4028", rough=0.9), v=16, bev=0)
        K.text("sack word", "SYRUP", (x, 0.5, 0.15), 0.035, (math.pi / 2, 0, 0), ink, extrude=0.0004)
    for k in range(3):
        x = -0.85 + k * 0.26
        o = K.box(f"syrup sack top {k}", (x + 0.12, 0.6, 0.37), (0.24, 0.15, 0.17), sack, bev=0.05); o.rotation_euler = (0, 0.06 * (k - 1), 0)
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
    K.box("gauge back", (S3_VAT.x, S3_VAT.y - S3_VR - 0.006, 0.26), (0.11, 0.006, 0.27), K.mat("gauge plate", "#F2EEE4", rough=0.5), bev=0.002)
    gi = hw_ink("gauge ink", "#2A1E12")
    K.text("gauge word", "SYRUP", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.372), 0.024, (math.pi / 2, 0, 0), gi, extrude=0.0003)
    K.text("gauge word", "HONEY", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.146), 0.024, (math.pi / 2, 0, 0), gi, extrude=0.0003)
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
    T_T = [0.17 * DUR, 0.42 * DUR, 0.895 * DUR]           # the key stills: dipping / RED (test 2) / cranking, still red / GREEN
    T_D = [t - 0.55 for t in T_T]
    T_C = [0.207 * DUR, 0.575 * DUR]                     # cranks of the SYRUP wheel
    CR = 0.6                                            # a crank's length
    T_GAPE = 0.95 * DUR
    light = place_back_room()
    wheel, wspin = s3_wheel("syrup wheel", S3_WHEEL)
    # the gauge: a glass tube, the honey part at the bottom and the syrup above it, the line between them dropping
    tube_m = hw_glass("gauge glass")
    K.cyl("gauge tube", (S3_VAT.x, S3_VAT.y - S3_VR - 0.02, 0.26), 0.019, 0.19, tube_m, v=16, bev=0.002)
    hon = K.cyl("gauge honey", (0, 0, 0), 0.016, 1.0, hw_honey("gauge honey", "#C87810", glow=0.4), v=16, bev=0)
    syr = K.cyl("gauge syrup", (0, 0, 0), 0.016, 1.0, K.mat("gauge syrup", "#F6F0DA", rough=0.3, emit=0.3), v=16, bev=0)
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
    fail = K.text("screen fail", "FAIL", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.047), 0.04, (math.pi / 2, 0, 0), hw_ink("fail ink", "#FF3A2A", emit=4.0), extrude=0.0004)
    ok = K.text("screen pass", "PASS", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.047), 0.04, (math.pi / 2, 0, 0), hw_ink("pass ink", "#3AFF6A", emit=4.0), extrude=0.0004)
    # a beacon on a post at the box's back corner: the whole room sees FAIL or PASS
    BEA = Vector((S3_BOX.x + 0.075, S3_BOX.y + 0.03, S3_BOX.z + 0.25))
    K.cyl("lamp post", (BEA.x, BEA.y, (S3_BOX.z + 0.14 + BEA.z) / 2), 0.008, BEA.z - S3_BOX.z - 0.14, K.mat("vat steel"), v=12, bev=0)
    K.cyl("lamp base", (BEA.x, BEA.y, BEA.z - 0.012), 0.032, 0.02, K.mat("lamp base", "#2A2E32", rough=0.4), v=24, bev=0.003)
    K.sph("lamp dome off", (BEA.x, BEA.y, BEA.z), 0.038, K.mat("lamp dome off", "#5A5048", rough=0.25))
    beacon_red = K.sph("lamp red beacon", (BEA.x, BEA.y, BEA.z), 0.04, K.mat("lamp red glow", "#FF2A1E", emit=8.0))
    beacon_grn = K.sph("lamp green beacon", (BEA.x, BEA.y, BEA.z), 0.04, K.mat("lamp green glow", "#2AFF5A", emit=8.0))
    def lit(o, spans):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = any(a <= t < b for a, b in spans)
            s = 1.0 if on else 1e-3
            o.scale = (s, s, s); o.keyframe_insert("scale", frame=f)
    red_spans = [(T_T[0], T_T[1] - 0.12), (T_T[1], T_T[2])]                 # FAIL stays up until the next test; it blinks off as he tests again
    for o in (red_on, fail, beacon_red): lit(o, red_spans)
    for o in (grn_on, ok, beacon_grn): lit(o, [(T_T[2], DUR + 1)])
    # ---- him: square to the lens between the vat and the wheel, turning to each job
    data = load_data()
    data.place(S3_P0.x, S3_P0.y, 0.0)
    hat = bee_hat(data)
    def yaw(t):
        y = 0.0
        for td, tt in zip(T_D, T_T):
            y += -38 * (W(t, td - (0.36 if td > 3 else 0.62), (0.3 if td > 3 else 0.35)) if td > 0.5 else 1.0) * (1 - (W(t, td + 0.2, 0.35) if td > 0.5 else W(t, td + 0.75, 0.45)))   # the first test: turned to the box till the touch lands            # to the vat and the box
        for tc in T_C:
            y += 12 * W(t, tc - 0.25, 0.25) * (1 - W(t, tc + CR, 0.25))            # to the wheel
        y += 0.0
        return math.radians(y)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        z = sum(k * hw_kick(t - tt - 0.1, 0.2) for k, tt in zip((0.025, 0.04), T_T[:2])) - sum(0.035 * math.sin(math.pi * max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C) + 0.06 * hw_kick(t - T_T[2] - 0.05, 0.15) + 0.04 * hw_kick(t - T_GAPE, 0.14)
        lean = sum((0.045, 0.08)[k] * W(t, tc - 0.3, 0.25) * (1 - W(t, tc + CR + 0.2, 0.3)) for k, tc in enumerate(T_C))   # steps in to the wheel and stays till he lets go
        data._kobj(t, loc=(S3_P0.x + lean, S3_P0.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (sum(6 * W(t, td - 0.1, 0.25) * (1 - W(t, td + 0.3, 0.25)) for td in T_D)
                                      + sum(8 * W(t, tc - 0.15, 0.2) * (1 - W(t, tc + CR, 0.2)) for tc in T_C)
                                      - 8 * W(t, T_T[2] + 0.05, 0.2) * (1 - W(t, T_GAPE - 0.1, 0.3)), 0,
                                      sum(12 * math.sin(2 * math.pi * (t - tt - 0.15) / 0.45) * W(t, tt + 0.1, 0.12) * (1 - W(t, tt + 0.7, 0.2)) for tt in T_T[:2])), 0, DUR + 0.4)   # red: he shakes his head, both times
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):           # his fist where the dipper's head reaches `world`
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    MOUTH = Vector((S3_VAT.x + 0.02, S3_VAT.y + 0.01, S3_VZ1 - 0.02))
    PLATE = Vector((S3_BOX.x - 0.05, S3_BOX.y + 0.035, S3_BOX.z + 0.15))
    # the dipper hand (his left): dip, lift, over to the box's plate, back up
    dk = [(0.0, short(lf, 0.0, MOUTH + Vector((0, 0, 0.09)), by=0.15))]
    for td, tt in zip(T_D, T_T):
        dk += [(td - 0.2, short(lf, td - 0.2, MOUTH + Vector((0, 0, 0.07)), by=0.15)), (td, short(lf, td, MOUTH + Vector((0, 0, 0.02)), by=0.15)), (td + 0.22, short(lf, td + 0.22, (MOUTH + PLATE) / 2 + Vector((-0.02, 0.02, 0.04)), by=0.15)),
               (tt - 0.05, short(lf, tt - 0.05, PLATE + Vector((0, 0, 0.05)), by=0.1)), (tt + 0.1, short(lf, tt + 0.1, PLATE + Vector((0, 0, 0.02)), by=0.1)), (tt + 0.35, (0.14, 0.1, -0.06))]
    dk += [(DUR + 0.3, (0.1, 0.13, -0.025))]
    # the wheel hand (his right): on the knob through each crank, the knob going round with the wheel
    def knob(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return wspin.matrix_world @ Vector((0.07, 0, 0.075))
    def wheel_turn(t):
        return math.radians(-150) + sum(math.radians(48) * ease(max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        wspin.rotation_euler = (0, 0, wheel_turn(t)); wspin.keyframe_insert("rotation_euler", frame=f)
    wk = [(0.0, (0.03, 0.08, -0.12)), (T_C[0] - 0.7, (0.03, 0.09, -0.11))]
    for tc in T_C:
        wk += [(tc - 0.12, hw_rel(data, rt, tc - 0.12, knob(tc - 0.12)))]
        wk += [(tc + CR * u, hw_rel(data, rt, tc + CR * u, knob(tc + CR * u))) for u in (0.35, 0.7, 1.0)]
        wk += [(tc + CR + 0.15, hw_rel(data, rt, tc + CR + 0.15, knob(tc + CR))), (tc + CR + 0.6, (0.05, 0.1, -0.08))]   # rests on the knob, then lets go slowly
    wk += [(T_GAPE, (0.07, 0.13, -0.03)), (DUR + 0.3, (0.07, 0.13, -0.025))]
    for ks in (dk, wk):
        ks.sort(key=lambda k: k[0])
        i = 1
        while i < len(ks):
            if ks[i][0] <= ks[i - 1][0] + 0.04: ks.pop(i)
            else: i += 1
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.15, back=None, elbow_out=0.5)
    data.reach(rt, hw_hand(data, rt, wk), 0.0, DUR + 0.3, lead=0.08, back=None, elbow_out=0.3)
    CAM = Vector((-0.3, -1.45, 0.72)); LOOK = Vector((0.0, -0.1, 0.45))
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
        gy = S3_VAT.y - S3_VR - 0.02
        hon.location = (S3_VAT.x, gy, (G0 + zl) / 2); hon.scale = (1, 1, max(1e-3, zl - G0))
        syr.location = (S3_VAT.x, gy, (zl + G1) / 2); syr.scale = (1, 1, max(1e-3, G1 - zl))
        for o in (hon, syr):
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f)
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 30, face_at=(0.45, 0.62), height=0.38, t=0.5 * DUR)   # framed first: behind his bench, face clear of the brim
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((0.02, 0.05, -0.03)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.0)) * ease(t / DUR), Vector((S3_BOX.x, S3_BOX.y, S3_BOX.z + 0.08))))
    compose.drop_cut(hw_named("sack word"), cam, NF, label="the sacks' stencils")
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="back_room", light=light, data=data, rest=1, grips=("honey dipper", "syrup wheel", "test probe plate", "vat blend"),
                boxes=[("the TEST box and its beacon", lambda: hw_drawn("test box", "test crate", "lamp", "screen"), (0.0, 0.0, 1.0, 0.75)),
                       ("the vat's gauge", lambda: hw_drawn("gauge"), (0.0, 0.0, 1.0, 0.75)),
                       ("the RICE SYRUP drum and its words", lambda: hw_drawn("syrup drum", "drum word", "drum hoop"), (0.0, 0.0, 1.0, 1.0))],
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
S4_P = Vector((0.45, 0.0, 0.0))                  # where he stands
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
    # the honey show's long table on the stage (board 2026-11-23: "no stage, no tables ... sign clutter"): a checked
    # cloth, entries in jars with rosettes, a cake stand; pendant lamps over the hall, a noticeboard and a radiator
    cloth = hw_noise("show cloth", "#F4F1EA", "#E2DCCF", scale=30, rough=0.85)
    K.box("show table", (0.1, 1.12, 0.24 + 0.29), (1.9, 0.26, 0.02), cloth, bev=0.004)
    K.box("show table drape", (0.1, 0.99, 0.24 + 0.2), (1.9, 0.006, 0.2), cloth, bev=0)
    for k in range(12):
        K.box("cloth check", (-0.82 + k * 0.17, 0.985, 0.24 + 0.2), (0.07, 0.004, 0.2), K.mat("check blue", "#7FA7D6", rough=0.85), bev=0)
    for k in range(9):
        x = -0.7 + k * 0.2
        jar(f"show jar {k}", (x, 1.12, 0.55), r=0.035, h=0.09, fill=0.9, honey_col=("#E8A82A", "#C97A12", "#F2C35A")[k % 3])
        if k % 3 == 1:
            K.cyl("rosette", (x + 0.05, 1.0, 0.5), 0.03, 0.006, K.mat("rosette red", "#C8261E", rough=0.5), rot=(math.pi / 2, 0, 0), v=20, bev=0.002)
    K.cyl("cake stand", (0.95, 1.12, 0.58), 0.08, 0.012, K.mat("stand white", "#FFFFFF", rough=0.3), v=32, bev=0.003)
    K.cyl("cake", (0.95, 1.12, 0.62), 0.065, 0.07, hw_noise("cake", "#D9A35A", "#E9BE7A", scale=20), v=32, bev=0.01)
    lampm = K.mat("pendant shade", "#2E4A3E", rough=0.4, metal=0.3)
    for x in (-0.5, 0.55):
        K.cyl("pendant cord", (x, 0.75, 2.0), 0.003, 0.6, K.mat("cord", "#222222"), v=6, bev=0)
        K.cyl("pendant shade", (x, 0.75, 1.68), 0.09, 0.06, lampm, v=32, bev=0.01)
        K.sph("pendant bulb", (x, 0.75, 1.64), 0.03, K.mat("bulb glow", "#FFE6B0", emit=8.0))
    K.box("noticeboard", (-1.46, 0.2, 1.05), (0.02, 0.5, 0.36), hw_noise("cork", "#B88A5A", "#CFA272", scale=40), bev=0.006)
    for k, (dy, dz, c) in enumerate(((-0.12, 0.06, "#FFFFFF"), (0.08, 0.08, "#FFF3A6"), (-0.05, -0.08, "#BFE3FF"), (0.13, -0.06, "#FFFFFF"))):
        K.box("notice", (-1.448, 0.2 + dy, 1.05 + dz), (0.004, 0.11, 0.13), K.mat(f"notice {c}", c, rough=0.8), bev=0)
    rad = K.mat("radiator", "#E8E4DA", rough=0.4, metal=0.2)
    for x in (-0.9, 0.9):
        for k in range(10):
            K.box("radiator fin", (x - 0.2 + k * 0.045, 1.33, 0.36), (0.02, 0.05, 0.3), rad, bev=0.004)
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
    K.sph("beacon dome", (S4_M.x, S4_M.y, S4_MH + 0.06), 0.048, K.mat("beacon glass", "#C8281C", rough=0.15, emit=0.6), scale=(1, 1, 1.15))
    spin = K.empty("beacon spin", (S4_M.x, S4_M.y, S4_MH + 0.06))
    K.box("beacon mirror", (0, 0, 0), (0.07, 0.012, 0.05), K.mat("beacon lamp", "#FF5A3A", emit=12.0), bev=0.002, parent=spin)
    hw_local(spin)
    # the screen under the dial: dark, then RICE SYRUP FOUND in red
    K.box("test machine screen", (S4_M.x, S4_M.y - 0.142, 0.3), (0.3, 0.004, 0.09), K.mat("machine screen", "#14181C", rough=0.3), bev=0.003)
    found = K.text("screen found", "RICE SYRUP\nFOUND", (S4_M.x, S4_M.y - 0.146, 0.3), 0.032, (math.pi / 2, 0, 0), hw_ink("found red", "#FF3A2A", emit=5.0), extrude=0.0004)
    return needle, spin, found


def s4_funnel(at):
    """THE SAMPLE FUNNEL: a big steel funnel on its own bracket off the machine's side, its mouth at `at`, and a clear
    glass pipe from its spout into the machine, so the drop's way in is SEEN (board: "the machine fires with no
    visible cause"). Returns the pipe's path [spout, elbow, machine]."""
    steel = K.mat("machine steel", "#B8BCC0", rough=0.25, metal=0.9)
    for k in range(7):
        r = 0.014 + k * 0.011
        K.cyl("funnel ring", (at.x, at.y, at.z - 0.06 + k * 0.01), r, 0.011, steel, v=40, bev=0.001)
    K.cyl("funnel rim", (at.x, at.y, at.z + 0.006), 0.083, 0.008, K.mat("funnel rim", "#1E4A7A", rough=0.4), v=40, bev=0.002)
    K.cyl("funnel spout", (at.x, at.y, at.z - 0.09), 0.012, 0.05, steel, v=16, bev=0)
    glass = hw_glass("pipe glass")
    p0 = Vector((at.x, at.y, at.z - 0.115)); p1 = Vector((at.x, at.y, at.z - 0.17)); p2 = Vector((S4_M.x + 0.21, at.y, at.z - 0.17))
    K.capsule("funnel pipe", p0, p1, 0.016, glass); K.capsule("funnel pipe", p1, p2, 0.016, glass)
    K.box("funnel bracket", (at.x / 2 + (S4_M.x + 0.21) / 2, at.y, at.z - 0.2), (abs(at.x - S4_M.x - 0.21) + 0.02, 0.03, 0.012), steel, bev=0.002)
    return [p0, p1, p2]


def shot4():
    """THE SHARPER TEST. The lens low and wide in the hall: he walks up to the new machine with his dipper, dips it in
    the jar of the blend that passed, holds it over the funnel and lets one drop fall; the dial swings hard from PASS
    into FAKE, the beacon spins red; he jumps back and points at it, then at us."""
    W = hw_win
    T_IN = 0.2 * DUR                          # the walk up ends
    T_DIP = T_IN + 0.2                         # he lifts the dipper high: the blend from the back room still on it
    T_DROP = 0.35 * DUR                        # the drop falls (mid-fall on the board's second still)
    T_SWING = T_DROP + 0.6                     # ... runs down the glass pipe into the machine, and the dial swings
    T_JUMP = T_SWING + 0.3
    T_POINT = 0.65 * DUR
    T_END = 0.88 * DUR                         # a last hop at us
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
        back = 0.04 * W(t, T_JUMP, 0.22) - 0.07 * W(t, T_POINT - 0.1, 0.3) + 0.02 * W(t, T_END - 0.1, 0.25)
        p = S4_P + Vector((back, -0.08 * W(t, T_JUMP, 0.22) + 0.03 * W(t, T_END - 0.1, 0.25), 0.0))     # jumps back toward us, not out of frame
        z = 0.07 * hw_kick(t - T_JUMP - 0.04, 0.15) + 0.06 * hw_kick(t - T_POINT, 0.14) + 0.07 * hw_kick(t - T_END, 0.14) + 0.06 * hw_kick(t - T_DIP - 0.4, 0.14) + 0.035 * hw_kick(t - T_DROP - 0.05, 0.12) + 0.05 * hw_kick(t - T_IN - 0.08, 0.13)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (-8 * W(t, T_DIP - 0.25, 0.25) * (1 - W(t, T_DIP + 0.3, 0.25)) + 10 * W(t, T_DROP - 0.4, 0.3) * (1 - W(t, T_SWING, 0.2))
                                      - 12 * W(t, T_JUMP, 0.15) * (1 - W(t, T_POINT - 0.1, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    POINT_AT = S4_DIAL + Vector((0.05, 0, 0.02))
    OVER = S4_FUN + Vector((0, 0, 0.05))
    dk = [(0.0, (0.08, 0.1, -0.06)), (T_IN - 0.3, (0.08, 0.11, -0.02)),
          (T_DIP, (0.05, 0.13, 0.07)),                                            # up high: look, the blend that passed
          (T_DROP - 0.2, (0.09, 0.12, -0.02)), (T_DROP + 0.25, (0.09, 0.12, -0.01)),
          (T_JUMP, (0.1, 0.16, -0.03)), (T_JUMP + 0.3, (0.09, 0.17, 0.0)),
          (T_POINT, tuple(Vector(hw_rel(data, lf, T_POINT, POINT_AT)).normalized() * 0.15)), (T_POINT + 0.35, tuple(Vector(hw_rel(data, lf, T_POINT + 0.35, POINT_AT)).normalized() * 0.155)), (T_END, (0.1, 0.13, 0.03)), (DUR + 0.3, (0.1, 0.13, 0.04))]
    pk = [(0.0, (0.07, 0.1, -0.11)), (T_IN, (0.08, 0.1, -0.1)), (T_DIP + 0.05, (0.09, 0.11, -0.08)),
          (T_DIP + 0.35, (0.06, 0.17, 0.06)), (T_DROP + 0.05, (0.09, 0.12, -0.07)), (T_SWING, (0.1, 0.1, -0.08)),      # the free hand up: watch this
          (T_JUMP, (0.08, 0.16, 0.03)), (T_JUMP + 0.3, (0.08, 0.16, 0.05)),
          (T_POINT, (0.06, 0.16, 0.0)), (T_POINT + 0.35, (0.09, 0.1, -0.09)), (T_END, (0.1, 0.14, 0.08)), (DUR + 0.3, (0.1, 0.14, 0.085))]
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.6)
    data.reach(rt, hw_hand(data, rt, pk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    CAM = Vector((0.32, -1.42, 0.55)); LOOK = Vector((0.28, 0.0, 0.47))
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
    # the funnel where his dipper drips (built to his reach)
    sc.frame_set(F(T_DROP)); bpy.context.view_layer.update()
    FUN = dr.matrix_world @ Vector((0, 0, dip["head_z"])) + Vector((0, 0, -0.06))
    PIPE = s4_funnel(FUN)
    # ---- the drop: from the dipper's head into the funnel
    drop = K.sph("honey drop", (0, 0, 0), 0.02, hw_honey("drop honey", "#F0A020", glow=3.0, clear=0.2), scale=(1, 1, 1.3))
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
    # ---- the drop runs down the glass pipe into the machine (glowing), then the dial swings
    slug = K.sph("pipe honey", (0, 0, 0), 0.013, hw_honey("pipe honey", "#F0A020", glow=3.0, clear=0.2), scale=(1, 1, 1))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = (t - T_DROP - 0.3) / (T_SWING - T_DROP - 0.3)
        if 0 <= u <= 1:
            v = u * 2.0; p = PIPE[0].lerp(PIPE[1], v) if v < 1 else PIPE[1].lerp(PIPE[2], v - 1); s_ = 1.0
        else:
            p = PIPE[0]; s_ = 1e-3
        slug.location = p; slug.scale = (s_ * (1.6 if 0.5 < u <= 1 else 1.0), s_, s_)
        slug.keyframe_insert("location", frame=f); slug.keyframe_insert("scale", frame=f)
    bm = bpy.data.materials["beacon glass"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for t, v in ((0.0, 0.0), (T_SWING, 0.0), (T_SWING + 0.1, 4.0)):
        bm.default_value = v; bm.keyframe_insert("default_value", frame=F(t))
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
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 24, face_at=(0.64, 0.59), height=0.36, t=0.5 * DUR)   # framed first: beside the machine
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.02, 0.08, 0.0)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.01)) * ease(t / DUR), S4_DIAL))
    compose.drop_cut(hw_named("show jar"), cam, NF, label="the honey show's jars")
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="village_hall", light=light, data=data, rest=1, grips=("honey dipper", "funnel"),
                boxes=[("the new test machine, its funnel and beacon", lambda: hw_drawn("test machine", "dial", "beacon", "funnel"), (0.0, 0.0, 1.0, 1.0)),
                       ("the machine's screen words", lambda: hw_drawn("screen found"), (0.02, 0.0, 0.98, 1.0))],
                conseq=[("the new machine catches the rice syrup: its dial swings from PASS into FAKE, RICE SYRUP FOUND lights up and the beacon spins", lambda: meshes_of("test machine", "dial", "beacon", "screen found", "funnel", "pipe honey"), T_SWING, DUR, {"hero": True}),
                        ("the needle swings from PASS to FAKE", lambda: meshes([needle]) + meshes_of("test machine dial"), T_SWING, T_SWING + 0.6, {"moves": True})])


# ====================================================================================================
# shot5.py
# ====================================================================================================
# ---------------------------------------------------------------- shot 5: the fakes keep coming (the alley)
"""5 ALMOST HALF. The alley behind the stall, where the imports come in: cobbles, brick walls, a back door, bins,
crates, and a stepped stand of import jars, three tiers of seven. One jar in each tier already wears a red SUSPECT
label (the old test's one in seven). He hauls down the big lever of the EU's new scanner; its red bar sweeps along the
tiers and two more in every tier spin round to red: three in seven, almost half, three times the old count. He picks
up a red one and holds it out to us: what's in your jar?"""

S5_N, S5_TIERS = 7, 3
S5_OLD = 2                                       # the one in seven the old test caught, in every tier
S5_NEW = (4, 6)                                  # the two more the new test catches: three in seven
S5_JR, S5_JH, S5_DX = 0.036, 0.12, 0.085
S5_TX0 = -0.15                                   # the first column's x
S5_TIER = [(0.42, 0.82 + 0.2 * k) for k in range(S5_TIERS)]    # (y, top z) of each shelf: high on a rack against the alley wall, over his head
S5_LEV = Vector((0.28, 0.14, 0.0))               # the lever's foot, at the stand's right end
S5_PIV = 0.16; S5_LL = 0.27                      # its pivot height, its arm's length
S5_P = Vector((0.48, 0.13, 0.0))                 # where he stands to haul it


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
    K.box("alley bed", (0, 0.5, -0.008), (8, 8, 0.012), hw_cobbles("alley cobbles", "#7E776C", "#A09682", "#3E3832", scale=7), bev=0)   # board: spheres "read as polka dots"
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
    for k in range(3):
        s5_crate(f"empty crate {k}", (-0.2 + 0.02 * k, 0.42, 0.22 * k), (0.28, 0.2, 0.22), rnd)
    K.cyl("broom handle", (-0.82, 0.5, 0.6), 0.012, 1.2, hw_wood("broom", "#A07A50", "#B89068"), rot=(0.12, 0, 0), v=12)
    return lambda: village_light(sun_elev=50, sun_az=-25, sun=3.2, sky=0.3)


def s5_stand(rnd):
    """the import rack: a tall steel-and-plank shelving rack against the alley wall, three shelves of seven jars
    over his head (board: the stand was too small to read a share from; on a tall rack the tiers fill the frame)"""
    wood = hw_wood("stand wood", "#8A6A44", "#A8865A", scale=5)
    steel = K.mat("rack steel", "#3E5A7A", rough=0.4, metal=0.5)
    xa, xb = S5_TX0 - 0.07, S5_TX0 + 6 * S5_DX + 0.07
    for x in (xa, xb):
        for y in (S5_TIER[0][0] - 0.08, S5_TIER[0][0] + 0.08):
            K.box("rack upright", (x, y, 0.77), (0.03, 0.03, 1.54), steel, bev=0.003)
    for k, (y, z) in enumerate(S5_TIER):
        K.box("rack shelf", ((xa + xb) / 2, y, z - 0.012), (xb - xa + 0.04, 0.18, 0.024), wood, bev=0.004)
        K.box("rack lip", ((xa + xb) / 2, y - 0.09, z - 0.03), (xb - xa + 0.04, 0.01, 0.04), steel, bev=0.002)
    for z in (0.25, 0.55):
        K.box("rack shelf", ((xa + xb) / 2, S5_TIER[0][0], z), (xb - xa + 0.04, 0.18, 0.024), wood, bev=0.004)
    K.text("stand stencil", "IMPORTS", ((xa + xb) / 2, S5_TIER[0][0] - 0.097, S5_TIER[0][1] - 0.03), 0.028, (math.pi / 2, 0, 0), hw_ink("rack word", "#FFFFFF"), extrude=0.0004)
    for k in range(3):                                   # the empty crates the jars came in, on the bottom shelf and the floor
        s5_crate(f"import crate {k}", (xa + 0.16 + 0.24 * (k % 2), S5_TIER[0][0], (0.27, 0.57, 0.0)[k]), (0.2, 0.15, 0.13), rnd)
    jars = []
    for k, (y, z) in enumerate(S5_TIER):
        row = []
        for i in range(S5_N):
            red = i == S5_OLD or i in S5_NEW
            j = jar(f"import jar {k} {i}", (S5_TX0 + i * S5_DX, y, z), r=S5_JR, h=S5_JH, fill=0.9, honey_col="#E8A82A", glow=0.35,
                    label="PURE HONEY", back="SUSPECT" if red else None, yaw=math.radians(rnd.uniform(-6, 6)))
            if i == S5_OLD:
                j["spin"].rotation_euler = (0, 0, math.pi)          # the old test already caught this one
            row.append(j)
        jars.append(row)
    return jars


def s5_scanner():
    """THE EU SCANNER: a blue rail along the rack's top, a carriage on it with a red light bar hanging down in front of
    the three shelves, just off the jars' faces; and its big lever on the rack's right upright. Returns (carriage, arm)."""
    steel = K.mat("scanner steel", "#B8BCC0", rough=0.25, metal=0.9)
    blue = K.mat("scanner blue", "#1E4A7A", rough=0.4)
    x0, x1 = S5_TX0 - 0.1, S5_TX0 + 6 * S5_DX + 0.1
    yf = S5_TIER[0][0] - 0.12; ztop = S5_TIER[-1][1] + S5_JH + 0.12
    K.box("gantry rail", ((x0 + x1) / 2, yf, ztop), (x1 - x0 + 0.06, 0.04, 0.035), blue, bev=0.004)
    K.text("gantry word", "EU TEST", ((x0 + x1) / 2, yf - 0.022, ztop), 0.026, (math.pi / 2, 0, 0), hw_ink("gantry word", "#FFFFFF"), extrude=0.0004)
    car = K.empty("scanner carriage", (0, 0, 0))
    K.box("scanner head", (0, yf, ztop - 0.04), (0.07, 0.07, 0.06), blue, bev=0.006, parent=car)
    K.capsule("scan bar", Vector((0, yf, S5_TIER[0][1] - 0.02)), Vector((0, yf, ztop - 0.06)), 0.009, K.mat("scan red", "#FF3020", rough=0.3, emit=6.0), parent=car)
    hw_local(car)
    K.box("lever box", (S5_LEV.x, S5_LEV.y, S5_PIV / 2), (0.08, 0.1, S5_PIV), blue, bev=0.006)
    K.capsule("lever cable", Vector((S5_LEV.x, S5_LEV.y + 0.03, S5_PIV)), Vector((x1 + 0.03, yf + 0.02, ztop)), 0.006, K.mat("cable black", "#1A1A1A", rough=0.6))
    arm = K.empty("lever arm", (S5_LEV.x, S5_LEV.y, S5_PIV))
    K.cyl("lever rod", (0, 0, S5_LL / 2), 0.012, S5_LL, steel, v=16, bev=0.002, parent=arm)
    K.cyl("lever grip", (0, 0, S5_LL), 0.022, 0.09, K.mat("lever red", "#C8261E", rough=0.4), rot=(math.pi / 2, 0, 0), v=16, bev=0.004, parent=arm)
    K.sph("lever hub", (0, 0, 0), 0.03, steel, parent=arm)
    hw_local(arm)
    return car, arm


def shot5():
    """ALMOST HALF. Beside the stand of import jars (one red in every tier of seven) he hauls the scanner's lever
    down with both hands; its red bar sweeps along the tiers and two more in every tier spin red; he jumps back, leans
    in after it, points along the reds, then turns to us with his hands out: what's in your jar?"""
    W = hw_win
    T_IN = 0.9                                    # walks in to the lever
    T_GRIP = 1.1                                  # both hands on its grip
    T_PULL0, T_PULL1 = 1.3, 1.75                  # hauls it down
    T_S0, T_S1 = 1.8, 3.6                         # the bar sweeps the tiers on its own
    T_LET = 2.0                                   # lets go and jumps back
    T_LEAN = 2.6                                  # leans in after the bar
    T_POINT = 3.25                                # points along the reds
    T_SHOW = 4.3                                  # turns to us, hands out: what's in your jar?
    T_BACK = 5.0                                  # swings back to point at the reds, then back to us
    A_UP, A_DN = math.radians(-2), math.radians(44)       # leaning up, hauled down toward him
    light = place_market_alley()
    rnd = hw_random.Random(5)
    jars = s5_stand(rnd)
    car, arm = s5_scanner()
    x0, x1 = S5_TX0 - 0.08, S5_TX0 + 6 * S5_DX + 0.08
    def car_x(t):
        return x0 + (x1 - x0) * ease(min(1.0, max(0.0, (t - T_S0) / (T_S1 - T_S0))))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        car.location = (car_x(t), 0, 0); car.keyframe_insert("location", frame=f)
        a = A_UP + (A_DN - A_UP) * ease(min(1.0, max(0.0, (t - T_PULL0) / (T_PULL1 - T_PULL0))))
        a -= (A_DN - A_UP) * ease(min(1.0, max(0.0, (t - T_LET - 0.6) / 0.35)))       # let go, it springs back up
        arm.rotation_euler = (0, a, 0); arm.keyframe_insert("rotation_euler", frame=f)
    for row in jars:
        for i in S5_NEW:
            u = (S5_TX0 + i * S5_DX - x0) / (x1 - x0)
            tt = T_S0 + (T_S1 - T_S0) * min(range(101), key=lambda k: abs(ease(k / 100) - u)) / 100   # the bar reaches it
            jar_flip(row[i], tt)
    def grip_pt(t, dy):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return arm.matrix_world @ Vector((0, dy, S5_LL))
    # ---- him
    data = load_data()
    P0 = S5_P + Vector((0.17, 0.06, 0))   # from up the alley, three-quarter to us
    data.place(P0.x, P0.y, math.degrees(math.atan2((S5_P - P0).x, -(S5_P - P0).y)))
    hat = bee_hat(data)
    data.walk_to(S5_P, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw = data.arm.rotation_euler.z
    FACE_LEV = math.atan2(S5_LEV.x - S5_P.x, -(S5_LEV.y - S5_P.y)) + math.radians(16)     # three-quarter to us, not his back
    FACE_STAND = math.radians(-48); FACE_US = math.radians(-12)
    def yaw(t):
        y = yw + (FACE_LEV - yw) * W(t, T_IN - 0.05, 0.3)
        y += (FACE_STAND - FACE_LEV) * W(t, T_LET + 0.1, 0.35)
        y += (FACE_US - FACE_STAND) * W(t, T_SHOW - 0.3, 0.4)
        y += math.radians(22) * W(t, T_POINT, 0.7) * (1 - W(t, T_SHOW - 0.35, 0.3))     # his finger runs along the reds
        y += (FACE_STAND - FACE_US) * W(t, T_BACK, 0.35) * (1 - W(t, T_BACK + 0.8, 0.4))     # swings back to the rack: those ones
        return y
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        p = S5_P + Vector((0.16, -0.03, 0)) * W(t, T_PULL0 - 0.05, 0.5)                               # walks back, hauling it down
        p += Vector((0.04, -0.04, 0)) * W(t, T_LET + 0.25, 0.2) * (1 - W(t, T_LEAN, 0.35))                  # jumps back as it goes
        p += Vector((-0.04, 0, 0)) * W(t, T_LEAN, 0.35) * (1 - W(t, T_SHOW - 0.3, 0.4))              # leans in after the bar
        p += Vector((0.0, -0.06, 0)) * W(t, T_SHOW - 0.3, 0.4)                                        # and steps to us
        p += Vector((-0.04, 0.03, 0)) * W(t, T_POINT - 0.15, 0.3) * (1 - W(t, T_SHOW - 0.3, 0.4))   # a step after his finger
        p += Vector((-0.06, -0.04, 0)) * W(t, T_BACK + 0.8, 0.45)                                     # and again: what's in YOUR jar?
        z = 0.06 * hw_kick(t - T_LET - 0.28, 0.14) + 0.035 * hw_kick(t - T_PULL1 + 0.05, 0.12) + 0.05 * hw_kick(t - T_SHOW - 0.1, 0.14) \
            + 0.04 * hw_kick(t - T_SHOW - 1.1, 0.13) + 0.05 * hw_kick(t - T_SHOW - 2.0, 0.14) + 0.035 * hw_kick(t - T_POINT - 0.05, 0.12) + 0.04 * hw_kick(t - T_POINT - 0.5, 0.12)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (14 * W(t, T_PULL0 - 0.1, 0.3) * (1 - W(t, T_PULL1, 0.3)) - 12 * W(t, T_LET, 0.2) * (1 - W(t, T_LEAN, 0.3))
                                      + 16 * W(t, T_LEAN, 0.3) * (1 - W(t, T_SHOW - 0.4, 0.35)) - 6 * W(t, T_SHOW, 0.4), 0,
                                      8 * math.sin(2 * math.pi * (t - T_SHOW) / 1.1) * W(t, T_SHOW + 0.2, 0.4)), 0, DUR + 0.4)
    sc.frame_set(F(T_GRIP)); bpy.context.view_layer.update()
    near, far = sorted("LR", key=lambda s: acts._shoulder(data, s).y)     # [near the lens, far]
    rest = {s: hw_hand(data, s, [(0.0, (0.05, 0.08, -0.13)), (DUR + 0.3, (0.05, 0.08, -0.13))]) for s in "LR"}
    after = {near: hw_hand(data, near, [(0.0, (0.06, 0.1, -0.1)), (T_LET + 0.3, (0.1, 0.12, -0.03)), (T_LEAN + 0.2, (0.1, 0.1, -0.06)),
                                         (T_POINT, (0.16, 0.04, -0.03)), (T_POINT + 0.4, (0.15, 0.05, -0.03)), (T_SHOW - 0.2, (0.08, 0.1, -0.08)),
                                         (T_SHOW + 0.25, (0.12, 0.09, -0.04)),
            (T_BACK + 0.3, (0.16, 0.04, -0.03)), (T_BACK + 0.65, (0.15, 0.05, -0.05)), (T_SHOW + 2.0, (0.1, 0.07, -0.06)), (T_SHOW + 2.35, (0.16, 0.01, -0.025)), (DUR + 0.3, (0.16, 0.01, -0.025))]),     # hands out, down, out: what's in YOUR jar?
             far: hw_hand(data, far, [(0.0, (0.06, 0.1, -0.1)), (T_LET + 0.3, (0.08, 0.12, -0.03)), (T_LEAN + 0.2, (0.06, 0.1, -0.1)),
                                       (T_SHOW - 0.2, (0.06, 0.1, -0.1)), (T_SHOW + 0.25, (0.12, 0.09, -0.04)), (T_SHOW + 0.75, (0.06, 0.11, -0.11)), (T_SHOW + 1.2, (0.1, 0.12, -0.03)),
            (T_SHOW + 1.65, (0.05, 0.08, -0.12)), (T_SHOW + 2.05, (0.05, 0.11, -0.07)), (T_SHOW + 2.35, (0.02, 0.12, -0.06)), (DUR + 0.3, (0.02, 0.12, -0.06))])}
    def hand_fn(s, dy):
        def fn(t):
            g = W(t, T_GRIP - 0.7, 0.65)
            p = rest[s](t).lerp(grip_pt(t, dy), g)
            return p.lerp(after[s](t), W(t, T_LET, 0.6))
        return fn
    data.reach(near, hand_fn(near, -0.035), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(far, hand_fn(far, 0.035), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    CAM = Vector((0.34, -1.29, 0.7)); LOOK = Vector((0.34, 0.3, 0.74))
    data.look_at(Vector((S5_LEV.x, S5_LEV.y, 0.5)), 0.0, max_yaw=45, max_pitch=35, blend=0.0)
    data.look_at(Vector((0.05, 0.42, 1.05)), T_S0 + 0.1, max_yaw=32, max_pitch=40, blend=0.15)      # looks up: watches the bar sweep
    data.look_at(CAM, T_SHOW - 0.2, max_yaw=45, blend=0.18)
    data.expression("determined", 0.0, T_S0)
    data.expression("surprised", T_S0 + 0.3, T_SHOW - 0.3, blend=0.12)
    data.expression("worried", T_SHOW - 0.2, DUR + 1.0, blend=0.15)
    data.finish()
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 24, face_at=(0.68, 0.45), height=0.34, t=0.5 * DUR)   # framed first: beside the rack, whole
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24, fstop=7.0)
    camera_path(cam, lambda t: (CAM + (LOOK - CAM).normalized() * 0.03 * W(t, T_SHOW, 1.5), LOOK, Vector((0.1, 0.2, 0.7))))
    allj = [j for row in jars for j in row]
    return dict(lanes=[], kiosks=[], place="market_alley", light=light, data=data, rest=1, grips=("lever grip",),
                boxes=[("the rack of import jars and its scanner", lambda: meshes([j["root"] for j in allj] + [car]) + hw_drawn("rack", "gantry"), (0.0, 0.1, 0.8, 0.95)),
                       ("the rack's words", lambda: hw_drawn("stand stencil", "gantry word"), (0.0, 0.3, 1.0, 1.0))],
                conseq=[("he hauls the lever, the scanner's red bar sweeps the tiers and two more jars in every seven spin red: three in seven, almost half",
                         lambda: meshes([j["root"] for j in allj] + [car]), T_S0, DUR, {"hero": True, "moves": lambda: meshes([car])}),
                        ("the lever comes down in his hands", lambda: meshes([arm]), T_PULL0, T_PULL1 + 0.3)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
