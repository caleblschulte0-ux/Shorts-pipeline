"""BEAT 2: "So Iceland built a wall of rock taller than a house."

THE WALL RISES (coordinator, 2026-11-27: after the audit of every recorded verdict the shots that passed have the WORLD
doing the action while Data reacts, one camera, two or three props; then r2e's and r2i's pre-flights; the purpose
clause "to keep the lava out" is line 3's picture now). One LOCKED lens, low on the town side: one painted tin house
whole at the right of the frame, its back to the wall; Data planted in the foreground at the left, clear of it. Behind
the house a long bank of black boulders grows still by still, one grade throughout, and its BUILDER rides up with it: a
digger on its crest placing a boulder, its arm somewhere new each still. Knee-high (still 1, the digger at ground level
beside the low row), window-high (2), at the eaves (3), far over the ridge and chimney with sky above it (4). Data: hands
on hips facing us; a thumb jerked back at the wall, grinning; half-turned, looking up; leaning right back, arms dropped,
mouth open. No fire and no lava in this shot."""

S2_CREST = 1.6                          # beat 3's crest (S3_CREST)
S2_SLOPE = 2.5                          # (w2b: a shallow face put its top 6 m back, barely over the ridge) a steep face of piled boulders
S2_H = 7.0                              # the finished wall: from this low lens its top stands well over the house's ridge
S2_HOUSE = (-2.8, 2.4, 1.6, 2.4)       # the house: centre x, y, width, depth; its front 1.4 m off the wall's foot (y 0)
S2_P0 = (-0.1, 5.55)
S2_DIG = (-4.9, -0.3)                  # the digger on the crest: x, and y off the crest's middle (toward the far side)                   # where he stands: in the foreground, right of the house


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
    lava_rock("near yard stones", 360, (-3.5, 2.5, 3.6, 6.6), lambda x, y: s2_ground_z(x, y) + 0.015, seed=91, r=(0.012, 0.045), moss=0.5,   # (r2g EMPTY 22-24%: the foreground read as one smooth plane)
              avoid=lambda x, y: (-3.4 < x < -1.5 and 1.2 < y < 3.9) or (abs(x - px) < 0.4 and abs(y - py) < 0.4))
    b = s2_base(S2_H)
    wall = earth_wall("earth wall", [(float(x), -b / 2) for x in range(-30, 31, 1)], h=S2_H, crest=S2_CREST, base=b, seed=8)
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=0.0, w=hw, d=hd, storeys=1, base=0.3, pitch=38, roof="#B8352B", wall="#E9D9A2", seed=5)
    def light():
        k = iceland_light(sun_elev=24, sun_az=118, sun=3.2, sky=0.45, haze=1.2)       # (coordinator, r2e: lit so the boulders read) the sun raking across the wall's town face from the right
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(250))      # a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall, house=house)


def shot2():
    """THE WALL RISES. See the module's head. (coordinator, after r2e's pre-flight: a LOCKED lens, one grade, nothing
    in the sky but the wall growing still by still and, behind its crest, the lava's glow and smoke held out; Data
    planted in one spot in four distinct poses.)"""
    W = lw_win
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    TOPS = [2.4, 3.5, 4.6, 6.2]                               # (p2a-p2e: it stands 3 m further back than the house, so it reads at half its height) the wall's top at each: a knee-high boulder row, window-high, at the eaves, far over the ridge and chimney
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
    # ---- its builder: one digger on the crest, riding up with it, placing a boulder on the town face, its arm somewhere
    # new each still. The kit's digger is posed when it is built, so each pose is its own digger, shown for its moment.
    rnd = lw_random.Random(12)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    POSES = [(-25, 16, -70, -60, True), (-5, 30, -95, -20, True), (15, 40, -110, 10, True), (25, 22, -80, 50, False),
             (5, 10, -60, 20, False), (-15, 26, -90, -40, True)]
    DX, DY = S2_DIG
    diggers = []
    for k, (slew, boom, stick, bucket, loaded) in enumerate(POSES):
        before = set(bpy.data.objects)
        d = FX.digger(name=f"digger {k}", loc=(0, 0, 0), yaw=0.0, slew=0.0, boom=boom, stick=stick, bucket=bucket, lights=False, seed=3)
        d["house"].rotation_euler[2] = math.radians(slew)
        d["root"].rotation_euler[2] = math.pi                    # its arm out over the town face, toward us
        bpy.context.view_layer.update()
        if loaded:
            tip = d["bucket"].matrix_world.translation
            bo = lw_block(f"digger {k} boulder", (tip.x, tip.y, tip.z + 0.1), 0.15, rock_m, rnd, squash=0.8); bo.parent = d["house"]
            bo.matrix_parent_inverse = d["house"].matrix_world.inverted()
        objs = [o for o in bpy.data.objects if o not in before]
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            d["root"].location = (DX, yc + DY, top(t)); d["root"].keyframe_insert("location", frame=f)
        diggers.append(objs)
    order = [0, 1, 2, 3, 4, 5]
    STEP = DUR / 9.0                                             # a working swing: each still lands mid-pose, on a different one
    pose_at = lambda t: order[int(max(0.0, t) / STEP) % len(order)]
    print("S2 digger poses at the stills", [pose_at(t) for t in TS], flush=True)
    for k, objs in enumerate(diggers):
        prev = None
        for f in range(1, NF + 8):
            t = (f - 1) / FPS; hid = pose_at(t) != k
            if hid != prev:
                for o in objs:
                    o.hide_render = hid; o.hide_viewport = hid
                    o.keyframe_insert("hide_render", frame=f); o.keyframe_insert("hide_viewport", frame=f)
                prev = hid
    # ---- him: planted in one spot in the foreground, in four poses
    data = load_data()
    CAM0 = Vector((0.225, 6.76, 0.45)); LOOK0 = CAM0 + Vector((-0.52, -0.85, 0.04)) * 5.0      # (r2f/r2g EMPTY 22-24%: the high sky has no cloud: nearer, nearly level)      # (r2e: the house cut by the frame's edge) locked off, the whole house and sky over it
    X0, Y0 = S2_P0; Z0 = s2_ground_z(X0, Y0) + 0.02
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    LENS = math.degrees(yaw_of(CAM0.x - X0, CAM0.y - Y0))
    data.place(X0, Y0, LENS)                                    # 1 facing us
    data.arm.location.z = Z0
    kit = hard_hat(data)
    T1, T2, T3 = 0.2 * DUR, 0.5 * DUR, 0.8 * DUR             # the turns between the poses (line 2 is a short line now)
    data.turn_to(LENS - 25, T1, T1 + 0.3)                      # 2 a quarter round toward the wall at his back
    data.turn_to(LENS - 50, T2, T2 + 0.3)                      # 3 half-turned to it
    data.turn_to(LENS - 35, T3, T3 + 0.3)                      # 4 back toward us a little, leaning back
    sc.frame_set(1); bpy.context.view_layer.update()
    M = data.arm.matrix_world
    def pts(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); M = data.arm.matrix_world
        fw = data.forward(); rt = Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))
        return M, fw, rt
    # 1 hands on hips, facing us
    M_, fw, rt = pts(0.0)
    for s_, sg in (("L", -1), ("R", 1)):
        hp = M_ @ data.J[s_]["hip"]
        for tt in (0.0, T1 - 0.05):
            data._arm_ik(s_, hp + rt * sg * 0.07 + fw * 0.02 + Vector((0, 0, 0.05)), tt, 1.4); data._k(f"hand.{s_}", tt, rot=(0, 0, sg * 20))
    # 2 a thumb jerked back over his shoulder at the wall, a grin; the other hand still on his hip
    M_, fw, rt = pts(T1 + 0.3)
    sh = M_ @ data.J["R"]["sh"]; hpL = M_ @ data.J["L"]["hip"]
    for tt in (T1 + 0.3, T2 - 0.05):
        data._arm_ik("R", sh + rt * 0.2 + fw * 0.03 + Vector((0, 0, 0.0)), tt, 1.0); data._k("hand.R", tt, rot=(-20, 0, 25))      # (r2f: over the shoulder put the arm behind his back, the hand in his head) out to the side, jerked back
        data._arm_ik("L", hpL - rt * 0.07 + fw * 0.02 + Vector((0, 0, 0.05)), tt, 1.4); data._k("hand.L", tt, rot=(0, 0, -20))
    # 3 half-turned, looking up at it, his arms down (r2i: a hand at his head read as broken)
    for tt in (T2 + 0.3, T3 - 0.05):
        for bn in data.RELAXED: data._k(bn, tt, rot=data.RELAXED[bn])
    # 4 leaning right back looking up, both arms dropped, mouth open
    for tt in (T3 + 0.3, DUR + 0.5):
        for bn in data.RELAXED: data._k(bn, tt, rot=(data.RELAXED[bn][0] + (6 if bn.startswith("arm") else 0),) + tuple(data.RELAXED[bn][1:]))
    lw_layer(data, "spine", lambda t: (-4 * W(t, T2, 0.35) - 24 * W(t, T3, 0.35), 0, 0), 0, DUR + 0.4)
    lw_layer(data, "chest", lambda t: (-14 * W(t, T3, 0.35), 0, 0), 0, DUR + 0.4)
    HEAD = Vector((X0, Y0, Z0 + 0.5))
    data.look_at(CAM0 + Vector((0, 0, 0.1)), 0.0, max_yaw=55, max_pitch=20, blend=0.0)            # 1 at us
    data.look_at(CAM0 + Vector((0, 0, 0.1)), T1 + 0.3, max_yaw=55, max_pitch=20, blend=0.2)       # 2 at us, the grin
    data.look_at(HEAD + Vector((0.3, 0.2, 2.0)), T2 + 0.3, max_yaw=30, max_pitch=40, blend=0.3)   # 3 up at it
    data.look_at(HEAD + Vector((0.2, 0.4, 3.0)), T3 + 0.3, max_yaw=30, max_pitch=45, blend=0.3)   # 4 right up at it
    data.expression("determined", 0.0, T1 + 0.1, blend=0.15)
    data.expression("happy", T1 + 0.1, T2 + 0.1, blend=0.15)
    data.expression("surprised", T2 + 0.1, T3 + 0.1, blend=0.15)
    data.expression("alarmed", T3 + 0.1, DUR + 1.0, blend=0.15)
    data.finish()
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=24.0, fstop=11.0)
    print("S2 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    still = lambda t: (CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5)))
    lw_cut(cam, still, still, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a digger piles a wall of black rock behind the house, from its knee to far over its roof", lambda: [wall["body"]], TS[0], TS[3], {"whole": False})])
