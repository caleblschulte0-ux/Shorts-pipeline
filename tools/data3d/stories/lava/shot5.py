"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?"

The harbour quay at dawn: fishing boats at the quay, the town on the slope above it, the earth wall curving round
above the town, black lava spread up to the town's edge where three houses still burn. The lens is low on the quay. He
walks up the quay to his own house by the water carrying a lit lantern and hangs it on the hook of the post by his door;
it swings, glowing; across the dark town a few windows light up, one here, one there, only a handful; he turns to us
and spreads his hands wide: would you?"""

S5_HOOK = Vector((0.2, 1.1, 0.5))       # the hook's tip, on the post by his door (pointing -X, toward where he comes from)
S5_EDGE_X = -2.2                        # the quay's water edge (x)


S5_SLOPE = 0.45                         # the hill's rise per metre
S5_BASIN = (-4.6, -0.25, 2.5, 7.4)     # the boat basin cut into the quay (x0, x1, y0, y1): water between him and the town


def s5_water(x, y):
    """True where the harbour's water is: the basin in front of the town, and the open harbour off the quay's edge"""
    x0, x1, y0, y1 = S5_BASIN
    return (x0 - 30 < x < x1 and y0 < y < y1) or (x < S5_EDGE_X and y < y0)


def s5_slope_z(x, y):
    """the quay flat, the boat basin sunk in it, the town's slope rising behind it, the lava field on the right"""
    if s5_water(x, y): return -1.2
    z = 0.0
    if y > 4.0: z += S5_SLOPE * (min(y, 36.0) - 4.0)    # the town climbs the hill behind the harbour, row over row (steep: every row seen over the one below)
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 4.0 else 0)
    return z


def s5_lantern():
    """a REAL hurricane lantern (Poly Haven's Lantern_01), its glass glowing with the flame in it, hung by its top: the
    pivot at the top of its bail, the lantern below it"""
    root = K.empty("lantern", (0, 0, 0))
    S_ = 1.35
    lm = ph_model("Lantern_01", (0, 0, -0.29 * S_), scale=S_, name="lantern body", parent=root)
    glow = lw_emit("lantern glow", "#FFB050", 3.0)
    for c in lm.children_recursive:
        if "glass" in c.name.lower():
            c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = glow
    L = lw_point("lantern light", (0, 0, -0.16), 25.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.16)
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


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, and up the slope behind, the whole story in one frame (board after the fire test: "put
    the standing town and the earth wall in frame, so 'the wall saved the rest' is seen"): on the left the town
    standing, street over street, below the earth wall; the black lava field heaped up behind the wall; on the right,
    past the wall's end, the tongue of lava that got round it, its ridged glowing front run into the backs of three
    houses that burn from inside."""
    rnd = lw_random.Random(61)
    ground = ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock")          # REAL rock ground (Poly Haven), at a real size
    lw_grid("town slope", -26, 26, 1.2, 40, 208, 128, s5_slope_z, ground)          # the town's land, the basin sunk in it
    stone = ph_mat("concrete_wall_008", scale=1.5, tint="#8A8580", name="harbour stone")
    x0, x1, y0, y1 = S5_BASIN
    for k in range(12):                                    # the basin's stone walls: its town side climbs with the slope
        y = y0 + (y1 - y0) * (k + 0.5) / 12; top = s5_slope_z(x1 + 0.3, y)
        K.box("harbour basin wall", (x1 + 0.12, y, (top - 1.2) / 2), (0.25, (y1 - y0) / 12 + 0.02, top + 1.2), stone, bev=0.01)
    K.box("harbour basin wall", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.1, -0.6), (x1 - S5_EDGE_X + 0.2, 0.25, 1.24), stone, bev=0.01)
    top = s5_slope_z(x1 + 0.3, y1 + 0.3)
    K.box("harbour head wall", ((x0 - 30 + x1) / 2, y1 + 0.12, (top - 1.2) / 2), (x1 - x0 + 30, 0.25, top + 1.2), stone, bev=0.01)
    K.box("quay concrete", (6.0, -2.0, -0.128), (16.4, 7.0, 0.24), ph_mat("concrete_wall_008", scale=2.0, tint="#B5B1AA", name="quay concrete"), bev=0.02)
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
    white = ph_mat("corrugated_iron_02", scale=0.6, tint="#EDEBE4", paint=True, rough=0.45, name="wheelhouse white"); glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    steel = lw_metal("mast steel", "#8A8E92"); deck = ph_mat("black_painted_planks", scale=0.8, name="boat deck planks")
    fend = K.mat("fender", "#1C1C1E", rough=0.6)
    for k, (x, y) in enumerate(((-0.95, 4.0), (-1.3, 6.2), (-2.6, 4.6), (-3.6, 6.3))):
        c = hull_cols[k]; hm = ph_mat("container_side", scale=0.8, tint=c, paint=True, rough=0.4, name=f"hull steel {c}")      # REAL painted steel plate (Poly Haven)
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
        ph_model("lifebuoy", (x, y - 0.12, 0.3), rot=(math.pi / 2, 0, 0), scale=0.32, name=f"fishing boat {k} lifebuoy")     # a REAL ring buoy on the wheelhouse front
        for j in range(3):
            K.cyl(f"fishing boat {k} fender", (x + 0.53, y - 0.6 + 0.6 * j, -0.2), 0.05, 0.18, fend, v=10)
    home = town_house("his town house", (5.6, 3.6, 0.0), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.3, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    paint = K.mat("post paint", "#EDEAE2", rough=0.5); iron = lw_metal("hook iron", "#2E3033")
    K.box("lantern post", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.42), (0.09, 0.09, 0.84), paint, bev=0.01)
    K.box("lantern post cap", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.855), (0.13, 0.13, 0.03), paint, bev=0.008)
    K.box("lantern post foot", (S5_HOOK.x + 0.16, S5_HOOK.y, 0.03), (0.16, 0.16, 0.06), K.mat("post foot", "#6E6B66", rough=0.8), bev=0.01)
    K.box("lantern hook arm", (S5_HOOK.x + 0.06, S5_HOOK.y, S5_HOOK.z + 0.05), (0.2, 0.025, 0.025), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x + 0.1, S5_HOOK.y, S5_HOOK.z - 0.02), (0.13, 0.018, 0.018), iron, bev=0.003).rotation_euler = (0, math.radians(-45), 0)
    K.cyl("lantern hook", (S5_HOOK.x - 0.035, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x - 0.025, S5_HOOK.y, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, x in enumerate((9.6, 13.8, 18.0)):            # his neighbours along the quay, off to the right
        quay.append(town_house(f"quay house {k}", (x, 3.9 + 0.2 * k, 0.0), yaw=0.0, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], d=2.8, seed=50 + k))
    asph = ph_mat("asphalt_02", scale=2.0, tint="#7A7A7A", name="town street")
    for ys in (8.2, 12.6, 16.2):                         # the town's streets, across the slope
        lw_grid(f"town street {ys}", -26, 12.0 if ys < 16 else -0.5, ys - 0.7, ys + 0.7, 120, 4, lambda x, y: s5_slope_z(x, y) + 0.03, asph)
    town = []
    rows = [(10.2, (-12.6, -8.4, -4.2), 0), (14.4, (-14.0, -9.8, -5.6, -1.4), 0), (18.0, (-15.0, -10.8, -6.6, -2.4), 1)]     # (the lens's line up the hill to the burning row is left open: a street and rubble)
    for y, xs, one in rows:                              # the town that STANDS: below the wall, untouched, street over street
        for x in xs:
            k = len(town); x += rnd.uniform(-0.3, 0.3); yy = y + rnd.uniform(-0.2, 0.2)
            town.append(town_house(f"town house up {k}", (x, yy, s5_slope_z(x, yy - 1.4) - 0.05), yaw=rnd.uniform(-0.08, 0.08),
                                   roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], storeys=1 if one else None, seed=30 + k))
    for k, (x, y) in enumerate(((-18.0, 10.6), (-22.0, 14.0), (-20.0, 6.4), (-18.4, 18.0))):        # more of the town off to the left, filling the hill
        town.append(town_house(f"town house up {len(town)}", (x, y, s5_slope_z(x, y - 1.4) - 0.05), yaw=0.05, roof=ROOFS[k + 2], wall=WALLS[k + 3], seed=80 + k))
    # THE WALL: across the hill above the town, the old lava heaped up behind it, and its right end, where the new
    # lava got round
    WY = 21.6
    wall = earth_wall("earth wall", [(x, WY + 0.004 * x * x) for x in range(-26, 1, 2)], h=4.4, crest=1.4, base=8.0, seed=14)
    wall["root"].location.z = s5_slope_z(-8.0, WY) - 0.5
    tilt = math.atan(S5_SLOPE)
    held = lava_mat("lava held", heat=0.35, scale=1.6, fresh=0.05)
    pool = lava("lava held behind the wall", [(-26, 25.2), (0.5, 24.0), (0.5, 36), (-26, 36)], z=0.0, thick=1.4, m=held, seed=4, lumpy=0.35)
    c = pool.location.copy(); pool.rotation_euler.x = tilt; pool.location.z = s5_slope_z(-8, c.y) - 0.3
    fresh = lava_mat("lava field fresh", heat=0.8, scale=1.6, fresh=0.2)        # black crust, light only in its cracks and seams
    out = [(-1.0, 20.2), (2.4, 19.9), (6.4, 20.3), (10.4, 20.8), (14.0, 20.4), (18.0, 21.0), (24.0, 22.0), (24.0, 36.0), (-0.5, 36.0), (-1.4, 26.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.9, m=fresh, seed=8, lumpy=0.4)
    c = flow.location.copy(); flow.rotation_euler.x = tilt; flow.location.z = s5_slope_z(8, c.y) - 0.2
    crust = lava_mat("lava front crust", heat=0.55, scale=7.0, fresh=0.15)
    for k in range(320):                                 # its FRONT: a ridge of broken black crust blocks, glowing in their cracks
        i = rnd.randrange(6); q = Vector(out[i]).lerp(Vector(out[i + 1]), rnd.random())
        q.y += rnd.uniform(-0.2, 1.2)
        rr = rnd.uniform(0.15, 0.5)
        lw_block("lava front block", (q.x, q.y, s5_slope_z(q.x, q.y) + 0.3 + rr * 0.4), rr, crust, rnd, squash=0.75)
    houses = list(town)
    for k, (x, y) in enumerate(((-0.6, 9.0), (4.2, 9.0), (8.6, 9.1), (-0.4, 13.4), (4.4, 13.4), (8.8, 13.5), (-0.2, 17.0))):     # REAL street lamps along the streets
        ph_model("street_lamp_01", (x, y, s5_slope_z(x, y)), rot=(0, 0, math.pi), scale=0.5, name=f"street lamp {k}")
    ph_model("fire_hydrant", (2.2, 8.9, s5_slope_z(2.2, 8.9)), rot=(0, 0, 0.3), scale=0.5, name="fire hydrant", only=("fire_hydrant", "fire_hydrant_cap_01"))
    for k, (x, y, r) in enumerate(((1.6, 11.0, 0.4), (6.8, 10.6, 2.0), (10.6, 12.0, 1.1), (3.2, 15.2, 2.6), (7.4, 15.6, 0.2), (11.4, 16.0, 1.7))):   # REAL mossy lava boulders on the open slope
        ph_model("rock_moss_set_02" if k % 2 else "boulder_01", (x, y, s5_slope_z(x, y) - 0.1), rot=(0, 0, r), scale=0.55 if k % 2 else 0.7, name=f"slope boulder {k}")
    for k, (x, y) in enumerate(((5.6, 11.6), (9.0, 14.6), (2.0, 14.8))):
        ph_model("old_tyre", (x, y, s5_slope_z(x, y) + 0.04), rot=(math.pi / 2, 0, 0.7 * k), scale=0.5, name=f"old tyre {k}")
    lava_rock("lava rubble", 1100, (-26, 26, 5.0, 24.0), s5_slope_z, seed=5, r=(0.05, 0.22), moss=0.45,
              avoid=lambda x, y: s5_water(x, y) or min(abs(y - 8.2), abs(y - 12.6), abs(y - 16.2)) < 0.85
              or any(abs(x - h_["root"].location.x) < 2.2 and abs(y - h_["root"].location.y) < 1.8 for h_ in houses))
    burning = []
    for k, (x, y) in enumerate(((0.8, 18.0), (5.0, 18.3), (9.2, 18.7))):     # at the lava's front, past the wall's end: three in a row across the frame, countable
        z = s5_slope_z(x, y - 1.3) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.12, 0.12), w=3.6, d=2.6, roof=ROOFS[(k * 2) % len(ROOFS)],
                        wall=WALLS[(k + 1) % len(WALLS)], storeys=(2, 1, 2)[k], seed=40 + k, burn=1.0)
        lw_house_fire(hs, seed=11 + k, t_end=DUR + 1.0)
        burning.append(hs)
    for gx in (2.0, 8.0, 14.0):
        lw_point("lava front glow", (gx, 20.0, s5_slope_z(gx, 20) + 1.2), 900.0, col=(1.0, 0.35, 0.1), r=2.0)

    def light():
        k = iceland_light(sun_elev=3, sun_az=-55, sun=1.6, sky=0.18, warm=(1.0, 0.62, 0.45), haze=1.6)      # first light: dim enough that a lit window reads
        ph_sky("qwantani_sunrise_puresky", strength=0.35, rot=math.radians(150))       # a REAL dawn sky (Poly Haven)
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
    CAM = Vector((0.05, -0.45, 0.8)); LOOK = Vector((1.0, 14.0, 2.5))      # low on the quay: him and the post low, the open slope, the three houses burning up the hill at the lava front, the town standing to the left
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=28.0, fstop=16.0)
    def cam_at(t):                                          # it pans with him up the quay to the post, then holds
        sc.frame_set(F(min(t, T_WALK1))); bpy.context.view_layer.update()
        pan = Vector((data.pos().x - STAND.x, 0.0, 0.0))
        return CAM + pan * 0.6 + Vector((0.0, 0.1, 0.0)) * ease(t / DUR), LOOK + pan, data.pos() + Vector((0, 0, 0.6))
    # CUT to the WIDE on his walk to his door (board round 2: "no harbour, no boats, no wall", "three burning houses
    # against many untouched ones"): high over the harbour water, the boats in the basin, him at his door on the quay,
    # the town on its hill, the three houses burning at the black lava's edge, the wall above, the handful of lights
    T_W0, T_W1 = 0.28 * DUR, T_HANG - 0.35          # on his walk up the quay, his face to this lens (KEYS: never his back)
    CW = Vector((3.5, -6.5, 8.5)); LW = Vector((0.5, 14.0, 5.0))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.12, 0.2, -0.05)) * (t - T_W0), LW, Vector((0.0, 14.0, 5.0))), T_W0, T_W1, 28.0, 20.0)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])
