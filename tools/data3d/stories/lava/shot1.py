"""BEAT 1, THE HOOK: "A volcano keeps erupting right beside one Icelandic town, and everyone had to run."

Grindavik's main street by day, low painted houses with coloured tin roofs down both sides, the black ridge over the
roofs and the eruption's black ash plume over it. The driver shuts his front door on it, throws his bag into his
tipper truck and drives out of town."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the siren pole's foot, at the kerb
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX, S1_FGAP = 1.6, 1.4             # the row of vents: its middle (x) and the gap between two vents
S1_CARX = 0.3                          # the leaving car's line up the street (pre-flight r1s: in the left lane the bomb hid it on still 3)
S1_HIT = (-0.62, 1.5, 0.0)              # (r1n: at -0.4 he hid it; at -0.95 the frame edge cut it; q1d: in the right lane it fell behind him: the left lane, its smash low so the car up the street stays in sight)
S1_HOME = (-1, 2)                      # his house: the left row's third, its door at street level
S1_HOME_BASE = 0.05
S1_SEE = 65.0                          # his quarter turn off the lens as he stands looking up at it
S1_NV = 5                              # the vents: a row of five fountains, each one seen on its own


def s1_ground_z(x, y):
    """the street flat, the land round the town rolling, and the ridge rising behind it to the fissure"""
    z = -0.07 if abs(x) < 1.1 else 0.0                    # (the road's own deck lies in this shallow bed: the kit's road, never the rock showing through it)
    if abs(x) > 2.4: z += 0.15 * lw_fbm(x * 0.3, y * 0.3, 3) + 0.03 * (abs(x) - 2.4)
    r = max(0.0, (y - 9.0) / 6.0)
    z += 8.0 * (r * r * (3 - 2 * r) if r < 1 else 1.0) + (0.5 * lw_fbm(x * 0.15, y * 0.2, 7) if y > 8.5 else 0.0)
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
        K.box(name + " taillight", (sx * 0.34, 1.2, 0.44), (0.24, 0.02, 0.13), lw_emit("taillight", "#FF1408", 12.0), bev=0.01, parent=root)
    K.box(name + " bumper", (0, -1.21, 0.22), (1.0, 0.06, 0.12), K.mat("car bumper", "#2A2A2C", rough=0.5), bev=0.02, parent=root)
    # ROUND 7 (seen close): built from its parts, not a painted block: door shut-lines, handles, mirrors, rims, a grille,
    # the plates, wipers, a rear bumper, mud on the sills
    seam = K.mat("car shut line", "#0C0C0D", rough=0.6); chrome = lw_metal("car trim", "#9EA2A6", rough=0.3)
    rim = lw_metal("car rim", "#B4B8BC", rough=0.35); plate = lw_paint("number plate", "#E8E6DE", rough=0.5)
    for sx in (-1, 1):
        for y in (-0.35, 0.42, 1.0):
            K.box(name + " door seam", (sx * 0.503, y, 0.48), (0.006, 0.008, 0.36), seam, bev=0.0, parent=root)
        K.box(name + " door seam", (sx * 0.503, 0.32, 0.27), (0.006, 1.3, 0.006), seam, bev=0.0, parent=root)
        for y in (0.3, 0.9):
            K.box(name + " door handle", (sx * 0.508, y, 0.52), (0.012, 0.1, 0.025), chrome, bev=0.004, parent=root)
        K.box(name + " mirror", (sx * 0.54, -0.38, 0.62), (0.09, 0.07, 0.07), paint, bev=0.02, parent=root)
        K.box(name + " mirror glass", (sx * 0.54, -0.34, 0.62), (0.07, 0.005, 0.05), glass, bev=0.0, parent=root)
        K.box(name + " sill mud", (sx * 0.5, 0.0, 0.2), (0.01, 1.3, 0.06), K.mat("car mud", "#3A332C", rough=0.95), bev=0.0, parent=root)
        for y in (-0.78, 0.8):
            K.cyl(name + " rim", (sx * 0.515, y, 0.2), 0.12, 0.012, rim, rot=(0, math.pi / 2, 0), v=24, parent=root)
            K.cyl(name + " hub", (sx * 0.522, y, 0.2), 0.035, 0.012, seam, rot=(0, math.pi / 2, 0), v=12, parent=root)
    K.box(name + " grille", (0, -1.205, 0.37), (0.4, 0.02, 0.08), seam, bev=0.005, parent=root)
    K.box(name + " plate", (0, -1.245, 0.22), (0.3, 0.01, 0.07), plate, bev=0.003, parent=root)
    K.box(name + " plate", (0, 1.225, 0.33), (0.3, 0.01, 0.07), plate, bev=0.003, parent=root)
    K.box(name + " rear bumper", (0, 1.21, 0.22), (1.0, 0.06, 0.12), K.mat("car bumper", "#2A2A2C", rough=0.5), bev=0.02, parent=root)
    for sx in (-0.2, 0.2):
        K.box(name + " wiper", (sx, -0.58, 0.58), (0.3, 0.01, 0.012), seam, bev=0.0, parent=root).rotation_euler = (math.radians(-30), 0, 0.15)
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
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, lw_noise("moss hill ground", "#343A2A", "#56603F", scale=0.35, rough=1.0, bump=0.35, detail=10))   # (coordinator, r1t: the black boulder bank behind the town read as the WALL, which shot 2 builds: the ridge is a smooth mossy hill in haze)   # REAL rock (Poly Haven), at a real size: BLACK lava rock (board B8: "a brown dirt bank")
    FX.road(a=(0, -7.5), b=(0, 12.5), width=2.3, line=True, shoulders=0, seed=5, z=-0.045, name="street road")      # the kit's real road: scanned asphalt, a worn centre line
    kerb = ph_mat("concrete_wall_008", scale=1.0, tint="#C8C4BC", name="kerb concrete")
    for sx in (-1, 1):
        K.box("kerb", (sx * 1.15, 2.5, 0.04), (0.12, 20, 0.08), kerb, bev=0.01)
        K.box("pavement", (sx * 1.45, 2.5, 0.035), (0.5, 20, 0.07), ph_mat("concrete_wall_008", scale=1.6, tint="#A8A49C", name="pavement"), bev=0.005)
    houses = []
    for sx in (-1, 1):
        y = -7.2 if sx < 0 else -6.6             # the street starts well in front of the ridge: two rows of houses down it
        k = 0
        while y < 9.5:
            w = rnd.uniform(3.2, 4.0); d = rnd.uniform(2.6, 3.0)       # Grindavik houses, not sheds (board after the fire test)
            hs = town_house(f"town house {sx}_{k}", (sx * (1.65 + d / 2), y + w / 2, 0), yaw=-sx * math.pi / 2, w=w, d=d, storeys=1,   # LOW painted tin houses (board B8: "grey clapboard terraces")
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A")[(k + (sx > 0)) % 4], wall=("#B44A3C", "#E9D9A2", "#BFD3DD", "#F1EEE6", "#7E9A86")[(k + 2 * (sx > 0)) % 5], base=(S1_HOME_BASE if (sx, k) == S1_HOME else 0.3), seed=k)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    lava_rock("street ash", 260, (-1.05, 1.05, -5.0, 9.0), lambda x, y: 0.012, seed=21, r=(0.015, 0.05), moss=0.0,   # cinders and ash fallen on the street
              avoid=lambda x, y: -1.6 < y < 1.7 and abs(x + 0.5) < 0.34)   # (none where he runs)
    lava_rock("lava field rock", 60, (-14, 14, -6, 8), s1_ground_z, seed=3, r=(0.04, 0.12), moss=0.6, avoid=lambda x, y: abs(x) < 5.2)
    # the slope up to the ridge is old lava field: broken black blocks and moss, never one smooth brown sheet (EMPTY
    # measured the bare slope as 30% of the set), with the town's power line and a gravel track climbing it
    lava_rock("ridge slope stone", 160, (-7, 10, 8.5, 15.0), s1_ground_z, seed=12, r=(0.02, 0.05), moss=0.7)
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
    # the lava is ON the ridge, not only in the air (board B18: "a bonfire cone on a dirt bank, no glow, no lava"):
    # glowing tongues run down the black slope from the fissure toward the town, each a lobe that widens as it comes
    for k, (x0_, y_end) in enumerate(((S1_FX - 3.6, 10.6), (S1_FX - 0.4, 11.6), (S1_FX + 2.9, 10.9), (S1_FX + 5.4, 12.2))):
        xc = lambda y, x0_=x0_, k=k: x0_ + 0.45 * math.sin(0.9 * y + 1.7 * k) + 0.12 * (S1_RIDGE_Y - y)
        hw = lambda y: 0.3 + 0.1 * (S1_RIDGE_Y - y)
        def tz(x, y, xc=xc, hw=hw, y_end=y_end):
            d = abs(x - xc(y)) / hw(y); e = max(0.0, (y_end + 0.5 - y) / 0.5)
            return s1_ground_z(x, y) + 0.14 - 0.34 * d * d - 0.34 * e * e
        pass                                               # (pre-flight: "the ridge's glowing streaks look like painted stripes": the tongues are cut)
    founts, spat, cores = [], [], []
    core = lw_emit("fountain core", "#FF9A20", 7.0)
    spm = lw_emit("lava spatter", "#FF7A10", 5.0); spd = lw_noise("cooled spatter", "#140E0B", "#3A2A20", scale=20, rough=0.9)
    for k in range(S1_NV):
        x = S1_FX + (k - (S1_NV - 1) / 2) * S1_FGAP
        z0 = s1_ground_z(x, S1_RIDGE_Y) - 0.2
        o = K.empty(f"fissure vent {k}", (x, S1_RIDGE_Y, z0))      # the vent: its fountain is a gas built in shot1, on its own clock
        o["base_z"] = z0; founts.append(o)
        for j in range(14):
            spat.append(K.sph(f"fissure spatter {k}_{j}", (x, S1_RIDGE_Y, z0), rnd.uniform(0.04, 0.09), spm if j % 3 else spd, seg=8, ring=6))
    puffs = []                                           # the plume is a gas, built in shot1 on the eruption's clock
    gate = None                                          # (the siren on its pole is cut: the board read its top as a broken disc at the frame's edge)
    glow = [lw_point(f"fissure light {k}", (S1_FX + x, S1_RIDGE_Y - 1.5, fz + 2.5), 0.0, col=(1.0, 0.4, 0.1), r=2.0) for k, x in enumerate((-3.5, 0, 3.5))]
    plume_lit = [lw_point(f"plume underlight {k}", (S1_FX + x, S1_RIDGE_Y + 2.0, fz + 5.0), 0.0, col=(1.0, 0.35, 0.08), r=3.0) for k, x in enumerate((-4, 4))]
    town_glow = lw_area("eruption glow on the town", (0, 12, 7), (0, 0, 0.5), 0.0, 14, col=(1.0, 0.5, 0.2))

    # ICELAND, unmissable (board B8: "nothing says Iceland"): the flag on a pole off a house front on each side of the
    # street, and the doors of the nearest houses left standing open behind the people who ran
    blue = lw_paint("flag blue", "#02529C", rough=0.7); white = lw_paint("flag white", "#F4F4F0", rough=0.7); red = lw_paint("flag red", "#DC1E35", rough=0.7)
    for k, (sx, y) in enumerate(((1, 7.4), (-1, 6.4), (1, 5.2), (-1, 4.0), (1, 2.8))):
        c = Vector((sx * 1.18, y, 1.52))
        for nm, off, size, m in (("field", (0, 0, 0), (0.54, 0.012, 0.38), blue), ("white bar", (-0.08, 0, 0), (0.11, 0.016, 0.38), white), ("white band", (0, 0, 0), (0.54, 0.016, 0.11), white),
                                 ("red bar", (-0.08, 0, 0), (0.055, 0.02, 0.38), red), ("red band", (0, 0, 0), (0.54, 0.02, 0.055), red)):
            K.box(f"icelandic flag {k} {nm}", tuple(c + Vector(off)), size, m, bev=0.0)
        o = K.cyl(f"flag pole {k}", (sx * 1.3, y, 1.74), 0.014, 0.82, lw_metal("flag pole", "#D8D8D4", rough=0.4), v=10)
        o.rotation_euler = (0, math.radians(90), 0)
    # EVERYONE HAD TO RUN: one car pulling away far up the street, whole in the frame, its tail lights to us (the
    # open front doors are cut: the board read their slabs as white boxes at the frame's edge)
    # (coordinator, after the bomb blocked twice: no car leaving up the street and no bomb: HE is the one who runs,
    # in his own truck, and the street he leaves is empty)
    # a house across the end of the street, under the ridge: its red tin roof slopes toward the lens
    town_house("town house at the street's end", (1.3, 10.4, s1_ground_z(1.3, 9.0)), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.5, roof="#B8352B", wall="#E9D9A2", seed=3)
    bpy.context.view_layer.update()
    for o in bpy.data.objects:                             # (the near left houses' door steps stood in the frame's corner as bare pale blocks: cut)
        if o.name.endswith(" step") or " step." in o.name:
            c = o.matrix_world.translation
            if c.x < 0 and -4.0 < c.y < 3.5: o.hide_render = True; o.hide_viewport = True
    def light():
        k = iceland_light(sun_elev=26, sun_az=-35, sun=3.0, sky=0.4, haze=1.4)           # the world's one bright day (the reset, 2026-11-25: no dusk)
        ph_sky("kloofendal_48d_partly_cloudy_puresky", strength=0.6, rot=math.radians(20))   # the same REAL sky as the wall's beats (Poly Haven)
        return k
    return dict(light=light, cores=cores, founts=founts, spat=spat, puffs=puffs, gate=gate, glow=glow + plume_lit, town_glow=town_glow, houses=houses, fz=fz)


def s1_duffel(name="duffel bag"):
    """HIS DUFFEL BAG (coordinator, r1t: "a red cylinder stuck to his side"): a soft holdall, its body sagging between
    two dark end panels, two carry straps looped over its top, a zip along it; built along x about its centre."""
    canvas = lw_canvas("duffel canvas", "#B0382A"); dark = K.mat("duffel trim", "#24221F", rough=0.8)
    root = K.empty(name, (0, 0, 0))
    body = K.capsule(name + " body", (-0.12, 0, 0), (0.12, 0, 0), 0.075, canvas, parent=root)
    body.scale = (1.0, 1.0, 0.82)
    for sx in (-1, 1):
        K.cyl(name + " end", (sx * 0.15, 0, -0.004), 0.066, 0.022, dark, rot=(0, math.pi / 2, 0), v=24, parent=root)
    K.box(name + " zip", (0, 0, 0.061), (0.22, 0.012, 0.006), dark, bev=0.002, parent=root)
    for sy in (-1, 1):                                    # the two carry straps, looped over the top
        a = Vector((-0.06, sy * 0.045, 0.05)); b = Vector((0.06, sy * 0.045, 0.05)); top = Vector((0, sy * 0.03, 0.12))
        K.capsule(name + " strap", tuple(a), tuple(top + Vector((-0.03, 0, 0))), 0.008, dark, parent=root)
        K.capsule(name + " strap", tuple(top + Vector((-0.03, 0, 0))), tuple(top + Vector((0.03, 0, 0))), 0.008, dark, parent=root)
        K.capsule(name + " strap", tuple(top + Vector((0.03, 0, 0))), tuple(b), 0.008, dark, parent=root)
    return root


def shot1():
    """EVERYONE HAD TO RUN, and so does he (coordinator, after r1t: "a different camera for every still").
    1 ESTABLISH (the cutaway, him far off): down the main street, the town's roofs low in the frame, the hill behind
    it soft in the haze, and a huge black ash plume rising off it with an orange-lit foot, the biggest thing there is.
    2 Close on the pavement: he runs toward us with his duffel bag in both hands, the plume over the roofs behind him.
    3 At his parked truck: he heaves the bag up over the tipper's side, arms up, the bag in the air at the rail.
    4 From the roadside ahead: one hand on the cab door, the other on the grab handle, a foot up on the step, while the
    other cars roll out of town past his truck in their own dust."""
    R = math.radians
    W = lw_win
    yaw_of = lambda dx, dy: math.atan2(dx, -dy)
    T_E = 1.0                                           # the establishing wide ends
    T_B = 2.15; T_C = 3.4                               # the cuts: to the truck, to the roadside
    P = place_grindavik_street()
    light = P["light"]
    data = load_data()
    # ---- the eruption: ONE huge black ash column off the hill, orange-lit at its foot (r1t: "no plume, a thin fire
    # fringe"); the fountains, the glowing slot and its spatter are cut
    for v in P["founts"]: v.hide_render = True; v.hide_viewport = True
    for o in P["spat"]: o.hide_render = True; o.hide_viewport = True
    for o in bpy.data.objects:
        if o.name.startswith("fissure glow"): o.hide_render = True; o.hide_viewport = True
        if o.type == "LIGHT" and o.name.startswith(("fissure light", "plume underlight")):
            o.data.energy = 0.0; o.hide_render = True
    PX = S1_FX - 4.0; PY = S1_RIDGE_Y + 3.0; PZ = s1_ground_z(PX, PY)
    plumes = []
    for k, (dx, w_, h_, dy) in enumerate(((0.0, 9.0, 44.0, 0.0), (-4.5, 6.0, 30.0, 1.5), (4.0, 6.5, 34.0, 1.0))):
        plumes.append(ash_plume((PX + dx, PY + dy, PZ - 0.5), w=w_, h=h_, S=7.0, dens=16.0, lean=(-0.02 + 0.02 * k, 0.03), col=(0.05, 0.047, 0.045),
                                seed=4.1 + 2.7 * k, t_end=DUR + 1.0, name=f"eruption plume {k}"))
    for k, dx in enumerate((-4.0, 0.0, 4.0)):
        lw_point(f"plume fire light {k}", (PX + dx, PY - 1.0, PZ + 1.5), 60000.0, col=(1.0, 0.42, 0.1), r=2.5)      # the orange foot
    P["town_glow"].data.energy = 900.0
    # ---- HIS truck, parked at the kerb further down the street, its nose out of town (q1v: on the kerb side the
    # houses' downpipes leave him no pavement, so he runs DOWN THE STREET and climbs in at the driver's door, on the
    # street side); a foot rung and a grab handle at that door (at his size the kit's step is at his hip)
    bpy.context.view_layer.update()
    DC = bpy.data.objects[f"town house {S1_HOME[0]}_{S1_HOME[1]} door"].matrix_world.translation.copy()
    XF = DC.x; YD = DC.y
    XT = -0.55; YT = YD - 2.4
    tr = FX.truck(name="his tipper truck", loc=(XT, YT, 0.0), yaw=0.0, lights=True, power=90.0, seed=2)
    troot = tr["root"]
    SIDE = XT + 0.65                                    # its street side: the driver's door
    steel = lw_metal("cab grab handle", "#B9BCBE", rough=0.3)
    DOOR_Y = YT - 1.85 + 0.62
    K.box("cab foot rung", (SIDE + 0.05, DOOR_Y + 0.02, 0.15), (0.1, 0.22, 0.025), steel, bev=0.004)
    for z_ in (0.3, 0.62):                              # (q1w: at his size the handle and the door are within 0.19 m of his shoulders, or his arm locks)
        K.box("cab grab handle mount", (SIDE + 0.02, DOOR_Y + 0.08, z_), (0.04, 0.03, 0.03), steel, bev=0.004)
    K.cyl("cab grab handle", (SIDE + 0.045, DOOR_Y + 0.08, 0.46), 0.014, 0.36, steel, v=12)
    GRAB = Vector((SIDE + 0.06, DOOR_Y + 0.08, 0.45)); DOORP = Vector((SIDE + 0.02, DOOR_Y - 0.09, 0.44))
    FC = Vector((-0.8, -0.6, 0.0))                      # he faces in to the door, three-quarter to the lens ahead of the truck
    PD = (GRAB + DOORP) / 2 - FC * 0.19; PD.z = 0.0
    # ---- the other cars, far up the street in the far lane, rolling out of town toward us in their dust
    cars = []
    for k, (col, y0, v) in enumerate((("#2F5E8C", YD + 12.0, 2.6), ("#C9C6BE", YD + 17.0, 2.4))):
        c = s1_car(f"car leaving {k}", col); cars.append(c)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; c.location = (0.95, y0 - v * t, 0.0); c.keyframe_insert("location", frame=f)
        for j in range(5):
            tj = 2.9 + 0.3 * j
            FX.dust_puff(base=(0.95, y0 - v * tj + 0.9, 0.05), w=0.7, h=0.6, t0=tj, dur=1.4, col=(0.5, 0.46, 0.4), dens=4.0, seed=7.0 + 3 * k + j, lean=(0.0, 0.3), name=f"dust off the cars {k} {j}")
    # ---- him: off his doorstep into the street, running down it and round his truck's tail to its street side
    T_AT = 2.45; T_WIND = 2.5; T_REL = 2.98; T_FLY = 0.9
    T_GO = 3.2; T_STEP = 3.85
    PS = Vector((-0.6, YD + 0.3, 0.0)); PM = Vector((SIDE + 0.3, YT + 1.85 + 0.47, 0.0))
    PT = Vector((SIDE + 0.3, YT - 0.2, 0.0))            # (q1w: 0.3 off the side, or the bag he throws goes through the rail)
    BED = Vector((XT + 0.05, PT.y - 0.1, 0.82))          # where the bag lands, on the tipper's floor
    data.place(PS.x, PS.y, math.degrees(yaw_of(0.5, -1.0)))
    kit = hard_hat(data)
    sc.frame_set(1); bpy.context.view_layer.update()
    data.walk_to((PM.x, PM.y), 0.0, 0.85, step=0.17, lift=0.08, bob=0.024)          # (q1w POP: running from his door, not a sprint at the end)
    data.walk_to((PT.x, PT.y), 0.85, T_AT, step=0.21, lift=0.09, bob=0.026)
    sc.frame_set(F(T_AT)); bpy.context.view_layer.update(); YA = data.arm.rotation_euler.z
    YB = yaw_of(0.1, -1.0)                             # (the throw: three-quarter to the high lens, the truck at his right)
    while YB - YA > math.pi: YB -= 2 * math.pi
    while YB - YA < -math.pi: YB += 2 * math.pi
    for f in range(F(T_AT) + 1, F(T_GO) + 1):
        t = (f - 1) / FPS; data._kobj(t, loc=tuple(PT), rot=YA + (YB - YA) * W(t, T_AT, 0.4))
    data.walk_to((PD.x, PD.y), T_GO, T_STEP, step=0.15, lift=0.05, bob=0.016)      # along the truck to its cab door
    sc.frame_set(F(T_STEP)); bpy.context.view_layer.update(); YS = data.arm.rotation_euler.z
    YC = yaw_of(FC.x, FC.y)                             # to the door and the handle, three-quarter to the lens ahead of the truck
    while YC - YS > math.pi: YC -= 2 * math.pi
    while YC - YS < -math.pi: YC += 2 * math.pi
    for f in range(F(T_STEP) + 1, NF + 8):
        t = (f - 1) / FPS; data._kobj(t, loc=tuple(PD), rot=YS + (YC - YS) * W(t, T_STEP, 0.45))
    # ---- the bag in both hands, at his belly as he runs (hitched up once on the way); swung down, then heaved up over
    # his right shoulder and thrown up over the tipper's side
    sc.frame_set(1); bpy.context.view_layer.update()
    def frame_at(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        m = (acts._shoulder(data, "L") + acts._shoulder(data, "R")) / 2; f_ = data.forward(); f_.z = 0; f_.normalize()
        return m, f_, Vector((-f_.y, f_.x, 0.0))
    HITCH = lambda t: 0.06 * W(t, 1.2, 0.15) * (1 - W(t, 1.37, 0.2)) + 0.06 * W(t, 1.85, 0.15) * (1 - W(t, 2.02, 0.2))                 # (q1v HOLD: a hitch of the bag mid-run)
    def carried(t):
        m, f_, l_ = frame_at(t)
        return m + f_ * 0.145 + Vector((0, 0, -0.17 + HITCH(t)))
    lw_layer(data, "spine", lambda t: (14 * W(t, 0.95, 0.3) * (1 - W(t, T_AT - 0.2, 0.3)) + 16 * W(t, T_WIND, 0.15) * (1 - W(t, T_WIND + 0.15, 0.15)) - 12 * W(t, T_WIND + 0.2, 0.2) * (1 - W(t, T_REL + 0.25, 0.3)), 0, 0), 0.0, DUR + 0.4)    # leaning into the run; down into the heave; back as it goes up
    sc.frame_set(F(T_REL)); bpy.context.view_layer.update()
    mR, fR, lR = frame_at(T_REL)
    REL = mR + fR * 0.18 - lR * 0.04 + Vector((0, 0, 0.0))       # (q1w: over his shoulder it was in his head, and out of his reach) up in front of his face
    def bag_at(t):
        if t < T_WIND: return carried(t)
        if t < T_REL:
            a = carried(T_WIND); u = (t - T_WIND) / (T_REL - T_WIND)
            m, f_, l_ = frame_at(t)
            low = m + f_ * 0.12 - l_ * 0.04 + Vector((0, 0, -0.22))
            if u < 0.35: return a.lerp(low, ease(u / 0.35))
            return low.lerp(REL, ease((u - 0.35) / 0.65))
        return None
    G = Vector((0, 0, -9.8)); V0 = (BED - REL - 0.5 * G * T_FLY * T_FLY) / T_FLY
    def flying(t):
        s_ = min(T_FLY, t - T_REL); return REL + V0 * s_ + 0.5 * G * s_ * s_
    duffel = s1_duffel("his duffel bag"); duffel.scale = (1.12, 1.12, 1.12)       # (q1v: under 12% of the frame, a purse; q1w: at 1.25 it was in his chest)
    sides = sorted("LR", key=lambda s_: (acts._shoulder(data, s_) - data.pos()).dot(frame_at(0.0)[2]), reverse=True)    # sides[0]: his left
    for k_, sd in enumerate(sides):
        sg = 1.0 if k_ == 0 else -1.0
        def grip(t, sg=sg):
            if t < T_REL:
                m, f_, l_ = frame_at(t); return bag_at(t) + l_ * (sg * 0.04) + Vector((0, 0, 0.1))       # (q1x: round its ends his arms were in it) on its straps
            m, f_, l_ = frame_at(t); return m + f_ * 0.17 + l_ * (sg * 0.06) + Vector((0, 0, 0.08 - 0.2 * W(t, T_REL + 0.1, 0.45)))     # (q1w: a world point behind him as he walked off: arms behind his back) his arms follow it up, open
        data.reach(sd, grip, 0.0, T_STEP - 0.3, lead=0.05, back=None, elbow_out=0.3)       # (q1x FLUID: no drop to a relaxed arm; the cab takes the hands from here)
    # ---- at the cab: a foot up on the rung, a hand on the door, a hand on the grab handle
    sc.frame_set(F(T_STEP + 0.3)); bpy.context.view_layer.update()
    hs = sorted("LR", key=lambda s_: (acts._shoulder(data, s_) - GRAB).length)     # the hand nearer the grab handle takes it
    data.reach(hs[0], lambda t: GRAB.copy(), T_STEP + 0.05, DUR + 0.5, lead=0.3, back=None, elbow_out=0.2)
    data.reach(hs[1], lambda t: DOORP.copy(), T_STEP + 0.15, DUR + 0.5, lead=0.3, back=None, elbow_out=0.2)
    near_leg = min("LR", key=lambda s_: (data.arm.matrix_world @ data.pb[f"leg.{s_}"].head - GRAB).length)
    lw_layer(data, f"leg.{near_leg}", lambda t: (-50 * W(t, T_STEP + 0.2, 0.3), 0, 0), T_STEP, DUR + 0.4)
    lw_layer(data, f"shin.{near_leg}", lambda t: (62 * W(t, T_STEP + 0.2, 0.3), 0, 0), T_STEP, DUR + 0.4)
    # ---- face and head
    PLUME = Vector((PX, PY, PZ + 12.0))
    data.look_at(Vector((PM.x, PM.y - 2.0, 0.4)), 0.0, max_yaw=30, max_pitch=30, blend=0.0)
    data.look_at(PLUME, 1.15, max_yaw=35, max_pitch=30, blend=0.3)                     # a look back up at it as he runs
    data.look_at(Vector((PT.x, PT.y - 2.0, 0.4)), 1.75, max_yaw=30, max_pitch=30, blend=0.3)
    data.look_at(REL + Vector((0, 0, 0.1)), T_AT - 0.1, max_yaw=40, max_pitch=40, blend=0.45)      # (q1w: at the bed his face turned 79 off the lens) at the bag going up
    data.look_at(GRAB + Vector((0, -0.2, 0.3)), T_GO + 0.1, max_yaw=35, max_pitch=35, blend=0.5)
    data.expression("alarmed", 0.0, T_AT, blend=0.15)
    data.expression("determined", T_AT, DUR + 1.0, blend=0.25)
    data.finish()
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t < T_REL:
            p = bag_at(t); _m, f_, l_ = frame_at(t); yaw = math.atan2(l_.y, l_.x)
            duffel.location = p; duffel.rotation_euler = (0, 0, yaw)
        else:
            duffel.location = flying(t); duffel.rotation_euler = (1.8 * min(T_FLY, t - T_REL), 0, yaw)
            if t - T_REL >= T_FLY: duffel.location = BED
        duffel.keyframe_insert("location", frame=f); duffel.keyframe_insert("rotation_euler", frame=f)
    TS = 0.68 * DUR
    print("S1 door", tuple(round(v, 2) for v in DC), "release", tuple(round(v, 2) for v in REL), "v0", tuple(round(v, 2) for v in V0), "still 3 at", round(TS, 2), "T_REL", T_REL, flush=True)
    # ---- the lens: 1 the establishing wide from far down the street; 2 low in the street ahead of him as he runs at
    # us, the plume over the roofs behind him; 3 from up over the far lane, down at him heaving the bag up at his
    # truck's side; 4 low in the street ahead of the truck's nose, back at him climbing in, the cars far up the street
    WCAM = Vector((0.3, YD - 15.0, 2.2)); WLOOK = Vector((-0.6, PY, 10.0))
    sc.frame_set(F(1.63)); bpy.context.view_layer.update(); PR = data.pos()
    CA0 = Vector((SIDE + 0.35, YT - 3.3, 0.5)); LA0 = PR + Vector((0, 0, 0.4))         # (q1w POP: close, he ran into the lens) long, from ahead of the truck's nose
    CA, LA = compose.frame_data(data, CA0, LA0, 70.0, face_at=(0.45, 0.6), height=0.36, t=1.63)
    CB0 = Vector((SIDE + 1.2, PT.y - 1.3, 1.5)); LB0 = PT + Vector((0, 0, 0.45))
    CB, LB = compose.frame_data(data, CB0, LB0, 35.0, face_at=(0.55, 0.55), height=0.36, t=TS)
    CC0 = Vector((SIDE + 0.0, YT - 4.2, 0.6)); LC0 = PD + Vector((0, 0, 0.4))
    CC, LC = compose.frame_data(data, CC0, LC0, 45.0, face_at=(0.4, 0.6), height=0.36, t=DUR - 0.05)
    print("S1 CAM A", tuple(round(v, 2) for v in CA), "B", tuple(round(v, 2) for v in CB), "C", tuple(round(v, 2) for v in CC), "truck street side x", round(SIDE, 2), flush=True)
    cam = K.camera(tuple(CA), tuple(LA), lens=70.0, fstop=11.0)
    lw_cut(cam, lambda t: ((CA, LA) if t < T_B else (CB, LB) if t < T_C else (CC, LC)) + (data.pos() + Vector((0, 0, 0.4)),),
           lambda t: (WCAM, WLOOK, Vector((0.0, YD, 2.0))), 0.0, T_E, 35.0, 35.0)
    for f in range(1, NF + 8):                     # the lens per set-up: long in the street, normal up high, a little long ahead of the truck
        t = (f - 1) / FPS
        cam.data.lens = 35.0 if t < T_E else 70.0 if t < T_B else 35.0 if t < T_C else 45.0
        cam.data.keyframe_insert("lens", frame=f)
    from character import _fcurves
    for fc in _fcurves(cam.data.animation_data.action):
        for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=("his duffel bag", "cab grab handle"), cutaway=(0.0, T_E),
                boxes=[],
                conseq=[("a huge black ash plume rises off the hill over the town's roofs", lambda: plumes, 0.0, T_E, {"whole": False}),
                        ("he runs down the street with his bag in both hands", lambda: meshes([duffel]), 1.25, T_B, {"whole": False, "moves": True}),
                        ("he heaves his bag up over his head and throws it into his truck", lambda: meshes([duffel]), T_REL - 0.3, T_REL + 0.5, {"whole": False, "moves": True}),
                        ("the other cars roll out of town toward his truck", lambda: meshes(cars), T_C, DUR, {"whole": False})])
