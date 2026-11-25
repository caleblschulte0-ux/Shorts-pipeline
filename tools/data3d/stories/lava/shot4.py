"""BEAT 4: "But then the ground split open inside the wall, and lava poured straight into the streets."

An empty street of the town INSIDE the wall, mid-afternoon: town houses down both sides, the earth wall a dark line
across the end of the street with smoke over it. The lens backs down the street ahead of him as he pushes a wheelbarrow
of sandbags toward us. The road jolts and a crack tears across the asphalt right in front of his wheel, kerb to kerb; it
yawns open, orange inside, steam shooting out; he lets go of the barrow and leaps back; the lava wells up out of the
crack and pours over the road, the barrow tipping in and catching fire; the lava runs down the street toward the
red-roofed corner house and he hops back from it, arms up."""

S4_YC = 0.0                     # the crack's line (y), across the street
S4_HALF = 8.0                   # the asphalt and pavement, out to the house fronts (x)
S4_KERB = 1.15                  # the kerbs (x): a narrow town street, so a long lens down it holds both rows of houses
S4_FRONT = 1.65                 # the house fronts (x)


def s4_zig(x):
    """the crack's zig-zag line across the street: y at x"""
    return S4_YC + 0.12 * math.sin(3.1 * x + 0.4) + 0.07 * math.sin(7.3 * x + 1.1)


def s4_ground_z(x, y):
    z = -0.6 if abs(x) < S4_HALF + 0.2 and abs(y - S4_YC) < 1.6 else -0.06   # under the slabs; well under the crack's trench (the gap showed black ground)
    if abs(y) > 5.0 or abs(x) > S4_HALF + 1.0: z += 0.06 + 0.1 * lw_fbm(x * 0.4, y * 0.4, 23)
    return z


def s4_slab(name, near, m):
    """one side of the cracked street: the asphalt from the crack to the end of the street (near: toward the lens),
    its crack edge the zig-zag with a 0.25 m face down into the ground. Built as strips of quads, every face up or out
    (one concave n-gon rendered black). Returns the object, origin on the crack line."""
    NS = 160
    xs = [-S4_HALF + 2 * S4_HALF * k / NS for k in range(NS + 1)]
    far_y = -S4_FRONT if near else S4_FRONT
    bm = LW_bmesh.new()
    te = [bm.verts.new((x, s4_zig(x) - S4_YC, 0.0)) for x in xs]
    tf = [bm.verts.new((x, far_y - S4_YC, 0.0)) for x in xs]
    be = [bm.verts.new((x, s4_zig(x) - S4_YC, -0.25)) for x in xs]
    for i in range(NS):
        q = (te[i], te[i + 1], tf[i + 1], tf[i]) if not near else (tf[i], tf[i + 1], te[i + 1], te[i])
        bm.faces.new(q)
        w = (te[i], be[i], be[i + 1], te[i + 1]) if not near else (te[i + 1], be[i + 1], be[i], te[i])
        bm.faces.new(w)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        if abs(p.normal.z) > 0.5 and p.normal.z < 0: p.flip()
    me.materials.append(m)
    o = lw_link(bpy.data.objects.new(name, me)); o.location = (0, S4_YC, 0.0)
    return o


def s4_barrow():
    """a builder's wheelbarrow of sandbags facing -Y: a steel tray, one wheel at its nose, two long handles back toward
    him, two legs. Built with the axle at its origin and the handles' ends at (±0.1, 0.72, 0.27): pitched for pushing."""
    root = K.empty("wheelbarrow", (0, 0, 0))
    tray = lw_metal("barrow galvanised", "#8E9398", rough=0.42); steel = lw_paint("barrow frame red", "#9E2A1E", rough=0.45)      # a galvanised tray on a red tube frame: a builder's barrow, not a toy
    K.box("wheelbarrow tray", (0, 0.3, 0.2), (0.4, 0.5, 0.05), tray, bev=0.02, parent=root)
    for sx in (-1, 1):
        K.box("wheelbarrow tray side", (sx * 0.2, 0.3, 0.28), (0.03, 0.5, 0.16), tray, bev=0.01, parent=root)
        K.cyl("wheelbarrow handle", (sx * 0.1, 0.38, 0.14), 0.015, 0.72, steel, rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
        K.cyl("wheelbarrow leg", (sx * 0.12, 0.5, 0.07), 0.012, 0.16, steel, v=10, parent=root)
    K.box("wheelbarrow tray front", (0, 0.06, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    K.box("wheelbarrow tray back", (0, 0.54, 0.28), (0.4, 0.03, 0.16), tray, bev=0.01, parent=root)
    rim = lw_metal("barrow rim", "#B4B8BC", rough=0.3)                 # the rolled rim round the tray's lip
    for sx in (-1, 1):
        K.cyl("wheelbarrow tray rim", (sx * 0.205, 0.3, 0.365), 0.012, 0.52, rim, rot=(math.pi / 2, 0, 0), v=10, parent=root)
    for y in (0.055, 0.545):
        K.cyl("wheelbarrow tray rim", (0, y, 0.365), 0.012, 0.43, rim, rot=(0, math.pi / 2, 0), v=10, parent=root)
    for sx in (-1, 1):
        K.cyl("wheelbarrow handle grip", (sx * 0.1, 0.7, 0.255), 0.02, 0.1, lw_rubber("grip black", "#151515", rough=0.7), rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
    K.cyl("wheelbarrow wheel", (0, 0, 0), 0.1, 0.06, lw_rubber("barrow tyre", "#141414", rough=0.8), rot=(0, math.pi / 2, 0), v=24, parent=root)
    K.cyl("wheelbarrow hub", (0, 0, 0), 0.03, 0.07, steel, rot=(0, math.pi / 2, 0), v=12, parent=root)
    sand = lw_canvas("sandbag hessian", "#9A8456")   # a coarse weave
    tie = lw_canvas("sandbag tie", "#4A3A22")
    for k, (x, y, rz) in enumerate(((-0.085, 0.22, 0.1), (0.085, 0.24, -0.08), (0.0, 0.4, 1.45), (-0.02, 0.33, 0.05))):
        sb = K.box(f"wheelbarrow sandbag {k}", (x, y, 0.255 + 0.05 * (k > 2)), (0.15, 0.26, 0.075), sand, bev=0.035, parent=root)
        sb.rotation_euler = (0, 0, rz)
        K.box(f"wheelbarrow sandbag tie {k}", (x + 0.12 * math.sin(-rz) * 0, y + 0.13 * math.cos(rz), 0.255 + 0.05 * (k > 2)), (0.05, 0.03, 0.05), tie, bev=0.01, parent=root)
    flames = []                                          # its fire is a gas lit where it lands (shot4), not flame-shaped balls
    lw_local(root)
    return root, flames


def place_town_crack():
    """AN EMPTY STREET INSIDE THE WALL: asphalt and pavements between two rows of town houses, the red-roofed house on
    the corner, the earth wall across the end of the street with smoke over it, the lava field beyond."""
    rnd = lw_random.Random(41)
    lw_grid("town ground", -30, 60, -30, 30, 100, 90, s4_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))
    asph = ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt")          # REAL asphalt (Poly Haven)
    near = s4_slab("street near", True, asph)
    far = s4_slab("street far", False, asph)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sy, slab in ((-1, near), (1, far)):
        o = K.box("kerb", (0, sy * S4_KERB, 0.04), (2 * S4_HALF, 0.12, 0.08), kerb, bev=0.01)
        o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    trench = lava_mat("crack lava", heat=1.6, scale=4.0, fresh=0.7)
    K.box("crack trench", (0, S4_YC, -0.32), (2 * S4_HALF + 0.4, 1.6, 0.1), trench, bev=0)
    for sy in (-1, 1):
        K.box("crack wall rock", (0, S4_YC + sy * 0.85, -0.23), (2 * S4_HALF + 0.4, 0.1, 0.4), lw_noise("crack rock", "#2A2522", "#4A3E36", scale=10, rough=0.95, bump=1.0), bev=0)
    houses = []
    for sy in (-1, 1):                                    # the street runs along X: a row of town houses down each side, their doors to the road
        x = -5.0 + (0.6 if sy > 0 else 0.0); k = 0
        while x < 6.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            roof = ROOFS[(k * 3 + (sy > 0) + 1) % len(ROOFS)]
            hs = town_house(f"town house {sy}_{k}", (x + w / 2, sy * (S4_FRONT + d / 2), 0), yaw=0.0 if sy > 0 else math.pi, w=w, d=d,
                            roof=roof, wall=WALLS[(k + (sy > 0) * 2) % len(WALLS)], base=0.3, storeys=1, seed=k + 20)
            houses.append(hs); x += w + rnd.uniform(0.4, 0.8); k += 1
    wall = earth_wall("earth wall", [(12.5 + 0.1 * y, y) for y in range(-30, 32, 2)], h=3.8, crest=1.4, base=7.0, seed=12)
    lava_rock("wall foot rubble", 160, (7.5, 10.5, -6.0, 6.0), lambda x, y: 0.0, seed=71, r=(0.08, 0.3), moss=0.0, avoid=lambda x, y: abs(y) < 1.2 and x < 8.6)       # STRAIGHT, flat-topped and steep, right across the end of the street, over the roofs (board B2: "a natural hillside")   # right across the end of the street, over the roofs: this street is INSIDE it
    for k, y in enumerate((1.5,)):            # the eruption's smoke over the wall: rolling columns of gas, leaning off on the wind
        lw_steam(f"wall smoke {k}", (21.0 + 2 * k, y, 2.0), w=4.5, h=16.0, seed=3.3 * k, col=(0.42, 0.41, 0.42), dens=2.5, lean=(0.2, 0.5), rise=1.2, t_end=DUR + 1.0)
    # the street under the eruption's fall-out: grit and lava cinders blown over the asphalt, a drain grating at each kerb
    bits = lava_rock("street cinders", 260, (-3.0, 13.0, -S4_KERB + 0.1, S4_KERB - 0.1), lambda x, y: 0.0, seed=44, r=(0.012, 0.04), moss=0.0,
                     avoid=lambda x, y: abs(y - s4_zig(x)) < 0.5 or (abs(x) < 0.8 and y > 0))
    grate = lw_metal("drain grating", "#2A2B2D", rough=0.6)
    for k in range(5):
        for sy in (-1, 1):
            bits.append(K.box("drain grating", (-1.0 + 3.0 * k + (1.5 if sy > 0 else 0.0), sy * (S4_KERB - 0.2), 0.012), (0.4, 0.22, 0.008), grate, bev=0.0))
    bpy.context.view_layer.update()
    for o in bits:                                       # they ride their half of the street when it jolts
        slab = near if o.location.y < s4_zig(o.location.x) else far
        o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    for k in range(2):                                   # REAL street lamps (Poly Haven) along the left kerb
        ph_model("street_lamp_01", (3.0 + 6 * k, S4_KERB + 0.25, 0.0), rot=(0, 0, math.pi), scale=0.5, name=f"street lamp {k}")

    def light():
        k = iceland_light(sun_elev=30, sun_az=-30, sun=3.2, sky=0.45, haze=1.2)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))      # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, near=near, far=far, houses=houses)


def shot4():
    """THE CRACK. A lens low in the street looking up it: the driver comes down the middle of the empty street toward us
    with a sandbag in his arms, houses down both sides, the earth wall across the end of the street over their roofs.
    The road jolts and a zig-zag crack tears across the asphalt right in front of his boots; he drops the bag and leaps
    back; the street pulls apart, the gap glowing orange, steam shooting up; lava wells up out of it and pours down the
    street at us; he hops back again, arms up against the heat."""
    T_JOLT = 0.2 * DUR; T_TEAR = T_JOLT + 0.05; T_TORN = T_TEAR + 0.35
    T_LET = 0.255 * DUR; T_OPEN0 = 0.355 * DUR; T_OPEN1 = 0.52 * DUR
    T_POUR = 0.5 * DUR; T_TIP = T_OPEN0 + 0.1; T_RUN = 0.8 * DUR
    W = lw_win
    P = place_town_crack()
    light = P["light"]; near, far = P["near"], P["far"]
    data = load_data()
    YAW = math.radians(-50)                                  # three-quarter to the lens, which is down the street at his front left
    X0 = 0.0; Y0 = s4_zig(X0) + 0.2                        # on the far side of the crack's line, his boots at its lip
    data.place(X0, Y0, math.degrees(YAW))
    kit = hard_hat(data)
    T_W = T_JOLT - 0.06                                     # he WALKS in (real steps), the last half metre down the street to the spot
    fw0 = data.forward(); fw0.z = 0; fw0.normalize()
    data.place(X0 - fw0.x * 0.32, Y0 - fw0.y * 0.32, math.degrees(YAW))
    data.walk_to((X0, Y0), 0.0, T_W)
    def hop(t, t0, d, h, T=0.4):
        u = min(1.0, max(0.0, (t - t0) / T)); return d * ease(u), h * math.sin(math.pi * u)
    for f in range(F(T_W) + 1, NF + 1):
        t = (f - 1) / FPS
        y1, z1 = hop(t, T_LET, 0.1, 0.11, 0.4); y2, z2 = hop(t, T_POUR + 0.1, 0.02, 0.06); y3, z3 = 0.0, 0.0; y4, z4 = hop(t, 0.74 * DUR, 0.03, 0.09, 0.42)      # (both feet are on the road at every board still but the leap: a hop caught mid-air read as floating); y2 += y4; z2 += z4
        jolt = -0.03 * lw_kick(t - T_JOLT, 0.1) - 0.04 * lw_kick(t - T_POUR, 0.15)
        walk = 0.0; step = 0.0
        back = -0.05 * W(t, T_TEAR, 0.3)                                               # a start back off the tear
        data._kobj(t, loc=(X0 + 0.05 * W(t, T_LET, 0.6) + 0.07 * math.sin(2 * math.pi * (t - T_POUR) / 1.3) * W(t, T_POUR, 0.3) + 0.06 * walk, Y0 + y1 + y2 + y3 - back + 0.3 * walk, 0.03 + z1 + z2 + z3 + jolt + step),
                   rot=YAW - math.radians(8) * W(t, T_LET, 0.4) + math.radians(14) * W(t, T_RUN + 0.1, 0.5) + math.radians(14) * math.sin(2 * math.pi * (t - T_POUR) / 1.3) * W(t, T_POUR, 0.4))
    lw_layer(data, "spine", lambda t: (16 * W(t, T_TEAR + 0.1, 0.35) * (1 - W(t, T_LET - 0.45, 0.3)) - 16 * lw_kick(t - T_JOLT, 0.18)
                                       - 26 * W(t, T_LET + 0.05, 0.25) * (1 - W(t, T_LET + 0.7, 0.3)) - 14 * W(t, T_RUN, 0.3), 0, 0), 0, DUR + 0.4)
    # ---- face and head: one feeling per moment, held (BEFORE the hands: a face moves his chest and shoulders)
    CAM0 = Vector((X0 - 1.4, Y0 - 0.45, 0.8)); LOOK0 = CAM0 + Vector((1.0, 0.02, -0.25))      # the street's far end, and the wall across it, stand clear at the right of his hat      # a little above him, tipped down at the road: the crack lies across the frame's lower third, the wall's crest and the sky across its top
    data.look_at(CAM0, 0.0, max_yaw=40, max_pitch=30, blend=0.0)                                        # coming down the street to us
    data.look_at(Vector((X0 - 0.35, s4_zig(X0 - 0.35), 0.0)), T_JOLT + 0.05, max_yaw=50, max_pitch=25, blend=0.2)   # down at the crack at his boots
    data.look_at(CAM0, T_LET + 0.5, max_yaw=55, max_pitch=40, blend=0.3)                                # up at us: did you see that
    data.look_at(Vector((X0 - 0.3, S4_YC - 0.5, 0.0)), T_POUR + 0.1, max_yaw=50, max_pitch=25, blend=0.3)  # at the lava welling up
    data.look_at(CAM0, T_RUN + 0.3, max_yaw=55, blend=0.3)
    data.expression("determined", 0.0, T_JOLT, blend=0.2)
    data.expression("alarmed", T_JOLT + 0.02, DUR + 1.0, blend=0.12)
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)       # (no prop: the spoken line names none, and a bag he drops has to be accounted for in every still after)
    # one arm up across his face against the heat, the other back for balance: never both out at his sides
    near_sd = min(sides, key=lambda s_: (acts._shoulder(data, s_) - CAM0).length)
    # FK poses from here (IK through these folded the elbow over, 60-180 deg/frame): the far arm thrown UP, palm out
    # at the heat, beside his head from the lens, never over his face; the near arm low and forward, pushing it off
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    UP = lambda sg: ((-58, 0, -sg * 12), (-48, 0, -sg * 22), (-10, sg * -12, -sg * 15))
    SHIELD = lambda sg: ((-50, 0, -sg * 30), (-55, 0, -sg * 45), (-10, sg * -12, -sg * 15))    # the forearm up across his face, palm out at the heat
    LOW = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = (LOW, WHOA, LOW, UP, UP, WHOA, UP, WHOA, LOW, WHOA, WHOA) if sd != near_sd else (WHOA, LOW, WHOA, WHOA, UP, WHOA, LOW, WHOA, SHIELD, SHIELD, SHIELD)   # both fly up at the leap; at the end the arm nearest the flow is up across his face against the heat   # his arms swing as he walks, fly up at the tear
        for tk, pose in zip((0.0, 0.38, 0.74, T_TORN - 0.1, T_LET + 0.15, T_LET + 0.55, T_LET + 0.95, T_LET + 1.3, T_LET + 1.7, T_LET + 2.1, DUR + 0.5), seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    # ---- the crack: a hairline tears across from kerb to kerb, then the street pulls apart and the lava shows in the gap
    gm = lava_mat("crack glow", heat=2.4, scale=6.0)
    rim_m = lw_emit("crack glow hot", "#FF4A08", 2.2)       # the light from inside, standing in the gap: a flat crusted skin read as a dark line from a low lens
    NR = 240
    xs = [-S4_HALF + 2 * S4_HALF * k / NR for k in range(NR + 1)]
    bm = LW_bmesh.new()
    far_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC + 0.02, 0.05)) for x in xs]
    near_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.08, 0.05)) for x in xs]
    for i in range(NR): bm.faces.new((near_e[i], near_e[i + 1], far_e[i + 1], far_e[i]))
    me = bpy.data.meshes.new("crack glow"); bm.to_mesh(me); bm.free(); me.materials.append(gm)
    tear = lw_link(bpy.data.objects.new("crack glow", me)); tear.location = (-S4_HALF, S4_YC, 0.0)
    bm = LW_bmesh.new()
    rib_lo = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.03, -0.02)) for x in xs]
    rib_hi = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.03, 0.06)) for x in xs]
    for i in range(NR): bm.faces.new((rib_lo[i], rib_lo[i + 1], rib_hi[i + 1], rib_hi[i]))
    me = bpy.data.meshes.new("crack glow rim"); bm.to_mesh(me); bm.free(); me.materials.append(rim_m)
    rim = lw_link(bpy.data.objects.new("crack glow rim", me)); rim.location = (-S4_HALF, S4_YC, 0.0)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR)
        rim.scale = (max(0.002, u), 1, 1); rim.hide_render = u < 0.01 or t > T_OPEN0 + 0.25
        rim.keyframe_insert("scale", frame=f); rim.keyframe_insert("hide_render", frame=f)
    tear.shape_key_add(name="Basis")
    op = tear.shape_key_add(name="open")
    for i in range(NR + 1): op.data[NR + 1 + i].co.y = s4_zig(xs[i]) - S4_YC - 0.36
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR); o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0)
        tear.scale = (max(0.002, u), 1, 1); tear.hide_render = u < 0.01; op.value = o
        tear.keyframe_insert("scale", frame=f); tear.keyframe_insert("hide_render", frame=f); op.keyframe_insert("value", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0); sh = 0.015 * math.sin(2 * math.pi * 11 * t) * lw_kick(t - T_JOLT, 0.25)
        near.location = (sh, S4_YC - 0.28 * o, 0.01 * o + 0.04 * lw_kick(t - T_JOLT, 0.12)); near.rotation_euler = (math.radians(-1.5) * o, 0, 0)
        far.location = (-sh, S4_YC, 0.0)
        for o_ in (near, far): o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    # the asphalt BREAKS along both lips: slabs of it heave up and tilt, first a little as the crack tears, then right up
    # as the street pulls apart, raw dark edges catching the glow
    lip = bpy.data.materials["street asphalt"]          # the road's own skin: until it breaks there is no line across the street
    rk = lw_random.Random(7)
    lips = []
    for slab, sg in ((near, -1), (far, 1)):
        x = -0.1                                           # (none under the lens: a shard a hand from the glass is a boulder)
        while x < S4_HALF - 0.1:
            w = rk.uniform(0.18, 0.34); xc = x + w / 2
            ch = lw_block("crack lip chunk", (xc, s4_zig(xc) - S4_YC + sg * rk.uniform(0.05, 0.11), -0.01), 1.0, lip, rk, squash=1.0); ch.scale = (w * rk.uniform(0.5, 0.7), rk.uniform(0.07, 0.14), rk.uniform(0.03, 0.05))   # torn SHARDS of asphalt, every one its own shape (board B2: "paver tiles")
            ch.parent = slab; ch.matrix_parent_inverse = slab.matrix_world.inverted(); lips.append(ch)
            lift = rk.uniform(0.25, 0.55); yaw = rk.uniform(-0.25, 0.25); t0 = T_OPEN0 + 0.1 * abs(xc) / S4_HALF
            for f in range(1, NF + 1):
                t = (f - 1) / FPS; o = 0.3 * W(t, T_TEAR + 0.3 * abs(xc + S4_HALF) / (2 * S4_HALF), 0.25) + 0.7 * W(t, t0, 0.45)
                if sg > 0 and abs(xc - X0) < 0.3: o *= 0.25                                # (the ones his boots stand at stay near flat)
                ch.rotation_euler = (-sg * lift * o, 0.15 * yaw * o, yaw * o); ch.location.z = -0.04 + 0.08 * o   # flush with the road until it breaks (his boots walk over it)
                ch.keyframe_insert("rotation_euler", frame=f); ch.keyframe_insert("location", frame=f)
            x += w
    lava_flow_key(gm, 0.0, DUR + 0.5, 0.2)
    trench = bpy.data.materials["crack lava"]
    lava_flow_key(trench, 0.0, DUR + 0.5, 0.25)
    # ---- steam shooting up out of the crack as it opens: two thin jets, one at each edge of the frame, off the lens's line to him
    steam = []
    for k, (x, lx_) in enumerate(()):                       # (none: a jet's box stood between the lens and his face, and a thin jet does not render)
        t0 = T_OPEN0 + 0.08 * k
        steam.append(lw_fire_column(f"crack steam {k}", (x, s4_zig(x) - 0.35, -0.2), w=0.3, h_fire=0.2, h_smoke=2.4, lean=(lx_, 0.0), t_end=DUR + 1.0,
                                    seed=2.1 * k, fire=0.0, smoke_d=20.0, smoke=(0.9, 0.91, 0.93), rise=2.6, flame_d=0.0, spread=0.1,
                                    keys=[(t0, 0.0), (t0 + 0.45, 1.0), (DUR, 0.6)], grow=True))
    # ---- the lava: it wells up in the crack and pours out over the road, down the street at the lens
    lm = lava_mat("street lava", heat=2.4, scale=9.0, fresh=0.35)
    for n_ in lm.node_tree.nodes:                             # BLACK crust plates over bright seams (board: "a tan, rubbery sheet"): no broad dull-red patches in daylight
        if n_.type == 'MAP_RANGE' and abs(n_.inputs["To Max"].default_value - 0.35) < 1e-4 and abs(n_.inputs["From Min"].default_value - 0.5) < 1e-4:
            n_.inputs["To Max"].default_value = 0.06
    out = []
    for k in range(40):
        a = 2 * math.pi * k / 40
        out.append((1.0 * math.cos(a) + 0.03 * math.sin(5 * a), 1.0 * math.sin(a) + 0.1 * math.cos(9 * a) + 0.06 * math.sin(14 * a)))
    flow = lava("street lava", out, z=0.0, thick=0.22, m=lm, seed=6, lumpy=0.1, n=40)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_POUR, 0.94 * DUR - T_POUR); w_ = W(t, T_POUR - 0.25, 0.4)
        L_ = 0.1 + 0.6 * u                                                     # a mound welling out of the gap, spreading down the middle of the road and across to the doors
        flow.location = (X0 + 2.6, S4_YC - 0.02 - 0.72 * L_, -0.2 + 0.22 * w_)        # it wells up along the crack and pours across the street
        flow.scale = (2.6, L_ * 1.25, 0.75 + 0.2 * (1 - u) * w_); flow.keyframe_insert("location", frame=f); flow.keyframe_insert("scale", frame=f)
        flow.hide_render = t < T_OPEN0 + 0.05; flow.keyframe_insert("hide_render", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.3, axis=1)
    glow2 = lw_point("far lava glow", (X0 + 4.0, -0.3, 1.2), 0.0, col=(1.0, 0.45, 0.12), r=0.8)
    # the heat is LOCAL light (board B3: "the whole street turns sepia"): small lamps low along the flow's edges, each
    # a pool half a metre wide on the road, on him and on the doorsteps; the street beyond them stays grey asphalt
    glows = []
    for k_, (gx, gy, e_) in enumerate(((X0 + 0.15, 0.18, 14.0), (X0 + 0.9, 0.3, 8.0), (X0 + 1.8, 0.35, 8.0), (X0 + 0.6, -1.15, 8.0), (X0 + 1.7, -1.3, 10.0), (X0 + 2.9, -1.3, 10.0), (X0 + 4.2, -1.2, 10.0))):
        glows.append((lw_point(f"lava edge glow {k_}", (gx, gy, 0.3), 0.0, col=(1.0, 0.4, 0.08), r=0.15), e_))
    steamw = lw_steam("crack steam", (X0 + 2.8, -0.2, 0.0), w=0.55, h=1.1, seed=8.5, col=(0.96, 0.96, 0.96), dens=5.0, lean=(0.2, 0.1), rise=2.0,
                      keys=[(T_OPEN0 + 0.2, 0.0), (T_POUR + 0.3, 1.0), (DUR + 1.0, 1.0)], t_end=DUR + 1.0)       # white steam off the crack itself
    try:                                                   # the lamps light everything BUT the lava and its steam: lit from a hand away, black crust went tan
        gc = bpy.data.collections.new("glow receivers"); bpy.context.scene.collection.children.link(gc)
        for o_ in [flow, tear] + lips + ([steamw] if hasattr(steamw, "name") else []): gc.objects.link(o_)
        for co_ in gc.collection_objects: co_.light_linking.link_state = 'EXCLUDE'
        for l_, _e in glows: l_.light_linking.receiver_collection = gc
        # and HE is lit orange by it: one warm lamp low on the lava side that lights only him, so the street keeps its grade
        hc = bpy.data.collections.new("heat on him"); bpy.context.scene.collection.children.link(hc)
        for o_ in bpy.data.objects:
            p_ = o_
            while p_ is not None and p_ is not data.arm: p_ = p_.parent
            if p_ is data.arm and o_.type == 'MESH': hc.objects.link(o_)
        heat = lw_point("heat on him", (X0 + 0.7, Y0 - 0.75, 0.35), 0.0, col=(1.0, 0.42, 0.1), r=0.25)
        heat.light_linking.receiver_collection = hc; glows.append((heat, 220.0))
    except Exception as e_:
        print("S4 light linking unavailable:", e_, flush=True)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS
        for n_, (l_, e_) in enumerate(glows):
            l_.data.energy = e_ * (0.25 * W(t, T_TEAR, 0.3) * (n_ < 3) + 0.75 * W(t, T_POUR - 0.2 + 0.12 * min(n_, 7 - n_), 0.7)); l_.data.keyframe_insert("energy", frame=f)
    data.finish()
    # ---- the lens: low in the street at his front left, looking up it: the crack across the bottom of the frame in
    # front of his boots, the houses down both sides behind him, the wall across the end of the street with its smoke
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(0.24, 0.6), height=0.345, t=DUR - 0.1)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24.0, fstop=11.0)
    print("S4 CAM", tuple(round(v, 2) for v in CAM), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    def cam_at(t):
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * (lw_kick(t - T_JOLT, 0.25) + lw_kick(t - T_TEAR - 0.3, 0.25)) * 2
        return CAM + shake, LOOK + shake, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="town_crack", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a crack tears across the road in front of his boots and pulls open, glowing", lambda: [tear, rim] + lips, T_TORN, T_OPEN1 + 0.2, {"whole": False}),
                        ("lava wells up and pours down the street at us", lambda: [flow], T_POUR + 0.3, DUR, {"whole": False})])
