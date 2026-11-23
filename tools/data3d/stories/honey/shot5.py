# ---------------------------------------------------------------- shot 5: the fakes keep coming (the alley)
"""5 THE FAKES KEEP COMING. The alley behind the cheap stall: real cobbles, brick walls, a back door, crates, bins,
a drainpipe, and a big blue drum stencilled SUGAR SYRUP on a stand, its tap filling PURE HONEY jars on a crate. The
lens tracks him in: he catches the tap filling another fake jar, grabs it and turns it upside down and the syrup
gushes out like water all over the cobbles; then he turns his own jar upside down beside it and his honey does not
budge; he holds both out to us, one empty, one full."""

S5_P = Vector((0.0, 0.0, 0.0))                  # where he stops at the crate
S5_YAW = math.radians(48)
S5_FW = Vector((math.sin(S5_YAW), -math.cos(S5_YAW), 0)); S5_OUT = Vector((math.cos(S5_YAW), math.sin(S5_YAW), 0))
S5_CT = 0.4                                      # the crate stack's top
S5_JAR = S5_P + S5_FW * 0.215 + S5_OUT * 0.06 + Vector((0, 0, S5_CT))   # the jar under the tap
S5_DRUM = S5_JAR + Vector((0.17, 0.31, 0.0))       # the drum's centre (its base on the stand at the crate's height)
S5_DR, S5_DH = 0.13, 0.38


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
    K.box("alley bed", (0, 0.5, -0.008), (8, 8, 0.012), K.mat("cobble joint", "#6A6258", rough=0.95), bev=0)
    stones = [hw_noise(f"cobble {k}", a, b, scale=18, rough=0.75, bump=0.6) for k, (a, b) in
              enumerate((("#7E7A72", "#9A958A"), ("#8C8070", "#A89A86"), ("#6E6A64", "#8A857C"), ("#9A8E7C", "#B2A690")))]
    for i in range(34):
        for j in range(21):
            x = -1.3 + i * 0.075 + (0.037 if j % 2 else 0.0) + rnd.uniform(-0.005, 0.005)
            y = -0.95 + j * 0.066 + rnd.uniform(-0.004, 0.004)
            K.sph("cobble", (x, y, -0.012), 1.0, rnd.choice(stones), scale=(0.04 + rnd.uniform(-0.003, 0.003), 0.035 + rnd.uniform(-0.003, 0.003), 0.012), seg=14, ring=7)
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
    sack = hw_noise("sack", "#B8A07A", "#CDB894", scale=20, rough=0.95, bump=0.6)
    for k, (x, y) in enumerate(((0.7, 0.4), (0.82, 0.32))):
        K.sph("sugar sack", (x, y, 0.15), 1.0, sack, scale=(0.13, 0.11, 0.16))
        K.text("sack print", "SUGAR", (x, y - 0.112, 0.16), 0.04, (math.pi / 2, 0, 0), K.mat("sack ink", "#3A3A6A", rough=0.8))
    for k in range(3):
        s5_crate(f"empty crate {k}", (-0.2 + 0.02 * k, 0.42, 0.22 * k), (0.28, 0.2, 0.22), rnd)
    K.cyl("broom handle", (-0.82, 0.5, 0.6), 0.012, 1.2, hw_wood("broom", "#A07A50", "#B89068"), rot=(0.12, 0, 0), v=12)
    # the drum of SUGAR SYRUP on its stand, its tap over the crate, and the crate stack with the jars it fills
    blue = K.mat("drum blue", "#1E5AA8", rough=0.35)
    K.cyl("drum", (S5_DRUM.x, S5_DRUM.y, S5_CT + S5_DH / 2), S5_DR, S5_DH, blue, v=40, bev=0.015)
    for z in (0.08, S5_DH - 0.08):
        K.cyl("drum rib", (S5_DRUM.x, S5_DRUM.y, S5_CT + z), S5_DR + 0.006, 0.02, blue, v=40, bev=0.006)
    K.cyl("drum cap", (S5_DRUM.x + 0.05, S5_DRUM.y, S5_CT + S5_DH + 0.01), 0.03, 0.025, K.mat("cap white", "#EEEEEE", rough=0.4), v=16)
    tv = (S5_JAR - S5_DRUM); tv.z = 0; ang = math.atan2(-tv.x, tv.y)
    K.text("drum stencil", "SUGAR\nSYRUP", (S5_DRUM.x + tv.normalized().x * (S5_DR + 0.003), S5_DRUM.y + tv.normalized().y * (S5_DR + 0.003), S5_CT + 0.24),
           0.05, (math.pi / 2, 0, ang + math.pi), K.mat("stencil white", "#F4F4F0", rough=0.6))
    s5_crate("drum stand", (S5_DRUM.x, S5_DRUM.y, 0.0), (0.3, 0.3, S5_CT), rnd)
    s5_crate("jar crate", (S5_JAR.x + 0.06, S5_JAR.y - 0.02, 0.0), (0.27, 0.23, S5_CT), rnd)
    steel = K.mat("tap steel", "#B0B4B8", rough=0.25, metal=0.9)
    spout = S5_JAR + Vector((0, 0, 0.13))
    K.capsule("tap pipe", S5_DRUM + Vector((0, 0, S5_CT + 0.2)) + tv.normalized() * (S5_DR - 0.01) - Vector((0, 0, S5_CT)), spout + Vector((0, 0, 0.02)), 0.012, steel)
    K.cyl("tap spout", tuple(spout), 0.012, 0.04, steel, v=16)
    K.box("tap handle", tuple(spout + Vector((0, 0, 0.045))), (0.05, 0.012, 0.012), K.mat("tap red", "#C8261E", rough=0.4), bev=0.003)
    return lambda: village_light(sun_elev=50, sun_az=-25, sun=3.2, sky=0.3)


def shot5():
    """THE FAKES KEEP COMING. The lens tracks him in to the crate: he catches the SUGAR SYRUP tap filling another
    PURE HONEY jar, grabs it and turns it upside down and the syrup gushes out like water onto the cobbles; he turns
    his own jar upside down beside it and his honey does not budge; he holds both out to us, one empty, one full."""
    T_STOP = 0.85                                 # he walks in
    T_GRAB = 0.3 * DUR                           # grabs the fake jar off the crate ...
    T_INV = T_GRAB + 0.4                         # ... and turns it upside down
    T_GUSH = 0.45 * DUR                          # it gushes out like water
    T_OWN = 0.65 * DUR                           # his own jar upside down: it does not budge
    T_SHOW = 0.85 * DUR                          # both out to us
    light = place_market_alley()
    fake = jar("fake jar", tuple(S5_JAR), r=0.048, h=0.12, fill=0.9, honey_col="#F2C35A", label="PURE HONEY")
    mine = jar("his jar", (0, 0, 0), r=0.062, h=0.15, fill=0.9, honey_col="#E49A1E", label="1 lb", glow=0.5)
    for j in (fake, mine):
        bpy.data.objects[("fake jar" if j is fake else "his jar") + " lid"].hide_render = True   # lids off: open jars
    rnd = hw_random.Random(3)
    for k, off in enumerate((Vector((0.1, -0.07, 0)), Vector((0.13, 0.04, 0)))):
        jar(f"filled fake {k}", tuple(S5_JAR + off), r=0.048, h=0.12, fill=0.9, honey_col="#F2C35A", label="PURE HONEY", yaw=math.radians(rnd.uniform(-15, 15)))
    for k in range(3):                           # and a tray of them waiting on the stack by the door
        jar(f"tray fake {k}", (-0.13 + 0.09 * k, 0.4, 0.66), r=0.04, h=0.1, fill=0.9, honey_col="#F2C35A", label="PURE HONEY")
    data = load_data()
    P0 = S5_P + Vector((-0.17, 0.08, 0.0))
    data.place(P0.x, P0.y, math.degrees(math.atan2((S5_P - P0).normalized().x, -(S5_P - P0).normalized().y)))
    hat = bee_hat(data)
    W = hw_win
    data.walk_to(Vector((S5_P.x, S5_P.y, 0)), 0.0, T_STOP)
    sc.frame_set(F(T_STOP)); bpy.context.view_layer.update()
    y_walk = data.arm.rotation_euler.z
    def body(t):
        p = S5_P.copy()
        p += -S5_FW * 0.06 * W(t, T_GRAB + 0.05, 0.4) - Vector((0, 0, 0)) # steps back off the crate with it
        p.z += 0.025 * hw_kick(t - T_GRAB - 0.1, 0.12)
        p += -S5_FW * 0.05 * hw_kick(t - T_GUSH - 0.1, 0.26)                                   # rocks back from the gush
        p.z += 0.03 * hw_kick(t - T_GUSH - 0.05, 0.12)
        p += -S5_FW * 0.0 * W(t, T_OWN - 0.6, 0.4)                                            # steps back for room
        p.z += 0.02 * math.sin(2 * math.pi * (t - T_OWN - 0.15) / 0.3) * W(t, T_OWN + 0.05, 0.2) * (1 - W(t, T_OWN + 0.65, 0.25))   # bounces with the shake
        p += S5_FW * 0.07 * W(t, T_SHOW - 0.3, 0.45)                                            # and comes to us
        p.z += 0.03 * hw_kick(t - T_SHOW - 0.2, 0.13)
        yaw = y_walk + (S5_YAW - y_walk) * W(t, T_STOP - 0.05, 0.4) - math.radians(38) * W(t, T_OWN - 0.6, 0.6)
        return p, yaw
    for f in range(F(T_STOP), NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (6 * math.sin(2 * math.pi * (t - T_OWN - 0.15) / 0.3) * W(t, T_OWN + 0.05, 0.2) * (1 - W(t, T_OWN + 0.65, 0.25)) - 8 * hw_kick(t - T_GUSH - 0.1, 0.26)
                                      + 6 * W(t, T_OWN - 0.3, 0.3) * (1 - W(t, T_SHOW - 0.5, 0.5)) - 5 * W(t, T_SHOW - 0.1, 0.5), 0, 0), 0, DUR + 0.4)
    sc.frame_set(F(T_STOP)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: (acts._shoulder(data, s) - Vector(data.arm.location)).dot(S5_OUT))
    left, right = sides                          # right: the crate's side (the fake); left: his own jar
    # ---- the fake jar: under the tap, filling; in his right hand from T_GRAB; upside down; empty; upright to us
    fr, fs, fh = fake["root"], fake["spin"], fake["honey"]
    def hold(sd, rel):
        return hw_hand(data, sd, rel)
    rk = [(0.0, (0.06, 0.1, -0.16)), (T_STOP, (0.07, 0.1, -0.15)), (T_GRAB - 0.35, (0.08, 0.06, -0.08)),
          (T_GRAB, hw_rel(data, right, T_GRAB, S5_JAR + Vector((0, 0, 0.06)))),
          (T_INV + 0.2, (0.11, 0.07, -0.02)), (T_GUSH + 0.5, (0.11, 0.09, -0.03)), (T_OWN - 0.2, (0.1, 0.12, -0.03)),
          (T_SHOW, (0.13, 0.08, -0.02)), (DUR + 0.3, (0.13, 0.08, -0.01))]
    lk = [(0.0, (0.06, 0.1, -0.14)), (T_STOP, (0.07, 0.1, -0.14)), (T_GUSH, (0.07, 0.11, -0.12)), (T_OWN - 0.45, (0.1, 0.08, -0.05)),
          (T_OWN - 0.1, (0.11, 0.06, -0.02)), (T_OWN + 0.15, (0.11, 0.06, 0.0)),
          (T_OWN + 0.3, (0.11, 0.08, 0.03)), (T_OWN + 0.45, (0.11, 0.08, -0.02)), (T_OWN + 0.6, (0.11, 0.08, 0.02)),   # shakes it: nothing
          (T_OWN + 0.8, (0.115, 0.075, 0.0)), (T_SHOW + 0.45, (0.13, 0.06, -0.04)), (DUR + 0.3, (0.13, 0.06, -0.04))]
    rh, lh_ = hold(right, rk), hold(left, lk)
    data.reach(right, rh, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(left, lh_, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    # ---- the face
    LENS = lambda t: Vector((-0.55 + 0.45 * ease(t / DUR), -1.25 + 0.2 * W(t, T_OWN, 1.0), 0.62))
    data.look_at(S5_JAR + Vector((0, 0, 0.1)), 0.0, max_yaw=45, max_pitch=35, blend=0.0)
    data.look_at(LENS(T_STOP), T_STOP + 0.05, max_yaw=45, blend=0.15)                          # a look at us: see that?
    data.look_at(S5_JAR + Vector((0, 0, 0.05)), T_GRAB - 0.4, max_yaw=45, max_pitch=35, blend=0.15)
    data.look_at(S5_JAR + Vector((0, -0.05, 0.1)), T_GUSH - 0.1, max_yaw=45, max_pitch=40, blend=0.12)
    data.look_at(LENS(T_OWN - 0.4), T_OWN - 0.5, max_yaw=45, blend=0.18)
    data.look_at(LENS(DUR), T_SHOW - 0.2, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_GRAB - 0.1)
    data.expression("determined", T_GRAB, T_GUSH - 0.05, blend=0.12)
    data.expression("surprised", T_GUSH, T_OWN - 0.3, blend=0.1)
    data.expression("pleased", T_OWN - 0.2, T_SHOW - 0.1, blend=0.15)
    data.expression("happy", T_SHOW, DUR + 1.0, blend=0.18)
    data.finish()
    # jars in his hands: the jar's middle in his fist, upright, upside down, upright again
    def carry(j, sd, t0, flip0, flip1, back0, back1, rest_at=None):
        root = j["root"]; hh = j["h"]
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < t0 and rest_at is not None:
                root.location = rest_at; root.rotation_euler = (0, 0, 0)
            else:
                sc.frame_set(f); bpy.context.view_layer.update()
                M = data.arm.matrix_world @ data.pb["hand." + sd].matrix
                fist = M.translation + (M.to_3x3() @ Vector((0, 0.045, 0)))
                yw = data.arm.rotation_euler.z
                a = math.pi * (W(t, flip0, 0.35) - W(t, back0, 0.4)) if back0 else math.pi * W(t, flip0, 0.35)
                Rm = Euler((0, 0, yw)).to_matrix() @ Euler((0, a, 0)).to_matrix()
                root.location = fist - Rm @ Vector((0, 0, hh / 2)); root.rotation_euler = Rm.to_euler()
                if rest_at is not None:
                    u = W(t, t0, 0.15); root.location = Vector(rest_at).lerp(root.location, u)
            root.keyframe_insert("location", frame=f); root.keyframe_insert("rotation_euler", frame=f)
    carry(fake, right, T_GRAB, T_INV - 0.05, None, T_SHOW - 0.5, None, rest_at=tuple(S5_JAR))
    carry(mine, left, 0.0, T_OWN - 0.35, None, T_SHOW - 0.4, None)
    # the fake fills under the tap, then (upside down) runs out of its mouth in a gush onto the cobbles
    hz = fake["hz"]
    for t, s_, z in ((0.0, 0.35, None), (T_GRAB - 0.15, 1.0, None), (T_GUSH, 1.0, "top"), (T_GUSH + 0.75, 0.02, "top")):
        fh.scale = (1, 1, s_); fh.location.z = (hz * s_ / 2 + 0.002) if z is None else (hz - hz * s_ / 2 + 0.002)
        fh.keyframe_insert("scale", frame=F(t)); fh.keyframe_insert("location", frame=F(t))
    syrup = hw_honey("cheap syrup", "#F4C65E", glow=0.6, clear=0.75)
    tap = K.cyl("tap stream", (0, 0, 0), 1.0, 1.0, syrup, v=12, bev=0)
    gush = K.cyl("gush", (0, 0, 0), 1.0, 1.0, syrup, v=16, bev=0)
    pud = K.cyl("syrup puddle", (0, 0, 0), 1.0, 0.004, hw_honey("puddle syrup", "#E8B44C", glow=0.3, clear=0.5), v=40, bev=0.0015)
    spout = S5_JAR + Vector((0, 0, 0.13)); land = Vector((0, 0, 0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        on = 1.0 - W(t, T_GRAB - 0.2, 0.15)
        top = fake["root"].matrix_world @ Vector((0, 0, hz)) if t < T_GRAB else spout - Vector((0, 0, 0.06))
        a, b = spout, top
        tap.location = (a + b) / 2; r = 0.006 * on + 1e-4; tap.scale = (r, r, max(1e-3, (a - b).length))
        for k in ("location", "scale"): tap.keyframe_insert(k, frame=f)
        mouth = fake["root"].matrix_world @ Vector((0, 0, fake["h"]))
        if f == F(T_GUSH): land = Vector((mouth.x, mouth.y, 0.0))
        g = W(t, T_GUSH, 0.12) * (1 - W(t, T_GUSH + 0.65, 0.2))
        gb = Vector((mouth.x, mouth.y, 0.0)); gl = max(1e-3, mouth.z)
        gush.location = (mouth + gb) / 2; rr = 0.018 * g + 1e-4; gush.scale = (rr, rr, gl)
        for k in ("location", "scale"): gush.keyframe_insert(k, frame=f)
        pr = 0.22 * W(t, T_GUSH + 0.05, 0.8) + 1e-3
        pud.location = (land.x if t >= T_GUSH else mouth.x, land.y if t >= T_GUSH else mouth.y, 0.003); pud.scale = (pr, pr * 0.8, 1)
        for k in ("location", "scale"): pud.keyframe_insert(k, frame=f)
    # splashes where it lands
    drops = []
    for k in range(12):
        d = K.sph("syrup splash", (0, 0, 0), 1.0, syrup, seg=10, ring=6); drops.append(d)
        th = 2 * math.pi * k / 12 + rnd.uniform(-0.2, 0.2); sp = rnd.uniform(0.25, 0.5); t0 = T_GUSH + 0.05 + rnd.uniform(0, 0.4)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - t0) / 0.35
            if 0 <= u <= 1:
                d.location = land + Vector((math.cos(th) * sp * 0.25 * u, math.sin(th) * sp * 0.25 * u, 0.12 * math.sin(math.pi * u) + 0.005)); s_ = 0.01
            else:
                d.location = land; s_ = 1e-4
            d.scale = (s_, s_, s_); d.keyframe_insert("location", frame=f); d.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(LENS(0)), tuple(S5_P + Vector((0.0, 0.0, 0.42))), lens=30, fstop=7.0)
    camera_path(cam, lambda t: (LENS(t), Vector((-0.12 + 0.2 * ease(t / DUR), 0.0, 0.42)) + S5_FW * 0.05 * W(t, T_OWN, 1.0), S5_P + Vector((0, 0, 0.5))))
    return dict(lanes=[], kiosks=[], place="market_alley", light=light, data=data, rest=1, grips=("fake jar", "his jar"),
                conseq=[("the fake PURE HONEY jar, upside down, gushes out like water onto the cobbles", lambda: meshes([fake["root"], gush, pud]), T_GUSH, T_GUSH + 0.8, {"hero": True}),
                        ("the SUGAR SYRUP drum's tap fills another PURE HONEY jar", lambda: meshes([fake["root"], tap]) + [o for o in bpy.data.objects if o.name.startswith(("drum", "tap"))], 0.1, T_GRAB),
                        ("his own jar upside down: the honey does not budge", lambda: meshes([mine["root"]]), T_OWN - 0.1, T_SHOW),
                        ("one empty, one full, held out to us", lambda: meshes([mine["root"], fake["root"]]), T_SHOW - 0.3, DUR)])
