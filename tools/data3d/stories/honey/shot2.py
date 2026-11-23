"""BEAT 3, A QUARTER OF THE PRICE: the yard outside his honey house. Two flagpoles beside a tall price board marked
in euros a kilo. Hand over hand he hoists the white RICE SYRUP flag: it stops at 0.50. Then he hoists the gold HONEY
flag and it climbs past 1.00, 1.50, 2.00 to 2.17, four times as high (DG SANTE: imported honey 2.17 EUR/kg in 2021,
rice syrup about 0.40-0.60 EUR/kg)."""

S3_Z0 = 0.3                            # the price board's zero: a flag's top edge reads its price against it
S3_PER = 0.36                          # metres per euro: 2.17 is 0.78 m up
S3_POLES = (Vector((-0.16, 0.34, 0.0)), Vector((0.3, 0.34, 0.0)))   # syrup pole, honey pole, the board behind both
S3_DATA = Vector((0.625, 0.17, 0.0))    # beside the honey pole, at its halyard


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
    # the honey house: a tall plank wall across the back with a deep-set window and an open door with a lit inside
    WY = 1.05
    plank = hw_noise("weathered planks", "#9C7A52", "#B8966A", scale=3, rough=0.85, bump=0.5, detail=6, stretch=(6, 1, 1))
    wx, wz, ww, wh = -1.05, 1.03, 0.74, 0.62          # out past the board: a window cut by the frame edge cuts its jars
    for k in range(34):
        xx = -2.6 + k * 0.155
        if 0.55 < xx < 0.95: continue                   # the open door
        if wx - ww / 2 - 0.08 < xx < wx + ww / 2 + 0.08: K.box("house plank", (xx, WY, 0.33), (0.15, 0.04, 0.66), plank, bev=0.006); K.box("house plank", (xx, WY, 1.84), (0.15, 0.04, 0.88), plank, bev=0.006); continue
        K.box("house plank", (xx, WY + rnd.uniform(-0.006, 0.006), 1.14), (0.15, 0.04, 2.28), plank, bev=0.006)
    trim = hw_wood("door trim", "#5E4026", "#74502E", scale=6)
    K.box("door post", (0.535, WY - 0.03, 0.68), (0.05, 0.06, 1.36), trim, bev=0.006)
    K.box("door post", (0.965, WY - 0.03, 0.68), (0.05, 0.06, 1.36), trim, bev=0.006)
    K.box("door lintel", (0.75, WY - 0.03, 1.38), (0.48, 0.06, 0.06), trim, bev=0.006)
    K.box("door top planks", (0.75, WY, 1.84), (0.46, 0.04, 0.88), plank, bev=0.006)
    inside = K.mat("inside wall", "#8A6A48", rough=0.9)
    K.box("inside back wall", (0.75, WY + 0.6, 0.8), (0.6, 0.02, 1.6), inside, bev=0)
    K.box("inside floor", (0.75, WY + 0.3, 0.005), (0.6, 0.6, 0.01), K.mat("inside floor", "#5A4430", rough=0.9), bev=0)
    for z in (0.5, 0.8, 1.1):
        K.box("inside shelf", (0.75, WY + 0.52, z), (0.5, 0.14, 0.02), hw_wood("inside shelf", "#7A5A38", "#946E46"), bev=0.003)
        for k in range(5):
            jar(f"inside jar {z} {k}", (0.57 + k * 0.09, WY + 0.5, z + 0.012), r=0.03, h=0.08, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY")
    lamp = K.sph("inside lamp", (0.75, WY + 0.3, 1.3), 0.04, K.mat("inside lamp", "#FFE2A0", rough=0.3, emit=4.0))
    door = K.box("open door", (0.98, WY - 0.2, 0.67), (0.04, 0.42, 1.3), hw_wood("door wood", "#6E4A2A", "#8A5E36"), bev=0.006)
    K.sph("door knob", (0.955, WY - 0.36, 0.68), 0.018, K.mat("knob brass", "#C8A040", rough=0.3, metal=0.8))
    frame_m = K.mat("window frame", "#EEE8DA", rough=0.4)
    for dx, sx in ((-ww / 2, 0.05), (ww / 2, 0.05)):
        K.box("window jamb", (wx + dx, WY - 0.02, wz), (sx, 0.1, wh + 0.05), frame_m, bev=0.006)
    K.box("window head", (wx, WY - 0.02, wz + wh / 2), (ww + 0.05, 0.1, 0.05), frame_m, bev=0.006)
    K.box("window sill", (wx, WY - 0.08, wz - wh / 2 - 0.01), (ww + 0.14, 0.18, 0.035), frame_m, bev=0.006)
    K.box("window back", (wx, WY + 0.28, wz), (ww, 0.02, wh), K.mat("window room", "#6E5238", rough=0.9), bev=0)
    K.box("window reveal", (wx - ww / 2 + 0.01, WY + 0.13, wz), (0.02, 0.3, wh), inside, bev=0)
    K.box("window reveal", (wx + ww / 2 - 0.01, WY + 0.13, wz), (0.02, 0.3, wh), inside, bev=0)
    shelf = hw_wood("window shelf", "#7A5A38", "#946E46")
    for z in (wz - 0.2, wz + 0.04):
        K.box("window shelf", (wx, WY + 0.16, z), (ww - 0.04, 0.16, 0.015), shelf, bev=0.002)
        for k in range(6):
            jar(f"window jar {z} {k}", (wx - 0.29 + k * 0.115, WY + 0.15, z + 0.008), r=0.036, h=0.1, fill=0.9, honey_col=rnd.choice(["#E39A1A", "#D98A12", "#EBAA2E"]), label="HONEY", glow=0.4)
    for dx in (-ww / 6, ww / 6):
        K.box("window mullion", (wx + dx, WY - 0.03, wz), (0.022, 0.025, wh), frame_m, bev=0.002)
    K.box("window transom", (wx, WY - 0.03, wz + 0.08), (ww, 0.025, 0.022), frame_m, bev=0.002)
    K.box("flower box", (wx, WY - 0.2, wz - wh / 2 - 0.08), (ww, 0.1, 0.1), hw_wood("flower box", "#5E7A3A", "#6E8A44"), bev=0.004)
    for k in range(5):
        K.sph("box flower", (wx - 0.3 + 0.15 * k, WY - 0.2, wz - wh / 2 - 0.01), 0.04, K.mat(f"box flower {k}", ("#E0583A", "#F2D43A", "#C96BC0", "#F4F0E6", "#E0583A")[k], rough=0.6))
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


def s3_pole(name, base, col, word, side):
    """a flagpole with a pulley at its top, its halyard down to a cleat on the side he hauls from, and a cloth flag
    clipped to the pole that flies to `side`. The flag's TOP EDGE is its price. Returns (flag, rope-to-flag scaler)."""
    pole = K.mat("pole white", "#EDEAE2", rough=0.4)
    H = 1.36
    K.cyl(name + " pole", tuple(base + Vector((0, 0, H / 2))), 0.016, H, pole, v=16, bev=0.003)
    K.sph(name + " finial", tuple(base + Vector((0, 0, H + 0.02))), 0.026, K.mat("finial gold", "#D2A23A", rough=0.3, metal=0.8))
    K.cyl(name + " foot", tuple(base + Vector((0, 0, 0.03))), 0.07, 0.06, hw_noise("pole stone", "#9A958A", "#B5AFA2", scale=10), v=24, bev=0.006)
    steel = K.mat("pulley steel", "#7A8288", rough=0.3, metal=0.8)
    K.cyl(name + " pulley", tuple(base + Vector((0, -0.024, H - 0.04))), 0.022, 0.012, steel, rot=(math.pi / 2, 0, 0), v=20, bev=0.002)
    rope = K.mat("halyard", "#F2ECDA", rough=0.8)
    rx = base.x - side * 0.02                  # the hauling run, on the front of the pole away from the flag
    K.capsule(name + " halyard", Vector((rx, base.y - 0.05, 0.22)), Vector((rx, base.y - 0.024, H - 0.04)), 0.007, rope)
    K.box(name + " cleat", (rx, base.y - 0.03, 0.22), (0.016, 0.02, 0.07), steel, bev=0.003)
    # the flag-side run of the halyard, from the pulley down to the flag's top clip: scaled on z every frame
    run = K.empty(name + " flag run", tuple(base + Vector((side * 0.02, -0.03, H - 0.04))))
    K.cyl(name + " flag run rope", (0, 0, -0.5), 0.006, 1.0, rope, v=8, bev=0, parent=run)
    hw_local(run)
    flag = K.empty(name + " flag", (0, 0, 0))
    cloth = K.mat(f"flag {col}", col, rough=0.75)
    W_, H_ = 0.26, 0.22
    for k in range(6):                         # the cloth in six panels with a gentle ripple
        u = (k + 0.5) / 6
        o = K.box(name + " cloth", (side * (0.02 + W_ * u), 0.004 * math.sin(u * 5.0), -H_ / 2), (W_ / 6 + 0.002, 0.006, H_ - 0.01 * u), cloth, bev=0.002, parent=flag)
        o.rotation_euler = (0, 0, 0.12 * math.cos(u * 5.0) * side)
    for z in (-0.012, -H_ + 0.012):            # the two clips that hold it to the halyard at the pole
        K.box(name + " clip", (side * 0.02, -0.005, z), (0.02, 0.016, 0.014), steel, bev=0.002, parent=flag)
    K.box(name + " hoist edge", (side * 0.02, -0.005, -H_ / 2), (0.012, 0.012, H_), K.mat("hoist tape", "#3A3A3A", rough=0.7), bev=0.002, parent=flag)
    ink = hw_ink(f"flag ink {name}", "#2A1E12" if col != "#F2B02A" else "#3A1E04")
    K.text(name + " word", word, (side * (0.02 + W_ / 2), -0.016, -H_ / 2), 0.05 if len(word) < 7 else 0.036, (math.pi / 2, 0, 0), ink, extrude=0.0008, parent=flag)
    hw_local(flag)
    return flag, run


def shot2():
    """A QUARTER OF THE PRICE. Two flagpoles in front of a tall price board banded every 0.50 euro a kilo. The RICE
    SYRUP flag already flies at the first band, 0.50. Beside the HONEY pole he hauls its halyard hand over hand and the
    gold flag climbs band by band, 1.00, 1.50, 2.00, to 2.17: four bands to the syrup's one. He looks from one to the
    other and rubs his hands: every spoonful of syrup is profit."""
    W = hw_win
    T_IN = 0.75                                     # walks in to the honey pole, looking over at the syrup flag
    T_LOOK = 0.25
    T_H0, T_H1 = 0.95, 3.25                          # the honey flag up to 2.17, hand over hand
    T_BACK = 3.45                                   # steps back from the pole, looking up
    T_RUB = 3.85                                    # rubs his hands
    NH = 4
    light = place_honey_house()
    board = hw_noise("price board", "#F4EEDC", "#E8E0C8", scale=4, rough=0.7, bump=0.1)
    band = hw_noise("price band", "#DDBF7E", "#D2B270", scale=4, rough=0.7, bump=0.1)
    ink = hw_ink("board ink", "#2A1E12")
    bx0, bx1 = -0.31, 0.52; by = S3_POLES[0].y + 0.16; bxc = (bx0 + bx1) / 2
    K.box("price board back", (bxc, by + 0.02, S3_Z0 + 0.43), (bx1 - bx0 + 0.06, 0.03, 1.0), hw_wood("board frame", "#6E4A2A", "#8A5E36"), bev=0.008)
    for k in range(5):
        z0 = S3_Z0 + S3_PER * 0.5 * k
        K.box("price band", (bxc, by, z0 + S3_PER * 0.25), (bx1 - bx0, 0.01, S3_PER * 0.5 - 0.004), board if k % 2 else band, bev=0.002)
    for k in range(0, 5):
        v = 0.5 * k; z = S3_Z0 + S3_PER * v
        K.box("board line", (bxc, by - 0.008, z), (bx1 - bx0, 0.004, 0.008 if k else 0.012), ink, bev=0)
        if k: K.text("board euro", f"{v:.2f}", ((S3_POLES[0].x + 0.04 + S3_POLES[1].x - 0.26) / 2, by - 0.01, z + 0.026), 0.05, (math.pi / 2, 0, 0), ink, extrude=0.0008)   # between the poles, clear of both flags
    K.text("price board head", "EUROS A KILO", (bxc, by - 0.01, S3_Z0 + S3_PER * 2.25 + 0.03), 0.05, (math.pi / 2, 0, 0), ink, extrude=0.0008)
    sf, srun = s3_pole("syrup", S3_POLES[0], "#FAFAF4", "RICE SYRUP", 1)
    hf, hrun = s3_pole("honey", S3_POLES[1], "#F2B02A", "HONEY", -1)
    tops = (S3_Z0 + S3_PER * 0.5, S3_Z0 + S3_PER * 2.17)
    def honey_z(t):
        return S3_Z0 + (tops[1] - S3_Z0) * ease(max(0.0, min(1.0, (t - T_H0) / (T_H1 - T_H0))))   # wound up with the crank
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for i, (fl, run, z) in enumerate(((sf, srun, tops[0]), (hf, hrun, honey_z(t)))):
            side = (1, -1)[i]
            fl.location = (S3_POLES[i].x, S3_POLES[i].y, z); fl.keyframe_insert("location", frame=f)
            run.scale = (1, 1, max(0.01, run.location.z - z)); run.keyframe_insert("scale", frame=f)
    # ---- the winch at the honey pole's foot: he cranks it and the halyard winds the flag up
    steel = K.mat("winch steel", "#5E666C", rough=0.35, metal=0.7)
    red = K.mat("winch red", "#B8261E", rough=0.45)
    HUB = Vector((S3_POLES[1].x + 0.14, S3_POLES[1].y - 0.16, 0.38))      # the crank's axis points at him
    K.box("winch post", (HUB.x - 0.07, HUB.y, 0.16), (0.07, 0.07, 0.32), hw_wood("winch post", "#6E4A2A", "#8A5E36"), bev=0.006)
    K.box("winch box", (HUB.x - 0.07, HUB.y, 0.38), (0.1, 0.12, 0.12), red, bev=0.01)
    K.cyl("winch drum", (HUB.x - 0.07, HUB.y, 0.465), 0.035, 0.1, steel, rot=(math.pi / 2, 0, 0), v=24, bev=0.003)
    K.capsule("winch rope", Vector((HUB.x - 0.07, HUB.y + 0.02, 0.5)), Vector((S3_POLES[1].x + 0.02, S3_POLES[1].y - 0.024, 1.32)), 0.006, K.mat("halyard", "#F2ECDA", rough=0.8))
    crank = K.empty("winch crank", tuple(HUB))
    K.cyl("crank hub", (-0.005, 0, 0), 0.022, 0.04, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.003, parent=crank)
    K.box("crank arm", (0.02, 0.025, 0), (0.012, 0.07, 0.02), steel, bev=0.003, parent=crank)
    K.cyl("crank handle", (0.045, 0.055, 0), 0.014, 0.05, red, rot=(0, math.pi / 2, 0), v=16, bev=0.003, parent=crank)
    hw_local(crank)
    TURNS = 4
    ang = lambda t: 2 * math.pi * TURNS * ease(max(0.0, min(1.0, (t - T_H0) / (T_H1 - T_H0))))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        crank.rotation_euler = (ang(t), 0, 0); crank.keyframe_insert("rotation_euler", frame=f)
    handle = lambda t: HUB + Vector((0.065, 0.055 * math.cos(ang(t)), 0.055 * math.sin(ang(t))))
    # ---- him: walks in to the winch, cranks, looks up at the flag, turns to us and rubs his hands
    data = load_data()
    YW = -82.0
    P0 = S3_DATA + Vector((0.22, 0.0, 0))
    data.place(P0.x, P0.y, -90)
    hat = bee_hat(data)
    data.walk_to(S3_DATA, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw0 = math.degrees(data.arm.rotation_euler.z)
    crankb = lambda t: math.sin(ang(t)) * W(t, T_H0, 0.2) * (1 - W(t, T_H1 - 0.1, 0.2))
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        yaw = yw0 + (YW - yw0) * W(t, T_IN - 0.05, 0.3) + 55 * W(t, T_BACK, 0.4) + 7 * crankb(t)
        p = S3_DATA + Vector((0.04, 0, 0)) * crankb(t) + Vector((0.04, -0.12, 0)) * W(t, T_BACK, 0.45)
        z = 0.035 * abs(crankb(t)) + 0.05 * hw_kick(t - T_BACK - 0.35, 0.14) + 0.04 * hw_kick(t - T_RUB - 0.6, 0.13)
        data._kobj(t, loc=(p.x, p.y, z), rot=math.radians(yaw))
    hw_layer(data, "spine", lambda t: (18 * crankb(t) + 8 * W(t, T_H0, 0.3) * (1 - W(t, T_H1, 0.3)) + 10 * W(t, T_RUB, 0.3), 0,
                                      10 * math.sin(2 * math.pi * (t - T_RUB) / 0.9) * W(t, T_RUB, 0.3)), 0, DUR + 0.4)
    sc.frame_set(F(T_H0)); bpy.context.view_layer.update()
    near, far = sorted("LR", key=lambda s: (acts._shoulder(data, s) - HUB).length)
    rub = [(T_BACK + 0.2, (0.12, 0.09, -0.05)), (T_RUB, (0.13, 0.0, -0.08))]
    for k in range(3):
        rub.append((T_RUB + 0.3 + 0.3 * k, (0.13 + (0.02 if k % 2 else -0.01), 0.0, -0.08 + (0.015 if k % 2 else 0))))
    rub.append((DUR + 0.3, (0.12, 0.01, -0.07)))
    rest_n = hw_hand(data, near, [(0.0, (0.06, 0.08, -0.12)), (T_IN, (0.08, 0.08, -0.1)), (T_H1, (0.08, 0.08, -0.1))] + rub)
    def near_fn(t):
        g = W(t, T_H0 - 0.35, 0.3) * (1 - W(t, T_H1 + 0.05, 0.3))
        return rest_n(t).lerp(handle(t), g)
    lid = HUB + Vector((0.03, 0.03, 0.4 - HUB.z + 0.005))
    rest_f = hw_hand(data, far, [(0.0, (0.06, 0.08, -0.12)), (T_IN + 0.2, (0.07, 0.08, -0.1)), (T_H0 + 0.3, (0.05, 0.08, -0.11)), (T_H1, (0.05, 0.08, -0.11))] + rub)   # pumping with the crank
    def far_fn(t):
        sc.frame_set(F(t)); sh, fw, out, up = hw_frame(data, far)
        return rest_f(t) + (fw * 0.025 + Vector((0, 0, 0.025))) * crankb(t)      # his free fist pumps with every turn
    data.reach(near, near_fn, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    data.reach(far, far_fn, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    LENS = Vector((0.3, -1.6, 0.68))
    data.look_at(Vector((S3_POLES[0].x, S3_POLES[0].y, tops[0])), 0.0, max_yaw=50, max_pitch=30, blend=0.15)
    data.look_at(Vector((S3_POLES[1].x, S3_POLES[1].y, 0.8)), T_H0 + 0.3, max_yaw=28, max_pitch=40, blend=0.2)
    data.look_at(Vector((S3_POLES[1].x, S3_POLES[1].y, tops[1])), T_H1 - 0.3, max_yaw=28, max_pitch=40, blend=0.2)
    data.look_at(LENS, T_RUB - 0.1, max_yaw=45, blend=0.18)
    data.expression("wry", 0.0, T_H0)
    data.expression("determined", T_H0 + 0.05, T_H1 - 0.1, blend=0.15)
    data.expression("surprised", T_H1, T_RUB - 0.1, blend=0.1)
    data.expression("pleased", T_RUB, DUR + 1.0, blend=0.18)
    data.finish()
    LOOK = Vector((0.3, 0.3, 0.7))
    LENS, LOOK = compose.frame_data(data, LENS, LOOK, 30, face_at=(0.76, 0.47), height=0.346, t=0.5 * DUR)   # framed first: at the winch, board clear
    cam = K.camera(tuple(LENS), tuple(LOOK), lens=30, fstop=8.0)
    compose.drop_cut(hw_named("window jar", "inside jar"), cam, NF, label="the honey house's jars")
    camera_path(cam, lambda t: (LENS + Vector((0.02, 0.08, 0.0)) * ease(t / DUR), LOOK + Vector((0.0, 0.0, 0.05 * ease(t / DUR))), LOOK))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="honey_house", light=light, data=data, rest=1, grips=("crank handle", "winch box"),
                boxes=[("the price board and both flags", lambda: hw_drawn("price band", "board line", "board euro", "syrup flag", "honey flag", "syrup cloth", "honey cloth"), (0.0, 0.2, 1.0, 1.0)),
                       ("the board's words", lambda: hw_drawn("board euro", "price board head", "syrup word", "honey word"), (0.0, 0.2, 1.0, 1.0))],
                conseq=[("he hauls the HONEY flag up the board to 2.17, four bands to the RICE SYRUP flag's one at 0.50", lambda: meshes([sf, hf, srun, hrun]) + meshes_of("price band", "board line", "syrup pole", "honey pole"), T_H0, DUR, {"hero": True, "moves": lambda: meshes([hf])}),
                        ("he cranks the winch and the honey flag climbs", lambda: meshes([hf, crank]), T_H0, T_H1, {"moves": True})])
