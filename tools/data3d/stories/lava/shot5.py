"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but almost nobody moved back. Would you?"

Dawn, the morning after, at the foot of the town's hill. Up the hill three houses burn in a row, side by side, black
lava round them; the earth wall stands across the hilltop behind them; below them the saved houses stand with dark
windows. The driver walks up to his own house with a lit lantern, hangs it on the hook by his window, and that one
window lights up: the only light in the town. He turns to us and shrugs."""

S5_HOOK = Vector((-0.3, 2.77, 0.47))        # the hook's tip: an iron arm off his house's front wall, between the window and the corner, at his own height
S5_KNOTS = ((6.9, 0.0), (8.2, 1.4), (10.0, 2.0), (11.2, 7.0), (14.4, 7.7), (17.5, 8.0), (19.5, 9.0), (40.0, 10.9))    # the hill behind his house (y, z)
S5_BURN_Y = 12.9                            # the burning row
S5_WALL_Y = 18.5
S5_BURN_X = 9.3                              # the burning row's middle: up the hill over his roof, in the middle of the lens's frame


def s5_z(x, y):
    """the paved yard in front of his house, flat; the hill climbing behind it, street over street"""
    if y <= S5_KNOTS[0][0]: return 0.0
    z = S5_KNOTS[-1][1]
    for (y0, z0), (y1, z1) in zip(S5_KNOTS, S5_KNOTS[1:]):
        if y <= y1:
            u = (y - y0) / (y1 - y0); z = z0 + (z1 - z0) * u; break
    return z + 0.1 * lw_fbm(x * 0.3, y * 0.3, 51) * min(1.0, (y - S5_KNOTS[0][0]) / 2.0)


def s5_lantern():
    """a REAL hurricane lantern (Poly Haven's Lantern_01), its glass glowing with the flame in it, hung by its top: the
    pivot at the top of its bail, the lantern below it"""
    root = K.empty("lantern", (0, 0, 0))
    S_ = 0.95
    lm = ph_model("Lantern_01", (0, 0, -0.29 * S_), scale=S_, name="lantern body", parent=root)
    glow = lw_emit("lantern glow", "#FFB050", 14.0)
    for c in lm.children_recursive:
        if "glass" in c.name.lower():
            c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = glow
    L = lw_point("lantern light", (0, 0, -0.16), 30.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.16)
    return root


def s5_lit_pane(house, k, t_on):
    """a window of a dark house that lights up at t_on (a pane in front of the dark one)"""
    p = house["windows"][k]
    lit = p.copy(); lit.data = p.data.copy(); bpy.context.collection.objects.link(lit)
    lit.name = p.name.replace("window pane", "window lit pane")
    lit.data.materials.clear(); lit.data.materials.append(lw_emit("window lit warm", "#FF6A00", 1.5))
    bpy.data.materials["window lit warm"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.012, 0.004, 1)   # LIGHT, not paint: a sunlit orange pane read pale pink
    b_ = bpy.data.materials["window lit warm"].node_tree.nodes["Principled BSDF"]
    b_.inputs["Roughness"].default_value = 1.0                                   # no sky in it: glass that mirrors the dawn reads as a pale card
    for nm in ("Specular IOR Level", "Specular"):
        if nm in b_.inputs: b_.inputs[nm].default_value = 0.0
    # a LAMP inside, not an orange card (coordinator): hot and yellow low in the middle of the pane, falling to deep amber at its edges
    nt_ = bpy.data.materials["window lit warm"].node_tree; N_ = nt_.nodes.new; L_ = nt_.links.new
    tc_ = N_("ShaderNodeTexCoord"); ds_ = N_("ShaderNodeVectorMath"); ds_.operation = 'DISTANCE'; ds_.inputs[1].default_value = (0.56, 0.5, 0.36)
    L_(tc_.outputs["Generated"], ds_.inputs[0])
    mr_ = N_("ShaderNodeMapRange"); mr_.inputs[1].default_value = 0.05; mr_.inputs[2].default_value = 0.7; mr_.inputs[3].default_value = 1.0; mr_.inputs[4].default_value = 0.0
    L_(ds_.outputs["Value"], mr_.inputs[0])
    cr_ = N_("ShaderNodeValToRGB"); cr_.color_ramp.elements[0].color = (*K.lin("#A83A00"), 1); cr_.color_ramp.elements[1].color = (*K.lin("#FFC25A"), 1)
    L_(mr_.outputs[0], cr_.inputs[0]); L_(cr_.outputs[0], b_.inputs["Emission Color"])
    st_ = N_("ShaderNodeMath"); st_.operation = 'MULTIPLY_ADD'; st_.inputs[1].default_value = 3.0; st_.inputs[2].default_value = 0.7
    L_(mr_.outputs[0], st_.inputs[0]); L_(st_.outputs[0], b_.inputs["Emission Strength"])
    lit.location.y -= 0.004
    lw_show([lit], t_on)
    bpy.context.view_layer.update()
    cs_ = [lit.matrix_world @ Vector(c) for c in lit.bound_box]
    x0, x1 = min(c.x for c in cs_), max(c.x for c in cs_); z0, z1 = min(c.z for c in cs_), max(c.z for c in cs_); yy = min(c.y for c in cs_) - 0.004
    ww, hh = x1 - x0, z1 - z0
    drape = lw_emit("window curtain lit", "#B8560E", 1.1); shade = lw_emit("window lamp shade", "#FFD27A", 3.2); stem = lw_emit("window lamp stem", "#3A1404", 0.3)
    inside = [K.box("window curtain L", (x0 + ww * 0.07, yy, z0 + hh * 0.5), (ww * 0.14, 0.004, hh), drape),      # an INTERIOR (coordinator: "a flat orange slab"): curtains drawn back, a lamp on the sill
              K.box("window curtain R", (x1 - ww * 0.07, yy, z0 + hh * 0.5), (ww * 0.14, 0.004, hh), drape),
              K.box("window curtain rail", (x0 + ww * 0.5, yy, z1 - hh * 0.04), (ww, 0.004, hh * 0.08), drape),
              K.box("window lamp stem", (x0 + ww * 0.56, yy, z0 + hh * 0.13), (ww * 0.035, 0.004, hh * 0.26), stem),
              K.box("window lamp shade", (x0 + ww * 0.56, yy, z0 + hh * 0.31), (ww * 0.17, 0.004, hh * 0.13), shade)]
    lw_show(inside, t_on)
    return lit



def place_harbour_dawn():
    """THE MORNING AFTER, in one frame, bottom to top: his own house and its yard at the foot of the hill; the saved
    houses on the hill, their windows dark; three houses in a row burning from inside, black crusted lava round their
    feet; and across the hilltop behind them the earth wall, still standing."""
    rnd = lw_random.Random(61)
    ground = ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock")
    lw_grid("town hill", -26, 36, 6.6, 48, 120, 120, s5_z, ground)
    asph = ph_mat("asphalt_02", scale=2.0, tint="#7A7A7A", name="town street")
    lw_grid("house yard", -14, 36, -3.0, 6.9, 56, 20, lambda x, y: 0.0, asph)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#9A968F", name="yard kerb")
    K.box("yard kerb", (8, 6.8, 0.05), (56, 0.16, 0.12), kerb, bev=0.015)
    # HIS HOUSE: low, white tin, a blue roof; its front to us, its right-hand window and corner in frame
    home = town_house("his town house", (-1.45, 4.5, 0.0), yaw=0.0, w=3.2, d=2.6, h=1.15, storeys=1, base=0.2, pitch=9, roof="#2F5E8C", wall="#F1EEE6", seed=5)
    for o in [o for o in bpy.data.objects if o.name.startswith("his town house downpipe") and o.location.x > 0]:
        bpy.data.objects.remove(o, do_unlink=True)       # (the pipe at this corner stood where he walks in)
    iron = lw_rust("hook iron", "#2A2624")
    fy = 4.5 - 1.3                                       # the house's front wall (y)
    K.box("lantern hook plate", (S5_HOOK.x, fy - 0.012, S5_HOOK.z + 0.02), (0.07, 0.012, 0.2), iron, bev=0.003)
    K.box("lantern hook arm", (S5_HOOK.x, (fy + S5_HOOK.y) / 2 - 0.01, S5_HOOK.z + 0.05), (0.022, fy - S5_HOOK.y + 0.02, 0.022), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x, fy - 0.06, S5_HOOK.z - 0.01), (0.016, 0.14, 0.016), iron, bev=0.003).rotation_euler = (math.radians(-40), 0, 0)
    K.cyl("lantern hook", (S5_HOOK.x, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x, S5_HOOK.y - 0.012, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(math.pi / 2, 0, 0), v=8)
    town = []
    for k, (x, y, roof, wall) in enumerate(((2.2, 8.9, "#B8352B", "#E9D9A2"), (5.2, 8.5, "#3F7A4A", "#BFD3DD"), (8.3, 8.6, "#C9A23A", "#F1EEE6"),
                                            (11.5, 8.8, "#9E3A2E", "#E6E0D2"), (-4.1, 10.2, "#2E6F73", "#D9C9B4"))):
        town.append(town_house(f"town house up {k}", (x, y, s5_z(x, y - 1.4) - 0.05), yaw=rnd.uniform(-0.06, 0.06), w=2.7, d=2.6, storeys=1, base=0.3,
                               roof=roof, wall=wall, seed=30 + k))
    # THE WALL across the hilltop, behind the burning row
    wall = earth_wall("earth wall", [(x, S5_WALL_Y + 0.003 * x * x) for x in range(-22, 33, 2)], h=4.6, crest=1.4, base=8.0, seed=14)
    wall["root"].location.z = s5_z(0, S5_WALL_Y) - 0.4
    # THE LAVA that came up through the crack, inside the wall: cooled black, light only in its seams, round the three
    # houses it took
    fresh = lava_mat("lava field fresh", heat=0.8, scale=1.6, fresh=0.2)
    lw_grid("new lava field", S5_BURN_X - 6.5, S5_BURN_X + 6.5, S5_BURN_Y - 2.6, S5_BURN_Y + 4.6, 60, 28,
            lambda x, y: s5_z(x, y) + 0.28 + 0.22 * lw_fbm(x * 0.8, y * 0.8, 7) - 0.5 * max(0.0, (S5_BURN_Y - 1.9 - y)) - 0.5 * max(0.0, -5.6 - (x - S5_BURN_X)) - 0.5 * max(0.0, (x - S5_BURN_X) - 5.6), fresh)
    crust = lava_mat("lava front crust", heat=0.55, scale=7.0, fresh=0.15)
    for k in range(150):                                 # its front: a ridge of broken crust blocks below the houses
        x = S5_BURN_X + rnd.uniform(-6.0, 6.0); y = S5_BURN_Y - 2.3 + rnd.uniform(-0.3, 0.5); rr = rnd.uniform(0.14, 0.4)
        lw_block("lava front block", (x, y, s5_z(x, y) + 0.2 + rr * 0.4), rr, crust, rnd, squash=0.75)
    houses = [home] + town
    lava_rock("lava rubble", 500, (-8, 22, 7.2, S5_BURN_Y - 2.8), s5_z, seed=5, r=(0.06, 0.24), moss=0.4,
              avoid=lambda x, y: any(abs(x - h_["root"].location.x) < 1.9 and abs(y - h_["root"].location.y) < 1.8 for h_ in houses))
    lava_rock("yard grit", 90, (-3.0, 4.0, 0.6, 4.6), lambda x, y: 0.0, seed=9, r=(0.012, 0.045), moss=0.0,
              avoid=lambda x, y: (-0.8 < x < 1.0 and 2.0 < y < 3.3) or (x < -0.1 and y > 3.1))
    burning = []
    for k, x in enumerate((S5_BURN_X - 3.6, S5_BURN_X, S5_BURN_X + 3.6)):           # THREE, in a row across the frame, side by side: countable
        y = S5_BURN_Y + 0.15 * (k % 2)
        hs = town_house(f"burning house {k}", (x, y, s5_z(x, y - 1.3) + 0.35), yaw=rnd.uniform(-0.06, 0.06), w=2.6, d=2.6, roof=ROOFS[(k * 2) % len(ROOFS)],
                        wall=WALLS[(k + 1) % len(WALLS)], storeys=2, base=0.3, seed=40 + k, burn=1.0)
        hp = hs["hole"]
        hf = (3.6, 2.6, 4.2)[k]                           # RAGGED, no two alike (coordinator: "smooth candle cones"): a torn body, a thin taller tongue and a low one beside it
        lw_fire_column(f"burning house {k} blaze", (hp.x, hp.y + 0.3, hp.z - 1.2), w=2.6, h_fire=hf, h_smoke=13.0, lean=(-0.45, 0.2), t_end=DUR + 1.0,
                       seed=k * 3.7 + 1.0, fire=13.0, smoke_d=3.2, spread=0.34, rise=2.4)
        lw_fire_column(f"burning house {k} blaze tongue", (hp.x + rnd.uniform(-0.8, 0.8), hp.y + 0.1, hp.z - 1.0), w=0.9, h_fire=hf * rnd.uniform(1.1, 1.35), h_smoke=2.0, lean=(rnd.uniform(-0.5, 0.1), 0.1), t_end=DUR + 1.0,
                       seed=k * 5.1 + 2.3, fire=22.0, smoke_d=0.8, spread=0.3, rise=3.6)
        lw_fire_column(f"burning house {k} blaze low", (hp.x + rnd.uniform(-1.0, 1.0), hp.y - 0.2, hp.z - 1.6), w=1.5, h_fire=hf * 0.55, h_smoke=1.5, lean=(rnd.uniform(-0.3, 0.3), 0.1), t_end=DUR + 1.0,
                       seed=k * 2.9 + 4.1, fire=16.0, smoke_d=0.8, spread=0.36, rise=3.0)
        lw_point(f"burning house {k} blaze light", (hp.x, hp.y - 0.6, hp.z + 0.8), 1600.0, col=(1.0, 0.45, 0.15), r=0.6)
        burning.append(hs)

    def light():
        k = iceland_light(sun_elev=6, sun_az=-55, sun=3.0, sky=0.4, warm=(1.0, 0.66, 0.5), haze=1.5)      # first light: clear and pale, dim enough that one lit window reads
        ph_sky("qwantani_sunrise_puresky", strength=0.85, rot=math.radians(150))       # a REAL dawn sky (Poly Haven)
        return k
    return dict(light=light, home=home, town=town, burning=burning, wall=wall)


def shot5():
    """He comes up to his own house with the lit lantern (still 1), lifts it onto the hook by his window (still 2); it
    hangs there glowing and the window beside it lights up, the only light in the town (still 3); he turns to us and
    shrugs (still 4). Up the hill behind him, all the while: the three burning houses in a row, the wall behind them."""
    T_IN = 0.85; T_HANG = 0.28 * DUR; T_LET = T_HANG + 0.17
    T_WIN = 0.52 * DUR; T_TURN = 0.695 * DUR; T_ASK = T_TURN + 0.52
    W = lw_win
    P = place_harbour_dawn()
    light = P["light"]
    data = load_data()
    R = math.radians
    HOOKED = S5_HOOK + Vector((0, 0, 0.005))
    # he stands in PROFILE along his house's front, a little toward us, the hook straight ahead of his wall-side hand
    data.place(0.0, 0.0, 0.0); sc.frame_set(1); bpy.context.view_layer.update()
    f0 = data.forward(); YAW_H = math.degrees(math.atan2(-0.6, -0.8) - math.atan2(f0.y, f0.x))
    data.place(0.0, 0.0, YAW_H); bpy.context.view_layer.update()
    fw = data.forward(); fw.z = 0; fw.normalize()
    near = sorted("LR", key=lambda s_: acts._shoulder(data, s_).y)               # near[0]: the hand toward the lens
    carry, other = near[1], near[0]                                              # the wall-side hand carries it: the hook is dead ahead of it
    sh0 = acts._shoulder(data, carry) - Vector(data.arm.location)
    TOES = 0.045
    UPH = HOOKED.z - TOES - sh0.z
    FWD = math.sqrt(max(0.06 ** 2, 0.165 ** 2 - UPH ** 2))
    STAND = HOOKED - sh0 - fw * FWD; STAND.z = 0.0
    START = STAND - fw * 0.24; MID = STAND - fw * 0.12
    print("S5 GEOM fw", tuple(round(v, 3) for v in fw), "sh0", tuple(round(v, 3) for v in sh0), "UPH", round(UPH, 3), "FWD", round(FWD, 3), "STAND", tuple(round(v, 3) for v in STAND),
          "windows", [tuple(round(v, 2) for v in w_.matrix_world.translation) for w_ in P["home"]["windows"]],
          "pipes", [tuple(round(v, 2) for v in o.matrix_world.translation) for o in bpy.data.objects if "his town house downpipe" in o.name], flush=True)
    data.place(START.x, START.y, YAW_H)
    kit = hard_hat(data)
    data.walk_to((MID.x, MID.y), 0.0, 0.3); data.walk_to((STAND.x, STAND.y), 0.55, T_IN)      # two steps with a stop between: both feet flat on the board's first still                                  # he WALKS up to his house (real steps)
    YAW0 = math.radians(YAW_H)
    sc.frame_set(F(T_IN)); YW = data.arm.rotation_euler.z                       # the facing his walk ends on
    while YW - YAW0 > math.pi: YW -= 2 * math.pi
    while YW - YAW0 < -math.pi: YW += 2 * math.pi
    def body(t):
        p = STAND.copy()
        p.z += TOES * W(t, T_HANG - 0.35, 0.3) * (1 - W(t, T_LET + 0.02, 0.2))                   # up on his toes to the hook
        back = W(t, T_LET + 0.05, 0.35)
        p += Vector((0.17, -0.12, 0.0)) * back                                                                   # a step back from it, to look
        p.z += 0.05 * lw_kick(t - T_WIN - 0.1, 0.2); p += Vector((-0.06, 0.05, 0.0)) * W(t, T_WIN + 0.05, 0.3)   # a start, and half a step in toward the warm glass                                               # a start as the window lights
        turn = W(t, T_TURN, 0.42)
        p += Vector((0.05, -0.05, 0.0)) * turn; p.z += 0.03 * math.sin(math.pi * turn)             # a step round to us
        st = W(t, T_ASK - 0.45, 0.4); p += Vector((0.0, -0.03, 0.0)) * st     # a step along the yard toward us
        p.z += 0.045 * lw_kick(t - T_ASK - 0.25, 0.22)                                            # the shrug
        return p, YW + (YAW0 - YW) * W(t, T_IN, 0.4) - R(6) * back - R(0) * W(t, T_WIN, 0.3) * (1 - turn) + R(13) * turn      # hips stay three-quarter to his window: only head and shoulders come round to us
    for f in range(F(T_IN) + 1, NF + 16):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (6 * W(t, T_WIN, 0.3) * (1 - W(t, T_TURN, 0.3)) + 0 * W(t, T_TURN + 0.02, 0.28) * (1 - W(t, T_ASK - 0.12, 0.28)) - 6 * W(t, T_ASK, 0.3), 0, 0), T_LET + 0.3, DUR + 0.4)
    # ---- face and head (BEFORE the hands: a face moves his chest and shoulders)
    wy = P["home"]["windows"][1].matrix_world.translation.copy()
    CAM0 = Vector((-1.6, 0.5, 0.5)); LOOK0 = CAM0 + Vector((5.9, 8.1, 1.9))
    data.look_at(S5_HOOK, 0.0, max_yaw=50, max_pitch=40, blend=0.0)
    data.look_at(wy, T_WIN + 0.05, max_yaw=22, max_pitch=20, blend=0.2)                          # the window, as it lights
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_TURN + 0.05, max_yaw=60, max_pitch=30, blend=0.3)  # to us: would you?
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_ASK - 0.1, max_yaw=60, max_pitch=30, blend=0.2)
    data.look_at(CAM0 + Vector((0, 0, 0.05)), T_ASK + 0.2, max_yaw=60, max_pitch=30, blend=0.2)
    data.expression("sad", 0.0, T_WIN, blend=0.25)
    data.expression("worried", T_WIN, T_ASK - 0.1, blend=0.3)                                   # a soft, tired look at it (coordinator: not a smile while three houses burn)
    data.expression("wry", T_ASK - 0.1, DUR + 1.0, blend=0.25)
    # ---- the lantern: carried in front of him in his wall-side hand, lifted onto the hook, let go; it swings
    lan = s5_lantern()
    carry_fn = lw_hand(data, carry, [(0.0, (0.13, 0.0, -0.12)), (0.4, (0.19, 0.03, 0.0)), (T_IN, (0.14, 0.0, -0.1)), (T_IN + 0.3, (0.04, 0.03, -0.17)), (DUR, (0.04, 0.03, -0.17))])
    down_fn = lw_hand(data, carry, [(T_LET, (0.12, 0.02, -0.08)), (T_LET + 0.42, (0.05, 0.04, -0.16)), (DUR, (0.05, 0.04, -0.16))])
    def carry_path(t):                                       # ONE job for the lantern hand: held up to light his way, a dip, the lift onto the hook, hold it there, and down
        if t < T_HANG: return carry_fn(min(t, T_IN + 0.3)).lerp(HOOKED, W(t, T_IN + 0.3, T_HANG - T_IN - 0.3))
        if t <= T_LET: return HOOKED.copy()
        return HOOKED.lerp(down_fn(t), W(t, T_LET, 0.42))
    data.reach(carry, carry_path, 0.0, T_LET + 0.45, lead=0.05, back=None, elbow_out=0.35)
    def swing(t):                                           # after the let-go: a damped swing about the hook
        s_ = t - T_LET
        return 0.0 if s_ <= 0 else math.radians(20) * math.exp(-s_ / 2.2) * math.sin(2 * math.pi * s_ / 0.9)
    # ---- his hands after it: a start at the lit window (both hands up, open), then the shrug to us
    for sd, sg in (("L", -1), ("R", 1)):                   # the shrug big enough for a phone: both arms out from his sides, palms up
        LG = 0.38                                     # measured: these FK keys land 0.4 s after the time they are given here (the reach's bake), so they are given early
        if sd == carry:                               # a hand out toward the warm glass as it lights, then down
            data._k(f"arm.{sd}", T_WIN + 0.05 - LG, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", T_WIN + 0.05 - LG, rot=(-38, 0, -sg * 16))
            data._k(f"arm.{sd}", T_WIN + 0.3 - LG, rot=(-10, 0, -sg * 68)); data._k(f"fore.{sd}", T_WIN + 0.3 - LG, rot=(-28, 0, -sg * 22))
            data._k(f"arm.{sd}", T_TURN - 0.05 - LG, rot=(-10, 0, -sg * 68)); data._k(f"fore.{sd}", T_TURN - 0.05 - LG, rot=(-28, 0, -sg * 22))
        else:
            for t_ in (T_LET + 0.5, T_TURN - 0.05 - LG): data._k(f"arm.{sd}", t_, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", t_, rot=(-38, 0, -sg * 16))
        data._k(f"arm.{sd}", T_TURN + 0.3 - LG, rot=(-58, 0, -sg * 6)); data._k(f"fore.{sd}", T_TURN + 0.3 - LG, rot=(-38, 0, sg * 18))   # his hands come together at his chest, then open into the shrug
        data._k(f"arm.{sd}", T_ASK - 0.1, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", T_ASK - 0.1, rot=(-38, 0, -sg * 16))   # his hands open low...
        data._k(f"arm.{sd}", DUR - 0.2, rot=(-2, 0, -sg * 26)); data._k(f"fore.{sd}", DUR - 0.2, rot=(-38, 0, -sg * 16))    # (his hands fall as the shot cuts)
        for t_ in (T_ASK + 0.45, DUR - 0.5):
            data._k(f"arm.{sd}", t_, rot=(-10, 0, -sg * 52)); data._k(f"fore.{sd}", t_, rot=(-62, 0, -sg * 34))   # ...and out into the shrug: elbows bent, hands low (small, not arms flung wide)
    data.finish()
    for f in range(1, NF + 16):
        t = (f - 1) / FPS
        if t <= T_LET:
            sc.frame_set(f); bpy.context.view_layer.update()
            hp_ = data.arm.matrix_world @ data.pb[f"hand.{carry}"].tail + Vector((0, 0, -0.02))
            lan.location = hp_.lerp(S5_HOOK, W(t, T_HANG - 0.12, 0.12))
            lan.rotation_euler = (0, math.radians(6) * math.sin(2 * math.pi * t / 0.6) * (1 - W(t, T_IN, 0.3)), 0)
        else:
            lan.location = S5_HOOK; lan.rotation_euler = (0, swing(t), 0)
        lan.keyframe_insert("location", frame=f); lan.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: wide and low in his yard, tipped up the hill: him and his window at the bottom, the saved houses
    # over his roof, the burning row and the wall at the top
    LENS_MM = 20.0
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=LENS_MM, fstop=11.0)
    C1, L1 = compose.frame_data(data, CAM0, LOOK0, LENS_MM, face_at=(0.4, 0.5), height=0.45, t=T_HANG)
    push = lambda t: Vector((0.0, 0.0, 0.0))
    lw_cut(cam, lambda t: (C1 + push(t), L1, data.pos() + Vector((0, 0, 0.6))), lambda t: (C1, L1, data.pos()), -1.0, -1.0, LENS_MM, LENS_MM)
    # ---- the payoff: his one window lights
    lit = [s5_lit_pane(P["home"], 1, T_WIN)]
    glow = lw_point("window spill", (wy.x + 0.1, wy.y - 0.4, wy.z - 0.35), 42.0, col=(1.0, 0.5, 0.15), r=0.3)
    lw_show([glow], T_WIN)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern hook"), cutaway=None,
                boxes=[],
                conseq=[("three houses burn in a row up the hill", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook by his window and it swings, glowing", lambda: meshes([lan]), T_IN, DUR, {"whole": False, "moves": True}),
                        ("the one window beside it lights up", lambda: meshes(lit), T_WIN, DUR, {"whole": False})])
