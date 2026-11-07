"""LOOK=NYC: the checkout BUILT the way the Oct-29 New York street was built (caaleb, 2026-11-06 23:11Z: "New York
looked good because of how it was built"). Daytime store, not night. Applied after the stager has animated the shot,
so staging, grip and timing are untouched.

  - every object is made of its real parts at real scale (the brick building had frames, sills, lintels, mullions):
    a suspended ceiling of 2x2 tiles on a T-bar grid with troffers, supply diffusers and sprinkler heads; gondola
    uprights with slots, brackets and kick plates; counters with a rubber bumper rail, a flatbed scanner and divider
    bars; kiosks with a scanner deck, receipt and cash slots, a handheld scanner and a status light
  - one muted palette (warm greys, slate, the products and Data carry the colour)
  - the clutter is gone: header band and its sign, hanging signs, lane-number poles, kiosk sign plates, floor decal,
    dump bin; the cashiers are dropped (the counters sinking and the kiosks rising tell the change)
  - daylight with a real directional key: a low-angle sun through the shopfront casts hard shadows; the panels fill
"""
import bpy, math, random
from mathutils import Vector
import scene_kit as K

CLUTTER = ("header", "band sign", "hanging sign", "sign rod", "ceiling signs", "lane sign", "lane number", "sign pole",
           "kiosk sign", "floor decal", "dump bin", "bin ball", "bin sign", "light frame", "light diffuser", "ceiling")


def _mat(name, hexc, rough=0.6, metal=0.0, emit=0.0):
    m = K.mat(name, hexc, rough=rough, metal=metal, emit=emit); return m


def _kill(o):
    for c in list(o.children_recursive) + [o]:
        if c.name in bpy.data.objects: bpy.data.objects.remove(c, do_unlink=True)


def brick_mat(name, base="#7A3B2A", base2="#8C4632", mortar="#6B655E", scale=7.0):
    """running-bond brick on a wall standing in XZ: per-brick colour, mottle, recessed mortar"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    br = nt.nodes.new("ShaderNodeTexBrick"); br.offset = 0.5; br.squash = 1.0
    br.inputs["Scale"].default_value = scale; br.inputs["Mortar Size"].default_value = 0.012; br.inputs["Brick Width"].default_value = 0.5; br.inputs["Row Height"].default_value = 0.17
    br.inputs["Color1"].default_value = (*K.lin(base), 1); br.inputs["Color2"].default_value = (*K.lin(base2), 1); br.inputs["Mortar"].default_value = (*K.lin(mortar), 1)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); mp.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 30; nz.inputs["Detail"].default_value = 6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs["Factor"].default_value = 0.35
    nt.links.new(br.outputs["Color"], mx.inputs["A"]); nt.links.new(nz.outputs["Color"], mx.inputs["B"]); nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; nt.links.new(br.outputs["Fac"], inv.inputs[1])
    ad = nt.nodes.new("ShaderNodeMath"); ad.operation = 'MULTIPLY_ADD'; ad.inputs[1].default_value = 0.15
    nt.links.new(nz.outputs["Fac"], ad.inputs[0]); nt.links.new(inv.outputs[0], ad.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; bump.inputs["Distance"].default_value = 0.004
    nt.links.new(ad.outputs[0], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"]); b.inputs["Roughness"].default_value = 0.85
    return m


def strip():
    for n in [o.name for o in bpy.data.objects]:
        o = bpy.data.objects.get(n)
        if o is not None and n.startswith(CLUTTER): _kill(o)
    for o in list(bpy.data.objects):
        if o.name.endswith("cashier"):
            for c in [o] + list(o.children_recursive): c.animation_data_clear(); c.hide_render = True; c.hide_viewport = True


def ceiling():
    """an OPEN ceiling, as modern stores build them: a corrugated deck painted light grey (a dark one ate the top third of the frame), steel bar joists, a round galvanised duct,
    conduit, and linear pendant fixtures hung on cables (each one sits on a lamp style.py already placed)"""
    z0 = K.WALL_H + 0.55
    deck = bpy.data.materials.get("deck") or bpy.data.materials.new("deck"); deck.use_nodes = True
    nt = deck.node_tree; b = nt.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*K.lin("#B9BBBC"), 1); b.inputs["Roughness"].default_value = 0.8
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = 'BANDS'; wv.bands_direction = 'X'; wv.wave_profile = 'SAW'; wv.inputs["Scale"].default_value = 2.0
    tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; bp.inputs["Distance"].default_value = 0.02
    nt.links.new(wv.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    K.box("deck", (1.0, (K.FAR_Y - 3.5) / 2, z0 + 0.02), (16, K.FAR_Y + 3.5, 0.04), deck, bev=0)
    steel = _mat("joist steel", "#A4A8AC", rough=0.55, metal=0.2)
    for k in range(int((K.FAR_Y + 3.0) / 0.9)):
        y = -3.0 + k * 0.9
        K.box("joist top", (1.0, y, z0 - 0.02), (16, 0.025, 0.02), steel, bev=0)
        K.box("joist bottom", (1.0, y, z0 - 0.28), (16, 0.025, 0.02), steel, bev=0)
        x = -7.0
        while x < 9.0:   # the web: diagonals between the chords
            w = K.box("joist web", (x + 0.13, y, z0 - 0.15), (0.012, 0.012, 0.36), steel, bev=0); w.rotation_euler = (0, math.radians(45 if int(x / 0.26) % 2 else -45), 0)
            x += 0.26
    galv = bpy.data.materials.get("duct") or bpy.data.materials.new("duct"); galv.use_nodes = True
    gb = galv.node_tree.nodes["Principled BSDF"]; gb.inputs["Base Color"].default_value = (*K.lin("#6C7075"), 1); gb.inputs["Metallic"].default_value = 0.8; gb.inputs["Roughness"].default_value = 0.4
    for x in (-1.6, 2.6):
        K.cyl("duct", (x, 2.0, z0 - 0.42), 0.16, 12.0, galv, rot=(math.radians(90), 0, 0), v=32, bev=0)
        for j in range(16): K.cyl("duct seam", (x, -3.6 + j * 0.75, z0 - 0.42), 0.163, 0.012, galv, rot=(math.radians(90), 0, 0), v=32, bev=0)
    K.cyl("conduit", (0.4, 2.0, z0 - 0.3), 0.012, 12.0, _mat("conduit", "#8A8D90", rough=0.4, metal=0.8), rot=(math.radians(90), 0, 0), v=12, bev=0)


def gondola_parts():
    """the back shelf run made of its parts: slotted uprights every 0.68 m, a bracket under each shelf end, kick plates, a pegboard back"""
    g = bpy.data.objects.get("gondola")
    if g is None: return
    steel = _mat("gondola steel", "#5E6369", rough=0.45, metal=0.5)
    slot = _mat("upright slot", "#1E2125", rough=0.6)
    yb = K.BACK_Y - 0.03; x0, x1 = -3.5, 4.8; x = x0
    while x <= x1 + 0.01:
        K.box("upright", (x, yb - 0.005, 0.66), (0.03, 0.03, 1.32), steel, bev=0.003, parent=g)
        for zz in [0.06 + 0.04 * k for k in range(31)]:
            K.box("upright slot", (x, yb - 0.021, zz), (0.006, 0.002, 0.02), slot, bev=0, parent=g)
        for z in (0.22, 0.66, 1.1):
            K.box("bracket", (x + 0.02, yb - 0.12, z - 0.03), (0.008, 0.22, 0.04), steel, bev=0.002, parent=g)
        x += 0.68
    K.box("kick plate", ((x0 + x1) / 2, yb - 0.25, 0.05), (x1 - x0, 0.012, 0.1), steel, bev=0.003, parent=g)
    # pegboard back: holes as a dotted pattern on the existing back panel material
    m = bpy.data.materials.get("shelf")
    if m:
        nt = m.node_tree; b = nt.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*K.lin("#7C8188"), 1)
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (40, 40, 40)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.feature = 'F1'; vo.inputs["Randomness"].default_value = 0.0
        nt.links.new(mp.outputs["Vector"], vo.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.12; mr.inputs["From Max"].default_value = 0.16
        nt.links.new(vo.outputs["Distance"], mr.inputs["Value"])
        bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.8; bp.inputs["Distance"].default_value = 0.002
        nt.links.new(mr.outputs["Result"], bp.inputs["Height"])
        if b.inputs["Normal"].is_linked:
            old = b.inputs["Normal"].links[0].from_socket; nt.links.new(old, bp.inputs["Normal"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def counter_parts(lanes):
    """each counter: a rubber bumper rail on the customer face, a flatbed scanner glass, a divider bar on the belt"""
    rub = _mat("bumper rubber", "#2A2C2F", rough=0.7)
    glass = _mat("scanner glass", "#14181C", rough=0.05, metal=0.0)
    red = _mat("scanner red", "#FF2A1A", rough=0.3, emit=3.0)
    div = _mat("divider", "#3D4249", rough=0.4)
    for ln in lanes:
        c = ln["counter"]; x = ln["x"]; y0 = 0.32; L = 1.5 * K.U; h = ln["h"]; w = 0.52 * K.U
        K.box("bumper", (x - w / 2 - 0.008, y0 + L / 2, h * 0.62), (0.022, L - 0.04, 0.035), rub, bev=0.01, parent=c)
        K.box("bumper low", (x - w / 2 - 0.006, y0 + L / 2, h * 0.3), (0.018, L - 0.04, 0.03), rub, bev=0.008, parent=c)
        K.box("scanner glass", (x, y0 + 0.24, h + 0.026), (0.14, 0.1, 0.004), glass, bev=0.001, parent=c)
        K.box("scanner line", (x, y0 + 0.24, h + 0.0285), (0.1, 0.003, 0.001), red, bev=0, parent=c)
        K.box("divider bar", (x, y0 + 0.62, h + 0.05), (w * 0.5, 0.025, 0.025), div, bev=0.008, parent=c)


OLD_KIOSK = ("kiosk base", "kiosk body", "kiosk stripe", "kiosk reader", "kiosk screen neck", "kiosk shelf", "kiosk scale", "kiosk bag")


def _brushed(name, hexc, rough=0.32):
    """brushed steel: metallic, anisotropic along x, a fine streak in the roughness"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = K.mat(name, hexc, rough=rough, metal=0.9); nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    try: b.inputs["Anisotropic"].default_value = 0.6
    except KeyError: pass
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2, 300, 300)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 4; nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = rough - 0.08; mr.inputs["To Max"].default_value = rough + 0.08
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    return m


def _painted(name, hexc, rough=0.42):
    """powder-coated sheet metal: a faint orange-peel bump and a little roughness variation"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = K.mat(name, hexc, rough=rough); nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 180
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.08; bp.inputs["Distance"].default_value = 0.001
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def _carrier_bag(name, base, m, inside, parent, bar):
    """a plastic carrier bag standing open on the scale: a rumpled tapered sack (not a ball), a dark mouth, two handle
    loops running up to the rack bar"""
    bx, by, bz = base; Wb, Db, Hb = 0.17, 0.1, 0.2
    o = K.box(name, (bx, by, bz + Hb / 2), (Wb, Db, Hb), m, bev=0.02, parent=parent)
    sd = o.modifiers.new("taper", "SIMPLE_DEFORM"); sd.deform_method = 'TAPER'; sd.factor = -0.35; sd.deform_axis = 'Z'
    ss = o.modifiers.new("soft", "SUBSURF"); ss.levels = 2; ss.render_levels = 2
    tx = bpy.data.textures.get("bag rumple") or bpy.data.textures.new("bag rumple", 'CLOUDS'); tx.noise_scale = 0.035; tx.noise_depth = 3
    md = o.modifiers.new("rumple", "DISPLACE"); md.texture = tx; md.strength = 0.03; md.mid_level = 0.5; md.texture_coords = 'GLOBAL'
    K.box(name + " mouth", (bx, by, bz + Hb - 0.004), (Wb * 0.86, Db * 0.7, 0.004), inside, bev=0.01, parent=parent)
    for dx in (-0.05, 0.05):   # a handle from each side seam up over the bar
        a = Vector((bx + dx, by, bz + Hb)); b = Vector((bar[0] + dx * 1.2, bar[1], bar[2])); mid = (a + b) / 2; L = (b - a).length
        h = K.cyl(name + " handle", tuple(mid), 0.009, L, m, v=8, bev=0, parent=parent)
        h.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()


def kiosk_parts(kiosks):
    """each kiosk rebuilt as a real self-checkout station (it read as a black filing cabinet): a pedestal cabinet with a
    service door and a vent, a scanner housing on top with a glass bed and a bioptic window, brushed trim, the screen on
    a post-and-bracket arm, a card terminal on a stalk, a bagging platform on a tube frame with a bag rack and a hanging
    carrier bag, and a light pole with the lane lamp on top. Built at the kiosk's rest pose, parented to its root, so
    the stager's rise carries all of it."""
    body = _painted("station body", "#5B6067"); panel = _painted("station panel", "#4A4F56", rough=0.5)
    trim = _brushed("station trim", "#B3B7BB"); tube = _brushed("station tube", "#9EA3A8", rough=0.38)
    dark = _mat("station dark", "#202226", rough=0.55); rubber = _mat("station rubber", "#18191B", rough=0.8)
    glass = _mat("scanner glass", "#14181C", rough=0.05); red = _mat("scanner red", "#FF2A1A", rough=0.3, emit=3.0)
    slot = _mat("slot", "#08090A", rough=0.6); keypad = bpy.data.materials.get("keypad") or _mat("keypad", "#3A3D42", rough=0.5)
    tscreen = _mat("terminal screen", "#9FD0FF", rough=0.1, emit=1.2); lamp = _mat("lane lamp", "#3BD16F", rough=0.3, emit=4.0)
    bagm = _mat("carrier bag", "#ECEBE6", rough=0.55)
    try: bagm.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 0.25
    except KeyError: pass
    for kk in kiosks:
        root = kk["root"]
        for c in list(root.children_recursive):
            if c.name.startswith(OLD_KIOSK) and c.name in bpy.data.objects: bpy.data.objects.remove(c, do_unlink=True)
        x, y, z0 = root.location; H = kk["h"] - 0.7; ch = H / 1.3       # H: the old body top (0.655); ch: counter height
        P = lambda *a, **k: K.box(*a, parent=root, **k)
        zc = z0                                                          # the root is at rest (z = 0) when this runs
        hp = H * 0.66                                                    # pedestal height
        P("plinth", (x, y, zc + 0.02), (0.36, 0.34, 0.04), rubber, bev=0.008)
        P("pedestal", (x, y + 0.01, zc + 0.04 + hp / 2), (0.28, 0.26, hp), body, bev=0.014)
        P("door", (x, y - 0.121, zc + 0.05 + hp * 0.52), (0.22, 0.004, hp * 0.78), panel, bev=0.004)
        P("door trim", (x, y - 0.124, zc + 0.05 + hp * 0.52), (0.232, 0.002, hp * 0.80), trim, bev=0.001)
        P("door lock", (x + 0.085, y - 0.127, zc + 0.05 + hp * 0.7), (0.012, 0.004, 0.012), trim, bev=0.002)
        for k in range(6): P("vent slat", (x, y - 0.127, zc + 0.08 + k * 0.016), (0.16, 0.004, 0.006), dark, bev=0.001)
        # the scanner housing: wider than the pedestal, overhanging toward the customer, brushed band round its lip
        zt = zc + 0.04 + hp; th = H - (0.04 + hp) + 0.01
        P("scanner housing", (x, y - 0.02, zt + th / 2), (0.36, 0.32, th), body, bev=0.03)
        P("housing trim", (x, y - 0.02, zt + th - 0.008), (0.368, 0.328, 0.012), trim, bev=0.004)
        P("bed glass", (x - 0.02, y - 0.06, zt + th + 0.002), (0.18, 0.14, 0.004), glass, bev=0.002)
        P("bed line", (x - 0.02, y - 0.06, zt + th + 0.0045), (0.13, 0.003, 0.001), red, bev=0)
        P("bed frame", (x - 0.02, y - 0.06, zt + th + 0.001), (0.196, 0.156, 0.003), trim, bev=0.001)
        P("bioptic tower", (x - 0.02, y + 0.07, zt + th + 0.05), (0.2, 0.05, 0.1), body, bev=0.012)
        P("bioptic window", (x - 0.02, y + 0.044, zt + th + 0.05), (0.15, 0.003, 0.07), glass, bev=0.001)
        P("fascia", (x, y - 0.181, zt + th * 0.5), (0.3, 0.003, th * 0.62), panel, bev=0.002)
        P("fascia trim", (x, y - 0.1825, zt + th * 0.5 - th * 0.31), (0.3, 0.002, 0.006), trim, bev=0.001)
        for k in range(5): P("speaker hole", (x - 0.1 + k * 0.012, y - 0.183, zt + th * 0.62), (0.006, 0.002, 0.006), slot, bev=0)
        P("receipt slot", (x + 0.12, y - 0.181, zt + th * 0.45), (0.07, 0.004, 0.006), slot, bev=0)
        P("receipt bezel", (x + 0.12, y - 0.180, zt + th * 0.45), (0.09, 0.003, 0.02), trim, bev=0.001)
        # the screen's post and bracket (the screen and its frame stay where kiosk() put them, keyed by the stager)
        zs = H + 0.17
        K.cyl("screen post", (x, y + 0.11, (zt + th + zs) / 2), 0.016, zs - (zt + th), tube, v=20, bev=0.002, parent=root)
        P("screen bracket", (x, y + 0.05, zs - 0.02), (0.08, 0.12, 0.03), dark, bev=0.008)
        # card terminal on a stalk, to the customer's left, tilted up to him
        K.cyl("terminal stalk", (x - 0.21, y - 0.08, zt + th * 0.5 + 0.07), 0.008, 0.16, tube, v=12, bev=0, parent=root)
        P("terminal arm", (x - 0.19, y - 0.08, zt + th * 0.5 - 0.005), (0.06, 0.014, 0.014), tube, bev=0.003)
        t = P("terminal", (x - 0.21, y - 0.08, zt + th * 0.5 + 0.16), (0.06, 0.03, 0.09), dark, bev=0.008); t.rotation_euler = (math.radians(-25), 0, 0)
        ts = P("terminal screen", (x - 0.21, y - 0.097, zt + th * 0.5 + 0.18), (0.044, 0.002, 0.026), tscreen, bev=0.001); ts.rotation_euler = (math.radians(-25), 0, 0)
        tk = P("terminal keys", (x - 0.21, y - 0.091, zt + th * 0.5 + 0.143), (0.044, 0.002, 0.03), keypad, bev=0.001); tk.rotation_euler = (math.radians(-25), 0, 0)
        # bagging area on a tube frame to +x: a brushed scale plate, a bag rack with a carrier bag hanging open
        bx = x + 0.34; zb = zc + ch * 0.88
        for dx in (-0.13, 0.13):
            for dy in (-0.12, 0.12):
                K.cyl("bag leg", (bx + dx, y + dy, zc + zb / 2), 0.009, zb, tube, v=12, bev=0, parent=root)
        P("bag frame", (bx, y, zb - 0.012), (0.29, 0.27, 0.02), tube, bev=0.004)
        P("bag scale", (bx, y, zb + 0.006), (0.27, 0.25, 0.012), trim, bev=0.003)
        P("bag shelf low", (bx, y, zc + 0.12), (0.27, 0.25, 0.012), panel, bev=0.003)
        for dx in (-0.12, 0.12): K.cyl("rack post", (bx + dx, y + 0.1, zb + 0.15), 0.007, 0.3, tube, v=12, bev=0, parent=root)
        K.cyl("rack bar", (bx, y + 0.1, zb + 0.3), 0.007, 0.25, tube, rot=(0, math.radians(90), 0), v=12, bev=0, parent=root)
        _carrier_bag(f"carrier bag {kiosks.index(kk)}", (bx, y + 0.04, zb + 0.012), bagm, dark, root, (bx, y + 0.1, zb + 0.3))
        # the lane light pole on the back corner, its lamp lit
        K.cyl("light pole", (x + 0.15, y + 0.12, (zt + th + H + 0.62) / 2), 0.01, (H + 0.62) - (zt + th), tube, v=12, bev=0, parent=root)
        K.cyl("lane lamp", (x + 0.15, y + 0.12, H + 0.64), 0.03, 0.06, lamp, v=24, bev=0.004, parent=root)
        K.cyl("lamp cap", (x + 0.15, y + 0.12, H + 0.675), 0.033, 0.01, dark, v=24, bev=0.002, parent=root)


def palette():
    """one muted palette: warm greys and slate; colour belongs to the products and Data"""
    for name, hexc in (("wall band", "#3A3D42"), ("kiosk accent", "#7A8088"), ("counter", "#34363A"), ("kiosk body", "#2E3136"),
                       ("counter edge", "#A97E57"), ("sign navy", "#2E3238"), ("column", "#3A3D42"), ("register", "#26282B"),
                       ("plank", "#C9C5BD"), ("rail", "#B8BCC0")):
        m = bpy.data.materials.get(name)
        if m:
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b and not b.inputs["Base Color"].is_linked: b.inputs["Base Color"].default_value = (*K.lin(hexc), 1)


def surfaces():
    """the brick, the concrete, the oak: real textures where the eye lands"""
    wall = bpy.data.materials.get("wall")
    if wall:   # the far wall is a brick feature wall, like the block in New York
        br = brick_mat("brick wall")
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.data.materials and o.data.materials[0] == wall: o.data.materials[0] = br
    m = bpy.data.materials.get("floor")
    if m:   # polished concrete: saw-cut joints every 1.2 m, warm grey mottle, a high coat
        nt = m.node_tree; br = next((n for n in nt.nodes if n.type == 'TEX_BRICK'), None)
        if br:
            br.inputs["Scale"].default_value = 1 / 1.2; br.inputs["Mortar Size"].default_value = 0.004
            br.inputs["Color1"].default_value = (*K.lin("#615C56"), 1); br.inputs["Color2"].default_value = (*K.lin("#5A5550"), 1); br.inputs["Mortar"].default_value = (*K.lin("#4A4744"), 1)
            mot = nt.nodes.new("ShaderNodeTexNoise"); mot.inputs["Scale"].default_value = 1.6; mot.inputs["Detail"].default_value = 10; mot.inputs["Roughness"].default_value = 0.65
            tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], mot.inputs["Vector"])
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'OVERLAY'; mx.inputs["Factor"].default_value = 0.8
            nt.links.new(br.outputs["Color"], mx.inputs["A"]); nt.links.new(mot.outputs["Color"], mx.inputs["B"])
            b = nt.nodes["Principled BSDF"]; nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    edge = bpy.data.materials.get("counter edge")
    if edge:   # oak laminate top: grain along the counter
        nt = edge.node_tree; b = nt.nodes["Principled BSDF"]
        wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = 'BANDS'; wv.bands_direction = 'Y'; wv.inputs["Scale"].default_value = 18; wv.inputs["Distortion"].default_value = 6; wv.inputs["Detail"].default_value = 4
        tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*K.lin("#8E6440"), 1); ramp.color_ramp.elements[1].color = (*K.lin("#B98C60"), 1)
        nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.35


def fixtures():
    """linear pendant fixtures hung on cables, one on each ceiling lamp style.lights() placed"""
    z0 = K.WALL_H + 0.55
    housing = _mat("fixture housing", "#1C1D1F", rough=0.4, metal=0.5)
    lens = _mat("fixture lens", "#FFFDF8", rough=0.3, emit=3.0)
    cable = _mat("cable", "#111111", rough=0.5)
    for o in [o for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith(("panel", "far panel"))]:
        x, y, z = o.location; L = o.data.size; Wd = o.data.size_y or 0.3
        zf = 2.3 if o.name.startswith("panel") else 2.35
        o.location.z = zf - 0.03
        K.box("fixture", (x, y, zf), (L, 0.07, 0.05), housing, bev=0.006)
        lo = K.box("fixture lens", (x, y, zf - 0.027), (L - 0.03, 0.05, 0.004), lens, bev=0); lo.visible_diffuse = False; lo.visible_shadow = False
        for s_ in (-1, 1): K.cyl("fixture cable", (x + s_ * L * 0.4, y, (zf + z0) / 2), 0.002, z0 - zf, cable, v=6, bev=0)
        o.data.size_y = 0.06


def relight():
    """daylight with a real key. The ceiling blocks a sky sun, so the key is the sun through the shopfront behind the
    camera: a distant hard spot from camera-left-front, low enough to throw long shadows to the right and back.
    The panel rows and the window wash drop to fill so the shadows read."""
    for o in bpy.data.objects:
        if o.type != 'LIGHT': continue
        if o.name.startswith("panel"): o.data.energy *= 1.2
        elif o.name.startswith("far panel"): o.data.energy *= 0.8
        elif o.name == "window": o.data.energy *= 0.12
        elif o.name == "fill": o.data.energy *= 0.5
        elif o.name == "daylight": o.data.energy = 0.0
    ld = bpy.data.lights.new("sun key", 'SPOT'); ld.energy = 17000; ld.color = (1.0, 0.93, 0.82); ld.shadow_soft_size = 0.06
    ld.spot_size = math.radians(40); ld.spot_blend = 0.25
    o = bpy.data.objects.new("sun key", ld); o.location = (-8.5, -5.0, 2.95)   # far off, like the sun: the near floor no longer gets twice the light Data does; bpy.context.collection.objects.link(o)
    o.rotation_euler = (Vector((0.9, 0.6, 0.3)) - o.location).to_track_quat('-Z', 'Y').to_euler()
    m = bpy.data.materials.get("floor")
    if m:   # the floor stops glaring white: a mid warm grey tile
        br = next((n for n in m.node_tree.nodes if n.type == 'TEX_BRICK'), None)
        if br: br.inputs["Color1"].default_value = (*K.lin("#A3A19C"), 1); br.inputs["Color2"].default_value = (*K.lin("#999791"), 1)
    w = bpy.context.scene.world
    if w:
        bg = w.node_tree.nodes.get("Background")
        if bg: bg.inputs["Strength"].default_value = 0.01   # the open front lets in a little sky, no more
    fixtures()
    m = bpy.data.materials.get("floor")
    if m:   # concrete, sealed not mirror-polished: the coat was whitening it
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Coat Weight"].default_value = 0.2
            nt = m.node_tree; src = b.inputs["Base Color"].links[0].from_socket   # after style.py's speckle: pull the whole floor down to mid-grey concrete
            mu = nt.nodes.new("ShaderNodeMix"); mu.data_type = 'RGBA'; mu.blend_type = 'MULTIPLY'; mu.inputs["Factor"].default_value = 1.0
            mu.inputs["B"].default_value = (0.5, 0.48, 0.45, 1); nt.links.new(src, mu.inputs["A"]); nt.links.new(mu.outputs["Result"], b.inputs["Base Color"])
    for name in ("kiosk body", "register"):   # style.py's edge wear reads pointiness, which on a low-poly box lightens whole faces: keep the machines charcoal
        m = bpy.data.materials.get(name)
        if m:
            for n in m.node_tree.nodes:
                if n.type == 'MIX' and n.data_type == 'RGBA' and not n.inputs['B'].is_linked: n.inputs['B'].default_value = (*K.lin('#4A4E54'), 1)


def piers():
    """brick piers carrying the roof just behind the shelf run: the far brick wall sits seven metres back, soft and dark
    behind the aisles, so the brick that makes the room read as BUILT has to stand where the camera actually looks"""
    br = brick_mat("brick wall"); cap = _mat("pier cap", "#8A8580", rough=0.7)
    for x in (-1.45, 1.55, 4.3):
        K.box("brick pier", (x, K.BACK_Y + 0.22, K.WALL_H / 2 + 0.28), (0.42, 0.36, K.WALL_H + 0.56), br, bev=0.004)
        K.box("pier base", (x, K.BACK_Y + 0.22, 0.05), (0.45, 0.39, 0.1), cap, bev=0.006)


def apply(sc, store, f_rest_kiosk):
    strip(); palette(); surfaces(); piers()
    sc.frame_set(1); ceiling(); gondola_parts(); counter_parts(store["lanes"] + store["extra"])
    sc.frame_set(f_rest_kiosk); bpy.context.view_layer.update(); kiosk_parts(store["kiosks"])
    sc.frame_set(1)


def feet_shadow(data):
    """a soft contact shadow under Data that travels with him: the key throws his cast shadow behind the counters, and
    without this he floats on the concrete. Its own round falloff (the shared contact-shadow plane shows its corners)."""
    m = bpy.data.materials.new("feet shadow"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); mixs = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); dif.inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2, 2, 1); mp.inputs["Location"].default_value = (-1, -1, 0)
    grad = nt.nodes.new("ShaderNodeTexGradient"); grad.gradient_type = 'SPHERICAL'
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6; nt.links.new(grad.outputs["Fac"], pw.inputs[0])
    mu = nt.nodes.new("ShaderNodeMath"); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = 0.9; nt.links.new(pw.outputs[0], mu.inputs[0])
    nt.links.new(mu.outputs[0], mixs.inputs["Fac"]); nt.links.new(tr.outputs[0], mixs.inputs[1]); nt.links.new(dif.outputs[0], mixs.inputs[2]); nt.links.new(mixs.outputs[0], out.inputs["Surface"])
    sc = data.sc; sc.frame_set(1)
    o = K.contact_shadow("Data feet shadow", (data.arm.location.x, data.arm.location.y), rx=0.3, ry=0.24, parent=data.arm)
    o.data.materials[0] = m
