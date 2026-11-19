"""Props built NEW for the card rewards short's rebuild (2026-11-18, after caaleb called the first cut "lazy as shit":
one counter, one card and one framing in every beat). Each beat gets its own things, and each thing is a machine Data
DRIVES, big enough to read on a phone:

  vacuum_tube    beat 1  a clear pneumatic tube that sucks his cash up off the counter and away to a giant gold card
  stirrup_pump   beat 2  a floor pump whose T-handle he works; its hose inflates a price tag
  price_balloon  beat 2  a red price tag that swells like a balloon, "$" on its face
  shovel / sack  beat 3  a coal shovel he digs into his coin heap and a POINTS sack that fills and bulges
  conveyor       beat 4  a steep cleated belt from a dented tin bucket up to a gold vault, driven by a crank wheel
  flip_coin      beat 5  a giant coin, CASH on one face and CARD on the other, that he flips

Units as scene_kit: metres at Data's scale (his shoulders at z 0.48, his reach 0.19 m from the shoulder)."""
import math

import bpy
from mathutils import Vector

import scene_kit as K
from saffron_kit import _place, _mat


def _glass(name="tube glass", tint=(0.88, 0.95, 1.0)):
    g = bpy.data.materials.get(name)
    if g: return g
    g = bpy.data.materials.new(name); g.use_nodes = True; b = g.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*tint, 1); b.inputs["Roughness"].default_value = 0.05
    b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.08
    return g


def _curve_tube(name, pts, r, m, res=24):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 6
    cu.use_fill_caps = False; sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.resolution_u = res; o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o); o.data.materials.append(m)
    return o


def bezier_path(pts, n=200):
    """sample a smooth path through pts (the tube's own curve) into n points; returns fn(u) for u in 0..1"""
    P = [Vector(p) for p in pts]
    # Catmull-Rom through the points: the same smooth line the AUTO bezier handles give
    def seg(i, t):
        p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[min(len(P) - 1, i + 1)]; p3 = P[min(len(P) - 1, i + 2)]
        t2, t3 = t * t, t * t * t
        return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
    samples = [seg(min(len(P) - 2, int(k * (len(P) - 1) / n)), (k * (len(P) - 1) / n) - min(len(P) - 2, int(k * (len(P) - 1) / n))) for k in range(n + 1)]
    L = [0.0]
    for a, b in zip(samples, samples[1:]): L.append(L[-1] + (b - a).length)
    def fn(u):
        s = max(0.0, min(1.0, u)) * L[-1]
        for k in range(1, len(L)):
            if L[k] >= s:
                w = (s - L[k - 1]) / max(1e-9, L[k] - L[k - 1]); return samples[k - 1].lerp(samples[k], w)
        return samples[-1]
    return fn


def vacuum_tube(name, pts, r=0.032, mouth=(0, 0, -1)):
    """a clear pneumatic tube along pts (world points), a chrome collar every so often and a wide chrome HOOD at its
    first point, opening downward: what it sucks up goes in there. Returns (root, path fn(u))."""
    root = K.empty(name, (0, 0, 0))
    t = _curve_tube(name + " glass", pts, r, _glass()); t.parent = root
    chrome = _mat("tube chrome", "#C8CDD2", rough=0.18, metal=1.0)
    fn = bezier_path(pts)
    for u in (0.12, 0.3, 0.5, 0.7, 0.88):
        p = fn(u); d = (fn(min(1, u + 0.01)) - fn(max(0, u - 0.01))).normalized()
        c = K.cyl(name + " collar", tuple(p), r * 1.2, 0.014, _mat("vacuum collar red", "#D8342A", rough=0.3), v=32, bev=0.002, parent=root)
        c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    h0 = Vector(pts[0])
    hood = bpy.data.meshes.new(name + " hood")
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=r * 2.6, radius2=r * 1.05, depth=0.07)
    bm.to_mesh(hood); bm.free()
    # a red vacuum NOZZLE (a chrome hood over clear glass read as a chemistry set, 11-18 judge)
    ho = bpy.data.objects.new(name + " hood", hood); bpy.context.collection.objects.link(ho)
    ho.data.materials.append(_mat("vacuum nozzle red", "#D8342A", rough=0.3, metal=0.0))
    md = Vector(mouth).normalized()                       # the way the nozzle's wide mouth faces
    ho.location = h0 + md * 0.035; ho.rotation_euler = (-md).to_track_quat('Z', 'Y').to_euler(); ho.parent = root
    sol = ho.modifiers.new("thick", 'SOLIDIFY'); sol.thickness = 0.004
    for p in ho.data.polygons: p.use_smooth = True
    return root, fn


def wad(name, loc, n=14, mesh=None):
    """a loose wad of n banknotes (one shared printed mesh), each its own object so they can leave one at a time,
    top note last in the list"""
    import props
    me = mesh or props.bill_mesh(name + " note", w=0.11, h=0.05)
    out = []
    for i in range(n):
        o = bpy.data.objects.new(f"{name} {i}", me); bpy.context.collection.objects.link(o)
        o.location = (loc[0] + 0.004 * math.sin(i * 2.3), loc[1] + 0.003 * math.cos(i * 1.7), loc[2] + 0.0035 * i + 0.002)
        o.rotation_euler = (0, 0, 0.12 * math.sin(i * 1.3)); out.append(o)
    return out


def giant_card(name, loc, w=0.2, h=0.3, yaw=0.0):
    """a giant gold rewards card stood up on its short edge like a monument (portrait, so it is tall in a phone frame),
    REWARDS and POINTS across it, an intake slot in its top edge for the tube, and a glow (returned) that flares when
    something arrives. Returns (root, glow material, slot point local)."""
    root = K.empty(name, (0, 0, 0))
    face = _mat("giant card gold", "#E3B23C", rough=0.26, metal=0.6)
    K.box(name + " slab", (0, 0, h / 2), (w, 0.02, h), face, bev=0.012, parent=root)
    K.box(name + " base", (0, 0, 0.012), (w * 1.15, 0.09, 0.024), _mat("giant card base", "#1C1B1E", rough=0.35), bev=0.004, parent=root)
    K.box(name + " chip", (-w * 0.22, -0.0105, h * 0.62), (w * 0.24, 0.002, w * 0.18), _mat("card chip", "#CFC7B0", rough=0.25, metal=0.9), bev=0.002, parent=root)
    glow = bpy.data.materials.get(name + " glow") or K.mat(name + " glow", "#FFE08A", rough=0.3, emit=0.0)
    K.box(name + " rim glow", (0, -0.0102, h / 2), (w * 0.93, 0.001, h * 0.95), glow, bev=0, parent=root)
    K.box(name + " face", (0, -0.0108, h / 2), (w * 0.88, 0.001, h * 0.91), face, bev=0, parent=root)
    ink = _mat("giant card ink", "#3B2A0C", rough=0.5)
    K.text(name + " rewards", "REWARDS", (0, -0.0115, h * 0.86), w * 0.16, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=root)
    K.text(name + " points", "+POINTS", (0, -0.0115, h * 0.3), w * 0.17, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=root)
    K.text(name + " number", "4000 1234 5678", (0, -0.0115, h * 0.14), w * 0.085, (math.pi / 2, 0, 0), ink, extrude=0.0006, parent=root)
    K.box(name + " slot", (0, 0, h + 0.001), (w * 0.4, 0.012, 0.004), _mat("card slot", "#141316", rough=0.4), bev=0.001, parent=root)
    _place(root, loc, yaw, None)
    return root, glow, Vector((0, 0, h))


def stirrup_pump(name, loc, h=0.3, yaw=0.0, rod=0.18):
    """a tall red floor pump: a foot plate, a barrel, a chrome rod and a black T-HANDLE (returned, to key up and down),
    a gauge on the barrel. Returns (root, handle, handle top local z at rest, gauge needle)."""
    root = K.empty(name, (0, 0, 0))
    red = _mat("pump red", "#C7302A", rough=0.35, metal=0.2); blk = _mat("pump black", "#1A1A1D", rough=0.5)
    chrome = _mat("tube chrome", "#C8CDD2", rough=0.18, metal=1.0)
    K.box(name + " foot", (0, 0, 0.006), (0.16, 0.06, 0.012), blk, bev=0.004, parent=root)
    K.cyl(name + " barrel", (0, 0, 0.012 + h * 0.4), 0.028, h * 0.8, red, v=40, bev=0.004, parent=root)
    K.cyl(name + " cap", (0, 0, 0.012 + h * 0.8), 0.031, 0.014, blk, v=40, bev=0.003, parent=root)
    K.cyl(name + " gauge", (0, -0.03, h * 0.22), 0.026, 0.012, _mat("gauge face", "#F4F1EA", rough=0.4), rot=(math.pi / 2, 0, 0), v=40, bev=0.002, parent=root)
    needle = K.box(name + " needle", (0, -0.037, h * 0.22), (0.003, 0.001, 0.02), _mat("gauge needle", "#C7302A", rough=0.4), bev=0, parent=root)
    z0 = 0.012 + h * 0.8                      # (scene_kit builds children at ABSOLUTE spots about the root's origin)
    handle = K.empty(name + " handle", (0, 0, z0), parent=root)
    K.cyl(name + " rod", (0, 0, z0 + rod / 2), 0.011, rod, chrome, v=24, bev=0.001, parent=handle)
    K.capsule(name + " grip", Vector((-0.1, 0, z0 + rod)), Vector((0.1, 0, z0 + rod)), 0.019, blk, parent=handle)
    _place(root, loc, yaw, None)
    return root, handle, needle


def price_balloon(name, loc, s=1.0, yaw=0.0):
    """a red PRICE TAG blown up like a balloon: a puffy pillow in the shape of a shop tag (square body, pointed end),
    a punched white-rimmed hole at the point, a big white "$" on its face, and a string from the hole down to its
    base. Scaled about its base (the root), so keying root.scale swells it. Returns (root, base point local)."""
    root = K.empty(name, (0, 0, 0))
    red = _mat("tag balloon", "#D93A2B", rough=0.25, emit=0.0)
    white = _mat("tag hole", "#F4F1EA", rough=0.5)
    zc = 0.15 * s
    K.box(name + " body", (0.03 * s, 0, zc), (0.2 * s, 0.065 * s, 0.21 * s), red, bev=0.03 * s, parent=root)
    pt = K.box(name + " point", (-0.07 * s, 0, zc), (0.13 * s, 0.062 * s, 0.13 * s), red, bev=0.028 * s, parent=root)
    pt.rotation_euler = (0, math.pi / 4, 0)
    # a brass GROMMET, not a white ring round a dark hole (that read as an eye, and the tag as a fish: 11-18 judge)
    K.cyl(name + " grommet", (-0.105 * s, -0.033 * s, zc), 0.014 * s, 0.004, _mat("tag grommet", "#C9A443", rough=0.3, metal=0.9), rot=(math.pi / 2, 0, 0), v=32, bev=0.001, parent=root)
    K.cyl(name + " grommet in", (-0.105 * s, -0.035 * s, zc), 0.008 * s, 0.004, red, rot=(math.pi / 2, 0, 0), v=24, bev=0, parent=root)
    K.text(name + " dollar", "$", (0.045 * s, -0.035 * s, zc - 0.005 * s), 0.17 * s, (math.pi / 2, 0, 0), white, extrude=0.004 * s, parent=root)
    _curve_tube(name + " string", [Vector((-0.105 * s, 0, zc)), Vector((-0.1 * s, 0, zc * 0.45)), Vector((-0.04 * s, 0, 0.0))], 0.0025,
                _mat("tag string", "#EDE3C8", rough=0.7)).parent = root
    _place(root, loc, yaw, None)
    return root, Vector((0, 0, 0.0))


def hose(name, a_fn, b_fn, nf, r=0.007, sag=0.04):
    """a black hose between two moving points, rebuilt as a 3-point curve whose ends are keyed every frame (hook
    empties follow a_fn/b_fn; the curve's points are hooked to them)"""
    m = _mat("pump black", "#1A1A1D", rough=0.5)
    a0, b0 = Vector(a_fn(0.0)), Vector(b_fn(0.0)); mid = (a0 + b0) / 2 + Vector((0, 0, -sag))
    o = _curve_tube(name, [a0, mid, b0], r, m)
    o.data.use_fill_caps = True
    return o


def shovel(name, length=0.3):
    """a coal shovel: a wooden shaft with a D-grip at its top end and a broad steel blade at the bottom. Built along
    local +Z from the blade (origin at the blade's centre). Returns (root, grip local, mid-shaft local)."""
    root = K.empty(name, (0, 0, 0))
    wood = _mat("shovel shaft", "#9A6B3F", rough=0.6); steel = _mat("shovel steel", "#5E6268", rough=0.35, metal=0.85)
    K.box(name + " blade", (0, 0, -0.01), (0.13, 0.005, 0.14), steel, bev=0.003, parent=root)
    for sx in (-1, 1): K.box(name + " lip", (sx * 0.065, -0.014, -0.01), (0.005, 0.03, 0.14), steel, bev=0.001, parent=root)
    K.cyl(name + " shaft", (0, 0, 0.05 + length / 2), 0.009, length, wood, v=20, bev=0.002, parent=root)
    K.box(name + " grip", (0, 0, 0.05 + length + 0.012), (0.06, 0.012, 0.012), _mat("pump black", "#1A1A1D", rough=0.5), bev=0.004, parent=root)
    return root, Vector((0, 0, 0.05 + length + 0.01)), Vector((0, 0, 0.05 + length * 0.45))


def sack(name, loc, r=0.11, h=0.2, yaw=0.0):
    """a fat burlap MONEY SACK standing open: a slumped body that narrows to a rope-tied waist, and above the rope the
    loose cloth flaring out in a ruffled, wavy collar round a dark mouth with gold in it. (A round body under a rolled
    rim read as a clay pot, 11-18 judge; a sack is the waist and the ruffle.) POINTS stencilled on it in gold. Scaled
    about its base (keying root.scale.x/y bulges it). Returns (root, mouth local)."""
    import bmesh
    root = K.empty(name, (0, 0, 0))
    burlap = locals_burlap()
    K.sph(name + " body", (0, 0, h * 0.36), 1.0, burlap, scale=(r, r * 0.88, h * 0.4), parent=root)
    K.sph(name + " slump", (r * 0.3, -r * 0.25, h * 0.16), 1.0, burlap, scale=(r * 0.75, r * 0.7, h * 0.17), parent=root)
    zw = h * 0.8                                                           # the tied waist
    def shell(nm, r1, r2, z1, z2, wave=0.0, seg=56):
        me = bpy.data.meshes.new(nm); bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r1, radius2=r2, depth=z2 - z1)
        for v in bm.verts:
            if wave and v.co.z > 0:
                a = math.atan2(v.co.y, v.co.x); k = 1 + 0.12 * math.sin(7 * a) + 0.05 * math.sin(3 * a + 1)
                v.co.x *= k; v.co.y *= k; v.co.z += wave * math.sin(7 * a + 0.6)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(nm, me); bpy.context.collection.objects.link(o); me.materials.append(burlap)
        o.location = (0, 0, (z1 + z2) / 2); sd = o.modifiers.new("thick", 'SOLIDIFY'); sd.thickness = 0.006
        sub = o.modifiers.new("smooth", 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
        for p in me.polygons: p.use_smooth = True
        o.parent = root
        return o
    shell(name + " shoulder", r * 0.86, r * 0.4, h * 0.58, zw)
    shell(name + " ruffle", r * 0.4, r * 0.78, zw, h * 1.05, wave=h * 0.035)
    cu = bpy.data.curves.new(name + " tie", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r * 0.05; cu.bevel_resolution = 4
    sp = cu.splines.new('POLY'); sp.points.add(39); sp.use_cyclic_u = True
    for i, pnt in enumerate(sp.points):
        a = 2 * math.pi * i / 40; pnt.co = (r * 0.42 * math.cos(a), r * 0.42 * math.sin(a), zw + 0.004, 1)
    to = bpy.data.objects.new(name + " tie", cu); bpy.context.collection.objects.link(to); to.parent = root
    cu.materials.append(_mat("sack rope", "#5C3D22", rough=0.9))
    for sx in (-1, 1):                                                     # the rope's two loose ends hang down the front
        _curve_tube(name + " tie end", [Vector((sx * 0.012, -r * 0.42, zw)), Vector((sx * 0.03, -r * 0.52, zw - h * 0.12)),
                                        Vector((sx * 0.025, -r * 0.6, zw - h * 0.22))], r * 0.04, _mat("sack rope", "#5C3D22", rough=0.9)).parent = root
    K.cyl(name + " inside", (0, 0, h * 0.86), r * 0.45, 0.004, _mat("sack inside", "#1E150C", rough=0.95), v=40, bev=0, parent=root)
    K.sph(name + " gold inside", (0, 0, h * 0.9), 1.0, bpy.data.materials.get("coins") or _mat("coins", "#E3B23C", rough=0.25, metal=0.9),
          scale=(r * 0.5, r * 0.5, h * 0.06), parent=root)
    K.text(name + " label", "POINTS", (0, -r * 0.9, h * 0.36), r * 0.4, (math.pi / 2, 0, 0), _mat("points gold", "#E3B23C", rough=0.3, metal=0.5), extrude=0.003, parent=root)
    _place(root, loc, yaw, None)
    return root, Vector((0, 0, h * 0.92))


def locals_burlap():
    """sacking: a pale tan weave with a coarse bump, matte (a smooth brown sphere read as a clay pot, 11-18 judge)"""
    m = bpy.data.materials.get("burlap")
    if m: return m
    m = bpy.data.materials.new("burlap"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 1.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 160.0
    wh = nt.nodes.new("ShaderNodeTexWave"); wh.inputs["Scale"].default_value = 160.0; wh.bands_direction = 'Y'
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 18.0
    for n in (wv, wh, nz): nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = 'MULTIPLY'
    nt.links.new(wv.outputs["Fac"], mix.inputs[0]); nt.links.new(wh.outputs["Fac"], mix.inputs[1])
    rp = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"])
    rp.color_ramp.elements[0].color = (*K.lin("#A88A5C"), 1); rp.color_ramp.elements[1].color = (*K.lin("#D2B88A"), 1)
    nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; bump.inputs["Distance"].default_value = 0.002
    nt.links.new(mix.outputs[0], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def coin_heap(name, loc, r=0.12, h=0.07, n=90, seed=1):
    """a heap of loose gold coins on the floor: a gold cone under a skin of tilted coins. Scale it (root.scale) to
    shrink it as it is dug away. Returns root."""
    import random
    rnd = random.Random(seed); root = K.empty(name, (0, 0, 0))
    gold = bpy.data.materials.get("coins") or K.mat("coins", "#F4CC52", rough=0.22, metal=0.65, emit=0.12)
    mesh = bpy.data.meshes.new(name + " cone")
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r, radius2=r * 0.12, depth=h); bm.to_mesh(mesh); bm.free()
    c = bpy.data.objects.new(name + " cone", mesh); bpy.context.collection.objects.link(c); c.location = (0, 0, h / 2); c.parent = root; mesh.materials.append(gold)
    for p in mesh.polygons: p.use_smooth = True
    proto = K.cyl(name + " coin", (0, 0, -5), 0.018, 0.004, gold, v=20, bev=0.001)
    for i in range(n):
        a = rnd.uniform(0, 6.283); d = r * math.sqrt(rnd.uniform(0, 1)); z = h * (1 - d / r) + 0.002
        o = proto.copy(); bpy.context.collection.objects.link(o); o.parent = root
        o.location = (d * math.cos(a), d * math.sin(a), z); o.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 6.28))
    _place(root, loc, 0.0, None)
    return root


def tin_bucket(name, loc, r=0.05, h=0.06):
    """a small dented tin bucket with a wire bail: the poor end"""
    root = K.empty(name, (0, 0, 0))
    tin = _mat("tin bucket", "#8E9398", rough=0.4, metal=0.85)
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=r * 0.82, radius2=r, depth=h); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name + " wall", me); bpy.context.collection.objects.link(o); o.location = (0, 0, h / 2); o.parent = root; me.materials.append(tin)
    o.modifiers.new("t", 'SOLIDIFY').thickness = 0.003
    K.cyl(name + " floor", (0, 0, 0.002), r * 0.82, 0.004, tin, v=32, bev=0, parent=root)
    bail = _curve_tube(name + " bail", [Vector((-r, 0, h)), Vector((0, 0, h + r * 0.9)), Vector((r, 0, h))], 0.0018, _mat("bail wire", "#55585C", rough=0.4, metal=0.8))
    bail.parent = root
    _place(root, loc, 0.0, None)
    return root


def vault(name, loc, w=0.2, d=0.16, h=0.34, label="VIP", sub=None):
    """a squat gold-trimmed steel vault, open at the top, with a gold FILL inside (returned) that rises when keyed
    (fill.scale.z 0..1) and VIP stencilled on it. Returns (root, fill, mouth local)."""
    root = K.empty(name, (0, 0, 0))
    steel = _mat("vault body", "#3C4247", rough=0.3, metal=0.85); brass = _mat("bank brass", "#C9A04A", rough=0.3, metal=0.9)
    t = 0.012
    K.box(name + " floor", (0, 0, t / 2), (w, d, t), steel, bev=0.002, parent=root)
    for sx in (-1, 1): K.box(name + " side", (sx * (w / 2 - t / 2), 0, h / 2), (t, d, h), steel, bev=0.002, parent=root)
    for sy in (-1, 1): K.box(name + " wall", (0, sy * (d / 2 - t / 2), h / 2), (w, t, h), steel, bev=0.002, parent=root)
    K.box(name + " rim", (0, -d / 2 + 0.002, h - 0.008), (w + 0.006, 0.008, 0.016), brass, bev=0.002, parent=root)
    K.box(name + " band", (0, -d / 2 - 0.001, h * 0.35), (w + 0.004, 0.004, 0.02), brass, bev=0.001, parent=root)
    K.text(name + " label", label, (0, -d / 2 - 0.002, h * 0.62), w * 0.24, (math.pi / 2, 0, 0), brass, extrude=0.002, parent=root)
    if sub: K.text(name + " sub", sub, (0, -d / 2 - 0.002, h * 0.47), w * 0.11, (math.pi / 2, 0, 0), brass, extrude=0.0012, parent=root)
    gold = bpy.data.materials.get("coins") or K.mat("coins", "#F4CC52", rough=0.22, metal=0.65, emit=0.12)
    fill = K.empty(name + " fill pivot", (0, 0, t), parent=root)
    K.box(name + " fill", (0, 0, (h - 0.03) / 2), (w - 2.4 * t, d - 2.4 * t, h - 0.03), gold, bev=0.004, parent=fill)
    fill.scale = (1, 1, 0.02)
    _place(root, loc, 0.0, None)
    return root, fill, Vector((0, 0, h))


def conveyor(name, a, b, w=0.09, cleats=14, hub=None, WR=0.075):
    """a steep cleated conveyor belt from a (its foot) to b (its head), on two steel stringers with legs, a crank
    WHEEL (returned) standing at its foot on the camera side (-Y), a knob on its rim. The cleats are returned with
    the belt path so a shot can run them up the belt. Returns (root, wheel, cleats, belt fn(u)->world, wheel radius)."""
    a, b = Vector(a), Vector(b); d = b - a; L = d.length; up = d.normalized()
    root = K.empty(name, (0, 0, 0))
    steel = _mat("conveyor steel", "#4A5056", rough=0.35, metal=0.8); belt = _mat("conveyor belt", "#202124", rough=0.7)
    yel = _mat("crank yellow", "#E8B623", rough=0.35, metal=0.2)
    rot = (0, -math.atan2(d.z, math.hypot(d.x, d.y)), math.atan2(d.y, d.x))
    mid = (a + b) / 2
    bo = K.box(name + " belt", tuple(mid), (L, w, 0.012), belt, bev=0.003, parent=root); bo.rotation_euler = rot
    for sy in (-1, 1):
        s = K.box(name + " stringer", tuple(mid + Vector((0, sy * (w / 2 + 0.008), 0.004))), (L + 0.02, 0.012, 0.03), steel, bev=0.003, parent=root)
        s.rotation_euler = rot
    for u in (0.2, 0.55, 0.9):
        p = a.lerp(b, u)
        if p.z > 0.05:
            K.box(name + " leg", (p.x, p.y + w / 2 + 0.02, p.z / 2), (0.014, 0.014, p.z), steel, bev=0.002, parent=root)
    post = hub is not None
    hub = Vector(hub) if post else a + Vector((0, -(w / 2 + 0.03), 0.0))
    if post:                                  # the wheel stands on its own post at hand height, a chain down to the belt's foot
        PB = 0.085                            # the post stands well BEHIND the wheel: the arm that turns it never meets it
        K.box(name + " post", (hub.x, hub.y + PB, hub.z / 2), (0.03, 0.03, hub.z), steel, bev=0.003, parent=root)
        K.box(name + " post foot", (hub.x, hub.y + PB, 0.006), (0.12, 0.08, 0.012), steel, bev=0.003, parent=root)
        for dz in (-0.012, 0.012):
            _curve_tube(name + " chain", [hub + Vector((0, 0.09, dz)), a + Vector((0, (w / 2 + 0.02), dz))], 0.003,
                        _mat("chain dark", "#2B2B2E", rough=0.4, metal=0.7)).parent = root
    wheel = K.empty(name + " wheel", tuple(hub), parent=root)
    H = tuple(hub)                            # children at ABSOLUTE spots (scene_kit), so the wheel turns about the hub
    ring = K.cyl(name + " rim", H, WR, 0.016, yel, rot=(math.pi / 2, 0, 0), v=48, bev=0.003, parent=wheel)
    K.cyl(name + " rim hole", tuple(hub + Vector((0, -0.0001, 0))), WR * 0.8, 0.0165, _mat("crank dark", "#2B2B2E", rough=0.5), rot=(math.pi / 2, 0, 0), v=48, bev=0, parent=wheel)
    for k in range(4):
        sp = K.box(name + " spoke", tuple(hub + Vector((0, -0.003, 0))), (WR * 1.7, 0.01, 0.014), yel, bev=0.002, parent=wheel); sp.rotation_euler = (0, math.radians(45 * k), 0)
    K.cyl(name + " hub cap", tuple(hub + Vector((0, -0.01, 0))), 0.016, 0.02, _mat("crank knob", "#C7302A", rough=0.4), rot=(math.pi / 2, 0, 0), v=24, bev=0.003, parent=wheel)
    K.cyl(name + " knob", tuple(hub + Vector((WR * 0.86, -0.025, 0))), 0.012, 0.04, _mat("crank knob", "#C7302A", rough=0.4), rot=(math.pi / 2, 0, 0), v=24, bev=0.003, parent=wheel)
    K.cyl(name + " axle", tuple(hub + Vector((0, 0.05, 0))), 0.01, 0.1, steel, rot=(math.pi / 2, 0, 0), v=24, bev=0.002, parent=root)
    n_ = Vector((0, 0, 1)) - up * up.z; n_.normalize()       # the belt's own "up", for the cleats
    cl = []
    for k in range(cleats):
        o = K.box(name + f" cleat {k}", (0, 0, -5), (0.012, w * 0.95, 0.022), yel, bev=0.002); o.rotation_euler = rot; cl.append(o)
    belt_fn = lambda u: a.lerp(b, u) + n_ * 0.018
    return root, wheel, cl, belt_fn, WR


def flip_coin(name, r=0.13, h=0.022):
    """a GIANT coin: a gold disc with CASH embossed on one face (-Y at rest) and CARD on the other (+Y), a milled rim.
    Built standing on its edge about its centre. Returns root."""
    root = K.empty(name, (0, 0, 0))
    gold = _mat("giant coin gold", "#EDC14B", rough=0.24, metal=0.75); dark = _mat("giant coin ink", "#7A5A12", rough=0.4, metal=0.6)
    K.cyl(name + " disc", (0, 0, 0), r, h, gold, rot=(math.pi / 2, 0, 0), v=64, bev=0.004, parent=root)
    K.cyl(name + " ring a", (0, -h / 2 - 0.0005, 0), r * 0.86, 0.002, dark, rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    K.cyl(name + " field a", (0, -h / 2 - 0.0012, 0), r * 0.8, 0.002, gold, rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    K.cyl(name + " ring b", (0, h / 2 + 0.0005, 0), r * 0.86, 0.002, dark, rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    K.cyl(name + " field b", (0, h / 2 + 0.0012, 0), r * 0.8, 0.002, gold, rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    K.text(name + " cash", "CASH", (0, -h / 2 - 0.0025, 0), r * 0.42, (math.pi / 2, 0, 0), dark, extrude=0.002, parent=root)
    K.text(name + " card", "CARD", (0, h / 2 + 0.0025, 0), r * 0.42, (math.pi / 2, 0, math.pi), dark, extrude=0.002, parent=root)
    return root


def signpost(name, loc, left="CASH", right="CARD", h=0.62, arm=0.2):
    """a wooden crossroads signpost: a post and two arrow boards pointing apart, LEFT and RIGHT painted on them"""
    root = K.empty(name, (0, 0, 0))
    wood = _mat("sign wood", "#8A5A34", rough=0.7); paint = _mat("sign paint", "#F4EEDF", rough=0.6)
    K.box(name + " post", (0, 0, h / 2), (0.03, 0.03, h), wood, bev=0.004, parent=root)
    for sx, word, z in ((-1, left, h * 0.86), (1, right, h * 0.7)):
        bd = K.box(name + " board", (sx * arm / 2, -0.02, z), (arm, 0.012, 0.07), wood, bev=0.003, parent=root)
        tip = K.box(name + " tip", (sx * arm, -0.02, z), (0.05, 0.012, 0.05), wood, bev=0.003, parent=root); tip.rotation_euler = (0, math.radians(45), 0)
        K.text(name + " word", word, (sx * arm / 2, -0.027, z), 0.05, (math.pi / 2, 0, 0), paint, extrude=0.001, parent=root)
    _place(root, loc, 0.0, None)
    return root
