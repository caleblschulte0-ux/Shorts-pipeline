"""BEAT 3, TUNED TO PASS: the cheap stall's back room. He dips his honey dipper in the blending vat and touches it to
the old grey TEST box: red FAIL. He turns the SYRUP wheel on the syrup drum down a notch and tests again: still red.
One more notch: green PASS, while the vat's gauge still reads mostly syrup (DG SANTE: fraudsters use "analyses in
accredited laboratories to adapt honey/sugar blends to elude possible detection")."""

S3_P0 = Vector((0.0, 0.0, 0.0))                 # him, square to the lens
S3_VAT = Vector((-0.3, -0.1, 0.0))            # the blending vat, front left of him
S3_VR, S3_VZ0, S3_VZ1 = 0.085, 0.12, 0.4       # its radius, its body's bottom and mouth
S3_BOX = Vector((-0.14, -0.28, 0.25))            # the TEST box on its crate, to his left
S3_DRUM = Vector((0.34, -0.14, 0.0))            # the RICE SYRUP drum, front right of him
S3_DH = 0.5                                     # its height
S3_WHEEL = Vector((S3_DRUM.x - 0.112, S3_DRUM.y - 0.01, 0.44))   # the SYRUP valve wheel on its side, facing him
S3_SYRUP = (0.86, 0.79, 0.72)                   # the gauge's syrup share after each notch: still mostly syrup


def place_back_room():
    """THE CHEAP STALL'S BACK ROOM: rough plank floor and walls, a dusty window with the sun through it, sacks stamped
    SYRUP stacked by the wall, the steel blending vat on its stand fed by a pipe from a syrup drum, an old grey TEST box
    on a crate, a bare bulb."""
    rnd = hw_random.Random(31)
    floor = hw_wood("back room floor", "#5A4030", "#735440", scale=5)
    K.box("back room floor", (0, 0.4, -0.01), (6, 6, 0.02), floor, bev=0)
    for k in range(-14, 15):
        K.box("floor seam", (k * 0.16, 0.4, 0.0006), (0.006, 6, 0.0012), K.mat("seam dark", "#2E2018", rough=0.95), bev=0)
    wall = hw_wood("back room wall", "#6E5038", "#8A6848", scale=3)
    K.box("back wall", (0, 0.75, 1.0), (4, 0.05, 2.0), wall, bev=0)
    for k in range(-12, 13):
        K.box("wall plank", (k * 0.17, 0.72, 1.0), (0.008, 0.01, 2.0), K.mat("plank gap", "#3A281C", rough=0.95), bev=0)
    K.box("side wall", (-1.3, 0.0, 1.0), (0.05, 2.0, 2.0), wall, bev=0)
    # the window: a frame, dusty glass, the sun through it
    fr = K.mat("window frame", "#D8CFC0", rough=0.6)
    K.box("window glass", (0.55, 0.725, 1.05), (0.5, 0.01, 0.42), K.mat("dusty glass", "#F4E7C4", rough=0.4, emit=1.2), bev=0)
    for dx, dz, sx, sz in ((0, 0.22, 0.56, 0.04), (0, -0.22, 0.56, 0.04), (-0.27, 0, 0.04, 0.46), (0.27, 0, 0.04, 0.46), (0, 0, 0.025, 0.42), (0, 0, 0.5, 0.025)):
        K.box("window frame", (0.55 + dx, 0.715, 1.05 + dz), (sx, 0.03, sz), fr, bev=0.003)
    # sacks of SYRUP along the back wall, stencilled
    sack = hw_noise("syrup sack", "#C9B48A", "#DCC9A0", scale=14, rough=0.95, bump=0.5)
    ink = hw_ink("sack ink", "#7A2A18")
    for k in range(5):
        x = -0.95 + k * 0.24 + rnd.uniform(-0.02, 0.02); z = 0.13
        K.box(f"syrup sack {k}", (x, 0.58, 0.14), (0.21, 0.15, 0.28), sack, bev=0.05); K.box(f"sack neck {k}", (x, 0.58, 0.3), (0.07, 0.05, 0.06), sack, bev=0.02); K.cyl(f"sack tie {k}", (x, 0.58, 0.285), 0.038, 0.012, K.mat("sack tie", "#5A4028", rough=0.9), v=16, bev=0)
        K.text("sack word", "SYRUP", (x, 0.5, 0.15), 0.035, (math.pi / 2, 0, 0), ink, extrude=0.0004)
    for k in range(3):
        x = -0.85 + k * 0.26
        o = K.box(f"syrup sack top {k}", (x + 0.12, 0.6, 0.37), (0.24, 0.15, 0.17), sack, bev=0.05); o.rotation_euler = (0, 0.06 * (k - 1), 0)
    # the syrup drum on the right, its SYRUP valve wheel, a hose across the floor to the vat
    steel = K.mat("vat steel", "#B8BCC0", rough=0.25, metal=0.9)
    drum = K.mat("syrup drum", "#2E5E8A", rough=0.45, metal=0.3)
    K.cyl("syrup drum", (S3_DRUM.x, S3_DRUM.y, S3_DH / 2), 0.11, S3_DH, drum, v=40, bev=0.01)
    for z in (0.08, S3_DH - 0.08):
        K.cyl("drum hoop", (S3_DRUM.x, S3_DRUM.y, z), 0.113, 0.018, steel, v=40, bev=0.003)
    K.cyl("drum valve", (S3_WHEEL.x + 0.012, S3_WHEEL.y, S3_WHEEL.z), 0.012, 0.03, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.002)
    K.text("drum word", "RICE\nSYRUP", (S3_DRUM.x, S3_DRUM.y - 0.113, 0.3), 0.032, (math.pi / 2, 0, 0), hw_ink("drum ink", "#F2EEE4"), extrude=0.0005)
    # the hose from the drum's foot along the floor into the vat's foot
    hose = K.mat("hose black", "#1E1E1E", rough=0.6)
    a, b = Vector((S3_DRUM.x - 0.08, S3_DRUM.y - 0.08, 0.03)), Vector((S3_VAT.x + 0.06, S3_VAT.y - 0.08, 0.03))
    mid = Vector(((a.x + b.x) / 2, min(a.y, b.y) - 0.1, 0.03))
    for p, q in ((a, mid), (mid, b)):
        d = q - p
        K.cyl("syrup hose", tuple((p + q) / 2), 0.014, d.length, hose, rot=tuple(Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()), v=12, bev=0)
    # the vat on its stand, with its gauge on the front: HONEY at the bottom, SYRUP at the top
    K.cyl("vat", (S3_VAT.x, S3_VAT.y, (S3_VZ0 + S3_VZ1) / 2), S3_VR, S3_VZ1 - S3_VZ0, steel, v=48, bev=0.006)
    K.cyl("vat rim", (S3_VAT.x, S3_VAT.y, S3_VZ1), S3_VR + 0.006, 0.012, steel, v=48, bev=0.003)
    K.cyl("vat blend", (S3_VAT.x, S3_VAT.y, S3_VZ1 - 0.02), S3_VR - 0.004, 0.01, hw_honey("vat blend", "#E8C070", clear=0.2), v=48, bev=0)
    for a in (0.6, 2.4, 4.2):
        K.box("vat leg", (S3_VAT.x + 0.07 * math.cos(a), S3_VAT.y + 0.07 * math.sin(a), S3_VZ0 / 2), (0.02, 0.02, S3_VZ0), steel, bev=0.003)
    K.box("gauge back", (S3_VAT.x, S3_VAT.y - S3_VR - 0.006, 0.26), (0.11, 0.006, 0.27), K.mat("gauge plate", "#F2EEE4", rough=0.5), bev=0.002)
    gi = hw_ink("gauge ink", "#2A1E12")
    K.text("gauge word", "SYRUP", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.372), 0.024, (math.pi / 2, 0, 0), gi, extrude=0.0003)
    K.text("gauge word", "HONEY", (S3_VAT.x, S3_VAT.y - S3_VR - 0.0095, 0.146), 0.024, (math.pi / 2, 0, 0), gi, extrude=0.0003)
    # the old TEST box on its crate: a grey case, a red and a green lamp, a little screen
    crate = hw_wood("crate wood", "#9C7048", "#B88A5C", scale=6)
    K.box("test crate", (S3_BOX.x, S3_BOX.y, S3_BOX.z / 2 - 0.005), (0.24, 0.16, S3_BOX.z - 0.01), crate, bev=0.006)
    case = K.mat("test case", "#8A8F94", rough=0.5, metal=0.3)
    K.box("test box", (S3_BOX.x, S3_BOX.y, S3_BOX.z + 0.07), (0.22, 0.13, 0.14), case, bev=0.012)
    K.text("test word", "TEST", (S3_BOX.x, S3_BOX.y - 0.067, S3_BOX.z + 0.12), 0.026, (math.pi / 2, 0, 0), hw_ink("test ink", "#1E2226"), extrude=0.0004)
    K.box("test screen", (S3_BOX.x + 0.035, S3_BOX.y - 0.066, S3_BOX.z + 0.06), (0.11, 0.004, 0.05), K.mat("screen dark", "#1A1E22", rough=0.3), bev=0.002)
    K.box("test probe plate", (S3_BOX.x - 0.05, S3_BOX.y + 0.035, S3_BOX.z + 0.142), (0.05, 0.05, 0.006), steel, bev=0.002)
    # a bare bulb on its flex
    K.cyl("bulb flex", (-0.1, 0.1, 1.55), 0.004, 0.5, K.mat("flex", "#1E1E1E"), v=8, bev=0)
    K.sph("bulb", (-0.1, 0.1, 1.28), 0.035, K.mat("bulb glow", "#FFE2A8", emit=6.0))

    def light():
        sc_ = bpy.context.scene; w = sc_.world or bpy.data.worlds.new("World"); sc_.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (1.0, 0.86, 0.66, 1); bg.inputs["Strength"].default_value = 0.3
        LOC._area("window sun", (0.6, 1.4, 1.6), 0.8, 90, (1.0, 0.88, 0.66), aim=(0.0, 0.0, 0.3))
        LOC._area("room fill", (0.4, -1.6, 1.8), 2.4, 55, (1.0, 0.92, 0.8), aim=(-0.1, 0.0, 0.4))
        LOC._area("bulb pool", (-0.1, 0.05, 1.2), 0.5, 24, (1.0, 0.85, 0.6), aim=(-0.1, -0.05, 0.3))
        return LOC._hero_key()
    return light


def s3_wheel(name, at):
    """the SYRUP valve wheel facing the lens, spinning about the pipe's +Y: a red rim, four spokes, a knob on the rim"""
    root = K.empty(name, tuple(at))
    spin = K.empty(name + " spin", (0, 0, 0), parent=root)
    red = K.mat("wheel red", "#C8261E", rough=0.4, metal=0.2)
    K.cyl(name + " rim", (0, 0, 0), 0.085, 0.014, red, v=40, bev=0.004, parent=spin)
    K.cyl(name + " hub", (0, 0, -0.01), 0.014, 0.03, red, v=16, bev=0.002, parent=spin)
    for a in (0, math.pi / 2):
        K.box(name + " spoke", (0, 0, 0.0), (0.16 * abs(math.cos(a)) + 0.014, 0.16 * abs(math.sin(a)) + 0.014, 0.014), red, bev=0.002, parent=spin)
    K.cyl(name + " knob", (0.07, 0, 0.035), 0.009, 0.06, K.mat("knob black", "#1E1E1E", rough=0.4), v=12, bev=0.002, parent=spin)
    K.text(name + " word", "SYRUP", (0, 0.0, 0.0072), 0.022, (0, 0, 0), hw_ink("wheel ink", "#FFFFFF"), extrude=0.0003, parent=spin)
    hw_local(root)
    root.rotation_euler = (0, -math.pi / 2, 0)            # its face and knob to -X, to him
    return root, spin


def shot3():
    """TUNED TO PASS. The lens high and to his right: he dips his dipper in the vat and touches it to the TEST box (red
    FAIL), cranks the SYRUP wheel down a notch (the gauge drops), tests again (still red), one more notch, tests (green
    PASS) while the gauge still reads mostly syrup; he turns and gapes at us."""
    W = hw_win
    T_D = [0.04 * DUR, 0.38 * DUR, 0.64 * DUR]           # dips
    T_T = [t + 0.22 * DUR * 0.55 for t in T_D]           # tests (arc 0.10 / 0.50 / 0.78)
    T_T = [0.17 * DUR, 0.42 * DUR, 0.895 * DUR]           # the key stills: dipping / RED (test 2) / cranking, still red / GREEN
    T_D = [t - 0.55 for t in T_T]
    T_C = [0.207 * DUR, 0.575 * DUR]                     # cranks of the SYRUP wheel
    CR = 0.6                                            # a crank's length
    T_GAPE = 0.95 * DUR
    light = place_back_room()
    wheel, wspin = s3_wheel("syrup wheel", S3_WHEEL)
    # the gauge: a glass tube, the honey part at the bottom and the syrup above it, the line between them dropping
    tube_m = hw_glass("gauge glass")
    K.cyl("gauge tube", (S3_VAT.x, S3_VAT.y - S3_VR - 0.02, 0.26), 0.019, 0.19, tube_m, v=16, bev=0.002)
    hon = K.cyl("gauge honey", (0, 0, 0), 0.016, 1.0, hw_honey("gauge honey", "#C87810", glow=0.4), v=16, bev=0)
    syr = K.cyl("gauge syrup", (0, 0, 0), 0.016, 1.0, K.mat("gauge syrup", "#F6F0DA", rough=0.3, emit=0.3), v=16, bev=0)
    G0, G1 = 0.172, 0.348
    def share(t):
        s = S3_SYRUP[0]
        for k, tc in enumerate(T_C):
            s += (S3_SYRUP[k + 1] - S3_SYRUP[k]) * ease(max(0.0, min(1.0, (t - tc) / CR)))
        return s
    # the TEST box's lamps and words: dark, then lit
    red_on = K.sph("lamp red", (S3_BOX.x - 0.07, S3_BOX.y - 0.066, S3_BOX.z + 0.06), 0.02, K.mat("lamp red glow", "#FF2A1E", emit=8.0))
    grn_on = K.sph("lamp green", (S3_BOX.x - 0.03, S3_BOX.y - 0.066, S3_BOX.z + 0.06), 0.02, K.mat("lamp green glow", "#2AFF5A", emit=8.0))
    for nm, x in (("lamp red off", -0.07), ("lamp green off", -0.03)):
        K.sph(nm, (S3_BOX.x + x, S3_BOX.y - 0.062, S3_BOX.z + 0.06), 0.019, K.mat("lamp off", "#3A3A3A", rough=0.3))
    fail = K.text("screen fail", "FAIL", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.047), 0.04, (math.pi / 2, 0, 0), hw_ink("fail ink", "#FF3A2A", emit=4.0), extrude=0.0004)
    ok = K.text("screen pass", "PASS", (S3_BOX.x + 0.035, S3_BOX.y - 0.069, S3_BOX.z + 0.047), 0.04, (math.pi / 2, 0, 0), hw_ink("pass ink", "#3AFF6A", emit=4.0), extrude=0.0004)
    # a beacon on a post at the box's back corner: the whole room sees FAIL or PASS
    BEA = Vector((S3_BOX.x + 0.075, S3_BOX.y + 0.03, S3_BOX.z + 0.25))
    K.cyl("lamp post", (BEA.x, BEA.y, (S3_BOX.z + 0.14 + BEA.z) / 2), 0.008, BEA.z - S3_BOX.z - 0.14, K.mat("vat steel"), v=12, bev=0)
    K.cyl("lamp base", (BEA.x, BEA.y, BEA.z - 0.012), 0.032, 0.02, K.mat("lamp base", "#2A2E32", rough=0.4), v=24, bev=0.003)
    K.sph("lamp dome off", (BEA.x, BEA.y, BEA.z), 0.038, K.mat("lamp dome off", "#5A5048", rough=0.25))
    beacon_red = K.sph("lamp red beacon", (BEA.x, BEA.y, BEA.z), 0.04, K.mat("lamp red glow", "#FF2A1E", emit=8.0))
    beacon_grn = K.sph("lamp green beacon", (BEA.x, BEA.y, BEA.z), 0.04, K.mat("lamp green glow", "#2AFF5A", emit=8.0))
    def lit(o, spans):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = any(a <= t < b for a, b in spans)
            s = 1.0 if on else 1e-3
            o.scale = (s, s, s); o.keyframe_insert("scale", frame=f)
    red_spans = [(T_T[0], T_T[1] - 0.12), (T_T[1], T_T[2])]                 # FAIL stays up until the next test; it blinks off as he tests again
    for o in (red_on, fail, beacon_red): lit(o, red_spans)
    for o in (grn_on, ok, beacon_grn): lit(o, [(T_T[2], DUR + 1)])
    # ---- him: square to the lens between the vat and the wheel, turning to each job
    data = load_data()
    data.place(S3_P0.x, S3_P0.y, 0.0)
    hat = bee_hat(data)
    def yaw(t):
        y = 0.0
        for td, tt in zip(T_D, T_T):
            y += -38 * (W(t, td - (0.5 if td > 3 else 0.62), 0.35) if td > 0.5 else 1.0) * (1 - W(t, td + 0.2, 0.35))            # to the vat and the box
        for tc in T_C:
            y += 12 * W(t, tc - 0.25, 0.25) * (1 - W(t, tc + CR, 0.25))            # to the wheel
        y += 0.0
        return math.radians(y)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        z = sum(0.04 * hw_kick(t - tt - 0.1, 0.16) for tt in T_T[:2]) - sum(0.035 * math.sin(math.pi * max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C) + 0.06 * hw_kick(t - T_T[2] - 0.05, 0.15) + 0.04 * hw_kick(t - T_GAPE, 0.14)
        lean = sum(0.045 * W(t, tc - 0.3, 0.25) * (1 - W(t, tc + CR - 0.3, 0.25)) for tc in T_C)
        data._kobj(t, loc=(S3_P0.x + lean, S3_P0.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (sum(6 * W(t, td - 0.1, 0.25) * (1 - W(t, td + 0.3, 0.25)) for td in T_D)
                                      + sum(8 * W(t, tc - 0.15, 0.2) * (1 - W(t, tc + CR, 0.2)) for tc in T_C)
                                      - 8 * W(t, T_T[2] + 0.05, 0.2) * (1 - W(t, T_GAPE - 0.1, 0.3)), 0,
                                      12 * math.sin(2 * math.pi * (t - T_T[1] - 0.15) / 0.45) * W(t, T_T[1] + 0.1, 0.12) * (1 - W(t, T_T[1] + 0.7, 0.2))), 0, DUR + 0.4)   # still red: he shakes his head
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):           # his fist where the dipper's head reaches `world`
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    MOUTH = Vector((S3_VAT.x + 0.02, S3_VAT.y + 0.01, S3_VZ1 - 0.02))
    PLATE = Vector((S3_BOX.x - 0.05, S3_BOX.y + 0.035, S3_BOX.z + 0.15))
    # the dipper hand (his left): dip, lift, over to the box's plate, back up
    dk = [(0.0, short(lf, 0.0, MOUTH + Vector((0, 0, 0.09)), by=0.15))]
    for td, tt in zip(T_D, T_T):
        dk += [(td - 0.2, short(lf, td - 0.2, MOUTH + Vector((0, 0, 0.07)), by=0.15)), (td, short(lf, td, MOUTH + Vector((0, 0, 0.02)), by=0.15)), (td + 0.28, short(lf, td + 0.28, (MOUTH + PLATE) / 2 + Vector((-0.02, 0.02, 0.04)), by=0.15)),
               (tt - 0.05, short(lf, tt - 0.05, PLATE + Vector((0, 0, 0.05)), by=0.1)), (tt + 0.1, short(lf, tt + 0.1, PLATE + Vector((0, 0, 0.02)), by=0.09)), (tt + 0.35, (0.14, 0.1, -0.06))]
    dk += [(T_GAPE, (0.1, 0.12, -0.03)), (DUR + 0.3, (0.1, 0.13, -0.025))]
    # the wheel hand (his right): on the knob through each crank, the knob going round with the wheel
    def knob(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return wspin.matrix_world @ Vector((0.07, 0, 0.075))
    def wheel_turn(t):
        return math.radians(-140) + sum(math.radians(50) * ease(max(0.0, min(1.0, (t - tc) / CR))) for tc in T_C)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        wspin.rotation_euler = (0, 0, wheel_turn(t)); wspin.keyframe_insert("rotation_euler", frame=f)
    wk = [(0.0, (0.03, 0.08, -0.12)), (T_C[0] - 0.7, (0.03, 0.09, -0.11))]
    for tc in T_C:
        wk += [(tc - 0.12, hw_rel(data, rt, tc - 0.12, knob(tc - 0.12)))]
        wk += [(tc + CR * u, hw_rel(data, rt, tc + CR * u, knob(tc + CR * u))) for u in (0.35, 0.7, 1.0)]
        wk += [(tc + CR + 0.3, (0.03, 0.1, -0.1))]
    wk += [(T_GAPE, (0.07, 0.13, -0.03)), (DUR + 0.3, (0.07, 0.13, -0.025))]
    for ks in (dk, wk):
        ks.sort(key=lambda k: k[0])
        i = 1
        while i < len(ks):
            if ks[i][0] <= ks[i - 1][0] + 0.04: ks.pop(i)
            else: i += 1
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.09, back=None, elbow_out=0.5)
    data.reach(rt, hw_hand(data, rt, wk), 0.0, DUR + 0.3, lead=0.08, back=None, elbow_out=0.3)
    CAM = Vector((-0.3, -1.45, 0.72)); LOOK = Vector((0.0, -0.1, 0.45))
    data.look_at(MOUTH, 0.0, max_yaw=45, max_pitch=18, blend=0.0)
    for td, tt in zip(T_D, T_T):
        data.look_at(MOUTH, td - 0.25, max_yaw=45, max_pitch=18, blend=0.15)
        data.look_at(PLATE, tt - 0.25, max_yaw=50, max_pitch=18, blend=0.15)
        data.look_at(CAM, tt + 0.3, max_yaw=45, blend=0.15)
    for tc in T_C:
        data.look_at(S3_WHEEL, tc - 0.2, max_yaw=45, max_pitch=15, blend=0.15)
        data.look_at(Vector(S3_VAT) + Vector((0, -S3_VR, 0.3)), tc + 0.35, max_yaw=45, max_pitch=15, blend=0.15)    # the gauge
    data.look_at(CAM, T_GAPE - 0.25, max_yaw=45, blend=0.15)
    data.expression("determined", 0.0, T_T[0])
    data.expression("angry", T_T[0] + 0.05, T_C[0] + 0.2, blend=0.12)
    data.expression("wry", T_C[0] + 0.25, T_T[1], blend=0.15)
    data.expression("worried", T_T[1] + 0.05, T_C[1] + 0.2, blend=0.12)
    data.expression("determined", T_C[1] + 0.25, T_T[2], blend=0.15)
    data.expression("surprised", T_T[2] + 0.05, DUR + 1.0, blend=0.1)
    data.finish()
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, lf, fore=True)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; s = share(t)
        zl = G0 + (G1 - G0) * (1 - s)
        gy = S3_VAT.y - S3_VR - 0.02
        hon.location = (S3_VAT.x, gy, (G0 + zl) / 2); hon.scale = (1, 1, max(1e-3, zl - G0))
        syr.location = (S3_VAT.x, gy, (zl + G1) / 2); syr.scale = (1, 1, max(1e-3, G1 - zl))
        for o in (hon, syr):
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((0.04, 0.1, -0.06)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.0)) * ease(t / DUR), Vector((S3_BOX.x, S3_BOX.y, S3_BOX.z + 0.08))))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="back_room", light=light, data=data, rest=1, grips=("honey dipper", "syrup wheel", "test probe plate", "vat blend"),
                conseq=[("the old TEST box turns green PASS while the gauge still reads mostly syrup", lambda: meshes_of("test box", "test crate", "lamp", "screen", "gauge", "vat"), T_T[2], DUR, {"hero": True}),
                        ("he turns the SYRUP wheel on the drum down a notch and the gauge drops", lambda: meshes([wheel]) + meshes_of("syrup drum", "drum", "gauge honey", "gauge syrup"), T_C[0], T_C[0] + CR, {"moves": True}),
                        ("the TEST box flashes red FAIL", lambda: meshes_of("lamp red", "screen fail", "test box", "test crate"), T_T[0], T_C[0] - 0.1)])
