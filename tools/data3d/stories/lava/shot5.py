"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?"

The harbour quay at dawn: fishing boats at the quay, the town on the slope above it, the earth wall curving round
above the town, black lava spread up to the town's edge where three houses still burn. The lens is low on the quay. He
walks up the quay to his own house by the water carrying a lit lantern and hangs it on the hook of the post by his door;
it swings, glowing; across the dark town a few windows light up, one here, one there, only a handful; he turns to us
and spreads his hands wide: would you?"""

S5_HOOK = Vector((0.2, 1.1, 0.5))       # the hook's tip, on the post by his door (pointing -X, toward where he comes from)
S5_EDGE_X = -2.2                        # the quay's water edge (x)


S5_BASIN = (-4.6, -0.25, 2.5, 7.4)     # the boat basin cut into the quay (x0, x1, y0, y1): water between him and the town


def s5_water(x, y):
    """True where the harbour's water is: the basin in front of the town, and the open harbour off the quay's edge"""
    x0, x1, y0, y1 = S5_BASIN
    return (x0 - 30 < x < x1 and y0 < y < y1) or (x < S5_EDGE_X and y < y0)


def s5_slope_z(x, y):
    """the quay flat, the boat basin sunk in it, the town's slope rising behind it, the lava field on the right"""
    if s5_water(x, y): return -1.2
    z = 0.0
    if y > 4.0: z += 0.3 * (min(y, 15.0) - 4.0)          # the town climbs the hill behind the harbour, row over row
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 4.0 else 0)
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
    fm = lw_fire_vol("house fire", density=4.0, strength=45.0, scale=2.4)        # fire as a VOLUME, not cards
    tongues = []
    for k in range(4):                                     # the roof is burning through: one big blaze and its tongues
        x = loc[0] + (0.0 if k == 0 else rnd.uniform(-0.5, 0.5)) * size; y = loc[1] + (0.0 if k == 0 else rnd.uniform(-0.25, 0.25)) * size
        r = (0.55 if k == 0 else 0.3) * size
        o = K.sph(f"{name} flame {k}", (x, y, loc[2] + 0.3 * size + (0.25 if k == 0 else 0.0) * size), r, fm, scale=(0.9, 0.8, 1.8), seg=14, ring=10)
        o.visible_shadow = False
        tongues.append(o)
    ash = lw_smoke_mat("fire smoke", density=1.4, col=(0.2, 0.2, 0.21))
    smoke = [lw_puff(f"{name} smoke {k}", (loc[0] + rnd.uniform(-0.2, 0.2) - 0.3 * k, loc[1] + 0.2 * k, loc[2] + 0.9 * size + 0.6 * k * size), (0.3 + 0.16 * k) * size, ash)
             for k in range(5)]
    L = lw_point(f"{name} fire light", (loc[0], loc[1] - 0.6, loc[2] + 0.6 * size), 900.0 * size, col=(1.0, 0.45, 0.15), r=0.4)
    return tongues, smoke, L


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, the town on the slope above, the earth wall round it, the black lava at the edge of town
    and three houses there still burning under their smoke."""
    rnd = lw_random.Random(61)
    lw_grid("town slope", -24, 24, 1.2, 40, 192, 120, s5_slope_z, lava_field_mat())          # the town's land, the basin sunk in it
    stone = lw_noise("harbour stone", "#4E4A46", "#6E6862", scale=9, rough=0.9, bump=0.8)
    x0, x1, y0, y1 = S5_BASIN
    for k in range(12):                                    # the basin's stone walls: its town side climbs with the slope
        y = y0 + (y1 - y0) * (k + 0.5) / 12; top = s5_slope_z(x1 + 0.3, y)
        K.box("harbour basin wall", (x1 + 0.12, y, (top - 1.2) / 2), (0.25, (y1 - y0) / 12 + 0.02, top + 1.2), stone, bev=0.01)
    K.box("harbour basin wall", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.1, -0.6), (x1 - S5_EDGE_X + 0.2, 0.25, 1.24), stone, bev=0.01)
    top = s5_slope_z(x1 + 0.3, y1 + 0.3)
    K.box("harbour head wall", ((x0 - 30 + x1) / 2, y1 + 0.12, (top - 1.2) / 2), (x1 - x0 + 30, 0.25, top + 1.2), stone, bev=0.01)
    K.box("quay concrete", (3.0, -2.0, -0.128), (10.4, 7.0, 0.24), lw_noise("quay concrete", "#8A8782", "#A5A29B", scale=10, rough=0.85, bump=0.4), bev=0.02)
    edge = K.mat("quay edge paint", "#D9B32E", rough=0.6)
    K.box("quay edge", (S5_EDGE_X + 0.1, -2.0, 0.03), (0.2, 7.0, 0.06), edge, bev=0.01)
    K.box("quay edge", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.12, 0.03), (x1 - S5_EDGE_X, 0.2, 0.06), edge, bev=0.01)
    for k in range(4):
        K.cyl("quay bollard", (S5_EDGE_X + 0.3 + 0.55 * k, y0 - 0.35, 0.1), 0.07, 0.2, lw_metal("bollard", "#2E3033"), v=16)
    water = bpy.data.materials.new("harbour water"); water.use_nodes = True; wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (*K.lin("#1E3440"), 1); wb.inputs["Roughness"].default_value = 0.06
    wt = water.node_tree; nz = wt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; bp = wt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    wt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); wt.links.new(bp.outputs["Normal"], wb.inputs["Normal"])
    K.box("harbour water", (-14, 0, -0.45), (24, 60, 0.02), water, bev=0)
    # fishing boats moored in the basin, built from their parts: hull with a raked bow, rubbing strake, deck,
    # wheelhouse with its windows and roof, mast and boom, fenders over the side
    hull_cols = ("#2E5E8A", "#C33A2A", "#E9E4D6", "#2E7A5A")
    white = lw_paint("wheelhouse white", "#EDEBE4", rough=0.4); glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    steel = lw_metal("mast steel", "#8A8E92"); deck = lw_noise("boat deck", "#6A5A48", "#8A7860", scale=14, rough=0.8, stretch=(1, 6, 1))
    fend = K.mat("fender", "#1C1C1E", rough=0.6)
    for k, (x, y) in enumerate(((-0.95, 4.0), (-1.3, 6.2), (-2.6, 4.6), (-3.6, 6.3))):
        c = hull_cols[k]; hm = lw_paint(f"hull {c}", c, rough=0.4)
        K.box(f"fishing boat {k} hull", (x, y, -0.3), (1.0, 2.2, 0.5), hm, bev=0.14)
        bow = K.box(f"fishing boat {k} bow", (x, y + 1.15, -0.22), (0.7, 0.7, 0.5), hm, bev=0.12); bow.rotation_euler = (0, 0, math.radians(45))
        K.box(f"fishing boat {k} strake", (x, y, -0.06), (1.04, 2.24, 0.05), K.mat("strake black", "#1A1A1A", rough=0.5), bev=0.02)
        K.box(f"fishing boat {k} deck", (x, y, -0.04), (0.9, 2.1, 0.03), deck, bev=0.01)
        K.box(f"fishing boat {k} wheelhouse", (x, y - 0.45, 0.25), (0.62, 0.65, 0.55), white, bev=0.04)
        K.box(f"fishing boat {k} wheelhouse roof", (x, y - 0.45, 0.55), (0.72, 0.75, 0.05), hm, bev=0.015)
        for wx in (-0.16, 0.16):
            K.box(f"fishing boat {k} window", (x + wx, y - 0.12, 0.35), (0.24, 0.02, 0.16), glass, bev=0.0)
        K.cyl(f"fishing boat {k} mast", (x, y + 0.35, 0.75), 0.022, 1.5, steel, v=10)
        K.cyl(f"fishing boat {k} boom", (x, y + 0.75, 0.6), 0.015, 0.8, steel, rot=(math.radians(70), 0, 0), v=8)
        for j in range(3):
            K.cyl(f"fishing boat {k} fender", (x + 0.53, y - 0.6 + 0.6 * j, -0.2), 0.05, 0.18, fend, v=10)
    home = town_house("his town house", (3.0, 3.2, 0.0), yaw=0.0, w=2.0, d=1.6, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    wood = lw_noise("post wood", "#5A4632", "#7A6248", scale=12, rough=0.8, stretch=(1, 1, 8))
    paint = K.mat("post paint", "#EDEAE2", rough=0.5); iron = lw_metal("hook iron", "#2E3033")
    K.box("lantern post", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.42), (0.09, 0.09, 0.84), paint, bev=0.01)
    K.box("lantern post cap", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.855), (0.13, 0.13, 0.03), paint, bev=0.008)
    K.box("lantern post foot", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.03), (0.16, 0.16, 0.06), K.mat("post foot", "#6E6B66", rough=0.8), bev=0.01)
    K.box("lantern hook arm", (S5_HOOK.x + 0.06, S5_HOOK.y, S5_HOOK.z + 0.05), (0.2, 0.025, 0.025), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x + 0.1, S5_HOOK.y, S5_HOOK.z - 0.02), (0.13, 0.018, 0.018), iron, bev=0.003).rotation_euler = (0, math.radians(-45), 0)
    hk = K.cyl("lantern hook", (S5_HOOK.x - 0.035, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x - 0.025, S5_HOOK.y, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, (x, y) in enumerate(((6.4, 3.0), (8.8, 3.4), (11.2, 4.0))):     # his neighbours along the quay, off to the right
        quay.append(town_house(f"quay house {k}", (x, y, 0.0), yaw=0.0, w=2.0, d=1.6, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], seed=50 + k))
    town = []
    spots = [(-4.8, 8.8), (-2.7, 8.6), (-2.4, 11.0), (-0.9, 12.6), (-7.0, 9.0), (-4.0, 12.0), (-2.0, 14.8), (0.9, 14.4), (-6.2, 11.6), (-5.6, 14.2)]
    for k, (x, y) in enumerate(spots):
        hs = town_house(f"town house up {k}", (x, y, s5_slope_z(x, y) - 0.05), yaw=rnd.uniform(-0.15, 0.15), w=rnd.uniform(1.8, 2.2), d=1.6,
                        roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=30 + k)
        town.append(hs)
    burning = []
    for k, (x, y) in enumerate(((-0.6, 8.6), (0.9, 9.6), (2.4, 10.8))):     # at the lava's edge: three in a row across the frame, countable
        z = s5_slope_z(x, y) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.3, 0.3), w=2.0, d=1.6, roof="#3A3230", wall="#6E655E", seed=40 + k)
        burning.append((hs, (x, y, z + 1.2)))
    lm = lava_mat("lava field fresh", heat=0.35, scale=2.5)
    out = [(0.4, 7.4), (12.9, 5.6), (14.9, 10.0), (12.9, 15.0), (3.6, 15.0), (3.4, 12.0), (1.9, 9.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.4, m=lm, seed=8, lumpy=0.2)
    c = flow.location.copy()                               # laid on the hill: tilted to its slope, its centre on the ground
    flow.rotation_euler.x = math.atan(0.3); flow.location.z = 0.3 * (c.y - 4.0) - 0.12
    wall = earth_wall("earth wall", [(x, 17.0 + 0.03 * x * x) for x in range(-26, 8, 2)], h=4.4, crest=1.4, base=8.5, seed=14)
    wall["root"].location.z = s5_slope_z(0.0, 16.0) - 0.3          # on the hilltop above the town

    def light():
        k = iceland_light(sun_elev=3, sun_az=-55, sun=1.6, sky=0.18, warm=(1.0, 0.62, 0.45), haze=1.6)      # first light: dim enough that a lit window reads
        lw_clouds(cover=0.7, scale=6.0)
        return k
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
    STAND = Vector((S5_HOOK.x - 0.2, S5_HOOK.y + 0.1, 0.0))               # facing +X, the hook in front of his near shoulder
    data.place(P0.x, P0.y, 90.0)
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.15, T_WALK1 - 0.15)
    # ---- the burning houses: the flames lick and flicker, the smoke climbs
    for hs, loc in P["burning"]:
        tongues, smoke, L = s5_fire(hs["root"].name, loc, 1.35, rnd)
        for k, o in enumerate(tongues):
            s0 = o.scale.copy(); ph = rnd.uniform(0, 6.28); hz = rnd.uniform(2.5, 4.5)
            for f in range(1, NF + 1, 2):
                t = (f - 1) / FPS; q = 1 + 0.3 * math.sin(2 * math.pi * hz * t + ph)
                o.scale = (s0.x * (0.9 + 0.1 * q), s0.y * (0.9 + 0.1 * q), s0.z * q); o.keyframe_insert("scale", frame=f)
        for k, o in enumerate(smoke):
            z0 = o.location.z
            for f in range(1, NF + 1, 3):
                t = (f - 1) / FPS; o.location.z = z0 + 0.35 * t; o.location.x += 0.0; o.keyframe_insert("location", frame=f)
        lw_flicker(bpy.data.materials["house fire"], DUR)
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = 900.0 * (1 + 0.25 * math.sin(2 * math.pi * 3.1 * t + rnd.uniform(0, 3))); L.data.keyframe_insert("energy", frame=f)
    # ---- a few windows light up across the dark town, one here, one there
    lit = []
    order = [(P["town"][1], 1, -0.07), (P["town"][7], 0, -0.02), (P["town"][2], 0, 0.03), (P["town"][0], 0, 0.08), (P["town"][6], 1, 0.13), (P["town"][3], 1, 0.18), (P["town"][5], 0, 0.23)]
    for hs, wi, frac in order:
        lit.append(s5_lit_pane(hs, min(wi, len(hs["windows"]) - 1), T_WIN + frac * DUR))
    lit_houses = [hs for hs, _w, _f in order]
    # ---- his body: the walk up the quay, the lift to the hook, a step back, the turn to us, the spread hands
    sc.frame_set(F(T_WALK1)); bpy.context.view_layer.update()
    YAW_H = math.radians(90)
    for f in range(F(T_WALK1 - 0.15) + 1, NF + 1):
        t = (f - 1) / FPS
        p = STAND.copy()
        p.z += 0.03 * W(t, T_HANG - 0.3, 0.25) * (1 - W(t, T_LET + 0.2, 0.3))                 # up on his toes to the hook
        p.x -= 0.05 * W(t, T_LET + 0.5, 0.5); p.y -= 0.1 * W(t, T_LET + 0.8, 0.45)   # a step back from it, and one toward us
        p.y -= 0.08 * W(t, T_ASK + 0.3, 0.7); p.z += 0.035 * lw_kick(t - T_ASK - 0.35, 0.22)   # and at the ask, a step to us and a shrug
        yaw = YAW_H - math.radians(35) * W(t, T_WIN - 0.2, 0.5) - math.radians(45) * W(t, T_TURN - 0.45, 0.4)
        data._kobj(t, loc=tuple(p), rot=yaw)
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
    # after the let-go: the lantern hand comes down slowly; his free hand waves up at the first window that lights,
    # comes down, then both spread wide to us
    AK = {carry: [(T_LET + 0.9, (0.07, 0.1, -0.07)), (T_ASK + 0.05, (0.07, 0.1, -0.08)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))],
          other: [(T_LET + 0.75, (0.06, 0.14, 0.03)), (T_LET + 1.0, (0.03, 0.16, 0.08)), (T_LET + 1.22, (0.03, 0.13, 0.09)), (T_LET + 1.44, (0.03, 0.16, 0.08)),
                  (T_ASK + 0.05, (0.08, 0.1, -0.06)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))]}
    down_fn = lw_hand(data, carry, AK[carry])
    def carry_path(t):                                       # ONE job for the lantern hand: carry, hang, then down slowly
        if t <= T_LET: return hand_path(t)
        return (hook_at(t) + Vector((0, 0, 0.005))).lerp(down_fn(t), W(t, T_LET, 0.9))
    data.reach(carry, carry_path, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
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
    data.reach(other, lw_hand(data, other, AK[other]), AK[other][0][0], DUR + 0.3, lead=0.6, back=None, elbow_out=0.4)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((0.2, -2.4, 0.6))
    data.look_at(Vector((3.0, 0.0, 0.4)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)
    data.look_at(S5_HOOK, T_WALK1 - 0.1, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(Vector((0.4, 9.0, 2.6)), T_LET + 0.2, max_yaw=30, max_pitch=30, blend=0.45)     # up the hill at the windows as he waves
    data.look_at(Vector((-0.8, 7.0, 2.0)), T_WIN + 0.12 * DUR, max_yaw=30, max_pitch=30, blend=0.45)
    data.look_at(LENS, T_TURN + 0.1, max_yaw=50, blend=0.45)
    data.expression("sad", 0.1, T_HANG - 0.1, blend=0.25)
    data.expression("determined", T_HANG, T_WIN, blend=0.2)
    data.expression("pleased", T_WIN + 0.1, T_ASK - 0.05, blend=0.25)
    data.expression("wry", T_ASK, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low on the quay, the town and its burning edge up the slope behind him
    CAM = Vector((0.05, -0.45, 0.8)); LOOK = Vector((0.15, 8.0, 1.8))      # low on the quay (solved with compose.Pinhole): him and the post low, the three burning houses in a row across the middle, the lit town round them
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=28.0, fstop=16.0)
    def cam_at(t):                                          # it pans with him up the quay to the post, then holds
        sc.frame_set(F(min(t, T_WALK1))); bpy.context.view_layer.update()
        pan = Vector((data.pos().x - STAND.x, 0.0, 0.0))
        return CAM + pan * 0.6 + Vector((0.0, 0.1, 0.0)) * ease(t / DUR), LOOK + pan, data.pos() + Vector((0, 0, 0.6))
    # CUT to the WIDE on his walk to his door (board round 2: "no harbour, no boats, no wall", "three burning houses
    # against many untouched ones"): high over the harbour water, the boats in the basin, him at his door on the quay,
    # the town on its hill, the three houses burning at the black lava's edge, the wall above, the handful of lights
    T_W0, T_W1 = 0.28 * DUR, T_HANG - 0.35          # on his walk up the quay, his face to this lens (KEYS: never his back)
    CW = Vector((2.0, -4.0, 3.5)); LW = Vector((-2.0, 8.5, 1.5))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.12, 0.2, -0.05)) * (t - T_W0), LW, Vector((0.0, 6.0, 1.5))), T_W0, T_W1, 28.0, 20.0)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])
