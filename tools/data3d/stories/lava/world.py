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
