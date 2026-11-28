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
S2_SLOPE = 3.5 # (same: a sloped, rubbly bank, not a vertical slab) # (r2zf pre-flight: "the wall only a little above the roof": a steeper face brings its crest nearer the lens)                          # (w2b: a shallow face put its top 6 m back, barely over the ridge) a steep face of piled boulders
S2_H = 8.0                              # the finished wall: from this low lens its top stands well over the house's ridge
S2_HOUSE = (-1.75, 1.1, 3.2, 2.6)    # (coordinator, after r3d: shot 4's real house size: 1.2 m read as a toy, so the lens stands back 5 m) # (coordinator, r2zh: a CENTRE GAP for the digger: the house takes the right ~35%, its gable end to us)         # (coordinator, r2y: composition) the house: centre x, y, width, depth; the right half of the frame, just clear of the wall's foot (y 0)
S2_P0 = (0.35, 10.35)                   # Data: the left foreground, 1.65 m from the lens (r3f pre-flight CONSEQUENCE: "the wall small, Data dominates": he stands back to a third of the frame)
S2_CAM = (0.0, 12.0, 0.55)             # (after r3d: 6 m further back (r3e: at 5 m the house ran off the right edge) for the real-sized house, same height and tilt)
S2_DIG = (1.2, 0.2)                     # (after r3d: side-on along the crest, in the gap left of the house, driving right as it goes; r3c/r3d: end-on its arm read as a pole) # (coordinator, after r2zu: the digger is the CAUSE, bigger: its body on the crest behind the house (r3a: behind his head it hid him and its bucket), its arm out over the gap where the bucket tips at the lip) x, and y off the crest's middle


def s2_base(h):
    return 2.0 * (S2_CREST / 2 + 0.1 + 0.97 * h / S2_SLOPE)


def s2_ground_z(x, y):
    """the town's ground (y > 0); the black field beyond the wall"""
    if y > 0.0: return 0.04 + 0.05 * lw_fbm(x * 0.3, y * 0.3, 19)
    return 0.06 + 0.06 * lw_fbm(x * 0.3, y * 0.3, 19)


def s2_flag(base, pole_h=2.3, fw=0.62, seed=0.0):
    """(coordinator, after r3g "nothing shows Iceland": a real Icelandic flag on a short pole by the house's gable,
    stirring in the wind) the flag: blue field, the red Nordic cross edged in white (18:25), its cloth a fine grid
    waving off the pole"""
    W_, H_ = 250, 180
    img = bpy.data.images.new("iceland flag", W_, H_)
    px = []
    for j in range(H_):
        for i in range(W_):
            u, v = i / W_ * 25.0, j / H_ * 18.0
            if 8.0 <= u < 10.0 or 8.0 <= v < 10.0: c = (0.86, 0.12, 0.21)
            elif 7.0 <= u < 11.0 or 7.0 <= v < 11.0: c = (0.95, 0.95, 0.95)
            else: c = (0.0, 0.32, 0.61)
            px += [c[0] ** 2.2, c[1] ** 2.2, c[2] ** 2.2, 1.0]
    img.pixels = px
    m = bpy.data.materials.new("iceland flag cloth"); m.use_nodes = True; nt = m.node_tree
    bs = nt.nodes["Principled BSDF"]; tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"]); bs.inputs["Roughness"].default_value = 0.8
    fh = fw * 18.0 / 25.0; NX, NY = 16, 11
    vs = [(fw * i / NX, 0.0, fh * j / NY) for j in range(NY + 1) for i in range(NX + 1)]
    fs = [(j * (NX + 1) + i, j * (NX + 1) + i + 1, (j + 1) * (NX + 1) + i + 1, (j + 1) * (NX + 1) + i) for j in range(NY) for i in range(NX)]
    me = bpy.data.meshes.new("iceland flag"); me.from_pydata(vs, [], fs); me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, _, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (x / fw, z / fh)          # the hoist (the cross's short arm) at the pole
    me.materials.append(m)
    o = lw_link(bpy.data.objects.new("iceland flag", me))
    o.location = (base[0], base[1], base[2] + pole_h - fh - 0.02)
    sol = o.modifiers.new("cloth", 'SOLIDIFY'); sol.thickness = 0.006
    sk0 = o.shape_key_add(name="rest", from_mix=False)
    keys = []
    for k in range(8):                                   # eight phases of the ripple as shape keys, crossfaded in turn
        sk = o.shape_key_add(name=f"ripple {k}", from_mix=False)
        for i, vt in enumerate(sk.data):
            x = me.vertices[i].co.x / fw
            vt.co.y = 0.035 * x * math.sin(6.0 * x - 2 * math.pi * k / 8 + seed)
        keys.append(sk)
    period = 1.6
    for f in range(1, NF + 8):
        ph = ((f - 1) / FPS / period * 8) % 8
        for k, sk in enumerate(keys):
            d = min(abs(ph - k), 8 - abs(ph - k))
            sk.value = max(0.0, 1.0 - d); sk.keyframe_insert("value", frame=f)
    pole_m = lw_metal("flag pole", "#D8D8D4")
    K.cyl("flag pole", (base[0], base[1], base[2] + pole_h / 2), 0.018, pole_h, pole_m, v=12)
    K.sph("flag pole knob", (base[0], base[1], base[2] + pole_h + 0.02), 0.03, pole_m, seg=12, ring=8)
    return o


def s2_radio():
    """a black hand-held radio, matte plastic: a rounded body, a ribbed grille, a stubby rubber antenna. Its local Z runs
    up its length from the butt in his fist (lw_ride keys it along his fingers)"""
    root = K.empty("radio", (0, 0, 0))
    body = K.mat("radio plastic", "#151516", rough=0.75)
    rub = K.mat("radio rubber", "#0C0C0D", rough=0.9)
    K.box("radio body", (0, 0, 0.045), (0.042, 0.026, 0.1), body, bev=0.008, parent=root)
    for k in range(4):
        K.box("radio grille", (0, -0.0135, 0.07 + 0.01 * k), (0.03, 0.002, 0.004), rub, bev=0.001, parent=root)
    K.cyl("radio antenna", (0.012, 0.0, 0.12), 0.0055, 0.06, rub, v=10, parent=root)
    K.cyl("radio knob", (-0.011, 0.0, 0.1), 0.006, 0.014, rub, v=10, parent=root)
    root.scale = (2.0, 2.0, 2.0)                               # (r3m: at 0.1 m it hid inside his fist) the size of a real handset in his hand
    return root


def place_wall_works():
    """THE WALL'S FOOT IN TOWN: moss ground and yard stones, one painted tin house with its front to the wall, the wall
    (risen by the shot), the black field beyond it."""
    lw_grid("lava field ground", -60, 60, -60, 0.6, 90, 70, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))
    lw_grid("town ground", -40, 40, 0.0, 30, 80, 40, s2_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock"))     # (coordinator, after board 46083546367: the dark volcanic ground of shots 4-5, not a lawn)
    # (r3o pre-flight HARD DEFECT look: shot 1's ash column read as "a soft, blurry dark vertical smudge ... a flat sprite"; the world
    # block still promises the eruption's dark smoke, CI 46083546367 WEATHER): shot 4's rolling gas column (it passed the board), darker, leaning off on the wind
    lw_steam("eruption smoke", (6.5, -22.0, 2.0), w=6.0, h=22.0, seed=3.3, col=(0.3, 0.29, 0.3), dens=2.5, lean=(0.3, 0.1), rise=1.2, t_end=DUR + 1.0)
    px, py = S2_P0
    hx, hy, hw, hd = S2_HOUSE
    in_house = lambda x, y: abs(x - hx) < hd / 2 + 0.3 and abs(y - hy) < hw / 2 + 0.3
    lava_rock("town yard stones", 520, (-9, 9, 0.2, 14), lambda x, y: s2_ground_z(x, y) + 0.02, seed=78, r=(0.03, 0.1), moss=0.0,     # (after r3d: no moss: it read as flat green discs)
              avoid=lambda x, y: in_house(x, y) or (abs(x - px) < 0.5 and abs(y - py) < 0.5))
    lava_rock("near yard stones", 360, (-3.5, 2.5, py - 1.0, py + 2.0), lambda x, y: s2_ground_z(x, y) + 0.015, seed=91, r=(0.012, 0.045), moss=0.0,   # (r2g EMPTY 22-24%: the foreground read as one smooth plane)
              avoid=lambda x, y: in_house(x, y) or (abs(x - px) < 0.4 and abs(y - py) < 0.4))
    b = s2_base(S2_H)
    wall = earth_wall("earth wall", [(float(x), -b / 2) for x in range(-30, 31, 1)], h=S2_H, crest=S2_CREST, base=b, seed=8)
    for m_ in [bpy.data.materials.get("wall heaped rock")]:      # (r2zd pre-flight: "the wall a flat dark slab"; coordinator: lighter rock, sunlit) this shot's wall only: a grey basalt, not a black block
        if m_ and m_.use_nodes:
            for n_ in m_.node_tree.nodes:
                if n_.bl_idname == "ShaderNodeMix" and n_.blend_type == 'MULTIPLY': n_.inputs[7].default_value = (*K.lin("#8E877E"), 1)
    house = town_house("town house by the wall", (hx, hy, s2_ground_z(hx, hy)), yaw=math.pi / 2, w=hw, d=hd, storeys=1, base=0.3, pitch=40, roof="#B8352B", wall="#E9D9A2", seed=5)     # shot 4's own build and size (its houses: 3.2-4.0 by 2.6-3.0, base 0.3, one storey)
    bpy.context.view_layer.update()
    for o in house["root"].children_recursive:                 # (r3d pre-flight BROKEN: "a dark vertical rod or post beside the house": its downpipes)
        if "downpipe" in o.name: o.hide_render = True; o.hide_viewport = True
    s2_flag((hx - hd / 2 - 0.2, hy + hw / 2 + 0.45, s2_ground_z(hx, hy)))     # at the house's far corner, the flag flying over its gable (clear of the digger's bucket)
    def light():
        k = iceland_light(sun_elev=30, sun_az=160, sun=3.2, sky=0.45, haze=1.2)       # (coordinator, r2e: lit so the boulders read) the sun raking across the wall's town face from the right
        bg = ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(185))      # (r2za EMPTY 48%: turned so its clouds stand over the house) a REAL sky with cloud in it (Poly Haven)
        nt = sc.world.node_tree; env = next(n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT')       # (CI 46083546367 WEATHER: "saturated blue ... warm and summery", not the world's "cold and bright"): the same real sky, its blue drained to a cold pale one
        hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.45; hs.inputs["Value"].default_value = 1.05
        nt.links.new(env.outputs["Color"], hs.inputs["Color"]); nt.links.new(hs.outputs["Color"], bg.inputs["Color"])
        return k
    return dict(light=light, wall=wall, house=house)


def shot2():
    """THE WALL RISES. See the module's head. (coordinator, after r2zu: the DIGGER is the cause and is seen causing it:
    on every still its bucket is at the crest's lip, tipping, rocks leaving it onto the wall's face; Data only REACTS.)"""
    W = lw_win
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    TOPS = [1.2, 2.9, 4.1, 5.4]  # (coordinator, after r2zu: back to 5.4 so the digger has headroom and the smoke shows over it)
    def top(t):
        if t <= TS[0]: return TOPS[0]
        for k in range(3):
            if t <= TS[k + 1]: return TOPS[k] + (TOPS[k + 1] - TOPS[k]) * W(t, TS[k], TS[k + 1] - TS[k])
        return TOPS[3]
    P = place_wall_works()
    light = P["light"]; wall = P["wall"]
    b = s2_base(S2_H); yc = -b / 2
    DX, DY = S2_DIG
    # (coordinator, after r3d: "the wall's top a flat slab edge", "the digger hovers on it") a rubble crest: loose
    # boulders heaped all along the top, riding up with the wall, and a lane of them on both sides of the digger's tracks
    crest_m = lw_noise("crest rubble", "#3A3633", "#8E877E", scale=10, rough=0.95, bump=0.9, detail=10)
    rr = lw_random.Random(31)
    lane = (yc + DY - 1.3, yc + DY + 1.3)
    for k in range(260):
        x = rr.uniform(-14.0, 14.0); y = rr.uniform(yc - S2_CREST / 2, yc + S2_CREST / 2)
        if -3.4 < x < 3.4 and lane[0] < y < lane[1]: continue
        r_ = rr.uniform(0.18, 0.42)
        bo = lw_block(f"crest rubble {k}", (0, 0, 0), r_, crest_m, rr, squash=0.75)
        bo.parent = wall["root"]; bo.location = (x, y, S2_H + r_ * 0.35)
    for k in range(70):                                            # heaped against the tracks' sides: it sits IN the rubble
        x = rr.uniform(-3.4, 3.4); y = rr.choice((lane[0] - rr.uniform(-0.05, 0.25), lane[1] + rr.uniform(-0.05, 0.12)))
        r_ = rr.uniform(0.16, 0.34)
        bo = lw_block(f"crest rubble lane {k}", (0, 0, 0), r_, crest_m, rr, squash=0.75)
        bo.parent = wall["root"]; bo.location = (x, y, S2_H + r_ * 0.3)
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        wall["root"].location = (0, 0, top(t) - S2_H); wall["root"].keyframe_insert("location", frame=f)
    # ---- its builder: one digger on the crest, riding up with it. On each still it TIPS a bucket of boulders over the
    # lip onto the town face (the rocks fall out of it); between the stills it swings back loaded. The kit's digger is
    # posed when it is built, so each pose is its own digger, shown for its moment. Solved offline (bucket hinge 0.35 m
    # past the lip, 0.5-0.7 m over the crest): still 1 in the gap left of the house, then along the crest over its roof.
    rnd = lw_random.Random(12)
    rock_m = lw_noise("loose lava rock", "#141312", "#3E3A36", scale=12, rough=0.95, bump=0.9, detail=10)
    #         slew, boom, stick, curl(+ = mouth out and down: tipping), loaded
    TIP = [(-45, 9, -135, 81), (-45, 10, -136, 81), (-45, 11, -137, 80), (-45, 13, -137, 80)]      # the bucket's hinge 0.35 m past the lip, 0.5-0.65 m over the crest: x -0.8, -1.3, -1.9, -2.5
    LOAD = [(-37.5, 26, -152, -24), (-37.5, 26, -152, -24), (-37.5, 26, -152, -24)]     # between: swung back up over the crest, the bucket curled full
    RXS = [DX, DX - 0.5, DX - 1.1, DX - 1.7]                      # it drives along the crest toward the house as the wall passes the roof it drives along the crest as it goes, its arm side-on to us
    def rx(t):
        if t <= TS[0]: return RXS[0]
        for k in range(3):
            if t <= TS[k + 1]: return RXS[k] + (RXS[k + 1] - RXS[k]) * W(t, TS[k], TS[k + 1] - TS[k])
        return RXS[3]
    POSES = [p_ + (False,) for p_ in TIP] + [p_ + (True,) for p_ in LOAD]
    diggers = []; lips = []
    for k, (slew, boom, stick, bucket, loaded) in enumerate(POSES):
        before = set(bpy.data.objects)
        d = FX.digger(name=f"digger {k}", loc=(0, 0, 0), yaw=0.0, slew=0.0, boom=boom, stick=stick, bucket=bucket, lights=False, seed=3)
        drv = K.mat("digger driver", "#1C1D20", rough=0.8)          # (coordinator: a dark seated figure in the cab, if cheap) its driver
        K.box(f"digger {k} driver body", (-0.4, -0.22, 1.05), (0.24, 0.2, 0.34), drv, bev=0.04, parent=d["house"])
        K.box(f"digger {k} driver head", (-0.4, -0.26, 1.32), (0.15, 0.15, 0.16), drv, bev=0.05, parent=d["house"])
        d["house"].rotation_euler[2] = math.radians(slew)
        d["root"].rotation_euler[2] = -math.pi / 2               # its tracks along the crest, side-on to us
        d["root"].scale = (1.6, 1.6, 1.6)                         # (coordinator, after r2zu: bigger) (r2y: real scale: as long as the house is wide)
        bpy.context.view_layer.update()
        scoop = [o for o in d["bucket"].children_recursive if o.type == 'MESH']
        vs = [o.matrix_world @ v.co for o in scoop for v in o.data.vertices]
        lips.append(min(vs, key=lambda v: v.z) if vs else d["bucket"].matrix_world.translation.copy())    # tipping, its lip is its lowest point
        if loaded:
            tip = d["bucket"].matrix_world.translation
            for j in range(2):
                bo = lw_block(f"digger {k} boulder {j}", (tip.x + 0.12 * (j - 0.5), tip.y + 0.1, tip.z + 0.05), 0.14, rock_m, rnd, squash=0.8); bo.parent = d["house"]
                bo.matrix_parent_inverse = d["house"].matrix_world.inverted()
        objs = [o for o in bpy.data.objects if o not in before]
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            d["root"].location = (rx(t), yc + DY, top(t)); d["root"].keyframe_insert("location", frame=f)
        diggers.append(objs)
    WIN = (0.45, 0.35)                                            # each still sits in its tipping pose: from 0.45 s before to 0.35 s after
    def pose_at(t):
        for k, ts in enumerate(TS):
            if ts - WIN[0] <= t < ts + WIN[1]: return k
        nxt = next((k for k, ts in enumerate(TS) if t < ts), 3)
        return 4 + max(0, min(2, nxt - 1))
    print("S2 digger poses at the stills", [pose_at(t) for t in TS], "lips", [tuple(round(v, 2) for v in l) for l in lips[:4]], flush=True)
    for k, objs in enumerate(diggers):
        prev = None
        for f in range(1, NF + 8):
            t = (f - 1) / FPS; hid = pose_at(t) != k
            if hid != prev:
                for o in objs:
                    o.hide_render = hid; o.hide_viewport = hid
                    o.keyframe_insert("hide_render", frame=f); o.keyframe_insert("hide_viewport", frame=f)
                prev = hid
    # the load leaving the bucket: boulders pour off its lip and fall down the town face, a few in the air on each still
    G_ = 9.8
    tip_m = lw_noise("tipped rock", "#4A4642", "#8E877E", scale=12, rough=0.95, bump=0.9, detail=10)     # the wall's own grey basalt
    for k, ts in enumerate(TS):
        for j in range(6):
            t0 = ts - WIN[0] + 0.02 + j * 0.075; life = 0.5
            vx, vy = rnd.uniform(-0.35, 0.35), rnd.uniform(0.45, 0.8)
            bo = lw_block(f"tipped boulder {k}_{j}", (0, 0, 0), rnd.uniform(0.16, 0.26), tip_m, rnd, squash=0.8)     # (r3b: 0.1 m dark rocks did not read leaving the bucket)
            prev = None
            for f in range(1, NF + 8):
                t = (f - 1) / FPS; tau = t - t0; on = 0.0 <= tau < life
                if on:
                    l0 = lips[k] + Vector((rx(t0), yc + DY, top(t0)))
                    bo.location = (l0.x + vx * tau, l0.y + vy * tau, l0.z - 0.5 * G_ * tau * tau)
                    bo.rotation_euler = (3.0 * tau + j, 2.0 * tau, 0.0)
                    bo.keyframe_insert("location", frame=f); bo.keyframe_insert("rotation_euler", frame=f)
                if on != prev:
                    bo.hide_render = not on; bo.hide_viewport = not on
                    bo.keyframe_insert("hide_render", frame=f); bo.keyframe_insert("hide_viewport", frame=f); prev = on
    # ---- him: planted in the foreground, he only REACTS (coordinator, after r2zu: no signalling)
    data = load_data()
    CAM0 = Vector(S2_CAM); LOOK0 = CAM0 + Vector((0.0, -1.0, 0.285)) * 5.0      # (coordinator, r2y: LOW, tilted up, close)
    X0, Y0 = S2_P0; Z0 = s2_ground_z(X0, Y0) + 0.02
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    LENS = math.degrees(yaw_of(CAM0.x - X0, CAM0.y - Y0))
    data.place(X0, Y0, LENS)
    data.arm.location.z = Z0
    kit = hard_hat(data)
    T1, T2, T3 = 0.17 * DUR, 0.45 * DUR, 0.8 * DUR             # the changes between the poses
    TO = Vector((CAM0.x - X0, CAM0.y - Y0, 0)).normalized()
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        SD = Vector((-TO.y, TO.x, 0))
        p = (Vector((X0, Y0, Z0)) + TO * (0.05 * W(t, T1, 0.45) + 0.04 * W(t, T2 + 0.15, 0.45))     # (r3e FRAME: 0.15 m nearer the lens put his feet under the bottom edge)     # a step back as it passes the roof, then another
             + SD * (0.05 * W(t, 0.1, 0.35) - 0.05 * W(t, T2 + 0.3, 0.4)))
        yaw = LENS - (41 + 4 * W(t, T2, 0.45) - 45 * W(t, T3, 0.5))     # (r3g/r3i FACE: 48 put a still at 75)     # (r3f pre-flight: "he never looks at the wall", "no turn to us") 1-3 turned well round to the digger; 4 right round to us
        data._kobj(t, loc=tuple(p), rot=math.radians(yaw))
        data._plant_feet_here(t, lift=(Z0, Z0))
    sc.frame_set(1); bpy.context.view_layer.update()
    def pts(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); M = data.arm.matrix_world
        fw = data.forward(); rt = Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))
        return M, fw, rt
    UP = Vector((0, 0, 1))
    def arms(tt, want):
        """want[side] is 'hang', 'hip' or 'thumb'"""
        M_, fw, rt = pts(tt)
        for s_, sg in (("L", -1), ("R", 1)):
            if s_ == "L": continue                                 # his near hand holds the radio all shot (data.reach below)
            sh = M_ @ data.J[s_]["sh"]; hp = M_ @ data.J[s_]["hip"]; w_ = want.get(s_, "hang")
            if w_ == "hip":
                data._arm_ik(s_, hp + rt * sg * 0.05 - fw * 0.03 + UP * 0.1, tt, 3.0)     # (r3c: at full stretch the hands hung by his hips: nearer the shoulder, the elbows jut out); data._k(f"hand.{s_}", tt, rot=(0, 0, sg * 20))
            elif w_ == "open":                                    # (r3e: the thumbs up read as a fist: dropped) hands open at his sides, relieved
                for bn, r in zip((f"arm.{s_}", f"fore.{s_}", f"hand.{s_}"), data.ARMS["open"](sg)): data._k(bn, tt, rot=r)
            elif w_ == "whoa":
                for bn, r in zip((f"arm.{s_}", f"fore.{s_}", f"hand.{s_}"), data.ARMS["whoa"](sg)): data._k(bn, tt, rot=r)
            elif w_ == "thumb":
                data._arm_ik(s_, sh + fw * 0.16 + rt * sg * 0.05 - UP * 0.01, tt, 0.4); data._k(f"hand.{s_}", tt, rot=(-85, 0, sg * 15))     # (r3c: out at his side it read as a wave; r3d: this comment had swallowed the fist's turn) in front of his shoulder at chest height, the thumb UP (character.act thumbs_up)
            else:
                for bn in (f"arm.{s_}", f"fore.{s_}", f"hand.{s_}"): data._k(bn, tt, rot=data.RELAXED[bn])
    # 1 watching it work, one hand on his hip
    for tt in (0.0, T1 - 0.05): arms(tt, {"R": "hip"})
    # 2 the wall reaches the roof: a step back, looking up at it, hands out: whoa (r3f pre-flight: four near-identical poses)
    for tt in (T1 + 0.4, T2 - 0.05): arms(tt, {"R": "whoa"})
    # 3 head up further, leaning back, both hands on his hips
    for tt in (T2 + 0.45, T3 - 0.05): arms(tt, {"R": "hip"})
    # 4 round to us: hands open, a relieved grin
    for tt in (T3 + 0.5, DUR + 0.5): arms(tt, {"R": "open"})
    # (coordinator, after r3j BODY "holds nothing, nothing links him to the work": he RADIOS the digger) a hand-held
    # radio in his near hand the whole shot: at his mouth on stills 1-2, lowered to his chest on 3, down at his side on 4
    radio = s2_radio()
    path = lw_hand(data, "L", [(0.0, (0.11, -0.05, 0.05)), (T1 + 0.3, (0.11, -0.05, 0.06)), (T2 - 0.1, (0.11, -0.05, 0.05)),
                               (T2 + 0.4, (0.09, -0.05, -0.12)), (T3 - 0.05, (0.09, -0.05, -0.12)), (T3 + 0.45, (0.07, 0.07, -0.13)), (DUR + 0.5, (0.07, 0.07, -0.13))])
    data.reach("L", path, 0.0, DUR + 0.5, lead=0.05, back=None, elbow_out=0.5)
    lw_layer(data, "spine", lambda t: (-4 * W(t, T1, 0.4) - 7 * W(t, T2, 0.45) + 11 * W(t, T3, 0.45), 0, 0), 0, DUR + 0.4)     # leaning back further as it climbs
    lw_layer(data, "chest", lambda t: (-3 * W(t, T1, 0.4) - 4 * W(t, T2, 0.45) + 7 * W(t, T3, 0.45), 0, 0), 0, DUR + 0.4)
    BK = [lips[k] + Vector((RXS[k], yc + DY, TOPS[k])) for k in range(4)]      # the bucket on each still
    data.look_at(BK[0], 0.0, max_yaw=20, max_pitch=6, blend=0.0)              # 1 at the bucket (r3g FACE: 75 degrees off the lens at 30)
    data.look_at(BK[1], T1 + 0.3, max_yaw=30, max_pitch=13, blend=0.35)      # 2 up at it
    data.look_at(BK[2], T2 + 0.35, max_yaw=30, max_pitch=20, blend=0.4)     # 3 further up (the rest is his lean back: r2ze, the glasses float on a big head pitch)
    data.look_at(CAM0 + Vector((0, 0, 0.1)), T3 + 0.35, max_yaw=15, max_pitch=8, blend=0.4)     # 4 to us
    data.perform("happy", T3 + 0.4, hold=DUR - T3, arms=False)                # 4 a happy bounce, his grin (r3f: "not clearly a grin")
    data.expression("determined", 0.0, T1 + 0.2, blend=0.15)
    data.expression("surprised", T1 + 0.2, T3 + 0.2, blend=0.2)
    data.expression("happy", T3 + 0.2, DUR + 1.0, blend=0.2)
    data.finish()
    for f in range(1, NF + 8):                                 # held UPRIGHT in his fist, antenna up, its face to us: the fist round its middle
        sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb["hand.L"].matrix
        radio.location = M.translation + (M.to_3x3() @ Vector((0, 0.045, 0))) - Vector((0, 0, 0.09))
        radio.rotation_euler = (0.0, 0.0, math.atan2(CAM0.x - radio.location.x, -(CAM0.y - radio.location.y)))
        radio.keyframe_insert("location", frame=f); radio.keyframe_insert("rotation_euler", frame=f)
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=24.0, fstop=11.0)     # (p2n, r2y: a wider lens: him, the digger and the house side by side, none hiding another)
    print("S2 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()), flush=True)
    still = lambda t: (CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5)))
    lw_cut(cam, still, still, -1.0, -1.0, 24.0, 24.0)
    return dict(lanes=[], kiosks=[], place="wall_works", light=light, data=data, rest=1, grips=("radio",), cutaway=None,
                boxes=[],
                conseq=[("his digger tips rock onto a wall behind the house, from its knee to over its roof", lambda: [wall["body"]], TS[0], TS[3], {"whole": False})])
