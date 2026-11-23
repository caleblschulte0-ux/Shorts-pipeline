"""BEAT 3, TWICE ROUND THE EARTH: the yard outside his honey house. He rolls a world globe as big as he is along
the path; a bee lifts off his hat and flies a glowing gold trail round the rolling globe once, then a second time; he
stops, snatches his empty one-pound jar off the stump, and the trail swoops into it and it fills gold in his hands (for
one pound of honey the hive's bees fly about 55,000 miles, more than twice round the Earth)."""

S3_R = 0.24                        # the globe's radius: up to his chest
S3_X0, S3_X1 = -0.62, 0.02         # where his feet start and stop along the path
S3_GO = 0.35                       # the globe's centre ahead of him


def s3_globe(name, R):
    """a big world globe ball: blue seas, raised green and sand continents, a thin gold equator. Returns dict(root,
    spin): key root.location to move it, spin.rotation_euler to roll it."""
    root = K.empty(name, (0, 0, 0))
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    sea = hw_noise("globe sea", "#2D6DAE", "#4B8DC9", scale=5, rough=0.3, bump=0.08)
    K.sph(name + " ball", (0, 0, 0), R, sea, seg=64, ring=32, parent=spin)
    rnd = hw_random.Random(7)
    lands = [hw_noise(f"globe land {c_}", c_, K.mute(c_, 0.8), scale=30, rough=0.6, bump=0.4) for c_ in ("#5E9A4A", "#7FAE56", "#C9B07A", "#8FB060")]
    for k in range(34):
        th = rnd.uniform(-1.1, 1.1); ph = rnd.uniform(0, 2 * math.pi)
        if 0.6 < ph < 1.3: continue
        n = Vector((math.cos(th) * math.cos(ph), math.cos(th) * math.sin(ph), math.sin(th)))
        o = K.sph(name + " land", tuple(n * (R * 0.985)), R * rnd.uniform(0.16, 0.3), rnd.choice(lands), scale=(1.0, 0.75, 0.1), seg=20, ring=10, parent=spin)
        o.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
    bpy.ops.mesh.primitive_torus_add(major_radius=R * 1.003, minor_radius=0.004, major_segments=96, minor_segments=6, location=(0, 0, 0))
    eq = bpy.context.active_object; eq.name = name + " equator"; eq.data.materials.append(K.mat("globe gold line", "#E2B649", rough=0.3, metal=0.8))
    eq.parent = spin
    for k in range(2):                         # the two ice caps
        K.sph(name + " ice", (0, 0, (1 if k else -1) * R * 0.97), R * 0.28, K.mat("globe ice", "#F2F5F8", rough=0.5), scale=(1, 1, 0.25), seg=24, ring=10, parent=spin)
    hw_local(root)
    return dict(root=root, spin=spin)


def place_honey_house():
    """THE YARD OUTSIDE HIS HONEY HOUSE: the honey house's weathered plank wall across the back with a sunny window full
    of his jars, its open door, a tin roof edge, his steel extractor and stacked hive boxes by the wall, frames leaning
    to dry, a flagstone path through the grass, the stump he uses as a table, flowers, and the hill behind."""
    rnd = hw_random.Random(33)
    grass = hw_noise("yard grass", "#5E8A32", "#94B850", scale=26, rough=0.95, bump=1.0, detail=8, lo=0.36, hi=0.66)
    K.box("yard ground", (0, 4, -0.01), (30, 30, 0.02), grass, bev=0)
    stone = hw_noise("flagstone", "#A79F90", "#C4BCAC", scale=9, rough=0.85, bump=0.7, detail=6)
    x = -2.2
    while x < 2.4:                                     # the flagstone path he rolls it along
        w = rnd.uniform(0.18, 0.28)
        for yy in (-0.12, 0.12):
            o = K.box("flagstone", (x + w / 2, yy + rnd.uniform(-0.02, 0.02), 0.006), (w - 0.025, 0.21, 0.016), stone, bev=0.006)
            o.rotation_euler = (0, 0, rnd.uniform(-0.08, 0.08))
        x += w
    blade = [K.mat(f"blade {c}", c, rough=0.8) for c in ("#5E8A2E", "#7AA23C", "#8DB24A")]
    petals = [K.mat(f"flower {c}", c, rough=0.6) for c in ("#F2D43A", "#F4F0E6", "#C96BC0", "#E0583A")]
    for k in range(260):
        x, y = rnd.uniform(-2.0, 2.2), rnd.uniform(-1.4, 0.9)
        if -0.3 < y < 0.3: continue
        for b in range(3):
            h = rnd.uniform(0.06, 0.13); a = rnd.uniform(0, 6.28); ln = rnd.uniform(0.1, 0.35)
            o = K.box("yard blade", (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), h / 2), (0.007, 0.002, h), rnd.choice(blade), bev=0)
            o.rotation_euler = (ln * math.sin(a), -ln * math.cos(a), a)
        if k % 3 == 0:
            K.sph("yard flower", (x, y, rnd.uniform(0.08, 0.14)), rnd.uniform(0.012, 0.018), rnd.choice(petals), seg=10, ring=6)
    # the honey house: a long plank wall across the back with a window, a door, a tin roof edge
    WY = 1.05
    plank = hw_noise("weathered planks", "#9C7A52", "#B8966A", scale=3, rough=0.85, bump=0.5, detail=6, stretch=(6, 1, 1))
    for k in range(34):
        xx = -2.6 + k * 0.155
        if 0.55 < xx < 0.95: continue                   # the open door
        K.box("house plank", (xx, WY + rnd.uniform(-0.006, 0.006), 0.85), (0.15, 0.04, 1.7), plank, bev=0.006)
    K.box("door frame top", (0.75, WY - 0.03, 1.32), (0.46, 0.06, 0.06), plank, bev=0.006)
    K.box("door dark", (0.75, WY + 0.1, 0.66), (0.42, 0.02, 1.3), K.mat("inside dark", "#2E241C", rough=0.9), bev=0)
    door = K.box("open door", (0.98, WY - 0.2, 0.65), (0.04, 0.42, 1.28), hw_wood("door wood", "#6E4A2A", "#8A5E36"), bev=0.006)
    tin = K.mat("roof tin", "#8E969C", rough=0.4, metal=0.7)
    for k in range(18):
        K.box("roof tin sheet", (-2.6 + 0.3 * k, WY - 0.1, 1.78), (0.29, 0.5, 0.012), tin, bev=0.002).rotation_euler = (-0.25, 0, 0)
    frame_m = K.mat("window frame", "#EEE8DA", rough=0.4)
    K.box("window frame", (-0.55, WY - 0.03, 1.0), (0.78, 0.04, 0.56), frame_m, bev=0.006)
    K.box("window inside", (-0.55, WY - 0.01, 1.0), (0.7, 0.02, 0.48), K.mat("window inside warm", "#4A3626", rough=0.9), bev=0)
    K.box("window sill", (-0.55, WY - 0.08, 0.71), (0.86, 0.12, 0.03), frame_m, bev=0.004)
    shelf = hw_wood("window shelf", "#7A5A38", "#946E46")
    for z in (0.78, 0.99):
        K.box("window shelf", (-0.55, WY - 0.03, z), (0.7, 0.08, 0.015), shelf, bev=0.002)
        for k in range(6):
            jar(f"window jar {z} {k}", (-0.85 + k * 0.12, WY - 0.04, z + 0.008), r=0.035, h=0.09, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY")
    K.box("window mullion", (-0.55, WY - 0.06, 1.0), (0.02, 0.01, 0.5), frame_m, bev=0)
    # by the wall: the extractor, a stack of hive boxes, frames leaning to dry
    steel = K.mat("extractor steel", "#C9CED4", rough=0.25, metal=0.85)
    K.cyl("extractor drum", (1.45, WY - 0.35, 0.36), 0.22, 0.52, steel, v=48, bev=0.01)
    K.cyl("extractor lid", (1.45, WY - 0.35, 0.64), 0.23, 0.03, steel, v=48, bev=0.006)
    K.box("extractor crank", (1.45, WY - 0.35, 0.72), (0.02, 0.2, 0.02), steel, bev=0.003)
    white = hw_noise("hive paint", "#F4F1E8", "#E2DED2", scale=8, rough=0.7, bump=0.15)
    for k in range(4):
        K.box("stacked hive box", (-1.45, WY - 0.3, 0.07 + 0.135 * k), (0.32, 0.28, 0.125), white, bev=0.004)
    comb = hw_noise("comb wax", "#E8B033", "#F2CC5E", scale=60, rough=0.5, bump=0.6)
    fw_m = hw_wood("frame wood", "#C8A878", "#D8BC8C", scale=6)
    for k in range(5):
        o = K.box("drying frame", (-1.05 + 0.07 * k, WY - 0.12, 0.2), (0.02, 0.3, 0.42), fw_m, bev=0.002); o.rotation_euler = (0.25, 0, 1.57)
        o = K.box("drying comb", (-1.05 + 0.07 * k, WY - 0.13, 0.2), (0.012, 0.26, 0.36), comb, bev=0.001); o.rotation_euler = (0.25, 0, 1.57)
    K.cyl("water butt", (2.1, WY - 0.3, 0.3), 0.2, 0.6, hw_wood("butt wood", "#7A5A38", "#946E46", scale=8), v=32, bev=0.01)
    # the hill behind the roof, with the hives on it
    hill = hw_noise("far hill", "#6F9A40", "#A2BD62", scale=9, rough=0.95, bump=0.5, detail=5)
    K.sph("far hill", (0, 9, -3.6), 6.0, hill, scale=(3.0, 1.0, 0.9))
    leaf = hw_noise("tree leaves", "#4E7E32", "#6E9C40", scale=10, rough=0.85, bump=0.4)
    for k, (xx, yy) in enumerate(((-2.4, 2.4), (2.6, 2.2), (0.2, 3.2), (-1.0, 3.6))):
        K.cyl("tree trunk", (xx, yy, 0.8), 0.08, 1.6, hw_wood("tree bark", "#5A4330", "#6E5440", scale=8), v=12, bev=0.01)
        for jj in range(5):
            K.sph("tree crown", (xx + rnd.uniform(-0.4, 0.4), yy + rnd.uniform(-0.2, 0.2), 1.9 + rnd.uniform(-0.2, 0.3)), rnd.uniform(0.45, 0.6), leaf, seg=20, ring=12)

    def light():
        return village_light(sun_elev=40, sun_az=-30, sun=4.2, sky=0.33)
    return light


def shot3():
    """TWICE ROUND THE EARTH. The lens three-quarter in front of him at his chest height; he leans into a world globe as
    big as he is and rolls it along his path; a bee lifts off his hat and flies a glowing gold trail round the rolling
    globe, once, twice; he stops it, snatches his empty pound jar off the stump and holds it up, the trail swoops into it
    and it fills gold in his hands."""
    T_OFF = 0.08 * DUR                          # the bee lifts off his hat
    T_W0 = 0.25                                 # he starts rolling
    T_L2 = 0.55 * DUR                           # twice round
    T_W1 = T_L2 - 0.1                           # he stops it
    T_GRAB = T_L2 + 0.2                         # the jar off the stump
    T_IN = 0.75 * DUR                           # the trail swoops in
    T_FULL = 0.9 * DUR
    light = place_honey_house()
    G = s3_globe("big globe", S3_R)
    gr, gs = G["root"], G["spin"]
    data = load_data()
    YAW = math.radians(90)                      # facing +X, along the path
    data.place(S3_X0, 0.0, math.degrees(YAW))
    hat = bee_hat(data)
    W = hw_win
    walk = lambda t: S3_X0 + (S3_X1 - S3_X0) * (ease((t - T_W0) / (T_W1 - T_W0)) if T_W0 < t < T_W1 else (0.0 if t <= T_W0 else 1.0))
    data.walk_to(Vector((S3_X1, 0.0, 0.0)), T_W0, T_W1, pushing=True)
    # the globe rolls ahead of his hands: no slip, a little wobble
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; x = walk(t) + S3_GO
        gr.location = (x, 0.0, S3_R + 0.012); gr.keyframe_insert("location", frame=f)
        gs.rotation_euler = (0.03 * math.sin(2 * math.pi * t / 1.3), (x - S3_X0 - S3_GO) / S3_R, 0.0); gs.keyframe_insert("rotation_euler", frame=f)
    gc = lambda t: Vector((walk(t) + S3_GO, 0.0, S3_R + 0.012))
    # his body over it: leaning in to push, then up and round to the stump, the jar held up, a hop when it is full
    hw_layer(data, "spine", lambda t: (8 * W(t, 0.0, 0.3) * (1 - W(t, T_W1, 0.3)) + 4 * math.sin(2 * math.pi * (t - T_W0) / 0.55) * W(t, T_W0, 0.2) * (1 - W(t, T_W1, 0.2))
                                      - 8 * W(t, T_IN - 0.4, 0.3) * (1 - W(t, T_FULL, 0.3)), 0,
                                      0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).y)       # [toward -Y: the lens, toward +Y]
    near, far = sides                                                   # the jar in his near hand, the far one rolls it
    end_yaw = YAW - math.radians(30)                                  # turns to us with the jar
    sc.frame_set(F(T_W1)); bpy.context.view_layer.update()
    for f in range(F(T_W1), NF + 1):
        t = (f - 1) / FPS
        data._kobj(t, loc=(S3_X1 - 0.03 * W(t, T_IN - 0.4, 0.4) * (1 - W(t, T_FULL, 0.3)), 0.0, 0.035 * hw_kick(t - T_FULL, 0.15) + 0.04 * hw_kick(t - T_IN - 0.3, 0.12)),
                   rot=YAW + (end_yaw - YAW) * W(t, T_W1, 0.6) + math.radians(10) * W(t, T_FULL - 0.1, 0.3) - math.radians(14) * W(t, T_IN, 0.35) * (1 - W(t, T_IN + 0.4, 0.35)))
    # the jar: his empty pound jar in his near hand all along; held up for the trail
    pj = jar("pound jar", (0, 0, 0), r=0.065, h=0.15, fill=0.88, honey_col="#F0B030", label="1 lb", glow=1.5)
    jr = pj["root"]
    def jar_at(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, near)
        lo = sh + fw * 0.07 + out * 0.12 + Vector((0, 0, -0.2))
        hi = sh + fw * 0.11 + out * 0.13 + Vector((0, 0, -0.12))
        return lo.lerp(hi, W(t, T_GRAB, 0.6)) + Vector((0.0, -0.04, 0.05)) * W(t, T_IN - 0.15, 0.7)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = jar_at(t); p.z += 0.012 * hw_kick(t - T_IN, 0.1) + 0.006 * math.sin(2 * math.pi * (t - T_W0) / 0.55) * W(t, T_W0, 0.2) * (1 - W(t, T_W1, 0.2))
        jr.location = p; jr.keyframe_insert("location", frame=f)
        jr.rotation_euler = (0, 0, data.arm.rotation_euler.z - math.radians(80)); jr.keyframe_insert("rotation_euler", frame=f)
    hon = pj["honey"]
    for t, s_ in ((0.0, 0.02), (T_IN + 0.05, 0.02), (T_FULL, 1.0)):
        hon.scale = (1, 1, s_); hon.keyframe_insert("scale", frame=F(t))
        hon.location.z = pj["hz"] * s_ / 2 + 0.002; hon.keyframe_insert("location", frame=F(t))   # it fills from the bottom
    # ---- hands: both on the globe's back while he rolls it; the near one to the jar; the far one up when it fills
    on_g = lambda t: gc(t) + Vector((-S3_R * 0.78, 0.06, 0.15))
    gripj = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), jr.matrix_world.translation + Vector((0, 0, 0.04)))[2]
    data.reach(near, gripj, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    data.reach(far, on_g, 0.0, T_W1 + 0.1, lead=0.05, back=None, elbow_out=0.35)
    fk = [(T_W1 + 0.1, hw_rel(data, far, T_W1 + 0.1, on_g(T_W1 + 0.1))), (T_W1 + 0.6, (0.07, 0.09, -0.1)), (T_IN + 0.15, (0.06, 0.13, 0.02)),
          (T_FULL - 0.15, (0.08, 0.1, -0.07)), (T_FULL + 0.35, (0.08, 0.12, 0.08)), (DUR + 0.3, (0.08, 0.12, 0.06))]
    data.reach(far, hw_hand(data, far, fk), T_W1 + 0.1, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    # ---- the bee and her trail: off his hat, twice round the rolling globe, then into the jar
    bee = worker_bee("trail bee", s=1.8)
    br = bee["root"]
    orb = S3_R + 0.07
    def orbit(u, t):                            # u in loops; the loop faces the lens a little so it reads round
        a = 2 * math.pi * u + math.radians(110)
        e1 = Vector((0.57, 0.82, 0.0))         # a loop standing at 55 degrees to the path: it faces the lens, clear of him
        r = orb + 0.03 * min(u, 2.0) / 2.0     # the second ring a little wider, so two rings read
        return gc(t) + e1 * (r * math.cos(a)) + Vector((0, 0, r * math.sin(a)))
    def bee_at(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        wo = hat["worn"]; bb = [wo.matrix_world @ Vector(c_) for c_ in wo.bound_box]
        top = sum(bb, Vector()) / 8; top.z = max(b.z for b in bb) + 0.03
        if t < T_OFF: return top
        if t < T_OFF + 0.4:
            u = ease((t - T_OFF) / 0.4); return top.lerp(orbit(0.0, t), u) + Vector((0, 0, 0.08 * math.sin(math.pi * u)))
        if t < T_L2: return orbit(2.0 * (t - T_OFF - 0.4) / (T_L2 - T_OFF - 0.4), t)
        jt = jr.matrix_world.translation + Vector((0, 0, 0.12))
        if t < T_IN:
            u = ease((t - T_L2) / (T_IN - T_L2)); return orbit(2.0, t).lerp(jt, u) + Vector((0, -0.12 * math.sin(math.pi * u), 0.05 * math.sin(math.pi * u)))
        u = min(1.0, (t - T_IN) / 0.3); return jt.lerp(jt + Vector((0.02, -0.08, -0.02)), ease(u))
    pts = []
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = bee_at(t); br.location = p; br.keyframe_insert("location", frame=f); pts.append(p.copy())
    for f in range(1, NF + 1):
        q = pts[min(NF - 1, f)] - pts[f - 1]
        if q.length > 1e-4:
            br.rotation_euler = (-q).to_track_quat('Y', 'Z').to_euler(); br.keyframe_insert("rotation_euler", frame=f)
    bee_buzz(bee, 0.0, DUR + 0.3, hz=7, amp=55)
    # the trail rides the globe: drawn in its (unspun) frame, so the two rings she flew stay wrapped round it as it
    # rolls and the picture reads "twice round the Earth"; the globe has stopped before she leaves it for the jar
    tf0, tf1 = F(T_OFF + 0.05), F(T_IN)
    cu = bpy.data.curves.new("gold trail", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.005; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(tf1 - tf0)
    for i, f in enumerate(range(tf0, tf1 + 1)):
        p = pts[f - 1] - gc((f - 1) / FPS); sp.points[i].co = (p.x, p.y, p.z, 1)
    trail = bpy.data.objects.new("gold trail", cu); bpy.context.collection.objects.link(trail); trail.parent = gr
    cu.materials.append(K.mat("trail gold", "#FFC23A", rough=0.3, emit=4.0))
    for f in range(1, NF + 1):
        cu.bevel_factor_end = min(1.0, max(0.0, (f - tf0) / max(1, tf1 - tf0))); cu.keyframe_insert("bevel_factor_end", frame=f)
        cu.bevel_factor_start = min(0.999, max(0.0, (f - F(T_FULL)) / 10.0)); cu.keyframe_insert("bevel_factor_start", frame=f)
    # ---- face and head
    LENS = Vector((0.45, -1.4, 0.62))
    data.look_at(gc(0.0) + Vector((0, 0, 0.1)), 0.0, max_yaw=40, max_pitch=40, blend=0.0)
    data.look_at(gc(T_OFF) + Vector((-0.2, 0, 0.6)), T_OFF - 0.05, max_yaw=40, max_pitch=45, blend=0.12)   # up: she lifts off
    data.look_at(LENS, T_OFF + 0.7, max_yaw=45, blend=0.2)                                             # at us, pushing
    data.look_at(orbit(1.5, T_L2 - 0.6) + Vector((0, 0, 0.25)), T_L2 - 0.7, max_yaw=40, max_pitch=40, blend=0.2)
    data.look_at(jar_at(T_IN) + Vector((0, 0, 0.1)), T_IN - 0.35, max_yaw=40, max_pitch=40, blend=0.18)
    data.look_at(LENS, T_FULL + 0.05, max_yaw=45, blend=0.18)
    data.expression("determined", 0.0, T_OFF - 0.05)
    data.expression("surprised", T_OFF, T_OFF + 0.9, blend=0.1)
    data.expression("pleased", T_OFF + 1.0, T_IN - 0.1, blend=0.18)
    data.expression("happy", T_FULL - 0.1, DUR + 1.0, blend=0.18)
    data.finish()
    cam = K.camera(tuple(LENS), (-0.05, 0.05, 0.42), lens=28.5, fstop=7.0)
    push = lambda t: W(t, T_L2, T_FULL - T_L2)
    lx = lambda t: walk(t) + 0.12
    camera_path(cam, lambda t: (Vector((lx(t) + 0.85, -1.2, 0.56)) + (jar_at(T_FULL) - LENS).normalized() * 0.4 * push(t),
                                Vector((lx(t), 0.05, 0.42)).lerp(jar_at(T_FULL) + Vector((0, 0, 0.05)), 0.5 * push(t)), gc(t).lerp(jar_at(T_FULL), 0.6 * push(t))))
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("pound jar", "big globe"),
                conseq=[("the gold trail goes twice round the rolling globe", lambda: meshes([gr, trail]), T_OFF + 0.5, T_L2 + 0.3, {"hero": True}),
                        ("he rolls the globe along the path", lambda: meshes([gr]), T_W0, T_W1, {"moves": True}),
                        ("the trail swoops into his pound jar and it fills gold", lambda: meshes([jr, br]), T_IN - 0.2, DUR)])
