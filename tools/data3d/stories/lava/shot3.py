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
S3_YAW = -12.0                  # his body, between the lava (0) and the lens
S3_CAMD = (-2.1, -2.5, 2.2)    # the lens from his feet: ALONG the wall, a little out over the lava side, over his head
S3_LOOKD = (0.0, 0.0, 0.2)
S3_LENS = 50.0
S3_FACE = (0.36, 0.7)
S3_XC = -0.25
S3_GLOWL = []
S3_PHI = math.radians(0.0)   # the tongue comes in across the field on this bearing
S3_STEAM = (0.3, 0.5)
S3_FACE_Y = -S3_CREST / 2      # the crest's outer edge (y); the outer face runs down to the foot at -S3_BASE / 2


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


S3_PILE = S3_H - 0.36           # the old lava heaped against the face: the field rises to here, a man's height and more of black wall still standing over it


def s3_ground_z(x, y):
    """the black lava field: months of old flows heaped up against the wall's outer face, falling away out to the fissure"""
    if y > 0.5: return 0.08 * lw_fbm(x * 0.3, y * 0.3, 19) - 1.0 * ease(max(0.0, min(1.0, (y - 4.2) / 1.6))) + 0.14 * max(0.0, y - 21.5)   # inside the wall: the town, on lower ground than the lava field
    u = max(0.0, min(1.0, (y + 16.0) / 11.0))
    return S3_PILE * ease(u) + 0.1 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_hose_nozzle():
    """a fire hose's brass nozzle with a grip, and the canvas hose running back from it"""
    root = K.empty("fire hose", (0, 0, 0))
    brass = lw_metal("nozzle chrome", "#C9CCD0", rough=0.22); red = lw_paint("nozzle red", "#C8231B", rough=0.4); blk = lw_rubber("nozzle grip", "#1A1A1A", rough=0.6)
    K.cyl("fire hose nozzle", (0, 0.02, 0.0), 0.027, 0.14, red, rot=(math.pi / 2, 0, 0), v=20, parent=root)          # a fireman's branch: red body,
    K.cyl("fire hose nozzle coupling", (0, 0.1, 0.0), 0.034, 0.035, brass, rot=(math.pi / 2, 0, 0), v=20, parent=root)   # a bright coupling to the hose,
    K.cyl("fire hose nozzle tip", (0, -0.085, 0.0), 0.02, 0.08, brass, rot=(math.pi / 2, 0, 0), v=16, parent=root)      # a bright barrel
    K.cyl("fire hose nozzle bumper", (0, -0.135, 0.0), 0.03, 0.03, blk, rot=(math.pi / 2, 0, 0), v=16, parent=root)     # and a black rubber bumper at its mouth,
    for sx in (-1, 1): K.box("fire hose nozzle bale", (sx * 0.032, -0.01, 0.03), (0.008, 0.012, 0.07), brass, bev=0.003, parent=root)   # the bale handle over its top
    K.box("fire hose nozzle bale", (0, -0.01, 0.066), (0.072, 0.014, 0.01), brass, bev=0.004, parent=root)
    K.cyl("fire hose grip", (0, 0.05, -0.05), 0.02, 0.09, blk, v=12, parent=root)
    lw_local(root)
    return root


def place_wall_crest():
    """THE TOP OF THE WALL: its crest track of crushed rock, the black lava field running away from its outer face,
    the town's roofs below it on the other side, a parked digger far along the crest, the plume over the far fissure."""
    rnd = lw_random.Random(31)
    lw_grid("lava field ground", -30, 30, -30, 30, 90, 90, s3_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven)
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8, clear=lambda x, y: abs(x + 0.2) < 0.4 and abs(y + 0.6) < 0.34)
    # the crest is HEAPED CRUSHED ROCK (board B1, and six rounds before it: "a smooth flat band, like asphalt"): a lumpy bed of real rock with loose stones all over it
    lw_grid("crest rock bed", -14, 14, -S3_CREST / 2 - 0.14, S3_CREST / 2 + 0.14, 220, 22,                  # a ROUNDED heap: its shoulders roll off into the faces (board B2: "a slab with a clean overhanging lip")
            lambda x, y: S3_H + 0.012 + 0.036 * lw_vn(x * 7.0, y * 7.0, 51) - 1.6 * max(0.0, abs(y) - 0.74 - 0.05 * lw_vn(x * 2.0, 3.0, 9)) ** 1.3,
            ph_mat("aerial_rocks_02", scale=0.45, tint="#3A3632", name="crest crushed rock"))
    lava_rock("crest gravel", 700, (-8.0, 8.0, -S3_CREST / 2, S3_CREST / 2), lambda x, y: S3_H + 0.02, seed=61, r=(0.02, 0.065), moss=0.0,
              avoid=lambda x, y: abs(x + 0.2) < 0.36 and abs(y + 0.6) < 0.3)
    rk_ = lw_noise("wall rock", "#151413", "#3C3834", scale=7, rough=0.95, bump=1.0, detail=8); rc_ = lw_random.Random(77)
    for k in range(90):                                  # the crest is a HEAP OF ROCK, not a kerbed road: boulders along both its edges (not where he stands)
        x = rc_.uniform(-7.0, 7.0); front = k % 3 != 0
        if front and -0.85 < x < 0.45: continue
        y = (-S3_CREST / 2 + rc_.uniform(-0.12, 0.1)) if front else (S3_CREST / 2 + rc_.uniform(-0.1, 0.15))
        r = rc_.uniform(0.09, 0.22)
        lw_block("crest boulder", (x, y, S3_H + r * 0.45), r, rk_, rc_, squash=0.75)
    for k in range(20):                                    # (the town is behind and below the wall: not in this lens, which looks down the face from the lava side): street after street of tin roofs
        d_ = 13.5 + 4.6 * (k // 5) + rnd.uniform(-0.8, 0.8); l_ = 3.6 * (k % 5 - 2) + rnd.uniform(-0.7, 0.7)      # down the lens's line, BEHIND and BELOW the wall, on the town's own ground
        hx_, hy_ = -0.2 + 0.707 * (d_ + l_), -0.6 + 0.707 * (d_ - l_)
        if hy_ < 7.0: continue
        town_house(f"town house below {k}", (hx_, hy_, s3_ground_z(hx_, hy_)), yaw=0.6 + rnd.uniform(-0.4, 0.4), w=rnd.uniform(2.2, 3.0), d=rnd.uniform(2.2, 2.8),
                   roof=ROOFS[(k * 3 + 1) % len(ROOFS)], wall=WALLS[(k * 2) % len(WALLS)], storeys=1, base=0.3, seed=100 + k)
    lava_rock("lava field rock", 120, (-25, 25, -25, -4.6), s3_ground_z, seed=9, r=(0.1, 0.35), moss=0.0)
    lava_rock("heap rock", 70, (-5, 4, -4.6, -1.2), s3_ground_z, seed=13, r=(0.06, 0.2), moss=0.0, avoid=lambda x, y: abs(x - S3_XC + 0.3 * (y + 1.5)) < 1.3 and y > -3.6)        # the old lava heaped against the face: broken blocks
    lava_rock("field block", 420, (-14, 10, -14, -4.0), s3_ground_z, seed=19, r=(0.05, 0.22), moss=0.0)   # the field outside the wall: broken black blocks, a little moss
    lava_rock("wall face rock", 260, (-14, 12, -4.2, -1.0), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=27, r=(0.08, 0.26), moss=0.0)   # the black rock it is built of, on its face
    lava_rock("wall face rock near", 420, (-7.0, 4.0, -1.45, -0.82), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=29, r=(0.06, 0.16), moss=0.0)
    lava_rock("works rubble", 160, (-14, 14, 4.4, 5.8), s3_ground_z, seed=12, r=(0.08, 0.3), moss=0.0)       # the works yard inside the wall
    for k, x in enumerate(()):   # the eruption's plume off in the distance, a gas leaning over the town
        lw_steam(f"far plume {k}", (x, 30.0, 2.0), w=7.0, h=24.0, seed=6.6 * k, col=(0.3, 0.29, 0.29), dens=2.2, lean=(0.5, 0.0), rise=1.0, t_end=DUR + 1.0)

    def light():
        k = iceland_light(sun_elev=24, sun_az=-30, sun=3.0, sky=0.4, haze=1.4)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(110))     # a REAL Icelandic-grey sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. From just above the crest, off his shoulder: the old lava heaped high against the face below him.
    A new front rolls in and slams the face right under his boots; he flinches, braces and blasts it with the hose;
    steam bursts up; the front grinds sideways and slides off along the wall; he follows it round with the spray and turns to
    us, pleased."""
    T_ROLL = -0.2; T_HIT = 0.22 * DUR; T_SPRAY = 0.3 * DUR; T_SLIDE = 0.5 * DUR; T_THUMB = 0.8 * DUR; T_REL = T_THUMB - 0.12
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    P0 = Vector((-0.2, -0.6, S3_H + 0.06))
    data.place(P0.x, P0.y, 0.0)
    data.arm.location.z = P0.z
    kit = hard_hat(data)
    # ---- REDESIGN after board round 3 ("a contained oval pad ... a pool that stopped, not a flow that turned"): the
    # lava comes in as a TONGUE straight at the wall across the field, hits the face beside him, and TURNS: a new lobe
    # pushes out of its nose sideways along the wall's foot, away from the town's side, the tongue behind it crusting
    # over as a trail. Seen from above it is an L: the flow's path bent by the wall.
    lm = lava_mat("lava front", heat=1.3, scale=3.5, fresh=0.45)
    tm = lava_mat("lava tongue", heat=2.2, scale=3.0, fresh=0.45)     # HOT as it comes: a crusted tongue read as black rock in the first still
    Y_FACE = -S3_BASE / 2 + (S3_PILE / (S3_H * 0.97)) * (S3_BASE / 2 - S3_CREST / 2 - 0.1)   # where the heap meets the face
    Y_HIT = Y_FACE - 0.3
    XC = S3_XC                                             # where the tongue strikes the face: right under him
    tout = []
    for k in range(25):
        a = 2 * math.pi * k / 25
        tout.append((0.5 * math.cos(a) + 0.04 * math.sin(3 * a), 0.7 * math.sin(a) + 0.05 * math.cos(4 * a)))
    tongue = lava("lava tongue", tout, z=0.0, thick=0.2, m=tm, seed=7, lumpy=0.07)
    out = []
    for k in range(25):                                    # the deflected lobe: long along the wall, its nose to -X
        a = 2 * math.pi * k / 25
        out.append((0.9 * math.cos(a) + 0.07 * math.sin(3 * a), 0.4 * math.sin(a) + 0.04 * math.cos(5 * a)))
    front = lava("lava front", out, z=0.0, thick=0.2, m=lm, seed=4, lumpy=0.08)
    Z_LAVA = S3_PILE - 0.3
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = ease(min(1.0, max(0.0, (t - T_ROLL) / (T_HIT - T_ROLL)))); v = W(t, T_HIT - 0.05, T_SLIDE + 0.9 - T_HIT)
        tip = (Y_HIT - 0.1) + 0.4 * u                      # in the first still its glowing nose is already in frame, a metre off the wall's foot
        s_ = Y_HIT - (tip - 0.7); tongue.location = (XC + math.sin(S3_PHI) * s_, Y_HIT - math.cos(S3_PHI) * s_, S3_PILE - 0.03); tongue.rotation_euler = (0, 0, S3_PHI); tongue.keyframe_insert('location', frame=f)     # ON the old heap's rocks, not under them: it is seen coming in the first still; tongue.keyframe_insert("location", frame=f)
        sq = 1.0 - 0.1 * lw_kick(t - T_HIT, 0.2)
        tongue.scale = (1.0 + 0.15 * lw_kick(t - T_HIT, 0.3), sq, 1.0 + 0.2 * lw_kick(t - T_HIT, 0.25)); tongue.keyframe_insert("scale", frame=f)
        sx = 0.12 + 0.88 * v
        front.location = (XC - 0.1 * sx, Y_HIT + 0.12, S3_PILE - 0.08 + 0.1 * W(t, T_HIT - 0.08, 0.25) + 0.05 * W(t, T_SLIDE, 0.8))      # it PILES UP against the face: it never sinks back
        front.scale = (sx, 0.8 + 0.2 * v, 1.0); front.hide_render = t < T_HIT - 0.06
        for k_ in ("location", "scale", "hide_render"): front.keyframe_insert(k_, frame=f)
    # ROUND 7 (close): the front is CRUST, not a sheet (board 6: "a tiled cell texture ... no height, no crust and no
    # front"): broken black crust blocks ride the tongue, and on the front they heap and BUCKLE up against the face
    # as it grinds along it, tipping up, glowing in their cracks
    cm_ = lava_mat("lava crust block", heat=1.4, scale=1.6, fresh=0.0)      # a broken plate is BLACK with a seam or two (board B2: "the same crackle net on every block"); rb = lw_random.Random(23)
    rb = lw_random.Random(23)
    for k in range(14):
        a_ = rb.uniform(0, 2 * math.pi); rr = math.sqrt(rb.random())
        b_ = lw_block("tongue crust", (0.34 * rr * math.cos(a_), 0.55 * rr * math.sin(a_), 0.16 + rb.uniform(0, 0.04)), rb.uniform(0.04, 0.09), cm_, rb, squash=0.5)
        b_.parent = tongue; b_.rotation_euler = (rb.uniform(-0.3, 0.3), rb.uniform(-0.3, 0.3), rb.uniform(0, 6.3))
    fb = []
    for k in range(40):
        bx = rb.uniform(-1.0, 1.0); by = rb.uniform(-0.7, 0.7) * math.sqrt(max(0.0, 1 - bx * bx))
        o_ = lw_block("front crust", (0, 0, -5), rb.uniform(0.045, 0.11) * (1.0 + 0.6 * max(0.0, by)), cm_, rb, squash=0.6)
        fb.append((o_, bx, by, rb.uniform(-0.4, 0.4), rb.uniform(0, 6.3), rb.uniform(0.0, 0.25)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; v = W(t, T_HIT - 0.05, T_SLIDE + 0.9 - T_HIT); sx = 0.12 + 0.88 * v
        fx = XC - 0.1 * sx; fz = S3_PILE - 0.08 + 0.1 * W(t, T_HIT - 0.08, 0.25) + 0.05 * W(t, T_SLIDE, 0.8)
        for o_, bx, by, tilt, spin, lag in fb:
            on = t >= T_HIT - 0.06 + lag * 0.4
            buck = W(t, T_HIT + lag, 0.6) * max(0.0, by)          # the side against the face piles up and tips over
            o_.location = (fx + 0.9 * sx * bx, Y_HIT + 0.12 + 0.4 * by, (fz + 0.17 + 0.14 * buck) if on else -6.0)
            o_.rotation_euler = (tilt + 0.9 * buck, 0.6 * buck * bx, spin + 0.3 * v)
            o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    lava_flow_key(tm, 0.0, DUR + 0.5, 0.1, axis=1)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.18)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]; heat_t = tm.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; cool = 1 - 0.9 * W(t, T_SLIDE + 0.3, T_THUMB - T_SLIDE)
        heat.default_value = 1.1 * (1 + 1.0 * lw_kick(t - T_HIT, 0.35) + 0.4 * W(t, T_HIT, 0.3)) * cool; heat.keyframe_insert("default_value", frame=f)
        heat_t.default_value = 2.2 * cool; heat_t.keyframe_insert("default_value", frame=f)
        heat_c = cm_.node_tree.nodes["lava heat"].inputs[1]; heat_c.default_value = 1.5 * cool; heat_c.keyframe_insert("default_value", frame=f)   # hosed, it crusts over: stopped
    # glowing chunks the impact throws up off the face, falling back onto the front
    cm = lava_mat("lava chunk", heat=1.2, scale=14.0, fresh=0.7); rnd = lw_random.Random(3); chunks = []
    for k in range(8):
        c = K.sph(f"lava chunk {k}", (0, 0, -5), rnd.uniform(0.015, 0.03), cm, seg=8, ring=6, scale=(1.0, 0.8, 0.7)); chunks.append(c)
        x0 = rnd.uniform(XC - 0.4, XC + 0.4); vy = -rnd.uniform(0.3, 0.9); vz = rnd.uniform(1.6, 2.6); t0 = T_HIT + rnd.uniform(-0.03, 0.12)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = t - t0
            if s < 0: c.location = (x0, Y_FACE, -3.0)
            else:
                z = S3_PILE + 0.3 + vz * s - 4.9 * s * s
                c.location = (x0 + 0.2 * s, Y_FACE - 0.15 + vy * s, max(z, S3_PILE + 0.2))
            c.keyframe_insert("location", frame=f)
    # ---- the hose: the nozzle in his hands, aimed down the face at the front; the jet; the steam where it lands
    noz = s3_hose_nozzle()
    aim = lambda t: Vector((XC - 0.08 + 0.08 * math.sin(2 * math.pi * (t - T_SPRAY) / 1.2), Y_HIT + 0.2, S3_PILE + 0.2))   # ONE target, where the front meets the face (board B1: the jet jumped sides between stills)
    jet_m = bpy.data.materials.get("hose water") or bpy.data.materials.new("hose water")
    jet_m.use_nodes = True; jb = jet_m.node_tree.nodes["Principled BSDF"]
    jb.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1); jb.inputs["Roughness"].default_value = 0.1
    jb.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1); jb.inputs["Emission Strength"].default_value = 0.3; jb.inputs["Transmission Weight"].default_value = 0.6
    drops = []                                             # (no loose drops: at this size they read as popcorn)
    # ---- his body: watching it come, a flinch at the hit, braced back as he opens up, turning with the slide
    yaw0 = math.radians(S3_YAW)
    def body_yaw(t):
        return yaw0 + math.radians(10) * (1 - W(t, 0.0, T_HIT + 0.1)) - math.radians(10) * W(t, T_SLIDE - 0.2, 1.0) \
            - math.radians(12) * W(t, T_THUMB - 0.3, 0.75)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.z += 0.03 * lw_kick(t - T_HIT, 0.2)                                       # a jolt at the hit
        p.y += -0.08 * W(t, 0.2, 0.3) + 0.1 * W(t, T_HIT, 0.2) - 0.06 * W(t, T_SPRAY - 0.1, 0.3)   # a step to the edge, a jump back at the hit, in again to spray
        p.y += 0.05 * W(t, T_SPRAY + 0.1, 0.4) * (1 - W(t, T_SPRAY + 0.6, 0.45))                  # the hose kicks him back; he digs in
        p.x -= 0.1 * W(t, T_SPRAY + 0.15, 0.6)                                                       # he shuffles along the crest after the front
        p.x += 0.09 * W(t, T_HIT + 0.25, 0.3) * (1 - W(t, T_SPRAY + 0.1, 0.4))                     # a sidestep to get the hose on it
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
    cam_side = Vector(S3_CAMD).xy.to_3d()
    sides = sorted("LR", key=lambda s: -(acts._shoulder(data, s) - data.arm.location).dot(cam_side))
    keys = lambda k: [(0.0, (0.13, 0.0, 0.0)), (T_HIT + 0.12, (0.08, 0.0, -0.12)),
                      (T_SPRAY, (0.12, -0.01 - 0.01 * k, -0.05)), (T_SPRAY + 0.2, (0.07, -0.01 - 0.01 * k, -0.1)), (T_SPRAY + 0.5, (0.14, -0.02 - 0.01 * k, -0.01)),
                      (T_SLIDE + 0.45, (0.09, -0.01 - 0.01 * k, -0.11)), (T_SLIDE + 0.95, (0.13, -0.03 - 0.01 * k, -0.03)), (DUR + 0.5, (0.12, -0.02, -0.05))]
    k0 = [k_ for k_ in keys(0) if k_[0] < T_REL] + [(T_REL + 0.35, (0.11, 0.04, -0.09)), (T_REL + 0.75, (0.08, 0.09, -0.13)), (DUR + 0.5, (0.08, 0.1, -0.13))]   # lets the nozzle go: his hand drops, done (a fist up flipped his elbow)
    data.reach(sides[0], lw_hand(data, sides[0], k0), -0.6, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)     # it held: one hand off the nozzle
    data.reach(sides[1], lw_hand(data, sides[1], keys(1)), -0.6, DUR + 0.4, lead=0.3, back=None, elbow_out=0.4)
    LENS = P0 + Vector(S3_CAMD)
    data.look_at(Vector((XC, Y_HIT - 1.0, S3_PILE)), 0.0, max_yaw=50, max_pitch=50, blend=0.0)
    data.look_at(Vector((XC - 0.3, Y_HIT, S3_PILE + 0.4)), T_HIT - 0.15, max_yaw=50, max_pitch=22, blend=0.15)
    data.look_at(aim(T_SPRAY), T_SPRAY, max_yaw=50, max_pitch=22, blend=0.25)
    data.look_at(aim(T_SLIDE + 0.7), T_SLIDE + 0.1, max_yaw=50, max_pitch=22, blend=0.3)
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
    hose = lw_link(bpy.data.objects.new("fire hose line", cu)); hose.data.materials.append(lw_canvas("hose canvas", "#B8342A"))
    HYD = Vector((P0.x + 0.8, P0.y + 0.2, S3_H))            # the hose GOES somewhere: a real hydrant (Poly Haven) on the crest right behind him, in frame
    try: ph_model("fire_hydrant", (HYD.x, HYD.y, S3_H + 0.02), rot=(0, 0, 0.4), scale=0.42, name="fire hydrant", only=("fire_hydrant", "fire_hydrant_cap_01", "fire_hydrant_cap_02", "fire_hydrant_cap_03", "fire_hydrant_chain"))
    except FileNotFoundError: K.cyl("fire hydrant", (HYD.x, HYD.y, S3_H + 0.25), 0.07, 0.5, lw_paint("hydrant red", "#C8231B", rough=0.4), v=16)
    glowl = [lw_point(f"lava front glow {k_}", (XC - 0.45 + 0.45 * k_, Y_HIT + 0.1, S3_PILE + 0.5), 0.0, col=(1.0, 0.42, 0.1), r=0.3) for k_ in range(3)]   # the front LIGHTS the wall's face and him
    S3_GLOWL[:] = glowl
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS
        for g_ in glowl: g_.data.energy = 22.0 * W(t, T_HIT - 0.3, 0.5) * (1 - 0.9 * W(t, T_SLIDE + 0.3, T_THUMB - T_SLIDE)); g_.data.keyframe_insert("energy", frame=f)
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        tail = noz.matrix_world @ Vector((0, 0.12, 0)); foot = data.arm.matrix_world.translation
        pts = [HYD + Vector((-0.05, -0.02, 0.16)), Vector((foot.x + 0.38, foot.y + 0.1, S3_H + 0.07)),
               Vector((foot.x + 0.16, foot.y + 0.22, S3_H + 0.06)), tail]
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
    # STEAM as a gas: ONE white cloud boils up off the lava where the jet lands and keeps growing while he sprays
    t0 = T_SPRAY + 0.05
    steam = [lw_fire_column("lava steam 0", (XC - 0.08, Y_HIT + 0.15, S3_PILE + 0.1), w=S3_STEAM[0], h_fire=0.15, h_smoke=S3_STEAM[1], lean=(-0.1, -0.1), t_end=DUR + 1.0,
                            seed=7.1, fire=0.0, smoke_d=12.0, smoke=(0.95, 0.96, 0.97), rise=2.2, flame_d=0.0, spread=0.3,
                            keys=[(t0, 0.0), (t0 + 0.4, 0.7), (T_SLIDE + 0.3, 1.0), (DUR + 0.5, 1.0)], grow=True)]
    try:                                                 # the lava's lamps light the rock and him, never the lava's own crust or the steam (lit orange, white steam went tan)
        gc = bpy.data.collections.new("glow receivers"); bpy.context.scene.collection.children.link(gc)
        for o_ in [tongue, front] + [o for o, *_ in fb] + [o for o in steam if hasattr(o, "name")]: gc.objects.link(o_)
        for co_ in gc.collection_objects: co_.light_linking.link_state = 'EXCLUDE'
        for l_ in S3_GLOWL: l_.light_linking.receiver_collection = gc
    except Exception as e_:
        print("S3 light linking unavailable:", e_, flush=True)
    for o_ in steam:                                     # steam is WHITE: where it is thick it carries a little light of its own, so it never greys out against the wall
        nt_ = o_.material_slots[0].material.node_tree
        pv_ = next(n for n in nt_.nodes if n.type == 'PRINCIPLED_VOLUME')
        for nm in ("Emission Strength", "Emission Color"):
            for l_ in list(pv_.inputs[nm].links): nt_.links.remove(l_)
        mu_ = nt_.nodes.new("ShaderNodeMath"); mu_.operation = 'MULTIPLY'; mu_.inputs[1].default_value = 0.22
        nt_.links.new(pv_.inputs["Density"].links[0].from_socket, mu_.inputs[0]); nt_.links.new(mu_.outputs[0], pv_.inputs["Emission Strength"])
        pv_.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1)
    # ---- ROUND 7, A CLOSE SHOT (coordinator after board 6): the lens AHEAD of him, out over the front a little above
    # his head, a medium lens: the crust front grinding along the face fills the bottom of the frame, he is on the crest
    # right above it hosing it, his face to us, the steam boiling up either side, the town's roofs behind the crest
    CAM, LOOK = compose.frame_data(data, P0 + Vector(S3_CAMD), P0 + Vector(S3_LOOKD), S3_LENS,
                                   face_at=S3_FACE, height=0.34, t=T_SPRAY + 0.3)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=S3_LENS, fstop=11.0)
    print("S3 CAM", tuple(round(v, 2) for v in CAM), "fw", tuple(round(v, 2) for v in data.forward()), flush=True)
    def cam_at(t):                                          # it eases after the front as it slides off along the wall
        mv = Vector((0.07, 0.07, 0.0)) * W(t, T_HIT - 0.1, 1.2)
        return CAM + mv, LOOK + mv * 0.9, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, S3_LENS, S3_LENS)
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=("fire hose",), cutaway=None,
                boxes=[],
                conseq=[("the lava front rolls in, heaps against the wall's face and stops", lambda: [tongue, front], T_HIT - 0.2, DUR, {"whole": False}),
                        ("he blasts the front with the hose and a cloud of steam bursts up", lambda: steam, T_SPRAY + 0.1, DUR, {"whole": False, "moves": True})])
