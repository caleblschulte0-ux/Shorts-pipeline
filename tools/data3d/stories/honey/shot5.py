# ---------------------------------------------------------------- shot 5: the fakes keep coming (the alley)
"""5 ALMOST HALF. The alley behind the stall, where the imports come in: real cobbles, brick walls, a back door,
bins, sacks, and a long plank of import jars on crates. He walks the row rolling the EU's new test roller along the
lids, and as it passes, almost half the jars spin round to a red SUSPECT label (shot 1 caught one in seven); at the
row's end he picks up the last red one and holds it out to us: what's in your jar?"""

S5_X0, S5_X1 = -0.5, 0.35                       # his walk along the row
S5_PY = -0.025                                   # his line along it
S5_ROW_Y = -0.22                                 # the row of import jars, on his left as he walks (+x)
S5_N = 7
S5_FAKES = (1, 3, 6)                             # 3 of 7: almost half, three times shot 1's one in seven
S5_JR, S5_JH = 0.055, 0.17
S5_RR = 0.03                                     # the roller's drum radius


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
    return lambda: village_light(sun_elev=50, sun_az=-25, sun=3.2, sky=0.3)


def s5_roller(name="test roller"):
    """the EU's new test roller: a red drum stamped EU TEST on a steel fork, a black grip. Built with the drum's axle
    along local X at the origin and the handle running up local +Z to the grip. Returns dict(root, spin)."""
    root = K.empty(name, (0, 0, 0))
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    red = K.mat("roller red", "#C8261E", rough=0.4)
    steel = K.mat("roller steel", "#B0B4B8", rough=0.25, metal=0.9)
    K.cyl(name + " drum", (0, 0, 0), S5_RR, 0.09, red, rot=(0, math.pi / 2, 0), v=32, bev=0.004, parent=spin)
    for k in range(6):                                       # ribs, so it reads as rolling
        a = 2 * math.pi * k / 6
        rb = K.box(name + " rib", (0, S5_RR * math.sin(a), S5_RR * math.cos(a)), (0.092, 0.007, 0.005),
                   K.mat("roller rib", "#F4F0E8", rough=0.5), bev=0.001, parent=spin)
        rb.rotation_euler = (-a, 0, 0)
    for s in (-1, 1):
        K.capsule(name + " fork", Vector((s * 0.04, 0, 0)), Vector((s * 0.02, 0, 0.05)), 0.004, steel, parent=root)
    shaft = K.empty(name + " shaft", (0, 0, 0), parent=root)          # scaled along z so the grip sits in his fist
    K.capsule(name + " stem", Vector((0, 0, 0.05)), Vector((0, 0, 0.1)), 0.005, steel, parent=shaft)
    K.cyl(name + " grip", (0, 0, 0.125), 0.011, 0.06, K.mat("roller grip", "#1E1E22", rough=0.7), v=16, bev=0.004, parent=shaft)
    hw_local(root)
    return dict(root=root, spin=spin, shaft=shaft)


def shot5():
    """ALMOST HALF. He walks the row of import jars rolling the EU's test roller along their lids; as it passes,
    almost half spin round to a red SUSPECT label; at the end he turns to us, picks up the last red one and holds it
    out to the lens: what's in your jar?"""
    W = hw_win
    T_W0, T_W1 = 0.2, 0.62 * DUR           # he walks the row, rolling
    T_TURN = T_W1 + 0.05                         # turns to us
    T_GRAB = T_W1 + 0.6                          # picks up the last red jar ...
    T_SHOW = T_GRAB + 0.55                       # ... and holds it out to us
    B = 0.15                                     # the plank's top: the jars stand on it
    LID = B + S5_JH + 0.016                      # their lids' top
    light = place_market_alley()
    rnd = hw_random.Random(5)
    wood = hw_wood("import plank", "#8A6A44", "#A8865A", scale=5)
    XS = [S5_X0 + 0.12 + (S5_X1 + 0.05 - S5_X0 - 0.12) * k / (S5_N - 1) for k in range(S5_N)]
    K.box("import plank", ((XS[0] + XS[-1]) / 2, S5_ROW_Y, B - 0.015), (XS[-1] - XS[0] + 0.14, 0.11, 0.03), wood, bev=0.004)
    for k, x in enumerate((XS[0] + 0.03, XS[-1] - 0.17, (XS[0] + XS[-1]) / 2 - 0.12)):
        s5_crate(f"import crate {k}", (x, S5_ROW_Y - 0.025, 0.0), (0.16, 0.08, B - 0.03), rnd)
    K.text("import stencil", "IMPORTS", ((XS[0] + XS[-1]) / 2, S5_ROW_Y - 0.057, B * 0.55), 0.05, (math.pi / 2, 0, 0), K.mat("stencil ink", "#2A2A2A", rough=0.8))
    jars = []
    for k, x in enumerate(XS):
        jars.append(jar(f"import jar {k}", (x, S5_ROW_Y, B), r=S5_JR, h=S5_JH, fill=0.9, honey_col="#E8A82A", glow=0.35, label="PURE HONEY",
                        back="SUSPECT" if k in S5_FAKES else None, yaw=math.radians(rnd.uniform(-8, 8))))
    last = jars[-1]
    data = load_data()
    data.place(S5_X0, S5_PY, 90.0)
    hat = bee_hat(data)
    data.walk_to(Vector((S5_X1, S5_PY, 0)), T_W0, T_W1)
    def yaw(t):
        return math.radians(90 - 70 * W(t, T_TURN, 0.45) - 16 * W(t, T_SHOW + 0.35, 0.5) + 16 * W(t, T_SHOW + 0.95, 0.5))
    def bx(t):
        return S5_X0 + (S5_X1 - S5_X0) * min(1.0, max(0.0, (t - T_W0) / (T_W1 - T_W0)))
    for f in range(F(T_W1) + 1, NF + 1):
        t = (f - 1) / FPS
        p = Vector((S5_X1, S5_PY, 0)) + Vector((0, -0.035, 0)) * W(t, T_GRAB - 0.5, 0.35) * (1 - W(t, T_SHOW, 0.4)) + Vector((-0.04, 0, 0)) * W(t, T_SHOW + 0.5, 0.3) + Vector((0.05, 0, 0)) * W(t, T_SHOW + 0.95, 0.3)
        z = 0.035 * hw_kick(t - T_TURN - 0.1, 0.13) + 0.04 * hw_kick(t - T_SHOW - 0.05, 0.14) + 0.05 * hw_kick(t - T_SHOW - 1.0, 0.14)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (8 * W(t, T_W0, 0.3) * (1 - W(t, T_W1, 0.3)) + 28 * W(t, T_GRAB - 0.4, 0.3) * (1 - W(t, T_GRAB + 0.05, 0.35))
                                      - 6 * W(t, T_SHOW, 0.4), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = ("R", "L") if acts._shoulder(data, "L").y > acts._shoulder(data, "R").y else ("L", "R")   # lf: the row's side (-y)
    # the roller hand: its fist over the lids for the walk, the drum on them, pressing with each stride
    def roll_fist(t):
        x = bx(t) + 0.12
        return Vector((x, S5_ROW_Y + 0.07, LID + S5_RR + 0.1 + 0.012 * math.sin(2 * math.pi * (t - T_W0) / 0.7)))
    rest_l = hw_hand(data, lf, [(0.0, (0.0, 0.05, -0.14)), (DUR + 0.3, (0.0, 0.05, -0.14))])
    down_l = hw_hand(data, lf, [(0.0, (0.12, 0.06, -0.03)), (T_W1 + 0.2, (0.12, 0.06, -0.03)), (T_GRAB, (0.09, 0.08, -0.06)), (T_SHOW + 0.3, (0.08, 0.08, -0.06)), (T_SHOW + 0.6, (0.13, 0.08, 0.0)),
                               (T_SHOW + 1.0, (0.12, 0.09, -0.02)), (T_SHOW + 1.3, (0.06, 0.1, -0.11)), (DUR + 0.3, (0.06, 0.1, -0.11))])     # waves the roller at it
    def lfn(t):
        a = 1.0; b = W(t, T_W1 - 0.3, 0.5)
        return rest_l(t).lerp(roll_fist(t), a).lerp(down_l(t), b)
    data.reach(lf, lfn, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.25)
    # the jar hand: hangs, then picks up the last jar and holds it out at the lens
    JMID = Vector(last["root"].location) + Vector((0, 0.0, S5_JH * 0.8))      # by its shoulder, under the lid
    grab = hw_rel(data, rt, T_GRAB, JMID)
    rk = [(0.0, (0.04, 0.08, -0.14)), (T_W1, (0.05, 0.08, -0.13)), (T_GRAB - 0.4, (0.12, 0.04, -0.04)), (T_GRAB - 0.15, (grab[0], grab[1], grab[2] + 0.07)), (T_GRAB, grab),
          (T_GRAB + 0.25, (max(grab[0], 0.14) + 0.02, grab[1], grab[2] + 0.06)), (T_SHOW, (0.15, 0.03, -0.05)), (T_SHOW + 0.45, (0.155, 0.04, -0.035)),
          (T_SHOW + 0.7, (0.155, 0.045, -0.012)), (T_SHOW + 1.05, (0.15, 0.04, -0.06)),        # shakes it at us
          (T_SHOW + 1.4, (0.155, 0.04, -0.03)), (DUR + 0.3, (0.155, 0.04, -0.03))]
    data.reach(rt, hw_hand(data, rt, rk), 0.0, DUR + 0.3, lead=0.08, back=None, elbow_out=0.35)
    # ---- the face
    CAM = Vector((0.62, -1.2, 0.72)); LOOK = Vector((-0.1, -0.1, 0.38))
    data.look_at(Vector((XS[3], S5_ROW_Y, LID)), 0.0, max_yaw=45, max_pitch=35, blend=0.0)
    data.look_at(CAM, T_W0 + 1.0, max_yaw=45, blend=0.15)                                 # a look at us mid-row: see?
    data.look_at(Vector((XS[-2], S5_ROW_Y, LID)), T_W0 + 1.6, max_yaw=45, max_pitch=35, blend=0.15)
    data.look_at(CAM, T_SHOW - 0.2, max_yaw=45, blend=0.18)
    data.expression("determined", 0.0, T_W0 + 0.9)
    data.expression("surprised", T_W0 + 1.0, T_W1 - 0.2, blend=0.12)
    data.expression("worried", T_W1 - 0.1, T_SHOW - 0.2, blend=0.15)
    data.expression("wry", T_SHOW - 0.1, DUR + 1.0, blend=0.18)
    data.finish()
    # ---- the roller: its drum on the lids under his fist, its grip in his fist; each fake spins red as it passes
    ro = s5_roller()
    flips = {}
    prev = None; ang = 0.0
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb["hand." + lf].matrix
        fist = M.translation + (M.to_3x3() @ Vector((0, 0.05, 0)))
        on = 1 - W(t, T_W1 + 0.05, 0.4)
        free = fist + data.forward() * 0.05 - Vector((0, 0, 0.1))           # off the lids: held out below the fist, clear of his coat
        D = free.lerp(Vector((fist.x, S5_ROW_Y, LID + S5_RR)), on)
        ax = (fist - D); L = max(0.03, ax.length); ax.normalize()
        xa = Vector((0, 1, 0)) - ax * ax.y; xa = xa.normalized() if xa.length > 1e-4 else Vector((1, 0, 0))
        from mathutils import Matrix
        R = Matrix((xa, ax.cross(xa), ax)).transposed()
        ro["root"].location = D; ro["root"].rotation_euler = R.to_euler()
        ro["shaft"].scale = (1, 1, L / 0.125)
        if prev is not None: ang += (D.x - prev.x) / S5_RR * on
        prev = D.copy()
        ro["spin"].rotation_euler = (-ang, 0, 0)
        for o, ks in ((ro["root"], ("location", "rotation_euler")), (ro["shaft"], ("scale",)), (ro["spin"], ("rotation_euler",))):
            for k in ks: o.keyframe_insert(k, frame=f)
        for k in S5_FAKES:
            if k not in flips and on > 0.9 and D.x >= XS[k]:
                flips[k] = t
    for k in S5_FAKES:
        jar_flip(jars[k], flips.get(k, T_W1 - 0.3), 0.3)
    # the last jar in his fist from T_GRAB: upright, its red label to us
    root = last["root"]; r0 = Vector(root.location); e0 = tuple(root.rotation_euler)
    for f in range(F(T_GRAB) - 1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb["hand." + rt].matrix
        fist = M.translation + (M.to_3x3() @ Vector((0, 0.045, 0)))
        u = W(t, T_GRAB, 0.12)
        root.location = r0.lerp(fist - Vector((0, 0, S5_JH * 0.8)), u)
        root.rotation_euler = (0, 0, e0[2] * (1 - u) + data.arm.rotation_euler.z * u)
        root.keyframe_insert("location", frame=f); root.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: in front of the row, tracking him along it; at the end it pushes in on the jar he holds out
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30, fstop=7.0)
    def lens(t):
        u = ease(t / DUR)
        w = (bx(t) - S5_X0) / (S5_X1 - S5_X0)
        push = W(t, T_GRAB, 1.4)                                   # and in on the jar he holds out
        c = CAM + Vector((0.2, -0.12, 0.0)) * w; l = LOOK + Vector((0.42, 0, 0.0)) * w - Vector((0.1, 0, 0)) * push
        return (c + (l - c).normalized() * 0.2 * push + Vector((0, 0, 0.03 * push)), l + Vector((0, 0, 0.04 * push)), Vector((bx(t), -0.1, 0.4)))
    camera_path(cam, lens)
    fakes = [jars[k] for k in S5_FAKES]
    return dict(lanes=[], kiosks=[], place="market_alley", light=light, data=data, rest=1, grips=("test roller", "import jar 6"),
                conseq=[("his roller passes along the lids and almost half the import jars spin round to a red SUSPECT", lambda: meshes([j["root"] for j in jars] + [ro["root"]]),
                         min(flips.values(), default=T_W0), T_W1 + 0.2, {"hero": True, "moves": lambda: meshes([ro["root"]])}),
                        ("the last red jar, held out to us: what's in your jar?", lambda: meshes([last["root"]]), T_GRAB, DUR)])
