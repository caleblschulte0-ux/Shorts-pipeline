"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?"

The harbour quay at dawn: fishing boats at the quay, the town on the slope above it, the earth wall curving round
above the town, black lava spread up to the town's edge where three houses still burn. The lens is low on the quay. He
walks up the quay to his own house by the water carrying a lit lantern and hangs it on the hook of the post by his door;
it swings, glowing; across the dark town a few windows light up, one here, one there, only a handful; he turns to us
and spreads his hands wide: would you?"""

S5_HOOK = Vector((0.2, 1.1, 0.5))       # the hook's tip, on the post by his door (pointing -X, toward where he comes from)
S5_EDGE_X = -2.2                        # the quay's water edge (x)


def s5_slope_z(x, y):
    """the quay flat, the town's slope rising behind it, the lava field on the right"""
    z = 0.0
    if y > 3.0: z += 0.16 * (y - 3.0)
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 3.0 else 0)
    return z


def s5_lantern():
    """a hurricane lantern: a tin base and cap, a glass globe with a warm flame glowing in it, a wire bail on top (its
    pivot at the bail's top, the lantern hanging below it)"""
    root = K.empty("lantern", (0, 0, 0))
    tin = lw_metal("lantern tin", "#B33A22", rough=0.4)
    K.cyl("lantern base", (0, 0, -0.17), 0.045, 0.03, tin, v=20, parent=root)
    K.cyl("lantern cap", (0, 0, -0.07), 0.04, 0.03, tin, v=20, parent=root)
    K.sph("lantern globe", (0, 0, -0.12), 0.042, lw_emit("lantern glow", "#FFB050", 3.0), scale=(1, 1, 1.25), seg=16, ring=10, parent=root)
    for sx in (-1, 1):
        K.cyl("lantern frame wire", (sx * 0.04, 0, -0.12), 0.004, 0.09, tin, v=6, parent=root)
        K.cyl("lantern bail", (sx * 0.03, 0, -0.03), 0.003, 0.07, lw_metal("bail wire", "#55595E"), rot=(0, sx * math.radians(30), 0), v=6, parent=root)
    K.cyl("lantern bail top", (0, 0, 0.0), 0.004, 0.035, lw_metal("bail wire", "#55595E"), rot=(0, math.pi / 2, 0), v=6, parent=root)
    lw_local(root)
    root.scale = (1.4, 1.4, 1.4)
    L = lw_point("lantern light", (0, 0, -0.12), 25.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.12)
    return root


def s5_lit_pane(house, k, t_on):
    """a window of a dark house that lights up at t_on (a pane in front of the dark one)"""
    p = house["windows"][k]
    lit = p.copy(); lit.data = p.data.copy(); bpy.context.collection.objects.link(lit)
    lit.name = p.name.replace("window pane", "window lit pane")
    lit.data.materials.clear(); lit.data.materials.append(lw_emit("window lit", "#FFC070", 2.5))
    lit.location.y -= 0.004
    lw_show([lit], t_on)
    return lit


def s5_fire(name, loc, size, rnd):
    """flames on a burning house: a cluster of hot tongues and a column of smoke billows over it"""
    fm = bpy.data.materials.get("house fire") or lw_emit("house fire", "#FF5000", 1.2)
    core = bpy.data.materials.get("house fire core") or lw_emit("house fire core", "#FF9020", 1.6)
    tongues = []
    for k in range(7):
        x = loc[0] + rnd.uniform(-0.45, 0.45) * size; y = loc[1] + rnd.uniform(-0.3, 0.3) * size
        o = K.sph(f"{name} flame {k}", (x, y, loc[2] + 0.25 * size), 0.18 * size, core if k % 3 == 0 else fm, scale=(0.8, 0.8, 2.2), seg=12, ring=8)
        tx = bpy.data.textures.new(f"{name} flame tex {k}", 'CLOUDS'); tx.noise_scale = 0.12 * size
        dm = o.modifiers.new("lick", 'DISPLACE'); dm.texture = tx; dm.strength = 0.12 * size
        tongues.append(o)
    ash = lw_smoke_mat("fire smoke", density=2.5, col=(0.22, 0.21, 0.21))
    smoke = [lw_puff(f"{name} smoke {k}", (loc[0] + rnd.uniform(-0.4, 0.4) - 0.5 * k, loc[1] + 0.3 * k, loc[2] + 1.0 * size + 1.3 * k * size), (0.8 + 0.4 * k) * size, ash)
             for k in range(6)]
    L = lw_point(f"{name} fire light", (loc[0], loc[1] - 0.6, loc[2] + 0.6 * size), 900.0 * size, col=(1.0, 0.45, 0.15), r=0.4)
    return tongues, smoke, L


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, the town on the slope above, the earth wall round it, the black lava at the edge of town
    and three houses there still burning under their smoke."""
    rnd = lw_random.Random(61)
    lw_grid("town slope", -24, 24, 1.2, 40, 80, 80, s5_slope_z, lava_field_mat())
    K.box("quay concrete", (3.0, -2.0, -0.12), (10.4, 7.0, 0.24), lw_noise("quay concrete", "#8A8782", "#A5A29B", scale=10, rough=0.85, bump=0.4), bev=0.02)
    K.box("quay edge", (S5_EDGE_X + 0.1, -2.0, 0.03), (0.2, 7.0, 0.06), K.mat("quay edge paint", "#D9B32E", rough=0.6), bev=0.01)
    for k in range(5):
        K.cyl("quay bollard", (S5_EDGE_X + 0.35, -4.0 + 1.6 * k, 0.1), 0.07, 0.2, lw_metal("bollard", "#2E3033"), v=16)
    water = bpy.data.materials.new("harbour water"); water.use_nodes = True; wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (*K.lin("#1E3440"), 1); wb.inputs["Roughness"].default_value = 0.06
    wt = water.node_tree; nz = wt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; bp = wt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    wt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); wt.links.new(bp.outputs["Normal"], wb.inputs["Normal"])
    K.box("harbour water", (-14, 0, -0.45), (24, 60, 0.02), water, bev=0)
    hull_cols = ("#2E5E8A", "#C33A2A", "#E9E4D6")
    for k, (y, c) in enumerate(zip((-1.2, 1.6, 4.6), hull_cols)):          # fishing boats moored along the quay
        x = S5_EDGE_X - 0.9
        K.box(f"fishing boat {k} hull", (x, y, -0.22), (1.1, 2.4, 0.55), lw_paint(f"hull {c}", c, rough=0.4), bev=0.18)
        K.box(f"fishing boat {k} wheelhouse", (x, y + 0.4, 0.3), (0.7, 0.7, 0.55), lw_paint("wheelhouse white", "#EDEBE4", rough=0.4), bev=0.05)
        K.box(f"fishing boat {k} window", (x, y + 0.04, 0.38), (0.55, 0.02, 0.18), K.mat("car glass", "#1E262C", rough=0.05, metal=0.3), bev=0.0)
        K.cyl(f"fishing boat {k} mast", (x, y - 0.5, 0.9), 0.025, 1.6, lw_metal("mast steel", "#8A8E92"), v=10)
    home = town_house("his town house", (1.45, 2.45, 0.0), yaw=0.0, w=2.0, d=1.6, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    wood = lw_noise("post wood", "#5A4632", "#7A6248", scale=12, rough=0.8, stretch=(1, 1, 8))
    K.box("lantern post", (S5_HOOK.x + 0.1, S5_HOOK.y, 0.36), (0.07, 0.07, 0.72), wood, bev=0.008)
    K.cyl("lantern hook", (S5_HOOK.x + 0.04, S5_HOOK.y, S5_HOOK.z + 0.01), 0.008, 0.09, lw_metal("hook iron", "#2E3033"), rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, (x, y) in enumerate(((4.0, 3.1), (6.4, 3.7), (8.8, 4.4))):     # his neighbours along the quay
        quay.append(town_house(f"quay house {k}", (x, y, 0.0), yaw=0.0, w=2.0, d=1.6, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], seed=50 + k))
    town = []
    spots = [(-3.6, 7.0), (-1.2, 8.4), (1.4, 9.2), (-4.4, 10.8), (3.4, 6.6), (-2.2, 12.6), (0.6, 12.0), (2.8, 11.2), (-6.0, 8.6), (5.2, 9.8)]
    for k, (x, y) in enumerate(spots):
        hs = town_house(f"town house up {k}", (x, y, s5_slope_z(x, y) - 0.05), yaw=rnd.uniform(-0.15, 0.15), w=rnd.uniform(1.8, 2.2), d=1.6,
                        roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=30 + k)
        town.append(hs)
    burning = []
    for k, (x, y) in enumerate(((7.4, 10.4), (9.6, 11.8), (11.4, 9.8))):     # at the lava's edge, right of the town
        z = s5_slope_z(x, y) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.3, 0.3), w=2.0, d=1.6, roof="#3A3230", wall="#6E655E", seed=40 + k)
        burning.append((hs, (x, y, z + 1.2)))
    lm = lava_mat("lava field fresh", heat=0.35, scale=2.5)
    out = [(6.0, 6.0), (16.0, 5.0), (22.0, 12.0), (20.0, 24.0), (8.0, 22.0), (6.2, 14.0), (5.8, 9.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.4, m=lm, seed=8, lumpy=0.2)
    flow.location.z = s5_slope_z(12, 12) - 0.1
    wall = earth_wall("earth wall", [(x, 17.0 + 0.03 * x * x) for x in range(-26, 8, 2)], h=4.4, crest=1.4, base=8.5, seed=14)

    def light():
        return iceland_light(sun_elev=6, sun_az=-55, sun=2.6, sky=0.4, warm=(1.0, 0.7, 0.5), haze=1.6)
    return dict(light=light, home=home, town=town, burning=burning, quay=quay)


def shot5():
    """THE QUAY AT DAWN. Low on the quay. He carries the lit lantern up the quay to the post by his door and hangs it; it
    swings, glowing; a few windows light up across the town, one here, one there; he turns to us and spreads his hands:
    would you?"""
    T_WALK1 = 0.4 * DUR; T_HANG = 0.48 * DUR; T_LET = T_HANG + 0.25
    T_WIN = 0.62 * DUR; T_TURN = 0.8 * DUR; T_ASK = 0.86 * DUR
    W = lw_win
    P = place_harbour_dawn()
    light = P["light"]
    data = load_data()
    rnd = lw_random.Random(7)
    P0 = Vector((S5_HOOK.x - 1.0, S5_HOOK.y + 0.1, 0.0))
    STAND = Vector((S5_HOOK.x - 0.17, S5_HOOK.y + 0.1, 0.0))               # facing +X, the hook in front of his near shoulder
    data.place(P0.x, P0.y, 90.0)
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.15, T_WALK1)
    # ---- the burning houses: the flames lick and flicker, the smoke climbs
    for hs, loc in P["burning"]:
        tongues, smoke, L = s5_fire(hs["root"].name, loc, 1.0, rnd)
        for k, o in enumerate(tongues):
            s0 = o.scale.copy(); ph = rnd.uniform(0, 6.28); hz = rnd.uniform(2.5, 4.5)
            for f in range(1, NF + 1, 2):
                t = (f - 1) / FPS; q = 1 + 0.3 * math.sin(2 * math.pi * hz * t + ph)
                o.scale = (s0.x * (0.9 + 0.1 * q), s0.y * (0.9 + 0.1 * q), s0.z * q); o.keyframe_insert("scale", frame=f)
        for k, o in enumerate(smoke):
            z0 = o.location.z
            for f in range(1, NF + 1, 3):
                t = (f - 1) / FPS; o.location.z = z0 + 0.35 * t; o.location.x += 0.0; o.keyframe_insert("location", frame=f)
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = 900.0 * (1 + 0.25 * math.sin(2 * math.pi * 3.1 * t + rnd.uniform(0, 3))); L.data.keyframe_insert("energy", frame=f)
    # ---- a few windows light up across the dark town, one here, one there
    lit = []
    order = [(P["quay"][0], 1, 0.0), (P["town"][4], 0, 0.06), (P["quay"][2], 0, 0.12), (P["town"][1], 1, 0.19), (P["quay"][1], 1, 0.26), (P["town"][7], 0, 0.31)]
    for hs, wi, frac in order:
        lit.append(s5_lit_pane(hs, min(wi, len(hs["windows"]) - 1), T_WIN + frac * DUR))
    lit_houses = [hs for hs, _w, _f in order if hs in P["quay"]]
    # ---- his body: the walk up the quay, the lift to the hook, a step back, the turn to us, the spread hands
    sc.frame_set(F(T_WALK1)); bpy.context.view_layer.update()
    YAW_H = math.radians(90)
    for f in range(F(T_WALK1) + 1, F(T_TURN) + 1):
        t = (f - 1) / FPS
        p = STAND.copy()
        p.z += 0.03 * W(t, T_HANG - 0.3, 0.25) * (1 - W(t, T_LET, 0.3))                 # up on his toes to the hook
        p.x -= 0.12 * W(t, T_LET + 0.15, 0.5)
        yaw = YAW_H - math.radians(35) * W(t, T_WIN - 0.2, 0.5) - math.radians(45) * W(t, T_TURN - 0.45, 0.4)
        data._kobj(t, loc=tuple(p), rot=yaw)
    data.walk_to((STAND.x - 0.2, STAND.y - 0.42), T_TURN, T_ASK + 0.3)          # he comes down the quay to us
    lw_layer(data, "spine", lambda t: (-8 * W(t, T_HANG - 0.3, 0.3) * (1 - W(t, T_LET, 0.3)) + 6 * W(t, T_LET + 0.1, 0.3) * (1 - W(t, T_TURN, 0.3))
                                       - 6 * W(t, T_ASK, 0.3), 0, 0), 0, DUR + 0.4)
    sc.frame_set(F(T_HANG)); bpy.context.view_layer.update()
    near = sorted("LR", key=lambda s_: acts._shoulder(data, s_).y)               # near[0]: the hand toward the lens
    carry, other = near[0], near[1]
    # the lantern: in his near hand from the start, up onto the hook, then on its own, swinging
    lan = s5_lantern()
    CK = [(0.0, (0.08, 0.1, -0.08)), (T_WALK1 - 0.2, (0.09, 0.1, -0.07))]
    carry_fn = lw_hand(data, carry, CK)
    hook_at = lambda t: S5_HOOK + Vector((0.0, 0.0, 0.0))
    def hand_path(t):
        if t <= T_WALK1 - 0.2: return carry_fn(t)
        u = W(t, T_WALK1 - 0.2, T_HANG - T_WALK1 + 0.2)
        return carry_fn(T_WALK1 - 0.2).lerp(hook_at(t) + Vector((0, 0, 0.005)), u)
    data.reach(carry, hand_path, 0.0, T_LET, lead=0.05, back=None, elbow_out=0.35)
    def swing(t):                                           # after the let-go: a damped swing about the hook
        s = t - T_LET
        return 0.0 if s <= 0 else math.radians(24) * math.exp(-s / 2.2) * math.sin(2 * math.pi * s / 0.9)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t <= T_LET:
            sc.frame_set(f); bpy.context.view_layer.update()
            lan.location = data.arm.matrix_world @ data.pb[f"hand.{carry}"].tail + Vector((0, 0, -0.02))
            lan.rotation_euler = (0, math.radians(10) * math.sin(2 * math.pi * t / 0.55) * (1 - W(t, T_WALK1 - 0.2, 0.3)), 0)
        else:
            lan.location = S5_HOOK; lan.rotation_euler = (0, swing(t), 0)
        lan.keyframe_insert("location", frame=f); lan.keyframe_insert("rotation_euler", frame=f)
    # after the let-go: the near hand comes down, then both hands spread wide to us
    AK = {carry: [(T_LET + 0.4, (0.08, 0.1, -0.08)), (T_TURN - 0.4, (0.1, 0.12, 0.0)), (T_TURN, (0.09, 0.11, -0.06)), (T_ASK + 0.05, (0.08, 0.1, -0.07)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))],
          other: [(T_ASK + 0.05, (0.07, 0.1, -0.09)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))]}
    data.reach(carry, lw_hand(data, carry, AK[carry]), AK[carry][0][0], DUR + 0.3, lead=0.4, back=None, elbow_out=0.35)
    data.reach(other, lw_hand(data, other, AK[other]), AK[other][0][0], DUR + 0.3, lead=0.5, back=None, elbow_out=0.35)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((0.2, -2.4, 0.6))
    data.look_at(Vector((3.0, 0.0, 0.4)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)
    data.look_at(S5_HOOK, T_WALK1 - 0.4, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(Vector((4.0, 2.2, 0.75)), T_WIN + 0.05, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((6.4, 2.8, 0.75)), T_WIN + 0.12 * DUR, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(LENS, T_TURN + 0.1, max_yaw=50, blend=0.3)
    data.expression("sad", 0.1, T_HANG - 0.1, blend=0.25)
    data.expression("determined", T_HANG, T_WIN, blend=0.2)
    data.expression("pleased", T_WIN + 0.1, T_ASK - 0.05, blend=0.25)
    data.expression("wry", T_ASK, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low on the quay, the town and its burning edge up the slope behind him
    CAM = Vector((0.3, -2.4, 0.5)); LOOK = Vector((2.0, 9.0, 1.1))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 20.0, face_at=(0.42, 0.5), height=0.34, t=T_HANG)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=20.0, fstop=11.0)
    camera_path(cam, lambda t: (CAM + Vector((0.05, 0.12, 0.0)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))))
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])
