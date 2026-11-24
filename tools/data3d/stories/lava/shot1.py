"""BEAT 1, THE HOOK: "A volcano has erupted nine times beside one town in Iceland, and the whole town had to run."

Grindavik's main street on a bright grey afternoon, low houses with coloured tin roofs down both sides, the ridge above
the town at the end of it. The ridge rips open and a curtain of lava fountains bursts up along it under a boiling
plume. The digger driver, at the striped road gate at the town's edge, winds the gate's crank hand over hand and the
striped arm swings up high over the road; the town's cars pour out under it, headlights on, past him and
out of the frame; he waves them on; the fountains surge; the street is empty and he runs after them."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the gate arm's pivot, on its post at the kerb
S1_ARM = 2.2                           # the arm, out across the road (toward -X)
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge


def s1_ground_z(x, y):
    """the street flat, the land round the town rolling, and the ridge rising behind it to the fissure"""
    z = 0.0
    if abs(x) > 2.4: z += 0.15 * lw_fbm(x * 0.3, y * 0.3, 3) + 0.03 * (abs(x) - 2.4)
    r = max(0.0, (y - 9.0) / 6.0)
    z += 3.4 * (r * r * (3 - 2 * r) if r < 1 else 1.0) + (0.5 * lw_fbm(x * 0.15, y * 0.2, 7) if y > 8.5 else 0.0)
    if y > S1_RIDGE_Y: z -= 0.6 * min(1.0, (y - S1_RIDGE_Y) / 2.0)
    return z


def s1_car(name, col):
    """a small hatchback at the world's scale (2.4 long, 1.0 wide), facing -Y, headlights on"""
    root = K.empty(name, (0, 0, 0))
    paint = bpy.data.materials.get(f"car paint {col}")
    if not paint:
        paint = bpy.data.materials.new(f"car paint {col}"); paint.use_nodes = True; b = paint.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*K.lin(col), 1); b.inputs["Roughness"].default_value = 0.25
        b.inputs["Coat Weight"].default_value = 0.6; b.inputs["Coat Roughness"].default_value = 0.05; b.inputs["Metallic"].default_value = 0.3
    glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    tyre = K.mat("car tyre", "#141414", rough=0.8)
    K.box(name + " body", (0, 0, 0.36), (1.0, 2.4, 0.42), paint, bev=0.09, parent=root)
    K.box(name + " cabin", (0, 0.2, 0.7), (0.9, 1.35, 0.4), paint, bev=0.12, parent=root)
    K.box(name + " windscreen", (0, -0.47, 0.7), (0.84, 0.04, 0.32), glass, bev=0.02, parent=root).rotation_euler = (math.radians(-30), 0, 0)
    for sx in (-1, 1):
        K.box(name + " side glass", (sx * 0.452, 0.22, 0.72), (0.01, 1.1, 0.26), glass, bev=0.0, parent=root)
        for y in (-0.78, 0.8):
            K.cyl(name + " tyre", (sx * 0.43, y, 0.2), 0.2, 0.16, tyre, rot=(0, math.pi / 2, 0), v=24, parent=root)
        K.box(name + " headlight", (sx * 0.33, -1.2, 0.42), (0.2, 0.02, 0.09), lw_emit("headlight", "#FFF6E0", 22.0), bev=0.01, parent=root)
        K.box(name + " taillight", (sx * 0.36, 1.2, 0.44), (0.16, 0.02, 0.08), lw_emit("taillight", "#FF2A18", 6.0), bev=0.01, parent=root)
    K.box(name + " bumper", (0, -1.21, 0.22), (1.0, 0.06, 0.12), K.mat("car bumper", "#2A2A2C", rough=0.5), bev=0.02, parent=root)
    lw_local(root)
    return root


def s1_gate():
    """the striped road gate at the town's edge: a steel post with its winch housing on top and the arm on its pivot (red
    and white bands); the crank that winds it is built beside his hands by s1_crank"""
    post_m = lw_metal("gate steel", "#8C9196")
    K.box("gate post", (S1_PIV.x, S1_PIV.y + 0.12, 0.25), (0.14, 0.14, 0.5), lw_paint("gate housing", "#E8E4DA"), bev=0.015)
    K.box("gate foot", (S1_PIV.x, S1_PIV.y + 0.12, 0.02), (0.26, 0.26, 0.04), post_m, bev=0.005)
    pv = K.empty("gate pivot", tuple(S1_PIV))
    red, white = K.mat("gate red", "#C8231B", rough=0.4), K.mat("gate white", "#F4F1EA", rough=0.4)
    n = 10
    for k in range(n):
        seg = S1_ARM / n
        K.box("gate arm", (S1_PIV.x - seg * (k + 0.5) - 0.03, S1_PIV.y, S1_PIV.z), (seg, 0.06, 0.08), red if k % 2 == 0 else white, bev=0.008, parent=pv)
    K.box("gate stop", (S1_PIV.x - S1_ARM + 0.05, S1_PIV.y, 0.23), (0.06, 0.06, 0.46), post_m, bev=0.01)
    return pv


def s1_crank(ctr, x_other):
    """the gate's winch crank: a wheel on the winch box's back face (axis along Y) with a knob on its rim. The box runs
    from the post top back to the wheel and across to where his other hand braces on it. Returns (wheel, box top z)."""
    post_m = lw_metal("gate steel", "#8C9196")
    x0, x1 = min(ctr.x, S1_PIV.x) - 0.07, max(ctr.x, S1_PIV.x) + 0.07
    y0, y1 = S1_PIV.y + 0.195, ctr.y - 0.012
    z0, z1 = ctr.z - 0.09, ctr.z + 0.07
    K.box("gate winch housing", ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), lw_paint("winch yellow", "#E0A21C"), bev=0.015)
    wh = K.empty("gate crank", tuple(ctr))
    K.cyl("gate crank wheel", (0, 0.0, 0), S1_CRANK_R + 0.012, 0.02, post_m, rot=(math.pi / 2, 0, 0), v=28, parent=wh)
    K.box("gate crank spoke", (S1_CRANK_R / 2, 0.0, 0), (S1_CRANK_R, 0.024, 0.02), post_m, bev=0.004, parent=wh)
    K.cyl("gate crank knob", (S1_CRANK_R, 0.04, 0), 0.016, 0.07, K.mat("gate handle", "#22201E", rough=0.5), rot=(math.pi / 2, 0, 0), v=14, parent=wh)
    lw_local(wh)
    return wh, z1


def s1_fountain_mat():
    """a lava fountain: pure glowing orange torn by streaks of black spatter crust (a lit surface over it washed it to
    salmon under the plume), the noise stretched up the jet so it reads as a rising spray"""
    m = bpy.data.materials.get("fountain lava")
    if m: return m
    m = bpy.data.materials.new("fountain lava"); m.use_nodes = True; nt = m.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (3, 3, 0.8)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 8; nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB"); el = rp.color_ramp.elements
    el[0].position = 0.35; el[0].color = (*K.lin("#B01000"), 1); el[1].position = 0.7; el[1].color = (*K.lin("#FF9A10"), 1)
    e = el.new(0.52); e.color = (*K.lin("#FF4000"), 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], em.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMath"); ms.operation = 'MULTIPLY_ADD'; ms.inputs[1].default_value = 1.2; ms.inputs[2].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], ms.inputs[0]); nt.links.new(ms.outputs[0], em.inputs["Strength"])
    crust = nt.nodes.new("ShaderNodeBsdfPrincipled"); crust.inputs["Base Color"].default_value = (0.02, 0.015, 0.012, 1); crust.inputs["Roughness"].default_value = 0.9
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.36; mr.inputs["From Max"].default_value = 0.44
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(mr.outputs[0], mx.inputs[0])
    nt.links.new(crust.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def place_grindavik_street():
    """GRINDAVIK'S MAIN STREET: the asphalt street with its kerbs running away from the lens up to the ridge, the low
    coloured-roof houses down both sides, the old lava field and moss round the town, the ridge above it where the
    fissure opens under its plume, the road gate at the town's edge, far blue mountains."""
    rnd = lw_random.Random(5)
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, lava_field_mat())
    K.box("street asphalt", (0, 2.5, 0.004), (4.0, 20, 0.01), lw_asphalt(), bev=0)
    kerb = lw_noise("kerb concrete", "#A6A39C", "#C2BFB6", scale=14, rough=0.8)
    for sx in (-1, 1):
        K.box("kerb", (sx * 2.05, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 2.55, 2.5, 0.035), (0.9, 20, 0.07), lw_noise("pavement", "#8E8C88", "#A8A59F", scale=8, rough=0.85), bev=0.005)
    for y in range(-8, 10, 2):
        K.box("centre line", (0, y + 0.5, 0.011), (0.08, 0.9, 0.004), K.mat("road paint", "#E9E4D4", rough=0.6), bev=0)
    houses = []
    for sx in (-1, 1):
        y = 0.9 if sx < 0 else 1.4
        k = 0
        while y < 8.0:
            w = rnd.uniform(1.9, 2.4); d = rnd.uniform(1.5, 1.8)
            hs = town_house(f"town house {sx}_{k}", (sx * (3.3 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            h=rnd.uniform(1.2, 1.45), roof=ROOFS[(k * 3 + (sx > 0)) % len(ROOFS)], wall=WALLS[k % len(WALLS)], seed=k)
            houses.append(hs); y += w + rnd.uniform(0.5, 0.9); k += 1
    lava_rock("lava field rock", 160, (-14, 14, -6, 14), s1_ground_z, seed=3, avoid=lambda x, y: abs(x) < 3.2 and y < 9.0)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a glowing line along the ridge, the curtain of fountains on it, the plume over it
    fz = s1_ground_z(0, S1_RIDGE_Y)
    K.box("fissure glow", (0, S1_RIDGE_Y, fz - 0.1), (44, 0.6, 0.3), lw_emit("fissure line", "#FF5000", 1.4), bev=0)
    fm = s1_fountain_mat(); founts = []
    for k in range(9):                                     # NINE vents, one for each eruption: they burst open one after another
        x = -14.4 + k * 3.6 + rnd.uniform(-0.25, 0.25)
        o = K.sph(f"fissure fountain {k}", (x, S1_RIDGE_Y, s1_ground_z(x, S1_RIDGE_Y) - 0.3), 1.0, fm, scale=(0.9, 0.4, 1.0), seg=20, ring=14)
        dm = o.modifiers.new("ragged", 'DISPLACE'); tx = bpy.data.textures.new(f"ragged {k}", 'CLOUDS'); tx.noise_scale = 0.35; dm.texture = tx; dm.strength = 0.35
        founts.append(o)
    spm = lw_emit("lava spatter", "#FF6000", 1.2)
    spat = [K.sph(f"fissure spatter {k}", (0, S1_RIDGE_Y, fz), rnd.uniform(0.05, 0.1), spm, seg=8, ring=6) for k in range(30)]
    ash = lw_billow_mat("eruption plume", col="#5C5A58")              # a lumpy billowing plume, not a soft smudge
    puffs = []
    for k in range(16):
        x = -20 + k * 2.7 + rnd.uniform(-1, 1)
        puffs.append(lw_billow(f"eruption plume {k}", (x, S1_RIDGE_Y + 3.0 + rnd.uniform(0, 3), fz + 7 + rnd.uniform(0, 6)), rnd.uniform(3.0, 4.2), ash, seed=k, scale=(1.3, 1.0, 0.9)))
    gate = s1_gate()
    glow = [lw_point(f"fissure light {k}", (x, S1_RIDGE_Y - 1.5, fz + 3.5), 0.0, col=(1.0, 0.4, 0.1), r=2.0) for k, x in enumerate((-12, -4, 4, 12))]
    plume_lit = [lw_point(f"plume underlight {k}", (x, S1_RIDGE_Y + 2.0, fz + 6.0), 0.0, col=(1.0, 0.35, 0.08), r=3.0) for k, x in enumerate((-9, 0, 9))]
    town_glow = lw_area("eruption glow on the town", (0, 12, 7), (0, 0, 0.5), 0.0, 14, col=(1.0, 0.5, 0.2))

    def light():
        k = iceland_light(sun_elev=18, sun_az=-45, sun=3.0, sky=0.35, haze=1.5)
        lw_clouds(cover=0.6, scale=3.0)
        return k
    return dict(light=light, founts=founts, spat=spat, puffs=puffs, gate=gate, glow=glow + plume_lit, town_glow=town_glow, houses=houses, fz=fz)


def shot1():
    """THE ROAD GATE. A low lens three-quarter from the road, the street running away behind him to the ridge. The ridge
    bursts open; he startles round at it, takes the gate's crank and winds it hand over fist: the striped arm swings up
    high over the road; the cars pour out past him; he waves them on; the fountains surge; he sets off after the cars."""
    T_ERUPT = 0.08 * DUR
    T_GRAB = 0.22 * DUR; T_UP0 = T_GRAB + 0.05; T_UP1 = T_UP0 + 1.5
    T_LET = T_UP1 + 0.1
    T_CARS = T_UP0 + 0.7
    T_WAVE0 = T_LET + 0.15; T_WAVE1 = 0.8 * DUR
    T_SURGE = 0.72 * DUR
    T_GO = 0.84 * DUR
    REVS = 2.5
    W = lw_win
    P = place_grindavik_street()
    light = P["light"]
    data = load_data()
    P0 = Vector((S1_PIV.x + 0.3, 0.42, 0.0))                # behind the gate's winch, facing down the road toward us
    data.place(P0.x, P0.y, 0.0)
    kit = hard_hat(data)
    rnd = lw_random.Random(9)
    # ---- the eruption: the fountains burst up at T_ERUPT and keep throwing, surging at T_SURGE; spatter; the plume climbs
    T_NINE = 0.2                                           # one vent bursts every T_NINE seconds: all nine by T_ERUPT + 1.6
    order = [4, 3, 5, 2, 6, 1, 7, 0, 8]                    # the rip runs out from the middle of the ridge both ways
    order = {v: i for i, v in enumerate(order)}
    for k, o in enumerate(P["founts"]):
        base = o.location.z; ph = rnd.uniform(0, 6.28); hz = rnd.uniform(0.8, 1.4); hk = rnd.uniform(0.75, 1.25)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            tk = T_ERUPT + T_NINE * order[k]                 # this vent's own burst: nine pops, counted off along the ridge
            up = W(t, tk, 0.18)
            h = hk * up * (3.0 + 0.6 * math.sin(2 * math.pi * hz * t + ph) + 2.0 * W(t, T_SURGE, 0.5) + 2.2 * lw_kick(t - tk, 0.22))
            o.scale = (0.6 + 0.5 * up, 0.35, max(0.001, h))                # a fan of spray, not a spike; o.location.z = base + 0.5 * h
            o.hide_render = up < 0.02; o.keyframe_insert("hide_render", frame=f)
            o.keyframe_insert("scale", frame=f); o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["spat"]):
        v = P["founts"][k % 9]; x0 = v.location.x + rnd.uniform(-0.5, 0.5); tk = T_ERUPT + T_NINE * order[k % 9]
        vx = rnd.uniform(-1.5, 1.5); vz = rnd.uniform(5.0, 8.5); per = 2 * vz / 9.8; ph = rnd.uniform(0, per)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < tk: o.location = (x0, S1_RIDGE_Y, P["fz"] - 1.0)
            else:
                u = (t - tk) % per
                o.location = (x0 + vx * u, S1_RIDGE_Y - 0.3 * u, P["fz"] + vz * u - 4.9 * u * u)
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["puffs"]):
        z0 = o.location.z
        for f in range(1, NF + 1, 3):
            t = (f - 1) / FPS; s = W(t, T_ERUPT + 0.03 * k, 0.9)
            lw_puff_key(o, f, (1.3 * s, 1.0 * s, 0.9 * s)); o.location.z = z0 - 6.0 * (1 - s) + 0.5 * t
            o.keyframe_insert("location", frame=f)
    for L in P["glow"]:
        e0 = 300.0 if 'plume' in L.name else 7000.0                # the plume a grey ash cloud, warm only underneath
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = e0 * W(t, T_ERUPT, 0.3) * (1 + 0.6 * W(t, T_SURGE, 0.5)); L.data.keyframe_insert("energy", frame=f)
    tg = P["town_glow"].data
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; tg.energy = 300.0 * W(t, T_ERUPT, 0.3) * (1 + 0.5 * W(t, T_SURGE, 0.5)); tg.keyframe_insert("energy", frame=f)
    # ---- the cars: one after another down the lane, under the raised arm, toward us and out of the frame
    cars = []
    for k, col in enumerate(("#B9C2C9", "#2D5A8E", "#C33A2A", "#E6E2D6", "#3B3F45")):
        c = s1_car(f"town car {k}", col); cars.append(c)
        y0 = 4.0 + 2.9 * k; v = 7.5
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = max(0.0, t - T_CARS)
            y = y0 - v * s
            c.location = (S1_LANE + 0.05 * math.sin(0.7 * t + k), y, s1_ground_z(S1_LANE, y) if y > 8 else 0.0); c.keyframe_insert("location", frame=f)
    crank_u = lambda t: ease(min(1.0, max(0.0, (t - T_UP0) / (T_UP1 - T_UP0))))
    # ---- his body: the start at the eruption, the lean into each turn of the crank, the wave, the flinch, the walk
    def body(t):
        p = P0.copy()
        p.z += 0.07 * lw_kick(t - T_ERUPT - 0.05, 0.12)
        p.z += 0.05 * lw_kick(t - T_SURGE, 0.12)
        cr = W(t, T_UP0, 0.25) * (1 - W(t, T_UP1, 0.25))                   # his whole body rides each turn of the crank
        p.z -= 0.025 * cr * (1 + math.sin(2 * math.pi * REVS * crank_u(t)))
        yaw = math.radians(-30) * W(t, T_ERUPT - 0.05, 0.3) * (1 - W(t, T_GRAB - 0.35, 0.3)) \
            + math.radians(3) * cr * math.sin(2 * math.pi * REVS * crank_u(t) + 1.2) \
            - math.radians(30) * W(t, T_WAVE0, 0.4) * (1 - W(t, T_GO - 1.0, 1.0)) + math.radians(40) * W(t, T_GO - 1.0, 1.0)
        return p, yaw
    for f in range(1, NF + 1):                             # at the end he turns after the cars, leaning into the run
        t = (f - 1) / FPS; p, yaw = body(t); p.z += 0.03 * lw_kick(t - T_GO, 0.15); data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (-12 * lw_kick(t - T_ERUPT - 0.05, 0.2) + (8 + 5 * math.sin(2 * math.pi * REVS * crank_u(t))) * W(t, T_GRAB, 0.3) * (1 - W(t, T_LET, 0.3))
                                       - 10 * lw_kick(t - T_SURGE, 0.25) + 10 * W(t, T_GO - 0.5, 0.8), 0,
                                       3 * math.sin(2 * math.pi * (t - T_WAVE0) / 1.0) * W(t, T_WAVE0, 0.3) * (1 - W(t, T_WAVE1, 0.3))), 0, DUR + 0.4)
    # ---- the crank, built where his near hand turns it: its hub just in front of that shoulder
    sc.frame_set(F(T_GRAB)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    wind, other = sides[0], sides[1]                                              # the hand on the post's side winds
    sh = acts._shoulder(data, wind)
    osh = acts._shoulder(data, other)
    HUB = Vector((sh.x - 0.01, sh.y - 0.18, sh.z - 0.08))
    wheel, TOP = s1_crank(HUB, osh.x)
    th = lambda t: 2 * math.pi * REVS * crank_u(t)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; wheel.rotation_euler = (0, th(t), 0); wheel.keyframe_insert("rotation_euler", frame=f)
    knob = lambda t: HUB + Vector((S1_CRANK_R * math.cos(th(t)), 0.065, -S1_CRANK_R * math.sin(th(t))))
    # ---- the gate: down until he winds it; each turn of the crank lifts it, and it stays up
    gate = P["gate"]
    ang = lambda t: math.radians(68) * crank_u(t)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; gate.rotation_euler = (0, ang(t), 0); gate.keyframe_insert("rotation_euler", frame=f)
    data.reach(wind, knob, T_GRAB, T_LET, lead=0.45, back=None, elbow_out=0.4)
    RK = [(T_LET + 0.55, (0.12, 0.1, -0.07)), (T_GO - 0.2, (0.09, 0.09, -0.09)), (DUR + 0.4, (0.08, 0.09, -0.09))]
    data.reach(wind, lw_hand(data, wind, RK), RK[0][0], DUR + 0.3, lead=0.55, back=None, elbow_out=0.4)
    WK = [(T_UP0 + 0.55, (0.08, 0.12, 0.0))]                 # his free hand waves the cars on while the other still winds
    t = T_UP0 + 0.95; k = 0
    while t < T_WAVE1 - 0.2:
        WK.append((t, (0.07, 0.15, 0.08) if k % 2 == 0 else (0.11, 0.07, 0.03))); t += 0.45; k += 1
    WK += [(max(T_SURGE + 0.1, WK[-1][0] + 0.35), (0.06, 0.1, 0.06)), (DUR + 0.4, (0.08, 0.09, -0.08))]
    WK = sorted({round(a, 3): b for a, b in WK}.items())
    data.reach(other, lw_hand(data, other, WK), WK[0][0], DUR + 0.3, lead=0.5, back=None, elbow_out=0.35)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((3.2, -3.6, 0.8))
    data.look_at(LENS, 0.0, max_yaw=40, blend=0.0)
    data.look_at(Vector((-3.0, S1_RIDGE_Y, 7.0)), T_ERUPT + 0.05, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(HUB, T_GRAB - 0.3, max_yaw=50, max_pitch=18, blend=0.3)                  # eyes down to it, the brim kept off his face
    data.look_at(Vector((-1.5, 5.0, 2.5)), T_UP0 + 0.6, max_yaw=55, max_pitch=40, blend=0.3)
    data.look_at(Vector((S1_LANE, -1.0, 0.7)), T_LET, max_yaw=55, blend=0.3)
    data.look_at(Vector((-2.0, S1_RIDGE_Y, 8.0)), T_SURGE, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((S1_LANE, -4.0, 0.7)), T_GO - 0.1, max_yaw=50, blend=0.3)
    data.expression("alarmed", T_ERUPT, T_GRAB - 0.05, blend=0.15)
    data.expression("determined", T_GRAB, T_SURGE - 0.1, blend=0.2)
    data.expression("worried", T_SURGE, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low, three-quarter from the road side of the gate, the street and the ridge behind him
    CAM = Vector((2.3, -3.8, 1.35)); LOOK = Vector((-0.4, 8.0, 1.9))
    CAM, LOOK = compose.frame_data(data, CAM, LOOK, 18.0, face_at=(0.58, 0.4), height=0.36, t=0.45 * DUR)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=18.0, fstop=11.0)
    camera_path(cam, lambda t: (CAM + Vector((-0.1, 0.2, 0.0)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))))
    founts = P["founts"]
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=("gate crank", "gate winch housing"),
                boxes=[],
                conseq=[("the ridge rips open and a curtain of lava fountains bursts up over the town", lambda: founts, T_ERUPT, DUR, {"whole": False}),
                        ("he winds the crank and the striped gate arm swings up over the road", lambda: lw_drawn("gate arm", "gate post", "gate stop"), T_UP0 + 0.3, T_UP1 + 0.4, {"whole": False, "moves": True}),
                        ("the town's cars pour out under the raised gate, past him", lambda: meshes(cars), T_CARS + 0.3, T_WAVE1, {"whole": False})])
