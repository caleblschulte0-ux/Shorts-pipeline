"""BEAT 5, THE PAYOFF: "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?"

The harbour quay at dawn: fishing boats at the quay, the town on the slope above it, the earth wall curving round
above the town, black lava spread up to the town's edge where three houses still burn. The lens is low on the quay. He
walks up the quay to his own house by the water carrying a lit lantern and hangs it on the hook of the post by his door;
it swings, glowing; across the dark town a few windows light up, one here, one there, only a handful; he turns to us
and spreads his hands wide: would you?"""

S5_HOOK = Vector((0.2, 1.1, 0.5))       # the hook's tip, on the post by his door (pointing -X, toward where he comes from)
S5_EDGE_X = -2.2                        # the quay's water edge (x)


S5_SLOPE = 0.45                         # the hill's rise per metre
S5_BASIN = (-4.6, -0.25, 2.5, 7.4)     # the boat basin cut into the quay (x0, x1, y0, y1): water between him and the town


def s5_water(x, y):
    """True where the harbour's water is: the basin in front of the town, and the open harbour off the quay's edge"""
    x0, x1, y0, y1 = S5_BASIN
    return (x0 - 30 < x < x1 and y0 < y < y1) or (x < S5_EDGE_X and y < y0)


def s5_slope_z(x, y):
    """the quay flat, the boat basin sunk in it, the town's slope rising behind it, the lava field on the right"""
    if s5_water(x, y): return -1.2
    z = 0.0
    if y > 4.8: z += S5_SLOPE * (min(y, 36.0) - 4.8)    # the town climbs the hill behind the harbour, row over row (steep: every row seen over the one below)
    z += 0.08 * lw_fbm(x * 0.3, y * 0.3, 51) * (1 if y > 4.8 else 0)
    return z


def s5_lantern():
    """a REAL hurricane lantern (Poly Haven's Lantern_01), its glass glowing with the flame in it, hung by its top: the
    pivot at the top of its bail, the lantern below it"""
    root = K.empty("lantern", (0, 0, 0))
    S_ = 1.35
    lm = ph_model("Lantern_01", (0, 0, -0.29 * S_), scale=S_, name="lantern body", parent=root)
    glow = lw_emit("lantern glow", "#FFB050", 3.0)
    for c in lm.children_recursive:
        if "glass" in c.name.lower():
            c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = glow
    L = lw_point("lantern light", (0, 0, -0.16), 25.0, col=(1.0, 0.7, 0.35), r=0.04)
    L.parent = root; L.location = (0, 0, -0.16)
    return root


def s5_lit_pane(house, k, t_on):
    """a window of a dark house that lights up at t_on (a pane in front of the dark one)"""
    p = house["windows"][k]
    lit = p.copy(); lit.data = p.data.copy(); bpy.context.collection.objects.link(lit)
    lit.name = p.name.replace("window pane", "window lit pane")
    lit.data.materials.clear(); lit.data.materials.append(lw_emit("window lit", "#FFC070", 2.5))
    lit.location.y -= 0.004
    lw_show([lit], t_on)
    return lit


def s5_boat(name, xy, yaw, hull, roof, seed=0):
    """one fishing boat afloat, built from its parts, facing +Y"""
    root = K.empty(name, (0, 0, 0))
    L_, B_ = 2.6, 1.05                                   # length, beam
    hm = ph_mat("container_side", scale=0.8, tint=hull, paint=True, rough=0.4, name=f"hull steel {hull}")
    stations = 12; ring = [(-1.0, 0.0), (-0.98, -0.22), (-0.8, -0.38), (-0.45, -0.48), (0.0, -0.5), (0.45, -0.48), (0.8, -0.38), (0.98, -0.22), (1.0, 0.0)]
    bm = LW_bmesh.new(); rows = []
    for i in range(stations + 1):
        u = i / stations; y = -L_ / 2 + L_ * u
        hw = B_ / 2 * (1.0 - max(0.0, (u - 0.55) / 0.45) ** 1.6) * (0.92 + 0.08 * math.sin(math.pi * min(u, 0.6) / 0.6)) + 0.01
        sheer = 0.02 + 0.16 * u ** 2.2; depth = 0.42 * (1.0 - 0.5 * max(0.0, u - 0.7) / 0.3)
        rows.append([bm.verts.new((px * hw, y, sheer + pz / 0.5 * depth)) for px, pz in ring])
    for i in range(stations):
        for j in range(len(ring) - 1):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    bm.faces.new(list(reversed(rows[0])))
    LW_bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + " hull"); bm.to_mesh(me); bm.free(); me.materials.append(hm)
    for p_ in me.polygons: p_.use_smooth = True
    h = lw_link(bpy.data.objects.new(name + " hull", me)); h.parent = root
    so = h.modifiers.new("t", 'SOLIDIFY'); so.thickness = 0.02
    band = K.mat("hull waterline red", "#7A1E16", rough=0.6)
    K.box(name + " boot top", (0, -0.1, -0.17), (B_ * 0.98, L_ * 0.8, 0.05), band, bev=0.02, parent=root)
    deck = ph_mat("black_painted_planks", scale=0.8, name="boat deck planks")
    K.box(name + " deck", (0, -0.15, 0.0), (B_ * 0.9, L_ * 0.78, 0.03), deck, bev=0.01, parent=root)
    white = ph_mat("corrugated_iron_02", scale=0.6, tint="#EDEBE4", paint=True, rough=0.45, name="wheelhouse white")
    glass = K.mat("car glass", "#1E262C", rough=0.05, metal=0.3)
    wy = -0.55
    K.box(name + " wheelhouse", (0, wy, 0.3), (0.66, 0.7, 0.58), white, bev=0.03, parent=root)
    K.box(name + " wheelhouse roof", (0, wy + 0.04, 0.62), (0.76, 0.84, 0.06), K.mat(f"wheelhouse roof {roof}", roof, rough=0.45), bev=0.015, parent=root)
    for wx in (-0.18, 0.18):
        K.box(name + " window", (wx, wy + 0.36, 0.43), (0.24, 0.02, 0.16), glass, bev=0.0, parent=root)
    for sx in (-1, 1):
        for wy_ in (-0.15, 0.15):
            K.box(name + " window", (sx * 0.335, wy + wy_, 0.43), (0.02, 0.22, 0.16), glass, bev=0.0, parent=root)
    steel = lw_metal("mast steel", "#8A8E92")
    K.cyl(name + " mast", (0, 0.35, 0.85), 0.025, 1.7, steel, v=10, parent=root)
    K.cyl(name + " crosstree", (0, 0.35, 1.45), 0.015, 0.6, steel, rot=(0, math.pi / 2, 0), v=8, parent=root)
    K.sph(name + " mast lamp", (0, 0.35, 1.72), 0.035, lw_emit("mast lamp", "#FFF1D0", 4.0), seg=10, ring=6, parent=root)
    K.cyl(name + " boom", (0, 0.75, 0.6), 0.015, 0.8, steel, rot=(math.radians(70), 0, 0), v=8, parent=root)
    for sx in (-1, 1):                                   # the stern gantry, an A-frame over the transom
        K.cyl(name + " gantry", (sx * 0.38, -L_ / 2 + 0.12, 0.42), 0.02, 0.8, steel, rot=(math.radians(-12), sx * math.radians(8), 0), v=8, parent=root)
    K.cyl(name + " gantry top", (0, -L_ / 2 + 0.04, 0.8), 0.02, 0.72, steel, rot=(0, math.pi / 2, 0), v=8, parent=root)
    rail = lw_metal("boat rail", "#D8DADC", rough=0.35)
    for sx in (-1, 1):                                   # the rails along her sides
        K.cyl(name + " rail", (sx * (B_ / 2 - 0.05), 0.15, 0.2), 0.008, L_ * 0.55, rail, rot=(math.pi / 2, 0, 0), v=6, parent=root)
        for j in range(4):
            K.cyl(name + " stanchion", (sx * (B_ / 2 - 0.05), -0.25 + 0.27 * j, 0.11), 0.008, 0.18, rail, v=6, parent=root)
    ph_model("lifebuoy", (0, wy + 0.37, 0.3), rot=(math.pi / 2, 0, 0), scale=0.3, name=name + " lifebuoy", parent=root)
    for j in range(3):                                   # old tyres over her side for fenders (REAL, Poly Haven)
        ph_model("old_tyre", (B_ / 2 + 0.04, -0.6 + 0.55 * j, -0.05), rot=(0, math.pi / 2, 0), scale=0.38, name=name + f" fender tyre {j}", parent=root)
    lw_local(root)
    root.location = (xy[0], xy[1], -0.45 + 0.22); root.rotation_euler = (0, 0, yaw)
    return root


def place_harbour_dawn():
    """THE HARBOUR AT DAWN: the concrete quay and its water edge, fishing boats moored, his house by the water with the
    lantern post at its door, and up the slope behind, the whole story in one frame (board after the fire test: "put
    the standing town and the earth wall in frame, so 'the wall saved the rest' is seen"): on the left the town
    standing, street over street, below the earth wall; the black lava field heaped up behind the wall; on the right,
    past the wall's end, the tongue of lava that got round it, its ridged glowing front run into the backs of three
    houses that burn from inside."""
    rnd = lw_random.Random(61)
    ground = ph_mat("aerial_rocks_02", scale=1.4, tint="#5A5650", name="town ground rock")          # REAL rock ground (Poly Haven), at a real size
    lw_grid("town slope", -26, 26, 1.2, 40, 208, 128, s5_slope_z, ground)          # the town's land, the basin sunk in it
    stone = ph_mat("concrete_wall_008", scale=1.5, tint="#8A8580", name="harbour stone")
    x0, x1, y0, y1 = S5_BASIN
    for k in range(12):                                    # the basin's stone walls: its town side climbs with the slope
        y = y0 + (y1 - y0) * (k + 0.5) / 12; top = s5_slope_z(x1 + 0.3, y)
        K.box("harbour basin wall", (x1 + 0.12, y, (top - 1.2) / 2), (0.25, (y1 - y0) / 12 + 0.02, top + 1.2), stone, bev=0.01)
    K.box("harbour basin wall", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.1, -0.6), (x1 - S5_EDGE_X + 0.2, 0.25, 1.24), stone, bev=0.01)
    top = s5_slope_z(x1 + 0.3, y1 + 0.3)
    K.box("harbour head wall", ((x0 - 30 + x1) / 2, y1 + 0.12, (top - 1.2) / 2), (x1 - x0 + 30, 0.25, top + 1.2), stone, bev=0.01)
    qc = ph_mat("concrete_wall_008", scale=2.0, tint="#B5B1AA", name="quay concrete")
    K.box("quay concrete", (6.0, -1.55, -0.128), (16.4, 7.9, 0.24), qc, bev=0.02)                  # the quay he walks: concrete right up to the basin
    K.box("quay concrete", ((x1 + 14.2) / 2, 3.6, -0.128), (14.2 - x1, 2.4, 0.24), qc, bev=0.02)    # and along the basin's side to the foot of the town
    for k in range(9):                                   # its expansion joints
        K.box("quay joint", (-1.0 + 1.6 * k, 0.4, 0.0), (0.02, 4.0, 0.005), K.mat("quay joint", "#3A3836", rough=0.9), bev=0.0)
    edge = lw_paint("quay edge paint", "#D9B32E", rough=0.6)
    K.box("quay edge", (S5_EDGE_X + 0.1, -2.0, 0.03), (0.2, 7.0, 0.06), edge, bev=0.01)
    K.box("quay edge", (S5_EDGE_X + (x1 - S5_EDGE_X) / 2, y0 - 0.12, 0.03), (x1 - S5_EDGE_X, 0.2, 0.06), edge, bev=0.01)
    K.box("quay edge", (x1 + 0.1, (y0 + 4.8) / 2, 0.03), (0.2, 4.8 - y0, 0.06), edge, bev=0.01)
    iron = lw_metal("bollard iron", "#232527", rough=0.55)
    for k, (bx, by) in enumerate(((S5_EDGE_X + 0.35, y0 - 0.4), (-1.0, y0 - 0.4), (x1 + 0.4, 3.3), (x1 + 0.4, 4.4), (S5_EDGE_X + 0.35, -1.4))):     # cast-iron mooring bollards along the edge
        K.cyl("quay bollard", (bx, by, 0.09), 0.07, 0.18, iron, v=20)
        K.cyl("quay bollard cap", (bx, by, 0.2), 0.095, 0.05, iron, v=20)
        K.cyl("quay bollard foot", (bx, by, 0.015), 0.1, 0.03, iron, v=20)
    water = bpy.data.materials.new("harbour water"); water.use_nodes = True; wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (*K.lin("#1E3440"), 1); wb.inputs["Roughness"].default_value = 0.06
    wt = water.node_tree; nz = wt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; bp = wt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    wt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); wt.links.new(bp.outputs["Normal"], wb.inputs["Normal"])
    K.box("harbour water", (-14, 0, -0.45), (24, 60, 0.02), water, bev=0)
    # fishing boats moored in the basin (board: "white box stacks"): a lofted hull, sharp at the bow and full at the
    # stern, sheer rising forward, a painted band at the waterline; a planked deck with bulwarks; the wheelhouse aft
    # with windows all round and a coloured roof; a mast with its crosstree and lamps; a gantry at the stern; tyres
    # over the side for fenders; a real ring buoy on the wheelhouse
    for k, (x, y, yaw) in enumerate(((-1.0, 4.4, 0.0), (-1.9, 6.4, 0.05), (-2.9, 4.2, -0.04), (-3.9, 6.2, 0.08))):
        s5_boat(f"fishing boat {k}", (x, y), yaw, ("#2E5E8A", "#C33A2A", "#2E7A5A", "#1F3A5A")[k], ("#C33A2A", "#2E5E8A", "#E9E4D6", "#D9B32E")[k], seed=k)
    home = town_house("his town house", (5.6, 3.6, 0.0), yaw=0.0, w=3.2, d=2.6, storeys=1, base=0.3, roof="#2F5E8C", wall="#F1EEE6", seed=3)
    iron = lw_rust("hook iron", "#3A3430")
    # the hook is on a TIMBER MOORING PILE at the quay's edge (board: "the white post reads as nothing"): a tarred
    # round pile, iron bands, a mooring rope coiled round its foot
    pile = lw_wood("pile timber", "#5A4A3A", scale=0.5)
    px_ = S5_HOOK.x + 0.17
    K.cyl("lantern post", (px_, S5_HOOK.y, 0.45), 0.085, 0.9, pile, v=20)
    K.cyl("lantern post cap", (px_, S5_HOOK.y, 0.91), 0.088, 0.03, iron, v=20)
    for bz in (0.25, 0.7):
        K.cyl("lantern post band", (px_, S5_HOOK.y, bz), 0.09, 0.035, iron, v=20)
    rope = lw_canvas("mooring rope", "#B79A62")
    for j in range(3):
        K.cyl("mooring rope", (px_, S5_HOOK.y, 0.04 + 0.035 * j), 0.125 + 0.012 * j, 0.03, rope, v=24)
    K.box("lantern hook arm", (S5_HOOK.x + 0.06, S5_HOOK.y, S5_HOOK.z + 0.05), (0.2, 0.025, 0.025), iron, bev=0.004)
    K.box("lantern hook brace", (S5_HOOK.x + 0.1, S5_HOOK.y, S5_HOOK.z - 0.02), (0.13, 0.018, 0.018), iron, bev=0.003).rotation_euler = (0, math.radians(-45), 0)
    K.cyl("lantern hook", (S5_HOOK.x - 0.035, S5_HOOK.y, S5_HOOK.z + 0.025), 0.009, 0.05, iron, v=8)
    K.cyl("lantern hook curl", (S5_HOOK.x - 0.025, S5_HOOK.y, S5_HOOK.z + 0.002), 0.008, 0.03, iron, rot=(0, math.pi / 2, 0), v=8)
    quay = []
    for k, x in enumerate((9.6, 13.8, 18.0)):            # his neighbours along the quay, off to the right
        quay.append(town_house(f"quay house {k}", (x, 3.9 + 0.2 * k, 0.0), yaw=0.0, roof=ROOFS[(k * 3 + 2) % len(ROOFS)], wall=WALLS[(k + 2) % len(WALLS)], d=2.8, seed=50 + k))
    asph = ph_mat("asphalt_02", scale=2.0, tint="#7A7A7A", name="town street")
    for ys in (8.2, 12.6, 16.2):                         # the town's streets, across the slope
        lw_grid(f"town street {ys}", -26, 12.0 if ys < 16 else -0.5, ys - 0.7, ys + 0.7, 120, 4, lambda x, y: s5_slope_z(x, y) + 0.03, asph)
    town = []
    rows = [(10.2, (-12.6, -8.4, -4.2), 0), (14.4, (-14.0, -9.8, -5.6, -1.4), 0), (18.0, (-15.0, -10.8, -6.6, -2.4), 1)]     # (the lens's line up the hill to the burning row is left open: a street and rubble)
    for y, xs, one in rows:                              # the town that STANDS: below the wall, untouched, street over street
        for x in xs:
            k = len(town); x += rnd.uniform(-0.3, 0.3); yy = y + rnd.uniform(-0.2, 0.2)
            town.append(town_house(f"town house up {k}", (x, yy, s5_slope_z(x, yy - 1.4) - 0.05), yaw=rnd.uniform(-0.08, 0.08),
                                   roof=ROOFS[(k * 2 + 1) % len(ROOFS)], wall=WALLS[k % len(WALLS)], storeys=1 if one else None, seed=30 + k))
    for k, (x, y) in enumerate(((-18.0, 10.6), (-22.0, 14.0), (-20.0, 6.4), (-18.4, 18.0))):        # more of the town off to the left, filling the hill
        town.append(town_house(f"town house up {len(town)}", (x, y, s5_slope_z(x, y - 1.4) - 0.05), yaw=0.05, roof=ROOFS[k + 2], wall=WALLS[k + 3], seed=80 + k))
    # THE WALL: across the hill above the town, the old lava heaped up behind it, and its right end, where the new
    # lava got round
    WY = 21.6
    wall = earth_wall("earth wall", [(x, WY + 0.004 * x * x) for x in range(-26, 1, 2)], h=4.4, crest=1.4, base=8.0, seed=14)
    wall["root"].location.z = s5_slope_z(-8.0, WY) - 0.5
    tilt = math.atan(S5_SLOPE)
    held = lava_mat("lava held", heat=0.35, scale=1.6, fresh=0.05)
    pool = lava("lava held behind the wall", [(-26, 25.2), (0.5, 24.0), (0.5, 36), (-26, 36)], z=0.0, thick=1.4, m=held, seed=4, lumpy=0.35)
    c = pool.location.copy(); pool.rotation_euler.x = tilt; pool.location.z = s5_slope_z(-8, c.y) - 0.3
    fresh = lava_mat("lava field fresh", heat=0.8, scale=1.6, fresh=0.2)        # black crust, light only in its cracks and seams
    out = [(-1.0, 20.2), (2.4, 19.9), (6.4, 20.3), (10.4, 20.8), (14.0, 20.4), (18.0, 21.0), (24.0, 22.0), (24.0, 36.0), (-0.5, 36.0), (-1.4, 26.0)]
    flow = lava("new lava field", out, z=0.0, thick=0.9, m=fresh, seed=8, lumpy=0.4)
    c = flow.location.copy(); flow.rotation_euler.x = tilt; flow.location.z = s5_slope_z(8, c.y) - 0.2
    crust = lava_mat("lava front crust", heat=0.55, scale=7.0, fresh=0.15)
    for k in range(320):                                 # its FRONT: a ridge of broken black crust blocks, glowing in their cracks
        i = rnd.randrange(6); q = Vector(out[i]).lerp(Vector(out[i + 1]), rnd.random())
        q.y += rnd.uniform(-0.2, 1.2)
        rr = rnd.uniform(0.15, 0.5)
        lw_block("lava front block", (q.x, q.y, s5_slope_z(q.x, q.y) + 0.3 + rr * 0.4), rr, crust, rnd, squash=0.75)
    houses = list(town)
    for k, (x, y) in enumerate(((-0.6, 9.0), (4.2, 9.0), (8.6, 9.1), (-0.4, 13.4), (4.4, 13.4), (8.8, 13.5), (-0.2, 17.0))):     # REAL street lamps along the streets
        ph_model("street_lamp_01", (x, y, s5_slope_z(x, y)), rot=(0, 0, math.pi), scale=0.5, name=f"street lamp {k}")
    ph_model("fire_hydrant", (2.2, 8.9, s5_slope_z(2.2, 8.9)), rot=(0, 0, 0.3), scale=0.5, name="fire hydrant", only=("fire_hydrant", "fire_hydrant_cap_01"))
    for k, (x, y, r) in enumerate(((1.6, 11.0, 0.4), (6.8, 10.6, 2.0), (10.6, 12.0, 1.1), (3.2, 15.2, 2.6), (7.4, 15.6, 0.2), (11.4, 16.0, 1.7))):   # REAL mossy lava boulders on the open slope
        ph_model("rock_moss_set_02" if k % 2 else "boulder_01", (x, y, s5_slope_z(x, y) - 0.1), rot=(0, 0, r), scale=0.55 if k % 2 else 0.7, name=f"slope boulder {k}")
    for k, (x, y) in enumerate(((5.6, 11.6), (9.0, 14.6), (2.0, 14.8))):
        ph_model("old_tyre", (x, y, s5_slope_z(x, y) + 0.04), rot=(math.pi / 2, 0, 0.7 * k), scale=0.5, name=f"old tyre {k}")
    lava_rock("lava rubble", 1100, (-26, 26, 5.0, 24.0), s5_slope_z, seed=5, r=(0.05, 0.22), moss=0.45,
              avoid=lambda x, y: s5_water(x, y) or min(abs(y - 8.2), abs(y - 12.6), abs(y - 16.2)) < 0.85
              or any(abs(x - h_["root"].location.x) < 2.2 and abs(y - h_["root"].location.y) < 1.8 for h_ in houses))
    burning = []
    for k, (x, y) in enumerate(((0.8, 18.0), (5.0, 18.3), (9.2, 18.7))):     # at the lava's front, past the wall's end: three in a row across the frame, countable
        z = s5_slope_z(x, y - 1.3) - 0.05
        hs = town_house(f"burning house {k}", (x, y, z), yaw=rnd.uniform(-0.12, 0.12), w=3.6, d=2.6, roof=ROOFS[(k * 2) % len(ROOFS)],
                        wall=WALLS[(k + 1) % len(WALLS)], storeys=(2, 1, 2)[k], seed=40 + k, burn=1.0)
        lw_house_fire(hs, seed=11 + k, t_end=DUR + 1.0)
        burning.append(hs)
    for gx in (2.0, 8.0, 14.0):
        lw_point("lava front glow", (gx, 20.0, s5_slope_z(gx, 20) + 1.2), 900.0, col=(1.0, 0.35, 0.1), r=2.0)

    def light():
        k = iceland_light(sun_elev=3, sun_az=-55, sun=1.6, sky=0.18, warm=(1.0, 0.62, 0.45), haze=1.6)      # first light: dim enough that a lit window reads
        ph_sky("qwantani_sunrise_puresky", strength=0.35, rot=math.radians(150))       # a REAL dawn sky (Poly Haven)
        return k
    return dict(light=light, home=home, town=town, burning=burning, quay=quay)


def shot5():
    """THE QUAY AT DAWN. Low on the quay. He carries the lit lantern up the quay to the post by his door and hangs it; it
    swings, glowing; a few windows light up across the town, one here, one there; he turns to us and spreads his hands:
    would you?"""
    T_WALK1 = 0.4 * DUR; T_HANG = 0.48 * DUR; T_LET = T_HANG + 0.25
    T_WIN = 0.62 * DUR; T_TURN = 0.8 * DUR; T_ASK = 0.86 * DUR
    W = lw_win
    P = place_harbour_dawn()
    light = P["light"]
    data = load_data()
    rnd = lw_random.Random(7)
    P0 = Vector((S5_HOOK.x - 0.9, S5_HOOK.y + 0.75, 0.0))                 # he comes down the quay toward us and across to the pile
    STAND = Vector((S5_HOOK.x - 0.2, S5_HOOK.y + 0.1, 0.0))               # facing +X, the hook in front of his near shoulder
    data.place(P0.x, P0.y, 50.0)
    kit = hard_hat(data)
    data.walk_to((STAND.x, STAND.y), 0.15, T_WALK1 - 0.15)
    # ---- his body: the walk up the quay, the lift to the hook, a step back, the turn to us, the spread hands
    sc.frame_set(F(T_WALK1 - 0.15)); bpy.context.view_layer.update()
    YAW_H = math.radians(90)
    Y_IN = data.arm.rotation_euler.z                       # the way he faces as his walk ends: he turns to the pile from there
    Y_IN += 2 * math.pi * round((YAW_H - Y_IN) / (2 * math.pi))
    for f in range(F(T_WALK1 - 0.15) + 1, NF + 1):
        t = (f - 1) / FPS
        p = STAND.copy()
        p.z += 0.03 * W(t, T_HANG - 0.3, 0.25) * (1 - W(t, T_LET + 0.2, 0.3))                 # up on his toes to the hook
        p.x -= 0.05 * W(t, T_LET + 0.5, 0.5); p.y -= 0.1 * W(t, T_LET + 0.8, 0.45)   # a step back from it, and one toward us
        p.y -= 0.08 * W(t, T_ASK + 0.3, 0.7); p.z += 0.035 * lw_kick(t - T_ASK - 0.35, 0.22)   # and at the ask, a step to us and a shrug
        yaw = Y_IN + (YAW_H - Y_IN) * W(t, T_WALK1 - 0.15, 0.6) - math.radians(30) * W(t, T_LET + 0.2, 1.0) - math.radians(45) * W(t, T_TURN - 0.45, 0.4)
        data._kobj(t, loc=tuple(p), rot=yaw)
    lw_layer(data, "spine", lambda t: (-8 * W(t, T_HANG - 0.3, 0.3) * (1 - W(t, T_LET, 0.3)) + 6 * W(t, T_LET + 0.1, 0.3) * (1 - W(t, T_TURN, 0.3))
                                       - 6 * W(t, T_ASK, 0.3), 0, 0), 0, DUR + 0.4)
    sc.frame_set(F(T_HANG)); bpy.context.view_layer.update()
    near = sorted("LR", key=lambda s_: acts._shoulder(data, s_).y)               # near[0]: the hand toward the lens
    carry, other = near[0], near[1]
    # the lantern: in his near hand from the start, up onto the hook, then on its own, swinging
    lan = s5_lantern()
    CK = [(0.0, (0.08, 0.1, -0.08)), (T_WALK1 - 0.2, (0.09, 0.1, -0.07))]
    carry_fn = lw_hand(data, carry, CK)
    hook_at = lambda t: S5_HOOK + Vector((0.0, 0.0, 0.0))
    def hand_path(t):
        if t <= T_WALK1 - 0.2: return carry_fn(t)
        u = W(t, T_WALK1 - 0.2, T_HANG - T_WALK1 + 0.2)
        return carry_fn(T_WALK1 - 0.2).lerp(hook_at(t) + Vector((0, 0, 0.005)), u)
    # after the let-go: the lantern hand comes down slowly; his free hand waves up at the first window that lights,
    # comes down, then both spread wide to us
    AK = {carry: [(T_LET + 0.9, (0.07, 0.1, -0.07)), (T_ASK + 0.05, (0.07, 0.1, -0.08)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))],
          other: [(T_LET + 0.95, (0.06, 0.14, 0.03)), (T_LET + 1.2, (0.03, 0.16, 0.08)), (T_LET + 1.42, (0.03, 0.13, 0.09)), (T_LET + 1.64, (0.03, 0.16, 0.08)),
                  (T_ASK + 0.05, (0.08, 0.1, -0.06)), (T_ASK + 0.45, (0.06, 0.16, 0.04)), (DUR + 0.4, (0.06, 0.16, 0.05))]}
    down_fn = lw_hand(data, carry, AK[carry])
    def carry_path(t):                                       # ONE job for the lantern hand: carry, hang, then down slowly
        if t <= T_LET: return hand_path(t)
        return (hook_at(t) + Vector((0, 0, 0.005))).lerp(down_fn(t), W(t, T_LET, 1.1))
    data.reach(carry, carry_path, 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    def swing(t):                                           # after the let-go: a damped swing about the hook
        s = t - T_LET
        return 0.0 if s <= 0 else math.radians(24) * math.exp(-s / 2.2) * math.sin(2 * math.pi * s / 0.9)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        if t <= T_LET:
            sc.frame_set(f); bpy.context.view_layer.update()
            lan.location = data.arm.matrix_world @ data.pb[f"hand.{carry}"].tail + Vector((0, 0, -0.02))
            lan.rotation_euler = (0, math.radians(10) * math.sin(2 * math.pi * t / 0.55) * (1 - W(t, T_WALK1 - 0.2, 0.3)), 0)
        else:
            lan.location = S5_HOOK; lan.rotation_euler = (0, swing(t), 0)
        lan.keyframe_insert("location", frame=f); lan.keyframe_insert("rotation_euler", frame=f)
    data.reach(other, lw_hand(data, other, AK[other]), AK[other][0][0], DUR + 0.3, lead=1.0, back=None, elbow_out=0.4)
    # ---- face and head: one feeling per moment, held
    LENS = Vector((0.2, -2.4, 0.6))
    data.look_at(Vector((0.3, -2.4, 0.7)), 0.0, max_yaw=60, max_pitch=30, blend=0.0)      # his face to us as he comes (board: glasses off his face in profile)
    data.look_at(S5_HOOK, T_WALK1 - 0.1, max_yaw=50, max_pitch=40, blend=0.3)
    data.look_at(Vector((0.4, 9.0, 2.6)), T_LET + 0.2, max_yaw=8, max_pitch=30, blend=0.45)     # up the hill at the windows as he waves
    data.look_at(Vector((-0.8, 7.0, 2.0)), T_WIN + 0.12 * DUR, max_yaw=30, max_pitch=30, blend=0.45)
    data.look_at(LENS, T_TURN + 0.1, max_yaw=50, blend=0.45)
    data.expression("sad", 0.1, T_HANG - 0.1, blend=0.25)
    data.expression("determined", T_HANG, T_WIN, blend=0.2)
    data.expression("pleased", T_WIN + 0.1, T_ASK - 0.05, blend=0.25)
    data.expression("wry", T_ASK, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- the lens: low on the quay, the town and its burning edge up the slope behind him
    CAM = Vector((0.05, -0.45, 0.8)); LOOK = Vector((1.0, 14.0, 2.5))      # low on the quay: him and the post low, the open slope, the three houses burning up the hill at the lava front, the town standing to the left
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=28.0, fstop=16.0)
    # framed through compose.py (board: "frame 1 cuts Data at the left edge"): the lens is SOLVED so his face sits where
    # it should at his first step and at the pile, and it trucks between the two as he walks
    C0, L0 = compose.frame_data(data, CAM + Vector((P0.x - STAND.x, 0, 0)), LOOK + Vector((P0.x - STAND.x, 0, 0)), 28.0, face_at=(0.5, 0.44), height=0.36, t=0.15)
    C1, L1 = compose.frame_data(data, CAM, LOOK, 28.0, face_at=(0.42, 0.44), height=0.36, t=T_WALK1)
    def cam_at(t):                                          # it trucks with him down the quay to the pile, then holds
        u = ease(min(1.0, max(0.0, (t - 0.15) / (T_WALK1 - 0.15))))
        return C0.lerp(C1, u) + Vector((0.0, 0.1, 0.0)) * ease(t / DUR), L0.lerp(L1, u), data.pos() + Vector((0, 0, 0.6))
    # CUT to the WIDE on his walk to his door (board round 2: "no harbour, no boats, no wall", "three burning houses
    # against many untouched ones"): high over the harbour water, the boats in the basin, him at his door on the quay,
    # the town on its hill, the three houses burning at the black lava's edge, the wall above, the handful of lights
    T_W0, T_W1 = 0.28 * DUR, T_HANG - 0.35          # on his walk up the quay, his face to this lens (KEYS: never his back)
    CW = Vector((3.5, -6.5, 8.5)); LW = Vector((0.5, 14.0, 5.0))
    lw_cut(cam, cam_at, lambda t: (CW + Vector((-0.12, 0.2, -0.05)) * (t - T_W0), LW, Vector((0.0, 14.0, 5.0))), T_W0, T_W1, 28.0, 20.0)
    # ---- the payoff: windows light up ACROSS THE TOWN, one here, one there (board: "a few windows, not one"): the
    # windows this lens sees at that moment, in houses spread over the frame, a beat apart
    from bpy_extras.object_utils import world_to_camera_view as _w2c
    sc.frame_set(F(T_WIN + 0.3)); bpy.context.view_layer.update()
    seen = []
    for hs in P["town"] + P["quay"]:
        for wi, p in enumerate(hs["windows"]):
            v = _w2c(sc, cam, p.matrix_world.translation)
            if 0.04 < v.x < 0.96 and 0.08 < v.y < 0.95 and v.z > 0:
                seen.append((v.x, v.y, hs, wi))
    rnd_w = lw_random.Random(5); rnd_w.shuffle(seen)
    pick, used = [], {}
    for vx, vy, hs, wi in seen:                          # spread: at most two in a house, none on top of another
        if used.get(id(hs), 0) >= 4 or any(abs(vx - a_) < 0.06 and abs(vy - b_) < 0.04 for a_, b_, _h, _w in pick): continue
        pick.append((vx, vy, hs, wi)); used[id(hs)] = used.get(id(hs), 0) + 1
        if len(pick) >= 8: break
    lit, lit_houses = [], []
    for k, (_x, _y, hs, wi) in enumerate(pick):
        lit.append(s5_lit_pane(hs, wi, T_WIN + (-0.06 + 0.04 * k) * DUR))
        if hs not in lit_houses: lit_houses.append(hs)
    print(f"SHOT5 windows lit across the town: {len(lit)} in {len(lit_houses)} houses", flush=True)
    return dict(lanes=[], kiosks=[], place="harbour_dawn", light=light, data=data, rest=1, grips=("lantern", "lantern post", "lantern hook"), cutaway=(T_W0, T_W1),
                boxes=[],
                conseq=[("three houses still burn at the edge of the black lava", lambda: lw_drawn("burning house"), 0.0, DUR, {"whole": False}),
                        ("he hangs the lantern on the hook and it swings, glowing", lambda: meshes([lan]), T_HANG - 0.1, DUR, {"whole": False, "moves": True}),
                        ("a few windows light up along the quay and across the dark town, one here, one there", lambda: meshes([h["root"] for h in lit_houses]), T_WIN, DUR, {"whole": False})])
