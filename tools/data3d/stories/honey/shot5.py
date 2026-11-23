# ---------------------------------------------------------------- shot 5: the fakes keep coming (the alley)
"""5 ALMOST HALF. The alley behind the stall, where the imports come in: cobbles, brick walls, a back door, bins,
crates, and a stepped stand of import jars, three tiers of seven. One jar in each tier already wears a red SUSPECT
label (the old test's one in seven). He hauls down the big lever of the EU's new scanner; its red bar sweeps along the
tiers and two more in every tier spin round to red: three in seven, almost half, three times the old count. He picks
up a red one and holds it out to us: what's in your jar?"""

S5_N, S5_TIERS = 7, 3
S5_OLD = 2                                       # the one in seven the old test caught, in every tier
S5_NEW = (4, 6)                                  # the two more the new test catches: three in seven
S5_JR, S5_JH, S5_DX = 0.036, 0.12, 0.085
S5_TX0 = -0.15                                   # the first column's x
S5_TIER = [(0.42, 0.82 + 0.2 * k) for k in range(S5_TIERS)]    # (y, top z) of each shelf: high on a rack against the alley wall, over his head
S5_LEV = Vector((0.28, 0.14, 0.0))               # the lever's foot, at the stand's right end
S5_PIV = 0.16; S5_LL = 0.27                      # its pivot height, its arm's length
S5_P = Vector((0.48, 0.13, 0.0))                 # where he stands to haul it


def s5_brick(name, a="#9C4A32", b="#B8644A", mortar="#CFC4B2", scale=7.0):
    """a real brick wall: courses of bricks of two colours with a soft mortar joint and a rough bump"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord"); br = nt.nodes.new("ShaderNodeTexBrick")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (math.pi / 2, 0, 0)   # courses along x, rows up z
    br.inputs["Scale"].default_value = scale; br.inputs["Mortar Size"].default_value = 0.018; br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.2; br.offset = 0.5
    br.inputs["Color1"].default_value = (*K.lin(a), 1); br.inputs["Color2"].default_value = (*K.lin(b), 1)
    br.inputs["Mortar"].default_value = (*K.lin(mortar), 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 60
    mix = nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type = 'MULTIPLY'; mix.inputs["Fac"].default_value = 0.25
    nt.links.new(br.outputs["Color"], mix.inputs["Color1"]); nt.links.new(nz.outputs["Fac"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bs.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5; bp.invert = True
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], bs.inputs["Normal"])
    return m


def s5_crate(name, loc, size, rnd):
    """a slatted wooden crate"""
    wood = hw_wood(f"crate wood {rnd.randrange(3)}", "#8A6A44", "#A8865A", scale=5)
    dark = K.mat("crate gap", "#3A2C1E", rough=0.9)
    x, y, z = loc; sx, sy, sz = size
    K.box(name + " inside", (x, y, z + sz / 2), (sx - 0.01, sy - 0.01, sz - 0.01), dark, bev=0)
    n = 3
    for k in range(n):
        zz = z + sz * (k + 0.5) / n
        for s in (-1, 1):
            K.box(name + " slat", (x, y + s * sy / 2, zz), (sx, 0.012, sz / n - 0.012), wood, bev=0.003)
            K.box(name + " slat", (x + s * sx / 2, y, zz), (0.012, sy, sz / n - 0.012), wood, bev=0.003)
    K.box(name + " top", (x, y, z + sz - 0.006), (sx + 0.006, sy + 0.006, 0.012), wood, bev=0.003)
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            K.box(name + " post", (x + sx_ * (sx / 2 - 0.01), y + sy_ * (sy / 2 - 0.01), z + sz / 2), (0.022, 0.022, sz), wood, bev=0.003)


def place_market_alley():
    """THE ALLEY BEHIND THE CHEAP STALL: cobbles (each stone a stone), brick walls with a back door and a drainpipe,
    crates, bins and sacks, the stall's canvas back, a lamp over the door, the drum of SUGAR SYRUP and its tap."""
    rnd = hw_random.Random(55)
    K.box("alley bed", (0, 0.5, -0.008), (8, 8, 0.012), hw_cobbles("alley cobbles", "#7E776C", "#A09682", "#3E3832", scale=7), bev=0)   # board: spheres "read as polka dots"
    brick = s5_brick("alley brick")
    K.box("alley back wall", (0, 0.62, 1.2), (6, 0.12, 2.4), brick, bev=0)
    K.box("alley side wall", (-1.35, 0.0, 1.2), (0.12, 2.4, 2.4), s5_brick("alley brick dark", "#7E3E2C", "#9A5440"), bev=0)
    door = hw_wood("back door", "#3E5A4A", "#557262", scale=4)
    K.box("back door", (-0.55, 0.555, 0.55), (0.42, 0.03, 1.1), door, bev=0.01)
    for k in range(5):
        K.box("door plank", (-0.55 - 0.16 + k * 0.08, 0.538, 0.55), (0.004, 0.006, 1.06), K.mat("plank gap", "#26342C", rough=0.9), bev=0)
    K.sph("door knob", (-0.38, 0.53, 0.55), 0.016, K.mat("brass", "#B89040", rough=0.3, metal=0.9))
    K.box("door step", (-0.55, 0.5, 0.02), (0.5, 0.12, 0.04), hw_noise("step stone", "#9A958A", "#B5AFA2", scale=10), bev=0.006)
    lampm = K.mat("lamp glass", "#FFE2A0", rough=0.3, emit=6.0)
    K.box("lamp arm", (-0.55, 0.52, 1.28), (0.02, 0.12, 0.02), K.mat("lamp iron", "#2E2A28", rough=0.5, metal=0.7), bev=0.003)
    K.cyl("lamp", (-0.55, 0.46, 1.22), 0.04, 0.09, lampm, v=16, bev=0.005)
    pipe = K.mat("drainpipe", "#3C4A42", rough=0.4, metal=0.5)
    K.cyl("drainpipe", (0.95, 0.54, 1.2), 0.025, 2.4, pipe, v=16, bev=0.002)
    K.box("drain shoe", (0.95, 0.5, 0.05), (0.06, 0.1, 0.05), pipe, bev=0.006)
    # the stall's back: striped canvas over the alley's far end
    for k in range(9):
        K.box("stall canvas", (1.3 + 0.0, -0.6 + k * 0.14, 0.9), (0.02, 0.14, 1.0),
              K.mat("canvas red" if k % 2 else "canvas cream", "#B8362C" if k % 2 else "#EDE2C8", rough=0.85), bev=0)
    # bins, sacks, a stack of empty crates by the door, a broom
    binm = K.mat("bin green", "#3E6A4A", rough=0.5, metal=0.3)
    K.cyl("bin", (-0.95, 0.38, 0.22), 0.16, 0.44, binm, v=24, bev=0.01)
    K.cyl("bin lid", (-0.95, 0.38, 0.45), 0.17, 0.03, binm, v=24, bev=0.006)
    for k in range(3):
        s5_crate(f"empty crate {k}", (-0.2 + 0.02 * k, 0.42, 0.22 * k), (0.28, 0.2, 0.22), rnd)
    K.cyl("broom handle", (-0.82, 0.5, 0.6), 0.012, 1.2, hw_wood("broom", "#A07A50", "#B89068"), rot=(0.12, 0, 0), v=12)
    return lambda: village_light(sun_elev=50, sun_az=-25, sun=3.2, sky=0.3)


def s5_stand(rnd):
    """the import rack: a tall steel-and-plank shelving rack against the alley wall, three shelves of seven jars
    over his head (board: the stand was too small to read a share from; on a tall rack the tiers fill the frame)"""
    wood = hw_wood("stand wood", "#8A6A44", "#A8865A", scale=5)
    steel = K.mat("rack steel", "#3E5A7A", rough=0.4, metal=0.5)
    xa, xb = S5_TX0 - 0.07, S5_TX0 + 6 * S5_DX + 0.07
    for x in (xa, xb):
        for y in (S5_TIER[0][0] - 0.08, S5_TIER[0][0] + 0.08):
            K.box("rack upright", (x, y, 0.77), (0.03, 0.03, 1.54), steel, bev=0.003)
    for k, (y, z) in enumerate(S5_TIER):
        K.box("rack shelf", ((xa + xb) / 2, y, z - 0.012), (xb - xa + 0.04, 0.18, 0.024), wood, bev=0.004)
        K.box("rack lip", ((xa + xb) / 2, y - 0.09, z - 0.03), (xb - xa + 0.04, 0.01, 0.04), steel, bev=0.002)
    for z in (0.25, 0.55):
        K.box("rack shelf", ((xa + xb) / 2, S5_TIER[0][0], z), (xb - xa + 0.04, 0.18, 0.024), wood, bev=0.004)
    K.text("stand stencil", "IMPORTS", ((xa + xb) / 2, S5_TIER[0][0] - 0.097, S5_TIER[0][1] - 0.03), 0.028, (math.pi / 2, 0, 0), hw_ink("rack word", "#FFFFFF"), extrude=0.0004)
    for k in range(3):                                   # the empty crates the jars came in, on the bottom shelf and the floor
        s5_crate(f"import crate {k}", (xa + 0.16 + 0.24 * (k % 2), S5_TIER[0][0], (0.27, 0.57, 0.0)[k]), (0.2, 0.15, 0.13), rnd)
    jars = []
    for k, (y, z) in enumerate(S5_TIER):
        row = []
        for i in range(S5_N):
            red = i == S5_OLD or i in S5_NEW
            j = jar(f"import jar {k} {i}", (S5_TX0 + i * S5_DX, y, z), r=S5_JR, h=S5_JH, fill=0.9, honey_col="#E8A82A", glow=0.35,
                    label="PURE HONEY", back="SUSPECT" if red else None, yaw=math.radians(rnd.uniform(-6, 6)))
            if i == S5_OLD:
                j["spin"].rotation_euler = (0, 0, math.pi)          # the old test already caught this one
            row.append(j)
        jars.append(row)
    return jars


def s5_scanner():
    """THE EU SCANNER: a blue rail along the rack's top, a carriage on it with a red light bar hanging down in front of
    the three shelves, just off the jars' faces; and its big lever on the rack's right upright. Returns (carriage, arm)."""
    steel = K.mat("scanner steel", "#B8BCC0", rough=0.25, metal=0.9)
    blue = K.mat("scanner blue", "#1E4A7A", rough=0.4)
    x0, x1 = S5_TX0 - 0.1, S5_TX0 + 6 * S5_DX + 0.1
    yf = S5_TIER[0][0] - 0.12; ztop = S5_TIER[-1][1] + S5_JH + 0.12
    K.box("gantry rail", ((x0 + x1) / 2, yf, ztop), (x1 - x0 + 0.06, 0.04, 0.035), blue, bev=0.004)
    K.text("gantry word", "EU TEST", ((x0 + x1) / 2, yf - 0.022, ztop), 0.026, (math.pi / 2, 0, 0), hw_ink("gantry word", "#FFFFFF"), extrude=0.0004)
    car = K.empty("scanner carriage", (0, 0, 0))
    K.box("scanner head", (0, yf, ztop - 0.04), (0.07, 0.07, 0.06), blue, bev=0.006, parent=car)
    K.capsule("scan bar", Vector((0, yf, S5_TIER[0][1] - 0.02)), Vector((0, yf, ztop - 0.06)), 0.009, K.mat("scan red", "#FF3020", rough=0.3, emit=6.0), parent=car)
    hw_local(car)
    K.box("lever box", (S5_LEV.x, S5_LEV.y, S5_PIV / 2), (0.08, 0.1, S5_PIV), blue, bev=0.006)
    K.capsule("lever cable", Vector((S5_LEV.x, S5_LEV.y + 0.03, S5_PIV)), Vector((x1 + 0.03, yf + 0.02, ztop)), 0.006, K.mat("cable black", "#1A1A1A", rough=0.6))
    arm = K.empty("lever arm", (S5_LEV.x, S5_LEV.y, S5_PIV))
    K.cyl("lever rod", (0, 0, S5_LL / 2), 0.012, S5_LL, steel, v=16, bev=0.002, parent=arm)
    K.cyl("lever grip", (0, 0, S5_LL), 0.022, 0.09, K.mat("lever red", "#C8261E", rough=0.4), rot=(math.pi / 2, 0, 0), v=16, bev=0.004, parent=arm)
    K.sph("lever hub", (0, 0, 0), 0.03, steel, parent=arm)
    hw_local(arm)
    return car, arm


def shot5():
    """ALMOST HALF. Beside the stand of import jars (one red in every tier of seven) he hauls the scanner's lever
    down with both hands; its red bar sweeps along the tiers and two more in every tier spin red; he jumps back, leans
    in after it, points along the reds, then turns to us with his hands out: what's in your jar?"""
    W = hw_win
    T_IN = 0.9                                    # walks in to the lever
    T_GRIP = 1.1                                  # both hands on its grip
    T_PULL0, T_PULL1 = 1.3, 1.75                  # hauls it down
    T_S0, T_S1 = 1.8, 3.6                         # the bar sweeps the tiers on its own
    T_LET = 2.0                                   # lets go and jumps back
    T_LEAN = 2.6                                  # leans in after the bar
    T_POINT = 3.25                                # points along the reds
    T_SHOW = 4.3                                  # turns to us, hands out: what's in your jar?
    T_BACK = 5.0                                  # swings back to point at the reds, then back to us
    A_UP, A_DN = math.radians(-2), math.radians(44)       # leaning up, hauled down toward him
    light = place_market_alley()
    rnd = hw_random.Random(5)
    jars = s5_stand(rnd)
    car, arm = s5_scanner()
    x0, x1 = S5_TX0 - 0.08, S5_TX0 + 6 * S5_DX + 0.08
    def car_x(t):
        return x0 + (x1 - x0) * ease(min(1.0, max(0.0, (t - T_S0) / (T_S1 - T_S0))))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        car.location = (car_x(t), 0, 0); car.keyframe_insert("location", frame=f)
        a = A_UP + (A_DN - A_UP) * ease(min(1.0, max(0.0, (t - T_PULL0) / (T_PULL1 - T_PULL0))))
        a -= (A_DN - A_UP) * ease(min(1.0, max(0.0, (t - T_LET - 0.6) / 0.35)))       # let go, it springs back up
        arm.rotation_euler = (0, a, 0); arm.keyframe_insert("rotation_euler", frame=f)
    for row in jars:
        for i in S5_NEW:
            u = (S5_TX0 + i * S5_DX - x0) / (x1 - x0)
            tt = T_S0 + (T_S1 - T_S0) * min(range(101), key=lambda k: abs(ease(k / 100) - u)) / 100   # the bar reaches it
            jar_flip(row[i], tt)
    def grip_pt(t, dy):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return arm.matrix_world @ Vector((0, dy, S5_LL))
    # ---- him
    data = load_data()
    P0 = S5_P + Vector((0.17, 0.06, 0))   # from up the alley, three-quarter to us
    data.place(P0.x, P0.y, math.degrees(math.atan2((S5_P - P0).x, -(S5_P - P0).y)))
    hat = bee_hat(data)
    data.walk_to(S5_P, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw = data.arm.rotation_euler.z
    FACE_LEV = math.atan2(S5_LEV.x - S5_P.x, -(S5_LEV.y - S5_P.y)) + math.radians(16)     # three-quarter to us, not his back
    FACE_STAND = math.radians(-48); FACE_US = math.radians(-12)
    def yaw(t):
        y = yw + (FACE_LEV - yw) * W(t, T_IN - 0.05, 0.3)
        y += (FACE_STAND - FACE_LEV) * W(t, T_LET + 0.1, 0.35)
        y += (FACE_US - FACE_STAND) * W(t, T_SHOW - 0.3, 0.4)
        y += math.radians(22) * W(t, T_POINT, 0.7) * (1 - W(t, T_SHOW - 0.35, 0.3))     # his finger runs along the reds
        y += (FACE_STAND - FACE_US) * W(t, T_BACK, 0.35) * (1 - W(t, T_BACK + 0.8, 0.4))     # swings back to the rack: those ones
        return y
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        p = S5_P + Vector((0.16, -0.03, 0)) * W(t, T_PULL0 - 0.05, 0.5)                               # walks back, hauling it down
        p += Vector((0.04, -0.04, 0)) * W(t, T_LET + 0.25, 0.2) * (1 - W(t, T_LEAN, 0.35))                  # jumps back as it goes
        p += Vector((-0.04, 0, 0)) * W(t, T_LEAN, 0.35) * (1 - W(t, T_SHOW - 0.3, 0.4))              # leans in after the bar
        p += Vector((0.0, -0.06, 0)) * W(t, T_SHOW - 0.3, 0.4)                                        # and steps to us
        p += Vector((-0.04, 0.03, 0)) * W(t, T_POINT - 0.15, 0.3) * (1 - W(t, T_SHOW - 0.3, 0.4))   # a step after his finger
        p += Vector((-0.05, -0.07, 0)) * W(t, T_BACK + 0.8, 0.45)                                     # and again: what's in YOUR jar?
        z = 0.06 * hw_kick(t - T_LET - 0.28, 0.14) + 0.035 * hw_kick(t - T_PULL1 + 0.05, 0.12) + 0.05 * hw_kick(t - T_SHOW - 0.1, 0.14) \
            + 0.04 * hw_kick(t - T_SHOW - 1.1, 0.13) + 0.05 * hw_kick(t - T_SHOW - 2.0, 0.14) + 0.035 * hw_kick(t - T_POINT - 0.05, 0.12) + 0.04 * hw_kick(t - T_POINT - 0.5, 0.12)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (14 * W(t, T_PULL0 - 0.1, 0.3) * (1 - W(t, T_PULL1, 0.3)) - 12 * W(t, T_LET, 0.2) * (1 - W(t, T_LEAN, 0.3))
                                      + 16 * W(t, T_LEAN, 0.3) * (1 - W(t, T_SHOW - 0.4, 0.35)) - 6 * W(t, T_SHOW, 0.4), 0,
                                      8 * math.sin(2 * math.pi * (t - T_SHOW) / 1.1) * W(t, T_SHOW + 0.2, 0.4)), 0, DUR + 0.4)
    sc.frame_set(F(T_GRIP)); bpy.context.view_layer.update()
    near, far = sorted("LR", key=lambda s: acts._shoulder(data, s).y)     # [near the lens, far]
    rest = {s: hw_hand(data, s, [(0.0, (0.05, 0.08, -0.13)), (DUR + 0.3, (0.05, 0.08, -0.13))]) for s in "LR"}
    after = {near: hw_hand(data, near, [(0.0, (0.06, 0.1, -0.1)), (T_LET + 0.3, (0.1, 0.12, -0.03)), (T_LEAN + 0.2, (0.1, 0.1, -0.06)),
                                         (T_POINT, (0.16, 0.04, -0.03)), (T_POINT + 0.4, (0.15, 0.05, -0.03)), (T_SHOW - 0.2, (0.08, 0.1, -0.08)),
                                         (T_SHOW + 0.25, (0.12, 0.09, -0.04)),
            (T_BACK + 0.3, (0.16, 0.04, -0.03)), (T_BACK + 0.65, (0.15, 0.05, -0.05)), (T_SHOW + 2.05, (0.13, 0.08, -0.04)), (T_SHOW + 2.5, (0.06, 0.12, -0.1)), (DUR + 0.3, (0.13, 0.08, -0.04))]),     # hands out, down, out: what's in YOUR jar?
             far: hw_hand(data, far, [(0.0, (0.06, 0.1, -0.1)), (T_LET + 0.3, (0.08, 0.12, -0.03)), (T_LEAN + 0.2, (0.06, 0.1, -0.1)),
                                       (T_SHOW - 0.2, (0.06, 0.1, -0.1)), (T_SHOW + 0.25, (0.12, 0.09, -0.04)), (T_SHOW + 0.75, (0.06, 0.11, -0.11)), (T_SHOW + 1.2, (0.1, 0.12, -0.03)),
            (T_SHOW + 1.65, (0.05, 0.08, -0.12)), (T_SHOW + 2.05, (0.13, 0.08, -0.04)), (T_SHOW + 2.5, (0.06, 0.12, -0.1)), (DUR + 0.3, (0.13, 0.08, -0.04))])}
    def hand_fn(s, dy):
        def fn(t):
            g = W(t, T_GRIP - 0.7, 0.65)
            p = rest[s](t).lerp(grip_pt(t, dy), g)
            return p.lerp(after[s](t), W(t, T_LET, 0.6))
        return fn
    data.reach(near, hand_fn(near, -0.035), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(far, hand_fn(far, 0.035), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    CAM = Vector((0.34, -1.29, 0.7)); LOOK = Vector((0.34, 0.3, 0.74))
    data.look_at(Vector((S5_LEV.x, S5_LEV.y, 0.5)), 0.0, max_yaw=45, max_pitch=35, blend=0.0)
    data.look_at(Vector((0.05, 0.42, 1.05)), T_S0 + 0.1, max_yaw=32, max_pitch=40, blend=0.15)      # looks up: watches the bar sweep
    data.look_at(CAM, T_SHOW - 0.2, max_yaw=45, blend=0.18)
    data.expression("determined", 0.0, T_S0)
    data.expression("surprised", T_S0 + 0.3, T_SHOW - 0.3, blend=0.12)
    data.expression("worried", T_SHOW - 0.2, DUR + 1.0, blend=0.15)
    data.finish()
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24, fstop=7.0)
    camera_path(cam, lambda t: (CAM + (LOOK - CAM).normalized() * 0.06 * W(t, T_SHOW, 1.5), LOOK, Vector((0.1, 0.2, 0.7))))
    allj = [j for row in jars for j in row]
    return dict(lanes=[], kiosks=[], place="market_alley", light=light, data=data, rest=1, grips=("lever grip",),
                conseq=[("he hauls the lever, the scanner's red bar sweeps the tiers and two more jars in every seven spin red: three in seven, almost half",
                         lambda: meshes([j["root"] for j in allj] + [car]), T_S0, DUR, {"hero": True, "moves": lambda: meshes([car])}),
                        ("the lever comes down in his hands", lambda: meshes([arm]), T_PULL0, T_PULL1 + 0.3)])
