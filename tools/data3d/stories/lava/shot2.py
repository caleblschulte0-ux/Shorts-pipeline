"""BEAT 2: "So Iceland built a wall of rock taller than a house to keep the lava out."

THE WALL RISES (coordinator, 2026-11-27, after the audit of every recorded verdict: the shots that passed have the
WORLD doing the action while Data reacts, one camera, two or three props). One lens, low on the town side: one painted
tin house at the left of the frame, its front to the wall; Data in the foreground at the right, three-quarter to us.
Behind the house a wall of black rock rises by itself, rock pouring down onto it from above the frame: level with the
ground (still 1), up to the house's knee (still 2), at its eaves (still 3), far over its roof ridge with an orange glow
held behind it (still 4). He watches it climb, his head tilting further up each still, and ends looking up at it."""

S2_CREST = 1.6                          # beat 3's crest (S3_CREST)
S2_SLOPE = 1.18                         # its faces
S2_H = 7.0                              # the finished wall: from this low lens its top stands well over the house's ridge
S2_HOUSE = (-2.45, 2.6, 1.6, 2.4)       # the house: centre x, y, width, depth; its front 1.4 m off the wall's foot (y 0)
S2_P0 = (-0.25, 5.55)                   # where he stands: in the foreground, right of the house


def s2_base(h):
    return 2.0 * (S2_CREST / 2 + 0.1 + 0.97 * h / S2_SLOPE)


def s2_ground_z(x, y):
    """the town's ground (y > 0); the black field beyond the wall"""
    if y > 0.0: return 0.04 + 0.05 * lw_fbm(x * 0.3, y * 0.3, 19)
    return 0.06 + 0.06 * lw_fbm(x * 0.3, y * 0.3, 19)


def place_wall_works():
    """THE WALL'S FOOT IN TOWN: moss ground and yard stones, one painted tin house with its front to the wall, the wall
    (risen by the shot), the black field beyond it."""
    lw_grid("lava field ground", -60, 60, -60, 0.6, 90, 70, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))
    lw_grid("town ground", -40, 40, 0.0, 30, 80, 40, s2_ground_z, lw_noise("town moss ground", "#4E5A34", "#8C9263", scale=0.9, rough=1.0, bump=0.5, detail=12))
    FX.ground("grass", area=(-10, 10, 1.6, 20), zfn=lambda x, y: s2_ground_z(x, y) + 0.03, seed=4, name="town grass")
    px, py = S2_P0
    lava_rock("town yard stones", 420, (-8, 8, 0.2, 12), lambda x, y: s2_ground_z(x, y) + 0.02, seed=78, r=(0.03, 0.1), moss=0.6,
              avoid=lambda x, y: (-3.4 < x < -1.5 and 1.2 < y < 3.9) or (abs(x - px) < 0.5 and abs(y - py) < 0.5))
    b = s2_base(S2_H)
    wall = earth_wall("earth wall", [(float(x), -b / 2) for x in range(-30, 31, 1)], h=S2_H, crest=S2_CREST, base=b, seed=8)
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=0.0, w=hw, d=hd, storeys=1, base=0.3, pitch=38, roof="#B8352B", wall="#E9D9A2", seed=5)
    def light():
        k = iceland_light(sun_elev=32, sun_az=156, sun=3.2, sky=0.45, haze=1.2)       # the sun behind the lens: on the wall's town face, on him
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(200))      # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall, house=house)


def shot2():
    """THE WALL RISES. See the module's head."""
    W = lw_win
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    TOPS = [-0.1, 0.55, 6.2, S2_H]                               # the wall's top at each: under the ground, the house's knee, over its ridge (seen from the lens), towering
    def top(t):
        if t <= TS[0]: return TOPS[0]
        for k in range(3):
            if t <= TS[k + 1]: return TOPS[k] + (TOPS[k + 1] - TOPS[k]) * W(t, TS[k], TS[k + 1] - TS[k])
        return TOPS[3]
    P = place_wall_works()
    light = P["light"]; wall = P["wall"]
    b = s2_base(S2_H); yc = -b / 2
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        wall["root"].location = (0, 0, top(t) - S2_H); wall["root"].keyframe_insert("location", frame=f)
    def face_z(x, y, t):
        return top(t) - S2_H + min(S2_H, max(0.0, (b / 2 - abs(y - yc)) * S2_SLOPE))
    # ---- the rock pouring down onto it from above the frame: blocks drop onto its crest and town face, and once down
    # they ride up with it
    rk = lw_random.Random(12)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    rocks = []
    for k in range(70):
        ts = rk.uniform(-0.2, DUR - 0.2)
        x = rk.uniform(-4.5, 3.0); yl = rk.uniform(-1.2, -0.1) - 0.85 * max(0.0, top(ts + 0.5)) / S2_SLOPE
        r = rk.uniform(0.08, 0.2)
        o = lw_block("falling rock", (x, yl, -9.0), r, rock_m, rk); rocks.append(o)
        z0 = face_z(x, yl, ts) + 3.5 + rk.uniform(0, 1.5); spin = rk.uniform(-6, 6); land = None
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            if t < ts: z = -9.0
            else:
                s = t - ts; z = z0 - 4.9 * s * s; zs = face_z(x, yl, t) + r * 0.5
                if land is None and z <= zs: land = t
                if land is not None: z = zs
            o.location = (x, yl, z); o.keyframe_insert("location", frame=f)
            o.rotation_euler = (spin * min(t - ts, (land or t) - ts) if t >= ts else 0.0, 0.3 * spin, 0.2 * spin); o.keyframe_insert("rotation_euler", frame=f)
    for k, t0 in enumerate(TS[1:3] + [TS[2] + 0.5]):
        FX.dust_puff(base=(-1.0 + 1.4 * (k - 1), -0.6 - 0.8 * k, max(0.2, TOPS[k + 1] * 0.6)), w=1.4, h=1.4 + 0.6 * k, t0=t0 - 0.4, dur=1.6,
                     col=(0.78, 0.74, 0.68), dens=4.0, seed=3.3 + k, name=f"dust off the falling rock {k}")
    # the lava's glow held behind it: lamps out past the crest, coming up as it rises, catching its top edge
    glows = [lw_point(f"lava glow behind the wall {k}", (-5.0 + 3.0 * k, -b - 2.0, S2_H + 0.5), 0.0, col=(1.0, 0.42, 0.1), r=1.5) for k in range(4)]
    for f in range(1, NF + 8, 2):
        t = (f - 1) / FPS
        for l_ in glows:
            l_.data.energy = 2.0e5 * W(t, TS[2] - 0.2, TS[3] - TS[2]); l_.data.keyframe_insert("energy", frame=f)
    # ---- him: in the foreground, three-quarter to the lens; he watches it climb, head going further up each still,
    # a step back as it passes the eaves
    data = load_data()
    CAM0 = Vector((-0.6, 7.0, 0.45)); LOOK0 = Vector((-1.2, 0.0, 1.6))
    X0, Y0 = S2_P0; Z0 = s2_ground_z(X0, Y0) + 0.02
    YAW = math.radians(-130)                                   # three-quarter to the lens, turned toward the house and the wall at its left
    data.place(X0, Y0, math.degrees(YAW))
    data.arm.location.z = Z0
    kit = hard_hat(data)
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        y_ = 0.12 * W(t, TS[2] - 0.3, 0.5) + 0.05 * W(t, TS[3] - 0.5, 0.4)            # a step back as it passes the eaves, another as it towers
        z_ = 0.03 * lw_kick(t - TS[2] + 0.1, 0.25)
        x_ = 0.03 * math.sin(2 * math.pi * t / 1.3)
        data._kobj(t, loc=(X0 + x_, Y0 + y_, Z0 + z_), rot=YAW + math.radians(10) * W(t, TS[1] - 0.3, 0.6) - math.radians(8) * W(t, TS[3] - 0.6, 0.5))
        data._plant_feet_here(t, lift=(Z0, Z0))
    lw_layer(data, "spine", lambda t: (-6 * W(t, TS[1], 0.6) - 10 * W(t, TS[2] - 0.2, 0.6) - 8 * W(t, TS[3] - 0.5, 0.5) + 10 * lw_kick(t - TS[2] + 0.1, 0.3), 0, 0), 0, DUR + 0.4)
    HEAD = Vector((X0, Y0, Z0 + 0.5))
    UPAT = lambda up: HEAD + Vector((-1.1, 0.35, up))                  # round toward the house and the wall over it, further up each still
    data.look_at(CAM0 + Vector((0, 0, 0.1)), 0.0, max_yaw=55, max_pitch=20, blend=0.0)          # at us, as it starts
    data.look_at(UPAT(0.15), TS[0] + 0.25, max_yaw=35, max_pitch=50, blend=0.35)                # round at the rock coming down
    data.look_at(UPAT(0.55), TS[1] + 0.2, max_yaw=35, max_pitch=50, blend=0.5)
    data.look_at(UPAT(1.4), TS[2] + 0.2, max_yaw=35, max_pitch=50, blend=0.5)                   # right up at it
    data.expression("surprised", 0.0, TS[2], blend=0.15)
    data.expression("alarmed", TS[2], DUR + 1.0, blend=0.25)
    sides = sorted("LR", key=lambda s_: -acts._shoulder(data, s_).x)
    LOW = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = (LOW, LOW, WHOA, WHOA, WHOA) if sd == sides[0] else (LOW, LOW, LOW, WHOA, WHOA)
        for tk, pose in zip((0.0, TS[1], TS[2] - 0.2, TS[3] - 0.4, DUR + 0.5), seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    data.finish()
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 28.0, face_at=(0.66, 0.66), height=0.36, t=TS[1])
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=28.0, fstop=11.0)
    print("S2 CAM", tuple(round(v, 2) for v in CAM), "look", tuple(round(v, 2) for v in LOOK), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    def cam_at(t):
        drift = Vector((0.0, -0.12, 0.05)) * (t / DUR)                # a slow push in as it rises
        tilt = Vector((0, 0, 0.9)) * W(t, TS[1], TS[3] - TS[1])          # tipping up with it
        return CAM + drift, LOOK + drift + tilt, data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 28.0, 28.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a wall of black rock rises behind the house, rock pouring down onto it", lambda: [wall["body"]], TS[0], TS[2], {"whole": False}),
                        ("it stands far over the house's roof, an orange glow held behind it", lambda: [wall["body"]], TS[2], DUR, {"whole": False})])
