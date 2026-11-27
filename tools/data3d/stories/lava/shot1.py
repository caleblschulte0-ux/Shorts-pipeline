"""BEAT 1, THE HOOK: "A volcano keeps erupting right beside one Icelandic town, and everyone had to run."

THE TOWN, AND IT ERUPTS (coordinator, 2026-11-27, after the audit of every recorded verdict: the shots that passed have
the WORLD doing the event while Data reacts, one camera, two or three props). One lens, low in Grindavik's main street,
looking up it past him to the roofs and the ridge over them. Behind the roofs the eruption comes and grows still by
still: nothing (still 1), an orange glow along the ridge (still 2), a lava fountain bursting up over the roofs (still
3), the fountain under a towering black ash plume (still 4). Data, in the foreground at the left, three-quarter to us,
looks at us, turns his head at the glow, flinches at the fountain, and on still 4 runs at the lens, out of the street."""

S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX = 1.6                            # the fissure's middle (x)
S1_HOME_BASE = 0.05
S1_P0 = (0.15, -2.6)                   # where he stands: in the street, centred on the lens (coordinator, r1za: margin all round)
S1_CAM = (0.3, -4.0, 1.65)             # (coordinator, after VARIETY: a HIGH lens, twice his height, tipped down the street) the one lens


def s1_ground_z(x, y):
    """the street flat, the land round the town rolling, and the ridge rising behind it to the fissure"""
    z = -0.07 if abs(x) < 1.1 else 0.0                    # (the road's own deck lies in this shallow bed: the kit's road, never the rock showing through it)
    if abs(x) > 2.4: z += 0.15 * lw_fbm(x * 0.3, y * 0.3, 3) + 0.03 * (abs(x) - 2.4)
    r = max(0.0, (y - 9.0) / 6.0)
    z += 8.0 * (r * r * (3 - 2 * r) if r < 1 else 1.0) + (0.5 * lw_fbm(x * 0.15, y * 0.2, 7) if y > 8.5 else 0.0)
    if y > S1_RIDGE_Y: z -= 0.6 * min(1.0, (y - S1_RIDGE_Y) / 2.0)
    return z


def place_grindavik_street():
    """GRINDAVIK'S MAIN STREET: the asphalt street with its kerbs running away from the lens up to the ridge, the low
    coloured-roof houses down both sides and one across its end, the old lava field and moss round the town, the ridge
    above it where the fissure opens (its glowing slot built here, hidden until the eruption comes), far blue
    mountains. Nothing else in the street: no cars, flags, poles or trucks (coordinator: two or three props)."""
    rnd = lw_random.Random(5)
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, lw_noise("moss hill ground", "#1E2C15", "#4A6430", scale=1.6, rough=1.0, bump=0.5, detail=12, lo=0.3, hi=0.75))     # (r1w EMPTY 34%: the moss read as one smooth sheet joining sky to street: a tighter, higher-contrast moss)     # (coordinator, p1c: the hill read beige: green moss, darker)
    # (coordinator, p1c: the kit's scanned asphalt read as a CRACKED street before anything happened, stealing shot 4's
    # crack: an intact grey deck, its centre line painted fresh)
    asph = lw_noise("street asphalt", "#28292C", "#4E5054", scale=40.0, rough=0.85, bump=0.35, detail=12, lo=0.38, hi=0.62)     # (r1za pre-flight: "blurry noise": a fine aggregate grain)     # (r1y EMPTY: the near street still one smooth plane at phone size: a coarse aggregate grain)     # (r1w EMPTY: worn patches, still intact)
    K.box("street road", (0, 2.5, -0.035), (2.3, 20, 0.07), asph, bev=0.0)
    paint = K.mat("street line paint", "#E6E2D6", rough=0.6)
    y_ = -7.2
    while y_ < 12.0:
        K.box("street road line", (0, y_ + 0.5, 0.0015), (0.07, 1.0, 0.004), paint, bev=0.0); y_ += 2.2
    for sx in (-1, 1):                                     # (r1x EMPTY 38%: the near street read as one smooth grey plane) its painted edge lines
        K.box("street road edge line", (sx * 0.98, 2.5, 0.0015), (0.06, 20, 0.004), paint, bev=0.0)
    iron = lw_noise("street cast iron", "#232325", "#45474A", scale=30.0, rough=0.6, bump=0.6)
    K.cyl("street manhole cover", (0.9, -3.1, 0.004), 0.32, 0.012, iron, v=40, bev=0.003)     # the near street's own furniture: a manhole cover by the lens
    for gy in (-3.3, -0.4, 2.6):                           # and the drain grates along the kerbs
        for sx in (-1, 1):
            K.box("street drain grate", (sx * 1.0, gy, 0.003), (0.22, 0.45, 0.01), iron, bev=0.0)
    for k in range(7):                                     # and the zebra crossing just behind him
        K.box("street crossing stripe", (-0.84 + 0.28 * k, -1.35, 0.0016), (0.15, 0.9, 0.004), paint, bev=0.0)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        K.box("kerb", (sx * 1.15, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 1.45, 2.5, 0.035), (0.5, 20, 0.07), ph_mat("concrete_wall_008", scale=1.6, tint="#A8A49C", name="pavement"), bev=0.005)
    houses = []
    for sx in (-1, 1):
        y = -7.2 if sx < 0 else -6.6
        k = 0
        while y < 9.5:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)
            hs = town_house(f"town house {sx}_{k}", (sx * (1.65 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d, storeys=1,
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A")[(k + (sx > 0)) % 4], wall=("#B44A3C", "#E9D9A2", "#BFD3DD", "#F1EEE6", "#7E9A86")[(k + 2 * (sx > 0)) % 5], base=0.3, seed=k)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    px, py = S1_P0
    # (coordinator, p1c: no cinders on the street: nothing has happened yet)
    lava_rock("lava field rock", 60, (-14, 14, -6, 8), s1_ground_z, seed=3, r=(0.04, 0.12), moss=0.6, avoid=lambda x, y: abs(x) < 5.2)
    lava_rock("ridge slope stone", 260, (-12, 14, 8.5, 15.0), s1_ground_z, seed=12, r=(0.05, 0.16), moss=0.5)     # (r1w EMPTY: the slope needs its rocks big enough to read at phone size)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a torn glowing slot along the ridge top (lava, never neon), hidden until the eruption comes
    fl = lava_mat("fissure lava", heat=2.0, scale=3.0, fresh=1.0)
    slot = []
    for k in range(14):
        x = S1_FX - 6.0 + 12.0 * k / 13; w_ = 0.45 + 0.25 * math.sin(1.7 * k)
        o = K.box("fissure glow", (x, S1_RIDGE_Y + 0.12 * math.sin(2.3 * k), s1_ground_z(x, S1_RIDGE_Y) + 0.12), (0.95, w_ * 1.6, 0.3), fl, bev=0.05)     # (p1a: sunk in the ridge, the glow never showed)
        o.rotation_euler = (0, 0, 0.15 * math.sin(3.1 * k)); slot.append(o)
    fz = s1_ground_z(S1_FX, S1_RIDGE_Y)
    # a house across the end of the street, under the ridge: its red tin roof slopes toward the lens
    town_house("town house at the street's end", (1.3, 10.4, s1_ground_z(1.3, 9.0)), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.5, roof="#B8352B", wall="#E9D9A2", seed=3)
    bpy.context.view_layer.update()
    for o in bpy.data.objects:                             # (the near houses' door steps stood in the frame's corner as bare pale blocks: cut)
        if o.name.endswith(" step") or " step." in o.name:
            c = o.matrix_world.translation
            if -4.5 < c.y < 3.5: o.hide_render = True; o.hide_viewport = True
    def light():
        k = iceland_light(sun_elev=26, sun_az=-35, sun=3.0, sky=0.4, haze=0.8)           # the world's one bright day (the reset, 2026-11-25: no dusk)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(70))   # (r1v EMPTY 25%: clouds over the street) the same REAL sky as the wall's beats (Poly Haven)
        return k
    return dict(light=light, slot=slot, houses=houses, fz=fz)


def shot1():
    """THE TOWN, AND IT ERUPTS. See the module's head."""
    W = lw_win
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    TS = [f_ * DUR for f_ in (0.08, 0.38, 0.68, 0.98)]           # the four stills
    T_GLOW = TS[0] + 0.3                                         # the smoking ridge starts to glow; the cars' lamps come on
    T_BURST = TS[2] - 0.55                                       # the fountain erupts out of it (still 3: he recoils from it)
    T_PLUME = TS[2] - 0.3                                        # the ash plume climbs over it
    T_CARS = TS[1] + 0.15                                        # the two parked cars pull out and speed out of town, past him
    T_TURN = TS[2] + 0.35                                        # he half-turns toward the lens side, about to follow them
    P = place_grindavik_street()
    light = P["light"]
    FZ = P["fz"]
    # ---- still 1: thin smoke already rising off the ridge (coordinator, r1za pre-flight: the eruption has a visible start)
    smoke = [lw_steam(f"ridge smoke {k}", (S1_FX + dx, S1_RIDGE_Y + 0.3, s1_ground_z(S1_FX + dx, S1_RIDGE_Y) - 0.1), w=1.2, h=7.0,
                      keys=[(0.0, 0.45), (T_GLOW, 0.6), (T_BURST, 0.8)], t_end=DUR + 1.0, seed=1.3 + k, col=(0.62, 0.62, 0.64), dens=2.5, lean=(0.04, 0.02))
             for k, dx in enumerate((-3.5, 0.5, 4.0))]
    # ---- the eruption, growing still by still: the slot glows, the fountain erupts, the plume fills the sky
    for o in P["slot"]:
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=F(T_GLOW))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_GLOW) + 1)
    # (coordinator, after shot 2's r2e pre-flight: one grade in all four stills: no lamp lights the town; the glow is the
    # lava's own, the slot and the fountain)
    # (coordinator, r1ze: the fountain twice as tall, near the top margin but whole (p1a: h 20 ran out of the top; 13), the densest version: a wide base, a
    # bright core, and two more columns layered round it in depth so it is never one flame card)
    fountain = lw_fire_column("lava fountain", (S1_FX, S1_RIDGE_Y, FZ - 0.3), w=6.0, h_fire=13.0, h_smoke=5.0,
                              lean=(0.03, 0.06), t_end=DUR + 1.0, seed=2.3, fire=10.0, smoke_d=3.0, rise=5.0, spread=0.35, flame_d=5.0,
                              keys=[(T_BURST - 0.05, 0.0), (T_BURST + 0.4, 0.75), (TS[2], 1.0)], grow=True)
    flanks = [lw_fire_column(f"lava fountain flank {k}", (S1_FX + dx, S1_RIDGE_Y + dy, s1_ground_z(S1_FX + dx, S1_RIDGE_Y) - 0.3), w=3.2, h_fire=h_, h_smoke=3.0,
                             lean=(0.03 * (k * 2 - 1), 0.05), t_end=DUR + 1.0, seed=5.7 + 3.1 * k, fire=8.0, smoke_d=3.0, rise=4.5, spread=0.3, flame_d=4.5,
                             keys=[(T_BURST, 0.0), (T_BURST + 0.45, 0.7), (TS[2], 1.0)], grow=True)
              for k, (dx, dy, h_) in enumerate(((-2.6, 1.2, 8.0), (2.4, -0.8, 9.5)))]
    PX, PY = S1_FX - 1.0, S1_RIDGE_Y + 2.5; PZ = s1_ground_z(PX, PY)
    plumes, base0 = [], []
    for k, (dx, w_, h_, dy) in enumerate(((0.0, 13.0, 64.0, 0.0), (-5.5, 9.0, 44.0, 1.5), (5.0, 9.5, 50.0, 1.0))):     # (coordinator, p1c: towering out of the top of the frame by still 4)
        o = ash_plume((PX + dx, PY + dy, PZ - 0.5), w=w_, h=h_, S=8.0, dens=20.0, lean=(-0.02 + 0.02 * k, 0.03), col=(0.05, 0.047, 0.045),
                      seed=4.1 + 2.7 * k, t_end=DUR + 1.0, name=f"eruption plume {k}")
        plumes.append(o); base0.append((Vector((PX + dx, PY + dy, PZ - 0.5)), o.location.copy(), o.scale.x))
    for o, (b, l0, s0) in zip(plumes, base0):
        o.hide_render = True; o.keyframe_insert("hide_render", frame=1); o.keyframe_insert("hide_render", frame=F(T_PLUME))
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_PLUME) + 1)
        for f in range(F(T_PLUME), NF + 8, 2):
            t = (f - 1) / FPS
            g = max(0.08, 0.08 + 0.92 * W(t, T_PLUME, TS[3] - T_PLUME))          # (a volume scaled near zero crashes Cycles: never under 0.08)
            o.scale = (s0 * g,) * 3; o.location = b + (l0 - b) * g
            o.keyframe_insert("scale", frame=f); o.keyframe_insert("location", frame=f)
    # ---- the town flees (coordinator, r1ze: the WORLD does the fleeing): two cars parked at the kerbs up the street; their
    # lamps come on at the glow; they pull out into the street and speed down it toward us, past him on either side, dust
    # behind; on still 4 both are whole in the frame at mid-street, nearer than on still 3. Smooth from still 1 to 4.
    cars, dust = [], []
    for k, (x0, x1, y0, y4, col) in enumerate(((0.65, 0.95, 9.0, -0.4, "#2F5E8C"), (-0.65, -0.95, 7.4, -1.0, "#B8352B"))):
        c = FX.car(name=f"getaway car {k}", loc=(x0, y0, 0.0), yaw=0.0, kind="hatch", col=col, lights=True, seed=4 + k, dirt=0.4, power=30.0)
        t0 = T_CARS + 0.25 * k; T = TS[3] - t0; ra = 0.6
        v = (y0 - y4) / (T - ra / 2)
        def cy(t, y0=y0, t0=t0, v=v, ra=ra):
            u = max(0.0, t - t0)
            return y0 - (v * u * u / (2 * ra) if u < ra else v * (ra / 2 + (u - ra)))
        for f in range(1, NF + 8):
            t = (f - 1) / FPS
            u = max(0.0, t - t0); pull = W(t, t0, 0.8)
            c["root"].location = (x0 + (x1 - x0) * pull, cy(t), 0.0)
            c["root"].rotation_euler = (0.0, 0.0, -0.25 * (x1 - x0) / abs(x1 - x0) * math.sin(math.pi * min(1.0, u / 0.8)))     # it noses out from the kerb and straightens
            c["root"].keyframe_insert("location", frame=f); c["root"].keyframe_insert("rotation_euler", frame=f)
        for L_ in c["lights"]:                                   # its lamps: off while it is parked, on at the glow
            L_.data.keyframe_insert("energy", frame=F(T_GLOW) + 3); e = L_.data.energy
            L_.data.energy = 0.0; L_.data.keyframe_insert("energy", frame=1); L_.data.keyframe_insert("energy", frame=F(T_GLOW)); L_.data.energy = e
        for kk, yd in enumerate((y0 - 1.4, y0 - 4.0)):         # its dust: off the street where its tail has passed
            tk = t0
            while cy(tk) > yd - 1.2 and tk < DUR + 1.0: tk += 1.0 / FPS
            dust.append(lw_steam(f"car dust {k}_{kk}", (x1, yd, 0.0), w=1.0, h=1.0, keys=[(tk - 0.05, 0.0), (tk + 0.25, 0.8), (tk + 1.5, 0.5)],
                                 t_end=DUR + 1.0, seed=7.1 + 2 * k + kk, col=(0.58, 0.54, 0.47), dens=2.5, lean=(0.0, 0.05)))
        cars.append(c)
    for kind in ("head", "tail"):                              # the lamp lenses light with the lamps
        m = bpy.data.materials.get(f"fx lens {kind} on")
        if m:
            bs = m.node_tree.nodes["Principled BSDF"]; si = bs.inputs["Emission Strength"]; e = si.default_value
            si.keyframe_insert("default_value", frame=F(T_GLOW) + 3)
            si.default_value = 0.0; si.keyframe_insert("default_value", frame=1); si.keyframe_insert("default_value", frame=F(T_GLOW)); si.default_value = e
    # ---- him: centred in the street (coordinator, r1za: centred with margin in every still). No run, no point: he
    # stands calm facing us, turns his head and shoulders to the glow, recoils from the fountain (leaning back, both arms
    # thrown up beside his head, mouth open), and holding the recoil half-turns to the lens side as if to follow the cars.
    data = load_data()
    CAM0 = Vector(S1_CAM); D = Vector((-0.08, 1.0, -0.23)).normalized(); LOOK0 = CAM0 + D * 5.0      # (r1ze: tilted up so the fountain stands whole in the frame)
    X0, Y0 = S1_P0; Z0 = 0.0
    LENS = yaw_of(CAM0.x - X0, CAM0.y - Y0)
    YAW = LENS + math.radians(10)                              # 1 facing us
    data.place(X0, Y0, math.degrees(YAW))
    kit = hard_hat(data)
    TO = Vector((CAM0.x - X0, CAM0.y - Y0, 0)).normalized()     # toward the lens
    SIDE = Vector((-TO.y, TO.x, 0))
    for f in range(1, NF + 8):
        t = (f - 1) / FPS
        p = (Vector((X0, Y0, Z0)) + SIDE * (0.05 * W(t, 0.1, 0.35) - 0.1 * W(t, T_GLOW + 0.15, 0.45))
             + TO * (0.16 * W(t, T_BURST + 0.08, 0.3) + 0.1 * W(t, T_TURN + 0.25, 0.45)))     # a step to the glow; the recoil's step back; a step toward the lens side
        data._kobj(t, loc=tuple(p), rot=YAW + math.radians(40) * W(t, T_GLOW, 0.6) - math.radians(10) * W(t, T_BURST + 0.08, 0.3)
                   - math.radians(55) * W(t, T_TURN, 0.6))
        data._plant_feet_here(t, lift=(Z0, Z0))
    lw_layer(data, "spine", lambda t: (-4 * W(t, T_GLOW + 0.2, 0.5) + 16 * W(t, T_BURST + 0.08, 0.3) - 6 * W(t, T_TURN + 0.2, 0.5), 0, 0), 0, DUR + 0.4)
    lw_layer(data, "chest", lambda t: (6 * W(t, T_BURST + 0.08, 0.3), 0, 0), 0, DUR + 0.4)
    RIDGE = Vector((S1_FX, S1_RIDGE_Y, FZ + 3.0))
    data.look_at(CAM0 + Vector((0, 0, 0.1)), 0.0, max_yaw=55, max_pitch=20, blend=0.0)                 # 1 at us, calm
    data.look_at(RIDGE, T_GLOW + 0.1, max_yaw=30, max_pitch=25, blend=0.35)                             # 2 round at the glow (FACE)
    data.look_at(RIDGE + Vector((0, 0, 4.0)), 1.9, max_yaw=30, max_pitch=30, blend=0.4)
    data.look_at(RIDGE + Vector((0, 0, 12.0)), T_BURST + 0.05, max_yaw=25, max_pitch=40, blend=0.15)    # 3 up at the fountain as it erupts
    data.look_at(RIDGE + Vector((0, 0, 10.0)), T_TURN + 0.3, max_yaw=55, max_pitch=30, blend=0.4)       # 4 still on it as he turns away
    data.expression("determined", 0.0, T_GLOW, blend=0.15)
    data.expression("surprised", T_GLOW, T_BURST, blend=0.15)
    data.expression("alarmed", T_BURST, DUR + 1.0, blend=0.1)
    sides = sorted("LR", key=lambda s_: -acts._shoulder(data, s_).x)
    LOW = lambda sg: ((-4, 0, sg * 5), (-22, 0, 0), (0, 0, 0))                    # (r2e pre-flight 'talking with his hands out': his arms hang)
    DOWN = lambda sg: ((-8, 0, sg * 8), (-28, 0, 0), (-4, 0, 0))                  # 2 still down, a little tense
    THROWN = lambda sg: ((-92, 0, -sg * 38), (-22, 0, -sg * 10), (-10, sg * -12, -sg * 15))     # 3 both arms thrown up beside his head (shot 3's UP, higher)
    HELD = lambda sg: ((-78, 0, -sg * 34), (-26, 0, -sg * 12), (-10, sg * -12, -sg * 12))      # 4 still up as he turns
    keys = [0.0, 0.4, T_GLOW + 0.2, 1.4, T_BURST + 0.05, T_BURST + 0.4, TS[2] + 0.1, T_TURN + 0.3, DUR + 0.5]
    for sd in sides:
        sg = -1 if sd == "L" else 1
        seq = [LOW, LOW, DOWN, DOWN, THROWN, THROWN, THROWN, HELD, HELD]
        for tk, pose in zip(keys, seq):
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), pose(sg)): data._k(bn, tk, rot=r)
    data.finish()
    cam = K.camera(tuple(CAM0), tuple(LOOK0), lens=20.0, fstop=11.0)
    print("S1 CAM", tuple(round(v, 2) for v in CAM0), "look", tuple(round(v, 2) for v in LOOK0), "data", tuple(round(v, 2) for v in data.pos()),
          "stills", [round(t, 2) for t in TS], "glow", round(T_GLOW, 2), "burst", round(T_BURST, 2), "turn", round(T_TURN, 2), flush=True)
    def cam_at(t):
        return CAM0, LOOK0, data.pos() + Vector((0, 0, 0.5))          # (coordinator, r1za: LOCKED: the drift moved the houses between stills)
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 20.0, 20.0)
    erupt = P["slot"] + [fountain] + flanks + plumes + smoke
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a lava fountain erupts up over the town's roofs", lambda: [fountain] + flanks, T_BURST + 0.35, DUR, {"whole": False}),       # (r1v: with the thin slot it measured 6% of the frame)
                        ("a huge black ash plume towers over the town", lambda: plumes, T_PLUME, DUR, {"whole": False})])
