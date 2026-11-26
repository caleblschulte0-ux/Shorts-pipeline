"""BEAT 1, THE HOOK: "A volcano keeps erupting right beside one Icelandic town, and everyone had to run."

Grindavik's main street by day, low painted houses with coloured tin roofs down both sides, the black ridge over the
roofs. A curtain of lava fountains stands on the ridge from the first frame. The digger driver looks back up at it and
bolts down the middle of the street at the lens, lava bombs landing on the road behind him."""

S1_PIV = Vector((0.85, 0.0, 0.5))      # the siren pole's foot, at the kerb
S1_CRANK_R = 0.045                     # the winch crank's knob, out from its hub
S1_LANE = -1.0                         # the cars' lane (x)
S1_RIDGE_Y = 15.0                      # the fissure's line on the ridge
S1_FX, S1_FGAP = 1.6, 1.4             # the row of vents: its middle (x) and the gap between two vents
S1_CARX = -0.2                         # the leaving car's line up the street
S1_HIT = (-0.6, 2.2, 0.0)              # where the lava bomb lands on the street, behind him
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
    lw_grid("lava field ground", -40, 40, -14, 40, 140, 110, s1_ground_z, ph_mat("rock_face_01", scale=2.2, tint="#0B0B0C", name="lava field rock ground", rough=0.95, bump=1.2))   # REAL rock (Poly Haven), at a real size: BLACK lava rock (board B8: "a brown dirt bank")
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
                            roof=("#B8352B", "#2F5E8C", "#3F7A4A", "#C9A23A")[(k + (sx > 0)) % 4], wall=("#B44A3C", "#E9D9A2", "#BFD3DD", "#F1EEE6", "#7E9A86")[(k + 2 * (sx > 0)) % 5], base=0.3, seed=k)
            houses.append(hs); y += w + rnd.uniform(0.4, 0.8); k += 1
    lava_rock("street ash", 260, (-1.05, 1.05, -5.0, 9.0), lambda x, y: 0.012, seed=21, r=(0.015, 0.05), moss=0.0,   # cinders and ash fallen on the street
              avoid=lambda x, y: -1.6 < y < 1.7 and abs(x + 0.5) < 0.34)   # (none where he runs)
    lava_rock("lava field rock", 160, (-14, 14, -6, 14), s1_ground_z, seed=3, avoid=lambda x, y: abs(x) < 5.2 and y < 10.0)
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
        lw_grid(f"lava tongue {k}", x0_ - 2.2, x0_ + 2.6, y_end - 0.2, S1_RIDGE_Y + 0.3, 44, 40, tz, fl)
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
    car = FX.car(name="car leaving", loc=(S1_CARX, 4.7, 0.0), yaw=math.pi, kind="hatch", col="#B9BEC4", seed=3)["root"]      # the kit's real car, its tail lamps lit
    for f in range(1, NF + 1):
        car.location = (S1_CARX, 4.7 + 0.98 * (f - 1) / FPS, 0.0); car.keyframe_insert("location", frame=f)
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


def shot1():
    """EVERYONE HAD TO RUN, so he runs. A wide lens low in the main street, pulling back ahead of him: the low painted
    houses with their tin roofs down both sides, the black ridge over the roofs with a curtain of lava fountains on it
    from the first frame. He stands at the kerb looking back up at it, mouth open; he bolts down the middle of the
    street at us, arms pumping, glowing bombs landing on the road behind him; he is big in the frame, terrified, the
    fire bigger behind; he reaches us."""
    T_ERUPT = 0.0
    T_SURGE = 0.74 * DUR
    T_RUN = 0.18 * DUR                                     # he bolts
    W = lw_win
    P = place_grindavik_street()
    light = P["light"]
    data = load_data()
    PW = Vector((-0.55, 1.3, 0.0)); PM = Vector((-0.45, -0.74, 0.0)); PE = Vector((-0.43, -1.0, 0.0)); T_SLOW = 0.75 * DUR     # from the kerb by a front door, down the middle of the street, at us
    data.place(PW.x, PW.y, 0.0)
    kit = hard_hat(data)
    rnd = lw_random.Random(9)
    # ---- the eruption: the row of fountains stands on the ridge from the first frame and surges at T_SURGE
    vents = P["founts"]; rf = lw_random.Random(17)
    for v in vents: v.hide_render = True; v.hide_viewport = True
    # the eruption is the KIT's: a fissure curtain of strand spray on the ridge, its gas above it, its clots on real
    # arcs, every lava colour off the kit's chart (an orange emission over ~2 renders peach, a red over ~1 salmon)
    fo = FX.lava_fountain(base=(S1_FX, S1_RIDGE_Y, P["fz"]), h=10.0, w=1.3, length=7.5, clots=700, lean=(-0.25, 0.35), seed=17, splats=0,
                          t_end=DUR + 1.0, name="fissure fountain")
    P["founts"] = [fo["jet"]]
    for o in P["spat"]: o.hide_render = True
    clot = lw_emit("fountain clot", "#FFA51E", 0.9)          # (the bomb's flung bits: yellow-orange and dim)
    # ---- THE BOMB: one big clot comes down out of the fountains and smashes into the street behind him (still 3), and
    # lies there glowing and smoking to the end (still 4)
    T_HIT = 0.58 * DUR; HIT = Vector(S1_HIT); B0 = Vector((S1_FX - 1.0, S1_RIDGE_Y - 0.5, P["fz"] + 1.0)); TF = 1.7
    bomb = lw_block("lava bomb", tuple(B0), 0.27, lava_mat("bomb lava", heat=1.1, scale=9.0, glow="#FF8A10", fresh=0.15), rf, squash=0.9)
    vz0 = (HIT.z + 0.14 - B0.z + 0.5 * 9.8 * TF * TF) / TF
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; s_ = max(0.0, min(TF, t - (T_HIT - TF))); u_ = s_ / TF
        bomb.location = (B0.x + (HIT.x - B0.x) * u_, B0.y + (HIT.y - B0.y) * u_, B0.z + vz0 * s_ - 0.5 * 9.8 * s_ * s_); bomb.keyframe_insert("location", frame=f)
        bomb.rotation_euler = (3.0 * s_, 2.0 * s_, 0.0); bomb.keyframe_insert("rotation_euler", frame=f)
        bomb.hide_render = t < T_HIT - TF; bomb.keyframe_insert("hide_render", frame=f)
    splat = K.sph("lava bomb splat", (HIT.x, HIT.y, 0.012), 0.58, lava_mat("splat lava", heat=1.0, scale=6.0, glow="#FF8A10", fresh=0.45), scale=(1.0, 0.8, 0.07), seg=20, ring=8)
    for t_, sc_ in ((T_HIT - 0.04, 0.0), (T_HIT + 0.1, 1.0), (DUR + 1.0, 1.08)):
        fr = F(t_); splat.scale = (max(0.06, sc_), max(0.06, 0.8 * sc_), 0.07); splat.keyframe_insert("scale", frame=fr)
        splat.hide_render = sc_ < 0.06; splat.keyframe_insert("hide_render", frame=fr)
    for k in range(9):                                    # what it throws out as it bursts: glowing bits that skip across the road and lie there
        a_ = 2 * math.pi * k / 9 + rf.uniform(-0.3, 0.3); d_ = rf.uniform(0.5, 1.0); hz = rf.uniform(0.3, 0.6)
        o = lw_block(f"bit of the bomb {k}", (HIT.x, HIT.y, 0.03), rf.uniform(0.05, 0.09), clot, rf, squash=0.8)
        for f in range(F(T_HIT) - 1, NF + 1):
            u_ = min(1.0, max(0.0, ((f - 1) / FPS - T_HIT) / 0.4))
            o.location = (HIT.x + d_ * math.cos(a_) * u_, HIT.y + d_ * math.sin(a_) * u_, 0.03 + hz * 4 * u_ * (1 - u_)); o.keyframe_insert("location", frame=f)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=F(T_HIT) - 1); o.hide_render = False; o.keyframe_insert("hide_render", frame=F(T_HIT))
    FX.smoke_column(base=(HIT.x, HIT.y + 0.1, 0.05), w=0.7, h=2.6, seed=6.1, col=(0.12, 0.11, 0.1), dens=12.0, lean=(-0.15, 0.25), rise=1.4,
                    keys=[(T_HIT - 0.02, 0.0), (T_HIT + 0.3, 1.0), (DUR + 1.0, 0.85)], t_end=DUR + 1.0, name="smoke off the bomb")
    bl = lw_point("light of the bomb", (HIT.x, HIT.y - 0.1, 0.35), 0.0, col=(1.0, 0.4, 0.1), r=0.3)
    for t_, e_ in ((T_HIT - 0.03, 0.0), (T_HIT + 0.08, 900.0), (T_HIT + 0.6, 380.0), (DUR + 1.0, 320.0)):
        bl.data.energy = e_; bl.data.keyframe_insert("energy", frame=F(t_))
    for L in P["glow"]:                                   # its light: on the ridge rock, and warm on the underside of the smoke (constant: one grade through the shot)
        L.data.energy = 2600.0 if "plume" in L.name else 4200.0
    P["town_glow"].data.energy = 700.0                    # the fire lights the world: orange on the ridge top, the smoke's underside and the near roofs
    # ---- him: at the kerb looking back up at it, then he BOLTS down the street at us
    RUNV = (PM - PW) / (T_SLOW - T_RUN)
    to_cam = math.radians(26)                              # the lens is ahead of him and to his left: he comes at it three-quarter
    run_yaw = math.atan2(PM.x - PW.x, -(PM.y - PW.y))
    yaw_see = math.atan2(-0.5, 0.85) + math.radians(S1_SEE)                     # still 1: side-on across the street, a little toward us, his face in profile up at the fountains
    data.place(PW.x, PW.y, math.degrees(yaw_see))
    data._kobj(0.0, loc=tuple(PW), rot=yaw_see)
    data._kobj(T_RUN - 0.42, loc=tuple(PW), rot=yaw_see); data._kobj(T_RUN - 0.02, loc=tuple(PW), rot=run_yaw)      # he turns, then he runs
    data.walk_to((PM.x, PM.y), T_RUN, T_SLOW, step=0.24, lift=0.1, lean=34.0, bob=0.026, ramp=0.15)
    data.walk_to((PE.x, PE.y), T_SLOW, DUR + 0.3, step=0.09, lift=0.035, lean=20.0, bob=0.01)      # ...and he pulls up at the lens, still coming
    lw_layer(data, "spine", lambda t: (-12 * (1 - W(t, T_RUN - 0.15, 0.2)) + 8 * W(t, T_RUN, 0.3), 0, 0), 0, DUR + 0.4)
    RIDGE = Vector((-7.0, S1_RIDGE_Y, 12.0))               # the row's end on the lens's side: he looks back over the shoulder we can see
    CAM0 = PW + Vector((-0.25, -1.6, 1.0)); LOOK0 = PW + Vector((0.5, 3.0, 2.0))
    data.look_at(Vector((PW.x - 6.0, PW.y + 0.6, 8.0)), 0.0, max_yaw=42, max_pitch=32, blend=0.0)                    # back up at the fountains over his shoulder
    data.look_at(CAM0 + RUNV * 0.6, T_RUN + 0.15, max_yaw=50, max_pitch=30, blend=0.6)
    data.look_at(CAM0 + RUNV * (T_SLOW - T_RUN) + Vector((0.3, -0.6, 0.0)), 0.6 * DUR, max_yaw=55, max_pitch=8, blend=0.5)   # his face to us to the end              # the end: running out past us, his head back over his shoulder at the fire
    data.expression("alarmed", 0.0, DUR + 1.0, blend=0.1)
    UPF = lambda sg: ((-82, 0, -sg * 10), (-100, 0, -sg * 10), (0, 0, 0))      # a runner's arms: bent square, one fist up in front as the other elbow goes back
    LOW = lambda sg: ((56, 0, -sg * 14), (-74, 0, -sg * 6), (0, 0, 0))
    FLUNG = lambda sg: ((-58, 0, -sg * 34), (-72, 0, -sg * 14), (0, 0, 0))            # the end: both hands thrown up in front of him, palms out                     # the end: both arms thrown up
    WHOA = lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15))
    def pose(sd, t, P_):
        for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), P_(-1 if sd == "L" else 1)): data._k(bn, t, rot=r)
    HANG = lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10))
    SHIELD = "none"                         # the arm up at his hat covered his face on the last still: both arms keep pumping
    OUT = lambda sg: ((8, 0, -sg * 76), (0, 0, -sg * 8), (0, 0, 0))            # one arm flung out at the fountains
    sc.frame_set(1); bpy.context.view_layer.update()
    far = max("LR", key=lambda s_: acts._shoulder(data, s_).y); oth = "R" if far == "L" else "L"       # the arm on the ridge's side
    pose(far, 0.0, OUT); pose(oth, 0.0, HANG); pose(far, T_RUN - 0.25, OUT); pose(far, T_RUN - 0.05, WHOA); pose(oth, T_RUN - 0.1, WHOA)
    for f in range(F(T_RUN), NF + 8):                  # arms pumping, one forward as the other goes back (over the walk's own swing)
        t = (f - 1) / FPS; b_ = 0.5 + 0.5 * math.sin(2 * math.pi * (t - T_RUN) / 0.528); g_ = ease(min(1.0, (t - T_RUN) / 0.55)); e_ = ease(min(1.0, max(0.0, (t - T_SLOW + 0.1) / 0.5)))
        for sd, bb in (("L", b_), ("R", 1 - b_)):
            sg = -1 if sd == "L" else 1
            for bn, lo, up, wh, fl in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), LOW(sg), UPF(sg), WHOA(sg), FLUNG(sg)):
                r = tuple(((wh[i] * (1 - g_) + (lo[i] * (1 - bb) + up[i] * bb) * g_) * (1 - e_) + (fl[i] if sd in SHIELD else (lo[i] * (1 - bb) + up[i] * bb)) * e_) for i in range(3)); data._k(bn, t, rot=r)
    data.finish()
    from character import _fcurves                         # his shoulders a quarter turned off the lens as he runs at it (coordinator: "square to the lens in all four stills")
    for fc in _fcurves(data.arm.animation_data.action):
        if fc.data_path == "rotation_euler" and fc.array_index == 2:
            for kp in fc.keyframe_points:
                t_ = (kp.co[0] - 1) / FPS; dz = math.radians(30) * W(t_, T_RUN + 0.1, 0.4) - math.radians(6) * W(t_, 0.76 * DUR, 0.5)
                kp.co[1] += dz; kp.handle_left[1] += dz; kp.handle_right[1] += dz
            fc.update()
    # ---- the lens: ahead of him down the street, backing away slower than he runs: he starts small and left, down the
    # street, and comes up big at the right third, running out past it (coordinator: "make the distance read")
    X0, Y0, H0 = 0.58, 0.42, 0.36; X1, Y1, S1_ = 0.5, 0.47, 0.86; ZOOM = 0.24
    CAMr, LOOKr = compose.frame_data(data, CAM0, LOOK0, 24.0, face_at=(X0, Y0), height=H0, t=0.0)
    cam = K.camera(tuple(CAMr), tuple(LOOKr), lens=24.0, fstop=11.0)
    sc.frame_set(1); bpy.context.view_layer.update()
    pos0 = data.pos().copy(); F0 = data.arm.matrix_world @ data.pb["head"].head; hoff = F0 - pos0
    ax = (LOOKr - CAMr).normalized(); rt = ax.cross(Vector((0, 0, 1))).normalized(); up = rt.cross(ax).normalized()
    v0 = F0 - CAMr; D0 = v0.dot(ax); HF = D0 * 1.5; WF = HF * 9.0 / 16.0     # the frame's size in metres at his distance (a 36 mm gate on the tall side)
    XA, YA = 0.5 + v0.dot(rt) / WF, 0.5 + v0.dot(up) / HF                                 # where his head really sits on the first frame
    print("S1 LENS D0", round(D0, 2), "WF", round(WF, 2), "HF", round(HF, 2), "head at", round(XA, 2), round(YA, 2), flush=True)
    GROW = lambda t: ease(min(1.0, max(0.0, (t - T_SLOW) / 1.0)))      # he is only big once he has pulled up: a run that close is a smear
    def cam_at(t):
        sc.frame_set(F(t)); u = ease(min(1.0, max(0.0, (t - T_RUN) / (DUR - T_RUN)))) * 0.5 + 0.5 * min(1.0, max(0.0, (t - T_RUN) / (DUR - T_RUN)))
        g = GROW(t); s_ = 1.0 - 0.04 * u + (S1_ - 0.96) * g; zf = 1.0 + ZOOM * g; x_ = XA + (X1 - XA) * min(1.0, 1.6 * u); y_ = YA + (Y1 - YA) * g
        fp = data.pos() + hoff; fp.z = F0.z
        c = fp - ax * (D0 * s_) - rt * ((x_ - 0.5) * WF * s_ / zf) - up * ((y_ - 0.5) * HF * s_ / zf)
        return c, c + (LOOKr - CAMr), data.pos() + Vector((0, 0, 0.5))
    lw_cut(cam, cam_at, cam_at, -1.0, -1.0, 24.0, 24.0)
    for f in range(1, NF + 1):                             # ...and the lens closes on him as he reaches it: the last still is HIM, at the lens, from the waist up
        cam.data.lens = 24.0 * (1.0 + ZOOM * GROW((f - 1) / FPS)); cam.data.keyframe_insert("lens", frame=f)
    founts = P["founts"]
    return dict(lanes=[], kiosks=[], place="grindavik_street", light=light, data=data, rest=1, grips=(), cutaway=None,
                boxes=[],
                conseq=[("a curtain of lava fountains stands on the ridge over the town's roofs", lambda: founts, T_ERUPT, DUR, {"whole": False})])
