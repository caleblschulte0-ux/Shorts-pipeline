"""The checkout set, built from primitives in bpy (rebuild of 2026-11-06, after the scratchpad wipe).

Units: metres at Data's scale. Data is 0.95 m tall; the world is built at U = 0.56 of adult size so he reads adult-sized.
Front of the store (the camera side) is -Y; the back wall is at BACK_Y. Data walks along y = 0 in +X.
Every builder returns the objects a stager needs (anchors are empties); materials are looked up by NAME by style.py,
so keep the names.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Euler

U = 0.56
BACK_Y = 2.4 * U          # 1.344
WALL_H = 4.6 * U          # 2.576
LANE_X = [0.0, 0.62, 1.24, 1.86]
FAR_X = [3.05, 3.67]
FAR_Y = BACK_Y + 7.0        # the far wall: the store goes on behind the lanes
FPS = 24

# natural supermarket colours; one brand accent (the orange band) and the blue of the screens
PAL = {
    "wall": "#E6E1D8", "wall band": "#C8643A", "floor": "#B9BDC1", "grout": "#A9ADB2", "counter": "#E9E6E0",
    "counter edge": "#6E6961", "kiosk body": "#EDEEF0", "kiosk dark": "#2B2F36", "kiosk screen": "#2F7FE0",
    "register": "#2B2F36", "reg screen": "#BFD8F0", "card reader": "#2B2F36", "keypad": "#3A3F47", "uniform": "#1F5F8B",
    "apron": "#2B2F36", "belt": "#1C1E22", "belt well": "#8A8F96", "rail": "#C9CDD2", "sign pole": "#AEB3B9",
    "lane sign": "#F6F2E8", "sign frame": "#2B2F36", "rack": "#4A4F57", "rack shelf": "#AEB3B9", "paper bag": "#C9A97E",
    "bag fold": "#B0905F", "cereal": "#C6392B", "cereal2": "#F0D27A", "milk": "#F2F2F0", "milk cap": "#2F5FB8",
    "banana": "#E8C94E", "cart metal": "#C9CDD2", "cart plastic": "#C6392B", "wheel": "#2A2D31", "shelf": "#8E9299",
    "plank": "#DAD6CE", "trim": "#8F8A82", "base board": "#5B5F66", "sign ivory": "#FFF6E6", "sign navy": "#1F3B63",
    "mat rubber": "#3A3D42", "basket red": "#B23A2E", "cone yellow": "#E8C219", "pallet wood": "#9C7A4E",
    "price strip": "#F5F1E8", "can lid": "#C9CDD2", "thin bag": "#EDEFF2", "skin": "#E8B48E", "hair": "#3A2A20",
    "pants": "#3E424C", "shoe": "#1F2024", "eye white": "#F6F4F0", "pupil": "#1C1A1E", "lip": "#B46A5C", "name tag": "#F7F5EE",
}
PRODUCTS = ["#B8655A", "#6E8FB5", "#C9A94E", "#7E9C6A", "#8A6FA8", "#D08A4E", "#5F8F8A", "#B5B0A6", "#C46A7E", "#5E6E8F"]
BRANDS = ["OATIES", "VITA", "PURE", "CRISP", "NOVA", "ALPINE", "SUNNY", "GOLD", "FRESH", "DAILY", "ORIGIN", "KETTLE", "MAPLE",
          "HARVEST", "BLUE SKY", "ROOTS", "SILK", "NORTH", "PRIMA", "ZEST", "ORCHARD", "CLASSIC"]


def lin(hexc):
    h = hexc.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


_MATS = {}
def mat(name, hexc=None, rough=0.6, metal=0.0, emit=0.0, spec=0.45):
    """one material per NAME (style.py restyles by name); the first call sets the colour"""
    if name in _MATS: return _MATS[name]
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        col = lin(hexc or PAL.get(name, "#AAAAAA"))
        b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal; b.inputs["Specular IOR Level"].default_value = spec
        if emit: b.inputs["Emission Strength"].default_value = emit; b.inputs["Emission Color"].default_value = (*col, 1)
    _MATS[name] = m
    return m


def _link(o, parent=None):
    bpy.context.collection.objects.link(o)
    if parent is not None:
        # children are built at ABSOLUTE positions; the parent's matrix_world is stale until the depsgraph runs, so the
        # inverse is built from its basis (roots) or after an update (nested) - never from a stale identity
        if parent.parent is None: inv = parent.matrix_basis.inverted()
        else: bpy.context.view_layer.update(); inv = parent.matrix_world.inverted()
        o.parent = parent; o.matrix_parent_inverse = inv
    return o


def _smooth(o):
    for p in o.data.polygons: p.use_smooth = True


def empty(name, loc, parent=None):
    o = bpy.data.objects.new(name, None); o.location = loc; o.empty_display_size = 0.05
    return _link(o, parent)


def box(name, loc, size, m, bev=0.012, parent=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc; me.materials.append(m)
    if bev:
        md = o.modifiers.new("bevel", "BEVEL"); md.width = min(bev, min(size) * 0.45); md.segments = 3; md.limit_method = 'NONE'
        _smooth(o)
    return _link(o, parent)


def cyl(name, loc, r, h, m, rot=(0, 0, 0), v=32, bev=0.004, parent=None):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=v, radius1=r, radius2=r, depth=h)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc; o.rotation_euler = rot; me.materials.append(m)
    _smooth(o)
    if bev:
        md = o.modifiers.new("bevel", "BEVEL"); md.width = min(bev, r * 0.3, h * 0.3); md.segments = 2
    return _link(o, parent)


def sph(name, loc, r, m, scale=(1, 1, 1), parent=None, seg=32, ring=16):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc; o.scale = scale; me.materials.append(m); _smooth(o)
    return _link(o, parent)


def text(name, body, loc, size, rot, m, extrude=0.002, parent=None, align='CENTER'):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.extrude = extrude
    cu.align_x = align; cu.align_y = 'CENTER'
    o = bpy.data.objects.new(name, cu); o.location = loc; o.rotation_euler = rot; cu.materials.append(m)
    return _link(o, parent)


# ------------------------------------------------------------------ the room
def floor(size=(16, 10), tile=0.9):
    """lino floor: big tiles as a faint seam grid in the base colour (style.py adds speckle/gloss/scuffs)"""
    m = mat("floor", rough=0.55)
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    br = nt.nodes.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.0 / tile
    br.inputs["Mortar Size"].default_value = 0.006 / tile; br.inputs["Mortar Smooth"].default_value = 0.6; br.offset = 0.0; br.squash = 1.0
    br.inputs["Color1"].default_value = (*lin(PAL["floor"]), 1); br.inputs["Color2"].default_value = (*lin("#B4B8BC"), 1)
    br.inputs["Mortar"].default_value = (*lin(PAL["grout"]), 1)
    tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    o = box("floor", (0.5, -2.0, -0.01), (size[0], size[1], 0.02), m, bev=0)
    return o


def walls():
    """back wall with trim and base board, the orange band with its text, a side return at the far end"""
    wall = mat("wall", rough=0.7); band = mat("wall band", rough=0.55); trim = mat("trim", rough=0.6); base = mat("base board", rough=0.7)
    box("back wall", (0.5, FAR_Y + 0.1, WALL_H / 2), (26, 0.2, WALL_H), wall, bev=0)
    cm = mat("ceiling", "#E9E7E2", rough=0.9)
    nt = cm.node_tree; b = nt.nodes["Principled BSDF"]
    br = nt.nodes.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1 / 0.6; br.inputs["Mortar Size"].default_value = 0.012 / 0.6
    br.inputs["Color1"].default_value = (*lin("#E9E7E2"), 1); br.inputs["Color2"].default_value = (*lin("#E4E2DD"), 1); br.inputs["Mortar"].default_value = (*lin("#C9C7C2"), 1)
    br.offset = 0.0; br.squash = 1.0; tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], br.inputs["Vector"]); nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    box("ceiling", (0.5, 3.2, WALL_H + 0.02), (26, 11.6, 0.04), cm, bev=0)
    for x in range(-5, 7):
        for y in [0.0, 1.0] + [2.4 + 1.4 * k for k in range(5)]:   # recessed light panels: a dark frame and a bright diffuser, lit by the real area lights below them
            box("light frame", (x * 1.2 + 0.3, y, WALL_H - 0.012), (1.22, 0.42, 0.02), mat("light frame", "#9A9C9E", rough=0.5), bev=0.003)
            box("light diffuser", (x * 1.2 + 0.3, y, WALL_H - 0.01), (1.16, 0.36, 0.01), mat("light diffuser", "#FFFFFF", rough=0.3, emit=7.0), bev=0.002)
    box("wall band", (0.5, FAR_Y - 0.012, 3.45 * U), (26, 0.024, 0.6 * U), band, bev=0.004)
    box("trim line", (0.5, FAR_Y - 0.012, 1.42), (26, 0.024, 0.035), trim, bev=0.004)
    box("base board", (0.5, FAR_Y - 0.012, 0.045), (26, 0.024, 0.09), base, bev=0.004)
    ivory = mat("sign ivory", rough=0.5)
    text("band sign", "SELF CHECKOUT  →", (2.4, FAR_Y - 0.034, 3.45 * U - 0.1), 0.24, (math.radians(90), 0, 0), ivory, extrude=0.008)
    text("band sign 2", "LANES 1-4", (-2.6, FAR_Y - 0.034, 3.45 * U - 0.09), 0.2, (math.radians(90), 0, 0), ivory, extrude=0.008)
    # the near overhead header over the lane line (the far band is soft and mostly behind the aisles)
    box("header band", (1.2, BACK_Y - 0.03, 2.1), (7.0, 0.05, 0.3), band, bev=0.006)
    text("header sign", "SELF CHECKOUT  →", (1.75, BACK_Y - 0.06, 2.1 - 0.07), 0.17, (math.radians(90), 0, 0), ivory, extrude=0.006)
    text("header sign 2", "LANES 1-4", (-1.4, BACK_Y - 0.06, 2.1 - 0.06), 0.14, (math.radians(90), 0, 0), ivory, extrude=0.006)
    for x in (-2.0, 0.4, 2.8, 4.4):
        cyl("header rod", (x, BACK_Y - 0.03, (2.25 + WALL_H) / 2), 0.006, WALL_H - 2.25, mat("sign pole", rough=0.4, metal=0.6), bev=0)


def aisles(y0=2.3, y1=7.6, xs=(-3.2, -1.8, -0.4, 1.0, 2.4, 3.8, 5.2), seed=5):
    """aisles of shelving receding away from camera behind the near gondola: each a double-sided unit running along
    +y with four planks of product runs on both faces and an end cap, under the ceiling light rows"""
    r = random.Random(seed); root = empty("aisles", (0, 0, 0))
    shelf = mat("shelf", rough=0.5); plank = mat("plank", rough=0.45); strip = mat("price strip", rough=0.6)
    L = y1 - y0; yc = (y0 + y1) / 2; H = 1.7; W = 0.9
    for x in xs:
        box("aisle spine", (x, yc, H / 2), (0.05, L, H), shelf, bev=0.003, parent=root)
        box("aisle base", (x, yc, 0.06), (W, L, 0.12), shelf, bev=0.004, parent=root)
        box("aisle cap", (x, y0 - 0.02, H / 2), (W, 0.04, H), shelf, bev=0.004, parent=root)
        for z in (0.3, 0.72, 1.14, 1.56):
            box("aisle plank", (x, yc, z), (W, L, 0.03), plank, bev=0.003, parent=root)
            for sg in (-1, 1):
                box("aisle strip", (x + sg * W / 2, yc, z - 0.002), (0.006, L, 0.025), strip, bev=0.001, parent=root)
                y = y0 + 0.08
                while y < y1 - 0.2:
                    col = r.choice(PRODUCTS); n = r.randint(3, 7); w = r.choice((0.1, 0.13, 0.16)); h = r.choice((0.16, 0.2, 0.26)); d = r.choice((0.07, 0.09))
                    pm = mat(f"prod {col}", col, rough=0.5)
                    for k in range(n):
                        if y + w > y1 - 0.1: break
                        box("aisle prod", (x + sg * (W / 2 - 0.1), y + w / 2, z + 0.015 + h / 2), (d * 2, w - 0.01, h), pm, bev=0.004, parent=root)
                        y += w
                    y += 0.05
        # end-cap product block facing camera
        col = r.choice(PRODUCTS); pm = mat(f"prod {col}", col, rough=0.5)
        for zz in (0.35, 0.8, 1.25):
            for k in range(3):
                box("cap prod", (x - 0.28 + k * 0.28, y0 - 0.1, zz), (0.22, 0.12, 0.3), pm, bev=0.004, parent=root)
    return root


def ceiling_signs():
    ivory = mat("sign ivory"); navy = mat("sign navy", rough=0.5); rod = mat("sign pole", rough=0.4, metal=0.6)
    root = empty("ceiling signs", (0, 0, 0))
    for x, body in ((-1.35, "EXPRESS LANE"), (0.85, "10 ITEMS OR LESS"), (3.1, "EXIT  →")):
        y, zc = 0.9, 1.3
        box("hanging sign", (x, y, zc), (0.9, 0.025, 0.28), navy, bev=0.006, parent=root)
        box("hanging sign face", (x, y - 0.014, zc), (0.84, 0.004, 0.22), ivory, bev=0.002, parent=root)
        text("hanging sign text", body, (x, y - 0.018, zc), 0.1, (math.radians(90), 0, 0), navy, extrude=0.003, parent=root)
        for sg in (-1, 1):
            cyl("sign rod", (x + sg * 0.35, y, (zc + 0.14 + WALL_H) / 2), 0.006, WALL_H - zc - 0.14, rod, bev=0, parent=root)
    return root


def gondola(x0=-3.5, x1=4.8, door_x=None, seed=3):
    """a shelf run along the back wall, three planks, PRODUCTS in runs of the same item with a label band and a BRAND"""
    r = random.Random(seed)
    shelf = mat("shelf", rough=0.5); plank = mat("plank", rough=0.45); strip = mat("price strip", rough=0.6)
    lid = mat("can lid", rough=0.35, metal=0.9); dark = mat("brand dark", "#1E2430", rough=0.5); light = mat("brand light", "#FBFAF5", rough=0.5)
    root = empty("gondola", (0, 0, 0)); depth = 0.26; y_back = BACK_Y - 0.02
    box("shelf back", ((x0 + x1) / 2, y_back - 0.01, 0.64), (x1 - x0, 0.02, 1.28), shelf, bev=0.003, parent=root)   # low enough to see the aisles over it
    for z in (0.22, 0.66, 1.1):
        box("shelf plank", ((x0 + x1) / 2, y_back - depth / 2, z), (x1 - x0, depth, 0.03), plank, bev=0.004, parent=root)
        yf = y_back - depth
        box("price strip", ((x0 + x1) / 2, yf - 0.004, z - 0.002), (x1 - x0, 0.006, 0.025), strip, bev=0.002, parent=root)
        x = x0 + 0.06; top = z + 0.015
        while x < x1 - 0.14:
            kind = r.choice(("box", "box", "can", "bottle", "box", "jug")); col = r.choice(PRODUCTS); col2 = r.choice(PRODUCTS)
            n = r.randint(2, 5); pm = mat(f"prod {col}", col, rough=0.5); lm = mat(f"prod {col2}", col2, rough=0.5)
            lum = sum(lin(col2)) / 3; ink = dark if lum > 0.2 else light; word = r.choice(BRANDS)
            if kind == "box":
                w, dp, h = r.uniform(0.07, 0.12), r.uniform(0.05, 0.1), r.uniform(0.11, 0.21)
                for k in range(n):
                    if x + w > x1 - 0.06: break
                    box("product", (x + w / 2, yf + 0.08, top + h / 2), (w, dp, h), pm, bev=0.003, parent=root)
                    box("label", (x + w / 2, yf + 0.08 - dp / 2 - 0.001, top + h * 0.55), (w * 0.8, 0.002, h * 0.3), lm, bev=0, parent=root)
                    text("brand", word, (x + w / 2, yf + 0.08 - dp / 2 - 0.0025, top + h * 0.55), min(w * 0.8 / max(3, len(word)) * 1.7, h * 0.16), (math.radians(90), 0, 0), ink, extrude=0.0004, parent=root)
                    x += w + 0.01
            elif kind == "can":
                rr, h = r.uniform(0.03, 0.04), r.uniform(0.08, 0.12)
                for k in range(n):
                    if x + 2 * rr > x1 - 0.06: break
                    cyl("product", (x + rr, yf + 0.08, top + h / 2), rr, h, pm, v=20, parent=root)
                    cyl("can lid", (x + rr, yf + 0.08, top + h), rr * 0.96, 0.006, lid, v=20, bev=0, parent=root)
                    box("label", (x + rr, yf + 0.08 - rr - 0.001, top + h / 2), (rr * 1.3, 0.002, h * 0.45), lm, bev=0, parent=root)
                    text("brand", word, (x + rr, yf + 0.08 - rr - 0.0025, top + h / 2), min(rr * 1.3 / max(3, len(word)) * 1.7, h * 0.2), (math.radians(90), 0, 0), ink, extrude=0.0004, parent=root)
                    x += 2 * rr + 0.008
            elif kind == "bottle":
                rr, h = r.uniform(0.025, 0.035), r.uniform(0.14, 0.2)
                for k in range(n):
                    if x + 2 * rr > x1 - 0.06: break
                    cyl("product", (x + rr, yf + 0.08, top + h / 2), rr, h, pm, v=20, parent=root)
                    cyl("neck", (x + rr, yf + 0.08, top + h + 0.02), rr * 0.45, 0.04, pm, v=16, parent=root)
                    cyl("cap", (x + rr, yf + 0.08, top + h + 0.047), rr * 0.5, 0.015, lm, v=16, parent=root)
                    box("label", (x + rr, yf + 0.08 - rr - 0.001, top + h * 0.45), (rr * 1.4, 0.002, h * 0.35), lm, bev=0, parent=root)
                    text("brand", word, (x + rr, yf + 0.08 - rr - 0.0025, top + h * 0.45), min(rr * 1.4 / max(3, len(word)) * 1.7, h * 0.15), (math.radians(90), 0, 0), ink, extrude=0.0004, parent=root)
                    x += 2 * rr + 0.008
            else:
                w, h = 0.1, r.uniform(0.17, 0.22)
                for k in range(n):
                    if x + w > x1 - 0.06: break
                    box("product", (x + w / 2, yf + 0.09, top + h / 2), (w, 0.1, h), pm, bev=0.012, parent=root)
                    cyl("cap", (x + w / 2, yf + 0.09, top + h + 0.01), 0.022, 0.02, lm, v=16, parent=root)
                    box("label", (x + w / 2, yf + 0.09 - 0.051, top + h * 0.5), (w * 0.7, 0.002, h * 0.35), lm, bev=0, parent=root)
                    text("brand", word, (x + w / 2, yf + 0.09 - 0.0525, top + h * 0.5), min(w * 0.7 / max(3, len(word)) * 1.7, h * 0.14), (math.radians(90), 0, 0), ink, extrude=0.0004, parent=root)
                    x += w + 0.012
            x += r.uniform(0.01, 0.05)
    return root


# ------------------------------------------------------------------ people
PEOPLE = [("crop", "#3A2A20", "#E8B48E", 1.0, 1.0), ("bob", "#1E1A18", "#C68B62", 0.96, 0.95), ("bun", "#6B4A2C", "#F0C9A8", 1.02, 0.97),
          ("crop", "#1A1A1A", "#8A5A3C", 1.04, 1.03), ("bob", "#B8762F", "#F2D4B8", 0.98, 0.96), ("crop", "#2C2C2C", "#5A3A28", 1.0, 1.0)]
_N = [0]


def capsule(name, a, b, r, m, parent=None, seg=24, ra=None, rb=None):
    """a smooth capsule from a to b (world), radius r (ra/rb taper the two ends); one mesh, smooth shaded, no seam"""
    a = Vector(a); b = Vector(b); d = b - a; h = max(1e-4, d.length); ra = ra or r; rb = rb or r
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=ra, radius2=rb, depth=h)
    bmesh.ops.translate(bm, verts=res["verts"], vec=(0, 0, h / 2))
    for z, rr, keep in ((0.0, ra, lambda c: c.z <= 1e-6), (h, rb, lambda c: c.z >= -1e-6)):
        sp = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=12, radius=rr)
        bmesh.ops.translate(bm, verts=sp["verts"], vec=(0, 0, z))
        kill = [v for v in sp["verts"] if not keep(Vector((v.co.x, v.co.y, v.co.z - z)))]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); me.materials.append(m)
    o.location = a; o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    _smooth(o); return _link(o, parent)


def cashier(name, loc, yaw=0.0):
    """a stylised person in the same register as Data: smooth capsules, no seams. Rounded head with a hair cap and a
    simple face (eyes, brows, mouth), neck, a torso with sloped rounded shoulders, an apron with a name tag, arms as
    joined capsules (upper arm, forearm, mitten) bending only at the elbow, legs as joined capsules with shoes.
    Every part is a DIRECT child of the root (the stager hides root.children). Front is -Y; yaw turns it."""
    i = _N[0] % len(PEOPLE); _N[0] += 1
    style, hair_c, skin_c, hs, ws = PEOPLE[i]
    root = empty(name, loc); L = Vector(loc)
    skin = mat(f"skin{i}", skin_c, rough=0.5); hair = mat(f"hair{i}", hair_c, rough=0.7)
    polo = mat("uniform", rough=0.7); apron = mat("apron", rough=0.75); pants = mat("pants", rough=0.75); shoe = mat("shoe", rough=0.45)
    tag = mat("name tag", rough=0.5); white = mat("eye white", rough=0.2); dark = mat("pupil", rough=0.3); lip = mat("lip", rough=0.6)
    H = 1.65 * U * hs; s = H / 0.924
    P = lambda ox, oy, oz: Vector((L.x + ox * ws, L.y + oy, L.z + oz * s))
    # legs: hip -> knee -> ankle, joined at the knee (same radius, the capsule ends overlap), shoes
    for sg in (-1, 1):
        hip = P(sg * 0.06, 0.0, 0.47); knee = P(sg * 0.06, -0.01, 0.26); ank = P(sg * 0.06, 0.0, 0.05)
        capsule("thigh", hip, knee, 0.052 * ws, pants, parent=root); capsule("shin", knee, ank, 0.046 * ws, pants, parent=root, ra=0.05 * ws, rb=0.04 * ws)
        capsule("shoe", P(sg * 0.06, 0.02, 0.028), P(sg * 0.06, -0.11, 0.028), 0.03, shoe, parent=root, ra=0.035, rb=0.028)
    # hips and torso: one tapered capsule hips->chest, a wide flattened cap for the sloped shoulders
    capsule("hips", P(0, 0, 0.44), P(0, 0, 0.56), 0.13 * ws, pants, parent=root, ra=0.125 * ws, rb=0.135 * ws).scale = (1.0, 0.68, 1.0)
    t = capsule("torso", P(0, 0, 0.55), P(0, 0, 0.77), 0.15 * ws, polo, parent=root, ra=0.135 * ws, rb=0.155 * ws); t.scale = (1.0, 0.66, 1.0)
    sh_ = sph("shoulders", P(0, 0, 0.77), 0.155 * ws, polo, scale=(1.0, 0.66, 0.5), parent=root)
    box("apron", P(0, -0.104, 0.585), (0.2 * ws, 0.012, 0.3 * s), apron, bev=0.03, parent=root)
    box("apron bib", P(0, -0.104, 0.75), (0.1 * ws, 0.012, 0.08 * s), apron, bev=0.02, parent=root)
    for sg in (-1, 1):
        capsule("strap", P(sg * 0.04, -0.1, 0.78), P(sg * 0.09, 0.0, 0.8), 0.008, apron, parent=root)
    box("name tag", P(0.08, -0.115, 0.70), (0.05 * ws, 0.005, 0.02 * s), tag, bev=0.002, parent=root)
    # neck and head
    capsule("neck", P(0, 0, 0.77), P(0, 0, 0.84), 0.034 * ws, skin, parent=root)
    sph("head", P(0, 0, 0.905), 0.095, skin, scale=(ws, 0.98, 1.08 * s), parent=root)
    for sg in (-1, 1): sph("ear", P(sg * 0.093, 0.0, 0.9), 0.02, skin, scale=(0.5, 0.8, 1.0), parent=root)
    sph("hair cap", P(0, 0.012, 0.935), 0.1, hair, scale=(1.03 * ws, 1.03, 0.8 * s), parent=root)
    if style == "bob":
        for sg in (-1, 1): capsule("hair side", P(sg * 0.09, 0.01, 0.94), P(sg * 0.092, 0.015, 0.8), 0.028, hair, parent=root)
        capsule("fringe", P(-0.07, -0.085, 0.965), P(0.07, -0.085, 0.965), 0.022, hair, parent=root)
    elif style == "bun":
        sph("bun", P(0, 0.095, 0.955), 0.045, hair, parent=root)
        capsule("fringe", P(-0.02, -0.088, 0.97), P(0.08, -0.08, 0.96), 0.018, hair, parent=root)
    else:
        for sg in (-1, 1): capsule("sideburn", P(sg * 0.092, -0.03, 0.91), P(sg * 0.092, -0.03, 0.86), 0.01, hair, parent=root)
    for sg in (-1, 1):
        sph("eye", P(sg * 0.036, -0.082, 0.91), 0.014, white, parent=root)
        sph("pupil", P(sg * 0.036, -0.094, 0.91), 0.007, dark, parent=root)
        capsule("brow", P(sg * 0.02, -0.088, 0.937), P(sg * 0.054, -0.086, 0.941), 0.004, hair, parent=root)
    capsule("mouth", P(-0.016, -0.093, 0.865), P(0.016, -0.093, 0.865), 0.0035, lip, parent=root)
    # arms: shoulder -> elbow -> wrist, joined at the elbow, bend only there; a mitten hand
    for sg in (-1, 1):
        sh = P(sg * 0.16, 0.0, 0.75); el = P(sg * 0.185, -0.03, 0.56); wr = P(sg * 0.17, -0.14, 0.45)
        capsule("sleeve", sh, sh + (el - sh) * 0.42, 0.05 * ws, polo, parent=root, ra=0.052 * ws, rb=0.045 * ws)
        capsule("upper arm", sh + (el - sh) * 0.3, el, 0.038 * ws, skin, parent=root)
        capsule("forearm", el, wr, 0.038 * ws, skin, parent=root, ra=0.038 * ws, rb=0.032 * ws)
        sph("mitten", wr + Vector((0, -0.02, -0.02)), 0.04 * ws, skin, scale=(0.8, 0.8, 1.1), parent=root)
    root.rotation_euler = (0, 0, yaw)
    return root


# ------------------------------------------------------------------ lanes
def checkout_lane(name, x, number=1, y0=0.32, length=1.5 * U, counter_h=0.9 * U, width=0.52 * U, with_cashier=True):
    """a staffed lane: counter body/top/kick band, belt well + belt + rails + rollers, register with tilted screen, card
    reader + keypad on the customer side, a candy rack at the near end, paper bags on a bagging shelf at the far end, a
    lit lane-number sign on a pole, a bag carousel, the cashier standing beside the counter (x - width*0.78).
    Returns dict(root, counter, cashier, x, kiosk_spot, h). The counter (and everything parented to it) sinks later."""
    root = empty(name, (x, y0, 0))
    cm = mat("counter", rough=0.6); edge = mat("counter edge", rough=0.6); belt = mat("belt", rough=0.65)
    railm = mat("rail", rough=0.4, metal=0.7); regm = mat("register", rough=0.5); scr = mat("reg screen", rough=0.15, emit=0.5)
    counter = empty(name + " counter", (x, y0, 0))
    box("counter body", (x, y0 + length / 2, counter_h / 2 + 0.03), (width, length, counter_h - 0.06), cm, bev=0.02, parent=counter)
    box("counter kick", (x, y0 + length / 2, 0.03), (width - 0.03, length - 0.03, 0.06), edge, bev=0.006, parent=counter)
    box("counter top", (x, y0 + length / 2, counter_h + 0.012), (width + 0.04, length + 0.04, 0.025), edge, bev=0.01, parent=counter)
    bL = length * 0.58; by = y0 + 0.32 + bL / 2
    box("belt well", (x, by, counter_h + 0.016), (width * 0.62, bL + 0.02, 0.02), mat("belt well"), bev=0.003, parent=counter)
    box("belt", (x, by, counter_h + 0.028), (width * 0.56, bL, 0.012), belt, bev=0.004, parent=counter)
    for s in (-1, 1):
        box("belt rail", (x + s * width * 0.31, by, counter_h + 0.045), (0.016, bL + 0.02, 0.04), railm, bev=0.004, parent=counter)
    for yy in (by - bL / 2, by + bL / 2):
        cyl("roller", (x, yy, counter_h + 0.028), 0.012, width * 0.56, railm, rot=(0, math.radians(90), 0), v=16, parent=counter)
    box("register", (x, y0 + 0.16, counter_h + 0.085), (0.2, 0.17, 0.12), regm, bev=0.012, parent=counter)
    fr = box("reg screen frame", (x, y0 + 0.10, counter_h + 0.24), (0.2, 0.025, 0.15), regm, bev=0.006, parent=counter); fr.rotation_euler = (math.radians(-12), 0, 0)
    s_ = box("reg screen", (x, y0 + 0.085, counter_h + 0.245), (0.17, 0.008, 0.12), scr, bev=0.003, parent=counter); s_.rotation_euler = (math.radians(-12), 0, 0)
    box("card reader", (x - width * 0.3, y0 + 0.08, counter_h + 0.06), (0.07, 0.1, 0.07), mat("card reader"), bev=0.006, parent=counter)
    box("keypad", (x - width * 0.3, y0 + 0.055, counter_h + 0.098), (0.05, 0.04, 0.006), mat("keypad"), bev=0.002, parent=counter)
    # candy rack at the near end (customer side)
    rack = mat("rack", rough=0.5)
    box("rack", (x + width * 0.3, y0 + 0.05, 0.3), (0.12, 0.08, 0.55), rack, bev=0.006, parent=counter)
    for k, z in enumerate((0.15, 0.3, 0.45)):
        box("rack shelf", (x + width * 0.3, y0 + 0.02, z), (0.13, 0.05, 0.01), mat("rack shelf"), bev=0.002, parent=counter)
        for j in range(3):
            box("candy", (x + width * 0.3 - 0.04 + j * 0.04, y0 + 0.02, z + 0.03), (0.03, 0.04, 0.05), mat(f"candy{(k + j) % 5}", PRODUCTS[(k * 3 + j) % len(PRODUCTS)], rough=0.5), bev=0.003, parent=counter)
    # bagging shelf with paper bags
    bagm = mat("paper bag", rough=0.8); fold = mat("bag fold", rough=0.8)
    for k in range(2):
        bx = x + (k - 0.5) * 0.11
        box("paper bag", (bx, y0 + length - 0.18, counter_h + 0.1), (0.09, 0.07, 0.17), bagm, bev=0.006, parent=counter)
        box("bag fold", (bx, y0 + length - 0.18, counter_h + 0.19), (0.085, 0.075, 0.015), fold, bev=0.003, parent=counter)
    # lane number sign on a pole, lit
    pole = mat("sign pole", rough=0.4, metal=0.6); signm = mat("lane sign", rough=0.4, emit=1.0); frame = mat("sign frame", rough=0.5)
    cyl("sign pole", (x, y0 + length - 0.1, counter_h + 0.55), 0.012, 1.0, pole, parent=counter)
    box("lane sign frame", (x, y0 + length - 0.1, counter_h + 1.08), (0.22, 0.03, 0.14), frame, bev=0.006, parent=counter)
    box("lane sign", (x, y0 + length - 0.1 - 0.017, counter_h + 1.08), (0.19, 0.004, 0.11), signm, bev=0.002, parent=counter)
    text("lane number", str(number), (x, y0 + length - 0.1 - 0.021, counter_h + 1.08), 0.085, (math.radians(90), 0, 0), frame, extrude=0.002, parent=counter)
    # bag carousel
    wire = mat("rail"); thin = mat("thin bag", rough=0.4)
    cy = y0 + length - 0.17 + 0.22
    cyl("carousel pole", (x + 0.1, cy, counter_h + 0.16), 0.012, 0.32, pole, parent=counter)
    for k in range(4):
        a = k * math.pi / 2; hx, hy = x + 0.1 + 0.07 * math.cos(a), cy + 0.07 * math.sin(a)
        for zz in (counter_h + 0.27, counter_h + 0.14): cyl("hoop", (hx, hy, zz), 0.045, 0.004, wire, v=20, bev=0, parent=counter)
        b = box("thin bag", (hx, hy, counter_h + 0.2), (0.075, 0.075, 0.13), thin, bev=0.008, parent=counter); b.rotation_euler = (0, 0, a)
    box("carousel base", (x + 0.1, cy, counter_h + 0.003), (0.22, 0.22, 0.006), pole, bev=0.002, parent=counter)
    cash = cashier(name + " cashier", (x - width * 0.78, y0 + length * 0.45, 0), yaw=math.radians(90)) if with_cashier else None
    return {"root": root, "counter": counter, "cashier": cash, "x": x, "kiosk_spot": Vector((x, y0 + length * 0.42, 0)), "h": counter_h, "number": number}


def kiosk(name, spot, counter_h=0.9 * U):
    """a self-checkout kiosk that is UNMISTAKABLY not a counter at phone size: a tall charcoal machine (1.3x the
    counter), a big bright screen at Data's eye level angled to camera, a lit SELF CHECKOUT sign on top, a card
    reader and a bagging shelf. Built with its base at z = 0 so the stager can start it below the floor and raise it.
    Returns dict(root, h, screen_mat): the screen's emission is keyed by the stager so it lights up as it arrives."""
    root = empty(name, (spot.x, spot.y, 0))
    body = mat("kiosk body", "#2E3136", rough=0.45); dark = mat("kiosk dark", "#1B1D21", rough=0.5)
    accent = mat("kiosk accent", "#C8643A", rough=0.5); ivory = mat("sign ivory", rough=0.5); navy = mat("sign navy", rough=0.5)
    scr = mat(f"kiosk screen {name}", "#DDEEFF", rough=0.08, emit=0.0)
    scr.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.12, 0.42, 1.0, 1)
    scr.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.1, 0.3, 1)
    H = counter_h * 1.3                                   # 0.655
    box("kiosk base", (spot.x, spot.y, 0.03), (0.4, 0.36, 0.06), dark, bev=0.006, parent=root)
    box("kiosk body", (spot.x, spot.y, H / 2 + 0.03), (0.32, 0.3, H - 0.06), body, bev=0.012, parent=root)
    box("kiosk stripe", (spot.x, spot.y - 0.151, H * 0.5), (0.26, 0.004, 0.03), accent, bev=0.001, parent=root)
    # the screen: big, on top, facing camera (-y), tilted back 18 degrees, centre at about Data's eye level
    zc = H + 0.17
    f = box("kiosk screen frame", (spot.x, spot.y - 0.04, zc), (0.34, 0.035, 0.3), dark, bev=0.006, parent=root); f.rotation_euler = (math.radians(18), 0, 0)
    s_ = box("kiosk screen", (spot.x, spot.y - 0.06, zc), (0.3, 0.006, 0.26), scr, bev=0.002, parent=root); s_.rotation_euler = (math.radians(18), 0, 0)
    ui = box("kiosk ui button", (spot.x, spot.y - 0.064, zc - 0.03), (0.16, 0.003, 0.05), mat("kiosk ui", "#FFFFFF", rough=0.3, emit=0.0), bev=0.004, parent=root); ui.rotation_euler = (math.radians(18), 0, 0)
    tt = text("kiosk ui text", "START", (spot.x, spot.y - 0.067, zc - 0.045), 0.03, (math.radians(72), 0, 0), navy, extrude=0.001, parent=root)
    box("kiosk screen neck", (spot.x, spot.y + 0.02, H + 0.03), (0.08, 0.08, 0.08), dark, bev=0.006, parent=root)
    # the lit sign on top
    box("kiosk sign", (spot.x, spot.y + 0.1, H + 0.38), (0.3, 0.03, 0.09), navy, bev=0.006, parent=root)   # a small lit sign on the machine, no pole
    box("kiosk sign face", (spot.x, spot.y + 0.083, H + 0.38), (0.27, 0.004, 0.065), mat("lane sign", rough=0.4, emit=1.0), bev=0.002, parent=root)
    text("kiosk sign text", "SELF CHECKOUT", (spot.x, spot.y + 0.079, H + 0.38), 0.03, (math.radians(90), 0, 0), navy, extrude=0.002, parent=root)
    # card reader on the near face, bagging shelf with a scale to the +x side
    box("kiosk reader", (spot.x - 0.11, spot.y - 0.17, H - 0.08), (0.07, 0.06, 0.1), dark, bev=0.006, parent=root)
    box("kiosk reader pad", (spot.x - 0.11, spot.y - 0.202, H - 0.07), (0.05, 0.004, 0.04), mat("keypad"), bev=0.001, parent=root)
    box("kiosk shelf", (spot.x + 0.3, spot.y, counter_h - 0.02), (0.3, 0.32, 0.025), body, bev=0.006, parent=root)
    box("kiosk shelf leg", (spot.x + 0.42, spot.y, counter_h / 2 - 0.02), (0.03, 0.03, counter_h - 0.04), dark, bev=0, parent=root)
    box("kiosk scale", (spot.x + 0.3, spot.y, counter_h - 0.0), (0.24, 0.24, 0.012), dark, bev=0.003, parent=root)
    box("kiosk bag", (spot.x + 0.3, spot.y + 0.02, counter_h + 0.08), (0.1, 0.07, 0.16), mat("paper bag"), bev=0.006, parent=root)
    return {"root": root, "h": H + 0.7, "screen_mat": scr}


def cart(name, loc, W=0.22, top=0.32, L=0.42, D=0.24, over=0.10):
    """Data's cart: a wire basket (slats fattened so they don't shimmer), four legs, four wheels, two handle posts and a
    bar barely longer than the basket so his hands grip the ENDS (handle_L at +y, handle_R at -y, both on the bar axis).
    The cart rolls along its +X. Returns dict(root, handle_L, handle_R, wheels, wheel_r, L, W, top, nose)."""
    root = empty(name, loc)
    met = mat("cart metal", rough=0.36, metal=1.0); plas = mat("cart grip", "#2A2B2E", rough=0.45); wheel = mat("wheel", rough=0.5)
    wheel_r = 0.035; bot = top - D; x0 = loc.x; y0 = loc.y
    t = 0.0085
    # floor of the basket and slats
    box("basket floor", (x0 + L / 2, y0, bot), (L, W, 0.006), met, bev=0, parent=root)
    nx = 7; ny = 5
    for k in range(nx + 1):
        xx = x0 + k * L / nx
        for s in (-1, 1): box("slat", (xx, y0 + s * W / 2, (top + bot) / 2), (t, t, D), met, bev=0, parent=root)
        box("slat", (xx, y0, bot + D * 0.02), (t, W, t), met, bev=0, parent=root)
    for k in range(ny + 1):
        yy = y0 - W / 2 + k * W / ny
        box("front slat", (x0 + L, yy, (top + bot) / 2), (t, t, D), met, bev=0, parent=root)
        box("front slat", (x0, yy, (top + bot) / 2), (t, t, D), met, bev=0, parent=root)
    for z in (bot + D * 0.33, bot + D * 0.66, top):
        for s in (-1, 1): box("slat", (x0 + L / 2, y0 + s * W / 2, z), (L, t, t), met, bev=0, parent=root)
        box("front slat", (x0 + L, y0, z), (t, W, t), met, bev=0, parent=root)
        box("front slat", (x0, y0, z), (t, W, t), met, bev=0, parent=root)
    for s in (-1, 1):
        for xx in (x0 + 0.06, x0 + L - 0.06):
            box("leg", (xx, y0 + s * (W / 2 - 0.01), (bot) / 2), (0.014, 0.014, bot), met, bev=0, parent=root)
            cyl("wheel", (xx, y0 + s * (W / 2 + 0.012), wheel_r), wheel_r, 0.018, wheel, rot=(math.radians(90), 0, 0), parent=root)
    hz = top + 0.05          # the posts rise 5 cm above the basket rim so the bar READS clearly above it
    for s in (-1, 1):
        box("post", (x0 - 0.025, y0 + s * (W / 2 - 0.01), (hz + bot) / 2), (0.014, 0.014, hz - bot), met, bev=0, parent=root)
    cyl("handle bar", (x0 - 0.03, y0, hz), 0.014, W + over, plas, rot=(math.radians(90), 0, 0), parent=root)
    for s in (-1, 1):   # rubber end caps, fat enough to read as the rod's end under the mitten when seen end-on
        cyl("bar cap", (x0 - 0.03, y0 + s * (W + over) / 2 - s * 0.012, hz), 0.019, 0.024, plas, rot=(math.radians(90), 0, 0), v=20, parent=root)
        # the handle frame: a tube from the basket rim up to the bar on each side, so side-on the handle has a STRUCTURE
        a = Vector((x0 + 0.10, y0 + s * (W / 2 - 0.01), top)); b = Vector((x0 - 0.03, y0 + s * (W / 2 - 0.01), hz))
        d = b - a; c = cyl("handle strut", ((a + b) / 2), 0.007, d.length, met, v=12, bev=0, parent=root)
        c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    hL = empty(name + " handle_L", (x0 - 0.03, y0 + W / 2, hz), parent=root)
    hR = empty(name + " handle_R", (x0 - 0.03, y0 - W / 2, hz), parent=root)
    nose = empty(name + " nose", (x0 + L, y0, top), parent=root)
    wheels = [o for o in root.children if o.name.startswith("wheel")]
    # goods
    cer = mat("cereal", rough=0.5); cer2 = mat("cereal2", rough=0.5); milk = mat("milk", rough=0.3); cap = mat("milk cap", rough=0.35); ban = mat("banana", rough=0.45)
    ivory = mat("label ivory", "#FFF8EC", rough=0.5); navy = mat("label navy", "#1F3B63", rough=0.5)
    cb = box("cereal box", (x0 + L * 0.62, y0 + 0.02, bot + 0.09), (0.07, 0.14, 0.17), cer, bev=0.003, parent=root)
    box("cereal stripe", (x0 + L * 0.62 - 0.036, y0 + 0.02, bot + 0.05), (0.001, 0.12, 0.05), navy, bev=0, parent=root)
    text("cereal brand front", "OAT CRUNCH", (x0 + L * 0.62 - 0.0365, y0 + 0.02, bot + 0.12), 0.022, (math.radians(90), 0, math.radians(-90)), ivory, extrude=0.0004, parent=root)
    text("cereal brand side", "OAT\nCRUNCH", (x0 + L * 0.62, y0 + 0.02 - 0.071, bot + 0.11), 0.018, (math.radians(90), 0, 0), ivory, extrude=0.0004, parent=root)
    cyl("milk", (x0 + L * 0.3, y0 - 0.03, bot + 0.08), 0.035, 0.16, milk, v=24, parent=root)
    cyl("milk cap", (x0 + L * 0.3, y0 - 0.03, bot + 0.165), 0.02, 0.012, cap, v=16, parent=root)
    box("milk label", (x0 + L * 0.3, y0 - 0.03 - 0.0355, bot + 0.08), (0.05, 0.002, 0.06), cap, bev=0, parent=root)
    text("milk name", "MILK", (x0 + L * 0.3, y0 - 0.03 - 0.037, bot + 0.085), 0.016, (math.radians(90), 0, 0), ivory, extrude=0.0004, parent=root)
    for k in range(3):
        b = cyl("banana", (x0 + L * 0.85, y0 + (k - 1) * 0.022, bot + 0.03), 0.013, 0.12, ban, v=12, rot=(0, math.radians(80), 0.3 * k), parent=root)
    return {"root": root, "handle_L": hL, "handle_R": hR, "wheels": wheels, "wheel_r": wheel_r, "L": L, "W": W, "top": top, "nose": nose}


def contact_shadow(name, loc, rx, ry, parent=None, alpha=0.7):
    m = bpy.data.materials.get("contact shadow")
    if m is None:
        m = bpy.data.materials.new("contact shadow"); m.use_nodes = True; nt = m.node_tree
        for n in list(nt.nodes): nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial"); mixs = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); dif.inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
        tc = nt.nodes.new("ShaderNodeTexCoord"); grad = nt.nodes.new("ShaderNodeTexGradient"); grad.gradient_type = 'SPHERICAL'
        mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-0.5, -0.5, 0); mp.inputs["Scale"].default_value = (1, 1, 1)
        # UV from 0..1 across the plane; spherical gradient from its centre
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeMath"); ramp.operation = 'MULTIPLY'; ramp.inputs[1].default_value = alpha * 2.2
        nt.links.new(grad.outputs["Fac"], ramp.inputs[0]); nt.links.new(ramp.outputs[0], mixs.inputs["Fac"])
        nt.links.new(tr.outputs[0], mixs.inputs[1]); nt.links.new(dif.outputs[0], mixs.inputs[2]); nt.links.new(mixs.outputs[0], out.inputs["Surface"])
        m.blend_method = 'BLEND' if hasattr(m, "blend_method") else None
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); o.location = (loc[0], loc[1], 0.0015); o.scale = (rx * 2, ry * 2, 1)
    o.visible_shadow = False
    return _link(o, parent)


def dressing():
    """floor mat, end-cap pallet with a SALE sign, the floor decal and a dump bin at the left edge (nothing in the foreground may ever cross him or the cart)"""
    box("floor mat", (-1.25, -0.05, 0.004), (0.95, 0.6, 0.008), mat("mat rubber", rough=0.9), bev=0.004)
    box("mat edge", (-1.25, -0.05, 0.0035), (1.0, 0.65, 0.006), mat("mat edge", "#55585E", rough=0.9), bev=0.003)
    ivory = mat("sign ivory"); pal = ["#C6392B", "#E0A62A", "#2F6FB0", "#3F8F5A"]
    box("pallet", (-1.3, 0.95, 0.03), (0.6, 0.45, 0.06), mat("pallet wood", rough=0.8), bev=0.004)
    for r in range(3):
        for c in range(3):
            box("endcap box", (-1.5 + c * 0.19, 0.95, 0.06 + 0.09 + r * 0.19), (0.17, 0.3, 0.18), mat(f"endcap {r}{c}", pal[(r + c) % 4], rough=0.55), bev=0.003)
    box("endcap sign", (-1.3, 0.72, 0.45), (0.3, 0.01, 0.12), ivory, bev=0.002)
    text("endcap text", "SALE", (-1.3, 0.712, 0.45), 0.08, (math.radians(90), 0, 0), mat("sale red", "#C6392B", rough=0.5), extrude=0.002)
    # (the foreground basket stack is GONE: it crossed the cart for two and a half seconds; no prop may ever cover him or the cart)
    # painted floor decal he walks along: SELF CHECKOUT with chevrons, matte paint in the near aisle (y = -0.55)
    paint = mat("floor paint", "#1F3B63", rough=0.85); paint2 = mat("floor paint 2", "#C8643A", rough=0.85)
    text("floor decal", "SELF CHECKOUT", (0.55, -0.62, 0.0015), 0.17, (0, 0, 0), paint, extrude=0.0005)
    # (no chevrons: one decal is enough; the floor was loud)
    # a low dump bin at the left frame edge for the first second, passing in the foreground
    dx, dy = float(os.environ.get("BIN_X", "-1.12")), float(os.environ.get("BIN_Y", "-0.6"))   # a sliver at the left edge in the first half second, never over him
    binm = mat("dump bin", "#3A3D42", rough=0.55); binr = mat("dump bin rim", "#C8643A", rough=0.5)
    box("dump bin", (dx, dy, 0.2), (0.46, 0.46, 0.4), binm, bev=0.02)
    box("dump bin rim", (dx, dy, 0.405), (0.48, 0.48, 0.02), binr, bev=0.006)
    for k in range(9):
        sph("bin ball", (dx + (k % 3 - 1) * 0.13, dy + (k // 3 - 1) * 0.13, 0.41 + (k % 2) * 0.03), 0.07, mat(f"ball{k % 4}", PRODUCTS[k % len(PRODUCTS)], rough=0.4))
    box("bin sign", (dx, dy - 0.245, 0.3), (0.2, 0.006, 0.1), mat("sale red", rough=0.5), bev=0.003)
    text("bin sign text", "2 FOR 1", (dx, dy - 0.25, 0.3), 0.05, (math.radians(90), 0, 0), mat("sign ivory"), extrude=0.001)


def camera(loc, target, lens=30, fstop=8.0):
    cam_d = bpy.data.cameras.new("cam"); cam_d.lens = lens; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36
    cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = fstop; cam_d.dof.focus_distance = (Vector(target) - Vector(loc)).length
    cam = bpy.data.objects.new("cam", cam_d); cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    _link(cam); bpy.context.scene.camera = cam
    return cam


def build_store(set3=True):
    """the whole set; returns dict(lanes, kiosks, extra, cart)"""
    floor(); walls(); ceiling_signs(); gondola(); aisles()
    lanes = [checkout_lane(f"lane{i + 1}", x, number=i + 1) for i, x in enumerate(LANE_X)]
    extra = [checkout_lane("lane_far", FAR_X[0], number=5), checkout_lane("lane_far2", FAR_X[1], number=6)]
    kiosks = [kiosk(f"kiosk{i + 1}", ln["kiosk_spot"], ln["h"]) for i, ln in enumerate(lanes)]
    for kk in kiosks: kk["root"].location.z = -kk["h"] - 0.05
    ct = cart("cart", Vector((-0.6, 0.0, 0)))
    for ln in lanes + extra:
        contact_shadow(ln["counter"].name + " shadow", (ln["x"], 0.32 + 1.5 * U / 2), rx=0.52 * U / 2 + 0.08, ry=1.5 * U / 2 + 0.08, parent=ln["counter"])
        if ln["cashier"] is not None:
            contact_shadow(ln["cashier"].name + " shadow", ln["cashier"].location, rx=0.17, ry=0.12, parent=ln["cashier"])
    cr = ct["root"]
    for w in ct["wheels"]:
        p = w.matrix_world.translation if w.parent is None else w.parent.matrix_world @ w.location
        contact_shadow("wheel shadow", (p.x, p.y), rx=0.05, ry=0.035, parent=cr)
    contact_shadow("cart shadow", (cr.location.x + ct["L"] / 2, cr.location.y), rx=ct["L"] * 0.55, ry=ct["W"] * 0.5, parent=cr)
    dressing()
    return {"lanes": lanes, "kiosks": kiosks, "extra": extra, "cart": ct}
