"""BEAT 2: "So Iceland built a wall of rock taller than a house to keep the lava out."

HE SETS THE TOP STONE (coordinator, 2026-11-26, after the thrown-boulder staging: "faceted toys", "a flat black
backdrop", "one thrown rock and the wall jumps"). The wall is the one the panel passed in beat 3: the same crushed
black rock, the same boulders on its face, the same daylight. The lens is close on its crest; a painted town house
with its flag sits down on the town side at the lower left, its WHOLE roof below the crest in every still: taller
than a house, at a glance. One action (the last stone goes in), one consequence (he stands on it, above the roof)."""

S2_H = 5.6                              # the wall: beat 3's (S3_H, S3_CREST, S3_BASE)
S2_CREST = 1.6
S2_BASE = 11.0
S2_P0 = (0.06, 0.17)                     # where he stands on the crest
S2_HOUSE = (1.35, 2.6, 3.2, 2.6)        # the town house below, at our lower left: centre x, y, width, depth


def s2_ground_z(x, y):
    """the town's ground inside the wall (y > 0), the black field outside it"""
    if y > 0.5: return 0.05 + 0.08 * lw_fbm(x * 0.3, y * 0.3, 19)
    return 0.2 + 0.07 * lw_fbm(x * 0.3, y * 0.3, 19)


def s2_face_z(y):
    """the wall's height at y, either face"""
    a = abs(y); y0, y1 = S2_BASE / 2, S2_CREST / 2 + 0.1
    return S2_H * 0.97 * max(0.0, min(1.0, (y0 - a) / (y0 - y1)))


def s2_boulder(name, r, seed=3):
    """ONE REAL BOULDER, big enough to carry (coordinator: the coarse icosahedron that reads as rubble at 10 cm is a
    faceted toy at 40): a finely cut lump, its surface pushed about by noise at two scales, broken flat on a few
    sides, in the wall's own rock."""
    rk = lw_random.Random(seed)
    bm = LW_bmesh.new(); LW_bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    cuts = [(Vector((rk.uniform(-1, 1), rk.uniform(-1, 1), rk.uniform(-0.6, 1))).normalized(), rk.uniform(0.72, 0.9)) for _ in range(7)]
    for v in bm.verts:
        n = v.co.normalized()
        d = 1.0 + 0.16 * lw_fbm(n.x * 1.7 + seed, n.y * 1.7 + n.z * 1.3, seed) + 0.05 * lw_fbm(n.x * 6.0, n.y * 6.0 + n.z * 5.0, seed + 5)
        for c, lim in cuts:                               # broken faces: the lump is cut back to a few flat planes
            k = n.dot(c)
            if k > 1e-3: d = min(d, lim / k)
        v.co = n * d; v.co.z = max(v.co.z, -0.62)        # it sits on a flat
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10))
    for p_ in me.polygons: p_.use_smooth = False
    o = lw_link(bpy.data.objects.new(name, me)); o.scale = (r, r * 0.92, r * 0.8)
    return o


def place_wall_works():
    """THE WALL, ALONG ITS CREST (coordinator, 2026-11-26: from the town side it was "a knee-high rock pile above a red
    slab"): one long black ridge running straight to the distance, its boulder faces dropping away on both sides; at
    its foot on the town side three whole painted houses, their roofs far below the crest, a flag on a pole in a yard;
    on the outer side bare black ground, and the fountains small and orange on the far horizon."""
    lw_grid("lava field ground", -80, 30, -40, 34, 130, 90, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#262422", name="lava field rock ground"))
    lw_grid("town ground", -80, 30, S2_BASE / 2 - 0.2, 34, 60, 20, lambda x, y: s2_ground_z(x, y) + 0.04, lw_noise("town moss ground", "#4E5A34", "#8C9263", scale=0.9, rough=1.0, bump=0.5, detail=12))   # the town inside the wall is green: the wall is the black thing
    path = [(x, 0.0) for x in range(-60, 5, 2)] + [(4.0 + 5.0 * math.sin(math.radians(a)), 5.0 - 5.0 * math.cos(math.radians(a))) for a in range(15, 91, 15)] + [(9.0, y) for y in range(7, 30, 2)]
    wall = earth_wall("earth wall", path, h=S2_H, crest=S2_CREST, base=S2_BASE, seed=8)
    px, py = S2_P0
    clear = lambda x, y: abs(x - px) < 0.75 and abs(y - py) < 0.75
    lava_rock("wall face rock", 1900, (-44, 2.5, -S2_BASE / 2 + 0.1, S2_BASE / 2 - 0.1), lambda x, y: max(s2_ground_z(x, y), s2_face_z(y)), seed=27, r=(0.08, 0.28), moss=0.0, avoid=clear)
    # from the town the wall is a BERM of piled basalt, not a slab (coordinator: "a wall of coal"): big and small blocks
    # heaped down its sloped town face, no two a size
    lava_rock("wall face rock big", 420, (-12, 4.5, 0.9, S2_BASE / 2 + 0.3), lambda x, y: max(s2_ground_z(x, y), s2_face_z(y)), seed=41, r=(0.3, 0.75), moss=0.0, avoid=clear)
    lava_rock("wall face rock mid", 900, (-12, 4.5, 0.9, S2_BASE / 2 + 0.6), lambda x, y: max(s2_ground_z(x, y), s2_face_z(y)), seed=42, r=(0.12, 0.3), moss=0.04, avoid=clear)
    lava_rock("lava field rock", 160, (-40, 4, -24, -S2_BASE / 2 - 0.3), s2_ground_z, seed=9, r=(0.1, 0.35), moss=0.0)
    FX.ground("grass", area=(-14, 8.5, S2_BASE / 2 + 0.2, 33), zfn=lambda x, y: s2_ground_z(x, y) + 0.07 + 0.03 * lw_fbm(x * 0.8, y * 0.8, 4), seed=4, name="town grass")   # the kit's real ground under the house
    houses = []
    for k, (x, roof, wl) in enumerate(((-21.5, "#B8352B", "#F1EEE6"), (-26.0, "#2F5E8C", "#E9D9A2"), (-30.5, "#3F7A4A", "#BFD3DD"))):
        houses.append(town_house(f"town house by the wall {k}", (x, 7.3, s2_ground_z(x, 7.3)), yaw=math.pi, w=3.2, d=2.6, storeys=1, base=0.3, pitch=38, roof=roof, wall=wl, seed=5 + k))
    for k, (x, y, roof, wl) in enumerate(((-24.0, 11.2, "#C9A23A", "#F1EEE6"), (-29.5, 10.6, "#B8352B", "#7E9A86"), (-35.5, 11.4, "#2F5E8C", "#F1EEE6"), (-36.0, 7.4, "#C9A23A", "#E9D9A2"))):
        town_house(f"town house back {k}", (x, y, s2_ground_z(x, y)), yaw=math.pi, w=3.2, d=2.6, storeys=1, base=0.3, pitch=38, roof=roof, wall=wl, seed=21 + k)
    lava_rock("town stones", 420, (-46, -12, S2_BASE / 2 + 0.2, 16), lambda x, y: s2_ground_z(x, y) + 0.04, seed=77, r=(0.06, 0.22), moss=0.85)
    # the house the wide set-up stands the wall beside: two storeys of painted tin, whole, the crest well clear of its ridge
    town_house("town house under the wall", (-1.6, 7.4, s2_ground_z(-1.6, 7.4)), yaw=math.pi, w=3.4, d=2.7, h=1.05, storeys=2, base=0.3, pitch=38, roof="#B8352B", wall="#E9D9A2", seed=5)
    # ICELAND: the flag on a pole in the yard between the first two houses, its face to the lens
    blue = lw_paint("flag blue", "#02529C", rough=0.7); white = lw_paint("flag white", "#F4F4F0", rough=0.7); red = lw_paint("flag red", "#DC1E35", rough=0.7)
    fx, fy = 1.4, 6.3; fzz = s2_ground_z(fx, fy)
    K.cyl("flag pole", (fx, fy, fzz + 1.6), 0.025, 3.2, lw_paint("flag pole white", "#EDEDE8", rough=0.5), v=10)
    FS = 1.6; c = Vector((fx, fy + 0.36 * FS, fzz + 2.75))
    for nm, off, size, m in (("field", 0.0, (0.012, 0.66, 0.46), blue), ("white bar", -0.1, (0.016, 0.13, 0.46), white), ("white band", 0.0, (0.016, 0.66, 0.13), white),
                             ("red bar", -0.1, (0.02, 0.065, 0.46), red), ("red band", 0.0, (0.02, 0.66, 0.065), red)):
        K.box(f"icelandic flag {nm}", tuple(c + Vector((0, off * FS, 0))), (size[0], size[1] * FS, size[2] * FS), m, bev=0.0)
    # the fountains, far out past the wall's end on the outer side
    # what the wall keeps out: from the town, lava fountains stand beyond the crest under their smoke (beat 1's ragged
    # fountains: a fat torn body and a thin taller jet), their feet hidden behind the wall
    for k, (x, y, hf) in enumerate(((-10.0, -37.0, 6.5), (-4.0, -38.0, 7.5), (4.0, -36.0, 6.0), (10.0, -38.0, 7.0))):      # (the kit's fountain, as in beat 1)
        FX.lava_fountain(base=(x, y, 0.0), h=hf, w=1.2, length=3.0, plume=0.9 * hf, clots=250, lean=(0.3, -0.2), seed=23 + k, splats=0, t_end=DUR + 1.0, name=f"far fountain {k}")
    def light():
        return FX.sky("day", sun_az=150)["sun"]              # the kit's real day sky, ONE for the close stills and the wide; its sun from the side of both lenses
    return dict(light=light, wall=wall, house=houses[0], houses=houses)


def shot2():
    """HE SETS THE LAST STONE, AND THEN WE SEE THE WALL. Close along the crest: he heaves a boulder up at his chest,
    both hands on it (still 1), presses it down onto the row of crest boulders in a puff of pale dust (still 2),
    straightens up beside the finished row looking out (still 3). CUT WIDE from the town side (still 4): the black wall
    standing clear over a two-storey tin house, running out of frame both ways, him small on top, the eruption's smoke
    behind it."""
    T_ARR = 0.62; T_GO = 0.9; T_SET = 1.32; T_OFF = 1.6; T_UPR = 2.0; T_CUT = 0.56 * DUR; T_BACK = 0.8 * DUR
    W = lw_win
    P = place_wall_works()
    light = P["light"]
    data = load_data()
    P0 = Vector((S2_P0[0], S2_P0[1], S2_H + 0.03))
    data.place(0.0, 0.0, 0.0); sc.frame_set(1); bpy.context.view_layer.update()
    f0 = data.forward(); YAW_D = 30.0 - math.degrees(math.atan2(f0.y, f0.x))      # three-quarter to the close lens, facing the row he builds
    YAW_D = (YAW_D + 180.0) % 360.0 - 180.0                    # (walk_to keeps its heading inside a half turn: so does he, or he spins once on frame 3)
    data.place(P0.x, P0.y, YAW_D); data.arm.location.z = P0.z; bpy.context.view_layer.update()
    YAW0 = data.arm.rotation_euler.z
    fw = data.forward(); fw.z = 0; fw.normalize(); lf = Vector((-fw.y, fw.x, 0.0))
    sh_l = {sd: 1.0 if (acts._shoulder(data, sd) - (acts._shoulder(data, "L") + acts._shoulder(data, "R")) / 2).dot(lf) > 0 else -1.0 for sd in "LR"}
    # he CARRIES it in along the crest (a body that only shifts its hands is a still frame on a phone), then turns to the row
    PS = P0 + Vector((-0.75, -0.06, 0.0))                     # (he strides in from well down the crest: still 1 is him mid-stride with the stone, the row's end empty ahead of him)
    data.place(PS.x, PS.y, YAW_D - 22.0)
    kit = hard_hat(data)
    data.walk_to((P0.x, P0.y), 0.0, T_ARR, step=0.2, lift=0.07, bob=0.02)
    from character import _fcurves
    for fc in _fcurves(data.arm.animation_data.action):       # walk_to walks on z = 0: lift every key of it onto the crest
        if fc.data_path == "location" and fc.array_index == 2:
            for kp in fc.keyframe_points: kp.co[1] += P0.z; kp.handle_left[1] += P0.z; kp.handle_right[1] += P0.z
    sc.frame_set(F(T_ARR)); bpy.context.view_layer.update(); YW = data.arm.rotation_euler.z
    while YW - YAW0 > math.pi: YW -= 2 * math.pi
    while YW - YAW0 < -math.pi: YW += 2 * math.pi
    R_ = 0.088; RB = 0.2
    SPOT = P0 + fw * 0.25; SPOT.z = S2_H + RB * 0.8 * 0.9 + R_ * 0.8 * 0.45          # on top of the row, in the gap between two of its boulders
    def body(t):
        return P0.copy(), YW + (YAW0 - YW) * W(t, T_ARR, 0.3) + math.radians(14) * W(t, T_OFF, 0.5)       # round to the row, then to the town he is keeping
    for f in range(F(T_ARR) + 1, NF + 8):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    def held(t):                                              # the boulder on his two hands, in front of his chest, wherever he is
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        m = (acts._shoulder(data, "L") + acts._shoulder(data, "R")) / 2; f_ = data.forward(); f_.z = 0; f_.normalize()
        return m + f_ * 0.17 + Vector((0, 0, -0.05)), Vector((-f_.y, f_.x, 0.0))
    HB, _lfB = held(T_GO)
    def stone_at(t):
        if t < T_GO: return held(t)[0]
        if t < T_SET:
            u = ease((t - T_GO) / (T_SET - T_GO)); p = HB.lerp(SPOT, u); p.z += 0.05 * math.sin(math.pi * u); return p
        return SPOT.copy()
    def side_at(t):
        return held(t)[1] if t < T_GO else _lfB
    T_REL = T_GO + 0.42 * (T_SET - T_GO)                       # his hands go with it as far as they reach, then it drops the last of the way
    lw_layer(data, "spine", lambda t: (15 * W(t, T_GO, T_SET - T_GO) * (1 - W(t, T_OFF, 0.35)), 0, 0), T_GO, DUR + 0.4)
    CAM0 = P0 + Vector((0.6, 2.5, 1.3)); LOOK0 = P0 + Vector((0.0, 0.0, 0.3))
    FAR = P0 + Vector((3.0, 14.0, 0.0))
    data.look_at(CAM0, 0.0, max_yaw=40, max_pitch=25, blend=0.0)
    data.look_at(SPOT, T_GO + 0.1, max_yaw=40, max_pitch=35, blend=0.3)
    data.look_at(FAR, T_OFF + 0.1, max_yaw=14, max_pitch=25, blend=0.5)
    data.expression("determined", 0.0, T_OFF, blend=0.15)
    data.expression("pleased", T_OFF, DUR + 1.0, blend=0.3)
    # ---- both hands ON the stone, all the way (the panel: "neither hand under or on it")
    for sd in "LR":
        sg = sh_l[sd]
        data.reach(sd, (lambda t, sg=sg: stone_at(min(t, T_REL)) + side_at(min(t, T_REL)) * (sg * R_ * 0.9) + Vector((0, 0, -0.01))), 0.0, T_OFF, lead=0.05, back=None, elbow_out=0.3)
    near = sorted("LR", key=lambda s_: (data.arm.matrix_world @ data.pb[f"arm.{s_}"].head).dot(Vector((0.23, 0.97, 0.0))), reverse=True)   # near[0]: the arm toward the close lens
    LG = 0.38
    HANG = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    SHADE = lambda sg: ((-20, 0, -sg * 96), (-20, 0, -sg * 52), (0, 0, 0))                       # a hand up over his eyes
    HIP = lambda sg: ((-6, 0, -sg * 64), (-98, 0, sg * 30), (0, 0, 0))                           # a fist on his hip
    def pose(t, P_, sides="LR"):
        for sd in sides:
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), P_(-1 if sd == "L" else 1)): data._k(bn, t, rot=r)
    pose(T_UPR + 0.3 - LG, HANG, "LR"); pose(T_BACK - 0.3 - LG, HANG, "LR"); sc.frame_set(F(T_BACK)); bpy.context.view_layer.update()
    row_arm = max("LR", key=lambda s_: acts._shoulder(data, s_).x); oth_arm = "R" if row_arm == "L" else "L"       # the arm on the row's side: out along his finished crest
    OUTR = lambda sg: ((8, 0, -sg * 74), (0, 0, -sg * 8), (0, 0, 0))
    pose(T_BACK + 0.12 - LG, OUTR, row_arm); pose(T_BACK + 0.12 - LG, HIP, oth_arm); pose(DUR + 0.5, OUTR, row_arm); pose(DUR + 0.5, HIP, oth_arm)
    data.finish()
    stone = s2_boulder("boulder top stone", R_, seed=4)
    stone.data.materials.clear()                              # HIS boulder is the wall's own basalt, a shade lighter with quarry dust: the one we follow onto the row
    stone.data.materials.append(lw_noise("fresh quarried boulder", "#3A3835", "#6A655F", scale=14, rough=0.92, bump=0.8, detail=10))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        stone.location = stone_at(t); stone.keyframe_insert("location", frame=f)
        stone.rotation_euler = (0.2 * (1 - W(t, T_GO, T_SET - T_GO)), 0, 0.6); stone.keyframe_insert("rotation_euler", frame=f)
    for k in range(0, 70):                                  # the crest's row of boulders, running away from him out of sight: a base course...
        rr = RB * (0.92 + 0.16 * lw_fbm(k * 1.7, 0.3, 5))
        b_ = s2_boulder(f"wall crest boulder {k}", rr, seed=20 + k); b_.location = (SPOT.x + 0.1 + 0.4 * k, SPOT.y + 0.03 * math.sin(k * 2.1), S2_H + rr * 0.8 * 0.5)       # (the row runs on AHEAD of him, so nothing of it stands between his feet and the lens); b_.rotation_euler = (0, 0, k * 1.3)
    for k in range(1, 70):                                  # ...and a top course that ENDS where he stands: his boulder is its next one
        rr = R_ * (0.95 + 0.2 * lw_fbm(k * 2.3, 0.7, 9))
        b_ = s2_boulder(f"wall crest top boulder {k}", rr, seed=120 + k); b_.location = (SPOT.x + 0.4 * k, SPOT.y + 0.03 * math.sin(k * 1.3), SPOT.z + 0.01 * math.sin(k * 3.1)); b_.rotation_euler = (0, 0, k * 2.1)
    # (the puff of dust is cut: as a gas it was invisible at phone size, as billows it read as snowballs)
    # ---- the lens: close along the crest; then WIDE from the town: the wall over the house
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 50.0, face_at=(0.5, 0.6), height=0.36, t=T_SET)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=50.0, fstop=16.0)
    WCAM = Vector((-1.0, 31.0, 3.6)); WLOOK = Vector((-1.0, 0.0, 1.45))
    print("S2 CAM", tuple(round(v, 2) for v in CAM), "look", tuple(round(v, 2) for v in LOOK), flush=True)
    lw_cut(cam, lambda t: (CAM, LOOK, data.pos() + Vector((0, 0, 0.5))), lambda t: (WCAM, WLOOK, Vector((-1.0, 3.0, 3.0))), T_CUT, T_BACK, 50.0, 85.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("boulder",), cutaway=(T_CUT, T_BACK),
                boxes=[],
                conseq=[("he heaves the last boulder up and sets it on the wall's crest", lambda: [stone] + [o for o in bpy.data.objects if o.name.startswith("wall crest top boulder")][:6], 0.0, T_SET + 0.2, {"whole": False}),
                        ("the wall stands clear over the two-storey house", lambda: meshes([o for o in bpy.data.objects if o.name.startswith("town house under the wall")]), T_CUT, T_BACK, {"whole": False})])
