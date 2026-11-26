"""BEAT 2: "So Iceland built a wall of rock taller than a house to keep the lava out."

The wall works by day. The driver stands in front of a town house with a black boulder over his head; behind the
house the rock wall is only waist-high. He heaves the boulder back over his shoulder onto it, and a second one, and
the wall rises row on row until its black face stands far over the roof; he looks up at it and gives us a thumbs up.
(The digger and its remote control are cut: at phone size the remote was a toy and he was a talking head.)"""

S2_DECK = 0.52                          # the digger's deck
S2_BOOM = Vector((0.95, 0.42, 1.05))    # the boom's foot pin, in the digger's own frame (facing its +X)
S2_L1, S2_L2 = 3.4, 3.0                 # boom and stick
S2_DIG = Vector((0.7, 3.6, 0.0))
S2_DIG_A = math.radians(90 + 25)       # its heading: turned off square to the wall, so the lens sees its side and its arm reaches up over the house      # the digger, beyond him on our right, facing +Y (the wall)
S2_HOUSE = (-1.55, 2.7, 3.0, 2.6)       # the house at the wall's foot, beyond him on our left: centre x, y, width, depth
S2_P0 = (-1.2, -1.0)                    # where he stands with the remote
# REDESIGN after board round 3 ("a gentle brown dirt slope ... about the digger's height", "no crest in frame"): the
# wall is a STEEP black rock face, three storeys and more over him, close behind the digger, its crest in frame
S2_WALL_Y = 6.8                        # the wall's crest centre line (it runs along X)
S2_WALL_H = 6.0
S2_BASE = 4.6
S2_FOOT = S2_WALL_Y - S2_BASE / 2       # its near foot (y)
S2_EDGE = S2_WALL_Y - 0.7               # its crest's near edge (y)


def s2_face_z(y):
    return S2_WALL_H * max(0.0, min(1.0, (y - S2_FOOT) / (S2_EDGE - S2_FOOT)))


def s2_ground_z(x, y):
    return 0.08 * lw_fbm(x * 0.4, y * 0.4, 11)


def s2_ik(p):
    """boom angle a (from level) and stick angle b (from the boom's line) that put the stick's end at p (x, z)"""
    dx, dz = p[0] - S2_BOOM.x, p[1] - S2_BOOM.z; d = max(abs(S2_L1 - S2_L2) + 1e-3, min(S2_L1 + S2_L2 - 1e-3, math.hypot(dx, dz)))
    c = (S2_L1 ** 2 + d ** 2 - S2_L2 ** 2) / (2 * S2_L1 * d)
    a = math.atan2(dz, dx) + math.acos(max(-1, min(1, c)))           # elbow up
    cb = (S2_L1 ** 2 + S2_L2 ** 2 - d ** 2) / (2 * S2_L1 * S2_L2)
    b = -(math.pi - math.acos(max(-1, min(1, cb))))
    return a, b


S2_RC_FW, S2_RC_UP = 0.18, -0.13        # the remote's centre from the middle of his shoulders: forward, up


def s2_knob_off(sx, lean, yaw):
    """a stick's knob from the remote's centre, the stick leaning `lean` (its pivot turned -lean about x), the remote
    turned `yaw`: the box (sx, 0, 0.025) to its pivot, the knob 0.065 up the stick"""
    v = Vector((sx, 0.065 * math.sin(lean), 0.025 + 0.065 * math.cos(lean)))
    c, s_ = math.cos(yaw), math.sin(yaw)
    return Vector((c * v.x - s_ * v.y, s_ * v.x + c * v.y, v.z))


def s2_remote(data):
    """the digger's remote control pack: a yellow box on his chest strap with two black sticks on its top, carried on
    his chest bone. Returns (box, [(stick pivot, knob)])."""
    sc.frame_set(1); bpy.context.view_layer.update()
    sh = [acts._shoulder(data, s_) for s_ in "LR"]; mid = (sh[0] + sh[1]) / 2
    fw = data.forward()
    c = mid + fw * S2_RC_FW + Vector((0, 0, S2_RC_UP))
    yaw = data.arm.rotation_euler.z
    root = K.empty("remote control", tuple(c))
    yel = lw_paint("remote yellow", "#F2B10E", rough=0.4); dark = lw_rubber("remote black", "#1A1A1A", rough=0.6)
    K.box("remote control box", (0, -0.01, 0), (0.2, 0.065, 0.05), yel, bev=0.012, parent=root)
    K.box("remote control screen", (0, -0.035, 0.026), (0.07, 0.012, 0.004), lw_emit("remote screen", "#7FE0FF", 4.0), bev=0.0, parent=root)
    sticks = []
    for sx in (-0.06, 0.06):
        pv = K.empty("remote stick pivot", (sx, 0.0, 0.025), parent=root)
        K.cyl("remote stick", (0, 0.0, 0.03), 0.008, 0.06, dark, parent=pv)
        kn = K.sph("remote stick knob", (0, 0.0, 0.065), 0.02, lw_rubber("remote knob red", "#C8201A", rough=0.5), parent=pv)   # red knobs, so the two sticks read
        sticks.append((pv, kn))
    lw_local(root)
    root.rotation_euler = (0, 0, yaw)
    bpy.context.view_layer.update()
    M = root.matrix_world.copy()
    return root, sticks


def s2_digger(knob_pts=((0.46, -0.58, S2_DECK + 0.545), (0.46, -0.3, S2_DECK + 0.545))):
    """THE DIGGER: a yellow tracked excavator facing +X, an open operator's deck on its -Y side where he stands at two
    control sticks, the boom on its +Y side: boom, stick and a toothed bucket, each on its own pivot empty.
    Returns dict(boom, stick, bucket, sticks=[(pivot, knob)], load)."""
    yel = lw_paint("digger yellow worn", "#E8A80C", rough=0.5)      # worn paint, dust in its seams
    dark = lw_metal("digger steel", "#2C2C2E", rough=0.5)
    track = lw_rubber("track rubber", "#1E1E1E", rough=0.9)
    for sy in (-0.72, 0.72):
        K.box("digger track", (0.1, sy, 0.22), (2.5, 0.42, 0.44), track, bev=0.12)
        for x in (-0.95, -0.3, 0.35, 1.0):
            K.cyl("digger roller", (x, sy - 0.22 * (1 if sy < 0 else -1), 0.22), 0.13, 0.03, dark, rot=(math.pi / 2, 0, 0), v=20)
    K.box("digger turntable", (0.0, 0.0, 0.48), (1.5, 1.5, 0.1), dark, bev=0.02)
    K.box("digger engine housing", (-0.75, 0.15, 0.95), (1.0, 1.55, 0.85), yel, bev=0.06)
    K.box("digger counterweight", (-1.3, 0.15, 0.82), (0.25, 1.6, 0.6), yel, bev=0.08)
    K.box("digger deck", (0.25, -0.45, S2_DECK - 0.03), (0.95, 0.75, 0.06), lw_noise("deck tread", "#3A3A3C", "#56565A", scale=80, rough=0.6, bump=1.0))
    K.box("digger boom mount", (0.75, 0.42, 0.8), (0.5, 0.5, 0.55), yel, bev=0.05)
    for sy in (-0.83, -0.07):                            # the canopy: two rear posts and the roof over his deck
        K.box("digger canopy post", (-0.2, sy, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    K.box("digger canopy roof", (0.2, -0.45, S2_DECK + 1.26), (0.95, 0.85, 0.05), dark, bev=0.015)
    cg = K.mat("cab glass", "#26343C", rough=0.04, metal=0.3)      # the cab's glass: front, sides and back
    K.box("digger cab glass", (0.66, -0.45, S2_DECK + 0.78), (0.02, 0.8, 0.9), cg, bev=0.0)
    for sy_ in (-0.86, -0.04):
        K.box("digger cab glass", (0.22, sy_, S2_DECK + 0.78), (0.86, 0.02, 0.9), cg, bev=0.0)
    K.box("digger cab post", (0.66, -0.86, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    K.box("digger cab post", (0.66, -0.04, S2_DECK + 0.62), (0.05, 0.05, 1.24), dark, bev=0.01)
    # its working parts, so it reads as a machine and not a toy block: engine grille slats, an exhaust stack, grab
    # rails, a warning-striped counterweight, a step, the hydraulic hoses
    for k in range(7):
        K.box("digger grille slat", (-0.75 + 0.12 * (k - 3), -0.63, 1.05), (0.05, 0.02, 0.45), dark, bev=0.005)
    K.cyl("digger exhaust", (-0.95, 0.55, 1.55), 0.045, 0.4, lw_metal("exhaust steel", "#3A3634", rough=0.6), v=14)
    rail = lw_metal("grab rail", "#202022", rough=0.4)
    for x in (-1.15, -0.35):
        K.cyl("digger grab rail post", (x, -0.66, 1.42), 0.015, 0.12, rail, v=8)
    K.cyl("digger grab rail", (-0.75, -0.66, 1.48), 0.015, 0.82, rail, rot=(0, math.pi / 2, 0), v=8)
    blk = lw_paint("stripe black", "#1A1A1A", rough=0.6)
    for k in range(5):
        o = K.box("digger warning stripe", (-1.43, -0.45 + 0.3 * k, 0.82), (0.02, 0.09, 0.62), blk, bev=0.0)
        o.rotation_euler = (math.radians(35), 0, 0)
    K.box("digger step", (0.25, -0.88, 0.5), (0.4, 0.14, 0.03), dark, bev=0.005)
    sticks = []
    if knob_pts: K.box("digger seat back", (-0.1, -0.45, S2_DECK + 0.5), (0.08, 0.4, 0.45), lw_rubber("seat black", "#1E1E1E", rough=0.7), bev=0.03)
    for kx, ky, kz in knob_pts:                           # the two control towers in front of him, a stick on each
        top = kz - 0.135
        K.box("digger control tower", (kx + 0.03, ky, (S2_DECK + top) / 2), (0.1, 0.1, top - S2_DECK), dark, bev=0.01)
        pv = K.empty("control stick pivot", (kx, ky, top))
        K.cyl("control stick", (kx, ky, top + 0.06), 0.012, 0.12, dark, parent=pv)
        knob = K.sph("control stick knob", (kx, ky, kz), 0.03, lw_rubber("knob black", "#141414", rough=0.5), parent=pv)
        sticks.append((pv, knob))
    K.box("digger lamp", (0.2, -0.02, S2_DECK + 1.3), (0.1, 0.12, 0.06), lw_emit("digger lamp", "#FFF2D0", 12.0), bev=0.01)
    boom = K.empty("digger boom", tuple(S2_BOOM))
    K.box("digger boom arm", (S2_BOOM.x + S2_L1 / 2, S2_BOOM.y, S2_BOOM.z), (S2_L1, 0.26, 0.34), yel, bev=0.05, parent=boom)
    K.cyl("digger ram", (S2_BOOM.x + 0.9, S2_BOOM.y, S2_BOOM.z - 0.25), 0.06, 1.4, lw_metal("ram chrome", "#C8CCD0", rough=0.15), rot=(0, math.pi / 2, 0), parent=boom)
    chrome = lw_metal("ram chrome", "#C8CCD0", rough=0.15); barrel = lw_paint("ram barrel", "#2A2A2C", rough=0.4)
    K.cyl("digger ram barrel", (S2_BOOM.x + 0.55, S2_BOOM.y, S2_BOOM.z - 0.27), 0.085, 0.9, barrel, rot=(0, math.pi / 2, 0), parent=boom)
    K.cyl("digger stick ram", (S2_BOOM.x + S2_L1 - 0.9, S2_BOOM.y, S2_BOOM.z + 0.28), 0.06, 1.5, chrome, rot=(0, math.pi / 2, 0), parent=boom)
    K.cyl("digger stick ram barrel", (S2_BOOM.x + S2_L1 - 1.4, S2_BOOM.y, S2_BOOM.z + 0.28), 0.08, 0.8, barrel, rot=(0, math.pi / 2, 0), parent=boom)
    for k_ in range(3):                                   # the hoses run up the boom
        K.cyl("digger hose", (S2_BOOM.x + S2_L1 / 2, S2_BOOM.y + 0.15, S2_BOOM.z + 0.12 + 0.04 * k_), 0.018, S2_L1 * 0.9, lw_rubber("hose black", "#121212", rough=0.6), rot=(0, math.pi / 2, 0), parent=boom)
    stick = K.empty("digger stick", (S2_BOOM.x + S2_L1, S2_BOOM.y, S2_BOOM.z), parent=boom)
    K.cyl("digger bucket ram", (S2_BOOM.x + S2_L1 + 0.9, S2_BOOM.y, S2_BOOM.z + 0.2), 0.05, 1.3, chrome, rot=(0, math.pi / 2, 0), parent=stick)
    K.box("digger stick arm", (S2_BOOM.x + S2_L1 + S2_L2 / 2, S2_BOOM.y, S2_BOOM.z), (S2_L2, 0.2, 0.24), yel, bev=0.04, parent=stick)
    bucket = K.empty("digger bucket", (S2_BOOM.x + S2_L1 + S2_L2, S2_BOOM.y, S2_BOOM.z), parent=stick)
    bx = S2_BOOM.x + S2_L1 + S2_L2
    K.box("digger bucket back", (bx, S2_BOOM.y, S2_BOOM.z - 0.32), (0.08, 0.7, 0.64), dark, bev=0.02, parent=bucket)
    K.box("digger bucket floor", (bx + 0.25, S2_BOOM.y, S2_BOOM.z - 0.62), (0.5, 0.7, 0.06), dark, bev=0.02, parent=bucket)
    for sy in (-0.35, 0.35):
        K.box("digger bucket side", (bx + 0.2, S2_BOOM.y + sy, S2_BOOM.z - 0.4), (0.45, 0.04, 0.5), dark, bev=0.01, parent=bucket)
    for k in range(5):
        K.box("digger bucket tooth", (bx + 0.52, S2_BOOM.y - 0.28 + 0.14 * k, S2_BOOM.z - 0.62), (0.1, 0.05, 0.04), dark, bev=0.01, parent=bucket)
    return dict(boom=boom, stick=stick, bucket=bucket, sticks=sticks, bx=bx)


def s2_truck(name, col="#E3A112"):
    """a yellow dump truck facing +Y: a cab, a raised-sided steel bed full of black rock, six wheels, headlights on"""
    root = K.empty(name, (0, 0, 0))
    yel = lw_paint(f"truck paint {col}", col, rough=0.45); dark = lw_metal("truck steel", "#2E2E30", rough=0.55)
    tyre = lw_rubber("car tyre", "#141414", rough=0.8)
    K.box(name + " cab", (0, 1.3, 1.0), (1.3, 0.9, 1.0), yel, bev=0.06, parent=root)
    K.box(name + " windscreen", (0, 1.76, 1.2), (1.1, 0.02, 0.4), K.mat("car glass", "#1E262C", rough=0.05, metal=0.3), bev=0.0, parent=root)
    K.box(name + " chassis", (0, 0.0, 0.5), (1.2, 3.4, 0.25), dark, bev=0.02, parent=root)
    K.box(name + " bed", (0, -0.4, 1.05), (1.45, 2.4, 0.85), yel, bev=0.05, parent=root)
    rk = lw_noise("wall rock", "#2A2522", "#5A4E44", scale=7, rough=0.95, bump=1.0, detail=8)
    rnd = lw_random.Random(len(name))
    for k in range(9):
        K.sph(name + " load", (rnd.uniform(-0.5, 0.5), rnd.uniform(-1.4, 0.6), 1.5), rnd.uniform(0.18, 0.3), rk, scale=(1, 1, 0.6), seg=10, ring=6, parent=root)
    for y in (-1.3, -0.5, 1.2):
        for sx in (-1, 1):
            K.cyl(name + " wheel", (sx * 0.66, y, 0.38), 0.38, 0.28, tyre, rot=(0, math.pi / 2, 0), v=24, parent=root)
    for sx in (-1, 1):
        K.box(name + " headlight", (sx * 0.45, 1.76, 0.7), (0.2, 0.02, 0.12), lw_emit("headlight", "#FFF6E0", 22.0), bev=0.01, parent=root)
    lw_local(root)
    return root


def s2_clear(x, y):
    """where no loose rock may lie: the house, the digger and its tracks' run, his own spot and the lens's line to him"""
    hx, hy, hw, hd = S2_HOUSE
    return (abs(x - hx) < hw / 2 + 0.35 and abs(y - hy) < hd / 2 + 0.6) or (abs(x - S2_DIG.x) < 1.3 and -0.4 < y - S2_DIG.y < 2.4 + 1.6) \
        or (abs(x - S2_DIG.x) < 1.2 and abs(y - S2_DIG.y) < 1.7) or (x - S2_P0[0]) ** 2 + (y - S2_P0[1]) ** 2 < 0.45 or (abs(x - S2_P0[0] - 0.2) < 0.5 and -3.4 < y < S2_P0[1])


def place_wall_works():
    """THE WALL WORKS by day: the trodden black gravel of the works, the earth wall's black rock face rising across the
    whole frame, a town house at its foot (the wall stands well over its roof), other diggers at work along it, the
    eruption's smoke beyond the crest."""
    rnd = lw_random.Random(21)
    lw_grid("works ground", -26, 26, -14, 22, 90, 80, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.2, tint="#4E4A45", name="works rock ground", rough=0.95))   # REAL black lava rock, trodden (Poly Haven)
    wall = earth_wall("earth wall", [(x, S2_WALL_Y + 0.006 * x * x) for x in range(-30, 32, 2)], h=S2_WALL_H, crest=1.4, base=S2_BASE, seed=4)
    lava_rock("works rock", 70, (-12, 12, -6, S2_FOOT - 0.2), s2_ground_z, seed=6, r=(0.08, 0.26), avoid=s2_clear)
    face = lava_rock("wall face rock", 160, (-12, 12, S2_FOOT + 0.2, S2_EDGE - 0.2), lambda x, y: s2_face_z(y - 0.006 * x * x), seed=17, r=(0.1, 0.32))   # the black rock it is built of, tumbled down its face
    hx, hy, hw, hd = S2_HOUSE
    house = town_house("town house by the wall", (hx, hy, 0.0), yaw=0.0, w=hw, d=hd, storeys=1, base=0.3, roof="#B8352B", wall="#F1EEE6", seed=5)   # the scale: a whole house, and the wall stands far over its roof
    blue = lw_paint("flag blue", "#02529C", rough=0.7); white = lw_paint("flag white", "#F4F4F0", rough=0.7); red = lw_paint("flag red", "#DC1E35", rough=0.7)
    c = Vector((hx + hw / 2 - 0.2, hy - hd / 2 - 0.5, 1.3))                       # ICELAND: the flag on a pole off the house front
    for nm, off_, size, m in (("field", (0, 0, 0), (0.6, 0.012, 0.42), blue), ("white bar", (-0.09, -0.002, 0), (0.12, 0.016, 0.42), white), ("white band", (0, -0.002, 0), (0.6, 0.016, 0.12), white),
                              ("red bar", (-0.09, -0.004, 0), (0.06, 0.02, 0.42), red), ("red band", (0, -0.004, 0), (0.6, 0.02, 0.06), red)):
        K.box(f"icelandic flag {nm}", tuple(c + Vector(off_)), size, m, bev=0.0)
    K.cyl("flag pole", (c.x - 0.31, c.y + 0.25, 1.3), 0.014, 0.55, lw_metal("flag pole", "#D8D8D4", rough=0.4), rot=(math.pi / 2, 0, 0), v=10)
    far = []
    for k, (x, a_, b_) in enumerate(((-9.0, 0.75, -1.9), (10.5, 0.9, -2.1))):   # other diggers at work along the wall: built, not boxes
        before = set(bpy.data.objects)
        Dk = s2_digger(knob_pts=())
        rg = K.empty(f"far digger {k}", (0, 0, 0))
        for o in set(bpy.data.objects) - before:
            if o.parent is None and o is not rg: o.parent = rg
        rg.location = (x, S2_FOOT - 2.6 + 0.006 * x * x, 0.0); rg.rotation_euler = (0, 0, math.radians(90 + (-12 if x < 0 else 12)))
        Dk["boom"].rotation_euler = (0, -a_, 0); Dk["stick"].rotation_euler = (0, -b_, 0)
        far.append((Dk, a_, b_, k))
    lava_rock("works rubble", 420, (-7.0, 7.0, -3.5, 6.0), s2_ground_z, seed=29, r=(0.05, 0.24), moss=0.0, avoid=s2_clear)     # the black rock spilled across the works as it is trucked to the wall
    lava_rock("works grit near the lens", 260, (S2_P0[0] - 1.6, S2_P0[0] + 2.0, S2_P0[1] - 2.2, S2_P0[1] + 1.2), s2_ground_z, seed=31, r=(0.02, 0.07), moss=0.0,
              avoid=lambda x, y: (x - S2_P0[0]) ** 2 + (y - S2_P0[1]) ** 2 < 0.2)     # the trodden works underfoot, right up to the lens (EMPTY: a bare dark foreground)
    lava_rock("works stones", 240, (-3.5, 3.5, -3.0, 3.0), s2_ground_z, seed=23, r=(0.025, 0.08), avoid=s2_clear)     # the trodden works: stones and grit underfoot
    for k, (x, y, r) in enumerate(((-5.6, -1.2, 0.3), (4.4, -2.6, -0.2), (7.4, 2.2, 0.1))):      # REAL props of a works (Poly Haven): barriers, bags of cement, drums
        ph_model("concrete_road_barrier", (x, y, s2_ground_z(x, y)), rot=(0, 0, r), scale=0.5, name=f"road barrier {k}")
    for k, (x, y) in enumerate(((-6.4, 1.6), (-6.0, 1.9), (-6.2, 2.3))):
        ph_model("cement_bag", (x, y, s2_ground_z(x, y) + 0.06 * k), rot=(0, 0, 0.4 * k), scale=0.5, name=f"cement bag {k}")
    for k, (x, y) in enumerate(((5.2, 0.6), (5.6, 0.9))):
        ph_model("barrel_03", (x, y, s2_ground_z(x, y)), rot=(0, 0, k), scale=0.5, name=f"fuel drum {k}")
    for k, x in enumerate((5.2,)):   # the eruption's smoke beyond the wall
        lw_steam(f"eruption smoke {k}", (x, S2_WALL_Y + 13.0 + 2 * k, S2_WALL_H - 1.5), w=4.5, h=14.0, seed=5.1 * k + 2, col=(0.4, 0.38, 0.38),
                 dens=2.2, lean=(0.6, 0.3), rise=1.0, grow=False, t_end=12.0)

    def light():
        k = iceland_light(sun_elev=30, sun_az=-140, sun=3.0, sky=0.4, haze=1.4)                  # the world's one bright day (the reset, 2026-11-25: no dusk, no night)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))   # the same REAL sky as the other beats (Poly Haven)
        return k
    return dict(light=light, wall=wall, far=far, house=house, face=face)


def shot2():
    """THE WALL GOES UP. Wide and low on the works, tipped up: him at the left with a boulder over his head, the town
    house behind him, the wall low beyond it. Two boulders go back over his shoulder and the wall rises behind the
    house until it stands far over the roof."""
    T_R1 = 0.5; T_L1 = 0.88; T_GRAB = 0.84; T_R2 = 1.2; T_L2 = 1.95; T_LOOK = 1.62; T_GRIN = 2.65
    W = lw_win
    P = place_wall_works()
    light = P["light"]
    data = load_data()
    P0 = Vector((S2_P0[0], S2_P0[1], s2_ground_z(*S2_P0))); YAW0 = math.radians(34)
    data.place(P0.x, P0.y, math.degrees(YAW0)); data._kobj(0.0, loc=tuple(P0))
    kit = hard_hat(data)
    # ---- the wall: it stands low behind the house and RISES as his boulders land on it
    root = P["wall"]["root"]
    bpy.context.view_layer.update()
    for o in P["face"]:
        o.parent = root; o.matrix_parent_inverse = root.matrix_world.inverted()
    O1, O2 = -(S2_WALL_H - 1.3), -(S2_WALL_H - 5.1)
    def off(t):
        return O1 + (O2 - O1) * ease(min(1.0, max(0.0, (t - T_L1) / 0.34))) + (0.0 - O2) * ease(min(1.0, max(0.0, (t - T_L2) / 0.32)))
    for f in range(1, NF + 1):
        root.location = (0, 0, off((f - 1) / FPS)); root.keyframe_insert("location", frame=f)
    dust = [lw_steam(f"wall dust {k}", (P0.x + 1.6 + 2.2 * k, S2_FOOT - 0.5, 0.1), w=3.2, h=2.6, seed=3.7 + k, col=(0.72, 0.68, 0.62), dens=10.0, lean=(0.1, -0.1), rise=0.9,
                     keys=[(T_L2 + 0.02, 0.0), (T_L2 + 0.35, 1.0), (DUR + 0.5, 0.8)], t_end=DUR + 1.0) for k in range(2)]      # dust rolling at its foot as it goes up
    fill = lw_area("works fill", (P0.x + 0.5, P0.y - 1.5, 3.5), (P0.x + 0.5, P0.y + 0.5, 0.0), 0.0, 5, col=(0.9, 0.95, 1.0))     # the sky's light the risen wall takes off the ground, given back: one grade
    lw_area("works top light", (P0.x + 0.1, P0.y - 0.25, 2.2), (P0.x, P0.y - 0.1, 0.0), 240.0, 0.5, col=(0.92, 0.96, 1.0))   # his contact shadow on the rock, the same in every still
    for f in range(1, NF + 1):
        fill.data.energy = 110.0 * (1 - off((f - 1) / FPS) / O1); fill.data.keyframe_insert("energy", frame=f)
    # ---- his body: a boulder over his head, the heave back, down for the next one, the heave, round to look, to us
    def body(t):
        p = P0.copy()
        dip = 0.06 * W(t, T_R1 + 0.1, 0.18) * (1 - W(t, T_GRAB + 0.03, 0.14)); p.z -= dip   # down for the next boulder
        p.x += 0.07 * W(t, T_LOOK, 0.35) - 0.05 * W(t, T_GRIN - 0.1, 0.35)
        st = W(t, T_L2 - 0.2, 0.3); p.y -= 0.17 * st; p.z = s2_ground_z(p.x, p.y) - dip + 0.03 * math.sin(math.pi * st)       # a step back from it as it goes up
        yaw = YAW0 + math.radians(44) * W(t, T_L2 - 0.2, 0.3) * (1 - W(t, T_GRIN - 0.2, 0.4)) - math.radians(14) * W(t, T_GRIN - 0.2, 0.4)   # round to look up at it, then to us
        return p, yaw, dip
    for f in range(1, NF + 8):
        t = (f - 1) / FPS; p, yaw, dip = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
        if dip > 0.002: data._plant_feet_here(t)
    heave = lambda t, t_r: -22 * W(t, t_r - 0.22, 0.14) * (1 - W(t, t_r - 0.04, 0.1))            # back as he winds up, forward through the throw
    lw_layer(data, "spine", lambda t: (heave(t, T_R1) + heave(t, T_R2) + 36 * W(t, T_R1 + 0.1, 0.18) * (1 - W(t, T_GRAB + 0.02, 0.14)) + 14 * W(t, T_R2 - 0.03, 0.1) * (1 - W(t, T_R2 + 0.15, 0.15))
                                       + 8 * W(t, T_L2, 0.2) * (1 - W(t, T_GRIN - 0.2, 0.3)), 0, 0), 0, DUR + 0.4)
    OVER = lambda sg: ((-58, 0, -sg * 6), (-38, 0, sg * 18), (0, 0, 0))                       # the boulder on his two hands in front of his chest
    BACK = lambda sg: ((-30, 0, -sg * 6), (-30, 0, sg * 16), (0, 0, 0))                       # the wind-up: down to his belt
    FLUNG = lambda sg: ((0, 0, -sg * 100), (0, 0, -sg * 40), (0, 0, 0))                       # the throw's end: both arms flung up in a V beside his head
    WIDE = lambda sg: ((-10, 0, -sg * 68), (-28, 0, -sg * 22), (0, 0, 0))                       # both hands thrown out
    DOWN = lambda sg: ((-38, 0, -sg * 4), (-10, 0, sg * 8), (0, 0, 0))                         # down to the boulder at his feet
    HANG = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    def pose(t, P_):
        for sd in "LR":
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), P_(-1 if sd == "L" else 1)): data._k(bn, t, rot=r)
    for t_, P_ in ((0.0, OVER), (0.14, OVER), (T_R1 - 0.16, BACK), (T_R1 + 0.1, FLUNG), (T_R1 + 0.3, DOWN), (T_GRAB, DOWN), (T_GRAB + 0.1, BACK), (T_R2 + 0.06, FLUNG), (T_R2 + 0.3, FLUNG), (T_LOOK + 0.34, HANG)):
        pose(t_, P_)
    TOP = Vector((P0.x + 2.4, S2_EDGE + 0.3, S2_WALL_H + 0.3))
    CAM0 = P0 + Vector((0.06, -1.3, 0.42)); LOOK0 = CAM0 + Vector((0.225, 0.974, 0.21))
    data.look_at(CAM0, 0.0, max_yaw=50, max_pitch=30, blend=0.0)
    data.look_at(TOP + Vector((0, 0, 4.0)), T_L2 + 0.05, max_yaw=48, max_pitch=50, blend=0.2)                       # up at it over his shoulder as it towers
    data.look_at(CAM0, T_GRIN - 0.1, max_yaw=55, max_pitch=40, blend=0.3)
    data.expression("determined", 0.0, T_LOOK, blend=0.15)
    pose(T_L2 + 0.02, HANG)
    pose(T_L2 + 0.3, WIDE); pose(T_GRIN - 0.25, WIDE)                                           # both hands thrown out as it towers over him
    data.expression("surprised", T_L2, T_GRIN - 0.2, blend=0.12)
    FIST = lambda sg: ((0, 0, -sg * 94), (0, 0, -sg * 44), (0, 0, 0))                          # a fist in the air, to us
    for bn, r in zip(("arm.R", "fore.R", "hand.R"), FIST(1)): data._k(bn, T_GRIN + 0.3, rot=r); data._k(bn, DUR + 0.5, rot=r)
    for bn, r in zip(("arm.L", "fore.L", "hand.L"), HANG(-1)): data._k(bn, T_GRIN + 0.3, rot=r); data._k(bn, DUR + 0.5, rot=r)
    data.expression("happy", T_GRIN - 0.15, DUR + 1.0, blend=0.25)
    data.finish()
    # ---- the boulders ride his hands, fly back over the house and land on the wall's crest
    rk = lw_noise("wall rock", "#151413", "#3C3834", scale=7, rough=0.95, bump=1.0, detail=8)
    rnd = lw_random.Random(4); R_ = 0.19; BIG = 1.0
    hands = {}; fwd = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        hands[f] = (data.arm.matrix_world @ data.pb["fore.L"].tail + data.arm.matrix_world @ data.pb["fore.R"].tail) / 2 + data.forward() * 0.11; fwd[f] = data.forward().copy()
    rocks = []
    for k, (t_g, t_r, t_l, lx) in enumerate(((-1.0, T_R1, T_L1, 1.7), (T_GRAB, T_R2, T_L2, 2.9))):
        o = lw_block(f"boulder {k}", (0, 0, 0), R_, rk, rnd, squash=0.85); rocks.append(o)
        o.cycles.use_motion_blur = False                                                          # a boulder in the air, not a smear, on the board's still
        rest = Vector((P0.x + 0.28, P0.y - 0.16, P0.z + R_ * 0.5))                             # the second one waits at his feet
        spin = rnd.uniform(4, 7); s0 = tuple(o.scale)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            held = hands[f] + Vector((0, 0, R_ * 0.6 + 0.02))
            if t_g > 0 and t < t_r:
                g_ = BIG; o.scale = tuple(v * g_ for v in s0); o.keyframe_insert("scale", frame=f)   # it is a big one: over his hat it fills his two hands
            if t < t_g - 0.12: p = rest
            elif t < t_g: p = rest.lerp(hands[f], (t - (t_g - 0.12)) / 0.12)
            elif t < t_r: p = held if t_g < 0 else hands[f].lerp(held + Vector((0, 0, 0.0)), min(1.0, (t - t_g) / 0.15))   # up over his hard hat, held there, then away
            else:
                u = min(1.0, (t - t_r) / (t_l - t_r)); p0 = hands[F(t_r)] + Vector((0, 0, R_ * 0.6 + 0.02 + 0.0))
                land = Vector((P0.x + lx, S2_EDGE + 0.1, S2_WALL_H + off(t) + R_ * 1.2))
                g_ = (BIG if t_g > 0 else 1.0) * (1.0 + 1.6 * u) / (1.0 + (BIG - 1.0) * u if t_g > 0 else 1.0); o.scale = tuple(v * g_ for v in s0); o.keyframe_insert("scale", frame=f)   # it lands on the crest's edge, a boulder you can still see from here
                p = p0.lerp(land, u * u); p.x = p0.x + (land.x - p0.x) * u ** 0.7; p.z = p0.z + (land.z - p0.z) * u + 4 * 0.9 * u * (1 - u)
                o.rotation_euler = (spin * min(t - t_r, t_l - t_r), 0.5 * spin * min(t - t_r, t_l - t_r), 0)
            o.location = p; o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: WIDE and low on the works in front of him, tipped up: him at the left, the house behind him, the
    # wall beyond it, to its crest when it has risen
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(0.29, 0.56), height=0.375, t=0.0)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=24.0, fstop=22.0)
    # the eruption it is built against: lava fountains far off beyond it, on the lens's line through the gap beside the house:
    # in sight over the low wall, hidden when it has risen
    hx_, hy_, hw_, hd_ = S2_HOUSE
    gap = Vector((hx_ + hw_ / 2 + 0.9, S2_FOOT, 0.0)); ray = (gap - Vector((CAM.x, CAM.y, 0.0))).normalized()
    fp = gap + ray * 15.0
    far_f = [lw_fire_column(f"far fountain {k}", (fp.x + 1.3 * (k - 1), fp.y + 0.6 * k, 0.0), w=2.2, h_fire=12.0 + 2.0 * (k % 2), h_smoke=3.0, lean=(0.1, 0.0), t_end=DUR + 1.0,
                            seed=2.1 * k + 0.4, fire=34.0, smoke_d=1.0) for k in range(3)]
    lw_point("far fountain light", (fp.x, fp.y - 2.0, 3.0), 3000.0, col=(1.0, 0.45, 0.12), r=1.5)
    print("S2 FAR FOUNTAINS at", tuple(round(v, 2) for v in fp), flush=True)
    lw_cut(cam, lambda t: (CAM, LOOK, data.pos() + Vector((0, 0, 0.6))), lambda t: (CAM, LOOK, data.pos()), -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("boulder",), cutaway=None,
                boxes=[],
                conseq=[("he hurls the black boulders up over his head at the wall", lambda: rocks[:1], 0.0, T_R1 + 0.08, {"whole": False}),
                        ("the rock wall rises behind the house until it stands far over the roof", lambda: [P["wall"]["body"]], T_L1, DUR, {"whole": False})])
