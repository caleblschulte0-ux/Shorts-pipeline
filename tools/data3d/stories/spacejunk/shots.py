"""space junk through a roof (Naples, Florida, 8 March 2024): the first daily-pipeline short, staged with
store/director.py. Five beats, five photographed places, one locked lens each; the world acts and Data reacts."""
import math, random
import bpy
from mathutils import Vector
import director as D

BIG = 2.4      # the stanchion is 10 cm tall: drawn this many times its size where the frame is a whole room


def _metal(name, col, rough=0.45, metal=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    return m


def junk(p, scale=1.0, name="space junk"):
    """the piece that survived: a scorched metal cylinder, 10 cm tall and 4 cm across, a collar at each end"""
    h = 0.10 * D.U * scale; r = 0.02 * D.U * scale
    body = _metal(name + " metal", (0.5, 0.48, 0.45), 0.42); burn = _metal(name + " burn", (0.12, 0.1, 0.09), 0.7)
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root); root.location = p
    for z, rr, hh, m in ((0, r, h, body), (-h * 0.42, r * 1.25, h * 0.12, burn), (h * 0.42, r * 1.25, h * 0.12, burn), (0, r * 1.06, h * 0.3, burn)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=rr, depth=hh, location=(0, 0, z)); o = bpy.context.active_object
        bpy.ops.object.shade_smooth(); o.data.materials.append(m); o.parent = root; o.name = name + " part"
    return root


def soda_can(p, scale=1.0):
    h = 0.122 * D.U * scale; r = 0.033 * D.U * scale
    red = _metal("can red", (0.5, 0.03, 0.03), 0.45, 0.6); top = _metal("can top", (0.8, 0.8, 0.82), 0.25)
    root = bpy.data.objects.new("soda can", None); bpy.context.collection.objects.link(root); root.location = p
    for z, rr, hh, m in ((h * 0.5, r, h * 0.92, red), (h * 0.975, r * 0.9, h * 0.05, top), (h * 0.02, r * 0.9, h * 0.04, top)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=rr, depth=hh, location=(0, 0, z)); o = bpy.context.active_object
        bpy.ops.object.shade_smooth(); o.data.materials.append(m); o.parent = root; o.name = "soda can part"
    return root


def hole(s, p, r=0.075, seed=3, wood=(0.55, 0.38, 0.2)):
    """a hole punched in the floor at p: a black opening and the floor's own splinters thrown up round its edge"""
    m = bpy.data.materials.new("hole dark"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (0.004, 0.003, 0.003, 1); o_ = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o_.inputs[0])
    rnd = random.Random(seed); vs = []
    for k in range(18):
        a = 2 * math.pi * k / 18; rr = r * rnd.uniform(0.72, 1.18); vs.append((math.cos(a) * rr, math.sin(a) * rr * 0.9, 0))
    me = bpy.data.meshes.new("hole"); me.from_pydata(vs, [], [list(range(18))]); o = bpy.data.objects.new("hole", me)
    bpy.context.collection.objects.link(o); o.location = (p[0], p[1], 0.003); me.materials.append(m)
    sp = bpy.data.materials.new("splinter"); sp.use_nodes = True; sp.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*wood, 1)
    sp.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    parts = [o]
    for k in range(14):
        a = rnd.uniform(0, 2 * math.pi); d = r * rnd.uniform(0.85, 1.25); L = rnd.uniform(0.03, 0.07)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(p[0] + math.cos(a) * d, p[1] + math.sin(a) * d * 0.9, L * 0.15))
        b = bpy.context.active_object; b.scale = (L, rnd.uniform(0.008, 0.016), 0.004); b.rotation_euler = (0, -rnd.uniform(0.15, 0.6), a)
        b.data.materials.append(sp); b.name = "splinter"; parts.append(b)
    return parts


def shot1():
    """the living room: it comes through the ceiling and punches into the floor in front of him"""
    s = D.Shot(globals(), "living_room"); s.place("lebombo", turn=135)
    s.hero(u=0.3, height=0.44)
    sofa = s.model("sofa_03", u=0.86, v=0.31, yaw=-25, scale=0.62)
    hit = s.spot(0.63, 0.14); top = s.air(0.66, 1.25, (hit - s.C).length)
    j = junk(tuple(top), BIG); T = 0.24
    s.fall(j, top, hit + Vector((0, 0, 0.02)), T - 0.035, T, spin=(260, 120, 40))
    s.appear(j, T + 0.004, show=False)                        # it goes on through the floor
    hp = hole(s, hit)
    for o in hp: s.appear(o, T)
    plaster = D.FX.ph_mat("white_plaster_02", scale=0.6)
    bits = s.debris(top + Vector((0, 0, -0.1)), 26, T - 0.03, plaster, speed=1.3, size=(0.01, 0.035), seed=4, spread=0.5, up=-0.6)
    s.dust(hit, T, w=0.7, h=1.0, dur=2.6, col=(0.86, 0.84, 0.8), dens=1.4)
    s.dust(top + Vector((0, 0, -0.5)), T - 0.02, w=0.6, h=0.9, dur=3.0, col=(0.86, 0.84, 0.8), dens=1.0, seed=2.0)
    s.shake(T, amp=0.035, dur=0.6); s.flash(hit + Vector((0, 0, 0.1)), T, power=120, dur=0.25)
    s.act([(0.02, "look", "lens"), (0.03, "happy"), (T + 0.01, "alarmed"), (T + 0.05, "whoa"), (0.42, "look", hit), (0.62, "look", top + Vector((0, 0, -0.6))),
           (0.66, "worried"), (0.86, "look", "lens")])
    s.happens("a piece of metal comes through the ceiling and punches a hole in the floor", [j] + hp, T - 0.04, 0.6, moves=[j] + bits)
    return s.done()


def pallet(p, scale=1.0):
    """the load NASA let go: a flat cargo pallet carrying nine old batteries, 2.6 tonnes"""
    root = bpy.data.objects.new("battery pallet", None); bpy.context.collection.objects.link(root); root.location = p
    base = _metal("pallet base", (0.55, 0.56, 0.58), 0.6, 0.2); cell = _metal("battery", (0.9, 0.9, 0.88), 0.7, 0.0); edge = _metal("pallet gold", (0.8, 0.55, 0.12), 0.5, 0.3)
    def box(loc, sz, m):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object; o.scale = sz; o.data.materials.append(m); o.parent = root; o.name = "pallet part"
    k = scale; box((0, 0, 0), (1.6 * k, 1.2 * k, 0.12 * k), base)
    for i in range(3):
        for jx in range(3):
            box(((i - 1) * 0.5 * k, (jx - 1) * 0.37 * k, 0.24 * k), (0.42 * k, 0.3 * k, 0.34 * k), cell)
    for sx in (-1, 1): box((sx * 0.84 * k, 0, 0.06 * k), (0.08 * k, 1.24 * k, 0.3 * k), edge)
    return root


def shot2():
    """the back garden by day: high over the hedge the pallet of old batteries drifts across the sky, tumbling"""
    s = D.Shot(globals(), "back_garden_day"); s.place("suburban_garden", turn=45)
    s.hero(u=0.3, height=0.4, face_v=0.5)
    a, b = s.air(1.25, 0.9, 9.0), s.air(-0.2, 0.72, 9.0)
    pl = pallet(tuple(a), 1.25); pl.rotation_euler = (0.5, 0.2, 0.3)
    s.move(pl, [(0.0, a, (30, 10, 20)), (1.0, b, (160, 70, 110))], ease=False)
    s.act([(0.02, "look", "lens"), (0.12, "look", pl), (0.3, "surprised"), (0.5, "look", pl), (0.55, "whoa"), (0.75, "look", pl), (0.9, "look", "lens")])
    s.happens("a pallet of old batteries drifts across the sky over the garden", [pl], 0.0, 1.0, moves=[pl])
    return s.done()


def _glow(name, col, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*col, 1); e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o.inputs[0])
    return m, e


def fireball(s, a, b, t0, t1, r=0.16, tail=2.2, die=None, name="fireball", col=(1.0, 0.55, 0.18)):
    """a burning piece crossing the sky from a to b: a white-hot head and a long tapering tail behind it. die: the
    time it has burned away to nothing by (None: it lasts)"""
    t0, t1 = s.T(t0), s.T(t1); a, b = Vector(a), Vector(b); d = (b - a).normalized()
    hm, he = _glow(name + " head", (1.0, 0.9, 0.7), 60.0); tm, te = _glow(name + " tail", col, 9.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=20, ring_count=12, location=a); head = bpy.context.active_object; head.data.materials.append(hm); head.name = name
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=r * 0.85, radius2=0.0, depth=tail, location=(0, 0, 0)); tl = bpy.context.active_object
    tl.data.materials.append(tm); tl.name = name + " tail"; tl.parent = head; tl.rotation_euler = (-d).to_track_quat('Z', 'Y').to_euler(); tl.location = -d * tail * 0.5
    head.visible_shadow = False; tl.visible_shadow = False
    td = s.T(die) if die is not None else None
    for f in range(1, s.NF + 1):
        x = (f - 1) / D.FPS; u = (x - t0) / max(1e-6, t1 - t0)
        head.location = a.lerp(b, max(0.0, min(1.0, u))); head.keyframe_insert("location", frame=f)
        k = 0.0 if u < 0 else (1.0 if td is None else max(0.0, min(1.0, (td - x) / max(1e-6, td - t0)))) if u <= 1 or td is None else 0.0
        if td is None and u > 1: k = 0.0
        head.scale = (k, k, k); head.keyframe_insert("scale", frame=f)
    return head


def shot3():
    """the same sky at night, three years on: the pallet comes back as a fireball, breaks up, burns away piece by
    piece, and one piece keeps going down behind the trees"""
    s = D.Shot(globals(), "night_field"); s.place("preller_drive", turn=180, light=2.2, plate=2.0)
    s.hero(u=0.28, height=0.38, face_v=0.42)
    a = s.air(1.15, 0.97, 14.0); m = s.air(0.62, 0.8, 14.0)
    main = fireball(s, a, m, 0.0, 0.42, r=0.8, tail=9.0, die=0.44, name="pallet burning")
    rnd = random.Random(7); pieces = []
    for k in range(7):
        e = s.air(0.62 - rnd.uniform(0.12, 0.5), 0.8 - rnd.uniform(0.02, 0.2), 14.0)
        pieces.append(fireball(s, m, e, 0.40, 0.62 + 0.03 * k, r=rnd.uniform(0.2, 0.34), tail=rnd.uniform(3.0, 5.0), die=0.56 + 0.035 * k, name=f"piece {k}"))
    end = s.air(0.5, 0.54, 14.0)
    last = fireball(s, m, end, 0.40, 0.84, r=0.3, tail=4.5, name="the one that lived", col=(1.0, 0.7, 0.3))
    s.glow(s.air(0.7, 0.8, 5.0), power=260, col=(1.0, 0.6, 0.3), keys=[(0.0, 0.2), (0.4, 1.0), (0.62, 0.35), (0.86, 0.0)], r=1.0)
    s.flash(end, 0.84, power=3000, dur=0.5, r=1.0)
    s.act([(0.02, "look", main), (0.2, "surprised"), (0.3, "look", m), (0.5, "worried"), (0.6, "look", last), (0.8, "look", end), (0.86, "alarmed"), (0.95, "look", "lens")])
    s.happens("a fireball crosses the night sky and breaks up; the pieces burn away but one keeps falling", [main, last] + pieces, 0.0, 0.9, moves=[main, last] + pieces)
    return s.done()


def shot4():
    """the room upstairs: the hole it left, and the piece itself on the tiles beside a soda can"""
    s = D.Shot(globals(), "upstairs_room"); s.place("small_empty_house", turn=225)
    s.hero(u=0.7, height=0.5, face_v=0.6)
    hp = hole(s, s.spot(0.22, 0.22), r=0.09, seed=9, wood=(0.78, 0.72, 0.62))
    pj = s.spot(0.3, 0.07); pc = s.spot(0.46, 0.07)
    j = junk((pj.x, pj.y, 0.05 * D.U * 2.0 + 0.6), 2.0); can = soda_can((pc.x, pc.y, 0.0), 2.0)
    j.rotation_euler = (0, 0, 0.4)
    s.fall(j, Vector((pj.x, pj.y, 0.9)), Vector((pj.x, pj.y, 0.05 * D.U * 2.0)), 0.3, 0.36, spin=(0, 0, 90), bounce=0.04)
    s.appear(j, 0.29)
    s.act([(0.02, "look", hp[0]), (0.05, "worried"), (0.36, "look", j), (0.42, "surprised"), (0.62, "look", can), (0.74, "look", j), (0.88, "look", "lens"), (0.9, "wry")])
    s.happens("the piece that did it lands on the tiles beside a soda can, and it is smaller", [j, can], 0.29, 0.5, moves=[j])
    return s.done()


def shot5():
    """out front: the house, the repair kit on the drive, and the question"""
    s = D.Shot(globals(), "front_drive"); s.place("suburban_parking_area", turn=225)
    s.hero(u=0.32, height=0.46)
    crate = s.model("wooden_crate_01", u=0.72, v=0.2, yaw=20)
    box = s.model("cardboard_box_01", u=0.86, v=0.24, yaw=-15)
    tool = s.model("metal_toolbox", u=0.6, v=0.12, yaw=35)
    top = D.compose.corners(s.parts(crate)); zt = max(c[2] for c in top); pc = s._point(crate)
    j = junk((pc.x, pc.y, zt + 0.05 * D.U * BIG + 1.2), BIG)
    s.fall(j, Vector((pc.x, pc.y, zt + 1.4)), Vector((pc.x, pc.y, zt + 0.05 * D.U * BIG)), 0.12, 0.2, spin=(0, 0, 120), bounce=0.05)
    s.shake(0.2, amp=0.012, dur=0.3)
    s.act([(0.02, "look", "lens"), (0.14, "look", j), (0.22, "surprised"), (0.4, "look", "lens"), (0.45, "determined"), (0.7, "look", j), (0.82, "look", "lens"), (0.84, "shrug")])
    s.happens("the piece drops onto the crate of repair gear beside him", [j], 0.12, 0.3, moves=[j])
    return s.done()


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
