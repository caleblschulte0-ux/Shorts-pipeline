"""BEAT 4: "But then the ground split open inside the wall, and lava poured straight into the streets."

An empty street of the town INSIDE the wall, mid-afternoon: town houses down both sides, the earth wall a dark line
across the end of the street with smoke over it. The lens backs down the street ahead of him as he pushes a wheelbarrow
of sandbags toward us. The road jolts and a crack tears across the asphalt right in front of his wheel, kerb to kerb; it
yawns open, orange inside, steam shooting out; he lets go of the barrow and leaps back; the lava wells up out of the
crack and pours over the road, the barrow tipping in and catching fire; the lava runs down the street toward the
red-roofed corner house and he hops back from it, arms up."""

S4_YC = 0.0                     # the crack's line (y), across the street
S4_HALF = 3.0                   # the asphalt and pavement, out to the house fronts (x)
S4_KERB = 1.75                  # the kerbs (x): a narrow town street, so a long lens down it holds both rows of houses
S4_FRONT = 2.35                 # the house fronts (x)


def s4_zig(x):
    """the crack's zig-zag line across the street: y at x"""
    return S4_YC + 0.12 * math.sin(3.1 * x + 0.4) + 0.07 * math.sin(7.3 * x + 1.1)


def s4_ground_z(x, y):
    z = -0.6 if abs(x) < 3.2 and abs(y - S4_YC) < 1.8 else -0.06   # under the slabs; well under the crack's trench (the gap showed black ground)
    if abs(x) > 3.3: z += 0.06 + 0.1 * lw_fbm(x * 0.4, y * 0.4, 23)
    return z


def s4_slab(name, near, m):
    """one side of the cracked street: the asphalt from the crack to the end of the street (near: toward the lens),
    its crack edge the zig-zag with a 0.25 m face down into the ground. Built as strips of quads, every face up or out
    (one concave n-gon rendered black). Returns the object, origin on the crack line."""
    xs = [-S4_HALF + 2 * S4_HALF * k / 40 for k in range(41)]
    far_y = -14.0 if near else 44.0
    bm = LW_bmesh.new()
    te = [bm.verts.new((x, s4_zig(x) - S4_YC, 0.0)) for x in xs]
    tf = [bm.verts.new((x, far_y - S4_YC, 0.0)) for x in xs]
    be = [bm.verts.new((x, s4_zig(x) - S4_YC, -0.25)) for x in xs]
    for i in range(40):
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
        K.cyl("wheelbarrow handle grip", (sx * 0.1, 0.7, 0.255), 0.02, 0.1, K.mat("grip black", "#151515", rough=0.7), rot=(math.radians(-90 + 17), 0, 0), v=12, parent=root)
    K.cyl("wheelbarrow wheel", (0, 0, 0), 0.1, 0.06, K.mat("car tyre", "#141414", rough=0.8), rot=(0, math.pi / 2, 0), v=24, parent=root)
    K.cyl("wheelbarrow hub", (0, 0, 0), 0.03, 0.07, steel, rot=(0, math.pi / 2, 0), v=12, parent=root)
    sand = lw_noise("sandbag hessian", "#8A7448", "#B29A68", scale=90, rough=0.95, bump=1.0, stretch=(1, 1, 1))   # a coarse weave
    tie = K.mat("sandbag tie", "#4A3A22", rough=0.9)
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
    lw_grid("town ground", -30, 30, -16, 60, 90, 100, s4_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))
    asph = ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt")          # REAL asphalt (Poly Haven)
    near = s4_slab("street near", True, asph)
    far = s4_slab("street far", False, asph)
    paint = K.mat("road paint", "#E9E4D4", rough=0.6)
    lines = []
    for y in list(range(-12, 0, 2)) + list(range(1, 40, 2)):
        o = K.box("centre line", (0, y + 0.5 - (0.6 if y < 0 else 0), 0.004), (0.08, 0.9, 0.006), paint, bev=0)
        o.parent = near if y < 0 else far; o.matrix_parent_inverse = (near if y < 0 else far).matrix_world.inverted()
        lines.append(o)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        for slab, y0, y1 in ((near, -14.0, -0.2), (far, 0.2, 40.0)):
            o = K.box("kerb", (sx * S4_KERB, (y0 + y1) / 2, 0.04), (0.12, y1 - y0, 0.08), kerb, bev=0.01)
            o.parent = slab; o.matrix_parent_inverse = slab.matrix_world.inverted()
    trench = lava_mat("crack lava", heat=1.4, scale=4.0, fresh=0.6)
    K.box("crack trench", (0, S4_YC, -0.32), (2 * S4_HALF + 0.4, 1.6, 0.1), trench, bev=0)
    for sy in (-1, 1):
        K.box("crack wall rock", (0, S4_YC + sy * 0.85, -0.23), (2 * S4_HALF + 0.4, 0.1, 0.4), lw_noise("crack rock", "#2A2522", "#4A3E36", scale=10, rough=0.95, bump=1.0), bev=0)
    houses = []
    for sx in (-1, 1):
        y = -9.0 + (0.6 if sx > 0 else 0.0); k = 0
        while y < 34.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            corner = sx > 0 and abs(y + w / 2 - 2.4) < 2.0
            roof = "#C0302A" if corner else ROOFS[(k * 3 + (sx > 0) + 1) % len(ROOFS)]
            if roof == "#B8352B" and not corner: roof = ROOFS[2]
            hs = town_house(f"town house {sx}_{k}" + (" corner" if corner else ""), (sx * (S4_FRONT + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            roof=roof, wall=WALLS[k % len(WALLS)], base=0.3, seed=k + 20)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    wall = earth_wall("earth wall", [(x, 40.0 + 0.01 * x * x) for x in range(-30, 32, 2)], h=4.4, crest=1.4, base=8.5, seed=12)
    for k, x in enumerate((-9.0, 1.0, 10.0)):            # the eruption's smoke over the wall: rolling columns of gas, leaning off on the wind
        lw_steam(f"wall smoke {k}", (x, 48.0 + 2 * k, 2.0), w=4.5, h=16.0, seed=3.3 * k, col=(0.42, 0.41, 0.42), dens=2.5, lean=(0.5, 0.2), rise=1.2, t_end=DUR + 1.0)
    for k in range(5):
        K.sph("far mountain", (-40 + 20 * k, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.8), seg=24, ring=12)
    for k in range(3):                                   # REAL street lamps (Poly Haven) along the left kerb
        ph_model("street_lamp_01", (-(S4_KERB + 0.25), 6 + 6 * k, 0.0), rot=(0, 0, -math.pi / 2), scale=0.5, name=f"street lamp {k}")

    def light():
        return iceland_light(sun_elev=30, sun_az=-30, sun=3.2, sky=0.45, haze=1.2)
    return dict(light=light, near=near, far=far, houses=houses)


def shot4():
    """THE CRACK. The lens backs down the street ahead of him as he pushes the barrow toward us; the road jolts and the
    crack tears across in front of his wheel; it yawns open, glowing, steam shooting up; he lets go and leaps back; lava
    wells up and pours over the road, the barrow tips in and burns; the lava runs toward the corner house and he hops
    back from it, arms up."""
    T_STOP = 0.2 * DUR; T_JOLT = 0.23 * DUR; T_TEAR = T_JOLT + 0.05; T_TORN = T_TEAR + 0.35
    T_OPEN0 = 0.33 * DUR; T_OPEN1 = 0.5 * DUR; T_LET = 0.36 * DUR
    T_POUR = 0.55 * DUR; T_TIP = 0.6 * DUR; T_RUN = 0.7 * DUR
    W = lw_win
    P = place_town_crack()
    light = P["light"]; near, far = P["near"], P["far"]
    data = load_data()
    Y0, YS = 1.3, 0.92                                     # where he starts pushing and where he stops (y)
    data.place(0.15, Y0, 0.0)
    kit = hard_hat(data)
    data.walk_to((0.15, YS), 0.0, T_STOP, pushing=True)
    # ---- the leap back at T_LET and the hops back at T_RUN, facing the crack (and us) the whole time
    def hop(t, t0, d, h, T=0.4):
        u = min(1.0, max(0.0, (t - t0) / T)); return d * ease(u), h * math.sin(math.pi * u)
    for f in range(F(T_STOP) + 1, NF + 1):
        t = (f - 1) / FPS
        y1, z1 = hop(t, T_LET, 0.32, 0.13, 0.5); y0_, z0_ = hop(t, T_POUR - 0.1, 0.1, 0.09, 0.4); y1 += y0_; z1 += z0_; y2, z2 = hop(t, T_RUN, 0.13, 0.06); y3, z3 = hop(t, T_RUN + 0.45, 0.14, 0.06)
        jolt = -0.03 * lw_kick(t - T_JOLT, 0.1) - 0.05 * lw_kick(t - T_POUR, 0.15)
        sway = 0.04 * math.sin(2 * math.pi * (t - T_LET) / 1.1) * W(t, T_LET + 0.3, 0.3)
        data._kobj(t, loc=(0.15 + sway - 0.45 * W(t, T_RUN, 0.7), YS + y1 + y2 + y3 + 0.04 * W(t, T_POUR, 0.2), z1 + z2 + z3 + jolt),
                   rot=math.radians(-8) * W(t, T_LET, 0.3) + math.radians(12) * math.sin(2 * math.pi * (t - T_LET) / 1.6) * W(t, T_LET + 0.3, 0.4) + math.radians(-14) * W(t, T_RUN, 0.5))
    lw_layer(data, "spine", lambda t: (14 * W(t, 0.0, 0.2) * (1 - W(t, T_STOP, 0.2)) - 16 * lw_kick(t - T_JOLT, 0.18) + 10 * W(t, T_TEAR, 0.25) * (1 - W(t, T_LET, 0.2))
                                       - 14 * W(t, T_LET, 0.2) * (1 - W(t, T_LET + 0.6, 0.3)) - 10 * W(t, T_RUN, 0.3)
, 0, 0), 0, DUR + 0.4)
    # ---- the barrow: pushed ahead of him, set down at the stop, let go; it rolls to the edge, tips in and burns
    bar, flames = s4_barrow()
    sc.frame_set(1); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)
    def bpos(t):
        sc.frame_set(F(min(t, T_LET))); bpy.context.view_layer.update()
        c = data.pos(); return Vector((c.x, c.y - 0.13 - 0.72, 0.1))
    path = {f: bpos((f - 1) / FPS) for f in range(1, F(T_LET) + 1)}
    y_edge = s4_zig(0.15) + 0.03
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        p = path[min(f, F(T_LET))].copy()
        pitch = math.radians(-6) * W(t, T_STOP - 0.1, 0.5)    # set down at the stop: the handles drop onto its legs
        p.z -= 0.03 * lw_kick(t - T_JOLT, 0.1)                  # the road jolts it with him
        if t > T_LET:                                       # let go: it rolls to the edge, then the tip
            roll = 0.25 * W(t, T_OPEN0 + 0.2, 0.9)
            p.y = max(y_edge - 0.12, p.y - roll)
            tip = W(t, T_TIP, 0.6)
            pitch += math.radians(52) * tip                  # nose first into the gap, its wheel sinking into the glow
            p.z -= 0.3 * tip
        bar.location = p; bar.rotation_euler = (pitch, 0, 0)
        bar.keyframe_insert("location", frame=f); bar.keyframe_insert("rotation_euler", frame=f)
    sc.frame_set(NF); bpy.context.view_layer.update()     # the barrow burns where it tipped: its sandbags and the tray catch
    fb = bar.matrix_world @ Vector((0.0, 0.32, 0.2))
    lw_fire_column("barrow fire", (fb.x, fb.y, fb.z), w=0.55, h_fire=0.9, h_smoke=2.6, lean=(0.15, 0.3), t_end=DUR + 1.0, seed=4.2, fire=6.0,
                   smoke_d=3.0, keys=[(T_TIP + 0.2, 0.0), (T_TIP + 0.75, 1.0)])
    bl = lw_point("barrow fire light", (fb.x, fb.y - 0.3, fb.z + 0.5), 0.0, col=(1.0, 0.45, 0.15), r=0.2)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; bl.data.energy = 120.0 * W(t, T_TIP + 0.2, 0.55) * (1 + 0.25 * math.sin(2 * math.pi * 4.1 * t)); bl.data.keyframe_insert("energy", frame=f)
    def handle(sx):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update()
            return bar.matrix_world @ Vector((sx * 0.1, 0.7, 0.27))
        return fn
    for sd, sx in zip(sides, (-1, 1)):
        data.reach(sd, handle(sx), 0.0, T_LET, lead=0.05, back=None, elbow_out=0.35)
    # arms up against the heat: hands up at his face's sides from the leap, higher at the hops back
    for sd in sides:
        HK = [(T_LET + 0.7, (0.08, 0.14, 0.0)), (T_POUR - 0.03, (0.07, 0.13, 0.07)), (T_POUR + 0.25, (0.08, 0.15, 0.0)), (T_TIP + 0.3, (0.04, 0.1, 0.12)),
              (T_RUN, (0.07, 0.13, 0.07)), (T_RUN + 0.4, (0.08, 0.15, 0.06)), (T_RUN + 0.8, (0.06, 0.12, -0.04)), (DUR + 0.4, (0.08, 0.15, 0.05))]
        data.reach(sd, lw_hand(data, sd, HK), HK[0][0], DUR + 0.3, lead=0.7, back=None, elbow_out=0.4)
    # ---- the crack: a hairline tears across from kerb to kerb, then the street pulls apart and the lava shows in the gap
    gm = lava_mat("crack glow", heat=1.6, scale=6.0)
    xs = [-S4_HALF + 2 * S4_HALF * k / 60 for k in range(61)]
    bm = LW_bmesh.new()
    far_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC, 0.004)) for x in xs]
    near_e = [bm.verts.new((x + S4_HALF, s4_zig(x) - S4_YC - 0.035, 0.004)) for x in xs]
    for i in range(60): bm.faces.new((near_e[i], near_e[i + 1], far_e[i + 1], far_e[i]))
    me = bpy.data.meshes.new("crack glow"); bm.to_mesh(me); bm.free(); me.materials.append(gm)
    tear = lw_link(bpy.data.objects.new("crack glow", me)); tear.location = (-S4_HALF, S4_YC, 0.0)
    tear.shape_key_add(name="Basis")
    op = tear.shape_key_add(name="open")
    for i in range(61): op.data[61 + i].co.y = s4_zig(xs[i]) - S4_YC - 0.85
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_TEAR, T_TORN - T_TEAR); o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0)
        tear.scale = (max(0.002, u), 1, 1); tear.hide_render = u < 0.01; op.value = o
        tear.keyframe_insert("scale", frame=f); tear.keyframe_insert("hide_render", frame=f); op.keyframe_insert("value", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; o = W(t, T_OPEN0, T_OPEN1 - T_OPEN0); sh = 0.015 * math.sin(2 * math.pi * 11 * t) * lw_kick(t - T_JOLT, 0.25)
        near.location = (sh, S4_YC - 0.8 * o, 0.02 * o + 0.04 * lw_kick(t - T_JOLT, 0.12)); near.rotation_euler = (math.radians(-4) * o, 0, 0)
        far.location = (-sh, S4_YC, 0.0)
        for o_ in (near, far): o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    # board round 3: "a thin painted line on the road, with no gap opening". The asphalt BREAKS along both lips: slabs of
    # it heave up and tilt as the street pulls apart, raw dark edges catching the glow
    lip = lw_noise("broken asphalt", "#3A3A3C", "#5A5A5E", scale=30, rough=0.9, bump=0.8)
    rk = lw_random.Random(7)
    lips = []
    for slab, sg in ((near, -1), (far, 1)):
        x = -S4_HALF + 0.1
        while x < S4_HALF - 0.1:
            w = rk.uniform(0.18, 0.34); xc = x + w / 2
            ch = K.box("crack lip chunk", (xc, s4_zig(xc) - S4_YC + sg * rk.uniform(0.04, 0.1), -0.01), (w * 0.92, rk.uniform(0.12, 0.22), 0.07), lip, bev=0.012)
            ch.parent = slab; ch.matrix_parent_inverse = slab.matrix_world.inverted(); lips.append(ch)
            lift = rk.uniform(0.25, 0.55); yaw = rk.uniform(-0.25, 0.25); t0 = T_OPEN0 + 0.1 * abs(xc) / S4_HALF
            for f in range(1, NF + 1):
                t = (f - 1) / FPS; o = W(t, t0, 0.45)
                ch.rotation_euler = (-sg * lift * o, 0.15 * yaw * o, yaw * o); ch.location.z = -0.01 + 0.05 * o
                ch.keyframe_insert("rotation_euler", frame=f); ch.keyframe_insert("location", frame=f)
            x += w
    lava_flow_key(gm, 0.0, DUR + 0.5, 0.2)
    trench = bpy.data.materials["crack lava"]
    lava_flow_key(trench, 0.0, DUR + 0.5, 0.25)
    # ---- steam shooting up out of the crack as it opens
    steam = []
    for k, x in enumerate((-2.1, -1.3, 1.4, 2.2)):        # out to the sides of him: the gap in front of him stays clear; steam as a GAS
        t0 = T_OPEN0 + 0.08 * k
        steam.append(lw_steam(f"crack steam {k}", (x, s4_zig(x) - 0.2, -0.25), w=0.7, h=2.8, seed=2.1 * k, rise=2.6,
                              keys=[(t0, 0.0), (t0 + 0.45, 1.0), (DUR, 0.55)], t_end=DUR + 1.0))
    # ---- the lava: it wells up in the crack and pours out over the road, toward him and the corner house
    lm = lava_mat("street lava", heat=1.2, scale=4.0, fresh=0.8)
    out = []
    for k in range(28):
        a = 2 * math.pi * k / 28
        out.append((1.0 * math.cos(a) + 0.07 * math.sin(4 * a) + 0.05 * math.sin(7 * a), 1.0 * math.sin(a) + 0.08 * math.cos(5 * a)))
    flow = lava("street lava", out, z=0.0, thick=0.2, m=lm, seed=6, lumpy=0.07)
    # board round 3: "the street in front of him never fills with orange", "a thin glowing band, not lava pouring":
    # a liquid tongue swells up out of the gap and runs DOWN the street at the lens over the near slab, kerb to kerb
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = W(t, T_POUR, DUR - T_POUR); w_ = W(t, T_POUR - 0.25, 0.4)
        L_ = 0.3 + 1.0 * u
        flow.location = (0.05 + 0.1 * math.sin(3 * t), S4_YC - 0.25 - L_, -0.22 + 0.25 * w_)
        flow.scale = (0.6 + 1.0 * u + 0.4 * w_, L_, 1.0 + 0.4 * (1 - u) * w_); flow.keyframe_insert("location", frame=f); flow.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.3, axis=1)
    glow = lw_point("crack glow", (0.0, S4_YC, 0.25), 0.0, col=(1.0, 0.45, 0.12), r=0.6)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; glow.data.energy = 260.0 * W(t, T_OPEN0, 0.5) + 200.0 * W(t, T_POUR, 0.6); glow.data.keyframe_insert("energy", frame=f)
    # ---- face and head: one feeling per moment, held
    data.look_at(Vector((0.15, -2.5, 0.6)), 0.0, max_yaw=40, blend=0.0)
    data.look_at(Vector((0.1, S4_YC, 0.0)), T_JOLT + 0.05, max_yaw=50, max_pitch=50, blend=0.2)
    data.look_at(Vector((0.4, S4_YC + 0.6, 0.0)), T_POUR + 0.1, max_yaw=50, max_pitch=50, blend=0.3)
    data.look_at(Vector((2.6, 2.4, 0.8)), T_RUN - 0.3, max_yaw=60, max_pitch=40, blend=0.3)
    data.look_at(Vector((0.2, -2.5, 0.7)), T_RUN + 0.45, max_yaw=50, blend=0.3)
    data.expression("determined", 0.0, T_JOLT, blend=0.2)
    data.expression("surprised", T_JOLT + 0.02, T_LET - 0.05, blend=0.12)
    data.expression("alarmed", T_LET, DUR + 1.0, blend=0.15)
    data.finish()
    # ---- the lens: backing down the street ahead of him while he pushes, then holding as the street splits
    # REDESIGN after board round 3 ("80% bare asphalt", "houses are slivers cut by the top edge", "no wall at the end"):
    # the lens comes DOWN to his height and goes LONG, right up the middle of a narrow street, so both rows of houses
    # close in behind him and the wall with its smoke stands across the end of the street over his head; the crack
    # tears across between him and us and the lava runs down the street at the lens
    CAM = Vector((0.3, YS - 5.55, 1.0)); LOOK = Vector((0.12, 40.0, -2.1))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=100.0, fstop=16.0)
    def cam_at(t):
        sc.frame_set(F(min(t, T_STOP))); bpy.context.view_layer.update()
        dy = data.pos().y - YS
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * lw_kick(t - T_JOLT, 0.25) * 2
        back = Vector((0, 0.0, 0.0))
        p0 = data.pos().copy(); sc.frame_set(F(t)); bpy.context.view_layer.update()
        fol = (data.pos() - p0) * 0.8; fol.z = 0.0                     # and pans with him as he leaps and hops back
        dolly = Vector(((data.pos() - p0).x * 0.8, (data.pos() - p0).y * 1.0, 0))               # and keeps its distance as he backs away
        return CAM + Vector((0, dy, 0)) + shake + back + dolly, LOOK + Vector((0, dy, 0)) + shake + back + fol, data.pos() + Vector((0, 0, 0.6))
    # CUT to the WIDE as the lava pours (board round 2: "80% bare asphalt", "no wall at the end of the street", "never
    # seen pouring toward a house"): high behind the lens and up the street, the crack glowing kerb to kerb, the lava
    # running at the red-roofed corner house, the street's houses both sides, the wall across its end with smoke over it
    T_W0, T_W1 = T_TIP - 0.05, T_RUN + 0.35
    CW = Vector((1.2, -9.5, 4.0)); LW = Vector((0.3, 8.0, 0.2))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((0.0, 0.35, -0.05)) * (t - T_W0), LW, Vector((0.6, 1.0, 0.3))), T_W0, T_W1, 100.0, 24.0)
    return dict(lanes=[], kiosks=[], place="town_crack", light=light, data=data, rest=1, grips=("wheelbarrow",), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("he pushes the barrow of sandbags down the street", lambda: [o for o in meshes([bar]) if "wheel" not in o.name.split("barrow ")[-1] and "hub" not in o.name], 0.0, T_STOP, {"whole": False, "moves": True}),
                        ("a crack tears across the road in front of his wheel and yawns open, glowing", lambda: [tear] + lips, T_TORN, T_OPEN1 + 0.2, {"whole": False}),
                        ("lava wells up and pours over the road; the barrow tips in and burns", lambda: [flow], T_POUR, DUR, {"whole": False})])
