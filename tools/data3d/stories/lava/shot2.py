"""BEAT 2: "So Iceland built a wall of rock taller than a house to keep the lava out."

THE WALL GROWS, AND HE IS ITS CAUSE (coordinator, 2026-11-27, after the boulder on the crest blocked: "the event is
the wall GROWING and Data is the cause"). By one painted tin house at the wall's foot, his tipper truck (shot 1's) is
backed up to a low row of black rock; at the truck's tip lever, both hands on it, he tips its load of rock onto the
row in a puff of dust (still 1). From up high on the other side of the alley: the wall now roof-high, more rock
sliding off the tipped bed onto it (still 2). Far off across the town: the finished wall plainly taller than the house
beside it, the black plume and a glowing flow out on the plain beyond it, held away from the town (still 3). Low by
the house: he stands small at the wall's foot beside the door, looking up at it (still 4).

The wall is three heaps of the beat-3 berm (same rock, same crest, same slope), each taller and wider than the last,
sharing the town-side foot: the next one rises out of the ground inside the one before, so the wall grows up and out
toward the lava side, and its foot by the house never moves."""

S2_HS = (0.5, 2.6, 5.6)                 # the wall's three heights: knee-high to the house, roof-high, beat 3's wall (S3_H)
S2_CREST = 1.6                          # beat 3's crest (S3_CREST)
S2_SLOPE = 0.97 * 5.6 / (11.0 / 2 - S2_CREST / 2 - 0.1)     # beat 3's faces (S3_BASE 11)
S2_XT, S2_YT = 0.0, 2.2                 # his truck: tail to the wall at y 0.35, nose into town
S2_HOUSE = (-2.45, 2.6, 1.6, 2.4)        # the house: centre x, y, width, depth; its front (and door) 1.4 m off the wall's foot, left of the truck's tail


def s2_base(h):
    return 2.0 * (S2_CREST / 2 + 0.1 + 0.97 * h / S2_SLOPE)


def s2_ground_z(x, y):
    """the town's ground (y > 0); the black lava field beyond the wall, hummocky, and far off the volcano's ridge"""
    if y > 0.0: return 0.04 + 0.05 * lw_fbm(x * 0.3, y * 0.3, 19)
    z = 0.06 + 0.06 * lw_fbm(x * 0.3, y * 0.3, 19)
    if y < -8.0:
        k = min(1.0, (-8.0 - y) / 4.0)
        z += k * (0.5 * lw_fbm(x * 0.16, y * 0.16, 31) + 0.2 * lw_fbm(x * 0.6, y * 0.6, 37))
    if y < -40.0 and x > 50.0: z += min(14.0, (x - 50.0) * 0.25 * min(1.0, (-40.0 - y) / 10.0))         # the ridge the eruption is on (q2a: a steep one read as a flat-topped table)
    return z


def place_wall_works():
    """THE WALL'S FOOT IN TOWN: green moss ground, one painted tin house with its front to the wall, more houses and a
    flag behind it; the wall's three heaps; beyond the wall the black field, a glowing lava flow out on it, the ridge
    with its fountains and their ash plumes."""
    lw_grid("lava field ground", -120, 120, -170, 0.6, 140, 150, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#151413", name="lava field rock ground"))
    lw_grid("town ground", -60, 60, 0.0, 40, 90, 50, s2_ground_z, lw_noise("town moss ground", "#4E5A34", "#8C9263", scale=0.9, rough=1.0, bump=0.5, detail=12))
    FX.ground("grass", area=(-12, 14, 4.2, 30), zfn=lambda x, y: s2_ground_z(x, y) + 0.03, seed=4, name="town grass")
    lava_rock("town yard stones", 500, (-10, 12, 0.2, 14), lambda x, y: s2_ground_z(x, y) + 0.02, seed=78, r=(0.03, 0.12), moss=0.6,
              avoid=lambda x, y: (-1.25 < x < 0.8 and y < 4.4) or (-3.4 < x < -1.5 and 1.2 < y < 3.9) or (-2.5 < x < -0.9 and 0.3 < y < 1.25))       # (clear of the truck, the house and his walk)
    walls = []
    path = [(float(x), 0.0) for x in range(-40, 41, 1)]
    for k, h in enumerate(S2_HS):
        b = s2_base(h)
        w = earth_wall(f"earth wall {k}", [(x, y - b / 2) for x, y in path], h=h, crest=S2_CREST, base=b, seed=8 + k)
        walls.append(w)
    lava_rock("lava field block", 700, (-60, 60, -80, -9), s2_ground_z, seed=13, r=(0.25, 0.9), moss=0.0)
    # the house at the wall's foot, its front and door to the wall; the town behind it
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=0.0, w=hw, d=hd, storeys=1, base=0.3, pitch=38, roof="#B8352B", wall="#E9D9A2", seed=5)
    for k, (x, y, roof, wl) in enumerate(((-3.2, 7.2, "#2F5E8C", "#F1EEE6"), (5.4, 6.6, "#3F7A4A", "#BFD3DD"), (-7.0, 9.6, "#C9A23A", "#E9D9A2"),
                                          (1.0, 10.4, "#B8352B", "#7E9A86"), (8.6, 10.8, "#2F5E8C", "#E9D9A2"), (-11.0, 7.0, "#9E3A2E", "#F1EEE6"))):
        town_house(f"town house back {k}", (x, y, s2_ground_z(x, y)), yaw=0.0, w=3.0, d=2.6, storeys=1 + (k % 2), base=0.3, pitch=38, roof=roof, wall=wl, seed=21 + k)
    blue = lw_paint("flag blue", "#02529C", rough=0.7); white = lw_paint("flag white", "#F4F4F0", rough=0.7); red = lw_paint("flag red", "#DC1E35", rough=0.7)
    fx, fy = -4.4, 2.3; fzz = s2_ground_z(fx, fy)          # (q2c: in the yard by the house, where the wide sees it)
    K.cyl("flag pole", (fx, fy, fzz + 1.6), 0.025, 3.2, lw_paint("flag pole white", "#EDEDE8", rough=0.5), v=10)
    FS = 1.4; c = Vector((fx + 0.36 * FS, fy, fzz + 2.85))
    for nm, off, size, m in (("field", 0.0, (0.66, 0.012, 0.46), blue), ("white bar", -0.1, (0.13, 0.016, 0.46), white), ("white band", 0.0, (0.66, 0.016, 0.13), white),
                             ("red bar", -0.1, (0.065, 0.02, 0.46), red), ("red band", 0.0, (0.66, 0.02, 0.065), red)):
        K.box(f"icelandic flag {nm}", tuple(c + Vector((off * FS, 0, 0))), (size[0] * FS, size[1], size[2] * FS), m, bev=0.0)
    # WHAT IT KEEPS OUT: the fountains on the far ridge under their ash, and a lobe of lava out on the field, glowing at
    # its front, stopped well short of the wall
    founts = []
    for k, (x, y, hf) in enumerate(((70.0, -62.0, 24.0), (86.0, -48.0, 28.0), (98.0, -74.0, 22.0))):      # (off down the wall, where the wide along it looks)
        z0 = s2_ground_z(x, y)
        founts.append(FX.lava_fountain(base=(x, y, z0), h=0.3 * hf, w=2.5, length=10.0, clots=120, clot_size=2.6, plume=2.0, lean=(0.3, 0.2), seed=23 + k, splats=0,
                                       t_end=DUR + 1.0, name=f"far fountain {k}")["jet"])
        founts.append(ash_plume((x, y, z0), w=0.5 * hf, h=2.6 * hf, S=8.0, dens=8.0, lean=(0.02, 0.02), col=(0.07, 0.066, 0.063), seed=1.7 + 2.3 * k, t_end=DUR + 1.0, name=f"far plume {k}"))
        lw_point(f"far plume fire light {k}", (x, y + 2.0, z0 + 0.3 * hf), 90000.0, col=(1.0, 0.5, 0.14), r=3.0)
    rl = lw_random.Random(5)
    lobe = [(30.0 + 13.0 * math.cos(a) * (1 + 0.12 * rl.uniform(-1, 1)), -30.0 + 7.0 * math.sin(a) * (1 + 0.12 * rl.uniform(-1, 1))) for a in [2 * math.pi * k / 18 for k in range(18)]]
    FX.lava_flow(lobe, z=s2_ground_z(30.0, -30.0) + 0.15, thick=0.5, fresh=0.85, drift=(0.0, 0.06), seed=6, name="lava flow beyond the wall")
    def light():
        return FX.sky("day", sun_az=-30)["sun"]
    return dict(light=light, walls=walls, house=house, founts=founts)


def shot2():
    """HE TIPS THE ROCK AND THE WALL GROWS. At his truck's tip lever in the alley between the truck and the house, both
    hands on it: the bed tips, its rock pours onto the low row in dust (still 1); from up high, the bed tipped right
    up, more rock sliding off, the wall roof-high beside the house (still 2). CUT WIDE: far across the town, the
    finished wall over the house, the lava out beyond it (still 3); low at the house, him small at the wall's foot by
    the door, looking up at it (still 4)."""
    R = math.radians
    W = lw_win
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    T_AB = 0.6; T_LET = 1.4; T_WALK = 1.85; T_ARR = 2.75
    T_CUT = 1.72; T_WB = 2.72
    P = place_wall_works()
    light = P["light"]; walls = P["walls"]
    # ---- the wall grows: each heap rises out of the ground inside the one before it
    RISE = [None, (0.42, 0.75), (1.3, 0.8)]          # (q2c: the roof-high heap breaks the ground as the first rock lands on the row)
    def off(k, t):
        if k == 0: return 0.0
        a, d = RISE[k]; return -(S2_HS[k] + 0.25) * (1.0 - W(t, a, d))       # (q2a: from below the ground, or the plan's box never sees it grow)
    for k, w in enumerate(walls):
        for f in range(1, NF + 1):
            w["root"].location = (0, 0, off(k, (f - 1) / FPS)); w["root"].keyframe_insert("location", frame=f)
    def surface(x, y, t):
        z = s2_ground_z(x, y)
        for k, h in enumerate(S2_HS):
            b = s2_base(h); yc = -b / 2
            z = max(z, off(k, t) + min(h, max(0.0, (b / 2 - abs(y - yc)) * S2_SLOPE)))
        return z
    # ---- HIS truck (shot 1's), backed up to the wall, its tailgate open; the tip lever on its town side
    tr = FX.truck(name="his tipper truck", loc=(S2_XT, S2_YT, 0.0), yaw=math.pi, lights=True, power=90.0, seed=2)
    troot = tr["root"]; hinge = tr["hinge"]
    for o in bpy.data.objects:
        if o.name.startswith(("his tipper truck tailgate",)): o.hide_render = True; o.hide_viewport = True
    T_DOWN = 2.6                                      # (q2r PLAN: still 4 needs a change) he pushes the lever back and the empty bed comes down
    TH = lambda t: 14.0 + (18.0 * W(t, 0.0, 0.55) + 20.0 * W(t, T_AB + 0.02, 0.6)) * (1.0 - W(t, T_DOWN, 0.5))      # the bed's tip, degrees: two pulls of the lever
    sc.frame_set(1); bpy.context.view_layer.update()
    H0 = hinge.matrix_world.copy(); H0i = H0.inverted()
    def hinge_at(t):
        return troot.matrix_world @ Matrix.Translation(hinge.location) @ Matrix.Rotation(R(TH(t)), 4, 'X')
    tail_l = H0i @ (troot.matrix_world @ Vector((0, 1.83, 0.7)))
    front_l = H0i @ (troot.matrix_world @ Vector((0, -0.6, 0.7)))
    up_t = hinge_at(1.0) @ tail_l; up_f = hinge_at(1.0) @ front_l
    SG = 1.0 if up_f.z > up_t.z else -1.0                     # (the kit's tip sign: the front goes UP)
    if SG < 0:
        hinge_at = lambda t: troot.matrix_world @ Matrix.Translation(hinge.location) @ Matrix.Rotation(-R(TH(t)), 4, 'X')
    for f in range(1, NF + 1):
        hinge.rotation_euler = (SG * R(TH((f - 1) / FPS)), 0, 0); hinge.keyframe_insert("rotation_euler", frame=f)
    print("S2 tail", tuple(round(v, 2) for v in hinge_at(0.0) @ tail_l), "front at 1s", tuple(round(v, 2) for v in hinge_at(1.0) @ front_l), "sign", SG, flush=True)
    # the load: black rock heaped in the bed, sliding out over the open tail as the bed tips past each one's angle
    rk = lw_random.Random(12)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    dl = (tail_l - front_l).normalized()
    load = []
    for k in range(54):
        q = Vector((rk.uniform(-0.5, 0.5), rk.uniform(-0.55, 1.6), 0.0))
        r = rk.uniform(0.06, 0.12)
        lp = H0i @ (troot.matrix_world @ Vector((q.x, q.y, 0.72 + r * 0.6 + 0.25 * rk.random())))
        ang = 2.0 + 50.0 * (1.0 - (q.y + 0.55) / 2.15) * rk.uniform(0.7, 1.1)       # the rock at the tail goes first
        o = lw_block("tipped rock", (0, 0, 0), r, rock_m, rk); load.append((o, lp, ang, r))
    lands = []
    for o, lp, ang, r in load:
        tr_ = None; ex = None; land = None; sp = rk.uniform(-1, 1)
        if ang < TH(0.0): tr_ = -(TH(0.0) - ang) / 22.0           # (q2a: the first rock landed at 0.63s: the pour is under way at frame 1)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if tr_ is None and TH(t) >= ang: tr_ = t
            if tr_ is None or t < tr_:
                p = hinge_at(t) @ lp
            else:
                s = t - tr_; d = 0.5 * 5.0 * s * s
                lq = lp + dl * d
                if ex is None and (lq - tail_l).dot(dl) < 0:
                    p = hinge_at(t) @ lq
                else:
                    if ex is None:
                        ex = (t, hinge_at(t) @ lq, (hinge_at(t).to_3x3() @ dl) * (5.0 * s) + Vector((0.25 * sp, 0, 0)))
                    te, pe, ve = ex
                    if land is None:
                        u = t - te; p = pe + ve * u + Vector((0, 0, -4.9 * u * u))
                        zs = surface(p.x, p.y, t) + r * 0.5
                        if p.z <= zs: p.z = zs; land = (t, p.copy()); lands.append(land)
                    else:
                        p = land[1]
            o.location = p; o.keyframe_insert("location", frame=f)
            o.rotation_euler = (2.5 * max(0.0, t - (tr_ if tr_ is not None else 99.0)) if not land else o.rotation_euler.x, 0.4 * sp, sp); o.keyframe_insert("rotation_euler", frame=f)
    lands.sort(key=lambda a: a[0])
    print("S2 rock lands", len(lands), "first", round(lands[0][0], 2) if lands else None, flush=True)
    for k, t0 in enumerate((0.05, 0.62, 1.05)):
        FX.dust_puff(base=(S2_XT + 0.35 + 0.1 * (k - 1), -0.35, 0.2), w=0.5,       # (q2e: off the line from the lens to his face)
                     h=1.2 + 0.5 * k, t0=t0, dur=1.6, col=(0.55, 0.52, 0.48), dens=6.0, seed=3.3 + k, name=f"dust off the tipped rock {k}")
    # ---- him: at the tip lever on the truck's side, between it and the house, facing out to the wall (q2a: from up
    # the alley between them the wall, the rock and the house were all out of the picture: the lens is out past the row)
    data = load_data()
    PL = Vector((S2_XT - 1.12, 0.75, 0.0))        # (q2c: at the tail's corner, so the pour is beside him in a close frame)
    YL = yaw_of(-0.12, -1.0)
    data.place(PL.x, PL.y, math.degrees(YL))
    kit = hard_hat(data)
    sc.frame_set(1); bpy.context.view_layer.update()
    fw = data.forward(); fw.z = 0; fw.normalize(); lf = Vector((-fw.y, fw.x, 0.0))
    # the lever: a steel rod off the chassis, its T-bar handle in front of his chest; it swings toward him as he pulls
    steel = lw_paint("tip lever steel", "#2A2C2E", rough=0.45); grip_m = lw_paint("tip lever grip", "#D23A22", rough=0.6)
    PIV = Vector((S2_XT - 0.66, PL.y - 0.16, 0.12))
    piv = K.empty("tip lever pivot", tuple(PIV))
    BAR = PL + fw * 0.15 + Vector((0, 0, 0.34))               # the T-bar's centre, pushed forward (the bed down)
    ROD_TOP = Vector((PIV.x + 0.12 * (1 if PL.x > PIV.x else -1), BAR.y, BAR.z))
    K.capsule("tip lever rod", tuple(PIV), tuple(ROD_TOP), 0.012, steel, parent=piv)
    K.capsule("tip lever bar", tuple(ROD_TOP), tuple(BAR + lf * -0.1), 0.011, steel, parent=piv)
    K.capsule("tip lever grip", tuple(BAR + lf * 0.08), tuple(BAR + lf * -0.1), 0.016, grip_m, parent=piv)
    PS_ = 1.0 if (PIV + Matrix.Rotation(0.2, 3, 'X') @ (BAR - PIV) - PL).length < (BAR - PL).length else -1.0       # the way that brings it to him
    PULL = lambda t: PS_ * (R(11.0) * W(t, 0.0, 0.5) + R(11.0) * W(t, T_AB + 0.02, 0.55)) * (1.0 - 0.7 * W(t, T_DOWN, 0.5))      # (q2s REACH: pushed right back it was 3 cm past his hand)      # (q2f READ: a bigger pull, his weight going with it)       # toward him about the pivot's x
    for f in range(1, NF + 1):
        piv.rotation_euler = (PULL((f - 1) / FPS), 0, 0); piv.keyframe_insert("rotation_euler", frame=f)
    def on_bar(t, u):
        a = PULL(t); rx = Matrix.Rotation(a, 3, 'X')
        return PIV + rx @ (BAR + lf * u - PIV)
    YW0 = data.arm.rotation_euler.z
    PE = Vector((S2_HOUSE[0] + 0.25, 0.55, 0.0))       # (q2g) at the house's front by its door steps, the wall's foot beside him: he walks there FACING the low lens
    YWK = yaw_of(PE.x - PL.x, PE.y - PL.y)
    while YWK - YW0 > math.pi: YWK -= 2 * math.pi
    while YWK - YW0 < -math.pi: YWK += 2 * math.pi
    for f in range(1, NF + 8):          # (coordinator 11-27: he never lets go on screen: no walk, no release) (q2b: on the sheet he stood still a second) round to the pour as the bed goes up, and back
        t = (f - 1) / FPS; SW = 0.035 * W(t, 0.0, 0.5) - 0.02 * W(t, 0.5, 0.15) + 0.04 * W(t, T_AB, 0.5)      # (q2o REACH: no weight back off the bar now he stays at it) (q2c: READ, he stood 1.7s: his weight goes back on each pull)
        data._kobj(t, loc=tuple(PL - fw * SW), rot=YW0 - R(24) * W(t, 0.15, 0.4) + R(24) * W(t, 0.95, 0.45))      # (q2e: STEADY, he turns to go before he goes)
    sides = sorted("LR", key=lambda s_: (acts._shoulder(data, s_) - PL).dot(lf), reverse=True)      # sides[0]: his hand toward the truck
    def body_at(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        m = (acts._shoulder(data, "L") + acts._shoulder(data, "R")) / 2; f_ = data.forward(); f_.z = 0; f_.normalize()
        return m, f_, Vector((-f_.y, f_.x, 0.0))
    # (q2f/q2g: let go to a relaxed arm, the hands swept through his coat and whipped): off the bar the hands come to
    # rest in front of his belly, held to his body as he goes; the shading hand goes up from there (FK, below)
    # (q2a: on the sheet he stood still 1.5s): he throws his weight back on each pull, and twists to watch the rock go
    LEAN = lambda t: -18 * W(t, 0.0, 0.5) + 12 * W(t, 0.52, 0.18) - 20 * W(t, T_AB, 0.5)
    lw_layer(data, "spine", lambda t: (LEAN(t) * (1 - W(t, T_LET, 0.5)), 0, 0), 0.0, DUR + 0.4)
    lw_layer(data, "spine", lambda t: (0, 0, 20 * W(t, T_AB - 0.1, 0.5)), 0.0, DUR + 0.4)      # (q2p REACH: unwinding it took his hand off the bar)
    # he lets go and goes to the wall's foot in front of the house, by its door (in the wide, behind his truck); there he
    # turns to the wall and looks up at it
    # (q2i-q2n: five rounds on the hands after a release; coordinator 11-27: remove the release) both hands stay on the
    # lever on every frame of the shot; the last set-up is a new lens on him at the lever, from up the wall's face
    for sd, u in ((sides[0], 0.05), (sides[1], -0.06)):
        data.reach(sd, lambda t, u=u: on_bar(t, u) + Vector((0, 0, 0.012)), 0.0, DUR + 0.5, lead=0.05, back=None, elbow_out=0.3)
    CD = PL + Vector((0.2, -1.5, 1.9)); LD = PL + Vector((0.1, 0.0, 0.25))     # up the wall's face, down at him at its foot, the lever whole beside him (q2o EDGE)
    TAILP = hinge_at(0.8) @ tail_l
    CREST = Vector((PL.x, -s2_base(S2_HS[2]) / 2 + 0.6, S2_HS[2]))
    data.look_at(TAILP + Vector((0, 0, 0.3)), 0.0, max_yaw=50, max_pitch=30, blend=0.0)
    data.look_at(Vector((S2_XT, -0.6, 1.4)), T_AB - 0.1, max_yaw=60, max_pitch=40, blend=0.6)       # the rock going onto the wall
    data.look_at(Vector((-17.0, 6.5, 10.5)), T_CUT - 0.25, max_yaw=35, max_pitch=20, blend=0.5)     # (q2o KEYS: the back of his head to the wide) round over his shoulder at the town
    data.look_at(CD + Vector((0, -0.6, 2.2)), T_WB - 0.45, max_yaw=35, max_pitch=50, blend=0.6)      # (q2q PLAN: a new pose) right up at the wall's top                         # (q2g) up at it
    data.expression("determined", 0.0, T_WB, blend=0.15)
    data.expression("surprised", T_WB, DUR + 1.0, blend=0.3)
    SHADE = lambda sg: ((-20, 0, -sg * 96), (-20, 0, -sg * 52), (0, 0, 0))                       # a hand up over his eyes
    HIP = lambda sg: ((-6, 0, -sg * 64), (-98, 0, sg * 30), (0, 0, 0))                           # a fist on his hip
    def pose(t, P_, sides_="LR"):
        for sd in sides_:
            for bn, r_ in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), P_(-1 if sd == "L" else 1)): data._k(bn, t, rot=r_)
    data.finish()
    # ---- the lens: out past the low row, low, back at him, the truck's tail pouring rock at the right and the house at
    # the left; then from up high over the rising wall; CUT WIDE across the town (he is behind his truck); then from up
    # the wall's face, down at him at its foot by the house's door
    LENS_B = 85.0
    him = [data.arm] + list(data.arm.children_recursive) + [o for o in bpy.data.objects if o.name.startswith(("hard hat", "hi-vis"))]
    for o in set(him):
        if o.type not in ('MESH', 'CURVE', 'ARMATURE'): continue
        o.hide_render = False; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=F(T_CUT) - 1)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=F(T_CUT)); o.keyframe_insert("hide_render", frame=F(T_WB) - 1)
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_WB))
    CA0 = PL + Vector((0.15, -2.6, 0.9)); LA0 = CA0 + Vector((0.2, 6.0, -1.0))     # (q2c: out over the low row, the pour beside him at the right, the house behind at the left)
    CA, LA = compose.frame_data(data, CA0, LA0, 35.0, face_at=(0.42, 0.6), height=0.36, t=0.25)
    CB0 = PL + Vector((1.5, -4.4, 4.6)); LB0 = PL + Vector((0.0, 0.0, 0.3))      # (q2d: from the truck's side of him, so the pour is in frame at the right)      # from up over the rising wall, long: its face below us, him at its foot, the house beyond
    CB, LB = compose.frame_data(data, CB0, LB0, LENS_B, face_at=(0.38, 0.6), height=0.34, t=1.2)
    # (q2c: from up the wall the wall was behind the lens; q2e: the solver backed the lens behind the house's corner) set
    # by hand: low and close along the house's front, wide, tipped up so the wall rises over him at the right
    # (q2o) CD/LD: set at the lever above, up the wall's face
    print("S2 CAM A", tuple(round(v, 2) for v in CA), "look", tuple(round(v, 2) for v in LA), "B", tuple(round(v, 2) for v in CB), "look", tuple(round(v, 2) for v in LB),
          "D", tuple(round(v, 2) for v in CD), "surface there", round(surface(CD.x, CD.y, DUR), 2), flush=True)
    cam = K.camera(tuple(CA), tuple(LA), lens=35.0, fstop=11.0)
    WC = Vector((-17.0, 6.5, 10.5)); WL = Vector((2.0, -9.0, 1.5))      # (q2c: higher, so the flow shows over the crest)      # along the wall from the town's end: the wall over the house, the lava and the eruption beyond it                 # THE WIDE: across the town, high, the wall over the house, the lava beyond
    lw_cut(cam, lambda t: ((CA, LA) if t < T_AB else (CB, LB) if t < T_CUT else (CD, LD)) + (data.pos() + Vector((0, 0, 0.4)),),
           lambda t: (WC, WL, Vector((1.0, 0.0, 2.0))), T_CUT, T_WB, 35.0, 20.0)
    for f in range(F(T_AB), F(T_CUT)):                      # the high set-up is a long lens
        cam.data.lens = LENS_B; cam.data.keyframe_insert("lens", frame=f)
    for f in range(F(T_WB), NF + 8):                        # the low set-up by the house is a wider lens: the wall over him
        cam.data.lens = 50.0; cam.data.keyframe_insert("lens", frame=f)
    from character import _fcurves
    for fc in _fcurves(cam.data.animation_data.action):
        for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
    wall_body = lambda: meshes([w["body"] for w in walls])
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("tip lever",), cutaway=(T_CUT, T_WB),
                boxes=[],
                conseq=[("he tips the load of rock off his truck onto the low row of rock in a puff of dust", lambda: [o for o, *_ in load], 0.0, T_AB, {"whole": False, "moves": True}),
                        ("the wall of rock grows roof-high beside the house", lambda: meshes([walls[1]["body"]]), 0.95, T_CUT, {"whole": False}),
                        ("the finished wall stands taller than the house, the lava out beyond it", wall_body, T_CUT, T_WB, {"whole": False})])
