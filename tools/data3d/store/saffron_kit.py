"""THE SAFFRON KIT (the third 3D short, 2026-11-13): a crocus that opens and closes, a jar of red threads, a gram scale
with a needle, a balance scale, a wicker basket, a farmhouse table and a wall clock. Kept for any spice, flower or
kitchen story after it. Units are the store's: metres at Data's scale (he is 0.96 tall, his hands hang at 0.30).

Every piece is MADE OF what it is (the 2D channel's rule, docs/CHANNEL_LOOK.md): a crocus is six cupped violet petals
with dark veins, three long crimson threads and three yellow stamens on a short pale stem, not a purple ball. It can
CLOSE on camera (shape key 'closed', per flower: each crocus owns its mesh so a wave can run across a field)."""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
import scene_kit as K
from clock import FPS

F = lambda t: int(round(t * FPS)) + 1
VIOLET, VIOLET_DK, THREAD, STAMEN, STEM = "#8A5BC8", "#4B2A7A", "#C81E12", "#F2C230", "#B9C98A"


def petal_mat():
    m = bpy.data.materials.get("crocus petal")
    if m: return m
    m = bpy.data.materials.new("crocus petal"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.45
    try: b.inputs["Subsurface Weight"].default_value = 0.25; b.inputs["Subsurface Radius"].default_value = (0.6, 0.3, 0.8)
    except KeyError: pass
    try: b.inputs["Sheen Weight"].default_value = 0.4
    except KeyError: pass
    # veins: dark violet lines running along the petal (UV v), the base of the petal darker
    uv = nt.nodes.new("ShaderNodeUVMap"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(uv.outputs["UV"], sep.inputs[0])
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.wave_type = 'BANDS'; wave.bands_direction = 'X'; wave.inputs["Scale"].default_value = 3.0
    wave.inputs["Distortion"].default_value = 2.0; nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
    vr = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(wave.outputs["Fac"], vr.inputs["Fac"])
    vr.color_ramp.elements[0].position = 0.0; vr.color_ramp.elements[0].color = (*K.lin(VIOLET_DK), 1)
    vr.color_ramp.elements[1].position = 0.35; vr.color_ramp.elements[1].color = (*K.lin(VIOLET), 1)
    base = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(sep.outputs["Y"], base.inputs["Fac"])
    base.color_ramp.elements[0].position = 0.0; base.color_ramp.elements[0].color = (*K.lin("#E8D9F5"), 1)
    base.color_ramp.elements[1].position = 0.22; base.color_ramp.elements[1].color = (1, 1, 1, 1)
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs["Factor"].default_value = 1.0
    nt.links.new(vr.outputs["Color"], mul.inputs["A"]); nt.links.new(base.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    return m


def _place(root, loc, yaw, parent):
    """children are built in the root's own frame (the root sits at the origin while they are made); then it moves"""
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    if parent is not None: root.parent = parent


def _mat(name, hexc, rough=0.5, emit=0.0, metal=0.0):
    return bpy.data.materials.get(name) or K.mat(name, hexc, rough=rough, emit=emit, metal=metal)


def crocus_mesh(name, H=0.16, R=0.05, seed=0, threads=True):
    """one crocus as ONE mesh: stem, six cupped petals (outer three wider), three crimson threads hanging over the
    rim, three yellow stamens. Shape key 'closed' folds every petal up into a bud. Petal UVs: x across, y along."""
    rnd = random.Random(seed)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new(); mi = {}
    mats = [petal_mat(), _mat("crocus thread", THREAD, rough=0.35), _mat("crocus stamen", STAMEN, rough=0.6), _mat("crocus stem", STEM, rough=0.7)]
    closed_co = {}

    def tube(a, b, r0, r1, mat_i, seg=8):
        a, b = Vector(a), Vector(b); d = (b - a).normalized(); nx = d.orthogonal().normalized(); ny = d.cross(nx)
        rings = []
        for k, (p, r) in enumerate(((a, r0), (b, r1))):
            rings.append([bm.verts.new(p + r * (math.cos(2 * math.pi * i / seg) * nx + math.sin(2 * math.pi * i / seg) * ny)) for i in range(seg)])
        for i in range(seg):
            f = bm.faces.new((rings[0][i], rings[0][(i + 1) % seg], rings[1][(i + 1) % seg], rings[1][i])); f.material_index = mat_i; f.smooth = True
        cap = bm.faces.new(list(reversed(rings[1]))); cap.material_index = mat_i
        return rings

    base_z = H * 0.38
    tube((0, 0, 0), (0, 0, base_z), 0.006, 0.008, 3)
    # petals: a grid u (across, -1..1) x v (along, 0..1), cupped, opening outward by `open_deg`
    nu, nv = 7, 9
    for k in range(6):
        outer = k % 2 == 0
        yaw = math.radians(60 * k + rnd.uniform(-6, 6)); L = H * (0.62 if outer else 0.56); Wd = R * (0.62 if outer else 0.5)
        open_deg, closed_deg = (50 if outer else 38) + rnd.uniform(-5, 5), 8 if outer else 4
        grid, gridc = [], []
        for j in range(nv):
            v = j / (nv - 1)
            row, rowc = [], []
            for i in range(nu):
                u = -1 + 2 * i / (nu - 1)
                w = Wd * math.sin(math.pi * min(1.0, v * 0.92 + 0.08)) ** 0.7 * (1 - 0.15 * v)     # narrow base, round tip
                for tgt, deg in ((row, open_deg), (rowc, closed_deg)):
                    tilt = math.radians(deg) * (0.35 + 0.65 * v * v) if deg > 30 else math.radians(deg) * (0.55 + 0.45 * v)                 # the petal curls out more toward its tip
                    along = Vector((0, -math.sin(tilt), math.cos(tilt)))       # radial out is -Y in the petal's frame
                    p = Vector((u * w, 0, 0)) + along * (v * L)
                    p.y += (u * u) * w * 0.35                                   # cupped: the edges come inward
                    p = Matrix.Rotation(yaw, 3, 'Z') @ p
                    p.z += base_z - 0.004; tgt.append(p)
            grid.append(row); gridc.append(rowc)
        vs = [[bm.verts.new(p) for p in row] for row in grid]
        for j in range(nv):
            for i in range(nu): closed_co[vs[j][i]] = gridc[j][i]
        for j in range(nv - 1):
            for i in range(nu - 1):
                f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i])); f.material_index = 0; f.smooth = True
                for lp, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))): lp[uvl].uv = (ii / (nu - 1), jj / (nv - 1))
    # threads: three crimson strands from the centre, arching up and over the rim; stamens: three shorter yellow ones
    def strand(n, length, r, mat_i, droop, spread):
        for k in range(n):
            a = math.radians(120 * k + 30 + rnd.uniform(-10, 10))
            pts = []
            for s in range(7):
                v = s / 6; out = spread * v * length; up = length * (0.85 * v) - droop * length * v * v
                pts.append(Vector((math.cos(a) * out, math.sin(a) * out, base_z + up)))
            for p0, p1 in zip(pts, pts[1:]):
                rings = tube(p0, p1, r, r * 0.95, mat_i, seg=6)
                for ring in rings:
                    for vv in ring: closed_co[vv] = Vector((vv.co.x * 0.35, vv.co.y * 0.35, vv.co.z))
            tip = tube(pts[-1], pts[-1] + (pts[-1] - pts[-2]).normalized() * r * 3, r * 1.9, r * 1.4, mat_i, seg=6)   # the thread flares at its end
            for ring in tip:
                for vv in ring: closed_co[vv] = Vector((vv.co.x * 0.35, vv.co.y * 0.35, vv.co.z))
    if threads: strand(3, H * 0.72, 0.0036, 1, 0.42, 0.6)
    strand(3, H * 0.3, 0.0028, 2, 0.1, 0.25)
    for v in bm.verts:
        if v not in closed_co: closed_co[v] = v.co.copy()
    me = bpy.data.meshes.new(name); bm.to_mesh(me)
    order = list(bm.verts); bm.free()
    for m in mats: me.materials.append(m)
    ob_tmp = bpy.data.objects.new("_tmp", me); bpy.context.collection.objects.link(ob_tmp)
    ob_tmp.shape_key_add(name="Basis"); sk = ob_tmp.shape_key_add(name="closed")
    for i, v in enumerate(order): sk.data[i].co = closed_co[v]
    sk.value = 0.0                              # a new shape key comes in at 1: the flower starts OPEN
    bpy.data.objects.remove(ob_tmp)
    return me


def crocus(name, loc, yaw=0.0, scale=1.0, seed=0, own=True, mesh=None, parent=None):
    """a crocus at loc. own=True: it gets its OWN mesh (it can close by itself); otherwise it shares `mesh`."""
    me = crocus_mesh(name, seed=seed) if (own or mesh is None) else mesh
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    o.location = loc; o.rotation_euler = (random.Random(seed).uniform(-0.12, 0.12), random.Random(seed + 1).uniform(-0.12, 0.12), yaw)
    o.scale = (scale, scale, scale)
    if parent: o.parent = parent
    return o


def close(o, t0, t1, to=1.0):
    """this flower folds shut from t0 to t1 (its own mesh's shape key)"""
    kb = o.data.shape_keys.key_blocks["closed"]
    kb.value = 0.0; kb.keyframe_insert("value", frame=F(t0)); kb.value = to; kb.keyframe_insert("value", frame=F(t1))


def flower_bed(x0, x1, y0, y1, dx=0.11, dy=0.11, seed=7, skip=lambda x, y: False, own_near=None, scale=(0.9, 1.15)):
    """a crocus field: flowers on a jittered grid. own_near(x, y) -> True gives that flower its own mesh (so it can
    close); the rest share a few templates (fast)."""
    rnd = random.Random(seed); tmpl = [crocus_mesh(f"crocus tmpl {k}", seed=100 + k) for k in range(5)]
    own, rest = [], []
    y = y0
    while y < y1:
        x = x0 + rnd.uniform(0, dx)
        while x < x1:
            px, py = x + rnd.uniform(-0.03, 0.03), y + rnd.uniform(-0.03, 0.03)
            if not skip(px, py):
                mine = bool(own_near and own_near(px, py))
                o = crocus(f"crocus {len(own) + len(rest)}", (px, py, 0.0), yaw=rnd.uniform(0, 6.28), scale=rnd.uniform(*scale) * (1 + 0.15 * (py > 3)),
                           seed=rnd.randint(0, 10 ** 6), own=mine, mesh=tmpl[rnd.randrange(5)])
                (own if mine else rest).append(o)
            x += dx * rnd.uniform(0.8, 1.25)
        y += dy * (1 + 0.04 * max(0.0, y))
    return own, rest


def leaves_tuft(name, loc, seed=0, parent=None):
    """the grass-like crocus leaves around a flower: thin dark green blades with a pale stripe"""
    rnd = random.Random(seed); m = _mat("crocus leaf", "#3E6B2E", rough=0.6)
    bm = bmesh.new()
    for k in range(5):
        a = rnd.uniform(0, 6.28); L = rnd.uniform(0.09, 0.14); lean = rnd.uniform(0.15, 0.4)
        prev = None
        for s in range(5):
            v = s / 4; c = Vector((math.cos(a) * lean * L * v * v, math.sin(a) * lean * L * v * v, L * v)); w = 0.004 * (1 - v * 0.8)
            side = Vector((-math.sin(a), math.cos(a), 0)) * w
            pair = (bm.verts.new(c - side), bm.verts.new(c + side))
            if prev: f = bm.faces.new((prev[0], prev[1], pair[1], pair[0])); f.smooth = True
            prev = pair
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o); o.location = loc
    if parent: o.parent = parent
    return o


# ------------------------------------------------------------------ the shop end of it
def jar(name, loc, h=0.07, r=0.024, fill=0.85, parent=None):
    """a little glass spice jar with a black lid, a white label and red threads packed inside. The threads fill it to
    the glass and the label is a thin band (2026-11-13 judge, at phone size: "reads as a small black pot, not
    saffron"): from across a room it has to read as a jar of RED."""
    root = K.empty(name, (0, 0, 0))
    glass = bpy.data.materials.get("jar glass")
    if not glass:
        glass = bpy.data.materials.new("jar glass"); glass.use_nodes = True; b = glass.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.95, 0.97, 1.0, 1); b.inputs["Roughness"].default_value = 0.05
        b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.45
    K.cyl(name + " glass", (0, 0, h * 0.42), r, h * 0.84, glass, parent=root, bev=0.003)
    K.cyl(name + " lid", (0, 0, h * 0.9), r * 1.04, h * 0.18, _mat("jar lid", "#1C1B1E", rough=0.35, metal=0.4), parent=root, bev=0.002)
    lab = K.cyl(name + " label", (0, 0, h * 0.62), r * 1.006, h * 0.1, _mat("jar label", "#F3EEE2", rough=0.7), parent=root, bev=0.0)
    lab.scale = (1, 1, 1)
    threads = bpy.data.materials.get("saffron threads") or K.mat("saffron threads", "#D8260F", rough=0.5)
    rnd = random.Random(len(name))
    for k in range(110):                     # loose threads packed to the glass: little curled sticks
        a = rnd.uniform(0, 6.28); rr = r * 0.8 * math.sqrt(rnd.uniform(0, 1)); z = rnd.uniform(0.008, h * 0.8 * fill)
        c = K.cyl(f"{name} thread {k}", (math.cos(a) * rr, math.sin(a) * rr, z), 0.0028, r * 0.7, threads,
                  rot=(rnd.uniform(0, 3.1), rnd.uniform(0, 3.1), 0), v=6, bev=0, parent=root)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root


def cash_stack(name, loc, n=40, yaw=0.0, parent=None, mesh=None, seed=0):
    """a fat stack of banknotes with a paper band: a block of note-edges (pale paper, a fine line per note) with a
    printed note on top, so it reads as MONEY from the side as well as from above"""
    import props
    me = mesh or props.bill_mesh(name + " bill", w=0.1, h=0.045)
    root = K.empty(name, (0, 0, 0))
    H = 0.0012 * n
    edge = bpy.data.materials.get("note edges")
    if not edge:
        edge = bpy.data.materials.new("note edges"); edge.use_nodes = True; nt = edge.node_tree; b = nt.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = 0.8
        tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sep.inputs[0])
        mt = nt.nodes.new("ShaderNodeMath"); mt.operation = 'MULTIPLY'; mt.inputs[1].default_value = 800.0; nt.links.new(sep.outputs["Z"], mt.inputs[0])
        sn = nt.nodes.new("ShaderNodeMath"); sn.operation = 'SINE'; nt.links.new(mt.outputs[0], sn.inputs[0])
        rp = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(sn.outputs[0], rp.inputs["Fac"])
        rp.color_ramp.elements[0].color = (*K.lin("#A9BC98"), 1); rp.color_ramp.elements[1].color = (*K.lin("#E4ECD8"), 1)
        nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    K.box(name + " block", (0, 0, H / 2), (0.098, 0.044, H), edge, bev=0.0008, parent=root)
    o = bpy.data.objects.new(name + " top note", me); bpy.context.collection.objects.link(o); o.parent = root; o.location = (0, 0, H + 0.0004)
    K.box(name + " band", (0, 0, H * 0.5), (0.02, 0.0455, H + 0.0016), _mat("cash band", "#D9B65A", rough=0.6), bev=0.0004, parent=root)
    _place(root, loc, yaw, parent)
    return root


def gram_scale(name, loc, yaw=0.0, parent=None):
    """a little kitchen scale: a white body, a round steel pan on top and a big round dial on its front with a red
    needle. Returns (root, needle) -- key needle.rotation_euler.y (radians, + clockwise as seen from the front)."""
    root = K.empty(name, (0, 0, 0))
    body = _mat("scale body", "#EDEBE6", rough=0.35); steel = _mat("scale steel", "#C9CCD0", rough=0.25, metal=0.9)
    K.box(name + " body", (0, 0, 0.035), (0.11, 0.1, 0.07), body, bev=0.012, parent=root)
    K.cyl(name + " post", (0, 0, 0.078), 0.008, 0.02, steel, parent=root)
    K.cyl(name + " pan", (0, 0, 0.09), 0.055, 0.008, steel, parent=root, bev=0.003)
    face = K.cyl(name + " dial", (0, -0.051, 0.036), 0.036, 0.004, _mat("scale dial", "#FBFAF6", rough=0.4), rot=(math.pi / 2, 0, 0), parent=root, bev=0.001)
    ink = _mat("scale ink", "#1C1B1E", rough=0.5)
    for k in range(11):                       # ticks round the top of the dial
        a = math.radians(-120 + 24 * k)
        K.box(f"{name} tick {k}", (0.028 * math.sin(a), -0.054, 0.036 + 0.028 * math.cos(a)), (0.0016, 0.001, 0.007 if k % 5 == 0 else 0.004), ink,
              bev=0, parent=root).rotation_euler = (0, a, 0)
    piv = K.empty(name + " needle pivot", (0, -0.055, 0.036), parent=root)
    nd = K.box(name + " needle", (0, -0.055, 0.049), (0.0048, 0.0014, 0.03), _mat("scale needle", "#D21F1A", rough=0.4), bev=0, parent=piv)   # thick enough to see move on a phone
    K.cyl(name + " needle cap", (0, -0.057, 0.036), 0.006, 0.003, _mat("scale needle", "#D21F1A", rough=0.4), rot=(math.pi / 2, 0, 0), parent=root, bev=0.0005)
    K.cyl(name + " hub", (0, -0.0565, 0.036), 0.004, 0.003, ink, rot=(math.pi / 2, 0, 0), parent=root)
    piv.rotation_euler = (0, math.radians(-120), 0)
    z0 = K.box(name + " zero mark", (0, -0.0535, 0.036), (0.006, 0.0015, 0.012), ink, bev=0, parent=root)   # a bold zero where the needle rests:
    z0.location = (0.026 * math.sin(math.radians(-120)), -0.0535, 0.036 + 0.026 * math.cos(math.radians(-120)))   # "barely moved" is measured from it
    z0.rotation_euler = (0, math.radians(-120), 0)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root, piv


def balance(name, loc, arm=0.22, h=0.32, yaw=0.0, parent=None, pan_r=0.075):
    """an old brass balance scale: a column, a beam on a pivot, two pans hanging on chains. Returns (root, beam, pans):
    key beam.rotation_euler.y (radians; + drops the RIGHT pan as seen from the front); the pans stay level."""
    root = K.empty(name, (0, 0, 0))
    brass = _mat("brass", "#B8893A", rough=0.3, metal=0.9); wood = _mat("balance base", "#4A3020", rough=0.5)
    K.box(name + " base", (0, 0, 0.015), (0.16, 0.1, 0.03), wood, bev=0.006, parent=root)
    K.cyl(name + " column", (0, 0, h / 2), 0.008, h, brass, parent=root)
    K.sph(name + " finial", (0, 0, h + 0.012), 0.012, brass, parent=root)
    beam = K.empty(name + " beam", (0, 0, h), parent=root)
    K.box(name + " beam bar", (0, 0, h), (arm * 2, 0.008, 0.012), brass, bev=0.002, parent=beam)
    pans = []
    for sg in (-1, 1):
        hang = K.empty(f"{name} hanger {sg}", (sg * arm, 0, h), parent=beam)
        drop = h * 0.62
        for a in (0, 2.09, 4.19):
            c = K.cyl(f"{name} chain {sg}{a}", (sg * arm + 0.03 * math.cos(a) * 0.5, 0.03 * math.sin(a) * 0.5, h - drop / 2), 0.0012, drop * 1.01, brass, parent=hang, v=6, bev=0)
            c.rotation_euler = (math.atan2(0.015 * math.sin(a), drop) * 1, -math.atan2(0.015 * math.cos(a), drop), 0)
        pan = K.cyl(f"{name} pan {sg}", (sg * arm, 0, h - drop), pan_r, 0.01, brass, parent=hang, bev=0.004)
        pans.append(hang)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root, beam, pans


def level_pans(beam, pans, nf):
    """the pans hang straight down whatever the beam does"""
    for f in range(1, nf + 1):
        bpy.context.scene.frame_set(f)
        for p in pans: p.rotation_euler = (0, -beam.rotation_euler.y, 0); p.keyframe_insert("rotation_euler", frame=f)


def basket(name, loc, r=0.13, h=0.1, parent=None):
    """a round wicker basket with a handle, open at the top"""
    root = K.empty(name, (0, 0, 0))
    m = _mat("wicker", "#B98A4E", rough=0.85)
    bm = bmesh.new(); seg = 28
    rings = []
    for j, (z, rr) in enumerate(((0.0, r * 0.82), (h * 0.5, r * 0.95), (h, r))):
        rings.append([bm.verts.new((rr * math.cos(2 * math.pi * i / seg), rr * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg): bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i])).smooth = True
    bm.faces.new(list(reversed(rings[0])))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name + " body", me); bpy.context.collection.objects.link(o); o.parent = root
    sol = o.modifiers.new("wall", 'SOLIDIFY'); sol.thickness = 0.008
    # weave: wavy bands of a darker cane
    dk = _mat("wicker dark", "#8A6232", rough=0.85)
    for j in range(5):
        z = h * (0.12 + 0.19 * j); rr = r * (0.84 + 0.16 * (z / h)) + 0.004
        t = bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=0.0035, location=(0, 0, 0)); band = bpy.context.active_object
        band.name = f"{name} band {j}"; band.data.materials.append(dk); band.parent = root; band.location = (0, 0, z)
    bpy.ops.mesh.primitive_torus_add(major_radius=r * 0.95, minor_radius=0.006); hd = bpy.context.active_object
    hd.name = name + " handle"; hd.data.materials.append(m); hd.parent = root; hd.location = (0, 0, h); hd.rotation_euler = (math.pi / 2, 0, 0)
    hd.scale = (1, 0.9, 1)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root


def table(name, loc, w=0.9, d=0.5, h=0.38, parent=None):
    """an old farmhouse table: a thick plank top, four square legs"""
    root = K.empty(name, (0, 0, 0))
    top = bpy.data.materials.get("farm table") or _plank_mat()
    K.box(name + " top", (0, 0, h - 0.018), (w, d, 0.036), top, bev=0.006, parent=root)
    leg = _mat("farm table leg", "#5A3B24", rough=0.7)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box(name + " leg", (sx * (w / 2 - 0.04), sy * (d / 2 - 0.04), (h - 0.036) / 2), (0.04, 0.04, h - 0.036), leg, bev=0.004, parent=root)
    _place(root, loc, locals().get("yaw", 0.0), parent)
    return root


def _plank_mat():
    m = bpy.data.materials.new("farm table"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.55
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.6, 9.0, 0.6)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.bands_direction = 'Y'; wave.inputs["Scale"].default_value = 1.2; wave.inputs["Distortion"].default_value = 1.5; wave.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(wave.outputs["Fac"], r.inputs["Fac"])
    r.color_ramp.elements[0].color = (*K.lin("#6E4A2C"), 1); r.color_ramp.elements[1].color = (*K.lin("#9A6E44"), 1)
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    return m


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
