"""The LOOK: 'kinda real, clean, professional' - not clay, not toon, not chrome. One place for materials, lights and
render settings. Materials are looked up by NAME from scene_kit's cache and restyled here."""
import bpy, math, os
from mathutils import Vector
import scene_kit as K

def _nodes(m):
    m.use_nodes = True; nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None); return nt, bsdf

def _tex_noise(nt, scale=40.0, detail=4.0, rough=0.6):
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail; n.inputs["Roughness"].default_value = rough
    return n

def _bump(nt, bsdf, src, strength=0.08, distance=0.002):
    b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = distance
    nt.links.new(src, b.inputs["Height"]); nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"]); return b

def _ramp(nt, src, a, b):
    r = nt.nodes.new("ShaderNodeMapRange"); r.inputs["To Min"].default_value = a; r.inputs["To Max"].default_value = b
    nt.links.new(src, r.inputs["Value"]); return r.outputs["Result"]

def _mix_col(nt, bsdf, fac, col2, amount=0.3):
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MIX'
    base = bsdf.inputs["Base Color"].default_value[:]
    mx.inputs["A"].default_value = base; mx.inputs["B"].default_value = col2
    src = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
    if src is not None: nt.links.new(src, mx.inputs["A"])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = amount
    nt.links.new(fac, mul.inputs[0]); nt.links.new(mul.outputs[0], mx.inputs["Factor"])
    nt.links.new(mx.outputs["Result"], bsdf.inputs["Base Color"]); return mx

def _get(name):
    return bpy.data.materials.get(name)

def restyle():
    # floor: speckled lino, satin, low-frequency scuff patches
    m = _get("floor")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.24; b.inputs["Specular IOR Level"].default_value = 0.5
            spk = _tex_noise(nt, 90, 3, 0.6); tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["Object"], spk.inputs["Vector"])
            sharp = _ramp(nt, spk.outputs["Fac"], -1.2, 2.2)      # noise Fac sits near 0.5: stretch it so the speckle shows
            cl = nt.nodes.new("ShaderNodeClamp"); nt.links.new(sharp, cl.inputs["Value"])
            _mix_col(nt, b, cl.outputs["Result"], (0.42, 0.41, 0.4, 1), 0.45)
            scuff = _tex_noise(nt, 0.6, 3, 0.7); nt.links.new(tc.outputs["Object"], scuff.inputs["Vector"])
            rr = nt.nodes.new("ShaderNodeMath"); rr.operation = 'MULTIPLY_ADD'; rr.inputs[1].default_value = 0.22; rr.inputs[2].default_value = 0.16
            nt.links.new(scuff.outputs["Fac"], rr.inputs[0]); nt.links.new(rr.outputs[0], b.inputs["Roughness"])
            _bump(nt, b, spk.outputs["Fac"], 0.04, 0.0005)
    for name in ("counter", "laminate", "counter edge"):
        m = _get(name)
        if m:
            nt, b = _nodes(m)
            if b:
                b.inputs["Roughness"].default_value = 0.38
                g = _tex_noise(nt, 18, 6, 0.8); g2 = nt.nodes.new("ShaderNodeMapping"); 
                _mix_col(nt, b, g.outputs["Fac"], (0.6, 0.55, 0.48, 1), 0.12); _bump(nt, b, g.outputs["Fac"], 0.03, 0.0004)
    for name in ("cart metal", "belt rail", "rail", "pole", "basket metal"):
        m = _get(name)
        if m:
            nt, b = _nodes(m)
            if b:
                b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.34
                b.inputs["Base Color"].default_value = (0.72, 0.73, 0.75, 1)
                n = _tex_noise(nt, 400, 2, 0.5); 
                rr = nt.nodes.new("ShaderNodeMath"); rr.operation = 'MULTIPLY_ADD'; rr.inputs[1].default_value = 0.12; rr.inputs[2].default_value = 0.28
                nt.links.new(n.outputs["Fac"], rr.inputs[0]); nt.links.new(rr.outputs[0], b.inputs["Roughness"])
    m = _get("belt")
    if m:
        nt, b = _nodes(m)
        if b: b.inputs["Roughness"].default_value = 0.72; b.inputs["Base Color"].default_value = (0.05, 0.05, 0.055, 1)
    for m in bpy.data.materials:
        if m.name == "reg screen" or m.name.startswith("kiosk screen"):
            nt, b = _nodes(m)
            if b:
                b.inputs["Roughness"].default_value = 0.06; b.inputs["Coat Weight"].default_value = 1.0; b.inputs["Coat Roughness"].default_value = 0.03
                b.inputs["Emission Color"].default_value = (0.55, 0.78, 1.0, 1)
                if m.name == "reg screen": b.inputs["Emission Strength"].default_value = 1.0   # kiosk screens are KEYED by the stager
    for name in ("paper bag", "bag"):
        m = _get(name)
        if m:
            nt, b = _nodes(m)
            if b:
                b.inputs["Roughness"].default_value = 0.85; n = _tex_noise(nt, 120, 3, 0.6); _bump(nt, b, n.outputs["Fac"], 0.1, 0.001)
    m = _get("wall")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.9; n = _tex_noise(nt, 160, 3, 0.6); _bump(nt, b, n.outputs["Fac"], 0.06, 0.0008)
    m = _get("Data / teal")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.34; b.inputs["Specular IOR Level"].default_value = 0.5
            b.inputs["Subsurface Weight"].default_value = 0.08; b.inputs["Subsurface Radius"].default_value = (0.02, 0.01, 0.008)
            b.inputs["Coat Weight"].default_value = 0.3; b.inputs["Coat Roughness"].default_value = 0.14
    m = _get("Coat / warm ivory")
    if m:
        nt, b = _nodes(m)
        if b:
            b.inputs["Roughness"].default_value = 0.82; b.inputs["Sheen Weight"].default_value = 0.9; b.inputs["Sheen Roughness"].default_value = 0.5
            n = _tex_noise(nt, 300, 2, 0.5); _bump(nt, b, n.outputs["Fac"], 0.05, 0.0004)
    m = _get("Frames / charcoal")
    if m:
        nt, b = _nodes(m)
        if b: b.inputs["Roughness"].default_value = 0.3; b.inputs["Coat Weight"].default_value = 0.5
    # product materials: desaturate a touch so the gondola reads as a store not a toy shop
    for m in bpy.data.materials:
        if m.name.startswith(("prod", "candy", "label")) and m.use_nodes:
            nt, b = _nodes(m)
            if b and not any(n.type == 'HUE_SAT' for n in nt.nodes):
                hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.72
                hs.inputs["Color"].default_value = b.inputs["Base Color"].default_value[:]
                nt.links.new(hs.outputs["Color"], b.inputs["Base Color"])


def lights(sc, data_follow=None):
    def area(name, loc, size, energy, col=(1, 1, 1), shape='SQUARE', size_y=None, aim=None):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = col; ld.shape = shape; ld.size = size
        if size_y: ld.size_y = size_y
        o = bpy.data.objects.new(name, ld); o.location = loc; bpy.context.collection.objects.link(o)
        if aim is not None: o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        return o
    # ceiling panels: a row over the lanes, a row behind
    for x in (-1.6, -0.4, 0.8, 2.0, 3.2):
        for y in (-0.9, 0.6):
            area(f"panel {x}_{y}", (x, y, 2.45), 1.1, 15, (1.0, 0.97, 0.92), shape='RECTANGLE', size_y=0.3, aim=(x, y, 0))
    # shopfront daylight
    sd = bpy.data.lights.new("daylight", 'SUN'); sd.energy = 10.0; sd.angle = math.radians(3); sd.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("daylight", sd); bpy.context.collection.objects.link(so)
    so.rotation_euler = Vector((0.75, 0.25, -0.6)).to_track_quat('-Z', 'Y').to_euler()   # from camera-left-front and above: his shadow falls to camera-right where it is SEEN
    # window: big soft area from camera-left-front, half strength
    area("window", (-2.4, -3.2, 1.6), 2.2, 60, (0.92, 0.95, 1.0), shape='RECTANGLE', size_y=1.6, aim=(0.5, 0.3, 0.6))
    # cool fill from the right
    area("fill", (3.0, -2.6, 1.4), 1.6, 9, (0.85, 0.9, 1.0), aim=(0.8, 0.3, 0.5))
    # warm hero key following Data
    key = area("hero key", (0, -1, 1), 0.42, 52, (1.0, 0.93, 0.85), aim=(0, 0, 0.6))
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg: bg.inputs["Color"].default_value = (0.6, 0.65, 0.75, 1); bg.inputs["Strength"].default_value = 0.05
    return key


def follow_key(key, data, f0, f1):
    sc = data.sc
    for f in range(f0, f1 + 1):
        sc.frame_set(f); p = Vector(data.arm.location); fw = data.forward()
        side = Vector((fw.y, -fw.x, 0))  # camera side is -y always; key sits camera-left-front of him
        loc = p + Vector((-0.45, -0.95, 0.95)); key.location = loc; key.keyframe_insert("location", frame=f)
        aim = p + Vector((0, 0, 0.7)); key.rotation_euler = (aim - loc).to_track_quat('-Z', 'Y').to_euler(); key.keyframe_insert("rotation_euler", frame=f)


def render_settings(sc, spp=24, pct=60, out=None):
    sc.render.engine = 'CYCLES'; cy = sc.cycles
    cy.device = 'CPU'; cy.samples = spp; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.05
    cy.use_denoising = True; cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'; cy.seed = 7; cy.use_animated_seed = False
    cy.max_bounces = 6; cy.diffuse_bounces = 3; cy.glossy_bounces = 3; cy.transparent_max_bounces = 6; cy.caustics_reflective = False; cy.caustics_refractive = False
    cy.filter_width = 1.05
    sc.render.resolution_x = 1080; sc.render.resolution_y = 1920; sc.render.resolution_percentage = pct; sc.render.fps = 24
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = -1.3
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    if out: sc.render.filepath = out
