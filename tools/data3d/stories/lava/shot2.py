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
