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
    bil = X.add(X.mul(wnoise(0.55, 5.0, 0.72, 0.4), 0.7), X.mul(wnoise(1.6, 4.0, 0.6, 0.7), 0.45))     # big billows with smaller curls on them
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
        m.cycles.volume_step_rate = 3.5                   # a soft gas needs no fine steps: a third of the render time
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
    add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = (0.55, 0.55, 0.55)   # board round 4: "a uniform tile": plates warped into every shape
    nt.links.new(warp.outputs["Color"], add.inputs[0]); nt.links.new(mp.outputs["Vector"], add.inputs[2])
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs["Scale"].default_value = scale * 0.6
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
    wr.inputs["To Min"].default_value = 0.004 + 0.03 * fresh; wr.inputs["To Max"].default_value = 0.13 + 0.14 * fresh
    nt.links.new(wid.outputs["Fac"], wr.inputs["Value"]); nt.links.new(wr.outputs["Result"], crack.inputs["From Max"])
    vo2 = nt.nodes.new("ShaderNodeTexVoronoi"); vo2.feature = 'DISTANCE_TO_EDGE'; vo2.inputs["Scale"].default_value = scale * 2.9
    vo2.inputs["Randomness"].default_value = 1.0; nt.links.new(add.outputs["Vector"], vo2.inputs["Vector"])
    hair = nt.nodes.new("ShaderNodeMapRange"); hair.inputs["From Min"].default_value = 0.0; hair.inputs["From Max"].default_value = 0.025
    hair.inputs["To Min"].default_value = 0.22; hair.inputs["To Max"].default_value = 0.0
    nt.links.new(vo2.outputs["Distance"], hair.inputs["Value"])
    hmask = nt.nodes.new("ShaderNodeMath"); hmask.operation = 'MULTIPLY'; nt.links.new(hair.outputs["Result"], hmask.inputs[0])
    nt.links.new(wid.outputs["Fac"], hmask.inputs[1])
    crk0 = nt.nodes.new("ShaderNodeMath"); crk0.operation = 'MAXIMUM'
    nt.links.new(crack.outputs["Result"], crk0.inputs[0]); nt.links.new(hmask.outputs[0], crk0.inputs[1])
    # board B1 (2026-11-25, three shots): "an even net of glowing cells ... a game texture". Real crust is mostly BLACK:
    # the seams glow only where the flow under them is still moving, in patches, and are dead black lines elsewhere
    actn = nt.nodes.new("ShaderNodeTexNoise"); actn.inputs["Scale"].default_value = scale * 0.2; actn.inputs["Detail"].default_value = 2
    nt.links.new(mp.outputs["Vector"], actn.inputs["Vector"])
    act = nt.nodes.new("ShaderNodeMapRange"); act.inputs["From Min"].default_value = 0.47 - 0.3 * fresh; act.inputs["From Max"].default_value = 0.6 - 0.3 * fresh
    nt.links.new(actn.outputs["Fac"], act.inputs["Value"])
    rimn = nt.nodes.new("ShaderNodeAttribute"); rimn.attribute_name = "hot"            # lava() paints its moving EDGE hot: the seams there are open and bright
    act2 = nt.nodes.new("ShaderNodeMath"); act2.operation = 'MAXIMUM'
    nt.links.new(act.outputs["Result"], act2.inputs[0]); nt.links.new(rimn.outputs["Fac"], act2.inputs[1])
    crk = nt.nodes.new("ShaderNodeMath"); crk.operation = 'MULTIPLY'
    nt.links.new(crk0.outputs[0], crk.inputs[0]); nt.links.new(act2.outputs[0], crk.inputs[1])
    big = nt.nodes.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = scale * 0.35; nt.links.new(mp.outputs["Vector"], big.inputs["Vector"])
    hot = nt.nodes.new("ShaderNodeMapRange"); hot.inputs["From Min"].default_value = 0.5 - 0.15 * fresh; hot.inputs["From Max"].default_value = 0.75 - 0.1 * fresh
    hot.inputs["To Max"].default_value = 0.85 * fresh
    nt.links.new(big.outputs["Fac"], hot.inputs["Value"])
    glowf = nt.nodes.new("ShaderNodeMath"); glowf.operation = 'MAXIMUM'
    nt.links.new(crk.outputs[0], glowf.inputs[0]); nt.links.new(hot.outputs["Result"], glowf.inputs[1])
    crust = nt.nodes.new("ShaderNodeTexNoise"); crust.inputs["Scale"].default_value = scale * 6; crust.inputs["Detail"].default_value = 8
    nt.links.new(add.outputs["Vector"], crust.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (*K.lin("#0B0A09"), 1); cr.color_ramp.elements[1].color = (*K.lin("#3A3532"), 1)
    nt.links.new(crust.outputs["Fac"], cr.inputs["Fac"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*K.lin("#B02500"), 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (*K.lin("#FFA020"), 1)
    e = ramp.color_ramp.elements.new(0.5); e.color = (*K.lin(glow), 1)
    nt.links.new(glowf.outputs[0], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB"); nt.links.new(glowf.outputs[0], mix.inputs["Fac"])
    crust_col = cr.outputs["Color"]; rock_nor = None
    try:                                                   # the crust is REAL ROCK (Poly Haven), near black, under the procedural break-up
        d_ = ph_path("burned_ground_01", "textures")
        def rimg(kind, data=True):
            f_ = LW_os.path.join(d_, f"burned_ground_01_{kind}_1k.jpg")
            if not LW_os.path.exists(f_): return None
            t_ = nt.nodes.new("ShaderNodeTexImage"); t_.image = bpy.data.images.load(f_, check_existing=True); t_.projection = 'BOX'; t_.projection_blend = 0.25
            if data: t_.image.colorspace_settings.name = 'Non-Color'
            rm_ = nt.nodes.new("ShaderNodeMapping"); rm_.inputs["Scale"].default_value = (scale * 0.22,) * 3
            nt.links.new(add.outputs["Vector"], rm_.inputs["Vector"]); nt.links.new(rm_.outputs["Vector"], t_.inputs["Vector"]); return t_
        rd = rimg("diff", False)
        if rd:
            mxr = nt.nodes.new("ShaderNodeMix"); mxr.data_type = 'RGBA'; mxr.blend_type = 'MULTIPLY'; mxr.inputs[0].default_value = 1.0
            nt.links.new(rd.outputs["Color"], mxr.inputs[6]); nt.links.new(cr.outputs["Color"], mxr.inputs[7])
            gain = nt.nodes.new("ShaderNodeMix"); gain.data_type = 'RGBA'; gain.blend_type = 'ADD'; gain.inputs[0].default_value = 1.0
            nt.links.new(mxr.outputs[2], gain.inputs[6]); nt.links.new(mxr.outputs[2], gain.inputs[7]); crust_col = gain.outputs[2]
        rock_nor = rimg("nor_gl")
    except FileNotFoundError:
        pass
    nt.links.new(crust_col, mix.inputs["Color1"]); mix.inputs["Color2"].default_value = (*K.lin("#2A0600"), 1)   # the molten part is
    # LIGHT, not paint: a sunlit orange base under its own glow washed every lava in daylight to salmon pink
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bs.inputs["Emission Color"])
    es = nt.nodes.new("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "lava heat"; es.inputs[1].default_value = 1.1 * heat   # brighter than this the view transform bleaches it to salmon
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
    nt.links.new(glowf.outputs[0], pw.inputs[0]); nt.links.new(pw.outputs[0], es.inputs[0])
    nt.links.new(es.outputs[0], bs.inputs["Emission Strength"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 1.0; bp.inputs["Distance"].default_value = 0.05
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(crack.outputs["Result"], inv.inputs[1])
    hb = nt.nodes.new("ShaderNodeMath"); hb.operation = 'MULTIPLY_ADD'; hb.inputs[2].default_value = 0.0
    nt.links.new(inv.outputs[0], hb.inputs[0]); nt.links.new(crust.outputs["Fac"], hb.inputs[1])
    nt.links.new(hb.outputs[0], bp.inputs["Height"])
    if rock_nor:
        nmr = nt.nodes.new("ShaderNodeNormalMap"); nmr.inputs["Strength"].default_value = 1.4
        nt.links.new(rock_nor.outputs["Color"], nmr.inputs["Color"]); nt.links.new(nmr.outputs["Normal"], bp.inputs["Normal"])
    nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
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
    hot = me.attributes.new("hot", 'FLOAT', 'POINT')         # its moving edge is the hot part: the rim ring 1, falling off inward
    for v in me.vertices:
        ring = min(rings, v.index // nb); s_ = 1.0 - ring / rings
        hot.data[v.index].value = s_ ** 2.5
    o = lw_link(bpy.data.objects.new(name, me)); o.location = (cx, cy, 0)
    sd = o.modifiers.new("sub", 'SUBSURF'); sd.levels = 1; sd.render_levels = 3
    tx = bpy.data.textures.get("lava crust break") or bpy.data.textures.new("lava crust break", 'VORONOI')   # broken crust is ROUGH GEOMETRY, not a smooth blob with a picture on it
    tx.noise_scale = 0.22; tx.distance_metric = 'DISTANCE'
    dm = o.modifiers.new("crust", 'DISPLACE'); dm.texture = tx; dm.texture_coords = 'LOCAL'; dm.strength = 0.5 * max(0.06, lumpy); dm.mid_level = 0.35
    return o


# ---------------------------------------------------------------- the earth wall
def earth_wall(name, path, h=2.6, crest=0.9, base=5.0, seed=3, n=None, clear=None):
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
    try: me.materials.append(ph_mat("rock_face_01", scale=1.8, tint="#4A4642", name="wall heaped rock", rough=0.95, bump=1.6))   # REAL rock (Poly Haven), not a noise
    except FileNotFoundError: me.materials.append(m)
    body = lw_link(bpy.data.objects.new(name + " body", me)); body.parent = root
    # ONE wall for every beat (coordinator, 2026-11-25: "the crest is a smooth flat asphalt-like band and the wall has no
    # face"): a heaped berm. Its top is loose crushed rock and stones, its shoulders are lined with boulders
    for k in range(int(len(pts) * 26)):
        i = rnd.randrange(len(pts) - 1); u = rnd.random()
        p = pts[i].lerp(pts[i + 1], u); tg = (pts[i + 1] - pts[i]).normalized(); nrm = Vector((-tg.y, tg.x, 0))
        off = rnd.uniform(-crest / 2, crest / 2); q = p + nrm * off
        if clear and clear(q.x, q.y): continue
        edge = abs(off) > crest / 2 - 0.18
        r = rnd.uniform(0.07, 0.17) if edge else rnd.uniform(0.02, 0.06)
        b = lw_block(name + " crest stone", (q.x, q.y, h + r * 0.4), r, m, rnd, squash=0.7); b.parent = root
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


def ash_plume(base, w, h, S=6.0, dens=5.0, seed=0.0, lean=(0.04, 0.03), col=(0.075, 0.07, 0.068), rise=0.5, t_end=None, name="ash plume"):
    """AN ERUPTION'S ASH COLUMN: the kit's smoke column built at a size the kit's billows were made for (w/S by h/S)
    and scaled up S times about its foot, so its billows scale with it. Built at full size, the kit's noise is a few
    metres across on a column sixty metres high, and the column renders as a smooth hard-edged cone (lava shot 2's
    sheet r2l: "hard dark inverted cones hanging in the sky"). dens is the optical depth a kit-sized column has: the
    shader's density is divided by S, since every ray through it is S times longer."""
    b = Vector(base)
    o = FX.smoke_column(base=tuple(b), w=w / S, h=h / S, lean=lean, col=col, dens=dens / S, seed=seed, rise=rise, t_end=t_end, name=name)["volume"]
    o.location = b + (o.location - b) * S; o.scale = (S, S, S)
    return o


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
"""BEAT 1, THE HOOK: "A volcano keeps erupting right beside one Icelandic town, and everyone had to run."

THE TOWN, AND IT ERUPTS (coordinator, 2026-11-27, after the audit of every recorded verdict: the shots that passed have
the WORLD doing the event while Data reacts, one camera, two or three props). One lens, low in Grindavik's main street,
looking up it past him to the roofs and the ridge over them. Behind the roofs the eruption comes and grows still by
still: nothing (still 1), an orange glow along the ridge (still 2), a lava fountain bursting up over the roofs (still
3), the fountain under a towering black ash plume (still 4). Data, in the foreground at the left, three-quarter to us,
looks at us, turns his head at the glow, flinches at the fountain, and on still 4 runs at the lens, out of the street."""

S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX = 1.6                            # the fissure's middle (x)
S1_HOME_BASE = 0.05
S1_P0 = (0.15, -2.6)                   # where he stands: in the street, centred on the lens (coordinator, r1za: margin all round)
S1_CAM = (0.35, -4.2, 0.42)            # the one lens, low in the street


def s1_ground_z(x, y):
    """the street flat, the land round the town rolling, and the ridge rising behind it to the fissure"""
    z = -0.07 if abs(x) < 1.1 else 0.0                    # (the road's own deck lies in this shallow bed: the kit's road, never the rock showing through it)
    if abs(x) > 2.4: z += 0.15 * lw_fbm(x * 0.3, y * 0.3, 3) + 0.03 * (abs(x) - 2.4)
    r = max(0.0, (y - 9.0) / 6.0)
    z += 8.0 * (r * r * (3 - 2 * r) if r < 1 else 1.0) + (0.5 * lw_fbm(x * 0.15, y * 0.2, 7) if y > 8.5 else 0.0)
    if y > S1_RIDGE_Y: z -= 0.6 * min(1.0, (y - S1_RIDGE_Y) / 2.0)
    return z


def place_grindavik_street():
    """GRINDAVIK'S MAIN STREET: the asphalt street with its kerbs running away from the lens up to the ridge, the low
    coloured-roof houses down both sides and one across its end, the old lava field and moss round the town, the ridge
    above it where the fissure opens (its glowing slot built here, hidden until the eruption comes), far blue
    mountains. Nothing else in the street: no cars, flags, poles or trucks (coordinator: two or three props)."""
    rnd = lw_random.Random(5)
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, lw_noise("moss hill ground", "#1E2C15", "#4A6430", scale=1.6, rough=1.0, bump=0.5, detail=12, lo=0.3, hi=0.75))     # (r1w EMPTY 34%: the moss read as one smooth sheet joining sky to street: a tighter, higher-contrast moss)     # (coordinator, p1c: the hill read beige: green moss, darker)
    # (coordinator, p1c: the kit's scanned asphalt read as a CRACKED street before anything happened, stealing shot 4's
    # crack: an intact grey deck, its centre line painted fresh)
    asph = lw_noise("street asphalt", "#28292C", "#4E5054", scale=40.0, rough=0.85, bump=0.35, detail=12, lo=0.38, hi=0.62)     # (r1za pre-flight: "blurry noise": a fine aggregate grain)     # (r1y EMPTY: the near street still one smooth plane at phone size: a coarse aggregate grain)     # (r1w EMPTY: worn patches, still intact)
    K.box("street road", (0, 2.5, -0.035), (2.3, 20, 0.07), asph, bev=0.0)
    paint = K.mat("street line paint", "#E6E2D6", rough=0.6)
    y_ = -7.2
    while y_ < 12.0:
        K.box("street road line", (0, y_ + 0.5, 0.0015), (0.07, 1.0, 0.004), paint, bev=0.0); y_ += 2.2
    for sx in (-1, 1):                                     # (r1x EMPTY 38%: the near street read as one smooth grey plane) its painted edge lines
        K.box("street road edge line", (sx * 0.98, 2.5, 0.0015), (0.06, 20, 0.004), paint, bev=0.0)
    iron = lw_noise("street cast iron", "#232325", "#45474A", scale=30.0, rough=0.6, bump=0.6)
    K.cyl("street manhole cover", (0.9, -3.1, 0.004), 0.32, 0.012, iron, v=40, bev=0.003)     # the near street's own furniture: a manhole cover by the lens
    for gy in (-3.3, -0.4, 2.6):                           # and the drain grates along the kerbs
        for sx in (-1, 1):
            K.box("street drain grate", (sx * 1.0, gy, 0.003), (0.22, 0.45, 0.01), iron, bev=0.0)
    for k in range(7):                                     # and the zebra crossing just behind him
        K.box("street crossing stripe", (-0.84 + 0.28 * k, -1.35, 0.0016), (0.15, 0.9, 0.004), paint, bev=0.0)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        K.box("kerb", (sx * 1.15, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 1.45, 2.5, 0.035), (0.5, 20, 0.07), ph_mat("concrete_wall_008", scale=1.6, tint="#A8A49C", name="pavement"), bev=0.005)
    houses = []
    for sx in (-1, 1):
        y = -7.2 if sx < 0 else -6.6
        k = 0
        while y < 9.5:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)
            hs = town_house(f"town house {sx}_{k}", (sx * (1.65 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d, storeys=1,
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A")[(k + (sx > 0)) % 4], wall=("#B44A3C", "#E9D9A2", "#BFD3DD", "#F1EEE6", "#7E9A86")[(k + 2 * (sx > 0)) % 5], base=0.3, seed=k)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    px, py = S1_P0
    # (coordinator, p1c: no cinders on the street: nothing has happened yet)
    lava_rock("lava field rock", 60, (-14, 14, -6, 8), s1_ground_z, seed=3, r=(0.04, 0.12), moss=0.6, avoid=lambda x, y: abs(x) < 5.2)
    lava_rock("ridge slope stone", 260, (-12, 14, 8.5, 15.0), s1_ground_z, seed=12, r=(0.05, 0.16), moss=0.5)     # (r1w EMPTY: the slope needs its rocks big enough to read at phone size)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a torn glowing slot along the ridge top (lava, never neon), hidden until the eruption comes
    fl = lava_mat("fissure lava", heat=2.0, scale=3.0, fresh=1.0)
    slot = []
    for k in range(14):
        x = S1_FX - 6.0 + 12.0 * k / 13; w_ = 0.45 + 0.25 * math.sin(1.7 * k)
        o = K.box("fissure glow", (x, S1_RIDGE_Y + 0.12 * math.sin(2.3 * k), s1_ground_z(x, S1_RIDGE_Y) + 0.12), (0.95, w_ * 1.6, 0.3), fl, bev=0.05)     # (p1a: sunk in the ridge, the glow never showed)
        o.rotation_euler = (0, 0, 0.15 * math.sin(3.1 * k)); slot.append(o)
    fz = s1_ground_z(S1_FX, S1_RIDGE_Y)
    # a house across the end of the street, under the ridge: its red tin roof slopes toward the lens
    town_house("town house at the street's end", (1.3, 10.4, s1_ground_z(1.3, 9.0)), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.5, roof="#B8352B", wall="#E9D9A2", seed=3)
    bpy.context.view_layer.update()
    for o in bpy.data.objects:                             # (the near houses' door steps stood in the frame's corner as bare pale blocks: cut)
        if o.name.endswith(" step") or " step." in o.name:
            c = o.matrix_world.translation
            if -4.5 < c.y < 3.5: o.hide_render = True; o.hide_viewport = True
    def light():
        k = iceland_light(sun_elev=26, sun_az=-35, sun=3.0, sky=0.4, haze=0.8)           # the world's one bright day (the reset, 2026-11-25: no dusk)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(70))   # (r1v EMPTY 25%: clouds over the street) the same REAL sky as the wall's beats (Poly Haven)
        return k
    return dict(light=light, slot=slot, houses=houses, fz=fz)


def shot1():
    """THE TOWN, AND IT ERUPTS. See the module's head."""
    W = lw_win
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    T_GLOW = TS[0] + 0.3                                         # the smoking ridge starts to glow; the cars' lamps come on
    T_BURST = TS[2] - 0.55                                       # the fountain erupts out of it (still 3: he recoils from it)
    T_PLUME = TS[2] - 0.3                                        # the ash plume climbs over it
    T_CARS = TS[1] + 0.15                                        # the two parked cars pull out and speed out of town, past him
    T_TURN = TS[2] + 0.35                                        # he half-turns toward the lens side, about to follow them
    P = place_grindavik_street()
    light = P["light"]
    FZ = P["fz"]
    # ---- still 1: thin smoke already rising off the ridge (coordinator, r1za pre-flight: the eruption has a visible start)
    smoke = [lw_steam(f"ridge smoke {k}", (S1_FX + dx, S1_RIDGE_Y + 0.3, s1_ground_z(S1_FX + dx, S1_RIDGE_Y) - 0.1), w=1.2, h=7.0,
                      keys=[(0.0, 0.45), (T_GLOW, 0.6), (T_BURST, 0.8)], t_end=DUR + 1.0, seed=1.3 + k, col=(0.62, 0.62, 0.64), dens=2.5, lean=(0.04, 0.02))
             for k, dx in enumerate((-3.5, 0.5, 4.0))]
    # ---- the eruption, growing still by still: the slot glows, the fountain erupts, the plume fills the sky
    for o in P["slot"]:
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=F(T_GLOW))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_GLOW) + 1)
    # (coordinator, after shot 2's r2e pre-flight: one grade in all four stills: no lamp lights the town; the glow is the
    # lava's own, the slot and the fountain)
    # (coordinator, r1ze: the fountain twice as tall, near the top margin but whole, the densest version: a wide base, a
    # bright core, and two more columns layered round it in depth so it is never one flame card)
    fountain = lw_fire_column("lava fountain", (S1_FX, S1_RIDGE_Y, FZ - 0.3), w=6.0, h_fire=20.0, h_smoke=5.0,
                              lean=(0.03, 0.06), t_end=DUR + 1.0, seed=2.3, fire=10.0, smoke_d=3.0, rise=5.0, spread=0.35, flame_d=5.0,
                              keys=[(T_BURST - 0.05, 0.0), (T_BURST + 0.4, 0.75), (TS[2], 1.0)], grow=True)
    flanks = [lw_fire_column(f"lava fountain flank {k}", (S1_FX + dx, S1_RIDGE_Y + dy, s1_ground_z(S1_FX + dx, S1_RIDGE_Y) - 0.3), w=3.2, h_fire=h_, h_smoke=3.0,
                             lean=(0.03 * (k * 2 - 1), 0.05), t_end=DUR + 1.0, seed=5.7 + 3.1 * k, fire=8.0, smoke_d=3.0, rise=4.5, spread=0.3, flame_d=4.5,
                             keys=[(T_BURST, 0.0), (T_BURST + 0.45, 0.7), (TS[2], 1.0)], grow=True)
              for k, (dx, dy, h_) in enumerate(((-2.6, 1.2, 12.0), (2.4, -0.8, 14.0)))]
    PX, PY = S1_FX - 1.0, S1_RIDGE_Y + 2.5; PZ = s1_ground_z(PX, PY)
    plumes, base0 = [], []
    for k, (dx, w_, h_, dy) in enumerate(((0.0, 13.0, 64.0, 0.0), (-5.5, 9.0, 44.0, 1.5), (5.0, 9.5, 50.0, 1.0))):     # (coordinator, p1c: towering out of the top of the frame by still 4)
        o = ash_plume((PX + dx, PY + dy, PZ - 0.5), w=w_, h=h_, S=8.0, dens=20.0, lean=(-0.02 + 0.02 * k, 0.03), col=(0.05, 0.047, 0.045),
                      seed=4.1 + 2.7 * k, t_end=DUR + 1.0, name=f"eruption plume {k}")
        plumes.append(o); base0.append((Vector((PX + dx, PY + dy, PZ - 0.5)), o.location.copy(), o.scale.x))
    for o, (b, l0, s0) in zip(plumes, base0):
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=F(T_PLUME))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_PLUME) + 1)
        for f in range(F(T_PLUME), NF + 8, 2):
            t = (f - 1) / FPS
            g = max(0.08, 0.08 + 0.92 * W(t, T_PLUME, TS[3] - T_PLUME))          # (a volume scaled near zero crashes Cycles: never under 0.08)
            o.scale = (s0 * g,) * 3; o.location = b + (l0 - b) * g
            o.keyframe_insert("scale", frame=f); o.keyframe_insert("location", frame=f)
    # ---- the town flees (coordinator, r1ze: the WORLD does the fleeing): two cars parked at the kerbs up the street; their
    # lamps come on at the glow; they pull out into the street and speed down it toward us, past him on either side, dust
    # behind; on still 4 both are whole in the frame at mid-street, nearer than on still 3. Smooth from still 1 to 4.
    cars, dust = [], []
    for k, (x0, x1, y0, y4, col) in enumerate(((0.65, 0.55, 9.0, 1.6, "#2F5E8C"), (-0.65, -0.55, 7.4, 0.6, "#B8352B"))):
        c = FX.car(name=f"getaway car {k}", loc=(x0, y0, 0.0), yaw=0.0, kind="hatch", col=col, lights=True, seed=4 + k, dirt=0.4, power=30.0)
        t0 = T_CARS + 0.25 * k; T = TS[3] - t0; ra = 0.6
        v = (y0 - y4) / (T - ra / 2)
        def cy(t, y0=y0, t0=t0, v=v, ra=ra):
            u = max(0.0, t - t0)
            return y0 - (v * u * u / (2 * ra) if u < ra else v * (ra / 2 + (u - ra)))
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            u = max(0.0, t - t0); pull = W(t, t0, 0.8)
            c["root"].location = (x0 + (x1 - x0) * pull, cy(t), 0.0)
            c["root"].rotation_euler = (0.0, 0.0, -0.25 * (x1 - x0) / abs(x1 - x0) * math.sin(math.pi * min(1.0, u / 0.8)))     # it noses out from the kerb and straightens
            c["root"].keyframe_insert("location", frame=f); c["root"].keyframe_insert("rotation_euler", frame=f)
        for L_ in c["lights"]:                                   # its lamps: off while it is parked, on at the glow
            L_.data.keyframe_insert("energy", frame=F(T_GLOW) + 3); e = L_.data.energy
            L_.data.energy = 0.0; L_.data.keyframe_insert("energy", frame=1); L_.data.keyframe_insert("energy", frame=F(T_GLOW)); L_.data.energy = e
        for kk, yd in enumerate((y0 - 1.4, y0 - 4.0)):         # its dust: off the street where its tail has passed
            tk = t0
            while cy(tk) > yd - 1.2 and tk < DUR + 1.0: tk += 1.0 / FPS
            dust.append(lw_steam(f"car dust {k}_{kk}", (x1, yd, 0.0), w=1.0, h=1.0, keys=[(tk - 0.05, 0.0), (tk + 0.25, 0.8), (tk + 1.5, 0.5)],
                                 t_end=DUR + 1.0, seed=7.1 + 2 * k + kk, col=(0.58, 0.54, 0.47), dens=2.5, lean=(0.0, 0.05)))
        cars.append(c)
    for kind in ("head", "tail"):                              # the lamp lenses light with the lamps
        m = bpy.data.materials.get(f"fx lens {kind} on")
        if m:
            bs = m.node_tree.nodes["Principled BSDF"]; si = bs.inputs["Emission Strength"]; e = si.default_value
            si.keyframe_insert("default_value", frame=F(T_GLOW) + 3)
            si.default_value = 0.0; si.keyframe_insert("default_value", frame=1); si.keyframe_insert("default_value", frame=F(T_GLOW)); si.default_value = e
    # ---- him: centred in the street (coordinator, r1za: centred with margin in every still). No run, no point: he
    # stands calm facing us, turns his head and shoulders to the glow, recoils from the fountain (leaning back, both arms
    # thrown up beside his head, mouth open), and holding the recoil half-turns to the lens side as if to follow the cars.
    data = load_data()
    CAM0 = Vector(S1_CAM); D = Vector((-0.12, 1.0, 0.1)).normalized(); LOOK0 = CAM0 + D * 5.0      # (r1ze: tilted up so the fountain stands whole in the frame)
    X0, Y0 = S1_P0; Z0 = 0.0
    LENS = yaw_of(CAM0.x - X0, CAM0.y - Y0)
    YAW = LENS + math.radians(10)                              # 1 facing us
    data.place(X0, Y0, math.degrees(YAW))
    kit = hard_hat(data)
    TO = Vector((CAM0.x - X0, CAM0.y - Y0, 0)).normalized()     # toward the lens
    SIDE = Vector((-TO.y, TO.x, 0))
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        p = (Vector((X0, Y0, Z0)) + SIDE * (0.05 * W(t, 0.1, 0.35) - 0.1 * W(t, T_GLOW + 0.15, 0.45))
             + TO * (0.16 * W(t, T_BURST + 0.08, 0.3) + 0.1 * W(t, T_TURN + 0.25, 0.45)))     # a step to the glow; the recoil's step back; a step toward the lens side
        data._kobj(t, loc=tuple(p), rot=YAW + math.radians(40) * W(t, T_GLOW, 0.6) - math.radians(10) * W(t, T_BURST + 0.08, 0.3)
                   - math.radians(55) * W(t, T_TURN, 0.6))
        data._plant_feet_here(t, lift=(Z0, Z0))
    lw_layer(data, "spine", lambda t: (-4 * W(t, T_GLOW + 0.2, 0.5) - 22 * W(t, T_BURST + 0.08, 0.3) + 8 * W(t, T_TURN + 0.2, 0.5), 0, 0), 0, DUR + 0.4)
    lw_layer(data, "chest", lambda t: (-10 * W(t, T_BURST + 0.08, 0.3), 0, 0), 0, DUR + 0.4)
    RIDGE = Vector((S1_FX, S1_RIDGE_Y, FZ + 3.0))
    data.look_at(CAM0 + Vector((0, 0, 0.1)), 0.0, max_yaw=55, max_pitch=20, blend=0.0)                 # 1 at us, calm
    data.look_at(RIDGE, T_GLOW + 0.1, max_yaw=30, max_pitch=25, blend=0.35)                             # 2 round at the glow (FACE)
    data.look_at(RIDGE + Vector((0, 0, 4.0)), 1.9, max_yaw=30, max_pitch=30, blend=0.4)
    data.look_at(RIDGE + Vector((0, 0, 12.0)), T_BURST + 0.05, max_yaw=25, max_pitch=40, blend=0.15)    # 3 up at the fountain as it erupts
    data.look_at(RIDGE + Vector((0, 0, 10.0)), T_TURN + 0.3, max_yaw=55, max_pitch=30, blend=0.4)       # 4 still on it as he turns away
    data.expression("determined", 0.0, T_GLOW, blend=0.15)
    data.expression("surprised", T_GLOW, T_BURST, blend=0.15)
    data.expression("alarmed", T_BURST, DUR + 1.0, blend=0.1)
    sides = sorted("LR", key=lambda s_: -acts._shoulder(data, s_).x)
    LOW = lambda sg: ((-4, 0, sg * 5), (-22, 0, 0), (0, 0, 0))                    # (r2e pre-flight 'talking with his hands out': his arms hang)
    DOWN = lambda sg: ((-8, 0, sg * 8), (-28, 0, 0), (-4, 0, 0))                  # 2 still down, a little tense
    THROWN = lambda sg: ((-82, 0, -sg * 24), (-44, 0, -sg * 22), (-10, sg * -12, -sg * 15))     # 3 both arms thrown up beside his head (shot 3's UP, higher)
    HELD = lambda sg: ((-64, 0, -sg * 20), (-50, 0, -sg * 20), (-10, sg * -12, -sg * 12))      # 4 still up as he turns
    keys = [0.0, 0.4, T_GLOW + 0.2, 1.4, T_BURST + 0.05, T_BURST + 0.4, TS[2] + 0.1, T_TURN + 0.3, DUR + 0.5]
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = [LOW, LOW, DOWN, DOWN, THROWN, THROWN, THROWN, HELD, HELD]
        for tk, pose in zip(keys, seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    data.finish()
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=28.0, fstop=11.0)
    print("S1 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()),
          "stills", [round(t, 2) for t in TS], "glow", round(T_GLOW, 2), "burst", round(T_BURST, 2), "turn", round(T_TURN, 2), flush=True)
    def cam_at(t):
        return CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5))          # (coordinator, r1za: LOCKED: the drift moved the houses between stills)
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 28.0, 28.0)
    erupt = P["slot"] + [fountain] + flanks + plumes + smoke
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a lava fountain erupts up over the town's roofs", lambda: [fountain] + flanks, T_BURST + 0.35, DUR, {"whole": False}),       # (r1v: with the thin slot it measured 6% of the frame)
                        ("a huge black ash plume towers over the town", lambda: plumes, T_PLUME, DUR, {"whole": False})])


# ====================================================================================================
# shot2.py
# ====================================================================================================
"""BEAT 2: "So Iceland built a wall of rock taller than a house."

THE WALL RISES (coordinator, 2026-11-27: after the audit of every recorded verdict the shots that passed have the WORLD
doing the action while Data reacts, one camera, two or three props; then r2e's and r2i's pre-flights; the purpose
clause "to keep the lava out" is line 3's picture now). One LOCKED lens, low on the town side: one painted tin house
whole at the right of the frame, its back to the wall; Data planted in the foreground at the left, clear of it. Behind
the house a long bank of black boulders grows still by still, one grade throughout, and its BUILDER rides up with it: a
digger on its crest placing a boulder, its arm somewhere new each still. Knee-high (still 1, the digger at ground level
beside the low row), window-high (2), at the eaves (3), far over the ridge and chimney with sky above it (4). Data: hands
on hips facing us; a thumb jerked back at the wall, grinning; half-turned, looking up; leaning right back, arms dropped,
mouth open. No fire and no lava in this shot."""

S2_CREST = 1.6                          # beat 3's crest (S3_CREST)
S2_SLOPE = 4.0 # (r2zf pre-flight: "the wall only a little above the roof": a steeper face brings its crest nearer the lens)                          # (w2b: a shallow face put its top 6 m back, barely over the ridge) a steep face of piled boulders
S2_H = 8.0                              # the finished wall: from this low lens its top stands well over the house's ridge
S2_HOUSE = (-1.05, 0.75, 1.2, 0.95) # (coordinator, r2zh: a CENTRE GAP for the digger: the house takes the right ~35%, its gable end to us)         # (coordinator, r2y: composition) the house: centre x, y, width, depth; the right half of the frame, just clear of the wall's foot (y 0)
S2_P0 = (0.3, 4.6)                     # Data: the left foreground, his feet near the bottom edge
S2_DIG = (0.05, -0.8)                    # the digger on the crest: x (just left of the house, never behind it), and y off the crest's middle


def s2_base(h):
    return 2.0 * (S2_CREST / 2 + 0.1 + 0.97 * h / S2_SLOPE)


def s2_ground_z(x, y):
    """the town's ground (y > 0); the black field beyond the wall"""
    if y > 0.0: return 0.04 + 0.05 * lw_fbm(x * 0.3, y * 0.3, 19)
    return 0.06 + 0.06 * lw_fbm(x * 0.3, y * 0.3, 19)


def place_wall_works():
    """THE WALL'S FOOT IN TOWN: moss ground and yard stones, one painted tin house with its front to the wall, the wall
    (risen by the shot), the black field beyond it."""
    lw_grid("lava field ground", -60, 60, -60, 0.6, 90, 70, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))
    lw_grid("town ground", -40, 40, 0.0, 30, 80, 40, s2_ground_z, lw_noise("town moss ground", "#4E5A34", "#8C9263", scale=0.9, rough=1.0, bump=0.5, detail=12))
    FX.ground("grass", area=(-10, 10, 1.6, 20), zfn=lambda x, y: s2_ground_z(x, y) + 0.03, seed=4, name="town grass")
    px, py = S2_P0
    lava_rock("town yard stones", 420, (-8, 8, 0.2, 12), lambda x, y: s2_ground_z(x, y) + 0.02, seed=78, r=(0.03, 0.1), moss=0.6,
              avoid=lambda x, y: (-1.55 < x < 0.15 and 0.0 < y < 2.1) or (abs(x - px) < 0.5 and abs(y - py) < 0.5))
    lava_rock("near yard stones", 360, (-3.5, 2.5, 3.6, 6.6), lambda x, y: s2_ground_z(x, y) + 0.015, seed=91, r=(0.012, 0.045), moss=0.5,   # (r2g EMPTY 22-24%: the foreground read as one smooth plane)
              avoid=lambda x, y: (-1.55 < x < 0.15 and 0.0 < y < 2.1) or (abs(x - px) < 0.4 and abs(y - py) < 0.4))
    b = s2_base(S2_H)
    wall = earth_wall("earth wall", [(float(x), -b / 2) for x in range(-30, 31, 1)], h=S2_H, crest=S2_CREST, base=b, seed=8)
    for m_ in [bpy.data.materials.get("wall heaped rock")]:      # (r2zd pre-flight: "the wall a flat dark slab"; coordinator: lighter rock, sunlit) this shot's wall only: a grey basalt, not a black block
        if m_ and m_.use_nodes:
            for n_ in m_.node_tree.nodes:
                if n_.bl_idname == "ShaderNodeMix" and n_.blend_type == 'MULTIPLY': n_.inputs[7].default_value = (*K.lin("#8E877E"), 1)
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=math.pi / 2, w=hw, d=hd, storeys=1, base=0.3, pitch=50, roof="#B8352B", wall="#E9D9A2", seed=5)
    def light():
        k = iceland_light(sun_elev=38, sun_az=160, sun=3.2, sky=0.45, haze=1.2)       # (coordinator, r2e: lit so the boulders read) the sun raking across the wall's town face from the right
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(185))      # (r2za EMPTY 48%: turned so its clouds stand over the house) a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall, house=house)


def shot2():
    """THE WALL RISES. See the module's head. (coordinator, after r2e's pre-flight: a LOCKED lens, one grade, nothing
    in the sky but the wall growing still by still and, behind its crest, the lava's glow and smoke held out; Data
    planted in one spot in four distinct poses.)"""
    W = lw_win
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    TOPS = [1.2, 2.9, 4.1, 5.4]  # (coordinator, r2zg: still 4's crest and digger with clear sky above)                             # (coordinator, r2y: measured against the house from the lens) the crest at the windows' sill, their top, the eaves, then twice the house
    def top(t):
        if t <= TS[0]: return TOPS[0]
        for k in range(3):
            if t <= TS[k + 1]: return TOPS[k] + (TOPS[k + 1] - TOPS[k]) * W(t, TS[k], TS[k + 1] - TS[k])
        return TOPS[3]
    P = place_wall_works()
    light = P["light"]; wall = P["wall"]
    b = s2_base(S2_H); yc = -b / 2
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        wall["root"].location = (0, 0, top(t) - S2_H); wall["root"].keyframe_insert("location", frame=f)
    # ---- its builder: one digger on the crest, riding up with it, placing a boulder on the town face, its arm somewhere
    # new each still. The kit's digger is posed when it is built, so each pose is its own digger, shown for its moment.
    rnd = lw_random.Random(12)
    dig_x = lambda t: S2_DIG[0]
    dig_z = lambda t: top(t)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    POSES = [(-10, 55, -75, -40, True), (-5, 30, -95, -20, True), (15, 40, -110, 10, True), (25, 10, -100, 50, True),
             (-20, -8, -105, 30, True), (-15, 2, -100, -20, True)]     # (coordinator, r2y: a boulder in its bucket every still) (p2t: in still 1 it works in the gap between him and the house, then drives along the crest to the left)
    DX, DY = S2_DIG
    diggers = []
    for k, (slew, boom, stick, bucket, loaded) in enumerate(POSES):
        before = set(bpy.data.objects)
        d = FX.digger(name=f"digger {k}", loc=(0, 0, 0), yaw=0.0, slew=0.0, boom=boom, stick=stick, bucket=bucket, lights=False, seed=3)
        d["house"].rotation_euler[2] = math.radians(slew)
        d["root"].rotation_euler[2] = math.pi + 0.7              # its arm out over the town face, three-quarter to us
        d["root"].scale = (1.45, 1.45, 1.45)                      # (coordinator, r2y: real scale: as long as the house is wide, its arm up to the ridge)
        bpy.context.view_layer.update()
        if loaded:
            tip = d["bucket"].matrix_world.translation
            bo = lw_block(f"digger {k} boulder", (tip.x, tip.y, tip.z + 0.1), 0.15, rock_m, rnd, squash=0.8); bo.parent = d["house"]
            bo.matrix_parent_inverse = d["house"].matrix_world.inverted()
        objs = [o for o in bpy.data.objects if o not in before]
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            d["root"].location = (dig_x(t), yc + DY, dig_z(t)); d["root"].keyframe_insert("location", frame=f)
        diggers.append(objs)
    order = [0, 4, 1, 3, 2, 5]                                 # (r2x pre-flight: on still 4 its raised arm was cut by the top edge: the low swing lands there)
    STEP = DUR / 8.0                                             # a working swing: each still lands mid-pose, on a different one
    pose_at = lambda t: order[int(max(0.0, t) / STEP) % len(order)]
    print("S2 digger poses at the stills", [pose_at(t) for t in TS], flush=True)
    for k, objs in enumerate(diggers):
        prev = None
        for f in range(1, NF + 8):
            t = (f - 1) / FPS; hid = pose_at(t) != k
            if hid != prev:
                for o in objs:
                    o.hide_render = hid; o.hide_viewport = hid
                    o.keyframe_insert("hide_render", frame=f); o.keyframe_insert("hide_viewport", frame=f)
                prev = hid
    # ---- him: planted in one spot in the foreground, in four poses
    data = load_data()
    CAM0 = Vector((0.0, 6.0, 0.55)); LOOK0 = CAM0 + Vector((0.0, -1.0, 0.285)) * 5.0      # (coordinator, r2y: LOW, tilted up, close: the ground line in the bottom fifth, the house the right half up to mid-frame, the sky over it where the wall rises)
    X0, Y0 = S2_P0; Z0 = s2_ground_z(X0, Y0) + 0.02
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    LENS = math.degrees(yaw_of(CAM0.x - X0, CAM0.y - Y0))
    data.place(X0, Y0, LENS)                                    # 1 facing us
    data.arm.location.z = Z0
    kit = hard_hat(data)
    T1, T2, T3 = 0.17 * DUR, 0.45 * DUR, 0.8 * DUR             # the turns between the poses (line 2 is a short line now)
    TO = Vector((CAM0.x - X0, CAM0.y - Y0, 0)).normalized()
    for f in range(1, NF + 8):                                 # (r2q HOLD/READ/FAR: planted, but a step back from the wall as it climbs, then another)
        t = (f - 1) / FPS
        SD = Vector((-TO.y, TO.x, 0))
        p = (Vector((X0, Y0, Z0)) + TO * (0.1 * W(t, T2 + 0.3, 0.45) + 0.1 * W(t, T3 - 0.1, 0.45))     # (coordinator, r2y: two real steps back)
             + SD * (0.06 * W(t, 0.15, 0.35) - 0.06 * W(t, 1.25, 0.35) + 0.1 * W(t, T2 + 0.75, 0.4)))     # (r2r READ: a weight shift in each pose)
        yaw = LENS + 25 * W(t, T1, 0.35) + 12 * W(t, T2, 0.45) - 22 * W(t, T3, 0.35)     # (p2q: the house and wall are at his left now: he turns that way)     # 2 a quarter round; 3 half-turned to it; 4 back toward us a little, leaning back
        data._kobj(t, loc=tuple(p), rot=math.radians(yaw))
        data._plant_feet_here(t, lift=(Z0, Z0))
    sc.frame_set(1); bpy.context.view_layer.update()
    M = data.arm.matrix_world
    def pts(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); M = data.arm.matrix_world
        fw = data.forward(); rt = Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))
        return M, fw, rt
    # 1 hands on hips, facing us
    M_, fw, rt = pts(0.0)
    for s_, sg in (("L", -1), ("R", 1)):
        hp = M_ @ data.J[s_]["hip"]
        for tt in (0.0, T1 - 0.05):
            data._arm_ik(s_, hp + rt * sg * 0.07 + fw * 0.02 + Vector((0, 0, 0.05)), tt, 1.4); data._k(f"hand.{s_}", tt, rot=(0, 0, sg * 20))
    # 2 a thumb jerked back over his shoulder at the wall, a grin; the other hand still on his hip
    for tt, jab in ((T1 + 0.4, 0.0), (T2 - 0.05, 0.0)):     # (r2s/r2t FLUID: no second jab, the thumb comes up over 0.45 s)     # (r2r ANATOMY: the hand's target follows him as he steps; READ: the thumb jabs back twice)
        M_, fw, rt = pts(tt)
        sh = M_ @ data.J["R"]["sh"]; hpL = M_ @ data.J["L"]["hip"]
        data._arm_ik("R", sh + rt * 0.2 + fw * (0.03 - jab) + Vector((0, 0, jab)), tt, 1.0); data._k("hand.R", tt, rot=(-20, 0, 25))      # (r2f: over the shoulder put the arm behind his back, the hand in his head) out to the side, jerked back
        data._arm_ik("L", hpL - rt * 0.07 + fw * 0.02 + Vector((0, 0, 0.05)), tt, 1.4); data._k("hand.L", tt, rot=(0, 0, -20))
    # 3 half-turned, looking up at it, his arms down (r2i: a hand at his head read as broken)
    for tt in (T2 + 0.5,):                                     # (r2q FLUID: the hands come down over 0.55 s)
        for bn in data.RELAXED: data._k(bn, tt, rot=data.RELAXED[bn])
    for tt in (T2 + 0.8, T3 - 0.05):                          # (r2v HOLD: his hands drift open from his sides as he takes it in)
        for bn in data.RELAXED:
            r = data.RELAXED[bn]
            data._k(bn, tt, rot=(r[0] - (16 if bn.startswith("arm") else 0), r[1], r[2] + ((-34 if bn.endswith(".R") else 34) if bn.startswith("arm") else 0)))
    # 4 leaning right back looking up, both arms dropped, mouth open
    for tt, dr in ((T3 + 0.3, 6), (T3 + 0.6, 14), (DUR + 0.5, 14)):     # (r2r HOLD: his arms drop on back as he leans)
        for bn in data.RELAXED: data._k(bn, tt, rot=(data.RELAXED[bn][0] + (dr if bn.startswith("arm") else 0),) + tuple(data.RELAXED[bn][1:]))
    lw_layer(data, "spine", lambda t: (-4 * W(t, T2, 0.35) + 6 * W(t, T2 + 0.55, 0.3) - 8 * W(t, T3 - 0.25, 0.5), 0, 0), 0, DUR + 0.4)     # (r2t HOLD: the lean starts as the half-turn settles)
    lw_layer(data, "chest", lambda t: (-3 * W(t, T3, 0.35), 0, 0), 0, DUR + 0.4)     # (r2y pre-flight: no head thrown back)
    HEAD = Vector((X0, Y0, Z0 + 0.5))
    data.look_at(CAM0 + Vector((0, 0, 0.1)), 0.0, max_yaw=55, max_pitch=20, blend=0.0)            # 1 at us
    data.look_at(CAM0 + Vector((0, 0, 0.1)), T1 + 0.3, max_yaw=55, max_pitch=20, blend=0.2)       # 2 at us, the grin
    data.look_at(CAM0 + Vector((-0.5, 0.0, 0.5)), T2 + 0.3, max_yaw=10, max_pitch=8, blend=0.3)     # (r2y pre-flight: thrown back his head read as broken)   # 3 up at it
    data.look_at(CAM0 + Vector((-0.7, 0.0, 0.8)), T3 + 0.3, max_yaw=8, max_pitch=8, blend=0.3)   # 4 at it (r2ze: glasses floated with the head pitched up; coordinator: keep the pitch small, he backs away)
    data.expression("determined", 0.0, T1 + 0.1, blend=0.15)
    data.expression("happy", T1 + 0.1, T2 + 0.1, blend=0.15)
    data.expression("surprised", T2 + 0.1, T3 + 0.1, blend=0.15)
    data.expression("alarmed", T3 + 0.1, DUR + 1.0, blend=0.15)
    data.finish()
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=24.0, fstop=11.0)     # (p2n, r2y: a wider lens: him, the digger and the house side by side, none hiding another)
    print("S2 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    still = lambda t: (CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5)))
    lw_cut(cam, still, still, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a digger piles a wall of black rock behind the house, from its knee to far over its roof", lambda: [wall["body"]], TS[0], TS[3], {"whole": False})])


# ====================================================================================================
# shot3.py
# ====================================================================================================
"""BEAT 3: "So when the lava came, it hit the wall and turned away from the town."

IN FRONT OF THE WALL, on the lava side. A wide lens low on the black field looking at the wall: its boulder face
towers across the frame behind him to its crest and the sky. A river of lava comes past him across the field, slams
into the foot of the face and heaps up; it stops dead against the rock, its crust going dark; he throws his arms up
and grins at us. The WALL stops it: no hose."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FOOT = -S3_BASE / 2         # the outer face's foot (y); the lava field is y < this
S3_P0 = (-0.65, S3_FOOT - 2.6)  # where he stands: on the field at the wall's foot
S3_NOSE = (0.95, S3_FOOT + 0.55) # where the river's front meets the face
S3_SRC = (4.0, -44.0)         # where it comes from: the fissure on the ridge
S3_WIDE = 0.95                 # the river's half width at its front


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


def s3_ground_z(x, y):
    """the black lava field outside the wall; inside, the town's ground"""
    if y > 0.5: return 0.08 * lw_fbm(x * 0.3, y * 0.3, 19) - 1.0 * ease(max(0.0, min(1.0, (y - 4.2) / 1.6)))
    return 0.2 + 0.07 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_river_d(x, y):
    """how far (x, y) is from the lava river's centre line (the ridge to the wall's foot)"""
    ax, ay = S3_NOSE; bx, by = S3_SRC
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    u = max(-0.1, min(1.3, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - ax - u * dx, y - ay - u * dy)


def s3_river(x, y, pad=0.0):
    return s3_river_d(x, y) < S3_WIDE + 0.5 + pad


def place_wall_crest():
    """THE LAVA SIDE OF THE WALL: the black field, the wall's boulder face along it, the
    river's road in across it."""
    lw_grid("lava field ground", -30, 30, -50, 30, 90, 110, s3_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven)
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    off = lambda x, y: s3_river(x, y) or (abs(x - S3_P0[0]) < 0.45 and abs(y - S3_P0[1]) < 0.4)
    lava_rock("lava field rock", 140, (-12, 12, -30, S3_FOOT - 0.3), s3_ground_z, seed=9, r=(0.1, 0.35), moss=0.0, avoid=off)
    lava_rock("field block", 420, (-8, 8, -14, S3_FOOT - 0.1), s3_ground_z, seed=19, r=(0.05, 0.22), moss=0.0, avoid=off)   # the field outside the wall: broken black blocks
    lava_rock("wall face rock", 420, (-9, 10, S3_FOOT + 0.1, -1.0), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=27, r=(0.08, 0.26), moss=0.0,
              avoid=None)       # the black rock it is built of, on its face
    lava_rock("wall foot rubble", 160, (-7, 9, S3_FOOT - 0.5, S3_FOOT + 0.3), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=29, r=(0.06, 0.2), moss=0.0, avoid=off)
    def light():
        k = iceland_light(sun_elev=30, sun_az=-140, sun=3.0, sky=0.4, haze=1.4)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))     # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. See the module's head."""
    T_HIT = 0.3 * DUR; T_STOP = 0.52 * DUR; T_DARK = 0.66 * DUR; T_SLAP = 0.84 * DUR
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    YAW = math.radians(12)                                   # three-quarter to the lens, which is on the field at his front left
    X0, Y0 = S3_P0; Z0 = s3_ground_z(X0, Y0) + 0.02
    data.place(X0, Y0, math.degrees(YAW))
    data.arm.location.z = Z0
    kit = hard_hat(data)
    # ---- the river: a long band of lava from the ridge, its front as wide as a street, sliding in along its own line
    ax, ay = S3_NOSE; bx, by = S3_SRC
    L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; nx, ny = -uy, ux
    out = []
    NS = 46
    for k in range(NS + 1):                                # up one bank, round the front, down the other (counter-clockwise)
        d = L * (k / NS) ** 1.6; wd = S3_WIDE * (1.0 + 0.03 * d) * (1 + 0.14 * math.sin(d * 0.9 + 1.0) + 0.09 * math.sin(d * 2.3))
        out.append((ax + ux * d + nx * wd, ay + uy * d + ny * wd))
    for k in range(NS, -1, -1):
        d = L * (k / NS) ** 1.6; wd = S3_WIDE * (1.0 + 0.03 * d) * (1 + 0.14 * math.sin(d * 1.1) + 0.09 * math.sin(d * 2.9 + 2.0))
        out.append((ax + ux * d - nx * wd, ay + uy * d - ny * wd))
    for k in range(1, 8):                                  # the front itself: a blunt lobed nose
        a = math.pi * k / 8
        out.append((ax - nx * S3_WIDE * math.cos(a) - ux * 1.1 * math.sin(a) * (1 + 0.15 * math.sin(5 * a)), ay - ny * S3_WIDE * math.cos(a) - uy * 1.1 * math.sin(a) * (1 + 0.15 * math.sin(5 * a))))
    sgn = sum(out[i][0] * out[(i + 1) % len(out)][1] - out[(i + 1) % len(out)][0] * out[i][1] for i in range(len(out)))
    if sgn < 0: out.reverse()
    lm = lava_mat("lava river", heat=2.2, scale=6.0, fresh=0.3)
    river = lava("lava river", out, z=0.0, thick=0.34, m=lm, seed=7, lumpy=0.2)
    home = Vector(river.location); RUN = 5.5                # how far out the front is at the start
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = min(1.0, max(0.0, (t + 0.5) / (T_HIT + 0.5))); back = RUN * (1 - u) ** 1.1      # it comes fast and SLAMS: no easing into the face
        heap = W(t, T_HIT - 0.05, 0.45)
        river.location = (home.x + ux * back, home.y + uy * back, 0.16 + 0.05 * heap); river.scale = (1, 1, 1.0 + 0.45 * heap)
        river.keyframe_insert("location", frame=f); river.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.25, axis=1)
    # broken crust plates heap and tip up against the face along the whole front as it hits
    cm_ = lava_mat("lava crust block", heat=1.4, scale=1.6, fresh=0.0); rb = lw_random.Random(23); fb = []
    for k in range(70):
        along = rb.uniform(-1.0, 1.0); o_ = lw_block("front crust", (0, 0, -6), rb.uniform(0.09, 0.24), cm_, rb, squash=0.55)
        fb.append((o_, along, rb.uniform(-0.5, 0.35), rb.uniform(-0.4, 0.4), rb.uniform(0, 6.3), rb.uniform(0.0, 0.3)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for o_, along, dy_, tilt, spin, lag in fb:
            on = t >= T_HIT - 0.05 + lag * 0.5; buck = W(t, T_HIT + lag, 0.5)
            x_ = ax + 0.9 * along; y_ = S3_FOOT + 0.25 + dy_ * (1 - 0.5 * buck) + 0.3 * buck
            o_.location = (x_, y_, (s3_face_z(y_) + 0.3 + 0.45 * buck * (1 - 0.4 * along * along)) if on else -6.0)
            o_.rotation_euler = (tilt + 1.0 * buck, 0.5 * buck * along, spin)
            o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]; heat_c = cm_.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):                           # stopped, it crusts over: its seams go dark
        t = (f - 1) / FPS; cool = 1 - 0.93 * W(t, T_STOP, T_DARK + 0.5 - T_STOP)
        heat.default_value = 2.4 * (1 + 0.6 * lw_kick(t - T_HIT, 0.35)) * cool; heat.keyframe_insert("default_value", frame=f)
        heat_c.default_value = 1.5 * cool; heat_c.keyframe_insert("default_value", frame=f)
    # the heat is LOCAL light: lamps low along the front, on the rock face and on him, never on the lava's own crust
    glows = [(lw_point(f"lava front glow {k_}", (ax - 0.9 + 0.36 * k_, S3_FOOT - 0.35, 0.8), 0.0, col=(1.0, 0.42, 0.1), r=0.25), 26.0) for k_ in range(6)]
    steam = lw_steam("front steam", (ax, S3_FOOT + 0.3, 0.7), w=0.8, h=1.8, seed=8.5, col=(0.96, 0.96, 0.96), dens=4.0, lean=(0.3, 0.1), rise=1.6,
                     keys=[(T_HIT - 0.1, 0.0), (T_HIT + 0.35, 1.0), (T_DARK, 0.7), (DUR + 1.0, 0.35)], t_end=DUR + 1.0)    # steam comes free off the front where it hit wet rock
    try:
        gc = bpy.data.collections.new("glow receivers"); bpy.context.scene.collection.children.link(gc)
        for o_ in [river] + [b[0] for b in fb] + ([steam] if hasattr(steam, "name") else []): gc.objects.link(o_)
        for co_ in gc.collection_objects: co_.light_linking.link_state = 'EXCLUDE'
        for l_, _e in glows: l_.light_linking.receiver_collection = gc
    except Exception as e_:
        print("S3 light linking unavailable:", e_, flush=True)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS
        for l_, e_ in glows:
            l_.data.energy = e_ * W(t, T_HIT - 0.25, 0.4) * (1 - 0.93 * W(t, T_STOP, T_DARK + 0.5 - T_STOP)); l_.data.keyframe_insert("energy", frame=f)
    # ---- him: braced at the foot watching it come, a flinch as it slams in, a look, then both arms up
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        z_ = -0.07 * W(t, 0.1, 0.4) * (1 - W(t, T_STOP, 0.4)) + 0.05 * lw_kick(t - T_HIT, 0.2) + 0.04 * lw_kick(t - T_SLAP, 0.25)   # knees bent, braced; a jolt at the hit
        y_ = -0.07 * W(t, T_HIT - 0.05, 0.25) - 0.04 * W(t, T_SLAP - 0.5, 0.45)                    # a step back against the wall at the hit, another to lean on it
        x_ = -0.05 * W(t, T_HIT, 0.3) + 0.2 * W(t, T_SLAP - 0.5, 0.45) + 0.04 * math.sin(2 * math.pi * t / 1.1) * (1 - W(t, T_HIT - 0.2, 0.3))
        data._kobj(t, loc=(X0 + x_, Y0 + y_, Z0 + z_), rot=YAW + math.radians(26) * W(t, T_HIT - 0.45, 0.4) - math.radians(22) * W(t, T_STOP + 0.1, 0.5))
        data._plant_feet_here(t, lift=(Z0, Z0))
    lw_layer(data, "spine", lambda t: (10 * W(t, 0.1, 0.4) * (1 - W(t, T_HIT - 0.1, 0.2)) - 18 * lw_kick(t - T_HIT, 0.3) - 8 * W(t, T_SLAP - 0.2, 0.4), 0, 0), 0, DUR + 0.4)
    CAM0 = Vector((-0.8, S3_FOOT - 4.3, Z0 + 0.85)); LOOK0 = CAM0 + Vector((0.25, 0.97, 0.08))
    FRONT = Vector((ax, S3_FOOT, 0.9))
    data.look_at(Vector((X0 + 0.9, Y0 - 0.6, 0.3)), 0.0, max_yaw=18, max_pitch=16, blend=0.0)       # at it coming across the field
    data.look_at(FRONT, T_HIT - 0.1, max_yaw=20, max_pitch=14, blend=0.2)
    data.look_at(CAM0, T_STOP + 0.2, max_yaw=55, max_pitch=40, blend=0.3)
    data.expression("alarmed", 0.0, T_SLAP - 0.3, blend=0.12)
    data.expression("pleased", T_SLAP - 0.25, DUR + 1.0, blend=0.25)
    sides = sorted("LR", key=lambda s_: -acts._shoulder(data, s_).x)          # sides[0] is the arm toward the lava, sides[1] toward the wall
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    UP = lambda sg: ((-58, 0, -sg * 12), (-48, 0, -sg * 22), (-10, sg * -12, -sg * 15))
    LOW = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = (WHOA, LOW, UP, WHOA, WHOA, UP, UP) if sd == sides[0] else (LOW, WHOA, UP, WHOA, LOW, UP, UP)
        for tk, pose in zip((0.0, 0.5 * T_HIT, T_HIT + 0.05, T_HIT + 0.5, T_DARK, T_SLAP, DUR + 0.5), seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    data.finish()
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(0.33, 0.47), height=0.35, t=T_HIT)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24.0, fstop=11.0)
    print("S3 CAM", tuple(round(v, 2) for v in CAM), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    def cam_at(t):
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * lw_kick(t - T_HIT, 0.3) * 2
        return CAM + shake, LOOK + shake, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("the lava river comes across the field and slams into the wall's face, heaping up", lambda: [river] + [b[0] for b in fb], T_HIT - 0.3, T_STOP, {"whole": False}),
                        ("it stops dead against the rock and its crust goes dark", lambda: [river], T_STOP, DUR, {"whole": False})])


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
S4_HALF = 8.0                   # the asphalt and pavement, out to the house fronts (x)
S4_KERB = 1.15                  # the kerbs (x): a narrow town street, so a long lens down it holds both rows of houses
S4_FRONT = 1.65                 # the house fronts (x)


def s4_zig(x):
    """the crack's zig-zag line across the street: y at x"""
    return S4_YC + 0.12 * math.sin(3.1 * x + 0.4) + 0.07 * math.sin(7.3 * x + 1.1)


def s4_ground_z(x, y):
    z = -0.6 if abs(x) < S4_HALF + 0.2 and abs(y - S4_YC) < 1.6 else -0.06   # under the slabs; well under the crack's trench (the gap showed black ground)
    if abs(y) > 5.0 or abs(x) > S4_HALF + 1.0: z += 0.06 + 0.1 * lw_fbm(x * 0.4, y * 0.4, 23)
    return z


def s4_slab(name, near, m):
    """one side of the cracked street: the asphalt from the crack to the end of the street (near: toward the lens),
    its crack edge the zig-zag with a 0.25 m face down into the ground. Built as strips of quads, every face up or out
    (one concave n-gon rendered black). Returns the object, origin on the crack line."""
    NS = 160
    xs = [-S4_HALF + 2 * S4_HALF * k / NS for k in range(NS + 1)]
    far_y = -S4_FRONT if near else S4_FRONT
    bm = LW_bmesh.new()
    te = [bm.verts.new((x, s4_zig(x) - S4_YC, 0.0)) for x in xs]
    tf = [bm.verts.new((x, far_y - S4_YC, 0.0)) for x in xs]
    be = [bm.verts.new((x, s4_zig(x) - S4_YC, -0.25)) for x in xs]
    for i in range(NS):
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
    lw_grid("town ground", -30, 60, -30, 30, 100, 90, s4_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))
    asph = ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt")          # REAL asphalt (Poly Haven)
    near = s4_slab("street near", True, asph)
    far = s4_slab("street far", False, asph)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sy, slab in ((-1, near), (1, far)):
        o = K.box("kerb", (0, sy * S4_KERB, 0.04), (2 * S4_HALF, 0.12, 0.08), kerb, bev=0.01)
        o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    trench = lava_mat("crack lava", heat=1.6, scale=4.0, fresh=0.7)
    K.box("crack trench", (0, S4_YC, -0.32), (2 * S4_HALF + 0.4, 1.6, 0.1), trench, bev=0)
    for sy in (-1, 1):
        K.box("crack wall rock", (0, S4_YC + sy * 0.85, -0.23), (2 * S4_HALF + 0.4, 0.1, 0.4), lw_noise("crack rock", "#2A2522", "#4A3E36", scale=10, rough=0.95, bump=1.0), bev=0)
    houses = []
    for sy in (-1, 1):                                    # the street runs along X: a row of town houses down each side, their doors to the road
        x = -5.0 + (0.6 if sy > 0 else 0.0); k = 0
        while x < 6.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            roof = ROOFS[(k * 3 + (sy > 0) + 1) % len(ROOFS)]
            hs = town_house(f"town house {sy}_{k}", (x + w / 2, sy * (S4_FRONT + d / 2), 0), yaw=0.0 if sy > 0 else math.pi, w=w, d=d,
                            roof=roof, wall=WALLS[(k + (sy > 0) * 2) % len(WALLS)], base=0.3, storeys=1, seed=k + 20)
            houses.append(hs); x += w + rnd.uniform(0.4, 0.8); k += 1
    wall = earth_wall("earth wall", [(12.5 + 0.1 * y, y) for y in range(-30, 32, 2)], h=3.8, crest=1.4, base=7.0, seed=12)
    lava_rock("wall foot rubble", 160, (7.5, 10.5, -6.0, 6.0), lambda x, y: 0.0, seed=71, r=(0.08, 0.3), moss=0.0, avoid=lambda x, y: abs(y) < 1.2 and x < 8.6)       # STRAIGHT, flat-topped and steep, right across the end of the street, over the roofs (board B2: "a natural hillside")   # right across the end of the street, over the roofs: this street is INSIDE it
    for k, y in enumerate((1.5,)):            # the eruption's smoke over the wall: rolling columns of gas, leaning off on the wind
        lw_steam(f"wall smoke {k}", (21.0 + 2 * k, y, 2.0), w=4.5, h=16.0, seed=3.3 * k, col=(0.42, 0.41, 0.42), dens=2.5, lean=(0.2, 0.5), rise=1.2, t_end=DUR + 1.0)
    # the street under the eruption's fall-out: grit and lava cinders blown over the asphalt, a drain grating at each kerb
    bits = lava_rock("street cinders", 260, (-3.0, 13.0, -S4_KERB + 0.1, S4_KERB - 0.1), lambda x, y: 0.0, seed=44, r=(0.012, 0.04), moss=0.0,
                     avoid=lambda x, y: abs(y - s4_zig(x)) < 0.5 or (abs(x) < 0.8 and y > 0))
    grate = lw_metal("drain grating", "#2A2B2D", rough=0.6)
    for k in range(5):
        for sy in (-1, 1):
            bits.append(K.box("drain grating", (-1.0 + 3.0 * k + (1.5 if sy > 0 else 0.0), sy * (S4_KERB - 0.2), 0.012), (0.4, 0.22, 0.008), grate, bev=0.0))
    bpy.context.view_layer.update()
    for o in bits:                                       # they ride their half of the street when it jolts
        slab = near if o.location.y < s4_zig(o.location.x) else far
        o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    for k in range(2):                                   # REAL street lamps (Poly Haven) along the left kerb
        ph_model("street_lamp_01", (3.0 + 6 * k, S4_KERB + 0.25, 0.0), rot=(0, 0, math.pi), scale=0.5, name=f"street lamp {k}")

    def light():
        k = iceland_light(sun_elev=30, sun_az=-30, sun=3.2, sky=0.45, haze=1.2)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))      # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, near=near, far=far, houses=houses)


def shot4():
    """THE CRACK. A lens low in the street looking up it: the driver comes down the middle of the empty street toward us
    with a sandbag in his arms, houses down both sides, the earth wall across the end of the street over their roofs.
    The road jolts and a zig-zag crack tears across the asphalt right in front of his boots; he drops the bag and leaps
    back; the street pulls apart, the gap glowing orange, steam shooting up; lava wells up out of it and pours down the
    street at us; he hops back again, arms up against the heat."""
    T_JOLT = 0.2 * DUR; T_TEAR = T_JOLT + 0.05; T_TORN = T_TEAR + 0.35
    T_LET = 0.255 * DUR; T_OPEN0 = 0.355 * DUR; T_OPEN1 = 0.52 * DUR
    T_POUR = 0.5 * DUR; T_TIP = T_OPEN0 + 0.1; T_RUN = 0.8 * DUR
    W = lw_win
    P = place_town_crack()
    light = P["light"]; near, far = P["near"], P["far"]
    data = load_data()
    YAW = math.radians(-50)                                  # three-quarter to the lens, which is down the street at his front left
    X0 = 0.0; Y0 = s4_zig(X0) + 0.2                        # on the far side of the crack's line, his boots at its lip
    data.place(X0, Y0, math.degrees(YAW))
    kit = hard_hat(data)
    T_W = T_JOLT - 0.06                                     # he WALKS in (real steps), the last half metre down the street to the spot
    fw0 = data.forward(); fw0.z = 0; fw0.normalize()
    data.place(X0 - fw0.x * 0.32, Y0 - fw0.y * 0.32, math.degrees(YAW))
    data.walk_to((X0, Y0), 0.0, T_W)
    def hop(t, t0, d, h, T=0.4):
        u = min(1.0, max(0.0, (t - t0) / T)); return d * ease(u), h * math.sin(math.pi * u)
    for f in range(F(T_W) + 1, NF + 1):
        t = (f - 1) / FPS
        y1, z1 = hop(t, T_LET, 0.1, 0.11, 0.4); y2, z2 = hop(t, T_POUR + 0.1, 0.02, 0.06); y3, z3 = 0.0, 0.0; y4, z4 = hop(t, 0.74 * DUR, 0.03, 0.09, 0.42)      # (both feet are on the road at every board still but the leap: a hop caught mid-air read as floating); y2 += y4; z2 += z4
        jolt = -0.03 * lw_kick(t - T_JOLT, 0.1) - 0.04 * lw_kick(t - T_POUR, 0.15)
        walk = 0.0; step = 0.0
        back = -0.05 * W(t, T_TEAR, 0.3)                                               # a start back off the tear
        data._kobj(t, loc=(X0 + 0.05 * W(t, T_LET, 0.6) + 0.07 * math.sin(2 * math.pi * (t - T_POUR) / 1.3) * W(t, T_POUR, 0.3) + 0.06 * walk, Y0 + y1 + y2 + y3 - back + 0.3 * walk, 0.03 + z1 + z2 + z3 + jolt + step),
                   rot=YAW - math.radians(8) * W(t, T_LET, 0.4) + math.radians(14) * W(t, T_RUN + 0.1, 0.5) + math.radians(14) * math.sin(2 * math.pi * (t - T_POUR) / 1.3) * W(t, T_POUR, 0.4))
    lw_layer(data, "spine", lambda t: (16 * W(t, T_TEAR + 0.1, 0.35) * (1 - W(t, T_LET - 0.45, 0.3)) - 16 * lw_kick(t - T_JOLT, 0.18)
                                       - 26 * W(t, T_LET + 0.05, 0.25) * (1 - W(t, T_LET + 0.7, 0.3)) - 14 * W(t, T_RUN, 0.3), 0, 0), 0, DUR + 0.4)
    # ---- face and head: one feeling per moment, held (BEFORE the hands: a face moves his chest and shoulders)
    CAM0 = Vector((X0 - 1.4, Y0 - 0.45, 0.8)); LOOK0 = CAM0 + Vector((1.0, 0.02, -0.25))      # the street's far end, and the wall across it, stand clear at the right of his hat      # a little above him, tipped down at the road: the crack lies across the frame's lower third, the wall's crest and the sky across its top
    data.look_at(CAM0, 0.0, max_yaw=40, max_pitch=30, blend=0.0)                                        # coming down the street to us
    data.look_at(Vector((X0 - 0.35, s4_zig(X0 - 0.35), 0.0)), T_JOLT + 0.05, max_yaw=50, max_pitch=25, blend=0.2)   # down at the crack at his boots
    data.look_at(CAM0, T_LET + 0.5, max_yaw=55, max_pitch=40, blend=0.3)                                # up at us: did you see that
    data.look_at(Vector((X0 - 0.3, S4_YC - 0.5, 0.0)), T_POUR + 0.1, max_yaw=50, max_pitch=25, blend=0.3)  # at the lava welling up
    data.look_at(CAM0, T_RUN + 0.3, max_yaw=55, blend=0.3)
    data.expression("determined", 0.0, T_JOLT, blend=0.2)
    data.expression("alarmed", T_JOLT + 0.02, DUR + 1.0, blend=0.12)
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)       # (no prop: the spoken line names none, and a bag he drops has to be accounted for in every still after)
    # one arm up across his face against the heat, the other back for balance: never both out at his sides
    near_sd = min(sides, key=lambda s_: (acts._shoulder(data, s_) - CAM0).length)
    # FK poses from here (IK through these folded the elbow over, 60-180 deg/frame): the far arm thrown UP, palm out
    # at the heat, beside his head from the lens, never over his face; the near arm low and forward, pushing it off
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    UP = lambda sg: ((-58, 0, -sg * 12), (-48, 0, -sg * 22), (-10, sg * -12, -sg * 15))
    SHIELD = lambda sg: ((-50, 0, -sg * 30), (-55, 0, -sg * 45), (-10, sg * -12, -sg * 15))    # the forearm up across his face, palm out at the heat
    LOW = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = (LOW, WHOA, LOW, UP, UP, WHOA, UP, WHOA, LOW, WHOA, WHOA) if sd != near_sd else (WHOA, LOW, WHOA, WHOA, UP, WHOA, LOW, WHOA, SHIELD, SHIELD, SHIELD)   # both fly up at the leap; at the end the arm nearest the flow is up across his face against the heat   # his arms swing as he walks, fly up at the tear
        for tk, pose in zip((0.0, 0.38, 0.74, T_TORN - 0.1, T_LET + 0.15, T_LET + 0.55, T_LET + 0.95, T_LET + 1.3, T_LET + 1.7, T_LET + 2.1, DUR + 0.5), seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    # ---- the crack: a hairline tears across from kerb to kerb, then the street pulls apart and the lava shows in the gap
    gm = lava_mat("crack glow", heat=2.4, scale=6.0)
    rim_m = lw_emit("crack glow hot", "#FF4A08", 2.2)       # the light from inside, standing in the gap: a flat crusted skin read as a dark line from a low lens
    NR = 240
    xs = [-S4_HALF + 2 * S4_HALF * k / NR for k in range(NR + 1)]
    bm = LW_bmesh.new()
    far_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC + 0.02, 0.05)) for x in xs]
    near_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.08, 0.05)) for x in xs]
    for i in range(NR): bm.faces.new((near_e[i], near_e[i + 1], far_e[i + 1], far_e[i]))
    me = bpy.data.meshes.new("crack glow"); bm.to_mesh(me); bm.free(); me.materials.append(gm)
    tear = lw_link(bpy.data.objects.new("crack glow", me)); tear.location = (-S4_HALF, S4_YC, 0.0)
    bm = LW_bmesh.new()
    rib_lo = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.03, -0.02)) for x in xs]
    rib_hi = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.03, 0.06)) for x in xs]
    for i in range(NR): bm.faces.new((rib_lo[i], rib_lo[i + 1], rib_hi[i + 1], rib_hi[i]))
    me = bpy.data.meshes.new("crack glow rim"); bm.to_mesh(me); bm.free(); me.materials.append(rim_m)
    rim = lw_link(bpy.data.objects.new("crack glow rim", me)); rim.location = (-S4_HALF, S4_YC, 0.0)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR)
        rim.scale = (max(0.002, u), 1, 1); rim.hide_render = u < 0.01 or t > T_OPEN0 + 0.25
        rim.keyframe_insert("scale", frame=f); rim.keyframe_insert("hide_render", frame=f)
    tear.shape_key_add(name="Basis")
    op = tear.shape_key_add(name="open")
    for i in range(NR + 1): op.data[NR + 1 + i].co.y = s4_zig(xs[i]) - S4_YC - 0.36
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR); o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0)
        tear.scale = (max(0.002, u), 1, 1); tear.hide_render = u < 0.01; op.value = o
        tear.keyframe_insert("scale", frame=f); tear.keyframe_insert("hide_render", frame=f); op.keyframe_insert("value", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0); sh = 0.015 * math.sin(2 * math.pi * 11 * t) * lw_kick(t - T_JOLT, 0.25)
        near.location = (sh, S4_YC - 0.28 * o, 0.01 * o + 0.04 * lw_kick(t - T_JOLT, 0.12)); near.rotation_euler = (math.radians(-1.5) * o, 0, 0)
        far.location = (-sh, S4_YC, 0.0)
        for o_ in (near, far): o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    # the asphalt BREAKS along both lips: slabs of it heave up and tilt, first a little as the crack tears, then right up
    # as the street pulls apart, raw dark edges catching the glow
    lip = bpy.data.materials["street asphalt"]          # the road's own skin: until it breaks there is no line across the street
    rk = lw_random.Random(7)
    lips = []
    for slab, sg in ((near, -1), (far, 1)):
        x = -0.1                                           # (none under the lens: a shard a hand from the glass is a boulder)
        while x < S4_HALF - 0.1:
            w = rk.uniform(0.18, 0.34); xc = x + w / 2
            ch = lw_block("crack lip chunk", (xc, s4_zig(xc) - S4_YC + sg * rk.uniform(0.05, 0.11), -0.01), 1.0, lip, rk, squash=1.0); ch.scale = (w * rk.uniform(0.5, 0.7), rk.uniform(0.07, 0.14), rk.uniform(0.03, 0.05))   # torn SHARDS of asphalt, every one its own shape (board B2: "paver tiles")
            ch.parent = slab; ch.matrix_parent_inverse = slab.matrix_world.inverted(); lips.append(ch)
            lift = rk.uniform(0.25, 0.55); yaw = rk.uniform(-0.25, 0.25); t0 = T_OPEN0 + 0.1 * abs(xc) / S4_HALF
            for f in range(1, NF + 1):
                t = (f - 1) / FPS; o = 0.3 * W(t, T_TEAR + 0.3 * abs(xc + S4_HALF) / (2 * S4_HALF), 0.25) + 0.7 * W(t, t0, 0.45)
                if sg > 0 and abs(xc - X0) < 0.3: o *= 0.25                                # (the ones his boots stand at stay near flat)
                ch.rotation_euler = (-sg * lift * o, 0.15 * yaw * o, yaw * o); ch.location.z = -0.04 + 0.08 * o   # flush with the road until it breaks (his boots walk over it)
                ch.keyframe_insert("rotation_euler", frame=f); ch.keyframe_insert("location", frame=f)
            x += w
    lava_flow_key(gm, 0.0, DUR + 0.5, 0.2)
    trench = bpy.data.materials["crack lava"]
    lava_flow_key(trench, 0.0, DUR + 0.5, 0.25)
    # ---- steam shooting up out of the crack as it opens: two thin jets, one at each edge of the frame, off the lens's line to him
    steam = []
    for k, (x, lx_) in enumerate(()):                       # (none: a jet's box stood between the lens and his face, and a thin jet does not render)
        t0 = T_OPEN0 + 0.08 * k
        steam.append(lw_fire_column(f"crack steam {k}", (x, s4_zig(x) - 0.35, -0.2), w=0.3, h_fire=0.2, h_smoke=2.4, lean=(lx_, 0.0), t_end=DUR + 1.0,
                                    seed=2.1 * k, fire=0.0, smoke_d=20.0, smoke=(0.9, 0.91, 0.93), rise=2.6, flame_d=0.0, spread=0.1,
                                    keys=[(t0, 0.0), (t0 + 0.45, 1.0), (DUR, 0.6)], grow=True))
    # ---- the lava: it wells up in the crack and pours out over the road, down the street at the lens
    lm = lava_mat("street lava", heat=2.4, scale=9.0, fresh=0.35)
    for n_ in lm.node_tree.nodes:                             # BLACK crust plates over bright seams (board: "a tan, rubbery sheet"): no broad dull-red patches in daylight
        if n_.type == 'MAP_RANGE' and abs(n_.inputs["To Max"].default_value - 0.35) < 1e-4 and abs(n_.inputs["From Min"].default_value - 0.5) < 1e-4:
            n_.inputs["To Max"].default_value = 0.06
    out = []
    for k in range(40):
        a = 2 * math.pi * k / 40
        out.append((1.0 * math.cos(a) + 0.03 * math.sin(5 * a), 1.0 * math.sin(a) + 0.1 * math.cos(9 * a) + 0.06 * math.sin(14 * a)))
    flow = lava("street lava", out, z=0.0, thick=0.22, m=lm, seed=6, lumpy=0.1, n=40)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_POUR, 0.94 * DUR - T_POUR); w_ = W(t, T_POUR - 0.25, 0.4)
        L_ = 0.1 + 0.6 * u                                                     # a mound welling out of the gap, spreading down the middle of the road and across to the doors
        flow.location = (X0 + 2.6, S4_YC - 0.02 - 0.72 * L_, -0.2 + 0.22 * w_)        # it wells up along the crack and pours across the street
        flow.scale = (2.6, L_ * 1.25, 0.75 + 0.2 * (1 - u) * w_); flow.keyframe_insert("location", frame=f); flow.keyframe_insert("scale", frame=f)
        flow.hide_render = t < T_OPEN0 + 0.05; flow.keyframe_insert("hide_render", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.3, axis=1)
    glow2 = lw_point("far lava glow", (X0 + 4.0, -0.3, 1.2), 0.0, col=(1.0, 0.45, 0.12), r=0.8)
    # the heat is LOCAL light (board B3: "the whole street turns sepia"): small lamps low along the flow's edges, each
    # a pool half a metre wide on the road, on him and on the doorsteps; the street beyond them stays grey asphalt
    glows = []
    for k_, (gx, gy, e_) in enumerate(((X0 + 0.15, 0.18, 14.0), (X0 + 0.9, 0.3, 8.0), (X0 + 1.8, 0.35, 8.0), (X0 + 0.6, -1.15, 8.0), (X0 + 1.7, -1.3, 10.0), (X0 + 2.9, -1.3, 10.0), (X0 + 4.2, -1.2, 10.0))):
        glows.append((lw_point(f"lava edge glow {k_}", (gx, gy, 0.3), 0.0, col=(1.0, 0.4, 0.08), r=0.15), e_))
    steamw = lw_steam("crack steam", (X0 + 2.8, -0.2, 0.0), w=0.55, h=1.1, seed=8.5, col=(0.96, 0.96, 0.96), dens=5.0, lean=(0.2, 0.1), rise=2.0,
                      keys=[(T_OPEN0 + 0.2, 0.0), (T_POUR + 0.3, 1.0), (DUR + 1.0, 1.0)], t_end=DUR + 1.0)       # white steam off the crack itself
    try:                                                   # the lamps light everything BUT the lava and its steam: lit from a hand away, black crust went tan
        gc = bpy.data.collections.new("glow receivers"); bpy.context.scene.collection.children.link(gc)
        for o_ in [flow, tear] + lips + ([steamw] if hasattr(steamw, "name") else []): gc.objects.link(o_)
        for co_ in gc.collection_objects: co_.light_linking.link_state = 'EXCLUDE'
        for l_, _e in glows: l_.light_linking.receiver_collection = gc
        # and HE is lit orange by it: one warm lamp low on the lava side that lights only him, so the street keeps its grade
        hc = bpy.data.collections.new("heat on him"); bpy.context.scene.collection.children.link(hc)
        for o_ in bpy.data.objects:
            p_ = o_
            while p_ is not None and p_ is not data.arm: p_ = p_.parent
            if p_ is data.arm and o_.type == 'MESH': hc.objects.link(o_)
        heat = lw_point("heat on him", (X0 + 0.7, Y0 - 0.75, 0.35), 0.0, col=(1.0, 0.42, 0.1), r=0.25)
        heat.light_linking.receiver_collection = hc; glows.append((heat, 220.0))
    except Exception as e_:
        print("S4 light linking unavailable:", e_, flush=True)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS
        for n_, (l_, e_) in enumerate(glows):
            l_.data.energy = e_ * (0.25 * W(t, T_TEAR, 0.3) * (n_ < 3) + 0.75 * W(t, T_POUR - 0.2 + 0.12 * min(n_, 7 - n_), 0.7)); l_.data.keyframe_insert("energy", frame=f)
    data.finish()
    # ---- the lens: low in the street at his front left, looking up it: the crack across the bottom of the frame in
    # front of his boots, the houses down both sides behind him, the wall across the end of the street with its smoke
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(0.24, 0.6), height=0.345, t=DUR - 0.1)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24.0, fstop=11.0)
    print("S4 CAM", tuple(round(v, 2) for v in CAM), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    def cam_at(t):
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * (lw_kick(t - T_JOLT, 0.25) + lw_kick(t - T_TEAR - 0.3, 0.25)) * 2
        return CAM + shake, LOOK + shake, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="town_crack", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a crack tears across the road in front of his boots and pulls open, glowing", lambda: [tear, rim] + lips, T_TORN, T_OPEN1 + 0.2, {"whole": False}),
                        ("lava wells up and pours down the street at us", lambda: [flow], T_POUR + 0.3, DUR, {"whole": False})])


# ====================================================================================================
# shot5.py
# ====================================================================================================
"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but almost nobody moved back. Would you?"

Dawn, the morning after, at the foot of the town's hill. Up the hill three houses burn in a row, side by side, black
lava round them; the earth wall stands across the hilltop behind them; below them the saved houses stand with dark
windows. The driver walks up to his own house with a lit lantern, hangs it on the hook by his window, and that one
window lights up: the only light in the town. He turns to us and shrugs."""

S5_HOOK = Vector((-0.3, 2.77, 0.47))        # the hook's tip: an iron arm off his house's front wall, between the window and the corner, at his own height
S5_KNOTS = ((6.9, 0.0), (8.2, 1.4), (10.0, 2.0), (11.2, 7.0), (14.4, 7.7), (17.5, 8.0), (19.5, 9.0), (40.0, 10.9))    # the hill behind his house (y, z)
S5_BURN_Y = 12.9                            # the burning row
S5_WALL_Y = 18.5
S5_BURN_X = 9.3                              # the burning row's middle: up the hill over his roof, in the middle of the lens's frame


def s5_z(x, y):
    """the paved yard in front of his house, flat; the hill climbing behind it, street over street"""
    if y <= S5_KNOTS[0][0]: return 0.0
    z = S5_KNOTS[-1][1]
    for (y0, z0), (y1, z1) in zip(S5_KNOTS, S5_KNOTS[1:]):
        if y <= y1:
            u = (y - y0) / (y1 - y0); z = z0 + (z1 - z0) * u; break
    return z + 0.1 * lw_fbm(x * 0.3, y * 0.3, 51) * min(1.0, (y - S5_KNOTS[0][0]) / 2.0)


def s5_lantern():
    """a REAL hurricane lantern (Poly Haven's Lantern_01), its glass glowing with the flame in it, hung by its top: the
    pivot at the top of its bail, the lantern below it"""
    root = K.empty("lantern", (0, 0, 0))
    S_ = 0.95
    lm = ph_model("Lantern_01", (0, 0, -0.29 * S_), scale=S_, name="lantern body", parent=root)
    glow = lw_emit("lantern glow", "#FFB050", 14.0)
    for c in lm.children_recursive:
        if "glass" in c.name.lower():
            c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = glow
    L = lw_point("lantern light", (0, 0, -0.16), 30.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.16)
    return root


def s5_lit_pane(house, k, t_on):
    """a window of a dark house that lights up at t_on (a pane in front of the dark one)"""
    p = house["windows"][k]
    lit = p.copy(); lit.data = p.data.copy(); bpy.context.collection.objects.link(lit)
    lit.name = p.name.replace("window pane", "window lit pane")
    lit.data.materials.clear(); lit.data.materials.append(lw_emit("window lit warm", "#FF6A00", 1.5))
    bpy.data.materials["window lit warm"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.012, 0.004, 1)   # LIGHT, not paint: a sunlit orange pane read pale pink
    b_ = bpy.data.materials["window lit warm"].node_tree.nodes["Principled BSDF"]
    b_.inputs["Roughness"].default_value = 1.0                                   # no sky in it: glass that mirrors the dawn reads as a pale card
    for nm in ("Specular IOR Level", "Specular"):
        if nm in b_.inputs: b_.inputs[nm].default_value = 0.0
    # a LAMP inside, not an orange card (coordinator): hot and yellow low in the middle of the pane, falling to deep amber at its edges
    nt_ = bpy.data.materials["window lit warm"].node_tree; N_ = nt_.nodes.new; L_ = nt_.links.new
    tc_ = N_("ShaderNodeTexCoord"); ds_ = N_("ShaderNodeVectorMath"); ds_.operation = 'DISTANCE'; ds_.inputs[1].default_value = (0.56, 0.5, 0.36)
    L_(tc_.outputs["Generated"], ds_.inputs[0])
    mr_ = N_("ShaderNodeMapRange"); mr_.inputs[1].default_value = 0.05; mr_.inputs[2].default_value = 0.7; mr_.inputs[3].default_value = 1.0; mr_.inputs[4].default_value = 0.0
    L_(ds_.outputs["Value"], mr_.inputs[0])
    cr_ = N_("ShaderNodeValToRGB"); cr_.color_ramp.elements[0].color = (*K.lin("#A83A00"), 1); cr_.color_ramp.elements[1].color = (*K.lin("#FFC25A"), 1)
    L_(mr_.outputs[0], cr_.inputs[0]); L_(cr_.outputs[0], b_.inputs["Emission Color"])
    st_ = N_("ShaderNodeMath"); st_.operation = 'MULTIPLY_ADD'; st_.inputs[1].default_value = 3.0; st_.inputs[2].default_value = 0.7
    # a drawn sheer curtain with the lamp behind it: soft vertical folds in the glow (no flat slab, no cut-out shapes)
    sx_ = N_("ShaderNodeSeparateXYZ"); L_(tc_.outputs["Generated"], sx_.inputs[0])
    fo_ = N_("ShaderNodeMath"); fo_.operation = 'MULTIPLY'; fo_.inputs[1].default_value = 46.0; L_(sx_.outputs[0], fo_.inputs[0])
    sn_ = N_("ShaderNodeMath"); sn_.operation = 'SINE'; L_(fo_.outputs[0], sn_.inputs[0])
    fd_ = N_("ShaderNodeMath"); fd_.operation = 'MULTIPLY_ADD'; fd_.inputs[1].default_value = 0.22; fd_.inputs[2].default_value = 0.78; L_(sn_.outputs[0], fd_.inputs[0])
    sm_ = N_("ShaderNodeMath"); sm_.operation = 'MULTIPLY'; L_(st_.outputs[0], sm_.inputs[0]); L_(fd_.outputs[0], sm_.inputs[1])
    L_(mr_.outputs[0], st_.inputs[0]); L_(sm_.outputs[0], b_.inputs["Emission Strength"])
    lit.location.y -= 0.004
    lw_show([lit], t_on)
    return lit



def place_harbour_dawn():
    """THE MORNING AFTER, in one frame, bottom to top: his own house and its yard at the foot of the hill; the saved
    houses on the hill, their windows dark; three houses in a row burning from inside, black crusted lava round their
    feet; and across the hilltop behind them the earth wall, still standing."""
    rnd = lw_random.Random(61)
    ground = ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock")
    lw_grid("town hill", -26, 36, 6.6, 48, 120, 120, s5_z, ground)
    asph = ph_mat("asphalt_02", scale=2.0, tint="#7A7A7A", name="town street")
    lw_grid("house yard", -14, 36, -3.0, 6.9, 56, 20, lambda x, y: 0.0, asph)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#9A968F", name="yard kerb")
    K.box("yard kerb", (8, 6.8, 0.05), (56, 0.16, 0.12), kerb, bev=0.015)
    # HIS HOUSE: low, white tin, a blue roof; its front to us, its right-hand window and corner in frame
    home = town_house("his town house", (-1.45, 4.5, 0.0), yaw=0.0, w=3.2, d=2.6, h=1.15, storeys=1, base=0.2, pitch=9, roof="#2F5E8C", wall="#F1EEE6", seed=5)
    for o in [o for o in bpy.data.objects if o.name.startswith("his town house downpipe") and o.location.x > 0]:
        bpy.data.objects.remove(o, do_unlink=True)       # (the pipe at this corner stood where he walks in)
    iron = lw_rust("hook iron", "#2A2624")
    fy = 4.5 - 1.3                                       # the house's front wall (y)
    K.box("lantern hook plate", (S5_HOOK.x, fy - 0.012, S5_HOOK.z + 0.02), (0.07, 0.012, 0.2), iron, bev=0.003)
    K.box("lantern hook arm", (S5_HOOK.x, (fy + S5_HOOK.y) / 2 - 0.01, S5_HOOK.z + 0.05), (0.022, fy - S5_HOOK.y + 0.02, 0.022), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x, fy - 0.06, S5_HOOK.z - 0.01), (0.016, 0.14, 0.016), iron, bev=0.003).rotation_euler = (math.radians(-40), 0, 0)
    K.cyl("lantern hook", (S5_HOOK.x, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x, S5_HOOK.y - 0.012, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(math.pi / 2, 0, 0), v=8)
    town = []
    for k, (x, y, roof, wall) in enumerate(((2.2, 8.9, "#B8352B", "#E9D9A2"), (5.2, 8.5, "#3F7A4A", "#BFD3DD"), (8.3, 8.6, "#C9A23A", "#F1EEE6"),
                                            (11.5, 8.8, "#9E3A2E", "#E6E0D2"), (-4.1, 10.2, "#2E6F73", "#D9C9B4"))):
        town.append(town_house(f"town house up {k}", (x, y, s5_z(x, y - 1.4) - 0.05), yaw=rnd.uniform(-0.06, 0.06), w=2.7, d=2.6, storeys=1, base=0.3,
                               roof=roof, wall=wall, seed=30 + k))
    # THE WALL across the hilltop, behind the burning row
    wall = earth_wall("earth wall", [(x, S5_WALL_Y + 0.003 * x * x) for x in range(-22, 33, 2)], h=4.6, crest=1.4, base=8.0, seed=14)
    wall["root"].location.z = s5_z(0, S5_WALL_Y) - 0.4
    # THE LAVA that came up through the crack, inside the wall: cooled black, light only in its seams, round the three
    # houses it took
    fresh = lava_mat("lava field fresh", heat=0.8, scale=1.6, fresh=0.2)
    lw_grid("new lava field", S5_BURN_X - 6.5, S5_BURN_X + 6.5, S5_BURN_Y - 2.6, S5_BURN_Y + 4.6, 60, 28,
            lambda x, y: s5_z(x, y) + 0.28 + 0.22 * lw_fbm(x * 0.8, y * 0.8, 7) - 0.5 * max(0.0, (S5_BURN_Y - 1.9 - y)) - 0.5 * max(0.0, -5.6 - (x - S5_BURN_X)) - 0.5 * max(0.0, (x - S5_BURN_X) - 5.6), fresh)
    crust = lava_mat("lava front crust", heat=0.55, scale=7.0, fresh=0.15)
    for k in range(150):                                 # its front: a ridge of broken crust blocks below the houses
        x = S5_BURN_X + rnd.uniform(-6.0, 6.0); y = S5_BURN_Y - 2.3 + rnd.uniform(-0.3, 0.5); rr = rnd.uniform(0.14, 0.4)
        lw_block("lava front block", (x, y, s5_z(x, y) + 0.2 + rr * 0.4), rr, crust, rnd, squash=0.75)
    houses = [home] + town
    lava_rock("lava rubble", 500, (-8, 22, 7.2, S5_BURN_Y - 2.8), s5_z, seed=5, r=(0.06, 0.24), moss=0.4,
              avoid=lambda x, y: any(abs(x - h_["root"].location.x) < 1.9 and abs(y - h_["root"].location.y) < 1.8 for h_ in houses))
    lava_rock("yard grit", 90, (-3.0, 4.0, 0.6, 4.6), lambda x, y: 0.0, seed=9, r=(0.012, 0.045), moss=0.0,
              avoid=lambda x, y: (-0.8 < x < 1.0 and 2.0 < y < 3.3) or (x < -0.1 and y > 3.1))
    burning = []
    for k, x in enumerate((S5_BURN_X - 3.6, S5_BURN_X, S5_BURN_X + 3.6)):           # THREE, in a row across the frame, side by side: countable
        y = S5_BURN_Y + 0.15 * (k % 2)
        hs = town_house(f"burning house {k}", (x, y, s5_z(x, y - 1.3) + 0.35), yaw=-math.pi / 2 + rnd.uniform(-0.12, 0.12), w=2.6, d=2.6, pitch=42, roof=ROOFS[(k * 2) % len(ROOFS)],
                        wall=WALLS[(k + 1) % len(WALLS)], storeys=2, base=0.3, seed=40 + k, burn=1.0)
        hp = hs["hole"]
        hf = (4.0, 3.1, 4.6)[k]                           # RAGGED, no two alike (coordinator: "smooth candle cones"): a torn body, a thin taller tongue and a low one beside it
        lw_fire_column(f"burning house {k} blaze", (hp.x, hp.y + 0.3, hp.z - 1.2), w=2.6, h_fire=hf, h_smoke=13.0, lean=(-0.45, 0.2), t_end=DUR + 1.0,
                       seed=k * 3.7 + 1.0, fire=13.0, smoke_d=3.2, spread=0.34, rise=2.4)
        lw_fire_column(f"burning house {k} blaze tongue", (hp.x + rnd.uniform(-0.8, 0.8), hp.y + 0.1, hp.z - 1.0), w=0.9, h_fire=hf * rnd.uniform(1.1, 1.35), h_smoke=2.0, lean=(rnd.uniform(-0.5, 0.1), 0.1), t_end=DUR + 1.0,
                       seed=k * 5.1 + 2.3, fire=22.0, smoke_d=0.8, spread=0.3, rise=3.6)
        lw_fire_column(f"burning house {k} blaze low", (hp.x + rnd.uniform(-1.0, 1.0), hp.y - 0.2, hp.z - 1.6), w=1.5, h_fire=hf * 0.55, h_smoke=1.5, lean=(rnd.uniform(-0.3, 0.3), 0.1), t_end=DUR + 1.0,
                       seed=k * 2.9 + 4.1, fire=16.0, smoke_d=0.8, spread=0.36, rise=3.0)
        lw_point(f"burning house {k} blaze light", (hp.x, hp.y - 0.6, hp.z + 0.8), 1600.0, col=(1.0, 0.45, 0.15), r=0.6)
        burning.append(hs)

    def light():
        k = iceland_light(sun_elev=6, sun_az=-55, sun=3.0, sky=0.4, warm=(1.0, 0.66, 0.5), haze=1.5)      # first light: clear and pale, dim enough that one lit window reads
        ph_sky("qwantani_sunrise_puresky", strength=0.85, rot=math.radians(150))       # a REAL dawn sky (Poly Haven)
        return k
    return dict(light=light, home=home, town=town, burning=burning, wall=wall)


def shot5():
    """He comes up to his own house with the lit lantern (still 1), lifts it onto the hook by his window (still 2); it
    hangs there glowing and the window beside it lights up, the only light in the town (still 3); he turns to us and
    shrugs (still 4). Up the hill behind him, all the while: the three burning houses in a row, the wall behind them."""
    T_IN = 1.15; T_HANG = 0.34 * DUR; T_LET = T_HANG + 0.22
    T_WIN = 0.55 * DUR; T_TURN = 0.695 * DUR; T_ASK = T_TURN + 0.52
    W = lw_win
    P = place_harbour_dawn()
    light = P["light"]
    data = load_data()
    R = math.radians
    HOOKED = S5_HOOK + Vector((0, 0, 0.005))
    # he stands in PROFILE along his house's front, a little toward us, the hook straight ahead of his wall-side hand
    data.place(0.0, 0.0, 0.0); sc.frame_set(1); bpy.context.view_layer.update()
    f0 = data.forward(); YAW_H = math.degrees(math.atan2(-0.6, -0.8) - math.atan2(f0.y, f0.x))
    data.place(0.0, 0.0, YAW_H); bpy.context.view_layer.update()
    fw = data.forward(); fw.z = 0; fw.normalize()
    near = sorted("LR", key=lambda s_: acts._shoulder(data, s_).y)               # near[0]: the hand toward the lens
    carry, other = near[1], near[0]                                              # the wall-side hand carries it: the hook is dead ahead of it
    sh0 = acts._shoulder(data, carry) - Vector(data.arm.location)
    TOES = 0.012
    UPH = HOOKED.z - TOES - sh0.z
    FWD = math.sqrt(max(0.06 ** 2, 0.165 ** 2 - UPH ** 2))
    STAND = HOOKED - sh0 - fw * FWD; STAND.z = 0.0
    START = STAND + Vector((0.22, -0.1, 0.0)); MID = STAND - fw * 0.12
    print("S5 GEOM fw", tuple(round(v, 3) for v in fw), "sh0", tuple(round(v, 3) for v in sh0), "UPH", round(UPH, 3), "FWD", round(FWD, 3), "STAND", tuple(round(v, 3) for v in STAND),
          "windows", [tuple(round(v, 2) for v in w_.matrix_world.translation) for w_ in P["home"]["windows"]],
          "pipes", [tuple(round(v, 2) for v in o.matrix_world.translation) for o in bpy.data.objects if "his town house downpipe" in o.name], flush=True)
    data.place(START.x, START.y, YAW_H - 61.0)                                   # already facing the way he walks in
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.0, T_IN, step=0.11, lift=0.03, bob=0.012)      # two steps with a stop between: both feet flat on the board's first still                                  # he WALKS up to his house (real steps)
    YAW0 = math.radians(YAW_H)
    sc.frame_set(F(T_IN)); YW = data.arm.rotation_euler.z                       # the facing his walk ends on
    while YW - YAW0 > math.pi: YW -= 2 * math.pi
    while YW - YAW0 < -math.pi: YW += 2 * math.pi
    def body(t):
        p = STAND.copy()
        p.z += TOES * W(t, T_HANG - 0.35, 0.3) * (1 - W(t, T_LET + 0.02, 0.2))                   # up on his toes to the hook
        back = W(t, T_LET + 0.05, 0.35)
        p += Vector((0.17, -0.12, 0.0)) * back                                                                   # a step back from it, to look
        p.z += 0.05 * lw_kick(t - T_WIN - 0.1, 0.2); p += Vector((-0.06, 0.05, 0.0)) * W(t, T_WIN + 0.05, 0.3)   # a start, and half a step in toward the warm glass                                               # a start as the window lights
        turn = W(t, T_TURN, 0.42)
        p += Vector((0.05, -0.05, 0.0)) * turn; p.z += 0.03 * math.sin(math.pi * turn)             # a step round to us
        st = W(t, T_ASK - 0.45, 0.4); p += Vector((0.0, -0.03, 0.0)) * st     # a step along the yard toward us
        p.z += 0.045 * lw_kick(t - T_ASK - 0.25, 0.22)                                            # the shrug
        return p, YW + (YAW0 - YW) * W(t, T_IN, 0.4) - R(6) * back - R(0) * W(t, T_WIN, 0.3) * (1 - turn) - R(24) * turn      # hips stay three-quarter to his window: only head and shoulders come round to us
    for f in range(F(T_IN) + 1, NF + 16):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (6 * W(t, T_WIN, 0.3) * (1 - W(t, T_TURN, 0.3)) + 0 * W(t, T_TURN + 0.02, 0.28) * (1 - W(t, T_ASK - 0.12, 0.28)) - 6 * W(t, T_ASK, 0.3), 0, 0), T_LET + 0.3, DUR + 0.4)
    # ---- face and head (BEFORE the hands: a face moves his chest and shoulders)
    wy = P["home"]["windows"][1].matrix_world.translation.copy()
    CAM0 = Vector((-1.6, 0.5, 0.5)); LOOK0 = CAM0 + Vector((5.9, 8.1, 1.9))
    data.look_at(STAND + Vector((-0.7, -0.6, 0.45)), 0.0, max_yaw=50, max_pitch=40, blend=0.0)
    data.look_at(S5_HOOK, T_IN - 0.45, max_yaw=50, max_pitch=40, blend=0.55)
    data.look_at(wy, T_WIN + 0.05, max_yaw=44, max_pitch=20, blend=0.45)                          # the window, as it lights
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_TURN + 0.05, max_yaw=60, max_pitch=30, blend=0.3)  # to us: would you?
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_ASK - 0.1, max_yaw=60, max_pitch=30, blend=0.2)
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_ASK + 0.2, max_yaw=60, max_pitch=30, blend=0.2)
    data.expression("sad", 0.0, T_WIN, blend=0.25)
    data.expression("worried", T_WIN, T_ASK - 0.1, blend=0.3)                                   # a soft, tired look at it (coordinator: not a smile while three houses burn)
    data.expression("wry", T_ASK - 0.1, DUR + 1.0, blend=0.25)
    # ---- the lantern: carried in front of him in his wall-side hand, lifted onto the hook, let go; it swings
    lan = s5_lantern()
    carry_fn = lw_hand(data, carry, [(0.0, (0.12, 0.0, -0.14)), (0.45, (0.12, 0.0, -0.14)), (0.85, (0.18, 0.02, -0.01)), (T_IN, (0.14, 0.0, -0.1)), (T_IN + 0.3, (0.1, 0.02, -0.08)), (DUR, (0.1, 0.02, -0.08))])
    down_fn = lw_hand(data, carry, [(T_LET, (0.12, 0.02, -0.08)), (T_LET + 0.42, (0.05, 0.04, -0.16)), (DUR, (0.05, 0.04, -0.16))])
    def carry_path(t):                                       # ONE job for the lantern hand: held up to light his way, a dip, the lift onto the hook, hold it there, and down
        if t < T_HANG: return carry_fn(min(t, T_IN + 0.3)).lerp(HOOKED, W(t, T_IN + 0.3, T_HANG - T_IN - 0.3))
        if t <= T_LET: return HOOKED.copy()
        return HOOKED.lerp(down_fn(t), W(t, T_LET, 0.42))
    data.reach(carry, carry_path, 0.0, T_LET + 0.45, lead=0.05, back=None, elbow_out=0.35)
    def swing(t):                                           # after the let-go: a damped swing about the hook
        s_ = t - T_LET
        return 0.0 if s_ <= 0 else math.radians(20) * math.exp(-s_ / 2.2) * math.sin(2 * math.pi * s_ / 0.9)
    # ---- his hands after it: a start at the lit window (both hands up, open), then the shrug to us
    for sd, sg in (("L", -1), ("R", 1)):                   # the shrug big enough for a phone: both arms out from his sides, palms up
        LG = 0.38                                     # measured: these FK keys land 0.4 s after the time they are given here (the reach's bake), so they are given early
        if sd == carry:                               # a hand out toward the warm glass as it lights, then down
            data._k(f"arm.{sd}", T_WIN + 0.05 - LG, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", T_WIN + 0.05 - LG, rot=(-38, 0, -sg * 16))
            data._k(f"arm.{sd}", T_WIN + 0.3 - LG, rot=(-10, 0, -sg * 68)); data._k(f"fore.{sd}", T_WIN + 0.3 - LG, rot=(-28, 0, -sg * 22))
            data._k(f"arm.{sd}", T_TURN - 0.05 - LG, rot=(-10, 0, -sg * 68)); data._k(f"fore.{sd}", T_TURN - 0.05 - LG, rot=(-28, 0, -sg * 22))
        else:
            for t_ in (T_LET + 0.5, T_TURN - 0.05 - LG): data._k(f"arm.{sd}", t_, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", t_, rot=(-38, 0, -sg * 16))
        data._k(f"arm.{sd}", T_TURN + 0.3 - LG, rot=(-58, 0, -sg * 6)); data._k(f"fore.{sd}", T_TURN + 0.3 - LG, rot=(-38, 0, sg * 18))   # his hands come together at his chest, then open into the shrug
        data._k(f"arm.{sd}", T_ASK - 0.1, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", T_ASK - 0.1, rot=(-38, 0, -sg * 16))   # his hands open low...
        data._k(f"arm.{sd}", DUR - 0.2, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", DUR - 0.2, rot=(-38, 0, -sg * 16))    # (his hands fall as the shot cuts)
        for t_ in (T_ASK + 0.45, DUR - 0.5):
            data._k(f"arm.{sd}", t_, rot=(-8, 0, -sg * 12)); data._k(f"fore.{sd}", t_, rot=(-100, 0, -sg * 14))   # ...and out into the shrug: elbows bent, hands low (small, not arms flung wide)
    data.finish()
    for f in range(1, NF + 16):
        t = (f - 1) / FPS
        if t <= T_LET:
            sc.frame_set(f); bpy.context.view_layer.update()
            hp_ = data.arm.matrix_world @ data.pb[f"hand.{carry}"].tail + Vector((0, 0, -0.02))
            lan.location = hp_.lerp(S5_HOOK, W(t, T_HANG - 0.12, 0.12))
            lan.rotation_euler = (0, math.radians(6) * math.sin(2 * math.pi * t / 0.6) * (1 - W(t, T_IN, 0.3)), 0)
        else:
            lan.location = S5_HOOK; lan.rotation_euler = (0, swing(t), 0)
        lan.keyframe_insert("location", frame=f); lan.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: wide and low in his yard, tipped up the hill: him and his window at the bottom, the saved houses
    # over his roof, the burning row and the wall at the top
    LENS_MM = 20.0
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=LENS_MM, fstop=11.0)
    C1, L1 = compose.frame_data(data, CAM0, LOOK0, LENS_MM, face_at=(0.38, 0.53), height=0.42, t=T_HANG)
    push = lambda t: Vector((0.0, 0.0, 0.0))
    lw_cut(cam, lambda t: (C1 + push(t), L1, data.pos() + Vector((0, 0, 0.6))), lambda t: (C1, L1, data.pos()), -1.0, -1.0, LENS_MM, LENS_MM)
    # ---- the payoff: his one window lights
    lit = [s5_lit_pane(P["home"], 1, T_WIN)]
    glow = lw_point("window spill", (wy.x + 0.1, wy.y - 0.4, wy.z - 0.35), 42.0, col=(1.0, 0.5, 0.15), r=0.3)
    lw_show([glow], T_WIN)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern hook"), cutaway=None,
                boxes=[],
                conseq=[("three houses burn in a row up the hill", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook by his window and it swings, glowing", lambda: meshes([lan]), T_IN, DUR, {"whole": False, "moves": True}),
                        ("the one window beside it lights up", lambda: meshes(lit), T_WIN, DUR, {"whole": False})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
