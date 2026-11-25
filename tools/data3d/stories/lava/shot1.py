"""BEAT 1, THE HOOK: "A volcano has erupted nine times beside one town in Iceland, and the whole town had to run."

Grindavik's main street on a bright grey afternoon, low houses with coloured tin roofs down both sides, the ridge above
the town at the end of it. The ridge rips open and a curtain of lava fountains bursts up along it under a boiling
plume. REDESIGN after board round 3 (a road gate's arm can never be whole in an upright frame at his size, and read as a
toy): the digger driver at the town's hand-cranked air-raid SIREN on its pole at the kerb winds its crank hand over
hand, the siren's rotor spins up and wails; at its call the town's cars pour out down the street, headlights on, past
him and out of the frame; he waves them on; the fountains surge; the street is empty and he runs after them."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the siren pole's foot, at the kerb
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX, S1_FGAP = 2.0, 0.8              # the nine vents: the row's middle (x) and the gap between two vents


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
    tyre = lw_rubber("car tyre", "#141414", rough=0.8)
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


S1_SIREN_Z = 1.42                      # the siren's rotor (z), on top of its pole


def s1_siren():
    """the town's hand-cranked air-raid siren: a galvanised pole at the kerb with a foot plate and bolts, a red siren on
    top - a drum of louvred stator slots round a rotor that spins inside it, a domed cap, a flared horn mouth on each
    side - and the gearbox on the pole at his shoulder that the crank turns (built by s1_crank). Returns the rotor."""
    post_m = lw_metal("gate steel", "#8C9196"); red = lw_paint("siren red", "#B3201A", rough=0.38); dark = lw_metal("siren slots", "#1A1A1C", rough=0.5)
    K.cyl("gate post", (S1_PIV.x, S1_PIV.y + 0.12, S1_SIREN_Z / 2), 0.05, S1_SIREN_Z, post_m, v=16)
    K.box("gate foot", (S1_PIV.x, S1_PIV.y + 0.12, 0.02), (0.3, 0.3, 0.04), post_m, bev=0.005)
    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        K.cyl("gate foot bolt", (S1_PIV.x + 0.11 * dx, S1_PIV.y + 0.12 + 0.11 * dy, 0.05), 0.014, 0.03, dark, v=8)
    c = Vector((S1_PIV.x, S1_PIV.y + 0.12, S1_SIREN_Z + 0.12))
    K.cyl("siren drum", tuple(c), 0.16, 0.2, red, v=32)
    K.cyl("siren band", tuple(c + Vector((0, 0, -0.11))), 0.17, 0.03, post_m, v=32)
    K.cyl("siren band", tuple(c + Vector((0, 0, 0.11))), 0.17, 0.03, post_m, v=32)
    for k in range(10):                                   # the stator's slots, all round the drum
        a = 2 * math.pi * k / 10
        o = K.box("siren slot", tuple(c + Vector((0.162 * math.cos(a), 0.162 * math.sin(a), 0))), (0.012, 0.06, 0.13), dark, bev=0.0)
        o.rotation_euler = (0, 0, a)
    K.sph("siren cap", tuple(c + Vector((0, 0, 0.12))), 0.165, red, scale=(1, 1, 0.45), seg=32, ring=12)
    for sx in (-1, 1):                                    # the two flared horn mouths
        K.cyl("siren horn", tuple(c + Vector((sx * 0.22, 0, 0))), 0.09, 0.14, red, rot=(0, math.pi / 2, 0), v=24)
        K.cyl("siren horn mouth", tuple(c + Vector((sx * 0.3, 0, 0))), 0.12, 0.03, dark, rot=(0, math.pi / 2, 0), v=24)
    rotor = K.empty("gate pivot", tuple(c))
    for k in range(6):                                    # the rotor's vanes, seen spinning through the slots
        a = 2 * math.pi * k / 6
        o = K.box("siren rotor vane", (c.x + 0.075 * math.cos(a), c.y + 0.075 * math.sin(a), c.z), (0.15, 0.02, 0.15), lw_metal("rotor steel", "#B8BCC0", rough=0.3), bev=0.003, parent=rotor)
        o.rotation_euler = (0, 0, a)
    # (round 5: the yellow sign plate is cut: the board read it as a flat toy plate, and EDGES caught it at the frame's edge)
    return rotor


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
    K.cyl("gate crank knob", (S1_CRANK_R, 0.04, 0), 0.016, 0.07, lw_rubber("gate handle", "#22201E"), rot=(math.pi / 2, 0, 0), v=14, parent=wh)
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
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, ph_mat("aerial_rocks_02", scale=1.4, tint="#4E4A45", name="lava field rock ground"))   # REAL rock (Poly Haven), at a real size
    K.box("street asphalt", (0, 2.5, 0.004), (4.0, 20, 0.01), ph_mat("asphalt_02", scale=1.6, tint="#9A9A9C", name="street asphalt"), bev=0)
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        K.box("kerb", (sx * 2.05, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 2.55, 2.5, 0.035), (0.9, 20, 0.07), ph_mat("concrete_wall_008", scale=1.6, tint="#A8A49C", name="pavement"), bev=0.005)
    for y in range(-8, 10, 2):
        K.box("centre line", (0, y + 0.5, 0.011), (0.08, 0.9, 0.004), K.mat("road paint", "#E9E4D4", rough=0.6), bev=0)
    houses = []
    for sx in (-1, 1):
        y = 0.9 if sx < 0 else 1.4
        k = 0
        while y < 8.0:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            hs = town_house(f"town house {sx}_{k}", (sx * (3.3 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d,
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A")[(k + (sx > 0)) % 3], wall=WALLS[k % len(WALLS)], base=0.3, seed=k)
            houses.append(hs); y += w + rnd.uniform(0.5, 0.9); k += 1
    lava_rock("street ash", 260, (0.2, 1.9, -3.0, 9.0), lambda x, y: 0.012, seed=21, r=(0.015, 0.05), moss=0.0,   # cinders and ash fallen on the street
              avoid=lambda x, y: abs(x - 1.15) < 0.45 and abs(y - 0.42) < 0.5)
    patch = K.mat("road patch", "#1E1E20", rough=0.9); rp = lw_random.Random(5)
    for k in range(10):                                   # the old road's patched cracks
        o = K.box("road crack seal", (rp.uniform(-1.6, 1.6), -2.5 + 1.2 * k, 0.012), (rp.uniform(0.6, 1.4), 0.025, 0.004), patch, bev=0.0)
        o.rotation_euler = (0, 0, rp.uniform(-0.6, 0.6))
    lava_rock("lava field rock", 160, (-14, 14, -6, 14), s1_ground_z, seed=3, avoid=lambda x, y: abs(x) < 3.2 and y < 9.0)
    # the slope up to the ridge is old lava field: broken black blocks and moss, never one smooth brown sheet (EMPTY
    # measured the bare slope as 30% of the set), with the town's power line and a gravel track climbing it
    lava_rock("ridge slope rock", 520, (-7, 10, 8.5, 15.2), s1_ground_z, seed=11, r=(0.08, 0.32), moss=0.06)
    lava_rock("ridge slope stone", 700, (-5, 8, 8.5, 15.0), s1_ground_z, seed=12, r=(0.03, 0.09), moss=0.1)
    pole = lw_noise("power pole wood", "#4A3626", "#6E5238", scale=20, rough=0.9, stretch=(1, 1, 6))
    wire = K.mat("power line", "#151515", rough=0.5)
    tops = []
    for k in range(7):
        y = 9.0 + 1.1 * k; x = -3.2 + 0.25 * k
        z = s1_ground_z(x, y); h = 1.5
        K.cyl("power pole", (x, y, z + h / 2), 0.035, h, pole, v=10)
        K.box("power pole arm", (x, y, z + h - 0.1), (0.6, 0.04, 0.04), pole, bev=0.005)
        tops.append(Vector((x, y, z + h - 0.08)))
    for a, b in zip(tops, tops[1:]):
        for dx in (-0.25, 0.25):
            p, q = a + Vector((dx, 0, 0)), b + Vector((dx, 0, 0)); d = q - p
            o = K.cyl("power line wire", ((p + q) / 2), 0.006, d.length, wire, v=6, bev=0)
            o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    grav = lw_noise("gravel track", "#6A645C", "#8A8478", scale=30, rough=0.95, bump=0.5)
    for k in range(10):
        y = 8.8 + 0.65 * k; x = 1.2 + 1.4 * math.sin(0.5 * k)
        o = K.box("gravel track", (x, y, s1_ground_z(x, y) + 0.01), (0.7, 0.75, 0.03), grav, bev=0.005)
        o.rotation_euler = (math.atan2(s1_ground_z(x, y + 0.4) - s1_ground_z(x, y - 0.4), 0.8), 0, 0.7 * math.cos(0.5 * k) * 0.5)
    for k in range(6):                                     # the far blue mountains over the ridge
        x = -40 + 16 * k
        K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    # the fissure: a glowing line along the ridge and NINE vents on it, one for each eruption, close enough that the
    # whole row is in the frame and far enough apart to count; each vent a fountain of fire (a volume, white-hot in
    # its core) throwing glowing spatter that arcs and falls; the plume over it is smoke (volumes), lit from below
    fz = s1_ground_z(S1_FX, S1_RIDGE_Y)
    # board round 3: "thin pale-pink glowing spikes like neon tubes ... no molten body, no spatter, no fall-back",
    # "rising from a visible glowing crack": the fissure is a torn, glowing slot along the ridge, each fountain a
    # thick ORANGE body (a dim core, the volume cooler), throwing glowing clots AND dark cooled spatter that falls back
    fl = lava_mat("fissure lava", heat=2.0, scale=3.0, fresh=1.0)
    for k in range(14):
        x = S1_FX - 6.0 + 12.0 * k / 13; w_ = 0.45 + 0.25 * math.sin(1.7 * k)
        o = K.box("fissure glow", (x, S1_RIDGE_Y + 0.12 * math.sin(2.3 * k), s1_ground_z(x, S1_RIDGE_Y) - 0.05), (0.95, w_, 0.2), fl, bev=0.05)
        o.rotation_euler = (0, 0, 0.15 * math.sin(3.1 * k))
    founts, spat, cores = [], [], []
    core = lw_emit("fountain core", "#FF9A20", 7.0)
    spm = lw_emit("lava spatter", "#FF7A10", 5.0); spd = lw_noise("cooled spatter", "#140E0B", "#3A2A20", scale=20, rough=0.9)
    for k in range(9):
        x = S1_FX + (k - 4) * S1_FGAP
        z0 = s1_ground_z(x, S1_RIDGE_Y) - 0.2
        o = K.empty(f"fissure vent {k}", (x, S1_RIDGE_Y, z0))      # the vent: its fountain is a gas built in shot1, on its own clock
        o["base_z"] = z0; founts.append(o)
        for j in range(14):
            spat.append(K.sph(f"fissure spatter {k}_{j}", (x, S1_RIDGE_Y, z0), rnd.uniform(0.04, 0.09), spm if j % 3 else spd, seg=8, ring=6))
    puffs = []                                           # the plume is a gas, built in shot1 on the eruption's clock
    gate = s1_siren()
    glow = [lw_point(f"fissure light {k}", (S1_FX + x, S1_RIDGE_Y - 1.5, fz + 2.5), 0.0, col=(1.0, 0.4, 0.1), r=2.0) for k, x in enumerate((-3.5, 0, 3.5))]
    plume_lit = [lw_point(f"plume underlight {k}", (S1_FX + x, S1_RIDGE_Y + 2.0, fz + 5.0), 0.0, col=(1.0, 0.35, 0.08), r=3.0) for k, x in enumerate((-4, 4))]
    town_glow = lw_area("eruption glow on the town", (0, 12, 7), (0, 0, 0.5), 0.0, 14, col=(1.0, 0.5, 0.2))

    def light():
        k = iceland_light(sun_elev=4, sun_az=-45, sun=1.0, sky=0.12, warm=(1.0, 0.6, 0.4), haze=2.0)     # the town dim under an orange-tinted sky; the eruption lights it
        ph_sky("kloofendal_overcast_puresky", strength=0.8, rot=math.radians(180))      # board round 5: "light the afternoon": the brief's grey BRIGHT afternoon (Poly Haven)
        return k
    return dict(light=light, cores=cores, founts=founts, spat=spat, puffs=puffs, gate=gate, glow=glow + plume_lit, town_glow=town_glow, houses=houses, fz=fz)


def shot1():
    """THE ROAD GATE. A low lens three-quarter from the road, the street running away behind him to the ridge. The ridge
    bursts open; he startles round at it, takes the gate's crank and winds it hand over fist: the striped arm swings up
    high over the road; the cars pour out past him; he waves them on; the fountains surge; he sets off after the cars."""
    T_ERUPT = 0.0                                          # board round 5: "open on the fissure already ripping"
    T_GRAB = 0.22 * DUR; T_UP0 = T_GRAB + 0.05; T_UP1 = T_UP0 + 1.5
    T_LET = T_UP1 + 0.1
    T_CARS = 0.2 * DUR
    T_WAVE0 = 0.38 * DUR + 0.3; T_WAVE1 = 0.8 * DUR
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
    T_NINE = 0.14                                          # one vent bursts every T_NINE s, left to right: nine, counted
    vents = P["founts"]; cols = []
    for k, v in enumerate(vents):                        # each vent a FOUNTAIN OF FIRE as a gas: torn tongues licking up a
        tk = T_ERUPT + T_NINE * k                        # glowing column, bursting in turn, nine, counted
        cols.append(lw_fire_column(f"fissure fountain {k}", (v.location.x, S1_RIDGE_Y, v["base_z"]), w=1.6, h_fire=6.0, h_smoke=3.0,
                                   lean=(0.1, 0.4), t_end=DUR + 1.0, seed=1.9 * k, fire=14.0, smoke_d=1.5, rise=3.5,
                                   keys=[(max(0.0, tk - 0.04), 0.0), (tk + 0.18, 1.0)], grow=True))
    for k, x in enumerate((-4.0, 0.0, 4.0)):             # the plume: a wall of grey gas and ash boiling off the whole fissure, leaning downwind
        cols.append(lw_steam(f"eruption plume {k}", (S1_FX + x, S1_RIDGE_Y + 1.0, P["fz"] + 1.5), w=4.5, h=16.0, seed=4.4 * k + 1, col=(0.46, 0.45, 0.46),
                             dens=3.0, lean=(-0.35, 0.3), rise=1.6, keys=[(T_ERUPT + 0.1 * k, 0.0), (T_ERUPT + 0.1 * k + 1.2, 1.0)], t_end=DUR + 1.0))
    P["founts"] = cols[:9]
    for o in P["spat"]: o.hide_render = True          # board round 4: the spatter read as "sparklers, fireworks, snow": the fountains carry it
    for k, o in enumerate(P["spat"]):
        v = vents[k // 14]; x0 = v.location.x + rnd.uniform(-0.12, 0.12); tk = T_ERUPT + T_NINE * (k // 14)
        vx = rnd.uniform(-1.1, 1.1); vz = rnd.uniform(4.5, 7.5); per = 2 * vz / 9.8; ph = rnd.uniform(0, per)
        b0 = v["base_z"] + 0.2
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < tk + ph * 0.3: o.location = (x0, S1_RIDGE_Y, b0 - 1.0)
            else:
                u = (t - tk + ph) % per
                o.location = (x0 + vx * u, S1_RIDGE_Y - 0.25 * u, b0 + vz * u - 4.9 * u * u)
            o.keyframe_insert("location", frame=f)
    for k, o in enumerate(P["puffs"]):
        z0 = o.location.z
        for f in range(1, NF + 1, 3):
            t = (f - 1) / FPS; s = W(t, T_ERUPT + 0.03 * k, 0.9)
            lw_puff_key(o, f, (1.3 * s, 1.0 * s, 0.9 * s)); o.location.z = z0 - 6.0 * (1 - s) + 0.5 * t
            o.keyframe_insert("location", frame=f)
    for L in P["glow"]:
        e0 = 50.0 if "plume" in L.name else 1200.0                # the plume a grey ash cloud, warm only underneath
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; L.data.energy = e0 * W(t, T_ERUPT, 0.3) * (1 + 0.6 * W(t, T_SURGE, 0.5)); L.data.keyframe_insert("energy", frame=f)
    tg = P["town_glow"].data
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; tg.energy = 300.0 * W(t, T_ERUPT, 0.3) * (1 + 0.5 * W(t, T_SURGE, 0.5)); tg.keyframe_insert("energy", frame=f)
    # ---- the cars: one after another down the lane, under the raised arm, toward us and out of the frame
    cars = []
    for k, col in enumerate(("#B9C2C9", "#2D5A8E", "#C33A2A", "#E6E2D6", "#3B3F45")):
        c = s1_car(f"town car {k}", col); cars.append(c)
        y0 = 3.0 + 3.2 * k; v = 3.6
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; s = max(0.0, t - T_CARS)
            y = y0 - v * s
            c.location = (S1_LANE + 0.05 * math.sin(0.7 * t + k), y, s1_ground_z(S1_LANE, y) if y > 8 else 0.0); c.keyframe_insert("location", frame=f)
    # ---- ROUND 6 RESTAGE (coordinator on board 5, the talking head): no crank, no post in the lens. He RUNS IN from
    # the side of the street, in profile, to the kerb by the cars' lane and waves them through with a lit baton, his
    # whole arm going; he flinches as the fountains surge, then turns and runs after the last car
    T_IN0, T_IN1 = 0.12 * DUR, 0.38 * DUR
    PS = Vector((2.6, 1.4, 0.0)); PW = Vector((0.15, 0.35, 0.0))
    data._kobj(0.0, loc=tuple(PS), rot=math.radians(-75))
    data.walk_to((PW.x, PW.y), T_IN0, T_IN1)
    sc.frame_set(F(T_IN1)); bpy.context.view_layer.update()
    Y_IN = data.arm.rotation_euler.z; YW = math.radians(-55)
    YW = Y_IN + ((YW - Y_IN + math.pi) % (2 * math.pi) - math.pi)
    for f in range(F(T_IN1) + 1, NF + 1):
        t = (f - 1) / FPS; p = PW.copy()
        p.z += 0.05 * lw_kick(t - T_SURGE, 0.12) + 0.03 * lw_kick(t - T_GO, 0.15)
        p.y += 0.06 * W(t, T_SURGE, 0.3)                                     # a step back from the surge
        yaw = Y_IN + (YW - Y_IN) * W(t, T_IN1, 0.5) + math.radians(60) * W(t, T_GO - 0.6, 0.9)   # then round after the cars
        data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (10 * W(t, T_IN0, 0.3) * (1 - W(t, T_IN1, 0.4)) - 10 * lw_kick(t - T_SURGE, 0.25) + 10 * W(t, T_GO - 0.5, 0.8), 0,
                                       4 * math.sin(2 * math.pi * (t - T_WAVE0) / 0.9) * W(t, T_WAVE0, 0.3) * (1 - W(t, T_WAVE1, 0.3))), 0, DUR + 0.4)
    sc.frame_set(F(T_IN1 + 0.2)); bpy.context.view_layer.update()
    sides = sorted("LR", key=lambda s_: acts._shoulder(data, s_).x)
    other, low = sides[0], sides[1]                         # the arm toward the cars' lane waves; the other stays low
    WK = [(T_IN1 + 0.15, (0.08, 0.12, 0.02))]
    t = T_IN1 + 0.5; k = 0
    while t < T_WAVE1 - 0.2:
        WK.append((t, (0.07, 0.16, 0.1) if k % 2 == 0 else (0.11, 0.08, 0.02))); t += 0.45; k += 1
    WK += [(max(T_SURGE + 0.1, WK[-1][0] + 0.35), (0.06, 0.1, 0.06)), (DUR + 0.4, (0.08, 0.09, -0.08))]
    WK = sorted({round(a, 3): b for a, b in WK}.items())
    data.reach(other, lw_hand(data, other, WK), WK[0][0], DUR + 0.3, lead=0.6, back=None, elbow_out=0.35)
    LK = [(T_IN1 + 0.3, (0.07, 0.1, -0.1)), (DUR + 0.4, (0.07, 0.1, -0.11))]
    data.reach(low, lw_hand(data, low, LK), LK[0][0], DUR + 0.3, lead=0.6, back=None, elbow_out=0.35)
    gate = P["gate"]; spin = 0.0                              # the siren off up the street spins and wails from the start
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; spin += 2 * math.pi * 7.0 / FPS
        gate.rotation_euler = (0, 0, spin); gate.keyframe_insert("rotation_euler", frame=f)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((-0.2, -3.4, 0.5))
    data.look_at(Vector((-2.0, S1_RIDGE_Y, 7.0)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)
    data.look_at(Vector((S1_LANE, -1.0, 0.7)), T_IN1 - 0.2, max_yaw=55, blend=0.3)       # at the cars he waves through
    data.look_at(Vector((-2.0, S1_RIDGE_Y, 8.0)), T_SURGE, max_yaw=60, max_pitch=30, blend=0.3)
    data.look_at(Vector((S1_LANE, -4.0, 0.7)), T_GO - 0.1, max_yaw=50, blend=0.3)
    data.expression("alarmed", T_ERUPT, T_IN1, blend=0.15)
    data.expression("determined", T_IN1 + 0.05, T_SURGE - 0.1, blend=0.2)
    data.expression("worried", T_SURGE, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the light baton in his waving hand: a marshal's orange wand, lit, riding his hand every frame
    bat = K.cyl("light baton", (0, 0, 0), 0.013, 0.2, lw_emit("baton glow", "#FF8A1E", 6.0), v=12)
    pb = data.pb[f"hand.{other}"]
    for f in range(1, NF + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        mw = data.arm.matrix_world @ pb.matrix
        d_ = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
        bat.location = data.arm.matrix_world @ pb.tail + d_ * 0.07
        bat.rotation_euler = d_.to_track_quat('Z', 'Y').to_euler()
        bat.keyframe_insert("location", frame=f); bat.keyframe_insert("rotation_euler", frame=f)
    # ---- the lens: LOW in the road, looking up the street: the fissure's curtain of fire across the top half from the
    # first frame, the cars' headlights streaming down at us, him at the kerb in profile waving them through. One lens.
    CAM, LOOK = compose.frame_data(data, Vector((0.45, -3.2, 0.32)), Vector((-0.2, 15.0, 4.2)), 30.0, face_at=(0.62, 0.42), height=0.34, t=T_IN1 + 0.6)
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30.0, fstop=16.0)
    lw_cut(cam, lambda t: (CAM + Vector((0.0, 0.12, 0.02)) * ease(t / DUR), LOOK, data.pos() + Vector((0, 0, 0.6))),
           lambda t: (CAM, LOOK, data.pos()), -1.0, -1.0, 30.0, 30.0)
    founts = P["founts"]
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=("light baton",), cutaway=None,
                boxes=[],
                conseq=[("the ridge rips open and a curtain of lava fountains bursts up over the town", lambda: founts, T_ERUPT, DUR, {"whole": False}),
                        ("he waves the town's cars through and they pour down the street past him at us", lambda: meshes(cars), T_CARS + 0.3, T_WAVE1, {"whole": False, "moves": True})])
