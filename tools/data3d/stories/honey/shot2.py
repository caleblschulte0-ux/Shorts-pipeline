"""BEAT 3, A QUARTER OF THE PRICE: the yard outside his honey house. Two flagpoles beside a tall price board marked
in euros a kilo. Hand over hand he hoists the white RICE SYRUP flag: it stops at 0.50. Then he hoists the gold HONEY
flag and it climbs past 1.00, 1.50, 2.00 to 2.17, four times as high (DG SANTE: imported honey 2.17 EUR/kg in 2021,
rice syrup about 0.40-0.60 EUR/kg)."""

S3_Z0 = 0.3                            # the price board's zero (the flags start here)
S3_PER = 0.36                          # metres per euro: 2.17 is 0.78 m up
S3_POLES = (Vector((0.0, 0.2, 0.0)), Vector((0.4, 0.2, 0.0)))   # syrup pole, honey pole
S3_DATA = Vector((0.2, 0.13, 0.0))     # he stands between them


def place_honey_house():
    """THE YARD OUTSIDE HIS HONEY HOUSE: the honey house's weathered plank wall across the back with a sunny window full
    of his jars, its open door, a tin roof edge, his steel extractor and stacked hive boxes by the wall, frames leaning
    to dry, a flagstone path through the grass, the stump he uses as a table, flowers, and the hill behind."""
    rnd = hw_random.Random(33)
    grass = hw_noise("yard grass", "#5E8A32", "#94B850", scale=26, rough=0.95, bump=1.0, detail=8, lo=0.36, hi=0.66)
    K.box("yard ground", (0, 4, -0.01), (30, 30, 0.02), grass, bev=0)
    stone = hw_noise("flagstone", "#A79F90", "#C4BCAC", scale=9, rough=0.85, bump=0.7, detail=6)
    x = -2.2
    while x < 2.4:                                     # the flagstone path he rolls it along
        w = rnd.uniform(0.18, 0.28)
        for yy in (-0.12, 0.12):
            o = K.box("flagstone", (x + w / 2, yy + rnd.uniform(-0.02, 0.02), 0.006), (w - 0.025, 0.21, 0.016), stone, bev=0.006)
            o.rotation_euler = (0, 0, rnd.uniform(-0.08, 0.08))
        x += w
    blade = [K.mat(f"blade {c}", c, rough=0.8) for c in ("#5E8A2E", "#7AA23C", "#8DB24A")]
    petals = [K.mat(f"flower {c}", c, rough=0.6) for c in ("#F2D43A", "#F4F0E6", "#C96BC0", "#E0583A")]
    for k in range(260):
        x, y = rnd.uniform(-2.0, 2.2), rnd.uniform(-1.4, 0.9)
        if -0.3 < y < 0.3: continue
        for b in range(3):
            h = rnd.uniform(0.06, 0.13); a = rnd.uniform(0, 6.28); ln = rnd.uniform(0.1, 0.35)
            o = K.box("yard blade", (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), h / 2), (0.007, 0.002, h), rnd.choice(blade), bev=0)
            o.rotation_euler = (ln * math.sin(a), -ln * math.cos(a), a)
        if k % 3 == 0:
            K.sph("yard flower", (x, y, rnd.uniform(0.08, 0.14)), rnd.uniform(0.012, 0.018), rnd.choice(petals), seg=10, ring=6)
    # the honey house: a long plank wall across the back with a window, a door, a tin roof edge
    WY = 1.05
    plank = hw_noise("weathered planks", "#9C7A52", "#B8966A", scale=3, rough=0.85, bump=0.5, detail=6, stretch=(6, 1, 1))
    for k in range(34):
        xx = -2.6 + k * 0.155
        if 0.55 < xx < 0.95: continue                   # the open door
        K.box("house plank", (xx, WY + rnd.uniform(-0.006, 0.006), 0.85), (0.15, 0.04, 1.7), plank, bev=0.006)
    K.box("door frame top", (0.75, WY - 0.03, 1.32), (0.46, 0.06, 0.06), plank, bev=0.006)
    K.box("door dark", (0.75, WY + 0.1, 0.66), (0.42, 0.02, 1.3), K.mat("inside dark", "#2E241C", rough=0.9), bev=0)
    door = K.box("open door", (0.98, WY - 0.2, 0.65), (0.04, 0.42, 1.28), hw_wood("door wood", "#6E4A2A", "#8A5E36"), bev=0.006)
    tin = K.mat("roof tin", "#8E969C", rough=0.4, metal=0.7)
    for k in range(18):
        K.box("roof tin sheet", (-2.6 + 0.3 * k, WY - 0.1, 1.78), (0.29, 0.5, 0.012), tin, bev=0.002).rotation_euler = (-0.25, 0, 0)
    frame_m = K.mat("window frame", "#EEE8DA", rough=0.4)
    K.box("window frame", (-0.55, WY - 0.03, 1.0), (0.78, 0.04, 0.56), frame_m, bev=0.006)
    K.box("window inside", (-0.55, WY - 0.01, 1.0), (0.7, 0.02, 0.48), K.mat("window inside warm", "#4A3626", rough=0.9), bev=0)
    K.box("window sill", (-0.55, WY - 0.08, 0.71), (0.86, 0.12, 0.03), frame_m, bev=0.004)
    shelf = hw_wood("window shelf", "#7A5A38", "#946E46")
    for z in (0.78, 0.99):
        K.box("window shelf", (-0.55, WY - 0.03, z), (0.7, 0.08, 0.015), shelf, bev=0.002)
        for k in range(6):
            jar(f"window jar {z} {k}", (-0.85 + k * 0.12, WY - 0.04, z + 0.008), r=0.035, h=0.09, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY")
    K.box("window mullion", (-0.55, WY - 0.06, 1.0), (0.02, 0.01, 0.5), frame_m, bev=0)
    # by the wall: the extractor, a stack of hive boxes, frames leaning to dry
    steel = K.mat("extractor steel", "#C9CED4", rough=0.25, metal=0.85)
    K.cyl("extractor drum", (1.45, WY - 0.35, 0.36), 0.22, 0.52, steel, v=48, bev=0.01)
    K.cyl("extractor lid", (1.45, WY - 0.35, 0.64), 0.23, 0.03, steel, v=48, bev=0.006)
    K.box("extractor crank", (1.45, WY - 0.35, 0.72), (0.02, 0.2, 0.02), steel, bev=0.003)
    white = hw_noise("hive paint", "#F4F1E8", "#E2DED2", scale=8, rough=0.7, bump=0.15)
    for k in range(4):
        K.box("stacked hive box", (-1.45, WY - 0.3, 0.07 + 0.135 * k), (0.32, 0.28, 0.125), white, bev=0.004)
    comb = hw_noise("comb wax", "#E8B033", "#F2CC5E", scale=60, rough=0.5, bump=0.6)
    fw_m = hw_wood("frame wood", "#C8A878", "#D8BC8C", scale=6)
    for k in range(5):
        o = K.box("drying frame", (-1.05 + 0.07 * k, WY - 0.12, 0.2), (0.02, 0.3, 0.42), fw_m, bev=0.002); o.rotation_euler = (0.25, 0, 1.57)
        o = K.box("drying comb", (-1.05 + 0.07 * k, WY - 0.13, 0.2), (0.012, 0.26, 0.36), comb, bev=0.001); o.rotation_euler = (0.25, 0, 1.57)
    K.cyl("water butt", (2.1, WY - 0.3, 0.3), 0.2, 0.6, hw_wood("butt wood", "#7A5A38", "#946E46", scale=8), v=32, bev=0.01)
    # the hill behind the roof, with the hives on it
    hill = hw_noise("far hill", "#6F9A40", "#A2BD62", scale=9, rough=0.95, bump=0.5, detail=5)
    K.sph("far hill", (0, 9, -3.6), 6.0, hill, scale=(3.0, 1.0, 0.9))
    leaf = hw_noise("tree leaves", "#4E7E32", "#6E9C40", scale=10, rough=0.85, bump=0.4)
    for k, (xx, yy) in enumerate(((-2.4, 2.4), (2.6, 2.2), (0.2, 3.2), (-1.0, 3.6))):
        K.cyl("tree trunk", (xx, yy, 0.8), 0.08, 1.6, hw_wood("tree bark", "#5A4330", "#6E5440", scale=8), v=12, bev=0.01)
        for jj in range(5):
            K.sph("tree crown", (xx + rnd.uniform(-0.4, 0.4), yy + rnd.uniform(-0.2, 0.2), 1.9 + rnd.uniform(-0.2, 0.3)), rnd.uniform(0.45, 0.6), leaf, seg=20, ring=12)

    def light():
        return village_light(sun_elev=40, sun_az=-30, sun=4.2, sky=0.33)
    return light


def s3_pole(name, base, col, word, price, side):
    """a flagpole with its halyard, and a flag that rides up it on the side away from him (the flag's root moves)"""
    pole = K.mat("pole white", "#EDEAE2", rough=0.4)
    K.cyl(name + " pole", tuple(base + Vector((0, 0, 0.66))), 0.013, 1.32, pole, v=16, bev=0.003)
    K.sph(name + " finial", tuple(base + Vector((0, 0, 1.335))), 0.024, K.mat("finial gold", "#D2A23A", rough=0.3, metal=0.8))
    K.cyl(name + " foot", tuple(base + Vector((0, 0, 0.02))), 0.065, 0.04, hw_noise("pole stone", "#9A958A", "#B5AFA2", scale=10), v=24, bev=0.006)
    K.box(name + " pulley arm", tuple(base + Vector((-side * 0.03, -0.035, 1.29))), (0.05, 0.07, 0.012), pole, bev=0.003)
    flag = K.empty(name + " flag", (0, 0, 0))
    K.box(name + " cloth", (side * 0.125, -0.004, 0), (0.23, 0.006, 0.27), K.mat(f"flag {col}", col, rough=0.7), bev=0.004, parent=flag)
    ink = hw_ink(f"flag ink {name}", "#2A1E12" if col != "#F2B02A" else "#3A1E04")
    K.text(name + " word", word, (side * 0.125, -0.0085, 0.055), 0.03, (math.pi / 2, 0, 0), ink, extrude=0.0005, parent=flag)
    K.text(name + " price", price, (side * 0.125, -0.0085, -0.045), 0.066, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=flag)
    hw_local(flag)
    return flag


def shot2():
    """A QUARTER OF THE PRICE. Between two flagpoles and the price board: hand over hand he hoists the RICE SYRUP flag
    and it stops at 0.50; he hops round to the HONEY pole and hoists its gold flag past 1.00, 1.50, 2.00 to 2.17;
    he points up at it and spreads his hands at us."""
    T_S0, T_S1 = 0.06 * DUR, 0.3 * DUR             # the syrup flag up to 0.50, two pulls
    T_H0, T_H1 = 0.42 * DUR, 0.8 * DUR            # the honey flag up to 2.17, three pulls
    T_PT, T_SPREAD = 0.85 * DUR, 0.9 * DUR
    NS, NH = 2, 3
    light = place_honey_house()
    W = hw_win
    board = hw_wood("price board", "#F0E6CC", "#E2D6B8", scale=3)
    ink = hw_ink("board ink", "#2A1E12")
    bx = (S3_POLES[0].x + S3_POLES[1].x) / 2; by = S3_POLES[0].y + 0.07
    K.box("price board", (bx, by, S3_Z0 + 0.47), (0.36, 0.02, 0.98), board, bev=0.006)
    K.text("price board head", "EUROS A KILO", (bx, by - 0.012, S3_Z0 + 0.92), 0.026, (math.pi / 2, 0, 0), ink, extrude=0.0006)
    for k in range(0, 5):
        v = 0.5 * k; z = S3_Z0 + S3_PER * v
        K.box("board line", (bx, by - 0.011, z), (0.34, 0.002, 0.005 if k else 0.009), ink, bev=0)
        if k: K.text("board euro", f"{v:.2f}", (bx + 0.13, by - 0.012, z + 0.02), 0.028, (math.pi / 2, 0, 0), ink, extrude=0.0006)
    sf = s3_pole("syrup", S3_POLES[0], "#FAFAF4", "RICE SYRUP", "0.50", -1)
    hf = s3_pole("honey", S3_POLES[1], "#F2B02A", "HONEY", "2.17", 1)
    rope_m = K.mat("rope", "#8A6A3A", rough=0.9)
    rope_x = (S3_POLES[0].x + 0.025, S3_POLES[1].x - 0.025); rope_y = S3_DATA.y - 0.02
    for i in (0, 1):
        K.cyl(("syrup", "honey")[i] + " rope", (rope_x[i], rope_y, 0.78), 0.008, 1.0, rope_m, v=8, bev=0)
        K.box(("syrup", "honey")[i] + " cleat", (rope_x[i] + (0.02, -0.02)[i], S3_POLES[i].y, 0.25), (0.012, 0.012, 0.05), board, bev=0.002)
    flags = (sf, hf); tops = (S3_Z0 + S3_PER * 0.5, S3_Z0 + S3_PER * 2.17)
    def flag_z(i, t):
        (t0, t1), n = ((T_S0, T_S1), NS) if i == 0 else ((T_H0, T_H1), NH)
        u = max(0.0, min(1.0, (t - t0) / (t1 - t0))) * n
        k = min(int(u), n - 1); fr = u - k
        return S3_Z0 + (tops[i] - S3_Z0) * (k + ease(min(1.0, fr * 1.25))) / n
    # ---- him: between the poles, turned to the pole he is hoisting, his near hand hand over hand on its rope
    data = load_data()
    data.place(S3_DATA.x, S3_DATA.y, -25.0)
    hat = bee_hat(data)
    tug = lambda t, t0, t1, n: (math.sin(math.pi * n * max(0.0, min(1.0, (t - t0) / (t1 - t0))))) ** 2 * W(t, t0, 0.1) * (1 - W(t, t1 - 0.05, 0.1))
    T_TURN = (T_S1 + T_H0) / 2; T_HEAVE = T_H0 + 0.625 * (T_H1 - T_H0)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        yaw = -25 + 50 * W(t, T_TURN - 0.2, 0.4) - 25 * W(t, T_PT + 0.1, 0.35)
        z = (-0.05 * tug(t, T_S0, T_S1, NS) - 0.055 * tug(t, T_H0, T_H1, NH)
             + 0.05 * hw_kick(t - (T_TURN - 0.15), 0.15) + 0.06 * hw_kick(t - T_SPREAD, 0.15) + 0.04 * hw_kick(t - T_HEAVE, 0.16))
        sway = 0.045 * math.sin(math.pi * NH * max(0.0, min(1.0, (t - T_H0) / (T_H1 - T_H0)))) * W(t, T_H0, 0.2) * (1 - W(t, T_H1 - 0.1, 0.2))
        sway += 0.05 * math.sin(math.pi * NS * max(0.0, min(1.0, (t - T_S0) / (T_S1 - T_S0)))) * W(t, T_S0, 0.2) * (1 - W(t, T_S1 - 0.1, 0.2))
        data._kobj(t, loc=(S3_DATA.x, S3_DATA.y - 0.6 * sway, z), rot=math.radians(yaw + 120 * sway))
    hw_layer(data, "spine", lambda t: (12 * tug(t, T_S0, T_S1, NS) + 13 * tug(t, T_H0, T_H1, NH) - 5 * hw_kick(t - T_HEAVE, 0.2) - 6 * W(t, T_H1 - 0.1, 0.3) * (1 - W(t, T_SPREAD, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    rope_at = lambda i, z: Vector((rope_x[i], rope_y, z))
    def pulls(sd, i, t0, t1, n):
        ks = []
        for k in range(n):
            a = t0 + (t1 - t0) * k / n; b = t0 + (t1 - t0) * (k + 0.5) / n
            ks += [(a + 0.02, hw_rel(data, sd, a + 0.02, rope_at(i, 0.5))), (b, hw_rel(data, sd, b, rope_at(i, 0.37)))]
        return ks
    REST, HIP = (0.07, 0.1, -0.13), (0.09, 0.05, -0.15)
    # the near hand on the rope; the far hand on his hip, then both up at the end
    lk = [(0.0, hw_rel(data, lf, 0.0, rope_at(0, 0.46)))] + pulls(lf, 0, T_S0, T_S1, NS)
    lk += [(T_S1 + 0.25, (0.1, 0.12, -0.06)), (T_H0, HIP), (T_H1 + 0.1, HIP), (T_SPREAD, (0.1, 0.15, 0.02)), (DUR + 0.3, (0.1, 0.15, 0.03))]
    rk = [(0.0, REST), (T_S0, HIP), (T_S1 - 0.25, HIP), (T_H0 - 0.22, hw_rel(data, rt, T_H0 - 0.22, rope_at(1, 0.49)))] + pulls(rt, 1, T_H0, T_H1, NH)
    rk += [(T_PT, (0.13, 0.1, 0.03)), (T_SPREAD - 0.05, (0.13, 0.12, 0.04)), (T_SPREAD + 0.15, (0.1, 0.15, 0.02)), (DUR + 0.3, (0.1, 0.15, 0.03))]
    for ks in (rk, lk):
        ks.sort(key=lambda k: k[0])
        i = 1
        while i < len(ks):
            if ks[i][0] <= ks[i - 1][0] + 0.03: ks.pop(i)
            else: i += 1
    data.reach(rt, hw_hand(data, rt, rk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.5)
    data.reach(lf, hw_hand(data, lf, lk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.5)
    LENS = Vector((0.2, -1.38, 0.7))
    data.look_at(Vector((S3_POLES[0].x - 0.15, 0.2, tops[0])), 0.0, max_yaw=45, max_pitch=30, blend=0.0)
    data.look_at(LENS, T_S1 - 0.05, max_yaw=45, blend=0.15)
    data.look_at(Vector((S3_POLES[1].x + 0.15, 0.2, 0.75)), T_H0 + 0.3, max_yaw=45, max_pitch=35, blend=0.2)
    data.look_at(LENS, T_H0 + 1.0, max_yaw=45, blend=0.2)
    data.look_at(Vector((S3_POLES[1].x + 0.15, 0.2, tops[1])), T_H1 - 0.35, max_yaw=45, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_SPREAD - 0.2, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_S1)
    data.expression("pleased", T_S1 + 0.05, T_H0 - 0.05, blend=0.15)
    data.expression("determined", T_H0, T_H1 - 0.05, blend=0.15)
    data.expression("surprised", T_H1, T_SPREAD - 0.1, blend=0.1)
    data.expression("wry", T_SPREAD, DUR + 1.0, blend=0.18)
    data.finish()
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for i in (0, 1):
            flags[i].location = (S3_POLES[i].x + (-0.013, 0.013)[i], S3_POLES[i].y - 0.01, flag_z(i, t)); flags[i].keyframe_insert("location", frame=f)
    cam = K.camera(tuple(LENS), (0.2, 0.15, 0.66), lens=32, fstop=8.0)
    camera_path(cam, lambda t: (LENS + Vector((0.0, 0.06, 0.03)) * ease(t / DUR), Vector((0.2, 0.15, 0.64 + 0.04 * ease(t / DUR))), Vector((0.2, 0.15, 0.66))))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("syrup rope", "honey rope"),
                conseq=[("the HONEY flag climbs to 2.17, the RICE SYRUP flag stopped at 0.50", lambda: meshes([sf, hf]) + meshes_of("price board", "board", "syrup pole", "honey pole"), T_S1, DUR, {"hero": True}),
                        ("he hoists the honey flag hand over hand", lambda: meshes([hf]), T_H0, T_H1, {"moves": True}),
                        ("the syrup flag stops at 0.50", lambda: meshes([sf]), T_S0, T_S1 + 0.5, {"moves": True})])
