"""THE LAVA SHORT (the ninth 3D short, 2026-11-23): a volcano keeps erupting beside Grindavik in Iceland; the town ran,
Iceland built walls of rock three stories tall, the wall turned the lava away, then the ground split open inside the
wall. Data is one of the digger drivers who build it: a yellow hard hat and an orange hi-vis vest over his own coat.

  1 hook     grindavik_street  wide      the fissure erupts over the town; he hauls up the road gate and the cars pour out
  2 walls    wall_works        low       at his digger's sticks: its arm swings round and dumps black rock on the wall
  3 holds    wall_crest        high      the lava front slams into the wall below him and slides off along it; his hose
  4 crack    town_crack        tracking  pushing a barrow down a street inside the wall, the road cracks open in front of him
  5 payoff   harbour_dawn      wide      dawn: three houses burn, the rest stand dark; he hangs his lantern at his door

Run through the shot harness (store/shots.py, STORY=lava). Built as drafts (world.py + one file per beat) and inlined
here in story order by build.sh; the world's continuity builders come first (hard hat, lava, earth wall, town house)."""
import locations as LOC


# ====================================================================================================
# world.py
# ====================================================================================================
"""THE DIGGER DRIVER'S WORLD (the lava short): Grindavik on the Reykjanes peninsula, one eruption. What persists from
beat to beat because the STORY carries it (script.json world.continuity), and the materials the town is made of.

  hard_hat(data)             his yellow hard hat (ear holes cut to his ears) and his orange hi-vis vest with silver
                             stripes: the vest is his own coat's chest and hips, a hair outside it, so it moves as his
                             coat moves and never changes his rig
  lava(name, pts, ...)       a lava flow: a sheet of black cracked crust with orange running in every crack, its
                             crust drifting slowly along the flow
  earth_wall(name, path, h)  the defence wall: crushed black rock heaped up in a long ridge with a flat crest
  town_house(name, loc, ...) a low Grindavik house: white or pale clad walls, a coloured tin roof, windows (lit or dark)
  iceland_light(...)         the low northern sun, a clear pale sky, and the soft key that follows him
"""
import random as lw_random
import compose        # frame-first placement (store/compose.py)
from mathutils import Matrix as LW_M
import bmesh as LW_bmesh


LW_U = K.U


def lw_link(o):
    bpy.context.collection.objects.link(o); return o


# ---------------------------------------------------------------- real CC0 assets (Poly Haven, via the data3d-assets branch)
# The coordinator, 2026-11-24: hand-modelled primitives read as toys to every judge. Real scanned skies, textures and
# props come from Poly Haven (CC0), fetched in CI to the orphan branch data3d-assets and unpacked to <repo>/cache/
# polyhaven (the render workflow does it; a session: git archive origin/data3d-assets polyhaven | tar -x -C cache).
# A missing asset RAISES: a silent stand-in is how a "real" world quietly renders as clay again.
import os as LW_os
LW_PH = LW_os.environ.get("POLYHAVEN_DIR") or LW_os.path.join(LW_os.path.dirname(LW_os.path.dirname(LW_os.path.dirname(LW_os.path.dirname(LW_os.path.abspath(K.__file__))))), "cache", "polyhaven")


def ph_path(*parts):
    p = LW_os.path.join(LW_PH, *parts)
    if not LW_os.path.exists(p):
        raise FileNotFoundError(f"Poly Haven asset missing: {p} (add it to .github/triggers/data3d_assets, then unpack data3d-assets into cache/)")
    return p


def ph_sky(aid, strength=1.0, rot=0.0, res="2k"):
    """a real sky: a Poly Haven HDRI as the world, turned `rot` (radians about Z); it lights the scene too"""
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld"); bg = nt.nodes.new("ShaderNodeBackground"); bg.name = "Background"
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(ph_path("hdri", f"{aid}_{res}.hdr"), check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return bg


def ph_mat(aid, scale=1.0, tint=None, name=None, rough=None, bump=1.0, res="1k", paint=False):
    """a real surface: a Poly Haven texture set (colour, normal, roughness) box-projected in object space, `scale`
    metres per tile. tint multiplies the colour (a painted tin wall in this house's colour)."""
    name = name or f"ph {aid} {scale} {tint}"
    m = bpy.data.materials.get(name)
    if m: return m
    d = ph_path(aid, "textures")
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale,) * 3
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    def img(kind, data=True):
        f = LW_os.path.join(d, f"{aid}_{kind}_{res}.jpg")
        if not LW_os.path.exists(f): return None
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(f, check_existing=True); t.projection = 'BOX'; t.projection_blend = 0.2
        if data: t.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
    dif = img("diff", False)
    col = dif.outputs["Color"]
    if tint and paint:                                   # PAINTED: the paint's own colour, the texture's light and dark kept in it
        bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(col, bw.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange"); nt.links.new(bw.outputs[0], mr.inputs["Value"]); mr.clamp = False
        mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 0.35; mr.inputs["To Min"].default_value = 0.45; mr.inputs["To Max"].default_value = 1.0
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        cc = nt.nodes.new("ShaderNodeCombineColor"); [nt.links.new(mr.outputs["Result"], cc.inputs[i]) for i in range(3)]
        nt.links.new(cc.outputs[0], mx.inputs[6]); mx.inputs[7].default_value = (*K.lin(tint), 1); col = mx.outputs[2]
    elif tint:
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        nt.links.new(col, mx.inputs[6]); mx.inputs[7].default_value = (*K.lin(tint), 1); col = mx.outputs[2]
    nt.links.new(col, bs.inputs["Base Color"])
    arm = img("arm"); rg = img("rough")
    if arm:
        sp = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(arm.outputs["Color"], sp.inputs[0])
        nt.links.new(sp.outputs[1], bs.inputs["Roughness"]); nt.links.new(sp.outputs[2], bs.inputs["Metallic"])
    elif rg:
        nt.links.new(rg.outputs["Color"], bs.inputs["Roughness"])
    if paint:                                            # paint is not bare metal
        for l in list(bs.inputs["Metallic"].links): nt.links.remove(l)
        bs.inputs["Metallic"].default_value = 0.0
    if rough is not None:
        for l in list(bs.inputs["Roughness"].links): nt.links.remove(l)
        bs.inputs["Roughness"].default_value = rough
    nor = img("nor_gl")
    if nor:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump
        nt.links.new(nor.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    return m


LW_PH_MODELS = {}


def ph_model(aid, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0, name=None, res="1k", only=None, parent=None):
    """a real prop: a Poly Haven glTF model, imported once and then linked again (same meshes) for every copy, under one
    empty placed at loc/rot/scale. only: keep just the parts whose names start with one of these (a kit holds variants
    laid over each other: the hydrant's new and aged bodies). Each copy is named after the empty. Returns the empty."""
    from mathutils import Euler
    if aid not in LW_PH_MODELS:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=ph_path(aid, f"{aid}_{res}.gltf"))
        objs = [o for o in bpy.data.objects if o not in before]
        for o in objs:
            for c in o.users_collection: c.objects.unlink(o)
        LW_PH_MODELS[aid] = objs
    src = [o for o in LW_PH_MODELS[aid] if not only or any(o.name.split(".")[0] == n_ or o.name.startswith(n_ + ".") for n_ in only)]
    root = K.empty(name or aid, tuple(loc), parent=parent)
    copies = {}
    for o in src:
        c = o.copy(); copies[o] = c; lw_link(c); c.name = f"{root.name} {o.name.split('.')[0]}"
    for o, c in copies.items():
        c.parent = copies.get(o.parent, root)
        if o.parent not in copies: c.matrix_parent_inverse = LW_M.Identity(4)
    root.rotation_euler = Euler(rot); root.scale = (scale,) * 3
    return root


def lw_noise(name, a, b, scale=4.0, rough=0.8, bump=0.2, detail=6.0, stretch=(1, 1, 1), lo=0.35, hi=0.7, coord="Object"):
    """two colours mixed by a noise with a bump from a finer one (any rock, moss or render surface of the town)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = stretch
    nt.links.new(tc.outputs[coord], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = detail
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = lo; rp.color_ramp.elements[1].position = hi
    rp.color_ramp.elements[0].color = (*K.lin(a), 1); rp.color_ramp.elements[1].color = (*K.lin(b), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = scale * 10
    nt.links.new(mp.outputs["Vector"], fine.inputs["Vector"]); nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def lw_local(root):
    """scene_kit builds children at ABSOLUTE positions; a prop built in its own frame makes every child relative"""
    for o in root.children_recursive:
        o.matrix_parent_inverse.identity()
    return root


def lw_fire_mat(name="fire", strength=1.6):
    """flame: pure light, deep red at its roots to orange-yellow in its tongues, the noise stretched up it (a lit
    surface under its own glow bleached to pink in the sun)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (4, 4, 1.2)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); el = rp.color_ramp.elements
    el[0].position = 0.35; el[0].color = (*K.lin("#A01000"), 1); el[1].position = 0.68; el[1].color = (*K.lin("#FFA018"), 1)
    e = el.new(0.5); e.color = (*K.lin("#FF4800"), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def lw_emit(name, hexc, strength):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(hexc), 1); bs.inputs["Emission Color"].default_value = (*K.lin(hexc), 1)
    bs.inputs["Emission Strength"].default_value = strength
    return m


def lw_worn(aid, name, hexc, scale=0.6, rough=None, paint=False):
    """look bible 2026-11-24, one finish across the frame: a prop Data touches wears a REAL scanned surface (Poly Haven)
    tinted to its colour, with the scan's wear, grime and dents, so it sits in the same world as the real set behind it.
    None when the scan is not unpacked (a local run before the asset fetch)."""
    try:
        return ph_mat(aid, scale=scale, tint=hexc, name=name, rough=rough, paint=paint)
    except FileNotFoundError:
        return None


def lw_rubber(name, hexc="#161616", rough=0.85):
    """tyres, grips, hoses, knobs: worn moulded rubber"""
    return lw_worn("rubberized_track", name, hexc, scale=0.25, rough=rough, paint=True) or K.mat(name, hexc, rough=rough)


def lw_wood(name, hexc="#8A7A66", scale=0.8):
    """weathered timber, grain and all"""
    return lw_worn("weathered_planks", name, hexc, scale=scale) or lw_noise(name, "#2E2620", "#4A3E32", scale=14, rough=0.85, bump=0.6, stretch=(1, 1, 6))


def lw_canvas(name, hexc):
    """woven canvas and hessian: a fire hose's jacket, a sandbag"""
    return lw_worn("denim_fabric", name, hexc, scale=0.15, rough=0.9, paint=True) or lw_noise(name, hexc, K.mute(hexc, 0.25), scale=90, rough=0.95, bump=1.0)


def lw_rust(name, hexc="#6A4030"):
    return lw_worn("rust_coarse_01", name, hexc, scale=0.4) or lw_metal(name, hexc, rough=0.7)


def lw_metal(name, hexc, rough=0.35):
    m = bpy.data.materials.get(name)
    if m: return m
    m = lw_worn("metal_plate_02", name, hexc, scale=0.5)        # real scanned steel: scuffs, grime, its own roughness
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(hexc), 1); bs.inputs["Metallic"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough * 0.7; rr.inputs["To Max"].default_value = rough * 1.3
    nt.links.new(nz.outputs["Fac"], rr.inputs["Value"]); nt.links.new(rr.outputs["Result"], bs.inputs["Roughness"])
    return m


def lw_paint(name, hexc, rough=0.45):
    """painted metal or wood: REAL scanned painted metal (Poly Haven), its chips, rust and grime kept under the colour"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = lw_worn("rusty_painted_metal", name, hexc, scale=0.6, rough=None, paint=True)
    if m: return m
    return lw_noise(name, hexc, K.mute(hexc, 0.25), scale=9, rough=rough, bump=0.05, lo=0.3, hi=0.75)


def lw_area(name, loc, aim, energy, size, col=(1.0, 0.96, 0.9), size_y=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = col
    ld.shape = 'RECTANGLE' if size_y else 'SQUARE'; ld.size = size
    if size_y: ld.size_y = size_y
    o = bpy.data.objects.new(name, ld); o.location = loc; bpy.context.collection.objects.link(o)
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def lw_point(name, loc, energy, col=(1.0, 0.55, 0.2), r=0.3):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = energy; ld.color = col; ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld); o.location = loc; bpy.context.collection.objects.link(o)
    return o


def lw_grid(name, x0, x1, y0, y1, nx, ny, zfn, m):
    """a ground patch: a grid whose height is zfn(x, y) (raw geometry, like a box)"""
    bm = LW_bmesh.new(); vs = []
    for j in range(ny + 1):
        vs.append([bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny,
                                 zfn(x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny))) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(m)
    return lw_link(bpy.data.objects.new(name, me))


def lw_vn(x, y, seed=0):
    """smooth value noise, -1..1 (terrain)"""
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 982451653) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    i, j = math.floor(x), math.floor(y); u, v = x - i, y - j
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
    a, b, c, d = h(i, j), h(i + 1, j), h(i, j + 1), h(i + 1, j + 1)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def lw_fbm(x, y, seed=0, oct=4):
    s, a, f = 0.0, 0.5, 1.0
    for k in range(oct):
        s += a * lw_vn(x * f, y * f, seed + k); a *= 0.5; f *= 2.0
    return s


def lava_field_mat(name="lava field"):
    """the old black lava fields round the town: black-brown cinder rock, its hollows furred with grey-green moss"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.92
    tc = nt.nodes.new("ShaderNodeTexCoord")
    rock = nt.nodes.new("ShaderNodeTexNoise"); rock.inputs["Scale"].default_value = 6.0; rock.inputs["Detail"].default_value = 10
    moss = nt.nodes.new("ShaderNodeTexVoronoi"); moss.inputs["Scale"].default_value = 3.0; moss.inputs["Randomness"].default_value = 1.0
    warp = nt.nodes.new("ShaderNodeTexNoise"); warp.inputs["Scale"].default_value = 9.0; warp.inputs["Detail"].default_value = 8
    for n_ in (rock, warp): nt.links.new(tc.outputs["Object"], n_.inputs["Vector"])
    wadd = nt.nodes.new("ShaderNodeVectorMath"); wadd.operation = 'MULTIPLY_ADD'; wadd.inputs[1].default_value = (0.35, 0.35, 0.35)
    nt.links.new(warp.outputs["Color"], wadd.inputs[0]); nt.links.new(tc.outputs["Object"], wadd.inputs[2]); nt.links.new(wadd.outputs["Vector"], moss.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeValToRGB"); rr.color_ramp.elements[0].color = (*K.lin("#110F0E"), 1); rr.color_ramp.elements[1].color = (*K.lin("#33302C"), 1)
    nt.links.new(rock.outputs["Fac"], rr.inputs["Fac"])
    mr = nt.nodes.new("ShaderNodeValToRGB"); mr.color_ramp.elements[0].position = 0.18; mr.color_ramp.elements[1].position = 0.5
    mr.color_ramp.elements[0].color = (0.75, 0.75, 0.75, 1); mr.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(moss.outputs["Distance"], mr.inputs["Fac"])
    mc = nt.nodes.new("ShaderNodeValToRGB"); mc.color_ramp.elements[0].color = (*K.lin("#27301E"), 1); mc.color_ramp.elements[1].color = (*K.lin("#3E4A2C"), 1)
    nt.links.new(warp.outputs["Fac"], mc.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB"); nt.links.new(mr.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(rr.outputs["Color"], mix.inputs["Color1"]); nt.links.new(mc.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.8; bp.inputs["Distance"].default_value = 0.05
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 40; fine.inputs["Detail"].default_value = 12
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"]); nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


LW_BLOCKS = {}


def lw_block(name, loc, r, m, rnd, squash=0.7):
    """one ANGULAR lava block (board round 3: "round shrub blobs", "brown blob-and-green-dot texture"): a coarse
    icosahedron, its corners pulled about, flat-shaded so its faces catch the light as broken rock does. Eight shapes
    are cut once per material and shared, so a slope of a thousand stays light."""
    key = (m.name, rnd.randrange(8))
    me = LW_BLOCKS.get(key)
    if me is None:
        rk = lw_random.Random(sum(map(ord, key[0])) * 8 + key[1])
        bm = LW_bmesh.new(); LW_bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        for v in bm.verts:
            v.co *= rk.uniform(0.7, 1.15); v.co.z = max(v.co.z, -0.35)
        me = bpy.data.meshes.new("lava block"); bm.to_mesh(me); bm.free(); me.materials.append(m)
        for p_ in me.polygons: p_.use_smooth = False
        LW_BLOCKS[key] = me
    o = lw_link(bpy.data.objects.new(name, me)); o.location = loc
    o.scale = (r, r * rnd.uniform(0.7, 1.2), r * squash * rnd.uniform(0.75, 1.2)); o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.3))
    return o


def lava_rock(name, n, area, zfn, seed=0, r=(0.05, 0.25), avoid=None, moss=0.3):
    """loose lava boulders and moss tufts strewn over a patch of ground (x0, x1, y0, y1)"""
    rnd = lw_random.Random(seed)
    m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    mo = lw_noise("moss tuft", "#4C5638", "#6E7850", scale=30, rough=1.0, bump=0.6)
    out = []
    for k in range(n):
        x = rnd.uniform(area[0], area[1]); y = rnd.uniform(area[2], area[3]); rr = rnd.uniform(*r)
        if avoid and avoid(x, y): continue
        if rnd.random() >= moss:
            o = lw_block(name, (x, y, zfn(x, y) + rr * 0.2), rr, m, rnd)
        else:
            o = K.sph(name, (x, y, zfn(x, y) + rr * 0.1), rr * 0.8, mo, scale=(1.0, rnd.uniform(0.7, 1.2), 0.35), seg=10, ring=6)   # a low cushion of moss, not a ball
            o.rotation_euler = (0, 0, rnd.uniform(0, 6.3))
        out.append(o)
    return out


def lw_asphalt(name="asphalt"):
    return lw_noise(name, "#2E2E30", "#4A4A4C", scale=40, rough=0.85, bump=0.25)


def lw_smoke_mat(name="volcano smoke", density=0.6, col=(0.55, 0.52, 0.5), glow=None):
    """a billowing smoke volume for a sphere: dense in the middle, soft and broken at its edge (the falloff is taken in
    the sphere's own 0..1 box, so it works at any radius), optionally lit from inside by a glow colour"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (*col, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-1, -1, -1); mp.inputs["Scale"].default_value = (2, 2, 2)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.2; nz.inputs["Detail"].default_value = 5; nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = 'LENGTH'; nt.links.new(mp.outputs["Vector"], ln.inputs[0])
    edge = nt.nodes.new("ShaderNodeMath"); edge.operation = 'SUBTRACT'; edge.inputs[0].default_value = 1.0; nt.links.new(ln.outputs["Value"], edge.inputs[1])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = 0.8
    nt.links.new(nz.outputs["Fac"], add.inputs[0]); nt.links.new(edge.outputs[0], add.inputs[2]); add.inputs[1].default_value = 0.9
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.55; mr.inputs["From Max"].default_value = 0.9
    mr.inputs["To Max"].default_value = density
    # the billows: a finer noise breaks the density and shades the colour, so a plume reads as rolling cauliflower
    # lumps on a phone, not one smooth beige blob (EMPTY measured shot 1's plume as the bare region)
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 6.5; fine.inputs["Detail"].default_value = 6; fine.inputs["Roughness"].default_value = 0.65
    nt.links.new(mp.outputs["Vector"], fine.inputs["Vector"])
    fadd = nt.nodes.new("ShaderNodeMath"); fadd.operation = 'MULTIPLY_ADD'; fadd.inputs[1].default_value = 0.35
    nt.links.new(fine.outputs["Fac"], fadd.inputs[0]); nt.links.new(add.outputs[0], fadd.inputs[2])
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = 0.17
    nt.links.new(fadd.outputs[0], sub.inputs[0])
    nt.links.new(sub.outputs[0], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], pv.inputs["Density"])
    shade = nt.nodes.new("ShaderNodeValToRGB")
    shade.color_ramp.elements[0].position = 0.3; shade.color_ramp.elements[0].color = (col[0] * 0.45, col[1] * 0.45, col[2] * 0.45, 1)
    shade.color_ramp.elements[1].position = 0.7; shade.color_ramp.elements[1].color = (min(1, col[0] * 1.25), min(1, col[1] * 1.25), min(1, col[2] * 1.25), 1)
    nt.links.new(fine.outputs["Fac"], shade.inputs["Fac"]); nt.links.new(shade.outputs["Color"], pv.inputs["Color"])
    if glow:
        pv.inputs["Emission Color"].default_value = (*glow, 1); pv.inputs["Emission Strength"].default_value = 0.0
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    return m


def lw_fire_vol(name="fire volume", density=3.0, strength=45.0, smoke=(0.9, 0.4, 0.12), scale=2.6):
    """FIRE AS A VOLUME (operator 2026-11-24: "fire as a volume, not cards"): a sphere domain filled with a torn,
    flickering flame: dense and white-yellow hot in its core, orange then deep red toward its ragged edge, with dark
    smoke where it is thin. Density and heat come from one field (the sphere's falloff broken by a noise stretched
    upward), so the flame licks up in tongues. Its Generated coords are the sphere's own 0..1 box: any radius."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    N = nt.nodes.new; L = nt.links.new
    out = N("ShaderNodeOutputMaterial"); pv = N("ShaderNodeVolumePrincipled")
    tc = N("ShaderNodeTexCoord"); mp = N("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-1, -1, -1)
    mp.inputs["Scale"].default_value = (2, 2, 2); L(tc.outputs["Generated"], mp.inputs["Vector"])
    st = N("ShaderNodeMapping"); st.inputs["Scale"].default_value = (scale, scale, scale * 0.45); L(mp.outputs["Vector"], st.inputs["Vector"])
    nz = N("ShaderNodeTexNoise"); nz.noise_dimensions = '4D'; nz.inputs["Scale"].default_value = 1.0; nz.inputs["Detail"].default_value = 7
    nz.inputs["Roughness"].default_value = 0.62; L(st.outputs["Vector"], nz.inputs["Vector"])
    ln = N("ShaderNodeVectorMath"); ln.operation = 'LENGTH'; L(mp.outputs["Vector"], ln.inputs[0])
    edge = N("ShaderNodeMath"); edge.operation = 'SUBTRACT'; edge.inputs[0].default_value = 1.0; L(ln.outputs["Value"], edge.inputs[1])
    f = N("ShaderNodeMath"); f.operation = 'MULTIPLY_ADD'; L(nz.outputs["Fac"], f.inputs[0]); f.inputs[1].default_value = 1.1
    L(edge.outputs[0], f.inputs[2])
    heat = N("ShaderNodeMapRange"); L(f.outputs[0], heat.inputs["Value"]); heat.inputs["From Min"].default_value = 0.62; heat.inputs["From Max"].default_value = 1.25
    dn = N("ShaderNodeMath"); dn.operation = 'MULTIPLY'; L(heat.outputs["Result"], dn.inputs[0]); dn.inputs[1].default_value = density
    L(dn.outputs[0], pv.inputs["Density"])
    rp = N("ShaderNodeValToRGB"); L(heat.outputs["Result"], rp.inputs["Fac"]); el = rp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (*K.lin("#6A0A00"), 1); el[1].position = 1.0; el[1].color = (*K.lin("#FFE7A0"), 1)
    el.new(0.35).color = (*K.lin("#E03000"), 1); el.new(0.7).color = (*K.lin("#FF9A18"), 1)
    L(rp.outputs["Color"], pv.inputs["Emission Color"])
    es = N("ShaderNodeMath"); es.operation = 'POWER'; L(heat.outputs["Result"], es.inputs[0]); es.inputs[1].default_value = 1.6
    em = N("ShaderNodeMath"); em.operation = 'MULTIPLY'; L(es.outputs[0], em.inputs[0]); em.inputs[1].default_value = strength
    L(em.outputs[0], pv.inputs["Emission Strength"])
    pv.inputs["Color"].default_value = (*smoke, 1)
    L(pv.outputs[0], out.inputs["Volume"])
    m["flicker"] = True
    return m


def lw_gas_mat(name="fire gas", smoke=(0.07, 0.065, 0.06), density=2.2, flame=24.0):
    """the material of a SIMULATED fire (lw_fire_sim): Mantaflow's own grids drive it. 'density' is the smoke, dark and
    sooty; 'flame' is the burning fuel, its emission coloured by its heat from deep red through orange to a yellow
    core. Real fire's shape comes from the sim: torn tongues, a rolling column, soot that thins as it climbs."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    N = nt.nodes.new; L = nt.links.new
    out = N("ShaderNodeOutputMaterial"); pv = N("ShaderNodeVolumePrincipled")
    ad = N("ShaderNodeAttribute"); ad.attribute_name = "density"; af = N("ShaderNodeAttribute"); af.attribute_name = "flame"
    dm = N("ShaderNodeMath"); dm.operation = 'MULTIPLY'; dm.inputs[1].default_value = density; L(ad.outputs["Fac"], dm.inputs[0])
    fd = N("ShaderNodeMath"); fd.operation = 'MULTIPLY_ADD'; L(af.outputs["Fac"], fd.inputs[0]); fd.inputs[1].default_value = 1.5; L(dm.outputs[0], fd.inputs[2])
    L(fd.outputs[0], pv.inputs["Density"])
    rp = N("ShaderNodeValToRGB"); L(af.outputs["Fac"], rp.inputs["Fac"]); el = rp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (*K.lin("#3A0500"), 1); el[1].position = 0.85; el[1].color = (*K.lin("#FFD27A"), 1)
    el.new(0.2).color = (*K.lin("#B82000"), 1); el.new(0.5).color = (*K.lin("#FF6A0A"), 1)
    L(rp.outputs["Color"], pv.inputs["Emission Color"])
    pw = N("ShaderNodeMath"); pw.operation = 'POWER'; L(af.outputs["Fac"], pw.inputs[0]); pw.inputs[1].default_value = 1.4
    es = N("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "flame strength"; L(pw.outputs[0], es.inputs[0]); es.inputs[1].default_value = flame
    L(es.outputs[0], pv.inputs["Emission Strength"])
    pv.inputs["Color"].default_value = (*smoke, 1); pv.inputs["Anisotropy"].default_value = 0.3
    L(pv.outputs[0], out.inputs["Volume"])
    return m


def lw_fire_sim(name, emitters, lo, hi, cache, f0=1, f1=None, res=96, fuel=1.4, wind=None, noise=0, mat=None):
    """FIRE AND SMOKE AS A REAL SIMULATION (coordinator 2026-11-24: hand-modelled fire blobs and clay smoke read as
    toys). A Mantaflow gas domain over the box lo..hi, each emitter mesh a fuel inflow that burns (flow BOTH), the
    flame licking up and rolling into a sooty column that climbs, spreads and thins. `wind` (x, y) is a constant
    breeze (a wind force field) that leans the column. Baked to `cache` for frames f0..f1 (the run bakes once, every
    frame reads it). The emitters themselves never render. Returns the domain."""
    f1 = f1 or NF
    lo, hi = Vector(lo), Vector(hi)
    dom = K.box(name, tuple((lo + hi) / 2), tuple(hi - lo), mat or lw_gas_mat(), bev=0.0)
    md = dom.modifiers.new("fluid", 'FLUID'); md.fluid_type = 'DOMAIN'; ds = md.domain_settings
    ds.domain_type = 'GAS'; ds.resolution_max = res; ds.use_adaptive_domain = False
    ds.cache_directory = cache; ds.cache_type = 'ALL'; ds.cache_frame_start = f0; ds.cache_frame_end = f1
    ds.vorticity = 0.25; ds.flame_vorticity = 0.9; ds.burning_rate = 0.8; ds.flame_smoke = 1.6; ds.flame_ignition = 1.25
    ds.flame_max_temp = 3.0; ds.alpha = 0.6; ds.beta = 1.6; ds.use_dissolve_smoke = True; ds.dissolve_speed = 70
    ds.use_dissolve_smoke_log = True; ds.time_scale = 1.0
    if noise:
        ds.use_noise = True; ds.noise_scale = noise; ds.noise_strength = 1.0
    for e in emitters:
        mf = e.modifiers.new("fluid", 'FLUID'); mf.fluid_type = 'FLOW'; fs = mf.flow_settings
        fs.flow_type = 'BOTH'; fs.flow_behavior = 'INFLOW'; fs.flow_source = 'MESH'; fs.surface_distance = 0.08
        fs.fuel_amount = fuel; fs.temperature = 2.0; fs.smoke_color = (0.12, 0.11, 0.1); fs.subframes = 1
        e.hide_render = True
    if wind:
        wd = bpy.data.objects.new(name + " wind", None); lw_link(wd)
        wd.field.type = 'WIND'; wd.field.strength = float(Vector(wind).length); wd.field.flow = 0.0
        wd.location = tuple(lo); wd.rotation_euler = Vector((wind[0], wind[1], 0)).to_track_quat('Z', 'Y').to_euler()
    return dom


def lw_bake(dom):
    """bake a lw_fire_sim domain (headless: the operator needs the domain as the context's object)"""
    sc.frame_set(1)
    with bpy.context.temp_override(scene=sc, object=dom, active_object=dom, selected_objects=[dom], view_layer=bpy.context.view_layer):
        r = bpy.ops.fluid.bake_all()
    return r


class LwNodes:
    """a little expression builder over a node tree: m.add(a, b), m.mul(a, b) ... take sockets or numbers"""
    def __init__(self, nt):
        self.nt = nt

    def _op(self, op, *a):
        n = self.nt.nodes.new("ShaderNodeMath"); n.operation = op
        for i, x in enumerate(a):
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: self.nt.links.new(x, n.inputs[i])
        return n.outputs[0]

    def __getattr__(self, k):
        ops = dict(add='ADD', sub='SUBTRACT', mul='MULTIPLY', div='DIVIDE', mx='MAXIMUM', mn='MINIMUM', pw='POWER',
                   sq='SQRT', ab='ABSOLUTE', mad='MULTIPLY_ADD', sm='SMOOTH_MIN', gt='GREATER_THAN')
        if k in ops: return lambda *a: self._op(ops[k], *a)
        raise AttributeError(k)

    def clamp01(self, x, lo=0.0, hi=1.0):
        n = self.nt.nodes.new("ShaderNodeMapRange"); n.clamp = True
        self.nt.links.new(x, n.inputs["Value"]); n.inputs["From Min"].default_value = lo; n.inputs["From Max"].default_value = hi
        return n.outputs["Result"]


def lw_fire_column(name, base, w=1.6, h_fire=1.6, h_smoke=6.0, lean=(0.0, 0.0), t_end=None, seed=0.0, fire=5.0, smoke_d=3.5,
                   smoke=(0.1, 0.095, 0.09), rise=1.4, keys=None, flame_d=3.9, spread=0.22, grow=False):
    """A BURNING FIRE AND ITS SMOKE as ONE procedural volume (coordinator 2026-11-24: "fire blobs, clay smoke" read as
    toys; the bpy wheel's Mantaflow will not run, so the gas is written as fields, not modelled as spheres). A tall box
    over `base`: the flame is a field of torn TONGUES that narrow as they climb (a cone of heat cut by turbulent noise
    that scrolls upward, so every tongue licks up and breaks off), hot yellow at its root, orange, then deep red at its
    tips; out of its top rolls a SOOT COLUMN that widens as it climbs, leans downwind, billows (domain-warped noise
    advected up at `rise` m/s) and thins away. Nothing in it is a sphere. Returns the volume box."""
    t_end = t_end if t_end is not None else DUR + 1.0
    H = h_fire + h_smoke; lx, ly = lean
    W_ = w * 2.2 + abs(lx) * h_smoke * 2; D_ = w * 2.2 + abs(ly) * h_smoke * 2
    ctr = Vector(base) + Vector((lx * h_smoke * 0.5, ly * h_smoke * 0.5, H / 2))
    m = bpy.data.materials.new(name + " gas"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    N = nt.nodes.new; L = nt.links.new; X = LwNodes(nt)
    out = N("ShaderNodeOutputMaterial"); pv = N("ShaderNodeVolumePrincipled")
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    # object space is metres about the box's centre (K.box builds the mesh at its size): z 0 at the base
    x = X.add(sep.outputs[0], 0.0); y = X.add(sep.outputs[1], 0.0); z = X.add(sep.outputs[2], H / 2)
    # the axis leans downwind as it climbs (quadratically: the smoke bends over)
    zs = X.mul(X.clamp01(X.sub(z, h_fire * 0.6), 0.0, h_smoke), h_smoke)     # (clamp01 is a MapRange: it returns 0..1, so scale back to metres)
    k_ = X.mul(X.mul(zs, zs), 1.0 / max(h_smoke, 0.1))
    ax = X.sub(x, X.add(-lx * h_smoke * 0.5, X.mul(k_, lx))); ay = X.sub(y, X.add(-ly * h_smoke * 0.5, X.mul(k_, ly)))
    # turbulence: noise advected upward (its sample point slides DOWN through the field as time runs, so features rise)
    tt = N("ShaderNodeValue"); tt.name = "fire time"
    cmb = N("ShaderNodeCombineXYZ"); L(ax, cmb.inputs[0]); L(ay, cmb.inputs[1]); L(X.sub(z, X.mul(tt.outputs[0], rise)), cmb.inputs[2])
    def noise(scale, detail=6.0, rough=0.6, wscale=0.6):
        nz = N("ShaderNodeTexNoise"); nz.noise_dimensions = '4D'; nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail; nz.inputs["Roughness"].default_value = rough
        L(cmb.outputs[0], nz.inputs["Vector"]); L(X.add(X.mul(tt.outputs[0], wscale), seed), nz.inputs["W"])
        return nz
    warp = noise(0.9, 3.0, 0.5, 0.35)
    wv = N("ShaderNodeVectorMath"); wv.operation = 'MULTIPLY_ADD'; L(warp.outputs["Color"], wv.inputs[0]); wv.inputs[1].default_value = (0.9, 0.9, 1.2)
    L(cmb.outputs[0], wv.inputs[2])
    def wnoise(scale, detail=6.0, rough=0.62, wscale=0.6):
        nz = N("ShaderNodeTexNoise"); nz.noise_dimensions = '4D'; nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail; nz.inputs["Roughness"].default_value = rough
        L(wv.outputs[0], nz.inputs["Vector"]); L(X.add(X.mul(tt.outputs[0], wscale), seed + 3.1), nz.inputs["W"])
        return nz.outputs["Fac"]
    r = X.sq(X.add(X.mul(ax, ax), X.mul(ay, ay)))
    # THE FLAME: a cone of heat (w/2 at its root, nothing at h_fire) cut into tongues by fast fine noise
    zf = X.div(z, h_fire)
    cone = X.sub(1.0, X.div(r, X.mx(X.mul(X.clamp01(X.sub(1.05, zf)), w * 0.55), 0.002)))      # (a zero divisor reads 0 in a math node: never let it reach one)
    heat = X.sub(X.add(X.mul(wnoise(2.4 / max(w, 0.3), 6.0, 0.7, 1.6), 2.2), X.mul(cone, 0.9)), X.add(0.95, X.mul(zf, 0.7)))
    flame = X.clamp01(heat, 0.0, 0.55)                                 # 0..1
    # THE SMOKE: a widening column out of the flame's top, billowing, thinning as it climbs
    zr = X.clamp01(X.sub(z, h_fire * 0.45), 0.0, h_smoke)          # 0..1 up the column
    rad = X.add(w * 0.35, X.mul(zr, w * 0.35 + h_smoke * spread))
    col = X.sub(1.0, X.div(r, rad))
    bil = X.add(X.mul(wnoise(0.55, 8.0, 0.72, 0.4), 0.7), X.mul(wnoise(1.6, 6.0, 0.6, 0.7), 0.45))     # big billows with smaller curls on them
    sd = X.clamp01(X.sub(X.add(X.mul(bil, 2.2), X.mul(col, 0.9)), 1.55), 0.0, 0.3)
    fade = X.mul(X.clamp01(X.sub(z, h_fire * 0.35), 0.0, h_fire * 0.5), X.sub(1.0, X.clamp01(zr, 0.55, 1.0)))
    amt = N("ShaderNodeValue"); amt.name = "gas amount"; amt.outputs[0].default_value = 1.0      # keyed: a burst comes and goes
    dens = X.mul(X.add(X.mul(X.mul(X.mul(sd, 0.3), fade), smoke_d), X.mul(flame, flame_d)), amt.outputs[0])
    L(dens, pv.inputs["Density"])
    rp = N("ShaderNodeValToRGB"); L(flame, rp.inputs["Fac"]); el = rp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (*K.lin("#4A0800"), 1); el[1].position = 1.0; el[1].color = (*K.lin("#FFE09A"), 1)
    el.new(0.25).color = (*K.lin("#C02400"), 1); el.new(0.55).color = (*K.lin("#FF6A0A"), 1); el.new(0.8).color = (*K.lin("#FFAA30"), 1)
    L(rp.outputs["Color"], pv.inputs["Emission Color"])
    es = N("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "fire strength"; L(X.mul(X.pw(flame, 1.6), amt.outputs[0]), es.inputs[0]); es.inputs[1].default_value = fire
    L(es.outputs[0], pv.inputs["Emission Strength"])
    pv.inputs["Color"].default_value = (*smoke, 1); pv.inputs["Anisotropy"].default_value = 0.2
    L(pv.outputs[0], out.inputs["Volume"])
    o = K.box(name, tuple(ctr), (W_, D_, H), m, bev=0.0)
    o.visible_shadow = True
    for f in (1, F(t_end) + 1):                          # time runs linearly through the shot
        tt.outputs[0].default_value = (f - 1) / FPS; tt.outputs[0].keyframe_insert("default_value", frame=f)
    if keys and keys[0][1] <= 0.0:                       # no gas yet: nothing there at all (no box for a ray or a body to meet)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=max(1, F(keys[0][0])))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=max(1, F(keys[0][0])) + 1)
    for t, v in (keys or ()):                            # how much gas there is when: (t, 0..1), eased between
        amt.outputs[0].default_value = v; amt.outputs[0].keyframe_insert("default_value", frame=F(t))
        if grow:                                         # and the cloud itself swells up out of its base as it comes
            g = 0.3 + 0.7 * v
            o.scale = (g, g, g); o.location = (Vector(base) + Vector((lx * h_smoke * 0.5, ly * h_smoke * 0.5, 0)) * g + Vector((0, 0, H / 2 * g)))
            o.keyframe_insert("scale", frame=F(t)); o.keyframe_insert("location", frame=F(t))
    from character import _fcurves
    for c in _fcurves(nt.animation_data.action):
        if 'nodes["fire time"]' in c.data_path:
            for kp in c.keyframe_points: kp.interpolation = 'LINEAR'
    try:
        m.cycles.volume_step_rate = 2.0                   # a soft gas needs no fine steps: half the render time
    except Exception:
        pass
    return o


def lw_steam(name, base, w=1.2, h=4.0, keys=None, t_end=None, seed=0.0, col=(0.9, 0.91, 0.93), dens=6.0, lean=(0.0, 0.0), rise=2.2, grow=True):
    """a burst of white STEAM (or dust: col) as a gas, not balls: a column that boils up out of `base`, widening and
    thinning, keyed by `keys` [(t, amount)] so it bursts and dies away"""
    return lw_fire_column(name, base, w=w, h_fire=0.3, h_smoke=h, lean=lean, t_end=t_end, seed=seed, fire=0.0, smoke_d=dens,
                          smoke=col, rise=rise, keys=keys, flame_d=0.0, spread=0.3, grow=grow and bool(keys))


def lw_flicker(m, t_end, rate=1.4):
    """key the fire volume's 4D noise so its tongues lick upward and flicker for the whole shot"""
    nz = next(n for n in m.node_tree.nodes if n.type == 'TEX_NOISE')
    for f in (1, NF + 15):
        nz.inputs["W"].default_value = rate * (f - 1) / FPS; nz.inputs["W"].keyframe_insert("default_value", frame=f)
    st = [n for n in m.node_tree.nodes if n.type == 'MAPPING'][1]
    for f in (1, NF + 15):
        st.inputs["Location"].default_value = (0, 0, -1.6 * (f - 1) / FPS); st.inputs["Location"].keyframe_insert("default_value", frame=f)


def lw_flame(name, loc, r, m, scale=(1, 1, 1.6)):
    """one flame: a fire volume in a sphere (taller than wide), casting no shadow, with a warm light inside it"""
    o = K.sph(name, loc, r, m, scale=scale, seg=16, ring=10)
    o.visible_shadow = False
    return o


def lw_puff(name, loc, r, m, scale=(1, 1, 1)):
    """one billow of smoke or steam (a volume ball, soft at its edge)"""
    o = K.sph(name, loc, r, m, scale=scale, seg=16, ring=8)
    o.visible_shadow = False
    return o


def lw_billow_mat(name="ash cloud", col="#5A5550", glow=None):
    """an opaque, soft cloud surface: a billow of ash or steam you can see in daylight (a volume needs many samples and
    reads as nothing on a phone)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.6; nz.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    c = K.lin(col); rp.color_ramp.elements[0].color = (c[0] * 0.6, c[1] * 0.6, c[2] * 0.6, 1); rp.color_ramp.elements[1].color = (min(1, c[0] * 1.5), min(1, c[1] * 1.5), min(1, c[2] * 1.5), 1)
    rp.color_ramp.elements[0].position = 0.35; rp.color_ramp.elements[1].position = 0.7
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 1.0
    if glow:
        bs.inputs["Emission Color"].default_value = (*K.lin(glow), 1); bs.inputs["Emission Strength"].default_value = 0.0
    return m


def lw_billow(name, loc, r, m, seed=0, scale=(1, 1, 1)):
    """one cauliflower billow of an ash or steam cloud: a sphere with lumps"""
    o = K.sph(name, loc, r, m, scale=scale, seg=24, ring=14)
    tx = bpy.data.textures.new(f"{name} lumps", 'CLOUDS'); tx.noise_scale = 0.5 * r; tx.noise_depth = 3; tx.noise_basis = 'VORONOI_F1'
    dm = o.modifiers.new("lumps", 'DISPLACE'); dm.texture = tx; dm.strength = 0.55 * r; dm.texture_coords = 'OBJECT'
    tx2 = bpy.data.textures.new(f"{name} lumps2", 'CLOUDS'); tx2.noise_scale = 0.15 * r
    dm2 = o.modifiers.new("lumps2", 'DISPLACE'); dm2.texture = tx2; dm2.strength = 0.1 * r
    sd = o.modifiers.new("sub", 'SUBSURF'); sd.levels = 0; sd.render_levels = 1
    for p_ in o.data.polygons: p_.use_smooth = True
    o.visible_shadow = False
    return o


def lw_puff_key(o, f, s):
    """key a puff's size at frame f; a puff too small to see is HIDDEN, never scaled to nothing (a volume scaled near
    zero crashes Cycles' openvdb: 'Non-zero scale values required')"""
    s = tuple(s) if not isinstance(s, (int, float)) else (s, s, s)
    small = min(abs(v) for v in s) < 0.06
    o.scale = tuple(max(0.06, abs(v)) for v in s); o.keyframe_insert("scale", frame=f)
    o.hide_render = small; o.keyframe_insert("hide_render", frame=f)


# ---------------------------------------------------------------- the lava
def lava_mat(name="lava", heat=1.0, scale=5.0, glow="#FF4A00", fresh=0.0):
    """lava as it looks: black-grey cracked crust plates, orange-yellow light running in every crack between them and
    the crust's underside glowing through thin spots. `heat` scales the crack glow (fresh 1, cooling 0.3). The crust
    drifts along +local X by the node 'lava flow' (a Mapping's location X), keyed by the shot. `fresh` (0..1) is a front
    still moving: wide glowing seams and big molten patches between thin plates (a cooled field is 0)."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.85
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.name = "lava flow"
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    warp = nt.nodes.new("ShaderNodeTexNoise"); warp.inputs["Scale"].default_value = scale * 0.6; warp.inputs["Detail"].default_value = 3
    nt.links.new(mp.outputs["Vector"], warp.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = (0.25, 0.25, 0.25)
    nt.links.new(warp.outputs["Color"], add.inputs[0]); nt.links.new(mp.outputs["Vector"], add.inputs[2])
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs["Scale"].default_value = scale
    nt.links.new(add.outputs["Vector"], vo.inputs["Vector"])
    crack = nt.nodes.new("ShaderNodeMapRange"); crack.inputs["From Min"].default_value = 0.0; crack.inputs["From Max"].default_value = 0.07 + 0.11 * fresh
    crack.inputs["To Min"].default_value = 1.0; crack.inputs["To Max"].default_value = 0.0
    nt.links.new(vo.outputs["Distance"], crack.inputs["Value"])
    # board round 3: "evenly cracked orange tiles, like a cartoon floor". Real crust breaks into plates of every size
    # with seams that pinch and gape: the seam width wanders with a slow noise, and a finer net of hairline cracks
    # glows dimmer inside each plate
    wid = nt.nodes.new("ShaderNodeTexNoise"); wid.inputs["Scale"].default_value = scale * 0.45; wid.inputs["Detail"].default_value = 2
    nt.links.new(mp.outputs["Vector"], wid.inputs["Vector"])
    wr = nt.nodes.new("ShaderNodeMapRange"); wr.inputs["From Min"].default_value = 0.35; wr.inputs["From Max"].default_value = 0.65
    wr.inputs["To Min"].default_value = 0.015 + 0.04 * fresh; wr.inputs["To Max"].default_value = 0.11 + 0.14 * fresh
    nt.links.new(wid.outputs["Fac"], wr.inputs["Value"]); nt.links.new(wr.outputs["Result"], crack.inputs["From Max"])
    vo2 = nt.nodes.new("ShaderNodeTexVoronoi"); vo2.feature = 'DISTANCE_TO_EDGE'; vo2.inputs["Scale"].default_value = scale * 2.9
    vo2.inputs["Randomness"].default_value = 1.0; nt.links.new(add.outputs["Vector"], vo2.inputs["Vector"])
    hair = nt.nodes.new("ShaderNodeMapRange"); hair.inputs["From Min"].default_value = 0.0; hair.inputs["From Max"].default_value = 0.025
    hair.inputs["To Min"].default_value = 0.45; hair.inputs["To Max"].default_value = 0.0
    nt.links.new(vo2.outputs["Distance"], hair.inputs["Value"])
    hmask = nt.nodes.new("ShaderNodeMath"); hmask.operation = 'MULTIPLY'; nt.links.new(hair.outputs["Result"], hmask.inputs[0])
    nt.links.new(wid.outputs["Fac"], hmask.inputs[1])
    crk = nt.nodes.new("ShaderNodeMath"); crk.operation = 'MAXIMUM'
    nt.links.new(crack.outputs["Result"], crk.inputs[0]); nt.links.new(hmask.outputs[0], crk.inputs[1])
    big = nt.nodes.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = scale * 0.35; nt.links.new(mp.outputs["Vector"], big.inputs["Vector"])
    hot = nt.nodes.new("ShaderNodeMapRange"); hot.inputs["From Min"].default_value = 0.5 - 0.15 * fresh; hot.inputs["From Max"].default_value = 0.75 - 0.1 * fresh
    hot.inputs["To Max"].default_value = 0.35 + 0.5 * fresh
    nt.links.new(big.outputs["Fac"], hot.inputs["Value"])
    glowf = nt.nodes.new("ShaderNodeMath"); glowf.operation = 'MAXIMUM'
    nt.links.new(crk.outputs[0], glowf.inputs[0]); nt.links.new(hot.outputs["Result"], glowf.inputs[1])
    crust = nt.nodes.new("ShaderNodeTexNoise"); crust.inputs["Scale"].default_value = scale * 6; crust.inputs["Detail"].default_value = 8
    nt.links.new(add.outputs["Vector"], crust.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (*K.lin("#141210"), 1); cr.color_ramp.elements[1].color = (*K.lin("#4A4440"), 1)
    nt.links.new(crust.outputs["Fac"], cr.inputs["Fac"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*K.lin("#B02500"), 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (*K.lin("#FFA020"), 1)
    e = ramp.color_ramp.elements.new(0.5); e.color = (*K.lin(glow), 1)
    nt.links.new(glowf.outputs[0], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB"); nt.links.new(glowf.outputs[0], mix.inputs["Fac"])
    nt.links.new(cr.outputs["Color"], mix.inputs["Color1"]); mix.inputs["Color2"].default_value = (*K.lin("#2A0600"), 1)   # the molten part is
    # LIGHT, not paint: a sunlit orange base under its own glow washed every lava in daylight to salmon pink
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bs.inputs["Emission Color"])
    es = nt.nodes.new("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "lava heat"; es.inputs[1].default_value = 1.1 * heat   # brighter than this the view transform bleaches it to salmon
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
    nt.links.new(glowf.outputs[0], pw.inputs[0]); nt.links.new(pw.outputs[0], es.inputs[0])
    nt.links.new(es.outputs[0], bs.inputs["Emission Strength"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.9; bp.inputs["Distance"].default_value = 0.03
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(crack.outputs["Result"], inv.inputs[1])
    hb = nt.nodes.new("ShaderNodeMath"); hb.operation = 'MULTIPLY_ADD'; hb.inputs[2].default_value = 0.0
    nt.links.new(inv.outputs[0], hb.inputs[0]); nt.links.new(crust.outputs["Fac"], hb.inputs[1])
    nt.links.new(hb.outputs[0], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def lava_flow_key(m, t0, t1, speed, axis=0):
    """the crust drifts along the flow (the material's 'lava flow' mapping), slowly, every frame of t0..t1"""
    mp = m.node_tree.nodes["lava flow"]
    for f in range(max(1, F(t0)), F(t1) + 1):
        v = [0.0, 0.0, 0.0]; v[axis] = -speed * ((f - 1) / FPS - t0)
        mp.inputs["Location"].default_value = v; mp.inputs["Location"].keyframe_insert("default_value", frame=f)


def lava(name, outline, z=0.0, thick=0.12, m=None, seed=0, lumpy=0.06, n=40):
    """a lava lobe: the 2D outline (list of (x, y), counter-clockwise) filled and raised into a lumpy slab `thick`
    high with a rounded front, its top broken by lumps. Returns the object (origin at the outline's centre)."""
    m = m or lava_mat()
    cx = sum(p[0] for p in outline) / len(outline); cy = sum(p[1] for p in outline) / len(outline)
    bm = LW_bmesh.new()
    rings = 6
    rows = []
    for k in range(rings + 1):
        s = 1.0 - k / rings                    # 1 at the rim, 0 at the centre
        row = []
        for i, (x, y) in enumerate(outline):
            px, py = cx + (x - cx) * s, cy + (y - cy) * s
            hz = thick * (1 - s ** 3) ** 0.5 if k < rings else thick
            hz += lumpy * lw_vn(px * 3.1, py * 3.1, seed) * (1 - s)
            row.append(bm.verts.new((px - cx, py - cy, z + max(0.0, hz))))
        rows.append(row)
    nb = len(outline)
    for k in range(rings):
        for i in range(nb):
            j = (i + 1) % nb
            bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
    bm.faces.new(list(reversed(rows[rings])))
    LW_bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(m)
    o = lw_link(bpy.data.objects.new(name, me)); o.location = (cx, cy, 0)
    sd = o.modifiers.new("sub", 'SUBSURF'); sd.levels = 1; sd.render_levels = 2
    return o


# ---------------------------------------------------------------- the earth wall
def earth_wall(name, path, h=2.6, crest=0.9, base=5.0, seed=3, n=None):
    """THE DEFENCE WALL: crushed black rock heaped into a long ridge `h` high with a flat crest `crest` wide and a
    base `base` wide, along `path` (a list of (x, y) points, its outer side to the path's left). Rough boulders
    stud its faces. Returns dict(root, body, path, h)."""
    rnd = lw_random.Random(seed)
    root = K.empty(name, (0, 0, 0))
    m = lw_noise("wall rock", "#151413", "#3C3834", scale=7, rough=0.95, bump=1.0, detail=8)     # CRUSHED BLACK ROCK (board: "brown dirt")
    pts = [Vector((p[0], p[1], 0)) for p in path]
    prof = [(-base / 2, 0.0), (-crest / 2 - 0.1, h * 0.97), (-crest / 2, h), (crest / 2, h), (crest / 2 + 0.1, h * 0.97), (base / 2, 0.0)]
    bm = LW_bmesh.new(); rows = []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(len(pts) - 1, i + 1)]
        tg = (b - a).normalized(); nrm = Vector((-tg.y, tg.x, 0))
        row = []
        for k, (u, z) in enumerate(prof):
            j = 0.12 * lw_vn(i * 0.9, k * 1.7, seed) if 0 < k < len(prof) - 1 else 0.0
            q = p + nrm * (u + j) + Vector((0, 0, z + (0.06 * lw_vn(i * 1.3, k, seed + 1) if k in (2, 3) else 0.0)))
            row.append(bm.verts.new(q))
        rows.append(row)
    for i in range(len(rows) - 1):
        for k in range(len(prof) - 1):
            bm.faces.new((rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]))
    bm.faces.new(rows[0]); bm.faces.new(list(reversed(rows[-1])))
    LW_bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    LW_bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
    for v in bm.verts:
        if v.co.z > 0.05:
            v.co.z += 0.08 * lw_vn(v.co.x * 2.3, v.co.y * 2.3, seed + 5)
            v.co.x += 0.05 * lw_vn(v.co.y * 3.1, v.co.z * 3.1, seed + 6)
    me = bpy.data.meshes.new(name + " body"); bm.to_mesh(me); bm.free()
    me.materials.append(m)
    body = lw_link(bpy.data.objects.new(name + " body", me)); body.parent = root
    for k in range(int(len(pts) * 16)):
        i = rnd.randrange(len(pts) - 1); u = rnd.random()
        p = pts[i].lerp(pts[i + 1], u); tg = (pts[i + 1] - pts[i]).normalized(); nrm = Vector((-tg.y, tg.x, 0))
        side = rnd.choice((-1, 1)); fz = rnd.uniform(0.05, 0.85)
        off = (crest / 2 + (base / 2 - crest / 2) * (1 - fz)) * side
        r = rnd.uniform(0.1, 0.32)
        b = lw_block(name + " boulder", tuple(p + nrm * off + Vector((0, 0, h * fz))), r, m, rnd, squash=0.8); b.parent = root
    return dict(root=root, body=body, path=pts, h=h)


# ---------------------------------------------------------------- the town's houses
ROOFS = ("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A", "#9E3A2E", "#2E6F73", "#A8442A")      # red, blue, green tin (board: no purple)
WALLS = ("#F1EEE6", "#BFD3DD", "#E9D9A2", "#B44A3C", "#E6E0D2", "#7E9A86", "#D9C9B4")   # painted tin cladding: white, sky blue, butter, oxide red, sage


def lw_hexmix(a, b, u):
    """two hex colours mixed u of the way from a to b (a hex)"""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(round(x + (y - x) * u)):02X}" for x, y in zip(ca, cb))


def lw_char(m, name, seed=0):
    """a copy of a surface, CHARRED: soot in patches and streaks climbing the wall (worst high up, where the smoke
    rolled out under the eaves), the paint scorched brown at their edges, the rest still its own colour"""
    c = bpy.data.materials.get(name)
    if c: return c
    c = m.copy(); c.name = name; nt = c.node_tree; bs = nt.nodes["Principled BSDF"]
    src = bs.inputs["Base Color"].links[0].from_socket
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 1.0, 0.35)
    mp.inputs["Location"].default_value = (seed * 3.1, seed * 1.7, 0); nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.6; nz.inputs["Detail"].default_value = 6; nz.inputs["Roughness"].default_value = 0.65
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sep.inputs[0])
    up = nt.nodes.new("ShaderNodeMath"); up.operation = 'MULTIPLY_ADD'; nt.links.new(sep.outputs[2], up.inputs[0]); up.inputs[1].default_value = 0.12; up.inputs[2].default_value = 0.0
    t_ = nt.nodes.new("ShaderNodeMath"); t_.operation = 'ADD'; nt.links.new(nz.outputs["Fac"], t_.inputs[0]); nt.links.new(up.outputs[0], t_.inputs[1])
    rp = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(t_.outputs[0], rp.inputs["Fac"]); el = rp.color_ramp.elements
    el[0].position = 0.42; el[0].color = (1, 1, 1, 1); el[1].position = 0.62; el[1].color = (*K.lin("#141110"), 1)
    el.new(0.5).color = (*K.lin("#6A4A30"), 1)
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
    nt.links.new(src, mx.inputs[6]); nt.links.new(rp.outputs["Color"], mx.inputs[7]); nt.links.new(mx.outputs[2], bs.inputs["Base Color"])
    return c


DOORS = ("#EDEBE4", "#2F4A5E", "#8E2E26", "#3E5A3C", "#C9A23A", "#5A4632", "#E6E0D2")


def town_house(name, loc, yaw=0.0, w=None, d=None, h=1.3, roof="#B8352B", wall="#F1EEE6", lit=(), dark_glass=True, seed=0,
               storeys=None, base=None, pitch=None, door=None, burn=0.0):
    """A GRINDAVIK HOUSE, at the world's scale (a storey ~1.3; board after the fire test: "garden sheds or
    dollhouses ... the same white door on each"): a concrete base (a raised ground floor up a flight of steps, or a low
    plinth), one or two storeys of REAL corrugated tin (Poly Haven) painted `wall`, a steep corrugated roof in `roof`,
    a ridge cap, gutters and downpipes, corner boards, a concrete chimney, rows of four-pane windows on the front and
    the gable ends, and a door in its own colour. Size, storeys, base and pitch vary with `seed` unless given.

    burn (0..1): the house is ON FIRE FROM INSIDE: its cladding charred toward soot, its front roof slope broken open
    (strips gone, one caved in, the charred rafters showing), its window panes the fire's own light (one material,
    `<name> window fire`, for the shot to flicker). Built facing -Y about its origin, placed at loc/yaw. Returns
    dict(root, windows, w, d, h, top, hole (world point inside the roof's hole), fire_windows (world points just in front
    of each burning pane, with the outward direction), yaw)."""
    rnd = lw_random.Random(seed * 7919 + 13)
    storeys = storeys or (2 if rnd.random() < 0.55 else 1)
    w = w or rnd.uniform(3.4, 4.6); d = d or rnd.uniform(2.8, 3.4)
    base = base if base is not None else (rnd.choice((0.25, 0.3)) if storeys == 2 else rnd.choice((0.3, 0.75, 0.9)))
    pitch = math.radians(pitch if pitch is not None else rnd.uniform(34, 42))
    door = door or DOORS[rnd.randrange(len(DOORS))]
    if burn:
        wall = lw_hexmix(wall, "#2A2522", 0.25 * burn); roof = lw_hexmix(roof, "#231F1D", 0.45); door = "#1E1A18"
    root = K.empty(name, (0, 0, 0))
    hw = storeys * h; top = base + hw
    conc = ph_mat("concrete_wall_008", scale=1.6, name="house base concrete")
    cl = ph_mat("corrugated_iron_02", scale=1.4, tint=wall, name=f"cladding {wall}", paint=True, rough=0.55)
    rm = ph_mat("corrugated_iron_03", scale=1.2, tint=roof, name=f"tin roof {roof}", paint=True, rough=0.45)
    if burn:
        cl = lw_char(cl, name + " charred cladding", seed); rm = lw_char(rm, name + " charred roof", seed + 1)
    trim = K.mat("house trim char" if burn else "house trim", "#2B2623" if burn else "#F7F5EF", rough=0.5)
    zinc = lw_metal("gutter zinc", "#8E9499")
    K.box(name + " base", (0, 0, base / 2), (w + 0.08, d + 0.08, base), conc, bev=0.01, parent=root)
    K.box(name + " walls", (0, 0, base + hw / 2), (w, d, hw), cl, bev=0.01, parent=root)
    ov = 0.22; run = d / 2 + ov; half = run / math.cos(pitch); gab = math.tan(pitch) * d / 2
    hole = None
    for sg in (-1, 1):
        zc = top + math.tan(pitch) * run / 2 - math.tan(pitch) * ov - 0.01
        broken = burn and sg == -1
        n = 6 if broken else 1
        for k in range(n):
            if broken and k in (2, 3):
                continue                                 # burnt through: two strips gone
            sw = (w + 2 * ov) / n; x = -(w + 2 * ov) / 2 + sw * (k + 0.5)
            r = K.box(name + " roof", (x, sg * run / 2, zc), (sw - (0.01 if broken else 0), half, 0.04), rm, bev=0.005, parent=root)
            r.rotation_euler = (-sg * pitch, 0, 0)
            if broken and k == 4:                        # caved: sagging into the hole
                r.rotation_euler = (-sg * pitch + math.radians(22), math.radians(-8), 0); r.location.z -= 0.25
        if broken:
            sw = (w + 2 * ov) / 6; hx = -(w + 2 * ov) / 2 + sw * 3
            hole = (hx, -d / 4, top + gab * 0.35)
            beam = K.mat("charred beam", "#15110F", rough=0.9)
            for j in range(4):                           # the charred rafters left across the hole
                bx = hx - sw * 0.85 + j * sw * 0.57
                rf = K.box(name + " rafter", (bx, -run / 2 + 0.05, zc - 0.05), (0.07, half * (0.75 + 0.2 * (j % 2)), 0.09), beam, bev=0.0, parent=root)
                rf.rotation_euler = (pitch + (0.25 if j == 2 else 0.0), 0, 0)
    K.box(name + " ridge cap", (0, 0, top + gab + 0.02), (w + 2 * ov, 0.16, 0.05), rm, bev=0.01, parent=root).rotation_euler = (0, 0, 0)
    for sx in (-1, 1):                                   # the gable ends: a triangle of cladding
        bm = LW_bmesh.new()
        a_ = bm.verts.new((sx * w / 2, -d / 2, top)); b_ = bm.verts.new((sx * w / 2, d / 2, top)); c_ = bm.verts.new((sx * w / 2, 0, top + gab))
        bm.faces.new((a_, b_, c_)); me = bpy.data.meshes.new(name + " gable"); bm.to_mesh(me); bm.free(); me.materials.append(cl)
        g = lw_link(bpy.data.objects.new(name + " gable", me)); g.parent = root
        so = g.modifiers.new("t", 'SOLIDIFY'); so.thickness = 0.02
    fire = lw_emit(name + " window fire", "#FF7A1E", 9.0) if burn else None
    glass_dark = K.mat("window glass", "#2B3238" if dark_glass else "#7E8C96", rough=0.08, metal=0.2)
    glass_lit = lw_emit("window lit", "#FFC070", 2.5)
    nwin = max(2, int(round(w / 1.05)))
    xs = [-w / 2 + w * (k + 0.5) / nwin for k in range(nwin)]
    door_x = xs[0] if base < 0.5 else xs[0] + 0.05
    windows = []; fire_windows = []
    def window(x, y, z, face, pane_m, side=False):
        dy = -0.012 if not side else 0.0
        fs = (0.6, 0.03, 0.66) if not side else (0.03, 0.6, 0.66)
        ps = (0.5, 0.01, 0.56) if not side else (0.01, 0.5, 0.56)
        off = Vector((0, -1, 0)) if not side else Vector((face, 0, 0))
        K.box(name + " window frame", tuple(Vector((x, y, z)) + off * 0.01), fs, trim, bev=0.006, parent=root)
        p = K.box(name + " window pane", tuple(Vector((x, y, z)) + off * 0.026), ps, pane_m, bev=0.0, parent=root)
        K.box(name + " window bar", tuple(Vector((x, y, z)) + off * 0.034), (fs[0] * 0.05 + 0.01, fs[1] * 0.05 + 0.01, 0.56) if True else None, trim, bev=0.0, parent=root)
        K.box(name + " window bar", tuple(Vector((x, y, z + 0.06)) + off * 0.034), (ps[0] + 0.005 if not side else 0.01, ps[1] + 0.005 if side else 0.01, 0.025), trim, bev=0.0, parent=root)
        K.box(name + " sill", tuple(Vector((x, y, z - 0.35)) + off * 0.035), (0.68 if not side else 0.07, 0.07 if not side else 0.68, 0.03), trim, bev=0.004, parent=root)
        return p
    for st in range(storeys):
        zc = base + st * h + h * 0.55
        for k, x in enumerate(xs):
            if st == 0 and k == 0:
                continue                                 # the door's bay
            idx = len(windows)
            on_fire = burn and (st == storeys - 1 or rnd.random() < 0.6)
            pm = fire if on_fire else (glass_lit if idx in lit else glass_dark)
            p = window(x, -d / 2, zc, -1, pm)
            windows.append(p)
            if on_fire:
                fire_windows.append(((x, -d / 2 - 0.08, zc - 0.28), (0, -1, 0)))
        for sx in (-1, 1):                               # one window in each gable end per storey
            window(sx * (w / 2 + 0.012), 0.0, zc, sx, fire if burn else glass_dark, side=True)
    zd = base + 0.5
    K.box(name + " door", (door_x, -d / 2 - 0.015, zd), (0.5, 0.03, 1.0), K.mat(f"house door {door}", door, rough=0.45), bev=0.008, parent=root)
    K.box(name + " door frame", (door_x, -d / 2 - 0.008, zd + 0.02), (0.6, 0.02, 1.08), trim, bev=0.004, parent=root)
    K.cyl(name + " door knob", (door_x + 0.17, -d / 2 - 0.04, zd - 0.02), 0.02, 0.025, lw_metal("knob brass", "#B8903A"), rot=(math.pi / 2, 0, 0), parent=root)
    nst = max(1, int(round(base / 0.17)))
    for k in range(nst):                                 # the steps up to a raised ground floor
        K.box(name + " step", (door_x, -d / 2 - 0.08 - 0.27 * (nst - 1 - k) - 0.14, (k + 1) * base / nst / 2), (0.8, 0.28 + 0.27 * (nst - 1 - k) * 0 + 0.02, (k + 1) * base / nst), conc, bev=0.006, parent=root)
    if base > 0.5:
        for sx in (-1, 1):
            K.cyl(name + " rail", (door_x + sx * 0.38, -d / 2 - 0.08 - 0.14 * nst, base + 0.45), 0.015, 0.9, zinc, v=8, parent=root)
    ch = K.box(name + " chimney", (w * rnd.choice((-0.28, 0.3)), 0.25, top + gab * 0.75), (0.32, 0.32, gab * 0.5 + 0.7), conc, bev=0.01, parent=root)
    for cx in (-1, 1):
        for cy in (-1, 1):
            K.box(name + " corner board", (cx * (w / 2 + 0.01), cy * (d / 2 + 0.01), base + hw / 2), (0.06, 0.06, hw), trim, bev=0.004, parent=root)
    for sg in (-1, 1):
        K.box(name + " fascia", (0, sg * (d / 2 + ov - 0.02), top - 0.06), (w + 2 * ov, 0.03, 0.1), trim, bev=0.004, parent=root)
        K.cyl(name + " gutter", (0, sg * (d / 2 + ov + 0.02), top - 0.12), 0.045, w + 2 * ov, zinc, rot=(0, math.pi / 2, 0), v=10, parent=root)
        K.cyl(name + " downpipe", (sg * (w / 2 + ov - 0.07), -(d / 2 + ov + 0.02), top / 2), 0.03, top - 0.1, zinc, v=8, parent=root)
    lw_local(root)
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    Mw = LW_M.Translation(Vector(loc)) @ LW_M.Rotation(yaw, 4, 'Z')
    R = LW_M.Rotation(yaw, 3, 'Z')
    return dict(root=root, windows=windows, w=w, d=d, h=h, top=top, gab=gab, yaw=yaw, storeys=storeys, base=base,
                hole=(Mw @ Vector(hole)) if hole else None,
                fire_windows=[(Mw @ Vector(p), R @ Vector(o)) for p, o in fire_windows])


def lw_house_fire(hs, seed=0, t_end=None, fire=5.0):
    """a house burning FROM INSIDE (board: "fire sits ON the roofs like candle flames"): the blaze comes up through the
    hole in its roof and rolls into a soot column, flames lick out of its upper windows and up the charred cladding,
    and the fire's light falls warm on the ground and the neighbouring walls, flickering. Needs a town_house built with
    burn>0. Returns the list of what it made (volumes and lights)."""
    rnd = lw_random.Random(seed)
    t_end = t_end if t_end is not None else DUR + 1.0
    out = []
    hp = hs["hole"]
    out.append(lw_fire_column(hs["root"].name + " blaze", (hp.x, hp.y + 0.3, hp.z - 1.2), w=2.6, h_fire=3.4, h_smoke=9.0,
                              lean=(-0.6, 0.25), t_end=t_end, seed=seed * 3.7 + 1.0, fire=fire * 1.4, smoke_d=3.5))
    for k, (p, o) in enumerate(hs["fire_windows"]):
        if p.z < hs["root"].location.z + hs["top"] - hs["h"] - 0.05:
            continue                                     # the flames come out of the top storey's windows
        out.append(lw_fire_column(hs["root"].name + f" window flame {k}", (p.x + o.x * 0.08, p.y + o.y * 0.08, p.z), w=0.85, h_fire=1.5,
                                  h_smoke=1.8, lean=(o.x * 0.25, o.y * 0.25), t_end=t_end, seed=seed * 5.3 + k, fire=fire * 1.6, smoke_d=2.4, rise=1.8))
        out.append(lw_point(hs["root"].name + f" window light {k}", tuple(p + o * 0.7 + Vector((0, 0, 0.3))), 160.0, col=(1.0, 0.45, 0.15), r=0.25))
    out.append(lw_point(hs["root"].name + " blaze light", (hp.x, hp.y - 0.4, hp.z + 1.0), 1400.0, col=(1.0, 0.45, 0.15), r=0.6))
    wf = bpy.data.materials.get(hs["root"].name + " window fire")
    lights = [o for o in out if o.type == 'LIGHT']
    for f in range(1, F(t_end) + 2, 2):                 # the flicker: every light and every burning pane, out of step
        t = (f - 1) / FPS
        for j, L in enumerate(lights):
            e0 = L.get("e0") or L.data.energy; L["e0"] = e0
            q = 1 + 0.22 * math.sin(2 * math.pi * (2.7 + 0.4 * j) * t + 1.7 * j + seed) + 0.12 * math.sin(2 * math.pi * 7.1 * t + j)
            L.data.energy = e0 * q; L.data.keyframe_insert("energy", frame=f)
        if wf:
            em = next(n for n in wf.node_tree.nodes if n.type == 'EMISSION' or n.type == 'BSDF_PRINCIPLED')
            inp = em.inputs.get("Emission Strength") or em.inputs.get("Strength")
            s0 = wf.get("s0") or inp.default_value; wf["s0"] = s0
            inp.default_value = s0 * (1 + 0.3 * math.sin(2 * math.pi * 3.3 * t + seed) + 0.15 * math.sin(2 * math.pi * 8.3 * t)); inp.keyframe_insert("default_value", frame=f)
    return out


# ---------------------------------------------------------------- the hard hat and the hi-vis vest
LW_HAT_ZB = 0.80


def lw_head_z(x, y):
    q = 1 - (x / 0.186) ** 2 - (y / 0.138) ** 2
    return 0.705 + 0.172 * math.sqrt(q) if q > 0 else -1.0


def lw_hat_mesh(to_world, ears):
    """a hard hat built ON his head (his rest frame, facing -Y): a domed shell with a raised ridge down its middle, a
    short rim all round and a peak at the front, cut round his ears"""
    from mathutils import Vector as V
    A = (0.168, 0.136); H = 0.2; n = 64              # a real hard hat's crown: tall enough that his ears sit INSIDE it (board: "antennae poke through the hat")
    verts, faces, rows = [], [], []
    rhos = [0.0, 0.1, 0.22, 0.35, 0.48, 0.6, 0.72, 0.82, 0.9, 0.95, 0.985, 1.0]
    for rho in rhos:
        row = []
        for i in range(n if rho > 0 else 1):
            th = 2 * math.pi * i / n; x, y = A[0] * rho * math.cos(th), A[1] * rho * math.sin(th)
            z = LW_HAT_ZB + H * math.sqrt(max(0.0, 1 - rho ** 3.5)) + 0.012 * math.exp(-(x / 0.03) ** 2) * (1 - rho ** 4)
            z = max(z, lw_head_z(x, y) + 0.014)
            verts.append((x, y, z)); row.append(len(verts) - 1)
        rows.append(row)
    for k in range(4):                                  # the rim: short at the sides and back, a peak at the front
        u = (k + 1) / 4; row = []
        for i in range(n):
            th = 2 * math.pi * i / n
            front = max(0.0, -math.sin(th)) ** 2
            out = 0.018 + 0.05 * front
            verts.append(((A[0] + out * u) * math.cos(th), (A[1] + out * u) * math.sin(th), LW_HAT_ZB - 0.004 * u + 0.012 * u * front))
            row.append(len(verts) - 1)
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append((a[0], b[i], b[j]) if len(a) == 1 else (a[i], b[i], b[j], a[j]))
    keep = []
    for f in faces:
        c = sum((V(verts[v]) for v in f), V()) / len(f); cw = to_world @ c; out = True
        for tr in ears:
            loc, nor, _i, d = tr.find_nearest(cw)
            if loc is not None and ((cw - loc).dot(nor) < 0 or d < 0.011): out = False
        if out: keep.append(f)
    used = sorted({v for f in keep for v in f}); remap = {v: i for i, v in enumerate(used)}
    me = bpy.data.meshes.new("hard hat")
    me.from_pydata([tuple(V(verts[v]) - V((0, 0, LW_HAT_ZB))) for v in used], [], [tuple(remap[v] for v in f) for f in keep]); me.update()
    m = bpy.data.materials.get("hard hat yellow")
    if not m:
        m = bpy.data.materials.new("hard hat yellow"); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = (*K.lin("#F0A800"), 1); bs.inputs["Roughness"].default_value = 0.3
        bs.inputs["Coat Weight"].default_value = 0.4; bs.inputs["Coat Roughness"].default_value = 0.15
    me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    return me


def hivis_mat(name="hi-vis vest"):
    """fluorescent orange with two silver reflective bands round the body (object-space height bands)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sp.inputs[0])
    band = None
    for z0, z1 in ((1.27, 1.40), (1.61, 1.74)):          # the coat mesh's own z (rig units): a band at his waist, one at his chest
        a = nt.nodes.new("ShaderNodeMath"); a.operation = 'GREATER_THAN'; a.inputs[1].default_value = z0
        b = nt.nodes.new("ShaderNodeMath"); b.operation = 'LESS_THAN'; b.inputs[1].default_value = z1
        nt.links.new(sp.outputs[2], a.inputs[0]); nt.links.new(sp.outputs[2], b.inputs[0])
        ab = nt.nodes.new("ShaderNodeMath"); ab.operation = 'MULTIPLY'; nt.links.new(a.outputs[0], ab.inputs[0]); nt.links.new(b.outputs[0], ab.inputs[1])
        if band is None: band = ab
        else:
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = 'MAXIMUM'; nt.links.new(band.outputs[0], mx.inputs[0]); nt.links.new(ab.outputs[0], mx.inputs[1]); band = mx
    col = nt.nodes.new("ShaderNodeMixRGB"); nt.links.new(band.outputs[0], col.inputs["Fac"])
    col.inputs["Color1"].default_value = (*K.lin("#FF4A00"), 1); col.inputs["Color2"].default_value = (*K.lin("#D9DCDF"), 1)
    nt.links.new(col.outputs["Color"], bs.inputs["Base Color"])
    rg = nt.nodes.new("ShaderNodeMapRange"); rg.inputs["To Min"].default_value = 0.75; rg.inputs["To Max"].default_value = 0.25
    nt.links.new(band.outputs[0], rg.inputs["Value"]); nt.links.new(rg.outputs["Result"], bs.inputs["Roughness"])
    mt = nt.nodes.new("ShaderNodeMapRange"); mt.inputs["To Max"].default_value = 0.6
    nt.links.new(band.outputs[0], mt.inputs["Value"]); nt.links.new(mt.outputs["Result"], bs.inputs["Metallic"])
    em = nt.nodes.new("ShaderNodeMapRange"); em.inputs["To Min"].default_value = 0.06; em.inputs["To Max"].default_value = 0.0
    nt.links.new(band.outputs[0], em.inputs["Value"]); nt.links.new(em.outputs["Result"], bs.inputs["Emission Strength"])
    bs.inputs["Emission Color"].default_value = (*K.lin("#FF6A0D"), 1)
    return m


def hard_hat(data, name="hard hat"):
    """HIS KIT: the yellow hard hat on his head (parented to the head bone, cut round his ears) and the orange hi-vis
    vest with two silver bands. The vest is a copy of his own coat's mesh between his hips and his chest, pushed a few
    millimetres out along its normals and opened down the front, deformed by the same armature: so it moves as his coat
    moves and his rig is untouched. Call right after load_data() and data.place(), before any animation."""
    from mathutils.bvhtree import BVHTree as BVH
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ears = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith("Ear") and o.parent == data.arm:
            ev = o.evaluated_get(dg); me = ev.to_mesh()
            ears.append(BVH.FromPolygons([o.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]))
            ev.to_mesh_clear()
    rest = LW_M.Translation(data.arm.location) @ LW_M.Rotation(data.arm.rotation_euler.z, 4, 'Z')
    worn = lw_link(bpy.data.objects.new(name, lw_hat_mesh(rest, ears)))
    sd = worn.modifiers.new("shell", 'SOLIDIFY'); sd.thickness = 0.006; sd.offset = 1.0
    worn.parent = data.arm; worn.parent_type = 'BONE'; worn.parent_bone = "head"
    bpy.context.view_layer.update()
    pbh = data.pb["head"]
    worn.matrix_parent_inverse = (data.arm.matrix_world @ pbh.matrix @ LW_M.Translation((0, pbh.bone.length, 0))).inverted()
    worn.matrix_basis = rest @ LW_M.Translation((0, 0, LW_HAT_ZB))
    # the vest: his coat's own mesh, hips to chest, a hair outside it
    coat = next(o for o in data.parts if o.name.startswith("Coat / continuous"))
    me = coat.data.copy(); me.name = "Coat hivis vest"
    bm = LW_bmesh.new(); bm.from_mesh(me)
    zs = [v.co.z * coat.scale.z + coat.location.z for v in bm.verts]
    z_lo, z_hi = 1.15, 2.5                               # the coat's rings (rig units): his hips (1.19) to his shoulders (2.46)
    drop = [v for v, z in zip(bm.verts, zs) if z < z_lo or z > z_hi]
    xs = [abs(v.co.x) for v in bm.verts]; front = min(v.co.y for v in bm.verts)
    drop += [v for v in bm.verts if abs(v.co.x) * coat.scale.x < 0.075 and v.co.y < 0 and v not in drop]   # open down the front
    LW_bmesh.ops.delete(bm, geom=list(set(drop)), context='VERTS')
    bm.to_mesh(me); bm.free()
    me.materials.clear(); me.materials.append(hivis_mat())
    vest = bpy.data.objects.new("Coat hivis vest", me); lw_link(vest)
    vest.parent = coat.parent; vest.matrix_parent_inverse = coat.matrix_parent_inverse.copy()
    vest.location = coat.location; vest.rotation_euler = coat.rotation_euler; vest.scale = coat.scale
    for g in coat.vertex_groups:
        if g.name not in vest.vertex_groups: vest.vertex_groups.new(name=g.name)
    ss = vest.modifiers.new("smooth", 'SUBSURF'); ss.levels = 2; ss.render_levels = 2
    disp = vest.modifiers.new("out", 'DISPLACE'); disp.strength = 0.045; disp.mid_level = 0.0      # rig units: ~9 mm out
    so = vest.modifiers.new("cloth", 'SOLIDIFY'); so.thickness = 0.02; so.offset = 1.0
    arm_md = vest.modifiers.new("Rig", 'ARMATURE'); arm_md.object = data.arm
    while vest.modifiers[0] != arm_md: vest.modifiers.move(len(vest.modifiers) - 1, 0)
    data.parts.append(vest)
    return dict(worn=worn, vest=vest)


# ---------------------------------------------------------------- the light
def iceland_light(sun_elev=14, sun_az=-35, sun=3.4, sky=0.4, warm=(1.0, 0.86, 0.7), haze=1.4):
    """the low northern sun: long, warm, from camera-left-front; a pale clear sky; the key that follows him"""
    return LOC.sky_light(sun_elev=sun_elev, sun_az=sun_az, sun=sun, sky=sky, warm=warm, haze=haze)


def lw_clouds(cover=0.55, scale=0.9, drift=(0.03, 0.02)):
    """broken Icelandic cloud over the physical sky (iceland_light's): a deck projected overhead, lit by the sky's own
    brightness so it stays in the same exposure, grey-bellied where it is thick, drifting. A clear sky is one smooth
    gradient, which reads as a bare set (store/empty.py); a real sky over Grindavik has weather in it."""
    nt = sc.world.node_tree; N = nt.nodes.new; L = nt.links.new
    bg = nt.nodes["Background"]; sk = next(n for n in nt.nodes if n.type == 'TEX_SKY')
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Generated"], sep.inputs[0])
    zc = N("ShaderNodeMath"); zc.operation = 'MAXIMUM'; L(sep.outputs["Z"], zc.inputs[0]); zc.inputs[1].default_value = 0.03
    zp = N("ShaderNodeMath"); zp.operation = 'ADD'; L(zc.outputs[0], zp.inputs[0]); zp.inputs[1].default_value = 0.15
    du = N("ShaderNodeMath"); du.operation = 'DIVIDE'; L(sep.outputs["X"], du.inputs[0]); L(zp.outputs[0], du.inputs[1])
    dv = N("ShaderNodeMath"); dv.operation = 'DIVIDE'; L(sep.outputs["Y"], dv.inputs[0]); L(zp.outputs[0], dv.inputs[1])
    cmb = N("ShaderNodeCombineXYZ"); L(du.outputs[0], cmb.inputs[0]); L(dv.outputs[0], cmb.inputs[1])
    mp = N("ShaderNodeMapping"); L(cmb.outputs[0], mp.inputs["Vector"])
    big = N("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = scale; big.inputs["Detail"].default_value = 3
    big.inputs["Roughness"].default_value = 0.5; L(mp.outputs["Vector"], big.inputs["Vector"])
    fine = N("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 5.0 * scale; fine.inputs["Detail"].default_value = 10
    fine.inputs["Roughness"].default_value = 0.65; L(mp.outputs["Vector"], fine.inputs["Vector"])
    cov = N("ShaderNodeMapRange"); L(big.outputs["Fac"], cov.inputs["Value"])
    cov.inputs["From Min"].default_value = 0.62 - 0.25 * cover; cov.inputs["From Max"].default_value = 0.72 - 0.25 * cover
    bw = N("ShaderNodeRGBToBW"); L(sk.outputs["Color"], bw.inputs[0])
    sh = N("ShaderNodeMath"); sh.operation = 'MULTIPLY_ADD'; L(fine.outputs["Fac"], sh.inputs[0]); sh.inputs[1].default_value = 0.7      # board round 3: "a visibly tiled noise texture" - soft bellies, not speckle
    sh.inputs[2].default_value = 0.6
    lum = N("ShaderNodeMath"); lum.operation = 'MULTIPLY'; L(bw.outputs[0], lum.inputs[0]); L(sh.outputs[0], lum.inputs[1])
    cc = N("ShaderNodeCombineColor"); [L(lum.outputs[0], cc.inputs[i]) for i in range(3)]
    mx = N("ShaderNodeMix"); mx.data_type = 'RGBA'; L(cov.outputs["Result"], mx.inputs[0])
    L(sk.outputs["Color"], mx.inputs[6]); L(cc.outputs[0], mx.inputs[7]); L(mx.outputs[2], bg.inputs["Color"])
    for f in (1, NF + 15):
        t = (f - 1) / FPS
        mp.inputs["Location"].default_value = (drift[0] * t, drift[1] * t, 0); mp.inputs["Location"].keyframe_insert("default_value", frame=f)


# ---------------------------------------------------------------- his body: layers, kicks and smooth hand paths
def lw_layer(data, bone, off, t0, t1):
    """ADD off(t) (degrees, x y z) on top of whatever already keys `bone`, every frame of t0..t1"""
    pb = data.pb[bone]
    base = {}
    for f in range(max(1, F(t0)), min(NF + 15, F(t1)) + 1):
        sc.frame_set(f); base[f] = tuple(math.degrees(v) for v in pb.rotation_euler)
    for f, b in base.items():
        o = off((f - 1) / FPS)
        data._k(bone, (f - 1) / FPS, rot=tuple(x + y for x, y in zip(b, o)))


def lw_kick(dt, tau=0.09):
    u = dt / tau
    return 0.0 if dt <= 0 else u * u * math.exp(2 * (1 - u))


def lw_win(t, a, d):
    return ease(min(1.0, max(0.0, (t - a) / d)))


def lw_spline(keys):
    """a smooth (Hermite) path through timed points [(t, point)], at rest at both ends"""
    ts = [k[0] for k in keys]; ps = [Vector(k[1]) for k in keys]; n = len(ps)
    assert all(a < b for a, b in zip(ts, ts[1:])), ts
    def vel(i):
        if i == 0 or i == n - 1: return Vector((0, 0, 0))
        return (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1])
    def fn(t):
        if t <= ts[0]: return ps[0].copy()
        for i in range(n - 1):
            if t <= ts[i + 1]:
                h = ts[i + 1] - ts[i]; u = (t - ts[i]) / max(1e-6, h)
                h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
                return ps[i] * h00 + vel(i) * (h10 * h) + ps[i + 1] * h01 + vel(i + 1) * (h11 * h)
        return ps[-1].copy()
    return fn


def lw_frame(data, sd):
    bpy.context.view_layer.update()
    sh = acts._shoulder(data, sd); c = Vector(data.arm.location)
    yaw = data.arm.rotation_euler.z; fw = Vector((math.sin(yaw), -math.cos(yaw), 0))
    out = sh - c; out.z = 0; out = out - fw * out.dot(fw); out.normalize()
    return sh, fw, out, Vector((0, 0, 1))


def lw_rel(data, sd, t, world):
    """a world point as (forward, out, up) from his shoulder at time t (to key a hand ON a thing in the set)"""
    sc.frame_set(F(t)); sh, fw, out, up = lw_frame(data, sd)
    d = Vector(world) - sh
    return (d.dot(fw), d.dot(out), d.z)


def lw_hand(data, sd, keys):
    """a hand path keyed (t, (forward, out, up)) from his shoulder, followed wherever his body goes"""
    path = lw_spline(keys)
    def fn(t):
        sc.frame_set(F(t)); sh, fw, out, up = lw_frame(data, sd)
        v = path(t)
        return sh + fw * v.x + out * v.y + Vector((0, 0, v.z))
    return fn


def lw_world_hand(fn_world):
    """a hand path given straight in the world (a grip on a moving thing)"""
    return lambda t: Vector(fn_world(t))


def lw_ride(obj, data, sd, back=0.04, along=(0, 1, 0)):
    """key a held prop on his hand every frame (after data.finish()), its butt in his fist, along his fingers"""
    hb = "hand." + sd
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb[hb].matrix
        p = M.translation + (M.to_3x3() @ Vector((0, 0.05, 0)))
        ax = (M.to_3x3() @ Vector(along)).normalized()
        obj.location = p - ax * back; obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(ax).to_euler()
        obj.keyframe_insert("location", frame=f); obj.keyframe_insert("rotation_euler", frame=f)


def lw_named(*prefixes):
    return [o for o in bpy.data.objects if o.type in ('MESH', 'FONT', 'CURVE', 'EMPTY') and o.name.startswith(prefixes) and o.parent is None]


def lw_drawn(*prefixes):
    return [o for o in bpy.data.objects if o.type in ('MESH', 'FONT', 'CURVE') and o.name.startswith(prefixes)]


def lw_key_scale(o, t, s):
    o.scale = (s, s, s) if isinstance(s, (int, float)) else s; o.keyframe_insert("scale", frame=max(1, F(t)))


def lw_show(objs, t_on, t_off=None):
    """hidden before t_on (and after t_off), every listed object"""
    for o in objs:
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=max(1, F(t_on) - 1))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=max(1, F(t_on)))
        if t_off is not None:
            o.hide_render = True; o.keyframe_insert("hide_render", frame=F(t_off))


def lw_cut(cam, main, wide, t0, t1, lens_main, lens_wide):
    """TWO SET-UPS CUT TOGETHER (the board, round 2, every shot: the world is never seen, because a lens close enough
    for him to read is too close for the town): main(t) and wide(t) -> (loc, look, focus point); the WIDE set-up holds
    from t0 to t1 (the shot's cutaway, which staging judges off him), the main one either side. A CUT: the keys are
    constant, so no frame is an in-between of the two set-ups and no motion blur smears across it."""
    from mathutils import Quaternion
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; w = t0 <= t < t1
        loc, look, foc = (wide if w else main)(t); loc = Vector(loc); look = Vector(look)
        cam.location = loc; cam.keyframe_insert("location", frame=f)
        cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.lens = lens_wide if w else lens_main; cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.focus_distance = (Vector(foc) - loc).length; cam.data.dof.keyframe_insert("focus_distance", frame=f)
    sc.render.motion_blur_position = 'START'
    from character import _fcurves
    for idb in (cam, cam.data):
        for fc in _fcurves(idb.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'


# ====================================================================================================
# shot1.py
# ====================================================================================================
"""BEAT 1, THE HOOK: "A volcano has erupted nine times beside one town in Iceland, and the whole town had to run."

Grindavik's main street on a bright grey afternoon, low houses with coloured tin roofs down both sides, the ridge above
the town at the end of it. The ridge rips open and a curtain of lava fountains bursts up along it under a boiling
plume. REDESIGN after board round 3 (a road gate's arm can never be whole in an upright frame at his size, and read as a
toy): the digger driver at the town's hand-cranked air-raid SIREN on its pole at the kerb winds its crank hand over
hand, the siren's rotor spins up and wails; at its call the town's cars pour out down the street, headlights on, past
him and out of the frame; he waves them on; the fountains surge; the street is empty and he runs after them."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the siren pole's foot, at the kerb
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX, S1_FGAP = 2.0, 0.8              # the nine vents: the row's middle (x) and the gap between two vents


def s1_ground_z(x, y):
    """the street flat, the land round the town rolling, and the ridge rising behind it to the fissure"""
    z = 0.0
    if abs(x) > 2.4: z += 0.15 * lw_fbm(x * 0.3, y * 0.3, 3) + 0.03 * (abs(x) - 2.4)
    r = max(0.0, (y - 9.0) / 6.0)
    z += 3.4 * (r * r * (3 - 2 * r) if r < 1 else 1.0) + (0.5 * lw_fbm(x * 0.15, y * 0.2, 7) if y > 8.5 else 0.0)
    if y > S1_RIDGE_Y: z -= 0.6 * min(1.0, (y - S1_RIDGE_Y) / 2.0)
    return z


def s1_car(name, col):
    """a small hatchback at the world's scale (2.4 long, 1.0 wide), facing -Y, headlights on"""
    root = K.empty(name, (0, 0, 0))
    paint = bpy.data.materials.get(f"car paint {col}")
    if not paint:
        paint = bpy.data.materials.new(f"car paint {col}"); paint.use_nodes = True; b = paint.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*K.lin(col), 1); b.inputs["Roughness"].default_value = 0.25
        b.inputs["Coat Weight"].default_value = 0.6; b.inputs["Coat Roughness"].default_value = 0.05; b.inputs["Metallic"].default_value = 0.3
    glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    tyre = lw_rubber("car tyre", "#141414", rough=0.8)
    K.box(name + " body", (0, 0, 0.36), (1.0, 2.4, 0.42), paint, bev=0.09, parent=root)
    K.box(name + " cabin", (0, 0.2, 0.7), (0.9, 1.35, 0.4), paint, bev=0.12, parent=root)
    K.box(name + " windscreen", (0, -0.47, 0.7), (0.84, 0.04, 0.32), glass, bev=0.02, parent=root).rotation_euler = (math.radians(-30), 0, 0)
    for sx in (-1, 1):
        K.box(name + " side glass", (sx * 0.452, 0.22, 0.72), (0.01, 1.1, 0.26), glass, bev=0.0, parent=root)
        for y in (-0.78, 0.8):
            K.cyl(name + " tyre", (sx * 0.43, y, 0.2), 0.2, 0.16, tyre, rot=(0, math.pi / 2, 0), v=24, parent=root)
        K.box(name + " headlight", (sx * 0.33, -1.2, 0.42), (0.2, 0.02, 0.09), lw_emit("headlight", "#FFF6E0", 22.0), bev=0.01, parent=root)
        K.box(name + " taillight", (sx * 0.36, 1.2, 0.44), (0.16, 0.02, 0.08), lw_emit("taillight", "#FF2A18", 6.0), bev=0.01, parent=root)
    K.box(name + " bumper", (0, -1.21, 0.22), (1.0, 0.06, 0.12), K.mat("car bumper", "#2A2A2C", rough=0.5), bev=0.02, parent=root)
    lw_local(root)
    return root


S1_SIREN_Z = 1.42                      # the siren's rotor (z), on top of its pole


def s1_siren():
    """the town's hand-cranked air-raid siren: a galvanised pole at the kerb with a foot plate and bolts, a red siren on
    top - a drum of louvred stator slots round a rotor that spins inside it, a domed cap, a flared horn mouth on each
    side - and the gearbox on the pole at his shoulder that the crank turns (built by s1_crank). Returns the rotor."""
    post_m = lw_metal("gate steel", "#8C9196"); red = lw_paint("siren red", "#B3201A", rough=0.38); dark = lw_metal("siren slots", "#1A1A1C", rough=0.5)
    K.cyl("gate post", (S1_PIV.x, S1_PIV.y + 0.12, S1_SIREN_Z / 2), 0.05, S1_SIREN_Z, post_m, v=16)
    K.box("gate foot", (S1_PIV.x, S1_PIV.y + 0.12, 0.02), (0.3, 0.3, 0.04), post_m, bev=0.005)
    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        K.cyl("gate foot bolt", (S1_PIV.x + 0.11 * dx, S1_PIV.y + 0.12 + 0.11 * dy, 0.05), 0.014, 0.03, dark, v=8)
    c = Vector((S1_PIV.x, S1_PIV.y + 0.12, S1_SIREN_Z + 0.12))
    K.cyl("siren drum", tuple(c), 0.16, 0.2, red, v=32)
    K.cyl("siren band", tuple(c + Vector((0, 0, -0.11))), 0.17, 0.03, post_m, v=32)
    K.cyl("siren band", tuple(c + Vector((0, 0, 0.11))), 0.17, 0.03, post_m, v=32)
    for k in range(10):                                   # the stator's slots, all round the drum
        a = 2 * math.pi * k / 10
        o = K.box("siren slot", tuple(c + Vector((0.162 * math.cos(a), 0.162 * math.sin(a), 0))), (0.012, 0.06, 0.13), dark, bev=0.0)
        o.rotation_euler = (0, 0, a)
    K.sph("siren cap", tuple(c + Vector((0, 0, 0.12))), 0.165, red, scale=(1, 1, 0.45), seg=32, ring=12)
    for sx in (-1, 1):                                    # the two flared horn mouths
        K.cyl("siren horn", tuple(c + Vector((sx * 0.22, 0, 0))), 0.09, 0.14, red, rot=(0, math.pi / 2, 0), v=24)
        K.cyl("siren horn mouth", tuple(c + Vector((sx * 0.3, 0, 0))), 0.12, 0.03, dark, rot=(0, math.pi / 2, 0), v=24)
    rotor = K.empty("gate pivot", tuple(c))
    for k in range(6):                                    # the rotor's vanes, seen spinning through the slots
        a = 2 * math.pi * k / 6
        o = K.box("siren rotor vane", (c.x + 0.075 * math.cos(a), c.y + 0.075 * math.sin(a), c.z), (0.15, 0.02, 0.15), lw_metal("rotor steel", "#B8BCC0", rough=0.3), bev=0.003, parent=rotor)
        o.rotation_euler = (0, 0, a)
    sign = K.box("siren sign", (S1_PIV.x, S1_PIV.y + 0.06, 0.95), (0.22, 0.012, 0.16), lw_paint("sign yellow", "#F2C200", rough=0.5), bev=0.004)
    K.box("siren sign mark", (S1_PIV.x, S1_PIV.y + 0.052, 0.95), (0.1, 0.004, 0.1), K.mat("sign black", "#141414", rough=0.5), bev=0.0)
    return rotor


def s1_crank(ctr, x_other):
    """the gate's winch crank: a wheel on the winch box's back face (axis along Y) with a knob on its rim. The box runs
    from the post top back to the wheel and across to where his other hand braces on it. Returns (wheel, box top z)."""
    post_m = lw_metal("gate steel", "#8C9196")
    x0, x1 = min(ctr.x, S1_PIV.x) - 0.07, max(ctr.x, S1_PIV.x) + 0.07
    y0, y1 = S1_PIV.y + 0.195, ctr.y - 0.012
    z0, z1 = ctr.z - 0.09, ctr.z + 0.07
    K.box("gate winch housing", ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), lw_paint("winch yellow", "#E0A21C"), bev=0.015)
    wh = K.empty("gate crank", tuple(ctr))
    K.cyl("gate crank wheel", (0, 0.0, 0), S1_CRANK_R + 0.012, 0.02, post_m, rot=(math.pi / 2, 0, 0), v=28, parent=wh)
    K.box("gate crank spoke", (S1_CRANK_R / 2, 0.0, 0), (S1_CRANK_R, 0.024, 0.02), post_m, bev=0.004, parent=wh)
    K.cyl("gate crank knob", (S1_CRANK_R, 0.04, 0), 0.016, 0.07, lw_rubber("gate handle", "#22201E"), rot=(math.pi / 2, 0, 0), v=14, parent=wh)
    lw_local(wh)
    return wh, z1


def s1_fountain_mat():
    """a lava fountain: pure glowing orange torn by streaks of black spatter crust (a lit surface over it washed it to
    salmon under the plume), the noise stretched up the jet so it reads as a rising spray"""
    m = bpy.data.materials.get("fountain lava")
    if m: return m
    m = bpy.data.materials.new("fountain lava"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (3, 3, 0.8)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 8; nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); el = rp.color_ramp.elements
    el[0].position = 0.35; el[0].color = (*K.lin("#B01000"), 1); el[1].position = 0.7; el[1].color = (*K.lin("#FF9A10"), 1)
    e = el.new(0.52); e.color = (*K.lin("#FF4000"), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], em.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMath"); ms.operation = 'MULTIPLY_ADD'; ms.inputs[1].default_value = 1.2; ms.inputs[2].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], ms.inputs[0]); nt.links.new(ms.outputs[0], em.inputs["Strength"])
    crust = nt.nodes.new("ShaderNodeBsdfPrincipled"); crust.inputs["Base Color"].default_value = (0.02, 0.015, 0.012, 1); crust.inputs["Roughness"].default_value = 0.9
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.36; mr.inputs["From Max"].default_value = 0.44
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(mr.outputs[0], mx.inputs[0])
    nt.links.new(crust.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def place_grindavik_street():
    """GRINDAVIK'S MAIN STREET: the asphalt street with its kerbs running away from the lens up to the ridge, the low
    coloured-roof houses down both sides, the old lava field and moss round the town, the ridge above it where the
    fissure opens under its plume, the road gate at the town's edge, far blue mountains."""
    rnd = lw_random.Random(5)
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven), at a real size
    K.box("street asphalt", (0, 2.5, 0.004), (4.0, 20, 0.01), ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt"), bev=0)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        K.box("kerb", (sx * 2.05, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 2.55, 2.5, 0.035), (0.9, 20, 0.07), ph_mat("concrete_wall_008", scale=1.6, tint="#A8A49C", name="pavement"), bev=0.005)
    for y in range(-8, 10, 2):
        K.box("centre line", (0, y + 0.5, 0.011), (0.08, 0.9, 0.004), K.mat("road paint", "#E9E4D4", rough=0.6), bev=0)
    houses = []
    for sx in (-1, 1):
        y = 0.9 if sx < 0 else 1.4
        k = 0
        while y < 8.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            hs = town_house(f"town house {sx}_{k}", (sx * (3.3 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A")[(k + (sx > 0)) % 3], wall=WALLS[k % len(WALLS)], base=0.3, seed=k)
            houses.append(hs); y += w + rnd.uniform(0.5, 0.9); k += 1
    lava_rock("lava field rock", 160, (-14, 14, -6, 14), s1_ground_z, seed=3, avoid=lambda x, y: abs(x) < 3.2 and y < 9.0)
    # the slope up to the ridge is old lava field: broken black blocks and moss, never one smooth brown sheet (EMPTY
    # measured the bare slope as 30% of the set), with the town's power line and a gravel track climbing it
    lava_rock("ridge slope rock", 520, (-7, 10, 8.5, 15.2), s1_ground_z, seed=11, r=(0.08, 0.32), moss=0.06)
    lava_rock("ridge slope stone", 700, (-5, 8, 8.5, 15.0), s1_ground_z, seed=12, r=(0.03, 0.09), moss=0.1)
    pole = lw_noise("power pole wood", "#4A3626", "#6E5238", scale=20, rough=0.9, stretch=(1, 1, 6))
    wire = K.mat("power line", "#151515", rough=0.5)
    tops = []
    for k in range(7):
        y = 9.0 + 1.1 * k; x = -3.2 + 0.25 * k
        z = s1_ground_z(x, y); h = 1.5
        K.cyl("power pole", (x, y, z + h / 2), 0.035, h, pole, v=10)
        K.box("power pole arm", (x, y, z + h - 0.1), (0.6, 0.04, 0.04), pole, bev=0.005)
        tops.append(Vector((x, y, z + h - 0.08)))
    for a, b in zip(tops, tops[1:]):
        for dx in (-0.25, 0.25):
            p, q = a + Vector((dx, 0, 0)), b + Vector((dx, 0, 0)); d = q - p
            o = K.cyl("power line wire", ((p + q) / 2), 0.006, d.length, wire, v=6, bev=0)
            o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    grav = lw_noise("gravel track", "#6A645C", "#8A8478", scale=30, rough=0.95, bump=0.5)
    for k in range(10):
        y = 8.8 + 0.65 * k; x = 1.2 + 1.4 * math.sin(0.5 * k)
        o = K.box("gravel track", (x, y, s1_ground_z(x, y) + 0.01), (0.7, 0.75, 0.03), grav, bev=0.005)
        o.rotation_euler = (math.atan2(s1_ground_z(x, y + 0.4) - s1_ground_z(x, y - 0.4), 0.8), 0, 0.7 * math.cos(0.5 * k) * 0.5)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a glowing line along the ridge and NINE vents on it, one for each eruption, close enough that the
    # whole row is in the frame and far enough apart to count; each vent a fountain of fire (a volume, white-hot in
    # its core) throwing glowing spatter that arcs and falls; the plume over it is smoke (volumes), lit from below
    fz = s1_ground_z(S1_FX, S1_RIDGE_Y)
    # board round 3: "thin pale-pink glowing spikes like neon tubes ... no molten body, no spatter, no fall-back",
    # "rising from a visible glowing crack": the fissure is a torn, glowing slot along the ridge, each fountain a
    # thick ORANGE body (a dim core, the volume cooler), throwing glowing clots AND dark cooled spatter that falls back
    fl = lava_mat("fissure lava", heat=2.0, scale=3.0, fresh=1.0)
    for k in range(14):
        x = S1_FX - 6.0 + 12.0 * k / 13; w_ = 0.45 + 0.25 * math.sin(1.7 * k)
        o = K.box("fissure glow", (x, S1_RIDGE_Y + 0.12 * math.sin(2.3 * k), s1_ground_z(x, S1_RIDGE_Y) - 0.05), (0.95, w_, 0.2), fl, bev=0.05)
        o.rotation_euler = (0, 0, 0.15 * math.sin(3.1 * k))
    founts, spat, cores = [], [], []
    core = lw_emit("fountain core", "#FF9A20", 7.0)
    spm = lw_emit("lava spatter", "#FF7A10", 5.0); spd = lw_noise("cooled spatter", "#140E0B", "#3A2A20", scale=20, rough=0.9)
    for k in range(9):
        x = S1_FX + (k - 4) * S1_FGAP
        z0 = s1_ground_z(x, S1_RIDGE_Y) - 0.2
        o = K.empty(f"fissure vent {k}", (x, S1_RIDGE_Y, z0))      # the vent: its fountain is a gas built in shot1, on its own clock
        o["base_z"] = z0; founts.append(o)
        for j in range(14):
            spat.append(K.sph(f"fissure spatter {k}_{j}", (x, S1_RIDGE_Y, z0), rnd.uniform(0.04, 0.09), spm if j % 3 else spd, seg=8, ring=6))
    puffs = []                                           # the plume is a gas, built in shot1 on the eruption's clock
    gate = s1_siren()
    glow = [lw_point(f"fissure light {k}", (S1_FX + x, S1_RIDGE_Y - 1.5, fz + 2.5), 0.0, col=(1.0, 0.4, 0.1), r=2.0) for k, x in enumerate((-3.5, 0, 3.5))]
    plume_lit = [lw_point(f"plume underlight {k}", (S1_FX + x, S1_RIDGE_Y + 2.0, fz + 5.0), 0.0, col=(1.0, 0.35, 0.08), r=3.0) for k, x in enumerate((-4, 4))]
    town_glow = lw_area("eruption glow on the town", (0, 12, 7), (0, 0, 0.5), 0.0, 14, col=(1.0, 0.5, 0.2))

    def light():
        k = iceland_light(sun_elev=4, sun_az=-45, sun=1.0, sky=0.12, warm=(1.0, 0.6, 0.4), haze=2.0)     # the town dim under an orange-tinted sky; the eruption lights it
        ph_sky("industrial_sunset_puresky", strength=0.25, rot=math.radians(180))      # a REAL low-sun sky, orange under the plume (Poly Haven)
        return k
    return dict(light=light, cores=cores, founts=founts, spat=spat, puffs=puffs, gate=gate, glow=glow + plume_lit, town_glow=town_glow, houses=houses, fz=fz)


def shot1():
    """THE ROAD GATE. A low lens three-quarter from the road, the street running away behind him to the ridge. The ridge
    bursts open; he startles round at it, takes the gate's crank and winds it hand over fist: the striped arm swings up
    high over the road; the cars pour out past him; he waves them on; the fountains surge; he sets off after the cars."""
    T_ERUPT = 0.08 * DUR
    T_GRAB = 0.22 * DUR; T_UP0 = T_GRAB + 0.05; T_UP1 = T_UP0 + 1.5
    T_LET = T_UP1 + 0.1
    T_CARS = T_UP0 + 0.7
    T_WAVE0 = T_LET + 0.15; T_WAVE1 = 0.8 * DUR
    T_SURGE = 0.72 * DUR
    T_GO = 0.84 * DUR
    REVS = 2.5
    W = lw_win
    P = place_grindavik_street()
    light = P["light"]
    data = load_data()
    P0 = Vector((S1_PIV.x + 0.3, 0.42, 0.0))                # behind the gate's winch, facing down the road toward us
    data.place(P0.x, P0.y, 0.0)
    kit = hard_hat(data)
    rnd = lw_random.Random(9)
    # ---- the eruption: the fountains burst up at T_ERUPT and keep throwing, surging at T_SURGE; spatter; the plume climbs
    T_NINE = 0.33                                          # one vent bursts every T_NINE s, left to right: nine, counted
    vents = P["founts"]; cols = []
    for k, v in enumerate(vents):                        # each vent a FOUNTAIN OF FIRE as a gas: torn tongues licking up a
        tk = T_ERUPT + T_NINE * k                        # glowing column, bursting in turn, nine, counted
        cols.append(lw_fire_column(f"fissure fountain {k}", (v.location.x, S1_RIDGE_Y, v["base_z"]), w=0.62, h_fire=2.8, h_smoke=2.0,
                                   lean=(0.1, 0.4), t_end=DUR + 1.0, seed=1.9 * k, fire=9.0, smoke_d=1.5, rise=3.5,
                                   keys=[(max(0.0, tk - 0.04), 0.0), (tk + 0.18, 1.0)], grow=True))
    for k, x in enumerate((-4.0, 0.0, 4.0)):             # the plume: a wall of grey gas and ash boiling off the whole fissure, leaning downwind
        cols.append(lw_steam(f"eruption plume {k}", (S1_FX + x, S1_RIDGE_Y + 1.0, P["fz"] + 1.5), w=4.5, h=16.0, seed=4.4 * k + 1, col=(0.46, 0.45, 0.46),
                             dens=3.0, lean=(-0.35, 0.3), rise=1.6, keys=[(T_ERUPT + 0.1 * k, 0.0), (T_ERUPT + 0.1 * k + 1.2, 1.0)], t_end=DUR + 1.0))
    P["founts"] = cols[:9]
    for k, o in enumerate(P["spat"]):
        v = vents[k // 14]; x0 = v.location.x + rnd.uniform(-0.12, 0.12); tk = T_ERUPT + T_NINE * (k // 14)
        vx = rnd.uniform(-1.1, 1.1); vz = rnd.uniform(4.5, 7.5); per = 2 * vz / 9.8; ph = rnd.uniform(0, per)
        b0 = v["base_z"] + 0.2
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < tk + ph * 0.3: o.location = (x0, S1_RIDGE_Y, b0 - 1.0)
            else:
                u = (t - tk + ph) % per
                o.location = (x0 + vx * u, S1_RIDGE_Y - 0.25 * u, b0 + vz * u - 4.9 * u * u)
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["puffs"]):
        z0 = o.location.z
        for f in range(1, NF + 1, 3):
            t = (f - 1) / FPS; s = W(t, T_ERUPT + 0.03 * k, 0.9)
            lw_puff_key(o, f, (1.3 * s, 1.0 * s, 0.9 * s)); o.location.z = z0 - 6.0 * (1 - s) + 0.5 * t
            o.keyframe_insert("location", frame=f)
    for L in P["glow"]:
        e0 = 50.0 if "plume" in L.name else 1200.0                # the plume a grey ash cloud, warm only underneath
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = e0 * W(t, T_ERUPT, 0.3) * (1 + 0.6 * W(t, T_SURGE, 0.5)); L.data.keyframe_insert("energy", frame=f)
    tg = P["town_glow"].data
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; tg.energy = 300.0 * W(t, T_ERUPT, 0.3) * (1 + 0.5 * W(t, T_SURGE, 0.5)); tg.keyframe_insert("energy", frame=f)
    # ---- the cars: one after another down the lane, under the raised arm, toward us and out of the frame
    cars = []
    for k, col in enumerate(("#B9C2C9", "#2D5A8E", "#C33A2A", "#E6E2D6", "#3B3F45")):
        c = s1_car(f"town car {k}", col); cars.append(c)
        y0 = 3.0 + 3.2 * k; v = 3.6
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = max(0.0, t - T_CARS)
            y = y0 - v * s
            c.location = (S1_LANE + 0.05 * math.sin(0.7 * t + k), y, s1_ground_z(S1_LANE, y) if y > 8 else 0.0); c.keyframe_insert("location", frame=f)
    crank_u = lambda t: ease(min(1.0, max(0.0, (t - T_UP0) / (T_UP1 - T_UP0))))
    # ---- his body: the start at the eruption, the lean into each turn of the crank, the wave, the flinch, the walk
    def body(t):
        p = P0.copy()
        p.z += 0.07 * lw_kick(t - T_ERUPT - 0.05, 0.12)
        p.z += 0.05 * lw_kick(t - T_SURGE, 0.12)
        cr = W(t, T_UP0, 0.25) * (1 - W(t, T_UP1, 0.25))                   # his whole body rides each turn of the crank
        p.z -= 0.025 * cr * (1 + math.sin(2 * math.pi * REVS * crank_u(t)))
        p.x += 0.035 * cr * math.sin(2 * math.pi * REVS * crank_u(t) + 0.6)          # he rocks side to side over the crank
        yaw = math.radians(-30) * W(t, T_ERUPT - 0.05, 0.3) * (1 - W(t, T_GRAB - 0.35, 0.3)) \
            + math.radians(3) * cr * math.sin(2 * math.pi * REVS * crank_u(t) + 1.2) \
            - math.radians(30) * W(t, T_WAVE0, 0.4) * (1 - W(t, T_GO - 1.0, 1.0)) + math.radians(40) * W(t, T_GO - 1.0, 1.0)
        return p, yaw
    for f in range(1, NF + 1):                             # at the end he turns after the cars, leaning into the run
        t = (f - 1) / FPS; p, yaw = body(t); p.z += 0.03 * lw_kick(t - T_GO, 0.15); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (-12 * lw_kick(t - T_ERUPT - 0.05, 0.2) + (8 + 5 * math.sin(2 * math.pi * REVS * crank_u(t))) * W(t, T_GRAB, 0.3) * (1 - W(t, T_LET, 0.3))
                                       - 10 * lw_kick(t - T_SURGE, 0.25) + 10 * W(t, T_GO - 0.5, 0.8), 0,
                                       3 * math.sin(2 * math.pi * (t - T_WAVE0) / 1.0) * W(t, T_WAVE0, 0.3) * (1 - W(t, T_WAVE1, 0.3))), 0, DUR + 0.4)
    # ---- the crank, built where his near hand turns it: its hub just in front of that shoulder
    sc.frame_set(F(T_GRAB)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    wind, other = sides[0], sides[1]                                              # the hand on the post's side winds
    sh = acts._shoulder(data, wind)
    osh = acts._shoulder(data, other)
    HUB = Vector((sh.x - 0.01, sh.y - 0.18, sh.z - 0.08))
    wheel, TOP = s1_crank(HUB, osh.x)
    th = lambda t: 2 * math.pi * REVS * crank_u(t)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; wheel.rotation_euler = (0, th(t), 0); wheel.keyframe_insert("rotation_euler", frame=f)
    knob = lambda t: HUB + Vector((S1_CRANK_R * math.cos(th(t)), 0.065, -S1_CRANK_R * math.sin(th(t))))
    # ---- the siren: its rotor spins up as he winds (geared up off the crank) and runs on, winding down slowly
    gate = P["gate"]; spin = 0.0
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        rate = 9.0 * W(t, T_UP0, 0.4) * (1 - 0.5 * W(t, T_LET, 1.5))      # rev/s
        spin += 2 * math.pi * rate / FPS
        gate.rotation_euler = (0, 0, spin); gate.keyframe_insert("rotation_euler", frame=f)
    data.reach(wind, knob, T_GRAB, T_LET, lead=0.45, back=None, elbow_out=0.4)
    RK = [(T_LET + 0.55, (0.12, 0.1, -0.07)), (T_GO - 0.2, (0.09, 0.09, -0.09)), (DUR + 0.4, (0.08, 0.09, -0.09))]
    data.reach(wind, lw_hand(data, wind, RK), RK[0][0], DUR + 0.3, lead=0.55, back=None, elbow_out=0.4)
    WK = [(T_UP0 + 0.55, (0.08, 0.12, 0.0))]                 # his free hand waves the cars on while the other still winds
    t = T_UP0 + 0.95; k = 0
    while t < T_WAVE1 - 0.2:
        WK.append((t, (0.07, 0.15, 0.08) if k % 2 == 0 else (0.11, 0.07, 0.03))); t += 0.45; k += 1
    WK += [(max(T_SURGE + 0.1, WK[-1][0] + 0.35), (0.06, 0.1, 0.06)), (DUR + 0.4, (0.08, 0.09, -0.08))]
    WK = sorted({round(a, 3): b for a, b in WK}.items())
    data.reach(other, lw_hand(data, other, WK), WK[0][0], DUR + 0.3, lead=0.5, back=None, elbow_out=0.35)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((3.2, -3.6, 0.8))
    data.look_at(LENS, 0.0, max_yaw=40, blend=0.0)
    data.look_at(Vector((-3.0, S1_RIDGE_Y, 7.0)), T_ERUPT + 0.05, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(HUB, T_GRAB - 0.3, max_yaw=50, max_pitch=18, blend=0.3)                  # eyes down to it, the brim kept off his face
    data.look_at(Vector((S1_PIV.x - 0.2, 0.6, S1_SIREN_Z + 0.4)), T_UP0 + 0.4, max_yaw=55, max_pitch=40, blend=0.3)      # up at the siren as it starts to wail
    data.look_at(Vector((-1.5, 5.0, 1.5)), T_UP0 + 1.0, max_yaw=55, max_pitch=40, blend=0.3)
    data.look_at(Vector((S1_LANE, -1.0, 0.7)), T_LET, max_yaw=55, blend=0.3)
    data.look_at(Vector((-2.0, S1_RIDGE_Y, 8.0)), T_SURGE, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((S1_LANE, -4.0, 0.7)), T_GO - 0.1, max_yaw=50, blend=0.3)
    data.expression("alarmed", T_ERUPT, T_GRAB - 0.05, blend=0.15)
    data.expression("determined", T_GRAB, T_SURGE - 0.1, blend=0.2)
    data.expression("worried", T_SURGE, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: WIDE from a little above his head, in front of him and off to the post's far side, so the street
    # runs away behind him to the ridge and all nine vents stand over the town in one row
    CAM = Vector((0.95, -1.24, 1.15)); LOOK = Vector((1.6, 17.45, -2.5))   # tipped down: the nine fountains high in the frame, less bare sky (EMPTY read the sky as 30%)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30.0, fstop=16.0)
    # CUT to the WIDE while the town drives out (board round 2: "the cars never pour out under the gate", "not
    # Grindavik's main street"): high behind the cars' exit, the street with its houses down both sides running to the
    # ridge, the nine fountains in a row over it, the raised gate with him at its post, the cars streaming at the lens
    T_W0, T_W1 = 0.5 * DUR, 0.8 * DUR
    CW = Vector((0.45, -4.6, 1.0)); LW = Vector((1.0, 10.0, 2.6))      # low on the road's crown: the cars streaming past us, him at the siren, the street and its houses to the fountains
    lw_cut(cam, lambda t: (CAM + Vector((0.0, 0.15, 0.02)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))),
           lambda t: (CW + Vector((0.0, 0.25, 0.0)) * (t - T_W0), LW, Vector((1.1, 0.4, 0.8))), T_W0, T_W1, 30.0, 40.0)
    founts = P["founts"]
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=("gate crank", "gate winch housing"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("the ridge rips open and a curtain of lava fountains bursts up over the town", lambda: founts, T_ERUPT, DUR, {"whole": False}),
                        ("he winds the crank and the siren on its pole spins up and wails", lambda: lw_drawn("siren", "gate post"), T_UP0 + 0.3, T_UP1 + 0.4, {"whole": False}),
                        ("at its call the town's cars pour out down the street, past him", lambda: meshes(cars), T_CARS + 0.3, T_WAVE1, {"whole": False})])


# ====================================================================================================
# shot2.py
# ====================================================================================================
"""BEAT 2: "So Iceland built walls of rock three stories tall, with a hundred diggers and trucks working day and night."

The wall works outside the town in the blue evening, the earth wall's black face rising behind him, three stories of
rock, floodlights along its foot, other diggers at work along it. The driver stands in front of it with his digger's
remote control pack on his chest, both hands on its two sticks: he shoves them forward and beside him the digger's big
arm swings up the face with its bucket full of black rock and tips it over the crest, the rock tumbling back down the
face in a burst of dust and bouncing past him; he ducks, then grins at us; he hauls the sticks back and the arm swings
down for the next bucketful; the floodlights blaze on as night falls."""

S2_DECK = 0.52                          # the digger's deck
S2_BOOM = Vector((0.95, 0.42, 1.05))    # the boom's foot pin, in the digger's own frame (facing its +X)
S2_L1, S2_L2 = 3.4, 3.0                 # boom and stick
S2_DIG = Vector((-3.0, 2.4, 0.0))      # the digger, beside and behind him, facing +Y (the wall)
# REDESIGN after board round 3 ("a gentle brown dirt slope ... about the digger's height", "no crest in frame"): the
# wall is a STEEP black rock face, three storeys and more over him, close behind the digger, its crest in frame
S2_WALL_Y = 6.8                        # the wall's crest centre line (it runs along X)
S2_WALL_H = 6.0
S2_BASE = 4.6
S2_FOOT = S2_WALL_Y - S2_BASE / 2       # its near foot (y)
S2_EDGE = S2_WALL_Y - 0.7               # its crest's near edge (y)


def s2_face_z(y):
    return S2_WALL_H * max(0.0, min(1.0, (y - S2_FOOT) / (S2_EDGE - S2_FOOT)))


def s2_ground_z(x, y):
    return 0.08 * lw_fbm(x * 0.4, y * 0.4, 11)


def s2_ik(p):
    """boom angle a (from level) and stick angle b (from the boom's line) that put the stick's end at p (x, z)"""
    dx, dz = p[0] - S2_BOOM.x, p[1] - S2_BOOM.z; d = max(abs(S2_L1 - S2_L2) + 1e-3, min(S2_L1 + S2_L2 - 1e-3, math.hypot(dx, dz)))
    c = (S2_L1 ** 2 + d ** 2 - S2_L2 ** 2) / (2 * S2_L1 * d)
    a = math.atan2(dz, dx) + math.acos(max(-1, min(1, c)))           # elbow up
    cb = (S2_L1 ** 2 + S2_L2 ** 2 - d ** 2) / (2 * S2_L1 * S2_L2)
    b = -(math.pi - math.acos(max(-1, min(1, cb))))
    return a, b


S2_RC_FW, S2_RC_UP = 0.18, -0.13        # the remote's centre from the middle of his shoulders: forward, up


def s2_knob_off(sx, lean, yaw):
    """a stick's knob from the remote's centre, the stick leaning `lean` (its pivot turned -lean about x), the remote
    turned `yaw`: the box (sx, 0, 0.025) to its pivot, the knob 0.065 up the stick"""
    v = Vector((sx, 0.065 * math.sin(lean), 0.025 + 0.065 * math.cos(lean)))
    c, s_ = math.cos(yaw), math.sin(yaw)
    return Vector((c * v.x - s_ * v.y, s_ * v.x + c * v.y, v.z))


def s2_remote(data):
    """the digger's remote control pack: a yellow box on his chest strap with two black sticks on its top, carried on
    his chest bone. Returns (box, [(stick pivot, knob)])."""
    sc.frame_set(1); bpy.context.view_layer.update()
    sh = [acts._shoulder(data, s_) for s_ in "LR"]; mid = (sh[0] + sh[1]) / 2
    fw = data.forward()
    c = mid + fw * S2_RC_FW + Vector((0, 0, S2_RC_UP))
    yaw = data.arm.rotation_euler.z
    root = K.empty("remote control", tuple(c))
    yel = lw_paint("remote yellow", "#F2B10E", rough=0.4); dark = lw_rubber("remote black", "#1A1A1A", rough=0.6)
    K.box("remote control box", (0, -0.01, 0), (0.2, 0.065, 0.05), yel, bev=0.012, parent=root)
    K.box("remote control screen", (0, -0.035, 0.026), (0.07, 0.012, 0.004), lw_emit("remote screen", "#7FE0FF", 4.0), bev=0.0, parent=root)
    sticks = []
    for sx in (-0.06, 0.06):
        pv = K.empty("remote stick pivot", (sx, 0.0, 0.025), parent=root)
        K.cyl("remote stick", (0, 0.0, 0.03), 0.008, 0.06, dark, parent=pv)
        kn = K.sph("remote stick knob", (0, 0.0, 0.065), 0.02, lw_rubber("remote knob red", "#C8201A", rough=0.5), parent=pv)   # red knobs, so the two sticks read
        sticks.append((pv, kn))
    lw_local(root)
    root.rotation_euler = (0, 0, yaw)
    bpy.context.view_layer.update()
    M = root.matrix_world.copy()
    return root, sticks


def s2_digger(knob_pts=((0.46, -0.58, S2_DECK + 0.545), (0.46, -0.3, S2_DECK + 0.545))):
    """THE DIGGER: a yellow tracked excavator facing +X, an open operator's deck on its -Y side where he stands at two
    control sticks, the boom on its +Y side: boom, stick and a toothed bucket, each on its own pivot empty.
    Returns dict(boom, stick, bucket, sticks=[(pivot, knob)], load)."""
    yel = lw_paint("digger yellow worn", "#E8A80C", rough=0.5)      # worn paint, dust in its seams
    dark = lw_metal("digger steel", "#2C2C2E", rough=0.5)
    track = lw_rubber("track rubber", "#1E1E1E", rough=0.9)
    for sy in (-0.72, 0.72):
        K.box("digger track", (0.1, sy, 0.22), (2.5, 0.42, 0.44), track, bev=0.12)
        for x in (-0.95, -0.3, 0.35, 1.0):
            K.cyl("digger roller", (x, sy - 0.22 * (1 if sy < 0 else -1), 0.22), 0.13, 0.03, dark, rot=(math.pi / 2, 0, 0), v=20)
    K.box("digger turntable", (0.0, 0.0, 0.48), (1.5, 1.5, 0.1), dark, bev=0.02)
    K.box("digger engine housing", (-0.75, 0.15, 0.95), (1.0, 1.55, 0.85), yel, bev=0.06)
    K.box("digger counterweight", (-1.3, 0.15, 0.82), (0.25, 1.6, 0.6), yel, bev=0.08)
    K.box("digger deck", (0.25, -0.45, S2_DECK - 0.03), (0.95, 0.75, 0.06), lw_noise("deck tread", "#3A3A3C", "#56565A", scale=80, rough=0.6, bump=1.0))
    K.box("digger boom mount", (0.75, 0.42, 0.8), (0.5, 0.5, 0.55), yel, bev=0.05)
    for sy in (-0.83, -0.07):                            # the canopy: two rear posts and the roof over his deck
        K.box("digger canopy post", (-0.2, sy, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    K.box("digger canopy roof", (0.2, -0.45, S2_DECK + 1.26), (0.95, 0.85, 0.05), dark, bev=0.015)
    cg = K.mat("cab glass", "#26343C", rough=0.04, metal=0.3)      # the cab's glass: front, sides and back
    K.box("digger cab glass", (0.66, -0.45, S2_DECK + 0.78), (0.02, 0.8, 0.9), cg, bev=0.0)
    for sy_ in (-0.86, -0.04):
        K.box("digger cab glass", (0.22, sy_, S2_DECK + 0.78), (0.86, 0.02, 0.9), cg, bev=0.0)
    K.box("digger cab post", (0.66, -0.86, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    K.box("digger cab post", (0.66, -0.04, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    # its working parts, so it reads as a machine and not a toy block: engine grille slats, an exhaust stack, grab
    # rails, a warning-striped counterweight, a step, the hydraulic hoses
    for k in range(7):
        K.box("digger grille slat", (-0.75 + 0.12 * (k - 3), -0.63, 1.05), (0.05, 0.02, 0.45), dark, bev=0.005)
    K.cyl("digger exhaust", (-0.95, 0.55, 1.55), 0.045, 0.4, lw_metal("exhaust steel", "#3A3634", rough=0.6), v=14)
    rail = lw_metal("grab rail", "#202022", rough=0.4)
    for x in (-1.15, -0.35):
        K.cyl("digger grab rail post", (x, -0.66, 1.42), 0.015, 0.12, rail, v=8)
    K.cyl("digger grab rail", (-0.75, -0.66, 1.48), 0.015, 0.82, rail, rot=(0, math.pi / 2, 0), v=8)
    blk = lw_paint("stripe black", "#1A1A1A", rough=0.6)
    for k in range(5):
        o = K.box("digger warning stripe", (-1.43, -0.45 + 0.3 * k, 0.82), (0.02, 0.09, 0.62), blk, bev=0.0)
        o.rotation_euler = (math.radians(35), 0, 0)
    K.box("digger step", (0.25, -0.88, 0.5), (0.4, 0.14, 0.03), dark, bev=0.005)
    sticks = []
    if knob_pts: K.box("digger seat back", (-0.1, -0.45, S2_DECK + 0.5), (0.08, 0.4, 0.45), lw_rubber("seat black", "#1E1E1E", rough=0.7), bev=0.03)
    for kx, ky, kz in knob_pts:                           # the two control towers in front of him, a stick on each
        top = kz - 0.135
        K.box("digger control tower", (kx + 0.03, ky, (S2_DECK + top) / 2), (0.1, 0.1, top - S2_DECK), dark, bev=0.01)
        pv = K.empty("control stick pivot", (kx, ky, top))
        K.cyl("control stick", (kx, ky, top + 0.06), 0.012, 0.12, dark, parent=pv)
        knob = K.sph("control stick knob", (kx, ky, kz), 0.03, lw_rubber("knob black", "#141414", rough=0.5), parent=pv)
        sticks.append((pv, knob))
    K.box("digger lamp", (0.2, -0.02, S2_DECK + 1.3), (0.1, 0.12, 0.06), lw_emit("digger lamp", "#FFF2D0", 12.0), bev=0.01)
    boom = K.empty("digger boom", tuple(S2_BOOM))
    K.box("digger boom arm", (S2_BOOM.x + S2_L1 / 2, S2_BOOM.y, S2_BOOM.z), (S2_L1, 0.26, 0.34), yel, bev=0.05, parent=boom)
    K.cyl("digger ram", (S2_BOOM.x + 0.9, S2_BOOM.y, S2_BOOM.z - 0.25), 0.06, 1.4, lw_metal("ram chrome", "#C8CCD0", rough=0.15), rot=(0, math.pi / 2, 0), parent=boom)
    chrome = lw_metal("ram chrome", "#C8CCD0", rough=0.15); barrel = lw_paint("ram barrel", "#2A2A2C", rough=0.4)
    K.cyl("digger ram barrel", (S2_BOOM.x + 0.55, S2_BOOM.y, S2_BOOM.z - 0.27), 0.085, 0.9, barrel, rot=(0, math.pi / 2, 0), parent=boom)
    K.cyl("digger stick ram", (S2_BOOM.x + S2_L1 - 0.9, S2_BOOM.y, S2_BOOM.z + 0.28), 0.06, 1.5, chrome, rot=(0, math.pi / 2, 0), parent=boom)
    K.cyl("digger stick ram barrel", (S2_BOOM.x + S2_L1 - 1.4, S2_BOOM.y, S2_BOOM.z + 0.28), 0.08, 0.8, barrel, rot=(0, math.pi / 2, 0), parent=boom)
    for k_ in range(3):                                   # the hoses run up the boom
        K.cyl("digger hose", (S2_BOOM.x + S2_L1 / 2, S2_BOOM.y + 0.15, S2_BOOM.z + 0.12 + 0.04 * k_), 0.018, S2_L1 * 0.9, lw_rubber("hose black", "#121212", rough=0.6), rot=(0, math.pi / 2, 0), parent=boom)
    stick = K.empty("digger stick", (S2_BOOM.x + S2_L1, S2_BOOM.y, S2_BOOM.z), parent=boom)
    K.cyl("digger bucket ram", (S2_BOOM.x + S2_L1 + 0.9, S2_BOOM.y, S2_BOOM.z + 0.2), 0.05, 1.3, chrome, rot=(0, math.pi / 2, 0), parent=stick)
    K.box("digger stick arm", (S2_BOOM.x + S2_L1 + S2_L2 / 2, S2_BOOM.y, S2_BOOM.z), (S2_L2, 0.2, 0.24), yel, bev=0.04, parent=stick)
    bucket = K.empty("digger bucket", (S2_BOOM.x + S2_L1 + S2_L2, S2_BOOM.y, S2_BOOM.z), parent=stick)
    bx = S2_BOOM.x + S2_L1 + S2_L2
    K.box("digger bucket back", (bx, S2_BOOM.y, S2_BOOM.z - 0.32), (0.08, 0.7, 0.64), dark, bev=0.02, parent=bucket)
    K.box("digger bucket floor", (bx + 0.25, S2_BOOM.y, S2_BOOM.z - 0.62), (0.5, 0.7, 0.06), dark, bev=0.02, parent=bucket)
    for sy in (-0.35, 0.35):
        K.box("digger bucket side", (bx + 0.2, S2_BOOM.y + sy, S2_BOOM.z - 0.4), (0.45, 0.04, 0.5), dark, bev=0.01, parent=bucket)
    for k in range(5):
        K.box("digger bucket tooth", (bx + 0.52, S2_BOOM.y - 0.28 + 0.14 * k, S2_BOOM.z - 0.62), (0.1, 0.05, 0.04), dark, bev=0.01, parent=bucket)
    return dict(boom=boom, stick=stick, bucket=bucket, sticks=sticks, bx=bx)


def s2_truck(name, col="#E3A112"):
    """a yellow dump truck facing +Y: a cab, a raised-sided steel bed full of black rock, six wheels, headlights on"""
    root = K.empty(name, (0, 0, 0))
    yel = lw_paint(f"truck paint {col}", col, rough=0.45); dark = lw_metal("truck steel", "#2E2E30", rough=0.55)
    tyre = lw_rubber("car tyre", "#141414", rough=0.8)
    K.box(name + " cab", (0, 1.3, 1.0), (1.3, 0.9, 1.0), yel, bev=0.06, parent=root)
    K.box(name + " windscreen", (0, 1.76, 1.2), (1.1, 0.02, 0.4), K.mat("car glass", "#1E262C", rough=0.05, metal=0.3), bev=0.0, parent=root)
    K.box(name + " chassis", (0, 0.0, 0.5), (1.2, 3.4, 0.25), dark, bev=0.02, parent=root)
    K.box(name + " bed", (0, -0.4, 1.05), (1.45, 2.4, 0.85), yel, bev=0.05, parent=root)
    rk = lw_noise("wall rock", "#2A2522", "#5A4E44", scale=7, rough=0.95, bump=1.0, detail=8)
    rnd = lw_random.Random(len(name))
    for k in range(9):
        K.sph(name + " load", (rnd.uniform(-0.5, 0.5), rnd.uniform(-1.4, 0.6), 1.5), rnd.uniform(0.18, 0.3), rk, scale=(1, 1, 0.6), seg=10, ring=6, parent=root)
    for y in (-1.3, -0.5, 1.2):
        for sx in (-1, 1):
            K.cyl(name + " wheel", (sx * 0.66, y, 0.38), 0.38, 0.28, tyre, rot=(0, math.pi / 2, 0), v=24, parent=root)
    for sx in (-1, 1):
        K.box(name + " headlight", (sx * 0.45, 1.76, 0.7), (0.2, 0.02, 0.12), lw_emit("headlight", "#FFF6E0", 22.0), bev=0.01, parent=root)
    lw_local(root)
    return root


def place_wall_works():
    """THE WALL WORKS in the blue evening: the trodden gravel of the works, the earth wall's black face rising across the
    whole frame, floodlight masts along its foot, other diggers at work along it, the eruption's smoke over the crest."""
    rnd = lw_random.Random(21)
    lw_grid("works ground", -26, 26, -14, 22, 90, 80, s2_ground_z, ph_mat("gravel_floor_02", scale=1.0, tint="#2F2B27", name="works gravel", rough=0.95))   # REAL gravel (Poly Haven)
    wall = earth_wall("earth wall", [(x, S2_WALL_Y + 0.006 * x * x) for x in range(-30, 32, 2)], h=S2_WALL_H, crest=1.4, base=S2_BASE, seed=4)
    lava_rock("works rock", 90, (-12, 12, -6, S2_FOOT - 0.2), s2_ground_z, seed=6, r=(0.08, 0.26),
              avoid=lambda x, y: (-4.2 < x < -1.6 and 0.3 < y < 4.2) or (-0.8 < x < 1.0 and -1.8 < y < 1.2) or (x + 6.5) ** 2 + (y + 4.0) ** 2 < 9.0 or (6.6 < x < 9.0 and -3.4 < y < 1.0))
    lava_rock("wall face rock", 160, (-12, 12, S2_FOOT + 0.2, S2_EDGE - 0.2), lambda x, y: s2_face_z(y - 0.006 * x * x), seed=17, r=(0.1, 0.32))   # the black rock it is built of, tumbled down its face
    masts = []
    for k, x in enumerate((-7.5, -4.2, 2.6, 6.0)):
        y = S2_FOOT - 0.5 + 0.006 * x * x
        K.cyl("floodlight mast", (x, y, 2.6), 0.06, 5.2, lw_metal("mast steel", "#8A8E92"), v=12)
        # board round 3: "white boxes on poles that cast no light". A real floodlight: a dark housing with four hot
        # lamp faces turned down at the works, a cone of light through the dust under it, a pool on the ground
        K.box("floodlight housing", (x, y - 0.02, 5.25), (1.0, 0.24, 0.45), lw_metal("floodlight housing", "#2A2C2E", rough=0.5), bev=0.03)
        K.box("floodlight bar", (x, y + 0.02, 5.0), (1.1, 0.06, 0.06), lw_metal("mast steel", "#8A8E92"), bev=0.01)
        head = None
        for i_, (dx_, dz_) in enumerate(((-0.24, 0.1), (0.24, 0.1), (-0.24, -0.1), (0.24, -0.1))):
            o = K.box("floodlight head", (x + dx_, y - 0.15, 5.25 + dz_), (0.42, 0.03, 0.18), lw_emit(f"floodlight lamp {k}", "#FFF4DC", 0.0), bev=0.01)
            head = head or o
        aim = Vector((0.3 * x, -1.0, 0.0))
        L = lw_area(f"floodlight {k}", (x, y - 0.3, 5.1), tuple(aim), 0.0, 0.8, col=(1.0, 0.95, 0.85))
        beam = bpy.data.meshes.new(f"floodlight beam {k}"); bm = LW_bmesh.new()
        LW_bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=0.25, radius2=2.2, depth=1.0)
        bm.to_mesh(beam); bm.free()
        bmat = bpy.data.materials.get("floodlight dust")
        if not bmat:
            bmat = bpy.data.materials.new("floodlight dust"); bmat.use_nodes = True; nt_ = bmat.node_tree
            nt_.nodes.remove(nt_.nodes["Principled BSDF"]); pv = nt_.nodes.new("ShaderNodeVolumePrincipled")
            pv.inputs["Density"].default_value = 0.006; pv.inputs["Color"].default_value = (1.0, 0.97, 0.9, 1)
            nt_.links.new(pv.outputs[0], nt_.nodes["Material Output"].inputs["Volume"])
        beam.materials.append(bmat)
        bo = lw_link(bpy.data.objects.new(f"floodlight beam {k}", beam)); bo.hide_render = True   # its haze read as a white blob (board): the light carries it
        src = Vector((x, y - 0.3, 5.1)); d_ = (aim - src); ln = d_.length * 0.92
        bo.scale = (1, 1, ln); bo.location = src + d_.normalized() * ln / 2
        bo.rotation_euler = (-d_).to_track_quat('Z', 'Y').to_euler()
        masts.append((head, L))
    far = []
    for k, (x, a_, b_) in enumerate(((-9.0, 0.75, -1.9), (5.6, 0.45, -1.5), (10.5, 0.9, -2.1))):   # other diggers at work along the wall: built, not boxes
        before = set(bpy.data.objects)
        Dk = s2_digger(knob_pts=())
        rg = K.empty(f"far digger {k}", (0, 0, 0))
        for o in set(bpy.data.objects) - before:
            if o.parent is None and o is not rg: o.parent = rg
        rg.location = (x, S2_FOOT - 2.6 + 0.006 * x * x, 0.0); rg.rotation_euler = (0, 0, math.radians(90 + (-12 if x < 0 else 12)))
        Dk["boom"].rotation_euler = (0, -a_, 0); Dk["stick"].rotation_euler = (0, -b_, 0)
        far.append((Dk, a_, b_, k))
    # the eruption beyond the wall reads as its glow along the horizon over the crest
    lava_rock("works rubble", 650, (-7.0, 7.0, -3.5, 6.0), s2_ground_z, seed=29, r=(0.05, 0.24), moss=0.0,     # the black rock spilled across the works as it is trucked to the wall
              avoid=lambda x, y: (x - 0.05) ** 2 + (y - 0.25) ** 2 < 0.25 or (-4.2 < x < -1.6 and 0.3 < y < 4.6))
    lava_rock("works stones", 240, (-3.5, 3.5, -1.8, 3.0), s2_ground_z, seed=23, r=(0.025, 0.08),     # the trodden works: stones and grit underfoot
              avoid=lambda x, y: (x - 0.05) ** 2 + (y - 0.25) ** 2 < 0.3 or (-4.2 < x < -1.6 and 0.3 < y < 4.6))
    for k, x0 in enumerate((-2.2, -1.5, 1.6, 2.3)):           # the tracks the machines have cut in it
        K.box(f"track rut {k}", (x0 + 0.1 * k, 0.6, 0.006), (0.32, 9.0, 0.01), lw_noise("rut mud", "#2A2622", "#3E3832", scale=30, rough=0.9, bump=1.0, stretch=(1, 6, 1)), bev=0)
    for k, (x, y, r) in enumerate(((-5.6, -1.2, 0.3), (4.4, -2.6, -0.2), (7.4, 2.2, 0.1))):      # REAL props of a works (Poly Haven): barriers, bags of cement, drums
        ph_model("concrete_road_barrier", (x, y, s2_ground_z(x, y)), rot=(0, 0, r), scale=0.5, name=f"road barrier {k}")
    for k, (x, y) in enumerate(((-6.4, 1.6), (-6.0, 1.9), (-6.2, 2.3))):
        ph_model("cement_bag", (x, y, s2_ground_z(x, y) + 0.06 * k), rot=(0, 0, 0.4 * k), scale=0.5, name=f"cement bag {k}")
    for k, (x, y, r) in enumerate(((-1.3, -0.9, 0.3), (1.4, -1.1, 1.1), (-2.4, 0.4, 2.0))):   # worn tyres off the machines, dumped about the works
        ph_model("old_tyre", (x, y, s2_ground_z(x, y)), rot=(math.radians(90) if k == 2 else 0, 0, r), scale=0.9, name=f"works tyre {k}")
    for k, (x, y) in enumerate(((5.2, 0.6), (5.6, 0.9))):
        ph_model("barrel_03", (x, y, s2_ground_z(x, y)), rot=(0, 0, k), scale=0.5, name=f"fuel drum {k}")
    K.box("eruption horizon glow", (0, 30, 3.0), (90, 0.5, 6.0), lw_emit("horizon glow", "#FF6A20", 0.8), bev=0)

    def light():
        k = iceland_light(sun_elev=1, sun_az=-40, sun=0.4, sky=0.11, warm=(0.8, 0.72, 1.0), haze=0.35)     # blue evening going to night: the floodlights carry the works
        ph_sky("qwantani_dusk_2_puresky", strength=0.07, rot=math.radians(200))       # a REAL dusk sky (Poly Haven)
        return k
    return dict(light=light, wall=wall, masts=masts, far=far)


def shot2():
    """THE WALL WORKS. A low lens at the foot of the wall, looking up at him and the digger behind him. He shoves the
    remote's sticks and the digger's arm swings up over him and over us to the crest; the rock tumbles back down the
    face past the lens in a burst of dust and he ducks, then grins; he hauls the sticks back and the arm swings down for
    the next load; the floodlights blaze on."""
    T_PUSH = 0.06 * DUR; T_TOP = 0.32 * DUR; T_TIP = T_TOP + 0.1; T_TIPPED = T_TIP + 0.5
    T_DUCK = T_TIP + 0.55; T_GRIN = T_DUCK + 0.55
    T_BACK = 0.66 * DUR; T_LOW = 0.9 * DUR
    T_LIGHTS = 0.82 * DUR
    W = lw_win
    P = place_wall_works()
    light = P["light"]
    data = load_data()
    P0 = Vector((0.05, 0.2, s2_ground_z(0.05, 0.2))); YAW0 = math.radians(18)
    PS = P0 + Vector((-0.12, 0.1, 0.0))                     # where he starts: he steps up to the work as he shoves
    data.place(PS.x, PS.y, math.degrees(YAW0))
    kit = hard_hat(data)
    remote, sticks = s2_remote(data)
    # ---- the digger: built facing +X at the origin, then set down behind him facing the wall (+Y)
    before = set(bpy.data.objects)
    D = s2_digger(knob_pts=())
    rig = K.empty("digger", (0, 0, 0))
    for o in set(bpy.data.objects) - before:
        if o.parent is None and o is not rig: o.parent = rig
    rig.location = S2_DIG; rig.rotation_euler = (0, 0, math.radians(90))
    def world(px, pz):                                     # a point in the digger's arm plane, in the world
        return Vector((S2_DIG.x - S2_BOOM.y, S2_DIG.y + px, pz))
    # ---- the arm: the bucket's path in its own plane (stick end), the bucket's curl
    LOW = (1.9, 0.6); HIGH = (S2_EDGE - 0.25 - S2_DIG.y, S2_WALL_H + 0.85)
    def path(t):
        u = ease(min(1.0, max(0.0, (t - T_PUSH) / (T_TOP - T_PUSH)))); v = ease(min(1.0, max(0.0, (t - T_BACK) / (T_LOW - T_BACK))))
        x = LOW[0] + (HIGH[0] - LOW[0]) * u; z = LOW[1] + (HIGH[1] - LOW[1]) * math.sin(u * math.pi / 2)
        x += (LOW[0] - 0.2 - HIGH[0]) * v; z += (LOW[1] - HIGH[1]) * v
        return x, z
    curl = lambda t: math.radians(-40) * (1 - W(t, T_TIP, 0.3)) + math.radians(85) * W(t, T_TIP, 0.3) * (1 - W(t, T_BACK, 0.4)) - math.radians(30) * W(t, T_BACK, 0.4)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; a, b = s2_ik(path(t))
        D["boom"].rotation_euler = (0, -a, 0); D["stick"].rotation_euler = (0, -b, 0); D["bucket"].rotation_euler = (0, curl(t), 0)
        for o in (D["boom"], D["stick"], D["bucket"]): o.keyframe_insert("rotation_euler", frame=f)
    # the remote's sticks lean with the work: forward while the arm climbs, a flick at the tip, back while it comes down
    lean = lambda t: math.radians(28) * (W(t, T_PUSH - 0.2, 0.25) - W(t, T_TOP, 0.3)) - math.radians(28) * (W(t, T_BACK - 0.2, 0.25) - W(t, T_LOW, 0.3)) \
        + math.radians(18) * (W(t, T_TIP - 0.12, 0.12) - W(t, T_TIPPED, 0.3))
    for k, (pv, kn) in enumerate(sticks):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; pv.rotation_euler = (-lean(t) * (1 if k == 0 else 0.85), 0, 0); pv.keyframe_insert("rotation_euler", frame=f)
    # ---- the load: rock that rides the bucket up, spills on the crest above us and tumbles back down the face past us
    rk = lw_noise("wall rock", "#2A2522", "#5A4E44", scale=7, rough=0.95, bump=1.0, detail=8)
    rnd = lw_random.Random(4)
    bk = D["bucket"]; bx = D["bx"]
    load = []
    for k in range(16):
        r = rnd.uniform(0.1, 0.2)
        o = K.sph(f"bucket load rock {k}", (0, 0, 0), r, rk, scale=(1, rnd.uniform(0.7, 1.1), 0.8), seg=10, ring=6)
        load.append((o, Vector((bx + rnd.uniform(0.05, 0.42), S2_BOOM.y + rnd.uniform(-0.28, 0.28), S2_BOOM.z - rnd.uniform(0.25, 0.5))), r))
    rides = {}
    for f in range(1, F(T_TIP + 0.6) + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); rides[f] = bk.matrix_world.copy()
    rel = lambda local: Vector(local) - Vector((bx, S2_BOOM.y, S2_BOOM.z))
    for o, local, r in load:
        t_go = T_TIP + 0.1 + rnd.uniform(0.0, 0.25); spin = rnd.uniform(-9, 9); a = rnd.uniform(2.6, 3.8)
        dx = rnd.uniform(-0.3, 2.4); stop = rnd.uniform(0.6, S2_FOOT - 0.3)
        p0 = rides[F(t_go)] @ rel(local)
        y_land = max(p0.y, S2_EDGE - 0.2)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < t_go: o.location = rides[min(f, max(rides))] @ rel(local)
            else:
                s = t - t_go; fall = min(1.0, s / 0.25)
                y = p0.y + (y_land - p0.y) * fall
                z = p0.z + (S2_WALL_H + r - p0.z) * fall * fall
                if s > 0.25:                                 # down the near face toward the works: past the lens
                    q = s - 0.25
                    y = max(stop, y_land - 0.5 * a * q * q)
                    z = (S2_WALL_H if y >= S2_EDGE else s2_face_z(y)) + r * (0.9 + 0.35 * abs(math.sin(10 * q + dx))) + 0.25 * abs(math.sin(4 * q + dx)) * (y < S2_EDGE)
                o.location = (p0.x + dx * min(1.0, s), y, z); o.rotation_euler = (spin * s, spin * 0.5 * s, 0)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f)
    dust = []                                            # the DUST off the tumbling rock: a gas boiling up the face, then settling
    for k in range(2):
        x = S2_DIG.x - S2_BOOM.y - 0.1 + 1.6 * k; y = S2_FOOT - 0.1 + 0.4 * k
        t0 = T_DUCK - 0.15 + 0.12 * k
        dust.append(lw_steam(f"tip dust {k}", (x, y, 0.0), w=1.6, h=2.6, seed=3.7 * k + 1, col=(0.55, 0.5, 0.45), dens=4.0, rise=1.2,
                             lean=(0.2, -0.3), keys=[(t0, 0.0), (t0 + 0.5, 1.0), (t0 + 2.2, 0.45)], t_end=DUR + 1.0))
    # ---- the trucks: rolling along behind the works
    for k, (x0, v) in enumerate(((12.0, -2.0),)):
        truck = s2_truck(f"dump truck {k}"); truck.rotation_euler = (0, 0, math.radians(90))
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; truck.location = (x0 + v * t, S2_FOOT - 0.55, 0.0); truck.keyframe_insert("location", frame=f)
    parked = s2_truck("dump truck waiting", col="#D99A10"); parked.location = (7.8, -1.2, 0.0); parked.rotation_euler = (0, 0, math.radians(-14))   # the next one in line for a load
    for Dk, a_, b_, k in P["far"]:                         # the other diggers keep working: dig, lift, swing back
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; ph = 2 * math.pi * (t / 3.2 + 0.31 * k)
            Dk["boom"].rotation_euler = (0, -(a_ + 0.22 * math.sin(ph)), 0); Dk["stick"].rotation_euler = (0, -(b_ + 0.3 * math.sin(ph + 1.1)), 0)
            Dk["bucket"].rotation_euler = (0, 0.5 * math.sin(ph + 2.0), 0)
            for o in (Dk["boom"], Dk["stick"], Dk["bucket"]): o.keyframe_insert("rotation_euler", frame=f)
    # ---- the floodlights: low at first, blazing on at T_LIGHTS
    for k, (head, L) in enumerate(P["masts"]):
        em = head.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; on = 0.75 + 0.25 * W(t, T_LIGHTS + 0.08 * k, 0.2)      # blazing from the start (board: "switched off"), full at nightfall
            em.default_value = 60.0 * on; em.keyframe_insert("default_value", frame=f)
            L.data.energy = 4000.0 * on; L.data.keyframe_insert("energy", frame=f)
    sk = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
    for f in range(1, NF + 1, 3):
        t = (f - 1) / FPS; sk.default_value = 0.11 * (1 - 0.4 * t / DUR); sk.keyframe_insert("default_value", frame=f)
    # ---- his body: leaning into the push, the duck as the rock comes down past, the grin, the haul back, the lights
    def body(t):
        p = P0.copy()
        p.z += -0.09 * W(t, T_DUCK + 0.15, 0.4) * (1 - W(t, T_GRIN + 0.12, 0.4)) - 0.04 * W(t, T_BACK - 0.2, 0.45) * (1 - W(t, T_LOW, 0.45))
        p.y += 0.12 * W(t, T_PUSH - 0.2, 0.5) * (1 - W(t, T_TOP, 0.5))                       # he walks the sticks forward with the arm
        p.x += 0.06 * math.sin(2 * math.pi * (t - T_PUSH) / 1.3) * W(t, T_PUSH, 0.4) * (1 - W(t, T_TIP, 0.4))   # steering it, his weight side to side
        p.y -= 0.12 * W(t, T_BACK - 0.2, 0.5) * (1 - W(t, T_LIGHTS + 0.3, 0.5))               # and leans back on them as he hauls it down
        p.x -= 0.06 * math.sin(2 * math.pi * (t - T_BACK) / 1.2) * W(t, T_BACK, 0.4) * (1 - W(t, T_LOW, 0.4))
        yaw = YAW0 - math.radians(30) * W(t, T_PUSH, 0.6) * (1 - W(t, T_DUCK - 0.2, 0.45)) + math.radians(8) * W(t, T_DUCK - 0.2, 0.45) * (1 - W(t, T_BACK, 0.55)) \
            - math.radians(25) * W(t, T_BACK, 0.55) * (1 - W(t, T_LIGHTS, 0.55)) + math.radians(14) * W(t, T_LIGHTS, 0.55) \
            + math.radians(18) * W(t, T_GRIN - 0.15, 0.45) * (1 - W(t, T_BACK - 0.1, 0.5))      # he turns his grin to us
        yw = math.atan2(P0.x - PS.x, -(P0.y - PS.y))
        yaw = yw + (yaw - yw) * W(t, 0.9, 0.45)
        return p, yaw
    T_STEP = 0.9
    data.walk_to((P0.x, P0.y), 0.05, T_STEP)
    for f in range(F(T_STEP) + 1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
        data._plant_feet_here(t, lift=(P0.z, P0.z))      # the duck is in his KNEES: his feet stay on the ground
    lw_layer(data, "spine", lambda t: (24 * W(t, T_PUSH - 0.2, 0.45) * (1 - W(t, T_TOP - 0.2, 0.45)) - 12 * W(t, T_TOP - 0.2, 0.45) * (1 - W(t, T_DUCK - 0.15, 0.45))
                                       + 30 * W(t, T_DUCK - 0.2, 0.45) * (1 - W(t, T_GRIN - 0.1, 0.45)) - 16 * W(t, T_BACK - 0.2, 0.45) * (1 - W(t, T_LOW, 0.45))
                                       - 10 * W(t, T_LIGHTS, 0.45), 0, 8 * math.sin(2 * math.pi * (t - T_GRIN) / 0.9) * W(t, T_GRIN, 0.45) * (1 - W(t, T_BACK, 0.45))), 0, DUR + 0.4)
    # his two hands hold the remote out in front of his chest, each on its stick's knob; the remote is keyed to
    # them after finish() (so whatever his body does later, the box stays in his hands and the knobs under them)
    SX = {}
    sc.frame_set(1); bpy.context.view_layer.update()
    for sd in "LR":
        sh_ = acts._shoulder(data, sd); SX[sd] = -0.06 if (sh_ - data.arm.location).dot(Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))) < 0 else 0.06
    lean_k = {sd: (lambda t, m=(1 if SX[sd] < 0 else 0.85): lean(t) * m) for sd in "LR"}   # as the sticks are keyed: pivot x = -lean * m
    def rc_centre(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        mid = (acts._shoulder(data, "L") + acts._shoulder(data, "R")) / 2
        yaw = data.arm.rotation_euler.z; fw = Vector((math.sin(yaw), -math.cos(yaw), 0))
        return mid + fw * S2_RC_FW + Vector((0, 0, S2_RC_UP)), yaw
    PUMP = None                                           # (no hand leaves its stick: the remote needs both)
    pump_w = lambda t: W(t, T_DUCK + 0.0, 0.42) * (1 - W(t, T_BACK - 0.52, 0.42))   # up as he comes out of the duck, back on its stick to haul
    def on_knob(sd):
        def fn(t):
            c, yaw = rc_centre(t)
            k = c + s2_knob_off(SX[sd], lean_k[sd](t), yaw) + Vector((0, 0, 0.035))
            if sd != PUMP or pump_w(t) <= 0: return k
            sh, fw, out, up = lw_frame(data, sd)
            fist = sh + fw * 0.1 + out * 0.12 + up * (0.03 + 0.03 * math.sin(2 * math.pi * (t - T_GRIN) / 0.5))   # out at his side, clear of his ducked head
            return k.lerp(fist, pump_w(t))
        return fn
    for sd in "LR":
        data.reach(sd, on_knob(sd), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- face and head
    BK = lambda t: world(*path(t))
    LENS = Vector((0.4, -1.4, 0.5))
    data.look_at(BK(0.0), 0.0, max_yaw=60, max_pitch=40, blend=0.0)
    data.look_at(BK(T_TOP - 0.5), T_PUSH + 0.4, max_yaw=60, max_pitch=60, blend=0.4)
    data.look_at(Vector((-1.0, 1.5, 0.3)), T_DUCK - 0.2, max_yaw=55, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_GRIN, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(BK(T_LOW), T_BACK + 0.1, max_yaw=40, max_pitch=50, blend=0.3)
    data.look_at(Vector((0.9, -1.3, 0.95)), T_LIGHTS + 0.05, max_yaw=45, max_pitch=30, blend=0.3)      # to us as the lights blaze (board: his back in the last still)
    data.expression("determined", 0.2, T_DUCK - 0.2, blend=0.2)
    data.expression("alarmed", T_DUCK - 0.15, T_GRIN - 0.05, blend=0.12)
    data.expression("happy", T_GRIN, T_BACK - 0.05, blend=0.2)
    data.expression("determined", T_BACK, T_LIGHTS, blend=0.2)
    data.expression("pleased", T_LIGHTS + 0.1, DUR + 1.0, blend=0.2)
    data.finish()
    # the remote is carried on HIM, so its knobs are where his final body puts them: finish() smooths and steadies the
    # torso after the hands were solved, which leaves a hand on a body-carried prop where the chest WAS (5-7 cm off).
    # Solve both hands again, every frame, on the final body
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for sd in "LR":
            data._arm_ik(sd, on_knob(sd)(t), t, 0.35)
    for f in range(1, NF + 1):                             # the remote rides in his hands, on his final body
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        yaw = data.arm.rotation_euler.z
        w = {sd: data.arm.matrix_world @ data.pb[f"fore.{sd}"].tail - Vector((0, 0, 0.035)) - s2_knob_off(SX[sd], lean_k[sd](t), yaw) for sd in "LR"}
        remote.location = (w["L"] + w["R"]) / 2
        remote.rotation_euler = (0, 0, yaw)
        remote.keyframe_insert("location", frame=f); remote.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: low at the foot of the wall, looking up at him, the digger and its arm over him
    # REDESIGN after board round 3 ("eye level with a small bank behind him"; the brief asks for a LOW lens looking up at
    # him and a towering wall): the lens at his knees, tipped up, the black face rising behind him to its crest with
    # the sky above it, the digger's arm swinging up past it
    CAM = Vector((0.46, -0.9, 0.3)); LOOK = Vector((-4.0, 6.0, 2.5))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=20.0, fstop=32.0)      # the works sharp all the way to the sky
    # CUT to the WIDE as the bucket goes over (board round 2: "no three-storey wall", "one digger", "the bucket never
    # tips over a crest"): low beyond his digger, along the wall's line, the black face towering up the frame, the diggers and
    # trucks along it under the floodlights, his bucket tipping over the crest, him small at the sticks
    T_W0, T_W1 = T_TOP - 0.2, T_DUCK - 0.1
    CW = Vector((-6.5, -4.0, 1.3)); LW = Vector((0.5, 6.5, 2.6))      # from the far side of his digger: his face, turned to the bucket, comes to this lens (KEYS: not his back)
    lw_cut(cam, lambda t: (CAM + (LOOK - CAM).normalized() * (0.07 + 0.17 * (1 - ease(min(1.0, t / (0.3 * DUR))))), LOOK, data.pos() + Vector((0, 0, 0.6))),
           lambda t: (CW + Vector((0.15, 0.1, 0.0)) * (t - T_W0), LW, Vector((-2.0, 4.0, 2.0))), T_W0, T_W1, 20.0, 16.0)
    arm_objs = lambda: meshes([D["boom"]])
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("remote stick", "remote control"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("he shoves the sticks and the digger's arm swings up over him with its bucket of black rock", arm_objs, T_PUSH, T_TOP + 0.3, {"whole": False, "moves": True, "hero": False}),
                        ("the rock tumbles back down the wall's face past us in a burst of dust", lambda: [o for o, _l, _r in load] + dust, T_DUCK - 0.2, T_DUCK + 1.2, {"whole": False}),
                        ("he hauls the sticks back and the arm swings down for the next load", arm_objs, T_BACK, T_LOW + 0.3, {"whole": False, "moves": True})])


# ====================================================================================================
# shot3.py
# ====================================================================================================
"""BEAT 3: "So when the lava came, it hit the wall and turned away from the town."

The top of the earth wall: a crest of crushed black rock, the town's roofs safe behind it, the black lava field on the
other side. HIGH, out over the lava, looking down at him on the crest. The lava front, a huge glowing front of cracked
black crust with orange in every crack, rolls in across the field below him and slams into the wall's face, its crust
buckling and splitting red; he braces a fire hose and blasts it, and a huge cloud of white steam bursts up; the front
grinds sideways and slides off along the wall, away from the town; he follows it round, still spraying, and turns to
us, pleased."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FACE_Y = -S3_CREST / 2      # the crest's outer edge (y); the outer face runs down to the foot at -S3_BASE / 2


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


S3_PILE = S3_H - 0.4           # the old lava already heaped against the face: the field rises to here at the wall


def s3_ground_z(x, y):
    """the black lava field: months of old flows heaped up against the wall's outer face, falling away out to the fissure"""
    if y > 0.5: return 0.08 * lw_fbm(x * 0.3, y * 0.3, 19)   # inside the wall: the town's ground, far below the crest
    u = max(0.0, min(1.0, (y + 16.0) / 11.0))
    return S3_PILE * ease(u) + 0.1 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_hose_nozzle():
    """a fire hose's brass nozzle with a grip, and the canvas hose running back from it"""
    root = K.empty("fire hose", (0, 0, 0))
    brass = lw_metal("nozzle brass", "#B8862E", rough=0.25)
    K.cyl("fire hose nozzle", (0, 0.0, 0.0), 0.028, 0.22, brass, rot=(math.pi / 2, 0, 0), v=20, parent=root)
    K.cyl("fire hose nozzle tip", (0, -0.13, 0.0), 0.018, 0.06, brass, rot=(math.pi / 2, 0, 0), v=16, parent=root)
    K.cyl("fire hose grip", (0, 0.05, -0.05), 0.02, 0.09, lw_rubber("nozzle grip", "#1E1E1E", rough=0.6), v=12, parent=root)
    lw_local(root)
    return root


def place_wall_crest():
    """THE TOP OF THE WALL: its crest track of crushed rock, the black lava field running away from its outer face,
    the town's roofs below it on the other side, a parked digger far along the crest, the plume over the far fissure."""
    rnd = lw_random.Random(31)
    lw_grid("lava field ground", -30, 30, -30, 30, 90, 90, s3_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven)
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    K.box("crest track", (0, 0, S3_H + 0.03), (50, S3_CREST - 0.1, 0.06), lw_noise("crushed rock", "#3E3732", "#615750", scale=30, rough=0.95, bump=1.0, detail=10), bev=0.02)
    for k in range(24):                                   # the town inside the wall: street after street of tin roofs
        town_house(f"town house below {k}", (-17 + 4.6 * (k % 8) + rnd.uniform(-0.3, 0.3), 9.0 + 4.4 * (k // 8) + 0.8 * (k % 2), 0), yaw=rnd.uniform(-0.15, 0.15),   # their fronts, doors and windows to the wall
                   roof=ROOFS[k % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=100 + k)
    lava_rock("lava field rock", 120, (-25, 25, -25, -4.6), s3_ground_z, seed=9, r=(0.1, 0.35))
    lava_rock("heap rock", 70, (-5, 4, -4.6, -1.2), s3_ground_z, seed=13, r=(0.06, 0.2))        # the old lava heaped against the face: broken blocks
    lava_rock("field block", 420, (-14, 10, -14, -4.0), s3_ground_z, seed=19, r=(0.05, 0.22), moss=0.12)   # the field outside the wall: broken black blocks, a little moss
    lava_rock("wall face rock", 260, (-14, 12, -4.2, -1.0), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=27, r=(0.08, 0.26), moss=0.0)   # the black rock it is built of, on its face
    lava_rock("works rubble", 160, (-14, 14, 4.4, 9.0), s3_ground_z, seed=12, r=(0.08, 0.3))       # the works yard inside the wall
    for k, x in enumerate((-22.0, -12.0)):               # the eruption's plume off in the distance, a gas leaning over the town
        lw_steam(f"far plume {k}", (x, 40.0 + 4 * k, 0.0), w=7.0, h=24.0, seed=6.6 * k, col=(0.45, 0.43, 0.42), dens=1.6, lean=(0.6, -0.3), rise=1.0, t_end=DUR + 1.0)

    def light():
        k = iceland_light(sun_elev=24, sun_az=-30, sun=3.0, sky=0.4, haze=1.4)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(120))     # a REAL Icelandic-grey sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. From just above the crest, off his shoulder: the old lava heaped high against the face below him.
    A new front rolls in and slams the face right under his boots; he flinches, braces and blasts it with the hose;
    steam bursts up; the front grinds sideways and slides off along the wall; he follows it round with the spray and turns to
    us, pleased."""
    T_ROLL = 0.03 * DUR; T_HIT = 0.21 * DUR; T_SPRAY = 0.35 * DUR; T_SLIDE = 0.52 * DUR; T_THUMB = 0.75 * DUR; T_REL = T_THUMB - 0.12
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    P0 = Vector((-0.2, -0.45, S3_H + 0.06))
    data.place(P0.x, P0.y, 0.0)
    data.arm.location.z = P0.z
    kit = hard_hat(data)
    # ---- REDESIGN after board round 3 ("a contained oval pad ... a pool that stopped, not a flow that turned"): the
    # lava comes in as a TONGUE straight at the wall across the field, hits the face beside him, and TURNS: a new lobe
    # pushes out of its nose sideways along the wall's foot, away from the town's side, the tongue behind it crusting
    # over as a trail. Seen from above it is an L: the flow's path bent by the wall.
    lm = lava_mat("lava front", heat=1.0, scale=3.5, fresh=0.8)
    tm = lava_mat("lava tongue", heat=0.55, scale=3.0, fresh=0.25)
    Y_FACE = -S3_BASE / 2 + (S3_PILE / (S3_H * 0.97)) * (S3_BASE / 2 - S3_CREST / 2 - 0.1)   # where the heap meets the face
    Y_HIT = Y_FACE - 0.45
    XC = 1.0                                               # where the tongue strikes the face: off his right hand
    tout = []
    for k in range(25):
        a = 2 * math.pi * k / 25
        tout.append((0.85 * math.cos(a) + 0.07 * math.sin(3 * a), 3.2 * math.sin(a) + 0.15 * math.cos(4 * a)))
    tongue = lava("lava tongue", tout, z=0.0, thick=0.4, m=tm, seed=7, lumpy=0.16)
    out = []
    for k in range(25):                                    # the deflected lobe: long along the wall, its nose to -X
        a = 2 * math.pi * k / 25
        out.append((3.0 * math.cos(a) + 0.2 * math.sin(3 * a), 0.75 * math.sin(a) + 0.06 * math.cos(5 * a)))
    front = lava("lava front", out, z=0.0, thick=0.45, m=lm, seed=4, lumpy=0.18)
    Z_LAVA = S3_PILE - 0.3
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = ease(min(1.0, max(0.0, (t - T_ROLL) / (T_HIT - T_ROLL)))); v = W(t, T_HIT - 0.05, T_SLIDE + 0.9 - T_HIT)
        tip = -7.5 + (Y_HIT + 0.3 + 7.5) * u
        tongue.location = (XC, tip - 3.2, Z_LAVA - 0.05); tongue.keyframe_insert("location", frame=f)
        sq = 1.0 - 0.1 * lw_kick(t - T_HIT, 0.2)
        tongue.scale = (1.0 + 0.15 * lw_kick(t - T_HIT, 0.3), sq, 1.0 + 0.2 * lw_kick(t - T_HIT, 0.25)); tongue.keyframe_insert("scale", frame=f)
        sx = 0.12 + 0.88 * v
        front.location = (XC + 0.5 - 3.0 * sx, Y_HIT + 0.1, Z_LAVA + 0.03 + 0.15 * W(t, T_HIT - 0.08, 0.25) - 0.08 * W(t, T_SLIDE, 0.8))
        front.scale = (sx, 0.8 + 0.2 * v, 1.0); front.hide_render = t < T_HIT - 0.06
        for k_ in ("location", "scale", "hide_render"): front.keyframe_insert(k_, frame=f)
    lava_flow_key(tm, 0.0, DUR + 0.5, 0.1, axis=1)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.18)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; heat.default_value = 1.1 * (1 + 1.0 * lw_kick(t - T_HIT, 0.35) + 0.4 * W(t, T_HIT, 0.3)); heat.keyframe_insert("default_value", frame=f)
    # glowing chunks the impact throws up off the face, falling back onto the front
    cm = lava_mat("lava chunk", heat=1.2, scale=14.0, fresh=0.7); rnd = lw_random.Random(3); chunks = []
    for k in range(8):
        c = K.sph(f"lava chunk {k}", (0, 0, -5), rnd.uniform(0.015, 0.03), cm, seg=8, ring=6, scale=(1.0, 0.8, 0.7)); chunks.append(c)
        x0 = rnd.uniform(XC - 1.2, XC + 0.6); vy = -rnd.uniform(0.3, 0.9); vz = rnd.uniform(1.6, 2.6); t0 = T_HIT + rnd.uniform(-0.03, 0.12)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = t - t0
            if s < 0: c.location = (x0, Y_FACE, -3.0)
            else:
                z = S3_PILE + 0.7 + vz * s - 4.9 * s * s
                c.location = (x0 + 0.2 * s, Y_FACE - 0.15 + vy * s, max(z, S3_PILE + 0.55))
            c.keyframe_insert("location", frame=f)
    # ---- the hose: the nozzle in his hands, aimed down the face at the front; the jet; the steam where it lands
    noz = s3_hose_nozzle()
    aim = lambda t: Vector((XC - 0.5 + 0.12 * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) - 1.6 * W(t, T_SLIDE, 0.9), Y_FACE - 0.15, S3_PILE + 0.3))   # the corner, then the nose as it slides
    jet_m = bpy.data.materials.get("hose water") or bpy.data.materials.new("hose water")
    jet_m.use_nodes = True; jb = jet_m.node_tree.nodes["Principled BSDF"]
    jb.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1); jb.inputs["Roughness"].default_value = 0.1
    jb.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1); jb.inputs["Emission Strength"].default_value = 0.3; jb.inputs["Transmission Weight"].default_value = 0.6
    drops = [K.sph(f"hose jet {k}", (0, 0, -5), 0.008, jet_m, seg=8, ring=6) for k in range(60)]
    # ---- his body: watching it come, a flinch at the hit, braced back as he opens up, turning with the slide
    yaw0 = math.radians(-12)
    def body_yaw(t):
        return yaw0 + math.radians(24) * (1 - W(t, 0.0, T_HIT + 0.1)) - math.radians(30) * W(t, T_SLIDE - 0.2, 1.0) \
            + math.radians(34) * W(t, T_THUMB - 0.3, 0.75)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.z += 0.03 * lw_kick(t - T_HIT, 0.2)                                       # a jolt at the hit
        p.y += -0.08 * W(t, 0.2, 0.3) + 0.1 * W(t, T_HIT, 0.2) - 0.06 * W(t, T_SPRAY - 0.1, 0.3)   # a step to the edge, a jump back at the hit, in again to spray
        p.y += 0.05 * W(t, T_SPRAY + 0.1, 0.4) * (1 - W(t, T_SPRAY + 0.6, 0.45))                  # the hose kicks him back; he digs in
        p.x -= 0.1 * W(t, T_SPRAY + 0.15, 0.6)                                                       # he shuffles along the crest after the front
        p.y += 0.07 * W(t, T_SLIDE, 0.45) * (1 - W(t, T_SLIDE + 0.55, 0.5))                       # the front grinds: he gives a step
        p.z -= 0.085 * W(t, T_HIT - 0.1, 0.35) * (1 - W(t, T_SPRAY + 0.35, 0.4))                 # knees bent, braced for the hit and the kick
        p.z -= 0.08 * W(t, T_SLIDE - 0.1, 0.35) * (1 - W(t, T_THUMB - 0.25, 0.4))                # and again as he leans the jet into the slide
        p.z += 0.04 * lw_kick(t - T_THUMB, 0.25)                                                     # a bounce: it's gone
        data._kobj(t, loc=tuple(p), rot=body_yaw(t))
        data._plant_feet_here(t, lift=(P0.z, P0.z))                                          # the crouch is in his KNEES: feet stay on the crest
    lw_layer(data, "spine", lambda t: (16 * W(t, 0.0, T_HIT - 0.1) * (1 - W(t, T_HIT - 0.1, 0.4)) - 6 * lw_kick(t - T_HIT, 0.3) + 12 * W(t, T_SPRAY - 0.3, 0.5) * (1 - W(t, T_THUMB - 0.3, 0.6))
                                       - 8 * W(t, T_THUMB, 0.5), 0, 6 * W(t, T_SLIDE, 0.8) * (1 - W(t, T_THUMB - 0.2, 0.6))), 0, DUR + 0.4)
    # his hands on the nozzle: both low at first, raised to aim as he opens it, both on it to the end
    sc.frame_set(1); bpy.context.view_layer.update()
    cam_side = Vector((0.45, -2.55, 0))
    sides = sorted("LR", key=lambda s: -(acts._shoulder(data, s) - data.arm.location).dot(cam_side))
    keys = lambda k: [(0.0, (0.09, -0.01, -0.13)), (0.45, (0.13, 0.0, 0.0)), (T_HIT + 0.12, (0.08, 0.0, -0.12)),
                      (T_SPRAY, (0.12, -0.01 - 0.01 * k, -0.05)), (T_SPRAY + 0.2, (0.07, -0.01 - 0.01 * k, -0.1)), (T_SPRAY + 0.5, (0.14, -0.02 - 0.01 * k, -0.01)),
                      (T_SLIDE + 0.45, (0.09, -0.01 - 0.01 * k, -0.11)), (T_SLIDE + 0.95, (0.13, -0.03 - 0.01 * k, -0.03)), (DUR + 0.5, (0.12, -0.02, -0.05))]
    k0 = [k_ for k_ in keys(0) if k_[0] < T_REL] + [(T_REL + 0.35, (0.11, 0.04, -0.09)), (T_REL + 0.75, (0.08, 0.09, -0.13)), (DUR + 0.5, (0.08, 0.1, -0.13))]   # lets the nozzle go: his hand drops, done (a fist up flipped his elbow)
    data.reach(sides[0], lw_hand(data, sides[0], k0), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)     # it held: one hand off the nozzle
    data.reach(sides[1], lw_hand(data, sides[1], keys(1)), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)
    LENS = Vector((-0.6, -3.6, S3_H + 1.3))
    data.look_at(Vector((XC, -6.0, S3_PILE)), 0.0, max_yaw=50, max_pitch=50, blend=0.0)
    data.look_at(Vector((XC - 0.3, Y_HIT, S3_PILE + 0.4)), T_HIT - 0.15, max_yaw=50, max_pitch=55, blend=0.15)
    data.look_at(aim(T_SPRAY), T_SPRAY, max_yaw=50, max_pitch=55, blend=0.25)
    data.look_at(Vector((-2.5, Y_HIT, S3_PILE + 0.4)), T_SLIDE + 0.1, max_yaw=50, max_pitch=55, blend=0.3)
    data.look_at(LENS, T_THUMB, max_yaw=50, max_pitch=50, blend=0.25)
    data.expression("alarmed", T_ROLL + 0.1, T_HIT + 0.3, blend=0.12)
    data.expression("determined", T_HIT + 0.35, T_SLIDE + 0.25, blend=0.2)
    data.expression("pleased", T_SLIDE + 0.35, DUR + 1.0, blend=0.25)
    data.finish()
    for f in range(1, NF + 1):                             # the nozzle in his hands, pointing at the spray
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        hs = [data.arm.matrix_world @ data.pb[f"hand.{s}"].tail for s in sides]
        p = (hs[0] + hs[1]) / 2 if t < T_REL else hs[1]
        d = (aim(t) - p).normalized()
        noz.location = p + d * 0.07; noz.rotation_euler = Vector((0, -1, 0)).rotation_difference(d).to_euler()
        noz.keyframe_insert("location", frame=f); noz.keyframe_insert("rotation_euler", frame=f)
    # the canvas hose: from the hydrant on the crest behind him, along the ground, up to the nozzle's tail
    cu = bpy.data.curves.new("fire hose line", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.02; cu.bevel_resolution = 3
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(3)
    hose = lw_link(bpy.data.objects.new("fire hose line", cu)); hose.data.materials.append(lw_canvas("hose canvas", "#B8342A"))
    HYD = Vector((P0.x - 1.4, P0.y + 0.6, S3_H))
    K.cyl("fire hydrant", (HYD.x, HYD.y, S3_H + 0.25), 0.07, 0.5, lw_paint("hydrant red", "#C8231B", rough=0.4), v=16)
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        tail = noz.matrix_world @ Vector((0, 0.12, 0)); foot = data.arm.matrix_world.translation
        pts = [HYD + Vector((0, 0, 0.12)), Vector((foot.x - 0.6, foot.y + 0.35, S3_H + 0.06)),
               Vector((foot.x - 0.15, foot.y + 0.2, S3_H + 0.06)), tail]
        for bp, q in zip(sp.bezier_points, pts):
            bp.co = q; bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.keyframe_insert("co", frame=f)
    # the jet: a solid rope of water from the nozzle tip arcing down to the aim point, breaking into spray at its end
    jc = bpy.data.curves.new("hose jet line", 'CURVE'); jc.dimensions = '3D'; jc.bevel_depth = 0.01; jc.bevel_resolution = 2
    jsp = jc.splines.new('POLY'); jsp.points.add(5)
    jet = lw_link(bpy.data.objects.new("hose jet line", jc)); jet.data.materials.append(jet_m)
    noz_tip = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); noz_tip[f] = noz.matrix_world @ Vector((0, -0.16, 0))
    noz_tip = {f: sum((noz_tip[min(NF, max(1, f + d))] for d in (-2, -1, 0, 1, 2)), Vector()) / 5 for f in noz_tip}   # the jet leaves a steadied tip
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; on = W(t, T_SPRAY, 0.12)
        a = noz_tip[f]; b = a.lerp(aim(t), max(0.02, on))
        pts = [a.lerp(b, u) + Vector((0, 0, 0.12 * on * math.sin(math.pi * u))) for u in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        for bp, q in zip(jsp.points, pts):
            bp.co = (q.x, q.y, q.z, 1.0); bp.keyframe_insert("co", frame=f)
        jet.hide_render = on < 0.02; jet.keyframe_insert("hide_render", frame=f)
    jr = lw_random.Random(17); jit = [Vector((jr.uniform(-1, 1), jr.uniform(-1, 1), jr.uniform(-1, 1))) for _ in drops]
    for k, o in enumerate(drops):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = t >= T_SPRAY
            if not on: o.location = (0, 0, -6)
            else:
                u = 0.75 + 0.25 * (((k / len(drops)) + 2.0 * t) % 1.0)
                a = noz_tip[f]; b = aim(t); m_ = a.lerp(b, u); m_.z += 0.25 * math.sin(math.pi * u)
                o.location = m_ + jit[k] * (0.015 + 0.12 * u * u)             # the jet fans out into fine spray as it falls
            o.keyframe_insert("location", frame=f)
    steam = []                                           # STEAM as a gas: it boils up where the jet lands, swelling into a column
    for k, t0 in enumerate((T_SPRAY + 0.06,)):          # that drifts off him and out over the field, off the lens's side
        b = aim(t0)
        steam.append(lw_steam(f"lava steam {k}", (1.4, -2.0, b.z - 0.3), w=0.95, h=3.4, seed=5.1 * k + 2, rise=2.4, dens=7.0,
                              lean=(0.25, 0.0), keys=[(t0, 0.0), (t0 + 0.8, 1.0), (DUR + 0.5, 0.8)], t_end=DUR + 1.0))
    # ---- the lens: just above the crest off his shoulder, out over the heap, looking down past him at the front
    CAM = LENS.copy() + Vector((0.0, 0.0, 0.45)); LOOK = Vector((-0.4, -0.8, S3_H + 0.16))    # high out over the heap: him on the crest, the town's roofs safe behind him, the front under him
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=56.0, fstop=22.0)
    def cam_at(t):                                          # it leans in at the hit, then drifts after the front as it slides off
        mv = Vector((0.03, 0.12, -0.03)) * W(t, T_HIT - 0.1, 0.9) + Vector((-0.12, 0.0, 0.0)) * W(t, T_SLIDE - 0.2, 1.4)
        return CAM + mv, LOOK + mv * 0.8, data.pos() + Vector((0, 0, 0.5))
    # CUT to the WIDE as the front grinds off (board round 2: "it never turns away from the town", "no town behind"):
    # high out over the lava field, the whole front against the wall's face sliding off along it, him small on the crest
    # with his jet and steam, the town's roofs safe on the far side
    T_W0, T_W1 = T_HIT - 0.15, T_REL - 0.1
    CW = Vector((3.4, -8.6, 8.2)); LW = Vector((-0.6, 1.0, 2.6))       # high out over the field: the tongue, the turn, the lobe along the wall, him and the town beyond
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.35, 0.15, -0.1)) * (t - T_W0), LW, Vector((0.0, -1.5, 4.0))), T_W0, T_W1, 56.0, 28.0)
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=("fire hose",), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("the lava front rolls in and slams into the wall's face, then slides off along it", lambda: [tongue, front], T_HIT - 0.2, DUR, {"whole": False}),
                        ("he blasts the front with the hose and a cloud of steam bursts up", lambda: steam, T_SPRAY + 0.1, DUR, {"whole": False, "moves": True})])


# ====================================================================================================
# shot4.py
# ====================================================================================================
"""BEAT 4: "But then the ground split open inside the wall, and lava poured straight into the streets."

An empty street of the town INSIDE the wall, mid-afternoon: town houses down both sides, the earth wall a dark line
across the end of the street with smoke over it. The lens backs down the street ahead of him as he pushes a wheelbarrow
of sandbags toward us. The road jolts and a crack tears across the asphalt right in front of his wheel, kerb to kerb; it
yawns open, orange inside, steam shooting out; he lets go of the barrow and leaps back; the lava wells up out of the
crack and pours over the road, the barrow tipping in and catching fire; the lava runs down the street toward the
red-roofed corner house and he hops back from it, arms up."""

S4_YC = 0.0                     # the crack's line (y), across the street
S4_HALF = 3.0                   # the asphalt and pavement, out to the house fronts (x)
S4_KERB = 1.75                  # the kerbs (x): a narrow town street, so a long lens down it holds both rows of houses
S4_FRONT = 2.35                 # the house fronts (x)


def s4_zig(x):
    """the crack's zig-zag line across the street: y at x"""
    return S4_YC + 0.12 * math.sin(3.1 * x + 0.4) + 0.07 * math.sin(7.3 * x + 1.1)


def s4_ground_z(x, y):
    z = -0.6 if abs(x) < 3.2 and abs(y - S4_YC) < 1.8 else -0.06   # under the slabs; well under the crack's trench (the gap showed black ground)
    if abs(x) > 3.3: z += 0.06 + 0.1 * lw_fbm(x * 0.4, y * 0.4, 23)
    return z


def s4_slab(name, near, m):
    """one side of the cracked street: the asphalt from the crack to the end of the street (near: toward the lens),
    its crack edge the zig-zag with a 0.25 m face down into the ground. Built as strips of quads, every face up or out
    (one concave n-gon rendered black). Returns the object, origin on the crack line."""
    xs = [-S4_HALF + 2 * S4_HALF * k / 40 for k in range(41)]
    far_y = -14.0 if near else 44.0
    bm = LW_bmesh.new()
    te = [bm.verts.new((x, s4_zig(x) - S4_YC, 0.0)) for x in xs]
    tf = [bm.verts.new((x, far_y - S4_YC, 0.0)) for x in xs]
    be = [bm.verts.new((x, s4_zig(x) - S4_YC, -0.25)) for x in xs]
    for i in range(40):
        q = (te[i], te[i + 1], tf[i + 1], tf[i]) if not near else (tf[i], tf[i + 1], te[i + 1], te[i])
        bm.faces.new(q)
        w = (te[i], be[i], be[i + 1], te[i + 1]) if not near else (te[i + 1], be[i + 1], be[i], te[i])
        bm.faces.new(w)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        if abs(p.normal.z) > 0.5 and p.normal.z < 0: p.flip()
    me.materials.append(m)
    o = lw_link(bpy.data.objects.new(name, me)); o.location = (0, S4_YC, 0.0)
    return o


def s4_barrow():
    """a builder's wheelbarrow of sandbags facing -Y: a steel tray, one wheel at its nose, two long handles back toward
    him, two legs. Built with the axle at its origin and the handles' ends at (±0.1, 0.72, 0.27): pitched for pushing."""
    root = K.empty("wheelbarrow", (0, 0, 0))
    tray = lw_metal("barrow galvanised", "#8E9398", rough=0.42); steel = lw_paint("barrow frame red", "#9E2A1E", rough=0.45)      # a galvanised tray on a red tube frame: a builder's barrow, not a toy
    K.box("wheelbarrow tray", (0, 0.3, 0.2), (0.4, 0.5, 0.05), tray, bev=0.02, parent=root)
    for sx in (-1, 1):
        K.box("wheelbarrow tray side", (sx * 0.2, 0.3, 0.28), (0.03, 0.5, 0.16), tray, bev=0.01, parent=root)
        K.cyl("wheelbarrow handle", (sx * 0.1, 0.38, 0.14), 0.015, 0.72, steel, rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
        K.cyl("wheelbarrow leg", (sx * 0.12, 0.5, 0.07), 0.012, 0.16, steel, v=10, parent=root)
    K.box("wheelbarrow tray front", (0, 0.06, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    K.box("wheelbarrow tray back", (0, 0.54, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    rim = lw_metal("barrow rim", "#B4B8BC", rough=0.3)                 # the rolled rim round the tray's lip
    for sx in (-1, 1):
        K.cyl("wheelbarrow tray rim", (sx * 0.205, 0.3, 0.365), 0.012, 0.52, rim, rot=(math.pi / 2, 0, 0), v=10, parent=root)
    for y in (0.055, 0.545):
        K.cyl("wheelbarrow tray rim", (0, y, 0.365), 0.012, 0.43, rim, rot=(0, math.pi / 2, 0), v=10, parent=root)
    for sx in (-1, 1):
        K.cyl("wheelbarrow handle grip", (sx * 0.1, 0.7, 0.255), 0.02, 0.1, lw_rubber("grip black", "#151515", rough=0.7), rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
    K.cyl("wheelbarrow wheel", (0, 0, 0), 0.1, 0.06, lw_rubber("barrow tyre", "#141414", rough=0.8), rot=(0, math.pi / 2, 0), v=24, parent=root)
    K.cyl("wheelbarrow hub", (0, 0, 0), 0.03, 0.07, steel, rot=(0, math.pi / 2, 0), v=12, parent=root)
    sand = lw_canvas("sandbag hessian", "#9A8456")   # a coarse weave
    tie = lw_canvas("sandbag tie", "#4A3A22")
    for k, (x, y, rz) in enumerate(((-0.085, 0.22, 0.1), (0.085, 0.24, -0.08), (0.0, 0.4, 1.45), (-0.02, 0.33, 0.05))):
        sb = K.box(f"wheelbarrow sandbag {k}", (x, y, 0.255 + 0.05 * (k > 2)), (0.15, 0.26, 0.075), sand, bev=0.035, parent=root)
        sb.rotation_euler = (0, 0, rz)
        K.box(f"wheelbarrow sandbag tie {k}", (x + 0.12 * math.sin(-rz) * 0, y + 0.13 * math.cos(rz), 0.255 + 0.05 * (k > 2)), (0.05, 0.03, 0.05), tie, bev=0.01, parent=root)
    flames = []                                          # its fire is a gas lit where it lands (shot4), not flame-shaped balls
    lw_local(root)
    return root, flames


def place_town_crack():
    """AN EMPTY STREET INSIDE THE WALL: asphalt and pavements between two rows of town houses, the red-roofed house on
    the corner, the earth wall across the end of the street with smoke over it, the lava field beyond."""
    rnd = lw_random.Random(41)
    lw_grid("town ground", -30, 30, -16, 60, 90, 100, s4_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))
    asph = ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt")          # REAL asphalt (Poly Haven)
    near = s4_slab("street near", True, asph)
    far = s4_slab("street far", False, asph)
    paint = K.mat("road paint", "#E9E4D4", rough=0.6)
    lines = []
    for y in list(range(-12, 0, 2)) + list(range(1, 40, 2)):
        o = K.box("centre line", (0, y + 0.5 - (0.6 if y < 0 else 0), 0.004), (0.08, 0.9, 0.006), paint, bev=0)
        o.parent = near if y < 0 else far; o.matrix_parent_inverse = (near if y < 0 else far).matrix_world.inverted()
        lines.append(o)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        for slab, y0, y1 in ((near, -14.0, -0.2), (far, 0.2, 40.0)):
            o = K.box("kerb", (sx * S4_KERB, (y0 + y1) / 2, 0.04), (0.12, y1 - y0, 0.08), kerb, bev=0.01)
            o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    trench = lava_mat("crack lava", heat=1.4, scale=4.0, fresh=0.6)
    K.box("crack trench", (0, S4_YC, -0.32), (2 * S4_HALF + 0.4, 1.6, 0.1), trench, bev=0)
    for sy in (-1, 1):
        K.box("crack wall rock", (0, S4_YC + sy * 0.85, -0.23), (2 * S4_HALF + 0.4, 0.1, 0.4), lw_noise("crack rock", "#2A2522", "#4A3E36", scale=10, rough=0.95, bump=1.0), bev=0)
    houses = []
    for sx in (-1, 1):
        y = -9.0 + (0.6 if sx > 0 else 0.0); k = 0
        while y < 34.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            corner = sx > 0 and abs(y + w / 2 - 2.4) < 2.0
            roof = "#C0302A" if corner else ROOFS[(k * 3 + (sx > 0) + 1) % len(ROOFS)]
            if roof == "#B8352B" and not corner: roof = ROOFS[2]
            hs = town_house(f"town house {sx}_{k}" + (" corner" if corner else ""), (sx * (S4_FRONT + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            roof=roof, wall=WALLS[k % len(WALLS)], base=0.3, seed=k + 20)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    wall = earth_wall("earth wall", [(x, 40.0 + 0.01 * x * x) for x in range(-30, 32, 2)], h=4.4, crest=1.4, base=8.5, seed=12)
    for k, x in enumerate((-9.0, 1.0, 10.0)):            # the eruption's smoke over the wall: rolling columns of gas, leaning off on the wind
        lw_steam(f"wall smoke {k}", (x, 48.0 + 2 * k, 2.0), w=4.5, h=16.0, seed=3.3 * k, col=(0.42, 0.41, 0.42), dens=2.5, lean=(0.5, 0.2), rise=1.2, t_end=DUR + 1.0)
    for k in range(5):
        K.sph("far mountain", (-40 + 20 * k, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.8), seg=24, ring=12)
    # the street under the eruption's fall-out (board EMPTY: "a smooth, bare region"): grit and lava cinders blown over
    # the asphalt, a drain grating at each kerb, the old road's patched cracks
    bits = lava_rock("street cinders", 260, (-S4_KERB + 0.1, S4_KERB - 0.1, -8.0, 30.0), lambda x, y: 0.0, seed=44, r=(0.015, 0.05), moss=0.0,
              avoid=lambda x, y: abs(y - S4_YC) < 1.3)
    patch = K.mat("road patch", "#1E1E20", rough=0.9)
    for k in range(14):
        y = -7.0 + 2.6 * k + rnd.uniform(-0.5, 0.5)
        if abs(y - S4_YC) < 1.4: continue
        o = K.box("road crack seal", (rnd.uniform(-1.2, 1.2), y, 0.012), (rnd.uniform(0.6, 1.4), 0.025, 0.004), patch, bev=0.0); o.rotation_euler = (0, 0, rnd.uniform(-0.6, 0.6)); bits.append(o)
    bits += lava_rock("street rubble", 150, (-S4_KERB + 0.15, S4_KERB - 0.15, 1.6, 14.0), lambda x, y: 0.0, seed=45, r=(0.04, 0.12), moss=0.0,
                      avoid=lambda x, y: abs(x) < 0.75 and y < 3.4)          # the bigger bombs the eruption threw over the town
    patch2 = K.mat("road patch old", "#2B2B2E", rough=0.95)
    for k in range(9):                                   # the old road's dug-up and re-laid squares
        y = 1.8 + 1.4 * k + rnd.uniform(-0.3, 0.3); x = rnd.choice((-1, 1)) * rnd.uniform(0.85, 1.2)
        o = K.box("road repair patch", (x, y, 0.006), (rnd.uniform(0.5, 0.9), rnd.uniform(0.5, 1.0), 0.004), patch2 if k % 2 else patch, bev=0.0)
        o.rotation_euler = (0, 0, rnd.uniform(-0.08, 0.08)); bits.append(o)
    grate = lw_metal("drain grating", "#2A2B2D", rough=0.6)
    for k in range(6):
        for sx in (-1, 1):
            y = -6.0 + 6.0 * k + (1.5 if sx > 0 else 0.0)
            if abs(y - S4_YC) < 1.4: continue
            bits.append(K.box("drain grating", (sx * (S4_KERB - 0.2), y, 0.012), (0.22, 0.4, 0.008), grate, bev=0.0))
    bpy.context.view_layer.update()
    for o in bits:                                       # they ride their slab of the street when it jolts
        slab = near if o.location.y < S4_YC else far
        o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    for k in range(3):                                   # REAL street lamps (Poly Haven) along the left kerb
        ph_model("street_lamp_01", (-(S4_KERB + 0.25), 6 + 6 * k, 0.0), rot=(0, 0, -math.pi / 2), scale=0.5, name=f"street lamp {k}")

    def light():
        k = iceland_light(sun_elev=30, sun_az=-30, sun=3.2, sky=0.45, haze=1.2)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(60))      # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, near=near, far=far, houses=houses)


def shot4():
    """THE CRACK. The lens backs down the street ahead of him as he pushes the barrow toward us; the road jolts and the
    crack tears across in front of his wheel; it yawns open, glowing, steam shooting up; he lets go and leaps back; lava
    wells up and pours over the road, the barrow tips in and burns; the lava runs toward the corner house and he hops
    back from it, arms up."""
    T_STOP = 0.2 * DUR; T_JOLT = 0.23 * DUR; T_TEAR = T_JOLT + 0.05; T_TORN = T_TEAR + 0.35
    T_OPEN0 = 0.33 * DUR; T_OPEN1 = 0.5 * DUR; T_LET = 0.36 * DUR
    T_POUR = 0.55 * DUR; T_TIP = 0.6 * DUR; T_RUN = 0.7 * DUR
    W = lw_win
    P = place_town_crack()
    light = P["light"]; near, far = P["near"], P["far"]
    data = load_data()
    Y0, YS = 2.4, 0.92                                     # where he starts pushing and where he stops (y)
    data.place(0.15, Y0, 0.0)
    kit = hard_hat(data)
    data.walk_to((0.15, YS), 0.0, T_STOP, pushing=True)
    # ---- the leap back at T_LET and the hops back at T_RUN, facing the crack (and us) the whole time
    def hop(t, t0, d, h, T=0.4):
        u = min(1.0, max(0.0, (t - t0) / T)); return d * ease(u), h * math.sin(math.pi * u)
    for f in range(F(T_STOP) + 1, NF + 1):
        t = (f - 1) / FPS
        y1, z1 = hop(t, T_LET, 0.32, 0.13, 0.5); y0_, z0_ = hop(t, T_POUR - 0.1, 0.1, 0.09, 0.4); y1 += y0_; z1 += z0_; y2, z2 = hop(t, T_RUN, 0.13, 0.06); y3, z3 = hop(t, T_RUN + 0.45, 0.14, 0.06)
        jolt = -0.03 * lw_kick(t - T_JOLT, 0.1) - 0.05 * lw_kick(t - T_POUR, 0.15)
        sway = 0.04 * math.sin(2 * math.pi * (t - T_LET) / 1.1) * W(t, T_LET + 0.3, 0.3)
        data._kobj(t, loc=(0.15 + sway - 0.45 * W(t, T_RUN, 0.7), YS + y1 + y2 + y3 + 0.04 * W(t, T_POUR, 0.2), z1 + z2 + z3 + jolt),
                   rot=math.radians(-8) * W(t, T_LET, 0.3) + math.radians(12) * math.sin(2 * math.pi * (t - T_LET) / 1.6) * W(t, T_LET + 0.3, 0.4) + math.radians(-14) * W(t, T_RUN, 0.5))
    lw_layer(data, "spine", lambda t: (14 * W(t, 0.0, 0.2) * (1 - W(t, T_STOP, 0.2)) - 16 * lw_kick(t - T_JOLT, 0.18) + 10 * W(t, T_TEAR, 0.25) * (1 - W(t, T_LET, 0.2))
                                       - 14 * W(t, T_LET, 0.2) * (1 - W(t, T_LET + 0.6, 0.3)) - 10 * W(t, T_RUN, 0.3)
, 0, 0), 0, DUR + 0.4)
    # ---- the barrow: pushed ahead of him, set down at the stop, let go; it rolls to the edge, tips in and burns
    bar, flames = s4_barrow()
    sc.frame_set(1); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)
    def bpos(t):
        sc.frame_set(F(min(t, T_LET))); bpy.context.view_layer.update()
        c = data.pos(); return Vector((c.x, c.y - 0.13 - 0.72, 0.1))
    path = {f: bpos((f - 1) / FPS) for f in range(1, F(T_LET) + 1)}
    y_edge = s4_zig(0.15) + 0.03
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        p = path[min(f, F(T_LET))].copy()
        pitch = math.radians(-6) * W(t, T_STOP - 0.1, 0.5)    # set down at the stop: the handles drop onto its legs
        p.z -= 0.03 * lw_kick(t - T_JOLT, 0.1)                  # the road jolts it with him
        if t > T_LET:                                       # let go: it rolls to the edge, then the tip
            roll = 0.25 * W(t, T_OPEN0 + 0.2, 0.9)
            p.y = max(y_edge - 0.12, p.y - roll)
            tip = W(t, T_TIP, 0.6)
            pitch += math.radians(52) * tip                  # nose first into the gap, its wheel sinking into the glow
            p.z -= 0.3 * tip; p.x += 1.0 * W(t, T_OPEN0 + 0.2, 1.0)       # rolling off toward the kerb as it goes: it burns off his line to the lens
        bar.location = p; bar.rotation_euler = (pitch, 0, 0)
        bar.keyframe_insert("location", frame=f); bar.keyframe_insert("rotation_euler", frame=f)
    sc.frame_set(NF); bpy.context.view_layer.update()     # the barrow burns where it tipped: its sandbags and the tray catch
    fb = bar.matrix_world @ Vector((0.0, 0.32, 0.2))
    lw_fire_column("barrow fire", (fb.x, fb.y, fb.z), w=0.42, h_fire=0.8, h_smoke=2.2, lean=(0.25, 0.0), t_end=DUR + 1.0, seed=4.2, fire=6.0,
                   smoke_d=3.0, keys=[(T_TIP + 0.2, 0.0), (T_TIP + 0.75, 1.0)])
    bl = lw_point("barrow fire light", (fb.x, fb.y - 0.3, fb.z + 0.5), 0.0, col=(1.0, 0.45, 0.15), r=0.2)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; bl.data.energy = 120.0 * W(t, T_TIP + 0.2, 0.55) * (1 + 0.25 * math.sin(2 * math.pi * 4.1 * t)); bl.data.keyframe_insert("energy", frame=f)
    def handle(sx):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update()
            return bar.matrix_world @ Vector((sx * 0.1, 0.7, 0.27))
        return fn
    for sd, sx in zip(sides, (-1, 1)):
        data.reach(sd, handle(sx), 0.0, T_LET, lead=0.05, back=None, elbow_out=0.35)
    # arms up against the heat: hands up at his face's sides from the leap, higher at the hops back
    for sd in sides:
        HK = [(T_LET + 0.7, (0.08, 0.14, 0.0)), (T_POUR - 0.03, (0.07, 0.13, 0.07)), (T_POUR + 0.25, (0.08, 0.15, 0.0)), (T_TIP + 0.3, (0.04, 0.1, 0.12)),
              (T_RUN, (0.07, 0.13, 0.07)), (T_RUN + 0.4, (0.08, 0.15, 0.06)), (T_RUN + 0.8, (0.06, 0.12, -0.04)), (DUR + 0.4, (0.08, 0.15, 0.05))]
        data.reach(sd, lw_hand(data, sd, HK), HK[0][0], DUR + 0.3, lead=0.7, back=None, elbow_out=0.4)
    # ---- the crack: a hairline tears across from kerb to kerb, then the street pulls apart and the lava shows in the gap
    gm = lava_mat("crack glow", heat=1.6, scale=6.0)
    xs = [-S4_HALF + 2 * S4_HALF * k / 60 for k in range(61)]
    bm = LW_bmesh.new()
    far_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC, 0.004)) for x in xs]
    near_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.035, 0.004)) for x in xs]
    for i in range(60): bm.faces.new((near_e[i], near_e[i + 1], far_e[i + 1], far_e[i]))
    me = bpy.data.meshes.new("crack glow"); bm.to_mesh(me); bm.free(); me.materials.append(gm)
    tear = lw_link(bpy.data.objects.new("crack glow", me)); tear.location = (-S4_HALF, S4_YC, 0.0)
    tear.shape_key_add(name="Basis")
    op = tear.shape_key_add(name="open")
    for i in range(61): op.data[61 + i].co.y = s4_zig(xs[i]) - S4_YC - 0.85
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR); o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0)
        tear.scale = (max(0.002, u), 1, 1); tear.hide_render = u < 0.01; op.value = o
        tear.keyframe_insert("scale", frame=f); tear.keyframe_insert("hide_render", frame=f); op.keyframe_insert("value", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0); sh = 0.015 * math.sin(2 * math.pi * 11 * t) * lw_kick(t - T_JOLT, 0.25)
        near.location = (sh, S4_YC - 0.8 * o, 0.02 * o + 0.04 * lw_kick(t - T_JOLT, 0.12)); near.rotation_euler = (math.radians(-4) * o, 0, 0)
        far.location = (-sh, S4_YC, 0.0)
        for o_ in (near, far): o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    # board round 3: "a thin painted line on the road, with no gap opening". The asphalt BREAKS along both lips: slabs of
    # it heave up and tilt as the street pulls apart, raw dark edges catching the glow
    lip = lw_noise("broken asphalt", "#3A3A3C", "#5A5A5E", scale=30, rough=0.9, bump=0.8)
    rk = lw_random.Random(7)
    lips = []
    for slab, sg in ((near, -1), (far, 1)):
        x = -S4_HALF + 0.1
        while x < S4_HALF - 0.1:
            w = rk.uniform(0.18, 0.34); xc = x + w / 2
            ch = K.box("crack lip chunk", (xc, s4_zig(xc) - S4_YC + sg * rk.uniform(0.04, 0.1), -0.01), (w * 0.92, rk.uniform(0.12, 0.22), 0.07), lip, bev=0.012)
            ch.parent = slab; ch.matrix_parent_inverse = slab.matrix_world.inverted(); lips.append(ch)
            lift = rk.uniform(0.25, 0.55); yaw = rk.uniform(-0.25, 0.25); t0 = T_OPEN0 + 0.1 * abs(xc) / S4_HALF
            for f in range(1, NF + 1):
                t = (f - 1) / FPS; o = W(t, t0, 0.45)
                ch.rotation_euler = (-sg * lift * o, 0.15 * yaw * o, yaw * o); ch.location.z = -0.01 + 0.05 * o
                ch.keyframe_insert("rotation_euler", frame=f); ch.keyframe_insert("location", frame=f)
            x += w
    lava_flow_key(gm, 0.0, DUR + 0.5, 0.2)
    trench = bpy.data.materials["crack lava"]
    lava_flow_key(trench, 0.0, DUR + 0.5, 0.25)
    # ---- steam shooting up out of the crack as it opens
    steam = []
    for k, x in enumerate((-2.1, -1.3, 1.4, 2.2)):        # out to the sides of him: the gap in front of him stays clear; steam as a GAS
        t0 = T_OPEN0 + 0.08 * k
        steam.append(lw_steam(f"crack steam {k}", (x, s4_zig(x) - 0.2, -0.25), w=0.7, h=2.8, seed=2.1 * k, rise=2.6,
                              keys=[(t0, 0.0), (t0 + 0.45, 1.0), (DUR, 0.55)], t_end=DUR + 1.0))
    # ---- the lava: it wells up in the crack and pours out over the road, toward him and the corner house
    lm = lava_mat("street lava", heat=1.2, scale=4.0, fresh=0.8)
    out = []
    for k in range(28):
        a = 2 * math.pi * k / 28
        out.append((1.0 * math.cos(a) + 0.07 * math.sin(4 * a) + 0.05 * math.sin(7 * a), 1.0 * math.sin(a) + 0.08 * math.cos(5 * a)))
    flow = lava("street lava", out, z=0.0, thick=0.2, m=lm, seed=6, lumpy=0.07)
    # board round 3: "the street in front of him never fills with orange", "a thin glowing band, not lava pouring":
    # a liquid tongue swells up out of the gap and runs DOWN the street at the lens over the near slab, kerb to kerb
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_POUR, DUR - T_POUR); w_ = W(t, T_POUR - 0.25, 0.4)
        L_ = 0.3 + 1.0 * u
        flow.location = (0.05 + 0.1 * math.sin(3 * t), S4_YC + 0.6 - L_, -0.22 + 0.25 * w_)   # wells up round the tipped barrow and runs at the lens
        flow.scale = (0.6 + 1.0 * u + 0.4 * w_, L_, 1.0 + 0.4 * (1 - u) * w_); flow.keyframe_insert("location", frame=f); flow.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.3, axis=1)
    glow = lw_point("crack glow", (0.0, S4_YC, 0.25), 0.0, col=(1.0, 0.45, 0.12), r=0.6)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; glow.data.energy = 260.0 * W(t, T_OPEN0, 0.5) + 200.0 * W(t, T_POUR, 0.6); glow.data.keyframe_insert("energy", frame=f)
    # ---- face and head: one feeling per moment, held
    data.look_at(Vector((0.15, -2.5, 0.6)), 0.0, max_yaw=40, blend=0.0)
    data.look_at(Vector((0.1, S4_YC, 0.0)), T_JOLT + 0.05, max_yaw=50, max_pitch=50, blend=0.2)
    data.look_at(Vector((0.4, S4_YC + 0.6, 0.0)), T_POUR + 0.1, max_yaw=50, max_pitch=50, blend=0.3)
    data.look_at(Vector((2.6, 2.4, 0.8)), T_RUN - 0.3, max_yaw=60, max_pitch=40, blend=0.3)
    data.look_at(Vector((0.2, -2.5, 0.7)), T_RUN + 0.45, max_yaw=50, blend=0.3)
    data.expression("determined", 0.0, T_JOLT, blend=0.2)
    data.expression("surprised", T_JOLT + 0.02, T_LET - 0.05, blend=0.12)
    data.expression("alarmed", T_LET, DUR + 1.0, blend=0.15)
    data.finish()
    # ---- the lens: backing down the street ahead of him while he pushes, then holding as the street splits
    # REDESIGN after board round 3 ("80% bare asphalt", "houses are slivers cut by the top edge", "no wall at the end"):
    # the lens comes DOWN to his height and goes LONG, right up the middle of a narrow street, so both rows of houses
    # close in behind him and the wall with its smoke stands across the end of the street over his head; the crack
    # tears across between him and us and the lava runs down the street at the lens
    CAM = Vector((0.3, YS - 4.0, 1.0)); LOOK = Vector((0.12, 40.0, -4.2))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=70.0, fstop=16.0)
    def cam_at(t):
        sc.frame_set(F(min(t, T_STOP))); bpy.context.view_layer.update()
        dy = data.pos().y - YS
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * lw_kick(t - T_JOLT, 0.25) * 2
        back = Vector((0, 0.0, 0.0))
        p0 = data.pos().copy(); sc.frame_set(F(t)); bpy.context.view_layer.update()
        fol = (data.pos() - p0) * 0.8; fol.z = 0.0                     # and pans with him as he leaps and hops back
        dolly = Vector(((data.pos() - p0).x * 0.8, (data.pos() - p0).y * 1.0, 0))               # and keeps its distance as he backs away
        return CAM + Vector((0, dy * 0.9, 0)) + shake + back + dolly, LOOK + Vector((0, dy * 0.9, 0)) + shake + back + fol, data.pos() + Vector((0, 0, 0.6))   # it backs off slower than he comes: he and the barrow come AT us
    # CUT to the WIDE as the lava pours (board round 2: "80% bare asphalt", "no wall at the end of the street", "never
    # seen pouring toward a house"): high behind the lens and up the street, the crack glowing kerb to kerb, the lava
    # running at the red-roofed corner house, the street's houses both sides, the wall across its end with smoke over it
    T_W0, T_W1 = T_TIP - 0.05, T_RUN + 0.35
    CW = Vector((1.0, -6.0, 3.2)); LW = Vector((0.3, 8.0, 0.2))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((0.0, 0.35, -0.05)) * (t - T_W0), LW, Vector((0.6, 1.0, 0.3))), T_W0, T_W1, 70.0, 24.0)
    return dict(lanes=[], kiosks=[], place="town_crack", light=light, data=data, rest=1, grips=("wheelbarrow",), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("he pushes the barrow of sandbags down the street", lambda: [o for o in meshes([bar]) if "wheel" not in o.name.split("barrow ")[-1] and "hub" not in o.name], 0.0, T_STOP, {"whole": False, "moves": True}),
                        ("a crack tears across the road in front of his wheel and yawns open, glowing", lambda: [tear] + lips, T_TORN, T_OPEN1 + 0.2, {"whole": False}),
                        ("lava wells up and pours over the road; the barrow tips in and burns", lambda: [flow], T_POUR, DUR, {"whole": False})])


# ====================================================================================================
# shot5.py
# ====================================================================================================
"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?"

The harbour quay at dawn: fishing boats at the quay, the town on the slope above it, the earth wall curving round
above the town, black lava spread up to the town's edge where three houses still burn. The lens is low on the quay. He
walks up the quay to his own house by the water carrying a lit lantern and hangs it on the hook of the post by his door;
it swings, glowing; across the dark town a few windows light up, one here, one there, only a handful; he turns to us
and spreads his hands wide: would you?"""

S5_HOOK = Vector((0.2, 1.1, 0.5))       # the hook's tip, on the post by his door (pointing -X, toward where he comes from)
S5_EDGE_X = -2.2                        # the quay's water edge (x)


S5_SLOPE = 0.45                         # the hill's rise per metre
S5_BASIN = (-4.6, -0.25, 2.5, 7.4)     # the boat basin cut into the quay (x0, x1, y0, y1): water between him and the town


def s5_water(x, y):
    """True where the harbour's water is: the basin in front of the town, and the open harbour off the quay's edge"""
    x0, x1, y0, y1 = S5_BASIN
    return (x0 - 30 < x < x1 and y0 < y < y1) or (x < S5_EDGE_X and y < y0)


def s5_slope_z(x, y):
    """the quay flat, the boat basin sunk in it, the town's slope rising behind it, the lava field on the right"""
    if s5_water(x, y): return -1.2
    z = 0.0
    if y > 4.8: z += S5_SLOPE * (min(y, 36.0) - 4.8)    # the town climbs the hill behind the harbour, row over row (steep: every row seen over the one below)
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 4.8 else 0)
    return z


def s5_lantern():
    """a REAL hurricane lantern (Poly Haven's Lantern_01), its glass glowing with the flame in it, hung by its top: the
    pivot at the top of its bail, the lantern below it"""
    root = K.empty("lantern", (0, 0, 0))
    S_ = 1.35
    lm = ph_model("Lantern_01", (0, 0, -0.29 * S_), scale=S_, name="lantern body", parent=root)
    glow = lw_emit("lantern glow", "#FFB050", 3.0)
    for c in lm.children_recursive:
        if "glass" in c.name.lower():
            c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = glow
    L = lw_point("lantern light", (0, 0, -0.16), 25.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.16)
    return root


def s5_lit_pane(house, k, t_on):
    """a window of a dark house that lights up at t_on (a pane in front of the dark one)"""
    p = house["windows"][k]
    lit = p.copy(); lit.data = p.data.copy(); bpy.context.collection.objects.link(lit)
    lit.name = p.name.replace("window pane", "window lit pane")
    lit.data.materials.clear(); lit.data.materials.append(lw_emit("window lit", "#FFC070", 2.5))
    lit.location.y -= 0.004
    lw_show([lit], t_on)
    return lit


def s5_boat(name, xy, yaw, hull, roof, seed=0):
    """one fishing boat afloat, built from its parts, facing +Y"""
    root = K.empty(name, (0, 0, 0))
    L_, B_ = 2.6, 1.05                                   # length, beam
    hm = ph_mat("container_side", scale=0.8, tint=hull, paint=True, rough=0.4, name=f"hull steel {hull}")
    stations = 12; ring = [(-1.0, 0.0), (-0.98, -0.22), (-0.8, -0.38), (-0.45, -0.48), (0.0, -0.5), (0.45, -0.48), (0.8, -0.38), (0.98, -0.22), (1.0, 0.0)]
    bm = LW_bmesh.new(); rows = []
    for i in range(stations + 1):
        u = i / stations; y = -L_ / 2 + L_ * u
        hw = B_ / 2 * (1.0 - max(0.0, (u - 0.55) / 0.45) ** 1.6) * (0.92 + 0.08 * math.sin(math.pi * min(u, 0.6) / 0.6)) + 0.01
        sheer = 0.02 + 0.16 * u ** 2.2; depth = 0.42 * (1.0 - 0.5 * max(0.0, u - 0.7) / 0.3)
        rows.append([bm.verts.new((px * hw, y, sheer + pz / 0.5 * depth)) for px, pz in ring])
    for i in range(stations):
        for j in range(len(ring) - 1):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    bm.faces.new(list(reversed(rows[0])))
    LW_bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + " hull"); bm.to_mesh(me); bm.free(); me.materials.append(hm)
    for p_ in me.polygons: p_.use_smooth = True
    h = lw_link(bpy.data.objects.new(name + " hull", me)); h.parent = root
    so = h.modifiers.new("t", 'SOLIDIFY'); so.thickness = 0.02
    band = K.mat("hull waterline red", "#7A1E16", rough=0.6)
    K.box(name + " boot top", (0, -0.1, -0.17), (B_ * 0.98, L_ * 0.8, 0.05), band, bev=0.02, parent=root)
    deck = ph_mat("black_painted_planks", scale=0.8, name="boat deck planks")
    K.box(name + " deck", (0, -0.15, 0.0), (B_ * 0.9, L_ * 0.78, 0.03), deck, bev=0.01, parent=root)
    white = ph_mat("corrugated_iron_02", scale=0.6, tint="#EDEBE4", paint=True, rough=0.45, name="wheelhouse white")
    glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    wy = -0.55
    K.box(name + " wheelhouse", (0, wy, 0.3), (0.66, 0.7, 0.58), white, bev=0.03, parent=root)
    K.box(name + " wheelhouse roof", (0, wy + 0.04, 0.62), (0.76, 0.84, 0.06), K.mat(f"wheelhouse roof {roof}", roof, rough=0.45), bev=0.015, parent=root)
    for wx in (-0.18, 0.18):
        K.box(name + " window", (wx, wy + 0.36, 0.43), (0.24, 0.02, 0.16), glass, bev=0.0, parent=root)
    for sx in (-1, 1):
        for wy_ in (-0.15, 0.15):
            K.box(name + " window", (sx * 0.335, wy + wy_, 0.43), (0.02, 0.22, 0.16), glass, bev=0.0, parent=root)
    steel = lw_metal("mast steel", "#8A8E92")
    K.cyl(name + " mast", (0, 0.35, 0.85), 0.025, 1.7, steel, v=10, parent=root)
    K.cyl(name + " crosstree", (0, 0.35, 1.45), 0.015, 0.6, steel, rot=(0, math.pi / 2, 0), v=8, parent=root)
    K.sph(name + " mast lamp", (0, 0.35, 1.72), 0.035, lw_emit("mast lamp", "#FFF1D0", 4.0), seg=10, ring=6, parent=root)
    K.cyl(name + " boom", (0, 0.75, 0.6), 0.015, 0.8, steel, rot=(math.radians(70), 0, 0), v=8, parent=root)
    for sx in (-1, 1):                                   # the stern gantry, an A-frame over the transom
        K.cyl(name + " gantry", (sx * 0.38, -L_ / 2 + 0.12, 0.42), 0.02, 0.8, steel, rot=(math.radians(-12), sx * math.radians(8), 0), v=8, parent=root)
    K.cyl(name + " gantry top", (0, -L_ / 2 + 0.04, 0.8), 0.02, 0.72, steel, rot=(0, math.pi / 2, 0), v=8, parent=root)
    rail = lw_metal("boat rail", "#D8DADC", rough=0.35)
    for sx in (-1, 1):                                   # the rails along her sides
        K.cyl(name + " rail", (sx * (B_ / 2 - 0.05), 0.15, 0.2), 0.008, L_ * 0.55, rail, rot=(math.pi / 2, 0, 0), v=6, parent=root)
        for j in range(4):
            K.cyl(name + " stanchion", (sx * (B_ / 2 - 0.05), -0.25 + 0.27 * j, 0.11), 0.008, 0.18, rail, v=6, parent=root)
    ph_model("lifebuoy", (0, wy + 0.37, 0.3), rot=(math.pi / 2, 0, 0), scale=0.3, name=name + " lifebuoy", parent=root)
    for j in range(3):                                   # old tyres over her side for fenders (REAL, Poly Haven)
        ph_model("old_tyre", (B_ / 2 + 0.04, -0.6 + 0.55 * j, -0.05), rot=(0, math.pi / 2, 0), scale=0.38, name=name + f" fender tyre {j}", parent=root)
    lw_local(root)
    root.location = (xy[0], xy[1], -0.45 + 0.22); root.rotation_euler = (0, 0, yaw)
    return root


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, and up the slope behind, the whole story in one frame (board after the fire test: "put
    the standing town and the earth wall in frame, so 'the wall saved the rest' is seen"): on the left the town
    standing, street over street, below the earth wall; the black lava field heaped up behind the wall; on the right,
    past the wall's end, the tongue of lava that got round it, its ridged glowing front run into the backs of three
    houses that burn from inside."""
    rnd = lw_random.Random(61)
    ground = ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock")          # REAL rock ground (Poly Haven), at a real size
    lw_grid("town slope", -26, 26, 1.2, 40, 208, 128, s5_slope_z, ground)          # the town's land, the basin sunk in it
    stone = ph_mat("concrete_wall_008", scale=1.5, tint="#8A8580", name="harbour stone")
    x0, x1, y0, y1 = S5_BASIN
    for k in range(12):                                    # the basin's stone walls: its town side climbs with the slope
        y = y0 + (y1 - y0) * (k + 0.5) / 12; top = s5_slope_z(x1 + 0.3, y)
        K.box("harbour basin wall", (x1 + 0.12, y, (top - 1.2) / 2), (0.25, (y1 - y0) / 12 + 0.02, top + 1.2), stone, bev=0.01)
    K.box("harbour basin wall", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.1, -0.6), (x1 - S5_EDGE_X + 0.2, 0.25, 1.24), stone, bev=0.01)
    top = s5_slope_z(x1 + 0.3, y1 + 0.3)
    K.box("harbour head wall", ((x0 - 30 + x1) / 2, y1 + 0.12, (top - 1.2) / 2), (x1 - x0 + 30, 0.25, top + 1.2), stone, bev=0.01)
    qc = ph_mat("concrete_wall_008", scale=2.0, tint="#B5B1AA", name="quay concrete")
    K.box("quay concrete", (6.0, -1.55, -0.128), (16.4, 7.9, 0.24), qc, bev=0.02)                  # the quay he walks: concrete right up to the basin
    K.box("quay concrete", ((x1 + 14.2) / 2, 3.6, -0.128), (14.2 - x1, 2.4, 0.24), qc, bev=0.02)    # and along the basin's side to the foot of the town
    for k in range(9):                                   # its expansion joints
        K.box("quay joint", (-1.0 + 1.6 * k, 0.4, 0.0), (0.02, 4.0, 0.005), K.mat("quay joint", "#3A3836", rough=0.9), bev=0.0)
    edge = lw_paint("quay edge paint", "#D9B32E", rough=0.6)
    K.box("quay edge", (S5_EDGE_X + 0.1, -2.0, 0.03), (0.2, 7.0, 0.06), edge, bev=0.01)
    K.box("quay edge", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.12, 0.03), (x1 - S5_EDGE_X, 0.2, 0.06), edge, bev=0.01)
    K.box("quay edge", (x1 + 0.1, (y0 + 4.8) / 2, 0.03), (0.2, 4.8 - y0, 0.06), edge, bev=0.01)
    iron = lw_metal("bollard iron", "#232527", rough=0.55)
    for k, (bx, by) in enumerate(((S5_EDGE_X + 0.35, y0 - 0.4), (-1.0, y0 - 0.4), (x1 + 0.4, 3.3), (x1 + 0.4, 4.4), (S5_EDGE_X + 0.35, -1.4))):     # cast-iron mooring bollards along the edge
        K.cyl("quay bollard", (bx, by, 0.09), 0.07, 0.18, iron, v=20)
        K.cyl("quay bollard cap", (bx, by, 0.2), 0.095, 0.05, iron, v=20)
        K.cyl("quay bollard foot", (bx, by, 0.015), 0.1, 0.03, iron, v=20)
    water = bpy.data.materials.new("harbour water"); water.use_nodes = True; wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (*K.lin("#1E3440"), 1); wb.inputs["Roughness"].default_value = 0.06
    wt = water.node_tree; nz = wt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; bp = wt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    wt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); wt.links.new(bp.outputs["Normal"], wb.inputs["Normal"])
    K.box("harbour water", (-14, 0, -0.45), (24, 60, 0.02), water, bev=0)
    # fishing boats moored in the basin (board: "white box stacks"): a lofted hull, sharp at the bow and full at the
    # stern, sheer rising forward, a painted band at the waterline; a planked deck with bulwarks; the wheelhouse aft
    # with windows all round and a coloured roof; a mast with its crosstree and lamps; a gantry at the stern; tyres
    # over the side for fenders; a real ring buoy on the wheelhouse
    for k, (x, y, yaw) in enumerate(((-1.0, 4.4, 0.0), (-1.9, 6.4, 0.05), (-2.9, 4.2, -0.04), (-3.9, 6.2, 0.08))):
        s5_boat(f"fishing boat {k}", (x, y), yaw, ("#2E5E8A", "#C33A2A", "#2E7A5A", "#1F3A5A")[k], ("#C33A2A", "#2E5E8A", "#E9E4D6", "#D9B32E")[k], seed=k)
    home = town_house("his town house", (5.6, 3.6, 0.0), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.3, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    iron = lw_rust("hook iron", "#3A3430")
    # the hook is on a TIMBER MOORING PILE at the quay's edge (board: "the white post reads as nothing"): a tarred
    # round pile, iron bands, a mooring rope coiled round its foot
    pile = lw_wood("pile timber", "#5A4A3A", scale=0.5)
    px_ = S5_HOOK.x + 0.17
    K.cyl("lantern post", (px_, S5_HOOK.y, 0.45), 0.085, 0.9, pile, v=20)
    K.cyl("lantern post cap", (px_, S5_HOOK.y, 0.91), 0.088, 0.03, iron, v=20)
    for bz in (0.25, 0.7):
        K.cyl("lantern post band", (px_, S5_HOOK.y, bz), 0.09, 0.035, iron, v=20)
    rope = lw_canvas("mooring rope", "#B79A62")
    for j in range(3):
        K.cyl("mooring rope", (px_, S5_HOOK.y, 0.04 + 0.035 * j), 0.125 + 0.012 * j, 0.03, rope, v=24)
    K.box("lantern hook arm", (S5_HOOK.x + 0.06, S5_HOOK.y, S5_HOOK.z + 0.05), (0.2, 0.025, 0.025), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x + 0.1, S5_HOOK.y, S5_HOOK.z - 0.02), (0.13, 0.018, 0.018), iron, bev=0.003).rotation_euler = (0, math.radians(-45), 0)
    K.cyl("lantern hook", (S5_HOOK.x - 0.035, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x - 0.025, S5_HOOK.y, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, x in enumerate((9.6, 13.8, 18.0)):            # his neighbours along the quay, off to the right
        quay.append(town_house(f"quay house {k}", (x, 3.9 + 0.2 * k, 0.0), yaw=0.0, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], d=2.8, seed=50 + k))
    asph = ph_mat("asphalt_02", scale=2.0, tint="#7A7A7A", name="town street")
    for ys in (8.2, 12.6, 16.2):                         # the town's streets, across the slope
        lw_grid(f"town street {ys}", -26, 12.0 if ys < 16 else -0.5, ys - 0.7, ys + 0.7, 120, 4, lambda x, y: s5_slope_z(x, y) + 0.03, asph)
    town = []
    rows = [(10.2, (-12.6, -8.4, -4.2), 0), (14.4, (-14.0, -9.8, -5.6, -1.4), 0), (18.0, (-15.0, -10.8, -6.6, -2.4), 1)]     # (the lens's line up the hill to the burning row is left open: a street and rubble)
    for y, xs, one in rows:                              # the town that STANDS: below the wall, untouched, street over street
        for x in xs:
            k = len(town); x += rnd.uniform(-0.3, 0.3); yy = y + rnd.uniform(-0.2, 0.2)
            town.append(town_house(f"town house up {k}", (x, yy, s5_slope_z(x, yy - 1.4) - 0.05), yaw=rnd.uniform(-0.08, 0.08),
                                   roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], storeys=1 if one else None, seed=30 + k))
    for k, (x, y) in enumerate(((-18.0, 10.6), (-22.0, 14.0), (-20.0, 6.4), (-18.4, 18.0))):        # more of the town off to the left, filling the hill
        town.append(town_house(f"town house up {len(town)}", (x, y, s5_slope_z(x, y - 1.4) - 0.05), yaw=0.05, roof=ROOFS[k + 2], wall=WALLS[k + 3], seed=80 + k))
    # THE WALL: across the hill above the town, the old lava heaped up behind it, and its right end, where the new
    # lava got round
    WY = 21.6
    wall = earth_wall("earth wall", [(x, WY + 0.004 * x * x) for x in range(-26, 1, 2)], h=4.4, crest=1.4, base=8.0, seed=14)
    wall["root"].location.z = s5_slope_z(-8.0, WY) - 0.5
    tilt = math.atan(S5_SLOPE)
    held = lava_mat("lava held", heat=0.35, scale=1.6, fresh=0.05)
    pool = lava("lava held behind the wall", [(-26, 25.2), (0.5, 24.0), (0.5, 36), (-26, 36)], z=0.0, thick=1.4, m=held, seed=4, lumpy=0.35)
    c = pool.location.copy(); pool.rotation_euler.x = tilt; pool.location.z = s5_slope_z(-8, c.y) - 0.3
    fresh = lava_mat("lava field fresh", heat=0.8, scale=1.6, fresh=0.2)        # black crust, light only in its cracks and seams
    out = [(-1.0, 20.2), (2.4, 19.9), (6.4, 20.3), (10.4, 20.8), (14.0, 20.4), (18.0, 21.0), (24.0, 22.0), (24.0, 36.0), (-0.5, 36.0), (-1.4, 26.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.9, m=fresh, seed=8, lumpy=0.4)
    c = flow.location.copy(); flow.rotation_euler.x = tilt; flow.location.z = s5_slope_z(8, c.y) - 0.2
    crust = lava_mat("lava front crust", heat=0.55, scale=7.0, fresh=0.15)
    for k in range(320):                                 # its FRONT: a ridge of broken black crust blocks, glowing in their cracks
        i = rnd.randrange(6); q = Vector(out[i]).lerp(Vector(out[i + 1]), rnd.random())
        q.y += rnd.uniform(-0.2, 1.2)
        rr = rnd.uniform(0.15, 0.5)
        lw_block("lava front block", (q.x, q.y, s5_slope_z(q.x, q.y) + 0.3 + rr * 0.4), rr, crust, rnd, squash=0.75)
    houses = list(town)
    for k, (x, y) in enumerate(((-0.6, 9.0), (4.2, 9.0), (8.6, 9.1), (-0.4, 13.4), (4.4, 13.4), (8.8, 13.5), (-0.2, 17.0))):     # REAL street lamps along the streets
        ph_model("street_lamp_01", (x, y, s5_slope_z(x, y)), rot=(0, 0, math.pi), scale=0.5, name=f"street lamp {k}")
    ph_model("fire_hydrant", (2.2, 8.9, s5_slope_z(2.2, 8.9)), rot=(0, 0, 0.3), scale=0.5, name="fire hydrant", only=("fire_hydrant", "fire_hydrant_cap_01"))
    for k, (x, y, r) in enumerate(((1.6, 11.0, 0.4), (6.8, 10.6, 2.0), (10.6, 12.0, 1.1), (3.2, 15.2, 2.6), (7.4, 15.6, 0.2), (11.4, 16.0, 1.7))):   # REAL mossy lava boulders on the open slope
        ph_model("rock_moss_set_02" if k % 2 else "boulder_01", (x, y, s5_slope_z(x, y) - 0.1), rot=(0, 0, r), scale=0.55 if k % 2 else 0.7, name=f"slope boulder {k}")
    for k, (x, y) in enumerate(((5.6, 11.6), (9.0, 14.6), (2.0, 14.8))):
        ph_model("old_tyre", (x, y, s5_slope_z(x, y) + 0.04), rot=(math.pi / 2, 0, 0.7 * k), scale=0.5, name=f"old tyre {k}")
    lava_rock("lava rubble", 1100, (-26, 26, 5.0, 24.0), s5_slope_z, seed=5, r=(0.05, 0.22), moss=0.45,
              avoid=lambda x, y: s5_water(x, y) or min(abs(y - 8.2), abs(y - 12.6), abs(y - 16.2)) < 0.85
              or any(abs(x - h_["root"].location.x) < 2.2 and abs(y - h_["root"].location.y) < 1.8 for h_ in houses))
    burning = []
    for k, (x, y) in enumerate(((0.8, 18.0), (5.0, 18.3), (9.2, 18.7))):     # at the lava's front, past the wall's end: three in a row across the frame, countable
        z = s5_slope_z(x, y - 1.3) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.12, 0.12), w=3.6, d=2.6, roof=ROOFS[(k * 2) % len(ROOFS)],
                        wall=WALLS[(k + 1) % len(WALLS)], storeys=(2, 1, 2)[k], seed=40 + k, burn=1.0)
        lw_house_fire(hs, seed=11 + k, t_end=DUR + 1.0)
        burning.append(hs)
    for gx in (2.0, 8.0, 14.0):
        lw_point("lava front glow", (gx, 20.0, s5_slope_z(gx, 20) + 1.2), 900.0, col=(1.0, 0.35, 0.1), r=2.0)

    def light():
        k = iceland_light(sun_elev=3, sun_az=-55, sun=1.6, sky=0.18, warm=(1.0, 0.62, 0.45), haze=1.6)      # first light: dim enough that a lit window reads
        ph_sky("qwantani_sunrise_puresky", strength=0.35, rot=math.radians(150))       # a REAL dawn sky (Poly Haven)
        return k
    return dict(light=light, home=home, town=town, burning=burning, quay=quay)


def shot5():
    """THE QUAY AT DAWN. Low on the quay. He carries the lit lantern up the quay to the post by his door and hangs it; it
    swings, glowing; a few windows light up across the town, one here, one there; he turns to us and spreads his hands:
    would you?"""
    T_WALK1 = 0.4 * DUR; T_HANG = 0.48 * DUR; T_LET = T_HANG + 0.25
    T_WIN = 0.62 * DUR; T_TURN = 0.8 * DUR; T_ASK = 0.86 * DUR
    W = lw_win
    P = place_harbour_dawn()
    light = P["light"]
    data = load_data()
    rnd = lw_random.Random(7)
    P0 = Vector((S5_HOOK.x - 0.9, S5_HOOK.y + 0.75, 0.0))                 # he comes down the quay toward us and across to the pile
    STAND = Vector((S5_HOOK.x - 0.2, S5_HOOK.y + 0.1, 0.0))               # facing +X, the hook in front of his near shoulder
    data.place(P0.x, P0.y, 50.0)
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.15, T_WALK1 - 0.15)
    # ---- his body: the walk up the quay, the lift to the hook, a step back, the turn to us, the spread hands
    sc.frame_set(F(T_WALK1 - 0.15)); bpy.context.view_layer.update()
    YAW_H = math.radians(90)
    Y_IN = data.arm.rotation_euler.z                       # the way he faces as his walk ends: he turns to the pile from there
    Y_IN += 2 * math.pi * round((YAW_H - Y_IN) / (2 * math.pi))
    for f in range(F(T_WALK1 - 0.15) + 1, NF + 1):
        t = (f - 1) / FPS
        p = STAND.copy()
        p.z += 0.03 * W(t, T_HANG - 0.3, 0.25) * (1 - W(t, T_LET + 0.2, 0.3))                 # up on his toes to the hook
        p.x -= 0.05 * W(t, T_LET + 0.5, 0.5); p.y -= 0.1 * W(t, T_LET + 0.8, 0.45)   # a step back from it, and one toward us
        p.y -= 0.08 * W(t, T_ASK + 0.3, 0.7); p.z += 0.035 * lw_kick(t - T_ASK - 0.35, 0.22)   # and at the ask, a step to us and a shrug
        yaw = Y_IN + (YAW_H - Y_IN) * W(t, T_WALK1 - 0.15, 0.6) - math.radians(30) * W(t, T_LET + 0.2, 1.0) - math.radians(45) * W(t, T_TURN - 0.45, 0.4)
        data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (-8 * W(t, T_HANG - 0.3, 0.3) * (1 - W(t, T_LET, 0.3)) + 6 * W(t, T_LET + 0.1, 0.3) * (1 - W(t, T_TURN, 0.3))
                                       - 6 * W(t, T_ASK, 0.3), 0, 0), 0, DUR + 0.4)
    sc.frame_set(F(T_HANG)); bpy.context.view_layer.update()
    near = sorted("LR", key=lambda s_: acts._shoulder(data, s_).y)               # near[0]: the hand toward the lens
    carry, other = near[0], near[1]
    # the lantern: in his near hand from the start, up onto the hook, then on its own, swinging
    lan = s5_lantern()
    CK = [(0.0, (0.08, 0.1, -0.08)), (T_WALK1 - 0.2, (0.09, 0.1, -0.07))]
    carry_fn = lw_hand(data, carry, CK)
    hook_at = lambda t: S5_HOOK + Vector((0.0, 0.0, 0.0))
    def hand_path(t):
        if t <= T_WALK1 - 0.2: return carry_fn(t)
        u = W(t, T_WALK1 - 0.2, T_HANG - T_WALK1 + 0.2)
        return carry_fn(T_WALK1 - 0.2).lerp(hook_at(t) + Vector((0, 0, 0.005)), u)
    # after the let-go: the lantern hand comes down slowly; his free hand waves up at the first window that lights,
    # comes down, then both spread wide to us
    AK = {carry: [(T_LET + 0.9, (0.07, 0.1, -0.07)), (T_ASK + 0.05, (0.07, 0.1, -0.08)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))],
          other: [(T_LET + 0.95, (0.06, 0.14, 0.03)), (T_LET + 1.2, (0.03, 0.16, 0.08)), (T_LET + 1.42, (0.03, 0.13, 0.09)), (T_LET + 1.64, (0.03, 0.16, 0.08)),
                  (T_ASK + 0.05, (0.08, 0.1, -0.06)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))]}
    down_fn = lw_hand(data, carry, AK[carry])
    def carry_path(t):                                       # ONE job for the lantern hand: carry, hang, then down slowly
        if t <= T_LET: return hand_path(t)
        return (hook_at(t) + Vector((0, 0, 0.005))).lerp(down_fn(t), W(t, T_LET, 1.1))
    data.reach(carry, carry_path, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    def swing(t):                                           # after the let-go: a damped swing about the hook
        s = t - T_LET
        return 0.0 if s <= 0 else math.radians(24) * math.exp(-s / 2.2) * math.sin(2 * math.pi * s / 0.9)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t <= T_LET:
            sc.frame_set(f); bpy.context.view_layer.update()
            lan.location = data.arm.matrix_world @ data.pb[f"hand.{carry}"].tail + Vector((0, 0, -0.02))
            lan.rotation_euler = (0, math.radians(10) * math.sin(2 * math.pi * t / 0.55) * (1 - W(t, T_WALK1 - 0.2, 0.3)), 0)
        else:
            lan.location = S5_HOOK; lan.rotation_euler = (0, swing(t), 0)
        lan.keyframe_insert("location", frame=f); lan.keyframe_insert("rotation_euler", frame=f)
    data.reach(other, lw_hand(data, other, AK[other]), AK[other][0][0], DUR + 0.3, lead=1.0, back=None, elbow_out=0.4)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((0.2, -2.4, 0.6))
    data.look_at(Vector((0.3, -2.4, 0.7)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)      # his face to us as he comes (board: glasses off his face in profile)
    data.look_at(S5_HOOK, T_WALK1 - 0.1, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(Vector((0.4, 9.0, 2.6)), T_LET + 0.2, max_yaw=8, max_pitch=30, blend=0.45)     # up the hill at the windows as he waves
    data.look_at(Vector((-0.8, 7.0, 2.0)), T_WIN + 0.12 * DUR, max_yaw=30, max_pitch=30, blend=0.45)
    data.look_at(LENS, T_TURN + 0.1, max_yaw=50, blend=0.45)
    data.expression("sad", 0.1, T_HANG - 0.1, blend=0.25)
    data.expression("determined", T_HANG, T_WIN, blend=0.2)
    data.expression("pleased", T_WIN + 0.1, T_ASK - 0.05, blend=0.25)
    data.expression("wry", T_ASK, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low on the quay, the town and its burning edge up the slope behind him
    CAM = Vector((0.05, -0.45, 0.8)); LOOK = Vector((1.0, 14.0, 2.5))      # low on the quay: him and the post low, the open slope, the three houses burning up the hill at the lava front, the town standing to the left
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=28.0, fstop=16.0)
    # framed through compose.py (board: "frame 1 cuts Data at the left edge"): the lens is SOLVED so his face sits where
    # it should at his first step and at the pile, and it trucks between the two as he walks
    C0, L0 = compose.frame_data(data, CAM + Vector((P0.x - STAND.x, 0, 0)), LOOK + Vector((P0.x - STAND.x, 0, 0)), 28.0, face_at=(0.5, 0.44), height=0.36, t=0.15)
    C1, L1 = compose.frame_data(data, CAM, LOOK, 28.0, face_at=(0.42, 0.44), height=0.36, t=T_WALK1)
    def cam_at(t):                                          # it trucks with him down the quay to the pile, then holds
        u = ease(min(1.0, max(0.0, (t - 0.15) / (T_WALK1 - 0.15))))
        return C0.lerp(C1, u) + Vector((0.0, 0.1, 0.0)) * ease(t / DUR), L0.lerp(L1, u), data.pos() + Vector((0, 0, 0.6))
    # CUT to the WIDE on his walk to his door (board round 2: "no harbour, no boats, no wall", "three burning houses
    # against many untouched ones"): high over the harbour water, the boats in the basin, him at his door on the quay,
    # the town on its hill, the three houses burning at the black lava's edge, the wall above, the handful of lights
    T_W0, T_W1 = 0.28 * DUR, T_HANG - 0.35          # on his walk up the quay, his face to this lens (KEYS: never his back)
    CW = Vector((3.5, -6.5, 8.5)); LW = Vector((0.5, 14.0, 5.0))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.12, 0.2, -0.05)) * (t - T_W0), LW, Vector((0.0, 14.0, 5.0))), T_W0, T_W1, 28.0, 20.0)
    # ---- the payoff: windows light up ACROSS THE TOWN, one here, one there (board: "a few windows, not one"): the
    # windows this lens sees at that moment, in houses spread over the frame, a beat apart
    from bpy_extras.object_utils import world_to_camera_view as _w2c
    sc.frame_set(F(T_WIN + 0.3)); bpy.context.view_layer.update()
    seen = []
    for hs in P["town"] + P["quay"]:
        for wi, p in enumerate(hs["windows"]):
            v = _w2c(sc, cam, p.matrix_world.translation)
            if 0.04 < v.x < 0.96 and 0.08 < v.y < 0.95 and v.z > 0:
                seen.append((v.x, v.y, hs, wi))
    rnd_w = lw_random.Random(5); rnd_w.shuffle(seen)
    pick, used = [], {}
    for vx, vy, hs, wi in seen:                          # spread: at most two in a house, none on top of another
        if used.get(id(hs), 0) >= 4 or any(abs(vx - a_) < 0.06 and abs(vy - b_) < 0.04 for a_, b_, _h, _w in pick): continue
        pick.append((vx, vy, hs, wi)); used[id(hs)] = used.get(id(hs), 0) + 1
        if len(pick) >= 8: break
    lit, lit_houses = [], []
    for k, (_x, _y, hs, wi) in enumerate(pick):
        lit.append(s5_lit_pane(hs, wi, T_WIN + (-0.06 + 0.04 * k) * DUR))
        if hs not in lit_houses: lit_houses.append(hs)
    print(f"SHOT5 windows lit across the town: {len(lit)} in {len(lit_houses)} houses", flush=True)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
