#!/usr/bin/env python3
"""Blender hero-shot template for the curiosity channel (headless Cycles).

The one cinematic beat per video (the REVEAL): the story's key values as
glowing monoliths rising from a dark reflective plane, labeled in 3D, with
a slow dolly-and-crane camera move. Fully parameterized — the pipeline
writes a JSON spec and runs:

    blender -b --factory-startup --python data_learning/blender_hero.py \
        -- /path/spec.json /path/outdir

Spec:
    {
      "points": [{"label": "Kola Borehole", "value": 12262,
                  "display": "12,262 m"}, ...],   # 2-5, any order
      "title": "You vs the fastest machines",
      "accent": "#4FD1C5",                        # champion + title color
      "seconds": 8, "fps": 12,                    # ffmpeg interpolates to 30
      "invert": false                             # true = monoliths hang DOWN
                                                  #   (depth stories)
      "log_scale": true                           # for 900 vs 828,000 spreads
    }

Frames land in <outdir>/hero_####.png. Render economics for CI: N seconds
at 12fps, 1080p, 48 samples, no denoiser (Ubuntu build lacks OIDN) — the
pipeline interpolates to 30fps with ffmpeg minterpolate, which halves the
Cycles bill. This module never imports pipeline code (it runs inside
Blender's Python), so it takes everything from the spec.
"""
import json
import math
import sys

import bpy


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _emission(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def _glossy_floor():
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.012, 0.015, 0.03, 1)
    bsdf.inputs["Roughness"].default_value = 0.15
    bsdf.inputs["Metallic"].default_value = 0.6
    return m


def _body(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Metallic"].default_value = 0.2
    # A hint of the same color as emission so bars read on the dark floor.
    if "Emission Color" in bsdf.inputs:            # Blender 4.x
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = 0.6
    return m


def build(spec: dict):
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    accent = _hex(spec.get("accent", "#4FD1C5"))
    cool = _hex("#3b6fb5")
    pts = spec["points"][:5]
    vals = [max(1e-9, float(p["value"])) for p in pts]
    if spec.get("log_scale"):
        hs = [math.log10(v + 1) for v in vals]
    else:
        hs = vals
    hmax = max(hs)
    heights = [0.8 + 3.6 * h / hmax for h in hs]
    vmax = max(vals)
    invert = bool(spec.get("invert"))
    # Portrait (9:16) has a much narrower horizontal view than the original
    # 16:9 tuning, so a wide lineup clips at the edges. Pack the monoliths
    # tighter when the frame is tall so all bars + their numbers stay in shot.
    portrait = int(spec.get("res_y", 1080)) > int(spec.get("res_x", 1920))
    gap = (1.75 if len(pts) >= 4 else 2.0) if portrait else 2.6
    x0 = -gap * (len(pts) - 1) / 2

    # Floor.
    bpy.ops.mesh.primitive_plane_add(size=90, location=(0, 0, 0))
    bpy.context.object.data.materials.append(_glossy_floor())

    grow_bars = []                        # (bar, value_text, h, z, i) for grow anim
    for i, (p, h) in enumerate(zip(pts, heights)):
        star = vals[i] == vmax
        x = x0 + i * gap
        z = (-h / 2) if invert else (h / 2)
        bpy.ops.mesh.primitive_cube_add(location=(x, 0, z))
        bar = bpy.context.object
        bar.scale = (0.55, 0.55, h / 2)
        bar.data.materials.append(
            _body(f"bar{i}", accent if star else cool))
        # Value text floats above (or below, inverted) the monolith tip —
        # staggered heights so neighbouring long numbers can't collide.
        lift = (0.55 + (1.75 if i % 2 else 0.10)) if portrait else (0.55 + (0.62 if i % 2 else 0.0))
        tip = (-h - lift) if invert else (h + lift)
        bpy.ops.object.text_add(location=(x, -0.05, tip))
        t = bpy.context.object
        t.data.body = p.get("display", str(p["value"]))
        t.data.size = 0.35 if portrait else 0.46
        t.data.align_x = "CENTER"
        t.data.extrude = 0.02
        t.rotation_euler = (math.radians(80), 0, 0)
        t.data.materials.append(
            _emission(f"num{i}", accent if star else (0.9, 0.93, 1.0), 3.0))
        # Label at the base.
        base = 0.35 if not invert else 0.35
        bpy.ops.object.text_add(location=(x, -1.25, base))
        lb = bpy.context.object
        lb.data.body = p["label"]
        lb.data.size = 0.22 if portrait else 0.30
        lb.data.align_x = "CENTER"
        lb.data.extrude = 0.01
        lb.rotation_euler = (math.radians(80), 0, 0)
        lb.data.materials.append(_emission(f"lb{i}", (0.75, 0.8, 0.9), 1.6))
        grow_bars.append((bar, t, h, z, i))

    # Key + rim lights.
    bpy.ops.object.light_add(type="AREA", location=(6, -7, 9))
    key = bpy.context.object
    key.data.energy = 2500
    key.data.size = 8
    bpy.ops.object.light_add(type="AREA", location=(-8, 5, 6))
    rim = bpy.context.object
    rim.data.energy = 1200
    rim.data.color = accent
    rim.data.size = 6

    # World: near-black with a whisper of blue.
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = \
        (0.004, 0.006, 0.014, 1)
    sc.world = w

    # Camera: slow dolly-in + crane, aimed at the lineup's heart, framed so
    # the tallest monolith's tip + value text stay in shot.
    aim_z = -2.4 if invert else 2.4
    bpy.ops.object.empty_add(location=(0, 0, aim_z))
    target = bpy.context.object
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    tc = cam.constraints.new(type="TRACK_TO")
    tc.target = target
    fps = int(spec.get("fps", 12))
    secs = float(spec.get("seconds", 8))
    frames = max(2, int(round(fps * secs)))
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    z0, z1 = (6.5, 4.6) if not invert else (8.0, 5.2)
    # Portrait: centre the camera (so the champion on the left isn't cut) and
    # pull it back so the whole narrow lineup + its floating numbers fit.
    cam_x = 0.6 if portrait else 3.2
    y0, y1 = (-25.5, -21.0) if portrait else (-19.0, -14.0)
    for f, (y, z) in ((1, (y0, z0)), (frames, (y1, z1))):
        cam.location = (cam_x, y, z)
        cam.keyframe_insert(data_path="location", frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

    # Optional: the monoliths RISE from the floor one by one (smallest first,
    # champion last), each value popping in as its bar lands — so the hero shot
    # is a reveal, not a static tableau. Guarded by spec["grow"] so ORI's
    # existing look is unchanged unless a caller opts in.
    if spec.get("grow") and grow_bars:
        span = max(3, int(frames * 0.18))                    # rise time per bar
        order_g = sorted(grow_bars, key=lambda gb: gb[2])    # by height, small->big
        step = max(1, int(frames * 0.55 / max(1, len(order_g))))
        for k, (bar, t, h, z, i) in enumerate(order_g):
            f0 = 1 + k * step
            f1 = min(frames, f0 + span)
            flat = 0.0009
            bar.scale.z = flat
            bar.location.z = (-flat) if invert else flat
            t.scale = (0.0, 0.0, 0.0)
            bar.keyframe_insert("scale", index=2, frame=f0)
            bar.keyframe_insert("location", index=2, frame=f0)
            t.keyframe_insert("scale", frame=max(1, f1 - 3))
            bar.scale.z = h / 2
            bar.location.z = z
            t.scale = (1.0, 1.0, 1.0)
            bar.keyframe_insert("scale", index=2, frame=f1)
            bar.keyframe_insert("location", index=2, frame=f1)
            t.keyframe_insert("scale", frame=f1)
        for bar, t, *_ in grow_bars:
            for ob in (bar, t):
                if ob.animation_data and ob.animation_data.action:
                    for fc in ob.animation_data.action.fcurves:
                        for kp in fc.keyframe_points:
                            kp.interpolation = "BEZIER"

    # Render engine. EEVEE (real-time rasteriser) is ~10-50x faster than CPU
    # Cycles and still nails this emission-lit, glossy-floor look via screen-
    # space reflections + bloom — so the daily pipeline can afford a 3D beat per
    # video. spec {"engine":"eevee"} opts in; Cycles stays the default for the
    # slower, physically-accurate hero.
    engine = str(spec.get("engine", "cycles")).lower()
    if engine == "eevee":
        # Blender 4.0 = BLENDER_EEVEE; 4.2+ renamed it to BLENDER_EEVEE_NEXT.
        try:
            sc.render.engine = "BLENDER_EEVEE"
        except Exception:  # noqa: BLE001
            sc.render.engine = "BLENDER_EEVEE_NEXT"
        ee = sc.eevee
        for attr, val in (("use_ssr", True), ("use_ssr_refraction", True),
                          ("use_bloom", True), ("bloom_intensity", 0.04),
                          ("use_gtao", True),
                          ("taa_render_samples", int(spec.get("samples", 32)))):
            try:
                setattr(ee, attr, val)               # attrs vary across versions
            except Exception:  # noqa: BLE001
                pass
    else:
        sc.render.engine = "CYCLES"
        sc.cycles.samples = int(spec.get("samples", 32))
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.adaptive_threshold = 0.05
        sc.cycles.max_bounces = 3
        sc.cycles.use_denoising = False    # Ubuntu build ships without OIDN
    sc.render.use_persistent_data = True
    sc.render.resolution_x = int(spec.get("res_x", 1920))
    sc.render.resolution_y = int(spec.get("res_y", 1080))
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Filmic"
    sc.view_settings.look = "Medium High Contrast"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    spec = json.loads(open(argv[0]).read())
    outdir = argv[1]
    build(spec)
    sc = bpy.context.scene
    sc.render.filepath = outdir.rstrip("/") + "/hero_"
    bpy.ops.render.render(animation=True)
    print("HERO_DONE", sc.frame_end)


if __name__ == "__main__":
    main()
