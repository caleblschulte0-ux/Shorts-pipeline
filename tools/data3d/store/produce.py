"""THE PRODUCE KIT: bananas, bunches, a hanging rail, a crate, a planter and a banana plant, built for the second 3D
short (the Cavendish clone story) and kept for any produce story after it.

Every piece is MADE OF what it is: a banana is a ridged, tapering, curved finger with a green neck, a stem and a dark
tip, not a yellow capsule; a bunch is fingers fanned off one crown; a plant is a pseudostem with long split leaves.
And every piece can DIE on camera, because the stories that need produce are about rot, blight and spoilage:
  rot(obj_or_mat, t0, t1)   the skin goes yellow -> freckled -> brown -> black, spots first (a noise threshold, keyed)
  wilt(leaf, t0, t1)        a leaf droops on its hinge and goes from green to straw
Materials are per piece (rot is keyed on the material), named "banana skin <name>" so style.py never restyles them.
Units are the store's: metres at Data's scale (U = 0.56 of adult size)."""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
import scene_kit as K
from clock import FPS

U = K.U
F = lambda t: int(round(t * FPS)) + 1

YELLOW, GREENISH, TIP, BROWN, BLACK = "#F0C93A", "#B8B640", "#2A2116", "#4A3018", "#140F0A"   # a dead skin is black-brown: the old milk-chocolate brown read as a paper bag


# ------------------------------------------------------------------ materials that can rot
def skin_mat(name, base=YELLOW, neck=GREENISH, rough=0.42, climb=False):
    """a banana skin: yellow body, green toward the stem (along the finger's own length, the mesh's UV u), a dark tip,
    and a ROT input (the 'rot' value node, 0 fresh .. 1 black) that spreads brown spots, then black, over it.
    climb=True: the rot RISES from the bottom of the object (a wilt climbing a stem out of the soil): only the part
    below a front that rides up with rot is spotted and darkened."""
    m = bpy.data.materials.new(f"banana skin {name}"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough; b.inputs["Specular IOR Level"].default_value = 0.35
    try: b.inputs["Coat Weight"].default_value = 0.12; b.inputs["Coat Roughness"].default_value = 0.35   # the waxy sheen of a fresh skin
    except KeyError: pass
    uv = nt.nodes.new("ShaderNodeUVMap"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(uv.outputs["UV"], sep.inputs[0])
    # along the finger: 0 at the stem .. 1 at the tip
    ramp = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(sep.outputs["X"], ramp.inputs["Fac"])
    es = ramp.color_ramp.elements
    es[0].position = 0.0; es[0].color = (*K.lin(neck), 1)
    es[1].position = 0.3; es[1].color = (*K.lin(base), 1)
    e = es.new(0.93); e.color = (*K.lin(base), 1)
    e = es.new(0.985); e.color = (*K.lin(TIP), 1)
    # the rot: brown spots where a noise passes a threshold that falls as rot rises, then the whole skin darkens
    rot = nt.nodes.new("ShaderNodeValue"); rot.name = "rot"; rot.label = "rot"; rot.outputs[0].default_value = 0.0
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 38.0
    nz.inputs["Detail"].default_value = 3.0; nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    thr = nt.nodes.new("ShaderNodeMath"); thr.operation = "MULTIPLY_ADD"; thr.inputs[1].default_value = -0.98; thr.inputs[2].default_value = 0.9
    nt.links.new(rot.outputs[0], thr.inputs[0])                                   # threshold = 0.9 - 0.98 * rot
    spot = nt.nodes.new("ShaderNodeMath"); spot.operation = 'GREATER_THAN'
    nt.links.new(nz.outputs["Fac"], spot.inputs[0]); nt.links.new(thr.outputs[0], spot.inputs[1])
    mix1 = nt.nodes.new("ShaderNodeMix"); mix1.data_type = 'RGBA'; mix1.inputs["B"].default_value = (*K.lin(BROWN), 1)
    nt.links.new(spot.outputs[0], mix1.inputs["Factor"]); nt.links.new(ramp.outputs["Color"], mix1.inputs["A"])
    dark = nt.nodes.new("ShaderNodeMapRange"); dark.inputs["From Min"].default_value = 0.3; dark.inputs["From Max"].default_value = 0.85
    nt.links.new(rot.outputs[0], dark.inputs["Value"])
    mix2 = nt.nodes.new("ShaderNodeMix"); mix2.data_type = 'RGBA'; mix2.inputs["B"].default_value = (*K.lin(BLACK), 1)
    fac_spot, fac_dark = spot.outputs[0], dark.outputs["Result"]
    if climb:   # the front: Generated Z (0 at the base .. 1 at the top) under rot * 1.3 - 0.15, a soft edge
        sz = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sz.inputs[0])
        fr = nt.nodes.new("ShaderNodeMath"); fr.operation = 'MULTIPLY_ADD'; fr.inputs[1].default_value = 1.3; fr.inputs[2].default_value = -0.15
        nt.links.new(rot.outputs[0], fr.inputs[0])
        df = nt.nodes.new("ShaderNodeMath"); df.operation = 'SUBTRACT'; nt.links.new(fr.outputs[0], df.inputs[0]); nt.links.new(sz.outputs["Z"], df.inputs[1])
        mk = nt.nodes.new("ShaderNodeMapRange"); mk.inputs["From Min"].default_value = -0.04; mk.inputs["From Max"].default_value = 0.08
        nt.links.new(df.outputs[0], mk.inputs["Value"])
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = 'MULTIPLY'; nt.links.new(spot.outputs[0], m1.inputs[0]); nt.links.new(mk.outputs["Result"], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = 'MULTIPLY'; nt.links.new(mk.outputs["Result"], m2.inputs[0])
        one = nt.nodes.new("ShaderNodeMath"); one.operation = 'MAXIMUM'; one.inputs[1].default_value = 0.6; nt.links.new(rot.outputs[0], one.inputs[0])
        nt.links.new(one.outputs[0], m2.inputs[1])        # under the front it is dark at once, not only spotted
        fac_spot, fac_dark = m1.outputs[0], m2.outputs[0]
        nt.links.new(fac_spot, mix1.inputs["Factor"])
    nt.links.new(fac_dark, mix2.inputs["Factor"]); nt.links.new(mix1.outputs["Result"], mix2.inputs["A"])
    nt.links.new(mix2.outputs["Result"], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough; rr.inputs["To Max"].default_value = 0.8   # a dead skin goes dull
    nt.links.new(rot.outputs[0], rr.inputs["Value"]); nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    return m


def rot_node(m):
    return m.node_tree.nodes["rot"].outputs[0]


def rot(m, t0, t1, to=1.0, frm=0.0):
    """the skin rots from frm to `to` over t0..t1 (ease in: it starts as freckles and races to black)"""
    v = rot_node(m)
    v.default_value = frm; v.keyframe_insert("default_value", frame=1)
    v.default_value = frm; v.keyframe_insert("default_value", frame=max(1, F(t0)))
    v.default_value = to; v.keyframe_insert("default_value", frame=max(2, F(t1)))


# ------------------------------------------------------------------ a banana
def banana_mesh(name, L=0.13, R=0.0165, bend=0.95, ridges=5, rings=22, seg=20):
    """one finger along +X from its stem end at the origin, curving UP (+Z) through `bend` radians. The cross-section
    is a rounded pentagon (ridges), the radius swells to the middle and pinches at the neck and the tip. UV u runs
    stem -> tip so the skin ramp knows where the neck is."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    Rc = L / bend                      # radius of the arc the spine follows
    rings_v = []
    for i in range(rings + 1):
        u = i / rings; a = -bend / 2 + bend * u
        c = Vector((Rc * math.sin(a), 0, Rc * (1 - math.cos(a)) - Rc * (1 - math.cos(bend / 2))))   # the spine
        tan = Vector((math.cos(a), 0, math.sin(a))); nrm = Vector((-math.sin(a), 0, math.cos(a))); side = Vector((0, 1, 0))
        # the profile: a thin neck (0..0.16), the full body, a rounded taper to a blunt tip
        if u < 0.16: r = R * (0.32 + 0.68 * math.sin(u / 0.16 * math.pi / 2) ** 1.4)
        elif u > 0.8: r = R * max(0.18, math.cos((u - 0.8) / 0.2 * math.pi / 2) ** 0.7)
        else: r = R * (1.0 + 0.06 * math.sin((u - 0.16) / 0.64 * math.pi))
        ring = []
        for j in range(seg):
            th = 2 * math.pi * j / seg
            k = 1.0 + 0.07 * math.cos(ridges * th)          # the ridges
            p = c + (nrm * math.cos(th) * 1.05 + side * math.sin(th)) * r * k
            ring.append(bm.verts.new(p))
        rings_v.append(ring)
    for i in range(rings):
        for j in range(seg):
            a, b_, c_, d = rings_v[i][j], rings_v[i][(j + 1) % seg], rings_v[i + 1][(j + 1) % seg], rings_v[i + 1][j]
            f = bm.faces.new((a, b_, c_, d))
            for lp, (uu, vv) in zip(f.loops, ((i / rings, j / seg), (i / rings, (j + 1) / seg), ((i + 1) / rings, (j + 1) / seg), ((i + 1) / rings, j / seg))):
                lp[uvl].uv = (uu, vv)
    for ring, uu in ((rings_v[0], 0.0), (rings_v[-1], 1.0)):   # caps: the cut stem end and the tip
        f = bm.faces.new(list(reversed(ring)) if uu == 0.0 else ring)
        for lp in f.loops: lp[uvl].uv = (uu, 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return me


def bunch(name, loc, m, n=6, L=0.13, spread=0.85, seed=0, parent=None, hang=False, stem_len=0.05):
    """a HAND of bananas: n fingers fanned off one crown, in two rows like a real hand, a short woody stem. The root is
    at the crown. Lying (hang=False) the fingers curve up off the table; hanging (hang=True) the stem points up to the
    hook and the fingers curve out and up below it. Returns (root, fingers)."""
    rnd = random.Random(seed); root = K.empty(name, loc, parent=parent)
    stem_m = K.mat("banana stem", "#5E5A2E", rough=0.8)
    fingers = []
    for k in range(n):
        row = k % 2; a = (k - (n - 1) / 2) / max(1, n - 1) * spread
        me = banana_mesh(f"{name} finger {k}", L=L * rnd.uniform(0.93, 1.05), R=0.0165 * L / 0.13, bend=rnd.uniform(0.85, 1.05))
        o = bpy.data.objects.new(f"{name} finger {k}", me); me.materials.append(m); K._link(o, root)
        # fan about the crown: yaw by a, the back row a little higher and tilted
        o.location = Vector(loc) + Vector((0, (row - 0.5) * 0.012, row * 0.012)) * (L / 0.13)
        o.rotation_euler = (0.0, -0.25 - 0.18 * row, a)
        fingers.append(o)
    st = K.cyl(f"{name} crown", Vector(loc) + Vector((-0.012, 0, 0.004)), 0.011, 0.03, stem_m, rot=(0, math.radians(90), 0), v=10, parent=root)
    K.cyl(f"{name} stem", Vector(loc) + Vector((-0.012 - stem_len / 2, 0, 0.004 + stem_len * 0.3)), 0.007, stem_len, stem_m,
          rot=(0, math.radians(60), 0), v=8, parent=root)
    if hang: root.rotation_euler = (0, math.radians(-90), 0)
    return root, fingers


# ------------------------------------------------------------------ fixtures
def table(name, loc, w=0.9, d=0.45, h=0.42, parent=None):
    """a produce table: a tilted slatted top in stained wood on a dark frame, a price rail on the front edge"""
    root = K.empty(name, loc, parent=parent); x, y, z = loc
    wood = K.mat("produce wood", "#8A6A48", rough=0.7); frame = K.mat("produce frame", "#2E3034", rough=0.5, metal=0.4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box(f"{name} leg", (x + sx * (w / 2 - 0.03), y + sy * (d / 2 - 0.03), h / 2), (0.03, 0.03, h), frame, bev=0.004, parent=root)
    for k in range(5):
        K.box(f"{name} slat", (x, y - d / 2 + d * (k + 0.5) / 5, h + 0.006 + 0.004 * k), (w, d / 5 - 0.008, 0.016), wood, bev=0.004, parent=root)
    K.box(f"{name} lip", (x, y - d / 2 - 0.004, h + 0.03), (w, 0.012, 0.05), wood, bev=0.004, parent=root)
    return root


def rail(name, x0, x1, y, z, n_hooks, parent=None):
    """a chrome rail on two posts with n hooks hanging from it; returns (root, hook points) where a bunch's stem goes"""
    root = K.empty(name, ((x0 + x1) / 2, y, z), parent=parent)
    chrome = K.mat("rail chrome", "#C9CDD2", rough=0.22, metal=0.9)
    K.cyl(f"{name} bar", ((x0 + x1) / 2, y, z), 0.008, x1 - x0 + 0.08, chrome, rot=(0, math.radians(90), 0), v=16, parent=root)
    for xp in (x0 - 0.03, x1 + 0.03):
        K.cyl(f"{name} post", (xp, y, z / 2), 0.012, z, chrome, v=16, parent=root)
        K.cyl(f"{name} foot", (xp, y, 0.008), 0.06, 0.016, K.mat("produce frame"), v=24, parent=root)
    pts = []
    for k in range(n_hooks):
        hx = x0 + (x1 - x0) * (k + 0.5) / n_hooks
        K.cyl(f"{name} hook {k}", (hx, y, z - 0.035), 0.0035, 0.07, chrome, v=8, parent=root)
        pts.append(Vector((hx, y, z - 0.07)))
    return root, pts


def crate(name, loc, w=0.34, d=0.24, h=0.17, stencil="GROS MICHEL", year="1950", parent=None):
    """an old wooden fruit crate: slatted sides, corner posts, a stencilled name on the front, and a LID hinged on
    its back edge (lid empty's x rotation opens it). Returns dict(root, lid, inner_z)."""
    root = K.empty(name, loc, parent=parent); x, y, z = loc
    wood = K.mat("crate wood", "#9C7B52", rough=0.85); dark = K.mat("crate post", "#6E5536", rough=0.85)
    ink = K.mat("crate ink", "#3B2A1A", rough=0.9)
    for k in range(3):   # side slats, a gap between each
        zz = z + 0.02 + k * (h - 0.02) / 3 + 0.025
        K.box(f"{name} front slat", (x, y - d / 2, zz), (w, 0.012, (h - 0.02) / 3 - 0.012), wood, bev=0.002, parent=root)
        K.box(f"{name} back slat", (x, y + d / 2, zz), (w, 0.012, (h - 0.02) / 3 - 0.012), wood, bev=0.002, parent=root)
        for sx in (-1, 1): K.box(f"{name} end slat", (x + sx * w / 2, y, zz), (0.012, d, (h - 0.02) / 3 - 0.012), wood, bev=0.002, parent=root)
    for sx in (-1, 1):
        for sy in (-1, 1): K.box(f"{name} corner", (x + sx * (w / 2 - 0.006), y + sy * (d / 2 - 0.006), z + h / 2), (0.022, 0.022, h), dark, bev=0.002, parent=root)
    K.box(f"{name} floor", (x, y, z + 0.008), (w, d, 0.012), dark, bev=0.002, parent=root)
    K.text(f"{name} stencil", stencil, (x, y - d / 2 - 0.007, z + h * 0.62), 0.042, (math.radians(90), 0, 0), ink, extrude=0.0006, parent=root)
    K.text(f"{name} year", year, (x, y - d / 2 - 0.007, z + h * 0.3), 0.034, (math.radians(90), 0, 0), ink, extrude=0.0006, parent=root)
    hinge = K.empty(f"{name} lid", (x, y + d / 2, z + h + 0.008), parent=root)
    for k in range(3):
        K.box(f"{name} lid slat", (x, y + d / 2 - d * (k + 0.5) / 3, z + h + 0.008), (w + 0.01, d / 3 - 0.008, 0.012), wood, bev=0.002, parent=hinge)
    return dict(root=root, lid=hinge, inner_z=z + 0.016, w=w, d=d, h=h)


def planter(name, loc, w=0.34, d=0.26, h=0.2, parent=None):
    """a slatted wooden planter box with a mound of dark soil; returns dict(root, soil, top_z)"""
    root = K.empty(name, loc, parent=parent); x, y, z = loc
    wood = K.mat("planter wood", "#7C6146", rough=0.85)
    for sx in (-1, 1): K.box(f"{name} end", (x + sx * w / 2, y, z + h / 2), (0.018, d, h), wood, bev=0.003, parent=root)
    for sy in (-1, 1): K.box(f"{name} side", (x, y + sy * d / 2, z + h / 2), (w + 0.018, 0.018, h), wood, bev=0.003, parent=root)
    soil_m = K.mat("soil", "#3A2A1E", rough=0.95)
    soil = K.sph(f"{name} soil", (x, y, z + h - 0.035), 0.5, soil_m, scale=(w - 0.01, d - 0.01, 0.07), parent=root, seg=32, ring=12)
    tx = bpy.data.textures.get("clods") or bpy.data.textures.new("clods", 'CLOUDS'); tx.noise_scale = 0.05
    md = soil.modifiers.new("clods", "DISPLACE"); md.texture = tx; md.strength = 0.012; md.mid_level = 0.5
    return dict(root=root, soil=soil, top_z=z + h)


def plant(name, base, height=0.42, n_leaves=6, seed=0, parent=None, angles=None):
    """a young banana plant: a green pseudostem rising from `base`, n long paddle leaves on hinges near its top, each a
    curved blade with a midrib. Every leaf has its own material so it can wilt on its own. Returns dict(root, stem,
    leaves=[(hinge, mat)], stem_mat). angles (degrees, 0 = +X): where the leaves point, for a plant staged to the lens
    (leaves to the sides read as a plant when they droop; leaves all round it closed into a pod)."""
    rnd = random.Random(seed); root = K.empty(name, base, parent=parent); bx, by, bz = base
    stem_m = skin_mat(f"{name} stem", base="#6E9A3E", neck="#86A84A", rough=0.55, climb=True)
    stem = K.cyl(f"{name} pseudostem", (bx, by, bz + height / 2), 0.03, height, stem_m, v=20, parent=root)
    for v in stem.data.vertices:     # tapering, and the UV-less cylinder gets its 'along' from object Z via the rot noise only
        k = 1.0 - 0.35 * (v.co.z / height + 0.5); v.co.x *= k; v.co.y *= k
    leaves = []
    for k in range(len(angles) if angles else n_leaves):
        a = math.radians(angles[k]) if angles else k * 2 * math.pi / n_leaves + rnd.uniform(-0.25, 0.25)
        lm = skin_mat(f"{name} leaf {k}", base="#4F8A35", neck="#5E9A3C", rough=0.5)
        hz = bz + height * (0.78 + 0.05 * (k % 3))
        hinge = K.empty(f"{name} leaf hinge {k}", (bx, by, hz), parent=root)
        hinge.rotation_euler = (0, 0, a)
        # the blade: a strip along +X from the hinge, rising then arching, 0.32 long, 0.09 wide
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); Lb, Wb, n = 0.28, 0.11, 14; rows = []
        for i in range(n + 1):
            u = i / n; xx = Lb * u; zz = 0.075 * math.sin(u * math.pi * 0.85) - 0.05 * u * u     # a paddle arching OUT, not a cup
            ww = Wb * (0.25 + 0.75 * math.sin(min(1.0, u * 1.25) * math.pi * 0.5)) * (1 - 0.6 * max(0, u - 0.8) / 0.2)
            rows.append([bm.verts.new((xx, s * ww / 2, zz - abs(s) * 0.012)) for s in (-1, 0, 1)])
        for i in range(n):
            for j in range(2):
                f = bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
                for lp, uv in zip(f.loops, ((i / n, j / 2), (i / n, (j + 1) / 2), ((i + 1) / n, (j + 1) / 2), ((i + 1) / n, j / 2))): lp[uvl].uv = uv
        me = bpy.data.meshes.new(f"{name} leaf {k}"); bm.to_mesh(me); bm.free(); me.materials.append(lm)
        for p in me.polygons: p.use_smooth = True
        lo = bpy.data.objects.new(f"{name} leaf {k}", me); bpy.context.collection.objects.link(lo); lo.parent = hinge
        sol = lo.modifiers.new("thick", "SOLIDIFY"); sol.thickness = 0.003
        hinge.rotation_euler = (0, math.radians(4 + 8 * (k % 2)), a)   # out, arching over
        leaves.append((hinge, lm))
    return dict(root=root, stem=stem, leaves=leaves, stem_mat=stem_m)


def wilt(hinge, mat, t0, t1, droop_deg=70, to=0.75):
    """a leaf sags on its hinge by droop_deg and goes from green to straw-brown (its rot) over t0..t1"""
    r0 = tuple(hinge.rotation_euler)
    hinge.rotation_euler = r0; hinge.keyframe_insert("rotation_euler", frame=1); hinge.keyframe_insert("rotation_euler", frame=max(1, F(t0)))
    for i in range(1, 9):
        u = i / 8; e = u * u * (3 - 2 * u)
        hinge.rotation_euler = (r0[0], r0[1] + math.radians(droop_deg) * e, r0[2]); hinge.keyframe_insert("rotation_euler", frame=F(t0 + (t1 - t0) * u))
    rot(mat, t0, t1, to=to)


def rail_at(name, start, yaw_deg, length, z, n_hooks, parent=None):
    """the hanging rail, running from `start` along the floor direction yaw_deg (0 = +X), so a row of bunches can
    recede into the frame instead of crossing it. Returns (root, [(hook point, swing empty)]): each swing empty sits at
    a hook with the rail's yaw, and anything parented to it swings ALONG the rail when its Y rotation is keyed."""
    sx, sy = start
    root, pts = rail(name, sx, sx + length, sy, z, n_hooks, parent=parent)
    pivot = K.empty(f"{name} pivot", (sx, sy, 0))
    root.parent = pivot; root.matrix_parent_inverse = pivot.matrix_basis.inverted()
    root.location = ((root.location.x), root.location.y, root.location.z)
    pivot.rotation_euler = (0, 0, math.radians(yaw_deg)); bpy.context.view_layer.update()
    R = Matrix.Rotation(math.radians(yaw_deg), 3, 'Z'); out = []
    for k, p in enumerate(pts):
        w = Vector((sx, sy, 0)) + R @ (p - Vector((sx, sy, 0)))
        sw = K.empty(f"{name} swing {k}", tuple(w)); sw.rotation_euler = (0, 0, math.radians(yaw_deg))
        out.append((w, sw))
    return pivot, out


def hang_bunch(name, swing, m, seed=0, L=0.14, n=6):
    """a bunch hung from a swing empty by its stem: fingers down, curving out toward the front, fanned along the rail"""
    root, fingers = bunch(name, tuple(swing.location), m, n=n, seed=seed, L=L, spread=0.8)
    root.parent = swing; root.matrix_parent_inverse = Matrix.Identity(4)
    root.location = (0, 0, -0.02); root.rotation_euler = (0, math.radians(90), math.radians(-90))
    return root, fingers


def swing(sw, t0, amp_deg=18, period=0.9, tau=1.4, nf=None, across=False):
    """a hung thing pushed at t0: a damped swing along the rail (or ACROSS it: a rail seen down its length swings
    toward and away from the lens along it, which reads as standing still), keyed every frame from t0 to nf"""
    base = tuple(sw.rotation_euler)
    sw.keyframe_insert("rotation_euler", frame=1)
    for f in range(max(1, F(t0)), (nf or F(t0 + 4)) + 1):
        u = (f - 1) / FPS - t0
        a = math.radians(amp_deg) * math.sin(2 * math.pi * u / period) * math.exp(-u / tau) if u >= 0 else 0.0
        sw.rotation_euler = (base[0] + a, base[1], base[2]) if across else (base[0], a, base[2]); sw.keyframe_insert("rotation_euler", frame=f)


def produce_box(name, loc, yaw=0.0, word="ECUADOR", parent=None):
    """a banana shipping box: corrugated brown, a printed band and the country it came from"""
    root = K.empty(name, loc, parent=parent); x, y, z = loc
    card = K.mat("carton", "#B8925E", rough=0.9); band = K.mat("carton band", "#2F5E9E", rough=0.7); ink = K.mat("carton ink", "#FFFFFF", rough=0.7)
    K.box(f"{name} body", (x, y, z + 0.09), (0.36, 0.26, 0.18), card, bev=0.006, parent=root)
    K.box(f"{name} band", (x, y - 0.131, z + 0.1), (0.3, 0.004, 0.07), band, bev=0.001, parent=root)
    K.text(f"{name} word", word, (x, y - 0.1335, z + 0.1), 0.045, (math.radians(90), 0, 0), ink, extrude=0.0005, parent=root)
    K.text(f"{name} label", "BANANAS", (x, y - 0.1335, z + 0.155), 0.03, (math.radians(90), 0, 0), K.mat("carton ink dark", "#3B2A1A", rough=0.8), extrude=0.0005, parent=root)
    root.rotation_euler = (0, 0, yaw)
    return root
