"""BEAT 3: "So when the lava came, it hit the wall and turned away from the town."

The top of the earth wall: a crest of crushed black rock, the town's roofs safe behind it, the black lava field on the
other side. HIGH, out over the lava, looking down at him on the crest. The lava front, a huge glowing front of cracked
black crust with orange in every crack, rolls in across the field below him and slams into the wall's face, its crust
buckling and splitting red; he braces a fire hose and blasts it, and a huge cloud of white steam bursts up; the front
grinds sideways and slides off along the wall, away from the town; he follows it along the crest, still spraying, and
gives us a thumb up."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FACE_Y = -S3_CREST / 2      # the crest's outer edge (y); the outer face runs down to the foot at -S3_BASE / 2


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


S3_PILE = S3_H - 0.9           # the old lava already heaped against the face: the field rises to here at the wall


def s3_ground_z(x, y):
    """the black lava field: months of old flows heaped up against the wall's outer face, falling away out to the fissure"""
    u = max(0.0, min(1.0, (y + 16.0) / 11.0))
    return S3_PILE * ease(u) + 0.1 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_hose_nozzle():
    """a fire hose's brass nozzle with a grip, and the canvas hose running back from it"""
    root = K.empty("fire hose", (0, 0, 0))
    brass = lw_metal("nozzle brass", "#B8862E", rough=0.25)
    K.cyl("fire hose nozzle", (0, 0.0, 0.0), 0.028, 0.22, brass, rot=(math.pi / 2, 0, 0), v=20, parent=root)
    K.cyl("fire hose nozzle tip", (0, -0.13, 0.0), 0.018, 0.06, brass, rot=(math.pi / 2, 0, 0), v=16, parent=root)
    K.cyl("fire hose grip", (0, 0.05, -0.05), 0.02, 0.09, K.mat("nozzle grip", "#1E1E1E", rough=0.6), v=12, parent=root)
    lw_local(root)
    return root


def place_wall_crest():
    """THE TOP OF THE WALL: its crest track of crushed rock, the black lava field running away from its outer face,
    the town's roofs below it on the other side, a parked digger far along the crest, the plume over the far fissure."""
    rnd = lw_random.Random(31)
    lw_grid("lava field ground", -30, 30, -30, 30, 90, 90, s3_ground_z, lava_field_mat())
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    K.box("crest track", (0, 0, S3_H + 0.03), (50, S3_CREST - 0.1, 0.06), lw_noise("crushed rock", "#3E3732", "#615750", scale=30, rough=0.95, bump=1.0, detail=10), bev=0.02)
    for k in range(12):
        town_house(f"town house below {k}", (-12 + 2.6 * k + rnd.uniform(-0.3, 0.3), 7.5 + 2.6 * (k % 3), 0), yaw=math.pi + rnd.uniform(-0.2, 0.2),
                   w=2.1, d=1.6, roof=ROOFS[k % len(ROOFS)], wall=WALLS[k % len(WALLS)])
    lava_rock("lava field rock", 120, (-25, 25, -25, -4.6), s3_ground_z, seed=9, r=(0.1, 0.35))
    smoke = lw_smoke_mat("far plume", density=0.7, col=(0.45, 0.42, 0.4))
    for k in range(6):
        lw_puff(f"far plume {k}", (-24 + 6 * k, 38 + 3 * (k % 3), 10 + 3.5 * k), 7.0, smoke, scale=(1.4, 1.0, 1.0))   # the plume, blown over the town

    def light():
        return iceland_light(sun_elev=24, sun_az=-30, sun=3.0, sky=0.4, haze=1.4)
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. From just above the crest, off his shoulder: the old lava heaped high against the face below him.
    A new front rolls in and slams the face right under his boots; he flinches, braces and blasts it with the hose;
    steam bursts up; the front grinds sideways and slides off along the wall; he follows it round with the spray, lets
    go with one hand and gives us a thumb up."""
    T_ROLL = 0.03 * DUR; T_HIT = 0.21 * DUR; T_SPRAY = 0.35 * DUR; T_SLIDE = 0.52 * DUR; T_REL = 0.64 * DUR; T_THUMB = 0.75 * DUR
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    P0 = Vector((-0.2, -0.45, S3_H + 0.06))
    data.place(P0.x, P0.y, 0.0)
    data.arm.location.z = P0.z
    kit = hard_hat(data)
    # ---- the lava front: a long glowing lobe riding in over the old heap, ramming the face under him, sliding off
    lm = lava_mat("lava front", heat=1.0, scale=3.5, fresh=0.8)
    out = []
    for k in range(25):                                    # the front's outline: a long tongue, its nose to +X
        a = 2 * math.pi * k / 25
        out.append((2.6 * math.cos(a) + 0.2 * math.sin(3 * a), 0.8 * math.sin(a) + 0.08 * math.cos(5 * a)))
    front = lava("lava front", out, z=0.0, thick=0.75, m=lm, seed=4, lumpy=0.18)
    Y_FACE = -S3_BASE / 2 + (S3_PILE / (S3_H * 0.97)) * (S3_BASE / 2 - S3_CREST / 2 - 0.1)   # where the heap meets the face
    Y_HIT = Y_FACE - 0.45
    def where(t):
        y = -6.0 + (Y_HIT + 6.0) * ease(min(1.0, max(0.0, (t - T_ROLL) / (T_HIT - T_ROLL))))
        x = -1.4 - 1.6 * W(t, T_SLIDE - 0.25, 1.5) - 0.1 * t      # it grinds off along the wall, away from him
        z = S3_PILE - 0.3 + 0.35 * W(t, T_HIT - 0.08, 0.25) - 0.12 * W(t, T_SLIDE, 0.8)   # it rides up the face as it rams it
        return Vector((x, y, z))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; front.location = where(t); front.keyframe_insert("location", frame=f)
        sq = 1.0 - 0.1 * lw_kick(t - T_HIT, 0.2)
        front.scale = (1.0 + 0.08 * W(t, T_SLIDE, 1.0), sq, 1.0 + 0.2 * lw_kick(t - T_HIT, 0.25)); front.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.18)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; heat.default_value = 2.2 * (1 + 1.0 * lw_kick(t - T_HIT, 0.35) + 0.4 * W(t, T_HIT, 0.3)); heat.keyframe_insert("default_value", frame=f)
    # glowing chunks the impact throws up off the face, falling back onto the front
    cm = lw_emit("lava chunk", "#FF5A00", 1.3); rnd = lw_random.Random(3); chunks = []
    for k in range(14):
        c = K.sph(f"lava chunk {k}", (0, 0, -5), rnd.uniform(0.04, 0.09), cm, seg=8, ring=6); chunks.append(c)
        x0 = rnd.uniform(-3.0, -0.6); vy = -rnd.uniform(0.3, 0.9); vz = rnd.uniform(1.6, 2.6); t0 = T_HIT + rnd.uniform(-0.03, 0.12)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = t - t0
            if s < 0: c.location = (x0, Y_FACE, -3.0)
            else:
                z = S3_PILE + 0.7 + vz * s - 4.9 * s * s
                c.location = (x0 + 0.2 * s, Y_FACE - 0.15 + vy * s, max(z, S3_PILE + 0.55))
            c.keyframe_insert("location", frame=f)
    # ---- the hose: the nozzle in his hands, aimed down the face at the front; the jet; the steam where it lands
    noz = s3_hose_nozzle()
    aim = lambda t: Vector((-0.45 + 0.15 * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) - 0.3 * W(t, T_SLIDE, 0.8), Y_FACE + 0.5, S3_PILE + 0.6))
    jet_m = bpy.data.materials.get("hose water") or bpy.data.materials.new("hose water")
    jet_m.use_nodes = True; jb = jet_m.node_tree.nodes["Principled BSDF"]
    jb.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1); jb.inputs["Roughness"].default_value = 0.1
    jb.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1); jb.inputs["Emission Strength"].default_value = 0.6
    drops = [K.sph(f"hose jet {k}", (0, 0, -5), 0.016, jet_m, seg=8, ring=6) for k in range(30)]
    steam_m = lw_smoke_mat("lava steam", density=3.0, col=(0.93, 0.94, 0.96))
    steam = [lw_puff(f"lava steam {k}", (0, 0, -5), 1.0, steam_m) for k in range(8)]
    # ---- his body: watching it come, a flinch at the hit, braced back as he opens up, turning with the slide
    yaw0 = math.radians(-12)
    def body_yaw(t):
        return yaw0 + math.radians(12) * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) * W(t, T_SPRAY, 0.3) - math.radians(30) * W(t, T_SLIDE, 0.6) \
            + math.radians(34) * W(t, T_THUMB - 0.1, 0.4)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.z += 0.07 * lw_kick(t - T_HIT, 0.12)                                      # a hop at the hit
        p.y += 0.08 * W(t, T_HIT, 0.2) - 0.06 * W(t, T_SPRAY - 0.1, 0.3)            # jumps back from the edge, then leans back in to spray
        data._kobj(t, loc=tuple(p), rot=body_yaw(t))
    lw_layer(data, "spine", lambda t: (16 * W(t, 0.0, T_HIT - 0.1) * (1 - W(t, T_HIT, 0.12)) - 16 * lw_kick(t - T_HIT, 0.22) + 12 * W(t, T_SPRAY - 0.2, 0.3) * (1 - W(t, T_THUMB - 0.1, 0.3))
                                       - 8 * W(t, T_THUMB, 0.3), 0, 6 * W(t, T_SLIDE, 0.5) * (1 - W(t, T_THUMB, 0.3))), 0, DUR + 0.4)
    # his hands on the nozzle: both low at first, raised to aim as he opens it, the camera-side one lets go for the thumb
    sc.frame_set(1); bpy.context.view_layer.update()
    cam_side = Vector((0.45, -2.55, 0))
    sides = sorted("LR", key=lambda s: -(acts._shoulder(data, s) - data.arm.location).dot(cam_side))
    keys = lambda k: [(0.0, (0.13, -0.05, -0.16)), (T_HIT - 0.1, (0.14, -0.05, -0.15)), (T_HIT + 0.15, (0.12, -0.05, -0.12)),
                      (T_SPRAY, (0.15, -0.04 - 0.01 * k, -0.06)), (T_SLIDE, (0.16, -0.04, -0.05)), (DUR + 0.5, (0.16, -0.04, -0.06))]
    data.reach(sides[0], lw_hand(data, sides[0], keys(0)), 0.0, T_REL, lead=0.3, back=None, elbow_out=0.4)
    data.reach(sides[1], lw_hand(data, sides[1], keys(1)), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)
    PUMP = [(T_REL + 0.35, (0.12, 0.1, -0.03)), (T_THUMB + 0.22, (0.1, 0.12, 0.12)), (T_THUMB + 0.45, (0.12, 0.11, 0.05)),
            (T_THUMB + 0.68, (0.1, 0.12, 0.13)), (DUR + 0.4, (0.11, 0.12, 0.1))]          # the free fist punches the air, twice
    data.reach(sides[0], lw_hand(data, sides[0], PUMP), PUMP[0][0], DUR + 0.3, lead=0.4, back=None, elbow_out=0.5)
    LENS = Vector((0.25, -3.0, S3_H + 0.8))
    data.look_at(Vector((-3.0, -6.0, S3_PILE)), 0.0, max_yaw=50, max_pitch=50, blend=0.0)
    data.look_at(Vector((-0.9, Y_HIT, S3_PILE + 0.4)), T_HIT - 0.15, max_yaw=50, max_pitch=55, blend=0.15)
    data.look_at(aim(T_SPRAY), T_SPRAY, max_yaw=50, max_pitch=55, blend=0.25)
    data.look_at(Vector((-2.5, Y_HIT, S3_PILE + 0.4)), T_SLIDE + 0.1, max_yaw=50, max_pitch=55, blend=0.3)
    data.look_at(LENS, T_THUMB, max_yaw=50, max_pitch=50, blend=0.25)
    data.expression("alarmed", T_ROLL + 0.1, T_HIT + 0.3, blend=0.12)
    data.expression("determined", T_HIT + 0.35, T_SLIDE + 0.25, blend=0.2)
    data.expression("pleased", T_SLIDE + 0.35, DUR + 1.0, blend=0.25)
    data.finish()
    for f in range(1, NF + 1):                             # the nozzle in his hands, pointing at the spray
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        hs = [data.arm.matrix_world @ data.pb[f"hand.{s}"].tail for s in sides]
        p = (hs[0] + hs[1]) / 2 if t < T_REL else hs[1]
        d = (aim(t) - p).normalized()
        noz.location = p + d * 0.07; noz.rotation_euler = Vector((0, -1, 0)).rotation_difference(d).to_euler()
        noz.keyframe_insert("location", frame=f); noz.keyframe_insert("rotation_euler", frame=f)
    # the canvas hose: from the hydrant on the crest behind him, along the ground, up to the nozzle's tail
    cu = bpy.data.curves.new("fire hose line", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.02; cu.bevel_resolution = 3
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(3)
    hose = lw_link(bpy.data.objects.new("fire hose line", cu)); hose.data.materials.append(K.mat("hose canvas", "#B8342A", rough=0.7))
    HYD = Vector((P0.x - 1.4, P0.y + 0.6, S3_H))
    K.cyl("fire hydrant", (HYD.x, HYD.y, S3_H + 0.25), 0.07, 0.5, K.mat("hydrant red", "#C8231B", rough=0.4), v=16)
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        tail = noz.matrix_world @ Vector((0, 0.12, 0)); foot = data.arm.matrix_world.translation
        pts = [HYD + Vector((0, 0, 0.12)), Vector((foot.x - 0.6, foot.y + 0.35, S3_H + 0.06)),
               Vector((foot.x - 0.15, foot.y + 0.2, S3_H + 0.06)), tail]
        for bp, q in zip(sp.bezier_points, pts):
            bp.co = q; bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.keyframe_insert("co", frame=f)
    # the jet: a solid rope of water from the nozzle tip arcing down to the aim point, breaking into spray at its end
    jc = bpy.data.curves.new("hose jet line", 'CURVE'); jc.dimensions = '3D'; jc.bevel_depth = 0.014; jc.bevel_resolution = 2
    jsp = jc.splines.new('BEZIER'); jsp.bezier_points.add(2)
    jet = lw_link(bpy.data.objects.new("hose jet line", jc)); jet.data.materials.append(jet_m)
    noz_tip = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); noz_tip[f] = noz.matrix_world @ Vector((0, -0.16, 0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; on = W(t, T_SPRAY, 0.12)
        a = noz_tip[f]; b = a.lerp(aim(t), max(0.02, on)); mid = a.lerp(b, 0.5); mid.z += 0.18 * on
        for bp, q in zip(jsp.bezier_points, (a, mid, b)):
            bp.co = q; bp.handle_left_type = bp.handle_right_type = 'AUTO'; bp.keyframe_insert("co", frame=f)
        jet.hide_render = on < 0.02; jet.keyframe_insert("hide_render", frame=f)
    jr = lw_random.Random(17); jit = [Vector((jr.uniform(-1, 1), jr.uniform(-1, 1), jr.uniform(-1, 1))) for _ in drops]
    for k, o in enumerate(drops):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = t >= T_SPRAY
            if not on: o.location = (0, 0, -6)
            else:
                u = 0.75 + 0.25 * (((k / len(drops)) + 2.0 * t) % 1.0)
                a = noz_tip[f]; b = aim(t); m_ = a.lerp(b, u); m_.z += 0.25 * math.sin(math.pi * u)
                o.location = m_ + jit[k] * (0.03 + 0.25 * u * u)              # the jet fans out into spray as it falls
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(steam):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; t0 = T_SPRAY + 0.06 + 0.12 * k; s = W(t, t0, 0.4)
            b = aim(t); age = max(0.0, t - t0)                      # it boils up off the front and rolls back over the crest
            o.location = (b.x - 0.55 - 0.16 * k - 0.3 * age, b.y + 0.1 + 0.9 * age + 0.15 * (k % 3), b.z + 0.1 + 0.4 * s + 0.6 * age)
            r = 0.3 * s * (1 + 0.08 * k) * (1 + 0.4 * age)
            lw_puff_key(o, f, (r, r, r * 0.9)); o.keyframe_insert("location", frame=f)
    # ---- the lens: just above the crest off his shoulder, out over the heap, looking down past him at the front
    CAM = LENS.copy(); LOOK = Vector((-0.59, -0.12, S3_H + 0.68))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=50.0, fstop=22.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.12, 0.0, 0.03)) * W(t, T_SLIDE - 0.2, 1.4), LOOK + Vector((-0.2, 0.0, 0.0)) * W(t, T_SLIDE - 0.2, 1.4), data.pos() + Vector((0, 0, 0.5))))
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=("fire hose",),
                boxes=[],
                conseq=[("the lava front rolls in and slams into the wall's face, then slides off along it", lambda: [front], T_ROLL, DUR, {"whole": False}),
                        ("he blasts the front with the hose and a cloud of steam bursts up", lambda: steam, T_SPRAY + 0.1, DUR, {"whole": False, "moves": True})])
