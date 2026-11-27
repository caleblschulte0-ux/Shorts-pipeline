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

S2_CREST = 3.0 # (coordinator, after board 46083546367: a flat bench of rock at the crest for the digger to sit on)                          # beat 3's crest (S3_CREST)
S2_SLOPE = 3.0 # (same: a sloped, rubbly bank, not a vertical slab) # (r2zf pre-flight: "the wall only a little above the roof": a steeper face brings its crest nearer the lens)                          # (w2b: a shallow face put its top 6 m back, barely over the ridge) a steep face of piled boulders
S2_H = 8.0                              # the finished wall: from this low lens its top stands well over the house's ridge
S2_HOUSE = (-1.05, 0.75, 1.2, 0.95) # (coordinator, r2zh: a CENTRE GAP for the digger: the house takes the right ~35%, its gable end to us)         # (coordinator, r2y: composition) the house: centre x, y, width, depth; the right half of the frame, just clear of the wall's foot (y 0)
S2_P0 = (0.3, 4.6)                     # Data: the left foreground, his feet near the bottom edge
S2_DIG = (0.05, 0.0)                    # the digger on the crest: x (just left of the house, never behind it), and y off the crest's middle


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
    lw_grid("town ground", -40, 40, 0.0, 30, 80, 40, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))     # (coordinator, after board 46083546367: the dark volcanic ground of shots 4-5, not a lawn)
    lw_steam("eruption smoke", (7.0, -26.0, 1.0), w=7.0, h=30.0, seed=3.3, col=(0.42, 0.41, 0.42), dens=2.5, lean=(0.2, 0.5), rise=1.2, t_end=DUR + 1.0)     # (same: the eruption's dark smoke beyond the wall at the left, shot 4's own column, in every still: the reason the wall is built)
    px, py = S2_P0
    lava_rock("town yard stones", 420, (-8, 8, 0.2, 12), lambda x, y: s2_ground_z(x, y) + 0.02, seed=78, r=(0.03, 0.1), moss=0.6,
              avoid=lambda x, y: (-1.55 < x < 0.15 and 0.0 < y < 2.1) or (abs(x - px) < 0.5 and abs(y - py) < 0.5))
    lava_rock("near yard stones", 360, (-3.5, 2.5, 3.6, 6.6), lambda x, y: s2_ground_z(x, y) + 0.015, seed=91, r=(0.012, 0.045), moss=0.5,   # (r2g EMPTY 22-24%: the foreground read as one smooth plane)
              avoid=lambda x, y: (-1.55 < x < 0.15 and 0.0 < y < 2.1) or (abs(x - px) < 0.4 and abs(y - py) < 0.4))
    b = s2_base(S2_H)
    wall = earth_wall("earth wall", [(float(x), -b / 2) for x in range(-30, 31, 1)], h=S2_H, crest=S2_CREST, base=b, seed=8)
    for m_ in [bpy.data.materials.get("wall heaped rock")]:      # (r2zd pre-flight: "the wall a flat dark slab"; coordinator: lighter rock, sunlit) this shot's wall only: a grey basalt, not a black block
        if m_ and m_.use_nodes:
            for n_ in m_.node_tree.nodes:
                if n_.bl_idname == "ShaderNodeMix" and n_.blend_type == 'MULTIPLY': n_.inputs[7].default_value = (*K.lin("#8E877E"), 1)
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=math.pi / 2, w=hw, d=hd, storeys=1, base=0.3, pitch=50, roof="#B8352B", wall="#E9D9A2", seed=5)
    def light():
        k = iceland_light(sun_elev=30, sun_az=160, sun=3.2, sky=0.45, haze=1.2)       # (coordinator, r2e: lit so the boulders read) the sun raking across the wall's town face from the right
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(185))      # (r2za EMPTY 48%: turned so its clouds stand over the house) a REAL sky with cloud in it (Poly Haven)
        return k
    return dict(light=light, wall=wall, house=house)


def shot2():
    """THE WALL RISES. See the module's head. (coordinator, after r2e's pre-flight: a LOCKED lens, one grade, nothing
    in the sky but the wall growing still by still and, behind its crest, the lava's glow and smoke held out; Data
    planted in one spot in four distinct poses.)"""
    W = lw_win
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    TOPS = [1.2, 2.9, 4.1, 5.4]  # (coordinator, r2zg: still 4's crest and digger with clear sky above)                             # (coordinator, r2y: measured against the house from the lens) the crest at the windows' sill, their top, the eaves, then twice the house
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
    dig_x = lambda t: S2_DIG[0]
    dig_z = lambda t: top(t)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    POSES = [(-10, 55, -75, -40, True), (-5, 30, -95, -20, True), (15, 40, -110, 10, True), (25, 10, -100, 50, True),
             (-20, -8, -105, 30, True), (-15, 2, -100, -20, True)]     # (coordinator, r2y: a boulder in its bucket every still) (p2t: in still 1 it works in the gap between him and the house, then drives along the crest to the left)
    DX, DY = S2_DIG
    diggers = []
    for k, (slew, boom, stick, bucket, loaded) in enumerate(POSES):
        before = set(bpy.data.objects)
        d = FX.digger(name=f"digger {k}", loc=(0, 0, 0), yaw=0.0, slew=0.0, boom=boom, stick=stick, bucket=bucket, lights=False, seed=3)
        d["house"].rotation_euler[2] = math.radians(slew)
        d["root"].rotation_euler[2] = math.pi + 0.7              # its arm out over the town face, three-quarter to us
        d["root"].scale = (1.45, 1.45, 1.45)                      # (coordinator, r2y: real scale: as long as the house is wide, its arm up to the ridge)
        bpy.context.view_layer.update()
        if loaded:
            tip = d["bucket"].matrix_world.translation
            bo = lw_block(f"digger {k} boulder", (tip.x, tip.y, tip.z + 0.1), 0.15, rock_m, rnd, squash=0.8); bo.parent = d["house"]
            bo.matrix_parent_inverse = d["house"].matrix_world.inverted()
        objs = [o for o in bpy.data.objects if o not in before]
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            d["root"].location = (dig_x(t), yc + DY, dig_z(t)); d["root"].keyframe_insert("location", frame=f)
        diggers.append(objs)
    order = [0, 4, 1, 3, 2, 5]                                 # (r2x pre-flight: on still 4 its raised arm was cut by the top edge: the low swing lands there)
    STEP = DUR / 8.0                                             # a working swing: each still lands mid-pose, on a different one
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
    CAM0 = Vector((0.0, 6.0, 0.55)); LOOK0 = CAM0 + Vector((0.0, -1.0, 0.285)) * 5.0      # (coordinator, r2y: LOW, tilted up, close: the ground line in the bottom fifth, the house the right half up to mid-frame, the sky over it where the wall rises)
    X0, Y0 = S2_P0; Z0 = s2_ground_z(X0, Y0) + 0.02
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    LENS = math.degrees(yaw_of(CAM0.x - X0, CAM0.y - Y0))
    data.place(X0, Y0, LENS)                                    # 1 facing us
    data.arm.location.z = Z0
    kit = hard_hat(data)
    T1, T2, T3 = 0.17 * DUR, 0.45 * DUR, 0.8 * DUR             # the turns between the poses (line 2 is a short line now)
    TO = Vector((CAM0.x - X0, CAM0.y - Y0, 0)).normalized()
    for f in range(1, NF + 8):                                 # (r2q HOLD/READ/FAR: planted, but a step back from the wall as it climbs, then another)
        t = (f - 1) / FPS
        SD = Vector((-TO.y, TO.x, 0))
        p = (Vector((X0, Y0, Z0)) + TO * (0.08 * W(t, T2 + 0.3, 0.45) + 0.08 * W(t, T3 - 0.1, 0.45))     # (coordinator, r2y: two real steps back)
             + SD * (0.06 * W(t, 0.15, 0.35) - 0.06 * W(t, 1.25, 0.35) + 0.1 * W(t, T2 + 0.75, 0.4)))     # (r2r READ: a weight shift in each pose)
        yaw = LENS + 35 + 10 * W(t, T1, 0.35) - 5 * W(t, T2, 0.45) - 15 * W(t, T3, 0.35)     # (p2q: the house and wall are at his left now: he turns that way)     # 2 a quarter round; 3 half-turned to it; 4 back toward us a little, leaning back
        data._kobj(t, loc=tuple(p), rot=math.radians(yaw))
        data._plant_feet_here(t, lift=(Z0, Z0))
    sc.frame_set(1); bpy.context.view_layer.update()
    M = data.arm.matrix_world
    def pts(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); M = data.arm.matrix_world
        fw = data.forward(); rt = Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))
        return M, fw, rt
    # (coordinator, after board 46083546367: "he does nothing". He is the digger crew: the BANKSMAN guiding it, body
    # three-quarter toward it, a big and different arm signal each still, nothing in his hands.)
    UP = Vector((0, 0, 1))
    def sig(tt, fn):
        M_, fw, rt = pts(tt)
        for s_, sg in (("L", -1), ("R", 1)):
            tgt = fn(s_, sg, M_ @ data.J[s_]["sh"], M_ @ data.J[s_]["hip"], fw, rt)
            if tgt is None:
                for bn in (f"arm.{s_}", f"fore.{s_}", f"hand.{s_}"): data._k(bn, tt, rot=data.RELAXED[bn])
            else:
                data._arm_ik(s_, tgt[0], tt, tgt[1]); data._k(f"hand.{s_}", tt, rot=tgt[2])
    hip_hand = lambda sg, hp, fw, rt: (hp + rt * sg * 0.07 + fw * 0.02 + UP * 0.05, 1.4, (0, 0, sg * 20))
    # 1 beckoning it up: his right arm up and forward, the hand waving it on; the left on his hip
    for k, tt in enumerate((0.0, 0.3, 0.6)):
        hi = 0.17 if k % 2 == 0 else 0.09
        sig(tt, lambda s_, sg, sh, hp, fw, rt, hi=hi: (sh + fw * (0.08 if hi > 0.1 else 0.14) + UP * hi + rt * 0.05, 0.6, (-40 if hi > 0.1 else 20, 0, 10)) if sg > 0 else hip_hand(sg, hp, fw, rt))
    # 2 both arms up over his head, waving it higher
    for k, tt in enumerate((T1 + 0.4, T1 + 0.7, T1 + 1.0, T2 - 0.05)):
        w_ = 0.05 if k % 2 == 0 else -0.04
        sig(tt, lambda s_, sg, sh, hp, fw, rt, w_=w_: (sh + UP * 0.2 + rt * sg * (0.07 + w_) + fw * 0.03, 0.5, (0, 0, sg * 10)))
    # 3 HOLD: his right arm straight out flat toward it, palm down, patting the air; the left down; a half-step back
    for k, tt in enumerate((T2 + 0.4, T2 + 0.75, T2 + 1.05, T3 - 0.05)):
        dz = 0.0 if k % 2 == 0 else -0.07
        sig(tt, lambda s_, sg, sh, hp, fw, rt, dz=dz: (sh + fw * 0.2 + rt * 0.08 + UP * (0.02 + dz), 0.3, (0, 0, 90)) if sg > 0 else None)
    # 4 done: both arms wide, thumbs up at the finished height, a step further back
    for k, tt in enumerate((T3 + 0.35, T3 + 0.65, DUR + 0.5)):
        dz = 0.0 if k % 2 == 0 else 0.07
        sig(tt, lambda s_, sg, sh, hp, fw, rt, dz=dz: (sh + rt * sg * 0.19 + UP * (0.06 + dz) + fw * 0.05, 0.5, (0, -sg * 30, sg * 15)))
    lw_layer(data, "spine", lambda t: (-3 * W(t, T1, 0.35) + 4 * W(t, T2, 0.35) - 6 * W(t, T3, 0.4), 0, 0), 0, DUR + 0.4)
    lw_layer(data, "chest", lambda t: (-3 * W(t, T3, 0.35), 0, 0), 0, DUR + 0.4)
    HEAD = Vector((X0, Y0, Z0 + 0.5)); DIGP = Vector((S2_DIG[0], -s2_base(S2_H) / 2, 3.0))
    data.look_at(DIGP, 0.0, max_yaw=15, max_pitch=8, blend=0.0)            # 1 at the digger, his face still to us
    data.look_at(DIGP, T1 + 0.3, max_yaw=15, max_pitch=10, blend=0.2)       # 2 at it
    data.look_at(CAM0 + Vector((0, 0, 0.1)), T2 + 0.3, max_yaw=30, max_pitch=8, blend=0.3)     # (r2y pre-flight: thrown back his head read as broken)   # 3 up at it
    data.look_at(DIGP, T3 + 0.3, max_yaw=15, max_pitch=10, blend=0.3)   # 4 at it (r2ze: glasses floated with the head pitched up; coordinator: keep the pitch small, he backs away)
    data.expression("determined", 0.0, T3 + 0.1, blend=0.15)
    data.expression("happy", T3 + 0.1, DUR + 1.0, blend=0.15)
    data.finish()
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=24.0, fstop=11.0)     # (p2n, r2y: a wider lens: him, the digger and the house side by side, none hiding another)
    print("S2 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    still = lambda t: (CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5)))
    lw_cut(cam, still, still, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a digger piles a wall of black rock behind the house, from its knee to far over its roof", lambda: [wall["body"]], TS[0], TS[3], {"whole": False})])
