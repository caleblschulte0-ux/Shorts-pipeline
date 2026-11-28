"""BEAT 3: "So when the lava came, it hit the wall and turned away from the town."

IN FRONT OF THE WALL, on the lava side. A wide lens low on the black field looking at the wall: its boulder face
towers across the frame behind him to its crest and the sky. A river of lava comes past him across the field, slams
into the foot of the face and heaps up; it stops dead against the rock, its crust going dark; he throws his arms up
and grins at us. The WALL stops it: no hose."""

S3_H = 4.4                     # the wall (as built in the works beat)
S3_CREST = 1.6
S3_BASE = 8.6
S3_FOOT = -S3_BASE / 2         # the outer face's foot (y); the lava field is y < this
S3_P0 = (-0.65, S3_FOOT - 2.6)  # where he stands: on the field at the wall's foot
S3_NOSE = (0.95, S3_FOOT + 0.55) # where the river's front meets the face
S3_SRC = (4.0, -44.0)         # where it comes from: the fissure on the ridge
S3_WIDE = 0.95                 # the river's half width at its front


def s3_face_z(y):
    """the outer face's height at y (between the foot and the crest's outer edge)"""
    y0, y1 = -S3_BASE / 2, -S3_CREST / 2 - 0.1
    return S3_H * 0.97 * max(0.0, min(1.0, (y - y0) / (y1 - y0)))


def s3_ground_z(x, y):
    """the black lava field outside the wall; inside, the town's ground"""
    if y > 0.5: return 0.08 * lw_fbm(x * 0.3, y * 0.3, 19) - 1.0 * ease(max(0.0, min(1.0, (y - 4.2) / 1.6)))
    return 0.2 + 0.07 * lw_fbm(x * 0.3, y * 0.3, 19)


def s3_river_d(x, y):
    """how far (x, y) is from the lava river's centre line (the ridge to the wall's foot)"""
    ax, ay = S3_NOSE; bx, by = S3_SRC
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    u = max(-0.1, min(1.3, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - ax - u * dx, y - ay - u * dy)


def s3_river(x, y, pad=0.0):
    return s3_river_d(x, y) < S3_WIDE + 0.5 + pad


def place_wall_crest():
    """THE LAVA SIDE OF THE WALL: the black field, the wall's boulder face along it, the
    river's road in across it."""
    lw_grid("lava field ground", -30, 30, -50, 30, 90, 110, s3_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven)
    wall = earth_wall("earth wall", [(x, 0.0) for x in range(-24, 26, 2)], h=S3_H, crest=S3_CREST, base=S3_BASE, seed=8)
    off = lambda x, y: s3_river(x, y) or (abs(x - S3_P0[0]) < 0.45 and abs(y - S3_P0[1]) < 0.4)
    lava_rock("lava field rock", 140, (-12, 12, -30, S3_FOOT - 0.3), s3_ground_z, seed=9, r=(0.1, 0.35), moss=0.0, avoid=off)
    lava_rock("field block", 420, (-8, 8, -14, S3_FOOT - 0.1), s3_ground_z, seed=19, r=(0.05, 0.22), moss=0.0, avoid=off)   # the field outside the wall: broken black blocks
    lava_rock("wall face rock", 420, (-9, 10, S3_FOOT + 0.1, -1.0), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=27, r=(0.08, 0.26), moss=0.0,
              avoid=None)       # the black rock it is built of, on its face
    lava_rock("wall foot rubble", 160, (-7, 9, S3_FOOT - 0.5, S3_FOOT + 0.3), lambda x, y: max(s3_ground_z(x, y), s3_face_z(y)), seed=29, r=(0.06, 0.2), moss=0.0, avoid=off)
    def light():
        k = iceland_light(sun_elev=30, sun_az=-140, sun=3.0, sky=0.4, haze=1.4)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))     # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall)


def shot3():
    """THE WALL HOLDS. See the module's head."""
    T_HIT = 0.3 * DUR; T_STOP = 0.52 * DUR; T_DARK = 0.66 * DUR; T_SLAP = 0.84 * DUR
    W = lw_win
    P = place_wall_crest()
    light = P["light"]
    data = load_data()
    YAW = math.radians(12)                                   # three-quarter to the lens, which is on the field at his front left
    X0, Y0 = S3_P0; Z0 = s3_ground_z(X0, Y0) + 0.02
    data.place(X0, Y0, math.degrees(YAW))
    data.arm.location.z = Z0
    kit = hard_hat(data)
    # ---- the river: a long band of lava from the ridge, its front as wide as a street, sliding in along its own line
    ax, ay = S3_NOSE; bx, by = S3_SRC
    L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; nx, ny = -uy, ux
    out = []
    NS = 46
    for k in range(NS + 1):                                # up one bank, round the front, down the other (counter-clockwise)
        d = L * (k / NS) ** 1.6; wd = S3_WIDE * (1.0 + 0.03 * d) * (1 + 0.14 * math.sin(d * 0.9 + 1.0) + 0.09 * math.sin(d * 2.3))
        out.append((ax + ux * d + nx * wd, ay + uy * d + ny * wd))
    for k in range(NS, -1, -1):
        d = L * (k / NS) ** 1.6; wd = S3_WIDE * (1.0 + 0.03 * d) * (1 + 0.14 * math.sin(d * 1.1) + 0.09 * math.sin(d * 2.9 + 2.0))
        out.append((ax + ux * d - nx * wd, ay + uy * d - ny * wd))
    for k in range(1, 8):                                  # the front itself: a blunt lobed nose
        a = math.pi * k / 8
        out.append((ax - nx * S3_WIDE * math.cos(a) - ux * 1.1 * math.sin(a) * (1 + 0.15 * math.sin(5 * a)), ay - ny * S3_WIDE * math.cos(a) - uy * 1.1 * math.sin(a) * (1 + 0.15 * math.sin(5 * a))))
    sgn = sum(out[i][0] * out[(i + 1) % len(out)][1] - out[(i + 1) % len(out)][0] * out[i][1] for i in range(len(out)))
    if sgn < 0: out.reverse()
    lm = lava_mat("lava river", heat=2.2, scale=6.0, fresh=0.3)
    river = lava("lava river", out, z=0.0, thick=0.34, m=lm, seed=7, lumpy=0.2)
    home = Vector(river.location); RUN = 5.5                # how far out the front is at the start
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = min(1.0, max(0.0, (t + 0.5) / (T_HIT + 0.5))); back = RUN * (1 - u) ** 1.1      # it comes fast and SLAMS: no easing into the face
        heap = W(t, T_HIT - 0.05, 0.45)
        river.location = (home.x + ux * back, home.y + uy * back, 0.16 + 0.05 * heap); river.scale = (1, 1, 1.0 + 0.45 * heap)
        river.keyframe_insert("location", frame=f); river.keyframe_insert("scale", frame=f)
    lava_flow_key(lm, 0.0, DUR + 0.5, 0.25, axis=1)
    # broken crust plates heap and tip up against the face along the whole front as it hits
    cm_ = lava_mat("lava crust block", heat=1.4, scale=1.6, fresh=0.0); rb = lw_random.Random(23); fb = []
    for k in range(70):
        along = rb.uniform(-1.0, 1.0); o_ = lw_block("front crust", (0, 0, -6), rb.uniform(0.09, 0.24), cm_, rb, squash=0.55)
        fb.append((o_, along, rb.uniform(-0.5, 0.35), rb.uniform(-0.4, 0.4), rb.uniform(0, 6.3), rb.uniform(0.0, 0.3)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        for o_, along, dy_, tilt, spin, lag in fb:
            on = t >= T_HIT - 0.05 + lag * 0.5; buck = W(t, T_HIT + lag, 0.5)
            x_ = ax + 0.9 * along; y_ = S3_FOOT + 0.25 + dy_ * (1 - 0.5 * buck) + 0.3 * buck
            o_.location = (x_, y_, (s3_face_z(y_) + 0.3 + 0.45 * buck * (1 - 0.4 * along * along)) if on else -6.0)
            o_.rotation_euler = (tilt + 1.0 * buck, 0.5 * buck * along, spin)
            o_.keyframe_insert("location", frame=f); o_.keyframe_insert("rotation_euler", frame=f)
    heat = lm.node_tree.nodes["lava heat"].inputs[1]; heat_c = cm_.node_tree.nodes["lava heat"].inputs[1]
    for f in range(1, NF + 1, 2):                           # stopped, it crusts over: its seams go dark
        t = (f - 1) / FPS; cool = 1 - 0.93 * W(t, T_STOP, T_DARK + 0.5 - T_STOP)
        heat.default_value = 2.4 * (1 + 0.6 * lw_kick(t - T_HIT, 0.35)) * cool; heat.keyframe_insert("default_value", frame=f)
        heat_c.default_value = 1.5 * cool; heat_c.keyframe_insert("default_value", frame=f)
    # the heat is LOCAL light: lamps low along the front, on the rock face and on him, never on the lava's own crust
    glows = [(lw_point(f"lava front glow {k_}", (ax - 0.9 + 0.36 * k_, S3_FOOT - 0.35, 0.8), 0.0, col=(1.0, 0.42, 0.1), r=0.25), 26.0) for k_ in range(6)]
    steam = lw_steam("front steam", (ax, S3_FOOT + 0.3, 0.7), w=0.8, h=1.8, seed=8.5, col=(0.96, 0.96, 0.96), dens=4.0, lean=(0.3, 0.1), rise=1.6,
                     keys=[(T_HIT - 0.1, 0.0), (T_HIT + 0.35, 1.0), (T_DARK, 0.7), (DUR + 1.0, 0.35)], t_end=DUR + 1.0)    # steam comes free off the front where it hit wet rock
    try:
        gc = bpy.data.collections.new("glow receivers"); bpy.context.scene.collection.children.link(gc)
        for o_ in [river] + [b[0] for b in fb] + ([steam] if hasattr(steam, "name") else []): gc.objects.link(o_)
        for co_ in gc.collection_objects: co_.light_linking.link_state = 'EXCLUDE'
        for l_, _e in glows: l_.light_linking.receiver_collection = gc
    except Exception as e_:
        print("S3 light linking unavailable:", e_, flush=True)
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS
        for l_, e_ in glows:
            l_.data.energy = e_ * W(t, T_HIT - 0.25, 0.4) * (1 - 0.93 * W(t, T_STOP, T_DARK + 0.5 - T_STOP)); l_.data.keyframe_insert("energy", frame=f)
    # ---- him: braced at the foot watching it come, a flinch as it slams in, a look, then both arms up
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        z_ = -0.07 * W(t, 0.1, 0.4) * (1 - W(t, T_STOP, 0.4)) + 0.05 * lw_kick(t - T_HIT, 0.2) + 0.04 * lw_kick(t - T_SLAP, 0.25)   # knees bent, braced; a jolt at the hit
        y_ = -0.07 * W(t, T_HIT - 0.05, 0.25) - 0.04 * W(t, T_SLAP - 0.5, 0.45)                    # a step back against the wall at the hit, another to lean on it
        x_ = -0.05 * W(t, T_HIT, 0.3) + 0.2 * W(t, T_SLAP - 0.5, 0.45) + 0.04 * math.sin(2 * math.pi * t / 1.1) * (1 - W(t, T_HIT - 0.2, 0.3))
        data._kobj(t, loc=(X0 + x_, Y0 + y_, Z0 + z_), rot=YAW + math.radians(26) * W(t, T_HIT - 0.45, 0.4) - math.radians(22) * W(t, T_STOP + 0.1, 0.5))
        data._plant_feet_here(t, lift=(Z0, Z0))
    lw_layer(data, "spine", lambda t: (10 * W(t, 0.1, 0.4) * (1 - W(t, T_HIT - 0.1, 0.2)) - 18 * lw_kick(t - T_HIT, 0.3) - 8 * W(t, T_SLAP - 0.2, 0.4), 0, 0), 0, DUR + 0.4)
    CAM0 = Vector((-0.8, S3_FOOT - 4.3, Z0 + 0.85)); LOOK0 = CAM0 + Vector((0.25, 0.97, 0.08))
    FRONT = Vector((ax, S3_FOOT, 0.9))
    data.look_at(Vector((X0 + 0.9, Y0 - 0.6, 0.3)), 0.0, max_yaw=18, max_pitch=16, blend=0.0)       # at it coming across the field
    data.look_at(FRONT, T_HIT - 0.1, max_yaw=20, max_pitch=14, blend=0.2)
    data.look_at(CAM0, T_STOP + 0.2, max_yaw=55, max_pitch=40, blend=0.3)
    data.expression("alarmed", 0.0, T_SLAP - 0.3, blend=0.12)
    data.expression("pleased", T_SLAP - 0.25, DUR + 1.0, blend=0.25)
    sides = sorted("LR", key=lambda s_: -acts._shoulder(data, s_).x)          # sides[0] is the arm toward the lava, sides[1] toward the wall
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    UP = lambda sg: ((-58, 0, -sg * 12), (-48, 0, -sg * 22), (-10, sg * -12, -sg * 15))
    LOW = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = (WHOA, LOW, UP, WHOA, WHOA, UP, UP) if sd == sides[0] else (LOW, WHOA, UP, WHOA, LOW, UP, UP)
        for tk, pose in zip((0.0, 0.5 * T_HIT, T_HIT + 0.05, T_HIT + 0.5, T_DARK, T_SLAP, DUR + 0.5), seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    data.finish()
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(0.33, 0.47), height=0.35, t=T_HIT)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24.0, fstop=11.0)
    print("S3 CAM", tuple(round(v, 2) for v in CAM), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    def cam_at(t):
        shake = Vector((0.02 * math.sin(2 * math.pi * 13 * t), 0, 0.015 * math.sin(2 * math.pi * 17 * t))) * lw_kick(t - T_HIT, 0.3) * 2
        return CAM + shake, LOOK + shake, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_crest", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("the lava river comes across the field and slams into the wall's face, heaping up", lambda: [river] + [b[0] for b in fb], T_HIT - 0.3, T_STOP, {"whole": False}),
                        ("it stops dead against the rock and its crust goes dark", lambda: [river], T_STOP, DUR, {"whole": False})])
