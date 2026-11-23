"""BEAT 2, ONE BEE'S LIFE: the hive yard on the hill. He flips open his hive and holds up a teaspoon as big as his arm,
its round bowl marked like a pie into twelve wedges; one bee flies out to it, wrings out her single golden drop, and
it fills ONE wedge of the twelve; she flops on the rim, worn out, and eleven more bees queue up in the air for the rest
(one bee makes about a twelfth of a teaspoon in her whole life)."""


def s2_tuft(name, x, y, rnd, grass):
    """a tuft of tall meadow grass: a few thin blades fanned out"""
    for k in range(4):
        h = rnd.uniform(0.08, 0.16); a = rnd.uniform(0, 2 * math.pi); lean = rnd.uniform(0.1, 0.35)
        b = K.box(name, (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), h / 2), (0.008, 0.002, h), grass, bev=0)
        b.rotation_euler = (lean * math.sin(a), -lean * math.cos(a), a)


def s2_hive(name, loc, rnd, paint="#F4F1E8", lid=True):
    """a white wooden beehive: a stand, three stacked boxes, an entrance slot at the bottom front, a gabled lid hinged
    at its back edge. Returns dict(root, lid) (lid is an empty at the hinge; the lid's mesh rides it)."""
    x, y = loc
    wood = hw_noise(f"hive paint {paint}", paint, K.mute(paint, 0.9), scale=8, rough=0.7, bump=0.15, stretch=(1, 1, 5))
    dark = K.mat("hive slot", "#2A2018", rough=0.9)
    W, D = 0.24, 0.26
    K.box(name + " stand", (x, y, 0.04), (W + 0.04, D + 0.04, 0.08), hw_wood("hive stand", "#6E5232", "#8A6A44"), bev=0.004)
    for k in range(2):
        K.box(name + " box", (x, y, 0.08 + 0.065 + k * 0.13), (W, D, 0.125), wood, bev=0.004)
        for sg in (-1, 1):
            K.box(name + " handle", (x + sg * (W / 2 + 0.004), y, 0.08 + 0.09 + k * 0.13), (0.008, 0.08, 0.016), wood, bev=0.002)
    K.box(name + " slot", (x, y - D / 2 - 0.002, 0.095), (0.16, 0.006, 0.014), dark, bev=0)
    K.box(name + " landing board", (x, y - D / 2 - 0.03, 0.085), (0.2, 0.06, 0.01), wood, bev=0.002)
    z_top = 0.08 + 0.26
    hinge = K.empty(name + " lid hinge", (x, y + D / 2 + 0.01, z_top))
    roofm = K.mat("hive roof tin", "#B8BCC0", rough=0.35, metal=0.7)
    lid_parts = [K.box(name + " lid", (x, y, z_top + 0.03), (W + 0.04, D + 0.04, 0.05), wood, bev=0.004)]
    for sg in (-1, 1):
        o = K.box(name + " lid roof", (x + sg * 0.09, y, z_top + 0.075), (0.2, D + 0.06, 0.008), roofm, bev=0.002)
        o.rotation_euler = (0, sg * 0.3, 0); lid_parts.append(o)
    for o in lid_parts:                     # built absolute: parent them to the hinge keeping where they are
        o.parent = hinge; o.matrix_parent_inverse = HW_M.Translation(-Vector((x, y + D / 2 + 0.01, z_top)))
    return dict(hinge=hinge, top=z_top, front=Vector((x, y - D / 2, z_top + 0.05)), slot=Vector((x, y - D / 2 - 0.03, 0.1)), W=W, D=D)


def s2_spoon(name, R=0.15, L=0.16):
    """the giant teaspoon, built upright: its grip at the origin, the handle up +Z, the round bowl at the top facing -Y,
    marked like a pie into twelve wedges by thin dark lines. Returns dict(root, center, fill, R)."""
    root = K.empty(name, (0, 0, 0))
    steel = K.mat("spoon steel", "#D9DDE2", rough=0.22, metal=0.85)
    K.capsule(name + " handle", Vector((0, 0, 0.0)), Vector((0, 0, L)), 0.018, steel, parent=root)
    c = Vector((0, 0, L + R * 0.95))
    K.cyl(name + " bowl", tuple(c + Vector((0, 0.012, 0))), R, 0.02, steel, rot=(math.pi / 2, 0, 0), v=64, bev=0.006, parent=root)
    K.cyl(name + " bowl rim", tuple(c + Vector((0, 0.0, 0))), R * 1.03, 0.012, steel, rot=(math.pi / 2, 0, 0), v=64, bev=0.004, parent=root)
    inner = K.cyl(name + " bowl face", tuple(c + Vector((0, -0.007, 0))), R * 0.94, 0.004, K.mat("spoon face", "#EEF0F2", rough=0.3, metal=0.4),
                  rot=(math.pi / 2, 0, 0), v=64, bev=0, parent=root)
    ink = K.mat("spoon marks", "#2B2B30", rough=0.6)
    for k in range(12):                     # the twelve wedges, like a pie
        a = math.radians(30 * k + 15)
        o = K.box(name + " mark", tuple(c + Vector((math.cos(a) * R * 0.47, -0.01, math.sin(a) * R * 0.47))), (R * 0.94, 0.002, 0.004), ink, bev=0, parent=root)
        o.rotation_euler = (0, -a, 0)
    K.cyl(name + " hub", tuple(c + Vector((0, -0.011, 0))), 0.008, 0.002, ink, rot=(math.pi / 2, 0, 0), v=16, bev=0, parent=root)
    # the one wedge her drop fills: a gold fan pointing straight down (where a drop runs), grown out from the hub
    bm = HW_bmesh.new(); n = 10; rr = R * 0.92
    verts = [bm.verts.new((0, 0, 0))] + [bm.verts.new((rr * math.cos(math.radians(-105 + 30 * i / n)), 0, rr * math.sin(math.radians(-105 + 30 * i / n)))) for i in range(n + 1)]
    for i in range(n): bm.faces.new((verts[0], verts[i + 1], verts[i + 2]))
    me = bpy.data.meshes.new(name + " fill"); bm.to_mesh(me); bm.free()
    fill = bpy.data.objects.new(name + " fill", me); me.materials.append(K.mat("spoon honey gold", "#F2A81E", rough=0.2, emit=0.35))
    bpy.context.collection.objects.link(fill)
    sd = fill.modifiers.new("thick", 'SOLIDIFY'); sd.thickness = 0.006
    fill.parent = root; fill.location = c + Vector((0, -0.013, 0))
    hw_local(root)
    return dict(root=root, center=c, fill=fill, R=R)


def place_hive_yard():
    """HIS HIVE YARD on the hill above the village: a meadow of tall grass and wildflowers, his white hives in a row,
    a split-rail fence, two apple trees, a stone shed, and the village's red roofs and church far down the hill."""
    rnd = hw_random.Random(22)
    meadow = hw_noise("meadow", "#5E8A32", "#A4C45A", scale=22, rough=0.95, bump=1.0, detail=8, lo=0.36, hi=0.66)
    K.box("meadow ground", (0, 4, -0.01), (30, 30, 0.02), meadow, bev=0)
    hill = hw_noise("far hill", "#6F9A40", "#A2BD62", scale=9, rough=0.95, bump=0.5, detail=5)
    K.sph("far hill", (0, 12, -4.0), 6.0, hill, scale=(3.0, 1.2, 0.9))
    hedge = hw_noise("hedge", "#3F6E2A", "#5E8E38", scale=18, rough=0.9, bump=0.8, detail=5)
    for k in range(16):                         # a long hedge of round bushes behind the hives
        K.sph("hedge bush", (-3.0 + 0.4 * k + rnd.uniform(-0.05, 0.05), 2.6 + rnd.uniform(-0.1, 0.1), 0.3), rnd.uniform(0.28, 0.36), hedge, scale=(1.0, 0.8, 1.1), seg=20, ring=12)
    grass = [K.mat(f"blade {c}", c, rough=0.8) for c in ("#5E8A2E", "#7AA23C", "#8DB24A")]
    petals = [K.mat(f"flower {c}", c, rough=0.6) for c in ("#F2D43A", "#F4F0E6", "#C96BC0", "#E0583A", "#6E8CE0")]
    for k in range(320):
        x, y = rnd.uniform(-1.8, 2.0), rnd.uniform(-1.3, 2.4)
        if -0.5 < x < 0.6 and -0.55 < y < 0.45: continue                 # his patch and the hive's, trodden flat
        s2_tuft("meadow tuft", x, y, rnd, rnd.choice(grass))
    for k in range(220):                       # the meadow right under the lens: grass and flowers up close
        x, y = rnd.uniform(-1.0, 1.4), rnd.uniform(-1.25, -0.55)
        s2_tuft("near tuft", x, y, rnd, rnd.choice(grass))
        if k % 3 == 0:
            K.sph("near flower", (x + 0.02, y, rnd.uniform(0.08, 0.15)), rnd.uniform(0.012, 0.02), rnd.choice(petals), seg=10, ring=6)
        if k % 2 == 0:
            K.sph("wildflower", (x + 0.02, y, rnd.uniform(0.1, 0.17)), rnd.uniform(0.012, 0.02), rnd.choice(petals), seg=10, ring=6)
    hives = [s2_hive(f"hive {k}", (x, y), rnd) for k, (x, y) in enumerate(((-1.0, 1.0), (-0.35, 1.25), (0.35, 1.45), (1.0, 1.25), (1.6, 0.9)))]
    rail = hw_wood("fence rail", "#7C6446", "#9A7E5A", scale=4)
    for k in range(14):
        x = -2.4 + 0.42 * k
        K.box("fence post", (x, 3.1, 0.24), (0.04, 0.04, 0.48), rail, bev=0.004)
    for z in (0.18, 0.36):
        K.box("fence rail", (0.33, 3.1, z), (5.6, 0.025, 0.03), rail, bev=0.003)
    leaf = hw_noise("apple leaves", "#4E7E32", "#6E9C40", scale=10, rough=0.85, bump=0.4)
    bark = hw_wood("apple bark", "#5A4330", "#6E5440", scale=8)
    for k, (x, y) in enumerate(((-1.3, 1.9), (1.4, 2.0), (-0.2, 2.9), (0.7, 3.4), (2.4, 2.9), (-2.2, 2.8))):
        K.cyl("apple trunk", (x, y, 0.65), 0.07, 1.3, bark, v=12, bev=0.01)
        for j in range(5):
            K.sph("apple crown", (x + rnd.uniform(-0.35, 0.35), y + rnd.uniform(-0.2, 0.2), 1.55 + rnd.uniform(-0.15, 0.35)), rnd.uniform(0.4, 0.55), leaf, seg=20, ring=12)
        for j in range(8):
            K.sph("apple", (x + rnd.uniform(-0.4, 0.4), y - 0.25 + rnd.uniform(-0.1, 0.1), 1.4 + rnd.uniform(-0.1, 0.4)), 0.035, K.mat("apple red", "#C8352A", rough=0.4), seg=12, ring=8)
    stone = hw_noise("shed stone", "#B5AB98", "#CFC6B2", scale=10, rough=0.9, bump=0.5)
    K.box("stone shed", (-2.6, 3.8, 0.45), (1.2, 0.9, 0.9), stone, bev=0.02)
    K.box("shed roof", (-2.6, 3.8, 0.95), (1.35, 1.05, 0.1), K.mat("roof tile", "#A4512E", rough=0.8), bev=0.01)
    K.box("shed door", (-2.6, 3.34, 0.32), (0.3, 0.02, 0.6), K.mat("door wood", "#5C3A22", rough=0.6), bev=0.006)
    # the village far down the hill: red roofs and the church tower over the meadow's edge
    walls = [K.mat(f"far wall {c}", c, rough=0.9) for c in ("#E9D9B8", "#E2C59A", "#EFE4CF")]
    for k in range(16):
        x = -5 + k * 0.65 + rnd.uniform(-0.1, 0.1); y = 9 + rnd.uniform(-0.5, 0.8)
        K.box("far house", (x, y, -0.2), (0.5, 0.4, 0.6), rnd.choice(walls), bev=0.01)
        K.box("far roof", (x, y, 0.13), (0.56, 0.46, 0.1), K.mat("roof tile", "#A4512E", rough=0.8), bev=0.01)
    K.box("far church", (1.5, 9.6, 0.4), (0.4, 0.4, 1.6), walls[2], bev=0.01)
    K.cyl("far church roof", (1.5, 9.6, 1.4), 0.3, 0.45, K.mat("roof tile", "#A4512E", rough=0.8), v=4, bev=0.01).rotation_euler = (0, 0, math.pi / 4)

    def light():
        return village_light(sun_elev=48, sun_az=-30, sun=3.8, sky=0.35)
    return light, hives


def shot2():
    """ONE BEE'S LIFE. The lens wide and low in front of his hive; he leans over and flips its lid open, raises the giant
    spoon out beside him, its twelve wedges to us; one bee flies out to it, wrings her single drop into the bottom wedge
    and it fills; she flops on the rim; he gapes and pushes the spoon at us; eleven bees file out and queue behind it."""
    T_LID = 0.35                                  # his hand on the lid ...
    T_OPEN = 0.75                                 # ... it falls open (and the spoon comes up: arc 0.08)
    T_OUT = 0.25 * DUR                            # one bee flies out
    T_LAND = T_OUT + 0.7                          # ... and lands in the bowl
    T_DROP = 0.45 * DUR                           # her drop
    T_FULL = T_DROP + 0.5                         # one wedge full
    T_FLOP = 0.6 * DUR                            # she flops on the rim
    T_PUSH = T_FLOP + 0.5                         # he pushes the spoon at us: ONE wedge
    T_Q = 0.76 * DUR                              # eleven more file out
    T_SHRUG = T_Q + 0.6
    light, hives = place_hive_yard()
    hive = s2_hive("his hive", (-0.27, 0.04), hw_random.Random(5))
    data = load_data()
    P0 = Vector((0.08, -0.06, 0.0)); YAW = math.radians(-8)
    data.place(P0.x, P0.y, math.degrees(YAW))
    CAM = Vector((0.16, -1.28, 0.64)); LOOK = Vector((0.16, -0.08, 0.44))
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).x)        # [toward -X (the hive), toward +X]
    lid_side, sp_side = sides[0], sides[1]
    hat = bee_hat(data)
    W = hw_win
    # ---- his body: every beat of it a move you can see on a phone
    def body(t):
        p = P0.copy()
        p += Vector((-0.04, 0.04, 0)) * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35))           # leans over the hive for the lid
        p += Vector((0.05, -0.03, 0)) * W(t, T_OPEN, 0.4)                                    # steps out, the spoon up
        p += Vector((-0.04, 0.0, 0)) * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))   # ducks to the slot to see her out
        p.z -= 0.03 * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))
        p += Vector((0.06, -0.03, 0)) * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL + 0.05, 0.25))   # in close to the bowl for her drop
        p += Vector((0.07, -0.05, 0)) * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25))   # ... closer as it fills
        p.z -= 0.03 * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25))
        p += Vector((-0.03, 0.05, 0)) * hw_kick(t - T_FLOP, 0.18)                              # rocks back, gaping
        p.z += 0.025 * hw_kick(t - T_FLOP, 0.12)
        p += Vector((0.0, -0.06, 0)) * W(t, T_PUSH, 0.3) * (1 - W(t, T_Q + 0.2, 0.4))          # steps at us with the spoon
        p.z -= 0.02 * W(t, T_SHRUG, 0.25)
        p += Vector((0.04, 0.06, 0)) * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3))          # steps back to see the queue
        p += Vector((-0.03, -0.05, 0)) * W(t, T_SHRUG, 0.3)                                     # and comes to us for the shrug
        yaw = YAW - math.radians(6) * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35)) - math.radians(16) * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.45, 0.35)) \
            + math.radians(14) * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL, 0.3)) - math.radians(20) * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3))
        return p, yaw
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (7 * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35)) + 10 * W(t, T_OUT - 0.1, 0.3) * (1 - W(t, T_OUT + 0.4, 0.3))
                                      + 12 * W(t, T_DROP - 0.35, 0.35) * (1 - W(t, T_FULL, 0.3)) + 10 * W(t, T_DROP + 0.05, 0.45) * (1 - W(t, T_FULL + 0.05, 0.25)) - 12 * hw_kick(t - T_FLOP, 0.2)
                                      + 8 * W(t, T_PUSH, 0.3) * (1 - W(t, T_Q, 0.4)) - 6 * W(t, T_Q + 0.05, 0.4) * (1 - W(t, T_SHRUG, 0.3)) + 10 * W(t, T_SHRUG, 0.3),
                                      0, -4 * W(t, 0.0, 0.3) * (1 - W(t, T_OPEN, 0.35))), 0, DUR + 0.4)
    for sd, sg in (("L", -1), ("R", 1)):          # the shrug: what can you do
        hw_layer(data, f"clav.{sd}", lambda t, sg=sg: (0, 0, sg * 20 * (W(t, T_SHRUG, 0.25) - W(t, T_SHRUG + 0.5, 0.3))), T_SHRUG - 0.1, DUR + 0.4)
    # ---- the lid: his hand lifts its front edge 30 degrees, then it falls open on its hinge
    hinge = hive["hinge"]
    ang = lambda t: math.radians(30) * W(t, T_LID + 0.1, T_OPEN - T_LID - 0.1) + math.radians(85) * W(t, T_OPEN, 0.25) \
        - math.radians(8) * hw_kick(t - T_OPEN - 0.25, 0.1)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; hinge.rotation_euler = (-ang(t), 0, 0); hinge.keyframe_insert("rotation_euler", frame=f)
    D = hive["D"]; hz = hive["top"]; hy = hinge.location.y
    def lid_front(t):                              # the lid's front edge by his side, where his fingers are
        a = ang(t); return Vector((hinge.location.x + 0.085, hy - (D + 0.02) * math.cos(a), hz + 0.05 + (D + 0.02) * math.sin(a)))
    # ---- the spoon: keyed in the world, his hand rides its grip
    spoon = s2_spoon("giant spoon")
    sr = spoon["root"]
    def spoon_at(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, sp_side)
        lo = sh + fw * 0.05 + out * 0.06 + Vector((0, 0, -0.14))                 # down by his side at first
        hi = sh + fw * 0.12 + out * 0.09 + Vector((0, 0, -0.13))                    # held out: the bowl beside his shoulder
        push = sh + fw * 0.15 + out * 0.06 + Vector((0, 0, -0.08))                # pushed at us
        g = lo.lerp(hi, W(t, T_OPEN - 0.1, 0.5)).lerp(push, W(t, T_PUSH, 0.35) * (1 - W(t, T_Q + 0.25, 0.4)))
        tilt = math.radians(34) * W(t, T_OPEN - 0.1, 0.5) - math.radians(8) * W(t, T_PUSH, 0.35)
        return g, tilt
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; g, tilt = spoon_at(t)
        yaw = data.arm.rotation_euler.z
        sr.location = g; sr.rotation_euler = (math.radians(-10), tilt, yaw + math.radians(10)); sr.keyframe_insert("location", frame=f); sr.keyframe_insert("rotation_euler", frame=f)
    grip = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), Vector(sr.matrix_world.translation) + sr.matrix_world.to_3x3() @ Vector((0, 0, 0.04)))[2]
    bowl = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), sr.matrix_world @ spoon["center"])[2]
    data.reach(sp_side, grip, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    tl = [T_LID + 0.1 + k * (T_OPEN - T_LID - 0.1) / 3 for k in range(4)]
    FK = [(0.0, (0.04, 0.07, -0.14))] + [(t, hw_rel(data, lid_side, t, lid_front(t) + Vector((0.0, -0.02, 0.02)))) for t in tl]
    le = Vector(FK[-1][1])
    FK += [(T_OPEN + 0.3, tuple(le.lerp(Vector((0.07, 0.1, -0.09)), 0.5) + Vector((0.02, 0.01, 0)))), (T_OPEN + 0.6, (0.07, 0.1, -0.09)), (T_DROP - 0.15, (0.06, 0.09, -0.11)), (T_DROP + 0.35, (0.11, 0.04, -0.02)), (T_FLOP - 0.1, (0.07, 0.08, -0.1)), (T_FLOP + 0.45, (0.1, 0.11, 0.05)),
           (T_PUSH + 0.35, (0.06, 0.12, -0.06)), (T_SHRUG, (0.06, 0.1, -0.1)), (T_SHRUG + 0.3, (0.08, 0.13, -0.02)), (DUR + 0.3, (0.07, 0.12, -0.05))]
    data.reach(lid_side, hw_hand(data, lid_side, FK), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- the bee: out of the slot, up to the bowl, in to its middle; she squeezes, the drop runs down, the wedge
    # fills; she rolls off onto the bottom rim on her back
    bee = worker_bee("the bee", s=2.4)
    br = bee["root"]
    slot = hive["slot"]
    land = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((0, -0.03, spoon["R"] * 0.55)))
    rim = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((0.0, -0.035, -spoon["R"] * 0.98)))
    side_rim = lambda t: bowl(t) + (sr.matrix_world.to_3x3() @ Vector((spoon["R"] * 0.95, -0.035, spoon["R"] * 0.2)))
    def bee_at(t):
        if t < T_OUT: return slot + Vector((0, 0.04, 0))
        if t < T_LAND:
            u = ease((t - T_OUT) / (T_LAND - T_OUT)); a = slot.lerp(land(T_LAND), u)
            return a + Vector((0.0, -0.22 * math.sin(math.pi * u), 0.1 * math.sin(math.pi * u)))     # out in front of him, in an arc
        if t < T_FLOP: return land(t)
        u = ease(min(1.0, (t - T_FLOP) / 0.3)); return land(t).lerp(side_rim(t), u) + Vector((0, 0, 0.03 * math.sin(math.pi * u)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = bee_at(t); br.location = p; br.keyframe_insert("location", frame=f)
        if t < T_LAND:
            q = bee_at(t + 1 / FPS) - p
            e = (-q).to_track_quat('Y', 'Z').to_euler() if q.length > 1e-4 else Euler((0, 0, 0))
        else:
            e = Euler((math.radians(-60), 0, data.arm.rotation_euler.z))               # head up the bowl, belly to it
            if t >= T_FLOP: e = Euler((math.radians(-60) + math.pi * W(t, T_FLOP, 0.3), 0, data.arm.rotation_euler.z))   # on her back
        br.rotation_euler = e; br.keyframe_insert("rotation_euler", frame=f)
        sq = 1.0 - 0.25 * math.sin(math.pi * min(1.0, max(0.0, (t - T_DROP + 0.25) / 0.5)))   # she squeezes it out
        br.scale = (1.0 + 0.15 * (1 - sq), sq, 1.0 + 0.1 * (1 - sq)); br.keyframe_insert("scale", frame=f)
    bee_buzz(bee, T_OUT - 0.1, T_LAND + 0.1, hz=7, amp=55)
    for pv, sg in bee["wings"]:
        pv.rotation_euler = (0, -sg * 0.5, 0); pv.keyframe_insert("rotation_euler", frame=F(T_LAND + 0.2))
        pv.rotation_euler = (0, -sg * 0.1, 0); pv.keyframe_insert("rotation_euler", frame=F(T_FLOP + 0.3))   # drooping
    drop = K.sph("her drop", (0, 0, 0), 0.016, K.mat("drop gold", "#F2A81E", rough=0.15, emit=0.35), seg=16, ring=10)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        u = min(1.0, max(0.0, (t - T_DROP) / 0.35))
        drop.location = (land(t) + (sr.matrix_world.to_3x3() @ Vector((0, 0.01, -0.04)))).lerp(rim(t) + (sr.matrix_world.to_3x3() @ Vector((0, 0.02, 0.05))), ease_in(u)); drop.keyframe_insert("location", frame=f)
        s = 0.0 if t < T_DROP - 0.15 else (1.0 if u < 1 else max(0.0, 1 - (t - T_DROP - 0.35) / 0.15))
        drop.scale = (max(0.01, s),) * 3; drop.keyframe_insert("scale", frame=f)
    fl = spoon["fill"]
    for t, s in ((0.0, 0.01), (T_DROP + 0.3, 0.01), (T_FULL, 1.04), (T_FULL + 0.12, 1.0)):
        fl.scale = (s, 1, s); fl.keyframe_insert("scale", frame=F(t))
    # ---- the queue: eleven more come out of the slot round BEHIND him and hang in a line from the spoon back over the
    # meadow, each waiting her turn
    queue = []
    for k in range(11):
        b = worker_bee(f"queue bee {k}", s=2.0); queue.append(b)
        def spot(t, k=k):
            return bowl(t) + Vector((0.08 + 0.02 * k, 0.06 + 0.07 * k, 0.07 + 0.04 * k + 0.015 * math.sin(1.3 * k)))
        t_go = T_Q + 0.05 * k; dur = 0.5 + 0.03 * k
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            v = W(t, t_go, dur)
            a = slot + Vector((0, 0.1, 0.05)); z = spot(t)
            p = a.lerp(z, v) + Vector((0, 0.35 * math.sin(math.pi * v), 0.25 * math.sin(math.pi * v))) + Vector((0, 0, 0.006 * math.sin(2 * math.pi * 1.6 * t + k)))
            b["root"].location = p; b["root"].keyframe_insert("location", frame=f)
            b["root"].rotation_euler = (0, 0, math.radians(150)); b["root"].keyframe_insert("rotation_euler", frame=f)
            s = 0.01 if t < t_go else 1.0
            b["root"].scale = (s, s, s); b["root"].keyframe_insert("scale", frame=f)
        bee_buzz(b, t_go, DUR + 0.2, hz=6.5 + 0.2 * k, amp=50)
    # ---- face and head
    data.look_at(lid_front(T_OPEN * 0.6), 0.0, max_yaw=40, max_pitch=30, blend=0.0)
    data.look_at(slot, T_OUT - 0.15, max_yaw=40, max_pitch=40, blend=0.15)                        # out she comes
    data.look_at(bowl(T_LAND), T_LAND - 0.25, max_yaw=40, max_pitch=40, blend=0.18)             # into his spoon
    data.look_at(rim(T_FULL), T_FULL - 0.25, max_yaw=40, max_pitch=40, blend=0.15)               # the one wedge
    data.look_at(CAM, T_FLOP + 0.15, max_yaw=45, blend=0.15)                                   # at us, gaping
    data.look_at(bowl(DUR) + Vector((0.4, 0.6, 0.1)), T_Q + 0.2, max_yaw=40, max_pitch=40, blend=0.18)   # the queue
    data.look_at(CAM, T_SHRUG - 0.05, max_yaw=45, blend=0.2)
    data.expression("pleased", 0.0, T_LAND - 0.05)
    data.expression("determined", T_LAND, T_FLOP - 0.05, blend=0.15)
    data.expression("surprised", T_FLOP, T_Q - 0.05, blend=0.1)
    data.expression("worried", T_Q, DUR + 1.0, blend=0.18)
    data.finish()
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=21, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.06, 0.1, 0.0)) * ease(t / DUR), LOOK, Vector((0.1, -0.2, 0.5))))
    return dict(lanes=[], kiosks=[], place="hive_yard", light=light, data=data, rest=1, grips=("giant spoon", "his hive lid"),
                conseq=[("one bee's single drop fills one of the spoon's twelve wedges", lambda: meshes([sr, br]), T_LAND, DUR, {"hero": True}),
                        ("he flips his hive's lid open", lambda: [o for o in bpy.data.objects if o.name.startswith("his hive") and o.type == "MESH"], T_LID, T_OPEN + 0.4),
                        ("eleven more bees queue in the air", lambda: meshes([b["root"] for b in queue]), T_Q + 0.7, DUR)])
