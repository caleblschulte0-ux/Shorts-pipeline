"""BEAT 3: "So when the lava came, it hit the wall and turned away from the town."

The top of the earth wall: a crest of crushed black rock, the town's roofs safe behind it, the black lava field on the
other side. HIGH, out over the lava, looking down at him on the crest. The lava front, a huge glowing front of cracked
black crust with orange in every crack, rolls in across the field below him and slams into the wall's face, its crust
buckling and splitting red; he braces a fire hose and blasts it, and a huge cloud of white steam bursts up; the front
grinds sideways and slides off along the wall, away from the town; he follows it round, still spraying, and turns to
us, pleased."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FACE_Y = -S3_CREST / 2      # the crest's outer edge (y); the outer face runs down to the foot at -S3_BASE / 2


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


S3_PILE = S3_H - 0.4           # the old lava already heaped against the face: the field rises to here at the wall


def s3_ground_z(x, y):
    """the black lava field: months of old flows heaped up against the wall's outer face, falling away out to the fissure"""
    if y > 0.5: return 0.08 * lw_fbm(x * 0.3, y * 0.3, 19)   # inside the wall: the town's ground, far below the crest
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
    lw_grid("lava field ground", -30, 30, -30, 30, 90, 90, s3_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven)
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    K.box("crest track", (0, 0, S3_H + 0.03), (50, S3_CREST - 0.1, 0.06), lw_noise("crushed rock", "#3E3732", "#615750", scale=30, rough=0.95, bump=1.0, detail=10), bev=0.02)
    for k in range(24):                                   # the town inside the wall: street after street of tin roofs
        town_house(f"town house below {k}", (-17 + 4.6 * (k % 8) + rnd.uniform(-0.3, 0.3), 9.0 + 4.4 * (k // 8) + 0.8 * (k % 2), 0), yaw=rnd.uniform(-0.15, 0.15),   # their fronts, doors and windows to the wall
                   roof=ROOFS[k % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=100 + k)
    lava_rock("lava field rock", 120, (-25, 25, -25, -4.6), s3_ground_z, seed=9, r=(0.1, 0.35))
    lava_rock("heap rock", 70, (-5, 4, -4.6, -1.2), s3_ground_z, seed=13, r=(0.06, 0.2))        # the old lava heaped against the face: broken blocks
    lava_rock("field block", 420, (-14, 10, -14, -4.0), s3_ground_z, seed=19, r=(0.05, 0.22), moss=0.12)   # the field outside the wall: broken black blocks, a little moss
    lava_rock("wall face rock", 260, (-14, 12, -4.2, -1.0), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=27, r=(0.08, 0.26), moss=0.0)   # the black rock it is built of, on its face
    lava_rock("works rubble", 160, (-14, 14, 4.4, 9.0), s3_ground_z, seed=12, r=(0.08, 0.3))       # the works yard inside the wall
    for k, x in enumerate((-22.0, -12.0)):               # the eruption's plume off in the distance, a gas leaning over the town
        lw_steam(f"far plume {k}", (x, 40.0 + 4 * k, 0.0), w=7.0, h=24.0, seed=6.6 * k, col=(0.45, 0.43, 0.42), dens=1.6, lean=(0.6, -0.3), rise=1.0, t_end=DUR + 1.0)

    def light():
        k = iceland_light(sun_elev=24, sun_az=-30, sun=3.0, sky=0.4, haze=1.4)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(120))     # a REAL Icelandic-grey sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. From just above the crest, off his shoulder: the old lava heaped high against the face below him.
    A new front rolls in and slams the face right under his boots; he flinches, braces and blasts it with the hose;
    steam bursts up; the front grinds sideways and slides off along the wall; he follows it round with the spray and turns to
    us, pleased."""
    T_ROLL = 0.03 * DUR; T_HIT = 0.21 * DUR; T_SPRAY = 0.35 * DUR; T_SLIDE = 0.52 * DUR; T_THUMB = 0.75 * DUR; T_REL = T_THUMB - 0.12
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    P0 = Vector((-0.2, -0.45, S3_H + 0.06))
    data.place(P0.x, P0.y, 0.0)
    data.arm.location.z = P0.z
    kit = hard_hat(data)
    # ---- REDESIGN after board round 3 ("a contained oval pad ... a pool that stopped, not a flow that turned"): the
    # lava comes in as a TONGUE straight at the wall across the field, hits the face beside him, and TURNS: a new lobe
    # pushes out of its nose sideways along the wall's foot, away from the town's side, the tongue behind it crusting
    # over as a trail. Seen from above it is an L: the flow's path bent by the wall.
    lm = lava_mat("lava front", heat=1.0, scale=3.5, fresh=0.8)
    tm = lava_mat("lava tongue", heat=0.55, scale=3.0, fresh=0.25)
    Y_FACE = -S3_BASE / 2 + (S3_PILE / (S3_H * 0.97)) * (S3_BASE / 2 - S3_CREST / 2 - 0.1)   # where the heap meets the face
    Y_HIT = Y_FACE - 0.45
    XC = 1.0                                               # where the tongue strikes the face: off his right hand
    tout = []
    for k in range(25):
        a = 2 * math.pi * k / 25
        tout.append((0.85 * math.cos(a) + 0.07 * math.sin(3 * a), 3.2 * math.sin(a) + 0.15 * math.cos(4 * a)))
    tongue = lava("lava tongue", tout, z=0.0, thick=0.4, m=tm, seed=7, lumpy=0.16)
    out = []
    for k in range(25):                                    # the deflected lobe: long along the wall, its nose to -X
        a = 2 * math.pi * k / 25
        out.append((3.0 * math.cos(a) + 0.2 * math.sin(3 * a), 0.75 * math.sin(a) + 0.06 * math.cos(5 * a)))
    front = lava("lava front", out, z=0.0, thick=0.45, m=lm, seed=4, lumpy=0.18)
    Z_LAVA = S3_PILE - 0.3
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = ease(min(1.0, max(0.0, (t - T_ROLL) / (T_HIT - T_ROLL)))); v = W(t, T_HIT - 0.05, T_SLIDE + 0.9 - T_HIT)
        tip = -7.5 + (Y_HIT + 0.3 + 7.5) * u
        tongue.location = (XC, tip - 3.2, Z_LAVA - 0.05); tongue.keyframe_insert("location", frame=f)
        sq = 1.0 - 0.1 * lw_kick(t - T_HIT, 0.2)
        tongue.scale = (1.0 + 0.15 * lw_kick(t - T_HIT, 0.3), sq, 1.0 + 0.2 * lw_kick(t - T_HIT, 0.25)); tongue.keyframe_insert("scale", frame=f)
        sx = 0.12 + 0.88 * v
        front.location = (XC + 0.5 - 3.0 * sx, Y_HIT + 0.1, Z_LAVA + 0.03 + 0.15 * W(t, T_HIT - 0.08, 0.25) - 0.08 * W(t, T_SLIDE, 0.8))
        front.scale = (sx, 0.8 + 0.2 * v, 1.0); front.hide_render = t < T_HIT - 0.06
        for k_ in ("location", "scale", "hide_render"): front.keyframe_insert(k_, frame=f)
    lava_flow_key(tm, 0.0, DUR + 0.5, 0.1, axis=1)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.18)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; heat.default_value = 1.1 * (1 + 1.0 * lw_kick(t - T_HIT, 0.35) + 0.4 * W(t, T_HIT, 0.3)); heat.keyframe_insert("default_value", frame=f)
    # glowing chunks the impact throws up off the face, falling back onto the front
    cm = lava_mat("lava chunk", heat=1.2, scale=14.0, fresh=0.7); rnd = lw_random.Random(3); chunks = []
    for k in range(8):
        c = K.sph(f"lava chunk {k}", (0, 0, -5), rnd.uniform(0.015, 0.03), cm, seg=8, ring=6, scale=(1.0, 0.8, 0.7)); chunks.append(c)
        x0 = rnd.uniform(XC - 1.2, XC + 0.6); vy = -rnd.uniform(0.3, 0.9); vz = rnd.uniform(1.6, 2.6); t0 = T_HIT + rnd.uniform(-0.03, 0.12)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = t - t0
            if s < 0: c.location = (x0, Y_FACE, -3.0)
            else:
                z = S3_PILE + 0.7 + vz * s - 4.9 * s * s
                c.location = (x0 + 0.2 * s, Y_FACE - 0.15 + vy * s, max(z, S3_PILE + 0.55))
            c.keyframe_insert("location", frame=f)
    # ---- the hose: the nozzle in his hands, aimed down the face at the front; the jet; the steam where it lands
    noz = s3_hose_nozzle()
    aim = lambda t: Vector((XC - 0.5 + 0.12 * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2) - 1.6 * W(t, T_SLIDE, 0.9), Y_FACE - 0.15, S3_PILE + 0.3))   # the corner, then the nose as it slides
    jet_m = bpy.data.materials.get("hose water") or bpy.data.materials.new("hose water")
    jet_m.use_nodes = True; jb = jet_m.node_tree.nodes["Principled BSDF"]
    jb.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1); jb.inputs["Roughness"].default_value = 0.1
    jb.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1); jb.inputs["Emission Strength"].default_value = 0.3; jb.inputs["Transmission Weight"].default_value = 0.6
    drops = [K.sph(f"hose jet {k}", (0, 0, -5), 0.008, jet_m, seg=8, ring=6) for k in range(60)]
    # ---- his body: watching it come, a flinch at the hit, braced back as he opens up, turning with the slide
    yaw0 = math.radians(-12)
    def body_yaw(t):
        return yaw0 + math.radians(24) * (1 - W(t, 0.0, T_HIT + 0.1)) - math.radians(30) * W(t, T_SLIDE - 0.2, 1.0) \
            + math.radians(34) * W(t, T_THUMB - 0.3, 0.75)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.z += 0.03 * lw_kick(t - T_HIT, 0.2)                                       # a jolt at the hit
        p.y += -0.08 * W(t, 0.2, 0.3) + 0.1 * W(t, T_HIT, 0.2) - 0.06 * W(t, T_SPRAY - 0.1, 0.3)   # a step to the edge, a jump back at the hit, in again to spray
        p.y += 0.05 * W(t, T_SPRAY + 0.1, 0.4) * (1 - W(t, T_SPRAY + 0.6, 0.45))                  # the hose kicks him back; he digs in
        p.x -= 0.1 * W(t, T_SPRAY + 0.15, 0.6)                                                       # he shuffles along the crest after the front
        p.y += 0.07 * W(t, T_SLIDE, 0.45) * (1 - W(t, T_SLIDE + 0.55, 0.5))                       # the front grinds: he gives a step
        p.z -= 0.085 * W(t, T_HIT - 0.1, 0.35) * (1 - W(t, T_SPRAY + 0.35, 0.4))                 # knees bent, braced for the hit and the kick
        p.z -= 0.08 * W(t, T_SLIDE - 0.1, 0.35) * (1 - W(t, T_THUMB - 0.25, 0.4))                # and again as he leans the jet into the slide
        p.z += 0.04 * lw_kick(t - T_THUMB, 0.25)                                                     # a bounce: it's gone
        data._kobj(t, loc=tuple(p), rot=body_yaw(t))
        data._plant_feet_here(t, lift=(P0.z, P0.z))                                          # the crouch is in his KNEES: feet stay on the crest
    lw_layer(data, "spine", lambda t: (16 * W(t, 0.0, T_HIT - 0.1) * (1 - W(t, T_HIT - 0.1, 0.4)) - 6 * lw_kick(t - T_HIT, 0.3) + 12 * W(t, T_SPRAY - 0.3, 0.5) * (1 - W(t, T_THUMB - 0.3, 0.6))
                                       - 8 * W(t, T_THUMB, 0.5), 0, 6 * W(t, T_SLIDE, 0.8) * (1 - W(t, T_THUMB - 0.2, 0.6))), 0, DUR + 0.4)
    # his hands on the nozzle: both low at first, raised to aim as he opens it, both on it to the end
    sc.frame_set(1); bpy.context.view_layer.update()
    cam_side = Vector((0.45, -2.55, 0))
    sides = sorted("LR", key=lambda s: -(acts._shoulder(data, s) - data.arm.location).dot(cam_side))
    keys = lambda k: [(0.0, (0.09, -0.01, -0.13)), (0.45, (0.13, 0.0, 0.0)), (T_HIT + 0.12, (0.08, 0.0, -0.12)),
                      (T_SPRAY, (0.12, -0.01 - 0.01 * k, -0.05)), (T_SPRAY + 0.2, (0.07, -0.01 - 0.01 * k, -0.1)), (T_SPRAY + 0.5, (0.14, -0.02 - 0.01 * k, -0.01)),
                      (T_SLIDE + 0.45, (0.09, -0.01 - 0.01 * k, -0.11)), (T_SLIDE + 0.95, (0.13, -0.03 - 0.01 * k, -0.03)), (DUR + 0.5, (0.12, -0.02, -0.05))]
    k0 = [k_ for k_ in keys(0) if k_[0] < T_REL] + [(T_REL + 0.35, (0.1, -0.03, -0.1)), (T_REL + 0.75, (0.07, -0.05, -0.15)), (DUR + 0.5, (0.07, -0.05, -0.15))]   # lets the nozzle go: his hand drops, done (a fist up flipped his elbow)
    data.reach(sides[0], lw_hand(data, sides[0], k0), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)     # it held: one hand off the nozzle
    data.reach(sides[1], lw_hand(data, sides[1], keys(1)), 0.0, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)
    LENS = Vector((-0.6, -3.6, S3_H + 1.3))
    data.look_at(Vector((XC, -6.0, S3_PILE)), 0.0, max_yaw=50, max_pitch=50, blend=0.0)
    data.look_at(Vector((XC - 0.3, Y_HIT, S3_PILE + 0.4)), T_HIT - 0.15, max_yaw=50, max_pitch=55, blend=0.15)
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
    jc = bpy.data.curves.new("hose jet line", 'CURVE'); jc.dimensions = '3D'; jc.bevel_depth = 0.01; jc.bevel_resolution = 2
    jsp = jc.splines.new('POLY'); jsp.points.add(5)
    jet = lw_link(bpy.data.objects.new("hose jet line", jc)); jet.data.materials.append(jet_m)
    noz_tip = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); noz_tip[f] = noz.matrix_world @ Vector((0, -0.16, 0))
    noz_tip = {f: sum((noz_tip[min(NF, max(1, f + d))] for d in (-2, -1, 0, 1, 2)), Vector()) / 5 for f in noz_tip}   # the jet leaves a steadied tip
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; on = W(t, T_SPRAY, 0.12)
        a = noz_tip[f]; b = a.lerp(aim(t), max(0.02, on))
        pts = [a.lerp(b, u) + Vector((0, 0, 0.12 * on * math.sin(math.pi * u))) for u in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        for bp, q in zip(jsp.points, pts):
            bp.co = (q.x, q.y, q.z, 1.0); bp.keyframe_insert("co", frame=f)
        jet.hide_render = on < 0.02; jet.keyframe_insert("hide_render", frame=f)
    jr = lw_random.Random(17); jit = [Vector((jr.uniform(-1, 1), jr.uniform(-1, 1), jr.uniform(-1, 1))) for _ in drops]
    for k, o in enumerate(drops):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; on = t >= T_SPRAY
            if not on: o.location = (0, 0, -6)
            else:
                u = 0.75 + 0.25 * (((k / len(drops)) + 2.0 * t) % 1.0)
                a = noz_tip[f]; b = aim(t); m_ = a.lerp(b, u); m_.z += 0.25 * math.sin(math.pi * u)
                o.location = m_ + jit[k] * (0.015 + 0.12 * u * u)             # the jet fans out into fine spray as it falls
            o.keyframe_insert("location", frame=f)
    steam = []                                           # STEAM as a gas: it boils up where the jet lands, swelling into a column
    for k, t0 in enumerate((T_SPRAY + 0.06,)):          # that drifts off him and out over the field, off the lens's side
        b = aim(t0)
        steam.append(lw_steam(f"lava steam {k}", (1.4, -2.0, b.z - 0.3), w=0.95, h=3.4, seed=5.1 * k + 2, rise=2.4, dens=7.0,
                              lean=(0.25, 0.0), keys=[(t0, 0.0), (t0 + 0.8, 1.0), (DUR + 0.5, 0.8)], t_end=DUR + 1.0))
    # ---- the lens: just above the crest off his shoulder, out over the heap, looking down past him at the front
    CAM = LENS.copy() + Vector((0.0, 0.0, 0.45)); LOOK = Vector((-0.4, -0.8, S3_H + 0.16))    # high out over the heap: him on the crest, the town's roofs safe behind him, the front under him
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=56.0, fstop=22.0)
    def cam_at(t):                                          # it leans in at the hit, then drifts after the front as it slides off
        mv = Vector((0.03, 0.12, -0.03)) * W(t, T_HIT - 0.1, 0.9) + Vector((-0.12, 0.0, 0.0)) * W(t, T_SLIDE - 0.2, 1.4)
        return CAM + mv, LOOK + mv * 0.8, data.pos() + Vector((0, 0, 0.5))
    # CUT to the WIDE as the front grinds off (board round 2: "it never turns away from the town", "no town behind"):
    # high out over the lava field, the whole front against the wall's face sliding off along it, him small on the crest
    # with his jet and steam, the town's roofs safe on the far side
    T_W0, T_W1 = T_HIT - 0.15, T_REL - 0.1
    CW = Vector((3.4, -8.6, 8.2)); LW = Vector((-0.6, 1.0, 2.6))       # high out over the field: the tongue, the turn, the lobe along the wall, him and the town beyond
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.35, 0.15, -0.1)) * (t - T_W0), LW, Vector((0.0, -1.5, 4.0))), T_W0, T_W1, 56.0, 28.0)
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=("fire hose",), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("the lava front rolls in and slams into the wall's face, then slides off along it", lambda: [tongue, front], T_HIT - 0.2, DUR, {"whole": False}),
                        ("he blasts the front with the hose and a cloud of steam bursts up", lambda: steam, T_SPRAY + 0.1, DUR, {"whole": False, "moves": True})])
