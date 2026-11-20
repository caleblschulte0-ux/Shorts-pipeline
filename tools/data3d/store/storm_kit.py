"""THE STORM KIT (the lightning short, 2026-11-19): a storm sky that can FLASH, a cloud deck, and a lightning BOLT that
is a new jagged shape every time it is called (a seed), with branches, a hot white core inside a blue glow, a light that
throws the whole set into white for the strike, and the flicker of a real return stroke (on, a gap, on again, gone).

The bolt is the story's subject, so it is the short's one callback (script.json callbacks: "bolt"); every call is a new
shape in a new place. Units are the store's: metres at Data's scale (he is 0.96 tall)."""
import math, random
import bpy
from mathutils import Vector
import scene_kit as K
from clock import FPS

F = lambda t: max(1, int(round(t * FPS)) + 1)


def _emit_mat(name, col, strength, alpha=1.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*col, 1); em.inputs["Strength"].default_value = strength
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs["Surface"])
        try: m.blend_method = 'BLEND'
        except AttributeError: pass
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    try: m.shadow_method = 'NONE'
    except AttributeError: pass
    return m


def _jag(a, b, rnd, depth=6, rough=0.22):
    """midpoint displacement: a path from a to b that zigzags like a channel of air breaking down"""
    pts = [Vector(a), Vector(b)]
    for d in range(depth):
        out = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            L = (q - p).length; m = (p + q) / 2
            side = (q - p).cross(Vector((0, 0, 1)) if abs((q - p).normalized().z) < 0.95 else Vector((1, 0, 0))).normalized()
            up = side.cross((q - p).normalized())
            m += side * rnd.uniform(-1, 1) * L * rough + up * rnd.uniform(-1, 1) * L * rough * 0.5
            out += [m, q]
        pts = out; rough *= 0.92
    return pts


def _tube(name, pts, r, m, parent=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        taper = 1.0 - 0.55 * i / max(1, len(pts) - 1)
        sp.points[i].co = (*p, 1); sp.points[i].radius = taper
    o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o); cu.materials.append(m)
    if parent: o.parent = parent
    o.visible_shadow = False
    return o


def bolt(name, top, bottom, seed=0, branches=4, width=0.012, glow=4.0, rough=0.22):
    """a lightning bolt from `top` (up in the cloud) to `bottom` (what it hits): a white-hot core, a wide soft blue
    glow round it, and `branches` forks that die out partway. Returns the root empty; strike() makes it flash."""
    rnd = random.Random(seed)
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root)
    core = _emit_mat("bolt core", (1.0, 0.98, 1.0), 60.0)
    halo = glow_mat()
    main = _jag(top, bottom, rnd, rough=rough)
    parts = [_tube(name + " core", main, width, core, root), _tube(name + " glow", main, width * glow, halo, root)]
    for k in range(branches):
        i = rnd.randrange(len(main) // 6, int(len(main) * 0.7))
        a = main[i]; L = (Vector(bottom) - Vector(top)).length
        d = (Vector(bottom) - a).normalized()
        sideways = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.4, 0.4), 0)).normalized()
        b = a + (d * 0.6 + sideways * 0.8).normalized() * L * rnd.uniform(0.12, 0.3)
        br = _jag(a, b, rnd, depth=4, rough=0.25)
        parts.append(_tube(name + f" branch{k}", br, width * 0.5, core, root))
        parts.append(_tube(name + f" branch{k} glow", br, width * 0.5 * glow, halo, root))
    root["parts"] = [p.name for p in parts]
    root["hit"] = tuple(bottom)    # where it strikes (in the root's space): staging.far measures every frame the bolt is
                                   # visible against Data on screen, however a shot flashes it (strike() or its own keys)
    return root


STROKE = [(0.0, 1.0), (0.05, 0.0), (0.09, 1.0), (0.2, 0.55), (0.26, 0.0)]   # (s after the strike, brightness)


def flash_level(t, strikes):
    """the strike brightness at time t (0..1) over a list of strike times"""
    v = 0.0
    for s in strikes:
        dt = t - s
        if dt < 0 or dt > STROKE[-1][0]: continue
        for (ta, a), (tb, b) in zip(STROKE, STROKE[1:]):
            if ta <= dt <= tb:
                v = max(v, a + (b - a) * (dt - ta) / (tb - ta)); break
    return v


def strike(bolt_root, times, nf, light_at=None, energy=4000.0, world=None):
    """key the bolt visible only while it strikes (a return stroke flickers: on, a gap, on again, fading), a flash
    light at `light_at` (default: the bolt's foot) and, if given, the world's brightness (world=(base, peak))"""
    parts = [bpy.data.objects[n] for n in bolt_root["parts"]]
    ld = bpy.data.lights.new(bolt_root.name + " flash", 'POINT'); ld.shadow_soft_size = 0.4; ld.color = (0.85, 0.9, 1.0)
    lo = bpy.data.objects.new(bolt_root.name + " flash", ld); bpy.context.collection.objects.link(lo)
    lo.location = light_at if light_at is not None else bpy.data.objects[bolt_root["parts"][0]].data.splines[0].points[-1].co.xyz + Vector((0, -0.3, 0.6))
    bg = None
    if world is not None:
        nt = bpy.context.scene.world.node_tree; bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    for f in range(1, nf + 1):
        v = flash_level((f - 1) / FPS, times)
        for p in parts:
            p.hide_render = v < 0.05; p.keyframe_insert("hide_render", frame=f)
            p.hide_viewport = v < 0.05
        ld.energy = energy * v; ld.keyframe_insert("energy", frame=f)
        if bg is not None:
            bg.inputs["Strength"].default_value = world[0] + (world[1] - world[0]) * v
            bg.inputs["Strength"].keyframe_insert("default_value", frame=f)
    return lo


def storm_sky(strength=0.06, tint=(0.42, 0.48, 0.6), horizon=(0.75, 0.62, 0.55)):
    """a storm sky: a dark slate dome with a dull band of light at the horizon. Returns the background node, whose
    strength strike() flashes."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes):
        if n.type not in ('OUTPUT_WORLD',): nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].position = 0.48; rp.color_ramp.elements[0].color = (*horizon, 1)
    rp.color_ramp.elements[1].position = 0.62; rp.color_ramp.elements[1].color = (*tint, 1)
    nt.links.new(sep.outputs["Z"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], bg.inputs["Color"]); nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return bg


def cloud_mat(name="storm cloud", a="#3A4150", b="#59606E"):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 1.0
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.5
    nz.inputs["Detail"].default_value = 8.0; nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = (*K.lin(a), 1); rp.color_ramp.elements[1].color = (*K.lin(b), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], bs.inputs["Base Color"])
    dp = nt.nodes.new("ShaderNodeDisplacement"); dp.inputs["Scale"].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], dp.inputs["Height"])
    nt.links.new(dp.outputs[0], nt.nodes["Material Output"].inputs["Displacement"])
    return m


def cloud_deck(z, y0=2.0, y1=30.0, x=(-14, 14), n=26, seed=3, roll=None):
    """a low ceiling of lumpy storm cloud: overlapping flattened lumps. roll=(t0, t1, dx): the whole deck rolls in
    over the scene by dx between t0 and t1 (the storm arriving)"""
    rnd = random.Random(seed); m = cloud_mat()
    root = bpy.data.objects.new("cloud deck", None); bpy.context.collection.objects.link(root)
    for i in range(n):
        y = rnd.uniform(y0, y1); r = rnd.uniform(1.6, 3.4) * (1 + y / 20)
        K.sph("cloud", (rnd.uniform(*x), y, z + rnd.uniform(-0.3, 0.6) + y * 0.05), 1.0, m,
              scale=(r * 1.4, r, r * 0.45), parent=root)
    if roll:
        t0, t1, dx = roll
        root.location.x = dx; root.keyframe_insert("location", frame=F(t0))
        root.location.x = 0; root.keyframe_insert("location", frame=F(t1))
    return root


def glow_mat():
    """the bolt's glow: brightest where the tube faces the lens, fading to nothing at its edges, so it reads as light
    round the core and not as a blue outline (the trail beat's look, 2026-11-19)"""
    m = bpy.data.materials.get("bolt glow soft")
    if m: return m
    m = bpy.data.materials.new("bolt glow soft"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em.inputs["Color"].default_value = (0.55, 0.68, 1.0, 1); em.inputs["Strength"].default_value = 14.0
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.5
    nt.links.new(lw.outputs["Facing"], inv.inputs[1]); nt.links.new(inv.outputs[0], pw.inputs[0])
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(pw.outputs[0], mx.inputs["Fac"]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    try: m.blend_method = 'BLEND'
    except AttributeError: pass
    return m


def bloom(threshold=1.2, strength=0.55, size=0.7):
    """a soft lens bloom over the frame (the compositor), so a bolt, a flash or a fire glows as light does in a lens.
    Every storm beat calls it, so the short has one look"""
    sc = bpy.context.scene
    if getattr(sc, "compositing_node_group", None) and sc.compositing_node_group.name == "storm bloom": return
    ng = bpy.data.node_groups.new("storm bloom", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new("CompositorNodeRLayers"); gl = ng.nodes.new("CompositorNodeGlare"); go = ng.nodes.new("NodeGroupOutput")
    gl.inputs["Type"].default_value = 'Bloom'; gl.inputs["Threshold"].default_value = threshold
    gl.inputs["Strength"].default_value = strength; gl.inputs["Size"].default_value = size
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"]); ng.links.new(gl.outputs["Image"], go.inputs[0])
    sc.compositing_node_group = ng
