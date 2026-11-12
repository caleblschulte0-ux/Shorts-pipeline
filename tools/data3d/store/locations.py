"""PLACES other than the store (2026-11-12, caaleb on the second 3D short's stills: "that was way too similar to be the
whole 4 different beats"). Every beat of a 3D short happens somewhere of its own, like the 2D videos cut from scene to
scene; the store is one place among several, not the only stage. The harness (store/shots.py) reads a shot's "env":

  "store"    the approved supermarket and its lights (build_set in the harness)
  "indoor"   a set built here that brings its own lamps (warehouse)
  "outdoor"  a set built here under a sun and a sky (plantation, field, dock)

Each builder returns the set's own lighting call, so a story only says where a beat happens. A story whose beats share
one place is refused by tests/test_data3d_story.py (every beat names its `set` in script.json, and they differ).

Units as scene_kit: metres at Data's scale (he is 0.95 m tall; the world is built at U = 0.56 of adult size).
"""
import math
import random

import bpy
from mathutils import Vector

import scene_kit as K

U = K.U


# ------------------------------------------------------------------ materials
def _noise_mat(name, a, b, scale=4.0, rough=0.85, bump=0.15, detail=6.0):
    """a ground or wall: two colours mixed by a noise, with a bump from the same noise"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.35; rp.color_ramp.elements[1].position = 0.7
    rp.color_ramp.elements[0].color = (*K.lin(a), 1); rp.color_ramp.elements[1].color = (*K.lin(b), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = scale * 12; nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def _ground(name, m, size=(40, 40)):
    return K.box(name, (0, 6, -0.01), (size[0], size[1], 0.02), m, bev=0)


# ------------------------------------------------------------------ light
def _area(name, loc, size, energy, col=(1, 1, 1), aim=(0, 0, 0.5), shape='SQUARE', size_y=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = col; ld.shape = shape; ld.size = size
    if size_y: ld.size_y = size_y
    o = bpy.data.objects.new(name, ld); o.location = loc; bpy.context.collection.objects.link(o)
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def _hero_key():
    """the warm key that follows him (style.follow_key moves it), as in the store"""
    return _area("hero key", (0, -1, 1), 0.9, 7.0, (1.0, 0.93, 0.85))


def sky_light(sun_elev=38, sun_az=-35, sun=3.2, sky=0.22, warm=(1.0, 0.93, 0.82), haze=1.0):
    """a sun and a sky. The sun comes from camera-left-front and above (as the store's key does), so his shadow falls
    to camera-right where it is seen; the sky is a physical sky dimmed to sit under AgX at the store's exposure."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True; nt = w.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    for n in [n for n in nt.nodes if n.type == 'TEX_SKY']: nt.nodes.remove(n)
    sk = nt.nodes.new("ShaderNodeTexSky")
    try: sk.sky_type = 'MULTIPLE_SCATTERING'
    except TypeError: sk.sky_type = 'SINGLE_SCATTERING'
    sk.sun_elevation = math.radians(sun_elev); sk.sun_rotation = math.radians(90 + sun_az); sk.sun_disc = False
    try: sk.air_density = haze; sk.aerosol_density = 1.0 + 2.0 * (haze - 1.0)
    except AttributeError: pass
    nt.links.new(sk.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = sky
    ld = bpy.data.lights.new("sun", 'SUN'); ld.energy = sun; ld.angle = math.radians(2.5); ld.color = warm
    o = bpy.data.objects.new("sun", ld); bpy.context.collection.objects.link(o)
    d = Vector((math.sin(math.radians(sun_az)) * math.cos(math.radians(sun_elev)), -math.cos(math.radians(sun_az)) * math.cos(math.radians(sun_elev)),
                math.sin(math.radians(sun_elev))))          # toward the sun: az 0 = straight behind the camera
    o.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return _hero_key()


def mist(density=0.02, col=(0.85, 0.88, 0.95)):
    """aerial haze. NOT USED: a world volume fills the whole scene and the 1950 plantation test rendered near black
    under it; the far rows go soft through the lens's depth of field instead."""
    sc = bpy.context.scene; nt = sc.world.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    vs = nt.nodes.new("ShaderNodeVolumeScatter"); vs.inputs["Density"].default_value = density; vs.inputs["Color"].default_value = (*col, 1)
    nt.links.new(vs.outputs[0], out.inputs["Volume"])


# ------------------------------------------------------------------ banana trees (shared meshes: a field of them is cheap)
_TREE = {}
def _tree_parts(dead=False):
    key = "dead" if dead else "live"
    if key in _TREE: return _TREE[key]
    import bmesh
    stem_m = _noise_mat(f"tree stem {key}", "#5D7A35" if not dead else "#4A3A22", "#7E9446" if not dead else "#2E2414", scale=3, rough=0.6, bump=0.3)
    leaf_m = _noise_mat(f"tree leaf {key}", "#3F7A2E" if not dead else "#7A6A3A", "#5C9A3A" if not dead else "#3E2E18", scale=2.5, rough=0.5, bump=0.1)
    if dead: leaf_m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    stem = bpy.data.meshes.get("tree stem") or None
    if stem is None:
        o = K.cyl("tree stem tmp", (0, 0, 0.5), 0.5, 1.0, stem_m, v=16, bev=0)
        for v in o.data.vertices: k = 1.0 - 0.35 * (v.co.z + 0.5); v.co.x *= k; v.co.y *= k
        stem = o.data; stem.name = "tree stem"; bpy.data.objects.remove(o)
        if not stem.materials: stem.materials.append(stem_m)
    leaf = bpy.data.meshes.get(f"tree leaf {key}")
    if leaf is None:
        bm = bmesh.new(); n = 16; rows = []
        for i in range(n + 1):
            u = i / n; xx = u; droop = 0.55 if dead else 0.0
            zz = 0.22 * math.sin(u * math.pi * 0.8) - (0.35 + droop) * u * u
            ww = 0.36 * (0.3 + 0.7 * math.sin(min(1.0, u * 1.2) * math.pi * 0.5)) * (1 - 0.7 * max(0, u - 0.82) / 0.18)
            if dead: ww *= 0.7
            rows.append([bm.verts.new((xx, s * ww / 2, zz - abs(s) * 0.03)) for s in (-1, 0, 1)])
        for i in range(n):
            for j in range(2): bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        leaf = bpy.data.meshes.new(f"tree leaf {key}"); bm.to_mesh(leaf); bm.free()
        leaf.materials.append(leaf_m)
        for p in leaf.polygons: p.use_smooth = True
    _TREE[key] = (stem, leaf, stem_m, leaf_m)
    return _TREE[key]


def banana_tree(name, loc, h=1.6, seed=0, dead=False, n_leaves=7):
    """a banana plant at field size: a tapering pseudostem and n long leaves arching out from its top. dead=True: the
    leaves hang brown down the stem (Panama disease: the old leaves collapse at the stalk and skirt the stem)."""
    rnd = random.Random(seed); stem, leaf, stem_m, leaf_m = _tree_parts(dead)
    root = K.empty(name, loc)
    s = bpy.data.objects.new(name + " stem", stem); bpy.context.collection.objects.link(s); s.parent = root
    s.material_slots[0].link = 'OBJECT'; s.material_slots[0].material = stem_m   # one shared mesh, live or dead skin per tree
    s.scale = (0.09 * h, 0.09 * h, h * 0.82); s.location = (0, 0, h * 0.41)
    for k in range(n_leaves):
        a = k * 2 * math.pi / n_leaves + rnd.uniform(-0.3, 0.3)
        lo = bpy.data.objects.new(f"{name} leaf {k}", leaf); bpy.context.collection.objects.link(lo); lo.parent = root
        L = h * rnd.uniform(0.55, 0.75)
        lo.scale = (L, L, L); lo.location = (0, 0, h * rnd.uniform(0.74, 0.86))
        pitch = rnd.uniform(-25, 5) + (55 if dead else 0)
        lo.rotation_euler = (0, math.radians(pitch), a)
    root.rotation_euler.z = rnd.uniform(0, 6.28)
    return root


def tree_rows(x0, x1, y0, y1, dx=0.9, dy=1.0, h=(1.4, 1.9), seed=1, dead_frac=0.0, skip=lambda x, y: False):
    rnd = random.Random(seed); out = []
    y = y0
    while y <= y1:
        x = x0 + rnd.uniform(0, dx * 0.5)
        while x <= x1:
            p = (x + rnd.uniform(-0.15, 0.15), y + rnd.uniform(-0.15, 0.15))
            if not skip(*p):
                out.append(banana_tree(f"tree {len(out)}", (p[0], p[1], 0), h=rnd.uniform(*h), seed=rnd.randint(0, 9999), dead=rnd.random() < dead_frac))
            x += dx
        y += dy
    return out


# ------------------------------------------------------------------ the places
def warehouse():
    """a ripening warehouse: concrete floor, pallet racking down both sides holding the SAME banana box, again and again,
    high-bay lamps going off into the back. Copies of one thing, as far as you can see."""
    floor = _noise_mat("warehouse floor", "#6A6864", "#7A7873", scale=0.6, rough=0.5, bump=0.05)   # sealed concrete: the lighter one burned out white
    K.box("warehouse floor", (0, 5, -0.01), (14, 16, 0.02), floor, bev=0)
    wall = _noise_mat("warehouse wall", "#B8BAB6", "#A9ABA7", scale=1.5, rough=0.8, bump=0.02)
    K.box("warehouse back wall", (0, 11.5, 2.0), (14, 0.2, 4.0), wall, bev=0)
    for sx in (-1, 1): K.box("warehouse side wall", (sx * 6.5, 5, 2.0), (0.2, 16, 4.0), wall, bev=0)
    K.box("warehouse roof", (0, 5, 3.6), (14, 16, 0.05), K.mat("warehouse roof", "#5E6266", rough=0.9), bev=0)
    upr = K.mat("rack upright", "#D9642A", rough=0.5, metal=0.3); beam = K.mat("rack beam", "#2B5C9E", rough=0.45, metal=0.3)
    card = K.mat("banana box card", "#C9A86A", rough=0.85); ink = K.mat("banana box ink", "#1F5FA8", rough=0.6)
    pal = K.mat("pallet wood", "#A88A5E", rough=0.85)
    for sx, x in ((-1, -1.35), (1, 1.65)):
        for y in [0.6 + 1.25 * k for k in range(8)]:
            for dx in (-0.25, 0.25):
                K.box("rack upright", (x + dx, y - 0.6, 1.2), (0.05, 0.05, 2.4), upr, bev=0.004)
                K.box("rack upright", (x + dx, y + 0.6, 1.2), (0.05, 0.05, 2.4), upr, bev=0.004)
            for z in (0.05, 0.85, 1.65):
                K.box("rack beam", (x - 0.25, y, z + 0.06), (0.04, 1.2, 0.08), beam, bev=0.003)
                K.box("rack beam", (x + 0.25, y, z + 0.06), (0.04, 1.2, 0.08), beam, bev=0.003)
                K.box("pallet", (x, y, z + 0.12), (0.5, 1.1, 0.06), pal, bev=0.004)
                for i in range(3):
                    for j in range(2):
                        for kk in range(2):
                            K.box("banana box", (x - 0.12 + 0.24 * j, y - 0.36 + 0.36 * i, z + 0.24 + 0.2 * kk), (0.23, 0.34, 0.19), card, bev=0.008)
                    K.box("banana box band", (x - sx * 0.245, y - 0.36 + 0.36 * i, z + 0.34), (0.006, 0.3, 0.06), ink, bev=0.002)
    lamp = K.mat("high bay", "#FFF6E6", rough=0.3, emit=12.0); shade = K.mat("high bay shade", "#3A3D40", rough=0.4, metal=0.6)
    for y in [0.4 + 1.6 * k for k in range(7)]:
        for x in (-0.6, 0.9):
            K.cyl("high bay shade", (x, y, 3.25), 0.18, 0.14, shade, v=24, bev=0.004)
            K.cyl("high bay lamp", (x, y, 3.175), 0.15, 0.01, lamp, v=24, bev=0)
            _area(f"high bay {x}_{y}", (x, y, 3.15), 0.6, 120, (1.0, 0.94, 0.85), aim=(x, y, 0))

    def light():
        sc = bpy.context.scene; w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (0.35, 0.37, 0.4, 1); bg.inputs["Strength"].default_value = 0.15
        _area("dock door", (-3.0, -3.0, 1.6), 3.0, 150, (0.92, 0.95, 1.0), aim=(0.0, 0.0, 0.6), shape='RECTANGLE', size_y=2.2)   # daylight from the open loading door, camera-left-front
        _area("fill", (3.0, -2.5, 1.3), 2.0, 25, (0.85, 0.9, 1.0), aim=(0.4, 0.3, 0.5))
        return _hero_key()
    return light


def plantation():
    """Central America, 1950: rows of tall Gros Michel plants under a hazy noon sun, a packing table of old boards in
    front of them. Faded and warm: the past."""
    dirt = _noise_mat("plantation dirt", "#8A6E4C", "#6E5A3E", scale=0.8, rough=0.95, bump=0.25)
    _ground("plantation ground", dirt)
    grass = _noise_mat("plantation grass", "#6D7A3E", "#8A8A4E", scale=1.2, rough=0.95, bump=0.3)
    for i, (x, y, r) in enumerate(((-1.6, 1.0, 1.1), (1.9, 1.6, 1.3), (-0.2, 3.5, 2.0), (3.0, 4.5, 1.6), (-3.2, 3.8, 1.5))):
        K.sph(f"grass patch {i}", (x, y, -0.02), 1.0, grass, scale=(r, r * 0.7, 0.04))
    tree_rows(-5, 5, 0.9, 12, dx=1.25, dy=1.3, h=(1.8, 2.4), seed=19, skip=lambda x, y: abs(x) < 1.1 and y < 2.2)
    shed = K.mat("shed boards", "#8E7A5C", rough=0.9); roof = K.mat("shed tin", "#7E7466", rough=0.6, metal=0.4)
    K.box("packing shed back", (2.6, 2.4, 0.9), (2.0, 0.08, 1.8), shed, bev=0.01)
    K.box("packing shed roof", (2.6, 1.9, 1.85), (2.3, 1.2, 0.04), roof, bev=0.006)
    for x in (1.65, 3.55): K.box("shed post", (x, 1.35, 0.9), (0.07, 0.07, 1.8), shed, bev=0.006)

    def light():
        key = sky_light(sun_elev=48, sun_az=-30, sun=3.6, sky=0.28, warm=(1.0, 0.86, 0.66), haze=1.6)
        return key
    return light


def field():
    """a banana farm today: rows of Cavendish going back to the hills, the near ones sick (brown leaves skirting the
    stem), open soil underfoot. Overcast and flat, a cooler light than the 1950 plantation."""
    soil = _noise_mat("field soil", "#5A4430", "#47362A", scale=1.0, rough=0.95, bump=0.35)
    _ground("field ground", soil)
    tree_rows(-5, 5, 0.6, 14, dx=1.1, dy=1.2, h=(1.5, 2.0), seed=31, dead_frac=0.35, skip=lambda x, y: abs(x - 0.1) < 1.0 and y < 1.6)
    hill = _noise_mat("hill", "#4E6A3A", "#6A7E4A", scale=0.3, rough=0.95, bump=0.1)
    for x, r in ((-8, 6), (4, 8), (14, 7)): K.sph("hill", (x, 22, -2.5), 1.0, hill, scale=(r, 3, 4.5))

    def light():
        key = sky_light(sun_elev=30, sun_az=-40, sun=2.4, sky=0.38, warm=(1.0, 0.95, 0.88), haze=2.0)
        return key
    return light


def dock():
    """an export dock in Ecuador: a concrete quay, stacks of shipping containers in faded colours, pallets of ECUADOR
    banana boxes, the sea and a ship's hull behind. Late afternoon sun."""
    quay = _noise_mat("quay concrete", "#9C9890", "#878379", scale=0.7, rough=0.8, bump=0.08)
    K.box("quay", (0, 4, -0.01), (16, 12, 0.02), quay, bev=0)
    K.box("quay edge", (0, 10.0, -0.1), (16, 0.3, 0.2), K.mat("quay edge paint", "#D8B43A", rough=0.7), bev=0.01)
    water = bpy.data.materials.new("sea"); water.use_nodes = True; b = water.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*K.lin("#2E5A6E"), 1); b.inputs["Roughness"].default_value = 0.12
    K.box("sea", (0, 30, -0.4), (80, 40, 0.02), water, bev=0)
    rib = []
    for i, (x, y, z, col, yaw) in enumerate(((-2.4, 3.0, 0, "#B0452E", 0), (-2.4, 3.0, 0.62, "#2F6A8C", 0), (-2.4, 4.4, 0, "#4F7D4A", 0),
                                               (2.8, 3.4, 0, "#2F6A8C", 0), (2.8, 3.4, 0.62, "#C9822E", 0), (2.8, 4.8, 0, "#B0452E", 0),
                                               (2.8, 4.8, 0.62, "#7A7A7A", 0), (-4.6, 5.5, 0, "#C9822E", 0))):
        m = _noise_mat(f"container {col}", col, K.mute(col, 0.35), scale=2.0, rough=0.6, bump=0.05)
        c = K.box(f"container {i}", (x, y, z + 0.31), (2.5, 0.6, 0.6), m, bev=0.01)
        for k in range(16):
            K.box("container rib", (x - 1.18 + k * 0.157, y - 0.305, z + 0.31), (0.03, 0.012, 0.56), m, bev=0.003)
    hull = K.mat("ship hull", "#1E2A36", rough=0.5, metal=0.2)
    K.box("ship hull", (1.0, 13.0, 1.2), (14, 2.5, 2.6), hull, bev=0.05)
    K.box("ship boot top", (1.0, 11.74, 0.12), (14, 0.02, 0.3), K.mat("ship red", "#8A2A24", rough=0.6), bev=0)
    for x in (-3.0, 0.5, 4.0):
        K.box("crane leg", (x, 9.0, 1.8), (0.12, 0.12, 3.6), K.mat("crane", "#C9A23A", rough=0.5, metal=0.3), bev=0.01)

    def light():
        return sky_light(sun_elev=24, sun_az=-45, sun=3.4, sky=0.3, warm=(1.0, 0.86, 0.68), haze=1.3)
    return light


PLACES = {"warehouse": warehouse, "plantation": plantation, "field": field, "dock": dock}
