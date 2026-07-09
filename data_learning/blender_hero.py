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
    gap = 2.6
    x0 = -gap * (len(pts) - 1) / 2

    # Floor.
    bpy.ops.mesh.primitive_plane_add(size=90, location=(0, 0, 0))
    bpy.context.object.data.materials.append(_glossy_floor())

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
        lift = 0.55 + (0.62 if i % 2 else 0.0)
        tip = (-h - lift) if invert else (h + lift)
        bpy.ops.object.text_add(location=(x, -0.05, tip))
        t = bpy.context.object
        t.data.body = p.get("display", str(p["value"]))
        t.data.size = 0.46
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
        lb.data.size = 0.30
        lb.data.align_x = "CENTER"
        lb.data.extrude = 0.01
        lb.rotation_euler = (math.radians(80), 0, 0)
        lb.data.materials.append(_emission(f"lb{i}", (0.75, 0.8, 0.9), 1.6))

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
    for f, (y, z) in ((1, (-19.0, z0)), (frames, (-14.0, z1))):
        cam.location = (3.2, y, z)
        cam.keyframe_insert(data_path="location", frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

    # Render settings — CPU Cycles tuned for a CI budget: adaptive sampling,
    # short bounce depth (emission-lit scene needs few), persistent data so
    # the scene isn't rebuilt per frame.
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(spec.get("samples", 32))
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.cycles.max_bounces = 3
    sc.render.use_persistent_data = True
    sc.cycles.use_denoising = False        # Ubuntu build ships without OIDN
    sc.render.resolution_x = int(spec.get("res_x", 1920))
    sc.render.resolution_y = int(spec.get("res_y", 1080))
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Filmic"
    sc.view_settings.look = "Medium High Contrast"


def build_earth_dive(spec: dict):
    """The 'Earth opens' hero: phase 1 — the camera dives from space
    toward THE Earth; phase 2 (hard cut inside the shot, masked by the
    assembler's luminance dip) — the camera rides down the glowing
    borehole past depth markers to a pulsing dot at the bottom.

    Spec: markers=[{label, display, frac}] (frac = depth/max_depth),
    accent, seconds, fps, samples, res_x/res_y."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    accent = _hex(spec.get("accent", "#4FD1C5"))
    markers = spec.get("markers", [])[:5]
    fps = int(spec.get("fps", 12))
    secs = float(spec.get("seconds", 8))
    frames = max(4, int(round(fps * secs)))
    half = frames // 2

    # --- phase 1 world: THE Earth in space ---
    bpy.ops.mesh.primitive_uv_sphere_add(radius=5, location=(0, 0, 0),
                                         segments=48, ring_count=24)
    earth = bpy.context.object
    bpy.ops.object.shade_smooth()
    earth.data.materials.append(_body("earth_sea", (0.05, 0.18, 0.42)))
    for i, (dx, dy, dz, r) in enumerate([(2.2, -3.4, 2.6, 1.5),
                                         (-3.0, -3.2, 0.6, 1.2),
                                         (0.8, -4.4, -2.0, 1.7),
                                         (-1.8, -3.8, 2.8, 1.0)]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r,
                                             location=(dx, dy, dz),
                                             segments=24, ring_count=12)
        blob = bpy.context.object
        bpy.ops.object.shade_smooth()
        blob.scale = (1.0, 0.35, 1.0)          # squashed = continent shell
        blob.data.materials.append(_body(f"land{i}", (0.10, 0.34, 0.18)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=5.25, location=(0, 0, 0),
                                         segments=32, ring_count=16)
    atmo = bpy.context.object
    m = bpy.data.materials.new("atmo")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.3, 0.55, 1.0, 1)
    bsdf.inputs["Alpha"].default_value = 0.08
    m.blend_method = "BLEND"
    atmo.data.materials.append(m)
    bpy.ops.object.light_add(type="SUN", location=(20, -18, 14))
    bpy.context.object.data.energy = 4.0

    # --- phase 2 world: the underground descent, far away at x=200 ---
    ox = 200.0
    depth = 15.0                     # tight ride: something near every frame
    bpy.ops.mesh.primitive_plane_add(size=1, location=(ox, 8, -depth / 2))
    wall = bpy.context.object
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall.scale = (60, depth * 1.4, 1)
    wall.data.materials.append(_body("rock", (0.045, 0.055, 0.09)))
    # strata seams — dense enough that the ride always passes something
    for i in range(1, 10):
        z = -depth * i / 10
        bpy.ops.mesh.primitive_cube_add(location=(ox, 7.8, z))
        seam = bpy.context.object
        seam.scale = (30, 0.05, 0.05)
        seam.data.materials.append(
            _emission(f"seam{i}", (0.13, 0.17, 0.30), 2.0))
    # the glowing borehole
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=depth,
                                        location=(ox, 6.5, -depth / 2))
    bore = bpy.context.object
    bore.data.materials.append(_emission("bore", accent, 6.0))
    # depth markers
    for mk in markers:
        z = -depth * max(0.02, min(1.0, float(mk.get("frac", 0.5))))
        bpy.ops.object.text_add(location=(ox + 1.0, 6.4, z + 0.2))
        t = bpy.context.object
        t.data.body = f"{mk.get('label', '')} · {mk.get('display', '')}"
        t.data.size = 0.55
        t.data.extrude = 0.02
        t.rotation_euler = (math.radians(90), 0, 0)
        t.data.materials.append(_emission(
            f"mk{z}", accent if mk is markers[-1] else (0.8, 0.85, 0.95),
            2.6))
        bpy.ops.mesh.primitive_cube_add(location=(ox, 6.5, z))
        tick = bpy.context.object
        tick.scale = (0.55, 0.06, 0.02)
        tick.data.materials.append(_emission(
            f"tk{z}", accent if mk is markers[-1] else (0.6, 0.7, 0.9), 3.5))
    # the bottom: a pulsing dot
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22,
                                         location=(ox, 6.5, -depth))
    dot = bpy.context.object
    dm = _emission("dot", accent, 8.0)
    dot.data.materials.append(dm)
    em = dm.node_tree.nodes["Emission"].inputs["Strength"]
    for f, v in ((half + 1, 4.0), (int(frames * 0.85), 14.0), (frames, 7.0)):
        em.default_value = v
        em.keyframe_insert(data_path="default_value", frame=f)
    bpy.ops.object.light_add(type="AREA", location=(ox, -2, -depth / 2))
    dl = bpy.context.object
    dl.data.energy = 350
    dl.data.size = 25
    dl.rotation_euler = (math.radians(90), 0, 0)

    # world background
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = \
        (0.004, 0.006, 0.014, 1)
    sc.world = w

    # --- camera: dive (phase 1), then ride the bore down (phase 2) ---
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    # phase 1: from deep space toward the surface
    for f, (loc, rot) in ((1, ((0, -34, 10), (math.radians(73), 0, 0))),
                          (half, ((0, -8.2, 1.2),
                                  (math.radians(82), 0, 0)))):
        cam.location = loc
        cam.rotation_euler = rot
        cam.keyframe_insert(data_path="location", frame=f)
        cam.keyframe_insert(data_path="rotation_euler", frame=f)
    # phase 2: underground, facing the wall, riding down beside the bore,
    # holding on the pulsing dot for the final ~15%.
    for f, z in ((half + 1, -0.8), (int(frames * 0.85), -depth + 0.6),
                 (frames, -depth + 0.5)):
        cam.location = (ox, -7.0, z)   # pulled back: readable, roomy frame
        cam.rotation_euler = (math.radians(90), 0, 0)
        cam.keyframe_insert(data_path="location", frame=f)
        cam.keyframe_insert(data_path="rotation_euler", frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

    _render_settings(sc, spec)


def _stars(n=120, spread=600.0, exclude=60.0, bright=5.0):
    """Deterministic emission star field (no RNG — resumable renders).
    Emission spheres are noise-free on CPU Cycles: free production value."""
    for i in range(n):
        a = (i * 2.399963) % (2 * math.pi)          # golden angle
        r = exclude + (spread - exclude) * (((i * 73) % 97) / 97.0)
        zz = (((i * 41) % 89) / 89.0 - 0.5) * spread * 0.55
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=spread / 900.0 * (0.5 + ((i * 13) % 7) / 7.0),
            location=(r * math.cos(a), r * math.sin(a), zz),
            segments=8, ring_count=4)
        bpy.context.object.data.materials.append(
            _emission(f"star{i}", (0.85, 0.9, 1.0), bright))


def _the_earth(radius=5.0, loc=(0, 0, 0), parent=None):
    """THE Earth (sea sphere + squashed continent shells + atmosphere),
    reused by every space template. Returns the sea sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc,
                                         segments=48, ring_count=24)
    sea = bpy.context.object
    bpy.ops.object.shade_smooth()
    sea.data.materials.append(_body("earth_sea", (0.05, 0.18, 0.42)))
    k = radius / 5.0
    for i, (dx, dy, dz, r) in enumerate([(2.2, -3.4, 2.6, 1.5),
                                         (-3.0, -3.2, 0.6, 1.2),
                                         (0.8, -4.4, -2.0, 1.7),
                                         (-1.8, -3.8, 2.8, 1.0)]):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=r * k, location=(loc[0] + dx * k, loc[1] + dy * k,
                                    loc[2] + dz * k),
            segments=24, ring_count=12)
        blob = bpy.context.object
        bpy.ops.object.shade_smooth()
        blob.scale = (1.0, 0.35, 1.0)
        blob.data.materials.append(_body(f"land{i}", (0.10, 0.34, 0.18)))
        blob.parent = parent if parent is not None else sea
        if parent is None:
            blob.matrix_parent_inverse = sea.matrix_world.inverted()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.05, location=loc,
                                         segments=32, ring_count=16)
    atmo = bpy.context.object
    m = bpy.data.materials.new("atmo")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.3, 0.55, 1.0, 1)
    bsdf.inputs["Alpha"].default_value = 0.08
    m.blend_method = "BLEND"
    atmo.data.materials.append(m)
    return sea


def _dark_world(sc):
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = \
        (0.004, 0.006, 0.014, 1)
    sc.world = w


def _frames(sc, spec):
    fps = int(spec.get("fps", 10))
    frames = max(4, int(round(fps * float(spec.get("seconds", 7)))))
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    return frames


def _bezier(cam):
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"


def build_earth_spin(spec: dict):
    """Premium reveal for 'the ground is moving': THE Earth visibly
    ROTATING under sunlight while the camera arcs closer — continents
    sweep past; a faint equatorial speed band hints the motion's edge."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    accent = _hex(spec.get("accent", "#4FD1C5"))
    frames = _frames(sc, spec)

    bpy.ops.object.empty_add(location=(0, 0, 0))
    spin = bpy.context.object                    # continents parent
    _the_earth(5.0, (0, 0, 0), parent=spin)
    spin.rotation_euler = (0, 0, 0)
    spin.keyframe_insert(data_path="rotation_euler", frame=1)
    spin.rotation_euler = (0, 0, 1.0)            # ~57 deg of visible spin
    spin.keyframe_insert(data_path="rotation_euler", frame=frames)
    # equatorial speed band
    bpy.ops.mesh.primitive_torus_add(major_radius=5.14, minor_radius=0.015,
                                     location=(0, 0, 0))
    bpy.context.object.data.materials.append(
        _emission("belt", accent, 1.8))
    bpy.ops.object.light_add(type="SUN", location=(24, -20, 12))
    bpy.context.object.data.energy = 4.5
    _stars(110, spread=420.0, exclude=90.0, bright=4.0)
    _dark_world(sc)

    bpy.ops.object.empty_add(location=(0, 0, 0.4))
    target = bpy.context.object
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    cam.data.clip_end = 1500
    cam.constraints.new(type="TRACK_TO").target = target
    for f, loc in ((1, (6.0, -30.0, 8.0)), (frames, (-6.0, -21.0, 4.5))):
        cam.location = loc
        cam.keyframe_insert(data_path="location", frame=f)
    _bezier(cam)
    _render_settings(sc, spec)


def build_orbit_fly(spec: dict):
    """The hook: the camera RACES along orbital space chasing THE Earth
    on its glowing path around the Sun — flying through, not looking at."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    accent = _hex(spec.get("accent", "#4FD1C5"))
    frames = _frames(sc, spec)

    # the Sun: emission sphere lights the whole scene noise-free
    bpy.ops.mesh.primitive_uv_sphere_add(radius=8, location=(0, 0, 0),
                                         segments=32, ring_count=16)
    bpy.context.object.data.materials.append(
        _emission("sun", (1.0, 0.82, 0.45), 30.0))
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 60))
    bpy.context.object.data.energy = 2.0
    # the orbit path + a farther, fainter sibling for depth
    bpy.ops.mesh.primitive_torus_add(major_radius=40, minor_radius=0.06,
                                     location=(0, 0, 0))
    bpy.context.object.data.materials.append(
        _emission("path", accent, 3.0))
    bpy.ops.mesh.primitive_torus_add(major_radius=70, minor_radius=0.05,
                                     location=(0, 0, 0))
    bpy.context.object.data.materials.append(
        _emission("path2", (0.35, 0.42, 0.6), 1.2))

    # Earth rides the path (parented to a rotating empty)…
    bpy.ops.object.empty_add(location=(0, 0, 0))
    eorb = bpy.context.object
    earth = _the_earth(1.6, (40, 0, 0))
    earth.parent = eorb
    earth.matrix_parent_inverse = eorb.matrix_world.inverted()
    eorb.rotation_euler = (0, 0, 0)
    eorb.keyframe_insert(data_path="rotation_euler", frame=1)
    eorb.rotation_euler = (0, 0, 0.55)
    eorb.keyframe_insert(data_path="rotation_euler", frame=frames)
    # …the camera chases on a slower arc just outside the ring
    bpy.ops.object.empty_add(location=(0, 0, 0))
    corb = bpy.context.object
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    cam.data.clip_end = 2000
    cam.location = (47.0, -10.0, 5.5)   # off-axis: Sun clears Earth's disc
    cam.parent = corb
    cam.matrix_parent_inverse = corb.matrix_world.inverted()
    cam.constraints.new(type="TRACK_TO").target = earth
    corb.rotation_euler = (0, 0, 0)
    corb.keyframe_insert(data_path="rotation_euler", frame=1)
    corb.rotation_euler = (0, 0, 0.40)
    corb.keyframe_insert(data_path="rotation_euler", frame=frames)
    for fc in corb.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    _stars(130, spread=700.0, exclude=110.0, bright=4.5)
    _dark_world(sc)
    _render_settings(sc, spec)


def build_cosmic_exit(spec: dict):
    """The ending: the camera can no longer hold — it is DRAGGED away
    from Earth, accelerating out past the orbit rings toward the galaxy,
    stars smearing into streaks as the world hits cosmic."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    accent = _hex(spec.get("accent", "#4FD1C5"))
    frames = _frames(sc, spec)

    earth = _the_earth(5.0, (0, 0, 0))
    # the Sun, far off-axis — enters frame as we recede
    bpy.ops.mesh.primitive_uv_sphere_add(radius=12,
                                         location=(220, 120, 60),
                                         segments=32, ring_count=16)
    bpy.context.object.data.materials.append(
        _emission("sun", (1.0, 0.82, 0.45), 40.0))
    bpy.ops.object.light_add(type="SUN", location=(40, -20, 30))
    bpy.context.object.data.energy = 3.0
    # orbit rings around the Sun (ours through Earth, siblings beyond)
    for r, br in ((255, 2.0), (180, 1.2), (330, 1.0)):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=r, minor_radius=0.18, location=(220, 120, 0))
        bpy.context.object.data.materials.append(
            _emission(f"ring{r}", accent if r == 255 else (0.35, 0.42, 0.6),
                      br))
    # galaxy hint beyond the Sun: a flat spiral of emission points
    for i in range(90):
        th = 0.35 * i
        rr = 40 + 6.5 * th
        x = 800 + rr * math.cos(th)
        y = 500 + rr * math.sin(th)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=2.4, location=(x, y, 120 + (((i * 7) % 11) - 5) * 4),
            segments=6, ring_count=3)
        bpy.context.object.data.materials.append(
            _emission(f"gal{i}", (0.75, 0.8, 1.0), 3.0))
    # star STREAKS along the exit corridor — dark until the acceleration,
    # then they smear into view (the world's answer to cosmic intensity)
    streak_mats = []
    for i in range(46):
        a = (i * 2.399963) % (2 * math.pi)
        rr = 26 + (((i * 73) % 97) / 97.0) * 130
        yy = -80 - (((i * 41) % 89) / 89.0) * 1050
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.32, depth=1,
            location=(rr * math.cos(a), yy, rr * math.sin(a)))
        st = bpy.context.object
        st.rotation_euler = (math.radians(90), 0, 0)
        st.scale = (1, 1, 34)                       # long smear along -y
        mm = _emission(f"streak{i}", (0.85, 0.9, 1.0), 0.0)
        st.data.materials.append(mm)
        streak_mats.append(mm)
    for mm in streak_mats:
        em = mm.node_tree.nodes["Emission"].inputs["Strength"]
        for f, v in ((1, 0.0), (int(frames * 0.5), 0.0),
                     (int(frames * 0.72), 5.0), (frames, 7.0)):
            em.default_value = v
            em.keyframe_insert(data_path="default_value", frame=f)
    _stars(120, spread=1400.0, exclude=140.0, bright=5.0)
    _dark_world(sc)

    bpy.ops.object.empty_add(location=(0, 0, 0))
    target = bpy.context.object
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    cam.data.clip_end = 8000
    cam.constraints.new(type="TRACK_TO").target = target
    for f, loc in ((1, (2.0, -15.0, 4.0)),
                   (int(frames * 0.35), (6.0, -75.0, 20.0)),
                   (int(frames * 0.70), (14.0, -400.0, 90.0)),
                   (frames, (30.0, -1350.0, 280.0))):
        cam.location = loc
        cam.keyframe_insert(data_path="location", frame=f)
    _bezier(cam)
    _render_settings(sc, spec)


def _render_settings(sc, spec):
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(spec.get("samples", 32))
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.cycles.max_bounces = 3
    sc.render.use_persistent_data = True
    sc.cycles.use_denoising = False
    sc.render.resolution_x = int(spec.get("res_x", 1920))
    sc.render.resolution_y = int(spec.get("res_y", 1080))
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Filmic"
    sc.view_settings.look = "Medium High Contrast"


TEMPLATES = {"monoliths": build, "earth_dive": build_earth_dive,
             "earth_spin": build_earth_spin, "orbit_fly": build_orbit_fly,
             "cosmic_exit": build_cosmic_exit}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    spec = json.loads(open(argv[0]).read())
    outdir = argv[1]
    TEMPLATES.get(spec.get("template", "monoliths"), build)(spec)
    sc = bpy.context.scene
    sc.render.filepath = outdir.rstrip("/") + "/hero_"
    if "probe" in argv:
        # look-check: first / mid / last frames only
        sc.frame_step = max(1, (sc.frame_end - 1) // 2)
    bpy.ops.render.render(animation=True)
    print("HERO_DONE", sc.frame_end)


if __name__ == "__main__":
    main()
