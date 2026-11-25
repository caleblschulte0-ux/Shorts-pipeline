"""BEAT 2: "So Iceland built walls of rock three stories tall, with a hundred diggers and trucks working day and night."

The wall works outside the town in the blue evening, the earth wall's black face rising behind him, three stories of
rock, floodlights along its foot, other diggers at work along it. The driver stands in front of it with his digger's
remote control pack on his chest, both hands on its two sticks: he shoves them forward and beside him the digger's big
arm swings up the face with its bucket full of black rock and tips it over the crest, the rock tumbling back down the
face in a burst of dust and bouncing past him; he ducks, then grins at us; he hauls the sticks back and the arm swings
down for the next bucketful; the floodlights blaze on as night falls."""

S2_DECK = 0.52                          # the digger's deck
S2_BOOM = Vector((0.95, 0.42, 1.05))    # the boom's foot pin, in the digger's own frame (facing its +X)
S2_L1, S2_L2 = 3.4, 3.0                 # boom and stick
S2_DIG = Vector((-3.0, 1.3, 0.0))      # the digger, behind him on his left, facing +Y (the wall): its bucket reaches to his side
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


def place_wall_works():
    """THE WALL WORKS in the blue evening: the trodden gravel of the works, the earth wall's black face rising across the
    whole frame, floodlight masts along its foot, other diggers at work along it, the eruption's smoke over the crest."""
    rnd = lw_random.Random(21)
    lw_grid("works ground", -26, 26, -14, 22, 90, 80, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.2, tint="#3A3632", name="works rock ground", rough=0.95))   # REAL black lava rock, trodden (Poly Haven)
    wall = earth_wall("earth wall", [(x, S2_WALL_Y + 0.006 * x * x) for x in range(-30, 32, 2)], h=S2_WALL_H, crest=1.4, base=S2_BASE, seed=4)
    lava_rock("works rock", 90, (-12, 12, -6, S2_FOOT - 0.2), s2_ground_z, seed=6, r=(0.08, 0.26),
              avoid=lambda x, y: (-4.2 < x < -1.6 and 0.3 < y < 4.2) or (-0.8 < x < 1.0 and -1.8 < y < 1.2) or (x + 6.5) ** 2 + (y + 4.0) ** 2 < 9.0 or (6.6 < x < 9.0 and -3.4 < y < 1.0))
    lava_rock("wall face rock", 160, (-12, 12, S2_FOOT + 0.2, S2_EDGE - 0.2), lambda x, y: s2_face_z(y - 0.006 * x * x), seed=17, r=(0.1, 0.32))   # the black rock it is built of, tumbled down its face
    masts = []
    for k, x in enumerate((-7.5, -4.2, 2.6, 6.0)):
        y = S2_FOOT - 0.5 + 0.006 * x * x
        K.cyl("floodlight mast", (x, y, 2.6), 0.06, 5.2, lw_metal("mast steel", "#8A8E92"), v=12)
        # board round 3: "white boxes on poles that cast no light". A real floodlight: a dark housing with four hot
        # lamp faces turned down at the works, a cone of light through the dust under it, a pool on the ground
        K.box("floodlight housing", (x, y - 0.02, 5.25), (1.0, 0.24, 0.45), lw_metal("floodlight housing", "#2A2C2E", rough=0.5), bev=0.03)
        K.box("floodlight bar", (x, y + 0.02, 5.0), (1.1, 0.06, 0.06), lw_metal("mast steel", "#8A8E92"), bev=0.01)
        head = None
        for i_, (dx_, dz_) in enumerate(((-0.24, 0.1), (0.24, 0.1), (-0.24, -0.1), (0.24, -0.1))):
            o = K.box("floodlight head", (x + dx_, y - 0.15, 5.25 + dz_), (0.42, 0.03, 0.18), lw_emit(f"floodlight lamp {k}", "#FFF4DC", 0.0), bev=0.01)
            head = head or o
        aim = Vector((0.3 * x, -1.0, 0.0))
        L = lw_area(f"floodlight {k}", (x, y - 0.3, 5.1), tuple(aim), 0.0, 0.8, col=(1.0, 0.95, 0.85))
        beam = bpy.data.meshes.new(f"floodlight beam {k}"); bm = LW_bmesh.new()
        LW_bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=0.25, radius2=2.2, depth=1.0)
        bm.to_mesh(beam); bm.free()
        bmat = bpy.data.materials.get("floodlight dust")
        if not bmat:
            bmat = bpy.data.materials.new("floodlight dust"); bmat.use_nodes = True; nt_ = bmat.node_tree
            nt_.nodes.remove(nt_.nodes["Principled BSDF"]); pv = nt_.nodes.new("ShaderNodeVolumePrincipled")
            pv.inputs["Density"].default_value = 0.006; pv.inputs["Color"].default_value = (1.0, 0.97, 0.9, 1)
            nt_.links.new(pv.outputs[0], nt_.nodes["Material Output"].inputs["Volume"])
        beam.materials.append(bmat)
        bo = lw_link(bpy.data.objects.new(f"floodlight beam {k}", beam)); bo.hide_render = True   # its haze read as a white blob (board): the light carries it
        src = Vector((x, y - 0.3, 5.1)); d_ = (aim - src); ln = d_.length * 0.92
        bo.scale = (1, 1, ln); bo.location = src + d_.normalized() * ln / 2
        bo.rotation_euler = (-d_).to_track_quat('Z', 'Y').to_euler()
        masts.append((head, L))
    far = []
    for k, (x, a_, b_) in enumerate(((-9.0, 0.75, -1.9), (5.6, 0.45, -1.5), (10.5, 0.9, -2.1))):   # other diggers at work along the wall: built, not boxes
        before = set(bpy.data.objects)
        Dk = s2_digger(knob_pts=())
        rg = K.empty(f"far digger {k}", (0, 0, 0))
        for o in set(bpy.data.objects) - before:
            if o.parent is None and o is not rg: o.parent = rg
        rg.location = (x, S2_FOOT - 2.6 + 0.006 * x * x, 0.0); rg.rotation_euler = (0, 0, math.radians(90 + (-12 if x < 0 else 12)))
        Dk["boom"].rotation_euler = (0, -a_, 0); Dk["stick"].rotation_euler = (0, -b_, 0)
        far.append((Dk, a_, b_, k))
    # the eruption beyond the wall reads as its glow along the horizon over the crest
    lava_rock("works rubble", 650, (-7.0, 7.0, -3.5, 6.0), s2_ground_z, seed=29, r=(0.05, 0.24), moss=0.0,     # the black rock spilled across the works as it is trucked to the wall
              avoid=lambda x, y: (x - 0.9) ** 2 + (y - 2.9) ** 2 < 1.2 or (x - 0.05) ** 2 + (y - 0.25) ** 2 < 0.25 or (-4.2 < x < -1.6 and 0.3 < y < 4.6))
    lava_rock("works stones", 240, (-3.5, 3.5, -1.8, 3.0), s2_ground_z, seed=23, r=(0.025, 0.08),     # the trodden works: stones and grit underfoot
              avoid=lambda x, y: (x - 0.05) ** 2 + (y - 0.25) ** 2 < 0.3 or (-4.2 < x < -1.6 and 0.3 < y < 4.6))
    for k, x0 in enumerate((-2.2, -1.5, 1.6, 2.3)):           # the tracks the machines have cut in it
        K.box(f"track rut {k}", (x0 + 0.1 * k, 0.6, 0.006), (0.32, 9.0, 0.01), lw_noise("rut mud", "#2A2622", "#3E3832", scale=30, rough=0.9, bump=1.0, stretch=(1, 6, 1)), bev=0)
    for k, (x, y, r) in enumerate(((-5.6, -1.2, 0.3), (4.4, -2.6, -0.2), (7.4, 2.2, 0.1))):      # REAL props of a works (Poly Haven): barriers, bags of cement, drums
        ph_model("concrete_road_barrier", (x, y, s2_ground_z(x, y)), rot=(0, 0, r), scale=0.5, name=f"road barrier {k}")
    for k, (x, y) in enumerate(((-6.4, 1.6), (-6.0, 1.9), (-6.2, 2.3))):
        ph_model("cement_bag", (x, y, s2_ground_z(x, y) + 0.06 * k), rot=(0, 0, 0.4 * k), scale=0.5, name=f"cement bag {k}")
    for k, (x, y, r) in enumerate(((-1.3, -0.9, 0.3), (1.4, -1.1, 1.1), (-2.4, 0.4, 2.0))):   # worn tyres off the machines, dumped about the works
        ph_model("old_tyre", (x, y, s2_ground_z(x, y)), rot=(math.radians(90) if k == 2 else 0, 0, r), scale=0.9, name=f"works tyre {k}")
    for k, (x, y) in enumerate(((5.2, 0.6), (5.6, 0.9))):
        ph_model("barrel_03", (x, y, s2_ground_z(x, y)), rot=(0, 0, k), scale=0.5, name=f"fuel drum {k}")
    for k, x in enumerate((-7.5, -1.0, 5.5)):   # the eruption's smoke along the whole wall, lit from under by its glow
        lw_steam(f"eruption smoke {k}", (x, S2_WALL_Y + 7.0 + 2 * k, S2_WALL_H - 1.5), w=4.5, h=14.0, seed=5.1 * k + 2, col=(0.22, 0.2, 0.21),
                 dens=2.2, lean=(0.6, 0.3), rise=1.0, grow=False, t_end=12.0)
    K.box("eruption horizon glow", (0, 30, 3.0), (90, 0.5, 6.0), lw_emit("horizon glow", "#FF6A20", 0.8), bev=0)

    def light():
        k = iceland_light(sun_elev=1, sun_az=-40, sun=0.4, sky=0.11, warm=(0.8, 0.72, 1.0), haze=0.35)     # blue evening going to night: the floodlights carry the works
        ph_sky("industrial_sunset_puresky", strength=0.22, rot=math.radians(200))       # a REAL evening sky with its clouds (Poly Haven): not a bare gradient
        return k
    return dict(light=light, wall=wall, masts=masts, far=far)


def shot2():
    """ROUND 7, A CLOSE SHOT (coordinator after board 6: the prop CLOSE, in front of him; no wide). He stands at the
    foot of the wall's black rock face beside his digger's bucket, guiding it in; the bucket heaves up the face full
    of black rock right past him, and a boulder tips off its edge and drops past his raised hand, thumping down at his
    boots in a burst of dust; he jumps back, then grins at us and waves the arm on up; the rest of the load spills off
    the crest and rattles down the face behind him; the floodlights blaze."""
    T_PUSH = 0.05 * DUR; T_SLIP = 0.27 * DUR; T_LAND = T_SLIP + 0.55
    T_TOP = 0.55 * DUR; T_TIP = T_TOP + 0.1; T_TIPPED = T_TIP + 0.5
    T_GRIN = T_LAND + 0.5; T_WAVE = T_GRIN + 0.7
    T_LIGHTS = 0.82 * DUR
    W = lw_win
    P = place_wall_works()
    light = P["light"]
    data = load_data()
    P0 = Vector((S2_DIG.x - S2_BOOM.y + 0.7, S2_FOOT - 0.55, 0.0)); P0.z = s2_ground_z(P0.x, P0.y)
    YAW0 = math.radians(25)                                 # three-quarter to the lens at his front right, the bucket at his right hand
    data.place(P0.x, P0.y, math.degrees(YAW0)); data.arm.location.z = P0.z
    # REACH (round 7): set him so his near shoulder is a hand's reach from the bucket's side plate, which sits 0.39 m
    # off the arm's plane toward him; the bucket starts with that plate at his palm, then lifts under it
    sc.frame_set(1); bpy.context.view_layer.update()
    FW0 = Vector((math.sin(YAW0), -math.cos(YAW0), 0.0))
    shn = min((acts._shoulder(data, s_) for s_ in "LR"), key=lambda v: v.x)
    PLANE_X = S2_DIG.x - S2_BOOM.y
    P0.x += (PLANE_X + 0.39 + 0.02) - (shn.x + FW0.x * 0.13)
    data.place(P0.x, P0.y, math.degrees(YAW0)); data.arm.location.z = P0.z
    sc.frame_set(1); bpy.context.view_layer.update()
    shn = min((acts._shoulder(data, s_) for s_ in "LR"), key=lambda v: v.x)
    HAND0 = shn + FW0 * 0.13 + Vector((0.0, 0.0, -0.06))
    kit = hard_hat(data)
    # ---- the digger: built facing +X at the origin, then set down behind him facing the wall (+Y)
    before = set(bpy.data.objects)
    D = s2_digger(knob_pts=())
    rig = K.empty("digger", (0, 0, 0))
    for o in set(bpy.data.objects) - before:
        if o.parent is None and o is not rig: o.parent = rig
    rig.location = S2_DIG; rig.rotation_euler = (0, 0, math.radians(90))
    def world(px, pz):                                     # a point in the digger's arm plane, in the world
        return Vector((S2_DIG.x - S2_BOOM.y, S2_DIG.y + px, pz))
    # ---- the arm: from the dig at the face's foot beside him, up the face past him to the crest, the tip, back down
    LOW = (HAND0.y + 0.05 - S2_DIG.y, HAND0.z + 0.12); LIFT = (LOW[0] + 0.12, LOW[1] + 0.14); HIGH = (S2_FOOT + 0.9 - S2_DIG.y, S2_WALL_H - 0.4)     # up the face, inside the arm's reach
    T_BACK = 0.8 * DUR
    def path(t):                                           # it lifts slowly beside him under his steadying hand, then heaves up the face
        a_ = ease(min(1.0, max(0.0, (t - T_PUSH) / (T_SLIP - T_PUSH)))); b_ = ease(min(1.0, max(0.0, (t - T_SLIP) / (T_TOP - T_SLIP))))
        x = LOW[0] + (LIFT[0] - LOW[0]) * a_ + (HIGH[0] - LIFT[0]) * b_
        z = LOW[1] + (LIFT[1] - LOW[1]) * a_ + (HIGH[1] - LIFT[1]) * math.sin(b_ * math.pi / 2)
        v = ease(min(1.0, max(0.0, (t - T_BACK) / (DUR + 0.6 - T_BACK))))
        return x + (LIFT[0] + 1.0 - x) * v, z + (2.6 - z) * v
    curl = lambda t: math.radians(-40) * (1 - W(t, T_TIP, 0.3)) + math.radians(85) * W(t, T_TIP, 0.3) * (1 - W(t, T_BACK, 0.4)) - math.radians(30) * W(t, T_BACK, 0.4) \
        + math.radians(14) * W(t, T_SLIP - 0.15, 0.2) * (1 - W(t, T_SLIP + 0.3, 0.3))       # a lurch that spills the boulder over the lip
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; a, b = s2_ik(path(t))
        D["boom"].rotation_euler = (0, -a, 0); D["stick"].rotation_euler = (0, -b, 0); D["bucket"].rotation_euler = (0, curl(t), 0)
        for o in (D["boom"], D["stick"], D["bucket"]): o.keyframe_insert("rotation_euler", frame=f)
    # ---- the load: rock that rides the bucket up, spills on the crest and tumbles back down the face behind him
    rk = lw_noise("wall rock", "#2A2522", "#5A4E44", scale=7, rough=0.95, bump=1.0, detail=8)
    rnd = lw_random.Random(4)
    bk = D["bucket"]; bx = D["bx"]
    load = []
    for k in range(14):
        r = rnd.uniform(0.1, 0.2)
        o = lw_block(f"bucket load rock {k}", (0, 0, 0), r, rk, rnd, squash=0.8)
        load.append((o, Vector((bx + rnd.uniform(0.05, 0.42), S2_BOOM.y + rnd.uniform(-0.28, 0.2), S2_BOOM.z - rnd.uniform(0.25, 0.5))), r))
    rides = {}
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update(); rides[f] = bk.matrix_world.copy()
    rel = lambda local: Vector(local) - Vector((bx, S2_BOOM.y, S2_BOOM.z))
    for o, local, r in load:
        t_go = T_TIP + 0.1 + rnd.uniform(0.0, 0.25); spin = rnd.uniform(-9, 9); a = rnd.uniform(2.6, 3.8)
        dx = -rnd.uniform(0.3, 1.3); stop = rnd.uniform(S2_FOOT - 0.2, S2_FOOT + 0.6)
        p0 = rides[F(t_go)] @ rel(local)
        y_land = min(p0.y, S2_EDGE - 0.2)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < t_go: o.location = rides[f] @ rel(local)
            else:
                s_ = t - t_go; fall = min(1.0, s_ / 0.25)
                y = p0.y + (y_land - p0.y) * fall
                z = p0.z + (s2_face_z(y_land) + r - p0.z) * fall * fall
                if s_ > 0.25:                                # down the face behind him
                    q = s_ - 0.25
                    y = max(stop, y_land - 0.5 * a * q * q)
                    z = (S2_WALL_H if y >= S2_EDGE else s2_face_z(y)) + r * (0.9 + 0.35 * abs(math.sin(10 * q + dx))) + 0.25 * abs(math.sin(4 * q + dx)) * (y < S2_EDGE)
                o.location = (p0.x + dx * min(1.0, s_), y, z); o.rotation_euler = (spin * s_, spin * 0.5 * s_, 0)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f)
    # ---- THE BOULDER: a real lava boulder on the bucket's lip that tips off as it heaves up past him, drops past his
    # raised hand and thumps down at his boots, rolls a turn toward us and stops
    bould = ph_model("boulder_01", (0, 0, 0), scale=0.34, name="boulder off the bucket")
    lip_local = Vector((bx + 0.45, S2_BOOM.y - 0.2, S2_BOOM.z - 0.12))
    p_s = rides[F(T_SLIP)] @ rel(lip_local)
    LANDB = Vector((P0.x - 0.3, P0.y - 0.45, s2_ground_z(P0.x - 0.3, P0.y - 0.45) + 0.05))
    ROLLB = Vector((P0.x - 0.55, P0.y - 0.95, s2_ground_z(P0.x - 0.55, P0.y - 0.95) + 0.05))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t < T_SLIP: q = rides[f] @ rel(lip_local); rot = (0, 0, 0)
        elif t < T_LAND:
            u = (t - T_SLIP) / (T_LAND - T_SLIP); q = p_s.lerp(LANDB, u); q.z = p_s.z + (LANDB.z - p_s.z) * u * u
            rot = (2.5 * u, 1.2 * u, 0)
        else:
            u = ease(min(1.0, (t - T_LAND) / 0.9)); q = LANDB.lerp(ROLLB, u); q.z += 0.12 * math.sin(math.pi * min(1.0, (t - T_LAND) / 0.35)) * (1 - u)
            rot = (2.5 + 4.0 * u, 1.2, 0)
        bould.location = q; bould.rotation_euler = rot
        bould.keyframe_insert("location", frame=f); bould.keyframe_insert("rotation_euler", frame=f)
    dust = [lw_steam("boulder dust", (LANDB.x - 0.55, LANDB.y + 0.2, 0.0), w=0.4, h=1.6, seed=3.7, col=(0.55, 0.5, 0.45), dens=5.0, rise=1.0,
                     lean=(0.0, 0.0), keys=[(T_LAND - 0.05, 0.0), (T_LAND + 0.4, 1.0), (T_LAND + 2.2, 0.45)], t_end=DUR + 1.0)]
    # ---- the trucks: rolling along behind the works
    for k, (x0, v) in enumerate(((12.0, -2.0),)):
        truck = s2_truck(f"dump truck {k}"); truck.rotation_euler = (0, 0, math.radians(90))
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; truck.location = (x0 + v * t, S2_FOOT - 0.55, 0.0); truck.keyframe_insert("location", frame=f)
    parked = s2_truck("dump truck waiting", col="#D99A10"); parked.location = (7.8, -1.2, 0.0); parked.rotation_euler = (0, 0, math.radians(-14))
    for Dk, a_, b_, k in P["far"]:                         # the other diggers keep working: dig, lift, swing back
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; ph = 2 * math.pi * (t / 3.2 + 0.31 * k)
            Dk["boom"].rotation_euler = (0, -(a_ + 0.22 * math.sin(ph)), 0); Dk["stick"].rotation_euler = (0, -(b_ + 0.3 * math.sin(ph + 1.1)), 0)
            Dk["bucket"].rotation_euler = (0, 0.5 * math.sin(ph + 2.0), 0)
            for o in (Dk["boom"], Dk["stick"], Dk["bucket"]): o.keyframe_insert("rotation_euler", frame=f)
    # ---- the floodlights, and a work light on him from the lens's side (board 6: "light it")
    for k, (head, L) in enumerate(P["masts"]):
        L.data.spread = math.radians(50)
        em = head.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; on = 0.75 + 0.25 * W(t, T_LIGHTS + 0.08 * k, 0.2)
            em.default_value = 60.0 * on; em.keyframe_insert("default_value", frame=f)
            L.data.energy = 2600.0 * on; L.data.keyframe_insert("energy", frame=f)
    lw_area("work light on him", (P0.x + 2.2, P0.y - 2.6, 3.2), (P0.x, P0.y, 0.6), 420.0, 1.2, col=(1.0, 0.93, 0.8))
    lw_area("work light on the face", (P0.x + 1.0, P0.y - 4.0, 4.5), (P0.x - 0.6, S2_FOOT + 1.2, 2.2), 900.0, 2.5, col=(1.0, 0.92, 0.78))
    sk = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
    for f in range(1, NF + 1, 3):
        t = (f - 1) / FPS; sk.default_value = 0.16 * (1 - 0.3 * t / DUR); sk.keyframe_insert("default_value", frame=f)
    # ---- his body: guiding it in, the jump back from the boulder, the grin, waving it on up
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p = P0.copy()
        p.x += 0.3 * W(t, T_LAND - 0.45, 0.5)                                     # he jumps clear of where it will land
        p.y += 0.06 * W(t, T_LAND - 0.45, 0.5)
        p.z += 0.09 * math.sin(math.pi * min(1.0, max(0.0, (t - T_LAND + 0.45) / 0.5))) + 0.03 * lw_kick(t - T_LAND, 0.15)
        p.y += 0.14 * W(t, 0.2, 0.6) * (1 - W(t, T_SLIP - 0.3, 0.4))            # he walks up with the bucket as it lifts
        p.x -= 0.07 * W(t, 0.05, 0.3) * (1 - W(t, 0.55, 0.3))                  # a shoulder into the bucket to start it
        p.z += 0.03 * W(t, 0.6, 0.3) * (1 - W(t, 1.0, 0.3))                     # up on his toes to steady it
        p.x -= 0.12 * W(t, T_WAVE, 0.5)                                            # and steps in again to wave it on
        p.z += 0.03 * lw_kick(t - T_GRIN, 0.2) + 0.03 * abs(math.sin(math.pi * (t - T_WAVE) / 0.45)) * W(t, T_WAVE, 0.3) * (1 - W(t, DUR - 0.3, 0.3))
        yaw = YAW0 + math.radians(18) * W(t, T_PUSH, 0.6) * (1 - W(t, T_SLIP - 0.2, 0.3)) - math.radians(14) * W(t, T_GRIN - 0.2, 0.4) \
            + math.radians(16) * W(t, T_WAVE, 0.5) * (1 - W(t, T_LIGHTS, 0.5)) + math.radians(14) * math.sin(2 * math.pi * (t - T_WAVE) / 0.9) * W(t, T_WAVE, 0.3) * (1 - W(t, DUR - 0.3, 0.3))
        data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (10 * W(t, T_PUSH, 0.45) * (1 - W(t, T_SLIP - 0.1, 0.3)) - 16 * W(t, T_SLIP, 0.25) * (1 - W(t, T_GRIN - 0.1, 0.4))
                                       - 8 * W(t, T_WAVE, 0.4) * (1 - W(t, T_LIGHTS, 0.5)), 0, 6 * math.sin(2 * math.pi * (t - T_GRIN) / 0.9) * W(t, T_GRIN, 0.3) * (1 - W(t, T_WAVE, 0.3))), 0, DUR + 0.4)
    sc.frame_set(F(T_SLIP)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)
    near_b, far_b = sides[0], sides[1]                      # the hand toward the bucket (left of him) and the other
    # the bucket hand: guiding it in ("come on, up"), up flat as the boulder drops past it, then waving the arm on up
    NK = [(T_SLIP - 0.25, (0.1, 0.16, 0.05)),
          (T_SLIP + 0.05, (0.1, 0.17, 0.15)), (T_LAND + 0.1, (0.09, 0.18, 0.15)), (T_GRIN, (0.07, 0.12, -0.04))]
    t_ = T_WAVE; k_ = 0
    while t_ < DUR - 0.3:
        NK.append((t_, (0.1, 0.16, 0.16) if k_ % 2 == 0 else (0.12, 0.17, 0.07))); t_ += 0.45; k_ += 1
    NK += [(DUR + 0.4, (0.1, 0.12, 0.12))]
    side_local = Vector((bx + 0.22, S2_BOOM.y - 0.39, S2_BOOM.z - 0.32))   # the bucket's side plate, the face toward him
    nk_fn = lw_hand(data, near_b, NK)
    def near_path(t):                                       # ONE job: his palm on the bucket's side, steadying it up; then up flat
        q = rides[min(NF, max(1, F(t)))].translation + Vector((0.41, -0.05, -0.12))     # the bucket's side plate by its pin (the arm turns about world X: its x offset holds)
        return q.lerp(nk_fn(t), W(t, T_SLIP - 0.25, 0.25))
    data.reach(near_b, near_path, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    FK = [(0.0, (0.07, 0.1, -0.08)), (T_SLIP - 0.1, (0.08, 0.1, -0.06)), (T_SLIP + 0.15, (0.1, 0.12, 0.08)), (T_LAND + 0.2, (0.08, 0.13, 0.06)),
          (T_GRIN + 0.1, (0.12, 0.08, 0.1)), (T_GRIN + 0.5, (0.07, 0.1, -0.08)), (T_LIGHTS, (0.07, 0.1, -0.08)), (T_LIGHTS + 0.4, (0.08, 0.15, 0.08)), (DUR + 0.4, (0.08, 0.15, 0.06))]
    data.reach(far_b, lw_hand(data, far_b, FK), 0.0, DUR + 0.3, lead=0.4, back=None, elbow_out=0.35)
    # ---- face and head
    BK = lambda t: world(*path(t))
    CAM0 = P0 + Vector((0.55, -2.6, 0.55)); LOOK0 = P0 + Vector((-0.8, 3.2, 1.5))
    data.look_at(BK(0.0), 0.0, max_yaw=60, max_pitch=40, blend=0.0)
    data.look_at(BK(T_SLIP - 0.3), T_PUSH + 0.3, max_yaw=60, max_pitch=60, blend=0.4)
    data.look_at(LANDB, T_SLIP + 0.1, max_yaw=60, max_pitch=50, blend=0.15)
    data.look_at(CAM0, T_GRIN - 0.1, max_yaw=55, max_pitch=40, blend=0.3)
    data.look_at(BK(T_TOP), T_WAVE + 0.1, max_yaw=50, max_pitch=60, blend=0.35)
    data.look_at(CAM0, T_LIGHTS + 0.05, max_yaw=55, max_pitch=30, blend=0.3)
    data.expression("determined", 0.0, T_SLIP - 0.05, blend=0.2)
    data.expression("alarmed", T_SLIP, T_GRIN - 0.1, blend=0.12)
    data.expression("happy", T_GRIN, T_LIGHTS, blend=0.2)
    data.expression("pleased", T_LIGHTS + 0.1, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: CLOSE at his front right, a medium lens a little below his eye: him and the bucket beside him, the
    # black rock face filling the frame behind them, the boulder dropping past his raised hand
    CAM, LOOK = compose.frame_data(data, CAM0, LOOK0, 27.0, face_at=(0.64, 0.42), height=0.36, t=T_SLIP)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=27.0, fstop=11.0)
    trk = lambda t: Vector((0.75 * (0.3 * W(t, T_LAND - 0.45, 0.5) - 0.12 * W(t, T_WAVE, 0.5)), 0.0, 0.0))   # the lens keeps him in, bucket on his left
    lw_cut(cam, lambda t: (CAM + trk(t) + Vector((-0.08, 0.1, 0.0)) * ease(t / DUR), LOOK + trk(t), data.pos() + Vector((0, 0, 0.6))),
           lambda t: (CAM + trk(t), LOOK + trk(t), data.pos()), -1.0, -1.0, 27.0, 27.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("digger",), cutaway=None,
                boxes=[],
                conseq=[("the digger's bucket heaves up the wall's face past him full of black rock", lambda: meshes([D["bucket"]]), T_PUSH, T_SLIP + 0.4, {"whole": False, "moves": True}),
                        ("a boulder tips off the bucket's edge and drops past his raised hand, thumping down at his boots in dust", lambda: meshes([bould]), T_SLIP, T_LAND + 0.9, {"whole": False, "moves": True})])
