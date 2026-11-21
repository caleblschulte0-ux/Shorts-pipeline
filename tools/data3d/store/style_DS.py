"""The DS LOOK: 'design-studio 3D' (Apple keynote / Headspace explainer). Same shot, staging and animation as style.py;
the set is warm neutrals, Data the only accent, every material soft matte with a faint sheen, no sun, no hard shadow,
one big soft studio key, bright and airy. Selected with LOOK=DS (scene_kit.DS switches the dressing to match).
Same interface as style.py: restyle(), lights(sc) -> hero key, follow_key(), render_settings()."""
import bpy, math
from mathutils import Vector
import scene_kit as K
from style import _nodes, _tex_noise, _bump, follow_key as _follow_key   # the hero key follows Data the same way

FSTOP = 4.0


def _get(name):
    return bpy.data.materials.get(name)


def _soft(b, rough=0.55, spec=0.3, sheen=0.0):
    b.inputs["Roughness"].default_value = rough; b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Metallic"].default_value = 0.0; b.inputs["Coat Weight"].default_value = 0.0
    if sheen: b.inputs["Sheen Weight"].default_value = sheen; b.inputs["Sheen Roughness"].default_value = 0.5


def restyle():
    keep = {"Data / teal", "Coat / warm ivory", "Frames / charcoal", "contact shadow", "Mouth / lip"}
    for m in bpy.data.materials:
        if m.name in keep or not m.use_nodes: continue
        nt, b = _nodes(m)
        if b is None: continue
        if m.name == "reg screen" or m.name.startswith("kiosk screen"):
            b.inputs["Roughness"].default_value = 0.12; b.inputs["Coat Weight"].default_value = 0.6; b.inputs["Coat Roughness"].default_value = 0.08
            if m.name.startswith("kiosk screen"): b.inputs["Emission Color"].default_value = (0.85, 0.95, 1.35, 1)   # the keyed strength stays the stager's; the airy grade needs a brighter blue-white
            if m.name == "reg screen": b.inputs["Emission Color"].default_value = (0.8, 0.88, 1.0, 1); b.inputs["Emission Strength"].default_value = 0.6
            continue
        if m.name in ("lane sign", "light diffuser", "kiosk ui"):
            b.inputs["Emission Strength"].default_value = 0.35 if m.name == "lane sign" else b.inputs["Emission Strength"].default_value; _soft(b, 0.5, 0.3); continue
        if m.name == "cart metal":
            b.inputs["Metallic"].default_value = 0.6; b.inputs["Roughness"].default_value = 0.5; b.inputs["Specular IOR Level"].default_value = 0.4; continue   # keeps the darker grey the kit gave it
        if m.name in ("rail", "belt rail", "pole", "sign pole", "can lid"):
            b.inputs["Metallic"].default_value = 0.6; b.inputs["Roughness"].default_value = 0.5; b.inputs["Specular IOR Level"].default_value = 0.4   # brushed satin, never chrome
            b.inputs["Base Color"].default_value = (*K.lin("#C9C6C1"), 1); continue
        if m.name == "floor":
            _soft(b, 0.6, 0.35); continue                                  # the seamless ground: matte, faint sheen
        if m.name in ("wall", "ceiling"):
            _soft(b, 0.85, 0.15); continue
        if m.name.startswith(("skin", "hair")):
            _soft(b, 0.5, 0.3); b.inputs["Subsurface Weight"].default_value = 0.08 if m.name.startswith("skin") else 0.0; continue
        if m.name in ("uniform", "apron", "pants", "Coat"):
            _soft(b, 0.8, 0.2, sheen=0.25); continue
        _soft(b, 0.55, 0.3)
    m = _get("Data / teal")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.45; b.inputs["Specular IOR Level"].default_value = 0.3
            b.inputs["Subsurface Weight"].default_value = 0.12; b.inputs["Subsurface Radius"].default_value = (0.02, 0.012, 0.01); b.inputs["Coat Weight"].default_value = 0.0
    m = _get("Coat / warm ivory")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.8; b.inputs["Sheen Weight"].default_value = 0.3; b.inputs["Sheen Roughness"].default_value = 0.6; b.inputs["Specular IOR Level"].default_value = 0.2
            n = _tex_noise(nt, 300, 2, 0.5); _bump(nt, b, n.outputs["Fac"], 0.05, 0.0004)
    m = _get("Frames / charcoal")
    if m:
        nt, b = _nodes(m)
        if b: b.inputs["Roughness"].default_value = 0.35; b.inputs["Coat Weight"].default_value = 0.4


def lights(sc, data_follow=None):
    def area(name, loc, size, energy, col=(1, 1, 1), shape='SQUARE', size_y=None, aim=None, spread=180):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = col; ld.shape = shape; ld.size = size; ld.spread = math.radians(spread)
        if size_y: ld.size_y = size_y
        o = bpy.data.objects.new(name, ld); o.location = loc; bpy.context.collection.objects.link(o)
        if aim is not None: o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        return o
    # the studio: one big soft key from camera-left-front, a soft fill from the right, a wide soft top light, a gentle rim from behind
    area("studio key", (-2.6, -3.2, 2.4), 4.0, 520, (1.0, 0.97, 0.93), shape='RECTANGLE', size_y=3.0, aim=(0.8, 0.3, 0.6))
    area("studio fill", (3.6, -3.0, 1.6), 3.0, 110, (0.94, 0.96, 1.0), shape='RECTANGLE', size_y=2.4, aim=(0.8, 0.3, 0.6))
    area("top soft", (1.0, 1.0, K.WALL_H - 0.05), 9.0, 260, (1.0, 0.98, 0.96), shape='RECTANGLE', size_y=7.0, aim=(1.0, 1.0, 0))
    area("rim", (1.5, 2.6, 2.3), 2.0, 140, (1.0, 0.98, 0.95), shape='RECTANGLE', size_y=0.8, aim=(0.8, 0.0, 0.7))
    key = area("hero key", (0, -1, 1), 1.4, 16, (1.0, 0.95, 0.9), aim=(0, 0, 0.6))
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg: bg.inputs["Color"].default_value = (0.9, 0.89, 0.87, 1); bg.inputs["Strength"].default_value = 0.35   # airy ambient
    return key


def follow_key(key, data, f0, f1):
    _follow_key(key, data, f0, f1)


def render_settings(sc, spp=24, pct=60, out=None):
    import style
    style.render_settings(sc, spp, pct, out)
    sc.view_settings.look = 'AgX - Base Contrast'; sc.view_settings.exposure = -0.55   # bright and airy; AgX keeps the highlights
    if sc.camera is not None: sc.camera.data.dof.aperture_fstop = FSTOP
