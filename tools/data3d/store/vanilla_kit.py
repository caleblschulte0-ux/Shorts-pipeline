"""THE VANILLA KIT (the fifth 3D short, 2026-11-18): a vanilla orchid that can be pollinated and grow its bean, a
bamboo stick, a vanilla bean that cures green -> brown -> black and can split to spill its seeds, a vine on a post, an
hourglass whose sand really runs, a steel grinder with a hopper and a spout, a log, and a bottle of vanilla flavour
that fills. Kept for any spice, flower, farm or kitchen story after it. Units are the store's: metres at Data's scale
(he is 0.96 tall, his hands hang at 0.30).

Every piece is MADE OF what it is (docs/CHANNEL_LOOK.md): an orchid is three long sepals, two petals and a rolled
trumpet lip on a green stem, not a yellow ball; a bean is a long thin wrinkled pod; an hourglass is two glass bulbs
in a wooden frame with sand you can watch fall."""
import math, random
import bpy
from mathutils import Vector
import scene_kit as K
from clock import FPS

F = lambda t: int(round(t * FPS)) + 1
PETAL, LIP, STEM, LEAF, BAMBOO = "#EFE7A0", "#F2C94C", "#6E9A3A", "#2F6E2A", "#C9A46A"
GREEN, BROWN, BLACK = "#3F7A22", "#6A4422", "#1A110B"


def _mat(name, hexc, rough=0.5, metal=0.0, emit=0.0, coat=0.0, sss=0.0, alpha=None, trans=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = K.mat(name, hexc, rough=rough, metal=metal, emit=emit)
    b = m.node_tree.nodes.get("Principled BSDF")
    for k, v in (("Coat Weight", coat), ("Subsurface Weight", sss), ("Transmission Weight", trans)):
        try:
            if v: b.inputs[k].default_value = v
        except KeyError: pass
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        try: m.blend_method = 'BLEND'
        except AttributeError: pass
    return m


def glass():
    return _mat("hourglass glass", "#E8F1F4", rough=0.05, trans=1.0, coat=0.5)


def _flat(name, loc, r, sc, m, rot, parent):
    o = K.sph(name, tuple(loc), r, m, scale=sc, parent=parent, seg=24, ring=12)
    o.rotation_euler = rot
    return o


# ------------------------------------------------------------------ the bean
def bean_mat(name="vanilla bean"):
    """a pod whose colour can be keyed: input 'cure' 0 = fresh green, 0.5 = brown, 1 = cured shiny black. Wrinkles are
    bump along its length; it goes glossier as it cures (oily, as a real cured bean is)."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    val = nt.nodes.new("ShaderNodeValue"); val.name = "cure"; val.outputs[0].default_value = 0.0
    rp = nt.nodes.new("ShaderNodeValToRGB")
    els = rp.color_ramp.elements
    els[0].position = 0.0; els[0].color = (*K.lin(GREEN), 1)
    els[-1].position = 1.0; els[-1].color = (*K.lin(BLACK), 1)
    els.new(0.5).color = (*K.lin(BROWN), 1)               # (set the ends FIRST: new() re-sorts, and elements[1] moved)
    nt.links.new(val.outputs[0], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange"); rough.inputs["To Min"].default_value = 0.55; rough.inputs["To Max"].default_value = 0.3
    nt.links.new(val.outputs[0], rough.inputs["Value"]); nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    tc = nt.nodes.new("ShaderNodeTexCoord"); wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = 'BANDS'
    wv.inputs["Scale"].default_value = 18.0; wv.inputs["Distortion"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35
    nt.links.new(wv.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def cure(m, keys):
    """keys: [(t, value 0..1)] on a bean material's cure"""
    v = m.node_tree.nodes["cure"].outputs[0]
    for t, x in keys:
        v.default_value = x; v.keyframe_insert("default_value", frame=F(t))


def bean(name, loc, length=0.16, r=0.011, m=None, rot=(0, 0, 0), parent=None):
    """a vanilla pod: long, thin, slightly flattened and tapered at both ends, built along +Z from its stem end at the
    root's origin. Scale the root's Z from 0 to 1 and it GROWS out of the flower."""
    m = m or bean_mat()
    root = K.empty(name, (0, 0, 0))
    K.capsule(f"{name} pod", Vector((0, 0, 0.0)), Vector((0, 0, length)), r, m, parent=root, seg=16, ra=r * 0.45, rb=r * 0.55)
    K.capsule(f"{name} belly", Vector((0, 0, length * 0.18)), Vector((0, 0, length * 0.82)), r, m, parent=root, seg=16, ra=r, rb=r)
    for o in root.children: o.scale = (1.0, 0.72, 1.0)
    root.location = loc; root.rotation_euler = rot
    if parent is not None: root.parent = parent
    return root


# ------------------------------------------------------------------ the orchid
def orchid(name, loc, s=1.0, yaw=0.0, parent=None, hv=(0.0, -0.05, -0.05)):
    """a vanilla orchid flower facing -Y (the camera): three long pale sepals in a Y, two narrower petals, and the
    rolled yellow trumpet lip at the heart, on a short green ovary/stem going up and back (+Y, +Z) to the vine. The
    stem's base is the root's origin. Returns (root, heart point local, bloom root): the bloom can wilt or drop as one."""
    root = K.empty(name, (0, 0, 0))
    pm = _mat("orchid petal", PETAL, rough=0.45, sss=0.3); lm = _mat("orchid lip", LIP, rough=0.4, sss=0.3)
    sm = _mat("orchid stem", STEM, rough=0.55)
    H = Vector(hv) * s                                       # the heart, from the stem's base (default forward and down)
    K.capsule(f"{name} ovary", Vector((0, 0, 0)), H + Vector((0, 0.008 * s, 0.006 * s)), 0.0055 * s, sm, parent=root, seg=12)
    bloom = K.empty(f"{name} bloom", tuple(H), parent=root)
    for k in range(3):                                       # sepals: up, and down-left / down-right
        a = math.radians(90 + 120 * k)
        d = Vector((math.cos(a), 0, math.sin(a)))
        _flat(f"{name} sepal {k}", H + d * 0.03 * s + Vector((0, 0.002 * s, 0)), 0.032 * s, (1.0, 0.12, 0.4), pm, (0, -a, 0), bloom)
    for k, a in enumerate((math.radians(25), math.radians(155))):    # petals: out to the sides, a little up, in front
        d = Vector((math.cos(a), 0, math.sin(a)))
        _flat(f"{name} petal {k}", H + d * 0.027 * s + Vector((0, -0.003 * s, 0)), 0.028 * s, (1.0, 0.12, 0.45), pm, (0, -a, 0), bloom)
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.019 * s, radius2=0.008 * s, depth=0.03 * s, end_fill_type='NOTHING',
                                    location=tuple(H + Vector((0, -0.012 * s, -0.006 * s))), rotation=(math.radians(90), 0, 0))
    lip = bpy.context.active_object; lip.name = f"{name} lip"; lip.data.materials.append(lm)
    sol = lip.modifiers.new("thick", 'SOLIDIFY'); sol.thickness = 0.0015 * s
    for pl in lip.data.polygons: pl.use_smooth = True
    bpy.context.view_layer.update(); lip.parent = bloom; lip.matrix_parent_inverse = bloom.matrix_world.inverted()
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    if parent is not None: root.parent = parent
    return root, H, bloom


def stick(name, length=0.12, r=0.006, parent=None):
    """a bevelled sliver of bamboo, built along +Z from its butt at the root (the hand holds the butt end)"""
    root = K.empty(name, (0, 0, 0))
    m = _mat("bamboo sliver", BAMBOO, rough=0.55)
    K.capsule(f"{name} shaft", Vector((0, 0, 0)), Vector((0, 0, length)), r, m, parent=root, seg=8, ra=r * 1.3, rb=r * 0.35)
    if parent is not None: root.parent = parent
    return root


def leaf(name, loc, size=0.07, rot=(0, 0, 0), parent=None):
    """a thick glossy vanilla leaf: a long flattened oval"""
    m = _mat("vanilla leaf", LEAF, rough=0.3, coat=0.4)
    o = K.sph(name, (0, 0, 0), size, m, scale=(0.42, 0.1, 1.0), seg=20, ring=10)
    o.location = loc; o.rotation_euler = rot
    if parent is not None: o.parent = parent
    return o


def vine_post(name, loc, h=1.6, seed=0, r=0.035):
    """a wooden post with a green vanilla vine wound up it, leaves every few centimetres"""
    rnd = random.Random(seed)
    root = K.empty(name, (0, 0, 0))
    wood = _mat("vine post wood", "#7A5E40", rough=0.9)
    K.cyl(f"{name} post", (0, 0, h / 2), r, h, wood, v=12, bev=0.003, parent=root)
    sm = _mat("vine stem", "#4E7E2A", rough=0.5)
    pts = []
    n = 26
    for i in range(n + 1):
        z = 0.05 + (h - 0.1) * i / n; a = i * 0.9 + seed
        pts.append(Vector((math.cos(a) * (r + 0.008), math.sin(a) * (r + 0.008), z)))
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        K.capsule(f"{name} vine {i}", a, b, 0.006, sm, parent=root, seg=8)
        if i % 2 == 0:
            out = Vector((a.x, a.y, 0)).normalized()
            leaf(f"{name} leaf {i}", tuple(a + out * 0.045 + Vector((0, 0, -0.01))), size=rnd.uniform(0.045, 0.06),
                 rot=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.4, 0.4), math.atan2(out.y, out.x) + math.pi / 2), parent=root)
    root.location = loc
    return root


# ------------------------------------------------------------------ the hourglass
def hourglass(name, loc, h=0.3, parent=None):
    """a big wooden hourglass: two glass bulbs, a top and a bottom cap, three turned posts, sand in the top bulb that
    drains (top cone shrinks) into a heap that grows in the bottom, with a thin falling stream between. Returns
    (root, run(t0, t1)): keys the sand running from full at t0 to empty at t1."""
    root = K.empty(name, (0, 0, 0))
    wood = _mat("hourglass wood", "#6B4426", rough=0.5, coat=0.2)
    sand = _mat("hourglass sand", "#E2B867", rough=0.85)
    R = h * 0.3
    K.cyl(f"{name} base", (0, 0, 0.012), R * 1.25, 0.024, wood, v=32, bev=0.004, parent=root)
    K.cyl(f"{name} top", (0, 0, h - 0.012), R * 1.25, 0.024, wood, v=32, bev=0.004, parent=root)
    for k in range(3):
        a = k * math.tau / 3 + 0.3
        K.cyl(f"{name} post {k}", (math.cos(a) * R * 1.05, math.sin(a) * R * 1.05, h / 2), 0.006, h - 0.04, wood, v=12, bev=0.001, parent=root)
    g = glass()
    zb, zt = 0.024 + (h - 0.048) * 0.26, 0.024 + (h - 0.048) * 0.74
    for z in (zb, zt):
        K.sph(f"{name} bulb", (0, 0, z), R * 0.92, g, scale=(1, 1, 1.15), parent=root, seg=32, ring=16)
    K.cyl(f"{name} neck", (0, 0, h / 2), R * 0.12, h * 0.08, g, v=16, bev=0.0, parent=root)
    def cone(nm, z, flip):
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=R * 0.8, radius2=0.0, depth=R * 0.9, location=(0, 0, 0))
        o = bpy.context.active_object; o.name = nm; o.data.materials.append(sand)
        if flip: o.rotation_euler = (math.pi, 0, 0)
        piv = K.empty(f"{nm} pivot", (0, 0, z), parent=root)
        o.parent = piv; o.location = (0, 0, R * 0.45)   # apex (flipped) or base (upright) at the pivot: it shrinks/grows from there
        return piv
    top = cone(f"{name} sand top", h / 2 + h * 0.02, True)       # an inverted cone standing on its apex in the neck
    bot = cone(f"{name} sand heap", 0.024 + 0.006, False)
    stream = K.cyl(f"{name} stream", (0, 0, (0.03 + h / 2) / 2 + 0.01), 0.0018, h / 2 - 0.03, sand, v=8, bev=0, parent=root)
    root.location = loc
    if parent is not None: root.parent = parent

    def run(t0, t1):
        nf = F(t1) + 2
        for f in range(1, nf + 1):                           # keyed every frame: sand runs at a steady rate
            t = (f - 1) / FPS; u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            a, b = 1.0 - 0.96 * u, 0.05 + 0.95 * u
            top.scale = (a ** 0.5, a ** 0.5, a); top.keyframe_insert("scale", frame=f)
            bot.scale = (max(0.2, b ** 0.5), max(0.2, b ** 0.5), b); bot.keyframe_insert("scale", frame=f)
        for t, v in ((0.0, True), (t0, False), (t1, True)):
            stream.hide_render = v; stream.keyframe_insert("hide_render", frame=F(t))
    return root, run


# ------------------------------------------------------------------ the grinder, the log, the bottle
def grinder(name, loc, s=1.0):
    """a small steel pulping grinder on legs: a box body, a wide square hopper on top that takes a log, two big toothed
    gears on its camera-facing side that turn while it runs, and a spout at the image-left that pours. Returns
    (root, hopper mouth local, spout mouth local, gears)."""
    root = K.empty(name, (0, 0, 0))
    steel = _mat("grinder steel", "#9AA3AA", rough=0.3, metal=0.9); dark = _mat("grinder dark", "#3A3F44", rough=0.4, metal=0.6)
    paint = _mat("grinder paint", "#2F6A8C", rough=0.4, metal=0.3, coat=0.3)
    BW, BD, BH = 0.18 * s, 0.14 * s, 0.13 * s
    K.box(f"{name} body", (0, 0, BH / 2), (BW, BD, BH), paint, bev=0.008, parent=root)
    for x in (-1, 1):
        K.box(f"{name} hopper wall x", (x * BW * 0.42, 0, BH + 0.05 * s), (0.008 * s, BD * 0.9, 0.1 * s), steel, bev=0.002, parent=root).rotation_euler = (0, -x * 0.32, 0)
    for y in (-1, 1):
        K.box(f"{name} hopper wall y", (0, y * BD * 0.4, BH + 0.05 * s), (BW * 0.9, 0.008 * s, 0.1 * s), steel, bev=0.002, parent=root).rotation_euler = (y * 0.32, 0, 0)
    gears = []
    for k, (x, z, r) in enumerate(((-0.035 * s, BH * 0.5, 0.034 * s), (0.04 * s, BH * 0.42, 0.026 * s))):
        g = K.empty(f"{name} gear {k}", (x, -BD / 2 - 0.006 * s, z), parent=root)
        K.cyl(f"{name} gear disc {k}", (x, -BD / 2 - 0.006 * s, z), r, 0.008 * s, steel, rot=(math.pi / 2, 0, 0), v=32, bev=0.001, parent=g)
        n = 12 if k == 0 else 9
        for i in range(n):
            a = i * math.tau / n
            t = K.box(f"{name} tooth {k}{i}", (x + math.cos(a) * r, -BD / 2 - 0.006 * s, z + math.sin(a) * r), (0.008 * s, 0.008 * s, 0.008 * s), steel, bev=0.001, parent=g)
            t.rotation_euler = (0, -a, 0)
        K.cyl(f"{name} gear hub {k}", (x, -BD / 2 - 0.011 * s, z), r * 0.3, 0.006 * s, dark, rot=(math.pi / 2, 0, 0), v=16, bev=0.001, parent=g)
        gears.append(g)
    SP = Vector((-BW / 2 - 0.05 * s, -0.01 * s, BH * 0.82))
    sp = K.cyl(f"{name} spout", tuple((SP + Vector((-BW / 2, -0.01 * s, BH * 0.89))) / 2), 0.012 * s, 0.07 * s, steel, v=16, bev=0.002, parent=root)
    sp.rotation_euler = (0, math.radians(70), 0)
    for x in (-1, 1):
        for y in (-1, 1):
            K.cyl(f"{name} leg", (x * BW * 0.4, y * BD * 0.38, -0.01 * s), 0.01 * s, 0.02 * s, dark, v=8, bev=0.001, parent=root)
    root.location = loc
    return root, Vector((0, 0, BH + 0.1 * s)), SP, gears


def spin(objs, t0, t1, turns=4.0, axis=1):
    for i, g in enumerate(objs):
        sgn = 1 if i % 2 == 0 else -1
        for t, a in ((0.0, 0.0), (t0, 0.0), (t1, sgn * turns * math.tau * (1.3 if i else 1.0))):
            r = [0.0, 0.0, 0.0]; r[axis] = a; g.rotation_euler = r; g.keyframe_insert("rotation_euler", frame=F(t))


def log(name, loc, r=0.035, length=0.15, rot=(0, 0, 0)):
    """a short barked log, built along its local X: rough brown bark, pale end grain with rings"""
    root = K.empty(name, (0, 0, 0))
    bark = _mat("log bark", "#5A4030", rough=0.95); grain = _mat("log end grain", "#D9B98A", rough=0.8)
    K.cyl(f"{name} bark", (0, 0, 0), r, length, bark, rot=(0, math.pi / 2, 0), v=20, bev=0.004, parent=root)
    for x in (-1, 1):
        K.cyl(f"{name} end", (x * length / 2, 0, 0), r * 0.9, 0.003, grain, rot=(0, math.pi / 2, 0), v=20, bev=0.0, parent=root)
        K.cyl(f"{name} ring", (x * (length / 2 + 0.0016), 0, 0), r * 0.5, 0.001, _mat("log ring", "#B8935E", rough=0.8), rot=(0, math.pi / 2, 0), v=20, bev=0.0, parent=root)
    root.location = loc; root.rotation_euler = rot
    return root


def bottle(name, loc, h=0.13, r=0.03, label="VANILLA", sub="FLAVOR", fill=0.85, parent=None):
    """a little amber glass bottle of vanilla flavour with a black cap and a cream paper label, LABEL big on it, facing
    -Y. Returns (root, liquid): scale the liquid's Z from 0 to 1 and it fills."""
    root = K.empty(name, (0, 0, 0))
    amber = _mat("bottle amber", "#8A4A18", rough=0.08, trans=0.6, coat=0.6)
    liq = _mat("vanilla extract", "#3A1C0A", rough=0.15)
    cap = _mat("bottle cap", "#151515", rough=0.35)
    paper = _mat("bottle label", "#F3E7C8", rough=0.7); ink = _mat("bottle ink", "#3B2414", rough=0.5)
    K.cyl(f"{name} glass", (0, 0, h * 0.38), r, h * 0.76, amber, v=32, bev=0.006, parent=root)
    K.cyl(f"{name} neck", (0, 0, h * 0.82), r * 0.42, h * 0.14, amber, v=24, bev=0.002, parent=root)
    K.cyl(f"{name} cap", (0, 0, h * 0.94), r * 0.5, h * 0.12, cap, v=24, bev=0.003, parent=root)
    lp = K.empty(f"{name} liquid pivot", (0, 0, 0.003), parent=root)
    K.cyl(f"{name} liquid", (0, 0, 0.003 + h * 0.36 * fill), r * 0.9, h * 0.72 * fill, liq, v=24, bev=0.0, parent=lp)
    K.cyl(f"{name} label", (0, 0, h * 0.4), r * 1.012, h * 0.4, paper, v=32, bev=0.0, parent=root)
    K.text(f"{name} label word", label, (0, -r * 1.03, h * 0.43), r * 0.46, (math.radians(90), 0, 0), ink, extrude=0.0004, parent=root)
    if sub:
        K.text(f"{name} label sub", sub, (0, -r * 1.03, h * 0.33), r * 0.3, (math.radians(90), 0, 0), ink, extrude=0.0003, parent=root)
    root.location = loc
    if parent is not None: root.parent = parent
    return root, lp


def seed_mesh(name="vanilla seed"):
    me = bpy.data.meshes.get(name)
    if me: return me
    o = K.sph(name, (0, 0, -50), 0.0055, _mat("vanilla seed", "#120B07", rough=0.4), seg=8, ring=6)
    me = o.data; bpy.data.objects.remove(o)
    return me


def seeds(n, at, name="seed"):
    """n tiny black seeds (shared mesh), parked at `at`: pour them with props.pour"""
    me = seed_mesh(); out = []
    for i in range(n):
        o = bpy.data.objects.new(f"{name} {i}", me); bpy.context.collection.objects.link(o); o.location = at
        s = random.Random(i).uniform(0.8, 1.3); o.scale = (s, s, s); out.append(o)
    return out
