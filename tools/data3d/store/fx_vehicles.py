"""THE KIT'S VEHICLES: a car, a tipper truck and a digger, registered in store/fx_kit.py's REGISTRY (FX.car, FX.truck,
FX.digger). The board named a vehicle 24 times in the lava story's rounds ("plain white box shapes that look
untextured", "a small white shape") and Poly Haven has one car, parked under a tarp (FX.parked_car uses it): so
these are BUILT, to real proportions at the shorts' scale (a hatchback 2.4 m long beside Data's 0.95 m), from the
parts a vehicle is made of:

  * a body that is ONE lofted, smoothed shell (a nose, a bonnet, a raked windscreen, a roof, pillars, a tail), never
    a box on a box; wheel arches cut into it; coated paint with road dirt on its sills
  * glass that carries the sky; rubber tyres with rounded shoulders on dished metal rims
  * head lamps and tail lamps that are LIGHTS: a lit lens and the lamp it casts (spots forward, red behind)

Every one faces -Y about its origin and returns dict(root, objects, lights, ...). Nothing here renders.
"""
import math, random
try:
    import bpy, bmesh
    from mathutils import Vector, Euler
    import scene_kit as K
except ImportError:           # the registry and the brief are read without Blender
    bpy = None
import fx_kit as FX
from fx_kit import element, _link, vn

PAINTS = ("#D8D9D6", "#1F2A36", "#8E1B1B", "#6F7478", "#2F4A3A", "#C9B48A", "#101112", "#3E5F8A")   # white, navy, red, grey, green, sand, black, blue


# ---------------------------------------------------------------- materials
def paint_mat(col, name=None, dirt=0.5):
    """coated car paint: a base colour under a clear coat, with road dirt climbing from the sills (dirt 0..1)"""
    name = name or f"fx car paint {col} {dirt}"
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    bs.inputs["Metallic"].default_value = 0.25; bs.inputs["Coat Weight"].default_value = 0.8; bs.inputs["Coat Roughness"].default_value = 0.06
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    nz = N("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9.0; nz.inputs["Detail"].default_value = 5; L(tc.outputs["Object"], nz.inputs["Vector"])
    low = N("ShaderNodeMapRange"); low.inputs["From Min"].default_value = 0.55; low.inputs["From Max"].default_value = 0.08
    low.inputs["To Min"].default_value = 0.0; low.inputs["To Max"].default_value = 1.0; L(sep.outputs[2], low.inputs["Value"])
    d = N("ShaderNodeMath"); d.operation = 'MULTIPLY'; L(low.outputs["Result"], d.inputs[0]); L(nz.outputs["Fac"], d.inputs[1])
    d2 = N("ShaderNodeMath"); d2.operation = 'MULTIPLY'; d2.use_clamp = True; L(d.outputs[0], d2.inputs[0]); d2.inputs[1].default_value = 2.2 * dirt
    mix = N("ShaderNodeMixRGB"); L(d2.outputs[0], mix.inputs["Fac"]); mix.inputs["Color1"].default_value = (*K.lin(col), 1); mix.inputs["Color2"].default_value = (*K.lin("#4A4138"), 1)
    L(mix.outputs["Color"], bs.inputs["Base Color"])
    r = N("ShaderNodeMapRange"); r.inputs["To Min"].default_value = 0.28; r.inputs["To Max"].default_value = 0.85; L(d2.outputs[0], r.inputs["Value"])
    L(r.outputs["Result"], bs.inputs["Roughness"])
    cw = N("ShaderNodeMapRange"); cw.inputs["To Min"].default_value = 0.8; cw.inputs["To Max"].default_value = 0.0; L(d2.outputs[0], cw.inputs["Value"])
    L(cw.outputs["Result"], bs.inputs["Coat Weight"])
    return m


def _simple(name, col, rough=0.5, metal=0.0, coat=0.0, bump=0.0, bscale=40.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(col), 1); bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metal; bs.inputs["Coat Weight"].default_value = coat
    if bump:
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = bscale; nz.inputs["Detail"].default_value = 4
        bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = 0.01
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def glass_mat():
    """vehicle glass from outside: dark, mirror-smooth, carrying the sky (what a car window looks like from the street)"""
    return _simple("fx car glass", "#0B0F12", rough=0.03, metal=0.0, coat=1.0)


def rubber_mat(): return _simple("fx tyre rubber", "#0E0E0E", rough=0.82, bump=0.5, bscale=60.0)
def rim_mat(): return _simple("fx wheel rim", "#A9ADB1", rough=0.32, metal=1.0)
def dark_mat(): return _simple("fx car black trim", "#0D0D0E", rough=0.55)
def chrome_mat(): return _simple("fx car chrome", "#C8CACC", rough=0.15, metal=1.0)
def steel_mat(): return _simple("fx worn steel", "#5A5C5E", rough=0.45, metal=1.0, bump=0.3, bscale=30.0)


def lens_mat(kind, on):
    """a lamp's lens. Lit: emission kept low enough to hold its colour (a red above ~1.5 renders pink); the LAMP beside
    it does the lighting. Unlit: clear or red plastic over a reflector."""
    name = f"fx lens {kind} {'on' if on else 'off'}"
    m = bpy.data.materials.get(name)
    if m: return m
    col, strength = {"head": ("#FFF1D0", 6.0), "tail": ("#C80A00", 0.9), "amber": ("#FF8A00", 2.2), "work": ("#FFF4DC", 9.0)}[kind]
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    base = {"head": "#C9CDD0", "tail": "#5A0500", "amber": "#8A4A00", "work": "#C9CDD0"}[kind]
    bs.inputs["Base Color"].default_value = (*K.lin(base), 1); bs.inputs["Roughness"].default_value = 0.08; bs.inputs["Coat Weight"].default_value = 1.0
    bs.inputs["Metallic"].default_value = 0.6 if kind in ("head", "work") else 0.0
    if on:
        bs.inputs["Emission Color"].default_value = (*K.lin(col), 1); bs.inputs["Emission Strength"].default_value = strength
    return m


def body_metal(col, weather=0.3, seed=0):
    """painted plant steel (a digger's yellow, a tipper's body): thick industrial paint, satin, chipped to rust in
    patches and dulled by dust (smooth plate: the scanned painted metals in the library are all ribbed sheet)"""
    name = f"fx plant paint {col} {weather} {seed}"
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    tc = N("ShaderNodeTexCoord")
    mp = N("ShaderNodeMapping"); mp.inputs["Location"].default_value = (seed * 1.7, seed * 0.9, 0); L(tc.outputs["Object"], mp.inputs["Vector"])
    chips = N("ShaderNodeTexNoise"); chips.inputs["Scale"].default_value = 7.0; chips.inputs["Detail"].default_value = 8; chips.inputs["Roughness"].default_value = 0.7
    L(mp.outputs["Vector"], chips.inputs["Vector"])
    cm = N("ShaderNodeMapRange"); cm.inputs["From Min"].default_value = 0.68 - 0.12 * weather; cm.inputs["From Max"].default_value = 0.72 - 0.1 * weather; L(chips.outputs["Fac"], cm.inputs["Value"])
    dust = N("ShaderNodeTexNoise"); dust.inputs["Scale"].default_value = 2.2; dust.inputs["Detail"].default_value = 4; L(mp.outputs["Vector"], dust.inputs["Vector"])
    dm = N("ShaderNodeMapRange"); dm.inputs["From Min"].default_value = 0.35; dm.inputs["From Max"].default_value = 0.8; dm.inputs["To Max"].default_value = 0.5 * weather + 0.1; L(dust.outputs["Fac"], dm.inputs["Value"])
    m1 = N("ShaderNodeMixRGB"); L(dm.outputs["Result"], m1.inputs["Fac"]); m1.inputs["Color1"].default_value = (*K.lin(col), 1); m1.inputs["Color2"].default_value = (*K.lin("#6A6258"), 1)
    m2 = N("ShaderNodeMixRGB"); L(cm.outputs["Result"], m2.inputs["Fac"]); L(m1.outputs["Color"], m2.inputs["Color1"]); m2.inputs["Color2"].default_value = (*K.lin("#4A2A18"), 1)
    L(m2.outputs["Color"], bs.inputs["Base Color"])
    rr = N("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = 0.42; rr.inputs["To Max"].default_value = 0.85; L(cm.outputs["Result"], rr.inputs["Value"]); L(rr.outputs["Result"], bs.inputs["Roughness"])
    bp = N("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.25; bp.inputs["Distance"].default_value = 0.004; L(chips.outputs["Fac"], bp.inputs["Height"]); L(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


# ---------------------------------------------------------------- parts
def _spot(name, loc, aim, power, parent, size=75.0, col=(1.0, 0.95, 0.85), r=0.04):
    ld = bpy.data.lights.new(name, 'SPOT'); ld.energy = power; ld.color = col; ld.spot_size = math.radians(size); ld.spot_blend = 0.5; ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return K._link(o, parent)


def _lamp(name, loc, power, col, parent, r=0.04):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = power; ld.color = col; ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld); o.location = loc
    return K._link(o, parent)


def _beam(name, a, b, w, t, m, parent, bev=0.01):
    """a box member from a to b: w across (x), t deep"""
    a = Vector(a); b = Vector(b); d = b - a
    o = K.box(name, tuple((a + b) / 2), (w, d.length, t), m, bev=bev, parent=parent)
    o.rotation_euler = d.to_track_quat('Y', 'Z').to_euler()
    return o


def wheel(name, loc, r, width, parent, side=1, hub="#A9ADB1", steel=False):
    """a wheel standing on the x axis at loc: a rubber tyre with rounded shoulders and a tread, a dished rim with
    spokes (or a plain steel disc with holes for a truck), a hub. side: +1 its face looks to +x."""
    rot = (0, math.pi / 2, 0); objs = []
    tyre = K.cyl(name + " tyre", loc, r, width, rubber_mat(), rot=rot, v=40, bev=min(width * 0.32, r * 0.22), parent=parent)
    tyre.modifiers["bevel"].segments = 5
    objs.append(tyre)
    x = loc[0] + side * (width / 2 - 0.012)
    rim = rim_mat() if hub == "#A9ADB1" else _simple(f"fx wheel rim {hub}", hub, rough=0.4, metal=0.6)
    objs.append(K.cyl(name + " rim well", (x - side * 0.004, loc[1], loc[2]), r * 0.66, 0.02, dark_mat(), rot=rot, v=32, bev=0.0, parent=parent))
    objs.append(K.cyl(name + " rim lip", (x, loc[1], loc[2]), r * 0.68, 0.018, rim, rot=rot, v=40, bev=0.004, parent=parent))
    objs.append(K.cyl(name + " rim dish", (x + side * 0.004, loc[1], loc[2]), r * 0.6, 0.014, dark_mat() if not steel else rim, rot=rot, v=32, bev=0.0, parent=parent))
    n = 6 if steel else 5
    for k in range(n):
        a = 2 * math.pi * k / n + 0.3
        if steel:
            objs.append(K.cyl(name + " rim hole", (x + side * 0.012, loc[1] + math.cos(a) * r * 0.4, loc[2] + math.sin(a) * r * 0.4), r * 0.08, 0.004, dark_mat(), rot=rot, v=12, bev=0.0, parent=parent))
        else:
            sp = K.box(name + " spoke", (x + side * 0.012, loc[1] + math.cos(a) * r * 0.31, loc[2] + math.sin(a) * r * 0.31), (0.014, r * 0.56, r * 0.15), rim, bev=0.004, parent=parent)
            sp.rotation_euler = (a, 0, 0); objs.append(sp)
    objs.append(K.cyl(name + " hub", (x + side * 0.018, loc[1], loc[2]), r * 0.17, 0.02, rim, rot=rot, v=16, bev=0.004, parent=parent))
    return objs


def _shell(name, st, m_paint, m_glass, parent, arches=(), arch_r=0.0, sub=2):
    """THE BODY: one shell lofted through cross-sections from nose to tail and smoothed. st: stations
    (y, zb, zs, zr, wb, ws, wr, kind): floor, belt line and top heights; half-widths at the sill, the belt and the
    top; kind of the span to the NEXT station: 'b' body, 'g' side glass, 's' a raked screen (its top is glass),
    'p' a pillar. arches: (y, z) of the wheels: an arch is cut for each, right through."""
    bm = bmesh.new(); rings = []
    for (y, zb, zs, zr, wb, ws, wr, _) in st:
        top = max(zr, zs + 0.03)
        half = [(0.0, zb), (wb * 0.78, zb), (wb, zb + 0.07), (ws, zb + (zs - zb) * 0.55), (ws, zs), (wr, top - 0.035), (wr * 0.7, top), (0.0, top)]
        pts = half + [(-x, z) for (x, z) in reversed(half[1:-1])]
        rings.append([bm.verts.new((x, y, z)) for (x, z) in pts])
    n = len(rings[0]); glass_faces = []
    for i in range(len(rings) - 1):
        kind = st[i][7]
        for k in range(n):
            j = (k + 1) % n
            f = bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
            kk = min(k, n - 1 - k) if k < 7 else n - 1 - k               # mirror index: 0..6 on the right, back down on the left
            seg = k if k < 7 else (n - 1 - k)                             # 4 = belt-to-top side band; 5, 6 = the top
            if (kind == 'g' and seg == 4) or (kind == 's' and seg in (5, 6)):
                glass_faces.append(f)
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cr = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    for i, ring in enumerate(rings):                                      # keep the ends and the glass lines from melting
        for k in range(n):
            e = bm.edges.get((ring[k], ring[(k + 1) % n]))
            if e is not None: e[cr] = 0.75 if i in (0, len(rings) - 1) else 0.3
    for f in glass_faces:
        f.material_index = 1
        for e in f.edges: e[cr] = max(e[cr], 0.55)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(m_paint); me.materials.append(m_glass); me.materials.append(dark_mat())
    o = K._link(bpy.data.objects.new(name, me), parent)
    sd = o.modifiers.new("smooth", 'SUBSURF'); sd.levels = sub; sd.render_levels = sub
    for k, (y, z) in enumerate(arches):
        c = K.cyl(f"{name} arch cutter {k}", (0, y, z), arch_r, 4.0, dark_mat(), rot=(0, math.pi / 2, 0), v=40, bev=0.0, parent=parent)
        c.hide_render = True; c.hide_viewport = True; c.display_type = 'WIRE'
        bo = o.modifiers.new(f"arch {k}", 'BOOLEAN'); bo.operation = 'DIFFERENCE'; bo.object = c
        try: bo.solver = 'EXACT'; bo.material_mode = 'TRANSFER'
        except Exception: pass
    return o


CARS = {
    # y from the nose (-L/2) to the tail, as fractions of the half length; heights as fractions of H; widths of W/2
    "hatch":  dict(L=2.4, W=1.0, H=0.86, wheel=0.19, axles=(-0.66, 0.68), prof=(
        (-1.00, .26, .50, .54, .78, .84, .76, 'b'), (-0.93, .15, .55, .61, .94, .98, .90, 'b'), (-0.50, .13, .65, .70, .98, 1.0, .92, 's'),
        (-0.17, .13, .68, .99, .98, 1.0, .80, 'g'), (0.10, .13, .68, 1.0, .98, 1.0, .80, 'p'), (0.15, .13, .68, 1.0, .98, 1.0, .80, 'g'),
        (0.60, .13, .68, .99, .98, 1.0, .80, 'p'), (0.68, .13, .68, .98, .98, 1.0, .80, 's'), (0.93, .15, .68, .74, .96, .98, .88, 'b'),
        (1.00, .24, .58, .64, .82, .86, .78, 'b'))),
    "suv":    dict(L=2.6, W=1.06, H=1.0, wheel=0.22, axles=(-0.64, 0.66), prof=(
        (-1.00, .30, .52, .56, .80, .86, .78, 'b'), (-0.93, .20, .58, .64, .95, .98, .90, 'b'), (-0.52, .18, .64, .68, .98, 1.0, .93, 's'),
        (-0.25, .18, .66, .99, .98, 1.0, .84, 'g'), (0.08, .18, .66, 1.0, .98, 1.0, .84, 'p'), (0.13, .18, .66, 1.0, .98, 1.0, .84, 'g'),
        (0.52, .18, .66, 1.0, .98, 1.0, .84, 'p'), (0.57, .18, .66, 1.0, .98, 1.0, .84, 'g'), (0.86, .18, .66, .99, .98, 1.0, .84, 's'),
        (0.96, .20, .66, .72, .97, .99, .90, 'b'), (1.00, .28, .58, .64, .84, .88, .80, 'b'))),
    "van":    dict(L=2.9, W=1.1, H=1.25, wheel=0.2, axles=(-0.68, 0.62), prof=(
        (-1.00, .24, .42, .46, .82, .88, .80, 'b'), (-0.94, .15, .46, .52, .95, .98, .90, 'b'), (-0.74, .13, .52, .56, .98, 1.0, .93, 's'),
        (-0.58, .13, .54, .98, .98, 1.0, .88, 'g'), (-0.30, .13, .54, 1.0, .98, 1.0, .88, 'p'), (-0.26, .13, .54, 1.0, .98, 1.0, .90, 'b'),
        (0.94, .13, .54, 1.0, .98, 1.0, .90, 'b'), (1.00, .20, .54, .97, .94, .96, .86, 'b'))),
    "pickup": dict(L=2.9, W=1.06, H=0.98, wheel=0.22, axles=(-0.66, 0.62), prof=(
        (-1.00, .30, .52, .56, .80, .86, .78, 'b'), (-0.93, .20, .58, .64, .95, .98, .90, 'b'), (-0.55, .18, .64, .68, .98, 1.0, .93, 's'),
        (-0.30, .18, .66, .99, .98, 1.0, .84, 'g'), (0.02, .18, .66, 1.0, .98, 1.0, .84, 'p'), (0.07, .18, .66, 1.0, .98, 1.0, .84, 's'),
        (0.16, .18, .64, .68, .98, 1.0, .96, 'b'), (0.96, .18, .64, .68, .98, 1.0, .96, 'b'), (1.00, .26, .60, .64, .92, .95, .90, 'b'))),
}


def _place(root, loc, yaw):
    root.location = tuple(loc); root.rotation_euler = (0, 0, yaw)
    return root


@element("vehicle", "a real car (kinds: hatch, suv, van, pickup): one smooth lofted body with a bonnet, a raked "
                    "windscreen, pillars and wheel arches, coated paint with road dirt, glass that carries the sky, "
                    "rubber tyres on spoked rims, mirrors, shut lines, plates; head and tail lamps that are lit lenses "
                    "AND the lamps they cast (spots on the road ahead, red behind)")
def car(name="car", loc=(0, 0, 0), yaw=0.0, kind="hatch", col=None, lights=True, seed=0, dirt=0.5, brake=False, power=70.0):
    """a car at the shorts' scale, facing -Y about its origin (yaw turns it; yaw=math.pi drives it away up +Y).
    col: paint hex (default by seed from PAINTS). lights: head and tail lamps on (False: parked, dark lenses).
    brake: tail lamps at brake brightness. power: watts of each head lamp's spot (70 reads in daylight without
    bleaching the road; 250 and up for dusk and night). To drive it, key root.location.
    Returns dict(root, body, wheels, head, tail, L, W, H)."""
    c = CARS[kind]; rnd = random.Random(seed * 131 + 7); L, W, H = c["L"], c["W"], c["H"]; wr = c["wheel"]
    col = col or PAINTS[rnd.randrange(len(PAINTS))]
    root = K.empty(name, (0, 0, 0)); paint = paint_mat(col, dirt=dirt); glass = glass_mat(); dark = dark_mat(); chrome = chrome_mat()
    st = [(y * L / 2, zb * H, zs * H, zr * H, wb * W / 2, ws * W / 2, wt * W / 2, kd) for (y, zb, zs, zr, wb, ws, wt, kd) in c["prof"]]
    ay = [a * L / 2 for a in c["axles"]]
    body = _shell(name + " body", st, paint, glass, root, arches=[(y, wr * 1.02) for y in ay], arch_r=wr * 1.2)
    wheels = []
    for y in ay:
        for sx in (-1, 1):
            wheels += wheel(f"{name} wheel", (sx * (W / 2 - wr * 0.42), y, wr), wr, wr * 0.8, root, side=sx)
        K.box(name + " axle shadow", (0, y, wr * 1.05), (W * 0.78, wr * 2.3, wr * 1.5), dark, bev=0.02, parent=root)   # the dark of the wheel well: no daylight through the arches
    K.box(name + " underside", (0, 0, H * 0.16), (W * 0.8, L * 0.86, 0.08), dark, bev=0.02, parent=root)
    nose, tail = -L / 2, L / 2
    zh = st[1][3] - 0.07 * H; zt = st[-2][2] - 0.06 * H
    lights_out = []; head = []; tails = []
    for sx in (-1, 1):
        hl = K.box(name + " head lamp", (sx * W * 0.33, nose + 0.035, zh), (W * 0.2, 0.05, H * 0.085), lens_mat("head", lights), bev=0.018, parent=root)
        hl.rotation_euler = (0, 0, -sx * 0.22); head.append(hl)
        tl = K.box(name + " tail lamp", (sx * W * 0.37, tail - 0.03, zt), (W * 0.16, 0.05, H * 0.12), lens_mat("tail", lights), bev=0.016, parent=root)
        tl.rotation_euler = (0, 0, sx * 0.2); tails.append(tl)
        if lights:
            lights_out.append(_spot(name + " head beam", (sx * W * 0.33, nose - 0.03, zh), (sx * W * 0.33, nose - 4.0, -0.2), power, root))
            lights_out.append(_lamp(name + " tail glow", (sx * W * 0.37, tail + 0.08, zt), 6.0 if brake else 1.5, (1.0, 0.06, 0.03), root))
        # mirrors, the shut lines of the doors, handles
        my = st[3][0] + 0.02 * L
        K.box(name + " mirror", (sx * (W / 2 + 0.045), my, st[3][2] + 0.03), (0.09, 0.05, 0.06), paint, bev=0.018, parent=root)
        K.box(name + " mirror glass", (sx * (W / 2 + 0.045), my + 0.027, st[3][2] + 0.03), (0.07, 0.004, 0.045), chrome, bev=0.0, parent=root)
        zdoor = (st[3][1] + st[3][2]) / 2 + 0.03
        doors = [s_[0] for s_ in st if s_[7] in ('g', 'p') or s_ is st[3]]
        ys = sorted({round(st[3][0] - 0.03 * L, 3), round((doors[0] + doors[-1]) / 2 + 0.06, 3), round(doors[-1] + 0.05 * L, 3)})
        for y in ys:
            K.box(name + " shut line", (sx * (W / 2 - 0.006), y, zdoor), (0.012, 0.007, (st[3][2] - st[3][1]) * 0.82), dark, bev=0.0, parent=root)
        for y in ys[1:]:
            K.box(name + " door handle", (sx * (W / 2 - 0.002), y - 0.09, st[3][2] - 0.05), (0.014, 0.09, 0.02), chrome if kind != "van" else dark, bev=0.005, parent=root)
        K.box(name + " sill", (sx * (W / 2 - 0.02), 0, st[3][1] + 0.035), (0.03, (ay[1] - ay[0]) - wr * 2.5, 0.05), dark, bev=0.01, parent=root)
    # the face: a grille, bumpers, plates, wipers
    K.box(name + " grille", (0, nose + 0.012, zh - 0.005), (W * 0.36, 0.03, H * 0.06), dark, bev=0.008, parent=root)
    K.box(name + " air dam", (0, nose + 0.03, st[1][1] + 0.07), (W * 0.62, 0.05, H * 0.09), dark, bev=0.015, parent=root)
    K.box(name + " front bumper", (0, nose + 0.02, st[1][1] + 0.16), (W * 0.9, 0.06, H * 0.05), paint, bev=0.02, parent=root)
    K.box(name + " rear bumper", (0, tail - 0.02, st[-2][1] + 0.1), (W * 0.9, 0.07, H * 0.11), dark, bev=0.02, parent=root)
    plate = _simple("fx number plate", "#E6E3D8", rough=0.5)
    K.box(name + " plate", (0, nose - 0.012, st[1][1] + 0.1), (0.26, 0.008, 0.062), plate, bev=0.003, parent=root)
    K.box(name + " plate", (0, tail + 0.018, zt - 0.11 * H), (0.26, 0.008, 0.062), plate, bev=0.003, parent=root)
    sy0, sy1 = st[2][0], st[3][0]; sz0, sz1 = st[2][3], st[3][3]; rake = math.atan2(sz1 - sz0, sy1 - sy0)
    for sx in (-0.2, 0.18):
        wp = K.box(name + " wiper", (sx * W, sy0 + 0.07 * (sy1 - sy0) + 0.012, sz0 + 0.07 * (sz1 - sz0) + 0.02), (W * 0.3, 0.01, 0.01), dark, bev=0.0, parent=root)
        wp.rotation_euler = (rake, 0, 0.12)
    _place(root, loc, yaw)
    objs = [o for o in root.children_recursive if o.type == 'MESH']
    return dict(objects=[root] + objs, lights=lights_out, root=root, body=body, wheels=wheels, head=head, tail=tails, L=L, W=W, H=H, kind=kind)


@element("vehicle", "the one REAL car in the asset library: a scanned car parked under a tarpaulin (a prop for a "
                    "drive or a yard; it has no lamps and does not drive). Falls back to FX.car when it is not unpacked")
def parked_car(name="covered car", loc=(0, 0, 0), yaw=0.0, length=2.4):
    if not FX.have("covered_car", "covered_car_1k.gltf"):
        print("FX FALLBACK covered_car is not unpacked: using FX.car(lights=False)", flush=True)
        return car.__wrapped__(name, loc, yaw, lights=False)
    root = FX.ph_model("covered_car", loc, rot=(0, 0, yaw), name=name)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in root.children_recursive if o.type == 'MESH' for c in o.bound_box]
    span = max(max(p.x for p in pts) - min(p.x for p in pts), max(p.y for p in pts) - min(p.y for p in pts))
    k = length / max(span, 1e-3); root.scale = (k, k, k)
    root.location = (loc[0], loc[1], loc[2] - min(p.z for p in pts) * k + loc[2] * 0)
    return dict(objects=[root] + [o for o in root.children_recursive if o.type == 'MESH'], lights=[], root=root)


@element("vehicle", "a tipper truck: a cab-over cab (lofted, glazed, mirrors on arms), a steel chassis, six wheels on "
                    "steel rims, a ribbed tipper body of worn painted steel that can be raised and loaded with rock; "
                    "head, tail and amber marker lamps that light")
def truck(name="truck", loc=(0, 0, 0), yaw=0.0, col="#C8CACB", body_col="#B5651D", tip=0.0, load=0.0, lights=True, seed=0, power=90.0):
    """a tipper truck at the shorts' scale (3.7 long, 1.3 wide, 1.75 high), facing -Y. tip: degrees the body is
    raised. load (0..1): how full of broken rock it is. Returns dict(root, cab, bed, wheels, hinge)."""
    L, W = 3.7, 1.3; wr = 0.27; rnd = random.Random(seed * 17 + 3)
    root = K.empty(name, (0, 0, 0)); paint = paint_mat(col, dirt=0.7); glass = glass_mat(); dark = dark_mat(); steel = steel_mat()
    nose = -L / 2; cabL = 1.05; H = 1.75; zc0 = 0.42
    st = [(nose + y * cabL, zc0 + zb, zc0 + zs, zc0 + zr, wb * W / 2, ws * W / 2, wt * W / 2, kd) for (y, zb, zs, zr, wb, ws, wt, kd) in (
        (0.00, .10, .50, .56, .86, .90, .84, 'b'), (0.06, .00, .58, .64, .96, .98, .90, 's'), (0.20, .00, .62, 1.26, .98, 1.0, .88, 'g'),
        (0.62, .00, .62, 1.33, .98, 1.0, .90, 'p'), (0.68, .00, .62, 1.33, .98, 1.0, .92, 'b'), (0.96, .00, .62, 1.33, .98, 1.0, .92, 'b'), (1.00, .04, .62, 1.30, .94, .96, .88, 'b'))]
    cab = _shell(name + " cab", st, paint, glass, root, arches=[(nose + 0.55, wr)], arch_r=wr * 1.22)
    ax = (nose + 0.55, L / 2 - 1.25, L / 2 - 0.62); wheels = []
    for i, y in enumerate(ax):
        for sx in (-1, 1):
            wheels += wheel(f"{name} wheel", (sx * (W / 2 - wr * 0.38), y, wr), wr, wr * 0.72 if i == 0 else wr * 1.15, root, side=sx, steel=True)
        K.cyl(name + " axle", (0, y, wr), 0.05, W * 0.8, steel, rot=(0, math.pi / 2, 0), v=12, parent=root)
    for sx in (-1, 1):
        K.box(name + " chassis rail", (sx * 0.24, 0.3, 0.52), (0.07, L - 0.5, 0.13), dark, bev=0.01, parent=root)
        K.box(name + " rear mudguard", (sx * (W / 2 - 0.16), (ax[1] + ax[2]) / 2, wr * 2 + 0.07), (0.3, 1.25, 0.03), dark, bev=0.01, parent=root)
        K.box(name + " tank", (sx * 0.46, nose + cabL + 0.5, 0.42), (0.26, 0.5, 0.26), steel, bev=0.06, parent=root)
        K.box(name + " step", (sx * (W / 2 - 0.05), nose + 0.42, 0.34), (0.1, 0.3, 0.03), steel, bev=0.006, parent=root)
        arm = K.box(name + " mirror arm", (sx * (W / 2 + 0.06), nose + 0.2, zc0 + 0.95), (0.12, 0.015, 0.015), dark, bev=0.0, parent=root)
        K.box(name + " mirror", (sx * (W / 2 + 0.12), nose + 0.2, zc0 + 0.95), (0.03, 0.05, 0.22), dark, bev=0.01, parent=root)
        K.box(name + " door line", (sx * (W / 2 - 0.006), nose + 0.66, zc0 + 0.32), (0.012, 0.007, 0.56), dark, bev=0.0, parent=root)
        K.box(name + " door handle", (sx * (W / 2 - 0.002), nose + 0.58, zc0 + 0.5), (0.014, 0.08, 0.02), dark, bev=0.004, parent=root)
    K.box(name + " axle shadow", (0, nose + 0.55, wr), (W * 0.7, wr * 2.2, wr * 1.6), dark, bev=0.02, parent=root)
    K.box(name + " grille", (0, nose + 0.012, zc0 + 0.3), (W * 0.62, 0.03, 0.26), dark, bev=0.01, parent=root)
    for k in range(4):
        K.box(name + " grille bar", (0, nose - 0.004, zc0 + 0.2 + k * 0.065), (W * 0.58, 0.01, 0.018), chrome_mat(), bev=0.003, parent=root)
    K.box(name + " bumper", (0, nose + 0.01, zc0 + 0.03), (W * 0.98, 0.09, 0.16), steel, bev=0.02, parent=root)
    K.box(name + " plate", (0, nose - 0.04, zc0 + 0.03), (0.28, 0.008, 0.065), _simple("fx number plate", "#E6E3D8", rough=0.5), bev=0.003, parent=root)
    K.box(name + " sun visor", (0, nose + 0.1, zc0 + 1.27), (W * 0.9, 0.16, 0.025), dark, bev=0.008, parent=root)
    K.cyl(name + " exhaust stack", (W * 0.36, nose + cabL + 0.09, 1.35), 0.035, 1.5, steel, v=14, parent=root)
    lights_out = []; head = []; tails = []
    for sx in (-1, 1):
        head.append(K.box(name + " head lamp", (sx * W * 0.36, nose + 0.02, zc0 + 0.03), (0.17, 0.06, 0.09), lens_mat("head", lights), bev=0.015, parent=root))
        tails.append(K.box(name + " tail lamp", (sx * W * 0.4, L / 2 - 0.02, 0.62), (0.13, 0.04, 0.08), lens_mat("tail", lights), bev=0.01, parent=root))
        K.box(name + " marker", (sx * W * 0.4, nose + 0.12, zc0 + 1.35), (0.06, 0.03, 0.03), lens_mat("amber", lights), bev=0.006, parent=root)
        if lights:
            lights_out.append(_spot(name + " head beam", (sx * W * 0.36, nose - 0.04, zc0 + 0.03), (sx * W * 0.36, nose - 5.0, -0.2), power, root))
            lights_out.append(_lamp(name + " tail glow", (sx * W * 0.4, L / 2 + 0.07, 0.62), 4.0, (1.0, 0.06, 0.03), root))
    # the tipper body: a steel tub on a hinge at the tail, ribbed, with a cab guard
    y0 = nose + cabL + 0.12; y1 = L / 2 - 0.02; bl = y1 - y0; bz = 0.66; bh = 0.62; bw = W * 0.98
    hinge = K.empty(name + " tipper hinge", (0, y1 - 0.25, bz), parent=root)
    bm_ = body_metal(body_col, weather=0.4, seed=seed); bed = []
    yc = (y0 + y1) / 2
    bed.append(K.box(name + " tipper floor", (0, yc, bz + 0.03), (bw, bl, 0.06), bm_, bev=0.008, parent=hinge))
    for sx in (-1, 1):
        bed.append(K.box(name + " tipper side", (sx * (bw / 2 - 0.02), yc, bz + bh / 2), (0.04, bl, bh), bm_, bev=0.008, parent=hinge))
        for k in range(6):
            yy = y0 + bl * (k + 0.5) / 6
            bed.append(K.box(name + " tipper rib", (sx * (bw / 2 + 0.01), yy, bz + bh / 2), (0.04, 0.05, bh * 0.96), bm_, bev=0.008, parent=hinge))
        bed.append(K.box(name + " tipper rail", (sx * (bw / 2), yc, bz + bh), (0.07, bl + 0.04, 0.05), bm_, bev=0.01, parent=hinge))
    bed.append(K.box(name + " tipper front", (0, y0 + 0.02, bz + bh / 2 + 0.08), (bw, 0.04, bh + 0.16), bm_, bev=0.008, parent=hinge))
    bed.append(K.box(name + " cab guard", (0, y0 - 0.2, bz + bh + 0.14), (bw, 0.48, 0.04), bm_, bev=0.008, parent=hinge))
    tg = K.box(name + " tailgate", (0, y1 - 0.02, bz + bh / 2), (bw, 0.04, bh), bm_, bev=0.008, parent=hinge); bed.append(tg)
    for k in range(3):
        bed.append(K.box(name + " tailgate rib", ((k - 1) * bw * 0.3, y1 + 0.005, bz + bh / 2), (0.05, 0.03, bh * 0.9), bm_, bev=0.006, parent=hinge))
    if load > 0:
        rock = FX.ph_mat("gray_rocks", scale=0.7, tint="#5A5652", name="fx truck load rock") if FX.have("gray_rocks", "textures") else _simple("fx truck load rock", "#4A4744", rough=0.9)
        for k in range(int(70 * load) + 20):
            x = rnd.uniform(-0.42, 0.42) * bw; y = rnd.uniform(y0 + 0.12, y1 - 0.12); s = rnd.uniform(0.07, 0.15)
            hump = (1 - (2 * x / bw) ** 2) * (1 - ((y - yc) / (bl / 2)) ** 2)
            b = FX.block(name + " load", (x, y, bz + 0.08 + load * bh * (0.45 + 0.75 * hump) * rnd.uniform(0.55, 1.0)), s, rock, rnd)
            b.parent = hinge; b.matrix_parent_inverse = hinge.matrix_basis.inverted(); bed.append(b)
    ram0 = Vector((0, y0 + 0.5, 0.56)); K.cyl(name + " tipping ram", tuple(ram0 + Vector((0, 0, 0.05))), 0.05, 0.3, steel, v=14, parent=root)
    hinge.rotation_euler = (math.radians(tip), 0, 0)
    if tip > 1:
        bpy.context.view_layer.update()
        top = hinge.matrix_world @ (Vector((0, y0 + 0.5, bz)) - Vector(hinge.location))
        K.capsule(name + " tipping ram rod", tuple(ram0), tuple(top), 0.028, chrome_mat(), parent=root)
    _place(root, loc, yaw)
    objs = [o for o in root.children_recursive if o.type == 'MESH']
    return dict(objects=[root] + objs, lights=lights_out, root=root, cab=cab, bed=bed, hinge=hinge, wheels=wheels, head=head, tail=tails, L=L, W=W, H=H)


def _bucket(name, pivot, ang, width, size, m, m_teeth, parent):
    """an excavator bucket: a curved scoop (an arc of plate between two side plates) with teeth on its lip.
    pivot: its hinge (top back); ang: its curl about x (0 = mouth forward, -Y)."""
    hold = K.empty(name, tuple(pivot), parent=parent)
    bm = bmesh.new(); n = 9; R = size; t = 0.02; verts = []
    for k in range(n + 1):
        a = math.radians(95 + 190 * k / n)                                # the scoop's back: an arc in the y-z plane
        y, z = -R * 0.55 + R * 0.62 * math.cos(a) * 1.1, -R * 0.55 + R * 0.62 * math.sin(a)
        verts.append((y, z))
    for sx in (-1, 1):
        for (y, z) in verts: bm.verts.new((sx * width / 2, y, z))
    bm.verts.ensure_lookup_table()
    for k in range(n):
        bm.faces.new((bm.verts[k], bm.verts[k + 1], bm.verts[n + 1 + k + 1], bm.verts[n + 1 + k]))
    for off in (0, n + 1):
        bm.faces.new([bm.verts[off + k] for k in range(n + 1)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + " scoop"); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name + " scoop", me); o.location = tuple(pivot)
    sol = o.modifiers.new("plate", 'SOLIDIFY'); sol.thickness = t * 1.5; sol.offset = 0
    bv = o.modifiers.new("bevel", 'BEVEL'); bv.width = 0.006; bv.segments = 2
    K._link(o, hold)
    ly, lz = verts[-1]
    P = Vector(pivot)
    for k in range(4):
        x = (k - 1.5) * width / 4
        th = K.box(name + " tooth", (P.x + x, P.y + ly - 0.035, P.z + lz + 0.005), (width * 0.11, 0.1, 0.028), m_teeth, bev=0.008, parent=hold)
        th.rotation_euler = (0.25, 0, 0)
    for sx in (-1, 1):
        K.box(name + " ear", (P.x + sx * width * 0.2, P.y - 0.02, P.z - 0.02), (0.03, 0.14, 0.12), m, bev=0.01, parent=hold)
    hold.rotation_euler = (ang, 0, 0)
    return hold


@element("vehicle", "a digger (a tracked excavator): two steel tracks with pads, rollers and sprockets, a slewing "
                    "house of worn yellow painted steel with a counterweight and an engine cover, a glazed cab, and a "
                    "boom, stick and toothed bucket on chromed hydraulic rams that pose by angle; work lamps that light")
def digger(name="digger", loc=(0, 0, 0), yaw=0.0, slew=0.0, boom=38.0, stick=-95.0, bucket=-40.0, col="#E3A008", lights=True, seed=0, power=80.0):
    """a tracked excavator at the shorts' scale (tracks 2.3 long, 1.5 wide over all, cab roof at 1.6), facing -Y.
    slew: degrees the house is turned on its tracks. boom: degrees the boom rises from level. stick: degrees the
    stick hangs from the boom's line (negative folds it down and in). bucket: its curl. To animate, key
    out['house'].rotation_euler[2], and rebuild or parent for the arm. Returns dict(root, house, cab, bucket, tip)."""
    root = K.empty(name, (0, 0, 0)); yel = body_metal(col, weather=0.35, seed=seed); dark = dark_mat(); steel = steel_mat(); glass = glass_mat(); chrome = chrome_mat()
    rub = _simple("fx track steel", "#2A2B2C", rough=0.6, metal=0.7, bump=0.4, bscale=25.0)
    TL, TW, TH = 2.3, 0.34, 0.5; gauge = 0.58
    for sx in (-1, 1):
        x = sx * gauge
        K.box(name + " track", (x, 0, TH / 2), (TW, TL, TH), rub, bev=TH * 0.47, parent=root)
        K.box(name + " track frame", (x - sx * 0.0, 0, TH / 2), (TW * 0.7, TL * 0.72, TH * 0.42), yel, bev=0.02, parent=root)
        n = 26
        for k in range(n):                                               # the pads: across the belt, top and bottom runs and round the ends
            u = k / n * 2 * (TL - TH + math.pi * TH / 2)
            run = TL - TH; arc = math.pi * TH / 2
            if u < run: y, z, a = -run / 2 + u, 0.0, 0.0
            elif u < run + arc: th = (u - run) / (TH / 2); y, z, a = run / 2 + TH / 2 * math.sin(th), TH / 2 - TH / 2 * math.cos(th), th
            elif u < 2 * run + arc: y, z, a = run / 2 - (u - run - arc), TH, math.pi
            else: th = (u - 2 * run - arc) / (TH / 2); y, z, a = -run / 2 - TH / 2 * math.sin(th), TH / 2 + TH / 2 * math.cos(th), math.pi + th
            pad = K.box(name + " track pad", (x, y, z), (TW * 1.04, 0.075, 0.022), rub, bev=0.005, parent=root); pad.rotation_euler = (a, 0, 0)
        for y in (-(TL - TH) / 2, (TL - TH) / 2):
            K.cyl(name + " sprocket", (x + sx * TW * 0.36, y, TH / 2), TH * 0.33, 0.04, steel, rot=(0, math.pi / 2, 0), v=20, parent=root)
        for k in range(5):
            K.cyl(name + " roller", (x + sx * TW * 0.36, -0.6 + k * 0.3, 0.11), 0.06, 0.04, steel, rot=(0, math.pi / 2, 0), v=14, parent=root)
    K.box(name + " car body", (0, 0, TH * 0.62), (gauge * 2, 0.9, 0.22), yel, bev=0.03, parent=root)
    K.cyl(name + " slew ring", (0, 0, TH + 0.04), 0.42, 0.1, steel, v=32, parent=root)
    house = K.empty(name + " house", (0, 0, TH + 0.09), parent=root); hz = TH + 0.09
    K.box(name + " deck", (0, 0.22, hz + 0.06), (1.36, 1.7, 0.12), yel, bev=0.03, parent=house)
    K.box(name + " engine cover", (0.14, 0.62, hz + 0.37), (1.0, 0.8, 0.5), yel, bev=0.06, parent=house)
    K.box(name + " counterweight", (0, 1.08, hz + 0.3), (1.34, 0.3, 0.52), _simple("fx digger counterweight", "#2B2C2D", rough=0.6, bump=0.3), bev=0.1, parent=house)
    for k in range(5):
        K.box(name + " engine louvre", (0.645, 0.4 + k * 0.1, hz + 0.42), (0.01, 0.06, 0.26), dark, bev=0.0, parent=house)
    K.cyl(name + " exhaust", (0.42, 0.75, hz + 0.75), 0.035, 0.3, steel, v=12, parent=house)
    K.box(name + " hand rail", (0.6, 0.3, hz + 0.75), (0.02, 0.9, 0.02), dark, bev=0.005, parent=house)
    for y in (-0.14, 0.74):
        K.box(name + " hand rail post", (0.6, y, hz + 0.68), (0.02, 0.02, 0.14), dark, bev=0.005, parent=house)
    # the cab: a steel frame with glass on four sides, on the left
    cx, cy, cw, cd, ch = -0.4, -0.3, 0.52, 0.86, 0.92; cz = hz + 0.12
    cab = []
    cab.append(K.box(name + " cab floor", (cx, cy, cz + 0.04), (cw, cd, 0.08), yel, bev=0.02, parent=house))
    cab.append(K.box(name + " cab roof", (cx, cy, cz + ch), (cw + 0.03, cd + 0.03, 0.06), yel, bev=0.025, parent=house))
    cab.append(K.box(name + " cab sill", (cx, cy, cz + 0.22), (cw, cd, 0.3), yel, bev=0.02, parent=house))
    for (px, py) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cab.append(K.box(name + " cab post", (cx + px * (cw / 2 - 0.02), cy + py * (cd / 2 - 0.02), cz + ch / 2 + 0.16), (0.045, 0.045, ch - 0.34), yel, bev=0.012, parent=house))
    cab.append(K.box(name + " cab glass", (cx, cy, cz + 0.37 + (ch - 0.4) / 2), (cw - 0.03, cd - 0.03, ch - 0.42), glass, bev=0.004, parent=house))
    cab.append(K.box(name + " cab door bar", (cx - cw / 2 - 0.004, cy + 0.02, cz + 0.6), (0.012, 0.03, ch - 0.5), yel, bev=0.004, parent=house))
    # the arm
    A = Vector((0.16, -0.5, hz + 0.3)); b1 = math.radians(boom); L1, L2 = 1.75, 1.05
    K.box(name + " boom foot", tuple(A + Vector((0, 0.04, -0.08))), (0.3, 0.3, 0.3), yel, bev=0.04, parent=house)
    d1 = Vector((0, -math.cos(b1), math.sin(b1))); n1 = Vector((0, math.sin(b1), math.cos(b1)))
    K_ = A + d1 * (L1 * 0.5) + n1 * 0.2                                    # the boom is a dog-leg: a knee above its line
    B = A + d1 * L1
    _beam(name + " boom lower", A, K_, 0.2, 0.26, yel, house, bev=0.03); _beam(name + " boom upper", K_, B, 0.18, 0.22, yel, house, bev=0.03)
    K.cyl(name + " boom knee", tuple(K_), 0.15, 0.2, yel, rot=(0, math.pi / 2, 0), v=20, parent=house)
    b2 = b1 + math.radians(stick); d2 = Vector((0, -math.cos(b2), math.sin(b2)))
    S0 = B - d2 * 0.28; C = B + d2 * L2
    _beam(name + " stick", S0, C, 0.15, 0.18, yel, house, bev=0.025)
    K.cyl(name + " stick pin", tuple(B), 0.07, 0.24, steel, rot=(0, math.pi / 2, 0), v=16, parent=house)

    def ram(nm, a, b, r=0.045):
        a = Vector(a); b = Vector(b); mid = a + (b - a) * 0.56
        K.capsule(name + f" {nm} ram", tuple(a), tuple(mid), r, dark, parent=house)
        K.capsule(name + f" {nm} rod", tuple(mid), tuple(b), r * 0.55, chrome, parent=house)
    for sx in (-1, 1):
        ram("boom", A + Vector((sx * 0.17, -0.12, -0.12)), K_ + Vector((sx * 0.13, 0, 0)) - n1 * 0.12)
    ram("stick", K_ + n1 * 0.18, S0 + Vector((0, 0, 0)) + n1 * 0.04, r=0.05)
    n2 = Vector((0, math.sin(b2), math.cos(b2)))
    ram("bucket", B + d2 * 0.15 + n2 * 0.14, C - d2 * 0.12 + n2 * 0.16, r=0.04)
    bk = _bucket(name + " bucket", tuple(C), b2 + math.radians(bucket) + math.pi / 2, 0.5, 0.42, steel, _simple("fx bucket teeth", "#3A3B3C", rough=0.4, metal=1.0), house)
    lights_out = []; lamps = []
    for (lx, ly, lzz, aim) in ((cx - 0.12, cy - cd / 2, cz + ch + 0.06, (cx, -5.0, 0.0)), (cx + 0.12, cy - cd / 2, cz + ch + 0.06, (0.4, -5.0, 0.0)), (0.16, A.y - 0.6, A.z + 0.5, (0.16, -4.0, 0.0))):
        lamps.append(K.box(name + " work lamp", (lx, ly - 0.02, lzz), (0.1, 0.05, 0.07), lens_mat("work", lights), bev=0.012, parent=house))
        if lights:
            lights_out.append(_spot(name + " work beam", (lx, ly - 0.07, lzz), aim, power, house, size=85.0))
    bc = K.cyl(name + " beacon", (cx, cy + 0.2, cz + ch + 0.07), 0.035, 0.07, lens_mat("amber", lights), v=14, parent=house)
    if lights:
        lights_out.append(_lamp(name + " beacon glow", (cx, cy + 0.2, cz + ch + 0.16), 6.0, (1.0, 0.5, 0.05), house))
    house.rotation_euler = (0, 0, math.radians(slew))
    _place(root, loc, yaw)
    bpy.context.view_layer.update()
    objs = [o for o in root.children_recursive if o.type == 'MESH']
    return dict(objects=[root] + objs, lights=lights_out, root=root, house=house, cab=cab, bucket=bk, lamps=lamps, tip=bk.matrix_world.translation.copy())
