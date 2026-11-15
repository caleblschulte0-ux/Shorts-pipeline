"""THE HELIUM KIT (the fourth 3D short, 2026-11-15): party balloons that float on a string and can shrivel, a gas
wellhead with a valve wheel, a hospital MRI scanner with a status light, a steel dewar flask and the white cold
smoke that pours from it, a cast-iron weight, and a helium cylinder. Kept for any gas, party or hospital story.
Units are the store's: metres at Data's scale (he is 0.96 tall, his hands hang at 0.30).

Every piece is MADE OF what it is (docs/CHANNEL_LOOK.md): a balloon is a glossy latex egg with a tied knot and a
string, not a coloured sphere; a scanner is a deep white ring with a bore, a padded table and a light."""
import math, random
import bpy
from mathutils import Vector, Matrix
import scene_kit as K
from clock import FPS

F = lambda t: int(round(t * FPS)) + 1


def _mat(name, hexc, rough=0.5, metal=0.0, emit=0.0, coat=0.0, sss=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = K.mat(name, hexc, rough=rough, metal=metal, emit=emit)
    b = m.node_tree.nodes.get("Principled BSDF")
    for k, v in (("Coat Weight", coat), ("Subsurface Weight", sss)):
        try:
            if v: b.inputs[k].default_value = v
        except KeyError: pass
    return m


def latex(hexc):
    """balloon latex: a glossy coat over a soft, slightly translucent colour"""
    return _mat(f"latex {hexc}", hexc, rough=0.32, coat=0.6, sss=0.15)


def balloon(name, loc, r=0.09, color="#D22B2B", parent=None, string=0.0):
    """a party balloon: a latex egg (narrower at the knot), the tied knot, and optionally a string hanging `string`
    metres down from the knot. Returns the root (an empty at the KNOT: the point a hand or a string holds)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    m = latex(color)
    body = K.sph(f"{name} body", (0, 0, 0), r, m, scale=(1.0, 1.0, 1.0), parent=root, seg=48, ring=24)
    # an egg, not a ball: the bottom third pulls in toward the knot. Its ORIGIN is the knot, so when it shrivels it
    # shrinks onto the knot and hangs from it, never a blob floating off its string
    me = body.data
    zs = [v.co.z for v in me.vertices]; zmin, zmax = min(zs), max(zs)
    for v in me.vertices:
        z = (v.co.z - zmin) / (zmax - zmin) * 2 - 1                  # -1 at the knot end .. 1 at the top
        if z < 0: v.co.x *= 1 + 0.32 * z; v.co.y *= 1 + 0.32 * z
        v.co.z = (v.co.z - zmin) * 1.18
    me.update()
    K.cyl(f"{name} knot", (0, 0, 0.004), r * 0.09, r * 0.14, m, v=16, bev=0.002, parent=root)
    K.sph(f"{name} knot lip", (0, 0, -0.002), r * 0.1, m, scale=(1, 1, 0.5), parent=root, seg=16, ring=8)
    if string > 0:
        s = K.cyl(f"{name} string", (0, 0, -string / 2), 0.0012, string, _mat("balloon string", "#F2F0EA", rough=0.8), v=6, bev=0, parent=root)
        root["string"] = s.name
    root["body"] = body.name
    root.location = loc
    return root


def string_between(name, a_fn, b_fn, nf, r=0.0012, t0=0.0):
    """a string drawn every frame from point a_fn(t) to b_fn(t) (a knot to a hand, a knot to a weight): a thin
    cylinder keyed in place, length and direction, so it is always taut between the two."""
    s = K.cyl(name, (0, 0, 0), r, 1.0, _mat("balloon string", "#F2F0EA", rough=0.8), v=6, bev=0)
    me = s.data
    for v in me.vertices: v.co.z += 0.5          # its base at the origin, its top at z = 1
    me.update()
    for f in range(F(t0), nf + 1):
        t = (f - 1) / FPS; a, b = Vector(a_fn(t)), Vector(b_fn(t)); d = b - a
        s.location = a; s.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); s.scale = (1, 1, max(1e-4, d.length))
        for p in ("location", "rotation_euler", "scale"): s.keyframe_insert(p, frame=f)
    return s


def shrivel(root, t0, t1, to=0.45, seed=0):
    """the balloon goes limp: it shrinks, wrinkles (a cloud displace on its skin grows) and its body sags over to
    one side of the knot, from t0 to t1. A limp balloon, not a smaller round one."""
    body = bpy.data.objects[root["body"]]
    rnd = random.Random(seed)
    tex = bpy.data.textures.new(f"{root.name} wrinkle", 'CLOUDS'); tex.noise_scale = 0.18
    md = body.modifiers.new("wrinkle", 'DISPLACE'); md.texture = tex; md.texture_coords = 'LOCAL'
    side = rnd.choice((-1, 1)); lean = rnd.uniform(2.6, 2.9)      # it ends hanging DOWN from its knot, as a limp one does
    for t, u in ((0.0, 0.0), (t0, 0.0)) + tuple((t0 + (t1 - t0) * k / 6, k / 6) for k in range(1, 7)):
        e = u * u * (3 - 2 * u)
        s = 1 - (1 - to) * e
        body.scale = (s * (1 + 0.15 * e), s * (1 - 0.1 * e), s * (1 - 0.35 * e)); body.keyframe_insert("scale", frame=F(t))
        root.rotation_euler = (0, side * lean * e, 0); root.keyframe_insert("rotation_euler", frame=F(t))
        md.strength = 0.09 * e; md.keyframe_insert("strength", frame=F(t))
    return body


def cylinder_tank(name, loc, r=0.05, h=0.42, color="#7FA8C9", parent=None):
    """a gas cylinder: a painted steel bottle with a domed shoulder, a brass valve and a round gauge"""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    m = _mat(f"tank paint {color}", color, rough=0.35, metal=0.4, coat=0.4)
    K.cyl(f"{name} body", (0, 0, h / 2), r, h, m, v=40, bev=0.01, parent=root)
    K.sph(f"{name} shoulder", (0, 0, h), r, m, scale=(1, 1, 0.55), parent=root, seg=40, ring=16)
    brass = _mat("valve brass", "#B88A3A", rough=0.3, metal=1.0)
    K.cyl(f"{name} valve", (0, 0, h + r * 0.55 + 0.02), r * 0.28, 0.04, brass, v=20, bev=0.003, parent=root)
    K.cyl(f"{name} gauge", (0, -r * 0.45, h + r * 0.55 + 0.05), r * 0.35, 0.012, _mat("gauge face", "#F4F2EC", rough=0.4), rot=(math.pi / 2, 0, 0), v=24, bev=0.002, parent=root)
    root.location = loc
    return root


def wellhead(name, loc, h=0.3, r=0.04, arm=0.26, rise=0.2, parent=None):
    """a gas wellhead at chest height: a fat red pipe out of a concrete pad up to a gate valve whose big handwheel
    lies FLAT on top (two hands turn it, the camera reads it from the front and a little above), and a branch pipe
    out to the image-left (-X) that turns up into an open steel nozzle, where a balloon is tied. Returns (root,
    wheel, nozzle point local, wheel centre local, wheel radius)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    red = _mat("wellhead red", "#B8322A", rough=0.4, metal=0.3, coat=0.3)
    steel = _mat("wellhead steel", "#8C9196", rough=0.3, metal=1.0)
    conc = _mat("well pad", "#9A968E", rough=0.9)
    K.box(f"{name} pad", (0, -0.02, 0.02), (0.2, 0.18, 0.04), conc, bev=0.01, parent=root)
    K.cyl(f"{name} pipe", (0, 0, h / 2), r, h, red, v=32, bev=0.004, parent=root)
    for z in (0.1, h - 0.02):
        K.cyl(f"{name} flange", (0, 0, z), r * 1.7, 0.026, red, v=32, bev=0.004, parent=root)
        for k in range(8):
            a = k * math.tau / 8
            K.cyl(f"{name} bolt", (math.cos(a) * r * 1.45, math.sin(a) * r * 1.45, z + 0.016), 0.005, 0.012, steel, v=8, bev=0.001, parent=root)
    K.box(f"{name} valve body", (0, 0, h + 0.05), (r * 2.6, r * 2.2, 0.1), red, bev=0.012, parent=root)
    K.cyl(f"{name} bonnet", (0, 0, h + 0.13), r * 0.8, 0.07, red, v=24, bev=0.004, parent=root)
    WZ = h + 0.19; WR = 0.085
    wheel = K.empty(f"{name} wheel", (0, 0, WZ), parent=root)
    bpy.ops.mesh.primitive_torus_add(major_radius=WR, minor_radius=0.009, major_segments=48, minor_segments=12, location=(0, 0, 0))
    tor = bpy.context.active_object; tor.name = f"{name} handwheel"; hw = _mat("handwheel", "#D8C23A", rough=0.4, metal=0.2, coat=0.3)
    tor.data.materials.append(hw); tor.parent = wheel
    for pl in tor.data.polygons: pl.use_smooth = True
    for k in range(3):
        sp = K.cyl(f"{name} spoke", (0, 0, WZ), 0.006, WR * 2, hw, v=8, bev=0.001, parent=wheel)
        sp.rotation_euler = (math.pi / 2, 0, k * math.pi / 3)
    K.cyl(f"{name} hub", (0, 0, WZ), 0.02, 0.026, steel, v=16, bev=0.002, parent=wheel)
    K.cyl(f"{name} branch", (-arm / 2, 0, h + 0.05), r * 0.7, arm, red, rot=(0, math.pi / 2, 0), v=24, bev=0.003, parent=root)
    K.sph(f"{name} elbow", (-arm, 0, h + 0.05), r * 0.72, red, parent=root, seg=24, ring=12)
    K.cyl(f"{name} riser", (-arm, 0, h + 0.05 + rise / 2), r * 0.7, rise, red, v=24, bev=0.003, parent=root)
    K.cyl(f"{name} nozzle", (-arm, 0, h + 0.05 + rise + 0.025), r * 0.45, 0.05, steel, v=24, bev=0.003, parent=root)
    root.location = loc
    return root, wheel, Vector((-arm, 0, h + 0.05 + rise + 0.05)), Vector((0, 0, WZ)), WR


def inflate(root, t0, t1, frm=0.3, seed=0):
    """the reverse of shrivel: a limp, wrinkled skin fills out round and tight from t0 to t1, with a little
    overshoot and wobble as it tightens (latex is springy)"""
    body = bpy.data.objects[root["body"]]
    tex = bpy.data.textures.new(f"{root.name} wrinkle", 'CLOUDS'); tex.noise_scale = 0.18
    md = body.modifiers.new("wrinkle", 'DISPLACE'); md.texture = tex; md.texture_coords = 'LOCAL'
    keys = [(0.0, 0.0), (t0, 0.0)] + [(t0 + (t1 - t0) * k / 8, k / 8) for k in range(1, 9)]
    for t, u in keys:
        e = u * u * (3 - 2 * u); s = frm + (1 - frm) * e
        body.scale = (s * (1 - 0.15 * (1 - e)), s, s * (1 - 0.4 * (1 - e))); body.keyframe_insert("scale", frame=F(t))
        md.strength = 0.06 * (1 - e); md.keyframe_insert("strength", frame=F(t))
    for dt, w in ((0.12, 1.06), (0.26, 0.97), (0.4, 1.0)):
        body.scale = (w, w, w); body.keyframe_insert("scale", frame=F(t1 + dt))
    return body


def scanner(name, loc, R=0.62, depth=0.55, parent=None):
    """a hospital MRI scanner, front on: a deep white ring around a dark bore, a padded table sliding out of it, a
    fill port on top and a big status light on the ring's face. Returns (root, light material, port point local)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    shell = _mat("scanner shell", "#ECEEF0", rough=0.28, coat=0.5)
    bore = _mat("scanner bore", "#C9CED4", rough=0.35)
    bpy.ops.mesh.primitive_torus_add(major_radius=R * 0.72, minor_radius=R * 0.3, major_segments=64, minor_segments=24, location=(0, 0, R + 0.02))
    ring = bpy.context.active_object; ring.name = f"{name} ring"; ring.rotation_euler = (math.pi / 2, 0, 0)
    ring.scale = (1, 1, depth / (R * 0.6)); ring.data.materials.append(shell); ring.parent = root
    for p in ring.data.polygons: p.use_smooth = True
    K.cyl(f"{name} bore liner", (0, 0, R + 0.02), R * 0.43, depth * 1.02, bore, rot=(math.pi / 2, 0, 0), v=48, bev=0.004, parent=root)
    K.box(f"{name} base", (0, 0, 0.12), (R * 1.5, depth * 1.05, 0.24), shell, bev=0.03, parent=root)
    pad = _mat("scanner pad", "#3A6E9E", rough=0.6)
    K.box(f"{name} table", (0, -depth * 0.9, R * 0.62), (R * 0.52, depth * 1.3, 0.05), shell, bev=0.015, parent=root)
    K.box(f"{name} table pad", (0, -depth * 0.9, R * 0.66), (R * 0.46, depth * 1.25, 0.03), pad, bev=0.012, parent=root)
    K.box(f"{name} table leg", (0, -depth * 1.25, R * 0.31), (R * 0.3, 0.12, R * 0.6), shell, bev=0.02, parent=root)
    light = bpy.data.materials.new(f"{name} status"); light.use_nodes = True
    bsdf = light.node_tree.nodes["Principled BSDF"]
    K.cyl(f"{name} status light", (-R * 0.55, -depth * 0.52, R * 1.4), 0.085, 0.025, light, rot=(math.pi / 2, 0, 0), v=32, bev=0.004, parent=root)
    steel = _mat("port steel", "#A9AEB4", rough=0.25, metal=1.0)
    K.cyl(f"{name} port", (-R * 0.25, 0, R * 1.62 + 0.06), 0.05, 0.12, steel, v=24, bev=0.004, parent=root)
    K.cyl(f"{name} port mouth", (-R * 0.25, 0, R * 1.62 + 0.125), 0.062, 0.012, steel, v=24, bev=0.002, parent=root)
    root.location = loc
    return root, bsdf, Vector((-R * 0.25, 0, R * 1.62 + 0.13))


def status(bsdf, t, hexc, emit=6.0):
    """key the scanner's status light to a colour at t"""
    c = (*K.lin(hexc), 1)
    for k, v in (("Base Color", c), ("Emission Color", c)):
        try: bsdf.inputs[k].default_value = v; bsdf.inputs[k].keyframe_insert("default_value", frame=F(t))
        except KeyError: pass
    try: bsdf.inputs["Emission Strength"].default_value = emit; bsdf.inputs["Emission Strength"].keyframe_insert("default_value", frame=F(t))
    except KeyError: pass


def frost(obj_names, t0, t1, white="#F4F8FC"):
    """frost creeps over these objects from t0 to t1: their base colour eases toward frost white and roughens"""
    for nm in obj_names:
        o = bpy.data.objects.get(nm)
        if not o or not o.data.materials: continue
        m = o.data.materials[0].copy(); o.data.materials[0] = m
        b = m.node_tree.nodes["Principled BSDF"]
        c0 = tuple(b.inputs["Base Color"].default_value); c1 = (*K.lin(white), 1)
        for t, u in ((0, 0), (t0, 0), (t1, 1)):
            b.inputs["Base Color"].default_value = tuple(a + (c - a) * u for a, c in zip(c0, c1)); b.inputs["Base Color"].keyframe_insert("default_value", frame=F(t))
            b.inputs["Roughness"].default_value = 0.3 + 0.5 * u; b.inputs["Roughness"].keyframe_insert("default_value", frame=F(t))


def dewar(name, loc, r=0.055, h=0.2, parent=None):
    """a steel dewar flask for liquid helium: a brushed cylinder, a rounded shoulder, a short neck and two handles.
    Returns (root, mouth point local)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    steel = _mat("dewar steel", "#B9BEC4", rough=0.22, metal=1.0)
    K.cyl(f"{name} body", (0, 0, h / 2), r, h, steel, v=40, bev=0.01, parent=root)
    K.sph(f"{name} shoulder", (0, 0, h), r, steel, scale=(1, 1, 0.45), parent=root, seg=40, ring=16)
    K.cyl(f"{name} neck", (0, 0, h + r * 0.45 + 0.02), r * 0.38, 0.05, steel, v=24, bev=0.003, parent=root)
    for sg in (-1, 1):
        K.box(f"{name} handle", (sg * (r + 0.012), 0, h * 0.7), (0.012, 0.03, 0.08), _mat("dewar handle", "#2A2D31", rough=0.5), bev=0.004, parent=root)
    K.box(f"{name} label", (0, -r * 0.99, h * 0.5), (r * 1.1, 0.002, h * 0.35), _mat("dewar label", "#2F6FB0", rough=0.5), bev=0.001, parent=root)
    root.location = loc
    return root, Vector((0, 0, h + r * 0.45 + 0.05))


def cold_smoke(name, mouth_fn, aim_fn, t0, t1, nf, n=60, seed=0):
    """the white cold smoke of boiling liquid helium: soft puffs leave the mouth from t0 to t1, roll along the pour
    direction and sink (cold gas falls), swelling and thinning as they go"""
    rnd = random.Random(seed)
    m = bpy.data.materials.new(f"{name} smoke"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.96, 0.98, 1.0, 1); b.inputs["Roughness"].default_value = 1.0
    try:
        b.inputs["Alpha"].default_value = 0.55
        b.inputs["Emission Color"].default_value = (0.9, 0.95, 1.0, 1); b.inputs["Emission Strength"].default_value = 0.35
    except KeyError: pass
    m.blend_method = 'BLEND' if hasattr(m, "blend_method") else None
    puffs = []
    for i in range(n):
        ts = t0 + (t1 - t0) * i / n + rnd.uniform(-0.02, 0.02)
        o = K.sph(f"{name} puff {i}", (0, 0, -5), 1.0, m, seg=16, ring=8); puffs.append(o)
        life = rnd.uniform(0.8, 1.3); sp = rnd.uniform(0.25, 0.4); r0, r1 = rnd.uniform(0.008, 0.014), rnd.uniform(0.035, 0.06)
        jit = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))) * 0.03
        for f in range(1, nf + 1):
            t = (f - 1) / FPS; u = (t - ts) / life
            if u < 0 or u > 1:
                o.scale = (0, 0, 0); o.location = Vector(mouth_fn(max(ts, min(t, ts + life))))
            else:
                p0 = Vector(mouth_fn(ts)); d = Vector(aim_fn(ts)).normalized()
                o.location = p0 + d * sp * u * life + Vector((0, 0, -0.12 * u * u)) + jit * u
                s = r0 + (r1 - r0) * u; o.scale = (s, s, s * 0.8)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f)
    return puffs


def weight(name, loc, s=0.07, parent=None):
    """a cast-iron weight: a dark iron block with a raised loop on top (what a string is tied round)"""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    iron = _mat("cast iron", "#2E3033", rough=0.55, metal=0.7)
    K.box(f"{name} block", (0, 0, s * 0.35), (s, s * 0.8, s * 0.7), iron, bev=0.008, parent=root)
    bpy.ops.mesh.primitive_torus_add(major_radius=s * 0.22, minor_radius=s * 0.06, location=(0, 0, s * 0.78))
    lp = bpy.context.active_object; lp.name = f"{name} loop"; lp.rotation_euler = (math.pi / 2, 0, 0)
    lp.data.materials.append(iron); lp.parent = root
    for p in lp.data.polygons: p.use_smooth = True
    root["tie"] = s * 0.92
    root.location = loc
    return root
