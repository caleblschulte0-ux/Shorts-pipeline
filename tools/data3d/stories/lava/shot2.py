"""BEAT 2: "So Iceland built a wall of rock taller than a house to keep the lava out."

HE SETS THE TOP STONE (coordinator, 2026-11-26, after the thrown-boulder staging: "faceted toys", "a flat black
backdrop", "one thrown rock and the wall jumps"). The wall is the one the panel passed in beat 3: the same crushed
black rock, the same boulders on its face, the same daylight. The lens is close on its crest; a painted town house
with its flag sits down on the town side at the lower left, its WHOLE roof below the crest in every still: taller
than a house, at a glance. One action (the last stone goes in), one consequence (he stands on it, above the roof)."""

S2_H = 4.4                              # the wall: beat 3's (S3_H, S3_CREST, S3_BASE)
S2_CREST = 1.6
S2_BASE = 8.6
S2_P0 = (0.0, 0.1)                     # where he stands on the crest
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
    lw_grid("lava field ground", -80, 30, -40, 34, 130, 90, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))
    lw_grid("town ground", -80, 30, S2_BASE / 2 - 0.2, 34, 60, 20, lambda x, y: s2_ground_z(x, y) + 0.04, lw_noise("town moss ground", "#5E6A3C", "#8C9263", scale=3.0, rough=1.0, bump=0.3))   # the town inside the wall is green: the wall is the black thing
    path = [(x, 0.0) for x in range(-60, 5, 2)] + [(4.0 + 5.0 * math.sin(math.radians(a)), 5.0 - 5.0 * math.cos(math.radians(a))) for a in range(15, 91, 15)] + [(9.0, y) for y in range(7, 30, 2)]
    wall = earth_wall("earth wall", path, h=S2_H, crest=S2_CREST, base=S2_BASE, seed=8)
    px, py = S2_P0
    clear = lambda x, y: abs(x - px) < 0.75 and abs(y - py) < 0.75
    lava_rock("wall face rock", 1900, (-44, 2.5, -S2_BASE / 2 + 0.1, S2_BASE / 2 - 0.1), lambda x, y: max(s2_ground_z(x, y), s2_face_z(y)), seed=27, r=(0.08, 0.28), moss=0.0, avoid=clear)
    lava_rock("lava field rock", 160, (-40, 4, -24, -S2_BASE / 2 - 0.3), s2_ground_z, seed=9, r=(0.1, 0.35), moss=0.0)
    houses = []
    for k, (x, roof, wl) in enumerate(((-21.5, "#B8352B", "#F1EEE6"), (-26.0, "#2F5E8C", "#E9D9A2"), (-30.5, "#3F7A4A", "#BFD3DD"))):
        houses.append(town_house(f"town house by the wall {k}", (x, 5.85, s2_ground_z(x, 5.85)), yaw=math.pi, w=3.2, d=2.6, storeys=1, base=0.3, pitch=38, roof=roof, wall=wl, seed=5 + k))
    for k, (x, y, roof, wl) in enumerate(((-24.0, 11.2, "#C9A23A", "#F1EEE6"), (-29.5, 10.6, "#B8352B", "#7E9A86"), (-35.5, 11.4, "#2F5E8C", "#F1EEE6"), (-36.0, 6.0, "#C9A23A", "#E9D9A2"))):
        town_house(f"town house back {k}", (x, y, s2_ground_z(x, y)), yaw=math.pi, w=3.2, d=2.6, storeys=1, base=0.3, pitch=38, roof=roof, wall=wl, seed=21 + k)
    lava_rock("town stones", 420, (-46, -12, S2_BASE / 2 + 0.2, 16), lambda x, y: s2_ground_z(x, y) + 0.04, seed=77, r=(0.06, 0.22), moss=0.85)
    # ICELAND: the flag on a pole in the yard between the first two houses, its face to the lens
    blue = lw_paint("flag blue", "#02529C", rough=0.7); white = lw_paint("flag white", "#F4F4F0", rough=0.7); red = lw_paint("flag red", "#DC1E35", rough=0.7)
    fx, fy = -23.75, 4.9; fzz = s2_ground_z(fx, fy)
    K.cyl("flag pole", (fx, fy, fzz + 1.6), 0.025, 3.2, lw_paint("flag pole white", "#EDEDE8", rough=0.5), v=10)
    FS = 1.6; c = Vector((fx, fy + 0.36 * FS, fzz + 2.75))
    for nm, off, size, m in (("field", 0.0, (0.012, 0.66, 0.46), blue), ("white bar", -0.1, (0.016, 0.13, 0.46), white), ("white band", 0.0, (0.016, 0.66, 0.13), white),
                             ("red bar", -0.1, (0.02, 0.065, 0.46), red), ("red band", 0.0, (0.02, 0.66, 0.065), red)):
        K.box(f"icelandic flag {nm}", tuple(c + Vector((0, off * FS, 0))), (size[0], size[1] * FS, size[2] * FS), m, bev=0.0)
    # the fountains, far out past the wall's end on the outer side
    for k, (x, y, hf) in enumerate(((-58.0, -1.5, 13.0), (-64.0, -4.5, 18.0), (-70.0, -2.5, 15.0))):
        lw_fire_column(f"far fountain {k}", (x, y, 0.0), w=4.6, h_fire=hf, h_smoke=14.0, lean=(0.0, -0.3), t_end=DUR + 1.0, seed=3.1 + k * 2.3, fire=14.0, smoke_d=1.6, rise=2.4, spread=0.3)
    def light():
        k = iceland_light(sun_elev=34, sun_az=55, sun=3.0, sky=0.4, haze=1.4)           # beat 3's light, on beat 3's wall
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))
        return k
    return dict(light=light, wall=wall, house=houses[0], houses=houses)


def shot2():
    """HE SETS THE TOP STONE. Close on the crest: he heaves a boulder up to his chest (still 1), locks it overhead
    (still 2), sets it down in the gap in the crest in a puff of dust (still 3), and stands up on it shading his eyes,
    looking out over the wall, the house's whole roof and its flag below his feet (still 4)."""
    T_UP = 0.62; T_TOP = 1.0; T_DOWN = 1.5; T_SET = 2.0; T_STEP = 2.3; T_STAND = 2.95
    W = lw_win
    P = place_wall_works()
    light = P["light"]
    data = load_data()
    P0 = Vector((S2_P0[0], S2_P0[1], S2_H + 0.03))
    data.place(0.0, 0.0, 0.0); sc.frame_set(1); bpy.context.view_layer.update()
    f0 = data.forward(); YAW_D = -57.0 - math.degrees(math.atan2(f0.y, f0.x))      # three-quarter to the lens (it is on the town side), turned along the crest
    data.place(P0.x, P0.y, YAW_D); data.arm.location.z = P0.z; bpy.context.view_layer.update()
    YAW0 = data.arm.rotation_euler.z; data._kobj(0.0, loc=tuple(P0), rot=YAW0)
    kit = hard_hat(data)
    sc.frame_set(1); bpy.context.view_layer.update()
    fw = data.forward(); fw.z = 0; fw.normalize()
    R_ = 0.17
    SPOT = P0 + Vector((0.04, -0.36, 0.0)); SPOT.z = S2_H + R_ * 0.8 * 0.5             # the gap in the crest in front of his feet: the stone's centre once it is in
    TOPZ = SPOT.z + R_ * 0.8 * 0.86 + 0.045                                    # the stone's top, where he stands
    def body(t):
        u = W(t, T_STEP, T_STAND - T_STEP)
        p = P0.lerp(Vector((SPOT.x, SPOT.y, TOPZ)), u); p.z += 0.16 * math.sin(math.pi * u)      # the step up onto it
        yaw = YAW0 - math.radians(22) * W(t, T_DOWN, T_SET - T_DOWN)                                 # round to look out over the wall
        return p, yaw
    for f in range(1, NF + 8):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    # the heave: back as it comes up to his chest, straight under it overhead, right over as he sets it down, up
    lw_layer(data, "spine", lambda t: (-10 * W(t, 0.1, 0.3) * (1 - W(t, T_TOP - 0.2, 0.25)) + 8 * W(t, T_DOWN, T_SET - T_DOWN) * (1 - W(t, T_STEP - 0.08, 0.3)), 0, 0), 0, DUR + 0.4)
    CHEST = lambda sg: ((-42, 0, -sg * 8), (-58, 0, sg * 16), (0, 0, 0))                        # the boulder against his chest
    LOCK = lambda sg: ((0, 0, -sg * 104), (0, 0, -sg * 34), (0, 0, 0))                          # arms locked up beside his head, the boulder on his hands
    DOWN = lambda sg: ((-40, 0, -sg * 6), (-12, 0, sg * 8), (0, 0, 0))                          # down on the stone
    OPEN = lambda sg: ((-10, 0, -sg * 74), (-25, 0, -sg * 25), (0, 0, 0))                        # his hands thrown open as it drops off his hat
    OPEN2 = lambda sg: ((-40, 0, -sg * 6), (-12, 0, sg * 8), (0, 0, 0))
    HANG = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    SHADE = lambda sg: ((-20, 0, -sg * 96), (-20, 0, -sg * 52), (0, 0, 0))                       # a hand up over his eyes
    def pose(t, P_, sides="LR"):
        for sd in sides:
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), P_(-1 if sd == "L" else 1)): data._k(bn, t, rot=r)
    for t_, P_ in ((0.0, CHEST), (T_UP - 0.2, CHEST), (T_TOP, LOCK), (T_DOWN - 0.12, LOCK), (T_SET, OPEN), (T_STEP, OPEN2), (T_STAND, HANG)):
        pose(t_, P_)
    near = sorted("LR", key=lambda s_: (data.arm.matrix_world @ data.pb[f"arm.{s_}"].head).dot(Vector((0.96, -0.29, 0.0))), reverse=True)   # near[0]: the arm toward the lens
    pose(T_STAND + 0.12, SHADE, near[1]); pose(DUR + 0.5, SHADE, near[1]); pose(T_STAND + 0.2, HANG, near[0]); pose(DUR + 0.5, HANG, near[0])
    CAM0 = P0 + Vector((2.55, -0.36, 1.2)); LOOK0 = CAM0 + Vector((-4.8, 0.68, -1.3))
    FAR = P0 + Vector((-3.0, -14.0, 0.5))                  # out over the lava field, past the lens's right shoulder
    data.look_at(CAM0, 0.0, max_yaw=40, max_pitch=25, blend=0.0)
    data.look_at(FAR, T_STAND - 0.05, max_yaw=55, max_pitch=25, blend=0.35)
    data.expression("determined", 0.0, T_SET, blend=0.15)
    data.expression("pleased", T_STAND, DUR + 1.0, blend=0.3)
    data.finish()
    # ---- the stone: on his hands at his chest, overhead, down into the gap; then it is part of the wall
    hands = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        hands[f] = (data.arm.matrix_world @ data.pb["fore.L"].tail + data.arm.matrix_world @ data.pb["fore.R"].tail) / 2
    stone = s2_boulder("boulder top stone", R_, seed=4)
    for k in list(range(-1, -60, -1)):                 # the crest's row of boulders: his is the one that was missing
        rr = 0.13 if k == 1 else R_ * (0.9 + 0.2 * lw_fbm(k * 1.7, 0.3, 5))
        b_ = s2_boulder(f"wall crest boulder {k}", rr, seed=20 + k); b_.location = (SPOT.x + 0.5 * k, SPOT.y + 0.04 * math.sin(k * 2.1), S2_H + rr * 0.8 * 0.5); b_.rotation_euler = (0, 0, k * 1.3)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        up = W(t, T_UP - 0.1, T_TOP - T_UP + 0.05)
        zf = ease(min(1.0, up / 0.7)); k7 = W(t, T_TOP + 0.02, 0.16)
        fwd = (0.15 + 0.18 * math.sin(math.pi * min(1.0, up / 0.7))) * (1 - k7) + 0.06 * k7             # up in front of his face first, then back over his hard hat
        hdir = (fw + Vector((0.99, -0.14, 0.0)) * 1.6).normalized()
        held = hands[f] + (hdir * (1 - k7) + fw * k7) * fwd + Vector((0, 0, 0.1 + (0.5 - 0.1) * zf))     # on his hands at his chest; on his hard hat with his arms up beside it
        if t < T_DOWN - 0.12: p = held
        elif t < T_SET:
            u = (t - (T_DOWN - 0.12)) / (T_SET - T_DOWN + 0.12); p0 = hands[F(T_DOWN - 0.12)] + fw * 0.06 + Vector((0, 0, 0.5))
            dr = (SPOT - P0); dr.z = 0; dr.normalize()
            p1 = Vector((P0.x + dr.x * 0.54, P0.y + dr.y * 0.54, p0.z)); p2 = Vector((p1.x, p1.y, SPOT.z + 0.16))      # out sideways off his hat, down clear of it, in to the gap
            p = p0.lerp(p1, ease(u / 0.4)) if u < 0.4 else (p1.lerp(p2, ease((u - 0.4) / 0.4)) if u < 0.8 else p2.lerp(SPOT, ease((u - 0.8) / 0.2)))
        else: p = SPOT.copy()
        stone.location = p; stone.keyframe_insert("location", frame=f)
        stone.rotation_euler = (0.25 * (1 - up), 0, 0.6); stone.keyframe_insert("rotation_euler", frame=f)
    dust = [lw_steam(f"wall stone dust {k}", (SPOT.x - 0.3 + 0.25 * k, SPOT.y - 0.1 - 0.25 * k, S2_H), w=0.4, h=0.45, seed=3.7 + k, col=(0.86, 0.84, 0.8), dens=11.0, lean=(0.25 * (k - 0.5), -0.1), rise=0.7,
                     keys=[(T_SET - 0.03, 0.0), (T_SET + 0.18, 1.0), (T_SET + 0.9, 0.35), (DUR + 0.5, 0.0)], t_end=DUR + 1.0) for k in range(2)]
    # ---- the lens: close on the crest from just outside the wall, level with him: the house's whole roof below at our left
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 50.0, face_at=(0.62, 0.41), height=0.34, t=0.0)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=50.0, fstop=16.0)
    print("S2 CAM", tuple(round(v, 2) for v in CAM), "look", tuple(round(v, 2) for v in LOOK), flush=True)
    lw_cut(cam, lambda t: (CAM, LOOK, data.pos() + Vector((0, 0, 0.5))), lambda t: (CAM, LOOK, data.pos()), -1.0, -1.0, 50.0, 50.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("boulder",), cutaway=None,
                boxes=[],
                conseq=[("he heaves the last boulder up and sets it in the gap on the wall's crest", lambda: [stone], 0.0, T_SET + 0.2, {"whole": False}),
                        ("the house's whole roof sits below the wall's crest", lambda: meshes([o for o in bpy.data.objects if o.name.startswith("town house by the wall 0")]), 0.0, DUR, {"whole": False})])
