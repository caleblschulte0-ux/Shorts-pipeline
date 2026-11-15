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


def shrivel(root, t0, t1, to=0.5, seed=0, hang=True):
    """the balloon goes LIMP (judge 2026-11-15: a shrunk round balloon read as "a candy blob, jelly beans"): its
    skin loses its gas and stops being round. It narrows a lot and stays long (an empty sock, not a smaller ball),
    wrinkles deeply, and folds over its own knot until it hangs DOWN off it, the knot and string where they were.
    Nothing drops: the knot never moves (the root is the knot). hang=False: it only goes soft and droops sideways."""
    body = bpy.data.objects[root["body"]]
    rnd = random.Random(seed)
    tex = bpy.data.textures.new(f"{root.name} wrinkle", 'CLOUDS'); tex.noise_scale = 0.12; tex.noise_depth = 2
    md = body.modifiers.new("wrinkle", 'DISPLACE'); md.texture = tex; md.texture_coords = 'LOCAL'; md.mid_level = 0.6
    side = rnd.choice((-1, 1)); lean = (rnd.uniform(2.75, 2.95) if hang else rnd.uniform(1.2, 1.5))
    for t, u in ((0.0, 0.0), (t0, 0.0)) + tuple((t0 + (t1 - t0) * k / 8, k / 8) for k in range(1, 9)):
        e = u * u * (3 - 2 * u)
        w = 1 - (1 - to * 0.75) * e                  # width falls further than length: limp, not small
        ln = 1 - (1 - to * 1.35) * e
        body.scale = (w, w * (1 - 0.25 * e), ln); body.keyframe_insert("scale", frame=F(t))
        root.rotation_euler = (0, side * lean * (e ** 1.4), 0); root.keyframe_insert("rotation_euler", frame=F(t))
        md.strength = 0.14 * e; md.keyframe_insert("strength", frame=F(t))
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


def inflate(root, t0, t1, frm=0.3, seed=0, droop=0.0):
    """the reverse of shrivel: a limp, wrinkled skin fills out round and tight from t0 to t1, with a little
    overshoot and wobble as it tightens (latex is springy). droop (radians): it starts flopped over to one side of
    its knot, an empty skin hanging off the neck (judge, round 2: "starts small and taut, not limp over the open
    end"), and rights itself, standing up as the gas fills it."""
    body = bpy.data.objects[root["body"]]
    tex = bpy.data.textures.new(f"{root.name} wrinkle", 'CLOUDS'); tex.noise_scale = 0.14
    md = body.modifiers.new("wrinkle", 'DISPLACE'); md.texture = tex; md.texture_coords = 'LOCAL'; md.mid_level = 0.6 if droop else 0.5
    keys = [(0.0, 0.0), (t0, 0.0)] + [(t0 + (t1 - t0) * k / 8, k / 8) for k in range(1, 9)]
    for t, u in keys:
        e = u * u * (3 - 2 * u); s = frm + (1 - frm) * e
        if droop:                                         # limp: narrow and long, an empty sock, not a small ball
            body.scale = (s * (1 - 0.45 * (1 - e)), s * (1 - 0.5 * (1 - e)), min(1.0, s * (1 + 0.9 * (1 - e))))
        else:
            body.scale = (s * (1 - 0.15 * (1 - e)), s, s * (1 - 0.4 * (1 - e)))
        body.keyframe_insert("scale", frame=F(t))
        md.strength = (0.13 if droop else 0.06) * (1 - e); md.keyframe_insert("strength", frame=F(t))
        if droop:
            root.rotation_euler = (0, droop * (1 - min(1.0, e * 1.3)), 0); root.keyframe_insert("rotation_euler", frame=F(t))
    for dt, w in ((0.12, 1.06), (0.26, 0.97), (0.4, 1.0)):
        body.scale = (w, w, w); body.keyframe_insert("scale", frame=F(t1 + dt))
    return body


def scanner(name, loc, R=0.62, depth=0.55, parent=None, light_at=None, light_r=0.13, shell_hex="#ECEEF0"):
    """a hospital MRI scanner, front on: a deep white ring around a dark bore, a padded table sliding out of it, a
    fill port on top and a big status light on the ring's face. Returns (root, light material, port point local)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    shell = _mat(f"scanner shell {shell_hex}", shell_hex, rough=0.28, coat=0.5)
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
    LA = Vector(light_at) if light_at is not None else Vector((-R * 0.55, -depth * 0.52, R * 1.4))
    # a BIG, sharp lamp in a dark bezel (judge 2026-11-15: "small and blurry, the payoff barely reads on a phone")
    K.cyl(f"{name} status bezel", tuple(LA + Vector((0, 0.006, 0))), light_r * 1.22, 0.03, _mat("lamp bezel", "#22262B", rough=0.4, metal=0.4), rot=(math.pi / 2, 0, 0), v=48, bev=0.004, parent=root)
    K.cyl(f"{name} status light", tuple(LA), light_r, 0.03, light, rot=(math.pi / 2, 0, 0), v=48, bev=0.006, parent=root)
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


def cold_smoke(name, mouth_fn, aim_fn, t0, t1, nf, n=150, seed=0, floor_z=None, into=None):
    """the white cold vapour of boiling liquid helium (judge 2026-11-15: "stacked spheres", not smoke). Many faint,
    soft wisps (a translucent, edge-faded white, each alone barely there) leave the mouth from t0 to t1, fall
    along the pour (cold gas sinks), swell and stretch along their path, and where they meet floor_z they spread out
    flat and pool, thinning away. Overlapping, they read as one flowing sheet of vapour."""
    rnd = random.Random(seed)
    m = bpy.data.materials.new(f"{name} vapour"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.55   # facing: thick, edges: gone
    ramp = nt.nodes.new("ShaderNodeMath"); ramp.operation = 'MULTIPLY'; ramp.inputs[1].default_value = 0.22
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1]); nt.links.new(inv.outputs[0], ramp.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.93, 0.96, 1.0, 1); em.inputs["Strength"].default_value = 0.9
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); dif.inputs["Color"].default_value = (0.95, 0.97, 1.0, 1)
    add = nt.nodes.new("ShaderNodeAddShader"); nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(dif.outputs[0], add.inputs[1])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(ramp.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(add.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
    try: m.blend_method = 'BLEND'
    except Exception: pass
    puffs = []
    for i in range(n):
        ts = t0 + (t1 - t0) * i / n + rnd.uniform(-0.015, 0.015)
        o = K.sph(f"{name} wisp {i}", (0, 0, -5), 1.0, m, seg=20, ring=10); puffs.append(o)
        o.visible_shadow = False if hasattr(o, "visible_shadow") else None
        life = rnd.uniform(1.0, 1.6); sp = rnd.uniform(0.18, 0.3); r0, r1 = rnd.uniform(0.012, 0.02), rnd.uniform(0.05, 0.085)
        jit = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 0.2))) * 0.035
        spread = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.6), 0)) * 0.22
        spin = rnd.uniform(0, math.tau)
        for f in range(1, nf + 1):
            t = (f - 1) / FPS; u = (t - ts) / life
            if u < 0 or u > 1:
                o.scale = (0, 0, 0); o.location = Vector(mouth_fn(max(ts, min(t, ts + life))))
            elif into is not None:          # it pours INTO a port (judge, round 2: "smoke goes into a funnel and piles up on
                # the floor, never into the scanner"; "flat white discs"): a sinking arc from the lip to the port's
                # mouth, swelling as it falls and drawn in, shrinking to nothing as it goes down the port
                p0 = Vector(mouth_fn(ts)); q = Vector(into); u2 = min(1.0, u * 1.25)
                mid = p0.lerp(q, 0.5) + Vector((0, 0, 0.02)) + jit * 0.6
                p = p0 * (1 - u2) ** 2 + mid * 2 * u2 * (1 - u2) + q * u2 * u2 + jit * 0.3 * math.sin(math.pi * u2)
                o.location = p
                s_ = (r0 * 0.8 + (r1 * 0.42 - r0 * 0.8) * min(1.0, u2 * 1.6)) * (1.0 - ease_in(max(0.0, u2 - 0.55) / 0.3))
                o.scale = (s_ * 1.25, s_ * 1.1, s_ * 1.0)
                o.rotation_euler = (0, 0, spin + u)
            else:
                p0 = Vector(mouth_fn(ts)); d = Vector(aim_fn(ts)).normalized()
                p = p0 + d * sp * u * life + Vector((0, 0, -0.22 * u * u)) + jit * u
                flat = 0.0
                if floor_z is not None and p.z < floor_z + 0.015:
                    flat = min(1.0, (floor_z + 0.015 - p.z) / 0.06)
                    p = Vector((p.x, p.y, floor_z + 0.015)) + spread * flat
                o.location = p
                s_ = (r0 + (r1 - r0) * u) * (1.0 - 0.35 * max(0.0, u - 0.75) / 0.25)
                o.scale = (s_ * (1.4 + flat), s_ * (1.1 + flat), s_ * (0.75 - 0.4 * flat))
                o.rotation_euler = (0, 0, spin + u)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f); o.keyframe_insert("rotation_euler", frame=f)
    return puffs


def ease_in(u):
    u = max(0.0, min(1.0, u)); return u * u


def frost_spread(obj_name, centre, t0, t1, r_max, white="#F2F8FD"):
    """FROST CREEPS OUT over a surface from one point (judge, round 2: "no frost is seen spreading over the ring"): a
    skin just over the object whose frosted patch is everything within r(t) of `centre`, with a ragged rim, r
    growing from 0 at t0 to r_max at t1. Returns the skin."""
    src = bpy.data.objects[obj_name]
    sk = src.copy(); sk.data = src.data.copy(); sk.name = f"{obj_name} frost"; bpy.context.collection.objects.link(sk)
    sk.scale = tuple(v * 1.01 for v in src.scale)
    sk.data.materials.clear()
    cen = K.empty(f"{obj_name} frost centre", tuple(centre))
    m = bpy.data.materials.new(f"{obj_name} frost"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.object = cen
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = 'LENGTH'; nt.links.new(tc.outputs["Object"], ln.inputs[0])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40.0; nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    jag = nt.nodes.new("ShaderNodeMath"); jag.operation = 'MULTIPLY_ADD'; jag.inputs[1].default_value = 0.035; jag.inputs[2].default_value = -0.017
    nt.links.new(nz.outputs["Fac"], jag.inputs[0])
    dist = nt.nodes.new("ShaderNodeMath"); dist.operation = 'ADD'; nt.links.new(ln.outputs["Value"], dist.inputs[0]); nt.links.new(jag.outputs[0], dist.inputs[1])
    lt = nt.nodes.new("ShaderNodeMath"); lt.operation = 'LESS_THAN'; nt.links.new(dist.outputs[0], lt.inputs[0])
    rad = lt.inputs[1]
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled"); bs.inputs["Base Color"].default_value = (*K.lin(white), 1)
    bs.inputs["Roughness"].default_value = 0.55    # white crystal on a grey ring (round 3: an icy tint on white "barely visible")
    nz2 = nt.nodes.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 160.0; nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.6     # crystals, not paint
    nt.links.new(nz2.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(lt.outputs[0], mx.inputs[0])
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(bs.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
    sk.data.materials.append(m)
    for t, u in ((0.0, 0.0), (t0, 0.0)) + tuple((t0 + (t1 - t0) * k / 6, k / 6) for k in range(1, 7)):
        rad.default_value = r_max * (u * u * (3 - 2 * u)) if u > 0 else -1.0
        rad.keyframe_insert("default_value", frame=F(t))
    return sk


def weight(name, loc, s=0.13, parent=None):
    """a cast-iron KETTLEBELL (judge 2026-11-15: "a small dark block that blends into the shelves, doesn't read as
    heavy iron"): a fat round iron belly on a flat foot, a thick arched handle on top (what a string is tied round),
    satin black iron with a cool highlight and a stamped weight band, so it reads as heavy on a phone."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    iron = _mat("kettlebell iron", "#2B2D30", rough=0.38, metal=0.85, coat=0.25)
    band = _mat("kettlebell band", "#C8A14A", rough=0.35, metal=1.0)
    R = s * 0.5
    K.sph(f"{name} belly", (0, 0, R * 0.95), R, iron, scale=(1, 1, 0.92), parent=root, seg=48, ring=24)
    K.cyl(f"{name} foot", (0, 0, R * 0.08), R * 0.62, R * 0.16, iron, v=40, bev=0.004, parent=root)
    K.cyl(f"{name} band", (0, 0, R * 0.95), R * 1.005, R * 0.16, band, v=48, bev=0.002, parent=root)
    for sx in (-1, 1):                        # the handle's two horns out of the belly
        K.cyl(f"{name} horn", (sx * R * 0.55, 0, R * 1.75), R * 0.16, R * 0.5, iron, v=20, bev=0.004, parent=root)
    bpy.ops.mesh.primitive_torus_add(major_radius=R * 0.55, minor_radius=R * 0.16, major_segments=40, minor_segments=14, location=(0, 0, R * 2.0))
    hd = bpy.context.active_object; hd.name = f"{name} handle"; hd.rotation_euler = (math.pi / 2, 0, 0)
    hd.data.materials.append(iron); hd.parent = root
    for p in hd.data.polygons: p.use_smooth = True
    root["tie"] = R * 2.55                    # the top of the handle's arch
    root.location = loc
    return root


def helium_tank(name, loc, r=0.075, h=0.46, color="#8FB3CF"):
    """a party HELIUM TANK standing on the floor: a painted steel bottle, domed shoulder, a brass valve with a big
    round knob on top (a hand turns it), a fill nozzle out to the side where a balloon goes on, and a BIG pressure
    gauge facing the camera (white face, a green FULL arc and a red EMPTY arc, a black needle on a pivot): the needle
    falling into the red is the tank running dry, readable on a phone. Data's arms are short (about 0.2 from the
    shoulder), so the knob and the gauge are both at the top, at his hand. Returns (root, knob, needle, points local:
    {"knob", "nozzle", "gauge"})."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    paint = _mat(f"tank paint {color}", color, rough=0.32, metal=0.35, coat=0.5)
    K.cyl(f"{name} body", (0, 0, h / 2), r, h, paint, v=48, bev=0.012, parent=root)
    K.sph(f"{name} shoulder", (0, 0, h), r, paint, scale=(1, 1, 0.55), parent=root, seg=48, ring=16)
    K.cyl(f"{name} foot ring", (0, 0, 0.012), r * 1.02, 0.024, _mat("tank foot", "#3A3F45", rough=0.5, metal=0.5), v=48, bev=0.004, parent=root)
    brass = _mat("valve brass", "#B88A3A", rough=0.3, metal=1.0)
    vz = h + r * 0.55
    K.cyl(f"{name} valve", (0, 0, vz + 0.03), r * 0.3, 0.06, brass, v=24, bev=0.004, parent=root)
    knob = K.empty(f"{name} knob", (0, 0, vz + 0.075), parent=root)
    km = _mat("tank knob", "#2F7FD8", rough=0.35, coat=0.4)
    K.cyl(f"{name} knob disc", (0, 0, vz + 0.075), r * 0.62, 0.025, km, v=40, bev=0.006, parent=knob)
    for k in range(6):                        # grip lugs: the knob reads as turning
        a = k * math.tau / 6
        K.cyl(f"{name} knob lug", (math.cos(a) * r * 0.62, math.sin(a) * r * 0.62, vz + 0.075), r * 0.11, 0.03, km, v=12, bev=0.003, parent=knob)
    K.box(f"{name} knob mark", (r * 0.35, 0, vz + 0.089), (r * 0.42, r * 0.1, 0.004), _mat("knob mark", "#F4F2EC", rough=0.4), bev=0.001, parent=knob)
    # the fill nozzle: out to the image-right and up
    K.cyl(f"{name} nozzle arm", (r * 0.45, 0, vz + 0.03), r * 0.12, r * 0.6, brass, rot=(0, math.pi / 2, 0), v=16, bev=0.002, parent=root)
    K.cyl(f"{name} nozzle", (r * 0.75, 0, vz + 0.06), r * 0.13, 0.05, _mat("nozzle black", "#1E2124", rough=0.6), v=16, bev=0.002, parent=root)
    noz = Vector((r * 0.75, 0, vz + 0.09))
    # the gauge: on the body's front, big, tilted a little up to the lens
    # the regulator gauge sits on the valve at the top, as on a real party tank: big, at his hand, facing the lens
    G = Vector((0, -r * 0.7 - 0.02, h + r * 0.35)); GR = r * 0.88
    K.cyl(f"{name} gauge stem", (0, -r * 0.35, h + r * 0.35), r * 0.12, r * 0.75, brass, rot=(math.pi / 2, 0, 0), v=16, bev=0.002, parent=root)
    gt = (math.pi / 2 - 0.12, 0, 0)
    K.cyl(f"{name} gauge rim", tuple(G + Vector((0, 0.004, 0))), GR * 1.12, 0.022, _mat("gauge chrome", "#C9CDD2", rough=0.2, metal=1.0), rot=gt, v=48, bev=0.004, parent=root)
    K.cyl(f"{name} gauge face", tuple(G), GR, 0.02, _mat("gauge face", "#F6F4EE", rough=0.45), rot=gt, v=48, bev=0.002, parent=root)
    nrm = Vector((0, -math.cos(0.12), math.sin(0.12)))              # the face's outward normal
    upv = Vector((0, math.sin(0.12), math.cos(0.12)))               # "up" on the face
    rt = Vector((1, 0, 0))
    def face_rot(a):                          # local X = across the face, local Y = "up" on it, local Z = out of it
        return (Matrix.Rotation(gt[0], 4, 'X') @ Matrix.Rotation(-a, 4, 'Z')).to_euler('XYZ')
    def on_face(a, rad, lift=0.012):          # a = 0 points straight up, + clockwise as we look at it
        return G + nrm * lift + (rt * math.sin(a) + upv * math.cos(a)) * rad
    for a0, a1, hexc in ((-2.2, -1.1, "#D9332B"), (0.9, 2.2, "#2FAF55")):   # EMPTY on the left, FULL on the right
        mm = _mat(f"gauge arc {hexc}", hexc, rough=0.4, emit=0.3)
        for k in range(10):
            a = a0 + (a1 - a0) * (k + 0.5) / 10
            K.box(f"{name} arc", tuple(on_face(a, GR * 0.78)), (GR * 0.24, GR * 0.18, 0.004), mm, bev=0.0005, parent=root).rotation_euler = face_rot(a)
    for k in range(9):                        # ticks
        a = -2.2 + 4.4 * k / 8
        K.box(f"{name} tick", tuple(on_face(a, GR * 0.55, 0.013)), (0.004, GR * 0.12, 0.003), _mat("tick black", "#1A1C1F", rough=0.5), bev=0.0, parent=root).rotation_euler = face_rot(a)
    needle = K.empty(f"{name} needle", tuple(G + nrm * 0.016), parent=root)
    needle.rotation_euler = gt
    blk = _mat("needle black", "#141618", rough=0.4)
    nd = K.box(f"{name} needle bar", tuple(G + nrm * 0.016 + upv * GR * 0.36), (GR * 0.07, GR * 0.72, 0.004), blk, bev=0.001, parent=needle)
    nd.rotation_euler = face_rot(0.0)
    K.cyl(f"{name} needle hub", tuple(G + nrm * 0.018), GR * 0.1, 0.008, blk, rot=gt, v=20, bev=0.001, parent=needle)
    root.location = loc
    return root, knob, needle, {"knob": Vector((0, 0, vz + 0.09)), "nozzle": noz, "gauge": G}


def needle_to(needle, t, a, base=None):
    """key the tank gauge's needle to angle a (radians; 0 = straight up, + toward FULL on the right) at t"""
    b = base if base is not None else (math.pi / 2 - 0.12)
    needle.rotation_euler = (b, 0, 0)
    # turn about the face normal: built as a child rotation so the bar stays on the face
    needle.rotation_mode = 'XYZ'
    m = Matrix.Rotation(b, 4, 'X') @ Matrix.Rotation(-a, 4, 'Z')
    needle.rotation_euler = m.to_euler('XYZ')
    needle.keyframe_insert("rotation_euler", frame=F(t))


def crank_wellhead(name, loc, h=0.4, r=0.045, stem=0.17, WR=0.075, front=False, neck_h=0.0, stem_a=0.0, gauge=False):
    """a gas wellhead with its valve wheel turned to FACE THE CAMERA (judge 2026-11-15: a flat wheel on top "looks
    static, the cause isn't readable"): a fat red pipe out of a concrete pad up to a gate valve, an open steel neck
    on top where a balloon is tied (the gas from the ground fills it right there), and out to the image-left (-X) a
    stem carrying a big yellow handwheel standing up, spokes and a red crank knob on its rim, so a hand going round
    with the knob reads as turning from any distance. Returns (root, wheel, neck point local, wheel centre local,
    WR); the wheel turns about local Y. front=True: the stem comes straight out of the pipe TOWARD the camera (-Y),
    so the wheel stands clear in front of the pipe, beside whoever turns it, never behind his arm (round 3: "the
    yellow wheel is hidden behind his arm, his body and the pipe"). neck_h: the balloon neck rises that much higher
    on a pipe of its own, so a full balloon floats above a head beside it. stem_a (radians): a front stem swung that
    far toward -X, so the pipe and its balloon stand off to the side of whoever turns the wheel (the wheel itself
    still faces -Y, the camera)."""
    root = K.empty(name, (0, 0, 0))   # built at the origin (K builds children at absolute spots), placed at the end
    red = _mat("wellhead paint", "#56707F", rough=0.45, metal=0.4, coat=0.2)   # painted steel, not red: red read as a
                                                                  # fire hydrant (helium round 7)
    steel = _mat("wellhead steel", "#8C9196", rough=0.3, metal=1.0)
    conc = _mat("well pad", "#9A968E", rough=0.9)
    K.box(f"{name} pad", (0, 0, 0.02), (0.22, 0.22, 0.04), conc, bev=0.01, parent=root)
    K.cyl(f"{name} pipe", (0, 0, h / 2), r, h, red, v=32, bev=0.004, parent=root)
    for z in (0.09, h - 0.08):
        K.cyl(f"{name} flange", (0, 0, z), r * 1.7, 0.026, red, v=32, bev=0.004, parent=root)
        for k in range(8):
            a = k * math.tau / 8
            K.cyl(f"{name} bolt", (math.cos(a) * r * 1.45, math.sin(a) * r * 1.45, z + 0.016), 0.005, 0.012, steel, v=8, bev=0.001, parent=root)
    K.box(f"{name} valve body", (0, 0, h - 0.02), (r * 2.6, r * 2.4, 0.09), red, bev=0.012, parent=root)
    K.cyl(f"{name} neck", (0, 0, h + 0.05 + neck_h / 2), r * 0.5, 0.06 + neck_h, steel, v=24, bev=0.003, parent=root)
    K.cyl(f"{name} neck lip", (0, 0, h + 0.08 + neck_h), r * 0.62, 0.012, steel, v=24, bev=0.002, parent=root)
    if front:
        dv = Vector((-math.sin(stem_a), -math.cos(stem_a), 0))
        WC = dv * stem + Vector((0, 0, h - 0.02))
        st = K.cyl(f"{name} stem", tuple(dv * (stem / 2) + Vector((0, 0, h - 0.02))), r * 0.32, stem, steel, v=16, bev=0.002, parent=root)
        st.rotation_euler = dv.to_track_quat('Z', 'Y').to_euler()
    else:
        WC = Vector((-stem, -0.01, h - 0.02))
        K.cyl(f"{name} stem", (-stem / 2, -0.01, h - 0.02), r * 0.32, stem, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.002, parent=root)
    wheel = K.empty(f"{name} wheel", tuple(WC), parent=root)
    hw = _mat("handwheel", "#E2C531", rough=0.4, metal=0.2, coat=0.3)
    bpy.ops.mesh.primitive_torus_add(major_radius=WR, minor_radius=0.01, major_segments=48, minor_segments=12, location=tuple(WC))
    tor = bpy.context.active_object; tor.name = f"{name} handwheel"; tor.rotation_euler = (math.pi / 2, 0, 0)
    tor.data.materials.append(hw)
    for pl in tor.data.polygons: pl.use_smooth = True
    tor.parent = wheel; tor.matrix_parent_inverse = wheel.matrix_basis.inverted()
    for k in range(4):
        sp = K.cyl(f"{name} spoke", tuple(WC), 0.007, WR * 2, hw, v=8, bev=0.001, parent=wheel)
        sp.rotation_euler = (0, k * math.pi / 4, 0)
    K.cyl(f"{name} hub", tuple(WC + Vector((0, -0.01, 0))), 0.02, 0.03, steel, rot=(math.pi / 2, 0, 0), v=16, bev=0.002, parent=wheel)
    knob = _mat("crank knob", "#C62B24", rough=0.35, coat=0.4)
    K.cyl(f"{name} crank", tuple(WC + Vector((WR, -0.025, 0))), 0.014, 0.05, knob, rot=(math.pi / 2, 0, 0), v=16, bev=0.004, parent=wheel)
    if gauge:                         # a pressure gauge on the valve body, facing the lens: gas plumbing
        face = _mat("gauge face", "#F4F1EA", rough=0.5); rim = _mat("gauge rim", "#2B2D30", rough=0.35, metal=0.8)
        GZ = h + 0.06
        K.cyl(f"{name} gauge stalk", (0, -r * 1.3, GZ - 0.02), 0.006, 0.04, steel, v=8, bev=0.001, parent=root)
        K.cyl(f"{name} gauge rim", (0, -r * 1.4, GZ + 0.02), 0.034, 0.02, rim, rot=(math.pi / 2, 0, 0), v=32, bev=0.003, parent=root)
        K.cyl(f"{name} gauge face", (0, -r * 1.4 - 0.011, GZ + 0.02), 0.028, 0.003, face, rot=(math.pi / 2, 0, 0), v=32, bev=0.0005, parent=root)
        K.box(f"{name} gauge needle", (0.008, -r * 1.4 - 0.014, GZ + 0.026), (0.022, 0.002, 0.003), rim, bev=0.0, parent=root)
        K.cyl(f"{name} ground pipe", (0.09, 0.0, 0.03), r * 0.6, 0.06, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.002, parent=root)   # a line running off into the ground
    root.location = loc
    return root, wheel, Vector((0, 0, h + 0.09 + neck_h)), WC, WR
