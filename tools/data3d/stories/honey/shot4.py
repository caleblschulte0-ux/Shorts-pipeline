"""BEAT 4, THE SHARPER TEST: the village hall, where the EU's inspectors have set up their new test machine. He walks
up with the blend that passed in the back room, dips his honey dipper in it and lets one drop fall into the machine's
funnel; the big dial swings hard from PASS into FAKE, its screen lights RICE SYRUP FOUND and the beacon spins red; he jumps back and points at it
(DG SANTE: "a different set of methods with improved detection capability was used")."""

S4_M = Vector((-0.05, 0.14, 0.0))               # the machine's foot (its front face at y = S4_M.y - 0.14)
S4_MH = 0.8                                     # its height
S4_DIAL = Vector((S4_M.x, S4_M.y - 0.145, 0.55))   # the dial's centre on its front
S4_FUN = Vector((0.28, -0.15, 0.44))             # the funnel's mouth on its side bracket
S4_P = Vector((0.52, 0.0, 0.0))                  # where he stands
S4_JAR = Vector((0.38, -0.27, 0.0))             # the jar of the tuned blend on its stool
S4_STOOL = 0.3


def place_village_hall():
    """THE VILLAGE HALL: a parquet floor, cream walls over a wooden wainscot, tall windows full of sun, bunting from
    the summer fete strung across, rows of folding chairs, a VILLAGE HALL board over the stage at the back."""
    rnd = hw_random.Random(57)
    par = hw_wood("parquet", "#9C6A3E", "#B8844E", scale=7)
    K.box("hall floor", (0, 0.8, -0.01), (8, 8, 0.02), par, bev=0)
    for k in range(-20, 21):
        K.box("parquet seam", (k * 0.12, 0.8, 0.0006), (0.004, 8, 0.0012), K.mat("parquet seam", "#5A3A20", rough=0.9), bev=0)
    cream = K.mat("hall wall", "#F1E6CF", rough=0.8)
    wain = hw_wood("wainscot", "#7A5232", "#8E6440", scale=4)
    K.box("hall back wall", (0, 1.4, 1.2), (6, 0.06, 2.4), cream, bev=0)
    K.box("hall wainscot", (0, 1.36, 0.3), (6, 0.03, 0.6), wain, bev=0.004)
    K.box("hall side wall", (-1.5, 0.4, 1.2), (0.06, 3, 2.4), cream, bev=0)
    K.box("hall side wainscot", (-1.46, 0.4, 0.3), (0.03, 3, 0.6), wain, bev=0.004)
    # tall windows on the back wall, the sun through them
    fr = K.mat("hall window frame", "#FFFFFF", rough=0.5)
    for x in (-0.9, 0.9):
        K.box("hall window", (x, 1.365, 1.25), (0.5, 0.01, 0.9), K.mat("hall window glow", "#FFF3D6", emit=2.2), bev=0)
        for dx, dz, sx, sz in ((0, 0.46, 0.56, 0.04), (0, -0.46, 0.56, 0.04), (-0.27, 0, 0.04, 0.96), (0.27, 0, 0.04, 0.96), (0, 0, 0.03, 0.9), (0, 0.15, 0.5, 0.025), (0, -0.15, 0.5, 0.025)):
            K.box("hall window frame", (x + dx, 1.355, 1.25 + dz), (sx, 0.03, sz), fr, bev=0.003)
    # the stage at the back with its board
    K.box("hall stage", (0, 1.15, 0.12), (2.4, 0.4, 0.24), wain, bev=0.01)
    K.box("hall board", (0, 1.365, 1.95), (1.0, 0.02, 0.2), K.mat("hall board", "#1E4A7A", rough=0.5), bev=0.006)
    K.text("hall board word", "VILLAGE HALL", (0, 1.35, 1.92), 0.09, (math.pi / 2, 0, 0), hw_ink("board gold", "#F2C64A", emit=0.3), extrude=0.001)
    # bunting across the hall
    cols = ["#E53935", "#FDD835", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA"]
    for row, (y, z) in enumerate(((0.9, 1.62), (0.4, 1.7))):
        for k in range(22):
            x = -1.4 + k * 0.13
            sag = 0.08 * (1 - ((x / 1.45) ** 2))
            fl = K.box("bunting flag", (x, y, z - sag - 0.04), (0.08, 0.004, 0.08), K.mat(f"bunting {cols[(k + row) % 6]}", cols[(k + row) % 6], rough=0.7), bev=0)
            fl.rotation_euler = (0, math.pi / 4, 0); fl.scale = (1, 1, 1)
        K.cyl("bunting string", (0, y, z - 0.02), 0.002, 2.9, K.mat("string", "#EEEEEE"), rot=(0, math.pi / 2, 0), v=6, bev=0)
    # folding chairs in rows behind
    seat = K.mat("chair seat", "#3E6E9E", rough=0.5)
    leg = K.mat("chair leg", "#9EA4AA", rough=0.3, metal=0.8)
    for r in range(2):
        for k in range(7):
            x = -1.1 + k * 0.34 + (0.17 if r else 0); y = 0.6 + r * 0.32
            if abs(x - S4_P.x) < 0.25 and r == 0: continue
            K.box("chair seat", (x, y, 0.24), (0.2, 0.2, 0.02), seat, bev=0.004)
            K.box("chair back", (x, y + 0.1, 0.38), (0.2, 0.02, 0.18), seat, bev=0.004)
            for dx in (-0.09, 0.09):
                K.box("chair leg", (x + dx, y, 0.12), (0.012, 0.012, 0.24), leg, bev=0)

    def light():
        sc_ = bpy.context.scene; w = sc_.world or bpy.data.worlds.new("World"); sc_.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (1.0, 0.94, 0.84, 1); bg.inputs["Strength"].default_value = 0.45
        LOC._area("hall windows", (0.0, 1.0, 1.6), 2.0, 110, (1.0, 0.93, 0.8), aim=(0.1, 0.0, 0.4))
        LOC._area("hall fill", (0.6, -1.8, 1.4), 2.4, 70, (1.0, 0.95, 0.88), aim=(0.15, 0.0, 0.45))
        return LOC._hero_key()
    return light


def s4_machine():
    """the inspectors' new test machine: a white cabinet, a big dial (PASS green on the left, FAKE red on the right),
    a red beacon on top, a funnel on a side bracket"""
    white = K.mat("machine white", "#F4F6F8", rough=0.35)
    trim = K.mat("machine trim", "#1E4A7A", rough=0.4)
    steel = K.mat("machine steel", "#B8BCC0", rough=0.25, metal=0.9)
    K.box("test machine", (S4_M.x, S4_M.y, S4_MH / 2), (0.42, 0.28, S4_MH), white, bev=0.02)
    K.box("test machine band", (S4_M.x, S4_M.y - 0.141, S4_MH - 0.08), (0.42, 0.004, 0.06), trim, bev=0)
    K.text("test machine word", "EU LAB TEST", (S4_M.x, S4_M.y - 0.144, S4_MH - 0.09), 0.03, (math.pi / 2, 0, 0), hw_ink("machine word", "#FFFFFF"), extrude=0.0004)
    K.cyl("test machine dial", tuple(S4_DIAL), 0.14, 0.01, K.mat("dial face", "#FFFFFF", rough=0.4), rot=(math.pi / 2, 0, 0), v=48, bev=0.003)
    K.cyl("test machine bezel", tuple(S4_DIAL + Vector((0, 0.002, 0))), 0.15, 0.008, steel, rot=(math.pi / 2, 0, 0), v=48, bev=0.002)
    # the scale: ticks from green (left) through amber to red (right), along the top half of the dial
    for k in range(13):
        a = math.radians(-65 + k * (130 / 12))
        col = "#2E9E44" if k < 5 else ("#F2A51E" if k < 8 else "#D32F2F")
        p = S4_DIAL + Vector((0.115 * math.sin(a), -0.007, 0.115 * math.cos(a)))
        tk = K.box("dial tick", tuple(p), (0.012, 0.003, 0.03), K.mat(f"tick {col}", col, rough=0.5), bev=0)
        tk.rotation_euler = (0, a, 0)
    K.text("dial pass", "PASS", tuple(S4_DIAL + Vector((-0.07, -0.008, -0.045))), 0.026, (math.pi / 2, 0, 0), hw_ink("dial green", "#2E9E44"), extrude=0.0004)
    K.text("dial fake", "FAKE", tuple(S4_DIAL + Vector((0.07, -0.008, -0.045))), 0.026, (math.pi / 2, 0, 0), hw_ink("dial red", "#D32F2F"), extrude=0.0004)
    needle = K.empty("dial needle", tuple(S4_DIAL + Vector((0, -0.012, 0))))
    K.box("dial needle arm", (0, 0, 0.05), (0.01, 0.003, 0.11), K.mat("needle black", "#1A1A1A", rough=0.4), bev=0.001, parent=needle)
    K.cyl("dial needle hub", (0, -0.002, 0), 0.014, 0.008, K.mat("needle black", "#1A1A1A"), rot=(math.pi / 2, 0, 0), v=16, bev=0.001, parent=needle)
    hw_local(needle)
    # the beacon on top: a red glass dome with a mirror inside that spins
    K.cyl("beacon base", (S4_M.x, S4_M.y, S4_MH + 0.015), 0.05, 0.03, trim, v=24, bev=0.003)
    K.sph("beacon dome", (S4_M.x, S4_M.y, S4_MH + 0.06), 0.048, K.mat("beacon glass", "#FF3020", rough=0.15, emit=0.6), scale=(1, 1, 1.15))
    spin = K.empty("beacon spin", (S4_M.x, S4_M.y, S4_MH + 0.06))
    K.box("beacon mirror", (0, 0, 0), (0.07, 0.012, 0.05), K.mat("beacon lamp", "#FF5A3A", emit=12.0), bev=0.002, parent=spin)
    hw_local(spin)
    # the screen under the dial: dark, then RICE SYRUP FOUND in red
    K.box("test machine screen", (S4_M.x, S4_M.y - 0.142, 0.3), (0.3, 0.004, 0.09), K.mat("machine screen", "#14181C", rough=0.3), bev=0.003)
    found = K.text("screen found", "RICE SYRUP\nFOUND", (S4_M.x, S4_M.y - 0.146, 0.3), 0.032, (math.pi / 2, 0, 0), hw_ink("found red", "#FF3A2A", emit=5.0), extrude=0.0004)
    return needle, spin, found


def s4_funnel(at):
    """the funnel on its bracket off the machine's right side, its mouth at `at`"""
    steel = K.mat("machine steel", "#B8BCC0", rough=0.25, metal=0.9)
    K.cyl("funnel spout", (at.x, at.y, at.z - 0.07), 0.01, 0.06, steel, v=16, bev=0)
    for k in range(6):
        r = 0.012 + k * 0.009
        K.cyl("funnel ring", (at.x, at.y, at.z - 0.045 + k * 0.009), r, 0.01, steel, v=32, bev=0.001)
    a, b = Vector((S4_M.x + 0.21, S4_M.y - 0.08, at.z - 0.1)), Vector((at.x, at.y, at.z - 0.1))
    d = b - a
    K.cyl("funnel pipe", tuple((a + b) / 2), 0.01, d.length, steel, rot=tuple(Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()), v=12, bev=0)


def shot4():
    """THE SHARPER TEST. The lens low and wide in the hall: he walks up to the new machine with his dipper, dips it in
    the jar of the blend that passed, holds it over the funnel and lets one drop fall; the dial swings hard from PASS
    into FAKE, the beacon spins red; he jumps back and points at it, then at us."""
    W = hw_win
    T_IN = 0.2 * DUR                          # the walk up ends
    T_DIP = 0.28 * DUR
    T_DROP = 0.42 * DUR                        # the drop falls
    T_SWING = T_DROP + 0.32                    # ... lands, and the dial swings (arc 0.55)
    T_JUMP = T_SWING + 0.42
    T_POINT = 0.72 * DUR
    T_END = 0.9 * DUR                          # a last hop at us
    light = place_village_hall()
    needle, spin, found = s4_machine()
    # ---- him: walks up from the right, dips, holds the dipper over the funnel, jumps back, points
    data = load_data()
    P0 = S4_P + Vector((0.17, 0.13, 0))
    d0 = S4_P - P0
    data.place(P0.x, P0.y, math.degrees(math.atan2(d0.x, -d0.y)))
    hat = bee_hat(data)
    data.walk_to(S4_P, 0.0, T_IN)
    sc.frame_set(F(T_IN)); bpy.context.view_layer.update(); yw = data.arm.rotation_euler.z
    def yaw(t):
        y = math.degrees(yw) + (-22 - math.degrees(yw)) * W(t, T_IN, 0.35)       # turns to the jar and the machine
        y += 0 * W(t, T_DIP + 0.25, 0.3) * (1 - W(t, T_JUMP - 0.1, 0.3))      # to the funnel
        y += 25 * W(t, T_JUMP - 0.05, 0.25) - 20 * W(t, T_POINT - 0.3, 0.3) + 25 * W(t, T_END - 0.15, 0.25)   # back round to us
        return math.radians(y)
    for f in range(F(T_IN), NF + 1):
        t = (f - 1) / FPS
        back = 0.07 * W(t, T_JUMP, 0.22) - 0.06 * W(t, T_POINT - 0.1, 0.3) + 0.05 * W(t, T_END - 0.1, 0.25)
        lean = 0.0 * (1 - W(t, T_JUMP - 0.1, 0.2))
        p = S4_P + Vector((back + lean, -0.02 * W(t, T_JUMP, 0.22), 0.0))
        z = 0.07 * hw_kick(t - T_JUMP - 0.04, 0.15) + 0.06 * hw_kick(t - T_POINT, 0.14) + 0.07 * hw_kick(t - T_END, 0.14) + 0.045 * hw_kick(t - T_DIP - 0.35, 0.13) + 0.035 * hw_kick(t - T_DROP - 0.05, 0.12) + 0.05 * hw_kick(t - T_IN - 0.08, 0.13)
        data._kobj(t, loc=(p.x, p.y, z), rot=yaw(t))
    hw_layer(data, "spine", lambda t: (14 * W(t, T_DIP - 0.25, 0.25) * (1 - W(t, T_DIP + 0.2, 0.25)) + 8 * W(t, T_DROP - 0.3, 0.25) * (1 - W(t, T_SWING, 0.2))
                                      - 12 * W(t, T_JUMP, 0.15) * (1 - W(t, T_POINT - 0.1, 0.3)), 0, 0), 0, DUR + 0.4)
    sc.frame_set(1); bpy.context.view_layer.update()
    lf, rt = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    def short(sd, t, world, by=0.13):
        v = Vector(hw_rel(data, sd, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    MOUTH = Vector((S4_JAR.x, S4_JAR.y, S4_STOOL + 0.1))
    POINT_AT = S4_DIAL + Vector((0.05, 0, 0.02))
    OVER = S4_FUN + Vector((0, 0, 0.05))
    dk = [(0.0, (0.06, 0.09, -0.12)), (T_IN, (0.08, 0.1, -0.1)),
          (T_DIP - 0.25, (0.13, 0.05, -0.04)), (T_DIP, (0.13, 0.05, -0.1)), (T_DIP + 0.3, (0.13, 0.06, -0.04)),
          (T_DROP - 0.15, (0.09, 0.12, -0.02)), (T_DROP + 0.25, (0.09, 0.12, -0.01)),
          (T_JUMP, (0.1, 0.16, -0.03)), (T_JUMP + 0.3, (0.09, 0.17, 0.0)),
          (T_POINT, tuple(Vector(hw_rel(data, lf, T_POINT, POINT_AT)).normalized() * 0.15)), (T_POINT + 0.35, tuple(Vector(hw_rel(data, lf, T_POINT + 0.35, POINT_AT)).normalized() * 0.155)), (T_END, (0.1, 0.13, 0.03)), (DUR + 0.3, (0.1, 0.13, 0.04))]
    pk = [(0.0, (0.07, 0.1, -0.11)), (T_IN, (0.08, 0.1, -0.1)), (T_SWING, (0.1, 0.1, -0.08)),
          (T_JUMP, (0.08, 0.16, 0.03)), (T_JUMP + 0.3, (0.08, 0.16, 0.05)),
          (T_POINT, (0.06, 0.16, 0.0)), (T_POINT + 0.35, (0.09, 0.1, -0.09)), (T_END, (0.1, 0.14, 0.08)), (DUR + 0.3, (0.1, 0.14, 0.085))]
    data.reach(lf, hw_hand(data, lf, dk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.6)
    data.reach(rt, hw_hand(data, rt, pk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.4)
    CAM = Vector((0.29, -1.42, 0.55)); LOOK = Vector((0.24, 0.0, 0.47))
    data.look_at(CAM, 0.0, max_yaw=45, blend=0.0)
    data.look_at(S4_P + Vector((-0.12, -0.22, 0.32)), T_DIP - 0.45, max_yaw=50, max_pitch=20, blend=0.15)
    data.look_at(S4_P + Vector((-0.2, -0.12, 0.42)), T_DROP - 0.3, max_yaw=50, max_pitch=20, blend=0.15)
    data.look_at(S4_DIAL, T_SWING - 0.05, max_yaw=55, max_pitch=20, blend=0.12)
    data.look_at(CAM, T_JUMP + 0.25, max_yaw=45, blend=0.15)
    data.look_at(S4_DIAL, T_POINT - 0.1, max_yaw=55, max_pitch=20, blend=0.15)
    data.look_at(CAM, T_END - 0.2, max_yaw=45, blend=0.15)
    data.expression("determined", 0.0, T_DROP)
    data.expression("wry", T_DROP + 0.05, T_SWING - 0.05, blend=0.12)
    data.expression("surprised", T_SWING, T_POINT, blend=0.08)
    data.expression("pleased", T_POINT + 0.05, DUR + 1.0, blend=0.18)
    data.finish()
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, lf, fore=True)
    dr = dip["root"]
    # the jar of the blend sits where his dipper dips, the funnel where it drips (both built to his reach)
    sc.frame_set(F(T_DIP)); bpy.context.view_layer.update()
    hd = dr.matrix_world @ Vector((0, 0, dip["head_z"]))
    JH, JR = 0.11, 0.045
    jz = max(0.15, hd.z + 0.03 - JH)                   # the head just under the jar's rim
    K.cyl("blend stool", (hd.x, hd.y, jz / 2), 0.07, jz, hw_wood("stool wood", "#8A5E3A", "#A2744A", scale=5), v=24, bev=0.006)
    jr = jar("blend jar", (hd.x, hd.y, jz), r=JR, h=JH, fill=0.85, honey_col="#E6B850", label="PASSED")
    jr["root"].rotation_euler = (0, 0, math.radians(20))
    sc.frame_set(F(T_DROP)); bpy.context.view_layer.update()
    FUN = dr.matrix_world @ Vector((0, 0, dip["head_z"])) + Vector((0, 0, -0.06))
    s4_funnel(FUN)
    # ---- the drop: from the dipper's head into the funnel
    drop = K.sph("honey drop", (0, 0, 0), 0.012, hw_honey("drop honey", "#E6A52A", glow=1.5, clear=0.3), scale=(1, 1, 1.3))
    sc.frame_set(F(T_DROP)); bpy.context.view_layer.update()
    head0 = dr.matrix_world @ Vector((0, 0, dip["head_z"]))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t < T_DROP:
            sc.frame_set(f); bpy.context.view_layer.update()
            p = dr.matrix_world @ Vector((0, 0, dip["head_z"] - 0.02)); s = 0.4 + 0.6 * W(t, T_DIP, 0.3)
        else:
            u = min(1.0, (t - T_DROP) / 0.3)
            p = head0.lerp(FUN + Vector((0, 0, -0.02)), u * u); s = 1.0 if u < 1 else 1e-3
        drop.location = p; drop.scale = (s, s, 1.3 * s)
        drop.keyframe_insert("location", frame=f); drop.keyframe_insert("scale", frame=f)
    # ---- the dial swings hard from PASS into FAKE (an overshoot and a shiver), the beacon spins
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        u = max(0.0, (t - T_SWING) / 0.35)
        a = -55 + 115 * min(1.0, ease(min(1.0, u))) + 14 * math.sin(min(u, 4.0) * 5.0) * math.exp(-1.4 * u) * (u > 0) + 1.5 * math.sin(t * 37) * (u > 1)
        needle.rotation_euler = (0, math.radians(a), 0); needle.keyframe_insert("rotation_euler", frame=f)
        on = W(t, T_SWING, 0.1)
        spin.rotation_euler = (0, 0, on * (t - T_SWING) * 14.0); spin.scale = (max(1e-3, on),) * 3
        spin.keyframe_insert("rotation_euler", frame=f); spin.keyframe_insert("scale", frame=f)
        g = max(1e-3, W(t, T_SWING + 0.25, 0.12)); found.scale = (g, g, g); found.keyframe_insert("scale", frame=f)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=26, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.04, 0.12, 0.0)) * ease(t / DUR), LOOK + Vector((-0.03, 0, 0.01)) * ease(t / DUR), S4_DIAL))
    meshes_of = lambda *names: [o for o in bpy.data.objects if o.type in ('MESH', 'FONT') and o.name.startswith(names)]
    return dict(lanes=[], kiosks=[], place="village_hall", light=light, data=data, rest=1, grips=("honey dipper", "blend jar", "funnel"),
                conseq=[("the new machine catches the rice syrup: its dial swings from PASS into FAKE, RICE SYRUP FOUND lights up and the beacon spins", lambda: meshes_of("test machine", "dial", "beacon", "screen found"), T_SWING, DUR, {"hero": True}),
                        ("the needle swings from PASS to FAKE", lambda: meshes([needle]) + meshes_of("test machine dial"), T_SWING, T_SWING + 0.6, {"moves": True})])
