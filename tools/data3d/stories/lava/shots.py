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


def lw_emit(name, hexc, strength):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(hexc), 1); bs.inputs["Emission Color"].default_value = (*K.lin(hexc), 1)
    bs.inputs["Emission Strength"].default_value = strength
    return m


def lw_metal(name, hexc, rough=0.35):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(hexc), 1); bs.inputs["Metallic"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough * 0.7; rr.inputs["To Max"].default_value = rough * 1.3
    nt.links.new(nz.outputs["Fac"], rr.inputs["Value"]); nt.links.new(rr.outputs["Result"], bs.inputs["Roughness"])
    return m


def lw_paint(name, hexc, rough=0.45):
    """painted metal or wood: the colour with a faint mottle so a big face never reads as a flat card"""
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
    rr = nt.nodes.new("ShaderNodeValToRGB"); rr.color_ramp.elements[0].color = (*K.lin("#1E1A17"), 1); rr.color_ramp.elements[1].color = (*K.lin("#4C433B"), 1)
    nt.links.new(rock.outputs["Fac"], rr.inputs["Fac"])
    mr = nt.nodes.new("ShaderNodeValToRGB"); mr.color_ramp.elements[0].position = 0.3; mr.color_ramp.elements[1].position = 0.75
    mr.color_ramp.elements[0].color = (0.75, 0.75, 0.75, 1); mr.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(moss.outputs["Distance"], mr.inputs["Fac"])
    mc = nt.nodes.new("ShaderNodeValToRGB"); mc.color_ramp.elements[0].color = (*K.lin("#5C6440"), 1); mc.color_ramp.elements[1].color = (*K.lin("#8C9468"), 1)
    nt.links.new(warp.outputs["Fac"], mc.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB"); nt.links.new(mr.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(rr.outputs["Color"], mix.inputs["Color1"]); nt.links.new(mc.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.8; bp.inputs["Distance"].default_value = 0.05
    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 40; fine.inputs["Detail"].default_value = 12
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"]); nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def lava_rock(name, n, area, zfn, seed=0, r=(0.05, 0.25), avoid=None):
    """loose lava boulders and moss tufts strewn over a patch of ground (x0, x1, y0, y1)"""
    rnd = lw_random.Random(seed)
    m = lw_noise("loose lava rock", "#1C1916", "#4A4038", scale=12, rough=0.95, bump=0.9, detail=10)
    mo = lw_noise("moss tuft", "#5E6842", "#8E9868", scale=30, rough=1.0, bump=0.6)
    out = []
    for k in range(n):
        x = rnd.uniform(area[0], area[1]); y = rnd.uniform(area[2], area[3]); rr = rnd.uniform(*r)
        if avoid and avoid(x, y): continue
        o = K.sph(name, (x, y, zfn(x, y) + rr * 0.3), rr, m if rnd.random() < 0.7 else mo, scale=(1.0, rnd.uniform(0.7, 1.2), rnd.uniform(0.45, 0.8)), seg=10, ring=6)
        o.rotation_euler = (0, 0, rnd.uniform(0, 6.3)); out.append(o)
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
    big = nt.nodes.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = scale * 0.35; nt.links.new(mp.outputs["Vector"], big.inputs["Vector"])
    hot = nt.nodes.new("ShaderNodeMapRange"); hot.inputs["From Min"].default_value = 0.5 - 0.15 * fresh; hot.inputs["From Max"].default_value = 0.75 - 0.1 * fresh
    hot.inputs["To Max"].default_value = 0.35 + 0.5 * fresh
    nt.links.new(big.outputs["Fac"], hot.inputs["Value"])
    glowf = nt.nodes.new("ShaderNodeMath"); glowf.operation = 'MAXIMUM'
    nt.links.new(crack.outputs["Result"], glowf.inputs[0]); nt.links.new(hot.outputs["Result"], glowf.inputs[1])
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
    es = nt.nodes.new("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "lava heat"; es.inputs[1].default_value = 2.2 * heat
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
    m = lw_noise("wall rock", "#2A2522", "#5A4E44", scale=7, rough=0.95, bump=1.0, detail=8)
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
    for k in range(int(len(pts) * 6)):
        i = rnd.randrange(len(pts) - 1); u = rnd.random()
        p = pts[i].lerp(pts[i + 1], u); tg = (pts[i + 1] - pts[i]).normalized(); nrm = Vector((-tg.y, tg.x, 0))
        side = rnd.choice((-1, 1)); fz = rnd.uniform(0.05, 0.85)
        off = (crest / 2 + (base / 2 - crest / 2) * (1 - fz)) * side
        r = rnd.uniform(0.08, 0.22)
        b = K.sph(name + " boulder", tuple(p + nrm * off + Vector((0, 0, h * fz))), r, m, scale=(1.0, rnd.uniform(0.7, 1.1), rnd.uniform(0.6, 0.9)), seg=10, ring=6, parent=root)
        b.rotation_euler = (rnd.random(), rnd.random(), rnd.random())
    return dict(root=root, body=body, path=pts, h=h)


# ---------------------------------------------------------------- the town's houses
ROOFS = ("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A", "#7A3E5E", "#2E6F73", "#A8442A")
WALLS = ("#F1EEE6", "#E6E0D2", "#DCE3E2", "#EDE4C8", "#D9D6CC")


def town_house(name, loc, yaw=0.0, w=2.0, d=1.6, h=1.25, roof="#B8352B", wall="#F1EEE6", lit=(), dark_glass=True, seed=0):
    """a low Grindavik house, at the world's scale (a storey ~1.3): corrugated-clad walls in white or pale paint, a
    pitched tin roof in a strong colour with deep eaves, a white door, four-pane windows. Built facing -Y (its front)
    about its own origin, placed at loc/yaw. lit: indices of windows whose panes glow warm (a window someone is home
    behind). Returns dict(root, windows=[pane objects], door)."""
    root = K.empty(name, (0, 0, 0))
    cl = lw_noise(f"cladding {wall}", wall, K.mute(wall, 0.85), scale=2.0, rough=0.6, bump=0.25, stretch=(30, 30, 1), lo=0.2, hi=0.8)
    K.box(name + " walls", (0, 0, h / 2), (w, d, h), cl, bev=0.01, parent=root)
    K.box(name + " plinth", (0, 0, 0.05), (w + 0.04, d + 0.04, 0.1), lw_noise("plinth concrete", "#8C8A86", "#A9A6A0", scale=12, rough=0.9), bev=0.005, parent=root)
    rm = lw_noise(f"tin roof {roof}", roof, K.mute(roof, 0.7), scale=1.5, rough=0.45, bump=0.35, stretch=(40, 1, 1), lo=0.3, hi=0.8)
    pitch = math.radians(28); ov = 0.18
    half = (d / 2 + ov) / math.cos(pitch)
    for sg in (-1, 1):
        r = K.box(name + " roof", (0, sg * (d / 2 + ov) / 2, h + math.tan(pitch) * (d / 2 + ov) / 2 - 0.01), (w + 2 * ov, half, 0.04), rm, bev=0.005, parent=root)
        r.rotation_euler = (-sg * pitch, 0, 0)
    gab = math.tan(pitch) * d / 2
    for sx in (-1, 1):                                   # the gable ends: a triangle of cladding
        bm = LW_bmesh.new()
        a = bm.verts.new((sx * w / 2, -d / 2, h)); b = bm.verts.new((sx * w / 2, d / 2, h)); c = bm.verts.new((sx * w / 2, 0, h + gab))
        bm.faces.new((a, b, c)); me = bpy.data.meshes.new(name + " gable"); bm.to_mesh(me); bm.free(); me.materials.append(cl)
        g = lw_link(bpy.data.objects.new(name + " gable", me)); g.parent = root
        so = g.modifiers.new("t", 'SOLIDIFY'); so.thickness = 0.02
    trim = K.mat("house trim", "#F7F5EF", rough=0.5)
    K.box(name + " door", (-w * 0.3, -d / 2 - 0.012, 0.5), (0.36, 0.03, 0.82), K.mat("house door", "#EDEBE4", rough=0.45), bev=0.008, parent=root)
    K.cyl(name + " door knob", (-w * 0.3 + 0.12, -d / 2 - 0.035, 0.48), 0.018, 0.02, lw_metal("knob brass", "#B8903A"), rot=(math.pi / 2, 0, 0), parent=root)
    xs = [-w * 0.3 + 0.55, w * 0.25] if w > 1.6 else [w * 0.2]
    windows = []
    for k, x in enumerate(xs):
        on = k in lit
        glass = lw_emit("window lit", "#FFC070", 2.5) if on else K.mat("window glass", "#2B3238" if dark_glass else "#7E8C96", rough=0.08, metal=0.2)
        K.box(name + " window frame", (x, -d / 2 - 0.01, 0.72), (0.5, 0.03, 0.46), trim, bev=0.006, parent=root)
        p = K.box(name + " window pane", (x, -d / 2 - 0.026, 0.72), (0.42, 0.01, 0.38), glass, bev=0.0, parent=root)
        K.box(name + " window bar", (x, -d / 2 - 0.033, 0.72), (0.025, 0.01, 0.38), trim, bev=0.0, parent=root)
        K.box(name + " window bar", (x, -d / 2 - 0.033, 0.72), (0.42, 0.01, 0.025), trim, bev=0.0, parent=root)
        windows.append(p)
    K.box(name + " chimney", (w * 0.28, 0.2, h + gab * 0.8), (0.16, 0.16, 0.4), lw_noise("chimney render", "#BDB8AE", "#9C968C", scale=10), bev=0.01, parent=root)
    lw_local(root)
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    return dict(root=root, windows=windows, w=w, d=d, h=h)


# ---------------------------------------------------------------- the hard hat and the hi-vis vest
LW_HAT_ZB = 0.80


def lw_head_z(x, y):
    q = 1 - (x / 0.186) ** 2 - (y / 0.138) ** 2
    return 0.705 + 0.172 * math.sqrt(q) if q > 0 else -1.0


def lw_hat_mesh(to_world, ears):
    """a hard hat built ON his head (his rest frame, facing -Y): a domed shell with a raised ridge down its middle, a
    short rim all round and a peak at the front, cut round his ears"""
    from mathutils import Vector as V
    A = (0.168, 0.136); H = 0.12; n = 64
    verts, faces, rows = [], [], []
    rhos = [0.0, 0.1, 0.22, 0.35, 0.48, 0.6, 0.72, 0.82, 0.9, 0.95, 0.985, 1.0]
    for rho in rhos:
        row = []
        for i in range(n if rho > 0 else 1):
            th = 2 * math.pi * i / n; x, y = A[0] * rho * math.cos(th), A[1] * rho * math.sin(th)
            z = LW_HAT_ZB + H * math.sqrt(max(0.0, 1 - rho ** 2.4)) + 0.012 * math.exp(-(x / 0.03) ** 2) * (1 - rho ** 4)
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


# ====================================================================================================
# shot1.py
# ====================================================================================================
"""BEAT 1, THE HOOK: "A volcano has erupted nine times beside one town in Iceland, and the whole town had to run."

Grindavik's main street on a bright grey afternoon, low houses with coloured tin roofs down both sides, the ridge above
the town at the end of it. The ridge rips open and a curtain of lava fountains bursts up along it under a boiling
plume. The digger driver, at the striped road gate at the town's edge, winds the gate's crank hand over hand and the
striped arm swings up high over the road; the town's cars pour out under it, headlights on, past him and
out of the frame; he waves them on; the fountains surge; the street is empty and he runs after them."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the gate arm's pivot, on its post at the kerb
S1_ARM = 2.2                           # the arm, out across the road (toward -X)
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge


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
    tyre = K.mat("car tyre", "#141414", rough=0.8)
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


def s1_gate():
    """the striped road gate at the town's edge: a steel post with its winch housing on top and the arm on its pivot (red
    and white bands); the crank that winds it is built beside his hands by s1_crank"""
    post_m = lw_metal("gate steel", "#8C9196")
    K.box("gate post", (S1_PIV.x, S1_PIV.y + 0.12, 0.25), (0.14, 0.14, 0.5), lw_paint("gate housing", "#E8E4DA"), bev=0.015)
    K.box("gate foot", (S1_PIV.x, S1_PIV.y + 0.12, 0.02), (0.26, 0.26, 0.04), post_m, bev=0.005)
    pv = K.empty("gate pivot", tuple(S1_PIV))
    red, white = K.mat("gate red", "#C8231B", rough=0.4), K.mat("gate white", "#F4F1EA", rough=0.4)
    n = 10
    for k in range(n):
        seg = S1_ARM / n
        K.box("gate arm", (S1_PIV.x - seg * (k + 0.5) - 0.03, S1_PIV.y, S1_PIV.z), (seg, 0.06, 0.08), red if k % 2 == 0 else white, bev=0.008, parent=pv)
    K.box("gate stop", (S1_PIV.x - S1_ARM + 0.05, S1_PIV.y, 0.23), (0.06, 0.06, 0.46), post_m, bev=0.01)
    return pv


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
    K.cyl("gate crank knob", (S1_CRANK_R, 0.04, 0), 0.016, 0.07, K.mat("gate handle", "#22201E", rough=0.5), rot=(math.pi / 2, 0, 0), v=14, parent=wh)
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
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, lava_field_mat())
    K.box("street asphalt", (0, 2.5, 0.004), (4.0, 20, 0.01), lw_asphalt(), bev=0)
    kerb = lw_noise("kerb concrete", "#A6A39C", "#C2BFB6", scale=14, rough=0.8)
    for sx in (-1, 1):
        K.box("kerb", (sx * 2.05, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 2.55, 2.5, 0.035), (0.9, 20, 0.07), lw_noise("pavement", "#8E8C88", "#A8A59F", scale=8, rough=0.85), bev=0.005)
    for y in range(-8, 10, 2):
        K.box("centre line", (0, y + 0.5, 0.011), (0.08, 0.9, 0.004), K.mat("road paint", "#E9E4D4", rough=0.6), bev=0)
    houses = []
    for sx in (-1, 1):
        y = 0.9 if sx < 0 else 1.4
        k = 0
        while y < 8.0:
            w = rnd.uniform(1.9, 2.4); d = rnd.uniform(1.5, 1.8)
            hs = town_house(f"town house {sx}_{k}", (sx * (3.3 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            h=rnd.uniform(1.2, 1.45), roof=ROOFS[(k * 3 + (sx > 0)) % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=k)
            houses.append(hs); y += w + rnd.uniform(0.5, 0.9); k += 1
    lava_rock("lava field rock", 160, (-14, 14, -6, 14), s1_ground_z, seed=3, avoid=lambda x, y: abs(x) < 3.2 and y < 9.0)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a glowing line along the ridge, the curtain of fountains on it, the plume over it
    fz = s1_ground_z(0, S1_RIDGE_Y)
    K.box("fissure glow", (0, S1_RIDGE_Y, fz - 0.1), (44, 0.6, 0.3), lw_emit("fissure line", "#FF5000", 1.4), bev=0)
    fm = s1_fountain_mat(); founts = []
    for k in range(9):                                     # NINE vents, one for each eruption: they burst open one after another
        x = -14.4 + k * 3.6 + rnd.uniform(-0.25, 0.25)
        o = K.sph(f"fissure fountain {k}", (x, S1_RIDGE_Y, s1_ground_z(x, S1_RIDGE_Y) - 0.3), 1.0, fm, scale=(0.9, 0.4, 1.0), seg=20, ring=14)
        dm = o.modifiers.new("ragged", 'DISPLACE'); tx = bpy.data.textures.new(f"ragged {k}", 'CLOUDS'); tx.noise_scale = 0.35; dm.texture = tx; dm.strength = 0.35
        founts.append(o)
    spm = lw_emit("lava spatter", "#FF6000", 1.2)
    spat = [K.sph(f"fissure spatter {k}", (0, S1_RIDGE_Y, fz), rnd.uniform(0.05, 0.1), spm, seg=8, ring=6) for k in range(30)]
    ash = lw_smoke_mat("eruption plume", density=2.5, col=(0.34, 0.33, 0.34))
    puffs = []
    for k in range(16):
        x = -20 + k * 2.7 + rnd.uniform(-1, 1)
        puffs.append(lw_puff(f"eruption plume {k}", (x, S1_RIDGE_Y + 3.0 + rnd.uniform(0, 3), fz + 7 + rnd.uniform(0, 6)), rnd.uniform(3.5, 5.0), ash, scale=(1.3, 1.0, 0.9)))
    gate = s1_gate()
    glow = [lw_point(f"fissure light {k}", (x, S1_RIDGE_Y - 1.5, fz + 3.5), 0.0, col=(1.0, 0.4, 0.1), r=2.0) for k, x in enumerate((-12, -4, 4, 12))]
    plume_lit = [lw_point(f"plume underlight {k}", (x, S1_RIDGE_Y + 2.0, fz + 6.0), 0.0, col=(1.0, 0.35, 0.08), r=3.0) for k, x in enumerate((-9, 0, 9))]
    town_glow = lw_area("eruption glow on the town", (0, 12, 7), (0, 0, 0.5), 0.0, 14, col=(1.0, 0.5, 0.2))

    def light():
        return iceland_light(sun_elev=18, sun_az=-45, sun=3.0, sky=0.35, haze=1.5)
    return dict(light=light, founts=founts, spat=spat, puffs=puffs, gate=gate, glow=glow + plume_lit, town_glow=town_glow, houses=houses, fz=fz)


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
    T_NINE = 0.2                                           # one vent bursts every T_NINE seconds: all nine by T_ERUPT + 1.6
    order = [4, 3, 5, 2, 6, 1, 7, 0, 8]                    # the rip runs out from the middle of the ridge both ways
    order = {v: i for i, v in enumerate(order)}
    for k, o in enumerate(P["founts"]):
        base = o.location.z; ph = rnd.uniform(0, 6.28); hz = rnd.uniform(0.8, 1.4); hk = rnd.uniform(0.75, 1.25)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            tk = T_ERUPT + T_NINE * order[k]                 # this vent's own burst: nine pops, counted off along the ridge
            up = W(t, tk, 0.18)
            h = hk * up * (3.0 + 0.6 * math.sin(2 * math.pi * hz * t + ph) + 2.0 * W(t, T_SURGE, 0.5) + 2.2 * lw_kick(t - tk, 0.22))
            o.scale = (0.5 + 0.3 * up, 0.35, max(0.001, h)); o.location.z = base + 0.5 * h
            o.hide_render = up < 0.02; o.keyframe_insert("hide_render", frame=f)
            o.keyframe_insert("scale", frame=f); o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["spat"]):
        v = P["founts"][k % 9]; x0 = v.location.x + rnd.uniform(-0.5, 0.5); tk = T_ERUPT + T_NINE * order[k % 9]
        vx = rnd.uniform(-1.5, 1.5); vz = rnd.uniform(5.0, 8.5); per = 2 * vz / 9.8; ph = rnd.uniform(0, per)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < tk: o.location = (x0, S1_RIDGE_Y, P["fz"] - 1.0)
            else:
                u = (t - tk) % per
                o.location = (x0 + vx * u, S1_RIDGE_Y - 0.3 * u, P["fz"] + vz * u - 4.9 * u * u)
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["puffs"]):
        z0 = o.location.z
        for f in range(1, NF + 1, 3):
            t = (f - 1) / FPS; s = 0.02 + 0.98 * W(t, T_ERUPT + 0.1 + 0.04 * k, 1.6)
            lw_puff_key(o, f, (1.3 * s, 1.0 * s, 0.9 * s)); o.location.z = z0 - 6.0 * (1 - s) + 0.5 * t
            o.keyframe_insert("location", frame=f)
    for L in P["glow"]:
        e0 = 1200.0 if 'plume' in L.name else 7000.0
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = e0 * W(t, T_ERUPT, 0.3) * (1 + 0.6 * W(t, T_SURGE, 0.5)); L.data.keyframe_insert("energy", frame=f)
    tg = P["town_glow"].data
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; tg.energy = 300.0 * W(t, T_ERUPT, 0.3) * (1 + 0.5 * W(t, T_SURGE, 0.5)); tg.keyframe_insert("energy", frame=f)
    # ---- the cars: one after another down the lane, under the raised arm, toward us and out of the frame
    cars = []
    for k, col in enumerate(("#B9C2C9", "#2D5A8E", "#C33A2A", "#E6E2D6", "#3B3F45")):
        c = s1_car(f"town car {k}", col); cars.append(c)
        y0 = 4.0 + 2.9 * k; v = 7.5
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
        p.z -= 0.045 * cr * (1 + math.sin(2 * math.pi * REVS * crank_u(t)))
        yaw = math.radians(-30) * W(t, T_ERUPT - 0.05, 0.3) * (1 - W(t, T_GRAB - 0.35, 0.3)) \
            + math.radians(13) * cr * math.sin(2 * math.pi * REVS * crank_u(t) + 1.2) \
            - math.radians(30) * W(t, T_WAVE0, 0.4) * (1 - W(t, T_GO - 0.95, 0.9)) + math.radians(50) * W(t, T_GO - 0.95, 0.9)
        return p, yaw
        return p, yaw
    for f in range(1, NF + 1):                             # at the end he turns after the cars, leaning into the run
        t = (f - 1) / FPS; p, yaw = body(t); p.z += 0.03 * lw_kick(t - T_GO, 0.15); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (-12 * lw_kick(t - T_ERUPT - 0.05, 0.2) + (8 + 11 * math.sin(2 * math.pi * REVS * crank_u(t))) * W(t, T_GRAB, 0.3) * (1 - W(t, T_LET, 0.3))
                                       - 10 * lw_kick(t - T_SURGE, 0.25) + 16 * W(t, T_GO - 0.2, 0.45), 0,
                                       8 * math.sin(2 * math.pi * (t - T_WAVE0) / 1.0) * W(t, T_WAVE0, 0.3) * (1 - W(t, T_WAVE1, 0.3))), 0, DUR + 0.4)
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
    # ---- the gate: down until he winds it; each turn of the crank lifts it, and it stays up
    gate = P["gate"]
    ang = lambda t: math.radians(68) * crank_u(t)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; gate.rotation_euler = (0, ang(t), 0); gate.keyframe_insert("rotation_euler", frame=f)
    data.reach(wind, knob, T_GRAB, T_LET, lead=0.45, back=None, elbow_out=0.4)
    RK = [(T_LET + 0.55, (0.08, 0.08, -0.09)), (T_GO - 0.2, (0.08, 0.06, -0.1)), (DUR + 0.4, (0.09, 0.03, -0.12))]
    data.reach(wind, lw_hand(data, wind, RK), RK[0][0], DUR + 0.3, lead=0.55, back=None, elbow_out=0.4)
    WK = [(T_LET + 0.4, (0.08, 0.12, 0.0))]
    t = T_WAVE0 + 0.5; k = 0
    while t < T_WAVE1 - 0.2:
        WK.append((t, (0.07, 0.15, 0.08) if k % 2 == 0 else (0.11, 0.07, 0.03))); t += 0.45; k += 1
    WK += [(max(T_SURGE + 0.1, WK[-1][0] + 0.35), (0.06, 0.1, 0.06)), (DUR + 0.4, (0.04, 0.09, -0.1))]
    WK = sorted({round(a, 3): b for a, b in WK}.items())
    data.reach(other, lw_hand(data, other, WK), WK[0][0], DUR + 0.3, lead=0.4, back=None, elbow_out=0.35)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((3.2, -3.6, 0.8))
    data.look_at(LENS, 0.0, max_yaw=40, blend=0.0)
    data.look_at(Vector((-3.0, S1_RIDGE_Y, 7.0)), T_ERUPT + 0.05, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(HUB, T_GRAB - 0.3, max_yaw=50, max_pitch=50, blend=0.3)
    data.look_at(Vector((-1.5, 5.0, 2.5)), T_UP0 + 0.6, max_yaw=55, max_pitch=40, blend=0.3)
    data.look_at(Vector((S1_LANE, -1.0, 0.7)), T_LET, max_yaw=55, blend=0.3)
    data.look_at(Vector((-2.0, S1_RIDGE_Y, 8.0)), T_SURGE, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((S1_LANE, -4.0, 0.7)), T_GO - 0.1, max_yaw=50, blend=0.3)
    data.expression("alarmed", T_ERUPT, T_GRAB - 0.05, blend=0.15)
    data.expression("determined", T_GRAB, T_SURGE - 0.1, blend=0.2)
    data.expression("worried", T_SURGE, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low, three-quarter from the road side of the gate, the street and the ridge behind him
    CAM = Vector((2.3, -3.8, 1.35)); LOOK = Vector((-0.4, 8.0, 1.9))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 18.0, face_at=(0.64, 0.4), height=0.36, t=0.45 * DUR)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=18.0, fstop=11.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.1, 0.2, 0.0)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))))
    founts = P["founts"]
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=("gate crank", "gate winch housing"),
                boxes=[],
                conseq=[("the ridge rips open and a curtain of lava fountains bursts up over the town", lambda: founts, T_ERUPT, DUR, {"whole": False}),
                        ("he winds the crank and the striped gate arm swings up over the road", lambda: lw_drawn("gate arm", "gate post", "gate stop"), T_UP0 + 0.3, T_UP1 + 0.4, {"whole": False, "moves": True}),
                        ("the town's cars pour out under the raised gate, past him", lambda: meshes(cars), T_CARS + 0.3, T_WAVE1, {"whole": False})])


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
S2_DIG = Vector((-2.4, 1.45, 0.0))      # the digger, beside and behind him, facing +Y (the wall)
S2_WALL_Y = 7.0                        # the wall's crest centre line (it runs along X)
S2_WALL_H = 4.4
S2_BASE = 8.5
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


def s2_remote(data):
    """the digger's remote control pack: a yellow box on his chest strap with two black sticks on its top, carried on
    his chest bone. Returns (box, [(stick pivot, knob)])."""
    sc.frame_set(1); bpy.context.view_layer.update()
    sh = [acts._shoulder(data, s_) for s_ in "LR"]; mid = (sh[0] + sh[1]) / 2
    fw = data.forward()
    c = mid + fw * 0.165 + Vector((0, 0, -0.15))
    yaw = data.arm.rotation_euler.z
    root = K.empty("remote control", tuple(c))
    yel = lw_paint("remote yellow", "#F2B10E", rough=0.4); dark = K.mat("remote black", "#1A1A1A", rough=0.5)
    K.box("remote control box", (0, 0, 0), (0.2, 0.09, 0.05), yel, bev=0.012, parent=root)
    K.box("remote control screen", (0, -0.035, 0.026), (0.07, 0.012, 0.004), lw_emit("remote screen", "#7FE0FF", 4.0), bev=0.0, parent=root)
    sticks = []
    for sx in (-0.06, 0.06):
        pv = K.empty("remote stick pivot", (sx, 0.0, 0.025), parent=root)
        K.cyl("remote stick", (0, 0.0, 0.03), 0.008, 0.06, dark, parent=pv)
        kn = K.sph("remote stick knob", (0, 0.0, 0.065), 0.018, dark, parent=pv)
        sticks.append((pv, kn))
    lw_local(root)
    root.rotation_euler = (0, 0, yaw)
    bpy.context.view_layer.update()
    M = root.matrix_world.copy()
    root.parent = data.arm; root.parent_type = 'BONE'; root.parent_bone = 'chest'
    bpy.context.view_layer.update(); root.matrix_world = M
    return root, sticks


def s2_digger(knob_pts=((0.46, -0.58, S2_DECK + 0.545), (0.46, -0.3, S2_DECK + 0.545))):
    """THE DIGGER: a yellow tracked excavator facing +X, an open operator's deck on its -Y side where he stands at two
    control sticks, the boom on its +Y side: boom, stick and a toothed bucket, each on its own pivot empty.
    Returns dict(boom, stick, bucket, sticks=[(pivot, knob)], load)."""
    yel = lw_paint("digger yellow", "#E8A80C", rough=0.4)
    dark = lw_metal("digger steel", "#2C2C2E", rough=0.5)
    track = lw_noise("track rubber", "#1A1A1A", "#2E2E2E", scale=60, rough=0.9, bump=0.8, stretch=(1, 8, 1))
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
    sticks = []
    if knob_pts: K.box("digger seat back", (-0.1, -0.45, S2_DECK + 0.5), (0.08, 0.4, 0.45), K.mat("seat black", "#1E1E1E", rough=0.7), bev=0.03)
    for kx, ky, kz in knob_pts:                           # the two control towers in front of him, a stick on each
        top = kz - 0.135
        K.box("digger control tower", (kx + 0.03, ky, (S2_DECK + top) / 2), (0.1, 0.1, top - S2_DECK), dark, bev=0.01)
        pv = K.empty("control stick pivot", (kx, ky, top))
        K.cyl("control stick", (kx, ky, top + 0.06), 0.012, 0.12, dark, parent=pv)
        knob = K.sph("control stick knob", (kx, ky, kz), 0.03, K.mat("knob black", "#141414", rough=0.4), parent=pv)
        sticks.append((pv, knob))
    K.box("digger lamp", (0.2, -0.02, S2_DECK + 1.3), (0.1, 0.12, 0.06), lw_emit("digger lamp", "#FFF2D0", 12.0), bev=0.01)
    boom = K.empty("digger boom", tuple(S2_BOOM))
    K.box("digger boom arm", (S2_BOOM.x + S2_L1 / 2, S2_BOOM.y, S2_BOOM.z), (S2_L1, 0.26, 0.34), yel, bev=0.05, parent=boom)
    K.cyl("digger ram", (S2_BOOM.x + 0.9, S2_BOOM.y, S2_BOOM.z - 0.25), 0.06, 1.4, lw_metal("ram chrome", "#C8CCD0", rough=0.15), rot=(0, math.pi / 2, 0), parent=boom)
    stick = K.empty("digger stick", (S2_BOOM.x + S2_L1, S2_BOOM.y, S2_BOOM.z), parent=boom)
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
    tyre = K.mat("car tyre", "#141414", rough=0.8)
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
    lw_grid("works ground", -26, 26, -14, 22, 90, 80, s2_ground_z, lw_noise("works gravel", "#3C3631", "#5E554C", scale=14, rough=0.95, bump=0.8, detail=10))
    wall = earth_wall("earth wall", [(x, S2_WALL_Y + 0.006 * x * x) for x in range(-30, 32, 2)], h=S2_WALL_H, crest=1.4, base=S2_BASE, seed=4)
    lava_rock("works rock", 90, (-12, 12, -6, S2_FOOT - 0.2), s2_ground_z, seed=6, r=(0.08, 0.26),
              avoid=lambda x, y: (-3.6 < x < -1.0 and -1.2 < y < 3.0) or (-0.8 < x < 1.0 and -1.8 < y < 1.2))
    masts = []
    for k, x in enumerate((-7.5, -4.2, 2.6, 6.0)):
        y = S2_FOOT - 0.5 + 0.006 * x * x
        K.cyl("floodlight mast", (x, y, 2.6), 0.06, 5.2, lw_metal("mast steel", "#8A8E92"), v=12)
        head = K.box("floodlight head", (x, y - 0.12, 5.25), (0.9, 0.2, 0.35), lw_emit(f"floodlight lamp {k}", "#FFF4DC", 0.0), bev=0.02)
        L = lw_area(f"floodlight {k}", (x, y - 0.3, 5.1), (0.3 * x, -1.0, 0.3), 0.0, 0.8, col=(1.0, 0.95, 0.85))
        masts.append((head, L))
    yel = lw_paint("digger yellow", "#E8A80C", rough=0.4)
    for k, x in enumerate((-10.5, 5.0, 9.5)):             # other diggers at work along the wall
        y = S2_FOOT - 1.4 + 0.006 * x * x
        K.box(f"far digger {k} body", (x, y, 0.7), (1.6, 1.3, 1.0), yel, bev=0.08)
        K.box(f"far digger {k} cab", (x - 0.3, y - 0.2, 1.5), (0.7, 0.7, 0.7), K.mat("car glass", "#1E262C", rough=0.05, metal=0.3), bev=0.05)
        bm_ = K.box(f"far digger {k} boom", (x + 0.2, y + 1.3, 2.2), (0.25, 3.0, 0.3), yel, bev=0.05); bm_.rotation_euler = (math.radians(40 - 10 * (k % 2)), 0, 0)
    ash = lw_smoke_mat("eruption smoke", density=1.6, col=(0.3, 0.3, 0.33))
    for k in range(8):
        lw_puff(f"eruption smoke {k}", (-16 + 4.5 * k + rnd.uniform(-1, 1), 20 + rnd.uniform(0, 5), 9 + rnd.uniform(0, 6)), rnd.uniform(4.0, 5.5), ash, scale=(1.4, 1.0, 1.0))
    for k in range(10):                                    # the plume's column climbing over the fissure: the sky is the eruption's
        u = k / 9
        lw_puff(f"eruption column {k}", (-7 + 9 * u * u + rnd.uniform(-1.5, 1.5), 30 + 4 * u, 14 + 30 * u), 5.5 + 4 * u, ash, scale=(1.3, 1.0, 1.0))
        lw_puff(f"eruption drift {k}", (-12 - 14 * u + rnd.uniform(-1.5, 1.5), 34 + 6 * u, 22 + 18 * u), 6.0 + 3 * u, ash, scale=(1.6, 1.0, 0.8))   # blown off west
    K.box("eruption horizon glow", (0, 30, 3.0), (90, 0.5, 6.0), lw_emit("horizon glow", "#FF6A20", 0.8), bev=0)

    def light():
        return iceland_light(sun_elev=10, sun_az=-40, sun=2.6, sky=0.35, warm=(1.0, 0.7, 0.5), haze=1.6)
    return dict(light=light, wall=wall, masts=masts)


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
    P0 = Vector((0.05, 0.2, 0.0)); YAW0 = math.radians(18)
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
    LOW = (2.3, 0.75); HIGH = (S2_EDGE - 0.25 - S2_DIG.y, S2_WALL_H + 0.85)
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
    dust_m = lw_smoke_mat("tip dust", density=2.0, col=(0.6, 0.55, 0.5))
    dust = []
    for k in range(4):
        x = S2_DIG.x - S2_BOOM.y - 0.4 + 0.9 * k; y = S2_FOOT - 0.3 + 0.5 * (k % 2)
        o = lw_puff(f"tip dust {k}", (x, y, 0.4), 0.8, dust_m); dust.append(o)
        t0 = T_DUCK - 0.15 + 0.08 * k
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s_ = W(t, t0, 0.5) * (1 - 0.5 * W(t, t0 + 1.4, 0.8))
            r_ = s_ * (1 + 0.3 * max(0.0, t - t0)); lw_puff_key(o, f, (r_, r_, r_ * 0.8)); o.location.z = 0.4 + 0.5 * max(0.0, t - t0)
            o.keyframe_insert("location", frame=f)
    # ---- the trucks: rolling along behind the works
    for k, (x0, v) in enumerate(((12.0, -2.0),)):
        truck = s2_truck(f"dump truck {k}"); truck.rotation_euler = (0, 0, math.radians(90))
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; truck.location = (x0 + v * t, S2_FOOT - 0.75, 0.0); truck.keyframe_insert("location", frame=f)
    # ---- the floodlights: low at first, blazing on at T_LIGHTS
    for k, (head, L) in enumerate(P["masts"]):
        em = head.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; on = 0.2 + 0.8 * W(t, T_LIGHTS + 0.08 * k, 0.2)
            em.default_value = 25.0 * on; em.keyframe_insert("default_value", frame=f)
            L.data.energy = 2500.0 * on; L.data.keyframe_insert("energy", frame=f)
    sk = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
    for f in range(1, NF + 1, 3):
        t = (f - 1) / FPS; sk.default_value = 0.35 * (1 - 0.4 * t / DUR); sk.keyframe_insert("default_value", frame=f)
    # ---- his body: leaning into the push, the duck as the rock comes down past, the grin, the haul back, the lights
    def body(t):
        p = P0.copy()
        p.z += -0.05 * W(t, T_DUCK - 0.15, 0.28) * (1 - W(t, T_GRIN - 0.1, 0.3)) - 0.04 * W(t, T_BACK - 0.2, 0.3) * (1 - W(t, T_LOW, 0.3))
        p.y += 0.05 * W(t, T_PUSH - 0.2, 0.3) * (1 - W(t, T_TOP, 0.3))
        yaw = YAW0 - math.radians(30) * W(t, T_PUSH, 0.6) * (1 - W(t, T_DUCK - 0.2, 0.3)) + math.radians(8) * W(t, T_DUCK - 0.2, 0.3) * (1 - W(t, T_BACK, 0.4)) \
            - math.radians(25) * W(t, T_BACK, 0.4) * (1 - W(t, T_LIGHTS, 0.4)) + math.radians(14) * W(t, T_LIGHTS, 0.4)
        yw = math.atan2(P0.x - PS.x, -(P0.y - PS.y))
        yaw = yw + (yaw - yw) * W(t, 0.9, 0.45)
        return p, yaw
    T_STEP = 0.9
    data.walk_to((P0.x, P0.y), 0.05, T_STEP)
    for f in range(F(T_STEP) + 1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (24 * W(t, T_PUSH - 0.2, 0.3) * (1 - W(t, T_TOP - 0.2, 0.3)) - 12 * W(t, T_TOP - 0.2, 0.3) * (1 - W(t, T_DUCK - 0.15, 0.2))
                                       + 22 * W(t, T_DUCK - 0.2, 0.28) * (1 - W(t, T_GRIN - 0.1, 0.3)) - 16 * W(t, T_BACK - 0.2, 0.3) * (1 - W(t, T_LOW, 0.3))
                                       - 10 * W(t, T_LIGHTS, 0.3), 0, 8 * math.sin(2 * math.pi * (t - T_GRIN) / 0.9) * W(t, T_GRIN, 0.2) * (1 - W(t, T_BACK, 0.2))), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    kns = [kn for _pv, kn in sticks]
    def on_knob(kn):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update()
            return kn.matrix_world.translation + Vector((0, 0, 0.035))
        return fn
    for sd in "LR":
        sh = acts._shoulder(data, sd); kn = min(kns, key=lambda k_: (k_.matrix_world.translation - sh).length)
        data.reach(sd, on_knob(kn), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- face and head
    BK = lambda t: world(*path(t))
    LENS = Vector((0.4, -1.4, 0.5))
    data.look_at(BK(0.0), 0.0, max_yaw=60, max_pitch=40, blend=0.0)
    data.look_at(BK(T_TOP - 0.5), T_PUSH + 0.4, max_yaw=60, max_pitch=60, blend=0.4)
    data.look_at(Vector((-1.0, 1.5, 0.3)), T_DUCK - 0.2, max_yaw=55, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_GRIN, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(BK(T_LOW), T_BACK + 0.1, max_yaw=60, max_pitch=50, blend=0.3)
    data.look_at(Vector((2.6, S2_FOOT, 5.2)), T_LIGHTS + 0.05, max_yaw=60, max_pitch=50, blend=0.3)
    data.expression("determined", 0.2, T_DUCK - 0.2, blend=0.2)
    data.expression("alarmed", T_DUCK - 0.15, T_GRIN - 0.05, blend=0.12)
    data.expression("happy", T_GRIN, T_BACK - 0.05, blend=0.2)
    data.expression("determined", T_BACK, T_LIGHTS, blend=0.2)
    data.expression("pleased", T_LIGHTS + 0.1, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low at the foot of the wall, looking up at him, the digger and its arm over him
    CAM = Vector((0.45, -1.25, 0.35)); LOOK = Vector((-1.0, 6.0, 2.5))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 16.0, face_at=(0.6, 0.3), height=0.46, t=0.4 * DUR)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=16.0, fstop=11.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.08, 0.06, 0.02)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))))
    arm_objs = lambda: meshes([D["boom"]])
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("remote stick", "remote control"),
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
grinds sideways and slides off along the wall, away from the town; he follows it along the crest, still spraying, and
gives us a thumb up."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FACE_Y = -S3_CREST / 2      # the crest's outer edge (y); the outer face runs down to the foot at -S3_BASE / 2


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


S3_PILE = S3_H - 0.9           # the old lava already heaped against the face: the field rises to here at the wall


def s3_ground_z(x, y):
    """the black lava field: months of old flows heaped up against the wall's outer face, falling away out to the fissure"""
    u = max(0.0, min(1.0, (y + 16.0) / 11.0))
    return S3_PILE * ease(u) + 0.1 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_hose_nozzle():
    """a fire hose's brass nozzle with a grip, and the canvas hose running back from it"""
    root = K.empty("fire hose", (0, 0, 0))
    brass = lw_metal("nozzle brass", "#B8862E", rough=0.25)
    K.cyl("fire hose nozzle", (0, 0.0, 0.0), 0.028, 0.22, brass, rot=(math.pi / 2, 0, 0), v=20, parent=root)
    K.cyl("fire hose nozzle tip", (0, -0.13, 0.0), 0.018, 0.06, brass, rot=(math.pi / 2, 0, 0), v=16, parent=root)
    K.cyl("fire hose grip", (0, 0.05, -0.05), 0.02, 0.09, K.mat("nozzle grip", "#1E1E1E", rough=0.6), v=12, parent=root)
    lw_local(root)
    return root


def place_wall_crest():
    """THE TOP OF THE WALL: its crest track of crushed rock, the black lava field running away from its outer face,
    the town's roofs below it on the other side, a parked digger far along the crest, the plume over the far fissure."""
    rnd = lw_random.Random(31)
    lw_grid("lava field ground", -30, 30, -30, 30, 90, 90, s3_ground_z, lava_field_mat())
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    K.box("crest track", (0, 0, S3_H + 0.03), (50, S3_CREST - 0.1, 0.06), lw_noise("crushed rock", "#3E3732", "#615750", scale=30, rough=0.95, bump=1.0, detail=10), bev=0.02)
    for k in range(12):
        town_house(f"town house below {k}", (-12 + 2.6 * k + rnd.uniform(-0.3, 0.3), 7.5 + 2.6 * (k % 3), 0), yaw=math.pi + rnd.uniform(-0.2, 0.2),
                   w=2.1, d=1.6, roof=ROOFS[k % len(ROOFS)], wall=WALLS[k % len(WALLS)])
    lava_rock("lava field rock", 120, (-25, 25, -25, -4.6), s3_ground_z, seed=9, r=(0.1, 0.35))
    smoke = lw_smoke_mat("far plume", density=0.7, col=(0.45, 0.42, 0.4))
    for k in range(6):
        lw_puff(f"far plume {k}", (-24 + 6 * k, 38 + 3 * (k % 3), 10 + 3.5 * k), 7.0, smoke, scale=(1.4, 1.0, 1.0))   # the plume, blown over the town

    def light():
        return iceland_light(sun_elev=24, sun_az=-30, sun=3.0, sky=0.4, haze=1.4)
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. From just above the crest, off his shoulder: the old lava heaped high against the face below him.
    A new front rolls in and slams the face right under his boots; he flinches, braces and blasts it with the hose;
    steam bursts up; the front grinds sideways and slides off along the wall; he follows it round with the spray, lets
    go with one hand and gives us a thumb up."""
    T_ROLL = 0.03 * DUR; T_HIT = 0.21 * DUR; T_SPRAY = 0.35 * DUR; T_SLIDE = 0.52 * DUR; T_REL = 0.64 * DUR; T_THUMB = 0.75 * DUR
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    P0 = Vector((-0.2, -0.45, S3_H + 0.06))
    data.place(P0.x, P0.y, 0.0)
    data.arm.location.z = P0.z
    kit = hard_hat(data)
    # ---- the lava front: a long glowing lobe riding in over the old heap, ramming the face under him, sliding off
    lm = lava_mat("lava front", heat=1.0, scale=3.5, fresh=0.8)
    out = []
    for k in range(25):                                    # the front's outline: a long tongue, its nose to +X
        a = 2 * math.pi * k / 25
        out.append((2.6 * math.cos(a) + 0.2 * math.sin(3 * a), 0.8 * math.sin(a) + 0.08 * math.cos(5 * a)))
    front = lava("lava front", out, z=0.0, thick=0.75, m=lm, seed=4, lumpy=0.18)
    Y_FACE = -S3_BASE / 2 + (S3_PILE / (S3_H * 0.97)) * (S3_BASE / 2 - S3_CREST / 2 - 0.1)   # where the heap meets the face
    Y_HIT = Y_FACE - 0.45
    def where(t):
        y = -6.0 + (Y_HIT + 6.0) * ease(min(1.0, max(0.0, (t - T_ROLL) / (T_HIT - T_ROLL))))
        x = -1.4 - 1.6 * W(t, T_SLIDE - 0.25, 1.5) - 0.1 * t      # it grinds off along the wall, away from him
        z = S3_PILE - 0.3 + 0.35 * W(t, T_HIT - 0.08, 0.25) - 0.12 * W(t, T_SLIDE, 0.8)   # it rides up the face as it rams it
        return Vector((x, y, z))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; front.location = where(t); front.keyframe_insert("location", frame=f)
        sq = 1.0 - 0.1 * lw_kick(t - T_HIT, 0.2)
        front.scale = (1.0 + 0.08 * W(t, T_SLIDE, 1.0), sq, 1.0 + 0.2 * lw_kick(t - T_HIT, 0.25)); front.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.18)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; heat.default_value = 2.2 * (1 + 1.0 * lw_kick(t - T_HIT, 0.35) + 0.4 * W(t, T_HIT, 0.3)); heat.keyframe_insert("default_value", frame=f)
    # glowing chunks the impact throws up off the face, falling back onto the front
    cm = lw_emit("lava chunk", "#FF5A00", 1.3); rnd = lw_random.Random(3); chunks = []
    for k in range(14):
        c = K.sph(f"lava chunk {k}", (0, 0, -5), rnd.uniform(0.04, 0.09), cm, seg=8, ring=6); chunks.append(c)
        x0 = rnd.uniform(-3.0, -0.6); vy = -rnd.uniform(0.3, 0.9); vz = rnd.uniform(1.6, 2.6); t0 = T_HIT + rnd.uniform(-0.03, 0.12)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = t - t0
            if s < 0: c.location = (x0, Y_FACE, -3.0)
            else:
                z = S3_PILE + 0.7 + vz * s - 4.9 * s * s
                c.location = (x0 + 0.2 * s, Y_FACE - 0.15 + vy * s, max(z, S3_PILE + 0.55))
            c.keyframe_insert("location", frame=f)
    # ---- the hose: the nozzle in his hands, aimed down the face at the front; the jet; the steam where it lands
    noz = s3_hose_nozzle()
    aim = lambda t: Vector((-0.45 + 0.15 * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) - 0.3 * W(t, T_SLIDE, 0.8), Y_FACE + 0.5, S3_PILE + 0.6))
    jet_m = bpy.data.materials.get("hose water") or bpy.data.materials.new("hose water")
    jet_m.use_nodes = True; jb = jet_m.node_tree.nodes["Principled BSDF"]
    jb.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1); jb.inputs["Roughness"].default_value = 0.1
    jb.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1); jb.inputs["Emission Strength"].default_value = 0.6
    drops = [K.sph(f"hose jet {k}", (0, 0, -5), 0.016, jet_m, seg=8, ring=6) for k in range(30)]
    steam_m = lw_smoke_mat("lava steam", density=3.0, col=(0.93, 0.94, 0.96))
    steam = [lw_puff(f"lava steam {k}", (0, 0, -5), 1.0, steam_m) for k in range(8)]
    # ---- his body: watching it come, a flinch at the hit, braced back as he opens up, turning with the slide
    yaw0 = math.radians(-12)
    def body_yaw(t):
        return yaw0 + math.radians(12) * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) * W(t, T_SPRAY, 0.3) - math.radians(30) * W(t, T_SLIDE, 0.6) \
            + math.radians(34) * W(t, T_THUMB - 0.1, 0.4)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.z += 0.07 * lw_kick(t - T_HIT, 0.12)                                      # a hop at the hit
        p.y += 0.08 * W(t, T_HIT, 0.2) - 0.06 * W(t, T_SPRAY - 0.1, 0.3)            # jumps back from the edge, then leans back in to spray
        data._kobj(t, loc=tuple(p), rot=body_yaw(t))
    lw_layer(data, "spine", lambda t: (16 * W(t, 0.0, T_HIT - 0.1) * (1 - W(t, T_HIT, 0.12)) - 16 * lw_kick(t - T_HIT, 0.22) + 12 * W(t, T_SPRAY - 0.2, 0.3) * (1 - W(t, T_THUMB - 0.1, 0.3))
                                       - 8 * W(t, T_THUMB, 0.3), 0, 6 * W(t, T_SLIDE, 0.5) * (1 - W(t, T_THUMB, 0.3))), 0, DUR + 0.4)
    # his hands on the nozzle: both low at first, raised to aim as he opens it, the camera-side one lets go for the thumb
    sc.frame_set(1); bpy.context.view_layer.update()
    cam_side = Vector((0.45, -2.55, 0))
    sides = sorted("LR", key=lambda s: -(acts._shoulder(data, s) - data.arm.location).dot(cam_side))
    keys = lambda k: [(0.0, (0.13, -0.05, -0.16)), (T_HIT - 0.1, (0.14, -0.05, -0.15)), (T_HIT + 0.15, (0.12, -0.05, -0.12)),
                      (T_SPRAY, (0.15, -0.04 - 0.01 * k, -0.06)), (T_SLIDE, (0.16, -0.04, -0.05)), (DUR + 0.5, (0.16, -0.04, -0.06))]
    data.reach(sides[0], lw_hand(data, sides[0], keys(0)), 0.0, T_REL, lead=0.3, back=None, elbow_out=0.4)
    data.reach(sides[1], lw_hand(data, sides[1], keys(1)), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)
    PUMP = [(T_REL + 0.35, (0.12, 0.1, -0.03)), (T_THUMB + 0.22, (0.1, 0.12, 0.12)), (T_THUMB + 0.45, (0.12, 0.11, 0.05)),
            (T_THUMB + 0.68, (0.1, 0.12, 0.13)), (DUR + 0.4, (0.11, 0.12, 0.1))]          # the free fist punches the air, twice
    data.reach(sides[0], lw_hand(data, sides[0], PUMP), PUMP[0][0], DUR + 0.3, lead=0.4, back=None, elbow_out=0.5)
    LENS = Vector((0.25, -3.0, S3_H + 0.8))
    data.look_at(Vector((-3.0, -6.0, S3_PILE)), 0.0, max_yaw=50, max_pitch=50, blend=0.0)
    data.look_at(Vector((-0.9, Y_HIT, S3_PILE + 0.4)), T_HIT - 0.15, max_yaw=50, max_pitch=55, blend=0.15)
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
    hose = lw_link(bpy.data.objects.new("fire hose line", cu)); hose.data.materials.append(K.mat("hose canvas", "#B8342A", rough=0.7))
    HYD = Vector((P0.x - 1.4, P0.y + 0.6, S3_H))
    K.cyl("fire hydrant", (HYD.x, HYD.y, S3_H + 0.25), 0.07, 0.5, K.mat("hydrant red", "#C8231B", rough=0.4), v=16)
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        tail = noz.matrix_world @ Vector((0, 0.12, 0)); foot = data.arm.matrix_world.translation
        pts = [HYD + Vector((0, 0, 0.12)), Vector((foot.x - 0.6, foot.y + 0.35, S3_H + 0.06)),
               Vector((foot.x - 0.15, foot.y + 0.2, S3_H + 0.06)), tail]
        for bp, q in zip(sp.bezier_points, pts):
            bp.co = q; bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.keyframe_insert("co", frame=f)
    # the jet: a solid rope of water from the nozzle tip arcing down to the aim point, breaking into spray at its end
    jc = bpy.data.curves.new("hose jet line", 'CURVE'); jc.dimensions = '3D'; jc.bevel_depth = 0.014; jc.bevel_resolution = 2
    jsp = jc.splines.new('BEZIER'); jsp.bezier_points.add(2)
    jet = lw_link(bpy.data.objects.new("hose jet line", jc)); jet.data.materials.append(jet_m)
    noz_tip = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); noz_tip[f] = noz.matrix_world @ Vector((0, -0.16, 0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; on = W(t, T_SPRAY, 0.12)
        a = noz_tip[f]; b = a.lerp(aim(t), max(0.02, on)); mid = a.lerp(b, 0.5); mid.z += 0.18 * on
        for bp, q in zip(jsp.bezier_points, (a, mid, b)):
            bp.co = q; bp.handle_left_type = bp.handle_right_type = 'AUTO'; bp.keyframe_insert("co", frame=f)
        jet.hide_render = on < 0.02; jet.keyframe_insert("hide_render", frame=f)
    jr = lw_random.Random(17); jit = [Vector((jr.uniform(-1, 1), jr.uniform(-1, 1), jr.uniform(-1, 1))) for _ in drops]
    for k, o in enumerate(drops):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = t >= T_SPRAY
            if not on: o.location = (0, 0, -6)
            else:
                u = 0.75 + 0.25 * (((k / len(drops)) + 2.0 * t) % 1.0)
                a = noz_tip[f]; b = aim(t); m_ = a.lerp(b, u); m_.z += 0.25 * math.sin(math.pi * u)
                o.location = m_ + jit[k] * (0.03 + 0.25 * u * u)              # the jet fans out into spray as it falls
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(steam):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; t0 = T_SPRAY + 0.06 + 0.12 * k; s = W(t, t0, 0.4)
            b = aim(t); age = max(0.0, t - t0)                      # it boils up off the front and rolls back over the crest
            o.location = (b.x - 0.55 - 0.16 * k - 0.3 * age, b.y + 0.1 + 0.9 * age + 0.15 * (k % 3), b.z + 0.1 + 0.4 * s + 0.6 * age)
            r = 0.3 * s * (1 + 0.08 * k) * (1 + 0.4 * age)
            lw_puff_key(o, f, (r, r, r * 0.9)); o.keyframe_insert("location", frame=f)
    # ---- the lens: just above the crest off his shoulder, out over the heap, looking down past him at the front
    CAM = LENS.copy(); LOOK = Vector((-0.59, -0.12, S3_H + 0.68))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=50.0, fstop=22.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.12, 0.0, 0.03)) * W(t, T_SLIDE - 0.2, 1.4), LOOK + Vector((-0.2, 0.0, 0.0)) * W(t, T_SLIDE - 0.2, 1.4), data.pos() + Vector((0, 0, 0.5))))
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=("fire hose",),
                boxes=[],
                conseq=[("the lava front rolls in and slams into the wall's face, then slides off along it", lambda: [front], T_ROLL, DUR, {"whole": False}),
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


def s4_zig(x):
    """the crack's zig-zag line across the street: y at x"""
    return S4_YC + 0.12 * math.sin(3.1 * x + 0.4) + 0.07 * math.sin(7.3 * x + 1.1)


def s4_ground_z(x, y):
    z = -0.06                                              # under the street's slabs (level with them it showed through black)
    if abs(x) > 3.3: z += 0.06 + 0.1 * lw_fbm(x * 0.4, y * 0.4, 23)
    return z


def s4_slab(name, near, m):
    """one side of the cracked street: the asphalt from the crack to the end of the street (near: toward the lens),
    its crack edge the zig-zag with a 0.25 m face down into the ground. Built as strips of quads, every face up or out
    (one concave n-gon rendered black). Returns the object, origin on the crack line."""
    xs = [-S4_HALF + 2 * S4_HALF * k / 40 for k in range(41)]
    far_y = -14.0 if near else 26.0
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
    tray = lw_paint("barrow green", "#2F6B3A", rough=0.45); steel = lw_metal("barrow steel", "#6A6E72", rough=0.4)
    K.box("wheelbarrow tray", (0, 0.3, 0.2), (0.4, 0.5, 0.05), tray, bev=0.02, parent=root)
    for sx in (-1, 1):
        K.box("wheelbarrow tray side", (sx * 0.2, 0.3, 0.28), (0.03, 0.5, 0.16), tray, bev=0.01, parent=root)
        K.cyl("wheelbarrow handle", (sx * 0.1, 0.38, 0.14), 0.015, 0.72, steel, rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
        K.cyl("wheelbarrow leg", (sx * 0.12, 0.5, 0.07), 0.012, 0.16, steel, v=10, parent=root)
    K.box("wheelbarrow tray front", (0, 0.06, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    K.box("wheelbarrow tray back", (0, 0.54, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    K.cyl("wheelbarrow wheel", (0, 0, 0), 0.1, 0.06, K.mat("car tyre", "#141414", rough=0.8), rot=(0, math.pi / 2, 0), v=24, parent=root)
    K.cyl("wheelbarrow hub", (0, 0, 0), 0.03, 0.07, steel, rot=(0, math.pi / 2, 0), v=12, parent=root)
    sand = lw_noise("sandbag hessian", "#7A6844", "#9A8658", scale=40, rough=0.9, bump=0.6)
    for k, (x, y) in enumerate(((-0.08, 0.2), (0.09, 0.22), (0.0, 0.4), (-0.06, 0.38))):
        K.sph(f"wheelbarrow sandbag {k}", (x, y, 0.27 + 0.04 * (k > 1)), 0.075, sand, scale=(1.0, 1.5, 0.5), seg=12, ring=8, parent=root)
    fire = lw_emit("barrow fire", "#FF6A10", 1.4)
    flames = []
    for k, (x, y) in enumerate(((-0.08, 0.22), (0.08, 0.3), (0.0, 0.42))):
        fl = K.sph(f"wheelbarrow flame {k}", (x, y, 0.4), 0.08, fire, scale=(0.7, 0.7, 2.0), seg=10, ring=8, parent=root)
        flames.append(fl)
    lw_local(root)
    return root, flames


def place_town_crack():
    """AN EMPTY STREET INSIDE THE WALL: asphalt and pavements between two rows of town houses, the red-roofed house on
    the corner, the earth wall across the end of the street with smoke over it, the lava field beyond."""
    rnd = lw_random.Random(41)
    lw_grid("town ground", -30, 30, -16, 40, 90, 80, s4_ground_z, lava_field_mat())
    asph = lw_noise("street asphalt", "#4A4A4D", "#66666A", scale=40, rough=0.85, bump=0.4)
    near = s4_slab("street near", True, asph)
    far = s4_slab("street far", False, asph)
    paint = K.mat("road paint", "#E9E4D4", rough=0.6)
    lines = []
    for y in list(range(-12, 0, 2)) + list(range(1, 24, 2)):
        o = K.box("centre line", (0, y + 0.5 - (0.6 if y < 0 else 0), 0.004), (0.08, 0.9, 0.006), paint, bev=0)
        o.parent = near if y < 0 else far; o.matrix_parent_inverse = (near if y < 0 else far).matrix_world.inverted()
        lines.append(o)
    kerb = lw_noise("kerb concrete", "#A6A39C", "#C2BFB6", scale=14, rough=0.8)
    for sx in (-1, 1):
        for slab, y0, y1 in ((near, -14.0, -0.2), (far, 0.2, 26.0)):
            o = K.box("kerb", (sx * 2.05, (y0 + y1) / 2, 0.04), (0.12, y1 - y0, 0.08), kerb, bev=0.01)
            o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    trench = lava_mat("crack lava", heat=1.4, scale=4.0, fresh=0.6)
    K.box("crack trench", (0, S4_YC, -0.32), (2 * S4_HALF + 0.4, 1.6, 0.1), trench, bev=0)
    for sy in (-1, 1):
        K.box("crack wall rock", (0, S4_YC + sy * 0.85, -0.2), (2 * S4_HALF + 0.4, 0.1, 0.4), lw_noise("crack rock", "#2A2522", "#4A3E36", scale=10, rough=0.95, bump=1.0), bev=0)
    houses = []
    for sx in (-1, 1):
        y = -9.0 + (0.6 if sx > 0 else 0.0); k = 0
        while y < 16.0:
            w = rnd.uniform(1.9, 2.4); d = rnd.uniform(1.5, 1.8)
            corner = sx > 0 and abs(y + w / 2 - 2.4) < 1.3
            roof = "#C0302A" if corner else ROOFS[(k * 3 + (sx > 0) + 1) % len(ROOFS)]
            if roof == "#B8352B" and not corner: roof = ROOFS[2]
            hs = town_house(f"town house {sx}_{k}" + (" corner" if corner else ""), (sx * (3.35 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            h=rnd.uniform(1.2, 1.45), roof=roof, wall=WALLS[k % len(WALLS)], seed=k + 20)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    wall = earth_wall("earth wall", [(x, 24.0 + 0.01 * x * x) for x in range(-30, 32, 2)], h=4.4, crest=1.4, base=8.5, seed=12)
    ash = lw_smoke_mat("wall smoke", density=1.6, col=(0.45, 0.44, 0.46))
    for k in range(9):
        lw_puff(f"wall smoke {k}", (-16 + 4 * k + rnd.uniform(-1, 1), 31 + rnd.uniform(0, 4), 8 + rnd.uniform(0, 6)), rnd.uniform(3.5, 4.8), ash, scale=(1.4, 1.0, 1.0))
    for k in range(5):
        K.sph("far mountain", (-40 + 20 * k, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.8), seg=24, ring=12)
    for k in range(3):
        K.cyl(f"street lamp post {k}", (-2.55, 6 + 4 * k, 0.6), 0.03, 1.2, lw_metal("pole", "#8A8E92"), v=10)

    def light():
        return iceland_light(sun_elev=30, sun_az=-30, sun=3.2, sky=0.45, haze=1.2)
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
    Y0, YS = 1.55, 0.92                                     # where he starts pushing and where he stops (y)
    data.place(0.15, Y0, 0.0)
    kit = hard_hat(data)
    data.walk_to((0.15, YS), 0.0, T_STOP, pushing=True)
    # ---- the leap back at T_LET and the hops back at T_RUN, facing the crack (and us) the whole time
    def hop(t, t0, d, h, T=0.4):
        u = min(1.0, max(0.0, (t - t0) / T)); return d * ease(u), h * math.sin(math.pi * u)
    for f in range(F(T_STOP) + 1, NF + 1):
        t = (f - 1) / FPS
        y1, z1 = hop(t, T_LET, 0.2, 0.08, 0.5); y2, z2 = hop(t, T_RUN, 0.13, 0.06); y3, z3 = hop(t, T_RUN + 0.45, 0.14, 0.06)
        jolt = -0.05 * lw_kick(t - T_JOLT, 0.1) - 0.05 * lw_kick(t - T_POUR, 0.15)
        sway = 0.04 * math.sin(2 * math.pi * (t - T_LET) / 1.1) * W(t, T_LET + 0.3, 0.3)
        data._kobj(t, loc=(0.15 + sway + 0.12 * W(t, T_RUN, 0.6), YS + y1 + y2 + y3 + 0.04 * W(t, T_POUR, 0.2), z1 + z2 + z3 + jolt),
                   rot=math.radians(-8) * W(t, T_LET, 0.3) + math.radians(12) * math.sin(2 * math.pi * (t - T_LET) / 1.6) * W(t, T_LET + 0.3, 0.4) + math.radians(14) * W(t, T_RUN, 0.5))
    lw_layer(data, "spine", lambda t: (14 * W(t, 0.0, 0.2) * (1 - W(t, T_STOP, 0.2)) - 16 * lw_kick(t - T_JOLT, 0.18) + 10 * W(t, T_TEAR, 0.25) * (1 - W(t, T_LET, 0.2))
                                       - 14 * W(t, T_LET, 0.2) * (1 - W(t, T_LET + 0.6, 0.3)) - 10 * W(t, T_RUN, 0.3), 0, 0), 0, DUR + 0.4)
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
        pitch = 0.0
        if t > T_LET:                                       # let go: the handles drop onto its legs, then the tip
            pitch += math.radians(-10) * W(t, T_LET, 0.2)
            roll = 0.25 * W(t, T_OPEN0 + 0.2, 0.9)
            p.y = max(y_edge - 0.05, p.y - roll)
            tip = W(t, T_TIP, 0.6)
            pitch += math.radians(48) * tip
            p.z -= 0.22 * tip
        bar.location = p; bar.rotation_euler = (pitch, 0, 0)
        bar.keyframe_insert("location", frame=f); bar.keyframe_insert("rotation_euler", frame=f)
    for k, fl in enumerate(flames):
        s0 = fl.scale.copy()
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = W(t, T_TIP + 0.25 + 0.1 * k, 0.3)
            fl.hide_render = on < 0.02; fl.keyframe_insert("hide_render", frame=f)
            k_ = max(0.05, on * (1 + 0.25 * math.sin(2 * math.pi * 5 * t + k)))
            fl.scale = (s0.x * k_, s0.y * k_, s0.z * k_ * (1 + 0.3 * math.sin(2 * math.pi * 3.3 * t + 2 * k))); fl.keyframe_insert("scale", frame=f)
    def handle(sx):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update()
            return bar.matrix_world @ Vector((sx * 0.1, 0.7, 0.27))
        return fn
    for sd, sx in zip(sides, (-1, 1)):
        data.reach(sd, handle(sx), 0.0, T_LET, lead=0.05, back=None, elbow_out=0.35)
    # arms up against the heat: hands up at his face's sides from the leap, higher at the hops back
    for sd in sides:
        HK = [(T_LET + 0.45, (0.07, 0.13, 0.04)), (T_POUR - 0.1, (0.06, 0.13, 0.05)), (T_POUR + 0.2, (0.04, 0.15, 0.13)), (T_RUN, (0.05, 0.14, 0.12)),
              (T_RUN + 0.4, (0.07, 0.15, 0.14)), (T_RUN + 0.75, (0.05, 0.12, 0.06)), (DUR + 0.4, (0.07, 0.15, 0.13))]
        data.reach(sd, lw_hand(data, sd, HK), HK[0][0], DUR + 0.3, lead=0.6, back=None, elbow_out=0.4)
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
    for i in range(61): op.data[61 + i].co.y = s4_zig(xs[i]) - S4_YC - 0.6
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR); o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0)
        tear.scale = (max(0.002, u), 1, 1); tear.hide_render = u < 0.01; op.value = o
        tear.keyframe_insert("scale", frame=f); tear.keyframe_insert("hide_render", frame=f); op.keyframe_insert("value", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0); sh = 0.015 * math.sin(2 * math.pi * 11 * t) * lw_kick(t - T_JOLT, 0.25)
        near.location = (sh, S4_YC - 0.55 * o, 0.02 * o + 0.04 * lw_kick(t - T_JOLT, 0.12)); near.rotation_euler = (math.radians(-4) * o, 0, 0)
        far.location = (-sh, S4_YC, 0.0)
        for o_ in (near, far): o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    lava_flow_key(gm, 0.0, DUR + 0.5, 0.2)
    trench = bpy.data.materials["crack lava"]
    lava_flow_key(trench, 0.0, DUR + 0.5, 0.25)
    # ---- steam shooting up out of the crack as it opens
    steam_m = lw_billow_mat("crack steam", "#E9ECEE")
    steam = []
    for k in range(6):
        x = -2.2 + 0.85 * k
        o = lw_billow(f"crack steam {k}", (x, s4_zig(x) - 0.25, -0.3), 0.6, steam_m, seed=40 + k)
        steam.append(o)
        z0 = -0.3; t0 = T_OPEN0 + 0.05 * k
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = W(t, t0, 0.5)
            o.hide_render = s < 0.02; o.keyframe_insert("hide_render", frame=f)
            r = max(0.05, s * (1.0 + 0.5 * (t - t0)))
            o.scale = (r, r, r * 1.2); o.location.z = z0 + 1.6 * s + 0.9 * max(0.0, t - t0)
            o.keyframe_insert("scale", frame=f); o.keyframe_insert("location", frame=f)
    # ---- the lava: it wells up in the crack and pours out over the road, toward him and the corner house
    lm = lava_mat("street lava", heat=1.2, scale=4.0, fresh=0.8)
    out = []
    for k in range(28):
        a = 2 * math.pi * k / 28
        out.append((2.9 * math.cos(a) + 0.2 * math.sin(4 * a), 0.6 * math.sin(a) + 0.08 * math.cos(6 * a)))
    flow = lava("street lava", out, z=0.0, thick=0.16, m=lm, seed=6, lumpy=0.05)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_POUR, DUR - T_POUR); w_ = W(t, T_POUR - 0.25, 0.4)
        flow.location = (0.3 * u, S4_YC - 0.15 - 0.9 * u, -0.25 + 0.27 * w_)     # it pours out toward us, down the street
        flow.scale = (0.9 + 0.15 * u, 0.6 + 1.9 * u, 1.0); flow.keyframe_insert("location", frame=f); flow.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.3, axis=1)
    glow = lw_point("crack glow", (0.0, S4_YC, 0.25), 0.0, col=(1.0, 0.45, 0.12), r=0.6)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; glow.data.energy = 900.0 * W(t, T_OPEN0, 0.5) + 600.0 * W(t, T_POUR, 0.6); glow.data.keyframe_insert("energy", frame=f)
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
    CAM = Vector((2.1, -1.0, 1.75)); LOOK = Vector((-0.7, 2.8, 0.0))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 22.0, face_at=(0.45, 0.72), height=0.34, t=T_STOP)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=22.0, fstop=11.0)
    def cam_at(t):
        sc.frame_set(F(min(t, T_STOP))); bpy.context.view_layer.update()
        dy = data.pos().y - YS
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * lw_kick(t - T_JOLT, 0.25) * 2
        back = Vector((0, 0.3, 0.0)) * W(t, T_LET, 1.5)
        return CAM + Vector((0, dy, 0)) + shake + back, LOOK + Vector((0, dy, 0)) + shake + back, data.pos() + Vector((0, 0, 0.6))
    camera_path(cam, cam_at)
    return dict(lanes=[], kiosks=[], place="town_crack", light=light, data=data, rest=1, grips=("wheelbarrow",),
                boxes=[],
                conseq=[("he pushes the barrow of sandbags down the street", lambda: [o for o in meshes([bar]) if "wheel" not in o.name.split("barrow ")[-1] and "hub" not in o.name], 0.0, T_STOP, {"whole": False, "moves": True}),
                        ("a crack tears across the road in front of his wheel and yawns open, glowing", lambda: [tear], T_TORN, T_OPEN1 + 0.2, {"whole": False}),
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


def s5_slope_z(x, y):
    """the quay flat, the town's slope rising behind it, the lava field on the right"""
    z = 0.0
    if y > 3.0: z += 0.16 * (y - 3.0)
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 3.0 else 0)
    return z


def s5_lantern():
    """a hurricane lantern: a tin base and cap, a glass globe with a warm flame glowing in it, a wire bail on top (its
    pivot at the bail's top, the lantern hanging below it)"""
    root = K.empty("lantern", (0, 0, 0))
    tin = lw_metal("lantern tin", "#B33A22", rough=0.4)
    K.cyl("lantern base", (0, 0, -0.17), 0.045, 0.03, tin, v=20, parent=root)
    K.cyl("lantern cap", (0, 0, -0.07), 0.04, 0.03, tin, v=20, parent=root)
    K.sph("lantern globe", (0, 0, -0.12), 0.042, lw_emit("lantern glow", "#FFB050", 3.0), scale=(1, 1, 1.25), seg=16, ring=10, parent=root)
    for sx in (-1, 1):
        K.cyl("lantern frame wire", (sx * 0.04, 0, -0.12), 0.004, 0.09, tin, v=6, parent=root)
        K.cyl("lantern bail", (sx * 0.03, 0, -0.03), 0.003, 0.07, lw_metal("bail wire", "#55595E"), rot=(0, sx * math.radians(30), 0), v=6, parent=root)
    K.cyl("lantern bail top", (0, 0, 0.0), 0.004, 0.035, lw_metal("bail wire", "#55595E"), rot=(0, math.pi / 2, 0), v=6, parent=root)
    lw_local(root)
    root.scale = (1.4, 1.4, 1.4)
    L = lw_point("lantern light", (0, 0, -0.12), 25.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.12)
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


def s5_fire(name, loc, size, rnd):
    """flames on a burning house: a cluster of hot tongues and a column of smoke billows over it"""
    fm = bpy.data.materials.get("house fire") or lw_emit("house fire", "#FF5000", 1.2)
    core = bpy.data.materials.get("house fire core") or lw_emit("house fire core", "#FF9020", 1.6)
    tongues = []
    for k in range(7):
        x = loc[0] + rnd.uniform(-0.45, 0.45) * size; y = loc[1] + rnd.uniform(-0.3, 0.3) * size
        o = K.sph(f"{name} flame {k}", (x, y, loc[2] + 0.25 * size), 0.18 * size, core if k % 3 == 0 else fm, scale=(0.8, 0.8, 2.2), seg=12, ring=8)
        tx = bpy.data.textures.new(f"{name} flame tex {k}", 'CLOUDS'); tx.noise_scale = 0.12 * size
        dm = o.modifiers.new("lick", 'DISPLACE'); dm.texture = tx; dm.strength = 0.12 * size
        tongues.append(o)
    ash = lw_smoke_mat("fire smoke", density=2.5, col=(0.22, 0.21, 0.21))
    smoke = [lw_puff(f"{name} smoke {k}", (loc[0] + rnd.uniform(-0.4, 0.4) - 0.5 * k, loc[1] + 0.3 * k, loc[2] + 1.0 * size + 1.3 * k * size), (0.8 + 0.4 * k) * size, ash)
             for k in range(6)]
    L = lw_point(f"{name} fire light", (loc[0], loc[1] - 0.6, loc[2] + 0.6 * size), 900.0 * size, col=(1.0, 0.45, 0.15), r=0.4)
    return tongues, smoke, L


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, the town on the slope above, the earth wall round it, the black lava at the edge of town
    and three houses there still burning under their smoke."""
    rnd = lw_random.Random(61)
    lw_grid("town slope", -24, 24, 1.2, 40, 80, 80, s5_slope_z, lava_field_mat())
    K.box("quay concrete", (3.0, -2.0, -0.12), (10.4, 7.0, 0.24), lw_noise("quay concrete", "#8A8782", "#A5A29B", scale=10, rough=0.85, bump=0.4), bev=0.02)
    K.box("quay edge", (S5_EDGE_X + 0.1, -2.0, 0.03), (0.2, 7.0, 0.06), K.mat("quay edge paint", "#D9B32E", rough=0.6), bev=0.01)
    for k in range(5):
        K.cyl("quay bollard", (S5_EDGE_X + 0.35, -4.0 + 1.6 * k, 0.1), 0.07, 0.2, lw_metal("bollard", "#2E3033"), v=16)
    water = bpy.data.materials.new("harbour water"); water.use_nodes = True; wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (*K.lin("#1E3440"), 1); wb.inputs["Roughness"].default_value = 0.06
    wt = water.node_tree; nz = wt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; bp = wt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    wt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); wt.links.new(bp.outputs["Normal"], wb.inputs["Normal"])
    K.box("harbour water", (-14, 0, -0.45), (24, 60, 0.02), water, bev=0)
    hull_cols = ("#2E5E8A", "#C33A2A", "#E9E4D6")
    for k, (y, c) in enumerate(zip((-1.2, 1.6, 4.6), hull_cols)):          # fishing boats moored along the quay
        x = S5_EDGE_X - 0.9
        K.box(f"fishing boat {k} hull", (x, y, -0.22), (1.1, 2.4, 0.55), lw_paint(f"hull {c}", c, rough=0.4), bev=0.18)
        K.box(f"fishing boat {k} wheelhouse", (x, y + 0.4, 0.3), (0.7, 0.7, 0.55), lw_paint("wheelhouse white", "#EDEBE4", rough=0.4), bev=0.05)
        K.box(f"fishing boat {k} window", (x, y + 0.04, 0.38), (0.55, 0.02, 0.18), K.mat("car glass", "#1E262C", rough=0.05, metal=0.3), bev=0.0)
        K.cyl(f"fishing boat {k} mast", (x, y - 0.5, 0.9), 0.025, 1.6, lw_metal("mast steel", "#8A8E92"), v=10)
    home = town_house("his town house", (1.45, 2.45, 0.0), yaw=0.0, w=2.0, d=1.6, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    wood = lw_noise("post wood", "#5A4632", "#7A6248", scale=12, rough=0.8, stretch=(1, 1, 8))
    K.box("lantern post", (S5_HOOK.x + 0.1, S5_HOOK.y, 0.36), (0.07, 0.07, 0.72), wood, bev=0.008)
    K.cyl("lantern hook", (S5_HOOK.x + 0.04, S5_HOOK.y, S5_HOOK.z + 0.01), 0.008, 0.09, lw_metal("hook iron", "#2E3033"), rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, (x, y) in enumerate(((4.0, 3.1), (6.4, 3.7), (8.8, 4.4))):     # his neighbours along the quay
        quay.append(town_house(f"quay house {k}", (x, y, 0.0), yaw=0.0, w=2.0, d=1.6, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], seed=50 + k))
    town = []
    spots = [(-3.6, 7.0), (-1.2, 8.4), (1.4, 9.2), (-4.4, 10.8), (3.4, 6.6), (-2.2, 12.6), (0.6, 12.0), (2.8, 11.2), (-6.0, 8.6), (5.2, 9.8)]
    for k, (x, y) in enumerate(spots):
        hs = town_house(f"town house up {k}", (x, y, s5_slope_z(x, y) - 0.05), yaw=rnd.uniform(-0.15, 0.15), w=rnd.uniform(1.8, 2.2), d=1.6,
                        roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=30 + k)
        town.append(hs)
    burning = []
    for k, (x, y) in enumerate(((7.4, 10.4), (9.6, 11.8), (11.4, 9.8))):     # at the lava's edge, right of the town
        z = s5_slope_z(x, y) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.3, 0.3), w=2.0, d=1.6, roof="#3A3230", wall="#6E655E", seed=40 + k)
        burning.append((hs, (x, y, z + 1.2)))
    lm = lava_mat("lava field fresh", heat=0.35, scale=2.5)
    out = [(6.0, 6.0), (16.0, 5.0), (22.0, 12.0), (20.0, 24.0), (8.0, 22.0), (6.2, 14.0), (5.8, 9.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.4, m=lm, seed=8, lumpy=0.2)
    flow.location.z = s5_slope_z(12, 12) - 0.1
    wall = earth_wall("earth wall", [(x, 17.0 + 0.03 * x * x) for x in range(-26, 8, 2)], h=4.4, crest=1.4, base=8.5, seed=14)

    def light():
        return iceland_light(sun_elev=6, sun_az=-55, sun=2.6, sky=0.4, warm=(1.0, 0.7, 0.5), haze=1.6)
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
    P0 = Vector((S5_HOOK.x - 1.0, S5_HOOK.y + 0.1, 0.0))
    STAND = Vector((S5_HOOK.x - 0.17, S5_HOOK.y + 0.1, 0.0))               # facing +X, the hook in front of his near shoulder
    data.place(P0.x, P0.y, 90.0)
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.15, T_WALK1)
    # ---- the burning houses: the flames lick and flicker, the smoke climbs
    for hs, loc in P["burning"]:
        tongues, smoke, L = s5_fire(hs["root"].name, loc, 1.0, rnd)
        for k, o in enumerate(tongues):
            s0 = o.scale.copy(); ph = rnd.uniform(0, 6.28); hz = rnd.uniform(2.5, 4.5)
            for f in range(1, NF + 1, 2):
                t = (f - 1) / FPS; q = 1 + 0.3 * math.sin(2 * math.pi * hz * t + ph)
                o.scale = (s0.x * (0.9 + 0.1 * q), s0.y * (0.9 + 0.1 * q), s0.z * q); o.keyframe_insert("scale", frame=f)
        for k, o in enumerate(smoke):
            z0 = o.location.z
            for f in range(1, NF + 1, 3):
                t = (f - 1) / FPS; o.location.z = z0 + 0.35 * t; o.location.x += 0.0; o.keyframe_insert("location", frame=f)
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = 900.0 * (1 + 0.25 * math.sin(2 * math.pi * 3.1 * t + rnd.uniform(0, 3))); L.data.keyframe_insert("energy", frame=f)
    # ---- a few windows light up across the dark town, one here, one there
    lit = []
    order = [(P["quay"][0], 1, 0.0), (P["town"][4], 0, 0.06), (P["quay"][2], 0, 0.12), (P["town"][1], 1, 0.19), (P["quay"][1], 1, 0.26), (P["town"][7], 0, 0.31)]
    for hs, wi, frac in order:
        lit.append(s5_lit_pane(hs, min(wi, len(hs["windows"]) - 1), T_WIN + frac * DUR))
    lit_houses = [hs for hs, _w, _f in order if hs in P["quay"]]
    # ---- his body: the walk up the quay, the lift to the hook, a step back, the turn to us, the spread hands
    sc.frame_set(F(T_WALK1)); bpy.context.view_layer.update()
    YAW_H = math.radians(90)
    for f in range(F(T_WALK1) + 1, F(T_TURN) + 1):
        t = (f - 1) / FPS
        p = STAND.copy()
        p.z += 0.03 * W(t, T_HANG - 0.3, 0.25) * (1 - W(t, T_LET, 0.3))                 # up on his toes to the hook
        p.x -= 0.12 * W(t, T_LET + 0.15, 0.5)
        yaw = YAW_H - math.radians(35) * W(t, T_WIN - 0.2, 0.5) - math.radians(45) * W(t, T_TURN - 0.45, 0.4)
        data._kobj(t, loc=tuple(p), rot=yaw)
    data.walk_to((STAND.x - 0.2, STAND.y - 0.42), T_TURN, T_ASK + 0.3)          # he comes down the quay to us
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
    data.reach(carry, hand_path, 0.0, T_LET, lead=0.05, back=None, elbow_out=0.35)
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
    # after the let-go: the near hand comes down, then both hands spread wide to us
    AK = {carry: [(T_LET + 0.4, (0.08, 0.1, -0.08)), (T_TURN - 0.4, (0.1, 0.12, 0.0)), (T_TURN, (0.09, 0.11, -0.06)), (T_ASK + 0.05, (0.08, 0.1, -0.07)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))],
          other: [(T_ASK + 0.05, (0.07, 0.1, -0.09)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))]}
    data.reach(carry, lw_hand(data, carry, AK[carry]), AK[carry][0][0], DUR + 0.3, lead=0.4, back=None, elbow_out=0.35)
    data.reach(other, lw_hand(data, other, AK[other]), AK[other][0][0], DUR + 0.3, lead=0.5, back=None, elbow_out=0.35)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((0.2, -2.4, 0.6))
    data.look_at(Vector((3.0, 0.0, 0.4)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)
    data.look_at(S5_HOOK, T_WALK1 - 0.4, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(Vector((4.0, 2.2, 0.75)), T_WIN + 0.05, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((6.4, 2.8, 0.75)), T_WIN + 0.12 * DUR, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(LENS, T_TURN + 0.1, max_yaw=50, blend=0.3)
    data.expression("sad", 0.1, T_HANG - 0.1, blend=0.25)
    data.expression("determined", T_HANG, T_WIN, blend=0.2)
    data.expression("pleased", T_WIN + 0.1, T_ASK - 0.05, blend=0.25)
    data.expression("wry", T_ASK, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low on the quay, the town and its burning edge up the slope behind him
    CAM = Vector((0.3, -2.4, 0.5)); LOOK = Vector((2.0, 9.0, 1.1))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 20.0, face_at=(0.42, 0.5), height=0.34, t=T_HANG)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=20.0, fstop=11.0)
    camera_path(cam, lambda t: (CAM + Vector((0.05, 0.12, 0.0)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))))
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
