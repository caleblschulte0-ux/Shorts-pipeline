"""THE REALISM KIT: the fire, smoke, steam, dust, lava, embers, houses, roads, ground, rocks, water and skies of every
3D short, built ONCE from what the judge panel has accepted, so no story builds them by hand again (2026-11-26).

Twenty-six board rounds of the lava short named the same hard defect, OFF THE LOOK, again and again: "flat flame
sprite", "Monopoly houses", "popcorn bombs", "clay smoke", "flat grey sky", "the fountain lights nothing", "one flat
green plane". Each was a thing a shot had built for itself out of spheres, boxes and a flat colour. The three shots
that passed (lava 3, 4 and 5) were made of the same few parts: a real Poly Haven sky, real scanned textures on every
surface, fire and smoke as a gas (never a mesh), lava as black crust with light in its seams, and a lamp beside
everything that glows. Those parts are lifted here and made general. The operator's rule is the bar: realistic, "the
realer the better", and nothing a hero touches may be flatter than the set behind it.

  REGISTRY            every element: its function, its group, one line saying what it is, and whether it glows
  brief()             the list a new story's brief and the proof loop's reviser are given (python fx_kit.py prints it)
  an element          a function with a realistic default. It returns a dict: "objects" (what it built), "lights"
                      (the lamps it cast), and whatever a stager needs (a root, a top, a rim). Every object carries
                      the custom property "fx" naming its element, which is how store/fx_lint.py knows it is the kit's.
  EMITS               an element that glows returns the lamp it casts. The wrapper REFUSES to return one without a
                      lamp, so "the fountain lights nothing" cannot be built from the kit.

A missing asset RAISES (ph_path): a silent stand-in is how a real world quietly renders as clay again. Assets are the
CC0 Poly Haven files of the orphan branch data3d-assets, unpacked to <repo>/cache/polyhaven (POLYHAVEN_DIR overrides);
add an id to .github/triggers/data3d_assets to fetch another. Where an element names a second choice, it is another
REAL asset, and the element says so in its "fallback".

Time: an element that moves reads the scene's own frame range and the one clock (tools/data3d/clock.py).
Run inside Blender's Python (the bpy wheel). Imported without bpy, only REGISTRY and brief() work (the tests, the docs).
"""
import functools, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path: sys.path.insert(0, _p)
from clock import FPS, F
try:
    import bpy, bmesh
    from mathutils import Vector, Matrix, Euler
    import scene_kit as K
except ImportError:           # the registry and the brief are read without Blender
    bpy = None

PH = os.environ.get("POLYHAVEN_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "cache", "polyhaven")
REGISTRY = {}
GROUPS = ("sky", "ground", "built", "fire", "lava", "water")
HOT = (1.0, 0.45, 0.14)      # the colour of light off fire and lava


def element(group, what, emits=False):
    """register an element. An emitting one must return a lamp; every object and lamp it built is tagged."""
    assert group in GROUPS, group

    def deco(fn):
        @functools.wraps(fn)
        def run(*a, **k):
            out = fn(*a, **k)
            if not isinstance(out, dict) or "objects" not in out:
                raise TypeError(f"fx_kit.{fn.__name__} must return a dict with 'objects'")
            out.setdefault("lights", [])
            if emits and not out["lights"]:
                raise RuntimeError(f"fx_kit.{fn.__name__} glows and returned no light: an emitter always casts its light")
            for o in out["objects"]:
                o["fx"] = fn.__name__
            for o in out["lights"]:
                o["fx"] = fn.__name__; o["fx_light"] = 1
            return out
        REGISTRY[fn.__name__] = {"fn": run, "group": group, "what": what, "emits": emits}
        return run
    return deco


def brief():
    """what exists, for a new story's brief, the README and the proof loop's reviser"""
    lines = ["THE REALISM KIT (store/fx_kit.py). Build these with the kit, never by hand from spheres, boxes and a flat colour:",
             "the panel fails a hand-built one as OFF THE LOOK, and store/fx_lint.py refuses it before a frame renders."]
    for g in GROUPS:
        for name, e in REGISTRY.items():
            if e["group"] == g:
                lines.append(f"- FX.{name}: {e['what']}" + (" (casts its own light)" if e["emits"] else ""))
    lines.append("Anything that glows and is not from the kit needs a lamp beside it (FX.glow_light), or it reads as pasted on.")
    return "\n".join(lines)


# ---------------------------------------------------------------- scene, time, small things
def _sc():
    return bpy.context.scene


def _nf():
    return max(1, _sc().frame_end)


def _dur():
    return _nf() / FPS


def _link(o):
    bpy.context.collection.objects.link(o); return o


def _fcurves(action):
    if hasattr(action, "fcurves"): return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips for cb in strip.channelbags for fc in cb.fcurves]


def _linear(idb, path_part):
    ad = idb.animation_data
    if ad and ad.action:
        for c in _fcurves(ad.action):
            if path_part in c.data_path:
                for kp in c.keyframe_points: kp.interpolation = 'LINEAR'


def vn(x, y, seed=0):
    """smooth value noise, -1..1 (terrain, lumps)"""
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 982451653) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    i, j = math.floor(x), math.floor(y); u, v = x - i, y - j
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
    a, b, c, d = h(i, j), h(i + 1, j), h(i, j + 1), h(i + 1, j + 1)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(x, y, seed=0, octaves=4):
    s, a, f = 0.0, 0.5, 1.0
    for k in range(octaves):
        s += a * vn(x * f, y * f, seed + k); a *= 0.5; f *= 2.0
    return s


def point(name, loc, energy, col=HOT, r=0.3):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = energy; ld.color = col; ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld); o.location = loc
    return _link(o)


def flicker(lights, seed=0.0, t_end=None, depth=0.22):
    """fire light is never steady: every lamp's power wanders, out of step with the others"""
    nf = F(t_end) + 1 if t_end is not None else _nf()
    for f in range(1, nf + 1, 2):
        t = (f - 1) / FPS
        for j, L in enumerate(lights):
            e0 = L.get("e0") or L.data.energy; L["e0"] = e0
            q = 1 + depth * math.sin(2 * math.pi * (2.7 + 0.4 * j) * t + 1.7 * j + seed) + 0.55 * depth * math.sin(2 * math.pi * 7.1 * t + j)
            L.data.energy = e0 * q; L.data.keyframe_insert("energy", frame=f)


# ---------------------------------------------------------------- real assets
def ph_path(*parts):
    p = os.path.join(PH, *parts)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Poly Haven asset missing: {p} (add it to .github/triggers/data3d_assets, then unpack "
                                f"data3d-assets into cache/: git archive origin/data3d-assets polyhaven | tar -x -C cache)")
    return p


def have(*parts):
    return os.path.exists(os.path.join(PH, *parts))


def first(*aids):
    """the first of these texture sets that is unpacked, and whether it was the first choice"""
    for k, a in enumerate(aids):
        if have(a, "textures"): return a, k > 0
    raise FileNotFoundError(f"none of the Poly Haven textures {aids} is unpacked in {PH}")


def ph_mat(aid, scale=1.0, tint=None, name=None, rough=None, bump=1.0, res="1k", paint=False, weather=0.0, seed=0, coord="Object"):
    """a real surface: a Poly Haven texture set (colour, normal, roughness) box-projected, `scale` metres a tile.
    tint multiplies the colour. paint: the tint is PAINT over the scan (its light and dark kept, not bare metal).
    weather (0..1): the paint is worn through in patches and streaks to the scan's own rusty, dirty surface, and grime
    runs down it, so a painted wall or roof is never one clean flat colour."""
    name = name or f"fx {aid} {scale} {tint} {paint} {weather} {seed}"
    m = bpy.data.materials.get(name)
    if m: return m
    d = ph_path(aid, "textures")
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    tc = N("ShaderNodeTexCoord"); mp = N("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale,) * 3
    L(tc.outputs[coord], mp.inputs["Vector"])

    def img(kind, data=True):
        f = os.path.join(d, f"{aid}_{kind}_{res}.jpg")
        if not os.path.exists(f): return None
        t = N("ShaderNodeTexImage"); t.image = bpy.data.images.load(f, check_existing=True); t.projection = 'BOX'; t.projection_blend = 0.2
        if data: t.image.colorspace_settings.name = 'Non-Color'
        L(mp.outputs["Vector"], t.inputs["Vector"]); return t
    dif = img("diff", False); col = raw = dif.outputs["Color"]
    if tint and paint:
        bw = N("ShaderNodeRGBToBW"); L(col, bw.inputs[0])
        mr = N("ShaderNodeMapRange"); L(bw.outputs[0], mr.inputs["Value"]); mr.clamp = False
        mr.inputs["From Max"].default_value = 0.35; mr.inputs["To Min"].default_value = 0.45; mr.inputs["To Max"].default_value = 1.0
        cc = N("ShaderNodeCombineColor"); [L(mr.outputs["Result"], cc.inputs[i]) for i in range(3)]
        mx = N("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        L(cc.outputs[0], mx.inputs[6]); mx.inputs[7].default_value = (*K.lin(tint), 1); col = mx.outputs[2]
    elif tint:
        mx = N("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        L(col, mx.inputs[6]); mx.inputs[7].default_value = (*K.lin(tint), 1); col = mx.outputs[2]
    worn = None
    if weather:
        wm = N("ShaderNodeMapping"); wm.inputs["Scale"].default_value = (1.3, 1.3, 0.22); wm.inputs["Location"].default_value = (seed * 2.3, seed * 1.1, seed * 0.7)
        L(tc.outputs[coord], wm.inputs["Vector"])
        wn = N("ShaderNodeTexNoise"); wn.inputs["Scale"].default_value = 2.2; wn.inputs["Detail"].default_value = 8; wn.inputs["Roughness"].default_value = 0.7
        L(wm.outputs["Vector"], wn.inputs["Vector"])
        wr = N("ShaderNodeMapRange"); L(wn.outputs["Fac"], wr.inputs["Value"])
        wr.inputs["From Min"].default_value = 0.66 - 0.2 * weather; wr.inputs["From Max"].default_value = 0.74 - 0.14 * weather
        worn = wr.outputs["Result"]                     # 1 where the paint is gone
        rust = N("ShaderNodeMix"); rust.data_type = 'RGBA'; rust.blend_type = 'MULTIPLY'; rust.inputs[0].default_value = 1.0
        L(raw, rust.inputs[6]); rust.inputs[7].default_value = (*K.lin("#8A6A52"), 1)
        w1 = N("ShaderNodeMix"); w1.data_type = 'RGBA'; L(worn, w1.inputs[0]); L(col, w1.inputs[6]); L(rust.outputs[2], w1.inputs[7])
        gm = N("ShaderNodeMapping"); gm.inputs["Scale"].default_value = (5.0, 5.0, 0.35); L(tc.outputs[coord], gm.inputs["Vector"])
        gn = N("ShaderNodeTexNoise"); gn.inputs["Scale"].default_value = 1.6; gn.inputs["Detail"].default_value = 5; L(gm.outputs["Vector"], gn.inputs["Vector"])
        gr = N("ShaderNodeMapRange"); L(gn.outputs["Fac"], gr.inputs["Value"]); gr.inputs["From Min"].default_value = 0.35; gr.inputs["From Max"].default_value = 0.75
        gr.inputs["To Min"].default_value = 1.0 - 0.45 * weather; gr.inputs["To Max"].default_value = 1.0
        gc = N("ShaderNodeCombineColor"); [L(gr.outputs["Result"], gc.inputs[i]) for i in range(3)]
        w2 = N("ShaderNodeMix"); w2.data_type = 'RGBA'; w2.blend_type = 'MULTIPLY'; w2.inputs[0].default_value = 1.0
        L(w1.outputs[2], w2.inputs[6]); L(gc.outputs[0], w2.inputs[7]); col = w2.outputs[2]
    L(col, bs.inputs["Base Color"])
    arm = img("arm"); rg = img("rough")
    if arm:
        sp = N("ShaderNodeSeparateColor"); L(arm.outputs["Color"], sp.inputs[0])
        L(sp.outputs[1], bs.inputs["Roughness"]); L(sp.outputs[2], bs.inputs["Metallic"])
    elif rg:
        L(rg.outputs["Color"], bs.inputs["Roughness"])
    if paint:
        for l in list(bs.inputs["Metallic"].links): nt.links.remove(l)
        bs.inputs["Metallic"].default_value = 0.0
    if rough is not None:
        for l in list(bs.inputs["Roughness"].links): nt.links.remove(l)
        if worn is not None:                            # bare, rusted patches are rougher than the paint
            rr = N("ShaderNodeMapRange"); L(worn, rr.inputs["Value"]); rr.inputs["To Min"].default_value = rough; rr.inputs["To Max"].default_value = 0.9
            L(rr.outputs["Result"], bs.inputs["Roughness"])
        else:
            bs.inputs["Roughness"].default_value = rough
    nor = img("nor_gl")
    if nor:
        nm = N("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump
        L(nor.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], bs.inputs["Normal"])
    return m


_MODELS = {}


def ph_model(aid, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0, name=None, res="1k", only=None, parent=None):
    """a real prop: a Poly Haven glTF model, imported once and linked again for every copy, under one empty"""
    if aid not in _MODELS or any(o.name not in bpy.data.objects for o in _MODELS[aid]):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=ph_path(aid, f"{aid}_{res}.gltf"))
        objs = [o for o in bpy.data.objects if o not in before]
        for o in objs:
            for c in o.users_collection: c.objects.unlink(o)
        _MODELS[aid] = objs
    src = [o for o in _MODELS[aid] if not only or any(o.name.split(".")[0] == n_ or o.name.startswith(n_ + ".") for n_ in only)]
    root = K.empty(name or aid, tuple(loc), parent=parent)
    copies = {}
    for o in src:
        c = o.copy(); copies[o] = c; _link(c); c.name = f"{root.name} {o.name.split('.')[0]}"
    for o, c in copies.items():
        c.parent = copies.get(o.parent, root)
        if o.parent not in copies: c.matrix_parent_inverse = Matrix.Identity(4)
    root.rotation_euler = Euler(rot); root.scale = (scale,) * 3
    return root


def grid(name, x0, x1, y0, y1, zfn, m, step=0.25):
    """a patch of ground: a grid whose height is zfn(x, y)"""
    nx = max(2, int((x1 - x0) / step)); ny = max(2, int((y1 - y0) / step))
    bm = bmesh.new(); vs = []
    for j in range(ny + 1):
        vs.append([bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny,
                                 zfn(x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny))) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(m)
    return _link(bpy.data.objects.new(name, me))


_BLOCKS = {}


def block(name, loc, r, m, rnd, squash=0.7):
    """one angular broken rock: a coarse icosahedron with its corners pulled about, flat-faced, eight shapes a material"""
    key = (m.name, rnd.randrange(8))
    me = _BLOCKS.get(key)
    if me is None or me.name not in bpy.data.meshes:
        rk = random.Random(sum(map(ord, key[0])) * 8 + key[1])
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in bm.verts:
            v.co *= rk.uniform(0.72, 1.15) * (1 + 0.12 * vn(v.co.x * 3 + key[1], v.co.y * 3 + v.co.z * 2, key[1])); v.co.z = max(v.co.z, -0.35)
        me = bpy.data.meshes.new("fx rock block"); bm.to_mesh(me); bm.free(); me.materials.append(m)
        for p_ in me.polygons: p_.use_smooth = False
        _BLOCKS[key] = me
    o = _link(bpy.data.objects.new(name, me)); o.location = loc
    o.scale = (r, r * rnd.uniform(0.7, 1.2), r * squash * rnd.uniform(0.75, 1.2)); o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.3))
    return o


# ================================================================ SKY
# preset -> (hdri, strength, sun lamp W/m2, sun colour, sun's angular size in degrees, second choice)
SKIES = {
    "day":       ("kloofendal_48d_partly_cloudy_puresky", 0.60, 3.0, (1.0, 0.93, 0.82), 2.5, None),
    "dawn":      ("qwantani_sunrise_puresky",             0.85, 3.0, (1.0, 0.66, 0.50), 3.0, None),
    "dusk":      ("qwantani_dusk_2_puresky",              0.90, 1.6, (1.0, 0.60, 0.45), 4.0, None),
    "sunset":    ("industrial_sunset_puresky",            0.80, 2.4, (1.0, 0.62, 0.40), 3.0, None),
    "overcast":  ("kloofendal_overcast_puresky",          1.00, 0.5, (1.0, 0.97, 0.94), 25.0, None),
    "noon":      ("qwantani_noon_puresky",                0.55, 3.4, (1.0, 0.96, 0.90), 2.0, "day"),
    "afternoon": ("qwantani_afternoon_puresky",           0.60, 3.2, (1.0, 0.90, 0.76), 2.5, "day"),
    "storm":     ("wasteland_clouds_puresky",             0.90, 0.8, (1.0, 0.95, 0.90), 15.0, "overcast"),
}
_SUN = {}


def hdri_sun(img):
    """where the sun is in an equirectangular sky: (azimuth angle about Z of the image's own frame, elevation), radians,
    from its brightest pixels. A lamp aimed anywhere else throws a second set of shadows."""
    key = img.filepath
    if key in _SUN: return _SUN[key]
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[:, :, :3].sum(axis=2)
    sy, sx = max(1, h // 128), max(1, w // 256)
    small = lum[:h // sy * sy, :w // sx * sx].reshape(h // sy, sy, w // sx, sx).mean(axis=(1, 3))
    small[: small.shape[0] // 2] = 0                    # the sun is above the horizon
    j, i = np.unravel_index(int(small.argmax()), small.shape)
    u = (i + 0.5) / small.shape[1]; v = (j + 0.5) / small.shape[0]
    _SUN[key] = ((u - 0.5) * 2 * math.pi, (v - 0.5) * math.pi)
    return _SUN[key]


@element("sky", "a REAL sky (Poly Haven HDRI) that lights the scene, with the sun lamp aimed at the sky's own sun: "
                "presets day, dawn, dusk, sunset, overcast, noon, afternoon, storm; sun_az turns the whole sky", emits=True)
def sky(preset="day", sun_az=None, strength=None, sun=None, res="2k"):
    """the world becomes the preset's HDRI. sun_az (degrees, 0 = the sun straight behind the camera at -Y, negative =
    camera left) turns the sky so its sun stands there; None leaves the sky as shot. The sun LAMP is aimed at the
    sky's sun, so there is one set of shadows. Returns dict(sun, sun_dir, preset, fallback)."""
    fallback = None
    aid, st, se, col, ang, second = SKIES[preset]
    if not have("hdri", f"{aid}_{res}.hdr") and second:
        fallback = f"sky {preset!r} ({aid}) is not unpacked: using {second!r}"; print("FX FALLBACK " + fallback, flush=True)
        aid, st, se, col, ang, _ = SKIES[second]
    sc = _sc(); w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld"); bg = nt.nodes.new("ShaderNodeBackground"); bg.name = "Background"
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(ph_path("hdri", f"{aid}_{res}.hdr"), check_existing=True)
    phi, el = hdri_sun(env.image)
    az_img = math.atan2(math.sin(phi), -math.cos(phi))            # the sun's direction about Z in the image's frame
    want = az_img if sun_az is None else math.atan2(-math.cos(math.radians(sun_az)), math.sin(math.radians(sun_az)))
    rot = az_img - want                                          # the mapping turns the lookup, so the sky turns by -rot
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = st if strength is None else strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    el = max(el, math.radians(4))
    d = Vector((math.cos(want) * math.cos(el), math.sin(want) * math.cos(el), math.sin(el)))
    ld = bpy.data.lights.new("sun", 'SUN'); ld.energy = se if sun is None else sun; ld.angle = math.radians(ang); ld.color = col
    o = _link(bpy.data.objects.new("sun", ld)); o.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return dict(objects=[], lights=[o], sun=o, sun_dir=d, preset=preset, fallback=fallback, background=bg)


# ================================================================ GROUND, ROAD, ROCK
# kind -> (texture choices, metres a tile, tint)
GROUNDS = {
    "rock":    (("aerial_rocks_02",), 3.0, None),
    "lava_field": (("aerial_rocks_02",), 3.0, "#5A5650"),
    "gravel":  (("gravel_floor_02",), 1.6, "#8E887E"),
    "trail":   (("rocky_trail",), 2.0, None),
    "scree":   (("gray_rocks",), 1.8, None),
    "burned":  (("burned_ground_01",), 2.0, None),
    "grass":   (("sparse_grass", "leafy_grass", "rocky_trail"), 2.0, None),
    "mud":     (("brown_mud", "rocky_trail"), 2.0, None),
    "sand":    (("coast_sand_rocks_02", "gravel_floor_02"), 2.0, None),
    "snow":    (("snow_02", "gray_rocks"), 2.0, None),
    "mountain": (("rocky_terrain_02", "aerial_rocks_02"), 4.0, None),
}


@element("ground", "real scanned ground with relief (kinds: rock, lava_field, gravel, trail, scree, burned, grass, mud, "
                   "sand, snow, mountain): never a flat plane of one colour")
def ground(kind="gravel", area=(-8, 8, -6, 12), zfn=None, relief=0.06, seed=0, step=0.25, tint=None, name=None):
    """a patch of ground over area (x0, x1, y0, y1). zfn(x, y) gives its height; without one it rolls gently by
    `relief` metres. Returns dict(ground, zfn, fallback)."""
    aids, scale, t0 = GROUNDS[kind]
    aid, second = first(*aids)
    fallback = f"ground {kind!r}: {aids[0]} is not unpacked, using {aid}" if second else None
    if fallback: print("FX FALLBACK " + fallback, flush=True)
    z = zfn or (lambda x, y: relief * fbm(x * 0.35, y * 0.35, seed))
    m = ph_mat(aid, scale=scale, tint=tint or t0, name=f"fx ground {kind} {tint}", bump=1.4)
    g = grid(name or f"{kind} ground", area[0], area[1], area[2], area[3], z, m, step=step)
    return dict(objects=[g], ground=g, zfn=z, fallback=fallback)


@element("ground", "a real asphalt road (scanned asphalt, a worn centre line, gravel shoulders with loose stones)")
def road(a=(0, -6), b=(0, 14), width=2.4, line=True, shoulders=0.7, seed=0, z=0.0, name="road"):
    """a straight road from a to b (x, y), slightly crowned. Returns dict(root, deck)."""
    A = Vector((a[0], a[1], 0)); B = Vector((b[0], b[1], 0)); L_ = (B - A).length; mid = (A + B) / 2
    yaw = math.atan2((B - A).y, (B - A).x)
    root = K.empty(name, (mid.x, mid.y, z)); rnd = random.Random(seed)
    asp = ph_mat("asphalt_02", scale=1.6, name="fx asphalt", bump=1.2)
    deck = grid(name + " deck", -L_ / 2, L_ / 2, -width / 2, width / 2,
                lambda x, y: 0.02 + 0.025 * (1 - (2 * y / width) ** 2) + 0.004 * fbm(x * 2, y * 2, seed), asp, step=0.2)
    objs = [deck]
    if shoulders:
        gr = ph_mat("gravel_floor_02", scale=1.3, tint="#8F8A80", name="fx road shoulder", bump=1.5)
        for sg in (-1, 1):
            y0 = sg * width / 2; y1 = sg * (width / 2 + shoulders)
            objs.append(grid(name + " shoulder", -L_ / 2, L_ / 2, min(y0, y1), max(y0, y1),
                             lambda x, y: 0.022 - 0.03 * (abs(y) - width / 2) / shoulders + 0.008 * fbm(x * 3, y * 3, seed + 2), gr, step=0.2))
        stone = ph_mat("gray_rocks", scale=0.5, name="fx road stone", bump=1.5)
        for k in range(int(L_ * 5)):
            sg = rnd.choice((-1, 1)); x = rnd.uniform(-L_ / 2, L_ / 2); y = sg * (width / 2 + rnd.uniform(-0.05, shoulders))
            objs.append(block(name + " stone", (x, y, 0.02), rnd.uniform(0.012, 0.04), stone, rnd))
    if line:
        paint = ph_mat("asphalt_02", scale=0.9, tint="#E9E4D2", name="fx road paint", paint=True, weather=0.75, rough=0.6, seed=seed)
        x = -L_ / 2 + 0.4
        while x < L_ / 2 - 1.0:
            objs.append(K.box(name + " line", (x + 0.5, 0, 0.0452), (1.0, 0.07, 0.004), paint, bev=0.0)); x += 2.2
    for o in objs:
        o.parent = root
    root.rotation_euler = (0, 0, yaw)
    return dict(objects=objs, root=root, deck=deck, width=width)


ROCK_MODELS = ("boulder_01", "rock_moss_set_02")


@element("ground", "real scanned boulders (Poly Haven models) and broken stones scattered over a patch, each turned "
                   "and sized differently: never a sphere, never evenly spaced")
def rocks(n=14, area=(-4, 4, 0, 6), zfn=None, size=(0.25, 0.9), seed=0, avoid=None, stones=3.0, name="rock", tint="#6A6660"):
    """n boulders over area (x0, x1, y0, y1), `size` their span in metres, plus `stones` small broken stones for each.
    avoid(x, y) keeps a place clear. Returns dict(boulders, stones)."""
    rnd = random.Random(seed); z = zfn or (lambda x, y: 0.0)
    boulders = []; small = []; objs = []
    sm = ph_mat("gray_rocks", scale=0.7, tint=tint, name=f"fx stone {tint}", bump=1.8)
    for k in range(n):
        x = rnd.uniform(area[0], area[1]); y = rnd.uniform(area[2], area[3])
        if avoid and avoid(x, y): continue
        aid = ROCK_MODELS[0] if rnd.random() < 0.5 or not have(ROCK_MODELS[1]) else ROCK_MODELS[1]
        r = ph_model(aid, (x, y, z(x, y)), rot=(rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), rnd.uniform(0, 6.3)), name=f"{name} boulder {k}")
        if aid == ROCK_MODELS[1]:                        # a set of several rocks side by side: keep one of them
            kids = [c for c in r.children if c.type == 'MESH']
            keep = kids[rnd.randrange(len(kids))] if kids else None
            for c in kids:
                if c is not keep: bpy.data.objects.remove(c, do_unlink=True)
            if keep: keep.location = (0, 0, 0)
        bpy.context.view_layer.update()
        ms = [c for c in r.children_recursive if c.type == 'MESH']
        pts = [c.matrix_world @ Vector(b) for c in ms for b in c.bound_box]
        span = max(max(p.x for p in pts) - min(p.x for p in pts), max(p.y for p in pts) - min(p.y for p in pts), 1e-3)
        s = rnd.uniform(*size) / span; r.scale = (s, s * rnd.uniform(0.85, 1.15), s * rnd.uniform(0.7, 1.1))
        bpy.context.view_layer.update()
        zmin = min((c.matrix_world @ Vector(b)).z for c in ms for b in c.bound_box)
        r.location.z += z(x, y) - zmin - 0.04 * rnd.uniform(*size)       # sat INTO the ground a little, never perched on it
        boulders.append(r); objs += ms
        for j in range(int(stones + rnd.random())):
            sx = x + rnd.uniform(-1, 1) * size[1] * 0.9; sy = y + rnd.uniform(-1, 1) * size[1] * 0.9
            if avoid and avoid(sx, sy): continue
            rr = rnd.uniform(0.03, 0.12) * size[1]
            small.append(block(f"{name} stone", (sx, sy, z(sx, sy) + rr * 0.25), rr, sm, rnd))
    return dict(objects=objs + small, boulders=boulders, stones=small)


# ================================================================ BUILT: the house
ROOFS = ("#A63A30", "#2F5878", "#3F6B48", "#B8943E", "#8E3A30", "#2E6468", "#7A7F84")      # oxide red, blue, green, ochre tin; bare grey
WALLS = ("#EDEAE2", "#B9CCD5", "#E2D3A0", "#A84A3E", "#DFD9CC", "#7E9584", "#D2C3AF")
DOORS = ("#EDEBE4", "#2F4A5E", "#8E2E26", "#3E5A3C", "#C9A23A", "#5A4632")


def _emit(name, hexc, strength):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*K.lin(hexc), 1); bs.inputs["Emission Color"].default_value = (*K.lin(hexc), 1)
    bs.inputs["Emission Strength"].default_value = strength
    return m


def _char(m, name, seed=0):
    """a copy of a surface, CHARRED: soot in patches climbing it, the paint scorched brown at their edges"""
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


def _hexmix(a, b, u):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(round(x + (y - x) * u)):02X}" for x, y in zip(ca, cb))


def _local(root):
    for o in root.children_recursive:
        o.matrix_parent_inverse.identity()
    return root


@element("built", "a real small house: weathered painted corrugated tin (scanned) on a concrete base, a coloured tin "
                  "roof with rust and grime, gutters, downpipes, corner boards, a chimney, paned windows, a door and "
                  "steps; size, storeys, pitch and colours vary with seed; burn>0 chars it and breaks its roof open; "
                  "lit windows cast their light", emits=False)
def house(name="house", loc=(0, 0, 0), yaw=0.0, w=None, d=None, h=1.3, roof=None, wall=None, lit=(), seed=0, storeys=None,
          base=None, pitch=None, door=None, burn=0.0, weather=0.55):
    """a house at the 3D shorts' scale (a storey ~1.3 m beside Data's 0.95 m). Built facing -Y about its origin, placed
    at loc/yaw. roof / wall: hex colours (default: picked from ROOFS / WALLS by seed, never two primaries side by
    side by luck: vary the seed). weather (0..1): how worn the paint is. lit: indices of windows that are lit from
    inside (each gets a lamp just outside its pane). Returns dict(root, windows, w, d, h, top, gab, hole, fire_windows, yaw)."""
    rnd = random.Random(seed * 7919 + 13)
    storeys = storeys or (2 if rnd.random() < 0.55 else 1)
    w = w or rnd.uniform(3.4, 4.6); d = d or rnd.uniform(2.8, 3.4)
    base = base if base is not None else (rnd.choice((0.25, 0.3)) if storeys == 2 else rnd.choice((0.3, 0.75, 0.9)))
    pitch = math.radians(pitch if pitch is not None else rnd.uniform(34, 42))
    roof = roof or ROOFS[rnd.randrange(len(ROOFS))]; wall = wall or WALLS[rnd.randrange(len(WALLS))]
    door = door or DOORS[rnd.randrange(len(DOORS))]
    if burn:
        wall = _hexmix(wall, "#2A2522", 0.25 * burn); roof = _hexmix(roof, "#231F1D", 0.45); door = "#1E1A18"
    root = K.empty(name, (0, 0, 0)); objs = []
    B = lambda *a, **k: objs.append(K.box(*a, parent=root, **k)) or objs[-1]
    C = lambda *a, **k: objs.append(K.cyl(*a, parent=root, **k)) or objs[-1]
    hw = storeys * h; top = base + hw
    conc = ph_mat("concrete_wall_008", scale=1.6, name="fx house concrete")
    cl = ph_mat("corrugated_iron_02", scale=1.4, tint=wall, name=f"fx cladding {wall} {seed}", paint=True, rough=0.55, weather=weather * 0.7, seed=seed)
    rm = ph_mat("corrugated_iron_03", scale=1.2, tint=roof, name=f"fx tin roof {roof} {seed}", paint=True, rough=0.45, weather=weather, seed=seed + 5)
    if burn:
        cl = _char(cl, name + " charred cladding", seed); rm = _char(rm, name + " charred roof", seed + 1)
    trim = ph_mat("concrete_wall_008", scale=0.8, tint="#2B2623" if burn else "#EFEDE6", name="fx house trim char" if burn else "fx house trim", paint=True, rough=0.55)
    zinc = ph_mat("corrugated_iron_03", scale=0.5, tint="#8E9499", name="fx gutter zinc", bump=0.2)
    B(name + " base", (0, 0, base / 2), (w + 0.08, d + 0.08, base), conc, bev=0.01)
    B(name + " walls", (0, 0, base + hw / 2), (w, d, hw), cl, bev=0.01)
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
            r = B(name + " roof", (x, sg * run / 2, zc), (sw - (0.01 if broken else 0), half, 0.04), rm, bev=0.005)
            r.rotation_euler = (-sg * pitch, 0, 0)
            if broken and k == 4:                        # caved: sagging into the hole
                r.rotation_euler = (-sg * pitch + math.radians(22), math.radians(-8), 0); r.location.z -= 0.25
        if broken:
            sw = (w + 2 * ov) / 6; hx = -(w + 2 * ov) / 2 + sw * 3
            hole = (hx, -d / 4, top + gab * 0.35)
            beam = ph_mat("burned_ground_01", scale=0.5, tint="#3A302A", name="fx charred beam") if have("burned_ground_01", "textures") else K.mat("fx charred beam", "#15110F", rough=0.9)
            for j in range(4):                           # the charred rafters left across the hole
                bx = hx - sw * 0.85 + j * sw * 0.57
                rf = B(name + " rafter", (bx, -run / 2 + 0.05, zc - 0.05), (0.07, half * (0.75 + 0.2 * (j % 2)), 0.09), beam, bev=0.0)
                rf.rotation_euler = (pitch + (0.25 if j == 2 else 0.0), 0, 0)
    B(name + " ridge cap", (0, 0, top + gab + 0.02), (w + 2 * ov, 0.16, 0.05), rm, bev=0.01)
    for sx in (-1, 1):                                   # the gable ends: a triangle of cladding
        bm = bmesh.new()
        a_ = bm.verts.new((sx * w / 2, -d / 2, top)); b_ = bm.verts.new((sx * w / 2, d / 2, top)); c_ = bm.verts.new((sx * w / 2, 0, top + gab))
        bm.faces.new((a_, b_, c_)); me = bpy.data.meshes.new(name + " gable"); bm.to_mesh(me); bm.free(); me.materials.append(cl)
        g = _link(bpy.data.objects.new(name + " gable", me)); g.parent = root; objs.append(g)
        so = g.modifiers.new("t", 'SOLIDIFY'); so.thickness = 0.02
    fire_m = _emit(name + " window fire", "#FF7A1E", 9.0) if burn else None
    glass = K.mat("fx window glass", "#2B3238", rough=0.06, metal=0.3)
    glass_lit = _emit("fx window lit", "#FFC070", 2.5)
    nwin = max(2, int(round(w / 1.05)))
    xs = [-w / 2 + w * (k + 0.5) / nwin for k in range(nwin)]
    door_x = xs[0] if base < 0.5 else xs[0] + 0.05
    windows = []; fire_windows = []; lit_at = []

    def window(x, y, z, face, pane_m, side=False):
        fs = (0.6, 0.03, 0.66) if not side else (0.03, 0.6, 0.66)
        ps = (0.5, 0.01, 0.56) if not side else (0.01, 0.5, 0.56)
        off = Vector((0, -1, 0)) if not side else Vector((face, 0, 0))
        B(name + " window frame", tuple(Vector((x, y, z)) + off * 0.01), fs, trim, bev=0.006)
        p = B(name + " window pane", tuple(Vector((x, y, z)) + off * 0.026), ps, pane_m, bev=0.0)
        B(name + " window bar", tuple(Vector((x, y, z)) + off * 0.034), (fs[0] * 0.05 + 0.01, fs[1] * 0.05 + 0.01, 0.56), trim, bev=0.0)
        B(name + " window bar", tuple(Vector((x, y, z + 0.06)) + off * 0.034), (ps[0] + 0.005 if not side else 0.01, ps[1] + 0.005 if side else 0.01, 0.025), trim, bev=0.0)
        B(name + " sill", tuple(Vector((x, y, z - 0.35)) + off * 0.035), (0.68 if not side else 0.07, 0.07 if not side else 0.68, 0.03), trim, bev=0.004)
        return p
    for st in range(storeys):
        zc = base + st * h + h * 0.55
        for k, x in enumerate(xs):
            if st == 0 and k == 0:
                continue                                 # the door's bay
            idx = len(windows)
            on_fire = burn and (st == storeys - 1 or rnd.random() < 0.6)
            p = window(x, -d / 2, zc, -1, fire_m if on_fire else (glass_lit if idx in lit else glass))
            windows.append(p)
            if on_fire: fire_windows.append(((x, -d / 2 - 0.08, zc - 0.28), (0, -1, 0)))
            elif idx in lit: lit_at.append((x, -d / 2 - 0.35, zc - 0.1))
        for sx in (-1, 1):                               # one window in each gable end per storey
            window(sx * (w / 2 + 0.012), 0.0, zc, sx, fire_m if burn else glass, side=True)
    zd = base + 0.5
    B(name + " door", (door_x, -d / 2 - 0.015, zd), (0.5, 0.03, 1.0), ph_mat("corrugated_iron_03", scale=3.0, tint=door, name=f"fx door {door}", paint=True, rough=0.5, weather=weather * 0.5, bump=0.1), bev=0.008)
    B(name + " door frame", (door_x, -d / 2 - 0.008, zd + 0.02), (0.6, 0.02, 1.08), trim, bev=0.004)
    C(name + " door knob", (door_x + 0.17, -d / 2 - 0.04, zd - 0.02), 0.02, 0.025, zinc, rot=(math.pi / 2, 0, 0))
    nst = max(1, int(round(base / 0.17)))
    for k in range(nst):                                 # the steps up to a raised ground floor
        B(name + " step", (door_x, -d / 2 - 0.08 - 0.27 * (nst - 1 - k) - 0.14, (k + 1) * base / nst / 2), (0.8, 0.3, (k + 1) * base / nst), conc, bev=0.006)
    if base > 0.5:
        for sx in (-1, 1):
            C(name + " rail", (door_x + sx * 0.38, -d / 2 - 0.08 - 0.14 * nst, base + 0.45), 0.015, 0.9, zinc, v=8)
    B(name + " chimney", (w * rnd.choice((-0.28, 0.3)), 0.25, top + gab * 0.75), (0.32, 0.32, gab * 0.5 + 0.7), conc, bev=0.01)
    for cx in (-1, 1):
        for cy in (-1, 1):
            B(name + " corner board", (cx * (w / 2 + 0.01), cy * (d / 2 + 0.01), base + hw / 2), (0.06, 0.06, hw), trim, bev=0.004)
    for sg in (-1, 1):
        B(name + " fascia", (0, sg * (d / 2 + ov - 0.02), top - 0.06), (w + 2 * ov, 0.03, 0.1), trim, bev=0.004)
        C(name + " gutter", (0, sg * (d / 2 + ov + 0.02), top - 0.12), 0.045, w + 2 * ov, zinc, rot=(0, math.pi / 2, 0), v=10)
        C(name + " downpipe", (sg * (w / 2 + ov - 0.07), -(d / 2 + ov + 0.02), top / 2), 0.03, top - 0.1, zinc, v=8)
    _local(root)
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    Mw = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(yaw, 4, 'Z'); R = Matrix.Rotation(yaw, 3, 'Z')
    lights = [point(f"{name} window light {k}", tuple(Mw @ Vector(p)), 14.0, col=(1.0, 0.72, 0.4), r=0.2) for k, p in enumerate(lit_at)]
    return dict(objects=objs, lights=lights, root=root, windows=windows, w=w, d=d, h=h, top=top, gab=gab, yaw=yaw, storeys=storeys,
                base=base, roof=roof, wall=wall, hole=(Mw @ Vector(hole)) if hole else None,
                fire_windows=[(Mw @ Vector(p), R @ Vector(o)) for p, o in fire_windows])


# ================================================================ FIRE, SMOKE, STEAM, DUST: gas, never a mesh
class _X:
    """a little expression builder over a node tree: add(a, b), mul(a, b) ... take sockets or numbers"""
    OPS = dict(add='ADD', sub='SUBTRACT', mul='MULTIPLY', div='DIVIDE', mx='MAXIMUM', mn='MINIMUM', pw='POWER', sq='SQRT')

    def __init__(self, nt):
        self.nt = nt

    def __getattr__(self, k):
        if k not in self.OPS: raise AttributeError(k)

        def op(*a):
            n = self.nt.nodes.new("ShaderNodeMath"); n.operation = self.OPS[k]
            for i, x in enumerate(a):
                if isinstance(x, (int, float)): n.inputs[i].default_value = x
                else: self.nt.links.new(x, n.inputs[i])
            return n.outputs[0]
        return op

    def clamp01(self, x, lo=0.0, hi=1.0):
        n = self.nt.nodes.new("ShaderNodeMapRange"); n.clamp = True
        self.nt.links.new(x, n.inputs["Value"]); n.inputs["From Min"].default_value = lo; n.inputs["From Max"].default_value = hi
        return n.outputs["Result"]


def gas(name, base, w=1.6, h_fire=1.6, h_smoke=6.0, lean=(0.0, 0.0), t_end=None, seed=0.0, fire=5.0, smoke_d=3.5,
        smoke=(0.1, 0.095, 0.09), rise=1.4, keys=None, flame_d=3.9, spread=0.22, grow=False, ramp=None, lit=0.0, taper=1.0, fall=0.42):
    """A BURNING FIRE AND ITS SMOKE as ONE procedural volume (lava shots 3-5: the version the panel accepted). A tall
    box over `base`: the flame is a field of torn TONGUES that narrow as they climb (a cone of heat cut by turbulent
    noise that scrolls upward), hot yellow at its root, orange, then deep red at its tips; out of its top rolls a
    SOOT COLUMN that widens as it climbs, leans downwind, billows and thins away. Nothing in it is a sphere or a card.
    keys [(t, 0..1)]: how much gas there is when. lit (0..1): the smoke's underside glows with the fire's colour.
    The raw volume: stories call fire(), smoke_column(), steam(), dust_puff() or lava_fountain(), which add the light."""
    t_end = t_end if t_end is not None else _dur() + 1.0
    H = h_fire + h_smoke; lx, ly = lean
    W_ = w * 2.2 + abs(lx) * h_smoke * 2; D_ = w * 2.2 + abs(ly) * h_smoke * 2
    ctr = Vector(base) + Vector((lx * h_smoke * 0.5, ly * h_smoke * 0.5, H / 2))
    m = bpy.data.materials.new(name + " gas"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    N = nt.nodes.new; L = nt.links.new; X = _X(nt)
    out = N("ShaderNodeOutputMaterial"); pv = N("ShaderNodeVolumePrincipled")
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    x = X.add(sep.outputs[0], 0.0); y = X.add(sep.outputs[1], 0.0); z = X.add(sep.outputs[2], H / 2)
    zs = X.mul(X.clamp01(X.sub(z, h_fire * 0.6), 0.0, h_smoke), h_smoke)
    k_ = X.mul(X.mul(zs, zs), 1.0 / max(h_smoke, 0.1))
    ax = X.sub(x, X.add(-lx * h_smoke * 0.5, X.mul(k_, lx))); ay = X.sub(y, X.add(-ly * h_smoke * 0.5, X.mul(k_, ly)))
    tt = N("ShaderNodeValue"); tt.name = "fire time"
    cmb = N("ShaderNodeCombineXYZ"); L(ax, cmb.inputs[0]); L(ay, cmb.inputs[1]); L(X.sub(z, X.mul(tt.outputs[0], rise)), cmb.inputs[2])

    def noise(src, scale, detail, rough, wscale, woff):
        nz = N("ShaderNodeTexNoise"); nz.noise_dimensions = '4D'; nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail; nz.inputs["Roughness"].default_value = rough
        L(src, nz.inputs["Vector"]); L(X.add(X.mul(tt.outputs[0], wscale), seed + woff), nz.inputs["W"])
        return nz
    warp = noise(cmb.outputs[0], 0.9, 3.0, 0.5, 0.35, 0.0)
    wv = N("ShaderNodeVectorMath"); wv.operation = 'MULTIPLY_ADD'; L(warp.outputs["Color"], wv.inputs[0]); wv.inputs[1].default_value = (0.9, 0.9, 1.2)
    L(cmb.outputs[0], wv.inputs[2])
    wn = lambda scale, detail=6.0, rough=0.62, wscale=0.6: noise(wv.outputs[0], scale, detail, rough, wscale, 3.1).outputs["Fac"]
    r = X.sq(X.add(X.mul(ax, ax), X.mul(ay, ay)))
    zf = X.div(z, max(h_fire, 0.01))
    cone = X.sub(1.0, X.div(r, X.mx(X.mul(X.pw(X.clamp01(X.sub(1.05, zf)), taper), w * 0.55), 0.002)))   # taper < 1: a column (a jet), 1: a cone (a fire)
    # the tongues: the noise is stretched UP the flame, so heat stands in long licks that tear apart, and it outweighs
    # the cone, so the outline is ragged tongues of different heights (a smooth cone read as "a candle flame", "a bonfire")
    lick = N("ShaderNodeMapping"); lick.inputs["Scale"].default_value = (1.0, 1.0, 0.42); L(wv.outputs[0], lick.inputs["Vector"])
    tongues = noise(lick.outputs["Vector"], 2.6 / max(w, 0.3), 7.0, 0.72, 1.6, 3.1).outputs["Fac"]
    heat = X.sub(X.add(X.mul(tongues, 3.0), X.mul(cone, 0.55)), X.add(1.38, X.mul(zf, fall)))
    flame = X.clamp01(heat, 0.0, 0.55)
    zr = X.clamp01(X.sub(z, h_fire * 0.45), 0.0, h_smoke)
    rad = X.add(w * 0.35, X.mul(zr, w * 0.35 + h_smoke * spread))
    col = X.sub(1.0, X.div(r, rad))
    bil = X.add(X.mul(wn(0.55, 5.0, 0.72, 0.4), 0.7), X.mul(wn(1.6, 4.0, 0.6, 0.7), 0.45))
    sd = X.mul(X.clamp01(X.sub(X.add(X.mul(bil, 2.2), X.mul(col, 0.9)), 1.55), 0.0, 0.3),
               X.clamp01(col, -0.25, 0.1))               # nothing outside the column: a thin haze there rendered as vertical streaks
    fade = X.mul(X.clamp01(X.sub(z, h_fire * 0.35), 0.0, max(h_fire * 0.5, 0.05)), X.sub(1.0, X.clamp01(zr, 0.55, 1.0)))
    amt = N("ShaderNodeValue"); amt.name = "gas amount"; amt.outputs[0].default_value = 1.0
    smk = X.mul(X.mul(X.mul(sd, 0.3), fade), smoke_d)
    dens = X.mul(X.add(smk, X.mul(flame, flame_d)), amt.outputs[0])
    L(dens, pv.inputs["Density"])
    rp = N("ShaderNodeValToRGB"); L(flame, rp.inputs["Fac"]); el = rp.color_ramp.elements
    stops = ramp or (("#4A0800", 0.0), ("#C02400", 0.25), ("#FF6A0A", 0.55), ("#FFAA30", 0.8), ("#FFE09A", 1.0))
    el[0].position = stops[0][1]; el[0].color = (*K.lin(stops[0][0]), 1); el[1].position = stops[-1][1]; el[1].color = (*K.lin(stops[-1][0]), 1)
    for hx, pos in stops[1:-1]:
        el.new(pos).color = (*K.lin(hx), 1)
    L(rp.outputs["Color"], pv.inputs["Emission Color"])
    es = N("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "fire strength"; L(X.mul(X.pw(flame, 1.6), amt.outputs[0]), es.inputs[0]); es.inputs[1].default_value = fire
    em = es.outputs[0]
    if lit:                                              # the column's foot is lit from below by what burns under it
        under = X.mul(X.mul(X.sub(1.0, X.clamp01(zr, 0.0, 0.45)), smk), lit * fire * 0.05)
        em = X.add(em, under)
    L(em, pv.inputs["Emission Strength"])
    pv.inputs["Color"].default_value = (*smoke, 1); pv.inputs["Anisotropy"].default_value = 0.2
    L(pv.outputs[0], out.inputs["Volume"])
    o = K.box(name, tuple(ctr), (W_, D_, H), m, bev=0.0)
    o.visible_shadow = True
    for f in (1, F(t_end) + 1):
        tt.outputs[0].default_value = (f - 1) / FPS; tt.outputs[0].keyframe_insert("default_value", frame=f)
    if keys and keys[0][1] <= 0.0:                       # no gas yet: nothing there at all
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=max(1, F(keys[0][0])))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=max(1, F(keys[0][0])) + 1)
    for t, v in (keys or ()):
        amt.outputs[0].default_value = v; amt.outputs[0].keyframe_insert("default_value", frame=F(t))
        if grow:
            g = 0.3 + 0.7 * v
            o.scale = (g, g, g); o.location = (Vector(base) + Vector((lx * h_smoke * 0.5, ly * h_smoke * 0.5, 0)) * g + Vector((0, 0, H / 2 * g)))
            o.keyframe_insert("scale", frame=F(t)); o.keyframe_insert("location", frame=F(t))
    _linear(nt, 'nodes["fire time"]')
    try: m.cycles.volume_step_rate = 3.5
    except Exception: pass
    return o


def _keyed_light(L_, keys, e):
    """a lamp that comes and goes with its gas"""
    for t, v in keys:
        L_.data.energy = e * v; L_.data.keyframe_insert("energy", frame=F(t))


@element("fire", "a burning fire: torn flame tongues as a gas, a soot column rolling out of its top, and the warm "
                 "flickering lamp it casts on everything near it", emits=True)
def fire(base=(0, 0, 0), w=1.6, h=1.6, smoke=6.0, lean=(-0.3, 0.15), seed=0.0, power=None, keys=None, t_end=None, name="fire", brightness=9.0, flame_d=10.0):
    """a fire `w` wide whose flames stand `h` high over base, its smoke climbing `smoke` metres more and leaning
    (lean: metres sideways per metre up, squared). power: the lamp's watts (default by size: a 2.6 x 3.4 m blaze is
    about 2,300 W; lava shot 5 passed at 1,600). keys [(t, 0..1)]: it flares and dies. Returns dict(volume, light)."""
    v = gas(name, base, w=w, h_fire=h, h_smoke=smoke, lean=lean, t_end=t_end, seed=seed, fire=brightness, keys=keys, lit=0.6, flame_d=flame_d)
    e = power if power is not None else 260.0 * w * h
    b = Vector(base)
    L1 = point(name + " light", (b.x, b.y - 0.15 * w, b.z + 0.45 * h), e, r=max(0.15, 0.22 * w))
    L2 = point(name + " ground glow", (b.x, b.y, b.z + 0.12 * h + 0.05), e * 0.35, col=(1.0, 0.38, 0.1), r=max(0.1, 0.3 * w))
    if keys:
        for L_ in (L1, L2): _keyed_light(L_, keys, L_.data.energy)
    else:
        flicker([L1, L2], seed, t_end)
    return dict(objects=[v], lights=[L1, L2], volume=v, light=L1)


@element("fire", "a column of smoke as a gas: it billows, widens as it climbs, leans downwind and thins away (dark "
                 "soot by default; col for ash or white)")
def smoke_column(base=(0, 0, 0), w=1.4, h=7.0, lean=(-0.35, 0.15), col=(0.1, 0.095, 0.09), dens=3.5, seed=0.0, keys=None, t_end=None, rise=1.4, name="smoke"):
    v = gas(name, base, w=w, h_fire=0.3, h_smoke=h, lean=lean, t_end=t_end, seed=seed, fire=0.0, smoke_d=dens, smoke=col, rise=rise,
            keys=keys, flame_d=0.0, spread=0.26)
    return dict(objects=[v], volume=v)


@element("fire", "a burst of white steam as a gas that boils up, spreads and dies away on the keys it is given")
def steam(base=(0, 0, 0), w=1.2, h=4.0, keys=None, lean=(0.0, 0.0), dens=6.0, seed=0.0, t_end=None, name="steam", col=(0.9, 0.91, 0.93)):
    v = gas(name, base, w=w, h_fire=0.3, h_smoke=h, lean=lean, t_end=t_end, seed=seed, fire=0.0, smoke_d=dens, smoke=col, rise=2.2,
            keys=keys, flame_d=0.0, spread=0.3, grow=bool(keys))
    return dict(objects=[v], volume=v)


@element("fire", "a puff of dust kicked up from the ground: a low, wide, tan cloud of gas that swells and settles")
def dust_puff(base=(0, 0, 0), w=1.0, h=1.2, t0=0.0, dur=1.6, col=(0.62, 0.55, 0.45), dens=5.0, seed=0.0, lean=(0.15, 0.0), name="dust"):
    keys = [(t0, 0.0), (t0 + 0.18 * dur, 1.0), (t0 + 0.5 * dur, 0.7), (t0 + dur, 0.0)]
    v = gas(name, base, w=w, h_fire=0.15, h_smoke=h, lean=lean, seed=seed, fire=0.0, smoke_d=dens, smoke=col, rise=0.6,
            keys=keys, flame_d=0.0, spread=0.55, grow=True)
    return dict(objects=[v], volume=v, keys=keys)


@element("fire", "a house on fire from INSIDE: the blaze comes up through the hole in its roof into a soot column, "
                 "flames lick out of its upper windows, and its light falls on the ground and the walls beside it "
                 "(needs FX.house(burn=...))", emits=True)
def house_fire(hs, seed=0, t_end=None, brightness=5.0):
    if hs.get("hole") is None:
        raise ValueError("fx_kit.house_fire needs a house built with burn>0 (its roof broken open)")
    nm = hs["root"].name; hp = hs["hole"]; objs = []; lights = []
    objs.append(gas(nm + " blaze", (hp.x, hp.y + 0.3, hp.z - 1.2), w=2.6, h_fire=3.4, h_smoke=9.0, lean=(-0.6, 0.25), t_end=t_end,
                    seed=seed * 3.7 + 1.0, fire=brightness * 1.4, smoke_d=3.5, lit=0.6))
    for k, (p, o) in enumerate(hs["fire_windows"]):
        if p.z < hs["root"].location.z + hs["top"] - hs["h"] - 0.05:
            continue
        objs.append(gas(nm + f" window flame {k}", (p.x + o.x * 0.08, p.y + o.y * 0.08, p.z), w=0.85, h_fire=1.5, h_smoke=1.8,
                        lean=(o.x * 0.25, o.y * 0.25), t_end=t_end, seed=seed * 5.3 + k, fire=brightness * 1.6, smoke_d=2.4, rise=1.8))
        lights.append(point(nm + f" window light {k}", tuple(p + o * 0.7 + Vector((0, 0, 0.3))), 160.0, r=0.25))
    lights.append(point(nm + " blaze light", (hp.x, hp.y - 0.5, hp.z + 0.9), 1600.0, r=0.6))
    flicker(lights, seed, t_end)
    wf = bpy.data.materials.get(nm + " window fire")
    if wf:
        inp = wf.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]; s0 = inp.default_value
        for f in range(1, (F(t_end) + 1 if t_end is not None else _nf()) + 1, 2):
            t = (f - 1) / FPS
            inp.default_value = s0 * (1 + 0.3 * math.sin(2 * math.pi * 3.3 * t + seed) + 0.15 * math.sin(2 * math.pi * 8.3 * t)); inp.keyframe_insert("default_value", frame=f)
    return dict(objects=objs, lights=lights, blaze=objs[0])


@element("fire", "the lamp for anything that glows and is not from the kit (a lit sign, a lantern, a hot coal): put it "
                 "beside the glowing thing so its light falls on what is near", emits=True)
def glow_light(loc, power=30.0, col=HOT, r=0.2, flickers=False, seed=0.0, name="glow"):
    L_ = point(name + " light", tuple(loc), power, col=col, r=r)
    if flickers: flicker([L_], seed)
    return dict(objects=[], lights=[L_], light=L_)


# ================================================================ LAVA
def lava_mat(name="fx lava", heat=1.0, scale=5.0, glow="#FF4A00", fresh=0.0):
    """lava as it looks: black-grey cracked crust plates (real scanned burnt rock under the break-up), orange light
    running in the seams only where the flow under them still moves, the rest dead black. `fresh` (0..1) is a front
    still moving: wide glowing seams and molten patches between thin plates. The crust drifts by the node 'lava flow'."""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    bs.inputs["Roughness"].default_value = 0.85
    tc = N("ShaderNodeTexCoord"); mp = N("ShaderNodeMapping"); mp.name = "lava flow"; L(tc.outputs["Object"], mp.inputs["Vector"])
    warp = N("ShaderNodeTexNoise"); warp.inputs["Scale"].default_value = scale * 0.6; warp.inputs["Detail"].default_value = 3
    L(mp.outputs["Vector"], warp.inputs["Vector"])
    add = N("ShaderNodeVectorMath"); add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = (0.55, 0.55, 0.55)
    L(warp.outputs["Color"], add.inputs[0]); L(mp.outputs["Vector"], add.inputs[2])
    vo = N("ShaderNodeTexVoronoi"); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs["Scale"].default_value = scale * 0.6
    L(add.outputs["Vector"], vo.inputs["Vector"])
    crack = N("ShaderNodeMapRange"); crack.inputs["To Min"].default_value = 1.0; crack.inputs["To Max"].default_value = 0.0
    L(vo.outputs["Distance"], crack.inputs["Value"])
    wid = N("ShaderNodeTexNoise"); wid.inputs["Scale"].default_value = scale * 0.45; wid.inputs["Detail"].default_value = 2
    L(mp.outputs["Vector"], wid.inputs["Vector"])
    wr = N("ShaderNodeMapRange"); wr.inputs["From Min"].default_value = 0.35; wr.inputs["From Max"].default_value = 0.65
    wr.inputs["To Min"].default_value = 0.004 + 0.03 * fresh; wr.inputs["To Max"].default_value = 0.13 + 0.14 * fresh
    L(wid.outputs["Fac"], wr.inputs["Value"]); L(wr.outputs["Result"], crack.inputs["From Max"])
    vo2 = N("ShaderNodeTexVoronoi"); vo2.feature = 'DISTANCE_TO_EDGE'; vo2.inputs["Scale"].default_value = scale * 2.9
    vo2.inputs["Randomness"].default_value = 1.0; L(add.outputs["Vector"], vo2.inputs["Vector"])
    hair = N("ShaderNodeMapRange"); hair.inputs["From Max"].default_value = 0.025; hair.inputs["To Min"].default_value = 0.22; hair.inputs["To Max"].default_value = 0.0
    L(vo2.outputs["Distance"], hair.inputs["Value"])
    hmask = N("ShaderNodeMath"); hmask.operation = 'MULTIPLY'; L(hair.outputs["Result"], hmask.inputs[0]); L(wid.outputs["Fac"], hmask.inputs[1])
    crk0 = N("ShaderNodeMath"); crk0.operation = 'MAXIMUM'; L(crack.outputs["Result"], crk0.inputs[0]); L(hmask.outputs[0], crk0.inputs[1])
    actn = N("ShaderNodeTexNoise"); actn.inputs["Scale"].default_value = scale * 0.2; actn.inputs["Detail"].default_value = 2
    L(mp.outputs["Vector"], actn.inputs["Vector"])
    act = N("ShaderNodeMapRange"); act.inputs["From Min"].default_value = 0.47 - 0.3 * fresh; act.inputs["From Max"].default_value = 0.6 - 0.3 * fresh
    L(actn.outputs["Fac"], act.inputs["Value"])
    rimn = N("ShaderNodeAttribute"); rimn.attribute_name = "hot"
    act2 = N("ShaderNodeMath"); act2.operation = 'MAXIMUM'; L(act.outputs["Result"], act2.inputs[0]); L(rimn.outputs["Fac"], act2.inputs[1])
    crk = N("ShaderNodeMath"); crk.operation = 'MULTIPLY'; L(crk0.outputs[0], crk.inputs[0]); L(act2.outputs[0], crk.inputs[1])
    big = N("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = scale * 0.35; L(mp.outputs["Vector"], big.inputs["Vector"])
    hot = N("ShaderNodeMapRange"); hot.inputs["From Min"].default_value = 0.5 - 0.15 * fresh; hot.inputs["From Max"].default_value = 0.75 - 0.1 * fresh
    hot.inputs["To Max"].default_value = 0.85 * fresh; L(big.outputs["Fac"], hot.inputs["Value"])
    glowf = N("ShaderNodeMath"); glowf.operation = 'MAXIMUM'; L(crk.outputs[0], glowf.inputs[0]); L(hot.outputs["Result"], glowf.inputs[1])
    crust = N("ShaderNodeTexNoise"); crust.inputs["Scale"].default_value = scale * 6; crust.inputs["Detail"].default_value = 8
    L(add.outputs["Vector"], crust.inputs["Vector"])
    cr = N("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (*K.lin("#0B0A09"), 1); cr.color_ramp.elements[1].color = (*K.lin("#3A3532"), 1)
    L(crust.outputs["Fac"], cr.inputs["Fac"])
    ramp = N("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*K.lin("#B02500"), 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (*K.lin("#FFA020"), 1)
    ramp.color_ramp.elements.new(0.5).color = (*K.lin(glow), 1)
    L(glowf.outputs[0], ramp.inputs["Fac"])
    mix = N("ShaderNodeMixRGB"); L(glowf.outputs[0], mix.inputs["Fac"])
    crust_col = cr.outputs["Color"]; rock_nor = None
    if have("burned_ground_01", "textures"):             # the crust is REAL ROCK, near black, under the procedural break-up
        d_ = ph_path("burned_ground_01", "textures")

        def rimg(kind, data=True):
            f_ = os.path.join(d_, f"burned_ground_01_{kind}_1k.jpg")
            if not os.path.exists(f_): return None
            t_ = N("ShaderNodeTexImage"); t_.image = bpy.data.images.load(f_, check_existing=True); t_.projection = 'BOX'; t_.projection_blend = 0.25
            if data: t_.image.colorspace_settings.name = 'Non-Color'
            rm_ = N("ShaderNodeMapping"); rm_.inputs["Scale"].default_value = (scale * 0.22,) * 3
            L(add.outputs["Vector"], rm_.inputs["Vector"]); L(rm_.outputs["Vector"], t_.inputs["Vector"]); return t_
        rd = rimg("diff", False)
        if rd:
            mxr = N("ShaderNodeMix"); mxr.data_type = 'RGBA'; mxr.blend_type = 'MULTIPLY'; mxr.inputs[0].default_value = 1.0
            L(rd.outputs["Color"], mxr.inputs[6]); L(cr.outputs["Color"], mxr.inputs[7])
            gain = N("ShaderNodeMix"); gain.data_type = 'RGBA'; gain.blend_type = 'ADD'; gain.inputs[0].default_value = 1.0
            L(mxr.outputs[2], gain.inputs[6]); L(mxr.outputs[2], gain.inputs[7]); crust_col = gain.outputs[2]
        rock_nor = rimg("nor_gl")
    L(crust_col, mix.inputs["Color1"]); mix.inputs["Color2"].default_value = (*K.lin("#2A0600"), 1)   # the molten part is LIGHT, not paint
    L(mix.outputs["Color"], bs.inputs["Base Color"]); L(ramp.outputs["Color"], bs.inputs["Emission Color"])
    es = N("ShaderNodeMath"); es.operation = 'MULTIPLY'; es.name = "lava heat"; es.inputs[1].default_value = 1.1 * heat   # brighter than this the view transform bleaches it to salmon
    pw = N("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
    L(glowf.outputs[0], pw.inputs[0]); L(pw.outputs[0], es.inputs[0]); L(es.outputs[0], bs.inputs["Emission Strength"])
    bp = N("ShaderNodeBump"); bp.inputs["Strength"].default_value = 1.0; bp.inputs["Distance"].default_value = 0.05
    inv = N("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L(crack.outputs["Result"], inv.inputs[1])
    hb = N("ShaderNodeMath"); hb.operation = 'MULTIPLY_ADD'; hb.inputs[2].default_value = 0.0
    L(inv.outputs[0], hb.inputs[0]); L(crust.outputs["Fac"], hb.inputs[1]); L(hb.outputs[0], bp.inputs["Height"])
    if rock_nor:
        nmr = N("ShaderNodeNormalMap"); nmr.inputs["Strength"].default_value = 1.4
        L(rock_nor.outputs["Color"], nmr.inputs["Color"]); L(nmr.outputs["Normal"], bp.inputs["Normal"])
    L(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def _lava_mesh(name, outline, z, thick, m, seed, lumpy):
    cx = sum(p[0] for p in outline) / len(outline); cy = sum(p[1] for p in outline) / len(outline)
    bm = bmesh.new(); rings = 6; rows = []; nb = len(outline)
    for k in range(rings + 1):
        s = 1.0 - k / rings
        row = []
        for (x, y) in outline:
            px, py = cx + (x - cx) * s, cy + (y - cy) * s
            hz = thick * (1 - s ** 3) ** 0.5 if k < rings else thick
            hz += lumpy * vn(px * 3.1, py * 3.1, seed) * (1 - s)
            row.append(bm.verts.new((px - cx, py - cy, z + max(0.0, hz))))
        rows.append(row)
    for k in range(rings):
        for i in range(nb):
            j = (i + 1) % nb
            bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
    bm.faces.new(list(reversed(rows[rings])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(m)
    hot = me.attributes.new("hot", 'FLOAT', 'POINT')     # its moving edge is the hot part
    for v in me.vertices:
        ring = min(rings, v.index // nb); hot.data[v.index].value = (1.0 - ring / rings) ** 2.5
    o = _link(bpy.data.objects.new(name, me)); o.location = (cx, cy, 0)
    sd = o.modifiers.new("sub", 'SUBSURF'); sd.levels = 1; sd.render_levels = 3
    tx = bpy.data.textures.get("fx lava crust break") or bpy.data.textures.new("fx lava crust break", 'VORONOI')
    tx.noise_scale = 0.22; tx.distance_metric = 'DISTANCE'
    dm = o.modifiers.new("crust", 'DISPLACE'); dm.texture = tx; dm.texture_coords = 'LOCAL'; dm.strength = 0.5 * max(0.06, lumpy); dm.mid_level = 0.35
    return o


def _rim_lights(name, outline, z, power, every=0.7, cap=14):
    """the glow a lava edge throws on the ground, the rocks and whoever stands by it: lamps just inside its rim"""
    pts = [Vector((p[0], p[1], 0)) for p in outline]; n = len(pts)
    cx = sum(p.x for p in pts) / n; cy = sum(p.y for p in pts) / n
    per = sum((pts[(i + 1) % n] - pts[i]).length for i in range(n))
    k = max(3, min(cap, int(per / every))); out = []; step = per / k; acc = 0.0; want = step / 2
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]; seg = (b - a).length
        while seg > 0 and want <= acc + seg and len(out) < k:
            q = a.lerp(b, (want - acc) / seg); q = q + (Vector((cx, cy, 0)) - q) * 0.08
            out.append(point(f"{name} glow {len(out)}", (q.x, q.y, z + 0.3), power, col=(1.0, 0.42, 0.1), r=0.25)); want += step
        acc += seg
    return out


def _rubble(name, outline, z, m, rnd, per_m=7.0, size=(0.05, 0.16), inset=0.1, pile=2):
    """the broken front of a flow: clinker blocks of its own crust heaped along its rim, glowing in their seams, so the
    edge is rough rock with light in it and never the clean outline of a disc laid on the ground (board: "a decal")"""
    pts = [Vector((p[0], p[1], 0)) for p in outline]; n = len(pts); out = []
    cx = sum(p.x for p in pts) / n; cy = sum(p.y for p in pts) / n; C = Vector((cx, cy, 0))
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for k in range(max(1, int((b - a).length * per_m))):
            q = a.lerp(b, rnd.random()); lay = rnd.randrange(pile)
            q = q + (C - q).normalized() * (inset * lay + rnd.uniform(-0.06, 0.1))
            r = rnd.uniform(*size) * (1.0 if lay == 0 else 0.8)
            out.append(block(name, (q.x, q.y, z + r * 0.3 + lay * size[1] * 0.7), r, m, rnd, squash=0.8))
    return out


@element("lava", "a lava flow: a lumpy slab of black cracked crust (real scanned rock) with orange light in its seams, "
                 "hottest at its moving edge, drifting; lamps along its rim throw its glow on the ground and on Data", emits=True)
def lava_flow(outline, z=0.0, thick=0.34, fresh=0.3, heat=2.2, glow=26.0, drift=(0.05, 0), seed=0, lumpy=0.2, scale=6.0, name="lava flow", front=7.0):
    """outline: [(x, y)] counter-clockwise, the lobe's plan. fresh 0 = a cooled field, 1 = a front still moving.
    glow: watts per rim lamp (26 as lava shot 3; 0 is refused: lava always lights what is near). drift: metres a
    second the crust slides (x, y of the object). Returns dict(lava, mat, rim)."""
    m = lava_mat(f"{name} mat", heat=heat, scale=scale, fresh=fresh)
    o = _lava_mesh(name, list(outline), z, thick, m, seed, lumpy)
    if drift and (drift[0] or drift[1]):
        mp = m.node_tree.nodes["lava flow"]
        for f in (1, _nf() + 1):
            t = (f - 1) / FPS
            mp.inputs["Location"].default_value = (-drift[0] * t, -drift[1] * t, 0); mp.inputs["Location"].keyframe_insert("default_value", frame=f)
        _linear(m.node_tree, "lava flow")
    rub = _rubble(name + " front block", list(outline), z, lava_mat(f"{name} front mat", heat=1.4, scale=1.6, fresh=0.0),
                  random.Random(seed + 17), per_m=front, size=(0.05, 0.17 + 0.2 * thick)) if front else []
    lights = _rim_lights(name, outline, z + thick, max(glow, 4.0))
    return dict(objects=[o] + rub, lights=lights, lava=o, mat=m, rim=lights, front=rub)


@element("lava", "a pool of molten lava: a ragged round of thin crust plates over wide glowing seams, with its glow "
                 "cast up and outward by its own lamps", emits=True)
def lava_pool(centre=(0, 0), r=1.2, z=0.0, seed=0, glow=40.0, name="lava pool", rim=True):
    rnd = random.Random(seed); n = 28
    outline = [(centre[0] + r * (1 + 0.18 * vn(k * 0.9, seed * 1.3, seed)) * math.cos(2 * math.pi * k / n) * rnd.uniform(0.94, 1.06),
                centre[1] + r * (1 + 0.18 * vn(k * 0.9, seed * 1.3 + 9, seed)) * math.sin(2 * math.pi * k / n) * rnd.uniform(0.94, 1.06)) for k in range(n)]
    m = lava_mat(f"{name} mat", heat=1.0, scale=4.0 / max(r, 0.3) * 1.5, fresh=0.8)
    o = _lava_mesh(name, outline, z, 0.07, m, seed, 0.03)
    rub = _rubble(name + " rim block", outline, z, lava_mat(f"{name} rim mat", heat=0.8, scale=1.6, fresh=0.0), rnd, per_m=9.0,
                  size=(0.04 * (1 + r), 0.11 * (1 + r)), pile=2) if rim else []
    lights = _rim_lights(name, outline, z + 0.07, glow, every=0.9, cap=8)
    lights.append(point(f"{name} core glow", (centre[0], centre[1], z + 0.6), glow * 3.0, col=(1.0, 0.45, 0.12), r=0.5 * r))
    flicker(lights[-1:], seed, depth=0.1)
    return dict(objects=[o] + rub, lights=lights, lava=o, mat=m, outline=outline, rim=rub)


def _clot_mat(name, vent, reach):
    """a thrown clot of lava: white-yellow at the vent, orange in flight, cooling to dark red and black crust as it
    gets far from the vent (the colour is read from how far the clot is, so it cools as it flies)"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    oi = N("ShaderNodeObjectInfo")
    dist = N("ShaderNodeVectorMath"); dist.operation = 'DISTANCE'; L(oi.outputs["Location"], dist.inputs[0]); dist.inputs[1].default_value = tuple(vent)
    u = N("ShaderNodeMapRange"); L(dist.outputs["Value"], u.inputs["Value"]); u.inputs["From Min"].default_value = 0.0; u.inputs["From Max"].default_value = reach
    jit = N("ShaderNodeMath"); jit.operation = 'MULTIPLY_ADD'; L(oi.outputs["Random"], jit.inputs[0]); jit.inputs[1].default_value = 0.35; L(u.outputs["Result"], jit.inputs[2])
    rp = N("ShaderNodeValToRGB"); L(jit.outputs[0], rp.inputs["Fac"]); el = rp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (*K.lin("#FF7A08"), 1); el[1].position = 1.15; el[1].color = (*K.lin("#2A0400"), 1)
    el.new(0.4).color = (*K.lin("#F03C00"), 1); el.new(0.8).color = (*K.lin("#A81400"), 1)
    st = N("ShaderNodeMapRange"); L(jit.outputs[0], st.inputs["Value"]); st.inputs["From Min"].default_value = 0.0; st.inputs["From Max"].default_value = 1.2
    st.inputs["To Min"].default_value = 3.2; st.inputs["To Max"].default_value = 0.5      # deep orange, never bright enough to bleach to pink-white (board B18: "popcorn")
    L(rp.outputs["Color"], bs.inputs["Emission Color"]); L(st.outputs["Result"], bs.inputs["Emission Strength"])
    bs.inputs["Base Color"].default_value = (*K.lin("#140A06"), 1); bs.inputs["Roughness"].default_value = 0.9
    return m


def _arcs(name, vent, n, speed, cone, t0, t1, period, size, seed, m, ground_z=None, wind=(0.0, 0.0), stretch=2.2):
    """n clots thrown from `vent` on real ballistic arcs, again and again (each on its own clock), every frame keyed:
    up fast, slowing, over, and down, tumbling, stretched along their flight. A clot below the ground is hidden."""
    rnd = random.Random(seed); V = Vector(vent); gz = V.z if ground_z is None else ground_z
    f0, f1 = max(1, F(t0)), min(_nf(), F(t1)) if t1 is not None else _nf()
    out = []
    for k in range(n):
        o = block(f"{name} {k}", tuple(V), 1.0, m, rnd, squash=1.0)
        r = rnd.uniform(*size) * (2.2 if rnd.random() < 0.08 else 1.0)
        P = period * rnd.uniform(0.7, 1.4); ph = rnd.uniform(0, P)
        az = rnd.uniform(0, 2 * math.pi); tilt = abs(rnd.gauss(0, cone * 0.5)); v0 = speed * rnd.uniform(0.55, 1.0) * (1 - 0.35 * tilt / max(cone, 1e-3) * 0.5)
        vx = v0 * math.sin(tilt) * math.cos(az) + wind[0]; vy = v0 * math.sin(tilt) * math.sin(az) + wind[1]; vz = v0 * math.cos(tilt)
        spin = (rnd.uniform(-6, 6), rnd.uniform(-6, 6), rnd.uniform(-6, 6))
        prev_hidden = None
        for f in range(f0, f1 + 1):
            t = (f - 1) / FPS - t0 + ph; s = t % P
            p = V + Vector((vx * s, vy * s, vz * s - 4.9 * s * s))
            hidden = p.z < gz - 0.02
            if hidden != prev_hidden or f in (f0, f1):
                o.hide_render = hidden; o.keyframe_insert("hide_render", frame=f); prev_hidden = hidden
            if hidden: continue
            vel = Vector((vx, vy, vz - 9.8 * s)); sp = vel.length
            o.location = p; o.keyframe_insert("location", frame=f)
            q = vel.to_track_quat('Z', 'Y').to_euler() if sp > 0.5 else Euler(spin)
            o.rotation_euler = q; o.keyframe_insert("rotation_euler", frame=f)
            k_ = 1 + (stretch - 1) * min(1.0, sp / max(speed, 0.1))                 # molten: pulled long along its flight
            o.scale = (r / k_ ** 0.5, r / k_ ** 0.5, r * k_); o.keyframe_insert("scale", frame=f)
        if o.animation_data and o.animation_data.action:
            for c in _fcurves(o.animation_data.action):
                for kp in c.keyframe_points: kp.interpolation = 'CONSTANT' if "hide" in c.data_path else 'LINEAR'
        out.append(o)
    return out


@element("lava", "glowing embers or lava bombs thrown on real ballistic arcs from a point: stretched, tumbling clots, "
                 "yellow-hot at the source and cooling to dark red as they fly (never pale balls), with the lamp "
                 "that lights the ground where they come from", emits=True)
def embers(origin=(0, 0, 0), n=40, speed=4.0, cone=0.6, size=(0.015, 0.05), t0=0.0, t1=None, period=1.6, seed=0, ground_z=None,
           wind=(0.0, 0.0), power=None, name="embers"):
    """speed: launch speed in m/s (they rise speed^2 / 19.6 metres). cone: how wide they fan (radians from straight up).
    period: seconds between one clot's throws. Returns dict(clots, light)."""
    reach = speed * speed / 19.6 * 1.3 + 0.3
    m = _clot_mat(f"{name} clot", origin, reach)
    clots = _arcs(name + " clot", origin, n, speed, cone, t0, t1, period, size, seed, m, ground_z=ground_z, wind=wind)
    L_ = point(name + " light", (origin[0], origin[1], origin[2] + 0.25 * reach), power if power is not None else 12.0 * n * (sum(size) / 0.065), r=0.3)
    flicker([L_], seed)
    return dict(objects=clots, lights=[L_], clots=clots, light=L_, reach=reach)


@element("lava", "a lava fountain: a ragged incandescent jet (gas) from a glowing vent in a spatter rampart of black "
                 "rock, hundreds of clots thrown on arcs and falling back, a dark gas plume lit from below, and strong "
                 "orange lamps that light the ground, the smoke and the houses around it (an eruption, not a bonfire)", emits=True)
def lava_fountain(base=(0, 0, 0), h=6.0, w=1.4, clots=360, plume=10.0, lean=(-0.3, 0.1), seed=0, power=None, t0=0.0, keys=None, name="fountain"):
    """h: how high the jet stands; w: the vent's width. plume: metres of gas above the jet. power: watts of the main
    lamp (default 900 a metre of height). Returns dict(jet, clots, rampart, pool, light)."""
    B_ = Vector(base); rnd = random.Random(seed + 91); objs = []
    # the jet: white-yellow, narrow and torn, standing on the vent (a fire's ramp starts red; molten rock starts yellow)
    hot = (("#8A1200", 0.0), ("#E03400", 0.2), ("#FF6200", 0.45), ("#FF8E10", 0.75), ("#FFB838", 1.0))
    jet = gas(name + " jet", tuple(B_), w=w, h_fire=h, h_smoke=plume, lean=lean, seed=seed * 2.3 + 0.7, fire=10.0, smoke_d=4.5,
              smoke=(0.075, 0.068, 0.062), rise=4.5, flame_d=14.0, spread=0.2, ramp=hot, lit=1.0, keys=keys, taper=0.4, fall=0.3)
    core = gas(name + " core", tuple(B_ + Vector((0, 0, -0.1))), w=w * 0.5, h_fire=h * 0.62, h_smoke=0.4, seed=seed * 1.3 + 4.2, fire=16.0, smoke_d=0.0,
               rise=6.0, flame_d=18.0, ramp=(("#FF5A00", 0.0), ("#FF9A18", 0.5), ("#FFD060", 1.0)), keys=keys, taper=0.5, fall=0.3)
    objs += [jet, core]
    # the spatter rampart: a low ring of welded black blocks round the vent, glowing in its throat
    rock = ph_mat("burned_ground_01", scale=0.8, tint="#2E2A27", name="fx spatter rock", bump=1.8) if have("burned_ground_01", "textures") else lava_mat("fx spatter rock", heat=0.0)
    ramp_blocks = []
    for k in range(110):
        a = rnd.uniform(0, 2 * math.pi); rr = w * rnd.uniform(0.55, 1.6); s = w * rnd.uniform(0.07, 0.2) * (1.5 - 0.5 * rr / (1.5 * w))
        ramp_blocks.append(block(name + " rampart", (B_.x + rr * math.cos(a), B_.y + rr * math.sin(a) * 0.8, B_.z + s * 0.25 + 0.2 * w * max(0, 1 - abs(rr / w - 0.8))), s, rock, rnd, squash=0.75))
    pool = lava_pool.__wrapped__((B_.x, B_.y), r=w * 0.62, z=B_.z + 0.1 * w, seed=seed, glow=30.0, name=name + " vent")
    objs += ramp_blocks + pool["objects"]
    v0 = math.sqrt(19.6 * h) * 0.9
    m = _clot_mat(f"{name} clot", tuple(B_), h * 1.25)
    cl = _arcs(name + " clot", tuple(B_ + Vector((0, 0, 0.3 * w))), clots, v0, 0.26, t0, None, 2 * v0 / 9.8 * 0.8, (0.014 * w, 0.05 * w), seed, m,
               ground_z=B_.z, wind=(lean[0] * 1.2, lean[1] * 1.2), stretch=2.6)
    objs += cl
    e = power if power is not None else 900.0 * h
    lights = [point(name + " light", (B_.x, B_.y - 0.3 * w, B_.z + 0.45 * h), e, r=0.35 * w + 0.2),
              point(name + " crown light", (B_.x + lean[0] * h * 0.3, B_.y + lean[1] * h * 0.3, B_.z + 0.95 * h), e * 0.5, r=0.5 * w + 0.3),
              point(name + " ground glow", (B_.x, B_.y - 0.9 * w, B_.z + 0.5 * w), e * 0.25, col=(1.0, 0.36, 0.08), r=0.5 * w)]
    if keys:
        for L_ in lights: _keyed_light(L_, keys, L_.data.energy)
    else:
        flicker(lights, seed, depth=0.16)
    lights += pool["lights"]
    return dict(objects=objs, lights=lights, jet=jet, core=core, clots=cl, rampart=ramp_blocks, pool=pool["lava"], light=lights[0], h=h)


# ================================================================ WATER
@element("water", "open water: a dark, glossy surface with two scales of moving waves that mirrors the real sky "
                  "(sea, harbour, lake); never a flat blue plane")
def water(area=(-20, 20, 4, 60), z=0.0, col="#0E2A30", wave=0.5, rough=0.06, drift=(0.15, 0.05), name="water"):
    """a sheet of water over area (x0, x1, y0, y1) at height z. wave: how rough the surface is (0 a pond, 1 a choppy
    sea). It needs a FX.sky to mirror. Returns dict(water, mat)."""
    m = bpy.data.materials.new(name + " mat"); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    N = nt.nodes.new; L = nt.links.new
    bs.inputs["Base Color"].default_value = (*K.lin(col), 1); bs.inputs["Roughness"].default_value = rough
    bs.inputs["IOR"].default_value = 1.33; bs.inputs["Specular IOR Level"].default_value = 0.6
    tc = N("ShaderNodeTexCoord"); mp = N("ShaderNodeMapping"); mp.name = "water drift"; L(tc.outputs["Object"], mp.inputs["Vector"])
    big = N("ShaderNodeTexNoise"); big.noise_dimensions = '4D'; big.inputs["Scale"].default_value = 0.9; big.inputs["Detail"].default_value = 3; big.inputs["Roughness"].default_value = 0.55
    st = N("ShaderNodeMapping"); st.inputs["Scale"].default_value = (1.0, 2.6, 1.0); L(mp.outputs["Vector"], st.inputs["Vector"]); L(st.outputs["Vector"], big.inputs["Vector"])
    fine = N("ShaderNodeTexNoise"); fine.noise_dimensions = '4D'; fine.inputs["Scale"].default_value = 7.0; fine.inputs["Detail"].default_value = 6; fine.inputs["Roughness"].default_value = 0.6
    L(mp.outputs["Vector"], fine.inputs["Vector"])
    hsum = N("ShaderNodeMath"); hsum.operation = 'MULTIPLY_ADD'; L(fine.outputs["Fac"], hsum.inputs[0]); hsum.inputs[1].default_value = 0.22; L(big.outputs["Fac"], hsum.inputs[2])
    bp = N("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.25 + 0.6 * wave; bp.inputs["Distance"].default_value = 0.08 + 0.25 * wave
    L(hsum.outputs[0], bp.inputs["Height"]); L(bp.outputs["Normal"], bs.inputs["Normal"])
    for f in (1, _nf() + 1):
        t = (f - 1) / FPS
        mp.inputs["Location"].default_value = (-drift[0] * t, -drift[1] * t, 0); mp.inputs["Location"].keyframe_insert("default_value", frame=f)
        for nz in (big, fine):
            nz.inputs["W"].default_value = 0.35 * t; nz.inputs["W"].keyframe_insert("default_value", frame=f)
    _linear(nt, "nodes")
    o = grid(name, area[0], area[1], area[2], area[3], lambda x, y: z, m, step=max(0.5, (area[1] - area[0]) / 60))
    return dict(objects=[o], water=o, mat=m)


def markdown():
    """the registry as a page (python fx_kit.py)"""
    out = ["| element | group | glows | what it is |", "|---|---|---|---|"]
    for g in GROUPS:
        out += [f"| `FX.{n}` | {g} | {'yes, with its light' if e['emits'] else ''} | {e['what']} |" for n, e in REGISTRY.items() if e["group"] == g]
    return "\n".join(out)


if __name__ == "__main__":
    print(brief() if "--brief" in sys.argv else markdown())
